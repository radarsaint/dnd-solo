"""Detail generation, room-agnostic (runtime/kit_detail.py, kit_texture.py, the canon
ledger in state_context.py). Two synthetic scenes plus area 6c: the mechanism is general,
the card game is one worked example."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from runtime import kit_detail, kit_prices, kit_texture
from runtime.kit_detail import NO_DETAIL, check_detail, check_detail_answer, generic_answer
from runtime.state_context import InvalidChange, Runtime, canon_in_scope


def card(id, entry, basis, roots, tags=(), handle='ask about it', procedure=None):
    return {'id': id, 'entry': entry, 'basis': basis, 'roots': roots, 'tags': list(tags),
            'handle': handle, 'procedure': procedure}


# Scene 1: a Dock Ward taproom (synthetic, not Mad Mage canon).
TAVERN = {
    'id': 'synthetic-dock-ward-taproom', 'fixture_only': True, 'starting_area': 'taproom',
    'areas': {'taproom': {'name': 'The Rusty Gaff taproom'}, 'yard': {'name': 'Back yard'}},
    'exits': {'back_door': {'areas': ['taproom', 'yard'], 'secret': False,
                            'labels': {'taproom': 'A back door to the yard.', 'yard': 'The taproom door.'}}},
    'facts': {
        'bar': {'area': 'taproom', 'visible': True,
                'text': 'A tar-black bar runs the length of the room, hung with fishing nets and gaff hooks.'},
        'fishers': {'area': 'taproom', 'visible': True,
                    'text': 'Three soaked fishers argue over a split catch at the corner table.'},
        'smuggled_casks': {'area': 'taproom', 'visible': False,
                           'text': 'The casks behind the bar hold smuggled Amnian brandy.'},
    },
    'actors': {'barkeep': {'name': 'One-eyed barkeep', 'location': 'taproom', 'status': 'alive', 'visible': True,
                           'motive': 'Keep the watch away from the casks and the fishers paying.',
                           'knowledge': ['What is in the casks.'], 'secrets': ['Sells smuggled brandy.'],
                           'communication_profile': {'rhythm': 'Short.', 'humor': 'Salt-dry.'}}},
    'resources': {},
    'texture_palette': {
        'schema': 'palette_v1',
        '_status': 'DM texture, not adventure fact. Synthetic test palette.',
        'areas': {'taproom': {
            'never_invent': ['what is in the casks'],
            'subjects': {'actor:barkeep': ['barkeep', 'bartender'], 'fishers': ['fishers', 'fisher']},
            'items': [{'id': 'tar_smell', 'kind': 'sense', 'text': 'Pine tar and herring brine hang over everything.',
                       'roots': ['bar']}],
            'decks': {'drink': [
                card('grog', 'Hot rum grog with a burnt lime peel, served in a dented pewter cup', 'real: navy grog',
                     ['bar'], ('familiar', 'tactile')),
                card('bilge', '"Bilgewater": black stout cut with brine, the fishers\' house joke', 'real: oyster stout',
                     ['bar', 'fishers'], ('familiar', 'grave_humor', 'gives_player_a_handle')),
                card('switchel', 'Ginger switchel with a nip of something he keeps under the bar', 'real: switchel',
                     ['bar', 'actor:barkeep'], ('owner_with_a_want',)),
                card('tea_kettle', 'Kettle tea stewed black with sugar, because he is working', 'real: builder\'s tea',
                     ['actor:barkeep'], ('tactile',)),
            ]}}}},
}

# Scene 2: a temple narthex with no deck for its carving (write your own candidates).
TEMPLE = {
    'id': 'synthetic-temple-narthex', 'fixture_only': True, 'starting_area': 'narthex',
    'areas': {'narthex': {'name': 'Narthex of the Morninglord'}, 'nave': {'name': 'Nave'}},
    'exits': {'bronze_door': {'areas': ['narthex', 'nave'], 'secret': False,
                              'labels': {'narthex': 'Tall bronze doors to the nave.', 'nave': 'The narthex doors.'}}},
    'facts': {'bronze_door_face': {'area': 'narthex', 'visible': True,
                                   'text': 'The bronze doors are green with age; a sunburst is worked into each leaf.'},
              'acolyte_sweeping': {'area': 'narthex', 'visible': True,
                                   'text': 'A young acolyte sweeps ash from the threshold.'},
              'relic_vault': {'area': 'narthex', 'visible': False,
                              'text': 'A relic vault lies under the threshold stone.'}},
    'actors': {'acolyte': {'name': 'Young acolyte', 'location': 'narthex', 'status': 'alive', 'visible': True,
                           'motive': 'Finish the sweeping before the high priest returns.',
                           'knowledge': [], 'secrets': [],
                           'communication_profile': {'rhythm': 'Eager.', 'humor': 'Nervous.'}}},
    'resources': {},
    'texture_palette': {'schema': 'palette_v1', '_status': 'DM texture, not adventure fact. Synthetic.',
                        'areas': {'narthex': {'never_invent': ['anything under the threshold'],
                                              'subjects': {'bronze_door': ['door', 'doors']},
                                              'items': [], 'decks': {}}}},
}


def session(source):
    temp = tempfile.TemporaryDirectory()
    runtime = Runtime(Path(temp.name) / 'kit.sqlite')
    runtime.initialize(copy.deepcopy(source), source['starting_area'])
    return temp, runtime


def invention(slot, fact, kind='drink_food', basis='DM choice: the source names no drink here',
              public=True, scope='actor', procedure='none', change_reason='none'):
    return {'slot': slot, 'kind': kind, 'fact': fact, 'basis': basis, 'public': public, 'scope': scope,
            'procedure': procedure, 'change_reason': change_reason}


def decide(request, slot, choice, inventions, candidates=(), typical=-1, chosen=-1, owner='none',
           handle='none', because='none', price_quote=()):
    return {'request': request, 'slot': slot, 'choice': choice, 'candidates': list(candidates),
            'typical': typical, 'chosen': chosen, 'owner': owner, 'handle': handle, 'because': because,
            'price_quote': list(price_quote), 'inventions': list(inventions)}


class TavernSceneTests(unittest.TestCase):
    """Scene 1: 'What's the barkeep drinking?' in a Dock Ward taproom."""

    ASK = "What's the barkeep drinking?"

    def setUp(self):
        self.temp, self.runtime = session(TAVERN)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.runtime.close)
        self.state = self.runtime.load()[1]
        self.oracle = kit_texture.oracle_packet(self.ASK, TAVERN, self.state, 'social')
        self.established = json.dumps(TAVERN) + ' ' + self.ASK

    def check(self, detail, oracle='default', state=None):
        check_detail(detail, self.ASK, 'social', TAVERN, state or self.state, (), self.established,
                     owners=['barkeep'], oracle=self.oracle if oracle == 'default' else oracle)

    def pick(self, index=0, fact=None):
        dealt = self.oracle['deal'][index]
        return decide(self.ASK, self.oracle['slot'], dealt['draw_id'],
                      [invention(self.oracle['slot'], fact or dealt['entry'])],
                      owner='barkeep: keep the fishers drinking and paying',
                      handle='ask for a cup of the same and watch what he pours from',
                      because='true because the barkeep works a tar-black bar hung with gaff hooks')

    def test_the_oracle_deals_a_seeded_ranked_hand_for_the_slot(self):
        self.assertEqual(self.oracle['slot'], 'actor:barkeep/drink')
        self.assertEqual(self.oracle['status'], 'open')
        self.assertTrue(kit_texture.DEAL_MIN <= len(self.oracle['deal']) <= kit_texture.DEAL_MAX)
        self.assertEqual(kit_texture.oracle_packet(self.ASK, TAVERN, self.state, 'social')['deal'],
                         self.oracle['deal'], 'the same seed, slot, and deal count deal the same hand')
        self.assertTrue(self.oracle['deal'][0]['kit_lean'])
        self.assertEqual(sum(card['kit_lean'] for card in self.oracle['deal']), 1)
        # Kit's taste re-ranks: the highest-weighted card leads.
        scores = [kit_texture._taste_score(next(c for c in TAVERN['texture_palette']['areas']['taproom']['decks']['drink']
                                                if c['id'] == dealt['card']), kit_texture.load_taste())
                  for dealt in self.oracle['deal']]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_asking_for_a_detail_requires_an_answer(self):
        self.assertTrue(kit_detail.asks_for_detail(self.ASK))
        with self.assertRaisesRegex(InvalidChange, 'asked for a detail'):
            self.check(dict(NO_DETAIL))

    def test_a_dealt_card_is_accepted_and_the_stock_default_is_rejected(self):
        self.check(self.pick())
        with self.assertRaisesRegex(InvalidChange, 'generic default: answer the invitation'):
            self.check(self.pick(fact='Ale.'))
        with self.assertRaisesRegex(InvalidChange, 'generic default'):
            self.check(self.pick(fact='Just water, same as always.'))

    def test_stock_words_as_color_are_fine(self):
        self.assertTrue(generic_answer('Ale.'))
        self.assertTrue(generic_answer('a mug of ale'))
        self.assertFalse(generic_answer('Ale cut with brine, which the fishers call Bilgewater'))

    def test_the_interpretation_must_be_the_card_chosen(self):
        with self.assertRaisesRegex(InvalidChange, 'dealt card you chose'):
            self.check(self.pick(fact='Plum brandy from Amn in a thimble glass.'))

    def test_owner_handle_and_because_are_required(self):
        detail = self.pick()
        for field, value, reason in (('owner', 'someone: wants things', 'owner'),
                                     ('handle', 'none', 'handle'),
                                     ('because', 'it is cool', 'true because'),
                                     ('because', 'true because the moon is purple tonight', 'because test failed')):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(InvalidChange, reason):
                    self.check({**detail, field: value})

    def test_override_needs_a_reason_and_candidates(self):
        detail = {**self.pick(), 'choice': 'override: the fishers already joked about stout'}
        with self.assertRaisesRegex(InvalidChange, 'candidates'):
            self.check(detail)
        candidates = [{'idea': 'ale', 'uses': 'the bar', 'creates': 'nothing'},
                      {'idea': 'Hot rum grog in pewter', 'uses': 'tar-black bar', 'creates': 'ask for a cup'},
                      {'idea': 'Brine-cut stout the fishers mock', 'uses': 'fishers argue', 'creates': 'join the joke'}]
        self.check({**detail, 'candidates': candidates, 'typical': 0, 'chosen': 2,
                    'inventions': [invention(self.oracle['slot'], 'Brine-cut stout, which the fishers call Bilgewater')]})
        with self.assertRaisesRegex(InvalidChange, 'most typical candidate'):
            self.check({**detail, 'candidates': candidates, 'typical': 0, 'chosen': 0})

    def test_the_private_plan_never_asks_for_small_or_safe(self):
        with self.assertRaisesRegex(InvalidChange, 'Shrinking direction'):
            self.check({**self.pick(), 'handle': 'offer the player a small, simple drink order'})
        with self.assertRaisesRegex(InvalidChange, 'Shrinking direction'):
            kit_detail.check_not_shrinking(['Let the dealer offer a small, playable wager.'])

    def test_answer_persists_in_the_canon_ledger_and_returns_on_the_next_ask(self):
        detail = self.pick()
        events = kit_detail.canon_events(detail, 't1', self.oracle)
        self.assertEqual([event['type'] for event in events], ['canon_entry', 'oracle_draw'])
        self.runtime.commit('t1', 0, events)
        state = self.runtime.load()[1]
        entry = state['canon']['actor:barkeep/drink']
        self.assertEqual(entry['fact'], detail['inventions'][0]['fact'])
        self.assertEqual(entry['roots'], self.oracle['deal'][0]['roots'])
        self.assertEqual(state['oracle']['deals']['actor:barkeep/drink'], 1)
        self.assertIn(self.oracle['deal'][0]['card'], state['oracle']['used']['taproom'])
        # The player sees it as an established detail; the next ask reuses it, no new deal.
        view = self.runtime.player_view()
        self.assertEqual(view['established_details'], [{'slot': 'actor:barkeep/drink', 'fact': entry['fact']}])
        again = kit_texture.oracle_packet('What is the bartender drinking now?', TAVERN, state, 'social')
        self.assertEqual((again['status'], again['canon']['fact']), ('canon_supplied', entry['fact']))
        self.assertNotIn('deal', again)

    def test_canon_changes_only_with_an_in_story_reason(self):
        self.runtime.commit('t1', 0, kit_detail.canon_events(self.pick(), 't1', self.oracle))
        state = self.runtime.load()[1]
        slot = 'actor:barkeep/drink'
        changed = invention(slot, 'Kettle tea stewed black with sugar')
        detail = decide(self.ASK, 'self: barkeep/drink', 'self', [changed])
        with self.assertRaisesRegex(InvalidChange, 'Canon says'):
            check_detail({**detail, 'candidates': [], 'choice': 'canon', 'slot': 'self: barkeep/drink'},
                         self.ASK, 'social', TAVERN, state, (), self.established, ['barkeep'], None)
        with self.assertRaisesRegex(InvalidChange, 'without an in-story reason'):
            self.runtime.commit('t2', 1, [{'type': 'canon_entry', **changed, 'procedure': None,
                                           'change_reason': None, 'evidence': 'test'}])
        reason = 'He finished the grog and the fishers stole the pot'
        self.runtime.commit('t2', 1, [{'type': 'canon_entry', **changed, 'procedure': None,
                                       'change_reason': reason, 'evidence': 'test'}])
        entry = self.runtime.load()[1]['canon'][slot]
        self.assertEqual(entry['supersedes']['reason'], reason)

    def test_actor_scoped_canon_follows_the_actor(self):
        self.runtime.commit('t1', 0, kit_detail.canon_events(self.pick(), 't1', self.oracle))
        state = self.runtime.load()[1]
        self.assertIn('actor:barkeep/drink', canon_in_scope(state))
        state['actors']['barkeep']['location'] = 'yard'
        self.assertNotIn('actor:barkeep/drink', canon_in_scope(state))
        state['area'] = 'yard'
        self.assertIn('actor:barkeep/drink', canon_in_scope(state))

    def test_a_used_card_leaves_the_deck(self):
        self.runtime.commit('t1', 0, kit_detail.canon_events(self.pick(), 't1', self.oracle))
        state = self.runtime.load()[1]
        hand = kit_texture.oracle_packet('What are the fishers drinking?', TAVERN, state, 'social')
        self.assertEqual(hand['slot'], 'taproom/fishers/drink')
        self.assertNotIn(self.oracle['deal'][0]['card'], [dealt['card'] for dealt in hand['deal']])

    def test_performance_must_show_the_detail_it_chose(self):
        detail = self.pick()
        shown = [{'speaker': 'Narrator', 'text': 'He lifts a dented pewter cup of hot rum grog, a lime peel '
                                                 'curling black on the rim.'}]
        check_detail_answer(shown, detail, self.ASK)
        with self.assertRaisesRegex(InvalidChange, 'never showed the detail'):
            check_detail_answer([{'speaker': 'Narrator', 'text': 'He shrugs and keeps wiping the bar down.'}],
                                detail, self.ASK)
        with self.assertRaisesRegex(InvalidChange, 'generic default'):
            check_detail_answer([{'speaker': 'Barkeep', 'text': 'Ale.'}], detail, self.ASK)

    def test_prices_come_from_the_srd_with_the_entry_recorded(self):
        ask = 'How much for a mug of that ale?'
        oracle = kit_texture.oracle_packet(ask, TAVERN, self.state, 'social', price_lookup=kit_prices.lookup_hint)
        # Keyed by the item asked about, not the SRD word; "mug" is the tier quoted.
        self.assertEqual((oracle['status'], oracle['slot']), ('priced', 'taproom/price/ale'))
        quote = {'item': 'Bilgewater stout', 'srd_entry': 'Ale, mug', 'magic': 'none'}
        priced = invention(oracle['slot'] + '/mug', 'A mug of Bilgewater stout is 4 cp.', kind='price',
                           basis='SRD 5.1 closest entry; the house names its stout', scope='location')
        detail = decide(ask, oracle['slot'], 'priced', [priced], price_quote=[quote])
        check_detail(detail, ask, 'social', TAVERN, self.state, (), self.established, ['barkeep'], oracle)
        with self.assertRaisesRegex(InvalidChange, 'Never invent one'):
            check_detail({**detail, 'inventions': [{**priced, 'fact': 'A mug of Bilgewater is 2 sp.'}]},
                         ask, 'social', TAVERN, self.state, (), self.established, ['barkeep'], oracle)
        events = kit_detail.canon_events(detail, 'p1', oracle)
        self.assertEqual(events[0]['price'], {'amount': 4, 'unit': 'cp', 'source': 'srd',
                                              'basis': 'SRD 5.1 food_drink_lodging: Ale, mug'})
        self.runtime.commit('p1', 0, events)
        state = self.runtime.load()[1]
        again = kit_texture.oracle_packet(ask, TAVERN, state, 'social', price_lookup=kit_prices.lookup_hint)
        self.assertEqual(again['status'], 'canon_supplied', 'once set, it always keeps that price')
        with self.assertRaisesRegex(InvalidChange, 'already has its price'):
            self.runtime.commit('p2', 1, [{**events[0], 'fact': 'A mug of Bilgewater stout is 5 cp.',
                                           'change_reason': 'The barkeep raised prices on the spot'}])
        # A priced answer names the number.
        with self.assertRaisesRegex(InvalidChange, 'literal question first'):
            check_detail_answer([{'speaker': 'Narrator', 'text': 'He slides a mug of Bilgewater stout over.'}],
                                detail, ask)

    def test_unpriced_things_get_no_number(self):
        ask = 'How much for the gaff hooks on the wall?'
        oracle = kit_texture.oracle_packet(ask, TAVERN, self.state, 'social', price_lookup=kit_prices.lookup_hint)
        self.assertEqual(oracle['status'], 'unpriced')
        self.assertIn('do not invent one', oracle['price']['flag'])
        detail = decide(ask, oracle['slot'], 'unpriced', [])
        check_detail(detail, ask, 'social', TAVERN, self.state, (), self.established, ['barkeep'], oracle)
        invented = invention(oracle['slot'], 'The hooks are 3 gp each.', kind='price',
                             basis='DM choice because nothing lists it', scope='location')
        with self.assertRaisesRegex(InvalidChange, 'price'):
            check_detail(decide(ask, oracle['slot'], 'unpriced', [invented]), ask, 'social', TAVERN, self.state,
                         (), self.established, ['barkeep'], oracle)


