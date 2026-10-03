"""Claims and knowers (docs/architecture/kit-claims-knowers.md). Room-agnostic.

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
runtime roll (the PC rolls Insight against that same number only when the player asks);
an NPC who actively hides something brings a flat 10 + their concealing skill; any other
check the source gives no DC is 10 + floor(dungeon floor level / 3). A PC whose passive
meets the number succeeds without a roll.

Everything the PC side uses comes from whatever sheet is loaded (runtime/pc_sheet.py).
NPC numbers come from the actor's ``stats`` block in the room source (SRD 5.1 stat
blocks plus role fields). No model calls; deterministic Python.
"""
import re

from . import pc_sheet
from .state_context import normalize_fact, require

SOURCES = ('adventure', 'canon', 'procedure', 'kit')
EXPOSURES = ('hidden', 'perceivable', 'public')
NPC_BANDS = ('knows', 'close', 'anchored', 'unaware')
STANCES = ('truth', 'lie', 'boast', 'bargain', 'hedge', 'silence', 'guess', 'fingerprint', 'wink')
# What each band lets a speaker do with a claim.
BAND_STANCES = {
    'knows': ('truth', 'lie', 'boast', 'bargain', 'hedge', 'silence'),
    'close': ('hedge', 'guess', 'silence', 'bargain'),
    'anchored': ('truth', 'boast', 'hedge', 'bargain', 'silence'),  # sincere, and wrong
    'unaware': ('silence', 'guess'),
}
MOTIVE_STANCES = ('lie', 'bargain', 'boast')
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


def default_dc(floor_level=1):
    """Brendon's rule for any check the source gives no DC: 10 + floor(floor level / 3).

    Settled (decided more than once; see docs/collab/BOARD.md, "Settled rules"): when the
    source names no DC, Kit sets it at DM discretion and this is the baseline. It is not
    an open decision; never raise an unnamed DC to Brendon as a question."""
    return 10 + floor_level // 3


def npc_skill(actor, skill):
    """An NPC's bonus in any skill: the stat block's printed skill, else the ability modifier."""
    stats = (actor or {}).get('stats') or {}
    abilities = stats.get('abilities') or {key: 10 for key in pc_sheet.ABILITIES}
    return (stats.get('skills') or {}).get(skill, _mod(abilities[pc_sheet.SKILLS[skill]]))


def npc_passive(actor, skill):
    """Flat 10 + skill: the number an NPC brings to any opposed check (no NPC dice)."""
    return 10 + npc_skill(actor, skill)


def claim_dc(claim, actors, floor_level=1):
    """One number per secret, used by every path (passive shield, active look, card table):

    1. the adventure's DC (``dc``);
    2. else, when an NPC actively hides it (``concealer`` + ``conceal_skill``), that NPC's
       flat 10 + skill, because NPCs never roll in opposed checks;
    3. else the default for any check the source gives no DC: 10 + floor(floor level / 3).
    """
    if type(claim.get('dc')) is int:
        return claim['dc']
    concealer = (actors or {}).get(claim.get('concealer') or '')
    if concealer and claim.get('conceal_skill') in pc_sheet.SKILLS:
        return npc_passive(concealer, claim['conceal_skill'])
    return default_dc(floor_level)


def pc_check(dc, modifier, passive_score, roll):
    """Brendon's rulings for any PC check against a fixed number (a DC or an NPC's flat
    10 + skill): when the PC's relevant passive already meets it, the result is automatic
    and nothing is rolled; otherwise the PC rolls d20 + modifier and meeting the number
    succeeds (5e: meet or beat). ``roll`` is only called when a roll is needed."""
    if passive_score is not None and passive_score >= dc:
        return {'auto': True, 'passive': passive_score, 'dc': dc, 'total': passive_score, 'success': True}
    die = roll()
    # A stated Avrae total is worked back with the sheet's bonus, so the "die" can sit
    # outside 1-20 when the table added something the sheet lacks (Bless, Guidance).
    require(type(die) is int, 'Invalid d20 roll')
    total = die + modifier
    return {'auto': False, 'die': die, 'modifier': modifier, 'dc': dc, 'total': total, 'success': total >= dc}


