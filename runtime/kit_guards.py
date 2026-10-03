"""Guards for failure modes a live ChatGPT host hits in play (branch kit-hardening).

Each guard follows the build pattern in docs/architecture/kit-expression-gap.md:
private source -> public carrier -> performer instruction -> validator check -> test.
Every threshold is a named constant documented where it is defined. They are cheap,
crude heuristics: they catch the common, recognizable form of each failure and are
tuned to stay quiet on ordinary good turns. None of them measures quality, and
none of them contains a line for any character. Section (g) of the doc lists what
each one cannot catch.

Checks come in two strengths:
- HARD checks protect truth and the player: hidden facts, the player's agency, and
  NPCs talking about game mechanics. They always apply.
- SOFT checks guard style: padding, repetition, and NPC voice distinctness (plus the
  existing flat-reply floors and callback use in kit_agent). After repeated rejections
  the host may commit a degraded turn, where soft failures are recorded as warnings
  instead of stalling the table (see DEGRADED_AFTER_REJECTIONS in kit_agent).
"""
import re

from .state_context import InvalidChange, require

# Every speaker label except these is an NPC voiced from the room source's actor cards.
NON_NPC_SPEAKERS = ('Narrator', 'Kit')


def is_npc(speaker):
    return isinstance(speaker, str) and bool(speaker.strip()) and speaker.strip() not in NON_NPC_SPEAKERS
_APOSTROPHES = str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"'})
_SMALL_WORDS = frozenset('''
    a an the and or but if of to in on at by for with from as is are was were be been am
    it its this that these those i you he she we they me him her us them my your his our
    their do does did not no so than then there here what who how why when where which
    will would can could shall should may might must just very really all any some
'''.split())


def normalize(text):
    return ' '.join((text or '').translate(_APOSTROPHES).casefold().split())


