"""Shared interactive notation viewer."""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QPushButton, QHBoxLayout, QComboBox
from .windows import _BaseWindow
from .puzzle3d import Puzzle3DView
from .puzzle_mesh import tokens
from .notation_help import move_text,grip_text
from .i18n import tr
from .notation import CUBE_EVENTS, notation_facelets
from . import theme
from .layouts import WrapLayout


class MoveExplorerWindow(_BaseWindow):
    def __init__(self, main, puzzle, moves):
        super().__init__(main, tr("move_demo"))
        self.puzzle, self.moves = puzzle, moves
        self.parts = tokens(puzzle,moves)
        self.index = 0
        heading = QLabel(moves or tr("demo_before"))
        heading.setObjectName("algorithmHeading")
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setMaximumHeight(110)
        self.body.addWidget(heading)
        grip = QLabel(grip_text(puzzle))
        grip.setWordWrap(True)
        grip.setObjectName("notationGrip")
        self.body.addWidget(grip)
        self.is_cube = puzzle in CUBE_EVENTS
        self.view = Puzzle3DView()
        self.view.set_puzzle(puzzle)
        self.body.addWidget(theme.visual_stage(self.view), 1)
        self.explanation = QLabel()
        self.explanation.setWordWrap(True)
        self.explanation.setAlignment(Qt.AlignCenter)
        self.body.addWidget(self.explanation)
        row = WrapLayout()
        for text, callback in (("reset_view", self.reset), ("demo_play", self.play), ("demo_step", self.advance)):
            button = QPushButton(tr(text))
            button.setObjectName("primary" if text == "demo_play" else "seg")
            button.clicked.connect(callback)
            row.addWidget(button)
            if text == "demo_play":
                self.play_button = button
                button.setEnabled(bool(self.parts))
        self.speed = QComboBox()
        for text, interval in (("0.5×", 2400), ("1×", 1200), ("2×", 600)):
            self.speed.addItem(text, interval)
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(lambda: self.timer.setInterval(self.speed.currentData()))
        row.addWidget(self.speed)
        self.body.addLayout(row)
        self.timer = QTimer(self)
        self.timer.setInterval(1200)
        self.timer.timeout.connect(self.advance)
        self.resize(700, 740)
        self.render()

    def reset(self):
        self.timer.stop()
        self.play_button.setText(tr("demo_play"))
        self.index = 0
        self.view.reset_view()
        self.render()

    def play(self):
        if not self.parts:
            return
        self.timer.stop() if self.timer.isActive() else self.timer.start()
        self.play_button.setText(tr("notation_pause") if self.timer.isActive() else tr("demo_play"))

    def advance(self):
        self.index = (self.index + 1) % (len(self.parts) + 1)
        self.render()

    def render(self):
        alg = " ".join(self.parts[:self.index])
        self.view.set_algorithm(alg)
        move = self.parts[self.index] if self.index<len(self.parts) else None
        self.view.set_highlight(move[0].upper() if self.is_cube and move else move)
        phase = tr("demo_before") if self.index == 0 else tr("demo_after") + ": " + self.parts[self.index - 1]
        if self.index < len(self.parts):
            phase += "\n" + move_text(self.puzzle,self.parts[self.index])
        self.explanation.setText(phase)

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        self.play_button.setText(tr("demo_play"))
        super().hideEvent(event)
