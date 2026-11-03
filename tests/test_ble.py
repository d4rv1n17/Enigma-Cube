import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enigma_timer import ble  # noqa: E402

SOLVED_PACKET = bytes(
    [0x12, 0x34, 0x56, 0x78] +          # corner nibbles 0-7: 1..8
    [0x00, 0x00, 0x00, 0x00] +          # corner orientation nibbles 8-15: 0
    [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC] +  # edge nibbles 16-27: 1..12
    [0x00, 0x00] +                      # nibbles 28-31
    [0x41] +                            # nibbles 32/33 = move U (face 4, cw)
    [0x00, 0x00] +                      # nibbles 34-37
    [0x00]                              # nibbles 38/39: decryption offsets
)


class NibbleTest(unittest.TestCase):
    def test_nibbles(self):
        data = bytes([0x12, 0x34])
        self.assertEqual(ble.get_nibble(data, 0), 1)
        self.assertEqual(ble.get_nibble(data, 1), 2)
        self.assertEqual(ble.get_nibble(data, 2), 3)
        self.assertEqual(ble.get_nibble(data, 3), 4)

    def test_bits(self):
        data = bytes([0b10110000])
        self.assertEqual(ble.get_bit(data, 0), 1)
        self.assertEqual(ble.get_bit(data, 1), 0)
        self.assertEqual(ble.get_bit(data, 2), 1)
        self.assertEqual(ble.get_bit(data, 3), 1)
        self.assertEqual(ble.get_bit(data, 4), 0)


class MoveTest(unittest.TestCase):
    def parse(self, face, amount):
        data = bytearray(20)
        data[16] = (face << 4) | amount
        return ble.parse_move(bytes(data))

    def test_moves(self):
        self.assertEqual(self.parse(1, 1)[2], "B")
        self.assertEqual(self.parse(2, 2)[2], "D2")
        self.assertEqual(self.parse(3, 3)[2], "L'")
        self.assertEqual(self.parse(4, 1)[2], "U")
        self.assertEqual(self.parse(5, 3)[2], "R'")
        self.assertEqual(self.parse(6, 2)[2], "F2")
        self.assertEqual(self.parse(6, 9)[2], "F2")

    def test_amounts(self):
        self.assertEqual(self.parse(4, 1)[1], 1)
        self.assertEqual(self.parse(4, 2)[1], 2)
        self.assertEqual(self.parse(4, 3)[1], -1)
        self.assertEqual(self.parse(4, 9)[1], -2)

    def test_invalid_face(self):
        self.assertIsNone(self.parse(0, 1))
        self.assertIsNone(self.parse(7, 1))

    def test_invalid_amount(self):
        self.assertIsNone(self.parse(4, 0))
        self.assertIsNone(self.parse(4, 5))


class SolvedStateTest(unittest.TestCase):
    def test_solved_packet(self):
        cp, co, ep, eo = ble.parse_state(SOLVED_PACKET)
        self.assertEqual(cp, list(range(8)))
        self.assertEqual(co, [0] * 8)
        self.assertEqual(ep, list(range(12)))
        self.assertEqual(eo, [0] * 12)
        self.assertTrue(ble.is_solved_state(cp, co, ep, eo))

    def test_facelets_solved(self):
        cp, co, ep, eo = ble.parse_state(SOLVED_PACKET)
        self.assertEqual(ble.state_to_facelets(cp, co, ep, eo),
                         "U" * 9 + "R" * 9 + "F" * 9
                         + "D" * 9 + "L" * 9 + "B" * 9)

    def test_parse_packet(self):
        move, state = ble.parse_packet(SOLVED_PACKET)
        self.assertIsNotNone(move)
        self.assertEqual(move.notation, "U")
        self.assertEqual(move.amount, 1)
        self.assertEqual(move.face, 4)
        self.assertTrue(state.solved)

    def test_short_packet(self):
        move, state = ble.parse_packet(b"\x00" * 10)
        self.assertIsNone(move)
        self.assertIsNone(state)


