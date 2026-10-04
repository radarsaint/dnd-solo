"""SRD 5.1 stat lines a room file can cite by name: ``"stat_block": {"srd": "Guard"}``.

Numbers are the SRD 5.1 stat blocks (CC-BY-4.0, Wizards of the Coast;
https://creativecommons.org/licenses/by/4.0/), in the combat engine's shape
(runtime/kit_combat.py): AC, hit points, initiative (Dex modifier), grapple (Str
modifier, Athletics when proficient), saves, attacks with average damage. Data only;
add a creature here when a room cites one that is not yet listed.
"""

_ATTACK = lambda name, verb, to_hit, damage, kind: {'name': name, 'verb': verb, 'to_hit': to_hit,
                                                     'damage': damage, 'type': kind}

CREATURES = {
    'commoner': {'ac': 10, 'hp': 4, 'initiative': 0, 'grapple': 0, 'saves': {},
                 'attacks': [_ATTACK('club', 'strikes', 2, 2, 'bludgeoning')]},
    'guard': {'ac': 16, 'hp': 11, 'initiative': 1, 'grapple': 1, 'saves': {},
              'attacks': [_ATTACK('spear', 'thrusts at', 3, 4, 'piercing')]},
    'bandit': {'ac': 12, 'hp': 11, 'initiative': 1, 'grapple': 0, 'saves': {},
               'attacks': [_ATTACK('scimitar', 'cuts', 3, 4, 'slashing')]},
    'scout': {'ac': 13, 'hp': 16, 'initiative': 2, 'grapple': 0, 'saves': {},
              'attacks': [_ATTACK('shortsword', 'stabs', 4, 5, 'piercing')]},
    'thug': {'ac': 11, 'hp': 32, 'initiative': 0, 'grapple': 2, 'saves': {},
             'attacks': [_ATTACK('mace', 'clubs', 4, 5, 'bludgeoning'), _ATTACK('mace', 'clubs', 4, 5, 'bludgeoning')]},
    'veteran': {'ac': 17, 'hp': 58, 'initiative': 1, 'grapple': 5, 'saves': {},
                'attacks': [_ATTACK('longsword', 'cuts', 5, 7, 'slashing'), _ATTACK('longsword', 'cuts', 5, 7, 'slashing')]},
}

INLINE_KEYS = ('ac', 'hp', 'attacks')


def stat_block(block):
    """The engine stat line for a room's ``stat_block`` (an SRD reference or inline), or None."""
    import copy
    if not isinstance(block, dict):
        return None
    if 'srd' in block:
        found = CREATURES.get(str(block['srd']).strip().casefold())
        return copy.deepcopy(found) if found else None
    if all(key in block for key in INLINE_KEYS) and type(block['ac']) is int and type(block['hp']) is int and \
            block['hp'] > 0 and isinstance(block['attacks'], list) and block['attacks'] and \
            all(isinstance(a, dict) and {'name', 'to_hit', 'damage'} <= set(a) for a in block['attacks']):
        return {'initiative': 0, 'grapple': 0, 'saves': {}, **copy.deepcopy(block),
                'attacks': [{'verb': 'strikes', 'type': 'bludgeoning', **a} for a in block['attacks']]}
    return None
