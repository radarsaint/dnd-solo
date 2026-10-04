"""The fidelity diff (runtime/kit_fidelity.py) against source manifests (runtime/kit_extract.py).

Source-agnostic: every test here builds its room mechanically from whatever manifest the
extractor produced (tests/authoring_rooms.py), then breaks it one way at a time. The same
mutations run over every synthetic keyed area (always) and over real book areas when a
book text is configured (skipped otherwise; no book text is committed). A design-doc
manifest Kit writes herself goes through the very same checker."""
import copy
import json
import os
import unittest
from pathlib import Path

from runtime import kit_author, kit_extract, kit_fidelity, kit_source
from tests.authoring_rooms import faithful_room, slug

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/authoring'


def synthetic():
    return kit_author.Book(1, source=FIX / 'keyed_text.txt', map_index=FIX / 'MAP_INDEX.md',
                           ledger=FIX / 'no-ledger.json')


def errors(room, inputs):
    return kit_author.validate(room, inputs)['errors']


def hidden_actors(room):
    return [k for k, a in room['actors'].items() if a.get('status') == 'hidden']


def counted(inputs):
    return [e for e in inputs['manifest']['creatures'] if e.get('count') and not e.get('npc')]


# Each mutation: (name, change(room, inputs) -> expected error fragment, or None when it does not apply).

def total(inputs, kind):
    return sum(e['count'] for e in counted(inputs) if e['kind'] == kind)


def drop_one_creature(room, inputs):
    for entry in counted(inputs):
        keys = [k for k in room['actors'] if k.startswith(slug(entry['kind']) + '_')]
        if keys:
            del room['actors'][keys[-1]]
            for t in room.get('triggers', ()):
                t['actors'] = [a for a in t['actors'] if a != keys[-1]]
            return f'the source has {total(inputs, entry["kind"])} {entry["kind"]}'


def add_one_creature(room, inputs):
    for entry in counted(inputs):
        keys = [k for k in room['actors'] if k.startswith(slug(entry['kind']) + '_')]
        if keys:
            room['actors'][keys[0] + '_extra'] = copy.deepcopy(room['actors'][keys[0]])
            for t in room.get('triggers', ()):
                if keys[0] in t['actors']:
                    t['actors'].append(keys[0] + '_extra')
            return f'the source has {total(inputs, entry["kind"])} {entry["kind"]}'


def reveal_a_hidden_creature(room, inputs):
    for key in hidden_actors(room):
        room['actors'][key].update(status='alive', visible=True)
        return f'actor {key}: the source keeps it out of sight'


def invent_a_creature(room, inputs):
    room['actors']['owlbear'] = {'name': 'Owlbear', 'location': 'inside', 'status': 'alive', 'visible': True,
                                 'motive': 'Hunt.', 'knowledge': [], 'secrets': [], 'stat_block': {'srd': 'Owlbear'}}
    return 'actor owlbear (owlbear) is not in the source'


def invent_stats(room, inputs):
    for key, actor in room['actors'].items():
        actor.pop('needs_stats', None)
        actor['stat_block'] = {'ac': 18, 'hp': 90, 'attacks': [{'name': 'Bite', 'to_hit': 11, 'damage': '4d10'}]}
        return f'actor {key} inline stat_block numbers the source does not state'


def an_srd_name_that_is_not_listed(room, inputs):
    for key, actor in room['actors'].items():
        actor.pop('needs_stats', None)
        actor['stat_block'] = {'srd': 'Tarrasque Prime'}
        return f"actor {key} stat_block srd 'Tarrasque Prime' is not in runtime/srd_creatures.py"


def an_srd_hp_the_source_does_not_state(room, inputs):
    for key, actor in room['actors'].items():
        if 'srd' in actor.get('stat_block', {}):
            actor['stat_block']['hp'] = 997
            return f'actor {key} stat_block hp 997 is not a number the source states'


def drop_a_named_npc(room, inputs):
    for npc in inputs['manifest']['npcs']:
        del room['actors'][slug(npc['name'].split()[0])]
        return f'missing named NPC {npc["name"]}'


