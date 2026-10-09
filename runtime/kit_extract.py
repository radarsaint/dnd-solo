"""Source extractors: a keyed area's text in, a **source manifest** out (the fidelity
checklist runtime/kit_fidelity.py diffs an authored room against).

The manifest shape is source-agnostic: a keyed area from any author (a published book's
keyed text, or Kit's own design doc later) becomes the same dict, and the checker reads only
that dict. Everything that knows how a particular source is *written* (its paragraph labels,
its damage and DC notation, its parentheticals, how it names other areas) lives in an
extractor here, never in the checker. Extractors are pluggable: ``EXTRACTORS[name](area)``.

    {"version": "source-manifest/1", "area": "<key>", "extractor": "<name>",
     "sentences": [{"id": "s1", "text", "secret": bool, "private": bool, "kind": "prose|treasure|hazard"}],
                   # secret: the source marks it DM-only (it must be carried in dm_only);
                   # private: about something only secret sentences mention (not public vocabulary)
     "creatures": [{"kind", "count": int|null, "hidden": bool|null, "sentence", "quote"}],
     "context_creatures": [... the same, from the parent's intro: allowed, not required],
     "npcs": [{"name", "kind"?, "sentence", "quote"}],
     "items": [{"name", "gp"?, "sentence", "quote"}],
     "hazards": [{"sentence", "quote", "damage": [{"dice", "type"}], "dc": [n], "to_hit": [n]}],
     "scripted": [{"sentence", "quote", "on"?}],   # something sets creatures off: needs a trigger
                                                   # (on: "disturb" | "enter" when the wording says)
     "numbers": {"dc": [], "hp": [], "gp": [], "dice": [], "to_hit": []},
     "must_carry": ["s3", ...],                    # secret, treasure and hazard sentences
     "exits": [{"area", "title", "way": bool, "secret": bool, "quote"}],
     "secret_ways": bool,                          # the source names a secret door or passage
     "vocabulary": [stems]}                        # the slice's own words (place names come from it)

``design_doc`` is the identity extractor: a manifest Kit wrote herself (same shape) is
checked for shape and passed through.
"""
import re

from . import kit_source, srd_creatures

VERSION = 'source-manifest/1'


# ---------------------------------------------------------------- shared text helpers

def norm(text):
    """Lowercase, curly quotes and dashes flattened, whitespace collapsed (for quote checks)."""
    text = str(text or '').replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    text = re.sub(r'[\u2013\u2014]', '-', text)
    return re.sub(r'\s+', ' ', text).strip().casefold()


def stem(word):
    w = word.casefold().replace("'", '')
    for tail, new in (('ies', 'y'), ('ves', 'f'), ('sses', 'ss'), ('ches', 'ch'), ('shes', 'sh'), ('xes', 'x')):
        if w.endswith(tail) and len(w) > len(tail) + 2:
            return w[:-len(tail)] + new
    if w.endswith('s') and not w.endswith('ss') and len(w) > 4 and w[-2] != 'u':
        w = w[:-1]  # the plural first, so 'puddings' and 'pudding' share a stem
    if w.endswith('ing') and len(w) > 5:
        w = w[:-3]
    elif w.endswith('ed') and len(w) > 4:
        w = w[:-2]
    elif w.endswith('s') and not w.endswith('ss') and len(w) > 3:
        w = w[:-1]
    return w.rstrip('e') if len(w) > 4 else w


def stems(text, minimum=3):
    return {stem(w) for w in re.findall(r"[a-z][a-z'-]*", norm(text)) if len(w) >= minimum}


# ---------------------------------------------------------------- the keyed-prose extractor

