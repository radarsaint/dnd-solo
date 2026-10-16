"""Advisory BFDM judgments for the private decision input.

``prepare_inputs`` calls ``select`` with the room source, the live state, and the
resolution kind. It does not read the player sentence. PR #122 is the combat-act
parser; this module does not add another one.

A card is attached only when ``_judgment`` on the source and the live sheet,
claim holders, or resolution kind establish that record's situation. Otherwise
the key is omitted. Every card is advisory. None of them overrule the state or
the player's choice.

The text of the corpus stays in radarsaint/bfdm-corpus. This module pins the
record ids, statuses, and evidence locators checked at ``CORPUS_COMMIT``.
No network fetch.
"""

from . import kit_reactions

CORPUS_REPO = 'radarsaint/bfdm-corpus'
CORPUS_COMMIT = 'bf56ca4f9b0f4b410b37c5601a6e49b33627eecb'
CORPUS_PATH = 'research/longitudinal/bounded-judgment-tranche-2026-10-15.jsonl'

RULE = ('Advisory historical records for a situation the live state already '
        'establishes. They do not overrule that state or the player\'s choice, '
        'and they are not standing practices. Do not narrate them.')

# Status and evidence locators must match the pinned JSONL. The advisory is the
# runtime wording and is not allowed to be stronger than that record.
RECORDS = {
    'BJ-001': {
        'status': 'VERIFIED_NARROW',
        'evidence': ['discord:865565663296225280', 'discord:865565818481279018',
                     'discord:865565932783796255', 'discord:865566464831258674',
                     'discord:865567436970786836'],
        'advisory': ('Unscheduled damage is in the room data and this turn is already a '
                     'physical act. One 2021 exchange allowed an unplanned repair and waited '
                     'for the player to carry it out. Do not write the outcome.'),
        'does_not': 'It does not remove a designed constraint, and it does not decide success.',
    },
    'BJ-002': {
        'status': 'VERIFIED_NARROW',
        'evidence': ['discord:863492563784040539'],
        'advisory': ('A constraint is still in force and the room data already has an exception '
                     'open. One 2021 refusal kept a designed vulnerability rather than grant a '
                     'private exception. The player still chooses.'),
        'does_not': 'It is not an automatic denial, and it does not fire because of wording.',
    },
    'BJ-003': {
        'status': 'VERIFIED_NARROW',
        'evidence': ['discord:744056939096571924'],
        'advisory': ('The room data says this resolution already stood. One 2020 correction '
                     'changed a resurrection rule going forward and left that night\'s '
                     'resurrections in place.'),
        'does_not': 'It is not a policy for every failed rule, and it does not erase the past.',
    },
    'BJ-004': {
        'status': 'NARROWED',
        'evidence': ['discord:746253583552479272', 'discord:746253900490735686',
                     'discord:746254025883779113', 'discord:746254092011175968',
                     'discord:746254154774872094'],
        'advisory_below': ('Live party resources are below the assumption written on this '
                           'prepared encounter. In one 2020 window a depletion guess was '
                           'corrected by the players, and the encounter that followed is not '
                           'in the record.'),
        'advisory_meets': ('Live party resources meet the assumption written on this prepared '
                           'encounter. A depletion guess in one 2020 window was not the table. '
                           'The encounter that followed is not in the record.'),
        'does_not': 'It does not order the encounter played, skipped, or replaced.',
    },
    'BJ-005': {
        'status': 'VERIFIED_NARROW',
        'evidence': ['bcs:BCS-000172'],
        'advisory': ('The room data names a fact this present NPC does not hold. One draft '
                     'correction refused to give an NPC a name the players had not said. '
                     'The log is not a play transcript.'),
        'does_not': 'It does not prove a replacement scene was run, and it does not speak for the player.',
    },
}


def party_ready(sheet, assumes):
    """True, False, or None when the sheet cannot establish the assumption."""
    if not isinstance(sheet, dict) or not isinstance(assumes, dict) or not assumes:
        return None
    seen = False
    ready = True
    if 'min_hp' in assumes:
        hp = sheet.get('hp')
        if type(hp) is not int:
            return None
        seen = True
        if hp < assumes['min_hp']:
            ready = False
    if 'min_slots_remaining' in assumes:
        counted = kit_reactions.slots(sheet)
        if not counted:
            return None
        remaining = sum(item['max'] - item['used'] for item in counted.values())
        seen = True
        if remaining < assumes['min_slots_remaining']:
            ready = False
    return ready if seen else None


