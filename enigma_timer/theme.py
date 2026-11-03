"""Colours and the application style sheet."""

import os
import sys

from PyQt5.QtGui import QFontDatabase
from PyQt5.QtCore import Qt

# Shared proportions. Dense controls (timer, sticker editor) use the same
# palette and type roles, with a smaller spacing variant where necessary.
SPACE = 8
PAGE_GAP = 16
PAGE_MARGIN = 24
CARD_MARGIN = 20
SIDEBAR_WIDTH = 224


def page(widget,layout):
    widget.setObjectName("workspacePage")
    widget.setAttribute(Qt.WA_StyledBackground,True)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(PAGE_GAP)


def window_layout(layout):
    layout.setContentsMargins(PAGE_MARGIN,16,PAGE_MARGIN,PAGE_MARGIN)
    layout.setSpacing(12)


def prepare_dialog(dialog):
    if dialog.layout() is not None:
        dialog.layout().setContentsMargins(PAGE_MARGIN,PAGE_MARGIN,PAGE_MARGIN,PAGE_MARGIN)
        dialog.layout().setSpacing(12)


def visual_stage(view):
    from PyQt5.QtWidgets import QFrame, QVBoxLayout
    frame = QFrame()
    frame.setObjectName("visualStage")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.addWidget(view)
    return frame


def fit_to_screen(window):
    """Keep restored/default windows inside the current monitor's work area."""
    screen = window.screen()
    if screen is None or window.isFullScreen() or window.isMaximized():
        return
    available = screen.availableGeometry().adjusted(12, 12, -12, -40)
    window.resize(min(window.width(), available.width()), min(window.height(), available.height()))
    geometry = window.geometry()
    x = max(available.left(), min(geometry.x(), available.right()-geometry.width()+1))
    y = max(available.top(), min(geometry.y(), available.bottom()-geometry.height()+1))
    window.move(x, y)

_ROOT = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEVRON = os.path.join(_ROOT, "assets", "chevron.png").replace("\\", "/")
CHECKMARK = os.path.join(_ROOT, "assets", "check.png").replace("\\", "/")

# Enigma Cube's original black, yellow, grey, and white palette, shared by
# every page, chart, popup, and detached window.
BG = "#121111"
PANEL = "#191817"
PANEL2 = "#232120"
BORDER = "#302d2b"
TEXT = "#f0efed"
MUTED = "#a39d99"
FAINT = "#716c68"
SCRAMBLE = "#d6d2cd"
ACCENT = "#f4cc0c"
ACCENT_DARK = "#352c07"
READY = "#2ee07a"
HOLD = "#ff6871"
INSPECT = "#ffb020"
BLUE = "#c2bdb8"
DNF_RED = "#ff6871"
STREAK_BG = "#352c07"   # active day-streak chip
STREAK_FG = "#f4cc0c"
TODAY_BG = "#25200b"    # "trained today" chip
DONE_GREEN = "#3ddc84"  # learned case / success (matches streak green family)
SUCCESS_BG = "#15382c"
ERROR_BG = "#3d2026"
CHIP_BG = "#302d2b"

_PREFERRED = ["Segoe UI", "SF Pro Display", "Helvetica Neue", "Inter",
              "Roboto", "Ubuntu", "Noto Sans", "Arial"]
_MONO = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "JetBrains Mono",
         "DejaVu Sans Mono", "Courier New"]

_cache = {}


def _pick(candidates, key):
    if key not in _cache:
        families = set(QFontDatabase().families())
        _cache[key] = next((f for f in candidates if f in families), "")
    return _cache[key]


def ui_font():
    return _pick(_PREFERRED, "ui")


def mono_font():
    return _pick(_MONO, "mono")


