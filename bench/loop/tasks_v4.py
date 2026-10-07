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

task("v4_11_hdlc_unframe", r'''
Write `hdlc_unframe(data)` that splits a byte stream in HDLC-style framing into frame payloads and returns them as a list of `bytes`, in stream order. `data` must be a `bytes` or `bytearray`, else ValueError. Every error below raises ValueError.
Bytes: 0x7E is the flag, 0x7D is the escape. The stream is read left to right in one of two states. Before the first flag it is hunting: every byte except 0x7E is ignored, and a 0x7E starts a frame. From then on it is inside a frame, for good (it never returns to hunting).
Inside a frame bytes are collected into a buffer, after unescaping:
- an ordinary byte is appended as it is;
- 0x7D must be followed by a second byte E. If E is 0x5E, append 0x7E; if E is 0x5D, append 0x7D (the escape pair is consumed as a unit). If E is 0x7E, it is the abort sequence: the buffer is emptied (the frame is discarded unchecked) and that 0x7E counts as a flag, so a new frame starts at once. Any other E is a ValueError;
- 0x7E is the flag: if the buffer is empty it is ignored (a repeated flag), otherwise the buffer is a complete frame, which is checked as below and then the buffer is emptied. Either way the same flag also opens the next frame, so one flag can end a frame and start the next.
- If the buffer ever holds more than 1024 bytes, that is a ValueError at once, even if a later abort would have discarded the frame.
Checking a frame: the last two buffer bytes are a CRC-16 (big-endian) of all the bytes before them, and what remains is the payload, which must be at least 1 byte; so a frame shorter than 3 bytes is a ValueError. The CRC is CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF, bits processed most significant first, no reflection, no final xor (the CRC of b"123456789" is 0x29B1). A wrong CRC is a ValueError. The CRC bytes are escaped on the wire like any other byte.
At the end of the data, if it is inside a frame and the buffer is not empty or an escape byte 0x7D is still waiting for its second byte, the stream is truncated: ValueError. An empty buffer there is fine (the last flag simply opened a frame that never began), and data that never contained a flag returns [].
Errors found inside a frame are raised even if the frame would later have been aborted, because the stream is read in order; an aborted frame is only exempt from the frame checks (length and CRC).
Examples (hex):
7e41b9157e -> [b"A"]
7e7d5e7d5ea97e -> [b"~"] (payload 0x7E, CRC 0x7EA9, all three escaped as needed)
7e41b97d7e41b9157e -> [b"A"] (the first frame was aborted)
7e41b915 -> ValueError (truncated); 7e41b9167e -> ValueError (bad CRC); 7e7d417e -> ValueError (bad escape)
''', r'''
import binascii, random, re

def frame(p, crc=None):
    c = binascii.crc_hqx(p, 0xFFFF) if crc is None else crc
    return p + bytes([c >> 8, c & 255])

def esc(b):
    out = bytearray()
    for x in b:
        if x == 0x7E:
            out += b"\x7d\x5e"
        elif x == 0x7D:
            out += b"\x7d\x5d"
        else:
            out.append(x)
    return bytes(out)

def wire(p, crc=None):
    return esc(frame(p, crc))

F = b"\x7e"

def bad(d):
    try:
        hdlc_unframe(d)
    except ValueError:
        return True
    return False

def eq(d, exp):
    got = hdlc_unframe(d)
    assert got == exp and type(got) is list and all(type(x) is bytes for x in got), (d, got, exp)

eq(bytes.fromhex("7e41b9157e"), [b"A"])
eq(bytes.fromhex("7e7d5e7d5ea97e"), [b"~"])
eq(bytes.fromhex("7e41b97d7e41b9157e"), [b"A"])
assert bad(bytes.fromhex("7e41b915"))
assert bad(bytes.fromhex("7e41b9167e"))
assert bad(bytes.fromhex("7e7d417e"))
eq(b"", [])
eq(b"hello world", [])
eq(b"hello\x7d", [])
eq(b"\x7d\x41\x7d", [])
eq(F, [])
eq(F + F + F, [])
assert bad(b"junk" + F + F + b"more")
eq(b"junk" + F + wire(b"A") + F, [b"A"])
eq(F + wire(b"A") + F + wire(b"BC") + F, [b"A", b"BC"])
assert bad(F + wire(b"A") + wire(b"BC") + F)
eq(F + F + F + wire(b"A") + F + F + F + wire(b"A") + F + F, [b"A", b"A"])
eq(F + wire(b"A") + F, [b"A"])
assert bad(F + wire(b"A") + F + b"x")
assert bad(F + wire(b"A") + F + b"\x7d")
assert bad(F + wire(b"A") + b"\x7d")
assert bad(F + b"\x7d")
assert bad(F + b"x")
# the abort sequence
eq(F + b"abc" + b"\x7d\x7e" + wire(b"Z") + F, [b"Z"])
eq(F + b"\x7d\x7e" + wire(b"Z") + F, [b"Z"])
eq(b"\x7d\x7e" + wire(b"Z") + F, [b"Z"])
eq(b"zz\x7d\x7e" + wire(b"Z") + F, [b"Z"])
assert bad(b"zz\x7d\x7ezz" + F + wire(b"Z") + F)
eq(b"\x7d\x7e" + b"\x7d\x7e" + wire(b"Z") + F, [b"Z"])
eq(F + wire(b"Q") + F + b"\x7d\x7e" + F, [b"Q"])
eq(F + wire(b"Q") + b"\x7d\x7e", [])
eq(F + b"\x01\x02\x03\x04" + b"\x7d\x7e" + F + b"\x01" + b"\x7d\x7e", [])
assert bad(F + b"\x7d\x41" + b"\x7d\x7e" + F)     # bad escape then abort: still an error
assert bad(F + b"\x7d\x7d" + b"\x7d\x7e" + F)
eq(b"\x7d\x41\x7d\x7d" + F + wire(b"A") + F, [b"A"])   # hunting ignores bad escapes
eq(b"\x7d\x7d\x7d" + F + wire(b"A") + F, [b"A"])
# frame checks
assert bad(F + frame(b"")[:2] + F)     # CRC only, no payload
assert bad(F + b"\x01" + F)
assert bad(F + b"\x01\x02" + F)
assert bad(F + wire(b"A", 0) + F)
assert bad(F + wire(b"A", 0xB914) + F)
assert bad(F + wire(b"A", 0xB815) + F)
eq(F + wire(b"A", 0xB915) + F, [b"A"])
eq(F + wire(bytes(range(256))) + F, [bytes(range(256))])
eq(F + wire(b"\x7e\x7d\x7e\x7d\x5e\x5d") + F, [b"\x7e\x7d\x7e\x7d\x5e\x5d"])
eq(F + wire(b"\x00") + F, [b"\x00"])
eq(F + wire(b"123456789") + F, [b"123456789"])
assert binascii.crc_hqx(b"123456789", 0xFFFF) == 0x29B1
# the 1024 limit counts unescaped bytes, payload + CRC
eq(F + wire(b"a" * 1022) + F, [b"a" * 1022])
assert bad(F + wire(b"a" * 1023) + F)
assert bad(F + wire(b"a" * 1023) + b"\x7d\x7e")
eq(F + wire(b"\x7e" * 1022) + F, [b"\x7e" * 1022])
assert bad(F + wire(b"\x7e" * 1023) + F)
assert bad(F + b"b" * 1025 + b"\x7d\x7e" + F)
eq(F + b"b" * 1024 + b"\x7d\x7e" + F, [])
assert bad(F + b"b" * 1024 + b"b" + b"\x7d\x7e" + F)
# types
for d in ["abc", None, 12, [1, 2], memoryview(b"~")]:
    assert bad(d), d
eq(bytearray(F + wire(b"A") + F), [b"A"])
r = hdlc_unframe(bytearray(F + wire(b"A") + F))
assert type(r[0]) is bytes

# oracle: tokens (abort | escape pair | lone escape | flag | run of ordinary bytes)
TOK = re.compile(rb"\x7d\x7e|\x7d.?|\x7e|[^\x7d\x7e]+", re.S)

def oracle(d):
    started = False
    cur = bytearray()
    out = []
    for t in TOK.findall(d):
        if t in (b"\x7e", b"\x7d\x7e"):
            if t == b"\x7d\x7e":
                cur = bytearray()
            elif cur:
                if len(cur) < 3 or binascii.crc_hqx(bytes(cur[:-2]), 0xFFFF) != int.from_bytes(cur[-2:], "big"):
                    raise ValueError("frame")
                out.append(bytes(cur[:-2]))
                cur = bytearray()
            started = True
            continue
        if not started:
            continue
        if t[0] == 0x7D:
            if len(t) == 1:
                raise ValueError("trunc")
            if t[1] not in (0x5E, 0x5D):
                raise ValueError("escape")
            cur.append(0x7E if t[1] == 0x5E else 0x7D)
        else:
            cur += t
        if len(cur) > 1024:
            raise ValueError("long")
    if started and cur:
        raise ValueError("trunc")
    return out

def both(d):
    try:
        exp = oracle(d)
    except ValueError:
        exp = ValueError
    try:
        got = hdlc_unframe(d)
    except ValueError:
        got = ValueError
    assert got == exp, (d.hex(), got, exp)
    return exp

random.seed(4011)
def rbytes(n, hot=0.0):
    return bytes(random.choice([0x7E, 0x7D, 0x5E, 0x5D]) if random.random() < hot else random.randrange(256) for _ in range(n))

def piece():
    r = random.random()
    if r < 0.40:
        p = rbytes(random.choice([1, 1, 2, 3, 5, 12, 40]), random.choice([0.0, 0.3, 0.7]))
        c = None if random.random() < 0.93 else random.randrange(65536)
        return wire(p, c)
    if r < 0.55:
        return F
    if r < 0.65:
        return b"\x7d\x7e"
    if r < 0.75:
        return rbytes(random.randint(1, 4), 0.0).replace(b"\x7e", b"x").replace(b"\x7d", b"y")
    if r < 0.80:
        return b"\x7d" + bytes([random.choice([0x5E, 0x5D, 0x41, 0x7D, 0x00, 0x7E, 0x5F])])
    if r < 0.85:
        return b"\x7d"
    if r < 0.88:
        return wire(rbytes(random.choice([1021, 1022, 1023, 1024]), 0.1))
    return wire(random.choice([b"A", b"hello", b"\x7e", b"\x7d\x7e"]))

nerr = nok = 0
for _ in range(220):
    n = random.choice([1, 2, 3, 4, 6, 9])
    d = b"".join(piece() for _ in range(n))
    if random.random() < 0.5:
        d = random.choice([b"", F, b"\x01\x02", F + F]) + d
    r = both(d)
    if r is ValueError:
        nerr += 1
    else:
        nok += 1
assert nok > 30 and nerr > 30, (nok, nerr)

# clean streams built from known payloads, with abort noise and shared flags
for _ in range(120):
    pls = [rbytes(random.randint(1, 30), random.choice([0.0, 0.5])) for _ in range(random.randint(0, 6))]
    d = bytearray(random.choice([b"", b"noise", b"\x7d\x01", b"\x00\x7d"]))
    d += F
    for p in pls:
        for _ in range(random.choice([0, 0, 1, 2])):
            d += F
        if random.random() < 0.3:
            junk = esc(rbytes(random.randint(0, 20)))
            d += junk + b"\x7d\x7e"
        d += wire(p) + F
    for _ in range(random.choice([0, 1, 3])):
        d += F
    assert both(bytes(d)) == pls
    assert hdlc_unframe(bytes(d)) == pls
    if pls:
        e = bytes(d)
        k = random.randrange(len(e))
        t = e[:k]
        both(t)
        both(e + bytes([random.randrange(256)]))
''', r'''
def _crc(b):
    c = 0xFFFF
    for x in b:
        c ^= x << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def hdlc_unframe(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    out = []
    inside = False
    pend = False
    buf = bytearray()
    for b in data:
        if not inside:
            if b == 0x7E:
                inside = True
            continue
        if pend:
            pend = False
            if b == 0x7E:
                buf = bytearray()
                continue
            if b == 0x5E:
                buf.append(0x7E)
            elif b == 0x5D:
                buf.append(0x7D)
            else:
                raise ValueError("bad escape")
        elif b == 0x7D:
            pend = True
            continue
        elif b == 0x7E:
            if buf:
                if len(buf) < 3:
                    raise ValueError("short frame")
                if _crc(buf[:-2]) != (buf[-2] << 8 | buf[-1]):
                    raise ValueError("bad crc")
                out.append(bytes(buf[:-2]))
                buf = bytearray()
            continue
        else:
            buf.append(b)
        if len(buf) > 1024:
            raise ValueError("frame too long")
    if inside and (pend or buf):
        raise ValueError("truncated")
    return out
''')

task("v4_12_markov_run", r'''
Write `markov_run(program, text, limit)` that runs a Markov-algorithm program (a string rewriting system) on `text` and returns `(result, steps)`, a str and an int. `program` and `text` must be str and `limit` an int that is not a bool and is >= 0, else ValueError. Every failure below raises ValueError.
Program syntax. `program.split("\n")` gives the lines. Strip spaces, tabs and "\r" from both ends of each line; a line that is then empty or starts with "#" is skipped (there are no end-of-line comments). Every other line is a rule `LHS -> RHS` or a terminating rule `LHS ->. RHS`.
The arrow is the first "->" that is not inside a quoted string. A quoted string starts at a `"` and ends at the next `"` that is not escaped; inside quotes a backslash skips the character after it. A line with no arrow, or with an unterminated quote, is an error. The text after the arrow is the RHS part, except that if its very first character is "." (no space before it) the rule is terminating and that "." is dropped. The LHS part and the RHS part are each stripped of spaces, tabs and "\r" at both ends, then read as a pattern:
- if it contains no `"`, it is the literal text as it stands (backslashes are ordinary characters; it may be empty);
- otherwise it must be exactly one quoted string: first and last character are `"` (so length >= 2), and between them there is no unescaped `"`. The only escapes are \" \\ \n (newline) \t (tab); any other backslash sequence, or a backslash just before the closing quote, is an error.
Quoting is how a pattern keeps edge spaces, contains "->", starts with "#", or holds a newline. The whole program is parsed before anything runs, so a syntax error in any line is an error even if that rule would never fire.
Running. Rules are tried in program order. Repeat: take the first rule whose LHS occurs in the current text (an empty LHS occurs everywhere, at index 0). In the text, replace the leftmost occurrence of that LHS, one occurrence only, by the RHS; this is one step. If the rule is terminating, return `(text, steps)` at once. If no rule applies, return `(text, steps)`. A step that would be the (limit+1)-th is a ValueError, so a run that halts after exactly `limit` steps is fine, and limit 0 only accepts texts to which no rule applies. The text may never be longer than 10000 characters: the initial text and the text after every step are checked, and the result of a terminating step too.
Examples:
markov_run("a -> bb\n\"bb\" ->. X", "a", 5) == ("X", 2)
markov_run("ba -> ab", "bbaa", 9) == ("aabb", 4)
markov_run("-> x", "", 3) raises ValueError (an empty LHS applies forever)
markov_run('"a -> b" ->. [ok]\n x ->. .', "a -> b", 1) == ("[ok]", 1)
markov_run("a ->.x\na -> .y", "a", 1) == ("x", 1); markov_run("a -> .y", "a", 1) == (".y", 1)
''', r'''
import random

def bad(*a):
    try:
        markov_run(*a)
    except ValueError:
        return True
    return False

def eq(p, t, n, exp):
    got = markov_run(p, t, n)
    assert got == exp and type(got) is tuple and type(got[0]) is str and type(got[1]) is int, (p, t, n, got, exp)

eq("a -> bb\n\"bb\" ->. X", "a", 5, ("X", 2))
eq("ba -> ab", "bbaa", 9, ("aabb", 4))
assert bad("-> x", "", 3)
eq('"a -> b" ->. [ok]\n x ->. .', "a -> b", 1, ("[ok]", 1))
eq("a ->.x\na -> .y", "a", 1, ("x", 1))
eq("a -> .y", "a", 1, (".y", 1))
eq("a -> .b\nb ->. c", "a", 5, (".c", 2))
eq("a -> . b\nb ->. c", "a", 5, (". c", 2))
eq("a ->\t.b\nb ->. c", "a", 5, (".c", 2))
eq("", "abc", 0, ("abc", 0))
eq("# nothing\n\n   \n\t\r", "abc", 0, ("abc", 0))
eq("x -> y", "abc", 0, ("abc", 0))
assert bad("b -> y", "abc", 0)
eq("b -> y", "abc", 1, ("ayc", 1))
eq("b ->. y", "abc", 1, ("ayc", 1))
assert bad("b ->. y", "abc", 0)
assert bad("b -> c", "abb", 1)       # second step would be the 2nd
eq("b -> c", "abb", 2, ("acc", 2))
# first matching rule wins, then leftmost occurrence
eq("b ->. X\na -> Y", "ab", 1, ("aX", 1))
eq("a -> X\nb ->. Y", "ba", 2, ("YX", 2))
eq("aa -> X", "aaaa", 5, ("XX", 2))
eq("aa -> a", "aaaa", 9, ("a", 3))
eq("a -> b\nb ->. c", "a", 5, ("c", 2))
# empty patterns
eq("->. start", "mid", 1, ("startmid", 1))
assert bad("->", "", 5)
assert bad("->", "x", 5)
eq("a ->", "banana", 9, ("bnn", 3))
eq("a ->.", "banana", 9, ("bnana", 1))
eq("a -> \n", "aa", 3, ("", 2))
# arrows and the first-arrow rule
eq("a -> b -> c", "a", 1, ("b -> c", 1))
eq("a->b", "a", 1, ("b", 1))
eq("a ->b", "a", 1, ("b", 1))
eq("a-> b", "a", 1, ("b", 1))
eq("a--> b", "a-", 1, ("b", 1))
eq("a ->. b -> c", "a", 1, ("b -> c", 1))
eq("a ->..b", "a", 1, (".b", 1))
eq("a ->. .b", "a", 1, (".b", 1))
eq("a -> ..b", "a", 1, ("..b", 1))
eq("a -> . b", "a", 1, (". b", 1))
eq("a ->.", "a", 1, ("", 1))
eq("a ->. ", "a", 1, ("", 1))
# whitespace and comments
eq("   a  \t->\t  b   \r\n#c\n  # c2\n", "xa", 1, ("xb", 1))
eq("a -> b # note", "a", 1, ("b # note", 1))
eq("a\x0b -> b", "a\x0b", 1, ("b", 1))
eq("\x0ca -> b\x0c", "\x0ca", 1, ("b\x0c", 1))
eq("\xa0a\xa0 -> b", "\xa0a\xa0", 1, ("b", 1))
assert bad("a -> b", "a", True)
assert bad("", "a", False)
eq("a#b -> c", "xa#bx", 1, ("xcx", 1))
eq("#a -> b\nx -> y", "#ax", 1, ("#ay", 1))
eq("a -> b\r\nb ->. c\r\n", "a", 2, ("c", 2))
# quoting
eq('" a " -> "-"', "x a y", 1, ("x-y", 1))
eq('" a " -> -', "x a y", 1, ("x-y", 1))
eq('a -> " "', "a", 1, (" ", 1))
eq('a -> "  p  "', "a", 1, ("  p  ", 1))
assert bad('a -> " "x', "a", 1)
eq('"->" -> arrow', "a->b", 1, ("aarrowb", 1))
eq('"a\\"b" -> q', 'xa"by', 1, ("xqy", 1))
eq('q -> "a\\"b"', 'q', 1, ('a"b', 1))
eq('"\\\\" -> "/"', "a\\b", 1, ("a/b", 1))
eq('"\\n" -> "\\t"', "a\nb", 1, ("a\tb", 1))
eq('"\\n" ->. nl', "a\nb", 1, ("anlb", 1))
eq('"#x" -> y', "a#xb", 1, ("ayb", 1))
eq('"" ->. q', "ab", 1, ("qab", 1))
eq('a -> ""', "bab", 1, ("bb", 1))
eq('"a" ->. ""', "bab", 1, ("bb", 1))
eq('a\\b -> c', "xa\\by", 1, ("xcy", 1))
eq('a -> b\\', "a", 1, ("b\\", 1))
eq('a -> b\\n', "a", 1, ("b\\n", 1))
eq('"a" -> "b" ', "a", 1, ("b", 1))
eq('"a" ->."b"', "a", 1, ("b", 1))
eq('"a" ->. "b"', "a", 1, ("b", 1))
eq('"a"->"b"', "a", 1, ("b", 1))
eq('"a ->" -> b', "xa ->y", 1, ("xby", 1))
eq('"a ->" ->. "-> b"', "a ->", 1, ("-> b", 1))
for pr in ["a", "a - > b", "a > b", "a -", '"a -> b', 'a" -> b', '"a" x -> b', 'x "a" -> b', 'a -> "b" c', 'a -> c "b"',
           'a -> b"', 'a -> "b', '"a\\" -> b', 'a -> "b\\"', 'a -> "b\\q"', 'a -> "\\x41"', 'a -> "\\0"', 'a -> "b\\', '"" "" -> x',
           'a -> ""b""', 'a -> "x"y"', 'a -> "x" "y"', '"a"b" -> c', '"a\\"" b -> c', '-', '-> "', '"->', 'a\n b\n', 'a -> b\nzzz',
           'a -> b\n"x -> y', 'a -> b\n\n#c\nc d']:
    assert bad(pr, "zzz", 3), pr
    assert bad(pr, "", 0), pr
for a in [("a -> b", "a", -1), ("a -> b", "a", "1"), ("a -> b", "a", 1.0), ("a -> b", "a", None), ("a -> b", None, 1),
          (None, "a", 1), (b"a -> b", "a", 1), (["a -> b"], "a", 1), ("a -> b", b"a", 1)]:
    assert bad(*a), a
# limits and sizes
assert bad("a -> aa", "a", 20)
eq("a -> aa\n", "", 5, ("", 0))
assert bad("x -> xx", "x", 9999)
assert bad("x -> xx", "x", 10000)
assert bad("x -> xx", "x", 20000)
eq("x ->. y", "x" * 10000, 1, ("y" + "x" * 9999, 1))
assert bad("x ->. y", "x" * 10001, 1)
assert bad("x ->. y", "x" * 10001, 0)
eq("x ->. y", "z" * 10000, 0, ("z" * 10000, 0))
assert bad("", "z" * 10001, 0)
eq("x ->. xx", "x" * 9999, 1, ("x" * 10000, 1))
assert bad("x ->. xx", "x" * 10000, 1)
assert bad("a -> b\nbad", "zzz", 0)

# oracle: build rule lists, serialize them with random spelling, simulate with str.replace
def osim(rules, text, limit):
    if len(text) > 10000:
        raise ValueError
    steps = 0
    while True:
        k = next((i for i, (l, _, _) in enumerate(rules) if l in text), None)
        if k is None:
            return text, steps
        if steps >= limit:
            raise ValueError
        l, r, t = rules[k]
        text = text.replace(l, r, 1)
        steps += 1
        if len(text) > 10000:
            raise ValueError
        if t:
            return text, steps

def quoted(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'

def ser(rules):
    lines = []
    for l, r, t in rules:
        if random.random() < 0.15:
            lines.append(random.choice(["", "   ", "# " + random.choice(["x -> y", "a ->. b", '"', "->"]), "  #", "\t# a\\"]))
        sp1 = random.choice(["", " ", "  ", "\t"])
        sp2 = random.choice(["", " ", "  ", "\t"])
        lq = l != l.strip(" \t\r") or any(c in l for c in '"\n\t') or "->" in l or l.startswith("#") or random.random() < 0.2
        rq = (r != r.strip(" \t\r") or any(c in r for c in '"\n\t') or random.random() < 0.2
              or (not t and sp2 == "" and r.startswith(".")))
        lt = quoted(l) if lq else l
        rt = quoted(r) if rq else r
        line = random.choice(["", " ", "\t"]) + lt + sp1 + "->" + ("." if t else "") + sp2 + rt + random.choice(["", " ", "\t", "  "])
        lines.append(line)
    if random.random() < 0.3:
        lines.append("")
    return random.choice(["\n", "\n", "\r\n"]).join(lines)

random.seed(4012)
SPEC = list('"->. \\\n\t#')

def rstr(n, p):
    return "".join(random.choice("abc") if random.random() > p else random.choice(SPEC) for _ in range(n))

def rrules():
    n = random.randint(0, 5)
    rules = []
    shrink = random.random() < 0.6
    for _ in range(n):
        l = rstr(random.choice([0, 1, 1, 2, 2, 3]), random.choice([0, 0, 0.3]))
        if shrink and l:
            r = rstr(random.randint(0, len(l)), random.choice([0, 0.3]))
        else:
            r = rstr(random.randint(0, 4), random.choice([0, 0.3]))
        rules.append((l, r, random.random() < 0.25))
    return rules

nok = nerr = nterm = 0
for _ in range(260):
    rules = rrules()
    prog = ser(rules)
    text = rstr(random.randint(0, 9), random.choice([0, 0, 0.2]))
    limit = random.choice([0, 1, 2, 3, 5, 8, 20, 60, 300])
    try:
        exp = osim(rules, text, limit)
        nok += 1
        nterm += exp[1] > 0
    except ValueError:
        exp = ValueError
        nerr += 1
    try:
        got = markov_run(prog, text, limit)
    except ValueError:
        got = ValueError
    assert got == exp, (prog, text, limit, got, exp)
assert nok > 80 and nerr > 40 and nterm > 50, (nok, nerr, nterm)

# sorting / counting programs through the same path
for _ in range(40):
    s = "".join(random.choice("ab") for _ in range(random.randint(0, 25)))
    prog = random.choice(["ba -> ab", "ba->ab", "\nba\t->\tab\n"])
    n = sum(1 for i in range(len(s)) for j in range(i + 1, len(s)) if s[i] == "b" and s[j] == "a")
    eq(prog, s, 400, ("".join(sorted(s)), n))
    assert bad(prog, s, n - 1) if n else True
''', r'''
_WS = " \t\r"
_ESC = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}


def _split_arrow(line):
    inq = False
    i = 0
    while i < len(line):
        c = line[i]
        if inq:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                inq = False
        elif c == '"':
            inq = True
        elif line.startswith("->", i):
            return line[:i], line[i + 2:]
        i += 1
    raise ValueError("no arrow" if not inq else "unterminated quote")


def _pattern(s):
    if '"' not in s:
        return s
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise ValueError("bad quoting")
    inner = s[1:-1]
    out = []
    i = 0
    while i < len(inner):
        c = inner[i]
        if c == '"':
            raise ValueError("stray quote")
        if c == "\\":
            i += 1
            if i == len(inner) or inner[i] not in _ESC:
                raise ValueError("bad escape")
            c = _ESC[inner[i]]
        out.append(c)
        i += 1
    return "".join(out)


def _parse(program):
    rules = []
    for raw in program.split("\n"):
        line = raw.strip(_WS)
        if not line or line[0] == "#":
            continue
        left, right = _split_arrow(line)
        term = right.startswith(".")
        if term:
            right = right[1:]
        rules.append((_pattern(left.strip(_WS)), _pattern(right.strip(_WS)), term))
    return rules


def markov_run(program, text, limit):
    if not isinstance(program, str) or not isinstance(text, str):
        raise ValueError("program and text must be str")
    if type(limit) is not int or limit < 0:
        raise ValueError("bad limit")
    rules = _parse(program)
    if len(text) > 10000:
        raise ValueError("text too long")
    steps = 0
    while True:
        for lhs, rhs, term in rules:
            i = text.find(lhs)
            if i >= 0:
                break
        else:
            return text, steps
        if steps == limit:
            raise ValueError("step limit")
        text = text[:i] + rhs + text[i + len(lhs):]
        steps += 1
        if len(text) > 10000:
            raise ValueError("text too long")
        if term:
            return text, steps
''')