def tokens(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", normalize(text))


def sentences(text):
    return [part.strip() for part in re.split(r'(?<=[.!?…])\s+|\n+', text or '') if part.strip()]


def content_words(words):
    return {word for word in words if len(word) >= 4 and word not in _SMALL_WORDS}


def ngrams(words, size):
    return {tuple(words[i:i + size]) for i in range(len(words) - size + 1)}


def distinctive_runs(a, b, size, min_content=2):
    """Word runs of `size` shared by two texts that carry at least `min_content`
    content words, so shared filler like 'at this table' does not count."""
    shared = ngrams(tokens(a), size) & ngrams(tokens(b), size)
    return {run for run in shared if len(content_words(run)) >= min_content}


def _run_text(run):
    return ' '.join(run)


# ---------------------------------------------------------------------------
# 1. Padding past the word floors (SOFT)
# ---------------------------------------------------------------------------
# A model told "at least 30 words" pads: it repeats itself, restates the player,
# or reaches for stock filler. These catch the crude forms only.
PADDING_REPEAT_RUN_WORDS = 6   # the same 6-word run twice in one turn is repetition
RESTATE_MAX_RUN_WORDS = 7      # echoing 7+ consecutive words of the player's is restating them
RECYCLED_RUN_WORDS = 8         # an 8-word run from the last few public turns is a recycled line
FILLER_PHRASES = (             # stock narration that fills space without adding anything
    'the air is thick with', 'tension hangs in the air', 'the tension is palpable',
    'a moment passes', 'time seems to stand still', 'time seems to slow',
    "you can't help but", 'little do you know', 'an air of mystery',
    'needless to say', 'it is worth noting', "it's worth noting", 'without further ado',
    'the atmosphere is', 'a palpable sense of',
)
# Narration that retells what the player just did ("You ask what is going on.").
# The accepted event already shows it; retelling it only fills the floor.
_RESTATE_OPENERS = re.compile(
    r"^you (say|said|ask|asked|tell|told|greet|greeted|introduce|introduced|declare|declared|"
    r"explain|explained|mention|mentioned|inquire|inquired|reply|replied|announce|announced)\b")


def check_padding(segments, player_action, action_kind, public_history=(), public_state='', card_words=()):
    """Reject crude padding: repetition, restating the player, recycled lines, filler.
    public_state is the current public table state (e.g. the player's hand): naming what
    is on the table again is reporting the state, not padding."""
    state_words = tokens(public_state or '')
    card_vocab = {normalize(word) for word in card_words or ()}

    def stated(run):
        # A hand or table reminder (cards, ranks, suits, colors, numbers) is reporting the
        # game state, never padding (Brendon's table call 7).
        if card_vocab and all(word.isdigit() or word in card_vocab for word in content_words(run)):
            return True
        size = len(run)
        return any(tuple(state_words[i:i + size]) == run for i in range(len(state_words) - size + 1))
    seen = {}
    for segment in segments:
        # Every position, not the ngram set: a set hides a run repeated inside one
        # segment, which is exactly how overacted narration pads (kit-voice-spec).
        words = tokens(segment['text'])
        for run in [tuple(words[i:i + PADDING_REPEAT_RUN_WORDS])
                    for i in range(len(words) - PADDING_REPEAT_RUN_WORDS + 1)]:
            if run in seen and len(content_words(run)) >= 2 and not stated(run):
                raise InvalidChange(
                    f'Padding: the turn repeats "{_run_text(run)}". Say each thing once; the floors '
                    'are not targets.')
            seen[run] = True
    performed = ' '.join(segment['text'] for segment in segments)
    if action_kind != 'opening' and player_action:
        echoed = ngrams(tokens(player_action), RESTATE_MAX_RUN_WORDS) & ngrams(
            tokens(performed), RESTATE_MAX_RUN_WORDS)
        if echoed:
            raise InvalidChange(
                f'Padding: the turn echoes {RESTATE_MAX_RUN_WORDS}+ of the player\'s own words '
                f'("{_run_text(sorted(echoed)[0])}"). Answer them; do not restate them.')
    if action_kind == 'social':
        for segment in segments:
            if segment['speaker'] in ('Narrator', 'Kit'):
                for sentence in sentences(segment['text']):
                    if _RESTATE_OPENERS.search(normalize(sentence)):
                        raise InvalidChange(
                            'Padding: narration retells what the player said or did ("'
                            f'{sentence[:60]}"). The event already shows it; start from the response.')
    for turn in public_history or ():
        recycled = ngrams(tokens(performed), RECYCLED_RUN_WORDS) & ngrams(
            tokens(turn.get('spoken', '')), RECYCLED_RUN_WORDS)
        recycled = {run for run in recycled if len(content_words(run)) >= 2 and not stated(run)}
        if recycled:
            raise InvalidChange(
                f'Padding: the turn recycles an earlier line ("{_run_text(sorted(recycled)[0])}"). '
                'Characters do not repeat themselves across turns.')
    lowered = normalize(performed)
    hits = [phrase for phrase in FILLER_PHRASES if phrase in lowered]
    if hits:
        raise InvalidChange(f'Padding: stock filler ("{hits[0]}"). Replace it with something '
                            'specific the player can see or answer, or cut it.')


# ---------------------------------------------------------------------------
# 2. NPC voices: nothing like Kit, and not like each other
# ---------------------------------------------------------------------------
# HARD: NPCs live in the fiction. Talk of dice, checks, DCs, the DM, "your character",
# or the story as a story is table talk, which belongs only to Kit.
NPC_META_PATTERN = re.compile(
    r"\b(dungeon master|game master|the dm|your character|the narrator|npcs?|nat(ural)? ?20|"
    r"d20|d12|d10|d8|d6|d4|saving throw|hit points|initiative|ability check|skill check|"
    r"roll (a|for|initiative|insight|perception|stealth|athletics)|make (a|an) \w+ check|"
    r"dc ?\d+|fourth wall|this scene|the story so far|plot twist|table presence|player character)\b")
# SOFT: Kit's signature register. Her voice guidance has her deliver short verdicts on
# the bid ("Bold.") and table-side asides. From an NPC, a sentence that is only such a
# verdict, or one of these table-side phrases, sounds like Kit, not like the character.
KIT_VERDICT_WORDS = frozenset((
    'bold', 'clever', 'reckless', 'doomed', 'audacious', 'daring', 'ambitious', 'interesting',
    'noted', 'terrible', 'fascinating', 'delightful', 'brave', 'cute', 'coward', 'cowards',
    'pity', 'shame', 'tragic', 'rude', 'adorable', 'riveting', 'thrilling', 'impressive'))
# Kit's dry register as constructions, not lines (approach-range playtest, 2026-09-28:
# the dealer drifted into deadpan understatement and asides). Each is a class of
# phrasing that comments on the moment instead of pursuing something.
KIT_DRY_REGISTER = (
    ('a one-word deadpan hedge', re.compile(
        r"^(probably|allegedly|apparently|mostly|presumably|arguably|possibly|supposedly|reportedly|"
        r"technically|theoretically|obviously|naturally|clearly|sadly|tragically|evidently)$")),
    ('understated approval of the player', re.compile(
        r"^(but|still|well|and|though)?,? ?i (do |must say i )?(admire|respect|appreciate|applaud|"
        r"salute|commend) (the|your|that)\b")),
    ('ironic self-pity', re.compile(r"\bfor my (feelings|nerves|heart|pride|dignity|sanity)\b")),
    ('an ironic comparison', re.compile(r"\b(haven't|hasn't|have not|has not) been this \w+ since\b")),
    ('an aside to the audience', re.compile(
        r"\b(if i do say so myself|as one does|how original|what a surprise|shocking,? i know)\b")),
)
KIT_VERDICT_MAX_WORDS = 2      # a sentence this short that is a verdict word is Kit's move
KIT_SIGNATURE_PHRASES = (
    'that is a choice', "that's a choice", 'what a choice', 'interesting choice',
    'did not see that coming', "didn't see that coming", "i'll allow it", 'i will allow it',
    "let's see how this plays out", 'let us see how this plays out', 'the dice decide',
)
KIT_SHARED_RUN_WORDS = 4       # an NPC reusing a 4-word run from Kit's own lines borrows her phrasing
# SOFT: two NPCs in one turn who could swap lines are one voice with two names.
NPC_COMPARE_MIN_WORDS = 5      # each NPC needs this many content words before comparing
NPC_OVERLAP_MAX_JACCARD = 0.5  # shared content-word ratio at or above this is interchangeable
NPC_SHARED_RUN_WORDS = 4       # or a shared 4-word run carrying two content words
VOICE_CONTRACT_FIELDS = ('rhythm', 'register', 'tics', 'never_says', 'wants', 'humor')


def kit_lines(segments, public_history=()):
    """Kit's own words: this turn's Kit segments plus her lines in recent public turns."""
    lines = [segment['text'] for segment in segments if segment['speaker'] == 'Kit']
    for turn in public_history or ():
        lines += [line[4:].strip() for line in (turn.get('spoken') or '').splitlines()
                  if line.startswith('Kit:')]
    return lines


def check_npc_meta(segments):
    """HARD: no table talk or mechanics in an NPC's mouth."""
    for segment in segments:
        if is_npc(segment['speaker']):
            found = NPC_META_PATTERN.search(normalize(segment['text']))
            if found:
                raise InvalidChange(
                    f'NPC voice: the {segment["speaker"]} used table talk ("{found.group(0)}"). '
                    'Rules, dice, and commentary on the game belong only in Kit segments.')


def check_npc_voices(segments, voice_contracts=None, public_history=()):
    """SOFT: NPC lines must not sound like Kit or like each other, and must keep
    their card's checkable voice limits."""
    voice_contracts = voice_contracts or {}
    kit = kit_lines(segments, public_history)
    by_speaker = {}
    for segment in segments:
        if not is_npc(segment['speaker']):
            continue
        speaker, text = segment['speaker'], segment['text']
        by_speaker[speaker] = by_speaker.get(speaker, '') + ' ' + text
        lowered = normalize(text)
        for phrase in KIT_SIGNATURE_PHRASES:
            if phrase in lowered:
                raise InvalidChange(
                    f'NPC voice: the {speaker} used Kit\'s table-side phrasing ("{phrase}"). '
                    'Kit\'s reactions stay in Kit segments; the NPC answers from their own card.')
        for sentence in sentences(text):
            words = tokens(sentence)
            if 0 < len(words) <= KIT_VERDICT_MAX_WORDS and set(words) & KIT_VERDICT_WORDS:
                raise InvalidChange(
                    f'NPC voice: the {speaker} delivered a one-word verdict ("{sentence}"), which '
                    'is Kit\'s register. Let the NPC react from their own wants and diction.')
            plain = ' '.join(words)
            for label, pattern in KIT_DRY_REGISTER:
                if pattern.search(plain):
                    raise InvalidChange(
                        f'NPC voice: the {speaker} slipped into Kit\'s dry register ({label}: '
                        f'"{sentence[:60]}"). NPC humor comes from their own card and pursues '
                        'something; wry comments on the moment belong to Kit.')
        for line in kit:
            shared = distinctive_runs(text, line, KIT_SHARED_RUN_WORDS)
            if shared:
                raise InvalidChange(
                    f'NPC voice: the {speaker} borrowed Kit\'s words ("{_run_text(sorted(shared)[0])}"). '
                    'NPCs never share her phrasing.')
        contract = voice_contracts.get(speaker) or {}
        for word in contract.get('never_words', []):
            if re.search(rf"\b{re.escape(normalize(word))}\b", lowered):
                raise InvalidChange(
                    f'NPC voice: the {speaker} said "{word}", which their voice contract rules out. '
                    'Speak from that card\'s register.')
        limit = contract.get('max_words_per_sentence')
        if limit:
            for sentence in sentences(text):
                if len(tokens(sentence)) > limit:
                    raise InvalidChange(
                        f'NPC voice: the {speaker} ran {len(tokens(sentence))} words in one sentence; '
                        f'their card\'s rhythm allows {limit}. Keep their clipped cadence.')
    speakers = sorted(by_speaker)
    for i, first in enumerate(speakers):
        for second in speakers[i + 1:]:
            a, b = content_words(tokens(by_speaker[first])), content_words(tokens(by_speaker[second]))
            if len(a) >= NPC_COMPARE_MIN_WORDS and len(b) >= NPC_COMPARE_MIN_WORDS:
                overlap = len(a & b) / len(a | b)
                if overlap >= NPC_OVERLAP_MAX_JACCARD:
                    raise InvalidChange(
                        f'NPC voice: the {first} and the {second} sound interchangeable ({overlap:.0%} '
                        f'shared words; limit {NPC_OVERLAP_MAX_JACCARD:.0%}). Give each their card\'s '
                        'rhythm, register, and wants.')
            shared = distinctive_runs(by_speaker[first], by_speaker[second], NPC_SHARED_RUN_WORDS)
            if shared:
                raise InvalidChange(
                    f'NPC voice: the {first} and the {second} share the phrase '
                    f'"{_run_text(sorted(shared)[0])}". Two characters do not talk alike.')


# SOFT, across turns (approach-range playtest: the dealer said "friend" in 18 of 29
# lines). An NPC may not reuse a pet name/vocative from their own recent turns, nor a
# distinctive phrase.
NPC_VOCATIVE_WINDOW_TURNS = 2  # a vocative used by the same NPC in the last 2 public turns
NPC_REPEAT_RUN_WORDS = 4       # a 4-word run (2+ content words) from the same NPC's recent lines
_NOT_VOCATIVES = frozenset('''
    then please eh no yes right too again now still though anyway indeed perhaps maybe surely
    well so oh look listen and but here come sit go ah yes okay alright course after all
    tonight today instead either neither first
'''.split())


def _vocatives(text):
    found = set()
    for sentence in sentences(text):
        norm = normalize(sentence)
        tail = re.search(r",\s*([a-z']+(?: [a-z']+)?)\s*[.!?]*$", norm)
        head = re.match(r"^([a-z']+(?: [a-z']+)?),\s", norm)
        for match in (tail, head):
            if match:
                words = match.group(1).split()
                if not set(words) & _NOT_VOCATIVES and not set(words) & _SMALL_WORDS - {'my'}:
                    found.add(re.sub(r'^my ', '', match.group(1)))
    return found


def speaker_history(public_history, speaker):
    """The given speaker's lines per recent public turn, oldest first."""
    prefix = f'{speaker}:'
    return [[line[len(prefix):].strip() for line in (turn.get('spoken') or '').splitlines()
             if line.startswith(prefix)] for turn in public_history or ()]


def check_npc_repetition(segments, public_history=()):
    by_speaker = {}
    for segment in segments:
        if is_npc(segment['speaker']):
            by_speaker[segment['speaker']] = by_speaker.get(segment['speaker'], '') + ' ' + segment['text']
    for speaker, text in by_speaker.items():
        turns = speaker_history(public_history, speaker)
        recent = ' '.join(' '.join(lines) for lines in turns[-NPC_VOCATIVE_WINDOW_TURNS:])
        reused = _vocatives(text) & _vocatives(recent)
        if reused:
            raise InvalidChange(
                f'NPC voice: the {speaker} reused the pet name "{sorted(reused)[0]}" from a recent '
                'turn. A repeated vocative becomes a catchphrase; find a new angle.')
        earlier = ' '.join(' '.join(lines) for lines in turns)
        shared = distinctive_runs(text, earlier, NPC_REPEAT_RUN_WORDS)
        if shared:
            raise InvalidChange(
                f'NPC voice: the {speaker} repeated their own phrase "{_run_text(sorted(shared)[0])}" '
                'from a recent turn. Characters do not run on catchphrases.')


# SOFT, across turns (approach-range playtest: Kit's rulings fell into "X, not Y" and
# "noted"). The same construction may not appear in Kit's lines this turn if it
# appeared in any of her recent public lines, or twice this turn.
KIT_TIC_CONSTRUCTIONS = (
    ('the "X, not Y" contrast', re.compile(r",\s+not\s+\w")),
    ('a "noted" acknowledgement', re.compile(r"\b(duly )?noted\b|\bwriting that down\b|"
                                            r"\bi'll remember that\b")),
)


def check_kit_tics(segments, public_history=()):
    current = [normalize(segment['text']) for segment in segments if segment['speaker'] == 'Kit']
    if not current:
        return
    recent = [normalize(line) for line in kit_lines([], public_history)]
    for label, pattern in KIT_TIC_CONSTRUCTIONS:
        uses = sum(len(pattern.findall(line)) for line in current)
        if uses >= 2 or (uses and any(pattern.search(line) for line in recent)):
            raise InvalidChange(
                f'Kit voice: {label} again. A ruling template repeated across turns becomes a tic; '
                'phrase this one differently.')


def check_voice_contracts(actor_cards):
    """Every speaking NPC card carries a distinct voice contract (fail loud at prepare)."""
    contracts = {}
    for speaker, card in (actor_cards or {}).items():
        contract = card.get('voice_contract')
        require(isinstance(contract, dict) and all(contract.get(key) for key in VOICE_CONTRACT_FIELDS),
                f'Actor card {speaker} needs a voice_contract with {", ".join(VOICE_CONTRACT_FIELDS)}')
        contracts[speaker] = contract
    names = sorted(contracts)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            for key in ('rhythm', 'register'):
                require(normalize(contracts[first][key]) != normalize(contracts[second][key]),
                        f'Voice contracts for {first} and {second} share the same {key}')
    return contracts


# ---------------------------------------------------------------------------
# 3. Kit's direction touches NPCs only through tactic, pacing, and framing
# ---------------------------------------------------------------------------
# kit_focus may choose which tactic plays out, how fast, and how it is framed. It may
# not set how an NPC talks: that comes from the NPC's card. Diction words next to an
# NPC reference in Kit's direction are the tell.
DICTION_WORDS = re.compile(
    r"\b(quips?|jokes?|joking|puns?|wisecracks?|witty|wit|banter|sarcas\w*|wry|wryly|humou?r\w*|"
    r"funny|drawl\w*|accent|diction|phrasing|vocabulary|catchphrase|voice|sounds? like|"
    r"speaks? like|talks? like|in kit's|like kit)\b")
NPC_REFERENCES = re.compile(r"\b(dealer|card player|players at the table|npcs?|actors?|he|his|him|"
                            r"she|her|they|them)\b")
# Quoted text of this many words in a brief direction field is a scripted line.
BRIEF_QUOTE_MAX_WORDS = 2


def check_direction_not_diction(brief):
    focus = normalize(brief.get('kit_focus', ''))
    if NPC_REFERENCES.search(focus) and DICTION_WORDS.search(focus):
        raise InvalidChange(
            'kit_focus sets how an NPC talks. Kit\'s direction may choose which tactic plays out, the '
            'pacing, and the framing; the NPC\'s words and humor come from their own card.')
    for field in ('objective', 'tactic', 'visible_cue', 'player_opening'):
        for quoted in re.findall(r'"([^"]+)"', (brief.get(field) or '').translate(_APOSTROPHES)):
            if len(tokens(quoted)) > BRIEF_QUOTE_MAX_WORDS:
                raise InvalidChange(
                    f'public_brief {field} scripts a line ("{quoted[:40]}"). Direct the move; '
                    'never write the NPC\'s words.')


# ---------------------------------------------------------------------------
# 4. Vague kit_focus
# ---------------------------------------------------------------------------
# "Make it engaging" passes every shape check and carries nothing. After removing
# words that could describe any turn at any table, kit_focus must still name at
# least KIT_FOCUS_MIN_CONCRETE_WORDS concrete things (a detail, actor, tactic, ruling,
# or restraint).
KIT_FOCUS_MIN_CONCRETE_WORDS = 2
EMPTY_DIRECTIVE_WORDS = frozenset('''
    make makes making keep keeps it this scene scenes turn moment moments engaging engage engaged
    engagement interesting interest fun exciting excitement excite memorable immersive immersion
    dramatic drama tension tense lively compelling entertaining entertain good great better best
    cool story player players experience vibe vibes mood atmosphere energy flow going more really
    very things stuff overall sure feel feels feeling some bit little lots enjoyable enjoy
    satisfying awesome epic vivid rich colorful flavorful flavor spice spicy punchy strong nice
    dynamic alive real realistic authentic natural organic show kit kit's taste personality
    character voice style own use give let add bring exciting fresh stakes high suspense
    suspenseful mysterious mystery intrigue intriguing emotional emotion emotions fully entire
    whole everything something anything table here now always
'''.split())
VAGUE_FOCUS_PHRASES = ('make it engaging', 'keep it interesting', 'make it fun', 'make it exciting',
                       'keep the player engaged', 'make it memorable', 'be engaging', 'be interesting',
                       'add tension', 'show personality', 'keep it moving')


def check_focus_specific(kit_focus):
    focus = normalize(kit_focus)
    concrete = [word for word in tokens(focus)
                if word not in EMPTY_DIRECTIVE_WORDS and word not in _SMALL_WORDS and len(word) > 2]
    phrase = next((p for p in VAGUE_FOCUS_PHRASES if p in focus), None)
    if len(concrete) < KIT_FOCUS_MIN_CONCRETE_WORDS:
        raise InvalidChange(
            f'kit_focus is too generic{f" ({phrase!r})" if phrase else ""}: name the concrete thing '
            'Kit foregrounds this turn (a detail, which actor tactic gets room, how a ruling is '
            'framed, or a deliberate restraint).')


# ---------------------------------------------------------------------------
# 5. The ruling dodge
# ---------------------------------------------------------------------------
# A social turn labeled `ruling` (or given `call` scope) escapes the exchange floors.
# That is only honest when the player asked a rules or mechanics question.
RULES_CUE = re.compile(
    r"\b(can i|could i|may i|am i able|do i (need|have|get)|roll|rolls|check|dc|modifier|bonus|"
    r"advantage|disadvantage|rules?|allowed|how does|saving throw|initiative|skill|ability|"
    r"insight|perception|stealth|athletics|persuasion|deception|intimidation|sleight of hand|"
    r"investigation|proficien\w*|spell|cantrip)\b")


def check_ruling_dodge(plan, action_kind, player_action):
    if action_kind != 'social':
        return
    asked_rules = bool(RULES_CUE.search(normalize(player_action)))
    require(plan['move'] != 'ruling' or asked_rules,
            'A social bid with no rules or mechanics question is not a ruling; answer it in the '
            'fiction (npc_reply with exchange scope).')
    require(plan['public_brief']['scope'] != 'call' or asked_rules or
            plan['move'] == 'ask_clarification',
            'Call scope on a social turn needs a rules question from the player or a genuine '
            'clarification; otherwise the actor answers in an exchange.')


def check_clarification_shape(segments, plan):
    """HARD: a clarification asks the player something and is not an NPC reply in disguise."""
    if plan['move'] != 'ask_clarification':
        return
    require(any('?' in segment['text'] for segment in segments),
            'ask_clarification must actually ask the player a question')
    require(plan['public_brief']['scope'] != 'call' or
            not any(is_npc(segment['speaker']) for segment in segments),
            'A clarification call cannot carry an NPC reply; use an exchange for that')


# ---------------------------------------------------------------------------
# 6. Paraphrased leaks of hidden information (HARD)
# ---------------------------------------------------------------------------
# The literal list in kit_agent catches "marked deck". The room fixture's DM-only
# `leak_keywords` catch the paraphrase: a set leaks when a single sentence contains
# at least one word from every group, e.g. {card, deck} + {marked, nicked, shaved}.
# A set is skipped once its revealing fact is public, or when the player raised it.
def _sentence_hits(sentence, groups):
    text = ' ' + ' '.join(tokens(sentence)) + ' '
    return all(any(f' {normalize(word)} ' in text for word in group) for group in groups)


def leak_sets(source):
    """DM-only paraphrase keyword sets from the room source, with each revealing fact's text."""
    sets = []
    for name, entry in (source or {}).get('leak_keywords', {}).items():
        if not isinstance(entry, dict):
            continue  # e.g. the fixture's _note
        fact = entry.get('revealed_by')
        sets.append({'name': name, 'groups': entry['groups'],
                     'revealed_text': source['facts'][fact]['text'] if fact else None})
    return sets


def leak_phrases(source):
    """DM-only literal phrases from the room source: {phrases, player_may_name}."""
    entry = (source or {}).get('leak_phrases') or {}
    return {'phrases': [p.lower() for p in entry.get('phrases', [])],
            'player_may_name': [p.lower() for p in entry.get('player_may_name', [])]}


_NEGATION = re.compile(r"\b(not|never|no|nothing|n't)\b|n't\b")


def check_paraphrased_leaks(text, public_view, player_action, sets):
    """Applies to every speaker, Kit included: her exact-ruling voice is a leak path too.
    When the player raised the subject themselves, only a question or a denial about it
    is allowed; a statement that confirms it is still a leak."""
    public = normalize(str(public_view))
    declared = sentences(player_action or '')
    for entry in sets or ():
        if entry['revealed_text'] and normalize(entry['revealed_text']) in public:
            continue
        raised = any(_sentence_hits(sentence, entry['groups']) for sentence in declared)
        for sentence in sentences(text):
            if raised and (sentence.rstrip('"\'” )').endswith('?') or
                           _NEGATION.search(normalize(sentence))):
                continue
            if _sentence_hits(sentence, entry['groups']):
                # Name the set, never the hidden fact, so the retry reason is public-safe.
                raise InvalidChange(
                    f'Public text paraphrases a private fact (keyword set {entry["name"]!r}). Stay '
                    'with what the player can perceive.')


# ---------------------------------------------------------------------------
# 7. Player agency (HARD)
# ---------------------------------------------------------------------------
# Narration (and Kit) may say what the player perceives, never what they do, decide,
# agree to, or feel. NPCs may presume, but may not declare the player's consent,
# decision, or feelings as settled. Questions and conditional clauses are exempt.
AGENCY_LOOKBACK_WORDS = 3      # "if you agree" is conditional when if/unless/... is this close
# Words just before "you ..." that make it a condition, a question, an ability, or a
# permission rather than a statement of what the player did.
_CONDITIONALS = frozenset('if unless when whether until once should would might may could '
                          'perhaps maybe before after lest suppose supposing whatever what how '
                          'why do does did can will to let lets letting'.split())
_NARRATION_AGENCY = re.compile(
    r"\byou(?:'re| are| have| had|'ve)? (?:\w+ly )?(agree|agreed|accept|accepted|decide|decided|refuse|"
    r"refused|feel|felt|realize|realized|realise|realised|nod|nodded|smile|smiled|laugh|laughed|"
    r"shrug|shrugged|sit|sat|take a seat|pay|paid|hand over|handed|reach for|reached for|lean|"
    r"leaned|grin|grinned|relax|relaxed|hesitate|hesitated|think|thought|wonder|"
    r"wondered|remember|remembered|find yourself|found yourself|can't help|cannot help|"
    r"afraid|terrified|nervous|convinced|tempted|uneasy|impressed|charmed|intrigued|"
    r"fall silent|fell silent|comply|complied|obey|obeyed)\b")
_NPC_AGENCY = re.compile(
    r"\byou(?:'ve| have)? (agree|agreed|accept|accepted|decided|feel|felt|are afraid|are nervous|"
    r"are tempted|are convinced)\b")
_IMPOSED_BODY = re.compile(
    r"\byour (heart|pulse|stomach|breath|hand|hands|fingers|cheeks|skin) "
    r"(races|raced|pounds|pounded|sinks|sank|quickens|quickened|catches|caught|drifts|drifted|"
    r"moves|moved|tightens|tightened|flushes|flushed|crawls|crawled|itch|itches)\b|"
    r"\ba chill (runs|ran) down your spine\b")


def _conditional(sentence_norm, start):
    before = tokens(sentence_norm[:start])[-AGENCY_LOOKBACK_WORDS:]
    return bool(set(before) & _CONDITIONALS)


def check_player_agency(segments):
    for segment in segments:
        pattern = _NPC_AGENCY if is_npc(segment['speaker']) else _NARRATION_AGENCY
        for sentence in sentences(segment['text']):
            if sentence.rstrip('"\'” )').endswith('?'):
                continue
            norm = normalize(sentence)
            for found in list(pattern.finditer(norm)) + list(_IMPOSED_BODY.finditer(norm)):
                if not _conditional(norm, found.start()):
                    raise InvalidChange(
                        f'Player agency: the {segment["speaker"]} decided for the player '
                        f'("{found.group(0)}"). Say what others do and what the player perceives; '
                        'the player chooses what they do, agree to, and feel.')


# ---------------------------------------------------------------------------
# 8. Source numbers (HARD)
# ---------------------------------------------------------------------------
# Approach-range playtest: the dealer charged 12 gp for passage; the source fixes 10.
# The room fixture's DM-only `numeric_facts` name a fixed amount, its units, and the
# words that tie a sentence to it. An amount in those units, in a sentence with a
# context word, must be an allowed amount, unless the player said that number first
# (an NPC may repeat or refuse a player's own offer). Arithmetic spread across
# sentences ("ten, plus two for my trouble") is not caught.
NUMBER_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
                'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
                'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
                'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
                'hundred': 100, 'a hundred': 100, 'a dozen': 12, 'dozen': 12}