def _block(source):
    block = (source or {}).get('_judgment')
    return block if isinstance(block, dict) else {}


def _view(record_id, relevance, advisory):
    record = RECORDS[record_id]
    return {
        'id': record_id,
        'record': record_id,
        'status': record['status'],
        'relevance': relevance,
        'binding': False,
        'advisory': advisory,
        'does_not': record['does_not'],
        'evidence': list(record['evidence']),
        'corpus_commit': CORPUS_COMMIT,
        'corpus_path': CORPUS_PATH,
    }


def select(source, state, kind='play'):
    """The private advisory packet, or None. ``state`` and ``source`` decide. The
    player sentence is not an argument."""
    if kind == 'opening' or not isinstance(state, dict):
        return None
    block = _block(source)
    if not block:
        return None
    area = state.get('area')
    applied = []

    for item in block.get('constraints') or ():
        if not isinstance(item, dict) or item.get('area') != area or item.get('exception_open') is not True:
            continue
        waived = state.get('judgment_waived') or ()
        if item.get('id') in waived:
            continue
        applied.append(_view('BJ-002', 'constraint_exception_open', RECORDS['BJ-002']['advisory']))
        break

    for item in block.get('encounters') or ():
        if not isinstance(item, dict) or item.get('area') != area or item.get('prepared') is not True:
            continue
        ready = party_ready(state.get('player_sheet'), item.get('assumes'))
        if ready is False:
            applied.append(_view('BJ-004', 'party_below_encounter_assumption',
                                 RECORDS['BJ-004']['advisory_below']))
        elif ready is True:
            applied.append(_view('BJ-004', 'party_meets_encounter_assumption',
                                 RECORDS['BJ-004']['advisory_meets']))
        break

    claims = (source or {}).get('claims') or {}
    for item in block.get('unknown_to') or ():
        if not isinstance(item, dict):
            continue
        actor, claim_id = item.get('actor'), item.get('claim')
        claim = claims.get(claim_id) if isinstance(claims, dict) else None
        holders = (claim or {}).get('holders') if isinstance(claim, dict) else None
        if not actor or not isinstance(holders, dict) or not holders:
            continue
        if holders.get(actor) in ('knows', 'close', 'anchored'):
            continue
        present = ((state.get('actors') or {}).get(actor) or {}).get('location') == area
        if not present:
            continue
        applied.append(_view('BJ-005', 'present_npc_does_not_hold_claim', RECORDS['BJ-005']['advisory']))
        break

    for item in block.get('settled') or ():
        if isinstance(item, dict) and item.get('area') == area and item.get('standing') is True:
            applied.append(_view('BJ-003', 'resolution_already_stood', RECORDS['BJ-003']['advisory']))
            break

    if kind == 'physical_act':
        for item in block.get('damage') or ():
            if isinstance(item, dict) and item.get('area') == area and item.get('scheduled') is False:
                applied.append(_view('BJ-001', 'unscheduled_damage_and_physical_act',
                                     RECORDS['BJ-001']['advisory']))
                break

    if not applied:
        return None
    return {
        'rule': RULE,
        'binding': False,
        'not_a_standing_practice': True,
        'corpus': {'repo': CORPUS_REPO, 'commit': CORPUS_COMMIT, 'path': CORPUS_PATH},
        'applied': applied[:2],
    }


def drift_against(jsonl_text):
    """Differences between the pinned records and a corpus JSONL. Empty means no drift."""
    import json
    rows = {}
    for line in jsonl_text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get('id'):
            rows[row['id']] = row
    errors = []
    for record_id, card in RECORDS.items():
        row = rows.get(record_id)
        if not row:
            errors.append(f'{record_id} missing from corpus')
            continue
        if row.get('status') != card['status']:
            errors.append(f'{record_id} status {row.get("status")} != {card["status"]}')
        if list(row.get('evidence') or []) != list(card['evidence']):
            errors.append(f'{record_id} evidence drifted')
    return errors
