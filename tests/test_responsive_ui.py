"""UI regressions that could hide controls or make details inaccessible."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QDialog, QScrollArea
from enigma_timer import theme, i18n
from enigma_timer.layouts import WrapLayout
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow
from enigma_timer.training import CaseDetail
from enigma_timer.dialogs import SolveDialog, WelcomeDialog
from enigma_timer.stats import Solve
from enigma_timer.windows import LiveCubeWindow

_APP=QApplication.instance() or QApplication([])


class ResponsiveUiTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=Store(os.path.join(self.folder.name,"data.json"))
        self.store.settings.update(welcome_seen=True,reduce_motion=True)
        self.main=MainWindow(self.store)

    def tearDown(self):
        self.main.close()
        _APP.processEvents()
        i18n.set_language("en")
        self.folder.cleanup()

    def test_controls_wrap_without_overlapping_or_losing_height(self):
        parent=QWidget()
        layout=WrapLayout(parent)
        buttons=[]
        for i in range(3):
            b=QPushButton(str(i))
            b.setFixedSize(140,36)
            layout.addWidget(b)
            buttons.append(b)
        parent.show()
        for width,expected in ((480,1),(310,2),(220,3)):
            height=layout.heightForWidth(width)
            parent.resize(width,height)
            _APP.processEvents()
            layout.setGeometry(QRect(0,0,width,height))
            self.assertEqual(len({b.y() for b in buttons}),expected)
            for i,b in enumerate(buttons):
                self.assertTrue(parent.rect().contains(b.geometry()))
                self.assertGreaterEqual(b.height(),b.sizeHint().height())
                for other in buttons[i+1:]:
                    self.assertFalse(b.geometry().intersects(other.geometry()))
        parent.close()

    def test_compact_training_case_opens_complete_inspector(self):
        self.main.resize(1100,710)
        self.main.set_page(1)
        tw=self.main.training
        tw.select_level("oll")
        tw.content.setCurrentIndex(1)
        tw._update_detail_visibility()
        self.assertTrue(tw.detail.isHidden())
        item=tw.grid.item(26)
        viewed=[]
        def inspect(dialog):
            detail=dialog.findChild(CaseDetail)
            viewed.append(detail.case.id)
            self.assertEqual(detail.alg.text(),detail.case.alg)
            self.assertTrue(detail.findChildren(QScrollArea))
            return QDialog.Accepted
        with patch.object(QDialog,"exec_",inspect):
            tw.grid.itemClicked.emit(item)
        self.assertEqual(len(viewed),1)

    def test_long_solve_scrolls_while_footer_remains_accessible(self):
        solve=Solve(12000,scramble="R U R' U' "*100)
        dialog=SolveDialog(solve,1,2,self.main)
        dialog.resize(480,450)
        dialog.show()
        _APP.processEvents()
        scroll=dialog.findChild(QScrollArea)
        self.assertGreater(scroll.verticalScrollBar().maximum(),0)
        for button in dialog.findChildren(QPushButton):
            if button.text() in (i18n.tr("close"),i18n.tr("copy"),i18n.tr("delete")):
                self.assertTrue(button.isVisibleTo(dialog))
                self.assertTrue(dialog.rect().contains(button.mapTo(dialog,button.rect().bottomRight())))
        dialog.close()

    def test_secondary_window_and_welcome_fit_small_sizes_in_both_languages(self):
        for language in ("en","ru"):
            i18n.set_language(language)
            window=LiveCubeWindow(self.main)
            window.resize(440,550)
            window.show()
            _APP.processEvents()
            for b in window.findChildren(QPushButton):
                if b.isVisibleTo(window):
                    self.assertTrue(window.rect().contains(b.mapTo(window,b.rect().bottomRight())))
            self.assertFalse(window.view.grab().isNull())
            window.close()
            welcome=WelcomeDialog("",self.main)
            welcome.resize(620,480)
            welcome.show()
            _APP.processEvents()
            self.assertEqual(len(welcome.findChildren(QScrollArea)),3)
            self.assertTrue(welcome.next.isVisibleTo(welcome))
            welcome.close()

    def test_russian_reference_cards_reflow_when_switching_puzzles(self):
        from enigma_timer.notation_panel import CubeNotationPanel
        i18n.set_language("ru")
        panel=CubeNotationPanel(lambda *_: None)
        panel.resize(800,650)
        panel.show()
        for puzzle in ("333","skewb","minx","sq1"):
            panel.set_puzzle(puzzle)
            _APP.processEvents()
            for card in panel.cards.values():
                self.assertGreaterEqual(card.width()+2,card.minimumSizeHint().width())
        panel.close()
