# -*- coding: utf-8 -*-
"""Learning path, lessons and spaced-repetition progress for the Training section.

Every case has a Leitner "box" (0..5). Rating a case in the trainer moves it
between boxes and schedules the next review:

    box:       0      1      2      3      4       5
    review:    now    1 day  3 days 7 days 16 days 35 days

A case counts as *learned* from box 3. New cases are introduced in order,
a few at a time, so the learner is never flooded.
"""

import random
import time

from .algs import CASES, SET_BY_ID

DAY = 86400.0
INTERVALS = [0, 1 * DAY, 3 * DAY, 7 * DAY, 16 * DAY, 35 * DAY]
LEARNED_BOX = 3
MAX_BOX = len(INTERVALS) - 1

NEW, LEARNING, LEARNED = 0, 1, 2

AGAIN, HARD, GOOD = 0, 1, 2

# Duolingo-style XP: every rated card earns experience, a brand-new case a bonus
XP_RATES = {AGAIN: 2, HARD: 5, GOOD: 10}
XP_NEW_BONUS = 5
XP_LESSON = 20


# ---------------------------------------------------------------------------
# Learning path
# ---------------------------------------------------------------------------

BEGINNER, INTERMEDIATE, ADVANCED = "beginner", "intermediate", "advanced"
TIER_NAMES = {
    BEGINNER: ("Beginner", "Новичок"),
    INTERMEDIATE: ("Intermediate", "Продвинутый"),
    ADVANCED: ("Pro", "Профи"),
}


class Level(object):
    def __init__(self, lid, name, subtitle, set_id=None, lesson=None, tier=BEGINNER):
        self.id = lid
        self.name = name            # (en, ru)
        self.subtitle = subtitle    # (en, ru)
        self.set_id = set_id
        self.lesson = lesson        # lesson id or None
        self.tier = tier

    @property
    def cases(self):
        return SET_BY_ID[self.set_id].cases if self.set_id else []


def _lv(*args, **kw):
    lv = Level(*args, **kw)
    LEVEL_BY_ID[lv.id] = lv
    return lv


LEVEL_BY_ID = {}

