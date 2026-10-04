"""The fidelity diff: an authored room against its source manifest (runtime/kit_extract.py).

Source-agnostic. This module reads only the manifest's shape (sentences with their secret
flags, creatures and counts, named NPCs, items, hazards, numbers, named ways out) and the
room's own fields; how any particular source is written lives in its extractor. Every
difference is reported at once (the repair gets one try):

- creatures: every one the source introduces, with its count and its visibility (one the
  source hides is ``status: hidden``); no creature the source does not have. A creature the
  manifest cannot place (two sentences for one rat, a beast that is really a named NPC) is
  settled by the room's ``source_claims``: ``[{"quote": "<words from the source>",
  "actors": [ids], "facts": [ids]}]``; every quote must be in the source slice.
- named NPCs are actors; their deceptions and true natures are carried on the dm side.
- every secret, treasure and hazard sentence is carried (its distinctive words and numbers);
- numbers: no DC, hit points, gp value, dice or attack bonus the source does not state;
  inline stat blocks only with the source's own numbers (else an SRD reference, else
  ``needs_stats``);
- hazards are traps (runtime/kit_traps.py) with the source's dice;
- ways out: only to areas the source names as a way from here (or sibling sub-areas),
  ``uncertain: true`` while no geometry ledger binds them, no secret way the source lacks,
  no place name the source does not use;
- the leak scan: every player-visible field, against hidden actors' names and the words only
  the source's secret sentences use; no DC or bonus in public text.
"""
import re

from . import srd_creatures
from .kit_extract import norm, stem, stems

POSITIONAL = {stem(w) for w in (
    'mouth end side edge way back front entrance entry approach outside inside beyond threshold doorway path near '
    'far corner middle center centre north south east west northern southern eastern western northeast northwest '
    'southeast southwest opening between past behind ahead onward onwards there here place spot area room stand '
    'standing just next last first other away along across through around toward towards from into upon over '
    'under below above down with the this that your their where what before after nearest farther further '
    'beside within without left right start leading leads lead going gone back way ways passage tunnel door '
    'doors hall corridor floor wall walls rest close closer step steps').split()}
GENERIC = {stem(w) for w in (
    'this that with from into their there they them then than room area floor wall walls door each also once other '
    'have here when which while these those what where some only more most like over under onto upon until after '
    'before creature creatures character characters anyone large small giant body thing something someone being '
    'made make makes look looks seem seems appear appears inside within around about against near left right '
    'feet foot each every both none just even still very much many long ago away back down could would should '
    'will shall must does doing done been being were your yours open opens opened opening close closes closed '
    'beyond behind step steps turn turns hold holds keep keeps take takes find finds found stand stands sits lies '
    'lying move moves another again first second third enough rather instead').split()}
PUBLIC_NUMBER = re.compile(r'\b(?:DC|difficulty class|save dc)\s*\d+|\bdifficulty class\b|[+-]\d+\s*(?:to hit|bonus)\b|'
                           r'\b\d+\s*hit points\b|\bAC\s*\d+\b|\barmor class\s*\d+', re.I)
DC_TEXT = re.compile(r'\bDC\s*(\d{1,2})\b', re.I)
GP_TEXT = re.compile(r'\b(\d[\d,]*)\s*gp\b', re.I)
HP_TEXT = re.compile(r'\b(\d{1,4})\s*hit points\b', re.I)
DICE_TEXT = re.compile(r'\b(\d+d\d+(?:\s*[+-]\s*\d+)?)\b', re.I)
ITEM_TEXT = re.compile(r"(\+\d (?!to\b)[a-z]+|\b(?:sphere|wand|rod|staff|ring|cloak|amulet|potion|scroll|bag|robe|"
                       r"boots|gloves|bracers|helm|necklace|periapt|brooch|horn|figurine|carpet|manual|tome|belt|cape|"
                       r"circlet|decanter|deck|orb|stone|pearl|elixir|oil|dust|talisman) of (?:the )?[a-z]+)", re.I)


