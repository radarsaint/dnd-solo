"""Test helper: a faithful room built mechanically from any source manifest
(runtime/kit_extract.py), whatever its author. Every source sentence is carried as a hidden
fact, every creature and NPC is an actor (SRD block, else needs_stats), every hazard is a
trap, every way the source names is an uncertain author link, and nothing the player sees
names a secret. Tests mutate it to show each kind of infidelity is caught; it holds no
source text of its own (it copies the manifest it is given at test time)."""
import re

from runtime import kit_author, kit_rooms, srd_creatures


def slug(text):
    return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_') or 'x'


def faithful_room(inputs):
    manifest = inputs['manifest']
    key = inputs['area']['key']
    level = inputs['level']
    room = {
        'id': kit_author.room_id(level, key), 'source_ref': f'Level {level} / {key} (authored)',
        'starting_area': 'approach',
        'areas': {
            'approach': {'name': 'The way in', 'called': 'the way in', 'source_area': key, 'outside': True,
                         'tease': {'text': 'The way ahead opens out.', 'heard': []}},
            'inside': {'name': 'Inside', 'called': 'inside', 'source_area': key, 'arrival': 'You go in.'},
        },
        'exits': {'in': {'name': 'the way in', 'areas': ['approach', 'inside'], 'secret': False,
                         'labels': {'approach': 'On, inside.', 'inside': 'Back out.'}}},
        'facts': {'here': {'area': 'inside', 'visible': True, 'text': 'You take in the space around you.'}},
        'actors': {}, 'triggers': [], 'traps': [], 'resources': {},
        'story': {'inside': {'about': 'What the source sets here.', 'endings': ['The PC moves on.']}},
    }
    bound = inputs['geometry'].get('bound')
    for exit_ in manifest['exits']:
        if not (exit_.get('way') or exit_.get('sibling')):
            continue
        other = exit_['area']
        area = f'to_{slug(other)}'
        room['areas'][area] = {'name': 'Beyond', 'called': 'beyond', 'source_area': other, 'outside': True,
                               'beyond': True, 'room_link': {'author': {'level': level, 'area': other}}}
        room['exits'][f'way_{slug(other)}'] = {
            'name': 'the way on', 'areas': ['inside', area], 'secret': bool(exit_.get('secret')),
            **({} if bound else {'uncertain': True}), 'labels': {'inside': 'Onward.', area: 'Back.'}}
    for sentence in manifest['sentences']:
        room['facts'][sentence['id']] = {'area': 'inside', 'visible': False, 'text': sentence['text']}
    # A bell or a shout the source rings: its responders are the creatures it sends.
    alarms = [s['id'] for s in manifest['sentences'] if kit_rooms.ALARM_WORDS.search(s['text'])]
    sent = [e for e in manifest['creatures'] if e['sentence'] in alarms and not e.get('npc') and not e.get('hidden')
            and srd_creatures.stat_block({'srd': e['kind']})]
    rounds = re.findall(r'(\d+) rounds?', ' '.join(manifest_text(manifest, sid) for sid in alarms))
    for sid in alarms if sent else ():
        room['facts'][sid]['alarm'] = {
            'responders': [{'who': e['kind'], 'count': e.get('count') or 1, 'stat_block': {'srd': e['kind']}}
                           for e in sent], 'arrives_in_rounds': int(rounds[0]) if rounds else 1}
    hidden = []
    for entry in manifest['creatures']:
        if entry.get('npc') or entry in sent:
            continue
        for n in range(entry.get('count') or 1):
            k = f'{slug(entry["kind"])}_{n + 1}'
            while k in room['actors']:
                k += '_'
            room['actors'][k] = actor(entry['kind'], entry['kind'].title(), entry.get('hidden'))
            if entry.get('hidden'):
                hidden.append(k)
    for npc in manifest['npcs']:
        k = slug(npc['name'].split()[0])
        room['actors'][k] = actor(npc.get('kind') or '', npc['name'], False)
        room['actors'][k]['secrets'] = [manifest_text(manifest, npc['sentence'])]
    fighters = [k for k, a in room['actors'].items() if k in hidden or (manifest['scripted'] and 'srd' in str(a))]
    if hidden or manifest['scripted']:
        stats = all(room['actors'][k].get('stat_block') for k in fighters) and fighters
        handled = any(item.get('on') == 'disturb' for item in manifest['scripted'])
        if handled:  # the source sets it off when something is handled: a disturb trigger
            room['facts']['here']['handling'] = {'nouns': ['space'], 'move': 'You move things about.'}
        room['triggers'].append({'id': 'stirred', 'on': {'disturb': 'here'} if handled else {'enter': 'inside'},
                                 'starts_combat': bool(stats), 'actors': fighters, 'reveal': 'Something stirs.'})
    for i, hazard in enumerate(manifest['hazards']):
        effect = {'damage': hazard['damage']}
        if hazard.get('dc'):
            effect.update(save='dex', dc=hazard['dc'][0], half_on_success=True)
        room['traps'].append({'id': f'hazard_{i + 1}', 'on': {'enter': 'inside'}, 'feature': hazard['sentence'],
                              'effect': effect, 'reset': 'once', 'reveal': 'Something goes off.'})
    if not room['triggers']:
        del room['triggers']
    if not room['traps']:
        del room['traps']
    return room


def manifest_text(manifest, sid):
    return next(s['text'] for s in manifest['sentences'] if s['id'] == sid)


def actor(kind, name, hidden):
    block = {'srd': kind} if kind and srd_creatures.stat_block({'srd': kind}) else None
    out = {'name': name, 'location': 'inside', 'status': 'hidden' if hidden else 'alive', 'visible': not hidden,
           'motive': 'Its own.', 'knowledge': [], 'secrets': []}
    if block:
        out['stat_block'] = block
    else:
        out['needs_stats'] = True
    return out
