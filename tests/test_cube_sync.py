import json
import random
import unittest

from enigma_timer.cube_sync import StateCalibration, facelets_to_state
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer.solver import apply_moves


class CubeSyncTests(unittest.TestCase):
    def test_reference_offset_survives_many_moves_and_missing_notifications(self):
        reported = apply_moves(SOLVED_FACELETS, "R U2 F D' B2")
        physical = apply_moves(SOLVED_FACELETS, "L2 B R' U F2 D")
        correction = StateCalibration.between(facelets_to_state(reported), facelets_to_state(physical))
        correction = StateCalibration.from_dict(json.loads(json.dumps(correction.to_dict())))
        rng = random.Random(578)
        for index in range(150):
            move = rng.choice("URFDLB") + rng.choice(["", "'", "2"])
            reported = apply_moves(reported, move)
            physical = apply_moves(physical, move)
            if index % 5 == 0:  # receive full packets, even with moves lost in between
                state = facelets_to_state(reported, index)
                corrected = correction.apply(state)
                self.assertEqual(corrected.facelets(), physical)
                self.assertEqual(corrected.time, index)

    def test_false_sensor_solved_is_not_physical_solved(self):
        physical = apply_moves(SOLVED_FACELETS, "R U F2")
        correction = StateCalibration.between(facelets_to_state(SOLVED_FACELETS), facelets_to_state(physical))
        self.assertFalse(correction.apply(facelets_to_state(SOLVED_FACELETS)).solved)

    def test_confirmed_physical_solved_can_have_non_solved_sensor_reference(self):
        reported = apply_moves(SOLVED_FACELETS, "R U F2 D B2")
        correction = StateCalibration.between(facelets_to_state(reported), facelets_to_state(SOLVED_FACELETS))
        self.assertTrue(correction.apply(facelets_to_state(reported)).solved)
        self.assertEqual(correction.apply(facelets_to_state(apply_moves(reported, "F"))).facelets(),
                         apply_moves(SOLVED_FACELETS, "F"))

    def test_impossible_single_edge_flip_is_rejected(self):
        colors = list(SOLVED_FACELETS)
        colors[7], colors[19] = colors[19], colors[7]
        with self.assertRaises(ValueError):
            facelets_to_state("".join(colors))

    def test_invalid_saved_mapping_is_rejected(self):
        with self.assertRaises(ValueError):
            StateCalibration([0]*8, [0]*8, list(range(12)), [0]*12)