SENTENCE = re.compile(r'(?<=[.!?)\u201d"])\s+(?=[(\u201c"A-Z0-9])')
LABEL = re.compile(r"^(?:([A-Z][\w'\u2019-]*(?: [A-Za-z][\w'\u2019-]*){0,3})\.|(Treasure|Traps?|Hazards?|Tactics|Developments?))\s+(?=[A-Z(])")
SECRET = re.compile(
    r"\b(lurks?|lurking|resides?|hidden|hides?|conceal(?:s|ed|ing)?|secret(?:ly)?|invisible|in fact|actually|"
    r"lies? (?:about|to)|another lie|lying|lied|illusory|illusion|stasis|doubles as|detect magic|emerges?|your choice|disguised?|"
    r"shapechanged|true form|unbeknownst|not visible|impersonat\w*|pretends?|claims? that|trap(?:ped|s)?|"
    r"in reality|is really|really is|spots? the|realize|out of sight|unseen|steps? out|steps? forth|"
    r"in (?:her|his|its|their) [\w-]+(?: [\w-]+)? form)\b", re.I)
COVER = re.compile(r"\b(claims? that|claims? to|pretends? to|insists? that|poses? as|passes? (?:herself|himself|"
                   r"itself|themselves) off as)\b", re.I)
DECEPTION = re.compile(r"\b(lies? (?:about|to)|another lie|lying|lied|in fact|actually|true form|true nature|"
                       r"in (?:her|his|its|their) [\w-]+(?: [\w-]+)? form|"
                       r"shapechanged|disguised?|illusory|pretends?|claims? that|impersonat\w*|in reality|is really|"
                       r"unbeknownst)\b", re.I)
DAMAGE = re.compile(r'\b(\d+) \((\d+d\d+(?:\s*[+-]\s*\d+)?)\) (\w+) damage', re.I)
DC = re.compile(r'\bDC (\d{1,2})\b')
HP = re.compile(r'\b(\d{1,4}) hit points\b', re.I)
GP = re.compile(r'\b(\d[\d,]*) gp\b', re.I)
DICE = re.compile(r'\b(\d+d\d+(?:\s*[+-]\s*\d+)?)\b')
TO_HIT = re.compile(r'\+(\d{1,2}) to hit\b', re.I)
SCRIPTED = re.compile(
    r"\b(if (?:it|the \w+(?: \w+)?|anyone|a character|any creature) (?:is |are )?(?:disturbed|touched|harmed|opened|"
    r"moved|approached|cornered|attacked)|(?:emerge|burst|spring|lunge)s? (?:out )?and attack|attacks? (?:all|anyone|"
    r"any creature|interlopers|intruders|those) (?:who|that|on sight)|attack (?:on sight|immediately)|"
    r"to attack anyone|ambush|stasis ends|animate and)", re.I)
COUNTS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
          'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'a pair of': 2, 'several': None, 'some': None,
          'a few': None, 'many': None, 'a dozen': 12, 'dozens of': None}
SCENERY = re.compile(r"\b(petrified|statues?|lifelike|depict\w*|carved|reliefs?|bas-relief|toppled|corpses?|carcass\w*|"
                     r"killed|slain|slew|dead|desiccated|remains|bones|skulls?|impaled|likeness|murals?|paintings?|"
                     r"images?|figurines?|resembles?|molded|mosaic|skeletal)\b", re.I)
LIVING = re.compile(r"\b(resides?|lurks?|attacks?|emerges?|hides?|scours?|sleep(?:s|ing)?|waits?|waiting|guards?|"
                    r"stationed|lives?|nests?|hunts?|patrols?|coats|serves?|flees?|watch(?:es)?|uses)\b", re.I)
EXTRA_CREATURES = ('basilisk', 'sahuagin', 'carrion crawler', 'kobold', 'grick', 'beholder', 'wyvern', 'centipede',
                   'rat', 'ooze', 'pudding', 'jelly', 'spider', 'snake', 'serpent', 'wolf', 'orc', 'gnoll', 'troll',
                   'ogre', 'duergar', 'drow', 'mind flayer', 'gnome', 'kenku', 'imp', 'quasit', 'ghost', 'specter',
                   'wraith', 'wight', 'mummy', 'zombie', 'skeleton', 'ghoul', 'ghast', 'wererat', 'werewolf', 'goblin',
                   'hobgoblin', 'bugbear', 'stirge', 'shadow', 'gargoyle', 'mimic', 'cultist', 'bandit', 'thug',
                   'guard', 'mage', 'priest', 'dwarf', 'elf', 'halfling', 'human', 'half-orc', 'nothic',
                   'intellect devourer', 'flumph', 'myconid', 'roper', 'piercer', 'cloaker', 'darkmantle',
                   'rust monster', 'otyugh', 'hound', 'bat', 'frog', 'toad', 'lizard', 'crocodile', 'mephit',
                   'homunculus', 'golem')
