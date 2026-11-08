#!/usr/bin/env python3
"""CPU tests for the v9 held-out set and its frozen protocol inputs (no GPU, no model, no server).

  python3 bench/loop/test_tasks_v9.py -v

- the task file: 30 tasks, v9_ ids, split held_out, explicit balanced families, one seed line each, not in run.SETS,
  accepted by the held-out gate (memring.require_held_out_eval_set / run.load_set);
- check_tasks.check() is clean (refs pass 7 seeds under the reference cap, empty fails, timing, prompt size, names);
- grader boundary checks: every mutant in tasks_v9_mutants.py applies exactly once and FAILS run.grade;
- novelty: the audit flags every known reskin inside v0-v8, gives no v9 task a HARD flag, every REVIEW flag has a
  written verdict, no verdict is stale, and a planted near-duplicate is caught;
- leak guards: every canned lesson of the deterministic distiller passes leak_check against v9 (otherwise memory on
  would be filtered to nothing), and a lesson quoting v9 is refused;
- freeze: the sha256 of the task, mutant and audit files match bench/loop/memeval_v9_freeze.json.
Grading tests need bwrap (as run.py's selftest does); they skip without it.
"""
import ast, contextlib, hashlib, inspect, io, json, os, shutil, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402
import memring  # noqa: E402
import check_tasks  # noqa: E402
import novelty_audit  # noqa: E402
import tasks_v9  # noqa: E402
import tasks_v9_mutants  # noqa: E402

FREEZE = os.path.join(HERE, "memeval_v9_freeze.json")
HAVE_BWRAP = shutil.which("bwrap") is not None
FAMILY_COUNTS = {"formats": 8, "number_theory": 7, "graphs_geometry": 7, "simulation_dp": 8}


