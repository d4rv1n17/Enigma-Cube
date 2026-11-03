import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow
from enigma_timer.stats import Solve, PLUS2, DNF

_APP=QApplication.instance() or QApplication([])


class StatsSidebarTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=Store(os.path.join(self.folder.name,"data.json"))
        self.store.settings["welcome_seen"]=True
        self.main=MainWindow(self.store)

    def tearDown(self):
        self.main.close()
        self.folder.cleanup()

    def solves(self, count):
        self.main.session.solves=[Solve(10000+i*1000,scramble="R U") for i in range(count)]
        self.main.refresh()

    def test_only_computable_averages_and_history_columns_are_shown(self):
        self.solves(7)
        table=self.main.stats_table
        self.assertTrue(table.isRowHidden(0))
        self.assertFalse(table.isRowHidden(1))
        self.assertFalse(table.isRowHidden(2))
        self.assertTrue(table.isRowHidden(3))
        self.assertTrue(self.main.times_table.isColumnHidden(3))
        self.assertFalse(self.main.times_table.isColumnHidden(2))
        self.main.all_averages.setChecked(True)
        self.assertFalse(table.isRowHidden(5))
        self.assertTrue(table.isRowHidden(0))
        self.main.all_averages.setChecked(False)
        self.assertTrue(table.isRowHidden(5))
        self.solves(12)
        self.assertFalse(table.isRowHidden(3))
        self.assertFalse(self.main.times_table.isColumnHidden(3))

    def test_metric_cards_show_penalties_and_open_correct_solve(self):
        self.solves(4)
        self.main.session.solves[-1].penalty=PLUS2
        self.main.refresh()
        self.assertEqual(self.main.single_metrics[0].text(),"15.00+")
        self.assertEqual(self.main.single_metrics[1].text(),"10.00")
        with patch.object(self.main,"open_solve") as detail:
            self.main.single_metrics[0].click()
            detail.assert_called_with(3)
            self.main.single_metrics[1].click()
            detail.assert_called_with(0)
        self.main.session.solves[-1].penalty=DNF
        self.main.refresh()
        self.assertEqual(self.main.single_metrics[0].text(),"DNF")

    def test_empty_session_has_no_meaningless_stat_rows(self):
        self.solves(0)
        self.assertFalse(self.main.single_metrics[0].isEnabled())
        self.assertTrue(self.main.stats_table.isHidden())
        self.assertEqual(self.main.history_count.text(),"0")
        self.solves(1)
        self.assertTrue(self.main.times_table.isColumnHidden(2))
        self.assertTrue(self.main.times_table.isColumnHidden(3))

    def test_unavailable_history_average_opens_solve_instead_of_dead_cell(self):
        self.solves(7)
        with patch.object(self.main,"open_solve") as detail:
            self.main._on_time_clicked(6,2)
        detail.assert_called_once_with(0)
