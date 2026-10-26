"""Kit's DM-assistant pricing tool: Goldscale's formula, as Goldscale answers it.

Build mode only (runtime/kit_campaign.py). Text in, Goldscale's reply out, so a host can
say "price a +1 longsword, uncommon weapon" and get the same answer the Goldscale bot gives
for "?gs buy +1 longsword uncommon weapon". When Goldscale asks a clarifying question, the
pending question is kept in a small JSON file so the next call can answer it across
separate Python runs (hosts like ChatGPT run one command at a time).

    python -m runtime.kit_appraise "buy wand of fireballs rare wand 8d6 aoe 7 charges"
    python -m runtime.kit_appraise --answer "2"
    python -m runtime.kit_appraise --formula

This is separate from the in-play shop precedence in runtime/kit_prices.py, which uses
runtime/pricing.py (the 2026-09-29 written formula) and never invents a price.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from .kit_lazyre import compile as lazy_compile
from .kit_text import leading_count, parse_quantity
from .goldscale import SOURCE
from .goldscale.clarification import (PendingAppraisal, PendingAppraisals, apply_answer, cancel_appraisal,
                                      classify_question, clarification_question, invalid_choice_message,
                                      start_appraisal, valid_closed_choice)
from .goldscale.formatting import format_missing, format_result
from .goldscale.pricing import has_impact
from .goldscale.formatting import formula_text, help_text
from .goldscale.parser import parse_item_text
from .goldscale.pricing import calculate_price

KEY = (None, 0, 0)  # one table, one appraiser
DEFAULT_STATE = 'kit_appraise.json'


# Phrasing around an item name, stripped generally (any item), in passes until nothing changes:
# "what's a potion of healing worth?", "sell a potion of healing", "what's the potion of healing's value?",
# "how much could I sell a healing potion for?", "price of a +1 longsword, please",
# "price check on a rope", "can I sell my torch?".
_FILLER = lazy_compile(r"^\s*(?:hey|hi|ok|okay|so|um|well|kit|goldscale)\b[,!]?\s*", re.I)
_AUX = r"(?:is|are|was|were|do|does|did|would|will|could|can|should|might)"
# A question word, then any auxiliary after it ("how much are 3 healing potions?", "what do two
# potions of greater healing go for?"), stripped generally, never as a one-off phrase.
_LEAD = lazy_compile(
    rf"^\s*(?:(?:what(?:'s|s|’s| is)?|how much(?:\s+for)?|how many(?: gold| gp| coins?)?|which)(?:\s+{_AUX})?|"
    r"can you|could you|would you|will you|may you|might you|"
    r"can i|could i|would i|will i|may i|might i|"
    r"please|pls|i'?d like to|i want to|i wanna|i need to|let'?s|tell me|do you know|any idea|give me)\b[,]?\s*", re.I)
_SUBJ = lazy_compile(r"^\s*(?:i|we|you|me|us)\b\s*(?:(?:get|got|make|pay|be|charge)\b\s*)?(?:for\b\s*)?", re.I)
_VERB = lazy_compile(
    r"^\s*(?:price(?:\s+check)?(?:\s+on)?|appraise|value|cost|quote|check(?:\s+on)?|be|get|for|on)\b\s*", re.I)
_OF = lazy_compile(r"^\s*(?:the\s+)?(?:value|price|worth|cost|market price|going rate)\s+(?:of|for|on)\b\s*", re.I)
_ARTICLE = lazy_compile(r"^\s*(?:a|an|the|one|some|my|this|that)\b\s*", re.I)
_TAIL = lazy_compile(r"(?:\s*(?:'s|’s)?\s*(?:(?:be\s+)?worth|value|price|cost|go(?:es)? for|sell(?:s)? for|"
                   r"buy for|fetch|run(?: me)?|be|for|please|pls|at market|in gold|in gp)\b|\s*[?.!,…]+)\s*$", re.I)
_SELL = lazy_compile(r"\b(?:sell|selling|sold|pawn|offload)\b(?!\s+for\s*[?.!]*\s*$)", re.I)
_MODE_WORD = lazy_compile(r"^\s*(?:\?gs\s+)?(?:buy(?:ing)?|sell(?:ing)?|pawn|offload|purchase)\b\s*", re.I)
# Question-word typos only. Item nouns are not corrected here.
_TYPOS = {
    'hw': 'how', 'muhc': 'much', 'mch': 'much', 'waht': 'what', 'whta': 'what', 'wht': 'what',
    'wats': 'what', 'hwat': 'what', 'whats': 'what', 'prise': 'price', 'prcie': 'price',
    'pirce': 'price', 'chekc': 'check', 'chek': 'check', 'chcek': 'check', 'wroth': 'worth',
    'wohrt': 'worth', 'worht': 'worth', 'seel': 'sell', 'slel': 'sell', 'howmuch': 'how much',
    'pricecheck': 'price check', 'cna': 'can',
}
_NEXT_ITEM = re.compile(
    r'^(?:a|an|the|my|your|\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
    r'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|dozen|pair|couple|brace)\b',
    re.I)
_NOT_NEXT = re.compile(
    r'^(?:\d+\s*(?:charges?|uses?|beads?)|\d+d\d+|\+[123]\b|'
    r'common|uncommon|rare|very|legendary|artifact|weapon|armor|armour|shield|potion|wand|'
    r'staff|cloak|ring|boots|scroll|consumable|utility|complex|minor|reusable|broad|healing|'
    r'damage|aoe|charged)\b',
    re.I)

# Well-known SRD items Kit can price without the player pasting the item text (SRD 5.1 values).
SRD_DEFAULTS = (
    ('potion of supreme healing', 'very rare potion', '10d4+20 healing'),
    ('potion of superior healing', 'rare potion', '8d4+8 healing'),
    ('potion of greater healing', 'uncommon potion', '4d4+4 healing'),
    ('potion of healing', 'common potion', '2d4+2 healing'),
)
_DICE = lazy_compile(r'\d+d\d+', re.I)
_RARITY = lazy_compile(r'\b(?:common|uncommon|rare|very rare|legendary|artifact)\b', re.I)


def _plural(word):
    return word[:-1] + 'ies' if word.endswith('y') else word + ('es' if word.endswith(('s', 'x', 'ch', 'sh')) else 's')


def name_variants(name):
    """Common spoken forms of an "<thing> of <quality>" item name: reversed and plural.
    'potion of greater healing' -> 'greater healing potion', 'potions of greater healing', ..."""
    out = {name}
    m = re.match(r'^(\w+) of (.+)$', name)
    if m:
        thing, quality = m.groups()
        many = _plural(thing)
        out |= {f'{quality} {thing}', f'{many} of {quality}', f'{quality} {many}'}
    else:
        *head, last = name.split()
        out.add(' '.join(head + [_plural(last)]))
    return sorted(out, key=len, reverse=True)


def canonical_names(text):
    """Rewrite any known item's variant spelling to its canonical name (word-bounded, case-insensitive)."""
    for name, _, _ in SRD_DEFAULTS:
        for variant in name_variants(name):
            if variant != name:
                text = re.sub(rf'\b{re.escape(variant)}\b', name, text, flags=re.I)
    return text


