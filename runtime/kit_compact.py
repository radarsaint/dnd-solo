"""Compact one-pass packets (latency experiment condition D; docs/latency/experiment-protocol.md).

Opt-in (``--compact`` on start / prepare --one-pass). The full packet stays the default.

A compact packet holds only:

* the operating contract: ``instructions``, the output ``schema`` (in the lossless
  kit_manifest shorthand), ``performance_limits``, ``host_retry``;
* the active scene: ``first_try``, the move and event, ``player_perceivable``, the reveal
  plan (obvious / hold / pointed), ``story_brief``, dialogue history, the public side;
* current character state (``kit_state``, ``your_character``) and live constraints
  (``constraints``, ``dm_only.room_rules``, geometry, and DM-only facts and actors *in the
  active area*);
* ``retrieval``: the commands that fetch everything else on demand.

What moves behind a command: the personality core text (``persona``), the full JSON
schema, the static ``missing_production_layers`` catalog, and DM-only facts and actors of
other areas (``fetch --part area --area ID``). Nothing is rewritten or summarized: every key
the compact packet keeps is byte-identical to the full packet's, and hidden-state guards
(reveal.hold, withheld texts) are applied before compaction, so they carry over unchanged.

Stable first: the operating contract comes before anything that changes per turn, so a
provider that caches a matching prefix can reuse it.
"""
import copy

from . import kit_manifest

CONTRACT_KEYS = ('performance_variant', 'instructions', 'schema', 'performance_limits', 'host_retry')
FETCHED_PRIVATE = ('personality_core',)
FETCHED_DM = ('missing_production_layers',)


def retrieval(db):
    base = f'python3 -m runtime.kit_agent'
    return {
        'rule': ('Compact packet: only this scene is here. Before your first line in this chat, run '
                 'persona once and keep it as personality_core (it does not change). Fetch anything else '
                 'only when the scene needs it; never guess a fact you were not given.'),
        'persona': f'{base} persona',
        'full_schema': f'{base} fetch --db {db} --part schema',
        'production_layers': f'{base} fetch --db {db} --part production_layers',
        'other_area': f'{base} fetch --db {db} --part area --area <area id>',
        'view': f'{base} view --db {db}',
    }


def _area_of(entry):
    return entry.get('area') if isinstance(entry, dict) else None


def _in_area(entries, area):
    """Entries that belong to the active area, or to no single area (room-wide)."""
    if not isinstance(entries, dict):
        return entries, {}
    keep, moved = {}, {}
    for key, entry in entries.items():
        where = _area_of(entry)
        (keep if where in (None, area) else moved)[key] = entry
    return keep, moved


def compact(packet, db):
    """The compact form of a full one-pass packet. Returns (packet, moved) where ``moved``
    names what was left for retrieval (for tests and telemetry; not sent)."""
    packet = copy.deepcopy(packet)
    out = {key: packet.pop(key) for key in CONTRACT_KEYS if key in packet}
    if 'schema' in out:
        out['schema'] = kit_manifest.compact_schema(out['schema'])
        out['schema_notation'] = kit_manifest.SCHEMA_NOTATION
    moved = {}
    private = packet.get('input', {}).get('private', {})
    for key in FETCHED_PRIVATE:
        if key in private:
            moved[key] = private.pop(key)
    dm = private.get('dm_context') if isinstance(private.get('dm_context'), dict) else {}
    for key in FETCHED_DM:
        if key in dm:
            moved[key] = dm.pop(key)
    area = (dm.get('scene') or {}).get('current_area')
    dm_only = dm.get('dm_only') if isinstance(dm.get('dm_only'), dict) else {}
    for key in ('unrevealed_facts', 'actors'):
        if key in dm_only and area is not None:
            dm_only[key], away = _in_area(dm_only[key], area)
            if away:
                moved[f'dm_only.{key}'] = away
    public = packet.get('input', {}).get('public')
    if isinstance(public, dict) and 'shared_with_private' in public:
        public['shared_with_private'] = ('personality_core: run retrieval.persona; public dialogue '
                                         'history is in input.private.dialogue_history')
    out['retrieval'] = retrieval(db)
    out['packet_mode'] = 'compact'
    out.update(packet)
    return out, moved
