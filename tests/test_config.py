import configparser
import unittest

from famdtool import config


class ConfigTests(unittest.TestCase):
    def test_external_config_file_exists_with_runtime_options(self):
        parser = configparser.ConfigParser()
        parser.read(config.CONFIG_PATH, encoding="utf-8")

        self.assertTrue(config.CONFIG_PATH.exists())
        self.assertEqual(parser.get("app", "title"), "FAMD Tool ni Yeol")
        self.assertEqual(parser.get("app", "version"), "1.0.1")
        self.assertIn("database", parser["paths"])
        self.assertIn("verbose_event_logs", parser["logging"])
        self.assertIn("non_detailed_logs", parser["workflow"])

    def test_config_values_are_loaded_into_constants(self):
        self.assertIsInstance(config.NON_DETAILED_LOGS, bool)
        self.assertIsInstance(config.VERBOSE_EVENT_LOGS, bool)
        self.assertEqual(config.APP_VERSION, "1.0.1")
        self.assertIn("ROBBERY", config.RESPONSE_TYPES)
        self.assertIn("REVIVAL", config.VITAL_TYPES)


if __name__ == "__main__":
    unittest.main()