_ONES = {word: value for word, value in NUMBER_WORDS.items() if value < 20 and ' ' not in word}
_TENS = {word: value for word, value in NUMBER_WORDS.items() if value in range(20, 100, 10)}
# Coin units as people say them. Each maps to its SRD abbreviation.
COIN_UNITS = {
    'gp': 'gp', 'gold': 'gp', 'gold piece': 'gp', 'gold pieces': 'gp', 'gold coin': 'gp',
    'gold coins': 'gp', 'golds': 'gp',
    'sp': 'sp', 'silver': 'sp', 'silver piece': 'sp', 'silver pieces': 'sp', 'silver coin': 'sp',
    'silver coins': 'sp', 'silvers': 'sp',
    'cp': 'cp', 'copper': 'cp', 'copper piece': 'cp', 'copper pieces': 'cp', 'copper coin': 'cp',
    'copper coins': 'cp', 'coppers': 'cp',
    'ep': 'ep', 'electrum': 'ep', 'electrum pieces': 'ep',
    'pp': 'pp', 'platinum': 'pp', 'platinum pieces': 'pp', 'platinum coins': 'pp',
}


def _parse_number(words, start):
    """(value, end) for a spoken or written number at words[start]: "63000", "five",
    "twenty five", "a hundred and twenty", "sixty three thousand", "63 thousand"."""
    total, current, index, seen = 0, 0, start, False
    while index < len(words):
        word = words[index]
        following = words[index + 1] if index + 1 < len(words) else None
        if word.isdigit() and not seen:
            current, seen = int(word), True
        elif word in _ONES and (not seen or current % 10 == 0 and current % 100 >= 20 or current % 100 == 0):
            current, seen = current + _ONES[word], True
        elif word in _TENS and (not seen or current % 100 == 0):
            current, seen = current + _TENS[word], True
        elif word == 'hundred' and (seen or index > start):
            current, seen = (current or 1) * 100, True
        elif word == 'thousand' and (seen or index > start):
            total, current, seen = total + (current or 1) * 1000, 0, True
        elif word == 'dozen' and (seen or index > start):
            current, seen = (current or 1) * 12, True
        elif word == 'a' and not seen and following in ('hundred', 'thousand', 'dozen'):
            pass
        elif word == 'and' and seen and following and (following in _ONES or following in _TENS):
            pass
        else:
            break
        index += 1
    return (total + current, index) if seen else None


