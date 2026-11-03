"""Interactive notation studio with shared geometry for every cube size."""
from functools import lru_cache
from PyQt5.QtCore import Qt, QSize, QUrl, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QIcon, QPixmap, QImage, QPainter, QColor, QPen
from PyQt5.QtWidgets import (QWidget, QFrame, QLabel, QHBoxLayout, QVBoxLayout,
    QGridLayout, QPushButton, QToolButton, QButtonGroup, QScrollArea,
    QBoxLayout, QGraphicsOpacityEffect, QComboBox)
from .i18n import tr, lang, pick
from .widgets import LiveCube3DWidget
from .notation import CUBE_EVENTS, notation_facelets
from .puzzle3d import Puzzle3DView, puzzle_image
from .notation_help import MOVES, grip_text, card_name, move_text
from .training import LessonBrowser
from . import reference


class MoveCard(QToolButton):
    """Short hover transitions without perpetual decoration or background timers."""
    def __init__(self):
        super().__init__()
        self._hover = 0.0
        self.animation = QPropertyAnimation(self,b"hover",self)
        self.animation.setDuration(140)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def _get_hover(self):
        return self._hover

    def _set_hover(self, value):
        self._hover = value
        self.update()

    hover = pyqtProperty(float,_get_hover,_set_hover)

    def animate_hover(self, value):
        from PyQt5.QtWidgets import QApplication
        self.animation.stop()
        if QApplication.instance().property("reduceMotion"):
            self._set_hover(value)
        else:
            self.animation.setStartValue(self._hover)
            self.animation.setEndValue(value)
            self.animation.start()

    def enterEvent(self, event):
        self.animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_hover(0.0)
        super().leaveEvent(event)

    def hideEvent(self, event):
        self.animation.stop()
        self._hover = 0.0
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._hover > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(244,204,12,int(95*self._hover)),1))
            painter.setBrush(QColor(244,204,12,int(7*self._hover)))
            painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),11,11)
            painter.end()


@lru_cache(maxsize=144)
def _thumbnail(puzzle, move):
    if puzzle not in CUBE_EVENTS:
        return QPixmap.fromImage(puzzle_image(puzzle,move))
    view = LiveCube3DWidget()
    view.resize(144,144)
    view.set_cube_size(CUBE_EVENTS[puzzle])
    view.set_state(notation_facelets(puzzle,move))
    result = QImage(144,144,QImage.Format_ARGB32_Premultiplied)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    view._paint_cube(painter)
    painter.end()
    view.deleteLater()
    return QPixmap.fromImage(result)


