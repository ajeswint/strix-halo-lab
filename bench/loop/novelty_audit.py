#!/usr/bin/env python3
"""Novelty audit of a candidate held-out set against every exposed task (v0-v8, run.SETS): lexical and semantic
similarity, embedding-free and deterministic. Method, thresholds and the v9 result: docs/v9-novelty-audit.md.

  novelty_audit.py --set v9                 table of each candidate's nearest prior tasks; exit 1 on any flag
  novelty_audit.py --set v9 --calibrate     the same metrics on known reskin pairs inside v0-v8 (threshold check)
  novelty_audit.py --set v9 --markdown      the table as Markdown (for the doc)

Metrics per (candidate, prior) pair, all in [0, 1]:
  w5    Jaccard of word 5-gram shingles of the prompts (copied or lightly edited spec text)
  tfidf cosine of word TF-IDF vectors of the prompts, IDF over all prompts (topic/vocabulary overlap)
  code  Jaccard of identifier/keyword token sets of the reference solutions (same implementation shape)
  name  Jaccard of name tokens: the id slug plus the entry-point names, split on "_" (same named problem)
  conc  Jaccard of concept tags from CONCEPTS, matched on prompt + reference (same problem type / core algorithm)
  io    1.0 when the entry-point arity signatures are identical (same I/O shape), else 0.0
A HARD rule flags a near-duplicate (fails, no override). A REVIEW rule (TF-IDF overlap alone) needs a written
semantic verdict in REVIEWED_DISTINCT. Rules and thresholds were fixed on the known reskin pairs in KNOWN_REUSES
(prior sets that re-used an earlier problem) before v9 was audited: every one of them must be flagged by some rule
(`--calibrate`). test_tasks_v9 checks that, that no v9 task has a HARD flag, and that every REVIEW flag has a verdict.

Limits: this is lexical and keyword-semantic, not paraphrase-proof. A problem re-told with new vocabulary and a new
concept that CONCEPTS does not list would pass. The audit says "unseen to the evaluated local models in this lab"
only together with the provenance in docs/v9-novelty-audit.md; it says nothing about pretraining data.
"""
import argparse, ast, math, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402

