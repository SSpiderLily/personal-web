"""Offline tests: temporary release dirs; no SSH, real service, or production HTTP."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import fcntl

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).parents[1] / 'scripts/deploy.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
OLD, NEW, LATER = 'a' * 40, 'b' * 40, 'c' * 40


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'releases').mkdir()
        (self.root / 'repository.git').mkdir()
        self.old = self.release(OLD)
        self.new = self.release(NEW)
        (self.root / 'current').symlink_to(self.old)
        self.config = {'root': str(self.root)}
        # Preserve historical code-switch regression tests; data boundary is covered separately.
        gate = patch.object(d.data_runtime, 'data_config', return_value={})
        gate.start(); self.addCleanup(gate.stop)
        activation = patch.object(d, 'activate_data', side_effect=lambda root, release, config, fd: d.activate(root, release, config))
        activation.start(); self.addCleanup(activation.stop)

    def release(self, sha):
        p = self.root / 'releases' / sha
        p.mkdir()
        (p / 'REVISION').write_text(sha)
        return p

    def test_success_switches_only_after_preparation(self):
        def prepare(*args):
            self.assertEqual((self.root / 'current').resolve(), self.old)
            return self.new
        with patch.object(d, 'fetch', return_value=NEW), patch.object(d, 'prepare', side_effect=prepare), patch.object(d, 'restart') as restart, patch.object(d, 'wait_healthy') as health:
            d.deploy(self.config, NEW)
        self.assertEqual((self.root / 'current').resolve(), self.new)
        restart.assert_called_once()
        self.assertEqual([c.args[1] for c in health.call_args_list], [OLD, NEW])

    def test_build_failure_keeps_current_without_restart(self):
        with patch.object(d, 'fetch', return_value=NEW), patch.object(d, 'prepare', side_effect=RuntimeError('build failed')), patch.object(d, 'restart') as restart, patch.object(d, 'wait_healthy'):
            with self.assertRaisesRegex(RuntimeError, 'build failed'):
                d.deploy(self.config, NEW)
        self.assertEqual((self.root / 'current').resolve(), self.old)
        restart.assert_not_called()

    def test_health_failure_rolls_back_and_still_fails(self):
        with patch.object(d, 'restart') as restart, patch.object(d, 'wait_healthy', side_effect=[RuntimeError('bad release'), None]) as health:
            with self.assertRaisesRegex(RuntimeError, 'bad release'):
                d.activate(self.root, self.new, self.config)
        self.assertEqual((self.root / 'current').resolve(), self.old)
        self.assertEqual(restart.call_count, 2)
        self.assertEqual([c.args[1] for c in health.call_args_list], [NEW, OLD])

    def test_restart_failure_rolls_back(self):
        with patch.object(d, 'restart', side_effect=[RuntimeError('restart failed'), None]), patch.object(d, 'wait_healthy') as health:
            with self.assertRaisesRegex(RuntimeError, 'restart failed'):
                d.activate(self.root, self.new, self.config)
        self.assertEqual((self.root / 'current').resolve(), self.old)
        health.assert_called_once_with(self.config, OLD)

    def test_interruption_rolls_back(self):
        with patch.object(d, 'restart', side_effect=[KeyboardInterrupt(), None]), patch.object(d, 'wait_healthy'):
            with self.assertRaises(KeyboardInterrupt):
                d.activate(self.root, self.new, self.config)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_rollback_failure_is_not_reported_as_success(self):
        with patch.object(d, 'restart'), patch.object(d, 'wait_healthy', side_effect=[RuntimeError('new unhealthy'), RuntimeError('old unhealthy')]):
            with self.assertRaisesRegex(RuntimeError, 'old unhealthy'):
                d.activate(self.root, self.new, self.config)
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_stale_sha_rejected_before_build(self):
        with patch.object(d, 'fetch', return_value=LATER), patch.object(d, 'prepare') as prepare, patch.object(d, 'wait_healthy'):
            with self.assertRaisesRegex(RuntimeError, 'stale SHA'):
                d.deploy(self.config, NEW)
        prepare.assert_not_called()

    def test_main_advancing_during_build_does_not_activate(self):
        with patch.object(d, 'fetch', side_effect=[NEW, LATER]), patch.object(d, 'prepare', return_value=self.new), patch.object(d, 'restart') as restart, patch.object(d, 'wait_healthy'):
            with self.assertRaisesRegex(RuntimeError, 'main changed'):
                d.deploy(self.config, NEW)
        restart.assert_not_called()
        self.assertEqual((self.root / 'current').resolve(), self.old)

    def test_duplicate_is_health_checked_without_rebuilding(self):
        with patch.object(d, 'fetch', return_value=OLD), patch.object(d, 'prepare') as prepare, patch.object(d, 'wait_healthy') as health:
            d.deploy(self.config, OLD)
        prepare.assert_not_called()
        health.assert_called_once_with(self.config, OLD)

    def test_busy_lock_prevents_commands(self):
        with (self.root / 'deploy.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(d, 'run') as run, patch.object(d, 'wait_healthy') as health:
                with self.assertRaises(BlockingIOError):
                    d.deploy(self.config, NEW)
            run.assert_not_called()
            health.assert_not_called()

    def test_uninitialized_root_rejected(self):
        (self.root / 'current').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Initialize'):
            d.deploy(self.config, NEW)

    def test_cli_is_inert_by_default_and_disabled_config_blocks_execute(self):
        result = subprocess.run([sys.executable, d.__file__, NEW], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('no commands executed', result.stdout)
        config = self.root / 'config.json'
        config.write_text('{"enabled": false}')
        result = subprocess.run([sys.executable, d.__file__, NEW, '--execute', '--config', str(config)], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('disabled', result.stderr)

    def test_invalid_revision_rejected(self):
        result = subprocess.run([sys.executable, d.__file__, 'main; echo unsafe'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_health_checks_marker_api_and_assets(self):
        import io
        config = {'health_url': 'http://unused.test', 'health_host': 'example.test'}
        bodies = [b'{"status":"ok"}', NEW.encode(), b'<script src="/assets/app.js"></script>', b'console.log(1)']
        with patch.object(d, 'run'), patch.object(d.urllib.request, 'urlopen', side_effect=[io.BytesIO(b) for b in bodies]) as fetch:
            d.healthy(config, NEW)
        self.assertEqual(fetch.call_count, 4)
        with patch.object(d, 'run'), patch.object(d.urllib.request, 'urlopen', side_effect=[io.BytesIO(b'{"status":"ok"}'), io.BytesIO(OLD.encode())]):
            with self.assertRaisesRegex(RuntimeError, 'expected release'):
                d.healthy(config, NEW)

    def test_prepare_uses_lockfiles_and_final_venv_path(self):
        config = dict(self.config, tool_path='/tools/bin', python='/tools/bin/python3.14', python_index='https://mirror.example/simple')
        commands = []
        def command(*args, cwd=None, env=None):
            commands.append(args)
            if args[:2] == ('node', '--version'): return 'v22.22.1'
            if args[:2] == ('uv', '--version'): return 'uv 0.12.3'
            if args[0] == config['python']: return 'Python 3.14.4'
            if args[0] == 'git': Path(args[args.index('-o') + 1]).touch()
            if args[0] == 'tar':
                target = Path(args[-1])
                (target / 'backend').mkdir()
                (target / 'frontend/dist').mkdir(parents=True)
            if env is not None:
                self.assertNotIn('VITE_TRIP_DEMO_URL', env)
            return ''
        with patch.dict(d.os.environ, {'VITE_TRIP_DEMO_URL': 'https://wrong.test'}), patch.object(d, 'run', side_effect=command):
            release = d.prepare(config, self.root, self.root / 'repository.git', NEW)
        self.assertIn(('uv', 'export', '--locked', '--no-dev', '--no-emit-project',
                       '--python', config['python'], '--format', 'requirements-txt'), commands)
        self.assertIn(('uv', 'pip', 'sync', '--python', str(release / 'backend/.venv/bin/python'),
                       '--require-hashes', '--index-url', config['python_index'],
                       'deployment-requirements.txt'), commands)
        self.assertIn(('npm', 'ci', '--no-audit', '--no-fund'), commands)
        self.assertTrue(any(c[0] == str(release / 'backend/.venv/bin/gunicorn') for c in commands))
        self.assertEqual((release / 'frontend/dist/__release.txt').read_text().strip(), NEW)
        self.assertEqual(release.stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / 'current').resolve(), self.old)


if __name__ == '__main__':
    unittest.main()
