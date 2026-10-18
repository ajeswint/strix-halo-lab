"""loop-v7: held-out Python tasks for the CRAwDAD debate (README "v7 tasks" section).

Same layout as tasks_v6.py: id, prompt, tests, ref. Written 2026-10-18 inline in one session (no subagents), every
check run under prlimit --as=4294967296 (the 2026-10-15 crash: a writer's uncapped 10**9 oracle reached 118 GB).
Buckets as in v6: formats and encodings, number theory and combinatorics, graphs and geometry, simulation and DP.
Unaimed: no family was chosen from a stored failure. Difficulty is set for the debate pair (dense 32B models with a
2,048-token reasoning budget): exact specs, algorithms that fit in that budget, no 10**18-scale number theory.
Sealed held-out set: nobody iterates a prompt, a loop or a design on these tasks. Every test file has exactly one
random.seed(N) line, N = 7000 + task number. Seeded random cases are checked against an oracle built differently from
the ref (brute force, a generator that builds the expected answer, or properties). Each ref is at most 150 lines.
Batch 1: v7_01 packbits, v7_02 ini_strict, v7_03 semver_order, v7_04 partition_rank, v7_05 digit_rules,
v7_06 route_lexmin, v7_07 rect_union, v7_08 bowling_frames, v7_09 paint_posts, v7_10 justify_lines.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})

task("v7_01_packbits", r'''
Write two functions for the PackBits run-length format: `packbits_decode(data)` and `packbits_encode(data)`. Both take
a `bytes` or `bytearray` (anything else, including str, list, memoryview or None, raises ValueError) and return `bytes`.

Format. A PackBits stream is a sequence of packets. Each packet starts with a header byte h, read as a signed 8-bit
value (0..127 as is, 128..255 as h - 256):
- 0 to 127: a literal packet; the next h + 1 bytes are copied to the output.
- -127 to -1: a repeat packet; the next single byte is written 1 - h times (2 to 128 copies).
- -128: a no-op; the decoder skips this header byte and reads the next packet. The encoder never writes it.

Decoder: decode packets until the data ends. A packet whose payload is cut off by the end of the data (a literal
header with fewer than h + 1 bytes after it, or a repeat header that is the last byte) raises ValueError. Empty input
gives b"".

Encoder: the output is canonical, produced by exactly this left-to-right rule. Let i be the current position and r the
number of consecutive bytes equal to data[i] starting at i, counting at most 128.
- If r >= 3: write a repeat packet for those r bytes and advance i by r.
- Otherwise write a literal packet starting at i. It takes data[i], then keeps taking the following bytes one at a
  time, and stops before a byte at which a run of 3 or more equal bytes begins, when it holds 128 bytes, or when the
  data ends.
A run of exactly 2 equal bytes is therefore stored inside a literal, and a run longer than 128 is split into a repeat
packet of 128 followed by whatever the same rule does with the rest (a rest of 1 or 2 bytes starts a literal). Empty
input gives b"".

Examples:
- packbits_encode(b"AAAABCD") == b"\xfdA\x02BCD"
- packbits_encode(b"AAB") == b"\x02AAB"
- packbits_encode(b"ABBBC") == b"\x00A\xfeB\x00C"
- packbits_encode(b"\x00" * 130) == b"\x81\x00\x01\x00\x00"
- packbits_decode(b"\x80\x00A") == b"A"
- packbits_decode(b"\xfeZ\x01xy") == b"ZZZxy"
- ValueError: packbits_decode(b"\x02AB"), packbits_decode(b"\xfd"), packbits_encode("AB")
''', r'''
import random
from itertools import groupby

E, D = packbits_encode, packbits_decode

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert E(b"AAAABCD") == b"\xfdA\x02BCD"
assert E(b"AAB") == b"\x02AAB"
assert E(b"ABBBC") == b"\x00A\xfeB\x00C"
assert E(b"") == b"" and D(b"") == b""
assert D(b"\x80\x00A") == b"A" and D(b"\xfeZ\x01xy") == b"ZZZxy"
assert E(bytearray(b"ZZZ")) == b"\xfeZ" and type(E(bytearray(b"Z"))) is bytes and type(D(bytearray(b"\x00Z"))) is bytes
assert E(b"\x00" * 128) == b"\x81\x00"
assert E(b"\x00" * 130) == b"\x81\x00\x01\x00\x00"
assert E(b"\x07" * 131) == b"\x81\x07\xfe\x07"
assert E(b"\x07" * 129 + b"\x09" * 3) == b"\x81\x07\x00\x07\xfe\x09"
assert E(b"\x07" * 256) == b"\x81\x07\x81\x07"
assert E(bytes(range(130))) == b"\x7f" + bytes(range(128)) + b"\x01\x80\x81"
assert E(b"ABCCD") == b"\x04ABCCD"
assert E(b"AABBCC") == b"\x05AABBCC"
assert E(b"AABBB") == b"\x01AA\xfeB"
assert E(b"Q") == b"\x00Q" and E(b"QQ") == b"\x01QQ" and E(b"QQQ") == b"\xfeQ"
assert E(b"x" + b"y" * 2 + b"z" * 3) == b"\x02xyy\xfez"
lit = bytes((i * 7) % 251 for i in range(127)) + b"\x05\x05"
assert E(lit) == b"\x7f" + lit[:128] + b"\x00\x05"
assert D(b"\xfe\x41") == b"AAA" and D(b"\x81\x00") == b"\x00" * 128 and D(b"\xff\x09") == b"\x09\x09"
assert D(b"\x80") == b"" and D(b"\x80\x80\x00q\x80") == b"q"
assert D(b"\x7f" + bytes(range(128))) == bytes(range(128))
for bad in (b"\x02AB", b"\xfd", b"\x00", b"\x01a", b"\x7f" + bytes(127), b"\x00a\xfe", b"\x80\x01z"):
    assert rej(D, bad), bad
for bad in ("AB", None, [65, 66], memoryview(b"A"), 5, (65,)):
    assert rej(D, bad) and rej(E, bad), bad

def oracle_enc(d):
    out, lit = bytearray(), bytearray()
    def flush():
        if lit:
            out.append(len(lit) - 1)
            out.extend(lit)
            lit.clear()
    for b, g in groupby(d):
        L = len(list(g))
        if L >= 3:
            flush()
            while L >= 3:
                k = min(L, 128)
                out.append(257 - k)
                out.append(b)
                L -= k
        for _ in range(L):
            lit.append(b)
            if len(lit) == 128:
                flush()
    flush()
    return bytes(out)

random.seed(7001)
lens = [1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 5, 7, 20, 127, 128, 129, 130, 131, 200, 255, 256, 257, 300]
for _ in range(300):
    alpha = random.choice([2, 3, 256])
    d = bytearray()
    for _ in range(random.randint(0, 40)):
        if random.random() < 0.3:
            d += bytes(random.randrange(alpha) for _ in range(random.randint(1, 200)))
        else:
            d += bytes([random.randrange(alpha)]) * random.choice(lens)
    d = bytes(d)
    enc = E(d if random.random() < 0.7 else bytearray(d))
    assert enc == oracle_enc(d), d[:60]
    assert D(enc) == d
for _ in range(300):
    stream, want = bytearray(), bytearray()
    for _ in range(random.randint(0, 30)):
        kind = random.random()
        if kind < 0.45:
            n = random.choice([1, 2, 3, 50, 127, 128, random.randint(1, 128)])
            pay = bytes(random.randrange(256) for _ in range(n))
            stream.append(n - 1)
            stream += pay
            want += pay
        elif kind < 0.9:
            n = random.randint(2, 128)
            b = random.randrange(256)
            stream += bytes([257 - n, b])
            want += bytes([b]) * n
        else:
            stream.append(128)
    assert D(bytes(stream)) == bytes(want)
    n = random.randint(2, 128)
    pay = bytes(random.randrange(256) for _ in range(n))
    cut = random.randint(1, n)
    assert rej(D, bytes(stream) + bytes([n - 1]) + pay[:n - cut])
    assert rej(D, bytes(stream) + bytes([random.randint(129, 255)]))
''', r'''
def _bytes(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("bytes or bytearray required")
    return bytes(data)


def packbits_decode(data):
    d = _bytes(data)
    out = bytearray()
    i = 0
    while i < len(d):
        h = d[i]
        i += 1
        if h < 128:
            n = h + 1
            if i + n > len(d):
                raise ValueError("truncated literal")
            out += d[i:i + n]
            i += n
        elif h == 128:
            continue
        else:
            if i >= len(d):
                raise ValueError("truncated repeat")
            out += d[i:i + 1] * (257 - h)
            i += 1
    return bytes(out)


def packbits_encode(data):
    d = _bytes(data)
    n = len(d)

    def run(i):
        j = i
        while j < n and j - i < 128 and d[j] == d[i]:
            j += 1
        return j - i

    out = bytearray()
    i = 0
    while i < n:
        r = run(i)
        if r >= 3:
            out.append(257 - r)
            out.append(d[i])
            i += r
            continue
        j = i
        while j < n and j - i < 128 and (j == i or run(j) < 3):
            j += 1
        out.append(j - i - 1)
        out += d[i:j]
        i = j
    return bytes(out)
''')

task("v7_02_ini_strict", r'''
Write `parse_ini_strict(text)` that parses a strict INI dialect and returns a dict mapping section name to a dict of
key -> value (all str). `text` must be a str (anything else raises ValueError). Only space and tab count as blanks.

Lines: split `text` on "\n"; a line that ends in "\r" loses that one "\r" first. Then, by the line's content with
leading and trailing blanks removed (call it s):
- s empty: ignored.
- s starts with ";" or "#": a comment line, ignored.
- s starts with "[": a section header. s must end with "]"; the name is the text between the brackets with blanks
  stripped, and must be non-empty and contain no "[" or "]". Otherwise ValueError. Names are case-sensitive. The
  header makes that section current and creates it as an empty dict if it does not exist yet; a repeated header
  reopens the existing section.
- otherwise s must contain "=" (else ValueError). The key is the text before the first "=", blanks stripped, then
  lowercased with str.lower(); an empty key raises ValueError. The raw value r is everything after that first "=".
Keys that come before any header go into the section "" (the empty string), which exists in the result only if it got
at least one key. A key that already exists in the current section (after lowercasing, also across a reopened
section) raises ValueError.

Values. Let v be r with blanks stripped.
- If v does not start with a double quote, the value is unquoted: r is cut before the first ";" or "#" that is
  directly preceded by a blank inside r (an inline comment), and the rest, blanks stripped, is the value. A ";" or "#"
  not preceded by a blank (for example `a=b;c`, or `a=;c` where nothing comes before it in r) is part of the value.
  Backslashes are ordinary characters in unquoted values.
- If v starts with a double quote, the value is quoted: characters after the opening quote are taken up to the
  closing unescaped quote. Inside, the escapes \" \\ and \n mean a quote, a backslash and a newline; a backslash
  followed by anything else (or by nothing) raises ValueError, and so does a missing closing quote. After the closing
  quote, the remaining text with blanks stripped must be empty or start with ";" or "#" (a comment); otherwise
  ValueError.

Example: parse_ini_strict("top = 1\n[db]\nHost = local ; c\npath=\"a\\\\b\"\n[ empty ]\n") ==
{"": {"top": "1"}, "db": {"host": "local", "path": "a\\b"}, "empty": {}}.
More: `a=b;c` gives "b;c"; `a = ;c` gives ""; `a=b=c` gives "b=c"; `a="x;y" # z` gives "x;y"; `K e Y = v` gives key
"k e y". ValueError: `[a`, `[]`, `[a]b]`, `novalue`, `=x`, `a="abc`, `a="a\q"`, `a="a" b`, and "a=1\nA=2".
''', r'''
import random

def rej(x):
    try:
        parse_ini_strict(x)
    except ValueError:
        return True
    return False

P = parse_ini_strict
assert P("top = 1\n[db]\nHost = local ; c\npath=\"a\\\\b\"\n[ empty ]\n") == {"": {"top": "1"}, "db": {"host": "local", "path": "a\\b"}, "empty": {}}
assert P("") == {} and P("[s]") == {"s": {}} and P("  ; just comment\n\n\t# x\n") == {}
assert P("a=b;c") == {"": {"a": "b;c"}}
assert P("a = ;c") == {"": {"a": ""}}
assert P("a =;c") == {"": {"a": ";c"}}
assert P("a=b ;c") == {"": {"a": "b"}} and P("a=b\t#c") == {"": {"a": "b"}} and P("a=b#c") == {"": {"a": "b#c"}}
assert P("a=b=c") == {"": {"a": "b=c"}}
assert P("a=\"x;y\" # z") == {"": {"a": "x;y"}} and P("a=\"x\";z") == {"": {"a": "x"}}
assert P("K e Y = v") == {"": {"k e y": "v"}}
assert P("a=\"say \\\"hi\\\"\"") == {"": {"a": "say \"hi\""}}
assert P("a=\"l1\\nl2\"") == {"": {"a": "l1\nl2"}}
assert P("a=c:\\path\\x") == {"": {"a": "c:\\path\\x"}}
assert P("a=\"\"") == {"": {"a": ""}} and P("a=") == {"": {"a": ""}} and P("a =   ") == {"": {"a": ""}}
assert P("a=x \"y\"") == {"": {"a": "x \"y\""}}
assert P("a=1\r\n[s]\r\nb=2\r\n") == {"": {"a": "1"}, "s": {"b": "2"}}
assert P("a=1\r\r\n") == {"": {"a": "1\r"}}
assert P("  [ s t ]  \n x = 1 \n[S]\ny=2\n[s t]\nz=3") == {"s t": {"x": "1", "z": "3"}, "S": {"y": "2"}}
assert P("[s]\na=1\n[t]\na=1") == {"s": {"a": "1"}, "t": {"a": "1"}}
assert P("a=\"#\" ; c") == {"": {"a": "#"}} and P("a = \"q\"   ") == {"": {"a": "q"}}
assert P("a=x\t;y ;z") == {"": {"a": "x"}}
for bad in ("[a", "[]", "[ ]", "[a]b]", "[a[b]", "[a] x", "novalue", "=x", " = x", "a=\"abc", "a=\"a\\q\"", "a=\"a\" b",
            "a=1\nA=2", "[s]\na=1\n[s]\na=2", "a=\"a\\\"", "a=\"\\", "x\n[s]", "a=1\n  junk", "[", "]", "a=\"x\"y"):
    assert rej(bad), bad
for bad in (None, b"a=1", 5, ["a=1"]):
    assert rej(bad), bad

random.seed(7002)
KCH = "abcdefgXYZ019_.- "
VCH = "abcxyz09 ;#\"\\=[]\t"
def word(ch, lo, hi):
    return "".join(random.choice(ch) for _ in range(random.randint(lo, hi)))
def key():
    while True:
        k = word(KCH, 1, 8).strip(" ")
        if k and k[0] not in ";#[":
            return k
def quote(v):
    return "\"" + v.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\""
def needs_quote(v):
    if v != v.strip(" \t") or v.startswith("\""):
        return True
    return any(v[i] in ";#" and (i == 0 or v[i - 1] in " \t") for i in range(len(v)))
for _ in range(250):
    want, lines = {}, []
    secs = [""] + [word("abcST12 _", 1, 6).strip(" ") or "z" for _ in range(random.randint(0, 4))]
    for s in secs:
        d = want.setdefault(s, {})
        if s == "":
            pass
        nk = random.randint(0, 5)
        chunk = []
        for _ in range(nk):
            k = key()
            if k.lower() in d:
                continue
            v = word(VCH, 0, 10) if random.random() < 0.8 else word(VCH, 0, 3) + "\n" + word(VCH, 0, 3)
            d[k.lower()] = v
            kk = "".join(c.upper() if random.random() < 0.3 else c for c in k)
            body = quote(v) if needs_quote(v) or "\n" in v or random.random() < 0.3 else v
            sp = lambda: random.choice(["", " ", "  ", "\t"])
            line = sp() + kk + sp() + "=" + sp() + body
            if random.random() < 0.3:
                line += random.choice([" ", "\t"]) + random.choice(";#") + word(VCH, 0, 6)
            elif body.startswith("\"") and random.random() < 0.2:
                line += random.choice(";#") + word(VCH, 0, 4)
            chunk.append(line)
        if s != "":
            lines.append(random.choice(["", " ", "\t"]) + "[" + random.choice(["", " "]) + s + random.choice(["", " "]) + "]")
        elif not d:
            del want[""]
        split = random.randint(0, len(chunk))
        lines += chunk[:split]
        if s != "" and split < len(chunk) and random.random() < 0.5:
            lines.append("[" + s + "]")
        lines += chunk[split:]
        for _ in range(random.randint(0, 2)):
            lines.insert(random.randint(0, len(lines)), random.choice(["", "  ", random.choice(" \t") + random.choice(";#") + word(VCH, 0, 8), ";" + word(VCH, 0, 8)]))
    eol = random.choice(["\n", "\r\n"])
    text = eol.join(lines) + random.choice(["", eol])
    got = P(text)
    assert got == want, (text, got, want)
''', r'''
BL = " \t"


def _value(r):
    s = r.strip(BL)
    if not s.startswith('"'):
        for i in range(1, len(r)):
            if r[i] in ";#" and r[i - 1] in BL:
                return r[:i].strip(BL)
        return s
    out = []
    i = 1
    while True:
        if i >= len(s):
            raise ValueError("missing closing quote")
        c = s[i]
        if c == "\\":
            if i + 1 >= len(s) or s[i + 1] not in '"\\n':
                raise ValueError("bad escape")
            out.append({'"': '"', "\\": "\\", "n": "\n"}[s[i + 1]])
            i += 2
        elif c == '"':
            break
        else:
            out.append(c)
            i += 1
    rest = s[i + 1:].strip(BL)
    if rest and rest[0] not in ";#":
        raise ValueError("text after the closing quote")
    return "".join(out)


def parse_ini_strict(text):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    out = {}
    sec = ""
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        s = line.strip(BL)
        if not s or s[0] in ";#":
            continue
        if s[0] == "[":
            if len(s) < 2 or not s.endswith("]"):
                raise ValueError("bad section header")
            name = s[1:-1].strip(BL)
            if not name or "[" in name or "]" in name:
                raise ValueError("bad section name")
            sec = name
            out.setdefault(sec, {})
            continue
        if "=" not in s:
            raise ValueError("not a key line")
        k, r = line.split("=", 1)
        k = k.strip(BL).lower()
        if not k:
            raise ValueError("empty key")
        v = _value(r)
        d = out.setdefault(sec, {})
        if k in d:
            raise ValueError("duplicate key")
        d[k] = v
    return out
''')

task("v7_03_semver_order", r'''
Write `semver_sort(versions)` that validates Semantic Versioning 2.0.0 strings and returns them sorted by precedence.
`versions` is a list or tuple of str; anything else, or any item that is not a str or not a valid version, raises
ValueError. The result is a new list; versions of equal precedence keep their input order (stable).

Syntax: MAJOR.MINOR.PATCH, optionally followed by "-" and a PRERELEASE, optionally followed by "+" and BUILD metadata.
- MAJOR, MINOR, PATCH: non-negative integers written with ASCII digits only, no leading zeros ("0" is fine, "01" is
  not). They can be arbitrarily large.
- The first "+" in the string starts BUILD; in what comes before it, the first "-" starts PRERELEASE. So hyphens may
  appear inside prerelease and build identifiers ("1.0.0-alpha-1" has prerelease "alpha-1").
- PRERELEASE and BUILD are each one or more identifiers separated by ".". Every identifier is non-empty and uses only
  ASCII letters, ASCII digits and "-". A prerelease identifier made only of digits must not have a leading zero
  ("0" is fine, "01" is not; "01a" is fine since it is not all digits). Build identifiers may have leading zeros.
- Nothing else is allowed: no "v" prefix, no blanks, no empty part (so "1.0.0-" and "1.0.0+" are invalid).

Precedence (BUILD is ignored entirely):
1. Compare MAJOR, MINOR, PATCH numerically, in that order.
2. If those are equal, a version with a prerelease has lower precedence than the same version without one.
3. Two prereleases are compared identifier by identifier from left to right: two all-digit identifiers numerically;
   two other identifiers by ASCII order of their characters (so "B" < "a" and "-" < "0"); an all-digit identifier is
   lower than any other identifier. If all compared identifiers are equal, the version with fewer identifiers is lower.

Example: semver_sort(["1.0.0", "1.0.0-rc.1", "1.0.0-beta.11", "1.0.0-alpha", "1.0.0-beta.2", "1.0.0-alpha.1"]) ==
["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"].
semver_sort(["1.0.0+b", "1.0.0", "1.0.0+a"]) == ["1.0.0+b", "1.0.0", "1.0.0+a"] (equal precedence, input order).
ValueError: semver_sort(["1.0"]), semver_sort(["01.0.0"]), semver_sort(["1.0.0-01"]), semver_sort(["v1.0.0"]),
semver_sort("1.0.0").
''', r'''
import random
from functools import cmp_to_key

def rej(x):
    try:
        semver_sort(x)
    except ValueError:
        return True
    return False

S = semver_sort
chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
assert S(["1.0.0", "1.0.0-rc.1", "1.0.0-beta.11", "1.0.0-alpha", "1.0.0-beta.2", "1.0.0-alpha.1"]) == ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0"]
assert S(list(reversed(chain))) == chain and S(tuple(chain)) == chain
assert S(["1.0.0+b", "1.0.0", "1.0.0+a"]) == ["1.0.0+b", "1.0.0", "1.0.0+a"]
assert S([]) == [] and type(S(())) is list
inp = ["2.0.0", "1.10.0", "1.9.0"]
out = S(inp)
assert out == ["1.9.0", "1.10.0", "2.0.0"] and inp == ["2.0.0", "1.10.0", "1.9.0"] and out is not inp
assert S(["1.0.99999999999999999999", "1.0.100000000000000000000", "1.0.9"]) == ["1.0.9", "1.0.99999999999999999999", "1.0.100000000000000000000"]
assert S(["1.0.0-a", "1.0.0-B"]) == ["1.0.0-B", "1.0.0-a"]
assert S(["1.0.0-a0", "1.0.0-a-"]) == ["1.0.0-a-", "1.0.0-a0"]
assert S(["1.0.0-a", "1.0.0-1"]) == ["1.0.0-1", "1.0.0-a"]
assert S(["1.0.0-10", "1.0.0-9", "1.0.0-1a"]) == ["1.0.0-9", "1.0.0-10", "1.0.0-1a"]
assert S(["1.0.0-01a", "1.0.0-0"]) == ["1.0.0-0", "1.0.0-01a"]
assert S(["1.0.0-alpha-1", "1.0.0-alpha"]) == ["1.0.0-alpha", "1.0.0-alpha-1"]
assert S(["1.0.0-a.b.c", "1.0.0-a.b"]) == ["1.0.0-a.b", "1.0.0-a.b.c"]
assert S(["1.0.0+001.x-y", "0.9.9-z+0", "1.0.0-x+y-z"]) == ["0.9.9-z+0", "1.0.0-x+y-z", "1.0.0+001.x-y"]
assert S(["1.0.0-rc+build", "1.0.0-rc"]) == ["1.0.0-rc+build", "1.0.0-rc"]
assert S(["0.0.0", "0.0.0-0"]) == ["0.0.0-0", "0.0.0"]
assert S(["1.0.0--", "1.0.0-0"]) == ["1.0.0-0", "1.0.0--"]
bad_items = ["1.0", "1.0.0.0", "01.0.0", "1.00.0", "1.0.00", "1.0.0-", "1.0.0+", "1.0.0-a..b", "1.0.0+a..b", "v1.0.0",
             " 1.0.0", "1.0.0 ", "1.0.0-a_b", "1.0.0-01", "1.0.0-a.01", "1.\uff10.0", "1.\u00b2.0", "1.0.0-\u00e9", "", "1..0",
             "-1.0.0", "1.0.0-+", "+1.0.0", "1.0.0+a+b", "1.0.0-a b", "1.0.a", "a.b.c", "1.0.0.", ".1.0.0", "1.0.0-.a", "1.0.0+.a"]
for b in bad_items:
    assert rej([b]), b
    assert rej(["1.0.0", b]), b
for b in ("1.0.0", None, {"1.0.0"}, 3):
    assert rej(b), b
for b in ([1], [None], ["1.0.0", b"1.0.0"]):
    assert rej(b), b
assert S(["1.0.0+0001", "1.0.0+a-b.c"]) == ["1.0.0+0001", "1.0.0+a-b.c"]

def ident_cmp(x, y):
    xd, yd = x.isdigit(), y.isdigit()
    if xd and yd:
        return (int(x) > int(y)) - (int(x) < int(y))
    if xd != yd:
        return -1 if xd else 1
    return (x > y) - (x < y)

def cmp(a, b):
    def split(v):
        v = v.split("+", 1)[0]
        core, _, pre = v.partition("-")
        return [int(p) for p in core.split(".")], (pre.split(".") if "-" in v else None)
    (ca, pa), (cb, pb) = split(a), split(b)
    if ca != cb:
        return -1 if ca < cb else 1
    if pa is None or pb is None:
        return 0 if pa is pb else (-1 if pb is None else 1)
    for x, y in zip(pa, pb):
        c = ident_cmp(x, y)
        if c:
            return c
    return (len(pa) > len(pb)) - (len(pa) < len(pb))

random.seed(7003)
AL = "abzAZ-"
def num(big=False):
    r = random.random()
    if r < 0.4:
        return str(random.randint(0, 3))
    return str(random.randint(0, 10**(25 if big else 3)))
def pre_id():
    r = random.random()
    if r < 0.4:
        return num()
    s = "".join(random.choice(AL + "0123") for _ in range(random.randint(1, 4)))
    return s if not s.isdigit() or s == str(int(s)) else "x" + s
def build_id():
    return "".join(random.choice(AL + "0123") for _ in range(random.randint(1, 4)))
def version():
    v = ".".join(num(random.random() < 0.1) for _ in range(3))
    if random.random() < 0.6:
        v += "-" + ".".join(pre_id() for _ in range(random.randint(1, 4)))
    if random.random() < 0.3:
        v += "+" + ".".join(build_id() for _ in range(random.randint(1, 3)))
    return v
for _ in range(250):
    base = [version() for _ in range(random.randint(1, 6))]
    vs = [random.choice(base) if random.random() < 0.3 else version() for _ in range(random.randint(0, 25))]
    random.shuffle(vs)
    assert S(vs) == sorted(vs, key=cmp_to_key(cmp)), vs
    if vs:
        i = random.randrange(len(vs))
        mut = random.choice([lambda s: s + ".", lambda s: "0" + s, lambda s: s.replace(".", "..", 1), lambda s: s + "+",
                             lambda s: s + " ", lambda s: s.replace(".", "_", 1)])
        broken = vs[:i] + [mut(vs[i])] + vs[i + 1:]
        assert rej(broken), broken[i]
''', r'''
import re

_ID = re.compile(r"[0-9A-Za-z-]+")
_NUM = re.compile(r"0|[1-9][0-9]*")
_DIG = re.compile(r"[0-9]+")


def _key(v):
    if not isinstance(v, str):
        raise ValueError("not a str")
    main, plus, build = v.partition("+")
    if plus and not all(_ID.fullmatch(x) for x in build.split(".")):
        raise ValueError("bad build")
    core, dash, pre = main.partition("-")
    parts = core.split(".")
    if len(parts) != 3 or not all(_NUM.fullmatch(p) for p in parts):
        raise ValueError("bad core")
    ids = []
    if dash:
        for x in pre.split("."):
            if not _ID.fullmatch(x):
                raise ValueError("bad prerelease")
            if _DIG.fullmatch(x):
                if not _NUM.fullmatch(x):
                    raise ValueError("leading zero")
                ids.append((0, int(x), ""))
            else:
                ids.append((1, 0, x))
    return (tuple(int(p) for p in parts), 0 if dash else 1, tuple(ids))


def semver_sort(versions):
    if not isinstance(versions, (list, tuple)):
        raise ValueError("versions must be a list or tuple")
    keyed = [(_key(v), v) for v in versions]
    return [v for _, v in sorted(keyed, key=lambda kv: kv[0])]
''')

task("v7_04_partition_rank", r'''
Write two functions about integer partitions: `count_partitions(n, max_part=None, distinct=False)` and
`kth_partition(n, k, max_part=None, distinct=False)`.

A partition of n is a tuple of positive ints that sum to n, written in non-increasing order (strictly decreasing when
`distinct` is True). With `max_part` given, every part must be <= max_part; None means no limit. n = 0 has exactly one
partition, the empty tuple (also for max_part = 0).

`count_partitions` returns how many such partitions exist. `kth_partition` returns the partition at index k (0-based)
in the list of all such partitions sorted in ascending lexicographic order of the tuples (compare first parts, then
second parts, and so on, as Python compares tuples). For n = 4 that list is (1, 1, 1, 1), (2, 1, 1), (2, 2), (3, 1),
(4,), so kth_partition(4, 2) == (2, 2).

Arguments: n is an int >= 0; k is an int; max_part is None or an int >= 0; distinct is a bool. A bool is never
accepted where an int is required. A wrong type, a negative n or max_part, or k outside 0 <= k < count raises
ValueError. n can be up to 300, so counts and k can be very large (count_partitions(300) is 9253082936723602): build
the answer part by part from counts, never by listing partitions.

Examples:
- count_partitions(5) == 7, count_partitions(5, distinct=True) == 3, count_partitions(5, max_part=2) == 3
- count_partitions(0) == 1, count_partitions(3, max_part=0) == 0
- kth_partition(5, 0) == (1, 1, 1, 1, 1), kth_partition(5, 6) == (5,)
- kth_partition(5, 1, distinct=True) == (4, 1), kth_partition(6, 0, distinct=True) == (3, 2, 1)
- kth_partition(7, 2, max_part=3) == (2, 2, 1, 1, 1), kth_partition(0, 0) == ()
- ValueError: kth_partition(4, 5), kth_partition(4, -1), count_partitions(-1), count_partitions(True)
''', r'''
import random

def rej(f, *a, **kw):
    try:
        f(*a, **kw)
    except ValueError:
        return True
    return False

C, K = count_partitions, kth_partition
assert C(5) == 7 and C(5, distinct=True) == 3 and C(5, max_part=2) == 3
assert C(0) == 1 and C(3, max_part=0) == 0 and C(0, max_part=0) == 1 and C(0, distinct=True) == 1
assert K(5, 0) == (1, 1, 1, 1, 1) and K(5, 6) == (5,)
assert K(5, 1, distinct=True) == (4, 1) and K(6, 0, distinct=True) == (3, 2, 1)
assert K(7, 2, max_part=3) == (2, 2, 1, 1, 1) and K(0, 0) == () and K(0, 0, max_part=0) == ()
assert [K(4, i) for i in range(5)] == [(1, 1, 1, 1), (2, 1, 1), (2, 2), (3, 1), (4,)]
assert K(4, 2) == (2, 2) and type(K(3, 0)) is tuple and C(300) == 9253082936723602
assert rej(K, 4, 5) and rej(K, 4, -1) and rej(C, -1) and rej(C, True) and rej(K, 3, 0, max_part=0)
for bad in (1.0, "3", None, False):
    assert rej(C, bad) and rej(K, bad, 0) and rej(K, 3, bad)
for bad in (-1, 1.5, True, "2"):
    assert rej(C, 5, max_part=bad) and rej(K, 5, 0, max_part=bad)
for bad in (0, 1, None, "yes"):
    assert rej(C, 5, distinct=bad) and rej(K, 5, 0, distinct=bad)

def gen(n, cap, distinct):
    if n == 0:
        yield ()
        return
    for p in range(min(n, cap), 0, -1):
        for rest in gen(n - p, p - 1 if distinct else p, distinct):
            yield (p,) + rest

for n in range(0, 13):
    for mp in [None] + list(range(0, n + 2)):
        for dist in (False, True):
            allp = sorted(gen(n, n if mp is None else mp, dist))
            assert C(n, mp, dist) == len(allp), (n, mp, dist)
            assert [K(n, i, mp, dist) for i in range(len(allp))] == allp, (n, mp, dist)
            assert rej(K, n, len(allp), mp, dist)

def pent(N):
    p = [1] + [0] * N
    for n in range(1, N + 1):
        k, s = 1, 0
        while True:
            for g in (k * (3 * k - 1) // 2, k * (3 * k + 1) // 2):
                if g > n:
                    break
                s += (-1) ** (k + 1) * p[n - g]
            if k * (3 * k - 1) // 2 > n:
                break
            k += 1
        p[n] = s
    return p

def distinct_counts(N):
    poly = [1] + [0] * N
    for part in range(1, N + 1):
        for s in range(N, part - 1, -1):
            poly[s] += poly[s - part]
    return poly

PN, QN = pent(300), distinct_counts(300)
random.seed(7004)
for n in [13, 50, 100, 199, 200, 299, 300] + random.sample(range(14, 300), 8):
    assert C(n) == PN[n] and C(n, distinct=True) == QN[n], n
assert C(100) == 190569292 and C(100, distinct=True) == 444793

def valid(t, n, mp, dist):
    if sum(t) != n or any(x < 1 for x in t):
        return False
    if mp is not None and t and t[0] > mp:
        return False
    return all(a > b if dist else a >= b for a, b in zip(t, t[1:]))

for _ in range(60):
    n = random.randint(20, 300)
    dist = random.random() < 0.4
    mp = random.choice([None, None, random.randint(1, n), random.randint(1, 25)])
    tot = C(n, mp, dist)
    if tot == 0:
        assert rej(K, n, 0, mp, dist)
        continue
    for k in {0, tot - 1, random.randrange(tot), random.randrange(tot)}:
        t = K(n, k, mp, dist)
        assert valid(t, n, mp, dist), (n, k, mp, dist, t)
        if k + 1 < tot:
            assert t < K(n, k + 1, mp, dist)
    if not dist:
        m = n if mp is None else min(mp, n)
        assert K(n, 0, mp, dist) == (1,) * n
        assert K(n, tot - 1, mp, dist) == (m,) * (n // m) + ((n % m,) if n % m else ())
''', r'''
_TABLES = {}


def _table(n, distinct):
    t = _TABLES.get(distinct)
    if t is not None and len(t) > n:
        return t
    N = max(n, 16)
    # c[m][s]: partitions of s with every part <= m (distinct parts when distinct)
    c = [[0] * (N + 1) for _ in range(N + 1)]
    c[0][0] = 1
    for m in range(1, N + 1):
        prev, row = c[m - 1], c[m]
        for s in range(N + 1):
            v = prev[s]
            if s >= m:
                v += prev[s - m] if distinct else row[s - m]
            row[s] = v
    _TABLES[distinct] = c
    return c


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _args(n, max_part, distinct):
    if not _isint(n) or n < 0:
        raise ValueError("n must be an int >= 0")
    if max_part is not None and (not _isint(max_part) or max_part < 0):
        raise ValueError("max_part must be None or an int >= 0")
    if not isinstance(distinct, bool):
        raise ValueError("distinct must be a bool")
    return n if max_part is None else min(max_part, n)


def count_partitions(n, max_part=None, distinct=False):
    m = _args(n, max_part, distinct)
    return _table(n, distinct)[m][n]


def kth_partition(n, k, max_part=None, distinct=False):
    m = _args(n, max_part, distinct)
    if not _isint(k):
        raise ValueError("k must be an int")
    c = _table(n, distinct)
    if not 0 <= k < c[m][n]:
        raise ValueError("k out of range")
    out, rem, cap = [], n, m
    while rem > 0:
        for p in range(1, min(rem, cap) + 1):
            sub = rem - p
            lim = p - 1 if distinct else p
            cnt = c[min(lim, sub)][sub]
            if k < cnt:
                out.append(p)
                rem, cap = sub, lim
                break
            k -= cnt
    return tuple(out)
''')

task("v7_05_digit_rules", r'''
Write `count_special(lo, hi, m)` that counts the integers x with lo <= x <= hi that satisfy both rules:
1. the sum of the decimal digits of x is divisible by m;
2. no two adjacent digits in the decimal representation of x are equal (so 121 is fine, 112 is not).

Decimal representation means the usual one without leading zeros: 0 is the single digit "0" (digit sum 0, so 0 always
satisfies both rules), 7 is "7", 1010 is "1010".

Arguments: lo and hi are ints with 0 <= lo <= 10**18 and 0 <= hi <= 10**18; m is an int with 1 <= m <= 100. A bool is
never accepted as an int. A wrong type or a value outside those ranges raises ValueError. If lo > hi the answer is 0.
The range can hold up to 10**18 numbers, so testing them one by one is impossible; the function has to count by digit
position (and stay fast when it is called many times with the same m).

Examples:
- count_special(0, 9, 1) == 10
- count_special(10, 99, 1) == 81 (two-digit numbers whose digits differ)
- count_special(0, 0, 7) == 1
- count_special(5, 3, 2) == 0
- count_special(1, 30, 3) == 10 (3, 6, 9, 12, 15, 18, 21, 24, 27, 30)
- count_special(100, 130, 2) == 11
- count_special(0, 10**18, 1) == 168856464709124011
- ValueError: count_special(-1, 5, 2), count_special(0, 10**18 + 1, 2), count_special(0, 5, 0), count_special(0, 5, True)
''', r'''
import random

def rej(*a):
    try:
        count_special(*a)
    except ValueError:
        return True
    return False

def ok(x, m):
    s = str(x)
    return sum(map(int, s)) % m == 0 and all(a != b for a, b in zip(s, s[1:]))

def brute(lo, hi, m):
    return sum(1 for x in range(lo, hi + 1) if ok(x, m))

def odp(N, m):
    if N < 0:
        return 0
    st = {(-1, 0, True, False): 1}
    for ch in str(N):
        top, nst = int(ch), {}
        for (p, s, t, sd), c in st.items():
            for d in range((top if t else 9) + 1):
                if sd and d == p:
                    continue
                nsd = sd or d != 0
                key = (d if nsd else -1, (s + d) % m, t and d == top, nsd)
                nst[key] = nst.get(key, 0) + c
        st = nst
    return sum(c for (p, s, t, sd), c in st.items() if s == 0)

F = count_special
assert F(0, 9, 1) == 10 and F(10, 99, 1) == 81 and F(0, 0, 7) == 1 and F(5, 3, 2) == 0
assert F(1, 30, 3) == 10 and F(0, 10**18, 1) == 168856464709124011
assert F(100, 130, 2) == 11
assert F(0, 10**18, 1) == odp(10**18, 1)
assert F(10**18, 10**18, 1) == 0 and F(0, 0, 1) == 1 and F(1, 1, 1) == 1 and F(11, 11, 1) == 0
assert F(10**18, 0, 5) == 0
for bad in [(-1, 5, 2), (0, 10**18 + 1, 2), (0, 5, 0), (0, 5, True), (0, 5, 101), (10**18 + 1, 0, 3), (1.0, 5, 2),
            (0, "5", 2), (True, 5, 2), (0, 5, 2.0), (None, 5, 2), (0, 5, -3)]:
    assert rej(*bad), bad

random.seed(7005)
for _ in range(40):
    m = random.choice([1, 2, 3, 5, 7, 9, 10, 11, 13, 17, 23, 50, 100])
    lo = random.choice([0, 1, random.randint(0, 2000)])
    hi = lo + random.randint(0, 1500)
    assert F(lo, hi, m) == brute(lo, hi, m), (lo, hi, m)
for m in (1, 3, 9):
    for _ in range(2):
        hi = random.randint(10**9, 10**18)
        lo = random.choice([0, random.randint(0, hi)])
        assert F(lo, hi, m) == odp(hi, m) - odp(lo - 1, m), (lo, hi, m)
for hi in (10**17, 98765432109876543, 121212121212121212):
    assert F(0, hi, 7) == odp(hi, 7), hi
for _ in range(60):
    m = random.choice([1, 7, 12, 100])
    a = random.randint(0, 10**18)
    b = random.randint(a, 10**18)
    c = random.randint(a, b)
    assert F(a, b, m) == F(a, c, m) + F(c + 1, b, m) if c < b else F(a, b, m) == F(a, c, m)
''', r'''
from functools import lru_cache

LIMIT = 10 ** 18


@lru_cache(maxsize=None)
def _free(rem, prev, need, m):
    # digit strings of length rem, first digit != prev, no equal neighbours, digit sum == need (mod m)
    if rem == 0:
        return 1 if need == 0 else 0
    return sum(_free(rem - 1, d, (need - d) % m, m) for d in range(10) if d != prev)


def _upto(N, m):
    if N < 0:
        return 0
    if N == 0:
        return 1
    total = 1  # x = 0
    ds = [int(c) for c in str(N)]
    L = len(ds)
    for length in range(1, L):
        total += sum(_free(length - 1, d, (-d) % m, m) for d in range(1, 10))
    prev, s = -1, 0
    for i, top in enumerate(ds):
        for d in range(1 if i == 0 else 0, top):
            if d != prev:
                total += _free(L - i - 1, d, (-(s + d)) % m, m)
        if top == prev:
            break
        prev, s = top, s + top
    else:
        if s % m == 0:
            total += 1
    return total


def count_special(lo, hi, m):
    for v in (lo, hi, m):
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("ints required")
    if not (0 <= lo <= LIMIT and 0 <= hi <= LIMIT and 1 <= m <= 100):
        raise ValueError("out of range")
    if lo > hi:
        return 0
    return _upto(hi, m) - _upto(lo - 1, m)
''')

task("v7_06_route_lexmin", r'''
Write `route_info(n, edges, src, dst)` for a directed graph with nodes 0..n-1. `edges` is a list of (u, v, w) tuples
(lists of three are accepted too): an edge from u to v with weight w. Parallel edges and self-loops are allowed.

Return None if dst cannot be reached from src. Otherwise return a tuple (dist, count, path):
- dist: the length of a shortest path from src to dst (the sum of its edge weights);
- count: the number of distinct shortest paths, modulo 1_000_000_007. Paths are sequences of edges, so two parallel
  edges with the same weight on a shortest path give two different paths;
- path: among all shortest paths, the one whose list of nodes is lexicographically smallest (compare the node lists
  element by element, as Python compares lists), as a list of node ids starting with src and ending with dst.
If src == dst the answer is (0, 1, [src]).

Validation (ValueError): n is not an int >= 1; edges is not a list or tuple; an edge is not a tuple or list of three
ints; u or v outside 0..n-1; w < 1; src or dst not an int in 0..n-1. A bool is never accepted as an int.

Sizes: up to 20000 nodes and 100000 edges, weights up to 10**9, and the number of shortest paths can be astronomically
large. Use Dijkstra-style shortest paths; do not enumerate paths.

Examples:
- route_info(4, [(0, 1, 1), (0, 2, 1), (1, 3, 1), (2, 3, 1)], 0, 3) == (2, 2, [0, 1, 3])
- route_info(3, [(0, 1, 2), (0, 1, 2), (1, 2, 1), (0, 2, 4)], 0, 2) == (3, 2, [0, 1, 2])
- route_info(3, [(0, 2, 5), (0, 1, 1), (1, 2, 4)], 0, 2) == (5, 2, [0, 1, 2])
- route_info(3, [(1, 0, 1)], 0, 1) is None
- route_info(2, [(0, 0, 3)], 1, 1) == (0, 1, [1])
- ValueError: route_info(2, [(0, 2, 1)], 0, 1), route_info(2, [(0, 1, 0)], 0, 1), route_info(0, [], 0, 0)
''', r'''
import random, heapq
from math import comb

MOD = 1_000_000_007
R = route_info

def rej(*a):
    try:
        R(*a)
    except ValueError:
        return True
    return False

assert R(4, [(0, 1, 1), (0, 2, 1), (1, 3, 1), (2, 3, 1)], 0, 3) == (2, 2, [0, 1, 3])
assert R(3, [(0, 1, 2), (0, 1, 2), (1, 2, 1), (0, 2, 4)], 0, 2) == (3, 2, [0, 1, 2])
assert R(3, [(0, 2, 5), (0, 1, 1), (1, 2, 4)], 0, 2) == (5, 2, [0, 1, 2])
assert R(3, [(1, 0, 1)], 0, 1) is None and R(1, [], 0, 0) == (0, 1, [0])
assert R(2, [(0, 0, 3)], 1, 1) == (0, 1, [1])
assert R(3, [[0, 2, 1], [0, 1, 1], [1, 2, 1]], 0, 2) == (1, 1, [0, 2])
assert R(5, [(0, 3, 1), (0, 2, 1), (3, 4, 1), (2, 4, 1), (0, 1, 3), (1, 4, 0 + 1)], 0, 4) == (2, 2, [0, 2, 4])
assert R(3, [(0, 1, 1), (1, 1, 1), (1, 2, 1)], 0, 2) == (2, 1, [0, 1, 2])
assert R(2, [(0, 1, 10**9)] * 5, 0, 1) == (10**9, 5, [0, 1])
for bad in [(2, [(0, 2, 1)], 0, 1), (2, [(0, 1, 0)], 0, 1), (0, [], 0, 0), (2, [(0, 1)], 0, 1), (2, [(0, 1, 1.0)], 0, 1),
            (2, [(0, 1, True)], 0, 1), (2, [(-1, 1, 1)], 0, 1), (2, [], 0, 2), (2, [], -1, 0), (True, [], 0, 0),
            (2, None, 0, 1), (2, [(0, 1, 1, 1)], 0, 1), (2, [], 0, 1.0), (2.0, [], 0, 1), (2, [None], 0, 1), (2, [(0, 1, -5)], 0, 1)]:
    assert rej(*bad), bad

def brute(n, edges, s, t):
    out = []
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    def dfs(u, cost, nodes, seen):
        if u == t:
            out.append((cost, list(nodes)))
            return
        for v, w in adj[u]:
            if v not in seen:
                seen.add(v); nodes.append(v)
                dfs(v, cost + w, nodes, seen)
                nodes.pop(); seen.discard(v)
    if s == t:
        return (0, 1, [s])
    dfs(s, 0, [s], {s})
    if not out:
        return None
    d = min(c for c, _ in out)
    best = [p for c, p in out if c == d]
    return (d, len(best) % MOD, min(best))

random.seed(7006)
for _ in range(300):
    n = random.randint(1, 7)
    edges = [(random.randrange(n), random.randrange(n), random.randint(1, 4)) for _ in range(random.randint(0, 14))]
    s, t = random.randrange(n), random.randrange(n)
    assert R(n, edges, s, t) == brute(n, edges, s, t), (n, edges, s, t)

def array_dijkstra(n, edges, s):
    INF = float("inf")
    adj = [dict() for _ in range(n)]
    for u, v, w in edges:
        if v not in adj[u] or w < adj[u][v]:
            adj[u][v] = w
    dist, done = [INF] * n, [False] * n
    dist[s] = 0
    for _ in range(n):
        u = min((i for i in range(n) if not done[i]), key=lambda i: dist[i])
        if dist[u] == INF:
            break
        done[u] = True
        for v, w in adj[u].items():
            dist[v] = min(dist[v], dist[u] + w)
    return dist

for _ in range(4):
    n = 250
    edges = [(random.randrange(n), random.randrange(n), random.randint(1, 50)) for _ in range(1500)]
    s = random.randrange(n)
    dist = array_dijkstra(n, edges, s)
    for t in random.sample(range(n), 25):
        r = R(n, edges, s, t)
        if dist[t] == float("inf"):
            assert r is None
            continue
        d, c, p = r
        assert d == dist[t] and p[0] == s and p[-1] == t and 1 <= c < MOD
        wmin = {}
        for u, v, w in edges:
            wmin[(u, v)] = min(w, wmin.get((u, v), w))
        assert sum(wmin[(a, b)] for a, b in zip(p, p[1:])) == d

H = W = 60
edges = []
for r in range(H):
    for c in range(W):
        if c + 1 < W:
            edges.append((r * W + c, r * W + c + 1, 1))
        if r + 1 < H:
            edges.append((r * W + c, (r + 1) * W + c, 1))
random.shuffle(edges)
d, c, p = R(H * W, edges, 0, H * W - 1)
assert d == H + W - 2 and c == comb(H + W - 2, H - 1) % MOD
assert p == list(range(W)) + [r * W + W - 1 for r in range(1, H)]
n = 20000
chain = [(i, i + 1, 7) for i in range(n - 1)] + [(i, i + 1, 7) for i in range(0, n - 1, 2)]
d, c, p = R(n, chain, 0, n - 1)
assert d == 7 * (n - 1) and c == pow(2, (n - 1 + 1) // 2, MOD) and p == list(range(n))
''', r'''
import heapq

MOD = 1_000_000_007


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _dijkstra(n, adj, start):
    dist = [None] * n
    dist[start] = 0
    pq = [(0, start)]
    done = [False] * n
    while pq:
        d, u = heapq.heappop(pq)
        if done[u]:
            continue
        done[u] = True
        for v, w in adj[u]:
            nd = d + w
            if dist[v] is None or nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def route_info(n, edges, src, dst):
    if not _isint(n) or n < 1:
        raise ValueError("n must be an int >= 1")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a list or tuple")
    adj = [[] for _ in range(n)]
    radj = [[] for _ in range(n)]
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 3 or not all(_isint(x) for x in e):
            raise ValueError("bad edge")
        u, v, w = e
        if not (0 <= u < n and 0 <= v < n) or w < 1:
            raise ValueError("bad edge")
        adj[u].append((v, w))
        radj[v].append((u, w))
    for x in (src, dst):
        if not _isint(x) or not 0 <= x < n:
            raise ValueError("bad endpoint")
    ds = _dijkstra(n, adj, src)
    if ds[dst] is None:
        return None
    if src == dst:
        return (0, 1, [src])
    dt = _dijkstra(n, radj, dst)
    D = ds[dst]
    cnt = [0] * n
    cnt[src] = 1
    for u in sorted((i for i in range(n) if ds[i] is not None), key=lambda i: ds[i]):
        if cnt[u]:
            for v, w in adj[u]:
                if ds[u] + w == ds[v]:
                    cnt[v] = (cnt[v] + cnt[u]) % MOD
    path = [src]
    u = src
    while u != dst:
        u = min(v for v, w in adj[u] if dt[v] is not None and ds[u] + w + dt[v] == D)
        path.append(u)
    return (D, cnt[dst], path)
''')

task("v7_07_rect_union", r'''
Write `union_area_perimeter(rects)` that returns the area and the perimeter of the union of axis-aligned rectangles,
as a tuple of two ints (area, perimeter).

`rects` is a list or tuple; each rectangle is a tuple or list of four ints (x1, y1, x2, y2) giving two opposite
corners in any order (so (3, 5, 1, 2) is the same rectangle as (1, 2, 3, 5)). A rectangle with zero width or zero
height is ignored completely: it adds no area and no perimeter, even where it touches or crosses other rectangles.
Coordinates satisfy |c| <= 10**9; a bool is never accepted as an int. A wrong type or a coordinate out of range raises
ValueError. There can be up to 200 rectangles.

Area is the area of the union. Perimeter is the total length of the boundary of the union, counting the boundaries of
holes too. Where two rectangles share a stretch of edge (they touch from opposite sides), that stretch is inside the
union and not part of the boundary. Rectangles that touch only at a corner keep their full boundaries at that corner.

Equivalently: draw the grid lines through every x and every y coordinate that occurs; each grid cell is either
covered by some rectangle or not; the area is the total area of covered cells, and the perimeter is the total length
of cell edges that have a covered cell on one side and an uncovered cell (or the outside) on the other.

Examples:
- union_area_perimeter([(0, 0, 2, 2)]) == (4, 8)
- union_area_perimeter([(0, 0, 2, 2), (1, 1, 3, 3)]) == (7, 12)
- union_area_perimeter([(0, 0, 1, 1), (1, 0, 2, 1)]) == (2, 6) (shared edge)
- union_area_perimeter([(0, 0, 1, 1), (1, 1, 2, 2)]) == (2, 8) (corner only)
- union_area_perimeter([(0, 0, 3, 1), (0, 2, 3, 3), (0, 1, 1, 2), (2, 1, 3, 2)]) == (8, 16) (a ring with a hole)
- union_area_perimeter([(0, 0, 5, 0), (2, 2, 2, 9)]) == (0, 0)
- union_area_perimeter([]) == (0, 0)
- ValueError: union_area_perimeter([(0, 0, 1)]), union_area_perimeter([(0, 0, 1, 1.5)]), union_area_perimeter(None)
''', r'''
import random

U = union_area_perimeter

def rej(x):
    try:
        U(x)
    except ValueError:
        return True
    return False

assert U([(0, 0, 2, 2)]) == (4, 8)
assert U([(0, 0, 2, 2), (1, 1, 3, 3)]) == (7, 12)
assert U([(0, 0, 1, 1), (1, 0, 2, 1)]) == (2, 6)
assert U([(0, 0, 1, 1), (1, 1, 2, 2)]) == (2, 8)
assert U([(0, 0, 3, 1), (0, 2, 3, 3), (0, 1, 1, 2), (2, 1, 3, 2)]) == (8, 16)
assert U([(0, 0, 5, 0), (2, 2, 2, 9)]) == (0, 0) and U([]) == (0, 0) and U(()) == (0, 0)
assert U([(3, 5, 1, 2)]) == (6, 10) and U([[1, 2, 3, 5]]) == (6, 10)
assert U([(0, 0, 4, 4), (1, 1, 2, 2)]) == (16, 16)
assert U([(0, 0, 4, 4), (4, 0, 4, 4)]) == (16, 16)
assert U([(0, 0, 2, 2), (0, 0, 2, 2)]) == (4, 8)
assert U([(-10**9, -10**9, 10**9, 10**9)]) == (4 * 10**18, 8 * 10**9)
for bad in ([(0, 0, 1)], [(0, 0, 1, 1.5)], None, [(0, 0, 1, True)], [(0, 0, 1, 10**9 + 1)], [(0, -10**9 - 1, 1, 1)],
            [None], [(0, 0, 1, 1, 1)], "abcd", [(0, 0, "1", 1)], {(0, 0, 1, 1)}, [(0, 0, 1, 1), 5]):
    assert rej(bad), bad

def grid(rects):
    cells = set()
    for x1, y1, x2, y2 in rects:
        for x in range(min(x1, x2), max(x1, x2)):
            for y in range(min(y1, y2), max(y1, y2)):
                cells.add((x, y))
    h = v = 0
    for x, y in cells:
        h += ((x, y - 1) not in cells) + ((x, y + 1) not in cells)
        v += ((x - 1, y) not in cells) + ((x + 1, y) not in cells)
    return len(cells), h, v

random.seed(7007)
for _ in range(300):
    rs = []
    for _ in range(random.randint(0, 9)):
        x1, x2 = random.randint(0, 10), random.randint(0, 10)
        y1, y2 = random.randint(0, 10), random.randint(0, 10)
        if random.random() < 0.1:
            x2 = x1
        rs.append((x1, y1, x2, y2))
    a, h, v = grid(rs)
    assert U(rs) == (a, h + v), rs
    ax, ay = random.randint(1, 10**7), random.randint(1, 10**7)
    bx, by = random.randint(-10**8, 10**8), random.randint(-10**8, 10**8)
    sgn = random.choice([1, -1])
    big = [(sgn * (ax * x1 + bx), ay * y1 + by, sgn * (ax * x2 + bx), ay * y2 + by) for x1, y1, x2, y2 in rs]
    assert U(big) == (a * ax * ay, h * ax + v * ay), (rs, ax, ay)
rs = [(random.randint(0, 30), random.randint(0, 30), random.randint(0, 30), random.randint(0, 30)) for _ in range(200)]
a, h, v = grid(rs)
assert U(rs) == (a, h + v)
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def union_area_perimeter(rects):
    if not isinstance(rects, (list, tuple)):
        raise ValueError("rects must be a list or tuple")
    norm = []
    for r in rects:
        if not isinstance(r, (list, tuple)) or len(r) != 4 or not all(_isint(c) and abs(c) <= 10 ** 9 for c in r):
            raise ValueError("bad rectangle")
        x1, y1, x2, y2 = r
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        if x1 < x2 and y1 < y2:
            norm.append((x1, y1, x2, y2))
    if not norm:
        return (0, 0)
    xs = sorted({r[0] for r in norm} | {r[2] for r in norm})
    ys = sorted({r[1] for r in norm} | {r[3] for r in norm})
    xi = {x: i for i, x in enumerate(xs)}
    yi = {y: i for i, y in enumerate(ys)}
    W, H = len(xs) - 1, len(ys) - 1
    diff = [[0] * (H + 1) for _ in range(W + 1)]
    for x1, y1, x2, y2 in norm:
        a, b, c, d = xi[x1], yi[y1], xi[x2], yi[y2]
        diff[a][b] += 1
        diff[c][b] -= 1
        diff[a][d] -= 1
        diff[c][d] += 1
    for i in range(W + 1):
        row = diff[i]
        for j in range(1, H + 1):
            row[j] += row[j - 1]
    for i in range(1, W + 1):
        prev, row = diff[i - 1], diff[i]
        for j in range(H + 1):
            row[j] += prev[j]
    cov = [[diff[i][j] > 0 for j in range(H)] for i in range(W)]
    area = per = 0
    for i in range(W):
        w = xs[i + 1] - xs[i]
        for j in range(H):
            if not cov[i][j]:
                continue
            h = ys[j + 1] - ys[j]
            area += w * h
            if i == 0 or not cov[i - 1][j]:
                per += h
            if i == W - 1 or not cov[i + 1][j]:
                per += h
            if j == 0 or not cov[i][j - 1]:
                per += w
            if j == H - 1 or not cov[i][j + 1]:
                per += w
    return (area, per)
''')

task("v7_08_bowling_frames", r'''
Write `bowling_score(rolls, partial=False)` that validates a ten-pin bowling game and returns its score.

`rolls` is a list or tuple of ints, the pins knocked down by each roll in order, each 0..10 (a bool is not an int
here). `partial` is a bool. Anything else raises ValueError.

Frames. Frames 1 to 9: a first roll of 10 is a strike and ends the frame; otherwise the frame has two rolls whose sum
is at most 10 (sum 10 is a spare). Frame 10: a strike earns two more rolls; if the first of those is not 10, the two
together are at most 10 (if it is 10, the next may be 0..10). Otherwise frame 10 has two rolls with sum at most 10; if
they make a spare, one more roll (0..10) follows. A complete game ends exactly there.

Score: the sum of all pins, plus for each strike in frames 1 to 9 the pins of the next two rolls, plus for each spare
in frames 1 to 9 the pins of the next roll. Rolls of frame 10 count once at face value (they earn no bonus of their
own).

Validation (ValueError): a value out of range or of the wrong type; a frame whose rolls break the rules above;
rolls left over after a complete game. With partial=False the game must be complete; an incomplete game raises
ValueError. With partial=True, any prefix of a valid game is accepted (including the empty list and a complete game),
and the score counts only rolls already made: a strike or spare whose bonus rolls have not happened yet gets only the
bonus rolls that exist.

Examples:
- bowling_score([10] * 12) == 300
- bowling_score([0] * 20) == 0
- bowling_score([5] * 21) == 150
- bowling_score([9, 0] * 10) == 90
- bowling_score([10, 7, 3, 9, 0, 10, 0, 8, 8, 2, 0, 6, 10, 10, 10, 8, 1]) == 167
- bowling_score([10, 10, 4], partial=True) == 42 and bowling_score([3, 7], partial=True) == 10
- ValueError: bowling_score([5, 6] + [0] * 18), bowling_score([0] * 19), bowling_score([0] * 21),
  bowling_score([10] * 9 + [10, 5, 6]), bowling_score([11] + [0] * 19)
''', r'''
import random

B = bowling_score

def rej(*a, **kw):
    try:
        B(*a, **kw)
    except ValueError:
        return True
    return False

assert B([10] * 12) == 300 and B([0] * 20) == 0 and B([5] * 21) == 150 and B([9, 0] * 10) == 90
assert B([10, 7, 3, 9, 0, 10, 0, 8, 8, 2, 0, 6, 10, 10, 10, 8, 1]) == 167
assert B([10, 10, 4], partial=True) == 42 and B([3, 7], partial=True) == 10
assert B([], partial=True) == 0 and B([10] * 12, partial=True) == 300 and B((10,) * 12) == 300
assert B([0] * 18 + [10, 10, 10]) == 30 and B([0] * 18 + [10, 0, 10]) == 20 and B([0] * 18 + [10, 3, 7]) == 20
assert B([0] * 18 + [3, 7, 10]) == 20 and B([0] * 18 + [10, 10, 0]) == 20
assert B([0] * 16 + [10, 10, 10, 10]) == 60
assert B([0] * 18 + [10], partial=True) == 10 and B([10] * 11, partial=True) == 290
for bad in ([5, 6] + [0] * 18, [0] * 19, [0] * 21, [10] * 9 + [10, 5, 6], [11] + [0] * 19, [-1] + [0] * 19,
            [True] + [0] * 19, [0.0] * 20, [10] * 13, [3, 4] * 10 + [1], [10] * 9 + [5, 5], [10] * 9 + [5, 5, 1, 1],
            [10] * 9 + [10, 3], "0" * 20, None, [0] * 18 + [10, 5, 6], [0] * 18 + [7, 2, 1]):
    assert rej(bad), bad
assert rej([0] * 20, partial=1) and rej([0] * 20, partial=None)
assert rej([5, 6], partial=True) and rej([0] * 21, partial=True) and rej([10] * 13, partial=True)
assert rej([10] * 9 + [10, 5, 6], partial=True) and rej([0] * 18 + [3, 4, 1], partial=True)

def gen_frames():
    fr = []
    for _ in range(9):
        r = random.random()
        if r < 0.3:
            fr.append((10,))
        else:
            a = random.randint(0, 9)
            b = 10 - a if r < 0.55 else random.randint(0, 10 - a)
            fr.append((a, b))
    r = random.random()
    if r < 0.3:
        b1 = random.choice([10, random.randint(0, 9)])
        b2 = random.randint(0, 10) if b1 == 10 else random.randint(0, 10 - b1)
        fr.append((10, b1, b2))
    elif r < 0.6:
        a = random.randint(0, 9)
        fr.append((a, 10 - a, random.randint(0, 10)))
    else:
        a = random.randint(0, 9)
        fr.append((a, random.randint(0, 9 - a)))
    return fr

def score_prefix(frames, upto):
    flat = [x for f in frames for x in f][:upto]
    total, pos = sum(flat), 0
    for f in frames[:9]:
        if pos >= len(flat):
            break
        if f == (10,):
            total += sum(flat[pos + 1:pos + 3])
        elif pos + 1 < len(flat) and f[0] + f[1] == 10:
            total += sum(flat[pos + 2:pos + 3])
        pos += len(f)
    return total

random.seed(7008)
for _ in range(400):
    frames = gen_frames()
    rolls = [x for f in frames for x in f]
    assert B(rolls) == score_prefix(frames, len(rolls)), rolls
    k = random.randint(0, len(rolls))
    assert B(rolls[:k], partial=True) == score_prefix(frames, k), (rolls, k)
    if k < len(rolls):
        assert rej(rolls[:k])
    assert rej(rolls + [random.randint(0, 10)]) and rej(rolls + [0], partial=True)
    i = random.randrange(len(rolls))
    assert rej(rolls[:i] + [random.choice([11, -1, 10**6])] + rolls[i + 1:], partial=True)
    two = [j for j, f in enumerate(frames[:9]) if len(f) == 2 and f[0] > 0]
    if two:
        j = random.choice(two)
        pos = sum(len(f) for f in frames[:j])
        bad = list(rolls)
        bad[pos + 1] = 11 - bad[pos]
        assert rej(bad, partial=True), bad
''', r'''
def bowling_score(rolls, partial=False):
    if not isinstance(rolls, (list, tuple)) or not isinstance(partial, bool):
        raise ValueError("rolls must be a list or tuple and partial a bool")
    for r in rolls:
        if not isinstance(r, int) or isinstance(r, bool) or not 0 <= r <= 10:
            raise ValueError("bad roll")
    n = len(rolls)
    i, starts, complete = 0, [], False
    for f in range(10):
        if i == n:
            break
        starts.append(i)
        a = rolls[i]
        if f < 9:
            if a == 10:
                i += 1
                continue
            if i + 1 == n:
                i = n
                break
            if a + rolls[i + 1] > 10:
                raise ValueError("frame over 10 pins")
            i += 2
            continue
        seq = rolls[i:i + 3]
        if a == 10:
            if len(seq) == 3 and seq[1] < 10 and seq[1] + seq[2] > 10:
                raise ValueError("bonus rolls over 10 pins")
            take = 3
        elif len(seq) >= 2:
            if a + seq[1] > 10:
                raise ValueError("frame over 10 pins")
            take = 3 if a + seq[1] == 10 else 2
        else:
            take = 2
        if len(seq) >= take:
            complete = True
            i += take
        else:
            i = n
    if i < n:
        raise ValueError("rolls after the end of the game")
    if not complete and not partial:
        raise ValueError("incomplete game")
    total = sum(rolls)
    for s in starts[:9]:
        if rolls[s] == 10:
            total += sum(rolls[s + 1:s + 3])
        elif s + 1 < n and rolls[s] + rolls[s + 1] == 10:
            total += sum(rolls[s + 2:s + 3])
    return total
''')

task("v7_09_paint_posts", r'''
Write `paint_plan(costs, forbidden=())` that paints a row of fence posts at minimum cost.

There are n posts and k colors. `costs` is a list of n rows (n >= 1); each row is a list of k ints >= 0 (k >= 1, the
same k in every row); costs[i][c] is the price of painting post i with color c. `forbidden` is a list, tuple or set of
pairs (c, d) (tuples or lists of two ints, each 0..k-1): color d may never be painted directly after color c, that is,
on post i + 1 when post i has color c. A pair (c, c) forbids two neighbours of color c. Additionally, no three
consecutive posts may have the same color.

Return None if no valid plan exists. Otherwise return a tuple (total, plan): total is the minimum total price over all
valid plans, and plan is a list of n colors achieving it; when several plans reach the minimum, return the
lexicographically smallest list (as Python compares lists).

Validation (ValueError): costs is not a non-empty list of lists; rows of different lengths or of length 0; a cost that
is not an int or is negative; forbidden is not a list, tuple or set; a pair that is not a tuple or list of two ints in
0..k-1. A bool is never accepted as an int.

Sizes: n up to 1000 and k up to 12, so trying all plans is impossible; use dynamic programming whose state remembers
the previous color and how many posts in a row (1 or 2) already have it.

Examples:
- paint_plan([[1, 5], [1, 5], [1, 5]]) == (7, [0, 0, 1])
- paint_plan([[1, 5], [1, 5], [1, 5]], [(0, 0)]) == (7, [0, 1, 0])
- paint_plan([[2, 2], [2, 2]]) == (4, [0, 0])
- paint_plan([[0], [0], [0]]) is None
- paint_plan([[3, 1, 2]]) == (1, [1])
- paint_plan([[1, 1], [1, 1]], {(0, 1), (1, 0), (0, 0)}) == (2, [1, 1])
- ValueError: paint_plan([]), paint_plan([[1, 2], [3]]), paint_plan([[1, -1]]), paint_plan([[1, 2]], [(0, 2)])
''', r'''
import random
from itertools import product

PP = paint_plan

def rej(*a):
    try:
        PP(*a)
    except ValueError:
        return True
    return False

assert PP([[1, 5], [1, 5], [1, 5]]) == (7, [0, 0, 1])
assert PP([[1, 5], [1, 5], [1, 5]], [(0, 0)]) == (7, [0, 1, 0])
assert PP([[2, 2], [2, 2]]) == (4, [0, 0]) and PP([[0], [0], [0]]) is None and PP([[0], [0]]) == (0, [0, 0])
assert PP([[3, 1, 2]]) == (1, [1]) and PP([[3, 1, 2]], [(0, 0), (1, 1), (2, 2)]) == (1, [1])
assert PP([[1, 1], [1, 1]], {(0, 1), (1, 0), (0, 0)}) == (2, [1, 1])
assert PP([[1, 1], [1, 1]], [[0, 1], [1, 0], [0, 0], [1, 1]]) is None
assert PP([[0, 0]] * 5) == (0, [0, 0, 1, 0, 0])
assert PP([[5, 0, 9], [5, 0, 9], [5, 0, 9], [5, 0, 9]], [(1, 0)]) == (9, [1, 1, 2, 1])
for bad in [([],), ([[1, 2], [3]],), ([[1, -1]],), ([[1, 2]], [(0, 2)]), ([[]],), (None,), ([[1.0]],), ([[True]],),
            ([[1, 2]], [(0,)]), ([[1, 2]], "ab"), ([[1, 2]], [(0, 1, 1)]), ([[1, 2]], [(True, 0)]), ([(1, 2)],),
            ([[1, 2]], None), ([[1, 2]], [(-1, 0)]), ([[1, 2]], [5])]:
    assert rej(*bad), bad

def brute(costs, forb):
    n, k = len(costs), len(costs[0])
    best = None
    for plan in product(range(k), repeat=n):
        if any((a, b) in forb for a, b in zip(plan, plan[1:])):
            continue
        if any(plan[i] == plan[i + 1] == plan[i + 2] for i in range(n - 2)):
            continue
        c = sum(costs[i][x] for i, x in enumerate(plan))
        if best is None or c < best[0]:
            best = (c, list(plan))
    return best

random.seed(7009)
for _ in range(200):
    k = random.randint(1, 3)
    n = random.randint(1, 6 if k < 3 else 5)
    costs = [[random.randint(0, 4) for _ in range(k)] for _ in range(n)]
    forb = {(random.randrange(k), random.randrange(k)) for _ in range(random.randint(0, k * k))}
    arg = random.choice([list, tuple, set])(forb)
    assert PP(costs, arg) == brute(costs, forb), (costs, forb)

def forward_min(costs, forb):
    INF = float("inf")
    k = len(costs[0])
    g = {(c, 1): costs[0][c] for c in range(k)}
    for row in costs[1:]:
        ng = {}
        for (c, r), v in g.items():
            for d in range(k):
                if (c, d) in forb or (d == c and r == 2):
                    continue
                key = (d, r + 1 if d == c else 1)
                if v + row[d] < ng.get(key, INF):
                    ng[key] = v + row[d]
        g = ng
    return min(g.values()) if g else None

for _ in range(12):
    n, k = random.randint(100, 300), random.randint(2, 8)
    costs = [[random.randint(0, 9) for _ in range(k)] for _ in range(n)]
    forb = {(random.randrange(k), random.randrange(k)) for _ in range(random.randint(0, k))}
    r = PP(costs, forb)
    best = forward_min(costs, forb)
    if best is None:
        assert r is None
        continue
    total, plan = r
    assert total == best and len(plan) == n
    assert sum(costs[i][c] for i, c in enumerate(plan)) == total
    assert not any((a, b) in forb for a, b in zip(plan, plan[1:]))
    assert not any(plan[i] == plan[i + 1] == plan[i + 2] for i in range(n - 2))
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def paint_plan(costs, forbidden=()):
    if not isinstance(costs, list) or not costs or not all(isinstance(r, list) for r in costs):
        raise ValueError("costs must be a non-empty list of lists")
    k = len(costs[0])
    if k == 0 or any(len(r) != k for r in costs):
        raise ValueError("rows must have the same length >= 1")
    if not all(_isint(x) and x >= 0 for r in costs for x in r):
        raise ValueError("costs must be ints >= 0")
    if not isinstance(forbidden, (list, tuple, set)):
        raise ValueError("forbidden must be a list, tuple or set")
    forb = set()
    for p in forbidden:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_isint(x) and 0 <= x < k for x in p):
            raise ValueError("bad forbidden pair")
        forb.add((p[0], p[1]))
    n = len(costs)
    INF = float("inf")
    # f[i][(prev, run)]: cheapest way to paint posts i..n-1 when post i-1 has color prev in a run of length run
    f = [None] * (n + 1)
    states = [(-1, 0)] + [(c, r) for c in range(k) for r in (1, 2)]
    f[n] = {s: 0 for s in states}

    def moves(prev, run):
        for c in range(k):
            if prev >= 0 and ((prev, c) in forb or (c == prev and run == 2)):
                continue
            yield c, (c, run + 1 if c == prev else 1)

    for i in range(n - 1, -1, -1):
        cur = {}
        for prev, run in states:
            best = INF
            for c, nxt in moves(prev, run):
                best = min(best, costs[i][c] + f[i + 1][nxt])
            cur[(prev, run)] = best
        f[i] = cur
    total = f[0][(-1, 0)]
    if total == INF:
        return None
    plan, state = [], (-1, 0)
    for i in range(n):
        for c, nxt in moves(*state):
            if costs[i][c] + f[i + 1][nxt] == f[i][state]:
                plan.append(c)
                state = nxt
                break
    return (total, plan)
''')

task("v7_10_justify_lines", r'''
Write `justify_lines(text, width)` that lays out text in fully justified lines of exactly `width` characters and returns
them as a list of str.

`text` must be a str and `width` an int >= 1 (a bool is not accepted); otherwise ValueError.

Tokens. The words of the text are what text.split() returns (maximal runs of non-whitespace). A word longer than
`width` is cut into pieces of exactly `width` characters from its start, plus a final shorter piece if characters are
left over; each piece is a token. Every other word is one token. Tokens keep their order.

Lines. Fill lines greedily: a line takes tokens one by one, separated by single spaces, as long as the line's length
stays <= width; the first token that does not fit starts the next line. (A piece of exactly `width` characters
therefore always sits alone on its line, while a final shorter piece may share its line with the tokens after it.)
Empty text, or text with only whitespace, gives [].

Justification:
- The last line, and every line that holds a single token, is left-aligned: tokens joined by single spaces, then
  spaces appended on the right up to `width`.
- Every other line is fully justified: the line starts with its first token and ends with its last token, and the
  spaces needed to reach `width` are spread over the gaps between tokens as evenly as possible; when they do not divide
  evenly, the leftmost gaps get one extra space each.

Examples:
- justify_lines("This is an example of text justification.", 16) ==
  ["This    is    an", "example  of text", "justification.  "]
- justify_lines("What must be acknowledgment shall be", 16) == ["What   must   be", "acknowledgment  ", "shall be        "]
- justify_lines("abcdefghij xy", 4) == ["abcd", "efgh", "ij  ", "xy  "]
- justify_lines("abcdefghij x", 4) == ["abcd", "efgh", "ij x"]
- justify_lines("  ", 5) == [] and justify_lines("a", 1) == ["a"]
- ValueError: justify_lines(None, 5), justify_lines("a b", 0), justify_lines("a b", True)
''', r'''
import random, re

J = justify_lines

def rej(*a):
    try:
        J(*a)
    except ValueError:
        return True
    return False

assert J("This is an example of text justification.", 16) == ["This    is    an", "example  of text", "justification.  "]
assert J("What must be acknowledgment shall be", 16) == ["What   must   be", "acknowledgment  ", "shall be        "]
assert J("abcdefghij xy", 4) == ["abcd", "efgh", "ij  ", "xy  "]
assert J("abcdefghij x", 4) == ["abcd", "efgh", "ij x"]
assert J("  ", 5) == [] and J("", 3) == [] and J("a", 1) == ["a"]
assert J("a b c d", 1) == ["a", "b", "c", "d"]
assert J("aa b c dd", 6) == ["aa b c", "dd    "]
assert J("a b c d e", 8) == ["a  b c d", "e       "]
assert J("abc\tde\nf  g", 7) == ["abc  de", "f g    "]
assert J("abcdefgh", 4) == ["abcd", "efgh"] and J("abcdefgh i", 4) == ["abcd", "efgh", "i   "]
assert J("x abcdefg", 3) == ["x  ", "abc", "def", "g  "]
for bad in [(None, 5), ("a b", 0), ("a b", True), (b"ab", 3), ("a", 2.0), ("a", -1), (["a"], 3), ("a", None)]:
    assert rej(*bad), bad

def tokens(text, w):
    out = []
    for word in text.split():
        out += [word[i:i + w] for i in range(0, len(word), w)]
    return out

random.seed(7010)
for _ in range(400):
    w = random.randint(1, 30)
    words = []
    for _ in range(random.randint(0, 25)):
        L = random.choice([1, 2, 3, 4, 5, 6, 8, 12, random.randint(1, 3 * w)])
        words.append("".join(random.choice("abcXYZ.,!?-'0") for _ in range(L)))
    text = "".join(random.choice([" ", "  ", "\t", "\n", " \n "]) + x for x in words) + random.choice(["", " ", "\n"])
    lines = J(text, w)
    toks = tokens(text, w)
    assert all(type(s) is str and len(s) == w for s in lines), (text, w, lines)
    per = [s.split() for s in lines]
    assert [t for p in per for t in p] == toks, (text, w, lines)
    assert all(p for p in per)
    for idx, (s, p) in enumerate(zip(lines, per)):
        if idx + 1 < len(lines):
            assert len(" ".join(p)) + 1 + len(per[idx + 1][0]) > w, (text, w, lines)
        if idx == len(lines) - 1 or len(p) == 1:
            assert s == " ".join(p).ljust(w), (text, w, s)
        else:
            assert s.startswith(p[0]) and s.endswith(p[-1])
            gaps = [len(g) for g in re.findall(r" +", s)]
            assert len(gaps) == len(p) - 1 and max(gaps) - min(gaps) <= 1, (s, gaps)
            assert gaps == sorted(gaps, reverse=True), (s, gaps)
''', r'''
def justify_lines(text, width):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise ValueError("width must be an int >= 1")
    tokens = []
    for w in text.split():
        while len(w) > width:
            tokens.append(w[:width])
            w = w[width:]
        tokens.append(w)
    lines, cur, cur_len = [], [], 0
    for t in tokens:
        if cur and cur_len + 1 + len(t) > width:
            lines.append(cur)
            cur, cur_len = [t], len(t)
        else:
            cur_len = len(t) if not cur else cur_len + 1 + len(t)
            cur.append(t)
    if cur:
        lines.append(cur)
    out = []
    for idx, ws in enumerate(lines):
        if idx == len(lines) - 1 or len(ws) == 1:
            s = " ".join(ws)
            out.append(s + " " * (width - len(s)))
            continue
        gaps = len(ws) - 1
        q, r = divmod(width - sum(len(w) for w in ws), gaps)
        parts = []
        for j, w in enumerate(ws[:-1]):
            parts.append(w + " " * (q + (1 if j < r else 0)))
        parts.append(ws[-1])
        out.append("".join(parts))
    return out
''')

# --- v7 tasks 11-30 append below this line (seeds 7011-7030); v7_01-10 above stay frozen once probed ---

TASKS = T
