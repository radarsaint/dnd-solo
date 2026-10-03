"""The passage toll as a conversation with stakes, not a price list (Brendon's table call 6).

The room source can declare ``tolls``: a demand an NPC makes (area 6c: the gang wants
10 gp a head for safe passage). Brendon's call: the toll stands, but when it comes up it
is a full exchange. One NPC asks for it, in character and with a motive; the player can
pay, haggle, refuse, or steer the talk back to the game; refusing has consequences; and
the toll can be played for only if the running table procedure can pay it out.

State lives in ``state['tolls'][id]`` and changes only through ``toll_state`` events:

    status: not_raised | demanded | countered | negotiated | paid | refused | deferred |
            staked | waived
    asked:  the amount on the table now (the demand, or the NPC's counter)
    agreed: a negotiated amount, once the NPC accepts an offer
    paid, offers, haggles, refusals, consequences (each with its source-backed text)

Every player response commits a turn. Haggling is the PC's check (``haggle.skill``)
against the demander's flat 10 + skill; an offer at or above the ask is simply
accepted, and one below the source-side floor gets no traction. Amounts in this state are
what the numeric guard allows characters to name for the toll (kit_agent.guard_context).
Deterministic Python; no model calls.
"""
import copy
import math
import re

from .state_context import require

STATUSES = ('not_raised', 'demanded', 'countered', 'negotiated', 'paid', 'refused', 'deferred',
            'staked', 'waived')
OPEN = ('demanded', 'countered', 'negotiated', 'refused', 'deferred')
SETTLED = ('paid', 'waived')

TOLL_WORDS = re.compile(r"\b(toll|tolls|passage|fee|to pass|pass through|way through|safe passage|"
                        r"a head|per head|your price|the price|protection)\b")
# ONE test for an NPC sentence naming the toll, shared by the detector (raised_events,
# names_toll) and the call-6 guard (kit_guards.check_toll_exchange), so a line that delivers
# the toll is always held to the exchange rule. The stake and the toll can be the same
# amount, so the loose words ("ten gold and you walk out") count only in a sentence with no
# game words; the strong words count anywhere. The player-side TOLL_WORDS stays as it is.
NPC_TOLL_STRONG = re.compile(r"\b(toll|tolls|passage|fee|to pass|pass through|way through|safe passage|"
                             r"a head|per head|your price|the price|protection)\b")
NPC_TOLL_LOOSE = re.compile(r"\b(walk (?:out|on|through)|go (?:on|through)|get (?:out|through))\b")
TOLL_GAME_WORDS = re.compile(r"\b(game|games|cards?|ante|deal|dealt|gambling|gamble|blind|bet|wager|play|"
                             r"hands?|rounds?|table|chair|seat|sit|win|richer)\b")


def npc_names_toll_words(sentence):
    """True when an NPC sentence uses toll words: a strong word anywhere, or a loose word in
    a sentence with no game words (callers also require the toll's amount)."""
    text = (sentence or '').casefold().replace('\u2019', "'")
    return bool(NPC_TOLL_STRONG.search(text) or (NPC_TOLL_LOOSE.search(text) and not TOLL_GAME_WORDS.search(text)))


_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
          'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'half': None}
_WORD_AMOUNT = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|"
                          r"twenty)\b(?:\s+(?:gp|gold|coins?|gold pieces))?")
PLAY_FOR = re.compile(r"\b(play|plays|playing|gamble|bet|wager|cut|deal|cards?|hand|round)\b[^.?!]{0,30}"
                      r"\b(for it|for the toll|for (?:the )?passage|for that|double or nothing|against the toll)\b"
                      r"|\bdouble or nothing\b|\bwin it off\b")
GAME_TALK = re.compile(r"\b(game|cards?|deal|hand|round|play|playing|blackjack|twenty[- ]one|bet|wager|"
                       r"ante|stakes?)\b")
REFUSE = re.compile(r"\b(no deal|not paying|won'?t pay|will not pay|refuse\w*|decline\w*|not a (?:chance|copper|coin)|"
                    r"forget it|keep dreaming|i'?m not paying|no toll|pay nothing|not one coin|go to hell|"
                    r"you'?ll get nothing|not giving you)\b|^\W*no\b(?![^.?!]*\b(?:problem|worries)\b)")
HAGGLE = re.compile(r"\b(haggle|haggling|bargain\w*|too (?:much|steep|rich|high)|lower|cheaper|discount|how about|"
                    r"meet me|a better (?:price|deal)|knock (?:it|some) (?:down|off)|for less|counter\w*|"
                    r"i'?ll give you|i (?:can|could) (?:do|offer|spare)|i offer|make it|what about)\b")
