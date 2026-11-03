# -*- coding: utf-8 -*-
"""Multi-window mode: any section of the app in its own window.

* PageWindow shows Training, Reference or Achievements on its own.
* MiniTimerWindow is a compact timer that saves into the current session
  of the main window, so it can sit next to the algorithms.

Every window shares the main window's store and TrainingHub, so progress and
solves made in one window appear in all of them immediately.
"""

import sys
import time

from PyQt5.QtCore import Qt, QTimer, QByteArray
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy,
                             QVBoxLayout, QWidget, QShortcut)

from . import scramble as scr
from . import theme
from .i18n import tr
from .stats import OK, Solve, fmt_ms
from .widgets import LiveCube3DWidget, TimerDisplay
from .layouts import WrapLayout

IDLE, HOLDING, READY, RUNNING, STOPPED = range(5)


def _dark(widget):
    if sys.platform.startswith("win"):
        from .window import _dark_title_bar
        _dark_title_bar(widget)


class _BaseWindow(QMainWindow):
    """Dark window with a slim header: title on the left, pin on the right."""

    def __init__(self, main, title, parent=None, key=None):
        QMainWindow.__init__(self, parent)
        self.main = main
        self.store = getattr(main, "store", None) or getattr(getattr(main, "main", None), "store", None)
        self._layout_key = key or type(self).__name__
        self._restored_layout = False
        self.setWindowTitle(title)
        self.setWindowIcon(main.windowIcon())
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        self.body = QVBoxLayout(central)
        theme.window_layout(self.body)
        head = QVBoxLayout()
        head.setSpacing(8)
        self.title = QLabel(title)
        self.title.setObjectName("dialogTitle")
        self.title.setWordWrap(True)
        head.addWidget(self.title)
        self.pin = QPushButton(tr("pin"))
        self.pin.setObjectName("pin")
        self.pin.setCheckable(True)
        self.pin.setFocusPolicy(Qt.NoFocus)
        self.pin.setToolTip(tr("pin_window"))
        self.pin.toggled.connect(self.set_pinned)
        self.body.addLayout(head)
        self.fullscreen = QPushButton(tr("fullscreen"))
        self.fullscreen.setObjectName("seg")
        self.fullscreen.clicked.connect(self.toggle_fullscreen)
        actions = WrapLayout()
        actions.addWidget(self.fullscreen)
        actions.addWidget(self.pin)
        head.addLayout(actions)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self, activated=self.leave_fullscreen)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.leave_fullscreen()
        else:
            self._was_maximized = self.isMaximized()
            self._before_full_geometry = self.saveGeometry()
            self.showFullScreen()
            self.fullscreen.setText(tr("exit_fullscreen"))

    def leave_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized() if getattr(self, "_was_maximized", False) else self.showNormal()
            self.fullscreen.setText(tr("fullscreen"))

    def set_pinned(self, on):
        geo = self.geometry()
        state = self.windowState()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on))
        self.setGeometry(geo)
        self.setWindowState(state)
        self.show()

    def sync(self):
        """Called by the main window whenever solves or progress change."""

    def showEvent(self, e):
        QMainWindow.showEvent(self, e)
        if not self._restored_layout:
            self._restored_layout = True
            saved = self.store.settings.get("window_layouts", {}).get(self._layout_key) if self.store else None
            if isinstance(saved, str):
                self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
            theme.fit_to_screen(self)
        self.setFocus()
        if not getattr(self, "_dark_done", False):
            self._dark_done = True
            _dark(self)

    def closeEvent(self, event):
        if self.store is not None:
            geometry = getattr(self, "_before_full_geometry", self.saveGeometry()) if self.isFullScreen() else self.saveGeometry()
            self.store.settings.setdefault("window_layouts", {})[self._layout_key] = bytes(geometry.toBase64()).decode("ascii")
            try:
                self.store.save()
            except OSError:
                pass
        super().closeEvent(event)


