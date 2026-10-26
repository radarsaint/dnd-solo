#!/usr/bin/env python3
"""Model-free phrase fuzzer for Kit (stdlib only).

Runs every player line in tests/corpus/player_lines.jsonl through KitChatBridge.prepare and
complete end to end on synthetic SRD rooms (tests/fixtures/fuzz/), with Kit's decision and
performance stubbed deterministically and dice pinned low, then:

* asserts the outcome the player gets (search/check, look, act, move, attack, spell,
  ritual or not, social, roll answered, Kit's ruling, refused), and
* scans every public / player-facing string for leaks: hidden fact text, hidden claim
  truths, hidden magic objects and where they are, hidden actor names, DC / AC / to-hit
  numbers. Text the engine itself declares revealed (player_view_after_event) is allowed.

Usage:
  python3 tools/kit_fuzz.py                 # run the corpus, print the failure table
  python3 tools/kit_fuzz.py --json out.json # also write every result
  python3 tools/kit_fuzz.py --only search   # one category
  python3 tools/kit_fuzz.py --line "I sift through the rubble." --room vault

Known failures live in tests/corpus/known_failures.json ({id: cause}); the unittest
wrapper (tests/test_kit_fuzz.py) fails only on a failure not listed there, so the suite stays
green while another branch fixes them, and reports listed cases that now pass.
"""
import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import kit_acts  # noqa: E402
from runtime.kit_agent import KitChatBridge, PendingRuling, RoomAdjudicator, start_session  # noqa: E402
from runtime.state_context import InvalidChange, Runtime  # noqa: E402

CORPUS = ROOT / 'tests/corpus/player_lines.jsonl'
KNOWN = ROOT / 'tests/corpus/known_failures.json'
SHEET = ROOT / 'tests/fixtures/characters/nik.json'
ROOMS = {
    'vault': 'tests/fixtures/fuzz/vault.json',
    'library': 'tests/fixtures/fuzz/library.json',
    'crypt': 'tests/fixtures/rooms/crypt.json',
}
OUTCOMES = ('search', 'look', 'act', 'move', 'attack', 'spell', 'social', 'roll', 'ruling', 'clarify', 'deferred',
            'refused')
# A PendingRuling that is not a refusal: the engine asks for a roll or a missing detail.
ATTACK_ASK = re.compile(r'Roll the attack|Who are you attacking|Roll initiative|Roll the .* damage', re.I)
CLARIFY_ASK = re.compile(r'Who are you trying that on|Whose words|What are you reading|Nobody here is fighting', re.I)
DEFERRED = re.compile(r'joins the public history once the turn in progress is committed', re.I)
# Engine action kinds (public action_kind / Resolution kind) -> player-visible outcome.
KINDS = {
    'check': 'search', 'check_request': 'search', 'knowledge': 'search', 'stealth': 'act',
    'social_check': 'social', 'called_check': 'roll',
    'observe': 'look', 'threshold_look': 'look', 'inspect_feature': 'look', 'handle_feature': 'look',
    'exit': 'move', 'exit_contested': 'move',
    'combat_round': 'attack', 'spell_cast': 'spell',
    'social': 'social', 'lie_read': 'social', 'toll_defer': 'social',
    'physical_act': 'ruling', 'feature_act': 'ruling', 'kit_ruling': 'ruling', 'ruling': 'ruling',
}
NUMBER_LEAKS = [re.compile(p, re.I) for p in (r'\bDC\s*(?:is|of|was|=|:)?\s*\d+', r'\bAC\s*(?:is|of|=|:)?\s*\d+', r'[+-]\d+\s+to\s+hit',
                                               r'\bdifficulty (?:class )?(?:of )?\d+')]
FILLER = ('The air is still and cool, and dust drifts slowly through the light around you.',
          'Somewhere above, old timbers settle with a soft creak, then go quiet again.',
          'Your own breath sounds loud here, and the shadows in the corners do not move.',
          'For a long moment nothing changes, and the place seems to wait on your next choice.')