task("v4_13_load_properties", r'''
Write `load_properties(text)` that parses the text of a Java-style .properties file and returns a dict mapping str to str; a later entry replaces an earlier one with the same key. A `text` that is not a str raises ValueError, and so does any bad escape (below). Whitespace here means exactly space, tab and form feed ("\f"); "\n" and "\r" are never whitespace, and no other character is.
Lines. Natural lines end at "\n", "\r" or "\r\n" (that pair is one terminator; nothing else splits lines). A natural line that is empty or only whitespace is skipped. So is a comment: a line whose first non-whitespace character is "#" or "!". A comment never continues, whatever it ends with.
Any other line starts an entry. Remove its leading whitespace. While the current line ends in an odd number of backslashes (a run of backslashes at the very end of the line, nothing after it, odd length), drop the last backslash and append the next natural line with its leading whitespace removed; an appended line is never a comment, and may be empty or only whitespace, in which case it adds nothing and (not ending in a backslash) ends the entry. If the text ends right after such a backslash, the entry ends there. Trailing whitespace is never removed. The result is the logical line.
Key and value. The key starts at the first character of the logical line and ends at the first unescaped whitespace character, "=" or ":", or at the end of the line. A backslash escapes the character after it (the pair is skipped as a unit), so "\ ", "\=", "\:" and "\\" do not end the key. After the key skip whitespace; if the next character is "=" or ":", skip that one character and then skip whitespace again. The rest of the logical line is the value, possibly empty; its trailing whitespace stays. So "k : = v" has the value "= v", "k==v" has "=v", "k v" has "v", "k" and "k=" have "", "=v" has the key "" and ":" alone has key "" and value "".
Escapes. Split the logical line first, and only then process escapes in the key and in the value separately, so an escaped separator is part of the key and "\u003d" is a plain "=" that never separates. In order, scanning left to right: "\t", "\n", "\r", "\f" are TAB, LF, CR and FF. "\u" must be followed by exactly 4 characters from 0-9, a-f, A-F, else ValueError; they give one UTF-16 code unit. A high surrogate unit (D800-DBFF) must be followed immediately by another "\uXXXX" holding a low surrogate unit (DC00-DFFF); the two form one code point (U+10000 and up). Any other surrogate unit is a ValueError. Every other "\c" (including "\\", "\ ", "\#" and an upper case "\U") is just c, the backslash dropped. All other characters, non-ASCII included, are kept as they are.
Examples:
load_properties("a=1\nb : 2\nc 3\nd\n") == {"a": "1", "b": "2", "c": "3", "d": ""}
load_properties("k = a\\\n    b\\n\\u0041") == {"k": "ab\nA"}
load_properties("# c\\\nx\\ y=z") == {"x y": "z"}   (the comment does not continue)
load_properties("k=\\ud83d\\ude00") == {"k": "\U0001F600"}
''', r'''
import random

def bad(t):
    try:
        load_properties(t)
    except ValueError:
        return True
    return False

def eq(t, exp):
    got = load_properties(t)
    assert got == exp and type(got) is dict and all(type(k) is str and type(v) is str for k, v in got.items()), (t, got, exp)

eq("a=1\nb : 2\nc 3\nd\n", {"a": "1", "b": "2", "c": "3", "d": ""})
eq("k = a\\\n    b\\n\\u0041", {"k": "ab\nA"})
eq("# c\\\nx\\ y=z", {"x y": "z"})
eq("k=\\ud83d\\ude00", {"k": "\U0001F600"})
eq("", {})
eq("\n\r\n\r  \t\f\n", {})
eq("a=1\r\nb=2\rc=3\n", {"a": "1", "b": "2", "c": "3"})
eq("a=1\n\nb=2\r\n\r\nc=3\r\r", {"a": "1", "b": "2", "c": "3"})
eq("a=x\x0by\nb=\x1c\x85z\u2028w", {"a": "x\x0by", "b": "\x1c\x85z\u2028w"})
eq("a=1\x0cb=2", {"a": "1\x0cb=2"})
eq("k=v \n", {"k": "v "})
eq("k=v \t\f\n", {"k": "v \t\f"})
eq("k=\xa0v\xa0", {"k": "\xa0v\xa0"})
eq("k\xa0=v", {"k\xa0": "v"})
eq("  \t\fa = b", {"a": "b"})
eq("\f\fk\fv", {"k": "v"})
eq("k\v=x", {"k\v": "x"})
eq("k:v", {"k": "v"})
eq("k : v", {"k": "v"})
eq("k = = x", {"k": "= x"})
eq("k : = v", {"k": "= v"})
eq("k==v", {"k": "=v"})
eq("k::v", {"k": ":v"})
eq("k=:v", {"k": ":v"})
eq("k:=v", {"k": "=v"})
eq("k \t=\t v", {"k": "v"})
eq("k \t v", {"k": "v"})
eq("k\tv w x ", {"k": "v w x "})
eq("=v", {"": "v"})
eq(":", {"": ""})
eq("  = x", {"": "x"})
eq("k", {"k": ""})
eq("k   ", {"k": ""})
eq("k=", {"k": ""})
eq("k =  ", {"k": ""})
eq("a=1\na=2\nb=3\na=4", {"a": "4", "b": "3"})
# escapes in keys
eq("a\\ b=c", {"a b": "c"})
eq("a\\=b=c", {"a=b": "c"})
eq("a\\:b:c", {"a:b": "c"})
eq("a\\\\=b", {"a\\": "b"})
eq("a\\\\\\=b", {"a\\=b": ""})
eq("a\\\\\\\\=b", {"a\\\\": "b"})
eq("\\#k=v", {"#k": "v"})
eq("\\!k=v", {"!k": "v"})
eq("k#=v", {"k#": "v"})
eq("k!=v", {"k!": "v"})
eq("\\ k=v", {" k": "v"})
eq("\\\tk=v", {"\tk": "v"})
eq("\\u0041=1", {"A": "1"})
eq("a\\u003db=c", {"a=b": "c"})
eq("a\\u0020b c", {"a b": "c"})
eq("a\\tb\\nc=1", {"a\tb\nc": "1"})
eq("\\uD83D\\uDE00=v", {"\U0001F600": "v"})
# continuation
eq("k=a\\\n  b", {"k": "ab"})
eq("k=a\\\\\n  b", {"k": "a\\", "b": ""})
eq("k=a\\\\\\\n  b", {"k": "a\\b"})
eq("k=a\\\\\\\\\n  b", {"k": "a\\\\", "b": ""})
eq("k=a\\\n\n", {"k": "a"})
eq("k=a\\\n   \nj=1", {"k": "a", "j": "1"})
eq("k=a\\", {"k": "a"})
eq("k=a\\\n", {"k": "a"})
eq("k=a\\\r\n b", {"k": "ab"})
eq("k=a\\\r b", {"k": "ab"})
eq("k=a\\\r\n\r\nj=1", {"k": "a", "j": "1"})
eq("k\\\n =v", {"k": "v"})
eq("k\\\n  v", {"kv": ""})
eq("k=\\\n#x", {"k": "#x"})
eq("k=a\\\n!b\\\n  c", {"k": "a!bc"})
eq(" \\\n k=v", {"k": "v"})
eq("\\\nk=v", {"k": "v"})
eq("k=a \\\n b", {"k": "a b"})
eq("k=a\\ \\\n b", {"k": "a b"})
eq("k=a\\ \n b", {"k": "a ", "b": ""})
eq("k=a\\\n\\\n\\\nb", {"k": "ab"})
eq("k=\\u00\\\ne9", {"k": "\xe9"})
eq("k=\\u00\\\n  e9x", {"k": "\xe9x"})
eq("k=\\\\u0041", {"k": "\\u0041"})
eq("k=\\\\\\u0041", {"k": "\\A"})
# comments
eq("# c\\\nk=v", {"k": "v"})
eq("  ! x\nk=1", {"k": "1"})
eq("\t#\nk=1\n#", {"k": "1"})
eq("k=1 # not\nj=2", {"k": "1 # not", "j": "2"})
eq("#a=1\n!b=2\n c=3", {"c": "3"})
eq("k=a\\\n# b", {"k": "a# b"})
# escapes in values
eq("k=\\t\\n\\r\\f", {"k": "\t\n\r\f"})
eq("k=\\u0041\\u00e9\\u00E9", {"k": "A\xe9\xe9"})
eq("k=a\\u003db", {"k": "a=b"})
eq("k=\\u0000", {"k": "\0"})
eq("k=\\uFFFF\\uFFFE", {"k": "\uffff\ufffe"})
eq("k=\\ud83d\\ude00\\uD83D\\uDE00", {"k": "\U0001F600" * 2})
eq("k=\\uDBFF\\uDFFF", {"k": "\U0010FFFF"})
eq("k=\\uD800\\uDC00", {"k": "\U00010000"})
eq("k=\\U0041", {"k": "U0041"})
eq("k=\\q\\%\\a", {"k": "q%a"})
eq("k=\\\\", {"k": "\\"})
eq("k=\\ ", {"k": " "})
eq("k=\\  ", {"k": "  "})
eq("k=\\=", {"k": "="})
eq("k=a=b:c d", {"k": "a=b:c d"})
eq("k=\U0001F600\u00e9\u4e2d", {"k": "\U0001F600\u00e9\u4e2d"})
eq("\u00e9\u4e2d=\u00e9", {"\u00e9\u4e2d": "\u00e9"})
eq("k=\\u00e9\\\n\\u00e9", {"k": "\xe9\xe9"})
for b in ["k=\\ud83d", "k=\\ude00", "k=\\ud83dx", "k=\\ud83d\\u0041", "k=\\ud83d\\ud83d", "k=\\ude00\\ud83d", "k=\\ud83d\\\\ude00",
          "k=\\ud83d\\ude0", "k=\\ud83dxxdc00", "k=\\ud83d\\\\udc00", "k=\\ud83d\\xdc00", "k=\\u12", "k=\\u", "k=\\u12G4", "k=\\u+123", "k=\\u 123", "k=\\u12_3", "k=\\u-123", "k=\\u0x41", "k=\\u\uff11\uff10\uff10\uff10",
          "k=\\u00e", "k=\\ube", "\\u00zz=1", "\\ud800=1", "k=\\uDC00\\uDC00", "k=\\u\u0661\u0662\u0663\u0664", "k=\\u004\n1",
          "a=1\nk=\\u12\nb=2", "k=\\ud83d\\\n\\ude00x\\u1"]:
    assert bad(b), b
eq("k=\\ud83d\\\n\\ude00", {"k": "\U0001F600"})
eq("k=\\ud83d\\\n  \\ude00", {"k": "\U0001F600"})
assert bad("k=\\ud83d\n\\ude00")
assert bad("k=\\u004\n1")
for t in [None, b"a=b", ["a=b"], 5, {"a": "b"}, bytearray(b"a")]:
    assert bad(t), t

# oracle: build random entries from known keys/values, write them in a random spelling, expect the dict
random.seed(4013)

def uesc(cu):
    h = "%04x" % cu
    return "\\u" + (h.upper() if random.random() < 0.5 else h)

def tokens(s, is_key, ws_sep=False):
    toks = []
    for n, ch in enumerate(s):
        o = ord(ch)
        first = n == 0
        if ch == "\t":
            t = random.choice(["\\t", "\\u0009"])
        elif ch == "\n":
            t = random.choice(["\\n", "\\u000a"])
        elif ch == "\r":
            t = random.choice(["\\r", "\\u000d"])
        elif ch == "\f":
            t = random.choice(["\\f", "\\u000c"])
        elif ch == "\\":
            t = random.choice(["\\\\", "\\\\", "\\u005c"])
        elif ch == " ":
            t = random.choice(["\\ ", "\\u0020"]) if (is_key or first or random.random() < 0.3) else " "
        elif ch in "=:":
            t = random.choice(["\\" + ch, uesc(o)]) if (is_key or (first and ws_sep) or random.random() < 0.3) else ch
        elif ch in "#!":
            t = ch if (not first and random.random() < 0.7) else random.choice(["\\" + ch, uesc(o)])
        elif o > 0xFFFF:
            v = o - 0x10000
            t = ch if random.random() < 0.5 else uesc(0xD800 + (v >> 10)) + uesc(0xDC00 + (v & 0x3FF))
        elif o > 127:
            t = ch if random.random() < 0.6 else uesc(o)
        elif ch in "tnrfu":
            t = ch if random.random() < 0.9 else uesc(o)
        else:
            t = random.choice([ch, ch, ch, "\\" + ch, uesc(o)])
        toks.append(t)
    return toks

ALPHA = list("abcXY01 =:#!\\\t\n\f\r.-_/") + ["\xe9", "\u4e2d", "\U0001F600", "\xa0", "\x0b", "\x1c", "\x85", "\u2028", "\U00010000", "\U0010FFFF"]
KEYPOOL = []

def rtext(lo, hi, special=0.5):
    n = random.randint(lo, hi)
    return "".join(random.choice(ALPHA) if random.random() < special else random.choice("abcdefgxyz") for _ in range(n))

WS = " \t\f"

def entry_text(k, v):
    kinds = random.choice(["ws", "eq", "eq", "colon", "none"])
    if kinds == "none" and v:
        kinds = "eq"
    if not k and kinds in ("ws", "none"):
        kinds = "eq"
    kt = tokens(k, True)
    vt = tokens(v, False, kinds in ("ws", "none"))
    if kinds == "none":
        sep = []
    elif kinds == "ws":
        sep = [random.choice(WS) for _ in range(random.randint(1, 3))]
    else:
        sep = [random.choice(WS) for _ in range(random.choice([0, 0, 1, 2]))] if k else []
        sep += ["=" if kinds == "eq" else ":"]
        sep += [random.choice(WS) for _ in range(random.choice([0, 0, 1, 2]))]
    toks = kt + sep + vt
    out = [toks[0]] if toks else [""]
    for i in range(1, len(toks)):
        t = toks[i]
        if random.random() < 0.12 and t[0] not in WS:
            out.append("\\" + random.choice(["\n", "\r\n", "\r"]) + random.choice(["", "", " ", "\t", "  \f"]))
        out.append(t)
    line = "".join(out)
    if random.random() < 0.08:
        tail = random.choice(["", " ", "\t\f"])
        line += "\\" + random.choice(["\n", "\r\n"] if not tail else ["\n", "\r\n", "\r"]) + tail
        return line, True
    return line, False

def build(nent):
    exp = {}
    parts = []
    for _ in range(nent):
        if random.random() < 0.3:
            c = random.choice(["", " ", "\t", "\f "]) + random.choice(["#", "!"]) + rtext(0, 6, 0.2).replace("\n", "x").replace("\r", "y")
            if random.random() < 0.4:
                c += "\\"
            parts.append(c)
        if random.random() < 0.2:
            parts.append(random.choice(["", " ", "\t\f"]))
        if KEYPOOL and random.random() < 0.3:
            k = random.choice(KEYPOOL)
        else:
            k = rtext(0, 5)
            KEYPOOL.append(k)
        v = rtext(0, 9)
        exp[k] = v
        line, tail_blank = entry_text(k, v)
        parts.append(line)
    text = ""
    for i, ln in enumerate(parts):
        text += ln
        if i < len(parts) - 1 or random.random() < 0.5:
            text += random.choice(["\n", "\r\n", "\r"])
    return text, exp

n_nonempty = 0
for _ in range(230):
    KEYPOOL.clear()
    text, exp = build(random.randint(0, 7))
    got = load_properties(text)
    assert got == exp, (text, got, exp)
    n_nonempty += bool(exp)
assert n_nonempty > 150

# every random text with one corrupted escape must fail
for _ in range(40):
    KEYPOOL.clear()
    text, exp = build(random.randint(1, 4))
    bad_text = text + random.choice(["\nz=\\u12", "\nz=\\ud800", "\nz=\\u12x4", "\n\\udc00=z", "\nz=\\ud83d\\u0041"])
    assert bad(bad_text), bad_text
''', r'''
_WS = " \t\f"
_HEX = "0123456789abcdefABCDEF"


def _lines(text):
    out = []
    cur = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\n" or c == "\r":
            out.append("".join(cur))
            cur = []
            if c == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
        else:
            cur.append(c)
        i += 1
    if cur:
        out.append("".join(cur))
    return out


def _unescape(raw):
    out = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        d = raw[i]
        i += 1
        if d == "t":
            out.append("\t")
        elif d == "n":
            out.append("\n")
        elif d == "r":
            out.append("\r")
        elif d == "f":
            out.append("\f")
        elif d == "u":
            cu, i = _unit(raw, i)
            if 0xD800 <= cu <= 0xDBFF:
                if raw[i:i + 2] != "\\u":
                    raise ValueError("lone high surrogate")
                lo, i = _unit(raw, i + 2)
                if not 0xDC00 <= lo <= 0xDFFF:
                    raise ValueError("bad low surrogate")
                cu = 0x10000 + ((cu - 0xD800) << 10) + (lo - 0xDC00)
            elif 0xDC00 <= cu <= 0xDFFF:
                raise ValueError("lone low surrogate")
            out.append(chr(cu))
        else:
            out.append(d)
    return "".join(out)


def _unit(raw, i):
    h = raw[i:i + 4]
    if len(h) != 4 or any(ch not in _HEX for ch in h):
        raise ValueError("bad \\u escape")
    return int(h, 16), i + 4


def load_properties(text):
    if not isinstance(text, str):
        raise ValueError("text must be str")
    lines = _lines(text)
    result = {}
    i = 0
    while i < len(lines):
        s = lines[i].lstrip(_WS)
        i += 1
        if not s or s[0] in "#!":
            continue
        while True:
            run = len(s) - len(s.rstrip("\\"))
            if run % 2 == 0:
                break
            s = s[:-1]
            if i >= len(lines):
                break
            s += lines[i].lstrip(_WS)
            i += 1
        n = len(s)
        j = 0
        while j < n and s[j] not in _WS and s[j] not in "=:":
            j += 2 if s[j] == "\\" else 1
        key = s[:j]
        j = min(j, n)
        while j < n and s[j] in _WS:
            j += 1
        if j < n and s[j] in "=:":
            j += 1
            while j < n and s[j] in _WS:
                j += 1
        result[_unescape(key)] = _unescape(s[j:])
    return result
''')

task("v4_14_ustar_entries", r'''
Write `ustar_entries(data)` that lists the entries of a POSIX ustar archive held in `data` (`bytes` or `bytearray`, else ValueError). It returns a list of tuples `(name, kind, size)` in archive order: name a str, kind one of "file", "dir", "symlink", "hardlink", size an int. Every failure raises ValueError. The archive is a sequence of 512-byte blocks.
Header block layout (byte offsets, end excluded): name 0-100, mode 100-108, uid 108-116, gid 116-124, size 124-136, mtime 136-148, checksum 148-156, typeflag 156-157, linkname 157-257, magic 257-263, version 263-265, uname 265-297, gname 297-329, devmajor 329-337, devminor 337-345, prefix 345-500, unused 500-512. The fields mode, uid, gid, mtime, linkname, uname, gname, devmajor, devminor and the unused bytes are ignored (never checked) but they are part of the checksum.
Reading starts at offset 0. At each header position look at the next 512 bytes:
- If fewer than 512 bytes remain (none included), ValueError. So data that ends at a header position without an end marker is an error, and so is empty data.
- A block of 512 zero bytes is a zero block. The first zero block must be followed immediately by a second full zero block, else ValueError. The archive then ends and everything after those two blocks is ignored. The result is the list so far.
- Any other block is a header. Its magic must be exactly b"ustar\x00" and its version exactly b"00", else ValueError. The checksum field must hold the sum of all 512 header bytes, taken as unsigned values, with the 8 checksum-field bytes counted as 0x20 each; a different value is a ValueError.
- Octal fields (size and checksum): drop leading spaces (0x20), then there must be at least one ASCII octal digit 0-7 and the value is those digits read in base 8 (no sign, no prefix, no other digit); after the digits only NUL or space bytes may follow, up to the end of the field. Anything else is a ValueError. A field may be entirely filled by digits.
- typeflag: b"0" or a NUL byte is a regular file (kind "file"), b"5" a "dir", b"2" a "symlink", b"1" a "hardlink". Any other byte is a ValueError.
- Text fields (name, prefix): the bytes before the first NUL (or the whole field if it has none), decoded as UTF-8 strictly (invalid is a ValueError). If the name field is empty it is a ValueError, even with a prefix. The entry name is prefix + "/" + name when the prefix is not empty, else name; it is returned exactly as stored (a trailing "/" stays).
- Data: after the header of a "file", `size` data bytes follow, padded to a multiple of 512 with arbitrary bytes; all of those blocks must be present, else ValueError. The next header is right after them. A "dir", "symlink" or "hardlink" has no data blocks whatever its size field says (the field must still be a valid octal field), and its reported size is 0. A "file" reports the size field.
Example: a header with name b"a", size field b"00000000003\x00", typeflag b"0", magic b"ustar\x00", version b"00", everything else NUL, has checksum sum 1587 = 0o3063, so its field may read b"003063\x00 ", b"  3063 \x00", b"00003063" and so on. That header, then b"xyz" + 509 NULs, then 1024 NULs gives [("a", "file", 3)].
''', r'''
import io, random, tarfile

Z = bytes(512)

def seal(h, spell=None):
    h = bytearray(h)
    h[148:156] = b" " * 8
    s = sum(h)
    h[148:156] = spell(s) if spell else ("%06o" % s).encode() + b"\0 "
    assert len(h) == 512
    return bytes(h)

def hdr(name=b"a", size=b"00000000000\0", flag=b"0", prefix=b"", magic=b"ustar\0", ver=b"00", spell=None, extra=None):
    assert len(name) <= 100 and len(size) <= 12 and len(prefix) <= 155
    h = bytearray(512)
    h[0:len(name)] = name
    h[124:124 + len(size)] = size
    h[156:157] = flag
    h[257:263] = magic
    h[263:265] = ver
    h[345:345 + len(prefix)] = prefix
    for off, val in (extra or {}).items():
        h[off:off + len(val)] = val
    return seal(h, spell)

def blocks(d):
    return d + bytes(-len(d) % 512)

END = Z + Z

def bad(d):
    try:
        ustar_entries(d)
    except ValueError:
        return True
    return False

def eq(d, exp):
    got = ustar_entries(d)
    assert got == exp and type(got) is list and all(type(x) is tuple and type(x[0]) is str and type(x[1]) is str and type(x[2]) is int for x in got), (got, exp)

# the example in the statement
h = hdr(b"a", b"00000000003\0")
assert h[148:156] == b"003063\0 "
eq(h + blocks(b"xyz") + END, [("a", "file", 3)])
for sp in [b"003063\0 ", b"  3063 \0", b"00003063", b" 003063 ", b"3063\0\0\0\0", b"3063    ", b"0003063\0", b"    3063"]:
    eq(hdr(b"a", b"00000000003\0", spell=lambda s: sp) + blocks(b"xyz") + END, [("a", "file", 3)])
eq(END, [])
eq(END + b"junk", [])
eq(END + Z + Z, [])
eq(END + h + b"x", [])
assert bad(b"")
assert bad(Z)
assert bad(Z + bytes(511))
assert bad(bytes(100))
assert bad(Z + h)
assert bad(Z + hdr(b"b") + END)
assert bad(Z + b"\1" + bytes(511))
assert bad(bytes(511) + b"\1" + END)
assert bad(bytes(300) + b"x" + bytes(211) + END)
assert bad(bytes(300) + b"\1" + bytes(211) + END)
assert bad(h + blocks(b"xyz"))
assert bad(h + blocks(b"xyz") + Z)
assert bad(h + blocks(b"xyz") + Z + bytes(511))
assert bad(h + blocks(b"xyz") + Z + b"\0" * 400 + b"\1" + b"\0" * 111)
assert bad(h + blocks(b"xyz")[:511])
assert bad(h)
assert bad(h[:511])
assert bad(h[:511] + END)
eq(bytearray(h + blocks(b"xyz") + END), [("a", "file", 3)])
for t in ["x", None, 5, [h], memoryview(END), (h,)]:
    assert bad(t), t
# sizes and padding
for n in [0, 1, 511, 512, 513, 1024, 1025]:
    d = hdr(b"f", ("%011o" % n).encode() + b"\0") + blocks(b"q" * n) + END
    eq(d, [("f", "file", n)])
    if n:
        k = (n + 511) // 512 * 512
        full = hdr(b"f", ("%011o" % n).encode() + b"\0") + b"q" * k
        assert bad(full[:512 + k - 1])
        assert bad(full)
        eq(full + END, [("f", "file", n)])
assert bad(hdr(b"f", b"00000000001\0") + END[:512])
eq(hdr(b"f", b"00000000001\0") + Z + END, [("f", "file", 1)])
eq(hdr(b"f", b"00000000001\0") + b"\1" * 512 + END, [("f", "file", 1)])
eq(hdr(b"f", b"0000000000\0\0") + END, [("f", "file", 0)])
assert bad(hdr(b"f", b"77777777777\0") + END)
assert bad(hdr(b"f", b"777777777777") + END)
# links and directories carry no data
eq(hdr(b"d/", b"00000000000\0", b"5") + END, [("d/", "dir", 0)])
eq(hdr(b"d", b"00000001750\0", b"5") + END, [("d", "dir", 0)])
eq(hdr(b"l", b"00000001750\0", b"2", extra={157: b"target"}) + hdr(b"h", b"77777777777\0", b"1", extra={157: b"l"}) + END,
   [("l", "symlink", 0), ("h", "hardlink", 0)])
assert bad(hdr(b"d", b"garbage", b"5") + END)
assert bad(hdr(b"d", b"", b"5") + END)
assert bad(hdr(b"l", b"8", b"2") + END)
# typeflag
eq(hdr(b"x", flag=b"\0") + END, [("x", "file", 0)])
eq(hdr(b"x", b"00000000002\0", flag=b"\0") + blocks(b"ab") + hdr(b"y", flag=b"0") + END, [("x", "file", 2), ("y", "file", 0)])
for fl in [b"3", b"4", b"6", b"7", b"x", b"g", b"L", b"K", b"A", b"S", b"D", b"M", b"V", b" ", b"\xff", b"/", b"a", b"\1"]:
    assert bad(hdr(b"x", flag=fl) + END), fl
# magic and version
for mg, vr in [(b"ustar ", b" \0"), (b"ustar ", b"00"), (b"ustar\0", b"  "), (b"ustar\0", b"0\0"), (b"ustar\0", b"01"), (b"ustar\0", b"\0\0"),
               (b"USTAR\0", b"00"), (b"ustar\0", b"10"), (b"\0" * 6, b"00"), (b"ustar\0", b"\0\0"), (b"ustaR\0", b"00"), (b"ustar1", b"00"), (b"\0" * 6, b"\0\0")]:
    assert bad(hdr(b"x", magic=mg, ver=vr) + END), (mg, vr)
# checksum
for sp in [b"003062\0 ", b"003064\0 ", b"        ", b"\0" * 8, b"003063x ", b"00306 3\0", b"003063 3", b"00308\0\0\0", b"-003063 ", b"+003063 ", b"0o3063\0 ",
           b"3063\0 \0x", b"\x00003063 ", b"003063\t\0", b"0x3063\0\0", b"003063\n\0", b"\xff003063\0"]:
    assert bad(hdr(b"a", b"00000000003\0", spell=lambda s: sp) + blocks(b"xyz") + END), sp
# checksum: signed bytes, and a checksum computed over the field as it stands
raw = bytearray(hdr(b"a" + b"\xc3\xa9", b"00000000000\0"))
assert bytes(raw[148:156]) != b" " * 8
eq(bytes(raw) + END, [("a\xe9", "file", 0)])
signed = bytearray(raw)
s = sum(x - 256 if x > 127 else x for x in (bytes(signed[:148]) + b" " * 8 + bytes(signed[156:])))
signed[148:156] = ("%06o" % s).encode() + b"\0 "
assert bytes(signed) != bytes(raw)
assert bad(bytes(signed) + END)
filled = bytearray(hdr(b"a"))
filled[148:156] = b"0" * 8
assert bad(bytes(filled) + END) or sum(filled[:148]) + 256 + sum(filled[156:]) == 0
# size forms
for sz, v in [(b"00000000012\0", 10), (b"          12", 10), (b"12\0\0\0\0\0\0\0\0\0\0", 10), (b"12          ", 10), (b"  12        ", 10), (b"00000000012 ", 10),
              (b"0000000001 \0", 1), (b"1\0 \0 \0 \0 \0 ", 1), (b"000000000012", 10), (b"0\0\0\0\0\0\0\0\0\0\0\0", 0), (b"0           ", 0), (b"00000000000\0", 0)]:
    eq(hdr(b"f", sz) + blocks(b"z" * v) + END, [("f", "file", v)])
for sz in [b"", b"\0" * 12, b" " * 12, b"00000000008\0", b"0000000001a\0", b"1 2\0\0\0\0\0\0\0\0\0", b"-0000000001\0", b"+0000000001\0", b"0000000001\0x",
           b"\0" + b"1" * 11, b"1\0" + b"1" * 10, b"0x0000000001", b"0o0000000001", b"\x80" + b"\0" * 11, b"1e1\0\0\0\0\0\0\0\0\0", b"0000000001.\0", b"0000000001\n\0", b"0000000001\t "]:
    assert bad(hdr(b"f", sz) + blocks(b"z" * 8) + END), sz
# names
eq(hdr(b"dir/sub/file.txt") + END, [("dir/sub/file.txt", "file", 0)])
eq(hdr(b"n", prefix=b"p") + END, [("p/n", "file", 0)])
eq(hdr(b"n", prefix=b"a/b/c") + END, [("a/b/c/n", "file", 0)])
eq(hdr(b"n/", prefix=b"a/", flag=b"5") + END, [("a//n/", "dir", 0)])
eq(hdr(b"n", prefix=b"\0" + b"zz") + END, [("n", "file", 0)])
eq(hdr(b"n", prefix=b"\xc3\xa9") + END, [("\xe9/n", "file", 0)])
eq(hdr(b"\xe4\xb8\xad\xe6\x96\x87") + END, [("中文", "file", 0)])
eq(hdr(b"\xf0\x9f\x98\x80") + END, [("\U0001F600", "file", 0)])
eq(hdr(b"ab\0cd") + END, [("ab", "file", 0)])
eq(hdr(b"x" * 100) + END, [("x" * 100, "file", 0)])
eq(hdr(b"x" * 100, prefix=b"y" * 155) + END, [("y" * 155 + "/" + "x" * 100, "file", 0)])
eq(hdr(b"n", extra={345: b"\0y"}) + END, [("n", "file", 0)])
assert bad(hdr(b"") + END)
assert bad(hdr(b"", prefix=b"p") + END)
assert bad(hdr(b"\0abc") + END)
for nm in [b"\xff", b"a\xc3", b"\xc3(", b"\xed\xa0\x80", b"\xc0\x80", b"\xf8\x88\x80\x80\x80", b"\xe2\x82", b"ok\xfe"]:
    assert bad(hdr(nm) + END), nm
    assert bad(hdr(b"ok", prefix=nm) + END), nm
eq(hdr(b"ok", extra={2: b"\0\xff"}) + END, [("ok", "file", 0)])
eq(hdr(b"ok", extra={345 + 10: b"\xff", 497: b"\xff\xfe"}) + END, [("ok", "file", 0)])
# ignored fields hold anything
junk = {100: b"\xff" * 8, 108: b"zz\x01", 116: b"\x80" * 8, 136: b"not octal!!!!", 157: b"\xff" * 100, 265: b"\xfe" * 32, 297: b"\xfd" * 32, 329: b"\xfc" * 16,
        500: b"\xfb" * 12}
eq(hdr(b"a", extra=junk) + END, [("a", "file", 0)])
eq(hdr(b"a", extra=junk) + hdr(b"b", b"00000000001\0", extra=junk) + blocks(b"q") + END + b"\xff" * 1000, [("a", "file", 0), ("b", "file", 1)])
# flipped header byte (outside the checksum field) always fails
d = bytearray(hdr(b"a", extra=junk) + END)
for off in [0, 5, 99, 100, 124, 130, 135, 136, 147, 156, 157, 256, 257, 262, 263, 264, 265, 344, 345, 499, 500, 511]:
    e = bytearray(d)
    e[off] ^= 0x01
    assert bad(bytes(e)), off
# duplicates and order
eq(hdr(b"a") + hdr(b"a") + END, [("a", "file", 0), ("a", "file", 0)])

# oracle: archives written by tarfile (USTAR_FORMAT), expected list recorded while writing
random.seed(4014)
PARTS = ["a", "bb", "dir", "x y", "\xe9t\xe9", "中", "n" * 30, "q" * 60, "v-1.2_z", "0"]

def rname():
    k = random.choice([1, 1, 2, 3, 5])
    return "/".join(random.choice(PARTS) for _ in range(k))

def build():
    bio = io.BytesIO()
    exp = []
    with tarfile.open(fileobj=bio, mode="w", format=tarfile.USTAR_FORMAT, encoding="utf-8") as tf:
        for _ in range(random.randint(0, 6)):
            name = rname()
            if random.random() < 0.15:
                name = "/".join([random.choice(PARTS[5:8]) for _ in range(random.randint(3, 5))]) + "/" + name
            k = random.choice(["file", "file", "file", "dir", "symlink", "hardlink"])
            ti = tarfile.TarInfo(name)
            ti.mtime = random.randrange(10 ** 9)
            ti.mode = random.choice([0o644, 0o755, 0o600])
            ti.uname = random.choice(["", "root", "user"])
            data = b""
            if k == "file":
                data = bytes(random.randrange(256) for _ in range(random.choice([0, 1, 7, 100, 511, 512, 513, 1024, 1300])))
                ti.size = len(data)
            elif k == "dir":
                ti.type = tarfile.DIRTYPE
            else:
                ti.type = tarfile.SYMTYPE if k == "symlink" else tarfile.LNKTYPE
                ti.linkname = random.choice(PARTS)
            try:
                tf.addfile(ti, io.BytesIO(data) if k == "file" else None)
            except ValueError:
                continue
            exp.append((name + "/" if k == "dir" else name, k, len(data)))
    return bio.getvalue(), exp

def spell_size(n):
    f = random.choice([("%011o" % n).encode() + b"\0", ("%011o" % n).encode() + b" ", (" " * random.randint(0, 5) + "%o" % n).encode(),
                       ("%012o" % n).encode(), ("%o" % n).encode()])
    return f.ljust(12, random.choice([b"\0", b" "])) if len(f) < 12 else f

def respell(a, exp):
    """Re-encode every header with legal alternative spellings and random junk in the ignored fields."""
    out = bytearray()
    pos = 0
    for name, k, sz in exp:
        h = bytearray(a[pos:pos + 512])
        n_field = bytes(h[124:136]).strip(b"\0 ")
        if k == "file" or random.random() < 0.5:
            h[124:136] = spell_size(int(n_field, 8))
        if k == "file" and random.random() < 0.3:
            h[156:157] = b"\0"
        for off, ln in [(100, 8), (108, 8), (116, 8), (136, 12), (265, 32), (297, 32), (329, 16), (500, 12)]:
            if random.random() < 0.4:
                h[off:off + ln] = bytes(random.randrange(256) for _ in range(ln))
        nm = bytes(h[0:100]).split(b"\0")[0]
        if len(nm) < 100 and random.random() < 0.3:
            h[len(nm):100] = b"\0" + bytes(random.randrange(1, 256) for _ in range(99 - len(nm)))
        pre = bytes(h[345:500]).split(b"\0")[0]
        if len(pre) < 155 and random.random() < 0.3:
            h[345 + len(pre):500] = b"\0" + bytes(random.randrange(1, 256) for _ in range(154 - len(pre)))
        out += seal(h, random.choice([None, lambda s: ("%6o\0 " % s).encode(), lambda s: ("%08o" % s).encode(), lambda s: (" %6o\0" % s).encode(),
                                      lambda s: ("%07o\0" % s).encode(), lambda s: ("%-6o\0 " % s).encode(), lambda s: ("%-8o" % s).encode()]))
        pos += 512
        if k == "file":
            ln = (sz + 511) // 512 * 512
            body = bytearray(a[pos:pos + ln])
            if sz < ln and random.random() < 0.5:
                body[sz:] = bytes(random.randrange(256) for _ in range(ln - sz))
            out += body
            pos += ln
    return bytes(out), pos

def entries_end(exp):
    return sum(512 + ((s + 511) // 512 * 512 if k == "file" else 0) for _, k, s in exp)

nonempty = 0
nbad = 0
for _ in range(110):
    a, exp = build()
    assert a[entries_end(exp):entries_end(exp) + 1024] == END
    eq(a, [tuple(x) for x in exp])
    nonempty += bool(exp)
    if exp:
        r, end = respell(a, exp)
        assert end == entries_end(exp)
        full = r + END + bytes(random.choice([0, 3, 512, 9000]))
        eq(full, [tuple(x) for x in exp])
        full = r + END + bytes(random.randrange(256) for _ in range(random.choice([1, 100, 2000])))
        eq(full, [tuple(x) for x in exp])
        # cuts before the end marker are errors, cuts after it are fine
        cut = random.randrange(0, end + 1024)
        assert bad(full[:cut]), (cut, end)
        cut2 = random.randrange(end + 1024, len(full) + 1)
        eq(full[:cut2], [tuple(x) for x in exp])
        # one flipped byte in a random header
        offs = []
        p = 0
        for _n, k, s in exp:
            offs.append(p)
            p += 512 + ((s + 511) // 512 * 512 if k == "file" else 0)
        hp = random.choice(offs)
        o = random.choice([x for x in range(512) if not 148 <= x < 156])
        e = bytearray(r + END)
        e[hp + o] = (e[hp + o] + random.randrange(1, 256)) % 256
        assert bad(bytes(e)), (hp, o)
        nbad += 1
        # a second end block that is not zero
        assert bad(r + Z + hdr(b"late")) and bad(r + Z + b"\0" * 511 + b"\1" + END)
assert nonempty > 70 and nbad > 70
''', r'''
_KINDS = {b"0": "file", b"\x00": "file", b"5": "dir", b"2": "symlink", b"1": "hardlink"}
_ZERO = bytes(512)


def _octal(field):
    f = field.lstrip(b" ")
    i = 0
    while i < len(f) and 0x30 <= f[i] <= 0x37:
        i += 1
    if i == 0 or f[i:].strip(b"\x00 "):
        raise ValueError("bad octal field")
    return int(f[:i], 8)


def _text(field):
    return field.split(b"\x00", 1)[0].decode("utf-8")


def ustar_entries(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    data = bytes(data)
    n = len(data)
    pos = 0
    out = []
    while True:
        if pos + 512 > n:
            raise ValueError("truncated archive")
        blk = data[pos:pos + 512]
        if blk == _ZERO:
            if data[pos + 512:pos + 1024] == _ZERO:
                return out
            raise ValueError("missing second zero block")
        if blk[257:263] != b"ustar\x00" or blk[263:265] != b"00":
            raise ValueError("bad magic")
        if _octal(blk[148:156]) != sum(blk[:148]) + 256 + sum(blk[156:]):
            raise ValueError("bad checksum")
        size = _octal(blk[124:136])
        kind = _KINDS.get(blk[156:157])
        if kind is None:
            raise ValueError("bad typeflag")
        name = _text(blk[0:100])
        prefix = _text(blk[345:500])
        if not name:
            raise ValueError("empty name")
        if prefix:
            name = prefix + "/" + name
        pos += 512
        if kind == "file":
            pos += (size + 511) // 512 * 512
            if pos > n:
                raise ValueError("truncated data")
        else:
            size = 0
        out.append((name, kind, size))
''')

