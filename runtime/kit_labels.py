"""One labeling pass per section, answered by the host. Python never calls a model.

Python splits a heading or a site into blocks and auto-labels front matter. The host
returns ids and enums only. Python checks the reply, clamps leaks, and freezes it.
An invalid reply speaks nothing from that section.
"""
import json
import re

AUDIENCE = ('player', 'dm', 'front')
KIND = ('read_aloud', 'prose', 'keyed', 'sidebar', 'rules', 'meta', 'map')
SECTION_MODE = ('crawl', 'town_social', 'regional')
HEARD = ('read_aloud', 'prose')
REPLY_KEYS = ('section', 'section_mode', 'opening_block', 'blocks')
BLOCK_KEYS = ('audience', 'kind', 'scene', 'opening')

LEAK_RE = re.compile(
    r'\bDC\s*\d+\b'
    r'|\b(?:armor|armour)\s+class\b'
    r'|\bhit points\b'
    r'|\bif the characters\b'
    r'|\bread when\b'
    r'|\b(?:secret|hidden|concealed)\b',
    re.I)
# A DM tip in front of boxed fiction. Cut before the box. A block that stays fused
# cannot open, and is not painted dm (that would delete the only box).
TIP_RE = re.compile(
    r"read the (?:following )?boxed(?: text)?"
    r"|when you(?:'re| are) ready"
    r"|skip\b[^.]{0,80}\bhook"
    r"|read or paraphrase"
    r"|add the following",
    re.I)
FRONT_RE = re.compile(
    r'^(?:contents|index|credits|preface|foreword|glossary|bibliography|overview|introduction|'
    r'rests|legal|welcome|tools|sheets|title)\b',
    re.I)
SIDEBAR_RE = re.compile(
    r'^(?:sidebar|side bar|general features|history)\b',
    re.I)
LATER_SUMMARY_RE = re.compile(
    r'\b(?:later floors?|lower levels?|the levels? below|the rest of (?:the )?(?:dungeon|crawl)|'
    r'on the floors? (?:below|above))\b',
    re.I)
PLAYABLE_HEAD_RE = re.compile(
    r'^(?:starting the adventure)\b'
    r'|^(?:encounter|scene|section)\s+[A-Z]?\d+'
    r'|^(?:part|chapter)\s+\S+',
    re.I)
SPEAKER_RE = re.compile(
    r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\s+'
    r'(?:says?|asks?|calls?|shouts?|whispers?|replies?|answers?|tells?|greets?|waves?|nods?)\b',
)
BLOCK_CAP = 20
BYTE_CAP = 6000

INSTRUCTIONS = (
    'Label this one section. Return one JSON object and nothing else. '
    'Ids and enums only. Do not echo the block text.\n'
    'Keys: section, section_mode, opening_block, blocks.\n'
    'section_mode is one of crawl, town_social, regional.\n'
    'blocks maps every listed id to '
    '{"audience":"player|dm|front","kind":"read_aloud|prose|keyed|sidebar|rules|meta|map",'
    '"scene":"<an id from scenes>","opening":true|false}. No other keys.\n'
    'Exactly one block has opening true, and opening_block is that id. '
    'The opening is the first player read_aloud in the section, or the first player prose '
    'when the section has no player read_aloud. It is never front matter, a title, a tip, '
    'or a later room.\n'
    'scene is only an id from that block\'s scenes list. Do not pull a block back onto an '
    'earlier scene, and do not assign it to a later scene.\n'
    'Python has already marked front matter. Leave it front. It is not in this request.\n'
    'A table or a sidebar is pre-tagged kind sidebar and audience dm. Keep it dm.\n'
    'A block that contains a DC, armor class, hit points, "if the characters", "read when", '
    'or a secret is dm even when you mark it player. Python will force that.\n'
    'One section per call. The opening section is the only pass before the first reply. '
    'Later sections are labeled during a clarify or a roll.\n'
    'Example shape, with the real ids from this request:\n'
    '{"section":"<section>","section_mode":"crawl","opening_block":"<id>",'
    '"blocks":{"<id>":{"audience":"player","kind":"read_aloud","scene":"<scene>","opening":true}}}'
)


def _path(db):
    from .kit_adventure import folder_for
    return folder_for(db) / 'labels.json'


