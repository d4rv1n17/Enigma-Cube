"""Custom painted widgets: big timer, scramble preview, progress chart."""

import math
import time
from collections import deque

from PyQt5.QtCore import (QEasingCurve, QPropertyAnimation, Qt, QRectF, QPointF, QPoint,
                          QTimer, pyqtSignal)
from PyQt5.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPolygonF, QRadialGradient, QTransform, QPixmap, QRegion)
from PyQt5.QtWidgets import (QApplication, QGraphicsOpacityEffect, QLabel, QStackedWidget,
                             QToolTip, QWidget, QProgressBar)

from . import theme
from .cube import Cube, FACE_COLORS
from .i18n import tr
from .puzzles import Pyraminx, Skewb, sq1_polygons, sq1_slice_lines
from .scramble import CUBE_SIZE
from .stats import INF, fmt_ms, fmt_avg


class FadeStackedWidget(QStackedWidget):
    """A stacked page container with a short, low-key fade between pages."""

    def __init__(self, parent=None):
        QStackedWidget.__init__(self, parent)
        self._fade_animation = None
        self._fade_page = None

    def setCurrentIndex(self, index):
        if index == self.currentIndex() or index < 0 or index >= self.count():
            return QStackedWidget.setCurrentIndex(self, index)
        snapshot = None
        if self.isVisible() and not QApplication.instance().property("reduceMotion") and self.currentWidget():
            current = self.currentWidget()
            snapshot = QPixmap(current.size())
            snapshot.fill(QColor(theme.BG))
            painter = QPainter(snapshot)
            current.render(painter, QPoint(), QRegion(), QWidget.DrawChildren)
            painter.end()
        previous = self._fade_page
        if previous is not None:
            if self._fade_animation is not None:
                self._fade_animation.stop()
                self._fade_animation.deleteLater()
                self._fade_animation = None
            previous.setGraphicsEffect(None)
            previous.deleteLater()
            self._fade_page = None
        QStackedWidget.setCurrentIndex(self, index)
        if snapshot is None or snapshot.isNull():
            return
        page = QLabel(self)
        page.setPixmap(snapshot)
        page.setGeometry(self.currentWidget().geometry())
        page.setAttribute(Qt.WA_TransparentForMouseEvents)
        page.show()
        page.raise_()
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(1.0)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(180)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda p=page, a=animation: self._finish_fade(p, a))
        self._fade_page = page
        self._fade_animation = animation
        animation.start()

    def setCurrentWidget(self, widget):
        index = self.indexOf(widget)
        if index >= 0:
            self.setCurrentIndex(index)

    def _finish_fade(self, page, animation):
        if page is self._fade_page:
            page.setGraphicsEffect(None)
            page.hide()
            page.deleteLater()
            self._fade_page = None
            self._fade_animation = None
        animation.deleteLater()

    def resizeEvent(self, event):
        if self._fade_page is not None:
            if self._fade_animation:
                self._fade_animation.stop()
                self._fade_animation.deleteLater()
                self._fade_animation = None
            self._fade_page.hide()
            self._fade_page.deleteLater()
            self._fade_page = None
        super().resizeEvent(event)