class Harness:
    """One mounted session per room; every case runs on a fresh copy of it."""

    def __init__(self, rooms=ROOMS, complete=True):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.complete_turns = complete
        self.snapshots, self.secrets = {}, {}
        for name, ref in rooms.items():
            db = self.folder / f'{name}.sqlite'
            started = start_session(db, SHEET, room=str(ROOT / ref))
            runtime = Runtime(db)
            KitChatBridge(runtime, RoomAdjudicator()).abandon(started['prepared']['turn_id'])
            self.secrets[name] = secrets(runtime.source())
            runtime.close()
            self.snapshots[name] = db
        self.count = 0

    def close(self):
        self.temp.cleanup()

    def fresh(self, room):
        self.count += 1
        db = self.folder / f'case-{self.count}.sqlite'
        shutil.copyfile(self.snapshots[room], db)
        return Runtime(db), db

    def run(self, case):
        room = case.get('room', 'vault')
        runtime, db = self.fresh(room)
        try:
            return self._run(case, runtime, room)
        finally:
            runtime.close()
            db.unlink(missing_ok=True)

    def _run(self, case, runtime, room):
        bridge = KitChatBridge(runtime, RoomAdjudicator(roll=lambda: 2, npc_roll=lambda: 2))
        setup(runtime, case)
        if case.get('interject'):  # a message arriving while a prepared turn waits
            first = bridge.prepare(case['interject'], 'waiting', one_pass=True)
        out = {'id': case['id'], 'line': case['line'], 'room': room, 'category': case.get('category'),
               'expect': expected(case), 'leaks': [], 'notes': []}
        try:
            packet = bridge.prepare(case['line'], 'turn', one_pass=True)
        except PendingRuling as exc:
            text = str(exc)
            out.update(public=text, outcome='attack' if ATTACK_ASK.search(text) else 'clarify' if CLARIFY_ASK.search(text)
                       else 'deferred' if DEFERRED.search(text) else 'refused')
            out['leaks'] = scan(str(exc), self.secrets[room], case['line'])
            return judge(case, out)
        except InvalidChange as exc:
            out.update(outcome='error', public=str(exc))
            return judge(case, out)
        public = packet['input']['public']
        event = public.get('accepted_public_event', '')
        out['kind'] = public.get('action_kind')
        out['public'] = event
        out['outcome'] = classify(public)
        out['ritual'] = bool(re.search(r'as a ritual|ten minutes', event, re.I))
        out['leaks'] = scan(public_text(public), self.secrets[room], case['line'], revealed(public))
        if self.complete_turns and not case.get('interject'):
            result, why = complete(bridge, packet)
            if result is None:
                out['notes'].append(f'stub decision rejected: {why[:160]}')
            else:
                out['committed'] = True
                out['leaks'] += [f'complete: {leak}' for leak in scan(
                    player_facing(result), self.secrets[room], case['line'], revealed(public))]
        return judge(case, out)


def setup(runtime, case):
    """Per-case state: an area to stand in, a check Kit already called (roll lines)."""
    events = []
    if case.get('area'):
        exit_key = case.get('via')
        if exit_key:
            events.append({'type': 'move', 'exit': exit_key, 'evidence': 'Setup.'})
    if case.get('pending'):
        skill, ability, target = case['pending']
        events.append({'type': 'pending_check', 'check': {'skill': skill, 'ability': ability, 'target': target,
                                                           'called_turn': 'setup'}, 'evidence': 'Kit called the check.'})
    if events:
        revision, _ = runtime.load()
        runtime.commit('setup', revision, events)


def expected(case):
    exp = case['expect']
    return [exp] if isinstance(exp, str) else list(exp)


def classify(public):
    event = public.get('accepted_public_event', '')
    kind = public.get('action_kind')
    if event.startswith('You go ahead: '):
        return 'act'
    if kind == 'check' and event.startswith('You roll '):
        return 'roll'
    return KINDS.get(kind, kind or 'unknown')


def cause(out):
    """A short cause label for a failing result, so the report groups failures by why."""
    exp, got, line = out['expect'], out.get('outcome'), out['line'].casefold()
    if out['leaks']:
        if any('magic object' in leak for leak in out['leaks']):
            return 'leak: Detect Magic names hidden objects and where they are'
        return 'leak: hidden text or rules number in public output'
    if any(f.startswith('ritual') for f in out['failures']):
        return 'ritual flag wrong'
    if re.search(r"\b(?:don't|do not|won't|not|never mind|without)\b", line) and got not in exp:
        if re.search(r'not going in|without stepping|just peek', line):
            return 'peek without entering read as a move'
        return 'negation ignored'
    if got == 'refused' and set(exp) & {'search', 'ruling'}:
        return 'search refused ("needs a room/rules ruling")'
    if got == 'refused':
        return 'plain act, move or speech refused ("needs a room/rules ruling")'
    if 'roll' in exp and got != 'roll':
        return 'roll line not read as a roll'
    if exp == ['search'] or exp == ['search', 'social'] or set(exp) == {'look', 'search'} and got not in exp:
        return {'refused': 'search refused ("needs a room/rules ruling")',
                'social': 'search read as speech (gesture verb wins)',
                'act': 'search read as a simple act (no check)',
                'ruling': 'search on a watched feature becomes a handles ruling (no check)',
                'look': 'search read as a free look (no check)',
                'move': 'search read as a move'}.get(got, f'search read as {got}')
    if got == 'move' and 'look' in exp:
        return 'peek without entering read as a move'
    if 'look' in exp and got not in exp:
        return f'look phrasing read as {got}'
    if 'move' in exp:
        return f'move phrasing read as {got}'
    if 'attack' in exp:
        return f'attack read as {got}'
    if exp == ['social']:
        return f'speech read as {got}'
    if got == 'refused':
        return 'plain act refused ("needs a room/rules ruling")'
    return f'{"/".join(exp)} read as {got}'