def drop_a_secret(room, inputs):
    """Drop the secret sentence with the most words no other sentence uses (one whose facts
    the rest of the room repeats is still carried)."""
    sentences = inputs['manifest']['sentences']

    def distinct(s):
        others = set().union(*[kit_extract.stems(o['text'], 4) for o in sentences if o is not s])
        return kit_extract.stems(s['text'], 4) - others - kit_fidelity.GENERIC
    secret = [s for s in sentences if s['secret'] and s['id'] in inputs['manifest']['must_carry']
              and not any(n['name'].split()[0] in s['text'] for n in inputs['manifest']['npcs'])
              and s['id'] not in {t['feature'] for t in room.get('traps', ())}]
    best = max(secret, key=lambda s: len(distinct(s)), default=None)
    if best and len(distinct(best)) >= 2:
        room['facts'].pop(best['id'])
        return 'not carried in'


def a_deception_only_in_public(room, inputs):
    for s in inputs['manifest']['sentences']:
        if s.get('deception'):
            room['facts'][s['id']]['visible'] = True
            for actor in room['actors'].values():
                actor['secrets'] = []
            return 'not carried in dm-side'


def drop_the_treasure(room, inputs):
    for item in inputs['manifest']['items']:
        room['facts'].pop(item['sentence'], None)
        return f'missing item {item["name"]!r}'


def invent_a_dc(room, inputs):
    room['facts']['here']['text'] = 'A DC 19 Strength check would shift the debris.'
    return 'facts.here.text: dc 19 is not a number the source states'


def show_a_dc_in_public(room, inputs):
    dcs = inputs['manifest']['numbers']['dc']
    if dcs:
        room['areas']['approach']['tease']['text'] = f'A DC {dcs[0]} check would tell you more.'
        return 'shows a game number'


def invent_treasure(room, inputs):
    room['facts']['here']['text'] = 'A sphere of annihilation hums in the corner, and 400 gp lie beside it.'
    return "'sphere of annihilation' is not in the source"


def invent_gp(room, inputs):
    room['facts']['extra'] = {'area': 'inside', 'visible': False, 'text': 'A purse with 4321 gp.'}
    return 'gp 4321 is not a number the source states'


def drop_the_trap(room, inputs):
    if inputs['manifest']['hazards']:
        room.pop('traps')
        return 'declare it in traps'


def change_the_trap_dice(room, inputs):
    if inputs['manifest']['hazards']:
        room['traps'][0]['effect']['damage'] = [{'dice': '9d12', 'type': 'fire'}]
        return "dice 9d12 are not the source's"


def drop_what_the_source_sets_off(room, inputs):
    if inputs['manifest']['scripted'] and not hidden_actors(room):
        room.pop('triggers', None)
        room.pop('traps', None)
        return 'the source sets something off'


def invent_a_secret_door(room, inputs):
    m = inputs['manifest']
    if m['secret_ways'] or any(e.get('secret') for e in m['exits']):
        return None
    room['areas']['crawl'] = {'name': 'Crawlway', 'called': 'the crawlway', 'source_area': m['area']}
    room['exits']['crawl'] = {'name': 'the crawlway', 'areas': ['inside', 'crawl'], 'secret': True,
                              'labels': {'inside': 'A crawlway.', 'crawl': 'Back.'}}
    return 'exit crawl is secret but the source names no secret door'


def invent_a_place_name(room, inputs):
    room['areas']['inside']['name'] = 'The Obsidian Reliquary'
    return 'area inside name names a place the source does not'


def an_exit_that_is_not_uncertain(room, inputs):
    for key, edge in room['exits'].items():
        if edge.pop('uncertain', None):
            return f'exit {key} joins another keyed area with no geometry ledger'


def drop_a_way(room, inputs):
    for e in inputs['manifest']['exits']:
        if e.get('way') and not e.get('sibling'):
            area = f'to_{slug(e["area"])}'
            room['areas'].pop(area)
            room['exits'].pop(f'way_{slug(e["area"])}')
            return f'the source names a way to area {e["area"]}'


def link_a_neighbour_that_is_no_way(room, inputs):
    for e in inputs['manifest']['exits']:
        if not e.get('way') and not e.get('sibling'):
            room['areas']['wrong'] = {'name': 'Beyond', 'called': 'beyond', 'source_area': e['area'], 'outside': True,
                                      'beyond': True, 'room_link': {'author': {'level': inputs['level'], 'area': e['area']}}}
            room['exits']['wrong'] = {'name': 'the way on', 'areas': ['inside', 'wrong'], 'secret': False,
                                      'uncertain': True, 'labels': {'inside': 'On.', 'wrong': 'Back.'}}
            return f'area wrong stands for {e["area"]}, which the source mentions but not as a way from here'