def check_evidence(skill, result):
    """The numbers behind a check, for the ledger only. Public text never carries a DC, a
    total, or a modifier (Brendon's table call 4, 2026-10-02): a success is told as what
    the character notices, a failure as what they don't."""
    name = skill.replace('_', ' ').title()
    if result['auto']:
        return f'passive {name} {result["passive"]} meets DC {result["dc"]}; no roll'
    return f'{name} d20 {result["die"]} + {result["modifier"]} = {result["total"]} vs DC {result["dc"]}'


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
        if claim.get('numeric_fact'):
            require(claim['numeric_fact'] in (source.get('numeric_facts') or {}),
                    f'Claim {key}: unknown numeric fact')
        for holder, band in (claim.get('holders') or {}).items():
            require(holder in source.get('actors', {}) and band in NPC_BANDS,
                    f'Claim {key}: holder {holder} needs a live actor and a band')
        require(claim.get('pc_check') in pc_sheet.SKILLS,
                f'Claim {key}: pc_check names the skill that finds it')
        if 'pc_checks' in claim:
            require(isinstance(claim['pc_checks'], list) and claim['pc_check'] in claim['pc_checks'] and
                    all(skill in pc_sheet.SKILLS for skill in claim['pc_checks']),
                    f'Claim {key}: pc_checks lists every skill that finds it, pc_check among them')
        for tier in claim.get('perception_details') or ():
            require(isinstance(tier, dict) and tier.get('fact') in source['facts'] and
                    type(tier.get('min_margin', 0)) is int,
                    f'Claim {key}: each perception detail names a source fact and an integer min_margin')
        require(claim.get('pc_access') in ('passive', 'roll'),
                f'Claim {key}: pc_access is passive (a shield: Insight/Perception) or roll (player-initiated)')
        claims[key] = claim
    return claims


def established_claims(state):
    """Durable definitions, with a fallback for pre-fix snapshots' said records."""
    claims = state.get('claims') or {}
    established = dict(claims.get('established') or {})
    for record in claims.get('said') or ():
        if record.get('claim') == 'new' and record.get('new'):
            definition = record['new']
            established.setdefault(definition['about'].strip().casefold(), definition)
    return established


