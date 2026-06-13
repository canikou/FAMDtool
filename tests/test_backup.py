import configparser
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from famdtool.backup import (
    CONFIG_NAME,
    DATABASE_NAME,
    export_app_backup,
    import_app_backup,
    validate_backup_archive,
)
from famdtool.database import FamdDatabase


class BackupTests(unittest.TestCase):
    def test_export_backup_contains_database_config_and_manifest(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "famd_data.sqlite3"
            config_path = root / "config.cfg"
            export_dir = root / "exports"

            db = FamdDatabase(db_path)
            db.add_blank_log("response", date(2026, 6, 13), "Yeol")
            db.close()
            config_path.write_text("[app]\nversion = 1.5.1\n", encoding="utf-8")

            result = export_app_backup(db_path, config_path, export_dir)

            self.assertTrue(result.path.exists())
            self.assertEqual(result.path.parent, export_dir)
            with ZipFile(result.path, "r") as archive:
                self.assertIn(DATABASE_NAME, archive.namelist())
                self.assertIn(CONFIG_NAME, archive.namelist())
                self.assertIn("manifest.txt", archive.namelist())
                self.assertGreater(archive.getinfo(DATABASE_NAME).file_size, 0)

    def test_import_backup_replaces_database_and_config_after_validation(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_db_path = root / "source.sqlite3"
            source_config_path = root / "source.cfg"
            live_db_path = root / "live.sqlite3"
            live_config_path = root / "config.cfg"
            export_dir = root / "exports"

            source_db = FamdDatabase(source_db_path)
            source_db.add_blank_log("vital", date(2026, 6, 13), "Imported")
            source_db.close()
            source_config_path.write_text("[workflow]\nnon_detailed_logs = true\n", encoding="utf-8")
            backup = export_app_backup(source_db_path, source_config_path, export_dir)

            live_db = FamdDatabase(live_db_path)
            live_db.add_blank_log("response", date(2026, 6, 12), "Old")
            live_db.close()
            live_config_path.write_text("[workflow]\nnon_detailed_logs = false\n", encoding="utf-8")

            restore_path = import_app_backup(backup.path, live_db_path, live_config_path)

            self.assertTrue(restore_path.exists())
            imported = FamdDatabase(live_db_path)
            self.assertEqual(len(imported.list_logs_for_day("vital", date(2026, 6, 13))), 1)
            self.assertEqual(len(imported.list_logs_for_day("response", date(2026, 6, 12))), 0)
            imported.close()

            parser = configparser.ConfigParser()
            parser.read(live_config_path, encoding="utf-8")
            self.assertTrue(parser.getboolean("workflow", "non_detailed_logs"))

    def test_validate_backup_rejects_missing_required_files(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr(CONFIG_NAME, "[app]\n")

            with self.assertRaisesRegex(ValueError, "missing required"):
                validate_backup_archive(path)


if __name__ == "__main__":
    unittest.main()