L333 = [
    _lv("notation", ("Notation", "Нотация"),
        ("How to read algorithms", "Как читать алгоритмы"), lesson="notation"),
    _lv("beginner", ("Beginner method", "Метод для начинающих"),
        ("Solve the cube for the first time", "Собери куб в первый раз"),
        set_id="beginner", lesson="beginner"),
    _lv("cross", ("Cross planning", "Крест: планирование"),
        ("Plan the whole cross in inspection", "Весь крест — на инспекции"),
        lesson="cross", tier=INTERMEDIATE),
    _lv("fingertricks", ("Finger tricks", "Фингертрики"),
        ("Turn with fingers, not wrists", "Крути пальцами, а не кистями"),
        lesson="fingertricks", tier=INTERMEDIATE),
    _lv("oll2", ("2-look OLL", "OLL в 2 этапа"),
        ("10 algorithms for a yellow top", "10 алгоритмов для жёлтого верха"),
        set_id="oll2", lesson="cfop", tier=INTERMEDIATE),
    _lv("pll2", ("2-look PLL", "PLL в 2 этапа"),
        ("6 algorithms to finish the cube", "6 алгоритмов, чтобы закончить куб"),
        set_id="pll2", tier=INTERMEDIATE),
    _lv("f2l", ("F2L", "F2L"),
        ("41 cases, two layers at once", "41 случай: два слоя сразу"),
        set_id="f2l", lesson="f2l", tier=INTERMEDIATE),
    _lv("lookahead", ("Look-ahead", "Look-ahead: без пауз"),
        ("From 30 to 15 seconds", "От 30 к 15 секундам"), lesson="lookahead", tier=INTERMEDIATE),
    _lv("oll", ("Full OLL", "Полный OLL"),
        ("57 cases, last layer orientation in one look",
         "57 случаев: ориентация за один взгляд"), set_id="oll", tier=ADVANCED),
    _lv("pll", ("Full PLL", "Полный PLL"),
        ("21 cases, last layer in one look", "21 случай: последний слой за один взгляд"),
        set_id="pll", tier=ADVANCED),
    _lv("roux-cmll", ("Roux: CMLL", "Roux: CMLL"),
        ("Another top method: blocks, CMLL, LSE", "Другой топ-метод: блоки, CMLL, LSE"),
        set_id="333-cmll", lesson="roux", tier=ADVANCED),
]
L222 = [
    _lv("222-notation", ("Notation", "Нотация"), ("Same as the 3x3", "Как на 3x3"),
        lesson="ref:222"),
    _lv("222-beginner", ("Beginner method", "Метод для начинающих"),
        ("Layer by layer, 4 algorithms", "Послойно, 4 алгоритма"),
        set_id="222-beginner", lesson="222-beginner"),
    _lv("222-ortega-oll", ("Ortega: OLL", "Ортега: OLL"), ("7 algorithms", "7 алгоритмов"),
        set_id="222-ortega-oll", lesson="222-ortega", tier=INTERMEDIATE),
    _lv("222-ortega-pbl", ("Ortega: PBL", "Ортега: PBL"), ("6 algorithms", "6 алгоритмов"),
        set_id="222-ortega-pbl", tier=INTERMEDIATE),
    _lv("222-cll", ("CLL", "CLL"), ("40 cases, last layer in one look",
                                     "40 случаев: последний слой за один взгляд"),
        set_id="222-cll", tier=ADVANCED),
]
LBIG = [
    _lv("big-notation", ("Notation", "Нотация"), ("Wide moves and slices", "Широкие ходы и слайсы"),
        lesson="ref:444"),
    _lv("444-reduction", ("Reduction method", "Метод редукции"),
        ("Centres, edges, then 3x3", "Центры, рёбра, затем 3x3"), lesson="444-reduction"),
    _lv("444-parity", ("4x4 parity", "Паритеты 4x4"), ("3 algorithms", "3 алгоритма"),
        set_id="444-parity", tier=INTERMEDIATE),
    _lv("555-edges", ("5x5 and bigger", "5x5 и больше"),
        ("Edge pairing", "Сборка рёбер"), set_id="555-edges", lesson="555-edges",
        tier=INTERMEDIATE),
]
LPYRA = [
    _lv("pyra-notation", ("Notation", "Нотация"), ("Corners and tips", "Вершины и кончики"),
        lesson="ref:pyram"),
    _lv("pyra-beginner", ("Beginner method", "Метод для начинающих"),
        ("Tips, centres, edges", "Вершинки, центры, рёбра"),
        set_id="pyra-beginner", lesson="pyra-beginner"),
    _lv("pyra-l4e", ("L4E", "L4E"), ("36 cases", "36 случаев"), set_id="pyra-l4e",
        lesson="pyra-l4e", tier=ADVANCED),
]
LSKEWB = [
    _lv("skewb-notation", ("Notation", "Нотация"), ("WCA corner moves", "Ходы углами по WCA"),
        lesson="ref:skewb"),
    _lv("skewb-layer", ("Layer method", "Послойный метод"),
        ("2 corner + 16 centre cases", "2 случая углов + 16 центров"),
        set_id="skewb-layer", lesson="skewb-layer", tier=INTERMEDIATE),
]
LMINX = [
    _lv("minx-notation", ("Notation", "Нотация"), ("Faces and Pochmann scrambles",
                                                   "Грани и скрамблы Похмана"), lesson="ref:minx"),
    _lv("minx-beginner", ("Beginner method", "Метод для начинающих"),
        ("Like a 3x3, layer by layer", "Как 3x3, послойно"), lesson="minx-beginner"),
    _lv("minx-ll", ("4-look last layer", "Последний слой в 4 этапа"), ("39 algorithms", "39 алгоритмов"),
        set_id="minx-ll", tier=INTERMEDIATE),
]
LSQ1 = [
    _lv("sq1-notation", ("Notation", "Нотация"), ("(x, y) and the slice", "(x, y) и слайс"),
        lesson="ref:sq1"),
    _lv("sq1-beginner", ("Beginner method", "Метод для начинающих"),
        ("7 algorithms", "7 алгоритмов"), set_id="sq1-beginner", lesson="sq1-beginner"),
]
LCLOCK = [
    _lv("clock-notation", ("Notation", "Нотация"), ("Pins and dials", "Штырьки и колёса"),
        lesson="ref:clock"),
    _lv("clock-beginner", ("Beginner method", "Метод для начинающих"),
        ("Cross, back, corners", "Крест, обратная сторона, углы"), lesson="clock-beginner"),
]
LBLD = [L333[0], _lv("bld-op", ("Old Pochmann", "Old Pochmann"),
                     ("Blindfolded, one piece at a time", "Вслепую, по одной детали"),
                     set_id="bld-op", lesson="bld-op", tier=INTERMEDIATE)]