def _read(db):
    path = _path(db)
    if not path.is_file():
        return {'frozen': {}, 'opening': None, 'want': None, 'silent': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'frozen': {}, 'opening': None, 'want': None, 'silent': []}
    data.setdefault('frozen', {})
    data.setdefault('silent', [])
    return data


def _write(db, data):
    path = _path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def leak(text):
    """A DM-only pattern. Player-facing labels do not keep it spoken."""
    return bool(LEAK_RE.search(text or ''))


def _split_tip(text):
    """(tip, box, fused). A clean cut puts the fiction after the cue in its own block.

    Primary cut: the sentence that holds the cue, then the fiction.
    Secondary cut: a colon after the cue. Still one blob: fused, and not the opening.
    """
    match = TIP_RE.search(text or '')
    if not match:
        return None
    # A colon after the cue introduces the box, even inside the same sentence.
    colon = text.find(':', match.start())
    end = len(text)
    for mark in '.!?':
        at = text.find(mark, match.end())
        if 0 <= at < end:
            end = at + 1
    if 0 <= colon < end:
        tip, box = text[:colon + 1].strip(), text[colon + 1:].strip()
        if box and not TIP_RE.search(box):
            return tip, box, False
    tip, box = text[:end].strip(), text[end:].strip()
    if box and not TIP_RE.search(box):
        return tip, box, False
    return text.strip(), '', True


def _split_leak(text):
    """A DC or a secret in one sentence does not drag the next sentence into dm."""
    parts = [part.strip() for part in re.split(r'(?<=[.!?])\s+', text or '') if part.strip()]
    if len(parts) < 2 or not any(leak(part) for part in parts):
        return None
    return parts


def _normalize_words(text):
    """One spacing, soft hyphens gone, a hyphenated wrap joined, before anything is frozen."""
    text = (text or '').replace('\u00ad', '')
    text = re.sub(r'(\w)-\s+([A-Za-z])', r'\1\2', text)
    return re.sub(r'\s+', ' ', text).strip()


def _table_line(line):
    stripped = line.strip()
    if stripped.count('|') >= 2:
        return True
    return len(re.findall(r'\S\s{2,}\S', stripped)) >= 1 and stripped.count('  ') >= 2


def _lines(text, start, end):
    rel = 0
    chunk = text[start:end]
    for line in chunk.split('\n'):
        yield start + rel, line
        rel += len(line) + 1


def blocks_for(text, loc):
    """Blocks inside one section, in reading order. Ids are b0, b1, ..."""
    from .kit_adventure import LOCATION_RE, _LABELED_RE
    start, end = loc['body']
    groups = []
    buf = []
    kind = None

    def flush():
        nonlocal buf, kind
        if not buf:
            kind = None
            return
        raw = '\n'.join(line for _off, line in buf).strip()
        if raw:
            groups.append({
                'start': buf[0][0],
                'end': buf[-1][0] + len(buf[-1][1]) + 1,
                'text': _normalize_words(raw.replace('>', ' ')),
                'kind': kind or 'prose',
            })
        buf = []
        kind = None

    for off, line in _lines(text, start, end):
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if SIDEBAR_RE.match(stripped):
            flush()
            kind = 'sidebar'
            buf.append((off, line))
            continue
        if _table_line(stripped):
            if kind not in (None, 'sidebar'):
                flush()
            kind = 'sidebar'
            buf.append((off, line))
            continue
        if stripped.startswith('>'):
            if kind not in (None, 'read_aloud'):
                flush()
            kind = 'read_aloud'
            buf.append((off, line))
            continue
        if LOCATION_RE.match(stripped) or _LABELED_RE.match(stripped):
            flush()
            groups.append({
                'start': off, 'end': off + len(line) + 1,
                'text': re.sub(r'\s+', ' ', stripped).strip(), 'kind': 'keyed',
            })
            continue
        if kind in ('read_aloud', 'sidebar'):
            flush()
        if kind is None and len(stripped) <= 60 and stripped[:1].isupper() and stripped[-1] not in '.?!':
            flush()
            groups.append({
                'start': off, 'end': off + len(line) + 1,
                'text': re.sub(r'\s+', ' ', stripped).strip(), 'kind': 'meta',
            })
            continue
        kind = kind or 'prose'
        buf.append((off, line))
    flush()
    scene = loc.get('key')
    expanded = []
    for group in groups:
        split = _split_tip(group['text'])
        if not split:
            expanded.append(group)
            continue
        tip, box, fused = split
        if fused:
            # Still one blob. It cannot open. Do not paint it dm: that would delete the only box.
            expanded.append({**group, 'fused': True})
            continue
        expanded.append({**group, 'text': tip, 'kind': 'rules', 'tip': True})
        expanded.append({
            'start': group['start'], 'end': group['end'], 'text': _normalize_words(box),
            'kind': 'read_aloud',
        })
    leaked = []
    for group in expanded:
        parts = None if group.get('fused') or group.get('tip') else _split_leak(group['text'])
        if not parts:
            leaked.append(group)
            continue
        for part in parts:
            leaked.append({**group, 'text': part, 'kind': 'rules' if leak(part) else group['kind'],
                           'tip': True if leak(part) else group.get('tip')})
    expanded = leaked
    out = []
    for n, group in enumerate(expanded):
        text_out = group['text']
        kind = group['kind']
        block_scene = scene
        audience = 'dm' if kind == 'sidebar' or leak(text_out) or group.get('tip') else None
        if FRONT_RE.match(text_out) or SIDEBAR_RE.match(text_out) or LATER_SUMMARY_RE.search(text_out):
            if SIDEBAR_RE.match(text_out) or LATER_SUMMARY_RE.search(text_out):
                audience, kind, block_scene = 'dm', 'sidebar', None
            else:
                audience, kind = 'front', 'meta'
        block = {
            'id': 'b%d' % n, 'text': text_out, 'start': group['start'], 'end': group['end'],
            'kind': kind, 'scene': block_scene,
            'scenes': [block_scene] if block_scene else [],
        }
        if group.get('fused'):
            block['fused'] = True
        if audience:
            block['audience'] = audience
            block['locked'] = True
        out.append(block)
    return out