def spoken_amounts(text, units=None):
    """Every (amount, unit) coin amount in the text, however it is said: "25 gp",
    "63,000 gp", "five silver", "twenty-five gold pieces", "a hundred and ten gold".
    Numbers are whole tokens, so "25 gp" is never found inside "125 gp". `units`
    maps unit phrases to what to report (default: COIN_UNITS, to SRD abbreviations)."""
    units = COIN_UNITS if units is None else units
    cleaned = re.sub(r'(?<=\d),(?=\d{3}\b)', '', normalize(text)).replace('-', ' ')
    words = re.findall(r"\d+|[a-z]+", cleaned)
    phrases = sorted(((tuple(phrase.split()), unit) for phrase, unit in units.items()),
                     key=lambda item: -len(item[0]))
    found, index = [], 0
    while index < len(words):
        number = _parse_number(words, index)
        if not number:
            index += 1
            continue
        value, end = number
        after = end + (1 if end < len(words) and words[end] == 'more' else 0)
        unit = next((unit for phrase, unit in phrases if tuple(words[after:after + len(phrase)]) == phrase),
                    None)
        if unit is not None:
            found.append((value, unit))
        index = max(end, index + 1)
    return found


def _amounts(sentence, units):
    """Amounts in the sentence said in one of `units` (a fact's unit words)."""
    return [amount for amount, _ in spoken_amounts(sentence, {normalize(word): True for word in units})]


