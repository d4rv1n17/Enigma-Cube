"""Bluetooth smart-cube support: Giiker Super Cube (original, 0xAADB).

The cube sends 20-byte notifications on the 0xAADB service (characteristic
0xAADC).  A packet is 40 nibbles:

* nibbles 0-7   corner permutation (values 1-8)
* nibbles 8-15  corner orientation (values 0-2)
* nibbles 16-27 edge permutation (values 1-12)
* nibbles 28-31 other info (ignored)
* nibbles 32-33 the move that just happened (face, amount)
* nibbles 34-37 other info (ignored)
* nibbles 38-39 decryption offsets (and 0xA7 marker in byte 18)

Some firmware encrypts the state; a packet with byte 18 == 0xA7 is decrypted
by adding two lookup-table entries per byte (offsets taken from nibbles 38
and 39).  All of the tables below are taken verbatim from cubing.js
(smart-puzzle/giiker.ts).

This module deliberately contains no Qt imports: the parsing is pure and can
be tested without Bluetooth.  The Qt glue lives in the GiikerWorker class at
the bottom.
"""

import asyncio
import os
import re
import time

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from .i18n import tr

# ---------------------------------------------------------------- constants

MESSAGE_LENGTH = 20

SERVICE_UUID = "0000aadb-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000aadc-0000-1000-8000-00805f9b34fb"

# Device name prefixes seen on Giiker-family cubes.
NAME_PREFIXES = ("Gi", "Mi", "Hi-", "QY", "QiYi")


def is_cube_advertisement(name, advertisement=None):
    """Return whether a BLE advertisement plausibly belongs to a smart cube.

    Giiker clones are often missing their local name in the first Windows
    advertisement. The AADB service UUID is a more reliable identifier when
    it is present; name matching remains a fallback for firmware that omits it.
    """
    folded_name = (name or "").strip().casefold()
    # "Mi" alone also matches Mi Band/headphones: require a cube name.
    if re.match(r"^(?:giiker|gi(?=[\d\s_-]|$)|mi smart magic cube|mi(?=\d)|hi-|qiyi|qy(?=[\d_-]|$))",
                folded_name):
        return True
    uuids = getattr(advertisement, "service_uuids", None) or ()
    normalized = {str(uuid).strip().casefold().replace("0x", "").replace("-", "")
                  for uuid in uuids}
    service_data = getattr(advertisement, "service_data", None) or {}
    normalized.update(str(uuid).strip().casefold().replace("0x", "").replace("-", "")
                      for uuid in service_data)
    return bool(normalized.intersection({
        "aadb", "0000aadb", "0000aadb00001000800000805f9b34fb"
    }))

# Face nibble (index 32) -> face letter: 1=B, 2=D, 3=L, 4=U, 5=R, 6=F.
MOVE_FACES = {1: "B", 2: "D", 3: "L", 4: "U", 5: "R", 6: "F"}

# Encryption marker byte + the 36-value decryption lookup table (cubing.js).
ENCRYPTED_MARKER = 0xA7
LOOKUP = [
    176, 81, 104, 224, 86, 137, 237, 119, 38, 26, 193, 161, 210, 126, 150, 81,
    93, 13, 236, 249, 89, 235, 88, 24, 113, 81, 214, 131, 130, 199, 2, 169,
    39, 165, 171, 41,
]

# Giiker corner permutation -> Kociemba (Reid) corner index.
CP_GIIKER_TO_REID = [4, 0, 3, 5, 7, 1, 2, 6]
CP_REID_TO_GIIKER = [1, 5, 6, 2, 0, 3, 7, 4]

# Giiker edge permutation -> Kociemba edge index.
EP_GIIKER_TO_REID = [4, 8, 0, 9, 5, 1, 3, 7, 6, 10, 2, 11]
EP_REID_TO_GIIKER = [2, 5, 10, 6, 0, 4, 8, 7, 1, 3, 9, 11]

# Orientation fix-up tables (cubing.js, verbatim).
PRE_CO = [1, 2, 1, 2, 2, 1, 2, 1]
POST_CO = [2, 1, 2, 1, 1, 2, 1, 2]
CO_FLIP = [-1, 1, -1, 1, 1, -1, 1, -1]
PRE_EO = [1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0]
POST_EO = [1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0]