def _ordered(blocks):
    if isinstance(blocks, dict):
        rows = list(blocks.values())
    else:
        rows = list(blocks or [])
    return sorted(rows, key=lambda block: (block.get('start', 0), block.get('id', '')))


def _eligible(block):
    """A clean player read-aloud or prose block. A fused tip is never the opening."""
    return (block.get('audience') == 'player' and block.get('kind') in HEARD
            and not block.get('fused') and block.get('scene') is not None
            and not leak(block.get('text', '')) and block.get('kind') != 'sidebar')


def choose_opening(blocks):
    """The first player read-aloud, otherwise the first player prose."""
    rows = [block for block in _ordered(blocks) if _eligible(block)]
    aloud = [block for block in rows if block.get('kind') == 'read_aloud']
    if aloud:
        return aloud[0]['id']
    prose = [block for block in rows if block.get('kind') == 'prose']
    return prose[0]['id'] if prose else None


def suggest_opening(blocks):
    """The first clean player read-aloud, else prose. A fused tip is skipped, not relabeled."""
    rows = [block for block in _ordered(blocks)
            if not block.get('fused') and block.get('audience') != 'front'
            and block.get('kind') != 'sidebar' and block.get('scene') is not None
            and not leak(block.get('text', ''))]
    aloud = [block for block in rows if block.get('kind') == 'read_aloud']
    if aloud:
        return aloud[0]['id']
    prose = [block for block in rows if block.get('kind') == 'prose']
    return prose[0]['id'] if prose else None


def _cap_blocks(blocks):
    """One call is at most 20 blocks and 6 KB of block text. Never a 100-block request."""
    out, size = [], 0
    for block in blocks:
        raw = len((block.get('text') or '').encode('utf-8'))
        if out and (len(out) >= BLOCK_CAP or size + raw > BYTE_CAP):
            break
        out.append(block)
        size += raw
    return out


def _host_blocks(blocks):
    """Blocks the host must label. Front matter is already decided."""
    return [block for block in blocks if block.get('audience') != 'front']


