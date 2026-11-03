# -*- coding: utf-8 -*-
"""Reference (notation for every puzzle) and Achievements pages."""

import time

from PyQt5.QtCore import QEvent, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel, QListView,
                             QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate,
                             QVBoxLayout, QWidget, QStackedWidget)

from . import achievements as ach
from . import reference, theme
from .i18n import lang, pick, tr
from .training import LessonBrowser

ROLE = Qt.UserRole + 7


class ReferencePage(QWidget):
    """Notation reference: list of puzzles on the left, notation on the right."""

    def __init__(self, hub, parent=None):
        QWidget.__init__(self, parent)
        self.hub = hub
        root = QHBoxLayout(self)
        theme.page(self,root)
        side = QFrame()
        side.setObjectName("panel")
        side.setFixedWidth(theme.SIDEBAR_WIDTH)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 14, 10, 10)
        t = QLabel(tr("reference").upper())
        t.setObjectName("sectionTitle")
        sv.addWidget(t)
        self.list = QListWidget()
        self.list.setObjectName("plainlist")
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setFocusPolicy(Qt.NoFocus)
        for pid, name in reference.PUZZLES:
            it = QListWidgetItem(pick(name))
            it.setData(ROLE, pid)
            it.setSizeHint(QSize(170, 40))
            self.list.addItem(it)
        self.list.currentRowChanged.connect(self._show)
        sv.addWidget(self.list, 1)
        root.addWidget(side)
        self.text = LessonBrowser()
        from .notation_panel import CubeNotationPanel
        self.cube_notation = CubeNotationPanel(self.text.open_demo, self)
        self.content = QStackedWidget()
        self.content.addWidget(self.text)
        self.content.addWidget(self.cube_notation)
        root.addWidget(self.content, 1)
        self.list.setCurrentRow(0)

    def _show(self, row):
        it = self.list.item(row)
        if it is None:
            return
        puzzle = it.data(ROLE)
        if puzzle in ("333", "222", "444", "pyram", "skewb", "sq1", "minx", "clock"):
            self.cube_notation.set_puzzle(puzzle)
            self.content.setCurrentWidget(self.cube_notation)
        else:
            self.text.setHtml(reference.html(puzzle, lang()))
            self.content.setCurrentWidget(self.text)

    def show_puzzle(self, pid):
        for row in range(self.list.count()):
            if self.list.item(row).data(ROLE) == pid:
                self.list.setCurrentRow(row)
                return


class BadgeDelegate(QStyledItemDelegate):
    W, H = 280, 152

    def __init__(self, page, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.page = page

    def sizeHint(self, option, index):
        width = self.page.grid.gridSize().width()
        return QSize(max(220, width-4) if width > 0 else self.W, self.H)

    def paint(self, p, option, index):
        a = ach.BY_ID.get(index.data(ROLE))
        if a is None:
            return
        unlocked = self.page.unlocked.get(a["id"])
        value, target = self.page.status.get(a["id"], (0, 1))
        r = QRectF(option.rect).adjusted(5, 5, -5, -5)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        hover = bool(option.state & QStyle.State_MouseOver)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.PANEL2 if hover else theme.PANEL))
        p.drawRoundedRect(r, 12, 12)
        # badge
        b = QRectF(r.left() + 16, r.top() + 18, 44, 44)
        if unlocked:
            p.setBrush(QColor(theme.ACCENT))
            p.drawEllipse(b)
            p.setPen(QColor("#111111"))
        else:
            p.setPen(QPen(QColor(theme.BORDER), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(b.adjusted(1, 1, -1, -1))
            p.setPen(QColor(theme.FAINT))
        f = QFont(theme.ui_font())
        f.setPixelSize(15 if len(a["badge"]) <= 3 else 12)
        f.setBold(True)
        p.setFont(f)
        p.drawText(b, Qt.AlignCenter, a["badge"])
        # texts
        tx = b.right() + 14
        f.setPixelSize(14)
        f.setBold(False)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT if unlocked else theme.MUTED))
        p.drawText(QRectF(tx, r.top() + 14, r.right() - tx - 14, 36),
                   Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, pick(a["name"]))
        f.setPixelSize(12)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(tx, r.top() + 52, r.right() - tx - 14, 62),
                   Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, pick(a["desc"]))
        if unlocked:
            p.setPen(QColor(theme.ACCENT))
            p.drawText(QRectF(tx, r.bottom() - 22, r.right() - tx - 10, 16),
                       Qt.AlignLeft | Qt.AlignVCenter,
                       time.strftime("%d.%m.%Y", time.localtime(unlocked)))
        elif target > 1:
            label = "%d/%d" % (value, target)
            lw = p.fontMetrics().boundingRect(label).width() + 10
            bar = QRectF(tx, r.bottom() - 16, max(20.0, r.right() - tx - 14 - lw), 4)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.BORDER))
            p.drawRoundedRect(bar, 2, 2)
            p.setBrush(QColor(theme.ACCENT))
            p.drawRoundedRect(QRectF(bar.left(), bar.top(),
                                     bar.width() * min(1.0, value / float(target)), 4), 2, 2)
            p.setPen(QColor(theme.FAINT))
            p.drawText(QRectF(bar.right() + 4, r.bottom() - 24, r.right() - bar.right() - 12, 20),
                       Qt.AlignRight | Qt.AlignVCenter, label)
        p.restore()