def check_new_definition(definition, established):
    """A subject's first committed truth is immutable, including within one batch."""
    for key in ('about', 'truth'):
        value = definition.get(key)
        require(isinstance(value, str) and 0 < len(value.strip()) <= FIELD_MAX,
                f'A new claim {key} must be 1-{FIELD_MAX} characters')
    subject = definition['about'].strip().casefold()
    require('/' in subject, 'A new claim about reads "<kind>:<thing>/<facet>"')
    prior = established.get(subject)
    require(prior is None or normalize_fact(prior['truth']) == normalize_fact(definition['truth']),
            f'Claim {subject} is already established; its truth cannot be redefined')
    return subject


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

    Brendon's ruling: "the higher the Wisdom, the more she winks." The margin is always
    the PC's passive Insight against the claim's DC, whatever skill finds the claim
    itself (the deck's Perception decides the fingerprint, not the wink)."""
    if not sheet or band == 'blind' or claim.get('pc_access') != 'passive':
        return 'none'
    margin = pc_sheet.passive(sheet, 'insight') - claim_dc(claim, actors, floor_level)
    if margin < 0:
        return 'none'
    return 'name_kind' if margin >= WINK_NAME_KIND_MARGIN else 'point'


def lie_dc(speaker_profile):
    """The one number for an NPC's lie: flat 10 + Deception. The PC's passive Insight meets
    it (the lie fails and the narrator gets its fingerprint), or the PC's active Insight
    roll, when the player asks, has to meet it."""
    return 10 + speaker_profile['deception']


def lie_lands(speaker_profile, sheet):
    """An NPC lie: flat 10 + Deception (open default) against passive Insight as AC.
    Meets or beats it: the lie lands. Short: the narrator gets a fingerprint of the lie."""
    attack = lie_dc(speaker_profile)
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
    # Passives use the PC as they stand now: the player's word, else the situation's default.
    situation = pc_sheet.situation_of(state)
    raw, sheet = sheet, pc_sheet.situated(sheet, situation)
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
    packet = {'pc': pc_sheet.private_summary(raw, situation) if raw else None, 'claims': out,
              'npc_lies_vs_passive_insight': lies,
              'said': (state.get('claims') or {}).get('said', [])[-8:]}
    established = established_claims(state)
    if established:
        packet['established'] = established
    return packet


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
    established = established_claims(state)
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
            subject = check_new_definition(item, established)
            established.setdefault(subject, item)
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
    sheet = pc_sheet.sheet_now(state)
    for item in items or ():
        if item['stance'] == 'silence' or (item['speaker'] in ('narrator', 'kit') and item['claim'] != 'new'):
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
    """Amounts keyed by speaker AND claim, retaining currency and excluding silence."""
    from . import kit_guards
    found = {}
    for item in items or ():
        if item['stance'] == 'silence':
            continue
        label = speaker_labels.get(item['speaker'], item['speaker'].capitalize())
        found.setdefault(label, {}).setdefault(item['claim'], set()).update(
            kit_guards.spoken_amounts(item['version']))
    return found


# ---------------------------------------------------------------------------
# Player-initiated knowledge rolls
# ---------------------------------------------------------------------------
_RECALL = re.compile(r"\b(appraise|apprais\w+|history|recall|remember|know (?:about|anything)|"
                     r"what do i know|identify|arcana|study the)\b")


# Skills that find something in front of the PC (a look, a read) rather than recall it.
OBSERVATION_SKILLS = ('perception', 'insight', 'investigation')


def _mentions(text, claim):
    return any(re.search(rf"\b{re.escape(w.casefold())}\b", text) for w in claim.get('subject_words') or ())


def roll_target(action, source):
    """(claim id, claim) a player's knowledge roll (History, Arcana...) is aimed at, or None."""
    text = (action or '').casefold()
    if not _RECALL.search(text):
        return None
    for key, claim in compile_claims(source).items():
        if claim.get('pc_access') == 'roll' and claim['pc_check'] not in OBSERVATION_SKILLS and \
                _mentions(text, claim):
            return key, claim
    return None


# A plain look ("I look at the fresco", "I look around") is free description, never a check
# (Brendon's table call 2): only a searching look qualifies.
_LOOK = re.compile(r"\b(look(?:s|ed|ing)? (?:for|closely|closer|carefully|hard|over|under|behind|into|through|"
                   r"for anything|again)|(?:close|careful|closer|hard) look|search\w*|inspect\w*|examin\w*|stud(?:y|ies|ying)|check\w*|peer\w*|"
                   r"scrutini[sz]\w*|insight|perception|investigat\w*|notice|watch\w*|"
                   r"see (?:if|whether|through)|tell (?:if|whether)|are they|is he|is she)\b")


def claim_skills(claim):
    """Every skill that can find this claim: ``pc_checks`` when listed, else ``pc_check``."""
    return tuple(claim.get('pc_checks') or (claim['pc_check'],))


# Brendon's skill rule (2026-10-03): a player may use any skill, but each skill gates what it
# reveals. Perception notices what is there; Investigation deduces from physical clues;
# Insight (Wisdom) reads motive and the why. A named skill wins; else the verb implies one.
_SKILL_NAMED = (('insight', re.compile(r'\binsight\b')),
                ('investigation', re.compile(r'\binvestigation\b')),
                ('perception', re.compile(r'\bperception\b')))
_SKILL_IMPLIED = (
    ('insight', re.compile(r"\b(?:motives?|why (?:they|he|she|would)|what (?:they|he|she)(?:'re| are|'s| is) "
                           r"(?:after|really after|up to)|what (?:they|he|she) wants?|read(?:s|ing)? (?:him|her|them|"
                           r"the (?:dealer|players?|table|room|group))|sense (?:his|her|their))\b")),
    ('investigation', re.compile(r"\b(?:investigat\w*|examin\w*|inspect\w*|search\w*|deduc\w*|clues?|"
                                 r"work out|figure out|piece together)\b")),
    ('perception', re.compile(r"\b(?:notic\w*|spot\w*|peer\w*|look(?:s|ed|ing)? (?:closely|closer|carefully|hard|"
                              r"for|over)|(?:close|careful|closer|hard) look)\b")),
)


def chosen_skill(action, implied=True):
    """The observation skill the player chose for a look or a read, or None: a stated roll
    in Perception, Insight, or Investigation (Avrae's "makes an Insight check!"), else the
    skill they name, else (with ``implied``) the one their verb implies. Only a stated or
    named skill gates a reveal; an implied one only picks which claim a look is aimed at."""
    from . import kit_rolls
    stated = kit_rolls.stated_skill(action or '')
    if stated in OBSERVATION_SKILLS:
        return stated
    text = kit_rolls.without_rolls(action or '')
    # The skill named first, skipping the one being swapped out ("Investigation instead of
    # Perception", "rather than Insight").
    named = sorted((match.start(), skill) for skill, pattern in _SKILL_NAMED for match in pattern.finditer(text)
                   if not re.search(r'\b(?:instead of|rather than|not)\s+(?:my\s+|a\s+|an\s+)?$',
                                    text[max(0, match.start() - 16):match.start()]))
    if named:
        return named[0][1]
    for skill, pattern in _SKILL_IMPLIED if implied else ():
        if pattern.search(text):
            return skill
    return None


def perception_details(claim, margin):
    """The observed details an active Perception check sees on this claim at ``margin`` over
    its DC, as fact ids, or None when the claim lists none. Brendon's rule: Perception is a
    snapshot (details without context, more and sharper with the result, each a hook for
    an Investigation or Insight follow-up); it never yields the claim's conclusion."""
    tiers = claim.get('perception_details')
    if not tiers:
        return None
    return [tier['fact'] for tier in sorted(tiers, key=lambda t: t.get('min_margin', 0))
            if margin >= tier.get('min_margin', 0)]


def gated_claim(source, state, claim_id, claim, skill):
    """(id, claim) this skill can reveal about the same thing as ``claim``: the claim itself
    when the skill finds it, else a hidden sibling here that the skill finds and that is
    linked to it (one cites the other's fact in its roots). None when this skill reveals
    nothing about it."""
    if skill is None or skill in claim_skills(claim):
        return claim_id, claim
    area = (state or {}).get('area')
    learned = set((state or {}).get('known_facts') or []) | set(((state or {}).get('claims') or {}).get('learned') or [])
    for key, other in compile_claims(source).items():
        if key == claim_id or other.get('exposure') != 'hidden' or skill not in claim_skills(other):
            continue
        fact = (source.get('facts') or {}).get(other.get('fact') or '', {})
        if area and fact and fact.get('area') != area:
            continue
        linked = (claim.get('fact') and claim['fact'] in (other.get('roots') or ())) or \
            (other.get('fact') and other['fact'] in (claim.get('roots') or ()))
        if linked and key not in learned and other.get('fact') not in learned:
            return key, other
    return None


def check_target(action, source, state=None):
    """(claim id, claim) an active look or read is aimed at, by the claim's own subject
    words, or None. Only hidden claims found by observation (Perception, Insight,
    Investigation) qualify; what the check can reveal is exactly that claim, never another.
    When the player chose a skill, a claim that skill finds comes first (each skill gates
    what it reveals; ``gated_claim`` settles a skill that finds none of them)."""
    text = (action or '').casefold()
    if not _LOOK.search(text):
        return None
    area = (state or {}).get('area')
    found = []
    for key, claim in compile_claims(source).items():
        fact = (source.get('facts') or {}).get(claim.get('fact') or '', {})
        if area and fact and fact.get('area') != area:
            continue
        if claim.get('exposure') == 'hidden' and set(claim_skills(claim)) & set(OBSERVATION_SKILLS) and \
                _mentions(text, claim):
            found.append((key, claim))
    if not found:
        return None
    skill = chosen_skill(action)
    for key, claim in found:
        if skill in claim_skills(claim):
            return key, claim
    return found[0]


_LIE_WORDS = re.compile(r"\b(lying|lie|lies|lied|liar|truth\w*|honest\w*|sincere\w*|straight with|"
                        r"mean(?:s)? it|level(?:ing)? with|bullshit\w*|deceiv\w*|decept\w*)\b")
_READ_WORDS = re.compile(r"\b(insight|read|reading|sense|tell|judge|gauge|study|studying|watch|watching|"
                         r"whether|if|is he|is she|are they|are you)\b")


def is_lie_read(action):
    """An Insight read on whether someone is lying (unquoted narration only)."""
    text = (action or '').casefold()
    return bool(_LIE_WORDS.search(text) and _READ_WORDS.search(text))
