"""Tests for development/nautobot_config.py configuration logic.

These tests verify that the development configuration file correctly reads
environment variables and constructs the expected Django/Nautobot settings.
Because nautobot_config.py uses wildcard imports from nautobot.core.settings,
each test case sets up mock nautobot modules before importing the config.
"""
import importlib
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Path to the file under test
_CONFIG_PATH = Path(__file__).parents[2] / "development" / "nautobot_config.py"


def _make_nautobot_mocks(installed_apps=None, middleware=None):
    """Build minimal mock modules that satisfy nautobot_config.py imports."""
    if installed_apps is None:
        installed_apps = []
    if middleware is None:
        middleware = []

    # Build a fake nautobot.core.settings module that exposes INSTALLED_APPS/MIDDLEWARE
    fake_settings = types.ModuleType("nautobot.core.settings")
    fake_settings.INSTALLED_APPS = list(installed_apps)
    fake_settings.MIDDLEWARE = list(middleware)

    def _is_truthy(value):
        """Minimal implementation matching nautobot's is_truthy behaviour."""
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"true", "yes", "1", "on"}

    def _parse_redis_connection(redis_database=0):
        host = os.getenv("NAUTOBOT_REDIS_HOST", "localhost")
        port = os.getenv("NAUTOBOT_REDIS_PORT", "6379")
        password = os.getenv("NAUTOBOT_REDIS_PASSWORD", "")
        if password:
            return f"redis://:{password}@{host}:{port}/{redis_database}"
        return f"redis://{host}:{port}/{redis_database}"

    fake_settings_funcs = types.ModuleType("nautobot.core.settings_funcs")
    fake_settings_funcs.is_truthy = _is_truthy
    fake_settings_funcs.parse_redis_connection = _parse_redis_connection

    fake_nautobot = types.ModuleType("nautobot")
    fake_nautobot_core = types.ModuleType("nautobot.core")

    return {
        "nautobot": fake_nautobot,
        "nautobot.core": fake_nautobot_core,
        "nautobot.core.settings": fake_settings,
        "nautobot.core.settings_funcs": fake_settings_funcs,
    }


