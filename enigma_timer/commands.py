"""Keyboard-first action search across the desktop workspace."""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel
from .i18n import tr


class CommandPalette(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.setWindowTitle(tr("quick_actions"))
        self.setMinimumWidth(520)
        self.resize(600, 490)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 22)
        lay.setSpacing(14)
        title = QLabel(tr("quick_actions"))
        title.setObjectName("pageHeading")
        lay.addWidget(title)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("action_search"))
        self.search.setClearButtonEnabled(True)
        lay.addWidget(self.search)
        self.results = QListWidget()
        self.results.setObjectName("commandList")
        lay.addWidget(self.results, 1)
        hint = QLabel(tr("action_keys"))
        hint.setObjectName("muted")
        lay.addWidget(hint)
        self.actions = [
            (tr("nav_timer"), lambda: main.set_page(0)),
            (tr("nav_training"), lambda: main.set_page(1)),
            (tr("nav_reference"), lambda: main.set_page(2)),
            (tr("nav_achievements"), lambda: main.set_page(3)),
            (tr("new_scramble_action"), main.new_scramble),
            (tr("previous_scramble"), main.previous_scramble),
            (tr("update_check"),main.check_updates),
            (tr("manual_entry"), main.manual_entry),
            (tr("ble_connect"), main._ble_show_scan),
            (tr("cube_sync"), main.open_cube_sync),
            (tr("cube_3d_title"), main.open_cube_window),
            (tr("solve_assistant"), main.open_solve_assistant),
            (tr("win_mini_timer"), lambda: main.open_window("timer")),
            (tr("win_training"), lambda: main.open_window("training")),
            (tr("win_reference"), lambda: main.open_window("reference")),
            (tr("win_achievements"), lambda: main.open_window("achievements")),
            (tr("minimal_mode"), main.toggle_minimal),
            (tr("settings"), main.open_settings),
            (tr("about"), main.show_about),
        ]
        self.search.textChanged.connect(self.filter)
        self.search.returnPressed.connect(self.execute)
        self.results.itemActivated.connect(self.execute)
        self.filter("")
        self.search.setFocus()

    def filter(self, text):
        self.results.clear()
        terms = text.casefold().split()
        for index, (label, _callback) in enumerate(self.actions):
            if all(term in label.casefold() for term in terms):
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, index)
                self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def execute(self, *_args):
        item = self.results.currentItem()
        if item is not None:
            action = self.actions[item.data(Qt.UserRole)][1]
            self.accept()
            QTimer.singleShot(0, action)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            step = 1 if event.key() == Qt.Key_Down else -1
            row = self.results.currentRow() + step
            self.results.setCurrentRow(max(0, min(self.results.count()-1, row)))
            return
        super().keyPressEvent(event)
