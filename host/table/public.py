"""Player-facing projection. Hidden engine fields never leave the process."""
import json

# Keys that belong to the DM packet, the host instructions, or the room file.
DROP_KEYS = frozenset({
    'dm_only', 'secrets', 'motive', 'knowledge', 'unrevealed_facts', 'instructions',
    'personality_core', 'private', 'session_manifest', 'room_manifest', 'prepared',
    'input', 'schema', 'host_retry', 'performance_limits', 'schema_notation',
    'next_step', 'next_command', 'packet_command', 'packet', 'do_not_start',
    'manifest_rule', 'first_try', 'body', 'folder', 'start_room', 'adventure_next',
    'db', 'room', 'sheet', 'example_sheet',
})


def project(value):
    if isinstance(value, dict):
        return {key: project(item) for key, item in value.items() if key not in DROP_KEYS}
    if isinstance(value, list):
        return [project(item) for item in value]
    return value


def adventure_public(block):
    if not isinstance(block, dict):
        return None
    if block.get('adventure_readiness') in (None, 'none'):
        return None
    compiled = block.get('locations_compiled') or []
    return {
        'title': block.get('adventure_title') or block.get('title'),
        'readiness': block.get('adventure_readiness'),
        'locations': block.get('locations_total') or block.get('locations'),
        'compiled': len(compiled) if isinstance(compiled, list) else compiled,
        'mounted_location': block.get('mounted_location'),
    }


def modules_public(lobby):
    """Names the player may start. Paths stay on the server."""
    found = []
    for entry in (lobby or {}).get('modules_available') or []:
        if not isinstance(entry, dict):
            continue
        found.append({
            'room_id': entry.get('room_id'),
            'starting_area': entry.get('starting_area'),
        })
    return found


def dumps(value):
    return json.dumps(project(value), ensure_ascii=False)
