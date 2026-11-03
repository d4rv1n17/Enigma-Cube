import math
import unittest
from collections import Counter
from enigma_timer.puzzle_mesh import scene,transition_scene,clock_state,clock_delta,normal_of
from enigma_timer.megaminx import geometry,permutation,state
from enigma_timer.puzzles import Pyraminx,Skewb,sq1_invert


def signature(mesh):
    return Counter((s.color,tuple(sorted(tuple(round(v,6) for v in p) for p in s.points))) for s in mesh)


class PuzzleMeshTests(unittest.TestCase):
    def test_corner_meshes_share_existing_simulator_colors(self):
        for puzzle,model in (("pyram",Pyraminx),("skewb",Skewb)):
            for alg in ("","U R L B U'","R U R' U'"):
                simulated = model().apply(alg)
                self.assertEqual([s.color for s in scene(puzzle,alg)],simulated.colors)
                self.assertEqual(len(simulated.geometry),len(simulated.slots))

    def test_geometry_has_finite_coordinates_and_nonzero_normals(self):
        for puzzle in ("pyram","skewb","sq1","minx","clock"):
            for s in scene(puzzle):
                with self.subTest(puzzle=puzzle,key=s.key):
                    self.assertTrue(all(math.isfinite(v) for p in s.points for v in p))
                    self.assertGreater(sum(v*v for v in normal_of(s.points)),.9)

    def test_megaminx_permutations_are_bijective_and_reversible(self):
        self.assertEqual(len(geometry()[0]),132)
        for token,inverse in (("U","U'"),("R","R'"),("F","F'"),("BR","BR'"),("BL","BL'"),("L","L'"),("R++","R--"),("D++","D--")):
            with self.subTest(token=token):
                self.assertEqual(sorted(permutation(token)),list(range(132)))
                self.assertEqual(state(token+" "+inverse),state())
                self.assertEqual(state(" ".join([token]*5)),state())
        self.assertNotEqual(state("R++ D-- U R--"),state())

    def test_clock_ganging_matches_wca_pin_groups(self):
        self.assertEqual(clock_delta("UL")[:9],(1,1,0,1,1,0,0,0,0))
        self.assertEqual(clock_delta("UR")[:9],(0,1,1,0,1,1,0,0,0))
        self.assertEqual(clock_delta("U")[:9],(1,1,1,1,1,1,0,0,0))
        self.assertEqual(clock_delta("ALL")[:9],(1,)*9)
        self.assertEqual(clock_state("UR3+ UR3-")[0],(0,)*18)
        self.assertEqual(clock_state("UR12+")[0],(0,)*18)
        self.assertEqual(clock_state("y2 y2"),clock_state(""))
        # Rear corner hands turn the opposite way; inner rear dials stay still.
        self.assertEqual(clock_state("UL1+")[0][9:],(0,0,11,0,0,0,0,0,0))
        self.assertEqual(clock_state("y2 UL1+")[0][:9],(0,0,11,0,0,0,0,0,0))

    def test_animated_move_endpoints_are_exact_target_scenes(self):
        examples = {
            "pyram":[(a,b) for a in ("","U R L'") for b in ("U","L'","R","B'","u","l'","r","b'")],
            "skewb":[(a,b) for a in ("","R U L'") for b in ("R","U'","L","B'")],
            "minx":[(a,b) for a in ("","R++ D-- U") for b in ("R++","D--","U'","F2","BR")],
            "sq1":[("","(1,0)"),("","(0,-1)"),("","/"),("(1,0)","/"),("(1,0) /","(0,3)"),("(0,-1)","/")],
            "clock":[("","UL3+"),("UR3+","ALL2-"),("UR3+","y2"),("UR3+ y2","D4-")],
        }
        for puzzle,moves in examples.items():
            for before,move in moves:
                after=(before+" "+move).strip()
                with self.subTest(puzzle=puzzle,before=before,move=move):
                    self.assertEqual(signature(transition_scene(puzzle,before,move,0)),signature(scene(puzzle,before)))
                    self.assertEqual(signature(transition_scene(puzzle,before,move,1)),signature(scene(puzzle,after)))
                    self.assertEqual(signature(transition_scene(puzzle,after,move,1,True)),signature(scene(puzzle,before)))

    def test_square_shape_changes_and_returns_after_inverse(self):
        alg="(1,0) / (0,3) /"
        self.assertNotEqual(signature(scene("sq1",alg)),signature(scene("sq1")))
        self.assertEqual(signature(scene("sq1",alg+" "+sq1_invert(alg))),signature(scene("sq1")))


if __name__=="__main__":
    unittest.main()