# ---------------------------------------------------------------- clone cubes
# Some Giiker-compatible cubes report states in a different slot order and
# with different orientation conventions.  The tables below were calibrated
# against a real clone cube (_calibrate.py): the cube was turned one face at
# a time from solved and the reported packets were fitted against the known
# physical states; the fit reproduces every captured packet exactly.
# CLONE_CP[s] is the Kociemba corner position clone slot s stands for, and
# CLONE_CP[v - 1] the piece a corner value v names.  Corner orientations are
# true = (CLONE_CA[s] * raw + CLONE_CB[s] + CLONE_CC[piece]) % 3; edge flips
# are raw_bit ^ CLONE_EPRE[piece] ^ CLONE_EPOST[s], with edge bit s belonging
# to clone edge slot s.
CLONE_CP = [4, 0, 1, 5, 7, 3, 2, 6]
CLONE_CA = [-1, 1, -1, 1, 1, -1, 1, -1]
CLONE_CB = [2, 0, 2, 0, 0, 2, 0, 2]
CLONE_CC = [0, 1, 0, 1, 1, 0, 1, 0]
CLONE_EP = [5, 8, 1, 9, 4, 0, 2, 6, 7, 11, 3, 10]
CLONE_EPRE = [1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1]
CLONE_EPOST = [0, 1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1]

