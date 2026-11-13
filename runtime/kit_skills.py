"""Intent-to-skill map. Compiled at import, cheap to consult on every turn.

SRD skill uses only. No adventure text. A stated skill with a reason
overrides the map. Investigation is the fallback when nothing fits better.
History is only for past events, places, people, kingdoms, or wars.
"""
import re

# First match wins. Investigation is not matched here; it is the fallback.
# Each row is (skill, short use for the play card, intent pattern).
SKILL_USES = (
    ('athletics',
     'climbing, jumping, swimming, pushing, or breaking',
     r"(?i)\b(?:climb|climbing|jump|jumping|swim|swimming|lift|shove|"
     r"push(?:ing)?|break down|force the (?:door|gate)|grapple|pull up)\b"),
    ('acrobatics',
     'balancing, tumbling, or slipping through tight spaces',
     r"(?i)\b(?:balanc(?:e|ing)|tumble|tumbling|somersault|tightrope|"
     r"slip through|keep my footing|land on my feet)\b"),
    ('sleight_of_hand',
     'picking pockets, palming, or planting an object',
     r"(?i)\b(?:pick(?:ing)? pockets?|palm(?:ing)?|plant(?:ing)?|"
     r"sleight|pickpocket|slip (?:it|the|a) into)\b"),
    ('stealth',
     'hiding, sneaking, or moving unseen',
     r"(?i)\b(?:hide|hiding|sneak|sneaking|lurk|move unseen|"
     r"stay out of sight|creep|stealth)\b"),
    ('animal_handling',
     'calming or reading an animal',
     r"(?i)\b(?:calm(?:ing)? the|soothe|soothing|animal handling|"
     r"read(?:ing)? (?:the |this |that )?(?:horse|hound|dog|beast|animal|wolf)|"
     r"the (?:horse|hound|dog|beast|animal) (?:is|looks|seems))\b"),
    ('medicine',
     'wounds, illness, or cause of death',
     r"(?i)\b(?:wound|wounds|injury|injured|illness|disease|poisoned|"
     r"cause of death|how (?:did|they) die|first aid|bandage|medicine)\b"),
    ('survival',
     'tracking, navigation, or foraging',
     r"(?i)\b(?:track|tracking|tracks|navigate|navigation|forage|"
     r"foraging|find (?:food|water|a path)|which way)\b"),
    ('perception',
     'noticing, spotting, or listening',
     r"(?i)\b(?:look around|look carefully|notice|noticing|spot|spotting|"
     r"listen|listening|peer|scan|keep watch|perception)\b"),
    ('insight',
     "reading a person's intent, mood, or lies",
     r"(?i)\b(?:lying|is (?:she|he|they) lying|intent|ulterior|"
     r"read (?:her|him|them|the room)|trust them|insight|"
     r"tell(?:ing)? the truth|hiding something)\b"),
    ('intimidation',
     'threats, coercion, or a show of force',
     r"(?i)\b(?:intimidate|threaten|threat|coerce|glare|scare|"
     r"show of force|back down)\b"),
    ('deception',
     'lying, bluffing, or disguising intent',
     r"(?i)\b(?:lie to|lying to|bluff|bluffing|disguise|feint|"
     r"pretend|deceive|deception|cover story)\b"),
    ('persuasion',
     'convincing, bargaining, or appealing',
     r"(?i)\b(?:persuade|convince|bargain|appeal|negotiate|"
     r"talk them into|charm|persuasion)\b"),
    ('religion',
     'gods, rites, holy symbols, undead, or cults',
     r"(?i)\b(?:god|gods|deity|temple|shrine|faith|holy|priest|"
     r"rite|rites|ritual of|undead|cult|cults|religion|cleric|"
     r"holy symbol)\b"),
    ('arcana',
     'magic, spells, planes, or magic items',
     r"(?i)\b(?:magic|spell|spells|arcane|wizard|enchant|enchanted|"
     r"ritual|plane|planes|planar|magic item|wand|scroll|arcana)\b"),
    ('nature',
     'terrain, weather, plants, animals, or natural creatures',
     r"(?i)\b(?:terrain|weather|plant|plants|animal|animals|beast|"
     r"wilderness|nature|forest|storm|herb|natural creature|"
    r"mountain|mountains|hills?|caves?)\b"),
    ('history',
     'past events, places, people, kingdoms, or wars',
     r"(?i)\b(?:history|historical|past events?|war|wars|kingdom|"
     r"kingdoms|empire|dynasty|legend|legends|founded|centuries|"
     r"who ruled|the old wars?|heritage|"
     r"this (?:village|town|city|kingdom|empire|realm))\b"),
    ('investigation',
     'deducing from clues or searching objects',
     r"(?i)\b(?:clue|clues|deduce|search(?:ing)? (?:the |this |that )?(?:chest|crate|desk|body|object|room)|"
     r"examine|inspect|footprint|handout|investigation)\b"),
)

FALLBACK = 'investigation'

_COMPILED = tuple(
    (skill, use, re.compile(pattern)) for skill, use, pattern in SKILL_USES
)

_SKILL_NAMES = {
    'athletics': 'athletics',
    'acrobatics': 'acrobatics',
    'sleight of hand': 'sleight_of_hand',
    'sleight_of_hand': 'sleight_of_hand',
    'stealth': 'stealth',
    'animal handling': 'animal_handling',
    'animal_handling': 'animal_handling',
    'medicine': 'medicine',
    'survival': 'survival',
    'perception': 'perception',
    'insight': 'insight',
    'intimidation': 'intimidation',
    'deception': 'deception',
    'persuasion': 'persuasion',
    'religion': 'religion',
    'arcana': 'arcana',
    'nature': 'nature',
    'history': 'history',
    'investigation': 'investigation',
}

# "use Arcana", "I'd like to use Insight because...", "can I try Religion"
_STATED = re.compile(
    r"(?i)\b(?:(?:i(?:'|’)d like to |i want to |i will |let me |can i )?"
    r"(?:use|try|trying|using)\s+)"
    r"(athletics|acrobatics|sleight of hand|sleight_of_hand|stealth|"
    r"animal handling|animal_handling|medicine|survival|perception|"
    r"insight|intimidation|deception|persuasion|religion|arcana|"
    r"nature|history|investigation)\b"
)


def stated_intent_skill(action):
    """A skill the host or player named for this act, or None."""
    text = action or ''
    try:
        from . import kit_rolls
        named = kit_rolls.stated_skill(text)
        if named and named in _SKILL_NAMES.values():
            return named
    except Exception:
        named = None
    hit = _STATED.search(text)
    if hit:
        return _SKILL_NAMES.get(hit.group(1).casefold())
    return None


def skill_for_intent(action, stated=None):
    """The skill that fits this action or question. Investigation if none fits better.

    A stated skill (host override with a reason, or a named skill) wins.
    """
    chosen = stated or stated_intent_skill(action)
    if chosen:
        return chosen
    text = action or ''
    for skill, _use, pattern in _COMPILED:
        if pattern.search(text):
            return skill
    return FALLBACK


def uses_for(skill):
    """The short SRD use line for a skill, or empty."""
    for name, use, _pattern in _COMPILED:
        if name == skill:
            return use
    if skill == FALLBACK:
        return 'deducing from clues or searching objects'
    return ''
