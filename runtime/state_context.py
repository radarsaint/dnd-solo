"""D&D Solo feasibility prototype: trusted DM backend, not a complete game.

Python standard library only. All write operations are for an adjudicating DM
or future validated server adapter, never direct player tool access.
"""
import copy
import hashlib
import json
import re
import secrets
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PERSONALITY_CORE = PROJECT_ROOT / 'docs/personality/dm-personality-core.md'
# Brendon's Halaster and Mad Mage lines, verbatim, for Mad Mage rooms only (is_mad_mage).
MAD_MAGE_ADDENDUM = PROJECT_ROOT / 'docs/personality/dm-personality-mad-mage.md'
# Distilled voice files (docs/voice/*.md, not README.md) join the personality core every
# turn, in file-name order, so both stages read them (the performer most). Whole files load
# until VOICE_MAX_BYTES; any that do not fit are skipped and voice_warning says so. They
# count toward the context budgets like the rest of the core; both budgets grow by the cap.
VOICE_DIR = PROJECT_ROOT / 'docs/voice'
VOICE_MAX_BYTES = 6000
VOICE_HEADING = '\n\n# Voice files (docs/voice)\n'


def voice_files(folder=None):
    folder = Path(folder or VOICE_DIR)
    if not folder.is_dir():
        return []
    return sorted((p for p in folder.glob('*.md') if p.name.lower() != 'readme.md'), key=lambda p: p.name)


def load_voice(folder=None, max_bytes=None):
    """(text, warning): the voice files that fit the cap, and a warning naming any skipped."""
    max_bytes = VOICE_MAX_BYTES if max_bytes is None else max_bytes
    parts, skipped, used = [], [], 0
    for path in voice_files(folder):
        part = f'\n## {path.name}\n\n' + path.read_text(encoding='utf-8').strip() + '\n'
        size = len(part.encode())
        if skipped or used + size > max_bytes:
            skipped.append(path.name)
            continue
        parts.append(part)
        used += size
    warning = (f'Voice files over the {max_bytes}-byte cap were not loaded: {", ".join(skipped)}. '
               'Shorten or merge docs/voice files.') if skipped else None
    return ''.join(parts), warning


def personality_core_text(folder=None, source=None):
    """The personality core plus the voice files that fit the cap. A Mad Mage room (``source``
    id starting dotmm) also gets the Mad Mage addendum after the core; no other room does."""
    core = PERSONALITY_CORE.read_text(encoding='utf-8')
    if source is not None and is_mad_mage(source):
        core = core.rstrip('\n') + '\n\n' + MAD_MAGE_ADDENDUM.read_text(encoding='utf-8')
    voice, _ = load_voice(folder)
    return core + VOICE_HEADING + voice if voice else core
RHYTHM_EVIDENCE_MAX_CHARS = 600  # per recent_rhythm entry; 12 entries stay inside context()
# Byte budget for one model input. context() enforces it on the core + DM context; the
# Kit bridge trims memory to keep each whole prepared input inside it (kit_agent.fit_to_budget).
# Sized for the worst case (ContextBudgetTests.test_a_long_card_game_with_a_full_detail_ledger_fits):
# 12 long turns, a Three-Dragon Ante gambit mid-play, and a full canon ledger (CANON_LIMIT
# entries at maximum length, ~47 KB). The private floor after every memory trim is ~79 KB.
# +5 KB for the room's story brief (runtime/kit_brief.py; the 6c brief measures ~4.6 KB).
# +2 KB (2026-10-03, main 8f2ad2e): Brendon's dm-personality-core grew by 14 lines (~1.7 KB);
# the worst case with a full voice slot measured 1.7 KB over on main itself.
# +1 KB for NPC attitudes (dm_only.attitudes_here and the ATTITUDES rule, runtime/kit_attitude.py).
# +2 KB (2026-10-04, PR #87, Brendon): room headroom. A room at both of its context caps
# (kit_rooms.DM_ONLY_ROOM_MAX_BYTES, CLAIMS_HERE_MAX_BYTES) in the suite's worst case comes to
# ~103,475 B; the personality core is not trimmed to make room. Overflow still fails loudly.
CONTEXT_BUDGET_BYTES = 99000 + VOICE_MAX_BYTES  # 105 KB: worst case, story brief, core growth, attitudes, full voice slot, room headroom
# (88 KB -> 89 KB, 2026-10-03: area 6c gained the vampire_tells fact and claim, table call 8).
# A staged or one-pass body carries the post-event public view (with the whole ledger)
# and the procedure state: ~49.4 KB in the same worst case.
PENDING_TURN_MAX_BYTES = 64000
CANON_BASIS_MAX_CHARS = 200

# Version 2 adds Kit's player_notes and richer episodes (player_bid, kit_choice,
# actor and story thread). Older snapshots are upgraded in memory on load; the
# stored history is never rewritten, and the next commit saves the new shape.
STATE_SCHEMA_VERSION = 2
KIT_EPISODE_LIMIT = 24       # stored; the decision sees a relevance-selected subset
PLAYER_NOTE_LIMIT = 8
PLAYER_NOTE_MAX_CHARS = 300
PLAYER_NOTE_MAX_EVIDENCE = 4
PLAYER_NOTE_SOURCES = ('observed', 'feedback')
# Refused attempts (pending rulings on in-fiction actions) kept in public state so a
# later turn can refer to them. Nothing about the world changes when one is recorded.
REFUSED_ATTEMPT_LIMIT = 4
REFUSED_ATTEMPT_MAX_CHARS = 300
# The canon ledger: details the source does not supply that the DM established in play
# (runtime/kit_detail.py), keyed by slot ("actor:uktarl/drink", "area_06c/card_table/game").
# Persisted so an invented answer stays true later; a change needs an in-story reason and
# keeps the superseded fact.
CANON_LIMIT = 48
CANON_KINDS = ('object', 'drink_food', 'appearance', 'name', 'price', 'inscription',
               'procedure', 'history', 'other')
CANON_SCOPES = ('scene', 'location', 'actor', 'campaign')
CANON_SLOT = re.compile(r'^[a-z0-9_:]+(/[a-z0-9_]+){1,3}$')
# Events a Kit turn may add at commit, after the adjudicated batch it was prepared with:
# the decision's canon entries, the oracle deal it consumed, and procedure state.
# Host bookkeeping, not a turn taken in the room (kit_rooms.stage counts the others).
BOOKKEEPING_EVENTS = ('party_roster', 'player_sheet', 'player_character', 'player_note', 'pc_state', 'kit_plan', 'rest',
                      'campaign_restore')
# A refused attempt changed nothing in the world, so it does not use up the check Kit just
# called (PR 145 playtest: one refused line, then every roll was refused).
KEEPS_PENDING_CHECK = BOOKKEEPING_EVENTS + ('refused_attempt',)
# A pending check's optional fields: a held exit, and room for the check-calling follow-up's
# quiet DC adjustment for creative use of the scene (Brendon: about -2) with its reason. Not
# applied anywhere yet.
PENDING_CHECK_OPTIONAL = {'exit', 'dc_adjust', 'reason', 'threshold', 'held', 'dc', 'action'}
# ``action``: the act a check the engine itself called waits on (the act needs the PC's roll and
# the engine never rolls for them); the player's roll resolves it (LET_IT_RIDE.md).
# A standing check (Let It Ride): an established result that holds while the PC keeps at the same
# endeavor, in state['standing_check']; the event with check None clears it.
STANDING_CHECK_KEYS = {'skill', 'total', 'die', 'modifier', 'area', 'route', 'against', 'approach', 'since'}
# A heavy turn Kit opened on a check call holds its description for the roll (kit_agent.STALL_KINDS).
HELD_KINDS = ('opening', 'exit', 'threshold_look')
# What the engine's outcome of a declared act may add (runtime/kit_acts.py: handles).
DECLARED_EVENTS = ('beat', 'reveal_fact', 'trigger_fired', 'scene_state', 'combat_state', 'actor_status',
                   'pc_conditions')
COMMIT_APPENDED_EVENTS = ('canon_entry', 'oracle_draw', 'procedure_state', 'claim_said', 'agenda_turn',
                          'pc_state', 'kit_plan', 'toll_state', 'story_beat', 'threshold_crossed',
                          'attitude_shift', 'pending_check', 'open_threads', 'risk_warned')
# A turn whose decision asks the player a question resolves nothing: its only event is a
# rhythm beat tagged 'asked' whose evidence is the question.
ASKED_EVENT_PREFIX = 'Kit asks before resolving: '
EPISODE_DEFAULTS = {'player_bid': None, 'kit_choice': None, 'actor_ref': None,
                    'story_anchor': None, 'story_basis': None}
# Notes describe what the player did or said. They are not a relationship meter.
_SCORE_PATTERN = r'\b\d+\s*(/|out of)\s*\d+\b|%|\b(score|meter|affection|rating)\b'


_FACT_QUOTES = str.maketrans({'\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"'})


def normalize_fact(text):
    """The one comparison form for canon facts, used by the runtime ledger and the
    detail validator alike: curly quotes straightened, case folded, whitespace
    collapsed, and trailing sentence punctuation dropped. "The toll is 10 gp." and
    "the toll is 10 gp" are the same fact; "10 gp" and "12 gp" are not."""
    text = ' '.join((text or '').translate(_FACT_QUOTES).casefold().split())
    return text.rstrip(' .!;')