def _load_config(env_overrides=None, installed_apps=None, middleware=None):
    """Import nautobot_config.py in an isolated namespace with mocked nautobot.

    Returns the module object so callers can inspect its attributes.
    """
    mocks = _make_nautobot_mocks(installed_apps=installed_apps, middleware=middleware)

    env_backup = {}
    env_keys_to_clear = [
        "NAUTOBOT_DEBUG",
        "NAUTOBOT_ALLOWED_HOSTS",
        "NAUTOBOT_SECRET_KEY",
        "NAUTOBOT_DB_ENGINE",
        "NAUTOBOT_DB_NAME",
        "NAUTOBOT_DB_USER",
        "NAUTOBOT_DB_PASSWORD",
        "NAUTOBOT_DB_HOST",
        "NAUTOBOT_DB_PORT",
        "NAUTOBOT_DB_TIMEOUT",
        "NAUTOBOT_REDIS_HOST",
        "NAUTOBOT_REDIS_PORT",
        "NAUTOBOT_REDIS_PASSWORD",
    ]
    # Save originals and clear them first
    for key in env_keys_to_clear:
        env_backup[key] = os.environ.pop(key, None)

    if env_overrides:
        for key, value in env_overrides.items():
            os.environ[key] = value

    # Patch sys.modules with our fakes
    original_modules = {k: sys.modules.get(k) for k in mocks}
    sys.modules.update(mocks)

    # Also make the wildcard import from nautobot.core.settings work by
    # populating __dict__ of the fake settings module with the attributes
    # that nautobot_config.py uses after the wildcard import.
    settings_mod = mocks["nautobot.core.settings"]
    # Expose these names at module level so "from ... import *" picks them up
    settings_mod.__all__ = ["INSTALLED_APPS", "MIDDLEWARE"]

    try:
        spec = importlib.util.spec_from_file_location("nautobot_config_test", _CONFIG_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        # Restore sys.modules
        for k, orig in original_modules.items():
            if orig is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = orig
        # Restore env
        for key, orig_value in env_backup.items():
            if orig_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = orig_value
        if env_overrides:
            for key in env_overrides:
                os.environ.pop(key, None)


class TestDebugMode(unittest.TestCase):
    """Tests for DEBUG and _TESTING detection."""

    def test_debug_false_by_default(self):
        """DEBUG should be False when NAUTOBOT_DEBUG is not set."""
        cfg = _load_config()
        self.assertFalse(cfg.DEBUG)

    def test_debug_true_when_env_is_true(self):
        """DEBUG should be True when NAUTOBOT_DEBUG=True."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertTrue(cfg.DEBUG)

    def test_debug_true_when_env_is_1(self):
        """DEBUG should be True when NAUTOBOT_DEBUG=1."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "1"})
        self.assertTrue(cfg.DEBUG)

    def test_debug_false_when_env_is_false(self):
        """DEBUG should be False when NAUTOBOT_DEBUG=False."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "False"})
        self.assertFalse(cfg.DEBUG)

    def test_debug_false_when_env_is_0(self):
        """DEBUG should be False when NAUTOBOT_DEBUG=0."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "0"})
        self.assertFalse(cfg.DEBUG)

    def test_testing_detection_when_argv_is_test(self):
        """_TESTING should be True when sys.argv[1] == 'test'."""
        with patch.object(sys, "argv", ["manage.py", "test"]):
            cfg = _load_config()
        self.assertTrue(cfg._TESTING)

    def test_testing_detection_false_when_argv_is_not_test(self):
        """_TESTING should be False when sys.argv[1] != 'test'."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertFalse(cfg._TESTING)

    def test_testing_detection_false_when_argv_is_empty(self):
        """_TESTING should be False when sys.argv has only one element."""
        with patch.object(sys, "argv", ["manage.py"]):
            cfg = _load_config()
        self.assertFalse(cfg._TESTING)


class TestDebugToolbar(unittest.TestCase):
    """Tests for conditional debug toolbar injection."""

    def test_debug_toolbar_not_added_when_debug_is_false(self):
        """debug_toolbar should not be added to INSTALLED_APPS when DEBUG=False."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "False"})
        self.assertNotIn("debug_toolbar", cfg.INSTALLED_APPS)
        self.assertFalse(hasattr(cfg, "DEBUG_TOOLBAR_CONFIG"))

    def test_debug_toolbar_not_added_during_testing(self):
        """debug_toolbar should not be added during test runs even if DEBUG=True."""
        with patch.object(sys, "argv", ["manage.py", "test"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertNotIn("debug_toolbar", cfg.INSTALLED_APPS)

    def test_debug_toolbar_added_when_debug_is_true(self):
        """debug_toolbar should be added to INSTALLED_APPS when DEBUG=True and not testing."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertIn("debug_toolbar", cfg.INSTALLED_APPS)

    def test_debug_toolbar_middleware_added_when_debug_is_true(self):
        """DebugToolbarMiddleware should be prepended to MIDDLEWARE when DEBUG=True."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertIn("debug_toolbar.middleware.DebugToolbarMiddleware", cfg.MIDDLEWARE)
        self.assertEqual(cfg.MIDDLEWARE[0], "debug_toolbar.middleware.DebugToolbarMiddleware")

    def test_debug_toolbar_not_duplicated_when_already_present(self):
        """debug_toolbar should not be added twice if it is already in INSTALLED_APPS."""
        existing_apps = ["debug_toolbar"]
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(
                env_overrides={"NAUTOBOT_DEBUG": "True"},
                installed_apps=existing_apps,
            )
        count = cfg.INSTALLED_APPS.count("debug_toolbar")
        self.assertEqual(count, 1)

    def test_debug_toolbar_middleware_not_duplicated_when_already_present(self):
        """DebugToolbarMiddleware should not be added twice if already in MIDDLEWARE."""
        existing_middleware = ["debug_toolbar.middleware.DebugToolbarMiddleware"]
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(
                env_overrides={"NAUTOBOT_DEBUG": "True"},
                middleware=existing_middleware,
            )
        count = cfg.MIDDLEWARE.count("debug_toolbar.middleware.DebugToolbarMiddleware")
        self.assertEqual(count, 1)

    def test_debug_toolbar_config_set_when_debug_is_true(self):
        """DEBUG_TOOLBAR_CONFIG should be set when DEBUG=True and not testing."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertTrue(hasattr(cfg, "DEBUG_TOOLBAR_CONFIG"))
        self.assertIn("SHOW_TOOLBAR_CALLBACK", cfg.DEBUG_TOOLBAR_CONFIG)
        self.assertTrue(cfg.DEBUG_TOOLBAR_CONFIG["SHOW_TOOLBAR_CALLBACK"](None))


class TestAllowedHosts(unittest.TestCase):
    """Tests for ALLOWED_HOSTS configuration."""

    def test_allowed_hosts_empty_by_default(self):
        """ALLOWED_HOSTS should contain [''] when env var is not set (split of empty string)."""
        cfg = _load_config()
        self.assertEqual(cfg.ALLOWED_HOSTS, [""])

    def test_allowed_hosts_single_value(self):
        """ALLOWED_HOSTS should correctly parse a single hostname."""
        cfg = _load_config(env_overrides={"NAUTOBOT_ALLOWED_HOSTS": "localhost"})
        self.assertEqual(cfg.ALLOWED_HOSTS, ["localhost"])

    def test_allowed_hosts_multiple_values(self):
        """ALLOWED_HOSTS should correctly parse space-separated hostnames."""
        cfg = _load_config(env_overrides={"NAUTOBOT_ALLOWED_HOSTS": "localhost 127.0.0.1"})
        self.assertEqual(cfg.ALLOWED_HOSTS, ["localhost", "127.0.0.1"])

    def test_allowed_hosts_wildcard(self):
        """ALLOWED_HOSTS should support wildcard '*' value."""
        cfg = _load_config(env_overrides={"NAUTOBOT_ALLOWED_HOSTS": "*"})
        self.assertEqual(cfg.ALLOWED_HOSTS, ["*"])


class TestSecretKey(unittest.TestCase):
    """Tests for SECRET_KEY configuration."""

    def test_secret_key_empty_by_default(self):
        """SECRET_KEY should be empty string when env var is not set."""
        cfg = _load_config()
        self.assertEqual(cfg.SECRET_KEY, "")

    def test_secret_key_from_env(self):
        """SECRET_KEY should reflect the NAUTOBOT_SECRET_KEY env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_SECRET_KEY": "supersecretkey123"})
        self.assertEqual(cfg.SECRET_KEY, "supersecretkey123")


class TestDatabaseConfiguration(unittest.TestCase):
    """Tests for DATABASES configuration."""

    def test_default_engine_is_postgresql(self):
        """Default DB engine should be django.db.backends.postgresql."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")

    def test_mysql_engine_from_env(self):
        """DB engine should be mysql when NAUTOBOT_DB_ENGINE=django.db.backends.mysql."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_ENGINE": "django.db.backends.mysql"})
        self.assertEqual(cfg.DATABASES["default"]["ENGINE"], "django.db.backends.mysql")

    def test_default_postgresql_port_is_5432(self):
        """Default port for postgresql should be 5432."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["PORT"], "5432")

    def test_default_mysql_port_is_3306(self):
        """Default port for MySQL should be 3306."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_ENGINE": "django.db.backends.mysql"})
        self.assertEqual(cfg.DATABASES["default"]["PORT"], "3306")

    def test_db_port_override_via_env(self):
        """NAUTOBOT_DB_PORT env var should override the default port."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_PORT": "9999"})
        self.assertEqual(cfg.DATABASES["default"]["PORT"], "9999")

    def test_default_db_name_is_nautobot(self):
        """Default DB name should be 'nautobot'."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["NAME"], "nautobot")

    def test_db_name_from_env(self):
        """DB name should come from NAUTOBOT_DB_NAME env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_NAME": "mydb"})
        self.assertEqual(cfg.DATABASES["default"]["NAME"], "mydb")

    def test_default_db_user_is_empty(self):
        """Default DB user should be empty string."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["USER"], "")

    def test_db_user_from_env(self):
        """DB user should come from NAUTOBOT_DB_USER env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_USER": "nautobot_user"})
        self.assertEqual(cfg.DATABASES["default"]["USER"], "nautobot_user")

    def test_default_db_password_is_empty(self):
        """Default DB password should be empty string."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["PASSWORD"], "")

    def test_db_password_from_env(self):
        """DB password should come from NAUTOBOT_DB_PASSWORD env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_PASSWORD": "s3cr3t"})
        self.assertEqual(cfg.DATABASES["default"]["PASSWORD"], "s3cr3t")

    def test_default_db_host_is_localhost(self):
        """Default DB host should be 'localhost'."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["HOST"], "localhost")

    def test_db_host_from_env(self):
        """DB host should come from NAUTOBOT_DB_HOST env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_HOST": "db.example.com"})
        self.assertEqual(cfg.DATABASES["default"]["HOST"], "db.example.com")

    def test_default_conn_max_age_is_300(self):
        """Default CONN_MAX_AGE should be 300 (integer)."""
        cfg = _load_config()
        self.assertEqual(cfg.DATABASES["default"]["CONN_MAX_AGE"], 300)

    def test_conn_max_age_from_env(self):
        """CONN_MAX_AGE should come from NAUTOBOT_DB_TIMEOUT env var as integer."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_TIMEOUT": "600"})
        self.assertEqual(cfg.DATABASES["default"]["CONN_MAX_AGE"], 600)
        self.assertIsInstance(cfg.DATABASES["default"]["CONN_MAX_AGE"], int)


