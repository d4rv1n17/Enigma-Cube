import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication,QWidget
from PyQt5.QtGui import QImage,QPainter,QColor
from enigma_timer.pages import ReferencePage
from enigma_timer.puzzle3d import Puzzle3DView,PolyPuzzle3DWidget,puzzle_image
from enigma_timer.puzzle_mesh import NON_CUBES,scene
from enigma_timer.move_explorer import MoveExplorerWindow
from enigma_timer.widgets import ScramblePreview
from enigma_timer.notation import notation_facelets
from enigma_timer import scramble,i18n,algs
from enigma_timer.megaminx import state

_APP = QApplication.instance() or QApplication([])


class AllPuzzleUiTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")
        _APP.setProperty("reduceMotion",False)

    def test_every_reference_card_and_mode_in_both_languages(self):
        for language in ("en","ru"):
            i18n.set_language(language)
            page=ReferencePage(None)
            page.resize(1060,590)
            page.show()
            panel=page.cube_notation
            for puzzle in ("222","333","444","555","666","777")+NON_CUBES:
                panel.set_puzzle(puzzle)
                for face in panel.cards:
                    panel.select_face(face)
                    for mode in range(3):
                        with self.subTest(language=language,puzzle=puzzle,face=face,mode=mode):
                            panel.set_mode(mode)
                            panel.toggle_move()
                            self.assertEqual(panel.cube.algorithm,panel.move)
                            self.assertTrue(panel.description.text())
                            self.assertNotIn("face_",panel.description.text())
                            self.assertFalse(panel.cards[face].icon().isNull())
                            panel.toggle_move()
                            self.assertEqual(panel.cube.algorithm,"")
            page.close()

    def test_every_scramble_gets_an_actual_non_cube_model(self):
        view=ScramblePreview()
        view.show()
        for puzzle in NON_CUBES:
            alg=scramble.generate(puzzle)
            view.set_scramble(puzzle,alg)
            self.assertIsNotNone(view._puzzle_view)
            self.assertFalse(view._puzzle_view.isHidden())
            self.assertEqual(view._puzzle_view._mesh,scene(puzzle,alg))
        view.set_scramble("333","R U")
        self.assertTrue(view._puzzle_view.isHidden())
        self.assertIsNotNone(view._grid)
        view.close()

    def test_poly_motion_finishes_and_hidden_timers_stop(self):
        for puzzle,move in (("pyram","R"),("skewb","U"),("sq1","/"),("minx","R++"),("clock","UR3+")):
            view=PolyPuzzle3DWidget()
            view.set_puzzle(puzzle)
            view.show()
            with patch("enigma_timer.puzzle3d.time.perf_counter",return_value=100.0) as clock:
                view.set_algorithm(move)
                self.assertIsNotNone(view._transition)
                self.assertTrue(view._turn_timer.isActive())
                clock.return_value=102.0
                view._advance_turn()
                self.assertIsNone(view._transition)
                self.assertEqual(view._mesh,scene(puzzle,move))
                view.hide()
                self.assertFalse(view._turn_timer.isActive())
            view.close()

    def test_explicit_cube_moves_include_slices_rotations_and_large_blocks(self):
        view=Puzzle3DView()
        view.resize(300,300)
        view.show()
        for puzzle,moves in (("333",("M","E'","S2","x","y'","z2","Rw")),("777",("4Rw","3R'","3Uw2","x"))):
            view.set_puzzle(puzzle)
            for move in moves:
                view.set_algorithm("")
                view.cube._turn=None
                view.cube._turn_queue.clear()
                view.set_algorithm(move)
                self.assertIsNotNone(view.cube._turn,move)
                self.assertEqual(view._facelets,notation_facelets(puzzle,move))
                self.assertEqual(view.cube._turn[-1][0],7 if move=="x" and puzzle=="777" else 3 if move.startswith(("x","y","z")) else int(move[0]) if move[0].isdigit() else 2)
        view.close()

    def test_all_megaminx_learning_cases_get_distinct_actual_images(self):
        pictures=[]
        for case in algs.CASES.values():
            if case.puzzle!="minx":
                continue
            self.assertEqual(state(case.setup()+" "+case.alg),state())
            image=puzzle_image("minx",case.setup(),96)
            self.assertFalse(image.isNull())
            pictures.append(image.constBits().asstring(image.sizeInBytes()))
        self.assertGreater(len(set(pictures)),25)

    def test_square_demo_parses_parenthesized_moves_with_spaces(self):
        main=QWidget()
        demo=MoveExplorerWindow(main,"sq1","(1, 0) / (0, -3)")
        self.assertEqual(demo.parts,["(1,0)","/","(0,-3)"])
        demo.advance()
        demo.advance()
        self.assertEqual(demo.view.poly._mesh,scene("sq1","(1,0) /"))
        demo.close()

    def test_all_nine_clock_hubs_stay_visible_on_both_faces(self):
        view=PolyPuzzle3DWidget()
        view.set_puzzle("clock")
        view.resize(360,360)
        for alg in ("","y2"):
            view.set_algorithm(alg)
            view._arrival=None
            image=QImage(360,360,QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor('#121111'))
            painter=QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            view._paint_cube(painter)
            painter.end()
            rect=view.rect().adjusted(10,10,-10,-10)
            scale=min(rect.width(),rect.height())/3.55*1.15
            for row in range(3):
                for col in range(3):
                    vx,vy,_=view._rotate((col-1)*.82,(1-row)*.82,.162)
                    color=image.pixelColor(round(rect.center().x()+vx*scale),round(rect.center().y()-vy*scale))
                    with self.subTest(alg=alg,row=row,col=col):
                        self.assertGreater(color.red(),130)
                        self.assertGreater(color.green(),100)
                        self.assertLess(color.blue(),80)
        view.close()


if __name__=="__main__":
    unittest.main()
