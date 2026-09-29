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

NPC_SPEAKERS = ('Dealer', 'Card player')   # room adapter: speakers voiced from actor cards
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


def check_padding(segments, player_action, action_kind, public_history=()):
    """Reject crude padding: repetition, restating the player, recycled lines, filler."""
    seen = {}
    for segment in segments:
        for run in ngrams(tokens(segment['text']), PADDING_REPEAT_RUN_WORDS):
            if run in seen and len(content_words(run)) >= 2:
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
        recycled = {run for run in recycled if len(content_words(run)) >= 2}
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
    'noted', 'terrible', 'fascinating', 'delightful', 'brave', 'cute'))
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
VOICE_CONTRACT_FIELDS = ('rhythm', 'register', 'tics', 'never_says', 'wants')


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
        if segment['speaker'] in NPC_SPEAKERS:
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
        if segment['speaker'] not in NPC_SPEAKERS:
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


def check_voice_contracts(actor_cards):
    """Every speaking NPC card carries a distinct voice contract (fail loud at prepare)."""
    contracts = {}
    for speaker in NPC_SPEAKERS:
        card = (actor_cards or {}).get(speaker)
        if card is None:
            continue
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
            not any(segment['speaker'] in NPC_SPEAKERS for segment in segments),
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


def check_paraphrased_leaks(text, public_view, player_action, sets):
    public = normalize(str(public_view))
    declared = sentences(player_action or '')
    for entry in sets or ():
        if entry['revealed_text'] and normalize(entry['revealed_text']) in public:
            continue
        if any(_sentence_hits(sentence, entry['groups']) for sentence in declared):
            continue
        for sentence in sentences(text):
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
        pattern = _NPC_AGENCY if segment['speaker'] in NPC_SPEAKERS else _NARRATION_AGENCY
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