# Concept tags: problem type, data format and core algorithm. A tag fires when its regex matches the lower-cased
# prompt + reference. Kept broad on purpose (a false shared tag only makes the audit stricter).
CONCEPTS = {
    "bfs": r"breadth[- ]first|\bbfs\b|deque\(|popleft",
    "dfs": r"depth[- ]first|\bdfs\b",
    "shortest_path": r"shortest|dijkstra|fewest (moves|steps|jumps)|min(imum)? (number of )?(moves|steps|jumps)",
    "union_find": r"union[- ]find|disjoint[- ]set|\bdsu\b",
    "topo_sort": r"topolog|prerequisite",
    "tree": r"\btree\b|parent\[|\broot\b|ancestor",
    "lca": r"common ancestor|\blca\b|binary lifting",
    "cycle": r"\bcycle\b|cycles",
    "grid": r"\bgrid\b|\bboard\b|rows? and col",
    "geometry_point": r"\bpoints?\b.*\b(x|y)\b|cross product|polygon|segment",
    "convex_hull": r"convex hull",
    "polygon_area": r"shoelace|polygon area",
    "line_raster": r"bresenham|line_cells|grid line|rasteri",
    "angle_sort": r"\bangle\b|polar|counterclockwise",
    "distance": r"distance",
    "dp": r"dynamic programming|\bdp\b|memo",
    "knapsack": r"knapsack",
    "lcs_edit": r"longest common|edit distance|edit script|subsequence",
    "lis": r"increasing subsequence",
    "interval": r"\binterval",
    "partition": r"partition",
    "binomial": r"binomial|math\.comb|\bc\(n, k\)",
    "prime_factor": r"prime|factori[sz]|trial division",
    "gcd": r"\bgcd\b|greatest common divisor|euclid",
    "totient": r"totient|\bphi\b",
    "modular": r"\bmod(ulo|ulus)?\b|pow\(",
    "fibonacci": r"fibonacci",
    "divisors": r"divisor",
    "digits": r"\bdigits?\b",
    "base_conversion": r"\bbase\b|radix|hex",
    "fraction": r"fraction|rational",
    "rounding": r"round(ing|ed)?\b|half up|half-up|halfway",
    "complex_int": r"gaussian|complex",
    "sieve": r"sieve",
    "simulation": r"simulat|each step|one step|\bturn\b|tick",
    "queue_sim": r"\bqueue\b|teller|elevator|scheduler",
    "game": r"\bgame\b|\bscore\b|player",
    "money": r"\bprice|\bcents?\b|ledger|balance|gain",
    "parse_text": r"\bparse|\btoken",
    "escape_quote": r"escape|quoted|backslash",
    "encode_decode": r"encode|decode",
    "whitespace": r"\bspaces?\b|\btab\b|whitespace|indent",
    "csv": r"\bcsv\b",
    "json": r"\bjson\b",
    "url": r"\burl\b|percent-encod",
    "ip_addr": r"\bipv[46]\b|cidr|netmask",
    "date_time": r"\bdate\b|calendar|\bclock\b|\bweek|\bhours?\b|leap year",
    "duration": r"duration",
    "units_size": r"\bkib\b|\bmib\b|bytes? count|\biec\b",
    "permissions": r"permission|setuid|sticky",
    "header_params": r"media[- ]type|content-type|header",
    "nested_dict": r"nested dict|dotted",
    "page_range": r"page",
    "outline": r"heading|outline",
    "checksum": r"checksum|check digit|luhn|\bcrc\b",
    "bits": r"\bbits?\b|bitwise|\bmask",
    "string_interleave": r"interleav",
    "probability": r"probabilit|chance|equally likely",
    "dice": r"\bdice\b|\bdie\b",
    "sandpile": r"sandpile|topple",
    "ant": r"langton|\bant\b|turmite",
    "snake": r"\bsnake\b",
    "egg_drop": r"\begg",
    "lots_fifo": r"\bfifo\b|\blifo\b|\blots?\b",
    "jump_game": r"\bjump",
    "maze_keys": r"\bkeys?\b.*\bdoors?\b|\bdoors?\b.*\bkeys?\b",
    "equation_vars": r"equalit|variables",
    "functional_graph": r"functional graph|rho\b",
    "simplify_polyline": r"douglas|peucker|simplif",
    "aliquot": r"aliquot|proper divisors|amicable|perfect number",
    "primitive_root": r"primitive root|multiplicative order",
    "factorial": r"factorial|n!",
    "lucky": r"\blucky\b",
    "consecutive_sum": r"consecutive (positive )?integers",
    "zeckendorf": r"zeckendorf",
    "quoted_printable": r"quoted-printable|soft break",
    "regex_glob": r"\bregex|glob|wildcard",
    "stack_vm": r"stack machine|\bopcode|instruction|registers?\b",
    "matrix": r"\bmatrix\b",
    "justify_wrap": r"justif|\bwrap",
}
_CONC = {k: re.compile(v, re.S) for k, v in CONCEPTS.items()}
_WORD = re.compile(r"[a-z0-9]+")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Prior sets that re-used an earlier problem (lab history in README / task docstrings). The audit must flag each.
KNOWN_REUSES = [("v6_06_ipv6_canonical", "v2_04_ipv6_canonical"), ("v6_08_url_normalize", "v3_03_url_normalize"),
                ("v7_07_rect_union", "v4_26_rect_union"), ("v7_06_route_lexmin", "v3_14_route_lex"),
                ("v6_17_lexmin_route", "v3_14_route_lex"), ("v6_02_bencode_canonical", "v3_10_bencode"),
                ("v7_10_justify_lines", "v2_08_text_justify")]

# Flag rules, fixed 2026-11-07 on KNOWN_REUSES with --calibrate BEFORE the v9 audit was run, and not changed after.
# HARD: a near-duplicate; the test fails, no override. REVIEW: TF-IDF vocabulary overlap alone, which also fires on
# shared words with different meaning ("chain", "primitive", "snake"); a REVIEW flag needs a written semantic verdict
# in REVIEWED_DISTINCT (problem type, I/O shape, core algorithm) or the test fails. The tfidf line 0.35 sits under
# the weakest known reuse (v7_06_route_lexmin ~ v3_14_route_lex, 0.3995), which only this rule catches.
HARD_RULES = (("w5 >= 0.08", lambda m: m["w5"] >= 0.08),
              ("code >= 0.60", lambda m: m["code"] >= 0.60),
              ("name >= 0.50 and conc >= 0.40", lambda m: m["name"] >= 0.50 and m["conc"] >= 0.40),
              ("tfidf >= 0.30 and conc >= 0.50 and io",
               lambda m: m["tfidf"] >= 0.30 and m["conc"] >= 0.50 and m["io"] == 1.0))
