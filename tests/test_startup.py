import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PyQt5.QtCore import QObject,pyqtSignal,Qt
from PyQt5.QtGui import QImage,QPainter
from PyQt5.QtWidgets import QApplication,QWidget,QPushButton
from PyQt5.QtTest import QTest
from enigma_timer.startup import StartupIntro,StartupController
from enigma_timer.instance import AppInstance
from enigma_timer.dialogs import SettingsDialog
from enigma_timer.storage import Store,DEFAULT_SETTINGS
from enigma_timer import i18n

_APP=QApplication.instance() or QApplication([])


class FakeIntro(QObject):
    finished=pyqtSignal()
    cancelled=pyqtSignal()

    def __init__(self,reduced_motion=False):
        super().__init__()
        self.reduced_motion=reduced_motion
        self.starts=0

    def start(self):
        self.starts+=1


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.quit_policy=_APP.quitOnLastWindowClosed()
        self.windows=[]
        self.language=i18n.lang()

    def tearDown(self):
        for window in self.windows:
            window.close()
        _APP.setQuitOnLastWindowClosed(self.quit_policy)
        _APP.setProperty("reduceMotion",False)
        i18n.set_language(self.language)

    def factory(self,store):
        window=QWidget()
        self.windows.append(window)
        return window

    def test_one_intro_per_controller_and_welcome_workspace_waits(self):
        store=SimpleNamespace(settings={"startup_intro":True})
        controller=StartupController(_APP,store,self.factory,FakeIntro)
        controller.start()
        controller.start()
        self.assertEqual(controller.intro.starts,1)
        self.assertIsNone(controller.window)
        controller.intro.finished.emit()
        controller.intro.finished.emit()
        self.assertEqual(len(self.windows),1)
        controller.window.hide()
        controller.activate()
        self.assertTrue(controller.window.isVisible())
        self.assertEqual(controller.intro.starts,1)

    def test_disabled_intro_opens_workspace_directly(self):
        controller=StartupController(_APP,SimpleNamespace(settings={"startup_intro":False}),self.factory,FakeIntro)
        controller.start()
        self.assertIsNone(controller.intro)
        self.assertTrue(controller.window.isVisible())

    def test_reduced_motion_is_forwarded_and_stays_under_five_seconds(self):
        controller=StartupController(_APP,SimpleNamespace(settings={"reduce_motion":True}),self.factory,FakeIntro)
        controller.start()
        self.assertTrue(controller.intro.reduced_motion)
        self.assertLessEqual(StartupIntro.DURATION_MS,5000)
        self.assertLess(StartupIntro.REDUCED_DURATION_MS,StartupIntro.DURATION_MS)

    def test_completion_fires_once_and_stops_both_timers(self):
        intro=StartupIntro()
        completed=[]
        cancelled=[]
        intro.finished.connect(lambda:completed.append(True))
        intro.cancelled.connect(lambda:cancelled.append(True))
        intro.start()
        intro.start()
        self.assertTrue(intro._frames.isActive())
        intro.finish()
        intro.finish()
        self.assertEqual(completed,[True])
        self.assertFalse(cancelled)
        self.assertFalse(intro._frames.isActive())
        self.assertFalse(intro._deadline.isActive())

    def test_mouse_and_keys_cannot_skip_the_intro(self):
        intro=StartupIntro()
        completed=[]
        intro.finished.connect(lambda:completed.append(True))
        intro.start()
        self.assertFalse(intro.findChildren(QPushButton))
        for button in (Qt.LeftButton,Qt.RightButton):
            QTest.mouseClick(intro,button)
        for key in (Qt.Key_Return,Qt.Key_Space,Qt.Key_Escape,Qt.Key_Tab,Qt.Key_A):
            QTest.keyClick(intro,key)
        self.assertFalse(completed)
        self.assertFalse(intro._done)
        self.assertTrue(intro.isVisible())
        self.assertTrue(intro._deadline.isActive())
        intro.finish()

    def test_caption_and_title_follow_the_interface_language(self):
        for language,title,caption in (("en","Starting","Precision in every move."),("ru","Запуск","Точность в каждом движении.")):
            i18n.set_language(language)
            intro=StartupIntro()
            self.assertIn(title,intro.windowTitle())
            self.assertEqual(intro.tagline,caption)
            intro._done=True
            intro.close()

    def test_close_cancels_launch_instead_of_opening_workspace(self):
        intro=StartupIntro()
        completed=[]
        cancelled=[]
        intro.finished.connect(lambda:completed.append(True))
        intro.cancelled.connect(lambda:cancelled.append(True))
        intro.start()
        intro.close()
        self.assertFalse(completed)
        self.assertEqual(cancelled,[True])
        self.assertFalse(intro._frames.isActive())

    def test_alt_f4_cancels_instead_of_skipping_into_the_app(self):
        intro=StartupIntro()
        completed=[]
        cancelled=[]
        intro.finished.connect(lambda:completed.append(True))
        intro.cancelled.connect(lambda:cancelled.append(True))
        intro.start()
        QTest.keyClick(intro,Qt.Key_F4,Qt.AltModifier)
        self.assertFalse(completed)
        self.assertEqual(cancelled,[True])

    def test_time_based_deadline_does_not_depend_on_frame_count(self):
        intro=StartupIntro()
        intro.start()
        with patch.object(intro,"_clock",SimpleNamespace(elapsed=lambda:intro.duration_ms+1000)):
            intro._tick()
        self.assertTrue(intro._done)
        self.assertFalse(intro.isVisible())

    def test_frames_render_with_and_without_motion(self):
        for reduced in (False,True):
            intro=StartupIntro(reduced_motion=reduced)
            for ms in (0,500,1000,1800,2600,3500):
                image=QImage(800,500,QImage.Format_ARGB32_Premultiplied)
                image.fill(Qt.transparent)
                painter=QPainter(image)
                intro.paint_frame(painter,ms)
                painter.end()
                self.assertGreater(image.pixelColor(400,200).alpha(),0)
            intro._done=True
            intro.close()

    def test_setting_is_staged_and_persists_across_launches(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"data.json")
            store=Store(path)
            self.assertTrue(store.settings["startup_intro"])
            dialog=SettingsDialog(store.settings)
            dialog.cb_startup_intro.setChecked(False)
            dialog.reject()
            self.assertTrue(store.settings["startup_intro"])
            accepted=SettingsDialog(store.settings)
            accepted.cb_startup_intro.setChecked(False)
            accepted._accept()
            store.settings=accepted.settings
            store.save()
            self.assertFalse(Store(path).settings["startup_intro"])
            accepted._reset_defaults()
            self.assertTrue(accepted.cb_startup_intro.isChecked())

    def test_second_instance_notifies_primary_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"data.json")
            first,second=AppInstance(path),AppInstance(path)
            activated=[]
            first.activated.connect(lambda:activated.append(True))
            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                QTest.qWait(80)
                self.assertEqual(activated,[True])
                self.assertTrue(first.primary)
            finally:
                second.close()
                first.close()
            third=AppInstance(path)
            try:
                self.assertTrue(third.acquire())
            finally:
                third.close()

    def test_cold_start_recovers_after_a_process_exits_without_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"data.json")
            script="import os,sys; from PyQt5.QtCore import QCoreApplication; from enigma_timer.instance import AppInstance; app=QCoreApplication([]); guard=AppInstance(sys.argv[1]); assert guard.acquire(); os._exit(0)"
            subprocess.run([sys.executable,"-c",script,path],cwd=str(Path(__file__).resolve().parent.parent),
                           check=True,timeout=10,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            recovered=AppInstance(path)
            try:
                self.assertTrue(recovered.acquire())
            finally:
                recovered.close()


if __name__=="__main__":
    unittest.main()
