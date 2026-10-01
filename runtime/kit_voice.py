"""Brendon's voice spec for Kit, built as carriers.

Each spec line that should change what the player reads follows the build pattern
from docs/architecture/kit-expression-gap.md: private source -> public field ->
performer instruction -> validator check -> test.

| Spec line                          | Private source         | Public carrier                  |
| ---------------------------------- | ---------------------- | ------------------------------- |
| check player mood, mirror it       | ``player_mood``        | ``public_brief.mirror``         |
| quippy / theatrical / combat voice | ``table_read`` hint    | ``turn_mode``                   |
| theatrical description, overacting | Kit's choice           | ``table_presence: showtime``    |
| NPCs notice what's up with players | actor motives, memory  | ``public_brief.npc_notice``     |

The checks here are floors, like the flat-reply floors: they catch a turn that
ignores its own carrier (a padded reply to a bored player, a playful joke on a tense
one, a meandering fight, an NPC quoting out-of-character feedback). They cannot
tell whether a turn was entertaining; judge that in play.

This module imports nothing from kit_agent so it merges cleanly with other work on
that file (kit-hardening adds NPC voice cards and leak, price, and repetition checks;
none of that is duplicated here).
"""
import re

from .state_context import require

MOOD_READS = ('neutral', 'playful', 'curious', 'tense', 'frustrated', 'bored', 'cautious', 'gleeful')
TURN_MODES = ('meta', 'banter', 'description', 'combat')
TABLE_PRESENCE = ('quiet', 'brief', 'present', 'showtime')
NPC_NOTICE_KINDS = ('mood', 'past_act', 'gear', 'stunt')

PLAYER_MOOD_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'read': {'type': 'string', 'enum': list(MOOD_READS)},
                   'cue': {'type': 'string'}},
    'required': ['read', 'cue'],
}

# Moods that set what the mirror may ask for.
MOMENTUM_MOODS = ('frustrated', 'bored')          # tight: momentum, never padding
SOBER_MOODS = ('tense', 'frustrated', 'cautious')  # no playful humor at their expense
PLAYFUL_MOODS = ('playful', 'gleeful')             # play back: some humor

MOOD_CUE_MAX_CHARS = 160
MIRROR_MAX_CHARS = 200
NPC_NOTICE_MAX_CHARS = 160
# mirror: "<energy> energy, <length>, <humor> humor: <how Kit answers>"
MIRROR_FORMAT = '<low|steady|high> energy, <tight|standard|roomy>, <no|dry|playful> humor: <how>'
MIRROR_PATTERN = re.compile(
    r'^\s*(?P<energy>low|steady|high) energy\s*,\s*(?P<length>tight|standard|roomy)\s*,\s*'
    r'(?P<humor>no|dry|playful) humor\s*[:;,.\u2014\u2013-]+\s*(?P<how>.*)$', re.I | re.S)
NPC_NOTICE_PATTERN = re.compile(r'^\s*(?P<kind>[a-z_ ]+?)\s*:\s*(?P<what>.+)$', re.I | re.S)
MOOD_CUE_REF = re.compile(r'^\s*(feedback|note)\s+(?P<id>\S+?)\s*[.:]?\s*$', re.I)

# Performance floors tied to the carriers.
TIGHT_MAX_WORDS = {'exchange': 110, 'feature': 150}  # a call keeps its own 60-word cap
COMBAT_MAX_AVG_SENTENCE_WORDS = 14                   # Narrator and Kit sentences in combat
COMBAT_MAX_SENTENCE_WORDS = 24
SHOWTIME_MAX_KIT_SEGMENTS = 3

FOCUS_ACTORS = ('uktarl', 'other')  # focus_actor values that name someone who can notice


def _norm(text):
    text = (text or '').replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    return ' '.join(text.casefold().split())


def _words(text):
    return len(re.findall(r"[\w\u2019']+", text))


def is_none(value):
    return isinstance(value, str) and value.strip().casefold() == 'none'


def parse_mirror(mirror):
    """The mirror's (energy, length, humor, how), or None if it is not in MIRROR_FORMAT."""
    found = MIRROR_PATTERN.match(mirror or '')
    if not found:
        return None
    return {key: found.group(key).strip().casefold() if key != 'how' else found.group(key).strip()
            for key in ('energy', 'length', 'humor', 'how')}


def parse_npc_notice(notice):
    found = NPC_NOTICE_PATTERN.match(notice or '')
    if not found:
        return None
    return found.group('kind').strip().casefold().replace(' ', '_'), found.group('what').strip()


def mode_hint(action_kind, is_ooc):
    """What code can detect about the turn mode; None leaves it to Kit's read."""
    if action_kind == 'opening':
        return 'description'
    if is_ooc:
        return 'meta'
    if action_kind != 'social':
        return 'description'  # a room action and its public result
    return None


