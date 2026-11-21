#!/usr/bin/env python3
"""Enigma Cube - a speedcubing timer.

Run:  python main.py
"""

import os
import sys

from PyQt5.QtCore import QLocale, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication,QMessageBox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from enigma_timer import i18n, theme  # noqa: E402
from enigma_timer.storage import Store,data_dir  # noqa: E402


def safe_exit_setup():
    """Don't run C++ destructors at interpreter exit (PyQt's recommended fix for
    crashes on exit when Qt objects outlive the QApplication)."""
    try:
        from PyQt5 import sip
    except ImportError:  # very old PyQt5
        try:
            import sip
        except ImportError:
            return
    sip.setdestroyonexit(False)


def finish(code):
    """Leave the process without running DLL teardown on Windows.

    All data is saved before we get here. Qt windows that are still alive
    when Windows unloads the DLLs can crash in the text-input framework
    during ExitProcess (a random access violation after a clean exit), so
    the process is ended directly once everything is flushed.
    """
    for f in (sys.stdout, sys.stderr):
        try:
            f.flush()
        except Exception:  # noqa: BLE001 - stdout may be missing in a GUI exe
            pass
    if sys.platform.startswith("win"):
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.TerminateProcess(k.GetCurrentProcess(), int(code) & 0xFFFFFFFF)
        except Exception:  # noqa: BLE001 - fall back to a normal exit
            pass
    sys.exit(code)


def main():
    if "--solver-worker" in sys.argv:
        from enigma_timer.solver import worker
        index = sys.argv.index("--solver-worker")
        worker(sys.argv[index + 1], sys.argv[index + 2] if len(sys.argv) > index + 2 else None)
        return
    safe_exit_setup()
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EnigmaCube.Desktop")
        except (AttributeError, OSError):
            pass
    if "--selftest" in sys.argv:
        from enigma_timer import selftest
        i = sys.argv.index("--selftest")
        folder = sys.argv[i + 1] if i + 1 < len(sys.argv) else "selftest"
        finish(selftest.run(folder))
    if "--uninstall" in sys.argv:
        # Settings -> Apps -> Enigma Cube -> Uninstall runs "EnigmaCube.exe --uninstall"
        from installer import setup_app
        sys.exit(setup_app.main())
    from enigma_timer.hub_link import ensure_launch
    if not ensure_launch():
        return
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Enigma Cube")
    app.setApplicationDisplayName("Enigma Cube")
    app.setOrganizationName("Enigma")
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    from enigma_timer.brand import app_icon
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())

    # Probe ownership before reading/recovering user data. A second launch
    # brings back the existing process instead of replaying the intro.
    from enigma_timer.instance import AppInstance
    guard=AppInstance(os.path.join(data_dir(),"data.json"),app)
    i18n.set_language("en")
    try:
        if not guard.acquire():
            finish(0)
    except RuntimeError:
        QMessageBox.information(None,"Enigma Cube",i18n.tr("startup_busy"))
        guard.close()
        finish(1)
    app.aboutToQuit.connect(guard.close)
    app._instance_guard=guard
    store = Store()
    i18n.set_language(i18n.configured_language(store.settings))
    from enigma_timer.startup import StartupController
    def create_workspace(data):
        from enigma_timer.window import MainWindow
        return MainWindow(data)
    controller=StartupController(app,store,create_workspace)
    app._startup_controller=controller
    guard.activated.connect(controller.activate)
    controller.start()
    code = app.exec_()
    # Free cached pixmaps while Qt is still alive; see safe_exit_setup().
    from enigma_timer import training
    training.clear_caches()
    finish(code)


if __name__ == "__main__":
    main()