task("v4_15_msgpack_loads", r'''
Write `msgpack_loads(data)` that decodes exactly one MessagePack value from `data` (`bytes` or `bytearray`, else ValueError) and returns it. Every failure raises ValueError. Multi-byte numbers and lengths are big-endian. The first byte `b` of a value selects its type:
- 0x00-0x7f: the int b. 0xe0-0xff: the int b - 256.
- 0x80-0x8f: a map with (b & 0x0f) entries. 0x90-0x9f: an array with (b & 0x0f) elements. 0xa0-0xbf: a str of (b & 0x1f) bytes.
- 0xc0: None. 0xc2: False. 0xc3: True.
- 0xc4, 0xc5, 0xc6: bin; a 1, 2 or 4 byte length follows, then that many bytes, returned as `bytes`.
- 0xca: float32, 0xcb: float64, both returned as a Python float (a float32 is widened exactly).
- 0xcc, 0xcd, 0xce, 0xcf: unsigned int of 1, 2, 4, 8 bytes. 0xd0, 0xd1, 0xd2, 0xd3: signed (two's complement) int of 1, 2, 4, 8 bytes.
- 0xd9, 0xda, 0xdb: str; a 1, 2 or 4 byte length follows, then that many bytes.
- 0xdc, 0xdd: array; a 2 or 4 byte element count follows, then the elements. 0xde, 0xdf: map; a 2 or 4 byte entry count follows, then key, value, key, value and so on.
- 0xc1 (never used), 0xc7-0xc9 and 0xd4-0xd8 (the ext types) are a ValueError.
Rules:
- Non-minimal encodings are valid: the int 5 may be 0xcf followed by eight bytes, a 3-byte str may use 0xdb, and so on. Ints are returned as int, whatever their encoded width; floats NaN and infinity are allowed.
- Every str payload must be valid UTF-8 (strict: no overlong forms, no surrogates, nothing above U+10FFFF), else ValueError.
- A map is returned as a dict in wire order. Its keys must be a str or an int (a bool is not accepted); a key that is None, bool, float, bytes, an array or a map is a ValueError. Two equal keys (same type and value) in one map are a ValueError; the int 1 and the str "1" are different keys.
- `data` must hold exactly one value: empty data, a missing byte anywhere (header, length, payload, element, key or value), or any byte left after the value is a ValueError.
- A count or length that claims more than the data can still hold must fail without allocating for it: an array count larger than the number of bytes left, or a map entry count whose 2 * count is larger, or a str or bin length larger than the bytes left, is a ValueError (a 10-byte input with a 4-billion-element array header must not allocate anything).
- At most 16 arrays and maps may be open (nested in each other) at once: 16 nested arrays are fine, 17 are a ValueError, even if the innermost is empty.
Examples (hex):
82 a1 61 01 a1 62 c3 -> {"a": 1, "b": True}
93 01 ce 00000002 a1 78 -> [1, 2, "x"]
cb 3ff0000000000000 -> 1.0; c0 c0 -> ValueError (a byte is left); 81 c0 01 -> ValueError (None key)
''', r'''
import math, random, struct

def bad(d):
    try:
        msgpack_loads(d)
    except ValueError:
        return True
    return False

def same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, float):
        return (a == b and math.copysign(1.0, a) == math.copysign(1.0, b)) or (a != a and b != b)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return len(a) == len(b) and all(same(k, l) and same(a[k], b[l]) for k, l in zip(a, b))
    return a == b

def eq(h, exp):
    d = bytes.fromhex(h) if isinstance(h, str) else h
    got = msgpack_loads(d)
    assert same(got, exp), (h if isinstance(h, str) else d[:40], got, exp)
    got = msgpack_loads(bytearray(d))
    assert same(got, exp)

def B(h):
    return bytes.fromhex(h)

eq("82 a1 61 01 a1 62 c3", {"a": 1, "b": True})
eq("93 01 ce 00000002 a1 78", [1, 2, "x"])
eq("cb 3ff0000000000000", 1.0)
assert bad(B("c0c0"))
assert bad(B("81c001"))
eq("c0", None); eq("c2", False); eq("c3", True)
assert bad(b"")
assert bad(bytearray())
for t in ["c0", None, 5, [1], (1,), memoryview(b"\xc0"), 1.5]:
    assert bad(t), t
# fixints
eq("00", 0); eq("7f", 127); eq("e0", -32); eq("ff", -1); eq("f0", -16); eq("01", 1); eq("e1", -31)
# sized ints
eq("cc 00", 0); eq("cc ff", 255); eq("cd 0100", 256); eq("cd ffff", 65535); eq("ce 00010000", 65536); eq("ce ffffffff", 2 ** 32 - 1)
eq("cf 0000000100000000", 2 ** 32); eq("cf ffffffffffffffff", 2 ** 64 - 1); eq("cf 0000000000000005", 5); eq("cf 8000000000000000", 2 ** 63)
eq("d0 80", -128); eq("d0 7f", 127); eq("d0 ff", -1); eq("d0 00", 0); eq("d1 8000", -32768); eq("d1 7fff", 32767); eq("d1 ffff", -1)
eq("d2 80000000", -2 ** 31); eq("d2 7fffffff", 2 ** 31 - 1); eq("d2 ffffffff", -1); eq("d3 8000000000000000", -2 ** 63)
eq("d3 7fffffffffffffff", 2 ** 63 - 1); eq("d3 ffffffffffffffff", -1); eq("d3 0000000000000007", 7); eq("d0 e0", -32)
for h in ["cc", "cd 01", "ce 000000", "cf 00000000000000", "d0", "d1 80", "d2 800000", "d3 80000000000000", "cc 00 00", "d0 00 00", "cf 0000000000000000 00"]:
    assert bad(B(h.replace(" ", ""))), h
# floats
eq("ca 3fc00000", 1.5); eq("ca bf800000", -1.0); eq("ca 00000001", 1.401298464324817e-45); eq("ca 7f7fffff", 3.4028234663852886e+38)
eq("ca 7f800000", float("inf")); eq("ca ff800000", float("-inf")); eq("ca 80000000", -0.0); eq("ca 00000000", 0.0)
eq("cb 3fb999999999999a", 0.1); eq("cb 8000000000000000", -0.0); eq("cb 7ff0000000000000", float("inf")); eq("cb fff0000000000000", float("-inf"))
eq("cb 0000000000000001", 5e-324); eq("cb 7fefffffffffffff", 1.7976931348623157e308)
assert math.isnan(msgpack_loads(B("ca7fc00000"))) and math.isnan(msgpack_loads(B("cb7ff8000000000000"))) and math.isnan(msgpack_loads(B("ca ffc00001".replace(" ", ""))))
for h in ["ca", "ca 3f", "ca 3fc000", "cb", "cb 3ff00000000000", "ca 3fc00000 00", "cb 3ff0000000000000 00"]:
    assert bad(B(h.replace(" ", ""))), h
# strings
eq("a0", ""); eq("a3 616263", "abc"); eq("a2 c3a9", "\xe9"); eq("a4 f09f9880", "\U0001F600"); eq("a3 e4b8ad", "中"); eq("a1 00", "\0")
eq("d9 00", ""); eq("d9 03 616263", "abc"); eq("da 0003 616263", "abc"); eq("db 00000003 616263", "abc"); eq("da 0000", ""); eq("db 00000000", "")
eq("a3 efbfbf", "￿"); eq("a4 f48fbfbf", "\U0010ffff"); eq("a3 e0a080", "ࠀ"); eq("a3 ed9fbf", "퟿")
eq(b"\xbf" + b"x" * 31, "x" * 31); eq(b"\xd9\x20" + b"x" * 32, "x" * 32); eq(b"\xd9\xff" + b"x" * 255, "x" * 255); eq(b"\xda\x01\x00" + b"x" * 256, "x" * 256)
for h in ["a1", "a3 6162", "a1 ff", "a2 c3", "a1 80", "a2 c328", "a2 c0 80", "a2 c080", "a3 e08080", "a3 eda080", "a3 edbfbf", "a4 f4908080", "a4 f0808080",
          "a4 f0 9f 98", "a1 c3", "a5 f8888080 80".replace(" ", ""), "a2 e282", "a2 e2 82", "d9", "d9 03 6162", "da 00", "da 0003 6162", "db 000000", "db 00000003 6162",
          "a1 6161", "d9 01 6161", "a3 c1bf61", "a2 c1bf", "a1 fe", "a2 f5 80", "a3 ffffff", "a4 f090 80".replace(" ", "")]:
    assert bad(B(h.replace(" ", ""))), h
# bin
eq("c4 00", b""); eq("c4 03 000102", b"\0\1\2"); eq("c5 0003 ff00ff", b"\xff\0\xff"); eq("c6 00000002 ffff", b"\xff\xff"); eq("c5 0000", b""); eq("c6 00000000", b"")
assert type(msgpack_loads(bytearray(B("c403aabbcc")))) is bytes
for h in ["c4", "c4 03 0102", "c5 00", "c5 0003 01", "c6 000000", "c6 00000004 010203", "c4 00 00", "c4 01"]:
    assert bad(B(h.replace(" ", ""))), h
# arrays
eq("90", []); eq("91 01", [1]); eq("92 c0 c3", [None, True]); eq("dc 0000", []); eq("dc 0002 01 02", [1, 2]); eq("dd 00000001 ff", [-1])
eq("dd 00000000", []); eq("91 90", [[]]); eq("92 90 91 90", [[], [[]]]); eq(b"\x9f" + b"\x00" * 15, [0] * 15); eq(b"\xdc\x00\x10" + b"\x01" * 16, [1] * 16)
eq(b"\xdc\x27\x10" + b"\x01" * 10000, [1] * 10000); eq(b"\xdd\x00\x01\x00\x00" + b"\xc3" * 65536, [True] * 65536)
for h in ["91", "92 01", "dc", "dc 00", "dc 0002 01", "dd 00000001", "dd 000000", "91 01 02", "90 00", "dc 0000 00", "91 92 01", "dd 00000002 01"]:
    assert bad(B(h.replace(" ", ""))), h
# maps
eq("80", {}); eq("81 a1 61 01", {"a": 1}); eq("de 0000", {}); eq("de 0001 a1 61 c0", {"a": None}); eq("df 00000001 01 02", {1: 2}); eq("81 ff a1 61", {-1: "a"})
eq("82 01 a1 61 a1 31 02", {1: "a", "1": 2}); eq("82 a1 62 01 a1 61 02", {"b": 1, "a": 2})
assert list(msgpack_loads(B("82a16201a16102"))) == ["b", "a"]
eq("82 01 02 03 04", {1: 2, 3: 4}); eq("81 cc 05 a1 78", {5: "x"}); eq("82 a0 01 a1 00 02", {"": 1, "\0": 2}); eq("81 a1 61 81 a1 62 90", {"a": {"b": []}})
eq("82 cf 0000000000000001 01 d0 ff 02", {1: 1, -1: 2}); eq("81 d9 01 61 7f", {"a": 127})
for h in ["81", "81 a1 61", "82 a1 61 01", "de 0001", "df 00000001 01", "81 c0 01", "81 c2 01", "81 c3 01", "81 ca 3fc00000 01", "81 cb 3ff0000000000000 01",
          "81 c4 00 01", "81 90 01", "81 80 01", "81 91 01 02", "82 01 01 01 02", "82 a1 61 01 a1 61 02", "82 01 02 cc 01 03", "82 01 02 d3 0000000000000001 03",
          "82 a1 61 01 d9 01 61 02", "82 a0 01 a0 02", "82 ff 01 d0 ff 02", "81 a1 61 01 02", "82 cf ffffffffffffffff 01 cf ffffffffffffffff 02",
          "81 a1 ff 01"]:
    assert bad(B(h.replace(" ", ""))), h
# reserved bytes
for b in [0xc1, 0xc7, 0xc8, 0xc9, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8]:
    assert bad(bytes([b]) + bytes(20)), hex(b)
    assert bad(bytes([b])), hex(b)
    assert bad(B("91") + bytes([b]) + bytes(20)), hex(b)
    assert bad(B("81a161") + bytes([b]) + bytes(20)), hex(b)
# lying counts and lengths
assert bad(B("dd ffffffff 01 02 03 04 05".replace(" ", "")))
assert bad(B("df ffffffff 01 02 03 04 05".replace(" ", "")))
assert bad(B("dd 7fffffff c0".replace(" ", "")))
assert bad(B("dd 40000000".replace(" ", "")))
assert bad(B("db ffffffff 61 62 63".replace(" ", "")))
assert bad(B("c6 ffffffff 61".replace(" ", "")))
assert bad(B("dc ffff 01".replace(" ", "")))
assert bad(B("de ffff 01 02".replace(" ", "")))
assert bad(B("da ffff 61".replace(" ", "")))
assert bad(B("c5 ffff 61".replace(" ", "")))
assert bad(B("91 dd ffffffff".replace(" ", "")))
assert bad(B("81 a1 61 df ffffffff".replace(" ", "")))
eq(b"\xdd\x00\x00\x00\x05" + bytes(5), [0] * 5)
assert bad(b"\xdd\x00\x00\x00\x06" + bytes(5))
eq(b"\xdf\x00\x00\x00\x02" + B("01020304"), {1: 2, 3: 4})
assert bad(b"\xdf\x00\x00\x00\x03" + B("01020304"))
assert bad(b"\xdf\x00\x00\x00\x02" + B("010203"))
# depth
def nest(n, inner=b"\x90"):
    return b"\x91" * (n - 1) + inner

assert msgpack_loads(nest(16)) is not None
eq(nest(16), [[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]])
assert bad(nest(17))
assert bad(nest(18, b"\x01"))
assert bad(b"\x91" * 100000)
assert bad(b"\x91" * 100000 + b"\xc0")
eq(b"\x91" * 15 + b"\x01", [[[[[[[[[[[[[[[1]]]]]]]]]]]]]]])
eq(b"\x91" * 16 + b"\x01", msgpack_loads(b"\x91" * 15 + b"\x91\x01"))
assert bad(b"\x91" * 17 + b"\x01")
eq(b"\x91" * 15 + B("81a16101"), [[[[[[[[[[[[[[[{"a": 1}]]]]]]]]]]]]]]])
assert bad(b"\x91" * 16 + B("81a16101"))
eq(B("92") + nest(15) + nest(15), [msgpack_loads(nest(15))] * 2)
assert bad(B("92") + nest(16) + nest(16))
assert bad(B("92") + nest(15) + nest(16))
eq(B("81 a1 61") + nest(15), {"a": msgpack_loads(nest(15))})
assert bad(B("81 a1 61".replace(" ", "")) + nest(16))
m = b"\x81\xa1a" * 15 + b"\x80"
assert msgpack_loads(m) is not None
assert bad(b"\x81\xa1a" * 16 + b"\x80")
assert bad(b"\x81\xa1a" * 17 + b"\x01")
assert msgpack_loads(b"\x81\xa1a" * 16 + b"\x01") is not None
# a big, mixed document

# oracle: an encoder that picks random valid spellings
random.seed(4015)
def lenhdr(n, fix, codes):
    opts = []
    if fix is not None and n <= fix[1]:
        opts.append(bytes([fix[0] | n]))
    for code, w in codes:
        if n < 1 << (8 * w):
            opts.append(bytes([code]) + n.to_bytes(w, "big"))
    return random.choice(opts)

def enc_int(v):
    opts = []
    if 0 <= v <= 127 or -32 <= v <= -1:
        opts.append(bytes([v & 0xFF]))
    if v >= 0:
        for code, w in ((0xcc, 1), (0xcd, 2), (0xce, 4), (0xcf, 8)):
            if v < 1 << (8 * w):
                opts.append(bytes([code]) + v.to_bytes(w, "big"))
    for code, w in ((0xd0, 1), (0xd1, 2), (0xd2, 4), (0xd3, 8)):
        if -(1 << (8 * w - 1)) <= v < 1 << (8 * w - 1):
            opts.append(bytes([code]) + v.to_bytes(w, "big", signed=True))
    return random.choice(opts)

def enc_float(x):
    f32 = struct.unpack(">f", struct.pack(">f", x))[0] if abs(x) < 3e38 else x
    if (f32 == x or x != x) and random.random() < 0.6 and abs(x) < 3e38 or x in (float("inf"), float("-inf")) and random.random() < 0.5:
        return b"\xca" + struct.pack(">f", x)
    return b"\xcb" + struct.pack(">d", x)

def enc_str(s):
    r = s.encode("utf-8")
    return lenhdr(len(r), (0xa0, 31), [(0xd9, 1), (0xda, 2), (0xdb, 4)]) + r

def enc(v):
    if v is None:
        return b"\xc0"
    if v is True:
        return b"\xc3"
    if v is False:
        return b"\xc2"
    if isinstance(v, int):
        return enc_int(v)
    if isinstance(v, float):
        return enc_float(v)
    if isinstance(v, str):
        return enc_str(v)
    if isinstance(v, bytes):
        return lenhdr(len(v), None, [(0xc4, 1), (0xc5, 2), (0xc6, 4)]) + v
    if isinstance(v, list):
        return lenhdr(len(v), (0x90, 15), [(0xdc, 2), (0xdd, 4)]) + b"".join(enc(x) for x in v)
    return lenhdr(len(v), (0x80, 15), [(0xde, 2), (0xdf, 4)]) + b"".join(enc(k) + enc(x) for k, x in v.items())

INTS = [0, 1, -1, 31, 32, 127, 128, 255, 256, -32, -33, -128, -129, 32767, 32768, 65535, 65536, -32768, -32769, 2 ** 31 - 1, 2 ** 31, 2 ** 32 - 1, 2 ** 32,
        -2 ** 31, -2 ** 31 - 1, 2 ** 63 - 1, 2 ** 63, 2 ** 64 - 1, -2 ** 63]
FLOATS = [0.0, -0.0, 1.0, 1.5, -2.25, 0.1, 1e300, -1e-300, 3.0e38, 5e-324, 1.401298464324817e-45, float("inf"), float("-inf"), 16777216.0, 1e10, 0.3]
CH = ["a", "b", "z", " ", "\0", "\xe9", "中", "ࠀ", "￿", "\U0001F600", "\U0010ffff", "퟿", "", "\x7f", "\x80"]

def rstr():
    n = random.choice([0, 0, 1, 2, 3, 5, 10, 31, 32, 33, 100, 255, 256, 300])
    return "".join(random.choice(CH) for _ in range(min(n, 60))) if n < 100 else random.choice(CH) * n

def gen(depth):
    r = random.random()
    if depth == 0 or r < 0.55:
        k = random.random()
        if k < 0.1:
            return None
        if k < 0.2:
            return random.choice([True, False])
        if k < 0.5:
            return random.choice(INTS) if random.random() < 0.6 else random.randint(-10 ** 6, 10 ** 6)
        if k < 0.65:
            return random.choice(FLOATS) if random.random() < 0.7 else random.uniform(-1e6, 1e6)
        if k < 0.9:
            return rstr()
        return bytes(random.randrange(256) for _ in range(random.choice([0, 1, 5, 255, 256, 300])))
    if r < 0.8:
        return [gen(depth - 1) for _ in range(random.choice([0, 1, 2, 3, 5, 15, 16, 17, 40]))]
    d = {}
    for _ in range(random.choice([0, 1, 2, 3, 5, 15, 16, 17])):
        k = rstr() if random.random() < 0.6 else random.choice(INTS)
        d[k] = gen(depth - 1)
    return d

def depth_of(v):
    if isinstance(v, list):
        return 1 + max([depth_of(x) for x in v], default=0)
    if isinstance(v, dict):
        return 1 + max([depth_of(x) for x in v.values()], default=0)
    return 0

nbig = 0
for _ in range(200):
    v = gen(random.choice([1, 2, 3, 4]))
    e = enc(v)
    got = msgpack_loads(e)
    assert same(got, v), (e[:60], got, v)
    assert same(msgpack_loads(bytearray(e)), v)
    nbig += len(e) > 200
    for _ in range(2):
        k = random.randrange(len(e))
        assert bad(e[:k]), (e[:k], v)
    assert bad(e + bytes([random.randrange(256)])) and bad(e + b"\xc0") and bad(e + e)
    assert bad(bytearray(e)[:-1])
assert nbig > 20

# wrapped in k arrays: depth boundary against the oracle
for _ in range(25):
    v = gen(2)
    base = depth_of(v)
    for k in range(0, 18 - base + 2):
        e = b"".join(lenhdr(1, (0x90, 15), [(0xdc, 2), (0xdd, 4)]) for _ in range(k)) + enc(v)
        if base + k <= 16:
            exp = v
            for _ in range(k):
                exp = [exp]
            assert same(msgpack_loads(e), exp), (k, base)
        else:
            assert bad(e), (k, base)

# maps with bad keys, spelled by hand
KEYS_BAD = [b"\xc0", b"\xc2", b"\xc3", b"\xca\x3f\xc0\x00\x00", b"\xcb" + bytes(8), b"\xc4\x01a", b"\x90", b"\x91\x01", b"\x80", b"\x81\x01\x01", b"\xde\x00\x00"]
KEYS_OK = [b"\xa1a", b"\x01", b"\xff", b"\xcc\x05", b"\xd3" + (-7).to_bytes(8, "big", signed=True), b"\xa0", b"\xd9\x01b"]
for kb in KEYS_BAD:
    for pos in range(2):
        pairs = [(b"\xa1z", b"\x01"), (kb, b"\x02")] if pos else [(kb, b"\x02"), (b"\xa1z", b"\x01")]
        assert bad(b"\x82" + b"".join(a + b for a, b in pairs)), kb
        assert bad(lenhdr(2, (0x80, 15), [(0xde, 2), (0xdf, 4)]) + b"".join(a + b for a, b in pairs)), kb
for kb in KEYS_OK:
    e = b"\x81" + kb + b"\xc0"
    assert type(msgpack_loads(e)) is dict
DUPS = [(b"\xa1a", b"\xd9\x01a"), (b"\x01", b"\xcc\x01"), (b"\x01", b"\xd3" + (1).to_bytes(8, "big")), (b"\xff", b"\xd0\xff"), (b"\xa0", b"\xda\x00\x00"),
        (b"\xcf" + (5).to_bytes(8, "big"), b"\x05"), (b"\xe0", b"\xd1" + (-32).to_bytes(2, "big", signed=True))]
for a, b in DUPS:
    assert bad(b"\x82" + a + b"\x01" + b + b"\x02"), (a, b)
    assert bad(b"\x83" + a + b"\x01" + b"\xa1q\x00" + b + b"\x02"), (a, b)
# distinct keys that only look alike
eq(b"\x84\x01\x01\xa1" + b"1" + b"\x02\xa0\x03\xff\x04", {1: 1, "1": 2, "": 3, -1: 4})
eq(b"\x82\xa1a\x01\xa2aa\x02", {"a": 1, "aa": 2})
eq(b"\x82\xa1a\x81\xa1a\x01\xa1b\x81\xa1a\x02", {"a": {"a": 1}, "b": {"a": 2}})
''', r'''
import struct

_MAX_OPEN = 16


def msgpack_loads(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    data = bytes(data)
    n = len(data)
    pos = [0]

    def take(k):
        p = pos[0]
        if k < 0 or p + k > n:
            raise ValueError("truncated")
        pos[0] = p + k
        return data[p:p + k]

    def num(k):
        return int.from_bytes(take(k), "big")

    def seq(count, per, openn, kind):
        if openn >= _MAX_OPEN:
            raise ValueError("nested too deep")
        if count * per > n - pos[0]:
            raise ValueError("count exceeds data")
        if kind == "a":
            return [val(openn + 1) for _ in range(count)]
        d = {}
        for _ in range(count):
            k = val(openn + 1)
            if type(k) is bool or not isinstance(k, (str, int)):
                raise ValueError("bad map key")
            if k in d:
                raise ValueError("duplicate key")
            d[k] = val(openn + 1)
        return d

    def text(k):
        raw = take(k)
        return raw.decode("utf-8")

    def val(openn):
        b = take(1)[0]
        if b <= 0x7F:
            return b
        if b >= 0xE0:
            return b - 256
        if b <= 0x8F:
            return seq(b & 15, 2, openn, "m")
        if b <= 0x9F:
            return seq(b & 15, 1, openn, "a")
        if b <= 0xBF:
            return text(b & 31)
        if b == 0xC0:
            return None
        if b == 0xC2:
            return False
        if b == 0xC3:
            return True
        if b in (0xC4, 0xC5, 0xC6):
            return take(num(1 << (b - 0xC4)))
        if b == 0xCA:
            return struct.unpack(">f", take(4))[0]
        if b == 0xCB:
            return struct.unpack(">d", take(8))[0]
        if 0xCC <= b <= 0xCF:
            return num(1 << (b - 0xCC))
        if 0xD0 <= b <= 0xD3:
            w = 1 << (b - 0xD0)
            return int.from_bytes(take(w), "big", signed=True)
        if b in (0xD9, 0xDA, 0xDB):
            return text(num(1 << (b - 0xD9)))
        if b in (0xDC, 0xDD):
            return seq(num(2 if b == 0xDC else 4), 1, openn, "a")
        if b in (0xDE, 0xDF):
            return seq(num(2 if b == 0xDE else 4), 2, openn, "m")
        raise ValueError("unsupported type byte")

    result = val(0)
    if pos[0] != n:
        raise ValueError("trailing bytes")
    return result
''')


