"""Claims and knowers (research/kit-aliveness/06-claim-and-knower-design.md). Room-agnostic.

A detail is not a string. It is a claim, and someone in the world holds it. Before a
detail is said, three questions: Source (adventure, canon, procedure, or Kit's choice
grown from a scene fact), Knower (who holds it, and how well), Motive (why this person
says it now: truth, lie, boast, bargain, hedge, or silence).

Brendon's rulings (2026-09-29), which this module implements:

- "Passive Perception is an AC against being snuck up on."
- "Passive Insight is an AC against an active Deception, and a shield against missing
  secrets."
- "Active skills are used when a player wants to do something that isn't automatically
  successful." The runtime never rolls a knowledge check on its own.
- Kit's asides tie to the PC's passive Insight: "the higher the Wisdom, the more she
  winks." Below the DC she stays in the narrator's band; at the DC she may point at where
  the tell is; at 5+ over she may name the kind of thing going on; she never names the
  secret.

Defaults: an NPC lie is a flat 10 + Deception against the PC's passive Insight, no
runtime roll; a concealment with no adventure DC is 10 + floor(dungeon floor level / 3).

Everything the PC side uses comes from whatever sheet is loaded (runtime/pc_sheet.py).
NPC numbers come from the actor's ``stats`` block in the room source (SRD 5.1 stat
blocks plus role fields). No model calls; deterministic Python.
"""
import re

from . import pc_sheet
from .state_context import require

SOURCES = ('adventure', 'canon', 'procedure', 'kit')
EXPOSURES = ('hidden', 'perceivable', 'public')
NPC_BANDS = ('knows', 'close', 'anchored', 'unaware')
PC_BANDS = ('learned', 'fingerprint', 'blind')
STANCES = ('truth', 'lie', 'boast', 'bargain', 'hedge', 'silence', 'guess', 'fingerprint', 'wink')
# What each band lets a speaker do with a claim.
BAND_STANCES = {
    'knows': ('truth', 'lie', 'boast', 'bargain', 'hedge', 'silence'),
    'close': ('hedge', 'guess', 'silence', 'bargain'),
    'anchored': ('truth', 'boast', 'hedge', 'bargain', 'silence'),  # sincere, and wrong
    'unaware': ('silence', 'guess'),
}
MOTIVE_STANCES = ('lie', 'bargain', 'boast')
WINK_TIERS = ('none', 'point', 'name_kind')
WINK_NAME_KIND_MARGIN = 5
SAID_LIMIT = 32
FIELD_MAX = 200
# Which ability works out a thing, and which skill sees through a person.
REASON_ABILITY = 'int'
_WORD = re.compile(r"[a-z0-9']+")
_SMALL = frozenset('a an the and or but of to in on at is it its this that with for from by as be '
                   'are was were he she they them his her their you your i me my we our so not no'.split())


def _words(text):
    return {w for w in _WORD.findall((text or '').casefold()) if len(w) >= 3 and w not in _SMALL}


def _mod(score):
    return (score - 10) // 2


# ---------------------------------------------------------------------------
# Profiles: NPC numbers from stats plus role; the PC's from the loaded sheet
# ---------------------------------------------------------------------------
def npc_profile(actor):
    """Passive numbers for one actor, from its ``stats`` block (SRD stat block + role)."""
    stats = actor.get('stats') or {}
    abilities = stats.get('abilities') or {key: 10 for key in pc_sheet.ABILITIES}
    skills = stats.get('skills') or {}
    prof = stats.get('proficiency_bonus', 2)

    def bonus(skill):
        return skills.get(skill, _mod(abilities[pc_sheet.SKILLS[skill]]))
    return {'insight': 10 + bonus('insight'), 'perception': 10 + bonus('perception'),
            'int': _mod(abilities['int']), 'wis': _mod(abilities['wis']), 'cha': _mod(abilities['cha']),
            'deception': bonus('deception'), 'sleight_of_hand': bonus('sleight_of_hand'),
            'stealth': bonus('stealth'), 'proficiency_bonus': prof,
            'domains': list(stats.get('domains') or []), 'special': list(stats.get('special') or []),
            'wants': actor.get('motive', '')}



