"""Replay recorded BLE moves with explicit recording integrity."""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
from .widgets import LiveCube3DWidget
from .solver import apply_moves
from .i18n import tr
from . import theme
from .layouts import WrapLayout


class ReplayDialog(QDialog):
    def __init__(self, solve, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("solve_replay"))
        self.resize(740, 760)
        self.events = solve.telemetry.get("events", [])
        self.states = [solve.telemetry["initial"]]
        for _, move in self.events:
            self.states.append(apply_moves(self.states[-1], move))
        self.index = 0
        lay = QVBoxLayout(self)
        verified = solve.telemetry.get("verified", False)
        label = QLabel(tr("replay_verified" if verified else "replay_incomplete"))
        label.setWordWrap(True)
        lay.addWidget(label)
        pauses = sum(1 for a, b in zip(self.events, self.events[1:]) if b[0] - a[0] >= 1000)
        metrics = QLabel(tr("replay_stats") % (len(self.events), len(self.events) / max(0.001, solve.ms / 1000), pauses))
        metrics.setWordWrap(True)
        lay.addWidget(metrics)
        self.view = LiveCube3DWidget()
        lay.addWidget(theme.visual_stage(self.view), 1)
        self.position = QLabel()
        self.position.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.position)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, len(self.events))
        self.slider.valueChanged.connect(self.seek)
        lay.addWidget(self.slider)
        row = WrapLayout()
        play = QPushButton(tr("demo_play"))
        play.clicked.connect(self.play)
        row.addWidget(play)
        step = QPushButton(tr("demo_step"))
        step.clicked.connect(self.advance)
        row.addWidget(step)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance)
        self.playing = False
        self.seek(0)

    def seek(self, index):
        self.index = index
        self.view.set_state(self.states[index])
        self.position.setText("%d / %d   %s" % (index, len(self.events), self.events[index - 1][1] if index else ""))
        if self.playing:
            self.schedule()

    def play(self):
        self.playing = not self.playing
        if self.playing:
            if self.index == len(self.events):
                self.slider.setValue(0)
            self.schedule()
        else:
            self.timer.stop()

    def schedule(self):
        if self.index >= len(self.events):
            self.playing = False
            return
        before = self.events[self.index - 1][0] if self.index else 0
        self.timer.start(max(40, self.events[self.index][0] - before))

    def advance(self):
        self.slider.setValue(min(len(self.events), self.index + 1))

    def done(self, result):
        self.timer.stop()
        super().done(result)
