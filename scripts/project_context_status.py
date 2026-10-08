#!/usr/bin/env python3
"""Deterministic status for the shared Project Gardener checkpoint.

This checker reports resumability boundaries. It does not decide what the
project means, rewrite the Project Brain, advance reconciliation cursors,
or accept semantic deltas.

Offline use (no network): pass repo SHAs and an issue fixture.
Online use resolves live main SHAs, issue #115, and the sibling control.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCHEMA = 'kit_project_context_status/v1'
DND_REPO = 'radarsaint/dnd-solo'
BFDM_REPO = 'radarsaint/bfdm-corpus'
CANONICAL_STATE = 'radarsaint/dnd-solo/coordination/context_state.json'
LOCAL_STATE = 'coordination/context_state.json'
BRAIN_PATH = 'docs/PROJECT_UNDERSTANDING.md'
INBOX_ISSUE = 115
PURPOSE = 'RESUMABILITY_CURSOR_NOT_KNOWLEDGE_STORE'
SHA_ADVANCE_MEANS = 'REVIEW_REQUIRED_NOT_AUTOMATIC_SEMANTIC_STALENESS'
PARTIAL_PASS_POLICY = 'STOP_AT_LAST_COMPLETELY_RECONCILED_BOUNDARY'
ADVANCE_ONLY_AFTER = (
    'RELEVANT_EVIDENCE_INSPECTED',
    'SEMANTIC_IMPACT_DECIDED',
    'REQUIRED_PROJECT_BRAIN_EDITS_DURABLY_WRITTEN',
    'UNRESOLVED_CONTRADICTIONS_EXPLICITLY_RECORDED',
)
STATE_SCHEMA = 'kit_project_gardener_state/v1'
CURSOR_FIELDS = (
    'reviewed_against_main',
    'context_review',
    'last_fully_reconciled_comment_id',
    'checkpoint',
    'semantic_brain',
)
REQUIRED_PATHS = (
    LOCAL_STATE,
    'coordination/control.json',
    'coordination/CONTEXT_CHANGELOG.md',
    'coordination/HANDOFF_TEMPLATE.md',
    'coordination/AGENTS_AND_TOOLS.md',
    'PROJECT_BOOTSTRAP.md',
    'PROJECT_CONTROL.md',
    'README.md',
    'START_HERE.md',
    '.github/pull_request_template.md',
    BRAIN_PATH,
)
CHANGELOG_BANNER = (
    'HISTORICAL',
    'superseded',
    'Do not maintain this file as current project memory.',
    'Do not require fresh collaborators to read it.',
)
CONTEXT_CLASSES = ('NONE', 'CONTROL', 'UNDERSTANDING', 'AGENTS_TOOLS', 'AUTHORITY')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DEFAULT_BFDM_FALLBACK_REF = 'docs/cross-repo-coordination-2026-10-07'
ROOT = Path(__file__).resolve().parents[1]


def norm_sha(value):
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if SHA_RE.fullmatch(text):
        return text
    return None


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rel_text(root, rel):
    return (Path(root) / rel).read_text(encoding='utf-8')


def slice_between(text, start, end):
    begin = text.find(start)
    if begin < 0:
        return None
    finish = text.find(end, begin + len(start))
    if finish < 0:
        return None
    return text[begin:finish]


def _worker_identity_gate_errors(text):
    """Structural worker-identity contract. Empty means the gate is present.

    Passing this check does not prove that a model understood its own role.
    """
    errors = []
    gate = text.find('### 0. Identify the worker')
    brain = text.find('### 1. Project Brain first')
    owning = text.find('### 3. Enter the owning task')
    route = text.find('### 4. Execute or route by worker capability')
    deeper = text.find('## Load deeper context only when relevant')
    if gate < 0 or brain < 0 or gate >= brain:
        errors.append('worker identity gate is not before Project Brain')
        return errors
    if not (owning >= 0 and route > owning and (deeper < 0 or route < deeper)):
        errors.append('execute-or-route step is not after the owning task and before deeper context')
    step0 = text[gate:brain].lower()
    if 'tool availability does not redefine worker identity' not in step0:
        errors.append('worker identity is not distinguished from tool availability')
    if not all(phrase in step0 for phrase in (
            'ordinary gpt', 'not grok build', 'not chatgpt work', 'not a shell')):
        errors.append('ordinary GPT is not explicitly distinguished from Grok Build, ChatGPT Work, and a shell executor')
    if not all(phrase in step0 for phrase in ('grok build', 'default', 'shell')):
        errors.append('Grok Build is not identified as the normal shell/repository executor')
    if 'brendon is not the routine' not in step0:
        errors.append('Brendon is not excluded as the routine repository executor')
    if any(state not in text[gate:brain] for state in (
            'PREPARED', 'RECORDED', 'DELIVERED', 'EXECUTED', 'VERIFIED', 'BLOCKED')):
        errors.append('action-state distinctions are missing from the worker identity gate')
    if 'weaker' not in step0 and 'weaken' not in step0:
        errors.append('local inability is not forbidden from weakening the acceptance condition')
    routed = text[route:deeper].lower() if route >= 0 and deeper > route else ''
    if 'grok build' not in routed or 'not weaken' not in routed:
        errors.append('repository execution is not routed to a capable executor instead of being skipped')
    return errors


def bootstrap_contract_errors(text):
    """Structural progressive-disclosure failures. Empty means the contract holds."""
    errors = []
    errors.extend(_worker_identity_gate_errors(text))
    brain = text.find('### 1. Project Brain first')
    authority = text.find('### 2. Reconcile with live authority')
    owning = text.find('### 3. Enter the owning task')
    deeper = text.find('## Load deeper context only when relevant')
    if -1 in (brain, authority, owning, deeper) or not (brain < authority < owning < deeper):
        errors.append('PROJECT_BOOTSTRAP.md required path is not Project Brain, then live authority, then owning task')
        return errors
    required = text[brain:deeper]
    step1, step2, step3 = text[brain:authority], text[authority:owning], text[owning:deeper]
    if BRAIN_PATH not in step1:
        errors.append('Project Brain step does not name docs/PROJECT_UNDERSTANDING.md')
    if 'PROJECT_CONTROL.md' not in step2 or 'dnd-solo/main' not in step2 or 'bfdm-corpus/main' not in step2:
        errors.append('live-authority step does not name both mains and PROJECT_CONTROL.md')
    if 'issue/PR' not in step3 or 'explicit user instruction' not in step3:
        errors.append('owning-task step does not route to an issue/PR or explicit user instruction')
    if 'CONTEXT_CHANGELOG.md' in required:
        errors.append('CONTEXT_CHANGELOG.md is required bootstrap reading')
    tail = text[deeper:]
    if 'coordination/AGENTS_AND_TOOLS.md' not in tail or 'when' not in tail.lower():
        errors.append('agent/tool map is not conditional deeper context')
    if 'coordination/context_state.json' not in tail or '#115' not in tail:
        errors.append('Gardener checkpoint and issue #115 are not discoverable for a Gardener pass')
    if 'historical provenance only' not in tail or 'CONTEXT_CHANGELOG.md' not in tail:
        errors.append('CONTEXT_CHANGELOG.md is not marked historical provenance only')
    if 'audits' not in tail.lower() or 'source' not in tail.lower():
        errors.append('historical/source evidence is not discoverable for causal work')
    runtime = slice_between(text, '### Runtime / implementation work', '## Before doing substantial work')
    if runtime is None or 'relevant' not in runtime.lower():
        errors.append('implementation architecture/code/tests are not limited to relevant work')
    elif 'Area 6c' not in runtime or 'universal runtime model' not in runtime:
        errors.append('bootstrap does not keep Area 6c from being treated as the Kit architecture')
    return errors


def cold_start_route(readme, start_here, bootstrap):
    """Structural discovery from the normal project/developer entry surfaces.

    Passing this route is not evidence that a model understands the project.
    """
    errors = []
    if 'Collaborators:' not in readme or 'PROJECT_BOOTSTRAP.md' not in readme:
        errors.append('README.md does not route collaborators to PROJECT_BOOTSTRAP.md')
    if 'PROJECT_BOOTSTRAP.md' not in start_here:
        errors.append('START_HERE.md does not route project work to PROJECT_BOOTSTRAP.md')
    play_marked = ('If you are Kit running a game' in start_here) and ('Development / project work' in start_here)
    if not play_marked:
        errors.append('START_HERE.md does not distinguish live play from project/development bootstrap')
    contract = bootstrap_contract_errors(bootstrap)
    errors.extend(contract)
    deeper = bootstrap.find('## Load deeper context only when relevant')
    tail = bootstrap[deeper:] if deeper >= 0 else ''
    required = ''
    if '## Required bootstrap path' in bootstrap and deeper >= 0:
        required = bootstrap[bootstrap.find('## Required bootstrap path'):deeper]
    runtime = slice_between(bootstrap, '### Runtime / implementation work', '## Before doing substantial work')
    discovered_task = 'issue/PR' in bootstrap and 'explicit user instruction' in bootstrap
    warning = 'universal runtime model' in bootstrap and 'Area 6c' in bootstrap
    return {
        'entry': 'README.md and START_HERE.md route project/development work to PROJECT_BOOTSTRAP.md',
        'live_play_distinguished': play_marked,
        'project_brain': BRAIN_PATH if BRAIN_PATH in bootstrap else None,
        'live_authority': [
            'radarsaint/dnd-solo/main',
            'radarsaint/bfdm-corpus/main',
            'PROJECT_CONTROL.md',
        ] if ('PROJECT_CONTROL.md' in bootstrap and 'dnd-solo/main' in bootstrap and 'bfdm-corpus/main' in bootstrap) else [],
        'owning_task': 'issue/PR or explicit user instruction' if discovered_task else None,
        'worker_identity_before_brain': (
            bootstrap.find('### 0. Identify the worker') >= 0
            and bootstrap.find('### 0. Identify the worker') < bootstrap.find('### 1. Project Brain first')),
        'deeper_context_conditional': deeper > bootstrap.find('### 3. Enter the owning task') >= 0,
        'agents_and_tools_conditional': 'coordination/AGENTS_AND_TOOLS.md' in tail and 'when' in tail.lower(),
        'gardener_checkpoint_discoverable': 'coordination/context_state.json' in tail and '#115' in tail,
        'semantic_inbox_discoverable': '#115' in tail,
        'historical_evidence_conditional': 'audits' in tail.lower() and 'source' in tail.lower(),
        'implementation_files_conditional': runtime is not None and 'relevant' in runtime.lower(),
        'changelog_required': 'CONTEXT_CHANGELOG.md' in required,
        'area_6c_treated_as_architecture': ('Area 6c' in bootstrap and not warning),
        'proves_gpt_understanding': False,
        'proves_worker_understanding': False,
        'errors': errors,
    }


def changelog_banner_errors(text):
    errors = []
    for snippet in CHANGELOG_BANNER:
        if snippet not in text:
            errors.append('CONTEXT_CHANGELOG.md is missing historical banner text: ' + snippet)
    return errors


def control_pointer_errors(data, *, sibling):
    """Return integrity messages for one repo control file."""
    errors = []
    if not isinstance(data, dict):
        return ['control file is not a JSON object']
    if 'context_changelog' in data:
        errors.append('active context_changelog pointer in coordination/control.json')
    for field in CURSOR_FIELDS:
        if field in data:
            errors.append('control file contains Gardener cursor field ' + field)
    inbox = data.get('context_inbox')
    if isinstance(inbox, dict) and 'last_fully_reconciled_comment_id' in inbox:
        errors.append('control file stores a semantic-inbox cursor')
    pointer = data.get('gardener_state')
    if sibling:
        if pointer != CANONICAL_STATE:
            if pointer == LOCAL_STATE or (isinstance(pointer, str) and pointer.endswith('context_state.json')
                                           and not pointer.startswith(DND_REPO + '/')):
                errors.append('BFDM sibling maintains a duplicate Gardener cursor')
            elif pointer is None:
                errors.append('BFDM control is missing the shared Gardener pointer')
            else:
                errors.append('BFDM control does not point at ' + CANONICAL_STATE)
        if data.get('gardener_state_role') != 'SINGLE_SHARED_RESUMABILITY_CURSOR_NOT_KNOWLEDGE_STORE':
            errors.append('BFDM gardener_state_role is not the shared resumability cursor')
    else:
        if pointer not in (LOCAL_STATE, CANONICAL_STATE):
            errors.append('dnd-solo control does not point at the shared Gardener checkpoint')
        if data.get('gardener_state_role') != 'SINGLE_SHARED_RESUMABILITY_CURSOR_NOT_KNOWLEDGE_STORE':
            errors.append('dnd-solo gardener_state_role is not the shared resumability cursor')
    return errors


def validate_string_list(name, value, errors):
    if not isinstance(value, list):
        errors.append(name + ' must be a list')
        return
    for index, item in enumerate(value):
        if isinstance(item, str) and item.strip():
            continue
        if isinstance(item, dict) and any(isinstance(item.get(key), str) and item[key].strip()
                                           for key in ('id', 'summary', 'reason')):
            continue
        errors.append('%s[%s] must be a non-empty string or an object with id, summary, or reason' % (name, index))


def validate_pass_object(name, value, errors, *, allow_null):
    if value is None and allow_null:
        return
    if not isinstance(value, dict):
        errors.append(name + ' must be an object')
        return
    for key in ('kind', 'scope'):
        if not isinstance(value.get(key), str) or not value[key].strip():
            errors.append('%s.%s must be a non-empty string' % (name, key))


def checkpoint_errors(state):
    errors = []
    if not isinstance(state, dict):
        return ['context_state.json is not a JSON object']
    if state.get('schema') != STATE_SCHEMA:
        errors.append('context_state.json schema is not ' + STATE_SCHEMA)
    if state.get('purpose') != PURPOSE:
        errors.append('purpose must identify resumability state, not a knowledge store')
    if state.get('canonical_location') != CANONICAL_STATE:
        errors.append('canonical Gardener location must be ' + CANONICAL_STATE)
    if type(state.get('state_revision')) is not int:
        errors.append('state_revision must be an integer')
    brain = state.get('semantic_brain')
    if not isinstance(brain, dict):
        errors.append('semantic_brain must be an object')
    else:
        if brain.get('repo') != DND_REPO:
            errors.append('semantic_brain.repo must be ' + DND_REPO)
        if brain.get('path') != BRAIN_PATH:
            errors.append('Project Brain path must be ' + BRAIN_PATH)
        if norm_sha(brain.get('last_semantic_commit')) is None:
            errors.append('last_semantic_commit is not a 40-character SHA')
    checkpoint = state.get('checkpoint')
    if not isinstance(checkpoint, dict):
        errors.append('checkpoint must be an object')
        return errors
    reviewed = checkpoint.get('reviewed_against_main')
    if not isinstance(reviewed, dict):
        errors.append('reviewed_against_main must be an object')
    else:
        for repo in (DND_REPO, BFDM_REPO):
            if norm_sha(reviewed.get(repo)) is None:
                errors.append('reviewed main SHA for %s is missing or malformed' % repo)
    inbox = checkpoint.get('context_inbox')
    if not isinstance(inbox, dict):
        errors.append('context_inbox must be an object')
    else:
        if inbox.get('repo') != DND_REPO or inbox.get('issue') != INBOX_ISSUE:
            errors.append('context inbox must be %s issue #%s' % (DND_REPO, INBOX_ISSUE))
        cursor = inbox.get('last_fully_reconciled_comment_id')
        if cursor is not None and type(cursor) is not int:
            errors.append('semantic inbox cursor must be an integer or null')
        if type(inbox.get('comment_count_at_checkpoint')) is not int:
            errors.append('comment_count_at_checkpoint must be an integer')
        if not isinstance(inbox.get('issue_state_at_checkpoint'), str):
            errors.append('issue_state_at_checkpoint must be a string')
    validate_pass_object('last_completed_pass', state.get('last_completed_pass'), errors, allow_null=True)
    active = state.get('active_pass', 'MISSING')
    if active == 'MISSING':
        errors.append('active_pass must be null or an object')
    else:
        validate_pass_object('active_pass', active, errors, allow_null=True)
    validate_string_list('unresolved', state.get('unresolved'), errors)
    validate_string_list('needs_review', state.get('needs_review'), errors)
    rules = state.get('checkpoint_rules')
    if not isinstance(rules, dict):
        errors.append('checkpoint_rules must be an object')
    else:
        if rules.get('sha_advance_means') != SHA_ADVANCE_MEANS:
            errors.append('sha_advance_means must be review-required, not automatic staleness')
        advance = rules.get('advance_only_after')
        if not isinstance(advance, list) or any(item not in advance for item in ADVANCE_ONLY_AFTER):
            errors.append('checkpoint advance rules are incomplete')
        if rules.get('partial_pass_policy') != PARTIAL_PASS_POLICY:
            errors.append('partial_pass_policy must stop at the last fully reconciled boundary')
    return errors


def commit_status(root, sha, *, resolve, online_lookup):
    if norm_sha(sha) is None:
        return 'MALFORMED'
    if not resolve:
        return 'WELL_FORMED'
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), 'cat-file', '-t', norm_sha(sha)],
            capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip() == 'commit':
        return 'RESOLVED'
    if online_lookup is not None:
        return 'RESOLVED' if online_lookup(norm_sha(sha)) else 'UNRESOLVED'
    return 'UNRESOLVED'


def inbox_assessment(recorded, issue):
    """Compare the recorded cursor to comment ids. Never infer acceptance."""
    cursor = None if not isinstance(recorded, dict) else recorded.get('last_fully_reconciled_comment_id')
    base = {
        'repo': DND_REPO,
        'issue': INBOX_ISSUE,
        'recorded_cursor': cursor,
        'pending_comment_ids': [],
        'acceptance_inferred': False,
        'auto_reconciled': False,
    }
    if issue is None:
        base.update({
            'status': 'UNAVAILABLE',
            'issue_state': None,
            'title': None,
            'comment_count': None,
            'note': 'Issue metadata unavailable. No semantic delta was marked reconciled.',
        })
        return base, []
    failures = []
    title = issue.get('title') if isinstance(issue, dict) else None
    state_name = issue.get('state') if isinstance(issue, dict) else None
    comments = issue.get('comments') if isinstance(issue, dict) else None
    base.update({'issue_state': state_name, 'title': title})
    if state_name != 'open':
        failures.append('issue #115 is not open')
    if not isinstance(title, str) or 'semantic delta inbox' not in title.lower():
        failures.append('issue #115 is not the semantic-delta inbox')
    if not isinstance(comments, list):
        failures.append('issue #115 comment metadata is not a list')
        base.update({'status': 'CURSOR_INTEGRITY_FAILURE', 'comment_count': None,
                     'note': 'Comment metadata is unusable. Pending deltas were not inferred.'})
        return base, failures
    ids = []
    for item in comments:
        if not isinstance(item, dict) or type(item.get('id')) is not int:
            failures.append('issue #115 comment is missing an integer id')
            continue
        ids.append(item['id'])
    ids = sorted(set(ids))
    base['comment_count'] = len(ids)
    if type(cursor) is not int and cursor is not None:
        failures.append('semantic inbox cursor must be an integer or null')
        base.update({'status': 'CURSOR_INTEGRITY_FAILURE',
                     'note': 'Cursor is unusable. Pending deltas were not inferred.'})
        return base, failures
    if cursor is None:
        base['pending_comment_ids'] = ids
        base['status'] = 'SEMANTIC_DELTAS_PENDING' if ids else 'CLEAR'
        base['note'] = ('No comments and a null cursor are a valid empty inbox.'
                        if not ids else
                        'Comments exist beyond the null cursor. They are pending, not reconciled.')
        return base, failures
    if cursor not in ids:
        failures.append('semantic inbox cursor does not identify a known comment')
        base.update({
            'status': 'CURSOR_INTEGRITY_FAILURE',
            'pending_comment_ids': [],
            'note': 'Cursor does not match a known comment. Pending deltas were not inferred.',
        })
        return base, failures
    pending = [item for item in ids if item > cursor]
    base['pending_comment_ids'] = pending
    base['status'] = 'SEMANTIC_DELTAS_PENDING' if pending else 'CLEAR'
    base['note'] = ('Comments newer than the recorded cursor are pending semantic deltas. '
                    'The checker did not accept, reject, or reconcile them.'
                    if pending else
                    'No comment id is newer than the recorded cursor. '
                    'The checker did not infer that any delta was accepted.')
    return base, failures


def sha_status(reviewed, live):
    if live is None:
        return 'UNAVAILABLE'
    live_norm = norm_sha(live)
    reviewed_norm = norm_sha(reviewed)
    if live_norm is None or reviewed_norm is None:
        return 'UNAVAILABLE'
    if live_norm == reviewed_norm:
        return 'REVIEWED_CURRENT'
    return 'SHA_ADVANCED_REVIEW_NEEDED'


def handoff_and_pr_errors(handoff, pull_template):
    errors = []
    if 'Context impact:' not in handoff:
        errors.append('handoff template does not require context impact')
    for name in CONTEXT_CLASSES:
        if name not in handoff:
            errors.append('handoff template is missing context class ' + name)
    if 'Project-context impact' not in pull_template:
        errors.append('PR template does not require context-impact classification')
    for name in CONTEXT_CLASSES:
        if name not in pull_template:
            errors.append('PR template is missing context class ' + name)
    return errors


def evaluate(root, *, live_shas, issue, bfdm_control, sibling_local_state_present=None,
             bfdm_unavailable=False, bfdm_source=None, resolve_commits=True,
             online_commit_lookup=None, state_override=None, dnd_control_override=None):
    """Return a status report. This function does not write repository files."""
    root = Path(root)
    failures = []
    notes = [
        'A SHA advance means semantic review is required. It does not mean the Project Brain is false or stale.',
        'No Gardener cursor was advanced.',
        'No semantic delta was accepted, rejected, or reconciled.',
        'No Project Brain content was rewritten.',
        'Structural success does not prove that a GPT understands the project.',
    ]
    state = state_override
    if state is None:
        try:
            state = load_json(root / LOCAL_STATE)
        except (OSError, json.JSONDecodeError) as exc:
            state = {}
            failures.append('coordination/context_state.json is unreadable: %s' % exc)
    dnd_control = dnd_control_override
    if dnd_control is None:
        try:
            dnd_control = load_json(root / 'coordination/control.json')
        except (OSError, json.JSONDecodeError) as exc:
            dnd_control = {}
            failures.append('coordination/control.json is unreadable: %s' % exc)
    failures.extend(checkpoint_errors(state))
    failures.extend(control_pointer_errors(dnd_control, sibling=False))
    for rel in REQUIRED_PATHS:
        if rel == BRAIN_PATH and isinstance(state, dict):
            brain = state.get('semantic_brain') if isinstance(state.get('semantic_brain'), dict) else {}
            rel = brain.get('path') or BRAIN_PATH
        if not (root / rel).is_file():
            if rel == BRAIN_PATH or (isinstance(state, dict) and isinstance(state.get('semantic_brain'), dict)
                                     and rel == state['semantic_brain'].get('path')):
                failures.append('Project Brain path is missing: ' + str(rel))
            else:
                failures.append('required continuity path is missing: ' + rel)
    try:
        readme = rel_text(root, 'README.md')
        start_here = rel_text(root, 'START_HERE.md')
        bootstrap = rel_text(root, 'PROJECT_BOOTSTRAP.md')
    except OSError as exc:
        readme, start_here, bootstrap = '', '', ''
        failures.append('bootstrap entry files are unreadable: %s' % exc)
    cold = cold_start_route(readme, start_here, bootstrap)
    for item in cold['errors']:
        if item not in failures:
            failures.append(item)
    try:
        failures.extend(changelog_banner_errors(rel_text(root, 'coordination/CONTEXT_CHANGELOG.md')))
    except OSError:
        failures.append('CONTEXT_CHANGELOG.md is missing; historical provenance must stay in place')
    try:
        failures.extend(handoff_and_pr_errors(
            rel_text(root, 'coordination/HANDOFF_TEMPLATE.md'),
            rel_text(root, '.github/pull_request_template.md')))
    except OSError as exc:
        failures.append('handoff or PR template is unreadable: %s' % exc)

    sibling_status = 'UNAVAILABLE'
    sibling_observed = None
    on_live_main = None
    if bfdm_unavailable or bfdm_control is None:
        sibling_status = 'UNAVAILABLE'
        notes.append('BFDM control was not available for pointer validation. No second cursor was created.')
    else:
        if isinstance(bfdm_control, (str, Path)):
            try:
                bfdm_control = load_json(bfdm_control)
            except (OSError, json.JSONDecodeError) as exc:
                bfdm_control = None
                failures.append('BFDM control is unreadable: %s' % exc)
        if isinstance(bfdm_control, dict):
            sibling_observed = bfdm_control.get('gardener_state')
            pointer_errors = control_pointer_errors(bfdm_control, sibling=True)
            duplicate = sibling_local_state_present is True or any('duplicate' in item.lower() for item in pointer_errors)
            if sibling_local_state_present is True and not any('duplicate' in item.lower() for item in pointer_errors):
                pointer_errors.append('BFDM sibling maintains a duplicate Gardener cursor')
                duplicate = True
            if duplicate:
                sibling_status = 'DUPLICATE_CURSOR'
            elif any('missing the shared Gardener pointer' in item for item in pointer_errors):
                sibling_status = 'MISSING_POINTER'
            elif pointer_errors:
                sibling_status = 'WRONG_POINTER'
            else:
                sibling_status = 'POINTS_AT_SHARED_CHECKPOINT'
            failures.extend(pointer_errors)
            if isinstance(bfdm_source, dict):
                on_live_main = bfdm_source.get('on_live_main')
                if on_live_main is False:
                    notes.append('Shared BFDM pointer was verified on ref %s, not on bfdm-corpus main. '
                                 'This is not a second cursor.' % bfdm_source.get('ref'))
        else:
            sibling_status = 'UNAVAILABLE'

    reviewed = {}
    if isinstance(state, dict) and isinstance(state.get('checkpoint'), dict):
        reviewed = state['checkpoint'].get('reviewed_against_main') or {}
    if not isinstance(live_shas, dict):
        live_shas = {}
    repos = {}
    for repo in (DND_REPO, BFDM_REPO):
        live = live_shas.get(repo, None)
        if isinstance(live, str) and live.strip().upper() == 'UNAVAILABLE':
            live = None
        repos[repo] = {
            'reviewed_main': norm_sha(reviewed.get(repo)) if isinstance(reviewed, dict) else None,
            'live_main': norm_sha(live) if live is not None else None,
            'status': sha_status(reviewed.get(repo) if isinstance(reviewed, dict) else None, live),
        }
    brain = state.get('semantic_brain') if isinstance(state, dict) else {}
    semantic_sha = brain.get('last_semantic_commit') if isinstance(brain, dict) else None
    commit = commit_status(root, semantic_sha, resolve=resolve_commits, online_lookup=online_commit_lookup)
    if commit == 'MALFORMED':
        if 'last_semantic_commit is not a 40-character SHA' not in failures:
            failures.append('last_semantic_commit is not a 40-character SHA')
    elif commit == 'UNRESOLVED':
        failures.append('last_semantic_commit is not resolvable')
    recorded_inbox = None
    if isinstance(state, dict) and isinstance(state.get('checkpoint'), dict):
        recorded_inbox = state['checkpoint'].get('context_inbox')
    inbox, inbox_failures = inbox_assessment(recorded_inbox, issue)
    failures.extend(inbox_failures)
    if (isinstance(recorded_inbox, dict) and type(recorded_inbox.get('comment_count_at_checkpoint')) is int
            and inbox.get('comment_count') is not None
            and recorded_inbox['comment_count_at_checkpoint'] != inbox['comment_count']):
        notes.append('comment_count_at_checkpoint is historical metadata and is not used to infer reconciliation.')

    review_signals = []
    if any(item['status'] == 'SHA_ADVANCED_REVIEW_NEEDED' for item in repos.values()):
        review_signals.append('SHA_ADVANCED_REVIEW_NEEDED')
    if inbox['status'] == 'SEMANTIC_DELTAS_PENDING':
        review_signals.append('SEMANTIC_DELTAS_PENDING')

    unique_failures = []
    for item in failures:
        if item not in unique_failures:
            unique_failures.append(item)
    authority_unavailable = any(item['status'] == 'UNAVAILABLE' for item in repos.values()) or inbox['status'] == 'UNAVAILABLE' or sibling_status == 'UNAVAILABLE'
    if unique_failures:
        classification = 'INTEGRITY_FAILURE'
    elif authority_unavailable:
        classification = 'AUTHORITY_UNAVAILABLE'
    elif 'SEMANTIC_DELTAS_PENDING' in review_signals:
        classification = 'SEMANTIC_DELTAS_PENDING'
    elif 'SHA_ADVANCED_REVIEW_NEEDED' in review_signals:
        classification = 'SHA_ADVANCED_REVIEW_NEEDED'
    else:
        classification = 'REVIEWED_CURRENT'

    active = state.get('active_pass') if isinstance(state, dict) else None
    schema_errors = checkpoint_errors(state)
    brain_on_disk = (root / BRAIN_PATH).is_file()
    brain_path_ok = (isinstance(state, dict) and isinstance(state.get('semantic_brain'), dict)
                     and state['semantic_brain'].get('path') == BRAIN_PATH)
    checkpoint_valid = (not schema_errors and commit in ('RESOLVED', 'WELL_FORMED')
                        and brain_on_disk and brain_path_ok)
    return {
        'schema': SCHEMA,
        'classification': classification,
        'local_plumbing_intact': not unique_failures,
        'proves_semantic_understanding': False,
        'project_brain_automatically_stale': False,
        'sha_advance_means': SHA_ADVANCE_MEANS,
        'repos': repos,
        'review_signals': review_signals,
        'semantic_inbox': inbox,
        'checkpoint': {
            'valid': checkpoint_valid,
            'canonical_location': state.get('canonical_location') if isinstance(state, dict) else None,
            'purpose': state.get('purpose') if isinstance(state, dict) else None,
            'active_pass': active if isinstance(state, dict) else None,
            'brain_path': BRAIN_PATH if (root / BRAIN_PATH).is_file() else None,
            'last_semantic_commit': {
                'value': norm_sha(semantic_sha),
                'status': commit,
            },
        },
        'sibling_pointer': {
            'status': sibling_status,
            'expected': CANONICAL_STATE,
            'observed': sibling_observed,
            'source': bfdm_source,
            'on_live_main': on_live_main,
            'local_state_file_present': sibling_local_state_present,
        },
        'structural_cold_start': {key: value for key, value in cold.items() if key != 'errors'},
        'integrity_failures': unique_failures,
        'notes': notes,
        'mutations': {
            'project_brain_rewritten': False,
            'gardener_cursor_advanced': False,
            'semantic_deltas_auto_reconciled': False,
            'issues_opened': False,
        },
    }


def format_human(report):
    lines = [
        'Project context status: %s' % report['classification'],
        'Plumbing intact: %s' % ('yes' if report['local_plumbing_intact'] else 'no'),
        'Proves semantic understanding: no',
        'Project Brain automatically stale: no',
        '',
    ]
    for repo, item in report['repos'].items():
        live = item['live_main'] if item['live_main'] else 'UNAVAILABLE'
        reviewed = item['reviewed_main'] if item['reviewed_main'] else 'MALFORMED'
        lines.append('Repo %s: %s' % (repo, item['status']))
        lines.append('  reviewed_main: %s' % reviewed)
        lines.append('  live_main: %s' % live)
    inbox = report['semantic_inbox']
    lines.extend([
        '',
        'Semantic inbox: %s' % inbox['status'],
        '  issue: %s#%s' % (inbox['repo'], inbox['issue']),
        '  recorded_cursor: %s' % ('null' if inbox['recorded_cursor'] is None else inbox['recorded_cursor']),
        '  comment_count: %s' % ('UNAVAILABLE' if inbox['comment_count'] is None else inbox['comment_count']),
        '  pending_comment_ids: %s' % inbox['pending_comment_ids'],
        '  acceptance_inferred: no',
    ])
    if inbox.get('note'):
        lines.append('  note: %s' % inbox['note'])
    commit = report['checkpoint']['last_semantic_commit']
    lines.extend([
        '',
        'Checkpoint: %s' % ('valid' if report['checkpoint']['valid'] else 'invalid'),
        '  purpose: %s' % report['checkpoint']['purpose'],
        '  brain: %s' % (report['checkpoint']['brain_path'] or 'MISSING'),
        '  last_semantic_commit: %s (%s)' % (commit['value'], commit['status']),
        '  active_pass: %s' % ('null' if report['checkpoint']['active_pass'] is None else 'present'),
        'Sibling pointer: %s' % report['sibling_pointer']['status'],
        '  expected: %s' % report['sibling_pointer']['expected'],
        '  observed: %s' % report['sibling_pointer']['observed'],
        '  on_live_main: %s' % ('yes' if report['sibling_pointer']['on_live_main'] is True
                               else 'no' if report['sibling_pointer']['on_live_main'] is False else 'unchecked'),
    ])
    source = report['sibling_pointer'].get('source') or {}
    if source.get('ref'):
        lines.append('  source: %s (%s)' % (source.get('ref'), source.get('kind')))
    lines.extend([
        '',
        'SHA advance means review required, not automatic semantic staleness.',
        'No Gardener cursor was advanced.',
        'No semantic delta was accepted, rejected, or reconciled.',
        'No Project Brain content was rewritten.',
    ])
    if report['review_signals']:
        lines.append('Review signals: %s' % ', '.join(report['review_signals']))
    if report['integrity_failures']:
        lines.append('Integrity failures:')
        for item in report['integrity_failures']:
            lines.append('  - %s' % item)
    return '\n'.join(lines) + '\n'


def format_json(report):
    return json.dumps(report, indent=2, sort_keys=True) + '\n'


def exit_code(report):
    if report['classification'] == 'INTEGRITY_FAILURE':
        return 2
    if report['classification'] == 'AUTHORITY_UNAVAILABLE':
        return 3
    return 0


class ApiResult(object):
    def __init__(self, ok, status, data):
        self.ok = ok
        self.status = status
        self.data = data


def _api_get_urllib(path):
    request = urllib.request.Request(
        'https://api.github.com/' + path,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'kit-project-context-status'})
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        request.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return ApiResult(True, response.status, json.loads(response.read().decode('utf-8')))
    except urllib.error.HTTPError as exc:
        payload = None
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except (OSError, json.JSONDecodeError, ValueError):
            payload = None
        return ApiResult(False, exc.code, payload)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ApiResult(False, None, None)


def _run_gh_api(path):
    return subprocess.run(['gh', 'api', path], capture_output=True, text=True, timeout=30, check=False)


def _gh_http_status(proc, data):
    if isinstance(data, dict):
        raw = data.get('status')
        if type(raw) is int:
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    match = re.search(r'HTTP (\d{3})', proc.stderr or '')
    if match:
        return int(match.group(1))
    return None


def _gh_auth_unavailable(proc, data, status):
    if status == 401:
        return True
    blob = '\n'.join([
        proc.stderr or '',
        proc.stdout or '',
        json.dumps(data) if isinstance(data, dict) else '',
    ]).lower()
    markers = (
        'gh auth login',
        'bad credentials',
        'requires authentication',
        'must authenticate',
        'populate the gh_token',
        'set the gh_token',
        'no oauth token',
    )
    return any(marker in blob for marker in markers)


def _gh_api_result(proc):
    """Return a kept GitHub CLI result, or None when urllib should be tried.

    A real HTTP response, including 404, is kept. Authentication failures and
    invocations that never produced an API response are not kept.
    """
    raw = (proc.stdout or '').strip()
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
    if proc.returncode == 0:
        return ApiResult(True, 200, data)
    status = _gh_http_status(proc, data)
    message = str(data.get('message', '')) if isinstance(data, dict) else ''
    not_found = status == 404 or message.lower() == 'not found' or 'not found' in (proc.stderr or '').lower()
    if not_found:
        return ApiResult(False, 404, data)
    if _gh_auth_unavailable(proc, data, status):
        return None
    if status is not None and isinstance(data, dict):
        return ApiResult(False, status, data)
    return None


def api_get(path, runner=None, transport=None):
    """GET a GitHub API path. 404 is a result; transport failure is not ok.

    ``gh api`` is used when it returns a usable response. If ``gh`` is missing,
    unauthenticated, or otherwise cannot produce one, the urllib path is used.
    """
    web = transport or _api_get_urllib
    if runner is None and not _which('gh'):
        return web(path)
    invoke = runner or _run_gh_api
    try:
        proc = invoke(path)
    except (OSError, subprocess.TimeoutExpired):
        return web(path)
    if not hasattr(proc, 'returncode'):
        return web(path)
    kept = _gh_api_result(proc)
    if kept is None:
        return web(path)
    return kept


def _which(name):
    for part in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(part) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def fetch_main_sha(repo):
    result = api_get('repos/%s/commits/main' % repo)
    if result.ok and isinstance(result.data, dict):
        return norm_sha(result.data.get('sha'))
    return None


def fetch_issue(repo, number):
    issue = api_get('repos/%s/issues/%s' % (repo, number))
    if not issue.ok or not isinstance(issue.data, dict):
        return None
    comments = []
    page = 1
    while page <= 20:
        batch = api_get('repos/%s/issues/%s/comments?per_page=100&page=%s' % (repo, number, page))
        if not batch.ok or not isinstance(batch.data, list):
            return None
        for item in batch.data:
            if isinstance(item, dict) and type(item.get('id')) is int:
                comments.append({'id': item['id'], 'created_at': item.get('created_at')})
        if len(batch.data) < 100:
            break
        page += 1
    return {'state': issue.data.get('state'), 'title': issue.data.get('title'), 'comments': comments}


def fetch_text_file(repo, path, ref):
    result = api_get('repos/%s/contents/%s?ref=%s' % (repo, path, ref))
    if result.status == 404:
        return False, None
    if not result.ok or not isinstance(result.data, dict) or 'content' not in result.data:
        return None, None
    try:
        text = base64.b64decode(result.data['content']).decode('utf-8')
    except (ValueError, UnicodeError):
        return None, None
    return True, text


def commit_exists_online(sha):
    result = api_get('repos/%s/commits/%s' % (DND_REPO, sha))
    return bool(result.ok and isinstance(result.data, dict) and norm_sha(result.data.get('sha')) == sha)


def resolve_sibling(explicit_control, explicit_unavailable, offline):
    if explicit_unavailable:
        return None, {'ref': None, 'on_live_main': None, 'kind': 'UNAVAILABLE'}, None
    if explicit_control:
        return explicit_control, {'ref': 'explicit-path', 'on_live_main': None, 'kind': 'EXPLICIT_PATH'}, None
    if offline:
        return None, {'ref': None, 'on_live_main': None, 'kind': 'UNAVAILABLE'}, None
    fallback = os.environ.get('BFDM_CONTROL_FALLBACK_REF', DEFAULT_BFDM_FALLBACK_REF)
    for ref, kind, on_main in (('main', 'MAIN', True), (fallback, 'FALLBACK_REF_NOT_MAIN', False)):
        if not ref:
            continue
        found, text = fetch_text_file(BFDM_REPO, 'coordination/control.json', ref)
        state_found, _state_text = fetch_text_file(BFDM_REPO, LOCAL_STATE, ref)
        if found is None or state_found is None:
            return None, {'ref': ref, 'on_live_main': None, 'kind': 'UNAVAILABLE'}, None
        if found:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return None, {'ref': ref, 'on_live_main': on_main, 'kind': kind}, None
            return data, {'ref': ref, 'on_live_main': on_main, 'kind': kind}, bool(state_found)
    return None, {'ref': None, 'on_live_main': None, 'kind': 'UNAVAILABLE'}, None


def build_report(args):
    offline = args.offline
    live = {}
    for repo, given in ((DND_REPO, args.dnd_sha), (BFDM_REPO, args.bfdm_sha)):
        if given is None:
            live[repo] = None if offline else fetch_main_sha(repo)
        elif given.strip().upper() == 'UNAVAILABLE':
            live[repo] = None
        else:
            live[repo] = given
    if args.issue_fixture:
        issue = load_json(args.issue_fixture)
    elif offline:
        issue = None
    else:
        issue = fetch_issue(DND_REPO, INBOX_ISSUE)
    bfdm_control, source, local_state = resolve_sibling(
        args.bfdm_control, args.bfdm_control_unavailable, offline or bool(args.bfdm_control))
    if args.sibling_local_state is not None:
        local_state = args.sibling_local_state
    lookup = None if args.skip_commit_resolve or offline else commit_exists_online
    return evaluate(
        args.root,
        live_shas=live,
        issue=issue,
        bfdm_control=bfdm_control,
        sibling_local_state_present=local_state,
        bfdm_unavailable=bfdm_control is None,
        bfdm_source=source,
        resolve_commits=not args.skip_commit_resolve,
        online_commit_lookup=lookup,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Report Project Gardener checkpoint status without mutating it.')
    parser.add_argument('--root', default=str(ROOT))
    parser.add_argument('--json', action='store_true', help='write machine-readable JSON to stdout')
    parser.add_argument('--human-out', help='also write the human report to this path')
    parser.add_argument('--offline', action='store_true', help='do not contact GitHub')
    parser.add_argument('--dnd-sha', help='injected radarsaint/dnd-solo main SHA, or UNAVAILABLE')
    parser.add_argument('--bfdm-sha', help='injected radarsaint/bfdm-corpus main SHA, or UNAVAILABLE')
    parser.add_argument('--bfdm-control', help='path to a BFDM coordination/control.json fixture or checkout')
    parser.add_argument('--bfdm-control-unavailable', action='store_true')
    parser.add_argument('--issue-fixture', help='path to issue #115 metadata JSON')
    parser.add_argument('--sibling-local-state', choices=('present', 'absent'))
    parser.add_argument('--skip-commit-resolve', action='store_true')
    args = parser.parse_args(argv)
    args.sibling_local_state = {'present': True, 'absent': False}.get(args.sibling_local_state)
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = build_report(args)
    human = format_human(report)
    if args.human_out:
        Path(args.human_out).write_text(human, encoding='utf-8')
    sys.stdout.write(format_json(report) if args.json else human)
    return exit_code(report)


if __name__ == '__main__':
    sys.exit(main())
