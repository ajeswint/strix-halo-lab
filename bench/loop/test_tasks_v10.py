#!/usr/bin/env python3
"""CPU tests for the v10 held-out set and mutant controls (no GPU, no model, no server).

  python3 -m unittest bench/loop/test_tasks_v10.py -v

- shape: 90 tasks, v10_ ids, balanced across the four v7/v8 families (23/22/22/23);
- check_tasks: clean pass on all 90 references (empty fails, seed 10000+NN, caps, timing);
- mutants: every mutant in tasks_v10_mutants.py applies exactly once and FAILS run.grade.
"""
import concurrent.futures as cf
import contextlib
import io
import os
import shutil
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402
import memring  # noqa: E402
import check_tasks  # noqa: E402
import tasks_v10  # noqa: E402
import tasks_v10_mutants  # noqa: E402

HAVE_BWRAP = shutil.which("bwrap") is not None
FAMILY_COUNTS = {"formats": 23, "number_theory": 22, "graphs_geometry": 22, "simulation_dp": 23}


class TestTaskFile(unittest.TestCase):
    def test_shape(self):
        ts = tasks_v10.TASKS
        self.assertEqual(len(ts), 90)
        self.assertEqual([t["id"][:7] for t in ts], [f"v10_{i:02d}_" for i in range(1, 91)])
        self.assertEqual(len({t["id"] for t in ts}), 90)
        for i, t in enumerate(ts, 1):
            seeds = [ln for ln in t["tests"].splitlines() if ln.startswith("random.seed(")]
            self.assertEqual(seeds, [f"random.seed({10000 + i})"], t["id"])
            self.assertIn(t["id"], memring.FAMILIES["v10"], t["id"])
        counts = {}
        for t in ts:
            fam = memring.FAMILIES["v10"][t["id"]]
            counts[fam] = counts.get(fam, 0) + 1
        self.assertEqual(counts, FAMILY_COUNTS)

    @unittest.skipUnless(HAVE_BWRAP, "needs bwrap")
    def test_task_65_welsh_powell_coloring(self):
        t = [x for x in tasks_v10.TASKS if x["id"] == "v10_65_welsh_powell_coloring"]
        self.assertEqual(len(t), 1)
        task = t[0]
        self.assertEqual(memring.FAMILIES["v10"]["v10_65_welsh_powell_coloring"], "graphs_geometry")
        ok, err = run.grade(task["ref"], task["tests"])
        self.assertTrue(ok, err)

    @unittest.skipUnless(HAVE_BWRAP, "needs bwrap")
    def test_check_tasks_clean(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check_tasks.check(list(tasks_v10.TASKS), "v10")
        self.assertEqual(rc, 0, buf.getvalue()[-3000:])


@unittest.skipUnless(HAVE_BWRAP, "needs bwrap")
class TestMutants(unittest.TestCase):
    def test_every_mutant_fails_the_grader(self):
        by = {t["id"]: t for t in tasks_v10.TASKS}
        self.assertEqual(set(tasks_v10_mutants.MUTANTS), set(by))
        jobs = []
        for tid, ms in tasks_v10_mutants.MUTANTS.items():
            self.assertGreaterEqual(len(ms), 2, tid)
            for desc, old, new in ms:
                self.assertEqual(by[tid]["ref"].count(old), 1, (tid, desc, "old text must match exactly once"))
                code = by[tid]["ref"].replace(old, new)
                compile(code, tid, "exec")  # must be valid Python syntax
                jobs.append((tid, desc, code))
        with cf.ThreadPoolExecutor(8) as pool:
            res = list(pool.map(lambda j: run.grade(j[2], by[j[0]]["tests"]), jobs))
        survivors = [(j[0], j[1]) for j, (ok, _) in zip(jobs, res) if ok]
        self.assertEqual(survivors, [])


if __name__ == "__main__":
    unittest.main()
