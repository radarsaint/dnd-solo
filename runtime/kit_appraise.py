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
# "how much could I sell a healing potion for?", "price of a +1 longsword, please".
_FILLER = re.compile(r"^\s*(?:hey|hi|ok|okay|so|um|well|kit|goldscale)\b[,!]?\s*", re.I)
_LEAD = re.compile(
    r"^\s*(?:what(?:'s|s| is| are| does| do| would| will| might| should)?|how much(?: is| does| would| will| could| can|"
    r" should| might)?|can you|could you|would you|will you|please|pls|i'?d like to|i want to|i wanna|"
    r"i need to|let'?s|tell me|do you know|any idea|give me)\b[,]?\s*", re.I)
_SUBJ = re.compile(r"^\s*(?:i|we|you|me|us)\b\s*(?:(?:get|got|make|pay|be|charge)\b\s*)?(?:for\b\s*)?", re.I)
_VERB = re.compile(r"^\s*(?:price(?:\s+check)?|appraise|value|cost|quote|be|get|for)\b\s*", re.I)
_OF = re.compile(r"^\s*(?:the\s+)?(?:value|price|worth|cost|market price|going rate)\s+(?:of|for|on)\b\s*", re.I)
_ARTICLE = re.compile(r"^\s*(?:a|an|the|one|some|my|this|that)\b\s*", re.I)
_TAIL = re.compile(r"(?:\s*(?:'s|’s)?\s*(?:(?:be\s+)?worth|value|price|cost|go(?:es)? for|sell(?:s)? for|"
                   r"buy for|fetch|run(?: me)?|be|for|please|pls|at market|in gold|in gp)\b|\s*[?.!,]+)\s*$", re.I)
_SELL = re.compile(r"\b(?:sell|selling|sold|pawn|offload)\b(?!\s+for\s*[?.!]*\s*$)", re.I)
_MODE_WORD = re.compile(r"^\s*(?:\?gs\s+)?(?:buy(?:ing)?|sell(?:ing)?|pawn|offload|purchase)\b\s*", re.I)

# Well-known SRD items Kit can price without the player pasting the item text (SRD 5.1 values).
SRD_DEFAULTS = (
    ('potion of supreme healing', 'very rare potion', '10d4+20 healing'),
    ('potion of superior healing', 'rare potion', '8d4+8 healing'),
    ('potion of greater healing', 'uncommon potion', '4d4+4 healing'),
    ('potion of healing', 'common potion', '2d4+2 healing'),
)
_DICE = re.compile(r'\d+d\d+', re.I)
_RARITY = re.compile(r'\b(?:common|uncommon|rare|very rare|legendary|artifact)\b', re.I)


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


def strip_question(text):
    """The item, without the phrasing around it, keeping buy/sell intent:
    "what's a potion of healing worth?" -> "potion of healing"; "sell a potion of healing" -> "sell potion of healing"."""
    original = (text or '').strip()
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
    t = canonical_names(t.strip(" \t'\"")).strip()
    # A leading count ("3 healing potions") becomes Goldscale's own quantity signal.
    count = re.match(r'^(\d+)\s+(?=[a-z])', t, re.I)
    if count and int(count.group(1)) > 1:
        t = f'qty {count.group(1)} {t[count.end():]}'
    return mode + t if t else original


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
