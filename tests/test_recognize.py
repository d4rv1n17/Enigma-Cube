"""Recognition of the live cube state against the training case database."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enigma_timer import algs, fast3  # noqa: E402


def facelets_str_from_state(st):
    g = st.facelets()
    out = []
    for f in "URFDLB":
        for r in range(3):
            for c in range(3):
                out.append(g[f][r][c])
    return "".join(out)


def _perm_for(rot):
    return fast3.State().apply(rot).arr


def rotated(s, perm):
    return "".join(s[perm[i]] for i in range(54))


def rotate_y2(s):
    # y2 rotation: U<->D, F<->B, L<->R (with flips)
    perm = _perm_for("y2")
    return rotated(s, perm)


class RecognizeTest(unittest.TestCase):
    def test_oll_case_recognized(self):
        cases = [algs.SET_BY_ID["oll2"].cases[0]]
        c = cases[0]
        # setup() creates the case from solved; the state the solver sees is
        # c.state() (the same view as the training picture).
        s = facelets_str_from_state(c.state())
        self.assertEqual(fast3.recognize_case(s, cases), c)

    def test_oll_case_any_orientation(self):
        cases = algs.SET_BY_ID["oll2"].cases
        c = cases[0]
        s = facelets_str_from_state(c.state())
        # whole-cube rotation in any of 24 orientations
        for rot in fast3.ROTATIONS:
            r = rotated(s, _perm_for(rot))
            self.assertEqual(fast3.recognize_case(r, cases), c,
                             "case %s not recognized after %s" % (c.id, rot))

    def test_oll_case_any_auf(self):
        cases = algs.SET_BY_ID["oll2"].cases
        c = cases[0]
        s = facelets_str_from_state(c.state())
        for auf in ("", "U", "U2", "U'"):
            r = rotated(s, _perm_for(auf))
            self.assertEqual(fast3.recognize_case(r, cases), c,
                             "case %s not recognized after AUF %s" % (c.id, auf))

    def test_oll_case_rotation_plus_auf(self):
        cases = algs.SET_BY_ID["oll2"].cases
        c = cases[0]
        s = facelets_str_from_state(c.state())
        for rot in fast3.ROTATIONS:
            r = rotated(s, _perm_for(rot))
            for auf in ("", "U", "U2", "U'"):
                r2 = rotated(r, _perm_for(auf))
                self.assertEqual(fast3.recognize_case(r2, cases), c,
                                 "case %s not recognized after %s %s" % (c.id, rot, auf))

    def test_oll_case_distinct(self):
        cases = algs.SET_BY_ID["oll2"].cases
        # all 10 cases must be recognized as themselves
        for c in cases:
            s = facelets_str_from_state(c.state())
            self.assertEqual(fast3.recognize_case(s, cases), c)

    def test_oll_case_distinct_rotations(self):
        cases = algs.SET_BY_ID["oll2"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            for rot in fast3.ROTATIONS:
                r = rotated(s, _perm_for(rot))
                self.assertEqual(fast3.recognize_case(r, cases), c)

    def test_full_oll_all_cases(self):
        cases = algs.SET_BY_ID["oll"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            found = fast3.recognize_case(s, cases)
            self.assertEqual(found, c,
                             "OLL case %s not recognized" % c.id)

    def test_full_oll_all_rotations(self):
        cases = algs.SET_BY_ID["oll"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            for rot in fast3.ROTATIONS:
                r = rotated(s, _perm_for(rot))
                self.assertEqual(fast3.recognize_case(r, cases), c)

    def test_pll_all_cases(self):
        cases = algs.SET_BY_ID["pll"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            self.assertEqual(fast3.recognize_case(s, cases), c)

    def test_f2l_all_cases(self):
        cases = algs.SET_BY_ID["f2l"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            self.assertEqual(fast3.recognize_case(s, cases), c)

    def test_f2l_all_rotations(self):
        cases = algs.SET_BY_ID["f2l"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            for rot in fast3.ROTATIONS:
                r = rotated(s, _perm_for(rot))
                self.assertEqual(fast3.recognize_case(r, cases), c)

    def test_solved_is_not_a_case(self):
        cases = algs.SET_BY_ID["oll"].cases
        solved = "U" * 9 + "R" * 9 + "F" * 9 + "D" * 9 + "L" * 9 + "B" * 9
        self.assertIsNone(fast3.recognize_case(solved, cases))

    def test_solved_is_not_a_case_after_rotation(self):
        cases = algs.SET_BY_ID["oll"].cases
        solved = "U" * 9 + "R" * 9 + "F" * 9 + "D" * 9 + "L" * 9 + "B" * 9
        for rot in fast3.ROTATIONS:
            r = rotated(solved, _perm_for(rot))
            self.assertIsNone(fast3.recognize_case(r, cases))

    def test_oll2_all_rotations(self):
        cases = algs.SET_BY_ID["oll2"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            for rot in fast3.ROTATIONS:
                r = rotated(s, _perm_for(rot))
                self.assertEqual(fast3.recognize_case(r, cases), c)

    def test_pll2_all_rotations(self):
        cases = algs.SET_BY_ID["pll2"].cases
        for c in cases:
            s = facelets_str_from_state(c.state())
            for rot in fast3.ROTATIONS:
                r = rotated(s, _perm_for(rot))
                self.assertEqual(fast3.recognize_case(r, cases), c)


if __name__ == "__main__":
    unittest.main()
