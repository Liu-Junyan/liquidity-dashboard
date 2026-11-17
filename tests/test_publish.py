"""Offline release exercises use real Git commits, remotes, merges and push races."""
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import publish, release
from scripts.collect import refresh
from scripts.import_manual import git
from scripts.registry import ROOT
from test_assemble import SavedInputClient


class PublicationTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.initial_time = (now - timedelta(hours=3)).isoformat().replace('+00:00', 'Z')
        self.later_time = (now - timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
        temporary = tempfile.TemporaryDirectory(prefix='publication-test-')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / 'repo'
        self.repo.mkdir()
        for name in ('scripts', 'site'):
            shutil.copytree(ROOT / name, self.repo / name, ignore=shutil.ignore_patterns('__pycache__'))
        (self.repo / 'data').mkdir()
        for name in ('registry.csv', 'categories.json', 'source-reviews.json'):
            shutil.copyfile(ROOT / 'data' / name, self.repo / 'data' / name)
        shutil.copytree(ROOT / 'data/manual', self.repo / 'data/manual')
        (self.repo / '.gitignore').write_text('dist/\ndist-preview/\n__pycache__/\n.env\n')
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'Release test')
        git(self.repo, 'config', 'user.email', 'release@example.test')
        git(self.repo, 'commit', '--allow-empty', '-m', 'Empty trusted baseline')
        refresh(self.repo, SavedInputClient(), now=self.initial_time)
        self.commit('Initial source and saved inputs')
        self.remote = self.directory / 'remote.git'
        git(self.directory, 'init', '--bare', str(self.remote))
        git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        git(self.repo, 'push', 'origin', 'main')

    def commit(self, message):
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', message)
        return git(self.repo, 'rev-parse', 'HEAD').strip()

    def publish(self, **options):
        return publish.publish(self.repo, verify=lambda repo: release.read_snapshot(repo), **options)

    def current(self):
        return publish.remote_head(self.repo, 'main')

    def sync(self):
        git(self.repo, 'merge', '--ff-only', self.current())

    def test_saved_inputs_publish_exact_artifact_without_collection(self):
        with patch('scripts.release.FredClient', side_effect=AssertionError('No network')):
            release.prepare(self.repo)
        record = json.loads((self.repo / release.RECORD).read_text())
        self.assertEqual(record['mode'], 'publish')
        self.commit('Prepared data')
        git(self.repo, 'push', 'origin', 'main')
        result = self.publish()
        self.assertTrue(result['deploy'])
        self.assertEqual(result['artifact'], self.current())
        public = json.loads((self.repo / 'dist/data/release.json').read_text())
        self.assertEqual(public['artifactCommit'], result['artifact'])
        self.assertEqual(public['snapshotId'], record['snapshotId'])
        release.validate_public_tree(self.repo / 'dist')
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')

    def test_old_queued_run_uses_current_branch_and_preserves_local_work(self):
        (self.repo / 'local-note.txt').write_text('Keep my local edits')
        original_head = git(self.repo, 'rev-parse', 'HEAD')
        result = self.publish()
        self.assertTrue(result['deploy'])
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), original_head)
        self.assertEqual((self.repo / 'local-note.txt').read_text(), 'Keep my local edits')
        second = self.publish()
        self.assertEqual(second['artifact'], result['artifact'])
        self.assertEqual(git(self.repo, 'worktree', 'list').count('\n'), 1)

    def test_concurrent_input_commit_forces_fresh_assembly(self):
        calls = []

        def advance(repo):
            release.read_snapshot(repo)
            calls.append(repo)
            if len(calls) == 1:
                categories = self.repo / 'data/categories.json'
                categories.write_text(categories.read_text() + '\n')
                self.new_input = self.commit('New category input while candidate builds')
                git(self.repo, 'push', 'origin', 'main')

        result = publish.publish(self.repo, verify=advance)
        self.assertEqual(len(calls), 2)
        self.assertTrue(result['deploy'])
        manifest = json.loads((self.repo / 'dist/data/manifest.json').read_text())
        self.assertEqual(manifest['sourceInputCommit'], self.new_input)
        self.assertTrue(release.is_ancestor(self.repo, self.new_input, result['artifact']))

    def test_race_at_push_retries_instead_of_force_pushing(self):
        real_run = subprocess.run
        advanced = []

        def racing_run(command, **kwargs):
            if (len(command) > 4 and command[:1] == ['git'] and command[3:5] == ['push', 'origin']
                    and command[-1].endswith(':refs/heads/main') and not advanced):
                advanced.append(True)
                (self.repo / 'data/categories.json').write_text(
                    (self.repo / 'data/categories.json').read_text() + '\n')
                self.new_input = self.commit('Input advances at push')
                git(self.repo, 'push', 'origin', 'main')
            return real_run(command, **kwargs)

        with patch('scripts.publish.subprocess.run', side_effect=racing_run):
            result = self.publish()
        self.assertTrue(result['deploy'])
        self.assertTrue(release.is_ancestor(self.repo, self.new_input, result['artifact']))
        manifest = json.loads((self.repo / 'dist/data/manifest.json').read_text())
        self.assertEqual(manifest['sourceInputCommit'], self.new_input)

    def test_continuous_input_changes_fail_without_replacing_previous_output(self):
        output = self.repo / 'dist'
        output.mkdir()
        (output / 'previous').write_text('Prior deployment')

        def advance(repo):
            path = self.repo / 'data/categories.json'
            path.write_text(path.read_text() + '\n')
            self.commit('New input')
            git(self.repo, 'push', 'origin', 'main')

        with self.assertRaisesRegex(ValueError, 'kept advancing'):
            publish.publish(self.repo, verify=advance, attempts=2)
        self.assertEqual((output / 'previous').read_text(), 'Prior deployment')

    def test_input_advancing_after_artifact_push_skips_upload(self):
        original_head = publish.remote_head
        calls = []
        (self.repo / 'dist').mkdir()
        (self.repo / 'dist/previous').write_text('Keep')

        def advance(repo, branch):
            calls.append(True)
            if len(calls) == 3:
                tip = original_head(repo, branch)
                git(self.repo, 'merge', '--ff-only', tip)
                path = self.repo / 'data/categories.json'
                path.write_text(path.read_text() + '\n')
                self.commit('Input after artifact push')
                git(self.repo, 'push', 'origin', 'main')
            return original_head(repo, branch)

        with patch('scripts.publish.remote_head', side_effect=advance):
            result = self.publish()
        self.assertFalse(result['deploy'])
        self.assertIn('Superseded', result['summary'])
        self.assertEqual((self.repo / 'dist/previous').read_text(), 'Keep')

    def test_recoverable_source_failure_retains_history_and_reports_warning(self):
        release.prepare(self.repo, mode='refresh', client=SavedInputClient({'sofr'}))
        record = json.loads((self.repo / release.RECORD).read_text())
        docs = release.read_snapshot(self.repo)
        self.assertEqual(docs[2]['outcomes']['sofr']['status'], 'retained')
        self.assertEqual(docs[1]['series']['sofr-effr-spread'][0]['value'], 0.1)
        self.assertIn('Collection warning', release.summary(self.repo, record, 'test', 'ready'))

    def test_fatal_validation_does_not_push_or_replace_previous_output(self):
        before = self.current()
        (self.repo / 'dist').mkdir()
        (self.repo / 'dist/previous').write_text('Keep')

        def fail(repo):
            raise ValueError('Fatal candidate check')

        with self.assertRaisesRegex(ValueError, 'Fatal candidate'):
            publish.publish(self.repo, verify=fail)
        self.assertEqual(before, self.current())
        self.assertEqual((self.repo / 'dist/previous').read_text(), 'Keep')

    def test_manual_addition_and_correction_publish_offline_but_unaudited_edit_blocks(self):
        directory = self.repo / 'data/manual'
        path = directory / 'bond-issuance.csv'
        original = path.read_text()
        path.write_text(original + '2026-11-30,1\n')
        self.commit('Add manual observation')
        git(self.repo, 'push', 'origin', 'main')
        with patch.dict('os.environ', {'FRED_API_KEY': ''}):
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'][-1]['value'], 1)
            path.write_text(original + '2026-11-30,2\n')
            self.commit('Correct manual input\n\nManual-Reason: bond-issuance 2026-11-30: source revision')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            before = (self.repo / 'dist/data/manifest.json').read_bytes()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'][-1]['value'], 2)
            path.write_text(original)
            self.commit('Remove erroneous month\n\nManual-Reason: bond-issuance 2026-11-30: '
                        'source withdrew preliminary observation')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'][-1]['date'], '2026-10-31')
            path.write_text(original + '2026-11-30,2\n')
            self.commit('Restore month as a new observation')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            before = (self.repo / 'dist/data/manifest.json').read_bytes()
            path.write_text(original + '2026-11-30,3\n')
            invalid = self.commit('Undocumented correction')
            git(self.repo, 'push', 'origin', 'main')
            with self.assertRaises(subprocess.CalledProcessError):
                self.publish()
        self.assertEqual(self.current(), invalid)
        self.assertEqual((self.repo / 'dist/data/manifest.json').read_bytes(), before)

    def test_data_pr_merge_publishes_without_another_generated_commit(self):
        prs = []
        result = self.publish(delivery='pull-request', open_pr=lambda *args: prs.append(args) or 'test-pr')
        self.assertFalse(result['deploy'])
        self.assertFalse((self.repo / 'dist').exists())
        candidate = prs[0][0]
        git(self.repo, 'fetch', 'origin', candidate)
        git(self.repo, 'merge', '--no-ff', '-m', 'Merge data update', 'FETCH_HEAD')
        merged = git(self.repo, 'rev-parse', 'HEAD').strip()
        git(self.repo, 'push', 'origin', 'main')
        adopted = self.publish(delivery='pull-request', open_pr=lambda *args: self.fail('Recursive PR'))
        self.assertTrue(adopted['deploy'])
        self.assertEqual(adopted['artifact'], merged)

    def test_rejected_default_branch_push_falls_back_to_data_pr(self):
        hook = self.remote / 'hooks/update'
        hook.write_text('#!/bin/sh\n[ "$1" != "refs/heads/main" ]\n')
        hook.chmod(0o755)
        before = self.current()
        prs = []
        result = self.publish(open_pr=lambda *args: prs.append(args) or 'test-pr')
        self.assertFalse(result['deploy'])
        self.assertEqual(before, self.current())
        self.assertTrue(prs[0][0].startswith('automation/data-'))

    def test_rollback_restores_exact_snapshot_and_automatic_inputs(self):
        first = self.publish()
        self.sync()
        old = {path: git(self.repo, 'show', f'{first["artifact"]}:{path}')
               for path in ('data/snapshot/manifest.json', 'data/automatic/sofr.json')}
        refresh(self.repo, SavedInputClient(), now=self.later_time)
        self.commit('Saved automatic refresh')
        git(self.repo, 'push', 'origin', 'main')
        second = self.publish()
        self.assertNotEqual(first['artifact'], second['artifact'])
        rolled_back = self.publish(mode='rollback', rollback=first['artifact'])
        self.assertTrue(rolled_back['deploy'])
        for path, content in old.items():
            self.assertEqual(git(self.repo, 'show', f'{rolled_back["artifact"]}:{path}'), content)
        self.assertIn('no collection', rolled_back['summary'])
        self.assertEqual(json.loads((self.repo / 'dist/data/release.json').read_text())['restoredFrom'], first['artifact'])
        reused = self.publish()
        self.assertEqual(reused['artifact'], rolled_back['artifact'])

    def test_rollback_pr_merge_keeps_original_snapshot(self):
        first = self.publish()
        self.sync()
        refresh(self.repo, SavedInputClient(), now=self.later_time)
        self.commit('New saved inputs')
        git(self.repo, 'push', 'origin', 'main')
        self.publish()
        self.sync()
        prs = []
        self.publish(mode='rollback', rollback=first['artifact'], delivery='pull-request',
                     open_pr=lambda *args: prs.append(args) or 'test-pr')
        git(self.repo, 'fetch', 'origin', prs[0][0])
        git(self.repo, 'merge', '--squash', 'FETCH_HEAD')
        merged = self.commit('Squash rollback data PR')
        git(self.repo, 'push', 'origin', 'main')
        result = self.publish(delivery='pull-request', open_pr=lambda *args: self.fail('Recursive PR'))
        self.assertTrue(result['deploy'])
        self.assertEqual(result['artifact'], merged)
        self.assertEqual(git(self.repo, 'show', f'{merged}:data/snapshot/manifest.json'),
                         git(self.repo, 'show', f'{first["artifact"]}:data/snapshot/manifest.json'))

    def test_dirty_sources_and_untrusted_rollback_refs_are_rejected(self):
        for ref in ('main', '--help', 'a' * 40):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                release.prepare(self.repo, mode='rollback', rollback=ref)
        (self.repo / 'data/categories.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'clean checkout'):
            release.prepare(self.repo)

    def test_rollback_rejects_unvalidated_historic_automatic_inputs(self):
        self.publish()
        self.sync()
        path = self.repo / 'data/automatic/sofr.json'
        path.write_text(path.read_text() + '\n')
        tampered = self.commit('Unvalidated automatic input change')
        with self.assertRaisesRegex(ValueError, 'historic publication record'):
            release.prepare(self.repo, mode='rollback', rollback=tampered)

    def test_private_files_and_symlinks_cannot_enter_public_artifact(self):
        result = self.publish()
        self.assertTrue(result['deploy'])
        for name in ('private.xlsx', '.env'):
            path = self.repo / 'dist' / name
            path.write_text('Never publish')
            with self.assertRaisesRegex(ValueError, 'Unexpected'):
                release.validate_public_tree(self.repo / 'dist')
            path.unlink()
        path = self.repo / 'dist/private'
        path.symlink_to(self.repo / 'data')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            release.validate_public_tree(self.repo / 'dist')

    def test_tampered_merged_artifact_fails_validation(self):
        self.publish()
        self.sync()
        path = self.repo / 'data/automatic/sofr.json'
        record = json.loads(path.read_text())
        record['observations'][0]['value'] = 999
        path.write_text(json.dumps(record))
        self.commit('Tampered artifact')
        with self.assertRaisesRegex(ValueError, 'hash'):
            release.prepare(self.repo)

    def test_source_change_after_data_pr_requires_reassembly(self):
        self.publish()
        self.sync()
        path = self.repo / 'data/categories.json'
        path.write_text(path.read_text() + '\n')
        changed = self.commit('New source input')
        self.assertIsNone(release.reusable_record(self.repo))
        release.prepare(self.repo)
        self.assertEqual(release.read_snapshot(self.repo)[2]['sourceInputCommit'], changed)


if __name__ == '__main__':
    unittest.main()
