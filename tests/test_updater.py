import unittest

from famdtool.updater import is_newer_version, select_update_asset, version_tuple


class UpdaterTests(unittest.TestCase):
    def test_version_tuple_ignores_v_prefix_and_suffixes(self):
        self.assertEqual(version_tuple("v1.2.3"), (1, 2, 3))
        self.assertEqual(version_tuple("1.2.3-beta"), (1, 2, 3))

    def test_is_newer_version_compares_semantic_parts(self):
        self.assertTrue(is_newer_version("1.1.0", "1.0.9"))
        self.assertTrue(is_newer_version("1.1.1", "1.1.0"))
        self.assertFalse(is_newer_version("1.1.0", "1.1.0"))
        self.assertFalse(is_newer_version("1.0.9", "1.1.0"))

    def test_select_update_asset_prefers_configured_installer_name(self):
        release = {
            "assets": [
                {
                    "name": "FAMDTool-v1.1.0-windows.zip",
                    "browser_download_url": "https://example.test/portable.zip",
                },
                {
                    "name": "FAMDTool-v1.1.0-windows-setup.exe",
                    "browser_download_url": "https://example.test/setup.exe",
                },
            ]
        }

        asset = select_update_asset(release, "1.1.0")

        self.assertIsNotNone(asset)
        self.assertEqual(asset["browser_download_url"], "https://example.test/setup.exe")


if __name__ == "__main__":
    unittest.main()