def _hidden_name(room):
    for key in hidden_actors(room):
        return key, room['actors'][key]['name'].split()[-1].lower() + 's'


def leak_in(field):
    def mutate(room, inputs):
        found = _hidden_name(room)
        if not found:
            return None
        key, noun = found
        line = f'You notice {noun} here.'
        if field == 'tease':
            room['areas']['approach']['tease']['text'] = line
        elif field == 'heard':
            room['areas']['approach']['tease']['heard'] = [{'actor': key, 'sound': f'{noun} rustling'}]
        elif field == 'handling':
            room['facts']['here']['handling'] = {'nouns': ['space'], 'look': line}
        elif field == 'go_text':
            room['exits']['in']['go_text'] = {'inside': line}
        elif field == 'label':
            room['exits']['in']['labels']['approach'] = line
        elif field == 'arrival':
            room['areas']['inside']['arrival'] = line
        elif field == 'hook':
            room['story']['inside']['hooks'] = [{'id': 'h', 'primary': True, 'within_beats': 2, 'text': line,
                                                 'delivered_when': {'fact_known': 'here'}}]
            room['areas']['approach']['tease']['points_to'] = 'h'
        return f'names hidden actor {key}'
    return mutate


def leak_a_secret_word(room, inputs):
    m = inputs['manifest']
    public = set().union(*[kit_extract.stems(s['text'], 4) for s in m['sentences'] if not s.get('private', s['secret'])])
    for s in m['sentences']:
        words = sorted(kit_extract.stems(s['text'], 4) - public - kit_fidelity.GENERIC) if s['secret'] else []
        plain = [w for w in s['text'].replace('.', ' ').replace(',', ' ').split()
                 if kit_extract.stem(kit_extract.norm(w)) in words and len(w) >= 5]
        if plain and not any(n['name'].split()[0] in s['text'] for n in m['npcs']):
            room['areas']['approach']['tease']['text'] = f'From here you can make out {plain[0]}.'
            return f'area approach tease names hidden fact {s["id"]}'


MUTATIONS = [
    drop_one_creature, add_one_creature, reveal_a_hidden_creature, invent_a_creature, invent_stats,
    an_srd_name_that_is_not_listed, an_srd_hp_the_source_does_not_state, drop_a_named_npc, drop_a_secret,
    a_deception_only_in_public, drop_the_treasure, invent_a_dc, show_a_dc_in_public, invent_treasure, invent_gp,
    drop_the_trap, change_the_trap_dice, drop_what_the_source_sets_off, invent_a_secret_door, invent_a_place_name,
    an_exit_that_is_not_uncertain, drop_a_way, link_a_neighbour_that_is_no_way, leak_a_secret_word,
    *[leak_in(f) for f in ('tease', 'heard', 'handling', 'go_text', 'label', 'arrival', 'hook')],
]


class Harness:
    """Runs every mutation over every area of ``book``; each area's faithful room must pass."""
    areas = ()

    def book(self):
        raise NotImplementedError

    def test_the_faithful_room_passes_for_every_area(self):
        book = self.book()
        for key in self.areas:
            with self.subTest(area=key):
                inputs = kit_author.area_inputs(book, key)
                self.assertEqual(errors(faithful_room(inputs), inputs), [])

    def test_every_mutation_is_rejected_where_it_applies(self):
        book = self.book()
        applied = set()
        for key in self.areas:
            inputs = kit_author.area_inputs(book, key)
            for mutate in MUTATIONS:
                room = faithful_room(inputs)
                want = mutate(room, inputs)
                if want is None:
                    continue
                applied.add(getattr(mutate, '__name__', 'leak'))
                with self.subTest(area=key, mutation=mutate.__name__):
                    found = errors(room, inputs)
                    self.assertTrue(any(want in e for e in found), f'{want!r} not in {found}')
        self.assertGreaterEqual(len(applied), self.minimum_classes)

    def test_all_the_mutations_at_once_are_reported_together(self):
        book = self.book()
        for key in self.areas:
            inputs = kit_author.area_inputs(book, key)
            room, wants = faithful_room(inputs), []
            for mutate in (drop_one_creature, reveal_a_hidden_creature, invent_a_creature, drop_a_secret,
                           drop_the_treasure, invent_treasure, drop_the_trap, an_exit_that_is_not_uncertain,
                           invent_a_place_name):
                want = mutate(room, inputs)
                if want:
                    wants.append(want)
            found = errors(room, inputs)
            with self.subTest(area=key):
                for want in wants:
                    self.assertTrue(any(want in e for e in found), f'{want!r} not in {found}')