def request_for(db, key):
    """A labeling request for one section. None when it is frozen, silent, or only front matter."""
    from .kit_adventure import _load
    data = _read(db)
    if key in (data.get('frozen') or {}) or key in (data.get('silent') or []):
        return None
    index, text = _load(db)
    loc = (index.get('locations') or {}).get(key)
    if not loc:
        return None
    loc = dict(loc, key=key)
    blocks = blocks_for(text, loc)
    if not blocks:
        return None
    host = list(_host_blocks(blocks))
    if not host:
        _freeze_front(db, key, blocks)
        return None
    host = _cap_blocks(host)
    opening = suggest_opening(host)
    if not opening:
        # Nothing clean to open on. A fused tip is not relabeled dm and is not spoken.
        _silence(db, key)
        return None
    return {
        'stage': 'label_section',
        'section': key,
        'instructions': INSTRUCTIONS,
        'section_modes': list(SECTION_MODE),
        'scenes': [key],
        'opening_block': opening,
        'blocks': [{
            'id': block['id'], 'text': block['text'], 'kind': block['kind'],
            'scene': block['scene'], 'scenes': list(block['scenes']),
            'start': block['start'], 'end': block['end'],
            **({'audience': block['audience'], 'locked': True} if block.get('locked') else {}),
            **({'fused': True} if block.get('fused') else {}),
        } for block in host],
    }


def _freeze_front(db, key, blocks):
    data = _read(db)
    if key in data['frozen']:
        return
    stored = {}
    for block in blocks:
        stored[block['id']] = {
            'audience': 'front', 'kind': block.get('kind') or 'meta', 'scene': block['scene'],
            'opening': False, 'start': block['start'], 'end': block['end'], 'text': block['text'],
        }
    data['frozen'][key] = {'blocks': stored, 'opening_block': None, 'section_mode': None, 'front': True}
    _write(db, data)
    from .kit_adventure import _load
    try:
        index, _text = _load(db)
    except Exception:
        return
    if index.get('start') == key:
        _soft_start(db, key)


def first_playable_offset(text):
    """Where front matter ends: Starting the Adventure, Encounter N, a part, or a greeter."""
    from .kit_adventure import _toc_line, contents_ranges
    listed = contents_ranges(text or '')
    at = 0
    head = None
    for line in (text or '').split('\n'):
        stripped = line.strip()
        in_list = any(start <= at < end for start, end in listed)
        if stripped and not in_list and not _toc_line(stripped):
            if PLAYABLE_HEAD_RE.match(stripped):
                return at
            if head is not None and SPEAKER_RE.search(stripped):
                return head
            if (not stripped.startswith('>') and len(stripped) <= 60 and stripped[:1].isupper()
                    and stripped[-1:] not in '.?!'):
                head = at
            elif stripped[-1:] in '.?!':
                head = None
        at += len(line) + 1
    return None


def mark_leading_front(db):
    """Title, credits, contents, and the rest before the first playable heading. No label call."""
    from .kit_adventure import _load
    try:
        index, text = _load(db)
    except Exception:
        return
    cut = first_playable_offset(text)
    if cut is None:
        return
    for key, loc in (index.get('locations') or {}).items():
        if (loc.get('offset') or 0) >= cut:
            continue
        if key in (_read(db).get('frozen') or {}):
            continue
        blocks = blocks_for(text, dict(loc, key=key))
        if not blocks:
            continue
        for block in blocks:
            block['audience'] = 'front'
            block['kind'] = 'meta'
        _freeze_front(db, key, blocks)


def opening_labeled(db):
    data = _read(db)
    opening = data.get('opening')
    return bool(opening and opening in (data.get('frozen') or {}))


def is_silent(db, key):
    return key in (_read(db).get('silent') or [])


def section_for_room(db, room_id):
    room_id = str(room_id or '')
    if not room_id.startswith('adv-'):
        return None
    _sha, _, slug = room_id[4:].partition('-')
    if not slug:
        return None
    from .kit_adventure import _load, _slug
    try:
        index, _text = _load(db)
    except Exception:
        return None
    found = (index.get('by_slug') or {}).get(slug)
    if found:
        return found
    for key in index.get('locations') or {}:
        if _slug(key) == slug:
            return key
    return None


def request_for_room(db, room_id):
    key = section_for_room(db, room_id)
    if not key:
        return None
    return request_for(db, key)


def next_request(db):
    """The opening section before play. Once a room is mounted, the section play is in."""
    from .kit_adventure import _load
    from .kit_lifecycle import mounted_room_id
    mounted = request_for_room(db, mounted_room_id(db))
    if mounted:
        return mounted
    seen = set()
    for _hop in range(8):
        try:
            index, _text = _load(db)
        except Exception:
            return None
        data = _read(db)
        frozen = data.get('frozen') or {}
        silent = set(data.get('silent') or [])
        want = data.get('want') or data.get('opening') or index.get('start')
        if not want or want in seen or want in silent or want in frozen:
            return None
        seen.add(want)
        req = request_for(db, want)
        if req:
            return req
    return None


