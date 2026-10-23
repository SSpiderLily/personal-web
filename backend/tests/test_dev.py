"""Local supervisor boundaries, using controlled child processes and no network."""
from pathlib import Path
import os
import signal
import socket
import sys
import tempfile
import time
import subprocess
import unittest
from unittest.mock import Mock, patch

from app import dev
from app.settings import Settings


class DevTests(unittest.TestCase):
    def configuration(self, **overrides):
        return Settings(_env_file=None, app_env="development", dev_ssh_host="cloud.example", **overrides)

    def process(self, pid, status=None):
        process = Mock(pid=pid)
        process.poll.return_value = status
        return process

    def test_production_refused_before_starting_children(self):
        settings = Mock(app_env="production")
        with patch.object(dev.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "development"):
                dev.run_dev(settings)
        launch.assert_not_called()

    def test_occupied_local_port_never_starts_children(self):
        with patch.object(dev, "require_free_port", side_effect=RuntimeError("occupied")), patch.object(dev.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(RuntimeError, "occupied"):
                dev.run_dev(self.configuration())
        launch.assert_not_called()

    def test_ssh_failure_does_not_start_backend_and_cleans_up(self):
        ssh = self.process(101, 255)
        with patch.object(dev, "require_free_port"), patch.object(dev.subprocess, "Popen", return_value=ssh) as launch, patch.object(dev, "stop_process") as stop:
            with self.assertRaisesRegex(RuntimeError, "SSH"):
                dev.run_dev(self.configuration())
        self.assertEqual(launch.call_count, 1)
        self.assertIn(ssh, [call.args[0] for call in stop.call_args_list])

    def test_backend_exit_closes_owned_ssh(self):
        ssh = self.process(101)
        backend = self.process(202, 7)
        with patch.object(dev, "require_free_port"), patch.object(dev, "wait_for_tunnel"), patch.object(dev.subprocess, "Popen", side_effect=[ssh, backend]) as launch, patch.object(dev, "stop_process") as stop:
            self.assertEqual(dev.run_dev(self.configuration()), 7)
        self.assertEqual({call.args[0].pid for call in stop.call_args_list if call.args[0]}, {101, 202})
        ssh_args = launch.call_args_list[0].args[0]
        self.assertIn("127.0.0.1:15432:127.0.0.1:5432", ssh_args)
        self.assertIn("StrictHostKeyChecking=yes", ssh_args)
        self.assertIn("BatchMode=yes", ssh_args)
        self.assertEqual(ssh_args[-1], "cloud.example")
        backend_call = launch.call_args_list[1]
        self.assertIn("8010", backend_call.args[0])
        self.assertEqual(backend_call.kwargs["cwd"], Path(dev.__file__).resolve().parents[1])
        self.assertTrue(backend_call.kwargs["start_new_session"])

    def test_dropped_tunnel_stops_running_backend(self):
        ssh = self.process(101, 255)
        backend = self.process(202)
        with patch.object(dev, "require_free_port"), patch.object(dev, "wait_for_tunnel"), patch.object(dev.subprocess, "Popen", side_effect=[ssh, backend]), patch.object(dev, "stop_process") as stop:
            with self.assertRaisesRegex(RuntimeError, "SSH"):
                dev.run_dev(self.configuration())
        self.assertIn(backend, [call.args[0] for call in stop.call_args_list])

    def test_keyboard_interrupt_closes_both_owned_processes(self):
        ssh = self.process(101)
        backend = self.process(202)
        with patch.object(dev, "require_free_port"), patch.object(dev, "wait_for_tunnel"), patch.object(dev.subprocess, "Popen", side_effect=[ssh, backend]), patch.object(dev.time, "sleep", side_effect=KeyboardInterrupt), patch.object(dev, "stop_process") as stop:
            with self.assertRaises(KeyboardInterrupt):
                dev.run_dev(self.configuration())
        self.assertEqual({call.args[0].pid for call in stop.call_args_list if call.args[0]}, {101, 202})

    def test_wait_timeout_stops_without_launching_backend(self):
        ssh = self.process(101)
        with patch.object(dev, "require_free_port"), patch.object(dev, "wait_for_tunnel", side_effect=RuntimeError("SSH timeout")), patch.object(dev.subprocess, "Popen", return_value=ssh) as launch, patch.object(dev, "stop_process") as stop:
            with self.assertRaisesRegex(RuntimeError, "SSH timeout"):
                dev.run_dev(self.configuration())
        self.assertEqual(launch.call_count, 1)
        self.assertIn(ssh, [call.args[0] for call in stop.call_args_list])

    def test_ssh_overrides_backgrounding_and_connection_reuse(self):
        ssh = self.process(101)
        backend = self.process(202, 0)
        with patch.object(dev, "require_free_port"), patch.object(dev, "wait_for_tunnel"), patch.object(dev.subprocess, "Popen", side_effect=[ssh, backend]) as launch, patch.object(dev, "stop_process"):
            dev.run_dev(self.configuration())
        args = launch.call_args_list[0].args[0]
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "ssh_config"
            config.write_text("Host cloud.example\n  ForkAfterAuthentication yes\n  ControlMaster auto\n  ControlPath /tmp/unused-shared-master\n  ControlPersist yes\n")
            result = subprocess.run(["ssh", "-G", "-F", str(config), *args[1:]], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        effective = dict(line.split(" ", 1) for line in result.stdout.splitlines())
        self.assertEqual(effective["forkafterauthentication"], "no")
        self.assertEqual(effective["controlmaster"], "false")
        self.assertEqual(effective.get("controlpath", "none"), "none")
        self.assertEqual(effective["controlpersist"], "no")

    def test_stop_process_cleans_worker_after_parent_already_exited(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "ready"
            child_code = "import signal,socket,sys,time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); s=socket.socket(); s.bind(('127.0.0.1',int(sys.argv[1]))); s.listen(); Path(sys.argv[2]).write_text('ready'); time.sleep(30)"
            parent_code = "import subprocess,sys; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2],sys.argv[3]],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            parent = subprocess.Popen([sys.executable, "-c", parent_code, child_code, str(port), str(ready)], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            released = False
            try:
                parent.wait(timeout=5)
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "controlled worker did not start")
                dev.stop_process(parent)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    with socket.socket() as listener:
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        try:
                            listener.bind(("127.0.0.1", port))
                        except OSError:
                            time.sleep(0.02)
                        else:
                            released = True
                            break
                self.assertTrue(released, "worker still holds its port after parent exited and cleanup returned")
            finally:
                if not released:
                    try:
                        os.killpg(parent.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                parent.wait(timeout=5)

    def test_stop_process_kills_group_after_grace_period(self):
        process = self.process(202)
        with patch.object(dev.os, "killpg") as kill, patch.object(dev.time, "monotonic", side_effect=[0, 6]):
            dev.stop_process(process)
        self.assertEqual([call.args[1] for call in kill.call_args_list if call.args[1]], [dev.signal.SIGTERM, dev.signal.SIGKILL])
        process.wait.assert_called()