def numeric_facts(source):
    return {name: fact for name, fact in (source or {}).get('numeric_facts', {}).items()
            if isinstance(fact, dict)}


# An opening sentence that leads with the amount ("Thirty gold, to a jeweler", "Oh, about
# 25 gp") is an elliptical answer; "I won twenty gold tonight" is not.
ELLIPTIC_AMOUNT = re.compile(
    r"^\W*(?:(?:oh|well|only|just|about|maybe|roughly|near|nearly|call it|that'?s|it'?s|its)\W+)*"
    r"(?:an? )?(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen"
    r"|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty"
    r"|ninety|hundred|thousand|dozen)")


def check_numeric_facts(segments, facts, player_action, stake_amounts=(), game_terms=()):
    """HARD: a fixed source amount is not changed. While a table game runs, its stake
    amounts may be named in a sentence about the game (one with a game term) that is not
    about the fact itself: "The stakes are eleven gold a head" is fine, but "Win and the
    ring's yours for 11 gold" or "passage is 11 gold" still is not. Stake amounts are
    never merged into a fact's allowed amounts."""
    declared = set()
    for fact in (facts or {}).values():
        for sentence in sentences(player_action or ''):
            declared.update(_amounts(sentence, fact['unit_words']))
    stakes = set(stake_amounts or ())
    # "What is that ring worth?" / "Thirty gold, to a jeweler." An opening sentence that
    # leads with an amount answers the player's own question, so a fact the question names
    # by its specific words is in play there (generic words like "cost" do not count).
    question = ' ' + ' '.join(token for part in sentences(player_action or '')
                              if part.rstrip('"\'” )').endswith('?') for token in tokens(part)) + ' '
    asked = {name for name, fact in (facts or {}).items()
             if any(f' {normalize(word)} ' in question
                    for word in fact.get('specific_words') or fact['context_words'])}
    for segment in segments:
        parts = sentences(segment['text'])
        for index, sentence in enumerate(parts):
            words = ' ' + ' '.join(tokens(sentence)) + ' '
            if index and parts[index - 1].rstrip('"\'” )').endswith('?'):
                # "The ring? Eleven gold." answers the question just asked.
                words += ' '.join(tokens(parts[index - 1])) + ' '
            about_game = any(f' {normalize(term)} ' in words for term in game_terms or ())
            named_facts = {name for name, fact in (facts or {}).items()
                           if any(f' {normalize(word)} ' in words
                                  for word in fact.get('specific_words') or fact['context_words'])}
            for name, fact in (facts or {}).items():
                specific = fact.get('specific_words') or fact['context_words']
                answers_question = index == 0 and name in asked and ELLIPTIC_AMOUNT.match(normalize(sentence))
                # "The ring costs forty gold" names the ring, not the passage toll.
                # Generic cost/price words must not attach it to another fact.
                if named_facts and name not in named_facts and not answers_question:
                    continue
                if not answers_question and not any(f' {normalize(word)} ' in words
                                                    for word in fact['context_words']):
                    continue
                about_fact = answers_question or any(f' {normalize(word)} ' in words for word in specific)
                for amount in _amounts(sentence, fact['unit_words']):
                    if amount in fact['allowed_amounts'] or amount in declared:
                        continue
                    if amount in stakes and about_game and not about_fact:
                        continue
                    raise InvalidChange(
                        f'Source fact: the {segment["speaker"]} named {amount} '
                        f'{fact["unit_words"][0]} for {name.replace("_", " ")}; the source fixes '
                        f'{" or ".join(str(a) for a in fact["allowed_amounts"])}. Characters may '
                        'haggle in words, not change a fixed price.')


