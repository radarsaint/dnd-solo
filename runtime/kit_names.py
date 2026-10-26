"""What the player's words name among the creatures here (one name-set for every caller).

A numbered label ("Giant rat 5") is named by its full label and any tail of it that keeps the number
("rat 5"); its unnumbered words ("giant rat", "rat", "giant") name the whole family and so name no
single one when several share them. Rules, in order:
* A bare number is never a name ("Initiative 6" names no rat).
* A numbered creature's unnumbered name gives way right before a digit ("rat 3" is not every rat).
* An ordinal ("the third rat") is that number when a creature has it.
* The earliest name in the words wins; at the same place, the longest; a name inside a longer match
  does not count. Several creatures at the same place: the one whose whole label is the word
  ("Bandit" beside Bandit 3), else none (``resolve`` returns them so the caller can ask).
* Only creatures the PC can perceive are named (``perceivable``).
Stdlib only; no room text is invented here."""
import re

ORDINALS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7,
            'eighth': 8, 'ninth': 9, 'tenth': 10}
_ORDINAL = re.compile(r"\b(?:the\s+)?(" + '|'.join(ORDINALS) + r"|(\d+)(?:st|nd|rd|th))\s+([a-z][\w'-]*)")
_NUMBERED = re.compile(r"^(.*\D)\s+(\d+)$")
HIDING = ('hidden', 'invisible', 'concealed', 'unseen')


def numbered(label):
    """(base, number) for 'giant rat 5' -> ('giant rat', '5'); else None."""
    found = _NUMBERED.match((label or '').casefold().strip())
    return (found.group(1).strip(), found.group(2)) if found else None


def perceivable(actor):
    """False for a creature marked unseen in any way the room schema allows."""
    actor = actor or {}
    if actor.get('status') == 'hidden' or actor.get('visible') is False:
        return False
    if any(actor.get(flag) is True for flag in HIDING):
        return False
    return not any(str(c).casefold() in HIDING for c in actor.get('conditions') or ())


def names(source, key, labels=None, extra=()):
    """Every name for ``key`` (casefolded). ``extra``: names the caller adds (palette words)."""
    labels = _labels(source) if labels is None else labels
    actor = (source.get('actors') or {}).get(key) or {}
    label = labels.get(key, key).casefold()
    found = {label, label.replace('-', ' '), (actor.get('name') or '').casefold()}
    words = label.split()
    if words and words[0] not in ('the', 'pale'):
        found.add(words[0])
    num = numbered(label)
    if num:
        base, n = num
        tail = base.split()
        for i in range(len(tail)):
            found.add(' '.join(tail[i:] + [n]))  # 'giant rat 5', 'rat 5'
        found |= {base, tail[-1]}  # the family: 'giant rat', 'rat'
    elif words and all((labels.get(other, other).casefold().split() or [''])[-1] != words[-1]
                       for other in (source.get('actors') or {}) if other != key):
        found.add(words[-1])  # the head noun when only this actor has it: 'watch warden' -> 'warden'
    found |= {n.casefold() for n in extra}
    return {n for n in found if n and n != 'pale man' and not n.isdigit()}


def _ordinals(text, source, keys, labels):
    """'the third rat' -> 'rat 3' when a creature here is rat 3; else just 'rat'."""
    def swap(m):
        n = str(ORDINALS.get(m.group(1)) or m.group(2))
        noun = m.group(3)
        for key in keys:
            num = numbered(labels.get(key, key))
            if num and num[1] == n and noun in num[0].split():
                return f'{noun} {n}'
        return noun
    return _ORDINAL.sub(swap, text)


def _matches(text, source, keys, labels, extra):
    out = []
    for key in keys:
        is_numbered = bool(numbered(labels.get(key, key)))
        for name in names(source, key, labels, extra(key) if extra else ()):
            for m in re.finditer(rf"\b{re.escape(name)}\b", text):
                if is_numbered and not re.search(r'\d', name) and re.match(r'\s*\d', text[m.end():]):
                    continue  # gives way before a number: 'rat 3' is not every rat
                out.append((m.start(), m.end(), key))
    return [m for m in out if not any(o[0] <= m[0] and m[1] <= o[1] and (o[1] - o[0]) > (m[1] - m[0])
                                      for o in out)]


def resolve(text, source, keys, labels=None, extra=None, skip=()):
    """(key, []) for the one creature the words name; (None, [tied keys]) when a shared name fits
    several at the same place; (None, []) for none. ``skip``: spans no name may touch."""
    labels = _labels(source) if labels is None else labels
    text = _ordinals((text or '').casefold(), source, keys, labels)
    found = [m for m in _matches(text, source, keys, labels, extra)
             if not any(m[0] < s1 and s0 < m[1] for s0, s1 in skip)]
    if not found:
        return None, []
    start = min(m[0] for m in found)
    longest = max(m[1] for m in found if m[0] == start)
    tied = sorted({m[2] for m in found if m[0] == start and m[1] == longest})
    if len(tied) == 1:
        return tied[0], []
    word = text[start:longest]
    whole = [k for k in tied if labels.get(k, k).casefold() == word]
    return (whole[0], []) if len(whole) == 1 else (None, sorted(tied, key=lambda k: _order(labels, k)))


def _order(labels, key):
    num = numbered(labels.get(key, key))
    return (num[0], int(num[1])) if num else (labels.get(key, key).casefold(), 0)


def missing_numbered(text, source, area_keys, keys, labels):
    """[(span, shown)] for each '<noun> N' the words name that no creature in ``keys`` is, where the
    noun heads a numbered family in the area: 'rat 3' -> 'Giant rat 3'."""
    text = _ordinals((text or '').casefold(), source, keys, labels)
    have = {numbered(labels.get(k, k)) for k in keys} - {None}
    families = {}
    for key in area_keys:
        label = labels.get(key, key)
        num = numbered(label)
        if num:
            families.setdefault(num[0].split()[-1], re.sub(r'\s*\d+$', '', label.strip()))
    out = []
    for m in re.finditer(r"\b([a-z][\w'-]*)\s+(\d+)\b", text):
        noun, n = m.group(1), m.group(2)
        if noun in families and not any(base.split()[-1] == noun and num == n for base, num in have):
            lead = families[noun].casefold().split()[:-1]  # 'giant rat 1' spans its family words too
            start = m.start()
            before = text[:start].split()
            if lead and before[-len(lead):] == lead:
                start = text.rfind(lead[0], 0, start)
            out.append(((start, m.end()), f'{families[noun]} {n}'))
    return out


def _labels(source):
    from .kit_agent import actor_speakers  # local: kit_agent imports kit_combat, which imports this
    return actor_speakers(source)