# Creature names from the SRD list, minus the ones that are everyday words (a guard, a shadow).
EVERYDAY = {'guard', 'shadow', 'scout', 'spy', 'mage', 'priest', 'commoner', 'thug', 'rat', 'bat', 'wolf', 'ghost',
            'imp', 'acolyte', 'veteran', 'bandit', 'cultist', 'noble', 'knight', 'zombie', 'skeleton', 'mimic'}
CREATURE_WORDS = sorted((n for n in srd_creatures.CREATURES if n not in EVERYDAY), key=lambda n: -len(n))


ALIVE_HINT = re.compile(r"\b(?:something|someone|a shape|shapes|a figure|figures|movement)\b[^.;]{0,40}?\b(?:skitter|click|"
                        r"shift|stir|slither|scurr|rustl|moves|moving|breath|waits|watch|crawl|creep|twitch|coil|"
                        r"lurk|slink)\w*|\bmany-legged\b", re.I)


def _strings(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f'{path}.{k}' if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f'{path}.{i}')


def _numbers(value):
    if type(value) is int:
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _numbers(v)


def _dict(value):
    return value if isinstance(value, dict) else {}


def public_texts(room):
    """(where, text, owner fact or None) for every field the player can see or hear."""
    out = []
    facts, areas, exits, actors = (_dict(room.get(k)) for k in ('facts', 'areas', 'exits', 'actors'))
    for key, fact in facts.items():
        if not isinstance(fact, dict):
            continue
        if fact.get('visible'):
            out.append((f'fact {key} text', fact.get('text'), None))
        handling = _dict(fact.get('handling'))
        for field in ('look', 'move', 'enter', 'handle', 'take', 'open', 'search'):
            if isinstance(handling.get(field), str):
                out.append((f'fact {key} handling.{field}', handling[field], key))
    for key, item in areas.items():
        if not isinstance(item, dict):
            continue
        for field in ('name', 'called', 'arrival'):
            out.append((f'area {key} {field}', item.get(field), None))
        tease = _dict(item.get('tease'))
        out.append((f'area {key} tease', tease.get('text'), None))
        out += [(f'area {key} tease heard', h.get('sound'), None) for h in tease.get('heard') or () if isinstance(h, dict)]
    for key, edge in exits.items():
        edge = _dict(edge)
        if edge.get('secret'):
            continue  # a secret way is shown only once found: its words are the finding
        out.append((f'exit {key} name', edge.get('name'), None))
        out += [(f'exit {key} label', t, None) for t in _dict(edge.get('labels')).values()]
        out += [(f'exit {key} go_text', t, None) for t in _dict(edge.get('go_text')).values()]
    for key, actor in actors.items():
        if isinstance(actor, dict) and actor.get('status') != 'hidden' and actor.get('visible', True):
            for field in ('name', 'description', 'appearance', 'look'):
                if isinstance(actor.get(field), str):
                    out.append((f'actor {key} {field}', actor[field], None))
    for area, story in _dict(room.get('story')).items():
        for hook in (_dict(story).get('hooks') or ()):
            if isinstance(hook, dict):
                out.append((f"story {area} hook {hook.get('id')} text", hook.get('text'), None))
    return [(w, t, o) for w, t, o in out if isinstance(t, str) and t.strip()]


def dm_texts(room):
    """Where the room keeps what the player does not see: hidden facts, every actor's motive,
    knowledge and secrets, claims, triggers, traps, the story's private side."""
    out = []
    for key, fact in _dict(room.get('facts')).items():
        if isinstance(fact, dict) and not fact.get('visible'):
            out.append(str(fact.get('text', '')))
    for actor in _dict(room.get('actors')).values():
        if isinstance(actor, dict):
            out += [s for _, s in _strings({k: actor.get(k) for k in ('motive', 'knowledge', 'secrets', 'name', 'truth')})]
    for block in ('claims', 'triggers', 'traps', 'attitudes'):
        out += [s for _, s in _strings(room.get(block))]
    for story in _dict(room.get('story')).values():
        out += [s for _, s in _strings({k: _dict(story).get(k) for k in ('about', 'purposes', 'endings')})]
    return ' '.join(out)