def check_player_character(character):
    require(isinstance(character, dict) and set(character) == {'name', 'ancestry', 'class', 'level'},
            'A player character records name, ancestry, class, and level')
    for key in ('name', 'ancestry'):
        require(isinstance(character[key], str) and 0 < len(character[key].strip()) <= 60,
                f'Player character {key} must be 1-60 characters')
    require(character['class'] is None or (isinstance(character['class'], str) and
                                           0 < len(character['class'].strip()) <= 60),
            'Player character class must be 1-60 characters or omitted')
    require(character['level'] is None or (type(character['level']) is int and 1 <= character['level'] <= 20),
            'Player character level must be 1-20 or omitted')


FIRST_SCENE = 'scene-1'


def current_scene(state):
    """The open scene's id (KRABS §8). A state from before scene ids is in its first scene."""
    return (state or {}).get('scene_id') or FIRST_SCENE


def canon_in_scope(state):
    """Canon entries that apply here: this location's, present actors', campaign-wide, and this
    scene's own (a scene-scoped entry is valid only in the scene that made it, KRABS §8: a
    later scene in the same room does not inherit it)."""
    area = state['area']
    scene = current_scene(state)
    present = {key for key, actor in state.get('actors', {}).items()
               if actor.get('location') == area and actor.get('status') not in ('fled', 'hidden')}
    kept = {}
    for slot, entry in (state.get('canon') or {}).items():
        scope, subject = entry.get('scope'), slot.split('/')[0]
        if scope == 'campaign' or \
                (scope == 'actor' and subject.startswith('actor:') and subject[6:] in present) or \
                (scope == 'location' and entry.get('area') == area) or \
                (scope == 'scene' and entry.get('area') == area and entry.get('scene', FIRST_SCENE) == scene):
            kept[slot] = entry
    return kept


class InvalidChange(ValueError):
    pass


class StaleTurn(InvalidChange):
    pass


class HostSequenceError(InvalidChange):
    """The host called the bridge out of order or with an unknown or finished turn ID.
    `next_step` names what to do instead, so the CLI can hand it back verbatim."""
    def __init__(self, message, next_step):
        super().__init__(message)
        self.next_step = next_step


HIDING_MARKS = ('hidden', 'invisible', 'concealed', 'unseen')
GONE_STATUSES = ('dead', 'fled', 'destroyed')


def unperceived(actor):
    """True for a creature still there that the PC cannot perceive now, whatever marks it: the
    room schema's status "hidden" (until a trigger) or "visible": false, or a hidden / invisible /
    concealed / unseen flag set true, or a condition of those names. Pass the source actor merged
    with its state. Dead, fled and destroyed creatures are not "there"."""
    actor = actor or {}
    if actor.get('status') in GONE_STATUSES:
        return False
    if actor.get('status') == 'hidden' or actor.get('visible') is False:
        return True
    if any(actor.get(mark) is True for mark in HIDING_MARKS):
        return True
    return any(str(c).casefold() in HIDING_MARKS for c in actor.get('conditions') or ())


def reveal_actor(actor, spec=None):
    """Clear every hiding marker on the state actor (a trigger's reveal): status hidden -> alive,
    visible true, each hiding flag false (also those only the room spec carries), and the hiding
    names dropped from conditions. Other conditions (prone) stay."""
    merged = {**(spec or {}), **actor}
    if actor.get('status') == 'hidden' or (spec or {}).get('status') == 'hidden' and 'status' not in actor:
        actor['status'] = 'alive'
    actor['visible'] = True
    for mark in HIDING_MARKS:
        if merged.get(mark):
            actor[mark] = False
    if merged.get('conditions'):
        actor['conditions'] = [c for c in merged['conditions'] if str(c).casefold() not in HIDING_MARKS]


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def require(condition, message):
    if not condition:
        raise InvalidChange(message)


def upgrade_state(state):
    """Bring an older snapshot up to STATE_SCHEMA_VERSION without inventing history.

    Version 1 Kit state had only episodes and current_appraisal. Missing episode
    fields are filled with None (unknown), never guessed from other fields.
    """
    if state.get('schema_version', 1) >= STATE_SCHEMA_VERSION:
        return state
    kit = state.setdefault('kit', {})
    kit.setdefault('episodes', [])
    kit.setdefault('current_appraisal', None)
    kit.setdefault('player_notes', [])
    for episode in kit['episodes']:
        for key, default in EPISODE_DEFAULTS.items():
            episode.setdefault(key, default)
    state['schema_version'] = STATE_SCHEMA_VERSION
    return state


def check_player_note_text(text):
    require(isinstance(text, str) and 0 < len(text.strip()) <= PLAYER_NOTE_MAX_CHARS,
            f'A player note must be 1–{PLAYER_NOTE_MAX_CHARS} characters')
    require(re.search(_SCORE_PATTERN, text.casefold()) is None,
            'A player note records observed behavior or feedback, not a score or meter')


def is_mad_mage(source):
    """A Dungeon of the Mad Mage room (its id starts with dotmm, as the area 6c regression fixture's does).
    Only these may carry Mad Mage wording; Kit is a general DM."""
    return str(source.get('id') or '').startswith('dotmm')


def source_constraint(source):
    """The packet's source line, named for the room's own adventure, never assumed to be Mad Mage."""
    ref = source.get('source_ref')
    if not ref:
        return 'This synthetic fixture is not canon for any published adventure and is not a campaign save.'
    if is_mad_mage(source):
        return 'This is a conditional test snapshot grounded in the cited Mad Mage source, not a campaign save.'
    title = str(ref).split(' / ')[0].strip()
    return (f'This room is grounded in the cited adventure source ({title}); '
            'do not add to it from other adventures.')


