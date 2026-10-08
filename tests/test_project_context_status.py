"""Offline fixtures for the Project Gardener status checker.

These tests prove structural routing and cursor mechanics only.
They do not prove that a model understands the project, and they do not
treat Area 6c or any campaign room as the architecture of Kit.
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'project_context'
SPEC = importlib.util.spec_from_file_location(
    'project_context_status', ROOT / 'scripts' / 'project_context_status.py')
STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS)

DND = STATUS.DND_REPO
BFDM = STATUS.BFDM_REPO
STATE = json.loads((ROOT / 'coordination' / 'context_state.json').read_text(encoding='utf-8'))
DND_SHA = STATE['checkpoint']['reviewed_against_main'][DND]
BFDM_SHA = STATE['checkpoint']['reviewed_against_main'][BFDM]
CLEAR = json.loads((FIXTURES / 'issue_clear.json').read_text(encoding='utf-8'))
PENDING = json.loads((FIXTURES / 'issue_pending.json').read_text(encoding='utf-8'))
POINTER = json.loads((FIXTURES / 'bfdm_control_shared_pointer.json').read_text(encoding='utf-8'))
DUPLICATE = json.loads((FIXTURES / 'bfdm_control_duplicate_cursor.json').read_text(encoding='utf-8'))


def bump(sha):
    return sha[:-1] + ('0' if sha[-1] != '0' else '1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProjectContextStatusTests(unittest.TestCase):
    def evaluate(self, **overrides):
        args = {
            'live_shas': {DND: DND_SHA, BFDM: BFDM_SHA},
            'issue': CLEAR,
            'bfdm_control': POINTER,
            'sibling_local_state_present': False,
            'resolve_commits': True,
        }
        args.update(overrides)
        return STATUS.evaluate(ROOT, **args)

    def test_valid_current_checkpoint(self):
        before_state = digest(ROOT / 'coordination' / 'context_state.json')
        before_brain = digest(ROOT / 'docs' / 'PROJECT_UNDERSTANDING.md')
        report = self.evaluate()
        self.assertEqual(report['classification'], 'REVIEWED_CURRENT')
        self.assertEqual(report['repos'][DND]['status'], 'REVIEWED_CURRENT')
        self.assertEqual(report['repos'][BFDM]['status'], 'REVIEWED_CURRENT')
        self.assertTrue(report['checkpoint']['valid'])
        self.assertEqual(report['checkpoint']['purpose'], STATUS.PURPOSE)
        self.assertEqual(report['checkpoint']['last_semantic_commit']['status'], 'RESOLVED')
        self.assertIsNone(report['checkpoint']['active_pass'])
        self.assertEqual(report['sibling_pointer']['status'], 'POINTS_AT_SHARED_CHECKPOINT')
        self.assertEqual(report['semantic_inbox']['status'], 'CLEAR')
        self.assertFalse(report['project_brain_automatically_stale'])
        self.assertFalse(report['proves_semantic_understanding'])
        self.assertEqual(report['mutations']['gardener_cursor_advanced'], False)
        self.assertEqual(report['mutations']['project_brain_rewritten'], False)
        self.assertEqual(before_state, digest(ROOT / 'coordination' / 'context_state.json'))
        self.assertEqual(before_brain, digest(ROOT / 'docs' / 'PROJECT_UNDERSTANDING.md'))
        human = STATUS.format_human(report)
        self.assertIn('Project context status: REVIEWED_CURRENT', human)
        self.assertIn('does not mean the Project Brain is false or stale', '\n'.join(report['notes']))
        self.assertIn('No Gardener cursor was advanced.', human)

    def test_dnd_solo_sha_advanced(self):
        report = self.evaluate(live_shas={DND: bump(DND_SHA), BFDM: BFDM_SHA})
        self.assertEqual(report['repos'][DND]['status'], 'SHA_ADVANCED_REVIEW_NEEDED')
        self.assertEqual(report['repos'][BFDM]['status'], 'REVIEWED_CURRENT')
        self.assertEqual(report['classification'], 'SHA_ADVANCED_REVIEW_NEEDED')
        self.assertIn('SHA_ADVANCED_REVIEW_NEEDED', report['review_signals'])
        self.assertFalse(report['project_brain_automatically_stale'])
        self.assertFalse(report['mutations']['gardener_cursor_advanced'])
        self.assertFalse(report['mutations']['project_brain_rewritten'])

    def test_bfdm_sha_advanced(self):
        report = self.evaluate(live_shas={DND: DND_SHA, BFDM: bump(BFDM_SHA)})
        self.assertEqual(report['repos'][BFDM]['status'], 'SHA_ADVANCED_REVIEW_NEEDED')
        self.assertEqual(report['repos'][DND]['status'], 'REVIEWED_CURRENT')
        self.assertEqual(report['classification'], 'SHA_ADVANCED_REVIEW_NEEDED')
        self.assertFalse(report['project_brain_automatically_stale'])
        self.assertEqual(report['sha_advance_means'], STATUS.SHA_ADVANCE_MEANS)

    def test_authority_unavailable(self):
        report = self.evaluate(live_shas={DND: None, BFDM: None})
        self.assertEqual(report['repos'][DND]['status'], 'UNAVAILABLE')
        self.assertEqual(report['repos'][BFDM]['status'], 'UNAVAILABLE')
        self.assertEqual(report['classification'], 'AUTHORITY_UNAVAILABLE')
        self.assertTrue(report['local_plumbing_intact'])
        self.assertFalse(report['project_brain_automatically_stale'])

    def test_zero_comments_and_null_cursor(self):
        report = self.evaluate(issue=CLEAR)
        inbox = report['semantic_inbox']
        self.assertIsNone(inbox['recorded_cursor'])
        self.assertEqual(inbox['comment_count'], 0)
        self.assertEqual(inbox['pending_comment_ids'], [])
        self.assertEqual(inbox['status'], 'CLEAR')
        self.assertFalse(inbox['acceptance_inferred'])
        self.assertFalse(inbox['auto_reconciled'])
        self.assertNotIn('INTEGRITY_FAILURE', report['classification'])

    def test_pending_semantic_deltas(self):
        report = self.evaluate(issue=PENDING)
        inbox = report['semantic_inbox']
        self.assertEqual(inbox['status'], 'SEMANTIC_DELTAS_PENDING')
        self.assertEqual(inbox['pending_comment_ids'], [101, 202])
        self.assertEqual(report['classification'], 'SEMANTIC_DELTAS_PENDING')
        self.assertFalse(inbox['acceptance_inferred'])
        self.assertFalse(inbox['auto_reconciled'])
        self.assertFalse(report['mutations']['semantic_deltas_auto_reconciled'])
        self.assertIn('not reconciled', inbox['note'])

        state = json.loads(json.dumps(STATE))
        state['checkpoint']['context_inbox']['last_fully_reconciled_comment_id'] = 101
        bounded = self.evaluate(issue=PENDING, state_override=state)
        self.assertEqual(bounded['semantic_inbox']['pending_comment_ids'], [202])
        self.assertNotIn(101, bounded['semantic_inbox']['pending_comment_ids'])
        self.assertFalse(bounded['semantic_inbox']['acceptance_inferred'])
        self.assertIn('did not accept, reject, or reconcile', bounded['semantic_inbox']['note'])

    def test_invalid_semantic_inbox_cursor(self):
        state = json.loads(json.dumps(STATE))
        state['checkpoint']['context_inbox']['last_fully_reconciled_comment_id'] = 999999
        report = self.evaluate(issue=PENDING, state_override=state)
        self.assertEqual(report['classification'], 'INTEGRITY_FAILURE')
        self.assertEqual(report['semantic_inbox']['status'], 'CURSOR_INTEGRITY_FAILURE')
        self.assertEqual(report['semantic_inbox']['pending_comment_ids'], [])
        self.assertIn('semantic inbox cursor does not identify a known comment', report['integrity_failures'])
        self.assertIn('not inferred', report['semantic_inbox']['note'])
        self.assertFalse(report['semantic_inbox']['acceptance_inferred'])

    def test_bfdm_duplicate_cursor(self):
        report = self.evaluate(bfdm_control=DUPLICATE, sibling_local_state_present=True)
        self.assertEqual(report['classification'], 'INTEGRITY_FAILURE')
        self.assertEqual(report['sibling_pointer']['status'], 'DUPLICATE_CURSOR')
        self.assertTrue(any('duplicate Gardener cursor' in item for item in report['integrity_failures']))
        self.assertTrue(any('context_review' in item for item in report['integrity_failures']))
        self.assertNotEqual(report['sibling_pointer']['observed'], STATUS.CANONICAL_STATE)

    def test_missing_project_brain_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in STATUS.REQUIRED_PATHS:
                if rel == STATUS.BRAIN_PATH:
                    continue
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, dest)
            report = STATUS.evaluate(
                root,
                live_shas={DND: DND_SHA, BFDM: BFDM_SHA},
                issue=CLEAR,
                bfdm_control=POINTER,
                sibling_local_state_present=False,
                resolve_commits=False,
            )
        self.assertEqual(report['classification'], 'INTEGRITY_FAILURE')
        self.assertFalse(report['checkpoint']['valid'])
        self.assertIsNone(report['checkpoint']['brain_path'])
        self.assertIn('Project Brain path is missing: docs/PROJECT_UNDERSTANDING.md', report['integrity_failures'])

    def test_changelog_restored_as_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in STATUS.REQUIRED_PATHS:
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, dest)
            bootstrap = (root / 'PROJECT_BOOTSTRAP.md').read_text(encoding='utf-8')
            bootstrap = bootstrap.replace(
                '### 1. Project Brain first',
                '### 1. Project Brain first\n\nRead `coordination/CONTEXT_CHANGELOG.md` before anything else.\n',
                1)
            (root / 'PROJECT_BOOTSTRAP.md').write_text(bootstrap, encoding='utf-8')
            control = json.loads((root / 'coordination' / 'control.json').read_text(encoding='utf-8'))
            control['context_changelog'] = 'coordination/CONTEXT_CHANGELOG.md'
            (root / 'coordination' / 'control.json').write_text(json.dumps(control), encoding='utf-8')
            report = STATUS.evaluate(
                root,
                live_shas={DND: DND_SHA, BFDM: BFDM_SHA},
                issue=CLEAR,
                bfdm_control=POINTER,
                sibling_local_state_present=False,
                resolve_commits=False,
            )
        self.assertEqual(report['classification'], 'INTEGRITY_FAILURE')
        self.assertIn('CONTEXT_CHANGELOG.md is required bootstrap reading', report['integrity_failures'])
        self.assertIn('active context_changelog pointer in coordination/control.json', report['integrity_failures'])
        self.assertTrue(report['structural_cold_start']['changelog_required'])

    def test_changelog_banner_cannot_silently_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in STATUS.REQUIRED_PATHS:
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / rel, dest)
            path = root / 'coordination' / 'CONTEXT_CHANGELOG.md'
            path.write_text('# Current context changelog\n\nKeep this up to date.\n', encoding='utf-8')
            report = STATUS.evaluate(
                root,
                live_shas={DND: DND_SHA, BFDM: BFDM_SHA},
                issue=CLEAR,
                bfdm_control=POINTER,
                sibling_local_state_present=False,
                resolve_commits=False,
            )
        self.assertEqual(report['classification'], 'INTEGRITY_FAILURE')
        self.assertTrue(any('historical banner' in item for item in report['integrity_failures']))

    def test_progressive_bootstrap_contract(self):
        text = (ROOT / 'PROJECT_BOOTSTRAP.md').read_text(encoding='utf-8')
        self.assertEqual(STATUS.bootstrap_contract_errors(text), [])
        self.assertLess(text.find('### 1. Project Brain first'), text.find('### 2. Reconcile with live authority'))
        self.assertLess(text.find('### 2. Reconcile with live authority'), text.find('### 3. Enter the owning task'))
        self.assertLess(text.find('### 3. Enter the owning task'), text.find('## Load deeper context only when relevant'))
        self.assertIn('Context impact:', (ROOT / 'coordination' / 'HANDOFF_TEMPLATE.md').read_text(encoding='utf-8'))
        pull = (ROOT / '.github' / 'pull_request_template.md').read_text(encoding='utf-8')
        self.assertIn('Project-context impact', pull)
        for name in STATUS.CONTEXT_CLASSES:
            self.assertIn(name, pull)
        dnd_control = json.loads((ROOT / 'coordination' / 'control.json').read_text(encoding='utf-8'))
        self.assertNotIn('context_changelog', dnd_control)
        self.assertEqual(dnd_control['gardener_state'], 'coordination/context_state.json')
        self.assertEqual(POINTER['gardener_state'], STATUS.CANONICAL_STATE)
        self.assertNotIn('context_changelog', POINTER)
        self.assertNotIn('context_state.json', POINTER['gardener_state'].split('/')[0])

    def test_structural_cold_start(self):
        route = STATUS.cold_start_route(
            (ROOT / 'README.md').read_text(encoding='utf-8'),
            (ROOT / 'START_HERE.md').read_text(encoding='utf-8'),
            (ROOT / 'PROJECT_BOOTSTRAP.md').read_text(encoding='utf-8'))
        self.assertEqual(route['errors'], [])
        self.assertEqual(route['project_brain'], 'docs/PROJECT_UNDERSTANDING.md')
        self.assertIn('radarsaint/dnd-solo/main', route['live_authority'])
        self.assertIn('radarsaint/bfdm-corpus/main', route['live_authority'])
        self.assertIn('PROJECT_CONTROL.md', route['live_authority'])
        self.assertEqual(route['owning_task'], 'issue/PR or explicit user instruction')
        self.assertTrue(route['deeper_context_conditional'])
        self.assertTrue(route['agents_and_tools_conditional'])
        self.assertTrue(route['gardener_checkpoint_discoverable'])
        self.assertTrue(route['semantic_inbox_discoverable'])
        self.assertTrue(route['historical_evidence_conditional'])
        self.assertTrue(route['implementation_files_conditional'])
        self.assertTrue(route['live_play_distinguished'])
        self.assertFalse(route['changelog_required'])
        self.assertFalse(route['area_6c_treated_as_architecture'])
        self.assertFalse(route['proves_gpt_understanding'])

    def test_historical_surface_guard_on_real_tree(self):
        changelog = (ROOT / 'coordination' / 'CONTEXT_CHANGELOG.md').read_text(encoding='utf-8')
        self.assertEqual(STATUS.changelog_banner_errors(changelog), [])
        bootstrap = (ROOT / 'PROJECT_BOOTSTRAP.md').read_text(encoding='utf-8')
        required = bootstrap[bootstrap.find('## Required bootstrap path'):bootstrap.find('## Load deeper context only when relevant')]
        self.assertNotIn('CONTEXT_CHANGELOG.md', required)
        for rel in ('coordination/control.json',):
            self.assertNotIn('context_changelog', json.loads((ROOT / rel).read_text(encoding='utf-8')))
        self.assertIn('coordination/CONTEXT_CHANGELOG.md', json.loads((ROOT / 'coordination' / 'control.json').read_text(encoding='utf-8'))['history_only'])

    def test_cli_exit_codes(self):
        script = str(ROOT / 'scripts' / 'project_context_status.py')
        valid = subprocess.run(
            [sys.executable, script, '--offline', '--json', '--dnd-sha', DND_SHA, '--bfdm-sha', BFDM_SHA,
             '--bfdm-control', str(FIXTURES / 'bfdm_control_shared_pointer.json'),
             '--issue-fixture', str(FIXTURES / 'issue_clear.json'),
             '--sibling-local-state', 'absent'],
            capture_output=True, text=True, check=False)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        payload = json.loads(valid.stdout)
        self.assertEqual(payload['classification'], 'REVIEWED_CURRENT')
        self.assertEqual(payload['schema'], STATUS.SCHEMA)
        unavailable = subprocess.run(
            [sys.executable, script, '--offline', '--json',
             '--bfdm-control', str(FIXTURES / 'bfdm_control_shared_pointer.json'),
             '--issue-fixture', str(FIXTURES / 'issue_clear.json'),
             '--sibling-local-state', 'absent'],
            capture_output=True, text=True, check=False)
        self.assertEqual(unavailable.returncode, 3, unavailable.stderr)
        self.assertEqual(json.loads(unavailable.stdout)['classification'], 'AUTHORITY_UNAVAILABLE')
        with tempfile.TemporaryDirectory() as tmp:
            broken = subprocess.run(
                [sys.executable, script, '--offline', '--json', '--root', tmp,
                 '--dnd-sha', DND_SHA, '--bfdm-sha', BFDM_SHA,
                 '--bfdm-control', str(FIXTURES / 'bfdm_control_shared_pointer.json'),
                 '--issue-fixture', str(FIXTURES / 'issue_clear.json'),
                 '--sibling-local-state', 'absent', '--skip-commit-resolve'],
                capture_output=True, text=True, check=False)
        self.assertEqual(broken.returncode, 2, broken.stderr)
        self.assertEqual(json.loads(broken.stdout)['classification'], 'INTEGRITY_FAILURE')

    def test_sha_advance_and_pending_deltas_are_both_visible(self):
        report = self.evaluate(live_shas={DND: bump(DND_SHA), BFDM: BFDM_SHA}, issue=PENDING)
        self.assertEqual(report['classification'], 'SEMANTIC_DELTAS_PENDING')
        self.assertEqual(report['review_signals'], ['SHA_ADVANCED_REVIEW_NEEDED', 'SEMANTIC_DELTAS_PENDING'])
        self.assertEqual(report['repos'][DND]['status'], 'SHA_ADVANCED_REVIEW_NEEDED')
        self.assertFalse(report['project_brain_automatically_stale'])


class GhApiFallbackTests(unittest.TestCase):
    """api_get must not require a live GitHub login. Runners and transports are fakes."""

    def result(self, runner, transport):
        calls = []

        def transport_spy(path):
            calls.append(path)
            return transport(path)

        found = STATUS.api_get('repos/radarsaint/dnd-solo/issues/115', runner=runner, transport=transport_spy)
        return found, calls

    def test_gh_success_does_not_call_urllib(self):
        def runner(_path):
            return subprocess.CompletedProcess(
                ['gh', 'api'], 0, stdout='{"sha":"abc"}\n', stderr='')

        found, calls = self.result(runner, lambda _path: self.fail('urllib should not run'))
        self.assertTrue(found.ok)
        self.assertEqual(found.status, 200)
        self.assertEqual(found.data, {'sha': 'abc'})
        self.assertEqual(calls, [])

    def test_gh_404_is_kept(self):
        body = '{"message":"Not Found","status":"404"}\n'

        def runner(_path):
            return subprocess.CompletedProcess(
                ['gh', 'api'], 1, stdout=body, stderr='gh: Not Found (HTTP 404)\n')

        found, calls = self.result(runner, lambda _path: self.fail('urllib should not replace a real 404'))
        self.assertFalse(found.ok)
        self.assertEqual(found.status, 404)
        self.assertEqual(found.data['message'], 'Not Found')
        self.assertEqual(calls, [])

    def test_unauthenticated_gh_falls_back_to_urllib(self):
        def runner(_path):
            return subprocess.CompletedProcess(
                ['gh', 'api'], 4, stdout='',
                stderr='To get started with GitHub CLI, please run:  gh auth login\n')

        def transport(path):
            self.assertIn('issues/115', path)
            return STATUS.ApiResult(True, 200, {'state': 'open', 'title': 'Semantic delta inbox'})

        found, calls = self.result(runner, transport)
        self.assertEqual(calls, ['repos/radarsaint/dnd-solo/issues/115'])
        self.assertTrue(found.ok)
        self.assertEqual(found.data['state'], 'open')

    def test_gh_401_falls_back_and_urllib_404_is_preserved(self):
        def runner(_path):
            return subprocess.CompletedProcess(
                ['gh', 'api'], 1,
                stdout='{"message":"Bad credentials","status":"401"}\n',
                stderr='gh: Bad credentials (HTTP 401)\n')

        def transport(_path):
            return STATUS.ApiResult(False, 404, {'message': 'Not Found'})

        found, calls = self.result(runner, transport)
        self.assertEqual(len(calls), 1)
        self.assertFalse(found.ok)
        self.assertEqual(found.status, 404)
        self.assertEqual(found.data['message'], 'Not Found')

    def test_unusable_gh_output_falls_back(self):
        def runner(_path):
            raise subprocess.TimeoutExpired(cmd='gh', timeout=30)

        found, calls = self.result(runner, lambda _path: STATUS.ApiResult(True, 200, {'ok': True}))
        self.assertEqual(len(calls), 1)
        self.assertTrue(found.ok)

    def test_non_auth_http_error_is_not_replaced(self):
        def runner(_path):
            return subprocess.CompletedProcess(
                ['gh', 'api'], 1,
                stdout='{"message":"Validation Failed","status":"422"}\n',
                stderr='gh: Validation Failed (HTTP 422)\n')

        found, calls = self.result(runner, lambda _path: self.fail('urllib should not hide a real HTTP error'))
        self.assertFalse(found.ok)
        self.assertEqual(found.status, 422)
        self.assertEqual(calls, [])

    def test_workflow_requests_issue_read_and_no_write(self):
        text = (ROOT / '.github' / 'workflows' / 'project-context-status.yml').read_text(encoding='utf-8')
        self.assertIn('contents: read', text)
        self.assertIn('issues: read', text)
        self.assertNotIn('issues: write', text)
        self.assertNotRegex(text, r': write\b')


if __name__ == '__main__':
    unittest.main()
