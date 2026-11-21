"""Main window and the timer state machine."""

import os
import sys
import time

from PyQt5.QtCore import QByteArray, QEvent, QObject, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QAction, QApplication,
                             QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                             QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow,
                             QMenu, QMessageBox, QPlainTextEdit, QPushButton, QShortcut,
                             QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit,
                             QToolButton, QVBoxLayout, QWidget)

from . import scramble as scr
from . import storage, theme
from . import ble as ble_mod
from . import cube as cube_mod
from .dialogs import (AboutDialog, CubeFrameDialog, SettingsDialog, SolveDialog,
                      TextDialog, WelcomeDialog)
from .i18n import tr
from .stats import (DNF, INF, OK, PLUS2, STAT_ROWS, SessionStats, Solve, fmt_avg,
                    fmt_ms, fmt_solve, parse_time, trimmed_indices)
from .stats import average as stats_average
from .stats import mean as stats_mean
from . import achievements as ach
from . import learn
from .i18n import pick
from .pages import AchievementsPage, ReferencePage
from .training import TrainingHub, TrainingWidget
from .widgets import (FadeStackedWidget, LiveCube3DWidget, ScramblePreview, TimeChart,
                      TimeHistogram, TimerDisplay, Toast)

# PyInstaller unpacks bundled files to sys._MEIPASS
_BASE = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(_BASE, "assets")

# timer states
IDLE, INSPECTING, HOLDING, READY, RUNNING, STOPPED = range(6)

INSPECTION_S = 15.0


def _panel():
    f = QFrame()
    f.setObjectName("panel")
    return f


def _section(text):
    lb = QLabel(text.upper())
    lb.setObjectName("sectionTitle")
    return lb


def _dark_title_bar(widget):
    """Ask Windows 10/11 to draw a dark title bar (no-op elsewhere)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        hwnd = ctypes.c_void_p(int(widget.winId()))
        value = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        for attribute, color in ((35, 0x00181818), (36, 0x00EDEFF0)):
            tint = ctypes.c_int(color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(tint), ctypes.sizeof(tint))
    except Exception:  # noqa: BLE001 - purely cosmetic
        pass


class _KeyFilter(QObject):
    """Application-wide filter so Space works no matter which widget has focus."""

    def __init__(self, win):
        QObject.__init__(self, win)
        self.win = win

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Polish and isinstance(obj, QDialog):
            theme.prepare_dialog(obj)
            obj.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
            obj.setWindowIcon(self.win.windowIcon())
        if t == QEvent.Polish and isinstance(obj, QPushButton) and isinstance(obj.window(), QDialog):
            obj.setAutoDefault(False)
        if t == QEvent.Show and isinstance(obj, QDialog):
            theme.fit_to_screen(obj)
            _dark_title_bar(obj)
            return False
        if t not in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride,
                     QEvent.MouseButtonPress):
            return False
        w = self.win
        # Windows reports Cyrillic key symbols under a Russian layout.
        # Keep workspace shortcuts tied to their physical keys as well.
        if (t in (QEvent.ShortcutOverride, QEvent.KeyPress)
                and QApplication.activeWindow() is w
                and QApplication.activeModalWidget() is None
                and QApplication.activePopupWidget() is None
                and ev.modifiers() == Qt.ControlModifier
                and w.state in (IDLE, STOPPED)):
            native = ev.nativeVirtualKey()
            action = {0x4B: w.open_command_palette, 0xBC: w.open_settings}.get(native)
            if action is not None:
                if t == QEvent.ShortcutOverride:
                    ev.accept()
                elif not ev.isAutoRepeat():
                    action()
                return True
        if getattr(w, "page", 0) != 0:
            return False
        if QApplication.activeModalWidget() is not None or \
                QApplication.activePopupWidget() is not None or \
                QApplication.activeWindow() is not w:
            return False
        if t == QEvent.MouseButtonPress:
            if w.state == RUNNING:
                w.stop_solve()
                return True
            return False
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)) \
                and w.state == IDLE:
            return False
        if t == QEvent.ShortcutOverride:
            # while the timer is busy, keys must reach us instead of shortcuts
            if w.state != IDLE or ev.key() == Qt.Key_Space:
                ev.accept()
                return True
            return False
        if t == QEvent.KeyPress:
            return w.on_key_press(ev.key(), ev.isAutoRepeat())
        return w.on_key_release(ev.key(), ev.isAutoRepeat())


class BleScanDialog(QDialog):
    """Scan for nearby Giiker cubes and connect to the chosen one."""

    def __init__(self, win):
        QDialog.__init__(self, win)
        self.win = win
        self.setWindowTitle(tr("ble_scan_title"))
        self.setMinimumSize(520, 430)
        self.resize(560, 500)
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 20)
        v.setSpacing(10)
        heading = QLabel(tr("ble_scan_title"))
        heading.setObjectName("dialogTitle")
        v.addWidget(heading)
        self.info = QLabel(tr("ble_scan_intro"))
        self.info.setWordWrap(True)
        self.info.setObjectName("bodyText")
        v.addWidget(self.info)
        self.status = QLabel(tr("ble_scan_waiting"))
        self.status.setObjectName("dialogStatus")
        self.status.setWordWrap(True)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, 1)
        self.reconnect_saved_btn = QPushButton(tr("ble_scan_reconnect_saved"))
        self.reconnect_saved_btn.setMinimumWidth(132)
        self.reconnect_saved_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.reconnect_saved_btn.setObjectName("seg")
        self.reconnect_saved_btn.setToolTip(tr("ble_scan_reconnect_saved_tip"))
        self.reconnect_saved_btn.setVisible(bool(win.settings.get("ble_last_address")))
        self.reconnect_saved_btn.clicked.connect(self._reconnect_saved)
        status_row.addWidget(self.reconnect_saved_btn)
        v.addLayout(status_row)
        self.list = QListWidget()
        self.list.setObjectName("scanList")
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.currentItemChanged.connect(self._selection_changed)
        v.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.refresh_btn = QPushButton(tr("ble_scan_refresh"))
        self.refresh_btn.setMinimumWidth(132)
        self.refresh_btn.clicked.connect(self._scan)
        row.addWidget(self.refresh_btn)
        self.connect_btn = QPushButton(tr("ble_scan_connect"))
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._chosen)
        row.addWidget(self.connect_btn)
        row.addStretch(1)
        close = QPushButton(tr("close"))
        close.clicked.connect(self.reject)
        row.addWidget(close)
        v.addLayout(row)
        win._ble_scan_dialog = self
        self._scanning = True
        self._has_cube = False
        self._cube_count = 0
        self._other_count = 0
        self._error_visible = False
        # if nothing shows up after a while, explain what to check
        self._empty_timer = QTimer(self)
        self._empty_timer.setSingleShot(True)
        self._empty_timer.setInterval(8000)
        self._empty_timer.timeout.connect(self._show_empty)
        self._connecting_address = None
        self._scan()
        # PyQt5's connect() returns a bound Connection object with no
        # .disconnect(); keep the bound slot so we can unhook it cleanly.
        win.ble.connected.connect(self._on_connected)
        win.ble.connection_stage.connect(self._connection_stage)
        if win.cube_btn.isChecked():
            QTimer.singleShot(0, self.accept)

    def _win_ble(self):
        """The Bluetooth worker; `_ble_show_scan` starts it before this dialog."""
        return self.win.ble

    def _connection_stage(self, key):
        if self._connecting_address and not self._error_visible:
            self.status.setText(tr(key))

    def _scan(self):
        self.list.clear()
        self._has_cube = False
        self._cube_count = 0
        self._other_count = 0
        self._scanning = True
        self._error_visible = False
        self.status.setText(tr("ble_status_scanning"))
        self.connect_btn.setEnabled(False)
        self.win._ble_devices.clear()
        self._empty_timer.start()
        if self._win_ble() is not None:
            self._win_ble().scan_restart()

    def add_device(self, name, address, is_cube=None):
        # A later scan response may upgrade an address-only placeholder to
        # the cube's real advertised name.
        if is_cube is None:
            is_cube = ble_mod.is_cube_advertisement(name)
        if not is_cube:
            return
        existing = None
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == address:
                existing = self.list.item(i)
                break
        if existing is None:
            existing = QListWidgetItem()
            existing.setData(Qt.UserRole, address)
            existing.setData(Qt.UserRole + 1, bool(is_cube))
            self.list.insertItem(0, existing)
        existing.setData(Qt.UserRole + 1, bool(is_cube))
        existing.setText("●  " + name + "   ·   " + address)
        existing.setToolTip(tr("ble_scan_candidate"))
        self._cube_count = sum(bool(self.list.item(i).data(Qt.UserRole + 1))
                               for i in range(self.list.count()))
        self._other_count = self.list.count() - self._cube_count
        self._has_cube = self._cube_count > 0
        if is_cube:
            row = self.list.row(existing)
            if row > 0:
                was_current = self.list.currentItem() is existing
                existing = self.list.takeItem(row)
                self.list.insertItem(0, existing)
                if was_current:
                    self.list.setCurrentItem(existing)
            existing.setForeground(QColor(theme.ACCENT))
            if not self._error_visible and not self._connecting_address:
                self.status.setText(tr("ble_scan_found") % self._cube_count)
            if self.list.currentItem() is None or not self.list.currentItem().data(Qt.UserRole + 1):
                self.list.setCurrentItem(existing)
        self._selection_changed(self.list.currentItem(), None)

    def _selection_changed(self, item, _previous):
        self.connect_btn.setEnabled(item is not None and not self._connecting_address)
        self.connect_btn.setText(tr("ble_scan_connect"))

    def _reconnect_saved(self):
        address = self.win.settings.get("ble_last_address")
        if not address or self._connecting_address:
            return
        self._connecting_address = address
        self._error_visible = False
        self.refresh_btn.setEnabled(False)
        self.reconnect_saved_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.status.setText(tr("ble_scan_connecting"))
        self.win._ble_connect(address)

    def scan_done(self):
        self._scanning = False
        self.refresh_btn.setEnabled(not self._connecting_address)

    def _show_empty(self):
        """Explain what to check while the scan found nothing."""
        if (self._scanning and self._cube_count == 0
                and self._connecting_address is None and not self._error_visible):
            self.status.setText(tr("ble_scan_empty"))

    def show_error(self, text):
        self._error_visible = True
        self.status.setText(text)   # the worker already formatted the message

    def _chosen(self, *_args):
        item = self.list.currentItem()
        if item is None:
            return
        address = item.data(Qt.UserRole)
        if self._connecting_address == address:
            return
        self._connecting_address = address
        self._error_visible = False
        self.refresh_btn.setEnabled(False)
        self.reconnect_saved_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.status.setText(tr("ble_scan_connecting"))
        self.win._ble_connect(address)

    def _unlink_worker(self):
        """Drop the auto-accept hook on the worker's `connected` signal."""
        try:
            win_ble = self._win_ble()
            if win_ble is not None:
                win_ble.connected.disconnect(self._on_connected)
                win_ble.connection_stage.disconnect(self._connection_stage)
        except (TypeError, RuntimeError):  # already gone / dialog closing
            pass

    def _on_connected(self, _name, address):
        # If a saved cube reconnects while the picker is open, discovery is no
        # longer useful. Otherwise close only for the explicitly chosen cube.
        if self._connecting_address in (None, address):
            self.accept()

    def connection_failed(self):
        self._connecting_address = None
        self.refresh_btn.setEnabled(True)
        self.reconnect_saved_btn.setEnabled(bool(self.win.settings.get("ble_last_address")))
        self._selection_changed(self.list.currentItem(), None)
        self._empty_timer.start()

    def accept(self):
        ble = self._win_ble()
        self._unlink_worker()
        if ble is not None:
            ble.scan_stop()
        if self.win._ble_scan_dialog is self:
            self.win._ble_scan_dialog = None
        QDialog.accept(self)

    def reject(self):
        ble = self._win_ble()
        self._unlink_worker()
        if ble is not None:
            ble.scan_stop()
        if self.win._ble_scan_dialog is self:
            self.win._ble_scan_dialog = None
        QDialog.reject(self)