def table_read(action, action_kind, is_ooc, public_history, player_notes):
    """Private, observable signals for Kit's mood and mode read. Counts, not guesses."""
    recent = [turn.get('player_input') or '' for turn in public_history or ()]
    recent = [text for text in recent if text and text != '[scene entry]']
    return {
        'mode_hint': mode_hint(action_kind, is_ooc),
        'out_of_character': bool(is_ooc),
        'player_words': _words(action) if action_kind != 'opening' else 0,
        'recent_player_words': [_words(text) for text in recent],
        'exclamations': (action or '').count('!') if action_kind != 'opening' else 0,
        'feedback_note_ids': [note['id'] for note in player_notes or ()
                              if note.get('source') == 'feedback'],
    }


def check_player_mood(mood, player_action, action_kind, player_notes, has_history):
    """player_mood is private; its cue ties the read to something observable."""
    require(isinstance(mood, dict) and set(mood) == {'read', 'cue'}, 'Invalid player_mood')
    require(mood['read'] in MOOD_READS, 'Invalid player_mood read')
    cue = mood['cue']
    require(isinstance(cue, str) and 0 < len(cue.strip()) <= MOOD_CUE_MAX_CHARS,
            f'player_mood cue must be 1-{MOOD_CUE_MAX_CHARS} characters')
    if action_kind == 'opening':
        require(mood['read'] == 'neutral', 'The room opening has no player to read yet; player_mood is neutral')
        return
    if mood['read'] == 'neutral':
        return
    ref = MOOD_CUE_REF.match(cue)
    if ref:
        require(any(note['id'] == ref.group('id') for note in player_notes or ()),
                'player_mood cue names an unknown player note')
        return
    if _norm(cue).startswith('pacing:'):
        require(len(cue.split(':', 1)[1].split()) >= 2, 'player_mood pacing cue must say what changed')
        require(has_history, 'player_mood pacing cue needs earlier turns to compare against')
        return
    excerpt = _norm(cue).strip(' .,!?;:"\'')
    require(excerpt and excerpt != 'none' and player_action is not None and
            excerpt in _norm(player_action),
            'player_mood cue must quote the player\'s words, name a player note (feedback nX), '
            'or start with pacing:')


def mood_cue_source(mood, player_notes):
    """'words', 'feedback', 'observed_note', 'pacing', or None for a neutral read."""
    if not isinstance(mood, dict) or mood.get('read') in (None, 'neutral'):
        return None
    ref = MOOD_CUE_REF.match(mood.get('cue', ''))
    if ref:
        note = next((n for n in player_notes or () if n['id'] == ref.group('id')), None)
        return 'feedback' if note and note.get('source') == 'feedback' else 'observed_note'
    return 'pacing' if _norm(mood.get('cue')).startswith('pacing:') else 'words'


def check_mirror(mirror, mood_read, turn_mode):
    """The mirror is public direction in a checkable form that fits the mood read."""
    require(len(mirror.strip()) <= MIRROR_MAX_CHARS, f'mirror exceeds {MIRROR_MAX_CHARS} characters')
    require(not re.search(r'["\u201c\u201d]', mirror), 'mirror is direction, not quoted dialogue')
    parsed = parse_mirror(mirror)
    require(parsed is not None, f'mirror must read "{MIRROR_FORMAT}"')
    require(len(parsed['how'].split()) >= 3, 'mirror must say how Kit answers the mood in a few words')
    if mood_read in MOMENTUM_MOODS:
        require(parsed['length'] == 'tight',
                f'A {mood_read} player gets momentum, not more words: mirror length must be tight')
    if mood_read in SOBER_MOODS:
        require(parsed['humor'] != 'playful',
                f'A {mood_read} player does not get playful humor: mirror humor must be no or dry')
    if mood_read in PLAYFUL_MOODS:
        require(parsed['humor'] != 'no', f'A {mood_read} player gets play back: mirror humor must be dry or playful')
    if turn_mode == 'combat':
        require(parsed['humor'] != 'playful', 'Combat is tense: mirror humor must be no or dry')
    return parsed


def check_turn_mode(plan, action_kind, is_ooc):
    mode = plan['turn_mode']
    require(mode in TURN_MODES, 'Invalid turn_mode')
    hint = mode_hint(action_kind, is_ooc)
    if action_kind == 'opening' or is_ooc:
        require(mode == hint, f'turn_mode must be {hint} for this turn')
    elif action_kind != 'social':
        require(mode in ('description', 'combat'), 'A room action is a description (or combat) turn')
    if mode == 'meta':
        require(plan['table_presence'] != 'quiet', 'Meta talk is answered by Kit; table presence cannot be quiet')


def check_showtime(plan, mood_read):
    if plan['table_presence'] != 'showtime':
        return
    scope = plan['public_brief']['scope']
    require(scope != 'call', 'Showtime is never a call: a roll prompt or ruling stays short')
    require(plan['turn_mode'] != 'combat', 'Combat stays tense and fast; showtime is for description and banter')
    require(mood_read != 'frustrated', 'A frustrated player gets momentum, not a show')
    require(plan['turn_mode'] in ('description', 'banter') or mood_read in PLAYFUL_MOODS,
            'Showtime needs a description or banter turn, or a playful player')