class SyntheticAreas(Harness, unittest.TestCase):
    areas = ('1', '2', '2a', '2b', '3', '4')
    minimum_classes = 24

    def book(self):
        return synthetic()

    def test_the_manifest_reads_each_kind_of_area(self):
        book = synthetic()
        m = {k: kit_author.area_inputs(book, k)['manifest'] for k in self.areas}
        self.assertEqual([n['name'] for n in m['1']['npcs']], ['Ysolde Marr'])
        self.assertTrue(any(s.get('deception') for s in m['1']['sentences']))     # "She claims ... In fact"
        self.assertEqual([(c['kind'], c['count'], c['hidden']) for c in m['3']['creatures']], [('stirge', 4, True)])
        self.assertEqual([i['name'] for i in m['3']['items']], ['rusted lockbox'])
        self.assertTrue(m['3']['scripted'])
        self.assertEqual([(h['damage'], h['dc']) for h in m['2a']['hazards']],
                         [([{'dice': '2d6', 'type': 'piercing'}], [12])])
        self.assertEqual([i['name'] for i in m['4']['items']], ['silver flask'])
        exits = {e['area']: e for e in m['4']['exits']}
        self.assertFalse(exits['1']['way'])                    # "kept in area 1" is no way out
        self.assertTrue(exits['2b']['secret'] and exits['2b']['back_reference'])
        self.assertTrue(m['2b']['secret_ways'])

    def test_a_secret_door_named_only_from_the_other_side_may_be_secret(self):
        inputs = kit_author.area_inputs(synthetic(), '4')
        room = faithful_room(inputs)
        self.assertTrue(room['exits']['way_2b']['secret'])
        self.assertEqual(errors(room, inputs), [])

    def test_alarm_responders_stand_for_the_creatures_the_source_sends(self):
        inputs = kit_author.area_inputs(synthetic(), '1')
        room = faithful_room(inputs)
        bells = [f for f in room['facts'].values() if f.get('alarm')]
        self.assertEqual(bells[0]['alarm']['responders'][0]['count'], 2)
        self.assertEqual(bells[0]['alarm']['arrives_in_rounds'], 2)
        self.assertEqual(errors(room, inputs), [])
        for fact in bells:
            fact['alarm']['responders'][0]['count'] = 3
        self.assertTrue(any('the source has 2 guard' in e for e in errors(room, inputs)))

    def test_a_modifier_the_source_uses_openly_is_not_a_tell_but_the_noun_is(self):
        inputs = kit_author.area_inputs(synthetic(), '3')
        room = faithful_room(inputs)
        for key in hidden_actors(room):
            room['actors'][key]['name'] = 'Lantern stirge'
        room['facts']['here']['text'] = 'A rusted lantern hangs from a hook.'      # the source says it openly
        self.assertEqual(errors(room, inputs), [])
        room['facts']['here']['text'] = 'A rusted lantern hangs from a hook, and a stirge wing pokes out.'
        self.assertTrue(any('names hidden actor' in e and 'stirg' in e for e in errors(room, inputs)))

    def test_the_feature_that_holds_a_secret_may_describe_it_when_handled(self):
        inputs = kit_author.area_inputs(synthetic(), '4')
        room = faithful_room(inputs)
        secret = next(s['id'] for s in inputs['manifest']['sentences'] if 'niche' in s['text'])
        room['facts']['pane'] = {'area': 'inside', 'visible': True, 'text': 'Two tall panes of smoked glass.',
                                 'handling': {'nouns': ['pane'], 'holds': secret,
                                              'search': 'Your hand passes through the north pane into a niche.'}}
        self.assertEqual(errors(room, inputs), [])
        room['facts']['pane']['handling'].pop('holds')
        self.assertTrue(any(f'names hidden fact {secret}' in e for e in errors(room, inputs)))

    def test_source_claims_settle_an_uncounted_creature_and_need_real_quotes(self):
        inputs = kit_author.area_inputs(synthetic(), '4')
        room = faithful_room(inputs)
        room['actors']['skeleton_2'] = copy.deepcopy(room['actors']['skeleton_1'])
        room['source_claims'] = [{'quote': 'a skeletal reflection of it steps out of each one',
                                  'actors': ['skeleton_1', 'skeleton_2']}]
        self.assertEqual(errors(room, inputs), [])
        room['source_claims'][0]['quote'] = 'three skeletons guard the gallery'
        self.assertTrue(any('is not in the source text for this area' in e for e in errors(room, inputs)))


