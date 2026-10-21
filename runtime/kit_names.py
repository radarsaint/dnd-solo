"""One name-set for every foe: the open-ask damage gate, attack targeting and the "That names X"
reply all read names here (Nagatha's re-probe of #127 at e486b18 and #135 at ef92808).

A numbered label ("Giant rat 3") is named by its full label, by its head noun and number ("rat 3",
"rat-3", "rat #3") and by its bare head noun ("rat"), which every rat shares, so it names none of
them alone. A bare number is never a name. A name with no number does not match where a number
follows it when the actor is numbered ("rat" inside "rat 3"). Where one foe's name sits inside a
longer match of another's, only the longer one counts.

Also here, so a branch without the unperceived-actor PR carries the same rule: ``unperceived``
(identical to state_context.unperceived) and ``perceivable``."""
import re

UNPERCEIVED_FLAGS = ('hidden', 'invisible', 'concealed', 'unseen')
GONE_STATUSES = ('dead', 'fled', 'destroyed')
ORDINALS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7,
            'eighth': 8, 'ninth': 9, 'tenth': 10, '1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5,
            '6th': 6, '7th': 7, '8th': 8, '9th': 9, '10th': 10}


def unperceived(actor):
    """True for a creature still there (not dead or fled) that the PC cannot currently perceive."""
    if not isinstance(actor, dict) or actor.get('status') in GONE_STATUSES:
        return False
    conditions = {str(c).casefold() for c in actor.get('conditions') or ()}
    return (actor.get('status') == 'hidden' or actor.get('visible') is False or
            any(actor.get(flag) is True for flag in UNPERCEIVED_FLAGS) or bool(conditions & set(UNPERCEIVED_FLAGS)))


def merged(source, state, key):
    return {**(((source or {}).get('actors') or {}).get(key) or {}),
            **(((state or {}).get('actors') or {}).get(key) or {})}


def perceivable(source, state, key):
    return not unperceived(merged(source, state, key))


def _labels(source):
    from .kit_combat import labels  # local: kit_combat imports this module
    return labels(source)


def numbered(label):
    """(stem, number) of a numbered label ('giant rat 3' -> ('giant rat', '3')), else None."""
    found = re.fullmatch(r"(.*?[a-z][\w' -]*?)[\s-]*#?(\d{1,3})", (label or '').casefold().strip())
    return (found.group(1).strip(' -'), found.group(2)) if found else None


def head(stem):
    words = re.split(r'[\s-]+', stem.strip())
    return words[-1] if words else ''


def names(source, key):
    """Every name of one actor (see the module note)."""
    from .kit_combat import _names  # local: kit_combat imports this module
    out = {n for n in _names(source, key) if re.search(r'[a-z]', n)}
    label = _labels(source).get(key, key).casefold()
    num = numbered(label)
    if num:
        stem, n = num
        noun = head(stem)
        out |= {f'{stem} {n}', f'{noun} {n}', noun}
    return {n for n in out if n}


def _pattern(name, numbered_actor=False):
    """A name's pattern. A numbered actor's unnumbered name ('rat', 'giant') does not match where a
    number follows ('rat 3' is Giant rat 3's, not every rat's)."""
    parts = [re.escape(p) for p in re.split(r'[\s-]+', name) if p]
    if parts and parts[-1].isdigit():
        body = r'[\s-]+'.join(parts[:-1]) + r'[\s-]*#?' + parts[-1]
        return rf'(?<![\w-]){body}(?![\w-])'
    return rf'(?<![\w-]){r"[\s-]+".join(parts)}(?![\w-])' + (r'(?![\s-]*#?\d)' if numbered_actor else '')


def spans(text, source, candidates):
    """[(key, start, end)] where the words name a candidate."""
    low = (text or '').casefold()
    found = []
    label_of = _labels(source)
    for key in candidates:
        is_numbered = bool(numbered(label_of.get(key, key)))
        for name in names(source, key):
            for match in re.finditer(_pattern(name, is_numbered), low):
                found.append((key, match.start(), match.end()))
    return [(key, s, e) for key, s, e in found
            if not any(o_s <= s and e <= o_e and (o_e - o_s) > (e - s) for other, o_s, o_e in found if other != key)]