class TempleSceneTests(unittest.TestCase):
    """Scene 2: 'What's carved on the door?' with no deck: write your own candidates."""

    ASK = "What's carved on the door?"

    def setUp(self):
        self.temp, self.runtime = session(TEMPLE)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.runtime.close)
        self.state = self.runtime.load()[1]
        self.oracle = kit_texture.oracle_packet(self.ASK, TEMPLE, self.state, 'social')
        self.established = json.dumps(TEMPLE) + ' ' + self.ASK
        self.candidates = [
            {'idea': 'A sunburst', 'uses': 'sunburst worked into each leaf', 'creates': 'nothing new'},
            {'idea': 'Seven kneeling pilgrims, the last one with a fresh ash thumbprint', 'uses': 'acolyte sweeps ash',
             'creates': 'ask the acolyte whose thumb that was'},
            {'idea': 'A sunrise over Waterdeep harbor, green with age', 'uses': 'bronze doors green with age',
             'creates': 'look for the temple on the skyline'}]

    def check(self, detail):
        check_detail(detail, self.ASK, 'social', TEMPLE, self.state, (), self.established,
                     owners=['acolyte'], oracle=self.oracle)

    def detail(self, **changes):
        base = decide(self.ASK, self.oracle['slot'], 'self',
                      [invention(self.oracle['slot'], 'Seven kneeling pilgrims face the sunburst; the last '
                                 'one wears a fresh ash thumbprint', kind='inscription',
                                 basis='DM choice: the source says only sunburst', scope='location')],
                      candidates=self.candidates, typical=0, chosen=1,
                      owner='acolyte: finish the sweeping before anyone notices the thumbprint',
                      handle='ask the acolyte about the thumbprint, or wipe it',
                      because='true because the acolyte sweeps ash from the threshold of these bronze doors')
        return {**base, **changes}

    def test_no_deck_means_open_no_deck_and_self_candidates(self):
        self.assertEqual((self.oracle['slot'], self.oracle['status']), ('narthex/bronze_door/carving', 'open_no_deck'))
        self.check(self.detail())
        with self.assertRaisesRegex(InvalidChange, 'choice must be self'):
            self.check(self.detail(choice='canon'))
        with self.assertRaisesRegex(InvalidChange, '3-5 one-line candidates'):
            self.check(self.detail(candidates=self.candidates[:2]))
        with self.assertRaisesRegex(InvalidChange, 'uses nothing established'):
            self.check(self.detail(candidates=self.candidates[:2] + [
                {'idea': 'A dragon', 'uses': 'dragons are cool', 'creates': 'fight it'}]))

    def test_specificity_floor(self):
        bland = self.detail(inventions=[invention(self.oracle['slot'], 'some pilgrims kneeling there',
                                                  kind='inscription', basis='DM choice: the source is silent',
                                                  scope='location')])
        with self.assertRaisesRegex(InvalidChange, 'Specificity floor'):
            self.check(bland)

    def test_the_answer_must_be_recorded(self):
        with self.assertRaisesRegex(InvalidChange, 'Record the answer'):
            self.check(self.detail(inventions=[]))

    def test_no_invention_may_settle_what_the_source_already_does(self):
        clash = invention('narthex/door/relic_vault', 'A relic vault is under the step', kind='other',
                          basis='DM choice to explain the step', scope='location')
        with self.assertRaisesRegex(InvalidChange, 'collides with a source fact'):
            self.check(self.detail(inventions=self.detail()['inventions'] + [clash]))

    def test_a_game_offered_as_playable_needs_a_runtime_procedure(self):
        dice = invention('narthex/acolyte/game', 'Liar\'s dice for candle stubs, three dice a hand',
                         kind='procedure', basis='real: liar\'s dice', scope='location', procedure='liars_dice')
        with self.assertRaisesRegex(InvalidChange, 'Only a procedure the runtime can run'):
            self.check(self.detail(inventions=self.detail()['inventions'] + [dice]))
        flavor = {**dice, 'kind': 'other', 'procedure': 'none'}
        self.check(self.detail(inventions=self.detail()['inventions'] + [flavor]))

    def test_rules_or_stakes_need_a_declared_procedure(self):
        line = [{'speaker': 'Acolyte', 'text': 'The rules are simple: each player puts in a candle.'}]
        with self.assertRaisesRegex(InvalidChange, 'Undeclared procedure'):
            kit_detail.check_detail_performance(line, ())
        kit_detail.check_detail_performance(line, ('liars_dice',), ('candle', 'dice'))
        kit_detail.check_detail_performance([{'speaker': 'Acolyte', 'text': 'We play liar\'s dice after vespers.'}], ())