MAGIC_ITEM = re.compile(
    r"(\+\d (?!to\b)\w+|\b(?:driftglobe|bag of holding|immovable rod|spell scroll|deck of [a-z]+|ioun stone|"
    r"(?:sphere|wand|rod|staff|ring|cloak|amulet|potion|scroll|bag|robe|boots|gloves|bracers|helm|necklace|periapt|"
    r"brooch|horn|figurine|carpet|manual|tome|belt|cape|circlet|decanter|gem|orb|stone|pearl|elixir|oil|dust|"
    r"wings|eyes|goggles|lantern|mantle|medallion|mirror|pipes|talisman|trident|sword|axe|mace|bow|dagger) "
    r"of (?:the )?[a-z]+(?: [a-z]+)?))\b", re.I)
WAY_WORDS = re.compile(r"\b(tunnels?|passages?|doors?|doorways?|corridors?|halls?|hallway|stairs?|stairways?|steps|"
                       r"leads?|leading|connect\w*|opens?|into|toward|towards|archway|arch|ladder|shaft|exits?|"
                       r"west|east|north|south|beyond|rejoin|flees?|retreats?|runs? to|heads? to|returns? to|"
                       r"investigate|comes? from|reach(?:es)?)\b", re.I)
SECRET_WAY = re.compile(r'\b(secret (?:door|passage|tunnel|panel|stair\w*)|hidden (?:door|passage|panel)|'
                        r'concealed (?:door|passage))', re.I)


GENERIC_STEMS = {stem(w) for w in ('this', 'that', 'with', 'from', 'into', 'their', 'there', 'they', 'room', 'area',
                                   'floor', 'wall', 'walls', 'door', 'feet', 'foot', 'each', 'also', 'once', 'other',
                                   'have', 'here', 'when', 'which', 'while', 'these', 'those', 'them', 'than', 'what',
                                   'where', 'some', 'only', 'more', 'most', 'like', 'over', 'under', 'onto', 'upon',
                                   'until', 'after', 'before', 'creature', 'character', 'characters', 'anyone')}


def creature_names():
    names = set(srd_creatures.CREATURES) | set(EXTRA_CREATURES)
    return sorted(names, key=lambda n: -len(n))


def _plural(name):
    last = name.split()[-1]
    forms = {last, last + 's', last + 'es'}
    if last.endswith('y'):
        forms.add(last[:-1] + 'ies')
    if last.endswith('f'):
        forms.add(last[:-1] + 'ves')
    if last == 'dwarf':
        forms.add('dwarves')
    if last.endswith('man'):
        forms.add(last[:-3] + 'men')
    head = ' '.join(name.split()[:-1])
    return [f'{head} {f}'.strip() for f in forms]


HEADING_LABELS = ('treasure', 'trap', 'traps', 'hazard', 'hazards')


def _sentences(lines):
    out, carried = [], ''
    for line in lines:
        line = ' '.join(str(line).split())
        if not line:
            continue
        if line.casefold().rstrip('.') in HEADING_LABELS:
            carried = line.casefold().rstrip('.')  # a heading on its own line labels the paragraph after it
            continue
        label = LABEL.match(line)
        tag = (label.group(1) or label.group(2)).casefold() if label else carried
        tag = 'treasure' if tag.startswith('treasure') else tag
        carried = ''
        body = line[label.end():] if label else line
        for text in SENTENCE.split(body):
            if text.strip():
                out.append({'text': text.strip(), 'label': tag})
    return out


