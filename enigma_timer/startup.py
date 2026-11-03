"""Finite branded launch animation and one cold-start hand-off to the workspace."""
import math
import os
from PyQt5.QtCore import Qt,QRectF,QElapsedTimer,QTimer,QObject,pyqtSignal
from PyQt5.QtGui import (QColor,QPainter,QImage,QPen,QPainterPath,QRadialGradient,QFont)
from PyQt5.QtWidgets import QWidget,QApplication
from . import theme
from .brand import ROOT,app_icon
from .i18n import tr


def _phase(ms,start,duration):
    return max(0.0,min(1.0,(ms-start)/duration))


def _ease(t):
    return 1-(1-t)**3


class StartupIntro(QWidget):
    finished=pyqtSignal()
    cancelled=pyqtSignal()
    DURATION_MS=3600
    REDUCED_DURATION_MS=1100

    def __init__(self,reduced_motion=False,parent=None):
        super().__init__(parent,Qt.SplashScreen|Qt.FramelessWindowHint)
        self.setWindowTitle(tr("startup_intro_title"))
        self.tagline=tr("startup_intro_tagline")
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground,True)
        self.setAttribute(Qt.WA_QuitOnClose,False)
        self.reduced_motion=bool(reduced_motion)
        self.duration_ms=self.REDUCED_DURATION_MS if self.reduced_motion else self.DURATION_MS
        self._clock=QElapsedTimer()
        self._started=False
        self._done=False
        self._logo=QImage(os.path.join(ROOT,"assets","icon.png"))
        self._wordmark=QImage(os.path.join(ROOT,"assets","header.png"))
        self._frames=QTimer(self)
        self._frames.setInterval(16)
        self._frames.setTimerType(Qt.PreciseTimer)
        self._frames.timeout.connect(self._tick)
        self._deadline=QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.timeout.connect(self.finish)
        self.setFocusPolicy(Qt.StrongFocus)
        self.resize(800,500)
        screen=QApplication.primaryScreen()
        if screen:
            available=screen.availableGeometry()
            self.resize(min(800,available.width()-32),min(500,available.height()-32))
            self.move(available.center()-self.rect().center())

    def start(self):
        if self._started or self._done:
            return
        self._started=True
        self._clock.start()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._frames.start()
        self._deadline.start(self.duration_ms)

    def _tick(self):
        if self._clock.elapsed()>=self.duration_ms:
            self.finish()
        else:
            self.update()

    def finish(self):
        if self._done:
            return
        self._done=True
        self._frames.stop()
        self._deadline.stop()
        # Create/show the workspace before closing the last launch window.
        self.finished.emit()
        self.close()

    def closeEvent(self,event):
        self._frames.stop()
        self._deadline.stop()
        if not self._done:
            self._done=True
            self.cancelled.emit()
        super().closeEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_F4 and event.modifiers() & Qt.AltModifier:
            self.close()
            return
        event.accept()

    def mousePressEvent(self,event):
        event.accept()

    def paintEvent(self,event):
        painter=QPainter(self)
        self.paint_frame(painter,self._clock.elapsed() if self._clock.isValid() else 0)
        painter.end()

    def paint_frame(self,painter,ms):
        """Deterministic frame rendering, also used for tests and video previews."""
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.save()
        painter.scale(self.width()/800.0,self.height()/500.0)
        frame=QRectF(1,1,798,498)
        path=QPainterPath()
        path.addRoundedRect(frame,22,22)
        painter.setClipPath(path)
        painter.fillRect(frame,QColor("#101010"))
        glow=QRadialGradient(400,211,340)
        glow.setColorAt(0,QColor("#23211b"))
        glow.setColorAt(.55,QColor("#171615"))
        glow.setColorAt(1,QColor("#101010"))
        painter.fillRect(frame,glow)
        reduced=self.reduced_motion
        appear=_ease(_phase(ms,60,270 if reduced else 650))
        depart=1-_phase(ms,self.duration_ms-260,260)
        painter.setOpacity(appear*depart)
        if not reduced:
            pulse=math.sin(math.pi*_phase(ms,200,2300))
            halo=QRadialGradient(400,204,142)
            halo.setColorAt(0,QColor(244,204,12,int(18*pulse)))
            halo.setColorAt(1,QColor(244,204,12,0))
            painter.fillRect(QRectF(230,34,340,340),halo)
            # A single timed orbit echoes the stopwatch inside the logo.
            orbit=_ease(_phase(ms,180,1100))
            painter.setPen(QPen(QColor(244,204,12,int(70*(1-_phase(ms,1300,800)))),1.1,Qt.SolidLine,Qt.RoundCap))
            painter.drawArc(QRectF(281,72,238,238),int((105-55*orbit)*16),int(-250*orbit*16))
        logo_ease=1.0 if reduced else _ease(_phase(ms,120,1050))
        size=188 if reduced else 164+24*logo_ease
        y=94 if reduced else 105-11*logo_ease
        painter.setOpacity(appear*depart)
        if not self._logo.isNull():
            painter.drawImage(QRectF(400-size/2,y,size,size),self._logo)
        else:
            # A damaged image asset must not leave startup permanently blank.
            painter.setPen(QColor(theme.ACCENT))
            painter.drawText(QRectF(200,120,400,100),Qt.AlignCenter,"ENIGMA")
        word_phase=1.0 if reduced else _ease(_phase(ms,800,850))
        painter.setOpacity(appear*word_phase*depart)
        word_y=310 if reduced else 320-10*word_phase
        if not self._wordmark.isNull():
            painter.save()
            reveal=1.0 if reduced else _ease(_phase(ms,850,750))
            painter.setClipRect(QRectF(400-155*reveal,word_y,310*reveal,94))
            painter.drawImage(QRectF(245,word_y,310,46),self._wordmark,QRectF(112,6,352,52))
            painter.drawImage(QRectF(344,word_y+59,112,25),self._wordmark,QRectF(112,65,142,32))
            painter.restore()
        else:
            font=QFont(theme.ui_font())
            font.setPixelSize(33)
            font.setLetterSpacing(QFont.AbsoluteSpacing,7)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT))
            painter.drawText(QRectF(190,word_y,420,50),Qt.AlignCenter,"ENIGMA CUBE")
        caption_phase=1.0 if reduced else _ease(_phase(ms,1600,650))
        painter.setOpacity(appear*caption_phase*depart)
        font=QFont(theme.ui_font())
        font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(QRectF(120,417,560,24),Qt.AlignCenter,self.tagline)
        painter.setOpacity(depart)
        painter.setPen(QPen(QColor("#34312a"),1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(frame,22,22)
        painter.restore()


class StartupController(QObject):
    """The intro belongs to a process launch, never to a window show event."""
    def __init__(self,app,store,window_factory,intro_factory=StartupIntro):
        super().__init__(app)
        self.app,self.store=app,store
        self.window_factory,self.intro_factory=window_factory,intro_factory
        self.window=None
        self.intro=None
        self._started=False

    def start(self):
        if self._started:
            return
        self._started=True
        self.app.setProperty("reduceMotion",bool(self.store.settings.get("reduce_motion",False)))
        if self.store.settings.get("startup_intro",True):
            self.app.setQuitOnLastWindowClosed(False)
            self.intro=self.intro_factory(reduced_motion=bool(self.store.settings.get("reduce_motion",False)))
            self.intro.finished.connect(self._show_workspace)
            self.intro.cancelled.connect(self.app.quit)
            self.intro.start()
        else:
            self._show_workspace()

    def _show_workspace(self):
        if self.window is not None:
            return
        self.window=self.window_factory(self.store)
        if getattr(self.window,"start_maximized",False):
            self.window.showMaximized()
        else:
            self.window.show()
        self.app.setQuitOnLastWindowClosed(True)

    def activate(self):
        target=self.window or self.intro
        if target is None:
            return
        modal=self.app.activeModalWidget()
        if modal and target is self.window:
            target=modal
        if target.isMinimized():
            target.setWindowState(target.windowState() & ~Qt.WindowMinimized)
            target.show()
        else:
            target.show()
        target.raise_()
        target.activateWindow()