def _kind(actor):
    block = _dict(actor.get('stat_block'))
    return norm(block.get('srd') or actor.get('kind') or actor.get('name') or '')


def _matches(kind, actor):
    want = {stem(w) for w in norm(kind).split()}
    have = {stem(w) for w in (_kind(actor) + ' ' + norm(actor.get('name', ''))).split()}
    return bool(want) and want <= have


def check(room, manifest, context=None):
    """(errors, warnings): every difference between the room and its source manifest."""
    context = context or {}
    errors, warns = [], []
    sentences = {s['id']: s for s in manifest.get('sentences') or ()}
    slice_text = norm(' '.join(s['text'] for s in sentences.values()) + ' ' + ' '.join(context.get('intro') or ()))
    actors = {k: a for k, a in _dict(room.get('actors')).items() if isinstance(a, dict)}
    facts = {k: f for k, f in _dict(room.get('facts')).items() if isinstance(f, dict)}
    numbers = {k: set(v) for k, v in (manifest.get('numbers') or {}).items()}
    everything = ' '.join(s for _, s in _strings(room))
    every_stem = stems(everything, 3)
    dm_stem = stems(dm_texts(room), 3)
    all_numbers = set(_numbers(room)) | {int(n) for n in re.findall(r'\b\d+\b', everything)}

    # -- source_claims: quotes from the source, tying ambiguous entities to room entries
    claims = room.get('source_claims') or []
    if not isinstance(claims, list):
        errors.append('source_claims must be a list of {quote, actors?, facts?, note?}')
        claims = []
    claimed = {}
    for i, claim in enumerate(claims):
        if not isinstance(claim, dict) or not isinstance(claim.get('quote'), str) or len(claim['quote'].strip()) < 12:
            errors.append(f'source_claims {i}: needs a quote (12+ characters copied from the source)')
            continue
        quote = norm(claim['quote']).strip(' ."')
        if quote not in slice_text:
            errors.append(f'source_claims {i}: quote "{claim["quote"][:80]}" is not in the source text for this area')
            continue
        for key in claim.get('actors') or ():
            if key not in actors:
                errors.append(f'source_claims {i}: unknown actor {key!r}')
            else:
                claimed.setdefault(key, []).append(quote)
        for key in claim.get('facts') or ():
            if key not in facts:
                errors.append(f'source_claims {i}: unknown fact {key!r}')

    # -- creatures and named NPCs
    assigned = {}
    entries = list(manifest.get('creatures') or ())
    npcs = list(manifest.get('npcs') or ())
    for npc in npcs:
        first = norm(npc['name']).split()[0]
        who = [k for k, a in actors.items() if first in norm(' '.join(s for _, s in _strings(
            {f: a.get(f) for f in ('name', 'secrets', 'knowledge', 'motive', 'truth')})))]
        if not who:
            errors.append(f'missing named NPC {npc["name"]} ("{npc["quote"][:90]}"): every person the source names is an actor')
        for k in who[:1]:
            assigned[k] = f'npc {npc["name"]}'
            hidden = [e for e in entries if e.get('npc') == npc['name']]
            if hidden and all(e.get('hidden') for e in hidden) and actors[k].get('status') != 'hidden' \
                    and not any(sentences.get(e['sentence'], {}).get('secret') is False for e in hidden):
                pass  # a named NPC in disguise is present; the disguise is a dm-side truth, not a hidden status
    by_claim = {}
    for entry in entries:
        if entry.get('npc'):
            continue
        text = norm(sentences.get(entry['sentence'], {}).get('text', entry.get('quote', '')))
        owners = [k for k, quotes in claimed.items() if any(q in text or text in q for q in quotes)]
        if owners:
            by_claim[id(entry)] = owners
    open_entries = [e for e in entries if not e.get('npc') and id(e) not in by_claim]
    for entry in entries:
        owners = by_claim.get(id(entry))
        if owners is None:
            continue
        for k in owners:
            assigned[k] = f'source claim for {entry["kind"]}'
        if entry.get('count') is not None and len(owners) != entry['count']:
            errors.append(f'source_claims for "{entry["quote"][:70]}": the source has {entry["count"]} {entry["kind"]}, '
                          f'the claim names {len(owners)}')
        _visibility(entry, owners, actors, errors)
    _responders(facts, open_entries)
    kinds = []
    for entry in open_entries:
        if entry['kind'] not in kinds:
            kinds.append(entry['kind'])
    for kind in kinds:
        group = [e for e in open_entries if e['kind'] == kind]
        exact = all(e.get('count') is not None for e in group)
        need = sum(e.get('count') or 1 for e in group)
        pool = [k for k, a in actors.items() if k not in assigned and _matches(kind, a)]
        quote = group[0]['quote'][:90]
        if len(pool) < need or (exact and len(pool) > need):
            errors.append(f'the source has {"" if exact else "at least "}{need} {kind} ("{quote}"); the room has '
                          f'{len(pool)}. Write each one as an actor (or settle the count with source_claims)')
        for k in pool[:need] if exact else pool:
            assigned[k] = kind
        for e in group:
            _visibility(e, pool[:need] if exact else pool, actors, errors)
    allowed = [e['kind'] for e in manifest.get('context_creatures') or ()]
    for key, actor in actors.items():
        if key in assigned or key in claimed:
            continue
        if any(_matches(kind, actor) for kind in allowed):
            continue
        errors.append(f'actor {key} ({_kind(actor) or "unnamed"}) is not in the source for this area: no invented '
                      'creatures (quote its line in source_claims if the manifest missed it)')

    # -- stat blocks: SRD first, the source's own numbers, else needs_stats
    woken = {a for t in (room.get('triggers') or ()) if isinstance(t, dict) and t.get('starts_combat', True)
             for a in (t.get('actors') or ())}
    for key, actor in actors.items():
        block = actor.get('stat_block')
        if block is None:
            if actor.get('needs_stats'):
                warns.append(f'actor {key} needs_stats: no SRD block and the source gives none; it cannot fight on-engine')
                if key in woken:
                    errors.append(f'actor {key} needs_stats but a trigger starts a fight with it: set starts_combat false')
            continue
        if not isinstance(block, dict):
            errors.append(f'actor {key} stat_block must be {{"srd": name}} or the source\'s own numbers')
            continue
        if 'srd' in block:
            if srd_creatures.stat_block({'srd': block['srd']}) is None:
                errors.append(f'actor {key} stat_block srd {block["srd"]!r} is not in runtime/srd_creatures.py: '
                              'use a listed name, the source\'s own stat block, or needs_stats (never invent one)')
            for field, pool in (('hp', 'hp'), ('ac', 'ac')):
                if field in block and block[field] not in numbers.get(pool, set()):
                    errors.append(f'actor {key} stat_block {field} {block[field]} is not a number the source states')
            extra = set(block) - {'srd', 'hp', 'ac'}
            if extra:
                errors.append(f'actor {key} stat_block: an SRD reference may only restate hp/ac from the source '
                              f'(not {sorted(extra)})')
        else:
            bad = []
            if block.get('hp') not in numbers.get('hp', set()):
                bad.append(f'hp {block.get("hp")}')
            if block.get('ac') not in numbers.get('ac', set()):
                bad.append(f'ac {block.get("ac")}')
            for attack in block.get('attacks') or ():
                if isinstance(attack, dict) and attack.get('to_hit') not in numbers.get('to_hit', set()):
                    bad.append(f'to_hit {attack.get("to_hit")}')
            if bad:
                errors.append(f'actor {key} inline stat_block numbers the source does not state ({", ".join(bad)}): '
                              'use {"srd": ...} (runtime/srd_creatures.py), or "needs_stats": true; never invent')

    # -- every secret, treasure and hazard sentence is carried
    others = {sid: set().union(*([stems(o['text'], 4) for oid, o in sentences.items() if oid != sid] or [set()]))
              for sid in sentences}
    for sid in manifest.get('must_carry') or ():
        s = sentences.get(sid)
        if not s:
            continue
        mine = stems(s['text'], 4) - GENERIC
        distinct = mine - others[sid]
        if len(distinct) < 2:
            distinct = mine
        pool = dm_stem if s.get('deception') else every_stem
        have = distinct & pool
        need = min(2, len(distinct))
        if len(have) < need:
            where = 'dm-side (hidden facts, actor secrets, claims)' if s.get('deception') else 'the room'
            errors.append(f'not carried in {where}: "{s["text"][:110]}" (none of: {", ".join(sorted(distinct)[:6])})')
        for kind, pattern in (('dc', DC_TEXT), ('gp', GP_TEXT), ('hp', HP_TEXT)):
            for n in pattern.findall(s['text']):
                n = int(str(n).replace(',', ''))
                if n and n not in all_numbers:
                    errors.append(f'the source states {kind} {n} ("{s["text"][:80]}") and the room drops it')
    for item in manifest.get('items') or ():
        words = {stem(w) for w in norm(item['name']).split() if len(w) >= 4} - GENERIC
        head = stem(norm(item['name']).split()[-1]) if norm(item['name']).split() else None
        if words and not (head in every_stem if head in words else words & every_stem):
            errors.append(f'missing item {item["name"]!r} ("{item["quote"][:80]}")')

    # -- numbers the source does not state
    for path, text in _strings(room):
        if path.startswith('source_claims'):
            continue
        for kind, pattern in (('dc', DC_TEXT), ('gp', GP_TEXT), ('hp', HP_TEXT)):
            for n in pattern.findall(text):
                n = int(str(n).replace(',', ''))
                if n not in numbers.get(kind, set()):
                    errors.append(f'{path}: {kind} {n} is not a number the source states')
        for dice in DICE_TEXT.findall(text):
            if re.sub(r'\s+', '', dice).lower() not in numbers.get('dice', set()):
                errors.append(f'{path}: dice {dice} are not the source\'s')
        for found in ITEM_TEXT.findall(text):
            if norm(found) not in slice_text:
                errors.append(f'{path}: {found!r} is not in the source (no invented items or treasure)')
    for key, claim in _dict(room.get('claims')).items():
        if isinstance(claim, dict) and type(claim.get('dc')) is int and claim['dc'] not in numbers.get('dc', set()):
            errors.append(f'claims {key}: DC {claim["dc"]} is not a DC the source states '
                          f'({", ".join(map(str, sorted(numbers.get("dc", ())))) or "it states none"}); omit dc for '
                          "the engine's default")

    # -- scripted conditions and hazards
    traps = [t for t in (room.get('traps') or ()) if isinstance(t, dict)]
    if manifest.get('scripted') and not (room.get('triggers') or traps):
        errors.append(f'the source sets something off ("{manifest["scripted"][0]["quote"]}") but the room declares no '
                      'triggers or traps: write it, do not leave Kit to improvise it')
    kinds_set = {next(iter(_dict(t.get('on'))), None) for t in (room.get('triggers') or ()) if isinstance(t, dict)} | \
        {next(iter(_dict(t.get('on'))), None) for t in traps}
    for item in manifest.get('scripted') or ():
        want = item.get('on')
        allowed_on = {'disturb': {'disturb', 'open'}, 'enter': {'enter', 'step'}}.get(want)
        if allowed_on and (room.get('triggers') or traps) and not kinds_set & allowed_on:
            errors.append(f'the source sets it off when {"handled" if want == "disturb" else "entered"} '
                          f'("{item["quote"]}"): a trigger or trap "on": {{"{want}": ...}}, not another condition')
    trap_dice = [{norm(d.get('dice', '')).replace(' ', '') for d in (_dict(t.get('effect')).get('damage') or ())
                  if isinstance(d, dict)} for t in traps]
    for hazard in manifest.get('hazards') or ():
        want = {d['dice'] for d in hazard['damage']}
        if not any(want <= dice for dice in trap_dice):
            errors.append(f'the source has a hazard with {", ".join(sorted(want))} damage ("{hazard["quote"][:90]}"): '
                          'declare it in traps (runtime/kit_traps.py) with the source\'s dice and DCs')

    # -- creatures named in the room's text that this area does not have (another area's
    # monster written in as scenery)
    for where, text in _strings({k: room.get(k) for k in ('facts', 'areas', 'exits', 'story', 'triggers', 'traps')}):
        for name in CREATURE_WORDS:
            head = name.split()[-1]
            if re.search(rf"\b{re.escape(name)}(?:e?s)?\b", norm(text)) and \
                    not re.search(rf"\b{re.escape(head)}", slice_text):
                errors.append(f'{where}: names a {name}, which is not in the source for this area')
                break

    # -- ways out
    errors += _way_problems(room, manifest, context)

    # -- the leak scan over every public field
    errors += leak_problems(room, manifest)
    return errors, warns