def judge(case, out):
    failures = []
    if out['outcome'] not in out['expect']:
        failures.append(f"outcome {out['outcome']} not in {out['expect']}")
    if 'ritual' in case and out.get('outcome') == 'spell' and out.get('ritual') != case['ritual']:
        failures.append(f"ritual {out.get('ritual')} expected {case['ritual']}")
    if out['leaks']:
        failures.append('leak: ' + '; '.join(out['leaks']))
    out['failures'] = failures
    out['ok'] = not failures
    if failures:
        out['cause'] = cause(out)
    return out


# ---- leak scanning -------------------------------------------------------------------------

def secrets(source):
    """(label, text) for everything the player must not see before finding it."""
    found = []
    facts = source.get('facts') or {}
    for key, fact in facts.items():
        if not isinstance(fact, dict) or fact.get('visible', True):
            continue
        found.append((f'hidden fact {key}', fact.get('text', ''), key))
        objects = fact.get('magic_objects') or {}
        for part in ('what', 'where'):
            if objects.get(part):
                found.append((f'hidden magic object {key}.{part}', objects[part], key))
        for noun in ((fact.get('handling') or {}).get('nouns') or ()):
            found.append((f'hidden object noun {key}', noun, key))
    for key, claim in (source.get('claims') or {}).items():
        if claim.get('exposure') == 'hidden':
            found.append((f'hidden claim {key}', claim.get('truth', ''), claim.get('fact') or key))
            found.append((f'hidden DC {key}', f"DC {claim['dc']}", claim.get('fact') or key)) if 'dc' in claim else None
    for key, actor in (source.get('actors') or {}).items():
        if actor.get('status') == 'hidden' or actor.get('visible') is False:
            found.append((f'hidden actor {key}', actor.get('name', ''), f'actor:{key}'))
    texts = {key: fact.get('text', '') for key, fact in facts.items() if isinstance(fact, dict)}
    return [(label, text, group, texts.get(group, '')) for label, text, group in found if text and len(text) >= 3]


def _norm(text):
    return re.sub(r'\s+', ' ', re.sub(r"[^\w\s']", ' ', str(text).casefold())).strip()


def scan(text, room_secrets, line='', allowed=()):
    """Leaks in ``text``: secret strings (or nouns as whole words) and rules numbers. The
    player's own words and engine-declared reveals are removed first."""
    body = _norm(text)
    for skip in (line, *allowed):
        if skip:
            body = body.replace(_norm(skip), ' ')
    leaks = []
    said = _norm(line)
    shown = [_norm(a) for a in allowed]
    for label, secret, group, fact_text in room_secrets:
        needle = _norm(secret)
        if not needle or needle in said:
            continue
        if any(needle in a for a in shown) or (fact_text and _norm(fact_text) in shown):
            continue  # the engine revealed this fact this turn
        hit = re.search(rf'\b{re.escape(needle)}\b', body) if 'noun' in label else needle in body
        if hit:
            leaks.append(f'{label}: "{secret}"')
    for pattern in NUMBER_LEAKS:
        for m in pattern.finditer(str(text)):
            if m.group(0).casefold() not in str(line).casefold():
                leaks.append(f'rules number: "{m.group(0)}"')
    return leaks


def revealed(public):
    """Strings the engine itself declares the player now knows this turn."""
    view = public.get('player_view_after_event') or {}
    if not isinstance(view, dict):
        return []
    out = []
    for value in (view.get('appended') or {}).values():
        out += [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]
    for value in (view.get('changed') or {}).values():
        if isinstance(value, str):
            out.append(value)
    return out


def public_text(public):
    keep = {k: v for k, v in public.items() if k not in ('player_action', 'shared_with_private',
                                                         'player_view_after_event')}
    return json.dumps(keep, ensure_ascii=False)


def player_facing(result):
    """The strings a committed turn shows the player (spoken lines, public event)."""
    parts = []

    def walk(value, key=''):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ('timing', 'private', 'manifest', 'kit_state'):
                    continue
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif isinstance(value, str) and key in ('text', 'spoken', 'public_event', 'accepted_public_event',
                                                'player_text', 'message', 'reply'):
            parts.append(value)
    walk(result)
    return '\n'.join(parts)


# ---- the deterministic Kit stub ----------------------------------------------------------