def creatures_in(sentences, prefix='s'):
    """Creatures a passage introduces with a count ('two giant rats', 'a wererat'), or by
    'uses the X statistics'; none from scenery sentences (statues, corpses, carvings)."""
    found = []
    names = creature_names()
    for index, item in enumerate(sentences):
        text = norm(item['text'])
        scenery = bool(SCENERY.search(text)) and not LIVING.search(text)
        sid = item.get('id') or f'{prefix}{index + 1}'
        taken = []
        stats = re.search(r"\buses? (?:the|its) ([a-z' -]+?) statistics\b", text)
        if stats:
            kind = stats.group(1).strip()
            found.append({'kind': kind, 'count': None, 'hidden': None, 'sentence': sid, 'quote': item['text'][:160]})
        if scenery:
            continue
        for name in names:
            for form in _plural(name):
                for m in re.finditer(rf"(?<![\w-]){re.escape(form)}(?![\w-])", text):
                    if any(a <= m.start() < b or a < m.end() <= b for a, b in taken):
                        continue
                    before = text[:m.start()].split()
                    after = text[m.end():m.end() + 2]
                    if after.startswith("'s") or re.search(r'\bby\s+(?:[\w-]+\s+){0,3}$', text[:m.start()]):
                        continue  # a possessive ('the crawler's tentacles') or an agent ('bitten by a snake')
                    count, ok = None, False
                    for span in range(0, 4):  # up to three adjectives between the count and the noun
                        for words in (3, 2, 1):
                            if len(before) >= span + words:
                                phrase = ' '.join(before[len(before) - span - words:len(before) - span])
                                between = before[len(before) - span:] if span else []
                                if phrase in COUNTS and 'of' not in between and phrase not in ('one',) + () or \
                                        phrase == 'one' and not between and 'of' not in between:
                                    count, ok = COUNTS[phrase], True
                                    break
                        if ok:
                            break
                    if not ok:
                        continue
                    taken.append((m.start(), m.end()))
                    found.append({'kind': name, 'count': count, 'hidden': bool(item.get('secret')),
                                  'sentence': sid, 'quote': item['text'][:160]})
    return found


def _numbers(text):
    return {'dc': sorted({int(n) for n in DC.findall(text)}), 'hp': sorted({int(n) for n in HP.findall(text)}),
            'gp': sorted({int(n.replace(',', '')) for n in GP.findall(text)}),
            'dice': sorted({re.sub(r'\s+', '', d).lower() for d in DICE.findall(text)}),
            'to_hit': sorted({int(n) for n in TO_HIT.findall(text)}),
            'ac': sorted({int(n) for n in re.findall(r'\b(?:Armor Class|AC) (\d{1,2})\b', text)})}