task("v4_16_ifc_calendar", r'''
The International Fixed Calendar (IFC) keeps the Gregorian year number and Gregorian January 1
as its first day, but splits the year into 13 months of exactly 28 days, numbered 1..13 (days
1..28). Every month begins on a Sunday, so the weekday of IFC day d (1..28) is (d - 1) % 7 with
Sunday = 0. Two intercalary days belong to no month and to no week:
- Leap Day, written (month 6, day 29), exists only in Gregorian leap years (divisible by 4,
  except multiples of 100 that are not multiples of 400). It comes right after (6, 28).
- Year Day, written (month 13, day 29), exists in every year and is the last day of the year.
So the order within a year is: months 1..6, Leap Day (leap years only), months 7..13, Year Day.
Years are 1..9999 (proleptic Gregorian). Write three functions:
- `ifc_from_gregorian(y, m, d)`: Gregorian date to the 4-tuple (ifc_year, ifc_month, ifc_day,
  weekday). weekday is an int 0..6 for ordinary days and None for Leap Day and Year Day.
- `ifc_to_gregorian(y, m, d)`: IFC date to the Gregorian 3-tuple (year, month, day).
- `ifc_add_days(date, n)`: `date` is an IFC date, a list or tuple of 3 ints (y, m, d); n is an
  int with abs(n) <= 10**7, positive or negative. Move n actual days (Leap Day and Year Day are
  days like any other) and return the IFC 3-tuple (y, m, d) of the result.
A valid IFC date has 1 <= m <= 13 and 1 <= d <= 28, or is Year Day (13, 29), or is Leap Day
(6, 29) in a leap year. Every argument must be an int (bool is not an int); the Gregorian
date must exist; years must be in 1..9999. Anything else, an n out of range, a `date` that is
not a list or tuple of length 3, or a result whose year is outside 1..9999, is a ValueError.
Examples: ifc_from_gregorian(2024, 6, 17) is (2024, 6, 29, None) (Leap Day);
ifc_from_gregorian(2023, 6, 17) is (2023, 6, 28, 6); ifc_from_gregorian(2023, 6, 18) is
(2023, 7, 1, 0); ifc_to_gregorian(2024, 13, 29) is (2024, 12, 31); ifc_add_days((2023, 13, 29), 1)
is (2024, 1, 1); ifc_to_gregorian(2023, 6, 29) raises ValueError.
''', r'''
import random, datetime, calendar

def bad(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert ifc_from_gregorian(2024, 1, 1) == (2024, 1, 1, 0)
assert ifc_from_gregorian(2024, 6, 17) == (2024, 6, 29, None)
assert ifc_from_gregorian(2023, 6, 17) == (2023, 6, 28, 6)
assert ifc_from_gregorian(2024, 6, 16) == (2024, 6, 28, 6)
assert ifc_from_gregorian(2024, 6, 18) == (2024, 7, 1, 0)
assert ifc_from_gregorian(2023, 6, 18) == (2023, 7, 1, 0)
assert ifc_from_gregorian(2023, 12, 31) == (2023, 13, 29, None)
assert ifc_from_gregorian(2023, 12, 30) == (2023, 13, 28, 6)
assert ifc_from_gregorian(2024, 12, 31) == (2024, 13, 29, None)
assert ifc_from_gregorian(2024, 12, 30) == (2024, 13, 28, 6)
assert ifc_from_gregorian(1900, 3, 1) == (1900, 3, 4, 3)
assert ifc_from_gregorian(2000, 3, 1) == (2000, 3, 5, 4)
assert ifc_from_gregorian(2000, 2, 29) == (2000, 3, 4, 3)
assert ifc_from_gregorian(1, 1, 1) == (1, 1, 1, 0)
assert ifc_from_gregorian(9999, 12, 31) == (9999, 13, 29, None)
assert ifc_to_gregorian(2024, 6, 29) == (2024, 6, 17)
assert ifc_to_gregorian(2024, 13, 29) == (2024, 12, 31)
assert ifc_to_gregorian(2023, 13, 29) == (2023, 12, 31)
assert ifc_to_gregorian(2024, 7, 1) == (2024, 6, 18)
assert ifc_to_gregorian(2023, 7, 1) == (2023, 6, 18)
assert ifc_to_gregorian(1900, 6, 28) == (1900, 6, 17)
assert ifc_to_gregorian(2000, 6, 29) == (2000, 6, 17)
assert ifc_to_gregorian(9999, 13, 29) == (9999, 12, 31)
assert ifc_add_days((2023, 13, 29), 1) == (2024, 1, 1)
assert ifc_add_days([2023, 13, 29], 1) == (2024, 1, 1)
assert ifc_add_days((2024, 6, 28), 1) == (2024, 6, 29)
assert ifc_add_days((2024, 6, 29), 1) == (2024, 7, 1)
assert ifc_add_days((2023, 6, 28), 1) == (2023, 7, 1)
assert ifc_add_days((2024, 1, 1), -1) == (2023, 13, 29)
assert ifc_add_days((2024, 1, 1), 366) == (2025, 1, 1)
assert ifc_add_days((2023, 1, 1), 365) == (2024, 1, 1)
assert ifc_add_days((2024, 6, 29), 0) == (2024, 6, 29)
assert ifc_add_days((1, 1, 1), 0) == (1, 1, 1)
assert ifc_add_days((1, 1, 1), 3652058) == (9999, 13, 29)
assert ifc_add_days((9999, 13, 29), -3652058) == (1, 1, 1)
for args in [(1, 1, 1, -1), (9999, 13, 29, 1), (9999, 13, 29, 10**7), (1, 1, 1, -10**7), (5000, 1, 1, 10**7), (5000, 1, 1, -10**7),
             (2000, 1, 1, 10**7 + 1), (2000, 1, 1, -10**7 - 1), (1, 1, 1, 3652059)]:
    assert bad(ifc_add_days, (args[0], args[1], args[2]), args[3]), args
for a in [(2023, 6, 29), (1900, 6, 29), (2024, 5, 29), (2024, 7, 29), (2024, 12, 29), (2024, 13, 30), (2024, 14, 1), (2024, 0, 1), (2024, 1, 0),
          (2024, 1, 29), (2024, 1, 30), (0, 1, 1), (10000, 1, 1), (-5, 1, 1), (2024.0, 1, 1), (2024, 1.0, 1), ("2024", 1, 1), (True, 1, 1), (2024, True, 1),
          (2024, 1, True), (None, 1, 1), (2024, 6, None)]:
    assert bad(ifc_to_gregorian, *a), a
for a in [(2023, 2, 29), (1900, 2, 29), (2024, 2, 30), (2024, 4, 31), (2024, 0, 1), (2024, 13, 1), (2024, 1, 0), (2024, 1, 32), (0, 1, 1), (10000, 1, 1),
          (2024.0, 1, 1), ("2024", 1, 1), (2024, 1, 1.0), (False, 1, 1), (2024, 1, False), (2024, True, 1), (None, 1, 1)]:
    assert bad(ifc_from_gregorian, *a), a
for dt, n in [(None, 1), ((2024, 1), 1), ((2024, 1, 1, 1), 1), ("2024", 1), ({2024, 1, 1}, 1), ((2024, 1, 1), 1.0), ((2024, 1, 1), True), ((2024, 1, 1), "1"),
              ((2024, 1, 1), None), ((2024, 6, 29.0), 1), ((2023, 6, 29), 1), ((2024, 13, 30), 1), ((2024, 14, 1), 1), ((2024, 1, 29), 1), ((0, 1, 1), 1),
              ((10000, 13, 29), -1), (((2024, 1, 1),), 1), ((True, 1, 1), 1)]:
    assert bad(ifc_add_days, dt, n), (dt, n)

# oracle: enumerate the labels of a year in calendar order and pair them with datetime days
def labels(y):
    L = [(m, d) for m in range(1, 7) for d in range(1, 29)]
    if calendar.isleap(y):
        L.append((6, 29))
    L += [(m, d) for m in range(7, 14) for d in range(1, 29)]
    L.append((13, 29))
    return L

def weekdays(L):
    out, k = [], 0
    for (m, d) in L:
        if d == 29:
            out.append(None)
        else:
            out.append(k % 7)
            k += 1
    return out

random.seed(4016)
years = [1, 4, 100, 400, 1900, 1999, 2000, 2023, 2024, 2100, 9996, 9999] + [random.randint(1, 9999) for _ in range(14)] + [4 * random.randint(1, 2499) for _ in range(4)]
for y in years:
    L = labels(y)
    W = weekdays(L)
    first = datetime.date(y, 1, 1)
    assert len(L) == (366 if calendar.isleap(y) else 365)
    for i, (m, d) in enumerate(L):
        g = first + datetime.timedelta(i)
        assert g.year == y
        assert ifc_from_gregorian(g.year, g.month, g.day) == (y, m, d, W[i]), (g, m, d)
        assert ifc_to_gregorian(y, m, d) == (g.year, g.month, g.day), (y, m, d)

def ifc_label_of(g):
    L = labels(g.year)
    return (g.year,) + L[(g - datetime.date(g.year, 1, 1)).days]

MAXO = datetime.date(9999, 12, 31).toordinal()
nerr = 0
for _ in range(900):
    y = random.choice([random.randint(1, 9999), random.randint(1, 30), random.randint(9970, 9999), random.randint(1990, 2030)])
    L = labels(y)
    m, d = random.choice(L)
    n = random.choice([random.randint(-10**7, 10**7), random.randint(-800, 800), random.randint(-40, 40), random.choice([-3, -2, -1, 0, 1, 2, 365, 366, -365, -366])])
    g = datetime.date(y, 1, 1) + datetime.timedelta(L.index((m, d)))
    o = g.toordinal() + n
    date = random.choice([(y, m, d), [y, m, d]])
    if 1 <= o <= MAXO:
        exp = ifc_label_of(datetime.date.fromordinal(o))
        assert ifc_add_days(date, n) == exp, (date, n, exp)
    else:
        nerr += 1
        assert bad(ifc_add_days, date, n), (date, n)
assert nerr > 10, nerr
''', r'''
_MD = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _mlen(y, m):
    return 29 if m == 2 and _leap(y) else _MD[m - 1]


def _before(y):
    p = y - 1
    return 365 * p + p // 4 - p // 100 + p // 400


def _gdoy(y, m, d):
    for v in (y, m, d):
        if not _isint(v):
            raise ValueError("int")
    if not (1 <= y <= 9999 and 1 <= m <= 12 and 1 <= d <= _mlen(y, m)):
        raise ValueError("date")
    return sum(_mlen(y, k) for k in range(1, m)) + d


def _idoy(y, m, d):
    for v in (y, m, d):
        if not _isint(v):
            raise ValueError("int")
    if not 1 <= y <= 9999:
        raise ValueError("year")
    leap = _leap(y)
    if (m, d) == (13, 29):
        return 366 if leap else 365
    if (m, d) == (6, 29):
        if not leap:
            raise ValueError("no leap day")
        return 169
    if not (1 <= m <= 13 and 1 <= d <= 28):
        raise ValueError("date")
    base = 28 * (m - 1) + d
    if leap and base >= 169:
        base += 1
    return base


def _ifc(y, doy):
    leap = _leap(y)
    if doy == (366 if leap else 365):
        return (y, 13, 29, None)
    if leap:
        if doy == 169:
            return (y, 6, 29, None)
        if doy > 169:
            doy -= 1
    q, r = divmod(doy - 1, 28)
    return (y, q + 1, r + 1, r % 7)


def ifc_from_gregorian(y, m, d):
    return _ifc(y, _gdoy(y, m, d))


def ifc_to_gregorian(y, m, d):
    doy = _idoy(y, m, d)
    for mm in range(1, 13):
        k = _mlen(y, mm)
        if doy <= k:
            return (y, mm, doy)
        doy -= k


def ifc_add_days(date, n):
    if not isinstance(date, (list, tuple)) or len(date) != 3:
        raise ValueError("date")
    if not _isint(n) or abs(n) > 10 ** 7:
        raise ValueError("n")
    y, m, d = date
    o = _before(y) + _idoy(y, m, d) + n
    if not 1 <= o <= _before(10000):
        raise ValueError("range")
    y = (o - 1) * 400 // 146097 + 1
    while _before(y) >= o:
        y -= 1
    while _before(y + 1) < o:
        y += 1
    return _ifc(y, o - _before(y))[:3]
''')

task("v4_17_timer_sched", r'''
Write `timer_sched(timers, cancels, mutes, until, k)` that works out what a timer service
delivers. All times are ints; bool is not an int.
- `timers`: list or tuple of at most 30 tuples (name, start, period, count, prio). name is a
  non-empty str, unique among the timers. 0 <= start <= 10**12, 0 <= period <= 10**12,
  1 <= count <= 10**12, -100 <= prio <= 100. Firing i (i = 0 .. count-1) of a timer is
  scheduled at s = start + i*period (so s can exceed 10**12). A timer with period 0 must
  have count 1.
- `cancels`: list or tuple of at most 60 tuples (name, t, mode): name is a timer's name,
  0 <= t <= 10**12, mode is "before" or "after". Mode "before" blocks every delivery of that
  timer at a time >= t; mode "after" blocks every delivery at a time > t (a delivery exactly
  at t still happens). A timer with several cancels is blocked by all of them.
- `mutes`: list or tuple of at most 60 windows (a, b), 0 <= a < b <= 10**12, half-open [a, b).
  A firing scheduled at a time s inside a window is not lost but postponed: its delivery time
  becomes b; if b lies inside another window it is postponed again to that window's end, and
  so on until the time lies in no window. A firing scheduled outside every window is
  delivered at s. Windows may overlap or touch.
- `until`: 0 <= until <= 10**12. A firing whose delivery time is >= until is never delivered.
  `k`: 0 <= k <= 200.
Cancels are judged on the delivery time, not on s, and they simply drop the firing.
Return a dict with two keys. "log": the first k deliveries (all of them if fewer), each a
tuple (delivery_time, name, i), ordered by delivery time; deliveries at the same time are
ordered by prio ascending (lower prio first), then by scheduled time s ascending, then by the
timer's position in `timers`. "counts": a dict {name: number of deliveries of that timer},
for every timer (0 included) and over the whole run, not just the first k. Counts can reach
10**12 and `timers` may hold 10**12 firings, so the work must not depend on count or until.
Anything else (wrong types or ranges, duplicate or empty names, a cancel naming an unknown
timer, a bad mode, period 0 with count > 1, a window with a >= b, too many items) is a
ValueError, checked before anything is computed.
Example: timer_sched([("a", 0, 5, 3, 0), ("b", 5, 0, 1, -1)], [], [], 100, 10) returns
{"log": [(0, "a", 0), (5, "b", 0), (5, "a", 1), (10, "a", 2)], "counts": {"a": 3, "b": 1}}.
With timers [("a", 0, 2, 4, 0)] and mutes [(1, 5)] the log is [(0, "a", 0), (5, "a", 1),
(5, "a", 2), (6, "a", 3)]; adding the cancel ("a", 5, "after") leaves the first three entries.
''', r'''
import random

def bad(*a):
    try:
        timer_sched(*a)
    except ValueError:
        return True
    return False

r = timer_sched([("a", 0, 5, 3, 0), ("b", 5, 0, 1, -1)], [], [], 100, 10)
assert r == {"log": [(0, "a", 0), (5, "b", 0), (5, "a", 1), (10, "a", 2)], "counts": {"a": 3, "b": 1}}, r
assert timer_sched([("a", 0, 2, 4, 0)], [], [(1, 5)], 100, 10)["log"] == [(0, "a", 0), (5, "a", 1), (5, "a", 2), (6, "a", 3)]
assert timer_sched([("a", 0, 2, 4, 0)], [("a", 5, "after")], [(1, 5)], 100, 10) == {"log": [(0, "a", 0), (5, "a", 1), (5, "a", 2)], "counts": {"a": 3}}
assert timer_sched([("a", 0, 2, 4, 0)], [("a", 5, "before")], [(1, 5)], 100, 10) == {"log": [(0, "a", 0)], "counts": {"a": 1}}
assert timer_sched([("a", 0, 2, 4, 0)], [("a", 0, "after")], [], 100, 10) == {"log": [(0, "a", 0)], "counts": {"a": 1}}
assert timer_sched([("a", 0, 2, 4, 0)], [("a", 0, "before")], [], 100, 10) == {"log": [], "counts": {"a": 0}}
assert timer_sched([("a", 0, 2, 4, 0)], [("a", 6, "after"), ("a", 2, "before")], [], 100, 10) == {"log": [(0, "a", 0)], "counts": {"a": 1}}
# chained and touching windows
assert timer_sched([("a", 3, 0, 1, 0)], [], [(2, 5), (5, 9), (9, 10)], 100, 5)["log"] == [(10, "a", 0)]
assert timer_sched([("a", 3, 0, 1, 0)], [], [(2, 5), (6, 9)], 100, 5)["log"] == [(5, "a", 0)]
assert timer_sched([("a", 3, 0, 1, 0)], [], [(6, 9), (2, 5), (4, 7)], 100, 5)["log"] == [(9, "a", 0)]
# until is exclusive, applies to the delivery time
assert timer_sched([("a", 3, 0, 1, 0)], [], [], 3, 5) == {"log": [], "counts": {"a": 0}}
assert timer_sched([("a", 3, 0, 1, 0)], [], [], 4, 5) == {"log": [(3, "a", 0)], "counts": {"a": 1}}
assert timer_sched([("a", 3, 0, 1, 0)], [], [(0, 4)], 4, 5) == {"log": [], "counts": {"a": 0}}
assert timer_sched([("a", 3, 0, 1, 0)], [], [(0, 4)], 5, 5) == {"log": [(4, "a", 0)], "counts": {"a": 1}}
# k limits only the log
assert timer_sched([("a", 0, 1, 10, 0)], [], [], 100, 3) == {"log": [(0, "a", 0), (1, "a", 1), (2, "a", 2)], "counts": {"a": 10}}
assert timer_sched([("a", 0, 1, 10, 0)], [], [], 100, 0) == {"log": [], "counts": {"a": 10}}
assert timer_sched([], [], [], 0, 0) == {"log": [], "counts": {}}
# same instant: prio, then scheduled time, then position
r = timer_sched([("x", 2, 0, 1, 5), ("y", 1, 0, 1, 5), ("z", 0, 0, 1, 7), ("w", 3, 0, 1, 5), ("v", 9, 0, 1, -3)], [], [(0, 4), (8, 10)], 50, 10)
assert r["log"] == [(4, "y", 0), (4, "x", 0), (4, "w", 0), (4, "z", 0), (10, "v", 0)], r
r = timer_sched([("p", 4, 0, 1, 1), ("q", 4, 0, 1, 1)], [], [], 50, 10)
assert r["log"] == [(4, "p", 0), (4, "q", 0)]
# a postponed firing is cancelled by its delivery time
assert timer_sched([("a", 3, 0, 1, 0)], [("a", 8, "after")], [(2, 9)], 100, 5) == {"log": [], "counts": {"a": 0}}
assert timer_sched([("a", 3, 0, 1, 0)], [("a", 9, "after")], [(2, 9)], 100, 5) == {"log": [(9, "a", 0)], "counts": {"a": 1}}
# big numbers
E12 = 10**12
r = timer_sched([("a", 0, 1, E12, 0)], [], [(10, 20)], E12, 25)
assert r["counts"] == {"a": E12}
assert r["log"] == [(i, "a", i) for i in range(10)] + [(20, "a", i) for i in range(10, 20)] + [(i, "a", i) for i in range(20, 25)], r["log"]
assert timer_sched([("a", 0, 1, E12, 0)], [], [(10**11, E12 - 5)], E12 - 2, 0)["counts"] == {"a": E12 - 2}
assert timer_sched([("a", 0, 1, E12, 0)], [], [(10**11, E12)], E12, 0)["counts"] == {"a": 10**11}
assert timer_sched([("a", 0, 1, E12, 0)], [], [(10**11, E12 - 1)], E12, 0)["counts"] == {"a": E12}
assert timer_sched([("a", 0, 1, E12, 0)], [("a", 10**11, "after")], [], E12, 0)["counts"] == {"a": 10**11 + 1}
assert timer_sched([("a", 0, 1, E12, 0)], [("a", 10**11, "before")], [], E12, 0)["counts"] == {"a": 10**11}
assert timer_sched([("a", 7, 3, E12, 0)], [], [], E12, 0)["counts"] == {"a": (E12 - 8) // 3 + 1}
assert timer_sched([("a", 7, 3, 5, 0)], [], [], E12, 10)["log"] == [(7 + 3 * i, "a", i) for i in range(5)]
assert timer_sched([("a", E12, E12, E12, 0), ("b", E12, 0, 1, 0)], [], [], E12, 5) == {"log": [], "counts": {"a": 0, "b": 0}}
r = timer_sched([("a", 5, E12, E12, 0)], [], [(0, 10), (10**11, 10**11 + 3)], E12, 5)
assert r == {"log": [(10, "a", 0)], "counts": {"a": 1}}, r
r = timer_sched([("a", 0, 3, E12, 2), ("b", 0, 3, E12, 1), ("c", 1, 3, E12, 1)], [("b", 12, "after")], [(4, 8), (7, 13)], 20, 40)
assert r["log"][:5] == [(0, "b", 0), (0, "a", 0), (1, "c", 0), (3, "b", 1), (3, "a", 1)], r["log"][:5]

for args in [
    ([("a", 0, 0, 2, 0)], [], [], 10, 5), ([("a", 0, 1, 0, 0)], [], [], 10, 5), ([("a", -1, 1, 1, 0)], [], [], 10, 5), ([("a", 0, -1, 1, 0)], [], [], 10, 5),
    ([("a", 0, 1, 1, 101)], [], [], 10, 5), ([("a", 0, 1, 1, -101)], [], [], 10, 5), ([("a", E12 + 1, 1, 1, 0)], [], [], 10, 5),
    ([("a", 0, E12 + 1, 1, 0)], [], [], 10, 5), ([("a", 0, 1, E12 + 1, 0)], [], [], 10, 5), ([("", 0, 1, 1, 0)], [], [], 10, 5),
    ([(1, 0, 1, 1, 0)], [], [], 10, 5), ([("a", 0, 1, 1, 0), ("a", 1, 1, 1, 0)], [], [], 10, 5), ([("a", 0, 1, 1)], [], [], 10, 5),
    ([("a", 0, 1, 1, 0, 0)], [], [], 10, 5), ([("a", True, 1, 1, 0)], [], [], 10, 5), ([("a", 0, 1.0, 1, 0)], [], [], 10, 5),
    ([("a", 0, 1, 1, "0")], [], [], 10, 5), (("a", 0, 1, 1, 0), [], [], 10, 5), ({}, [], [], 10, 5),
    ([("a", 0, 1, 1, 0)], [("b", 1, "before")], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", 1, "during")], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", -1, "before")], [], 10, 5),
    ([("a", 0, 1, 1, 0)], [("a", E12 + 1, "before")], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", 1)], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", True, "after")], [], 10, 5),
    ([("a", 0, 1, 1, 0)], [(["a"], 1, "after")], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", 1, ["after"])], [], 10, 5), ([("a", 0, 1, 1, 0)], "x", [], 10, 5),
    ([("a", 0, 1, 1, 0)], [], [(5, 5)], 10, 5), ([("a", 0, 1, 1, 0)], [], [(6, 5)], 10, 5), ([("a", 0, 1, 1, 0)], [], [(-1, 5)], 10, 5),
    ([("a", 0, 1, 1, 0)], [], [(0, E12 + 1)], 10, 5), ([("a", 0, 1, 1, 0)], [], [(1, 2, 3)], 10, 5), ([("a", 0, 1, 1, 0)], [], [(1.0, 2)], 10, 5),
    ([("a", 0, 1, 1, 0)], [], [(1, 2)], -1, 5), ([("a", 0, 1, 1, 0)], [], [(1, 2)], E12 + 1, 5), ([("a", 0, 1, 1, 0)], [], [(1, 2)], 10.0, 5),
    ([("a", 0, 1, 1, 0)], [], [(1, 2)], True, 5), ([("a", 0, 1, 1, 0)], [], [(1, 2)], 10, -1), ([("a", 0, 1, 1, 0)], [], [(1, 2)], 10, 201),
    ([("a", 0, 1, 1, 0)], [], [(1, 2)], 10, 1.0), ([("a", 0, 1, 1, 0)], [], [(1, 2)], 10, None),
    ([("t%d" % i, 0, 1, 1, 0) for i in range(31)], [], [], 10, 5), ([("a", 0, 1, 1, 0)], [("a", 1, "after")] * 61, [], 10, 5),
    ([("a", 0, 1, 1, 0)], [], [(1, 2)] * 61, 10, 5),
]:
    assert bad(*args), args
assert not bad([("t%d" % i, 0, 1, 1, 0) for i in range(30)], [("t0", 1, "after")] * 60, [(1, 2)] * 60, 10, 200)

# oracle: tick by tick, postponed firings wait in a pending list until a tick outside every window
def tick_oracle(timers, cancels, mutes, until, k):
    pend, log = [], []
    counts = {t[0]: 0 for t in timers}
    def blocked(nm, tk):
        for (n, c, mode) in cancels:
            if n == nm and ((mode == "before" and tk >= c) or (mode == "after" and tk > c)):
                return True
        return False
    for tk in range(until):
        for ti, (name, start, period, cnt, prio) in enumerate(timers):
            if tk >= start:
                if period == 0:
                    if tk == start:
                        pend.append((ti, 0, tk))
                elif (tk - start) % period == 0 and (tk - start) // period < cnt:
                    pend.append((ti, (tk - start) // period, tk))
        if any(a <= tk < b for (a, b) in mutes):
            continue
        batch = sorted(pend, key=lambda p: (timers[p[0]][4], p[2], p[0]))
        pend = []
        for ti, i, s in batch:
            nm = timers[ti][0]
            if blocked(nm, tk):
                continue
            counts[nm] += 1
            log.append((tk, nm, i))
    return {"log": log[:k], "counts": counts}

def gen_small():
    nt = random.randint(1, 5)
    names = random.sample(["a", "b", "c", "d", "e", "f"], nt)
    timers = []
    for nm in names:
        period = random.choice([0, 1, 2, 3, 3, 4, 5, 8])
        cnt = 1 if period == 0 else random.randint(1, 9)
        timers.append((nm, random.randint(0, 30), period, cnt, random.randint(-2, 2)))
    cancels = [(random.choice(names), random.randint(0, 45), random.choice(["before", "after"])) for _ in range(random.choice([0, 0, 1, 2, 3]))]
    mutes = []
    for _ in range(random.choice([0, 1, 2, 3, 4])):
        a = random.randint(0, 40)
        mutes.append((a, a + random.randint(1, 9)))
    return timers, cancels, mutes, random.randint(0, 70), random.randint(0, 45)

random.seed(4017)
cases = []
nonempty = delayed = cancelled = ties = 0
for _ in range(260):
    timers, cancels, mutes, until, k = gen_small()
    exp = tick_oracle(timers, cancels, mutes, until, k)
    got = timer_sched(random.choice([timers, tuple(timers)]), cancels, mutes, until, k)
    assert got == exp, (timers, cancels, mutes, until, k, got, exp)
    full = tick_oracle(timers, cancels, mutes, until, 10**6)
    nonempty += bool(exp["log"])
    ties += any(full["log"][j][0] == full["log"][j + 1][0] for j in range(len(full["log"]) - 1))
    nodel = tick_oracle(timers, cancels, [], until, 10**6)
    delayed += nodel["counts"] != full["counts"] or [e[0] for e in nodel["log"]] != [e[0] for e in full["log"]]
    nocan = tick_oracle(timers, [], mutes, until, 10**6)
    cancelled += nocan["counts"] != full["counts"]
    cases.append((timers, cancels, mutes, until, k, exp))
assert nonempty > 150 and ties > 60 and delayed > 80 and cancelled > 40, (nonempty, ties, delayed, cancelled)

# the same cases with every time multiplied by f (order and indices do not change)
for timers, cancels, mutes, until, k, exp in cases[:90]:
    f = random.choice([10**6, 7 * 10**8, 10**9, 123456789])
    T2 = [(n, s * f, p * f, c, pr) for (n, s, p, c, pr) in timers]
    C2 = [(n, t * f, m) for (n, t, m) in cancels]
    M2 = [(a * f, b * f) for (a, b) in mutes]
    got = timer_sched(T2, C2, M2, until * f, k)
    want = {"log": [(t * f, n, i) for (t, n, i) in exp["log"]], "counts": exp["counts"]}
    assert got == want, (T2, C2, M2, until * f, k)
''', r'''
from bisect import bisect_right


def timer_sched(timers, cancels, mutes, until, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def seq(x, n):
        if not isinstance(x, (list, tuple)) or len(x) > n:
            raise ValueError("sequence")
        return x

    if not (isint(until) and 0 <= until <= 10 ** 12 and isint(k) and 0 <= k <= 200):
        raise ValueError("until/k")
    T = []
    pos = {}
    for idx, t in enumerate(seq(timers, 30)):
        if not isinstance(t, (list, tuple)) or len(t) != 5:
            raise ValueError("timer")
        name, start, period, count, prio = t
        if not isinstance(name, str) or not name or name in pos:
            raise ValueError("name")
        if not all(isint(v) for v in (start, period, count, prio)):
            raise ValueError("int")
        if not (0 <= start <= 10 ** 12 and 0 <= period <= 10 ** 12 and 1 <= count <= 10 ** 12 and -100 <= prio <= 100):
            raise ValueError("range")
        if period == 0 and count != 1:
            raise ValueError("period 0")
        pos[name] = idx
        T.append((name, start, period, count, prio))
    thr = [None] * len(T)
    for c in seq(cancels, 60):
        if not isinstance(c, (list, tuple)) or len(c) != 3:
            raise ValueError("cancel")
        name, t, mode = c
        if not isinstance(name, str) or name not in pos or not isint(t) or not 0 <= t <= 10 ** 12:
            raise ValueError("cancel")
        if not isinstance(mode, str) or mode not in ("before", "after"):
            raise ValueError("mode")
        lim = t if mode == "before" else t + 1
        j = pos[name]
        thr[j] = lim if thr[j] is None else min(thr[j], lim)
    ws = []
    for w in seq(mutes, 60):
        if not isinstance(w, (list, tuple)) or len(w) != 2:
            raise ValueError("window")
        a, b = w
        if not (isint(a) and isint(b) and 0 <= a < b <= 10 ** 12):
            raise ValueError("window")
        ws.append((a, b))
    ws.sort()
    merged = []
    for a, b in ws:
        if merged and a <= merged[-1][1]:
            if b > merged[-1][1]:
                merged[-1][1] = b
        else:
            merged.append([a, b])
    starts = [w[0] for w in merged]

    def delivery(s):
        j = bisect_right(starts, s) - 1
        if j >= 0 and s < merged[j][1]:
            return merged[j][1]
        return s

    events = []
    counts = {}
    for idx, (name, start, period, count, prio) in enumerate(T):
        lim = until if thr[idx] is None else min(until, thr[idx])

        def f(x):
            if x <= start:
                return 0
            if period == 0:
                return 1
            return min(count, (x - start + period - 1) // period)

        n = f(lim)
        for a, b in merged:
            if a < lim <= b:
                n -= f(lim) - f(a)
        counts[name] = n
        i = 0
        while i < count and i < k:
            s = start + i * period
            d = delivery(s)
            if d >= lim:
                break
            events.append((d, prio, s, idx, i))
            i += 1
    events.sort()
    return {"log": [(d, T[idx][0], i) for (d, prio, s, idx, i) in events[:k]], "counts": counts}
''')

