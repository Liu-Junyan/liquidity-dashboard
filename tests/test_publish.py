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
        self.directory = Path(temporary.name).resolve()
        self.repo = self.directory / 'repo'
        self.repo.mkdir()
        for name in ('scripts', 'site'):
            shutil.copytree(ROOT / name, self.repo / name, ignore=shutil.ignore_patterns('__pycache__'))
        (self.repo / 'data').mkdir()
        for name in ('registry.csv', 'categories.json', 'source-reviews.json'):
            shutil.copyfile(ROOT / 'data' / name, self.repo / 'data' / name)
        manual = self.repo / 'data/manual'
        shutil.copytree(ROOT / 'data/manual', manual, ignore=shutil.ignore_patterns('bond-issuance.csv'))
        # Seed the test repository before its first input commit so correction audits use a fixed history.
        (manual / 'bond-issuance.csv').write_text('date,value\n2020-01-31,10\n')
        (self.repo / '.gitignore').write_text('dist/\n__pycache__/\n.env\n')
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
        self.assertEqual(docs[1]['series']['sofr-effr-spread'][0]['value'], 10)
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
        path = self.repo / 'data/manual/bond-issuance.csv'
        month_end = '2020-02-29'
        original = path.read_text()
        path.write_text(original + f'{month_end},1\n')
        self.commit('Add manual observation')
        git(self.repo, 'push', 'origin', 'main')
        with patch.dict('os.environ', {'FRED_API_KEY': ''}):
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'][-1]['value'], 1)
            path.write_text(original + f'{month_end},2\n')
            self.commit(f'Correct manual input\n\nManual-Reason: bond-issuance {month_end}: source revision')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'][-1]['value'], 2)
            path.write_text(original)
            self.commit(f'Remove erroneous month\n\nManual-Reason: bond-issuance {month_end}: '
                        'source withdrew preliminary observation')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            self.assertEqual(json.loads((self.repo / 'dist/data/observations.json').read_text())
                             ['series']['bond-issuance'], [{'date': '2020-01-31', 'value': 10}])
            path.write_text(original + f'{month_end},2\n')
            self.commit('Restore month as a new observation')
            git(self.repo, 'push', 'origin', 'main')
            self.assertTrue(self.publish()['deploy'])
            self.sync()
            before = (self.repo / 'dist/data/manifest.json').read_bytes()
            path.write_text(original + f'{month_end},3\n')
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

    def test_rollback_redeploys_release_then_publish_resumes_current_release(self):
        first = self.publish()
        self.sync()
        output = self.repo / 'dist'
        original = {p.relative_to(output): p.read_bytes() for p in output.rglob('*')
                    if p.is_file() and p.name != 'release.json'}
        refresh(self.repo, SavedInputClient(), now=self.later_time)
        index = self.repo / 'site/index.html'
        index.write_text(index.read_text() + '\n<!-- Updated dashboard -->\n')
        self.commit('Update dashboard and saved inputs')
        git(self.repo, 'push', 'origin', 'main')
        second = self.publish()
        current_release = (output / 'data/release.json').read_bytes()
        self.assertNotEqual(first['artifact'], second['artifact'])
        result = self.publish(mode='rollback', rollback=first['artifact'], delivery='pull-request',
                              open_pr=lambda *args: self.fail('Rollback opened a PR'))
        self.assertTrue(result['deploy'])
        self.assertEqual(result['artifact'], first['artifact'])
        self.assertEqual(self.current(), second['artifact'])
        self.assertEqual(original, {path: (output / path).read_bytes() for path in original})
        stamp = json.loads((output / 'data/release.json').read_text())
        self.assertEqual(stamp['artifactCommit'], first['artifact'])
        self.assertEqual(stamp['restoredFrom'], first['artifact'])
        self.assertEqual(self.publish()['artifact'], second['artifact'])
        self.assertEqual((output / 'data/release.json').read_bytes(), current_release)
        self.assertIn('Updated dashboard', (output / 'index.html').read_text())

    def test_branch_advance_during_rollback_skips_output(self):
        first = self.publish()
        self.sync()
        previous = (self.repo / 'dist/data/release.json').read_bytes()
        with patch('scripts.publish.remote_head', side_effect=[first['artifact'], 'b' * 40]):
            result = self.publish(mode='rollback', rollback=first['artifact'])
        self.assertFalse(result['deploy'])
        self.assertEqual(self.current(), first['artifact'])
        self.assertEqual((self.repo / 'dist/data/release.json').read_bytes(), previous)

    def test_dirty_sources_and_untrusted_rollback_refs_are_rejected(self):
        for ref in ('main', '--help', 'a' * 40):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.publish(mode='rollback', rollback=ref)
        (self.repo / 'data/categories.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'clean checkout'):
            release.prepare(self.repo)

    def test_rollback_rejects_unvalidated_historic_automatic_inputs(self):
        self.publish()
        self.sync()
        path = self.repo / 'data/automatic/sofr.json'
        path.write_text(path.read_text() + '\n')
        tampered = self.commit('Unvalidated automatic input change')
        git(self.repo, 'push', 'origin', 'main')
        with self.assertRaisesRegex(ValueError, 'historic publication record'):
            self.publish(mode='rollback', rollback=tampered)

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


class HistoricalReleaseTests(unittest.TestCase):
    def test_november_release_uses_its_original_calculation_policy(self):
        target = '7f8c7c9305bf2a898515056d8c5ac892ad5f7fe6'
        snapshot = 'production-911b528875316300d1275b0d0c01980964477ba3903a9898fa5a1ebb78584300'
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / 'repo'
            remote = Path(directory) / 'remote.git'
            git(ROOT, 'init', '--bare', str(remote))
            # A check can run in a detached worktree. Give the test remote its own main.
            git(remote, 'fetch', str(ROOT), 'HEAD:refs/heads/main')
            git(ROOT, 'clone', '--branch', 'main', str(remote), str(repo))
            before = publish.remote_head(repo, 'main')
            result = publish.publish(repo, mode='rollback', rollback=target)
            self.assertTrue(result['deploy'])
            public = repo / 'dist/data'
            stamp = json.loads((public / 'release.json').read_bytes())
            self.assertEqual(stamp['snapshotId'], snapshot)
            self.assertEqual(stamp['artifactCommit'], target)
            self.assertEqual(stamp['restoredFrom'], target)
            for name in ('catalog.json', 'observations.json', 'manifest.json'):
                archived = subprocess.check_output(['git', '-C', str(repo), 'show', f'{target}:data/snapshot/{name}'])
                self.assertEqual((public / name).read_bytes(), archived)
            observations = json.loads((public / 'observations.json').read_bytes())
            self.assertEqual(len(observations['series']['sofr-effr-spread']), 4401)
            self.assertEqual(publish.remote_head(repo, 'main'), before)


if __name__ == '__main__':
    unittest.main()
