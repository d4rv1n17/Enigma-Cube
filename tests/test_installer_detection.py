"""Regression: a chosen existing app folder must offer Update without registry."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PyQt5.QtWidgets import QApplication
from installer import setup_core as core, setup_app

_APP = QApplication.instance() or QApplication([])


class InstallerDetectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.old = self.root / "games" / "Enigma Cube"
        self.old.mkdir(parents=True)
        (self.old/core.APP_EXE).write_bytes(b"old app")
        (self.old/core.MANIFEST).write_text(core.APP_EXE+"\n",encoding="utf-8")
        self.registry = patch.object(core,"_registered_installs",return_value=[])
        self.registry.start()
        self.addCleanup(self.registry.stop)
        self.addCleanup(self.folder.cleanup)

    def test_app_without_registry_or_manifest_is_still_an_update(self):
        (self.old/core.MANIFEST).unlink()
        existing=core.existing_install(str(self.old))
        self.assertEqual(Path(existing["dir"]),self.old)
        self.assertEqual(core.normalise_dir(str(self.old)),str(self.old))
        with patch.object(core,"default_install_dir",return_value=str(self.old)):
            self.assertEqual(Path(core.existing_install()["dir"]),self.old)

    def test_empty_folder_or_manifest_without_app_is_not_an_installation(self):
        (self.old/core.APP_EXE).unlink()
        self.assertIsNone(core.existing_install(str(self.old)))
        self.assertIsNone(core.existing_install(""))
        self.assertIsNone(core.existing_install(str(self.root/"empty")))

    def test_registration_from_another_folder_does_not_follow_the_target(self):
        other={"dir":str(self.root/"another-copy"),"version":"2.2","inno_uninstall":"another-copy/unins000.exe"}
        with patch.object(core,"_registered_installs",return_value=[other]):
            detected=core.existing_install(str(self.old))
        self.assertNotIn("inno_uninstall",detected)
        self.assertEqual(Path(detected["dir"]),self.old)

    def test_matching_registration_keeps_version_and_legacy_metadata(self):
        record={"dir":str(self.old),"version":"3.1","inno_uninstall":"same-copy/unins000.exe"}
        with patch.object(core,"_registered_installs",return_value=[record]):
            self.assertEqual(core.existing_install(str(self.old)),record)

    def test_setup_label_changes_when_typing_or_selecting_existing_folder(self):
        payload=self.root/"payload.zip"
        with zipfile.ZipFile(payload,"w") as archive:
            archive.writestr(core.APP_EXE,b"new app")
            archive.writestr("payload.json",json.dumps({"version":"3.2.1"}))
        original_resource=core.resource
        with patch.object(core,"resource",side_effect=lambda name: str(payload) if name=="payload.zip" else original_resource(name)):
            window=setup_app.SetupWindow(install_dir=str(self.root/"empty"))
        try:
            for language in ("en","ru"):
                window.set_lang(language)
                window.path.setText(str(self.root/"fresh"))
                self.assertEqual(window.b_main.text(),window.t("install"))
                window.path.setText(str(self.old))
                self.assertEqual(window.b_main.text(),window.t("update"))
                self.assertIn("3.2.1",window.title.text())
                self.assertIn(window.t("keeps"),window.note.text())
                window.path.setText(str(self.root/"fresh"))
                self.assertIsNone(window.existing)
                self.assertEqual(window.b_main.text(),window.t("install"))
            with patch.object(setup_app.QFileDialog,"getExistingDirectory",return_value=str(self.old)):
                window.pick_dir()
            self.assertEqual(window.b_main.text(),window.t("update"))
            self.assertEqual(Path(window.path.text()),self.old)
        finally:
            window.close()
