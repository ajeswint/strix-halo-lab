"""loop-v4: held-out Python tasks for the DeepSeek-fixer replication (Roadmap item 2). Probe: v4_01-10.

Same layout as tasks_v3.py: id, prompt, tests, ref. Written 2026-10-07 for the hardened grader
(oracle over stdin, static deny-list; the refs use none of the denied names). Modelled on the
v3 failures (forth_vm, farthest_vertex, mod_sqrts, hist_calendar, billiard): long specs with
exact edge rules, tie-breaks and big numbers. None was used for prompt or loop iteration. Every
test file has exactly one random.seed(N) line, N = 4001 + task number - 1, so agent.py's
fresh-seed grade applies. Seeded random cases are checked against an oracle inside the test
that is built differently from the ref (tick simulation vs event skipping, Algorithm W vs
levels, brute-force removal vs Cooper-Harvey-Kennedy, datetime vs own calendar, ...).
v4_01 json_patch, v4_02 mini_asm, v4_03 dst_zone, v4_04 rr_priority, v4_05 hm_infer,
v4_06 phi_blocks, v4_07 sub_game, v4_08 lattice_poly, v4_09 dec_round, v4_10 bracelets.
Tasks 11-30 are appended at the marker below with seeds 4011-4030; the first 10 stay as they are.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("v4_01_json_patch", r'''
Write `json_patch(doc, ops)` that applies a list of JSON-Patch-style operations (an RFC 6902
subset) to a JSON-like value built from dict (str keys), list, str, int, float, bool and None,
and returns the patched value. `doc` and `ops` must not be modified, and the result must share
no dict or list object with either of them. Any failure raises ValueError.
Pointers (the "path" and "from" strings): "" is the whole document. Otherwise the string must
start with "/", and the rest is split at every "/" into tokens ("/" is the single token "",
"//" is two empty tokens). In a token "~1" means "/" and "~0" means "~", read left to right
(so "~01" is "~1"); a "~" followed by anything else, or at the end of the token, is a
ValueError. A pointer that is not a str, or does not start with "/", is a ValueError.
Resolving a token against a value: dict: the key must exist. list: the token must be a
canonical index: ASCII digits only, either "0" or without a leading zero (so no sign, no
spaces, no "01", no "-0"), and less than len. Every other token is an error, and so is any
token applied to a str, number, bool or None. The token "-" is an error everywhere except as
the last token of an add target (below).
The ops: a list (else ValueError) of dicts, each with a str "op" and a str "path". "add",
"replace" and "test" also need the key "value" (any value, None included); "move" and "copy"
need a str "from". Extra keys are ignored. A missing key, a wrong type or an unknown op name is
a ValueError. Ops run in order, each on the result of the previous one.
- add: the parent (all tokens but the last) must resolve. Path "" replaces the whole document.
  In a dict the key is set (replacing any old value). In a list the last token is "-" (append)
  or a canonical index i <= len (insert before position i; i == len appends); i > len is an error.
- remove: the target must resolve; path "" is an error. It removes the key or the list element
  (later elements shift down).
- replace: the target must resolve; path "" replaces the whole document.
- test: the target must resolve and equal "value", else ValueError. Equality is JSON equality:
  dicts compare by keys and values (order ignored), lists element by element; True and False are
  NOT equal to 1 and 0, but 1 == 1.0.
- copy: the "from" target must resolve; its deep copy is added at "path" as in add.
- move: if "from" is a proper prefix of "path" (as token lists; "" is a prefix of every other
  pointer) it is an error. If both are the same pointer, the "from" target must resolve and
  nothing changes. Otherwise remove "from" and then add that value at "path", on the document as
  it is after the removal.
Example: json_patch({"a": [1, 2]}, [{"op": "move", "from": "/a/0", "path": "/a/1"}]) is
{"a": [2, 1]}.
''', r'''
import json, random, re
import copy as _cp

def A(p, v): return {"op": "add", "path": p, "value": v}
def R(p): return {"op": "remove", "path": p}
def RP(p, v): return {"op": "replace", "path": p, "value": v}
def TS(p, v): return {"op": "test", "path": p, "value": v}
def MV(f, p): return {"op": "move", "from": f, "path": p}
def CP(f, p): return {"op": "copy", "from": f, "path": p}

def bad(doc, ops):
    try:
        json_patch(doc, ops)
    except ValueError:
        return True
    return False

def ok(doc, ops, exp):
    got = json_patch(doc, ops)
    assert json.dumps(got, sort_keys=True) == json.dumps(exp, sort_keys=True), (doc, ops, got, exp)

ok({"a": [1, 2]}, [MV("/a/0", "/a/1")], {"a": [2, 1]})
ok(1, [A("", [1])], [1])
ok({}, [A("/x", 1), A("/x", 2), A("/y", None)], {"x": 2, "y": None})
ok([1, 2, 3], [A("/0", 0), A("/2", "m"), A("/-", 9)], [0, 1, "m", 2, 3, 9])
ok([1, 2, 3], [A("/3", 4)], [1, 2, 3, 4])
assert bad([1, 2, 3], [A("/4", 4)])
ok([1, 2, 3], [R("/0"), R("/1")], [2])
assert bad([1], [R("")])
assert bad({"a": 1}, [R("/b")])
assert bad([1], [R("/1")])
ok(5, [RP("", {"z": 1})], {"z": 1})
assert bad({"a": 1}, [RP("/b", 1)])
ok([1, 2], [RP("/1", [3])], [1, [3]])
assert bad([1, 2], [RP("/2", 0)])
ok({"a": 1}, [TS("/a", 1.0), TS("/a", 1)], {"a": 1})
assert bad({"a": True}, [TS("/a", 1)])
assert bad({"a": 0}, [TS("/a", False)])
assert bad({"a": 1}, [TS("/a", True)])
ok({"a": {"x": [1, {"y": None}], "z": 2.5}}, [TS("/a", {"z": 2.5, "x": [1, {"y": None}]})], {"a": {"x": [1, {"y": None}], "z": 2.5}})
assert bad({"a": [1, True]}, [TS("/a", [1, 1])])
assert bad({"a": [1]}, [TS("/a", [1, 2])])
assert bad({"a": {"x": 1}}, [TS("/a", {"x": 1, "y": 2})])
assert bad({"a": None}, [TS("/a", 0)])
ok({"a": None}, [TS("/a", None)], {"a": None})
assert bad({}, [TS("/a", None)])
d = {"a": [1]}
r = json_patch(d, [CP("/a", "/b"), A("/b/-", 2)])
assert r == {"a": [1], "b": [1, 2]} and d == {"a": [1]}
ok([1, 2, 3], [MV("/0", "/2")], [2, 3, 1])
ok([1, 2, 3], [MV("/2", "/0")], [3, 1, 2])
assert bad([1, 2, 3], [MV("/0", "/3")])
assert bad({"a": {"b": 1}}, [MV("/a", "/a/c")])
assert bad({"a": 1}, [MV("", "/a")])
ok({"a": 1}, [MV("/a", "/a")], {"a": 1})
assert bad({"a": 1}, [MV("/b", "/b")])
ok({"a": 1}, [MV("", "")], {"a": 1})
ok({"a": 5}, [MV("/a", "")], 5)
ok({"a": {"b": 1}, "c": 2}, [MV("/a/b", "/c")], {"a": {}, "c": 1})
ok({"a": [1, 2], "b": 0}, [MV("/a/1", "/a/0")], {"a": [2, 1], "b": 0})
ok({"a/b": 1, "m~n": 2, "~1": 3, "": 4}, [TS("/a~1b", 1), TS("/m~0n", 2), TS("/~01", 3), TS("/", 4)], {"a/b": 1, "m~n": 2, "~1": 3, "": 4})
ok({"": {"": 1}}, [TS("//", 1)], {"": {"": 1}})
ok({"a": 1}, [A("/b~0~1", 2)], {"a": 1, "b~/": 2})
for p in ["/~", "/a~", "/~2", "/~x", "/a~~0", "a", "x/y", " /a"]:
    assert bad({"a": 1, "": 1}, [TS(p, 1)]), p
    assert bad({"a": 1, "": 1}, [A(p, 1)]), p
for t in ["01", "+1", "-1", " 1", "1 ", "x", "", "1.0", "١", "-", "00", "-0"]:
    assert bad([5, 6], [RP("/" + t, 0)]), t
    assert bad([5, 6], [R("/" + t)]), t
    assert bad([5, 6], [TS("/" + t, 5)]), t
ok([5, 6], [TS("/0", 5), TS("/1", 6)], [5, 6])
assert bad([[1]], [A("/-/0", 1)])
assert bad({"a": 1}, [A("/a/b", 1)])
assert bad({"a": "str"}, [A("/a/0", 1)])
assert bad([1], [A("/x", 1)])
assert bad([1], [A("/١", 1)])
assert bad({"a": [1]}, [A("/a/b", 1)])
ok({"a": 1}, [], {"a": 1})
ok({"a": 1}, [{"op": "add", "path": "/b", "value": 2, "extra": [1], "from": 7}], {"a": 1, "b": 2})
for ops in [{"op": "add"}, "x", [1], [{"op": "add", "path": "/a"}], [{"op": "zap", "path": "/a"}],
            [{"path": "/a", "value": 1}], [{"op": "add", "path": 1, "value": 1}], [{"op": "move", "path": "/a"}],
            [{"op": "move", "from": 1, "path": "/a"}], [{"op": "copy", "from": "/a"}], [{"op": 1, "path": "/a"}],
            [{"op": "remove"}], [{"op": "test", "path": "/a"}], [{"op": "replace", "path": "/a"}], None, [None]]:
    assert bad({"a": 1}, ops), ops
ok({"a": 1}, [A("/z", None), {"op": "test", "path": "/z", "value": None}], {"a": 1, "z": None})
# no mutation, no sharing
def ids(x, out):
    if isinstance(x, (dict, list)):
        out.add(id(x))
        for y in (x.values() if isinstance(x, dict) else x):
            ids(y, out)
    return out
doc = {"a": [1, {"b": [2]}], "c": {"d": []}}
snap = _cp.deepcopy(doc)
val = {"v": [1, 2]}
ops = [A("/e", val), CP("/a", "/f"), R("/c/d"), TS("/a/1/b/0", 2)]
osnap = _cp.deepcopy(ops)
res = json_patch(doc, ops)
assert doc == snap and ops == osnap
assert not (ids(res, set()) & (ids(doc, set()) | ids(ops, set()))), "result shares a container"
assert res["f"] is not res["a"] and res["e"] is not val
res2 = json_patch(doc, [])
assert res2 == doc and not (ids(res2, set()) & ids(doc, set()))

# oracle: functional implementation
def otok(p):
    if not isinstance(p, str) or (p and p[0] != "/"):
        raise ValueError
    if p == "":
        return []
    out = []
    for r in p[1:].split("/"):
        if re.search(r"~(?![01])", r):
            raise ValueError
        out.append(re.sub(r"~([01])", lambda m: "~" if m.group(1) == "0" else "/", r))
    return out

def oidx(t):
    if not re.fullmatch(r"0|[1-9][0-9]*", t, re.A):
        raise ValueError
    return int(t)

def oget(d, toks):
    for t in toks:
        if isinstance(d, dict):
            if t not in d:
                raise ValueError
            d = d[t]
        elif isinstance(d, list):
            i = oidx(t)
            if i >= len(d):
                raise ValueError
            d = d[i]
        else:
            raise ValueError
    return d

def oset(d, toks, mode, v=None):
    if not toks:
        if mode == "remove":
            raise ValueError
        return v
    t, rest = toks[0], toks[1:]
    if isinstance(d, dict):
        if rest:
            if t not in d:
                raise ValueError
            return {**d, t: oset(d[t], rest, mode, v)}
        if mode == "add":
            return {**d, t: v}
        if t not in d:
            raise ValueError
        if mode == "replace":
            return {**d, t: v}
        return {k: x for k, x in d.items() if k != t}
    if isinstance(d, list):
        if not rest and mode == "add" and t == "-":
            return d + [v]
        i = oidx(t)
        if not rest and mode == "add":
            if i > len(d):
                raise ValueError
            return d[:i] + [v] + d[i:]
        if i >= len(d):
            raise ValueError
        if rest:
            return d[:i] + [oset(d[i], rest, mode, v)] + d[i + 1:]
        return d[:i] + [v] + d[i + 1:] if mode == "replace" else d[:i] + d[i + 1:]
    raise ValueError

def norm(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return ["s", x]
    if isinstance(x, (int, float)):
        return ["n", float(x)]
    if isinstance(x, list):
        return ["l"] + [norm(y) for y in x]
    return ["d", sorted([k, norm(y)] for k, y in x.items())]

def oracle(doc, ops):
    if not isinstance(ops, list):
        raise ValueError
    for o in ops:
        if not isinstance(o, dict) or not isinstance(o.get("op"), str) or not isinstance(o.get("path"), str):
            raise ValueError
        k = o["op"]
        if k in ("add", "replace", "test"):
            if "value" not in o:
                raise ValueError
        elif k in ("move", "copy"):
            if not isinstance(o.get("from"), str):
                raise ValueError
        elif k != "remove":
            raise ValueError
        pt = otok(o["path"])
        if k == "add":
            doc = oset(doc, pt, "add", _cp.deepcopy(o["value"]))
        elif k == "replace":
            oget(doc, pt)
            doc = oset(doc, pt, "replace", _cp.deepcopy(o["value"]))
        elif k == "remove":
            oget(doc, pt)
            doc = oset(doc, pt, "remove")
        elif k == "test":
            if norm(oget(doc, pt)) != norm(o["value"]):
                raise ValueError
        else:
            ft = otok(o["from"])
            v = oget(doc, ft)
            if k == "copy":
                doc = oset(doc, pt, "add", _cp.deepcopy(v))
            elif ft == pt:
                pass
            elif len(ft) < len(pt) and pt[:len(ft)] == ft:
                raise ValueError
            else:
                doc = oset(doc, ft, "remove")
                doc = oset(doc, pt, "add", v)
    return doc

random.seed(4001)
KEYS = ["a", "b", "", "a/b", "m~n", "0", "01", "~1"]

def gen(depth):
    r = random.random()
    if depth == 0 or r < 0.3:
        return random.choice([0, 1, 2.5, 1.0, True, False, None, "s", "", 7])
    if r < 0.65:
        return {k: gen(depth - 1) for k in random.sample(KEYS, random.randint(0, 4))}
    return [gen(depth - 1) for _ in range(random.randint(0, 4))]

def esc(k):
    return k.replace("~", "~0").replace("/", "~1")

def paths(d, pre=""):
    out = [pre]
    if isinstance(d, dict):
        for k, v in d.items():
            out += paths(v, pre + "/" + esc(k))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out += paths(v, pre + "/" + str(i))
    return out

def mutate(p):
    if random.random() < 0.85:
        return p
    return random.choice([p + "/-", p + "/0", p + "/x", p + "/", p + "/~", p + "/~2", p + "/01", p + "/+1", p + "/9", p + "/\u0662", p[:-1] if p else "q", "/" + p, "x" + p])

def child(d, p):
    q = random.choice(paths(d))
    t = oget(d, otok(q))
    if isinstance(t, dict):
        return q + "/" + esc(random.choice(KEYS))
    if isinstance(t, list):
        return q + "/" + random.choice(["-", str(random.randint(0, len(t)))])
    return q

def rand_ops(doc):
    ops = []
    cur = doc
    for _ in range(random.randint(1, 6)):
        ps = paths(cur)
        k = random.choice(["add", "add", "remove", "replace", "test", "move", "move", "copy"])
        p = mutate(child(cur, "") if k in ("add", "copy", "move") else random.choice(ps))
        if k in ("add", "replace"):
            ops.append({"op": k, "path": p, "value": gen(2)})
        elif k == "remove":
            ops.append({"op": k, "path": p})
        elif k == "test":
            try:
                v = _cp.deepcopy(oget(cur, otok(p)))
            except ValueError:
                v = gen(1)
            if random.random() < 0.1:
                v = random.choice([True, 1, 1.0, 0, False])
            ops.append({"op": k, "path": p, "value": v})
        else:
            ops.append({"op": k, "from": mutate(random.choice(ps)), "path": p})
        try:
            cur = oracle(doc, ops)
        except ValueError:
            break
    return ops

nbad = 0
for _ in range(4000):
    doc = gen(3)
    ops = rand_ops(doc)
    snap = _cp.deepcopy(doc)
    try:
        exp = oracle(doc, ops)
        e = None
    except ValueError:
        e = True
    try:
        got = json_patch(doc, ops)
        g = None
    except ValueError:
        g = True
    assert doc == snap
    assert e == g, (doc, ops, e, g)
    if e is None:
        assert norm(got) == norm(exp), (doc, ops, got, exp)
        assert not (ids(got, set()) & (ids(doc, set()) | ids(ops, set())))
    else:
        nbad += 1

assert 500 < nbad < 3000, nbad
''', r'''
import copy

def _tokens(p):
    if not isinstance(p, str):
        raise ValueError("pointer")
    if p == "":
        return []
    if p[0] != "/":
        raise ValueError("pointer")
    out = []
    for raw in p[1:].split("/"):
        s = []
        i = 0
        while i < len(raw):
            c = raw[i]
            if c == "~":
                if i + 1 < len(raw) and raw[i + 1] in "01":
                    s.append("~" if raw[i + 1] == "0" else "/")
                    i += 2
                    continue
                raise ValueError("escape")
            s.append(c)
            i += 1
        out.append("".join(s))
    return out


def _index(t):
    if not (t.isascii() and t.isdigit() and (t == "0" or t[0] != "0")):
        raise ValueError("index")
    return int(t)


def _get(cur, toks):
    for t in toks:
        if isinstance(cur, dict):
            if t not in cur:
                raise ValueError("missing")
            cur = cur[t]
        elif isinstance(cur, list):
            i = _index(t)
            if i >= len(cur):
                raise ValueError("missing")
            cur = cur[i]
        else:
            raise ValueError("scalar")
    return cur


def _eq(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_eq(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_eq(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _add(doc, toks, val):
    if not toks:
        return val
    parent = _get(doc, toks[:-1])
    last = toks[-1]
    if isinstance(parent, dict):
        parent[last] = val
    elif isinstance(parent, list):
        if last == "-":
            parent.append(val)
        else:
            i = _index(last)
            if i > len(parent):
                raise ValueError("index")
            parent.insert(i, val)
    else:
        raise ValueError("scalar")
    return doc


def _remove(doc, toks):
    if not toks:
        raise ValueError("root")
    parent = _get(doc, toks[:-1])
    last = toks[-1]
    if isinstance(parent, dict):
        if last not in parent:
            raise ValueError("missing")
        return doc, parent.pop(last)
    if isinstance(parent, list):
        i = _index(last)
        if i >= len(parent):
            raise ValueError("missing")
        return doc, parent.pop(i)
    raise ValueError("scalar")


def json_patch(doc, ops):
    if not isinstance(ops, list):
        raise ValueError("ops")
    doc = copy.deepcopy(doc)
    for o in ops:
        if not isinstance(o, dict) or not isinstance(o.get("op"), str) or not isinstance(o.get("path"), str):
            raise ValueError("op")
        k = o["op"]
        if k in ("add", "replace", "test"):
            if "value" not in o:
                raise ValueError("value")
        elif k in ("move", "copy"):
            if not isinstance(o.get("from"), str):
                raise ValueError("from")
        elif k != "remove":
            raise ValueError("op name")
        pt = _tokens(o["path"])
        if k == "add":
            doc = _add(doc, pt, copy.deepcopy(o["value"]))
        elif k == "remove":
            doc, _ = _remove(doc, pt)
        elif k == "replace":
            _get(doc, pt)
            if not pt:
                doc = copy.deepcopy(o["value"])
            else:
                parent = _get(doc, pt[:-1])
                if isinstance(parent, dict):
                    parent[pt[-1]] = copy.deepcopy(o["value"])
                else:
                    parent[_index(pt[-1])] = copy.deepcopy(o["value"])
        elif k == "test":
            if not _eq(_get(doc, pt), o["value"]):
                raise ValueError("test")
        else:
            ft = _tokens(o["from"])
            val = _get(doc, ft)
            if k == "copy":
                doc = _add(doc, pt, copy.deepcopy(val))
            elif ft == pt:
                continue
            elif len(ft) < len(pt) and pt[:len(ft)] == ft:
                raise ValueError("into itself")
            else:
                doc, val = _remove(doc, ft)
                doc = _add(doc, pt, val)
    return doc
''')

task("v4_02_mini_asm", r'''
Write `assemble(src: str) -> bytes` for a tiny 8-bit machine. It returns the memory image from
address 0 up to just past the highest byte emitted (a program that emits nothing gives b"");
bytes never written are 0. Every error raises ValueError. Whitespace is spaces and tabs; lines
end at "\n" (a trailing "\r" is ignored). Mnemonics, directives and register names are
case-insensitive; names (labels and .equ constants) are case-sensitive.
A line is: zero or more labels `NAME:` (the colon directly after the name), then an optional
statement, then an optional comment that starts at the first ";" outside any "..." string or
'...' character literal. NAME is [A-Za-z_][A-Za-z0-9_]*; r0-r3 in any case are not allowed as
names, and a name may be defined only once (labels and .equ constants share one namespace). A
label's value is the location counter where it appears. The counter starts at 0; no byte may
be placed above address 65535.
A statement is a mnemonic or directive and comma-separated operands (commas inside strings,
character literals or parentheses do not split; an empty operand is an error).
Expressions: numbers (decimal, 0x.., 0b..; a number directly followed by a letter, digit or "_"
is an error), character literals (one ASCII character, or one escape: \n \t \r \0 \\ \' \" \xHH),
names, and `$` (the location counter at the start of the current statement; the same for all
its operands), with parentheses, unary - and ~, and these binary operators from tightest to
loosest: * / %  |  + -  |  << >>  |  &  |  ^  |  |  (all left associative). / and % floor like
Python and a zero divisor is an error; a shift count outside 0..64 is an error. Integers are
unbounded; range checks apply where a value is stored.
Instructions (registers r0-r3, D and S are register numbers):
  nop = 00; hlt = 01 (no operands); ldi rD, e = 10+D, e (e in -128..255, stored mod 256);
  mov rD, rS = 20+4*D+S; add rD, rS = 30+4*D+S; jmp e = 40 lo hi; jz e = 41 lo hi (e in
  0..65535, little endian); br e = 50 off, where off = e - (address of the next instruction)
  must be in -128..127 and is stored mod 256.
Directives: .byte e,... (each -128..255, stored mod 256); .word e,... (each -32768..65535,
little endian); .ascii "s",... (string literals only, with escapes \n \t \r \0 \\ \" \xHH,
ASCII only); .space n[, fill] (n bytes of fill, default 0, fill in -128..255, 0 <= n <= 65536);
.align n (n a power of two, 1..4096; zero bytes up to the next multiple of n); .org e (set
the counter to e, which must be >= the counter and <= 65535; skipped bytes are 0);
.equ NAME, e (define a constant; `$` in e is the counter at that line).
Order of evaluation: the operand of .org, the count of .space and the operand of .align are
evaluated when their line is reached, and may use only labels and .equ names defined on
earlier lines (an .equ expression used there is evaluated by the same rule at that point).
Every other expression may refer forward. Every .equ expression is evaluated, used or not; a
cycle or an undefined name is an error.
Example: "start: ldi r1, 5\n br start" is b"\x11\x05\x50\xfc".
''', r'''
import random

def asm(src, exp):
    got = assemble(src)
    assert isinstance(got, bytes) and got == exp, (src, got, exp)

def bad(src):
    try:
        assemble(src)
    except ValueError:
        return True
    return False

asm("start: ldi r1, 5\n br start", b"\x11\x05\x50\xfc")
asm("", b"")
asm("\n  ; only a comment\n\t\n", b"")
asm("nop\nhlt", b"\x00\x01")
asm("ldi r1, 5", b"\x11\x05")
asm("LDI R3, -1", b"\x13\xff")
asm("ldi r0, 255\nldi r2, -128", b"\x10\xff\x12\x80")
for s in ["ldi r0, 256", "ldi r0, -129", "ldi r4, 1", "ldi 1, 2", "ldi r1", "ldi r1, r2", "ldi r1, 2, 3", "ldi r1,", "ldi , 1", "ldi r-1, 1", "ldi rr, 1"]:
    assert bad(s), s
asm("mov r1, r2", b"\x26")
asm("add r3, r0", b"\x3c")
asm("MOV r0,R3\nadd R2 ,r2", b"\x23\x3a")
for s in ["mov r1", "mov r1, 5", "mov 1, r1", "add r1, r2, r3", "mov r1 r2", "nop 1", "hlt r0", "foo", "ld r1, 2"]:
    assert bad(s), s
asm("jmp 0x1234", b"\x40\x34\x12")
asm("jz end\nnop\nend: hlt", b"\x41\x04\x00\x00\x01")
for s in ["jmp 65536", "jmp -1", "jz", "jmp 1, 2"]:
    assert bad(s), s
asm("jmp 65535", b"\x40\xff\xff")
asm("br next\nnext: hlt", b"\x50\x00\x01")
asm("top: nop\n br top", b"\x00\x50\xfd")
asm("br far\n.space 127\nfar: nop", b"\x50\x7f" + bytes(127) + b"\x00")
assert bad("br far\n.space 128\nfar: nop")
asm("top: .space 126\n br top", bytes(126) + b"\x50\x80")
assert bad("top: .space 127\n br top")
asm(".byte 1, -1, 'A', 0x10, 0b101, '\\n'", bytes([1, 255, 65, 16, 5, 10]))
asm(".byte 255, -128, 0", bytes([255, 128, 0]))
assert bad(".byte 256") and bad(".byte -129") and bad(".byte") and bad(".byte 1,") and bad(".byte ,1") and bad(".byte 1,,2")
asm(".word 0x1234, -1, 65535", b"\x34\x12\xff\xff\xff\xff")
assert bad(".word 65536") and bad(".word -32769") and bad(".word")
asm('.ascii "hi\\n\\x41\\"\\\\"', b'hi\nA"\\')
asm('.ascii "a;b" ; comment', b"a;b")
asm('.ascii "a", "bc",""', b"abc")
asm('.ascii "x:y"', b"x:y")
asm('.ascii "it\'s"', b"it's")
asm('.ascii "\\0\\x7f\\x00"', b"\x00\x7f\x00")
for s in ['.ascii "abc', '.ascii "a\\q"', '.ascii "é"', ".ascii 5", ".ascii", '.ascii "a" "b"', '.ascii "a\\x4"', '.ascii "a"b"', ".ascii 'a'"]:
    assert bad(s), s
asm(".org 4\n hlt", b"\x00\x00\x00\x00\x01")
assert bad(".org 2\n.org 1")
asm(".org 2\n.org 2\nhlt", b"\x00\x00\x01")
asm(".org 4", b"")
asm(".org 4\n.space 0\n.align 4", b"")
asm(".org 5\n.align 4\nhlt", bytes(8) + b"\x01")
asm(".space 3, 7", b"\x07\x07\x07")
asm(".space 2\n.byte 1", b"\x00\x00\x01")
asm(".space 2, -1", b"\xff\xff")
asm(".space 0", b"")
assert len(assemble(".space 65536")) == 65536
for s in [".space -1", ".space 65537", ".space", ".space 1, 256", ".space 1, 2, 3", ".align 3", ".align 0", ".align 8192", ".align", ".align -2", ".org", ".org 65536", ".org -1", ".org 1, 2"]:
    assert bad(s), s
asm(".byte 1\n.align 1\n.byte 2", b"\x01\x02")
asm(".byte 1\n.align 4096\n.byte 2", b"\x01" + bytes(4095) + b"\x02")
asm(".org 0xFFFF\n.byte 1", bytes(65535) + b"\x01")
assert bad(".org 0xFFFF\n.word 1") and bad(".org 65535\n.ascii \"ab\"") and bad(".space 65536\n.byte 1")
asm(".equ N, 3\n.byte N*2", b"\x06")
asm(".byte K\n.equ K, T+1\n.equ T, 4", b"\x05")
asm(".equ a, 1\n.equ b, a+1\n.byte a, b", b"\x01\x02")
for s in [".equ a, b\n.equ b, a", ".equ a, a", ".equ a, zz", ".equ a, 1\n.equ a, 1", "a: nop\n.equ a, 1", "a: nop\na: nop", ".equ r1, 1", "R2: nop",
          ".equ a, b\n.equ b, 1\n.equ c, d", ".equ 1x, 2", ".equ N 5", ".equ N", ".equ N, 1, 2", ".equ , 1", ".equ N, ", ".byte undefined_name", ".equ x, 1/0"]:
    assert bad(s), s
asm("a: nop\nA: hlt\n.byte a, A", b"\x00\x01\x00\x01")
assert bad("L: nop\n jmp l")
assert bad(".org later\nlater: nop") and bad(".space later\nlater: nop") and bad(".align later\nlater: nop")
assert bad(".org E\n.equ E, 3")
asm("L: nop\n.equ E, L+3\n.org E\nhlt", b"\x00\x00\x00\x01")
asm(".equ E, L+3\nL: nop\n.org E\nhlt", b"\x00\x00\x00\x01")
asm(".org 2\n.equ here, $\n.byte here", b"\x00\x00\x02")
asm(".org 3\n.byte $, $+1", b"\x00\x00\x00\x03\x04")
asm("a: b: nop\nc:\n.word a, b, c", b"\x00" + b"\x00\x00\x00\x00\x01\x00")
asm("x: .byte x\ny: .byte y", b"\x00\x01")
asm("  \t lab:\tldi r0 ,\t7 ; c\r\n\tjmp lab\r", b"\x10\x07\x40\x00\x00")
for s in ["lab : nop", "lab::", ":", "1a: nop", "a b: nop", "nop,", "nop:x", ".byte1 5", ".unknown 1", "ldi,r1,2"]:
    assert bad(s), s
asm(".byte 1+2*3", b"\x07")
asm(".byte 7-2-1, 2*3%4, 100/7/2", b"\x04\x02\x07")
asm(".byte 1<<2+1", b"\x08")
asm(".byte 6&3|8, 5^1&3, 2|1^3, 1|2&3^4", bytes([10, 4, 2, 7]))
asm(".byte -7/2, -7%3, ~0, -(-3), - -3, ~~5", bytes([252, 2, 255, 3, 3, 5]))
asm(".byte 7 / -2, 7 % -2, -7 >> 1, 1 << 7 >> 3, (1+2)*(3+4)", bytes([252, 255, 252, 16, 21]))
asm(".byte 08, 0X1f, 0B11, 'a'+1, '\\x41', '\\'', ','", bytes([8, 31, 3, 98, 65, 39, 44]))
asm(".byte ';' ; c\n.byte ';', ';'", bytes([59, 59, 59]))
asm(".word 1<<15, (1<<16)-1, 0xFFFF&~1, -(1<<15)", b"\x00\x80\xff\xff\xfe\xff\x00\x80")
asm(".byte 1<<64>>64, 1<<0", b"\x01\x01")
for s in [".byte 10/0", ".byte 10%0", ".byte 1<<65", ".byte 1<<-1", ".byte 1>>65", ".byte (1+2", ".byte 1+2)", ".byte ()", ".byte 1 2", ".byte *2", ".byte 2*", ".byte 1 + + 2".replace("+ +", "* *"),
          ".byte 0x", ".byte 0x1G", ".byte 12ab", ".byte 0b12", ".byte 1_0", ".byte ''", ".byte 'ab'", ".byte '\\q'", ".byte '\\x4'", ".byte 'a", ".byte \"a\"", ".byte 1 $", ".byte $$", ".byte 1+", ".byte 3 ? 4", ".byte 1 < 2", ".byte 2**2", ".byte 1,\n,2".replace("\n", "")]:
    assert bad(s), s
assert bad(".byte 1<<64")

# random expressions against Python's evaluator
random.seed(4002)
def lit():
    v = random.choice([0, 1, 2, 3, 5, 7, 10, 16, 31, 100, 255])
    f = random.random()
    return (str(v), v) if f < 0.5 else (hex(v), v) if f < 0.7 else (bin(v), v) if f < 0.85 else ("'%s'" % chr(v) if 33 <= v < 127 and chr(v) not in "\\'" else str(v), v)

def gexpr(d):
    if d == 0 or random.random() < 0.25:
        return lit()
    r = random.random()
    if r < 0.15:
        t, _ = gexpr(d - 1)
        o = random.choice(["-", "~"])
        return o + "(" + t + ")" if random.random() < 0.5 else o + t if t[0] not in "-~" else o + "(" + t + ")", None
    if r < 0.25:
        t, _ = gexpr(d - 1)
        return "(" + t + ")", None
    a, _ = gexpr(d - 1)
    b, _ = gexpr(d - 1)
    o = random.choice(["*", "/", "%", "+", "-", "<<", ">>", "&", "^", "|", "+", "-", "&", "|"])
    sp = random.choice(["", " "])
    return a + sp + o + sp + b, None

class I(int):
    pass

def _wrap(f):
    return lambda self, o: I(f(int(self), int(o)))

for _n in ["__add__", "__sub__", "__mul__", "__floordiv__", "__mod__", "__and__", "__or__", "__xor__"]:
    setattr(I, _n, _wrap(getattr(int, _n)))

def _shift(f):
    def g(self, o):
        if not 0 <= o <= 64:
            raise ValueError("shift")
        return I(f(int(self), int(o)))
    return g

I.__lshift__ = _shift(int.__lshift__)
I.__rshift__ = _shift(int.__rshift__)
I.__neg__ = lambda self: I(-int(self))
I.__invert__ = lambda self: I(~int(self))

def pyval(t):
    t2 = re.sub(r"'(.)'", lambda m: str(ord(m.group(1))), t)
    t2 = re.sub(r"/", "//", t2)
    t2 = re.sub(r"0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+", lambda m: "I(" + m.group(0) + ")", t2)
    return int(eval(t2, {"__builtins__": {}, "I": I}, {}))

import re
nerr = nok = 0
for _ in range(1500):
    t, _ = gexpr(random.randint(1, 4))
    try:
        v = pyval(t)
        e = None
    except (ZeroDivisionError, ValueError, OverflowError, MemoryError):
        e = True
    wide = random.random() < 0.5
    src = (".word " if wide else ".byte ") + t
    if e is None:
        lo, hi = (-32768, 65535) if wide else (-128, 255)
        if not lo <= v <= hi:
            e = True
    if e:
        assert bad(src), (src,)
        nerr += 1
    else:
        asm(src, (v & 0xFFFF).to_bytes(2, "little") if wide else bytes([v & 255]))
        nok += 1
assert nok > 400 and nerr > 100, (nok, nerr)

# random data layouts with labels
def layout():
    names = ["l%d" % i for i in range(random.randint(1, 4))]
    items = []
    n = random.randint(3, 12)
    kinds = ["byte", "word", "ascii", "space", "align", "org", "jmp", "br", "wordref", "nop"]
    for _ in range(n):
        items.append(random.choice(kinds))
    for nm in names:
        items.insert(random.randint(0, len(items)), "label:" + nm)
    lines = []
    sim = []
    loc = 0
    labels = {}
    for it in items:
        if it.startswith("label:"):
            labels[it[6:]] = loc
            lines.append(it[6:] + ":")
            sim.append(("label",))
        elif it == "byte":
            vs = [random.randint(-128, 255) for _ in range(random.randint(1, 4))]
            lines.append(".byte " + ", ".join(map(str, vs)))
            sim.append(("data", loc, bytes(v & 255 for v in vs)))
            loc += len(vs)
        elif it == "word":
            vs = [random.randint(-32768, 65535) for _ in range(random.randint(1, 3))]
            lines.append(".word " + ", ".join(hex(v) if v >= 0 else str(v) for v in vs))
            sim.append(("data", loc, b"".join((v & 0xFFFF).to_bytes(2, "little") for v in vs)))
            loc += 2 * len(vs)
        elif it == "ascii":
            s = "".join(random.choice("abc xyz;:,'") for _ in range(random.randint(0, 5)))
            lines.append('.ascii "' + s + '"  ; c')
            sim.append(("data", loc, s.encode()))
            loc += len(s)
        elif it == "space":
            k = random.randint(0, 5)
            f = random.randint(-128, 255)
            lines.append(".space %d, %d" % (k, f))
            sim.append(("data", loc, bytes([f & 255]) * k))
            loc += k
        elif it == "align":
            a = random.choice([1, 2, 4, 8, 16])
            p = -loc % a
            lines.append(".align %d" % a)
            sim.append(("data", loc, bytes(p)))
            loc += p
        elif it == "org":
            t = loc + random.randint(0, 6)
            lines.append(".org %s" % random.choice([str(t), "$+%d" % (t - loc)]))
            loc = t
            sim.append(("label",))
        elif it == "nop":
            lines.append("nop")
            sim.append(("data", loc, b"\x00"))
            loc += 1
        elif it == "jmp":
            sim.append(("jmp", loc, random.choice(names)))
            lines.append("jmp " + sim[-1][2])
            loc += 3
        elif it == "br":
            sim.append(("br", loc, random.choice(names)))
            lines.append("br " + sim[-1][2])
            loc += 2
        else:
            sim.append(("wordref", loc, random.choice(names), random.randint(0, 3)))
            lines.append(".word %s+%d" % (sim[-1][2], sim[-1][3]))
            loc += 2
    mem = {}
    err = False
    for s in sim:
        if s[0] == "data":
            for i, b in enumerate(s[2]):
                mem[s[1] + i] = b
        elif s[0] == "jmp":
            a = labels[s[2]]
            for i, b in enumerate(bytes([0x40, a & 255, a >> 8])):
                mem[s[1] + i] = b
        elif s[0] == "br":
            off = labels[s[2]] - (s[1] + 2)
            if not -128 <= off <= 127:
                err = True
            else:
                mem[s[1]] = 0x50
                mem[s[1] + 1] = off & 255
        elif s[0] == "wordref":
            a = labels[s[2]] + s[3]
            mem[s[1]] = a & 255
            mem[s[1] + 1] = a >> 8
    end = max(mem) + 1 if mem else 0
    return "\n".join(lines), (None if err else bytes(mem.get(i, 0) for i in range(end)))

nl = 0
for _ in range(600):
    src, exp = layout()
    if exp is None:
        assert bad(src), src
    else:
        asm(src, exp)
        nl += 1
assert nl > 300, nl
''', r'''
import re

_REG = re.compile(r"[rR][0-3]$")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_TOK = re.compile(r"[ \t]*(?:(0[xX][0-9a-fA-F]+|0[bB][01]+|[0-9]+)|('(?:\\x[0-9a-fA-F]{2}|\\.|[^\\'])')|([A-Za-z_][A-Za-z0-9_]*)|(\$)|(<<|>>|[-+*/%&|^~()]))")
_ESC = {"n": 10, "t": 9, "r": 13, "0": 0, "\\": 92, "'": 39, '"': 34}
_PREC = {"|": 1, "^": 2, "&": 3, "<<": 4, ">>": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}


def _strip(line):
    out = []
    q = None
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == "\\":
                i += 1
                if i >= len(line):
                    raise ValueError("escape")
                out.append(line[i])
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            out.append(c)
        elif c == ";":
            break
        else:
            out.append(c)
        i += 1
    if q:
        raise ValueError("unterminated")
    return "".join(out).strip(" \t\r")


def _split(text):
    if text == "":
        return []
    parts, cur, q, depth, i = [], [], None, 0, 0
    while i < len(text):
        c = text[i]
        if q:
            cur.append(c)
            if c == "\\" and i + 1 < len(text):
                i += 1
                cur.append(text[i])
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c == "(":
            depth += 1
            cur.append(c)
        elif c == ")":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur).strip(" \t"))
            cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur).strip(" \t"))
    if q or any(p == "" for p in parts):
        raise ValueError("operand")
    return parts


def _char(body):
    if body[0] != "\\":
        if ord(body) > 127:
            raise ValueError("ascii")
        return ord(body)
    if body[1] == "x":
        return int(body[2:], 16)
    if body[1] not in _ESC:
        raise ValueError("escape")
    return _ESC[body[1]]


def _tokens(text):
    toks = []
    pos = 0
    while True:
        rest = text[pos:]
        if rest.strip(" \t") == "":
            return toks
        m = _TOK.match(text, pos)
        if not m:
            raise ValueError("token")
        pos = m.end()
        if m.group(1) is not None:
            if pos < len(text) and (text[pos].isalnum() or text[pos] == "_"):
                raise ValueError("number")
            g = m.group(1)
            if g[:2] in ("0x", "0X"):
                toks.append(("n", int(g[2:], 16)))
            elif g[:2] in ("0b", "0B"):
                toks.append(("n", int(g[2:], 2)))
            else:
                toks.append(("n", int(g)))
        elif m.group(2) is not None:
            toks.append(("n", _char(m.group(2)[1:-1])))
        elif m.group(3) is not None:
            toks.append(("name", m.group(3)))
        elif m.group(4) is not None:
            toks.append(("here", None))
        else:
            toks.append(("op", m.group(5)))


def _eval(text, here, lookup):
    toks = _tokens(text)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def unary():
        nonlocal pos
        t = peek()
        if t is None:
            raise ValueError("expression")
        pos += 1
        if t[0] == "n":
            return t[1]
        if t[0] == "here":
            return here
        if t[0] == "name":
            return lookup(t[1])
        if t[1] == "-":
            return -unary()
        if t[1] == "~":
            return ~unary()
        if t[1] == "(":
            v = expr(1)
            c = peek()
            if c != ("op", ")"):
                raise ValueError("paren")
            pos += 1
            return v
        raise ValueError("expression")

    def expr(minp):
        nonlocal pos
        left = unary()
        while True:
            t = peek()
            if t is None or t[0] != "op" or t[1] not in _PREC or _PREC[t[1]] < minp:
                return left
            pos += 1
            right = expr(_PREC[t[1]] + 1)
            o = t[1]
            if o in ("/", "%") and right == 0:
                raise ValueError("zero")
            if o in ("<<", ">>") and not 0 <= right <= 64:
                raise ValueError("shift")
            left = {"|": lambda: left | right, "^": lambda: left ^ right, "&": lambda: left & right,
                    "<<": lambda: left << right, ">>": lambda: left >> right, "+": lambda: left + right,
                    "-": lambda: left - right, "*": lambda: left * right, "/": lambda: left // right,
                    "%": lambda: left % right}[o]()

    v = expr(1)
    if pos != len(toks):
        raise ValueError("trailing")
    return v


def _string(op):
    if len(op) < 2 or op[0] != '"' or op[-1] != '"':
        raise ValueError("string")
    body = op[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == '"':
            raise ValueError("quote")
        if c == "\\":
            i += 1
            if i >= len(body):
                raise ValueError("escape")
            e = body[i]
            if e == "x":
                h = body[i + 1:i + 3]
                if len(h) != 2 or any(x not in "0123456789abcdefABCDEF" for x in h):
                    raise ValueError("escape")
                out.append(int(h, 16))
                i += 2
            elif e in _ESC:
                out.append(_ESC[e])
            else:
                raise ValueError("escape")
        else:
            if ord(c) > 127:
                raise ValueError("ascii")
            out.append(ord(c))
        i += 1
    return bytes(out)


_ARITY = {"nop": 0, "hlt": 0, "ldi": 2, "mov": 2, "add": 2, "jmp": 1, "jz": 1, "br": 1}
_SIZE = {"nop": 1, "hlt": 1, "ldi": 2, "mov": 1, "add": 1, "jmp": 3, "jz": 3, "br": 2}


def assemble(src):
    labels, equs, plan = {}, {}, []
    loc = 0

    def ev(text, here, stack=()):
        def lookup(n):
            if n in labels:
                return labels[n]
            if n in equs:
                if n in stack:
                    raise ValueError("cycle")
                t, h = equs[n]
                return ev(t, h, stack + (n,))
            raise ValueError("undefined " + n)
        return _eval(text, here, lookup)

    def define(name, table, value):
        if not _NAME.match(name) or _REG.match(name) or name in labels or name in equs:
            raise ValueError("name")
        table[name] = value

    for line in src.split("\n"):
        s = _strip(line)
        while True:
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*):", s)
            if not m:
                break
            define(m.group(1), labels, loc)
            s = s[m.end():].lstrip(" \t")
        if not s:
            continue
        m = re.match(r"\.?[A-Za-z_][A-Za-z0-9_]*", s)
        if not m:
            raise ValueError("statement")
        word = m.group(0).lower()
        rest = s[m.end():]
        if rest and rest[0] not in " \t":
            raise ValueError("statement")
        ops = _split(rest.strip(" \t"))
        start = loc
        if word == ".equ":
            if len(ops) != 2:
                raise ValueError("equ")
            define(ops[0], equs, (ops[1], loc))
            continue
        elif word == ".org":
            if len(ops) != 1:
                raise ValueError("org")
            v = ev(ops[0], loc)
            if not loc <= v <= 0xFFFF:
                raise ValueError("org")
            loc = v
            continue
        elif word == ".space":
            if len(ops) not in (1, 2):
                raise ValueError("space")
            n = ev(ops[0], loc)
            if not 0 <= n <= 65536:
                raise ValueError("space")
            plan.append((start, word, ops, n))
            loc += n
        elif word == ".align":
            if len(ops) != 1:
                raise ValueError("align")
            n = ev(ops[0], loc)
            if n < 1 or n > 4096 or n & (n - 1):
                raise ValueError("align")
            pad = -loc % n
            plan.append((start, word, ops, pad))
            loc += pad
        elif word == ".byte":
            if not ops:
                raise ValueError("byte")
            plan.append((start, word, ops, None))
            loc += len(ops)
        elif word == ".word":
            if not ops:
                raise ValueError("word")
            plan.append((start, word, ops, None))
            loc += 2 * len(ops)
        elif word == ".ascii":
            if not ops:
                raise ValueError("ascii")
            data = b"".join(_string(o) for o in ops)
            plan.append((start, word, ops, data))
            loc += len(data)
        elif word in _ARITY:
            if len(ops) != _ARITY[word]:
                raise ValueError("operands")
            plan.append((start, word, ops, None))
            loc += _SIZE[word]
        else:
            raise ValueError("unknown " + word)
        if loc > 0x10000:
            raise ValueError("overflow")
    for name, (t, h) in equs.items():
        ev(t, h, (name,))
    mem = bytearray(65536)
    end = 0

    def put(addr, data):
        nonlocal end
        if addr + len(data) > 65536:
            raise ValueError("overflow")
        if data:
            mem[addr:addr + len(data)] = data
            end = max(end, addr + len(data))

    def rng(v, lo, hi):
        if not lo <= v <= hi:
            raise ValueError("range")
        return v

    def reg(o):
        if not _REG.match(o):
            raise ValueError("register")
        return int(o[1])

    for start, word, ops, extra in plan:
        if word == ".byte":
            put(start, bytes(rng(ev(o, start), -128, 255) & 255 for o in ops))
        elif word == ".word":
            put(start, b"".join((rng(ev(o, start), -32768, 65535) & 0xFFFF).to_bytes(2, "little") for o in ops))
        elif word == ".ascii":
            put(start, extra)
        elif word == ".space":
            f = rng(ev(ops[1], start), -128, 255) & 255 if len(ops) == 2 else 0
            put(start, bytes([f]) * extra)
        elif word == ".align":
            put(start, bytes(extra))
        elif word == "nop":
            put(start, b"\x00")
        elif word == "hlt":
            put(start, b"\x01")
        elif word == "ldi":
            put(start, bytes([0x10 + reg(ops[0]), rng(ev(ops[1], start), -128, 255) & 255]))
        elif word == "mov":
            put(start, bytes([0x20 + 4 * reg(ops[0]) + reg(ops[1])]))
        elif word == "add":
            put(start, bytes([0x30 + 4 * reg(ops[0]) + reg(ops[1])]))
        elif word in ("jmp", "jz"):
            a = rng(ev(ops[0], start), 0, 65535)
            put(start, bytes([0x40 if word == "jmp" else 0x41, a & 255, a >> 8]))
        else:
            off = rng(ev(ops[0], start) - (start + 2), -128, 127)
            put(start, bytes([0x50, off & 255]))
    return bytes(mem[:end])
''')

task("v4_03_dst_zone", r'''
Write `local_to_utc(zone, y, mo, d, h, mi, fold=0)` and `next_transition(zone, t)` for a time
zone with at most one daylight-saving rule. A UTC instant is an int number of minutes since
1970-01-01 00:00 UTC; dates are proleptic Gregorian.
`zone` is a dict with "std" (int, the standard offset from UTC in minutes, -900..900) and
"dst" (None, or a dict with "save" (int, 1..180 minutes) and "start" and "end", each a
sequence of 5 ints (month, week, weekday, hour, minute)). Both keys are required; extra keys are ignored. A rule
means: the week-th weekday of that month (week 1-4 is the 1st-4th such weekday, -1 is the
last one; weekday 0 = Monday ... 6 = Sunday) at wall-clock hour:minute (hour 0-23, minute
0-59). The start rule is read on the standard clock (offset std) and the end rule on the
daylight clock (offset std+save); the two months must differ. For a year Y, daylight time
begins at the start rule's instant in Y and ends at the end rule's instant in Y if the start
month is before the end month (northern zones), else at the end rule's instant in Y+1
(southern zones, whose daylight period crosses New Year). The offset in effect is std+save
during daylight time and std otherwise. Any invalid zone value (types, ranges, rule fields,
equal months) is a ValueError for both functions, even if the other arguments would not
touch the rule.
local_to_utc: y must be in 1970..2100, (y, mo, d) a real date, h in 0..23, mi in 0..59 and
fold 0 or 1, else ValueError. It returns the UTC instant of that wall-clock time. A wall time
that never occurs (skipped when the clocks go forward) is a ValueError. A wall time that
occurs twice (when the clocks go back) is resolved by fold: 0 is the first occurrence and 1
the second; for every other wall time fold is ignored.
next_transition: returns (instant, offset_after) for the first change of offset strictly
after the UTC instant t (any int), where offset_after is std+save at a start and std at an
end; it returns None if "dst" is None.
Example (std -360, save 60, start (3, 2, 6, 2, 0), end (11, 1, 6, 2, 0)): 2026-03-08 02:30
does not exist, and 2026-11-01 01:30 is 06:30 UTC with fold 0 and 07:30 UTC with fold 1.
''', r'''
import calendar, datetime as dt, random
from bisect import bisect_right

def tg(y, mo, d, h, mi):
    return calendar.timegm((y, mo, d, h, mi, 0)) // 60

def Z(std, save=None, s=None, e=None):
    return {"std": std, "dst": None if save is None else {"save": save, "start": s, "end": e}}

US = Z(-360, 60, (3, 2, 6, 2, 0), (11, 1, 6, 2, 0))
SYD = Z(600, 60, (10, 1, 6, 2, 0), (4, 1, 6, 3, 0))
LH = Z(630, 30, (10, 1, 6, 2, 0), (4, 1, 6, 2, 0))
UTCZ = Z(0)

def bad(*a):
    try:
        local_to_utc(*a)
    except ValueError:
        return True
    return False

def badn(z, t):
    try:
        next_transition(z, t)
    except ValueError:
        return True
    return False

assert local_to_utc(US, 2026, 3, 8, 1, 59) == tg(2026, 3, 8, 7, 59)
assert bad(US, 2026, 3, 8, 2, 0) and bad(US, 2026, 3, 8, 2, 30) and bad(US, 2026, 3, 8, 2, 59, 1)
assert local_to_utc(US, 2026, 3, 8, 3, 0) == tg(2026, 3, 8, 8, 0)
assert local_to_utc(US, 2026, 11, 1, 0, 59) == tg(2026, 11, 1, 5, 59)
assert local_to_utc(US, 2026, 11, 1, 1, 30) == tg(2026, 11, 1, 6, 30)
assert local_to_utc(US, 2026, 11, 1, 1, 30, 1) == tg(2026, 11, 1, 7, 30)
assert local_to_utc(US, 2026, 11, 1, 1, 0, 0) == tg(2026, 11, 1, 6, 0) and local_to_utc(US, 2026, 11, 1, 1, 0, 1) == tg(2026, 11, 1, 7, 0)
assert local_to_utc(US, 2026, 11, 1, 2, 0) == tg(2026, 11, 1, 8, 0) and local_to_utc(US, 2026, 11, 1, 2, 0, 1) == tg(2026, 11, 1, 8, 0)
assert local_to_utc(US, 2026, 7, 1, 12, 0) == tg(2026, 7, 1, 17, 0) and local_to_utc(US, 2026, 1, 1, 12, 0) == tg(2026, 1, 1, 18, 0)
assert local_to_utc(UTCZ, 1970, 1, 1, 0, 0) == 0 and local_to_utc(Z(-60), 1970, 1, 1, 0, 0) == 60 and local_to_utc(Z(90), 1970, 1, 1, 0, 0) == -90
# southern zone: daylight time crosses New Year
assert local_to_utc(SYD, 2026, 10, 4, 1, 59) == tg(2026, 10, 3, 15, 59)
assert bad(SYD, 2026, 10, 4, 2, 0) and bad(SYD, 2026, 10, 4, 2, 59)
assert local_to_utc(SYD, 2026, 10, 4, 3, 0) == tg(2026, 10, 3, 16, 0)
assert local_to_utc(SYD, 2027, 1, 15, 12, 0) == tg(2027, 1, 15, 1, 0)
assert local_to_utc(SYD, 2026, 1, 15, 12, 0) == tg(2026, 1, 15, 1, 0)
assert local_to_utc(SYD, 2026, 7, 15, 12, 0) == tg(2026, 7, 15, 2, 0)
assert local_to_utc(SYD, 2026, 4, 5, 1, 59) == tg(2026, 4, 4, 14, 59)
assert local_to_utc(SYD, 2026, 4, 5, 2, 0) == tg(2026, 4, 4, 15, 0) and local_to_utc(SYD, 2026, 4, 5, 2, 0, 1) == tg(2026, 4, 4, 16, 0)
assert local_to_utc(SYD, 2026, 4, 5, 2, 59, 1) == tg(2026, 4, 4, 16, 59)
assert local_to_utc(SYD, 2026, 4, 5, 3, 0) == tg(2026, 4, 4, 17, 0) and local_to_utc(SYD, 2026, 4, 5, 3, 0, 1) == tg(2026, 4, 4, 17, 0)
# half-hour save
assert bad(LH, 2026, 10, 4, 2, 0) and bad(LH, 2026, 10, 4, 2, 29) and local_to_utc(LH, 2026, 10, 4, 2, 30) == tg(2026, 10, 3, 15, 30)
assert local_to_utc(LH, 2026, 4, 5, 1, 29) == tg(2026, 4, 4, 14, 29)
assert local_to_utc(LH, 2026, 4, 5, 1, 30) == tg(2026, 4, 4, 14, 30) and local_to_utc(LH, 2026, 4, 5, 1, 30, 1) == tg(2026, 4, 4, 15, 0)
assert local_to_utc(LH, 2026, 4, 5, 2, 0) == tg(2026, 4, 4, 15, 30)
# last weekday, week 4, rule at midnight with the ambiguity crossing midnight
EU = Z(60, 60, (3, -1, 6, 1, 0), (10, -1, 6, 2, 0))   # std CET: start 01:00 UTC... on the standard clock 01:00 = 00:00 UTC? (std +60) -> 2026-03-29 00:00 UTC
assert local_to_utc(EU, 2026, 3, 29, 0, 59) == tg(2026, 3, 28, 23, 59)
assert bad(EU, 2026, 3, 29, 1, 0) and bad(EU, 2026, 3, 29, 1, 59)
assert local_to_utc(EU, 2026, 3, 29, 2, 0) == tg(2026, 3, 29, 0, 0)
assert local_to_utc(EU, 2026, 10, 25, 1, 59) == tg(2026, 10, 24, 23, 59)
assert local_to_utc(EU, 2026, 10, 25, 1, 30, 0) == tg(2026, 10, 24, 23, 30) and local_to_utc(EU, 2026, 10, 25, 1, 30, 1) == tg(2026, 10, 25, 0, 30)
MID = Z(0, 120, (5, 4, 2, 0, 0), (9, 1, 0, 1, 0))     # end 01:00 daylight; ambiguity 23:00 (previous day) to 01:00
assert local_to_utc(MID, 2026, 9, 7, 0, 30, 0) == tg(2026, 9, 6, 22, 30) and local_to_utc(MID, 2026, 9, 7, 0, 30, 1) == tg(2026, 9, 7, 0, 30)
assert local_to_utc(MID, 2026, 9, 6, 23, 0, 0) == tg(2026, 9, 6, 21, 0) and local_to_utc(MID, 2026, 9, 6, 23, 0, 1) == tg(2026, 9, 6, 23, 0)
assert local_to_utc(MID, 2026, 9, 6, 22, 59) == tg(2026, 9, 6, 20, 59)
assert bad(MID, 2026, 5, 27, 0, 0) and bad(MID, 2026, 5, 27, 1, 59) and bad(MID, 2026, 5, 27, 0, 59) and local_to_utc(MID, 2026, 5, 27, 2, 0) == tg(2026, 5, 27, 0, 0) and local_to_utc(MID, 2026, 5, 26, 23, 59) == tg(2026, 5, 26, 23, 59)
# next_transition
t0 = tg(2026, 1, 1, 0, 0)
assert next_transition(US, t0) == (tg(2026, 3, 8, 8, 0), -300)
assert next_transition(US, tg(2026, 3, 8, 8, 0)) == (tg(2026, 11, 1, 7, 0), -360)
assert next_transition(US, tg(2026, 3, 8, 7, 59)) == (tg(2026, 3, 8, 8, 0), -300)
assert next_transition(US, tg(2026, 11, 1, 7, 0)) == (tg(2027, 3, 14, 8, 0), -300)
assert next_transition(SYD, t0) == (tg(2026, 4, 4, 16, 0), 600)
assert next_transition(SYD, tg(2026, 4, 4, 16, 0)) == (tg(2026, 10, 3, 16, 0), 660)
assert next_transition(SYD, tg(2026, 10, 3, 16, 0)) == (tg(2027, 4, 3, 16, 0), 600)
assert next_transition(UTCZ, 5) is None and next_transition(Z(-300), -10**9) is None
assert next_transition(US, tg(1970, 1, 1, 0, 0) - 10**7)[1] in (-300, -360)
assert next_transition(US, -10**12)[1] in (-300, -360) and next_transition(US, 10**12)[1] in (-300, -360)
# validation
for z in [None, [], {}, {"dst": None}, {"std": 0}, {"std": 901, "dst": None}, {"std": -901, "dst": None}, {"std": 1.5, "dst": None}, {"std": "0", "dst": None},
          Z(0, 0, (3, 2, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 181, (3, 2, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 2, 0), (3, 4, 6, 2, 0)),
          Z(0, 60, (13, 2, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (0, 2, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, 5, 6, 2, 0), (11, 1, 6, 2, 0)),
          Z(0, 60, (3, 0, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, -2, 6, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 7, 2, 0), (11, 1, 6, 2, 0)),
          Z(0, 60, (3, 2, -1, 2, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 24, 0), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 2, 60), (11, 1, 6, 2, 0)),
          Z(0, 60, (3, 2, 6, 2, -1), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 2), (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 2, 0, 0), (11, 1, 6, 2, 0)),
          Z(0, 60, None, (11, 1, 6, 2, 0)), Z(0, 60, (3, 2, 6, 2, 0), None), Z(0, 60.0, (3, 2, 6, 2, 0), (11, 1, 6, 2, 0)),
          {"std": 0, "dst": {"start": (3, 2, 6, 2, 0), "end": (11, 1, 6, 2, 0)}}, {"std": 0, "dst": []}, Z(0, 60, (3, 2, 6, 2, "0"), (11, 1, 6, 2, 0)),
          Z(0, 60, (3, 2, 6, 2, 0), (11, 1, 6, 2, 0.5))]:
    assert bad(z, 2026, 6, 1, 12, 0), z
    assert badn(z, 0), z
assert Z(0, 60, [3, 2, 6, 2, 0], [11, 1, 6, 2, 0]) and local_to_utc(Z(0, 60, [3, 2, 6, 2, 0], [11, 1, 6, 2, 0]), 2026, 7, 1, 0, 0) == tg(2026, 6, 30, 23, 0)
assert local_to_utc(dict(US, extra=1), 2026, 7, 1, 0, 0) == tg(2026, 7, 1, 5, 0)
for a in [(1969, 12, 31, 12, 0), (2101, 1, 1, 0, 0), (2026, 2, 29, 0, 0), (2026, 4, 31, 0, 0), (2026, 0, 1, 0, 0), (2026, 13, 1, 0, 0), (2026, 1, 0, 0, 0),
          (2026, 1, 32, 0, 0), (2026, 1, 1, 24, 0), (2026, 1, 1, -1, 0), (2026, 1, 1, 0, 60), (2026, 1, 1, 0, -1), (2026, 1, 1, 0, 0, 2), (2026, 1, 1, 0, 0, -1)]:
    assert bad(US, *a), a
assert local_to_utc(US, 2024, 2, 29, 12, 0) == tg(2024, 2, 29, 18, 0) and bad(US, 2100, 2, 29, 0, 0) and local_to_utc(US, 2100, 12, 31, 23, 59) == tg(2101, 1, 1, 5, 59)

# independent oracle: event list from datetime, offset by bisect
def o_day(y, rule):
    m, wk, wd = rule[0], rule[1], rule[2]
    ds = [dt.date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    ds = [x for x in ds if x.weekday() == wd]
    return ds[wk - 1] if wk > 0 else ds[-1]

def o_events(z):
    std, d = z["std"], z["dst"]
    ev = []
    for y in range(1967, 2104):
        a = o_day(y, d["start"])
        ev.append((tg(a.year, a.month, a.day, d["start"][3], d["start"][4]) - std, std + d["save"]))
        b = o_day(y, d["end"])
        ev.append((tg(b.year, b.month, b.day, d["end"][3], d["end"][4]) - std - d["save"], std))
    ev.sort()
    return ev

def o_offset(z, ev, keys, t):
    i = bisect_right(keys, t) - 1
    return ev[i][1] if i >= 0 else z["std"]

def o_l2u(z, ev, keys, y, mo, d, h, mi, fold):
    L = tg(y, mo, d, h, mi)
    c = []
    for o in sorted({z["std"] + z["dst"]["save"], z["std"]}):
        if o_offset(z, ev, keys, L - o) == o:
            c.append(L - o)
    c.sort()
    if not c:
        return None
    return c[fold] if len(c) == 2 else c[0]

random.seed(4003)
def rzone():
    m1, m2 = random.sample(range(1, 13), 2)
    rule = lambda m: (m, random.choice([1, 2, 3, 4, -1]), random.randint(0, 6), random.choice([0, 1, 2, 3, 12, 23, random.randint(0, 23)]), random.choice([0, 30, 15, random.randint(0, 59)]))
    return Z(random.choice([0, 60, -300, 600, 630, -210, 345, random.randint(-900, 900)]), random.choice([30, 60, 60, 120, 45, random.randint(1, 180)]), rule(m1), rule(m2))

n_gap = n_amb = n_ok = n_tr = 0
def alternates(ev):
    return all(ev[i][1] != ev[i + 1][1] for i in range(len(ev) - 1))

for _ in range(60):
    z = rzone()
    ev = o_events(z)
    while not alternates(ev):
        z = rzone()
        ev = o_events(z)
    keys = [e[0] for e in ev]
    for _ in range(40):
        i = random.randrange(8, len(ev) - 8)
        base = ev[i][0] + z["std"] + random.choice([0, -1, 1, -30, 30, -60, 60, -120, 120, -180, 180, random.randint(-300, 300)])
        d0 = dt.datetime(1970, 1, 1) + dt.timedelta(minutes=base)
        if not 1970 <= d0.year <= 2100:
            continue
        for fold in (0, 1):
            exp = o_l2u(z, ev, keys, d0.year, d0.month, d0.day, d0.hour, d0.minute, fold)
            if exp is None:
                assert bad(z, d0.year, d0.month, d0.day, d0.hour, d0.minute, fold), (z, d0)
                n_gap += 1
            else:
                got = local_to_utc(z, d0.year, d0.month, d0.day, d0.hour, d0.minute, fold)
                assert got == exp, (z, d0, fold, got, exp)
                n_ok += 1
    for _ in range(10):
        t = random.randint(-10**6, 120 * 525949)
        t = random.choice([t, ev[random.randrange(len(ev) - 8)][0] + random.choice([-1, 0, 1])])
        nxt = [e for e in ev if e[0] > t]
        assert next_transition(z, t) == (nxt[0][0], nxt[0][1]), (z, t, next_transition(z, t), nxt[0])
        n_tr += 1
assert n_gap > 100 and n_ok > 1500, (n_gap, n_ok)
''', r'''
def _dfc(y, m, d):
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _dim(y, m):
    if m == 2:
        return 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28
    return 30 if m in (4, 6, 9, 11) else 31


def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check(zone):
    if not isinstance(zone, dict) or "std" not in zone or "dst" not in zone:
        raise ValueError("zone")
    std, dst = zone["std"], zone["dst"]
    if not _isint(std) or not -900 <= std <= 900:
        raise ValueError("std")
    if dst is None:
        return std, None
    if not isinstance(dst, dict) or not _isint(dst.get("save")) or not 1 <= dst["save"] <= 180:
        raise ValueError("dst")
    rules = []
    for k in ("start", "end"):
        r = dst.get(k)
        if not isinstance(r, (list, tuple)) or len(r) != 5 or not all(_isint(x) for x in r):
            raise ValueError("rule")
        m, wk, wd, h, mi = r
        if not (1 <= m <= 12 and wk in (1, 2, 3, 4, -1) and 0 <= wd <= 6 and 0 <= h <= 23 and 0 <= mi <= 59):
            raise ValueError("rule")
        rules.append(tuple(r))
    if rules[0][0] == rules[1][0]:
        raise ValueError("months")
    return std, (dst["save"], rules[0], rules[1])


def _rule_minutes(y, r):
    m, wk, wd, h, mi = r
    if wk > 0:
        dow = (_dfc(y, m, 1) + 3) % 7
        day = 1 + (wd - dow) % 7 + 7 * (wk - 1)
    else:
        last = _dim(y, m)
        dow = (_dfc(y, m, last) + 3) % 7
        day = last - (dow - wd) % 7
    return _dfc(y, m, day) * 1440 + h * 60 + mi


def _year(t):
    z = t // 1440 + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    return yoe + era * 400 + (1 if (5 * doy + 2) // 153 >= 10 else 0)


def _events(std, dst, y0):
    save, s, e = dst
    out = []
    for y in range(y0 - 2, y0 + 3):
        out.append((_rule_minutes(y, s) - std, std + save))
        out.append((_rule_minutes(y, e) - std - save, std))
    out.sort()
    return out


def _offset(std, dst, t):
    best = std
    for when, off in _events(std, dst, _year(t)):
        if when <= t:
            best = off
    return best


def local_to_utc(zone, y, mo, d, h, mi, fold=0):
    std, dst = _check(zone)
    if not (_isint(y) and 1970 <= y <= 2100 and _isint(mo) and 1 <= mo <= 12 and _isint(d) and 1 <= d <= _dim(y, mo)):
        raise ValueError("date")
    if not (_isint(h) and 0 <= h <= 23 and _isint(mi) and 0 <= mi <= 59) or fold not in (0, 1):
        raise ValueError("time")
    local = _dfc(y, mo, d) * 1440 + h * 60 + mi
    if dst is None:
        return local - std
    found = []
    for off in (std + dst[0], std):
        if _offset(std, dst, local - off) == off:
            found.append(local - off)
    if not found:
        raise ValueError("gap")
    return found[fold] if len(found) == 2 else found[0]


def next_transition(zone, t):
    std, dst = _check(zone)
    if dst is None:
        return None
    for when, off in _events(std, dst, _year(t)):
        if when > t:
            return (when, off)
    raise ValueError("range")
''')

task("v4_04_rr_priority", r'''
Write `simulate_rr(jobs, q)` for a single CPU. `jobs` is a list of (arrival, burst, priority)
int triples (arrival >= 0, burst >= 1, priority any int, smaller number = higher priority) and
q >= 1 is the time quantum. It returns, in input order, a list of (start, finish) pairs: the
instant each job first gets the CPU and the instant its burst is complete. Anything invalid
(not a list of int triples, arrival < 0, burst < 1, q < 1, bool values) raises ValueError;
an empty list gives [].
There is one FIFO ready queue per priority. Time is discrete and the CPU is idle when no job is
ready. At every instant t these steps happen in this order:
1. A running job whose remaining burst is 0 finishes at t and leaves the CPU.
2. Jobs whose arrival is t join the back of their priority's queue, in input order.
3. If the running job has used a full quantum q since it was started, it goes to the back of its
   queue and the CPU is free (this also applies when a better job has just arrived). Otherwise,
   if a job with a strictly better priority than the running job is waiting, the running job
   goes to the FRONT of its queue (its remaining burst is kept, its next run gets a fresh
   quantum) and the CPU is free. Equal priority never preempts.
4. If the CPU is free, the first job of the best non-empty priority queue is started with a
   fresh quantum (it keeps the CPU for up to q more time units).
Times go up to 10**12 and q can be 1 while bursts are huge, so simulating one time unit or one
quantum at a time is too slow: the result must be computed quickly (well under a second for up
to 10 jobs).
Example: jobs [(0, 5, 1), (0, 3, 1)], q=2: the first job runs 0-2, the second 2-4, the first
4-6, the second 6-7, the first 7-8, so the result is [(0, 8), (2, 7)].
''', r'''
import random, time

def tick(jobs, q):
    n = len(jobs)
    rem = [b for _, b, _ in jobs]
    qs = {}
    running = None
    used = 0
    start = [None] * n
    fin = [None] * n
    t = 0
    while any(f is None for f in fin):
        if running is not None and rem[running] == 0:
            fin[running] = t
            running = None
        for i in range(n):
            if jobs[i][0] == t:
                qs.setdefault(jobs[i][2], []).append(i)
        if running is not None:
            p = jobs[running][2]
            if used == q:
                qs.setdefault(p, []).append(running)
                running = None
            elif any(l and x < p for x, l in qs.items()):
                qs.setdefault(p, []).insert(0, running)
                running = None
        if running is None:
            ne = [x for x, l in qs.items() if l]
            if ne:
                running = qs[min(ne)].pop(0)
                used = 0
                if start[running] is None:
                    start[running] = t
        if running is not None:
            rem[running] -= 1
            used += 1
        t += 1
    return list(zip(start, fin))

def bad(jobs, q):
    try:
        simulate_rr(jobs, q)
    except ValueError:
        return True
    return False

assert simulate_rr([(0, 5, 1), (0, 3, 1)], 2) == [(0, 8), (2, 7)]
assert simulate_rr([], 3) == []
assert simulate_rr([(0, 5, 1)], 2) == [(0, 5)]
assert simulate_rr([(0, 10, 5), (3, 2, 1)], 100) == [(0, 12), (3, 5)]
assert simulate_rr([(0, 4, 1), (2, 1, 1), (2, 1, 1)], 2) == [(0, 6), (2, 3), (3, 4)]
assert simulate_rr([(0, 4, 2), (2, 1, 1)], 2) == [(0, 5), (2, 3)]
assert simulate_rr([(0, 6, 2), (0, 6, 2), (1, 1, 1)], 4) == [(0, 11), (6, 13), (1, 2)]
assert simulate_rr([(0, 2, 1), (10, 2, 1)], 5) == [(0, 2), (10, 12)]
assert simulate_rr([(5, 3, 0), (5, 3, 0)], 3) == [(5, 8), (8, 11)]
assert simulate_rr([(0, 3, 4), (0, 3, -2)], 1) == [(3, 6), (0, 3)]
assert simulate_rr([(0, 2, 1), (2, 2, 1)], 2) == [(0, 2), (2, 4)]
assert simulate_rr([(0, 10**12, 3)], 7) == [(0, 10**12)]
assert simulate_rr([(0, 10**12, 1), (0, 10**12, 1)], 10**6) == [(0, 2 * 10**12 - 10**6), (10**6, 2 * 10**12)]
for jobs, q in [([(0, 0, 1)], 1), ([(-1, 1, 1)], 1), ([(0, 1, 1)], 0), ([(0, 1, 1)], -3), ([(0, 1)], 1), ([(0, 1, 1, 1)], 1), ([(0.5, 1, 1)], 1),
                ([(0, 1.0, 1)], 1), ([(0, 1, "1")], 1), ([(True, 1, 1)], 1), ([(0, 1, True)], 1), ("abc", 1), (None, 1), ([(0, 1, 1)], 1.5), ([(0, 1, 1)], True), ([None], 1)]:
    assert bad(jobs, q), (jobs, q)
random.seed(4004)
t0 = time.time()
ncase = 0
for it in range(1700):
    n = random.randint(1, 6)
    mx = random.choice([6, 12, 25])
    q = random.randint(1, 6)
    pr = random.choice([1, 2, 3, 5])
    jobs = [(random.choice([0, 0, random.randint(0, mx * 2)]), random.randint(1, mx), random.randint(-1, pr - 2)) for _ in range(n)]
    got = simulate_rr(jobs, q)
    exp = tick(jobs, q)
    assert got == exp, (jobs, q, got, exp)
    ncase += 1
    if it % 8 == 0:
        for c in (1000, 10**6, 10**9 + 7, 123456789012):
            if c * mx * 2 > 10**12 // 2:
                continue
            big = [(a * c, b * c, p) for a, b, p in jobs]
            exp2 = [(s * c, f * c) for s, f in exp]
            assert simulate_rr(big, q * c) == exp2, (jobs, q, c)
            sh = 10**12 + 5
            assert simulate_rr([(a + sh, b, p) for a, b, p in jobs], q) == [(s + sh, f + sh) for s, f in exp], (jobs, q, "shift")
# mid-size, bursts that are not multiples of q
for it in range(120):
    n = random.randint(2, 7)
    q = random.randint(1, 7)
    jobs = [(random.choice([0, random.randint(0, 400)]), random.randint(1, 500), random.randint(0, 2)) for _ in range(n)]
    assert simulate_rr(jobs, q) == tick(jobs, q), (jobs, q)
# huge values: only checked for the quick return and basic invariants
jobs = [(0, 10**12 - 3, 2), (10**11, 10**12 + 7, 2), (5 * 10**11, 123456789, 1), (7, 999999999999, 3), (10**12, 5, 0)]
t1 = time.time()
r = simulate_rr(jobs, 1)
assert time.time() - t1 < 1.0
assert r[4] == (10**12, 10**12 + 5)
assert max(f for s, f in r) == sum(b for _, b, _ in jobs) + 0 or max(f for s, f in r) >= sum(b for _, b, _ in jobs)
assert all(f - s >= b for (s, f), (a, b, p) in zip(r, jobs)) and all(s >= a for (s, f), (a, b, p) in zip(r, jobs))
assert time.time() - t0 < 25
''', r'''
from collections import deque


def simulate_rr(jobs, q):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(jobs, list) or not isint(q) or q < 1:
        raise ValueError("input")
    for j in jobs:
        if not isinstance(j, (tuple, list)) or len(j) != 3 or not all(isint(x) for x in j) or j[0] < 0 or j[1] < 1:
            raise ValueError("job")
    n = len(jobs)
    order = sorted(range(n), key=lambda i: (jobs[i][0], i))
    rem = [j[1] for j in jobs]
    prio = [j[2] for j in jobs]
    start = [None] * n
    fin = [None] * n
    queues = {}
    t = 0
    ai = 0
    running = None
    used = 0
    done = 0

    def arrive():
        nonlocal ai
        while ai < n and jobs[order[ai]][0] <= t:
            i = order[ai]
            queues.setdefault(prio[i], deque()).append(i)
            ai += 1

    while done < n:
        if running is None and ai < n and not any(queues.values()) and jobs[order[ai]][0] > t:
            t = jobs[order[ai]][0]
        if running is not None and rem[running] == 0:
            fin[running] = t
            done += 1
            running = None
        arrive()
        if running is not None:
            p = prio[running]
            if used == q:
                queues.setdefault(p, deque()).append(running)
                running = None
            elif any(d and x < p for x, d in queues.items()):
                queues[p].appendleft(running)
                running = None
        if running is None:
            ready = [x for x, d in queues.items() if d]
            if ready:
                p = min(ready)
                running = queues[p].popleft()
                used = 0
                if start[running] is None:
                    start[running] = t
                grp = [running] + list(queues[p])
                k = len(grp)
                nxt = None
                for x in range(ai, n):
                    if prio[order[x]] <= p:
                        nxt = jobs[order[x]][0]
                        break
                r = (min(rem[i] for i in grp) - 1) // q
                if nxt is not None:
                    r = min(r, (nxt - t - 1) // (k * q))
                if r > 0:
                    for pos, i in enumerate(grp):
                        if start[i] is None:
                            start[i] = t + pos * q
                    t += r * k * q
                    for i in grp:
                        rem[i] -= r * q
                    arrive()
        if done == n:
            break
        if running is not None:
            step = min(rem[running], q - used)
            if ai < n:
                step = min(step, jobs[order[ai]][0] - t)
            t += step
            rem[running] -= step
            used += step
    return list(zip(start, fin))
''')

task("v4_05_hm_infer", r'''
Write `infer(term) -> str` that returns the principal type of a term of a small ML-like
language (Hindley-Milner inference with let-polymorphism), or raises ValueError.
Terms are tuples: ("int", n) with n an int (not a bool); ("bool", b) with b a bool;
("var", name); ("lam", name, body); ("app", f, arg); ("if", c, t, e); ("pair", a, b);
("fst", e); ("snd", e); ("let", name, e1, e2); ("letrec", name, e1, e2). Names are non-empty
str. In "let" the name is not visible in e1; in "letrec" it is visible in e1 with a
monomorphic type, and e2 sees it generalized. A "let" or "letrec" name is generalized over
the type variables of e1's type that do not occur free in the environment (lambda-bound
variables are monomorphic). Inner bindings shadow outer ones.
Types: Int, Bool, functions and pairs. "if" needs a Bool condition and equal branch types;
"pair" has the pair type and "fst"/"snd" project it. The initial environment is closed and
polymorphic: add: Int -> Int -> Int; eq: a -> a -> Bool; not: Bool -> Bool (they can be
shadowed). A ValueError is raised for an unbound variable, a type mismatch, an infinite type
(occurs check) and a malformed term (not a tuple, unknown tag, wrong length, wrong field
types, empty name; a list is not a tuple).
The result string uses type variables named in order of first appearance, reading the printed
type left to right: a, b, ..., z, then a1, b1, ..., z1, a2, ... Function types print as
"t1 -> t2", right associative; a function type on the left of an arrow is parenthesized.
A pair prints as "(t1, t2)" with its two components printed with no extra parentheses.
Examples: infer(("lam", "x", ("var", "x"))) is "a -> a"; the K combinator is
"a -> b -> a"; the S combinator \f.\g.\x. f x (g x) is "(a -> b -> c) -> (a -> b) -> a -> c";
\y. let f = \x. y in (f 1, f True) is "a -> (a, a)" and \f. (f 1, f True) is an error.
''', r'''
import random

def V(x): return ("var", x)
def L(x, b): return ("lam", x, b)
def AP(f, *a):
    for x in a:
        f = ("app", f, x)
    return f
def LET(x, e1, e2): return ("let", x, e1, e2)
def LR(x, e1, e2): return ("letrec", x, e1, e2)
def IF(c, a, b): return ("if", c, a, b)
def PR(a, b): return ("pair", a, b)
def FST(e): return ("fst", e)
def SND(e): return ("snd", e)
def I(n): return ("int", n)
def B(b): return ("bool", b)

def bad(t):
    try:
        infer(t)
    except ValueError:
        return True
    return False

x, y, f, g, p = V("x"), V("y"), V("f"), V("g"), V("p")
ID = L("x", x)
assert infer(ID) == "a -> a"
assert infer(L("x", L("y", x))) == "a -> b -> a"
assert infer(L("f", L("g", L("x", AP(f, x, AP(g, x)))))) == "(a -> b -> c) -> (a -> b) -> a -> c"
assert infer(L("f", L("g", L("x", AP(f, AP(g, x)))))) == "(a -> b) -> (c -> a) -> c -> b"
assert infer(I(3)) == "Int" and infer(I(-7)) == "Int" and infer(B(False)) == "Bool"
assert infer(AP(V("add"), I(1))) == "Int -> Int"
assert infer(V("eq")) == "a -> a -> Bool" and infer(V("not")) == "Bool -> Bool" and infer(V("add")) == "Int -> Int -> Int"
assert infer(LET("id", ID, PR(AP(V("id"), I(1)), AP(V("id"), B(True))))) == "(Int, Bool)"
assert bad(L("f", PR(AP(f, I(1)), AP(f, B(True)))))
assert bad(L("x", AP(x, x)))
assert infer(IF(B(True), I(1), I(2))) == "Int"
assert bad(IF(I(1), I(1), I(2))) and bad(IF(B(True), I(1), B(True)))
assert infer(L("p", FST(p))) == "(a, b) -> a" and infer(L("p", SND(p))) == "(a, b) -> b"
assert infer(L("p", PR(SND(p), FST(p)))) == "(a, b) -> (b, a)"
assert infer(L("y", LET("f", L("x", y), PR(AP(f, I(1)), AP(f, B(True)))))) == "a -> (a, a)"
assert infer(L("x", LET("y", x, y))) == "a -> a"
fact = LR("f", L("n", IF(AP(V("eq"), V("n"), I(0)), I(1), AP(V("add"), V("n"), AP(f, AP(V("add"), V("n"), I(-1)))))), f)
assert infer(fact) == "Int -> Int"
assert infer(LR("f", ID, PR(AP(f, I(1)), AP(f, B(True))))) == "(Int, Bool)"
assert bad(LR("f", L("x", PR(AP(f, I(1)), AP(f, B(True)))), f))
assert infer(LET("add", ID, V("add"))) == "a -> a"
assert infer(L("x", L("x", x))) == "a -> b -> b"
assert bad(LET("z", AP(I(1), I(2)), I(3)))
assert infer(L("f", L("x", AP(f, AP(f, x))))) == "(a -> a) -> a -> a"
assert infer(LR("f", L("x", AP(f, x)), f)) == "a -> b"
assert infer(LET("pair", L("a", L("b", PR(V("a"), V("b")))), AP(V("pair"), I(1), B(True)))) == "(Int, Bool)"
assert infer(LET("pair", L("a", L("b", PR(V("a"), V("b")))), V("pair"))) == "a -> b -> (a, b)"
assert infer(L("x", IF(AP(V("not"), x), x, B(False)))) == "Bool -> Bool"
assert infer(L("f", L("x", IF(AP(V("eq"), AP(f, x), x), B(True), B(False))))) == "(a -> a) -> a -> Bool"
assert infer(L("f", PR(f, f))) == "a -> (a, a)"
assert infer(PR(ID, L("x", L("y", x)))) == "(a -> a, b -> c -> b)"
assert infer(PR(PR(I(1), ID), L("f", f))) == "((Int, a -> a), b -> b)"
assert infer(L("f", L("g", L("x", AP(g, AP(f, x)))))) == "(a -> b) -> (b -> c) -> a -> c"
assert infer(L("f", AP(f, ID))) == "((a -> a) -> b) -> b"
assert infer(L("f", L("x", AP(f, x, x)))) == "(a -> a -> b) -> a -> b"
assert infer(LET("k", L("x", L("y", x)), AP(V("k"), I(1), B(True)))) == "Int"
assert infer(L("x", LET("f", L("y", PR(x, y)), AP(f, I(1))))) == "a -> (a, Int)"
assert infer(L("x", LET("f", L("y", PR(x, y)), PR(AP(f, I(1)), AP(f, B(True)))))) == "a -> ((a, Int), (a, Bool))"
assert infer(LET("f", L("x", x), LET("g", L("y", AP(f, y)), PR(AP(g, I(1)), AP(g, B(True)))))) == "(Int, Bool)"
assert infer(L("f", LET("g", f, PR(AP(g, I(1)), AP(g, I(2)))))) == "(Int -> a) -> (a, a)"
assert bad(L("f", LET("g", f, PR(AP(g, I(1)), AP(g, B(True))))))
assert infer(LR("even", L("n", IF(AP(V("eq"), V("n"), I(0)), B(True), AP(V("even"), AP(V("add"), V("n"), I(-1))))), V("even"))) == "Int -> Bool"
assert bad(LR("f", AP(f, f), f)) and infer(LR("x", x, I(1))) == "Int" and bad(LR("x", AP(V("add"), x), x))
names = [chr(97 + i % 26) + (str(i // 26) if i >= 26 else "") for i in range(30)]
big = V("v0")
for i in range(29, -1, -1):
    big = L("v%d" % i, big)
assert infer(big) == " -> ".join(names + ["a"])
assert infer(L("a", L("b", L("c", PR(V("c"), PR(V("a"), V("b"))))))) == "a -> b -> c -> (c, (a, b))"
# errors
for t in [V("zzz"), V("x"), ("int", True), ("bool", 1), ("bool", None), ("int", 1.5), ("int", "1"), ("var", 3), ("var", ""), ("lam", "x"), ("lam", "", ID), ("lam", 1, x),
          ("zzz", 1), ("app", 1, 2), ("app", I(1)), ("app", I(1), I(2), I(3)), [], None, "x", 5, ("let", "x", I(1)), ("let", "x", I(1), I(2), I(3)), ["lam", "x", x],
          ("if", B(True), I(1)), ("pair", I(1)), ("fst",), ("fst", I(1)), ("snd", I(1), I(2)), ("letrec", "f", ID), ("let", "", I(1), I(2)), ("lam", "x", None),
          AP(V("add"), B(True)), AP(V("add"), I(1), I(2), I(3)), AP(V("not"), I(1)), AP(V("eq"), I(1), B(True)), AP(I(1), I(2)), FST(I(1)), IF(B(True), L("x", x), I(1))]:
    assert bad(t), t
assert bad(AP(V("eq"), ID, ID)) is False and infer(AP(V("eq"), ID, ID)) == "Bool"
assert infer(AP(V("eq"), I(1), I(2))) == "Bool"
assert infer(AP(V("eq"), ID)) == "(a -> a) -> Bool"

# oracle: algorithm W with explicit substitutions
cnt = [0]
def fresh():
    cnt[0] += 1
    return ("v", cnt[0])

def ap(s, t):
    if t[0] == "v":
        return ap(s, s[t[1]]) if t[1] in s else t
    if t[0] in ("Int", "Bool"):
        return t
    return (t[0], ap(s, t[1]), ap(s, t[2]))

def ftv(t, acc=None):
    acc = set() if acc is None else acc
    if t[0] == "v":
        acc.add(t[1])
    elif t[0] in ("fn", "pr"):
        ftv(t[1], acc)
        ftv(t[2], acc)
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
    if a[0] != b[0] or a[0] in ("Int", "Bool"):
        raise ValueError("mismatch")
    s = uni(a[1], b[1], s)
    return uni(a[2], b[2], s)

def inst(sc):
    vs, t = sc
    m = {v: fresh() for v in vs}
    return ap(m, t)

PRIM = {"add": ((), ("fn", ("Int",), ("fn", ("Int",), ("Int",)))), "not": ((), ("fn", ("Bool",), ("Bool",)))}
_e = ("v", -1)
PRIM["eq"] = ((-1,), ("fn", _e, ("fn", _e, ("Bool",))))

def W(env, e, s):
    if not isinstance(e, tuple) or not e:
        raise ValueError("term")
    k = e[0]
    n = {"int": 2, "bool": 2, "var": 2, "lam": 3, "app": 3, "if": 4, "pair": 3, "fst": 2, "snd": 2, "let": 4, "letrec": 4}.get(k)
    if n is None or len(e) != n:
        raise ValueError("term")
    if k == "int":
        if type(e[1]) is not int:
            raise ValueError("term")
        return ("Int",), s
    if k == "bool":
        if type(e[1]) is not bool:
            raise ValueError("term")
        return ("Bool",), s
    if k in ("var", "lam", "let", "letrec") and (not isinstance(e[1], str) or not e[1]):
        raise ValueError("term")
    if k == "var":
        if e[1] not in env:
            raise ValueError("unbound")
        return inst(env[e[1]]), s
    if k == "lam":
        a = fresh()
        t, s = W({**env, e[1]: ((), a)}, e[2], s)
        return ("fn", a, t), s
    if k == "app":
        tf, s = W(env, e[1], s)
        ta, s = W(env, e[2], s)
        r = fresh()
        s = uni(tf, ("fn", ta, r), s)
        return ap(s, r), s
    if k == "if":
        tc, s = W(env, e[1], s)
        s = uni(tc, ("Bool",), s)
        t1, s = W(env, e[2], s)
        t2, s = W(env, e[3], s)
        s = uni(t1, t2, s)
        return ap(s, t1), s
    if k == "pair":
        t1, s = W(env, e[1], s)
        t2, s = W(env, e[2], s)
        return ("pr", t1, t2), s
    if k in ("fst", "snd"):
        t, s = W(env, e[1], s)
        a, b = fresh(), fresh()
        s = uni(t, ("pr", a, b), s)
        return ap(s, a if k == "fst" else b), s
    def gen(env, t, s):
        t = ap(s, t)
        envv = set()
        for sc in env.values():
            envv |= ftv(ap(s, sc[1])) - set(sc[0])
        return tuple(sorted(ftv(t) - envv)), t
    if k == "let":
        t1, s = W(env, e[2], s)
        sc = gen(env, t1, s)
        return W({**env, e[1]: sc}, e[3], s)
    a = fresh()
    t1, s = W({**env, e[1]: ((), a)}, e[2], s)
    s = uni(a, t1, s)
    sc = gen(env, t1, s)
    return W({**env, e[1]: sc}, e[3], s)

def show(t):
    order = []
    def collect(t):
        if t[0] == "v":
            if t[1] not in order:
                order.append(t[1])
        elif t[0] in ("fn", "pr"):
            collect(t[1])
            collect(t[2])
    collect(t)
    nm = {v: chr(97 + i % 26) + (str(i // 26) if i >= 26 else "") for i, v in enumerate(order)}
    def go(t, left):
        if t[0] == "v":
            return nm[t[1]]
        if t[0] in ("Int", "Bool"):
            return t[0]
        if t[0] == "pr":
            return "(" + go(t[1], False) + ", " + go(t[2], False) + ")"
        s = go(t[1], True) + " -> " + go(t[2], False)
        return "(" + s + ")" if left else s
    return go(t, False)

def oracle(e):
    t, s = W(PRIM, e, {})
    return show(ap(s, t))

random.seed(4005)
VARS = ["x", "y", "f", "g", "add", "eq", "not", "id"]
def gen(d, scope):
    r = random.random()
    if d == 0 or r < 0.15:
        c = random.random()
        if c < 0.5 and scope:
            return V(random.choice(scope))
        if c < 0.65:
            return V(random.choice(["add", "eq", "not"]))
        return random.choice([I(random.randint(-2, 2)), B(random.random() < 0.5)])
    if r < 0.35:
        n = random.choice(["x", "y", "f", "g"])
        return L(n, gen(d - 1, scope + [n]))
    if r < 0.6:
        return AP(gen(d - 1, scope), gen(d - 1, scope))
    if r < 0.7:
        return LET(random.choice(["x", "y", "f", "id"]), gen(d - 1, scope), None)
    if r < 0.78:
        return IF(gen(d - 1, scope), gen(d - 1, scope), gen(d - 1, scope))
    if r < 0.86:
        return PR(gen(d - 1, scope), gen(d - 1, scope))
    if r < 0.92:
        return random.choice([FST, SND])(gen(d - 1, scope))
    return LR(random.choice(["f", "g", "x"]), gen(d - 1, scope), None)

def fill(d, scope):
    t = gen(d, scope)
    return fix(t, scope)

def fix(t, scope):
    if t[0] in ("let", "letrec") and t[3] is None:
        n = t[1]
        e1 = fix(t[2], scope + ([n] if t[0] == "letrec" else []))
        return (t[0], n, e1, fix(gen(random.randint(0, 3), scope + [n]), scope + [n]))
    if t[0] == "lam":
        return ("lam", t[1], fix(t[2], scope + [t[1]]))
    if t[0] in ("app", "pair", "if"):
        return (t[0],) + tuple(fix(c, scope) for c in t[1:])
    if t[0] in ("fst", "snd"):
        return (t[0], fix(t[1], scope))
    return t

nok = nerr = 0
for _ in range(5000):
    t = fill(random.randint(1, 7), [])
    try:
        exp = oracle(t)
    except ValueError:
        exp = None
    try:
        got = infer(t)
    except ValueError:
        got = None
    assert got == exp, (t, got, exp)
    if exp is None:
        nerr += 1
    else:
        nok += 1
assert nok > 1000 and nerr > 600, (nok, nerr)
# exponentially large types stay fast
chain = V("p10")
for i in range(10, 0, -1):
    chain = LET("p%d" % i, L("x", PR(AP(V("p%d" % (i - 1)), x), AP(V("p%d" % (i - 1)), x))), chain)
chain = LET("p0", L("x", PR(x, x)), chain)
assert infer(chain) == oracle(chain)
deep = I(0)
for i in range(120):
    deep = LET("v%d" % i, L("z", V("z")), PR(deep, AP(V("v%d" % i), I(i))))
assert infer(deep) == oracle(deep)
''', r'''
class _TV:
    __slots__ = ("link", "level")

    def __init__(self, level):
        self.link = None
        self.level = level


_GEN = 10 ** 9
_INT = ("Int",)
_BOOL = ("Bool",)


def _prune(t):
    while isinstance(t, _TV) and t.link is not None:
        t = t.link
    return t


def _bind(v, t):
    t = _prune(t)
    if isinstance(t, _TV):
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
    if isinstance(a, _TV):
        _bind(a, b)
        a.link = b
    elif isinstance(b, _TV):
        _bind(b, a)
        b.link = a
    elif a[0] != b[0]:
        raise ValueError("mismatch")
    else:
        for x, y in zip(a[1:], b[1:]):
            _unify(x, y)


def _generalize(t, level):
    t = _prune(t)
    if isinstance(t, _TV):
        if t.level > level:
            t.level = _GEN
    else:
        for c in t[1:]:
            _generalize(c, level)


def _instantiate(t, level, memo):
    t = _prune(t)
    if isinstance(t, _TV):
        if t.level == _GEN:
            if t not in memo:
                memo[t] = _TV(level)
            return memo[t]
        return t
    if len(t) == 1:
        return t
    return (t[0],) + tuple(_instantiate(c, level, memo) for c in t[1:])


def _name(i):
    return chr(97 + i % 26) + (str(i // 26) if i >= 26 else "")


def _show(t, names, left=False):
    t = _prune(t)
    if isinstance(t, _TV):
        if t not in names:
            names[t] = _name(len(names))
        return names[t]
    if t[0] in ("Int", "Bool"):
        return t[0]
    if t[0] == "pair":
        a = _show(t[1], names)
        return "(" + a + ", " + _show(t[2], names) + ")"
    a = _show(t[1], names, True)
    s = a + " -> " + _show(t[2], names)
    return "(" + s + ")" if left else s


_ARITY = {"int": 2, "bool": 2, "var": 2, "lam": 3, "app": 3, "if": 4, "pair": 3, "fst": 2, "snd": 2, "let": 4, "letrec": 4}


def _infer(env, e, level):
    if not isinstance(e, tuple) or not e or e[0] not in _ARITY or len(e) != _ARITY[e[0]]:
        raise ValueError("term")
    k = e[0]
    if k == "int":
        if type(e[1]) is not int:
            raise ValueError("term")
        return _INT
    if k == "bool":
        if type(e[1]) is not bool:
            raise ValueError("term")
        return _BOOL
    if k in ("var", "lam", "let", "letrec") and (not isinstance(e[1], str) or e[1] == ""):
        raise ValueError("term")
    if k == "var":
        if e[1] not in env:
            raise ValueError("unbound")
        return _instantiate(env[e[1]], level, {})
    if k == "lam":
        a = _TV(level)
        return ("fn", a, _infer({**env, e[1]: a}, e[2], level))
    if k == "app":
        tf = _infer(env, e[1], level)
        ta = _infer(env, e[2], level)
        r = _TV(level)
        _unify(tf, ("fn", ta, r))
        return r
    if k == "if":
        _unify(_infer(env, e[1], level), _BOOL)
        t1 = _infer(env, e[2], level)
        _unify(t1, _infer(env, e[3], level))
        return t1
    if k == "pair":
        return ("pair", _infer(env, e[1], level), _infer(env, e[2], level))
    if k in ("fst", "snd"):
        a, b = _TV(level), _TV(level)
        _unify(_infer(env, e[1], level), ("pair", a, b))
        return a if k == "fst" else b
    if k == "let":
        t1 = _infer(env, e[2], level + 1)
    else:
        a = _TV(level + 1)
        t1 = _infer({**env, e[1]: a}, e[2], level + 1)
        _unify(a, t1)
    _generalize(t1, level)
    return _infer({**env, e[1]: t1}, e[3], level)


def infer(term):
    a = _TV(_GEN)
    env = {"add": ("fn", _INT, ("fn", _INT, _INT)), "not": ("fn", _BOOL, _BOOL),
           "eq": ("fn", a, ("fn", a, _BOOL))}
    return _show(_infer(env, term, 0), {})
''')

task("v4_06_phi_blocks", r'''
Write `phi_blocks(n, edges, entry, defs)` for SSA construction. The control-flow graph has nodes
0..n-1 and directed edges (u, v) (duplicate edges and self-loops are allowed). Only nodes
reachable from `entry` exist: ignore every other node and every edge that starts at one (a
definition in an unreachable node counts for nothing).
Node d dominates v if every path from `entry` to v contains d (so every node dominates itself);
d strictly dominates v if it dominates v and d != v. The dominance frontier DF(x) is the set of
reachable nodes y for which there is an edge p -> y with p reachable, x dominates p, and x does
not strictly dominate y (so x can be in DF(x), and `entry` is in DF(entry) when an edge leads
back to it). For a set S, DF(S) is the union of DF(x) over x in S. `defs` maps each variable
(any hashable) to an iterable of the nodes that assign it. For a variable with definition
nodes S, let P be the smallest set with P = DF(S' union P), where S' is S without the
unreachable nodes. A phi function is needed in exactly the nodes of P (`entry` gets no implicit
definition, and a variable that is not live still gets its phis).
Return a dict with one key per variable of `defs`, whose value is the sorted list of the nodes
of P. A variable with no (reachable) definition gets [].
ValueError: n must be an int >= 1 (bool is not an int); entry must be an int in 0..n-1; edges
must be a list of pairs of ints in 0..n-1; defs must be a dict, each value an iterable of ints
in 0..n-1. These checks apply to the whole input, including its unreachable parts.
Efficiency: n up to 30,000, up to 100,000 edges and a few dozen variables with thousands of
definitions each, so quadratic dominator or frontier computations are too slow.
Example: n=4, edges [(0,1),(0,2),(1,3),(2,3)], entry 0, defs {"x": [1]} gives {"x": [3]}.
''', r'''
import random, time

def bad(*a):
    try:
        phi_blocks(*a)
    except ValueError:
        return True
    return False

D = [(0, 1), (0, 2), (1, 3), (2, 3)]
assert phi_blocks(4, D, 0, {"x": [1]}) == {"x": [3]}
assert phi_blocks(4, D, 0, {"x": [1, 2], "y": [0], "z": [3], "w": []}) == {"x": [3], "y": [], "z": [], "w": []}
assert phi_blocks(4, D, 0, {}) == {}
# loops: header 1, body 2, exit 3
L = [(0, 1), (1, 2), (2, 1), (1, 3)]
assert phi_blocks(4, L, 0, {"i": [0, 2]}) == {"i": [1]}
assert phi_blocks(4, L, 0, {"i": [1]}) == {"i": [1]}
assert phi_blocks(4, L, 0, {"i": [3]}) == {"i": []}
# entry with a back edge is in its own frontier
assert phi_blocks(3, [(0, 1), (1, 2), (2, 0)], 0, {"a": [0]}) == {"a": [0]}
assert phi_blocks(3, [(0, 1), (1, 2), (2, 0)], 0, {"a": [2]}) == {"a": [0]}
assert phi_blocks(3, [(0, 1), (1, 2), (2, 0)], 1, {"a": [2]}) == {"a": [1]}
assert phi_blocks(1, [(0, 0)], 0, {"a": [0]}) == {"a": [0]}
assert phi_blocks(1, [], 0, {"a": [0]}) == {"a": []}
# unreachable nodes and edges
assert phi_blocks(5, D + [(4, 3), (4, 4)], 0, {"x": [4], "y": [1]}) == {"x": [], "y": [3]}
assert phi_blocks(4, D, 1, {"x": [3]}) == {"x": []}
assert phi_blocks(4, [(1, 3), (2, 3), (0, 1), (3, 3)], 0, {"x": [1], "y": [3]}) == {"x": [], "y": [3]}
assert phi_blocks(4, D + D + [(0, 1)], 0, {"x": [2]}) == {"x": [3]}
# iterated: phi at 3 is itself a definition that needs a phi at 5
G = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (0, 4)]
assert phi_blocks(5, G, 0, {"x": [1]}) == {"x": [3, 4]}
assert phi_blocks(5, G, 0, {"x": [3]}) == {"x": [4]}
assert phi_blocks(5, G, 0, {"x": (2,), "y": {1, 2}, "z": iter([0, 3])}) == {"x": [3, 4], "y": [3, 4], "z": [4]}
for a in [(0, [], 0, {}), (-1, [], 0, {}), (True, [], 0, {}), (2.0, [], 0, {}), ("2", [], 0, {}), (2, [(0, 1)], 2, {}), (2, [(0, 1)], -1, {}), (2, [(0, 1)], True, {}), (2, [(0, 1)], None, {}),
          (2, [(0, 2)], 0, {}), (2, [(0, -1)], 0, {}), (2, [(0, 1, 1)], 0, {}), (2, [(0,)], 0, {}), (2, [(0, True)], 0, {}), (2, [(0, 1.0)], 0, {}), (2, [[0, "1"]], 0, {}),
          (2, ((0, 1),), 0, {}), (2, None, 0, {}), (2, [(0, 1)], 0, [("x", [0])]), (2, [(0, 1)], 0, {"x": [2]}), (2, [(0, 1)], 0, {"x": [-1]}), (2, [(0, 1)], 0, {"x": [True]}),
          (2, [(0, 1)], 0, {"x": 1}), (2, [(0, 1)], 0, {"x": [0.0]}), (3, [(0, 1), (2, 5)], 0, {}), (3, [(0, 1)], 0, {"x": [2, 3]}), (3, [(0, 1), (2, 2)], 0, {"x": ["a"]})]:
    assert bad(*a), a
assert phi_blocks(3, [(0, 1), (2, 2)], 0, {(1, 2): [2], None: [1]}) == {(1, 2): [], None: []}
# brute-force oracle
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

def oracle(n, edges, entry, defs):
    R = reach(n, edges, entry)
    dom = {v: set() for v in R}
    for d in R:
        r = reach(n, edges, entry, d)
        for v in R:
            if v == d or v not in r:
                dom[v].add(d)
    def df(x):
        out = set()
        for p, y in edges:
            if p in R and x in dom[p] and not (x in dom[y] and x != y):
                out.add(y)
        return out
    res = {}
    for var, ds in defs.items():
        S = {d for d in ds if d in R}
        P = set()
        while True:
            new = set()
            for x in S | P:
                new |= df(x)
            if new <= P:
                break
            P |= new
        res[var] = sorted(P)
    return res

random.seed(4006)
nonempty = 0
for it in range(2500):
    n = random.randint(1, 11)
    m = random.randint(0, 2 * n + 2)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    if random.random() < 0.6:
        edges += [(i, i + 1) for i in range(n - 1) if random.random() < 0.8]
    entry = random.randrange(n) if random.random() < 0.3 else 0
    defs = {v: random.sample(range(n), random.randint(0, min(n, 4))) for v in "abc"}
    got = phi_blocks(n, edges, entry, defs)
    exp = oracle(n, edges, entry, defs)
    assert got == exp, (n, edges, entry, defs, got, exp)
    nonempty += sum(1 for v in exp.values() if v)
assert nonempty > 1500, nonempty
# large: a chain of diamonds closed by a back edge
K = 8000
edges = []
for i in range(K):
    a, b, c = 3 * i, 3 * i + 1, 3 * i + 2
    nxt = 3 * (i + 1)
    edges += [(a, b), (a, c), (b, nxt), (c, nxt)]
n = 3 * K + 1
edges.append((3 * K, 0))
defs = {}
exp = {}
for v in range(30):
    S = random.sample(range(K), 800)
    defs["v%d" % v] = [random.choice([3 * i + 1, 3 * i + 2]) for i in S]
    exp["v%d" % v] = sorted({0} | {3 * (i + 1) for i in S})
random.shuffle(edges)
t0 = time.time()
got = phi_blocks(n, edges, 0, defs)
assert time.time() - t0 < 4.0, time.time() - t0
assert got == exp
# a long chain with unreachable noise
n = 30000
edges = [(i, i + 1) for i in range(n - 2)] + [(n - 1, 5), (n - 1, n - 1)]
t0 = time.time()
got = phi_blocks(n, edges, 0, {"x": [1, 7, n - 1], "y": [n - 2]})
assert time.time() - t0 < 3.0
assert got == {"x": [], "y": []}
''', r'''
def phi_blocks(n, edges, entry, defs):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or n < 1 or not isint(entry) or not 0 <= entry < n or not isinstance(edges, list) or not isinstance(defs, dict):
        raise ValueError("input")
    succ = [[] for _ in range(n)]
    for e in edges:
        if not isinstance(e, (tuple, list)) or len(e) != 2 or not all(isint(x) and 0 <= x < n for x in e):
            raise ValueError("edge")
        succ[e[0]].append(e[1])
    dl = {}
    for var, ds in defs.items():
        try:
            items = list(ds)
        except TypeError:
            raise ValueError("defs")
        if not all(isint(x) and 0 <= x < n for x in items):
            raise ValueError("def")
        dl[var] = items
    order = []
    seen = [False] * n
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

    def intersect(a, b):
        while a != b:
            while num[a] > num[b]:
                a = idom[a]
            while num[b] > num[a]:
                b = idom[b]
        return a

    changed = True
    while changed:
        changed = False
        for b in rpo:
            if b == entry:
                continue
            new = None
            for p in preds[b]:
                if p in idom:
                    new = p if new is None else intersect(new, p)
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
                if r is None:
                    break
    out = {}
    for var, items in dl.items():
        has = set()
        queued = set()
        work = []
        for d in items:
            if seen[d] and d not in queued:
                queued.add(d)
                work.append(d)
        while work:
            x = work.pop()
            for y in df[x]:
                if y not in has:
                    has.add(y)
                    if y not in queued:
                        queued.add(y)
                        work.append(y)
        out[var] = sorted(has)
    return out
''')

task("v4_07_sub_game", r'''
Write `sub_game(S, piles)` that solves a sum of subtraction games. In one move a player picks
one pile with n stones and a number s from the set S with s <= n, and removes s stones from
that pile. Several piles are played together; players alternate; normal play: a player who
cannot move loses. S is a list, tuple, set or frozenset of distinct ints in 1..40 (not
empty); piles is a list of ints in 0..10**18 (at most 50 of them, possibly none). Anything
else (wrong container type, bool or float or str items, values out of range, repeated items
in a list or tuple, empty S) is a ValueError.
Return a dict with three keys:
- "grundy": the list of Grundy values of the piles, in order. The Grundy value of a pile of n
  stones is the mex (smallest non-negative int not present) of the Grundy values of the piles
  reachable from it by one move; for n = 0 it is 0.
- "winner": "first" if the player to move wins the whole game with best play, else "second".
- "moves": the list of ALL winning first moves as (pile_index, s) tuples, sorted ascending
  (by index, then by s). A move is winning when the position after it is lost for the player
  who has to move next. It is [] when the winner is "second". Note that the Grundy value of
  the pile after a winning move can be smaller than, equal to, or larger than the value
  before it.
Piles go up to 10**18, so the Grundy values cannot be computed one stone at a time: the
sequence of Grundy values of a subtraction game is eventually periodic (each value depends
only on the previous max(S) values), and the answer must come in well under a second for any
valid input.
Examples: sub_game([1], [3]) is {"grundy": [1], "winner": "first", "moves": [(0, 1)]};
sub_game({1, 2}, [4, 5]) is {"grundy": [1, 2], "winner": "first", "moves": [(0, 2), (1, 1)]};
sub_game((1, 2), []) is {"grundy": [], "winner": "second", "moves": []}.
''', r'''
import random, time
from functools import lru_cache

def bad(S, piles):
    try:
        sub_game(S, piles)
    except ValueError:
        return True
    return False

assert sub_game([1], [3]) == {"grundy": [1], "winner": "first", "moves": [(0, 1)]}
assert sub_game({1, 2}, [4, 5]) == {"grundy": [1, 2], "winner": "first", "moves": [(0, 2), (1, 1)]}
assert sub_game((1, 2), []) == {"grundy": [], "winner": "second", "moves": []}
assert sub_game([3], [0, 0]) == {"grundy": [0, 0], "winner": "second", "moves": []}
assert sub_game([2, 3], [1]) == {"grundy": [0], "winner": "second", "moves": []}
assert sub_game(frozenset({5}), [7, 7]) == {"grundy": [1, 1], "winner": "second", "moves": []}
assert sub_game([1], [10**18]) == {"grundy": [0], "winner": "second", "moves": []}
assert sub_game([1], [10**18 - 1]) == {"grundy": [1], "winner": "first", "moves": [(0, 1)]}
r = sub_game(list(range(1, 41)), [10**18, 10**18 - 1, 41, 40, 5])
assert r["grundy"] == [10**18 % 41, (10**18 - 1) % 41, 0, 40, 5], r
for S, pl in [([1], [1, 2, 3]), ({1, 2, 3}, [10, 11]), ([40], [10**18]), ([1, 40], [0, 1, 39, 40, 41])]:
    assert sub_game(S, pl)["winner"] in ("first", "second")
for S, pl in [([], [1]), ([0], [1]), ([41], [1]), ([-1], [1]), ([1, 1], [1]), ((2, 2), [1]), ([True], [1]), ([1.0], [1]), (["1"], [1]), ("12", [1]), (None, [1]), (5, [1]),
              ({1: 2}, [1]), ([1], (1, 2)), ([1], None), ([1], [-1]), ([1], [10**18 + 1]), ([1], [True]), ([1], [1.5]), ([1], ["1"]), ([1], [None]), ([1], 5), ([1], {1}), ([[1]], [1]),
              ([1], [1] * 51), ([1, 2], [3, [4]])]:
    assert bad(S, pl), (S, pl)
assert not bad([1], [0] * 50) and not bad({40, 1}, [10**18] * 3)

# oracles
def dp_seq(S, L):
    S = sorted(S)
    g = []
    for n in range(L):
        seen = {g[n - s] for s in S if s <= n}
        m = 0
        while m in seen:
            m += 1
        g.append(m)
    return g

def moves_from(S, piles, G):
    gs = [G(n) for n in piles]
    X = 0
    for v in gs:
        X ^= v
    mv = []
    if X:
        for i, n in enumerate(piles):
            for s in sorted(S):
                if s <= n and G(n - s) == gs[i] ^ X:
                    mv.append((i, s))
    return {"grundy": gs, "winner": "first" if X else "second", "moves": mv}

def minimax_oracle(S, piles):
    Ss = sorted(S)
    @lru_cache(maxsize=None)
    def win(state):
        for i, n in enumerate(state):
            for s in Ss:
                if s <= n:
                    nxt = list(state)
                    nxt[i] -= s
                    if not win(tuple(sorted(nxt))):
                        return True
        return False
    mv = []
    for i, n in enumerate(piles):
        for s in Ss:
            if s <= n:
                nxt = list(piles)
                nxt[i] -= s
                if not win(tuple(sorted(nxt))):
                    mv.append((i, s))
    return {"winner": "first" if win(tuple(sorted(piles))) else "second", "moves": mv}

random.seed(4007)
bigger = 0
for _ in range(700):
    S = random.sample(range(1, 9), random.randint(1, 4))
    piles = [random.randint(0, 9) for _ in range(random.randint(1, 4))]
    got = sub_game(S, piles)
    mm = minimax_oracle(S, piles)
    assert got["winner"] == mm["winner"] and got["moves"] == mm["moves"], (S, piles, got, mm)
    seq = dp_seq(S, 12)
    assert got["grundy"] == [seq[n] for n in piles], (S, piles, got)
    for (i, s) in got["moves"]:
        if seq[piles[i] - s] > seq[piles[i]]:
            bigger += 1
assert bigger >= 8, bigger

# direct Grundy DP up to 3000
pool = [random.sample(range(1, 41), random.randint(1, 9)) for _ in range(10)] + [[11, 27, 38], [3, 5, 33, 37, 38], [40, 39, 1], [2, 5, 13, 16, 18, 21, 26, 28]]
cache = {}
def seq_of(S, L):
    k = (tuple(sorted(S)), L)
    if k not in cache:
        cache[k] = dp_seq(S, L)
    return cache[k]
nmv = 0
for _ in range(120):
    S = random.choice(pool)
    sq = seq_of(S, 3001)
    piles = [random.choice([random.randint(0, 3000), random.randint(0, 60)]) for _ in range(random.randint(1, 6))]
    got = sub_game(random.choice([S, tuple(S), set(S)]), piles)
    exp = moves_from(S, piles, lambda n: sq[n])
    assert got == exp, (S, piles, got, exp)
    nmv += len(exp["moves"])
assert nmv > 100, nmv

# huge piles: period found by brute force on an independent 6000-term sequence
def find_period(g):
    L = len(g)
    for p in range(1, L // 3):
        if all(g[k] == g[k + p] for k in range(L // 2, L - p)):
            t = L // 2
            while t > 0 and g[t - 1] == g[t - 1 + p]:
                t -= 1
            return t, p
    return None

t0 = time.time()
total = 0
for S in [[11, 27, 38], [3, 5, 33, 37, 38], [2, 5, 13, 16, 18, 21, 26, 28], [7, 15, 16, 22, 30, 37, 38], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], [40], [9, 14], pool[0], pool[1], pool[2]]:
    g = dp_seq(S, 6000)
    tp = find_period(g)
    assert tp is not None
    t, p = tp
    G = lambda n, g=g, t=t, p=p: g[n] if n < 6000 else g[t + (n - t) % p]
    for _ in range(12):
        piles = [random.choice([random.randint(0, 10**18), 10**18 - random.randint(0, 100), random.randint(5000, 7000), random.randint(0, 10**9)]) for _ in range(random.randint(1, 5))]
        got = sub_game(S, piles)
        exp = moves_from(S, piles, G)
        assert got == exp, (S, piles, got, exp)
        total += len(exp["moves"])
assert total > 20, total
assert time.time() - t0 < 6.0
t1 = time.time()
for _ in range(30):
    sub_game(random.sample(range(1, 41), 8), [10**18, 10**18 - 1, 123456789012345678])
assert time.time() - t1 < 1.5
''', r'''
def sub_game(S, piles):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(S, (list, tuple, set, frozenset)) or not S:
        raise ValueError("S")
    items = list(S)
    if not all(isint(s) and 1 <= s <= 40 for s in items) or len(set(items)) != len(items):
        raise ValueError("S")
    if not isinstance(piles, list) or len(piles) > 50 or not all(isint(p) and 0 <= p <= 10 ** 18 for p in piles):
        raise ValueError("piles")
    ss = sorted(items)
    m = ss[-1]
    top = max(piles) if piles else 0
    g = []
    seen = {}
    start = per = None
    n = 0
    while n <= top:
        used = {g[n - s] for s in ss if s <= n}
        v = 0
        while v in used:
            v += 1
        g.append(v)
        if n >= m - 1:
            key = tuple(g[n - m + 1:n + 1])
            if key in seen:
                start = seen[key] - m + 1
                per = n - seen[key]
                break
            seen[key] = n
        n += 1

    def grundy(x):
        if x < len(g):
            return g[x]
        return g[start + (x - start) % per]

    gs = [grundy(p) for p in piles]
    total = 0
    for v in gs:
        total ^= v
    moves = []
    if total:
        for i, p in enumerate(piles):
            want = gs[i] ^ total
            for s in ss:
                if s <= p and grundy(p - s) == want:
                    moves.append((i, s))
    return {"grundy": gs, "winner": "first" if total else "second", "moves": moves}
''')

task("v4_08_lattice_poly", r'''
Write `lattice_count(poly)` that returns a tuple (interior, boundary, twice_area) for a simple
polygon whose vertices are lattice points. `poly` is a list or tuple of 3..2000 vertices, each
a list or tuple of two ints (bool is not an int) with absolute value at most 10**9; anything
else, checked on the raw input before any merging, is a ValueError. The polygon may be given
clockwise or counter-clockwise, starting at any vertex.
Merging: every run of equal consecutive vertices is replaced by one vertex, also around the
end (a last vertex equal to the first is dropped). If fewer than 3 vertices remain it is a
ValueError. The m remaining vertices v0..v(m-1) define the closed boundary of m edges
v(i) -> v(i+1), the last one going back to v0. A vertex where the boundary continues straight
(a 180 degree turn) is allowed and stays a vertex.
The polygon must be simple, otherwise ValueError. Two edges are neighbours if they are
consecutive around the boundary (for m == 3 all three pairs are neighbours). Edges are closed
segments. Two edges that are not neighbours must have no point in common at all, not even an
endpoint touching another edge. Two neighbouring edges must have only their shared vertex in
common: a turn straight back onto the previous edge (0 degrees, a spike) is not allowed. A
polygon with zero area is a ValueError too.
interior is the number of lattice points strictly inside, boundary the number of lattice points
on the boundary, and twice_area twice the area (a positive int). Coordinates are huge, so the
counts must be computed exactly from the vertices, not by enumeration. Segment tests must be
exact (integer arithmetic). n can be 2000; an O(n^2) pairwise edge test is acceptable.
Example: [(0, 0), (4, 0), (0, 4)] gives (3, 12, 16).
''', r'''
import random
from fractions import Fraction as F

def bad(p):
    try:
        lattice_count(p)
    except ValueError:
        return True
    return False

def eq(p, exp):
    got = lattice_count(p)
    assert isinstance(got, tuple) and got == exp and all(type(x) is int for x in got), (p, got, exp)

eq([(0, 0), (4, 0), (0, 4)], (3, 12, 16))
eq([(0, 0), (0, 4), (4, 0)], (3, 12, 16))
eq([[0, 0], [1, 0], [0, 1]], (0, 3, 1))
eq(((0, 0), (1, 0), (1, 1), (0, 1)), (0, 4, 2))
eq([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)], (1, 8, 8))
eq([(0, 0), (0, 0), (1, 0), (1, 1), (1, 1), (0, 1), (0, 0)], (0, 4, 2))
eq([(0, 0), (0, 0), (0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (0, 0)], (0, 4, 2))
eq([(0, 0), (5, 0), (10, 0), (10, 10), (0, 10)], (81, 40, 200))
eq([(5, 0), (10, 0), (10, 10), (0, 10), (0, 0)], (81, 40, 200))
eq([(10, 10), (10, 0), (5, 0), (0, 0), (0, 10), (5, 10)], (81, 40, 200))
eq([(0, 0), (7, 3), (2, 5)], (14, 3, 29))
eq([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)], (5, 16, 24))
eq([(0, 4), (2, 4), (2, 2), (4, 2), (4, 0), (0, 0)], (5, 16, 24))
eq([(0, 0), (10**9, 1), (0, 1)], (0, 10**9 + 2, 10**9))
eq([(-10**9, -10**9), (10**9, -10**9), (10**9, 10**9), (-10**9, 10**9)], (4 * 10**18 - 4 * 10**9 + 1, 8 * 10**9, 8 * 10**18))
# a triangle with a diagonal side: boundary gcd(2e9, 2e9) = 2e9 on the hypotenuse
eq([(-10**9, -10**9), (10**9, 10**9), (10**9, -10**9)], ((4 * 10**18 - 6 * 10**9 + 2) // 2, 6 * 10**9, 4 * 10**18))
# non-simple
assert bad([(0, 0), (2, 2), (2, 0), (0, 2)])
assert bad([(0, 0), (4, 0), (4, 4), (2, 0), (0, 4)])
assert bad([(0, 0), (4, 0), (2, 0), (2, 3)])
assert bad([(0, 0), (4, 0), (4, 4), (0, 4), (0, 2), (2, 2), (0, 2)])
assert bad([(0, 0), (4, 0), (4, 4), (2, 0), (2, 4), (0, 4)])
assert bad([(0, 0), (4, 0), (4, 4), (0, 4), (2, 0)])
assert bad([(0, 0), (4, 0), (4, 4), (0, 4), (2, 4), (2, 2), (3, 2), (3, 3)])
assert bad([(0, 0), (2, 0), (4, 0), (4, 4), (0, 4), (2, 0)])
assert bad([(0, 0), (6, 0), (6, 6), (3, 0), (0, 6)])
assert bad([(0, 0), (4, 0), (4, 4), (0, 4), (4, 0), (0, 0)])
assert bad([(0, 0), (4, 0), (4, 4), (2, 2), (0, 4), (2, 2)])
# touching at a vertex of two corners is not allowed either
assert bad([(0, 0), (4, 0), (2, 2), (4, 4), (0, 4), (2, 2)])
# 4 vertices with last two neighbours
assert bad([(0, 0), (2, 0), (1, 0), (1, 1)])
assert bad([(0, 0), (3, 0), (1, 0), (1, 5)])
# zero area / too few
assert bad([(0, 0), (1, 1), (2, 2)]) and bad([(0, 0), (0, 0), (5, 5)]) and bad([(1, 1)] * 5) and bad([(0, 0), (4, 0), (2, 0)])
assert bad([(0, 0), (1, 0), (2, 0), (3, 0)]) and bad([(1, 1)] * 2000) and bad([(0, 0), (1, 0), (0, 0), (1, 0)])
# validation
for p in [None, [], [(0, 0), (1, 0)], "abc", 5, {(0, 0), (1, 0), (0, 1)}, [(0, 0), (1, 0), (0, 1), (2,)], [(0, 0), (1, 0), (0, 1, 2)], [(0, 0), (1.0, 0), (0, 1)], [(0, 0), (1, 0), (0, True)],
          [(0, 0), (1, 0), (False, 1)], [(0, 0), (1, 0), ("0", 1)], [(0, 0), (1, 0), (0, 10**9 + 1)], [(0, 0), (1, 0), (-10**9 - 1, 1)], [(0, 0), (1, 0), None], [(0, 0), (1, 0), 7],
          [(0, 0), (1, 0), (0, 1), (0, 0, 0)], [(0, 0), (1, 0), (0, 1.5)], [(0, 0), (1, 0), (0, None)], [(1, 1)] * 2001, [[0, 0], [1, 0], "ab"]]:
    assert bad(p), p
eq([(10**9, 0), (0, 10**9), (-10**9, 0), (0, -10**9)], (2 * 10**18 - 2 * 10**9 + 1, 4 * 10**9, 4 * 10**18))

# large convex: (i, i*i) for i in 0..N-1 closed by the chord
def parab(N):
    return [(i, i * i) for i in range(N)]

def parab_expect(N):
    c = N - 1
    I = sum(max(0, c * i - i * i - 1) for i in range(1, c))
    B = c * 1 + c
    return I, B, 2 * I + B - 2

for N in (300, 600):
    pts = parab(N)
    exp = parab_expect(N)
    eq(pts, exp)
    eq(pts[::-1], exp)
    eq(pts[117:] + pts[:117], exp)
    k = 1000
    big = [(x * k, y * k) for x, y in pts]
    I, B, A2 = exp
    Bk = B * k
    A2k = A2 * k * k
    eq(big, ((A2k - Bk + 2) // 2, Bk, A2k))
# one nudged vertex makes it non-simple (large n, fast rejection)
pts = parab(500)
pts[250] = (250, 10**6)
assert bad(pts)
pts = parab(500)
pts.append(pts[10])
assert bad(pts)
# a staircase (valid, orthogonal, many collinear-free corners)
P = [(0, 0)]
for i in range(100):
    P += [(2 * i, 2 * i + 2), (2 * i + 2, 2 * i + 2)]
P += [(200, 0)]
twice = sum(4 * (2 * i + 2) for i in range(100))
eq(P, ((twice - 800 + 2) // 2, 800, twice))
eq(P[::-1], ((twice - 800 + 2) // 2, 800, twice))

# brute-force oracle for small coordinates
def common(a, b, c, d):
    ax, ay = a
    bx, by = b
    cx, cy = c
    dx, dy = d
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    den = rx * sy - ry * sx
    qx, qy = cx - ax, cy - ay
    if den != 0:
        t = F(qx * sy - qy * sx, den)
        u = F(qx * ry - qy * rx, den)
        if 0 <= t <= 1 and 0 <= u <= 1:
            return ("p", (ax + t * rx, ay + t * ry))
        return None
    if qx * ry - qy * rx != 0:
        return None
    rr = rx * rx + ry * ry
    t0 = F(qx * rx + qy * ry, rr)
    t1 = F((dx - ax) * rx + (dy - ay) * ry, rr)
    lo, hi = max(F(0), min(t0, t1)), min(F(1), max(t0, t1))
    if lo > hi:
        return None
    if lo == hi:
        return ("p", (ax + lo * rx, ay + lo * ry))
    return ("s",)

def oracle(poly):
    v = []
    for p in poly:
        if not v or v[-1] != p:
            v.append(p)
    while len(v) > 1 and v[0] == v[-1]:
        v.pop()
    m = len(v)
    if m < 3:
        return None
    e = [(v[i], v[(i + 1) % m]) for i in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            com = common(e[i][0], e[i][1], e[j][0], e[j][1])
            adj = j == i + 1 or (i == 0 and j == m - 1)
            if adj:
                sv = v[j] if j == i + 1 else v[0]
                if com != ("p", (F(sv[0]), F(sv[1]))):
                    return None
            elif com is not None:
                return None
    a2 = abs(sum(e[i][0][0] * e[i][1][1] - e[i][1][0] * e[i][0][1] for i in range(m)))
    if a2 == 0:
        return None
    xs = [p[0] for p in v]
    ys = [p[1] for p in v]
    inside = bound = 0
    for px in range(min(xs), max(xs) + 1):
        for py in range(min(ys), max(ys) + 1):
            on = False
            cnt = 0
            for (x1, y1), (x2, y2) in e:
                if (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) == 0 and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
                    on = True
                    break
                if (y1 > py) != (y2 > py):
                    lhs = (px - x1) * (y2 - y1)
                    rhs = (py - y1) * (x2 - x1)
                    if (y2 - y1 > 0 and lhs < rhs) or (y2 - y1 < 0 and lhs > rhs):
                        cnt += 1
            if on:
                bound += 1
            elif cnt % 2 == 1:
                inside += 1
    return (inside, bound, a2)

random.seed(4008)
R = 5

def clamp(x):
    return max(-R, min(R, x))

def star():
    import math
    k = random.randint(3, 9)
    cx, cy = random.randint(-1, 1), random.randint(-1, 1)
    angs = sorted(random.uniform(0, 2 * math.pi) for _ in range(k))
    pts = []
    for a in angs:
        r = random.uniform(1, 5)
        pts.append((clamp(cx + round(r * math.cos(a))), clamp(cy + round(r * math.sin(a)))))
    return pts

def dress(p):
    p = list(p)
    out = []
    for i, q in enumerate(p):
        out.append(q)
        if random.random() < 0.15:
            out.append(q)
        nx = p[(i + 1) % len(p)]
        if random.random() < 0.3:
            mx, my = q[0] + nx[0], q[1] + nx[1]
            if mx % 2 == 0 and my % 2 == 0:
                out.append((mx // 2, my // 2))
    s = random.randrange(len(out))
    out = out[s:] + out[:s]
    if random.random() < 0.5:
        out.reverse()
    if random.random() < 0.15:
        out.append(out[0])
    return out

def gen():
    r = random.random()
    if r < 0.3:
        return [(random.randint(-R, R), random.randint(-R, R)) for _ in range(random.randint(3, 8))]
    if r < 0.8:
        return dress(star())
    if r < 0.9:
        pts = [(random.randint(-R, R), random.randint(-R, R)) for _ in range(random.randint(3, 9))]
        pts.sort(key=lambda q: (q[0] > 0 or (q[0] == 0 and q[1] > 0), q[1] * 1.0 / (abs(q[0]) + 1e-9) if q[0] else 1e9 * q[1]))
        return dress(pts)
    p = dress(star())
    i = random.randrange(len(p))
    p[i] = (random.randint(-R, R), random.randint(-R, R))
    return p

ok = err = 0
for _ in range(900):
    p = gen()
    exp = oracle(p)
    if exp is None:
        assert bad(p), p
        err += 1
    else:
        eq(p, exp)
        ok += 1
assert ok > 250 and err > 250, (ok, err)
''', r'''
from math import gcd


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _in_box(a, b, p):
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _touch(a, b, c, d):
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return ((d1 == 0 and _in_box(c, d, a)) or (d2 == 0 and _in_box(c, d, b))
            or (d3 == 0 and _in_box(a, b, c)) or (d4 == 0 and _in_box(a, b, d)))


def lattice_count(poly):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= 10 ** 9
    if not isinstance(poly, (list, tuple)) or not 3 <= len(poly) <= 2000:
        raise ValueError("poly")
    pts = []
    for p in poly:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not isint(p[0]) or not isint(p[1]):
            raise ValueError("vertex")
        pts.append((p[0], p[1]))
    v = []
    for p in pts:
        if not v or v[-1] != p:
            v.append(p)
    while len(v) > 1 and v[0] == v[-1]:
        v.pop()
    m = len(v)
    if m < 3:
        raise ValueError("degenerate")
    for i in range(m):
        a, b, c = v[i - 1], v[i], v[(i + 1) % m]
        if _cross(a, b, c) == 0 and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0:
            raise ValueError("spike")
    for i in range(m):
        a, b = v[i], v[(i + 1) % m]
        for j in range(i + 2, m):
            if i == 0 and j == m - 1:
                continue
            if _touch(a, b, v[j], v[(j + 1) % m]):
                raise ValueError("not simple")
    twice = 0
    bnd = 0
    for i in range(m):
        a, b = v[i], v[(i + 1) % m]
        twice += a[0] * b[1] - b[0] * a[1]
        bnd += gcd(abs(b[0] - a[0]), abs(b[1] - a[1]))
    twice = abs(twice)
    if twice == 0:
        raise ValueError("zero area")
    return ((twice - bnd + 2) // 2, bnd, twice)
''')

task("v4_09_dec_round", r'''
Write `round_dec(s, places, mode)` that rounds an exact decimal string and returns a canonical
decimal string. Do not use the decimal or fractions modules.
s: an optional sign "+" or "-", then digits with at most one ".", with at least one digit in
all ("5.", ".5" and "0005" are fine, "." is not), then optionally "e" or "E", an optional sign
and 1 to 10 digits. ASCII digits only; no spaces, no underscores. The value is exact: the
mantissa times 10 to the exponent. places: an int (not a bool) in -10**6..10**6. mode: one of
"half_even", "half_up", "half_down", "floor", "ceil", "up", "down". Anything else (including a
non-str s) is a ValueError.
Round the exact value to a multiple of 10**-places (places 2 is hundredths; places -2 is
hundreds):
- "floor" rounds toward -infinity, "ceil" toward +infinity, "up" away from zero, "down" toward
  zero; a value that is already a multiple is left unchanged by all four.
- "half_even", "half_up", "half_down" round to the nearest multiple; an exact tie goes to the
  even multiple, the one away from zero, the one toward zero, respectively. A tie is decided on
  the exact value, never on a value that was already rounded.
Output: plain notation, no exponent, no "+". The integer part has no leading zeros, and is "0"
if it is zero. With places > 0 there is a "." and exactly `places` fractional digits ("0.00",
"12.30"). With places <= 0 there is no "."; a non-zero result is its digits followed by -places
zeros ("1200"), and zero is just "0". A "-" appears only if the rounded result is not zero:
"-0.4" with places 0 gives "0" for "half_even", "ceil" and "down", and "-1" for "floor".
Size limit: if the output would have more than 4000 digits (the integer part, counting the "0"
of a zero integer part, plus the fractional digits), raise ValueError. The input can be
extreme though, and the answer must come back immediately: "1e-999999999" with places 2 gives
"0.00" for "half_even" and "0.01" for "up"; "0e9999999999" with places 2 gives "0.00";
"1e999999999" with places 0 is a ValueError; "0" with places -1000000 is "0".
Examples: round_dec("2.5", 0, "half_even") is "2"; round_dec("-2.5", 0, "half_up") is "-3";
round_dec("9.995", 2, "half_up") is "10.00"; round_dec("1250", -2, "half_even") is "1200".
''', r'''
_banned(mods=("decimal", "fractions"))
import decimal, random, time

_C = decimal.Context(prec=20050, Emax=decimal.MAX_EMAX, Emin=decimal.MIN_EMIN, traps=[decimal.InvalidOperation])
_R = {"half_even": decimal.ROUND_HALF_EVEN, "half_up": decimal.ROUND_HALF_UP, "half_down": decimal.ROUND_HALF_DOWN,
      "floor": decimal.ROUND_FLOOR, "ceil": decimal.ROUND_CEILING, "up": decimal.ROUND_UP, "down": decimal.ROUND_DOWN}

def oracle(s, places, mode):
    d = decimal.Decimal(s)
    q = decimal.Decimal((0, (1,), -places))
    try:
        r = d.quantize(q, rounding=_R[mode], context=_C)
    except decimal.InvalidOperation:
        return None
    if r == 0:
        r = abs(r)
    out = format(r, "f")
    if len(out.lstrip("-").replace(".", "")) > 4000:
        return None
    return out

def bad(*a):
    try:
        round_dec(*a)
    except ValueError:
        return True
    return False

def ok(s, places, mode, exp):
    got = round_dec(s, places, mode)
    assert got == exp, (s, places, mode, got, exp)
    o = oracle(s, places, mode)
    assert o == exp, ("oracle disagrees with the hand value", s, places, mode, o, exp)

H = []
def h(s, places, mode, exp):
    H.append((s, places, mode, exp))

for s, e in [("2.5", "2"), ("3.5", "4"), ("-2.5", "-2"), ("-3.5", "-4"), ("2.4999", "2"), ("2.5001", "3"), ("-2.5001", "-3"), ("0.5", "0"), ("1.5", "2"), ("-0.5", "0")]:
    h(s, 0, "half_even", e)
for s, e in [("2.5", "3"), ("-2.5", "-3"), ("2.4999", "2"), ("-2.4999", "-2"), ("0.5", "1"), ("-0.5", "-1"), ("0.49", "0")]:
    h(s, 0, "half_up", e)
for s, e in [("2.5", "2"), ("-2.5", "-2"), ("2.5000001", "3"), ("-2.5000001", "-3"), ("0.5", "0"), ("-0.5", "0"), ("3.5", "3")]:
    h(s, 0, "half_down", e)
for s, e in [("2.1", "2"), ("-2.1", "-3"), ("2.9", "2"), ("-2.9", "-3"), ("2.0", "2"), ("-2.00", "-2"), ("0.1", "0"), ("-0.1", "-1")]:
    h(s, 0, "floor", e)
for s, e in [("2.1", "3"), ("-2.1", "-2"), ("2.9", "3"), ("-2.9", "-2"), ("2.0", "2"), ("-2.00", "-2"), ("0.1", "1"), ("-0.1", "0")]:
    h(s, 0, "ceil", e)
for s, e in [("2.1", "3"), ("-2.1", "-3"), ("2.0", "2"), ("-2.0", "-2"), ("0.0001", "1"), ("-0.0001", "-1")]:
    h(s, 0, "up", e)
for s, e in [("2.9", "2"), ("-2.9", "-2"), ("2.0", "2"), ("0.9", "0"), ("-0.9", "0")]:
    h(s, 0, "down", e)
# carries
h("9.99", 1, "half_up", "10.0")
h("99.5", 0, "half_up", "100")
h("-99.5", 0, "half_even", "-100")
h("0.999", 2, "half_up", "1.00")
h("999.9999", 3, "up", "1000.000")
h("-999.9999", 3, "floor", "-1000.000")
h("9.995", 2, "half_up", "10.00")
h("9.995", 2, "half_even", "10.00")
h("9.985", 2, "half_even", "9.98")
h("9.985", 2, "half_down", "9.98")
h("0.9999999999999999999999", 3, "half_even", "1.000")
# negative zero and zero results
h("-0.4", 0, "half_even", "0")
h("-0.4", 0, "floor", "-1")
h("-0.4", 0, "ceil", "0")
h("-0.4", 0, "down", "0")
h("-0", 2, "floor", "0.00")
h("-0.0001", 2, "half_up", "0.00")
h("-0.0001", 2, "up", "-0.01")
h("-0.0001", 2, "ceil", "0.00")
h("-0.0001", 2, "floor", "-0.01")
h("0", 3, "floor", "0.000")
h("-0.000", 0, "up", "0")
h("000", -2, "up", "0")
h("0", -5, "half_even", "0")
h("-0e5", 1, "down", "0.0")
# padding and spellings
h("1.5", 3, "floor", "1.500")
h("12", 2, "up", "12.00")
h(".5", 1, "half_even", "0.5")
h("5.", 2, "down", "5.00")
h("0005.10", 1, "down", "5.1")
h("+7.25", 1, "half_even", "7.2")
h("+7.35", 1, "half_even", "7.4")
h("7.25", 1, "half_up", "7.3")
h("7.25", 1, "half_down", "7.2")
h("-7.25", 1, "half_up", "-7.3")
h("-7.25", 1, "half_down", "-7.2")
h("0.05", 1, "half_even", "0.0")
h("0.15", 1, "half_even", "0.2")
h("0.25", 1, "half_even", "0.2")
h("100", 1, "half_even", "100.0")
# negative places
h("1250", -2, "half_even", "1200")
h("1350", -2, "half_even", "1400")
h("1250", -2, "half_up", "1300")
h("-1250", -2, "half_down", "-1200")
h("-1250", -2, "half_up", "-1300")
h("1201", -2, "ceil", "1300")
h("-1201", -2, "floor", "-1300")
h("-1201", -2, "ceil", "-1200")
h("49", -2, "half_even", "0")
h("50", -2, "half_even", "0")
h("50", -2, "half_up", "100")
h("51", -2, "half_even", "100")
h("150", -2, "half_even", "200")
h("1", -1, "up", "10")
h("-1", -1, "up", "-10")
h("5", -1, "half_even", "0")
h("15", -1, "half_even", "20")
h("25", -1, "half_even", "20")
h("25", -1, "half_down", "20")
h("-25", -1, "half_up", "-30")
h("0.4", -1, "up", "10")
h("0.4", -1, "half_up", "0")
h("999", -1, "half_up", "1000")
h("999", -3, "half_up", "1000")
h("499.99", -3, "half_even", "0")
h("500", -3, "half_even", "0")
h("500.01", -3, "half_even", "1000")
h("1500", -3, "half_even", "2000")
h("1000", -3, "up", "1000")
h("1000.0001", -3, "up", "2000")
# exponents
h("1.5e2", 0, "down", "150")
h("1.5e2", 1, "down", "150.0")
h("15E-1", 0, "half_even", "2")
h("2.5e-1", 0, "half_up", "0")
h("2.5e-1", 1, "half_up", "0.3")
h("2.5e-1", 1, "half_even", "0.2")
h("5.e2", 0, "down", "500")
h(".5e1", 0, "down", "5")
h("1e+3", 0, "up", "1000")
h("1e0", 0, "down", "1")
h("1E+00", 0, "down", "1")
h("1e0000000001", 0, "up", "10")
h("12345e-2", 1, "half_even", "123.4")
h("12345e-2", 1, "half_up", "123.5")
h("12355e-2", 1, "half_even", "123.6")
h("0e5", 2, "up", "0.00")
h("0e9999999999", 2, "floor", "0.00")
h("0.00e-9999999999", 1, "ceil", "0.0")
h("-0.0e+9999999999", 0, "up", "0")
h("5e-1", 0, "half_even", "0")
h("5e-1", 0, "half_down", "0")
h("5e-1", 0, "half_up", "1")
h("5e-2", 0, "half_up", "0")
h("5e-2", 1, "half_up", "0.1")
h("0.05e1", 0, "half_up", "1")
h("0.05e1", 0, "half_even", "0")
h("0.05e1", 0, "half_down", "0")
h("1e-999999999", 2, "half_even", "0.00")
h("1e-999999999", 2, "up", "0.01")
h("1e-999999999", 2, "ceil", "0.01")
h("1e-999999999", 2, "floor", "0.00")
h("1e-999999999", 2, "down", "0.00")
h("-1e-999999999", 2, "floor", "-0.01")
h("-1e-999999999", 2, "ceil", "0.00")
h("-1e-999999999", 2, "up", "-0.01")
h("-1e-999999999", 2, "half_up", "0.00")
h("99999e-9999999999", 0, "up", "1")
h("5e-999999999", 0, "half_up", "0")
h("123456789e-9999999999", -3, "up", "1000")
h("123456789e-9999999999", -3, "down", "0")
h("1e-999999999", -1000000, "half_even", "0")
h("0", -1000000, "up", "0")
h("1", -1000000, "half_even", "0")
h("1", -1000000, "floor", "0")
h("-1", -1000000, "floor", "ValueError")
h("-1", -1000000, "ceil", "0")
# long mantissas
h("123456789012345678901234567890.5", 0, "half_even", "123456789012345678901234567890")
h("123456789012345678901234567891.5", 0, "half_even", "123456789012345678901234567892")
h("123456789012345678901234567890.5", 0, "half_up", "123456789012345678901234567891")
h("9" * 50 + ".5", 0, "half_up", "1" + "0" * 50)
h("9" * 50 + ".5", 0, "half_down", "9" * 50)
h("0." + "0" * 40 + "5", 41, "half_even", "0." + "0" * 40 + "5")
h("0." + "0" * 40 + "5", 40, "half_even", "0." + "0" * 40)
h("0." + "0" * 40 + "5", 40, "half_up", "0." + "0" * 39 + "1")
h("0." + "0" * 40 + "5000000000000001", 40, "half_even", "0." + "0" * 39 + "1")
# size limit
h("1e5000", 0, "up", "ValueError")
h("1e3999", 0, "up", "1" + "0" * 3999)
h("1e4000", 0, "up", "ValueError")
h("1e3999", -3990, "up", "1" + "0" * 3999)
h("1e4000", -3990, "up", "ValueError")
h("1", 3999, "up", "1." + "0" * 3999)
h("1", 4000, "up", "ValueError")
h("0", 3999, "floor", "0." + "0" * 3999)
h("0", 4000, "floor", "ValueError")
h("5", -3999, "up", "1" + "0" * 3999)
h("5", -4000, "up", "ValueError")
h("5", -4000, "half_even", "0")
h("1e999999999", 0, "half_even", "ValueError")
h("1e999999999", 5, "down", "ValueError")
h("0", 1000000, "up", "ValueError")
h("12e9999999999", -1000000, "up", "ValueError")
h("1.5", 10**6, "down", "ValueError")
h("9" * 3990, 5, "down", "9" * 3990 + "." + "0" * 5)
h("9" * 3990 + "e5", 0, "up", "9" * 3990 + "0" * 5)
h("9" * 3990 + "e11", 0, "up", "ValueError")
h("9" * 3990, 0, "down", "9" * 3990)
h("9" * 3990, 10, "down", "9" * 3990 + "." + "0" * 10)
h("9" * 3990, 11, "down", "ValueError")
h("9" * 3990 + "5e-1", 0, "half_even", "1" + "0" * 3990)
h("9" * 3000 + ".5", 0, "half_up", "1" + "0" * 3000)
for s, p, m, e in H:
    if e == "ValueError":
        assert bad(s, p, m), (s, p, m)
    elif len(s) < 4000:
        ok(s, p, m, e)
    else:
        assert round_dec(s, p, m) == e
# validation
for s in ["", "+", "-", ".", "+.", "-.", "e5", ".e5", "1e", "1e+", "1e-", "1e5.5", "1.2.3", "1,5", "1 ", " 1", "1\n", "\n1", "١٢", "1_0", "0x10", "inf", "nan", "NaN", "Infinity", "-inf",
          "--1", "+-1", "1e12345678901", "1ee5", "1e5e5", "1.5f", "−1", "1e٣", "１", "1 e5", "1e 5", "1.e", "1e+-5", "e", "E5", "+e5", "1f", "1.5.", "..5", "1e1.0", "½", "1\t", "1\x00"]:
    assert bad(s, 1, "half_even"), repr(s)
for s in [1, 1.5, None, b"1", ["1"], ("1",), True, 0]:
    assert bad(s, 1, "half_even"), s
for p in [1.0, "2", None, True, False, 10**6 + 1, -10**6 - 1, 2.5, [1], (1,)]:
    assert bad("1.5", p, "half_even"), p
assert bad("0", -10**6 - 1, "up") and bad("0", True, "up") and bad("0", False, "up") and round_dec("0", -10**6, "up") == "0"
for m in ["HALF_EVEN", "half-even", "halfeven", "", None, 1, "round", "Floor", "ceiling", "truncate", " up", "up ", ["up"], ("up",), True]:
    assert bad("1.5", 0, m), m

# random cases against the decimal module
random.seed(4009)
def rdigits(k):
    return "".join(random.choice("0123456789") for _ in range(k))

def rstr():
    kind = random.random()
    if kind < 0.35:
        ip, fp = rdigits(random.randint(0, 6)), rdigits(random.randint(0, 6))
        if not ip and not fp:
            ip = "0"
    elif kind < 0.7:
        # tie-heavy: a "5" followed by zeros at a random position
        ip, fp = rdigits(random.randint(0, 4)), rdigits(random.randint(0, 3)) + "5" + "0" * random.randint(0, 3)
        if random.random() < 0.15:
            fp = fp[:-1] + "1" if fp.endswith("0") else fp + "1"
    elif kind < 0.85:
        ip, fp = "9" * random.randint(0, 4), "9" * random.randint(0, 4) + random.choice(["", "5", "50", "4", "6"])
        if not ip and not fp:
            ip = "9"
    else:
        ip, fp = random.choice(["0", "00", ""]), "0" * random.randint(0, 5) + rdigits(random.randint(0, 3))
        if not ip and not fp:
            fp = "0"
    s = random.choice(["", "", "", "-", "-", "+"]) + ip
    if fp or random.random() < 0.7:
        if fp or ip:
            s += "." + fp
    if s.lstrip("+-") == "." or not (ip or fp):
        s = s.rstrip(".") + "0"
    r = random.random()
    if r < 0.5:
        s += random.choice("eE") + random.choice(["", "", "+", "-"]) + random.choice([str(random.randint(0, 12)), "00" + str(random.randint(0, 9)), str(random.randint(0, 60))])
    elif r < 0.55:
        s += "e" + random.choice(["-", "+", ""]) + random.choice(["999999999", "9999999999", "5000", "123456789"])
    return s

modes = list(_R)
nerr = nz = ntie = 0
t0 = time.time()
for _ in range(9000):
    s = rstr()
    places = random.choice([0, 0, 1, 2, 3, -1, -2, -3, random.randint(-12, 12), random.randint(-30, 30), random.choice([3999, 4000, -3999, -4000, 10**6, -10**6])])
    mode = random.choice(modes)
    exp = oracle(s, places, mode)
    if exp is None:
        assert bad(s, places, mode), (s, places, mode)
        nerr += 1
    else:
        got = round_dec(s, places, mode)
        assert got == exp, (s, places, mode, got, exp)
        nz += exp.lstrip("-0.") == ""
        ntie += mode.startswith("half")
assert nerr > 30 and nz > 300 and ntie > 2000, (nerr, nz, ntie)
assert time.time() - t0 < 5
''', r'''
import re

_PAT = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]{1,10}))?")
_MODES = frozenset(("half_even", "half_up", "half_down", "floor", "ceil", "up", "down"))
_LIM = 4000


def round_dec(s, places, mode):
    if (not isinstance(s, str) or type(places) is not int or not -10 ** 6 <= places <= 10 ** 6
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
    D = int(ip + fp)
    E = (int(ex) if ex else 0) - len(fp)
    T = -places
    if places > 0 and places >= _LIM:
        raise ValueError("size")
    q = 0
    inc = 0
    if D == 0:
        R = 0
    elif E >= T:
        if len(str(D)) + E - T > _LIM:
            raise ValueError("size")
        R = D * 10 ** (E - T)
    else:
        k = T - E
        nd = len(str(D))
        if k > nd:
            exact, half = False, -1
        else:
            p = 10 ** k
            q, r = divmod(D, p)
            exact = r == 0
            half = (2 * r > p) - (2 * r < p)
        if exact:
            inc = 0
        elif mode == "up":
            inc = 1
        elif mode == "down":
            inc = 0
        elif mode == "floor":
            inc = 1 if neg else 0
        elif mode == "ceil":
            inc = 0 if neg else 1
        elif half > 0:
            inc = 1
        elif half < 0:
            inc = 0
        elif mode == "half_up":
            inc = 1
        elif mode == "half_down":
            inc = 0
        else:
            inc = q & 1
        R = q + inc
    digits = str(R)
    if places > 0:
        total = max(len(digits), places + 1)
    elif R == 0:
        total = 1
    else:
        total = len(digits) + T
    if total > _LIM:
        raise ValueError("size")
    if places > 0:
        digits = digits.rjust(places + 1, "0")
        body = digits[:-places] + "." + digits[-places:]
    elif R == 0:
        body = "0"
    else:
        body = digits + "0" * T
    return "-" + body if neg and R != 0 else body
''')

task("v4_10_bracelets", r'''
Write `proper_bracelets(n, k, m=10**9 + 7)`. A cycle has the vertices 0..n-1, vertex i is
adjacent to i+1 and vertex n-1 to vertex 0. Each vertex gets one of k labeled colors, and a
coloring is proper if adjacent vertices have different colors. Two colorings count as the same
if one becomes the other under a rotation or a reflection of the cycle (the 2n symmetries of
the n-gon; colors are never permuted or merged). Return the number of distinct proper
colorings, taken modulo m, as an int in 0..m-1.
n, k and m must be ints (bool is not an int) with n >= 3, k >= 1 and m >= 2, else ValueError.
n goes up to 10**12, k up to 10**18 and m up to 10**18; m is any integer, not necessarily
prime and possibly sharing factors with 2n. The count itself is far too large to build and n is
too large to loop over its rotations. The call must return in well under a second.
Examples: proper_bracelets(3, 3) is 1; proper_bracelets(4, 3) is 6; proper_bracelets(5, 3) is 3;
proper_bracelets(6, 3) is 13; proper_bracelets(8, 2) is 1 and proper_bracelets(7, 2) is 0.
''', r'''
import random, time
from math import gcd

def bad(*a):
    try:
        proper_bracelets(*a)
    except ValueError:
        return True
    return False

assert proper_bracelets(3, 3) == 1 and proper_bracelets(4, 3) == 6 and proper_bracelets(5, 3) == 3
assert proper_bracelets(6, 3) == 13 and proper_bracelets(8, 2) == 1 and proper_bracelets(7, 2) == 0
assert proper_bracelets(3, 3, 10**9 + 7) == 1 and proper_bracelets(3, 2) == 0 and proper_bracelets(3, 1) == 0
assert proper_bracelets(4, 2) == 1 and proper_bracelets(4, 1) == 0 and proper_bracelets(10, 1, 2) == 0
assert proper_bracelets(1000, 2) == 1 and proper_bracelets(999, 2) == 0
assert proper_bracelets(6, 3, 2) == 1 and proper_bracelets(6, 3, 13) == 0 and proper_bracelets(6, 3, 5) == 3 and proper_bracelets(6, 3, 12) == 1
assert proper_bracelets(4, 3, 4) == 2 and proper_bracelets(4, 3, 6) == 0 and proper_bracelets(4, 3, 7) == 6 and proper_bracelets(4, 3, 5) == 1
for a in [(2, 3), (1, 3), (0, 3), (-5, 3), (3, 0), (3, -1), (3, 3, 1), (3, 3, 0), (3, 3, -7), (True, 3), (3, True), (3, 3, True), (4.0, 3), (4, 3.0), (4, 3, 7.0),
          ("4", 3), (4, "3"), (4, 3, "7"), (None, 3), (4, None), (4, 3, None)]:
    assert bad(*a), a

# brute force over explicit colorings, canonical form under all 2n symmetries
def brute(n, k):
    syms = []
    for r in range(n):
        syms.append([(i + r) % n for i in range(n)])
        syms.append([(r - i) % n for i in range(n)])
    seen = set()
    c = []
    def rec():
        if len(c) == n:
            if c[0] != c[-1]:
                seen.add(min(tuple(c[s[i]] for i in range(n)) for s in syms))
            return
        for x in range(k):
            if not c or c[-1] != x:
                c.append(x)
                rec()
                c.pop()
    rec()
    return len(seen)

for n in range(3, 10):
    for k in range(1, 5 if n <= 8 else 4):
        b = brute(n, k)
        assert proper_bracelets(n, k, 10**30) == b, (n, k, b)
        assert proper_bracelets(n, k, 10**9 + 7) == b % (10**9 + 7)
        for m in (2, 3, 4, 6, 12, 2 * n, 4 * n, 7):
            assert proper_bracelets(n, k, m) == b % m, (n, k, m)

# independent exact Burnside through the cycle structure of each symmetry
def fixed(n, k, perm):
    seen = [False] * n
    cyc = [0] * n
    nc = 0
    for i in range(n):
        if not seen[i]:
            j = i
            while not seen[j]:
                seen[j] = True
                cyc[j] = nc
                j = perm[j]
            nc += 1
    edges = set()
    for i in range(n):
        a, b = cyc[i], cyc[(i + 1) % n]
        if a == b:
            return 0
        edges.add((min(a, b), max(a, b)))
    deg = [0] * nc
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    if len(edges) == nc - 1:
        return k * (k - 1) ** (nc - 1)
    assert len(edges) == nc and all(x == 2 for x in deg)
    return (k - 1) ** nc + (-1) ** nc * (k - 1)

def exact(n, k):
    tot = 0
    for r in range(n):
        tot += fixed(n, k, [(i + r) % n for i in range(n)])
        tot += fixed(n, k, [(r - i) % n for i in range(n)])
    assert tot % (2 * n) == 0
    return tot // (2 * n)

for n in range(3, 9):
    for k in range(1, 5):
        assert exact(n, k) == brute(n, k), (n, k)
random.seed(4010)
for _ in range(120):
    n = random.choice([random.randint(3, 20), random.randint(3, 60), 12, 16, 30, 36, 60, 49, 53])
    k = random.choice([random.randint(1, 5), random.randint(1, 10**6), random.randint(1, 10**18), 2, 3, 10**18])
    e = exact(n, k)
    for m in (random.randint(2, 10**18), random.randint(2, 100), 2 * n * random.randint(1, 50), 10**9 + 7, random.choice([2, 4, 8, 16, 3, 9, 6, 12]) * n, e if e > 1 else 2):
        got = proper_bracelets(n, k, m)
        assert got == e % m and isinstance(got, int), (n, k, m, got, e % m)
    assert proper_bracelets(n, k) == e % (10**9 + 7)
# a slow independent check of the rotation sum for medium n
def slow(n, k):
    tot = 0
    for r in range(n):
        g = gcd(r, n)
        tot += (k - 1) ** g + (-1) ** g * (k - 1)
    if n % 2 == 0:
        tot += (n // 2) * k * (k - 1) ** (n // 2)
    assert tot % (2 * n) == 0
    return tot // (2 * n)
for _ in range(25):
    n = random.randint(61, 360)
    k = random.randint(1, 40)
    m = random.choice([random.randint(2, 10**18), 2 * n, 10**9 + 7, n * n])
    assert proper_bracelets(n, k, m) == slow(n, k) % m, (n, k, m)
# huge n: speed and consistency across coprime moduli
t0 = time.time()
for n in (963761198400, 999999999989, 999983 * 999983, 2**39, 10**12, 10**12 - 1, 735134400 * 1000):
    k = random.choice([2, 3, 10**18, 123456789012345678])
    seen = {}
    for m in (10**9 + 7, 998244353, 10**18, 2 * n, 4 * n + 1, 2**60, 10**9 + 7 + 998244353):
        r = proper_bracelets(n, k, m)
        assert isinstance(r, int) and 0 <= r < m
        seen[m] = r
    assert seen[10**18] % 10**9 == proper_bracelets(n, k, 10**9) and seen[2**60] % 1024 == proper_bracelets(n, k, 1024) and seen[10**18] % 1024 == seen[2**60] % 1024
    assert seen[10**9 + 7 + 998244353] == proper_bracelets(n, k, 10**9 + 7 + 998244353)
    assert proper_bracelets(n, k, (10**9 + 7) * 998244353) % (10**9 + 7) == seen[10**9 + 7]
    assert proper_bracelets(n, k, (10**9 + 7) * 998244353) % 998244353 == seen[998244353]
    assert proper_bracelets(n, k, 2 * n) == seen[2 * n]
    assert proper_bracelets(n, 2, 10**18) == (1 if n % 2 == 0 else 0)
    assert proper_bracelets(n, 1, 10**18) == 0
assert time.time() - t0 < 3.0, time.time() - t0
''', r'''
def _factor(n):
    f = {}
    p = 2
    while p * p <= n:
        while n % p == 0:
            f[p] = f.get(p, 0) + 1
            n //= p
        p += 1 if p == 2 else 2
    if n > 1:
        f[n] = f.get(n, 0) + 1
    return f


def proper_bracelets(n, k, m=10**9 + 7):
    for v in (n, k, m):
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("int")
    if n < 3 or k < 1 or m < 2:
        raise ValueError("range")
    mod = 2 * n * m
    divs = [(1, 1)]
    for p, a in _factor(n).items():
        nxt = []
        for d, ph in divs:
            pk = 1
            for i in range(a + 1):
                nxt.append((d * pk, ph * (1 if i == 0 else pk - pk // p)))
                pk *= p
        divs = nxt
    total = 0
    for e, ph in divs:
        d = n // e
        fixed = pow(k - 1, d, mod) + (k - 1 if d % 2 == 0 else -(k - 1))
        total += ph * fixed
    if n % 2 == 0:
        total += (n // 2) * k * pow(k - 1, n // 2, mod)
    total %= mod
    return (total // (2 * n)) % m
''')

# --- tasks 11-30 are appended here (seeds 4011-4030) ---

TASKS = T
PROBE_IDS = [t["id"] for t in T[:10]]
