import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from PyQt5.QtWidgets import QApplication, QDialog
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow
from enigma_timer.cube_sync import StateCalibration, facelets_to_state
from enigma_timer.sync_dialog import CubeSyncDialog
from enigma_timer.solver import apply_moves
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer import cube

_APP = QApplication.instance() or QApplication([])


class PhysicalStateWorkflowTests(unittest.TestCase):
    def test_unverified_state_is_blocked_and_confirmed_state_updates_all_consumers(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(os.path.join(folder, "data.json"))
            store.settings["welcome_seen"] = True
            main = MainWindow(store)
            try:
                main.settings["ble_last_address"] = "test-device"
                main.ble_profile = "clone"
                main.cube_btn.setChecked(True)
                matrix = ((0,0,1), (0,1,0), (-1,0,0))
                main._frame_perm = cube.frame_perm(matrix)
                reported = facelets_to_state(apply_moves(SOLVED_FACELETS, "R F U2"))
                main._ble_state(reported)
                self.assertFalse(main._cube_state_trusted)
                self.assertFalse(main.hub.cube_connected)
                self.assertFalse(main.ble_scramble_ready)
                dialog = CubeSyncDialog(main)
                dialog.fill_solved()
                dialog.confirm.setChecked(True)
                dialog.apply()
                self.assertEqual(dialog.result(), QDialog.Accepted)
                self.assertTrue(dialog.target.solved)
                correction = StateCalibration.between(reported, dialog.target)
                main.settings["ble_state_calibrations"] = {
                    "test-device": {"profile": "clone", "mapping": correction.to_dict()}}
                main._ble_state(reported)
                self.assertTrue(main._cube_state_trusted)
                self.assertTrue(main.ble_state.solved)
                self.assertTrue(main.hub.cube_connected)
                main.ble_profile = "std"  # another decoder must not reuse this calibration
                main._ble_state(reported)
                self.assertFalse(main._cube_state_trusted)
            finally:
                main.close()

    def test_sync_edit_rejects_a_move_during_editing(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(os.path.join(folder, "data.json"))
            store.settings["welcome_seen"] = True
            main = MainWindow(store)
            try:
                main.cube_btn.setChecked(True)
                main._ble_state(facelets_to_state(SOLVED_FACELETS))
                dialog = CubeSyncDialog(main)
                dialog.fill_solved()
                main._ble_state(facelets_to_state(apply_moves(SOLVED_FACELETS, "R")))
                dialog.apply()
                self.assertIsNone(dialog.target)
                self.assertTrue(dialog.error.text())
            finally:
                main.close()