def groups(text, source, candidates):
    """[(start, end, keys)] in text order: each place a name sits and every candidate it fits."""
    out = {}
    for key, s, e in spans(text, source, candidates):
        out.setdefault((s, e), set()).add(key)
    # A span inside a longer span at the same place is the longer one's.
    kept = {(s, e): keys for (s, e), keys in out.items()
            if not any(o_s <= s and e <= o_e and (o_s, o_e) != (s, e) for o_s, o_e in out)}
    low = (text or '').casefold()
    label_of = _labels(source)
    for (s, e), keys in kept.items():
        # A foe whose whole label is the words ('Bandit' beside Bandit 3 and Bandit 12) is that foe.
        said = re.sub(r'[\s-]+', ' ', low[s:e])
        exact = {k for k in keys if re.sub(r'[\s-]+', ' ', label_of.get(k, k).casefold()) == said}
        if len(keys) > 1 and len(exact) == 1:
            kept[(s, e)] = exact
    return [(s, e, keys) for (s, e), keys in sorted(kept.items())]


def ordinal(text, source, candidates):
    """(key or None, tied) for 'the third rat': the rat numbered 3 if there is one, else every rat."""
    for match in re.finditer(r'\b(' + '|'.join(ORDINALS) + r')\s+([a-z][\w-]*)', (text or '').casefold()):
        n, noun = str(ORDINALS[match.group(1)]), match.group(2)
        fits = [k for k in candidates if noun in names(source, k)]
        if not fits:
            continue
        exact = [k for k in fits if (numbered(_labels(source).get(k, k)) or ('', ''))[1] == n]
        return (exact[0], []) if len(exact) == 1 else (None, sorted(fits))
    return None, []


def resolve(text, source, candidates):
    """(key, tied): the one candidate the words name first, else (None, the candidates the first
    name fits when it fits several), else (None, [])."""
    key, tied = ordinal(text, source, candidates)
    if key or tied:
        return key, tied
    found = groups(text, source, candidates)
    if not found:
        return None, []
    keys = found[0][2]
    return (next(iter(keys)), []) if len(keys) == 1 else (None, sorted(keys))


def missing_numbered(text, source, candidates):
    """(shown label, actor key or None) for a numbered foe the words name that is not among the
    candidates ('giant rat 1' with only Giant rat 3 here, 'bandit 12'), else None."""
    label_of = _labels(source)
    stems = {}
    for key in (source or {}).get('actors') or {}:
        num = numbered(label_of.get(key, key))
        if num:
            stems.setdefault(head(num[0]), num[0])
            stems.setdefault(num[0], num[0])
    if not stems:
        return None
    low = (text or '').casefold()
    for stem in sorted(stems, key=len, reverse=True):
        body = r'[\s-]+'.join(re.escape(p) for p in re.split(r'[\s-]+', stem))
        for match in re.finditer(rf'(?<![\w-]){body}[\s-]*#?(\d{{1,3}})(?![\w-])', low):
            n = match.group(1)
            here = [k for k in candidates if (numbered(label_of.get(k, k)) or ('', ''))[1] == n and
                    head((numbered(label_of.get(k, k)) or ('', ''))[0]) == head(stem)]
            if here:
                continue
            full = stems[stem]
            key = next((k for k in (source or {}).get('actors') or {}
                        if numbered(label_of.get(k, k)) == (full, n)), None)
            shown = f'{full} {n}'
            return shown[:1].upper() + shown[1:], key
    return None


def shown(source, keys):
    label_of = _labels(source)
    out = sorted(label_of.get(k, k) for k in keys)
    return out[0] if len(out) == 1 else f"{', '.join(out[:-1])} or {out[-1]}"
