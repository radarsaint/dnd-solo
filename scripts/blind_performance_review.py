"""Make a blind, player-facing comparison packet from two public continuations.

Input is deliberately restricted to public text. Keep private traces in a
separate file, and inspect each candidate for source/knowledge violations
before inviting a player to review it.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value


def load_experiment(path):
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'experiment', 'pairs'}:
        raise ValueError('Input must contain only experiment and pairs')
    _nonempty(data['experiment'], 'experiment')
    pairs = data['pairs']
    if not isinstance(pairs, list) or not pairs:
        raise ValueError('pairs must be a nonempty list')
    case_ids = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {
                'case_id', 'public_context', 'player_input', 'candidates'}:
            raise ValueError('Each pair must have only case_id, public_context, player_input, candidates')
        case_id = _nonempty(pair['case_id'], 'case_id')
        if case_id in case_ids:
            raise ValueError(f'Duplicate case_id: {case_id}')
        case_ids.add(case_id)
        _nonempty(pair['public_context'], 'public_context')
        _nonempty(pair['player_input'], 'player_input')
        candidates = pair['candidates']
        if not isinstance(candidates, list) or len(candidates) != 2:
            raise ValueError(f'{case_id} needs exactly two candidates')
        variant_ids = set()
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {'variant_id', 'spoken'}:
                raise ValueError('Candidate may contain only variant_id and spoken')
            variant_id = _nonempty(candidate['variant_id'], 'variant_id')
            if variant_id in variant_ids:
                raise ValueError(f'Duplicate variant_id in {case_id}')
            variant_ids.add(variant_id)
            _nonempty(candidate['spoken'], 'spoken')
    return data, hashlib.sha256(raw).hexdigest()


def _quoted(text):
    return '\n'.join('> ' + line for line in text.strip().splitlines())


def render_review(data, digest, seed):
    """Return public Markdown and a separate private answer key."""
    rng = random.Random(seed)
    lines = [
        '# Blind Kit Performance Review', '',
        f'Experiment: {data["experiment"]}', '',
        'Read only the public context and both continuations. Choose which DM you would keep playing with.',
        'Name the exact line or behavior that made the difference. Do not score by length alone.', '',
    ]
    key = {'experiment': data['experiment'], 'input_sha256': digest,
           'seed': seed, 'mapping': []}
    for pair in data['pairs']:
        candidates = list(pair['candidates'])
        rng.shuffle(candidates)
        lines += [f'## {pair["case_id"]}', '', '**What the player has seen**', '',
                  _quoted(pair['public_context']), '', '**Player says or does**', '',
                  _quoted(pair['player_input']), '']
        mapping = {'case_id': pair['case_id']}
        for label, candidate in zip(('A', 'B'), candidates):
            lines += [f'### Continuation {label}', '', _quoted(candidate['spoken']), '']
            mapping[label] = candidate['variant_id']
        lines += [
            '**Review**', '',
            '- Which continuation would you choose to play next, and why? Quote the decisive moment.',
            '- What could your character do next?',
            '- For each continuation, score 0–3: response to bid; embodied actor; Kit’s judgment; playable invitation; earned scale.',
            '- Note any source/rules error, private reveal, invented player action, or unsupported world change.', '',
        ]
        key['mapping'].append(mapping)
    return '\n'.join(lines), key


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='JSON with only public review material')
    parser.add_argument('--review', type=Path, required=True, help='New Markdown packet for reviewers')
    parser.add_argument('--key', type=Path, required=True, help='New private answer-key JSON')
    parser.add_argument('--seed', type=int, required=True, help='Recorded randomization seed')
    args = parser.parse_args(argv)
    if len({args.input.resolve(), args.review.resolve(), args.key.resolve()}) != 3:
        parser.error('Input, review, and key paths must be distinct')
    if args.review.exists() or args.key.exists():
        parser.error('Refusing to overwrite a review or answer key')
    try:
        data, digest = load_experiment(args.input)
        review, key = render_review(data, digest, args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.review.write_text(review + '\n', encoding='utf-8')
    args.key.write_text(json.dumps(key, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