LOH = [_lv("oh", ("One-handed tips", "Советы для одной руки"), ("Grips and algorithms",
                                                                 "Хваты и алгоритмы"),
           lesson="oh"), L333[2], L333[3], L333[4]]
LFMC = [L333[0], _lv("fmc", ("FMC basics", "Основы FMC"), ("Blocks, skeletons, NISS",
                                                            "Блоки, скелеты, NISS"), lesson="fmc")]

PATHS = {
    "333": L333, "222": L222, "444": LBIG, "555": LBIG, "666": LBIG, "777": LBIG,
    "pyram": LPYRA, "skewb": LSKEWB, "minx": LMINX, "sq1": LSQ1, "clock": LCLOCK,
    "333bf": LBLD, "333oh": LOH, "333fm": LFMC,
}
# order of the puzzles in the Training selector
PATH_ORDER = ["333", "222", "444", "pyram", "skewb", "minx", "sq1", "clock",
              "333bf", "333oh", "333fm"]
PATH_DESCRIPTIONS = {
    "333": ("Learn CFOP, the method used by most speedcubers. Explore Roux as an alternative.",
            "Освой CFOP — основной метод спидкуберов. Для разнообразия попробуй Roux."),
    "222": ("The 2x2 has no edges. Start layer by layer, then learn Ortega and CLL.",
            "У куба 2×2 нет рёбер. Начни с послойной сборки, затем изучи Ortega и CLL."),
    "444": ("Solve the centres and pair the edges, then solve it like a 3x3. Learn the parity cases too.",
            "Собери центры и спарь рёбра, затем реши куб как 3×3. Отдельно изучи паритеты."),
    "pyram": ("Learn the tips and centres, then practise a few edge algorithms.",
              "Освой вершины и центры, затем потренируй несколько алгоритмов для рёбер."),
    "skewb": ("Turn a Skewb by its corners. Start with an intuitive layer, then learn a few algorithms.",
              "Собери один слой интуитивно, затем освой несколько алгоритмов для Скьюба."),
    "minx": ("Solve the Megaminx like a large 3x3, one face at a time.",
             "Собирай мегаминкс по аналогии с большим 3×3 — грань за гранью."),
    "sq1": ("Square-1 changes shape. First return it to a cube, then solve it.",
            "Square-1 меняет форму. Сначала верни ему форму куба, затем собери."),
    "clock": ("Set the pins, turn the dials and bring every clock to 12.",
              "Выставь штырьки, поверни циферблаты и установи все часы на 12."),
    "333bf": ("Memorise the cube, then solve it blindfolded.",
              "Запомни расположение деталей, затем собери куб с закрытыми глазами."),
    "333oh": ("Learn CFOP one-handed, with finger tricks suited to one hand.",
              "Освой CFOP одной рукой и подбери удобные движения пальцами."),
    "333fm": ("Search for the shortest solution and write down your ideas as you go.",
              "Ищи самое короткое решение и записывай найденные варианты."),
}

