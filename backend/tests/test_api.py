"""HTTP contract checks; TestClient makes no requests to production."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
with patch.dict(os.environ, {"APP_ENV": "test", "DEBUG": "false"}):
    from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_profile_contract(self):
        data = {'name':'', 'title':'', 'introduction':'', 'skills':[], 'avatar_file_id':None, 'contacts':[], 'social_links':[]}
        with patch('app.profile.load_profile', return_value=data), patch('app.projects.list_published', return_value=[]):
            response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        for field in ("name", "title", "introduction"):
            self.assertIsInstance(profile[field], str)
        self.assertEqual(profile["name"], "")
        self.assertIsInstance(profile["skills"], list)
        self.assertTrue(all(isinstance(skill, str) for skill in profile["skills"]))
        self.assertIsInstance(profile["projects"], list)
        for project in profile["projects"]:
            self.assertIsInstance(project["name"], str)
            self.assertIsInstance(project["description"], str)

    def test_dice_includes_both_boundaries(self):
        # Deterministic samples detect off-by-one errors without random flakes.
        for raw in range(6):
            with self.subTest(raw=raw), patch("app.main.randbelow", return_value=raw):
                response = self.client.post("/api/dice/roll")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"value": raw + 1})

    def test_real_dice_is_an_integer_in_range(self):
        response = self.client.post("/api/dice/roll")
        self.assertEqual(response.status_code, 200)
        value = response.json()["value"]
        self.assertIs(type(value), int)
        self.assertTrue(1 <= value <= 6)

    def test_dice_requires_post(self):
        self.assertEqual(self.client.get("/api/dice/roll").status_code, 405)


class SettingsIntegrationTests(unittest.TestCase):
    def test_fastapi_reads_debug_from_environment(self):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("APP_", "DB_")) and key != "DEBUG"}
        env.update(APP_ENV="test", DEBUG="true")
        result = subprocess.run(
            [sys.executable, "-c", "from app.main import app; print(app.debug)"],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