class TestMysqlCharsetOption(unittest.TestCase):
    """Tests for MySQL OPTIONS charset injection."""

    def test_mysql_options_charset_set(self):
        """DATABASES default OPTIONS should have charset=utf8mb4 for MySQL engine."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_ENGINE": "django.db.backends.mysql"})
        self.assertIn("OPTIONS", cfg.DATABASES["default"])
        self.assertEqual(cfg.DATABASES["default"]["OPTIONS"]["charset"], "utf8mb4")

    def test_postgresql_does_not_have_charset_options(self):
        """DATABASES default OPTIONS should NOT be injected for PostgreSQL engine."""
        cfg = _load_config()
        self.assertNotIn("OPTIONS", cfg.DATABASES["default"])

    def test_mysql_charset_is_utf8mb4(self):
        """The MySQL charset must specifically be utf8mb4 for full Unicode support."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_ENGINE": "django.db.backends.mysql"})
        self.assertEqual(cfg.DATABASES["default"]["OPTIONS"]["charset"], "utf8mb4")


class TestCachesConfiguration(unittest.TestCase):
    """Tests for CACHES and CACHEOPS_REDIS configuration."""

    def test_caches_default_backend(self):
        """CACHES default backend should be django_redis.cache.RedisCache."""
        cfg = _load_config()
        self.assertEqual(cfg.CACHES["default"]["BACKEND"], "django_redis.cache.RedisCache")

    def test_caches_default_timeout(self):
        """CACHES default TIMEOUT should be 300."""
        cfg = _load_config()
        self.assertEqual(cfg.CACHES["default"]["TIMEOUT"], 300)

    def test_caches_default_client_class(self):
        """CACHES default CLIENT_CLASS should be django_redis.client.DefaultClient."""
        cfg = _load_config()
        self.assertEqual(
            cfg.CACHES["default"]["OPTIONS"]["CLIENT_CLASS"],
            "django_redis.client.DefaultClient",
        )

    def test_caches_default_location_is_string(self):
        """CACHES default LOCATION should be a non-empty string (Redis URL)."""
        cfg = _load_config()
        self.assertIsInstance(cfg.CACHES["default"]["LOCATION"], str)
        self.assertTrue(len(cfg.CACHES["default"]["LOCATION"]) > 0)

    def test_caches_location_uses_database_0(self):
        """CACHES LOCATION should reference Redis database 0."""
        cfg = _load_config()
        location = cfg.CACHES["default"]["LOCATION"]
        self.assertTrue(location.endswith("/0"), f"Expected Redis DB 0, got: {location}")

    def test_cacheops_redis_uses_database_1(self):
        """CACHEOPS_REDIS should reference Redis database 1."""
        cfg = _load_config()
        self.assertIsInstance(cfg.CACHEOPS_REDIS, str)
        self.assertTrue(
            cfg.CACHEOPS_REDIS.endswith("/1"),
            f"Expected Redis DB 1, got: {cfg.CACHEOPS_REDIS}",
        )

    def test_caches_and_cacheops_use_different_databases(self):
        """CACHES and CACHEOPS_REDIS should point to different Redis databases."""
        cfg = _load_config()
        self.assertNotEqual(cfg.CACHES["default"]["LOCATION"], cfg.CACHEOPS_REDIS)

    def test_redis_host_from_env(self):
        """Redis host should be picked up from NAUTOBOT_REDIS_HOST env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_REDIS_HOST": "myredis.example.com"})
        self.assertIn("myredis.example.com", cfg.CACHES["default"]["LOCATION"])
        self.assertIn("myredis.example.com", cfg.CACHEOPS_REDIS)

    def test_redis_port_from_env(self):
        """Redis port should be picked up from NAUTOBOT_REDIS_PORT env var."""
        cfg = _load_config(env_overrides={"NAUTOBOT_REDIS_PORT": "6380"})
        self.assertIn("6380", cfg.CACHES["default"]["LOCATION"])

    def test_redis_password_included_in_url_when_set(self):
        """Redis password should appear in the connection URL when NAUTOBOT_REDIS_PASSWORD is set."""
        cfg = _load_config(env_overrides={"NAUTOBOT_REDIS_PASSWORD": "r3d1spass"})
        self.assertIn("r3d1spass", cfg.CACHES["default"]["LOCATION"])


class TestLoggingConfiguration(unittest.TestCase):
    """Tests for LOGGING configuration."""

    def test_logging_defined_when_not_testing(self):
        """LOGGING dict should be set when not in test mode."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertTrue(hasattr(cfg, "LOGGING"))
        self.assertIsInstance(cfg.LOGGING, dict)

    def test_logging_not_defined_when_testing(self):
        """LOGGING dict should NOT be set during test runs (quiet test output)."""
        with patch.object(sys, "argv", ["manage.py", "test"]):
            cfg = _load_config()
        self.assertFalse(hasattr(cfg, "LOGGING"))

    def test_log_level_is_info_when_debug_is_false(self):
        """LOG_LEVEL should be 'INFO' when DEBUG=False."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "False"})
        self.assertEqual(cfg.LOG_LEVEL, "INFO")

    def test_log_level_is_debug_when_debug_is_true(self):
        """LOG_LEVEL should be 'DEBUG' when DEBUG=True."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        self.assertEqual(cfg.LOG_LEVEL, "DEBUG")

    def test_logging_has_required_keys(self):
        """LOGGING dict should contain version, formatters, handlers, and loggers."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        for key in ("version", "formatters", "handlers", "loggers"):
            self.assertIn(key, cfg.LOGGING, f"Missing key '{key}' in LOGGING")

    def test_logging_version_is_1(self):
        """LOGGING version should be 1 (dictConfig format)."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertEqual(cfg.LOGGING["version"], 1)

    def test_logging_disable_existing_loggers_is_false(self):
        """LOGGING should not disable existing loggers."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertFalse(cfg.LOGGING["disable_existing_loggers"])

    def test_logging_normal_formatter_present(self):
        """LOGGING should define a 'normal' formatter."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertIn("normal", cfg.LOGGING["formatters"])

    def test_logging_verbose_formatter_present(self):
        """LOGGING should define a 'verbose' formatter."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertIn("verbose", cfg.LOGGING["formatters"])

    def test_logging_nautobot_handler_uses_verbose_when_debug(self):
        """Nautobot logger should use verbose_console handler when DEBUG=True."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "True"})
        nautobot_handlers = cfg.LOGGING["loggers"]["nautobot"]["handlers"]
        self.assertIn("verbose_console", nautobot_handlers)

    def test_logging_nautobot_handler_uses_normal_when_not_debug(self):
        """Nautobot logger should use normal_console handler when DEBUG=False."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "False"})
        nautobot_handlers = cfg.LOGGING["loggers"]["nautobot"]["handlers"]
        self.assertIn("normal_console", nautobot_handlers)

    def test_logging_django_logger_uses_normal_console(self):
        """Django logger should always use normal_console handler."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config()
        self.assertIn("normal_console", cfg.LOGGING["loggers"]["django"]["handlers"])