REVIEW_RULES = (("tfidf >= 0.35", lambda m: m["tfidf"] >= 0.35),)
RULES = HARD_RULES + REVIEW_RULES

# Writer's semantic verdicts on the REVIEW-tier v9 flags (2026-11-07). Each says why the pair is a different problem.
# Open to the adversarial reviewer: a verdict that does not hold makes the v9 task a near-duplicate.
REVIEWED_DISTINCT = {
    ("v9_03_tab_stops", "v2_08_text_justify"):
        "Column arithmetic on one line (tab stops; collapse trailing space runs per fixed chunk) vs packing words into "
        "lines and distributing spaces. Shared words: spaces, width, line. Different I/O (str+width -> str both ways vs "
        "text -> list of lines) and algorithm.",
    ("v9_10_aliquot_chain", "v8_29_matrix_chain"):
        "Shared word 'chain' only. Iterated sum-of-proper-divisors with cycle classification vs interval DP over "
        "matrix dimensions.",
    ("v9_11_primitive_root", "v8_13_primitive_triples"):
        "Shared word 'primitive' and gcd vocabulary. Multiplicative order / existence of primitive roots mod n "
        "(totient, factor phi, pow checks) vs enumerating coprime Pythagorean triples (Euclid's formula).",
    ("v9_21_rdp_simplify", "v6_22_segment_pair_kinds"):
        "Shared exact-geometry vocabulary (segment, endpoints, ints). Recursive polyline simplification by "
        "point-to-segment distance vs classifying how every pair of segments intersects.",
    ("v9_21_rdp_simplify", "v8_18_closest_pair"):
        "Shared squared-distance vocabulary. RDP keep/drop recursion over a polyline vs the minimum pairwise "
        "distance over a point set.",
    ("v9_22_polar_order", "v4_30_cocircular"):
        "Shared point-list vocabulary. Angular sort around an origin with half-plane + cross-product ties vs finding "
        "the circle through the most points.",
    ("v9_22_polar_order", "v7_25_point_location"):
        "Shared cross-product vocabulary. Ordering points by angle vs classifying points inside/outside/on a simple "
        "polygon. Angular comparison is a sub-step of some hull algorithms (v2_24, v6_18); none asks for the order.",
    ("v9_27_snake_game", "v8_03_case_convert"):
        "Lexical coincidence: 'snake' (the game) vs 'snake_case' (identifier style). Grid movement simulation with a "
        "growing body vs string case conversion.",
}

def words(text):
    return _WORD.findall((text or "").lower())


def shingles(text, n=5):
    w = words(text)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def entry_sig(t):
    """Sorted arity signature of the reference's top-level functions that the tests mention."""
    try:
        tree = ast.parse(t["ref"])
    except SyntaxError:
        return ()
    sig = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and re.search(r"\b" + re.escape(n.name) + r"\b", t["tests"]):
            sig.append(len(n.args.args))
    return tuple(sorted(sig))


def entry_names(t):
    try:
        tree = ast.parse(t["ref"])
    except SyntaxError:
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            and re.search(r"\b" + re.escape(n.name) + r"\b", t["tests"])}


def features(t):
    slug = t["id"].split("_", 2)[-1]
    text = (t["prompt"] + "\n" + t["ref"]).lower()
    return {"id": t["id"], "words": Counter(words(t["prompt"])), "w5": shingles(t["prompt"]),
            "code": set(_IDENT.findall(t["ref"])) - {"self", "None", "True", "False"},
            "name": set(slug.split("_")) | {p for n in entry_names(t) for p in n.lower().split("_") if p},
            "conc": {k for k, rx in _CONC.items() if rx.search(text)}, "io": entry_sig(t)}


class Corpus:
    def __init__(self, tasks):
        self.f = {t["id"]: features(t) for t in tasks}
        df = Counter(w for f in self.f.values() for w in f["words"])
        n = len(self.f)
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1 for w, c in df.items()}
        self.vec = {}
        for tid, f in self.f.items():
            v = {w: c * self.idf[w] for w, c in f["words"].items()}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            self.vec[tid] = {w: x / norm for w, x in v.items()}

    def metrics(self, a, b):
        fa, fb, va, vb = self.f[a], self.f[b], self.vec[a], self.vec[b]
        if len(va) > len(vb):
            va, vb = vb, va
        return {"w5": jaccard(fa["w5"], fb["w5"]), "tfidf": sum(x * vb.get(w, 0.0) for w, x in va.items()),
                "code": jaccard(fa["code"], fb["code"]), "name": jaccard(fa["name"], fb["name"]),
                "conc": jaccard(fa["conc"], fb["conc"]), "io": 1.0 if fa["io"] == fb["io"] and fa["io"] else 0.0}


