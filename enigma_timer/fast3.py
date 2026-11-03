"""Fast 3x3 simulator built on sticker permutations.

The generic Cube class is exact but slow; for the training section we need
to evaluate hundreds of algorithms, so every move is turned once into a
permutation of the 54 sticker locations and then applied with plain lists.
"""

from .cube import Cube, invert, tokens

FACES = "URFDLB"
LOCS = [(f, r, c) for f in FACES for r in range(3) for c in range(3)]
LOC_INDEX = dict((loc, i) for i, loc in enumerate(LOCS))
CENTRE = dict((f, LOC_INDEX[(f, 1, 1)]) for f in FACES)

_BASE = Cube(3)
# sticker id -> location index in the solved cube, and its colour
_HOME = {}
COLOR = {}
for _pos, _nv, _col, _sid in _BASE.stickers:
    _f, _r, _c = _BASE.locate(_pos, _nv)
    _HOME[_sid] = LOC_INDEX[(_f, _r, _c)]
    COLOR[LOC_INDEX[(_f, _r, _c)]] = _col

_PERM = {}


def _perm(tok):
    """perm[i] = location where the sticker at location i ends up."""
    p = _PERM.get(tok)
    if p is None:
        c = Cube(3).apply(tok)
        p = [0] * 54
        for pos, nv, col, sid in c.stickers:
            f, r, cc = c.locate(pos, nv)
            p[_HOME[sid]] = LOC_INDEX[(f, r, cc)]
        _PERM[tok] = p
    return p


ROTATIONS = []
for _a in ("", "x", "x2", "x'", "z", "z'"):
    for _b in ("", "y", "y2", "y'"):
        ROTATIONS.append((_a + " " + _b).strip())


class State(object):
    """arr[location] = id of the solved location the sticker came from."""

    __slots__ = ("arr",)

    def __init__(self, arr=None):
        self.arr = list(arr) if arr is not None else list(range(54))

    def copy(self):
        return State(self.arr)

    def apply(self, alg):
        arr = self.arr
        for tok in tokens(alg):
            p = _perm(tok)
            new = [0] * 54
            for src in range(54):
                new[p[src]] = arr[src]
            arr = new
        self.arr = arr
        return self

    def color(self, loc):
        return COLOR[self.arr[loc]]

    def centre(self, face):
        return COLOR[self.arr[CENTRE[face]]]

    def normalize(self):
        """Rotate the whole cube so the centres are in standard position."""
        if self.centre("U") == "U" and self.centre("F") == "F":
            return self
        for rot in ROTATIONS:
            c = self.copy().apply(rot)
            if c.centre("U") == "U" and c.centre("F") == "F":
                self.arr = c.arr
                return self
        return self

    def facelets(self):
        g = dict((f, [[None] * 3 for _ in range(3)]) for f in FACES)
        for i, (f, r, c) in enumerate(LOCS):
            g[f][r][c] = COLOR[self.arr[i]]
        return g

    def ids(self):
        g = dict((f, [[None] * 3 for _ in range(3)]) for f in FACES)
        for i, (f, r, c) in enumerate(LOCS):
            g[f][r][c] = self.arr[i]
        return g

    def key(self):
        return tuple(COLOR[x] for x in self.arr)

    def is_solved(self):
        g = self.facelets()
        return all(len(set(c for row in g[f] for c in row)) == 1 for f in g)


def net_rotation(alg):
    """Whole-cube rotation that `alg` leaves behind."""
    c = State().apply(alg)
    for rot in ROTATIONS:
        r = State().apply(rot)
        if all(r.centre(f) == c.centre(f) for f in "UF"):
            return rot
    return ""


def case_state(alg):
    """The state `alg` solves, seen from the solver's starting view."""
    return State().apply(net_rotation(alg)).apply(invert(alg))


def facelets_str(g):
    """Fast3 facelets() dict -> 54-char URFDLB string."""
    return "".join(g[f][r][c] for f in FACES for r in range(3) for c in range(3))


def _rotate_str(s, perm):
    """Rotate a 54-char facelet string by the sticker permutation `perm`.

    The result at position i takes its value from s[perm[i]] (perm is the
    sticker permutation of the applied rotation, as built by State().apply).
    """
    return "".join(s[perm[i]] for i in range(54))


_PERM_CACHE = {}


def _perm_for(alg):
    p = _PERM_CACHE.get(alg)
    if p is None:
        p = tuple(State().apply(alg).arr)
        _PERM_CACHE[alg] = p
    return p


def _rotations():
    out = []
    for rot in ROTATIONS:
        for auf in ("", "U", "U2", "U'"):
            out.append((rot, auf))
    return out


ROT_AUF_PAIRS = _rotations()


def recognize_case(state_facelets, cases):
    """Return the case whose picture matches `state_facelets` (54 chars).

    Tries every whole-cube rotation (24) and AUF (4), so the cube may be
    held in any orientation.  Returns None if no case matches.
    """
    for rot, auf in ROT_AUF_PAIRS:
        s = _rotate_str(state_facelets, _perm_for(auf)) if auf else state_facelets
        s = _rotate_str(s, _perm_for(rot))
        for c in cases:
            key = _CASE_KEYS.get(c.id)
            if key is None:
                st = c.state()
                if st is None:
                    continue
                key = facelets_str(st.facelets())
                _CASE_KEYS[c.id] = key
            if s == key:
                return c
    return None


_CASE_KEYS = {}


def recognize_case_state(state_facelets, cases):
    """Like recognize_case but also returns (rot, auf) that were matched."""
    for rot, auf in ROT_AUF_PAIRS:
        s = _rotate_str(state_facelets, _perm_for(auf)) if auf else state_facelets
        s = _rotate_str(s, _perm_for(rot))
        for c in cases:
            key = _CASE_KEYS.get(c.id)
            if key is None:
                st = c.state()
                if st is None:
                    continue
                key = facelets_str(st.facelets())
                _CASE_KEYS[c.id] = key
            if s == key:
                return c, rot, auf
    return None, "", ""


def case_key(case):
    """54-char facelet string of the case's state (cached)."""
    key = _CASE_KEYS.get(case.id)
    if key is None:
        st = case.state()
        if st is None:
            return None
        key = facelets_str(st.facelets())
        _CASE_KEYS[case.id] = key
    return key


SOLVED_FACELETS = "U" * 9 + "R" * 9 + "F" * 9 + "D" * 9 + "L" * 9 + "B" * 9


def is_solved_facelets(state_facelets):
    """True if the cube is solved in any of the 24 whole-cube orientations."""
    if state_facelets == SOLVED_FACELETS:
        return True
    return any(_rotate_str(state_facelets, _perm_for(rot)) == SOLVED_FACELETS
               for rot in ROTATIONS)