def _fix_typos(text):
    """Question-word typos only (prise -> price). Item nouns are left alone."""
    def repl(match):
        fixed = _TYPOS.get(match.group(0).casefold())
        return fixed if fixed else match.group(0)
    return re.sub(r"[A-Za-z']+", repl, text)


def _comma_bonus(text):
    """'longsword, +1' and '+1 longsword' share a bonus at the front.

    A trailing '+1' with no comma is left where the speaker put it, so
    'cloak of protection uncommon cloak +1' still prices as that line.
    """
    found = re.search(r',\s*\+\s*([123])\b', text, flags=re.I)
    if not found:
        return text
    rest = ' '.join((text[:found.start()] + ' ' + text[found.end():]).replace(',', ' ').split())
    if re.match(rf'\+{found.group(1)}\b', rest):
        return rest
    return f'+{found.group(1)} {rest}'.strip()


def _split_clauses(frame):
    """'a rope and two torches' is two items. '+1 longsword, uncommon weapon' is one."""
    clauses = []
    for chunk in re.split(r'\s+(?:and|&)\s+', frame):
        buf = []
        for piece in [part.strip() for part in chunk.split(',')]:
            if not piece:
                continue
            if buf and _NEXT_ITEM.match(piece) and not _NOT_NEXT.match(piece):
                clauses.append(', '.join(buf))
                buf = [piece]
            else:
                buf.append(piece)
        if buf:
            clauses.append(', '.join(buf))
    return clauses