class TestPluginsConfiguration(unittest.TestCase):
    """Tests for PLUGINS setting."""

    def test_plugins_contains_nautobot_topology_views(self):
        """PLUGINS list must include 'nautobot_topology_views'."""
        cfg = _load_config()
        self.assertIn("nautobot_topology_views", cfg.PLUGINS)

    def test_plugins_is_a_list(self):
        """PLUGINS must be a list."""
        cfg = _load_config()
        self.assertIsInstance(cfg.PLUGINS, list)


class TestDefaultDbSettingsMapping(unittest.TestCase):
    """Tests for the default_db_settings port mapping dictionary."""

    def test_default_db_settings_has_postgresql_key(self):
        """default_db_settings should include a key for postgresql engine."""
        cfg = _load_config()
        self.assertIn("django.db.backends.postgresql", cfg.default_db_settings)

    def test_default_db_settings_has_mysql_key(self):
        """default_db_settings should include a key for mysql engine."""
        cfg = _load_config()
        self.assertIn("django.db.backends.mysql", cfg.default_db_settings)

    def test_postgresql_default_port_in_mapping(self):
        """default_db_settings postgresql entry should map NAUTOBOT_DB_PORT to '5432'."""
        cfg = _load_config()
        self.assertEqual(
            cfg.default_db_settings["django.db.backends.postgresql"]["NAUTOBOT_DB_PORT"],
            "5432",
        )

    def test_mysql_default_port_in_mapping(self):
        """default_db_settings mysql entry should map NAUTOBOT_DB_PORT to '3306'."""
        cfg = _load_config()
        self.assertEqual(
            cfg.default_db_settings["django.db.backends.mysql"]["NAUTOBOT_DB_PORT"],
            "3306",
        )


