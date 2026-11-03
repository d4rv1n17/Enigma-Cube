"""Live, state-checked smart cube solve assistant. Computation is isolated."""
import json
import os
import sys

from PyQt5.QtCore import QProcess, QTimer, Qt, QTemporaryDir
from PyQt5.QtWidgets import QLabel, QPushButton, QHBoxLayout, QProgressBar

from .i18n import tr, pick
from . import theme
from .solver import GuidedSolution
from .widgets import LiveCube3DWidget
from .windows import _BaseWindow
from .layouts import WrapLayout


class SolveAssistantWindow(_BaseWindow):
    def __init__(self, main):
        super().__init__(main, tr("solve_assistant"))
        theme.window_layout(self.body)
        self.process = None
        self.jobdir = None
        self.plan = None
        self.snapshot = None
        self.buffer = bytearray()
        self.is_guiding = False
        self.caption = QLabel(tr("assistant_intro"))
        self.caption.setWordWrap(True)
        self.body.addWidget(self.caption)
        self.view = LiveCube3DWidget()
        self.body.addWidget(theme.visual_stage(self.view), 1)
        self.step = QLabel(tr("assistant_ready"))
        self.step.setAlignment(Qt.AlignCenter)
        self.step.setObjectName("algorithmHeading")
        self.body.addWidget(self.step)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.detail)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.body.addWidget(self.progress)
        self.sequence = QLabel()
        self.sequence.setAlignment(Qt.AlignCenter)
        self.sequence.setWordWrap(True)
        self.sequence.setObjectName("muted")
        self.body.addWidget(self.sequence)
        row = WrapLayout()
        self.calculate = QPushButton(tr("assistant_calculate"))
        self.calculate.setObjectName("primary")
        self.calculate.clicked.connect(self.start)
        row.addWidget(self.calculate)
        connect = QPushButton(tr("ble_connect"))
        connect.clicked.connect(main._ble_show_scan)
        self.cancel = QPushButton(tr("assistant_cancel"))
        self.cancel.clicked.connect(self.stop)
        row.addWidget(self.cancel)
        self.body.addLayout(row)
        tools = WrapLayout()
        tools.addWidget(connect)
        sync = QPushButton(tr("cube_sync"))
        sync.clicked.connect(main.open_cube_sync)
        tools.addWidget(sync)
        self.body.addLayout(tools)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.timed_out)
        self.resize(760, 820)
        self.sync()

    def current(self):
        if not self.main.cube_btn.isChecked() or self.main.ble_state is None:
            return None
        state = self.main.ble_state.facelets()
        if self.main._frame_perm is not None:
            from .cube import rotate_frame_facelets
            state = rotate_frame_facelets(state, self.main._frame_perm)
        return state

    def start(self):
        self.stop()
        if not self.main._cube_state_trusted:
            self.main.open_cube_sync()
            self.sync()
            return
        state = self.current()
        if state is None:
            self.detail.setText(tr("assistant_wait"))
            return
        self.snapshot = state
        self.jobdir = QTemporaryDir()
        if not self.jobdir.isValid():
            self.detail.setText(tr("assistant_failed"))
            return
        self.output_path = os.path.join(self.jobdir.path(), "result.json")
        self.is_guiding = True
        self.calculate.setEnabled(False)
        self.step.setText(tr("assistant_thinking"))
        self.detail.setText(tr("assistant_initializing"))
        self.process = QProcess(self)
        self.buffer.clear()
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.finished)
        self.process.errorOccurred.connect(self.failed)
        args = ["--solver-worker", state, self.output_path]
        if not getattr(sys, "frozen", False):
            args.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))
        self.process.start(sys.executable, args)
        self.timeout.start(120000)

    def read_output(self):
        if self.process is not None:
            self.buffer.extend(bytes(self.process.readAllStandardOutput()))

    def finished(self, *_):
        if self.process is None:
            return
        self.read_output()
        self.timeout.stop()
        process, self.process = self.process, None
        process.deleteLater()
        self.calculate.setEnabled(True)
        try:
            with open(self.output_path, "r", encoding="utf-8") as stream:
                payload = json.load(stream)
            if "error" in payload:
                raise ValueError(payload["error"])
            if self.current() != self.snapshot:
                self.is_guiding = False
                self.step.setText(tr("assistant_changed"))
                self.detail.setText(tr("assistant_recalculate"))
                return
            self.plan = GuidedSolution(self.snapshot, payload["moves"])
            self.sync()
        except (ValueError, OSError, KeyError) as error:
            self.is_guiding = False
            self.step.setText(tr("assistant_failed"))
            self.detail.setText(str(error) or tr("assistant_recalculate"))
        finally:
            if self.jobdir:
                self.jobdir.remove()
                self.jobdir = None

    def failed(self, *_):
        if self.process and self.process.error() == QProcess.FailedToStart:
            self.stop()
            self.detail.setText(tr("assistant_failed"))

    def timed_out(self):
        self.stop()
        self.step.setText(tr("assistant_failed"))
        self.detail.setText(tr("assistant_timeout"))

    def stop(self):
        self.timeout.stop()
        self.is_guiding = False
        self.plan = None
        if self.process is not None:
            process, self.process = self.process, None
            process.blockSignals(True)
            process.kill()
            process.waitForFinished(1500)
            process.deleteLater()
        if self.jobdir:
            self.jobdir.remove()
            self.jobdir = None
        self.calculate.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.sequence.clear()
        self.view.set_highlight(None)
        self.step.setText(tr("assistant_ready"))
        self.detail.setText(tr("assistant_intro"))

    def sync(self):
        state = self.current()
        self.view.set_state(state)
        if state is None:
            if self.plan or self.process:
                self.stop()
            self.step.setText(tr("assistant_wait"))
            self.detail.setText(tr("assistant_connection_lost"))
            self.calculate.setEnabled(False)
            return
        if not self.main._cube_state_trusted:
            if self.plan or self.process:
                self.stop()
            self.step.setText(tr("sync_required"))
            self.detail.setText(tr("sync_required_detail"))
            self.calculate.setText(tr("cube_sync"))
            self.calculate.setEnabled(True)
            return
        self.calculate.setText(tr("assistant_calculate"))
        if self.process is None:
            self.calculate.setEnabled(True)
            if self.plan is None and self.step.text() in (tr("assistant_wait"), tr("sync_required")):
                self.step.setText(tr("assistant_ready"))
                self.detail.setText(tr("assistant_intro"))
        colors = {"U": ("white", "белый"), "F": ("green", "зелёный"), "R": ("red", "красный"),
                  "D": ("yellow", "жёлтый"), "L": ("orange", "оранжевый"), "B": ("blue", "синий")}
        self.caption.setText(tr("assistant_grip") % (pick(colors[state[4]]), pick(colors[state[22]])))
        if self.plan is None:
            return
        outcome = self.plan.observe(state)
        self.progress.setRange(0, max(1, len(self.plan.moves)))
        self.progress.setValue(self.plan.index)
        if outcome == "done":
            self.step.setText(tr("assistant_done"))
            self.detail.setText(tr("assistant_done_detail"))
            self.sequence.clear()
            self.view.set_highlight(None)
            self.is_guiding = False
            if self.plan.moves:
                from . import achievements as ach
                ach.set_flag(self.main.store, "guided_solve")
                self.main.check_achievements()
                self.main.save()
            self.plan = None
        elif outcome == "deviated":
            self.step.setText(tr("assistant_changed"))
            self.detail.setText(tr("assistant_recalculate"))
            self.view.set_highlight(None)
        else:
            move = self.plan.moves[self.plan.index]
            self.step.setText(move + "  ·  %d / %d" % (self.plan.index + 1, len(self.plan.moves)))
            self.detail.setText(move_description(move) + (" · " + tr("assistant_half") if outcome == "half" else ""))
            self.view.set_highlight(move[0])
            self.sequence.setText("  ".join(self.plan.moves[self.plan.index:self.plan.index + 10]))

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


def move_description(move):
    face = tr("face_" + move[0])
    direction = tr("turn_half" if move.endswith("2") else "turn_inverse" if move.endswith("'") else "turn_clockwise")
    return tr("turn_instruction") % (face, direction)
