import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk

from famdtool import main_window
from famdtool.dialogs import TimeInputFrame
from famdtool.image_preview import load_thumbnail


RUN_GUI_TESTS = os.environ.get("FAMD_RUN_GUI_TESTS") == "1"


@unittest.skipUnless(RUN_GUI_TESTS, "Set FAMD_RUN_GUI_TESTS=1 to run Tk smoke tests.")
class TkSmokeTests(unittest.TestCase):
    def make_root(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk is not available: {exc}")
        root.withdraw()
        return root

    def test_time_input_widget_accepts_keyboard_style_ampm_changes(self):
        root = self.make_root()
        try:
            frame = TimeInputFrame(root, None)
            frame.minute_var.set("75")
            frame.hour_var.set("0")

            frame.set_ampm("PM")
            frame.normalize()

            self.assertEqual(frame.hour_var.get(), "1")
            self.assertEqual(frame.minute_var.get(), "59")
            self.assertEqual(frame.ampm_var.get(), "PM")
        finally:
            root.destroy()

    def test_main_app_constructs_with_temporary_database(self):
        with TemporaryDirectory() as temp_dir:
            old_db_path = main_window.DB_PATH
            main_window.DB_PATH = Path(temp_dir) / "test.sqlite3"
            app = None
            try:
                app = main_window.FamdToolApp()
                app.withdraw()

                self.assertEqual(app.title(), "FAMD Tool ni Yeol")
                self.assertIsNotNone(app.db)
            finally:
                main_window.DB_PATH = old_db_path
                if app is not None:
                    app.on_close()

    def test_thumbnail_loader_creates_tk_image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed.")

        root = self.make_root()
        try:
            with TemporaryDirectory() as temp_dir:
                source = Path(temp_dir) / "source.png"
                Image.new("RGB", (1000, 800), "blue").save(source)

                thumbnail = load_thumbnail(source, 120, 80)

                self.assertIsNotNone(thumbnail)
                self.assertLessEqual(thumbnail.width(), 120)
                self.assertLessEqual(thumbnail.height(), 80)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