class AchievementsPage(QWidget):
    def __init__(self, store, parent=None):
        QWidget.__init__(self, parent)
        self.store = store
        self.unlocked = {}
        self.status = {}
        lay = QVBoxLayout(self)
        theme.page(self,lay)
        self.title = QLabel(tr("achievements"))
        self.title.setObjectName("pageHeading")
        lay.addWidget(self.title)
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.next_goal = QLabel()
        self.next_goal.setWordWrap(True)
        self.next_goal.setObjectName("statusText")
        lay.addWidget(self.next_goal)
        self.filter = QComboBox()
        self.filter.setObjectName("event")
        for key, value in (("all", "ach_filter_all"),
                           (ach.SOLVING, "ach_filter_solving"),
                           (ach.TRAINING, "ach_filter_training"),
                           ("unlocked", "ach_filter_unlocked")):
            self.filter.addItem(tr(value), key)
        self.filter.currentIndexChanged.connect(self.refresh)
        lay.addWidget(self.filter, 0, Qt.AlignLeft)
        self.grid = QListWidget()
        self.grid.setObjectName("grid")
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setUniformItemSizes(False)
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.setFocusPolicy(Qt.NoFocus)
        self.grid.setMouseTracking(True)
        self.grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid.viewport().installEventFilter(self)
        self.grid.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.grid.setItemDelegate(BadgeDelegate(self, self.grid))
        lay.addWidget(self.grid, 1)
        self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_badges()

    def eventFilter(self, obj, event):
        if obj is self.grid.viewport() and event.type() == QEvent.Resize:
            self._layout_badges()
        return super().eventFilter(obj, event)

    def _layout_badges(self):
        if not hasattr(self, "grid"):
            return
        width = max(1, self.grid.viewport().width())
        columns = max(1, width // BadgeDelegate.W)
        target = QSize(max(224, width // columns-4), BadgeDelegate.H)
        if self.grid.gridSize() != target:
            self.grid.setGridSize(target)

    def refresh(self):
        _new, self.status = ach.check(self.store)
        self.unlocked = self.store.training.get("ach", {})
        self.grid.clear()
        order = sorted(ach.A, key=lambda a: (a["id"] not in self.unlocked,
                                             a["cat"] != ach.SOLVING))
        for a in order:
            selected = self.filter.currentData() if hasattr(self, "filter") else "all"
            if selected == "unlocked" and a["id"] not in self.unlocked:
                continue
            if selected in (ach.SOLVING, ach.TRAINING) and a["cat"] != selected:
                continue
            it = QListWidgetItem()
            it.setData(ROLE, a["id"])
            it.setToolTip(pick(a["name"])+"\n"+pick(a["desc"]))
            self.grid.addItem(it)
        self.summary.setText(tr("ach_summary") % (len(self.unlocked), len(ach.A)))
        pending = [a for a in ach.A if a["id"] not in self.unlocked]
        pending.sort(key=lambda a: self.status[a["id"]][0] / max(1, self.status[a["id"]][1]), reverse=True)
        if pending:
            a = pending[0]
            value, target = self.status[a["id"]]
            self.next_goal.setText(tr("ach_next") % (pick(a["name"]), value, target))
        else:
            self.next_goal.clear()