def _frame(text):
    """(mode, item words) with the question shell removed. mode is 'sell ' or ''."""
    original = _fix_typos((text or '').strip()).replace('\u2019', "'")
    mode = 'sell ' if _SELL.search(original) else ('buy ' if re.match(r'^\s*(?:\?gs\s+)?buy\b', original, re.I) else '')
    t = original
    for _ in range(12):
        before = t
        for pattern in (_FILLER, _MODE_WORD, _LEAD, _SUBJ, _OF, _VERB, _ARTICLE):
            t = pattern.sub('', t, count=1)
        t = _TAIL.sub('', t)
        t = re.sub(r"\s+(?:i|we)\s+(?:sell|buy|get|pay)\s*$", '', t, flags=re.I)
        t = re.sub(r"\b(?:sell(?:ing)?|buy(?:ing)?)\s+(?=\S)", '', t, count=1, flags=re.I) if t is before else t
        if t == before:
            break
    return mode, t.strip(" \t'\"")


def _one_clause(part):
    part = _comma_bonus(part.strip(" \t'\""))
    for _ in range(4):
        nxt = _ARTICLE.sub('', part, count=1).strip()
        if nxt == part:
            break
        part = nxt
    part = canonical_names(part).strip()
    parsed = parse_quantity(part)
    if parsed:
        count, rest = parsed
        part = f'qty {count} {rest}' if count > 1 else rest
    return part.strip(" \t'\"?.!,…")


def strip_question(text):
    """The item, without the phrasing around it, keeping buy/sell intent.

    "what's a potion of healing worth?" -> "potion of healing"
    "sell a potion of healing" -> "sell potion of healing"
    "price a rope and two torches" -> "rope and qty 2 torches"
    "can I sell my torch?" -> "sell torch"
    """
    original = (text or '').strip()
    mode, frame = _frame(original)
    if not frame:
        return original
    parts = [part for part in (_one_clause(piece) for piece in _split_clauses(frame)) if part]
    if not parts:
        return original
    return (mode + ' and '.join(parts)).strip()


_CP = {'cp': 1, 'sp': 10, 'gp': 100}
_SKIP_TOKENS = frozenset(
    'a an the my your our his her their some of please pls hey hi ok okay'.split())
_MAGIC_MARK = lazy_compile(
    r"(?<![0-9d])\+[123]\b|\b(?:common|uncommon|rare|very rare|legendary|artifact|minor|reusable|broad)\b|\d+d\d+",
    re.I)
_CATALOG = None


def _unknown(mode, quantity=1):
    return {'item': 'unknown item', 'quantity': quantity, 'price': None, 'unit': None,
            'source': 'unknown', 'mode': 'sell' if (mode or '').startswith('sell') else 'buy'}


# Brendon's ruling: a merchant buys mundane gear at half the listed SRD price,
# the same 50% Goldscale applies when a magic item is sold.
SELL_SHARE = 2
# More listed entries than this is a vague word ("armor"), not a choice to offer.
_MAX_CHOICES = 4


def _ambiguous(mode, quantity, entries):
    """A name that fits a few listed entries: ask which, with each one's price. Never pick."""
    selling = (mode or '').startswith('sell')
    choices = []
    for entry in entries:
        amount, unit = _bundle_price(entry, quantity, selling)
        choices.append({'item': entry['name'], 'price': amount, 'unit': unit})
    return {'item': 'ambiguous item', 'quantity': quantity, 'price': None, 'unit': None,
            'source': 'ambiguous', 'mode': 'sell' if selling else 'buy', 'choices': choices}


def _entry_tokens(name):
    bare = re.sub(r'\([^)]*\)', ' ', (name or '').casefold())
    head, _, qual = bare.partition(',')
    return re.findall(r'[a-z0-9]+', head), re.findall(r'[a-z0-9]+', qual)


def _catalog():
    """SRD rows as (entry, head tokens, qualifier tokens) and the token set. Loaded once."""
    global _CATALOG
    if _CATALOG is None:
        from . import kit_prices
        rows = []
        words = set()
        for entry in kit_prices.srd_entries():
            head, qual = _entry_tokens(entry['name'])
            rows.append((entry, head, qual))
            words.update(head)
            words.update(qual)
        _CATALOG = (rows, words)
    return _CATALOG