class AnimatedProgressBar(QProgressBar):
    """Brief progress feedback; data and timers never depend on its frames."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = 0
        self._animation = QPropertyAnimation(self, b"value", self)
        self._animation.setDuration(280)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def setValue(self, value):
        self._target = max(self.minimum(), min(self.maximum(), value))
        self._animation.stop()
        if self.isVisible() and not QApplication.instance().property("reduceMotion"):
            self._animation.setStartValue(self.value())
            self._animation.setEndValue(self._target)
            self._animation.start()
        else:
            QProgressBar.setValue(self, self._target)

    def showEvent(self, event):
        super().showEvent(event)
        if self._target > self.minimum() and not QApplication.instance().property("reduceMotion"):
            QProgressBar.setValue(self, self.minimum())
            self.setValue(self._target)

    def hideEvent(self, event):
        self._animation.stop()
        QProgressBar.setValue(self, self._target)
        super().hideEvent(event)


class TimerDisplay(QWidget):
    """Huge auto-scaling time readout. Mouse press/release act like Space."""

    pressed = pyqtSignal()
    released = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._text = "0.00"
        self._sub = ""
        self._color = QColor(theme.TEXT)
        self.setMinimumHeight(140)
        self.setCursor(Qt.PointingHandCursor)

    def set_display(self, text, color=None, sub=""):
        color = QColor(color or theme.TEXT)
        if text != self._text or sub != self._sub or color != self._color:
            self._text, self._sub, self._color = text, sub, color
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        r = self.rect()
        sub_h = int(r.height() * 0.16) if self._sub else 0
        main = r.adjusted(0, 0, 0, -sub_h)
        # Keep the timer dominant without letting long times or tall screens
        # turn the readout into a wall of digits.
        size = min(main.height() * 0.44, r.width() * 1.18 / max(4, len(self._text)))
        f = QFont(theme.ui_font())
        f.setPixelSize(max(14, int(size)))
        f.setWeight(QFont.Medium)
        f.setLetterSpacing(QFont.PercentageSpacing, 98)
        p.setFont(f)
        p.setPen(self._color)
        p.drawText(main, Qt.AlignCenter, self._text)
        if self._sub:
            f2 = QFont(theme.ui_font())
            px = int(min(sub_h * 0.5, r.width() * 1.7 / max(10, len(self._sub))))
            f2.setPixelSize(max(11, px))
            p.setFont(f2)
            p.setPen(QColor(theme.MUTED))
            p.drawText(r.adjusted(0, r.height() - sub_h - 4, 0, 0),
                       Qt.AlignHCenter | Qt.AlignTop, self._sub)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.pressed.emit()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.released.emit()


class ScramblePreview(QWidget):
    """Draws the scrambled state: cube nets, Pyraminx, Skewb and Square-1."""

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._grid = None
        self._n = 0
        self._polys = None
        self._lines = []
        self._puzzle_view = None
        self.setMinimumSize(200, 150)

    def set_scramble(self, puzzle, scramble):
        self._grid, self._n, self._polys, self._lines = None, 0, None, []
        if self._puzzle_view is not None:
            self._puzzle_view.hide()
        try:
            n = CUBE_SIZE.get(puzzle)
            if n:
                self._n = n
                self._grid = Cube(n).apply(scramble).facelets()
            elif puzzle in ("pyram","skewb","sq1","minx","clock"):
                from .puzzle3d import PolyPuzzle3DWidget
                if self._puzzle_view is None:
                    self._puzzle_view = PolyPuzzle3DWidget(self)
                self._puzzle_view.set_puzzle(puzzle)
                self._puzzle_view.set_algorithm(scramble)
                self._puzzle_view.setGeometry(self.rect())
                self._puzzle_view.show()
        except Exception:  # noqa: BLE001 - a preview must never break the timer
            self._grid, self._polys = None, None
            if self._puzzle_view is not None:
                self._puzzle_view.hide()
        self.update()

    def resizeEvent(self,event):
        if self._puzzle_view is not None:
            self._puzzle_view.setGeometry(self.rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        if self._puzzle_view is not None and not self._puzzle_view.isHidden():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(8, 8, -8, -8)
        if self._grid:
            self._paint_cube(p, r)
        elif self._polys:
            self._paint_polys(p, r)
        else:
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignCenter | Qt.TextWordWrap, tr("preview_na"))
        p.end()

    def _paint_polys(self, p, r):
        xs = [pt[0] for poly, _ in self._polys for pt in poly]
        ys = [pt[1] for poly, _ in self._polys for pt in poly]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        scale = min(r.width() / max(1e-6, x1 - x0), r.height() / max(1e-6, y1 - y0))
        ox = r.x() + (r.width() - (x1 - x0) * scale) / 2.0
        oy = r.y() + (r.height() - (y1 - y0) * scale) / 2.0

        def T(pt):
            return QPointF(ox + (pt[0] - x0) * scale, oy + (pt[1] - y0) * scale)

        pen = QPen(QColor("#000000"), max(1.0, scale * 0.03))
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cache = {}
        for poly, col in self._polys:
            if col not in cache:
                cache[col] = QColor(col)
            p.setBrush(cache[col])
            p.drawPolygon(QPolygonF([T(pt) for pt in poly]))
        if self._lines:
            p.setPen(QPen(QColor(theme.ACCENT), max(1.5, scale * 0.035), Qt.DashLine))
            for a, b in self._lines:
                p.drawLine(T(a), T(b))

    def _paint_cube(self, p, r):
        n = self._n
        gap = 6.0
        s = min((r.width() - 3 * gap) / (4.0 * n), (r.height() - 2 * gap) / (3.0 * n))
        s = max(2.0, s)
        face = s * n
        total_w = 4 * face + 3 * gap
        total_h = 3 * face + 2 * gap
        ox = r.x() + (r.width() - total_w) / 2.0
        oy = r.y() + (r.height() - total_h) / 2.0
        layout = {"U": (1, 0), "L": (0, 1), "F": (1, 1), "R": (2, 1), "B": (3, 1), "D": (1, 2)}
        inset = max(0.6, s * 0.07)
        radius = s * 0.18
        colors = dict((k, QColor(v)) for k, v in FACE_COLORS.items())
        for fname, (cx, cy) in layout.items():
            fx = ox + cx * (face + gap)
            fy = oy + cy * (face + gap)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#000000"))
            p.drawRoundedRect(QRectF(fx - 2, fy - 2, face + 4, face + 4), radius + 2, radius + 2)
            g = self._grid[fname]
            for row in range(n):
                for col in range(n):
                    p.setBrush(colors[g[row][col]])
                    p.drawRoundedRect(QRectF(fx + col * s + inset, fy + row * s + inset,
                                             s - 2 * inset, s - 2 * inset), radius, radius)


from .analytics_widgets import TimeChart, TimeHistogram


class LiveCubeWidget(QWidget):
    """A 3x3 net drawn from the smart cube's live state.

    The widget is passive: `set_state` receives a 54-char URFDLB facelet
    string (or None to show nothing).  The cube is drawn exactly like
    ScramblePreview's net, so both views stay in one style.
    """

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._grid = None
        self.setMinimumSize(200, 150)

    def set_state(self, facelets):
        if facelets is None:
            self._grid = None
        else:
            g = {}
            for i, face in enumerate("URFDLB"):
                g[face] = facelets[i * 9:(i + 1) * 9]
            self._grid = g
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(8, 8, -8, -8)
        if self._grid:
            self._paint_cube(p, r)
        p.end()

    def _paint_cube(self, p, r):
        n = 3
        gap = 6.0
        s = min((r.width() - 3 * gap) / (4.0 * n), (r.height() - 2 * gap) / (3.0 * n))
        s = max(2.0, s)
        face = s * n
        total_w = 4 * face + 3 * gap
        total_h = 3 * face + 2 * gap
        ox = r.x() + (r.width() - total_w) / 2.0
        oy = r.y() + (r.height() - total_h) / 2.0
        layout = {"U": (1, 0), "L": (0, 1), "F": (1, 1), "R": (2, 1), "B": (3, 1), "D": (1, 2)}
        inset = max(0.6, s * 0.07)
        radius = s * 0.18
        colors = dict((k, QColor(v)) for k, v in FACE_COLORS.items())
        for fname, (cx, cy) in layout.items():
            fx = ox + cx * (face + gap)
            fy = oy + cy * (face + gap)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#000000"))
            p.drawRoundedRect(QRectF(fx - 2, fy - 2, face + 4, face + 4), radius + 2, radius + 2)
            g = self._grid[fname]
            for row in range(n):
                for col in range(n):
                    p.setBrush(colors[g[row * n + col]])
                    p.drawRoundedRect(QRectF(fx + col * s + inset, fy + row * s + inset,
                                             s - 2 * inset, s - 2 * inset), radius, radius)


class LiveCube3DWidget(QWidget):
    """Interactive 3D view of the smart cube's live state.

    Drag with the mouse to orbit the cube and see every side, roll the
    wheel to zoom, double-click to reset the view.  `set_state` takes the
    URFDLB facelet string (or None to show nothing). The default is 3x3;
    set_cube_size configures 2x2 through 7x7 before supplying its state.
    The sticker layout follows the standard Kociemba net, so
    the view matches the flat scramble preview; the cube keeps its own
    fixed frame, so rotate the view to match how the physical cube sits
    in your hands.
    """

    # normal, column direction (col+), row direction (row+), in the
    # Kociemba facelet reading order of each face
    _AXES = {
        "U": ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
        "R": ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
        "F": ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
        "D": ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
        "L": ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
        "B": ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
    }
    _FACE_ORDER = ("U", "R", "F", "D", "L", "B")   # facelet string order

    _STICKER = 0.92        # sticker size, fraction of a cubie face
    _LIGHT = (-0.35, 0.6, 0.72)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._facelets = None
        self.cube_size = 3
        self._highlight = None
        from .brand import logo_image
        self._logo = logo_image()
        self._turn = None
        self._turn_queue = deque()
        self._display_state = None
        self._logo_orientation = 0
        self._display_logo_orientation = 0
        self._camera_reset = None
        self._velocity = (0.0, 0.0, 0.0)
        self._last_drag = 0.0
        self._last_frame = time.perf_counter()
        self._zoom_target = 1.0
        self._arrival = None
        self._solved_flash = None
        self._turn_timer = QTimer(self)
        self._turn_timer.setInterval(16)
        self._turn_timer.setTimerType(Qt.PreciseTimer)
        self._turn_timer.timeout.connect(self._advance_turn)
        self._yaw = math.radians(-24)    # default view shows U, F and R
        self._pitch = math.radians(22)
        self._roll = 0.0                 # roll about the view axis
        self._zoom = 1.0
        self._grab = None                # (x, y, button) while dragging
        self.setMinimumSize(120, 150)
        self.setFocusPolicy(Qt.NoFocus)  # never steal the timer's keys
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(tr("cube_3d_controls"))

    # ---- state ------------------------------------------------------
    def set_cube_size(self, size):
        """Change geometry without carrying animation state across puzzles."""
        if size not in range(2, 8):
            raise ValueError("Cube size must be between 2 and 7")
        if size == self.cube_size:
            return
        self.cube_size = size
        self._turn_timer.stop()
        self._turn = None
        self._turn_queue.clear()
        self._facelets = self._display_state = None
        self._logo_orientation = self._display_logo_orientation = 0
        self._arrival = self._solved_flash = None
        self.update()

    def _apply_turn(self, state, move):
        if self.cube_size == 3:
            from .solver import apply_moves
            return apply_moves(state, move)
        from .fastn import tables
        permutation = tables(self.cube_size).perm(move)
        result = list(state)
        for src, dst in enumerate(permutation):
            result[dst] = state[src]
        return "".join(result)

    def _explicit_transition(self, previous, target, move):
        from .cube import _MOVE_RE, _SLICE, _ROTATION
        match = _MOVE_RE.fullmatch(move)
        if not match or self._apply_turn(previous,move)!=target:
            return None
        prefix,face,wide,suffix = match.groups()
        if face in _ROTATION:
            face,width,skip = _ROTATION[face],self.cube_size,0
        elif face in _SLICE:
            face,width,skip = _SLICE[face],self.cube_size-1,1
        else:
            width = int(prefix) if prefix else 2 if wide or face.islower() else 1
            skip = width-1 if prefix and not wide and face.isupper() else 0
            face = face.upper()
        if not 0<=skip<width<=self.cube_size:
            return None
        angle = -math.pi if "2" in suffix else math.pi/2 if "'" in suffix else -math.pi/2
        axis = self._AXES[face][0]
        orientation = self._logo_orientation
        next_orientation = orientation
        if self.cube_size==3:
            from .puzzles import _rotate, _dot
            white_face = next(f for i,f in enumerate(self._FACE_ORDER) if previous[i*9+4]=="U")
            n,u,v = self._AXES[white_face]
            signed = _dot(n,axis)
            selected = (width==self.cube_size and skip==0) or (signed>1-2*width/self.cube_size+1e-6 and (skip==0 or signed<1-2*skip/self.cube_size-1e-6))
            if selected:
                top = (tuple(-c for c in v),u,v,tuple(-c for c in u))[orientation]
                normal = _rotate(n,axis,angle)
                dest = max(self._FACE_ORDER,key=lambda f:_dot(self._AXES[f][0],normal))
                _n,du,dv = self._AXES[dest]
                options = (tuple(-c for c in dv),du,dv,tuple(-c for c in du))
                next_orientation = max(range(4),key=lambda i:_dot(options[i],_rotate(top,axis,angle)))
        self._logo_orientation = next_orientation
        return previous,axis,angle,target,orientation,next_orientation,(width,skip)

    def set_state(self, facelets, move=None):
        if facelets is not None and (len(facelets) != 6*self.cube_size**2 or any(c not in self._FACE_ORDER for c in facelets)):
            raise ValueError("Facelets do not match cube geometry")
        if facelets == self._facelets:
            return
        previous = self._facelets
        transition = None
        if previous and facelets and self.isVisible() and not QApplication.instance().property("reduceMotion"):
            if move:
                transition = self._explicit_transition(previous,facelets,move)
            for face in (self._FACE_ORDER if transition is None else ()):
                for suffix, angle in (("", -math.pi/2), ("'", math.pi/2), ("2", -math.pi)):
                    if self._apply_turn(previous, face + suffix) == facelets:
                        orientation = self._logo_orientation
                        white_center = self.cube_size == 3 and previous[self._FACE_ORDER.index(face)*9+4] == "U"
                        next_orientation = (orientation + (round(-angle/(math.pi/2)) if white_center else 0)) % 4
                        transition = (previous, self._AXES[face][0], angle, facelets, orientation, next_orientation, (1,0))
                        self._logo_orientation = next_orientation
                        break
                if transition:
                    break
            if transition is None and self.cube_size >= 4:
                for face in self._FACE_ORDER:
                    for width, skip, token in ((2,0,face+"w"),(2,1,"2"+face),(3,0,"3"+face+"w")):
                        for suffix, angle in (("",-math.pi/2),("'",math.pi/2),("2",-math.pi)):
                            if self._apply_turn(previous,token+suffix) == facelets:
                                transition = (previous,self._AXES[face][0],angle,facelets,0,0,(width,skip))
                                break
                        if transition:
                            break
                    if transition:
                        break
        self._facelets = facelets
        if not self._is_solved(facelets):
            self._solved_flash = None
        if transition:
            if self._turn is None:
                self._begin_turn(transition)
            elif len(self._turn_queue) < 2:
                self._turn_queue.append(transition)
            else:
                # Rendering must never build up seconds of delay behind BLE.
                self._turn_queue.clear()
                self._begin_turn(transition, duration=.085)
        else:
            self._turn = None
            self._turn_queue.clear()
            self._display_state = facelets
            if previous is None:
                self._logo_orientation = 0
            self._display_logo_orientation = self._logo_orientation
        if previous is None and facelets and self.isVisible() and not self._reduced_motion():
            self._arrival = time.perf_counter()
        if self._reduced_motion():
            self._advance_turn()
        else:
            self._ensure_frames()
        self.update()

    def _reduced_motion(self):
        return bool(QApplication.instance().property("reduceMotion"))

    def _ensure_frames(self):
        if self.isVisible() and not self._turn_timer.isActive() and not self._reduced_motion():
            self._last_frame = time.perf_counter()
            self._turn_timer.start()

    def _begin_turn(self, transition, started=None, duration=None):
        source, axis, angle, target, logo_start, logo_end, layers = transition
        duration = duration or (.19 if abs(angle) > 2 else .15)
        self._turn = (source, axis, angle, time.perf_counter() if started is None else started, duration, target, logo_start, logo_end, layers)
        self._display_state = source

    def _advance_turn(self):
        now = time.perf_counter()
        dt = min(.05, max(0.0, now-self._last_frame))
        self._last_frame = now
        if self._reduced_motion():
            self._turn = None
            self._turn_queue.clear()
            self._display_state = self._facelets
            self._display_logo_orientation = self._logo_orientation
            self._camera_reset = None
            self._velocity = (0.0, 0.0, 0.0)
            self._zoom = self._zoom_target
            self._arrival = self._solved_flash = None
            self._turn_timer.stop()
            self.update()
            return
        while self._turn and now-self._turn[3] >= self._turn[4]:
            finished = self._turn
            self._display_state = finished[5]
            self._display_logo_orientation = finished[7]
            self._turn = None
            if self._turn_queue:
                transition = self._turn_queue.popleft()
                self._begin_turn(transition, started=finished[3]+finished[4],
                                 duration=.09 if self._turn_queue else .13)
            elif self._is_solved(self._display_state) and not self._is_solved(finished[0]):
                self._solved_flash = now
        if self._camera_reset:
            start, target, began = self._camera_reset
            t = min(1.0, (now-began)/.38)
            ease = 1-(1-t)**3
            self._yaw, self._pitch, self._roll, self._zoom = tuple(a+(b-a)*ease for a,b in zip(start,target))
            if t == 1:
                self._camera_reset = None
        elif self._grab is None:
            self._yaw += self._velocity[0]*dt
            self._pitch += self._velocity[1]*dt
            self._roll += self._velocity[2]*dt
            damping = math.exp(-10*dt)
            self._velocity = tuple(v*damping if abs(v*damping) > .012 else 0.0 for v in self._velocity)
            self._zoom += (self._zoom_target-self._zoom)*(1-math.exp(-18*dt))
            if abs(self._zoom_target-self._zoom) < .001:
                self._zoom = self._zoom_target
        if self._arrival is not None and now-self._arrival >= .28:
            self._arrival = None
        if self._solved_flash is not None and now-self._solved_flash >= .65:
            self._solved_flash = None
        if not (self._turn or self._camera_reset or any(self._velocity) or
                self._zoom != self._zoom_target or self._arrival is not None or self._solved_flash is not None):
            self._turn_timer.stop()
        self.update()

    @staticmethod
    def _is_solved(state):
        area = len(state)//6 if state else 0
        return bool(area) and all(len(set(state[i:i+area])) == 1 for i in range(0,len(state),area))

    def set_highlight(self, face):
        self._highlight = face
        self.update()

    def _home_view(self):
        return (math.radians(-24), math.radians(22), 0.0, 1.0)

    def reset_view(self):
        target = self._home_view()
        self._velocity = (0.0,0.0,0.0)
        self._zoom_target = 1.0
        if self.isVisible() and not self._reduced_motion():
            start = tuple(b+((a-b+math.pi) % (2*math.pi)-math.pi) for a,b in zip(
                (self._yaw,self._pitch,self._roll), target[:3])) + (self._zoom,)
            self._camera_reset = (start, target, time.perf_counter())
            self._ensure_frames()
        else:
            self._yaw, self._pitch, self._roll, self._zoom = target
            self._camera_reset = None
        self.update()

    # ---- events -----------------------------------------------------
    def mousePressEvent(self, e):
        # Left drag orbits; right drag (or Shift+drag) rolls the view, so
        # any physical grip of the cube can be matched exactly.
        if e.button() in (Qt.LeftButton, Qt.RightButton):
            self._camera_reset = None
            self._velocity = (0.0,0.0,0.0)
            self._last_drag = time.perf_counter()
            self._grab = (e.x(), e.y(), e.button())
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._grab is None:
            return
        dx, dy = e.x() - self._grab[0], e.y() - self._grab[1]
        now = time.perf_counter()
        dt = max(.008, now-self._last_drag)
        self._last_drag = now
        self._grab = (e.x(), e.y(), self._grab[2])
        if self._grab[2] == Qt.RightButton or (e.modifiers() & Qt.ShiftModifier):
            self._roll += dx * 0.011
            velocity = (0.0,0.0,dx*.011/dt)
        else:
            self._yaw += dx * 0.011
            self._pitch += dy * 0.011
            velocity = (dx*.011/dt,dy*.011/dt,0.0)
        self._velocity = tuple(max(-3,min(3,v)) for v in velocity)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() in (Qt.LeftButton, Qt.RightButton):
            self._grab = None
            if self._reduced_motion() or time.perf_counter()-self._last_drag > .08:
                self._velocity = (0.0,0.0,0.0)
            self._ensure_frames()
            self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, e):
        self.reset_view()

    def wheelEvent(self, e):
        # Use the real delta: touchpads send many small deltas (a single
        # scroll gesture would saturate the zoom with a sign-only step), and
        # horizontal-only scrolls / zero-delta phase events must not zoom.
        delta = e.angleDelta().y()
        if delta:
            self._camera_reset = None
            self._zoom_target = max(0.6, min(2.0, self._zoom_target * (1.15 ** (delta / 120.0))))
            if self._reduced_motion():
                self._zoom = self._zoom_target
            self._ensure_frames()
            self.update()

    def hideEvent(self, event):
        self._turn_timer.stop()
        self._turn = self._camera_reset = None
        self._turn_queue.clear()
        self._display_state = self._facelets
        self._display_logo_orientation = self._logo_orientation
        self._velocity = (0.0,0.0,0.0)
        self._zoom = self._zoom_target
        self._arrival = self._solved_flash = None
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._facelets and not self._reduced_motion():
            self._arrival = time.perf_counter()
            self._ensure_frames()

    # ---- rendering ----------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._facelets:
            self._paint_cube(p)
        else:
            self._paint_placeholder(p)
        p.end()

    def _paint_placeholder(self, painter):
        size = self.cube_size
        scale = min(self.width(), self.height()) / 4.2
        cx, cy = self.width()/2, self.height()/2
        for face in self._FACE_ORDER:
            n, u, v = self._AXES[face]
            if self._rotate(*n)[2] <= 0:
                continue
            for row in range(size):
                for col in range(size):
                    points = []
                    for a, b in ((-1,-1),(1,-1),(1,1),(-1,1)):
                        point = tuple(n[i] + ((2*col+1-size)/size+a*.90/size)*u[i] + ((2*row+1-size)/size+b*.90/size)*v[i] for i in range(3))
                        x, y, _ = self._rotate(*point)
                        points.append(QPointF(cx+x*scale, cy-y*scale))
                    painter.setPen(QPen(QColor("#45433e"), 1))
                    painter.setBrush(QColor("#252420"))
                    painter.drawPolygon(QPolygonF(points))

    def _rotate(self, x, y, z):
        """Rotate a cube-space vector by yaw (about Y) then pitch (about X).

        Returns (vx, vy, depth) in view space: +depth points towards the
        viewer, so a face with a positive depth is visible."""
        cy, sy = math.cos(self._yaw), math.sin(self._yaw)
        vx = x * cy + z * sy
        z1 = -x * sy + z * cy
        cp, sp = math.cos(self._pitch), math.sin(self._pitch)
        vy = y * cp - z1 * sp
        depth = y * sp + z1 * cp
        if self._roll:
            cr, sr = math.cos(self._roll), math.sin(self._roll)
            vx, vy = vx * cr - vy * sr, vx * sr + vy * cr
        return vx, vy, depth

    def _paint_cube(self, p):
        r = self.rect().adjusted(8, 8, -8, -8)
        # any rotation of a unit cube fits in a circle of radius sqrt(3)
        s = min(r.width(), r.height()) / 3.466 * self._zoom
        if self._arrival is not None:
            progress = min(1.0, (time.perf_counter()-self._arrival)/.28)
            ease = 1-(1-progress)**3
            s *= .96+.04*ease
            p.setOpacity(.35+.65*ease)
        cx = r.x() + r.width() / 2.0
        cy = r.y() + r.height() / 2.0
        if self._solved_flash is not None:
            progress = min(1.0, (time.perf_counter()-self._solved_flash)/.65)
            glow = QRadialGradient(QPointF(cx, cy), s*1.65)
            glow.setColorAt(0, QColor(244,204,12,int(26*math.sin(math.pi*progress))))
            glow.setColorAt(1, QColor(244,204,12,0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(cx,cy),s*1.65,s*1.65)

        # Soft contact shadow gives the puzzle depth without a heavy frame.
        shadow = QRadialGradient(QPointF(cx, cy + s * 0.79), s * 0.62)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 125))
        shadow.setColorAt(0.62, QColor(0, 0, 0, 58))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(shadow))
        p.drawEllipse(QRectF(cx - s * 0.65, cy + s * 0.55,
                             s * 1.3, s * 0.48))

        self._paint_turn(p, cx, cy, s)

    def _paint_turn(self, painter, cx, cy, scale):
        """Rotate the actual sticker geometry of one layer, preserving colors."""
        size = self.cube_size
        if self._turn:
            source, axis, angle, started, duration, _target, logo_orientation, _logo_end, layers = self._turn
            progress = min(1.0, max(0.0, (time.perf_counter()-started)/duration))
            # Quintic easing settles into place without an artificial bounce.
            progress = progress**3 * (10-15*progress+6*progress*progress)
            angle *= progress
        else:
            source, axis, angle = self._display_state or self._facelets, (0,1,0), 0.0
            logo_orientation = self._display_logo_orientation
            layers = (1,0)
        lower, upper = 1-2*layers[0]/size, 1-2*layers[1]/size
        ca, sa = math.cos(angle), math.sin(angle)

        def turn(point):
            dot = sum(a*b for a, b in zip(axis, point))
            cross = (axis[1]*point[2]-axis[2]*point[1],
                     axis[2]*point[0]-axis[0]*point[2],
                     axis[0]*point[1]-axis[1]*point[0])
            return tuple(point[i]*ca + cross[i]*sa + axis[i]*dot*(1-ca) for i in range(3))

        surfaces = []
        for fi, face in enumerate(self._FACE_ORDER):
            n, u, v = self._AXES[face]
            for row in range(size):
                for col in range(size):
                    center = tuple(n[i] + (2*col+1-size)/size*u[i] + (2*row+1-size)/size*v[i] for i in range(3))
                    signed = sum(center[i]*axis[i] for i in range(3))
                    moving = bool(self._turn) and ((layers[0]==size and layers[1]==0) or (signed > lower+1e-6 and (layers[1] == 0 or signed < upper-1e-6)))
                    normal = turn(n) if moving else n
                    vx, vy, depth = self._rotate(*normal)
                    if depth <= 0:
                        continue
                    rotated_center = turn(center) if moving else center
                    distance = self._rotate(*rotated_center)[2]
                    polygons = []
                    for inset in (1.0, self._STICKER):
                        corners = []
                        for a, b in ((-1,-1), (1,-1), (1,1), (-1,1)):
                            point = tuple(center[i] + inset/size*(a*u[i]+b*v[i]) for i in range(3))
                            x, y, _ = self._rotate(*(turn(point) if moving else point))
                            corners.append(QPointF(cx+x*scale, cy-y*scale))
                        polygons.append(QPolygonF(corners))
                    color = QColor(FACE_COLORS[source[fi*size*size+row*size+col]])
                    light = self._LIGHT
                    length = math.sqrt(sum(c*c for c in light))
                    brightness = .62 + .38*max(0, (vx*light[0]+vy*light[1]+depth*light[2])/length)
                    color.setRgb(*(min(255, int(c*brightness)) for c in (color.red(), color.green(), color.blue())))
                    surfaces.append((distance, polygons, color, row, col, size == 3 and row == col == 1 and source[fi*9+4] == "U", face))
        if self._turn:
            # Dark cut surfaces prevent a turn from exposing a hollow cube.
            u = next(n for n in ((1,0,0),(0,1,0),(0,0,1)) if not sum(a*b for a,b in zip(axis,n)))
            v = (axis[1]*u[2]-axis[2]*u[1], axis[2]*u[0]-axis[0]*u[2], axis[0]*u[1]-axis[1]*u[0])
            for boundary, sign in ((lower,1),(upper,-1)):
                if abs(boundary) >= 1:
                    continue
                center = tuple(a*boundary for a in axis)
                for rotating in (False, True):
                    normal = tuple(a*sign*(-1 if rotating else 1) for a in axis)
                    if self._rotate(*normal)[2] <= 0:
                        continue
                    points = []
                    for a,b in ((-1,-1),(1,-1),(1,1),(-1,1)):
                        point = tuple(center[i]+a*u[i]+b*v[i] for i in range(3))
                        x,y,_ = self._rotate(*(turn(point) if rotating else point))
                        points.append(QPointF(cx+x*scale,cy-y*scale))
                    polygon = QPolygonF(points)
                    surfaces.append((self._rotate(*center)[2], [polygon,polygon], None, 0,0,False,None))
        surfaces.sort(key=lambda item: (item[2] is not None, item[0]))
        for _distance, (backing, sticker), color, row, col, logo, face in surfaces:
            painter.setPen(QPen(QColor("#191919"), 1))
            painter.setBrush(QColor("#101010"))
            painter.drawPolygon(backing)
            if color is None:
                continue
            painter.setBrush(color)
            path = self._sticker_path(sticker, row, col, size)
            painter.drawPath(path)
            painter.save()
            painter.setClipPath(path)
            sheen = QLinearGradient(path.boundingRect().topLeft(),path.boundingRect().bottomRight())
            sheen.setColorAt(0,QColor(255,255,255,23))
            sheen.setColorAt(.55,QColor(255,255,255,0))
            sheen.setColorAt(1,QColor(0,0,0,17))
            painter.fillRect(path.boundingRect(),QBrush(sheen))
            painter.restore()
            if logo:
                self._paint_logo(painter, sticker, logo_orientation)
            if face == self._highlight:
                painter.setPen(QPen(QColor(244,204,12,145),1.6))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)

    @staticmethod
    def _sticker_path(corners, row, col, size=3):
        # Giiker-style curved inner corners: circular center, petal-shaped edges.
        rounding = [.13]*4
        if size != 3:
            rounding = [.19]*4
        elif row == col == 1:
            rounding = [.47]*4
        elif row == 0 and col == 1:
            rounding[2] = rounding[3] = .43
        elif row == 2 and col == 1:
            rounding[0] = rounding[1] = .43
        elif col == 0 and row == 1:
            rounding[1] = rounding[2] = .43
        elif col == 2 and row == 1:
            rounding[0] = rounding[3] = .43
        else:
            rounding[{(0,0):2, (0,2):3, (2,0):1, (2,2):0}[(row,col)]] = .40
        entries, exits = [], []
        for index, corner in enumerate(corners):
            prev, nxt = corners[(index-1)%4], corners[(index+1)%4]
            fraction = rounding[index]
            entries.append(corner + (prev-corner)*fraction)
            exits.append(corner + (nxt-corner)*fraction)
        path = QPainterPath()
        path.moveTo(entries[0])
        for index, corner in enumerate(corners):
            path.quadTo(corner, exits[index])
            path.lineTo(entries[(index+1)%4])
        path.closeSubpath()
        return path

    def _paint_logo(self, painter, corners, orientation=0):
        if self._logo.isNull():
            return
        corners = list(corners)
        corners = corners[orientation:] + corners[:orientation]
        center = sum((point.x() for point in corners))/4, sum((point.y() for point in corners))/4
        target = QPolygonF([QPointF(center[0]+(q.x()-center[0])*.68,
                                   center[1]+(q.y()-center[1])*.68) for q in corners])
        size = self._logo.width()
        source = QPolygonF([QPointF(0,0), QPointF(size,0), QPointF(size,size), QPointF(0,size)])
        transform = QTransform()
        if QTransform.quadToQuad(source, target, transform):
            painter.save()
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.setTransform(transform, True)
            painter.drawImage(QRectF(0,0,size,size), self._logo)
            painter.restore()



class Toast(QLabel):
    """Small pop-up message shown over the timer."""

    def __init__(self, parent):
        QLabel.__init__(self, parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._opacity_animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._opacity_animation.finished.connect(self._opacity_finished)
        self._position_animation = QPropertyAnimation(self, b"pos", self)
        self._position_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._dismissing = False

    def show_message(self, text, ms=3000):
        self._opacity_animation.stop()
        self._position_animation.stop()
        self._dismissing = False
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        if par is not None:
            self.move(int((par.width() - self.width()) / 2), 14)
        self.raise_()
        self.show()
        if QApplication.instance().property("reduceMotion"):
            self._effect.setOpacity(1.0)
        else:
            target = self.pos()
            self.move(target+QPointF(0,6).toPoint())
            self._effect.setOpacity(0.0)
            self._opacity_animation.setDuration(160)
            self._opacity_animation.setStartValue(0.0)
            self._opacity_animation.setEndValue(1.0)
            self._position_animation.setDuration(180)
            self._position_animation.setStartValue(self.pos())
            self._position_animation.setEndValue(target)
            self._opacity_animation.start()
            self._position_animation.start()
        self._timer.start(ms)

    def _dismiss(self):
        self._dismissing = True
        self._position_animation.stop()
        self._opacity_animation.stop()
        if QApplication.instance().property("reduceMotion"):
            self.hide()
            return
        self._opacity_animation.setDuration(120)
        self._opacity_animation.setStartValue(self._effect.opacity())
        self._opacity_animation.setEndValue(0.0)
        self._opacity_animation.start()

    def _opacity_finished(self):
        if self._dismissing:
            self.hide()

    def hideEvent(self, event):
        self._timer.stop()
        self._opacity_animation.stop()
        self._position_animation.stop()
        super().hideEvent(event)