def stylesheet():
    family = ui_font()
    fam = ('font-family: "%s";' % family) if family else ""
    return """
* { %(fam)s }
QMainWindow, QWidget#central, QWidget#workspacePage { background: %(BG)s; }
QWidget { color: %(TEXT)s; font-size: 14px; }
QToolTip { background: %(PANEL2)s; color: %(TEXT)s; border: 1px solid %(BORDER)s;
           padding: 7px 10px; border-radius: 8px; }

/* cards: no outlines, just a slightly lighter surface */
QFrame#panel { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 18px; }
QWidget#timerSurface { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 22px; }
QWidget#scrambleSurface { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 16px; }
QFrame#visualStage { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 18px; }
QFrame#statMetric { background: %(BG)s; border: 1px solid %(BORDER)s; border-radius: 12px; }
QPushButton#statValue { background: transparent; border: none; padding: 0; text-align: left; font-weight: 650; min-height: 30px; }
QPushButton#statValue:hover { background: %(PANEL2)s; border-radius: 5px; }
QPushButton#statsMore { padding: 2px 0; font-size: 12px; text-align: left; }
QLabel#statCount { color: %(MUTED)s; background: %(PANEL2)s; padding: 3px 8px; border-radius: 8px; font-size: 12px; }
QFrame#settingGroup { background: %(BG)s; border: 1px solid %(BORDER)s; border-radius: 16px; }
QFrame#welcomeTip { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 12px; }
QLabel#welcomeIcon { color: %(ACCENT)s; background: %(ACCENT_DARK)s; border-radius: 19px;
                     font-size: 18px; font-weight: 700; }
QPushButton#welcomeSkip { background: transparent; color: %(MUTED)s; border-color: transparent; }
QPushButton#welcomeSkip:hover { color: %(TEXT)s; background: %(PANEL2)s; }
QFrame#welcomeDot { border: none; }
QLabel#muted { color: %(MUTED)s; }
QLabel#dialogTitle { font-size: 18px; font-weight: 650; }
QLabel#pageHeading { font-size: 26px; font-weight: 650; padding: 0 0 8px 0; }
QLabel#cardTitle { font-size: 18px; font-weight: 650; }
QLabel#labelStrong { font-size: 14px; font-weight: 650; }
QLabel#detailTitle { font-size: 20px; font-weight: 650; }
QLabel#heroTitle { font-size: 30px; font-weight: 700; }
QLabel#bodyText { color: %(TEXT)s; font-size: 14px; }
QLabel#caption { color: %(MUTED)s; font-size: 12px; }
QLabel#algorithmHeading { color: %(ACCENT)s; font-size: 28px; font-weight: 650; padding: 8px 0; }
QLabel#algorithmText { color: %(ACCENT)s; font-size: 18px; font-weight: 600; padding: 8px 0; }
QLabel#metricLarge { color: %(ACCENT)s; font-size: 40px; font-weight: 650; }
QLabel#coachText { color: %(ACCENT)s; background: %(ACCENT_DARK)s; border-radius: 10px; font-size: 14px; padding: 10px 12px; }
QLabel#statusText { color: %(ACCENT)s; font-size: 14px; padding: 8px 0; }
QLabel#errorText { color: %(DNF_RED)s; font-size: 13px; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: %(PANEL2)s; color: %(MUTED)s; padding: 10px 22px;
               border: 1px solid %(BORDER)s; min-width: 95px; margin-right: 6px; border-radius: 10px; }
QTabBar::tab:selected { background: %(ACCENT_DARK)s; color: %(ACCENT)s; border-color: #665727; }
QTabBar::tab:hover { color: %(TEXT)s; }
QListWidget#commandList { background: transparent; border: none; outline: none; }
QListWidget#commandList::item { padding: 12px 14px; border-radius: 10px; margin: 2px 0; }
QListWidget#commandList::item:selected { background: %(ACCENT_DARK)s; color: %(ACCENT)s; }
QLabel#dialogStatus { color: %(MUTED)s; font-size: 13px; }
QLabel#chip { background: %(CHIP_BG)s; border-radius: 12px; padding: 5px 12px;
              font-size: 13px; font-weight: 700; }
QLabel#sectionTitle { color: %(MUTED)s; font-size: 12px; font-weight: 650; }
QLabel#toast { background: %(PANEL2)s; color: %(ACCENT)s; border: 1px solid %(BORDER)s;
               border-radius: 16px;
               padding: 8px 20px; font-weight: 600; font-size: 14px; }

/* buttons are quiet text by default */
QPushButton { background: transparent; border: 1px solid transparent; border-radius: 9px;
              padding: 7px 12px; min-height: 20px; color: %(MUTED)s; }
QPushButton:hover { color: %(TEXT)s; background: %(PANEL2)s; border-color: %(BORDER)s; }
QPushButton:pressed { color: %(ACCENT)s; background: %(ACCENT_DARK)s; }
QPushButton:disabled { color: %(FAINT)s; }
QPushButton:focus { border-color: %(ACCENT)s; }
QPushButton:checked { color: %(ACCENT)s; }
QPushButton:focus, QToolButton:focus, QComboBox:focus { border: 1px solid %(ACCENT)s; }

QPushButton#puzzle { padding: 6px 7px 5px 7px; font-weight: 600; font-size: 13px;
                     border-radius: 0; border-bottom: 2px solid transparent; min-width: 30px; }
QPushButton#puzzle:hover { background: transparent; color: %(TEXT)s; }
QPushButton#puzzle:checked { color: %(TEXT)s; border-bottom: 2px solid %(ACCENT)s; }
QPushButton#pen { min-width: 40px; font-weight: 700; font-size: 13px;
                  background: %(PANEL)s; border-color: %(BORDER)s; }
QPushButton#pen:checked { background: %(ACCENT_DARK)s; color: %(ACCENT)s;
                          border-color: #66552b; }
QPushButton#icon { padding: 5px 9px; font-size: 16px; color: %(FAINT)s; }
QPushButton#icon:hover { color: %(TEXT)s; background: %(PANEL2)s; }
QPushButton#icon:checked { color: %(ACCENT)s; }
QPushButton#tab { padding: 6px 9px; font-size: 11px; font-weight: 700;
                   border-radius: 0; border-bottom: 2px solid transparent; }
QPushButton#tab:hover { background: transparent; color: %(TEXT)s; }
QPushButton#tab:checked { color: %(ACCENT)s; border-bottom-color: %(ACCENT)s; }

QPushButton#event { font-size: 14px; font-weight: 700; padding: 8px 14px; color: %(TEXT)s;
                    background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 11px; }
QPushButton#event:hover { background: %(PANEL2)s; }
QPushButton#event::menu-indicator { image: none; width: 0; }
QPushButton#windows { font-size: 14px; font-weight: 600; padding: 7px 12px; color: %(MUTED)s;
                      background: transparent; border-radius: 9px; }
QPushButton#windows:hover { background: %(PANEL2)s; color: %(TEXT)s; }
QPushButton#windows::menu-indicator { image: none; width: 0; }
QPushButton#cube { font-size: 15px; padding: 6px 9px; color: %(FAINT)s; }
QPushButton#cube:hover { color: %(TEXT)s; }
QPushButton#cube:checked { color: %(READY)s; }
QLabel#keycap { background: %(PANEL2)s; color: %(TEXT)s; border-radius: 6px; padding: 2px 8px;
                font-size: 12px; font-weight: 600; }
QLabel#empty { color: %(MUTED)s; font-size: 13px; }
QPushButton#pin { padding: 4px 10px; font-size: 12px; color: %(MUTED)s; border-radius: 8px; }
QPushButton#pin:hover { color: %(TEXT)s; background: %(PANEL2)s; }
QPushButton#pin:checked { color: #111; background: %(ACCENT)s; }
QFrame#steprow { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 14px; }
QFrame#steprow:hover { background: %(PANEL2)s; border-color: #514c48; }
QProgressBar { background: %(BORDER)s; border: none; border-radius: 4px; min-height: 7px; }
QProgressBar::chunk { background: %(ACCENT)s; border-radius: 4px; }
QPushButton#nav { font-size: 13px; font-weight: 650; padding: 8px 14px; color: %(MUTED)s;
                  min-height: 22px; border-radius: 11px; }
QPushButton#nav:hover { background: %(PANEL)s; color: %(TEXT)s; }
QPushButton#nav:checked { color: %(ACCENT)s; background: %(ACCENT_DARK)s; border-color: #544622; }
QPushButton#primary { background: %(ACCENT)s; color: #15130d; font-weight: 800; padding: 9px 20px;
                      border: 1px solid %(ACCENT)s; border-radius: 11px; }
QPushButton#primary:hover { background: #ffda66; color: #15130d; border-color: #ffda66; }
QPushButton#primary:disabled { background: %(PANEL2)s; color: %(FAINT)s; border-color: %(BORDER)s; }
QPushButton#seg { background: %(PANEL2)s; color: %(MUTED)s; padding: 8px 13px;
                  border-color: %(BORDER)s; }
QPushButton#seg:checked { background: %(ACCENT_DARK)s; color: %(ACCENT)s; }
QPushButton#rate { background: %(PANEL2)s; color: %(TEXT)s; padding: 10px 16px; font-weight: 700;
                   border: 1px solid %(BORDER)s; border-radius: 11px; }
QPushButton#rate:hover { background: #2e2b29; border-color: #514c48; }
QPushButton#rate:disabled { color: %(MUTED)s; background: %(PANEL)s; }

QListWidget#levels, QListWidget#grid { background: transparent; border: none; outline: 0; }
QListView::item { border-radius: 10px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QListWidget#scanList { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 12px;
                       outline: 0; padding: 6px; }
QListWidget#scanList::item { padding: 9px 12px; border-radius: 8px; color: %(TEXT)s;
                             font-size: 14px; font-weight: 600; }
QListWidget#scanList::item:hover { background: #2e2b29; }
QListWidget#scanList::item:selected { background: %(ACCENT_DARK)s; color: %(ACCENT)s; }
QListWidget#plainlist { background: transparent; border: none; outline: 0; font-size: 14px; }
QListWidget#plainlist::item { padding: 7px 11px; border-radius: 9px; color: %(MUTED)s; }
QListWidget#plainlist::item:hover { background: %(PANEL2)s; color: %(TEXT)s; }
QListWidget#plainlist::item:selected { background: %(ACCENT_DARK)s; color: %(ACCENT)s; }
QListWidget#levels::item, QListWidget#grid::item { background: transparent; border: none; }
QTextBrowser { background: transparent; border: none; color: %(SCRAMBLE)s; font-size: 15px;
               selection-background-color: %(ACCENT)s; selection-color: #111; }
QTextBrowser a { color: %(ACCENT)s; }
QTextBrowser h1, QTextBrowser h2 { color: %(TEXT)s; }

/* real buttons inside dialogs */
QDialog QPushButton { background: %(PANEL2)s; color: %(TEXT)s; padding: 8px 16px; font-weight: 600;
                      border: 1px solid %(BORDER)s; }
QDialog QPushButton:hover { background: #2e2b29; }
QDialog QPushButton:default { background: %(ACCENT)s; border-color: %(ACCENT)s;
                               color: #15130d; }
QDialog QPushButton#pen:checked { background: %(ACCENT_DARK)s; color: %(ACCENT)s; }

QToolButton { background: transparent; border: 1px solid transparent; border-radius: 9px;
              padding: 5px 9px; color: %(FAINT)s; font-size: 16px; }
QToolButton:hover { color: %(TEXT)s; background: %(PANEL2)s; border-color: %(BORDER)s; }
QToolButton#helpIcon { padding: 0; border: 1px solid transparent; border-radius: 8px; }
QToolButton#helpIcon:hover, QToolButton#helpIcon:focus { background: %(ACCENT_DARK)s; border-color: #665727; }
QToolButton#helpIcon:pressed { background: %(PANEL2)s; }
QToolButton::menu-indicator { image: none; }

QComboBox { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 9px;
            padding: 6px 10px; font-weight: 600; font-size: 14px; min-height: 24px; }
QComboBox:hover { background: %(PANEL2)s; }
QComboBox:focus { border-color: %(ACCENT)s; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url(%(CHEVRON)s); width: 10px; height: 6px; }
QComboBox QAbstractItemView { background: %(PANEL2)s; border: none; padding: 4px;
            selection-background-color: %(ACCENT)s; selection-color: #111; outline: 0; }
QDialog QComboBox { background: %(BG)s; font-size: 14px; font-weight: 400; }

QMenu { background: %(PANEL)s; border: 1px solid %(BORDER)s; padding: 6px; border-radius: 12px; }
QMenu::item { padding: 8px 24px; border-radius: 7px; }
QMenu::item:selected { background: %(PANEL2)s; color: %(ACCENT)s; }
QMenu::separator { height: 1px; background: %(BORDER)s; margin: 5px 10px; }

QTableWidget { background: transparent; border: none; gridline-color: transparent;
               selection-background-color: transparent; outline: 0; }
QTableWidget::item { padding: 2px 6px; border: none; }
QTableWidget::item:hover { background: %(PANEL2)s; }
QTableWidget::item:selected { color: %(ACCENT)s; background: %(ACCENT_DARK)s; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section { background: transparent; color: %(MUTED)s; border: none;
                       padding: 2px 6px 6px 6px; font-size: 11px; font-weight: 600; }
QTableCornerButton::section { background: transparent; border: none; }

QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
QScrollBar::handle:vertical { background: #45413e; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #625c56; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 6px; margin: 2px; }
QScrollBar::handle:horizontal { background: #45413e; border-radius: 3px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #625c56; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QToolButton#notationCard { background: %(PANEL)s; border: 1px solid %(BORDER)s;
    border-radius: 12px; padding: 4px; color: %(TEXT)s; font-size: 12px; }
QToolButton#notationCard:hover { background: %(PANEL2)s; border-color: %(FAINT)s; }
QToolButton#notationCard:checked { background: %(ACCENT_DARK)s; border-color: %(ACCENT)s; color: %(ACCENT)s; }
QToolButton#notationCard:focus { border-color: %(ACCENT)s; }
QFrame#notationStage { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #222120,stop:0.5 #191817,stop:1 #141313);
    border: 1px solid #3a3733; border-radius: 22px; }
QLabel#notationSymbol { font-size: 23px; font-weight: 650; color: %(TEXT)s; }
QLabel#notationBadge { color: %(MUTED)s; font-size: 10px; font-weight: 600; padding: 5px 0; }
QLabel#notationExplanation { color: %(MUTED)s; font-size: 13px; padding: 6px 0; }
QPushButton#notationMode { background: %(PANEL)s; border: 1px solid %(BORDER)s;
    border-radius: 9px; color: %(MUTED)s; padding: 8px 9px; font-size: 12px; }
QPushButton#notationMode:hover { border-color: %(FAINT)s; color: %(TEXT)s; }
QPushButton#notationMode:checked { background: %(ACCENT_DARK)s; border-color: #716012; color: %(ACCENT)s; }
QPushButton#notationMore { background: %(PANEL)s; color: %(MUTED)s; border: 1px solid %(BORDER)s;
    border-radius: 12px; padding: 12px 16px; text-align: left; }
QPushButton#notationMore:hover, QPushButton#notationMore:checked { color: %(TEXT)s; background: %(PANEL2)s; }
QLabel#notationGrip { background: %(PANEL)s; border: 1px solid %(BORDER)s;
    border-radius: 10px; padding: 12px; color: %(TEXT)s; }
QDialog { background: %(PANEL)s; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox { background: %(BG)s; border: 1px solid %(BORDER)s;
            border-radius: 9px; padding: 8px 10px; selection-background-color: %(ACCENT)s;
            selection-color: #111; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border-color: %(ACCENT)s; }
QCheckBox { spacing: 10px; padding: 3px 0; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #5a5551;
                        border-radius: 5px; background: %(PANEL2)s; }
QCheckBox::indicator:hover { border-color: %(ACCENT)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; border-color: %(ACCENT)s; image: url("%(CHECKMARK)s"); }
QCheckBox:focus { color: %(ACCENT)s; }
QCheckBox:disabled { color: %(FAINT)s; }
QRadioButton { spacing: 9px; padding: 3px 0; }
QRadioButton::indicator { width: 16px; height: 16px; background: %(BG)s; border: 1px solid %(FAINT)s; border-radius: 8px; }
QRadioButton::indicator:checked { background: %(ACCENT)s; border: 4px solid %(ACCENT_DARK)s; }
QSplitter::handle { background: %(BG)s; }
QSplitter::handle:hover { background: %(BORDER)s; }
QSlider::groove:horizontal { height: 4px; background: %(BORDER)s; border-radius: 2px; }
QSlider::handle:horizontal { background: %(TEXT)s; width: 14px; margin: -5px 0;
                             border-radius: 7px; }
QSlider::sub-page:horizontal { background: %(ACCENT)s; border-radius: 2px; }
""" % dict(fam=fam, BG=BG, PANEL=PANEL, PANEL2=PANEL2, BORDER=BORDER, TEXT=TEXT,
           MUTED=MUTED, FAINT=FAINT, ACCENT=ACCENT, ACCENT_DARK=ACCENT_DARK,
           SCRAMBLE=SCRAMBLE, READY=READY, HOLD=HOLD, INSPECT=INSPECT,
           DNF_RED=DNF_RED, CHIP_BG=CHIP_BG, CHEVRON=CHEVRON, CHECKMARK=CHECKMARK)
