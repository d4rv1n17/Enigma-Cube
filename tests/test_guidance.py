import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from enigma_timer.solver import GuidedSolution, apply_moves, normalize_colors
from enigma_timer.fast3 import SOLVED_FACELETS
from enigma_timer.stats import Solve
from enigma_timer.storage import Store


class GuidanceTests(unittest.TestCase):
    def test_guidance_recovers_after_wrong_turn_is_undone(self):
        initial = apply_moves(SOLVED_FACELETS, "R")
        plan = GuidedSolution(initial, ["R'"])
        self.assertEqual(plan.observe(apply_moves(initial, "F")), "deviated")
        self.assertTrue(plan.deviated)
        self.assertEqual(plan.observe(initial), "ready")
        self.assertFalse(plan.deviated)
        self.assertEqual(plan.observe(SOLVED_FACELETS), "done")

    def test_mastered_cases_are_reviewed_when_due_before_new_cases(self):
        from enigma_timer.learn import Progress, Trainer, LEARNED
        progress = Progress({})
        progress.set_status("mastered", LEARNED, now=100)
        progress.data["cases"]["mastered"]["due"] = 101
        trainer = Trainer(progress, [SimpleNamespace(id="new"), SimpleNamespace(id="mastered")])
        self.assertEqual(trainer.next_case(now=200).id, "mastered")

    def test_half_turn_accepts_either_intermediate_direction(self):
        for first in ("R", "R'"):
            plan = GuidedSolution(SOLVED_FACELETS, ["R2", "U"])
            self.assertEqual(plan.observe(apply_moves(SOLVED_FACELETS, first)), "half")
            self.assertEqual(plan.index, 0)
            self.assertEqual(plan.observe(apply_moves(SOLVED_FACELETS, "R2")), "ready")
            self.assertEqual(plan.index, 1)
            self.assertEqual(plan.observe(apply_moves(SOLVED_FACELETS, "R2 U")), "done")

    def test_lost_move_event_can_be_recovered_from_state(self):
        plan = GuidedSolution(SOLVED_FACELETS, ["R", "U", "F"])
        self.assertEqual(plan.observe(apply_moves(SOLVED_FACELETS, "R U")), "ready")
        self.assertEqual(plan.index, 2)
        self.assertEqual(plan.observe(apply_moves(SOLVED_FACELETS, "R U L")), "deviated")

    def test_orientation_normalizes_centers(self):
        rotated = apply_moves(SOLVED_FACELETS, "x y")
        self.assertEqual(normalize_colors(rotated), SOLVED_FACELETS)
        with self.assertRaises(ValueError):
            normalize_colors("U" * 54)

    def test_replay_metadata_and_old_solves_roundtrip(self):
        old = Solve.from_dict({"ms": 12345})
        self.assertIsNone(old.telemetry)
        old.telemetry = {"initial": SOLVED_FACELETS, "events": [[0, "R"]], "verified": True}
        self.assertEqual(Solve.from_dict(old.to_dict()).telemetry, old.telemetry)

    def test_corrupted_store_recovers_previous_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "data.json")
            store = Store(path)
            store.current.solves.append(Solve(12345))
            store.save()
            store.current.solves.append(Solve(23456))
            store.save()
            with open(path, "w") as f:
                f.write("broken JSON")
            recovered = Store(path)
            self.assertTrue(recovered.recovered_backup)
            self.assertEqual(recovered.current.solves[0].ms, 12345)
            self.assertEqual(len(recovered.current.solves), 1)


if __name__ == "__main__":
    unittest.main()