def patter_request(db):
    """The section play has reached, offered during a clarify or a roll. None before a room is up."""
    from .kit_lifecycle import mounted_room_id
    if not mounted_room_id(db):
        return None
    return next_request(db)


def _problems(req, reply):
    if not isinstance(reply, dict):
        return ['the reply must be one JSON object']
    if set(reply) - set(REPLY_KEYS):
        return ['the reply echoes something other than ids and enums']
    if reply.get('section') not in (None, '', req.get('section')):
        return ['this reply is for %s' % req.get('section')]
    if reply.get('section_mode') not in SECTION_MODE:
        return ['section_mode must be crawl, town_social, or regional']
    blocks = reply.get('blocks')
    if not isinstance(blocks, dict):
        return ['blocks must map each id to enums']
    issued = {block['id']: block for block in req.get('blocks') or []}
    problems = []
    if set(blocks) != set(issued):
        problems.append('labels are only accepted for block ids Python issued')
    openings = []
    for block_id, body in blocks.items():
        if block_id not in issued:
            continue
        if not isinstance(body, dict) or set(body) != set(BLOCK_KEYS):
            problems.append('block %s must be audience, kind, scene, and opening' % block_id)
            continue
        if body.get('audience') not in AUDIENCE:
            problems.append('audience %r is not player, dm, or front' % body.get('audience'))
        if body.get('kind') not in KIND:
            problems.append('kind %r is not a block kind' % body.get('kind'))
        if type(body.get('opening')) is not bool:
            problems.append('opening must be true or false')
        allow = issued[block_id].get('scenes') or []
        if issued[block_id].get('scene') is None:
            if body.get('scene') not in (None, ''):
                problems.append('a sidebar is not a scene')
        elif body.get('scene') not in allow:
            problems.append('scene %r is not on the allowlist' % body.get('scene'))
        elif body.get('scene') != issued[block_id].get('scene'):
            problems.append('a block cannot be pulled onto another scene')
        if body.get('opening') is True:
            openings.append(block_id)
    if len(openings) != 1:
        problems.append('exactly one opening')
    elif reply.get('opening_block') != openings[0]:
        problems.append('opening_block must be the one opening')
    return problems


def _clamp(req, reply):
    """Force leaks, sidebars, and front matter. Pick the opening the rules require."""
    issued = {block['id']: block for block in req.get('blocks') or []}
    stored = {}
    for block_id, body in reply['blocks'].items():
        src = issued[block_id]
        audience = body['audience']
        kind = body['kind']
        if src.get('locked') and src.get('audience') == 'front':
            audience, kind = 'front', src.get('kind') or kind
        if src.get('kind') == 'sidebar' or kind == 'sidebar':
            audience, kind = 'dm', 'sidebar'
        if leak(src.get('text', '')):
            audience = 'dm'
        if audience == 'front':
            kind = src.get('kind') or 'meta'
        stored[block_id] = {
            'id': block_id, 'audience': audience, 'kind': kind, 'scene': src.get('scene'),
            'opening': False, 'start': src.get('start'), 'end': src.get('end'),
            'text': _normalize_words(src.get('text') or ''),
        }
        if src.get('fused'):
            stored[block_id]['fused'] = True
    opening = choose_opening(stored)
    if opening:
        stored[opening]['opening'] = True
    return {
        'blocks': stored, 'opening_block': opening, 'section_mode': reply.get('section_mode'),
    }


def _set_opening(db, key):
    from .kit_adventure import _load, _write_json, folder_for
    index, _text = _load(db)
    index['start'] = key
    for item in index.get('starts') or []:
        item['default'] = item.get('id') == key
    _write_json(folder_for(db) / 'index.json', index)


def _drop_room(db, section):
    from .kit_adventure import room_file
    path = room_file(db, section)
    if path.is_file():
        path.unlink()
    side = path.with_suffix('.provenance.json')
    if side.is_file():
        side.unlink()


