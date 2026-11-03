import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from PyQt5.QtWidgets import QApplication
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow
from enigma_timer.startup import StartupController

_APP=QApplication.instance() or QApplication([])


class WindowRestoreTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.folder.name,"data.json")
        self.windows=[]
        self.quit_policy=_APP.quitOnLastWindowClosed()

    def tearDown(self):
        for window in self.windows:
            window.close()
        _APP.processEvents()
        _APP.setQuitOnLastWindowClosed(self.quit_policy)
        self.folder.cleanup()

    def launch(self):
        store=Store(self.path)
        store.settings.update(startup_intro=False,welcome_seen=True)
        controller=StartupController(_APP,store,MainWindow)
        controller.start()
        _APP.processEvents()
        self.windows.append(controller.window)
        return controller

    def test_new_install_maximizes_and_remembers_manual_window_size(self):
        first=self.launch().window
        self.assertTrue(first.isMaximized())
        self.assertFalse(first.isFullScreen())
        first.showNormal()
        first.resize(1100,710)
        _APP.processEvents()
        size=first.size()
        first.close()
        second=self.launch().window
        self.assertFalse(second.start_maximized)
        self.assertFalse(second.isMaximized())
        if _APP.primaryScreen().availableGeometry().width()>=1200:
            self.assertEqual(second.size(),size)
        second.showMaximized()
        _APP.processEvents()
        second.close()
        third=self.launch()
        self.assertTrue(third.window.isMaximized())
        third.window.showMinimized()
        _APP.processEvents()
        third.activate()
        _APP.processEvents()
        self.assertFalse(third.window.isMinimized())
        self.assertTrue(third.window.isMaximized())

    def test_invalid_saved_geometry_falls_back_to_maximized_default(self):
        store=Store(self.path)
        store.settings["geometry"]="invalid geometry"
        store.save()
        window=self.launch().window
        self.assertTrue(window.start_maximized)
        self.assertTrue(window.isMaximized())
