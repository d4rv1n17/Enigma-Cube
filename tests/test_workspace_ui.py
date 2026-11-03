import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow
from enigma_timer.dialogs import SettingsDialog
from enigma_timer.commands import CommandPalette
from enigma_timer.windows import LiveCubeWindow
from enigma_timer.widgets import LiveCube3DWidget
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer.solver import apply_moves
from enigma_timer.brand import app_icon

_APP = QApplication.instance() or QApplication([])


class WorkspaceUiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.folder.name, "data.json"))
        self.store.settings["welcome_seen"] = True
        self.main = MainWindow(self.store)

    def tearDown(self):
        self.main.close()
        _APP.setProperty("reduceMotion", False)
        self.folder.cleanup()

    def test_dialog_has_no_unused_question_button(self):
        dialog = SettingsDialog(self.store.settings, self.main)
        dialog.ensurePolished()
        self.assertFalse(dialog.windowFlags() & Qt.WindowContextHelpButtonHint)
        self.assertFalse(dialog.windowIcon().isNull())

    def test_settings_are_staged_until_saved(self):
        dialog = SettingsDialog(self.store.settings, self.main)
        self.assertEqual(dialog.tabs.count(), 4)
        dialog.cb_insp.setChecked(True)
        dialog.cb_reduce_motion.setChecked(True)
        self.assertFalse(self.store.settings["inspection"])
        dialog._accept()
        self.assertTrue(dialog.settings["inspection"])
        self.assertTrue(dialog.settings["reduce_motion"])
        self.assertFalse(self.store.settings["inspection"])

    def test_reset_defaults_can_be_cancelled(self):
        self.store.settings["inspection"] = True
        dialog = SettingsDialog(self.store.settings, self.main)
        dialog._reset_defaults()
        self.assertFalse(dialog.cb_insp.isChecked())
        dialog.reject()
        self.assertTrue(self.store.settings["inspection"])

    def test_action_search_filters_without_executing(self):
        palette = CommandPalette(self.main)
        palette.filter("3D")
        self.assertEqual(palette.results.count(), 1)
        palette.filter("this action does not exist")
        self.assertEqual(palette.results.count(), 0)
        palette.execute()
        self.assertEqual(self.main.page, 0)

    def test_detached_cube_remembers_its_size(self):
        window = LiveCubeWindow(self.main)
        window.resize(740, 720)
        window.show()
        _APP.processEvents()
        size = window.size()
        window.close()
        reopened = LiveCubeWindow(self.main)
        reopened.show()
        _APP.processEvents()
        self.assertEqual(reopened.size(), size)
        reopened.close()

    def test_reduced_motion_skips_turn_animation(self):
        view = LiveCube3DWidget()
        view.set_state(SOLVED_FACELETS)
        view.show()
        _APP.setProperty("reduceMotion", True)
        view.set_state(apply_moves(SOLVED_FACELETS, "R"))
        self.assertIsNone(view._turn)
        self.assertFalse(view._turn_timer.isActive())
        view.close()

    def test_brand_has_native_small_icon_sizes(self):
        icon = app_icon()
        for size in (16, 24, 32, 64):
            self.assertFalse(icon.pixmap(size, size).isNull())

    def test_move_playback_closes_with_the_main_workspace(self):
        from enigma_timer.training import LessonBrowser
        browser = LessonBrowser(self.main)
        browser.open_demo(QUrl("demo:333:R"))
        demo = browser._demos[0]
        self.assertIn(demo, self.main.extra_windows)
        self.main.close()
        self.assertFalse(demo.isVisible())