def _one_edit(left, right):
    """True when left and right differ by one insertion, deletion, substitution, or transposition."""
    if left == right:
        return False
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        diffs = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
        if len(diffs) == 1:
            return True
        return (len(diffs) == 2 and diffs[1] == diffs[0] + 1
                and left[diffs[0]] == right[diffs[1]] and left[diffs[1]] == right[diffs[0]])
    if len(left) > len(right):
        left, right = right, left
    skip = 0
    i = 0
    for char in right:
        if i < len(left) and left[i] == char:
            i += 1
        else:
            skip += 1
            if skip > 1:
                return False
    return True


def _fold_token(token, words):
    """Plural, or one unique misspelling, of a token that is actually in the price list.

    Two catalog words one edit away is not a match: that would be a guess.
    """
    if token in words:
        return token
    folded = []
    if len(token) > 3 and token.endswith('ies'):
        folded.append(token[:-3] + 'y')
    if len(token) > 4 and token.endswith('es'):
        folded.append(token[:-2])
    if len(token) > 3 and token.endswith('s'):
        folded.append(token[:-1])
    if token.endswith('y') and len(token) > 3:
        folded.append(token[:-1] + 'ies')
    folded.extend((token + 's', token + 'es'))
    exact = list(dict.fromkeys(cand for cand in folded if cand in words))
    if len(exact) == 1:
        return exact[0]
    if len(token) >= 4:
        near = [word for word in words if len(word) >= 4 and _one_edit(token, word)]
        if len(near) == 1:
            return near[0]
    return token


def _query_tokens(name, words):
    tokens = []
    for token in re.findall(r'[a-z0-9]+', (name or '').casefold()):
        if token in _SKIP_TOKENS or token.isdigit():
            continue
        tokens.append(_fold_token(token, words))
    return tokens


def match_catalog(name):
    """The one SRD entry whose name is exactly these words, or None.

    "torches" is Torch. "hempen rope" is the hempen rope. "rope" is both ropes,
    so it is None: the caller says unknown item instead of picking one.
    A word that is not in the list, and not one edit from exactly one listed word,
    does not match a neighbor.
    """
    rows, words = _catalog()
    wanted = _query_tokens(name, words)
    if not wanted:
        return None
    wanted_set = set(wanted)
    hits = [entry for entry, head, qual in rows if head and set(head + qual) == wanted_set]
    if len(hits) == 1:
        return hits[0]
    return None


def catalog_choices(name):
    """Listed entries this name could be, when it is not exactly one of them.

    "rope" is both ropes and "lantern" both lanterns: every head word of the
    entry was said and nothing else was. A word not in the list matches nothing.
    """
    rows, words = _catalog()
    wanted = _query_tokens(name, words)
    if not wanted:
        return []
    wanted_set = set(wanted)
    hits = [entry for entry, head, qual in rows
            if head and set(head) <= wanted_set <= set(head + qual)]
    return hits if 1 < len(hits) <= _MAX_CHOICES else []


def _bundle_price(entry, quantity, selling=False):
    """Listed price times quantity, in the largest whole coin the rate divides into.

    Arrow is 1 gp per 20, so one arrow is 5 cp and a dozen is 6 sp. A rate that
    does not divide into whole coins returns (None, None) rather than a rounded guess.
    Selling is half the bundle, rounded down to a whole copper (a merchant does not
    pay half a copper): one torch sells for 0 cp, two for 1 cp.
    """
    per = entry.get('per') or 1
    copper = entry['amount'] * _CP[entry['unit']] * quantity
    if copper % per:
        return None, None
    copper //= per
    if selling:
        copper //= SELL_SHARE
    if copper == 0:
        return 0, 'cp'
    if copper % 100 == 0:
        return copper // 100, 'gp'
    if copper % 10 == 0:
        return copper // 10, 'sp'
    return copper, 'cp'


def _looks_magic(name):
    low = (name or '').casefold()
    if any(known in low for known, _, _ in SRD_DEFAULTS):
        return True
    return bool(_MAGIC_MARK.search(name or ''))


def _from_goldscale(line, quantity):
    try:
        got = price(line)
    except ValueError:
        data = parse_item_text(_command(line))
        return {'item': data.item_name or 'unknown item', 'quantity': data.quantity or quantity,
                'price': None, 'unit': 'gp', 'source': 'goldscale', 'mode': data.mode}
    total = got['transaction_total'] if got['transaction_total'] is not None else got['final_price']
    return {'item': got['item'], 'quantity': got['quantity'] or 1, 'price': total,
            'unit': got['unit'], 'source': 'goldscale', 'mode': got['mode']}


