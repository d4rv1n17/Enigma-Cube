import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtGui import QImage, QPainter, QColor
from enigma_timer.cube import Cube, FACE_COLORS
from enigma_timer.notation import notation_grid, notation_shapes, notation_facelets
from enigma_timer.widgets import LiveCube3DWidget
from enigma_timer.move_explorer import MoveExplorerWindow
from enigma_timer.training import LessonBrowser
from PyQt5.QtCore import QUrl
from enigma_timer.caseview import iso_grid, DISPLAY
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer.solver import apply_moves
from enigma_timer.pages import ReferencePage

_APP = QApplication.instance() or QApplication([])


class NotationTests(unittest.TestCase):
    def test_moves_match_scramble_simulator(self):
        for n in range(2, 8):
            for face in "URFDLB":
                for suffix in ("", "'", "2"):
                    move = face + suffix
                    with self.subTest(n=n, move=move):
                        self.assertEqual(notation_grid(str(n)*3, move), Cube(n).apply(move).facelets())
        for move in ("Rw", "M", "E'", "S2", "x", "y'", "z2", "R U F' L2 D B"):
            self.assertEqual(notation_grid("333", move), Cube(3).apply(move).facelets())

    def test_reference_uses_white_top_green_front_red_right(self):
        for n in (2, 3, 4):
            shapes = notation_shapes(str(n)*3)
            colors = [shape[2] for shape in shapes[1:]]
            self.assertEqual(colors, [FACE_COLORS[f] for _ in range(n*n) for f in "UFR"])
        # CFOP case pictures retain their own intentional yellow-top palette.
        grid = notation_grid("333")
        self.assertEqual(iso_grid(grid, 3)[1][2], DISPLAY["U"])
        self.assertNotEqual(DISPLAY["U"], FACE_COLORS["U"])

    def test_native_reference_controls_and_preview(self):
        page = ReferencePage(None)
        panel = page.cube_notation
        self.assertIs(page.content.currentWidget(), panel)
        self.assertEqual(panel.cube._facelets, SOLVED_FACELETS)
        panel.select_face("R")
        panel.set_mode(1)
        self.assertEqual(panel.move, "R'")
        panel.toggle_move()
        self.assertEqual(panel.cube._facelets, apply_moves(SOLVED_FACELETS, "R'"))
        panel.toggle_move()
        self.assertEqual(panel.cube._facelets, SOLVED_FACELETS)
        page.show_puzzle("pyram")
        self.assertIs(page.content.currentWidget(), panel)
        self.assertEqual(panel.cube.poly.puzzle,"pyram")
        page.show_puzzle("444")
        self.assertEqual(panel.puzzle, "444")
        self.assertTrue(panel.advanced.toPlainText())
        panel.size_select.setCurrentIndex(2)
        self.assertEqual(panel.puzzle,"666")
        self.assertEqual(panel.cube.cube_size,6)
        self.assertEqual(panel.cube._facelets,notation_facelets("666"))
        from enigma_timer.reference import advanced_html
        self.assertIn("demo:666:",advanced_html("666","ru"))
        page.close()

    def test_all_cube_previews_use_correct_geometry_and_state(self):
        page = ReferencePage(None)
        panel = page.cube_notation
        for puzzle, size in (("222",2),("333",3),("444",4)):
            page.show_puzzle(puzzle)
            self.assertEqual(panel.cube.cube_size,size)
            for face in "FRULDB":
                for mode, suffix in enumerate(("","'","2")):
                    panel.select_face(face)
                    panel.set_mode(mode)
                    panel.toggle_move()
                    self.assertEqual(panel.cube._facelets,notation_facelets(puzzle,face+suffix))
        page.close()

    def test_nxn_turn_animation_endpoints_match_static_rendering(self):
        for puzzle in ("222","444"):
            view = LiveCube3DWidget()
            view.set_cube_size(int(puzzle[0]))
            view.resize(240,240)
            def pixels():
                image = QImage(240,240,QImage.Format_ARGB32_Premultiplied)
                image.fill(QColor('#121111'))
                painter = QPainter(image)
                painter.setRenderHint(QPainter.Antialiasing)
                view._paint_cube(painter)
                painter.end()
                return image.constBits().asstring(image.sizeInBytes())
            moves = [f+s for f in "URFDLB" for s in ("","'","2")]
            if puzzle == "444":
                moves += ["Rw","Rw'","2R","2R2","3Rw","Uw","2F'"]
            with patch('enigma_timer.widgets.time.perf_counter',return_value=100.0) as clock:
                view.show()
                for move in moves:
                    view.set_state(notation_facelets(puzzle))
                    clock.return_value += 1
                    view._advance_turn()
                    before = pixels()
                    view.set_state(notation_facelets(puzzle,move))
                    with self.subTest(puzzle=puzzle,move=move):
                        self.assertIsNotNone(view._turn)
                        first = pixels()
                        self.assertLess(sum(a!=b for a,b in zip(before,first)),2500)
                        clock.return_value = view._turn[3]+view._turn[4]
                        last = pixels()
                        clock.return_value += .001
                        view._advance_turn()
                        final = pixels()
                        self.assertEqual(view._display_state,notation_facelets(puzzle,move))
                        self.assertLess(sum(a!=b for a,b in zip(last,final)),2500)
            view.close()

    def test_changing_geometry_clears_queued_turns(self):
        view = LiveCube3DWidget()
        view.show()
        view.set_state(SOLVED_FACELETS)
        view.set_state(apply_moves(SOLVED_FACELETS,"R"))
        view.set_state(apply_moves(SOLVED_FACELETS,"R U"))
        view.set_cube_size(4)
        self.assertIsNone(view._turn)
        self.assertFalse(view._turn_queue)
        self.assertIsNone(view._facelets)
        with self.assertRaises(ValueError):
            view.set_state(SOLVED_FACELETS)
        view.close()

    def test_detached_nxn_demo_pause_and_hidden_timer(self):
        main = QWidget()
        for puzzle in ("222","444"):
            demo = MoveExplorerWindow(main,puzzle,"R U F'")
            demo.show()
            self.assertEqual(demo.view.cube_size,int(puzzle[0]))
            demo.advance()
            self.assertEqual(demo.view._facelets,notation_facelets(puzzle,"R"))
            demo.play()
            self.assertTrue(demo.timer.isActive())
            demo.hide()
            self.assertFalse(demo.timer.isActive())
            demo.close()
        empty = MoveExplorerWindow(main,"222","")
        empty.play()
        self.assertFalse(empty.timer.isActive())
        self.assertFalse(empty.play_button.isEnabled())
        empty.close()

    def test_malformed_demo_links_are_ignored(self):
        browser = LessonBrowser()
        for value in ("demo:","demo:333","demo:unknown:R","https://example.com","demo:333:"+"R"*2049):
            browser.open_demo(QUrl(value))
        self.assertFalse(browser._demos)
        browser.close()

    def test_hover_respects_reduced_motion_and_stops_when_hidden(self):
        from enigma_timer.notation_panel import MoveCard
        card = MoveCard()
        card.show()
        _APP.setProperty("reduceMotion", True)
        try:
            card.animate_hover(1.0)
            self.assertEqual(card.hover,1.0)
            self.assertFalse(card.animation.state())
            _APP.setProperty("reduceMotion", False)
            card.animate_hover(0.0)
            card.hide()
            self.assertFalse(card.animation.state())
            self.assertEqual(card.hover,0.0)
        finally:
            _APP.setProperty("reduceMotion", False)
            card.close()


if __name__ == "__main__":
    unittest.main()