class MainWindow(QMainWindow):
    def __init__(self, store):
        QMainWindow.__init__(self)
        self.store = store
        self.settings = store.settings
        self.state = IDLE
        self.t_start = 0.0
        self.t_start_ble = None   # monotonic time of the starting packet
        self.ble_moves = 0        # cube turns since the solve started
        self._solve_events = []
        self._solve_initial = None
        self._solve_event_origin = None
        self._frame_dialog = None   # open CubeFrameDialog (moves go to it)
        self._sync_dialog = None
        self.solve_assistant = None
        self._frame_perm = None     # stored whole-cube rotation, if any
        self._load_frame_perm()
        self.hold_start = 0.0
        self.insp_start = None
        self.insp_alerts_done = set()
        self.insp_penalty = OK
        self.arm_inspection = False
        self.scramble = ""
        from .scramble_history import ScrambleHistory
        self.scramble_history=ScrambleHistory()
        self.stats = None
        self._loading = False
        self.page = 0
        self.training = None
        self.extra_windows = []
        from .updates import UpdateService
        self.updater=UpdateService(store,self)
        self.updater.changed.connect(self._update_changed)
        self._last_update_state=""
        self.hub = TrainingHub(store, self)
        self.page_widgets = {0: None}
        self.achievements_page = None
        self.hub.changed.connect(self._training_changed)

        # smart cube
        self.ble = None                 # GiikerWorker once a worker is running
        self.ble_state = None           # last CubeState
        self._raw_ble_state = None
        self._cube_state_trusted = False
        self.ble_solved_seen = False    # True once we saw the cube solved
        self.ble_saw_unsolved = False   # a solve can stop only after leaving solved state
        self.ble_scramble_ready = False
        self._ble_target_states = set()
        self.ble_wait_move = False      # armed: waiting for the first turn
        self._ble_devices = {}
        self._ble_scan_dialog = None
        self._ble_connected_name = ""
        self._ble_connected_address = None
        self.ble_profile = None
        self.live_cube_window = None

        self.setWindowTitle(tr("app_title"))
        from .brand import app_icon
        self.setWindowIcon(app_icon())
        QApplication.instance().setProperty("reduceMotion", bool(self.settings.get("reduce_motion", False)))
        self.setMinimumSize(960, 640)
        self._build_ui()
        self._build_shortcuts()

        self.tick = QTimer(self)
        self.tick.setTimerType(Qt.PreciseTimer)
        self.tick.timeout.connect(self._on_tick)
        self.tick.start(15)

        self.key_filter = _KeyFilter(self)
        QApplication.instance().installEventFilter(self.key_filter)

        geo = self.settings.get("geometry")
        restored = False
        if geo:
            try:
                restored = self.restoreGeometry(QByteArray.fromBase64(geo.encode("ascii")))
            except Exception:  # noqa: BLE001 - geometry is cosmetic
                pass
        if not restored:
            self.resize(1280, 800)
        # saveGeometry includes normal bounds and maximized/fullscreen state.
        # Startup chooses the default only when no usable user choice exists.
        self.start_maximized = not restored

        self.switch_session(self.store.current_id)
        self.check_achievements(quiet=True)   # unlock earned ones without a toast storm
        if getattr(self.store, "recovered_backup", False):
            QTimer.singleShot(250, lambda: self.toast.show_message(tr("backup_recovered"), 6000))
        if self.settings.get("ble_last_address"):
            self._ble_start_worker()
        if self.store.is_first_run and not self.settings.get("welcome_seen"):
            self.settings["welcome_pending"] = True
            self.save()
        if self.settings.get("welcome_pending") and not self.settings.get("welcome_seen"):
            QTimer.singleShot(0, self._show_welcome)
        self.update_poll=QTimer(self)
        self.update_poll.setInterval(12*3600*1000)
        self.update_poll.timeout.connect(self.updater.automatic_check)
        self.update_poll.start()
        QTimer.singleShot(4000,self.updater.automatic_check)
        self._update_changed()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(theme.PAGE_MARGIN, 16, theme.PAGE_MARGIN, theme.PAGE_MARGIN)
        root.setSpacing(16)

        # ---- top bar -------------------------------------------------
        self.top_bar = QWidget()
        top = QHBoxLayout(self.top_bar)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(5)
        logo = QLabel()
        self.brand_logo = logo
        pm = QPixmap(os.path.join(ASSETS, "header.png"))
        self.brand_pixmap = pm
        if not pm.isNull():
            pm.setDevicePixelRatio(2.0)   # header.png is drawn at 2x for sharp HiDPI
            logo.setPixmap(pm)
        logo.setCursor(Qt.PointingHandCursor)
        logo.setToolTip(tr("about"))
        logo.mousePressEvent = lambda e: self.show_about()
        top.addWidget(logo)
        top.addSpacing(16)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for i, key in enumerate(("nav_timer", "nav_training", "nav_reference", "nav_achievements")):
            b = QPushButton(tr(key))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setFocusPolicy(Qt.NoFocus)
            self.nav_group.addButton(b, i)
            top.addWidget(b)
        self.nav_group.buttonClicked[int].connect(self.set_page)
        top.addStretch(1)
        # event selector: one quiet button with a menu (fits any window width)
        self.puzzle_bar = QPushButton()
        self.puzzle_bar.setObjectName("event")
        self.puzzle_bar.setFocusPolicy(Qt.NoFocus)
        self.puzzle_bar.setCursor(Qt.PointingHandCursor)
        self.event_menu = QMenu(self.puzzle_bar)
        self.event_actions = {}
        groups = (("222", "333", "444", "555", "666", "777"),
                  ("pyram", "skewb", "minx", "clock", "sq1"),
                  ("333oh", "333bf", "333fm"))
        for gi, group in enumerate(groups):
            if gi:
                self.event_menu.addSeparator()
            for pid in group:
                act = QAction(scr.PUZZLE_NAME[pid], self.event_menu)
                act.setCheckable(True)
                act.triggered.connect(lambda _=False, p=pid: self.select_puzzle(p))
                self.event_menu.addAction(act)
                self.event_actions[pid] = act
        self.puzzle_bar.setMenu(self.event_menu)
        top.addWidget(self.puzzle_bar)
        top.addSpacing(10)

        # smart cube: one button with a connection menu
        self.cube_btn = QPushButton("◎  " + tr("ble_btn_label"))
        self.cube_btn.setObjectName("cube")
        self.cube_btn.setCheckable(True)   # checked == cube connected
        self.cube_btn.setFocusPolicy(Qt.NoFocus)
        self.cube_btn.setCursor(Qt.PointingHandCursor)
        self.cube_btn.setToolTip(tr("ble_connect"))
        cm = self.cube_menu = QMenu(self.cube_btn)
        self.cube_status = cm.addAction(tr("ble_status_off"))
        self.cube_status.setEnabled(False)
        cm.addSeparator()
        self.cube_scan_action = cm.addAction(tr("ble_connect"), self._ble_show_scan)
        self.cube_disconnect_action = cm.addAction(tr("ble_disconnect"), self._ble_disconnect)
        self.cube_disconnect_action.setEnabled(False)
        cm.addSeparator()
        self.cube_window_action = cm.addAction(tr("cube_open_window"), self.open_cube_window)
        cm.addAction(tr("solve_assistant"), self.open_solve_assistant)
        cm.addAction(tr("cube_sync"), self.open_cube_sync)
        self.cube_frame_action = cm.addAction(tr("frame_calibrate"), self._ble_calibrate_frame)
        self.cube_frame_action.setEnabled(False)
        self.cube_frame_reset_action = cm.addAction(tr("frame_reset"), self.reset_frame)
        self.cube_frame_reset_action.setEnabled(False)
        self.cube_btn.setMenu(cm)
        top.addWidget(self.cube_btn)
        top.addSpacing(10)

        # multi-window mode: any section can live in its own window
        self.windows_btn = QPushButton("⧉  " + tr("windows"))
        self.windows_btn.setObjectName("windows")
        self.windows_btn.setFocusPolicy(Qt.NoFocus)
        self.windows_btn.setCursor(Qt.PointingHandCursor)
        self.windows_btn.setToolTip(tr("windows_tip"))
        wm = self.windows_menu = QMenu(self.windows_btn)
        sec = wm.addAction(tr("win_open_section"))
        sec.setEnabled(False)
        wm.addAction(tr("quick_actions") + "\tCtrl+K", self.open_command_palette)
        wm.addSeparator()
        wm.addAction("⏱   " + tr("win_mini_timer") + "\tCtrl+T", lambda: self.open_window("timer"))
        wm.addAction(tr("cube_3d_title"), self.open_cube_window)
        wm.addAction(tr("solve_assistant"), self.open_solve_assistant)
        wm.addAction("◆   " + tr("win_training") + "\tCtrl+Shift+1", lambda: self.open_window("training"))
        wm.addAction("?    " + tr("win_reference") + "\tCtrl+Shift+2", lambda: self.open_window("reference"))
        wm.addAction("★   " + tr("win_achievements") + "\tCtrl+Shift+3",
                     lambda: self.open_window("achievements"))
        wm.addSeparator()
        self.minimal_action = wm.addAction(tr("minimal_mode") + "\tM", self.toggle_minimal)
        self.minimal_action.setCheckable(True)
        self.minimal_action.setChecked(bool(self.settings.get("minimal")))
        self.windows_btn.setMenu(wm)
        top.addWidget(self.windows_btn)

        gear = QPushButton("⚙")
        gear.setObjectName("icon")
        gear.setToolTip(tr("settings") + " (Ctrl+,)")
        gear.setFocusPolicy(Qt.NoFocus)
        gear.clicked.connect(self.open_settings)
        top.addWidget(gear)
        root.addWidget(self.top_bar)
        self.update_banner=QFrame()
        self.update_banner.setObjectName("panel")
        update_row=QHBoxLayout(self.update_banner)
        update_row.setContentsMargins(16,10,12,10)
        self.update_banner_text=QLabel()
        self.update_banner_text.setWordWrap(True)
        update_row.addWidget(self.update_banner_text,1)
        self.update_banner_action=QPushButton()
        self.update_banner_action.setObjectName("primary")
        self.update_banner_action.clicked.connect(self._update_action)
        update_row.addWidget(self.update_banner_action)
        self.update_banner.hide()
        root.addWidget(self.update_banner)

        # ---- body ----------------------------------------------------
        self.pages = FadeStackedWidget()
        self.timer_page = QWidget()
        body = QHBoxLayout(self.timer_page)
        body.setContentsMargins(0, 0, 0, 0)
        self.pages.addWidget(self.timer_page)
        body.setSpacing(16)
        root.addWidget(self.pages, 1)

        # left: statistics + list of times
        self.left_panel = _panel()
        self.left_panel.setFixedWidth(280)
        lv = QVBoxLayout(self.left_panel)
        lv.setContentsMargins(16, 14, 12, 10)
        lv.setSpacing(8)
        sess_row = QHBoxLayout()
        sess_row.setSpacing(6)
        self.session_combo = QComboBox()
        self.session_combo.setFocusPolicy(Qt.NoFocus)
        self.session_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.session_combo.currentIndexChanged.connect(self._on_session_combo)
        sess_row.addWidget(self.session_combo, 1)
        menu_btn = QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setToolTip(tr("stats_session_actions"))
        menu_btn.setFocusPolicy(Qt.NoFocus)
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(menu_btn)
        menu.addAction(tr("new_session"), self.new_session)
        menu.addAction(tr("rename_session"), self.rename_session)
        menu.addAction(tr("delete_session"), self.delete_session)
        menu.addAction(tr("clear_session"), self.clear_session)
        menu.addSeparator()
        menu.addAction(tr("manual_entry") + "   Ctrl+E", self.manual_entry)
        menu.addSeparator()
        menu.addAction(tr("import_cstimer"), self.import_cstimer)
        menu.addSeparator()
        menu.addAction(tr("export_csv"), self.export_csv)
        menu.addAction(tr("export_cstimer"), self.export_cstimer)
        menu.addSeparator()
        menu.addAction(tr("settings"), self.open_settings)
        menu.addAction(tr("about"), self.show_about)
        menu_btn.setMenu(menu)
        sess_row.addWidget(menu_btn)
        lv.addLayout(sess_row)
        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        self.single_metrics = []
        for caption, column in (("stats_last", 1), ("stats_personal_best", 2)):
            card = QFrame()
            card.setObjectName("statMetric")
            box = QVBoxLayout(card)
            box.setContentsMargins(10, 10, 10, 10)
            box.setSpacing(3)
            title = QLabel(tr(caption))
            title.setObjectName("caption")
            title.setWordWrap(True)
            box.addWidget(title)
            value = QPushButton("—")
            value.setObjectName("statValue")
            value.setCursor(Qt.PointingHandCursor)
            value.clicked.connect(lambda _=False, col=column: self._on_stat_clicked(0, col))
            box.addWidget(value)
            metrics.addWidget(card, 1)
            self.single_metrics.append(value)
        lv.addLayout(metrics)
        averages_head = QHBoxLayout()
        averages_title = QLabel(tr("stats_averages"))
        averages_title.setObjectName("sectionTitle")
        averages_head.addWidget(averages_title)
        averages_head.addStretch(1)
        averages_help = QToolButton()
        from .brand import info_icon
        averages_help.setObjectName("helpIcon")
        averages_help.setIcon(info_icon())
        averages_help.setIconSize(QSize(16, 16))
        averages_help.setFixedSize(28, 28)
        averages_help.setCursor(Qt.PointingHandCursor)
        averages_help.setToolTip(tr("stats_average_help_title"))
        averages_help.setAccessibleName(tr("stats_average_help_title"))
        averages_help.clicked.connect(self._show_stats_help)
        averages_head.addWidget(averages_help)
        lv.addLayout(averages_head)
        self.stats_table = QTableWidget(len(STAT_ROWS), 3)
        self.stats_table.setHorizontalHeaderLabels([tr("stats_average_column"), tr("stats_latest"), tr("best")])
        self._setup_table(self.stats_table)
        self.stats_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.stats_table.setColumnWidth(0, 100)
        self.stats_table.verticalHeader().setDefaultSectionSize(32)
        self.stats_table.horizontalHeader().setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stats_table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.stats_table.cellClicked.connect(self._on_stat_clicked)
        self.stats_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for r, (label, size, _kind) in enumerate(STAT_ROWS):
            caption = tr("stats_mean3") if label == "mo3" else tr("stats_average_n") % size
            it = QTableWidgetItem(caption)
            it.setForeground(self._qcolor(theme.MUTED))
            it.setToolTip(tr("stats_average_help_body"))
            self.stats_table.setItem(r, 0, it)
        lv.addWidget(self.stats_table)
        self.averages_empty = QLabel()
        self.averages_empty.setObjectName("caption")
        self.averages_empty.setWordWrap(True)
        lv.addWidget(self.averages_empty)
        self.all_averages = QPushButton(tr("stats_all_averages"))
        self.all_averages.setObjectName("statsMore")
        self.all_averages.setCheckable(True)
        self.all_averages.toggled.connect(lambda: self._update_stats_rows())
        lv.addWidget(self.all_averages, 0, Qt.AlignLeft)
        self.summary = QLabel()
        self.summary.setObjectName("caption")
        self.summary.setWordWrap(True)
        lv.addWidget(self.summary)
        history_head = QHBoxLayout()
        self.history_title = QLabel(tr("stats_history"))
        self.history_title.setObjectName("labelStrong")
        history_head.addWidget(self.history_title)
        history_head.addStretch(1)
        self.history_count = QLabel("0")
        self.history_count.setObjectName("statCount")
        history_head.addWidget(self.history_count)
        lv.addLayout(history_head)
        history_hint = QLabel(tr("stats_history_hint"))
        history_hint.setObjectName("caption")
        history_hint.setWordWrap(True)
        lv.addWidget(history_hint)

        self.times_table = QTableWidget(0, 4)
        self.times_table.setHorizontalHeaderLabels(["#", tr("time"), "ao5", "ao12"])
        self._setup_table(self.times_table)
        self.times_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.times_table.setColumnWidth(0, 32)
        self.times_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.times_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.times_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.times_table.horizontalHeader().setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.times_table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.times_table.verticalHeader().setDefaultSectionSize(36)
        self.times_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.times_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.times_table.cellClicked.connect(self._on_time_clicked)
        self.times_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.times_table.customContextMenuRequested.connect(self._times_menu)
        lv.addWidget(self.times_table, 1)
        self.empty_label = QLabel(tr("empty_times"))
        self.empty_label.setObjectName("empty")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        lv.addWidget(self.empty_label, 1)
        body.addWidget(self.left_panel)

        # centre: scramble, timer, penalty bar
        center = QVBoxLayout()
        center.setSpacing(10)
        body.addLayout(center, 1)

        self.scramble_panel = QWidget()
        self.scramble_panel.setObjectName("scrambleSurface")
        sv = QHBoxLayout(self.scramble_panel)
        sv.setContentsMargins(16, 12, 12, 12)
        sv.setSpacing(8)
        self.scramble_moves_label = QLabel()
        self.scramble_moves_label.setObjectName("scramble")
        self.scramble_moves_label.setWordWrap(True)
        self.scramble_moves_label.setTextFormat(Qt.PlainText)
        self.scramble_moves_label.setAlignment(Qt.AlignCenter)
        self.scramble_moves_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.scramble_moves_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sv.addWidget(self.scramble_moves_label, 1)
        sbtns = QVBoxLayout()
        self.previous_scramble_button=QPushButton("←")
        self.previous_scramble_button.setObjectName("icon")
        self.previous_scramble_button.setToolTip(tr("previous_scramble"))
        self.previous_scramble_button.setAccessibleName(tr("previous_scramble"))
        self.previous_scramble_button.setFocusPolicy(Qt.NoFocus)
        self.previous_scramble_button.clicked.connect(self.previous_scramble)
        nb = QPushButton("→")
        self.next_scramble_button=nb
        nb.setObjectName("icon")
        nb.setToolTip(tr("next_scramble"))
        nb.setFocusPolicy(Qt.NoFocus)
        nb.clicked.connect(self.new_scramble)
        cb = QPushButton("❐")
        cb.setObjectName("icon")
        cb.setToolTip(tr("copy_scramble"))
        cb.setFocusPolicy(Qt.NoFocus)
        cb.clicked.connect(self.copy_scramble)
        sbtns.addWidget(self.previous_scramble_button)
        sbtns.addWidget(nb)
        sbtns.addWidget(cb)
        sbtns.addStretch(1)
        sv.addLayout(sbtns)
        center.addWidget(self.scramble_panel)

        self.timer_area = QWidget()
        self.timer_area.setObjectName("timerSurface")
        ta = QVBoxLayout(self.timer_area)
        ta.setContentsMargins(18, 14, 18, 14)
        self.timer_display = TimerDisplay()
        self.timer_display.pressed.connect(lambda: self.on_key_press(Qt.Key_Space, False))
        self.timer_display.released.connect(lambda: self.on_key_release(Qt.Key_Space, False))
        ta.addWidget(self.timer_display, 1)
        center.addWidget(self.timer_area, 1)
        self.toast = Toast(self.timer_area)

        self.pen_bar = QWidget()
        pb = QHBoxLayout(self.pen_bar)
        pb.setContentsMargins(0, 0, 0, 0)
        pb.addStretch(1)
        self.pen_buttons = {}
        for label, val in ((tr("ok"), OK), (tr("plus2"), PLUS2), (tr("dnf"), DNF)):
            b = QPushButton(label)
            b.setObjectName("pen")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, v=val: self.set_last_penalty(v))
            self.pen_buttons[val] = b
            pb.addWidget(b)
        cbtn = QPushButton("✎")
        cbtn.setObjectName("icon")
        cbtn.setToolTip(tr("comment"))
        cbtn.setFocusPolicy(Qt.NoFocus)
        cbtn.clicked.connect(self.comment_last)
        dbtn = QPushButton("✕")
        dbtn.setObjectName("icon")
        dbtn.setToolTip(tr("delete") + " (Ctrl+Z)")
        dbtn.setFocusPolicy(Qt.NoFocus)
        dbtn.clicked.connect(self.delete_last)
        pb.addWidget(cbtn)
        pb.addWidget(dbtn)
        pb.addStretch(1)
        center.addWidget(self.pen_bar)

        self.hint = QWidget()
        hl = QHBoxLayout(self.hint)
        hl.setContentsMargins(0, 0, 0, 6)
        hl.setSpacing(10)
        hl.addStretch(1)
        self.hint_key = QLabel(tr("key_space"))
        self.hint_key.setObjectName("keycap")
        hl.addWidget(self.hint_key)
        self.hint_text = QLabel()
        self.hint_text.setWordWrap(True)
        self.hint_text.setMinimumWidth(0)
        self.hint_text.setObjectName("muted")
        hl.addWidget(self.hint_text)
        hl.addStretch(1)
        center.addWidget(self.hint)

        # right: preview + chart
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(310)
        rv = QVBoxLayout(self.right_panel)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)
        right_card = _panel()
        rc = QVBoxLayout(right_card)
        rc.setContentsMargins(0, 0, 0, 0)
        rc.setSpacing(0)
        rv.addWidget(right_card, 1)
        self.preview_panel = QWidget()
        pv = QVBoxLayout(self.preview_panel)
        pv.setContentsMargins(14, 14, 14, 8)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.preview = ScramblePreview()
        self.preview.setMinimumHeight(220)
        self.live_cube = LiveCube3DWidget()
        self.live_cube.setMinimumHeight(220)
        # Put the preview and its title in their own panels. A hidden second
        # column used to keep taking layout space and pulled the title away
        # from the centered cube net.
        self.scramble_preview_panel = QWidget()
        scramble_box = QVBoxLayout(self.scramble_preview_panel)
        scramble_box.setContentsMargins(0, 0, 0, 0)
        scramble_box.setSpacing(4)
        self.scramble_label = QLabel(tr("scramble").capitalize())
        self.scramble_label.setObjectName("sectionTitle")
        self.scramble_label.setAlignment(Qt.AlignCenter)
        scramble_box.addWidget(self.scramble_label)
        scramble_box.addWidget(self.preview, 1)
        row.addWidget(self.scramble_preview_panel, 1)

        self.live_cube_panel = QWidget()
        cube_box = QVBoxLayout(self.live_cube_panel)
        cube_box.setContentsMargins(0, 0, 0, 0)
        cube_box.setSpacing(4)
        self.cube_label = QLabel(tr("your_cube").capitalize())
        self.cube_label.setObjectName("sectionTitle")
        self.cube_label.setAlignment(Qt.AlignCenter)
        cube_box.addWidget(self.cube_label)
        cube_box.addWidget(self.live_cube, 1)
        self.live_cube_panel.setVisible(False)
        row.addWidget(self.live_cube_panel, 1)
        pv.addLayout(row)
        rc.addWidget(self.preview_panel)
        self.chart_panel = QWidget()
        cv = QVBoxLayout(self.chart_panel)
        cv.setContentsMargins(8, 4, 10, 10)
        cv.setSpacing(8)
        tabs = QHBoxLayout()
        tabs.setSpacing(2)
        self.chart_tabs = QButtonGroup(self)
        self.chart_tabs.setExclusive(True)
        for idx, key in enumerate(("tab_progress", "tab_distribution")):
            b = QPushButton(tr(key).upper())
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setChecked(idx == 0)
            self.chart_tabs.addButton(b, idx)
            tabs.addWidget(b)
        tabs.addStretch(1)
        cv.addLayout(tabs)
        self.chart_stack = QStackedWidget()
        self.chart = TimeChart()
        self.chart.solve_clicked.connect(self.open_solve)
        self.histogram = TimeHistogram()
        self.chart_stack.addWidget(self.chart)
        self.chart_stack.addWidget(self.histogram)
        self.chart_tabs.buttonClicked[int].connect(self.chart_stack.setCurrentIndex)
        cv.addWidget(self.chart_stack, 1)
        rc.addWidget(self.chart_panel, 1)
        body.addWidget(self.right_panel)
        self._apply_visibility()

    def _setup_table(self, t):
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.setFocusPolicy(Qt.NoFocus)
        t.verticalHeader().setVisible(False)
        t.setShowGrid(False)
        t.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        h = t.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Stretch)
        h.setHighlightSections(False)
        t.setCursor(Qt.PointingHandCursor)

    @staticmethod
    def _qcolor(c):
        return QColor(c)

    def _build_shortcuts(self):
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.WindowShortcut)
            s.activated.connect(fn)
            return s

        sc("Ctrl+1", lambda: self.set_last_penalty(OK))
        sc("Ctrl+2", lambda: self.set_last_penalty(PLUS2))
        sc("Ctrl+3", lambda: self.set_last_penalty(DNF))
        sc("Ctrl+Z", self.delete_last)
        sc("N", self.new_scramble)
        sc("Shift+N", self.previous_scramble)
        sc("Ctrl+E", self.manual_entry)
        sc("Ctrl+,", self.open_settings)
        sc("Ctrl+K", self.open_command_palette)
        sc("M", self.toggle_minimal)
        sc("Ctrl+T", lambda: self.open_window("timer"))
        sc("Ctrl+Shift+1", lambda: self.open_window("training"))
        sc("Ctrl+Shift+2", lambda: self.open_window("reference"))
        sc("Ctrl+Shift+3", lambda: self.open_window("achievements"))

    def _apply_visibility(self):
        st = self.state
        busy = st in (INSPECTING, HOLDING, READY, RUNNING)
        # Holding Space without inspection keeps the UI visible (red/green
        # colour feedback); once the timer is armed or running, focus mode
        # hides everything but the time.
        focus_state = st in (INSPECTING, READY, RUNNING) or \
            (st == HOLDING and self.insp_start is not None)
        show = not (self.settings.get("focus_mode") and focus_state)
        self.top_bar.setVisible(show)
        minimal = bool(self.settings.get("minimal"))
        self.left_panel.setVisible(show and not minimal)
        self.scramble_panel.setVisible(show)
        self.pen_bar.setVisible(show and not busy and self._current_solves_count() > 0)
        has = self._current_solves_count() > 0
        # Keep the smart-cube scramble check visible even in sessions that
        # already have solves; otherwise the most useful readiness feedback
        # disappears as soon as the first result is recorded.
        self.hint.setVisible(show and not busy
                             and (not has or self._ble_uses_cube_start()))
        self.times_table.setVisible(has)
        self.empty_label.setVisible(not has)
        want_preview = bool(self.settings.get("show_preview"))
        want_chart = bool(self.settings.get("show_chart"))
        self.right_panel.setVisible(show and not minimal and (want_preview or want_chart))
        self.preview_panel.setVisible(want_preview)
        self.chart_panel.setVisible(want_chart)
        navigation_allowed=not busy and not self._mini_timer_busy()
        self.previous_scramble_button.setEnabled(navigation_allowed and self.scramble_history.can_previous(self.session.id))
        self.next_scramble_button.setEnabled(navigation_allowed)
        if hasattr(self,"update_banner"):
            self._update_changed()

    def _current_solves_count(self):
        s = self.store.current
        return len(s.solves) if s else 0

    # ==================================================================
    # Sessions & puzzles
    # ==================================================================
    @property
    def session(self):
        return self.store.current

    def select_puzzle(self, pid):
        if self.session and self.session.puzzle == pid:
            return
        existing = self.store.sessions_for(pid)
        if existing:
            target = existing[-1]
        else:
            target = self.store.new_session(scr.PUZZLE_LABEL[pid], pid)
        self.switch_session(target.id)

    def switch_session(self, sid):
        self.store.current_id = sid
        sess = self.session
        if sess is None:
            return
        self._loading = True
        for pid, act in self.event_actions.items():
            act.setChecked(pid == sess.puzzle)
        self._update_puzzle_caption()
        self.session_combo.clear()
        for s in self.store.sessions_for(sess.puzzle):
            self.session_combo.addItem(s.name, s.id)
        idx = self.session_combo.findData(sid)
        self.session_combo.setCurrentIndex(max(0, idx))
        self._loading = False
        self.cancel_timer()
        current=self.scramble_history.current(sid)
        if current is None:
            self.new_scramble(force=True)
        else:
            self._display_scramble(current)
        self.refresh()
        self.save()

    def _on_session_combo(self, idx):
        if self._loading or idx < 0:
            return
        sid = self.session_combo.itemData(idx)
        if sid and sid != self.store.current_id:
            self.switch_session(sid)

    def new_session(self):
        pid = self.session.puzzle if self.session else "333"
        default = "%s #%d" % (scr.PUZZLE_LABEL[pid], len(self.store.sessions_for(pid)) + 1)
        name, ok = QInputDialog.getText(self, tr("new_session"), tr("session_name"),
                                        QLineEdit.Normal, default)
        if ok and name.strip():
            s = self.store.new_session(name.strip(), pid)
            self.switch_session(s.id)

    def rename_session(self):
        s = self.session
        name, ok = QInputDialog.getText(self, tr("rename_session"), tr("session_name"),
                                        QLineEdit.Normal, s.name)
        if ok and name.strip():
            s.name = name.strip()
            self.switch_session(s.id)

    def delete_session(self):
        s = self.session
        if QMessageBox.question(self, tr("delete_session"),
                                tr("confirm_delete_session") % (s.name, len(s.solves))) \
                != QMessageBox.Yes:
            return
        pid = s.puzzle
        self.store.delete_session(s.id)
        rest = self.store.sessions_for(pid)
        self.switch_session(rest[-1].id if rest else self.store.current_id)

    def clear_session(self):
        s = self.session
        if not s.solves:
            return
        if QMessageBox.question(self, tr("clear_session"),
                                tr("confirm_clear") % len(s.solves)) != QMessageBox.Yes:
            return
        s.solves = []
        self.refresh()
        self.save()

    # ==================================================================
    # Scrambles
    # ==================================================================
    def new_scramble(self, force=False):
        if force is not True and self.state==STOPPED:
            self.state=IDLE
            self._apply_visibility()
            self._render()
        if getattr(self, "page", 0) != 0 and force is not True and self.scramble:
            return
        if self.state != IDLE and force is not True:
            return
        if force is not True and self._mini_timer_busy():
            return
        puzzle = self.session.puzzle
        value=self.scramble_history.next(self.session.id,lambda:scr.generate(puzzle),fresh=force is True)
        self._display_scramble(value)

    def previous_scramble(self):
        if self.state==STOPPED:
            self.state=IDLE
            self._apply_visibility()
            self._render()
        if self.state!=IDLE or self.page!=0 or self._mini_timer_busy():
            return
        if self.scramble_history.can_previous(self.session.id):
            self._display_scramble(self.scramble_history.previous(self.session.id))

    def _mini_timer_busy(self):
        return any(getattr(w,"state",IDLE) in (HOLDING,READY,INSPECTING,RUNNING) for w in self.extra_windows)

    def _display_scramble(self,value):
        puzzle=self.session.puzzle
        self.scramble=value
        self.previous_scramble_button.setEnabled(self.scramble_history.can_previous(self.session.id))
        self.scramble_moves_label.setText(self.scramble)
        self._prepare_ble_target()
        size = {"444": 19, "555": 17, "666": 15, "777": 14, "minx": 15,
                "333fm": 20}.get(puzzle, 23)
        self.scramble_moves_label.setStyleSheet(
            "font-size: %dpx; font-weight: 500; color: %s;" % (size, theme.SCRAMBLE))
        self.preview.set_scramble(puzzle, self.scramble)
        self._sync_windows()
        if hasattr(self, "hint_text") and self.state == IDLE:
            self._update_ble_scramble_status()

    def copy_scramble(self):
        QApplication.clipboard().setText(self.scramble)
        self.toast.show_message(tr("copied"), 1200)

    # ==================================================================
    # Timer state machine
    # ==================================================================
    def on_key_press(self, key, auto_repeat):
        if self.state == RUNNING:
            if not auto_repeat:
                self.stop_solve()
            return True
        if self.state == STOPPED:
            if auto_repeat:
                return True
            self.state = IDLE  # the release of the stopping key was lost
        if key == Qt.Key_Escape and self.state in (INSPECTING, HOLDING, READY):
            self.cancel_timer()
            return True
        if key != Qt.Key_Space:
            return False
        if auto_repeat:
            return True
        if self.state == IDLE:
            if self._ble_uses_cube_start() and not self.ble_scramble_ready:
                self._render()
                return True
            if self._ble_uses_cube_start() and not self.settings.get("inspection"):
                # smart cube without inspection: Space behaves like the
                # usual hold (a cube turn also starts, Space or not)
                self.state = READY
                self.insp_start = None
                self._apply_visibility()
                self._render()
                return True
            if self.settings.get("inspection"):
                self.arm_inspection = True
            else:
                self._begin_hold()
        elif self.state == INSPECTING:
            self._begin_hold()
        return True

    def on_key_release(self, key, auto_repeat):
        if auto_repeat:
            return key == Qt.Key_Space or self.state != IDLE
        if self.state == STOPPED:
            self.state = IDLE
            self._apply_visibility()
            self._render()
            return True
        if key != Qt.Key_Space:
            return self.state != IDLE
        if self.state == IDLE and self.arm_inspection:
            self.arm_inspection = False
            self._start_inspection()
        elif self.state == HOLDING:
            self.state = INSPECTING if self.insp_start is not None else IDLE
            self._apply_visibility()
            self._render()
        elif self.state == READY:
            self.start_solve()
        return True

    def _begin_hold(self):
        self.hold_start = time.perf_counter()
        self.state = HOLDING
        if int(self.settings.get("hold_ms", 300)) <= 0:
            self.state = READY
        self._apply_visibility()
        self._render()

    def _start_inspection(self):
        self.insp_start = time.perf_counter()
        self.insp_alerts_done = set()
        self.state = INSPECTING
        self._apply_visibility()
        self._render()

    def start_solve(self):
        if self.solve_assistant is not None and self.solve_assistant.is_guiding:
            return
        self.insp_penalty = OK
        if self.insp_start is not None:
            used = time.perf_counter() - self.insp_start
            if used > INSPECTION_S + 2:
                self.insp_penalty = DNF
            elif used > INSPECTION_S:
                self.insp_penalty = PLUS2
        self.insp_start = None
        self.t_start = time.perf_counter()
        self.ble_moves = 0
        self._solve_events = []
        self._solve_event_origin = None
        self._solve_initial = (self.ble_state.facelets()
                               if self._ble_session_connected() and self.ble_state and self._cube_state_trusted else None)
        self.ble_saw_unsolved = bool(self.ble_state is not None
                                     and not self.ble_state.solved)
        self.state = RUNNING
        self.ble_scramble_ready = False
        self._apply_visibility()
        self._render()

    def stop_solve(self, elapsed_ms=None):
        if elapsed_ms is None:
            elapsed_ms = int((time.perf_counter() - self.t_start) * 1000)
        self.t_start_ble = None
        self.state = STOPPED
        solve = Solve(elapsed_ms, self.insp_penalty, self.scramble)
        if self._solve_initial and self._solve_events:
            from .solver import apply_moves
            final = self.ble_state.facelets() if self.ble_state else None
            replayed = apply_moves(self._solve_initial, " ".join(e[1] for e in self._solve_events))
            solve.telemetry = {"initial": self._solve_initial, "events": self._solve_events,
                               "verified": replayed == final}
        self.insp_penalty = OK
        self._add_solve(solve)
        self.new_scramble(force=True)
        self._apply_visibility()
        self._render()

    def cancel_timer(self):
        self.state = IDLE
        self.insp_start = None
        self.arm_inspection = False
        self.insp_penalty = OK
        self.t_start_ble = None
        self._apply_visibility()
        self._render()

    def _on_tick(self):
        if self.state == HOLDING:
            if (time.perf_counter() - self.hold_start) * 1000 >= int(self.settings.get("hold_ms", 300)):
                self.state = READY
        if self.insp_start is not None and self.state in (INSPECTING, HOLDING, READY):
            used = time.perf_counter() - self.insp_start
            if self.settings.get("inspection_alerts"):
                for mark in (8, 12):
                    if used >= mark and mark not in self.insp_alerts_done:
                        self.insp_alerts_done.add(mark)
                        QApplication.beep()
        if self.state != IDLE:
            self._render()

    def _render(self):
        d = int(self.settings.get("decimals", 2))
        st = self.state
        if st == RUNNING:
            ms = int((time.perf_counter() - self.t_start) * 1000)
            mode = self.settings.get("update_mode", "full")
            if mode == "hidden":
                text = tr("solving")
            elif mode == "seconds":
                text = fmt_ms(ms, 2).split(".")[0]
            elif mode == "tenths":
                text = fmt_ms(ms, 1)
            else:
                text = fmt_ms(ms, d)
            self.timer_display.set_display(text, theme.TEXT)
            return
        if self.insp_start is not None and st in (INSPECTING, HOLDING, READY):
            used = time.perf_counter() - self.insp_start
            left = INSPECTION_S - used
            if left > 0:
                text = str(int(left) + 1)
            elif left > -2:
                text = "+2"
            else:
                text = "DNF"
            color = {HOLDING: theme.HOLD, READY: theme.READY}.get(st, theme.INSPECT)
            self.timer_display.set_display(text, color, tr("inspection"))
            return
        if st == HOLDING:
            self.timer_display.set_display(self._last_text(d), theme.HOLD)
            return
        if st == READY:
            self.timer_display.set_display(fmt_ms(0, d), theme.READY)
            return
        self.timer_display.set_display(self._last_text(d), theme.TEXT, self._last_sub())
        if self._ble_session_connected() and not self._cube_state_trusted:
            self.hint_text.setText(tr("sync_required_detail"))
            return
        if self._ble_uses_cube_start():
            if self.ble_state is None:
                self.hint_text.setText(tr("ble_identifying"))
            else:
                self.hint_text.setText(
                    tr("ble_ready_first_turn") if self.ble_scramble_ready
                    else tr("ble_apply_scramble"))
        else:
            self.hint_text.setText(tr("hint_inspect") if self.settings.get("inspection") else tr("hint_ready"))

    def _last_text(self, d):
        s = self.session
        if s and s.solves:
            return fmt_solve(s.solves[-1], d)
        return fmt_ms(0, d)

    def _last_sub(self):
        if not self.stats or self.stats.count == 0:
            return ""
        parts = []
        for label in ("ao5", "ao12"):
            v = self.stats.rows[label]["current"]
            if v is not None:
                parts.append("%s  %s" % (label, fmt_avg(v, int(self.settings.get("decimals", 2)))))
        return "     ".join(parts)

    # ==================================================================
    # Solves
    # ==================================================================
    def _add_solve(self, solve):
        sess = self.session
        old = self.stats
        sess.solves.append(solve)
        self.refresh()
        self.save()
        self._check_pb(old)
        if not self.toast.isVisible():
            self.check_achievements()
        else:
            ach.check(self.store)   # unlock silently, the PB toast is showing

    def _check_pb(self, old):
        if old is None or self.stats is None:
            return
        d = int(self.settings.get("decimals", 2))
        for label in ("ao100", "ao50", "ao12", "ao5", "single"):
            new_row = self.stats.rows[label]
            old_best = old.rows[label]["best"]
            cur = new_row["current"]
            if cur is None or cur == INF or old_best is None:
                continue
            if cur < old_best:
                name = tr("single") if label == "single" else label
                val = fmt_ms(cur, d) if label == "single" else fmt_avg(cur, d)
                self.toast.show_message(tr("new_pb") % (name, val), 3500)
                return

    def set_last_penalty(self, pen):
        if self.state != IDLE or not self.session.solves:
            return
        self.session.solves[-1].penalty = pen
        self.refresh()
        self.save()

    def delete_last(self):
        if self.state != IDLE or not self.session.solves:
            return
        s = self.session.solves[-1]
        if QMessageBox.question(self, tr("delete"),
                                tr("confirm_delete_solve") % fmt_solve(s)) != QMessageBox.Yes:
            return
        self.session.solves.pop()
        self.refresh()
        self.save()

    def comment_last(self):
        if not self.session.solves:
            return
        s = self.session.solves[-1]
        text, ok = QInputDialog.getText(self, tr("comment"), tr("comment_prompt"),
                                        QLineEdit.Normal, s.comment)
        if ok:
            s.comment = text.strip()
            self.refresh()
            self.save()

    def manual_entry(self):
        if self.state != IDLE:
            return
        text, ok = QInputDialog.getText(self, tr("manual_entry"), tr("enter_time"))
        if not ok or not text.strip():
            return
        try:
            ms, pen = parse_time(text)
        except ValueError:
            QMessageBox.warning(self, tr("manual_entry"), tr("bad_time"))
            return
        self._add_solve(Solve(ms, pen, self.scramble))
        self.new_scramble(force=True)

    def open_solve(self, index):
        if self.state in (HOLDING, READY, INSPECTING, RUNNING) or self._mini_timer_busy():
            return
        solves = self.session.solves
        if not (0 <= index < len(solves)):
            return
        dlg = SolveDialog(solves[index], index + 1, int(self.settings.get("decimals", 2)), self)
        dlg.exec_()
        if dlg.deleted:
            del solves[index]
        self.refresh()
        self.save()

    # ==================================================================
    # Tables
    # ==================================================================
    def refresh(self):
        sess = self.session
        self.stats = SessionStats(sess.solves)
        st = self.stats
        d = int(self.settings.get("decimals", 2))

        # stats panel
        for column, button in enumerate(self.single_metrics, 1):
            value = st.rows["single"]["current" if column == 1 else "best"]
            text = fmt_solve(sess.solves[-1], d) if column == 1 and sess.solves else fmt_ms(value, d)
            if value == INF:
                text = "DNF"
            if value is None:
                text = "—"
            button.setText(text)
            button.setStyleSheet("font-size: %dpx; color: %s;" % (
                24 if len(text)<=6 else 20 if len(text)<=8 else 14,
                theme.ACCENT if column==2 else theme.TEXT))
            button.setToolTip(tr("solve_click_hint"))
            button.setEnabled(value is not None)
        for r, (label, _size, kind) in enumerate(STAT_ROWS):
            row = st.rows[label]
            fmt = (lambda v: fmt_ms(v, d)) if kind == "single" else (lambda v: fmt_avg(v, d))
            cur = QTableWidgetItem(fmt(row["current"]) if row["current"] is not None else "-")
            best = QTableWidgetItem(fmt(row["best"]) if row["best"] is not None else "-")
            best.setForeground(self._qcolor(theme.ACCENT))
            cur.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            best.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cur.setToolTip(cur.text()+"\n"+tr("average_click_hint"))
            best.setToolTip(best.text()+"\n"+tr("average_click_hint"))
            self.stats_table.setItem(r, 1, cur)
            self.stats_table.setItem(r, 2, best)
        mean = fmt_avg(st.session_mean, d) if st.session_mean is not None else "-"
        sd = fmt_avg(st.std_dev, d) if st.std_dev is not None else "-"
        self.summary.setText(tr("stats_session_mean") % mean)
        self.summary.setToolTip(tr("stats_session_detail") % (st.count, st.dnf_count, sd))
        self.history_count.setText(str(st.count))
        self._update_stats_rows()

        # times list (newest first)
        n = len(sess.solves)
        t = self.times_table
        t.setUpdatesEnabled(False)
        t.setRowCount(n)
        best_i = st.rows["single"]["best_index"]
        ao5 = st.series["ao5"]
        ao12 = st.series["ao12"]
        t.setColumnHidden(2, n < 5)
        t.setColumnHidden(3, n < 12)
        for row in range(n):
            i = n - 1 - row
            s = sess.solves[i]
            cells = [str(i + 1), fmt_solve(s, d),
                     fmt_avg(ao5[i], d) if ao5[i] is not None else "—",
                     fmt_avg(ao12[i], d) if ao12[i] is not None else "—"]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                it.setTextAlignment((Qt.AlignLeft if c == 0 else Qt.AlignRight) | Qt.AlignVCenter)
                has_average = c == 2 and ao5[i] is not None or c == 3 and ao12[i] is not None
                it.setToolTip(txt+"\n"+(tr("average_click_hint") if has_average else tr("solve_click_hint")))
                it.setData(Qt.UserRole, i)
                if c == 0:
                    it.setForeground(self._qcolor(theme.MUTED))
                elif c == 1:
                    if i == best_i:
                        it.setForeground(self._qcolor(theme.ACCENT))
                    elif s.penalty == DNF:
                        it.setForeground(self._qcolor(theme.DNF_RED))
                    if s.comment:
                        it.setToolTip(s.comment)
                        it.setText(txt + "  •")
                t.setItem(row, c, it)
        t.setUpdatesEnabled(True)

        # chart
        self.chart.set_data(st.values, ao5, ao12, d)
        self.histogram.set_data(st.values)

        # penalty bar
        last = sess.solves[-1] if sess.solves else None
        for val, b in self.pen_buttons.items():
            b.setChecked(bool(last) and last.penalty == val)
        self._apply_visibility()
        self._render()
        self._sync_windows()

    def _show_stats_help(self):
        TextDialog(tr("stats_average_help_title"), tr("stats_average_help_body"), self).exec_()

    def _update_stats_rows(self):
        if self.stats is None:
            return
        visible = 0
        for row, (_label, size, _kind) in enumerate(STAT_ROWS):
            show = row > 0 and (self.all_averages.isChecked() or self.stats.count >= size)
            self.stats_table.setRowHidden(row, not show)
            visible += int(show)
        self.stats_table.setVisible(visible > 0)
        self.stats_table.setFixedHeight(32*visible + self.stats_table.horizontalHeader().sizeHint().height()+4)
        self.averages_empty.setVisible(visible == 0)
        self.averages_empty.setText(tr("stats_need_solves") % max(0, 3-self.stats.count))
        self.all_averages.setVisible(0 < self.stats.count < 100)
        self.all_averages.setText(tr("stats_hide_averages") if self.all_averages.isChecked() else tr("stats_all_averages"))

    def _row_index(self, row):
        it = self.times_table.item(row, 0)
        return it.data(Qt.UserRole) if it is not None else None

    def _on_time_clicked(self, row, col):
        i = self._row_index(row)
        if i is None:
            return
        if col == 2 and self.stats.series["ao5"][i] is not None:
            self.show_average(5, i)
        elif col == 3 and self.stats.series["ao12"][i] is not None:
            self.show_average(12, i)
        else:
            self.open_solve(i)

    def _on_time_double_clicked(self, row, col):
        if col in (0, 1):
            i = self._row_index(row)
            if i is not None:
                self.open_solve(i)

    def _times_menu(self, pos):
        row = self.times_table.rowAt(pos.y())
        if row < 0:
            return
        i = self._row_index(row)
        s = self.session.solves[i]
        m = QMenu(self)
        for label, val in ((tr("ok"), OK), (tr("plus2"), PLUS2), (tr("dnf"), DNF)):
            a = QAction(label, m)
            a.setCheckable(True)
            a.setChecked(s.penalty == val)
            a.triggered.connect(lambda _=False, v=val: self._set_penalty(i, v))
            m.addAction(a)
        m.addSeparator()
        m.addAction(tr("comment") + "…", lambda: self.open_solve(i))
        m.addAction(tr("copy_scramble_menu"),
                    lambda: QApplication.clipboard().setText(s.scramble))
        m.addSeparator()
        m.addAction(tr("delete"), lambda: self._delete_index(i))
        m.exec_(self.times_table.viewport().mapToGlobal(pos))

    def _set_penalty(self, i, pen):
        self.session.solves[i].penalty = pen
        self.refresh()
        self.save()

    def _delete_index(self, i):
        s = self.session.solves[i]
        if QMessageBox.question(self, tr("delete"),
                                tr("confirm_delete_solve") % fmt_solve(s)) == QMessageBox.Yes:
            del self.session.solves[i]
            self.refresh()
            self.save()

    def _on_stat_clicked(self, row, col):
        if col not in (1, 2) or not self.stats:
            return
        label, size, kind = STAT_ROWS[row]
        info = self.stats.rows[label]
        if col == 1:
            end = self.stats.count - 1 if info["current"] is not None else None
        else:
            end = info["best_index"]
        if end is None:
            return
        if kind == "single":
            self.open_solve(end)
        else:
            self.show_average(size, end, mean=(kind == "mean"))

    def show_average(self, size, end, mean=False):
        """Show the breakdown of the average of `size` solves ending at `end`."""
        d = int(self.settings.get("decimals", 2))
        solves = self.session.solves[end - size + 1:end + 1]
        if len(solves) < size:
            return
        values = [s.value for s in solves]
        label = ("mo%d" if mean else "ao%d") % size
        avg = stats_mean(values) if mean else stats_average(values)
        trimmed = set() if mean else trimmed_indices(values)
        lines = ["%s: %s" % (label, fmt_avg(avg, d)), ""]
        for k, s in enumerate(solves):
            t = fmt_solve(s, d)
            if k in trimmed:
                t = "(%s)" % t
            line = "%d. %-12s %s" % (end - size + 2 + k, t, s.scramble.replace("\n", " "))
            if s.comment:
                line += "   // " + s.comment
            lines.append(line)
        TextDialog(label, "\n".join(lines), self).exec_()

    # ==================================================================
    # Import / export / settings
    # ==================================================================
    def import_cstimer(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("import_cstimer"), "",
                                              "csTimer export (*.txt *.json);;All files (*)")
        if not path:
            return
        try:
            sessions = storage.import_cstimer(path)
        except Exception as e:  # noqa: BLE001 - show any parse error to the user
            QMessageBox.warning(self, tr("import_cstimer"), tr("import_failed") % e)
            return
        total = 0
        for s in sessions:
            self.store.sessions.append(s)
            total += len(s.solves)
        if sessions:
            self.switch_session(sessions[0].id)
        QMessageBox.information(self, tr("import_cstimer"),
                                tr("imported") % (len(sessions), total))

    def export_csv(self):
        s = self.session
        default = os.path.join(os.path.expanduser("~"), "%s.csv" % s.name.replace(" ", "_"))
        path, _ = QFileDialog.getSaveFileName(self, tr("export_csv"), default, "CSV (*.csv)")
        if not path:
            return
        storage.export_csv(s, path, int(self.settings.get("decimals", 2)))
        self.toast.show_message(tr("exported") % os.path.basename(path), 2500)

    def export_cstimer(self):
        s = self.session
        default = os.path.join(os.path.expanduser("~"), "%s.txt" % s.name.replace(" ", "_"))
        path, _ = QFileDialog.getSaveFileName(self, tr("export_cstimer"), default,
                                              "csTimer export (*.txt)")
        if not path:
            return
        storage.export_cstimer(s, path)
        self.toast.show_message(tr("exported") % os.path.basename(path), 2500)

    def set_page(self, idx):
        if self.state != IDLE:
            self.nav_group.button(self.page).setChecked(True)
            return
        if self.page_widgets.get(idx) is None and idx > 0:
            if idx == 1:
                # open the path of the event the user is timing
                path = self.session.puzzle if self.session.puzzle in learn.PATHS else "333"
                if not self.store.settings.get("train_path"):
                    self.hub.path = path
                w = self.training = TrainingWidget(self.hub)
            elif idx == 2:
                w = ReferencePage(self.hub)
                w.show_puzzle(self.reference_puzzle())
                ach.set_flag(self.store, "reference")
            else:
                w = self.achievements_page = AchievementsPage(self.store)
            self.page_widgets[idx] = w
            self.pages.addWidget(w)
        if idx == 3 and self.achievements_page is not None:
            self.achievements_page.refresh()
        self.page = idx
        self.pages.setCurrentWidget(self.page_widgets[idx] if idx else self.timer_page)
        if idx in (1, 2):
            self.check_achievements()
        self.puzzle_bar.setVisible(idx == 0)
        self.minimal_action.setEnabled(idx == 0)
        b = self.nav_group.button(idx)
        if b and not b.isChecked():
            b.setChecked(True)

    def _training_changed(self):
        ach.mark_day(self.store)
        self.check_achievements()

    def check_achievements(self, quiet=False):
        new, _ = ach.check(self.store)
        if not new:
            return
        self.save()
        self._sync_windows()
        if quiet:
            return
        if len(new) == 1:
            self.toast.show_message("★  " + tr("ach_new") % pick(new[0]["name"]), 4500)
        else:
            self.toast.show_message("★  " + tr("ach_many") % len(new), 4500)

    def reference_puzzle(self):
        pid = self.session.puzzle
        return {"555": "444", "666": "444", "777": "444", "333oh": "333",
                "333bf": "333", "333fm": "333"}.get(pid, pid)

    def open_window(self, kind):
        """Open a section (or the mini timer) in its own window."""
        if self.state != IDLE:
            return None
        from .windows import MiniTimerWindow, PageWindow
        ach.set_flag(self.store, "training_window")
        if kind == "reference":
            ach.set_flag(self.store, "reference")
        win = MiniTimerWindow(self) if kind == "timer" else PageWindow(self, kind)
        self.extra_windows.append(win)
        win.destroyed.connect(lambda *_: self.extra_windows.remove(win)
                              if win in self.extra_windows else None)
        k = len(self.extra_windows)
        geo = self.geometry()
        win.move(geo.x() + 40 + 30 * k, geo.y() + 30 + 30 * k)
        win.show()
        win.raise_()
        win.activateWindow()
        self.check_achievements()
        return win

    def open_command_palette(self):
        if self.state not in (IDLE, STOPPED):
            return
        if self.state == STOPPED:
            self.cancel_timer()
        from .commands import CommandPalette
        CommandPalette(self).exec_()

    def open_cube_window(self):
        """Open or raise a dedicated, live 3D view of the smart cube."""
        if self.state != IDLE:
            return None
        if self.live_cube_window is not None:
            if self.live_cube_window.isMinimized():
                self.live_cube_window.showNormal()
            self.live_cube_window.raise_()
            self.live_cube_window.activateWindow()
            return self.live_cube_window
        from .windows import LiveCubeWindow
        win = LiveCubeWindow(self)
        self.live_cube_window = win
        self.extra_windows.append(win)
        win.destroyed.connect(lambda *_: self._cube_window_closed(win))
        geo = self.geometry()
        win.move(geo.x() + 80, geo.y() + 55)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def open_solve_assistant(self):
        if self.state not in (IDLE, STOPPED):
            return None
        if self.solve_assistant is None:
            from .assistant import SolveAssistantWindow
            win = SolveAssistantWindow(self)
            self.solve_assistant = win
            self.extra_windows.append(win)
            win.destroyed.connect(lambda *_: self._assistant_closed(win))
        self.solve_assistant.show()
        self.solve_assistant.raise_()
        self.solve_assistant.activateWindow()
        return self.solve_assistant

    def _assistant_closed(self, win):
        if win in self.extra_windows:
            self.extra_windows.remove(win)
        if self.solve_assistant is win:
            self.solve_assistant = None

    def open_cube_sync(self):
        if self._raw_ble_state is None or not self.cube_btn.isChecked() or self.state == RUNNING:
            self.toast.show_message(tr("assistant_wait"), 4000)
            return False
        from .sync_dialog import CubeSyncDialog
        from .cube_sync import StateCalibration
        if self.solve_assistant is not None:
            self.solve_assistant.stop()
        dialog = CubeSyncDialog(self)
        self._sync_dialog = dialog
        try:
            result = dialog.exec_()
        finally:
            self._sync_dialog = None
        if result != QDialog.Accepted:
            return False
        calibration = StateCalibration.between(self._raw_ble_state, dialog.target)
        address = self._ble_connected_address or self.settings.get("ble_last_address")
        self.settings.setdefault("ble_state_calibrations", {})[address] = {
            "profile": self.ble_profile, "mapping": calibration.to_dict()}
        self._ble_state(self._raw_ble_state)
        self.save()
        self.toast.show_message(tr("sync_saved"), 5000)
        return True

    def _cube_window_closed(self, win):
        if win in self.extra_windows:
            self.extra_windows.remove(win)
        if self.live_cube_window is win:
            self.live_cube_window = None

    def open_training_window(self):
        return self.open_window("training")

    def _sync_windows(self):
        for w in list(self.extra_windows):
            try:
                w.sync()
            except RuntimeError:   # already deleted by Qt
                pass

    def toggle_minimal(self):
        if self.state != IDLE or self.page != 0:
            return
        self.settings["minimal"] = not self.settings.get("minimal")
        self.minimal_action.setChecked(bool(self.settings["minimal"]))
        self._apply_visibility()
        self.save()

    def showEvent(self, e):
        QMainWindow.showEvent(self, e)
        if not getattr(self, "_dark_title", False):
            self._dark_title = True
            theme.fit_to_screen(self)
            _dark_title_bar(self)

    def show_about(self):
        if self.state == IDLE:
            AboutDialog(os.path.join(ASSETS, "logo_full.png"), self).exec_()

    def _update_changed(self):
        service=self.updater
        visible=(service.state in ("available","downloading","ready") and
                 self.state==IDLE and not self._mini_timer_busy() and not self.settings.get("minimal"))
        self.update_banner.setVisible(visible)
        self.update_banner_text.setText(service.description())
        self.update_banner_action.setVisible(service.state in ("available","ready"))
        self.update_banner_action.setText(tr("update_restart" if service.state=="ready" else "update_download"))
        self.update_banner_action.setEnabled(service.can_install and not service.busy)
        self.update_banner_action.setToolTip("" if service.can_install else tr("update_desktop_only"))
        if service.manual and service.state in ("current","error") and service.state!=self._last_update_state and hasattr(self,"toast"):
            self.toast.show_message(service.description(),5000)
        self._last_update_state=service.state

    def check_updates(self):
        try:
            self.updater.check(manual=True)
        except OSError as error:
            QMessageBox.warning(self, "Enigma Hub", str(error))

    def _update_action(self):
        if self.updater.state=="ready":
            self.install_update()
        else:
            self.updater.start_download()

    def install_update(self):
        if self.state!=IDLE or self._mini_timer_busy():
            self.toast.show_message(tr("update_finish_solve"),5000)
            return
        try:
            self.store.save()
            self.updater.apply()
        except OSError:
            QMessageBox.warning(self,tr("updates_section"),tr("update_install_error"))
            return
        except Exception:
            QMessageBox.warning(self,tr("updates_section"),tr("update_integrity_error"))
            return
        self.close()

    def open_settings(self):
        # A completed solve briefly leaves the timer in STOPPED until the
        # stopping key is released. That release can be lost when focus moves
        # to a toolbar button, which otherwise makes Settings silently unusable.
        if self.state == STOPPED:
            self.state = IDLE
            self._apply_visibility()
            self._render()
        if self.state != IDLE:
            return
        from .i18n import configured_language
        old_lang = configured_language(self.settings)
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_():
            self.settings.update(dlg.settings)
            if not self.settings.get("auto_update",True):
                self.updater.cancel()
            elif self.updater.can_install:
                QTimer.singleShot(0,self.updater.automatic_check)
            QApplication.instance().setProperty("reduceMotion", bool(self.settings.get("reduce_motion", False)))
            self.save()
            if configured_language(self.settings) != old_lang:
                QMessageBox.information(self, tr("settings"), tr("restart_needed"))
            # apply the live-cube visibility immediately
            self._apply_cube_view()
            self.cancel_timer()
            self.refresh()
            self._render()

    def _show_welcome(self):
        if self.settings.get("welcome_seen") or not self.settings.get("welcome_pending"):
            return
        dlg = WelcomeDialog(os.path.join(ASSETS, "header.png"), self)
        if dlg.exec_() == QDialog.Accepted:
            self.settings["welcome_seen"] = True
            self.settings["welcome_pending"] = False
            self.save()

    # ==================================================================
    # Smart cube (BLE)
    # ==================================================================
    def _ble_supported(self):
        """BLE only makes sense for 3x3 and needs the bleak package."""
        return (self.session is not None and self.session.puzzle == "333"
                and ble_mod is not None)

    def _ble_start_worker(self, auto_reconnect=True):
        """Create the worker thread and wire its signals."""
        if self.ble is not None:
            # A failed startup used to leave a non-null but unusable worker
            # behind. Every later scan/connect then targeted its empty loop.
            if self.ble.isRunning() and self.ble._wait_for_loop():
                return True
            if self.ble.isRunning():
                # A worker whose event loop died cannot be reused. Tear it
                # down before creating a fresh scanner/connection worker.
                self.ble.stop()
                if self.ble.isRunning():
                    self._ble_error(tr("ble_error") % "Bluetooth worker could not be restarted")
                    return False
            self.ble.deleteLater()
            self.ble = None
        profiles = self.settings.get("ble_profiles", {})
        known = list(profiles) if isinstance(profiles, dict) else []
        known.append(self.settings.get("ble_last_address"))
        self.ble = ble_mod.GiikerWorker(self, known_addresses=known)
        self.ble.device_found_detailed.connect(self._ble_device_found_detailed)
        self.ble.scan_finished.connect(self._ble_scan_done)
        self.ble.connected.connect(self._ble_connected)
        self.ble.disconnected.connect(self._ble_disconnected)
        self.ble.move_received.connect(self._ble_move)
        self.ble.state_received.connect(self._ble_state)
        self.ble.profile_detected.connect(self._ble_profile_detected)
        self.ble.error.connect(self._ble_error)
        self.ble.reconnecting.connect(self._ble_reconnecting)
        self.ble.start()
        if not self.ble._wait_for_loop():  # noqa: SLF001 - startup race guard
            self.ble.error.emit(tr("ble_error") % "worker did not start")
            return False
        address = self.settings.get("ble_last_address") if auto_reconnect else None
        if address:
            profiles = self.settings.get("ble_profiles", {})
            profile = profiles.get(address) if isinstance(profiles, dict) else None
            self.ble_profile = profile
            self.ble.connect_to(address, quiet=True, profile=profile)
        return True

    def _ble_show_scan(self):
        if self.state == STOPPED:
            self.state = IDLE
            self._apply_visibility()
            self._render()
        if self.state != IDLE:
            return
        if not self._ble_supported():
            self.toast.show_message(tr("ble_ignore_hint"), 2500)
            return
        # Let the user choose a device in the picker. Starting a remembered
        # connection and a scan at once races the Windows BLE adapter.
        if not self._ble_start_worker(auto_reconnect=False):
            return
        dlg = BleScanDialog(self)
        dlg.exec_()

    def _ble_disconnect(self):
        if self.ble is not None:
            self.ble.disconnect()

    def _ble_connect(self, address, quiet=False):
        if not self._ble_start_worker(auto_reconnect=False):
            return
        profiles = self.settings.get("ble_profiles", {})
        profile = profiles.get(address) if isinstance(profiles, dict) else None
        self.ble.connect_to(address, quiet=quiet, profile=profile)

    def _ble_device_found(self, name, address):
        self._ble_devices[address] = name
        dlg = getattr(self, "_ble_scan_dialog", None)
        if dlg is not None:
            dlg.add_device(name, address)

    def _ble_device_found_detailed(self, name, address, is_cube):
        self._ble_devices[address] = name
        dlg = getattr(self, "_ble_scan_dialog", None)
        if dlg is not None:
            dlg.add_device(name, address, is_cube)
        # Remember only a plausible smart cube, never a random BLE peripheral.
        if is_cube and not self.settings.get("ble_last_address"):
            self.settings["ble_last_address"] = address

    def _ble_scan_done(self):
        dlg = getattr(self, "_ble_scan_dialog", None)
        if dlg is not None:
            dlg.scan_done()

    def _ble_connected(self, name, address):
        self.settings["ble_last_address"] = address
        self._ble_connected_address = address
        profiles = self.settings.setdefault("ble_profiles", {})
        if not isinstance(profiles, dict):
            profiles = self.settings["ble_profiles"] = {}
        self.ble_profile = profiles.get(address)
        self.save()
        self._ble_connected_name = name
        self.ble_solved_seen = False
        self.ble_wait_move = False
        self.cube_btn.setChecked(True)
        self.cube_btn.setText("●  " + tr("ble_btn_connected"))
        self._update_cube_connection_label()
        self.cube_scan_action.setEnabled(False)
        self.cube_disconnect_action.setEnabled(True)
        self.cube_frame_action.setEnabled(True)
        self.cube_frame_reset_action.setEnabled(True)
        self._update_ble_scramble_status()
        self.toast.show_message(tr("ble_connected_toast"), 2000)
        self._apply_cube_view()
        self._apply_visibility()
        self._render()
        self._sync_windows()
        if self._frame_perm is None:
            # On first use, walk the user through orienting the live view;
            # the state matcher itself remains rotation-invariant.
            QTimer.singleShot(500, self._ble_calibrate_frame)

    def _apply_cube_view(self):
        """Show/hide the live cube + its label per the connection and setting."""
        on = (self.cube_btn.isChecked()
              and bool(self.settings.get("ble_show_cube", True)))
        self.live_cube_panel.setVisible(on)

    def _ble_reconnecting(self, attempt):
        if self.cube_btn.isChecked():
            return
        self.cube_btn.setText(tr("ble_reconnecting") if attempt else tr("ble_btn_label"))
        message = tr("ble_reconnect_attempt") % attempt if attempt else tr("ble_reconnect_exhausted")
        self.cube_status.setText(message)
        self.toast.show_message(message, 5000)

    def _ble_disconnected(self):
        if self._frame_dialog is not None:
            self._frame_dialog.reject()
        was_connected = self.cube_btn.isChecked()
        self.cube_btn.setChecked(False)
        self.cube_btn.setText("◎  " + tr("ble_btn_label"))
        self._ble_connected_address = None
        self.ble_profile = None
        self.cube_status.setText(tr("ble_status_off"))
        self.cube_scan_action.setEnabled(True)
        self.cube_disconnect_action.setEnabled(False)
        self.cube_frame_action.setEnabled(False)
        self.cube_frame_reset_action.setEnabled(False)
        self.ble_state = None
        self._raw_ble_state = None
        self._cube_state_trusted = False
        self.ble_solved_seen = False
        self.ble_wait_move = False
        self.live_cube.set_state(None)
        self.hub.set_cube(None, False)   # trainer views leave live-cube mode
        self._apply_cube_view()
        self._apply_visibility()
        self._sync_windows()
        if was_connected:
            self.toast.show_message(tr("ble_disconnected_toast"), 2000)
        self._render()

    def _ble_profile_detected(self, address, profile):
        profiles = self.settings.setdefault("ble_profiles", {})
        if not isinstance(profiles, dict):
            profiles = self.settings["ble_profiles"] = {}
        profiles[address] = profile
        self.ble_profile = profile
        if address and not self.settings.get("ble_last_address"):
            self.settings["ble_last_address"] = address
        self.save()
        if self.cube_btn.isChecked():
            self._update_cube_connection_label()

    def _update_cube_connection_label(self):
        profile_key = {"std": "ble_profile_std", "clone": "ble_profile_clone"}.get(
            self.ble_profile, "ble_profile_detecting")
        self.cube_status.setText("%s — %s · %s" % (
            tr("ble_status_connected"), self._ble_connected_name, tr(profile_key)))

    def _ble_error(self, text):
        dlg = getattr(self, "_ble_scan_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.connection_failed()
            dlg.show_error(text)
            return
        if dlg is not None:
            dlg.connection_failed()
        self.toast.show_message(tr("ble_error") % text, 4000)

    def _ble_uses_cube_start(self):
        """True when the next start should come from the cube, not Space."""
        return (self.page == 0 and self._cube_state_trusted and self._sync_dialog is None
                and not (self.solve_assistant and self.solve_assistant.is_guiding)
                and self.ble is not None and self.cube_btn.isChecked()
                and bool(self.settings.get("ble_timer"))
                and self.session is not None and self.session.puzzle == "333")

    def _ble_state(self, state):
        self._raw_ble_state = state
        self._cube_state_trusted = False
        address = getattr(self.ble, "_address", None) or self.settings.get("ble_last_address")
        calibrations = self.settings.get("ble_state_calibrations", {})
        record = calibrations.get(address) if isinstance(calibrations, dict) else None
        if isinstance(record, dict) and record.get("profile") == self.ble_profile:
            try:
                from .cube_sync import StateCalibration
                state = StateCalibration.from_dict(record["mapping"]).apply(state)
                self._cube_state_trusted = True
            except (KeyError, ValueError, TypeError):
                pass
        self.ble_state = state
        facelets = state.facelets()
        if self._frame_perm is not None:
            facelets = cube_mod.rotate_frame_facelets(facelets, self._frame_perm)
        if self.settings.get("ble_show_cube", True):
            self.live_cube.set_state(facelets)
        self.hub.set_cube(facelets, self._cube_state_trusted)
        self._sync_windows()
        self._update_ble_scramble_status(facelets)
        if not self._cube_state_trusted:
            return
        if self.state in (INSPECTING, HOLDING, READY):
            self.ble_solved_seen = state.solved
            return
        if not self.settings.get("ble_stop_on_solve"):
            return
        if self.state == RUNNING and not state.solved:
            self.ble_saw_unsolved = True
        if (state.solved and self.ble_saw_unsolved and self.state == RUNNING
                and self.session is not None
                and self.session.puzzle == "333"):
            if self.t_start_ble is not None:
                # Both packets were timestamped on the worker thread; the
                # (roughly constant) BLE transport delay then cancels out
                # of the difference, instead of adding main-thread jitter.
                elapsed = int((state.time - self.t_start_ble) * 1000)
            else:
                elapsed = int((time.perf_counter() - self.t_start) * 1000)
            self.stop_solve(elapsed)

    def _ble_move(self, move):
        if self._frame_dialog is not None:
            self._frame_dialog.record_move(move)
            return  # calibration turns must never start or stop a solve
        if (self.state in (IDLE, READY, INSPECTING)
                and self._ble_uses_cube_start()
                and self.ble_scramble_ready):
            # no Space needed: grabbing the cube and turning it starts the
            # timer (in INSPECTING the standard +2/DNF penalties apply)
            self.start_solve()
            self.ble_moves = 1
            # the starting packet's monotonic timestamp (same clock as the
            # final packet's) gives an exact cube-to-cube duration
            self.t_start_ble = move.time
            self.ble_scramble_ready = False
        elif self.state == RUNNING:
            self.ble_moves += 1
        if self.state == RUNNING and self._solve_initial:
            if self._solve_event_origin is None:
                self._solve_event_origin = move.time
            self._solve_events.append([max(0, int((move.time - self._solve_event_origin) * 1000)), move.notation])

    def _ble_session_connected(self):
        return (self.cube_btn.isChecked() and self.session is not None
                and self.session.puzzle == "333")

    def _prepare_ble_target(self):
        """Precompute every whole-cube orientation of the active 3x3 scramble."""
        self._ble_target_states = set()
        self.ble_scramble_ready = False
        if self.session is None or self.session.puzzle != "333":
            return
        cube = cube_mod.Cube(3).apply(self.scramble)
        grid = cube.facelets()
        target = "".join(
            "".join(row) for face in "URFDLB" for row in grid[face])
        for rotation in cube_mod.whole_rotations():
            self._ble_target_states.add(cube_mod.rotate_frame_facelets(
                target, cube_mod.frame_perm(rotation)))
        if self.ble_state is not None:
            current = self.ble_state.facelets()
            if self._frame_perm is not None:
                current = cube_mod.rotate_frame_facelets(current, self._frame_perm)
            self.ble_scramble_ready = current in self._ble_target_states

    def _update_ble_scramble_status(self, facelets=None):
        if not self._ble_session_connected() or not self._cube_state_trusted:
            self.ble_scramble_ready = False
            return
        if not self._ble_target_states:
            self._prepare_ble_target()
        if facelets is None and self.ble_state is not None:
            facelets = self.ble_state.facelets()
            if self._frame_perm is not None:
                facelets = cube_mod.rotate_frame_facelets(facelets, self._frame_perm)
        self.ble_scramble_ready = (facelets in self._ble_target_states
                                   if facelets is not None else False)
        if self.state == IDLE:
            self._render()

    def _ble_calibrate_frame(self):
        if not self.cube_btn.isChecked() or self._frame_dialog is not None:
            return
        dlg = CubeFrameDialog(self)
        self._frame_dialog = dlg
        dlg.finished.connect(lambda _result, current=dlg:
                             self._clear_frame_dialog(current))
        dlg.exec_()

    def _clear_frame_dialog(self, dlg):
        if self._frame_dialog is dlg:
            self._frame_dialog = None

    def _load_frame_perm(self):
        raw = self.settings.get("ble_frame_rotation")
        try:
            mat = tuple(tuple(int(v) for v in row) for row in raw)
            self._frame_perm = cube_mod.frame_perm(mat)
        except (TypeError, ValueError):
            self._frame_perm = None

    def apply_frame(self, mat):
        mat = tuple(tuple(int(v) for v in row) for row in mat)
        self.settings["ble_frame_rotation"] = [list(row) for row in mat]
        self._frame_perm = cube_mod.frame_perm(mat)
        if self.ble_state is not None:
            facelets = cube_mod.rotate_frame_facelets(
                self.ble_state.facelets(), self._frame_perm)
            self.live_cube.set_state(facelets)
            self.hub.set_cube(facelets, self._cube_state_trusted)
        self._sync_windows()
        self.save()

    def reset_frame(self):
        self.settings.pop("ble_frame_rotation", None)
        self._frame_perm = None
        if self.ble_state is not None:
            facelets = self.ble_state.facelets()
            self.live_cube.set_state(facelets)
            self.hub.set_cube(facelets, self._cube_state_trusted)
        self._sync_windows()
        self.save()

    # ==================================================================
    def save(self):
        try:
            self.store.save()
        except (IOError, OSError) as e:
            self.toast.show_message("Save error: %s" % e, 5000)

    def resizeEvent(self, e):
        QMainWindow.resizeEvent(self, e)
        # Preserve a generous timer column on compact displays, while giving
        # the solve list and chart more room on wide monitors.
        width = e.size().width()
        self._update_puzzle_caption()
        if not self.brand_pixmap.isNull():
            target = 130 if width < 1100 else 155 if width < 1200 else 210
            scaled = self.brand_pixmap.scaled(target * 2, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2.0)
            self.brand_logo.setPixmap(scaled)
            self.brand_logo.setFixedWidth(target)
        self.left_panel.setFixedWidth(max(260, min(320, int(width * 0.235))))
        self.right_panel.setFixedWidth(max(290, min(360, int(width * 0.27))))
        if self.toast.isVisible():
            self.toast.move(int((self.timer_area.width() - self.toast.width()) / 2), 14)

    def _update_puzzle_caption(self):
        if self.session is None or not hasattr(self, "puzzle_bar"):
            return
        puzzle = self.session.puzzle
        names = scr.PUZZLE_LABEL if self.width() < 1100 else scr.PUZZLE_NAME
        self.puzzle_bar.setText("%s  ▾" % names.get(puzzle, puzzle))
        self.puzzle_bar.setToolTip(scr.PUZZLE_NAME.get(puzzle, puzzle))

    def closeEvent(self, e):
        self.updater.close()
        self.update_poll.stop()
        for w in list(self.extra_windows):
            w.close()
        if self.ble is not None:
            self.ble.stop()
            self.ble.wait(2000)
        self.settings["geometry"] = self.saveGeometry().toBase64().data().decode("ascii")
        self.save()
        QMainWindow.closeEvent(self, e)