def keyed_prose(area):
    """Published-adventure keyed prose: paragraph labels ('Treasure.'), damage as
    '10 (3d6) bludgeoning damage', DCs as 'DC 15 Wisdom (Perception)', DM-only asides in
    parentheses, other areas named as 'area 17b'. ``area``: {key, title, lines, intro?,
    neighbours: [{area, title, quotes, back?, sibling?}]}."""
    raw = _sentences(area['lines'])
    for item in raw:
        text = item['text']
        # Treasure is carried, but it is not a secret by being treasure: a crown hanging from a
        # statue is in plain view; one under the rubble says so.
        item['secret'] = bool(text.startswith('(') or SECRET.search(text))
        item['deception'] = bool(DECEPTION.search(text))
        item['kind'] = 'treasure' if item['label'] == 'treasure' else ('hazard' if DAMAGE.search(text) else 'prose')
        if item['kind'] == 'hazard':
            item['secret'] = True
    # Two passes of propagation: a sentence about something only the secret sentences mention
    # (the goblin at the bottom of the hidden pit) is secret too.
    names = {stem(w) for n in creature_names() for w in n.split()}
    for item in raw:
        # A cover story ("she claims that ...") is carried dm-side as a lie, but its words are
        # what the liar says aloud: public vocabulary, not a tell.
        item['private'] = item['secret'] and not COVER.search(item['text'])
    # Only a thing the secret sentences introduce first: an area's opening describes what it
    # names, even when a later secret sentence says more about it.
    for _ in range(2):
        for i, item in enumerate(raw):
            if item['private'] or COVER.search(item['text']):
                continue
            secret = set().union(*([stems(s['text'], 4) for s in raw[:i] if s['private']] or [set()]))
            others = set().union(*([stems(o['text'], 4) for o in raw if not o['private'] and o is not item] or [set()]))
            if (stems(item['text'], 4) & secret) - others - names - GENERIC_STEMS:
                item['private'] = True
    sentences = [{'id': f's{i + 1}', 'text': s['text'], 'secret': s['secret'], 'private': s['private'],
                  **({'deception': True} if s['deception'] else {}), 'kind': s['kind']}
                 for i, s in enumerate(raw)]
    text = ' '.join(s['text'] for s in sentences)
    creatures = creatures_in(sentences)
    intro = _sentences(area.get('intro') or [])
    npcs = []
    for s in sentences:
        for m in re.finditer(r"\bnamed ((?:[A-Z][\w'\u2019-]+)(?: [A-Z][\w'\u2019-]+){0,2})", s['text']):
            before = norm(s['text'][:m.start()])
            kind = next((n for n in creature_names() if re.search(rf'\b{re.escape(n)}\b', before)), None)
            npcs.append({'name': m.group(1), **({'kind': kind} if kind else {}), 'sentence': s['id'],
                         'quote': s['text'][:160]})
    for c in creatures:
        said = next(x['text'] for x in sentences if x['id'] == c['sentence'])
        for n in npcs:
            if n['name'].split()[0] in said and (n.get('kind') in (None, c['kind'])):
                c['npc'] = n['name']
    items = []
    for s in sentences:
        for m in GP.finditer(s['text']):
            lead = s['text'][:m.start()].rstrip(' (')
            name = _item_name(lead)
            items.append({'name': name, 'gp': int(m.group(1).replace(',', '')), 'sentence': s['id'],
                          'quote': s['text'][:160]})
        if s['kind'] == 'treasure' or s['secret']:
            for m in MAGIC_ITEM.finditer(s['text']):
                items.append({'name': norm(m.group(1)), 'sentence': s['id'], 'quote': s['text'][:160]})
    hazards = []
    for s in sentences:
        dmg = [{'dice': re.sub(r'\s+', '', d).lower(), 'type': t.lower()} for _, d, t in DAMAGE.findall(s['text'])]
        if dmg:
            hazards.append({'sentence': s['id'], 'quote': s['text'][:200], 'damage': dmg,
                            'dc': sorted({int(n) for n in DC.findall(s['text'])}),
                            'to_hit': sorted({int(n) for n in TO_HIT.findall(s['text'])})})
    scripted = [{'sentence': s['id'], 'quote': SCRIPTED.search(s['text']).group(0),
                 **_scripted_on(SCRIPTED.search(s['text']).group(0))}
                for s in sentences if SCRIPTED.search(s['text'])]
    exits = []
    for n in area.get('neighbours') or ():
        quotes = n.get('quotes') or []
        exits.append({'area': n['area'], 'title': n.get('title', ''),
                      'way': any(_names_a_way(q, n.get('names') or [n['area'], area['key']]) for q in quotes),
                      'secret': any(bool(SECRET_WAY.search(q)) for q in quotes),
                      'quote': (quotes[0] if quotes else '')[:200],
                      **({'sibling': True} if n.get('sibling') else {}),
                      **({'back_reference': True} if n.get('back') else {})})
    own = text + ' ' + ' '.join(area.get('intro') or [])
    return {
        'version': VERSION, 'area': area['key'], 'extractor': 'keyed_prose', 'sentences': sentences,
        'creatures': creatures,
        'context_creatures': creatures_in([{'text': s['text'], 'secret': False} for s in intro], 'p'),
        'npcs': npcs, 'items': items, 'hazards': hazards, 'scripted': scripted, 'numbers': _numbers(text),
        'must_carry': [s['id'] for s in sentences if s['secret'] or s['kind'] in ('treasure', 'hazard')],
        'exits': exits, 'secret_ways': bool(SECRET_WAY.search(own)),
        'vocabulary': sorted(stems(own) | stems(area.get('title', '')) |
                             {w for n in area.get('neighbours') or () for w in stems(n.get('title', ''))}),
    }