task("v4_18_book_rooms", r'''
Write `book_rooms(rooms, requests)` that books meetings online, one request at a time in the
given order. All numbers are ints (bool is not an int).
- `rooms`: list or tuple of 1..20 tuples (name, capacity, gap). name is a unique non-empty
  str, 1 <= capacity <= 1000, 0 <= gap <= 10**9. After a meeting the room needs `gap` time
  units of cleaning, so a meeting [s, e) occupies its room over the half-open interval
  [s, e + gap), using that room's own gap.
- `requests`: list or tuple of at most 200 tuples (id, start, end, size, pref, flex). id is a
  unique non-empty str; 0 <= start < end <= 10**9; 1 <= size <= 1000; pref is None or the
  name of a room (an unknown name is a ValueError); 0 <= flex <= 10**9.
A room is eligible for a request if its capacity >= size, and it is free at shift d if the
interval [start + d, end + d + gap) intersects no interval already booked in that room (two
half-open intervals intersect when each starts before the other ends; touching is fine).
Handling one request: find the smallest shift d in 0..flex for which at least one eligible
room is free; if there is none, the request is rejected and changes nothing. Otherwise, among
the eligible rooms free at that d: take the room named by pref if it is among them (a pref
that is too small or busy is simply ignored, not an error); otherwise take the room with the
smallest capacity, ties by smaller gap, remaining ties by earlier position in `rooms`. The
meeting is booked as [start + d, end + d + gap) in that room.
Return a dict with two keys. "assign": a list with one entry per request, in request order:
None if rejected, else the tuple (room_name, start + d). "busy": a dict mapping every room
name (also unused ones) to the total length of the intervals booked in it, gaps included.
Times go up to 10**9 and flex up to 10**9, so d cannot be tried one unit at a time; the
answer must be immediate. Anything invalid (wrong types or ranges, duplicate or empty names
and ids, an unknown pref, too many items, start >= end) is a ValueError, checked before any
request is handled.
Example: rooms [("A", 4, 2), ("B", 10, 0)] and requests [("m1", 0, 10, 3, None, 0),
("m2", 5, 8, 3, None, 0), ("m3", 5, 8, 3, None, 7), ("m4", 12, 14, 3, "B", 0)] give
{"assign": [("A", 0), ("B", 5), ("B", 8), ("B", 12)], "busy": {"A": 12, "B": 8}}: m1 takes the
smaller room A (occupied [0, 12)); m2 finds A busy and takes B; m3 would fit A only at d = 7
but fits B already at d = 3, so d = 3 and B; m4 finds A and B free and takes its pref B.
''', r'''
import random

def bad(*a):
    try:
        book_rooms(*a)
    except ValueError:
        return True
    return False

R0 = [("A", 4, 2), ("B", 10, 0)]
r = book_rooms(R0, [("m1", 0, 10, 3, None, 0), ("m2", 5, 8, 3, None, 0), ("m3", 5, 8, 3, None, 7), ("m4", 12, 14, 3, "B", 0)])
assert r == {"assign": [("A", 0), ("B", 5), ("B", 8), ("B", 12)], "busy": {"A": 12, "B": 8}}, r
assert book_rooms(R0, []) == {"assign": [], "busy": {"A": 0, "B": 0}}
assert book_rooms([("only", 5, 0)], [("x", 0, 5, 6, None, 0)]) == {"assign": [None], "busy": {"only": 0}}
# gap is applied to the room being booked, after the meeting; touching is fine
r = book_rooms([("A", 4, 3)], [("a", 0, 5, 1, None, 0), ("b", 8, 9, 1, None, 0), ("c", 7, 9, 1, None, 0), ("d", 9, 10, 1, None, 0)])
assert r == {"assign": [("A", 0), ("A", 8), None, None], "busy": {"A": 8 + 4}}, r
r = book_rooms([("A", 4, 3)], [("a", 5, 6, 1, None, 0), ("b", 0, 5, 1, None, 0), ("c", 0, 3, 1, None, 0), ("d", 0, 2, 1, None, 0)])
assert r == {"assign": [("A", 5), None, None, ("A", 0)], "busy": {"A": 4 + 5}}, r
# the new meeting's own gap blocks it before an existing booking
r = book_rooms([("A", 4, 3)], [("a", 10, 12, 1, None, 0), ("b", 0, 8, 1, None, 0), ("c", 0, 7, 1, None, 0)])
assert r == {"assign": [("A", 10), None, ("A", 0)], "busy": {"A": 5 + 10}}, r
# tie-breaks: capacity, then gap, then position
rooms = [("p", 5, 2), ("q", 5, 1), ("r", 5, 1), ("s", 3, 9), ("t", 8, 0)]
r = book_rooms(rooms, [("1", 0, 1, 4, None, 0), ("2", 0, 1, 4, None, 0), ("3", 0, 1, 4, None, 0), ("4", 0, 1, 4, None, 0), ("5", 0, 1, 4, None, 0), ("6", 0, 1, 4, None, 0)])
assert [x[0] if x else None for x in r["assign"]] == ["q", "r", "p", "t", None, None], r
r = book_rooms(rooms, [("1", 0, 1, 2, None, 0), ("2", 0, 1, 2, None, 0)])
assert [x[0] for x in r["assign"]] == ["s", "q"]
# pref: used when free and eligible, ignored otherwise
r = book_rooms(rooms, [("1", 0, 1, 2, "t", 0), ("2", 0, 1, 2, "t", 0), ("3", 0, 1, 7, "s", 0), ("4", 0, 1, 7, "p", 0)])
assert [x[0] if x else None for x in r["assign"]] == ["t", "s", None, None], r
# smallest shift wins over a pref that is free only later
r = book_rooms([("A", 5, 0), ("B", 5, 0)], [("1", 0, 4, 1, None, 0), ("2", 0, 4, 1, None, 0), ("3", 2, 4, 1, "A", 9)])
assert r["assign"] == [("A", 0), ("B", 0), ("A", 4)], r
r = book_rooms([("A", 5, 0), ("B", 5, 0)], [("1", 0, 4, 1, None, 0), ("2", 0, 5, 1, None, 0), ("3", 2, 4, 1, "B", 9)])
assert r["assign"] == [("A", 0), ("B", 0), ("A", 4)], r
# flex limits
r = book_rooms([("A", 5, 1)], [("1", 0, 4, 1, None, 0), ("2", 0, 2, 1, None, 4), ("3", 0, 2, 1, None, 4)])
assert r["assign"] == [("A", 0), None, None], r
r = book_rooms([("A", 5, 1)], [("1", 0, 4, 1, None, 0), ("2", 0, 2, 1, None, 5), ("3", 0, 2, 1, None, 8)])
assert r["assign"] == [("A", 0), ("A", 5), ("A", 8)], r
assert r["busy"] == {"A": 5 + 3 + 3}, r
# shifting skips over several bookings and fits gaps between them
r = book_rooms([("A", 5, 0)], [("1", 0, 3, 1, None, 0), ("2", 5, 8, 1, None, 0), ("3", 10, 13, 1, None, 0), ("4", 0, 2, 1, None, 100), ("5", 0, 3, 1, None, 100), ("6", 0, 3, 1, None, 100)])
assert r["assign"] == [("A", 0), ("A", 5), ("A", 10), ("A", 3), ("A", 13), ("A", 16)], r
# big numbers
G = 10**9
r = book_rooms([("A", 5, G), ("B", 6, 0)], [("1", 0, G, 5, None, 0), ("2", 0, G, 5, None, 0), ("3", 0, G, 5, None, G), ("4", 0, 1, 5, "A", G)])
assert r["assign"] == [("A", 0), ("B", 0), ("B", G), None], r
r = book_rooms([("A", 5, G), ("B", 6, 0)], [("1", 0, G - 5, 5, None, 0), ("2", 0, G, 5, None, 0), ("3", 0, G, 5, None, G), ("4", G - 1, G, 5, "B", G)])
assert r["assign"] == [("A", 0), ("B", 0), ("B", G), ("A", 2 * G - 5)], r
assert r["busy"] == {"A": 3 * G - 4, "B": 2 * G}, r
# validation
rq = [("m", 0, 1, 1, None, 0)]
for args in [
    ([], rq), (None, rq), ("AB", rq), ([("A", 1, 0)] * 2, rq), ([("", 1, 0)], rq), ([(1, 1, 0)], rq), ([("A", 0, 0)], rq), ([("A", 1001, 0)], rq),
    ([("A", 1, -1)], rq), ([("A", 1, G + 1)], rq), ([("A", 1.0, 0)], rq), ([("A", True, 0)], rq), ([("A", 1, False)], rq), ([("A", 1)], rq),
    ([("A", 1, 0, 0)], rq), ([("r%d" % i, 1, 0) for i in range(21)], rq), ([("A", 1, 0)], None), ([("A", 1, 0)], "m"),
    ([("A", 1, 0)], [("m", 1, 1, 1, None, 0)]), ([("A", 1, 0)], [("m", 2, 1, 1, None, 0)]), ([("A", 1, 0)], [("m", -1, 1, 1, None, 0)]),
    ([("A", 1, 0)], [("m", 0, G + 1, 1, None, 0)]), ([("A", 1, 0)], [("m", 0, 1, 0, None, 0)]), ([("A", 1, 0)], [("m", 0, 1, 1001, None, 0)]),
    ([("A", 1, 0)], [("m", 0, 1, 1, "Z", 0)]), ([("A", 1, 0)], [("m", 0, 1, 1, 5, 0)]), ([("A", 1, 0)], [("m", 0, 1, 1, ["A"], 0)]),
    ([("A", 1, 0)], [("m", 0, 1, 1, None, -1)]), ([("A", 1, 0)], [("m", 0, 1, 1, None, G + 1)]), ([("A", 1, 0)], [("m", 0, 1, 1, None, True)]),
    ([("A", 1, 0)], [("m", 0.0, 1, 1, None, 0)]), ([("A", 1, 0)], [("m", 0, 1, True, None, 0)]), ([("A", 1, 0)], [("", 0, 1, 1, None, 0)]),
    ([("A", 1, 0)], [(7, 0, 1, 1, None, 0)]), ([("A", 1, 0)], [("m", 0, 1, 1, None, 0)] * 2), ([("A", 1, 0)], [("m", 0, 1, 1, None)]),
    ([("A", 1, 0)], [("m%d" % i, 0, 1, 1, None, 0) for i in range(201)]),
    ([("A", 1, 0)], [("m", 0, 1, 1, None, 0), ("n", 0, 1, 1, "Z", 0)]),
]:
    assert bad(*args), args
assert not bad([("r%d" % i, 1, 0) for i in range(20)], [("m%d" % i, 0, 1, 1, None, 0) for i in range(200)])
assert not bad(tuple(R0), (("m", 0, 1, 1, "A", 0),))

# oracle: occupancy sets on a unit grid, shifts tried one by one
def grid_oracle(rooms, reqs):
    occ = {n: set() for (n, c, g) in rooms}
    out = []
    for (rid, s, e, size, pref, flex) in reqs:
        placed = None
        for d in range(flex + 1):
            free = []
            for ri, (n, c, g) in enumerate(rooms):
                if c >= size and not any(t in occ[n] for t in range(s + d, e + d + g)):
                    free.append((0 if n == pref else 1, c, g, ri))
            if free:
                _, c, g, ri = min(free)
                n = rooms[ri][0]
                for t in range(s + d, e + d + g):
                    occ[n].add(t)
                placed = (n, s + d)
                break
        out.append(placed)
    return {"assign": out, "busy": {n: len(occ[n]) for n in occ}}

def gen_case():
    nr = random.randint(1, 4)
    rooms = [("r%d" % i, random.choice([2, 4, 4, 6, 10]), random.choice([0, 0, 1, 2, 3])) for i in range(nr)]
    reqs = []
    for i in range(random.randint(1, 14)):
        s = random.randint(0, 40)
        reqs.append(("q%d" % i, s, s + random.randint(1, 6), random.randint(1, 10), random.choice([None, None] + [r[0] for r in rooms]), random.choice([0, 0, 2, 5, 10, 20])))
    return rooms, reqs

random.seed(4018)
cases = []
placed = shifted = rejected = prefhit = 0
for _ in range(300):
    rooms, reqs = gen_case()
    exp = grid_oracle(rooms, reqs)
    got = book_rooms(random.choice([rooms, tuple(rooms)]), reqs)
    assert got == exp, (rooms, reqs, got, exp)
    for (rid, s, e, size, pref, flex), a in zip(reqs, exp["assign"]):
        placed += a is not None
        rejected += a is None
        shifted += a is not None and a[1] != s
        prefhit += a is not None and a[0] == pref
    cases.append((rooms, reqs, exp))
assert placed > 1000 and rejected > 500 and shifted > 80 and prefhit > 200, (placed, rejected, shifted, prefhit)

# the same cases with all times multiplied by f
for rooms, reqs, exp in cases[:100]:
    f = random.choice([10**6, 10**7, 12345678])
    R2 = [(n, c, g * f) for (n, c, g) in rooms]
    Q2 = [(i, s * f, e * f, z, p, fl * f) for (i, s, e, z, p, fl) in reqs]
    want = {"assign": [None if a is None else (a[0], a[1] * f) for a in exp["assign"]], "busy": {n: v * f for n, v in exp["busy"].items()}}
    assert book_rooms(R2, Q2) == want, (R2, Q2)
''', r'''
def book_rooms(rooms, requests):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    if not isinstance(rooms, (list, tuple)) or not 1 <= len(rooms) <= 20:
        raise ValueError("rooms")
    if not isinstance(requests, (list, tuple)) or len(requests) > 200:
        raise ValueError("requests")
    names, cap, gap = [], [], []
    for r in rooms:
        if not isinstance(r, (list, tuple)) or len(r) != 3:
            raise ValueError("room")
        n, c, g = r
        if not isinstance(n, str) or not n or n in names:
            raise ValueError("room name")
        if not (isint(c) and 1 <= c <= 1000 and isint(g) and 0 <= g <= 10 ** 9):
            raise ValueError("room numbers")
        names.append(n)
        cap.append(c)
        gap.append(g)
    reqs = []
    ids = set()
    for q in requests:
        if not isinstance(q, (list, tuple)) or len(q) != 6:
            raise ValueError("request")
        rid, s, e, size, pref, flex = q
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError("id")
        ids.add(rid)
        if not all(isint(v) for v in (s, e, size, flex)):
            raise ValueError("int")
        if not (0 <= s < e <= 10 ** 9 and 1 <= size <= 1000 and 0 <= flex <= 10 ** 9):
            raise ValueError("range")
        if pref is not None and (not isinstance(pref, str) or pref not in names):
            raise ValueError("pref")
        reqs.append((s, e, size, None if pref is None else names.index(pref), flex))
    booked = [[] for _ in names]
    busy = [0] * len(names)
    out = []
    for s, e, size, pref, flex in reqs:
        elig = [i for i in range(len(names)) if cap[i] >= size]
        shifts = {0}
        for i in elig:
            for a, b in booked[i]:
                if 0 < b - s <= flex:
                    shifts.add(b - s)
        done = None
        for d in sorted(shifts):
            free = [i for i in elig if all(s + d >= b or e + d + gap[i] <= a for a, b in booked[i])]
            if free:
                if pref in free:
                    i = pref
                else:
                    i = min(free, key=lambda j: (cap[j], gap[j], j))
                booked[i].append((s + d, e + d + gap[i]))
                busy[i] += e - s + gap[i]
                done = (names[i], s + d)
                break
        out.append(done)
    return {"assign": out, "busy": dict(zip(names, busy))}
''')
task("v4_19_leap_clock", r'''
Write `leap_label(n, leaps)` and `leap_count(label, leaps)` for a UTC clock that counts real
seconds and has leap seconds. Dates are proleptic Gregorian.
- `leaps`: list or tuple of at most 200 entries (year, month, delta), each a list or tuple of
  3 ints (bool is not an int) with 1970 <= year <= 9998, 1 <= month <= 12, delta 1 or -1, in strictly increasing
  (year, month) order. The leap second happens at the very end of the last day of that
  month. With delta = 1 that day has 86401 seconds and its last second is labelled 23:59:60.
  With delta = -1 that day has 86399 seconds: the labels run through 23:59:58 and the next
  second is 00:00:00 of the next day (23:59:59 does not exist on that day). All other days
  have 86400 seconds, labelled 00:00:00 .. 23:59:59.
- n counts real seconds elapsed since the label 1970-01-01 00:00:00, which is n = 0.
  Leap seconds are counted; the first day of the clock is a normal day unless a leap falls
  in January 1970.
- `leap_label(n, leaps)` returns the label of second n as the str "YYYY-MM-DD hh:mm:ss"
  (zero padded, 4-digit year, 24-hour clock). n must be an int >= 0 (not a bool); a label
  with a year above 9999 is a ValueError.
- `leap_count(label, leaps)` is the inverse and returns the int n. label must be a str of
  exactly that format: ASCII digits only, one space, nothing before or after. The date must
  exist and have a year in 1970..9999; hh 0..23, mm 0..59, ss 0..59, or ss = 60 which is
  allowed only for 23:59:60 on a day that ends with a +1 leap second. A label that does not
  exist on its day (23:59:60 on any other day, 23:59:59 on a -1 day) is a ValueError.
`leaps` is validated first in both functions; anything invalid is a ValueError. Years up to
9999 must work for any valid input in well under a second.
Examples with leaps = [(1972, 6, 1), (1972, 12, 1)]: leap_label(78796799, leaps) is
"1972-06-30 23:59:59", leap_label(78796800, leaps) is "1972-06-30 23:59:60", and
leap_label(78796801, leaps) is "1972-07-01 00:00:00". With leaps = [(1970, 1, -1)],
leap_count("1970-02-01 00:00:00", leaps) is 2678399 and leap_label(2678398, leaps) is
"1970-01-31 23:59:58".
''', r'''
import random, datetime, calendar
from bisect import bisect_right

def bad(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

L72 = [(1972, 6, 1), (1972, 12, 1)]
assert leap_label(0, []) == "1970-01-01 00:00:00"
assert leap_label(86399, []) == "1970-01-01 23:59:59"
assert leap_label(86400, ()) == "1970-01-02 00:00:00"
assert leap_label(78796799, L72) == "1972-06-30 23:59:59"
assert leap_label(78796800, L72) == "1972-06-30 23:59:60"
assert leap_label(78796801, L72) == "1972-07-01 00:00:00"
assert leap_label(78796800, [(1972, 6, 1)]) == "1972-06-30 23:59:60"
assert leap_count("1972-06-30 23:59:60", L72) == 78796800
assert leap_count("1972-07-01 00:00:00", L72) == 78796801
assert leap_count("1972-06-30 23:59:59", L72) == 78796799
LN = [(1970, 1, -1)]
assert leap_count("1970-02-01 00:00:00", LN) == 2678399
assert leap_label(2678398, LN) == "1970-01-31 23:59:58"
assert leap_label(2678399, LN) == "1970-02-01 00:00:00"
assert leap_count("1970-01-31 23:59:58", LN) == 2678398
assert leap_count("1970-01-31 23:59:59", [(1970, 2, -1)]) == 2678399
assert bad(leap_count, "1970-01-31 23:59:59", LN)
assert bad(leap_count, "1970-01-31 23:59:60", LN)
assert bad(leap_count, "1970-01-30 23:59:60", L72)
assert bad(leap_count, "1972-06-30 23:59:60", [(1972, 7, 1)])
assert bad(leap_count, "1972-06-30 23:59:60", [])
assert bad(leap_count, "1972-06-30 23:58:60", L72)
assert bad(leap_count, "1972-06-30 22:59:60", L72)
assert bad(leap_count, "1972-12-30 23:59:60", L72)
assert leap_count("1972-12-31 23:59:60", L72) == leap_count("1973-01-01 00:00:00", L72) - 1
assert leap_count("1973-01-01 00:00:00", L72) == 1096 * 86400 + 2
# consecutive months, mixed signs
LC = [(1999, 1, 1), (1999, 2, -1), (1999, 3, 1)]
assert leap_count("1999-01-31 23:59:60", LC) - leap_count("1999-01-31 23:59:59", LC) == 1
assert leap_count("1999-02-01 00:00:00", LC) - leap_count("1999-01-31 23:59:60", LC) == 1
assert leap_count("1999-03-01 00:00:00", LC) - leap_count("1999-02-28 23:59:58", LC) == 1
assert leap_count("1999-03-31 23:59:60", LC) - leap_count("1999-03-01 00:00:00", LC) == 31 * 86400
assert leap_count("1999-04-01 00:00:00", LC) - leap_count("1999-01-01 00:00:00", LC) == 90 * 86400 + 1
# the end of the clock
tot = sum(e[2] for e in LC)
last = (datetime.datetime(9999, 12, 31, 23, 59, 59) - datetime.datetime(1970, 1, 1)).days * 86400 + 86399 + tot
assert leap_label(last, LC) == "9999-12-31 23:59:59"
assert bad(leap_label, last + 1, LC)
assert leap_count("9999-12-31 23:59:59", LC) == last
assert leap_count("1970-01-01 00:00:00", LC) == 0
assert bad(leap_label, 10**30, [])
for a in [-1, 1.0, True, "5", None, [5]]:
    assert bad(leap_label, a, []), a
for lb in ["1969-12-31 23:59:59", "10000-01-01 00:00:00", "1970-1-01 00:00:00", "1970-01-01 0:00:00", "1970-01-01T00:00:00", "1970-01-01  00:00:00", " 1970-01-01 00:00:00",
           "1970-01-01 00:00:00 ", "1970-01-01 00:00:00\n", "1970-01-01 00:00:61", "1970-01-01 24:00:00", "1970-01-01 00:60:00", "1970-13-01 00:00:00", "1970-00-01 00:00:00",
           "1970-01-00 00:00:00", "1970-02-29 00:00:00", "1971-02-29 00:00:00", "1900-02-28 00:00:00", "1970-04-31 00:00:00", "１970-01-01 00:00:00",
           "1970-01-01 ٠٠:00:00", "1970/01/01 00:00:00", "1970-01-01", "", "9999-12-31 23:59:60", "1970-01-01 00:00:60", "-970-01-01 00:00:00", "+970-01-01 00:00:00"]:
    assert bad(leap_count, lb, []), lb
for lb in [None, 5, b"1970-01-01 00:00:00", ["1970-01-01 00:00:00"]]:
    assert bad(leap_count, lb, []), lb
assert leap_count("2000-02-29 12:00:00", []) == (datetime.date(2000, 2, 29) - datetime.date(1970, 1, 1)).days * 86400 + 43200
assert bad(leap_count, "2100-02-29 12:00:00", [])
BAD_LEAPS = [[(1972, 12, 1), (1972, 6, 1)], [(1972, 6, 1), (1972, 6, 1)], [(1972, 6, 1), (1972, 6, -1)], [(1972, 13, 1)], [(1972, 0, 1)], [(1969, 12, 1)], [(9999, 1, 1)],
             [(1972, 6, 0)], [(1972, 6, 2)], [(1972, 6, True)], [(1972.0, 6, 1)], [(1972, 6, 1.0)], [(1972, 6)], [(1972, 6, 1, 1)], [(True, 6, 1)], [(1972, False, 1)], ["x"], [None],
             None, 5, "ab", {(1972, 6, 1)}, [(1972, 6, 1)] * 2, [(1970 + i // 12, i % 12 + 1, 1) for i in range(201)]]
for lp in BAD_LEAPS:
    assert bad(leap_label, 5, lp), lp
    assert bad(leap_count, "1970-01-01 00:00:00", lp), lp
assert not bad(leap_label, 5, [(1970 + i // 12, i % 12 + 1, 1) for i in range(200)])
assert not bad(leap_label, 5, [(9998, 12, -1)])
assert not bad(leap_label, 5, [[1972, 6, 1], (1972, 12, -1)])

# oracle: walk the days one by one with datetime and lay the seconds end to end
def build(leaps):
    extra = {}
    for (y, m, dl) in leaps:
        extra[datetime.date(y, m, calendar.monthrange(y, m)[1])] = dl
    days, starts, lens, idx = [], [], [], {}
    t = 0
    day = datetime.date(1970, 1, 1)
    one = datetime.timedelta(1)
    while day.year < 2034:
        ln = 86400 + extra.get(day, 0)
        idx[day] = len(days)
        days.append(day)
        starts.append(t)
        lens.append(ln)
        t += ln
        day += one
    return days, starts, lens, idx, t

def o_label(tab, n):
    days, starts, lens, idx, total = tab
    i = bisect_right(starts, n) - 1
    sod = n - starts[i]
    assert 0 <= sod < lens[i]
    if sod == 86400:
        return "%s 23:59:60" % days[i].isoformat()
    return "%s %02d:%02d:%02d" % (days[i].isoformat(), sod // 3600, sod % 3600 // 60, sod % 60)

def o_count(tab, y, m, d, hh, mi, ss):
    days, starts, lens, idx, total = tab
    try:
        dt = datetime.date(y, m, d)
    except ValueError:
        return None
    if dt not in idx or not (0 <= hh < 24 and 0 <= mi < 60 and 0 <= ss <= 60):
        return None
    if ss == 60 and not (hh == 23 and mi == 59):
        return None
    sod = hh * 3600 + mi * 60 + ss
    i = idx[dt]
    return starts[i] + sod if sod < lens[i] else None

def gen_leaps(kind):
    if kind == 0:
        return []
    if kind == 1:
        base = random.randint(1972, 1990)
        return [(base, m, random.choice([1, 1, -1])) for m in sorted(random.sample(range(1, 13), random.randint(2, 6)))]
    ym = sorted(random.sample([(y, m) for y in range(1970, 2032) for m in range(1, 13)], random.randint(8, 30)))
    return [(y, m, random.choice([1, 1, 1, -1])) for (y, m) in ym]

random.seed(4019)
nlab60 = nneg = 0
for kind in [0, 1, 2, 2, 2, 1]:
    leaps = gen_leaps(kind)
    tab = build(leaps)
    days, starts, lens, idx, total = tab
    ns = [random.randint(0, total - 1) for _ in range(120)]
    for i, ln in enumerate(lens):
        if ln != 86400:
            for dn in range(-3, 3):
                ns.append(starts[i] + ln + dn)
    for n in ns:
        n = min(max(n, 0), total - 1)
        exp = o_label(tab, n)
        got = leap_label(n, leaps)
        assert got == exp, (leaps, n, got, exp)
        y, mo, d = int(exp[:4]), int(exp[5:7]), int(exp[8:10])
        hh, mi, ss = int(exp[11:13]), int(exp[14:16]), int(exp[17:19])
        assert o_count(tab, y, mo, d, hh, mi, ss) == n
        assert leap_count(exp, tuple(leaps)) == n, (leaps, exp, n)
        nlab60 += ss == 60
    # random labels, valid and invalid
    for _ in range(150):
        dt = random.choice(days)
        if random.random() < 0.5 and any(ln != 86400 for ln in lens):
            dt = random.choice([days[i] for i, ln in enumerate(lens) if ln != 86400])
        hh, mi, ss = random.choice([(23, 59, 59), (23, 59, 60), (23, 59, 58), (random.randint(0, 23), random.randint(0, 59), random.randint(0, 59)),
                                    (random.randint(0, 23), random.randint(0, 59), 60), (0, 0, 0)])
        lab = "%s %02d:%02d:%02d" % (dt.isoformat(), hh, mi, ss)
        exp = o_count(tab, dt.year, dt.month, dt.day, hh, mi, ss)
        if exp is None:
            assert bad(leap_count, lab, leaps), (leaps, lab)
        else:
            assert leap_count(lab, leaps) == exp, (leaps, lab)
            nneg += 1
    # beyond the table: one straight line, checked with datetime arithmetic
    tot = sum(e[2] for e in leaps)
    t0 = datetime.datetime(1970, 1, 1)
    for _ in range(60):
        n = random.choice([random.randint(total, 3 * 10**9), random.randint(total, 2 * 10**11), random.randint(2 * 10**11, 3 * 10**11)])
        try:
            exp = (t0 + datetime.timedelta(seconds=n - tot)).strftime("%Y-%m-%d %H:%M:%S")
        except OverflowError:
            exp = None
        if exp is None:
            assert bad(leap_label, n, leaps), n
        else:
            assert leap_label(n, leaps) == exp, (n, exp)
            assert leap_count(exp, leaps) == n
assert nlab60 > 6 and nneg > 400, (nlab60, nneg)
''', r'''
import re
from bisect import bisect_left, bisect_right


def _isint(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _days(y, m, d):
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil(z):
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + 1 if m <= 2 else y), m, d


def _mlen(y, m):
    if m == 2:
        return 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28
    return 30 if m in (4, 6, 9, 11) else 31


def _prep(leaps):
    if not isinstance(leaps, (list, tuple)) or len(leaps) > 200:
        raise ValueError("leaps")
    days, deltas, cums, prev, c = [], [], [], None, 0
    for e in leaps:
        if not isinstance(e, (list, tuple)) or len(e) != 3:
            raise ValueError("leap")
        y, m, dl = e
        if not (_isint(y) and _isint(m) and _isint(dl)):
            raise ValueError("leap int")
        if not (1970 <= y <= 9998 and 1 <= m <= 12 and dl in (1, -1)):
            raise ValueError("leap range")
        if prev is not None and (y, m) <= prev:
            raise ValueError("leap order")
        prev = (y, m)
        days.append(_days(y, m, _mlen(y, m)))
        deltas.append(dl)
        c += dl
        cums.append(c)
    bounds = [(d + 1) * 86400 + c for d, c in zip(days, cums)]
    return days, deltas, cums, bounds


def leap_label(n, leaps):
    days, deltas, cums, bounds = _prep(leaps)
    if not _isint(n) or n < 0:
        raise ValueError("n")
    j = bisect_right(bounds, n)
    off = cums[j - 1] if j else 0
    if j < len(bounds) and deltas[j] == 1 and n == bounds[j] - 1:
        y, m, d = _civil(days[j])
        return "%04d-%02d-%02d 23:59:60" % (y, m, d)
    day, sod = divmod(n - off, 86400)
    y, m, d = _civil(day)
    if y > 9999:
        raise ValueError("year")
    return "%04d-%02d-%02d %02d:%02d:%02d" % (y, m, d, sod // 3600, sod % 3600 // 60, sod % 60)


def leap_count(label, leaps):
    days, deltas, cums, bounds = _prep(leaps)
    mt = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})", label) if isinstance(label, str) else None
    if mt is None:
        raise ValueError("format")
    y, m, d, hh, mi, ss = (int(x) for x in mt.groups())
    if not (1970 <= y <= 9999 and 1 <= m <= 12 and 1 <= d <= _mlen(y, m) and hh < 24 and mi < 60 and ss <= 60):
        raise ValueError("value")
    day = _days(y, m, d)
    j = bisect_left(days, day)
    off = cums[j - 1] if j else 0
    here = j < len(days) and days[j] == day
    if ss == 60 and not (hh == 23 and mi == 59 and here and deltas[j] == 1):
        raise ValueError("no such second")
    if (hh, mi, ss) == (23, 59, 59) and here and deltas[j] == -1:
        raise ValueError("no such second")
    return day * 86400 + off + hh * 3600 + mi * 60 + ss
''')

task("v4_20_list_schedule", r'''
Write `list_schedule(jobs, workers)` that simulates a list scheduler and returns the
schedule.
- `jobs`: list or tuple of 0..200 tuples (name, duration, deps). name is a unique non-empty
  str; duration is an int, 0 <= duration <= 10**12 (bool is not an int); deps is a list or
  tuple of names of other jobs, with no name repeated. A job can start only when every job
  in its deps has finished. An unknown dep, a repeated dep, a job that depends on itself, a
  dependency cycle, or wrong types anywhere are a ValueError (the whole input is checked
  before anything is simulated).
- `workers`: int, 1 <= workers <= 64, numbered 0 .. workers-1. A worker runs one job at a
  time, without interruption.
- Priority of a job: the largest total duration over all chains job -> j2 -> j3 ... that
  follow "is listed in the deps of" edges forward, counting every job on the chain including
  the job itself (so a job without dependents has priority equal to its own duration).
  Higher priority goes first; equal priorities go by name ascending (Python str order).
Simulation: time starts at 0 and jumps from one decision instant to the next. At an instant
t, first every running job whose finish time is t finishes, freeing its worker, so jobs
starting at t see it as finished. Then, repeatedly, while some worker is idle and some job is
ready (not started, all deps finished): the ready job with the highest priority starts at t
on the lowest-numbered idle worker. A job of duration 0 finishes at the same instant it
starts: its worker is idle again at once and its dependents may become ready and start at t
inside the same repetition. When nothing more can start at t, time jumps to the earliest
finish time of a running job.
Return {"start": {name: start time}, "worker": {name: worker number}, "makespan": the largest
finish time over all jobs, 0 when there are no jobs}. Durations go up to 10**12, so time
must not be simulated unit by unit.
Examples: jobs [("a", 3, []), ("b", 2, ["a"]), ("c", 4, ["a"]), ("d", 1, ["b", "c"])] with 2
workers give {"start": {"a": 0, "b": 3, "c": 3, "d": 7}, "worker": {"a": 0, "b": 1, "c": 0,
"d": 0}, "makespan": 8}. Jobs [("z", 0, []), ("y", 2, ["z"]), ("x", 1, [])] with 1 worker give
start {"z": 0, "y": 0, "x": 2}, worker 0 for all three, makespan 3.
''', r'''
import random

def bad(*a):
    try:
        list_schedule(*a)
    except ValueError:
        return True
    return False

J1 = [("a", 3, []), ("b", 2, ["a"]), ("c", 4, ["a"]), ("d", 1, ["b", "c"])]
assert list_schedule(J1, 2) == {"start": {"a": 0, "b": 3, "c": 3, "d": 7}, "worker": {"a": 0, "b": 1, "c": 0, "d": 0}, "makespan": 8}
assert list_schedule(tuple(J1), 1) == {"start": {"a": 0, "c": 3, "b": 7, "d": 9}, "worker": {"a": 0, "b": 0, "c": 0, "d": 0}, "makespan": 10}
J2 = [("z", 0, []), ("y", 2, ["z"]), ("x", 1, [])]
assert list_schedule(J2, 1) == {"start": {"z": 0, "y": 0, "x": 2}, "worker": {"z": 0, "y": 0, "x": 0}, "makespan": 3}
assert list_schedule([], 3) == {"start": {}, "worker": {}, "makespan": 0}
assert list_schedule([("only", 0, [])], 2) == {"start": {"only": 0}, "worker": {"only": 0}, "makespan": 0}
# ties by name in str order (upper case first, "a10" before "a2")
r = list_schedule([("b", 2, []), ("B", 2, []), ("a10", 2, []), ("a2", 2, [])], 1)
assert r["start"] == {"B": 0, "a10": 2, "a2": 4, "b": 6}, r
# higher priority beats the name, and a long chain beats a long single job
r = list_schedule([("a", 5, []), ("b", 2, []), ("c", 4, ["b"])], 1)
assert r["start"] == {"b": 0, "a": 2, "c": 7}, r
r = list_schedule([("a", 6, []), ("b", 2, []), ("c", 4, ["b"])], 1)
assert r["start"] == {"a": 0, "b": 6, "c": 8}, r
# lowest idle worker, workers freed at the same instant
r = list_schedule([("p", 5, []), ("q", 4, []), ("s", 3, []), ("t", 3, ["q"]), ("u", 1, ["p", "s"])], 3)
assert r["start"] == {"p": 0, "q": 0, "s": 0, "t": 4, "u": 5} and r["worker"] == {"q": 0, "p": 1, "s": 2, "t": 0, "u": 1}, r
# a job finishing at t counts as finished for a job starting at t
r = list_schedule([("a", 5, []), ("b", 5, []), ("c", 1, ["a", "b"])], 2)
assert r["start"]["c"] == 5 and r["worker"]["c"] == 0 and r["makespan"] == 6, r
# zero-duration chains resolve inside one instant and keep priority order
r = list_schedule([("z1", 0, []), ("z2", 0, ["z1"]), ("w", 3, ["z2"]), ("v", 1, []), ("u", 2, [])], 1)
assert r["start"] == {"z1": 0, "z2": 0, "w": 0, "u": 3, "v": 5}, r
r = list_schedule([("m", 4, []), ("z", 0, []), ("n", 3, ["z"])], 2)
assert r["start"] == {"m": 0, "z": 0, "n": 0} and r["worker"] == {"m": 0, "z": 1, "n": 1}, r
# zero jobs are dependency edges too
r = list_schedule([("a", 2, []), ("z", 0, ["a"]), ("b", 1, ["z"])], 2)
assert r["start"] == {"a": 0, "z": 2, "b": 2} and r["worker"] == {"a": 0, "z": 0, "b": 0}, r
# dependencies may be listed after their dependents
r = list_schedule([("c", 1, ["b"]), ("b", 1, ["a"]), ("a", 1, [])], 4)
assert r["start"] == {"a": 0, "b": 1, "c": 2} and r["makespan"] == 3, r
# big numbers
E = 10**12
r = list_schedule([("a", E, []), ("b", E, []), ("c", E, ["a", "b"]), ("d", E, ["c"])], 2)
assert r == {"start": {"a": 0, "b": 0, "c": E, "d": 2 * E}, "worker": {"a": 0, "b": 1, "c": 0, "d": 0}, "makespan": 3 * E}, r
chain = [("j%03d" % i, E, ["j%03d" % (i - 1)] if i else []) for i in range(200)]
r = list_schedule(chain, 64)
assert r["makespan"] == 200 * E and r["start"]["j199"] == 199 * E and set(r["worker"].values()) == {0}
r = list_schedule([("x%d" % i, E - i, []) for i in range(130)], 64)
assert r["makespan"] == 3 * E - 255 and r["start"]["x64"] == E - 63 and r["start"]["x128"] == 2 * E - 127, r
assert r["worker"]["x128"] == 0 and r["worker"]["x129"] == 1 and r["worker"]["x64"] == 63 and r["worker"]["x127"] == 0, r
# validation
for args in [
    ([("a", 1, ["a"])], 1), ([("a", 1, ["b"]), ("b", 1, ["a"])], 1), ([("a", 1, ["b"]), ("b", 1, ["c"]), ("c", 1, ["a"])], 2),
    ([("a", 1, ["z"])], 1), ([("a", 1, []), ("b", 1, ["a", "a"])], 1), ([("a", 1, []), ("a", 1, [])], 1), ([("", 1, [])], 1), ([(1, 1, [])], 1),
    ([("a", -1, [])], 1), ([("a", E + 1, [])], 1), ([("a", 1.0, [])], 1), ([("a", True, [])], 1), ([("a", "1", [])], 1), ([("a", 1, None)], 1),
    ([("a", 1, "b"), ("b", 1, [])], 1), ([("a", 1, [1])], 1), ([("a", 1, [None])], 1), ([("a", 1)], 1), ([("a", 1, [], 0)], 1), ("ab", 1), (None, 1), (5, 1),
    ({"a": 1}, 1), ([["a"]], 1), ([None], 1), ([("a", 1, [])], 0), ([("a", 1, [])], 65), ([("a", 1, [])], -1), ([("a", 1, [])], 1.0), ([("a", 1, [])], True),
    ([("a", 1, [])], "1"), ([("a", 1, [])], None), ([("a", 1, [])] + [("b%d" % i, 1, []) for i in range(200)], 1), ([("a", 1, [{"x": 1}])], 1),
]:
    assert bad(*args), args
assert not bad([("b%d" % i, 1, []) for i in range(200)], 64)
assert not bad([("a", 1, ()), ("b", 0, ("a",))], 1) and not bad((("a", 1, []),), 64)

# oracle: tick by tick; priority from explicit enumeration of every chain
def tick_oracle(jobs, workers):
    dur = {n: d for n, d, _ in jobs}
    deps = {n: list(ds) for n, _, ds in jobs}
    succ = {n: [m for m, _, ds in jobs if n in ds] for n in dur}
    def longest(n):
        best = 0
        def walk(v, acc):
            nonlocal best
            acc += dur[v]
            best = max(best, acc)
            for w in succ[v]:
                walk(w, acc)
        walk(n, 0)
        return best
    bl = {n: longest(n) for n in dur}
    finished, start, wk, running = set(), {}, {}, {}
    t = 0
    limit = sum(dur.values()) + 5
    while len(finished) < len(dur):
        for w, (n, e) in list(running.items()):
            if e == t:
                finished.add(n)
                del running[w]
        while True:
            idle = [w for w in range(workers) if w not in running]
            ready = [n for n in dur if n not in start and all(d in finished for d in deps[n])]
            if not idle or not ready:
                break
            n = min(ready, key=lambda x: (-bl[x], x))
            start[n] = t
            wk[n] = idle[0]
            if dur[n] == 0:
                finished.add(n)
            else:
                running[idle[0]] = (n, t + dur[n])
        t += 1
        assert t <= limit
    return {"start": start, "worker": wk, "makespan": max([start[n] + dur[n] for n in dur], default=0)}

POOL = ["a", "b", "c", "a10", "a2", "B", "j1", "j2", "j10", "zz", "Z", "m"]

def gen_dag(maxn, durs):
    n = random.randint(1, maxn)
    names = random.sample(POOL, n)
    p = random.choice([0.15, 0.3, 0.5])
    jobs = []
    for i, nm in enumerate(names):
        deps = [names[j] for j in range(i) if random.random() < p]
        random.shuffle(deps)
        jobs.append((nm, random.choice(durs), deps))
    random.shuffle(jobs)
    return jobs

random.seed(4020)
cases = []
zeros = ties = multi = 0
for _ in range(260):
    jobs = gen_dag(9, [0, 1, 1, 2, 2, 3, 4, 5, 6])
    w = random.randint(1, 4)
    exp = tick_oracle(jobs, w)
    got = list_schedule(random.choice([jobs, tuple(jobs)]), w)
    assert got == exp, (jobs, w, got, exp)
    zeros += any(j[1] == 0 for j in jobs)
    multi += len(set(exp["worker"].values())) > 1
    ties += len({exp["start"][j[0]] for j in jobs}) < len(jobs)
    cases.append((jobs, w, exp))
assert zeros > 90 and multi > 100 and ties > 120, (zeros, multi, ties)

# scaled durations give the scaled schedule
for jobs, w, exp in cases[:100]:
    f = random.choice([10**6, 10**9, 999999937])
    J2 = [(n, d * f, ds) for (n, d, ds) in jobs]
    got = list_schedule(J2, w)
    want = {"start": {n: s * f for n, s in exp["start"].items()}, "worker": exp["worker"], "makespan": exp["makespan"] * f}
    assert got == want, (J2, w)

# large random DAGs: structural checks and scale invariance
for _ in range(4):
    n = random.randint(120, 200)
    names = ["t%03d" % i for i in random.sample(range(1000), n)]
    jobs = []
    for i, nm in enumerate(names):
        deps = random.sample(names[:i], min(i, random.randint(0, 3)))
        jobs.append((nm, random.randint(0, 40), deps))
    w = random.choice([1, 3, 8, 64])
    r1 = list_schedule(jobs, w)
    fin = {nm: r1["start"][nm] + d for (nm, d, _) in jobs}
    assert r1["makespan"] == max(fin.values())
    for (nm, d, ds) in jobs:
        assert all(fin[x] <= r1["start"][nm] for x in ds)
        assert 0 <= r1["worker"][nm] < w
    for k in range(w):
        iv = sorted((r1["start"][nm], fin[nm]) for (nm, d, _) in jobs if r1["worker"][nm] == k and d > 0)
        assert all(iv[i][1] <= iv[i + 1][0] for i in range(len(iv) - 1))
    f = 10**9 + 7
    r2 = list_schedule([(nm, d * f, ds) for (nm, d, ds) in jobs], w)
    assert r2["start"] == {nm: s * f for nm, s in r1["start"].items()} and r2["worker"] == r1["worker"] and r2["makespan"] == r1["makespan"] * f
''', r'''
import heapq


def list_schedule(jobs, workers):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)

    if not isinstance(jobs, (list, tuple)) or len(jobs) > 200:
        raise ValueError("jobs")
    if not isint(workers) or not 1 <= workers <= 64:
        raise ValueError("workers")
    names, dur, raw = [], [], []
    index = {}
    for j in jobs:
        if not isinstance(j, (list, tuple)) or len(j) != 3:
            raise ValueError("job")
        name, d, deps = j
        if not isinstance(name, str) or not name or name in index:
            raise ValueError("name")
        if not isint(d) or not 0 <= d <= 10 ** 12:
            raise ValueError("duration")
        if not isinstance(deps, (list, tuple)):
            raise ValueError("deps")
        index[name] = len(names)
        names.append(name)
        dur.append(d)
        raw.append(deps)
    n = len(names)
    succ = [[] for _ in range(n)]
    indeg = [0] * n
    for u, deps in enumerate(raw):
        seen = set()
        for dep in deps:
            if not isinstance(dep, str) or dep not in index or dep in seen or index[dep] == u:
                raise ValueError("dep")
            seen.add(dep)
            succ[index[dep]].append(u)
            indeg[u] += 1
    order = [u for u in range(n) if indeg[u] == 0]
    left = indeg[:]
    for u in order:
        for v in succ[u]:
            left[v] -= 1
            if left[v] == 0:
                order.append(v)
    if len(order) < n:
        raise ValueError("cycle")
    prio = [0] * n
    for u in reversed(order):
        prio[u] = dur[u] + max((prio[v] for v in succ[u]), default=0)
    waiting = indeg[:]
    ready = [(-prio[u], names[u], u) for u in range(n) if waiting[u] == 0]
    heapq.heapify(ready)
    idle = list(range(workers))
    running = []
    start, worker = {}, {}
    done = 0
    makespan = 0
    t = 0

    def finish(u, w):
        for v in succ[u]:
            waiting[v] -= 1
            if waiting[v] == 0:
                heapq.heappush(ready, (-prio[v], names[v], v))
        heapq.heappush(idle, w)

    while done < n:
        while ready and idle:
            _, _, u = heapq.heappop(ready)
            w = heapq.heappop(idle)
            start[names[u]] = t
            worker[names[u]] = w
            makespan = max(makespan, t + dur[u])
            if dur[u] == 0:
                done += 1
                finish(u, w)
            else:
                heapq.heappush(running, (t + dur[u], w, u))
        if done == n:
            break
        t = running[0][0]
        while running and running[0][0] == t:
            _, w, u = heapq.heappop(running)
            done += 1
            finish(u, w)
    return {"start": start, "worker": worker, "makespan": makespan}
''')