def flags(m, rules=RULES):
    return [name for name, rule in rules if rule(m)]


def hard_flags(m):
    return flags(m, HARD_RULES)


def prior_tasks():
    out = []
    for s in sorted(run.SETS, key=lambda s: int(s[1:])):
        out += [dict(t, set=s) for t in run.load_set(s)]
    return out


def audit(candidates, priors=None):
    """One row per candidate: its nearest prior task on each metric, and every flagged pair."""
    priors = priors if priors is not None else prior_tasks()
    corpus = Corpus(list(priors) + list(candidates))
    rows = []
    for c in candidates:
        ms = [(p["id"], corpus.metrics(c["id"], p["id"])) for p in priors]
        best = {k: max(ms, key=lambda x: x[1][k]) for k in ("w5", "tfidf", "code", "name", "conc")}
        flagged = [(pid, m, flags(m)) for pid, m in ms if flags(m)]
        hard = [(pid, m, hard_flags(m)) for pid, m in ms if hard_flags(m)]
        unreviewed = [(pid, m, fl) for pid, m, fl in flagged if not hard_flags(m) and (c["id"], pid) not in REVIEWED_DISTINCT]
        rows.append({"id": c["id"], "family": c.get("family"), "best": best, "flagged": flagged, "hard": hard,
                     "unreviewed": unreviewed,
                     "concepts": sorted(corpus.f[c["id"]]["conc"]), "io": corpus.f[c["id"]]["io"],
                     "n_priors": len(priors)})
    return rows


def calibrate(priors=None):
    priors = priors if priors is not None else prior_tasks()
    corpus = Corpus(priors)
    return [(a, b, corpus.metrics(a, b), flags(corpus.metrics(a, b))) for a, b in KNOWN_REUSES]


def table(rows, markdown=False):
    head = ["task", "family", "max w5 (prior)", "max tfidf (prior)", "max code (prior)", "max name (prior)",
            "max conc (prior)", "hard", "review (verdict)"]
    lines = []
    if markdown:
        lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = [r["id"], r["family"] or "-"]
        for k in ("w5", "tfidf", "code", "name", "conc"):
            pid, m = r["best"][k]
            cells.append(f"{m[k]:.2f} ({pid.split('_', 2)[0]}_{pid.split('_', 2)[1]})")
        cells.append(str(len(r["hard"])))
        cells.append(str(len(r["flagged"]) - len(r["hard"])) + (f" ({len(r['unreviewed'])} without)" if r["unreviewed"] else ""))
        lines.append("| " + " | ".join(cells) + " |" if markdown else "  ".join(cells))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, help="candidate set, loaded with run.load_set (not in run.SETS)")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args(argv)
    if a.set in run.SETS:
        raise SystemExit(f"{a.set} is an exposed set; audit a candidate set")
    priors = prior_tasks()
    bad = 0
    if a.calibrate:
        for x, y, m, fl in calibrate(priors):
            print(f"{x} ~ {y}: " + " ".join(f"{k}={v:.2f}" for k, v in m.items()) + f"  flags={fl}")
            bad += not fl
        print(f"{len(KNOWN_REUSES)} known reuses, {bad} NOT flagged")
    rows = audit(run.load_set(a.set), priors)
    print(table(rows, a.markdown))
    nhard = sum(bool(r["hard"]) for r in rows)
    nopen = sum(bool(r["unreviewed"]) for r in rows)
    for r in rows:
        for pid, m, fl in r["flagged"]:
            tier = "HARD" if hard_flags(m) else ("REVIEWED" if (r["id"], pid) in REVIEWED_DISTINCT else "REVIEW-OPEN")
            print(f"{tier} {r['id']} ~ {pid}: {fl} " + " ".join(f"{k}={v:.2f}" for k, v in m.items()))
    stale = set(REVIEWED_DISTINCT) - {(r["id"], pid) for r in rows for pid, _, _ in r["flagged"]}
    for k in sorted(stale):
        print(f"STALE verdict (pair no longer flagged): {k}")
    print(f"{len(rows)} candidates vs {len(priors)} prior tasks: {nhard} with a HARD flag, "
          f"{sum(bool(r['flagged']) for r in rows)} with any flag, {nopen} with a REVIEW flag lacking a verdict")
    return 1 if nhard or nopen or bad else 0


if __name__ == "__main__":
    sys.exit(main())