def current_floor_level(source, area=None):
    """Return the dungeon floor for an area, defaulting to floor 1.

    Area data may carry ``floor_level``; a fixture-level value is the fallback for
    sources whose areas share one floor.
    """
    area_data = ((source or {}).get('areas') or {}).get(area, {}) if area else {}
    level = area_data.get('floor_level', (source or {}).get('floor_level', 1))
    return level if type(level) is int and level >= 1 else 1


def claim_dc(claim, actors, floor_level=1):
    """The adventure's DC, else 10 + floor(dungeon floor level / 3)."""
    if type(claim.get('dc')) is int:
        return claim['dc']
    return 10 + floor_level // 3


# ---------------------------------------------------------------------------
# Compile at init
# ---------------------------------------------------------------------------
def compile_claims(source):
    """Claims from the room source's ``claims`` block, checked. Keyed by the thing."""
    claims = {}
    for key, claim in ((source or {}).get('claims') or {}).items():
        if key.startswith('_'):
            continue
        require(claim.get('source') in SOURCES, f'Claim {key}: unknown source')
        require(claim.get('exposure') in EXPOSURES, f'Claim {key}: unknown exposure')
        require(isinstance(claim.get('about'), str) and '/' in claim['about'],
                f'Claim {key}: about reads "<kind>:<thing>/<facet>"')
        require(claim.get('roots') and all(r in source['facts'] or r.split(':', 1)[-1] in source.get('actors', {})
                                           for r in claim['roots']),
                f'Claim {key}: roots must cite source facts or actors')
        if claim.get('fact'):
            require(claim['fact'] in source['facts'], f'Claim {key}: unknown fact')
        for holder, band in (claim.get('holders') or {}).items():
            require(holder in source.get('actors', {}) and band in NPC_BANDS,
                    f'Claim {key}: holder {holder} needs a live actor and a band')
        require(claim.get('pc_check') in pc_sheet.SKILLS,
                f'Claim {key}: pc_check names the skill that finds it')
        require(claim.get('pc_access') in ('passive', 'roll'),
                f'Claim {key}: pc_access is passive (a shield: Insight/Perception) or roll (player-initiated)')
        claims[key] = claim
    return claims


# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------
def npc_band(claim, actor_id, actors, area=None, floor_level=1):
    actor = actors.get(actor_id) or {}
    if area and actor.get('location') != area:
        return 'unaware'
    listed = (claim.get('holders') or {}).get(actor_id)
    if listed:
        return listed
    profile = npc_profile(actor)
    if set(profile['special']) & set(claim.get('granted_by') or ()):
        return 'knows'  # e.g. Read Thoughts (open question: passive, or only when used)
    ability = claim.get('npc_check', 'insight')
    score = profile['insight'] if ability == 'insight' else 10 + profile[REASON_ABILITY]
    if set(profile['domains']) & set(claim.get('domains') or ()):
        score += profile['proficiency_bonus']
    short = claim_dc(claim, actors, floor_level) - score
    if short <= 0:
        return 'knows'
    return 'close' if short <= 4 else 'anchored'


def pc_band(claim_id, claim, sheet, state, floor_level=1):
    """learned (a player roll succeeded or it came out in play), fingerprint (the PC's
    passive meets the concealer's DC; passive access only), else blind."""
    learned = set(state.get('known_facts') or []) | set((state.get('claims') or {}).get('learned') or [])
    if claim_id in learned or (claim.get('fact') and claim['fact'] in learned):
        return 'learned'
    if claim.get('exposure') != 'hidden':
        return 'learned'
    if sheet and claim.get('pc_access') == 'passive' and \
            pc_sheet.passive(sheet, claim['pc_check']) >= claim_dc(claim, state.get('actors', {}), floor_level):
        return 'fingerprint'
    return 'blind'


def wink_tier(claim, sheet, actors, band, floor_level=1):
    """How far Kit may hint: none below the DC, point at the DC, name_kind at 5+ over.
    Keyed to the PC's passive Insight for people's secrets, or the claim's passive skill."""
    if not sheet or band == 'blind' or claim.get('pc_access') != 'passive':
        return 'none'
    margin = pc_sheet.passive(sheet, claim['pc_check']) - claim_dc(claim, actors, floor_level)
    if margin < 0:
        return 'none'
    return 'name_kind' if margin >= WINK_NAME_KIND_MARGIN else 'point'


