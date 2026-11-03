import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import patch
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from enigma_timer.i18n import configured_language
from enigma_timer.storage import Store
from enigma_timer.dialogs import SettingsDialog
from enigma_timer.scramble_history import ScrambleHistory
from enigma_timer.window import MainWindow,IDLE,RUNNING,INSPECTING,STOPPED
from enigma_timer.cube import Cube

_APP=QApplication.instance() or QApplication([])


class LanguageHistoryTests(unittest.TestCase):
    def test_english_is_default_and_russian_choice_survives_restart(self):
        for settings in ({},{'language':None},{'language':''},{'language':'auto'},{'language':'uk'}):
            self.assertEqual(configured_language(settings),'en')
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'data.json')
            store=Store(path)
            self.assertEqual(store.settings['language'],'en')
            dialog=SettingsDialog(store.settings)
            self.assertEqual(dialog.cmb_lang.count(),2)
            dialog.cmb_lang.setCurrentIndex(dialog.cmb_lang.findData('ru'))
            dialog._accept()
            store.settings=dialog.settings
            store.save()
            self.assertEqual(configured_language(Store(path).settings),'ru')
            dialog.close()

    def test_back_and_forward_preserve_history_and_session_boundaries(self):
        history=ScrambleHistory(limit=3)
        self.assertEqual(history.next('a',lambda:'R'),'R')
        self.assertEqual(history.next('a',lambda:'U'),'U')
        self.assertEqual(history.previous('a'),'R')
        self.assertEqual(history.next('a',lambda:self.fail('should use forward history')),'U')
        history.next('b',lambda:'F')
        self.assertEqual(history.current('a'),'U')
        self.assertFalse(history.can_previous('b'))
        history.previous('a')
        history.next('a',lambda:'L',fresh=True)
        self.assertEqual(history.current('a'),'L')
        self.assertFalse(history.can_next('a'))
        history.next('a',lambda:'D')
        history.next('a',lambda:'B')
        history.previous('a');history.previous('a')
        self.assertEqual(history.current('a'),'L')
        self.assertFalse(history.can_previous('a'))

    def test_returning_a_scramble_updates_preview_and_blocks_during_solves(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(os.path.join(folder,'data.json'))
            store.settings['welcome_seen']=True
            main=MainWindow(store)
            try:
                initial=main.scramble
                target=set(main._ble_target_states)
                with patch('enigma_timer.window.scr.generate',return_value='R U'):
                    main.new_scramble()
                main.previous_scramble()
                self.assertEqual(main.scramble,initial)
                self.assertEqual(main.preview._grid,Cube(3).apply(initial).facelets())
                self.assertEqual(main._ble_target_states,target)
                with patch('enigma_timer.window.scr.generate',side_effect=AssertionError('new generation')):
                    main.new_scramble()
                self.assertEqual(main.scramble,'R U')
                for state in (RUNNING,INSPECTING):
                    main.state=state
                    main.previous_scramble()
                    self.assertEqual(main.scramble,'R U')
                main.state=IDLE
                main.previous_scramble()
                self.assertEqual(main.scramble,initial)
                main.new_scramble()
                main.state=STOPPED
                main.previous_scramble()
                self.assertEqual(main.state,IDLE)
                self.assertEqual(main.scramble,initial)
            finally:
                main.state=IDLE
                main.close()

    def test_update_check_is_available_from_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(os.path.join(folder,'data.json'))
            store.settings['welcome_seen']=True
            main=MainWindow(store)
            try:
                main.updater.fetch=lambda:None
                dialog=SettingsDialog(main.settings,main)
                self.assertTrue(dialog.cb_auto_update.isChecked())
                self.assertTrue(dialog.check_update.isEnabled())
                dialog.check_update.click()
                main.updater._thread.join(2)
                QTest.qWait(20)
                self.assertEqual(main.updater.state,'current')
                self.assertEqual(dialog.update_status.text(),main.updater.description())
                self.assertTrue(dialog.apply_update.isHidden())
                dialog.close()
            finally:main.close()

    def test_restart_installation_waits_for_all_timers_and_a_successful_save(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(os.path.join(folder,'data.json'))
            store.settings['welcome_seen']=True
            main=MainWindow(store)
            try:
                with patch.object(main.updater,'apply') as apply:
                    main.state=RUNNING
                    main.install_update()
                    apply.assert_not_called()
                    main.state=IDLE
                    with patch.object(main,'_mini_timer_busy',return_value=True):
                        main.install_update()
                    apply.assert_not_called()
                    with patch.object(store,'save',side_effect=OSError('disk full')),patch('enigma_timer.window.QMessageBox.warning'):
                        main.install_update()
                    apply.assert_not_called()
            finally:
                main.state=IDLE
                main.close()


if __name__=='__main__':unittest.main()
