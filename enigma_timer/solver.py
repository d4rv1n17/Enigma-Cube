"""Offline solver boundary and state-verified guided solutions."""
import json
import os

from .fast3 import _perm, SOLVED_FACELETS
from .cube import tokens


def apply_moves(facelets, moves):
    if len(facelets) != 54:
        raise ValueError("Expected 54 facelets")
    for move in tokens(moves):
        result = list(facelets)
        for src, dst in enumerate(_perm(move)):
            result[dst] = facelets[src]
        facelets = "".join(result)
    return facelets


def normalize_colors(facelets):
    if len(facelets) != 54 or any(facelets.count(f) != 9 for f in "URFDLB"):
        raise ValueError("Invalid facelet counts")
    centers = [facelets[i * 9 + 4] for i in range(6)]
    if len(set(centers)) != 6:
        raise ValueError("Invalid centers")
    colors = dict(zip(centers, "URFDLB"))
    return "".join(colors[c] for c in facelets)


def solution(facelets):
    from .storage import data_dir
    os.environ.setdefault("RUBIK_SOLVER_CACHE_DIR", os.path.join(data_dir(), "solver-cache"))
    from rubik_solver import Cube, init_solver, solve
    normalized = normalize_colors(facelets)
    cube = Cube.from_string(normalized)
    valid = cube.verify()
    if valid is not True:
        raise ValueError(str(valid))
    if normalized == SOLVED_FACELETS:
        return []
    init_solver()
    moves = solve(cube, max_depth=24)
    if moves is None:
        raise ValueError("No solution found within the search limit")
    if apply_moves(normalized, moves) != SOLVED_FACELETS:
        raise ValueError("Solution verification failed")
    return moves.split()


def worker(facelets, output=None):
    try:
        result = {"moves": solution(facelets)}
    except Exception as error:
        result = {"error": str(error)}
    if output:
        with open(output + ".tmp", "w", encoding="utf-8") as stream:
            json.dump(result, stream)
        os.replace(output + ".tmp", output)
    else:
        print("ENIGMA_SOLVER:" + json.dumps(result), flush=True)


class GuidedSolution:
    def __init__(self, facelets, moves):
        self.moves = list(moves)
        self.states = [facelets]
        for move in moves:
            self.states.append(apply_moves(self.states[-1], move))
        self.index = 0
        self.deviated = False

    @property
    def complete(self):
        return self.index == len(self.moves)

    def observe(self, state):
        # Match physical state, rather than trusting a possibly dropped move event.
        for index in range(len(self.states) - 1, self.index - 1, -1):
            if state == self.states[index]:
                self.index = index
                self.deviated = False
                return "done" if self.complete else "ready"
        if not self.complete and self.moves[self.index].endswith("2"):
            face = self.moves[self.index][0]
            if state in (apply_moves(self.states[self.index], face),
                         apply_moves(self.states[self.index], face + "'")):
                self.deviated = False
                return "half"
        self.deviated = True
        return "deviated"
