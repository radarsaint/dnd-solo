"""Nagatha's acceptance sets for #122 (/tmp/rvdf ord, fz, g; /tmp/rv5d; /tmp/rv92), copied into
tests/fixtures/declared, each message with the entries Kit would declare for it, hand-written
(*.decl, one line per message; '-' is a turn where she declares no combat act: a question, a
taunt, a look). Every declared entry gets a clause record; every refusal is said; a missing roll
is an Avrae ask with nothing committed. Rope bridge (rogue), kiln (warlock, wizard); dice pinned.

.decl entry syntax, entries joined by ' ; ', the roll after '=' verbatim ('\\n' for a newline):
  atk T WEAPON =roll | thr T WEAPON =roll (thrown) | bon T WEAPON =roll | spl T|- SPELL =roll | rea REACTION [T] [=roll]
  away FEET | toward T | dodge | dash | disengage | hide [=roll] | help | grab T [=roll]
  shove T [=roll] | obj his words"""
import os
import re
import unittest
from pathlib import Path

from runtime.kit_agent import PendingRuling
from test_kit_review101c import Arena, KILN_OPEN, clause_log, rogue, warlock, without_shield, wizard

HERE = Path(__file__).resolve().parent / 'fixtures' / 'declared'
SETS = ('ord', 'fz', 'g', 'rv5d', 'rv92')
REPORT = os.environ.get('KIT_ACCEPT_REPORT')  # write the per-message outcomes here when set


def sheet(kind):
    if kind == 'rb':
        return rogue(gear=['rapier', 'dagger (thrown)', 'shortbow'])
    if kind == 'wl':
        return warlock(hp=60, gear=['dagger', 'rapier'])
    found = without_shield(wizard(hp=60))
    found['spells']['1'] = found['spells']['1'] + ['Absorb Elements']
    return found


def arena(test, kind):
    if kind == 'rb':
        made = Arena(test, 'rope_bridge', sheet=sheet(kind), roll=lambda: 10)
        made.act('Initiative 25. I stab the bridge ogre with my rapier, 5 to hit, 3 piercing.')
    else:
        made = Arena(test, 'kiln', sheet=sheet(kind), roll=lambda: 10)
        made.act(KILN_OPEN)
    return made


def entries(line):
    if line.strip() == '-':
        return None
    out = []
    for order, part in enumerate(line.split(' ; '), 1):
        head, _, roll = part.partition(' =')
        words = head.split()
        kind, rest = words[0], words[1:]
        entry = {'order': order}
        if roll:
            entry['roll'] = roll.replace('\\n', '\n')
        if kind in ('atk', 'bon', 'thr'):
            entry.update(kind='bonus_attack' if kind == 'bon' else 'attack', target=rest[0], weapon=' '.join(rest[1:]))
            if kind == 'thr':
                entry['thrown'] = True
        elif kind == 'spl':
            entry.update(kind='spell', target=None if rest[0] == '-' else rest[0], spell=' '.join(rest[1:]))
        elif kind == 'rea':
            entry.update(kind='reaction', reaction=rest[0], **({'target': rest[1]} if len(rest) > 1 else {}))
        elif kind == 'away':
            entry.update(kind='move', way='away', distance_ft=int(rest[0]))
        elif kind == 'toward':
            entry.update(kind='move', way='toward', target=rest[0])
        elif kind == 'grab':
            entry.update(kind='grapple', target=rest[0])
        elif kind == 'shove':
            entry.update(kind='shove', target=rest[0])
        elif kind == 'obj':
            entry.update(kind='object', says=' '.join(rest))
        else:
            assert kind in ('dodge', 'dash', 'disengage', 'hide', 'help'), kind
            entry['kind'] = kind
        out.append({k: v for k, v in entry.items() if v is not None})
    return out


def cases():
    for name in SETS:
        msgs = (HERE / f'{name}.txt').read_text().strip().split('\n')
        decls = (HERE / f'{name}.decl').read_text().rstrip('\n').split('\n')
        assert len(msgs) == len(decls), name
        for index, (msg, decl) in enumerate(zip(msgs, decls), 1):
            kind, text = msg.split('|', 1)
            yield f'{name}#{index}', kind, text.replace('\\n', '\n'), entries(decl)


class AcceptanceSets(unittest.TestCase):
    def test_every_declared_entry_is_recorded_and_every_refusal_said(self):
        lines = []
        counted = 0
        for label, kind, text, declared in cases():
            if declared is None:
                lines.append(f'{label} [{kind}] {text!r}\n   -> no combat_acts (Kit answers or narrates)')
                continue
            made = arena(self, kind)
            before = (made.fight.get('hp'), made.fight.get('pc_damage'), made.state['pc_resources'])
            try:
                result = made.act(text, combat_acts=declared)
            except PendingRuling as caught:
                self.assertIn('No turn was committed', str(caught), label)
                self.assertEqual((made.fight.get('hp'), made.fight.get('pc_damage'), made.state['pc_resources']),
                                 before, label)
                lines.append(f'{label} [{kind}] {text!r}\n   -> ASK {str(caught)[:160]}')
                counted += 1
                continue
            log = clause_log(result)
            self.assertEqual([c[0] for c in log], list(range(1, len(declared) + 1)), (label, result.public_event))
            if any(c[2] == 'refused' for c in log):
                self.assertIn("didn't happen because", result.public_event, label)
            fight = made.fight
            lines.append(f'{label} [{kind}] {text!r}\n   -> {result.public_event}\n   clauses='
                         f'{[c[2] for c in log]} hp={fight.get("hp")} pc_damage={fight.get("pc_damage")}')
            counted += 1
        self.assertGreater(counted, 180)
        if REPORT:
            Path(REPORT).write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    unittest.main()