PAY = re.compile(r"\b(i(?:'ll| will)? pay|pay (?:it|the|him|them|up|you)|here'?s (?:the|your|my)|hand (?:it |them )?over|"
                 r"count out|toss (?:him|them|you) (?:the|my) (?:coins|gold)|fine,? (?:here|take it)|deal\b(?=[.!]?$)|"
                 r"i accept|accepted|agreed|you have a deal|it'?s a deal)\b")


# A threat dressed as payment ("I pay with this" over a slammed axe) is never a payment.
WEAPON_WORDS = (r"axe|greataxe|blade|sword|rapier|dagger|knife|steel|fist|fists|knuckles|crossbow|bow|hammer|"
                r"maul|mace|club|spear|scimitar")
THREAT = re.compile(r"\b(pay (?:you |him |them )?with (?:this|that|these|steel|iron|blood|my \w+)|"
                    r"(?:slam|slams|slammed|bury|buries|drive|drives|plant|plants|draw|draws|drew|brandish\w*|"
                    r"level|levels|unsheathe\w*|crack|cracks|thump|thumps)\s+(?:my|the|a|his|her)\s+(?:" +
                    WEAPON_WORDS + r")|or (?:i|we)'?ll (?:kill|gut|break|cut|hurt|bury)|over my dead body|"
                    r"make me|who wants change|try (?:and|to) take it)\b")
# An appeal or a bluff about the toll: an exemption, a friend who vouches, kinship, a favour.
# An appeal or a bluff about the toll. Strong: about passage itself (counts while the toll is
# open). Soft: kinship, a friend's word, a favour (counts when the toll is named or rolled on;
# "cousins, others of the blood" on arrival is a greeting, not a bid on the toll).
APPEAL_STRONG = re.compile(r"\b(waive\w*|let (?:me|us) (?:through|pass|by)|already (?:paid|settled)|"
                           r"settled (?:it|up|the toll)|pass free|free of charge|on the house|no toll)\b")
APPEAL = re.compile(r"\b(between (?:family|friends|kin|cousins|brothers|sisters)|among (?:family|friends|kin)|"
                    r"surely|for (?:a|an old) friend|vouch\w*|know my face|(?:her|his|your) guest|"
                    r"take my word|my word|as a favou?r|professional courtesy|our kind|of the blood|"
                    r"look after our own|turn(?:ed)? away)\b")
SOCIAL_SKILLS = ('deception', 'persuasion', 'intimidation')
STEER = re.compile(r"\b(play|playing|deal me|deal us|deal|bet|bets|betting|wager|ante|stake|join|sit in|buy in|"
                   r"buy-in|blackjack|twenty[- ]one|another (?:round|hand)|next (?:round|hand)|hit|stand)\b")
LOOKING = re.compile(r"\b(search\w*|look\w*|inspect\w*|examin\w*|study\w*|check\w*|admir\w*|peer\w*)\b")
_ROLL_BRACKETS = re.compile(r'\[[^\]]*\]')


def _plain(action):
    """Casefolded text without stated-roll brackets ("[Deception: 22]")."""
    return _ROLL_BRACKETS.sub(' ', action.casefold().replace('\u2019', "'").replace('\u2018', "'")).strip()


def is_question(text):
    """The bid ends on a question, even inside closing quotes ("...surely?'")."""
    return text.rstrip(' .\'"\u201d)').endswith('?')


def compile_tolls(source):
    tolls = {k: v for k, v in ((source or {}).get('tolls') or {}).items() if not k.startswith('_')}
    for key, toll in tolls.items():
        require(type(toll.get('amount')) is int and toll['amount'] >= 1, f'Toll {key}: amount in whole coins')
        require(toll.get('demanded_by') in (source.get('actors') or {}), f'Toll {key}: demanded_by is an actor')
        require(toll.get('area') in (source.get('areas') or {}), f'Toll {key}: area')
        require(type(toll.get('floor', toll['amount'])) is int, f'Toll {key}: floor in whole coins')
        require(isinstance(toll.get('refusal'), list) and toll['refusal'] and
                all(isinstance(item, dict) and item.get('kind') and item.get('text') for item in toll['refusal']),
                f'Toll {key}: refusal lists consequences, each with kind and text')
    return tolls