# ---------------------------------------------------------------------------
# 9. Scene fit (HARD): who the player is, what the deal was, what can be staked
# ---------------------------------------------------------------------------
# Ancestry words a line might pin on the player. The player's own ancestry, and plain
# words for it (a Harengon is rabbit-folk), are always allowed.
ANCESTRY_WORDS = (
    'elf', 'elves', 'elven', 'elvish', 'elfling', 'half-elf', 'dwarf', 'dwarven', 'human', 'halfling',
    'gnome', 'orc', 'half-orc', 'tiefling', 'dragonborn', 'goliath', 'aasimar', 'harengon', 'tabaxi',
    'kenku', 'firbolg', 'genasi', 'goblin', 'hobgoblin', 'bugbear', 'kobold', 'lizardfolk', 'tortle',
    'triton', 'warforged', 'satyr', 'owlin', 'centaur', 'minotaur', 'yuan-ti', 'githyanki', 'githzerai',
    'rabbit', 'hare', 'bunny', 'rabbitfolk', 'catfolk', 'birdfolk')
ANCESTRY_ALIASES = {
    'harengon': ('harengon', 'rabbit', 'hare', 'bunny', 'rabbitfolk'),
    'elf': ('elf', 'elves', 'elven', 'elvish'), 'dwarf': ('dwarf', 'dwarven'),
    'tabaxi': ('tabaxi', 'catfolk'), 'kenku': ('kenku', 'birdfolk'), 'owlin': ('owlin', 'birdfolk'),
    'half-elf': ('half-elf', 'elf', 'elven'), 'half-orc': ('half-orc', 'orc'),
}


