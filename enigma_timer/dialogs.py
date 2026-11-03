"""Dialogs: settings, solve details, average details."""

import time

from PyQt5.QtCore import Qt,QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox,
                             QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSlider,
                             QVBoxLayout, QWidget, QTabWidget)

from . import VERSION, theme
from . import cube
from .i18n import tr
from .stats import OK, PLUS2, DNF, fmt_solve, fmt_ms
from .widgets import FadeStackedWidget


class WelcomeDialog(QDialog):
    """Three-step, first-run tour of the timer, learning, and Giiker support."""

    _STEPS = (
        ("welcome_intro_kicker", "welcome_intro_title", "welcome_intro_body", (
            ("⏱", "welcome_intro_timer", "welcome_intro_timer_body"),
            ("▤", "welcome_intro_stats", "welcome_intro_stats_body"),
            ("✦", "welcome_intro_learn", "welcome_intro_learn_body"),
        )),
        ("welcome_timer_kicker", "welcome_timer_title", "welcome_timer_body", (
            ("↻", "welcome_scramble_title", "welcome_scramble_body"),
            ("␣", "welcome_space_title", "welcome_space_body"),
            ("＋", "welcome_stats_title", "welcome_stats_body"),
        )),
        ("welcome_cube_kicker", "welcome_cube_title", "welcome_cube_body", (
            ("◆", "welcome_training_title", "welcome_training_body"),
            ("◎", "welcome_giiker_title", "welcome_giiker_body"),
            ("⚙", "welcome_modes_title", "welcome_modes_body"),
        )),
    )

    def __init__(self, logo_path, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(tr("welcome_window_title"))
        self.setMinimumSize(620, 480)
        self.resize(760, 620)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 22)
        root.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setFixedHeight(48)
        logo.setScaledContents(False)
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToHeight(44, Qt.SmoothTransformation))
        header.addWidget(logo)
        header.addStretch(1)
        skip = QPushButton(tr("welcome_skip"))
        skip.setObjectName("welcomeSkip")
        skip.clicked.connect(self.accept)
        header.addWidget(skip)
        root.addLayout(header)

        self.pages = FadeStackedWidget()
        for step in self._STEPS:
            self.pages.addWidget(self._make_page(*step))
        root.addWidget(self.pages, 1)

        footer = QHBoxLayout()
        self.back = QPushButton(tr("back"))
        self.back.setObjectName("seg")
        self.back.clicked.connect(self._previous)
        footer.addWidget(self.back)
        footer.addStretch(1)
        self.dots = []
        for _ in self._STEPS:
            dot = QFrame()
            dot.setObjectName("welcomeDot")
            dot.setFixedSize(22, 4)
            self.dots.append(dot)
            footer.addWidget(dot)
        footer.addStretch(1)
        self.next = QPushButton()
        self.next.setObjectName("primary")
        self.next.setDefault(True)
        self.next.clicked.connect(self._advance)
        footer.addWidget(self.next)
        root.addLayout(footer)
        self._update_controls()

    @staticmethod
    def _make_page(kicker_key, title_key, body_key, tips):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 4, 0, 4)
        card = QFrame()
        card.setObjectName("panel")
        box = QVBoxLayout(card)
        box.setContentsMargins(28, 24, 28, 24)
        box.setSpacing(12)

        kicker = QLabel(tr(kicker_key).upper())
        kicker.setObjectName("sectionTitle")
        box.addWidget(kicker)
        title = QLabel(tr(title_key))
        title.setWordWrap(True)
        title.setObjectName("heroTitle")
        box.addWidget(title)
        body = QLabel(tr(body_key))
        body.setWordWrap(True)
        body.setObjectName("muted")
        body.setObjectName("bodyText")
        box.addWidget(body)
        box.addSpacing(4)

        for symbol, title_key, body_key in tips:
            row = QFrame()
            row.setObjectName("welcomeTip")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 9, 14, 9)
            row_layout.setSpacing(14)
            badge = QLabel(symbol)
            badge.setObjectName("welcomeIcon")
            badge.setFixedSize(38, 38)
            badge.setAlignment(Qt.AlignCenter)
            row_layout.addWidget(badge)
            text = QVBoxLayout()
            text.setSpacing(2)
            heading = QLabel(tr(title_key))
            heading.setObjectName("labelStrong")
            heading.setWordWrap(True)
            description = QLabel(tr(body_key))
            description.setWordWrap(True)
            description.setObjectName("muted")
            description.setObjectName("caption")
            text.addWidget(heading)
            text.addWidget(description)
            row_layout.addLayout(text, 1)
            box.addWidget(row)
        box.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(card)
        outer.addWidget(scroll, 1)
        return page

    def _update_controls(self):
        index = self.pages.currentIndex()
        self.back.setVisible(index > 0)
        self.next.setText(tr("welcome_finish") if index == len(self._STEPS) - 1
                          else tr("welcome_next"))
        for i, dot in enumerate(self.dots):
            color = theme.ACCENT if i == index else theme.BORDER
            dot.setStyleSheet("background: %s; border-radius: 2px;" % color)

    def _advance(self):
        if self.pages.currentIndex() == len(self._STEPS) - 1:
            self.accept()
            return
        self.pages.setCurrentIndex(self.pages.currentIndex() + 1)
        self._update_controls()

    def _previous(self):
        if self.pages.currentIndex() > 0:
            self.pages.setCurrentIndex(self.pages.currentIndex() - 1)
            self._update_controls()


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(tr("settings"))
        self.setMinimumSize(620, 480)
        self.settings = dict(settings)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        heading = QLabel(tr("settings"))
        heading.setObjectName("pageHeading")
        lay.addWidget(heading)
        self.tabs = QTabWidget()
        sections = []
        for key in ("settings_timer_tab", "settings_cube_tab", "settings_interface_tab", "settings_keys_tab"):
            content = QWidget()
            box = QVBoxLayout(content)
            box.setContentsMargins(4, 16, 12, 12)
            box.setSpacing(16)
            sections.append(box)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(content)
            self.tabs.addTab(scroll, tr(key))

        def section(title_key):
            card = QFrame()
            card.setObjectName("settingGroup")
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 18, 20, 18)
            box.setSpacing(12)
            title = QLabel(tr(title_key).upper())
            title.setObjectName("sectionTitle")
            box.addWidget(title)
            index = (0 if title_key == "s_timer_section" else 1 if title_key == "ble_cube"
                     else 3 if title_key == "shortcuts" else 2)
            sections[index].addWidget(card)
            return box

        timer_box = section("s_timer_section")

        self.cb_insp = QCheckBox(tr("s_inspection"))
        self.cb_insp.setChecked(bool(settings.get("inspection")))
        self.cb_alerts = QCheckBox(tr("s_alerts"))
        self.cb_alerts.setChecked(bool(settings.get("inspection_alerts")))
        self.cb_focus = QCheckBox(tr("s_focus"))
        self.cb_focus.setChecked(bool(settings.get("focus_mode")))
        self.cb_preview = QCheckBox(tr("s_preview"))
        self.cb_preview.setChecked(bool(settings.get("show_preview")))
        self.cb_chart = QCheckBox(tr("s_chart"))
        self.cb_chart.setChecked(bool(settings.get("show_chart")))
        for w in (self.cb_insp, self.cb_alerts, self.cb_focus, self.cb_preview, self.cb_chart):
            timer_box.addWidget(w)
        self.cb_insp.toggled.connect(self.cb_alerts.setEnabled)
        self.cb_alerts.setEnabled(self.cb_insp.isChecked())

        cube_box = section("ble_cube")
        self.cb_ble_start = QCheckBox(tr("ble_start"))
        self.cb_ble_start.setChecked(bool(settings.get("ble_timer", True)))
        ble_mode_help = QLabel(tr("ble_start_mode_help"))
        ble_mode_help.setObjectName("muted")
        ble_mode_help.setWordWrap(True)
        self.cb_ble_stop = QCheckBox(tr("ble_stop"))
        self.cb_ble_stop.setChecked(bool(settings.get("ble_stop_on_solve", True)))
        self.cb_ble_show = QCheckBox(tr("ble_show_state"))
        self.cb_ble_show.setChecked(bool(settings.get("ble_show_cube", True)))
        for w in (self.cb_ble_start, ble_mode_help,
                  self.cb_ble_stop, self.cb_ble_show):
            cube_box.addWidget(w)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft)
        self.cmb_goal = QComboBox()
        for count in (5, 10, 20, 30):
            self.cmb_goal.addItem(str(count), count)
        self._select(self.cmb_goal, settings.get("daily_review_goal", 10))
        form.addRow(tr("daily_goal_setting"), self.cmb_goal)

        hold_row = QHBoxLayout()
        self.sl_hold = QSlider(Qt.Horizontal)
        self.sl_hold.setRange(0, 10)  # x100 ms
        self.sl_hold.setValue(int(settings.get("hold_ms", 300)) // 100)
        self.lb_hold = QLabel()
        self.lb_hold.setMinimumWidth(56)
        self.sl_hold.valueChanged.connect(self._hold_changed)
        self._hold_changed(self.sl_hold.value())
        hold_row.addWidget(self.sl_hold, 1)
        hold_row.addWidget(self.lb_hold)
        form.addRow(tr("s_hold"), hold_row)

        self.cmb_update = QComboBox()
        for key in ("full", "tenths", "seconds", "hidden"):
            self.cmb_update.addItem(tr("u_" + key), key)
        self._select(self.cmb_update, settings.get("update_mode", "full"))
        form.addRow(tr("s_update"), self.cmb_update)

        self.cmb_dec = QComboBox()
        for d in (2, 3):
            self.cmb_dec.addItem(str(d), d)
        self._select(self.cmb_dec, int(settings.get("decimals", 2)))
        form.addRow(tr("s_decimals"), self.cmb_dec)

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem("English", "en")
        self.cmb_lang.addItem("Русский", "ru")
        from .i18n import configured_language
        self._select(self.cmb_lang, configured_language(settings))
        form.addRow(tr("s_language"), self.cmb_lang)
        display_box = section("s_display_section")
        display_box.addLayout(form)
        self.cb_reduce_motion = QCheckBox(tr("reduce_motion"))
        self.cb_reduce_motion.setChecked(bool(settings.get("reduce_motion", False)))
        display_box.addWidget(self.cb_reduce_motion)
        self.cb_startup_intro=QCheckBox(tr("startup_intro_setting"))
        self.cb_startup_intro.setChecked(bool(settings.get("startup_intro",True)))
        display_box.addWidget(self.cb_startup_intro)
        intro_hint=QLabel(tr("startup_intro_hint"))
        intro_hint.setObjectName("caption")
        intro_hint.setWordWrap(True)
        display_box.addWidget(intro_hint)

        self.updater=getattr(parent,"updater",None)
        update_box=section("updates_section")
        version=QLabel(tr("update_version")%VERSION)
        version.setObjectName("labelStrong")
        update_box.addWidget(version)
        self.cb_auto_update=QCheckBox(tr("update_automatic"))
        self.cb_auto_update.setChecked(bool(settings.get("auto_update",True)))
        self.cb_auto_update.setToolTip(tr("update_automatic_hint"))
        update_box.addWidget(self.cb_auto_update)
        self.update_status=QLabel()
        self.update_status.setObjectName("muted")
        self.update_status.setWordWrap(True)
        update_box.addWidget(self.update_status)
        update_row=QHBoxLayout()
        self.check_update=QPushButton(tr("update_check"))
        self.check_update.setObjectName("seg")
        self.check_update.clicked.connect(lambda:self.updater.check(manual=True) if self.updater else None)
        update_row.addWidget(self.check_update)
        self.apply_update=QPushButton()
        self.apply_update.setObjectName("primary")
        self.apply_update.clicked.connect(self._update_action)
        update_row.addWidget(self.apply_update)
        update_row.addStretch()
        update_box.addLayout(update_row)
        if self.updater:
            self.updater.changed.connect(self._refresh_updates)
            self.finished.connect(self._disconnect_updates)
        self._refresh_updates()

        shortcut_box = section("shortcuts")
        sc = QLabel(tr("shortcuts_text"))
        sc.setObjectName("muted")
        sc.setWordWrap(True)
        shortcut_box.addWidget(sc)

        for box in sections:
            box.addStretch(1)
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        reset = QPushButton(tr("reset_settings"))
        reset.setObjectName("seg")
        reset.clicked.connect(self._reset_defaults)
        btns.addWidget(reset)
        btns.addStretch(1)
        cancel = QPushButton(tr("cancel"))
        cancel.setObjectName("seg")
        ok = QPushButton(tr("save_settings"))
        ok.setObjectName("primary")
        ok.setDefault(True)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.resize(740, 650)

    def _reset_defaults(self):
        from .storage import DEFAULT_SETTINGS
        for attr, key in (("cb_insp", "inspection"), ("cb_alerts", "inspection_alerts"),
                          ("cb_focus", "focus_mode"), ("cb_preview", "show_preview"),
                          ("cb_chart", "show_chart"), ("cb_ble_start", "ble_timer"),
                          ("cb_ble_stop", "ble_stop_on_solve"), ("cb_ble_show", "ble_show_cube"),
                          ("cb_reduce_motion", "reduce_motion"),
                          ("cb_startup_intro", "startup_intro"),
                          ("cb_auto_update", "auto_update")):
            getattr(self, attr).setChecked(bool(DEFAULT_SETTINGS.get(key, False)))
        self.sl_hold.setValue(DEFAULT_SETTINGS["hold_ms"]//100)
        for combo, value in ((self.cmb_goal, 10), (self.cmb_update, DEFAULT_SETTINGS["update_mode"]),
                             (self.cmb_dec, DEFAULT_SETTINGS["decimals"]), (self.cmb_lang, "en")):
            self._select(combo, value)

    @staticmethod
    def _select(combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _refresh_updates(self):
        service=self.updater
        self.update_status.setText(service.description() if service else tr("update_idle"))
        self.check_update.setEnabled(bool(service) and not service.busy and service.state!="ready")
        actionable=bool(service) and service.state in ("available","ready")
        self.apply_update.setVisible(actionable)
        self.apply_update.setEnabled(actionable and service.can_install and not service.busy)
        self.apply_update.setText(tr("update_restart" if service and service.state=="ready" else "update_download"))
        self.apply_update.setToolTip("" if service and service.can_install else tr("update_desktop_only"))

    def _disconnect_updates(self,*_args):
        if self.updater:
            try:
                self.updater.changed.disconnect(self._refresh_updates)
            except (TypeError,RuntimeError):
                pass

    def _update_action(self):
        if not self.updater:
            return
        if self.updater.state=="ready":
            owner=self.parent()
            if owner and hasattr(owner,"install_update"):
                self._accept()
                QTimer.singleShot(0,owner.install_update)
        else:
            self.updater.start_download()

    def _hold_changed(self, v):
        self.lb_hold.setText("%.1f s" % (v / 10.0))

    def _accept(self):
        s = self.settings
        s["inspection"] = self.cb_insp.isChecked()
        s["inspection_alerts"] = self.cb_alerts.isChecked()
        s["focus_mode"] = self.cb_focus.isChecked()
        s["show_preview"] = self.cb_preview.isChecked()
        s["show_chart"] = self.cb_chart.isChecked()
        s["ble_timer"] = self.cb_ble_start.isChecked()
        s["daily_review_goal"] = self.cmb_goal.currentData()
        s["ble_stop_on_solve"] = self.cb_ble_stop.isChecked()
        s["ble_show_cube"] = self.cb_ble_show.isChecked()
        s["hold_ms"] = self.sl_hold.value() * 100
        s["update_mode"] = self.cmb_update.currentData()
        s["decimals"] = self.cmb_dec.currentData()
        s["language"] = self.cmb_lang.currentData() or "en"
        s["reduce_motion"] = self.cb_reduce_motion.isChecked()
        s["startup_intro"] = self.cb_startup_intro.isChecked()
        s["auto_update"] = self.cb_auto_update.isChecked()
        self.accept()


class SolveDialog(QDialog):
    """Shows one solve; lets the user change penalty, comment or delete it."""

    def __init__(self, solve, number, decimals, parent=None):
        QDialog.__init__(self, parent)
        self.solve = solve
        self.deleted = False
        self.decimals = decimals
        self.setWindowTitle(tr("solve_n") % number)
        self.setMinimumWidth(440)
        self.resize(600, 590)
        root = QVBoxLayout(self)
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        title = QLabel(tr("solve_n") % number)
        title.setObjectName("dialogTitle")
        lay.addWidget(title)
        session = getattr(parent, "session", None)
        if session is not None:
            session_label = QLabel(session.name)
            session_label.setObjectName("muted")
            session_label.setTextFormat(Qt.PlainText)
            lay.addWidget(session_label)

        self.lb_time = QLabel()
        self.lb_time.setObjectName("metricLarge")
        lay.addWidget(self.lb_time)
        date = QLabel(time.strftime("%Y-%m-%d  %H:%M:%S", time.localtime(solve.date)))
        date.setObjectName("muted")
        lay.addWidget(date)
        self.lb_breakdown = QLabel()
        self.lb_breakdown.setObjectName("muted")
        lay.addWidget(self.lb_breakdown)
        if solve.telemetry:
            replay = QPushButton(tr("solve_replay"))
            replay.setObjectName("primary")
            replay.clicked.connect(self.show_replay)
            lay.addWidget(replay)

        pen_row = QHBoxLayout()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        # button ids must be >= 0 (Qt treats -1 as "assign automatically")
        self._pen_values = [OK, PLUS2, DNF]
        for idx, (label, val) in enumerate(((tr("ok"), OK), (tr("plus2"), PLUS2),
                                            (tr("dnf"), DNF))):
            b = QPushButton(label)
            b.setObjectName("pen")
            b.setCheckable(True)
            b.setChecked(solve.penalty == val)
            self.group.addButton(b, idx)
            pen_row.addWidget(b)
        pen_row.addStretch(1)
        self.group.buttonClicked[int].connect(self._set_penalty)
        lay.addLayout(pen_row)

        t = QLabel(tr("scramble").upper())
        t.setObjectName("sectionTitle")
        lay.addWidget(t)
        scr = QLabel(solve.scramble or "-")
        scr.setWordWrap(True)
        scr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scr.setObjectName("bodyText")
        lay.addWidget(scr)
        self.scramble_label = scr
        self.preview = None
        if session is not None and solve.scramble:
            from .widgets import ScramblePreview
            self.preview = ScramblePreview()
            self.preview.set_scramble(session.puzzle, solve.scramble)
            self.preview.setMinimumHeight(140)
            self.preview.setMaximumHeight(180)
            lay.addWidget(self.preview, 1)

        t2 = QLabel(tr("comment").upper())
        t2.setObjectName("sectionTitle")
        lay.addWidget(t2)
        self.ed_comment = QLineEdit(solve.comment)
        lay.addWidget(self.ed_comment)

        btns = QHBoxLayout()
        delete = QPushButton(tr("delete"))
        delete.setStyleSheet("color: %s;" % theme.DNF_RED)
        delete.clicked.connect(self._delete)
        copy = QPushButton(tr("copy"))
        copy.clicked.connect(self._copy)
        close = QPushButton(tr("close"))
        close.setObjectName("primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        btns.addWidget(delete)
        btns.addStretch(1)
        btns.addWidget(copy)
        btns.addWidget(close)
        root.addLayout(btns)
        self._refresh()

    def _refresh(self):
        self.lb_time.setText(fmt_solve(self.solve, self.decimals))
        penalty = {OK: tr("ok"), PLUS2: "+2", DNF: "DNF"}[self.solve.penalty]
        self.lb_breakdown.setText("%s: %s   ·   %s: %s" % (
            tr("solve_raw_time"), fmt_ms(self.solve.ms, self.decimals),
            tr("solve_penalty_label"), penalty))

    def show_replay(self):
        from .replay import ReplayDialog
        ReplayDialog(self.solve, self).exec_()

    def _set_penalty(self, idx):
        self.solve.penalty = self._pen_values[idx]
        self._refresh()

    def _copy(self):
        QApplication.clipboard().setText("%s   %s" % (fmt_solve(self.solve, self.decimals),
                                                      self.solve.scramble))

    def _delete(self):
        self.deleted = True
        self.accept()

    def accept(self):
        self.solve.comment = self.ed_comment.text().strip()
        QDialog.accept(self)


class TextDialog(QDialog):
    """Read-only text (average breakdown) with a copy button."""

    def __init__(self, title, text, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)
        self.resize(620, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        heading.setWordWrap(True)
        lay.addWidget(heading)
        ed = QPlainTextEdit(text)
        ed.setReadOnly(True)
        mono = theme.mono_font()
        if mono:
            ed.setStyleSheet('font-family: "%s"; font-size: 14px;' % mono)
        lay.addWidget(ed)
        row = QHBoxLayout()
        row.addStretch(1)
        copy = QPushButton(tr("copy"))
        copy.clicked.connect(lambda: QApplication.clipboard().setText(text))
        close = QPushButton(tr("close"))
        close.setDefault(True)
        close.clicked.connect(self.accept)
        row.addWidget(copy)
        row.addWidget(close)
        lay.addLayout(row)


class AboutDialog(QDialog):
    def __init__(self, logo_path, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(tr("about"))
        self.setMinimumSize(420, 470)
        self.resize(480, 550)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(18)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        pm = QPixmap(logo_path)
        if not pm.isNull():
            logo.setPixmap(pm.scaled(300, 230, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setStyleSheet("background: %s; border-radius: 16px;" % theme.BG)
        lay.addWidget(logo)
        ver = QLabel("Enigma Cube")
        ver.setAlignment(Qt.AlignCenter)
        ver.setObjectName("pageHeading")
        lay.addWidget(ver)
        version = QLabel(tr("about_version") % VERSION)
        version.setAlignment(Qt.AlignCenter)
        version.setObjectName("muted")
        lay.addWidget(version)
        txt = QLabel(tr("about_text"))
        txt.setObjectName("muted")
        txt.setWordWrap(True)
        txt.setAlignment(Qt.AlignCenter)
        lay.addWidget(txt)
        lay.addStretch(1)
        close = QPushButton(tr("close"))
        close.setDefault(True)
        close.setObjectName("primary")
        close.setMinimumWidth(110)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)


class CubeFrameDialog(QDialog):
    """Two-turn physical alignment of a smart cube's internal frame.

    The cube's firmware has its own reference frame; when it disagrees
    with how the solver holds the cube, live views show turns on the
    "wrong" side.  Two known physical turns (top face, then front face)
    uniquely pick one of the 24 whole-cube rotations, which the main
    window then applies to every live facelet view.
    """

    def __init__(self, win):
        QDialog.__init__(self, win)
        self.win = win
        self.setWindowTitle(tr("frame_title"))
        self.setMinimumWidth(440)
        self.step = 0
        self.faces = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(14)
        heading = QLabel(tr("frame_title"))
        heading.setObjectName("dialogTitle")
        heading.setWordWrap(True)
        lay.addWidget(heading)
        self.progress = QProgressBar()
        self.progress.setRange(0, 3)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        lay.addWidget(self.progress)
        self.text = QLabel()
        self.text.setWordWrap(True)
        lay.addWidget(self.text)
        from .widgets import LiveCube3DWidget
        self.preview = LiveCube3DWidget()
        self.preview.setMinimumSize(180, 150)
        lay.addWidget(theme.visual_stage(self.preview), 1)
        self.resize(580, 560)
        row = QHBoxLayout()
        reset = QPushButton(tr("frame_reset"))
        reset.clicked.connect(self._reset)
        row.addWidget(reset)
        row.addStretch(1)
        self.btn = QPushButton()
        self.btn.setDefault(True)
        self.btn.clicked.connect(self._next)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self._enter()

    def _enter(self):
        self.progress.setValue(self.step)
        state = getattr(self.win, "ble_state", None)
        self.preview.set_state(state.facelets() if state is not None else None)
        label, btn, enabled = {
            0: (tr("frame_intro"), tr("frame_next"), True),
            1: (tr("frame_step1"), tr("frame_next"), True),
            2: (tr("frame_step2"), tr("frame_done"), True),
            3: (tr("frame_ok"), tr("close"), True),
        }.get(self.step, ("", tr("frame_done"), True))
        self.text.setText(label)
        self.btn.setText(btn)
        self.btn.setEnabled(enabled)
        self.btn.setFocus()

    def record_move(self, move):
        """Called by the main window for every cube turn while shown."""
        if self.step in (1, 2) and len(self.faces) < self.step:
            self.faces.append((self.step, move.notation[0]))

    def _next(self):
        if self.step == 0:
            self.step = 1
            self.faces = []
            self._enter()
            return
        if self.step in (1, 2):
            self.step += 1
            if self.step <= 2:
                self._enter()
            else:
                self._finish()
        else:
            QDialog.accept(self)

    def _reset(self):
        self.step = 0
        self.faces = []
        self.win.reset_frame()
        self._enter()

    def _finish(self):
        f1 = f2 = None
        for st, face in self.faces:
            if st == 1 and f1 is None:
                f1 = face
            if st == 2 and f2 is None:
                f2 = face
        if f1 is None or f2 is None:
            self.text.setText(tr("frame_no_move"))
            self.step = 1
            self.faces = []
            self._enter()
            return
        want = ((0, 1, 0), (0, 0, 1))   # user frame: U then F
        cands = [m for m in cube.whole_rotations()
                 if cube.rotation_face(m, f1) == "U"
                 and cube.rotation_face(m, f2) == "F"]
        if len(cands) == 1:
            self.win.apply_frame(cands[0])
            self.step = 3
            self._enter()
            return
        self.text.setText(tr("frame_failed"))
        self.step = 1
        self.faces = []
        self._enter()

    def closeEvent(self, e):
        self.win._frame_dialog = None
        QDialog.closeEvent(self, e)
