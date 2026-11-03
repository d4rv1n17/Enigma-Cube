import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import math
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtGui import QImage, QPainter, QColor
from enigma_timer.widgets import LiveCube3DWidget, FadeStackedWidget, Toast, AnimatedProgressBar
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer.solver import apply_moves

_APP = QApplication.instance() or QApplication([])


class MotionTests(unittest.TestCase):
    def setUp(self):
        _APP.setProperty("reduceMotion", False)
        self.clock_patch = patch("enigma_timer.widgets.time.perf_counter", return_value=100.0)
        self.clock = self.clock_patch.start()
        self.view = LiveCube3DWidget()
        self.view.set_state(SOLVED_FACELETS)
        self.view.show()

    def tearDown(self):
        self.view.close()
        self.clock_patch.stop()
        _APP.setProperty("reduceMotion", False)

    def test_queued_turns_finish_at_the_latest_logical_state(self):
        target = apply_moves(SOLVED_FACELETS, "R U")
        self.view.set_state(apply_moves(SOLVED_FACELETS, "R"))
        self.view.set_state(target)
        self.assertEqual(self.view._facelets, target)
        self.assertEqual(len(self.view._turn_queue), 1)
        self.clock.return_value += 1
        self.view._advance_turn()
        self.assertEqual(self.view._display_state, target)
        self.assertIsNone(self.view._turn)
        self.assertFalse(self.view._turn_timer.isActive())

    def test_fast_input_does_not_build_an_unbounded_queue(self):
        state = SOLVED_FACELETS
        for move in "R U F D L B R U F D L B".split():
            state = apply_moves(state, move)
            self.view.set_state(state)
            self.assertLessEqual(len(self.view._turn_queue), 2)
        self.clock.return_value += 1
        self.view._advance_turn()
        self.assertEqual(self.view._display_state, state)
        self.assertEqual(self.view._facelets, state)

    def test_a_state_jump_does_not_invent_intermediate_moves(self):
        self.view.set_state(apply_moves(SOLVED_FACELETS, "R"))
        target = apply_moves(SOLVED_FACELETS, "L D F2")
        self.view.set_state(target)
        self.assertIsNone(self.view._turn)
        self.assertFalse(self.view._turn_queue)
        self.assertEqual(self.view._display_state, target)

    def test_reduced_motion_flushes_active_animation(self):
        target = apply_moves(SOLVED_FACELETS, "R U")
        self.view.set_state(apply_moves(SOLVED_FACELETS, "R"))
        self.view.set_state(target)
        _APP.setProperty("reduceMotion", True)
        self.view._advance_turn()
        self.assertEqual(self.view._display_state, target)
        self.assertIsNone(self.view._turn)
        self.assertFalse(self.view._turn_timer.isActive())

    def test_hidden_cube_stops_painting_and_keeps_latest_state(self):
        target = apply_moves(SOLVED_FACELETS, "R")
        self.view.set_state(target)
        self.view.hide()
        self.assertFalse(self.view._turn_timer.isActive())
        self.assertEqual(self.view._display_state, target)

    def test_camera_reset_takes_short_path_and_finishes_exactly(self):
        self.view._yaw = 7*math.tau + 1.3
        self.view._zoom = 1.7
        self.view.reset_view()
        start, target, _ = self.view._camera_reset
        self.assertLessEqual(abs(start[0]-target[0]), math.pi)
        self.clock.return_value += 1
        self.view._advance_turn()
        self.assertIsNone(self.view._camera_reset)
        self.assertAlmostEqual(self.view._yaw, math.radians(-24))
        self.assertAlmostEqual(self.view._zoom, 1)

    def test_white_center_logo_keeps_its_rotation_after_the_turn(self):
        self.view.set_state(apply_moves(SOLVED_FACELETS, "U"))
        self.assertEqual(self.view._logo_orientation, 1)
        self.clock.return_value += 1
        self.view._advance_turn()
        self.assertEqual(self.view._display_logo_orientation, 1)

    def test_camera_and_zoom_settle_without_idle_frame_timer(self):
        self.view._arrival = None
        self.view._velocity = (2.0,0.0,0.0)
        self.view._zoom_target = 1.7
        self.view._ensure_frames()
        initial_yaw = self.view._yaw
        for _ in range(100):
            self.clock.return_value += .016
            self.view._advance_turn()
        self.assertGreater(self.view._yaw, initial_yaw)
        self.assertLess(self.view._yaw-initial_yaw, .3)
        self.assertEqual(self.view._zoom, 1.7)
        self.assertFalse(self.view._turn_timer.isActive())

    def test_rendering_does_not_flash_at_turn_endpoints(self):
        self.view.resize(240,240)
        self.view._arrival = None
        def render():
            image = QImage(240,240,QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor('#121111'))
            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            self.view._paint_cube(painter)
            painter.end()
            return image.constBits().asstring(image.sizeInBytes())
        before = render()
        self.view.set_state(apply_moves(SOLVED_FACELETS, "U"))
        first = render()
        self.assertLess(sum(a != b for a,b in zip(before,first)), 2500)
        self.clock.return_value = self.view._turn[3]+self.view._turn[4]
        last = render()
        self.clock.return_value += .001
        self.view._advance_turn()
        settled = render()
        self.assertLess(sum(a != b for a,b in zip(last,settled)), 2500)

    def test_progress_animation_finishes_at_the_actual_value(self):
        bar = AnimatedProgressBar()
        bar.show()
        bar.setValue(65)
        bar._animation.setCurrentTime(280)
        self.assertEqual(bar.value(), 65)
        bar.close()

    def test_replaced_toast_is_not_hidden_by_old_dismissal(self):
        parent = QWidget()
        parent.show()
        toast = Toast(parent)
        toast.show_message("First")
        toast._dismiss()
        toast.show_message("Second")
        toast._opacity_finished()
        self.assertTrue(toast.isVisible())
        self.assertEqual(toast.text(), "Second")
        parent.close()

    def test_page_overlay_is_removed_on_resize_and_reduced_motion(self):
        pages = FadeStackedWidget()
        pages.addWidget(QLabel("First"))
        pages.addWidget(QLabel("Second"))
        pages.show()
        pages.setCurrentIndex(1)
        pages.resize(400,300)
        _APP.processEvents()
        self.assertIsNone(pages._fade_page)
        _APP.setProperty("reduceMotion", True)
        pages.setCurrentIndex(0)
        self.assertIsNone(pages._fade_page)
        pages.close()

    def test_page_crossfade_has_an_opaque_dark_background(self):
        pages = FadeStackedWidget()
        pages.addWidget(QWidget())
        pages.addWidget(QWidget())
        pages.resize(200,200)
        pages.show()
        pages.setCurrentIndex(1)
        image = pages._fade_page.pixmap().toImage()
        from enigma_timer import theme
        self.assertEqual(image.pixelColor(0,0), QColor(theme.BG))
        pages.close()