task("v4_21_kth_coprime", r'''
Write `kth_coprime(n, k)` that returns the k-th smallest positive integer x with gcd(x, n) == 1
(k = 1 is the smallest such x). Both arguments must be ints (bool is not an int) with
1 <= n <= 10**12 and 1 <= k <= 10**18, otherwise raise ValueError. The result is an int.
n can be 10**12 and k can be 10**18, so counting or testing numbers one by one is impossible.
The pattern of integers coprime to n repeats with period n, and every block of n consecutive
integers holds exactly phi(n) of them, so the answer is about k * n / phi(n), which can be far
above n and far above 10**18 (it is an exact Python int, never a float).
Details that matter:
- gcd(x, 1) == 1 for every x, so kth_coprime(1, k) == k.
- For n >= 2 the multiples of n are never in the sequence, but n + 1, 2n + 1, ... are, and
  so is 1. For n == 2 the sequence is the odd numbers 1, 3, 5, ...
- The k-th number may sit in a later period than the first one, and k may be a multiple of
  phi(n) (the last coprime number of a period is then the answer, not the first of the next).
- n has at most 11 distinct prime factors; trial division up to 10**6 is enough to factor it.
Examples: the integers coprime to 12 are 1, 5, 7, 11, 13, 17, 19, 23, 25, 29, 31, 35, 37, ...
so kth_coprime(12, 1) == 1, kth_coprime(12, 4) == 11 (the last of the first period),
kth_coprime(12, 5) == 13, kth_coprime(12, 9) == 25; kth_coprime(1, 7) == 7;
kth_coprime(2, 10**18) == 2 * 10**18 - 1.
''', r'''
import random
from math import gcd

def brute(n, k):
    x = 0
    while k:
        x += 1
        if gcd(x, n) == 1:
            k -= 1
    return x

def same(n, k, exp):
    got = kth_coprime(n, k)
    assert type(got) is int and got == exp, (n, k, got, exp)

def rej(*a):
    try:
        kth_coprime(*a)
    except ValueError:
        return True
    return False

def count_le(x, primes):
    def rec(i, d, s):
        if i == len(primes):
            return s * (x // d)
        return rec(i + 1, d, s) + rec(i + 1, d * primes[i], -s)
    return rec(0, 1, 1)

def check_big(n, primes, k):
    prod = 1
    for q in primes:
        prod *= q
    got = kth_coprime(n, k)
    assert type(got) is int and got >= 1 and gcd(got, n) == 1, (n, k, got)
    # got is coprime and exactly k coprime numbers lie in [1, got]: it is the k-th one
    assert count_le(got, primes) == k, (n, k, got)

for n, k, e in [(12, 1, 1), (12, 4, 11), (12, 5, 13), (12, 9, 25), (1, 7, 7), (1, 1, 1), (2, 1, 1), (2, 2, 3),
                (2, 10**18, 2 * 10**18 - 1), (1, 10**18, 10**18), (6, 2, 5), (6, 3, 7), (30, 8, 29), (30, 9, 31),
                (10, 4, 9), (10, 5, 11), (7, 6, 6), (7, 7, 8), (4, 3, 5)]:
    same(n, k, e)
    if k <= 10**4:
        same(n, k, brute(n, k))

for n in (3, 4, 9, 10, 30, 210, 97, 100):
    phi = sum(1 for x in range(1, n + 1) if gcd(x, n) == 1)
    for k in (phi - 1, phi, phi + 1, 2 * phi, 2 * phi + 1, 5 * phi, 5 * phi + 1):
        if k >= 1:
            same(n, k, brute(n, k))

BIG = [(10**12, [2, 5]), (999999999989, [999999999989]), (200560490130, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]),
       (2**39, [2]), (3**25, [3]), (999999999999, [3, 7, 11, 13, 37, 101, 9901]),
       (999983 * 999979, [999983, 999979]), (2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23, [2, 3, 5, 7, 11, 13, 17, 19, 23])]
for n, pr in BIG:
    prod = 1
    for q in pr:
        prod *= q
    phi = count_le(n, pr)
    ks = (1, phi, phi + 1, 10**18, 123456789012345678) if max(pr) > 10**5 else (1, 2, phi - 1, phi, phi + 1, 2 * phi, 10**18, 10**18 - 1, 123456789012345678)
    for k in ks:
        if 1 <= k <= 10**18:
            check_big(n, pr, k)

# mid-size n where the period fits: count by direct scan
for n in (360, 1155, 4096, 30030):
    phi = sum(1 for x in range(1, n + 1) if gcd(x, n) == 1)
    cop = [x for x in range(1, n + 1) if gcd(x, n) == 1]
    for k in (1, 7, phi // 2, phi, phi + 1, 3 * phi + 5, 10**6 + 3):
        q, r = divmod(k - 1, phi)
        same(n, k, q * n + cop[r])

random.seed(4021)
for _ in range(300):
    n = random.choice([random.randint(1, 40), random.randint(1, 400), random.choice([6, 12, 30, 60, 210, 36, 48, 64, 81, 97])])
    k = random.choice([random.randint(1, 60), random.randint(1, 800)])
    same(n, k, brute(n, k))

POOL = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 101, 9901, 99991]
cases = 0
while cases < 70:
    n, pr = 1, []
    for q in random.sample(POOL, random.randint(1, 8)):
        e = random.choice([1, 1, 1, 2, 3])
        if n * q ** e <= 10**12:
            n *= q ** e
            pr.append(q)
    if n == 1:
        continue
    k = random.choice([random.randint(1, 10**18), int(10 ** random.uniform(0, 18)) or 1, random.randint(1, 10**6)])
    check_big(n, pr, min(k, 10**18))
    cases += 1

for bad in (0, -5, 10**12 + 1, 10**13, 1.0, "6", None, True, [6], 12.5):
    assert rej(bad, 5), bad
for bad in (0, -1, 10**18 + 1, 2.0, "3", None, False, True, [3], 10**30):
    assert rej(12, bad), bad
assert rej(0, 0) and rej(True, True) and rej(10**12 + 1, 10**18 + 1)
same(10**12, 10**18, kth_coprime(10**12, 10**18))
''', r'''
def kth_coprime(n, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not isint(k) or not 1 <= n <= 10 ** 12 or not 1 <= k <= 10 ** 18:
        raise ValueError("range")
    primes = []
    m = n
    p = 2
    while p * p <= m:
        if m % p == 0:
            primes.append(p)
            while m % p == 0:
                m //= p
        p += 1 if p == 2 else 2
    if m > 1:
        primes.append(m)
    terms = [(1, 1)]
    for q in primes:
        terms += [(d * q, -s) for d, s in terms]

    def cnt(x):
        return sum(s * (x // d) for d, s in terms)

    phi = cnt(n)
    q, r = divmod(k - 1, phi)
    lo, hi = 1, n
    while lo < hi:
        mid = (lo + hi) // 2
        if cnt(mid) >= r + 1:
            hi = mid
        else:
            lo = mid + 1
    return q * n + lo
''')

task("v4_22_bounded_compositions", r'''
Write `bounded_compositions(n, k, lo, hi, p)` that returns, modulo the prime p, the number of
ordered k-tuples (x1, ..., xk) of integers with lo <= xi <= hi for every i and
x1 + x2 + ... + xk == n. Tuples that differ only in the order of their entries are different
tuples (these are compositions, not partitions).
All five arguments must be ints (bool is not an int), with 1 <= k <= 200,
0 <= lo <= hi <= 10**12, 0 <= n <= 10**15, and p a prime with 2 <= p <= 10**9 + 7. Anything
else is a ValueError, and so is a composite p (including every p that is not prime but passes
the range test). The result is an int in range(p): it is 0 when no tuple exists (for example
when n < k * lo or n > k * hi), and when the true count is a multiple of p.
The counts are astronomically large and n may exceed p by many orders of magnitude (for
example p = 2 or p = 7 with n near 10**15). The answer must be the true count reduced modulo
p, so binomial coefficients of huge top arguments have to be taken modulo a prime that may
be far smaller than the top argument; tables of factorials, or dividing by factorials that
contain the factor p, give wrong answers there. A float, or an arithmetic result that is
only right when n < p, is wrong.
Examples: bounded_compositions(5, 2, 0, 5, 7) == 6 (the tuples (0, 5), (1, 4), ..., (5, 0)).
The tuples with 3 entries in 1..3 that sum to 6 are the 6 permutations of (1, 2, 3) and
(2, 2, 2), 7 in all, so bounded_compositions(6, 3, 1, 3, 5) == 2.
bounded_compositions(3, 1, 5, 6, 7) == 0.
bounded_compositions(10**12, 3, 0, 10**12, 2) == 1 (the exact count is (10**12 + 2) *
(10**12 + 1) // 2, which is odd).
''', r'''
import random
from math import comb

def same(args, exp):
    got = bounded_compositions(*args)
    assert type(got) is int and got == exp, (args, got, exp)

def rej(*a):
    try:
        bounded_compositions(*a)
    except ValueError:
        return True
    return False

def dp_count(n, k, lo, hi):
    # sliding window over the sum, exact integers
    cur = [1] + [0] * n
    for _ in range(k):
        pre = [0]
        for v in cur:
            pre.append(pre[-1] + v)
        nxt = [0] * (n + 1)
        for s in range(n + 1):
            a, b = s - hi, s - lo
            if b < 0:
                continue
            nxt[s] = pre[b + 1] - pre[max(a, 0)]
        cur = nxt
    return cur[n]

def exact_ie(n, k, lo, hi):
    m = n - k * lo
    w = hi - lo + 1
    if m < 0:
        return 0
    tot = 0
    j = 0
    while j <= k and m - j * w >= 0:
        tot += (-1) ** j * comb(k, j) * comb(m - j * w + k - 1, k - 1)
        j += 1
    return tot

same((5, 2, 0, 5, 7), 6)
same((6, 3, 1, 3, 5), 2)
same((6, 3, 1, 3, 10**9 + 7), 7)
same((3, 1, 5, 6, 7), 0)
same((10**12, 3, 0, 10**12, 2), 1)
same((0, 1, 0, 0, 2), 1)
same((0, 3, 0, 0, 3), 1)
same((0, 5, 0, 7, 3), 1)
same((5, 1, 5, 9, 2), 1)
same((9, 1, 5, 9, 2), 1)
same((10, 1, 5, 9, 11), 0)
same((4, 1, 5, 9, 11), 0)
same((15, 3, 5, 5, 13), 1)
same((16, 3, 5, 5, 13), 0)
same((10, 4, 0, 10, 10**9 + 7), comb(13, 3) % (10**9 + 7))
same((10, 4, 0, 10**12, 13), comb(13, 3) % 13)
same((12, 4, 0, 3, 5), dp_count(12, 4, 0, 3) % 5)
same((2 * 10**14, 200, 10**12, 10**12, 7), 1)
same((2 * 10**14 + 1, 200, 10**12, 10**12, 7), 0)
same((2 * 10**14 - 1, 200, 0, 10**12, 998244353), exact_ie(2 * 10**14 - 1, 200, 0, 10**12) % 998244353)
for p in (2, 3, 5, 7, 13, 199, 211, 1009, 10**9 + 7):
    for args in [(10**15, 3, 0, 10**12, p), (10**12, 3, 0, 10**12, p), (123456789012, 5, 7, 10**12, p),
                 (10**14, 120, 10**11, 10**12, p), (10**15, 200, 0, 10**12, p), (777777777777777, 150, 10, 10**12, p)]:
        same(args, exact_ie(*args[:4]) % p)

# the symmetry n -> k*(lo+hi) - n
for p in (2, 11, 10**9 + 7):
    for k, lo, hi in [(7, 2, 9), (50, 10**5, 10**6), (200, 3, 10**12 // 7)]:
        n = k * lo + (k * (hi - lo)) // 3
        assert bounded_compositions(n, k, lo, hi, p) == bounded_compositions(k * (lo + hi) - n, k, lo, hi, p)

random.seed(4022)
PR = [2, 3, 5, 7, 11, 13, 97, 101, 997, 10007, 65537, 998244353, 10**9 + 7]
for _ in range(220):
    k = random.randint(1, 8)
    lo = random.randint(0, 5)
    hi = lo + random.randint(0, 12)
    n = random.randint(0, k * hi + 3)
    p = random.choice(PR)
    same((n, k, lo, hi, p), dp_count(n, k, lo, hi) % p)

for _ in range(40):
    k = random.randint(1, 200)
    lo = random.choice([0, random.randint(0, 10**12), random.randint(0, 50)])
    hi = lo + random.choice([0, 1, random.randint(0, 10**12 - lo), random.randint(0, 5000)])
    hi = min(hi, 10**12)
    n = random.randint(k * lo, k * hi)
    p = random.choice(PR)
    same((n, k, lo, hi, p), exact_ie(n, k, lo, hi) % p)

for bad in [(5, 0, 0, 5, 7), (5, 201, 0, 5, 7), (5, 2, -1, 5, 7), (5, 2, 3, 2, 7), (5, 2, 0, 10**12 + 1, 7), (-1, 2, 0, 5, 7),
            (10**15 + 1, 2, 0, 5, 7), (5, 2, 0, 5, 1), (5, 2, 0, 5, 0), (5, 2, 0, 5, 4), (5, 2, 0, 5, 9), (5, 2, 0, 5, 561),
            (5, 2, 0, 5, 10**9 + 9), (5, 2, 0, 5, 10**9 + 8), (5, 2, 0, 5, -7), (5, 2, 0, 5, 91), (5, 2, 0, 5, 10**9 + 7 + 2),
            (5.0, 2, 0, 5, 7), (5, 2.0, 0, 5, 7), (5, 2, 0.0, 5, 7), (5, 2, 0, 5.0, 7), (5, 2, 0, 5, 7.0), (True, 2, 0, 5, 7),
            (5, True, 0, 5, 7), (5, 2, False, 5, 7), (5, 2, 0, True, 7), ("5", 2, 0, 5, 7), (None, 2, 0, 5, 7), (5, 2, 0, 5, None),
            (5, 2, 0, 5, True), (5, 2, 0, 5, "7"), (5, 2, 0, 5, 1000000007 * 3), (5, 2, 0, 5, 25), (5, 2, 0, 5, 3 * 5)]:
    assert rej(*bad), bad
same((7, 2, 0, 5, 10**9 + 7), 0 + dp_count(7, 2, 0, 5))
same((0, 200, 0, 10**12, 10**9 + 7), 1)
''', r'''
from math import comb


def bounded_compositions(n, k, lo, hi, p):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not all(isint(v) for v in (n, k, lo, hi, p)):
        raise ValueError("type")
    if not (1 <= k <= 200 and 0 <= lo <= hi <= 10 ** 12 and 0 <= n <= 10 ** 15 and 2 <= p <= 10 ** 9 + 7):
        raise ValueError("range")
    d = 2
    while d * d <= p:
        if p % d == 0:
            raise ValueError("p is not prime")
        d += 1
    r = k - 1

    def binom(top):
        res = 1
        a, b = top, r
        while b:
            x, y = a % p, b % p
            if y > x:
                return 0
            res = res * (comb(x, y) % p) % p
            a //= p
            b //= p
        return res

    m = n - k * lo
    w = hi - lo + 1
    if m < 0:
        return 0
    total = 0
    for j in range(k + 1):
        t = m - j * w
        if t < 0:
            break
        term = comb(k, j) % p * binom(t + k - 1) % p
        total += -term if j & 1 else term
    return total % p
''')

task("v4_23_two_square_reps", r'''
Write `two_square_reps(n)` that returns a tuple (r, pairs) describing all ways to write n as a
sum of two squares of integers. `n` must be an int (bool is not an int) with 0 <= n <= 10**12,
otherwise raise ValueError.
- r is the number of ORDERED pairs (x, y) of integers of any sign with x*x + y*y == n. Order
  and signs count: for n = 25 the pairs are (+-5, 0), (0, +-5), (+-3, +-4), (+-4, +-3), so
  r == 12. For n = 0 the only pair is (0, 0), so r == 1. r is 0 when n is not a sum of two
  squares.
- pairs is the list of the distinct representations in canonical form (a, b) with
  a >= b >= 0 and a*a + b*b == n, sorted by a ascending (a differs between two distinct
  representations of the same n, so there are no ties). Each pair is a tuple of two ints.
  For n = 0 it is [(0, 0)]; for n not a sum of two squares it is [].
Examples: two_square_reps(25) == (12, [(4, 3), (5, 0)]); two_square_reps(2) == (4, [(1, 1)]);
two_square_reps(0) == (1, [(0, 0)]); two_square_reps(3) == (0, []);
two_square_reps(50) == (12, [(5, 5), (7, 1)]) since 50 = 25 + 25 = 49 + 1 (the pair (5, 5)
counts 4 ordered pairs, the pair (7, 1) counts 8); two_square_reps(65) == (16, [(7, 4), (8, 1)]).
n can be near 10**12 (a prime p = 1 mod 4 near 10**12, or a product of many small primes
that are 1 mod 4, which has hundreds of representations), so scanning a up to sqrt(n) is far
too slow for the large cases: first factor n (trial division up to 10**6 is enough), and
build the representations from the factorization. Return a tuple, not a list.
''', r'''
import random
from math import isqrt

def same(n, exp):
    got = two_square_reps(n)
    assert isinstance(got, tuple) and len(got) == 2 and got == exp, (n, got, exp)
    assert type(got[0]) is int and isinstance(got[1], list) and all(type(q) is tuple and len(q) == 2 for q in got[1]), (n, got)

def rej(a):
    try:
        two_square_reps(a)
    except ValueError:
        return True
    return False

def brute(n):
    s = isqrt(n)
    pairs = []
    r = 0
    for x in range(-s, s + 1):
        rem = n - x * x
        y = isqrt(rem)
        if y * y == rem:
            r += 1 if y == 0 else 2
    for b in range(0, s + 1):
        rem = n - b * b
        a = isqrt(rem)
        if a * a == rem and a >= b:
            pairs.append((a, b))
    pairs.sort()
    return (r, pairs)

def verify(n, fac):
    # n = prod fac[p]**e with the given primes; divisor-count formula r = 4 * (d1 - d3)
    divs = [1]
    for q, e in fac:
        divs = [d * q ** i for d in divs for i in range(e + 1)]
    assert len(divs) == len(set(divs))
    d1 = sum(1 for d in divs if d % 4 == 1)
    d3 = sum(1 for d in divs if d % 4 == 3)
    exp_r = 4 * (d1 - d3)
    r, pairs = two_square_reps(n)
    assert type(r) is int and r == exp_r, (n, r, exp_r)
    seen = 0
    last = -1
    for a, b in pairs:
        assert type(a) is int and type(b) is int and a >= b >= 0 and a * a + b * b == n, (n, a, b)
        assert a > last, (n, pairs)
        last = a
        seen += 1 if a == b == 0 else (4 if (b == 0 or a == b) else 8)
    assert seen == r, (n, seen, r)

for n, e in [(0, (1, [(0, 0)])), (1, (4, [(1, 0)])), (2, (4, [(1, 1)])), (3, (0, [])), (4, (4, [(2, 0)])), (5, (8, [(2, 1)])),
             (9, (4, [(3, 0)])), (21, (0, [])), (25, (12, [(4, 3), (5, 0)])), (45, (8, [(6, 3)])), (50, (12, [(5, 5), (7, 1)])),
             (65, (16, [(7, 4), (8, 1)])), (49, (4, [(7, 0)])), (6, (0, [])), (7, (0, [])), (8, (4, [(2, 2)])), (18, (4, [(3, 3)])),
             (325, (24, [(15, 10), (17, 6), (18, 1)])), (1105, (32, [(24, 23), (31, 12), (32, 9), (33, 4)])), (10, (8, [(3, 1)])), (13, (8, [(3, 2)]))]:
    same(n, e)

for n in range(0, 1500):
    same(n, brute(n))

random.seed(4023)
for _ in range(200):
    n = random.randint(1500, 10**6)
    same(n, brute(n))
for _ in range(60):
    n = random.randint(1, 10**6) * random.choice([1, 2, 4, 5, 13, 25, 65, 85])
    same(n, brute(n))

P1 = [5, 13, 17, 29, 37, 41, 53, 61, 73, 89, 97, 101, 109, 113, 137, 1009, 10009, 999953, 999961]
P3 = [3, 7, 11, 19, 23, 31, 43, 47, 999983]
for _ in range(120):
    fac = {}
    n = 1
    for q in random.sample(P1, random.randint(0, 6)) + random.sample(P3, random.randint(0, 2)) + [2]:
        e = random.choice([1, 1, 2, 3, 4])
        if q == 2:
            e = random.choice([0, 0, 1, 2, 5])
        if q in P3:
            e = random.choice([2, 2, 4, 1])
        if n * q ** e <= 10**12 and e > 0:
            n *= q ** e
            fac[q] = e
    if n > 1:
        verify(n, sorted(fac.items()))

for n, fac in [(10**12, [(2, 12), (5, 12)]), (999999999989, [(999999999989, 1)]), (999983 ** 2, [(999983, 2)]),
               (999953 * 999961, [(999953, 1), (999961, 1)]), (5 * 13 * 17 * 29 * 37 * 41 * 53 * 61, [(5, 1), (13, 1), (17, 1), (29, 1), (37, 1), (41, 1), (53, 1), (61, 1)]),
               (5 ** 16, [(5, 16)]), (2 * 5 ** 2 * 13 ** 2 * 17 * 29 * 37 * 41 * 53, [(2, 1), (5, 2), (13, 2), (17, 1), (29, 1), (37, 1), (41, 1), (53, 1)]),
               (999999999961, [(999999999961, 1)]), (999999999959, [(999999999959, 1)]), (9 * 49 * 999983, [(3, 2), (7, 2), (999983, 1)]),
               (13 ** 8 * 5 ** 3, [(13, 8), (5, 3)]), (2 ** 39, [(2, 39)]), (3 ** 22 * 5, [(3, 22), (5, 1)])]:
    verify(n, fac)
same(3 * 999983, (0, []))
same(999983 ** 2, (4, [(999983, 0)]))
same(2 ** 39, (4, [(2 ** 19, 2 ** 19)]))

for bad in (-1, -10**12, 10**12 + 1, 10**13, 1.0, 4.0, "4", None, True, False, [4], (4,), 2.5):
    assert rej(bad), bad
''', r'''
from math import isqrt


def two_square_reps(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 10 ** 12:
        raise ValueError("n")
    if n == 0:
        return (1, [(0, 0)])
    fac = {}
    m = n
    p = 2
    while p * p <= m:
        while m % p == 0:
            fac[p] = fac.get(p, 0) + 1
            m //= p
        p += 1 if p == 2 else 2
    if m > 1:
        fac[m] = fac.get(m, 0) + 1

    def gmul(u, v):
        return (u[0] * v[0] - u[1] * v[1], u[0] * v[1] + u[1] * v[0])

    cur = [(1, 0)]
    count = 4
    for p, e in sorted(fac.items()):
        if p == 2:
            z = (1, 0)
            for _ in range(e):
                z = gmul(z, (1, 1))
            cur = [gmul(c, z) for c in cur]
        elif p % 4 == 3:
            if e % 2:
                return (0, [])
            f = p ** (e // 2)
            cur = [(c[0] * f, c[1] * f) for c in cur]
        else:
            count *= e + 1
            c = 2
            while pow(c, (p - 1) // 2, p) != p - 1:
                c += 1
            t = pow(c, (p - 1) // 4, p)
            a, b = p, t
            while b * b > p:
                a, b = b, a % b
            pi, pb = (b, isqrt(p - b * b)), (b, -isqrt(p - b * b))
            ws = []
            for j in range(e + 1):
                w = (1, 0)
                for _ in range(j):
                    w = gmul(w, pi)
                for _ in range(e - j):
                    w = gmul(w, pb)
                ws.append(w)
            cur = [gmul(c, w) for c in cur for w in ws]
    pairs = set()
    for x, y in cur:
        a, b = abs(x), abs(y)
        pairs.add((max(a, b), min(a, b)))
    return (count, sorted(pairs))
''')

