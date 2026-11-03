"""Regression checks for status messages during ongoing BLE discovery."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QListWidget, QPushButton
from enigma_timer.window import BleScanDialog

_APP = QApplication.instance() or QApplication([])


class ConnectionStatusTests(unittest.TestCase):
    def dialog(self, status, connecting=None, error=False):
        dialog = BleScanDialog.__new__(BleScanDialog)
        QDialog.__init__(dialog)
        dialog.status = QLabel(status)
        dialog.list = QListWidget()
        dialog.connect_btn = QPushButton()
        dialog._connecting_address = connecting
        dialog._error_visible = error
        return dialog

    def test_other_device_cannot_hide_connection_error(self):
        dialog = self.dialog("Connection failed: test", error=True)
        dialog.add_device("Other BLE device", "00:11:22:33:44:55", False)
        self.assertEqual(dialog.list.count(), 0)
        self.assertEqual(dialog.status.text(), "Connection failed: test")
        self.assertTrue(dialog._error_visible)

    def test_discovered_cube_cannot_replace_connecting_status(self):
        dialog = self.dialog("Connecting…", connecting="00:11:22:33:44:55")
        dialog.add_device("Gi157084", "00:11:22:33:44:55", True)
        self.assertEqual(dialog.status.text(), "Connecting…")
        self.assertFalse(dialog.connect_btn.isEnabled())
