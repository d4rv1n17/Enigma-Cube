import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enigma_timer import learn  # noqa: E402

NOW = time.mktime((2026, 6, 15, 12, 0, 0, 0, 0, -1))
DAY = 86400.0


def stamp(day_offset, hour=12):
    return NOW + day_offset * DAY + (hour - 12) * 3600.0


class ProgressXpTest(unittest.TestCase):
    def setUp(self):
        self.p = learn.Progress({"cases": {}, "lessons": {}})
        self.c = sorted(learn.CASES)[0]

    def test_rate_awards_xp(self):
        self.p.rate(self.c, learn.GOOD, now=NOW)
        rev, new, xp = self.p.today(now=NOW)
        self.assertEqual((rev, new), (0, 1))   # a fresh case counts as new
        self.assertEqual(xp, learn.XP_RATES[learn.GOOD] + learn.XP_NEW_BONUS)
        self.assertEqual(self.p.data["xp"], xp)

    def test_repeat_counts_as_review(self):
        self.p.rate(self.c, learn.GOOD, now=NOW)
        self.p.rate(self.c, learn.GOOD, now=NOW + 60)
        rev, new, xp = self.p.today(now=NOW)
        self.assertEqual((rev, new), (1, 1))

    def test_new_bonus_only_once(self):
        self.p.rate(self.c, learn.GOOD, now=NOW)
        xp_first = self.p.data["xp"]
        self.p.rate(self.c, learn.GOOD, now=NOW + 60)
        self.assertEqual(self.p.data["xp"], xp_first + learn.XP_RATES[learn.GOOD])

    def test_again_pays_less(self):
        self.p.rate(self.c, learn.AGAIN, now=NOW)
        self.assertEqual(self.p.data["xp"], learn.XP_RATES[learn.AGAIN] + learn.XP_NEW_BONUS)

    def test_today_resets_next_day(self):
        self.p.rate(self.c, learn.GOOD, now=NOW)
        rev, new, xp = self.p.today(now=NOW + DAY)
        self.assertEqual((rev, new, xp), (0, 0, 0))


class ProgressStreakTest(unittest.TestCase):
    def setUp(self):
        self.p = learn.Progress({"cases": {}, "lessons": {}})
        self.c = sorted(learn.CASES)[0]

    def test_streak_counts_consecutive_days(self):
        for off in (0, -1, -2):
            self.p.rate(self.c, learn.GOOD, now=NOW + off * DAY)
        self.assertEqual(self.p.streak(now=NOW), 3)

    def test_streak_survives_until_tomorrow(self):
        self.p.rate(self.c, learn.GOOD, now=NOW - DAY)   # active yesterday
        self.assertEqual(self.p.streak(now=NOW), 1)
        # still alive late the same evening...
        self.assertEqual(self.p.streak(now=NOW + 11 * 3600.0), 1)
        # ...but gone the next day (nothing recorded today/yesterday)
        self.assertEqual(self.p.streak(now=NOW + DAY), 0)

    def test_streak_broken_by_gap(self):
        self.p.rate(self.c, learn.GOOD, now=NOW)
        self.p.rate(self.c, learn.GOOD, now=NOW - 2 * DAY)
        self.assertEqual(self.p.streak(now=NOW), 1)


class ProgressLegacyTest(unittest.TestCase):
    def test_legacy_day_list_converted(self):
        # v1 stored "days" as a list of active dates; opening that data in a
        # new build must not crash (it crashed the whole app via qFatal).
        p = learn.Progress({"cases": {}, "lessons": {},
                            "days": ["2026-06-13", "2026-06-14"]})
        self.assertIsInstance(p.data["days"], dict)
        self.assertEqual(self_day_counts(p, "2026-06-13"), (0, 0, 0))
        self.assertEqual(p.data["days"]["2026-06-14"], {"rev": 0, "new": 0, "xp": 0})

    def test_lesson_xp_once(self):
        p = learn.Progress({"cases": {}, "lessons": {}})
        p.set_lesson_done("l1", now=NOW)
        self.assertEqual(p.data["xp"], learn.XP_LESSON)
        p.set_lesson_done("l1", now=NOW + 1)
        self.assertEqual(p.data["xp"], learn.XP_LESSON)

    def test_day_history_pruned(self):
        p = learn.Progress({"cases": {}, "lessons": {}})
        for i in range(405):
            p.rate("x%d" % i, learn.GOOD, now=NOW - i * DAY)
        self.assertLessEqual(len(p.data["days"]), 400)


def self_day_counts(p, day):
    r = p.data["days"].get(day) or {}
    return r.get("rev", 0), r.get("new", 0), r.get("xp", 0)


if __name__ == "__main__":
    unittest.main()