task("v4_24_fib_edges", r'''
Write `fib_edges(n, k)` that describes the decimal expansion of the Fibonacci number F(n)
(F(0) = 0, F(1) = 1, F(2) = 1, F(3) = 2, ...) without ever building it. `n` and `k` must be ints
(bool is not an int) with 0 <= n <= 10**18 and 1 <= k <= 18, otherwise raise ValueError.
It returns a tuple (d, lead, trail):
- d is the number of decimal digits of F(n) as an int (F(0) = 0 has 1 digit).
- lead is a str with the first min(k, d) digits of F(n).
- trail is a str with the last min(k, d) digits of F(n). If d >= k these are exactly k
  characters and keep their leading zeros, i.e. F(n) mod 10**k padded with zeros on the left
  to width k (F(75) = 2111485077978050, so the last 3 digits are '050'). If d < k, trail is
  the whole number as a str, and lead is the same str.
Because n goes up to 10**18, F(n) has about 2 * 10**17 digits, far beyond any big integer.
d and the leading digits come from n * log10(phi) - log10(sqrt(5)) where phi = (1 + sqrt(5)) / 2
(the term psi**n with psi = (1 - sqrt(5)) / 2 is far below any digit that matters once n is
more than a few thousand, but for small n the number must be exact), computed with enough
significant digits that no digit of the first k (k <= 18) is wrong; lead is the leading digits
truncated, never rounded. The trailing digits come from arithmetic modulo 10**k.
Every returned lead and trail is a str, d is an int.
Examples: fib_edges(0, 1) == (1, '0', '0'); fib_edges(10, 3) == (2, '55', '55') (F(10) = 55,
two digits only); fib_edges(15, 2) == (3, '61', '10') (F(15) = 610); fib_edges(15, 1) ==
(3, '6', '0'); fib_edges(100, 5) == (21, '35422', '15075') (F(100) = 354224848179261915075).
''', r'''
import random
import decimal

def same(n, k, exp):
    got = fib_edges(n, k)
    assert isinstance(got, tuple) and got == exp, (n, k, got, exp)
    assert type(got[0]) is int and type(got[1]) is str and type(got[2]) is str, got

def rej(*a):
    try:
        fib_edges(*a)
    except ValueError:
        return True
    return False

FS = []
a, b = 0, 1
for _ in range(6200):
    FS.append(str(a))
    a, b = b, a + b

def exact(n, k):
    s = FS[n]
    return (len(s), s[:k], s[-k:])

def mmul(A, B, md):
    return [[(A[0][0] * B[0][0] + A[0][1] * B[1][0]) % md, (A[0][0] * B[0][1] + A[0][1] * B[1][1]) % md],
            [(A[1][0] * B[0][0] + A[1][1] * B[1][0]) % md, (A[1][0] * B[0][1] + A[1][1] * B[1][1]) % md]]

def trail_oracle(n, k):
    md = 10 ** k
    R = [[1, 0], [0, 1]]
    M = [[1, 1], [1, 0]]
    e = n
    while e:
        if e & 1:
            R = mmul(R, M, md)
        M = mmul(M, M, md)
        e >>= 1
    return str(R[0][1] % md).zfill(k)

def scaled(n, k):
    # fast doubling on mantissas with a shared decimal exponent: F(m) ~ a*10**E, F(m+1) ~ b*10**E
    a, b, E = 0, 1, 0
    for bit in bin(n)[2:]:
        c = a * (2 * b - a)
        d = a * a + b * b
        E *= 2
        a, b = (d, c + d) if bit == "1" else (c, d)
        L = len(str(max(a, b)))
        if L > 100:
            sh = L - 100
            a //= 10 ** sh
            b //= 10 ** sh
            E += sh
    s = str(a)
    return (len(s) + E, s[:k])

def big_check(n, k):
    d, lead, trail = fib_edges(n, k)
    d2, lead2 = scaled(n, k)
    assert type(d) is int and d == d2 and lead == lead2, (n, k, (d, lead), (d2, lead2))
    assert trail == trail_oracle(n, k), (n, k, trail)
    assert len(lead) == k and len(trail) == k

same(0, 1, (1, "0", "0"))
same(0, 18, (1, "0", "0"))
same(1, 5, (1, "1", "1"))
same(2, 3, (1, "1", "1"))
same(10, 3, (2, "55", "55"))
same(15, 2, (3, "61", "10"))
same(15, 1, (3, "6", "0"))
same(20, 5, (4, "6765", "6765"))
same(20, 4, (4, "6765", "6765"))
same(20, 3, (4, "676", "765"))
same(75, 3, (16, "211", "050"))
same(75, 16, (16, "2111485077978050", "2111485077978050"))
same(75, 18, (16, "2111485077978050", "2111485077978050"))
same(100, 5, (21, "35422", "15075"))
same(100, 18, (21, "354224848179261915", "224848179261915075"))
for n in (3000, 3001, 2999, 2998, 3002, 4096, 6000, 6199):
    for k in (1, 2, 9, 17, 18):
        same(n, k, exact(n, k))
for n in range(0, 140):
    for k in (1, 3, 18):
        same(n, k, exact(n, k))

random.seed(4024)
for _ in range(220):
    n = random.choice([random.randint(0, 6199), random.randint(2500, 3500), random.randint(0, 400)])
    k = random.randint(1, 18)
    same(n, k, exact(n, k))
for _ in range(60):
    n = random.choice([random.randint(3000, 10**5), random.randint(10**5, 10**9), random.randint(10**9, 10**18), int(10 ** random.uniform(3.5, 18))])
    n = min(n, 10**18)
    k = random.choice([random.randint(1, 18), 18, 1, 9])
    big_check(n, k)
for n in (10**18, 10**18 - 1, 10**17, 10**9, 3003, 2 * 10**15 + 7, 12345678901234567):
    for k in (1, 7, 18):
        big_check(n, k)
# the longer lead extends the shorter one, trails likewise
for n in (10**18, 10**18 - 7, 5 * 10**12 + 1):
    d18, l18, t18 = fib_edges(n, 18)
    for k in (1, 5, 12):
        d, l, t = fib_edges(n, k)
        assert d == d18 and l18.startswith(l) and t18.endswith(t), (n, k)

for bad in [(-1, 3), (10**18 + 1, 3), (5, 0), (5, 19), (5, -1), (5.0, 3), (5, 3.0), ("5", 3), (5, "3"), (None, 3), (5, None),
            (True, 3), (5, True), (False, 3), (10**20, 5), (5, 10**9), (-10**18, 5)]:
    assert rej(*bad), bad
''', r'''
from decimal import Decimal, localcontext


def fib_edges(n, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not isint(k) or not 0 <= n <= 10 ** 18 or not 1 <= k <= 18:
        raise ValueError("range")
    if n <= 3000:
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        s = str(a)
        return (len(s), s[:k], s[-k:])
    md = 10 ** k
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * ((2 * b - a) % md) % md
        d = (a * a + b * b) % md
        a, b = (d, (c + d) % md) if bit == "1" else (c, d)
    trail = str(a).zfill(k)
    with localcontext() as ctx:
        ctx.prec = 120
        root5 = Decimal(5).sqrt()
        phi = (1 + root5) / 2
        x = n * phi.log10() - root5.log10()
        ip = int(x)
        frac = x - ip
        lead = str(int(Decimal(10) ** (frac + k - 1)))
    return (ip + 1, lead, trail)
''')

task("v4_25_capped_part_count", r'''
Write `capped_part_count(n, parts, m)` that counts, modulo m, the ways to write n as a sum of
parts of given sizes where each size may be used a limited number of times. `parts` is a
list or tuple of 1 to 6 pairs (size, cap); a pair may be a list or a tuple. size is an int
with 1 <= size <= 12 and all sizes are distinct. cap is None (this size can be used any
number of times) or an int with 0 <= cap <= 9 (it can be used at most cap times; cap 0 means
the size cannot be used at all, it is still a valid pair and its size still has to be
distinct from the others). A way is a tuple of counts (c1, ..., cr), one per pair, with
0 <= ci <= cap_i (no upper bound if cap_i is None) and c1*size1 + ... + cr*sizer == n. The
order of the parts inside a sum does not matter (it is the counts that are counted).
n is an int with 0 <= n <= 10**18, m is an int with 1 <= m <= 10**18. bool is not an int, and
a None cap is the only non-int cap. Anything that breaks these rules (wrong type or range,
parts not a list or tuple, empty or longer than 6, a pair that is not a 2-sequence, a repeated
size) is a ValueError. The result is an int in range(m); for m == 1 it is always 0.
The exact count is far too large to compute for large n directly and enumerating partitions
or filling a table of size n is impossible when n reaches 10**18. For n = 0 the answer is 1
(the empty sum), also when m > 1 and every cap is 0. If every cap is finite, the count is 0
as soon as n exceeds sum(size * cap).
Examples: capped_part_count(6, [(1, None), (2, None), (3, None)], 100) == 7;
capped_part_count(10, [(1, None), (5, 1)], 1000) == 2 (ten 1s, or one 5 and five 1s);
capped_part_count(10**18, [(1, None), (2, None)], 10**9 + 7) == 500000029 (the exact count is
10**18 // 2 + 1); capped_part_count(7, [(7, 0)], 5) == 0;
capped_part_count(34, [(2, 3), (7, 4)], 10) == 1 (6 + 28).
''', r'''
import random
from fractions import Fraction
from math import gcd

def same(args, exp):
    got = capped_part_count(*args)
    assert type(got) is int and got == exp, (args, got, exp)

def rej(*a):
    try:
        capped_part_count(*a)
    except ValueError:
        return True
    return False

def dp(n, items):
    f = [1] + [0] * n
    for s, c in items:
        g = [0] * (n + 1)
        for t in range(n + 1):
            v = f[t]
            if v:
                j = 0
                while t + j * s <= n and (c is None or j <= c):
                    g[t + j * s] += v
                    j += 1
        f = g
    return f[n]

def big(n, items):
    # exact value for huge n: quasi-polynomial interpolation in n over its residue class
    unl = [s for s, c in items if c is None]
    D = sum(s * c for s, c in items if c is not None)
    if not unl:
        return 0 if n > D else dp(n, items)
    L = 1
    for s in unl:
        L = L * s // gcd(L, s)
    u = len(unl)
    n0 = D + ((n - D) % L)
    ys = [dp(n0 + t * L, items) for t in range(u)]
    x = Fraction(n - n0, L)
    tot = Fraction(0)
    for i in range(u):
        term = Fraction(ys[i])
        for j in range(u):
            if j != i:
                term *= (x - j) / (i - j)
        tot += term
    assert tot.denominator == 1
    return int(tot)

U = None
same((6, [(1, U), (2, U), (3, U)], 100), 7)
same((10, [(1, U), (5, 1)], 1000), 2)
same((10**18, [(1, U), (2, U)], 10**9 + 7), 500000029)
same((7, [(7, 0)], 5), 0)
same((34, [(2, 3), (7, 4)], 10), 1)
same((33, [(2, 3), (7, 4)], 10), 0)
same((35, [(2, 3), (7, 4)], 10**18), 0)
same((10**18, [(2, 3), (7, 4)], 10**18), 0)
same((0, [(7, 0)], 5), 1)
same((0, [(7, 0), (3, 0)], 1), 0)
same((0, [(5, U)], 2), 1)
same((1, [(5, 0)], 7), 0)
same((1, [(5, 0), (4, 0), (3, 0)], 7), 0)
same((10**18 + 0, [(5, U)], 10**18), 1 if 10**18 % 5 == 0 else 0)
same((10**18 - 1, [(5, U)], 10**18), 0)
same((10**18, [(1, U), (2, U), (3, U)], 10**18), (((10**18 + 3) ** 2 + 6) // 12) % 10**18)
same((10**18, [(1, U), (2, U), (3, U)], 10**9 + 7), 250000227)
same((10**18, [(1, U), (2, U)], 1), 0)
same((10**18, [(3, 2), (5, U)], 1000), sum(1 for a in range(3) if 10**18 - 3 * a >= 0 and (10**18 - 3 * a) % 5 == 0) % 1000)
same((10**18 - 1, ((4, U), (6, U)), 1000), 0)
same((10**18, ((4, U), [6, U]), 1000), big(10**18, [(4, U), (6, U)]) % 1000)
same((100, [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3)], 10**9), dp(100, [(1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3)]) % 10**9)
same((12, ((12, 1), (1, U)), 10**18), 2)
same((11, [[12, 1], [1, U]], 10**18), 1)

random.seed(4025)
MS = [1, 2, 3, 7, 10, 1000, 10**9 + 7, 998244353, 10**18, 10**18 - 1, 999999999999999989]
for _ in range(120):
    r = random.randint(1, 6)
    sizes = random.sample(range(1, 13), r)
    items = [(s, random.choice([None, None, 0, 1, 2, 5, 9])) for s in sizes]
    parts = [tuple(q) if random.random() < 0.5 else list(q) for q in items]
    n = random.choice([random.randint(0, 40), random.randint(0, 250)])
    m = random.choice(MS)
    same((n, parts, m), dp(n, items) % m)

for _ in range(8):
    r = random.randint(2, 6)
    sizes = random.sample(range(1, 13), r)
    items = [(s, random.choice([None, 3, 7, 9])) for s in sizes]
    n = random.randint(300, 1500)
    m = random.choice(MS)
    same((n, items, m), dp(n, items) % m)

SM = [1, 2, 3, 4, 5, 6, 10, 12]
for _ in range(14):
    u = random.randint(1, 4)
    unl = random.sample(SM, u)
    rest = [s for s in range(1, 13) if s not in unl]
    cp = random.sample(rest, random.randint(0, min(3, 6 - u)))
    items = [(s, None) for s in unl] + [(s, random.choice([0, 1, 2, 4])) for s in cp]
    random.shuffle(items)
    n = random.choice([random.randint(10**6, 10**18), 10**18, random.randint(10**12, 10**15)])
    m = random.choice(MS)
    same((n, items, m), big(n, items) % m)

for bad in [(-1, [(1, None)], 5), (10**18 + 1, [(1, None)], 5), (5, [(1, None)], 0), (5, [(1, None)], -3), (5, [(1, None)], 10**18 + 1),
            (5, [], 5), (5, [(1, None)] * 2, 5), (5, [(s, None) for s in range(1, 8)], 5), (5, [(0, None)], 5), (5, [(13, None)], 5),
            (5, [(1, -1)], 5), (5, [(1, 10)], 5), (5, [(1, 1.0)], 5), (5, [(1, True)], 5), (5, [(True, None)], 5), (5, [(1.0, None)], 5),
            (5, [(1, None, 3)], 5), (5, [(1,)], 5), (5, [1], 5), (5, "ab", 5), (5, None, 5), (5, {(1, None)}, 5), (5, [(1, None), (2, 1), (1, 3)], 5),
            (5.0, [(1, None)], 5), (True, [(1, None)], 5), (5, [(1, None)], 5.0), (5, [(1, None)], True), ("5", [(1, None)], 5), (5, [(1, None)], None),
            (5, [(2, 0), (2, None)], 5), (None, [(1, None)], 5), (5, 7, 5), (5, [("1", None)], 5), (5, [(1, "2")], 5)]:
    assert rej(*bad), bad
same((5, ((1, None),), 7), 1)
same((9, [(3, None)], 4), 1)
same((10, [(3, None)], 4), 0)
''', r'''
def capped_part_count(n, parts, m):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not isint(m) or not 0 <= n <= 10 ** 18 or not 1 <= m <= 10 ** 18:
        raise ValueError("n or m")
    if not isinstance(parts, (list, tuple)) or not 1 <= len(parts) <= 6:
        raise ValueError("parts")
    seen = set()
    items = []
    for it in parts:
        if not isinstance(it, (list, tuple)) or len(it) != 2:
            raise ValueError("pair")
        s, c = it
        if not isint(s) or not 1 <= s <= 12 or s in seen:
            raise ValueError("size")
        if c is not None and (not isint(c) or not 0 <= c <= 9):
            raise ValueError("cap")
        seen.add(s)
        items.append((s, c))

    def times_one_minus(poly, e):
        res = poly + [0] * e
        for i, v in enumerate(poly):
            res[i + e] -= v
        return res

    num = [1]
    den = [1]
    for s, c in items:
        if c == 0:
            continue
        den = times_one_minus(den, s)
        if c is not None:
            num = times_one_minus(num, s * (c + 1))
    num = [v % m for v in num]
    den = [v % m for v in den]

    def mul(a, b, par):
        top = len(a) + len(b) - 2 - par
        out = [0] * (top // 2 + 1 if top >= 0 else 0)
        for i, x in enumerate(a):
            if x:
                for j, y in enumerate(b):
                    if (i + j) % 2 == par:
                        out[(i + j) // 2] += x * y
        return [v % m for v in out]

    while n:
        neg = [(-v if i & 1 else v) % m for i, v in enumerate(den)]
        num = mul(num, neg, n & 1)
        den = mul(den, neg, 0)
        n >>= 1
    return (num[0] if num else 0) % m
''')


task("v4_26_rect_union", r'''
Write `union_stats(rects)` that returns a tuple (area, perimeter, components) of three ints for
a set of axis-aligned rectangles.
`rects` is a list or tuple of 0..100 rectangles. Each rectangle is a list or tuple of four ints
(x1, y1, x2, y2) (bool is not an int), every |value| <= 10**9, with x1 <= x2 and y1 <= y2.
Anything else is a ValueError, and this is checked for every rectangle before any rectangle is
ignored. Rectangles are closed regions.
A rectangle with x1 == x2 or y1 == y2 has no area: it is ignored completely. It adds nothing
to the union and it connects nothing. Let U be the union of the remaining rectangles.
area: the area of U (overlaps are counted once).
perimeter: the total length of the boundary of U. A piece of boundary is a segment with U on
exactly one side of it, so the boundaries of holes count, and an edge shared by two
rectangles that lie on opposite sides of it contributes nothing. Rectangles that merely touch
at a corner point contribute their own sides.
components: two (non-ignored) rectangles are linked when their intersection is non-empty and
is not a single point, that is, they overlap or share a boundary segment of positive length.
components is the number of groups of rectangles under the transitive closure of "linked". A
rectangle touching another only at one corner point is not linked to it. Identical rectangles
are linked. With no non-ignored rectangle the result is (0, 0, 0).
Coordinates are huge, so do not iterate over unit cells; compress the coordinates or sweep.
Example: [(0, 0, 2, 2), (2, 0, 4, 2), (5, 5, 6, 6), (6, 6, 7, 7)] gives (10, 20, 3): the first
two form a 4 x 2 block (area 8, perimeter 12), the two unit squares touch only at (6, 6)
(area 2, perimeter 8, two components).
''', r'''
import random

def eq(r, exp):
    got = union_stats(r)
    assert isinstance(got, tuple) and got == exp and all(type(x) is int for x in got), (r, got, exp)

def bad(r):
    try:
        union_stats(r)
    except ValueError:
        return True
    return False

eq([], (0, 0, 0))
eq([(0, 0, 2, 2), (2, 0, 4, 2), (5, 5, 6, 6), (6, 6, 7, 7)], (10, 20, 3))
eq([(0, 0, 1, 1)], (1, 4, 1))
eq([[0, 0, 1, 1], [0, 0, 1, 1]], (1, 4, 1))
eq(((0, 0, 3, 3), (1, 1, 2, 2)), (9, 12, 1))
eq([(0, 0, 3, 1), (0, 2, 3, 3), (0, 1, 1, 2), (2, 1, 3, 2)], (8, 16, 1))
eq([(0, 0, 1, 1), (1, 1, 2, 2)], (2, 8, 2))
eq([(0, 0, 1, 1), (1, 1, 2, 2), (1, 0, 2, 1)], (3, 8, 1))
eq([(0, 0, 2, 2), (2, 1, 4, 3)], (8, 14, 1))
# zero-area rectangles are ignored, even when they bridge two others
eq([(0, 0, 1, 1), (1, 0, 1, 1), (2, 0, 3, 1)], (2, 8, 2))
eq([(0, 0, 1, 1), (0, 5, 9, 5), (3, 3, 3, 3)], (1, 4, 1))
eq([(0, 0, 0, 0)], (0, 0, 0))
eq([(0, 0, 5, 0), (2, 2, 2, 7)], (0, 0, 0))
# an L shape and a T shape
eq([(0, 0, 4, 1), (0, 1, 1, 4)], (7, 16, 1))
eq([(0, 0, 3, 1), (1, 1, 2, 3)], (5, 12, 1))
# huge coordinates
B = 10 ** 9
eq([(-B, -B, B, B)], (4 * B * B, 8 * B, 1))
eq([(-B, -B, 0, 0), (0, 0, B, B)], (2 * B * B, 8 * B, 2))
eq([(-B, -B, 0, B), (0, -B, B, B), (-B, -B, B, -B + 1)], (4 * B * B, 8 * B, 1))
K = 10 ** 7
eq([(i * K, i * K, (i + 1) * K, (i + 1) * K) for i in range(100)], (100 * K * K, 400 * K, 100))
eq([(i * K, 0, (i + 1) * K, K) for i in range(100)], (100 * K * K, 202 * K, 1))
eq([(i * K, 0, (i + 1) * K, K) for i in range(99, -1, -1)], (100 * K * K, 202 * K, 1))
# errors
for r in [None, 5, "abc", {(0, 0, 1, 1)}, [(0, 0, 1)], [(0, 0, 1, 1, 1)], [(0, 0, 1, 1), None], [(1, 0, 0, 1)], [(0, 1, 1, 0)], [(0, 0, 1.0, 1)],
          [(0, 0, True, 1)], [(0, 0, 1, "1")], [(0, 0, B + 1, 1)], [(-B - 1, 0, 1, 1)], [(0, 0, 1, 1)] * 101, [(0, 0, 1, 1), (3, 3, 2, 3)],
          [(0, 0, 1, 1), 7], [(0, 0, 1, 1), [0, 0, 1, None]], [(5, 5, 5, 4)], [(0, 0, 1, 1), (0, 0, 1, 1.5)], [((0, 0), (1, 1))], [(False, 0, 1, 1)]]:
    assert bad(r), r
eq([(0, 0, 1, 1)] * 100, (1, 4, 1))

# oracle: unit cells, 4-connectivity
def oracle(rects):
    cells = set()
    for x1, y1, x2, y2 in rects:
        if x1 == x2 or y1 == y2:
            continue
        for x in range(x1, x2):
            for y in range(y1, y2):
                cells.add((x, y))
    h = v = 0
    for x, y in cells:
        if (x, y + 1) not in cells:
            h += 1
        if (x, y - 1) not in cells:
            h += 1
        if (x + 1, y) not in cells:
            v += 1
        if (x - 1, y) not in cells:
            v += 1
    seen = set()
    comps = 0
    for c in cells:
        if c in seen:
            continue
        comps += 1
        seen.add(c)
        st = [c]
        while st:
            x, y = st.pop()
            for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    st.append(nb)
    return len(cells), h, v, comps

random.seed(4026)
R = 5

def rr():
    x1 = random.randint(-R, R)
    y1 = random.randint(-R, R)
    w = random.choice([0, 1, 1, 2, 2, 3, 4])
    h = random.choice([0, 1, 1, 2, 2, 3, 4])
    if random.random() < 0.1:
        w = 0
    return (x1, y1, min(R + 3, x1 + w), min(R + 3, y1 + h))

for it in range(250):
    n = random.choice([0, 1, 2, 3, 4, 5, 6, 8, 10, 14])
    rs = [rr() for _ in range(n)]
    if random.random() < 0.3 and rs:
        # share corners and edges on purpose
        x1, y1, x2, y2 = rs[0]
        rs.append((x2, y2, x2 + random.randint(0, 2), y2 + random.randint(0, 2)))
        rs.append((x2, y1, x2 + random.randint(0, 2), y2))
    if random.random() < 0.3:
        rs = [list(r) for r in rs]
    a, h, v, c = oracle(rs)
    eq(rs, (a, h + v, c))
    kx, ky = random.choice([(1, 1), (3, 1), (10 ** 8, 7), (7, 10 ** 8), (10 ** 8, 10 ** 8)])
    ox = random.choice([0, -5 * 10 ** 7, 3]) if kx > 1000 else 0
    big = [(x1 * kx + ox, y1 * ky, x2 * kx + ox, y2 * ky) for x1, y1, x2, y2 in rs]
    if all(abs(t) <= B for r in big for t in r):
        eq(big, (a * kx * ky, h * kx + v * ky, c))
# larger random case: 100 rectangles on a 40 x 40 lattice, scaled
rs = []
for _ in range(100):
    x1 = random.randint(-20, 20)
    y1 = random.randint(-20, 20)
    rs.append((x1, y1, x1 + random.randint(0, 6), y1 + random.randint(0, 6)))
a, h, v, c = oracle(rs)
eq(rs, (a, h + v, c))
eq([(x1 * K, y1 * K, x2 * K, y2 * K) for x1, y1, x2, y2 in rs], (a * K * K, (h + v) * K, c))
''', r'''
def union_stats(rects):
    def ok(v):
        return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= 10 ** 9
    if not isinstance(rects, (list, tuple)) or len(rects) > 100:
        raise ValueError("rects")
    rs = []
    for r in rects:
        if not isinstance(r, (list, tuple)) or len(r) != 4 or not all(ok(v) for v in r):
            raise ValueError("rect")
        x1, y1, x2, y2 = r
        if x1 > x2 or y1 > y2:
            raise ValueError("order")
        if x1 < x2 and y1 < y2:
            rs.append((x1, y1, x2, y2))
    m = len(rs)
    if m == 0:
        return (0, 0, 0)
    xs = sorted({v for r in rs for v in (r[0], r[2])})
    ys = sorted({v for r in rs for v in (r[1], r[3])})
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: i for i, v in enumerate(ys)}
    W, H = len(xs) - 1, len(ys) - 1
    cnt = [[0] * (H + 1) for _ in range(W + 1)]
    for x1, y1, x2, y2 in rs:
        a, b, c, d = xi[x1], yi[y1], xi[x2], yi[y2]
        cnt[a][b] += 1
        cnt[c][b] -= 1
        cnt[a][d] -= 1
        cnt[c][d] += 1
    for i in range(W + 1):
        for j in range(H + 1):
            if i:
                cnt[i][j] += cnt[i - 1][j]
            if j:
                cnt[i][j] += cnt[i][j - 1]
            if i and j:
                cnt[i][j] -= cnt[i - 1][j - 1]
    area = per = 0
    for i in range(W):
        row = cnt[i]
        dx = xs[i + 1] - xs[i]
        for j in range(H):
            if row[j] <= 0:
                continue
            dy = ys[j + 1] - ys[j]
            area += dx * dy
            if i == 0 or cnt[i - 1][j] <= 0:
                per += dy
            if i == W - 1 or cnt[i + 1][j] <= 0:
                per += dy
            if j == 0 or row[j - 1] <= 0:
                per += dx
            if j == H - 1 or row[j + 1] <= 0:
                per += dx
    parent = list(range(m))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(m):
        a = rs[i]
        for j in range(i + 1, m):
            b = rs[j]
            lx, hx = max(a[0], b[0]), min(a[2], b[2])
            ly, hy = max(a[1], b[1]), min(a[3], b[3])
            if lx <= hx and ly <= hy and (lx < hx or ly < hy):
                parent[find(i)] = find(j)
    return (area, per, len({find(i) for i in range(m)}))
''')


task("v4_27_mst_census", r'''
Write `mst_census(n, edges)` for a weighted undirected multigraph. It returns a tuple
(weight, count, chosen).
`n` is an int (bool is not an int) with 1 <= n <= 60; the nodes are 0..n-1. `edges` is a list
or tuple of 0..600 edges, each a list or tuple of three ints (u, v, w) (bool is not an int)
with 0 <= u, v < n and |w| <= 10**9. Anything else is a ValueError. Parallel edges and
self-loops (u == v) are allowed. An edge is identified by its position in `edges`, counted from
0, so two parallel edges are two different edges even when their weights are equal. If the graph
is not connected (checked after the validation above) it is a ValueError.
weight: the total weight of a minimum spanning tree.
count: the exact number of different minimum spanning trees, where a tree is a set of n - 1
edge positions. A self-loop is never in a spanning tree. The count can be astronomically large
(use exact integers; do not take it modulo anything).
chosen: the tuple of the n - 1 edge positions of one particular minimum spanning tree, in
ascending order: among all minimum spanning trees, the one whose ascending position list is
lexicographically smallest (compare the lists element by element, first difference decides).
Only edge positions matter for this choice, not node numbers.
For n == 1 the result is (0, 1, ()), whatever the (self-loop) edges are.
Example 1: n = 3, edges [(0, 1, 1), (1, 2, 1), (0, 2, 1)] gives (2, 3, (0, 1)).
Example 2: n = 4, edges [(0, 1, 5), (0, 1, 5), (1, 2, 2), (2, 3, 2), (1, 3, 2)] gives
(9, 6, (0, 2, 3)): one of the two parallel 0-1 edges (2 ways) times one of the 3 spanning
trees of the triangle 1-2-3 (3 ways).
Example 3: n = 3, edges [(0, 1, 3), (0, 2, 1), (1, 2, 1), (0, 1, 1)] gives (2, 3, (1, 2)),
because weight 3 is too heavy to be used.
''', r'''
import random
from itertools import combinations
from math import comb

def bad(n, e):
    try:
        mst_census(n, e)
    except ValueError:
        return True
    return False

def eq(n, e, exp):
    got = mst_census(n, e)
    assert isinstance(got, tuple) and len(got) == 3 and got == exp, (n, e, got, exp)
    assert type(got[0]) is int and type(got[1]) is int and isinstance(got[2], tuple) and all(type(i) is int for i in got[2])

eq(3, [(0, 1, 1), (1, 2, 1), (0, 2, 1)], (2, 3, (0, 1)))
eq(4, [(0, 1, 5), (0, 1, 5), (1, 2, 2), (2, 3, 2), (1, 3, 2)], (9, 6, (0, 2, 3)))
eq(3, [(0, 1, 3), (0, 2, 1), (1, 2, 1), (0, 1, 1)], (2, 3, (1, 2)))
eq(1, [], (0, 1, ()))
eq(1, [(0, 0, 5), (0, 0, -7)], (0, 1, ()))
eq(2, [(0, 1, 4)], (4, 1, (0,)))
eq(2, [(0, 0, -9), (1, 1, 2), (1, 0, 4), [0, 1, 4]], (4, 2, (2,)))
eq(2, [(1, 0, -3), (0, 1, -3), (0, 1, 3)], (-3, 2, (0,)))
# lexicographic choice by positions
eq(3, [(0, 1, 1), (1, 2, 7), (0, 2, 7), (1, 2, 1)], (2, 1, (0, 3)))
eq(3, [(1, 2, 2), (0, 1, 1), (0, 2, 1), (0, 1, 1)], (2, 2, (1, 2)))
# path, weights mixed with negatives
eq(4, [(0, 1, -1), (1, 2, -1), (2, 3, -1), (0, 3, 0), (0, 2, 5)], (-3, 1, (0, 1, 2)))
# complete graph, equal weights: n ** (n - 2) trees, the star at node 0 is the first one
for k in (2, 3, 5, 12, 30):
    E = [(i, j, 7) for i in range(k) for j in range(i + 1, k)]
    eq(k, E, (7 * (k - 1), k ** (k - 2), tuple(range(k - 1))))
# complete bipartite, equal weights: a**(b-1) * b**(a-1)
for a, b in ((2, 3), (4, 4), (5, 9)):
    E = [(i, a + j, -2) for i in range(a) for j in range(b)]
    eq(a + b, E, (-2 * (a + b - 1), a ** (b - 1) * b ** (a - 1), tuple(range(b)) + tuple(j * b for j in range(1, a))))
# cycle of 40 with equal weights: 40 trees; one heavy edge forces count 1
C = [(i, (i + 1) % 40, 3) for i in range(40)]
eq(40, C, (117, 40, tuple(range(39))))
C[5] = (5, 6, 4)
eq(40, C, (117, 1, tuple(range(5)) + tuple(range(6, 40))))
C[5] = (5, 6, 2)
eq(40, C, (116, 39, tuple(range(39))))
# every tree edge doubled: 2 ** (n - 1) trees, the first copies win
E = []
for i in range(1, 41):
    E += [(i - 1, i, 1), (i - 1, i, 1)]
eq(41, E, (40, 2 ** 40, tuple(range(0, 80, 2))))
# two triangles joined by one bridge, a square with a diagonal of the same weight
eq(6, [(0, 1, 1), (1, 2, 1), (0, 2, 1), (3, 4, 1), (4, 5, 1), (3, 5, 1), (2, 3, 9)], (13, 9, (0, 1, 3, 4, 6)))
eq(4, [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 0, 1), (0, 2, 1)], (3, 8, (0, 1, 2)))
# a large weight class built from several lighter components
E = [(i, i + 1, 1) for i in range(0, 20, 2)]
E += [(i, j, 2) for i in range(0, 20, 2) for j in range(1, 20, 2) if abs(i - j) > 1]
w, cn, ch = mst_census(20, E)
assert w == 10 + 2 * 9 and ch[:10] == tuple(range(10)) and len(ch) == 19 and isinstance(cn, int)
# disconnected and invalid
assert bad(2, []) and bad(3, [(0, 1, 1)]) and bad(4, [(0, 1, 1), (2, 3, 1)]) and bad(2, [(0, 0, 1), (1, 1, 1)])
assert bad(60, [(i, i + 1, 1) for i in range(58)])
for n, e in [(0, []), (61, []), (-1, []), (True, []), (1.0, []), ("2", [(0, 1, 1)]), (None, []), (2, None), (2, "ab"), (2, [(0, 1)]), (2, [(0, 1, 1, 1)]),
             (2, [(0, 2, 1)]), (2, [(-1, 1, 1)]), (2, [(0, 1, 10 ** 9 + 1)]), (2, [(0, 1, -10 ** 9 - 1)]), (2, [(0, 1, 1.0)]), (2, [(0, True, 1)]),
             (2, [(0, 1, True)]), (2, [(0, 1, 1), None]), (2, [(0, 1, 1), 5]), (2, [(0, 1, "1")]), (1, [(0, 1, 1)]), (1, [(0, 0, 1.5)]),
             (2, [{0, 1, 2}]), (3, [(0, 1, 1)] * 601), (2, {(0, 1, 1)})]:
    assert bad(n, e), (n, e)
eq(2, [(0, 1, 10 ** 9)] * 600, (10 ** 9, 600, (0,)))
eq(2, [(0, 1, -10 ** 9), (1, 0, -10 ** 9)], (-10 ** 9, 2, (0,)))

# oracle: enumerate all (n-1)-subsets of edge positions in lexicographic order
def oracle(n, E):
    if n == 1:
        return (0, 1, ())
    best = None
    cnt = 0
    arg = None
    for sub in combinations(range(len(E)), n - 1):
        par = list(range(n))

        def f(x):
            while par[x] != x:
                x = par[x]
            return x
        tot = 0
        good = True
        for i in sub:
            u, v, w = E[i]
            a, b = f(u), f(v)
            if a == b:
                good = False
                break
            par[a] = b
            tot += w
        if not good:
            continue
        if best is None or tot < best:
            best, cnt, arg = tot, 1, sub
        elif tot == best:
            cnt += 1
    if best is None:
        return None
    return (best, cnt, arg)

random.seed(4027)
conn = disc = 0
for it in range(220):
    n = random.randint(1, 6)
    m = random.randint(0, 11)
    wr = random.choice([(1, 1), (1, 2), (1, 3), (-1, 2), (0, 4), (5, 5)])
    E = [(random.randrange(n), random.randrange(n), random.randint(*wr)) for _ in range(m)]
    if random.random() < 0.5 and n > 1:
        # make a connected skeleton so that most cases have trees
        perm = list(range(n))
        random.shuffle(perm)
        sk = [(perm[i], perm[random.randrange(i)], random.randint(*wr)) for i in range(1, n)]
        E = (sk + E)[:11]
        random.shuffle(E)
    if random.random() < 0.3:
        E = [[u, v, w] for u, v, w in E]
    exp = oracle(n, E)
    if exp is None:
        assert bad(n, E), (n, E)
        disc += 1
    else:
        eq(n, E, exp)
        conn += 1
assert conn > 100 and disc > 10, (conn, disc)
''', r'''
def _tree_count(k, pairs):
    # number of spanning trees of the multigraph on nodes 0..k-1 (Kirchhoff, Bareiss elimination)
    if k <= 1:
        return 1
    size = k - 1
    M = [[0] * size for _ in range(size)]
    for a, b in pairs:
        if a < size:
            M[a][a] += 1
        if b < size:
            M[b][b] += 1
        if a < size and b < size:
            M[a][b] -= 1
            M[b][a] -= 1
    sign = 1
    prev = 1
    for i in range(size - 1):
        if M[i][i] == 0:
            for r in range(i + 1, size):
                if M[r][i] != 0:
                    M[i], M[r] = M[r], M[i]
                    sign = -sign
                    break
            else:
                return 0
        for r in range(i + 1, size):
            for c in range(i + 1, size):
                M[r][c] = (M[r][c] * M[i][i] - M[r][i] * M[i][c]) // prev
        prev = M[i][i]
    return sign * M[size - 1][size - 1]


def mst_census(n, edges):
    def isi(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isi(n) or not 1 <= n <= 60:
        raise ValueError("n")
    if not isinstance(edges, (list, tuple)) or len(edges) > 600:
        raise ValueError("edges")
    E = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 3 or not all(isi(v) for v in e):
            raise ValueError("edge")
        u, v, w = e
        if not (0 <= u < n and 0 <= v < n and abs(w) <= 10 ** 9):
            raise ValueError("edge range")
        E.append((u, v, w))
    order = sorted(range(len(E)), key=lambda i: (E[i][2], i))
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    weight = 0
    count = 1
    labels = {}
    pos = 0
    while pos < len(order):
        w = E[order[pos]][2]
        end = pos
        while end < len(order) and E[order[end]][2] == w:
            end += 1
        lab = [find(x) for x in range(n)]
        labels[w] = lab
        pairs = [(lab[E[i][0]], lab[E[i][1]]) for i in order[pos:end]]
        pairs = [(a, b) for a, b in pairs if a != b]
        # connected parts of this weight class on the contracted graph
        sub = {}

        def sf(x):
            while sub.setdefault(x, x) != x:
                sub[x] = sub[sub[x]]
                x = sub[x]
            return x
        for a, b in pairs:
            sub[sf(a)] = sf(b)
        parts = {}
        for a, b in pairs:
            parts.setdefault(sf(a), []).append((a, b))
        for plist in parts.values():
            nodes = sorted({x for p in plist for x in p})
            idx = {x: i for i, x in enumerate(nodes)}
            count *= _tree_count(len(nodes), [(idx[a], idx[b]) for a, b in plist])
            weight += w * (len(nodes) - 1)
        for a, b in pairs:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
        pos = end
    if len({find(x) for x in range(n)}) != 1:
        raise ValueError("disconnected")
    chosen = []
    dsus = {}
    for i, (u, v, w) in enumerate(E):
        lab = labels[w]
        a, b = lab[u], lab[v]
        if a == b:
            continue
        d = dsus.setdefault(w, {})

        def f2(x, d=d):
            while d.setdefault(x, x) != x:
                d[x] = d[d[x]]
                x = d[x]
            return x
        ra, rb = f2(a), f2(b)
        if ra != rb:
            d[ra] = rb
            chosen.append(i)
    return (weight, count, tuple(chosen))
''')