def stub_decision(private):
    from_tests = ROOT / 'tests'
    if str(from_tests) not in sys.path:
        sys.path.insert(0, str(from_tests))
    from test_kit_agent import RecordingModel
    plan = RecordingModel().plan(private)
    plan.update({'move': 'world_description', 'table_presence': 'quiet', 'focus_actor': 'none'})
    plan['improv_read'].update(actor_ref='none', actor_basis='none')
    offers = private.get('acts') or {}
    if offers.get('handles'):
        plan['handles'] = {'target': 'none', 'act': 'none', 'reason': kit_acts.NONE_REASONS[0]}
    if offers.get('downed'):
        plan['downed'] = {'act': 'turn_away'}
    return plan


def stub_performance(event, words=60):
    first = event or 'You take it in.'
    return {'segments': [{'speaker': 'Narrator', 'text': ' '.join((first,) + FILLER[:2])},
                         {'speaker': 'Narrator', 'text': ' '.join(FILLER[2:])}]}


def complete(bridge, packet):
    """Commit the turn with the stub; (result, None) or (None, last rejection)."""
    private = packet['input']['private']
    event = packet['input']['public'].get('accepted_public_event', '')
    plan = stub_decision(private)
    why = ''
    for perf in (stub_performance(''), stub_performance(event)):
        try:
            return bridge.complete(packet['turn_id'], {'decision': plan, 'performance': perf}), None
        except InvalidChange as exc:
            why = str(exc)
            continue
        except PendingRuling as exc:
            return None, str(exc)
    try:
        bridge.abandon(packet['turn_id'])
    except Exception:  # noqa: BLE001 - a stub that cannot commit just leaves the prepare
        pass
    return None, why


# ---- corpus run ---------------------------------------------------------------------------

def load_corpus(path=CORPUS):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def load_known(path=KNOWN):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else {}


def run_corpus(cases=None, complete_turns=True):
    cases = load_corpus() if cases is None else cases
    harness = Harness(complete=complete_turns)
    try:
        return [harness.run(case) for case in cases]
    finally:
        harness.close()


def table(results, known):
    rows = defaultdict(Counter)
    for r in results:
        cat = r.get('category') or '?'
        rows[cat]['total'] += 1
        if not r['ok']:
            rows[cat]['known' if r['id'] in known else 'NEW'] += 1
        if r['leaks']:
            rows[cat]['leaks'] += 1
    lines = [f"{'category':<14}{'total':>6}{'fail':>6}{'known':>7}{'NEW':>5}{'leaks':>7}"]
    for cat in sorted(rows):
        c = rows[cat]
        lines.append(f"{cat:<14}{c['total']:>6}{c['known'] + c['NEW']:>6}{c['known']:>7}{c['NEW']:>5}{c['leaks']:>7}")
    return '\n'.join(lines)


def by_cause(results, known):
    causes = Counter(r['cause'] for r in results if not r['ok'])
    lines = [f"{'n':>4}  cause"]
    for label, n in causes.most_common():
        example = next(r['line'] for r in results if r.get('cause') == label)
        lines.append(f'{n:>4}  {label}   e.g. {example!r}')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json')
    ap.add_argument('--only', help='one category')
    ap.add_argument('--line')
    ap.add_argument('--room', default='vault')
    ap.add_argument('--no-complete', action='store_true', help='prepare only (faster)')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)
    if args.line:
        cases = [{'id': 'cli', 'line': args.line, 'room': args.room, 'expect': list(OUTCOMES), 'category': 'cli'}]
    else:
        cases = load_corpus()
        if args.only:
            cases = [c for c in cases if c.get('category') == args.only]
    clock = time.perf_counter()
    results = run_corpus(cases, not args.no_complete)
    elapsed = time.perf_counter() - clock
    known = load_known()
    if args.line:
        print(json.dumps(results[0], indent=1, ensure_ascii=False))
        return 0
    print(table(results, known))
    print()
    print(by_cause(results, known))
    new = [r for r in results if not r['ok'] and r['id'] not in known]
    fixed = [r for r in results if r['ok'] and r['id'] in known]
    for r in results:
        if not r['ok'] and (args.verbose or r['id'] not in known):
            tag = f"known: {known[r['id']]}" if r['id'] in known else 'NEW'
            print(f"- {r['id']} [{tag}] {r['line']!r}: {'; '.join(r['failures'])} | {r.get('public', '')[:140]}")
    for r in fixed:
        print(f"+ {r['id']} now passes (listed known: {known[r['id']]})")
    print(f"{len(results)} lines, {sum(not r['ok'] for r in results)} failing "
          f"({len(new)} new), {sum(1 for r in results if r.get('committed'))} committed, {elapsed:.1f}s")
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding='utf-8')
    return 1 if new else 0


if __name__ == '__main__':
    sys.exit(main())
