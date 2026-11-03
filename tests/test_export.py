import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from enigma_timer import storage  # noqa: E402
from enigma_timer.stats import Solve, OK, PLUS2, DNF  # noqa: E402


class ExportCsTimerTest(unittest.TestCase):
    def test_roundtrip(self):
        solves = [
            Solve(12340, OK, "R U R' U'", 1600000000, "hi"),
            Solve(11000, PLUS2, "F2 D'", 1600000001),
            Solve(9000, DNF, "L", 1600000002, "oops"),
            Solve(0, DNF, "", 1600000003),  # DNF without a raw time
        ]
        s = storage.Session("main", "444", solves)
        text = storage.export_cstimer(s)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "export.txt")
        self.assertEqual(storage.export_cstimer(s, p), text)
        with open(p, encoding="utf-8") as f:
            imported = storage.import_cstimer(f.name if False else p)
        self.assertEqual(len(imported), 1)
        back = imported[0]
        self.assertEqual(back.puzzle, "444")
        self.assertEqual(len(back.solves), len(solves))
        for a, b in zip(solves, back.solves):
            self.assertEqual(a.ms, b.ms)
            self.assertEqual(a.penalty, b.penalty)
            self.assertEqual(a.scramble, b.scramble)
            self.assertEqual(a.comment, b.comment)
            self.assertEqual(a.date, b.date)

    def test_format_shape(self):
        s = storage.Session("my sess", "333", [Solve(12345, OK, "R U", 1700000000)])
        data = json.loads(storage.export_cstimer(s))
        self.assertIn("session1", data)
        self.assertEqual(data["session1"][0][0], [0, 12345])
        self.assertEqual(data["session1"][0][1], "R U")
        sd = json.loads(data["properties"]["sessionData"])
        self.assertEqual(sd["1"]["name"], "my sess")
        self.assertEqual(sd["1"]["opt"]["scrType"], "333")

    def test_puzzle_mapping(self):
        for pid, expected in (("pyram", "pyr"), ("skewb", "skb"), ("minx", "mgm"),
                              ("clock", "clk"), ("333bf", "333bf"), ("sq1", "sq1")):
            s = storage.Session("x", pid, [Solve(1000, OK, "", 0)])
            data = json.loads(storage.export_cstimer(s))
            sd = json.loads(data["properties"]["sessionData"])
            self.assertEqual(sd["1"]["opt"]["scrType"], expected, pid)

    def test_empty_session(self):
        s = storage.Session("empty", "333", [])
        data = json.loads(storage.export_cstimer(s))
        self.assertEqual(data["session1"], [])

    def test_multiline_scramble_flattened(self):
        # minx scrambles contain newlines; csTimer keeps them on one line
        s = storage.Session("x", "minx", [Solve(5000, OK, "a\nb\nc", 0)])
        data = json.loads(storage.export_cstimer(s))
        self.assertEqual(data["session1"][0][1], "a b c")


if __name__ == "__main__":
    unittest.main()
