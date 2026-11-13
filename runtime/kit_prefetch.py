"""Cheap next-move prep after the opening is already up.

While the host waits on the player, the current area, its exits, one
confirmed link hop, and rulings for the obvious next actions are loaded
so the next response can be a commit, not a lookup. This is never called
from landing or pick.
"""

def prepare_next(db, scene_key=None, beat=None):
    """Prefetch the current section's cheap next-move context. Structural only."""
    from .kit_adventure import _load
    from . import kit_links, kit_rulings
    try:
        index, text = _load(db)
    except Exception:
        return None
    key = kit_links.section_key(index, scene_key or index.get('start'))
    if not key:
        return None
    loc = (index.get('locations') or {}).get(key) or {}
    span = kit_links._recorded_span(loc, len(text or ''))
    exits = list(loc.get('leads_to') or loc.get('exits') or [])
    hops = kit_links.prefetch_confirmed(db, key)
    look_talk_check = {'look': 0, 'talk': 0, 'check': 0}
    ruling_hits = []
    records = []
    visible = set()
    for person in (beat or {}).get('people') or []:
        if person.get('addressable') and not person.get('hidden') and person.get('name'):
            visible.add(person.get('name'))
    for ruling in kit_rulings.rulings_from(index, key):
        kinds = kit_rulings.obvious_kinds(ruling)
        if visible and (ruling.get('trigger_kind') == 'npc' or 'talk' in kinds):
            if 'talk' not in kinds:
                kinds.append('talk')
        if not kinds:
            continue
        for kind in kinds:
            look_talk_check[kind] = look_talk_check.get(kind, 0) + 1
        ruling_hits.append({
            'kinds': kinds,
            'confidence': ruling.get('confidence'),
            'quote_words': len(str(ruling.get('quote') or '').split()),
            'has_mechanics': bool(ruling.get('has_mechanics')),
        })
        records.append({
            'from': ruling.get('from'),
            'confidence': ruling.get('confidence'),
            'condition': ruling.get('condition') or '',
            'outcome': ruling.get('outcome') or '',
            'quote': ruling.get('quote') or '',
            'span': ruling.get('span'),
            'trigger_kind': ruling.get('trigger_kind') or '',
            'has_mechanics': bool(ruling.get('has_mechanics')),
        })
    fiction_n = 0
    for item in (beat or {}).get('fiction') or []:
        if item:
            fiction_n += 1
    return {
        'ready': True,
        'area_key': key,
        'area_chars': (span[1] - span[0]) if span else 0,
        'exits_n': len(exits),
        'link_hops_n': len(hops),
        'link_hops': hops,
        'ruling_n': len(ruling_hits),
        'obvious': look_talk_check,
        'rulings': ruling_hits,
        'ruling_records': records,
        'look_ready': bool(fiction_n or visible),
        'talk_ready': sorted(visible),
    }


def stash(db, scene_key=None, beat=None):
    """Write next-move prep onto the session sidecar once the opening is up."""
    from . import kit_skim
    try:
        data = kit_skim._read(db)
    except Exception:
        data = {}
    if data.get('next_move_prep'):
        return data.get('next_move_prep')
    if data.get('status') != 'accepted' and not data.get('burst_spoken'):
        return None
    found = prepare_next(db, scene_key or data.get('scene_key') or data.get('design_start_name'),
                         beat or (data.get('beat') if isinstance(data.get('beat'), dict) else None))
    if not found:
        return None
    try:
        fresh = kit_skim._read(db)
        fresh['next_move_prep'] = found
        kit_skim._write(db, fresh)
    except Exception:
        return found
    return found
