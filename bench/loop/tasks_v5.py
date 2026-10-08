"""loop-v5: 10 held-out Python tasks aimed at the families of the coded v4 failures (Roadmap item 2).

Same layout as tasks_v4.py: id, prompt, tests, ref. Written 2026-10-07 for the hardened grader
(oracle over stdin, static deny-list; the refs use none of the denied names). The aim is family
resemblance to the coded v4 failures, chosen from their specs and not from any model's wrong
answers; hardness is what the run measures. Five families, two tasks each, named by the
mechanism in the exemplar spec: civil time (gaps, folds, leap seconds), ordering (same-instant
order, priority, zero-duration cascades), Hindley-Milner with let/letrec and canonical variable
names, iterated dominance frontiers at large n, several rounding modes and extreme exponents.
None was used for prompt or loop iteration and no test or prompt comes from a stored error. Every
test file has exactly one random.seed(N) line, N = 5000 + task number, so agent.py's fresh-seed
grade applies. Seeded random cases are checked against an oracle built differently from the ref.
Each ref is at most 150 lines.
v5_01 table_zone, v5_02 leap_smear, v5_03 petri_starts, v5_04 gate_trace, v5_05 weak_poly,
v5_06 group_infer, v5_07 branch_influence, v5_08 pruned_phis, v5_09 sigfig_sci, v5_10 step_snap.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("v5_01_table_zone", r'''
Write `table_zone_eval(zone, ops)` for a time zone given as an explicit table of offset changes.
Everything is an int number of seconds. An instant x counts UTC seconds since 1970-01-01 00:00:00
UTC. A wall time w counts local-clock seconds since 1970-01-01 00:00:00 on the local clock; there
is no calendar, a day is 86400 wall seconds. Both may be any int, including negative.
`zone` is a list or tuple (initial, transitions). `initial` is the offset from UTC in effect
before the first transition. `transitions` is a list or tuple of at most 100000 entries (t, off),
each a list or tuple of 2 ints (bool is not an int): from instant t on the offset is off. Limits:
|initial| and |off| <= 50400, |t| <= 10**13, each t at least 172800 greater than the previous t,
and each offset differs from the previous offset (initial for the first) by at most 86400. A
transition may keep the offset unchanged; it then has no effect at all. The offset at instant x is
that of the last transition with t <= x, else initial; the wall time of x is x + offset(x).
A wall time w matches an instant x when x + offset(x) == w. Under these limits w matches 0, 1 or 2
instants, and a w with 0 matches lies in the gap of exactly one transition: one at which the
offset rises from a to b, T being its instant, with T + a <= w < T + b (a gap can last a whole day).
`resolve(w, fold)`, fold being the int 0 or 1, gives an instant:
- 1 match: that instant (fold is ignored);
- 2 matches (the clocks went back): fold 0 is the earlier instant, fold 1 the later one;
- 0 matches (a gap): fold 0 gives w - a and fold 1 gives w - b, with a, b of the gap's transition.
`ops` is a list or tuple of operations, each a list or tuple whose first item is a str. The result
is the list of their results in order:
- ("instant", w, fold) -> resolve(w, fold), an int;
- ("wall", x) -> the tuple (w, f) with w the wall time of instant x and f = 1 if x is the later of
  two instants matching w, else 0;
- ("add", w, fold, days, secs) -> first w2 = w + 86400 * days on the wall clock, resolved with the
  same fold to an instant x1 = resolve(w2, fold); then x2 = x1 + secs real seconds; the result is
  the ("wall", x2) tuple.
Limits: |w|, |x|, |secs| <= 10**13, |days| <= 10**6, fold exactly 0 or 1 (not bool). Anything invalid
(zone, ops, an unknown operation name, a wrong number of items, any value of a wrong type or out of
range) makes the whole call a ValueError, including an invalid zone with an empty ops. At 100000
transitions and several thousand operations the call must still finish in a few seconds.
Examples: zone (-36000, [(1000000, 50400)]) has a gap of 86400 s: ("instant", 1000000, 0) is
1036000, ("instant", 1000000, 1) is 949600, ("wall", 1036000) is (1086400, 0). Zone (3600,
[(500000, 0)]) has wall times 500000..503599 twice: ("instant", 501000, 0) is 497400, with fold 1
it is 501000, and ("wall", 501000) is (501000, 1). In zone (0, [(1000000, 3600)]),
("add", 913600, 0, 1, 0) is (1003600, 0) and ("add", 913600, 1, 1, 0) is (996400, 0).
''', r'''
import random

def ev(z, ops):
    return table_zone_eval(z, ops)

def bad(z, ops):
    try:
        table_zone_eval(z, ops)
    except ValueError:
        return True
    return False

# worked examples from the statement
Z1 = (-36000, [(1000000, 50400)])
assert ev(Z1, [("instant", 1000000, 0), ("instant", 1000000, 1), ("wall", 1036000), ("wall", 949600)]) == [1036000, 949600, (1086400, 0), (913600, 0)]
Z2 = (3600, [(500000, 0)])
assert ev(Z2, [("instant", 501000, 0), ("instant", 501000, 1), ("wall", 501000), ("wall", 497400)]) == [497400, 501000, (501000, 1), (501000, 0)]
Z3 = (0, [(1000000, 3600)])
assert ev(Z3, [("add", 913600, 0, 1, 0), ("add", 913600, 1, 1, 0), ("add", 999999, 0, 0, 1), ("add", 913599, 0, 1, 1)]) == [(1003600, 0), (996400, 0), (1003600, 0), (1003600, 0)]
assert ev((5, []), []) == [] and ev([5, ()], [["wall", 0], ("instant", -7, 1)]) == [(5, 0), -12]
# gap edges: the gap is [T + a, T + b)
assert ev(Z1, [("instant", 963999, 0), ("instant", 963999, 1), ("instant", 964000, 0), ("instant", 964000, 1)]) == [999999, 999999, 1000000, 913600]
assert ev(Z1, [("instant", 1050399, 0), ("instant", 1050399, 1), ("instant", 1050400, 0), ("instant", 1050400, 1)]) == [1086399, 999999, 1000000, 1000000]
assert ev(Z1, [("wall", 999999), ("wall", 1000000)]) == [(963999, 0), (1050400, 0)]
# fold edges: the wall times [T + b, T + a) occur twice
assert ev(Z2, [("instant", 500000, 0), ("instant", 500000, 1), ("instant", 503599, 0), ("instant", 503599, 1)]) == [496400, 500000, 499999, 503599]
assert ev(Z2, [("instant", 503600, 0), ("instant", 503600, 1), ("instant", 499999, 0), ("instant", 499999, 1)]) == [503600, 503600, 496399, 496399]
assert ev(Z2, [("wall", 499999), ("wall", 500000), ("wall", 503599), ("wall", 503600)]) == [(503599, 0), (500000, 1), (503599, 1), (503600, 0)]
assert ev(Z2, [("wall", 496400), ("wall", 496399)]) == [(500000, 0), (499999, 0)]
# a transition that changes nothing is invisible
Z5 = (0, [(1000000, 0), (2000000, 3600), (4000000, 3600)])
assert ev(Z5, [("instant", 1000000, 1), ("instant", 2001000, 0), ("instant", 2001000, 1), ("wall", 3999999), ("wall", 4000000), ("wall", 4003599)]) == [1000000, 2001000, 1997400, (4003599, 0), (4003600, 0), (4007199, 0)]
# a fold and a gap of a whole day
Z6 = (50400, [(10 ** 6, -36000), (3 * 10 ** 6, 50400)])
assert ev(Z6, [("instant", 964000, 0), ("instant", 964000, 1), ("instant", 1050399, 0), ("instant", 1050399, 1)]) == [913600, 1000000, 999999, 1086399]
assert ev(Z6, [("instant", 1050400, 0), ("instant", 1050400, 1), ("instant", 963999, 0), ("instant", 963999, 1)]) == [1086400, 1086400, 913599, 913599]
assert ev(Z6, [("wall", 913600), ("wall", 1000000), ("wall", 999999), ("wall", 1086399)]) == [(964000, 0), (964000, 1), (1050399, 0), (1050399, 1)]
assert ev(Z6, [("instant", 2964000, 0), ("instant", 2964000, 1), ("instant", 3050399, 0), ("instant", 3050399, 1), ("instant", 3050400, 0)]) == [3000000, 2913600, 3086399, 2999999, 3000000]
# add: days on the wall clock first (with the given fold), then real seconds
Z7 = (3600, [(500000, 0), (800000, 7200), (1100000, 3600)])
assert ev(Z7, [("add", 501000, 0, 0, 0), ("add", 501000, 1, 0, 0), ("add", 501000, 0, 0, 3600), ("add", 501000, 0, 0, 3601), ("add", 501000, 0, 0, 3599)]) == [(501000, 0), (501000, 1), (501000, 1), (501001, 1), (500999, 1)]
assert ev(Z7, [("add", 501000, 0, 3, 0), ("add", 501000, 1, -5, -1), ("add", 0, 0, 0, 10 ** 7), ("add", 799999, 0, 0, 1)]) == [(760200, 0), (68999, 0), (10 ** 7, 0), (807200, 0)]
assert ev(Z7, [("add", 714600, 0, 1, 0), ("add", 714600, 1, 1, 0), ("add", 714600, 0, 0, 86400), ("add", 714600, 1, 0, 86400)]) == [(808200, 0), (793800, 0), (808200, 0), (808200, 0)]
assert ev(Z7, [("add", 1103600, 0, 0, 0), ("add", 1103600, 1, 0, 0), ("add", 1103600, 0, 0, 3600), ("add", 1103600, 1, -1, 86400)]) == [(1103600, 0), (1103600, 1), (1103600, 1), (1103600, 0)]
# days then seconds is not seconds then days around a gap
Z8 = (0, [(1000000, 3600)])
assert ev(Z8, [("add", 914600, 0, 1, 0), ("add", 914600, 1, 1, 0), ("add", 914600, 0, 1, -3600), ("add", 914600, 1, 1, 3600)]) == [(1004600, 0), (997400, 0), (997400, 0), (1004600, 0)]
# validation
G = [(1000000, 3600)]
for z in [None, 5, "ab", {}, (), (0,), (0, [], 0), (True, []), (50401, []), (-50401, []), (1.0, []), ("0", []), (0, None), (0, 5), (0, "x"), (0, {(1000000, 3600)}),
          (0, [(1000000,)]), (0, [(1000000, 3600, 0)]), (0, [5]), (0, [None]), (0, [(True, 3600)]), (0, [(1000000, True)]), (0, [(1000000.0, 3600)]), (0, [(1000000, 3600.0)]),
          (0, [("1", 3600)]), (0, [(1000000, 50401)]), (0, [(1000000, -50401)]), (-43200, [(1000000, 50400)]), (50400, [(1000000, -43200)]), (-36001, [(1000000, 50400)]), (50400, [(1000000, -36001)]), (0, [(1000000, 3600), (1172800, 50400), (1345600, -36001)]), (0, [(10 ** 13 + 1, 0)]),
          (0, [(-10 ** 13 - 1, 0)]), (0, [(1000000, 3600), (1172799, 0)]), (0, [(1000000, 3600), (1000000, 0)]), (0, [(1000000, 3600), (900000, 0)]),
          (0, [(1000000, 3600), (1172800, 99999)]), (0, [(1000000, 3600), (1172800, 0), (1172800 + 172799, 3600)]), (0, [(1000000, 3600), None]),
          (0, [(i * 172800, i % 2 * 3600) for i in range(100001)])]:
    assert bad(z, []), z
    assert bad(z, [("wall", 0)]), z
assert not bad((0, [(i * 172800, i % 2 * 3600) for i in range(100000)]), [])
assert not bad((0, [(1000000, 3600), (1172800, 0)]), []) and not bad((-36000, [(-10 ** 13, 50400), (10 ** 13, -36000)]), [])
assert not bad((50400, [(0, -36000), (172800, 50400), (345600, -36000)]), [])
for ops in [None, 5, "wall", {("wall", 0)}, [None], [5], [()], [[]], ["wall"], [("wall",)], [("wall", 0, 0)], [("instant", 0)], [("instant", 0, 0, 0)], [("add", 0, 0, 0)],
            [("add", 0, 0, 0, 0, 0)], [("bogus", 0)], [(0, 0)], [("Wall", 0)], [("wall ", 0)], [("wall", True)], [("wall", 0.0)], [("wall", "0")], [("wall", None)],
            [("wall", 10 ** 13 + 1)], [("wall", -10 ** 13 - 1)], [("instant", 0, 2)], [("instant", 0, -1)], [("instant", 0, True)], [("instant", 0, 1.0)], [("instant", 0.5, 0)],
            [("instant", 10 ** 13 + 1, 0)], [("add", 0, 0, 10 ** 6 + 1, 0)], [("add", 0, 0, -10 ** 6 - 1, 0)], [("add", 0, 0, 0, 10 ** 13 + 1)], [("add", 0, 0, 0, -10 ** 13 - 1)],
            [("add", 0, 2, 0, 0)], [("add", True, 0, 0, 0)], [("add", 0, 0, True, 0)], [("add", 0, 0, 0, True)], [("add", 0, 0, 0.0, 0)], [("add", 0, 0, 0, 1.0)],
            [("wall", 0), ("wall", 1), ("bogus",)], [("wall", 0)] * 3 + [None]]:
    assert bad(G and (0, G), ops), ops
assert ev((0, G), [("wall", 10 ** 13), ("wall", -10 ** 13), ("instant", 10 ** 13, 1), ("add", -10 ** 13, 1, 10 ** 6, 10 ** 13), ("add", 0, 1, -10 ** 6, -10 ** 13)]) == [
    (10 ** 13 + 3600, 0), (-10 ** 13, 0), 10 ** 13 - 3600, (-10 ** 13 + 86400 * 10 ** 6 + 10 ** 13 + 3600, 0), (-86400 * 10 ** 6 - 10 ** 13, 0)]

# independent oracle: for every distinct offset o in the zone, w - o is an instant for w iff the offset in force there is o
def o_off(init, tr, x):
    o = init
    for t, f in tr:
        if t <= x:
            o = f
    return o

def o_matches(init, tr, w):
    return sorted(w - o for o in {init} | {f for _, f in tr} if o_off(init, tr, w - o) == o)

def o_resolve(init, tr, w, fold):
    m = o_matches(init, tr, w)
    assert len(m) <= 2
    if len(m) == 2:
        return m[fold]
    if m:
        return m[0]
    prev, hits = init, []
    for t, f in tr:
        if f > prev and t + prev <= w < t + f:
            hits.append((prev, f))
        prev = f
    assert len(hits) == 1
    return w - hits[0][fold]

def o_wall(init, tr, x):
    w = x + o_off(init, tr, x)
    return (w, o_matches(init, tr, w).index(x))

def o_add(init, tr, w, fold, days, secs):
    return o_wall(init, tr, o_resolve(init, tr, w + 86400 * days, fold) + secs)

random.seed(5001)
POOL = [-43200, -36000, -12600, 0, 3600, 19800, 20700, 45900, 46800, 50400]

def rzone(m):
    init = random.choice(POOL)
    tr, t, cur = [], random.randint(-10 ** 9, 10 ** 9), init
    for _ in range(m):
        t += 172800 + random.choice([0, 0, 1, 86400, random.randint(0, 10 ** 6), random.randint(0, 10 ** 7)])
        nxt = random.choice([o for o in POOL if abs(o - cur) <= 86400] + [cur] * 2)
        tr.append((t, nxt))
        cur = nxt
    return init, tr

n_gap = n_fold = n_ops = 0
for zi in range(16):
    init, tr = rzone(random.choice([1, 2, 5, 12, 30, 60]))
    offs = [init] + [f for _, f in tr]
    ops, exp = [], []
    for _ in range(110):
        k = random.randrange(len(tr))
        t = tr[k][0]
        a, b = offs[k], offs[k + 1]
        kind = random.choice(["instant", "instant", "wall", "add", "add"])
        w = t + random.choice([a, b]) + random.choice([-1, 0, 1, -3600, 3600, b - a, a - b, (b - a) // 2, random.randint(-90000, 90000), random.randint(-10 ** 9, 10 ** 9)])
        f = random.randint(0, 1)
        if kind == "instant":
            ops.append(("instant", w, f))
            exp.append(o_resolve(init, tr, w, f))
        elif kind == "wall":
            x = t + random.choice([-1, 0, 1, random.randint(-200000, 200000), random.randint(-10 ** 9, 10 ** 9)])
            ops.append(("wall", x))
            exp.append(o_wall(init, tr, x))
        else:
            days = random.choice([0, 0, 1, -1, 2, -3, random.randint(-1000, 1000)])
            secs = random.choice([0, 1, -1, 3600, -3600, 86400, -86400, random.randint(-10 ** 6, 10 ** 6), random.randint(-10 ** 11, 10 ** 11)])
            ops.append(("add", w, f, days, secs))
            exp.append(o_add(init, tr, w, f, days, secs))
        if kind == "instant":
            m = o_matches(init, tr, w)
            n_gap += not m
            n_fold += len(m) == 2
    got = ev((init, tr), ops)
    for o, g, e in zip(ops, got, exp):
        assert g == e, (init, tr, o, g, e)
    n_ops += len(ops)
assert n_gap > 60 and n_fold > 60, (n_gap, n_fold)

# a table with 100000 transitions and many queries (a linear scan per query is far too slow)
N, T0, P = 100000, 5 * 10 ** 8, 200000
big = (3600, [(T0 + k * P, 0 if k % 2 == 0 else 3600) for k in range(N)])
def b_off(x):
    c = min(N, max(0, (x - T0) // P + 1))
    return 3600 if c == 0 else (0 if (c - 1) % 2 == 0 else 3600)

def b_resolve(w, fold):
    m = sorted(w - o for o in (0, 3600) if b_off(w - o) == o)
    if len(m) == 2:
        return m[fold]
    if m:
        return m[0]
    k = (w - T0) // P
    assert 0 <= k < N and k % 2 == 1 and T0 + k * P <= w < T0 + k * P + 3600
    return w - (0, 3600)[fold]

def b_wall(x):
    w = x + b_off(x)
    return (w, sorted(w - o for o in (0, 3600) if b_off(w - o) == o).index(x))

ops, exp = [], []
for _ in range(5000):
    k = random.choice([0, 1, 2, N - 2, N - 1, random.randrange(N), random.randrange(N), -3, N + 2])
    t = T0 + k * P
    w = t + random.choice([0, 3600]) + random.choice([-1, 0, 1, -3600, 3600, 1800, -1800, random.randint(-50000, 50000)])
    f = random.randint(0, 1)
    kind = random.choice(["instant", "wall", "add"])
    if kind == "instant":
        ops.append(("instant", w, f))
        exp.append(b_resolve(w, f))
    elif kind == "wall":
        ops.append(("wall", w))
        exp.append(b_wall(w))
    else:
        days, secs = random.choice([0, 1, -1, 5]), random.choice([0, 1, -1, 3600, 200000, -200000, random.randint(-10 ** 7, 10 ** 7)])
        ops.append(("add", w, f, days, secs))
        exp.append(b_wall(b_resolve(w + 86400 * days, f) + secs))
assert ev(big, ops) == exp
''', r'''
from bisect import bisect_right


def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _zone(zone):
    if not isinstance(zone, (list, tuple)) or len(zone) != 2:
        raise ValueError("zone")
    init, tr = zone
    if not _isint(init) or abs(init) > 50400 or not isinstance(tr, (list, tuple)) or len(tr) > 100000:
        raise ValueError("zone")
    ts, offs = [], [init]
    for e in tr:
        if not isinstance(e, (list, tuple)) or len(e) != 2 or not _isint(e[0]) or not _isint(e[1]):
            raise ValueError("transition")
        t, off = e
        if abs(t) > 10 ** 13 or abs(off) > 50400 or abs(off - offs[-1]) > 86400:
            raise ValueError("transition range")
        if ts and t - ts[-1] < 172800:
            raise ValueError("transition order")
        ts.append(t)
        offs.append(off)
    return ts, offs


def _resolve(Z, w, fold):
    ts, offs, A, B = Z
    i = bisect_right(A, w)
    found = []
    for s in (i - 1, i):
        if 0 <= s < len(offs):
            x = w - offs[s]
            if (s == 0 or ts[s - 1] <= x) and (s == len(ts) or x < ts[s]):
                found.append(x)
    if len(found) == 2:
        return found[fold]
    if found:
        return found[0]
    k = bisect_right(B, w) - 1
    return w - offs[k + fold]


def _wall(Z, x):
    ts, offs = Z[0], Z[1]
    w = x + offs[bisect_right(ts, x)]
    return (w, 0 if _resolve(Z, w, 0) == x else 1)


def _int(v, lim):
    if not _isint(v) or abs(v) > lim:
        raise ValueError("int")
    return v


def _fold(v):
    if not _isint(v) or v not in (0, 1):
        raise ValueError("fold")
    return v


def table_zone_eval(zone, ops):
    ts, offs = _zone(zone)
    Z = (ts, offs, [t + offs[k + 1] for k, t in enumerate(ts)], [t + offs[k] for k, t in enumerate(ts)])
    if not isinstance(ops, (list, tuple)):
        raise ValueError("ops")
    out = []
    for op in ops:
        if not isinstance(op, (list, tuple)) or not op or not isinstance(op[0], str):
            raise ValueError("op")
        name, a = op[0], op[1:]
        if name == "instant" and len(a) == 2:
            out.append(_resolve(Z, _int(a[0], 10 ** 13), _fold(a[1])))
        elif name == "wall" and len(a) == 1:
            out.append(_wall(Z, _int(a[0], 10 ** 13)))
        elif name == "add" and len(a) == 4:
            w, f, days, secs = _int(a[0], 10 ** 13), _fold(a[1]), _int(a[2], 10 ** 6), _int(a[3], 10 ** 13)
            out.append(_wall(Z, _resolve(Z, w + 86400 * days, f) + secs))
        else:
            raise ValueError("op")
    return out
''')


task("v5_02_leap_smear", r'''
Write `smeared_ms(n, leaps)` and `unsmeared_ms(s, leaps)` for a clock that smears leap seconds
instead of showing 23:59:60. Dates are proleptic Gregorian.
- Real time n is an int count of SI milliseconds since 1970-01-01 00:00:00.000 UTC, 0 <= n <= 10**16.
  The smeared reading s is an int count of milliseconds on a clock whose every day has exactly
  86400000 ms; s = 0 at n = 0.
- `leaps`: list or tuple of at most 100 entries (year, month, delta), each a list or tuple of 3 ints
  (bool is not an int) with 1970 <= year <= 2400, 1 <= month <= 12, delta 1 or -1, in strictly
  increasing (year, month) order, and not (1970, 1). Leap k happens at the end of that month: with
  delta = 1 the month lasts one real second longer than its calendar length, with -1 one real second
  less. Leaps accumulate: the month of leap k ends E_k real milliseconds after the epoch, where
  E_k = 86400000 * D_k + 1000 * (delta_0 + ... + delta_k), D_k being the number of days from
  1970-01-01 to the first day of the month after leap k's month.
- Smear window of leap k: the 1000 real seconds [E_k - 1000000, E_k). Define
  g_k(n) = min(1000, max(0, (n - (E_k - 1000000)) // 1000)), with // the floor division. So g_k is 0
  before the window, rises by 1 every 1000 real ms inside it, and is 1000 from E_k on.
- `smeared_ms(n, leaps)` = n - sum over all leaps k of delta_k * g_k(n). A +1 leap makes the clock lose
  1 ms per 1000 real ms of its window (1000 ms in all), a -1 leap makes it gain 1 ms per 1000 real
  ms. Windows of different leaps never overlap.
- `unsmeared_ms(s, leaps)` returns the smallest n >= 0 for which smeared_ms(n, leaps) == s, s an int
  with 0 <= s <= 10**16. If a +1 window makes several n give the same s, the smallest n is
  returned. If no n gives s (a -1 window skips values), it is a ValueError.
- In both functions leaps is validated first; an invalid leaps, or n or s that is not an int
  (bool is not an int) or is outside its range, is a ValueError. Both must be fast for any valid
  input (n up to 10**16, 100 leaps), so counting millisecond by millisecond is not an option.
Examples: with leaps = [(1972, 6, 1)] the window is [78795801000, 78796801000). Then
smeared_ms(78795801999, leaps) and smeared_ms(78795802000, leaps) are both 78795801999 (the clock
stands still for one ms), so unsmeared_ms(78795801999, leaps) is 78795801999. With leaps = [(1970, 2, -1)] the window starts at
5096599000, smeared_ms(5096599999, leaps) = 5096599999, smeared_ms(5096600000, leaps) = 5096600001, so
unsmeared_ms(5096600000, leaps) is a ValueError.
''', r'''
import random, datetime

def bad(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

# worked examples from the statement
L1 = [(1972, 6, 1)]
ws = 78795801000
assert smeared_ms(ws - 1, L1) == ws - 1 and smeared_ms(ws, L1) == ws and smeared_ms(ws + 999, L1) == ws + 999
assert smeared_ms(ws + 1000, L1) == ws + 999 and smeared_ms(ws + 1001, L1) == ws + 1000 and smeared_ms(ws + 1999, L1) == ws + 1998 and smeared_ms(ws + 2000, L1) == ws + 1998
assert smeared_ms(ws + 10 ** 6 - 1, L1) == 78796800000 and smeared_ms(ws + 10 ** 6, L1) == 78796800000 and smeared_ms(ws + 10 ** 6 + 5, L1) == 78796800005
L2 = [(1970, 2, -1)]
w2 = 5096599000
assert [smeared_ms(w2 + d, L2) for d in (999, 1000, 1001, 10 ** 6 - 1, 10 ** 6)] == [w2 + 999, w2 + 1001, w2 + 1002, w2 + 10 ** 6 - 1 + 999, w2 + 10 ** 6 + 1000]
assert unsmeared_ms(w2 + 1001, L2) == w2 + 1000 and unsmeared_ms(w2 + 999, L2) == w2 + 999 and unsmeared_ms(w2 + 10 ** 6 + 1000, L2) == w2 + 10 ** 6
assert bad(unsmeared_ms, w2 + 1000, L2) and bad(unsmeared_ms, w2 + 2001, L2) and not bad(unsmeared_ms, w2 + 2002, L2) and bad(unsmeared_ms, w2 + 10 ** 6 + 999, L2)
# no leaps and the ends of the range
assert smeared_ms(0, []) == 0 and smeared_ms(10 ** 16, ()) == 10 ** 16 and unsmeared_ms(0, []) == 0 and unsmeared_ms(10 ** 16, []) == 10 ** 16
assert smeared_ms(0, L1) == 0 and unsmeared_ms(0, L2) == 0
assert unsmeared_ms(ws + 999, L1) == ws + 999 and unsmeared_ms(ws + 1998, L1) == ws + 1999 and unsmeared_ms(78796800000, L1) == ws + 999999 and unsmeared_ms(78796800001, L1) == ws + 10 ** 6 + 1
# after all windows: a plain shift of 1000 ms per leap
LC = [(1999, 1, 1), (1999, 2, -1), (1999, 3, 1)]
assert smeared_ms(10 ** 15, LC) == 10 ** 15 - 1000 and unsmeared_ms(10 ** 15 - 1000, LC) == 10 ** 15
assert smeared_ms(10 ** 16, LC) == 10 ** 16 - 1000 and unsmeared_ms(10 ** 16 - 1000, LC) == 10 ** 16 and bad(unsmeared_ms, 10 ** 16 + 1, LC)
L12 = [(1972, 6, 1), (1972, 12, 1)]
E2 = 1096 * 86400000 + 2000
assert smeared_ms(E2, L12) == 1096 * 86400000 and smeared_ms(E2 - 1, L12) == 1096 * 86400000 and smeared_ms(E2 - 10 ** 6, L12) == 1096 * 86400000 - 10 ** 6 + 1000
assert smeared_ms(E2 + 1000, L12) == 1096 * 86400000 + 1000 and unsmeared_ms(1096 * 86400000, L12) == E2 - 1 and unsmeared_ms(1096 * 86400000 - 10 ** 6 + 1000, L12) == E2 - 10 ** 6
# calendar: leap years, century years, the last allowed year
def days(y, m):
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    return (datetime.date(ny, nm, 1) - datetime.date(1970, 1, 1)).days
assert days(2000, 2) == 11017 and days(2100, 2) == 47541
for y, m, dl in [(2000, 2, 1), (2100, 2, -1), (2400, 12, 1), (2400, 2, -1), (1970, 2, 1), (2024, 12, -1)]:
    E = days(y, m) * 86400000 + 1000 * dl
    Lx = [(y, m, dl)]
    assert smeared_ms(E, Lx) == days(y, m) * 86400000 and smeared_ms(E - 10 ** 6, Lx) == E - 10 ** 6 and smeared_ms(E - 10 ** 6 + 1000, Lx) == E - 10 ** 6 + 1000 - dl
    assert smeared_ms(E - 1, Lx) == E - 1 - dl * 999 and smeared_ms(E + 12345, Lx) == E + 12345 - 1000 * dl
# validation
for lp in [None, 5, "ab", {(1972, 6, 1)}, [None], [5], [()], [(1972, 6)], [(1972, 6, 1, 1)], [(1972, 6, 0)], [(1972, 6, 2)], [(1972, 6, -2)], [(1972, 6, True)],
           [(True, 6, 1)], [(1972, True, 1)], [(1972.0, 6, 1)], [(1972, 6.0, 1)], [(1972, 6, 1.0)], [("1972", 6, 1)], [(1969, 12, 1)], [(2401, 1, 1)], [(1972, 0, 1)], [(1972, 13, 1)],
           [(1970, 1, 1)], [(1970, 1, -1)], [(1972, 12, 1), (1972, 6, 1)], [(1972, 6, 1), (1972, 6, 1)], [(1972, 6, 1), (1972, 6, -1)], [(1972, 6, 1), (1971, 12, 1)],
           [(1972, 6, 1)] * 2, [(1972, 6, 1), None], [(1972 + i // 12, i % 12 + 1, 1) for i in range(101)]]:
    assert bad(smeared_ms, 5, lp), lp
    assert bad(unsmeared_ms, 5, lp), lp
assert not bad(smeared_ms, 5, [(1970, 2, 1)]) and not bad(smeared_ms, 5, [[1972, 6, 1], (1972, 7, -1), [1972, 8, 1]]) and not bad(smeared_ms, 5, [(2400, 12, -1)])
assert not bad(smeared_ms, 5, [(1970 + i // 12, i % 12 + 1, 1) for i in range(1, 101)])
assert bad(smeared_ms, 5, [(1970 + i // 12, i % 12 + 1, 1) for i in range(0, 100)])
for n in [-1, 10 ** 16 + 1, 1.0, True, "5", None, [5], 5.5]:
    assert bad(smeared_ms, n, []), n
    assert bad(unsmeared_ms, n, L1), n
assert bad(smeared_ms, 5, None) and bad(smeared_ms, -1, None) and bad(unsmeared_ms, -5, [(2401, 1, 1)])

# independent oracle: leap boundaries from datetime, the lag summed leap by leap, inverse by scanning or bisecting a linear forward map
def o_ends(leaps):
    out, cum = [], 0
    for y, m, dl in leaps:
        nd = datetime.date(y + (m == 12), m % 12 + 1, 1)
        cum += dl
        out.append(((nd - datetime.date(1970, 1, 1)).days * 86400000 + 1000 * cum, dl))
    return out

def o_fwd(E, n):
    lag = 0
    for e, dl in E:
        start = e - 1000000
        if n >= e:
            lag += 1000 * dl
        elif n >= start:
            lag += dl * ((n - start) // 1000)
    return n - lag

def o_inv_scan(E, s):
    c = len(E)
    for n in range(max(0, s - 1000 * c - 2), s + 1000 * c + 3):
        if o_fwd(E, n) == s:
            return n
    return None

def o_inv_bisect(E, s):
    lo, hi = 0, s + 1000 * len(E) + 5
    while lo < hi:
        mid = (lo + hi) // 2
        if o_fwd(E, mid) >= s:
            hi = mid
        else:
            lo = mid + 1
    return lo if o_fwd(E, lo) == s else None

random.seed(5002)
def rleaps(kind):
    if kind == 0:
        y = random.randint(1970, 2400)
        m = 2 if random.random() < 0.4 else random.randint(1, 12)
        return [(y, 2 if (y, m) == (1970, 1) else m, random.choice([1, -1]))]
    if kind == 1:
        base = random.randint(1971, 2390)
        return [(base, m, random.choice([1, 1, -1])) for m in sorted(random.sample(range(1, 13), random.randint(2, 6)))]
    ym = sorted(random.sample([(y, m) for y in range(1970, 2401) for m in range(1, 13) if (y, m) != (1970, 1)], random.randint(5, 40)))
    return [(y, m, random.choice([1, 1, -1])) for y, m in ym]

def near(E):
    n = random.choice([random.randint(0, 3 * 10 ** 13), random.randint(0, 10 ** 16)])
    if E and random.random() < 0.85:
        e, dl = random.choice(E)
        n = e + random.choice([-10 ** 6, -10 ** 6 - 1, -10 ** 6 + 1, -999, -1000, -1001, 0, 1, -1, 999, 1000, 1001, random.randint(-10 ** 6 - 2000, 2000), random.randint(-10 ** 6, 0)])
    return max(0, n)

n_plat = n_skip = n_in = 0
for kind in [0, 0, 0, 1, 1, 1, 2, 2, 2, 2, 1, 0]:
    leaps = rleaps(kind)
    E = o_ends(leaps)
    for _ in range(90):
        n = near(E)
        s = o_fwd(E, n)
        assert smeared_ms(n, leaps) == s, (leaps, n, s, smeared_ms(n, leaps))
        n_in += any(0 <= n - (e - 1000000) < 1000000 for e, _ in E)
        if len(leaps) <= 2:
            m = o_inv_scan(E, s)
        else:
            m = o_inv_bisect(E, s)
        assert m is not None and m <= n
        assert unsmeared_ms(s, tuple(tuple(x) for x in leaps)) == m, (leaps, n, s, m)
        n_plat += m < n
        # the value just above: reachable or skipped
        t = s + random.choice([1, 1, 2, -1])
        if t < 0:
            continue
        exp = o_inv_scan(E, t) if len(leaps) <= 1 else o_inv_bisect(E, t)
        if exp is None:
            assert bad(unsmeared_ms, t, leaps), (leaps, t)
            n_skip += 1
        else:
            assert unsmeared_ms(t, leaps) == exp, (leaps, t, exp)
assert n_in > 300 and n_plat > 30 and n_skip > 10, (n_in, n_plat, n_skip)
''', r'''
from bisect import bisect_right


def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _days(y, m):
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5
    return era * 146097 + yoe * 365 + yoe // 4 - yoe // 100 + doy - 719468


def _prep(leaps):
    if not isinstance(leaps, (list, tuple)) or len(leaps) > 100:
        raise ValueError("leaps")
    ends, signs, pref, prev, cum = [], [], [0], None, 0
    for e in leaps:
        if not isinstance(e, (list, tuple)) or len(e) != 3 or not all(_isint(v) for v in e):
            raise ValueError("leap")
        y, m, dl = e
        if not (1970 <= y <= 2400 and 1 <= m <= 12 and dl in (1, -1)) or (y, m) == (1970, 1):
            raise ValueError("leap range")
        if prev is not None and (y, m) <= prev:
            raise ValueError("leap order")
        prev = (y, m)
        cum += dl
        nxt = _days(y, m + 1) if m < 12 else _days(y + 1, 1)
        ends.append(nxt * 86400000 + 1000 * cum)
        signs.append(dl)
        pref.append(1000 * cum)
    return ends, signs, pref


def _fwd(P, n):
    ends, signs, pref = P
    k = bisect_right(ends, n)
    s = n - pref[k]
    if k < len(ends):
        s -= signs[k] * max(0, (n - ends[k] + 1000000) // 1000)
    return s


def _lim(v):
    if not _isint(v) or not 0 <= v <= 10 ** 16:
        raise ValueError("range")
    return v


def smeared_ms(n, leaps):
    P = _prep(leaps)
    return _fwd(P, _lim(n))


def unsmeared_ms(s, leaps):
    P = _prep(leaps)
    _lim(s)
    lo, hi = 0, s + 1000 * len(P[0])
    while lo < hi:
        mid = (lo + hi) // 2
        if _fwd(P, mid) >= s:
            hi = mid
        else:
            lo = mid + 1
    if _fwd(P, lo) != s:
        raise ValueError("skipped")
    return lo
''')


task("v5_03_petri_starts", r'''
Write `petri_starts(places, transitions, until, limit)`, a simulator for a timed Petri net. It
returns the list of firing starts as (time, transition name) tuples, in the order they happen.
- `places`: dict, place name (non-empty str) -> initial tokens, an int 0 <= n <= 10**6.
- `transitions`: list or tuple of 0..50 tuples (name, inputs, outputs, duration, priority,
  servers). name is a unique non-empty str. inputs and outputs are dicts place -> weight, every
  place must exist in `places`, weights are ints 1..1000; inputs must not be empty, outputs may
  be. duration is an int 0..10**12, priority is any int (a smaller number is more urgent),
  servers is an int 1..10**6.
- `until` is an int 0..10**12 and `limit` an int 1..2000. A bool is never an int. Anything
  invalid (wrong types, unknown place, duplicate name, out of range) raises ValueError, and the
  whole input is checked before anything is simulated.
Semantics. A firing is "in progress" from its start at time s until its completion at s +
duration. Time starts at 0 and jumps from one instant to the next instant at which some
firing completes. At an instant t:
1. Every in-progress firing that completes at t completes now and puts its output weights into
   its output places. All completions at t happen before any start at t.
2. Then, repeatedly: a transition is enabled when every input place holds at least the input
   weight AND its number of in-progress firings is less than its servers. Among the enabled
   transitions the one with the smallest priority number starts, ties going to the one earlier
   in the list. Starting takes the input tokens out of the places at once and records
   (t, name). If its duration is 0 the firing completes at the same instant: its outputs are put
   into the places immediately (before the next selection) and it never counts as in progress;
   otherwise it completes at t + duration. After every single start the choice begins again
   from scratch with the new token counts.
3. When nothing is enabled, time jumps to the smallest completion time of an in-progress firing.
Stop when no firing is in progress, or the next instant is greater than `until`, or `limit`
starts have been recorded (the stop is immediate, also in the middle of an instant). Only
starts at times <= until are recorded.
Example: places {"p": 2, "q": 0}; transitions [("a", {"p": 1}, {"q": 1}, 3, 0, 1),
("b", {"q": 1}, {"p": 1}, 0, 0, 1)]; until 10, limit 100. At t=0 a starts (p=1); a is not
enabled again (1 server). At t=3 a completes (q=1), then a starts again (p=0) and b starts and
completes at once (p=1). The result is [(0, "a"), (3, "a"), (3, "b"), (6, "a"), (6, "b"),
(9, "a"), (9, "b")]. Durations reach 10**12, so time must not be simulated unit by unit.
''', r'''
import random, time

def bad(*a):
    try:
        petri_starts(*a)
    except ValueError:
        return True
    return False

def tick_oracle(places, trans, until, limit):
    tok = dict(places)
    m = len(trans)
    order = sorted(range(m), key=lambda i: (trans[i][4], i))
    flights = []          # [end_time, transition index]
    log = []
    for t in range(until + 1):
        done = [f for f in flights if f[0] == t]
        flights = [f for f in flights if f[0] != t]
        for _, i in done:
            for p, w in trans[i][2].items():
                tok[p] += w
        while len(log) < limit:
            ok = [i for i in order
                  if sum(1 for f in flights if f[1] == i) < trans[i][5] and all(tok[p] >= w for p, w in trans[i][1].items())]
            if not ok:
                break
            i = ok[0]
            for p, w in trans[i][1].items():
                tok[p] -= w
            log.append((t, trans[i][0]))
            if trans[i][3] == 0:
                for p, w in trans[i][2].items():
                    tok[p] += w
            else:
                flights.append([t + trans[i][3], i])
        if len(log) >= limit:
            break
        if not flights:
            break
    return log

EX = [("a", {"p": 1}, {"q": 1}, 3, 0, 1), ("b", {"q": 1}, {"p": 1}, 0, 0, 1)]
assert petri_starts({"p": 2, "q": 0}, EX, 10, 100) == [(0, "a"), (3, "a"), (3, "b"), (6, "a"), (6, "b"), (9, "a"), (9, "b")]
assert petri_starts({"p": 2, "q": 0}, tuple(EX), 8, 100) == [(0, "a"), (3, "a"), (3, "b"), (6, "a"), (6, "b")]
assert petri_starts({"p": 2, "q": 0}, EX, 10, 4) == [(0, "a"), (3, "a"), (3, "b"), (6, "a")]
assert petri_starts({"p": 2, "q": 0}, EX, 10, 1) == [(0, "a")]
assert petri_starts({}, [], 5, 5) == []
assert petri_starts({"p": 0}, [("t", {"p": 1}, {}, 1, 0, 1)], 5, 5) == []
# priority, then list position
assert petri_starts({"p": 1}, [("lo", {"p": 1}, {}, 1, 5, 1), ("hi", {"p": 1}, {}, 1, 1, 1)], 9, 9) == [(0, "hi")]
assert petri_starts({"p": 1}, [("x", {"p": 1}, {}, 1, 2, 1), ("y", {"p": 1}, {}, 1, 2, 1)], 9, 9) == [(0, "x")]
assert petri_starts({"p": 1}, [("x", {"p": 1}, {}, 1, 3, 1), ("y", {"p": 1}, {}, 1, -3, 1)], 9, 9) == [(0, "y")]
# all completions at t come before any start at t
T4 = [("a", {"p": 1}, {"q": 1}, 4, 0, 1), ("b", {"q": 1}, {"p": 1}, 4, 0, 1)]
assert petri_starts({"p": 1, "q": 0}, T4, 12, 99) == [(0, "a"), (4, "b"), (8, "a"), (12, "b")]
assert petri_starts({"p": 1, "q": 0}, T4, 11, 99) == [(0, "a"), (4, "b"), (8, "a")]
assert petri_starts({"p": 1, "q": 0}, T4, 0, 99) == [(0, "a")]
# servers
assert petri_starts({"p": 3}, [("w", {"p": 1}, {}, 5, 0, 2)], 100, 10) == [(0, "w"), (0, "w"), (5, "w")]
assert petri_starts({"p": 3}, [("w", {"p": 1}, {}, 5, 0, 3)], 100, 10) == [(0, "w")] * 3
assert petri_starts({"p": 3}, [("z", {"p": 1}, {}, 0, 0, 1)], 100, 10) == [(0, "z")] * 3
# weights: needs at least the weight, takes exactly the weight
assert petri_starts({"p": 3}, [("t", {"p": 2}, {}, 1, 0, 5)], 9, 9) == [(0, "t")]
assert petri_starts({"p": 4}, [("t", {"p": 2}, {}, 1, 0, 5)], 9, 9) == [(0, "t"), (0, "t")]
assert petri_starts({"p": 1, "q": 1}, [("t", {"p": 1, "q": 2}, {}, 1, 0, 5)], 9, 9) == []
# zero-duration cascade in one instant, selection restarts after every start
CY = [("t1", {"s": 1}, {"x": 1}, 0, 2, 1), ("t2", {"x": 1}, {"y": 1}, 0, 1, 1), ("t3", {"y": 1}, {"s": 1}, 0, 3, 1)]
assert petri_starts({"s": 1, "x": 0, "y": 0}, CY, 5, 7) == [(0, "t1"), (0, "t2"), (0, "t3"), (0, "t1"), (0, "t2"), (0, "t3"), (0, "t1")]
assert petri_starts({"s": 1, "x": 0, "y": 0}, CY, 0, 2000) == [(0, n) for _ in range(667) for n in ("t1", "t2", "t3")][:2000]
assert petri_starts({"s": 1, "x": 1, "y": 0}, CY, 5, 5) == [(0, "t2"), (0, "t1"), (0, "t2"), (0, "t3"), (0, "t1")]
# a zero-duration output enables a more urgent transition ahead of an older candidate
r = petri_starts({"s": 1, "z": 1}, [("late", {"z": 1}, {}, 2, 5, 1), ("gen", {"s": 1}, {"z": 1}, 0, 0, 1), ("urg", {"z": 1}, {}, 2, 1, 1)], 9, 9)
assert r == [(0, "gen"), (0, "urg"), (0, "late")], r
# until is inclusive
A = [("a", {"p": 1}, {"p": 1}, 5, 0, 1)]
assert petri_starts({"p": 1}, A, 10, 99) == [(0, "a"), (5, "a"), (10, "a")]
assert petri_starts({"p": 1}, A, 9, 99) == [(0, "a"), (5, "a")]
assert petri_starts({"p": 1}, A, 10, 2) == [(0, "a"), (5, "a")]
# a transition that starts only because a later completion frees its server and tokens
r = petri_starts({"p": 3, "r": 1}, [("m", {"p": 1}, {}, 3, 0, 1), ("k", {"p": 1, "r": 1}, {"r": 1}, 1, 1, 1)], 10, 10)
assert r == [(0, "m"), (0, "k"), (1, "k")], r
# big numbers
E = 10**12
assert petri_starts({"p": 1}, [("a", {"p": 1}, {"p": 1}, E, 0, 1)], E, 5) == [(0, "a"), (E, "a")]
assert petri_starts({"p": 1}, [("a", {"p": 1}, {"p": 1}, E, 0, 1)], E - 1, 5) == [(0, "a")]
H = E // 2
assert petri_starts({"p": 1, "q": 0}, [("a", {"p": 1}, {"q": 1}, H, 0, 1), ("b", {"q": 1}, {"p": 1}, H, 0, 1)], E, 9) == [(0, "a"), (H, "b"), (E, "a")]
assert petri_starts({"p": 2}, [("a", {"p": 1}, {"p": 1}, E - 1, 0, 1), ("b", {"p": 1}, {"p": 1}, 3, 1, 1)], E, 9)[:2] == [(0, "a"), (0, "b")]
for args in [
    ({"p": 1}, [("a", {}, {}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, -1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, E + 1, 0, 1)], 5, 5),
    ({"p": 1}, [("a", {"p": 1}, {}, 1, 0, 0)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, 0, 10**6 + 1)], 5, 5), ({"p": 1}, [("a", {"p": 0}, {}, 1, 0, 1)], 5, 5),
    ({"p": 1}, [("a", {"p": 1001}, {}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {"p": 0}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"zz": 1}, {}, 1, 0, 1)], 5, 5),
    ({"p": 1}, [("a", {"p": 1}, {"zz": 1}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, 0, 1), ("a", {"p": 1}, {}, 1, 0, 1)], 5, 5),
    ({"p": 1}, [("", {"p": 1}, {}, 1, 0, 1)], 5, 5), ({"p": 1}, [(1, {"p": 1}, {}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1.0, 0, 1)], 5, 5),
    ({"p": 1}, [("a", {"p": 1}, {}, True, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, True, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, 0, True)], 5, 5),
    ({"p": 1}, [("a", {"p": 1}, {}, 1, 0.5, 1)], 5, 5), ({"p": 1}, [("a", {"p": True}, {}, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", [("p", 1)], {}, 1, 0, 1)], 5, 5),
    ({"p": 1}, [("a", {"p": 1}, None, 1, 0, 1)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, 0)], 5, 5), ({"p": 1}, [("a", {"p": 1}, {}, 1, 0, 1, 7)], 5, 5),
    ({"p": 1}, ["a"], 5, 5), ({"p": 1}, [None], 5, 5), ({"p": 1}, "a", 5, 5), ({"p": 1}, None, 5, 5), ({"p": 1}, {"a": 1}, 5, 5),
    ({"p": -1}, [], 5, 5), ({"p": 10**6 + 1}, [], 5, 5), ({"p": 1.0}, [], 5, 5), ({"p": True}, [], 5, 5), ({"": 1}, [], 5, 5), ({1: 1}, [], 5, 5),
    ([("p", 1)], [], 5, 5), (None, [], 5, 5), ({"p": 1}, [], -1, 5), ({"p": 1}, [], E + 1, 5), ({"p": 1}, [], 1.0, 5), ({"p": 1}, [], True, 5),
    ({"p": 1}, [], 5, 0), ({"p": 1}, [], 5, 2001), ({"p": 1}, [], 5, True), ({"p": 1}, [], 5, 2.0), ({"p": 1}, [], "5", 5), ({"p": 1}, [], 5, None),
    ({"p": 1}, [("t%d" % i, {"p": 1}, {}, 1, 0, 1) for i in range(51)], 5, 5),
]:
    assert bad(*args), args
assert not bad({"p": 1}, [("t%d" % i, {"p": 1}, {}, 1, 0, 1) for i in range(50)], 5, 5)
assert not bad({"p": 10**6}, [("a", {"p": 1000}, {"p": 1000}, E, -5, 10**6)], E, 2000)

random.seed(5003)
stats = dict(zero=0, cap=0, multi=0, srv=0, same=0)
cases = []
for it in range(420):
    npl = random.randint(1, 4)
    names = ["p%d" % i for i in range(npl)]
    places = {n: random.choice([0, 1, 1, 2, 3, 4]) for n in names}
    tr = []
    for i in range(random.randint(1, 6)):
        ins = {n: random.choice([1, 1, 2]) for n in random.sample(names, random.randint(1, min(2, npl)))}
        outs = {n: random.choice([1, 1, 2]) for n in random.sample(names, random.randint(0, min(3, npl)))}
        tr.append(("t%d" % i, ins, outs, random.choice([0, 0, 1, 2, 3, 4, 6]), random.randint(-1, 2), random.choice([1, 1, 2, 3])))
    until = random.choice([0, 3, 10, 25, 40])
    limit = random.choice([1, 5, 20, 60, 200])
    exp = tick_oracle(places, tr, until, limit)
    got = petri_starts(places, tr if it % 2 else tuple(tr), until, limit)
    assert got == exp, (places, tr, until, limit, got, exp)
    stats["zero"] += any(t[3] == 0 for t in tr) and bool(exp)
    stats["cap"] += len(exp) == limit
    stats["multi"] += len({x for x, _ in exp}) > 2
    stats["srv"] += any(t[5] > 1 for t in tr)
    stats["same"] += any(exp[i][0] == exp[i + 1][0] for i in range(len(exp) - 1))
    cases.append((places, tr, until, limit, exp))
assert stats["zero"] > 120 and stats["cap"] > 40 and stats["multi"] > 35 and stats["same"] > 120, stats
# scaling every duration and the horizon by f scales every start time
for places, tr, until, limit, exp in cases[:150]:
    f = random.choice([7, 10**6, 999999937])
    tr2 = [(n, i, o, d * f, pr, s) for (n, i, o, d, pr, s) in tr]
    assert petri_starts(places, tr2, until * f, limit) == [(t * f, n) for t, n in exp], (places, tr, until, limit, f)
    assert petri_starts(places, tr2, until * f + f - 1, limit) == [(t * f, n) for t, n in exp]
t1 = time.time()
r = petri_starts({"a": 3, "b": 0, "c": 1}, [("x", {"a": 1}, {"b": 1}, E // 3, 1, 2), ("y", {"b": 1, "c": 1}, {"a": 1, "c": 1}, E // 7, 0, 1), ("z", {"b": 2}, {"a": 2}, 0, 2, 1)], E, 2000)
assert len(r) > 4 and all(0 <= a <= E for a, _ in r) and [a for a, _ in r] == sorted(a for a, _ in r)
assert time.time() - t1 < 2
''', r'''
import heapq


def petri_starts(places, transitions, until, limit):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def arcs(d):
        if not isinstance(d, dict):
            raise ValueError("arcs")
        out = []
        for p, w in d.items():
            if p not in places or not isint(w) or not 1 <= w <= 1000:
                raise ValueError("arc")
            out.append((p, w))
        return out

    if not isinstance(places, dict) or not isinstance(transitions, (list, tuple)) or len(transitions) > 50:
        raise ValueError("input")
    if not isint(until) or not 0 <= until <= 10 ** 12 or not isint(limit) or not 1 <= limit <= 2000:
        raise ValueError("bounds")
    for p, n in places.items():
        if not isinstance(p, str) or not p or not isint(n) or not 0 <= n <= 10 ** 6:
            raise ValueError("place")
    names, ins, outs, dur, pri, srv = [], [], [], [], [], []
    for tr in transitions:
        if not isinstance(tr, (list, tuple)) or len(tr) != 6:
            raise ValueError("transition")
        name, i, o, d, pr, s = tr
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("name")
        if not isint(d) or not 0 <= d <= 10 ** 12 or not isint(pr) or not isint(s) or not 1 <= s <= 10 ** 6:
            raise ValueError("numbers")
        ia = arcs(i)
        if not ia:
            raise ValueError("no inputs")
        names.append(name)
        ins.append(ia)
        outs.append(arcs(o))
        dur.append(d)
        pri.append(pr)
        srv.append(s)
    tokens = dict(places)
    order = sorted(range(len(names)), key=lambda k: (pri[k], k))
    busy = [0] * len(names)
    running = []
    log = []
    t = 0
    while True:
        while running and running[0][0] == t:
            _, k = heapq.heappop(running)
            busy[k] -= 1
            for p, w in outs[k]:
                tokens[p] += w
        while len(log) < limit:
            pick = None
            for k in order:
                if busy[k] < srv[k] and all(tokens[p] >= w for p, w in ins[k]):
                    pick = k
                    break
            if pick is None:
                break
            for p, w in ins[pick]:
                tokens[p] -= w
            log.append((t, names[pick]))
            if dur[pick] == 0:
                for p, w in outs[pick]:
                    tokens[p] += w
            else:
                busy[pick] += 1
                heapq.heappush(running, (t + dur[pick], pick))
        if len(log) >= limit or not running or running[0][0] > until:
            break
        t = running[0][0]
    return log
''')


task("v5_04_gate_trace", r'''
Write `gate_trace(gates, stimuli, watch, until)`, an event-driven logic simulator with delta
rounds and inertial delays. It returns {name: [(time, value), ...]} for each name in `watch`.
- `gates`: list or tuple of 0..60 tuples (out, op, ins, delay). out is a non-empty str and no two
  gates share an out. op is one of "AND", "OR", "XOR", "NAND", "NOR", "NOT", "BUF". ins is a
  list or tuple of non-empty strs: exactly one for NOT and BUF, 2 to 4 for the others (a name
  may repeat). delay is an int 0..10**12. The names used anywhere in gates are the known
  signals; a known signal that is no gate's out is a primary input. The graph "input signal ->
  out" must have no cycle (a gate reading its own out is a cycle).
- `stimuli`: list or tuple of 0..200 tuples (time, signal, value): time an int 0..10**12, signal
  a primary input, value the int 0 or 1.
- `watch`: list or tuple of known signal names (repeats allowed, the result is a dict).
  `until`: int 0..10**12. A bool is never an int. Anything invalid, including a cycle, an unknown
  or driven stimulus signal or an unknown watch name, raises ValueError; all of it is checked
  before simulating.
Every signal is 0 at the start. Each gate has at most one pending assignment (out := value, due
at some time). Simulated instants, in increasing order: 0, every stimulus time, and every time
at which an assignment is due, restricted to t <= until. Instant t runs in rounds:
a. Batch. In the first round, first apply the stimuli dated t in list order (a later one for the
   same signal overrides an earlier one), then apply every pending assignment due at t. In the
   later rounds apply the assignments due at t (queued by the previous round with delay 0).
   A signal "changed" in the round if its value after the batch differs from before it.
b. Evaluate. Every gate with an input that changed in this round (in the first round of
   instant 0: every gate) computes its function from the current values. It first deletes its
   own pending assignment, then, if the computed value differs from its out's current value,
   queues (out := value) due at t + delay. A delay of 0 means due in the next round of this same
   instant. Rounds continue while some assignment is due at t.
The trace of a watched signal has (t, v) for each instant t whose final value v (after its last
round) differs from the final value at the previous simulated instant (0 before instant 0).
Example: gates [("n","NOT",["a"],2), ("y","AND",["a","n"],0)], stimuli [(5,"a",1), (6,"a",0)],
watch ["n","y"], until 20: n is 1 from t=2; at 5 y becomes 1 and n would fall at 7, but at 6 the
evaluation of n gives 1 again, so the pending fall is deleted and n stays 1. Result
{"n": [(2, 1)], "y": [(5, 1), (6, 0)]}. Times reach 10**12.
''', r'''
import random

def bad(*a):
    try:
        gate_trace(*a)
    except ValueError:
        return True
    return False

STATS = dict(cancel=0, resched=0, zero=0)

def oracle(gates, stimuli, watch, until):
    """Tick by tick; a snapshot of the signals before each batch decides which gates see a change."""
    sig = {}
    for out, op, ins, d in gates:
        sig[out] = 0
        for s in ins:
            sig[s] = 0
    pend = [[] for _ in gates]        # per gate: list of [due, value]
    def fn(op, v):
        if op == "BUF":
            return v[0]
        if op == "NOT":
            return 1 - v[0]
        r = {"AND": all(v), "NAND": all(v), "OR": any(v), "NOR": any(v), "XOR": sum(v) % 2 == 1}[op]
        r = int(bool(r))
        return 1 - r if op in ("NAND", "NOR") else r
    trace = {w: [] for w in watch}
    prev = dict(sig)
    for t in range(until + 1):
        first = True
        while True:
            snap = dict(sig)
            if first:
                for tt, s, v in stimuli:
                    if tt == t:
                        sig[s] = v
            for k, g in enumerate(gates):
                for e in list(pend[k]):
                    if e[0] == t:
                        sig[g[0]] = e[1]
                        pend[k].remove(e)
            for k, (out, op, ins, d) in enumerate(gates):
                if (t == 0 and first) or any(snap[s] != sig[s] for s in ins):
                    if pend[k]:
                        STATS["cancel"] += 1
                    v = fn(op, [sig[s] for s in ins])
                    old = pend[k]
                    pend[k] = []
                    if v != sig[out]:
                        pend[k].append([t + d, v])
                        if old and old[0][1] == v:
                            STATS["resched"] += 1
                    if d == 0:
                        STATS["zero"] += 1
            first = False
            if not any(e[0] == t for p in pend for e in p):
                break
        for w in watch:
            if sig[w] != prev[w]:
                trace[w].append((t, sig[w]))
                prev[w] = sig[w]
    return trace

G1 = [("n", "NOT", ["a"], 2), ("y", "AND", ["a", "n"], 0)]
S1 = [(5, "a", 1), (6, "a", 0)]
assert gate_trace(G1, S1, ["n", "y"], 20) == {"n": [(2, 1)], "y": [(5, 1), (6, 0)]}
assert gate_trace(tuple(G1), tuple(S1), ("a", "n", "y", "y"), 20) == {"a": [(5, 1), (6, 0)], "n": [(2, 1)], "y": [(5, 1), (6, 0)]}
# a pulse longer than the delay passes: n falls at 7 and rises again at 9
r = gate_trace(G1, [(5, "a", 1), (8, "a", 0)], ["n", "y"], 20)
assert r == {"n": [(2, 1), (7, 0), (10, 1)], "y": [(5, 1), (7, 0)]}, r
# zero-delay glitch inside one instant leaves no trace
GX = [("b", "BUF", ["a"], 0), ("x", "XOR", ["a", "b"], 0)]
assert gate_trace(GX, [(3, "a", 1)], ["x", "b"], 9) == {"x": [], "b": [(3, 1)]}
# ... and a delayed gate that saw the glitch cancels its pending change
GC = [("c1", "BUF", ["a"], 0), ("c2", "BUF", ["c1"], 0), ("g", "XOR", ["a", "c2"], 2)]
assert gate_trace(GC, [(3, "a", 1), (4, "a", 0)], ["g", "c2"], 20) == {"g": [], "c2": [(3, 1), (4, 0)]}
# inertial delay: a short pulse is rejected, the trailing edge restarts nothing
GB = [("b", "BUF", ["a"], 5)]
assert gate_trace(GB, [(0, "a", 1), (3, "a", 0)], ["b"], 30) == {"b": []}
assert gate_trace(GB, [(0, "a", 1), (5, "a", 0)], ["b"], 30) == {"b": [(5, 1), (10, 0)]}
assert gate_trace(GB, [(0, "a", 1), (6, "a", 0)], ["b"], 30) == {"b": [(5, 1), (11, 0)]}
assert gate_trace(GB, [(0, "a", 1), (2, "a", 0), (3, "a", 1)], ["b"], 30) == {"b": [(8, 1)]}
# a new evaluation with the same value as the pending one restarts the delay
GO = [("y", "OR", ["a", "c"], 4)]
assert gate_trace(GO, [(0, "a", 1), (2, "c", 1)], ["y"], 30) == {"y": [(6, 1)]}
assert gate_trace(GO, [(0, "a", 1), (2, "a", 1)], ["y"], 30) == {"y": [(4, 1)]}
assert gate_trace(GO, [(0, "a", 1), (2, "c", 1), (3, "c", 0)], ["y"], 30) == {"y": [(7, 1)]}
# a gate whose inputs did not change keeps its pending assignment
GK = [("y", "BUF", ["a"], 6), ("z", "BUF", ["c"], 0)]
assert gate_trace(GK, [(0, "a", 1), (3, "c", 1)], ["y", "z"], 30) == {"y": [(6, 1)], "z": [(3, 1)]}
# stimulus and due assignment in the same batch
assert gate_trace(GB, [(0, "a", 1), (5, "a", 0)], ["b"], 5) == {"b": [(5, 1)]}
# stimuli at the same time: the later in the list wins; no net change means no evaluation
GZ = [("b", "BUF", ["a"], 0)]
assert gate_trace(GZ, [(3, "a", 1), (3, "a", 0)], ["a", "b"], 9) == {"a": [], "b": []}
assert gate_trace(GZ, [(3, "a", 0), (3, "a", 1)], ["a", "b"], 9) == {"a": [(3, 1)], "b": [(3, 1)]}
assert gate_trace(GZ, [(4, "a", 0)], ["a", "b"], 9) == {"a": [], "b": []}
# instant 0: every gate is evaluated once
assert gate_trace([("n", "NOT", ["a"], 0)], [], ["n"], 0) == {"n": [(0, 1)]}
assert gate_trace([("n", "NOT", ["a"], 1)], [], ["n"], 0) == {"n": []}
assert gate_trace([("n", "NOT", ["a"], 1)], [], ["n"], 1) == {"n": [(1, 1)]}
assert gate_trace([("n", "NOT", ["a"], 0)], [(0, "a", 1)], ["a", "n"], 5) == {"a": [(0, 1)], "n": []}
assert gate_trace([("n", "NAND", ["a", "a"], 0), ("m", "NOR", ["a", "b", "b"], 0), ("x", "XOR", ["a", "b", "c"], 0)], [], ["n", "m", "x"], 0) == {"n": [(0, 1)], "m": [(0, 1)], "x": []}
assert gate_trace([("x", "XOR", ["a", "b", "c"], 0), ("o", "OR", ["a", "b", "c", "d"], 0)], [(1, "a", 1), (1, "b", 1), (1, "c", 1)], ["x", "o"], 1) == {"x": [(1, 1)], "o": [(1, 1)]}
# until is inclusive; later events are not simulated
assert gate_trace(GB, [(0, "a", 1)], ["b"], 4) == {"b": []}
assert gate_trace(GB, [(0, "a", 1)], ["b"], 5) == {"b": [(5, 1)]}
assert gate_trace(GB, [(7, "a", 1), (8, "a", 0), (20, "a", 1)], ["a", "b"], 12) == {"a": [(7, 1), (8, 0)], "b": []}
# empty everything
assert gate_trace([], [], [], 0) == {}
assert gate_trace([], [], [], 10**12) == {}
# a deeper chain and reconvergence: an XOR race across unequal delays gives a pulse
GR = [("p", "BUF", ["a"], 3), ("q", "NOT", ["a"], 1), ("r", "AND", ["p", "q"], 0), ("s", "OR", ["r", "a"], 2)]
assert gate_trace(GR, [(10, "a", 1), (20, "a", 0)], ["p", "q", "r", "s"], 40) == oracle(GR, [(10, "a", 1), (20, "a", 0)], ["p", "q", "r", "s"], 40)
# big numbers
E = 10**12
GE = [("y", "BUF", ["a"], E)]
assert gate_trace(GE, [(0, "a", 1)], ["y"], E) == {"y": [(E, 1)]}
assert gate_trace(GE, [(1, "a", 1)], ["y"], E) == {"y": []}
assert gate_trace(GE, [(E, "a", 1)], ["a", "y"], E) == {"a": [(E, 1)], "y": []}
# z is evaluated at 0 and again at 7, when y rises: the second evaluation deletes the pending rise
assert gate_trace([("y", "BUF", ["a"], 7), ("z", "NOT", ["y"], E - 7)], [(0, "a", 1)], ["y", "z"], E) == {"y": [(7, 1)], "z": []}
assert gate_trace([("y", "BUF", ["a"], 7), ("z", "NOT", ["y"], E - 7)], [(0, "a", 1), (E - 6, "a", 0)], ["y", "z"], E) == {"y": [(7, 1)], "z": []}
assert gate_trace([("y", "BUF", ["a"], 7), ("z", "NOT", ["y"], E - 7)], [(10, "a", 1)], ["y", "z"], E) == {"y": [(17, 1)], "z": []}
assert gate_trace([("y", "BUF", ["a"], 7), ("z", "NOT", ["y"], E - 7)], [(E - 8, "a", 1)], ["y", "z"], E) == {"y": [(E - 1, 1)], "z": [(E - 7, 1)]}
# errors
BADS = [
    ([("a", "NOT", ["a"], 0)], [], [], 0), ([("a", "BUF", ["b"], 0), ("b", "BUF", ["a"], 0)], [], [], 0),
    ([("a", "BUF", ["b"], 1), ("b", "AND", ["c", "a"], 1)], [], [], 0),
    ([("a", "BUF", ["b"], 0), ("a", "BUF", ["c"], 0)], [], [], 0), ([("a", "BUF", ["b"], 0)], [(0, "a", 1)], [], 5),
    ([("a", "BUF", ["b"], 0)], [(0, "zz", 1)], [], 5), ([("a", "BUF", ["b"], 0)], [], ["zz"], 5),
    ([("a", "NOT", ["b", "c"], 0)], [], [], 0), ([("a", "BUF", ["b", "c"], 0)], [], [], 0), ([("a", "AND", ["b"], 0)], [], [], 0),
    ([("a", "XOR", ["b"], 0)], [], [], 0), ([("a", "AND", ["b", "c", "d", "e", "f"], 0)], [], [], 0), ([("a", "AND", [], 0)], [], [], 0),
    ([("a", "MUX", ["b", "c"], 0)], [], [], 0), ([("a", "and", ["b", "c"], 0)], [], [], 0), ([("a", "BUF", ["b"], -1)], [], [], 0),
    ([("a", "BUF", ["b"], 10**12 + 1)], [], [], 0), ([("a", "BUF", ["b"], 1.0)], [], [], 0), ([("a", "BUF", ["b"], True)], [], [], 0),
    ([("a", "BUF", ["b"], "1")], [], [], 0), ([("", "BUF", ["b"], 0)], [], [], 0), ([("a", "BUF", [""], 0)], [], [], 0),
    ([(1, "BUF", ["b"], 0)], [], [], 0), ([("a", "BUF", [2], 0)], [], [], 0), ([("a", "BUF", "b", 0)], [], [], 0),
    ([("a", "BUF", None, 0)], [], [], 0), ([("a", "BUF", ["b"])], [], [], 0), ([("a", "BUF", ["b"], 0, 0)], [], [], 0),
    (["a"], [], [], 0), ([None], [], [], 0), ("abc", [], [], 0), (None, [], [], 0), ({"a": 1}, [], [], 0),
    ([("a", "BUF", ["b"], 0)], [(0, "b", 2)], [], 5), ([("a", "BUF", ["b"], 0)], [(0, "b", -1)], [], 5), ([("a", "BUF", ["b"], 0)], [(0, "b", True)], [], 5),
    ([("a", "BUF", ["b"], 0)], [(0, "b", 1.0)], [], 5), ([("a", "BUF", ["b"], 0)], [(0, "b", "1")], [], 5), ([("a", "BUF", ["b"], 0)], [(-1, "b", 1)], [], 5),
    ([("a", "BUF", ["b"], 0)], [(10**12 + 1, "b", 1)], [], 5), ([("a", "BUF", ["b"], 0)], [(True, "b", 1)], [], 5), ([("a", "BUF", ["b"], 0)], [(0.0, "b", 1)], [], 5),
    ([("a", "BUF", ["b"], 0)], [(0, 7, 1)], [], 5), ([("a", "BUF", ["b"], 0)], [(0, "b")], [], 5), ([("a", "BUF", ["b"], 0)], [(0, "b", 1, 1)], [], 5),
    ([("a", "BUF", ["b"], 0)], [None], [], 5), ([("a", "BUF", ["b"], 0)], None, [], 5), ([("a", "BUF", ["b"], 0)], "x", [], 5),
    ([("a", "BUF", ["b"], 0)], [], None, 5), ([("a", "BUF", ["b"], 0)], [], "a", 5), ([("a", "BUF", ["b"], 0)], [], [1], 5), ([("a", "BUF", ["b"], 0)], [], [["a"]], 5),
    ([("a", "BUF", ["b"], 0)], [], [], -1), ([("a", "BUF", ["b"], 0)], [], [], 10**12 + 1), ([("a", "BUF", ["b"], 0)], [], [], 1.0), ([("a", "BUF", ["b"], 0)], [], [], True),
    ([("a", "BUF", ["b"], 0)], [], [], "5"), ([("a", "BUF", ["b"], 0)], [], [], None),
    ([("g%d" % i, "BUF", ["in"], 0) for i in range(61)], [], [], 0), ([("a", "BUF", ["b"], 0)], [(0, "b", 1)] * 201, [], 5),
]
for args in BADS:
    assert bad(*args), args
assert not bad([("g%d" % i, "BUF", ["in"], 0) for i in range(60)], [], ["g59"], 0)
assert not bad([("a", "BUF", ["b"], 0)], [(0, "b", 1)] * 200, [], 5)
assert not bad([("a", "AND", ("b", "b", "c", "c"), 0)], ((0, "b", 1),), (), 5)
assert not bad([("a", "BUF", ["b"], 0)], [], ["a", "b", "a"], 5)

random.seed(5004)
NAMES = ["a", "b", "c", "d", "e", "f", "g", "h", "i1", "i2", "j10", "j2"]
cases = []
nz = nw = 0
for it in range(320):
    nin = random.randint(1, 3)
    ng = random.randint(1, 9)
    names = random.sample(NAMES, nin + ng)
    prim = names[:nin]
    sigs = list(prim)
    gates = []
    delay_set = random.choice([[0, 0, 1], [0, 1, 2, 3], [1, 2, 2, 5], [0, 0, 0, 0, 1]])
    for nm in names[nin:]:
        op = random.choice(["AND", "OR", "XOR", "NAND", "NOR", "NOT", "BUF", "AND", "XOR", "NOT"])
        k = 1 if op in ("NOT", "BUF") else random.randint(2, 4)
        gates.append((nm, op, [random.choice(sigs[-5:] if random.random() < 0.7 else sigs) for _ in range(k)], random.choice(delay_set)))
        sigs.append(nm)
    random.shuffle(gates)
    known = sorted({x for g in gates for x in [g[0]] + g[2]})
    used = [p for p in prim if p in known]
    stimuli = []
    for _ in range(random.randint(0, 14) if used else 0):
        stimuli.append((random.randint(0, 20), random.choice(used), random.randint(0, 1)))
    until = random.choice([0, 5, 12, 30, 45])
    watch = random.sample(known, random.randint(1, len(known)))
    exp = oracle(gates, stimuli, watch, until)
    got = gate_trace(gates if it % 2 else tuple(gates), stimuli, watch, until)
    assert got == exp, (gates, stimuli, watch, until, got, exp)
    nz += sum(len(v) for v in exp.values()) > 4
    cases.append((gates, stimuli, watch, until, exp))
assert STATS["cancel"] > 120 and STATS["resched"] > 25 and STATS["zero"] > 800 and nz > 70, (STATS, nz)
for gates, stimuli, watch, until, exp in cases[:120]:
    f = random.choice([3, 10**6, 999999937])
    g2 = [(o, op, i, d * f) for o, op, i, d in gates]
    s2 = [(t * f, s, v) for t, s, v in stimuli]
    want = {w: [(t * f, v) for t, v in tr] for w, tr in exp.items()}
    assert gate_trace(g2, s2, watch, until * f) == want, (gates, stimuli, until, f)
# larger circuit, all wired forward, compared with the oracle
for _ in range(3):
    prim = ["a", "b", "c", "d"]
    sigs = list(prim)
    gates = []
    for i in range(40):
        op = random.choice(["AND", "OR", "XOR", "NAND", "NOR", "NOT", "BUF"])
        k = 1 if op in ("NOT", "BUF") else random.randint(2, 4)
        gates.append(("w%d" % i, op, [random.choice(sigs) for _ in range(k)], random.choice([0, 1, 2, 3])))
        sigs.append("w%d" % i)
    known = sorted({x for g in gates for x in [g[0]] + g[2]})
    used = [p for p in prim if p in known]
    stimuli = [(random.randint(0, 30), random.choice(used), random.randint(0, 1)) for _ in range(30)]
    assert gate_trace(gates, stimuli, known, 60) == oracle(gates, stimuli, known, 60)
''', r'''
import heapq

OPS = ("AND", "OR", "XOR", "NAND", "NOR", "NOT", "BUF")


def gate_trace(gates, stimuli, watch, until):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def isname(s):
        return isinstance(s, str) and s != ""

    if not isinstance(gates, (list, tuple)) or len(gates) > 60:
        raise ValueError("gates")
    if not isinstance(stimuli, (list, tuple)) or len(stimuli) > 200 or not isinstance(watch, (list, tuple)):
        raise ValueError("input")
    if not isint(until) or not 0 <= until <= 10 ** 12:
        raise ValueError("until")
    outs, ops, ins, delays = [], [], [], []
    driver = {}
    known = set()
    for g in gates:
        if not isinstance(g, (list, tuple)) or len(g) != 4:
            raise ValueError("gate")
        out, op, gi, d = g
        if not isname(out) or out in driver or op not in OPS or not isint(d) or not 0 <= d <= 10 ** 12:
            raise ValueError("gate")
        if not isinstance(gi, (list, tuple)) or not all(isname(s) for s in gi):
            raise ValueError("ins")
        if not 1 <= len(gi) <= 4 or (len(gi) == 1) != (op in ("NOT", "BUF")):
            raise ValueError("arity")
        driver[out] = len(outs)
        outs.append(out)
        ops.append(op)
        ins.append(list(gi))
        delays.append(d)
        known.add(out)
        known.update(gi)
    n = len(outs)
    readers = {s: [] for s in known}
    indeg = [0] * n
    for k in range(n):
        for s in ins[k]:
            readers[s].append(k)
            if s in driver:
                indeg[k] += 1
    stim = {}
    for st in stimuli:
        if not isinstance(st, (list, tuple)) or len(st) != 3:
            raise ValueError("stimulus")
        t, s, v = st
        if not isint(t) or not 0 <= t <= 10 ** 12 or not isname(s) or s not in known or s in driver or not isint(v) or v not in (0, 1):
            raise ValueError("stimulus")
        stim.setdefault(t, []).append((s, v))
    if not all(isname(w) and w in known for w in watch):
        raise ValueError("watch")
    ready = [k for k in range(n) if indeg[k] == 0]
    for k in ready:
        for r in readers[outs[k]]:
            indeg[r] -= 1
            if indeg[r] == 0:
                ready.append(r)
    if len(ready) < n:
        raise ValueError("cycle")

    def f(k):
        v = [val[s] for s in ins[k]]
        op = ops[k]
        if op == "BUF":
            return v[0]
        if op == "NOT":
            return 1 - v[0]
        if op in ("AND", "NAND"):
            r = int(all(v))
        elif op in ("OR", "NOR"):
            r = int(any(v))
        else:
            r = sum(v) % 2
        return 1 - r if op in ("NAND", "NOR") else r

    val = {s: 0 for s in known}
    last = dict(val)
    trace = {w: [] for w in watch}
    pend = {}
    times = [0] + list(stim)
    heapq.heapify(times)
    done_t = -1
    while times:
        t = heapq.heappop(times)
        if t > until:
            break
        if t == done_t:
            continue
        done_t = t
        rnd = 0
        while True:
            before = {}
            if rnd == 0:
                for s, v in stim.get(t, []):
                    before.setdefault(s, val[s])
                    val[s] = v
            for k in [k for k, (d, _) in pend.items() if d == t]:
                before.setdefault(outs[k], val[outs[k]])
                val[outs[k]] = pend.pop(k)[1]
            changed = {s for s, b in before.items() if val[s] != b}
            todo = range(n) if (t == 0 and rnd == 0) else sorted({k for s in changed for k in readers[s]})
            for k in todo:
                pend.pop(k, None)
                v = f(k)
                if v != val[outs[k]]:
                    pend[k] = (t + delays[k], v)
                    if delays[k]:
                        heapq.heappush(times, t + delays[k])
            rnd += 1
            if not any(d == t for d, _ in pend.values()):
                break
        for w in trace:
            if val[w] != last[w]:
                trace[w].append((t, val[w]))
                last[w] = val[w]
    return trace
''')


task("v5_05_weak_poly", r'''
Write `weak_infer(term) -> str`: the principal type of a term of a small ML-like language with n-ary
functions, lists and mutable references, by Hindley-Milner inference with the value restriction.
Raise ValueError when the term is ill-typed or malformed.
Terms are tuples whose first item is a str tag: ("int", n) with n an int (not a bool); ("bool", b)
with a bool; ("str", s) with a str; ("unit",); ("var", name); ("fn", params, body) with params a
non-empty tuple of distinct names (a list is malformed); ("call", f, args) with args a non-empty tuple
of terms; ("let", name, e1, e2); ("letrec", name, e1, e2); ("nil",); ("cons", h, t);
("match", s, e_nil, hn, tn, e_cons); ("ref", e); ("get", r); ("set", r, e). Names are non-empty str.
A non-tuple, an empty tuple, a tag that is not a str, an unknown tag, a wrong length or a wrong field
type is malformed.
Types: Int, Bool, Str, Unit, List<T>, Ref<T> and n-ary function types (T1, ..., Tn) -> R, n >= 1.
A call needs exactly the function's arity (no currying). "cons" needs t : List of h's type; nil is a
List of a fresh variable. "match" needs s : List<A>; it is e_nil when s is empty, else e_cons with
hn : A and tn : List<A>; both branches have one type; hn and tn must differ. "get" reads, "set"
needs e to have the content type of r and has type Unit. The initial environment (shadowable) is
plus: (Int, Int) -> Int; eq: (a, a) -> Bool; size: Str -> Int.
Binding: fn parameters and match-bound names are monomorphic. In "let" name is not visible in e1.
"letrec" requires e1 to be a "fn" term (else ValueError); name is visible in e1 with a monomorphic
type, and e2 sees it generalized. Generalizing means quantifying the type variables of e1's type that
do not occur free in the environment. "letrec" always generalizes. "let" generalizes only if e1 is a
syntactic value: an int, bool, str, unit, var, fn or nil term, or a cons whose h and t are both values
(recursively). For any other e1 its type variables stay monomorphic and are shared by every use of
name. Inner bindings shadow outer ones. ValueError also covers an unbound variable, a type mismatch
(arity included) and an infinite type.
The result prints type variables as t1, t2, ... in order of first appearance, reading the printed
string left to right. A function type with one parameter prints "P -> R", with P in parentheses
when P is itself a function type; with n >= 2 parameters it prints "(P1, P2) -> R", each Pi bare.
R is always bare, and List<T> / Ref<T> print T bare.
Examples: ("fn", ("x",), ("var", "x")) is "t1 -> t1"; \f x. f(x) is "(t1 -> t2, t1) -> t2";
\f. \(x, y). f(x, y) is "((t1, t2) -> t3) -> (t1, t2) -> t3"; let r = ref(nil) in r is "Ref<List<t1>>".
With f = (\x. x)(\y. y), a call and not a value, using f at Int and at Bool is an error; with
f = \y. y it is accepted.
''', r'''
import random

def I(n): return ("int", n)
def Bo(b): return ("bool", b)
def S(s): return ("str", s)
def V(x): return ("var", x)
def F(ps, body): return ("fn", tuple(ps.split()), body)
def C(f, *a): return ("call", f, tuple(a))
def LET(n, a, b): return ("let", n, a, b)
def LR(n, a, b): return ("letrec", n, a, b)
def CONS(h, t): return ("cons", h, t)
def MATCH(s, en, h, t, ec): return ("match", s, en, h, t, ec)
def REF(e): return ("ref", e)
def GET(r): return ("get", r)
def SET(r, e): return ("set", r, e)
UNIT, NIL = ("unit",), ("nil",)
x, y, f, g, r, h, t, l = [V(c) for c in "xyfgrhtl"]
PLUS, EQ, SIZE = V("plus"), V("eq"), V("size")
ID = F("x", x)
TWO = F("a b", UNIT)

def bad(term):
    try:
        weak_infer(term)
    except ValueError:
        return True
    return False

def ok(term, want):
    got = weak_infer(term)
    assert got == want, (term, got, want)

ok(ID, "t1 -> t1")
ok(F("x y", x), "(t1, t2) -> t1")
ok(F("x y", y), "(t1, t2) -> t2")
ok(F("x", F("y", x)), "t1 -> t2 -> t1")
ok(F("f x", C(f, x)), "(t1 -> t2, t1) -> t2")
ok(F("f", C(f, ID)), "((t1 -> t1) -> t2) -> t2")
ok(F("f g", F("x", C(f, C(g, x)))), "(t1 -> t2, t3 -> t1) -> t3 -> t2")
ok(F("f", C(f, I(1), Bo(True))), "((Int, Bool) -> t1) -> t1")
ok(F("x", F("y z", x)), "t1 -> (t2, t3) -> t1")
ok(F("f", F("x y", C(f, x, y))), "((t1, t2) -> t3) -> (t1, t2) -> t3")
ok(F("x y", C(y, x)), "(t1, t1 -> t2) -> t2")
ok(F("f", F("x", C(f, x))), "(t1 -> t2) -> t1 -> t2")
ok(F("a b c d e f g h i j k l", V("k")), "(t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12) -> t11")
ok(F("a b c d e f g h i j k l", V("l")), "(t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12) -> t12")
ok(I(3), "Int"); ok(I(-7), "Int"); ok(Bo(False), "Bool"); ok(S(""), "Str"); ok(UNIT, "Unit")
ok(PLUS, "(Int, Int) -> Int"); ok(EQ, "(t1, t1) -> Bool"); ok(SIZE, "Str -> Int")
ok(NIL, "List<t1>"); ok(CONS(I(1), NIL), "List<Int>"); ok(CONS(NIL, NIL), "List<List<t1>>")
assert bad(CONS(I(1), CONS(Bo(True), NIL))) and bad(CONS(I(1), I(2)))
ok(REF(NIL), "Ref<List<t1>>"); ok(F("x", REF(x)), "t1 -> Ref<t1>"); ok(REF(ID), "Ref<t1 -> t1>")
ok(F("r", SET(r, I(1))), "Ref<Int> -> Unit"); ok(F("r", GET(r)), "Ref<t1> -> t1")
ok(F("r s", SET(r, GET(V("s")))), "(Ref<t1>, Ref<t1>) -> Unit")
ok(CONS(F("a b", V("a")), NIL), "List<(t1, t2) -> t1>")
ok(C(PLUS, I(1), I(2)), "Int"); ok(C(SIZE, S("ab")), "Int"); ok(C(EQ, I(1), I(2)), "Bool")
ok(C(EQ, ID, ID), "Bool")
assert bad(C(PLUS, I(1))) and bad(C(PLUS, I(1), I(2), I(3))) and bad(C(PLUS, I(1), Bo(True))) and bad(C(SIZE, I(1)))
assert bad(C(EQ, I(1), Bo(True))) and bad(C(I(1), I(2))) and bad(C(F("x y", x), I(1)))
ok(C(F("x y", x), I(1), Bo(True)), "Int")
ok(C(C(F("x", F("y", x)), I(1)), Bo(True)), "Int")
assert bad(C(F("x", F("y", x)), I(1), Bo(True)))
# let polymorphism and the value restriction
ok(LET("id", ID, C(TWO, C(V("id"), I(1)), C(V("id"), Bo(True)))), "Unit")
ok(LET("id", ID, V("id")), "t1 -> t1")
fv = LET("f", C(F("x", x), ID), C(TWO, C(f, I(1)), C(f, Bo(True))))
assert bad(fv)
ok(LET("f", C(F("x", x), ID), C(f, I(1))), "Int")
ok(LET("f", C(F("x", x), ID), f), "t1 -> t1")
ok(LET("n", NIL, C(TWO, CONS(I(1), V("n")), CONS(Bo(True), V("n")))), "Unit")
assert bad(LET("r", REF(NIL), C(TWO, SET(r, CONS(I(1), NIL)), SET(r, CONS(Bo(True), NIL)))))
ok(LET("r", REF(NIL), C(F("u", GET(r)), SET(r, CONS(I(1), NIL)))), "List<Int>")
ok(LET("r", REF(NIL), r), "Ref<List<t1>>")
ok(LET("l", CONS(NIL, NIL), C(TWO, C(EQ, V("l"), CONS(CONS(I(1), NIL), NIL)), C(EQ, V("l"), CONS(CONS(Bo(True), NIL), NIL)))), "Unit")
assert bad(LET("l", CONS(C(ID, NIL), NIL), C(TWO, C(EQ, V("l"), CONS(CONS(I(1), NIL), NIL)), C(EQ, V("l"), CONS(CONS(Bo(True), NIL), NIL)))))
ok(LET("l", CONS(ID, CONS(F("z", V("z")), NIL)), V("l")), "List<t1 -> t1>")
assert bad(LET("l", CONS(NIL, CONS(C(ID, NIL), NIL)), C(TWO, C(EQ, V("l"), CONS(CONS(I(1), NIL), NIL)), C(EQ, V("l"), CONS(CONS(Bo(True), NIL), NIL)))))
ok(LET("l", CONS(NIL, CONS(NIL, NIL)), C(TWO, C(EQ, V("l"), CONS(CONS(I(1), NIL), NIL)), C(EQ, V("l"), CONS(CONS(Bo(True), NIL), NIL)))), "Unit")
ok(LET("l", CONS(ID, CONS(C(ID, ID), NIL)), V("l")), "List<t1 -> t1>")
# a weak variable must not be generalized by a later, inner let
assert bad(LET("r", REF(NIL), LET("g", F("y", GET(r)), C(TWO, C(EQ, C(g, UNIT), CONS(I(1), NIL)), C(EQ, C(g, UNIT), CONS(Bo(True), NIL))))))
ok(LET("r", REF(NIL), LET("g", F("y", GET(r)), C(g, UNIT))), "List<t1>")
ok(F("a", LET("r", REF(NIL), GET(r))), "t1 -> List<t2>")
ok(LET("k", F("a", LET("r", REF(NIL), GET(r))), C(TWO, C(EQ, C(V("k"), I(1)), CONS(I(1), NIL)), C(EQ, C(V("k"), I(1)), CONS(Bo(True), NIL)))), "Unit")
ok(F("x", LET("y", x, y)), "t1 -> t1")
assert bad(F("x", LET("y", x, C(TWO, C(y, I(1)), C(y, Bo(True))))))
assert bad(F("f", LET("g", f, C(TWO, C(g, I(1)), C(g, Bo(True))))))
ok(F("f", LET("g", f, C(TWO, C(g, I(1)), C(g, I(2))))), "(Int -> t1) -> Unit")
ok(F("x", LET("f", F("y", x), C(TWO, C(f, I(1)), C(f, Bo(True))))), "t1 -> Unit")
ok(F("x", LET("p", C(F("a", V("a")), x), V("p"))), "t1 -> t1")
assert bad(F("x", LET("p", C(F("a", V("a")), x), C(TWO, C(V("p"), I(1)), C(V("p"), Bo(True))))))
# letrec
LEN = LR("len", F("l", MATCH(l, I(0), "h", "t", C(PLUS, I(1), C(V("len"), t)))), V("len"))
ok(LEN, "List<t1> -> Int")
MAP = LR("map", F("f l", MATCH(l, NIL, "h", "t", CONS(C(f, h), C(V("map"), f, t)))), V("map"))
ok(MAP, "(t1 -> t2, List<t1>) -> List<t2>")
ok(LR("f", F("x", C(f, x)), f), "t1 -> t2")
ok(LR("id", ID, C(TWO, C(V("id"), I(1)), C(V("id"), Bo(True)))), "Unit")
assert bad(LR("f", F("x", C(TWO, C(f, I(1)), C(f, Bo(True)))), f))
assert bad(LR("x", I(1), x)) and bad(LR("x", NIL, x)) and bad(LR("x", C(ID, ID), x)) and bad(LR("x", LET("a", ID, ID), x))
assert bad(LR("f", F("x", C(f, f)), f))
assert bad(LET("f", F("x", C(f, x)), f))
ok(LET("f", ID, LET("f", F("x", C(f, x)), V("f"))), "t1 -> t1")
ok(LR("f", F("x", x), LR("f", F("x y", y), V("f"))), "(t1, t2) -> t2")
ok(LR("go", F("n l", MATCH(l, V("n"), "h", "t", C(V("go"), C(PLUS, V("n"), V("h")), t))), V("go")), "(Int, List<Int>) -> Int")
ok(LR("app", F("a b", MATCH(V("a"), V("b"), "h", "t", CONS(h, C(V("app"), t, V("b"))))), V("app")), "(List<t1>, List<t1>) -> List<t1>")
assert bad(LR("f", F("x", F("y", C(f, y, x))), f))
# shadowing and match
ok(F("x", F("x", x)), "t1 -> t2 -> t2")
assert bad(F("x x", x)) and bad(F("x y x", x))
ok(LET("plus", ID, V("plus")), "t1 -> t1")
ok(LET("eq", NIL, V("eq")), "List<t1>")
ok(F("plus", C(V("plus"), I(1))), "(Int -> t1) -> t1")
ok(MATCH(NIL, I(1), "h", "t", h), "Int")
ok(MATCH(NIL, NIL, "h", "t", CONS(h, t)), "List<t1>")
ok(F("l", MATCH(l, I(0), "h", "t", h)), "List<Int> -> Int")
ok(F("l", MATCH(l, UNIT, "l", "t", l)), "List<Unit> -> Unit")
ok(F("l", MATCH(l, I(0), "h", "t", C(PLUS, h, I(2)))), "List<Int> -> Int")
assert bad(MATCH(NIL, I(1), "h", "h", I(2))) and bad(MATCH(I(1), I(1), "h", "t", I(2)))
assert bad(MATCH(NIL, I(1), "h", "t", Bo(True))) and bad(MATCH(NIL, I(1), "h", "", I(2)))
assert bad(F("l", MATCH(l, I(0), "h", "t", t)))
assert bad(F("x", C(x, x))) and bad(F("x", CONS(x, x))) and bad(F("r", SET(r, r))) and bad(F("x", C(x, x, x)))
assert bad(LET("x", V("x"), I(1))) and bad(V("zzz")) and bad(LET("f", F("x", C(f, x)), I(1)))
ok(LET("x", I(1), LET("x", Bo(True), V("x"))), "Bool")
ok(F("x", MATCH(NIL, x, "x", "t", V("x"))), "t1 -> t1")
# malformed terms
for w in [[], None, "x", 5, (), [ "int", 1 ], ("int", True), ("int", 1.5), ("int", "1"), ("int",), ("bool", 1), ("bool", None), ("str", 5), ("str", b"a"),
          ("unit", 1), ("nil", 1), ("var", 3), ("var", ""), ("var",), ("zzz",), ("zzz", 1), (1, 2), ([], 1), (None,), ("fn",), ("fn", ("x",)),
          ("fn", ["x"], x), ("fn", (), I(1)), ("fn", ("x", ""), I(1)), ("fn", ("x", 1), I(1)), ("fn", "x", x), ("fn", ("x", "x"), x), ("fn", ("x",), None),
          ("fn", ("x",), x, x), ("fn", ("f",), ("call", f, ())), ("call", ID), ("call", ID, [I(1)]), ("call", ID, ()), ("call", ID, I(1)), ("call", ID, (I(1),), 3), ("call", ID, (None,)),
          ("let", "x", I(1)), ("let", "", I(1), I(2)), ("let", 1, I(1), I(2)), ("let", "x", I(1), I(2), I(3)), ("letrec", "f", ID),
          ("letrec", "", ID, I(1)), ("cons", I(1)), ("cons", I(1), NIL, NIL), ("match", NIL, I(1), "h", "t"), ("match", NIL, I(1), "h", "t", I(1), I(2)),
          ("match", NIL, I(1), 1, "t", I(1)), ("match", NIL, I(1), "h", None, I(1)), ("ref",), ("ref", I(1), I(2)), ("get",), ("set", REF(I(1))),
          ("set", REF(I(1)), I(1), I(1)), ("get", I(1)), ("set", I(1), I(1)), ("set", REF(I(1)), Bo(True))]:
    assert bad(w), w

# deep sharing: a let chain that blows up if lets are inlined
chain = V("f40")
for i in range(40, 0, -1):
    chain = LET("f%d" % i, F("x", C(V("f%d" % (i - 1)), C(V("f%d" % (i - 1)), x))), chain)
chain = LET("f0", ID, chain)
ok(chain, "t1 -> t1")
chain2 = C(V("f40"), I(1))
for i in range(40, 0, -1):
    chain2 = LET("f%d" % i, F("x", C(V("f%d" % (i - 1)), C(V("f%d" % (i - 1)), x))), chain2)
chain2 = LET("f0", F("x", C(PLUS, x, I(1))), chain2)
ok(chain2, "Int")
# the same chain with a non-value start: every fi stays monomorphic, and the types still unify
mono = C(V("f20"), I(1))
for i in range(20, 0, -1):
    mono = LET("f%d" % i, F("x", C(V("f%d" % (i - 1)), C(V("f%d" % (i - 1)), x))), mono)
mono = LET("f0", C(F("z", V("z")), ID), mono)
ok(mono, "Int")

# oracle: algorithm W with explicit substitutions (value restriction switchable)
cnt = [0]
def fresh():
    cnt[0] += 1
    return ("v", cnt[0])

def ap(s, t):
    if t[0] == "v":
        return ap(s, s[t[1]]) if t[1] in s else t
    return (t[0],) + tuple(ap(s, c) for c in t[1:])

def ftv(t, acc=None):
    acc = set() if acc is None else acc
    if t[0] == "v":
        acc.add(t[1])
    for c in t[1:] if t[0] != "v" else ():
        ftv(c, acc)
    return acc

def uni(a, b, s):
    a, b = ap(s, a), ap(s, b)
    if a == b:
        return s
    if a[0] == "v" or b[0] == "v":
        if a[0] != "v":
            a, b = b, a
        if a[1] in ftv(b):
            raise ValueError("occurs")
        s = {k: ap({a[1]: b}, v) for k, v in s.items()}
        s[a[1]] = b
        return s
    if a[0] != b[0] or len(a) != len(b):
        raise ValueError("mismatch")
    for p, q in zip(a[1:], b[1:]):
        s = uni(p, q, s)
    return s

PRIM = {"plus": ((), ("fn", ("Int",), ("Int",), ("Int",))), "size": ((), ("fn", ("Int",), ("Str",))),
        "eq": ((-1,), ("fn", ("Bool",), ("v", -1), ("v", -1)))}
SHAPES = {"int": 2, "bool": 2, "str": 2, "unit": 1, "var": 2, "fn": 3, "call": 3, "let": 4, "letrec": 4, "nil": 1,
          "cons": 3, "match": 6, "ref": 2, "get": 2, "set": 3}
LITS = {"int": (int, "Int"), "bool": (bool, "Bool"), "str": (str, "Str")}
def nm(v):
    if not isinstance(v, str) or not v:
        raise ValueError("name")
    return v

def is_value(e):
    stack = [e]
    while stack:
        q = stack.pop()
        if q[0] in ("int", "bool", "str", "unit", "var", "fn", "nil"):
            continue
        if q[0] != "cons":
            return False
        stack += [q[1], q[2]]
    return True

def W(env, e, s, vr):
    if not isinstance(e, tuple) or not e or not isinstance(e[0], str) or SHAPES.get(e[0]) != len(e):
        raise ValueError("shape")
    k = e[0]
    if k in LITS:
        if type(e[1]) is not LITS[k][0]:
            raise ValueError("lit")
        return (LITS[k][1],), s
    if k == "unit":
        return ("Unit",), s
    if k == "nil":
        return ("List", fresh()), s
    if k == "var":
        sc = env.get(nm(e[1]))
        if sc is None:
            raise ValueError("unbound")
        return ap({v: fresh() for v in sc[0]}, sc[1]), s
    if k == "fn":
        ps = e[1]
        if not isinstance(ps, tuple) or not ps:
            raise ValueError("params")
        for p in ps:
            nm(p)
        if len(set(ps)) < len(ps):
            raise ValueError("dup")
        vs = [fresh() for _ in ps]
        env2 = dict(env)
        for p, v in zip(ps, vs):
            env2[p] = ((), v)
        t, s = W(env2, e[2], s, vr)
        return ("fn", t) + tuple(vs), s
    if k == "call":
        if not isinstance(e[2], tuple) or not e[2]:
            raise ValueError("args")
        tf, s = W(env, e[1], s, vr)
        ts = []
        for a in e[2]:
            ta, s = W(env, a, s, vr)
            ts.append(ta)
        r = fresh()
        s = uni(tf, ("fn", r) + tuple(ts), s)
        return ap(s, r), s
    if k == "cons":
        th, s = W(env, e[1], s, vr)
        tt, s = W(env, e[2], s, vr)
        s = uni(tt, ("List", th), s)
        return ap(s, tt), s
    if k == "ref":
        t, s = W(env, e[1], s, vr)
        return ("Ref", t), s
    if k in ("get", "set"):
        t, s = W(env, e[1], s, vr)
        a = fresh()
        s = uni(t, ("Ref", a), s)
        if k == "get":
            return ap(s, a), s
        t2, s = W(env, e[2], s, vr)
        s = uni(a, t2, s)
        return ("Unit",), s
    if k == "match":
        nm(e[3]); nm(e[4])
        if e[3] == e[4]:
            raise ValueError("names")
        ts, s = W(env, e[1], s, vr)
        a = fresh()
        s = uni(ts, ("List", a), s)
        t1, s = W(env, e[2], s, vr)
        env2 = dict(env)
        env2[e[3]] = ((), a)
        env2[e[4]] = ((), ("List", a))
        t2, s = W(env2, e[5], s, vr)
        s = uni(t1, t2, s)
        return ap(s, t1), s
    nm(e[1])
    def gen(t, s):
        t = ap(s, t)
        used = set()
        for sc in env.values():
            used |= ftv(ap(s, sc[1])) - set(sc[0])
        return tuple(sorted(ftv(t) - used)), t
    env2 = dict(env)
    if k == "let":
        t1, s = W(env, e[2], s, vr)
        env2[e[1]] = gen(t1, s) if (is_value(e[2]) or not vr) else ((), ap(s, t1))
    else:
        if not isinstance(e[2], tuple) or not e[2] or e[2][0] != "fn":
            raise ValueError("letrec")
        a = fresh()
        env3 = dict(env)
        env3[e[1]] = ((), a)
        t1, s = W(env3, e[2], s, vr)
        s = uni(a, t1, s)
        env2[e[1]] = gen(t1, s)
    return W(env2, e[3], s, vr)

def show(t):
    order = []
    def walk(t):
        if t[0] == "v":
            if t[1] not in order:
                order.append(t[1])
        elif t[0] == "fn":
            for p in t[2:]:
                walk(p)
            walk(t[1])
        else:
            for c in t[1:]:
                walk(c)
    walk(t)
    names = {v: "t%d" % (i + 1) for i, v in enumerate(order)}
    def go(t, paren=False):
        if t[0] == "v":
            return names[t[1]]
        if len(t) == 1:
            return t[0]
        if t[0] != "fn":
            return "%s<%s>" % (t[0], go(t[1]))
        ps = [go(p, len(t) == 3) for p in t[2:]]
        left = ps[0] if len(ps) == 1 else "(" + ", ".join(ps) + ")"
        out = left + " -> " + go(t[1])
        return "(" + out + ")" if paren else out
    return go(t)

def oracle(e, vr=True):
    t, s = W(PRIM, e, {}, vr)
    return show(ap(s, t))

random.seed(5005)
NAMES = ["x", "y", "f", "g", "r", "plus", "eq", "size"]
JUNK = [None, 3, "x", (), ("zzz",), ("int", True), ("var", ""), ("fn", ["x"], I(1))]
def gen(d, scope):
    c = random.random()
    if d == 0 or c < 0.12:
        c = random.random()
        if c < 0.55 and scope:
            return V(random.choice(scope))
        if c < 0.62:
            return V(random.choice(["plus", "eq", "size"]))
        if c < 0.64:
            return random.choice(JUNK)
        return random.choice([I(random.randint(-2, 2)), Bo(random.random() < 0.5), S("s"), UNIT, NIL, NIL])
    c = random.random()
    if c < 0.2:
        ps = random.sample(["x", "y", "f", "g"], random.choice([1, 1, 2, 3]))
        return ("fn", tuple(ps), gen(d - 1, scope + ps))
    if c < 0.42:
        return ("call", gen(d - 1, scope), tuple(gen(d - 1, scope) for _ in range(random.choice([1, 1, 2, 2, 3]))))
    if c < 0.55:
        n = random.choice(["x", "y", "f", "g"])
        e1 = gen(d - 1, scope)
        return LET(n, e1, gen(d - 1, scope + [n]))
    if c < 0.63:
        n = random.choice(["f", "g", "x"])
        ps = random.sample(["x", "y", "r"], random.choice([1, 2]))
        e1 = F(" ".join(ps), gen(d - 1, scope + [n] + ps)) if random.random() < 0.93 else gen(d - 1, scope)
        return LR(n, e1, gen(d - 1, scope + [n]))
    if c < 0.73:
        return CONS(gen(d - 1, scope), gen(d - 1, scope))
    if c < 0.81:
        a, b = random.choice([("h", "t"), ("h", "t"), ("x", "y"), ("x", "x")])
        return MATCH(gen(d - 1, scope), gen(d - 1, scope), a, b, gen(d - 1, scope + [a, b]))
    if c < 0.89:
        return REF(gen(d - 1, scope))
    if c < 0.95:
        return GET(gen(d - 1, scope))
    return SET(gen(d - 1, scope), gen(d - 1, scope))

def lit():
    return random.choice([I(1), Bo(True), S("s"), UNIT])

def weak_pattern(d):
    n = random.choice(["x", "y", "f"])
    fam = random.randrange(6)
    a, b = lit(), (lit() if random.random() < 0.6 else None)
    b = a if b is None else b
    if fam == 0:
        e1, u1, u2 = REF(NIL), SET(V(n), CONS(a, NIL)), SET(V(n), CONS(b, NIL))
    elif fam == 1:
        e1, u1, u2 = C(F("a", V("a")), ID), C(V(n), a), C(V(n), b)
    elif fam == 2:
        e1, u1, u2 = random.choice([CONS(C(ID, NIL), NIL), CONS(NIL, CONS(C(ID, NIL), NIL))]), C(EQ, V(n), CONS(CONS(a, NIL), NIL)), C(EQ, V(n), CONS(CONS(b, NIL), NIL))
    elif fam == 3:
        e1, u1, u2 = CONS(ID, CONS(F("a", V("a")), NIL)), C(EQ, V(n), CONS(ID, NIL)), C(EQ, V(n), CONS(F("c", gen(d, ["c"])), NIL))
    elif fam == 4:
        e1, u1, u2 = REF(ID), C(GET(V(n)), a), C(GET(V(n)), b)
    else:
        e1 = random.choice([NIL, ID, CONS(NIL, NIL), V("eq")])
        u1, u2 = C(EQ, C(V(n), a) if e1 in (ID,) else V(n), gen(d, [n])), gen(d, [n])
    body = C(TWO, u1, u2)
    if random.random() < 0.3:
        m = random.choice(["g", "r"])
        body = LET(m, F("q", body), C(V(m), I(1)))
    if random.random() < 0.25:
        body = F("z", body)
    return LET(n, e1, body)

nok = nerr = ndiff = 0
for _ in range(2500):
    term = weak_pattern(random.randint(0, 2)) if random.random() < 0.3 else gen(random.randint(1, 6), [])
    try:
        exp = oracle(term)
    except ValueError:
        exp = None
    try:
        got = weak_infer(term)
    except ValueError:
        got = None
    assert got == exp, (term, got, exp)
    nerr += exp is None
    nok += exp is not None
    try:
        ndiff += oracle(term, False) != exp
    except ValueError:
        ndiff += exp is not None
assert nok > 500 and nerr > 800, (nok, nerr)
assert ndiff > 100, ndiff
''', r'''
class _V:
    __slots__ = ("link", "level")

    def __init__(self, level):
        self.link, self.level = None, level

_GEN = 1 << 30
_INT, _BOOL, _STR, _UNIT = ("Int",), ("Bool",), ("Str",), ("Unit",)
_ARITY = {"int": 2, "bool": 2, "str": 2, "unit": 1, "var": 2, "fn": 3, "call": 3, "let": 4,
          "letrec": 4, "nil": 1, "cons": 3, "match": 6, "ref": 2, "get": 2, "set": 3}
_LIT = {"int": (int, _INT), "bool": (bool, _BOOL), "str": (str, _STR)}

def _prune(t):
    while isinstance(t, _V) and t.link is not None:
        t = t.link
    return t

def _bind(v, t):
    t = _prune(t)
    if isinstance(t, _V):
        if t is v:
            raise ValueError("infinite type")
        t.level = min(t.level, v.level)
    else:
        for c in t[1:]:
            _bind(v, c)

def _unify(a, b):
    a, b = _prune(a), _prune(b)
    if a is b:
        return
    if isinstance(a, _V):
        _bind(a, b)
        a.link = b
    elif isinstance(b, _V):
        _bind(b, a)
        b.link = a
    elif a[0] != b[0] or len(a) != len(b):
        raise ValueError("mismatch")
    else:
        for x, y in zip(a[1:], b[1:]):
            _unify(x, y)

def _retag(t, level, to):
    t = _prune(t)
    if isinstance(t, _V):
        if t.level > level:
            t.level = to
    else:
        for c in t[1:]:
            _retag(c, level, to)

def _inst(t, level, memo):
    t = _prune(t)
    if isinstance(t, _V):
        if t.level != _GEN:
            return t
        return memo.setdefault(t, _V(level))
    return (t[0],) + tuple(_inst(c, level, memo) for c in t[1:])

def _value(e):
    return e[0] in _LIT or e[0] in ("unit", "var", "fn", "nil") or (e[0] == "cons" and _value(e[1]) and _value(e[2]))

def _bad(*ns):
    return not all(isinstance(n, str) and n for n in ns)

def _infer(env, e, lv):
    if not isinstance(e, tuple) or not e or not isinstance(e[0], str) or _ARITY.get(e[0]) != len(e):
        raise ValueError("term")
    k = e[0]
    if k in _LIT:
        if type(e[1]) is not _LIT[k][0]:
            raise ValueError("literal")
        return _LIT[k][1]
    if k in ("unit", "nil"):
        return _UNIT if k == "unit" else ("List", _V(lv))
    if k in ("var", "let", "letrec") and _bad(e[1]):
        raise ValueError("name")
    if k == "var":
        if e[1] not in env:
            raise ValueError("unbound")
        return _inst(env[e[1]], lv, {})
    if k == "fn":
        ps = e[1]
        if not isinstance(ps, tuple) or not ps or _bad(*ps) or len(set(ps)) != len(ps):
            raise ValueError("params")
        vs = [_V(lv) for _ in ps]
        return ("fn", _infer({**env, **dict(zip(ps, vs))}, e[2], lv)) + tuple(vs)
    if k == "call":
        if not isinstance(e[2], tuple) or not e[2]:
            raise ValueError("args")
        tf = _infer(env, e[1], lv)
        ta = [_infer(env, a, lv) for a in e[2]]
        r = _V(lv)
        _unify(tf, ("fn", r) + tuple(ta))
        return r
    if k == "cons":
        h = _infer(env, e[1], lv)
        _unify(_infer(env, e[2], lv), ("List", h))
        return ("List", h)
    if k == "match":
        if _bad(e[3], e[4]) or e[3] == e[4]:
            raise ValueError("match names")
        a = _V(lv)
        _unify(_infer(env, e[1], lv), ("List", a))
        t = _infer(env, e[2], lv)
        _unify(t, _infer({**env, e[3]: a, e[4]: ("List", a)}, e[5], lv))
        return t
    if k == "ref":
        return ("Ref", _infer(env, e[1], lv))
    if k in ("get", "set"):
        a = _V(lv)
        _unify(_infer(env, e[1], lv), ("Ref", a))
        if k == "set":
            _unify(a, _infer(env, e[2], lv))
        return a if k == "get" else _UNIT
    if k == "let":
        t1 = _infer(env, e[2], lv + 1)
        _retag(t1, lv, _GEN if _value(e[2]) else lv)
    else:
        if not isinstance(e[2], tuple) or not e[2] or e[2][0] != "fn":
            raise ValueError("letrec needs fn")
        a = _V(lv + 1)
        t1 = _infer({**env, e[1]: a}, e[2], lv + 1)
        _unify(a, t1)
        _retag(t1, lv, _GEN)
    return _infer({**env, e[1]: t1}, e[3], lv)

def _show(t, names, left=False):
    t = _prune(t)
    if isinstance(t, _V):
        if t not in names:
            names[t] = "t%d" % (len(names) + 1)
        return names[t]
    if len(t) == 1:
        return t[0]
    if t[0] != "fn":
        return t[0] + "<" + _show(t[1], names) + ">"
    ps = [_show(p, names, len(t) == 3) for p in t[2:]]
    s = (ps[0] if len(ps) == 1 else "(" + ", ".join(ps) + ")") + " -> " + _show(t[1], names)
    return "(" + s + ")" if left else s

def weak_infer(term):
    a = _V(_GEN)
    env = {"plus": ("fn", _INT, _INT, _INT), "eq": ("fn", _BOOL, a, a), "size": ("fn", _INT, _STR)}
    return _show(_infer(env, term, 0), {})
''')


task("v5_06_group_infer", r'''
Write `group_type(term) -> str`: the principal type, printed as an s-expression, of a term of a small
functional language with tuples, lists and mutually recursive binding groups, by Hindley-Milner
inference with plain let-polymorphism (no value restriction). Raise ValueError when the term is
ill-typed or malformed.
Terms: an int that is not a bool (type Int); True or False (Bool); a non-empty str (a variable);
otherwise a tuple whose first item is a str tag: ("lam", x, body) with one parameter;
("app", f, a) with one argument; ("if", c, t, e); ("let", x, e1, e2); ("letrec", group, body);
("tuple", e1, ..., en); ("proj", i, n, e). Names are non-empty str. Anything else (float, None, empty
str, list, dict, empty tuple, unknown or non-str tag, wrong length, bad name) is malformed.
"if" needs a Bool condition and equal branch types. "tuple" allows n = 0 (type (Tuple)) and n >= 2;
n = 1 is a ValueError. "proj" takes i and n as ints that are not bools, with n >= 2 and 0 <= i < n
(else ValueError); e must be a tuple of exactly n components and the result is component i
(0-based). In "let" x is not visible in e1 and is generalized over the type variables of e1's type
that are not free in the environment (lambda-bound names are monomorphic). In "letrec", group is a
non-empty tuple of (name, expr) pairs, each a tuple of length 2, with distinct names. Every name is
visible in every expr of the group, monomorphic there (no dependency analysis: a name used at two
types inside its own group is an error). After the whole group is typed, each name is generalized
on its own over the type variables not free in the environment outside the group, and body sees the
generalized names. Inner bindings shadow outer ones. The initial environment (shadowable) is
add: Int -> Int -> Int; eq: a -> a -> Bool; nil: List a; cons: a -> List a -> List a;
head: List a -> a; tail: List a -> List a; isnil: List a -> Bool. ValueError also covers an
unbound variable, a mismatch and an infinite type.
Output: Int, Bool, (-> A B) for a function (always binary, curried, never flattened), (List A),
(Tuple A1 ... An) and (Tuple) for n = 0. Type variables are named by order of first appearance,
reading the printed string left to right: a, b, ..., z, aa, ab, ..., az, ba, ..., zz, aaa, ...
Examples: ("lam", "x", "x") is "(-> a a)"; the K combinator is "(-> a (-> b a))";
("lam", "y", ("let", "f", ("lam", "x", "y"), ("tuple", ("app", "f", 1), ("app", "f", True)))) is
"(-> a (Tuple a a))"; ("lam", "f", ("tuple", ("app", "f", 1), ("app", "f", True))) is an error;
a group of even and odd defined through each other, with body "even", is "(-> Int Bool)".
''', r'''
import random
import itertools
import string

def L(x, b): return ("lam", x, b)
def AP(f, *a):
    for z in a:
        f = ("app", f, z)
    return f
def IF(c, a, b): return ("if", c, a, b)
def LET(x, a, b): return ("let", x, a, b)
def LR(group, body): return ("letrec", tuple(group), body)
def TU(*a): return ("tuple",) + a
def PJ(i, n, e): return ("proj", i, n, e)

def bad(t):
    try:
        group_type(t)
    except ValueError:
        return True
    return False

def ok(t, want):
    got = group_type(t)
    assert got == want, (t, got, want)

ID = L("x", "x")
ok(ID, "(-> a a)")
ok(L("x", L("y", "x")), "(-> a (-> b a))")
ok(L("f", L("g", L("x", AP("f", "x", AP("g", "x"))))), "(-> (-> a (-> b c)) (-> (-> a b) (-> a c)))")
ok(L("f", L("g", L("x", AP("f", AP("g", "x"))))), "(-> (-> a b) (-> (-> c a) (-> c b)))")
ok(L("x", L("f", AP("f", "x"))), "(-> a (-> (-> a b) b))")
ok(L("f", AP("f", 1)), "(-> (-> Int a) a)")
ok(L("a", L("b", TU("b", "a"))), "(-> a (-> b (Tuple b a)))")
ok(3, "Int"); ok(-7, "Int"); ok(0, "Int"); ok(True, "Bool"); ok(False, "Bool")
ok("add", "(-> Int (-> Int Int))"); ok(AP("add", 1), "(-> Int Int)"); ok(AP("add", 1, 2), "Int")
ok("eq", "(-> a (-> a Bool))"); ok("nil", "(List a)"); ok("cons", "(-> a (-> (List a) (List a)))")
ok("head", "(-> (List a) a)"); ok("tail", "(-> (List a) (List a))"); ok("isnil", "(-> (List a) Bool)")
ok(AP("cons", 1, "nil"), "(List Int)"); ok(AP("cons", "nil", "nil"), "(List (List a))")
ok(AP("cons", ID, "nil"), "(List (-> a a))")
ok(AP("eq", ID), "(-> (-> a a) Bool)"); ok(AP("eq", ID, ID), "Bool")
assert bad(AP("cons", 1, AP("cons", True, "nil"))) and bad(AP("add", True)) and bad(AP("add", 1, 2, 3)) and bad(AP("eq", 1, True))
ok(L("l", IF(AP("isnil", "l"), "l", "nil")), "(-> (List a) (List a))")
ok(L("l", AP("add", AP("head", "l"), 1)), "(-> (List Int) Int)")
# tuples and projections
ok(TU(), "(Tuple)"); ok(TU(1, True), "(Tuple Int Bool)"); ok(TU(1, True, TU()), "(Tuple Int Bool (Tuple))")
ok(TU("nil", "nil"), "(Tuple (List a) (List b))"); ok(L("x", TU("x", "x")), "(-> a (Tuple a a))")
ok(TU(TU(1, 2), ID), "(Tuple (Tuple Int Int) (-> a a))")
assert bad(TU(1)) and bad(TU(TU())[:1] + (1,)) and bad(TU("zz"))
ok(PJ(0, 2, TU(1, True)), "Int"); ok(PJ(1, 2, TU(1, True)), "Bool"); ok(PJ(2, 3, TU(1, True, ID)), "(-> a a)")
ok(L("p", PJ(1, 3, "p")), "(-> (Tuple a b c) b)"); ok(L("p", PJ(0, 2, "p")), "(-> (Tuple a b) a)")
ok(L("p", TU(PJ(1, 2, "p"), PJ(0, 2, "p"))), "(-> (Tuple a b) (Tuple b a))")
assert bad(PJ(2, 3, TU(1, 2))) and bad(PJ(2, 2, TU(1, 2))) and bad(PJ(-1, 2, TU(1, 2))) and bad(PJ(0, 1, TU(1)))
assert bad(L("p", PJ(0, 1, "p"))) and bad(L("p", PJ(0, 0, "p"))) and bad(PJ(0, 0, TU())) and bad(PJ(True, 2, TU(1, 2))) and bad(PJ(0, 2.0, TU(1, 2))) and bad(PJ(0, 2, 5)) and bad(PJ(0, 2, TU(1, 2, 3)))
assert bad(L("p", TU(PJ(0, 2, "p"), PJ(0, 3, "p"))))
# if
ok(IF(True, 1, 2), "Int"); ok(L("x", IF(AP("eq", "x", "x"), "x", "x")), "(-> a a)")
assert bad(IF(1, 1, 2)) and bad(IF(True, 1, True)) and bad(("if", True, 1))
# let polymorphism: no value restriction
ok(LET("id", ID, TU(AP("id", 1), AP("id", True))), "(Tuple Int Bool)")
ok(LET("id", AP(ID, ID), TU(AP("id", 1), AP("id", True))), "(Tuple Int Bool)")
ok(LET("f", AP("cons", ID, "nil"), TU(AP("head", "f"), "f")), "(Tuple (-> a a) (List (-> b b)))")
ok(LET("n", "nil", TU(AP("cons", 1, "n"), AP("cons", True, "n"))), "(Tuple (List Int) (List Bool))")
assert bad(L("f", TU(AP("f", 1), AP("f", True))))
ok(L("y", LET("f", L("x", "y"), TU(AP("f", 1), AP("f", True)))), "(-> a (Tuple a a))")
assert bad(L("f", LET("g", "f", TU(AP("g", 1), AP("g", True)))))
ok(L("f", LET("g", "f", TU(AP("g", 1), AP("g", 2)))), "(-> (-> Int a) (Tuple a a))")
ok(L("x", LET("p", L("y", TU("x", "y")), TU(AP("p", 1), AP("p", True)))), "(-> a (Tuple (Tuple a Int) (Tuple a Bool)))")
ok(LET("x", 1, LET("x", True, "x")), "Bool")
ok(L("x", LET("x", "x", "x")), "(-> a a)")
assert bad(LET("x", "x", 1)) and bad(LET("f", L("x", AP("f", "x")), 1)) and bad("zzz") and bad(LET("", 1, 2)) and bad(LET(3, 1, 2))
ok(LET("add", ID, "add"), "(-> a a)")
ok(L("x", L("x", "x")), "(-> a (-> b b))")
ok(L("x", L("y", L("x", TU("x", "y")))), "(-> a (-> b (-> c (Tuple c b))))")
# letrec groups
EVEN = ("even", L("n", IF(AP("eq", "n", 0), True, AP("odd", AP("add", "n", -1)))))
ODD = ("odd", L("n", IF(AP("eq", "n", 0), False, AP("even", AP("add", "n", -1)))))
ok(LR([EVEN, ODD], "even"), "(-> Int Bool)")
ok(LR([EVEN, ODD], TU("odd", "even")), "(Tuple (-> Int Bool) (-> Int Bool))")
ok(LR([ODD, EVEN], "odd"), "(-> Int Bool)")
assert bad(LR([EVEN, ("odd", L("n", IF(AP("eq", "n", 0), 1, AP("even", "n"))))], "even"))
assert bad(LR([("f", ID), ("g", L("y", TU(AP("f", 1), AP("f", True))))], "g"))
ok(LET("f", ID, LET("g", L("y", TU(AP("f", 1), AP("f", True))), "g")), "(-> a (Tuple Int Bool))")
ok(LR([("f", ID), ("g", L("y", "y"))], TU(AP("f", 1), AP("f", True), AP("g", "nil"))), "(Tuple Int Bool (List a))")
ok(LR([("f", L("x", AP("g", "x"))), ("g", L("y", AP("f", "y")))], "f"), "(-> a b)")
ok(LR([("f", L("x", AP("g", "x"))), ("g", L("y", AP("f", "y")))], TU("f", "g")), "(Tuple (-> a b) (-> c d))")
ok(L("z", LR([("f", L("x", "z"))], TU(AP("f", 1), AP("f", True)))), "(-> a (Tuple a a))")
ok(LR([("f", L("x", "x"))], TU(AP("f", 1), AP("f", True))), "(Tuple Int Bool)")
ok(LR([("xs", AP("cons", 1, "xs"))], "xs"), "(List Int)")
ok(LR([("x", "x")], "x"), "a"); ok(LR([("x", "x"), ("y", "x")], TU("x", "y")), "(Tuple a b)")
ok(LR([("f", L("x", AP("f", "x")))], "f"), "(-> a b)")
ok(LR([("f", L("x", AP("f", AP("f", "x"))))], "f"), "(-> a a)")
ok(LR([("f", ID)], LR([("f", L("x", L("y", "y")))], "f")), "(-> a (-> b b))")
ok(LR([("add", ID)], "add"), "(-> a a)")
ok(LR([("a", 1), ("b", True)], TU("a", "b")), "(Tuple Int Bool)")
assert bad(LR([("x", AP("x", "x"))], "x")) and bad(LR([("f", L("x", AP("f", "f")))], "f")) and bad(LR([("xs", AP("cons", "xs", "nil"))], "xs"))
assert bad(LR([("f", 1), ("f", 2)], "f")) and bad(LR([], 1)) and bad(LR([("f", 1), ("g", 2), ("f", 3)], 1))
assert bad(("letrec", [("f", 1)], 1)) and bad(("letrec", (["f", 1],), 1)) and bad(("letrec", (("f", 1, 2),), 1)) and bad(("letrec", (("f",),), 1))
assert bad(("letrec", (("", 1),), 1)) and bad(("letrec", ((1, 1),), 1)) and bad(("letrec", "f", 1)) and bad(("letrec", None, 1)) and bad(("letrec", ("f",), 1))
assert bad(("letrec", (("f", 1),))) and bad(("letrec", (("f", 1),), 1, 2)) and bad(("letrec", ((("f"), 1), 5), 1)) and bad(LR([("f", "g")], 1))
assert bad(LR([("f", L("x", "x"))], "g"))
# malformed terms
for w in [[], None, 1.5, "", (), {}, ["lam", "x", "x"], ("lam", "x"), ("lam", "", "x"), ("lam", 1, 1), ("lam", None, 1), ("lam", ("x",), 1), ("lam", "x", "x", "x"),
          ("lam", "x", None), ("lam", "x", 1.0), ("app", 1), ("app", ID), ("app", ID, 1, 2), ("app", ID, ""), ("app", ID, [1]), ("if", True, 1), ("if", True, 1, 2, 3),
          ("let", "x", 1), ("let", "x", 1, 2, 3), ("let", None, 1, 2), ("tuple", None), ("tuple", 1, 1.5), ("tuple", 1, "") , ("proj", 0, 2), ("proj", 0, 2, TU(1, 2), 1),
          ("zzz",), ("zzz", 1), (1, 2), (["lam"], "x", "x"), (None, 1), ("LAM", "x", "x"), ("Tuple", 1, 2), ("fst", TU(1, 2))]:
    assert bad(w), w

# naming: a..z, aa..zz, aaa.. by first appearance, checked against itertools
def names(n):
    out = []
    for width in (1, 2, 3):
        for p in itertools.product(string.ascii_lowercase, repeat=width):
            out.append("".join(p))
            if len(out) == n:
                return out
for n in (2, 25, 26, 27, 28, 52, 53, 54, 78, 200, 701, 702, 703, 704, 720):
    ok(TU(*["nil"] * n), "(Tuple " + " ".join("(List %s)" % v for v in names(n)) + ")")
ok(L("p", TU(*["p"] * 3)), "(-> a (Tuple a a a))")
deep = L("v0", L("v1", L("v2", L("v3", L("v4", L("v5", L("v6", L("v7", L("v8", L("v9", "v0"))))))))))
ok(deep, "(-> a (-> b (-> c (-> d (-> e (-> f (-> g (-> h (-> i (-> j a))))))))))")
chain = "v0"
for i in range(119, -1, -1):
    chain = L("v%d" % i, chain)
nm = names(120)
exp = nm[0]
for v in reversed(nm):
    exp = "(-> %s %s)" % (v, exp)
ok(chain, exp)
# sharing: inlining the lets would take 2**45 steps
dbl = "f45"
for i in range(45, 0, -1):
    dbl = LET("f%d" % i, L("x", AP("f%d" % (i - 1), AP("f%d" % (i - 1), "x"))), dbl)
ok(LET("f0", ID, dbl), "(-> a a)")
dbl2 = AP("f45", 0)
for i in range(45, 0, -1):
    dbl2 = LET("f%d" % i, L("x", AP("f%d" % (i - 1), AP("f%d" % (i - 1), "x"))), dbl2)
ok(LET("f0", L("x", AP("add", "x", 1)), dbl2), "Int")
# a 150-member group: every binding calls the next
members = [("g%d" % i, L("x", AP("g%d" % (i + 1), "x"))) for i in range(149)] + [("g149", ID)]
ok(LR(members, "g0"), "(-> a a)")
members[-1] = ("g149", L("x", AP("g0", "x")))
ok(LR(members, "g0"), "(-> a b)")
members[-1] = ("g149", L("x", AP("add", "x", 1)))
ok(LR(members, "g0"), "(-> Int Int)")
members[75] = ("g75", L("x", AP("g76", True)))
assert bad(LR(members, "g0"))

# oracle: algorithm W with explicit substitutions, one scheme per name
cnt = [0]
def fresh():
    cnt[0] += 1
    return ("v", cnt[0])

def ap(s, t):
    if t[0] == "v":
        return ap(s, s[t[1]]) if t[1] in s else t
    return (t[0],) + tuple(ap(s, c) for c in t[1:])

def ftv(t, acc=None):
    acc = set() if acc is None else acc
    if t[0] == "v":
        acc.add(t[1])
    else:
        for c in t[1:]:
            ftv(c, acc)
    return acc

def uni(a, b, s):
    a, b = ap(s, a), ap(s, b)
    if a == b:
        return s
    if a[0] == "v" or b[0] == "v":
        if a[0] != "v":
            a, b = b, a
        if a[1] in ftv(b):
            raise ValueError("occurs")
        s = {k: ap({a[1]: b}, v) for k, v in s.items()}
        s[a[1]] = b
        return s
    if a[0] != b[0] or len(a) != len(b):
        raise ValueError("mismatch")
    for p, q in zip(a[1:], b[1:]):
        s = uni(p, q, s)
    return s

def fnt(a, b): return ("fn", a, b)
LA = lambda t: ("List", t)
PRIM = {"add": ((), fnt(("Int",), fnt(("Int",), ("Int",)))), "eq": ((-1,), fnt(("v", -1), fnt(("v", -1), ("Bool",)))),
        "nil": ((-2,), LA(("v", -2))), "cons": ((-3,), fnt(("v", -3), fnt(LA(("v", -3)), LA(("v", -3))))),
        "head": ((-4,), fnt(LA(("v", -4)), ("v", -4))), "tail": ((-5,), fnt(LA(("v", -5)), LA(("v", -5)))),
        "isnil": ((-6,), fnt(LA(("v", -6)), ("Bool",)))}

def gen_scheme(env, t, s):
    t = ap(s, t)
    used = set()
    for sc in env.values():
        used |= ftv(ap(s, sc[1])) - set(sc[0])
    return tuple(sorted(ftv(t) - used)), t

def W(env, e, s):
    if isinstance(e, bool):
        return ("Bool",), s
    if isinstance(e, int):
        return ("Int",), s
    if isinstance(e, str):
        if e not in env:
            raise ValueError("unbound")
        sc = env[e]
        return ap({v: fresh() for v in sc[0]}, sc[1]), s
    if not isinstance(e, tuple) or not e or not isinstance(e[0], str):
        raise ValueError("shape")
    k, n = e[0], len(e)
    if k == "tuple":
        if n == 2:
            raise ValueError("1-tuple")
        ts = []
        for c in e[1:]:
            t, s = W(env, c, s)
            ts.append(t)
        return ("Tuple",) + tuple(ts), s
    if (k, n) not in (("lam", 3), ("app", 3), ("if", 4), ("let", 4), ("letrec", 3), ("proj", 4)):
        raise ValueError("shape")
    if k == "lam":
        if not isinstance(e[1], str) or not e[1]:
            raise ValueError("name")
        a = fresh()
        env2 = dict(env)
        env2[e[1]] = ((), a)
        t, s = W(env2, e[2], s)
        return fnt(a, t), s
    if k == "app":
        tf, s = W(env, e[1], s)
        ta, s = W(env, e[2], s)
        r = fresh()
        s = uni(tf, fnt(ta, r), s)
        return ap(s, r), s
    if k == "if":
        tc, s = W(env, e[1], s)
        s = uni(tc, ("Bool",), s)
        t1, s = W(env, e[2], s)
        t2, s = W(env, e[3], s)
        s = uni(t1, t2, s)
        return ap(s, t1), s
    if k == "proj":
        i, m = e[1], e[2]
        if isinstance(i, bool) or isinstance(m, bool) or not isinstance(i, int) or not isinstance(m, int) or m < 2 or i < 0 or i >= m:
            raise ValueError("proj")
        t, s = W(env, e[3], s)
        vs = [fresh() for _ in range(m)]
        s = uni(t, ("Tuple",) + tuple(vs), s)
        return ap(s, vs[i]), s
    if k == "let":
        if not isinstance(e[1], str) or not e[1]:
            raise ValueError("name")
        t1, s = W(env, e[2], s)
        env2 = dict(env)
        env2[e[1]] = gen_scheme(env, t1, s)
        return W(env2, e[3], s)
    g = e[1]
    if not isinstance(g, tuple) or len(g) == 0:
        raise ValueError("group")
    for p in g:
        if not isinstance(p, tuple) or len(p) != 2 or not isinstance(p[0], str) or not p[0]:
            raise ValueError("group item")
    if len({p[0] for p in g}) != len(g):
        raise ValueError("dup")
    mono = {p[0]: fresh() for p in g}
    env3 = dict(env)
    for k2, v in mono.items():
        env3[k2] = ((), v)
    ts = []
    for p in g:
        t, s = W(env3, p[1], s)
        s = uni(mono[p[0]], t, s)
        ts.append(t)
    env2 = dict(env)
    for p, t in zip(g, ts):
        env2[p[0]] = gen_scheme(env, t, s)
    return W(env2, e[2], s)

def show(t):
    toks = []
    def flat(t):
        if t[0] == "v":
            toks.append(t[1])
        else:
            for c in t[1:]:
                flat(c)
    flat(t)
    order = list(dict.fromkeys(toks))
    table = dict(zip(order, names(len(order) + 1)))
    def go(t):
        if t[0] == "v":
            return table[t[1]]
        if t[0] in ("Int", "Bool"):
            return t[0]
        return "(" + ("->" if t[0] == "fn" else t[0]) + "".join(" " + go(c) for c in t[1:]) + ")"
    return go(t)

def oracle(e):
    t, s = W(PRIM, e, {})
    return show(ap(s, t))

random.seed(5006)
PR = ["add", "eq", "nil", "cons", "head", "tail", "isnil"]
JUNK = [None, 1.5, "", (), ("zzz",), ("tuple", 1), ("proj", 0, 1, ("tuple", 1)), ("lam", "", 1), ("letrec", (), 1)]
def lit():
    return random.choice([0, 1, -3, True, False])

def gen(d, scope):
    c = random.random()
    if d == 0 or c < 0.12:
        c = random.random()
        if c < 0.55 and scope:
            return random.choice(scope)
        if c < 0.75:
            return random.choice(PR)
        if c < 0.77:
            return random.choice(JUNK)
        return lit()
    c = random.random()
    if c < 0.2:
        n = random.choice(["x", "y", "f", "g"])
        return L(n, gen(d - 1, scope + [n]))
    if c < 0.45:
        return AP(gen(d - 1, scope), *[gen(d - 1, scope) for _ in range(random.choice([1, 1, 2]))])
    if c < 0.52:
        return IF(gen(d - 1, scope), gen(d - 1, scope), gen(d - 1, scope))
    if c < 0.64:
        n = random.choice(["x", "y", "f", "g"])
        return LET(n, gen(d - 1, scope), gen(d - 1, scope + [n]))
    if c < 0.76:
        ns = random.sample(["x", "y", "f", "g", "add"], random.choice([1, 2, 2, 3]))
        if random.random() < 0.03:
            ns = ns + ns[:1]
        sc = scope + ns
        return LR([(n, L(random.choice(["a", "b"]), gen(d - 1, sc + ["a", "b"])) if random.random() < 0.7 else gen(d - 1, sc)) for n in ns], gen(d - 1, sc))
    if c < 0.88:
        return TU(*[gen(d - 1, scope) for _ in range(random.choice([0, 2, 2, 3]))])
    n = random.choice([2, 2, 3])
    return PJ(random.randrange(n), n, gen(d - 1, scope))

def group_pattern(d):
    a, b = random.choice([(1, True), (True, 1), (1, 2), (True, False)])
    k = random.randrange(5)
    if k == 0:
        grp = [("f", ID), ("g", L("y", TU(AP("f", a), AP("f", b))))]
        body = random.choice(["g", "f", TU("f", "g")])
    elif k == 1:
        grp = [("f", L("x", AP("g", "x"))), ("g", L("y", TU(AP("f", a), "y")))]
        body = random.choice(["g", "f", TU("f", "g")])
    elif k == 2:
        grp = [("f", L("x", "z")), ("g", L("y", AP("f", "y")))]
        body = L("z", TU(AP("g", a), AP("g", b)))
    elif k == 3:
        grp = [("f", ID), ("g", L("y", "y")), ("h", L("w", TU(AP("g", a), "f")))]
        body = TU(AP("f", a), AP("f", b), AP("h", a))
    else:
        grp = [("xs", AP("cons", a, "ys")), ("ys", AP("cons", b, "xs"))]
        body = TU("xs", "ys")
    if random.random() < 0.5:
        grp = [grp[i] for i in random.sample(range(len(grp)), len(grp))]
    t = LR(grp, body)
    if random.random() < 0.3:
        t = L("z", t)
    return t

nok = nerr = nmulti = 0
for _ in range(2500):
    term = group_pattern(1) if random.random() < 0.3 else gen(random.randint(1, 6), [])
    try:
        exp = oracle(term)
    except ValueError:
        exp = None
    try:
        got = group_type(term)
    except ValueError:
        got = None
    assert got == exp, (term, got, exp)
    nerr += exp is None
    nok += exp is not None
    nmulti += exp is not None and "letrec" in repr(term) and "'g'" in repr(term)
assert nok > 500 and nerr > 500 and nmulti > 30, (nok, nerr, nmulti)
''', r'''
class _V:
    __slots__ = ("link", "level")

    def __init__(self, level):
        self.link, self.level = None, level

_GEN = 1 << 30
_INT, _BOOL = ("Int",), ("Bool",)
_SHAPE = {"lam": 3, "app": 3, "if": 4, "let": 4, "letrec": 3, "proj": 4}

def _prune(t):
    while isinstance(t, _V) and t.link is not None:
        t = t.link
    return t

def _bind(v, t):
    t = _prune(t)
    if isinstance(t, _V):
        if t is v:
            raise ValueError("infinite type")
        t.level = min(t.level, v.level)
    else:
        for c in t[1:]:
            _bind(v, c)

def _unify(a, b):
    a, b = _prune(a), _prune(b)
    if a is b:
        return
    if isinstance(a, _V):
        _bind(a, b)
        a.link = b
    elif isinstance(b, _V):
        _bind(b, a)
        b.link = a
    elif a[0] != b[0] or len(a) != len(b):
        raise ValueError("mismatch")
    else:
        for x, y in zip(a[1:], b[1:]):
            _unify(x, y)

def _generalize(t, level):
    t = _prune(t)
    if isinstance(t, _V):
        if t.level > level:
            t.level = _GEN
    else:
        for c in t[1:]:
            _generalize(c, level)

def _inst(t, level, memo):
    t = _prune(t)
    if isinstance(t, _V):
        return memo.setdefault(t, _V(level)) if t.level == _GEN else t
    return (t[0],) + tuple(_inst(c, level, memo) for c in t[1:])

def _bad(n):
    return not isinstance(n, str) or n == ""

def _infer(env, e, lv):
    if type(e) is int:
        return _INT
    if type(e) is bool:
        return _BOOL
    if type(e) is str:
        if e not in env:
            raise ValueError("unbound or empty name")
        return _inst(env[e], lv, {})
    if not isinstance(e, tuple) or not e or not isinstance(e[0], str):
        raise ValueError("term")
    k = e[0]
    if k == "tuple":
        if len(e) == 2:
            raise ValueError("1-tuple")
        return ("Tuple",) + tuple(_infer(env, c, lv) for c in e[1:])
    if _SHAPE.get(k) != len(e):
        raise ValueError("term")
    if k == "lam":
        if _bad(e[1]):
            raise ValueError("name")
        a = _V(lv)
        return ("fn", a, _infer({**env, e[1]: a}, e[2], lv))
    if k == "app":
        tf, ta, r = _infer(env, e[1], lv), _infer(env, e[2], lv), _V(lv)
        _unify(tf, ("fn", ta, r))
        return r
    if k == "if":
        _unify(_infer(env, e[1], lv), _BOOL)
        t = _infer(env, e[2], lv)
        _unify(t, _infer(env, e[3], lv))
        return t
    if k == "proj":
        i, n = e[1], e[2]
        if type(i) is not int or type(n) is not int or not 0 <= i < n or n < 2:
            raise ValueError("proj")
        vs = [_V(lv) for _ in range(n)]
        _unify(_infer(env, e[3], lv), ("Tuple",) + tuple(vs))
        return vs[i]
    if k == "let":
        if _bad(e[1]):
            raise ValueError("name")
        t = _infer(env, e[2], lv + 1)
        _generalize(t, lv)
        return _infer({**env, e[1]: t}, e[3], lv)
    group = e[1]
    if not isinstance(group, tuple) or not group or not all(isinstance(p, tuple) and len(p) == 2 for p in group):
        raise ValueError("group")
    names = [p[0] for p in group]
    if any(_bad(n) for n in names) or len(set(names)) != len(names):
        raise ValueError("group names")
    vs = [_V(lv + 1) for _ in group]
    inner = {**env, **dict(zip(names, vs))}
    ts = [_infer(inner, p[1], lv + 1) for p in group]
    for v, t in zip(vs, ts):
        _unify(v, t)
    for t in ts:
        _generalize(t, lv)
    return _infer({**env, **dict(zip(names, ts))}, e[2], lv)

def _name(i):
    s = ""
    while True:
        s = chr(97 + i % 26) + s
        i = i // 26 - 1
        if i < 0:
            return s

def _show(t, names):
    t = _prune(t)
    if isinstance(t, _V):
        if t not in names:
            names[t] = _name(len(names))
        return names[t]
    parts = [t[0] if t[0] != "fn" else "->"]
    for c in t[1:]:
        parts.append(_show(c, names))
    return parts[0] if len(t) == 1 and t[0] in ("Int", "Bool") else "(" + " ".join(parts) + ")"

def group_type(term):
    a, b = _V(_GEN), _V(_GEN)
    c, d, f = _V(_GEN), _V(_GEN), _V(_GEN)
    la = lambda x: ("List", x)
    fn = lambda x, y: ("fn", x, y)
    env = {"add": fn(_INT, fn(_INT, _INT)), "eq": fn(a, fn(a, _BOOL)), "nil": la(b), "cons": fn(c, fn(la(c), la(c))),
           "head": fn(la(d), d), "tail": fn(la(f), la(f)), "isnil": fn(la(_V(_GEN)), _BOOL)}
    return _show(_infer(env, term, 0), {})
''')


task("v5_07_branch_influence", r'''
Write `branch_influence(n, edges, entry, exits, targets)`: which branch nodes can decide whether the target nodes run. The control-flow graph has nodes 0..n-1 and directed edges (u, v) (duplicates and self-loops are allowed). R is the set of nodes reachable from `entry`; ignore every other node and every edge that starts at one. Each node of R that is listed in `exits` also has an implicit edge to a virtual node END (not one of 0..n-1) and keeps its ordinary edges. A is the set of nodes of R from which END can be reached. Every other node of R (it can only run forever) is dropped together with every edge into or out of it; only A and END remain.
In that graph y post-dominates x if every path from x to END contains y (so every node post-dominates itself); y strictly post-dominates x if it does and y != x. A node y of A is control dependent on a node x of A (possibly x == y) if there is an edge x -> s with s in A such that y post-dominates s and y does not strictly post-dominate x. (The implicit edge x -> END never makes a node control dependent, but it is a path for post-dominance, so an exit node is not post-dominated by its own successors.)
Let T be the set of nodes of `targets` that lie in A. C is the smallest set such that every node x on which some node of T union C is control dependent belongs to C (a branch that decides a branch that decides a target also counts). Return the tuple (sorted list of the nodes of C, sorted list of the distinct targets that are not in A). Targets outside A contribute nothing to C.
ValueError: n must be an int >= 1 (bool is not an int); entry must be an int in 0..n-1; edges must be a list of pairs (tuples or lists of length 2) of ints in 0..n-1; exits and targets must each be a list, tuple or set of ints in 0..n-1. These checks apply to the whole input, including its unreachable parts.
Efficiency: n up to 40,000 and up to 120,000 edges, so computing a post-dominator set for every node is too slow.
Examples: n=4, edges [(0,1),(0,2),(1,3),(2,3)], entry 0, exits [3], targets [1] gives ([0], []). n=2, edges [(0,0),(0,1)], entry 0, exits [1], targets [0] gives ([0], []).
''', r'''
import random, time

def bad(*a):
    try:
        branch_influence(*a)
    except ValueError:
        return True
    return False

D = [(0, 1), (0, 2), (1, 3), (2, 3)]
assert branch_influence(4, D, 0, [3], [1]) == ([0], [])
assert branch_influence(4, D, 0, [3], [1, 2]) == ([0], [])
assert branch_influence(4, D, 0, [3], [3]) == ([], [])
assert branch_influence(4, D, 0, [3], [0]) == ([], [])
assert branch_influence(4, D, 0, [3], []) == ([], [])
assert branch_influence(4, D + D + [(0, 1)], 0, (3,), {1, 1}) == ([0], [])
assert branch_influence(4, [[0, 1], [0, 2], [1, 3], [2, 3]], 0, {3}, (2, 2)) == ([0], [])
# loop: header 1 controls itself and the body
L = [(0, 1), (1, 2), (2, 1), (1, 3)]
assert branch_influence(4, L, 0, [3], [2]) == ([1], [])
assert branch_influence(4, L, 0, [3], [1]) == ([1], [])
assert branch_influence(4, L, 0, [3], [3]) == ([], [])
assert branch_influence(4, L, 0, [3], [0]) == ([], [])
# a self-loop controls itself
assert branch_influence(2, [(0, 0), (0, 1)], 0, [1], [0]) == ([0], [])
assert branch_influence(2, [(0, 0), (0, 1)], 0, [1], [1]) == ([], [])
# iterated: 2 is decided by 1, which is decided by 0
N = [(0, 1), (0, 3), (1, 2), (1, 3), (2, 3)]
assert branch_influence(4, N, 0, [3], [2]) == ([0, 1], [])
assert branch_influence(4, N, 0, [3], [1]) == ([0], [])
# loop with an inner if: 3 is decided by 2, 2 by 1, 1 by itself; 4 only by 1
W = [(0, 1), (1, 2), (1, 5), (2, 3), (2, 4), (3, 4), (4, 1)]
assert branch_influence(6, W, 0, [5], [3]) == ([1, 2], [])
assert branch_influence(6, W, 0, [5], [4]) == ([1], [])
assert branch_influence(6, W, 0, [5], [5, 0]) == ([], [])
# dead ends: edges into a node that cannot reach an exit are ignored
assert branch_influence(4, [(0, 1), (0, 2), (2, 2), (1, 3)], 0, [3], [1]) == ([], [])
assert branch_influence(4, [(0, 1), (0, 2), (2, 2), (1, 3)], 0, [3], [2, 1, 2]) == ([], [2])
assert branch_influence(3, [(0, 1), (1, 2), (2, 1)], 0, [0], [1, 2]) == ([], [1, 2])
# an exit node keeps its ordinary edges, and its own successors do not post-dominate it
assert branch_influence(3, [(0, 1), (1, 2)], 0, [0, 2], [2]) == ([0], [])
assert branch_influence(3, [(0, 1), (1, 2)], 0, [2], [2]) == ([], [])
assert branch_influence(3, [(0, 1), (1, 2)], 0, [0, 2], [1]) == ([0], [])
assert branch_influence(4, [(0, 1), (1, 2), (1, 3), (2, 3)], 0, [3, 1], [2]) == ([1], [])
assert branch_influence(4, [(0, 1), (1, 2), (1, 3), (2, 3)], 0, [3], [2]) == ([1], [])
# unreachable nodes and edges, unreachable exits and targets
assert branch_influence(5, D + [(4, 3)], 0, [3, 4], [1, 4]) == ([0], [4])
assert branch_influence(5, D + [(4, 3), (4, 4)], 0, [3], [4, 4, 4]) == ([], [4])
assert branch_influence(5, D + [(4, 0)], 0, [4], [1]) == ([], [1])
assert branch_influence(4, D, 1, [3], [1, 2, 3, 0]) == ([], [0, 2])
assert branch_influence(4, D, 2, [3], [0]) == ([], [0])
# the entry cannot reach an exit: A is empty
assert branch_influence(2, [(0, 1)], 0, [], [0, 1]) == ([], [0, 1])
assert branch_influence(2, [(0, 1)], 0, [0], [1, 0]) == ([], [1])
assert branch_influence(1, [], 0, [0], [0]) == ([], [])
assert branch_influence(1, [(0, 0)], 0, [0], [0]) == ([0], [])
assert branch_influence(1, [(0, 0)], 0, [], [0]) == ([], [0])
for a in [(0, [], 0, [], []), (-1, [], 0, [], []), (True, [], 0, [], []), (2.0, [], 0, [], []), ("2", [], 0, [], []), (None, [], 0, [], []),
          (2, [(0, 1)], 2, [], []), (2, [(0, 1)], -1, [], []), (2, [(0, 1)], True, [], []), (2, [(0, 1)], None, [], []), (2, [(0, 1)], 0.0, [], []),
          (2, [(0, 2)], 0, [], []), (2, [(0, -1)], 0, [], []), (2, [(0, 1, 1)], 0, [], []), (2, [(0,)], 0, [], []), (2, [(0, True)], 0, [], []),
          (2, [(0, 1.0)], 0, [], []), (2, [[0, "1"]], 0, [], []), (2, ((0, 1),), 0, [], []), (2, None, 0, [], []), (2, {(0, 1)}, 0, [], []),
          (2, [(0, 1)], 0, [2], []), (2, [(0, 1)], 0, [-1], []), (2, [(0, 1)], 0, [True], []), (2, [(0, 1)], 0, [0.0], []), (2, [(0, 1)], 0, ["0"], []),
          (2, [(0, 1)], 0, None, []), (2, [(0, 1)], 0, 1, []), (2, [(0, 1)], 0, "01", []), (2, [(0, 1)], 0, {0: 1}, []), (2, [(0, 1)], 0, iter([0]), []),
          (2, [(0, 1)], 0, [0], [2]), (2, [(0, 1)], 0, [0], [-1]), (2, [(0, 1)], 0, [0], [True]), (2, [(0, 1)], 0, [0], [None]), (2, [(0, 1)], 0, [0], None),
          (2, [(0, 1)], 0, [0], 1), (2, [(0, 1)], 0, [0], "0"), (2, [(0, 1)], 0, [0], {0: 1}), (2, [(0, 1)], 0, [0], (x for x in [0])),
          (3, [(0, 1), (2, 5)], 0, [], []), (3, [(0, 1)], 0, [2, 3], []), (3, [(0, 1)], 0, [1], [2, 3]), (3, [(0, 1), (2, 2)], 0, [], ["a"]),
          (3, [(0, 1)], 0, [(1,)], [])]:
    assert bad(*a), a
# brute-force oracle: post-dominance by removing one node at a time, control dependence straight from the definition
def oracle(n, edges, entry, exits, targets):
    succ = {i: set() for i in range(n)}
    for u, v in edges:
        succ[u].add(v)
    R = {entry}
    st = [entry]
    while st:
        u = st.pop()
        for v in succ[u]:
            if v not in R:
                R.add(v)
                st.append(v)
    ex = {x for x in exits if x in R}
    def to_end(skip):
        ok = {x for x in ex if x != skip}
        grew = True
        while grew:
            grew = False
            for u in R:
                if u != skip and u not in ok and any(v in ok for v in succ[u]):
                    ok.add(u)
                    grew = True
        return ok
    A = to_end(None)
    RE = {y: to_end(y) for y in A}
    def pdom(y, x):
        return x == y or x not in RE[y]
    cdon = {y: set() for y in A}
    for x in A:
        for s in succ[x]:
            if s in A:
                for y in A:
                    if pdom(y, s) and not (y != x and pdom(y, x)):
                        cdon[y].add(x)
    C = set()
    T = {t for t in targets if t in A}
    while True:
        new = set()
        for y in T | C:
            new |= cdon[y]
        if new <= C:
            break
        C |= new
    return sorted(C), sorted(set(targets) - A)

random.seed(5007)
nonempty = skipped = 0
for it in range(1100):
    n = random.randint(1, 9)
    m = random.randint(0, 2 * n + 2)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    if random.random() < 0.6:
        edges += [(i, i + 1) for i in range(n - 1) if random.random() < 0.8]
    entry = random.randrange(n) if random.random() < 0.25 else 0
    exits = random.sample(range(n), random.randint(0, min(n, 2)))
    targets = random.sample(range(n), random.randint(0, min(n, 3)))
    got = branch_influence(n, edges, entry, exits, targets)
    exp = oracle(n, edges, entry, exits, targets)
    assert got == exp, (n, edges, entry, exits, targets, got, exp)
    nonempty += bool(exp[0])
    skipped += bool(exp[1])
assert nonempty > 250 and skipped > 150, (nonempty, skipped)
for it in range(40):
    n = random.randint(18, 34)
    edges = [(i, i + 1) for i in range(n - 1) if random.random() < 0.85]
    edges += [(random.randrange(n), random.randrange(n)) for _ in range(random.randint(n // 2, n))]
    exits = random.sample(range(n), random.randint(1, 4))
    targets = random.sample(range(n), random.randint(1, 6))
    random.shuffle(edges)
    got = branch_influence(n, edges, 0, set(exits), targets)
    exp = oracle(n, edges, 0, exits, targets)
    assert got == exp, (n, edges, exits, targets, got, exp)
# large: a chain of diamonds, then nested ifs, then sequential while loops with dead side branches
K, DEP, M = 4000, 2000, 2000
ids = iter(range(10 ** 6))
edges, want, targets = [], set(), []
a = [next(ids) for _ in range(K)]
b = [next(ids) for _ in range(K)]
c = [next(ids) for _ in range(K)]
nest = [next(ids) for _ in range(DEP)]
body = next(ids)
join = next(ids)
L = [next(ids) for _ in range(M)]
Bd = [next(ids) for _ in range(M)]
Z = [next(ids) for _ in range((M + 2) // 3)]
F = next(ids)
for i in range(K):
    nxt = a[i + 1] if i + 1 < K else nest[0]
    edges += [(a[i], b[i]), (a[i], c[i]), (b[i], nxt), (c[i], nxt)]
for j in range(DEP):
    edges += [(nest[j], nest[j + 1] if j + 1 < DEP else body), (nest[j], join)]
edges += [(body, join), (join, L[0])]
for i in range(M):
    edges += [(L[i], Bd[i]), (Bd[i], L[i]), (L[i], L[i + 1] if i + 1 < M else F)]
    if i % 3 == 0:
        edges += [(L[i], Z[i // 3]), (Z[i // 3], Z[i // 3])]
noise = [next(ids) for _ in range(3000)]
nn = next(ids)
for u in noise:
    edges += [(u, random.choice(noise)), (u, random.choice(a + Bd + Z)), (u, random.choice(noise))]
for i in random.sample(range(K), 400):
    targets.append(random.choice([b[i], c[i]]))
    want.add(a[i])
j0 = DEP // 2
targets += [nest[j0], body]
want |= set(nest[:DEP])
for i in random.sample(range(M), 300):
    targets.append(Bd[i])
    want.add(L[i])
skip = [Z[random.randrange(len(Z))] for _ in range(5)] + random.sample(noise, 5)
targets += skip + [join, F, 0]
targets += [targets[0], skip[0]]
random.shuffle(targets)
random.shuffle(edges)
n = nn + 1
assert len(edges) < 120000
t0 = time.time()
got = branch_influence(n, edges, a[0], [F], targets)
assert time.time() - t0 < 3.0, time.time() - t0
assert got == (sorted(want), sorted(set(skip))), (len(got[0]), len(want))
''', r'''
def branch_influence(n, edges, entry, exits, targets):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def ints(c):
        if not isinstance(c, (list, tuple, set)):
            raise ValueError("collection")
        out = list(c)
        if not all(isint(x) and 0 <= x < n for x in out):
            raise ValueError("value")
        return out

    if not isint(n) or n < 1 or not isint(entry) or not 0 <= entry < n or not isinstance(edges, list):
        raise ValueError("input")
    succ = [set() for _ in range(n)]
    for e in edges:
        if not isinstance(e, (tuple, list)) or len(e) != 2 or not all(isint(x) and 0 <= x < n for x in e):
            raise ValueError("edge")
        succ[e[0]].add(e[1])
    exits = ints(exits)
    targets = ints(targets)
    seen = [False] * n
    seen[entry] = True
    stack = [entry]
    while stack:
        u = stack.pop()
        for v in succ[u]:
            if not seen[v]:
                seen[v] = True
                stack.append(v)
    pred = [[] for _ in range(n)]
    for u in range(n):
        if seen[u]:
            for v in succ[u]:
                pred[v].append(u)
    inA = [False] * n
    ex = sorted({x for x in exits if seen[x]})
    stack = list(ex)
    for x in ex:
        inA[x] = True
    while stack:
        w = stack.pop()
        for p in pred[w]:
            if not inA[p]:
                inA[p] = True
                stack.append(p)
    end = n
    exs = set(ex)
    sa = [[s for s in succ[x] if inA[s]] if inA[x] else [] for x in range(n)]
    pa = [[] for _ in range(n + 1)]
    for x in range(n):
        for s in sa[x]:
            pa[s].append(x)
    pa[end] = ex
    # post-dominators = dominators of the reversed graph rooted at END (Lengauer-Tarjan)
    N = n + 1
    dfn = [-1] * N
    order = [end]
    par = [-1] * N
    dfn[end] = 0
    stack = [(end, iter(pa[end]))]
    while stack:
        u, it = stack[-1]
        for v in it:
            if dfn[v] < 0:
                dfn[v] = len(order)
                order.append(v)
                par[v] = u
                stack.append((v, iter(pa[v])))
                break
        else:
            stack.pop()
    semi = dfn[:]
    label = list(range(N))
    anc = [-1] * N
    ip = [-1] * N
    bucket = [[] for _ in range(N)]

    def ev(v):
        if anc[v] < 0:
            return v
        path = []
        x = v
        while anc[x] >= 0 and anc[anc[x]] >= 0:
            path.append(x)
            x = anc[x]
        for x in reversed(path):
            a = anc[x]
            if semi[label[a]] < semi[label[x]]:
                label[x] = label[a]
            anc[x] = anc[a]
        return label[v]

    for i in range(len(order) - 1, 0, -1):
        w = order[i]
        for v in (sa[w] + [end] if w in exs else sa[w]):
            if dfn[v] < 0:
                continue
            u = ev(v)
            if semi[u] < semi[w]:
                semi[w] = semi[u]
        bucket[order[semi[w]]].append(w)
        p = par[w]
        anc[w] = p
        for v in bucket[p]:
            u = ev(v)
            ip[v] = u if semi[u] < semi[v] else p
        bucket[p] = []
    for i in range(1, len(order)):
        w = order[i]
        if ip[w] != order[semi[w]]:
            ip[w] = ip[ip[w]]
    cdby = [[] for _ in range(n)]
    for x in range(n):
        if inA[x]:
            stop = ip[x]
            for s in sa[x]:
                r = s
                while r != stop:
                    cdby[r].append(x)
                    r = ip[r]
    inC = [False] * n
    done = [False] * n
    work = []
    for t in targets:
        if inA[t] and not done[t]:
            done[t] = True
            work.append(t)
    while work:
        y = work.pop()
        for x in cdby[y]:
            inC[x] = True
            if not done[x]:
                done[x] = True
                work.append(x)
    return [x for x in range(n) if inC[x]], sorted({t for t in targets if not inA[t]})
''')


task("v5_08_pruned_phis", r'''
Write `live_phi_sites(n, edges, entry, blocks, params)`: the nodes where an SSA builder must put phi functions, pruned by liveness. The control-flow graph has nodes 0..n-1 and directed edges (u, v) (duplicates and self-loops are allowed). Only nodes reachable from `entry` exist: ignore every other node, every edge that starts at one, and every instruction in one.
`blocks` maps a node to a list of instructions executed in order (a node that is not a key has none). An instruction is a pair (op, x) with x a non-empty str: ("use", x) reads x, ("def", x) assigns x, ("upd", x) reads x and then assigns it. `params` is a collection of names that are assigned once at the very start of `entry`, before its first instruction.
Node d dominates v if every path from `entry` to v contains d (so every node dominates itself); d strictly dominates v if it dominates v and d != v. The dominance frontier DF(d) is the set of nodes y for which there is an edge p -> y with p reachable, d dominates p, and d does not strictly dominate y (so d can be in DF(d), and `entry` is in DF(entry) when an edge leads back to it). DF of a set is the union of DF of its members.
For a name x, D(x) is the set of reachable nodes holding a "def" or "upd" of x, plus `entry` if x is in `params`. P(x) is the smallest set with P = DF(D(x) union P). A use of x in a node is upward exposed if no "def" or "upd" of x comes before it in that node's list ("upd" itself is a use, so it is exposed when nothing precedes it). x is live-in at y if some path of 0 or more edges starts at y and ends at a node w with an upward-exposed use of x, and no node before w on that path (y included, if y != w) holds a "def" or "upd" of x. The implicit assignment of a param does not affect liveness, and phi functions are not instructions.
A phi for x is needed at y exactly when y is in P(x) and x is live-in at y (P(x) is built in full first, then filtered).
Return a list of pairs (node, names) as tuples, one for each node that needs at least one phi, in ascending node order, where names is the ascending list of the names (str order) that need a phi there.
ValueError: n must be an int >= 1 (bool is not an int); entry an int in 0..n-1; edges a list of pairs (tuples or lists of length 2) of ints in 0..n-1; blocks a dict whose keys are ints in 0..n-1, each value a list or tuple of pairs (tuple or list of length 2) whose op is one of the three strings and whose name is a non-empty str; params a list, tuple, set or frozenset of non-empty str. These checks apply to the whole input, including the unreachable parts.
Efficiency: n up to 40,000, up to 120,000 edges, a few dozen names, so quadratic dominator or frontier computations are too slow.
Examples: n=4, edges [(0,1),(0,2),(1,3),(2,3)], entry 0, blocks {1: [("def","x")], 2: [("def","x")], 3: [("use","x")]}, params [] gives [(3, ["x"])]. n=2, edges [(0,1),(1,0)], entry 0, blocks {0: [("use","a")]}, params ["a"] gives [(0, ["a"])].
''', r'''
import random, time

def bad(*a):
    try:
        live_phi_sites(*a)
    except ValueError:
        return True
    return False

def df_(x): return ("def", x)
def us_(x): return ("use", x)
def up_(x): return ("upd", x)

D = [(0, 1), (0, 2), (1, 3), (2, 3)]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 2: [df_("x")], 3: [us_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(2, [(0, 1), (1, 0)], 0, {0: [us_("a")]}, ["a"]) == [(0, ["a"])]
assert isinstance(live_phi_sites(4, D, 0, {1: [df_("x")], 3: [us_("x")]}, [])[0], tuple)
assert live_phi_sites(4, D, 0, {1: [df_("x")], 2: [df_("x")], 0: [us_("x")]}, []) == []
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [df_("x"), us_("x")]}, []) == []
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [us_("x"), df_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [up_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [up_("y"), up_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [df_("y"), us_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [up_("x"), up_("x")]}, ()) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {1: [df_("x")], 3: [up_("x")]}, ["x"]) == [(3, ["x"])]
assert live_phi_sites(4, D, 0, {}, ["x"]) == []
assert live_phi_sites(4, D, 0, {1: [df_("x")]}, ["x"]) == []
assert live_phi_sites(4, D, 0, {3: [us_("x")]}, ["x"]) == []
# liveness is blocked by a node that holds a def, y included
G = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (0, 4)]
assert live_phi_sites(5, G, 0, {1: [df_("x")], 4: [us_("x")]}, []) == [(3, ["x"]), (4, ["x"])]
assert live_phi_sites(5, G, 0, {1: [df_("x")], 3: [df_("x")], 4: [us_("x")]}, []) == [(4, ["x"])]
assert live_phi_sites(5, G, 0, {1: [df_("x")], 3: [us_("x"), df_("x")], 4: [us_("x")]}, []) == [(3, ["x"]), (4, ["x"])]
assert live_phi_sites(5, G, 0, {2: [df_("x")], 3: [us_("y")], 4: [us_("x"), df_("y")]}, ["y"]) == [(3, ["x"]), (4, ["x"])]
assert live_phi_sites(5, G, 0, {1: [df_("x")], 4: [df_("x"), us_("x")]}, []) == []
# loops: header 1, body 2, exit 3
L = [(0, 1), (1, 2), (2, 1), (1, 3)]
assert live_phi_sites(4, L, 0, {2: [up_("i")], 3: [us_("i")]}, ["i"]) == [(1, ["i"])]
assert live_phi_sites(4, L, 0, {1: [df_("i")], 2: [up_("i")], 3: [us_("i")]}, ["i"]) == []
assert live_phi_sites(4, L, 0, {1: [us_("i"), df_("i")], 2: [up_("i")]}, ["i"]) == [(1, ["i"])]
assert live_phi_sites(4, L, 0, {2: [df_("i")], 3: [us_("i")]}, []) == [(1, ["i"])]
assert live_phi_sites(4, L, 0, {3: [df_("i")], 1: [us_("i")]}, []) == []
# the entry in its own frontier, through an edge into the entry
C = [(0, 1), (1, 2), (2, 0)]
assert live_phi_sites(3, C, 0, {1: [us_("a")]}, ["a"]) == [(0, ["a"])]
assert live_phi_sites(3, C, 0, {1: [us_("a")]}, []) == []
assert live_phi_sites(3, C, 0, {2: [df_("a")], 1: [us_("a")]}, []) == [(0, ["a"])]
assert live_phi_sites(3, C, 0, {0: [df_("a")], 1: [us_("a")]}, ["a"]) == []
assert live_phi_sites(3, C, 0, {0: [us_("a"), df_("a")]}, ["a"]) == [(0, ["a"])]
assert live_phi_sites(3, C, 0, {2: [us_("a")]}, ["a", "b", "a"]) == [(0, ["a"])]
assert live_phi_sites(3, C, 0, {1: [df_("a")], 2: [us_("a")]}, ["a"]) == []
assert live_phi_sites(3, C, 1, {0: [us_("a")]}, ["a"]) == [(1, ["a"])]
assert live_phi_sites(3, C, 2, {1: [us_("a")]}, ("a",)) == [(2, ["a"])]
assert live_phi_sites(3, C, 0, {2: [us_("a")]}, {"a"}) == [(0, ["a"])]
assert live_phi_sites(3, C, 0, {2: [us_("a")]}, frozenset(["a"])) == [(0, ["a"])]
assert live_phi_sites(3, [(0, 1), (1, 2)], 0, {2: [us_("a")]}, ["a"]) == []
assert live_phi_sites(1, [(0, 0)], 0, {0: [us_("a")]}, ["a"]) == [(0, ["a"])]
assert live_phi_sites(1, [], 0, {0: [us_("a")]}, ["a"]) == []
assert live_phi_sites(1, [(0, 0)], 0, {0: [df_("a"), us_("a")]}, []) == []
assert live_phi_sites(1, [(0, 0)], 0, {0: [up_("a")]}, []) == [(0, ["a"])]
# unreachable nodes, edges and instructions
assert live_phi_sites(5, D + [(4, 3), (4, 4)], 0, {4: [df_("x")], 1: [df_("x")], 3: [us_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(5, D + [(4, 3), (4, 4)], 0, {4: [us_("x")], 1: [df_("x")]}, []) == []
assert live_phi_sites(5, D + [(4, 3), (4, 4)], 0, {4: [df_("x")], 3: [us_("x")]}, ["x"]) == []
assert live_phi_sites(4, D, 1, {3: [us_("x")]}, ["x"]) == []
assert live_phi_sites(4, [(1, 3), (2, 3), (0, 1), (3, 3)], 0, {1: [df_("x")], 3: [us_("x"), df_("y")], 2: [df_("x")]}, []) == []
assert live_phi_sites(4, [(1, 3), (2, 3), (0, 1), (3, 3)], 0, {1: [df_("x")], 3: [up_("x")]}, []) == [(3, ["x"])]
assert live_phi_sites(4, D + D + [(0, 1)], 0, {2: [df_("x")], 3: [us_("x")]}, []) == [(3, ["x"])]
# several names at several nodes: ascending nodes, str order of names
G2 = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (4, 5), (4, 6), (5, 7), (6, 7), (7, 4), (7, 8)]
blk = {1: [df_(v) for v in ("b", "a", "B", "ab")], 5: [df_("b"), df_("a")], 8: [us_(v) for v in ("a", "ab", "b", "B")]}
assert live_phi_sites(9, G2, 0, blk, []) == [(3, ["B", "a", "ab", "b"]), (4, ["a", "b"]), (7, ["a", "b"])]
assert live_phi_sites(9, G2, 0, blk, ["z"]) == live_phi_sites(9, G2, 0, blk, [])
assert live_phi_sites(9, G2, 0, {1: [df_("x")], 6: [df_("x")], 8: [us_("x")]}, ["x"]) == [(3, ["x"]), (4, ["x"]), (7, ["x"])]
assert live_phi_sites(9, G2, 0, {6: [df_("x")], 7: [us_("x")]}, []) == [(4, ["x"]), (7, ["x"])]
# input forms
assert live_phi_sites(4, [[0, 1], [0, 2], (1, 3), (2, 3)], 0, {1: ((("def"), "x"),), 3: [["use", "x"]]}, ["q"]) == [(3, ["x"])]
for a in [(0, [], 0, {}, []), (-1, [], 0, {}, []), (True, [], 0, {}, []), (2.0, [], 0, {}, []), ("2", [], 0, {}, []), (2, [(0, 1)], 2, {}, []), (2, [(0, 1)], -1, {}, []),
          (2, [(0, 1)], True, {}, []), (2, [(0, 1)], None, {}, []), (2, [(0, 2)], 0, {}, []), (2, [(0, -1)], 0, {}, []), (2, [(0, 1, 1)], 0, {}, []), (2, [(0,)], 0, {}, []),
          (2, [(0, True)], 0, {}, []), (2, [(0, 1.0)], 0, {}, []), (2, ((0, 1),), 0, {}, []), (2, None, 0, {}, []), (3, [(0, 1), (2, 5)], 0, {}, []),
          (2, [(0, 1)], 0, [], []), (2, [(0, 1)], 0, None, []), (2, [(0, 1)], 0, {}, None), (2, [(0, 1)], 0, {}, "a"), (2, [(0, 1)], 0, {}, [1]), (2, [(0, 1)], 0, {}, [""]),
          (2, [(0, 1)], 0, {}, [("a",)]), (2, [(0, 1)], 0, {}, {"a": 1, 2: 3}),
          (2, [(0, 1)], 0, {2: []}, []), (2, [(0, 1)], 0, {-1: []}, []), (2, [(0, 1)], 0, {True: []}, []), (2, [(0, 1)], 0, {"0": []}, []), (2, [(0, 1)], 0, {0: None}, []),
          (2, [(0, 1)], 0, {0: "ab"}, []), (2, [(0, 1)], 0, {0: [("use",)]}, []), (2, [(0, 1)], 0, {0: [("use", "a", "b")]}, []), (2, [(0, 1)], 0, {0: [("USE", "a")]}, []),
          (2, [(0, 1)], 0, {0: [("kill", "a")]}, []), (2, [(0, 1)], 0, {0: [("use", "")]}, []), (2, [(0, 1)], 0, {0: [("use", 1)]}, []), (2, [(0, 1)], 0, {0: [("use", None)]}, []),
          (2, [(0, 1)], 0, {0: ["use"]}, []), (2, [(0, 1)], 0, {0: [(1, "a")]}, []), (2, [(0, 1)], 0, {0: {("use", "a")}}, []),
          (3, [(0, 1)], 0, {2: [("use", "a"), ("use", 5)]}, []), (3, [(0, 1)], 0, {2: [("bad", "a")]}, ["a"]), (3, [(0, 1)], 0, {1: []}, ["a", 2])]:
    assert bad(*a), a
assert live_phi_sites(3, [(0, 1)], 0, {2: []}, []) == []
# brute-force oracle: removal dominators, fixpoint frontier closure, forward-search liveness
def reach(n, edges, entry, skip=None):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    seen = set()
    if entry == skip:
        return seen
    st = [entry]
    seen.add(entry)
    while st:
        u = st.pop()
        for v in adj[u]:
            if v != skip and v not in seen:
                seen.add(v)
                st.append(v)
    return seen

def oracle(n, edges, entry, blocks, params):
    R = reach(n, edges, entry)
    dom = {v: set() for v in R}
    for d in R:
        r = reach(n, edges, entry, d)
        for v in R:
            if v == d or v not in r:
                dom[v].add(d)
    def frontier(x):
        return {y for p, y in edges if p in R and x in dom[p] and not (x in dom[y] and x != y)}
    succ = {v: sorted({b for a, b in edges if a == v}) for v in R}
    names = {x for b in R for _, x in blocks.get(b, [])} | set(params)
    def live_in(x, y):
        seen = {y}
        st = [y]
        while st:
            b = st.pop()
            killed = False
            for op, v in blocks.get(b, []):
                if v != x:
                    continue
                if op != "def":
                    return True
                killed = True
                break
            if not killed:
                for s in succ[b]:
                    if s not in seen:
                        seen.add(s)
                        st.append(s)
        return False
    out = {}
    for x in names:
        S = {b for b in R if any(op != "use" and v == x for op, v in blocks.get(b, []))}
        if x in params:
            S.add(entry)
        P = set()
        while True:
            new = set()
            for d in S | P:
                new |= frontier(d)
            if new <= P:
                break
            P |= new
        for y in P:
            if live_in(x, y):
                out.setdefault(y, []).append(x)
    return [(y, sorted(out[y])) for y in sorted(out)]

random.seed(5008)
nonempty = 0
entry_hits = 0
for it in range(300):
    n = random.randint(1, 9)
    m = random.randint(0, 2 * n)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    if random.random() < 0.6:
        edges += [(i, i + 1) for i in range(n - 1) if random.random() < 0.8]
    entry = random.randrange(n) if random.random() < 0.3 else 0
    if random.random() < 0.5:
        edges.append((random.randrange(n), entry))
    names = ["a", "b", "c"][:random.randint(1, 3)]
    blocks = {}
    for b in range(n):
        if random.random() < 0.75:
            blocks[b] = [(random.choice(("use", "def", "upd", "use", "def")), random.choice(names)) for _ in range(random.randint(0, 3))]
    params = random.sample(names, random.randint(0, len(names)))
    got = live_phi_sites(n, edges, entry, blocks, params)
    exp = oracle(n, edges, entry, blocks, params)
    assert got == exp, (n, edges, entry, blocks, params, got, exp)
    nonempty += len(exp)
    entry_hits += any(y == entry for y, _ in exp)
assert nonempty > 150 and entry_hits > 25, (nonempty, entry_hits)

def liveness(n, succ, kill, use):
    live = [False] * n
    changed = True
    while changed:
        changed = False
        for b in range(n - 1, -1, -1):
            if not live[b] and (b in use or (b not in kill and any(live[s] for s in succ[b]))):
                live[b] = True
                changed = True
    return live

# large 1: a chain of diamonds closed by an edge back to the entry
K = 3500
edges = []
for i in range(K):
    a, b, c, nxt = 3 * i, 3 * i + 1, 3 * i + 2, 3 * i + 3
    edges += [(a, b), (a, c), (b, nxt), (c, nxt)]
n = 3 * K + 1
edges.append((3 * K, 0))
succ = [[] for _ in range(n)]
for u, v in edges:
    succ[u].append(v)
blocks, exp = {}, {}
params = []
for v in range(8):
    name = "v%d" % v
    S = random.sample(range(K), 500)
    kill = {3 * i + random.choice((1, 2)) for i in S}
    use = set(random.sample(range(n), 40))
    for b in kill:
        blocks.setdefault(b, []).append(("def", name))
    for b in use:
        blocks.setdefault(b, []).insert(0, ("use", name))
    if v % 3 == 0:
        params.append(name)
    live = liveness(n, succ, kill - use, use)
    P = {3 * (i + 1) for i in S} | {0}
    for y in P:
        if live[y]:
            exp.setdefault(y, []).append(name)
exp = [(y, sorted(exp[y])) for y in sorted(exp)]
random.shuffle(edges)
t0 = time.time()
got = live_phi_sites(n, edges, 0, blocks, params)
assert time.time() - t0 < 3.0
assert got == exp and len(exp) > 600, len(exp)
# large 2: a wide fan into a join that returns to the entry, plus unreachable noise
N = 20000
J = N + 1
edges = [(0, i) for i in range(1, N + 1)] + [(i, J) for i in range(1, N + 1)] + [(J, 0)]
edges += [(N + 2 + k, J) for k in range(40)] + [(N + 2 + k, N + 3 + k) for k in range(39)]
n = N + 42
edges += edges[:5000]
random.shuffle(edges)
succ = [[] for _ in range(n)]
for u, v in edges:
    if u < N + 2:
        succ[u].append(v)
blocks = {N + 2 + k: [("def", "p"), ("def", "q"), ("use", "r")] for k in range(40)}
cases = {"p": ([1, 5, 77], [J], ["p"]), "q": ([2, 3], [0], []), "r": ([N], [N, 1], []), "s": ([], [5], ["s"]), "t": ([4, 9], [9], []), "u": ([8], [J], ["u"])}
exp = {}
for name, (kill, use, pr) in cases.items():
    for b in kill:
        blocks.setdefault(b, []).append(("def", name))
    for b in use:
        blocks.setdefault(b, []).insert(0, ("use", name))
    if pr:
        params.append(name)
    live = liveness(N + 2, succ, set(kill) - set(use), set(use))
    P = {J, 0} if kill else ({0} if pr else set())
    for y in P:
        if live[y]:
            exp.setdefault(y, []).append(name)
exp = [(y, sorted(exp[y])) for y in sorted(exp)]
assert len(exp) == 2 and exp[0][0] == 0, exp
t0 = time.time()
got = live_phi_sites(n, edges, 0, blocks, ["p", "s", "u"])
assert time.time() - t0 < 3.0
assert got == exp, (got, exp)
# large 3: one long chain whose last node returns to the entry
n = 30000
edges = [(i, i + 1) for i in range(n - 1)] + [(n - 1, 0), (n - 1, n - 1), (n - 1, 0)]
blocks = {0: [("use", "m")], 5: [("def", "p")], 10: [("use", "r")], 20000: [("def", "q"), ("def", "r")], 29999: [("use", "p"), ("use", "q"), ("upd", "t")]}
t0 = time.time()
got = live_phi_sites(n, edges, 0, blocks, ["m", "p", "r", "t"])
assert time.time() - t0 < 3.0
assert got == [(0, ["m", "r", "t"]), (29999, ["t"])], got
blocks[0] = [("def", "m")]
assert live_phi_sites(n, edges, 0, blocks, ["m", "p", "r", "t"]) == [(0, ["r", "t"]), (29999, ["t"])]
assert live_phi_sites(n, edges[:-3], 0, blocks, ["m", "p", "r", "t"]) == []
''', r'''
def live_phi_sites(n, edges, entry, blocks, params):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def isname(v):
        return isinstance(v, str) and v != ""

    def pair(e):
        return isinstance(e, (tuple, list)) and len(e) == 2

    if (not isint(n) or n < 1 or not isint(entry) or not 0 <= entry < n or not isinstance(edges, list)
            or not isinstance(blocks, dict) or not isinstance(params, (list, tuple, set, frozenset))):
        raise ValueError("input")
    succ = [[] for _ in range(n)]
    for e in edges:
        if not pair(e) or not all(isint(x) and 0 <= x < n for x in e):
            raise ValueError("edge")
        succ[e[0]].append(e[1])
    if not all(isname(x) for x in params):
        raise ValueError("params")
    kills, exposed = {}, {}
    for b, code in blocks.items():
        if not isint(b) or not 0 <= b < n or not isinstance(code, (list, tuple)):
            raise ValueError("block")
        for ins in code:
            if not pair(ins) or ins[0] not in ("use", "def", "upd") or not isname(ins[1]):
                raise ValueError("instruction")
        done = set()
        for op, x in code:
            if op != "def" and x not in done:
                exposed.setdefault(x, set()).add(b)
            if op != "use":
                done.add(x)
                kills.setdefault(x, set()).add(b)
    order, seen = [], [False] * n
    seen[entry] = True
    stack = [(entry, iter(succ[entry]))]
    while stack:
        u, it = stack[-1]
        for v in it:
            if not seen[v]:
                seen[v] = True
                stack.append((v, iter(succ[v])))
                break
        else:
            order.append(u)
            stack.pop()
    rpo = order[::-1]
    num = {v: i for i, v in enumerate(rpo)}
    preds = {v: set() for v in rpo}
    for u in rpo:
        for v in succ[u]:
            preds[v].add(u)
    idom = {entry: entry}

    def meet(a, b):
        while a != b:
            while num[a] > num[b]:
                a = idom[a]
            while num[b] > num[a]:
                b = idom[b]
        return a

    changed = True
    while changed:
        changed = False
        for b in rpo[1:]:
            new = None
            for p in preds[b]:
                if p in idom:
                    new = p if new is None else meet(new, p)
            if idom.get(b) != new:
                idom[b] = new
                changed = True
    idom[entry] = None
    df = {v: [] for v in rpo}
    for b in rpo:
        for p in preds[b]:
            r = p
            while r != idom[b]:
                df[r].append(b)
                r = idom[r]
    plan = {}
    for x in sorted(set(kills) | set(exposed) | set(params)):
        uses = [u for u in exposed.get(x, ()) if seen[u]]
        sites = {d for d in kills.get(x, ()) if seen[d]}
        if x in params:
            sites.add(entry)
        if not uses or not sites:
            continue
        live = set(uses)
        work = list(uses)
        dead = kills.get(x, ())
        while work:
            for p in preds[work.pop()]:
                if p not in live and p not in dead:
                    live.add(p)
                    work.append(p)
        has, queued, work = set(), set(sites), list(sites)
        while work:
            for y in df[work.pop()]:
                if y not in has:
                    has.add(y)
                    if y not in queued:
                        queued.add(y)
                        work.append(y)
        for y in has & live:
            plan.setdefault(y, []).append(x)
    return [(y, plan[y]) for y in sorted(plan)]
''')


task("v5_09_sigfig_sci", r'''
Write `format_sigfigs(s, sig, mode)` that rounds an exact decimal string to `sig` significant
digits and returns it in scientific notation. Do not use the decimal or fractions modules.
s: an optional sign "+" or "-", then digits with at most one ".", with at least one digit in
all ("5.", ".5" and "007" are fine, "." is not), then optionally "e" or "E", an optional sign
and 1 to 10 digits (leading zeros count towards the 10). ASCII digits only; no spaces, no
underscores. len(s) is at most 100000; a longer s is a ValueError. The value is exact: the
mantissa times 10 to the exponent. sig: an int (not a bool) in 1..2000. mode: one of
"nearest_even", "nearest_away", "nearest_zero", "toward_zero", "away_zero", "toward_neg",
"toward_pos", "zero_five". Anything else (including a non-str s) is a ValueError.
Significant digits are counted from the first non-zero digit of the mantissa: leading zeros,
including those after the point, are not significant; zeros after it are. Round the exact
value to `sig` significant digits. If the value has no more than `sig` of them nothing is
dropped and nothing changes. Otherwise:
- "toward_zero" truncates; "away_zero" goes to the next larger magnitude; "toward_neg" and
  "toward_pos" go down or up in value (floor, ceiling). The last three change the value only
  if the dropped digits are not all zero.
- "nearest_even", "nearest_away", "nearest_zero" round to the nearest `sig`-digit value; an
  exact tie (the dropped part is exactly half a unit of the last kept digit) goes to the even
  last digit, away from zero, toward zero, respectively. Ties are decided on the exact value:
  a dropped part of "5000...01" is above the tie.
- "zero_five" truncates, except that if something was dropped and the last kept digit of the
  truncated value is 0 or 5, it goes one unit away from zero instead.
A round-up can carry through the digits: 9.99 with sig 2 gives 10, written "1.0e+01".
Output: the first digit, then if sig > 1 a "." and the other sig-1 digits (padded with zeros
if needed), then "e", then "+" or "-" (always), then the decimal exponent of the first digit
with at least 2 digits and no other leading zeros ("e+00", "e-07", "e+123"). A "-" comes first
if the result is negative and not zero. Zero, in any spelling and with any exponent, gives
zeros: sig 3 gives "0.00e+00", sig 1 gives "0e+00" (no sign, exponent +00).
Range: the exponent of the first digit of the rounded result (after any carry) must be within
-999999999..999999999, else ValueError. A zero result never raises for range. The input can be
extreme though, and the answer must come back immediately: "9.99e999999999" with sig 3 is
"9.99e+999999999" but with sig 2 and "nearest_even" it is a ValueError; "1e-9999999999" is a
ValueError; "0e-9999999999" with sig 4 is "0.000e+00".
Examples: format_sigfigs("2.5", 1, "nearest_even") is "2e+00"; format_sigfigs("-0.0009995",
3, "nearest_away") is "-1.00e-03"; format_sigfigs("12345", 2, "toward_pos") is "1.3e+04";
format_sigfigs("1.04", 2, "zero_five") is "1.1e+00".
''', r'''
_banned(mods=("decimal", "fractions"))
import decimal, random, time

_D = decimal
_RM = {"nearest_even": _D.ROUND_HALF_EVEN, "nearest_away": _D.ROUND_HALF_UP, "nearest_zero": _D.ROUND_HALF_DOWN,
       "toward_zero": _D.ROUND_DOWN, "away_zero": _D.ROUND_UP, "toward_neg": _D.ROUND_FLOOR,
       "toward_pos": _D.ROUND_CEILING, "zero_five": _D.ROUND_05UP}

def oracle(s, sig, mode):
    """None means ValueError."""
    if len(s) > 100000:
        return None
    d = _D.Decimal(s)
    if d.is_zero():
        return ("0" if sig == 1 else "0." + "0" * (sig - 1)) + "e+00"
    ctx = _D.Context(prec=sig, rounding=_RM[mode], Emax=_D.MAX_EMAX, Emin=_D.MIN_EMIN, traps=[])
    r = ctx.plus(d)
    sg, dg, e = r.as_tuple()
    dg = "".join(map(str, dg)).ljust(sig, "0")
    assert len(dg) == sig and dg[0] != "0"
    a = e + len(r.as_tuple().digits) - 1
    if abs(a) > 999999999:
        return None
    return ("-" if sg else "") + dg[0] + ("." + dg[1:] if sig > 1 else "") + "e%s%02d" % ("-" if a < 0 else "+", abs(a))

def bad(*a):
    try:
        format_sigfigs(*a)
    except ValueError:
        return True
    return False

def ok(s, sig, mode, exp, orc=True):
    if exp == "ValueError":
        assert bad(s, sig, mode), (s[:60], sig, mode)
        if orc:
            assert oracle(s, sig, mode) is None, ("oracle disagrees", s[:60], sig, mode)
        return
    got = format_sigfigs(s, sig, mode)
    assert got == exp, (s[:60], sig, mode, got[:60], exp[:60])
    if orc:
        o = oracle(s, sig, mode)
        assert o == exp, ("oracle disagrees with the hand value", s[:60], sig, mode, o, exp)

NE, NA, NZ, TZ, AZ, TN, TP, ZF = ("nearest_even", "nearest_away", "nearest_zero", "toward_zero", "away_zero",
                                  "toward_neg", "toward_pos", "zero_five")
H = []
def h(s, sig, mode, exp, orc=True):
    H.append((s, sig, mode, exp, orc))

# ties, one significant digit
for s, e in [("2.5", "2e+00"), ("3.5", "4e+00"), ("-2.5", "-2e+00"), ("-3.5", "-4e+00"), ("0.25", "2e-01"), ("0.35", "4e-01"),
             ("0.0035", "4e-03"), ("1.5", "2e+00"), ("0.5", "5e-01"), ("15", "2e+01"), ("25", "2e+01"), ("35", "4e+01"),
             ("95", "1e+02"), ("-95", "-1e+02"), ("2.50001", "3e+00"), ("2.4999", "2e+00"), ("-0.00000025", "-2e-07")]:
    h(s, 1, NE, e)
for s, e in [("2.5", "3e+00"), ("-2.5", "-3e+00"), ("95", "1e+02"), ("0.45", "5e-01"), ("2.4999", "2e+00"), ("-0.00045", "-5e-04")]:
    h(s, 1, NA, e)
for s, e in [("2.5", "2e+00"), ("-2.5", "-2e+00"), ("95", "9e+01"), ("-95", "-9e+01"), ("2.50001", "3e+00"), ("2.5", "2e+00"), ("0.45", "4e-01")]:
    h(s, 1, NZ, e)
# truncation, away, floor, ceiling, zero_five
for s, sg, m, e in [("199.99", 2, TZ, "1.9e+02"), ("-199.99", 2, TZ, "-1.9e+02"), ("199.01", 2, AZ, "2.0e+02"), ("-199.01", 2, AZ, "-2.0e+02"),
                    ("-100.0", 2, AZ, "-1.0e+02"), ("100.0", 2, AZ, "1.0e+02"), ("100.001", 2, AZ, "1.1e+02"),
                    ("-1.01", 2, TN, "-1.1e+00"), ("1.09", 2, TN, "1.0e+00"), ("1.01", 2, TP, "1.1e+00"), ("-1.09", 2, TP, "-1.0e+00"),
                    ("1.00", 2, TP, "1.0e+00"), ("-1.00", 2, TN, "-1.0e+00"), ("-0.00001", 1, TP, "-1e-05"),
                    ("-0.000011", 1, TN, "-2e-05"), ("0.000011", 1, TN, "1e-05"), ("0.000011", 1, TP, "2e-05"),
                    ("1.04", 2, ZF, "1.1e+00"), ("1.54", 2, ZF, "1.6e+00"), ("1.24", 2, ZF, "1.2e+00"), ("1.50", 2, ZF, "1.5e+00"),
                    ("-1.04", 2, ZF, "-1.1e+00"), ("0.0504", 2, ZF, "5.1e-02"), ("9.0001", 1, ZF, "9e+00"), ("4.9", 1, ZF, "4e+00"),
                    ("5.9", 1, ZF, "6e+00"), ("0.0001", 3, ZF, "1.00e-04"), ("10.0000001", 2, ZF, "1.1e+01"),
                    ("-5.0000001", 1, ZF, "-6e+00"), ("0.0000", 2, ZF, "0.0e+00"), ("99.4", 2, ZF, "9.9e+01"), ("90.4", 2, ZF, "9.1e+01")]:
    h(s, sg, m, e)
# carries through digits and into the exponent
for s, sg, m, e in [("9.99", 2, NE, "1.0e+01"), ("0.00999", 2, NE, "1.0e-02"), ("99999", 3, TP, "1.00e+05"), ("-99999", 3, TN, "-1.00e+05"),
                    ("99999", 3, TN, "9.99e+04"), ("-99999", 3, TP, "-9.99e+04"), ("9.995", 3, NE, "1.00e+01"), ("9.985", 3, NE, "9.98e+00"),
                    ("9.985", 3, NA, "9.99e+00"), ("9.985", 3, NZ, "9.98e+00"), ("0.9995", 3, NA, "1.00e+00"), ("0.9995", 3, NZ, "9.99e-01"),
                    ("8.995", 3, NE, "9.00e+00"), ("19.95", 3, NE, "2.00e+01"), ("19.85", 3, NE, "1.98e+01"), ("19.85", 3, NA, "1.99e+01"),
                    ("999.9", 1, NE, "1e+03"), ("999.9", 1, TZ, "9e+02"), ("-999.9", 2, AZ, "-1.0e+03"), ("0.099", 1, AZ, "1e-01"),
                    ("9" * 30, 5, TP, "1.0000e+30"), ("9" * 30 + ".5", 30, NE, "1." + "0" * 29 + "e+30"),
                    ("9" * 30 + ".5", 31, NE, "9." + "9" * 29 + "5e+29"), ("9" * 30 + ".49", 31, NE, "9." + "9" * 29 + "5e+29")]:
    h(s, sg, m, e)
# padding and spellings
for s, sg, m, e in [("5", 4, NE, "5.000e+00"), ("0.00120", 5, NE, "1.2000e-03"), ("100", 1, NE, "1e+02"), ("123456", 10, NE, "1.234560000e+05"),
                    ("+12.5", 3, NE, "1.25e+01"), (".5", 2, NE, "5.0e-01"), ("5.", 2, NE, "5.0e+00"), ("0005.10", 2, NE, "5.1e+00"),
                    ("00.0012300", 3, NE, "1.23e-03"), ("-0.0000500", 1, NE, "-5e-05"), ("12.0", 2, TZ, "1.2e+01"), ("1000000", 1, AZ, "1e+06"),
                    ("1000001", 1, AZ, "2e+06"), ("-1000001", 1, TN, "-2e+06"), ("-1000001", 1, TP, "-1e+06"), ("100", 5, TP, "1.0000e+02")]:
    h(s, sg, m, e)
for s, sg, m, e in [("5", 1500, NE, "5." + "0" * 1499 + "e+00"), ("123", 2000, TZ, "1.23" + "0" * 1997 + "e+02"), ("0.00045", 1999, NA, "4.5" + "0" * 1997 + "e-04"),
                    ("-12", 1000, AZ, "-1.2" + "0" * 998 + "e+01")]:
    h(s, sg, m, e)
h("12" + "9" * 2100, 2000, NE, "1.3" + "0" * 1998 + "e+2101")
h("12" + "9" * 2100, 2000, TZ, "1.2" + "9" * 1998 + "e+2101")
# zero
for s, sg, e in [("0", 3, "0.00e+00"), ("-0.000", 1, "0e+00"), ("0e99999", 2, "0.0e+00"), ("-0e-9999999999", 2, "0.0e+00"), (".0", 2, "0.0e+00"),
                 ("00.00e5", 4, "0.000e+00"), ("+0.", 1, "0e+00"), ("-.0E+9999999999", 3, "0.00e+00"), ("0e0000000000", 2, "0.0e+00")]:
    for m in (NE, AZ, TN, ZF):
        h(s, sg, m, e)
# exponents in the string
for s, sg, m, e in [("1.5e2", 1, NE, "2e+02"), ("15E-1", 1, NE, "2e+00"), ("1e+3", 2, NE, "1.0e+03"), ("1e0000000001", 2, NE, "1.0e+01"),
                    ("12345e-2", 3, TZ, "1.23e+02"), ("12355e-2", 4, NE, "1.236e+02"), ("12345e-2", 4, NE, "1.234e+02"), ("12345e-2", 4, NA, "1.235e+02"),
                    ("0.05e1", 1, NE, "5e-01"), ("5.e2", 2, NE, "5.0e+02"), (".5e1", 2, NE, "5.0e+00"), ("0.0001e-3", 1, NE, "1e-07"),
                    ("99.5e-4", 2, NE, "1.0e-02"), ("99.5E+4", 2, NZ, "9.9e+05"), ("1e10", 1, NE, "1e+10"), ("1e123", 2, NE, "1.0e+123"),
                    ("1e-100", 2, NE, "1.0e-100"), ("7e-5", 3, TZ, "7.00e-05"), ("12e+0", 1, NE, "1e+01"), ("19e+0", 1, NE, "2e+01")]:
    h(s, sg, m, e)
# range limits
for s, sg, m, e in [("1e999999999", 3, NE, "1.00e+999999999"), ("9.99e999999999", 3, NE, "9.99e+999999999"), ("9.99e999999999", 2, NE, "ValueError"),
                    ("9.99e999999999", 2, TZ, "9.9e+999999999"), ("9.99e999999999", 2, TP, "ValueError"), ("-9.99e999999999", 2, TN, "ValueError"),
                    ("-9.99e999999999", 2, TP, "-9.9e+999999999"), ("99e999999998", 1, NE, "ValueError"), ("99e999999998", 1, TZ, "9e+999999999"),
                    ("1e1000000000", 3, NE, "ValueError"), ("0.1e1000000000", 3, NE, "1.00e+999999999"), ("10e999999999", 3, TZ, "ValueError"),
                    ("1e-999999999", 2, NE, "1.0e-999999999"), ("0.1e-999999998", 2, NE, "1.0e-999999999"), ("0.1e-999999999", 2, NE, "ValueError"),
                    ("1e-1000000000", 2, NE, "ValueError"), ("9e-1000000000", 2, NE, "ValueError"), ("0.99e-999999998", 2, TZ, "9.9e-999999999"),
                    ("9.9e-1000000000", 1, AZ, "1e-999999999"), ("9.9e-1000000000", 1, TZ, "ValueError"), ("9.9e-1000000000", 1, NE, "1e-999999999"),
                    ("0.0000000001e-999999990", 1, NE, "ValueError"), ("1e9999999999", 1, NE, "ValueError"), ("1e-9999999999", 4, NE, "ValueError"),
                    ("123e-9999999999", 2, NE, "ValueError"), ("0.000001e0000000000", 1, NE, "1e-06"), ("1e0999999999", 2, NE, "1.0e+999999999"),
                    ("0e9999999999", 4, NE, "0.000e+00"), ("0e-9999999999", 4, NE, "0.000e+00")]:
    h(s, sg, m, e)
# long mantissas (size limit 100000)
big = "9" * 100000
h(big, 3, NE, "1.00e+100000")
h(big, 3, TZ, "9.99e+99999")
h(big, 3, TN, "9.99e+99999")
h(big, 3, TP, "1.00e+100000")
h("-" + big[:-1], 3, TN, "-1.00e+99999")
h("+" + big[:-1], 2000, NE, "1." + "0" * 1999 + "e+99999")
h(big, 2000, TZ, "9." + "9" * 1999 + "e+99999")
h(big, 2000, ZF, "9." + "9" * 1999 + "e+99999")
h(big, 2000, NE, "1." + "0" * 1999 + "e+100000")
tie = "1" + "0" * 4 + "5" + "0" * 99994
h(tie, 5, NE, "1.0000e+99999")
h(tie, 5, NA, "1.0001e+99999")
h(tie, 5, NZ, "1.0000e+99999")
tie1 = "1" + "0" * 4 + "5" + "0" * 99993 + "1"
h(tie1, 5, NE, "1.0001e+99999")
h(tie1, 5, NZ, "1.0001e+99999")
h(tie1, 5, TZ, "1.0000e+99999")
h(tie1, 5, ZF, "1.0001e+99999")
h("0." + "0" * 99990 + "5" + "0" * 7, 1, NE, "5e-99991")
h("0." + "0" * 99989 + "25", 1, NE, "2e-99990")
h("0." + "0" * 99989 + "35", 1, NE, "4e-99990")
h("0." + "0" * 99989 + "251", 1, NE, "3e-99990")
h("1" + "0" * 99998 + "1", 1, AZ, "2e+99999")
h("1" + "0" * 99998 + "1", 1, TP, "2e+99999")
h("1" + "0" * 99998 + "1", 1, TN, "1e+99999")
h("-1" + "0" * 99997 + "1", 1, TN, "-2e+99998")
h("0" * 99990 + "1" + "5" * 9, 3, NE, "1.56e+09")
h("0" * 50000 + "7" + "0" * 49999, 3, NE, "7.00e+49999")
h("0" * 99999 + "7", 3, NE, "7.00e+00")
h("0" * 99988 + "7e999999999", 2, TZ, "7.0e+999999999")
h("9" * 100001, 3, NE, "ValueError", False)
h("0" * 100001, 3, NE, "ValueError", False)
h("1" + "0" * 100000, 3, NE, "ValueError", False)
h("1e" + "0" * 99998, 3, NE, "ValueError", False)
h("1." + "0" * 99996 + "e1", 3, NE, "1.00e+01")
for s, sg, m, e, orc in H:
    ok(s, sg, m, e, orc)
# validation
for s in ["", "+", "-", ".", "+.", "-.", "e5", ".e5", "1e", "1e+", "1e-", "1e5.5", "1.2.3", "1,5", "1 ", " 1", "1\n", "\n1", "١٢", "1_0", "0x10", "inf", "nan",
          "NaN", "Infinity", "-inf", "--1", "+-1", "1e12345678901", "1e00000000005", "0e12345678901", "1ee5", "1e5e5", "1.5f", "−1", "1e٣", "１", "1 e5", "1e 5",
          "1.e", "1e+-5", "e", "E5", "+e5", "1f", "1.5.", "..5", "1e1.0", "½", "1\t", "1\x00", "1e5\n", "0,5", "1E", "1e++5", "(1)", "0b1"]:
    assert bad(s, 2, NE), repr(s)
for s in [1, 1.5, None, b"1", ["1"], ("1",), True, 0, decimal.Decimal(1)]:
    assert bad(s, 1, NE), s
for sg in [0, -1, 2001, 10**6, 1.0, "2", None, True, False, 2.5, [1], (1,)]:
    assert bad("1.5", sg, NE), sg
assert not bad("1.5", 2000, NE) and not bad("1.5", 1, NE)
for m in ["NEAREST_EVEN", "nearest-even", "half_even", "", None, 1, "round", "Floor", "floor", "ceil", "truncate", " toward_zero", "toward_zero ", ["toward_zero"], ("toward_zero",), True, "nearest", "zero_5"]:
    assert bad("1.5", 1, m), m

# random cases against the decimal module
random.seed(5009)
def rd(k):
    return "".join(random.choice("0123456789") for _ in range(k))

def rcase():
    kind = random.random()
    lead = "0" * random.choice([0, 0, 0, 1, 2, 4])
    if kind < 0.3:
        core = random.choice("123456789") + rd(random.randint(0, 9))
        sig = random.randint(1, len(core) + 2)
    elif kind < 0.65:
        kept = random.choice("123456789") + rd(random.randint(0, 5))
        core = kept + "5" + "0" * random.randint(0, 4)
        if random.random() < 0.2:
            core += random.choice("1239") if core.endswith("0") else "1"
        sig = len(kept)
    elif kind < 0.9:
        a = random.randint(1, 6)
        core = "9" * a + random.choice(["", "5", "50", "4", "6", "49", "51", "500001", "9"])
        if random.random() < 0.3:
            core = random.choice("1234") + "9" * a + random.choice(["5", "4", "6", "50"])
        sig = random.randint(1, len(core))
    elif kind < 0.95:
        core = random.choice("1234") + "0" * random.randint(0, 5) + random.choice(["", "1", "4", "5", "6", "50", "9"])
        sig = random.randint(1, len(core))
    else:
        core, sig = "0" * random.randint(1, 4), random.randint(1, 5)
    D = lead + core
    pos = random.randint(0, len(D))
    s = random.choice(["", "", "-", "-", "+"]) + D[:pos]
    if pos < len(D) or random.random() < 0.5:
        s += "." + D[pos:]
    r = random.random()
    if r < 0.45:
        pass
    elif r < 0.85:
        s += random.choice("eE") + random.choice(["", "+", "-"]) + random.choice([str(random.randint(0, 12)), "00" + str(random.randint(0, 9)), str(random.randint(0, 400))])
    else:
        ex = random.choice([999999999, 999999998, 999999997, 999999996, 999999995, -999999999, -999999998, -999999997, -999999996, -999999995, 9999999999, -9999999999, 1000000000, -1000000000])
        s += random.choice("eE") + (("-" if ex < 0 else random.choice(["", "+"])) + str(abs(ex)))
    return s, sig, random.choice(list(_RM))

nerr = nzero = ntie = nneg = nrange = 0
t0 = time.time()
for _ in range(4500):
    s, sig, mode = rcase()
    exp = oracle(s, sig, mode)
    if exp is None:
        assert bad(s, sig, mode), (s, sig, mode)
        nerr += 1
    else:
        got = format_sigfigs(s, sig, mode)
        assert got == exp, (s, sig, mode, got, exp)
        nzero += exp.startswith("0")
        ntie += mode.startswith("nearest")
        nneg += exp.startswith("-")
        nrange += exp[-9:].isdigit() and int(exp[-9:]) > 99999999
assert nerr > 60 and nzero > 30 and ntie > 1200 and nneg > 800 and nrange > 40, (nerr, nzero, ntie, nneg, nrange)
assert time.time() - t0 < 5
''', r'''
import re

_PAT = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]{1,10}))?")
_MODES = frozenset(("nearest_even", "nearest_away", "nearest_zero", "toward_zero", "away_zero",
                    "toward_neg", "toward_pos", "zero_five"))
_RANGE = 999999999


def format_sigfigs(s, sig, mode):
    if (not isinstance(s, str) or len(s) > 100000 or type(sig) is not int or not 1 <= sig <= 2000
            or not isinstance(mode, str) or mode not in _MODES):
        raise ValueError("argument")
    m = _PAT.fullmatch(s)
    if not m:
        raise ValueError("syntax")
    sign, ip, fp, ex = m.groups()
    fp = fp or ""
    if not (ip or fp):
        raise ValueError("no digits")
    neg = sign == "-"
    z = (ip + fp).lstrip("0")
    if not z:
        return ("0" if sig == 1 else "0." + "0" * (sig - 1)) + "e+00"
    # exponent of the first non-zero digit
    aexp = (int(ex) if ex else 0) - len(fp) + len(z) - 1
    if len(z) <= sig:
        kept = z.ljust(sig, "0")
    else:
        kept, rest = z[:sig], z[sig:]
        if not rest.strip("0"):
            inc = False
        elif mode == "toward_zero":
            inc = False
        elif mode == "away_zero":
            inc = True
        elif mode == "toward_neg":
            inc = neg
        elif mode == "toward_pos":
            inc = not neg
        elif mode == "zero_five":
            inc = kept[-1] in "05"
        else:
            tie = rest[0] == "5" and not rest[1:].strip("0")
            if tie:
                if mode == "nearest_even":
                    inc = kept[-1] in "13579"
                else:
                    inc = mode == "nearest_away"
            else:
                inc = rest[0] >= "5"
        if inc:
            head = kept.rstrip("9")
            if not head:
                kept = "1" + "0" * (sig - 1)
                aexp += 1
            else:
                kept = head[:-1] + chr(ord(head[-1]) + 1) + "0" * (sig - len(head))
    if not -_RANGE <= aexp <= _RANGE:
        raise ValueError("range")
    body = kept[0] + ("." + kept[1:] if sig > 1 else "")
    return ("-" if neg else "") + body + "e" + ("-" if aexp < 0 else "+") + str(abs(aexp)).rjust(2, "0")
''')


task("v5_10_step_snap", r'''
Write `snap_to_step(x, step, mode)` that rounds an exact decimal x to a multiple of an exact
decimal step (cash rounding to 0.05, lot sizes of 25) and returns a canonical decimal string.
Do not use the decimal or fractions modules.
x and step are strings: an optional sign "+" or "-", then digits with at most one ".", with at
least one digit in all ("5." and ".5" are fine, "." is not), then optionally "e" or "E", an
optional sign and 1 to 10 digits. ASCII digits only; no spaces, no underscores. A string of more
than 4000 characters is a ValueError. The values are exact. step must be greater than zero ("0", "-0",
"0e5" and any negative step are ValueErrors). mode: one of "floor", "ceil", "outward", "inward",
"tie_even", "tie_odd", "tie_away", "tie_zero". Anything else (including a non-str x or step) is
a ValueError.
The result is k*step for an integer k. If x is already a multiple of step it is returned
unchanged by every mode. Otherwise x lies strictly between two neighbouring multiples:
- "floor" takes the lower one (toward -infinity), "ceil" the upper one; "outward" takes the one
  farther from zero, "inward" the one nearer to zero (zero itself is a multiple, and is nearer
  than any other).
- "tie_*" take the nearer multiple. If x is exactly halfway: "tie_even" takes the multiple whose
  integer k is even, "tie_odd" the one whose k is odd (k=0 is even, and k=-3 is odd),
  "tie_away" the one farther from zero, "tie_zero" the one nearer to zero. The parity is that
  of k, not of any digit of the output: with step "0.05", x="0.125" is 2.5 steps and
  "tie_even" gives k=2, "0.10". Ties are decided on exact values.
Output: plain notation, no exponent, no "+". Write step as m*10**e with m an integer that is
not divisible by 10; let d = max(0, -e). The result has exactly d fractional digits (and no "."
if d is 0), and its integer part has no leading zeros, with "0" if it is zero: step "0.050"
has m=5, e=-2, d=2, so results look like "0.15"; step "25" and step "1e3" have d=0. A "-" appears
only if the result is not zero ("-0.01" to step "0.05" with "ceil" is "0.00").
Size limit: if the output would have more than 3000 digits (the integer part, counting the "0"
of a zero integer part, plus d), raise ValueError. The inputs can be extreme though, and the
answer must come back immediately: step "1e999999999" with x="5e999999998" gives "0" for
"tie_even" and "tie_zero" but is a ValueError for "tie_odd" and "tie_away" (the result 1e999999999
is too long); step "1e-2999" is fine, step "1e-3000" is a ValueError.
Examples: snap_to_step("0.125", "0.05", "tie_even") is "0.10"; snap_to_step("-37.5", "25",
"tie_odd") is "-25"; snap_to_step("-37.5", "25", "tie_even") is "-50";
snap_to_step("1e-999999999", "0.01", "outward") is "0.01"; snap_to_step("7.3", "0.5", "inward")
is "7.0".
''', r'''
_banned(mods=("decimal", "fractions"))
import fractions, math, random, re, time

_MODES = ["floor", "ceil", "outward", "inward", "tie_even", "tie_odd", "tie_away", "tie_zero"]
_PAT = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?")

def val(t):
    """exact Fraction of a decimal string (the standard library parses it), or None if the exponent is too big for a cheap oracle"""
    m = _PAT.fullmatch(t)
    if m.group(4) and abs(int(m.group(4))) > 30000:
        return None
    return fractions.Fraction(t)

def oracle(x, step, mode):
    """'ValueError', or the expected string, or None if the oracle cannot run"""
    if len(x) > 4000 or len(step) > 4000:
        return "ValueError"
    fx, fs = val(x), val(step)
    if fx is None or fs is None:
        return None
    if fs <= 0:
        return "ValueError"
    d, p = 0, 1
    while p % fs.denominator:
        p *= 10
        d += 1
    if d >= 3000:
        return "ValueError"
    q = fx / fs
    lo = math.floor(q)
    fr = q - lo
    if fr == 0:
        k = lo
    else:
        far = lo + 1 if fx > 0 else lo
        near = lo if fx > 0 else lo + 1
        if mode == "floor":
            k = lo
        elif mode == "ceil":
            k = lo + 1
        elif mode == "outward":
            k = far
        elif mode == "inward":
            k = near
        elif fr != fractions.Fraction(1, 2):
            k = lo if fr < fractions.Fraction(1, 2) else lo + 1
        elif mode == "tie_even":
            k = lo if lo % 2 == 0 else lo + 1
        elif mode == "tie_odd":
            k = lo if lo % 2 == 1 else lo + 1
        elif mode == "tie_away":
            k = far
        else:
            k = near
    r = k * fs * 10 ** d
    assert r.denominator == 1
    n = r.numerator
    if abs(n) >= 10 ** 3000:
        return "ValueError"
    s = str(abs(n)).rjust(d + 1, "0")
    out = s[:-d] + "." + s[-d:] if d else s
    return ("-" if n < 0 else "") + out

def bad(*a):
    try:
        snap_to_step(*a)
    except ValueError:
        return True
    return False

def ok(x, step, mode, exp, orc=True):
    if exp == "ValueError":
        assert bad(x, step, mode), (x[:50], step[:50], mode)
    else:
        try:
            got = snap_to_step(x, step, mode)
        except ValueError as e:
            raise AssertionError(("unexpected ValueError", x[:50], step[:50], mode, exp[:40]))
        assert got == exp, (x[:50], step[:50], mode, got[:60], exp[:60])
    if orc:
        o = oracle(x, step, mode)
        assert o is None or o == exp, ("oracle disagrees with the hand value", x[:50], step[:50], mode, o, exp)

FL, CE, OU, IN, TE, TO, TA, TZ = _MODES
H = []
def h(x, step, mode, exp, orc=True):
    H.append((x, step, mode, exp, orc))

def allm(x, step, exps, orc=True):
    for m, e in zip(_MODES, exps):
        h(x, step, m, e, orc)

#            floor    ceil     outward  inward   t_even   t_odd    t_away   t_zero
allm("0.125", "0.05", ["0.10", "0.15", "0.15", "0.10", "0.10", "0.15", "0.15", "0.10"])
allm("-0.125", "0.05", ["-0.15", "-0.10", "-0.15", "-0.10", "-0.10", "-0.15", "-0.15", "-0.10"])
allm("0.175", "0.05", ["0.15", "0.20", "0.20", "0.15", "0.20", "0.15", "0.20", "0.15"])
allm("0.025", "0.05", ["0.00", "0.05", "0.05", "0.00", "0.00", "0.05", "0.05", "0.00"])
allm("-0.025", "0.05", ["-0.05", "0.00", "-0.05", "0.00", "0.00", "-0.05", "-0.05", "0.00"])
allm("0.075", "0.05", ["0.05", "0.10", "0.10", "0.05", "0.10", "0.05", "0.10", "0.05"])
allm("0.12", "0.05", ["0.10", "0.15", "0.15", "0.10", "0.10", "0.10", "0.10", "0.10"])
allm("0.13", "0.05", ["0.10", "0.15", "0.15", "0.10", "0.15", "0.15", "0.15", "0.15"])
allm("-0.13", "0.05", ["-0.15", "-0.10", "-0.15", "-0.10", "-0.15", "-0.15", "-0.15", "-0.15"])
allm("37.5", "25", ["25", "50", "50", "25", "50", "25", "50", "25"])
allm("-37.5", "25", ["-50", "-25", "-50", "-25", "-50", "-25", "-50", "-25"])
allm("12.5", "25", ["0", "25", "25", "0", "0", "25", "25", "0"])
allm("-12.5", "25", ["-25", "0", "-25", "0", "0", "-25", "-25", "0"])
allm("62.5", "25", ["50", "75", "75", "50", "50", "75", "75", "50"])
allm("-62.5", "25", ["-75", "-50", "-75", "-50", "-50", "-75", "-75", "-50"])
allm("4.5", "3", ["3", "6", "6", "3", "6", "3", "6", "3"])
allm("-4.5", "3", ["-6", "-3", "-6", "-3", "-6", "-3", "-6", "-3"])
allm("1.5", "3", ["0", "3", "3", "0", "0", "3", "3", "0"])
allm("7.25", "0.5", ["7.0", "7.5", "7.5", "7.0", "7.0", "7.5", "7.5", "7.0"])
allm("7.75", "0.5", ["7.5", "8.0", "8.0", "7.5", "8.0", "7.5", "8.0", "7.5"])
allm("6.25", "2.50", ["5.0", "7.5", "7.5", "5.0", "5.0", "7.5", "7.5", "5.0"])
allm("0.45", "0.3", ["0.3", "0.6", "0.6", "0.3", "0.6", "0.3", "0.6", "0.3"])
allm("250", "100", ["200", "300", "300", "200", "200", "300", "300", "200"])
allm("-250", "1e2", ["-300", "-200", "-300", "-200", "-200", "-300", "-300", "-200"])
allm("1500", "1e3", ["1000", "2000", "2000", "1000", "2000", "1000", "2000", "1000"])
allm("-1500", "1e3", ["-2000", "-1000", "-2000", "-1000", "-2000", "-1000", "-2000", "-1000"])
allm("1.0005", "0.001", ["1.000", "1.001", "1.001", "1.000", "1.000", "1.001", "1.001", "1.000"])
allm("-1.0005", "0.001", ["-1.001", "-1.000", "-1.001", "-1.000", "-1.000", "-1.001", "-1.001", "-1.000"])
allm("7.3", "0.5", ["7.0", "7.5", "7.5", "7.0", "7.5", "7.5", "7.5", "7.5"])
allm("-7.3", "0.5", ["-7.5", "-7.0", "-7.5", "-7.0", "-7.5", "-7.5", "-7.5", "-7.5"])
allm("0.2", "0.5", ["0.0", "0.5", "0.5", "0.0", "0.0", "0.0", "0.0", "0.0"])
allm("-0.2", "0.5", ["-0.5", "0.0", "-0.5", "0.0", "0.0", "0.0", "0.0", "0.0"])
allm("0.3", "0.5", ["0.0", "0.5", "0.5", "0.0", "0.5", "0.5", "0.5", "0.5"])
# exact multiples are unchanged, spellings and padding
for m in _MODES:
    for x, s, e in [("7.5", "0.5", "7.5"), ("-7.50", "0.5", "-7.5"), ("0", "0.5", "0.0"), ("-0", "0.5", "0.0"), ("-0.000", "7", "0"), ("5", "0.01", "5.00"),
                    ("1e3", "0.1", "1000.0"), ("+75", "25", "75"), ("-75.0", "+25.00", "-75"), ("5.", "5", "5"), (".5", ".5", "0.5"), ("12", "4e0", "12"),
                    ("1.5e1", "0.0050", "15.000"), ("0.15", "0.05", "0.15"), ("300", "1e2", "300"), ("-1e3", "1e3", "-1000"), ("0e99999", "3", "0"),
                    ("-0e-99999", "0.25", "0.00"), ("0.0000", "1e3", "0")]:
        h(x, s, m, e)
# the output scale comes from the step in lowest terms
allm("1.234", "0.050", ["1.20", "1.25", "1.25", "1.20", "1.25", "1.25", "1.25", "1.25"])
allm("1.234", "0.5000", ["1.0", "1.5", "1.5", "1.0", "1.0", "1.0", "1.0", "1.0"])
allm("1.234", "50e-2", ["1.0", "1.5", "1.5", "1.0", "1.0", "1.0", "1.0", "1.0"])
allm("1234", "1000", ["1000", "2000", "2000", "1000", "1000", "1000", "1000", "1000"])
allm("1234", "1.0e3", ["1000", "2000", "2000", "1000", "1000", "1000", "1000", "1000"])
allm("0.7", "0.25", ["0.50", "0.75", "0.75", "0.50", "0.75", "0.75", "0.75", "0.75"])
allm("0.625", "0.25", ["0.50", "0.75", "0.75", "0.50", "0.50", "0.75", "0.75", "0.50"])
allm("100.001", "0.002", ["100.000", "100.002", "100.002", "100.000", "100.000", "100.002", "100.002", "100.000"])
# negative results that round to zero lose the sign
for m, e in zip(_MODES, ["-0.05", "0.00", "-0.05", "0.00", "0.00", "0.00", "0.00", "0.00"]):
    h("-0.01", "0.05", m, e)
for m, e in zip(_MODES, ["-1", "0", "-1", "0", "0", "0", "0", "0"]):
    h("-0.0001", "1", m, e)
# extreme exponents
tiny = [("0.00", "0.01", "0.01", "0.00", "0.00", "0.00", "0.00", "0.00"), ("-0.01", "0.00", "-0.01", "0.00", "0.00", "0.00", "0.00", "0.00")]
allm("1e-999999999", "0.01", tiny[0], False)
allm("-1e-999999999", "0.01", tiny[1], False)
allm("1e-999999999", "1e-2", ["0.00", "0.01", "0.01", "0.00", "0.00", "0.00", "0.00", "0.00"], False)
allm("123456789e-9999999999", "5", ["0", "5", "5", "0", "0", "0", "0", "0"], False)
allm("-123456789e-9999999999", "5", ["-5", "0", "-5", "0", "0", "0", "0", "0"], False)
allm("5e-1000000000", "1e-1", ["0.0", "0.1", "0.1", "0.0", "0.0", "0.0", "0.0", "0.0"], False)
allm("5e999999998", "1e999999999", ["0", "ValueError", "ValueError", "0", "0", "ValueError", "ValueError", "0"], False)
allm("-5e999999998", "1e999999999", ["ValueError", "0", "ValueError", "0", "0", "ValueError", "ValueError", "0"], False)
allm("4e999999998", "1e999999999", ["0", "ValueError", "ValueError", "0", "0", "0", "0", "0"], False)
allm("6e999999998", "1e999999999", ["0", "ValueError", "ValueError", "0", "ValueError", "ValueError", "ValueError", "ValueError"], False)
allm("1e999999999", "1e999999999", ["ValueError"] * 8, False)
allm("1e999999999", "3", ["ValueError"] * 8, False)
allm("1e999999999", "1e-999999999", ["ValueError"] * 8, False)
allm("1", "1e999999999", ["0", "ValueError", "ValueError", "0", "0", "0", "0", "0"], False)
allm("-1", "1e999999999", ["ValueError", "0", "ValueError", "0", "0", "0", "0", "0"], False)
allm("0", "1e999999999", ["0"] * 8, False)
allm("-0e-9999999999", "9999999999e9999999999", ["0"] * 8, False)
allm("3e999999999", "1e999999999", ["ValueError"] * 8, False)
allm("12e9999999999", "7e9999999999", ["ValueError"] * 8, False)
allm("1e9999999999", "1e9999999999", ["ValueError"] * 8, False)
allm("0.5e9999999999", "1e9999999999", ["0", "ValueError", "ValueError", "0", "0", "ValueError", "ValueError", "0"], False)
# size limits
allm("1", "1e-2999", ["1." + "0" * 2999] * 8)
allm("1", "1e-3000", ["ValueError"] * 8)
allm("0", "1e-3000", ["ValueError"] * 8)
allm("0", "1e-2999", ["0." + "0" * 2999] * 8)
allm("0", "10e-3000", ["0." + "0" * 2999] * 8)
allm("0", "100e-3001", ["0." + "0" * 2999] * 8)
allm("0", "1e-3000", ["ValueError"] * 8)
allm("0", "1e-2998", ["0." + "0" * 2998] * 8)
allm("0.5e-2999", "1e-2999", ["0." + "0" * 2999, "0." + "0" * 2998 + "1", "0." + "0" * 2998 + "1", "0." + "0" * 2999, "0." + "0" * 2999,
                              "0." + "0" * 2998 + "1", "0." + "0" * 2998 + "1", "0." + "0" * 2999])
allm("3e-3000", "1e-2999", ["0." + "0" * 2999, "0." + "0" * 2998 + "1", "0." + "0" * 2998 + "1", "0." + "0" * 2999, "0." + "0" * 2999,
                            "0." + "0" * 2999, "0." + "0" * 2999, "0." + "0" * 2999])
allm("9" * 3000, "1", ["9" * 3000] * 8)
allm("9" * 3000 + ".5", "1", ["9" * 3000, "ValueError", "ValueError", "9" * 3000, "ValueError", "9" * 3000, "ValueError", "9" * 3000])
allm("-" + "9" * 3000 + ".5", "1", ["ValueError", "-" + "9" * 3000, "ValueError", "-" + "9" * 3000, "ValueError", "-" + "9" * 3000, "ValueError", "-" + "9" * 3000])
allm("1e2999", "3e2998", ["9" + "0" * 2998, "12" + "0" * 2998, "12" + "0" * 2998, "9" + "0" * 2998, "9" + "0" * 2998, "9" + "0" * 2998, "9" + "0" * 2998, "9" + "0" * 2998])
allm("1e3000", "1e2999", ["ValueError"] * 8)
allm("1e2999", "1e2999", ["1" + "0" * 2999] * 8)
allm("15" + "0" * 1999, "1e2000", ["1" + "0" * 2000, "2" + "0" * 2000, "2" + "0" * 2000, "1" + "0" * 2000, "2" + "0" * 2000, "1" + "0" * 2000, "2" + "0" * 2000, "1" + "0" * 2000])
allm("15" + "0" * 1999, "1e1999", ["15" + "0" * 1999] * 8)
allm("0." + "0" * 3990 + "7", "0.00001", ["0.00000", "0.00001", "0.00001", "0.00000", "0.00000", "0.00000", "0.00000", "0.00000"])
allm("-0." + "0" * 3990 + "7", "0.00001", ["-0.00001", "0.00000", "-0.00001", "0.00000", "0.00000", "0.00000", "0.00000", "0.00000"])
allm("7e-3990", "1e-2000", ["0." + "0" * 2000, "0." + "0" * 1999 + "1", "0." + "0" * 1999 + "1", "0." + "0" * 2000, "0." + "0" * 2000, "0." + "0" * 2000, "0." + "0" * 2000, "0." + "0" * 2000])
allm("5", "1e-2995", ["5." + "0" * 2995] * 8)
allm("500000", "1e-2995", ["ValueError"] * 8)
allm("50000", "1e-2995", ["50000." + "0" * 2995] * 8)
allm("1e3100", "1e-2999", ["ValueError"] * 8)
allm("7e7000", "3", ["ValueError"] * 8)
allm("7e-7000", "3", ["0", "3", "3", "0", "0", "0", "0", "0"])
allm("7e-7000", "3e-100", ["0." + "0" * 100, "0." + "0" * 99 + "3", "0." + "0" * 99 + "3", "0." + "0" * 100, "0." + "0" * 100, "0." + "0" * 100, "0." + "0" * 100, "0." + "0" * 100])
# a 4000-character x and step
LX = "1" + "0" * 1999 + ".5" + "0" * 1997
assert len(LX) == 3999
h(LX, "1", FL, "1" + "0" * 1999)
h(LX, "1", CE, "1" + "0" * 1998 + "1")
h(LX, "1", TE, "1" + "0" * 1999)
h(LX, "1", TA, "1" + "0" * 1998 + "1")
LY = "1" + "0" * 1998 + "1.5" + "0" * 1997
h(LY, "1", TE, "1" + "0" * 1998 + "2")
h(LY, "1", TO, "1" + "0" * 1998 + "1")
h("1", "0." + "0" * 1996 + "25", FL, "1." + "0" * 1998)
h("9" * 4000, "9" * 3999, FL, "ValueError")
h("9" * 3000, "9" * 3000, TE, "9" * 3000)
h("9" * 3000, "9" * 2999, FL, "9" * 2999 + "0")
h("9" * 3000, "9" * 2999, TE, "9" * 2999 + "0")
h("9" * 3000, "9" * 2999, CE, "ValueError")
h("9" * 3001, "9" * 3000, FL, "ValueError")
for x, step, mode, exp, orc in H:
    ok(x, step, mode, exp, orc)
# validation
for s in ["", "+", "-", ".", "+.", ".e5", "e5", "1e", "1e+", "1e5.5", "1.2.3", "1,5", " 1", "1 ", "1\n", "١٢", "1_0", "0x10", "inf", "nan", "--1", "+-1", "1e12345678901",
          "1ee5", "1.5f", "−1", "1e٣", "１", "1 e5", "1e 5", "1e+-5", "..5", "1e1.0", "1\t", "1\x00", "1e5\n"]:
    assert bad(s, "1", TE), repr(s)
    assert bad("1", s, TE), repr(s)
for s in [1, 1.5, None, b"1", ["1"], ("1",), True]:
    assert bad(s, "1", TE), s
    assert bad("1", s, TE), s
for s in ["0", "-0", "0.0", "0e5", "+0.", "-0e-9999999999", "-1", "-0.5", "-1e9999", "-1e-9999999999", "0.000e99", "00"]:
    assert bad("1", s, TE) and bad("0", s, FL), s
for m in ["FLOOR", "Floor", "round", "tie", "", None, 1, "half_even", "tie-even", " floor", "floor ", ["floor"], ("floor",), True, "tie_even "]:
    assert bad("1.5", "1", m), m
assert not bad("1.5", "+1", FL) and not bad("1.5", "0.000001", FL)
assert bad("1" * 4001, "1", FL) and bad("1", "1" * 4001, FL) and bad("1" * 4001, "0", FL)
assert not bad("1" * 2999, "1" * 4000, FL) and not bad("0" * 3999 + "1", "1", FL) and not bad("1", "0" * 3999 + "1", FL)

# random cases against fractions
random.seed(5010)
def rint(lo, hi):
    return random.randint(lo, hi)

def fmt(D, e):
    """D (int >= 0) * 10**e as a random decimal spelling"""
    ds = str(D)
    f = rint(0, len(ds) + 2)
    ds = ds.rjust(f, "0")
    ip, fp = ds[:len(ds) - f], ds[len(ds) - f:]
    if random.random() < 0.15:
        ip = "0" * rint(1, 3) + ip
    s = ip
    if f or random.random() < 0.1:
        s += "." + fp
    E = e + f
    if E != 0 or random.random() < 0.2:
        s += random.choice("eE") + ("-" if E < 0 else random.choice(["", "", "+"])) + (("0" * rint(0, 2)) + str(abs(E)))
    return s

def rcase():
    if random.random() < 0.06:
        # near the 3000-digit limits
        sm, se = rint(1, 30), rint(-3003, -2994)
        k = rint(0, 40)
        n, ex = random.choice([((2 * k + 1) * sm * 5, se - 1), (rint(0, 10 ** 6), rint(-3010, 3010)), (k * sm, se + rint(0, 6))])
        x = random.choice(["", "-"]) + fmt(n, ex)
        return x, fmt(sm, se), random.choice(_MODES)
    sm = rint(1, random.choice([9, 99, 999, 25, 5, 125, 10 ** 12]))
    se = rint(-6, 6) if random.random() < 0.85 else rint(-40, 40)
    if random.random() < 0.08:
        sm *= 10 ** rint(1, 3)
    step = fmt(sm, se)
    k = rint(-300, 300) if random.random() < 0.9 else rint(-10 ** 15, 10 ** 15)
    r = random.random()
    # x = (k + t) * step, t one of 0, 1/2, 1/4, 3/4, or a tiny shift of a tie
    if r < 0.12:
        n, ex = k * sm, se                          # exact multiple
    elif r < 0.55:
        n, ex = (2 * k + 1) * sm * 5, se - 1        # exact tie
    elif r < 0.7:
        n, ex = (4 * k + random.choice([1, 3])) * sm * 25, se - 2
    elif r < 0.9:
        n, ex = ((2 * k + 1) * sm * 5) * 10 ** 4 + random.choice([-1, 1]), se - 5   # just off the tie
    else:
        n, ex = rint(0, 10 ** rint(1, 12)), rint(-12, 12)
    neg = n < 0
    n = abs(n)
    if n == 0 and random.random() < 0.5:
        neg = True
    x = ("-" if neg else random.choice(["", "", "+"])) + fmt(n, ex)
    return x, step, random.choice(_MODES)

nerr = nzero = nneg = ntie = nbig = 0
t0 = time.time()
for _ in range(3500):
    x, step, mode = rcase()
    exp = oracle(x, step, mode)
    assert exp is not None
    if exp == "ValueError":
        assert bad(x, step, mode), (x, step, mode)
        nerr += 1
    else:
        got = snap_to_step(x, step, mode)
        assert got == exp, (x, step, mode, got, exp)
        nzero += not exp.strip("0.")
        nneg += exp.startswith("-")
        ntie += mode.startswith("tie")
        nbig += len(exp) > 20
assert nzero > 60 and nneg > 600 and ntie > 1200 and nbig > 20 and 10 < nerr < 400, (nerr, nzero, nneg, ntie, nbig)
assert time.time() - t0 < 5
''', r'''
import re

_PAT = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]{1,10}))?")
_MODES = frozenset(("floor", "ceil", "outward", "inward", "tie_even", "tie_odd", "tie_away", "tie_zero"))
_DIG = 3000


def _parse(t):
    if not isinstance(t, str) or len(t) > 4000:
        raise ValueError("argument")
    m = _PAT.fullmatch(t)
    if not m:
        raise ValueError("syntax")
    sign, ip, fp, ex = m.groups()
    fp = fp or ""
    if not (ip or fp):
        raise ValueError("no digits")
    return sign == "-", int(ip + fp), (int(ex) if ex else 0) - len(fp)


def snap_to_step(x, step, mode):
    if not isinstance(mode, str) or mode not in _MODES:
        raise ValueError("mode")
    neg, a, ea = _parse(x)
    sneg, b, es = _parse(step)
    if b == 0 or sneg:
        raise ValueError("step")
    t = str(b).rstrip("0")
    es += len(str(b)) - len(t)
    b = int(t)
    d = max(0, -es)
    if d >= _DIG:
        raise ValueError("size")
    km = 0                      # magnitude of k
    if a:
        diff = (ea + len(str(a))) - (es + len(t))   # exponent of x minus exponent of step
        if diff > _DIG:
            raise ValueError("size")      # the result keeps at least diff digits: integer part + d
        if diff < -1:
            q, r, den = 0, 1, 3           # |x| < step/10: below the halfway point, never exact
        else:
            shift = ea - es
            num, den = (a * 10 ** shift, b) if shift >= 0 else (a, b * 10 ** -shift)
            q, r = divmod(num, den)
        km = q
        if r:
            c = (2 * r > den) - (2 * r < den)
            if mode == "floor":
                up = neg
            elif mode == "ceil":
                up = not neg
            elif mode == "outward":
                up = True
            elif mode == "inward":
                up = False
            elif c:
                up = c > 0
            elif mode == "tie_even":
                up = q % 2 == 1
            elif mode == "tie_odd":
                up = q % 2 == 0
            else:
                up = mode == "tie_away"
            km = q + up
    res = km * b
    if res and (es >= _DIG or res >= 10 ** (_DIG - max(es, 0))):
        raise ValueError("size")
    if es >= 0:
        body = str(res) + "0" * es if res else "0"
    else:
        digits = str(res).rjust(d + 1, "0")
        body = digits[:-d] + "." + digits[-d:]
    return "-" + body if neg and res else body
''')

TASKS = T