@unittest.skipUnless(kit_source.source_text_path() and kit_source.source_text_path().is_file(),
                     'no book text configured (KIT_SOURCE_TEXT or config/kit_source.json)')
class BookAreas(Harness, unittest.TestCase):
    """Real keyed areas of a configured book: a lair with hidden creatures, an ooze under
    water, duplicates, a disguised NPC, a pit trap, a rat nest with a named NPC."""
    areas = ('17a', '17b', '3', '21', '31', '28d', '35')
    minimum_classes = 22

    def book(self):
        return kit_author.book_for(1)


class DesignDocManifests(unittest.TestCase):
    """A keyed area Kit designs herself: the design_doc extractor passes her manifest through
    and the same checker diffs the room against it."""

    MANIFEST = {
        'area': '7', 'sentences': [
            {'id': 'd1', 'text': 'A collapsed kiln fills the north end of the workshop.', 'secret': False},
            {'id': 'd2', 'text': 'Two mud elementals sleep in the ash and rise if the kiln is touched.', 'secret': True},
            {'id': 'd3', 'text': 'A clay jar under the ash holds 30 gp.', 'secret': True, 'kind': 'treasure'}],
        'creatures': [{'kind': 'mud elemental', 'count': 2, 'hidden': True, 'sentence': 'd2',
                       'quote': 'Two mud elementals sleep in the ash'}],
        'npcs': [], 'items': [{'name': 'clay jar', 'gp': 30, 'sentence': 'd3', 'quote': 'A clay jar under the ash'}],
        'hazards': [], 'scripted': [{'sentence': 'd2', 'quote': 'rise if the kiln is touched'}],
        'numbers': {'dc': [], 'hp': [], 'gp': [30], 'dice': [], 'to_hit': [], 'ac': []},
        'must_carry': ['d2', 'd3'], 'exits': [{'area': '6', 'title': 'Yard', 'way': True, 'secret': False, 'quote': ''}]}

    def manifest(self):
        return kit_extract.extract({'key': '7', 'manifest': self.MANIFEST}, 'design_doc')

    def room(self, manifest):
        inputs = {'level': '01', 'area': {'key': '7'}, 'manifest': manifest, 'geometry': {'bound': False}}
        return faithful_room(inputs)

    def test_a_design_doc_manifest_is_checked_by_the_same_diff(self):
        manifest = self.manifest()
        self.assertEqual(manifest['extractor'], 'design_doc')
        room = self.room(manifest)
        found, _ = kit_fidelity.check(room, manifest, {'bound': False})
        self.assertEqual(found, [])
        del room['actors']['mud_elemental_2']
        room['areas']['approach']['tease']['text'] = 'You hear an elemental grumbling in the ash.'
        found, _ = kit_fidelity.check(room, manifest, {'bound': False})
        self.assertTrue(any('the source has 2 mud elemental' in e for e in found), found)
        self.assertTrue(any('names hidden actor' in e for e in found), found)

    def test_a_design_doc_missing_a_field_is_refused(self):
        broken = {k: v for k, v in self.MANIFEST.items() if k != 'must_carry'}
        with self.assertRaises(ValueError):
            kit_extract.extract({'key': '7', 'manifest': broken}, 'design_doc')

    def test_the_checker_never_reads_source_formatting(self):
        """The book's conventions (bold labels, DC notation, parentheticals, 'area N') are
        the extractor's; the checker module imports none of them."""
        text = (ROOT / 'runtime/kit_fidelity.py').read_text(encoding='utf-8')
        for convention in ('SECRET', 'LABEL', 'DAMAGE', 'area_refs', 'keyed_prose', 'kit_source', 'Mad Mage'):
            self.assertNotIn(convention, text)
        self.assertEqual(set(kit_extract.EXTRACTORS), {'keyed_prose', 'design_doc'})


if __name__ == '__main__':
    unittest.main()