class PaletteTests(unittest.TestCase):
    def test_palettes_are_checked_at_init(self):
        broken = copy.deepcopy(TAVERN)
        broken['texture_palette']['areas']['taproom']['decks']['drink'][0]['roots'] = ['no_such_fact']
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = Runtime(Path(temp.name) / 'kit.sqlite')
        self.addCleanup(runtime.close)
        with self.assertRaisesRegex(InvalidChange, 'real source ids'):
            runtime.initialize(broken, 'taproom')
        priced = copy.deepcopy(TAVERN)
        priced['texture_palette']['areas']['taproom']['decks']['price'] = []
        with self.assertRaisesRegex(InvalidChange, 'never dealt'):
            kit_texture.check_palette(priced)

    def test_area_06c_palette_passes_its_leak_checks(self):
        source = json.loads((Path(__file__).parent / 'fixtures/level_01_area_06c.json').read_text())
        kit_texture.check_palette(source)
        games = source['texture_palette']['areas']['area_06c']['decks']['game']
        # Familiar games first: hold 'em and blackjack are dealt as equals of Three-Dragon Ante;
        # only the one the runtime can run carries a procedure.
        self.assertEqual({card['id']: card['procedure'] for card in games}['three_dragon_ante'], 'three_dragon_ante')
        self.assertTrue(all(card['procedure'] is None for card in games if card['id'] != 'three_dragon_ante'))
        self.assertTrue({'real: Texas hold \'em', 'real: blackjack'} <= {card['basis'] for card in games})

    def test_taste_vetoes_never_reach_a_prompt(self):
        from runtime import kit_agent
        taste = kit_texture.load_taste()
        prompts = kit_agent.PRIVATE_INSTRUCTIONS + kit_agent.PUBLIC_INSTRUCTIONS + kit_agent.KIT_EXPRESSION_V1
        for word in ('high card', 'nothing special', 'gruel', 'porridge', 'a matching coin'):
            self.assertIn(word, json.dumps(taste['avoids']))
            self.assertNotIn(word, prompts.casefold())


if __name__ == '__main__':
    unittest.main()
