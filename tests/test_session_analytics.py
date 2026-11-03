import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from unittest.mock import patch

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from enigma_timer.analytics_widgets import TimeChart, TimeHistogram
from enigma_timer.dialogs import SolveDialog
from enigma_timer.stats import Solve, PLUS2, DNF, INF
from enigma_timer.storage import Store
from enigma_timer.window import MainWindow

_APP = QApplication.instance() or QApplication([])


class AnalyticsTests(unittest.TestCase):
    def test_buckets_are_bounded_and_count_penalized_times_and_exclude_dnf(self):
        hist = TimeHistogram()
        values = [1160, 2880, 35060, 40010, 62000, INF, None]
        hist.set_data(values)
        rows = hist.buckets()
        self.assertLessEqual(len(rows), 8)
        self.assertEqual(sum(c for _, _, c in rows), 5)
        for value in hist._values:
            self.assertEqual(sum(start <= value < end for start, end, _ in rows), 1)
        self.assertEqual(hist._dnfs, 1)
        hist.set_data([10000]*7)
        self.assertEqual(sum(c for _, _, c in hist.buckets()), 7)
        for width, height in ((250,170),(290,350),(360,600)):
            hist.resize(width,height)
            self.assertFalse(hist.grab().isNull())

    def test_chart_uses_ao12_bounds_and_click_returns_original_solve_index(self):
        chart=TimeChart()
        chart.resize(290,300)
        chart.set_data([10000]*405, [None]*405, [60000]*405)
        self.assertIn(60000,chart._finite())
        chart.show()
        _APP.processEvents()
        self.assertFalse(chart.grab().isNull())
        plot, n, X = chart._geom
        chosen=[]
        chart.solve_clicked.connect(chosen.append)
        QTest.mouseClick(chart,Qt.LeftButton,pos=QPoint(round(X(0)),round(plot.center().y())))
        self.assertEqual(chosen,[5])
        QTest.mouseClick(chart,Qt.LeftButton,pos=QPoint(2,2))
        self.assertEqual(chosen,[5])
        chart.set_data([INF],[None],[None])
        chart.grab()
        self.assertIsNone(chart._geom)
        chart.close()

    def test_single_click_maps_newest_row_to_details_and_keeps_average_action(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(os.path.join(folder,"data.json"))
            store.settings["welcome_seen"]=True
            main=MainWindow(store)
            try:
                main.session.solves=[Solve(10000+i*1000,scramble="R U R'") for i in range(6)]
                main.refresh()
                with patch.object(main,"open_solve") as detail, patch.object(main,"show_average") as avg:
                    main._on_time_clicked(0,1)
                    detail.assert_called_once_with(5)
                    main._on_time_clicked(0,2)
                    avg.assert_called_once_with(5,5)
                solve=main.session.solves[-1]
                solve.penalty=PLUS2
                dialog=SolveDialog(solve,6,2,main)
                self.assertIn("17.00",dialog.lb_time.text())
                self.assertIn("15.00",dialog.lb_breakdown.text())
                self.assertEqual(dialog.scramble_label.text(),"R U R'")
                self.assertIsNotNone(dialog.preview._grid)
                self.assertFalse(dialog.grab().isNull())
                dialog.ed_comment.setText("test note")
                dialog.accept()
                main.save()
                restored=Store(store.path).sessions[0].solves[-1]
                self.assertEqual((restored.scramble,restored.comment,restored.penalty),
                                 ("R U R'","test note",PLUS2))
            finally:
                main.close()