def _responders(facts, entries):
    """Alarm responders answer from elsewhere: they stand for the creatures the source sends."""
    for fact in facts.values():
        for responder in (_dict(fact.get('alarm')).get('responders') or ()):
            if not isinstance(responder, dict):
                continue
            who = {'name': responder.get('who', ''), 'stat_block': responder.get('stat_block')}
            for entry in [e for e in entries if _matches(e['kind'], who)]:
                if entry.get('count') in (None, responder.get('count')):
                    entries.remove(entry)


def _visibility(entry, keys, actors, errors):
    if entry.get('hidden') is None:
        return
    for k in keys:
        hidden = actors[k].get('status') == 'hidden'
        if entry['hidden'] and not hidden:
            errors.append(f'actor {k}: the source keeps it out of sight ("{entry["quote"][:80]}"); make it '
                          '"status": "hidden", "visible": false until its trigger fires')
        elif not entry['hidden'] and hidden:
            errors.append(f'actor {k}: the source has it in plain view ("{entry["quote"][:80]}"); it is not hidden')


def _way_problems(room, manifest, context):
    errors = []
    here = manifest.get('area')
    areas = {k: a for k, a in _dict(room.get('areas')).items() if isinstance(a, dict)}
    ways = {e['area']: e for e in manifest.get('exits') or ()}
    vocabulary = set(manifest.get('vocabulary') or ())
    bound = bool(context.get('bound'))
    linked = set()
    for key, item in areas.items():
        src = item.get('source_area')
        if src in (None, here) or src == context.get('parent'):
            continue
        linked.add(src)
        way = ways.get(src)
        if way and not way.get('way') and not way.get('sibling') and not bound:
            errors.append(f'area {key} stands for {src}, which the source mentions but not as a way from here: '
                          'no invented exits')
    for key, edge in _dict(room.get('exits')).items():
        edge = _dict(edge)
        ends = [_dict(areas.get(a)).get('source_area') for a in edge.get('areas') or ()]
        if any(e not in (None, here) for e in ends) and not bound and edge.get('uncertain') is not True:
            errors.append(f'exit {key} joins another keyed area with no geometry ledger: mark it "uncertain": true')
        secret_to = any(_dict(ways.get(e)).get('secret') for e in ends)
        if secret_to and not edge.get('secret'):
            errors.append(f'exit {key}: the source makes this way secret; mark it "secret": true')
        if edge.get('secret') and not (manifest.get('secret_ways') or secret_to):
            errors.append(f'exit {key} is secret but the source names no secret door or passage: no invented exits')
    for src, way in ways.items():
        if way.get('way') and src not in linked:
            errors.append(f'the source names a way to area {src} ({way.get("title", "")}); give it an outside area '
                          f'with "room_link": {{"author": {{"level", "area": "{src}"}}}} (exit "uncertain": true)')
    for key, item in areas.items():
        for field in ('name', 'called'):
            invented = _new_words(item.get(field), vocabulary)
            if invented:
                errors.append(f'area {key} {field} names a place the source does not ({", ".join(invented)})')
    for key, edge in _dict(room.get('exits')).items():
        invented = _new_words(_dict(edge).get('name'), vocabulary)
        if invented:
            errors.append(f'exit {key} name names a way the source does not ({", ".join(invented)})')
    return errors