def check_npc_notice(plan, is_ooc, player_notes):
    notice = plan['public_brief']['npc_notice'].strip()
    if is_none(notice):
        return
    require(len(notice) <= NPC_NOTICE_MAX_CHARS, f'npc_notice exceeds {NPC_NOTICE_MAX_CHARS} characters')
    require(not re.search(r'["\u201c\u201d]', notice), 'npc_notice is direction, not an NPC line')
    parsed = parse_npc_notice(notice)
    require(parsed is not None and parsed[0] in NPC_NOTICE_KINDS and len(parsed[1].split()) >= 3,
            'npc_notice must read "<mood|past_act|gear|stunt>: <what the actor notices and why it '
            'matters to them>" or be none')
    kind, _ = parsed
    require(not re.search(r'\b(kit|dm|table talk|out of character|ooc|feedback)\b', _norm(notice)),
            'npc_notice is what the actor sees in the fiction, never Kit, the table, or feedback')
    require(plan['focus_actor'] in FOCUS_ACTORS, 'npc_notice needs a focus actor to do the noticing')
    require(plan['turn_mode'] != 'meta' and not is_ooc, 'NPCs do not hear table talk; npc_notice is none in meta mode')
    if kind == 'mood':
        mood = plan['player_mood']
        require(mood['read'] != 'neutral', 'npc_notice mood needs a player_mood read')
        require(mood_cue_source(mood, player_notes) == 'words',
                'An NPC notices only what the character says or does this turn, never out-of-character '
                'feedback or pacing; cue the mood from the player\'s words or pick another notice')
    if kind == 'past_act':
        require(plan['memory_refs'], 'npc_notice past_act needs the remembered turn in memory_refs')


def check_voice_plan(plan, action_kind, player_action, is_ooc, player_notes, has_history):
    """All voice-spec checks on a private decision."""
    check_player_mood(plan['player_mood'], player_action, action_kind, player_notes, has_history)
    check_turn_mode(plan, action_kind, is_ooc)
    check_mirror(plan['public_brief']['mirror'], plan['player_mood']['read'], plan['turn_mode'])
    check_showtime(plan, plan['player_mood']['read'])
    check_npc_notice(plan, is_ooc, player_notes)


def _sentences(text):
    return [part for part in re.split(r'(?<=[.!?])\s+|\s*[;\u2014]\s*|\n+', text) if _words(part)]


def check_voice_presence(segments, plan, focus_speakers=()):
    """HARD, like table presence and the chosen move: who must speak for the carriers.
    Plans fixed before these carriers existed (no turn_mode or npc_notice) skip them."""
    brief = plan.get('public_brief') or {}
    kit_count = sum(segment['speaker'] == 'Kit' for segment in segments)
    if plan.get('turn_mode') == 'meta':
        require(kit_count >= 1, 'Meta turn: Kit answers the table talk herself in a Kit segment')
    if plan.get('table_presence') == 'showtime':
        require(1 <= kit_count <= SHOWTIME_MAX_KIT_SEGMENTS,
                f'Showtime: Kit takes the stage in 1-{SHOWTIME_MAX_KIT_SEGMENTS} Kit segments, '
                f'not {kit_count}; the actors still get their turn')
    if not is_none(brief.get('npc_notice', 'none')):
        require(focus_speakers and any(segment['speaker'] in focus_speakers for segment in segments),
                f'npc_notice: the {" or ".join(focus_speakers) or "focus actor"} never reacted. They '
                'notice it in their own voice.')


def check_voice_style(segments, plan):
    """SOFT, like the flat-reply floors (warnings in degraded mode): length for the
    mirror and rhythm for combat."""
    brief = plan.get('public_brief') or {}
    scope = brief.get('scope')
    mirror = parse_mirror(brief.get('mirror', ''))
    if mirror and mirror['length'] == 'tight' and scope in TIGHT_MAX_WORDS:
        total = sum(_words(segment['text']) for segment in segments)
        require(total <= TIGHT_MAX_WORDS[scope],
                f'Mirror says tight: {total} words (limit {TIGHT_MAX_WORDS[scope]} for {scope}). '
                'Give momentum: answer, move the scene, hand the player a choice. No padding.')
    if plan.get('turn_mode') == 'combat':
        lengths = [_words(sentence) for segment in segments if segment['speaker'] in ('Narrator', 'Kit')
                   for sentence in _sentences(segment['text'])]
        if lengths:
            average = sum(lengths) / len(lengths)
            require(average <= COMBAT_MAX_AVG_SENTENCE_WORDS and max(lengths) <= COMBAT_MAX_SENTENCE_WORDS,
                    f'Combat narration dragged (average {average:.0f} words per sentence, longest '
                    f'{max(lengths)}; limits {COMBAT_MAX_AVG_SENTENCE_WORDS} and '
                    f'{COMBAT_MAX_SENTENCE_WORDS}). Short, punchy, sensory beats.')


def check_voice_performance(segments, plan, focus_speakers=()):
    """Both halves, for callers outside check_speech."""
    check_voice_presence(segments, plan, focus_speakers)
    check_voice_style(segments, plan)
