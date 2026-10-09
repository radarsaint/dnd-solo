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
    # SRD 5.1 Giant Centipede: Bite +4, 4 (1d4+2) piercing, and a DC 11 Constitution save or
    # 10 (3d6) poison (no damage on a success). Poison that drops the target to 0 hp leaves it
    # stable but poisoned for 1 hour, paralyzed while poisoned. No Stealth listed: Dex +2.
    'giant centipede': {'ac': 13, 'hp': 4, 'initiative': 2, 'grapple': -3, 'saves': {}, 'stealth': 2,
                        'attacks': [{**_ATTACK('bite', 'bites', 4, 4, 'piercing'),
                                     'save': {'ability': 'con', 'dc': 11, 'damage': 10, 'type': 'poison',
                                              'half': False, 'at_zero': ['poisoned', 'paralyzed']}}]},
    # SRD 5.1 Ghoul: AC 12, 22 (5d8) hp, Dex 15. Bite +2, 9 (2d6+2) piercing, or Claws +4,
    # 7 (2d4+2) slashing; a creature other than an elf or undead hit by the claws makes a DC 10
    # Constitution save or is paralyzed for 1 minute, repeating the save at the end of each of
    # its turns. The engine's one swing a turn is the claws.
    'ghoul': {'ac': 12, 'hp': 22, 'initiative': 2, 'grapple': 1, 'saves': {}, 'stealth': 2,
              'attacks': [{**_ATTACK('claws', 'rakes', 4, 7, 'slashing'),
                           'save': {'ability': 'con', 'dc': 10, 'damage': 0, 'type': 'paralysis',
                                    'condition': {'name': 'paralyzed', 'rounds': 10, 'repeat': 'end_of_turn',
                                                  'immune': ['elf']}}}]},
    # SRD 5.1 Skeleton: AC 13 (armor scraps), 13 (2d8+4) hp, Dex 14. Shortsword +4, 5 (1d6+2)
    # piercing. No Stealth listed: Dex +2.
    'skeleton': {'ac': 13, 'hp': 13, 'initiative': 2, 'grapple': 0, 'saves': {}, 'stealth': 2,
                 'attacks': [_ATTACK('shortsword', 'stabs', 4, 5, 'piercing')]},
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