class Runtime:
    def __init__(self, path):
        self.path = path  # the session dir is its parent (kit_handoff's trace lives there)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS source (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS snapshots (revision INTEGER PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, digest TEXT NOT NULL, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY, turn_id TEXT NOT NULL REFERENCES turns(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS kit_turns (turn_id TEXT PRIMARY KEY REFERENCES turns(id), body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS kit_pending (
                turn_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                body TEXT NOT NULL, plan TEXT
            );
            -- Refused attempts that arrived while a prepared turn was waiting: held here, not
            -- committed, so that turn's revision stays current (#150 retest).
            CREATE TABLE IF NOT EXISTS queued_attempts (
                seq INTEGER PRIMARY KEY, action TEXT NOT NULL, ruling TEXT NOT NULL
            );
            -- Timing telemetry is deliberately outside turns/ledger/kit_turns: it never
            -- enters a turn digest, so an identical retry stays idempotent.
            -- The last full packet issued for a pending one-pass turn, for rehydrate (a host that
            -- lost it, e.g. the one a window answer returns). Rows of finished turns are pruned.
            CREATE TABLE IF NOT EXISTS kit_packets (turn_id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS kit_telemetry (
                seq INTEGER PRIMARY KEY, turn_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS immutable_ledger_update BEFORE UPDATE ON ledger
                BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_ledger_delete BEFORE DELETE ON ledger
                BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
        """)

    def close(self):
        self.db.close()

    def _check_source(self, source):
        """The room's graph and DM prep, checked before it is played (initialize and reload)."""
        for exit_id, edge in source['exits'].items():
            require(len(edge['areas']) == 2 and len(set(edge['areas'])) == 2,
                    'Each exit must connect two distinct areas')
            require(all(a in source['areas'] for a in edge['areas']), 'Unknown exit endpoint')
        for fact in source['facts'].values():
            require(fact['area'] in source['areas'], 'Unknown fact area')
        for actor in source['actors'].values():
            require(actor['location'] in source['areas'], 'Unknown actor area')
        # DM prep is checked once, before play: the texture palette (roots, no prices, no
        # leaks) and every table procedure's config. Local import: both import this module.
        from . import kit_agenda, kit_attitude, kit_cards, kit_claims, kit_toll
        # The texture palette is checked lazily, per area, the first time play draws on it
        # (kit_texture.area_palette): it never delays the first framing (ROOM_LOADER.md).
        kit_attitude.compile_attitudes(source)
        kit_claims.compile_claims(source)
        kit_agenda.compile_agenda(source)
        kit_toll.compile_tolls(source)
        for key, config in (source.get('procedures') or {}).items():
            if not key.startswith('_') and config.get('kind') == 'card_game':
                kit_cards.check_config(config)

    def initialize(self, source, area, room_path=None):
        """Create a fresh fixture session. Refuse to overwrite a running game. ``room_path``:
        the room file it was mounted from (kit_rooms), kept in the first snapshot."""
        require(self.db.execute('SELECT 1 FROM source').fetchone() is None,
                'This database already holds a game.')
        require(area in source['areas'], 'Unknown starting area')
        self._check_source(source)
        state = {
            'schema_version': STATE_SCHEMA_VERSION, 'area': area, 'elapsed_seconds': 0,
            'scene_id': FIRST_SCENE, 'visited': [area], 'known_facts': [], 'known_exits': [],
            'actors': copy.deepcopy(source['actors']),
            'resources': copy.deepcopy(source['resources']), 'rhythm': [],
            'kit': {'episodes': [], 'current_appraisal': None, 'player_notes': []},
            'roll_seed': secrets.token_hex(16),
            'room': {'id': source.get('id'), 'path': str(room_path) if room_path else None, 'turns_in': {}},
        }
        self._observe(state, source)
        with self.db:
            self.db.execute('INSERT INTO source VALUES (1, ?)', (encode(source),))
            self.db.execute('INSERT INTO snapshots VALUES (0, ?)', (encode(state),))

    def reload_room(self, new_source, room_path=None):
        """Swap in an edited copy of the room this game is playing, mid-game (PR 145 playtest
        bug 10: adding a claim meant a new database and lost episodes). Safe only when it is
        the same room (same id), the PC's area still exists, and no prepared turn is waiting.
        Progress carries over: known facts and exits, visited areas, actors as they stand, Kit's
        memory. Ids the edit removed are dropped; new actors and resources start as written.
        Returns the new revision, or None when the room is unchanged."""
        old = self.source()
        if encode(old) == encode(new_source):
            return None
        require(new_source.get('id') == old.get('id'),
                f"Reload only the room being played ({old.get('id')!r}); this file is {new_source.get('id')!r}. "
                'Use a new --db to start a different room.')
        require(self.db.execute('SELECT 1 FROM kit_pending').fetchone() is None,
                'Finish or abandon the prepared turn before reloading the room.')
        revision, state = self.load()
        require(state['area'] in new_source['areas'],
                f"The edited room no longer has the PC's area {state['area']!r}.")
        self._check_source(new_source)
        new = copy.deepcopy(state)
        new['known_facts'] = [k for k in new['known_facts'] if k in new_source['facts']]
        new['known_exits'] = [k for k in new['known_exits'] if k in new_source['exits']]
        new['visited'] = [a for a in new['visited'] if a in new_source['areas']]
        actors = {k: v for k, v in new['actors'].items() if k in new_source['actors']}
        for key, actor in new_source['actors'].items():
            actors.setdefault(key, copy.deepcopy(actor))
        new['actors'] = actors
        new['resources'] = {**copy.deepcopy(new_source.get('resources') or {}), **new['resources']}
        if room_path:
            new.setdefault('room', {})['path'] = str(room_path)
        self._observe(new, new_source)
        body = encode(new_source)
        turn_id = 'room_reload:' + hashlib.sha256(body.encode()).hexdigest()[:16]
        event = {'type': 'beat', 'tags': ['room_reloaded'],
                 'evidence': f'The room file was edited and reloaded mid-game ({room_path or old.get("id")}).'}
        with self.db:
            self.db.execute('UPDATE source SET body=? WHERE id=1', (body,))
            self.db.execute('INSERT INTO turns VALUES (?, ?, ?)', (turn_id, turn_id, revision + 1))
            self.db.execute('INSERT INTO ledger(turn_id, body) VALUES (?, ?)', (turn_id, encode(event)))
            self.db.execute('INSERT INTO snapshots VALUES (?, ?)', (revision + 1, encode(new)))
        return revision + 1

    def source(self):
        row = self.db.execute('SELECT body FROM source WHERE id=1').fetchone()
        require(row is not None, 'Initialize a session first')
        return json.loads(row[0])

    def load(self):
        row = self.db.execute('SELECT revision, body FROM snapshots ORDER BY revision DESC LIMIT 1').fetchone()
        require(row is not None, 'Initialize a session first')
        state = upgrade_state(json.loads(row[1]))
        claims = state.get('claims')
        if claims is not None and 'established' not in claims:
            # Older saves retained only 32 said records. Recover first definitions
            # from the append-only ledger, including those outside that window.
            established = {}
            for (body,) in self.db.execute(
                    "SELECT body FROM ledger WHERE json_extract(body, '$.type') = 'claim_said' ORDER BY seq"):
                said = json.loads(body)['said']
                if said.get('claim') == 'new' and said.get('new'):
                    definition = said['new']
                    established.setdefault(definition['about'].strip().casefold(), definition)
            claims['established'] = established
        return row[0], state

    @staticmethod
    def _observe(state, source):
        # Fixture visibility is explicit. A production adapter must supply perception,
        # light, concealment, and discovery rulings before accepting a reveal.
        for key, fact in source['facts'].items():
            if fact['area'] == state['area'] and fact['visible'] and key not in state['known_facts']:
                state['known_facts'].append(key)
        for key, edge in source['exits'].items():
            if state['area'] in edge['areas'] and not edge['secret'] and key not in state['known_exits']:
                state['known_exits'].append(key)

    def commit(self, turn_id, expected_revision, events):
        """Atomically accept an adjudicated event batch; safe to retry identically."""
        return self._commit(turn_id, expected_revision, events)

    def commit_kit_turn(self, turn_id, expected_revision, events, record, consume_pending=False):
        """Commit world events, a private Kit episode, and the public turn together."""
        require(isinstance(record, dict), 'Kit turn record required')
        require(isinstance(record.get('player_input'), str) and record['player_input'].strip(),
                'Player input required')
        require(isinstance(record.get('public_event'), str) and record['public_event'].strip(),
                'Public event required')
        require(isinstance(record.get('spoken'), str) and record['spoken'].strip(),
                'Player-facing turn required')
        trace = record.get('trace')
        require(isinstance(trace, dict) and isinstance(trace.get('appraisal'), dict)
                and isinstance(trace.get('observed_event'), str)
                and isinstance(trace.get('move'), str), 'Private Kit decision required')
        require(all(len(encode(record[key]).encode()) <= 12000 for key in
                    ('player_input', 'public_event', 'spoken', 'trace')), 'Kit turn exceeds size limit')
        return self._commit(turn_id, expected_revision, events, record, consume_pending)

    def commit_engine_interstitial(self, turn_id, expected_revision, events, record, consume_pending=False):
        """Commit a checkpoint the engine raised (kit_combat: a reaction window, a flourish
        handoff) with no model turn. It joins the public history so Kit sees it next turn;
        Kit's own appraisal, episodes and notes are untouched (she made no decision)."""
        require(isinstance(record, dict) and record.get('engine_checkpoint') is True and
                record.get('turn_role') == 'interstitial' and isinstance(record.get('interstitial'), dict),
                'Interstitial record required')
        for key in ('player_input', 'public_event', 'spoken'):
            require(isinstance(record.get(key), str) and record[key].strip(), f'{key} required')
        require(len(encode(record).encode()) <= 12000, 'Interstitial exceeds size limit')
        revision = self._commit(turn_id, expected_revision, events, record)
        if consume_pending:  # the window turn Kit voiced was staged under this id
            with self.db:
                self.db.execute('DELETE FROM kit_pending WHERE turn_id=?', (turn_id,))
        return revision

    def stage_kit_turn(self, turn_id, expected_revision, body):
        """Save an uncommitted chat turn so a host can perform the two model stages."""
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        require(isinstance(body, dict), 'Pending turn body required')
        serialized = encode(body)
        require(len(serialized.encode()) <= PENDING_TURN_MAX_BYTES, 'Pending turn exceeds size limit')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM turns WHERE id=?', (turn_id,)).fetchone() is not None:
                raise HostSequenceError(
                    f'Turn ID already committed: {turn_id!r} is a finished turn. Use a new turn_id '
                    'for a new player action.', 'prepare_new_turn')
            revision, _ = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            row = self.db.execute('SELECT revision, body FROM kit_pending WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            if row:
                if row != (expected_revision, serialized):
                    raise HostSequenceError(
                        f'Turn ID already staged differently: {turn_id!r} is pending for another '
                        'action or revision. Finish or abandon it, or prepare with a new turn_id.',
                        'new_turn_id_or_abandon')
            else:
                self.db.execute('INSERT INTO kit_pending VALUES (?, ?, ?, NULL)',
                                (turn_id, expected_revision, serialized))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def pending_kit_turn(self, turn_id):
        row = self.db.execute('SELECT revision, body, plan FROM kit_pending WHERE turn_id=?',
                              (turn_id,)).fetchone()
        if row is None:
            committed = self.db.execute('SELECT revision FROM turns WHERE id=?', (turn_id,)).fetchone()
            if committed:
                raise HostSequenceError(
                    f'No pending Kit turn with that ID: {turn_id!r} was already committed at revision '
                    f'{committed[0]}. Do not resubmit it; prepare the next player action with a new '
                    'turn_id.', 'prepare_new_turn')
            raise HostSequenceError(
                f'No pending Kit turn with that ID: {turn_id!r} was never prepared, or was abandoned. '
                'Call prepare first and use the turn_id it returns.', 'prepare')
        return {'revision': row[0], 'body': json.loads(row[1]),
                'plan': json.loads(row[2]) if row[2] is not None else None}

    def save_kit_packet(self, turn_id, packet):
        """Keep the full packet just issued for a pending turn, replacing an earlier one."""
        with self.db:
            self.db.execute('DELETE FROM kit_packets WHERE turn_id NOT IN (SELECT turn_id FROM kit_pending)')
            self.db.execute('INSERT OR REPLACE INTO kit_packets(turn_id, body) VALUES (?, ?)',
                            (turn_id, encode(packet)))

    def kit_packet(self, turn_id):
        """The full packet last issued for a turn that is still pending, else None."""
        row = self.db.execute('SELECT p.body FROM kit_packets p JOIN kit_pending k USING (turn_id) '
                              'WHERE p.turn_id=?', (turn_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def discard_pending_kit_turn(self, turn_id):
        """Drop an uncommitted staged turn (nothing in the world or ledger changes)."""
        self.pending_kit_turn(turn_id)  # clear error when unknown or already committed
        with self.db:
            self.db.execute('DELETE FROM kit_pending WHERE turn_id=?', (turn_id,))

    def committed_kit_turn(self, turn_id):
        """The committed public record and revision for a turn ID, or None."""
        row = self.db.execute('''SELECT kit_turns.body, turns.revision FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id WHERE kit_turns.turn_id=?''',
                              (turn_id,)).fetchone()
        return {**json.loads(row[0]), 'revision': row[1]} if row else None

    def save_kit_plan(self, turn_id, expected_revision, plan):
        serialized = encode(plan)
        require(len(serialized.encode()) <= 12000, 'Private Kit decision exceeds size limit')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            revision, _ = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            row = self.db.execute('SELECT revision, plan FROM kit_pending WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            require(row is not None and row[0] == expected_revision, 'No matching pending Kit turn')
            require(row[1] is None or row[1] == serialized, ('Private decision already fixed for this turn: a retry keeps the same decision and changes only '
                     'the performance. Resubmit the decision you first sent, unchanged.'))
            if row[1] is None:
                self.db.execute('UPDATE kit_pending SET plan=? WHERE turn_id=?',
                                (serialized, turn_id))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit(self, turn_id, expected_revision, events, kit_record=None, consume_pending=False):
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        require(type(expected_revision) is int and expected_revision >= 0, 'Invalid revision')
        require(isinstance(events, list) and 0 < len(events) <= 100, 'Expected 1–100 events')
        payload = events if kit_record is None else {'events': events, 'kit_record': kit_record}
        digest = hashlib.sha256(encode(payload).encode()).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior = self.db.execute('SELECT digest, revision FROM turns WHERE id=?', (turn_id,)).fetchone()
            if prior:
                require(prior[0] == digest, 'Turn ID already used with different events')
                self.db.rollback()
                return prior[1]
            revision, state = self.load()
            if revision != expected_revision:
                raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
            if consume_pending:
                pending = self.db.execute('SELECT revision, body, plan FROM kit_pending WHERE turn_id=?',
                                          (turn_id,)).fetchone()
                require(pending is not None and pending[0] == expected_revision and
                        pending[2] == encode(kit_record['trace']), 'Pending Kit decision changed')
                staged = json.loads(pending[1])
                prepared = staged['events']
                asked = isinstance(kit_record['trace'].get('ask_player'), dict)
                # An act Kit declared (runtime/kit_acts.py) appends the engine's outcome of it.
                declared = bool(kit_record.get('declared'))
                require(staged['action'] == kit_record['player_input'] and
                        (asked and events == [{'type': 'beat', 'tags': ['asked'],
                                                'evidence': kit_record['public_event']}] and kit_record['public_event'].startswith(ASKED_EVENT_PREFIX) or
                         not asked and (staged['public_event'] == kit_record['public_event'] or
                                        declared and kit_record['public_event'].startswith(staged['public_event'])) and
                         events[:len(prepared)] == prepared and
                         all(event.get('type') in COMMIT_APPENDED_EVENTS + (DECLARED_EVENTS if declared else ())
                             for event in events[len(prepared):])), 'Pending Kit event changed')
            source = self.source()
            acted_in = state['area']
            for event in events:
                self._apply(state, source, event)
            opening = any(event.get('type') == 'beat' and 'scene_entry' in (event.get('tags') or ())
                          for event in events)  # Kit's framing of the room is not the player's turn
            room = state.setdefault('room', {'id': source.get('id'), 'path': None, 'turns_in': {}})
            if opening:
                room['opened'] = sorted(set(room.get('opened') or ()) | {acted_in})
            elif any(event.get('type') not in BOOKKEEPING_EVENTS for event in events):
                room.setdefault('turns_in', {})[acted_in] = room.get('turns_in', {}).get(acted_in, 0) + 1
            if not any(event.get('type') == 'pending_check' for event in events) and \
                    any(event.get('type') not in KEEPS_PENDING_CHECK for event in events):
                held = (state.get('pending_check') or {}).get('held')
                if not (held and held.get('area', acted_in) == state['area']):
                    # A called check lasts one player turn. A held description is an obligation:
                    # it stays until delivered, and only for the room it describes (leaving
                    # that room lapses it, so it never lands in the wrong place).
                    state.pop('pending_check', None)
            next_revision = revision + 1
            if kit_record is not None and not kit_record.get('engine_checkpoint'):
                kit = state['kit']
                trace = kit_record['trace']
                read = trace.get('improv_read') if isinstance(trace.get('improv_read'), dict) else {}
                kit['current_appraisal'] = trace['appraisal']
                kit['episodes'].append({
                    'turn_id': turn_id, 'player_input': kit_record['player_input'],
                    'event': trace['observed_event'], 'appraisal': trace['appraisal'],
                    'goal': trace.get('goal'), 'move': trace['move'],
                    'brief': trace.get('public_brief'),
                    'public_event': kit_record['public_event'],
                    # Private: Kit's own reason and her reading of the bid, kept so a
                    # later decision can see why she did what she did.
                    'player_bid': read.get('player_bid'), 'kit_choice': read.get('kit_choice'),
                    'actor_ref': read.get('actor_ref'), 'story_anchor': read.get('story_anchor'),
                    'story_basis': read.get('story_basis'),
                })
                kit['episodes'] = kit['episodes'][-KIT_EPISODE_LIMIT:]
                note = trace.get('player_note')
                if isinstance(note, dict) and str(note.get('note', 'none')).strip().casefold() != 'none':
                    evidence = [turn_id if ref == 'this_turn' else ref
                                for ref in note.get('evidence_turns', [])]
                    self._add_player_note(state, f'n{next_revision}', 'observed', note['note'],
                                          evidence, note.get('replaces', 'none'),
                                          current_turn=turn_id)
            # Arriving in an area linked to another room file mounts that room in this same
            # commit (docs/architecture/ROOM_LOADER.md): no host step, and a room that cannot
            # mount rejects the whole turn, so the session stays where it was. After Kit's episode:
            # the turn that leaves was decided in this room, so its memory stays with this room.
            link = (source['areas'].get(state['area']) or {}).get('room_link')
            if link:
                from . import kit_rooms
                new_source, state = kit_rooms.arrive(source, state, link)
                self.db.execute('UPDATE source SET body=? WHERE id=1', (encode(new_source),))
            self.db.execute('INSERT INTO turns VALUES (?, ?, ?)', (turn_id, digest, next_revision))
            self.db.executemany('INSERT INTO ledger(turn_id, body) VALUES (?, ?)',
                                [(turn_id, encode(event)) for event in events])
            if kit_record is not None:
                self.db.execute('INSERT INTO kit_turns VALUES (?, ?)', (turn_id, encode(kit_record)))
            self.db.execute('INSERT INTO snapshots VALUES (?, ?)', (next_revision, encode(state)))
            if consume_pending:
                self.db.execute('DELETE FROM kit_pending WHERE turn_id=?', (turn_id,))
            self.db.commit()
            return next_revision
        except Exception:
            self.db.rollback()
            raise

    def preview_state(self, expected_revision, events):
        """Apply an adjudicated batch to an unsaved copy, including earned knowledge."""
        revision, state = self.load()
        if revision != expected_revision:
            raise StaleTurn(f'Expected revision {expected_revision}; current is {revision}')
        source = self.source()
        for event in events:
            self._apply(state, source, event)
        return state

    def preview(self, expected_revision, events):
        """Player-safe rendering of the adjudicated state before it is committed."""
        return self._player_view(self.source(), self.preview_state(expected_revision, events))

    def record_kit_timing(self, turn_id, **fields):
        """Merge latency telemetry for a turn. Not part of the committed turn record."""
        require(isinstance(turn_id, str) and bool(turn_id.strip()), 'Turn ID required')
        with self.db:
            row = self.db.execute('SELECT body FROM kit_telemetry WHERE turn_id=?',
                                  (turn_id,)).fetchone()
            body = {**(json.loads(row[0]) if row else {}), **fields}
            if row:
                self.db.execute('UPDATE kit_telemetry SET body=? WHERE turn_id=?',
                                (encode(body), turn_id))
            else:
                self.db.execute('INSERT INTO kit_telemetry(turn_id, body) VALUES (?, ?)',
                                (turn_id, encode(body)))

    def kit_timing(self, turn_id):
        row = self.db.execute('SELECT body FROM kit_telemetry WHERE turn_id=?', (turn_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recent_kit_timings(self, limit=8):
        require(type(limit) is int and 0 <= limit <= 50, 'Invalid timing limit')
        rows = self.db.execute('SELECT turn_id, body FROM kit_telemetry ORDER BY seq DESC LIMIT ?',
                               (limit,)).fetchall()
        return list(reversed([{'turn_id': row[0], **json.loads(row[1])} for row in rows]))

    def recent_kit_turns(self, limit=8):
        require(type(limit) is int and 0 <= limit <= 12, 'Invalid history limit')
        rows = self.db.execute('''SELECT kit_turns.body FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id
            ORDER BY turns.revision DESC LIMIT ?''', (limit,)).fetchall()
        return list(reversed([json.loads(row[0]) for row in rows]))

    def player_inputs(self):
        """Every committed Kit turn's player input, oldest first (for names the player said)."""
        rows = self.db.execute('''SELECT kit_turns.body FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id ORDER BY turns.revision''').fetchall()
        return [json.loads(row[0]).get('player_input') or '' for row in rows]

    def committed_kit_turn_ids(self):
        return {row[0] for row in self.db.execute('SELECT turn_id FROM kit_turns')}

    def kit_turns_by_id(self, turn_ids):
        """Committed public records for the given turns, oldest first."""
        wanted = [ref for ref in dict.fromkeys(turn_ids) if isinstance(ref, str)]
        if not wanted:
            return []
        rows = self.db.execute(
            f'''SELECT kit_turns.turn_id, kit_turns.body FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id
            WHERE kit_turns.turn_id IN ({','.join('?' * len(wanted))})
            ORDER BY turns.revision''', wanted).fetchall()
        return [{'turn_id': row[0], **json.loads(row[1])} for row in rows]

    def latest_kit_turn_id(self):
        row = self.db.execute('''SELECT kit_turns.turn_id FROM kit_turns
            JOIN turns ON turns.id = kit_turns.turn_id ORDER BY turns.revision DESC LIMIT 1''').fetchone()
        return row[0] if row else None

    def player_notes(self):
        return self.load()[1]['kit']['player_notes']

    def record_player_feedback(self, text, evidence_turns=None, replaces='none'):
        """Record the player's out-of-character comment as an evidence-cited note.

        It is committed like any other adjudicated change (its own revision and an
        append-only ledger entry), so a turn prepared before it must be prepared again.
        Retrying the same comment about the same turn is idempotent.
        """
        check_player_note_text(text)
        revision, _ = self.load()
        if evidence_turns is None:
            latest = self.latest_kit_turn_id()
            require(latest is not None,
                    'Feedback must cite a committed turn; play the opening first')
            evidence_turns = [latest]
        event = {'type': 'player_note', 'source': 'feedback', 'note': text.strip(),
                 'evidence_turns': list(evidence_turns), 'replaces': replaces or 'none',
                 'evidence': 'The host recorded the player\'s out-of-character feedback.'}
        # Same comment about the same turn is the same feedback: a retry after a lost
        # response returns the original revision instead of adding a duplicate note.
        digest = hashlib.sha256(encode(event).encode()).hexdigest()[:16]
        next_revision = self.commit(f'feedback-{digest}', revision, [event])
        return {'revision': next_revision, 'note': next(
            (note for note in self.player_notes() if note['id'] == f'n{next_revision}'), None)}

    def set_player_character(self, name, ancestry, class_name=None, level=None):
        """Record who the player is playing (name, ancestry, class, level), as the host
        states it. Its own revision like feedback; the public view shows it as
        ``your_character`` so every character in the scene can get it right."""
        character = {'name': name, 'ancestry': ancestry, 'class': class_name, 'level': level}
        check_player_character(character)
        revision, _ = self.load()
        event = {'type': 'player_character', 'character': character,
                 'evidence': 'The host stated the player character\'s established identity.'}
        digest = hashlib.sha256(f'{revision}:{encode(event)}'.encode()).hexdigest()[:16]
        next_revision = self.commit(f'character-{digest}', revision, [event])
        return {'revision': next_revision, 'character': character}

    def set_player_sheet(self, sheet, intake=None):
        """Load the player character's sheet (runtime/pc_sheet.py, any class or
        ancestry). It also sets the public identity, like set_player_character."""
        from . import pc_sheet
        pc_sheet.check_sheet(sheet)
        # Store the real character name; the file title ("Copy of Nik") rides in sheet_title.
        sheet = pc_sheet.with_real_name(sheet)
        pc_sheet.check_sheet(sheet)
        revision, _ = self.load()
        event = {'type': 'player_sheet', 'sheet': sheet,
                 **({'intake': intake} if intake else {}),
                 'evidence': 'The host loaded the player character\'s sheet.'}
        digest = hashlib.sha256(f'{revision}:{encode(event)}'.encode()).hexdigest()[:16]
        next_revision = self.commit(f'sheet-{digest}', revision, [event])
        return {'revision': next_revision, 'character': pc_sheet.identity(sheet)}

    def add_companion(self, key, sheet, role, policy):
        """Put a companion on the party roster (runtime/kit_party.py): its sheet as the player
        supplied it, its tactics role and spending policy. Returns what the sheet leaves to ask."""
        from . import kit_party
        kit_party.member(sheet, role, policy)
        revision, _ = self.load()
        event = {'type': 'party_roster', 'key': key, 'sheet': sheet, 'role': role, 'policy': policy,
                 'evidence': 'The player supplied a companion sheet.'}
        digest = hashlib.sha256(f'{revision}:{encode(event)}'.encode()).hexdigest()[:16]
        next_revision = self.commit(f'party-{digest}', revision, [event])
        return {'revision': next_revision, 'asks': self.load()[1]['party'][key]['asks']}

    def restore_campaign(self, log, carried, pc_state=None):
        """Apply a player save's public record (kit_resume) before the room's opening."""
        revision, _ = self.load()
        event = {'type': 'campaign_restore', 'log': log, 'carried': carried,
                 **({'pc_state': pc_state} if pc_state is not None else {}),
                 'evidence': "The host resumed from the player's save."}
        digest = hashlib.sha256(f'{revision}:{encode(event)}'.encode()).hexdigest()[:16]
        return self.commit(f'restore-{digest}', revision, [event])

    def rest(self, kind):
        """The PC finished a short or long rest (host bookkeeping, like the sheet): the reaction
        inventory's uses come back (short: short-rest uses; long: everything, slots included)."""
        require(kind in ('short', 'long'), 'A rest is short or long')
        revision, _ = self.load()
        event = {'type': 'rest', 'kind': kind, 'evidence': f'The host recorded a {kind} rest.'}
        next_revision = self.commit(f'rest-{kind}-{revision}', revision, [event])
        return {'revision': next_revision, 'pc_resources': self.load()[1].get('pc_resources')}

    def close_scene(self, reason):
        """Close the open scene (KRABS §8); the next scene opens. Returns the new revision and scene."""
        require(isinstance(reason, str) and reason.strip(), 'Say why the scene closes')
        revision, state = self.load()
        event = {'type': 'scene_close', 'scene': current_scene(state), 'evidence': f'Scene closed: {reason.strip()[:300]}'}
        new = self.commit(f'close-{current_scene(state)}', revision, [event])
        return {'revision': new, 'scene': current_scene(self.load()[1])}

    def set_pc_state(self, **lists):
        """What the PC holds, has equipped, or has active right now (pc_sheet.CONDITIONS)."""
        revision, _ = self.load()
        event = {'type': 'pc_state', **lists, 'evidence': 'The host updated what the character holds or has active.'}
        digest = hashlib.sha256(f'{revision}:{encode(event)}'.encode()).hexdigest()[:16]
        return {'revision': self.commit(f'pcstate-{digest}', revision, [event])}

    def record_refused_attempt(self, action, ruling):
        """Commit a public note that the player tried something the table could not
        resolve. It is its own revision (like feedback), changes nothing in the world,
        and a retry of the same attempt at the same revision is idempotent."""
        require(isinstance(action, str) and action.strip(), 'Player action required')
        revision, _ = self.load()
        if self.db.execute('SELECT 1 FROM kit_pending WHERE revision=?', (revision,)).fetchone():
            # A prepared turn is waiting at this revision: committing now would make it stale
            # ('Expected revision 10; current is 11'). Queue it; flush_queued_attempts commits
            # it once nothing current is waiting. Returns None (nothing committed yet).
            with self.db:
                self.db.execute('INSERT INTO queued_attempts(action, ruling) VALUES (?, ?)',
                                (action.strip()[:REFUSED_ATTEMPT_MAX_CHARS], str(ruling).strip()[:REFUSED_ATTEMPT_MAX_CHARS]))
            return None
        return self._commit_attempts(revision, [(action, ruling)])

    def flush_queued_attempts(self):
        """Commit queued refused attempts when no prepared turn is waiting at the current
        revision. Returns the new revision, or None when nothing was flushed."""
        revision, _ = self.load()
        if self.db.execute('SELECT 1 FROM kit_pending WHERE revision=?', (revision,)).fetchone():
            return None
        rows = self.db.execute('SELECT seq, action, ruling FROM queued_attempts ORDER BY seq').fetchall()
        if not rows:
            return None
        new = self._commit_attempts(revision, [(a, r) for _, a, r in rows])
        with self.db:
            self.db.execute('DELETE FROM queued_attempts WHERE seq <= ?', (rows[-1][0],))
        return new

    def _commit_attempts(self, revision, attempts):
        events = [self._attempt_event(action, ruling) for action, ruling in attempts]
        digest = hashlib.sha256(f'{revision}:{encode(events)}'.encode()).hexdigest()[:16]
        return self.commit(f'attempt-{digest}', revision, events)

    @staticmethod
    def _attempt_event(action, ruling):
        return {'type': 'refused_attempt', 'action': action.strip()[:REFUSED_ATTEMPT_MAX_CHARS],
                 'ruling': str(ruling).strip()[:REFUSED_ATTEMPT_MAX_CHARS],
                 'evidence': 'The player attempted an action the slice could not adjudicate; '
                             'nothing changed in the world.'}

    def _add_player_note(self, state, note_id, source, text, evidence_turns, replaces='none',
                         current_turn=None):
        """Every note cites committed turns; notes can retire older observed notes."""
        require(source in PLAYER_NOTE_SOURCES, 'Unknown player note source')
        check_player_note_text(text)
        committed = self.committed_kit_turn_ids()
        require(isinstance(evidence_turns, list) and
                0 < len(evidence_turns) <= PLAYER_NOTE_MAX_EVIDENCE and
                all(isinstance(ref, str) and (ref in committed or ref == current_turn)
                    for ref in evidence_turns),
                f'A player note must cite 1–{PLAYER_NOTE_MAX_EVIDENCE} committed turn IDs')
        notes = state['kit']['player_notes']
        if replaces not in (None, 'none'):
            old = next((note for note in notes if note['id'] == replaces), None)
            require(old is not None, 'replaces must name an existing player note')
            require(source == 'feedback' or old['source'] == 'observed',
                    'Only new feedback can replace the player\'s own feedback')
            notes.remove(old)
        notes.append({'id': note_id, 'source': source, 'note': text.strip(),
                      'evidence_turns': list(dict.fromkeys(evidence_turns))})
        while len(notes) > PLAYER_NOTE_LIMIT:
            # Drop the oldest inferred note before any explicit feedback.
            observed = [note for note in notes if note['source'] == 'observed']
            notes.remove(observed[0] if observed else notes[0])

    def _apply(self, state, source, event):
        require(isinstance(event, dict), 'Event must be an object')
        require(isinstance(event.get('evidence'), str) and bool(event['evidence'].strip()),
                'Record the adjudication or evidence for each event')
        kind = event.get('type')
        if kind == 'reveal_fact':
            key = event.get('fact')
            require(key in source['facts'], 'Unknown fact')
            require(source['facts'][key]['area'] == state['area'], 'Remote reveal unsupported')
            if key not in state['known_facts']:
                state['known_facts'].append(key)
        elif kind == 'reveal_exit':
            key = event.get('exit')
            require(key in source['exits'], 'Unknown exit')
            require(state['area'] in source['exits'][key]['areas'], 'Exit not adjacent')
            if key not in state['known_exits']:
                state['known_exits'].append(key)
        elif kind == 'move':
            key = event.get('exit')
            require(key in state['known_exits'], 'Exit not discovered')
            edge = source['exits'][key]
            require(state['area'] in edge['areas'], 'Exit not adjacent')
            state['area'] = next(a for a in edge['areas'] if a != state['area'])
            state.setdefault('room', {'id': source.get('id'), 'path': None, 'turns_in': {}})['came_by'] = key
            state.pop('pc_position', None)  # a new area: no longer at the old doorway
            if (state.get('standing_check') or {}).get('area') != state['area']:
                state.pop('standing_check', None)  # a new area ends a standing attempt
            if state['area'] not in state['visited']:
                state['visited'].append(state['area'])
            self._observe(state, source)
        elif kind == 'actor_status':
            key = event.get('actor')
            require(key in state['actors'], 'Unknown actor')
            actor = state['actors'][key]
            require(actor['location'] == state['area'], 'Remote actor update unsupported')
            status = event.get('status')
            require(status in {'alive', 'unconscious', 'dead', 'fled'}, 'Unknown status')
            require(actor['status'] != 'dead' or status == 'dead', 'Resurrection needs a future explicit rules operation')
            actor['status'] = status
            toward = event.get('toward')
            if toward is not None:
                require(status == 'fled' and isinstance(toward, str) and re.match(r'^area_[0-9a-z_]+$', toward),
                        'Only a fleeing actor heads toward an area (e.g. area_07)')
                actor['fled_toward'] = toward
        elif kind == 'pc_conditions':
            # The PC's conditions now (a condition ending by rule, healing): the whole list.
            conditions = event.get('conditions')
            require(isinstance(conditions, list) and all(isinstance(c, str) and c.strip() for c in conditions),
                    'pc_conditions lists condition names')
            terms = event.get('terms', {})
            require(isinstance(terms, dict) and all(isinstance(v, dict) for v in terms.values()),
                    'pc_conditions terms are {condition: {how it ends}}')
            state['pc_conditions'] = list(dict.fromkeys(conditions))
            # How each ends (kit_combat.condition_terms): durations, repeat saves, "while".
            state['pc_condition_terms'] = {k: copy.deepcopy(v) for k, v in terms.items() if k in conditions}
        elif kind == 'trigger_fired':
            from . import kit_triggers
            kit_triggers.apply_event(state, source, event)
        elif kind == 'spend_resource':
            key, amount = event.get('resource'), event.get('amount')
            require(key in state['resources'], 'Unknown resource')
            require(type(amount) is int and amount > 0, 'Spend must be a positive integer')
            require(state['resources'][key] >= amount, 'Insufficient resource')
            state['resources'][key] -= amount
        elif kind == 'advance_time':
            seconds = event.get('seconds')
            require(type(seconds) is int and seconds > 0, 'Time increment must be a positive integer')
            state['elapsed_seconds'] += seconds
        elif kind == 'player_note':
            require(event.get('source') == 'feedback', 'Only host-recorded feedback is a note event')
            revision, _ = self.load()
            self._add_player_note(state, f'n{revision + 1}', 'feedback', event.get('note'),
                                  event.get('evidence_turns'), event.get('replaces', 'none'))
        elif kind == 'refused_attempt':
            require(isinstance(event.get('action'), str) and isinstance(event.get('ruling'), str),
                    'A refused attempt needs the action and the ruling')
            revision, _ = self.load()
            attempts = state.setdefault('refused_attempts', [])
            attempts.append({'action': event['action'], 'ruling': event['ruling'],
                             'revision': revision + 1})
            state['refused_attempts'] = attempts[-REFUSED_ATTEMPT_LIMIT:]
        elif kind == 'canon_entry':
            slot = event.get('slot')
            require(isinstance(slot, str) and CANON_SLOT.match(slot), 'canon_entry needs a slot')
            require(slot.split('/')[-1] not in source['facts'], 'canon_entry collides with a source fact')
            require(event.get('kind') in CANON_KINDS and event.get('scope') in CANON_SCOPES,
                    'Unknown canon_entry kind or scope')
            require(isinstance(event.get('fact'), str) and 0 < len(event['fact'].strip()) <= 240,
                    'canon_entry fact must be 1-240 characters')
            require(isinstance(event.get('basis'), str) and 0 < len(event['basis'].strip()) <= CANON_BASIS_MAX_CHARS,
                    f'canon_entry needs its basis (1-{CANON_BASIS_MAX_CHARS} characters)')
            require(type(event.get('public')) is bool, 'canon_entry public must be a boolean')
            procedure = event.get('procedure')
            if procedure is not None or event['kind'] == 'procedure':
                require(event['kind'] == 'procedure' and procedure in
                        {k for k in source.get('procedures', {}) if not k.startswith('_')},
                        'A procedure entry must name a procedure this room can run')
            price = event.get('price')
            if event['kind'] == 'price':
                require(isinstance(price, dict) and type(price.get('amount')) is int and
                        price.get('unit') in ('cp', 'sp', 'ep', 'gp', 'pp') and price.get('basis'),
                        'A price entry records its amount, unit, and which source, SRD entry, or '
                        'formula set it')
            canon = state.setdefault('canon', {})
            prior = canon.get(slot)
            fact = event['fact'].strip()
            revision, _ = self.load()
            if prior and normalize_fact(prior['fact']) == normalize_fact(fact):
                pass  # restating canon is fine
            else:
                if prior:
                    require(prior['kind'] != 'price', f'{slot} already has its price: {prior["fact"]}')
                    require(isinstance(event.get('change_reason'), str) and
                            len(event['change_reason'].split()) >= 4,
                            f'canon_entry contradicts {slot} ({prior["fact"]}) without an in-story reason')
                else:
                    require(len(canon) < CANON_LIMIT, 'Too many canon entries for one session')
                canon[slot] = {'kind': event['kind'], 'fact': fact, 'basis': event['basis'].strip(),
                               'public': event['public'], 'scope': event['scope'],
                               'procedure': procedure, 'roots': list(event.get('roots') or []),
                               'choice': event.get('choice'), 'price': price,
                               'area': state['area'], 'revision': revision + 1,
                               **({'scene': current_scene(state)} if event['scope'] == 'scene' else {}),
                               **({'supersedes': {'fact': prior['fact'], 'revision': prior['revision'],
                                                  'reason': event['change_reason']}} if prior else {})}
        elif kind == 'scene_close':
            # KRABS §8: the open scene closes and the next one opens. Scope decides what
            # survives: actor status, location, relocation, custody, campaign- and location-
            # scoped canon live in global state and stay true; this scene's own canon and its
            # scene-local state (who is hidden from whom) end with it.
            closing = current_scene(state)
            require(event.get('scene') == closing, f'scene_close names the open scene ({closing})')
            require((state.get('combat') or {}).get('status') not in ('awaiting_initiative', 'running'),
                    'A scene cannot close in the middle of a fight')
            state['canon'] = {slot: entry for slot, entry in (state.get('canon') or {}).items()
                              if not (entry.get('scope') == 'scene' and entry.get('scene', FIRST_SCENE) == closing)}
            state.pop('scene', None)
            closed = state.setdefault('scenes_closed', [])
            closed.append({'scene': closing, 'area': state['area']})
            state['scenes_closed'] = closed[-12:]
            state['scene_id'] = f'scene-{int(closing.rsplit("-", 1)[-1]) + 1}'
        elif kind == 'player_character':
            character = event.get('character')
            check_player_character(character)
            state['player_character'] = dict(character)
            state.pop('player_sheet', None)
        elif kind == 'player_sheet':
            from . import pc_sheet
            sheet = pc_sheet.with_real_name(pc_sheet.check_sheet(event.get('sheet')))
            state['player_sheet'] = copy.deepcopy(sheet)
            state['player_character'] = pc_sheet.identity(sheet)
            from . import kit_reactions
            # The reaction inventory, slots and uses, rebuilt from the sheet; what was spent since the
            # last rest stays spent (re-sending or editing the sheet is not a rest: #101 review D7).
            state['pc_resources'] = kit_reactions.carry_spent(kit_reactions.build(sheet), state.get('pc_resources'))
            # Where this sheet came from and when (P5). No timing gate: the player manages their own sheet.
            intake = event.get('intake') or {'kind': 'json'}
            require(isinstance(intake, dict) and all(isinstance(v, (str, type(None))) for v in intake.values()),
                    'player_sheet intake is {kind, at, named_by_player, imported_at}')
            state['sheet_import'] = {**copy.deepcopy(intake), 'long_rests': state.get('long_rests', 0)}
        elif kind == 'pc_resources':
            from . import kit_reactions
            state['pc_resources'] = copy.deepcopy(kit_reactions.check(event.get('resources')))
        elif kind == 'rest':
            from . import kit_reactions
            require(event.get('kind') in ('short', 'long'), 'A rest is short or long')
            state['pc_resources'] = kit_reactions.rest(kit_reactions.current(state), state.get('player_sheet') or {},
                                                       event['kind'])
            if event['kind'] == 'long':
                state['long_rests'] = int(state.get('long_rests') or 0) + 1
        elif kind == 'claim_said':
            from . import kit_claims
            said = event.get('said')
            require(isinstance(said, dict) and {'claim', 'by', 'version', 'stance', 'why', 'turn'} <= set(said),
                    'claim_said needs claim, by, version, stance, why, turn')
            claims = state.setdefault('claims', {'said': [], 'learned': []})
            if said['claim'] == 'new':
                definition = said.get('new')
                require(isinstance(definition, dict), 'A new claim_said needs its definition')
                established = kit_claims.established_claims(state)
                subject = kit_claims.check_new_definition(definition, established)
                established.setdefault(subject, copy.deepcopy(definition))
                claims['established'] = established
            claims['said'] = (claims['said'] + [copy.deepcopy(said)])[-kit_claims.SAID_LIMIT:]
        elif kind == 'toll_state':
            from . import kit_toll
            kit_toll.apply_event(state, source, event)
        elif kind == 'agenda_turn':
            from . import kit_agenda
            kit_agenda.apply_event(state, source, event)
        elif kind == 'pending_check':
            # The check Kit called, kept for the player's roll next turn; None clears it.
            from . import pc_sheet
            check = event.get('check')
            require(check is None or (isinstance(check, dict) and
                                      set(check) - PENDING_CHECK_OPTIONAL == {'skill', 'ability', 'target', 'called_turn'} and
                                      ('exit' not in check or check['exit'] in (source.get('exits') or {})) and
                                      ('threshold' not in check or check['threshold'] in (source.get('exits') or {})) and
                                      ('dc' not in check or (type(check['dc']) is int and 1 <= check['dc'] <= 30)) and
                                      ('dc_adjust' not in check or (type(check['dc_adjust']) is int and
                                                                    -5 <= check['dc_adjust'] <= 5)) and
                                      ('held' not in check or (isinstance(check['held'], dict) and
                                                               set(check['held']) - {'area'} == {'kind'} and
                                                               check['held'].get('area', state['area']) in source['areas'] and
                                                               check['held']['kind'] in HELD_KINDS)) and
                                      ('reason' not in check or (isinstance(check['reason'], str) and
                                                                 len(check['reason']) <= 200)) and
                                      ('action' not in check or (isinstance(check['action'], str) and
                                                                 0 < len(check['action']) <= 2000)) and
                                      pc_sheet.SKILLS.get(check['skill']) == check['ability'] and
                                      isinstance(check['target'], str) and isinstance(check['called_turn'], str)),
                    'pending_check is {skill, ability, target, called_turn[, exit, threshold, held, dc, dc_adjust, reason, action]} or None')
            if check is None:
                state.pop('pending_check', None)
            else:
                state['pending_check'] = copy.deepcopy(check)
                if not check.get('exit'):
                    # The recap says the check is called, not the stale "nothing rolled" of
                    # the request turn (PR 145 playtest bug 15).
                    state['rhythm'].append({'tags': ['check_called'],
                                            'evidence': f"Kit called for {check['skill']}; waiting on the roll."})
                    state['rhythm'] = state['rhythm'][-12:]
        elif kind == 'standing_check':
            from . import pc_sheet
            check = event.get('check')
            require(check is None or (isinstance(check, dict) and set(check) == STANDING_CHECK_KEYS and
                                      check['skill'] in pc_sheet.SKILLS and type(check['total']) is int and
                                      check['area'] in source['areas'] and
                                      isinstance(check['against'], dict) and isinstance(check['approach'], str)),
                    'standing_check is {skill, total, die, modifier, area, route, against, approach, since} or None')
            if check is None:
                state.pop('standing_check', None)
            else:
                state['standing_check'] = copy.deepcopy(check)
        elif kind == 'risk_warned':
            from . import kit_interstitial
            kit_interstitial.apply(state, event)
        elif kind == 'open_threads':
            from . import kit_threads
            kit_threads.apply_event(state, event)
        elif kind == 'kit_plan':
            from . import kit_plan
            kit_plan.apply_event(state, event)
        elif kind == 'story_beat':
            from . import kit_brief
            kit_brief.apply_event(state, source, event)
        elif kind == 'threshold_crossed':
            from . import kit_brief
            kit_brief.apply_threshold(state, source, event)
        elif kind == 'attitude_shift':
            from . import kit_attitude
            kit_attitude.apply_event(state, source, event)
        elif kind == 'scene_state':
            from . import kit_combat
            kit_combat.check_scene(event.get('state'))
            state['scene'] = copy.deepcopy(event['state'])
        elif kind == 'party_roster':
            from . import kit_party
            entry = kit_party.member(event.get('sheet'), event.get('role'), event.get('policy'))
            key = event.get('key')
            require(isinstance(key, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,30}', key or '') and key != 'pc',
                    'a companion key is a short lowercase id')
            party = dict(state.get('party') or {})
            party[key] = entry
            kit_party.check_party(party)
            state['party'] = party
        elif kind == 'party_state':
            from . import kit_party
            kit_party.check_party(event.get('party'))
            require(set(event['party']) == set(state.get('party') or {}), 'party_state changes no one on the roster')
            state['party'] = copy.deepcopy(event['party'])
        elif kind == 'combat_state':
            from . import kit_combat
            kit_combat.check_fight(event.get('state'))
            state['combat'] = copy.deepcopy(event['state'])
            if event['state'].get('pc_conditions'):
                # Conditions are the PC's, not the fight's: they outlast it until they end by rule.
                state['pc_conditions'] = list(dict.fromkeys(list(state.get('pc_conditions') or ()) +
                                                            list(event['state']['pc_conditions'])))
        elif kind == 'pc_state':
            from . import pc_sheet
            sheet = state.get('player_sheet')
            require(sheet is not None, 'Load a character sheet before changing what is held or active')
            for key in pc_sheet.CONDITIONS:
                if key in event:
                    require(isinstance(event[key], list) and len(event[key]) <= 12 and
                            all(isinstance(v, str) and 0 < len(v) <= 60 for v in event[key]),
                            f'pc_state {key} lists up to 12 names')
                    sheet[key] = list(event[key])
        elif kind == 'claim_learned':
            key = event.get('claim')
            require(key in (source.get('claims') or {}), 'Unknown claim')
            claims = state.setdefault('claims', {'said': [], 'learned': []})
            if key not in claims['learned']:
                claims['learned'].append(key)
        elif kind == 'oracle_draw':
            slot = event.get('slot')
            require(isinstance(slot, str) and CANON_SLOT.match(slot), 'oracle_draw needs a slot')
            oracle = state.setdefault('oracle', {'deals': {}, 'used': {}})
            oracle['deals'][slot] = oracle['deals'].get(slot, 0) + 1
            if event.get('card'):
                used = oracle['used'].setdefault(state['area'], [])
                if event['card'] not in used:
                    used.append(event['card'])
        elif kind == 'procedure_state':
            key = event.get('procedure')
            require(key in {k for k in source.get('procedures', {}) if not k.startswith('_')},
                    'Unknown table procedure')
            body = event.get('state')
            require(isinstance(body, dict) and set(body) == {'public', 'private'},
                    'Procedure state needs public and private halves')
            require(len(encode(body).encode()) <= 6000, 'Procedure state exceeds size limit')
            state.setdefault('procedures', {})[key] = copy.deepcopy(body)
        elif kind == 'pc_position':
            key = event.get('at_exit')
            require(key in source['exits'] and state['area'] in source['exits'][key]['areas'],
                    'pc_position names an exit next to the PC')
            state['pc_position'] = {'area': state['area'], 'at_exit': key}
        elif kind == 'campaign_restore':
            # Resume from the player's save (kit_resume): the public record of rooms left and
            # what the PC carries. Only lists of short public strings; nothing of a room's secrets.
            log, carried = event.get('log'), event.get('carried')
            def names(value, limit=60):
                return isinstance(value, list) and len(value) <= limit and all(
                    isinstance(v, str) and len(v) <= 400 for v in value)
            rooms = (log or {}).get('rooms') if isinstance(log, dict) else None
            require(isinstance(rooms, list) and len(rooms) <= 200 and all(
                isinstance(r, dict) and isinstance(r.get('room_id'), str) and
                r.get('status') in ('left', 'bypassed') and names(r.get('areas')) and
                names(r.get('learned'), 200) and names(r.get('took')) and
                isinstance(r.get('npcs_met'), list) and all(
                    isinstance(n, dict) and isinstance(n.get('name'), str) and isinstance(n.get('status'), str)
                    for n in r['npcs_met']) for r in rooms), 'campaign_restore needs log.rooms of public records')
            require(isinstance(carried, list) and len(carried) <= 60 and all(
                isinstance(c, dict) and isinstance(c.get('item'), str) for c in carried),
                'campaign_restore carried lists {item, from}')
            from . import kit_save, kit_reactions
            for record in rooms:
                kit_save.check_carry(record.get('carry'))
            pc = event.get('pc_state')
            if pc is not None:
                counts = lambda v: isinstance(v, dict) and all(
                    isinstance(k, str) and type(n) is int and n >= 0 for k, n in v.items())
                require(isinstance(pc, dict) and counts(pc.get('slots', {})) and counts(pc.get('uses', {}))
                        and names(pc.get('conditions', [])), 'campaign_restore pc_state is {slots, uses, conditions}')
                spent = {'slots': {k: {'used': n} for k, n in pc.get('slots', {}).items()},
                         'uses': {k: {'used': n} for k, n in pc.get('uses', {}).items()}}
                state['pc_resources'] = kit_reactions.carry_spent(kit_reactions.current(state), spent)
                if pc.get('conditions'):
                    state['pc_conditions'] = list(dict.fromkeys(pc['conditions']))
            state['campaign_log'] = copy.deepcopy(log)
            state['carried'] = copy.deepcopy(carried)
        elif kind == 'beat':
            tags = event.get('tags')
            require(isinstance(tags, list) and all(isinstance(t, str) for t in tags), 'Invalid beat tags')
            # The ledger keeps the full evidence; the rhythm window keeps a bounded
            # excerpt so long player declarations cannot exhaust the context budget.
            evidence = event['evidence']
            if len(evidence) > RHYTHM_EVIDENCE_MAX_CHARS:
                evidence = evidence[:RHYTHM_EVIDENCE_MAX_CHARS - 3] + '...'
            state['rhythm'].append({'tags': tags, 'evidence': evidence})
            state['rhythm'] = state['rhythm'][-12:]
        elif kind == 'spell_running':
            # A lasting spell the PC keeps up (Detect Magic, 10 minutes): until when, in game
            # seconds, so entering a new area while it runs senses there (#150 retest 5).
            spell, until = event.get('spell'), event.get('until')
            require(isinstance(spell, str) and 0 < len(spell) <= 40 and type(until) is int and until >= 0,
                    'spell_running needs a spell name and an until time')
            state.setdefault('spells_running', {})[spell.casefold()] = until
        else:
            raise InvalidChange(f'Unsupported event: {kind}')

    @staticmethod
    def _attitudes_here(source, state):
        """DM-only: present NPCs' attitudes and what last moved them (runtime/kit_attitude.py)."""
        from . import kit_attitude
        here = kit_attitude.attitudes_here(source, state)
        return {'attitudes_here': here} if here else {}

    @staticmethod
    def _tolls_here(source, state):
        """DM-only: each toll in this area, its config and where the exchange stands."""
        if not source.get('tolls'):
            return {}
        from . import kit_toll
        return {key: {'state': body, 'demand': {k: toll[k] for k in ('demanded_by', 'amount', 'unit', 'per',
                                                                      'floor', 'basis') if k in toll},
                      'refusal': toll['refusal'], 'violence': toll.get('violence'),
                      'note': ('A full exchange (Brendon\'s call 6): one NPC asks for it, with a motive that '
                               'stays inside the act, and lets the player answer; pay, haggle, refuse, '
                               'or steer back to the game each commit; a refusal\'s consequence persists; a '
                               'deferred toll comes back later.')}
                for key, (toll, body) in kit_toll.here(source, state).items()}

    @staticmethod
    def _player_view(source, state):
        view = Runtime._base_player_view(source, state)
        established = [{'slot': key, 'fact': item['fact']}
                       for key, item in canon_in_scope(state).items() if item['public']]
        if established:
            view['established_details'] = established
        from . import kit_cards  # local import: kit_cards imports this module
        procedures = {key: kit_cards.public_view((source.get('procedures') or {}).get(key) or {}, body['public'])
                      for key, body in (state.get('procedures') or {}).items()}
        if procedures:
            view['table_procedures'] = procedures
        from . import kit_toll
        tolls = kit_toll.public_view(source, state) if source.get('tolls') else {}
        if tolls:
            view['tolls'] = tolls
        from . import kit_combat
        if kit_combat.config(source) and (state.get('combat') or state.get('scene')):
            view.update(kit_combat.public_view(source, state))
        return view

    @staticmethod
    def _base_player_view(source, state):
        exits = []
        for key in state['known_exits']:
            edge = source['exits'][key]
            if state['area'] not in edge['areas']:
                continue
            other = next(a for a in edge['areas'] if a != state['area'])
            exits.append({'id': key, 'description': edge['labels'][state['area']],
                          'known_destination': source['areas'][other]['name'] if other in state['visited'] else None})
        return {
            'area': source['areas'][state['area']]['name'],
            'known_facts_here': [source['facts'][k]['text'] for k in state['known_facts']
                                 if source['facts'][k]['area'] == state['area']],
            'exits': exits,
            'actors': [{'name': a['name'], 'status': a['status']} for k, a in state['actors'].items()
                       if a['location'] == state['area'] and a['visible'] and a['status'] != 'fled'
                       and not unperceived({**(source['actors'].get(k) or {}), **a})],
            'resources': state['resources'], 'elapsed_seconds': state['elapsed_seconds'],
            **({'your_character': dict(state['player_character'])} if state.get('player_character') else {}),
            **({'your_position': f"at {source['exits'][state['pc_position']['at_exit']].get('name') or 'the doorway'}"}
               if (state.get('pc_position') or {}).get('area') == state['area'] else {}),
        }

    def player_view(self):
        _, state = self.load()
        return self._player_view(self.source(), state)

    @staticmethod
    def dm_only(source, state):
        """The DM-only half of the context for the PC's area (also measured at mount)."""
        area = state['area']
        return {
            'room_rules': source.get('room_rules', []),
            'unrevealed_facts': {k: f for k, f in source['facts'].items()
                                 if f['area'] == area and k not in state['known_facts']},
            'geometry': {k: e for k, e in source['exits'].items() if area in e['areas']},
            'actors': {k: a for k, a in state['actors'].items()
                       if a['location'] == area and a['status'] != 'fled'},
            **({'canon_here': canon_in_scope(state)} if canon_in_scope(state) else {}),
            **({'procedures_private': {k: body['private'] for k, body in
                                       state['procedures'].items()}}
               if state.get('procedures') else {}),
            **({'supported_procedures': {
                k: {'kind': p.get('kind'), 'name': p.get('name')}
                for k, p in source['procedures'].items()
                if not k.startswith('_') and p.get('offered', True)}}
               if source.get('procedures') else {}),
            **({'tolls_here': Runtime._tolls_here(source, state)} if Runtime._tolls_here(source, state) else {}),
            **Runtime._attitudes_here(source, state),
        }

    def context(self, personality_core=None, max_bytes=CONTEXT_BUDGET_BYTES):
        if personality_core is None:
            personality_core = personality_core_text(source=self.source())
        revision, state = self.load()
        source, area = self.source(), state['area']
        packet = {
            'prototype_version': '0.1.1', 'revision': revision,
            'personality_core': personality_core,
            'dm_context': {
                'scene': {'current_area': area, 'elapsed_seconds': state['elapsed_seconds'],
                          'scene_id': current_scene(state)},
                'source_id': source['id'], 'fixture_only': bool(source.get('fixture_only')),
                'source_ref': source.get('source_ref'), 'map_ref': source.get('map_ref'),
                'level_context': source.get('level_context'),
                'campaign_context': source.get('campaign_context'),
                'player_perceivable': self._player_view(source, state),
                'dm_only': Runtime.dm_only(source, state),
                'recent_rhythm': state['rhythm'],
                'constraints': [
                    'Player output must respect player_perceivable and accepted reveals.',
                    'DM-only facts and actor secrets are private.',
                    'The source graph is immutable. Missing connections are not invented.',
                    'Writes require adjudication; this prototype does not check D&D legality.',
                    source_constraint(source),
                ],
                'missing_production_layers': ['rules resolver', 'source retrieval', 'level story state',
                    *(['Halaster state'] if is_mad_mage(source) else []), 'faction ticks',
                    'player model beyond evidence-cited notes', 'character patterns'],
            },
        }
        require(len(encode(packet).encode()) <= max_bytes, 'Context budget exceeded; narrow the source adapter')
        return packet


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'view', 'context', 'commit'])
    parser.add_argument('--db', default='session.sqlite')
    parser.add_argument('--fixture', default=str(PROJECT_ROOT / 'tests/fixtures/feasibility_room.json'))
    parser.add_argument('--core', default=str(PERSONALITY_CORE))
    parser.add_argument('--turn-file', help='JSON object with turn_id, expected_revision, events')
    args = parser.parse_args()
    runtime = Runtime(args.db)
    try:
        if args.command == 'init':
            source = json.loads(Path(args.fixture).read_text(encoding='utf-8'))
            runtime.initialize(source, source['starting_area'])
            output = runtime.player_view()
        elif args.command == 'view':
            output = runtime.player_view()
        elif args.command == 'context':
            output = runtime.context(Path(args.core).read_text(encoding='utf-8'))
        else:
            if not args.turn_file:
                parser.error('--turn-file is required')
            output = {'revision': runtime.commit(**json.loads(Path(args.turn_file).read_text(encoding='utf-8')))}
        print(json.dumps(output, indent=2, ensure_ascii=False))
    finally:
        runtime.close()