def sha256_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestTaskFile(unittest.TestCase):
    def test_shape(self):
        ts = tasks_v9.TASKS
        self.assertEqual(len(ts), 30)
        self.assertEqual([t["id"][:6] for t in ts], [f"v9_{i:02d}_" for i in range(1, 31)])
        self.assertEqual(len({t["id"] for t in ts}), 30)
        for t in ts:
            self.assertEqual(t["split"], "held_out", t["id"])
            self.assertIn(t["family"], memring.KNOWN_FAMILIES, t["id"])
            seeds = [ln for ln in t["tests"].splitlines() if ln.startswith("random.seed(")]
            self.assertEqual(seeds, [f"random.seed({9000 + int(t['id'][3:5])})"], t["id"])
        counts = {}
        for t in ts:
            counts[t["family"]] = counts.get(t["family"], 0) + 1
        self.assertEqual(counts, FAMILY_COUNTS)

    def test_not_registered_as_train_and_gate_accepts(self):
        self.assertNotIn("v9", run.SETS)
        self.assertNotIn("v9", memring.TRAIN_SETS)
        self.assertEqual(run.set_split("v9"), "held_out")
        ts = run.load_set("v9")
        self.assertEqual(memring.require_held_out_eval_set("v9", ts), (True, None))
        self.assertFalse(set(t["id"] for t in ts) & memring.train_task_ids())
        for t in ts:   # the explicit family is what retrieval ranks on; no FAMILIES-map entry overrides it
            self.assertEqual(memring.task_family(t["id"], "v9", t["family"]), t["family"])

    @unittest.skipUnless(HAVE_BWRAP, "needs bwrap")
    def test_check_tasks_clean(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = check_tasks.check(list(tasks_v9.TASKS), None)
        self.assertEqual(rc, 0, buf.getvalue()[-3000:])


@unittest.skipUnless(HAVE_BWRAP, "needs bwrap")
class TestMutants(unittest.TestCase):
    def test_every_mutant_fails_the_grader(self):
        import concurrent.futures as cf
        by = {t["id"]: t for t in tasks_v9.TASKS}
        self.assertEqual(set(tasks_v9_mutants.MUTANTS), set(by))
        jobs = []
        for tid, ms in tasks_v9_mutants.MUTANTS.items():
            self.assertGreaterEqual(len(ms), 2, tid)
            for desc, old, new in ms:
                self.assertEqual(by[tid]["ref"].count(old), 1, (tid, desc))
                code = by[tid]["ref"].replace(old, new)
                compile(code, tid, "exec")   # a kill by SyntaxError would test nothing
                jobs.append((tid, desc, code))
        with cf.ThreadPoolExecutor(8) as pool:
            res = list(pool.map(lambda j: run.grade(j[2], by[j[0]]["tests"]), jobs))
        survivors = [(j[0], j[1]) for j, (ok, _) in zip(jobs, res) if ok]
        self.assertEqual(survivors, [])


class TestNovelty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priors = novelty_audit.prior_tasks()
        cls.rows = novelty_audit.audit(run.load_set("v9"), cls.priors)

    def test_compares_against_all_240_prior_tasks(self):
        self.assertEqual(len(self.priors), 240)
        self.assertEqual({r["n_priors"] for r in self.rows}, {240})

    def test_calibration_flags_every_known_reuse(self):
        for a, b, m, fl in novelty_audit.calibrate(self.priors):
            self.assertTrue(fl, (a, b, m))

    def test_no_hard_flag_and_every_review_flag_has_a_verdict(self):
        self.assertEqual([(r["id"], [p for p, _, _ in r["hard"]]) for r in self.rows if r["hard"]], [])
        self.assertEqual([(r["id"], [p for p, _, _ in r["unreviewed"]]) for r in self.rows if r["unreviewed"]], [])
        flagged = {(r["id"], p) for r in self.rows for p, _, _ in r["flagged"]}
        self.assertEqual(set(novelty_audit.REVIEWED_DISTINCT) - flagged, set(), "stale verdicts")

    def test_planted_near_duplicates_are_hard_flagged(self):
        v8 = [t for t in self.priors if t["set"] == "v8"]
        copy = dict(v8[0], id="v9_31_copy", split="held_out", family="formats")
        light = dict(v8[25], id="v9_32_light", split="held_out", family="simulation_dp",
                     prompt=v8[25]["prompt"].replace("Write", "Implement").replace("return", "give back"))
        rows = novelty_audit.audit([copy, light], self.priors)
        self.assertIn(v8[0]["id"], [p for p, _, _ in rows[0]["hard"]])
        self.assertIn(v8[25]["id"], [p for p, _, _ in rows[1]["hard"]])

    def test_cli_exit_code(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = novelty_audit.main(["--set", "v9", "--calibrate"])
        self.assertEqual(rc, 0, buf.getvalue()[-2000:])


def canned_lessons():
    src = inspect.getsource(memring._distill_deterministic)
    return sorted({n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant)
                   and isinstance(n.value, str) and len(n.value) >= 40})


class TestLeakGuards(unittest.TestCase):
    def prov(self):
        return {"task_id": "v8_01_hex_color", "task_set": "v8", "split": "train", "family": "formats", "arm": "loop",
                "model": "qwen3-32b", "created_at": "2026-11-07T00:00:00Z", "verdict": {"x": 1}}

    def test_canned_lessons_pass_against_v9(self):
        lessons = canned_lessons()
        self.assertGreaterEqual(len(lessons), 9)
        v9 = run.load_set("v9")
        for text in lessons:
            self.assertIsNone(memring.leak_check(text, self.prov(), held_out_tasks=v9), text)

    def test_lesson_quoting_v9_refused(self):
        v9 = run.load_set("v9")
        for t in v9:
            line = max(t["prompt"].splitlines(), key=len)   # a whole prompt line (a 6-word run of short words can pass)
            text = "Remember: " + line.strip()
            self.assertIsNotNone(memring.leak_check(text, self.prov(), held_out_tasks=v9), t["id"])
        self.assertIsNotNone(memring.leak_check("Use rho_shapes style bookkeeping for tails.", self.prov(), held_out_tasks=v9))


class TestFreeze(unittest.TestCase):
    def test_pinned_hashes(self):
        with open(FREEZE) as f:
            fr = json.load(f)
        for rel, want in fr["frozen_files_sha256"].items():
            self.assertEqual(sha256_file(os.path.join(HERE, rel)), want, rel)
        self.assertEqual(set(fr["frozen_files_sha256"]), {"tasks_v9.py", "tasks_v9_mutants.py", "novelty_audit.py"})
        self.assertEqual(fr["set"], "v9")
        self.assertEqual(sorted(fr["planned_preregs"]), ["memeval-v9-qwen3-32b", "memeval-v9-r1-distill-qwen-32b"])
        for label, p in fr["planned_preregs"].items():
            self.assertEqual(label, "memeval-v9-" + p["model"])
            self.assertEqual((p["k"], p["e"], p["task_budget"], p["parallel"], p["memory_k"]),
                             (4, 4, 16 * run.MAX_TOKENS, 4, memring.LESSON_K))


if __name__ == "__main__":
    unittest.main()