def _identity_patterns(wrong):
    words = '|'.join(re.escape(word) for word in sorted(wrong, key=len, reverse=True))
    adjectives = r"(?:[\w'-]+\s+){0,3}?"
    return (
        # "You're an elf", "you are a pretty little elf"
        re.compile(rf"\byou(?:'re| are)\s+(?:a|an|some|the|one)\s+{adjectives}({words})\b"),
        # vocatives: "Sit down, elf." "Well, little elf, ..."
        re.compile(rf"(?:^|[,;:]\s*|\b(?:hey|oi|listen|well|so|now|come)\s+)(?:my\s+|dear\s+|little\s+|"
                   rf"young\s+|sweet\s+|good\s+)?({words})\s*[,!?.]"),
        # "an elf like you", "for an elf"
        re.compile(rf"\b(?:a|an)\s+{adjectives}({words})\s+like\s+you\b"),
        re.compile(rf"\bfor (?:a|an)\s+{adjectives}({words})\b(?=[^.?!]*\byou)"),
    )


_EPITHET = r"^(?:a|an)\s+(?:[\w'-]+\s+){{0,3}}?({words})\b(?:\s+(?:with|who|that|in|at|come)\b|\s*[,.!?\u2014-])"


def check_player_identity(segments, character):
    """HARD: no line calls the player something their character is not. With a
    Harengon player, "A love-struck elf with a purse to empty" (an NPC's epithet for
    the visitor) or "You're an elf" is rejected; "your elf" (a possession) is not an
    identity claim and passes. Quiet without a recorded player character."""
    ancestry = normalize((character or {}).get('ancestry'))
    if not ancestry:
        return
    allowed = set(ANCESTRY_ALIASES.get(ancestry, (ancestry,))) | {ancestry}
    wrong = [word for word in ANCESTRY_WORDS if word not in allowed]
    patterns = _identity_patterns(wrong)
    epithet = re.compile(_EPITHET.format(words='|'.join(re.escape(w) for w in sorted(wrong, key=len, reverse=True))))
    for segment in segments:
        parts = sentences(segment['text'])
        for index, sentence in enumerate(parts):
            text = normalize(sentence)
            hit = next((found for pattern in patterns for found in [pattern.search(text)] if found), None)
            if not hit and index == 0 and is_npc(segment['speaker']):
                hit = epithet.search(text)
            if hit:
                raise InvalidChange(
                    f'Scene fit: the {segment["speaker"]} calls the player "{hit.group(1)}", but the '
                    f'player character is {character.get("name") or "the player"}, a {character["ancestry"]} '
                    '(public view your_character). Get who they are right.')


CLEAN_DEAL = re.compile(
    r"\b(?:fingers|hands|wrists) (?:stay |stayed |are |were |kept |keep )?(?:clear|clean|honest|still)\b"
    r"|\bdeals? (?:it |them |the cards )?(?:clean|straight|honest|fair)(?:ly)?\b"
    r"|\bdealt (?:it |them )?(?:clean|straight|honest|honestly|fair|fairly)\b"
    r"|\b(?:clean|honest|fair|straight) deal\b|\bnot a finger (?:near|on|out of place)\b"
    r"|\bstraight off the top\b|\bevery card (?:from|off) the top\b|\boff the top,? (?:every|each) card\b"
    r"|\bthe deal (?:is|was|looks|looked|seems|seemed) (?:clean|fair|honest|straight)\b"
    r"|\bno (?:tricks?|sleight|funny business) (?:in|with) the deal\b|\bnothing (?:wrong|off|amiss) (?:with|about|in) the deal\b")
_PERCEIVED = re.compile(r"\b(?:to you|you see|you can see|you notice|you spot|you can tell|you catch|as far as you)\b")


def check_clean_deal(segments, dealer_cheated):
    """HARD: when the game state says the dealer cheated this deal, the Narrator and
    Kit cannot describe a clean one ("his fingers stay clear of the deck", "a straight
    deal"). What the player perceived may be said as perception ("nothing looks wrong
    to you"). NPCs may lie; that is theirs."""
    if not dealer_cheated:
        return
    for segment in segments:
        if segment['speaker'] not in ('Narrator', 'Kit'):
            continue
        for sentence in sentences(segment['text']):
            text = normalize(sentence)
            if CLEAN_DEAL.search(text) and not _PERCEIVED.search(text):
                raise InvalidChange(
                    f'Scene fit: the {segment["speaker"]} describes a clean deal ("{sentence[:60]}"), '
                    'but the game state says otherwise. Describe only what the player can see.')


STAKE_CUE = re.compile(
    r"\b(?:wager|wagers|wagering|stake|staking|put up|puts up|putting up|play (?:you )?for|playing for|"
    r"bet|bets|betting|throw in|throws in|toss in|in(?:to)? the (?:pot|stakes)|on the table as|as stakes|"
    r"win (?:a|the|one|this|that) (?:gambit|hand|game|round))\b")
UNCARRIED_STAKES = re.compile(
    r"\b(ring|rings|toll|tolls|passage|key|keys|bottle|cordial|door|way through|your (?:sword|blade|weapon|"
    r"horse|boots|pack|cloak|bow)|favou?r|secret|secrets)\b")


def check_stake_offers(segments, stake_unit='gp', carriable=()):
    """HARD: the card game carries gold only. An NPC who offers to stake the ring, the
    toll, passage, or anything else ("I'll stake the ring against your purse", "Win a
    gambit and the toll's waived") offers a wager the runtime cannot pay out. A pronoun
    ("put it in the pot") right after the item counts."""
    for segment in segments:
        if not is_npc(segment['speaker']):
            continue
        parts = sentences(segment['text'])
        for index, sentence in enumerate(parts):
            text = normalize(sentence)
            if not STAKE_CUE.search(text):
                continue
            item = UNCARRIED_STAKES.search(text)
            if not item and index and re.search(r"\b(it|that|them)\b", text):
                item = UNCARRIED_STAKES.search(normalize(parts[index - 1]))
            if item and item.group(1) not in carriable:
                raise InvalidChange(
                    f'Scene fit: the {segment["speaker"]} offers to stake "{item.group(1)}", but the table '
                    f'game stakes only {stake_unit}. Offer only what the game can carry.')


# ---------------------------------------------------------------------------
# 10. Numbers stay in the ledger (Brendon's table call 4, 2026-10-02)
# ---------------------------------------------------------------------------
# HARD: public text never shows a DC, an opposed number, a roll total, a modifier, or die
# math. Roll requests name the skill only; a success is told as what the character notices.
_SKILL_NAMES = (r"(?:acrobatics|animal handling|arcana|athletics|deception|history|insight|intimidation|"
                r"investigation|medicine|nature|perception|performance|persuasion|religion|sleight of hand|"
                r"stealth|survival|strength|dexterity|constitution|intelligence|wisdom|charisma|initiative)")