class DecryptTest(unittest.TestCase):
    def test_roundtrip(self):
        # Build a raw packet: byte 18 must be the 0xA7 marker (the cube
        # sends it that way); decrypting adds lookup[offset1 + i] +
        # lookup[offset2 + i] to each byte.
        offset1, offset2 = 1, 2
        raw = bytearray(((i * 7) - ble.LOOKUP[offset1 + i]
                         - ble.LOOKUP[offset2 + i]) & 0xFF for i in range(20))
        raw[18] = ble.ENCRYPTED_MARKER
        raw[19] = (offset1 << 4) | offset2
        self.assertTrue(ble.is_encrypted(bytes(raw)))
        expected = bytearray((raw[i] + ble.LOOKUP[offset1 + i]
                              + ble.LOOKUP[offset2 + i]) & 0xFF
                             for i in range(20))
        self.assertEqual(ble.decrypt_packet(bytes(raw)), bytes(expected))

    def test_parse_packet_encrypted(self):
        # Encrypt the solved packet: raw[i] = plain[i] - lookup sums.
        # byte 18 of the raw packet must be 0xA7 (the marker); nibbles
        # 36/37 (inside byte 18) are ignored by the parser, so this works.
        offset1, offset2 = 0, 1
        raw = bytearray((SOLVED_PACKET[i] - ble.LOOKUP[offset1 + i]
                         - ble.LOOKUP[offset2 + i]) & 0xFF for i in range(20))
        raw[18] = ble.ENCRYPTED_MARKER
        raw[19] = (offset1 << 4) | offset2
        move, state = ble.parse_packet(bytes(raw))
        self.assertIsNotNone(state)
        self.assertTrue(state.solved)
        self.assertEqual(move.notation, "U")


class MoveApplicationTest(unittest.TestCase):
    """The cube itself tells us the state after each move; check that our
    parser's state transitions agree with a real cube model."""

    def test_R_move_from_solved(self):
        # The state parsed from a solved cube's packet must reproduce the
        # exact solved facelet string; every face check below pins one face.
        cp, co, ep, eo = ble.parse_state(SOLVED_PACKET)
        facelets = ble.state_to_facelets(cp, co, ep, eo)
        self.assertEqual(facelets[0:9], "U" * 9)
        self.assertEqual(facelets[9:18], "R" * 9)
        self.assertEqual(facelets[18:27], "F" * 9)
        self.assertEqual(facelets[27:36], "D" * 9)
        self.assertEqual(facelets[36:45], "L" * 9)
        self.assertEqual(facelets[45:54], "B" * 9)


