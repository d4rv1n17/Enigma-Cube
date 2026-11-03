"""Notation uses the same white-U, green-F frame as the scramble simulator."""
from .cube import FACE_COLORS
from .fastn import NState
from .caseview import iso_grid

CUBE_EVENTS = {"222": 2, "333": 3, "444": 4, "555": 5, "666": 6, "777": 7,
               "333oh": 3, "333bf": 3, "333fm": 3}


def notation_grid(puzzle, moves=""):
    return NState(CUBE_EVENTS[puzzle]).apply(moves).facelets()


def notation_shapes(puzzle, moves=""):
    return iso_grid(notation_grid(puzzle, moves), CUBE_EVENTS[puzzle], palette=FACE_COLORS)


def notation_facelets(puzzle, moves=""):
    """The same URFDLB state consumed by the interactive renderer."""
    return "".join(NState(CUBE_EVENTS[puzzle]).apply(moves).key())