class PageWindow(_BaseWindow):
    """Training, Reference or Achievements in a separate window."""

    TITLES = {"training": "win_training", "reference": "win_reference",
              "achievements": "win_achievements"}

    def __init__(self, main, kind, parent=None):
        _BaseWindow.__init__(self, main, tr(self.TITLES[kind]), parent, key=kind)
        self.kind = kind
        theme.window_layout(self.body)
        from .pages import AchievementsPage, ReferencePage
        from .training import TrainingWidget
        if kind == "training":
            self.page = TrainingWidget(main.hub)
            self.resize(1180, 780)
        elif kind == "reference":
            self.page = ReferencePage(main.hub)
            self.page.show_puzzle(main.reference_puzzle())
            self.resize(1100, 760)
        else:
            self.page = AchievementsPage(main.store)
            self.page.refresh()
            self.resize(900, 720)
        self.body.addWidget(self.page, 1)

    def sync(self):
        if self.kind == "achievements":
            self.page.refresh()


class LiveCubeWindow(_BaseWindow):
    """A roomy, independently orbitable view of the connected smart cube."""

    def __init__(self, main, parent=None):
        _BaseWindow.__init__(self, main, tr("cube_3d_title"), parent)
        theme.window_layout(self.body)
        self.phase = QLabel()
        self.phase.setWordWrap(True)
        self.phase.setObjectName("statusText")
        self.body.addWidget(self.phase)
        self.view = LiveCube3DWidget()
        self.view.setMinimumSize(220, 200)
        self.body.addWidget(theme.visual_stage(self.view), 1)
        self.hint = QLabel(tr("cube_3d_empty"))
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.body.addWidget(self.hint)
        controls = WrapLayout()
        reset = QPushButton(tr("reset_view"))
        reset.setObjectName("seg")
        reset.clicked.connect(self.view.reset_view)
        controls.addWidget(reset)
        connect = QPushButton(tr("ble_connect"))
        connect.clicked.connect(main._ble_show_scan)
        controls.addWidget(connect)
        solve = QPushButton(tr("solve_assistant"))
        solve.setObjectName("primary")
        solve.clicked.connect(main.open_solve_assistant)
        controls.addWidget(solve)
        self.body.addLayout(controls)
        self.controls_hint = QLabel(tr("cube_3d_controls"))
        self.controls_hint.setObjectName("muted")
        self.controls_hint.setAlignment(Qt.AlignCenter)
        self.controls_hint.setWordWrap(True)
        self.body.addWidget(self.controls_hint)
        self.resize(620, 650)
        self.setMinimumSize(440, 500)
        self.sync()

    def sync(self):
        state = self.main.ble_state
        if state is None:
            self.phase.setText(tr("assistant_wait"))
            self.view.set_state(None)
            self.hint.setVisible(True)
            return
        facelets = state.facelets()
        if self.main._frame_perm is not None:
            from . import cube as cube_mod
            facelets = cube_mod.rotate_frame_facelets(facelets, self.main._frame_perm)
        self.view.set_state(facelets)
        from .window import RUNNING, INSPECTING
        key = ("sync_required_detail" if not self.main._cube_state_trusted else
               "cube_phase_solving" if self.main.state == RUNNING else
               "cube_phase_inspection" if self.main.state == INSPECTING else
               "cube_phase_ready" if self.main.ble_scramble_ready else "cube_phase_scramble")
        self.phase.setText(tr(key))
        self.hint.setVisible(False)


