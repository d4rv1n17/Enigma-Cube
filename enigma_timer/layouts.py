"""Shared responsive layouts for toolbars and secondary windows."""
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QLayout


class WrapLayout(QLayout):
    """Keep controls at their preferred size and wrap them onto another row."""
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)
        self.invalidate()

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        result = QSize(0, 0)
        for item in self.items:
            if not item.isEmpty():
                result = result.expandedTo(item.sizeHint().expandedTo(item.minimumSize()))
        margins = self.contentsMargins()
        return result + QSize(margins.left()+margins.right(), margins.top()+margins.bottom())

    def _arrange(self, rect, measure):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self.items:
            if item.isEmpty():
                continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            width = min(size.width(), max(1, area.width()))
            if row_height and x+width > area.right()+1:
                x, y, row_height = area.x(), y+row_height+self.spacing(), 0
            if not measure:
                item.setGeometry(QRect(x, y, width, size.height()))
            x += width+self.spacing()
            row_height = max(row_height, size.height())
        return y+row_height-rect.y()+margins.bottom()
