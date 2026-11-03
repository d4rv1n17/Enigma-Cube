"""Bind a sensor's internal piece identities to a verified physical state.

The correction is a constant relabeling of pieces and their orientation
offsets. It is applied to complete packets, never by accumulating BLE moves.
"""
from .ble import (CubeState, CORNER_FACELETS, CORNER_COLORS, EDGE_FACELETS,
                  EDGE_COLORS, _valid_state)


def facelets_to_state(facelets, timestamp=0):
    if len(facelets) != 54 or any(facelets.count(f) != 9 for f in "URFDLB"):
        raise ValueError("Each color must occur exactly nine times")
    if any(facelets[i*9+4] != f for i, f in enumerate("URFDLB")):
        raise ValueError("The centers do not match the sensor frame")
    cp, co, ep, eo = [], [], [], []
    for slots in CORNER_FACELETS:
        colors = [facelets[s] for s in slots]
        orientation = next((i for i, c in enumerate(colors) if c in "UD"), None)
        if orientation is None:
            raise ValueError("Invalid corner colors")
        piece = next((i for i, c in enumerate(CORNER_COLORS)
                      if c == tuple(colors[(orientation+j) % 3] for j in range(3))), None)
        if piece is None:
            raise ValueError("Invalid corner colors or orientation")
        cp.append(piece)
        co.append(orientation)
    for slots in EDGE_FACELETS:
        colors = tuple(facelets[s] for s in slots)
        piece = next((i for i, c in enumerate(EDGE_COLORS) if colors in (c, c[::-1])), None)
        if piece is None:
            raise ValueError("Invalid edge colors")
        ep.append(piece)
        eo.append(int(colors != EDGE_COLORS[piece]))
    if not _valid_state((cp, co, ep, eo)):
        raise ValueError("Impossible cube: check duplicate pieces, twists and flips")
    return CubeState(cp, co, ep, eo, timestamp)


class StateCalibration:
    def __init__(self, corners, twists, edges, flips):
        if (sorted(corners) != list(range(8)) or sorted(edges) != list(range(12))
                or len(twists) != 8 or any(t not in (0, 1, 2) for t in twists)
                or len(flips) != 12 or any(f not in (0, 1) for f in flips)):
            raise ValueError("Invalid state calibration")
        if not _valid_state((corners, twists, edges, flips)):
            raise ValueError("Impossible state calibration")
        self.corners, self.twists = list(corners), list(twists)
        self.edges, self.flips = list(edges), list(flips)

    @classmethod
    def between(cls, reported, physical):
        if not all(_valid_state((s.cp, s.co, s.ep, s.eo)) for s in (reported, physical)):
            raise ValueError("Invalid reference state")
        corners, twists, edges, flips = [0]*8, [0]*8, [0]*12, [0]*12
        for slot, piece in enumerate(reported.cp):
            corners[piece] = physical.cp[slot]
            twists[piece] = (physical.co[slot] - reported.co[slot]) % 3
        for slot, piece in enumerate(reported.ep):
            edges[piece] = physical.ep[slot]
            flips[piece] = physical.eo[slot] ^ reported.eo[slot]
        return cls(corners, twists, edges, flips)

    def apply(self, state):
        return CubeState([self.corners[p] for p in state.cp],
                         [(o+self.twists[p]) % 3 for p, o in zip(state.cp, state.co)],
                         [self.edges[p] for p in state.ep],
                         [o ^ self.flips[p] for p, o in zip(state.ep, state.eo)], state.time)

    def to_dict(self):
        return {"corners": self.corners, "twists": self.twists,
                "edges": self.edges, "flips": self.flips}

    @classmethod
    def from_dict(cls, data):
        return cls(data["corners"], data["twists"], data["edges"], data["flips"])