def _soft_start(db, skipped):
    """The next playable section after one that cannot be spoken. None leaves the picker."""
    from .kit_adventure import _load, compile_location
    index, text = _load(db)
    data = _read(db)
    silent = set(data.get('silent') or [])
    here = (index.get('locations') or {}).get(skipped) or {}
    order = sorted((index.get('locations') or {}).items(), key=lambda item: item[1].get('offset') or 0)
    for key, loc in order:
        if key == skipped or key in silent or key in (data.get('frozen') or {}):
            continue
        if (loc.get('offset') or 0) < (here.get('offset') or 0):
            continue
        blocks = blocks_for(text, dict(loc, key=key))
        host = _host_blocks(blocks)
        if not host:
            continue
        if not any(block.get('kind') in HEARD or block.get('kind') == 'keyed' for block in host):
            continue
        _set_opening(db, key)
        data = _read(db)
        data['want'] = key
        data['opening'] = None
        _write(db, data)
        try:
            compile_location(db, key, neighbours=False)
        except Exception:
            pass
        return key
    _set_opening(db, None)
    return None


def _silence(db, section):
    data = _read(db)
    if section not in data['silent']:
        data['silent'].append(section)
    data['frozen'].pop(section, None)
    _write(db, data)
    _drop_room(db, section)
    return _soft_start(db, section)


def _recompile(db, section):
    from .kit_adventure import compile_location, room_file
    try:
        if room_file(db, section).is_file() or True:
            compile_location(db, section, neighbours=False)
    except Exception:
        pass


def accept(db, reply):
    """Validate one section. Invalid replies are not stored and that section is not spoken."""
    from .kit_adventure import _load
    req = next_request(db)
    if isinstance(reply, dict) and reply.get('section'):
        data = _read(db)
        prior = (data.get('frozen') or {}).get(reply['section'])
        if prior and req and reply.get('section') == req.get('section'):
            pass
        elif prior and reply.get('section') != (req or {}).get('section'):
            try:
                index, text = _load(db)
                loc = dict((index.get('locations') or {}).get(reply['section']) or {}, key=reply['section'])
                prior_req = {
                    'section': reply['section'],
                    'blocks': [{'id': bid, 'text': body.get('text'), 'kind': body.get('kind'),
                                'scene': body.get('scene'), 'scenes': [body.get('scene')],
                                'start': body.get('start'), 'end': body.get('end')}
                               for bid, body in (prior.get('blocks') or {}).items()],
                }
                if not _problems(prior_req, reply):
                    clamped = _clamp(prior_req, reply)
                    same = {bid: {k: body.get(k) for k in ('audience', 'kind', 'scene', 'opening')}
                            for bid, body in (prior.get('blocks') or {}).items()}
                    fresh = {bid: {k: body.get(k) for k in ('audience', 'kind', 'scene', 'opening')}
                             for bid, body in clamped['blocks'].items()}
                    if same == fresh and prior.get('section_mode') == clamped.get('section_mode'):
                        return {'stage': 'labels_frozen', 'section': reply['section'],
                                'opening': data.get('opening'), 'label_request': req,
                                'player_hears': _lines_from(prior)}
            except Exception:
                pass
            return {'stage': 'labels_rejected', 'problems': ['%s is already frozen' % reply['section']],
                    'label_request': req}
    if not req:
        return {'stage': 'labels_idle', 'label_request': None}
    problems = _problems(req, reply)
    if problems:
        fallback = _silence(db, req['section'])
        return {'stage': 'labels_rejected', 'problems': problems, 'label_request': next_request(db),
                'soft_start': fallback, 'start_picker': _picker(db), 'player_hears': []}
    clamped = _clamp(req, reply)
    issued = {block['id']: block for block in req.get('blocks') or []}
    named = issued.get(reply.get('opening_block')) or {}
    if clamped.get('opening_block') != reply.get('opening_block'):
        # A fused tip is refused as the opening. The next clean player block stands.
        # If there is none, soft-start. Any other mismatch is still a bad label pass.
        if named.get('fused') and clamped.get('opening_block'):
            pass
        elif not clamped.get('opening_block'):
            fallback = _silence(db, req['section'])
            return {'stage': 'labels_rejected',
                    'problems': ['a fused tip cannot open, and no clean player block follows'],
                    'label_request': next_request(db), 'soft_start': fallback,
                    'start_picker': _picker(db), 'player_hears': []}
        else:
            fallback = _silence(db, req['section'])
            return {'stage': 'labels_rejected',
                    'problems': ['the opening must be the first player read-aloud, or player prose'],
                    'label_request': next_request(db), 'soft_start': fallback,
                    'start_picker': _picker(db), 'player_hears': []}
    if any(body.get('audience') == 'front' and body.get('opening') for body in clamped['blocks'].values()):
        fallback = _silence(db, req['section'])
        return {'stage': 'labels_rejected', 'problems': ['front matter is never the opening'],
                'label_request': next_request(db), 'soft_start': fallback,
                'start_picker': _picker(db), 'player_hears': []}
    data = _read(db)
    prior = (data.get('frozen') or {}).get(req['section'])
    if prior:
        same = {bid: {k: body.get(k) for k in ('audience', 'kind', 'scene', 'opening')}
                for bid, body in (prior.get('blocks') or {}).items()}
        fresh = {bid: {k: body.get(k) for k in ('audience', 'kind', 'scene', 'opening')}
                 for bid, body in clamped['blocks'].items()}
        if same != fresh or prior.get('section_mode') != clamped.get('section_mode'):
            return {'stage': 'labels_rejected', 'problems': ['%s is already frozen' % req['section']],
                    'label_request': req}
    data.setdefault('frozen', {})[req['section']] = clamped
    opening = clamped.get('opening_block')
    if opening and any(body.get('audience') == 'player' for body in clamped['blocks'].values()):
        data['opening'] = req['section']
        data['want'] = None
        _set_opening(db, req['section'])
    elif not opening:
        data['want'] = None
        _soft_start(db, req['section'])
    if req['section'] in data.get('silent') or []:
        data['silent'] = [key for key in data.get('silent') or [] if key != req['section']]
    _write(db, data)
    _recompile(db, req['section'])
    hears = _lines_from(clamped)
    return {'stage': 'labels_frozen', 'section': req['section'], 'opening': _read(db).get('opening'),
            'opening_block': opening, 'player_hears': hears, 'label_request': next_request(db)}