def _quote_clause(mode, cleaned):
    parsed = parse_quantity(cleaned)
    if parsed and parsed[0] > 1:
        quantity, name = parsed
    else:
        quantity, name = 1, cleaned
    name = name.strip()
    if _looks_magic(name):
        prefix = mode
        counted = f'qty {quantity} {name}' if quantity > 1 else name
        return _from_goldscale(f'{prefix}{counted}'.strip(), quantity)
    hit = match_catalog(name)
    if hit is None:
        choices = catalog_choices(name)
        return _ambiguous(mode, quantity, choices) if choices else _unknown(mode, quantity)
    amount, unit = _bundle_price(hit, quantity, mode.startswith('sell'))
    return {'item': hit['name'], 'quantity': quantity, 'price': amount, 'unit': unit,
            'source': 'srd', 'mode': 'sell' if mode.startswith('sell') else 'buy'}


def read_items(text):
    """One shop or appraisal line, as a list of item/quantity/price rows.

    A name that is not one entry in the price data is "unknown item". Goldscale's
    final price is used when the line is a magic item it can already price, so a
    rephrase does not change that price. SRD gear uses the listed rate.
    """
    mode, frame = _frame(text)
    if not frame:
        return [_unknown(mode)]
    rows = []
    for piece in _split_clauses(frame):
        cleaned = _one_clause(piece)
        rows.append(_quote_clause(mode, cleaned) if cleaned else _unknown(mode))
    return rows or [_unknown(mode)]


def _spoken_name(name):
    """'Rope, hempen (50 feet)' -> 'hempen rope (50 feet)'."""
    size = re.search(r'\s*(\([^)]*\))\s*$', name)
    bare = name[:size.start()] if size else name
    head, _, qual = bare.partition(',')
    words = f'{qual.strip()} {head.strip()}'.strip() if qual else head.strip()
    words = words.lower()
    return f'{words} {size.group(1)}' if size else words


def _coins(amount, unit):
    """75 sp -> '7 gp 5 sp'. Zero copper is 'less than 1 cp'."""
    if amount is None:
        return 'no listed price'
    copper = amount * _CP[unit]
    if copper == 0:
        return 'less than 1 cp'
    parts = []
    for name, size in (('gp', 100), ('sp', 10), ('cp', 1)):
        if copper >= size:
            parts.append(f'{copper // size} {name}')
            copper %= size
    return ' '.join(parts)


def mundane_reply(text):
    """Plain-gear answer for a line with no magic item in it, or None for Goldscale.

    Goldscale cannot price a torch or a rope; it asks for an item description,
    which dead-ends a player who only wanted the shop price.
    """
    rows = read_items(text)
    # An unlisted name may be a homebrew magic item ("potion of vigor"): Goldscale
    # asks for its description, as it did before. Only listed or ambiguous gear is answered here.
    if not rows or any(row['source'] not in ('srd', 'ambiguous') for row in rows):
        return None
    lines = []
    for row in rows:
        count = f"{row['quantity']} x " if row['quantity'] > 1 else ''
        if row['source'] == 'srd':
            verb = 'sells for' if row['mode'] == 'sell' else 'costs'
            lines.append(f"{count}{_spoken_name(row['item'])} {verb} {_coins(row['price'], row['unit'])}.")
        elif row['source'] == 'ambiguous':
            options = [f"{_spoken_name(c['item'])} ({_coins(c['price'], c['unit'])})" for c in row['choices']]
            which = ', '.join(options[:-1]) + ' or ' + options[-1]
            lines.append(f"Which one: {which}?")
    if any(row['mode'] == 'sell' and row['source'] == 'srd' for row in rows):
        lines.append('Selling is half the listed price.')
    return '\n'.join(lines)


def srd_defaults(text):
    """Fill in rarity/type and dice for a well-known SRD item the player only named."""
    low = text.casefold()
    for name, rarity_type, dice in SRD_DEFAULTS:
        if name in low:
            extra = []
            if not _RARITY.search(text):
                extra.append(rarity_type)
            if not _DICE.search(text):
                extra.append(dice)
            return f"{text} {' '.join(extra)}" if extra else text
    return text


def _command(text):
    text = (text or '').strip()
    if text.lower().startswith('?gs'):
        return text
    text = srd_defaults(strip_question(text))
    if not text.lower().startswith(('buy ', 'sell ')):
        text = 'buy ' + text
    return '?gs ' + text