PATH_NAMES = {
    "333": ("3x3 · Fridrich (CFOP)", "3x3 · Фридрих (CFOP)"),
    "222": ("2x2 · Ortega, CLL", "2x2 · Ортега, CLL"),
    "444": ("4x4–7x7 · Reduction", "4x4–7x7 · Редукция"),
    "pyram": ("Pyraminx", "Пирамидка"),
    "skewb": ("Skewb", "Скьюб"),
    "minx": ("Megaminx", "Мегаминкс"),
    "sq1": ("Square-1", "Square-1"),
    "clock": ("Clock", "Clock"),
    "333bf": ("3x3 blindfolded", "3x3 вслепую"),
    "333oh": ("3x3 one-handed", "3x3 одной рукой"),
    "333fm": ("3x3 fewest moves", "3x3 FMC"),
}
LEVELS = L333   # kept for older code


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

class Progress(object):
    """Wraps the `training` dict stored in data.json."""

    def __init__(self, data):
        self.data = data
        data.setdefault("cases", {})
        data.setdefault("lessons", {})
        data.setdefault("xp", 0)
        data.setdefault("lesson_xp_awarded", [])
        days = data.setdefault("days", {})
        if not isinstance(days, dict):
            # v1 stored "days" as a plain list of active dates (for the
            # streak).  Convert to the v2 dict-of-counts format.
            data["days"] = {d: {"rev": 0, "new": 0, "xp": 0} for d in days}
            days = data["days"]

    # --- per case ------------------------------------------------------
    def _rec(self, cid):
        return self.data["cases"].get(cid)

    def box(self, cid):
        r = self._rec(cid)
        return r["box"] if r else -1

    def status(self, cid):
        r = self._rec(cid)
        if not r:
            return NEW
        return LEARNED if r["box"] >= LEARNED_BOX else LEARNING

    def set_status(self, cid, status, now=None):
        now = now or time.time()
        if status == NEW:
            self.data["cases"].pop(cid, None)
            return
        r = self.data["cases"].setdefault(cid, {"box": 0, "due": now, "seen": 0, "ok": 0})
        if status == LEARNED:
            r["box"] = max(r["box"], LEARNED_BOX)
            r["due"] = now + INTERVALS[r["box"]]
        else:
            r["box"] = min(r["box"], LEARNED_BOX - 1)
            r["due"] = now

    def is_due(self, cid, now=None):
        r = self._rec(cid)
        return bool(r) and r["due"] <= (now or time.time())

    # --- lessons -------------------------------------------------------
    def lesson_done(self, lid):
        return bool(self.data["lessons"].get(lid))

    def set_lesson_done(self, lid, done=True, now=None):
        awarded = self.data.setdefault("lesson_xp_awarded", [])
        self.data["lessons"][lid] = bool(done)
        if done and lid not in awarded:
            self._log_xp(XP_LESSON, time.time() if now is None else now, kind=None)
            awarded.append(lid)

    # --- XP / streaks / today ------------------------------------------
    def _day(self, now=None):
        """YYYY-MM-DD key for "now" (local time)."""
        return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))

    def _bump_day(self, now):
        d = self._day(now)
        days = self.data["days"]
        rec = days.get(d)
        if rec is None:
            rec = days[d] = {"rev": 0, "new": 0, "xp": 0}
        # keep the recent history only (enough for a long streak)
        if len(days) > 400:
            for k in sorted(days)[:-400]:
                del days[k]
        return rec

    def _log_xp(self, amount, now, kind="rev"):
        r = self._bump_day(now)
        r["xp"] += amount
        if kind in ("rev", "new"):
            r[kind] += 1
        self.data["xp"] = self.data.get("xp", 0) + amount

    def rate(self, cid, rating, now=None):
        now = now or time.time()
        fresh = self._rec(cid) is None
        r = self.data["cases"].setdefault(cid, {"box": 0, "due": now, "seen": 0, "ok": 0})
        r["seen"] += 1
        if rating == AGAIN:
            r["box"] = 0
            r["due"] = now
        elif rating == HARD:
            r["box"] = max(1, r["box"])
            r["due"] = now + INTERVALS[r["box"]] / 2.0
            r["ok"] += 1
        else:
            r["box"] = min(MAX_BOX, r["box"] + 1)
            r["due"] = now + INTERVALS[r["box"]]
            r["ok"] += 1
        xp = XP_RATES[rating] + (XP_NEW_BONUS if fresh else 0)
        self._log_xp(xp, now, kind="new" if fresh else "rev")

    def today(self, now=None):
        """(reviews_today, new_today, xp_today)."""
        r = self.data["days"].get(self._day(now)) or {}
        return r.get("rev", 0), r.get("new", 0), r.get("xp", 0)

    def streak(self, now=None):
        """Consecutive days (ending today or yesterday) with any activity."""
        days = self.data["days"]
        if not days:
            return 0
        now = now or time.time()
        d = self._day(now)
        if d not in days:
            d = self._day(now - DAY)
            if d not in days:
                return 0
        n = 0
        cur = time.mktime(time.strptime(d, "%Y-%m-%d"))
        while True:
            n += 1
            cur -= DAY
            if time.strftime("%Y-%m-%d", time.localtime(cur)) not in days:
                return n

    def lesson_xp(self, lid, now=None):
        """Award XP for finishing a lesson (only the first time)."""
        awarded = self.data.setdefault("lesson_xp_awarded", [])
        if lid in awarded:
            return
        self._log_xp(XP_LESSON, time.time() if now is None else now)
        self.data["lessons"][lid] = True
        awarded.append(lid)

    # --- levels --------------------------------------------------------
    def level_counts(self, level):
        """(learned, total) for a level; a lesson-only level counts as 1 item."""
        if not level.set_id:
            return (1 if self.lesson_done(level.lesson) else 0), 1
        cases = level.cases
        return sum(1 for c in cases if self.status(c.id) == LEARNED), len(cases)

    def level_done(self, level):
        a, b = self.level_counts(level)
        return a >= b

    def course_counts(self, path_id):
        """(done, total) over every step of a course (lesson = 1 item, set = its cases)."""
        done = total = 0
        for lv in PATHS.get(path_id, []):
            a, b = self.level_counts(lv)
            done += a
            total += b
        return done, total

    def next_level(self, path="333"):
        for lv in PATHS.get(path, L333):
            if not self.level_done(lv):
                return lv
        return None

    def due_count(self, cases, now=None):
        now = now or time.time()
        return sum(1 for c in cases if self.is_due(c.id, now))


