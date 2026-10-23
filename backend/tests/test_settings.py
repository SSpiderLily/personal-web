"""Configuration boundaries; no database, SSH or production network access."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from app import settings as config


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.env_file = self.directory / ".env"
        self.enterContext(patch.object(config, "LOCAL_ENV_FILE", self.env_file))
        config.get_settings.cache_clear()
        self.addCleanup(config.get_settings.cache_clear)

    def write_local(self, content):
        self.env_file.write_text(content, encoding="utf-8")

    def production_env(self):
        return dict(APP_ENV="production", DEBUG="false", DB_HOST="127.0.0.1",
                    DB_PORT="5432", DB_NAME="personal_web_prod",
                    DB_USER="personal_web_prod", DB_PASSWORD="test-only-secret")

    def test_local_file_and_environment_override(self):
        self.write_local("APP_ENV=development\nDEBUG=true\nDB_PORT=15432\nDB_NAME=local_dev\nDB_PASSWORD='test-password#with$chars'\n")
        with patch.dict(os.environ, {"DB_NAME": "override_dev"}):
            settings = config.get_settings()
        self.assertTrue(settings.debug)
        self.assertEqual(settings.db_port, 15432)
        self.assertEqual(settings.db_name, "override_dev")
        self.assertEqual(settings.db_password.get_secret_value(), "test-password#with$chars")

    def test_local_path_does_not_follow_working_directory(self):
        self.write_local("DB_NAME=fixed_path_dev\n")
        elsewhere = self.directory / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / ".env").write_text("DB_NAME=wrong_dev\n")
        previous = Path.cwd()
        try:
            os.chdir(elsewhere)
            self.assertEqual(config.get_settings().db_name, "fixed_path_dev")
        finally:
            os.chdir(previous)

    def test_production_ignores_local_file(self):
        self.write_local("DEBUG=true\nDB_PORT=15432\nDB_NAME=wrong_dev\nUNEXPECTED_KEY=invalid\n")
        with patch.dict(os.environ, self.production_env()):
            settings = config.get_settings()
        self.assertEqual(settings.db_name, "personal_web_prod")
        self.assertEqual(settings.db_port, 5432)
        self.assertFalse(settings.debug)

    def test_production_requires_explicit_database_fields(self):
        for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            env = self.production_env()
            del env[name]
            with self.subTest(missing=name), patch.dict(os.environ, env, clear=True):
                config.get_settings.cache_clear()
                with self.assertRaises(ValidationError):
                    config.get_settings()

    def test_production_rejects_debug_and_empty_password(self):
        for override in ({"DEBUG": "true"}, {"DB_PASSWORD": ""}, {"DB_PASSWORD": "   "}):
            with self.subTest(override=override), patch.dict(os.environ, self.production_env() | override):
                config.get_settings.cache_clear()
                with self.assertRaises(ValidationError):
                    config.get_settings()

    def test_rejects_invalid_environment_port_and_blank_identifiers(self):
        for override in ({"APP_ENV": "prodction"}, {"DB_PORT": "0"}, {"DB_PORT": "65536"},
                         {"DB_PORT": "abc"}, {"DEBUG": "perhaps"}, {"DB_NAME": "   "}):
            with self.subTest(override=override), patch.dict(os.environ, override, clear=True):
                config.get_settings.cache_clear()
                with self.assertRaises(ValidationError):
                    config.get_settings()

    def test_test_mode_does_not_load_local_credentials(self):
        self.write_local("DB_PASSWORD=test-only-private-value\nUNEXPECTED_KEY=invalid\n")
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            self.assertEqual(config.get_settings().db_password.get_secret_value(), "")

    def test_secret_is_hidden_in_representations_and_error_text(self):
        self.write_local("DB_PASSWORD=test-only-private-value\n")
        settings = config.get_settings()
        self.assertNotIn("test-only-private-value", repr(settings))
        self.assertNotIn("test-only-private-value", settings.model_dump_json())
        self.write_local("DB_PASSWORD=test-only-private-value\nDB_PORT=test-only-invalid-value\n")
        config.get_settings.cache_clear()
        with self.assertRaises(ValidationError) as caught:
            config.get_settings()
        self.assertNotIn("test-only-private-value", str(caught.exception))
        self.assertNotIn("test-only-invalid-value", str(caught.exception))

    def test_missing_local_file_keeps_existing_database_free_api_usable(self):
        settings = config.get_settings()
        self.assertEqual(settings.app_env, "development")
        self.assertFalse(settings.debug)
        self.assertEqual(settings.db_password.get_secret_value(), "")

    def test_file_cannot_silently_select_production(self):
        self.write_local("APP_ENV=production\nDB_HOST=127.0.0.1\nDB_PORT=5432\nDB_NAME=prod\nDB_USER=prod\nDB_PASSWORD=test-only-secret\n")
        with self.assertRaises(ValueError):
            config.get_settings()
