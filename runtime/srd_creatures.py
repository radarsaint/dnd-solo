"""SRD 5.1 stat lines a room file can cite by name: ``"stat_block": {"srd": "Guard"}``.

Numbers are the SRD 5.1 stat blocks (CC-BY-4.0, Wizards of the Coast;
https://creativecommons.org/licenses/by/4.0/), in the combat engine's shape
(runtime/kit_combat.py): AC, hit points, initiative (Dex modifier), grapple (Str
modifier, Athletics when proficient), saves, attacks with average damage. Data only;
add a creature here when a room cites one that is not yet listed.

``GENERATED`` was generated from the SRD 5.1 monster data (5e-bits/5e-database, src/2014,
the SRD 5.1 under CC-BY-4.0): AC, hit points, Dex modifier, Athletics or Str modifier,
proficient saves, Stealth (or Dex), and the Multiattack's attacks with average damage on a
hit summed over its damage parts (``also`` lists the parts after the first; the engine deals
the sum). A rider save is kept when the SRD text gives one with damage. Immunities, spells
and special actions are not modelled. Never edit a number by hand: regenerate, or cite the
book's own stat block (an authored room may override ``hp``/``ac`` only with a number its
keyed text states, runtime/kit_author.py).
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
}

GENERATED = {
    'acolyte': {"ac": 10, "hp": 9, "initiative": 0, "grapple": 0, "saves": {}, "stealth": 0, "attacks": [{"name": "club", "verb": "clubs", "to_hit": 2, "damage": 2, "type": "bludgeoning"}]},
    'animated armor': {"ac": 18, "hp": 33, "initiative": 0, "grapple": 2, "saves": {}, "stealth": 0, "attacks": [{"name": "slam", "verb": "slams", "to_hit": 4, "damage": 5, "type": "bludgeoning"}, {"name": "slam", "verb": "slams", "to_hit": 4, "damage": 5, "type": "bludgeoning"}]},
    'bandit captain': {"ac": 15, "hp": 65, "initiative": 3, "grapple": 4, "saves": {"str": 4, "dex": 5, "wis": 2}, "stealth": 3, "attacks": [{"name": "scimitar", "verb": "cuts", "to_hit": 5, "damage": 6, "type": "slashing"}, {"name": "scimitar", "verb": "cuts", "to_hit": 5, "damage": 6, "type": "slashing"}, {"name": "dagger", "verb": "stabs", "to_hit": 5, "damage": 5, "type": "piercing"}]},
    'basilisk': {"ac": 12, "hp": 52, "initiative": -1, "grapple": 3, "saves": {}, "stealth": -1, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 5, "damage": 17, "type": "piercing", "also": [{"damage": 7, "type": "poison"}]}]},
    'bat': {"ac": 12, "hp": 1, "initiative": 2, "grapple": -4, "saves": {}, "stealth": 2, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 0, "damage": 1, "type": "piercing"}]},
    'black pudding': {"ac": 7, "hp": 85, "initiative": -3, "grapple": 3, "saves": {}, "stealth": -3, "attacks": [{"name": "pseudopod", "verb": "strikes", "to_hit": 5, "damage": 24, "type": "bludgeoning", "also": [{"damage": 18, "type": "acid"}]}]},
    'bugbear': {"ac": 16, "hp": 27, "initiative": 2, "grapple": 2, "saves": {}, "stealth": 6, "attacks": [{"name": "morningstar", "verb": "clubs", "to_hit": 4, "damage": 11, "type": "piercing"}]},
    'crocodile': {"ac": 12, "hp": 19, "initiative": 0, "grapple": 2, "saves": {}, "stealth": 2, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 7, "type": "piercing"}]},
    'cultist': {"ac": 12, "hp": 9, "initiative": 1, "grapple": 0, "saves": {}, "stealth": 1, "attacks": [{"name": "scimitar", "verb": "cuts", "to_hit": 3, "damage": 4, "type": "slashing"}]},
    'darkmantle': {"ac": 11, "hp": 22, "initiative": 1, "grapple": 3, "saves": {}, "stealth": 3, "attacks": [{"name": "crush", "verb": "strikes", "to_hit": 5, "damage": 6, "type": "bludgeoning"}]},
    'dire wolf': {"ac": 14, "hp": 37, "initiative": 2, "grapple": 3, "saves": {}, "stealth": 4, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 5, "damage": 10, "type": "piercing"}]},
    'drow': {"ac": 15, "hp": 13, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'duergar': {"ac": 16, "hp": 26, "initiative": 0, "grapple": 2, "saves": {}, "stealth": 0, "attacks": [{"name": "war pick", "verb": "bites", "to_hit": 4, "damage": 6, "type": "piercing"}]},
    'ettercap': {"ac": 13, "hp": 44, "initiative": 2, "grapple": 2, "saves": {}, "stealth": 4, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 10, "type": "piercing", "also": [{"damage": 4, "type": "poison"}]}, {"name": "claws", "verb": "claws", "to_hit": 4, "damage": 7, "type": "slashing"}]},
    'flying sword': {"ac": 17, "hp": 17, "initiative": 2, "grapple": 1, "saves": {"dex": 4}, "stealth": 2, "attacks": [{"name": "longsword", "verb": "cuts", "to_hit": 3, "damage": 5, "type": "slashing"}]},
    'gargoyle': {"ac": 15, "hp": 52, "initiative": 0, "grapple": 2, "saves": {}, "stealth": 0, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 5, "type": "piercing"}, {"name": "claws", "verb": "claws", "to_hit": 4, "damage": 5, "type": "slashing"}]},
    'gelatinous cube': {"ac": 6, "hp": 84, "initiative": -4, "grapple": 2, "saves": {}, "stealth": -4, "attacks": [{"name": "pseudopod", "verb": "strikes", "to_hit": 4, "damage": 10, "type": "acid"}]},
    'ghast': {"ac": 13, "hp": 36, "initiative": 3, "grapple": 3, "saves": {}, "stealth": 3, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 3, "damage": 12, "type": "piercing"}]},
    'ghost': {"ac": 11, "hp": 45, "initiative": 1, "grapple": -2, "saves": {}, "stealth": 1, "attacks": [{"name": "withering touch", "verb": "drains", "to_hit": 5, "damage": 17, "type": "necrotic"}]},
    'ghoul': {"ac": 12, "hp": 22, "initiative": 2, "grapple": 1, "saves": {}, "stealth": 2, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 2, "damage": 9, "type": "piercing"}]},
    'giant badger': {"ac": 10, "hp": 13, "initiative": 0, "grapple": 1, "saves": {}, "stealth": 0, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 3, "damage": 4, "type": "piercing"}, {"name": "claws", "verb": "claws", "to_hit": 3, "damage": 6, "type": "slashing"}]},
    'giant bat': {"ac": 13, "hp": 22, "initiative": 3, "grapple": 2, "saves": {}, "stealth": 3, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'giant frog': {"ac": 11, "hp": 18, "initiative": 1, "grapple": 1, "saves": {}, "stealth": 3, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 3, "damage": 4, "type": "piercing"}]},
    'giant poisonous snake': {"ac": 14, "hp": 11, "initiative": 4, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 6, "damage": 6, "type": "piercing", "save": {"ability": "con", "dc": 11, "damage": 10, "type": "poison", "half": True}}]},
    'giant rat': {"ac": 12, "hp": 7, "initiative": 2, "grapple": -2, "saves": {}, "stealth": 2, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 4, "type": "piercing"}]},
    'giant spider': {"ac": 14, "hp": 26, "initiative": 3, "grapple": 2, "saves": {}, "stealth": 7, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 5, "damage": 7, "type": "piercing", "save": {"ability": "con", "dc": 11, "damage": 9, "type": "poison", "half": True}}]},
    'giant toad': {"ac": 11, "hp": 39, "initiative": 1, "grapple": 2, "saves": {}, "stealth": 1, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 12, "type": "piercing", "also": [{"damage": 5, "type": "poison"}]}]},
    'giant wolf spider': {"ac": 13, "hp": 11, "initiative": 3, "grapple": 1, "saves": {}, "stealth": 7, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 3, "damage": 4, "type": "piercing", "save": {"ability": "con", "dc": 11, "damage": 7, "type": "poison", "half": True}}]},
    'gnoll': {"ac": 15, "hp": 22, "initiative": 1, "grapple": 2, "saves": {}, "stealth": 1, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 4, "type": "piercing"}]},
    'goblin': {"ac": 15, "hp": 7, "initiative": 2, "grapple": -1, "saves": {}, "stealth": 6, "attacks": [{"name": "scimitar", "verb": "cuts", "to_hit": 4, "damage": 5, "type": "slashing"}]},
    'gray ooze': {"ac": 8, "hp": 22, "initiative": -2, "grapple": 1, "saves": {}, "stealth": 2, "attacks": [{"name": "pseudopod", "verb": "strikes", "to_hit": 3, "damage": 11, "type": "bludgeoning", "also": [{"damage": 7, "type": "acid"}]}]},
    'hobgoblin': {"ac": 18, "hp": 11, "initiative": 1, "grapple": 1, "saves": {}, "stealth": 1, "attacks": [{"name": "longsword", "verb": "cuts", "to_hit": 3, "damage": 5, "type": "slashing"}]},
    'imp': {"ac": 13, "hp": 10, "initiative": 3, "grapple": -2, "saves": {}, "stealth": 5, "attacks": [{"name": "sting", "verb": "stings", "to_hit": 5, "damage": 5, "type": "piercing", "save": {"ability": "con", "dc": 11, "damage": 10, "type": "poison", "half": True}}]},
    'kobold': {"ac": 12, "hp": 5, "initiative": 2, "grapple": -2, "saves": {}, "stealth": 2, "attacks": [{"name": "dagger", "verb": "stabs", "to_hit": 4, "damage": 4, "type": "piercing"}]},
    'mage': {"ac": 12, "hp": 40, "initiative": 2, "grapple": -1, "saves": {"int": 6, "wis": 4}, "stealth": 2, "attacks": [{"name": "dagger", "verb": "stabs", "to_hit": 5, "damage": 4, "type": "piercing"}]},
    'mimic': {"ac": 12, "hp": 58, "initiative": 1, "grapple": 3, "saves": {}, "stealth": 5, "attacks": [{"name": "pseudopod", "verb": "strikes", "to_hit": 5, "damage": 7, "type": "bludgeoning"}]},
    'minotaur': {"ac": 14, "hp": 76, "initiative": 0, "grapple": 4, "saves": {}, "stealth": 0, "attacks": [{"name": "greataxe", "verb": "hacks at", "to_hit": 6, "damage": 17, "type": "slashing"}]},
    'mummy': {"ac": 11, "hp": 58, "initiative": -1, "grapple": 3, "saves": {"wis": 2}, "stealth": -1, "attacks": [{"name": "rotting fist", "verb": "pummels", "to_hit": 5, "damage": 20, "type": "bludgeoning", "also": [{"damage": 10, "type": "necrotic"}]}]},
    'ochre jelly': {"ac": 8, "hp": 45, "initiative": -2, "grapple": 2, "saves": {}, "stealth": -2, "attacks": [{"name": "pseudopod", "verb": "strikes", "to_hit": 4, "damage": 12, "type": "bludgeoning", "also": [{"damage": 3, "type": "acid"}]}]},
    'ogre': {"ac": 11, "hp": 59, "initiative": -1, "grapple": 4, "saves": {}, "stealth": -1, "attacks": [{"name": "greatclub", "verb": "clubs", "to_hit": 6, "damage": 13, "type": "bludgeoning"}]},
    'orc': {"ac": 13, "hp": 15, "initiative": 1, "grapple": 3, "saves": {}, "stealth": 1, "attacks": [{"name": "greataxe", "verb": "hacks at", "to_hit": 5, "damage": 9, "type": "slashing"}]},
    'owlbear': {"ac": 13, "hp": 59, "initiative": 1, "grapple": 5, "saves": {}, "stealth": 1, "attacks": [{"name": "beak", "verb": "bites", "to_hit": 7, "damage": 10, "type": "piercing"}, {"name": "claws", "verb": "claws", "to_hit": 7, "damage": 14, "type": "slashing"}]},
    'poisonous snake': {"ac": 13, "hp": 2, "initiative": 3, "grapple": -4, "saves": {}, "stealth": 3, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 5, "damage": 1, "type": "piercing", "save": {"ability": "con", "dc": 10, "damage": 5, "type": "poison", "half": True}}]},
    'priest': {"ac": 13, "hp": 27, "initiative": 0, "grapple": 0, "saves": {}, "stealth": 0, "attacks": [{"name": "mace", "verb": "clubs", "to_hit": 2, "damage": 3, "type": "bludgeoning"}]},
    'quasit': {"ac": 13, "hp": 7, "initiative": 3, "grapple": -3, "saves": {}, "stealth": 5, "attacks": [{"name": "claw", "verb": "claws", "to_hit": 4, "damage": 5, "type": "piercing", "save": {"ability": "con", "dc": 10, "damage": 5, "type": "poison", "half": False}}]},
    'rat': {"ac": 10, "hp": 1, "initiative": 0, "grapple": -4, "saves": {}, "stealth": 0, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 0, "damage": 1, "type": "piercing"}]},
    'rug of smothering': {"ac": 12, "hp": 33, "initiative": 2, "grapple": 3, "saves": {}, "stealth": 2, "attacks": [{"name": "smother", "verb": "strikes", "to_hit": 5, "damage": 10, "type": "bludgeoning"}]},
    'rust monster': {"ac": 14, "hp": 27, "initiative": 1, "grapple": 1, "saves": {}, "stealth": 1, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 3, "damage": 5, "type": "piercing"}]},
    'shadow': {"ac": 12, "hp": 16, "initiative": 2, "grapple": -2, "saves": {}, "stealth": 4, "attacks": [{"name": "strength drain", "verb": "drains", "to_hit": 4, "damage": 9, "type": "necrotic"}]},
    'shrieker': {"ac": 5, "hp": 13, "initiative": -5, "grapple": -5, "saves": {}, "stealth": -5, "attacks": [], "note": "no weapon attack in its SRD block (spells or special actions only)"},
    'skeleton': {"ac": 13, "hp": 13, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 2, "attacks": [{"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'specter': {"ac": 12, "hp": 22, "initiative": 2, "grapple": -5, "saves": {}, "stealth": 2, "attacks": [{"name": "life drain", "verb": "drains", "to_hit": 4, "damage": 10, "type": "necrotic"}]},
    'spy': {"ac": 12, "hp": 27, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}, {"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'stirge': {"ac": 14, "hp": 2, "initiative": 3, "grapple": -3, "saves": {}, "stealth": 3, "attacks": [{"name": "blood drain", "verb": "bites", "to_hit": 5, "damage": 5, "type": "piercing"}]},
    'swarm of bats': {"ac": 12, "hp": 22, "initiative": 2, "grapple": -3, "saves": {}, "stealth": 2, "attacks": [{"name": "bites", "verb": "bites", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'swarm of rats': {"ac": 10, "hp": 24, "initiative": 0, "grapple": -1, "saves": {}, "stealth": 0, "attacks": [{"name": "bites", "verb": "bites", "to_hit": 2, "damage": 7, "type": "piercing"}]},
    'troll': {"ac": 15, "hp": 84, "initiative": 1, "grapple": 4, "saves": {}, "stealth": 1, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 7, "damage": 7, "type": "piercing"}, {"name": "claw", "verb": "claws", "to_hit": 7, "damage": 11, "type": "slashing"}, {"name": "claw", "verb": "claws", "to_hit": 7, "damage": 11, "type": "slashing"}]},
    'violet fungus': {"ac": 5, "hp": 18, "initiative": -5, "grapple": -4, "saves": {}, "stealth": -5, "attacks": [{"name": "rotting touch", "verb": "drains", "to_hit": 2, "damage": 4, "type": "necrotic"}]},
    'wererat': {"ac": 12, "hp": 33, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 4, "type": "piercing"}]},
    'wererat human': {"ac": 12, "hp": 33, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}, {"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'wererat hybrid': {"ac": 12, "hp": 33, "initiative": 2, "grapple": 0, "saves": {}, "stealth": 4, "attacks": [{"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}, {"name": "shortsword", "verb": "stabs", "to_hit": 4, "damage": 5, "type": "piercing"}]},
    'wight': {"ac": 14, "hp": 45, "initiative": 2, "grapple": 2, "saves": {}, "stealth": 4, "attacks": [{"name": "longsword", "verb": "cuts", "to_hit": 4, "damage": 6, "type": "slashing"}, {"name": "longsword", "verb": "cuts", "to_hit": 4, "damage": 6, "type": "slashing"}]},
    "will-o'-wisp": {"ac": 19, "hp": 22, "initiative": 9, "grapple": -5, "saves": {}, "stealth": 9, "attacks": [{"name": "shock", "verb": "shocks", "to_hit": 4, "damage": 9, "type": "lightning"}]},
    'wolf': {"ac": 13, "hp": 11, "initiative": 2, "grapple": 1, "saves": {}, "stealth": 4, "attacks": [{"name": "bite", "verb": "bites", "to_hit": 4, "damage": 7, "type": "piercing"}]},
    'zombie': {"ac": 8, "hp": 22, "initiative": -2, "grapple": 1, "saves": {"wis": 0}, "stealth": -2, "attacks": [{"name": "slam", "verb": "slams", "to_hit": 3, "damage": 4, "type": "bludgeoning"}]},
}
for _name, _block in GENERATED.items():
    CREATURES.setdefault(_name, _block)

INLINE_KEYS = ('ac', 'hp', 'attacks')
OVERRIDES = ('ac', 'hp')  # an SRD reference may restate these with the book's own number


def stat_block(block):
    """The engine stat line for a room's ``stat_block`` (an SRD reference or inline), or None."""
    import copy
    if not isinstance(block, dict):
        return None
    if 'srd' in block:
        found = CREATURES.get(str(block['srd']).strip().casefold())
        if not found:
            return None
        found = copy.deepcopy(found)
        for key in OVERRIDES:
            if key in block:
                if type(block[key]) is not int or block[key] <= 0:
                    return None
                found[key] = block[key]
        return found
    if all(key in block for key in INLINE_KEYS) and type(block['ac']) is int and type(block['hp']) is int and \
            block['hp'] > 0 and isinstance(block['attacks'], list) and block['attacks'] and \
            all(isinstance(a, dict) and {'name', 'to_hit', 'damage'} <= set(a) for a in block['attacks']):
        return {'initiative': 0, 'grapple': 0, 'saves': {}, **copy.deepcopy(block),
                'attacks': [{'verb': 'strikes', 'type': 'bludgeoning', **a} for a in block['attacks']]}
    return None
