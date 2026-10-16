"""Situational DM judgments for Kit's private decision input.

``prepare_inputs`` calls ``for_turn`` with the player line. A match adds
``dm_judgment`` to that private packet only. The performer never receives it.
No match adds nothing: the research is not dumped into every turn.

The cards are a curated subset of
``research/longitudinal/bounded-judgment-tranche-2026-10-15`` in
``radarsaint/bfdm-corpus``. Each card keeps its limit beside the advice.
An empty ``later_judgments`` list is the slot for a later sourced judgment.
Nothing in that list is inferred from the historical line, and a wish to
add hindsight is not itself a later judgment.

No model calls.
"""

RULE = ('Bounded historical judgments for this turn only. Use one only when the '
        'player line is the situation it names. The limit travels with the advice. '
        'These are not standing practices. Do not narrate the research, and do not '
        'treat a later empty slot as an endorsement.')


def _later(items):
    """Sourced hindsight only. An empty list stays empty."""
    out = []
    for item in items or ():
        if not item.get('source') or not item.get('text'):
            continue
        out.append({'source': item['source'], 'text': item['text'], 'status': item.get('status', 'UNPROVEN')})
    return out


# Order is the conflict order. An earlier match can suppress a later card.
CARDS = (
    {
        'id': 'designed_constraint',
        'status': 'VERIFIED_NARROW',
        'when': ('spare bedroom', 'give me a house', 'my own house', 'housing exception',
                 'meant to be vulnerable'),
        'unless': (),
        'suppresses': ('unplanned_repair',),
        'advice': ('Decline a request that removes a constraint the situation was built to keep. '
                   'Say what the constraint is for. Do not invent a private exception.'),
        'limit': ('One Empire City refusal on 2021-07-10, message 863492563784040539. '
                  'A spare bedroom was refused because home was meant to stay vulnerable, and one '
                  'gift would be demanded by everyone. This does not forbid unplanned repair of '
                  'destruction, and it is not a rule for every creative request.'),
        'evidence': ('discord:863492563784040539',),
        'later_judgments': (),
    },
    {
        'id': 'prepared_fight_stands',
        'status': 'NARROWED',
        'when': ('topped up', 'not depleted', "we're full", 'ready for the fight'),
        'unless': (),
        'also': ('preplanned', 'prepared fight', 'the boss'),
        'suppresses': ('party_mismatch',),
        'advice': ('Do not cancel a prepared encounter because a simplistic rule says hard fights '
                   'should be skipped. The table has said they are up for it. Play the fight, or ask '
                   'one question if something else is actually wrong.'),
        'limit': ('On 2020-08-21 Brendon guessed the party was depleted and said not to take them into '
                  'the preplanned fight (746253583552479272). Players immediately said some were not '
                  'depleted. His first read was not the table. The window does not show the encounter '
                  'that was played. Cancelling on the guess would have been the wrong use of that moment.'),
        'evidence': ('discord:746253583552479272', 'discord:746253875727564831'),
        'later_judgments': (),
    },
    {
        'id': 'party_mismatch',
        'status': 'NARROWED',
        'when': ('depleted', 'out of spell slots', 'out of slots', 'too wiped for the boss'),
        'unless': ('topped up', 'not depleted', "we're full"),
        'also': ('preplanned', 'prepared fight', 'the boss'),
        'suppresses': (),
        'advice': ('The prepared encounter assumed a party you may not have. Say so, and offer a '
                   'smaller danger or a non-fight only if they would find that satisfying. Do not '
                   'announce that the scene has already been changed.'),
        'limit': ('He reconsidered out loud, then offered mostly roleplay only if it was satisfying, '
                  'or mobs instead of bosses (746253900490735686, 746254092011175968). Players corrected '
                  'the depleted read and one asked for some kind of fight (746254154774872094). '
                  'No delivered encounter is in the window. This is not a rule that every prepared '
                  'fight yields to a tired party.'),
        'evidence': ('discord:746253583552479272',),
        'later_judgments': (),
    },
    {
        'id': 'undisclosed_knowledge',
        'status': 'VERIFIED_DRAFT_CORRECTION',
        'when': ('mentioned tasha', 'clue they missed', 'never said', "didn't reveal", 'did not reveal'),
        'unless': (),
        'suppresses': (),
        'advice': ('An NPC acts on what that NPC has seen or been told. Do not hand them a fact the '
                   'players never revealed and the NPC was not there to learn.'),
        'limit': ('BCS-000172. The draft had Neris infer that the party had mentioned Tasha. Brendon '
                  'corrected it: "you are asuming they mentioned tasha. they didnt". The source is a '
                  'partial workbench log, not a play transcript. It does not prove a replacement scene '
                  'was run.'),
        'evidence': ('bcs:BCS-000172',),
        'later_judgments': (),
    },
    {
        'id': 'nonretroactive_correction',
        'status': 'VERIFIED_NARROW',
        'when': ('undo last night', "take back the resurrection", 'once per day resurrection',
                 'nerf what already happened'),
        'unless': (),
        'suppresses': (),
        'advice': ('If a rule was a mistake, change it going forward. Do not erase a resolution that '
                   'already stood.'),
        'limit': ('One announcement, 744056939096571924, 2020-08-15. He called the once-per-day '
                  'resurrection a balance mistake and said that night\'s resurrections still stood. '
                  'That is not a policy for every failed house rule, and no later practice is in the message.'),
        'evidence': ('discord:744056939096571924',),
        'later_judgments': (),
    },
    {
        'id': 'unplanned_repair',
        'status': 'VERIFIED_NARROW',
        'when': ('clear the rubble', 'help rebuild', 'repair the damage', 'rebuilding the',
                 'fix what was destroyed'),
        'unless': ('spare bedroom', 'give me a house', 'my own house', 'housing exception'),
        'suppresses': (),
        'advice': ('The player is offering to repair something the prep did not schedule. Let them try. '
                   'Do not write their outcome, and do not pay them for work they have not done yet.'),
        'limit': ('Empire City staff chat, 2021-07-16. A player asked to clear rubble at the money changer '
                  '(865565663296225280). Brendon had not planned it, called the rebuilding healing, said yes, '
                  'and then "just waiting for his post" (865566464831258674, 865567436970786836). '
                  'A colleague later said the player posted without being prodded. This is not permission '
                  'to remove a designed vulnerability, and it does not show what the fiction became.'),
        'evidence': ('discord:865565818481279018', 'discord:865565932783796255'),
        'later_judgments': (),
    },
)


def _hit(text, card):
    if not any(phrase in text for phrase in card['when']):
        return False
    if any(phrase in text for phrase in card.get('unless', ())):
        return False
    also = card.get('also')
    if also and not any(phrase in text for phrase in also):
        return False
    return True


def for_turn(action, kind='play'):
    """The private packet for this player line, or None when nothing applies."""
    if kind == 'opening' or not isinstance(action, str) or not action.strip():
        return None
    text = action.casefold()
    chosen = []
    suppressed = set()
    for card in CARDS:
        if card['id'] in suppressed:
            continue
        if not _hit(text, card):
            continue
        chosen.append(card)
        suppressed.update(card.get('suppresses') or ())
    if not chosen:
        return None
    return {
        'rule': RULE,
        'not_a_standing_practice': True,
        'applied': [_view(card) for card in chosen[:2]],
    }


def _view(card):
    later = _later(card.get('later_judgments'))
    view = {
        'id': card['id'],
        'status': card['status'],
        'advice': card['advice'],
        'limit': card['limit'],
        'evidence': list(card['evidence']),
        'later_judgments': later,
    }
    if later:
        view['hindsight'] = later
    return view