def initial(toll):
    return {'status': 'not_raised', 'asked': toll['amount'], 'agreed': None, 'paid': 0, 'demanded_by': None,
            'offers': [], 'haggles': 0, 'refusals': 0, 'consequences': []}


def current(source, state, key):
    tolls = compile_tolls(source)
    return copy.deepcopy((state.get('tolls') or {}).get(key) or initial(tolls[key]))


def here(source, state):
    """{id: (config, state)} for the tolls of the current area."""
    return {key: (toll, current(source, state, key)) for key, toll in compile_tolls(source).items()
            if toll['area'] == state.get('area')}


def check_state(body):
    require(isinstance(body, dict) and body.get('status') in STATUSES, 'Toll state needs a known status')
    for key in ('asked', 'paid', 'haggles', 'refusals'):
        require(type(body.get(key)) is int and body[key] >= 0, f'Toll state {key} is a whole number')
    require(body.get('agreed') is None or type(body['agreed']) is int, 'Toll agreed is a whole number')
    require(isinstance(body.get('offers'), list) and len(body['offers']) <= 12, 'Toll offers: at most 12')
    require(isinstance(body.get('consequences'), list) and len(body['consequences']) <= 8,
            'Toll consequences: at most 8')


def apply_event(state, source, event):
    key = event.get('toll')
    require(key in compile_tolls(source), 'Unknown toll')
    check_state(event.get('state'))
    state.setdefault('tolls', {})[key] = copy.deepcopy(event['state'])


def event(key, body, evidence):
    return {'type': 'toll_state', 'toll': key, 'state': body, 'evidence': evidence}


def offered_amount(action):
    from .kit_rolls import without_rolls
    text = without_rolls(action)  # a die face or a roll total is never an offer
    if re.search(r'\bhalf\b', text):
        return 'half'
    for found in re.finditer(r"\b(\d{1,3})\s*(gp|gold|coins?|gold pieces)\b", text):
        return int(found.group(1))
    found = _WORD_AMOUNT.search(text)
    if found and found.group(0) != found.group(1):  # "five gold", not a bare "one"
        return _WORDS[found.group(1)]
    found = re.search(r"\b(?:how about|make it|i(?:'ll| will| can| could)? (?:give|offer|do|spare)(?: you)?)\s+(\d{1,3}|"
                      + '|'.join(w for w in _WORDS if _WORDS[w]) + r")\b", text)
    if found:
        token = found.group(1)
        return int(token) if token.isdigit() else _WORDS[token]
    return None


def intent(action, body, game_running=False):
    """'toll_pay' | 'toll_haggle' | 'toll_appeal' | 'toll_threaten' | 'toll_refuse' |
    'toll_play_for' | 'toll_defer' | None.

    Only a toll that is on the table (or a player who names it) is answered here; game
    talk while it is open defers it (it stays pending and comes back). The reading is by
    what the bid does, not by single words: a payment made "with this" over a slammed axe is
    a threat; "no toll between family, surely?" is an appeal, not a refusal; a stated
    Deception or Persuasion roll on the toll is an appeal or bluff, a stated Intimidation a
    threat; a question is never a refusal or a payment."""
    from . import kit_rolls
    text = _plain(action)
    named = bool(TOLL_WORDS.search(text))
    open_ = body['status'] in OPEN
    if body['status'] in SETTLED or body['status'] == 'staked':
        return None
    if not open_ and not named:
        return None
    if PLAY_FOR.search(text):
        return 'toll_play_for'
    skill = kit_rolls.stated_skill(action)
    skill = skill if skill in SOCIAL_SKILLS else None
    question = is_question(text)
    if THREAT.search(text) or skill == 'intimidation':
        return 'toll_threaten'
    amount = offered_amount(text)
    appeal = APPEAL_STRONG.search(text) or (APPEAL.search(text) and named) or skill
    if appeal and type(amount) is not int and amount != 'half' and not (REFUSE.search(text) and not question
                                                                         and not skill and not named):
        return 'toll_appeal'
    if REFUSE.search(text) and not question:
        return 'toll_refuse'
    ask = body['agreed'] or body['asked']
    if HAGGLE.search(text) or (amount not in (None,) and amount != 'half' and amount < ask) or amount == 'half':
        if not (question and amount is None and not HAGGLE.search(text)):
            return 'toll_haggle'
    if PAY.search(text) and not question:
        return 'toll_pay'
    if open_ and not named and GAME_TALK.search(text) and STEER.search(text) and '?' not in text and \
            not skill and not kit_rolls.stated_skill(action) and not LOOKING.search(text):
        # Steering the talk to the game ("Deal me in", "I'll bet fifty") defers the toll. A
        # question about the game, a search near the card players, or "go on with your
        # game" is not steering (6c baseline V4, V8).
        return 'toll_defer'
    return None