NOT_A_WAY = re.compile(r"\b(?:found|see|described|detailed|located|kept|hidden|stored|appears?|mentioned|"
                       r"taken|brought)\s+(?:in|at|from)?\s*\(?areas?\s*$", re.I)


def _names_a_way(sentence, keys):
    """Does the sentence name the area as somewhere one goes (a door, a tunnel, flight to
    it), rather than mention it ('the mask found in area 21', 'see area 31')?"""
    for m in kit_source.AREA_REF.finditer(sentence):
        named = [m.group(1)] + re.findall(r'\d{1,3}[a-z]?', m.group(2) or '')
        if not set(named) & set(keys):
            continue
        before = sentence[:m.start()]
        if NOT_A_WAY.search(before + 'area'):
            continue
        if WAY_WORDS.search(' '.join(before.split()[-14:])):
            return True
    return False


PLACE_PREPOSITIONS = {'on', 'in', 'under', 'inside', 'beneath', 'behind', 'at', 'from', 'near', 'by', 'atop', 'below'}
ITEM_STOP = re.compile(r"\b(?:holds?|holding|contains?|containing|worth|is|are|was|lies|sits|hangs|on|in|under|with|"
                       r"inside|beneath|behind|that|which|valued)\b")


def _scripted_on(quote):
    """What sets it off, when the wording says: handling the thing ('disturb') or coming in ('enter')."""
    if re.search(r'\b(disturbed|touched|harmed|opened|moved|attacked)\b', quote, re.I):
        return {'on': 'disturb'}
    if re.search(r'\b(approached|who enter|that enter|on sight|anyone)\b', quote, re.I):
        return {'on': 'enter'}
    return {}


def _item_name(lead):
    """The thing a value belongs to: the noun phrase after the last determiner, unless that
    phrase is only where the thing sits ('a lockbox on the ledge holds 12 gp')."""
    marks = list(re.finditer(r"\b(?:a|an|the|its|one)\s+", lead, re.I))
    head = lead
    for mark in reversed(marks):
        before = lead[:mark.start()].split()
        head = lead[mark.end():]
        if not (before and before[-1].lower() in PLACE_PREPOSITIONS):
            break
    words = re.sub(r"[^\w' -]", ' ', norm(head))
    cut = ITEM_STOP.search(words)
    words = (words[:cut.start()] if cut and cut.start() > 0 else words).split()
    return ' '.join(words[:3])


def design_doc(area):
    """Kit's own design doc: the manifest is given (``area['manifest']``); checked for shape."""
    manifest = dict(area['manifest'])
    missing = [k for k in ('sentences', 'creatures', 'npcs', 'items', 'hazards', 'numbers', 'must_carry', 'exits')
               if k not in manifest]
    if missing:
        raise ValueError(f'design-doc manifest is missing {missing}')
    manifest.setdefault('version', VERSION)
    manifest.setdefault('extractor', 'design_doc')
    for key in ('context_creatures', 'scripted'):
        manifest.setdefault(key, [])
    manifest.setdefault('secret_ways', False)
    manifest.setdefault('vocabulary', sorted(set().union(*([stems(s['text']) for s in manifest['sentences']] or [set()]))))
    return manifest


EXTRACTORS = {'keyed_prose': keyed_prose, 'design_doc': design_doc}


def extract(area, extractor='keyed_prose'):
    return EXTRACTORS[extractor](area)


def naming_sentences(lines, key):
    """The sentences of ``lines`` that name area ``key`` (an extractor's neighbour quotes)."""
    return [s['text'] for s in _sentences(lines) if key in kit_source.area_refs(s['text'])]