def _lines_from(stored):
    lines = []
    for block in _ordered((stored or {}).get('blocks') or {}):
        if _eligible(block):
            lines.append(block.get('text') or '')
    return [line for line in lines if line]


def _picker(db):
    from .kit_adventure import _load, start_picker
    try:
        index, _text = _load(db)
    except Exception:
        return None
    return start_picker(index.get('starts') or [])


def frozen_blocks(db, key):
    row = (_read(db).get('frozen') or {}).get(key)
    if not row:
        return None
    return row.get('blocks') or None


def frozen_labels(db, key):
    """Compatibility: audience by block id."""
    blocks = frozen_blocks(db, key)
    if not blocks:
        return None
    return {bid: body.get('audience') for bid, body in blocks.items()}


def audience_for(blocks, offset, sentence):
    if not blocks:
        return None
    if leak(sentence):
        return 'dm'
    for body in blocks.values():
        if body.get('start', 0) <= offset < body.get('end', 0):
            if body.get('kind') == 'sidebar':
                return 'dm'
            return body.get('audience')
    return None


def apply_blocks(read, dm, blocks):
    """Player read-aloud and prose stay visible. Leaks, sidebars, and front matter do not."""
    rows = [(off, sent) for off, sent in list(read) + list(dm)]
    rows.sort(key=lambda item: item[0])
    spoken, hidden = [], []
    for off, sent in rows:
        audience = audience_for(blocks, off, sent)
        if audience == 'player':
            kind = None
            for body in blocks.values():
                if body.get('start', 0) <= off < body.get('end', 0):
                    kind = body.get('kind')
                    break
            if kind in HEARD:
                spoken.append((off, sent))
            continue
        if audience == 'front':
            continue
        hidden.append((off, sent))
    return spoken, hidden


def apply_labels(read, dm, labels):
    """Older callers passed an audience map. Block records are the real input."""
    if labels and isinstance(next(iter(labels.values()), None), dict):
        return apply_blocks(read, dm, labels)
    return read, dm


def player_hears(db, source):
    """Lines the player may hear in this room. None when this is not an ingested scene."""
    if not str((source or {}).get('id') or '').startswith('adv-'):
        return None
    key = section_for_room(db, (source or {}).get('id'))
    if not key:
        return None
    if is_silent(db, key):
        return []
    blocks = frozen_blocks(db, key)
    if blocks:
        return _lines_from({'blocks': blocks})
    from .kit_adventure import room_file
    path = room_file(db, key)
    if not path.is_file():
        return []
    try:
        room = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    lines = []
    for fact in (room.get('facts') or {}).values():
        if isinstance(fact, dict) and fact.get('visible') and fact.get('text') and not leak(fact.get('text')):
            lines.append(fact['text'])
    return lines