# One clockwise turn of each face in piece-movement form (Kociemba indexing,
# derived from the sticker model and verified in tests/test_ble.py):
# DEST[p] is the position the piece at p moves to and DTW[p] the twist it
# picks up when it leaves position p (EDEST/EFLIP likewise for edges).
MOVE_CUBIES = {
    "U": ([1, 2, 3, 0, 4, 5, 6, 7],
          [0, 0, 0, 0, 0, 0, 0, 0],
          [1, 2, 3, 0, 4, 5, 6, 7, 8, 9, 10, 11],
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    "R": ([3, 1, 2, 7, 0, 5, 6, 4],
          [1, 0, 0, 2, 2, 0, 0, 1],
          [11, 1, 2, 3, 8, 5, 6, 7, 0, 9, 10, 4],
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    "F": ([4, 0, 2, 3, 5, 1, 6, 7],
          [2, 1, 0, 0, 1, 2, 0, 0],
          [0, 8, 2, 3, 4, 9, 6, 7, 5, 1, 10, 11],
          [0, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0]),
    "D": ([0, 1, 2, 3, 7, 4, 5, 6],
          [0, 0, 0, 0, 0, 0, 0, 0],
          [0, 1, 2, 3, 7, 4, 5, 6, 8, 9, 10, 11],
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    "L": ([0, 5, 1, 3, 4, 6, 2, 7],
          [0, 2, 1, 0, 0, 1, 2, 0],
          [0, 1, 9, 3, 4, 5, 10, 7, 8, 6, 2, 11],
          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
    "B": ([0, 1, 6, 2, 4, 5, 7, 3],
          [0, 0, 2, 1, 0, 0, 1, 2],
          [0, 1, 2, 10, 4, 5, 6, 11, 8, 9, 7, 3],
          [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 1]),
}

# Facelets of each corner (Kociemba order: URF, UFL, ULB, UBR, DFR, DLF, DBL,
# DRB), indices into the 54-char URFDLB facelet string.  On the B face the
# reading order runs right-to-left physically (B1 sits next to R3), so the
# DBL corner reads B9 (53) and DRB reads B7 (51).
CORNER_FACELETS = [
    (8, 9, 20), (6, 18, 38), (0, 36, 47), (2, 45, 11),
    (29, 26, 15), (27, 44, 24), (33, 53, 42), (35, 17, 51),
]

# Facelets of each edge (UR, UF, UL, UB, DR, DF, DL, DB, FR, FL, BL, BR).
EDGE_FACELETS = [
    (5, 10), (7, 19), (3, 37), (1, 46),
    (32, 16), (28, 25), (30, 43), (34, 52),
    (23, 12), (21, 41), (50, 39), (48, 14),
]

# The colors of each corner piece in solved orientation, one per facelet slot.
CORNER_COLORS = [
    ("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"),
    ("D", "F", "R"), ("D", "L", "F"), ("D", "B", "L"), ("D", "R", "B"),
]

# The colors of each edge piece in solved orientation.
EDGE_COLORS = [
    ("U", "R"), ("U", "F"), ("U", "L"), ("U", "B"),
    ("D", "R"), ("D", "F"), ("D", "L"), ("D", "B"),
    ("F", "R"), ("F", "L"), ("B", "L"), ("B", "R"),
]


# ---------------------------------------------------------------- helpers

def get_nibble(data: bytes, i: int) -> int:
    """Nibble i of the packet (high nibble first)."""
    if i % 2 == 1:
        return data[i // 2] % 16
    return data[i // 2] // 16


def get_bit(data: bytes, i: int) -> int:
    """Bit i of the packet (bit 0 = most significant bit of byte 0)."""
    return (data[i // 8] >> (7 - (i % 8))) & 1


def is_encrypted(data: bytes) -> bool:
    return len(data) == MESSAGE_LENGTH and data[18] == ENCRYPTED_MARKER


def decrypt_packet(data: bytes) -> bytes:
    """Undo the 0xA7 encryption using the two offsets from nibbles 38/39."""
    offset1 = get_nibble(data, 38)
    offset2 = get_nibble(data, 39)
    out = bytearray(MESSAGE_LENGTH)
    for i in range(MESSAGE_LENGTH):
        out[i] = (data[i] + LOOKUP[offset1 + i] + LOOKUP[offset2 + i]) & 0xFF
    return bytes(out)


def plaintext_packet(data: bytes):
    """Return one validated plaintext packet, decrypting it when needed."""
    if len(data) != MESSAGE_LENGTH:
        return None
    return decrypt_packet(data) if is_encrypted(data) else bytes(data)


# ---------------------------------------------------------------- parsing

def parse_move(data: bytes):
    """Return (face, amount, notation) from nibbles 32/33, or None."""
    face = get_nibble(data, 32)
    amount = get_nibble(data, 33)
    if face not in MOVE_FACES:
        return None
    # 1 = clockwise, 2 = double, 3 = counter-clockwise, 9 = double counter-
    # clockwise (reported as -2, same notation as double).
    if amount == 3:
        amount = -1
    elif amount == 9:
        amount = -2
    elif amount not in (1, 2):
        return None
    if amount == 2:
        notation = MOVE_FACES[face] + "2"
    elif amount == -1:
        notation = MOVE_FACES[face] + "'"
    elif amount == -2:
        notation = MOVE_FACES[face] + "2"
    else:
        notation = MOVE_FACES[face]
    return face, amount, notation


def parse_state(data: bytes):
    """Parse the 20-byte packet into a Kociemba-style state.

    Returns (corner_pieces, corner_orientation, edge_pieces, edge_orientation)
    using the standard Reid/Kociemba indexing (corners URF..DRB, edges UR..BR).
    """
    cp = []
    co = []
    for i in range(8):
        gi = CP_REID_TO_GIIKER[i]
        piece = CP_GIIKER_TO_REID[get_nibble(data, gi) - 1]
        orientation = (get_nibble(data, gi + 8) * CO_FLIP[gi]
                       + PRE_CO[piece] + POST_CO[i]) % 3
        cp.append(piece)
        co.append(orientation)
    ep = []
    eo = []
    for i in range(12):
        gi = EP_REID_TO_GIIKER[i]
        piece = EP_GIIKER_TO_REID[get_nibble(data, gi + 16) - 1]
        orientation = (get_bit(data, gi + 112)
                       ^ PRE_EO[piece] ^ POST_EO[i])
        ep.append(piece)
        eo.append(orientation)
    return cp, co, ep, eo


def parse_state_clone(data: bytes):
    """Parse a packet from a clone cube (CLONE_* tables above).

    Same return convention as parse_state().
    """
    cp = [0] * 8
    co = [0] * 8
    for s in range(8):
        piece = CLONE_CP[get_nibble(data, s) - 1]
        pos = CLONE_CP[s]
        cp[pos] = piece
        co[pos] = (CLONE_CA[s] * get_nibble(data, 8 + s) + CLONE_CB[s]
                   + CLONE_CC[piece]) % 3
    ep = [0] * 12
    eo = [0] * 12
    for s in range(12):
        piece = CLONE_EP[get_nibble(data, 16 + s) - 1]
        pos = CLONE_EP[s]
        ep[pos] = piece
        eo[pos] = get_bit(data, 112 + s) ^ CLONE_EPRE[piece] ^ CLONE_EPOST[s]
    return cp, co, ep, eo


def apply_face_move(cp, co, ep, eo, face: str, times: int = 1):
    """Apply `times` clockwise turns of `face` to a parsed cubie state."""
    dest, dtw, edest, efl = MOVE_CUBIES[face]
    for _ in range(times):
        ncp, nco = [0] * 8, [0] * 8
        for p in range(8):
            q = dest[p]
            ncp[q] = cp[p]
            nco[q] = (co[p] + dtw[p]) % 3
        nep, neo = [0] * 12, [0] * 12
        for p in range(12):
            q = edest[p]
            nep[q] = ep[p]
            neo[q] = eo[p] ^ efl[p]
        cp, co, ep, eo = ncp, nco, nep, neo
    return cp, co, ep, eo


def _plausible(state) -> bool:
    """A parsed state must be a permutation of all pieces."""
    cp, _co, ep, _eo = state
    return sorted(cp) == list(range(8)) and sorted(ep) == list(range(12))


def _valid_state(state) -> bool:
    """A decoded packet must represent a physically possible 3x3 state."""
    if not _plausible(state):
        return False
    cp, co, ep, eo = state
    if sum(co) % 3 or sum(eo) % 2:
        return False

    def parity(permutation):
        return sum(permutation[i] > permutation[j]
                   for i in range(len(permutation))
                   for j in range(i + 1, len(permutation))) % 2

    return parity(cp) == parity(ep)


def _transition_ok(prev_raw: bytes, raw: bytes, face: str, times: int,
                   decode) -> bool:
    """Does `decode(prev)` transformed by the move equal `decode(raw)`?"""
    try:
        state = decode(prev_raw)
        target = decode(raw)
    except (IndexError, ValueError):
        return False
    if not _valid_state(state) or not _valid_state(target):
        return False
    state = apply_face_move(*state, face, times)
    return state == tuple(target)


def detect_profile(prev_raw: bytes, raw: bytes, plaintext=False):
    """Decide which decoding the connected cube uses.

    Checks whether the reported move transforms the previous packet's state
    into this packet's state under the standard decoding, under the clone
    decoding, or under neither (a dropped packet, say).  Returns "std",
    "clone" or None when there is not enough evidence.
    """
    if prev_raw is None:
        return None
    if not plaintext:
        prev_raw = plaintext_packet(prev_raw)
        raw = plaintext_packet(raw)
    if prev_raw is None or raw is None:
        return None
    move = parse_move(raw)
    if move is None:
        return None
    times = {1: 1, 2: 2, -1: 3, -2: 2}[move[1]]
    face = MOVE_FACES[move[0]]
    std_ok = _transition_ok(prev_raw, raw, face, times, parse_state)
    clone_ok = _transition_ok(prev_raw, raw, face, times, parse_state_clone)
    if std_ok and not clone_ok:
        return "std"
    if clone_ok and not std_ok:
        return "clone"
    return None


def is_solved_state(cp, co, ep, eo) -> bool:
    return (cp == list(range(8)) and co == [0] * 8
            and ep == list(range(12)) and eo == [0] * 12)


def state_to_facelets(cp, co, ep, eo) -> str:
    """Convert the parsed state into a 54-char URFDLB facelet string."""
    facelets = [None] * 54
    for i, face in enumerate("URFDLB"):
        facelets[i * 9 + 4] = face  # centers
    for i in range(8):
        piece = cp[i]
        colors = CORNER_COLORS[piece]
        slots = CORNER_FACELETS[i]
        orientation = co[i]
        # The piece's U/D colour lands on facelet slot `orientation`; the
        # other two colours follow it cyclically around the corner.
        for n in range(3):
            facelets[slots[n]] = colors[(n - orientation) % 3]
    for i in range(12):
        piece = ep[i]
        colors = EDGE_COLORS[piece]
        slots = EDGE_FACELETS[i]
        if eo[i]:
            facelets[slots[0]] = colors[1]
            facelets[slots[1]] = colors[0]
        else:
            facelets[slots[0]] = colors[0]
            facelets[slots[1]] = colors[1]
    return "".join(facelets)


# ---------------------------------------------------------------- Qt glue

class Move:
    """A single move reported by the cube."""

    __slots__ = ("face", "amount", "notation", "time")

    def __init__(self, face: int, amount: int, notation: str, time: float):
        self.face = face
        self.amount = amount
        self.notation = notation
        self.time = time

    def __repr__(self):
        return "Move({!r}, t={:.2f})".format(self.notation, self.time)


class CubeState:
    """Full cube state as parsed from a packet."""

    __slots__ = ("cp", "co", "ep", "eo", "time")

    def __init__(self, cp, co, ep, eo, time):
        self.cp = cp
        self.co = co
        self.ep = ep
        self.eo = eo
        self.time = time

    @property
    def solved(self) -> bool:
        return is_solved_state(self.cp, self.co, self.ep, self.eo)

    def facelets(self) -> str:
        return state_to_facelets(self.cp, self.co, self.ep, self.eo)


def parse_packet(raw: bytes, profile: str = "std", plaintext=False):
    """Parse one 20-byte notification into (Move, CubeState).

    Handles 0xA7 decryption transparently.  Returns (None, None) if the
    packet does not look like a state packet.  `profile` selects the state
    decoding: "std" for standard Giiker cubes, "clone" for cubes following
    the clone encoding (auto-detected via detect_profile).
    """
    if plaintext:
        if len(raw) != MESSAGE_LENGTH:
            return None, None
    else:
        raw = plaintext_packet(raw)
        if raw is None:
            return None, None
    now = time.monotonic()   # durations are differences of these timestamps
    move = parse_move(raw)
    if move is None:
        move = None
    else:
        move = Move(move[0], move[1], move[2], now)
    try:
        if profile == "clone":
            cp, co, ep, eo = parse_state_clone(raw)
        else:
            cp, co, ep, eo = parse_state(raw)
    except (IndexError, ValueError):
        return None, None
    if not _valid_state((cp, co, ep, eo)):
        return move, None
    state = CubeState(cp, co, ep, eo, now)
    return move, state


def trace_packet(raw: bytes, move, state):
    """Append one packet to ble_trace.log (only when ENIGMA_BLE_TRACE is set).

    Debug aid for real cubes: one line per packet with the decrypted packet
    bytes, the move the cube reported and the facelet state derived from it.
    """
    if not os.environ.get("ENIGMA_BLE_TRACE"):
        return
    try:
        enc = is_encrypted(raw)
        plain = decrypt_packet(raw) if enc else raw
        line = "{} {} {} move={} state={}\n".format(
            time.strftime("%H:%M:%S"), "enc" if enc else "plain", plain.hex(),
            move.notation if move is not None else "-",
            state.facelets() if state is not None else "-")
        with open("ble_trace.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:  # noqa: BLE001 - tracing must never break the link
        pass


class GiikerWorker(QThread):
    """Runs its own asyncio loop and talks to the cube over BLE.

    Signals (all emitted on the main thread):
        device_found(name, address)      - during scan
        connected(name, address)         - after a successful connect
        disconnected()                   - link lost or disconnected
        move_received(Move)              - every move the cube reports
        state_received(CubeState)        - full state after every move
        error(str)                       - human-readable error
    """

    device_found = pyqtSignal(str, str)
    device_found_detailed = pyqtSignal(str, str, bool)
    scan_finished = pyqtSignal()
    connected = pyqtSignal(str, str)
    disconnected = pyqtSignal()
    move_received = pyqtSignal(object)
    state_received = pyqtSignal(object)
    profile_detected = pyqtSignal(str, str)
    error = pyqtSignal(str)
    reconnecting = pyqtSignal(int)
    connection_stage = pyqtSignal(str)

    def __init__(self, parent=None, known_addresses=()):
        super().__init__(parent)
        self._loop = None
        self._client = None
        self._last_raw = None
        self._connected = False
        self._address = None
        self._candidates = {}   # address -> BleakDevice from the last scan
        self._quiet_connect = False
        self._connect_pending = False   # guards against double connects
        self._connect_task = None
        self._scanner = None        # active BleakScanner (continuous scan)
        self._scan_requested = False
        self._scan_restarting = False
        self._reported_names = {}   # address -> latest useful name this scan
        self._profile = None         # withheld until the packet layout is known
        self._state_published = False
        self._want_connection = False
        self._reconnect_task = None
        self._stopping = False
        self._known_cubes = {str(address).casefold(): "Giiker"
                             for address in known_addresses if address}
        self._scan_lock = asyncio.Lock()
        self._restart_lock = asyncio.Lock()

    # ---- commands (called from the main thread)

    def scan_start(self):
        """Start one continuous scan: devices stream out via device_found
        as soon as they advertise, until scan_stop()."""
        if not self._loop_ready():
            self.error.emit(tr("ble_worker_unavailable"))
            return
        self._scan_requested = True
        # The *_async methods are coroutines: passing them to
        # call_soon_threadsafe only creates the coroutine object and never
        # runs it. Schedule them with create_task instead.
        try:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._scan_start_async()))
        except RuntimeError as e:
            self.error.emit(tr("ble_discovery_failed") % e)

    def scan_stop(self):
        """Stop the continuous scan (safe to call when not scanning)."""
        self._scan_requested = False
        if not self._loop_ready():
            return
        try:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._scan_stop_async()))
        except RuntimeError:
            pass

    def scan_restart(self):
        """Restart discovery in sequence so Windows never has two scans."""
        if not self._loop_ready():
            self.error.emit(tr("ble_worker_unavailable"))
            return
        self._scan_requested = True
        try:
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._scan_restart_async()))
        except RuntimeError as e:
            self.error.emit(tr("ble_discovery_failed") % e)

    def connect_to(self, address: str, quiet: bool = False, profile=None):
        self._want_connection = True
        self._address = address
        self._last_raw = None
        self._profile = profile if profile in ("std", "clone") else None
        self._state_published = False
        self._quiet_connect = quiet
        if not self._loop_ready():
            self.error.emit(tr("ble_worker_unavailable"))
            return
        def _queue_connect():
            async def replace_reconnect():
                task, self._reconnect_task = self._reconnect_task, None
                if task is not None and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                if self._connect_task is None or self._connect_task.done():
                    self._connect_task = self._loop.create_task(self._connect_async(address))
            self._loop.create_task(replace_reconnect())
        try:
            self._loop.call_soon_threadsafe(_queue_connect)
        except RuntimeError as e:
            self.error.emit(tr("ble_connection_failed") % e)

    def _loop_ready(self):
        loop = self._loop
        # QThread.isRunning() can briefly lag the worker's asyncio startup
        # on Windows. The loop itself is the authority: commands scheduled
        # before run_forever() are safe, but require is_running() here so a
        # stale, already-closed worker can never masquerade as ready.
        return loop is not None and not loop.is_closed() and loop.is_running()

    def _wait_for_loop(self, timeout=2.0):
        """Block until run() has created the event loop (or give up).

        Callers start the QThread and immediately talk to it; without this the
        call_soon_threadsafe below can race the loop's creation.
        """
        deadline = time.time() + timeout
        while not self._loop_ready() and time.time() < deadline:
            time.sleep(0.01)
        return self._loop_ready()

    def disconnect(self):
        self._want_connection = False
        if self._loop_ready():
            def cancel_and_disconnect():
                if self._reconnect_task is not None:
                    self._reconnect_task.cancel()
                    self._reconnect_task = None
                if self._connect_task is not None:
                    self._connect_task.cancel()
                self._loop.create_task(self._disconnect_async())
            self._loop.call_soon_threadsafe(cancel_and_disconnect)

    # ---- thread / asyncio plumbing

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def stop(self):
        """Stop the worker thread cleanly (called from the main thread)."""
        self._stopping = True
        self._want_connection = False
        if self._loop is None:
            if self.isRunning():
                self.terminate()
                self.wait(1000)
            return
        self._scan_requested = False
        try:
            if self._loop.is_closed():
                raise RuntimeError("BLE event loop is already closed")
            self._loop.call_soon_threadsafe(self._shutdown_async)
        except RuntimeError:
            # A half-started worker can outlive its event loop. The caller
            # will still wait and use terminate() as the last resort below.
            pass
        # _shutdown_async schedules loop.stop(); run() then closes the loop.
        # wait() belongs to the caller (closeEvent uses wait(2000)).
        self.wait(3000)
        if self.isRunning():
            # Last resort: never let Qt see a still-running QThread destroyed
            # ("QThread: Destroyed while thread is still running" is qFatal).
            self.terminate()
            self.wait(1000)

    def _shutdown_async(self):
        # Teardown and loop stop must be ONE task: stopping the loop right
        # away would never run a task scheduled next to it, leaving the BLE
        # client connected at the OS level.
        async def _shutdown():
            try:
                tasks = [t for t in (self._connect_task, self._reconnect_task)
                         if t is not None and not t.done()]
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                if self._client is not None:
                    await self._disconnect_async()
                if self._scanner is not None:
                    await self._scan_stop_async()
            finally:
                self._loop.stop()
        self._loop.create_task(_shutdown())

    # ---- asyncio coroutines

    async def _scan_start_async(self):
        async with self._scan_lock:
            await self._start_scanner()

    async def _start_scanner(self):
        if not self._scan_requested or self._connected or self._stopping:
            return
        if self._scanner is not None:
            return
        self._reported_names = {}
        # Do not reuse BLEDevice objects from an earlier scan. Windows may
        # rotate private addresses, and cached WinRT devices can be stale.
        self._candidates = {}
        # No service-uuid filter: some Windows adapters deliver
        # advertisements without names or service UUIDs, and a filtered
        # scan then returns nothing at all (seen in the wild).
        try:
            from bleak import BleakScanner  # noqa: PLC0415 - optional dependency
            self._scanner = BleakScanner(detection_callback=self._on_detect,
                                         scanning_mode="active")
            await self._scanner.start()
        except Exception as e:  # noqa: BLE001 - report to the UI
            import traceback
            traceback.print_exc()
            failed, self._scanner = self._scanner, None
            if failed is not None:
                try:
                    await asyncio.wait_for(failed.stop(), timeout=3.0)
                except Exception:
                    pass
            self.error.emit(tr("ble_discovery_failed") % e)
            self.scan_finished.emit()

    async def _scan_stop_async(self, notify=True):
        async with self._scan_lock:
            await self._stop_scanner(notify)

    async def _stop_scanner(self, notify=True):
        scanner, self._scanner = self._scanner, None
        if scanner is None:
            return
        try:
            await scanner.stop()
        except Exception:  # noqa: BLE001 - best effort
            import traceback
            traceback.print_exc()
        if notify:
            self.scan_finished.emit()

    async def _scan_restart_async(self):
        async with self._restart_lock:
            if not self._scan_requested or self._stopping:
                return
            await self._restart_scanner()

    async def _restart_scanner(self):
        # A remembered address is reconnected in the background at startup.
        # Cancel that attempt before discovery: on Windows, the connection
        # task can otherwise stop the scanner just after the picker starts.
        self._scan_restarting = True
        try:
            recovery, self._reconnect_task = self._reconnect_task, None
            if recovery is not None and not recovery.done():
                recovery.cancel()
                await asyncio.gather(recovery, return_exceptions=True)
            task = self._connect_task
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await self._scan_stop_async(notify=False)
            if self._scan_requested and not self._connected:
                await self._scan_start_async()
        finally:
            self._scan_restarting = False

    def _on_detect(self, device, adv):
        """Keep the latest device/name and report newly useful scan data.

        The first advertisement can omit its scan response (and local name),
        so a later callback for the same address must be allowed to upgrade
        the placeholder in the device picker.
        """
        address = device.address
        name = (adv.local_name or device.name or "").strip()
        # Keep the bleak device object: on WinRT, connecting by a bare
        # address only works right after the device was seen, while the
        # object from a live scan connects reliably.
        key = address.casefold()
        is_cube = is_cube_advertisement(name, adv) or key in self._known_cubes
        if not is_cube:
            return
        # Keep recognition across nameless packets and scanner restarts,
        # but only display a remembered cube after a live advertisement.
        display_name = name if is_cube_advertisement(name) else self._known_cubes.get(key, "Giiker")
        self._known_cubes[key] = display_name
        self._candidates[address] = device
        previous = self._reported_names.get(address)
        if previous == (display_name, is_cube):
            return
        self._reported_names[address] = (display_name, is_cube)
        self.device_found.emit(display_name, address)
        self.device_found_detailed.emit(display_name, address, is_cube)

    async def _connect_async(self, address, automatic=False):
        # A double-click in the scan dialog schedules _connect_async twice;
        # without this guard both tasks run and leak a BLE client.
        if self._connect_pending:
            return
        # A link can disappear before Bleak delivers its disconnected
        # callback. Do not let that stale client object block reconnects.
        if self._client is not None:
            if getattr(self._client, "is_connected", False):
                return
            self._client = None
            self._connected = False
        self._connect_pending = True
        self._last_raw = None
        self._state_published = False
        try:
            from bleak import BleakClient, BleakScanner  # noqa: PLC0415 - optional dependency
            # Stop discovery before connecting. On Windows, starting a GATT
            # connection while the adapter is still scanning often times out.
            if self._scanner is not None:
                await self._scan_stop_async(notify=False)
            # Prefer the device object captured during the scan (WinRT
            # connects it reliably); fall back to the raw address.
            device = self._candidates.get(address)
            if automatic or device is None:
                self.connection_stage.emit("ble_stage_discovery")
                device = await BleakScanner.find_device_by_address(
                    address, timeout=5.0, scanning_mode="active")
                if not self._want_connection:
                    return
                if device is None:
                    if automatic:
                        return
                    raise RuntimeError(tr("ble_scan_empty"))
            def new_client(target, cached):
                return BleakClient(target, timeout=8.0, services=[SERVICE_UUID],
                                   winrt={"use_cached_services": cached},
                                   disconnected_callback=self._on_link_lost)
            async def initialize(client):
                self.connection_stage.emit("ble_stage_connect")
                await asyncio.wait_for(client.connect(timeout=8.0), timeout=10.0)
                self.connection_stage.emit("ble_stage_subscribe")
                await asyncio.wait_for(client.start_notify(
                    CHARACTERISTIC_UUID,
                    lambda characteristic, data, owner=client:
                        self._on_notification(characteristic, data)
                        if self._client is owner else None), timeout=5.0)
            client = new_client(device, cached=True)
            # Keep ownership immediately, including while connect() is in
            # flight. If it fails, the exception path can release this
            # partially initialized WinRT client before the next attempt.
            self._client = client
            try:
                await initialize(client)
            except Exception as first_error:
                # WinRT device objects can go stale between an advertisement
                # and opening GATT. Resolve the address from a fresh scan and
                # retry once even when the first attempt used a scan result.
                await self._discard(client)
                self._client = None
                self.connection_stage.emit("ble_stage_retry")
                match = await BleakScanner.find_device_by_address(
                    address, timeout=6.0, scanning_mode="active")
                if match is None:
                    raise first_error
                device = match
                client = new_client(device, cached=False)
                self._client = client
                await initialize(client)
            # bleak >=0.20 dropped BleakClient._device_info; the scanned
            # device object carries the name.
            name = getattr(device, "name", None) if device is not None else None
            if not name:
                name = getattr(getattr(client, "_device_info", None), "name", None)
            self._device_name = name or "Cube"
            if self._stopping or not self._want_connection or self._client is not client:
                raise asyncio.CancelledError()
            if not getattr(client, "is_connected", False):
                raise RuntimeError("Connection was lost during initialization")
            self._connected = True
            self.connected.emit(self._device_name, address)
            # Grab the current state right away: many firmwares stay silent
            # on subscribe, and without a first packet the profile detector
            # has no baseline state to check transitions against (the first
            # turns would then be decoded with the wrong profile).
            try:
                data = await asyncio.wait_for(client.read_gatt_char(CHARACTERISTIC_UUID), timeout=1.5)
                if data:
                    self._on_notification(CHARACTERISTIC_UUID,
                                          bytearray(data))
            except Exception:  # noqa: BLE001 - a read is best effort
                pass
            if self._stopping or not self._want_connection or self._client is not client:
                raise asyncio.CancelledError()
            if not getattr(client, "is_connected", False):
                raise RuntimeError("Connection was lost during initialization")
        except asyncio.CancelledError:
            client, self._client = self._client, None
            self._connected = False
            if client is not None:
                await self._discard(client)
            raise
        except Exception as e:  # noqa: BLE001 - report to the UI
            # Drop a client that connected but failed at start_notify: the
            # guard above would otherwise block every future connect.
            was_connected, self._connected = self._connected, False
            client, self._client = self._client, None
            if client is not None:
                # Finish GATT teardown before restarting discovery. Starting
                # a WinRT scan while a failed client is still disconnecting
                # can leave the adapter stuck until the next manual retry.
                await self._discard(client)
            if not automatic and not getattr(self, "_quiet_connect", False):
                self.error.emit(tr("ble_connection_failed") % e)
            if not automatic or was_connected:
                self.disconnected.emit()
        finally:
            self._connect_pending = False
            if self._connect_task is asyncio.current_task():
                self._connect_task = None
            # If connecting from the picker fails, discovery should resume
            # in that same picker so the user doesn't need a second search.
            if (self._scan_requested and not self._scan_restarting
                    and not self._connected and self._scanner is None):
                self._loop.create_task(self._scan_start_async())

    async def _discard(self, client):
        """Disconnect a half-connected client (best effort)."""
        if self._client is client:
            self._client = None
        try:
            await asyncio.wait_for(client.disconnect(), timeout=3.0)
        except Exception:  # noqa: BLE001 - best effort
            pass

    async def _disconnect_async(self):
        client = self._client
        self._client = None
        self._connected = False
        if client is None:
            return
        try:
            await client.stop_notify(CHARACTERISTIC_UUID)
        except Exception:  # noqa: BLE001 - best effort
            pass
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001 - best effort
            pass
        self.disconnected.emit()

    def _on_link_lost(self, client):
        """Bleak disconnected_callback: the link dropped unexpectedly (cube
        powered off, out of range).  Runs on a WinRT callback thread, so hop
        to the worker loop that owns the client state."""
        try:
            self._loop.call_soon_threadsafe(lambda: self._handle_link_lost(client))
        except RuntimeError:
            pass  # loop already shut down

    def _handle_link_lost(self, client):
        if client is not self._client:
            return  # stale teardown callbacks must never clear a newer connection
        self._client = None
        self._connected = False
        self.disconnected.emit()
        if (self._want_connection and not self._stopping and self._address
                and (self._reconnect_task is None or self._reconnect_task.done())):
            self._reconnect_task = self._loop.create_task(self._restore_connection(self._address))

    async def _restore_connection(self, address):
        try:
            for attempt, delay in enumerate((1, 3, 8), 1):
                if not self._want_connection or self._stopping or self._address != address:
                    return
                self.reconnecting.emit(attempt)
                await asyncio.sleep(delay)
                if not self._want_connection or self._stopping:
                    return
                await self._connect_async(address, automatic=True)
                if self._connected:
                    return
            self.reconnecting.emit(0)
        except asyncio.CancelledError:
            raise
        finally:
            if self._reconnect_task is asyncio.current_task():
                self._reconnect_task = None

    # ---- notifications

    def _on_notification(self, _characteristic, data: bytearray):
        raw = bytes(data)
        plain = plaintext_packet(raw)
        if plain is None:
            return
        # Filter out repeated packets: state occupies bytes 0..15 and the
        # reported move starts at byte 16. Compare after decryption, since
        # encrypted packets can differ even for the same cube state.
        if self._last_raw is not None and plain[:16] == self._last_raw[:16]:
            return
        prev_raw = self._last_raw
        self._last_raw = plain

        # A move-to-state transition identifies the packet layout. Until then,
        # only publish a state when both decoders agree; never draw an
        # unverified standard decode for a clone cube.
        detected = detect_profile(prev_raw, plain, plaintext=True)
        if detected is not None and self._profile != detected:
            self._profile = detected
            self.profile_detected.emit(self._address or "", detected)

        if self._profile is None:
            std_state = parse_packet(plain, "std", plaintext=True)[1]
            clone_state = parse_packet(plain, "clone", plaintext=True)[1]
            if std_state is not None and clone_state is None:
                self._profile = "std"
                self.profile_detected.emit(self._address or "", self._profile)
            elif clone_state is not None and std_state is None:
                self._profile = "clone"
                self.profile_detected.emit(self._address or "", self._profile)
            elif (std_state is not None and clone_state is not None
                  and std_state.cp == clone_state.cp
                  and std_state.co == clone_state.co
                  and std_state.ep == clone_state.ep
                  and std_state.eo == clone_state.eo):
                state = std_state
            else:
                state = None
        else:
            state = parse_packet(plain, self._profile, plaintext=True)[1]
        if self._profile is not None:
            state = parse_packet(plain, self._profile, plaintext=True)[1]

        # If the profile became known on this packet, publish the preceding
        # state before this move. This lets the UI arm on an exact scramble
        # before handling the first solve move.
        if self._profile is not None and prev_raw is not None and not self._state_published:
            _old_move, old_state = parse_packet(
                prev_raw, self._profile, plaintext=True)
            if old_state is not None:
                self.state_received.emit(old_state)

        move = parse_packet(plain, self._profile or "std",
                            plaintext=True)[0] if state is not None else None
        trace_packet(raw, move, state if self._profile is not None else None)
        if move is not None:
            self.move_received.emit(move)
        if state is not None:
            self.state_received.emit(state)
        self._state_published = state is not None
