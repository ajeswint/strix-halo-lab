"""loop-v3: 30 held-out Python tasks for the loop-alone headroom run (Roadmap item 2).

Same layout as tasks_v2.py: id, prompt, tests, ref. Written 2026-10-06, modelled on the 7 v2
tasks early-stop best-of-16 failed (apply_patch, int_eval, str_literal, xml_lite,
tree_max_path, min_cost_flow, best_rational): multi-rule specs with error cases and
tie-break rules. None was used for prompt or loop iteration. Every test file has exactly
one random.seed(N) line (N = 3001..3030), so agent.py's fresh-seed grade applies to all 30.
v3_01-10 parsers/interpreters/formats, v3_11-20 graphs/trees/DP/data structures, v3_21-30
number theory/exact arithmetic/geometry/calendars/simulation. Seeded random cases are
checked against an oracle inside the test, not against the ref; _banned() rejects stdlib
modules that would trivialize a task.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("v3_01_ini_interp", r'''
Write `parse_ini(text: str) -> dict[str, dict[str, str]]` that parses an INI file and expands
`${...}` references in the values. Rules:
- Lines are separated by "\n"; one "\r" at the end of a line is removed. Each line is then
  stripped of leading and trailing spaces and tabs. Empty lines and lines whose first
  character is ";" or "#" are ignored.
- A NAME is a non-empty string of characters from A-Z a-z 0-9 "_" "." "-".
- Section header: a line starting with "[" and ending with "]"; the text between them,
  stripped of spaces/tabs, must be a NAME (case-sensitive), else ValueError. A header that
  repeats an earlier section continues that section.
- Key line: any other line containing "="; it is split at the FIRST "=". The key, stripped,
  must be a NAME and is stored lowercased (keys are case-insensitive). The value is the rest,
  stripped of spaces/tabs, and may contain "=", ";", "#", "[" and "]". A key that already
  exists in the same section (including from an earlier header of the same section, compared
  case-insensitively) raises ValueError.
- Keys before the first header belong to the section "" (empty name). The result contains
  every section whose header appears, and "" only if it has keys. A line that is neither
  ignored, a header nor a key line raises ValueError.
- After the whole file is read, every value is expanded:
  - "$$" is a literal "$".
  - "${key}" is replaced by the expanded value of `key` in the same section as the value
    being expanded; "${sec:key}" by the expanded value of `key` in section `sec` ("${:key}"
    means section ""). Split at the first ":". `key` must be a NAME and is matched
    case-insensitively; `sec` must be "" or a NAME and is case-sensitive.
  - The referenced value is expanded in the context of its OWN section (a "${k}" inside it
    refers to its own section). References may point forward in the file.
  - Replacement text is not scanned again: "$${a}" is the literal text "${a}".
  - ValueError for: a "$" followed by anything other than "$" or "{" (or at the end of the
    value); a "${" with no closing "}"; an invalid key or section name in a reference; a
    reference to a missing section or key; a reference cycle (a value that, directly or
    through other references, needs its own expansion).
Examples: "[a]\nX = 1\ny = ${x}$$ ${b:z}\n[b]\nz=${a:x}!" gives
{"a": {"x": "1", "y": "1$ 1!"}, "b": {"z": "1!"}}. With "z=${Y}" instead, b has no key "y"
(references without a section look in their own section): ValueError. With "z=${a:Y}", b.z
needs a.y, which needs b.z: a cycle, ValueError.
Do not use the configparser module.
''', r'''
_banned(mods=("configparser",))
import random
def bad(s):
    try:
        parse_ini(s)
    except ValueError:
        return True
    return False
assert parse_ini("") == {}
assert parse_ini("; c\n# d\n\n") == {}
assert parse_ini("[s]") == {"s": {}}
assert parse_ini("k=v") == {"": {"k": "v"}}
assert parse_ini("[a]\nX = 1\ny = ${x}$$ ${b:z}\n[b]\nz=${a:x}!") == {"a": {"x": "1", "y": "1$ 1!"}, "b": {"z": "1!"}}
assert parse_ini("[ a.b-c_1 ]\r\n  key =  v = w ; x  \r\n") == {"a.b-c_1": {"key": "v = w ; x"}}
assert parse_ini("[s]\na=1\n[t]\n[s]\nb=${A}2") == {"s": {"a": "1", "b": "12"}, "t": {}}
assert parse_ini("k=\n[s]\nj=${:k}x") == {"": {"k": ""}, "s": {"j": "x"}}
assert parse_ini("[s]\na=$${b}\nb=$$$$") == {"s": {"a": "${b}", "b": "$$"}}
assert parse_ini("[s]\na=${b}${b}\nb=${c}-\nc=[x]") == {"s": {"a": "[x]-[x]-", "b": "[x]-", "c": "[x]"}}
assert parse_ini("[s]\na=${t:k}\n[t]\nk=${j}\nj=J") == {"s": {"a": "J"}, "t": {"k": "J", "j": "J"}}
assert parse_ini("[S]\na=1\n[s]\na=${S:a}") == {"S": {"a": "1"}, "s": {"a": "1"}}
assert parse_ini("[s]\na={x}$${}") == {"s": {"a": "{x}${}"}}
assert parse_ini("\t[s]\t\n\tk\t=\tv\t") == {"s": {"k": "v"}}
for s in ["[]", "[ ]", "[a b]", "[a", "a]", "x", "=v", "a b=c", "[s]\na=1\nA=2", "[s]\na=1\n[s]\na=2",
          "[s]\na=$", "[s]\na=$x", "[s]\na=${b", "[s]\na=${}", "[s]\na=${b c}", "[s]\na=${t:b}",
          "[s]\na=${b}", "[s]\na=${a}", "[s]\na=${b}\nb=${a}", "[s]\na=${s:b}\nb=${c}\nc=${A}",
          "[s]\na=${x y:b}", "[s]\na=${:b}", "k=${k}", "[s]\na=1\n[t]\nb=${S:a}", "[s]\na=${s:b:c}",
          "[s]\na=$$$", "[s]\nok=1\nbad=${nope}"]:
    assert bad(s), s
random.seed(3001)
NAMECH = "abcXYZ019_.-"
LIT = "abc XYZ09=;#[]:{}}$"
def name(n):
    return "".join(random.choice(NAMECH) for _ in range(random.randint(1, n)))
for _ in range(400):
    secs = []
    for _ in range(random.randint(1, 4)):
        s = name(4)
        if s not in secs:
            secs.append(s)
    if random.random() < 0.3:
        secs.insert(0, "")
    keys = []          # (sec, key) in definition order
    raw = {}           # (sec, key) -> raw value text
    exp = {}
    order = []
    for s in secs:
        used = set()
        for _ in range(random.randint(0 if s else 1, 4)):
            k = name(5).lower()
            if k in used:
                continue
            used.add(k)
            parts_raw, parts_exp = [], []
            for _ in range(random.randint(0, 4)):
                if keys and random.random() < 0.45:
                    rs, rk = random.choice(keys)
                    shown = "".join(c.upper() if random.random() < 0.4 else c for c in rk)
                    if rs == s and random.random() < 0.6:
                        parts_raw.append("${" + shown + "}")
                    else:
                        parts_raw.append("${" + rs + ":" + shown + "}")
                    parts_exp.append(exp[(rs, rk)])
                else:
                    lit = "".join(random.choice(LIT) for _ in range(random.randint(1, 4)))
                    parts_raw.append(lit.replace("$", "$$"))
                    parts_exp.append(lit)
            r, e = "".join(parts_raw), "".join(parts_exp)
            if r != r.strip(" \t"):
                continue
            keys.append((s, k))
            raw[(s, k)] = r
            exp[(s, k)] = e
            order.append((s, k))
    # render: sections in random order, each split over 1-2 headers; "" keys first
    lines = []
    def ws():
        return random.choice(["", "", " ", "\t", "  "])
    nl = random.choice(["\n", "\r\n"])
    want = {}
    for s in secs:
        mine = [k for (ss, k) in order if ss == s]
        if s:
            want[s] = {}
        elif mine:
            want[s] = {}
        for k in mine:
            want[s][k] = exp[(s, k)]
    plan = []
    for s in secs:
        mine = [k for (ss, k) in order if ss == s]
        random.shuffle(mine)
        if s == "":
            plan.insert(0, ("", mine))
            continue
        cut = random.randint(0, len(mine))
        plan.append((s, mine[:cut]))
        if random.random() < 0.4:
            plan.append((s, mine[cut:]))
        else:
            plan[-1] = (s, mine)
    head = [p for p in plan if p[0] == ""]
    rest = [p for p in plan if p[0] != ""]
    random.shuffle(rest)
    for s, ks in head + rest:
        if s:
            lines.append(ws() + "[" + ws() + s + ws() + "]" + ws())
        for k in ks:
            if random.random() < 0.2:
                lines.append(ws() + random.choice([";", "#"]) + " note = ${x}")
            if random.random() < 0.15:
                lines.append(ws())
            shown = "".join(c.upper() if random.random() < 0.3 else c for c in k)
            lines.append(ws() + shown + ws() + "=" + ws() + raw[(s, k)] + ws())
    text = nl.join(lines) + random.choice(["", nl])
    got = parse_ini(text)
    assert got == want, (text, got, want)
    if order:
        s, k = random.choice(order)
        if raw[(s, k)] and random.random() < 0.5:
            t2 = text + nl + ("[" + s + "]" if s else "[" + secs[-1] + "]") + nl + k.upper() + "=dup"
            if s == "" :
                t2 = k + "=dup" + nl + text
            assert bad(t2), t2
''', r'''
import re

_NAME = re.compile(r"[A-Za-z0-9_.\-]+\Z")


def _is_name(s):
    return bool(_NAME.match(s))


def parse_ini(text):
    data = {}
    seen = []
    cur = ""
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        line = line.strip(" \t")
        if not line or line[0] in ";#":
            continue
        if line[0] == "[" and line[-1] == "]" and len(line) >= 2:
            nm = line[1:-1].strip(" \t")
            if not _is_name(nm):
                raise ValueError("bad section name")
            cur = nm
            data.setdefault(cur, {})
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip(" \t")
            if not _is_name(k):
                raise ValueError("bad key")
            k = k.lower()
            sec = data.setdefault(cur, {})
            if k in sec:
                raise ValueError("duplicate key")
            sec[k] = v.strip(" \t")
            continue
        raise ValueError("bad line")
    done = {}
    active = set()

    def expand(sec, key):
        if (sec, key) in done:
            return done[(sec, key)]
        if (sec, key) in active:
            raise ValueError("cycle")
        active.add((sec, key))
        raw = data[sec][key]
        out = []
        i = 0
        n = len(raw)
        while i < n:
            c = raw[i]
            if c != "$":
                out.append(c)
                i += 1
                continue
            if i + 1 >= n:
                raise ValueError("lone $")
            if raw[i + 1] == "$":
                out.append("$")
                i += 2
                continue
            if raw[i + 1] != "{":
                raise ValueError("bad $")
            j = raw.find("}", i + 2)
            if j < 0:
                raise ValueError("unterminated ${")
            ref = raw[i + 2:j]
            if ":" in ref:
                rs, rk = ref.split(":", 1)
                if rs != "" and not _is_name(rs):
                    raise ValueError("bad section in reference")
            else:
                rs, rk = sec, ref
            if not _is_name(rk):
                raise ValueError("bad key in reference")
            rk = rk.lower()
            if rs not in data or rk not in data[rs]:
                raise ValueError("missing reference")
            out.append(expand(rs, rk))
            i = j + 1
        active.discard((sec, key))
        done[(sec, key)] = "".join(out)
        return done[(sec, key)]

    return {s: {k: expand(s, k) for k in d} for s, d in data.items()}
''')


task("v3_02_forth_vm", r'''
Write `forth(src: str) -> list[int]` that runs a small Forth dialect and returns the final
data stack, bottom first. Rules:
- The source is split into words on any whitespace. Words are case-insensitive.
- A word matching an optional "-" followed by one or more ASCII digits is a number literal and
  pushes its value ("-0" is 0, "007" is 7). Every other word is looked up in the dictionary.
- Built-in words (stack effect written "before -- after", top of stack on the right):
  `+ - *` ( a b -- a+b / a-b / a*b ); `/` ( a b -- a//b ) and `mod` ( a b -- a%b ) with
  Python's floor semantics; `/mod` ( a b -- a%b a//b ); `negate` ( a -- -a ); `abs`;
  `dup` ( a -- a a ); `drop` ( a -- ); `swap` ( a b -- b a ); `over` ( a b -- a b a );
  `rot` ( a b c -- b c a ); `=` `<` `>` ( a b -- flag ) where the flag is -1 for true and 0
  for false. `/`, `mod` and `/mod` with b == 0 raise ZeroDivisionError. A word that needs more
  items than the stack holds raises ValueError (the stack is left as it was is not required).
- Definitions: `: name body ;`. `name` is the word after ":" and must not be a number
  literal (ValueError); it may be any other word, including a built-in name, which it then
  replaces for everything that follows. Words in the body are resolved WHEN THE DEFINITION IS
  MADE (early binding): later redefinitions of a word do not change bodies that already used
  it, and inside its own body `name` means its previous definition (ValueError if it had
  none). A body word that is not a literal, a control word, or currently defined raises
  ValueError at definition time.
- Control words, allowed only inside a body: `if ... then`, `if ... else ... then` (pops a
  flag; nonzero runs the first branch), and `begin ... until` (runs the loop body, then pops
  a flag; repeats while the flag is 0). They nest. Unbalanced or misplaced control words in
  a body (e.g. `else` without `if`, `then` without `if`, `until` closing an `if`, an `if`
  left open at ";") raise ValueError when the definition is made. Control words outside a
  body raise ValueError.
- ":" inside a body, ";" outside a body, a ":" with no name after it, and a definition
  missing its ";" at the end of the source raise ValueError. An unknown word outside a body
  raises ValueError.
- Words run in order; an error stops execution and is raised.
Examples: forth("1 2 swap") == [2, 1]; forth(": sq dup * ; 3 sq") == [9];
forth(": foo 5 ; : bar foo ; : foo 6 ; bar foo") == [5, 6];
forth(": dup dup dup ; 1 dup") == [1, 1, 1];
forth(": cnt begin 1 - dup 0 = until ; 3 cnt") == [0].
''', r'''
import random
def run(s):
    try:
        return forth(s)
    except ValueError:
        return "V"
    except ZeroDivisionError:
        return "Z"
fixed = {
    "": [], "1 2 swap": [2, 1], ": sq dup * ; 3 sq": [9], ": foo 5 ; : bar foo ; : foo 6 ; bar foo": [5, 6],
    ": dup dup dup ; 1 dup": [1, 1, 1], ": cnt begin 1 - dup 0 = until ; 3 cnt": [0],
    "-7 2 /": [-4], "-7 2 mod": [1], "7 -2 /mod": [-1, -4], "1 2 3 rot": [2, 3, 1], "1 2 over": [1, 2, 1],
    "3 negate abs": [3], "-0 007": [0, 7], "1 2 = 2 2 = 1 2 < 2 1 >": [0, -1, -1, -1],
    ": t if 10 else 20 then ; 1 t 0 t -5 t": [10, 20, 10],
    ": t if 1 if 2 else 3 then else 4 then ; 1 t 0 t": [2, 4],
    ": SWAP dup ; 1 2 swap": [1, 2, 2], "1 DUP Drop": [1],
    ": fact dup 1 > if dup 1 - fact * then ;": "V",
    ": f 1 ; : f f 1 + ; : f f f * ; f": [4],
    ": sum 0 swap begin swap over + swap 1 - dup 0 = until drop ; 4 sum": [10],
    ": a 1 ; : b a a ; : a 2 ; : c b a ; c": [1, 1, 2],
    ": + - ; 5 3 + : - * ; 5 3 -": [2, 15],
    ": e if then ; 1 e 2": [2], ": l begin 0 until ; 0 1 = ": [0],
}
for s, v in fixed.items():
    assert run(s) == v, (s, run(s), v)
for s in ["foo", "1 +", "drop", "if", "1 then", "else", "begin", "0 until", ";", ":", ": 5 1 ;", ": -3 1 ;",
          ": f : g ; ;", ": f 1", ": f if ;", ": f then ;", ": f else ;", ": f until ;", ": f begin ;",
          ": f if 1 until ;", ": f begin 1 then ;", ": f if else else then ;", ": f g ;", ": f f ;",
          "1 2 3 rot rot rot rot drop drop drop drop", ": f 1 ; ; ", "1 swap", "1 over"]:
    assert run(s) == "V", (s, run(s))
for s in ["1 0 /", "1 0 mod", "1 0 /mod", ": f 0 / ; 1 f", "1 0 / foo"]:
    assert run(s) == "Z", s
assert run("foo 1 0 /") == "V"

# oracle: definitions are stored as fully expanded primitive token lists; execution scans them
PRIMS = ["+", "-", "*", "/", "mod", "/mod", "negate", "abs", "dup", "drop", "swap", "over", "rot", "=", "<", ">"]
CTRL = ["if", "else", "then", "begin", "until"]
def isnum(w):
    d = w[1:] if w[:1] == "-" else w
    return d != "" and all(c in "0123456789" for c in d)
class Err(Exception):
    pass
def oracle(src):
    words = [w.lower() for w in src.split()]
    defs = {}
    st = []
    def need(n):
        if len(st) < n:
            raise Err("V")
    def prim(w):
        if isnum(w):
            st.append(int(w)); return
        if w in ("+", "-", "*", "/", "mod", "/mod", "=", "<", ">"):
            need(2); b = st.pop(); a = st.pop()
            if w in ("/", "mod", "/mod") and b == 0:
                raise Err("Z")
            st.extend({"+": lambda: [a + b], "-": lambda: [a - b], "*": lambda: [a * b], "/": lambda: [a // b],
                       "mod": lambda: [a % b], "/mod": lambda: [a % b, a // b], "=": lambda: [-(a == b)],
                       "<": lambda: [-(a < b)], ">": lambda: [-(a > b)]}[w]())
        elif w in ("negate", "abs", "dup", "drop"):
            need(1); a = st.pop()
            st.extend({"negate": [-a], "abs": [abs(a)], "dup": [a, a], "drop": []}[w])
        elif w in ("swap", "over"):
            need(2); b = st.pop(); a = st.pop()
            st.extend([b, a] if w == "swap" else [a, b, a])
        elif w == "rot":
            need(3); c = st.pop(); b = st.pop(); a = st.pop()
            st.extend([b, c, a])
    def match(code, i, opens, closes):
        depth = 0
        while i < len(code):
            w = code[i]
            if w in ("if", "begin"):
                depth += 1
            elif w in ("then", "until"):
                if depth == 0:
                    return i
                depth -= 1
            elif w == "else" and depth == 0 and "else" in closes:
                return i
            i += 1
        return i
    def execute(code):
        # code is a flat list of primitives, literals and control words
        i = 0
        loops = []
        while i < len(code):
            w = code[i]
            if w == "if":
                need(1); f = st.pop()
                if f == 0:
                    j = match(code, i + 1, None, ("else",))
                    i = j + 1
                    continue
            elif w == "else":
                j = match(code, i + 1, None, ())
                i = j + 1
                continue
            elif w == "then":
                pass
            elif w == "begin":
                loops.append(i)
            elif w == "until":
                need(1); f = st.pop()
                if f == 0:
                    i = loops[-1] + 1
                    continue
                loops.pop()
            else:
                prim(w)
            i += 1
    def check_ctrl(body):
        stack = []
        for w in body:
            if w in ("if", "begin"):
                stack.append(w)
            elif w == "else":
                if not stack or stack[-1] != "if":
                    raise Err("V")
                stack[-1] = "else"
            elif w == "then":
                if not stack or stack[-1] not in ("if", "else"):
                    raise Err("V")
                stack.pop()
            elif w == "until":
                if not stack or stack[-1] != "begin":
                    raise Err("V")
                stack.pop()
        if stack:
            raise Err("V")
    def lookup(w):
        if isnum(w):
            return [w]
        if w in defs:
            return defs[w]
        if w in PRIMS:
            return [w]
        raise Err("V")
    i = 0
    try:
        while i < len(words):
            w = words[i]
            if w == ":":
                if i + 1 >= len(words):
                    raise Err("V")
                name = words[i + 1]
                if isnum(name):
                    raise Err("V")
                try:
                    end = words.index(";", i + 2)
                except ValueError:
                    raise Err("V")
                body = words[i + 2:end]
                if ":" in body:
                    raise Err("V")
                exp = []
                for b in body:
                    exp.extend([b] if b in CTRL else lookup(b))
                check_ctrl(body)
                defs[name] = exp
                i = end + 1
                continue
            if w == ";" or w in CTRL:
                raise Err("V")
            execute(lookup(w))
            i += 1
    except Err as e:
        return str(e)
    return st
# sanity: the oracle agrees with the fixed table
for s, v in fixed.items():
    assert oracle(s) == v, ("oracle", s)
random.seed(3002)
OPS = ["+", "-", "*", "/", "mod", "/mod", "negate", "abs", "dup", "drop", "swap", "over", "rot", "=", "<", ">"]
def lit():
    return str(random.choice([0, 1, 2, 3, -1, -2, 5, 7, 10, random.randint(-20, 20)]))
def straight(n, names):
    out = []
    for _ in range(n):
        r = random.random()
        if r < 0.4:
            out.append(lit())
        elif r < 0.85 or not names:
            out.append(random.choice(OPS))
        else:
            out.append(random.choice(names))
    return out
def body(names, d):
    out = straight(random.randint(0, 4), names)
    r = random.random()
    if d > 0 and r < 0.35:
        out += [lit(), "if"] + body(names, d - 1)
        if random.random() < 0.5:
            out += ["else"] + body(names, d - 1)
        out += ["then"]
    elif d > 0 and r < 0.5:
        k = random.randint(1, 4)
        inner = random.choice([[], ["dup", "drop"], ["swap", "swap"], ["1", "+", "1", "-"]])
        out += [str(k), "begin"] + inner + ["1", "-", "dup", "0", "=", "until", "drop"]
    elif d > 0 and r < 0.6:
        out += ["0", str(random.randint(1, 4)), "begin", "swap", "over", "+", "swap", "1", "-", "dup", "0", "=", "until", "drop"]
    return out + straight(random.randint(0, 3), names)
for _ in range(2500):
    names = []
    prog = []
    for _ in range(random.randint(0, 4)):
        nm = random.choice(["f", "g", "h", "sq", "F", "G"])
        prog += [":", nm] + body(names, 2) + [";"]
        names.append(nm)
        if random.random() < 0.5:
            prog += straight(random.randint(0, 3), names)
    prog += [lit() for _ in range(random.randint(0, 4))] + straight(random.randint(1, 8), names)
    if random.random() < 0.1:
        prog.insert(random.randint(0, len(prog)), random.choice(["if", "then", ";", "until", "nope", ":"]))
    src = random.choice([" ", "  ", "\n", "\t "]).join(prog)
    exp = oracle(src)
    got = run(src)
    assert got == exp, (src, got, exp)
''', r'''
def _isnum(w):
    d = w[1:] if w.startswith("-") else w
    return d != "" and all("0" <= c <= "9" for c in d)


_CTRL = ("if", "else", "then", "begin", "until")


def _need(st, n):
    if len(st) < n:
        raise ValueError("stack underflow")


def _builtin(name):
    def bin2(f, zero_check=False):
        def run(st):
            _need(st, 2)
            b = st.pop()
            a = st.pop()
            if zero_check and b == 0:
                st.append(a)
                st.append(b)
                raise ZeroDivisionError("division by zero")
            st.extend(f(a, b))
        return run

    def un(f):
        def run(st):
            _need(st, 1)
            st.extend(f(st.pop()))
        return run

    def rot(st):
        _need(st, 3)
        c = st.pop()
        b = st.pop()
        a = st.pop()
        st.extend([b, c, a])

    table = {
        "+": bin2(lambda a, b: [a + b]),
        "-": bin2(lambda a, b: [a - b]),
        "*": bin2(lambda a, b: [a * b]),
        "/": bin2(lambda a, b: [a // b], True),
        "mod": bin2(lambda a, b: [a % b], True),
        "/mod": bin2(lambda a, b: [a % b, a // b], True),
        "=": bin2(lambda a, b: [-1 if a == b else 0]),
        "<": bin2(lambda a, b: [-1 if a < b else 0]),
        ">": bin2(lambda a, b: [-1 if a > b else 0]),
        "swap": bin2(lambda a, b: [b, a]),
        "over": bin2(lambda a, b: [a, b, a]),
        "negate": un(lambda a: [-a]),
        "abs": un(lambda a: [abs(a)]),
        "dup": un(lambda a: [a, a]),
        "drop": un(lambda a: []),
        "rot": rot,
    }
    return table[name]


def _compile(body, dictionary):
    # returns a list of nodes: ("lit", n), ("call", fn), ("if", then_nodes, else_nodes), ("loop", nodes)
    pos = 0

    def seq(stops):
        nonlocal pos
        out = []
        while pos < len(body):
            w = body[pos]
            if w in stops:
                return out, w
            pos += 1
            if _isnum(w):
                out.append(("lit", int(w)))
            elif w == "if":
                a, stop = seq(("else", "then"))
                if stop is None:
                    raise ValueError("unclosed if")
                pos += 1
                b = []
                if stop == "else":
                    b, stop = seq(("then",))
                    if stop is None:
                        raise ValueError("unclosed if")
                    pos += 1
                out.append(("if", a, b))
            elif w == "begin":
                a, stop = seq(("until",))
                if stop is None:
                    raise ValueError("unclosed begin")
                pos += 1
                out.append(("loop", a))
            elif w in _CTRL:
                raise ValueError("misplaced " + w)
            elif w in dictionary:
                out.append(("call", dictionary[w]))
            else:
                raise ValueError("unknown word " + w)
        return out, None

    nodes, stop = seq(())
    return nodes


def _run(nodes, st):
    for node in nodes:
        k = node[0]
        if k == "lit":
            st.append(node[1])
        elif k == "call":
            node[1](st)
        elif k == "if":
            _need(st, 1)
            _run(node[1] if st.pop() != 0 else node[2], st)
        else:
            while True:
                _run(node[1], st)
                _need(st, 1)
                if st.pop() != 0:
                    break


def forth(src):
    words = [w.lower() for w in src.split()]
    dictionary = {n: _builtin(n) for n in ("+", "-", "*", "/", "mod", "/mod", "=", "<", ">", "swap", "over",
                                            "negate", "abs", "dup", "drop", "rot")}
    st = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == ":":
            if i + 1 >= len(words):
                raise ValueError("missing name")
            name = words[i + 1]
            if _isnum(name):
                raise ValueError("number as name")
            j = i + 2
            body = []
            while j < len(words) and words[j] != ";":
                if words[j] == ":":
                    raise ValueError("nested definition")
                body.append(words[j])
                j += 1
            if j >= len(words):
                raise ValueError("missing ;")
            nodes = _compile(body, dictionary)
            dictionary[name] = (lambda nodes: lambda s: _run(nodes, s))(nodes)
            i = j + 1
            continue
        if w == ";" or w in _CTRL:
            raise ValueError("misplaced " + w)
        if _isnum(w):
            st.append(int(w))
        elif w in dictionary:
            dictionary[w](st)
        else:
            raise ValueError("unknown word " + w)
        i += 1
    return st
''')


task("v3_03_url_normalize", r'''
Write `normalize_url(url: str) -> str` that normalizes an absolute URL of the form
`scheme "://" authority path ["?" query] ["#" fragment]`. Rules, applied in this order:
1. Split: scheme is everything before the first ":"; it must be followed by "//", else
   ValueError. The scheme must be an ASCII letter followed by ASCII letters, digits, "+",
   "-" or "." (ValueError otherwise) and is lowercased. The authority runs from after "//" to
   the first "/", "?" or "#" (or the end). The path runs from there to the first "?" or "#";
   the query from after that "?" to the first "#"; the fragment is everything after the
   first "#". The query and fragment may contain "?"; a later "#" inside the fragment is
   percent-encoded by rule 3.
2. Authority = [userinfo "@"] host [":" port], where userinfo is everything before the LAST
   "@" (if any). The host runs to the first ":" after the userinfo. The host must be
   non-empty and use only ASCII letters, digits, "." and "-" (ValueError otherwise; this
   rejects "[" for IPv6) and is lowercased. The port, if a ":" is present, must be only ASCII
   digits (ValueError otherwise); an empty port is dropped; leading zeros are removed ("0080"
   -> "80", "000" -> "0"); a value above 65535 raises ValueError; the default port is dropped:
   http 80, https 443, ws 80, wss 443, ftp 21. An empty userinfo ("@host") is dropped.
3. Percent-encoding, in userinfo, path, query and fragment (not the host): a "%" must be
   followed by two hex digits (ValueError otherwise). Each "%XX" is uppercased ("%3a" ->
   "%3A"), and if XX is the code of an unreserved character (A-Z a-z 0-9 "-" "." "_" "~") it
   is decoded to that character ("%7E" -> "~", "%41" -> "A"). Every character that is not
   unreserved, not "%", and not one of  ! $ & ' ( ) * + , ; = : @ / ?  is percent-encoded as
   the uppercase "%XX" of each byte of its UTF-8 encoding (space -> "%20", "é" -> "%C3%A9",
   "[" -> "%5B", "#" in the fragment -> "%23").
4. Dot segments are removed from the path, after rule 3 (so "%2E" counts as "."), with the
   RFC 3986 section 5.2.4 algorithm: "." segments are dropped; ".." drops the previous
   segment (never past the root); a final "." or ".." leaves a trailing "/" ("/a/b/.." ->
   "/a/"). Empty segments are kept ("/a//b" stays). Query and fragment are not touched by
   this rule. An empty path becomes "/".
5. An empty query ("?" with nothing after it) and an empty fragment are dropped.
Output: scheme + "://" + [userinfo + "@"] + host + [":" + port] + path + ["?" + query] +
["#" + fragment].
Examples: "HTTP://User@Example.COM:0080/a/./b/../%7euser/%3f?q=%2a#F" ->
"http://User@example.com/a/~user/%3F?q=%2A#F"; "https://h:443" -> "https://h/";
"ftp://h:021?#" -> "ftp://h/". Do not use urllib.
''', r'''
_banned(mods=("urllib", "http", "email"))
import random
def bad(s):
    try:
        normalize_url(s)
    except ValueError:
        return True
    return False
fixed = {
    "HTTP://User@Example.COM:0080/a/./b/../%7euser/%3f?q=%2a#F": "http://User@example.com/a/~user/%3F?q=%2A#F",
    "https://h:443": "https://h/", "ftp://h:021?#": "ftp://h/", "http://h:": "http://h/",
    "http://h:8080": "http://h:8080/", "http://h:000": "http://h:0/", "wss://h:80/": "wss://h:80/",
    "http://@h/": "http://h/", "http://a@b@h/": "http://a@b@h/", "http://u:p@h:81/x": "http://u:p@h:81/x",
    "http://h/a/b/..": "http://h/a/", "http://h/a/b/.": "http://h/a/b/", "http://h/../../a": "http://h/a",
    "http://h/a//b/../c": "http://h/a//c", "http://h/%2e%2E/a/%2E": "http://h/a/", "http://h/.a/..b/a.": "http://h/.a/..b/a.",
    "http://h/a b?c d#e f": "http://h/a%20b?c%20d#e%20f", "http://h/é": "http://h/%C3%A9",
    "http://h/[x]{y}|^`\"<>\\": "http://h/%5Bx%5D%7By%7D%7C%5E%60%22%3C%3E%5C",
    "http://h/!$&'()*+,;=:@/?": "http://h/!$&'()*+,;=:@/", "http://h/a?!$&'()*+,;=:@/?": "http://h/a?!$&'()*+,;=:@/?", "http://h#a#b?c": "http://h/#a%23b?c",
    "http://h?a?b/./c": "http://h/?a?b/./c", "http://h/%41%62%2F%25%20": "http://h/Ab%2F%25%20",
    "HtTp+X.y-z://H": "http+x.y-z://h/", "http://h/a/./../../b/": "http://h/b/", "http://h.-x/.": "http://h.-x/",
    "http://%7e@h": "http://~@h/", "http://h?": "http://h/", "http://h/#": "http://h/", "http://h/?#x": "http://h/#x",
    "https://h:65535": "https://h:65535/", "http://h/~%7E": "http://h/~~", "http://u@h:443": "http://u@h:443/",
}
for s, v in fixed.items():
    assert normalize_url(s) == v, (s, normalize_url(s), v)
for s in ["", "http:/h", "http:h", "://h", "1http://h", "ht tp://h", "http://", "http:///a", "http://u@/a", "http://h:x",
          "http://h:65536", "http://[::1]/", "http://h_1/", "http://h:8 0", "http://h/%", "http://h/%4", "http://h/%zz",
          "http://h?%g0", "http://h#%", "http://u%@h", "http://h:-1", "http://h:80:80", "http://hé/"]:
    assert bad(s), s
random.seed(3003)
UNR = "abcxyzABCXYZ0189-._~"
SAFE = "!$&'()*+,;=:@"
ENC = ["%2F", "%3F", "%23", "%25", "%20", "%C3%A9", "%5B", "%40", "%3A"]
RAW = {"%20": " ", "%C3%A9": "é", "%5B": "["}       # canonical forms with a raw-character spelling
DEFAULT = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}
def piece(extra):
    out = []
    for _ in range(random.randint(0, 5)):
        r = random.random()
        if r < 0.6:
            out.append(random.choice(UNR))
        elif r < 0.8:
            out.append(random.choice(SAFE + extra))
        else:
            out.append(random.choice(ENC))
    return out
def noisy(tokens):
    out = []
    for t in tokens:
        if len(t) == 1 and t in UNR and random.random() < 0.2:
            h = "%02X" % ord(t)
            out.append("%" + "".join(c.lower() if random.random() < 0.5 else c for c in h))
        elif t in RAW and random.random() < 0.5:
            out.append(RAW[t])
        elif t.startswith("%") and random.random() < 0.3:
            out.append(t.lower())
        else:
            out.append(t)
    return "".join(out)
def mixcase(s):
    return "".join(c.upper() if random.random() < 0.5 else c for c in s)
for _ in range(1500):
    scheme = random.choice(["http", "https", "ws", "wss", "ftp", "git+ssh", "x-y.z"])
    host = ".".join("".join(random.choice("abz09-") for _ in range(random.randint(1, 4))) for _ in range(random.randint(1, 3)))
    user = piece("") if random.random() < 0.3 else None
    if user is not None and not user:
        user = None
    port = None
    r = random.random()
    nport = ""
    if r < 0.2:
        port = random.choice([1, 8080, 65535, 0, 443, 80, 21])
        if DEFAULT.get(scheme) == port:
            port = None
            nport = ":" + "0" * random.randint(0, 2) + str(DEFAULT[scheme])
        else:
            nport = ":" + "0" * random.randint(0, 2) + str(port)
    elif r < 0.3:
        nport = ":"
    elif r < 0.4 and scheme in DEFAULT:
        nport = ":" + str(DEFAULT[scheme])
    segs = []
    for _ in range(random.randint(0, 4)):
        while True:
            s = piece("")
            if "".join(s) not in (".", ".."):
                break
        segs.append(s)
    trailing = random.random() < 0.3
    # canonical path
    cpath = "".join("/" + "".join(s) for s in segs) + ("/" if trailing or not segs else "")
    # noisy path: dot segments sprinkled between real ones
    npieces = []
    for i, s in enumerate(segs):
        r = random.random()
        if r < 0.15:
            npieces.append(random.choice([".", "%2E", "%2e"]))
        elif r < 0.3:
            npieces.append(random.choice(["q", "x%41"]))
            npieces.append(random.choice(["..", "%2E%2E", ".%2e"]))
        elif r < 0.35 and i == 0:
            npieces.append("..")
        npieces.append(noisy(s))
    npath = "".join("/" + p for p in npieces) + ("/" if trailing else "")
    if not segs:
        npath = random.choice(["", "/", "/.", "/..", "/./", "/x/.."])
        if npath in ("/x/..",):
            pass
    query = piece("/?") if random.random() < 0.5 else None
    frag = piece("/?") if random.random() < 0.4 else None
    want = scheme + "://" + ("".join(user) + "@" if user else "") + host + (":" + str(port) if port is not None else "")
    want += cpath
    if query:
        want += "?" + "".join(query)
    if frag:
        want += "#" + "".join(frag)
    url = mixcase(scheme) + "://" + (noisy(user) + "@" if user else random.choice(["", "", "@"])) + mixcase(host) + nport + npath
    if query is not None:
        url += "?" + noisy(query)
    elif random.random() < 0.2:
        url += "?"
    if frag is not None:
        url += "#" + noisy(frag)
    elif random.random() < 0.2:
        url += "#"
    got = normalize_url(url)
    assert got == want, (url, got, want)
    assert normalize_url(got) == got, got
''', r'''
_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_KEEP = set("!$&'()*+,;=:@/?")
_HEX = set("0123456789abcdefABCDEF")
_DEFAULT = {"http": "80", "https": "443", "ws": "80", "wss": "443", "ftp": "21"}
_ALNUM = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


def _pct(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "%":
            h = s[i + 1:i + 3]
            if len(h) != 2 or not all(x in _HEX for x in h):
                raise ValueError("bad percent escape")
            ch = chr(int(h, 16))
            out.append(ch if ch in _UNRESERVED else "%" + h.upper())
            i += 3
        elif c in _UNRESERVED or c in _KEEP:
            out.append(c)
            i += 1
        else:
            out.append("".join("%%%02X" % b for b in c.encode("utf-8")))
            i += 1
    return "".join(out)


def _remove_dots(path):
    inp = path
    out = []
    while inp:
        if inp.startswith("../"):
            inp = inp[3:]
        elif inp.startswith("./"):
            inp = inp[2:]
        elif inp.startswith("/./"):
            inp = inp[2:]
        elif inp == "/.":
            inp = "/"
        elif inp.startswith("/../"):
            inp = inp[3:]
            if out:
                out.pop()
        elif inp == "/..":
            inp = "/"
            if out:
                out.pop()
        elif inp in (".", ".."):
            inp = ""
        else:
            j = inp.find("/", 1)
            if j < 0:
                j = len(inp)
            out.append(inp[:j])
            inp = inp[j:]
    return "".join(out)


def normalize_url(url):
    if ":" not in url:
        raise ValueError("no scheme")
    scheme, rest = url.split(":", 1)
    if not rest.startswith("//"):
        raise ValueError("no authority")
    if not scheme or not (scheme[0].isascii() and scheme[0].isalpha()):
        raise ValueError("bad scheme")
    for c in scheme:
        if not (c in _ALNUM or c in "+-."):
            raise ValueError("bad scheme")
    scheme = scheme.lower()
    rest = rest[2:]
    cut = len(rest)
    for d in "/?#":
        k = rest.find(d)
        if 0 <= k < cut:
            cut = k
    auth, rest = rest[:cut], rest[cut:]
    frag = None
    if "#" in rest:
        rest, frag = rest.split("#", 1)
    query = None
    if "?" in rest:
        rest, query = rest.split("?", 1)
    path = rest
    user = None
    if "@" in auth:
        user, auth = auth.rsplit("@", 1)
    port = None
    if ":" in auth:
        host, port = auth.split(":", 1)
    else:
        host = auth
    if not host or not all(c in _ALNUM or c in ".-" for c in host):
        raise ValueError("bad host")
    host = host.lower()
    if port is not None:
        if port == "":
            port = None
        else:
            if not all(c in "0123456789" for c in port):
                raise ValueError("bad port")
            port = str(int(port))
            if int(port) > 65535:
                raise ValueError("port out of range")
            if _DEFAULT.get(scheme) == port:
                port = None
    if user is not None:
        user = _pct(user)
    path = _remove_dots(_pct(path)) or "/"
    if not path.startswith("/"):
        path = "/" + path
    if query is not None:
        query = _pct(query)
    if frag is not None:
        frag = _pct(frag)
    out = scheme + "://"
    if user:
        out += user + "@"
    out += host
    if port is not None:
        out += ":" + port
    out += path
    if query:
        out += "?" + query
    if frag:
        out += "#" + frag
    return out
''')


task("v3_04_md_table", r'''
Write `parse_table(text: str) -> dict` that parses a Markdown pipe table and returns
{"header": [str, ...], "align": [str | None, ...], "rows": [[str, ...], ...]}. Rules:
- Lines are separated by "\n"; one "\r" at the end of a line is removed. Lines that are
  empty or only spaces/tabs at the start and at the end of the text are ignored; such a line
  between table lines raises ValueError.
- Splitting a line into cells: strip spaces/tabs from both ends of the line. If it now starts
  with "|", remove that one character. Then, if it ends with a "|" that is not escaped,
  remove that one character. Split the remainder at every unescaped "|". A "|" is escaped
  when it immediately follows a backslash that is not itself part of an earlier escape:
  read left to right, a backslash followed by "|" forms the escape "\|", which becomes a
  literal "|" in the cell; every other backslash is a literal backslash. So "\\|" is a
  literal backslash followed by an escaped (literal) pipe. Each cell is stripped of spaces
  and tabs. An empty remainder gives one empty cell: "|" and "||" are each one empty cell.
- Line 1 is the header. Line 2 is the delimiter row: each of its cells must match `:?-+:?`
  (one or more "-", optional ":" at either end), else ValueError. Alignment per column:
  ":-" style (colon only on the left) "left", "-:" "right", ":-:" "center", no colon None.
  The delimiter row must have the same number of cells as the header, else ValueError.
- Every further line is a body row. A row with fewer cells than the header is padded with
  "" on the right; extra cells are dropped.
- Fewer than two table lines raises ValueError.
Example: "| a | b\\|c |\n|:--|--:|\n| 1 |\nx|y|z" gives
{"header": ["a", "b|c"], "align": ["left", "right"], "rows": [["1", ""], ["x", "y"]]}.
''', r'''
import random
def bad(s):
    try:
        parse_table(s)
    except ValueError:
        return True
    return False
def T3(h, a, r):
    return {"header": h, "align": a, "rows": r}
fixed = {
    "| a | b\\|c |\n|:--|--:|\n| 1 |\nx|y|z": T3(["a", "b|c"], ["left", "right"], [["1", ""], ["x", "y"]]),
    "a\n-": T3(["a"], [None], []), "|\n|-|": T3([""], [None], []), "||\n:-:": T3([""], ["center"], []),
    " a | b \n --- | :---: \n": T3(["a", "b"], [None, "center"], []),
    "\n \na|b\r\n-|-\r\n\r\n\t\n": T3(["a", "b"], [None, None], []),
    "a|b\n-|-\n\\|x|y\\|": T3(["a", "b"], [None, None], [["|x", "y|"]]),
    "a\n-\nx\\\\|y": T3(["a"], [None], [["x\\|y"]]),
    "a|b\n-|-\nx\\ |y": T3(["a", "b"], [None, None], [["x\\", "y"]]),
    "a|b\n-|-\n|x\\\\\\|": T3(["a", "b"], [None, None], [["x\\\\|", ""]]),
    "a|b\n-|-\n| |": T3(["a", "b"], [None, None], [["", ""]]),
    "a|b\n-|-\n|||": T3(["a", "b"], [None, None], [["", ""]]),
    "a|b\n-|-\nx": T3(["a", "b"], [None, None], [["x", ""]]),
    "a|b\n-|-\n||": T3(["a", "b"], [None, None], [["", ""]]),
    "| a |\n| :-- |\n| \\ |": T3(["a"], ["left"], [["\\"]]),
    "|a|\n|-|\n|b|c|": T3(["a"], [None], [["b"]]),
    "x\\y|z\n--:|:-\n": T3(["x\\y", "z"], ["right", "left"], []),
}
for s, v in fixed.items():
    assert parse_table(s) == v, (s, parse_table(s), v)
for s in ["", "a", "\n\n", "a|b\n-", "a\n-|-", "a\nx", "a\n:", "a\n-:-", "a\n- -", "a\n--::", "a\n-\n\nb",
          "a|b\n-|-|-", "a\n|-|-|", "a\n -\n \n x", "a|b\n:-|"]:
    assert bad(s), s
random.seed(3004)
CH = "ab Z9-:\\|*`"
def cell():
    s = "".join(random.choice(CH) for _ in range(random.randint(0, 5)))
    return s.strip(" ")
def render_cell(c):
    return c.replace("|", "\\|")
def ws():
    return random.choice(["", " ", "  ", "\t"])
def render_row(cells):
    parts = [render_cell(c) for c in cells]
    lead = random.random() < 0.5 or cells[0] == "" or len(cells) == 1 and random.random() < 0.5
    trail = random.random() < 0.5 or cells[-1] == "" or parts[-1].endswith("\\")
    out = ""
    for i, p in enumerate(parts):
        if i:
            out += "|"
        pad_r = ws()
        if p.endswith("\\") and pad_r == "" and (i < len(parts) - 1 or trail):
            pad_r = " "
        out += ws() + p + pad_r
    if lead:
        out = ws() + "|" + out
    if trail:
        out = out + "|" + ws()
    if len(cells) == 1 and cells[0] == "" and not lead:
        out = "|"
    return ws() + out + ws()
for _ in range(1500):
    n = random.randint(1, 5)
    header = [cell() for _ in range(n)]
    align = [random.choice(["left", "right", "center", None]) for _ in range(n)]
    def dcell(a):
        d = "-" * random.randint(1, 4)
        return {"left": ":" + d, "right": d + ":", "center": ":" + d + ":", None: d}[a]
    rows_want = []
    rows_text = []
    for _ in range(random.randint(0, 4)):
        m = random.randint(1, n + 2)
        cells = [cell() for _ in range(m)]
        rows_text.append(render_row(cells))
        rows_want.append((cells + [""] * n)[:n])
    lines = [render_row(header), render_row([dcell(a) for a in align])] + rows_text
    nl = random.choice(["\n", "\r\n"])
    text = random.choice(["", nl, " " + nl]) + nl.join(lines) + random.choice(["", nl, nl + "\t" + nl])
    want = {"header": header, "align": align, "rows": rows_want}
    got = parse_table(text)
    assert got == want, (text, got, want)
    if rows_text:
        k = random.randint(2, len(lines) - 1)
        t2 = nl.join(lines[:k] + [random.choice(["", "  "])] + lines[k:])
        assert bad(t2), t2
''', r'''
def _cells(line):
    s = line.strip(" \t")
    if s.startswith("|"):
        s = s[1:]
    # tokenize: list of (char, escaped)
    toks = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            toks.append(("|", True))
            i += 2
        else:
            toks.append((s[i], False))
            i += 1
    if toks and toks[-1] == ("|", False):
        toks.pop()
    cells = [[]]
    for ch, esc in toks:
        if ch == "|" and not esc:
            cells.append([])
        else:
            cells[-1].append(ch)
    return ["".join(c).strip(" \t") for c in cells]


_ALIGN = {(True, False): "left", (False, True): "right", (True, True): "center", (False, False): None}


def parse_table(text):
    lines = []
    for ln in text.split("\n"):
        if ln.endswith("\r"):
            ln = ln[:-1]
        lines.append(ln)
    blank = [ln.strip(" \t") == "" for ln in lines]
    lo = 0
    while lo < len(lines) and blank[lo]:
        lo += 1
    hi = len(lines)
    while hi > lo and blank[hi - 1]:
        hi -= 1
    body = lines[lo:hi]
    if any(ln.strip(" \t") == "" for ln in body):
        raise ValueError("blank line inside table")
    if len(body) < 2:
        raise ValueError("need header and delimiter")
    header = _cells(body[0])
    delim = _cells(body[1])
    if len(delim) != len(header):
        raise ValueError("delimiter width")
    align = []
    for d in delim:
        core = d
        left = core.startswith(":")
        if left:
            core = core[1:]
        right = core.endswith(":")
        if right:
            core = core[:-1]
        if core == "" or set(core) != {"-"}:
            raise ValueError("bad delimiter cell")
        align.append(_ALIGN[(left, right)])
    n = len(header)
    rows = []
    for ln in body[2:]:
        c = _cells(ln)
        rows.append((c + [""] * n)[:n])
    return {"header": header, "align": align, "rows": rows}
''')


task("v3_05_sexpr_eval", r'''
Write `lisp_eval(src: str) -> int` that evaluates one expression of a small Lisp. Rules:
Syntax
- Tokens are "(", ")" and atoms; atoms are maximal runs of characters that are not
  whitespace or parentheses. An atom that is an optional "-" followed by one or more ASCII
  digits is an integer; every other atom is a symbol ("-" and "-a" are symbols).
- The source must hold exactly one expression: empty input, unbalanced parentheses or
  anything after the first complete expression raise ValueError.
- `let`, `let*`, `lambda` and `if` are reserved. A list whose first element is reserved
  must have this shape, else ValueError:
  (let ((name expr) ...) body)   (let* ((name expr) ...) body)   (lambda (name ...) body)
  (if test then else)
  where each `name` is a non-reserved symbol (not an integer), the binding list may be
  empty, the names of one `let` or one `lambda` must be distinct (`let*` may repeat them),
  and each binding is a list of exactly two elements. A reserved symbol anywhere else (as
  an operand, as a name, or alone) raises ValueError, and so does the empty list "()".
- The whole expression is checked for these syntax errors before anything is evaluated,
  so a syntax error raises ValueError even inside a branch that would never run.
Evaluation (lexical scope, closures)
- An integer evaluates to itself. A symbol evaluates to its innermost binding; an unbound
  symbol raises ValueError when (and only if) it is evaluated.
- (if t a b): evaluates t, which must be an integer (else ValueError); nonzero evaluates a,
  zero evaluates b. Only the chosen branch is evaluated.
- (let ((x e1) (y e2)) body): e1, e2 are evaluated left to right in the OUTER scope, then
  body with the new bindings. (let* ...) binds one at a time, each expr seeing the earlier
  bindings.
- (lambda (p ...) body) evaluates to a function that closes over the current scope.
- (f a1 a2 ...): evaluates f, then the arguments left to right; then, if f's value is not a
  function, or the argument count does not fit, ValueError; otherwise the call's result.
- Built-in functions, bound in the outermost scope (so they can be passed around and
  shadowed): `+` and `*` (any number of integer args; 0 args give 0 and 1); `-` (one arg
  negates, more subtract left to right, zero args ValueError); `//` and `%` (exactly two,
  floor semantics like Python, divisor 0 raises ZeroDivisionError); `<`, `=`, `>` (exactly
  two, result 1 or 0); `min`, `max` (one or more). A function passed where a built-in
  needs an integer raises ValueError.
- The final result must be an integer; a function result raises ValueError.
Examples: "(let ((x 2) (y 3)) (* x y))" -> 6; "(let ((x 1)) (let ((x 2) (y x)) y))" -> 1;
"(let* ((x 1) (x (+ x 1))) x)" -> 2; "((lambda (f) (f 5)) (lambda (n) (- n)))" -> -5;
"(if 0 undefined 7)" -> 7; "(if 1 2 (let x))" raises ValueError.
''', r'''
import random
def run(s):
    try:
        v = lisp_eval(s)
    except ValueError:
        return "V"
    except ZeroDivisionError:
        return "Z"
    assert type(v) is int, (s, v)
    return v
fixed = {
    "(let ((x 2) (y 3)) (* x y))": 6, "(let ((x 1)) (let ((x 2) (y x)) y))": 1, "(let* ((x 1) (x (+ x 1))) x)": 2,
    "((lambda (f) (f 5)) (lambda (n) (- n)))": -5, "(if 0 undefined 7)": 7, "(if 1 2 (let x))": "V",
    "42": 42, "-7": -7, " ( + ) ": 0, "(*)": 1, "(- 5)": -5, "(- 10 3 2)": 5, "(// -7 2)": -4, "(% -7 2)": 1,
    "(< 1 2)": 1, "(= 2 2)": 1, "(> 1 2)": 0, "(min 3 1 2)": 1, "(max 3)": 3, "(let () 5)": 5,
    "(let ((+ -)) (+ 5 3))": 2, "(let ((f (lambda (x) (lambda (y) (- x y))))) ((f 10) 3))": 7,
    "(let ((x 1)) (let ((f (lambda () x))) (let ((x 2)) (f))))": 1, "((lambda (x y) (if x y 0)) 3 4)": 4,
    "(let ((g +)) (g 1 2 3))": 6, "(-)": "V", "(// 1 0)": "Z", "(% 1 0)": "Z", "(+ 1 +)": "V", "(lambda (x) x)": "V",
    "+": "V", "(1 2)": "V", "((lambda (x) x))": "V", "((lambda (x) x) 1 2)": "V", "(if + 1 2)": "V", "(min)": "V",
    "(< 1)": "V", "(foo)": "V", "(let ((x 1) (x 2)) x)": "V", "(lambda (x x) x)": "V", "(let* ((x 1) (x 2)) x)": 2,
    "()": "V", "(if 1 2)": "V", "(if 1 2 3 4)": "V", "(let ((x)) 1)": "V", "(let ((1 2)) 1)": "V", "(let (x 1) x)": "V",
    "(let ((x 1)) x x)": "V", "(lambda x x)": "V", "(+ 1 if)": "V", "(let ((if 1)) if)": "V", "(lambda (let) 1)": "V",
    "": "V", "(": "V", ")": "V", "(+ 1 2))": "V", "1 2": "V", "(+ 1 (": "V", "(if 0 (1 2) 3)": 3, "(if 1 3 ())": "V",
    "(let ((x (// 1 0))) undefined)": "Z", "(undefined (// 1 0))": "V", "((// 1 0) undefined)": "Z",
    "(5 (// 1 0))": "Z", "(let* () (- 1))": -1, "(let ((x 1)) (let* ((y x) (x 5) (z x)) (+ y z)))": 6,
    "(lambda* (x) x)": "V", "(let ((- +)) (- 1 2))": 3, "(-a)": "V", "(let ((-a 4)) -a)": 4,
    "(let ((f (lambda (n) (* n n)))) (+ (f 3) (f 4)))": 25, "(let ((x 5)) ((lambda (x) x) 7))": 7,
    "((lambda () 3))": 3, "(if (lambda () 1) 2 3)": "V", "(if -1 2 3)": 2, "(+ (lambda () 1))": "V",
}
for s, v in fixed.items():
    assert run(s) == v, (s, run(s), v)
# oracle: compile to Python with helper functions
class Err(Exception):
    pass
class Fn:
    def __init__(self, lo, hi, f):
        self.lo, self.hi, self.f = lo, hi, f
def _app(f, *a):
    if not isinstance(f, Fn) or not (f.lo <= len(a) <= f.hi):
        raise Err()
    return f.f(*a)
def _ints(a):
    for x in a:
        if not isinstance(x, int):
            raise Err()
    return a
def _test(c):
    if not isinstance(c, int):
        raise Err()
    return c != 0
INF = 99
def _sub(*a):
    _ints(a)
    return -a[0] if len(a) == 1 else a[0] - sum(a[1:])
BUILTINS = {"+": Fn(0, INF, lambda *a: sum(_ints(a))), "*": Fn(0, INF, lambda *a: __import__("math").prod(_ints(a))),
            "-": Fn(1, INF, _sub), "//": Fn(2, 2, lambda a, b: _ints((a, b))[0] // b),
            "%": Fn(2, 2, lambda a, b: _ints((a, b))[0] % b), "<": Fn(2, 2, lambda a, b: int(_ints((a, b))[0] < b)),
            "=": Fn(2, 2, lambda a, b: int(_ints((a, b))[0] == b)), ">": Fn(2, 2, lambda a, b: int(_ints((a, b))[0] > b)),
            "min": Fn(1, INF, lambda *a: min(_ints(a))), "max": Fn(1, INF, lambda *a: max(_ints(a)))}
def mangle(s):
    return "v_" + "".join(c if c.isalnum() else "_%02x" % ord(c) for c in s)
def py(n):
    k = n[0]
    if k == "int":
        return "(%d)" % n[1]
    if k == "var":
        return mangle(n[1])
    if k == "if":
        return "((%s) if _test(%s) else (%s))" % (py(n[2]), py(n[1]), py(n[3]))
    if k == "let":
        names = ", ".join(mangle(x) for x, _ in n[1])
        return "((lambda %s: %s)(%s))" % (names, py(n[2]), ", ".join(py(e) for _, e in n[1]))
    if k == "let*":
        out = py(n[2])
        for x, e in reversed(n[1]):
            out = "((lambda %s: %s)(%s))" % (mangle(x), out, py(e))
        return out
    if k == "lambda":
        return "Fn(%d, %d, lambda %s: %s)" % (len(n[1]), len(n[1]), ", ".join(mangle(x) for x in n[1]), py(n[2]))
    if k == "app":
        return "_app(%s)" % ", ".join(py(x) for x in n[1:])
def oracle(n):
    g = {"Fn": Fn, "_app": _app, "_test": _test}
    for name, f in BUILTINS.items():
        g[mangle(name)] = f
    try:
        v = eval(py(n), g)
    except (Err, NameError):
        return "V"
    except ZeroDivisionError:
        return "Z"
    return v if isinstance(v, int) else "V"
def sp():
    return random.choice([" ", " ", "  ", "\n", "\t"])
def src(n):
    k = n[0]
    if k == "int":
        return str(n[1])
    if k == "var":
        return n[1]
    if k == "if":
        return "(if" + sp() + sp().join(src(x) for x in n[1:]) + ")"
    if k in ("let", "let*"):
        b = sp().join("(" + x + sp() + src(e) + ")" for x, e in n[1])
        return "(" + k + sp() + "(" + b + ")" + sp() + src(n[2]) + ")"
    if k == "lambda":
        return "(lambda" + sp() + "(" + " ".join(n[1]) + ")" + sp() + src(n[2]) + ")"
    return "(" + random.choice(["", " "]) + sp().join(src(x) for x in n[1:]) + ")"
random.seed(3005)
NAMES = ["x", "y", "z", "f", "g", "+", "-", "min", "n-1", "a*"]
ARITH = ["+", "-", "*", "//", "%", "<", "=", ">", "min", "max"]
def gen(d, scope, want_fn=False):
    r = random.random()
    if want_fn:
        fs = [v for v, t in scope if t == "fn"]
        if fs and r < 0.5:
            return ("var", random.choice(fs)), None
        if r < 0.7 or d <= 0:
            return ("var", random.choice(ARITH)), None
        ps = random.sample(["x", "y", "n-1", "z"], random.randint(0, 2))
        body, _ = gen(d - 1, scope + [(p, "int") for p in ps])
        return ("lambda", ps, body), len(ps)
    if d <= 0 or r < 0.2:
        if random.random() < 0.5 or not scope:
            return ("int", random.choice([0, 1, 2, 3, -1, 5, 7, random.randint(-30, 30)])), None
        if random.random() < 0.03:
            return ("var", "unbound"), None
        return ("var", random.choice([v for v, _ in scope])), None
    if r < 0.45:
        op = random.choice(ARITH)
        lo = {"//": 2, "%": 2, "<": 2, "=": 2, ">": 2, "-": 1, "min": 1, "max": 1}.get(op, 0)
        hi = 2 if op in ("//", "%", "<", "=", ">") else 3
        cnt = random.randint(lo, hi) if random.random() < 0.95 else random.randint(0, 3)
        return ("app", ("var", op)) + tuple(gen(d - 1, scope)[0] for _ in range(cnt)), None
    if r < 0.55:
        return ("if", gen(d - 1, scope)[0], gen(d - 1, scope)[0], gen(d - 1, scope)[0]), None
    if r < 0.75:
        kind = random.choice(["let", "let*"])
        binds = []
        inner = list(scope)
        used = set()
        for _ in range(random.randint(0, 3)):
            nm = random.choice(NAMES)
            if kind == "let" and nm in used:
                continue
            used.add(nm)
            if random.random() < 0.3:
                e, ar = gen(d - 1, scope if kind == "let" else inner, want_fn=True)
                t = "fn"
            else:
                e, _ = gen(d - 1, scope if kind == "let" else inner)
                t = "int"
            binds.append((nm, e))
            if kind == "let*":
                inner = [(v, tt) for v, tt in inner if v != nm] + [(nm, t)]
        if kind == "let":
            names = {nm for nm, _ in binds}
            inner = [(v, t) for v, t in scope if v not in names] + [(nm, "fn" if b[0] in ("lambda",) or (b[0] == "var" and b[1] in ARITH) else "int") for nm, b in binds]
        body, _ = gen(d - 1, inner)
        return (kind, binds, body), None
    # application of a function value
    f, ar = gen(d - 1, scope, want_fn=True)
    if ar is None:
        ar = random.randint(1, 3) if not (f[0] == "var" and f[1] in ("//", "%", "<", "=", ">")) else 2
    if random.random() < 0.05:
        ar += 1
    return ("app", f) + tuple(gen(d - 1, scope)[0] for _ in range(ar)), None
for _ in range(2500):
    tree, _ = gen(random.randint(1, 5), [])
    s = src(tree)
    exp = oracle(tree)
    got = run(s)
    assert got == exp, (s, got, exp)
''', r'''
_RESERVED = ("let", "let*", "lambda", "if")


def _tokens(s):
    out = []
    cur = []
    for c in s:
        if c in "()" or c.isspace():
            if cur:
                out.append("".join(cur))
                cur = []
            if c in "()":
                out.append(c)
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur))
    return out


def _is_int(a):
    d = a[1:] if a.startswith("-") else a
    return d != "" and all(c in "0123456789" for c in d)


def _parse(toks):
    pos = 0

    def expr():
        nonlocal pos
        if pos >= len(toks):
            raise ValueError("unexpected end")
        t = toks[pos]
        pos += 1
        if t == ")":
            raise ValueError("unexpected )")
        if t != "(":
            return int(t) if _is_int(t) else t
        items = []
        while True:
            if pos >= len(toks):
                raise ValueError("unclosed (")
            if toks[pos] == ")":
                pos += 1
                return items
            items.append(expr())

    e = expr()
    if pos != len(toks):
        raise ValueError("trailing input")
    return e


def _name_ok(x):
    return isinstance(x, str) and x not in _RESERVED


def _check(e):
    if isinstance(e, int):
        return
    if isinstance(e, str):
        if e in _RESERVED:
            raise ValueError("reserved word used as a value")
        return
    if not e:
        raise ValueError("empty list")
    head = e[0]
    if head in ("let", "let*"):
        if len(e) != 3 or not isinstance(e[1], list):
            raise ValueError("bad let")
        names = []
        for b in e[1]:
            if not isinstance(b, list) or len(b) != 2 or not _name_ok(b[0]):
                raise ValueError("bad binding")
            names.append(b[0])
            _check(b[1])
        if head == "let" and len(set(names)) != len(names):
            raise ValueError("duplicate name")
        _check(e[2])
    elif head == "lambda":
        if len(e) != 3 or not isinstance(e[1], list) or not all(_name_ok(p) for p in e[1]):
            raise ValueError("bad lambda")
        if len(set(e[1])) != len(e[1]):
            raise ValueError("duplicate parameter")
        _check(e[2])
    elif head == "if":
        if len(e) != 4:
            raise ValueError("bad if")
        for x in e[1:]:
            _check(x)
    else:
        for x in e:
            _check(x)


class _Closure:
    def __init__(self, params, body, env):
        self.params, self.body, self.env = params, body, env


class _Builtin:
    def __init__(self, lo, hi, f):
        self.lo, self.hi, self.f = lo, hi, f


def _ints(args):
    for a in args:
        if not isinstance(a, int):
            raise ValueError("integer expected")
    return args


def _minus(*a):
    return -a[0] if len(a) == 1 else a[0] - sum(a[1:])


def _prod(*a):
    r = 1
    for x in a:
        r *= x
    return r


_INF = float("inf")
_GLOBAL = {
    "+": _Builtin(0, _INF, lambda *a: sum(a)),
    "*": _Builtin(0, _INF, _prod),
    "-": _Builtin(1, _INF, _minus),
    "//": _Builtin(2, 2, lambda a, b: a // b),
    "%": _Builtin(2, 2, lambda a, b: a % b),
    "<": _Builtin(2, 2, lambda a, b: 1 if a < b else 0),
    "=": _Builtin(2, 2, lambda a, b: 1 if a == b else 0),
    ">": _Builtin(2, 2, lambda a, b: 1 if a > b else 0),
    "min": _Builtin(1, _INF, lambda *a: min(a)),
    "max": _Builtin(1, _INF, lambda *a: max(a)),
}


def _lookup(env, name):
    while env is not None:
        frame, env = env
        if name in frame:
            return frame[name]
    if name in _GLOBAL:
        return _GLOBAL[name]
    raise ValueError("unbound symbol " + name)


def _eval(e, env):
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        return _lookup(env, e)
    head = e[0]
    if head == "if":
        t = _eval(e[1], env)
        if not isinstance(t, int):
            raise ValueError("if test must be an integer")
        return _eval(e[2] if t != 0 else e[3], env)
    if head == "let":
        frame = {}
        for name, x in e[1]:
            frame[name] = _eval(x, env)
        return _eval(e[2], (frame, env))
    if head == "let*":
        for name, x in e[1]:
            env = ({name: _eval(x, env)}, env)
        return _eval(e[2], env)
    if head == "lambda":
        return _Closure(e[1], e[2], env)
    f = _eval(head, env)
    args = [_eval(x, env) for x in e[1:]]
    if isinstance(f, _Builtin):
        if not (f.lo <= len(args) <= f.hi):
            raise ValueError("arity")
        return f.f(*_ints(args))
    if isinstance(f, _Closure):
        if len(args) != len(f.params):
            raise ValueError("arity")
        return _eval(f.body, (dict(zip(f.params, args)), f.env))
    raise ValueError("not a function")


def lisp_eval(src):
    e = _parse(_tokens(src))
    _check(e)
    v = _eval(e, None)
    if not isinstance(v, int):
        raise ValueError("result is not an integer")
    return v
''')


task("v3_06_mustache", r'''
Write `render(template: str, ctx: dict) -> str`, a Mustache-like template engine. Rules:
- Text outside tags is copied unchanged (a lone "{", "}" or "}}" is ordinary text).
- A tag starts at "{{". If the next character is "{", it is a triple tag that ends at the
  next "}}}"; otherwise it ends at the next "}}". No end -> ValueError. For "{{" tags, the
  first character after "{{" selects the kind: "#" section, "^" inverted section, "/" close,
  "&" unescaped variable, "!" comment (its content is ignored entirely); anything else
  starts an escaped variable (the whole content is the name). The name is the rest of the
  content stripped of spaces; for a triple tag it is the content between "{{{" and "}}}",
  stripped.
- A name is either "." or one or more parts joined by single "."; each part is a non-empty
  run of A-Z a-z 0-9 "_". Anything else (empty, "a..b", ".a", "a b") raises ValueError.
- Lookup uses a context stack that starts as [ctx]. "." is the top of the stack. For a
  dotted name, the first part is looked up from the top of the stack down: the first frame
  that is a dict containing that key gives the value (frames that are not dicts are
  skipped); if none, the name is missing. Each further part descends into a dict that
  contains it; if the current value is not such a dict, the name is missing.
- Variables: "{{name}}" writes the value HTML-escaped (& < > " ' become &amp; &lt; &gt;
  &quot; &#39;); "{{{name}}}" and "{{&name}}" write it unescaped. Value -> text: str as is;
  bool "true"/"false"; int str(); None or missing "". A list or dict raises ValueError.
- "{{#name}}...{{/name}}": if the value is falsy (missing, None, False, 0, "", [], {}) the
  block is skipped. A list renders the block once per item with the item pushed on the
  stack; any other truthy value renders it once with the value pushed.
- "{{^name}}...{{/name}}": renders the block once, pushing nothing, iff the value is falsy.
- A close tag must name the innermost open section exactly (same text after stripping),
  else ValueError; a close with no open section, or a section left open at the end, raises
  ValueError. The whole template is checked for syntax errors before rendering (a bad tag
  inside a skipped section still raises ValueError).
- No other Mustache features (no partials, no delimiter changes, no standalone-line
  whitespace removal).
Example: render("{{#items}}<{{name}}:{{{name}}}>{{/items}}{{^none}}!{{/none}}",
{"items": [{"name": "a&b"}, {"name": 1}]}) == "<a&amp;b:a&b><1:1>!".
''', r'''
import random
def run(t, c):
    try:
        return render(t, c)
    except ValueError:
        return "V"
fixed = [
    ("{{#items}}<{{name}}:{{{name}}}>{{/items}}{{^none}}!{{/none}}", {"items": [{"name": "a&b"}, {"name": 1}]}, "<a&amp;b:a&b><1:1>!"),
    ("", {}, ""), ("plain } }} { text", {}, "plain } }} { text"), ("{{a}}", {"a": "<\"'&>"}, "&lt;&quot;&#39;&amp;&gt;"),
    ("{{&a}}{{{ a }}}", {"a": "<"}, "<<"), ("{{ b }}|{{a.b}}|{{x}}", {"a": {"b": 2}, "b": True}, "true|2|"), ("{{a}}{{b}}{{c}}", {"a": None, "b": False, "c": 0}, "false0"),
    ("{{a}}", {"a": [1]}, "V"), ("{{a}}", {"a": {}}, "V"), ("{{#a}}{{.}}{{/a}}", {"a": [1, "<", True]}, "1&lt;true"),
    ("{{#a}}x{{/a}}", {"a": 0}, ""), ("{{#a}}x{{/a}}", {"a": ""}, ""), ("{{#a}}x{{/a}}", {"a": {}}, ""),
    ("{{#a}}{{.}}{{/a}}", {"a": 5}, "5"), ("{{#a}}{{b}}{{/a}}", {"a": {"c": 1}, "b": "outer"}, "outer"),
    ("{{#a}}{{b.c}}{{/a}}", {"a": {"b": 1}, "b": {"c": "x"}}, ""), ("{{#a}}{{#b}}{{c}}{{/b}}{{/a}}", {"a": {"b": [1, {"c": 2}]}, "c": 3}, "32"),
    ("{{^a}}no{{/a}}{{^b}}no{{/b}}", {"a": [], "b": [0]}, "no"), ("{{!a}}b{{! }} {{!}}}", {}, "b }"),
    ("{{a}}}", {"a": 1}, "1}"), ("{{{a}}}}", {"a": "<"}, "<}"), ("x{{#a}}{{/a}}y", {}, "xy"),
    ("{{#a.b}}{{.}}{{/a.b}}", {"a": {"b": ["p", "q"]}}, "pq"), ("{{#a}}{{a}}{{/a}}", {"a": "s"}, "s"),
    ("{{#a}}{{.}}{{/a}}", {"a": [[1, 2]]}, "V"), ("{{#a}}{{#.}}{{.}}{{/.}}{{/a}}", {"a": [[1, 2], [3]]}, "123"),
    ("{{#a}}x{{/b}}", {}, "V"), ("{{#a}}x", {}, "V"), ("x{{/a}}", {}, "V"), ("{{a", {}, "V"), ("{{{a}}", {}, "V"),
    ("{{}}", {}, "V"), ("{{ }}", {}, "V"), ("{{a..b}}", {}, "V"), ("{{.a}}", {}, "V"), ("{{a.}}", {}, "V"),
    ("{{a b}}", {}, "V"), ("{{ #a}}{{/a}}", {}, "V"), ("{{#a}}{{/ a }}", {}, ""), ("{{#a}}{{bad name}}{{/a}}", {}, "V"),
    ("{{#a}}{{#b}}{{/a}}{{/b}}", {}, "V"), ("{{#a.b}}{{/a}}", {}, "V"), ("{{#}}{{/}}", {}, "V"), ("{{&}}", {}, "V"),
    ("{{a-b}}", {}, "V"), ("{{^a}}{{x}}{{/a}}", {"a": 1, "x": []}, ""), ("{{^a}}{{.}}{{/a}}", {"a": 0}, "V"),
]
for t, c, v in fixed:
    assert run(t, c) == v, (t, c, run(t, c), v)
class Missing:
    pass
MISSING = Missing()
def look(stack, name):
    if name == ".":
        return stack[-1]
    parts = name.split(".")
    for fr in reversed(stack):
        if isinstance(fr, dict) and parts[0] in fr:
            v = fr[parts[0]]
            break
    else:
        return MISSING
    for p in parts[1:]:
        if isinstance(v, dict) and p in v:
            v = v[p]
        else:
            return MISSING
    return v
class Bad(Exception):
    pass
def text_of(v):
    if v is MISSING or v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        raise Bad()
    return str(v)
def esc(s):
    return "".join({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}.get(c, c) for c in s)
def falsy(v):
    return v is MISSING or not v
def rend(nodes, stack):
    out = []
    for n in nodes:
        k = n[0]
        if k == "text":
            out.append(n[1])
        elif k == "var":
            s = text_of(look(stack, n[1]))
            out.append(esc(s) if n[2] else s)
        elif k == "sec":
            v = look(stack, n[1])
            if n[2]:
                if falsy(v):
                    out.append(rend(n[3], stack))
            elif not falsy(v):
                for item in (v if isinstance(v, list) else [v]):
                    out.append(rend(n[3], stack + [item]))
    return "".join(out)
def ws():
    return random.choice(["", "", " ", "  "])
def ser(nodes):
    out = []
    for n in nodes:
        k = n[0]
        if k == "text":
            out.append(n[1])
        elif k == "comment":
            out.append("{{!" + n[1] + "}}")
        elif k == "var":
            if n[2]:
                out.append("{{" + ws() + n[1] + ws() + "}}")
            elif random.random() < 0.5:
                out.append("{{{" + ws() + n[1] + ws() + "}}}")
            else:
                out.append("{{&" + ws() + n[1] + ws() + "}}")
        else:
            out.append("{{" + ("^" if n[2] else "#") + ws() + n[1] + ws() + "}}" + ser(n[3]) + "{{/" + ws() + n[1] + ws() + "}}")
    return "".join(out)
random.seed(3006)
KEYS = ["a", "b", "c", "d"]
NAMES = ["a", "b", "c", "d", ".", "a.b", "b.c", "a.b.c", "c.a"]
TXT = "xy <>&\"'}{ "
def text():
    while True:
        s = "".join(random.choice(TXT) for _ in range(random.randint(1, 4)))
        if "{{" not in s and not s.endswith("{"):
            return s
def scalar():
    return random.choice(["s", "<b>", "x&y", "'q'", "", 0, 1, 42, True, False, None])
def value(d):
    r = random.random()
    if d <= 0 or r < 0.45:
        return scalar()
    if r < 0.75:
        return {k: value(d - 1) for k in random.sample(KEYS, random.randint(0, 3))}
    return [value(d - 1) for _ in range(random.randint(0, 3))]
def tmpl(d):
    nodes = []
    for _ in range(random.randint(0, 4)):
        r = random.random()
        if r < 0.3:
            nodes.append(("text", text()))
        elif r < 0.6 or d <= 0:
            nodes.append(("var", random.choice(NAMES), random.random() < 0.6))
        elif r < 0.65:
            nodes.append(("comment", "".join(random.choice("ab {#/") for _ in range(random.randint(0, 4)))))
        else:
            nodes.append(("sec", random.choice(NAMES), random.random() < 0.3, tmpl(d - 1)))
    # adjacent text nodes are fine; a text ending in "{" never precedes a tag (text() forbids it)
    return nodes
for _ in range(2000):
    nodes = tmpl(3)
    ctx = {k: value(3) for k in random.sample(KEYS, random.randint(0, 4))}
    t = ser(nodes)
    try:
        exp = rend(nodes, [ctx])
    except Bad:
        exp = "V"
    got = run(t, ctx)
    assert got == exp, (t, ctx, got, exp)
    # a syntax error anywhere, even inside a section that is skipped, must raise ValueError
    holder = nodes
    while True:
        secs = [n for n in holder if n[0] == "sec"]
        if not secs or random.random() < 0.4:
            break
        holder = random.choice(secs)[3]
    holder.insert(random.randint(0, len(holder)), ("text", random.choice(["{{a b}}", "{{/zz}}", "{{#zz}}", "{{a..b}}", "{{.a}}"])))
    t2 = ser(nodes)
    assert run(t2, ctx) == "V", t2
''', r'''
def _valid_name(n):
    if n == ".":
        return True
    parts = n.split(".")
    for p in parts:
        if not p or not all(c.isascii() and (c.isalnum() or c == "_") for c in p):
            return False
    return True


def _parse(t):
    root = []
    stack = [("", root)]
    i = 0
    n = len(t)
    while i < n:
        j = t.find("{{", i)
        if j < 0:
            stack[-1][1].append(("text", t[i:]))
            break
        if j > i:
            stack[-1][1].append(("text", t[i:j]))
        if t.startswith("{{{", j):
            k = t.find("}}}", j + 3)
            if k < 0:
                raise ValueError("unterminated triple tag")
            name = t[j + 3:k].strip(" ")
            if not _valid_name(name):
                raise ValueError("bad name")
            stack[-1][1].append(("var", name, False))
            i = k + 3
            continue
        k = t.find("}}", j + 2)
        if k < 0:
            raise ValueError("unterminated tag")
        content = t[j + 2:k]
        i = k + 2
        sig = content[:1]
        if sig == "!":
            continue
        if sig in ("#", "^", "/", "&"):
            name = content[1:].strip(" ")
        else:
            name = content.strip(" ")
        if not _valid_name(name):
            raise ValueError("bad name")
        if sig in ("#", "^"):
            node = ("sec", name, sig == "^", [])
            stack[-1][1].append(node)
            stack.append((name, node[3]))
        elif sig == "/":
            if len(stack) == 1 or stack[-1][0] != name:
                raise ValueError("mismatched close")
            stack.pop()
        else:
            stack[-1][1].append(("var", name, sig != "&"))
    if len(stack) != 1:
        raise ValueError("unclosed section")
    return root


_MISSING = object()


def _lookup(stack, name):
    if name == ".":
        return stack[-1]
    parts = name.split(".")
    val = _MISSING
    for frame in reversed(stack):
        if isinstance(frame, dict) and parts[0] in frame:
            val = frame[parts[0]]
            break
    if val is _MISSING:
        return _MISSING
    for p in parts[1:]:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            return _MISSING
    return val


_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def _text(v):
    if v is _MISSING or v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (list, dict)):
        raise ValueError("cannot render a list or dict")
    return str(v)


def _falsy(v):
    return v is _MISSING or not v


def _render(nodes, stack, out):
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(node[1])
        elif kind == "var":
            s = _text(_lookup(stack, node[1]))
            out.append("".join(_ESC.get(c, c) for c in s) if node[2] else s)
        else:
            v = _lookup(stack, node[1])
            if node[2]:
                if _falsy(v):
                    _render(node[3], stack, out)
            elif not _falsy(v):
                for item in (v if isinstance(v, list) else [v]):
                    stack.append(item)
                    _render(node[3], stack, out)
                    stack.pop()


def render(template, ctx):
    tree = _parse(template)
    out = []
    _render(tree, [ctx], out)
    return "".join(out)
''')


task("v3_07_proto_wire", r'''
Write `decode_fields(data: bytes) -> list` that decodes the Protocol Buffers wire format
into a list of (field_number, wire_type, value) tuples, in order. Rules:
- A varint is read byte by byte; byte i contributes (b & 0x7F) << (7 * i), and reading
  continues while b & 0x80 is set. At most 10 bytes: if the 10th byte still has 0x80 set, or
  the value is 2**64 or more, raise ValueError. Non-minimal encodings (e.g. b"\x80\x00" for
  0) are accepted. Running out of data inside a varint raises ValueError.
- A record is a key varint followed by a payload. The key must be below 2**32 (else
  ValueError); field_number = key >> 3 must be at least 1 (else ValueError); wire_type =
  key & 7.
- wire type 0: the value is a varint (an int). 1: the value is the next 8 bytes as an
  unsigned little-endian int. 5: the next 4 bytes, the same way. 2: a varint length L, then
  the value is the next L bytes (a bytes object). Not enough bytes left raises ValueError.
- wire type 3 starts a group: the records that follow, up to the matching wire type 4
  record, form the value as a list of tuples (groups nest). The wire type 4 record has no
  payload, is not included in the output, and must have the same field number as the
  group it closes, else ValueError. A wire type 4 record with no open group, or data that
  ends while a group is open, raises ValueError.
- Wire types 6 and 7 raise ValueError.
Examples: decode_fields(b"\x08\x96\x01") == [(1, 0, 150)];
decode_fields(b"\x12\x03abc\x1b\x08\x01\x1c") == [(2, 2, b"abc"), (3, 3, [(1, 0, 1)])];
decode_fields(b"\x0d\x01\x00\x00\x80") == [(1, 5, 2147483649)].
''', r'''
import random
def run(b):
    try:
        return decode_fields(b)
    except ValueError:
        return "V"
fixed = {
    b"": [], b"\x08\x96\x01": [(1, 0, 150)], b"\x12\x03abc\x1b\x08\x01\x1c": [(2, 2, b"abc"), (3, 3, [(1, 0, 1)])],
    b"\x0d\x01\x00\x00\x80": [(1, 5, 2147483649)], b"\x09" + bytes(range(1, 9)): [(1, 1, 0x0807060504030201)],
    b"\x08\x80\x00": [(1, 0, 0)], b"\x88\x80\x80\x80\x00\x05": [(1, 0, 5)], b"\x12\x00": [(2, 2, b"")],
    b"\x08" + b"\xff" * 9 + b"\x01": [(1, 0, 2 ** 64 - 1)], b"\x0b\x0c": [(1, 3, [])],
    b"\x0b\x13\x14\x0c": [(1, 3, [(2, 3, [])])], b"\xf8\xff\xff\xff\x0f\x00": [(2 ** 29 - 1, 0, 0)],
    b"\x0b\x12\x01\x0c\x0c": [(1, 3, [(2, 2, b"\x0c")])],
}
for b, v in fixed.items():
    assert run(b) == v, (b, run(b), v)
for b in [b"\x08", b"\x08\x80", b"\x08" + b"\xff" * 10 + b"\x01", b"\x08" + b"\xff" * 9 + b"\x02", b"\x08" + b"\x80" * 10 + b"\x00",
          b"\x00\x00", b"\x07\x00", b"\x80\x80\x80\x80\x10\x00", b"\x0e", b"\x0f", b"\x09\x00", b"\x0d\x00\x00\x00",
          b"\x12\x05ab", b"\x12", b"\x0b", b"\x0c", b"\x0b\x14", b"\x0b\x13\x0c\x14", b"\x0b\x08\x01", b"\x12\x80"]:
    assert run(b) == "V", b
# oracle: iterative decoder with an explicit stack
def oracle(b):
    pos = 0
    def varint():
        nonlocal pos
        v = 0
        for i in range(10):
            if pos >= len(b):
                return None
            c = b[pos]; pos += 1
            v |= (c & 127) << (7 * i)
            if not c & 128:
                return v if v < 2 ** 64 else None
        return None
    stack = [(None, [])]
    while pos < len(b):
        key = varint()
        if key is None or key >= 2 ** 32 or key >> 3 == 0:
            return "V"
        f, w = key >> 3, key & 7
        if w == 0:
            v = varint()
            if v is None:
                return "V"
            stack[-1][1].append((f, 0, v))
        elif w in (1, 5):
            n = 8 if w == 1 else 4
            if pos + n > len(b):
                return "V"
            stack[-1][1].append((f, w, sum(b[pos + i] << (8 * i) for i in range(n))))
            pos += n
        elif w == 2:
            n = varint()
            if n is None or pos + n > len(b):
                return "V"
            stack[-1][1].append((f, 2, bytes(b[pos:pos + n])))
            pos += n
        elif w == 3:
            stack.append((f, []))
        elif w == 4:
            if len(stack) == 1 or stack[-1][0] != f:
                return "V"
            g, items = stack.pop()
            stack[-1][1].append((g, 3, items))
        else:
            return "V"
    return stack[0][1] if len(stack) == 1 else "V"
def enc_varint(v, pad):
    out = []
    while True:
        c = v & 127
        v >>= 7
        if v or pad > 0:
            out.append(c | 128)
            if not v:
                pad -= 1
        else:
            out.append(c)
            return bytes(out)
def ev(v):
    n = (max(v.bit_length(), 1) + 6) // 7
    return enc_varint(v, random.choice([0, 0, 0, random.randint(0, 10 - n)]))
def encode(recs):
    out = b""
    for f, w, v in recs:
        out += ev((f << 3) | w)
        if w == 0:
            out += ev(v)
        elif w == 1:
            out += v.to_bytes(8, "little")
        elif w == 5:
            out += v.to_bytes(4, "little")
        elif w == 2:
            out += ev(len(v)) + v
        else:
            out += encode(v) + ev((f << 3) | 4)
    return out
random.seed(3007)
def field():
    return random.choice([1, 2, 3, 15, 16, 2047, 2048, random.randint(1, 2 ** 29 - 1)])
def recs(d):
    out = []
    for _ in range(random.randint(0, 4)):
        w = random.choice([0, 0, 1, 2, 2, 5, 3])
        f = field()
        if w == 0:
            v = random.choice([0, 1, 127, 128, 300, 2 ** 63, 2 ** 64 - 1, random.getrandbits(random.randint(1, 64))])
        elif w == 1:
            v = random.getrandbits(64)
        elif w == 5:
            v = random.getrandbits(32)
        elif w == 2:
            v = bytes(random.getrandbits(8) for _ in range(random.choice([0, 1, 3, 130])))
        else:
            if d <= 0:
                continue
            v = recs(d - 1)
        out.append((f, w, v))
    return out
for _ in range(2000):
    r = recs(3)
    b = encode(r)
    assert oracle(b) == r
    got = run(b)
    assert got == r, (b, got, r)
    m = bytearray(b)
    k = random.random()
    if k < 0.3 and m:
        del m[random.randrange(len(m)):]
    elif k < 0.6 and m:
        m[random.randrange(len(m))] = random.getrandbits(8)
    elif k < 0.8:
        m.insert(random.randint(0, len(m)), random.choice([0x0C, 0x14, 0x80, 0x0B, 0x07, 0xFF]))
    else:
        m += bytes([random.choice([0x0C, 0x0E, 0x08, 0x12, 0x80])])
    m = bytes(m)
    assert run(m) == oracle(m), (m, run(m), oracle(m))
''', r'''
def _varint(data, pos):
    value = 0
    for i in range(10):
        if pos >= len(data):
            raise ValueError("truncated varint")
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << (7 * i)
        if not b & 0x80:
            if value >= 1 << 64:
                raise ValueError("varint too large")
            return value, pos
    raise ValueError("varint longer than 10 bytes")


def _records(data, pos, group):
    out = []
    while pos < len(data):
        key, pos = _varint(data, pos)
        if key >= 1 << 32:
            raise ValueError("key too large")
        field, wire = key >> 3, key & 7
        if field == 0:
            raise ValueError("field number 0")
        if wire == 0:
            v, pos = _varint(data, pos)
        elif wire in (1, 5):
            n = 8 if wire == 1 else 4
            if pos + n > len(data):
                raise ValueError("truncated fixed field")
            v = int.from_bytes(data[pos:pos + n], "little")
            pos += n
        elif wire == 2:
            n, pos = _varint(data, pos)
            if pos + n > len(data):
                raise ValueError("truncated bytes field")
            v = bytes(data[pos:pos + n])
            pos += n
        elif wire == 3:
            v, pos = _records(data, pos, field)
        elif wire == 4:
            if group is None or group != field:
                raise ValueError("unmatched end group")
            return out, pos
        else:
            raise ValueError("bad wire type")
        out.append((field, wire, v))
    if group is not None:
        raise ValueError("unterminated group")
    return out, pos


def decode_fields(data):
    out, _ = _records(bytes(data), 0, None)
    return out
''')


task("v3_08_strftime", r'''
Write `strftime(fmt: str, dt: tuple) -> str` where dt = (year, month, day, hour, minute,
second), formatting like C's strftime in the "C" locale, proleptic Gregorian calendar.
Rules:
- dt must be a valid date and time: 1 <= year <= 9999, 1 <= month <= 12, day within the
  month (leap years: divisible by 4, except centuries not divisible by 400), 0 <= hour <=
  23, 0 <= minute <= 59, 0 <= second <= 59; otherwise raise ValueError (even if fmt has no
  directives).
- Characters other than "%" are copied. "%" followed by one of these characters is replaced:
  %Y year, 4 digits zero-padded ("0042"); %y year % 100, 2 digits; %m month, 2 digits; %d day,
  2 digits; %e day, space-padded to width 2 (" 5"); %H hour 00-23; %I hour on a 12-hour clock
  01-12 (0 -> 12, 13 -> 01); %p "AM" for hours 0-11, "PM" for 12-23; %M minute; %S second;
  %j day of the year, 3 digits (001-366); %a %A weekday name ("Mon"/"Monday" ...); %b %B
  month name ("Jan"/"January" ...); %w weekday as a digit, 0 = Sunday .. 6 = Saturday; %u
  weekday as a digit, 1 = Monday .. 7 = Sunday; %U week of the year, 2 digits, where weeks
  start on Sunday and days before the year's first Sunday are week 00; %W the same with
  weeks starting on Monday; %% a literal "%".
- "%" followed by any other character, or a "%" at the end of fmt, raises ValueError.
Examples: strftime("%Y-%m-%d %H:%M:%S", (2024, 2, 29, 13, 5, 9)) == "2024-02-29 13:05:09";
strftime("%a %e %b %I%p %j %U %W %w %u", (2023, 1, 1, 0, 0, 0)) ==
"Sun  1 Jan 12AM 001 01 00 0 7". Do not use the datetime, time or calendar modules.
''', r'''
_banned(mods=("datetime", "_datetime", "_pydatetime", "time", "calendar", "_strptime", "locale", "zoneinfo", "email", "subprocess", "os", "ctypes"))
import random, datetime
def bad(f, dt):
    try:
        strftime(f, dt)
    except ValueError:
        return True
    return False
assert strftime("%Y-%m-%d %H:%M:%S", (2024, 2, 29, 13, 5, 9)) == "2024-02-29 13:05:09"
assert strftime("%a %e %b %I%p %j %U %W %w %u", (2023, 1, 1, 0, 0, 0)) == "Sun  1 Jan 12AM 001 01 00 0 7"
assert strftime("", (1, 1, 1, 0, 0, 0)) == ""
assert strftime("%Y|%y|%%|%A|%B", (42, 12, 31, 23, 59, 59)) == "0042|42|%|Wednesday|December"
assert strftime("%Y %j %U %W", (2000, 12, 31, 12, 0, 0)) == "2000 366 53 52"
assert strftime("%I %p %I %p", (2001, 1, 1, 12, 0, 0)) == "12 PM 12 PM"
assert strftime("%I%p", (2001, 1, 1, 13, 0, 0)) == "01PM"
assert strftime("%%Y %%%d", (1999, 1, 9, 0, 0, 0)) == "%Y %09"
assert strftime("a%%", (1999, 1, 9, 0, 0, 0)) == "a%"
assert strftime("%Y-%m-%d %a", (1900, 3, 1, 0, 0, 0)) == "1900-03-01 Thu"
assert strftime("%Y %a", (1, 1, 1, 0, 0, 0)) == "0001 Mon"
assert strftime("%e|%d", (2020, 7, 10, 0, 0, 0)) == "10|10"
for f, dt in [("%", (2000, 1, 1, 0, 0, 0)), ("%q", (2000, 1, 1, 0, 0, 0)), ("x%", (2000, 1, 1, 0, 0, 0)), ("%G", (2000, 1, 1, 0, 0, 0)),
              ("%E", (2000, 1, 1, 0, 0, 0)), ("%-d", (2000, 1, 1, 0, 0, 0)), ("% d", (2000, 1, 1, 0, 0, 0)),
              ("", (1900, 2, 29, 0, 0, 0)), ("", (2000, 2, 30, 0, 0, 0)), ("", (2023, 4, 31, 0, 0, 0)), ("", (0, 1, 1, 0, 0, 0)),
              ("", (10000, 1, 1, 0, 0, 0)), ("", (2000, 13, 1, 0, 0, 0)), ("", (2000, 0, 1, 0, 0, 0)), ("", (2000, 1, 0, 0, 0, 0)),
              ("", (2000, 1, 1, 24, 0, 0)), ("", (2000, 1, 1, 0, 60, 0)), ("", (2000, 1, 1, 0, 0, 60)), ("", (2000, 1, 1, -1, 0, 0))]:
    assert bad(f, dt), (f, dt)
assert strftime("", (2000, 2, 29, 0, 0, 0)) == ""
DIRS = "YymdeHIpMSjaAbBUWwu%"
def oracle(fmt, dt):
    d = datetime.datetime(*dt)
    out = []
    i = 0
    while i < len(fmt):
        if fmt[i] != "%":
            out.append(fmt[i]); i += 1; continue
        c = fmt[i + 1]
        out.append("%04d" % dt[0] if c == "Y" else d.strftime("%" + c))
        i += 2
    return "".join(out)
random.seed(3008)
for _ in range(4000):
    y = random.choice([1, 4, 100, 400, 1600, 1700, 1900, 1999, 2000, 2004, 2100, 9999, random.randint(1, 9999)])
    m = random.randint(1, 12)
    dmax = [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    d = random.choice([1, 2, 7, dmax, random.randint(1, dmax)])
    dt = (y, m, d, random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    fmt = "".join(random.choice(["%" + random.choice(DIRS), "%" + random.choice(DIRS), "-", " ", "x", "%%"]) for _ in range(random.randint(0, 8)))
    got = strftime(fmt, dt)
    exp = oracle(fmt, dt)
    assert got == exp, (fmt, dt, got, exp)
    if random.random() < 0.2:
        bd = list(dt)
        k = random.randrange(6)
        bd[k] = [random.choice([0, 10000]), random.choice([0, 13]), dmax + 1, 24, 60, 60][k]
        assert bad(fmt, tuple(bd)), bd
    if random.random() < 0.2:
        assert bad(fmt + random.choice(["%", "%x", "%z", "%Z", "%c", "%"]), dt)
''', r'''
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _mdays(y, m):
    return [31, 29 if _leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def _ordinal(y, m, d):
    # days since 0001-01-01 (which is day 0, a Monday)
    yy = y - 1
    n = yy * 365 + yy // 4 - yy // 100 + yy // 400
    for mm in range(1, m):
        n += _mdays(y, mm)
    return n + d - 1


def strftime(fmt, dt):
    y, mo, d, h, mi, s = dt
    if not (1 <= y <= 9999 and 1 <= mo <= 12 and 1 <= d <= _mdays(y, mo)
            and 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= s <= 59):
        raise ValueError("invalid date or time")
    wd = _ordinal(y, mo, d) % 7          # 0 = Monday
    yday = _ordinal(y, mo, d) - _ordinal(y, 1, 1)   # 0-based
    sun_wd = (wd + 1) % 7               # 0 = Sunday
    h12 = h % 12 or 12
    vals = {
        "Y": "%04d" % y, "y": "%02d" % (y % 100), "m": "%02d" % mo, "d": "%02d" % d, "e": "%2d" % d,
        "H": "%02d" % h, "I": "%02d" % h12, "p": "AM" if h < 12 else "PM", "M": "%02d" % mi, "S": "%02d" % s,
        "j": "%03d" % (yday + 1), "a": _DAYS[wd][:3], "A": _DAYS[wd], "b": _MONTHS[mo - 1][:3], "B": _MONTHS[mo - 1],
        "w": str(sun_wd), "u": str(wd + 1),
        "U": "%02d" % ((yday + 7 - sun_wd) // 7), "W": "%02d" % ((yday + 7 - wd) // 7), "%": "%",
    }
    out = []
    i = 0
    while i < len(fmt):
        c = fmt[i]
        if c != "%":
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(fmt) or fmt[i + 1] not in vals:
            raise ValueError("bad directive")
        out.append(vals[fmt[i + 1]])
        i += 2
    return "".join(out)
''')


task("v3_09_rpn_infix", r'''
Write `rpn_to_infix(rpn: str) -> str` that converts a postfix (RPN) expression to infix with
the fewest parentheses allowed by the rules below. Rules:
- Tokens are separated by one or more spaces (only " "; leading/trailing spaces allowed).
  Token kinds: a name ([a-z]+); an integer ("0" or a non-zero digit followed by digits);
  a binary operator + - * / ^; the unary negation "~"; a function call "name/N" where N is
  an integer as above (N may be 0), which pops N arguments. Anything else raises ValueError.
- Evaluation is the usual stack machine. Popping from an empty stack, an empty input, or
  ending with more than one item raises ValueError.
- Output format: a binary operator has one space on each side ("a + b"); negation is "-"
  directly before its operand ("-a", "--a"); a call is "name(" + arguments joined by ", " +
  ")"; "f/0" gives "f()". Call arguments are never parenthesized as a whole.
- Precedence, lowest to highest: + - (1), * / (2), negation (3), ^ (4); names, integers,
  calls and parenthesized expressions are atoms (5). Let p be the precedence of a binary
  operator and q the precedence of an operand's top-level expression:
  - left operand: parenthesize iff q < p, or the operator is ^ and the operand is also a
    ^ expression (^ is right-associative);
  - right operand: parenthesize iff q < p, or q == p and the operator is - or /.
    (So "a b c - +" gives "a + b - c", "a b c / *" gives "a * b / c", "a b c ^ ^" gives
    "a ^ b ^ c", but "a b c + -" gives "a - (b + c)".)
  - negation: parenthesize its operand iff q < 3 ("a b + ~" gives "-(a + b)", "a b ^ ~" gives
    "-a ^ b", "a ~ b ^" gives "(-a) ^ b", "a b ~ ^" gives "a ^ (-b)", "a b ~ *" gives "a * -b").
Examples: rpn_to_infix("3 x 2 ^ * y f/1 -") == "3 * x ^ 2 - f(y)";
rpn_to_infix("a b + c d - max/2 ~") == "-max(a + b, c - d)".
''', r'''
import random
from fractions import Fraction
def bad(s):
    try:
        rpn_to_infix(s)
    except ValueError:
        return True
    return False
fixed = {
    "3 x 2 ^ * y f/1 -": "3 * x ^ 2 - f(y)", "a b + c d - max/2 ~": "-max(a + b, c - d)", "a": "a", " 0 ": "0",
    "a b c - +": "a + b - c", "a b c / *": "a * b / c", "a b c ^ ^": "a ^ b ^ c", "a b ^ c ^": "(a ^ b) ^ c",
    "a b c + -": "a - (b + c)", "a b c * /": "a / (b * c)", "a b c - -": "a - (b - c)", "a b - c -": "a - b - c",
    "a b + ~": "-(a + b)", "a b ^ ~": "-a ^ b", "a ~ b ^": "(-a) ^ b", "a b ~ ^": "a ^ (-b)", "a b ~ *": "a * -b",
    "a ~ ~": "--a", "a ~ b *": "-a * b", "a b * ~": "-(a * b)", "f/0": "f()", "f/0 g/1": "g(f())",
    "a b + c *": "(a + b) * c", "a b c + *": "a * (b + c)", "a b * c +": "a * b + c", "a b c * +": "a + b * c",
    "a b + c d + *": "(a + b) * (c + d)", "b c d f/3 ~": "-f(b, c, d)",
    "x y z f/3": "f(x, y, z)", "a b - c - d -": "a - b - c - d", "a b c d - - -": "a - (b - (c - d))",
    "a b ~ -": "a - -b", "a ~ ~ b ^": "(--a) ^ b", "a b ^ c d ^ ^": "(a ^ b) ^ c ^ d", "10 a 2 ^ /": "10 / a ^ 2",
    "a b / c d / /": "a / b / (c / d)", "a b c * *": "a * b * c", "a b + c + d +": "a + b + c + d",
    "a b f/2 c ^": "f(a, b) ^ c", "a b c ^ ~ ^": "a ^ (-b ^ c)", "a   b  +": "a + b",
}
for s, v in fixed.items():
    assert rpn_to_infix(s) == v, (s, rpn_to_infix(s), v)
assert bad("a b c d f/3 ~")
for s in ["", "   ", "+", "a +", "a b", "~", "01", "a1", "A", "f/", "f/01", "/2", "f/1", "a f/2", "a b c f/2", "a\tb +", "a b +\n",
          "f/-1", "a -1 +", "a ** b", "a b %", "a,b +", "f/1x", "1.5"]:
    assert bad(s), s
PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 4}
def tree(s):
    st = []
    for t in s.split():
        if t in PREC:
            b = st.pop(); a = st.pop(); st.append((t, a, b))
        elif t == "~":
            st.append(("~", st.pop()))
        elif "/" in t:
            name, n = t.split("/")
            n = int(n)
            args = st[len(st) - n:]
            del st[len(st) - n:]
            st.append(("call", name, args))
        else:
            st.append(("atom", t))
    assert len(st) == 1
    return st[0]
def show(n):
    # returns (text, precedence)
    k = n[0]
    if k == "atom":
        return n[1], 5
    if k == "call":
        return n[1] + "(" + ", ".join(show(a)[0] for a in n[2]) + ")", 5
    if k == "~":
        t, q = show(n[1])
        return "-" + ("(" + t + ")" if q < 3 else t), 3
    p = PREC[k]
    lt, lq = show(n[1])
    rt, rq = show(n[2])
    if lq < p or (k == "^" and n[1][0] == "^"):
        lt = "(" + lt + ")"
    if rq < p or (rq == p and k in "-/"):
        rt = "(" + rt + ")"
    return lt + " " + k + " " + rt, p
# value check: parse the infix back with a precedence-climbing parser and evaluate exactly
def val_rpn(n, env):
    k = n[0]
    if k == "atom":
        return Fraction(int(n[1])) if n[1].isdigit() else env[n[1]]
    if k == "call":
        return sum((i + 2) * val_rpn(a, env) for i, a in enumerate(n[2])) + len(n[1])
    if k == "~":
        return -val_rpn(n[1], env)
    a, b = val_rpn(n[1], env), val_rpn(n[2], env)
    return {"+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b, "/": lambda: a / b}[k]()
def val_infix(s, env):
    toks = s.replace("(", " ( ").replace(")", " ) ").replace(",", " , ").split()
    # re-attach unary minus: a "-" token at operand position is negation
    pos = 0
    def peek():
        return toks[pos] if pos < len(toks) else None
    def expr(minp):
        nonlocal pos
        left = unary()
        while peek() in ("+", "-", "*", "/") and PREC[peek()] >= minp:
            op = toks[pos]; pos += 1
            right = expr(PREC[op] + 1)
            left = {"+": left + right, "-": left - right, "*": left * right}[op] if op != "/" else left / right
        return left
    def unary():
        nonlocal pos
        if peek() == "-":
            pos += 1
            return -unary()
        return atom()
    def atom():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            v = expr(1)
            assert toks[pos] == ")"; pos += 1
            return v
        sign = (-1) ** (len(t) - len(t.lstrip("-")))
        t = t.lstrip("-")
        if t == "":
            return sign * atom()
        if pos < len(toks) and toks[pos] == "(" and t.isalpha() and t not in env:
            pos += 1
            args = []
            if toks[pos] != ")":
                args.append(expr(1))
                while toks[pos] == ",":
                    pos += 1
                    args.append(expr(1))
            assert toks[pos] == ")"; pos += 1
            return sign * (sum((i + 2) * a for i, a in enumerate(args)) + len(t))
        return sign * atom_text(t)
    def atom_text(t):
        if t.startswith("-"):
            return -atom_text(t[1:])
        return Fraction(int(t)) if t.isdigit() else env[t]
    v = expr(1)
    assert pos == len(toks), s
    return v
random.seed(3009)
VARS = ["a", "b", "x", "yy"]
FUNCS = ["f", "g", "max", "h"]
def gen(d, allow_pow):
    r = random.random()
    if d <= 0 or r < 0.25:
        return random.choice(VARS + ["0", "1", "2", "17"])
    if r < 0.35:
        return gen(d - 1, allow_pow) + " ~"
    if r < 0.45:
        n = random.randint(0, 3)
        return " ".join([gen(d - 1, allow_pow) for _ in range(n)] + [random.choice(FUNCS) + "/" + str(n)])
    ops = "+-*/^" if allow_pow else "+-*/"
    return gen(d - 1, allow_pow) + " " + gen(d - 1, allow_pow) + " " + random.choice(ops)
for _ in range(3000):
    allow_pow = random.random() < 0.6
    s = gen(random.randint(1, 6), allow_pow)
    s = "  ".join(s.split()) if random.random() < 0.2 else s
    want = show(tree(s))[0]
    got = rpn_to_infix(s)
    assert got == want, (s, got, want)
    if not allow_pow:
        env = {v: Fraction(random.randint(-9, 9) or 1, random.randint(1, 5)) for v in VARS}
        try:
            v1 = val_rpn(tree(s), env)
        except ZeroDivisionError:
            continue
        assert val_infix(got, env) == v1, (s, got)
    if random.random() < 0.2:
        toks = s.split()
        toks.insert(random.randint(0, len(toks)), random.choice(["+", "*", "^"]))
        try:
            tree(" ".join(toks))
        except (IndexError, AssertionError):
            assert bad(" ".join(toks)), toks
''', r'''
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 4}


def _is_int(t):
    return t.isascii() and t.isdigit() and (t == "0" or t[0] != "0")


def _is_name(t):
    return t != "" and t.isascii() and t.isalpha() and t.islower()


def rpn_to_infix(rpn):
    if any(c != " " and c.isspace() for c in rpn):
        raise ValueError("only spaces separate tokens")
    toks = rpn.split(" ")
    toks = [t for t in toks if t != ""]
    if not toks:
        raise ValueError("empty")
    st = []   # (text, precedence, kind) where kind is the top-level operator or "atom"

    def pop():
        if not st:
            raise ValueError("stack underflow")
        return st.pop()

    for t in toks:
        if t in _PREC:
            b = pop()
            a = pop()
            p = _PREC[t]
            lt = a[0]
            if a[1] < p or (t == "^" and a[2] == "^"):
                lt = "(" + lt + ")"
            rt = b[0]
            if b[1] < p or (b[1] == p and t in "-/"):
                rt = "(" + rt + ")"
            st.append((lt + " " + t + " " + rt, p, t))
        elif t == "~":
            a = pop()
            st.append(("-" + ("(" + a[0] + ")" if a[1] < 3 else a[0]), 3, "~"))
        elif "/" in t:
            name, _, n = t.partition("/")
            if not _is_name(name) or not _is_int(n):
                raise ValueError("bad call token")
            n = int(n)
            if n > len(st):
                raise ValueError("stack underflow")
            args = st[len(st) - n:]
            del st[len(st) - n:]
            st.append((name + "(" + ", ".join(a[0] for a in args) + ")", 5, "atom"))
        elif _is_name(t) or _is_int(t):
            st.append((t, 5, "atom"))
        else:
            raise ValueError("bad token")
    if len(st) != 1:
        raise ValueError("leftover operands")
    return st[0][0]
''')


task("v3_10_bencode", r'''
Write two functions for strict, canonical bencoding.
`bdecode(data: bytes)` returns int, bytes, list or dict (with bytes keys). Rules:
- Integer: b"i", an optional "-", one or more ASCII digits, b"e". No leading zeros ("i03e"),
  no "i-0e", no empty digits ("ie", "i-e").
- Byte string: a length in ASCII digits (no leading zeros, "0" allowed), b":", then exactly
  that many bytes. Fewer bytes left raises ValueError.
- List: b"l", zero or more values, b"e". Dict: b"d", zero or more (key, value) pairs, b"e";
  every key must be a byte string, and keys must be strictly increasing in raw byte order
  (so no duplicates, no unsorted keys).
- The input must be exactly one value: empty input, trailing bytes, an unexpected byte, or
  input ending inside a value raise ValueError.
`bencode(obj) -> bytes`:
- int -> integer (bool is not allowed: TypeError); bytes -> byte string; str -> its UTF-8
  bytes as a byte string; list or tuple -> list; dict -> dict whose keys are bytes or str
  (str keys are UTF-8 encoded), written in increasing raw byte order of the encoded keys.
- Two keys that encode to the same bytes (e.g. "a" and b"a") raise ValueError. Any other
  type (float, None, set, bool, a dict key that is not str/bytes) raises TypeError.
Examples: bdecode(b"d1:ali-3ee1:b0:e") == {b"a": [-3], b"b": b""};
bencode({"b": 1, b"a": ["x", (2,)]}) == b"d1:al1:xli2eee1:bi1ee". Use no third-party modules.
''', r'''
import random
def bad(b):
    try:
        bdecode(b)
    except ValueError:
        return True
    return False
def enc_err(o):
    try:
        bencode(o)
    except ValueError:
        return "V"
    except TypeError:
        return "T"
    return None
assert bdecode(b"d1:ali-3ee1:b0:e") == {b"a": [-3], b"b": b""}
assert bencode({"b": 1, b"a": ["x", (2,)]}) == b"d1:al1:xli2eee1:bi1ee"
assert bdecode(b"i0e") == 0 and bdecode(b"i-12e") == -12 and bdecode(b"0:") == b"" and bdecode(b"le") == [] and bdecode(b"de") == {}
assert bdecode(b"3:a:e") == b"a:e" and bdecode(b"10:0123456789") == b"0123456789"
assert bdecode(b"d1:a0:2:aa0:1:b0:e") == {b"a": b"", b"aa": b"", b"b": b""}
assert bdecode(b"d2:\x00\x000:1:\xff0:e") == {b"\x00\x00": b"", b"\xff": b""}
assert bad(b"d1:\xff0:2:\x00\x000:e")
assert bdecode(b"llleee") == [[[]]]
assert bencode(0) == b"i0e" and bencode(-5) == b"i-5e" and bencode(b"") == b"0:" and bencode("é") == b"2:\xc3\xa9"
assert bencode({}) == b"de" and bencode([]) == b"le" and bencode(()) == b"le"
assert bencode({"aa": 1, "b": 2, "a": 3}) == b"d1:ai3e2:aai1e1:bi2ee"
assert bencode({"é": 0, "z": 0}) == b"d1:zi0e2:\xc3\xa9i0ee"
assert bencode(10 ** 30) == b"i" + str(10 ** 30).encode() + b"e"
for b in [b"", b"i", b"ie", b"i-e", b"i03e", b"i-0e", b"i-03e", b"i1", b"i1x", b"i+1e", b"i 1e", b"01:a", b"2:a", b"1a", b":",
          b"l", b"li1e", b"d", b"d1:a", b"d1:ai1e", b"di1ei1ee", b"d1:b0:1:a0:e", b"d1:a0:1:a0:e", b"i1ei2e", b"le ",
          b"x", b"e", b"d1:ae", b"-1:a", b"1:ab", b"l1:ae1", b"i1.5e", b"d0:i1e0:i2ee", b"\xff", b"lde"[:2]]:
    assert bad(b), b
assert bdecode(b"d0:i1ee") == {b"": 1}
for o in [True, False, 1.5, None, {1, 2}, {1: 2}, [None], {"a": True}, {b"a": 1.0}, object(), {(1,): 1}, bytearray(b"x")]:
    assert enc_err(o) == "T", o
for o in [{"a": 1, b"a": 2}, [{"é": 0, "é".encode(): 1}]]:
    assert enc_err(o) == "V", o
def my_enc(o):
    if isinstance(o, int):
        return b"i%de" % o
    if isinstance(o, str):
        o = o.encode()
    if isinstance(o, bytes):
        return b"%d:" % len(o) + o
    if isinstance(o, (list, tuple)):
        return b"l" + b"".join(my_enc(x) for x in o) + b"e"
    items = sorted(((k.encode() if isinstance(k, str) else k), v) for k, v in o.items())
    return b"d" + b"".join(my_enc(k) + my_enc(v) for k, v in items) + b"e"
def norm(o):
    if isinstance(o, str):
        return o.encode()
    if isinstance(o, (list, tuple)):
        return [norm(x) for x in o]
    if isinstance(o, dict):
        return {(k.encode() if isinstance(k, str) else k): norm(v) for k, v in o.items()}
    return o
def my_dec(b):
    # returns value or None on any error
    import re
    pos = 0
    def val():
        nonlocal pos
        if pos >= len(b):
            raise IndexError
        c = b[pos:pos + 1]
        if c == b"i":
            m = re.compile(rb"i(0|-?[1-9][0-9]*)e").match(b, pos)
            if not m:
                raise IndexError
            pos = m.end()
            return int(m.group(1))
        if c == b"l":
            pos += 1
            out = []
            while b[pos:pos + 1] != b"e":
                out.append(val())
            pos += 1
            return out
        if c == b"d":
            pos += 1
            out = {}
            last = None
            while b[pos:pos + 1] != b"e":
                if pos >= len(b):
                    raise IndexError
                k = val()
                if not isinstance(k, bytes) or (last is not None and k <= last):
                    raise IndexError
                last = k
                out[k] = val()
            pos += 1
            return out
        m = re.compile(rb"(0|[1-9][0-9]*):").match(b, pos)
        if not m:
            raise IndexError
        n = int(m.group(1))
        if m.end() + n > len(b):
            raise IndexError
        pos = m.end() + n
        return b[m.end():pos]
    try:
        v = val()
    except IndexError:
        return "V"
    return v if pos == len(b) else "V"
random.seed(3010)
def rnd(d):
    r = random.random()
    if d <= 0 or r < 0.35:
        return random.choice([0, 1, -1, 9, 10, -10, 2 ** 70, -(2 ** 40), random.randint(-999, 999)])
    if r < 0.6:
        k = random.choice([b"", b"a", b"ab", b"\x00", b"\xff\x00", b"e", b"i1e", b"12:", bytes(random.getrandbits(8) for _ in range(12))])
        return k.decode("latin-1") if random.random() < 0.3 and k.isascii() else k
    if r < 0.8:
        xs = [rnd(d - 1) for _ in range(random.randint(0, 3))]
        return tuple(xs) if random.random() < 0.3 else xs
    out = {}
    for _ in range(random.randint(0, 4)):
        k = random.choice([b"", b"a", b"b", b"aa", b"ab", b"\x80", b"\xff", "z", "zz", "é", b"A", b"a\x00"])
        kb = k.encode() if isinstance(k, str) else k
        if any((x.encode() if isinstance(x, str) else x) == kb for x in out):
            continue
        out[k] = rnd(d - 1)
    return out
for _ in range(2000):
    o = rnd(4)
    e = bencode(o)
    assert e == my_enc(o), (o, e, my_enc(o))
    assert bdecode(e) == norm(o), (e, bdecode(e), norm(o))
    m = bytearray(e)
    k = random.random()
    if k < 0.3:
        del m[random.randrange(len(m)):]
    elif k < 0.6:
        m[random.randrange(len(m))] = random.choice(b"ile0123456789:-dx")
    elif k < 0.8:
        m.insert(random.randint(0, len(m)), random.choice(b"ile0-:d"))
    else:
        i = random.randrange(len(m)); j = random.randrange(len(m))
        m[i], m[j] = m[j], m[i]
    m = bytes(m)
    exp = my_dec(m)
    try:
        got = bdecode(m)
    except ValueError:
        got = "V"
    assert got == exp, (m, got, exp)
''', r'''
def _digits(b):
    return len(b) > 0 and all(48 <= c <= 57 for c in b)


def _decode(data, pos):
    if pos >= len(data):
        raise ValueError("unexpected end")
    c = data[pos]
    if c == ord("i"):
        end = data.find(b"e", pos + 1)
        if end < 0:
            raise ValueError("unterminated integer")
        s = data[pos + 1:end]
        neg = s.startswith(b"-")
        d = s[1:] if neg else s
        if not _digits(d) or (len(d) > 1 and d[0] == 48) or (neg and d == b"0"):
            raise ValueError("bad integer")
        return int(s), end + 1
    if c == ord("l"):
        pos += 1
        out = []
        while True:
            if pos >= len(data):
                raise ValueError("unterminated list")
            if data[pos] == ord("e"):
                return out, pos + 1
            v, pos = _decode(data, pos)
            out.append(v)
    if c == ord("d"):
        pos += 1
        out = {}
        last = None
        while True:
            if pos >= len(data):
                raise ValueError("unterminated dict")
            if data[pos] == ord("e"):
                return out, pos + 1
            if not (48 <= data[pos] <= 57):
                raise ValueError("dict key must be a byte string")
            k, pos = _decode(data, pos)
            if last is not None and k <= last:
                raise ValueError("dict keys not strictly increasing")
            last = k
            v, pos = _decode(data, pos)
            out[k] = v
    if 48 <= c <= 57:
        colon = data.find(b":", pos)
        if colon < 0:
            raise ValueError("missing colon")
        ln = data[pos:colon]
        if not _digits(ln) or (len(ln) > 1 and ln[0] == 48):
            raise ValueError("bad length")
        n = int(ln)
        start = colon + 1
        if start + n > len(data):
            raise ValueError("string too short")
        return bytes(data[start:start + n]), start + n
    raise ValueError("unexpected byte")


def bdecode(data):
    data = bytes(data)
    v, pos = _decode(data, 0)
    if pos != len(data):
        raise ValueError("trailing data")
    return v


def bencode(obj):
    if isinstance(obj, bool):
        raise TypeError("bool not allowed")
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, str):
        obj = obj.encode("utf-8")
    if type(obj) is bytes:
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, (list, tuple)):
        return b"l" + b"".join(bencode(x) for x in obj) + b"e"
    if isinstance(obj, dict):
        items = {}
        for k, v in obj.items():
            if isinstance(k, str):
                kb = k.encode("utf-8")
            elif type(k) is bytes:
                kb = k
            else:
                raise TypeError("bad key type")
            if kb in items:
                raise ValueError("duplicate key")
            items[kb] = v
        return b"d" + b"".join(bencode(k) + bencode(items[k]) for k in sorted(items)) + b"e"
    raise TypeError("unsupported type")
''')


task("v3_11_bridges_2ecc", r'''
Write `bridges_and_components(n: int, edges: list[tuple[int, int]]) -> tuple[list[int], list[list[int]]]`.
The undirected graph has vertices 0..n-1 (n >= 1); edges[i] = (u, v) is the edge with index i.
Parallel edges and self-loops are allowed, and the graph may be disconnected. An edge is a
bridge if deleting that one edge index (parallel copies of it stay) increases the number of
connected components. Self-loops are never bridges, and an edge with a parallel copy is never
a bridge.
Return (bridges, comps):
- bridges: the sorted list of edge indices that are bridges.
- comps: the 2-edge-connected components, i.e. the connected components of the graph after
  deleting every bridge. Each component is a sorted list of vertices, and the list of
  components is sorted by smallest vertex. An isolated vertex is a component on its own.
Examples: n=4, edges [(0,1), (1,2), (2,0), (2,3)] -> ([3], [[0, 1, 2], [3]]).
n=2, edges [(0,1), (0,1)] -> ([], [[0, 1]]). n=3, edges [(0,1), (1,1)] -> ([0], [[0], [1], [2]]).
Must handle n and len(edges) up to 200000 in a few seconds, including a path-shaped graph
(deep recursion will overflow the Python stack).
''', r'''
import random, time
def _comps(n, edges, skip):
    p = list(range(n))
    def f(x):
        while p[x] != x:
            p[x] = p[p[x]]; x = p[x]
        return x
    for i, (u, v) in enumerate(edges):
        if i not in skip:
            p[f(u)] = f(v)
    groups = {}
    for v in range(n):
        groups.setdefault(f(v), []).append(v)
    return sorted(groups.values())
def _oracle(n, edges):
    base = len(_comps(n, edges, ()))
    br = [i for i in range(len(edges)) if len(_comps(n, edges, (i,))) > base]
    return (br, _comps(n, edges, set(br)))
assert bridges_and_components(1, []) == ([], [[0]])
assert bridges_and_components(1, [(0, 0)]) == ([], [[0]])
assert bridges_and_components(2, [(0, 1)]) == ([0], [[0], [1]])
assert bridges_and_components(2, [(0, 1), (1, 0)]) == ([], [[0, 1]])
assert bridges_and_components(4, [(0, 1), (1, 2), (2, 0), (2, 3)]) == ([3], [[0, 1, 2], [3]])
assert bridges_and_components(3, [(0, 1), (1, 1)]) == ([0], [[0], [1], [2]])
assert bridges_and_components(6, [(3, 4), (4, 5), (5, 3), (0, 3), (1, 2)]) == ([3, 4], [[0], [1], [2], [3, 4, 5]])
assert bridges_and_components(5, [(0, 1), (1, 2), (2, 3), (3, 1), (3, 4), (4, 3), (0, 4)]) == ([], [[0, 1, 2, 3, 4]])
random.seed(3011)
for _ in range(1500):
    n = random.randint(1, 8)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(random.randint(0, 11))]
    assert bridges_and_components(n, edges) == _oracle(n, edges), (n, edges)
t0 = time.perf_counter()
n = 200000
b, c = bridges_and_components(n, [(i, i + 1) for i in range(n - 1)])
assert b == list(range(n - 1)) and len(c) == n
b, c = bridges_and_components(n, [(i, (i + 1) % n) for i in range(n)])
assert b == [] and c == [list(range(n))]
edges = [(random.randrange(i), i) for i in range(1, n)] + [(random.randrange(n), random.randrange(n)) for _ in range(1000)]
b, c = bridges_and_components(n, edges)
assert sum(len(x) for x in c) == n and len(c) == len(b) + 1
assert time.perf_counter() - t0 < 10.0
''', r'''
def bridges_and_components(n, edges):
    adj = [[] for _ in range(n)]
    for i, (u, v) in enumerate(edges):
        if u != v:
            adj[u].append((v, i)); adj[v].append((u, i))
    tin = [-1] * n; low = [0] * n; it = [0] * n; pe = [-1] * n
    isb = [False] * len(edges)
    timer = 0
    for r in range(n):
        if tin[r] != -1:
            continue
        tin[r] = low[r] = timer; timer += 1
        st = [r]
        while st:
            x = st[-1]
            if it[x] < len(adj[x]):
                y, i = adj[x][it[x]]; it[x] += 1
                if i == pe[x]:
                    continue
                if tin[y] == -1:
                    pe[y] = i; tin[y] = low[y] = timer; timer += 1; st.append(y)
                elif tin[y] < low[x]:
                    low[x] = tin[y]
            else:
                st.pop()
                if st:
                    p = st[-1]
                    if low[x] < low[p]:
                        low[p] = low[x]
                    if low[x] > tin[p]:
                        isb[pe[x]] = True
    comp = [-1] * n; comps = []
    for r in range(n):
        if comp[r] != -1:
            continue
        comp[r] = len(comps); q = [r]
        for x in q:
            for y, i in adj[x]:
                if not isb[i] and comp[y] == -1:
                    comp[y] = comp[r]; q.append(y)
        comps.append(sorted(q))
    return [i for i in range(len(edges)) if isb[i]], comps
''')


task("v3_12_min_cut", r'''
Write `min_cut(n: int, edges: list[tuple[int, int, int]], s: int, t: int) -> tuple[int, list[int]]`.
The network has vertices 0..n-1 and directed edges (u, v, capacity); capacities are integers
>= 0 and can be as large as 10**9. Parallel edges and edges in both directions between the
same pair are allowed and independent; self-loops may appear and are useless. s != t.
An s-t cut is a vertex set S with s in S and t not in S; its capacity is the sum of the
capacities of the edges going from a vertex in S to a vertex outside S.
Return (F, S): F is the maximum flow value from s to t (equal to the minimum cut capacity),
and S is the sorted list of vertices of the minimum-capacity cut that has the fewest vertices.
That set is unique: it is exactly the set of vertices reachable from s in the residual graph
of a maximum flow.
Example: n=4, edges [(0,1,3), (1,3,1), (0,2,1), (2,3,5)], s=0, t=3 -> (2, [0, 1]).
n=3, edges [(0,1,0)], s=0, t=2 -> (0, [0]).
Must handle n=300 and 3000 edges with capacities up to 10**9 in a few seconds (pushing flow one
unit at a time is far too slow).
''', r'''
import random, time
def _oracle(n, edges, s, t):
    others = [v for v in range(n) if v != s and v != t]
    best = None
    for m in range(1 << len(others)):
        S = {s} | {others[i] for i in range(len(others)) if m >> i & 1}
        c = sum(w for u, v, w in edges if u in S and v not in S)
        key = (c, len(S))
        if best is None or key < best[0]:
            best = (key, sorted(S))
    return (best[0][0], best[1])
assert min_cut(2, [], 0, 1) == (0, [0])
assert min_cut(3, [(0, 1, 0)], 0, 2) == (0, [0])
assert min_cut(4, [(0, 1, 3), (1, 3, 1), (0, 2, 1), (2, 3, 5)], 0, 3) == (2, [0, 1])
assert min_cut(3, [(0, 1, 2), (1, 2, 2)], 0, 2) == (2, [0])
assert min_cut(3, [(0, 1, 2), (1, 2, 2), (1, 0, 7), (2, 2, 9)], 2, 0) == (0, [2])
assert min_cut(4, [(0, 1, 5), (0, 1, 5), (1, 2, 4), (2, 3, 100), (1, 3, 1)], 0, 3) == (5, [0, 1])
random.seed(3012)
for _ in range(700):
    n = random.randint(2, 7)
    edges = [(random.randrange(n), random.randrange(n), random.choice([0, 1, 1, 2, 3, 4, 6]))
             for _ in range(random.randint(0, 14))]
    s, t = random.sample(range(n), 2)
    assert min_cut(n, edges, s, t) == _oracle(n, edges, s, t), (n, edges, s, t)
t0 = time.perf_counter()
for _ in range(3):
    n = 300
    edges = [(random.randrange(n), random.randrange(n), random.randint(10**8, 10**9)) for _ in range(3000)]
    F, S = min_cut(n, edges, 0, n - 1)
    Sset = set(S)
    assert 0 in Sset and n - 1 not in Sset and S == sorted(Sset)
    assert F == sum(w for u, v, w in edges if u in Sset and v not in Sset)
assert min_cut(3, [(0, 1, 10**9), (1, 2, 10**9), (0, 2, 10**9 - 1)], 0, 2) == (2 * 10**9 - 1, [0])
assert time.perf_counter() - t0 < 10.0
''', r'''
from collections import deque


def min_cut(n, edges, s, t):
    to, cap, head = [], [], [[] for _ in range(n)]
    for u, v, c in edges:
        if u == v:
            continue
        head[u].append(len(to)); to.append(v); cap.append(c)
        head[v].append(len(to)); to.append(u); cap.append(0)
    flow = 0
    BIG = 1 << 62
    while True:
        level = [-1] * n; level[s] = 0; q = deque([s])
        while q:
            x = q.popleft()
            for e in head[x]:
                if cap[e] > 0 and level[to[e]] < 0:
                    level[to[e]] = level[x] + 1; q.append(to[e])
        if level[t] < 0:
            break
        it = [0] * n

        def dfs(x, f):
            if x == t:
                return f
            hx = head[x]
            while it[x] < len(hx):
                e = hx[it[x]]; y = to[e]
                if cap[e] > 0 and level[y] == level[x] + 1:
                    d = dfs(y, min(f, cap[e]))
                    if d > 0:
                        cap[e] -= d; cap[e ^ 1] += d
                        return d
                it[x] += 1
            return 0
        while True:
            f = dfs(s, BIG)
            if f == 0:
                break
            flow += f
    seen = [False] * n; seen[s] = True; q = [s]
    for x in q:
        for e in head[x]:
            if cap[e] > 0 and not seen[to[e]]:
                seen[to[e]] = True; q.append(to[e])
    return flow, [v for v in range(n) if seen[v]]
''')


task("v3_13_farthest_vertex", r'''
Write `farthest(n: int, edges: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]`.
The input is a tree with vertices 0..n-1 (n >= 1, exactly n-1 undirected edges (u, v, w),
connected); every edge weight w is an integer >= 1. The distance between two vertices is the
sum of the edge weights on the unique path between them. For every vertex v, in order
v = 0..n-1, return (d, f, c): d is the largest distance from v to any vertex, f is the smallest
vertex index among the vertices at distance d from v, and c is the number of vertices at
distance d from v.
For n == 1 the answer is [(0, 0, 1)].
Example: n=4, edges [(0,1,1), (0,2,1), (0,3,1)] -> [(1, 1, 3), (2, 2, 2), (2, 1, 2), (2, 1, 2)].
Must handle n up to 100000 in a few seconds, including a path-shaped tree (deep recursion will
overflow the Python stack; a search from every vertex is far too slow).
''', r'''
import random, time
def _oracle(n, edges):
    adj = [[] for _ in range(n)]
    for a, b, w in edges:
        adj[a].append((b, w)); adj[b].append((a, w))
    out = []
    for u in range(n):
        dist = {u: 0}; todo = [u]
        while todo:
            x = todo.pop()
            for y, w in adj[x]:
                if y not in dist:
                    dist[y] = dist[x] + w; todo.append(y)
        d = max(dist.values())
        far = [v for v in dist if dist[v] == d]
        out.append((d, min(far), len(far)))
    return out
assert farthest(1, []) == [(0, 0, 1)]
assert farthest(2, [(1, 0, 5)]) == [(5, 1, 1), (5, 0, 1)]
assert farthest(4, [(0, 1, 1), (0, 2, 1), (0, 3, 1)]) == [(1, 1, 3), (2, 2, 2), (2, 1, 2), (2, 1, 2)]
assert farthest(5, [(0, 1, 2), (1, 2, 2), (2, 3, 2), (3, 4, 2)]) == [(8, 4, 1), (6, 4, 1), (4, 0, 2), (6, 0, 1), (8, 0, 1)]
assert farthest(6, [(0, 5, 3), (0, 4, 3), (0, 1, 1), (1, 2, 1), (1, 3, 1)]) == [(3, 4, 2), (4, 4, 2), (5, 4, 2), (5, 4, 2), (6, 5, 1), (6, 4, 1)]
assert farthest(7, [(0, 1, 1), (1, 2, 1), (0, 3, 1), (3, 4, 1), (0, 5, 1), (5, 6, 1)]) == [(2, 2, 3), (3, 4, 2), (4, 4, 2), (3, 2, 2), (4, 2, 2), (3, 2, 2), (4, 2, 2)]
random.seed(3013)
for _ in range(1200):
    n = random.randint(1, 10)
    edges = [(random.randrange(i), i) for i in range(1, n)]
    perm = list(range(n)); random.shuffle(perm)
    edges = [(perm[a], perm[b], random.randint(1, 3)) if random.random() < 0.5 else (perm[b], perm[a], random.randint(1, 3)) for a, b in edges]
    assert farthest(n, edges) == _oracle(n, edges), (n, edges)
t0 = time.perf_counter()
n = 100000
r = farthest(n, [(i, i + 1, 1) for i in range(n - 1)])
assert r[0] == (n - 1, n - 1, 1) and r[n - 1] == (n - 1, 0, 1) and r[n // 2] == (n // 2, 0, 1)
r = farthest(n, [(0, i, 7) for i in range(1, n)])
assert r[0] == (7, 1, n - 1) and r[1] == (14, 2, n - 2) and r[5] == (14, 1, n - 2)
edges = [(random.randrange(i), i, random.randint(1, 2)) for i in range(1, n)]
r = farthest(n, edges)
assert len(r) == n and all(isinstance(x, tuple) and x[0] > 0 and x[2] >= 1 for x in r)
assert time.perf_counter() - t0 < 10.0
''', r'''
def _merge(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] != b[0]:
        return a if a[0] > b[0] else b
    return (a[0], min(a[1], b[1]), a[2] + b[2])


def farthest(n, edges):
    adj = [[] for _ in range(n)]
    for a, b, w in edges:
        adj[a].append((b, w)); adj[b].append((a, w))
    parent = [-1] * n
    seen = [False] * n; seen[0] = True
    order = [0]
    for x in order:
        for y, w in adj[x]:
            if not seen[y]:
                seen[y] = True; parent[y] = x; order.append(y)
    # (dist, smallest index, count) over the subtree, measured from its root
    down = [None] * n
    for v in reversed(order):
        best = (0, v, 1)
        for y, w in adj[v]:
            if y != parent[v]:
                best = _merge(best, (down[y][0] + w, down[y][1], down[y][2]))
        down[v] = best
    up = [None] * n  # outside v's subtree, measured from v
    for v in order:
        kids = [(y, w) for y, w in adj[v] if y != parent[v]]
        contrib = [(down[y][0] + w, down[y][1], down[y][2]) for y, w in kids]
        k = len(kids)
        pre = [None] * (k + 1)
        for i in range(k):
            pre[i + 1] = _merge(pre[i], contrib[i])
        suf = [None] * (k + 1)
        for i in range(k - 1, -1, -1):
            suf[i] = _merge(suf[i + 1], contrib[i])
        base = _merge((0, v, 1), up[v])
        for i, (y, w) in enumerate(kids):
            b = _merge(base, _merge(pre[i], suf[i + 1]))
            up[y] = (b[0] + w, b[1], b[2])
    return [_merge(down[v], up[v]) for v in range(n)]
''')


task("v3_14_route_lex", r'''
Write `best_route(n: int, w: list[list[int | None]]) -> tuple[int, list[int]] | None`.
There are n places 0..n-1 (1 <= n <= 13). w[i][j] (i != j) is the integer cost of travelling
directly from i to j (it may be negative or zero), or None if there is no direct road from i
to j; roads are one-way, so w[i][j] and w[j][i] are unrelated. The diagonal w[i][i] is
ignored. A route is a list containing every place exactly once, starting with 0 (it does not
return to 0), such that every consecutive pair (a, b) has w[a][b] not None. Its cost is the sum
of those w[a][b].
Return (cost, route) for a route of minimum cost; if several routes have that cost, return the
lexicographically smallest route list. Return None if no route exists. For n == 1 return
(0, [0]).
Example: n=3, w=[[0,1,1],[1,0,1],[1,1,0]] -> (2, [0, 1, 2]).
n=3, w=[[0,None,5],[2,0,None],[None,3,0]] -> (8, [0, 2, 1]).
Must handle n = 13 in about a second (trying all orders is far too slow).
''', r'''
import random, time, itertools
def _oracle(n, w):
    best = None
    for p in itertools.permutations(range(1, n)):
        r = (0,) + p
        c = 0
        for a, b in zip(r, r[1:]):
            if w[a][b] is None:
                c = None; break
            c += w[a][b]
        if c is not None and (best is None or c < best[0]):
            best = (c, list(r))
    return best
assert best_route(1, [[None]]) == (0, [0])
assert best_route(2, [[0, None], [4, 0]]) is None
assert best_route(2, [[0, -4], [None, 0]]) == (-4, [0, 1])
assert best_route(3, [[0, 1, 1], [1, 0, 1], [1, 1, 0]]) == (2, [0, 1, 2])
assert best_route(3, [[0, None, 5], [2, 0, None], [None, 3, 0]]) == (8, [0, 2, 1])
assert best_route(4, [[0, 1, 2, 3], [0, 0, 1, 2], [0, 0, 0, 1], [0, 0, 0, 0]]) == (3, [0, 1, 2, 3])
assert best_route(4, [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]) == (0, [0, 1, 2, 3])
assert best_route(4, [[0, 5, 1, None], [None, 0, None, 1], [None, 1, 0, None], [None, None, None, 0]]) == (3, [0, 2, 1, 3])
random.seed(3014)
for _ in range(500):
    n = random.randint(1, 7)
    w = [[None if random.random() < 0.3 else random.randint(-2, 3) for _ in range(n)] for _ in range(n)]
    assert best_route(n, w) == _oracle(n, w), (n, w)
t0 = time.perf_counter()
for _ in range(2):
    n = 13
    w = [[random.randint(0, 3) if random.random() < 0.9 else None for _ in range(n)] for _ in range(n)]
    r = best_route(n, w)
    assert r is None or (len(r[1]) == n and sorted(r[1]) == list(range(n)) and r[1][0] == 0)
n = 13
w = [[0] * n for _ in range(n)]
assert best_route(n, w) == (0, list(range(n)))
assert time.perf_counter() - t0 < 10.0
''', r'''
def best_route(n, w):
    if n == 1:
        return (0, [0])
    full = (1 << n) - 1
    f = [None] * ((1 << n) * n)
    for v in range(n):
        f[full * n + v] = 0
    for mask in range(full - 1, 0, -1):
        if not mask & 1:
            continue
        for v in range(n):
            if not mask >> v & 1:
                continue
            best = None
            wv = w[v]
            for u in range(n):
                if mask >> u & 1:
                    continue
                c = wv[u]
                if c is None:
                    continue
                r = f[(mask | 1 << u) * n + u]
                if r is None:
                    continue
                if best is None or c + r < best:
                    best = c + r
            f[mask * n + v] = best
    if f[n] is None:
        return None
    route = [0]; mask = 1; v = 0
    while mask != full:
        for u in range(n):
            if mask >> u & 1 or w[v][u] is None:
                continue
            r = f[(mask | 1 << u) * n + u]
            if r is not None and w[v][u] + r == f[mask * n + v]:
                route.append(u); mask |= 1 << u; v = u
                break
    return (f[n], route)
''')


task("v3_15_digit_kth", r'''
Write `count_and_kth(lo: int, hi: int, m: int, k: int) -> tuple[int, int | None]`.
A non-negative integer x is good if its decimal representation (no leading zeros; zero is
written "0") has no two adjacent equal digits and its digit sum is divisible by m.
Inputs: 0 <= lo <= hi <= 10**18, 1 <= m <= 60, k >= 1.
Return (c, x): c is the number of good integers in [lo, hi] (both ends included), and x is the
k-th smallest good integer in [lo, hi], or None if there are fewer than k.
Examples: count_and_kth(0, 20, 1, 12) -> (20, 12) (the good numbers are 0..10 and 12..20).
count_and_kth(10, 30, 3, 2) -> (7, 15) (the good numbers are 12, 15, 18, 21, 24, 27, 30).
count_and_kth(11, 11, 1, 1) -> (0, None).
Each call must be fast: well under 0.1 s even for hi near 10**18 (scanning the range is far
too slow).
''', r'''
import random, time
def _good(x, m):
    s = str(x)
    return all(a != b for a, b in zip(s, s[1:])) and sum(map(int, s)) % m == 0
def _oracle(lo, hi, m, k):
    g = [x for x in range(lo, hi + 1) if _good(x, m)]
    return (len(g), g[k - 1] if k <= len(g) else None)
assert count_and_kth(0, 20, 1, 12) == (20, 12)
assert count_and_kth(10, 30, 3, 2) == (7, 15)
assert count_and_kth(11, 11, 1, 1) == (0, None)
assert count_and_kth(0, 0, 7, 1) == (1, 0)
assert count_and_kth(0, 0, 7, 2) == (1, None)
assert count_and_kth(100, 199, 1, 1) == (81, 101)
assert count_and_kth(10**18, 10**18, 1, 1) == (0, None)
assert count_and_kth(0, 10**18, 1, 1) == (1 + sum(9 ** d for d in range(1, 19)), 0)
assert count_and_kth(0, 10**18, 1, 1 + sum(9 ** d for d in range(1, 19))) == (1 + sum(9 ** d for d in range(1, 19)), 989898989898989898)
random.seed(3015)
for _ in range(300):
    lo = random.randint(0, 3000); hi = lo + random.randint(0, 1500)
    m = random.randint(1, 30); k = random.randint(1, 60)
    assert count_and_kth(lo, hi, m, k) == _oracle(lo, hi, m, k), (lo, hi, m, k)
for _ in range(60):
    lo = random.randint(0, 10**18 - 3000); hi = lo + random.randint(0, 2500)
    m = random.randint(1, 60); k = random.randint(1, 40)
    assert count_and_kth(lo, hi, m, k) == _oracle(lo, hi, m, k), (lo, hi, m, k)
t0 = time.perf_counter()
for _ in range(20):
    lo = random.randint(0, 10**17); hi = random.randint(lo, 10**18)
    c, x = count_and_kth(lo, hi, random.randint(1, 60), random.randint(1, 10**6))
    assert x is None or (lo <= x <= hi and _good(x, 1))
assert time.perf_counter() - t0 < 4.0
''', r'''
def count_and_kth(lo, hi, m, k):
    F = [[[0] * m for _ in range(10)] for _ in range(20)]
    for last in range(10):
        F[0][last][0] = 1
    for r in range(1, 20):
        for last in range(10):
            row = F[r][last]
            for s in range(m):
                t = 0
                for d in range(10):
                    if d != last:
                        t += F[r - 1][d][(s + d) % m]
                row[s] = t

    def count(N):
        if N < 0:
            return 0
        D = list(map(int, str(N)))
        L = len(D)
        total = 1  # zero
        for l in range(1, L):
            for d in range(1, 10):
                total += F[l - 1][d][d % m]
        prev = -1; s = 0
        for i in range(L):
            for d in range(1 if i == 0 else 0, D[i]):
                if d != prev:
                    total += F[L - 1 - i][d][(s + d) % m]
            if D[i] == prev:
                return total
            prev = D[i]; s = (s + D[i]) % m
        if L > 1 or N > 0:
            total += s == 0
        return total
    base = count(lo - 1)
    c = count(hi) - base
    if k > c:
        return (c, None)
    target = base + k
    a, b = lo, hi
    while a < b:
        mid = (a + b) // 2
        if count(mid) >= target:
            b = mid
        else:
            a = mid + 1
    return (c, a)
''')


task("v3_16_persistent_multiset", r'''
Write `persistent_multiset(ops: list[tuple]) -> list[int | None]`.
Process a list of operations on versions of a multiset of integers. Version 0 is the empty
multiset. Versions are numbered 1, 2, 3, ... in the order they are created; only "add" and
"remove" create a version, and they never change an existing version. In every operation, v
is an existing version number (0 <= v <= number of versions created so far).
- ("add", v, x): create a new version equal to version v plus one copy of x.
- ("remove", v, x): create a new version equal to version v minus one copy of x. If version v
  does not contain x, the new version is still created and equals version v.
- ("kth", v, k): answer the k-th smallest element of version v counting copies (k = 1 is the
  smallest), or None if k < 1 or k is larger than the size of version v. Creates no version.
- ("count", v, a, b): answer the number of elements of version v (counting copies) with
  a <= element <= b; 0 if a > b. Creates no version.
Values x, a, b are integers with absolute value up to 10**9. Return the answers of the "kth"
and "count" operations, in order.
Example: [("add",0,5), ("add",1,3), ("kth",2,1), ("kth",1,1), ("count",0,0,10),
("remove",2,5), ("count",3,0,10), ("kth",3,2), ("remove",0,7), ("count",2,3,5)]
-> [3, 5, 0, 1, None, 2]   (version 1 = {5}, 2 = {3, 5}, 3 = {3}, 4 = {}).
Must handle 100000 operations in a few seconds, including long chains where each version is
built on the previous one (copying a version per operation is too slow and uses too much
memory: the grader caps memory at 4 GiB).
''', r'''
import random, time
def _oracle(ops):
    vers = [[]]; out = []
    for op in ops:
        if op[0] == "add":
            vers.append(sorted(vers[op[1]] + [op[2]]))
        elif op[0] == "remove":
            s = list(vers[op[1]])
            if op[2] in s:
                s.remove(op[2])
            vers.append(s)
        elif op[0] == "kth":
            s = vers[op[1]]; k = op[2]
            out.append(s[k - 1] if 1 <= k <= len(s) else None)
        else:
            out.append(sum(1 for e in vers[op[1]] if op[2] <= e <= op[3]))
    return out
ex = [("add", 0, 5), ("add", 1, 3), ("kth", 2, 1), ("kth", 1, 1), ("count", 0, 0, 10),
      ("remove", 2, 5), ("count", 3, 0, 10), ("kth", 3, 2), ("remove", 0, 7), ("count", 2, 3, 5)]
assert persistent_multiset(ex) == [3, 5, 0, 1, None, 2]
assert persistent_multiset([]) == []
assert persistent_multiset([("kth", 0, 1), ("count", 0, -10**9, 10**9), ("remove", 0, 4), ("kth", 1, 0)]) == [None, 0, None]
assert persistent_multiset([("add", 0, 2), ("add", 1, 2), ("remove", 2, 2), ("count", 2, 2, 2), ("count", 3, 2, 2), ("count", 3, 3, 1), ("kth", 2, 2), ("kth", 3, 2), ("kth", 2, -1)]) == [2, 1, 0, 2, None, None]
assert persistent_multiset([("add", 0, -10**9), ("add", 0, 10**9), ("kth", 1, 1), ("kth", 2, 1), ("count", 1, 0, 10**9)]) == [-10**9, 10**9, 0]
random.seed(3016)
for _ in range(400):
    ops = []; nv = 0
    for _ in range(random.randint(0, 30)):
        r = random.random(); v = random.randint(0, nv)
        if r < 0.35:
            ops.append(("add", v, random.randint(-4, 4))); nv += 1
        elif r < 0.55:
            ops.append(("remove", v, random.randint(-4, 4))); nv += 1
        elif r < 0.75:
            ops.append(("kth", v, random.randint(-1, 6)))
        else:
            a = random.randint(-5, 5); ops.append(("count", v, a, a + random.randint(-2, 6)))
    assert persistent_multiset(ops) == _oracle(ops), ops
t0 = time.perf_counter()
ops = []; nv = 0; vals = []
for _ in range(100000):
    r = random.random()
    v = nv if r < 0.7 else random.randint(0, nv)
    if r < 0.6:
        x = random.randint(-10**9, 10**9); vals.append(x); ops.append(("add", v, x)); nv += 1
    elif r < 0.7:
        ops.append(("remove", v, random.choice(vals) if vals else 0)); nv += 1
    elif r < 0.85:
        ops.append(("kth", v, random.randint(1, 60000)))
    else:
        a = random.randint(-10**9, 10**9); ops.append(("count", v, a, a + random.randint(0, 10**9)))
ops.append(("count", nv, -10**9, 10**9))
res = persistent_multiset(ops)
assert len(res) == sum(1 for o in ops if o[0] in ("kth", "count"))
assert 0 < res[-1] <= sum(1 for o in ops if o[0] == "add")
assert time.perf_counter() - t0 < 10.0
''', r'''
from bisect import bisect_left, bisect_right


def persistent_multiset(ops):
    xs = sorted({op[2] for op in ops if op[0] in ("add", "remove")})
    size = max(1, len(xs))
    pos = {x: i for i, x in enumerate(xs)}
    L = [0]; R = [0]; C = [0]

    def upd(node, lo, hi, p, d):
        nid = len(C)
        L.append(L[node]); R.append(R[node]); C.append(C[node] + d)
        if lo != hi:
            mid = (lo + hi) // 2
            if p <= mid:
                L[nid] = upd(L[node], lo, mid, p, d)
            else:
                R[nid] = upd(R[node], mid + 1, hi, p, d)
        return nid

    def leaf(node, p):
        lo, hi = 0, size - 1
        while lo != hi and node:
            mid = (lo + hi) // 2
            if p <= mid:
                node, hi = L[node], mid
            else:
                node, lo = R[node], mid + 1
        return C[node]

    def below(node, r):  # elements with index < r
        lo, hi = 0, size - 1; t = 0
        while node and r > lo:
            if r > hi:
                return t + C[node]
            mid = (lo + hi) // 2
            if r > mid + 1:
                t += C[L[node]]; node, lo = R[node], mid + 1
            else:
                node, hi = L[node], mid
        return t

    roots = [0]; out = []
    for op in ops:
        kind = op[0]
        if kind == "add":
            roots.append(upd(roots[op[1]], 0, size - 1, pos[op[2]], 1))
        elif kind == "remove":
            root = roots[op[1]]
            if leaf(root, pos[op[2]]) > 0:
                root = upd(root, 0, size - 1, pos[op[2]], -1)
            roots.append(root)
        elif kind == "kth":
            node = roots[op[1]]; k = op[2]
            if k < 1 or k > C[node]:
                out.append(None); continue
            lo, hi = 0, size - 1
            while lo != hi:
                mid = (lo + hi) // 2
                if C[L[node]] >= k:
                    node, hi = L[node], mid
                else:
                    k -= C[L[node]]; node, lo = R[node], mid + 1
            out.append(xs[lo])
        else:
            a, b = op[2], op[3]
            if a > b:
                out.append(0); continue
            root = roots[op[1]]
            out.append(below(root, bisect_right(xs, b)) - below(root, bisect_left(xs, a)))
    return out
''')


task("v3_17_path_max_edge", r'''
Write `path_max(n: int, edges: list[tuple[int, int, int]], queries: list[tuple[int, int]]) -> list[tuple[int, int] | None]`.
The input is a tree with vertices 0..n-1 (n >= 1, exactly n-1 undirected edges, connected);
edges[i] = (u, v, w) is the edge with index i and integer weight w (may be negative or zero).
For each query (a, b), in order, return:
- None if a == b;
- otherwise (W, i): W is the largest weight among the edges on the unique path from a to b,
  and i is the smallest edge index among the edges on that path whose weight is W.
Example: n=4, edges [(0,1,5), (1,2,5), (1,3,7)], queries [(0,2), (2,3), (3,3), (0,1)]
-> [(5, 0), (7, 2), None, (5, 0)].
Must handle n = 50000 and 50000 queries in a few seconds, including a path-shaped tree (deep
recursion will overflow the Python stack; walking each path edge by edge is too slow).
''', r'''
import random, time
def _oracle(n, edges, queries):
    adj = [[] for _ in range(n)]
    for i, (u, v, w) in enumerate(edges):
        adj[u].append((v, i)); adj[v].append((u, i))
    out = []
    for a, b in queries:
        if a == b:
            out.append(None); continue
        par = {a: None}; todo = [a]
        while todo:
            x = todo.pop()
            for y, i in adj[x]:
                if y not in par:
                    par[y] = (x, i); todo.append(y)
        ids = []; x = b
        while x != a:
            x, i = par[x]; ids.append(i)
        W = max(edges[i][2] for i in ids)
        out.append((W, min(i for i in ids if edges[i][2] == W)))
    return out
assert path_max(1, [], [(0, 0)]) == [None]
assert path_max(2, [(1, 0, -3)], [(0, 1), (1, 0), (1, 1)]) == [(-3, 0), (-3, 0), None]
assert path_max(4, [(0, 1, 5), (1, 2, 5), (1, 3, 7)], [(0, 2), (2, 3), (3, 3), (0, 1)]) == [(5, 0), (7, 2), None, (5, 0)]
assert path_max(5, [(3, 4, 2), (2, 3, 2), (1, 2, 1), (0, 1, 2)], [(0, 4), (1, 2), (4, 1), (0, 2)]) == [(2, 0), (1, 2), (2, 0), (2, 3)]
assert path_max(5, [(0, 1, 0), (0, 2, 0), (0, 3, 0), (3, 4, 0)], [(4, 1), (2, 4), (4, 3), (1, 2)]) == [(0, 0), (0, 1), (0, 3), (0, 0)]
random.seed(3017)
for _ in range(500):
    n = random.randint(1, 10)
    edges = [(random.randrange(i), i) for i in range(1, n)]
    perm = list(range(n)); random.shuffle(perm)
    edges = [((perm[a], perm[b]) if random.random() < 0.5 else (perm[b], perm[a])) + (random.randint(-2, 2),) for a, b in edges]
    random.shuffle(edges)
    queries = [(random.randrange(n), random.randrange(n)) for _ in range(8)]
    assert path_max(n, edges, queries) == _oracle(n, edges, queries), (n, edges, queries)
t0 = time.perf_counter()
n = 50000
edges = [(i, i + 1, 1) for i in range(n - 1)]
r = path_max(n, edges, [(0, n - 1), (n - 1, 1), (5, 6)] * 1000)
assert r[:3] == [(1, 0), (1, 1), (1, 5)]
edges = [(random.randrange(i), i, random.randint(-10**9, 10**9)) for i in range(1, n)]
queries = [(random.randrange(n), random.randrange(n)) for _ in range(50000)]
r = path_max(n, edges, queries)
assert len(r) == 50000 and all(x is None or edges[x[1]][2] == x[0] for x in r)
assert time.perf_counter() - t0 < 10.0
''', r'''
def path_max(n, edges, queries):
    M = max(n, 1)
    NEG = -(1 << 200)
    adj = [[] for _ in range(n)]
    for i, (u, v, w) in enumerate(edges):
        k = w * M - i
        adj[u].append((v, k)); adj[v].append((u, k))
    parent = [0] * n; depth = [0] * n; key = [NEG] * n
    seen = [False] * n; seen[0] = True; order = [0]
    for x in order:
        for y, k in adj[x]:
            if not seen[y]:
                seen[y] = True; parent[y] = x; depth[y] = depth[x] + 1; key[y] = k; order.append(y)
    LOG = max(1, (n - 1).bit_length())
    up = [parent]; mx = [key]
    for _ in range(1, LOG):
        pu, pm = up[-1], mx[-1]
        up.append([pu[pu[v]] for v in range(n)])
        mx.append([pm[v] if pm[v] > pm[pu[v]] else pm[pu[v]] for v in range(n)])
    out = []
    for a, b in queries:
        if a == b:
            out.append(None); continue
        best = NEG
        if depth[a] < depth[b]:
            a, b = b, a
        d = depth[a] - depth[b]; j = 0
        while d:
            if d & 1:
                if mx[j][a] > best:
                    best = mx[j][a]
                a = up[j][a]
            d >>= 1; j += 1
        if a != b:
            for j in range(LOG - 1, -1, -1):
                ua, ub = up[j][a], up[j][b]
                if ua != ub:
                    best = max(best, mx[j][a], mx[j][b]); a, b = ua, ub
            best = max(best, mx[0][a], mx[0][b])
        i = (-best) % M
        out.append(((best + i) // M, i))
    return out
''')


task("v3_18_steiner_tree", r'''
Write `steiner(n: int, edges: list[tuple[int, int, int]], terminals: list[int]) -> int | None`.
The undirected graph has vertices 0..n-1 and edges (u, v, w) with integer weight w >= 1;
parallel edges and self-loops are allowed, and the graph may be disconnected. terminals is a
list of 1 to 7 distinct vertices. Return the minimum total weight of a set of edges that
connects all terminals to each other (the edges may also use non-terminal vertices), or None
if the terminals cannot all be connected. With a single terminal the answer is 0.
Example: n=4, edges [(0,1,1), (0,2,1), (0,3,1), (1,2,3), (2,3,3), (1,3,3)], terminals [1,2,3]
-> 3 (the star through vertex 0 beats any two of the direct edges, which cost 6).
n=3, edges [(0,1,1)], terminals [0, 2] -> None.
Must handle n = 50, 300 edges and 7 terminals in a few seconds (trying all vertex subsets is
far too slow, and a minimum spanning tree over terminal-to-terminal shortest paths is not
always optimal).
''', r'''
import random, time
def _oracle(n, edges, terms):
    best = None
    for m in range(1 << len(edges)):
        p = list(range(n)); cost = 0
        def f(x):
            while p[x] != x:
                x = p[x]
            return x
        for i, (u, v, w) in enumerate(edges):
            if m >> i & 1:
                cost += w; p[f(u)] = f(v)
        if len({f(t) for t in terms}) == 1 and (best is None or cost < best):
            best = cost
    return best
assert steiner(1, [], [0]) == 0
assert steiner(3, [(0, 1, 4)], [2]) == 0
assert steiner(3, [(0, 1, 1)], [0, 2]) is None
assert steiner(3, [(0, 1, 1), (1, 2, 1), (0, 2, 3)], [0, 2]) == 2
assert steiner(4, [(0, 1, 1), (0, 2, 1), (0, 3, 1), (1, 2, 3), (2, 3, 3), (1, 3, 3)], [1, 2, 3]) == 3
assert steiner(2, [(0, 1, 5), (0, 1, 2), (1, 1, 1)], [1, 0]) == 2
assert steiner(7, [(0, 1, 2), (1, 2, 2), (2, 3, 2), (3, 0, 2), (4, 0, 1), (4, 1, 1), (4, 2, 1), (4, 3, 1), (5, 6, 1)], [0, 1, 2, 3]) == 4
random.seed(3018)
for _ in range(400):
    n = random.randint(1, 6)
    edges = [(random.randrange(n), random.randrange(n), random.randint(1, 5)) for _ in range(random.randint(0, 9))]
    terms = random.sample(range(n), random.randint(1, min(n, 4)))
    assert steiner(n, edges, terms) == _oracle(n, edges, terms), (n, edges, terms)
t0 = time.perf_counter()
for _ in range(3):
    n = 50
    edges = [(random.randrange(i), i, random.randint(1, 100)) for i in range(1, n)]
    edges += [(random.randrange(n), random.randrange(n), random.randint(1, 100)) for _ in range(300 - len(edges))]
    terms = random.sample(range(n), 7)
    r = steiner(n, edges, terms)
    assert isinstance(r, int) and 0 < r <= sum(w for _, _, w in edges)
assert time.perf_counter() - t0 < 10.0
''', r'''
import heapq


def steiner(n, edges, terminals):
    k = len(terminals)
    if k <= 1:
        return 0
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        if u != v:
            adj[u].append((v, w)); adj[v].append((u, w))
    INF = float("inf")
    full = (1 << k) - 1
    dp = [[INF] * n for _ in range(1 << k)]
    for i, t in enumerate(terminals):
        dp[1 << i][t] = 0
    for mask in range(1, full + 1):
        d = dp[mask]
        sub = (mask - 1) & mask
        while sub:
            if sub < (mask ^ sub):
                a = dp[sub]; b = dp[mask ^ sub]
                for v in range(n):
                    s = a[v] + b[v]
                    if s < d[v]:
                        d[v] = s
            sub = (sub - 1) & mask
        pq = [(d[v], v) for v in range(n) if d[v] < INF]
        heapq.heapify(pq)
        while pq:
            dv, v = heapq.heappop(pq)
            if dv > d[v]:
                continue
            for y, w in adj[v]:
                if dv + w < d[y]:
                    d[y] = dv + w; heapq.heappush(pq, (d[y], y))
    r = min(dp[full])
    return None if r == INF else r
''')


task("v3_19_min_mean_cycle", r'''
Write `min_mean_cycle(n: int, edges: list[tuple[int, int, int]]) -> Fraction | None`.
The directed graph has vertices 0..n-1 and edges (u, v, w) with integer weights (any sign).
Parallel edges are allowed and self-loops are allowed (a self-loop is a cycle of one edge).
The mean of a directed cycle is its total weight divided by its number of edges. Return the
minimum mean over all directed cycles as a fractions.Fraction (exact, so no floats), or None
if the graph has no directed cycle.
Example: n=2, edges [(0,1,1), (1,0,2)] -> Fraction(3, 2).
n=3, edges [(0,1,1), (1,2,1), (2,0,1), (0,0,5)] -> Fraction(1, 1).
Must handle n = 150 and 1500 edges in a few seconds (enumerating cycles is far too slow).
''', r'''
import random, time
from fractions import Fraction
def _oracle(n, edges):
    w = {}
    for u, v, c in edges:
        if (u, v) not in w or c < w[(u, v)]:
            w[(u, v)] = c
    best = None
    for s in range(n):
        stack = [(s, [s], 0)]
        while stack:
            x, path, tot = stack.pop()
            for y in range(s, n):
                if (x, y) not in w:
                    continue
                if y == s:
                    val = Fraction(tot + w[(x, y)], len(path))
                    if best is None or val < best:
                        best = val
                elif y not in path:
                    stack.append((y, path + [y], tot + w[(x, y)]))
    return best
def chk(n, edges, want):
    r = min_mean_cycle(n, edges)
    assert r == want and (want is None or isinstance(r, Fraction)), (n, edges, r, want)
chk(1, [], None)
chk(1, [(0, 0, -3)], Fraction(-3))
chk(2, [(0, 1, 1), (1, 0, 2)], Fraction(3, 2))
chk(3, [(0, 1, 1), (1, 2, 1), (2, 0, 1), (0, 0, 5)], Fraction(1))
chk(3, [(0, 1, -5), (1, 2, -5)], None)
chk(2, [(0, 1, 4), (0, 1, 1), (1, 0, 0)], Fraction(1, 2))
chk(5, [(0, 1, 0), (1, 0, 0), (2, 3, -1), (3, 4, -1), (4, 2, 0)], Fraction(-2, 3))
random.seed(3019)
for _ in range(600):
    n = random.randint(1, 6)
    edges = [(random.randrange(n), random.randrange(n), random.randint(-5, 5)) for _ in range(random.randint(0, 10))]
    chk(n, edges, _oracle(n, edges))
t0 = time.perf_counter()
for _ in range(3):
    n = 150
    edges = [(random.randrange(n), random.randrange(n), random.randint(-10**6, 10**6)) for _ in range(1500)]
    r = min_mean_cycle(n, edges)
    assert isinstance(r, Fraction)
n = 150
chk(n, [(i, i + 1, -7) for i in range(n - 1)] + [(n - 1, 0, 6)], Fraction(-7 * (n - 1) + 6, n))
assert time.perf_counter() - t0 < 10.0
''', r'''
from fractions import Fraction


def min_mean_cycle(n, edges):
    d = [[None] * n for _ in range(n + 1)]
    d[0] = [0] * n
    for k in range(1, n + 1):
        prev = d[k - 1]; cur = d[k]
        for u, v, w in edges:
            p = prev[u]
            if p is not None:
                c = p + w
                if cur[v] is None or c < cur[v]:
                    cur[v] = c
    best = None
    for v in range(n):
        dn = d[n][v]
        if dn is None:
            continue
        worst = None
        for k in range(n):
            dk = d[k][v]
            if dk is not None:
                val = Fraction(dn - dk, n - k)
                if worst is None or val > worst:
                    worst = val
        if best is None or worst < best:
            best = worst
    return best
''')


task("v3_20_tree_iso_classes", r'''
Write `iso_classes(trees: list[tuple[int, list[tuple[int, int]]]]) -> list[list[int]]`.
trees[i] = (n, edges) is an unrooted tree on vertices 0..n-1 (n >= 1, exactly n-1 undirected
edges, connected). Two trees are isomorphic if there is a bijection between their vertex sets
that maps edges to edges (so trees with different n are never isomorphic). Partition the
indices 0..len(trees)-1 into isomorphism classes. Return the classes, each as an ascending list
of indices, with the classes sorted by their first index.
Example: trees [(3, [(0,1), (1,2)]), (1, []), (3, [(2,0), (0,1)]), (4, [(0,1), (1,2), (2,3)]),
(4, [(0,1), (0,2), (0,3)])] -> [[0, 2], [1], [3], [4]].
Must handle a total of 200000 vertices in a few seconds, including single trees of 100000
vertices shaped like a path (deep recursion will overflow the Python stack).
''', r'''
import random, time, itertools
def _canon(n, edges):
    best = None
    for p in itertools.permutations(range(n)):
        c = sorted(tuple(sorted((p[a], p[b]))) for a, b in edges)
        if best is None or c < best:
            best = c
    return (n, tuple(best))
def _oracle(trees):
    g = {}
    for i, (n, e) in enumerate(trees):
        g.setdefault(_canon(n, e), []).append(i)
    return sorted(g.values())
def rnd_tree(n):
    e = [(random.randrange(i), i) for i in range(1, n)]
    p = list(range(n)); random.shuffle(p)
    e = [(p[a], p[b]) if random.random() < 0.5 else (p[b], p[a]) for a, b in e]
    random.shuffle(e)
    return (n, e)
assert iso_classes([]) == []
assert iso_classes([(1, [])]) == [[0]]
assert iso_classes([(3, [(0, 1), (1, 2)]), (1, []), (3, [(2, 0), (0, 1)]), (4, [(0, 1), (1, 2), (2, 3)]), (4, [(0, 1), (0, 2), (0, 3)])]) == [[0, 2], [1], [3], [4]]
assert iso_classes([(2, [(0, 1)]), (2, [(1, 0)]), (1, [])]) == [[0, 1], [2]]
assert iso_classes([(6, [(0, 1), (1, 2), (2, 3), (1, 4), (2, 5)]), (6, [(0, 1), (1, 2), (2, 3), (1, 4), (1, 5)]), (6, [(5, 4), (4, 3), (3, 2), (4, 1), (3, 0)])]) == [[0, 2], [1]]
assert iso_classes([(7, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]), (7, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (2, 6)]), (7, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (3, 6)]), (7, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (4, 6)])]) == [[0], [1, 2], [3]]
random.seed(3020)
for _ in range(30):
    trees = [rnd_tree(random.randint(1, 6)) for _ in range(random.randint(1, 12))]
    assert iso_classes(trees) == _oracle(trees), trees
trees = [rnd_tree(7) for _ in range(12)]
assert iso_classes(trees) == _oracle(trees), trees
t0 = time.perf_counter()
n = 100000
big = rnd_tree(n // 2)
p = list(range(n // 2)); random.shuffle(p)
big2 = (n // 2, [(p[b], p[a]) for a, b in reversed(big[1])])
path1 = (n, [(i, i + 1) for i in range(n - 1)])
q = list(range(n)); random.shuffle(q)
path2 = (n, [(q[i + 1], q[i]) for i in range(n - 1)])
star = (n // 2, [(0, i) for i in range(1, n // 2)])
r = iso_classes([path1, big, star, path2, big2])
assert r == [[0, 3], [1, 4], [2]], r
assert time.perf_counter() - t0 < 10.0
''', r'''
def iso_classes(trees):
    canon = {}
    keys = []
    for n, edges in trees:
        adj = [[] for _ in range(n)]
        for a, b in edges:
            adj[a].append(b); adj[b].append(a)
        deg = [len(x) for x in adj]
        removed = [False] * n
        leaves = [v for v in range(n) if deg[v] <= 1]
        rem = n
        while rem > 2:
            rem -= len(leaves); nl = []
            for v in leaves:
                removed[v] = True
            for v in leaves:
                for y in adj[v]:
                    if not removed[y]:
                        deg[y] -= 1
                        if deg[y] == 1:
                            nl.append(y)
            leaves = nl
        labs = []
        for c in leaves:
            parent = [-1] * n; parent[c] = c; order = [c]
            for x in order:
                for y in adj[x]:
                    if parent[y] == -1:
                        parent[y] = x; order.append(y)
            kids = [[] for _ in range(n)]
            root = None
            for v in reversed(order):
                t = tuple(sorted(kids[v]))
                l = canon.get(t)
                if l is None:
                    l = canon[t] = len(canon)
                if v == c:
                    root = l
                else:
                    kids[parent[v]].append(l)
            labs.append(root)
        keys.append(tuple(sorted(labs)))
    groups = {}
    for i, k in enumerate(keys):
        groups.setdefault(k, []).append(i)
    return sorted(groups.values())
''')


task("v3_21_mod_sqrts", r'''
Write `mod_sqrts(a: int, m: int) -> list[int]` returning, in increasing order, every x with
0 <= x < m and x*x ≡ a (mod m). Rules:
- a is any int (negative allowed; reduce it mod m). m < 1 raises ValueError. m == 1 gives [0].
- m can be any modulus up to 10**9: prime, a prime power, or composite, and a need not be
  coprime to m. Examples: mod_sqrts(2, 7) == [3, 4]; mod_sqrts(3, 7) == [];
  mod_sqrts(1, 8) == [1, 3, 5, 7]; mod_sqrts(0, 16) == [0, 4, 8, 12]; mod_sqrts(4, 8) == [2, 6];
  mod_sqrts(9, 27) == [3, 6, 12, 15, 21, 24]; mod_sqrts(-1, 10) == [3, 7].
- Speed: for a prime m near 10**9 the call must take milliseconds, so scanning x is far too
  slow; 300 calls with m up to 10**9 must finish within a few seconds in total.
Do not use sympy, gmpy2 or numpy.
''', r'''
_banned(mods=("sympy", "gmpy2", "numpy"))
import random, time
ms = mod_sqrts
def brute(a, m):
    return [x for x in range(m) if (x * x - a) % m == 0]
assert ms(2, 7) == [3, 4]
assert ms(3, 7) == []
assert ms(1, 8) == [1, 3, 5, 7]
assert ms(0, 16) == [0, 4, 8, 12]
assert ms(4, 8) == [2, 6]
assert ms(9, 27) == [3, 6, 12, 15, 21, 24]
assert ms(-1, 10) == [3, 7]
assert ms(5, 1) == [0]
assert ms(0, 2) == [0] and ms(1, 2) == [1] and ms(3, 2) == [1]
assert ms(0, 1024) == list(range(0, 1024, 32))
assert ms(2, 3) == []
assert ms(12, 72) == brute(12, 72)
for bad in [(1, 0), (1, -7)]:
    try:
        ms(*bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
def is_prime(n):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2; s += 1
    for b in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        x = pow(b, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True
def rand_prime(lo, hi):
    while True:
        n = random.randint(lo, hi)
        if is_prime(n):
            return n
def cnt_prime(a, p):
    a %= p
    if a == 0 or p == 2:
        return 1
    return 2 if pow(a, (p - 1) // 2, p) == 1 else 0
random.seed(3021)
for _ in range(1500):
    m = random.randint(1, 1500)
    a = random.randint(-3000, 3000)
    assert ms(a, m) == brute(a, m), (a, m)
for _ in range(200):
    p = random.choice([2, 3, 5, 7])
    m = p ** random.randint(1, {2: 11, 3: 6, 5: 4, 7: 3}[p])
    r = random.randint(0, m - 1)
    a = (r * r * random.choice([1, p, p * p])) % m + random.choice([0, 0, m])
    assert ms(a, m) == brute(a, m), (a, m)
t0 = time.perf_counter()
for _ in range(100):
    p = rand_prime(9 * 10**8, 10**9)
    r = random.randint(0, p - 1)
    out = ms(r * r + random.choice([0, p, -p]), p)
    assert out == sorted({r, (p - r) % p}), (p, r, out)
    a = random.randint(0, p - 1)
    out = ms(a, p)
    assert len(out) == cnt_prime(a, p) and all((x * x - a) % p == 0 for x in out), (a, p, out)
for _ in range(60):
    p, q = rand_prime(5000, 15000), rand_prime(15001, 30000)
    k = random.choice([1, 4, 8, 9, 12])
    m = p * q * k
    r = random.randint(0, m - 1)
    a = r * r % m
    out = ms(a, m)
    assert r in out and out == sorted(set(out)) and all(0 <= x < m and (x * x - a) % m == 0 for x in out), (a, m)
    assert len(out) == len(brute(a, k)) * cnt_prime(a, p) * cnt_prime(a, q), (a, m, len(out))
for _ in range(20):
    p = rand_prime(20000, 31000)
    s = random.randint(1, p - 1)
    assert ms((p * s) ** 2, p * p) == list(range(0, p * p, p)), p
    assert ms(p * s, p * p) == [], p
assert time.perf_counter() - t0 < 6.0
''', r'''
def _factor(m):
    f = {}
    d = 2
    while d * d <= m:
        while m % d == 0:
            f[d] = f.get(d, 0) + 1
            m //= d
        d += 1 if d == 2 else 2
    if m > 1:
        f[m] = f.get(m, 0) + 1
    return f


def _sqrt_prime(a, p):
    a %= p
    if p == 2 or a == 0:
        return [a] if p == 2 else [0]
    if pow(a, (p - 1) // 2, p) != 1:
        return []
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    mm, c, t, r = s, pow(z, q, p), pow(a, q, p), pow(a, (q + 1) // 2, p)
    while t != 1:
        i, t2 = 0, t
        while t2 != 1:
            t2 = t2 * t2 % p
            i += 1
        b = pow(c, 1 << (mm - i - 1), p)
        mm, c, t, r = i, b * b % p, t * b * b % p, r * b % p
    return sorted({r, p - r})


def _sqrt_pp(a, p, e):
    roots = _sqrt_prime(a, p)
    pk = p
    for _ in range(e - 1):
        nxt = pk * p
        new = []
        for r in roots:
            for t in range(p):
                x = r + t * pk
                if (x * x - a) % nxt == 0:
                    new.append(x)
        roots, pk = new, nxt
    return roots


def mod_sqrts(a, m):
    if m < 1:
        raise ValueError("m must be >= 1")
    if m == 1:
        return [0]
    a %= m
    res, M = [0], 1
    for p, e in _factor(m).items():
        q = p ** e
        rs = _sqrt_pp(a % q, p, e)
        if not rs:
            return []
        inv = pow(M, -1, q)
        res = [r1 + M * ((r2 - r1) * inv % q) for r1 in res for r2 in rs]
        M *= q
    return sorted(res)
''')


task("v3_22_dlog", r'''
Write `dlog(g: int, h: int, m: int) -> int` returning the smallest integer x >= 0 with
pow(g, x, m) == h % m, or -1 if there is none. Rules:
- g and h are any ints (negative allowed; reduce them mod m). m < 1 raises ValueError.
- g**0 is 1 for every g, including 0, so the answer is 0 whenever h ≡ 1 (mod m). With m == 1
  everything is ≡ 0 ≡ 1, so the answer is 0.
- m is any modulus up to 10**10, and g need not be coprime to m or a generator.
  Examples: dlog(3, 13, 17) == 4; dlog(2, 1, 7) == 0; dlog(2, 0, 8) == 3; dlog(2, 0, 7) == -1;
  dlog(0, 0, 5) == 1; dlog(6, 6, 10) == 1; dlog(6, 4, 10) == -1; dlog(2, 4, 12) == 2;
  dlog(-1, 1, 1) == 0.
- Speed: 30 calls with m near 10**10 must finish within a few seconds in total, so trying
  x = 0, 1, 2, ... is far too slow.
Do not use sympy, gmpy2 or numpy.
''', r'''
_banned(mods=("sympy", "gmpy2", "numpy"))
import random, time
def brute(g, h, m):
    h %= m
    v = 1 % m
    for x in range(m + 64):
        if v == h:
            return x
        v = v * g % m
    return -1
assert dlog(3, 13, 17) == 4
assert dlog(2, 1, 7) == 0
assert dlog(2, 0, 8) == 3
assert dlog(2, 0, 7) == -1
assert dlog(0, 0, 5) == 1
assert dlog(0, 1, 5) == 0
assert dlog(0, 3, 5) == -1
assert dlog(6, 6, 10) == 1
assert dlog(6, 4, 10) == -1
assert dlog(2, 4, 12) == 2
assert dlog(2, 16, 12) == 2
assert dlog(-1, 1, 1) == 0
assert dlog(5, 7, 1) == 0
assert dlog(-2, 4, 7) == 2
assert dlog(3, -1, 7) == 3
assert dlog(2, 2**40 % (3 * 2**35), 3 * 2**35) == brute(2, 2**40, 3 * 2**35)
for bad in [(2, 3, 0), (2, 3, -5)]:
    try:
        dlog(*bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
random.seed(3022)
for _ in range(3000):
    m = random.randint(1, 300)
    g, h = random.randint(-400, 400), random.randint(-400, 400)
    if random.random() < 0.5:
        h = pow(g, random.randint(0, 40), m) + random.choice([0, m, -m])
    assert dlog(g, h, m) == brute(g, h, m), (g, h, m)
t0 = time.perf_counter()
for _ in range(25):
    m = random.choice([random.randint(10**9, 10**10), 2**random.randint(10, 20) * random.randint(10**3, 10**4)])
    g = random.randint(2, m - 1)
    x0 = random.randint(0, m)
    h = pow(g, x0, m)
    r = dlog(g, h, m)
    assert 0 <= r <= x0 and pow(g, r, m) == h, (g, h, m, x0, r)
for p in (9999999967, 9999999943, 9999999929):
    s = random.randint(2, p - 2)
    g = s * s % p
    n = random.randint(2, p - 1)
    while pow(n, (p - 1) // 2, p) == 1:
        n += 1
    assert dlog(g, n, p) == -1, (g, n, p)
    x0 = random.randint(0, p)
    r = dlog(g, pow(g, x0, p), p)
    assert 0 <= r <= x0 and pow(g, r, p) == pow(g, x0, p)
for _ in range(5):
    g, x0 = random.randint(2, 50), random.randint(0, 500)
    m = g ** 3 * random.randint(10**5, 10**6)
    h = pow(g, x0, m)
    r = dlog(g, h, m)
    assert 0 <= r <= x0 and pow(g, r, m) == h, (g, h, m, x0, r)
assert time.perf_counter() - t0 < 8.0
''', r'''
from math import gcd, isqrt


def dlog(g, h, m):
    if m < 1:
        raise ValueError("m must be >= 1")
    g %= m
    h %= m
    v = 1 % m
    for x in range(64):
        if v == h:
            return x
        v = v * g % m
    cnt, k = 0, 1 % m
    while True:
        d = gcd(g, m)
        if d == 1:
            break
        if h % d:
            return -1
        h //= d
        m //= d
        k = k * (g // d) % m
        cnt += 1
    if m == 1:
        return cnt
    n = isqrt(m) + 1
    table = {}
    cur = h % m
    for j in range(n):
        table[cur] = j
        cur = cur * g % m
    gn = pow(g, n, m)
    cur = k % m
    for i in range(1, n + 2):
        cur = cur * gn % m
        if cur in table:
            return i * n - table[cur] + cnt
    return -1
''')


task("v3_23_pell", r'''
Write two functions.

`sqrt_cf(n: int) -> tuple[int, list[int]]` returns the continued fraction of sqrt(n) for an
integer n >= 0 as (a0, period), where period is the shortest repeating block of partial
quotients after a0. For a perfect square it is (isqrt(n), []). n < 0 raises ValueError.
Examples: sqrt_cf(2) == (1, [2]); sqrt_cf(14) == (3, [1, 2, 1, 6]); sqrt_cf(16) == (4, []);
sqrt_cf(0) == (0, []).

`pell(n: int, c: int) -> tuple[int, int] | None` returns the solution of x*x - n*y*y == c in
positive integers x, y with the smallest y, or None if there is no such solution. c must be
1 or -1, and n must be a positive integer that is not a perfect square; anything else raises
ValueError. Examples: pell(2, 1) == (3, 2); pell(2, -1) == (1, 1); pell(3, -1) is None;
pell(13, -1) == (18, 5); pell(61, 1) == (1766319049, 226153980).

n goes up to 10**6, where the answer can have hundreds of digits; 60 calls of each function
with n near 10**6 must take at most a few seconds in total. No floats (they lose precision),
and do not use sympy, gmpy2, decimal or fractions.
''', r'''
_banned(mods=("sympy", "gmpy2", "decimal", "_pydecimal", "fractions"))
import random, time
from math import isqrt
assert sqrt_cf(2) == (1, [2])
assert sqrt_cf(3) == (1, [1, 2])
assert sqrt_cf(14) == (3, [1, 2, 1, 6])
assert sqrt_cf(16) == (4, [])
assert sqrt_cf(0) == (0, [])
assert sqrt_cf(1) == (1, [])
assert sqrt_cf(13) == (3, [1, 1, 1, 1, 6])
assert sqrt_cf(61)[1][-1] == 14 and len(sqrt_cf(61)[1]) == 11
assert pell(2, 1) == (3, 2)
assert pell(2, -1) == (1, 1)
assert pell(3, 1) == (2, 1)
assert pell(3, -1) is None
assert pell(5, -1) == (2, 1)
assert pell(5, 1) == (9, 4)
assert pell(13, -1) == (18, 5)
assert pell(13, 1) == (649, 180)
assert pell(61, 1) == (1766319049, 226153980)
assert pell(61, -1) == (29718, 3805)
assert pell(34, -1) is None
assert pell(10, -1) == (3, 1)
for bad in [lambda: sqrt_cf(-1), lambda: pell(4, 1), lambda: pell(0, 1), lambda: pell(-3, 1),
            lambda: pell(2, 2), lambda: pell(2, 0), lambda: pell(1, -1)]:
    try:
        bad()
        assert False, "expected ValueError"
    except ValueError:
        pass
def cf_rat(p, q, k):
    out = []
    while q and len(out) < k:
        a = p // q
        out.append(a)
        p, q = q, p - a * q
    return out
def check_cf(n, a0, per, D):
    s = isqrt(n * 10**(2 * D))
    lo, hi = cf_rat(s, 10**D, 10**6), cf_rat(s + 1, 10**D, 10**6)
    common = []
    for u, v in zip(lo, hi):
        if u != v:
            break
        common.append(u)
    common = common[:-1]
    r = isqrt(n)
    if r * r == n:
        assert (a0, per) == (r, []), n
        return
    assert a0 == r and per and per[-1] == 2 * a0 and 2 * a0 not in per[:-1], (n, per[:5])
    assert len(common) > 2 * len(per) + 1, (n, len(common), len(per))
    gen = [a0] + per * (len(common) // len(per) + 1)
    assert gen[:len(common)] == common, n
def brute_pell(n, c, ymax):
    for y in range(1, ymax + 1):
        v = n * y * y + c
        if v > 0:
            x = isqrt(v)
            if x * x == v:
                return (x, y)
    return None
random.seed(3023)
for _ in range(150):
    n = random.randint(0, 3000)
    a0, per = sqrt_cf(n)
    check_cf(n, a0, per, 1200)
for _ in range(150):
    n = random.randint(2, 3000)
    if isqrt(n) ** 2 == n:
        continue
    x1, y1 = pell(n, 1)
    assert x1 > 0 and y1 > 0 and x1 * x1 - n * y1 * y1 == 1, n
    b = brute_pell(n, 1, min(y1, 4000))
    assert b == (x1, y1) if y1 <= 4000 else b is None, (n, x1, y1)
    m = pell(n, -1)
    if m is None:
        if y1 <= 4000:
            assert brute_pell(n, -1, y1) is None, n
    else:
        a, bb = m
        assert a > 0 and bb > 0 and a * a - n * bb * bb == -1, n
        assert a * a + n * bb * bb == x1 and 2 * a * bb == y1, n
t0 = time.perf_counter()
for _ in range(60):
    n = random.randint(9 * 10**5, 10**6)
    if isqrt(n) ** 2 == n:
        n += 1
    a0, per = sqrt_cf(n)
    x1, y1 = pell(n, 1)
    assert x1 * x1 - n * y1 * y1 == 1 and x1 > 0 and y1 > 0
    m = pell(n, -1)
    assert (m is None) == (len(per) % 2 == 0), n
    if m:
        assert m[0] ** 2 - n * m[1] ** 2 == -1 and m[0] ** 2 + n * m[1] ** 2 == x1, n
assert time.perf_counter() - t0 < 6.0
''', r'''
from math import isqrt


def sqrt_cf(n):
    if n < 0:
        raise ValueError("n must be >= 0")
    a0 = isqrt(n)
    if a0 * a0 == n:
        return (a0, [])
    per = []
    m, d, a = 0, 1, a0
    while a != 2 * a0:
        m = d * a - m
        d = (n - m * m) // d
        a = (a0 + m) // d
        per.append(a)
    return (a0, per)


def pell(n, c):
    if c not in (1, -1) or n < 1 or isqrt(n) ** 2 == n:
        raise ValueError("bad input")
    a0, per = sqrt_cf(n)
    L = len(per)
    if c == -1 and L % 2 == 0:
        return None
    k = L if (c == -1 or L % 2 == 0) else 2 * L
    p0, q0, p1, q1 = 1, 0, a0, 1
    for i in range(k - 1):
        a = per[i % L]
        p0, q0, p1, q1 = p1, q1, a * p1 + p0, a * q1 + q0
    return (p1, q1)
''')


task("v3_24_clip_area", r'''
Write `clip_area(subject, clip)` returning the exact area of the intersection of the polygon
`subject` with the convex polygon `clip`, as a fractions.Fraction. Rules:
- Both are lists of (x, y) integer vertex tuples in order, in either orientation (clockwise or
  counter-clockwise). Both are guaranteed simple (no self-intersections). subject may be
  concave; clip may have collinear consecutive vertices.
- Raise ValueError if either polygon has fewer than 3 vertices or zero area, or if clip is not
  convex: the cross products of consecutive edge pairs (including the wrap-around pairs) must
  not include both a positive and a negative value.
- Shared edges and touching points contribute 0. The result is a Fraction >= 0 (an
  integer-valued result still compares equal, e.g. == 4).
Examples:
clip_area([(0,0),(4,0),(4,4),(0,4)], [(2,2),(6,2),(6,6),(2,6)]) == 4
clip_area([(0,0),(4,0),(0,4)], [(1,0),(3,0),(3,2),(1,2)]) == Fraction(7, 2)
clip_area([(0,0),(6,0),(6,4),(4,4),(4,1),(2,1),(2,4),(0,4)], [(1,0),(5,0),(5,3),(1,3)]) == 8
''', r'''
_banned(mods=("shapely", "numpy", "sympy"))
import random, math
from fractions import Fraction as F
def area2(P):
    return sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
def bad(s, c):
    try:
        clip_area(s, c)
    except ValueError:
        return True
    return False
sq = [(0, 0), (4, 0), (4, 4), (0, 4)]
assert clip_area(sq, [(2, 2), (6, 2), (6, 6), (2, 6)]) == 4
assert clip_area(sq, [(2, 6), (6, 6), (6, 2), (2, 2)]) == 4
assert clip_area(sq[::-1], [(2, 2), (6, 2), (6, 6), (2, 6)]) == 4
assert clip_area([(0, 0), (4, 0), (0, 4)], [(1, 0), (3, 0), (3, 2), (1, 2)]) == F(7, 2)
assert clip_area([(0, 0), (4, 0), (0, 4)], [(1, 0), (3, 0), (3, 3), (1, 3)]) == 4
U = [(0, 0), (6, 0), (6, 4), (4, 4), (4, 1), (2, 1), (2, 4), (0, 4)]
assert clip_area(U, [(1, 0), (5, 0), (5, 3), (1, 3)]) == 8
assert clip_area(U, [(1, 2), (5, 2), (5, 3), (1, 3)]) == 2
assert clip_area(sq, [(4, 0), (8, 0), (8, 4), (4, 4)]) == 0
assert clip_area(sq, [(5, 5), (9, 5), (9, 9)]) == 0
assert clip_area(sq, [(-1, -1), (9, -1), (9, 9), (-1, 9)]) == 16
assert clip_area([(1, 1), (2, 1), (2, 2)], sq) == F(1, 2)
assert clip_area(sq, [(0, 0), (2, 0), (4, 0), (4, 4), (0, 4)]) == 16
assert clip_area([(0, 0), (3, 0), (0, 3)], [(0, 0), (3, 0), (3, 3), (0, 3)]) == F(9, 2)
assert isinstance(clip_area([(0, 0), (3, 0), (0, 1)], [(0, 0), (5, 0), (5, 5), (0, 5)]), F)
assert bad([(0, 0), (1, 0)], sq)
assert bad(sq, [(0, 0), (1, 1)])
assert bad([(0, 0), (1, 1), (2, 2)], sq)
assert bad(sq, [(0, 0), (1, 1), (3, 3)])
assert bad(sq, [(0, 0), (4, 0), (4, 4), (2, 1), (0, 4)])
def cross_xs(A, B):
    xs = set()
    for i in range(len(A)):
        p, q = A[i], A[(i + 1) % len(A)]
        for j in range(len(B)):
            r, s = B[j], B[(j + 1) % len(B)]
            d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
            if d == 0:
                continue
            t = F((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0]), d)
            u = F((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0]), d)
            if 0 <= t <= 1 and 0 <= u <= 1:
                xs.add(p[0] + t * (q[0] - p[0]))
    return xs
def section(P, X):
    ys = []
    for i in range(len(P)):
        p, q = P[i], P[(i + 1) % len(P)]
        if min(p[0], q[0]) < X < max(p[0], q[0]):
            ys.append(p[1] + (X - p[0]) * F(q[1] - p[1], q[0] - p[0]))
    ys.sort()
    return [(ys[k], ys[k + 1]) for k in range(0, len(ys), 2)]
def oracle(A, B):
    xs = sorted({F(p[0]) for p in A} | {F(p[0]) for p in B} | cross_xs(A, B))
    tot = F(0)
    for x0, x1 in zip(xs, xs[1:]):
        X = (x0 + x1) / 2
        L = 0
        for a, b in section(A, X):
            for c, d in section(B, X):
                L += max(0, min(b, d) - max(a, c))
        tot += (x1 - x0) * L
    return tot
def hull(pts):
    pts = sorted(set(pts))
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(pts), half(pts[::-1])
    return lo[:-1] + up[:-1]
def star(k, R):
    while True:
        pts = list({(random.randint(-R, R), random.randint(-R, R)) for _ in range(k)})
        if len(pts) < 3:
            continue
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        ang = [math.atan2(p[1] - cy, p[0] - cx) for p in pts]
        gaps = [ang[i + 1] - ang[i] for i in range(len(ang) - 1)] + [ang[0] + 2 * math.pi - ang[-1]]
        if min(gaps) < 1e-9 or max(gaps) >= math.pi - 1e-9 or area2(pts) == 0:
            continue
        return pts
random.seed(3024)
for _ in range(400):
    S = star(random.randint(3, 9), random.choice([3, 6, 10]))
    while True:
        C = hull([(random.randint(-8, 8), random.randint(-8, 8)) for _ in range(random.randint(3, 8))])
        if len(C) >= 3 and area2(C) != 0:
            break
    if random.random() < 0.5:
        S = S[::-1]
    if random.random() < 0.5:
        C = C[::-1]
    k = random.randrange(len(C))
    C = C[k:] + C[:k]
    exp = oracle(S, C)
    got = clip_area(S, C)
    assert got == exp, (S, C, got, exp)
''', r'''
from fractions import Fraction


def _area2(P):
    n = len(P)
    return sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n))


def clip_area(subject, clip):
    if len(subject) < 3 or len(clip) < 3 or _area2(subject) == 0 or _area2(clip) == 0:
        raise ValueError("degenerate polygon")
    n = len(clip)
    signs = set()
    for i in range(n):
        a, b, c = clip[i], clip[(i + 1) % n], clip[(i + 2) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cr:
            signs.add(cr > 0)
    if len(signs) > 1:
        raise ValueError("clip not convex")
    if _area2(clip) < 0:
        clip = clip[::-1]
    out = [(Fraction(x), Fraction(y)) for x, y in subject]
    for i in range(n):
        a, b = clip[i], clip[(i + 1) % n]
        if a == b:
            continue
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        inp, out = out, []
        if not inp:
            break
        for j in range(len(inp)):
            p, q = inp[j - 1], inp[j]
            sp, sq = side(p), side(q)
            if sq >= 0:
                if sp < 0:
                    t = sp / (sp - sq)
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                out.append(q)
            elif sp >= 0:
                if sp > 0:
                    t = sp / (sp - sq)
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    if len(out) < 3:
        return Fraction(0)
    return abs(Fraction(_area2(out)) / 2)
''')


task("v3_25_hist_calendar", r'''
Write `hist_add(date: str, days: int, switch: str) -> str` doing date arithmetic in the
calendar of a country that moved from the Julian to the Gregorian calendar.
- `switch` is the first day on the Gregorian calendar, a valid Gregorian date "YYYY-MM-DD"
  from 1582-10-15 to 1929-12-31 inclusive (else ValueError). The day before it is the Julian
  date of the previous physical day: switch "1582-10-15" follows Julian 1582-10-04, switch
  "1752-09-14" follows Julian 1752-09-02, switch "1918-02-14" follows Julian 1918-01-31.
- Julian leap years: every year divisible by 4. Gregorian: divisible by 4, except centuries
  not divisible by 400. Both are proleptic; years run from 1 to 9999.
- A date label is valid if it is a valid Julian date no later than the last Julian day, or a
  valid Gregorian date no earlier than switch. Labels in the gap are invalid (e.g.
  "1752-09-05" with switch "1752-09-14"), and so is "1900-02-29" if 1900 is on the Gregorian
  side, while "1700-02-29" is valid when 1700-02-29 Julian is before the switch.
- Format: exactly 4-digit year, 2-digit month, 2-digit day, zero-padded, joined by "-".
  Anything else (wrong format, year 0000, invalid date) raises ValueError, for date and switch.
- Return the label of the day `days` days after `date` (before it if days < 0), in the same
  format. Raise ValueError if the result is before Julian 0001-01-01 or after 9999-12-31.
Examples:
hist_add("1752-09-02", 1, "1752-09-14") == "1752-09-14"
hist_add("1752-09-14", -1, "1752-09-14") == "1752-09-02"
hist_add("1700-02-28", 1, "1752-09-14") == "1700-02-29"
hist_add("1700-02-28", 1, "1582-10-15") == "1700-03-01"
hist_add("1918-01-31", 1, "1918-02-14") == "1918-02-14"
Do not use the datetime, calendar, time or dateutil modules.
''', r'''
_banned(mods=("datetime", "_datetime", "_pydatetime", "calendar", "time", "dateutil", "_strptime"))
import random, datetime
CUM = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
ML = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
def jul_raw(y, m, d):
    return 365 * (y - 1) + (y - 1) // 4 + CUM[m] + (1 if m > 2 and y % 4 == 0 else 0) + d
OFF = datetime.date(1582, 10, 15).toordinal() - jul_raw(1582, 10, 5)
def jul_ord(y, m, d):
    return jul_raw(y, m, d) + OFF
def jul_valid(y, m, d):
    return 1 <= y <= 9999 and 1 <= m <= 12 and 1 <= d <= ML[m] + (1 if m == 2 and y % 4 == 0 else 0)
def jul_from(o):
    y = max(1, (o - OFF) * 4 // 1461 - 1)
    while jul_ord(y + 1, 1, 1) <= o:
        y += 1
    m = 1
    while m < 12 and jul_ord(y, m + 1, 1) <= o:
        m += 1
    return (y, m, o - jul_ord(y, m, 1) + 1)
def lab(t):
    return "%04d-%02d-%02d" % t
def g_ord(t):
    return datetime.date(*t).toordinal()
def oracle(date, days, sw):
    S = g_ord(sw)
    y, m, d = date
    try:
        go = datetime.date(y, m, d).toordinal()
    except ValueError:
        go = None
    if go is not None and go >= S:
        o = go
    elif jul_valid(y, m, d) and jul_ord(y, m, d) < S:
        o = jul_ord(y, m, d)
    else:
        return "ValueError"
    o += days
    if o < jul_ord(1, 1, 1) or o > datetime.date(9999, 12, 31).toordinal():
        return "ValueError"
    if o >= S:
        dd = datetime.date.fromordinal(o)
        return lab((dd.year, dd.month, dd.day))
    return lab(jul_from(o))
def call(*a):
    try:
        return hist_add(*a)
    except ValueError:
        return "ValueError"
assert hist_add("1752-09-02", 1, "1752-09-14") == "1752-09-14"
assert hist_add("1752-09-14", -1, "1752-09-14") == "1752-09-02"
assert hist_add("1700-02-28", 1, "1752-09-14") == "1700-02-29"
assert hist_add("1700-02-28", 1, "1582-10-15") == "1700-03-01"
assert hist_add("1918-01-31", 1, "1918-02-14") == "1918-02-14"
assert hist_add("1582-10-04", 1, "1582-10-15") == "1582-10-15"
assert hist_add("2000-01-01", 0, "1582-10-15") == "2000-01-01"
assert hist_add("0001-01-01", 0, "1582-10-15") == "0001-01-01"
assert hist_add("0004-02-28", 1, "1582-10-15") == "0004-02-29"
assert hist_add("0001-01-01", 577737, "1582-10-15") == "1582-10-15"
assert hist_add("1700-02-18", 1, "1700-03-01") == "1700-03-01"
assert hist_add("1600-02-28", 1, "1700-03-01") == "1600-02-29"
assert hist_add("1700-02-29", 1, "1752-09-14") == "1700-03-01"
assert hist_add("1500-02-29", -59, "1582-10-15") == "1500-01-01"
assert hist_add("1100-02-29", 0, "1918-02-14") == "1100-02-29"
assert hist_add("9999-12-31", 0, "1929-12-31") == "9999-12-31"
for a in [("1752-09-05", 0, "1752-09-14"), ("1752-09-13", 0, "1752-09-14"), ("1900-02-29", 0, "1752-09-14"),
          ("1700-02-29", 0, "1700-03-01"), ("1700-02-19", 0, "1700-03-01"), ("0000-12-31", 0, "1582-10-15"),
          ("1752-9-14", 0, "1752-09-14"), ("1752-09-14", 0, "1582-10-14"), ("1752-09-14", 0, "1930-01-01"),
          ("2001-02-29", 0, "1582-10-15"), ("1600-13-01", 0, "1700-03-01"), ("17520914", 0, "1752-09-14"),
          ("9999-12-31", 1, "1582-10-15"), ("0001-01-01", -1, "1582-10-15"), ("1582-10-10", 0, "1582-10-15"),
          ("1752-09-14", 0, "1800-02-29"), (" 1752-09-14", 0, "1752-09-14"), ("1752-09-14", 0, "1752-09-31")]:
    assert call(*a) == "ValueError", a
SW = ["1582-10-15", "1582-12-20", "1700-03-01", "1752-09-14", "1753-03-01", "1873-01-01", "1916-04-14",
      "1918-02-14", "1923-03-01", "1929-12-31"]
random.seed(3025)
lo, hi = jul_ord(1, 1, 1), datetime.date(9999, 12, 31).toordinal()
for _ in range(3000):
    if random.random() < 0.3:
        dd = datetime.date.fromordinal(random.randint(datetime.date(1582, 10, 15).toordinal(), datetime.date(1929, 12, 31).toordinal()))
        sw = lab((dd.year, dd.month, dd.day))
    else:
        sw = random.choice(SW)
    S = g_ord(tuple(map(int, sw.split("-"))))
    mode = random.random()
    if mode < 0.15:
        y = random.choice([int(sw[:4]) - 1, int(sw[:4]), int(sw[:4]) + 1, 1700, 1800, 1900])
        date = (y, random.randint(1, 12), random.randint(1, 31))
        days = random.randint(-100, 100)
    else:
        o = random.choice([random.randint(lo, hi), S + random.randint(-400, 400)])
        if o >= S:
            dd = datetime.date.fromordinal(o)
            date = (dd.year, dd.month, dd.day)
        else:
            date = jul_from(o)
        days = random.choice([random.randint(-60, 60), random.randint(-10**6, 10**6), S - o + random.randint(-3, 3)])
    exp = oracle(date, days, tuple(map(int, sw.split("-"))))
    got = call(lab(date), days, sw)
    assert got == exp, (lab(date), days, sw, got, exp)
''', r'''
import re


def _gj(y, m, d):
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045


def _jj(y, m, d):
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - 32083


def _from_g(j):
    a = j + 32044
    b = (4 * a + 3) // 146097
    c = a - 146097 * b // 4
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return (100 * b + d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1)


def _from_j(j):
    c = j + 32082
    d = (4 * c + 3) // 1461
    e = c - 1461 * d // 4
    m = (5 * e + 2) // 153
    return (d - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1)


_ML = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _ok(y, m, d, greg):
    if not (1 <= y <= 9999 and 1 <= m <= 12 and d >= 1):
        return False
    leap = y % 4 == 0 and (not greg or y % 100 != 0 or y % 400 == 0)
    return d <= _ML[m] + (1 if m == 2 and leap else 0)


def _parse(s):
    if not isinstance(s, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", s):
        raise ValueError("bad format")
    return tuple(int(x) for x in s.split("-"))


def hist_add(date, days, switch):
    sw = _parse(switch)
    if not _ok(*sw, True) or not ((1582, 10, 15) <= sw <= (1929, 12, 31)):
        raise ValueError("bad switch")
    S = _gj(*sw)
    t = _parse(date)
    if _ok(*t, True) and _gj(*t) >= S:
        j = _gj(*t)
    elif _ok(*t, False) and _jj(*t) < S:
        j = _jj(*t)
    else:
        raise ValueError("bad date")
    j += days
    if j < _jj(1, 1, 1) or j > _gj(9999, 12, 31):
        raise ValueError("out of range")
    return "%04d-%02d-%02d" % (_from_g(j) if j >= S else _from_j(j))
''')


task("v3_26_apportion", r'''
Write `apportion(votes: list[int], seats: int, method: str, threshold=(0, 1)) -> list[int]`
returning the number of seats each party gets (same order as votes).
- votes[i] >= 0 is party i's vote count, seats >= 0. threshold = (num, den) with num >= 0,
  den >= 1. With total = sum(votes), party i is eligible if votes[i] > 0 and
  votes[i] * den >= num * total. Ineligible parties get 0 seats.
- ValueError for: a negative vote count, seats < 0, num < 0 or den < 1, an unknown method,
  or seats > 0 with no eligible party. If seats == 0 every party gets 0 (after the other
  checks). The two largest-remainder methods also raise for nothing else.
- Highest-averages methods hand out seats one at a time, each to the eligible party with the
  largest quotient votes / D(s), where s is the number of seats the party already holds:
  "dhondt": D(s) = s + 1; "sainte-lague": D(s) = 2s + 1; "modified-sainte-lague": D(0) = 7/5
  and D(s) = 2s + 1 for s >= 1; "huntington-hill": D(s) = sqrt(s*(s+1)). For
  huntington-hill D(0) = 0, so first every eligible party gets one seat (ValueError if seats
  is less than the number of eligible parties), then the rest go by quotient.
- Largest-remainder methods: let V = sum of eligible votes. "hare": quota Q = V / seats
  (exact rational). "droop": Q = V // (seats + 1) + 1 (integer). Each eligible party first
  gets floor(votes / Q) seats; the remaining seats go one each to eligible parties in
  decreasing order of remainder votes - Q * floor(votes / Q). If more seats remain than there
  are eligible parties, keep cycling through that same order.
- Ties (equal quotients, or equal remainders): the party with more votes wins; if still tied,
  the lower index.
- Compare exactly: votes go up to 10**15, so floats give wrong answers.
Examples:
apportion([100, 80, 30, 20], 8, "dhondt") == [4, 3, 1, 0]
apportion([100, 80, 30, 20], 8, "sainte-lague") == [3, 3, 1, 1]
apportion([100, 80, 30, 20], 8, "hare") == [3, 3, 1, 1]
apportion([100, 80, 30, 20], 8, "dhondt", (1, 10)) == [4, 3, 1, 0]
apportion([10, 10], 3, "dhondt") == [2, 1]
''', r'''
import random
from fractions import Fraction as F
from math import isqrt
def call(*a):
    try:
        return apportion(*a)
    except ValueError:
        return "ValueError"
def oracle(votes, seats, method, thr=(0, 1)):
    num, den = thr
    if any(v < 0 for v in votes) or seats < 0 or num < 0 or den < 1:
        return "ValueError"
    if method not in ("dhondt", "sainte-lague", "modified-sainte-lague", "huntington-hill", "hare", "droop"):
        return "ValueError"
    tot = sum(votes)
    el = [i for i, v in enumerate(votes) if v > 0 and v * den >= num * tot]
    res = [0] * len(votes)
    if seats == 0:
        return res
    if not el:
        return "ValueError"
    def better(i, ni, di, j, nj, dj):
        # is quotient ni/di of i strictly better than nj/dj of j (di, dj may be 0 = infinity)
        if di == 0 or dj == 0:
            if di == 0 and dj != 0:
                return True
            if dj == 0 and di != 0:
                return False
        else:
            if ni * dj != nj * di:
                return ni * dj > nj * di
        if votes[i] != votes[j]:
            return votes[i] > votes[j]
        return i < j
    if method in ("hare", "droop"):
        V = sum(votes[i] for i in el)
        if method == "hare":
            qn, qd = V, seats
        else:
            qn, qd = V // (seats + 1) + 1, 1
        rem = {}
        for i in el:
            res[i] = votes[i] * qd // qn
            rem[i] = (votes[i] * qd - res[i] * qn, qd)
        left = seats - sum(res)
        order = []
        pool = list(el)
        while pool:
            b = pool[0]
            for j in pool[1:]:
                if better(j, rem[j][0], rem[j][1], b, rem[b][0], rem[b][1]):
                    b = j
            order.append(b)
            pool.remove(b)
        k = 0
        while left > 0:
            res[order[k % len(order)]] += 1
            k += 1
            left -= 1
        return res
    if method == "huntington-hill":
        if seats < len(el):
            return "ValueError"
        for i in el:
            res[i] = 1
        left = seats - len(el)
    else:
        left = seats
    for _ in range(left):
        b = None
        for i in el:
            s = res[i]
            if method == "dhondt":
                n_, d_ = votes[i], s + 1
            elif method == "sainte-lague":
                n_, d_ = votes[i], 2 * s + 1
            elif method == "modified-sainte-lague":
                n_, d_ = (votes[i] * 5, 7) if s == 0 else (votes[i], 2 * s + 1)
            else:
                n_, d_ = votes[i] ** 2, s * (s + 1)
            if b is None or better(i, n_, d_, b[0], b[1], b[2]):
                b = (i, n_, d_)
        res[b[0]] += 1
    return res
assert apportion([100, 80, 30, 20], 8, "dhondt") == [4, 3, 1, 0]
assert apportion([100, 80, 30, 20], 8, "sainte-lague") == [3, 3, 1, 1]
assert apportion([100, 80, 30, 20], 8, "hare") == [3, 3, 1, 1]
assert apportion([100, 80, 30, 20], 8, "dhondt", (1, 10)) == [4, 3, 1, 0]
assert apportion([10, 10], 3, "dhondt") == [2, 1]
assert apportion([10, 20], 3, "huntington-hill") == [1, 2]
assert apportion([1, 1, 1], 2, "hare") == [1, 1, 0]
assert apportion([3, 0], 10, "droop") == [10, 0]
assert apportion([2, 1], 10, "droop") == [6, 4]
assert apportion([0, 0], 0, "dhondt") == [0, 0]
assert apportion([], 0, "hare") == []
assert apportion([5, 1], 3, "modified-sainte-lague") == [3, 0]
assert apportion([5, 2], 3, "sainte-lague") == [2, 1]
assert apportion([10**15, 10**15 - 1, 1], 5, "dhondt") == [3, 2, 0]
assert apportion([7, 3], 2, "sainte-lague", (3, 10)) == [1, 1]
assert apportion([7, 3], 2, "sainte-lague", (31, 100)) == [2, 0]
for a in [([1, -1], 2, "dhondt"), ([1], -1, "dhondt"), ([1], 1, "dhondt", (1, 0)), ([1], 1, "dhondt", (-1, 2)),
          ([1], 1, "jefferson"), ([0, 0], 1, "dhondt"), ([1, 1, 1], 2, "huntington-hill"), ([1, 9], 1, "hare", (2, 1))]:
    assert call(*a) == "ValueError", a
M = ["dhondt", "sainte-lague", "modified-sainte-lague", "huntington-hill", "hare", "droop"]
random.seed(3026)
for _ in range(2500):
    n = random.randint(1, 7)
    kind = random.random()
    if kind < 0.4:
        votes = [random.randint(0, 12) for _ in range(n)]
    elif kind < 0.7:
        base = random.randint(1, 50)
        votes = [base * random.randint(0, 4) for _ in range(n)]
    else:
        votes = [random.randint(0, 10**15) for _ in range(n)]
    seats = random.randint(0, 25)
    thr = random.choice([(0, 1), (0, 1), (1, 20), (1, 5), (1, 3), (random.randint(0, 3), random.randint(1, 10))])
    m = random.choice(M)
    exp = oracle(votes, seats, m, thr)
    got = call(votes, seats, m, thr)
    assert got == exp, (votes, seats, m, thr, got, exp)
    if exp != "ValueError":
        assert sum(got) == seats
''', r'''
from fractions import Fraction

_METHODS = ("dhondt", "sainte-lague", "modified-sainte-lague", "huntington-hill", "hare", "droop")


def apportion(votes, seats, method, threshold=(0, 1)):
    num, den = threshold
    if any(v < 0 for v in votes) or seats < 0 or num < 0 or den < 1 or method not in _METHODS:
        raise ValueError("bad input")
    total = sum(votes)
    el = [i for i, v in enumerate(votes) if v > 0 and v * den >= num * total]
    res = [0] * len(votes)
    if seats == 0:
        return res
    if not el:
        raise ValueError("no eligible party")
    if method in ("hare", "droop"):
        V = sum(votes[i] for i in el)
        Q = Fraction(V, seats) if method == "hare" else Fraction(V // (seats + 1) + 1)
        for i in el:
            res[i] = int(votes[i] // Q)
        order = sorted(el, key=lambda i: (-(votes[i] - Q * res[i]), -votes[i], i))
        left = seats - sum(res)
        for k in range(left):
            res[order[k % len(order)]] += 1
        return res
    left = seats
    if method == "huntington-hill":
        if seats < len(el):
            raise ValueError("too few seats")
        for i in el:
            res[i] = 1
        left -= len(el)

    def q(i):
        s, v = res[i], votes[i]
        if method == "dhondt":
            return Fraction(v, s + 1)
        if method == "sainte-lague":
            return Fraction(v, 2 * s + 1)
        if method == "modified-sainte-lague":
            return Fraction(5 * v, 7) if s == 0 else Fraction(v, 2 * s + 1)
        return Fraction(v * v, s * (s + 1))
    for _ in range(left):
        b = max(el, key=lambda i: (q(i), votes[i], -i))
        res[b] += 1
    return res
''')


task("v3_27_lp2d", r'''
Write `lp2d(cons, obj)` that maximizes p*x + q*y, with obj = (p, q), over real x >= 0, y >= 0
subject to a*x + b*y <= c for every (a, b, c) in cons. Return:
- the string "infeasible" if no point satisfies all constraints;
- the string "unbounded" if the region is non-empty and p*x + q*y has no maximum on it;
- otherwise (value, x, y) as fractions.Fraction values, where (x, y) is the optimal point
  with the smallest x, and among those the smallest y.
All inputs are ints with absolute value <= 10**6. cons may be empty and may contain
redundant, duplicated or parallel constraints, or rows with a == b == 0 (meaning 0 <= c).
With p == q == 0 every feasible point is optimal. Up to 40 constraints per call.
Examples:
lp2d([(1, 1, 4)], (1, 1)) == (4, 0, 4)
lp2d([(1, 1, 4)], (1, 0)) == (4, 4, 0)
lp2d([(-1, -1, -5)], (-1, -1)) == (-5, 0, 5)
lp2d([(1, 0, -1)], (1, 1)) == "infeasible"
lp2d([(1, -1, 0)], (1, 0)) == "unbounded"
lp2d([], (0, 0)) == (0, 0, 0)
Do not use scipy, numpy or pulp.
''', r'''
_banned(mods=("scipy", "numpy", "pulp", "cvxpy", "sympy"))
import random
from fractions import Fraction as F
def oracle(cons, obj):
    rows = [(-1, 0, 0), (0, -1, 0)]
    for a, b, c in cons:
        if a == 0 and b == 0:
            if c < 0:
                return "infeasible"
        else:
            rows.append((a, b, c))
    def feas(x, y):
        return all(a * x + b * y <= c for a, b, c in rows)
    verts = set()
    for i in range(len(rows)):
        a1, b1, c1 = rows[i]
        for j in range(i + 1, len(rows)):
            a2, b2, c2 = rows[j]
            d = a1 * b2 - a2 * b1
            if d == 0:
                continue
            x, y = F(c1 * b2 - c2 * b1, d), F(a1 * c2 - a2 * c1, d)
            if feas(x, y):
                verts.add((x, y))
    if not verts:
        return "infeasible"
    p, q = obj
    dirs = [(p, q)]
    for a, b, _ in rows:
        dirs += [(-b, a), (b, -a), (-a, -b)]
    for dx, dy in dirs:
        if (dx, dy) != (0, 0) and all(a * dx + b * dy <= 0 for a, b, _ in rows) and p * dx + q * dy > 0:
            return "unbounded"
    best = max(p * x + q * y for x, y in verts)
    x, y = min(v for v in verts if p * v[0] + q * v[1] == best)
    return (best, x, y)
assert lp2d([(1, 1, 4)], (1, 1)) == (4, 0, 4)
assert lp2d([(1, 1, 4)], (1, 0)) == (4, 4, 0)
assert lp2d([(-1, -1, -5)], (-1, -1)) == (-5, 0, 5)
assert lp2d([(1, 0, -1)], (1, 1)) == "infeasible"
assert lp2d([(1, -1, 0)], (1, 0)) == "unbounded"
assert lp2d([], (0, 0)) == (0, 0, 0)
assert lp2d([], (-1, -1)) == (0, 0, 0)
assert lp2d([], (0, 1)) == "unbounded"
assert lp2d([(0, 0, -1)], (0, 0)) == "infeasible"
assert lp2d([(0, 0, 0)], (1, 1)) == "unbounded"
assert lp2d([(0, 0, 3), (1, 0, 2), (0, 1, 3)], (1, 1)) == (5, 2, 3)
assert lp2d([(-1, 0, -2)], (-1, 0)) == (-2, 2, 0)
assert lp2d([(-1, 0, -2), (0, 1, 7)], (-1, 0)) == (-2, 2, 0)
assert lp2d([(1, 0, 3)], (1, 0)) == (3, 3, 0)
assert lp2d([(2, 3, 7), (5, -1, 4)], (3, 2)) == lp2d([(5, -1, 4), (2, 3, 7), (2, 3, 7)], (3, 2))
r = lp2d([(2, 3, 7), (5, -1, 4)], (3, 2))
assert r == (F(111, 17), F(19, 17), F(27, 17)) and all(isinstance(v, F) for v in r)
assert lp2d([(1, 2, 4), (3, 1, 6)], (0, 0)) == (0, 0, 0)
assert lp2d([(-1, -1, -2), (1, 1, 2)], (1, -1)) == (2, 2, 0)
assert lp2d([(-1, -1, -2), (1, 1, 2)], (1, 1)) == (2, 0, 2)
assert lp2d([(-1, 1, 0), (1, -1, 0)], (0, 0)) == (0, 0, 0)
assert lp2d([(-1, 1, 0), (1, -1, 0)], (1, -1)) == (0, 0, 0)
assert lp2d([(-1, 1, 0), (1, -1, 0)], (1, 0)) == "unbounded"
assert lp2d([(1, 1, -1)], (0, 0)) == "infeasible"
random.seed(3027)
for _ in range(1500):
    k = random.randint(0, 6)
    R = random.choice([3, 10, 1000])
    cons = [(random.randint(-R, R), random.randint(-R, R), random.randint(-R, 2 * R)) for _ in range(k)]
    if random.random() < 0.2 and cons:
        a, b, c = random.choice(cons)
        s = random.randint(1, 3)
        cons.append((a * s, b * s, c * s + random.choice([0, 0, -1, 1])))
    if random.random() < 0.1:
        cons.append((0, 0, random.randint(-1, 2)))
    random.shuffle(cons)
    obj = random.choice([(random.randint(-R, R), random.randint(-R, R)), (0, 0)] + [(-a, -b) for a, b, _ in cons][:2] + [(a, b) for a, b, _ in cons][:2])
    exp = oracle(cons, obj)
    got = lp2d(cons, obj)
    assert got == exp, (cons, obj, got, exp)
for _ in range(10):
    cons = [(random.randint(-10**6, 10**6), random.randint(1, 10**6), random.randint(0, 10**6)) for _ in range(40)]
    obj = (random.randint(-10**6, 10**6), random.randint(-10**6, 10**6))
    assert lp2d(cons, obj) == oracle(cons, obj)
''', r'''
from fractions import Fraction


def lp2d(cons, obj):
    rows = [(-1, 0, 0), (0, -1, 0)]
    for a, b, c in cons:
        if a == 0 and b == 0:
            if c < 0:
                return "infeasible"
            continue
        rows.append((a, b, c))
    rows = list(dict.fromkeys(rows))
    verts = set()
    for i in range(len(rows)):
        a1, b1, c1 = rows[i]
        for j in range(i + 1, len(rows)):
            a2, b2, c2 = rows[j]
            d = a1 * b2 - a2 * b1
            if d == 0:
                continue
            x = Fraction(c1 * b2 - c2 * b1, d)
            y = Fraction(a1 * c2 - a2 * c1, d)
            if all(a * x + b * y <= c for a, b, c in rows):
                verts.add((x, y))
    if not verts:
        return "infeasible"
    p, q = obj
    cand = [(p, q)]
    for a, b, _ in rows:
        cand += [(-b, a), (b, -a), (-a, -b)]
    for dx, dy in cand:
        if (dx or dy) and p * dx + q * dy > 0 and all(a * dx + b * dy <= 0 for a, b, _ in rows):
            return "unbounded"
    best = max(p * x + q * y for x, y in verts)
    x, y = min(v for v in verts if p * v[0] + q * v[1] == best)
    return (Fraction(best), x, y)
''')


task("v3_28_monthly_rule", r'''
Write `monthly(start, count, interval=1, bymonthday=(), byday=(), bysetpos=(), until=None)`
returning a list of "YYYY-MM-DD" strings: the occurrences of a monthly recurrence (a subset of
iCalendar RRULE FREQ=MONTHLY), proleptic Gregorian calendar, years 1..9999.
- start and until are "YYYY-MM-DD" (exactly 4-2-2 digits, a valid date, year >= 1).
- Candidate months: the month of start, then every `interval` months after it.
- Matching days of a candidate month:
  - bymonthday: ints in 1..31 or -31..-1, where -1 is the last day of the month, -2 the one
    before, and so on. A value that does not exist in that month (31 in April, -30 in
    February) matches nothing.
  - byday: strings of an optional ordinal and a weekday code MO TU WE TH FR SA SU, e.g. "FR",
    "2TU", "+3SU", "-1FR". The ordinal is 1..5 with optional sign. Without an ordinal every
    such weekday of the month matches; with n > 0 the n-th such weekday of the month; with
    n < 0 the |n|-th from the end. If it does not exist, nothing matches.
  - If both bymonthday and byday are non-empty, a day must match both lists (one entry of
    each). If only one is non-empty, it alone decides. If both are empty, the day of month of
    start matches (months without that day are skipped).
  - bysetpos: if non-empty, from the month's sorted matching days keep only those at the listed
    positions (1-based; negative counts from the end; positions out of range are ignored, and
    a day selected twice appears once).
- Occurrences are the matching days >= start, in order. Return the first `count` of them,
  stopping early at the first occurrence after `until` (until is inclusive) or after year 9999.
- ValueError: bad start or until; count < 0; interval < 1; a bymonthday or bysetpos value of 0
  or with absolute value > 31; a malformed byday string (including ordinal 0 or > 5).
Examples:
monthly("2024-01-31", 4) == ["2024-01-31", "2024-03-31", "2024-05-31", "2024-07-31"]
monthly("2024-01-01", 3, byday=["-1FR"]) == ["2024-01-26", "2024-02-23", "2024-03-29"]
monthly("2024-01-01", 3, byday=["MO", "TU", "WE", "TH", "FR"], bysetpos=[-1])
    == ["2024-01-31", "2024-02-29", "2024-03-29"]
monthly("2024-01-01", 3, bymonthday=[13], byday=["FR"]) == ["2024-09-13", "2024-12-13", "2025-06-13"]
Do not use the datetime, calendar, time or dateutil modules.
''', r'''
_banned(mods=("datetime", "_datetime", "_pydatetime", "calendar", "time", "dateutil", "_strptime"))
import random, datetime
WD = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
def oracle(start, count, interval=1, bymonthday=(), byday=(), bysetpos=(), until=None):
    s = datetime.date.fromisoformat(start)
    u = datetime.date.fromisoformat(until) if until else None
    out = []
    y, m = s.year, s.month
    while y <= 9999 and len(out) < count:
        days = []
        d = datetime.date(y, m, 1)
        if u and d > u:
            break
        while d.month == m:
            dim = (datetime.date(y + (m == 12), m % 12 + 1, 1) - datetime.date(y, m, 1)).days if y < 9999 or m < 12 else 31
            ok_md = any(v == d.day or v == d.day - dim - 1 for v in bymonthday)
            fwd, back = (d.day - 1) // 7 + 1, (dim - d.day) // 7 + 1
            ok_bd = False
            for spec in byday:
                code, n = spec[-2:], spec[:-2]
                if WD.index(code) == d.weekday() and (n == "" or int(n) == fwd or int(n) == -back):
                    ok_bd = True
            if bymonthday and byday:
                ok = ok_md and ok_bd
            elif bymonthday:
                ok = ok_md
            elif byday:
                ok = ok_bd
            else:
                ok = d.day == s.day
            if ok:
                days.append(d)
            if d.day == dim:
                break
            d += datetime.timedelta(days=1)
        if bysetpos:
            days = [days[k] for k in range(len(days)) if (k + 1) in bysetpos or (k - len(days)) in bysetpos]
        for d in days:
            if d < s:
                continue
            if u and d > u:
                return out
            if len(out) < count:
                out.append(d.isoformat())
        m += interval
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
    return out
def call(*a, **k):
    try:
        return monthly(*a, **k)
    except ValueError:
        return "ValueError"
assert monthly("2024-01-31", 4) == ["2024-01-31", "2024-03-31", "2024-05-31", "2024-07-31"]
assert monthly("2024-01-01", 3, byday=["-1FR"]) == ["2024-01-26", "2024-02-23", "2024-03-29"]
assert monthly("2024-01-01", 3, byday=["MO", "TU", "WE", "TH", "FR"], bysetpos=[-1]) == ["2024-01-31", "2024-02-29", "2024-03-29"]
assert monthly("2024-01-01", 3, bymonthday=[13], byday=["FR"]) == ["2024-09-13", "2024-12-13", "2025-06-13"]
assert monthly("2024-01-15", 2, bymonthday=[1, 15]) == ["2024-01-15", "2024-02-01"]
assert monthly("2024-01-16", 2, bymonthday=[1, 15]) == ["2024-02-01", "2024-02-15"]
assert monthly("2023-01-01", 3, bymonthday=[-1]) == ["2023-01-31", "2023-02-28", "2023-03-31"]
assert monthly("2024-02-01", 2, bymonthday=[-30, 30]) == ["2024-03-02", "2024-03-30"]
assert monthly("2024-01-01", 2, byday=["5MO"]) == ["2024-01-29", "2024-04-29"]
assert monthly("2024-01-01", 3, interval=2, byday=["+1SU"]) == ["2024-01-07", "2024-03-03", "2024-05-05"]
assert monthly("2024-01-01", 5, bymonthday=[31], until="2024-08-30") == ["2024-01-31", "2024-03-31", "2024-05-31", "2024-07-31"]
assert monthly("2024-01-01", 0) == []
assert monthly("2024-03-10", 3, until="2024-03-09") == []
assert monthly("9999-11-30", 5) == ["9999-11-30", "9999-12-30"]
assert monthly("9000-02-01", 3, interval=12, bymonthday=[30]) == []
assert monthly("2024-01-01", 2, bymonthday=[1, 2, 3, 4, 5], bysetpos=[2, -1, 2, 9]) == ["2024-01-02", "2024-01-05"]
assert monthly("0001-01-01", 2, byday=["MO"]) == ["0001-01-01", "0001-01-08"]
for a, k in [(("2024-1-01", 3), {}), (("2024-02-30", 3), {}), (("0000-01-01", 1), {}), (("2024-01-01", -1), {}),
             (("2024-01-01", 1), {"interval": 0}), (("2024-01-01", 1), {"bymonthday": [0]}),
             (("2024-01-01", 1), {"bymonthday": [32]}), (("2024-01-01", 1), {"byday": ["6MO"]}),
             (("2024-01-01", 1), {"byday": ["0MO"]}), (("2024-01-01", 1), {"byday": ["mo"]}),
             (("2024-01-01", 1), {"byday": ["MON"]}), (("2024-01-01", 1), {"bysetpos": [0]}),
             (("2024-01-01", 1), {"bysetpos": [-32]}), (("2024-01-01", 1), {"until": "2024-13-01"}),
             (("2024-01-01", 1), {"byday": ["+-1MO"]}), (("2024-01-01", 1), {"byday": ["1"]})]:
    assert call(*a, **k) == "ValueError", (a, k)
random.seed(3028)
for _ in range(700):
    y = random.choice([random.randint(1, 9999), random.randint(1890, 2110), 9998, 9999])
    m = random.randint(1, 12)
    d0 = datetime.date(y, m, 1)
    s = (d0 + datetime.timedelta(days=random.randint(0, 27 if (y, m) == (9999, 12) else 30))).isoformat()
    if datetime.date.fromisoformat(s).month != m:
        s = d0.isoformat()
    kw = {}
    if random.random() < 0.5:
        kw["bymonthday"] = random.sample([v for v in range(-31, 32) if v], random.randint(1, 4))
    if random.random() < 0.5:
        kw["byday"] = [random.choice(["", "", "1", "2", "-1", "+3", "-2", "4", "5", "-5"]) + random.choice(WD) for _ in range(random.randint(1, 3))]
    if random.random() < 0.3:
        kw["bysetpos"] = random.sample([v for v in range(-6, 7) if v], random.randint(1, 3))
    if random.random() < 0.4:
        kw["interval"] = random.randint(1, 13)
    kw["until"] = (datetime.date.fromisoformat(s) + datetime.timedelta(days=random.randint(-5, 1500))).isoformat() if y < 9995 else "9999-12-31"
    cnt = random.randint(0, 12)
    exp = oracle(s, cnt, **kw)
    got = call(s, cnt, **kw)
    assert got == exp, (s, cnt, kw, got, exp)
''', r'''
import re

_WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
_ML = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _dim(y, m):
    return 29 if m == 2 and y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else _ML[m]


def _parse(s):
    if not isinstance(s, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", s):
        raise ValueError("bad date")
    y, m, d = (int(x) for x in s.split("-"))
    if y < 1 or not 1 <= m <= 12 or not 1 <= d <= _dim(y, m):
        raise ValueError("bad date")
    return (y, m, d)


def _weekday(y, m, d):
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    yy = y - (m < 3)
    return (yy + yy // 4 - yy // 100 + yy // 400 + t[m - 1] + d + 6) % 7


def monthly(start, count, interval=1, bymonthday=(), byday=(), bysetpos=(), until=None):
    s = _parse(start)
    u = _parse(until) if until is not None else None
    if count < 0 or interval < 1:
        raise ValueError("bad count/interval")
    for v in list(bymonthday) + list(bysetpos):
        if v == 0 or abs(v) > 31:
            raise ValueError("bad value")
    specs = []
    for b in byday:
        mt = re.fullmatch(r"([+-]?)([1-5]?)(MO|TU|WE|TH|FR|SA|SU)", b) if isinstance(b, str) else None
        if not mt or (mt.group(1) and not mt.group(2)):
            raise ValueError("bad byday")
        n = int(mt.group(1) + mt.group(2)) if mt.group(2) else None
        specs.append((n, _WD[mt.group(3)]))
    out = []
    y, m = s[0], s[1]
    while y <= 9999 and len(out) < count:
        if u is not None and (y, m, 1) > u:
            break
        dim = _dim(y, m)
        md = {v if v > 0 else dim + 1 + v for v in bymonthday}
        bd = set()
        w1 = _weekday(y, m, 1)
        for n, w in specs:
            days = [d for d in range(1, dim + 1) if (w1 + d - 1) % 7 == w]
            if n is None:
                bd.update(days)
            elif 1 <= abs(n) <= len(days):
                bd.add(days[n - 1] if n > 0 else days[n])
        if bymonthday and byday:
            match = md & bd
        elif bymonthday:
            match = md
        elif byday:
            match = bd
        else:
            match = {s[2]}
        match = sorted(d for d in match if 1 <= d <= dim)
        if bysetpos:
            L = len(match)
            match = sorted({match[p - 1 if p > 0 else L + p] for p in bysetpos if (1 <= p <= L or 1 <= -p <= L)})
        for d in match:
            if (y, m, d) < s:
                continue
            if u is not None and (y, m, d) > u:
                return out
            if len(out) < count:
                out.append("%04d-%02d-%02d" % (y, m, d))
        m += interval
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
    return out
''')


task("v3_29_root_digits", r'''
Write `root_digits(p: int, q: int, n: int, digits: int) -> str` returning the real n-th root
of the rational p/q rounded to `digits` decimal places, as a string. Rules:
- q != 0 (the sign may be on p or q), n >= 1, digits >= 0, else ValueError. A negative p/q
  with even n raises ValueError; with odd n the root is the negative real root.
- Round the magnitude to the nearest multiple of 10**-digits; an exact halfway case (only
  possible when the root is rational) goes to the even last digit. Then apply the sign.
- Format: "-" only if the rounded value is non-zero and negative, then the integer part
  without leading zeros (at least one digit), then, if digits > 0, "." and exactly `digits`
  digits.
- Sizes: |p|, |q| up to 10**300, n up to 50, digits up to 200. 300 calls must take well under
  a few seconds. Floats overflow or lose digits here; do not use the decimal, fractions,
  gmpy2 or sympy modules.
Examples:
root_digits(2, 1, 2, 5) == "1.41421"
root_digits(1, 4, 2, 0) == "0"        (0.5 rounds to even 0)
root_digits(9, 4, 2, 0) == "2"        (1.5 rounds to even 2)
root_digits(-27, 8, 3, 1) == "-1.5"
root_digits(1, -8, 3, 0) == "0"       (-0.5 -> 0, no sign)
root_digits(5, 8, 1, 2) == "0.62"     (0.625 -> 0.62)
root_digits(10**100, 1, 7, 3) == "193069772888325.017"
''', r'''
_banned(mods=("decimal", "_pydecimal", "_decimal", "fractions", "gmpy2", "sympy", "mpmath"))
import random, re, time
from fractions import Fraction as F
def call(*a):
    try:
        return root_digits(*a)
    except ValueError:
        return "ValueError"
def verify(p, q, n, d, s):
    assert re.fullmatch(r"-?(0|[1-9][0-9]*)" + (r"\.[0-9]{%d}" % d if d else ""), s), (p, q, n, d, s)
    v = F(s.replace(".", "")) / 10**d if d else F(s)
    x = F(p, q)
    if x < 0:
        assert v <= 0, (p, q, n, d, s)
    assert s not in ("-0",) and not re.fullmatch(r"-0\.0*", s), s
    a, mag = abs(x), abs(v)
    h = F(1, 2 * 10**d)
    lo, hi = max(mag - h, F(0)), mag + h
    assert lo ** n <= a <= hi ** n, (p, q, n, d, s)
    if (mag > 0 and lo ** n == a) or hi ** n == a:
        assert (mag * 10**d) % 2 == 0, ("tie not to even", p, q, n, d, s)
assert root_digits(2, 1, 2, 5) == "1.41421"
assert root_digits(1, 4, 2, 0) == "0"
assert root_digits(9, 4, 2, 0) == "2"
assert root_digits(25, 4, 2, 0) == "2"
assert root_digits(49, 4, 2, 0) == "4"
assert root_digits(-27, 8, 3, 1) == "-1.5"
assert root_digits(27, -8, 3, 0) == "-2"
assert root_digits(1, -8, 3, 0) == "0"
assert root_digits(5, 8, 1, 2) == "0.62"
assert root_digits(7, 8, 1, 2) == "0.88"
assert root_digits(10**100, 1, 7, 3) == "193069772888325.017"
assert root_digits(0, 5, 4, 3) == "0.000"
assert root_digits(0, -5, 3, 0) == "0"
assert root_digits(1, 3, 1, 2) == "0.33"
assert root_digits(-1, 3, 1, 2) == "-0.33"
assert root_digits(-1, 300, 1, 2) == "0.00"
assert root_digits(1, 1, 50, 4) == "1.0000"
assert root_digits(81, 16, 4, 1) == "1.5"
assert root_digits(1, 16, 4, 0) == "0"
assert root_digits(3**40, 2**40, 40, 0) == "2"
assert root_digits(10**300, 1, 2, 2) == "1" + "0" * 150 + ".00"
assert root_digits(2, 1, 2, 60) == "1.414213562373095048801688724209698078569671875376948073176680"
for a in [(1, 0, 2, 2), (1, 2, 0, 2), (1, 2, 2, -1), (-1, 2, 2, 2), (1, -2, 4, 0)]:
    assert call(*a) == "ValueError", a
random.seed(3029)
for _ in range(1500):
    n = random.choice([1, 2, 2, 3, 3, 4, 5, 7])
    d = random.choice([0, 0, 1, 2, 3, 5])
    if random.random() < 0.4:
        r = F(random.randint(-300, 300), random.choice([1, 2, 4, 8, 10, 20, 40, 1000]))
        if n % 2 == 0:
            r = abs(r)
        x = r ** n
        p, q = x.numerator * random.choice([1, -1]), x.denominator
        if random.random() < 0.5:
            p, q = -p, -q
        if n % 2 == 0 and F(p, q) < 0:
            p = -p
    else:
        p, q = random.randint(-10**6, 10**6), random.choice([-1, 1]) * random.randint(1, 10**6)
        if n % 2 == 0:
            p = abs(p) * (1 if q > 0 else -1)
    s = root_digits(p, q, n, d)
    verify(p, q, n, d, s)
cases = []
for _ in range(300):
    n = random.randint(1, 50)
    d = random.randint(0, 200)
    p = random.randint(1, 10**300) * (random.choice([1, -1]) if n % 2 else 1)
    q = random.randint(1, 10**300)
    cases.append((p, q, n, d))
t0 = time.perf_counter()
outs = [root_digits(*c) for c in cases]
assert time.perf_counter() - t0 < 3.0
for c, s in zip(cases[:40], outs[:40]):
    verify(*c, s)
''', r'''
def _iroot(a, n):
    if a < 2:
        return a
    x = 1 << ((a.bit_length() + n - 1) // n)
    while True:
        y = ((n - 1) * x + a // x ** (n - 1)) // n
        if y >= x:
            break
        x = y
    while x ** n > a:
        x -= 1
    while (x + 1) ** n <= a:
        x += 1
    return x


def root_digits(p, q, n, digits):
    if q == 0 or n < 1 or digits < 0:
        raise ValueError("bad input")
    neg = (p < 0) != (q < 0) and p != 0
    if neg and n % 2 == 0:
        raise ValueError("even root of negative")
    a, b = abs(p), abs(q)
    scale = 10 ** (digits * n)
    f = _iroot(a * scale // b, n)
    lhs = (2 * f + 1) ** n * b
    rhs = 2 ** n * a * scale
    if lhs < rhs or (lhs == rhs and f % 2 == 1):
        f += 1
    s = str(f)
    if digits:
        s = s.rjust(digits + 1, "0")
        s = s[:-digits] + "." + s[-digits:]
    return ("-" if neg and f else "") + s
''')


task("v3_30_billiard", r'''
Write `billiard(W, H, x, y, vx, vy, t, e=1)` that simulates a point ball in the box
0 <= X <= W, 0 <= Y <= H and returns (X, Y, VX, VY, hits_x, hits_y) at time t.
- W, H are positive ints. The start (x, y) is strictly inside (0 < x < W, 0 < y < H); x and y
  are ints or fractions.Fraction. vx, vy are ints of any sign (0 allowed). t >= 0 is an int or
  Fraction. e (restitution) is an int or Fraction with 0 < e <= 1. Anything else raises
  ValueError.
- The ball moves in straight lines. The axes are independent: when the ball reaches x = 0 or
  x = W moving toward that wall, vx is replaced by -vx * e (likewise vy at y = 0 or y = H). A
  corner hit reflects both components and counts once on each axis.
- hits_x / hits_y count the wall hits on each axis at times in (0, t]. A hit at exactly time t
  counts, and the returned velocity is then already reflected.
- X, Y, VX, VY are exact (ints or Fractions, compared with ==).
- With e == 1, |v| * t can reach 10**30 and hit counts are astronomically large: the answer
  must come in O(1) arithmetic steps (2000 such calls in well under a second). With e < 1 the
  inputs keep each axis below 2000 hits.
Examples:
billiard(10, 10, 5, 5, 1, 0, 5) == (10, 5, -1, 0, 1, 0)
billiard(10, 10, 5, 5, 1, 0, 25) == (10, 5, -1, 0, 3, 0)
billiard(4, 4, 1, 1, 1, 1, 3) == (4, 4, -1, -1, 1, 1)
billiard(10, 10, 5, 5, 2, 0, 10, Fraction(1, 2)) == (Fraction(5, 2), 5, -1, 0, 1, 0)
''', r'''
import random, time
from fractions import Fraction as F
def call(*a):
    try:
        return billiard(*a)
    except ValueError:
        return "ValueError"
def sim(W, H, x, y, vx, vy, t, e=1):
    X, Y, VX, VY, hx, hy, tau = F(x), F(y), F(vx), F(vy), 0, 0, F(0)
    e = F(e)
    while True:
        dts = []
        if VX:
            dts.append(((W - X) / VX) if VX > 0 else X / -VX)
        if VY:
            dts.append(((H - Y) / VY) if VY > 0 else Y / -VY)
        dt = min(dts) if dts else None
        if dt is None or tau + dt > t:
            X += VX * (t - tau)
            Y += VY * (t - tau)
            return (X, Y, VX, VY, hx, hy)
        tau += dt
        X += VX * dt
        Y += VY * dt
        if VX and X in (0, W) and ((X == W) == (VX > 0)):
            VX = -VX * e
            hx += 1
        if VY and Y in (0, H) and ((Y == H) == (VY > 0)):
            VY = -VY * e
            hy += 1
def big(W, H, x, y, vx, vy, t):
    out = []
    for L, p, v in ((W, x, vx), (H, y, vy)):
        if v == 0:
            out.append((F(p), 0, 0))
            continue
        P = F(2 * L, abs(v))
        k = int(F(t) // P)
        r = sim(L, 2, p, 1, v, 0, F(t) - k * P)
        out.append((r[0], r[2], r[4] + 2 * k))
    return (out[0][0], out[1][0], out[0][1], out[1][1], out[0][2], out[1][2])
assert billiard(10, 10, 5, 5, 1, 0, 5) == (10, 5, -1, 0, 1, 0)
assert billiard(10, 10, 5, 5, 1, 0, 25) == (10, 5, -1, 0, 3, 0)
assert billiard(10, 10, 5, 5, 1, 0, 15) == (0, 5, 1, 0, 2, 0)
assert billiard(10, 10, 5, 5, 1, 0, F(29, 2)) == (F(1, 2), 5, -1, 0, 1, 0)
assert billiard(4, 4, 1, 1, 1, 1, 3) == (4, 4, -1, -1, 1, 1)
assert billiard(10, 10, 5, 5, 2, 0, 10, F(1, 2)) == (F(5, 2), 5, -1, 0, 1, 0)
assert billiard(10, 10, 5, 5, -3, 0, F(5, 3), F(1, 3)) == (0, 5, 1, 0, 1, 0)
assert billiard(10, 10, 5, 5, 0, 0, 10**9) == (5, 5, 0, 0, 0, 0)
assert billiard(10, 10, 5, 5, 3, -4, 0) == (5, 5, 3, -4, 0, 0)
assert billiard(3, 5, F(1, 2), F(5, 2), 10**15, -10**15, 10**15) == big(3, 5, F(1, 2), F(5, 2), 10**15, -10**15, 10**15)
for a in [(0, 10, 5, 5, 1, 1, 1), (10, -1, 5, 5, 1, 1, 1), (10, 10, 0, 5, 1, 1, 1), (10, 10, 5, 10, 1, 1, 1),
          (10, 10, 5, 5, 1, 1, -1), (10, 10, 5, 5, 1, 1, 1, 0), (10, 10, 5, 5, 1, 1, 1, F(3, 2)),
          (10, 10, 11, 5, 1, 1, 1), (10, 10, 5, 5, 1, 1, 1, -1)]:
    assert call(*a) == "ValueError", a
random.seed(3030)
for _ in range(1500):
    W, H = random.randint(1, 10), random.randint(1, 10)
    x = F(random.randint(1, 4 * W - 1), 4)
    y = F(random.randint(1, 3 * H - 1), 3)
    vx, vy = random.randint(-6, 6), random.randint(-6, 6)
    t = random.choice([F(random.randint(0, 60)), F(random.randint(0, 400), random.choice([2, 3, 6, 12]))])
    e = random.choice([1, 1, F(1, 2), F(2, 3), F(9, 10), F(1, 7)])
    if e == 1 or random.random() < 0.5:
        exp = sim(W, H, x, y, vx, vy, t, e)
        got = billiard(W, H, x, y, vx, vy, t, e)
        assert got == exp, (W, H, x, y, vx, vy, t, e, got, exp)
    tt = random.choice([F(random.randint(0, 10**6)), F(random.randint(0, 10**9), 7)])
    if e != 1:
        got = billiard(W, H, x, y, vx * 1000, vy * 1000, tt, e)
        exp = sim(W, H, x, y, vx * 1000, vy * 1000, tt, e)
        assert got == exp, (W, H, x, y, vx * 1000, vy * 1000, tt, e, got, exp)
cases = [(random.randint(1, 1000), random.randint(1, 1000), None, None, random.randint(-10**15, 10**15),
          random.randint(-10**15, 10**15), random.choice([random.randint(0, 10**15), F(random.randint(0, 10**18), random.randint(1, 999))]))
         for _ in range(2000)]
cases = [(W, H, F(random.randint(1, 2 * W - 1), 2), F(random.randint(1, 5 * H - 1), 5), vx, vy, t) for W, H, _, _, vx, vy, t in cases]
t0 = time.perf_counter()
outs = [billiard(*c) for c in cases]
assert time.perf_counter() - t0 < 2.0
for c, o in zip(cases[:300], outs[:300]):
    assert o == big(*c), (c, o)
''', r'''
from fractions import Fraction
from numbers import Rational


def _axis(L, p, v, t, e):
    if v == 0:
        return Fraction(p), 0, 0
    if e == 1:
        X = p + v * t
        hits = (X // L) if v > 0 else ((L - X) // L)
        hits = int(hits)
        r = X % (2 * L)
        pos = r if r <= L else 2 * L - r
        return pos, (v if hits % 2 == 0 else -v), hits
    hits = 0
    p, v, t = Fraction(p), Fraction(v), Fraction(t)
    while True:
        dt = (L - p) / v if v > 0 else p / -v
        if dt > t:
            return p + v * t, v, hits
        t -= dt
        p = Fraction(L) if v > 0 else Fraction(0)
        v = -v * e
        hits += 1


def billiard(W, H, x, y, vx, vy, t, e=1):
    for z in (W, H, vx, vy):
        if not isinstance(z, int):
            raise ValueError("bad int")
    for z in (x, y, t, e):
        if not isinstance(z, Rational):
            raise ValueError("bad number")
    if W <= 0 or H <= 0 or not (0 < x < W) or not (0 < y < H) or t < 0 or not (0 < e <= 1):
        raise ValueError("bad input")
    X, VX, hx = _axis(W, x, vx, t, e)
    Y, VY, hy = _axis(H, y, vy, t, e)
    return (X, Y, VX, VY, hx, hy)
''')

TASKS = T
