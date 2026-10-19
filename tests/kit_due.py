"""What a live Kit does when the engine says the equipment question is due (runtime/kit_gear.py:
the packet's private gear_clarify): she asks it, in her own voice, on that turn.

Suites written before the equipment audit script Kit's lines for sheets that now raise one (Nik's
stats-only sheet lists the Sentinel Shield; a wizard has no shield training). They play the
sheet as it is and have scripted Kit ask the question when it is due, as she would at the
table; nothing about the sheet or the engine is changed for them.
"""


def asked(packet, segments):
    """``segments`` with Kit's question added when the packet says it is due this turn."""
    due = ((packet or {}).get('input') or {}).get('private', {}).get('gear_clarify')
    out = [dict(segment) for segment in segments]
    if not due:
        return out
    kit = [segment for segment in out if segment.get('speaker') == 'Kit']
    if kit:  # one Kit line: the question joins it
        kit[-1]['text'] = f"{kit[-1]['text'].rstrip()} {due['ask']}"
        return out
    shown = next((segment['text'] for segment in out if segment.get('speaker') != 'Kit'), '')
    quote = ' '.join(shown.split()[:6]).rstrip('.,;:!?')
    return out + [{'speaker': 'Kit', 'text': due['ask'], 'reacts_to': quote}]


# Nik's sheet lists the Sentinel Shield (advantage on initiative while held): the initiative call
# says so. Either ending is the engine's call for the sheet in play.
INITIATIVE = ('Roll initiative.', 'Roll initiative with advantage (the Sentinel Shield).')
INITIATIVE_RE = r'Roll initiative(?: with advantage \(the Sentinel Shield\))?\.'
