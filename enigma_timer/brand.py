"""Shared branding at both native title-bar and cube-sticker sizes."""
import os
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QImage, QPixmap

ROOT = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(__file__))


def logo_image():
    return QImage(os.path.join(ROOT, "assets", "icon.png"))


def info_icon():
    """A consistent information symbol independent of installed font glyphs."""
    from PyQt5.QtCore import QPointF, QRectF
    from PyQt5.QtGui import QColor, QPainter, QPen
    from . import theme
    icon = QIcon()
    for mode, color in ((QIcon.Normal, theme.MUTED),
                        (QIcon.Active, theme.ACCENT),
                        (QIcon.Disabled, theme.FAINT)):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        pixmap.setDevicePixelRatio(2)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(color), 1.35, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(QRectF(1.5, 1.5, 13, 13))
        painter.drawLine(QPointF(8, 7.3), QPointF(8, 11))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(8, 4.8), .8, .8)
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


def app_icon():
    icon = QIcon()
    original = logo_image()
    if original.isNull():
        return icon
    # Native title bars request 16–32 px images too. Use the actual logo at
    # every size instead of substituting a hand-drawn cube for small icons.
    for size in (16, 20, 24, 32, 48, 64, 128, 256, 512):
        image = original.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon.addPixmap(QPixmap.fromImage(image))
    return icon