def _load(path):
    """(store, answers): the pending question plus every answer given so far."""
    store = PendingAppraisals()
    answers = []
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        store._items[KEY] = PendingAppraisal(raw['raw'], raw['question_kind'], raw['created_at'])
        answers = [tuple(a) for a in raw.get('answers', [])]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return store, answers


def _save(path, store, answers=()):
    pending = store._items.get(KEY)
    target = Path(path)
    if pending is None:
        if target.exists():
            target.unlink()
        return
    target.write_text(json.dumps({'raw': pending.raw, 'question_kind': pending.question_kind,
                                  'created_at': pending.created_at,
                                  'answers': [list(a) for a in answers]}), encoding='utf-8')


def _data(raw, answers):
    """Re-read the item and apply every clarification so far, so no answer is lost."""
    data = parse_item_text(raw)
    for kind, reply in answers:
        data = apply_answer(data, PendingAppraisal(raw, kind, 0.0), reply)
    return data


def appraise(text, state_path=None, now=None):
    """Goldscale's reply to one item description (may be a clarifying question)."""
    store = PendingAppraisals()
    plain = None if (text or '').strip().lower().startswith('?gs') else mundane_reply(text)
    if plain is not None:
        if state_path:
            _save(state_path, store, [])
        return plain
    reply = start_appraisal(_command(text), KEY, store, now=now)
    if state_path:
        _save(state_path, store, [])
    return reply


def answer(text, state_path, now=None):
    """Answer Goldscale's pending question. None when nothing is pending.

    Answers accumulate in the state file across separate runs: description text is merged
    into the item text, closed choices are replayed on every step, so an item that needs
    two or more clarifications moves forward instead of re-asking the first question.
    """
    store, answers = _load(state_path)
    pending = store.get(KEY, now=now)
    if not pending:
        _save(state_path, store)
        return None
    text = (text or '').strip()
    raw, kind = pending.raw, pending.question_kind
    if kind == 'description':
        extra = re.sub(r'^\?gs\s+(buy|sell)\s+', '', text, flags=re.I)
        raw = f'{raw}, {extra}' if extra else raw
    else:
        if not valid_closed_choice(pending, text):
            return invalid_choice_message(kind)
        answers = answers + [(kind, text)]
    data = _data(raw, answers)
    try:
        result = format_result(calculate_price(data))
        store.clear(KEY)
        _save(state_path, store)
        return result
    except ValueError as error:
        if str(error) != 'missing fields':
            raise
    if kind == 'spell_description' and not has_impact(data):
        nxt, lead = 'utility', "I found spell text, but no damage or healing dice.\n"
    else:
        nxt, lead = classify_question(data, raw), ''
    if nxt:
        store.set(KEY, raw, nxt, now=now)
        _save(state_path, store, answers)
        return lead + clarification_question(data, nxt)
    # Nothing closed to ask: keep the item open so the next --answer adds the missing text.
    store.set(KEY, raw, 'description', now=now)
    _save(state_path, store, answers)
    return format_missing(data)


def price(text):
    """Structured result for a complete description (raises ValueError if fields are missing)."""
    result = calculate_price(parse_item_text(_command(text)))
    return {'item': result.item_name, 'impact': result.impact, 'impact_math': result.impact_math,
            'rarity': result.rarity, 'category': result.category, 'gpi': result.gpi,
            'list_price': result.list_price, 'final_price': result.final_price, 'mode': result.mode,
            'quantity': result.quantity, 'transaction_total': result.transaction_total,
            'unit': 'gp', 'basis': SOURCE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('text', nargs='?', help='item description, e.g. "+1 longsword uncommon weapon"')
    parser.add_argument('--answer', help="answer Goldscale's pending clarifying question")
    parser.add_argument('--cancel', action='store_true', help='drop a pending question')
    parser.add_argument('--formula', action='store_true', help="print Goldscale's formula")
    parser.add_argument('--state', default=DEFAULT_STATE, help='pending-question file')
    args = parser.parse_args(argv)
    if args.formula:
        out = formula_text()
    elif args.cancel:
        store, _ = _load(args.state)
        out = cancel_appraisal(KEY, store)
        _save(args.state, store)
    elif args.answer is not None:
        out = answer(args.answer, args.state) or 'There is no pending appraisal to answer.'
    elif args.text and args.text.strip().lower() != 'help':
        out = appraise(args.text, args.state)
    else:
        out = help_text()
    sys.stdout.write(out + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