PUBLIC_NUMBER_PATTERNS = (
    ('a DC', re.compile(r"\bdc ?\d+|\bdifficulty (?:class )?(?:of )?\d+", re.I)),
    ('an opposed number', re.compile(r"\bvs\.? ?(?:dc ?|passive \w+ ?)?\d+|\bversus \d+|\bmeets (?:dc ?)?\d+", re.I)),
    ('a roll total', re.compile(r"\(\s*(?:passive\s+)?" + _SKILL_NAMES + r"\s+\d+", re.I)),
    ('a die expression', re.compile(r"\bd(?:4|6|8|10|12|20|100)\s*[+-]\s*\d+|\b\d+d\d+\b|\bd20\b|\bnat(?:ural)? ?(?:1|20)\b", re.I)),
)
SIGNED_MODIFIER = re.compile(
    _SKILL_NAMES + r"(?:\s+(?:check|roll|save|saving throw|bonus|modifier))?[,:]?\s*(?:at |of |is )?[+\u2212-]\s?\d+"
    + r"|[+\u2212-]\s?\d+\s+(?:to|on|in)\s+(?:your\s+)?" + _SKILL_NAMES
    + r"|\b(?:your|a|the) (?:bonus|modifier) (?:is|of) [+\u2212-]?\s?\d+", re.I)
# Reminders of the PC's own bonuses, advantage sources, or item benefits (call 4).
FEATURE_REMINDER = re.compile(
    r"\b(?:grants?|gives?|giving|grant(?:ing|s)?) (?:you )?(?:advantage|disadvantage|a bonus|a \+\d|\+\d)"
    r"|\byou(?:'ve| have)? (?:got )?(?:advantage|a \+\d+|\+\d+) (?:on|to|for)\b"
    r"|\byour (?:\w+ )?(?:bonus|modifier)\b", re.I)


def check_public_numbers(segments, rules_question=False, public_event=''):
    """HARD: no DCs, opposed totals, roll totals, modifiers, or die math in public text,
    and no reminder of the PC's bonuses or item benefits unless the player asked a rules
    question about them. The ledger keeps the numbers (KRABS section 12)."""
    texts = [('accepted event', public_event or '')] + [(segment['speaker'], segment['text']) for segment in segments]
    for speaker, text in texts:
        for name, pattern in PUBLIC_NUMBER_PATTERNS:
            found = pattern.search(text or '')
            require(not found, f'Numbers stay in the ledger: the {speaker} shows {name} ("{found and found.group(0)}"). '
                    'Name the skill only, and tell the result as what the character notices.')
        if rules_question:
            continue
        found = SIGNED_MODIFIER.search(text or '')
        require(not found, f'Numbers stay in the ledger: the {speaker} states a modifier ("{found and found.group(0)}"). '
                'A roll request names the skill only.')
        if speaker in ('Kit', 'Narrator'):
            found = FEATURE_REMINDER.search(text or '')
            require(not found, f'No bonus or feature reminders: the {speaker} restates the character\'s own '
                    f'bonuses ("{found and found.group(0)}"). Say it only when the player asks a rules question.')


# ---------------------------------------------------------------------------
# 11. A room with no refreshment (Brendon's table call 3)
# ---------------------------------------------------------------------------
REFRESHMENT = re.compile(r"\b(wine|ale|beer|mead|cordial|liquor|spirits|brandy|whisk(?:e)?y|drinks?|cups?|glass(?:es)?|"
                         r"goblets?|mugs?|flasks?|tankards?|bottles?|food|bread|meat|cheese|snacks?|refreshments?|"
                         r"water|tea|stew|meal|supper|dinner)\b")
SERVING = re.compile(r"\b(pour\w*|serv\w*|offer\w*|hand(?:s|ed|ing)?|pass(?:es|ed|ing)?|slid\w*|slide\w*|fill\w*|"
                     r"refill\w*|top(?:s|ped)? up|sip\w*|drink\w*|drank|eat\w*|ate|nibbl\w*|toast\w*|raise\w* (?:a|his|her|their)|"
                     r"have (?:a|some)|help yourself|try (?:a|some|the))\b")
REFRESHMENT_NEGATED = re.compile(r"\b(no|not|none|nothing|never|without|empty|dry|run out|ran out|gone|"
                                 r"don'?t|do not|haven'?t|have not|can'?t|cannot|no longer|nor|neither|lack\w*)\b")


def check_no_refreshment(segments):
    """HARD where the area says so: no public line serves, offers, or shows food or drink.
    Saying there is none (the cellar is dry, nothing to offer) is the clue, and passes."""
    for segment in segments:
        for sentence in sentences(segment['text']):
            text = normalize(sentence)
            if REFRESHMENT.search(text) and SERVING.search(text) and not REFRESHMENT_NEGATED.search(text):
                raise InvalidChange(
                    f'Room fit: the {segment["speaker"]} serves or shows food or drink ("{sentence[:60]}"), but '
                    'nobody here eats or drinks. Say there is none, or leave it out.')


# ---------------------------------------------------------------------------
# 12. The toll is an exchange, not a price tag (Brendon's table call 6)
# ---------------------------------------------------------------------------
TOLL_WORDS = re.compile(r"\b(toll|passage|fee|to pass|way through|safe passage|a head|per head)\b")
TOLL_GAME_WORDS = re.compile(r"\b(game|games|cards?|ante|deal|dealt|gambling|gamble|blind|bet|wager|play)\b")


def check_toll_exchange(segments, amount, raised):
    """HARD: the first time the toll is named with its amount, an NPC makes the demand
    (never the Narrator or Kit), the line is not tossed in beside game talk, and it leaves
    the player an opening (a question). Once raised, the exchange goes on in any words."""
    if raised or not amount:
        return
    for segment in segments:
        parts = sentences(segment['text'])
        for index, sentence in enumerate(parts):
            said = {value for value, _ in spoken_amounts(sentence)}
            if amount not in said or not TOLL_WORDS.search(normalize(sentence)):
                continue
            require(is_npc(segment['speaker']),
                    f'The toll is an NPC\'s demand: the {segment["speaker"]} names it ("{sentence[:60]}"). Let the '
                    'NPC who wants it make the demand, with their reason.')
            around = ' '.join(normalize(part) for part in parts[max(0, index - 1):index + 1])
            require('?' in segment['text'] and not TOLL_GAME_WORDS.search(around),
                    f'The toll is a real exchange, not a line beside the game: the {segment["speaker"]} names it '
                    'in passing. Make the demand its own beat, with a reason in character and an opening '
                    'for the player to answer.')