task("v4_28_pal_range", r'''
Write `best_palindromes(s, queries)` that answers range queries about palindromic substrings.
`s` is a str with 1..400 characters (any characters; compare them by code point, as Python
compares strings). `queries` is a list or tuple of 0..300 queries, each a list or tuple of two
ints (l, r) (bool is not an int) with 0 <= l <= r < len(s). Anything else is a ValueError, and
one bad query makes the whole call a ValueError. An empty `queries` gives [].
For a query (l, r) consider every palindromic substring that lies completely inside
s[l..r] (both ends included, positions counted in s, not in the slice). A palindrome reads the
same reversed; a single character is a palindrome. Choose one as follows:
1. the longest;
2. among the longest, the one that is smallest as a string (lexicographic comparison; both
   have the same length);
3. if the same string occurs at several positions, the one with the smallest start position.
The answer for the query is the tuple (palindrome, start) with the palindrome as a str and
start its 0-based start index in s. The result is the list of answers in query order.
Example: s = "cbcaba", queries [(0, 5), (0, 2), (4, 4), (1, 4)] gives
[("aba", 3), ("cbc", 0), ("b", 4), ("a", 3)].
In the first query "cbc" (start 0) and "aba" (start 3) both have length 3, "aba" is smaller.
In the last query, s[1..4] = "bcab" has no palindrome longer than 1 character, and "a" is the
smallest of its single characters.
The same string may be a palindrome in several places, e.g. s = "abxab": the query (0, 4) gives
("a", 0), since "a" at 0, "b" at 1, "x" at 2, "a" at 3, "b" at 4 are all of length 1, and
"a" is smallest with the smallest start.
''', r'''
import random

def eq(s, q, exp):
    got = best_palindromes(s, q)
    assert isinstance(got, list) and got == exp, (s, q, got, exp)
    assert all(isinstance(a, tuple) and len(a) == 2 and type(a[0]) is str and type(a[1]) is int for a in got)

def bad(s, q):
    try:
        best_palindromes(s, q)
    except ValueError:
        return True
    return False

eq("cbcaba", [(0, 5), (0, 2), (4, 4), (1, 4)], [("aba", 3), ("cbc", 0), ("b", 4), ("a", 3)])
eq("abxab", [(0, 4)], [("a", 0)])
eq("abxab", [], [])
eq("abxab", (), [])
eq("a", [(0, 0)], [("a", 0)])
eq("a", [[0, 0], [0, 0]], [("a", 0), ("a", 0)])
eq("abacaba", [(0, 6), (1, 5), (0, 2), (2, 4), (3, 6)], [("abacaba", 0), ("bacab", 1), ("aba", 0), ("aca", 2), ("aba", 4)])
eq("abba", [(0, 3), (0, 2), (1, 3), (1, 2)], [("abba", 0), ("bb", 1), ("bb", 1), ("bb", 1)])
eq("zzabbaxx", [(0, 7), (0, 1), (6, 7), (2, 7), (1, 6)], [("abba", 2), ("zz", 0), ("xx", 6), ("abba", 2), ("abba", 2)])
eq("bbaa", [(0, 3), (1, 3), (0, 2)], [("aa", 2), ("aa", 2), ("bb", 0)])
eq("baab", [(0, 3), (0, 1), (1, 2)], [("baab", 0), ("a", 1), ("aa", 1)])
eq("éaé", [(0, 2), (1, 2)], [("éaé", 0), ("a", 1)])
eq("baééab", [(0, 5), (2, 3)], [("baééab", 0), ("éé", 2)])
eq("Ab", [(0, 1)], [("A", 0)])
eq("bA", [(0, 1)], [("A", 1)])
eq("a b", [(0, 2)], [(" ", 1)])
eq("aaaa", [(0, 3), (1, 3), (2, 2)], [("aaaa", 0), ("aaa", 1), ("a", 2)])
eq("abcabc", [(0, 5), (2, 4)], [("a", 0), ("a", 3)])
# invalid
for s, q in [("", []), (None, []), (5, []), ("ab", None), ("ab", [(0, 2)]), ("ab", [(1, 0)]), ("ab", [(-1, 1)]), ("ab", [(0,)]), ("ab", [(0, 1, 1)]),
             ("ab", [(0, 1.0)]), ("ab", [(True, 1)]), ("ab", [(0, True)]), ("ab", [("0", 1)]), ("ab", [None]), ("ab", [5]), ("ab", [(0, 1), (2, 2)]),
             ("ab", "ab"), ("ab", {(0, 1)}), (b"ab", [(0, 1)]), (["a", "b"], [(0, 1)]), ("a" * 401, [(0, 0)]), ("ab", [(0, 0)] * 301), ("ab", [[0, 1], [1]]),
             ("ab", [(0, None)]), ("ab", [(0, 0), (-1, -1)]), ("ab", [(False, 1)])]:
    assert bad(s, q), (s, q)
eq("a" * 400, [(0, 0)] * 300, [("a", 0)] * 300)

# reference by brute force: all substrings inside the range
def oracle(s, qs):
    out = []
    for l, r in qs:
        best = None
        for i in range(l, r + 1):
            for j in range(i + 1, r + 2):
                t = s[i:j]
                if t == t[::-1]:
                    key = (-len(t), t, i)
                    if best is None or key < best:
                        best = key
        out.append((best[1], best[2]))
    return out

random.seed(4028)
alphabets = ["ab", "ab", "abc", "abc", "ba", "xyzw", "aéb", "aA"]
for it in range(150):
    al = random.choice(alphabets)
    n = random.randint(1, 30)
    if random.random() < 0.3:
        # glue palindromes together so that ties are common
        s = ""
        while len(s) < n:
            h = "".join(random.choice(al) for _ in range(random.randint(1, 4)))
            s += h + random.choice(["", h[::-1], h[::-1][1:]])
        s = s[:n]
    else:
        s = "".join(random.choice(al) for _ in range(n))
    qs = []
    for _ in range(random.randint(0, 25)):
        l = random.randrange(len(s))
        r = random.randrange(l, len(s))
        qs.append((l, r) if random.random() < 0.7 else [l, r])
    eq(s, qs, oracle(s, qs))
# all queries of a longer string
s = "".join(random.choice("ab") for _ in range(23))
qs = [(l, r) for l in range(23) for r in range(l, 23)]
eq(s, qs, oracle(s, qs))
# long strings: closed forms
n = 400
eq("a" * n, [(l, r) for l, r in ((0, 399), (5, 100), (399, 399), (17, 18))], [("a" * (r - l + 1), l) for l, r in ((0, 399), (5, 100), (399, 399), (17, 18))])
alt = "ab" * 200
qs = [(0, 399), (1, 399), (3, 3), (0, 1), (10, 20), (11, 20), (250, 399), (251, 399)]
exp = []
for l, r in qs:
    m = r - l + 1
    ln = m if m % 2 == 1 else m - 1
    cands = [(alt[st:st + ln], st) for st in range(l, r - ln + 2)]
    exp.append(min(cands))
eq(alt, qs, exp)
s = "ab" * 99 + "c" + "ba" * 99
eq(s, [(0, 396), (1, 395), (100, 296), (0, 198)], [(s, 0), (s[1:396], 1), (s[100:297], 100), ("ab" * 98 + "a", 0)])
''', r'''
def best_palindromes(s, queries):
    def isi(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(s, str) or not 1 <= len(s) <= 400:
        raise ValueError("s")
    if not isinstance(queries, (list, tuple)) or len(queries) > 300:
        raise ValueError("queries")
    n = len(s)
    qs = []
    for q in queries:
        if not isinstance(q, (list, tuple)) or len(q) != 2 or not isi(q[0]) or not isi(q[1]):
            raise ValueError("query")
        if not 0 <= q[0] <= q[1] < n:
            raise ValueError("range")
        qs.append((q[0], q[1]))
    # Manacher: d1[c] = number of odd palindromes centred at c, d2[c] = even ones with right centre c
    d1 = [0] * n
    lo, hi = 0, -1
    for i in range(n):
        k = 1 if i > hi else min(d1[lo + hi - i], hi - i + 1)
        while i - k >= 0 and i + k < n and s[i - k] == s[i + k]:
            k += 1
        d1[i] = k
        if i + k - 1 > hi:
            lo, hi = i - k + 1, i + k - 1
    d2 = [0] * n
    lo, hi = 0, -1
    for i in range(n):
        k = 0 if i > hi else min(d2[lo + hi - i + 1], hi - i + 1)
        while i - k - 1 >= 0 and i + k < n and s[i - k - 1] == s[i + k]:
            k += 1
        d2[i] = k
        if i + k - 1 > hi:
            lo, hi = i - k, i + k - 1
    out = []
    for l, r in qs:
        best = 0
        cands = []
        for c in range(l, r + 1):
            k = min(d1[c], c - l + 1, r - c + 1)
            ln = 2 * k - 1
            if ln > best:
                best, cands = ln, [c - k + 1]
            elif ln == best:
                cands.append(c - k + 1)
        for c in range(l + 1, r + 1):
            k = min(d2[c], c - l, r - c + 1)
            ln = 2 * k
            if ln > best:
                best, cands = ln, [c - k]
            elif ln == best and ln > 0:
                cands.append(c - k)
        out.append(min((s[st:st + best], st) for st in cands))
    return out
''')


task("v4_29_maximal_runs", r'''
Write `maximal_runs(s)` that lists all maximal repetitions ("runs") of a string.
`s` is a str with 0..300 characters (any characters). Anything else, including a string longer
than 300, is a ValueError.
A period of a string t is an integer p >= 1 such that t[k] == t[k + p] for every k with
0 <= k and k + p < len(t). The smallest period of t is the smallest such p (len(t) itself is
always a period, so one exists for every non-empty t).
A run is a triple (i, j, p) that describes the substring t = s[i:j] (0-based, j exclusive) with
all of these properties:
1. p is the smallest period of t;
2. len(t) >= 2 * p (the pattern repeats at least twice);
3. it cannot be extended to the left with the same period: i == 0 or s[i - 1] != s[i - 1 + p];
4. it cannot be extended to the right with the same period: j == len(s) or s[j] != s[j - p].
The result is the list of all runs as tuples (i, j, p), sorted ascending by i, then j (two runs
never have the same i and j). An empty string, or a string without any run, gives [].
Runs may overlap and may contain other runs. A substring that has several periods (for instance
"aaaa" has the periods 1, 2, 3 and 4) is reported once, with its smallest one.
Example 1: "aabaabaa" gives [(0, 2, 1), (0, 8, 3), (3, 5, 1), (6, 8, 1)]. The substring
"abaaba" (positions 1..6) has period 3 but is not a run, because it extends to the left: "a"
at 0 equals "a" at 3.
Example 2: "abab" gives [(0, 4, 2)]; "aaaa" gives [(0, 4, 1)]; "abcab" gives [].
Example 3: "xaaaxaaax" gives [(0, 9, 4), (1, 4, 1), (5, 8, 1)].
''', r'''
import random

def eq(s, exp):
    got = maximal_runs(s)
    assert isinstance(got, list) and got == exp and all(isinstance(t, tuple) and len(t) == 3 for t in got), (s, got, exp)

def bad(s):
    try:
        maximal_runs(s)
    except ValueError:
        return True
    return False

eq("aabaabaa", [(0, 2, 1), (0, 8, 3), (3, 5, 1), (6, 8, 1)])
eq("abab", [(0, 4, 2)])
eq("aaaa", [(0, 4, 1)])
eq("abcab", [])
eq("xaaaxaaax", [(0, 9, 4), (1, 4, 1), (5, 8, 1)])
eq("", [])
eq("a", [])
eq("aa", [(0, 2, 1)])
eq("ab", [])
eq("aba", [])
eq("abaab", [(2, 4, 1)])
eq("ababa", [(0, 5, 2)])
eq("abaaba", [(0, 6, 3), (2, 4, 1)])
eq("abcabcab", [(0, 8, 3)])
eq("abcabca", [(0, 7, 3)])
eq("abcabc", [(0, 6, 3)])
eq("zabcabcz", [(1, 7, 3)])
eq("aabaab", [(0, 2, 1), (0, 6, 3), (3, 5, 1)])
eq("abaabaab", [(0, 8, 3), (2, 4, 1), (5, 7, 1)])
eq("a" * 300, [(0, 300, 1)])
eq("ab" * 150, [(0, 300, 2)])
eq("abc" * 100, [(0, 300, 3)])
eq("a" * 50 + "b" + "a" * 50, [(0, 50, 1), (51, 101, 1)])
eq("ab" * 5 + "ba" * 5, [(0, 10, 2), (1, 19, 9), (3, 17, 7), (5, 15, 5), (7, 13, 3), (9, 11, 1), (10, 20, 2)])
eq("ééxééx", [(0, 2, 1), (0, 6, 3), (3, 5, 1)])
eq("AaAaA", [(0, 5, 2)])
eq("aAaA", [(0, 4, 2)])
for s in [None, 5, b"abab", ["a", "a"], ("a", "a"), "a" * 301, 1.5, True]:
    assert bad(s), s
eq("a" * 299 + "b", [(0, 299, 1)])

# oracle: test every substring and every period directly
def oracle(s):
    n = len(s)
    out = []
    for i in range(n):
        for j in range(i + 2, n + 1):
            t = s[i:j]
            L = j - i
            p = 0
            for q in range(1, L + 1):
                if all(t[k] == t[k + q] for k in range(L - q)):
                    p = q
                    break
            if 2 * p > L:
                continue
            if i > 0 and s[i - 1] == s[i - 1 + p]:
                continue
            if j < n and s[j] == s[j - p]:
                continue
            out.append((i, j, p))
    return sorted(out)

random.seed(4029)
for it in range(260):
    al = random.choice(["ab", "ab", "ab", "abc", "a", "aab", "xyé"])
    n = random.randint(0, 16)
    r = random.random()
    if r < 0.4:
        s = "".join(random.choice(al) for _ in range(n))
    else:
        blocks = ""
        while len(blocks) < n:
            u = "".join(random.choice(al) for _ in range(random.randint(1, 4)))
            blocks += u * random.randint(1, 4) + random.choice(["", "", u[:2], random.choice(al)])
        s = blocks[:n]
    eq(s, oracle(s))
for it in range(12):
    n = random.randint(40, 70)
    u = "".join(random.choice("ab") for _ in range(random.randint(1, 6)))
    s = ""
    while len(s) < n:
        s += u * random.randint(1, 5) + random.choice(["a", "b", "ab", ""])
    s = s[:n]
    eq(s, oracle(s))
# Fibonacci word, 60 characters
fa, fb = "a", "ab"
while len(fb) < 60:
    fa, fb = fb, fb + fa
eq(fb[:60], oracle(fb[:60]))
''', r'''
def maximal_runs(s):
    if not isinstance(s, str) or len(s) > 300:
        raise ValueError("s")
    n = len(s)
    out = []
    for p in range(1, n // 2 + 1):
        k = 0
        while k + p < n:
            if s[k] != s[k + p]:
                k += 1
                continue
            a = k
            while k + p < n and s[k] == s[k + p]:
                k += 1
            if k - a >= p:
                t = s[a:k + p]
                pi = [0] * len(t)
                for x in range(1, len(t)):
                    q = pi[x - 1]
                    while q and t[x] != t[q]:
                        q = pi[q - 1]
                    if t[x] == t[q]:
                        q += 1
                    pi[x] = q
                if len(t) - pi[-1] == p:
                    out.append((a, k + p, p))
    out.sort()
    return out
''')


task("v4_30_cocircular", r'''
Write `densest_circle(points)` that finds the circle holding the most of the given points.
`points` is a list or tuple of 0..40 points, each a list or tuple of two ints (x, y) (bool is
not an int) with |x|, |y| <= 10**6. The points must be pairwise different. Anything else is a
ValueError. A point is identified by its position in `points`, counted from 0.
Consider every circle that passes through at least three of the points that are not on one
line (three points on one line lie on no circle; any three points that are not on one line
lie on exactly one circle). For such a circle C let S(C) be the set of positions of all the
points that lie exactly on C (on the circle itself, not inside it). The answer is
(k, indices): k = the largest |S(C)| over all these circles, and indices = the tuple of the
positions in S(C), ascending. If several circles reach the largest k, pick the one whose
ascending position tuple is lexicographically smallest (first difference decides; all these
tuples have length k). If there are fewer than 3 points, or all the points are on one line, so
that no circle exists, the answer is (0, ()).
The test must be exact: coordinates are up to 10**6, so floating point is not safe. At most 40
points means about 10**4 triples, which is fine.
Example 1: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)] gives (4, (0, 1, 3, 4)). The four corners
of the square lie on the circle with centre (1, 1); the centre point itself is not on it.
Example 2: [(0, 0), (1, 0), (0, 1), (1, 1), (5, 5), (6, 5), (5, 6), (6, 6)] gives
(4, (0, 1, 2, 3)): two circles hold 4 points each, the one with the smaller position tuple wins.
Example 3: [(0, 0), (1, 1), (2, 2), (0, 3)] gives (3, (0, 1, 3)): positions 0, 1, 2 are on one
line, and the three triples that are not on one line each give a circle with 3 points.
''', r'''
import random
from fractions import Fraction as F
from itertools import combinations

# oracle: every triple, centre and r^2 by Cramer with Fractions, then test all points
def oracle(P):
    best = (0, ())
    n = len(P)
    for i, j, k in combinations(range(n), 3):
        (ax, ay), (bx, by), (cx, cy) = P[i], P[j], P[k]
        det = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if det == 0:
            continue
        b2 = (bx * bx + by * by - ax * ax - ay * ay)
        c2 = (cx * cx + cy * cy - ax * ax - ay * ay)
        # 2(bx-ax) X + 2(by-ay) Y = b2 ; 2(cx-ax) X + 2(cy-ay) Y = c2
        X = F(b2 * (cy - ay) - c2 * (by - ay), 2 * det)
        Y = F(c2 * (bx - ax) - b2 * (cx - ax), 2 * det)
        r2 = (ax - X) ** 2 + (ay - Y) ** 2
        mem = tuple(t for t in range(n) if (P[t][0] - X) ** 2 + (P[t][1] - Y) ** 2 == r2)
        assert i in mem and j in mem and k in mem
        if len(mem) > best[0] or (len(mem) == best[0] and mem < best[1]):
            best = (len(mem), mem)
    return best

def eq(p, exp):
    got = densest_circle(p)
    assert isinstance(got, tuple) and len(got) == 2 and got == exp and type(got[0]) is int and isinstance(got[1], tuple), (p, got, exp)
    if len(p) <= 12:
        assert oracle(p) == exp, ("test expectation disagrees with the oracle", p, exp)

def bad(p):
    try:
        densest_circle(p)
    except ValueError:
        return True
    return False

eq([(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)], (4, (0, 1, 3, 4)))
eq([(0, 0), (1, 0), (0, 1), (1, 1), (5, 5), (6, 5), (5, 6), (6, 6)], (4, (0, 1, 2, 3)))
eq([(5, 5), (6, 5), (5, 6), (6, 6), (0, 0), (1, 0), (0, 1), (1, 1)], (4, (0, 1, 2, 3)))
eq([(0, 0), (1, 1), (2, 2), (0, 3)], (3, (0, 1, 3)))
eq([], (0, ()))
eq([(0, 0)], (0, ()))
eq([(0, 0), (1, 0)], (0, ()))
eq([(0, 0), (1, 1), (2, 2)], (0, ()))
eq([(0, 0), (1, 1), (2, 2), (-3, -3), (10, 10)], (0, ()))
eq([(3, 0), (0, 0), (7, 0), (1, 0)], (0, ()))
eq([(0, 0), (1, 0), (0, 1)], (3, (0, 1, 2)))
eq(((0, 0), (1, 0), (0, 1)), (3, (0, 1, 2)))
eq([[0, 0], [4, 0], [0, 3]], (3, (0, 1, 2)))
eq([(0, 0), (1, 0), (0, 1), (2, 2)], (3, (0, 1, 2)))
eq([(0, 0), (1, 0), (0, 1), (1, 1)], (4, (0, 1, 2, 3)))
eq([(1, 1), (0, 0), (1, 0), (0, 1), (3, 7)], (4, (0, 1, 2, 3)))
# the unit square plus its centre and a point inside the circle: still the 4 corners
eq([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1), (1, 0)], (4, (0, 1, 2, 3)))
# a point inside or outside, not on the circle (distance squared 2 vs 1 and 3)
eq([(0, 0), (2, 0), (0, 2), (2, 2), (1, 1)], (4, (0, 1, 2, 3)))
# 12 lattice points on x^2 + y^2 = 25, shuffled, plus 8 others
ring = [(5, 0), (-5, 0), (0, 5), (0, -5), (3, 4), (3, -4), (-3, 4), (-3, -4), (4, 3), (4, -3), (-4, 3), (-4, -3)]
other = [(1, 1), (2, 3), (-2, 1), (6, 6), (7, -1), (0, 0), (1, -4), (-1, 2)]
P = ring + other
eq(P, (12, tuple(range(12))))
Q = P[::3] + P[1::3] + P[2::3]
eq(Q, (12, tuple(sorted(i for i, q in enumerate(Q) if q[0] ** 2 + q[1] ** 2 == 25))))
# huge scale and offset
S = 10 ** 5
eq([(x * S + 3, y * S - 7) for x, y in ring[:6] + [(1, 1), (2, 3)]], (6, (0, 1, 2, 3, 4, 5)))
M = 10 ** 6
eq([(M, 0), (-M, 0), (0, M), (0, -M), (0, 0), (M - 1, 0)], (4, (0, 1, 2, 3)))
eq([(M, M), (-M, -M), (M, -M), (-M, M), (M, 0)], (4, (0, 1, 2, 3)))
eq([(M, M), (M - 1, M), (M, M - 1), (-M, -M), (M - 1, M - 1)], (4, (0, 1, 2, 4)))
# lexicographic choice between circles of equal size, different sizes of circles
eq([(0, 0), (9, 9), (1, 0), (9, 10), (0, 1), (10, 9), (1, 1), (10, 10)], (4, (0, 2, 4, 6)))
eq([(9, 9), (0, 0), (9, 10), (1, 0), (10, 9), (0, 1), (10, 10), (1, 1)], (4, (0, 2, 4, 6)))
# 40 points on a 7 x 6 grid: circles with 8 lattice points exist; check the answer is a real circle with k >= 8
G = [(x, y) for x in range(7) for y in range(6)][:40]
for GG in (G, G[::-1], G[7:] + G[:7]):
    k, idx = densest_circle(GG)
    assert k >= 8 and len(idx) == k and list(idx) == sorted(idx) and len(set(idx)) == k
    a, b, c = (GG[i] for i in idx[:3])
    det = 2 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    assert det != 0
    ux = ((c[1] - a[1]) * ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) - (b[1] - a[1]) * ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2)) / det
    uy = ((b[0] - a[0]) * ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) - (c[0] - a[0]) * ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)) / det
    cx, cy = a[0] + ux, a[1] + uy
    assert all(abs((GG[i][0] - cx) ** 2 + (GG[i][1] - cy) ** 2 - ux * ux - uy * uy) < 1e-9 for i in idx)
    assert sum(1 for q in GG if abs((q[0] - cx) ** 2 + (q[1] - cy) ** 2 - ux * ux - uy * uy) < 1e-9) == k
# errors
for p in [None, 5, "ab", {(0, 0), (1, 1), (2, 5)}, [(0, 0), (0, 0), (1, 1)], [(0, 0), (1, 0), (0, 0)], [(0, 0), (1, 0), [0, 0]], [(0, 0), (1, 0), (0, 1.0)],
          [(0, 0), (1, 0), (0, True)], [(0, 0), (1, 0), (0,)], [(0, 0), (1, 0), (0, 1, 2)], [(0, 0), (1, 0), (0, M + 1)], [(0, 0), (1, 0), (-M - 1, 1)],
          [(0, 0), (1, 0), None], [(0, 0), (1, 0), 3], [(0, 0), (1, 0), "ab"], [(0, 0), (1, 0), (0, "1")], [(i, i * i) for i in range(41)],
          [(0, 0), (0, 0)], [(1, 1), (1, 1)], [(0, 0), (1, 0), (False, 1)], [(0, 0), (1, 0), (0, None)]]:
    assert bad(p), p

random.seed(4030)
for it in range(200):
    R = random.choice([2, 3, 3, 4, 5])
    n = random.randint(0, 10)
    allp = [(x, y) for x in range(-R, R + 1) for y in range(-R, R + 1)]
    if random.random() < 0.3:
        # prefer lattice points on a few circles around the origin
        rad = random.choice([1, 2, 4, 5, 8, 9, 10, 13, 25])
        allp = [q for q in allp if q[0] ** 2 + q[1] ** 2 in (rad, rad + 1, 2 * rad)] or allp
    n = min(n, len(allp))
    P = random.sample(allp, n)
    if random.random() < 0.3:
        P = [list(q) for q in P]
    eq(P, oracle(P))
for it in range(6):
    P = random.sample([(x, y) for x in range(-3, 4) for y in range(-3, 4)], random.randint(12, 14))
    eq_o = oracle(P)
    eq(P, eq_o)
Pm = [(x * 1000 + y, y * 999 - x) for x in range(-2, 3) for y in range(-2, 3)]
eq(Pm[:12], oracle(Pm[:12]))
''', r'''
from math import gcd


def densest_circle(points):
    def ok(v):
        return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= 10 ** 6
    if not isinstance(points, (list, tuple)) or len(points) > 40:
        raise ValueError("points")
    P = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not ok(p[0]) or not ok(p[1]):
            raise ValueError("point")
        P.append((p[0], p[1]))
    if len(set(P)) != len(P):
        raise ValueError("duplicate")
    n = len(P)
    groups = {}
    for i in range(n):
        ax, ay = P[i]
        for j in range(i + 1, n):
            bx, by = P[j][0] - ax, P[j][1] - ay
            b2 = bx * bx + by * by
            for k in range(j + 1, n):
                cx, cy = P[k][0] - ax, P[k][1] - ay
                d = 2 * (bx * cy - by * cx)
                if d == 0:
                    continue
                c2 = cx * cx + cy * cy
                ux = cy * b2 - by * c2
                uy = bx * c2 - cx * b2
                X, Y = ax * d + ux, ay * d + uy
                r2 = ux * ux + uy * uy
                if d < 0:
                    d, X, Y = -d, -X, -Y
                g = gcd(gcd(X, Y), d)
                den = d * d
                h = gcd(r2, den)
                key = (X // g, Y // g, d // g, r2 // h, den // h)
                s = groups.get(key)
                if s is None:
                    groups[key] = {i, j, k}
                else:
                    s.add(i)
                    s.add(j)
                    s.add(k)
    best = (0, ())
    for s in groups.values():
        cand = (len(s), tuple(sorted(s)))
        if cand[0] > best[0] or (cand[0] == best[0] and cand[1] < best[1]):
            best = cand
    return best
''')

TASKS = T
PROBE_IDS = [t["id"] for t in T[:10]]
