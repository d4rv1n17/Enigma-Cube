"""Explicit physical-state verification; never assume that a cube is solved."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QPushButton, QButtonGroup, QCheckBox, QWidget, QScrollArea, QFrame)
from .cube import FACE_COLORS
from .cube_sync import facelets_to_state
from .i18n import tr
from . import theme
from .layouts import WrapLayout


class CubeSyncDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.snapshot = main._raw_ble_state.facelets()
        self.profile = main.ble_profile
        self.frame = main._frame_perm
        self.target = None
        self.setWindowTitle(tr("cube_sync"))
        self.resize(650, 640)
        root = QVBoxLayout(self)
        heading = QLabel(tr("cube_sync"))
        heading.setObjectName("dialogTitle")
        heading.setWordWrap(True)
        root.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        intro = QLabel(tr("sync_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.colors = list(main.ble_state.facelets())
        if self.frame is not None:
            from .cube import rotate_frame_facelets
            self.colors = list(rotate_frame_facelets("".join(self.colors), self.frame))
        grip = QLabel(tr("sync_grip") % (tr("color_" + self.colors[4]), tr("color_" + self.colors[22])))
        grip.setWordWrap(True)
        grip.setObjectName("statusText")
        lay.addWidget(grip)
        self.selected = "U"
        self.buttons = []
        palette = WrapLayout()
        self.palette = QButtonGroup(self)
        for face in "URFDLB":
            button = QPushButton(tr("color_" + face))
            button.setCheckable(True)
            button.setStyleSheet("QPushButton { background:%s; color:#111; border:2px solid #555; padding:7px; } QPushButton:checked { border:3px solid %s; }" % (FACE_COLORS[face], "#111" if face=="U" else theme.TEXT))
            button.setChecked(face == "U")
            self.palette.addButton(button)
            button.clicked.connect(lambda _=False, f=face: setattr(self, "selected", f))
            palette.addWidget(button)
        lay.addLayout(palette)
        net = QGridLayout()
        net.setSpacing(10)
        positions = {"U": (0,1), "L": (1,0), "F": (1,1), "R": (1,2), "B": (1,3), "D": (2,1)}
        self.cells = {}
        for fi, face in enumerate("URFDLB"):
            panel = QWidget()
            grid = QGridLayout(panel)
            grid.setContentsMargins(2,2,2,2)
            grid.setSpacing(3)
            grid.setAlignment(Qt.AlignCenter)
            label = QLabel(tr("sync_face_" + face))
            label.setAlignment(Qt.AlignCenter)
            grid.addWidget(label, 0, 0, 1, 3)
            for cell in range(9):
                index = fi*9+cell
                button = QPushButton("●" if cell == 4 else "")
                button.setFixedSize(30,30)
                button.setEnabled(cell != 4)
                button.clicked.connect(lambda _=False, i=index: self.paint(i))
                grid.addWidget(button, cell//3+1, cell%3)
                self.cells[index] = button
            net.addWidget(panel, *positions[face])
        lay.addLayout(net, 1)
        self.confirm = QCheckBox(tr("sync_confirm"))
        root.addWidget(self.confirm)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName("errorText")
        root.addWidget(self.error)
        row = QHBoxLayout()
        solved = QPushButton(tr("sync_fill_solved"))
        solved.clicked.connect(self.fill_solved)
        row.addWidget(solved)
        row.addStretch()
        cancel = QPushButton(tr("cancel"))
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        save = QPushButton(tr("sync_apply"))
        save.setObjectName("primary")
        save.setEnabled(False)
        self.confirm.toggled.connect(save.setEnabled)
        save.clicked.connect(self.apply)
        row.addWidget(save)
        root.addLayout(row)
        self.refresh()

    def refresh(self):
        for index, button in self.cells.items():
            button.setStyleSheet("background:%s; border:1px solid #777; border-radius:5px; color:#222; padding:0;" % FACE_COLORS[self.colors[index]])

    def paint(self, index):
        self.colors[index] = self.selected
        self.confirm.setChecked(False)
        self.error.clear()
        self.refresh()

    def fill_solved(self):
        self.colors = [self.colors[fi*9+4] for fi in range(6) for _ in range(9)]
        self.confirm.setChecked(False)
        self.refresh()

    def apply(self):
        if (self.main._raw_ble_state is None or self.main._raw_ble_state.facelets() != self.snapshot
                or self.main.ble_profile != self.profile or not self.main.cube_btn.isChecked()):
            self.error.setText(tr("sync_moved"))
            return
        physical = list(self.colors)
        if self.frame is not None:
            unrotated = list(physical)
            for displayed, raw in enumerate(self.frame):
                unrotated[raw] = physical[displayed]
            physical = unrotated
        try:
            self.target = facelets_to_state("".join(physical), self.main._raw_ble_state.time)
        except (ValueError, KeyError, TypeError) as error:
            self.error.setText(tr("sync_invalid") + "\n" + str(error))
            return
        self.accept()