class Trainer(object):
    """Chooses the next case to practise from a list of cases."""

    NEW_PER_SESSION = 4

    def __init__(self, progress, cases, include_learned=True):
        self.progress = progress
        self.cases = list(cases)
        self.include_learned = include_learned
        self.last = None
        self.new_introduced = 0
        self.reviewed = 0

    def next_case(self, now=None):
        now = now or time.time()
        p = self.progress
        pool = [c for c in self.cases if c.id != self.last] or self.cases
        due = [c for c in pool if p.status(c.id) != NEW and p.is_due(c.id, now)
               and (self.include_learned or p.status(c.id) != LEARNED)]
        if due:
            due.sort(key=lambda c: p.data["cases"][c.id]["due"])
            choice = due[0]
        else:
            fresh = [c for c in pool if p.status(c.id) == NEW]
            if fresh and self.new_introduced < self.NEW_PER_SESSION:
                choice = fresh[0]
                self.new_introduced += 1
            else:
                learning = [c for c in pool if p.status(c.id) == LEARNING]
                if learning:
                    choice = min(learning, key=lambda c: (p.box(c.id), random.random()))
                elif fresh:
                    choice = fresh[0]
                else:
                    choice = min(pool, key=lambda c: (p.box(c.id), random.random()))
        self.last = choice.id
        return choice

    def rate(self, case, rating, now=None):
        self.progress.rate(case.id, rating, now)
        self.reviewed += 1


def random_auf():
    return random.choice(["", "U", "U2", "U'"])


def all_case_ids():
    return list(CASES.keys())
