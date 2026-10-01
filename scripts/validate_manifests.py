#!/usr/bin/env python3
"""Validate public asset indexes without requiring the private image binaries."""
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_manifests(root=ROOT):
    files = {'maps': ('assets/maps/index.json', 2),
             'art': ('assets/art/index.json', 2),
             'handouts': ('assets/handouts/index.json', 1)}
    manifests = {}
    for kind, (path, version) in files.items():
        data = json.loads((Path(root) / path).read_text(encoding='utf-8'))
        require(isinstance(data, dict) and type(data.get('schema_version')) is int and
                data['schema_version'] == version, f'{path}: unsupported schema_version')
        require(isinstance(data.get('campaign'), str) and data['campaign'].strip(),
                f'{path}: campaign required')
        manifests[kind] = data
    require(len({data['campaign'] for data in manifests.values()}) == 1,
            'Manifest campaigns do not agree')
    ids, paths = set(), set()

    def identity(entry, label, required=True):
        require(isinstance(entry, dict), f'{label}: entry must be an object')
        if required or 'id' in entry:
            key = entry.get('id')
            require(isinstance(key, str) and key.strip(), f'{label}: id required')
            require(key not in ids, f'{label}: duplicate id {key}')
            ids.add(key)

    def image(entry, kind, label, require_id=True):
        identity(entry, label, require_id)
        path = entry.get('path')
        require(isinstance(path, str) and path.startswith(f'assets/{kind}/') and
                '\\' not in path and all(part not in ('', '.', '..') for part in path.split('/')) and
                PurePosixPath(path).suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'),
                f'{label}: invalid asset path')
        require(path not in paths, f'{label}: duplicate asset path {path}')
        paths.add(path)

    def map_pair(entry, label, role_ids=True):
        identity(entry, label)
        for role in ('dm', 'player'):
            child = entry.get(role)
            image(child, 'maps', f'{label}/{role}', role_ids)
            if role == 'dm':
                require(child.get('visibility') == 'dm_only' and
                        child.get('authority') == 'canonical_geometry',
                        f'{label}: DM map must remain private geometry authority')
            else:
                require(child.get('visibility') == 'player_presentation' and
                        child.get('knowledge_gated') is True,
                        f'{label}: player map must remain knowledge gated')

    maps, art, handouts = (manifests[key] for key in ('maps', 'art', 'handouts'))
    require(isinstance(maps.get('levels'), dict) and maps['levels'], 'maps: levels object required')
    require(isinstance(maps.get('hubs'), dict), 'maps: hubs object required')
    for key, entry in maps['levels'].items():
        map_pair(entry, f'maps/levels/{key}')
    for key, hub in maps['hubs'].items():
        identity(hub, f'maps/hubs/{key}')
        require(isinstance(hub.get('maps'), list) and hub['maps'], f'hub {key}: maps list required')
        for index, entry in enumerate(hub['maps']):
            map_pair(entry, f'maps/hubs/{key}/{index}', role_ids=False)
    map_count = len(paths)
    require(isinstance(art.get('levels'), dict) and art['levels'], 'art: levels object required')
    require(isinstance(art.get('entities'), list), 'art: entities list required')
    scene_count = 0
    for key, entries in art['levels'].items():
        require(isinstance(entries, list), f'art/levels/{key}: list required')
        for index, entry in enumerate(entries):
            image(entry, 'art', f'art/levels/{key}/{index}')
            require(entry.get('visibility') == 'reveal_gated' and
                    isinstance(entry.get('rule'), str) and entry['rule'].strip(),
                    f'art/levels/{key}/{index}: reveal rule required')
            scene_count += 1
    for index, entry in enumerate(art['entities']):
        image(entry, 'art', f'art/entities/{index}')
        require(entry.get('visibility') == 'reveal_gated' and
                isinstance(entry.get('rule'), str) and entry['rule'].strip(),
                f'art/entities/{index}: reveal rule required')
    require(isinstance(handouts.get('handouts'), list), 'handouts: list required')
    for index, entry in enumerate(handouts['handouts']):
        image(entry, 'handouts', f'handouts/{index}')
        require(isinstance(entry.get('reveal_rule'), str) and entry['reveal_rule'].strip(),
                f'handouts/{index}: reveal rule required')
    for data, key, count in ((maps, 'indexed_map_files', map_count),
                             (art, 'indexed_level_scene_assets', scene_count),
                             (art, 'indexed_entity_assets', len(art['entities'])),
                             (handouts, 'indexed_handout_sheets', len(handouts['handouts']))):
        migration = data.get('migration')
        require(isinstance(migration, dict) and type(migration.get(key)) is int and migration[key] == count,
                f'migration {key}: count does not match indexed entries')
    return {'maps': map_count, 'art': scene_count + len(art['entities']),
            'handouts': len(handouts['handouts'])}


def main():
    try:
        counts = validate_manifests()
    except (ValueError, OSError) as exc:
        print(f'Manifest validation failed: {exc}', file=sys.stderr)
        return 1
    print('manifests ok: ' + ', '.join(f'{count} {kind}' for kind, count in counts.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
