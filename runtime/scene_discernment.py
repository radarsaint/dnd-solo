"""Reusable private read before an NPC/world performance is chosen.

The source adapter decides which story scopes and actors exist. The DM model
chooses which, if any, matter to this player move. This module validates those
references; it cannot determine whether the model's interpretation is good.
"""

from .state_context import require


IMPROV_READ_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'story_anchor': {'type': 'string', 'enum': ['none', 'scene', 'level', 'campaign']},
        'story_basis': {'type': 'string'},
        'actor_ref': {'type': 'string'},
        'actor_basis': {'type': 'string', 'enum': ['none', 'motive', 'immediate_goal']},
        # One line (~160 characters): the bid as declared, the pressure it meets, and what Kit
        # makes of it. Replaces player_bid + connection + kit_choice (plan update #3, PR3 b).
        'kit_choice': {'type': 'string', 'maxLength': 320},
    },
    'required': ['story_anchor', 'story_basis', 'actor_ref', 'actor_basis', 'kit_choice'],
}
# Accepted from older hosts and kept in memory when sent; no longer asked for.
LEGACY_READ_FIELDS = ('player_bid', 'connection')
KIT_CHOICE_TARGET_CHARS = 160


def discernment_candidates(dm_context):
    """Bound references to live actors and explicitly active story scopes.

    An adapter must mark a level or campaign context active_here to make it
    eligible. A local scene is always available, but may be declined.
    """
    scene = dm_context['scene']
    actors = dm_context['dm_only']['actors']
    story_bases = {'none': ['none'], 'scene': ['scene_state']}
    for scope in ('level', 'campaign'):
        context = dm_context.get(f'{scope}_context') or {}
        if context.get('active_here') is True:
            bases = [key for key, value in context.items()
                     if key not in ('active_here', 'source_ref') and value]
            if bases:
                story_bases[scope] = bases
    current_area = scene['current_area']
    actor_bases = {'none': ['none']}
    for actor_id, actor in actors.items():
        if actor.get('location') != current_area or actor.get('status') in ('dead', 'fled', 'hidden'):
            continue
        bases = [key for key in ('immediate_goal', 'motive') if actor.get(key)]
        if bases:
            actor_bases[actor_id] = bases
    return {'story_bases': story_bases, 'actor_bases': actor_bases}


def check_improv_read(read, candidates):
    require(isinstance(read, dict) and set(read) - set(LEGACY_READ_FIELDS) == set(IMPROV_READ_SCHEMA['required']),
            'Incomplete scene discernment')
    for field in ('kit_choice',) + tuple(f for f in LEGACY_READ_FIELDS if f in read):
        value = read[field]
        require(isinstance(value, str) and 0 < len(value.strip()) <= 320,
                f'Invalid scene discernment {field}')
    require(isinstance(read['story_anchor'], str) and
            read['story_anchor'] in candidates['story_bases'],
            'Story anchor is not active here')
    require(isinstance(read['story_basis'], str) and
            read['story_basis'] in candidates['story_bases'][read['story_anchor']],
            'Story basis is not established for this anchor')
    actor = read['actor_ref']
    require(isinstance(actor, str) and actor in candidates['actor_bases'],
            'Actor is not available in this scene')
    require(isinstance(read['actor_basis'], str) and
            read['actor_basis'] in candidates['actor_bases'][actor],
            'Actor basis is not established for this actor')