class MiniTimerWindow(_BaseWindow):
    """A small always-handy timer that saves into the main session."""

    def __init__(self, main, parent=None):
        _BaseWindow.__init__(self, main, tr("win_mini_timer"), parent)
        self.state = IDLE
        self.t_start = 0.0
        self.hold_start = 0.0
        self.body.setContentsMargins(16, 10, 16, 14)
        self.body.setSpacing(6)

        self.scramble = QLabel()
        self.scramble.setWordWrap(True)
        self.scramble.setAlignment(Qt.AlignCenter)
        self.scramble.setTextFormat(Qt.PlainText)
        self.scramble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scramble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.scramble.setObjectName("bodyText")
        self.body.addWidget(self.scramble)

        self.display = TimerDisplay()
        self.display.setMinimumHeight(110)
        self.display.pressed.connect(lambda: self._press(Qt.Key_Space, False))
        self.display.released.connect(lambda: self._release(Qt.Key_Space, False))
        self.body.addWidget(self.display, 1)

        self.hint = QLabel(tr("mini_hint"))
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setObjectName("caption")
        self.body.addWidget(self.hint)

        self.tick = QTimer(self)
        self.tick.setTimerType(Qt.PreciseTimer)
        self.tick.timeout.connect(self._on_tick)

        self.setFocusPolicy(Qt.StrongFocus)
        self.resize(460, 330)
        self.setMinimumSize(340, 260)
        self.sync()

    # ------------------------------------------------------------------
    def _decimals(self):
        return int(self.main.settings.get("decimals", 2))

    def sync(self):
        m = self.main
        self.title.setText("%s · %s" % (tr("win_mini_timer"),
                                        scr.PUZZLE_NAME.get(m.session.puzzle, m.session.puzzle)))
        self.scramble.setText(m.scramble)
        if self.state == IDLE:
            self._render()

    def _render(self):
        d = self._decimals()
        st = self.state
        if st == RUNNING:
            ms = int((time.perf_counter() - self.t_start) * 1000)
            self.display.set_display(fmt_ms(ms, d), theme.TEXT)
        elif st == HOLDING:
            self.display.set_display(self.main._last_text(d), theme.HOLD)
        elif st == READY:
            self.display.set_display(fmt_ms(0, d), theme.READY)
        else:
            self.display.set_display(self.main._last_text(d), theme.TEXT, self.main._last_sub())
        busy = st in (HOLDING, READY, RUNNING)
        self.scramble.setVisible(not busy or st == HOLDING)
        if self.main.state != 0:
            self.hint.setText(tr("mini_busy"))
        else:
            self.hint.setText(tr("mini_hint"))

    def _on_tick(self):
        if self.state == HOLDING:
            hold = int(self.main.settings.get("hold_ms", 300))
            if (time.perf_counter() - self.hold_start) * 1000 >= hold:
                self.state = READY
        self._render()

    # ------------------------------------------------------------------
    def _press(self, key, auto_repeat):
        if self.state == RUNNING:
            if not auto_repeat:
                self._stop()
            return True
        if self.main.solve_assistant is not None and self.main.solve_assistant.is_guiding:
            return key == Qt.Key_Space
        if self.state == STOPPED:
            return True
        if key == Qt.Key_Escape and self.state in (HOLDING, READY):
            self.state = IDLE
            self.tick.stop()
            self._render()
            return True
        if key != Qt.Key_Space or auto_repeat:
            return key == Qt.Key_Space
        if self.state == IDLE and self.main.state == 0:
            self.hold_start = time.perf_counter()
            self.state = HOLDING
            if int(self.main.settings.get("hold_ms", 300)) <= 0:
                self.state = READY
            self.tick.start(15)
            self._render()
        return True

    def _release(self, key, auto_repeat):
        if auto_repeat:
            return True
        if self.state == STOPPED:
            self.state = IDLE
            self._render()
            return True
        if key != Qt.Key_Space:
            return False
        if self.state == HOLDING:
            self.state = IDLE
            self.tick.stop()
            self._render()
        elif self.state == READY:
            self.t_start = time.perf_counter()
            self.state = RUNNING
            self._render()
        return True

    def _stop(self):
        ms = int((time.perf_counter() - self.t_start) * 1000)
        self.tick.stop()
        self.state = STOPPED
        m = self.main
        m._add_solve(Solve(ms, OK, m.scramble))
        m.new_scramble(force=True)
        self.sync()
        self._render()

    def keyPressEvent(self, e):
        if not self._press(e.key(), e.isAutoRepeat()):
            _BaseWindow.keyPressEvent(self, e)

    def keyReleaseEvent(self, e):
        if not self._release(e.key(), e.isAutoRepeat()):
            _BaseWindow.keyReleaseEvent(self, e)

    def mousePressEvent(self, e):
        if self.state == RUNNING:
            self._stop()
        else:
            _BaseWindow.mousePressEvent(self, e)

    def closeEvent(self, e):
        if self.state == RUNNING:
            self._stop()
        self.tick.stop()
        _BaseWindow.closeEvent(self, e)


__all__ = ["PageWindow", "MiniTimerWindow"]