class TestBoundaryAndRegressionCases(unittest.TestCase):
    """Boundary, negative, and regression tests."""

    def test_conn_max_age_zero(self):
        """CONN_MAX_AGE of 0 disables persistent connections and should parse correctly."""
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_TIMEOUT": "0"})
        self.assertEqual(cfg.DATABASES["default"]["CONN_MAX_AGE"], 0)
        self.assertIsInstance(cfg.DATABASES["default"]["CONN_MAX_AGE"], int)

    def test_debug_toolbar_not_added_when_debug_false_and_not_testing(self):
        """Regression: debug_toolbar must NOT appear even in non-test runserver if DEBUG=False."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(env_overrides={"NAUTOBOT_DEBUG": "False"})
        self.assertNotIn("debug_toolbar", cfg.INSTALLED_APPS)

    def test_allowed_hosts_with_three_entries(self):
        """ALLOWED_HOSTS should handle three space-separated entries correctly."""
        cfg = _load_config(
            env_overrides={"NAUTOBOT_ALLOWED_HOSTS": "host1 host2 host3"}
        )
        self.assertEqual(cfg.ALLOWED_HOSTS, ["host1", "host2", "host3"])

    def test_db_password_with_special_characters(self):
        """DB password containing special characters should not be altered."""
        special_pw = "p@$$w0rd!#&"
        cfg = _load_config(env_overrides={"NAUTOBOT_DB_PASSWORD": special_pw})
        self.assertEqual(cfg.DATABASES["default"]["PASSWORD"], special_pw)

    def test_mysql_and_debug_mode_simultaneously(self):
        """MySQL charset option and DEBUG mode should both work at the same time."""
        with patch.object(sys, "argv", ["manage.py", "runserver"]):
            cfg = _load_config(
                env_overrides={
                    "NAUTOBOT_DB_ENGINE": "django.db.backends.mysql",
                    "NAUTOBOT_DEBUG": "True",
                }
            )
        self.assertEqual(cfg.DATABASES["default"]["OPTIONS"]["charset"], "utf8mb4")
        self.assertTrue(cfg.DEBUG)
        self.assertIn("debug_toolbar", cfg.INSTALLED_APPS)

    def test_secret_key_with_spaces(self):
        """SECRET_KEY containing spaces should be preserved exactly."""
        key_with_spaces = "key with spaces in it"
        cfg = _load_config(env_overrides={"NAUTOBOT_SECRET_KEY": key_with_spaces})
        self.assertEqual(cfg.SECRET_KEY, key_with_spaces)

    def test_caches_structure_has_default_key(self):
        """CACHES must have a 'default' key required by Django."""
        cfg = _load_config()
        self.assertIn("default", cfg.CACHES)

    def test_databases_structure_has_default_key(self):
        """DATABASES must have a 'default' key required by Django."""
        cfg = _load_config()
        self.assertIn("default", cfg.DATABASES)


if __name__ == "__main__":
    unittest.main()