def lie_lands(speaker_profile, sheet):
    """An NPC lie: flat 10 + Deception (open default) against passive Insight as AC.
    Meets or beats it: the lie lands. Short: the narrator gets a fingerprint of the lie."""
    attack = 10 + speaker_profile['deception']
    defence = pc_sheet.passive(sheet, 'insight') if sheet else 10
    return {'deception': attack, 'passive_insight': defence, 'lands': attack >= defence}


# ---------------------------------------------------------------------------
# prepare: claims_here
# ---------------------------------------------------------------------------
def claims_here(source, state, sheet):
    """Every claim in this area with each present NPC's band, the PC's band, and the
    wink tier. The narrator's band is exactly the PC's band."""
    claims = compile_claims(source)
    area = state['area']
    actors = state.get('actors') or {}
    level = current_floor_level(source, area)
    present = [key for key, actor in actors.items() if actor.get('location') == area and actor.get('status') != 'fled']
    out = {}
    for key, claim in claims.items():
        fact = source['facts'].get(claim.get('fact') or '', {})
        if fact and fact.get('area') != area:
            continue
        band = pc_band(key, claim, sheet, state, level)
        entry = {'about': claim['about'], 'truth': claim['truth'], 'source': claim['source'],
                 'dc': claim_dc(claim, actors, level), 'pc_band': band,
                 'wink': wink_tier(claim, sheet, actors, band, level),
                 'npc_bands': {actor: npc_band(claim, actor, actors, area, level) for actor in present}}
        if band == 'fingerprint' and claim.get('fingerprint'):
            entry['fingerprint'] = claim['fingerprint']
        if claim.get('anchored_version'):
            entry['anchored_version'] = claim['anchored_version']
        if claim.get('pc_access') == 'roll':
            entry['player_roll'] = f"{claim['pc_check']} DC {entry['dc']}, only when the player asks"
        out[key] = entry
    lies = {actor: lie_lands(npc_profile(actors[actor]), sheet) for actor in present}
    return {'pc': pc_sheet.private_summary(sheet) if sheet else None, 'claims': out,
            'npc_lies_vs_passive_insight': lies,
            'said': (state.get('claims') or {}).get('said', [])[-8:]}


# ---------------------------------------------------------------------------
# decide: the claims block
# ---------------------------------------------------------------------------
_LINE = {'type': 'string'}
CLAIMS_SCHEMA = {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False,
    'properties': {'claim': _LINE,        # a claims_here id, or "new"
                   'about': _LINE, 'truth': _LINE, 'roots': {'type': 'array', 'items': _LINE},
                   'holder': _LINE,       # new Kit claims: who holds it
                   'speaker': _LINE,      # actor id, narrator, or kit
                   'stance': {'type': 'string', 'enum': list(STANCES)},
                   'version': _LINE,      # what the speaker says (never the stance)
                   'why': _LINE},         # the speaker's want that makes them say it
    'required': ['claim', 'about', 'truth', 'roots', 'holder', 'speaker', 'stance', 'version', 'why']}}
MAX_CLAIMS = 4