def _new_words(text, vocabulary):
    if not isinstance(text, str):
        return []
    return sorted(w for w in stems(text, 4) - POSITIONAL - GENERIC if w not in vocabulary)


def leak_problems(room, manifest):
    """Hidden actors' names, words only the source's secrets use, and DC or bonus numbers, in
    any player-visible field."""
    errors = []
    sentences = manifest.get('sentences') or ()
    public_vocab = set().union(*([stems(s['text'], 4) for s in sentences if not s.get('private', s.get('secret'))]
                                 or [set()]))
    # A named NPC the PC meets in person may give her name; who she really is stays hidden.
    public_vocab |= set().union(*([stems(n['name'], 4) for n in manifest.get('npcs') or ()] or [set()]))
    # Plain place words (tunnel, north, door) are never a tell, even where every sentence is secret.
    secret_vocab = set().union(*([stems(s['text'], 4) for s in sentences if s.get('secret')] or [set()])) - POSITIONAL
    actors = {k: a for k, a in _dict(room.get('actors')).items() if isinstance(a, dict)}
    facts = {k: f for k, f in _dict(room.get('facts')).items() if isinstance(f, dict)}
    tells = {}
    for key, actor in actors.items():
        if actor.get('status') != 'hidden':
            continue
        words = (stems(key.replace('_', ' '), 4) | stems(actor.get('name'), 4) | stems(_kind(actor), 4)) - GENERIC
        heads = {stem(norm(t).split()[-1]) for t in (_kind(actor), actor.get('name') or '') if norm(t)}
        # A modifier the source uses openly ('glistening black stone') is not a tell; the noun is.
        tells[f'hidden actor {key}'] = {w for w in words if w in heads or w not in public_vocab}
    holders = {}
    for key, fact in facts.items():
        holds = _dict(fact.get('handling')).get('holds')
        if holds:
            holders.setdefault(holds, set()).add(key)
    for claim in _dict(room.get('claims')).values():
        if isinstance(claim, dict) and claim.get('fact'):
            holders.setdefault(claim['fact'], set()).update(claim.get('roots') or ())
    for key, fact in facts.items():
        if fact.get('visible'):
            continue
        words = (stems(fact.get('text'), 4) & secret_vocab) - public_vocab - GENERIC
        if words:
            tells[f'hidden fact {key}'] = (words, holders.get(key, set()))
    for key, actor in actors.items():
        words = (stems(' '.join(str(s) for s in actor.get('secrets') or ()), 4) & secret_vocab) - public_vocab - GENERIC
        if words:
            tells[f'actor {key} secrets'] = (words, set())
    # A tease that hints at something alive ('something many-legged skitters') where every
    # creature here is hidden gives the ambush away without naming it.
    if tells and not any(a.get('status') != 'hidden' and a.get('visible', True) for a in actors.values()):
        for key, item in _dict(room.get('areas')).items():
            tease = _dict(_dict(item).get('tease')).get('text')
            if isinstance(tease, str) and ALIVE_HINT.search(tease):
                errors.append(f'area {key} tease hints at a hidden creature ("{ALIVE_HINT.search(tease).group(0)}"): '
                              'the approach gives only what is plainly there')
    for where, text, owner in public_texts(room):
        found = stems(text, 4)
        for what, words in tells.items():
            if isinstance(words, tuple):
                words, allowed = words
                if owner in allowed:
                    continue  # the feature that holds or reveals it may describe it when handled
            leaked = sorted(found & words)
            if leaked:
                errors.append(f'{where} names {what} ({", ".join(leaked)}): it stays dm_only until play reveals it')
        if PUBLIC_NUMBER.search(text):
            errors.append(f'{where} shows a game number ("{PUBLIC_NUMBER.search(text).group(0)}"): DCs, bonuses and '
                          'hit points never reach the player')
    return errors
