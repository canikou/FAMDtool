import configparser
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from famdtool import config


class ConfigTests(unittest.TestCase):
    def test_external_config_file_exists_with_runtime_options(self):
        parser = configparser.ConfigParser()
        parser.read(config.CONFIG_PATH, encoding="utf-8")

        self.assertTrue(config.CONFIG_PATH.exists())
        self.assertEqual(parser.get("app", "title"), "FAMD Tool ni Yeol")
        self.assertEqual(parser.get("app", "version"), "1.5.2")
        self.assertIn("database", parser["paths"])
        self.assertIn("icon", parser["paths"])
        self.assertIn("verbose_event_logs", parser["logging"])
        self.assertIn("non_detailed_logs", parser["workflow"])
        self.assertIn("latest_api_url", parser["updates"])
        self.assertIn("asset_pattern", parser["updates"])

    def test_config_values_are_loaded_into_constants(self):
        self.assertIsInstance(config.NON_DETAILED_LOGS, bool)
        self.assertIsInstance(config.VERBOSE_EVENT_LOGS, bool)
        self.assertEqual(config.APP_VERSION, "1.5.2")
        self.assertEqual(config.APP_VERSION, config.APP_BUILD_VERSION)
        self.assertTrue(config.ICON_PATH.name.endswith(".ico"))
        self.assertTrue(config.UPDATES_ENABLED)
        self.assertIn("{version}", config.UPDATE_ASSET_PATTERN)
        self.assertIn("ROBBERY", config.RESPONSE_TYPES)
        self.assertIn("REVIVAL", config.VITAL_TYPES)

    def test_repair_config_updates_stale_version_without_clobbering_user_settings(self):
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.cfg"
            config_path.write_text(
                "\n".join(
                    [
                        "[app]",
                        "title = FAMD Tool ni Yeol",
                        "version = 1.1.0",
                        "default_responders = Custom Responder",
                        "",
                        "[workflow]",
                        "non_detailed_logs = false",
                    ]
                ),
                encoding="utf-8",
            )

            changed = config.repair_config_file(config_path)
            changed_again = config.repair_config_file(config_path)

            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")

            self.assertTrue(changed)
            self.assertFalse(changed_again)
            self.assertEqual(parser.get("app", "version"), config.APP_BUILD_VERSION)
            self.assertEqual(parser.get("app", "default_responders"), "Custom Responder")
            self.assertFalse(parser.getboolean("workflow", "non_detailed_logs"))
            self.assertIn("latest_api_url", parser["updates"])


if __name__ == "__main__":
    unittest.main()