class CubeNotationPanel(QWidget):
    def __init__(self, open_demo, parent=None):
        super().__init__(parent)
        self.open_demo = open_demo
        self.puzzle, self.face, self.mode, self.after = "333", "F", 0, False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)
        body = QWidget()
        self.scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(2,2,8,8)
        layout.setSpacing(10)
        header = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("pageHeading")
        header.addWidget(self.heading)
        header.addStretch()
        badge = QLabel(tr("notation_interactive"))
        badge.setObjectName("notationBadge")
        header.addWidget(badge)
        self.size_select = QComboBox()
        for size in range(4,8):
            self.size_select.addItem("%d × %d" % (size,size),str(size)*3)
        self.size_select.setToolTip(tr("notation_cube_size"))
        self.size_select.currentIndexChanged.connect(self.change_size)
        header.addWidget(self.size_select)
        self.hours = QComboBox()
        for hour in range(1,7):
            self.hours.addItem(tr("notation_hours") % hour,hour)
        self.hours.currentIndexChanged.connect(lambda: self.set_mode(self.mode))
        header.addWidget(self.hours)
        layout.addLayout(header)
        grip = QLabel(tr("notation_grip_short"))
        self.grip = grip
        grip.setObjectName("notationGrip")
        grip.setWordWrap(True)
        layout.addWidget(grip)
        self.content = QBoxLayout(QBoxLayout.LeftToRight)
        self.content.setSpacing(14)
        layout.addLayout(self.content)
        preview = QFrame()
        preview.setObjectName("notationStage")
        box = QVBoxLayout(preview)
        box.setContentsMargins(22,18,22,18)
        box.setSpacing(8)
        top = QHBoxLayout()
        self.move_title = QLabel()
        self.move_title.setObjectName("notationSymbol")
        top.addWidget(self.move_title)
        top.addStretch()
        self.phase = QLabel()
        self.phase.setObjectName("notationBadge")
        top.addWidget(self.phase)
        box.addLayout(top)
        self.cube = Puzzle3DView()
        self.cube.setMinimumSize(240,230)
        box.addWidget(self.cube,1)
        camera = QHBoxLayout()
        tip = QLabel(tr("notation_orbit"))
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        camera.addWidget(tip,1)
        reset = QPushButton("↺")
        reset.setObjectName("icon")
        reset.setToolTip(tr("reset_view"))
        reset.setAccessibleName(tr("reset_view"))
        reset.clicked.connect(self.cube.reset_view)
        camera.addWidget(reset)
        separate = QPushButton("↗")
        separate.setObjectName("icon")
        separate.setToolTip(tr("notation_open_demo"))
        separate.setAccessibleName(tr("notation_open_demo"))
        separate.clicked.connect(self.open_selected)
        camera.addWidget(separate)
        box.addLayout(camera)
        self.content.addWidget(preview,3)
        self.controls = QFrame()
        self.controls.setObjectName("notationControls")
        self.controls.setFixedWidth(270)
        side = QVBoxLayout(self.controls)
        side.setContentsMargins(0,0,0,0)
        side.setSpacing(7)
        label = QLabel(tr("notation_choose_face"))
        label.setObjectName("sectionTitle")
        side.addWidget(label)
        self.move_select = QComboBox()
        self.move_select.currentIndexChanged.connect(self.choose_move)
        side.addWidget(self.move_select)
        self.gallery = QGridLayout()
        self.gallery.setSpacing(7)
        self.cards = {}
        self.faces = QButtonGroup(self)
        side.addLayout(self.gallery)
        direction = QLabel(tr("notation_choose_direction"))
        direction.setObjectName("sectionTitle")
        side.addWidget(direction)
        modes = QHBoxLayout()
        modes.setSpacing(5)
        self.mode_group = QButtonGroup(self)
        for index, (text,key) in enumerate((("90° ↻","notation_cw"),("90° ↺","notation_ccw"),("180°","notation_half"))):
            button = QPushButton(text)
            button.setObjectName("notationMode")
            button.setToolTip(tr(key))
            button.setAccessibleName(tr(key))
            button.setCheckable(True)
            button.setChecked(index == 0)
            self.mode_group.addButton(button,index)
            modes.addWidget(button)
        self.mode_group.buttonClicked[int].connect(self.set_mode)
        side.addLayout(modes)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(52)
        self.description.setObjectName("notationExplanation")
        side.addWidget(self.description)
        self.effect = QGraphicsOpacityEffect(self.description)
        self.description.setGraphicsEffect(self.effect)
        self.fade = QPropertyAnimation(self.effect,b"opacity",self)
        self.fade.setDuration(180)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.play = QPushButton(tr("notation_show_move"))
        self.play.setObjectName("primary")
        self.play.clicked.connect(self.toggle_move)
        side.addWidget(self.play)
        side.addStretch()
        self.content.addWidget(self.controls)
        self.more = QPushButton(tr("notation_more") + "  +")
        self.more.setObjectName("notationMore")
        self.more.setCheckable(True)
        layout.addWidget(self.more)
        self.advanced = LessonBrowser()
        self.advanced.setMinimumHeight(330)
        self.advanced.hide()
        self.more.toggled.connect(self.toggle_advanced)
        layout.addWidget(self.advanced)
        layout.addStretch(1)
        self.set_puzzle("333")

    @property
    def move(self):
        return self.move_for(self.face)

    def move_for(self,face):
        if self.puzzle=="clock":
            return "y2" if face=="y2" else face+str(self.hours.currentData() or 1)+("-" if self.mode==1 else "+")
        if self.puzzle=="sq1":
            if face=="/":
                return face
            amount = (-1 if self.mode==1 else 6 if self.mode==2 else 1)
            return "(%d,0)" % amount if face=="(1,0)" else "(0,%d)" % amount
        if self.puzzle=="minx" and face.endswith("++"):
            return face[:1]+("--" if self.mode==1 else "++")
        return face + ("", "'", "2")[self.mode]

    def build_cards(self):
        for card in self.cards.values():
            self.faces.removeButton(card)
            self.gallery.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards = {}
        faces = ("F","R","U","L","D","B") if self.puzzle in CUBE_EVENTS else MOVES[self.puzzle]
        if self.face not in faces:
            self.face = faces[0]
        columns = 3 if self.puzzle=="clock" else 2
        self.move_select.blockSignals(True)
        self.move_select.clear()
        self.move_select.setVisible(self.puzzle=="clock")
        for index,face in enumerate(faces):
            card = MoveCard()
            card.setObjectName("notationCard")
            card.setCheckable(True)
            card.setChecked(face==self.face)
            card.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if columns==3 else Qt.ToolButtonTextBesideIcon)
            compact = len(faces)>6
            card.setIconSize(QSize(34,34) if columns==3 else QSize(36,36) if compact else QSize(44,44))
            card.setMinimumSize(78 if columns==3 else 125,50 if compact else 58)
            card.setCursor(Qt.PointingHandCursor)
            self.faces.addButton(card,index)
            card.clicked.connect(lambda _=False,f=face:self.select_face(f))
            if self.puzzle=="clock":
                card.setParent(self.controls)
                card.hide()
                self.move_select.addItem(face+" · "+card_name(self.puzzle,face),face)
            else:
                self.gallery.addWidget(card,index//columns,index%columns)
            self.cards[face] = card
        self.move_select.setCurrentIndex(faces.index(self.face))
        self.move_select.blockSignals(False)

    def choose_move(self,index):
        face = self.move_select.itemData(index)
        if face:
            self.select_face(face)

    def refresh_modes(self):
        angle = "120°" if self.puzzle in ("pyram","skewb") else "72°" if self.puzzle=="minx" else "30°" if self.puzzle=="sq1" else "1h" if self.puzzle=="clock" else "90°"
        if self.puzzle=="minx" and self.face.endswith("++"):
            angle = "144°"
        if self.puzzle=="clock":
            angle = str(self.hours.currentData())+pick(("h","ч"))
        self.mode_group.button(0).setText(angle+" ↻")
        self.mode_group.button(1).setText(angle+" ↺")
        self.mode_group.button(2).setText("144°" if self.puzzle=="minx" else "180°")
        for index,text in enumerate((pick((angle+" clockwise",angle+" по часовой")),pick((angle+" counter-clockwise",angle+" против часовой")),pick(("Half turn","Пол-оборота")))):
            self.mode_group.button(index).setToolTip(text)
            self.mode_group.button(index).setAccessibleName(text)
        half = self.puzzle not in ("pyram","skewb","clock") and not (self.puzzle=="minx" and self.face.endswith("++"))
        self.mode_group.button(2).setVisible(half)
        neutral = (self.puzzle=="clock" and self.face=="y2") or (self.puzzle=="sq1" and self.face=="/")
        self.hours.setEnabled(not neutral)
        for button in self.mode_group.buttons():
            button.setEnabled(not neutral)
        if self.mode==2 and not half:
            self.mode = 0
            self.mode_group.button(0).setChecked(True)

    def set_puzzle(self, puzzle):
        if puzzle not in CUBE_EVENTS and puzzle not in MOVES:
            raise ValueError("Unsupported reference puzzle")
        self.puzzle, self.after = puzzle, False
        self.cube.set_puzzle(puzzle)
        name = puzzle[0]+"×"+puzzle[0] if puzzle in CUBE_EVENTS else pick(dict(reference.PUZZLES)[puzzle])
        self.heading.setText(tr("notation_title") % name)
        self.grip.setText(grip_text(puzzle))
        self.hours.setVisible(puzzle=="clock")
        self.size_select.setVisible(CUBE_EVENTS.get(puzzle,0) >= 4)
        self.size_select.blockSignals(True)
        self.size_select.setCurrentIndex(max(0,CUBE_EVENTS.get(puzzle,0)-4))
        self.size_select.blockSignals(False)
        self.more.setVisible(puzzle != "222")
        self.more.setChecked(False)
        self.advanced.hide()
        self.advanced.setHtml(reference.advanced_html(puzzle,lang()))
        self.scroll.verticalScrollBar().setValue(0)
        self.build_cards()
        self.refresh_modes()
        self.more.setText(tr("notation_more" if puzzle in CUBE_EVENTS else "notation_explanation")+"  +")
        self.refresh_cards()
        self.refresh_preview()

    def change_size(self, index):
        puzzle = self.size_select.itemData(index)
        if puzzle and puzzle != self.puzzle:
            self.set_puzzle(puzzle)

    def set_mode(self, mode):
        if mode not in (0,1,2):
            return
        self.mode, self.after = mode, False
        self.mode_group.button(mode).setChecked(True)
        self.refresh_modes()
        self.refresh_cards()
        self.refresh_preview()

    def select_face(self, face):
        if face not in self.cards:
            return
        self.face, self.after = face, False
        self.cards[face].setChecked(True)
        self.refresh_modes()
        self.refresh_cards()
        self.refresh_preview()

    def refresh_cards(self):
        for face, card in self.cards.items():
            move = self.move_for(face)
            name = card_name(self.puzzle,face)
            card.setText(move if self.puzzle=="clock" else move+"\n"+name)
            card.setToolTip(name + " · " + move)
            card.setIcon(QIcon(_thumbnail(self.puzzle,move)))
            if self.puzzle=="clock":
                self.move_select.setItemIcon(self.move_select.findData(face),card.icon())
        self._layout_controls()

    def refresh_preview(self):
        self.move_title.setText(self.move + "  ·  " + card_name(self.puzzle,self.face))
        self.move_title.setWordWrap(True)
        self.phase.setText(tr("demo_after" if self.after else "demo_before"))
        self.cube.set_algorithm(self.move if self.after else "")
        self.cube.set_highlight(self.move if self.puzzle not in CUBE_EVENTS else self.face)
        self.description.setText(move_text(self.puzzle,self.move))
        self.play.setText(tr("notation_return" if self.after else "notation_show_move"))
        self.fade.stop()
        if self.isVisible() and not self.cube._reduced_motion():
            self.fade.setStartValue(.35)
            self.fade.setEndValue(1.0)
            self.fade.start()
        else:
            self.effect.setOpacity(1.0)

    def toggle_move(self):
        self.after = not self.after
        self.refresh_preview()

    def toggle_advanced(self, checked):
        self.advanced.setVisible(checked)
        self.more.setText(tr("notation_more" if self.puzzle in CUBE_EVENTS else "notation_explanation") + ("  −" if checked else "  +"))

    def open_selected(self):
        self.open_demo(QUrl("demo:%s:%s" % (self.puzzle,self.move)))

    def resizeEvent(self, event):
        self._layout_controls()
        super().resizeEvent(event)

    def _layout_controls(self):
        narrow = self.width() < 640
        self.content.setDirection(QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight)
        for card in self.cards.values():
            card.ensurePolished()
        widths = [card.minimumSizeHint().width() for card in self.cards.values()] if self.puzzle!="clock" else []
        controls_width = max(270, 2*max(widths, default=125)+16)
        self.controls.setFixedWidth(max(controls_width,self.width()-24) if narrow else controls_width)

    def hideEvent(self, event):
        self.fade.stop()
        self.effect.setOpacity(1.0)
        self.after = False
        super().hideEvent(event)

    def showEvent(self, event):
        self.refresh_preview()
        super().showEvent(event)