class TollTable:
    """Resolve one toll response into (public_text, new_state, trace lines, events extra)."""

    def __init__(self, key, toll, label, pc_numbers, npc_flat, roll):
        self.key, self.toll, self.label = key, toll, label
        self.pc_numbers = pc_numbers  # skill -> (modifier, passive)
        self.npc_flat = npc_flat      # the demander's flat 10 + skill
        self.roll = roll              # () -> d20
        self.trace = []

    def resolve(self, kind, action, body):
        body = copy.deepcopy(body)
        if body['status'] == 'not_raised':
            body['status'] = 'demanded'
        handler = getattr(self, '_' + kind[len('toll_'):])
        return handler(action, body), body

    def _ask(self, body):
        return body['agreed'] or body['asked']

    def _pay(self, action, body):
        amount = self._ask(body)
        stated = offered_amount(action)
        if type(stated) is int and stated > amount:
            amount = stated
        body.update(status='paid', paid=amount)
        self.trace.append(f'toll paid: {amount} {self.toll["unit"]}')
        return f'You count out {amount} {self.toll["unit"]} for passage. The toll is paid.'

    def _haggle(self, action, body):
        ask, floor = self._ask(body), self.toll.get('floor', self.toll['amount'])
        offer = offered_amount(action)
        if offer == 'half':
            offer = max(1, ask // 2)
        body['haggles'] += 1
        unit = self.toll['unit']
        if type(offer) is int:
            body['offers'] = (body['offers'] + [offer])[-12:]
        if type(offer) is int and offer >= ask:
            body.update(status='negotiated', agreed=offer)
            return f'{offer} {unit} is what was asked. The {self.label.lower()} takes the offer.'
        if type(offer) is int and offer < floor:
            body['status'] = 'countered'
            self.trace.append(f'offer {offer} below the floor {floor}: no roll')
            return f'{offer} {unit} gets no traction. The ask stays at {ask} {unit}.'
        skill = self.toll['haggle']['skill']
        modifier, _ = self.pc_numbers(skill)
        die = self.roll(skill)
        total = die + modifier
        name = skill.replace('_', ' ').title()
        self.trace.append(f'haggle: {name} d20 {die} + {modifier} = {total} vs {self.npc_flat} '
                          f'(10 + {self.toll["haggle"]["npc_skill"]})')
        if type(offer) is not int:
            # "Too steep": no number named. Success brings the ask down to the floor's side.
            if total >= self.npc_flat:
                counter = max(floor, math.ceil((ask + floor) / 2))
                body.update(status='countered', asked=counter)
                return f'The {self.label.lower()} gives ground. The ask comes down to {counter} {unit}.'
            body['status'] = 'countered'
            return f'The {self.label.lower()} does not budge. The ask stays at {ask} {unit}.'
        if total >= self.npc_flat:
            body.update(status='negotiated', agreed=offer)
            return f'The {self.label.lower()} takes {offer} {unit}. That is the toll now, if you pay it.'
        counter = max(floor, math.ceil((offer + ask) / 2))
        body.update(status='countered', asked=counter)
        return f'The {self.label.lower()} turns down {offer} {unit} and comes back at {counter} {unit}.'

    def _contest(self, action, default_skill):
        """The PC's stated (or sheet) roll in the skill the bid uses, against the demander's
        flat 10 + Insight (NPCs never roll). Returns (success, name)."""
        from . import kit_rolls
        skill = kit_rolls.stated_skill(action)
        skill = skill if skill in SOCIAL_SKILLS else default_skill
        modifier, _ = self.pc_numbers(skill)
        die = self.roll(skill)
        total = die + modifier
        name = skill.replace('_', ' ').title()
        self.trace.append(f'{name} d20 {die} + {modifier} = {total} vs {self.npc_flat} '
                          f'(10 + {self.toll["haggle"]["npc_skill"]})')
        return total >= self.npc_flat, name

    def _appeal(self, action, body):
        """An appeal or a bluff (an exemption, kinship, a friend's word): Persuasion, or the
        Deception the player rolls for a lie. Success waives the toll; failure leaves it."""
        success, name = self._contest(action, self.toll['haggle']['skill'])
        ask, unit = self._ask(body), self.toll['unit']
        if success:
            body.update(status='waived', agreed=None)
            self.trace.append(f'appeal ({name}) succeeds: toll waived')
            return f'The {self.label.lower()} lets it go. No toll for you this time.'
        body['status'] = 'countered'
        self.trace.append(f'appeal ({name}) fails: the ask stands')
        return f'The {self.label.lower()} is not buying it. The ask stays at {ask} {unit}.'

    def _threaten(self, action, body):
        """A threat (steel on the table, "pay with this"): Intimidation against the flat 10 +
        Insight. Success waives the toll; failure is a refusal, with its consequence."""
        success, name = self._contest(action, 'intimidation')
        if success:
            body.update(status='waived', agreed=None)
            self.trace.append('threat succeeds: toll waived')
            return (f'The {self.label.lower()} weighs the threat and decides your passage is not worth the '
                    'trouble. No toll.')
        self.trace.append('threat fails: read as a refusal')
        text = self._refuse(action, body)
        return 'The threat does not land. ' + text[len('You refuse the toll. '):]

    def _refuse(self, action, body):
        body['refusals'] += 1
        ladder = self.toll['refusal']
        step = ladder[min(body['refusals'], len(ladder)) - 1]
        consequence = {'kind': step['kind'], 'text': step['text'], 'refusal': body['refusals']}
        body['consequences'] = (body['consequences'] + [consequence])[-8:]
        body['status'] = 'refused'
        self.trace.append(f'refusal {body["refusals"]}: {step["kind"]}')
        return f'You refuse the toll. {step["text"]}'

    def _defer(self, action, body):
        body['status'] = 'deferred'
        return ''

    def _play_for(self, action, body):
        # The caller decides whether the procedure can carry it (kit_agent).
        body['status'] = 'staked'
        return ''


def public_view(source, state):
    """What the player knows: open or settled tolls after they were raised (no floor)."""
    out = {}
    for key, (toll, body) in here(source, state).items():
        if body['status'] == 'not_raised':
            continue
        out[key] = {'status': body['status'], 'asked': body['asked'], 'unit': toll['unit'],
                    'per': toll.get('per'), **({'agreed': body['agreed']} if body['agreed'] else {}),
                    **({'paid': body['paid']} if body['paid'] else {}),
                    **({'offers': body['offers']} if body['offers'] else {}),
                    **({'consequence': body['consequences'][-1]['text']} if body['consequences'] else {})}
    return out


def amounts(view):
    """Coin amounts the toll state backs (for the numeric guard): the ask, the agreed and
    paid amounts, and the player's offers."""
    found = set()
    for body in (view or {}).values():
        for key in ('asked', 'agreed', 'paid'):
            if type(body.get(key)) is int and body[key] > 0:
                found.add(body[key])
        found.update(v for v in body.get('offers', ()) if type(v) is int)
    return found


def raised_events(source, state, spoken, turn_id):
    """When a turn's NPC line names the toll's amount with a toll word, the demand is on
    the table: record who made it."""
    events = []
    if not spoken:
        return events
    from . import kit_guards
    from .kit_agent import actor_speakers
    labels = {label: key for key, label in actor_speakers(source).items()}
    for key, (toll, body) in here(source, state).items():
        if body['status'] != 'not_raised':
            continue
        for line in spoken.splitlines():
            speaker, _, text = line.partition(':')
            if speaker.strip() not in labels:
                continue
            for sentence in kit_guards.sentences(text):
                said = {amount for amount, _ in kit_guards.spoken_amounts(sentence)}
                if toll['amount'] in said and npc_names_toll_words(sentence):
                    body.update(status='demanded', demanded_by=labels[speaker.strip()])
                    events.append(event(key, body, f'{speaker.strip()} raised the toll in turn {turn_id}.'))
                    break
            if body['status'] == 'demanded':
                break
    return events


def names_toll(source, key, spoken):
    """True when an NPC line in ``spoken`` names this toll's amount with a toll word (the
    same test that puts the demand on the table)."""
    from . import kit_guards
    from .kit_agent import actor_speakers
    toll = ((source or {}).get('tolls') or {}).get(key)
    if not toll or not spoken:
        return False
    labels = set(actor_speakers(source).values())
    for line in spoken.splitlines():
        speaker, _, text = line.partition(':')
        if speaker.strip() not in labels:
            continue
        for sentence in kit_guards.sentences(text):
            said = {amount for amount, _ in kit_guards.spoken_amounts(sentence)}
            if toll['amount'] in said and npc_names_toll_words(sentence):
                return True
    return False