def check_claims(items, packet, source, state):
    """Structure only: source and roots exist; the speaker's band permits the stance;
    every lie, boast, or bargain cites the speaker's want; narrator and Kit stay inside
    the PC's band and wink tier."""
    require(isinstance(items, list) and len(items) <= MAX_CLAIMS, f'claims: at most {MAX_CLAIMS} entries')
    here = (packet or {}).get('claims') or {}
    actors = state.get('actors') or {}
    for item in items:
        require(isinstance(item, dict) and set(item) == set(CLAIMS_SCHEMA['items']['required']),
                'Each claim needs ' + ', '.join(CLAIMS_SCHEMA['items']['required']))
        for key in ('claim', 'speaker', 'stance', 'version', 'why'):
            require(isinstance(item[key], str) and item[key].strip() and len(item[key]) <= FIELD_MAX,
                    f'claim {key} must be 1-{FIELD_MAX} characters')
        require(item['stance'] in STANCES, f'Unknown stance {item["stance"]!r}')
        speaker = item['speaker'].strip()
        if item['claim'] == 'new':
            # Kit's choice: grown from a scene fact, held by someone, written once.
            require(isinstance(item['roots'], list) and item['roots'] and
                    all(r in source.get('facts', {}) or r in (state.get('canon') or {}) or
                        r.split(':', 1)[-1] in actors for r in item['roots']),
                    'A new claim with no source is nonsense: roots must cite scene facts, canon, or actors')
            require(item['holder'] in actors or item['holder'] == 'room',
                    'A new claim names a holder in the scene (an actor id, or room for what anyone can see)')
            require(item['truth'].strip() and item['about'].strip(), 'A new claim states about and truth')
            band = 'knows' if speaker == item['holder'] else None
            pc = 'learned' if item['holder'] == 'room' else 'blind'
            wink = 'none'
        else:
            require(item['claim'] in here, f'Unknown claim {item["claim"]!r}; use a claims_here id or "new"')
            entry = here[item['claim']]
            band = entry['npc_bands'].get(speaker)
            pc, wink = entry['pc_band'], entry['wink']
        if speaker == 'narrator':
            allowed = {'learned': ('truth',), 'fingerprint': ('fingerprint',), 'blind': ()}[pc]
            require(item['stance'] in allowed,
                    f'The narrator knows only what the player character has earned: this claim is '
                    f'{pc} for them' + (', so show only its fingerprint (deniable evidence, never the label)'
                                        if pc == 'fingerprint' else '') + '.')
            continue
        if speaker == 'kit':
            require(item['stance'] == 'wink' and wink != 'none',
                    'Kit\'s asides hint only as far as the wink tier allows (none here)')
            continue
        require(speaker in actors, f'Unknown speaker {speaker!r}: an actor id, narrator, or kit')
        band = band or 'unaware'
        require(item['stance'] in BAND_STANCES[band],
                f'{speaker} is {band} on this claim: they may {", ".join(BAND_STANCES[band])}')
        if band == 'anchored' and item['claim'] != 'new':
            require(_words(item['version']) - _words(here[item['claim']]['truth']),
                    'An anchored speaker says their wrong version, grown from the obvious feature')
        if item['stance'] in MOTIVE_STANCES:
            wants = _words(npc_profile(actors[speaker])['wants']) | _words(actors[speaker].get('immediate_goal'))
            require(len(item['why'].split()) >= 4 and _words(item['why']) & wants,
                    f'A {item["stance"]} needs a why that cites {speaker}\'s want')


def said_events(items, turn_id, packet, state):
    """Public history with a private stance, so a lie can be caught later."""
    events = []
    actors = state.get('actors') or {}
    sheet = state.get('player_sheet')
    for item in items or ():
        if item['speaker'] in ('narrator', 'kit') or item['stance'] == 'silence':
            continue
        record = {'claim': item['claim'], 'by': item['speaker'], 'to': 'pc', 'version': item['version'],
                  'stance': item['stance'], 'why': item['why'], 'turn': turn_id}
        if item['stance'] == 'lie' and item['speaker'] in actors:
            contest = lie_lands(npc_profile(actors[item['speaker']]), sheet)
            record['contest'] = contest
        if item['claim'] == 'new':
            record['new'] = {'about': item['about'], 'truth': item['truth'], 'roots': item['roots'],
                             'holder': item['holder']}
        events.append({'type': 'claim_said', 'said': record,
                       'evidence': f'Claim said with turn {turn_id}.'})
    return events


def planned_amounts(items, speaker_labels):
    """{public speaker label: set of (amount, unit)} for versions the decision planned."""
    from . import kit_guards
    found = {}
    for item in items or ():
        label = speaker_labels.get(item['speaker'], item['speaker'].capitalize())
        found.setdefault(label, set()).update(kit_guards.spoken_amounts(item['version']))
    return found


# ---------------------------------------------------------------------------
# Player-initiated knowledge rolls
# ---------------------------------------------------------------------------
_RECALL = re.compile(r"\b(appraise|apprais\w+|history|recall|remember|know (?:about|anything)|"
                     r"what do i know|identify|arcana|study the)\b")


def roll_target(action, source):
    """(claim id, claim) a player's knowledge roll is aimed at, or None."""
    text = (action or '').casefold()
    if not _RECALL.search(text):
        return None
    for key, claim in compile_claims(source).items():
        if claim.get('pc_access') == 'roll' and any(re.search(rf"\b{re.escape(w)}\b", text)
                                                     for w in claim.get('subject_words') or ()):
            return key, claim
    return None