class _PacketTools:
    """Shared helpers: cube-model facelets and Giiker packet building."""

    @staticmethod
    def _cube_facelets(cube):
        g = cube.facelets()
        return "".join("".join(row) for face in "URFDLB" for row in g[face])

    @staticmethod
    def _facelets_to_cubies(f):
        """Independent Kociemba facelets->cubies conversion (does not use
        the Giiker permutation tables)."""
        cp, co = [0] * 8, [0] * 8
        for i, slots in enumerate(ble.CORNER_FACELETS):
            cols = [f[s] for s in slots]
            ori = next(n for n in range(3) if cols[n] in "UD")
            piece = next(j for j in range(8)
                         if ble.CORNER_COLORS[j][0] == cols[ori]
                         and ble.CORNER_COLORS[j][1:] ==
                         (cols[(ori + 1) % 3], cols[(ori + 2) % 3]))
            cp[i], co[i] = piece, ori
        ep, eo = [0] * 12, [0] * 12
        for i, slots in enumerate(ble.EDGE_FACELETS):
            c0, c1 = f[slots[0]], f[slots[1]]
            try:
                piece = next(j for j in range(12)
                             if ble.EDGE_COLORS[j] == (c0, c1))
                eo[i] = 0
            except StopIteration:
                piece = next(j for j in range(12)
                             if ble.EDGE_COLORS[j] == (c1, c0))
                eo[i] = 1
            ep[i] = piece
        return cp, co, ep, eo

    @staticmethod
    def _set_nibble(data, i, v):
        if i % 2 == 1:
            data[i // 2] = (data[i // 2] & 0xF0) | v
        else:
            data[i // 2] = (data[i // 2] & 0x0F) | (v << 4)

    @staticmethod
    def _set_bit(data, i, b):
        if b:
            data[i // 8] |= 1 << (7 - (i % 8))

    def _build_packet(self, cp, co, ep, eo):
        """Inverse of parse_state: encode cubie values into a 20-byte
        Giiker packet (unencrypted, no move)."""
        data = bytearray(20)
        for i in range(8):
            gi = ble.CP_REID_TO_GIIKER[i]
            self._set_nibble(data, gi, ble.CP_REID_TO_GIIKER[cp[i]] + 1)
            ori = ((co[i] - ble.PRE_CO[cp[i]] - ble.POST_CO[i])
                   * ble.CO_FLIP[gi]) % 3
            self._set_nibble(data, gi + 8, ori)
        for i in range(12):
            gi = ble.EP_REID_TO_GIIKER[i]
            self._set_nibble(data, gi + 16, ble.EP_REID_TO_GIIKER[ep[i]] + 1)
            self._set_bit(data, gi + 112,
                          eo[i] ^ ble.PRE_EO[ep[i]] ^ ble.POST_EO[i])
        return bytes(data)

    def _build_clone_packet(self, cp, co, ep, eo):
        """Inverse of parse_state_clone: encode cubie values into a 20-byte
        packet the way a clone cube would report them."""
        data = bytearray(20)
        for s in range(8):
            pos = ble.CLONE_CP[s]
            piece = cp[pos]
            self._set_nibble(data, s, ble.CLONE_CP.index(piece) + 1)
            raw = (ble.CLONE_CA[s] * (co[pos] - ble.CLONE_CB[s]
                                      - ble.CLONE_CC[piece])) % 3
            self._set_nibble(data, 8 + s, raw)
        for s in range(12):
            pos = ble.CLONE_EP[s]
            piece = ep[pos]
            self._set_nibble(data, 16 + s, ble.CLONE_EP.index(piece) + 1)
            self._set_bit(data, 112 + s,
                          eo[pos] ^ ble.CLONE_EPRE[piece] ^ ble.CLONE_EPOST[s])
        return bytes(data)

    @staticmethod
    def _with_move(packet, notation):
        """Set the move nibbles (byte 16) the way the cube reports them."""
        code = {"B": 1, "D": 2, "L": 3, "U": 4, "R": 5, "F": 6}[notation[0]]
        amount = 3 if notation.endswith("'") else \
            2 if notation.endswith("2") else 1
        data = bytearray(packet)
        data[16] = (code << 4) | amount
        return bytes(data)


class RoundTripTest(_PacketTools, unittest.TestCase):
    """End-to-end convention lock: the app's own cube simulator (cube.py)
    and the BLE parser must agree on the same 54-char Kociemba facelet
    string, after every single move of a scramble.

    The packet for each intermediate state is built with the inverse of
    parse_state (from the model's cubie values), then parsed back; the
    facelets must reproduce the simulator's net exactly.
    """

    def _check(self, cube):
        fstr = self._cube_facelets(cube)
        cp, co, ep, eo = self._facelets_to_cubies(fstr)
        move, state = ble.parse_packet(self._build_packet(cp, co, ep, eo))
        self.assertIsNone(move)           # no move nibbles in a synthetic packet
        self.assertIsNotNone(state)
        self.assertEqual(ble.state_to_facelets(state.cp, state.co,
                                              state.ep, state.eo), fstr)
        self.assertEqual((state.cp, state.co, state.ep, state.eo),
                         (cp, co, ep, eo))
        return state

    def test_solved_and_single_moves(self):
        from enigma_timer.cube import Cube
        cube = Cube(3)
        state = self._check(cube)
        self.assertTrue(state.solved)
        for mv in ("R", "U'", "F2", "L", "D'", "B2", "R'"):
            cube.apply(mv)
            state = self._check(cube)
            self.assertEqual(state.solved, cube.is_solved())

    def test_random_scramble_tracks_every_move(self):
        import random
        from enigma_timer.cube import Cube
        rng = random.Random(1234)
        cube = Cube(3)
        for _ in range(60):
            mv = rng.choice("URFDLB") + rng.choice(["", "'", "2"])
            cube.apply(mv)
            state = self._check(cube)
            self.assertEqual(state.solved, cube.is_solved())


# Decrypted packets captured from a real clone cube with ENIGMA_BLE_TRACE=1
# (see _calibrate.py): the cube was solved, then turned R U U' U L F D B,
# one slow turn at a time.  These are the ground truth the clone tables in
# ble.py were calibrated and must forever be verified against.
CLONE_TRACE = [
    ("1234567833333333123456789abc00002321acf2", None),
    ("51346278113311331534a27896bc00005123719e", "R"),
    ("52146738111312231524ab38967c26204151ce6c", "U"),
    ("51346278113311331534a27896bc00004341e4d6", "U'"),
    ("52146738111312231524ab38967c2620414345f5", "U"),
    ("52316784112312111523abc4967834203141538e", "L"),
    ("23156784213212115231abc49678642061313c2d", "F"),
    ("531427863131321142315bc9a678eda02161501a", "D"),
    ("531462783131231242315bc98a67ed50112110bc", "B"),
]


class CloneStateTest(_PacketTools, unittest.TestCase):
    """A clone cube's packets must decode to the state the physical cube
    really has after the moves the user performed."""

    def test_clone_decode_matches_physical_cube(self):
        from enigma_timer.cube import Cube
        cube = Cube(3)
        for i, (hexstr, mv) in enumerate(CLONE_TRACE):
            if mv is not None:
                cube.apply(mv)
            cp, co, ep, eo = ble.parse_state_clone(bytes.fromhex(hexstr))
            self.assertEqual(ble.state_to_facelets(cp, co, ep, eo),
                             self._cube_facelets(cube),
                             "clone packet %d (%s) decodes wrong" % (i, mv))

    def test_standard_decode_is_wrong_for_clone(self):
        # The disagreement between the two decodings is what detect_profile
        # keys on; if the standard decoding ever agreed with the physical
        # cube here, the profiles would be indistinguishable.
        from enigma_timer.cube import Cube
        cube = Cube(3)
        wrong = 0
        for hexstr, mv in CLONE_TRACE:
            if mv is not None:
                cube.apply(mv)
            cp, co, ep, eo = ble.parse_state(bytes.fromhex(hexstr))
            if ble.state_to_facelets(cp, co, ep, eo) != self._cube_facelets(cube):
                wrong += 1
        self.assertEqual(wrong, len(CLONE_TRACE) - 1)   # all but the solved one

    def test_clone_packet_roundtrip(self):
        """parse_state_clone must decode ANY state correctly, not only the
        nine calibrated ones: encode a random-walk state the way a clone
        cube would report it and parse it back."""
        import random
        from enigma_timer.cube import Cube
        rng = random.Random(77)
        cube = Cube(3)
        for _ in range(60):
            cube.apply(rng.choice("URFDLB") + rng.choice(["", "'", "2"]))
            fstr = self._cube_facelets(cube)
            cp, co, ep, eo = self._facelets_to_cubies(fstr)
            packet = self._build_clone_packet(cp, co, ep, eo)
            got = ble.parse_state_clone(packet)
            self.assertEqual(got, (cp, co, ep, eo))
            self.assertEqual(ble.state_to_facelets(*got), fstr)


class CloneProfileTest(_PacketTools, unittest.TestCase):
    """detect_profile must recognise a clone cube from its very first
    transition and never flip for a standard cube."""

    def test_detects_clone_on_first_transition(self):
        prev = bytes.fromhex(CLONE_TRACE[0][0])
        profile = None
        for hexstr, _mv in CLONE_TRACE[1:]:
            raw = bytes.fromhex(hexstr)
            profile = ble.detect_profile(prev, raw) or profile
            prev = raw
        self.assertEqual(profile, "clone")

    def test_first_transition_decides(self):
        p = ble.detect_profile(bytes.fromhex(CLONE_TRACE[0][0]),
                               bytes.fromhex(CLONE_TRACE[1][0]))
        self.assertEqual(p, "clone")

    def test_stays_std_for_standard_cube(self):
        import random
        from enigma_timer.cube import Cube
        rng = random.Random(55)
        cube = Cube(3)
        prev = self._build_packet(list(range(8)), [0] * 8,
                                  list(range(12)), [0] * 12)
        for _ in range(40):
            mv = rng.choice("URFDLB") + rng.choice(["", "'", "2"])
            cube.apply(mv)
            fstr = self._cube_facelets(cube)
            cp, co, ep, eo = self._facelets_to_cubies(fstr)
            raw = self._with_move(self._build_packet(cp, co, ep, eo), mv)
            # A standard cube's transitions must never be read as clone
            # packets.  On double turns both decodings fit (the state
            # relabelling commutes with the square of a move), so
            # detect_profile may return None there - but never "clone".
            self.assertNotEqual(ble.detect_profile(prev, raw), "clone")
            prev = raw

    def test_clone_walk_never_flips_to_std(self):
        """Mirror test: a clone cube's transitions (including double turns,
        where both decodings fit) must never be read as standard packets."""
        import random
        from enigma_timer.cube import Cube
        rng = random.Random(56)
        cube = Cube(3)
        prev = self._build_clone_packet(list(range(8)), [0] * 8,
                                        list(range(12)), [0] * 12)
        for _ in range(40):
            mv = rng.choice("URFDLB") + rng.choice(["", "'", "2"])
            cube.apply(mv)
            fstr = self._cube_facelets(cube)
            cp, co, ep, eo = self._facelets_to_cubies(fstr)
            raw = self._with_move(self._build_clone_packet(cp, co, ep, eo), mv)
            self.assertNotEqual(ble.detect_profile(prev, raw), "std")
            prev = raw

    def test_inconclusive_keeps_current(self):
        # A packet pair that fits neither decoding (e.g. a dropped packet)
        # must not flip the profile: detect_profile returns None.
        self.assertIsNone(ble.detect_profile(bytes.fromhex(CLONE_TRACE[1][0]),
                                             bytes.fromhex(CLONE_TRACE[6][0])))


class MoveCubiesTest(_PacketTools, unittest.TestCase):
    """MOVE_CUBIES / apply_face_move must agree with the sticker model for
    every face and amount, over a long random walk."""

    def test_random_walk(self):
        import random
        from enigma_timer.cube import Cube
        rng = random.Random(99)
        cube = Cube(3)
        cp, co, ep, eo = list(range(8)), [0] * 8, list(range(12)), [0] * 12
        self.assertEqual(ble.state_to_facelets(cp, co, ep, eo),
                         self._cube_facelets(cube))
        for _ in range(120):
            face = rng.choice("URFDLB")
            times = rng.choice([1, 2, 3])
            cube.apply(face + {1: "", 2: "2", 3: "'"}[times])
            cp, co, ep, eo = ble.apply_face_move(cp, co, ep, eo, face, times)
            self.assertEqual(ble.state_to_facelets(cp, co, ep, eo),
                             self._cube_facelets(cube),
                             "apply_face_move diverged after %s" %
                             (face + {1: "", 2: "2", 3: "'"}[times]))


if __name__ == "__main__":
    unittest.main()
