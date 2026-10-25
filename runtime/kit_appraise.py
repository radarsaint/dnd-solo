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
import sys
from pathlib import Path

from .goldscale import SOURCE
from .goldscale.clarification import (PendingAppraisal, PendingAppraisals, cancel_appraisal,
                                      continue_appraisal, start_appraisal)
from .goldscale.formatting import formula_text, help_text
from .goldscale.parser import parse_item_text
from .goldscale.pricing import calculate_price

KEY = (None, 0, 0)  # one table, one appraiser
DEFAULT_STATE = 'kit_appraise.json'


def _command(text):
    text = (text or '').strip()
    if text.lower().startswith('?gs'):
        return text
    if not text.lower().startswith(('buy ', 'sell ')):
        text = 'buy ' + text
    return '?gs ' + text


def _load(path):
    store = PendingAppraisals()
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        store._items[KEY] = PendingAppraisal(raw['raw'], raw['question_kind'], raw['created_at'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return store


def _save(path, store):
    pending = store._items.get(KEY)
    target = Path(path)
    if pending is None:
        if target.exists():
            target.unlink()
        return
    target.write_text(json.dumps({'raw': pending.raw, 'question_kind': pending.question_kind,
                                  'created_at': pending.created_at}), encoding='utf-8')


def appraise(text, state_path=None, now=None):
    """Goldscale's reply to one item description (may be a clarifying question)."""
    store = _load(state_path) if state_path else PendingAppraisals()
    reply = start_appraisal(_command(text), KEY, store, now=now)
    if state_path:
        _save(state_path, store)
    return reply


def answer(text, state_path, now=None):
    """Answer Goldscale's pending question. None when nothing is pending."""
    store = _load(state_path)
    reply = continue_appraisal(text, KEY, store, now=now)
    _save(state_path, store)
    return reply


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
        store = _load(args.state)
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
