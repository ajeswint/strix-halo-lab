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
Tasks 11-30 (2026-10-18) were written easier after the crawdad-v7-probe bar (all-fail 9 of 10): one or two functions,
about six rules each with an example, light validation, references of at most about 40 lines (the stack machine is
60). v7_11 rle_letters, v7_12 hex_lines, v7_13 column_totals, v7_14 bit_flags, v7_15 duration_words,
v7_16 collatz_leader, v7_17 prime_gap, v7_18 perm_rank, v7_19 change_ways, v7_20 radix_text, v7_21 island_stats,
v7_22 course_order, v7_23 shoelace, v7_24 knight_hops, v7_25 point_location, v7_26 teller_queue, v7_27 lis_count,
v7_28 life_board, v7_29 stack_machine, v7_30 wrap_cost.
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

# --- v7 tasks 11-30 (seeds 7011-7030), written easier after the crawdad-v7-probe bar (README) ---

task("v7_11_rle_letters", r'''
Write two functions for a run-length code over ASCII letters: `rle_pack(text)` and `rle_unpack(code)`.

rle_pack(text): `text` must be a str made only of ASCII letters a-z and A-Z (the empty string is fine); anything else
raises ValueError. Each maximal run of one repeated letter is written as the run length in decimal followed by the
letter, except that a run of length 1 is written as the letter alone. Upper and lower case are different letters.
Runs are never split, however long they are.

rle_unpack(code): the exact inverse. `code` must be a str. It is read as a sequence of items; each item is an optional
count followed by one ASCII letter, and stands for the letter repeated count times (once if there is no count). It
accepts exactly the strings that rle_pack can produce, so each of these raises ValueError:
- any character that is not an ASCII digit or an ASCII letter, or digits at the end with no letter after them;
- a count with a leading zero, or a count of 0 or 1 (rle_pack never writes those);
- two items in a row with the same letter (rle_pack would have merged them into one run).

Examples:
- rle_pack("aaabccdddd") == "3ab2c4d"
- rle_pack("") == "" and rle_pack("aA") == "aA" and rle_pack("z" * 12) == "12z"
- rle_unpack("3ab2c4d") == "aaabccdddd" and rle_unpack("2Aa") == "AAa"
- ValueError: rle_pack("ab1"), rle_pack("a b"), rle_unpack("1a"), rle_unpack("01a"), rle_unpack("aa"),
  rle_unpack("2a3a"), rle_unpack("3"), rle_unpack("a-b")
''', r'''
import random, re
from itertools import groupby

P, U = rle_pack, rle_unpack

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert P("aaabccdddd") == "3ab2c4d" and P("") == "" and P("aA") == "aA" and P("z" * 12) == "12z"
assert U("3ab2c4d") == "aaabccdddd" and U("2Aa") == "AAa" and U("") == "" and U("12z") == "z" * 12
assert P("abc") == "abc" and P("aabbaa") == "2a2b2a" and U("2a2b2a") == "aabbaa" and U("aA") == "aA"
for bad in ("ab1", "a b", "é", "a\n", None, 5, ["a"], b"aa"):
    assert rej(P, bad), bad
for bad in ("1a", "01a", "aa", "2a3a", "3", "a-b", "0a", "a2", "2a2a", " 2a", "2 a", "٢a", "a2a", None, b"2a", "10"):
    assert rej(U, bad), bad

def opack(s):
    return "".join((str(len(g)) if len(g) > 1 else "") + k for k, g in ((k, list(g)) for k, g in groupby(s)))

random.seed(7011)
for _ in range(300):
    s = "".join(random.choice("aaabBz") * random.choice([1, 1, 2, 3, 9, 10, 11, 25]) for _ in range(random.randint(0, 12)))
    assert P(s) == opack(s), s
    assert U(P(s)) == s
for _ in range(1500):
    c = "".join(random.choice("ab0129") for _ in range(random.randint(1, 6)))
    ok, exp = False, None
    if re.fullmatch(r"(?:\d*[ab])*", c):
        exp = "".join(ch * (int(d) if d else 1) for d, ch in re.findall(r"(\d*)([ab])", c))
        ok = opack(exp) == c
    if ok:
        assert U(c) == exp, c
    else:
        assert rej(U, c), c
''', r'''
import re

_LETTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
_ITEM = re.compile(r"([1-9][0-9]*)?([A-Za-z])")


def rle_pack(text):
    if not isinstance(text, str) or any(c not in _LETTERS for c in text):
        raise ValueError("ASCII letters only")
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        n = j - i
        out.append((str(n) if n > 1 else "") + text[i])
        i = j
    return "".join(out)


def rle_unpack(code):
    if not isinstance(code, str):
        raise ValueError("code must be a str")
    out, pos, prev = [], 0, None
    while pos < len(code):
        m = _ITEM.match(code, pos)
        if not m:
            raise ValueError("bad item")
        if m.group(1) and int(m.group(1)) < 2:
            raise ValueError("count below 2")
        ch = m.group(2)
        if ch == prev:
            raise ValueError("two items with the same letter")
        out.append(ch * (int(m.group(1)) if m.group(1) else 1))
        prev, pos = ch, m.end()
    return "".join(out)
''')

task("v7_12_hex_lines", r'''
Write `hex_dump(data, width=16)` that formats bytes as hex dump lines and returns them as a list of str.

`data` must be a `bytes` or `bytearray`; `width` must be an int from 1 to 64 (a bool is not accepted). Otherwise raise
ValueError.

Split the data into chunks of `width` bytes (the last chunk may be shorter). Each chunk gives one line made of:
1. the offset of the chunk's first byte as exactly 8 lowercase hex digits;
2. two spaces;
3. the hex area: each byte as two lowercase hex digits, bytes separated by one space. In a short last chunk, every
   missing byte is replaced by three spaces, so the hex area always has 3 * width - 1 characters;
4. two spaces;
5. a "|", then one character per byte of the chunk (the byte itself if it is printable ASCII, 0x20 to 0x7e,
   otherwise "."), then a closing "|". This part is not padded.

Empty data gives []. Lines carry no trailing newline.

Examples:
- hex_dump(b"Hello, world!\n", 8) == ["00000000  48 65 6c 6c 6f 2c 20 77  |Hello, w|",
                                       "00000008  6f 72 6c 64 21 0a        |orld!.|"]
- hex_dump(bytes([30, 31, 32, 33]), 4) == ["00000000  1e 1f 20 21  |.. !|"]
- hex_dump(b"") == [] and hex_dump(b"A", 1) == ["00000000  41  |A|"]
- ValueError: hex_dump("abc"), hex_dump(b"a", 0), hex_dump(b"a", 65), hex_dump(b"a", True)
''', r'''
import random

H = hex_dump

def rej(*a):
    try:
        H(*a)
    except ValueError:
        return True
    return False

assert H(b"Hello, world!\n", 8) == ["00000000  48 65 6c 6c 6f 2c 20 77  |Hello, w|", "00000008  6f 72 6c 64 21 0a        |orld!.|"]
assert H(bytes([30, 31, 32, 33]), 4) == ["00000000  1e 1f 20 21  |.. !|"]
assert H(b"") == [] and H(b"A", 1) == ["00000000  41  |A|"]
assert H(bytearray(b"~\x7f "), 2) == ["00000000  7e 7f  |~.|", "00000002  20     | |"]
assert H(bytes(range(16)))[0] == "00000000  " + " ".join("%02x" % i for i in range(16)) + "  |" + "." * 16 + "|"
for bad in [("abc",), (b"a", 0), (b"a", 65), (b"a", True), (None,), ([65],), (b"a", 2.0), (b"a", "16"), (memoryview(b"a"),)]:
    assert rej(*bad), bad

def oracle(data, w):
    out = []
    for o in range(0, len(data), w):
        ch = data[o:o + w]
        hx = " ".join("%02x" % b for b in ch).ljust(3 * w - 1)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in ch)
        out.append("%08x  %s  |%s|" % (o, hx, asc))
    return out

random.seed(7012)
for _ in range(400):
    w = random.choice([1, 2, 3, 7, 8, 16, 31, 64, random.randint(1, 64)])
    data = bytes(random.randrange(256) for _ in range(random.randint(0, 3 * w + 5)))
    assert H(data, w) == oracle(data, w), (data, w)
    if w == 16:
        assert H(data) == oracle(data, 16)
data = bytes(random.randrange(256) for _ in range(70000))
assert H(data, 16) == oracle(data, 16)
''', r'''
def hex_dump(data, width=16):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes or bytearray")
    if not isinstance(width, int) or isinstance(width, bool) or not 1 <= width <= 64:
        raise ValueError("width must be an int from 1 to 64")
    lines = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        cells = [format(chunk[i], "02x") if i < len(chunk) else "  " for i in range(width)]
        text = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)
        lines.append(format(off, "08x") + "  " + " ".join(cells) + "  |" + text + "|")
    return lines
''')

task("v7_13_column_totals", r'''
Write `column_totals(text)` that reads a small comma-separated table of integers and returns the sum of each column as
a dict {column name: sum}.

`text` must be a str (otherwise ValueError). Only spaces and tabs count as blanks here.
- Split `text` on "\n"; a line ending in "\r" loses that one "\r". Lines that are empty or contain only blanks are
  skipped everywhere.
- The first remaining line is the header: split it on ",", strip blanks from each name. Every name must be non-empty
  and the names must be distinct, else ValueError.
- Every later remaining line is a data row: split on ",", strip blanks from each field. It must have exactly as many
  fields as the header, else ValueError. Each field must be an optional "+" or "-" followed by one or more ASCII
  digits (leading zeros are fine), else ValueError. So "1_000", "1.0", "", " " and non-ASCII digits are all errors.
- The result maps every header name to the sum of its column's integers (0 when there are no data rows).
- If no remaining line exists at all, return {}.

Examples:
- column_totals("a,b\n1,2\n3,4\n") == {"a": 4, "b": 6}
- column_totals(" x , y \r\n\n -1, +2\r\n007,-0\n") == {"x": 6, "y": 2}
- column_totals("") == {} and column_totals("only\n") == {"only": 0}
- ValueError: column_totals("a,a\n1,2"), column_totals("a,\n1,2"), column_totals("a,b\n1"),
  column_totals("a,b\n1,x"), column_totals("a,b\n1,2.0"), column_totals("a,b\n1,1_000"), column_totals(5)
''', r'''
import random

C = column_totals

def rej(x):
    try:
        C(x)
    except ValueError:
        return True
    return False

assert C("a,b\n1,2\n3,4\n") == {"a": 4, "b": 6}
assert C(" x , y \r\n\n -1, +2\r\n007,-0\n") == {"x": 6, "y": 2}
assert C("") == {} and C("only\n") == {"only": 0} and C(" \n\t\n") == {}
assert C("n\n5\n\n-7\n") == {"n": -2} and C("a b,c\n1,1") == {"a b": 1, "c": 1}
for bad in ("a,a\n1,2", "a,\n1,2", "a,b\n1", "a,b\n1,x", "a,b\n1,2.0", "a,b\n1,1_000", 5, None, "a,b\n1,2,3", "a,b\n1, ",
            "a,b\n1,٣", "a,b\n+,1", "a,b\n1,--2", "a,b\n1,2\n3", ",\n1,2", b"a\n1"):
    assert rej(bad), bad

random.seed(7013)
NAMES = "abcxyzQ_ 9"
for _ in range(300):
    k = random.randint(1, 5)
    names = []
    while len(names) < k:
        nm = "".join(random.choice(NAMES) for _ in range(random.randint(1, 5))).strip(" ")
        if nm and nm not in names:
            names.append(nm)
    rows = [[random.randint(-10**6, 10**6) for _ in range(k)] for _ in range(random.randint(0, 8))]
    want = {nm: sum(r[i] for r in rows) for i, nm in enumerate(names)}
    sp = lambda: random.choice(["", " ", "\t", "  "])
    def fmt(v):
        s = str(abs(v)).zfill(random.choice([1, 1, 4]))
        sign = "-" if v < 0 else random.choice(["", "", "+"]) if v > 0 else random.choice(["", "-", "+"])
        return sp() + sign + s + sp()
    lines = [",".join(sp() + nm + sp() for nm in names)] + [",".join(fmt(v) for v in r) for r in rows]
    for _ in range(random.randint(0, 3)):
        lines.insert(random.randint(0, len(lines)), random.choice(["", " ", "\t "]))
    eol = random.choice(["\n", "\r\n"])
    text = eol.join(lines) + random.choice(["", eol])
    assert C(text) == want, (text, want)
    if rows:
        bad = list(lines)
        i = max(j for j, s in enumerate(bad) if s.strip(" \t"))
        bad[i] = bad[i] + random.choice([",1", ",", "x", ".5"])
        assert rej(eol.join(bad)), bad
''', r'''
import re

_INT = re.compile(r"[+-]?[0-9]+")
BL = " \t"


def column_totals(text):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    header, sums = None, None
    for line in text.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip(BL):
            continue
        fields = [f.strip(BL) for f in line.split(",")]
        if header is None:
            if any(not f for f in fields) or len(set(fields)) != len(fields):
                raise ValueError("bad header")
            header, sums = fields, [0] * len(fields)
            continue
        if len(fields) != len(header):
            raise ValueError("wrong number of fields")
        for i, f in enumerate(fields):
            if not _INT.fullmatch(f):
                raise ValueError("bad integer")
            sums[i] += int(f)
    return {} if header is None else dict(zip(header, sums))
''')

task("v7_14_bit_flags", r'''
Write `pack_flags(flags)` and `unpack_flags(data, n)` that store a list of booleans in bytes, most significant bit
first.

pack_flags(flags): `flags` is a list or tuple whose items are exactly True or False (the ints 0 and 1 are not
accepted); otherwise ValueError. Flag i goes into byte i // 8, at bit 7 - (i % 8), where bit 7 is the value 0x80. A set
flag is a 1 bit. The result has (len(flags) + 7) // 8 bytes, and the unused low bits of the last byte are 0. An empty
list gives b"".

unpack_flags(data, n): the inverse. `data` must be a `bytes` or `bytearray`, and `n` an int >= 0 (not a bool). Raise
ValueError unless len(data) == (n + 7) // 8 exactly, and also when any unused padding bit in the last byte is 1.
Return the list of n bools.

Examples:
- pack_flags([True, False, True]) == b"\xa0"
- pack_flags([]) == b"" and pack_flags((True,) * 8) == b"\xff"
- pack_flags([False] * 8 + [True]) == b"\x00\x80"
- unpack_flags(b"\xa0", 3) == [True, False, True] and unpack_flags(b"", 0) == []
- unpack_flags(b"\x00\x80", 9) == [False] * 8 + [True]
- ValueError: unpack_flags(b"\xa1", 3) (a padding bit is set), unpack_flags(b"\xa0\x00", 3) (too long),
  unpack_flags(b"\xa0", 9) (too short), pack_flags([1, 0]), pack_flags("TF")
''', r'''
import random

PK, UN = pack_flags, unpack_flags

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert PK([True, False, True]) == b"\xa0" and PK([]) == b"" and PK((True,) * 8) == b"\xff"
assert PK([False] * 8 + [True]) == b"\x00\x80"
assert UN(b"\xa0", 3) == [True, False, True] and UN(b"", 0) == [] and UN(b"\x00\x80", 9) == [False] * 8 + [True]
assert UN(bytearray(b"\xff"), 8) == [True] * 8 and type(PK([True])) is bytes
for a in [(b"\xa1", 3), (b"\xa0\x00", 3), (b"\xa0", 9), (b"", 1), (b"\x00", 0), (b"\x01", 7), ("a", 1), (b"\x00", -1),
          (b"\x00", True), (b"\x00", 1.0), ([0], 1)]:
    assert rej(UN, *a), a
for a in ([1, 0], "TF", None, [True, None], [True, 1], (False, 0.0)):
    assert rej(PK, a), a

def opack(fl):
    if not fl:
        return b""
    nb = (len(fl) + 7) // 8
    bits = "".join("1" if f else "0" for f in fl).ljust(8 * nb, "0")
    return int(bits, 2).to_bytes(nb, "big")

random.seed(7014)
for _ in range(500):
    n = random.randint(0, 70)
    fl = [random.random() < 0.5 for _ in range(n)]
    b = PK(fl)
    assert b == opack(fl), fl
    assert UN(b, n) == fl
    assert UN(bytearray(b), n) == fl
    if n % 8:
        bad = bytearray(b)
        bad[-1] |= 1 << random.randrange(8 - n % 8)
        assert rej(UN, bytes(bad), n)
    assert rej(UN, b + b"\x00", n)
    if b:
        assert rej(UN, b[:-1], n)
''', r'''
def pack_flags(flags):
    if not isinstance(flags, (list, tuple)) or any(type(f) is not bool for f in flags):
        raise ValueError("flags must be a list or tuple of bools")
    out = bytearray((len(flags) + 7) // 8)
    for i, f in enumerate(flags):
        if f:
            out[i // 8] |= 0x80 >> (i % 8)
    return bytes(out)


def unpack_flags(data, n):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes or bytearray")
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be an int >= 0")
    if len(data) != (n + 7) // 8:
        raise ValueError("wrong length")
    if n % 8 and data[-1] & ((1 << (8 - n % 8)) - 1):
        raise ValueError("padding bit set")
    return [bool(data[i // 8] & (0x80 >> (i % 8))) for i in range(n)]
''')

task("v7_15_duration_words", r'''
Write `format_duration(seconds, style="short")` that writes a whole number of seconds in days, hours, minutes and
seconds.

`seconds` must be an int (a bool is not accepted) and `style` must be "short" or "long"; otherwise ValueError.

Take the absolute value and split it into days (86400 s), hours (3600 s), minutes (60 s) and seconds, largest unit
first, so hours < 24, minutes < 60 and seconds < 60 (days can be any size). Keep only the units whose count is not 0,
in the order days, hours, minutes, seconds.
- short style: each kept unit is written as the count followed directly by d, h, m or s, joined by single spaces:
  "1d 2h 5s". Zero is "0s". A negative input gets a "-" in front: "-1m 1s".
- long style: each kept unit is written as the count, a space and the unit name (day, hour, minute, second), with an
  "s" added to the name when the count is not 1. One part is written alone; two parts are joined by " and "; three or
  more parts are joined by ", " except the last two, which are joined by " and " (no comma before "and"). Zero is
  "0 seconds". A negative input gets "minus " in front.

Examples:
- format_duration(3661) == "1h 1m 1s" and format_duration(3600) == "1h"
- format_duration(86460) == "1d 1m" and format_duration(0) == "0s" and format_duration(-61) == "-1m 1s"
- format_duration(10**7) == "115d 17h 46m 40s"
- format_duration(3661, "long") == "1 hour, 1 minute and 1 second"
- format_duration(90, "long") == "1 minute and 30 seconds" and format_duration(7200, "long") == "2 hours"
- format_duration(0, "long") == "0 seconds" and format_duration(-259200, "long") == "minus 3 days"
- ValueError: format_duration(1.5), format_duration(True), format_duration(5, "medium")
''', r'''
import random

F = format_duration

def rej(*a):
    try:
        F(*a)
    except ValueError:
        return True
    return False

assert F(3661) == "1h 1m 1s" and F(3600) == "1h" and F(86460) == "1d 1m" and F(0) == "0s" and F(-61) == "-1m 1s"
assert F(10**7) == "115d 17h 46m 40s"
assert F(3661, "long") == "1 hour, 1 minute and 1 second" and F(90, "long") == "1 minute and 30 seconds"
assert F(7200, "long") == "2 hours" and F(0, "long") == "0 seconds" and F(-259200, "long") == "minus 3 days"
assert F(1, "long") == "1 second" and F(86401, "long") == "1 day and 1 second" and F(59) == "59s"
assert F(90061, "long") == "1 day, 1 hour, 1 minute and 1 second" and F(172922, style="long") == "2 days, 2 minutes and 2 seconds"
assert F(-1) == "-1s" and F(-1, "long") == "minus 1 second" and F(3600, style="short") == "1h"
for bad in [(1.5,), (True,), (5, "medium"), ("5",), (None,), (5, "Long"), (5, None), (5, 1), (False, "long")]:
    assert rej(*bad), bad

def oracle(s, style):
    neg, r = s < 0, -s if s < 0 else s
    d = r // 86400
    h = (r - d * 86400) // 3600
    m = (r - d * 86400 - h * 3600) // 60
    sec = r - d * 86400 - h * 3600 - m * 60
    units = [(d, "d", "day"), (h, "h", "hour"), (m, "m", "minute"), (sec, "s", "second")]
    kept = [(n, a, b) for n, a, b in units if n != 0]
    if style == "short":
        body = " ".join("%d%s" % (n, a) for n, a, b in kept) if kept else "0s"
        return ("-" + body) if neg else body
    words = ["%d %s%s" % (n, b, "" if n == 1 else "s") for n, a, b in kept] or ["0 seconds"]
    if len(words) == 1:
        body = words[0]
    else:
        body = ", ".join(words[:-1]) + " and " + words[-1]
    return ("minus " + body) if neg else body

random.seed(7015)
for _ in range(1500):
    s = random.choice([random.randint(-100, 100), random.randint(-10**6, 10**6), random.randint(-10**12, 10**12),
                       random.choice([0, 60, 3600, 86400]) * random.randint(-3, 3) + random.choice([0, 1, 59])])
    style = random.choice(["short", "long"])
    assert F(s, style) == oracle(s, style), (s, style)
    if style == "short":
        assert F(s) == oracle(s, "short")
''', r'''
UNITS = (("d", "day", 86400), ("h", "hour", 3600), ("m", "minute", 60), ("s", "second", 1))


def format_duration(seconds, style="short"):
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        raise ValueError("seconds must be an int")
    if style not in ("short", "long"):
        raise ValueError("style must be short or long")
    neg, rest, parts = seconds < 0, abs(seconds), []
    for short, name, size in UNITS:
        q, rest = divmod(rest, size)
        if q:
            parts.append(f"{q}{short}" if style == "short" else f"{q} {name}{'' if q == 1 else 's'}")
    if style == "short":
        return ("-" if neg else "") + (" ".join(parts) if parts else "0s")
    if not parts:
        return "0 seconds"
    body = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return ("minus " if neg else "") + body
''')

task("v7_16_collatz_leader", r'''
Write `collatz_leader(limit)` that finds the starting number up to `limit` with the longest Collatz chain.

The Collatz step maps n to n // 2 when n is even and to 3 * n + 1 when n is odd. The chain of a start n is the list of
numbers from n until the first 1, both included; its length is the number of terms. So the chain of 1 is [1] (length
1), the chain of 2 is [2, 1] (length 2), and the chain of 6 is [6, 3, 10, 5, 16, 8, 4, 2, 1] (length 9).

`limit` must be an int with 1 <= limit <= 300000 (a bool is not accepted); otherwise ValueError.

Return a tuple (start, length) for the start in 1..limit whose chain is longest. If several starts share the longest
length, return the smallest of them.

Chains pass through numbers much larger than `limit`, and computing every chain from scratch is too slow for the
largest limits: remember the lengths you have already found (for every number met on the way) and reuse them.

Examples:
- collatz_leader(1) == (1, 1)
- collatz_leader(2) == (2, 2)
- collatz_leader(10) == (9, 20)
- collatz_leader(100) == (97, 119)
- collatz_leader(1000) == (871, 179)
- collatz_leader(10000) == (6171, 262)
- ValueError: collatz_leader(0), collatz_leader(300001), collatz_leader(10.0), collatz_leader(True)
''', r'''
import random

L = collatz_leader

def rej(x):
    try:
        L(x)
    except ValueError:
        return True
    return False

assert L(1) == (1, 1) and L(2) == (2, 2) and L(10) == (9, 20) and L(100) == (97, 119)
assert L(1000) == (871, 179) and L(10000) == (6171, 262) and L(100000) == (77031, 351)
assert L(3) == (3, 8) and L(6) == (6, 9) and L(9) == (9, 20)
for bad in (0, 300001, 10.0, True, -5, "10", None):
    assert rej(bad), bad

def chain_len(n):
    k = 1
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        k += 1
    return k

random.seed(7016)
for lim in [random.randint(1, 60) for _ in range(20)] + [random.randint(61, 1500) for _ in range(3)]:
    best = (1, 1)
    for s in range(1, lim + 1):
        c = chain_len(s)
        if c > best[1]:
            best = (s, c)
    assert L(lim) == best, lim
''', r'''
def collatz_leader(limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 300000:
        raise ValueError("limit must be an int from 1 to 300000")
    cache = {1: 1}
    best = (1, 1)
    for start in range(2, limit + 1):
        n, path = start, []
        while n not in cache:
            path.append(n)
            n = n // 2 if n % 2 == 0 else 3 * n + 1
        length = cache[n]
        for m in reversed(path):
            length += 1
            cache[m] = length
        if cache[start] > best[1]:
            best = (start, cache[start])
    return best
''')

task("v7_17_prime_gap", r'''
Write `widest_prime_gap(lo, hi)` that finds the widest gap between consecutive primes inside a range.

`lo` and `hi` must be ints (a bool is not accepted) with 0 <= lo <= hi <= 2_000_000; otherwise ValueError.

Consider only the primes p with lo <= p <= hi, in increasing order. For each pair of neighbours (p, q) in that list,
the gap is q - p. Return a tuple (gap, p, q) for the widest gap; if several pairs share the widest gap, return the one
with the smallest p. If the range holds fewer than two primes, return None. Primes outside the range do not count, so a
gap that starts before lo or ends after hi is never reported.

A prime is an integer >= 2 with no divisor other than 1 and itself. With hi up to two million, use a sieve of
Eratosthenes up to hi rather than testing each number on its own.

Examples:
- widest_prime_gap(10, 30) == (6, 23, 29)   (primes 11, 13, 17, 19, 23, 29)
- widest_prime_gap(2, 3) == (1, 2, 3)
- widest_prime_gap(0, 2) is None and widest_prime_gap(24, 28) is None
- widest_prime_gap(100, 200) == (14, 113, 127)
- widest_prime_gap(0, 10**6) == (114, 492113, 492227)
- widest_prime_gap(14, 22) == (2, 17, 19)
- ValueError: widest_prime_gap(5, 4), widest_prime_gap(-1, 4), widest_prime_gap(0, 2_000_001), widest_prime_gap(0, 10.0)
''', r'''
import random

W = widest_prime_gap

def rej(*a):
    try:
        W(*a)
    except ValueError:
        return True
    return False

assert W(10, 30) == (6, 23, 29) and W(2, 3) == (1, 2, 3) and W(0, 2) is None and W(24, 28) is None
assert W(100, 200) == (14, 113, 127) and W(0, 10**6) == (114, 492113, 492227) and W(14, 22) == (2, 17, 19)
assert W(0, 0) is None and W(0, 1) is None and W(3, 5) == (2, 3, 5) and W(2, 2) is None
assert W(492114, 492227) is None and W(492113, 492227) == (114, 492113, 492227)
for bad in [(5, 4), (-1, 4), (0, 2_000_001), (0, 10.0), (True, 5), (0, "9"), (None, 3), (0, False)]:
    assert rej(*bad), bad

def isprime(n):
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True

random.seed(7017)
for _ in range(120):
    lo = random.choice([0, random.randint(0, 3000), random.randint(0, 50)])
    hi = lo + random.randint(0, random.choice([5, 40, 400]))
    ps = [p for p in range(lo, hi + 1) if isprime(p)]
    want = None
    for p, q in zip(ps, ps[1:]):
        if want is None or q - p > want[0]:
            want = (q - p, p, q)
    assert W(lo, hi) == want, (lo, hi)
''', r'''
def widest_prime_gap(lo, hi):
    for v in (lo, hi):
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("ints required")
    if not 0 <= lo <= hi <= 2_000_000:
        raise ValueError("need 0 <= lo <= hi <= 2000000")
    if hi < 2:
        return None
    sieve = bytearray([1]) * (hi + 1)
    sieve[0] = sieve[1] = 0
    i = 2
    while i * i <= hi:
        if sieve[i]:
            sieve[i * i::i] = bytes(len(range(i * i, hi + 1, i)))
        i += 1
    best, prev = None, None
    p = sieve.find(1, max(lo, 2))
    while p != -1:
        if prev is not None and (best is None or p - prev > best[0]):
            best = (p - prev, prev, p)
        prev = p
        p = sieve.find(1, p + 1)
    return best
''')

task("v7_18_perm_rank", r'''
Write `perm_at(items, k)` and `perm_rank(perm)` for permutations in lexicographic order.

Take a collection of distinct ints and sort it ascending. List all permutations of it in lexicographic order (compare
as Python compares lists); index them from 0. For [1, 2, 3] the list is [1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1],
[3, 1, 2], [3, 2, 1].

- perm_at(items, k): `items` is a list or tuple of distinct ints in any order (its order does not matter, only its
  set of values). Return the permutation at index k as a list. 0 <= k < n! is required, where n = len(items).
- perm_rank(perm): `perm` is a list or tuple of distinct ints. Return its index in the list built from its own values
  (so perm_rank(perm_at(items, k)) == k).

There can be up to 20 items, so n! is far too many to list: work out each position from factorials (with m items
left, each choice of the next item covers (m - 1)! permutations).

Validation (ValueError): not a list or tuple; an item that is not an int (a bool is not accepted); repeated values;
for perm_at, k not an int (not a bool) or out of range. With no items, perm_at([], 0) == [] and perm_rank([]) == 0.

Examples:
- perm_at([1, 2, 3], 0) == [1, 2, 3] and perm_at([3, 1, 2], 5) == [3, 2, 1]
- perm_at([1, 2, 3, 4], 9) == [2, 3, 4, 1] and perm_rank([2, 3, 4, 1]) == 9
- perm_rank((10, -5)) == 1 and perm_at([], 0) == []
- ValueError: perm_at([1, 2], 2), perm_at([1, 1], 0), perm_at([1, 2], -1), perm_rank([1, True]), perm_rank("12")
''', r'''
import random
from itertools import permutations
from math import factorial

PA, PR = perm_at, perm_rank

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert PA([1, 2, 3], 0) == [1, 2, 3] and PA([3, 1, 2], 5) == [3, 2, 1]
assert PA([1, 2, 3, 4], 9) == [2, 3, 4, 1] and PR([2, 3, 4, 1]) == 9
assert PR((10, -5)) == 1 and PA([], 0) == [] and PR([]) == 0 and PA((7,), 0) == [7]
assert [PA([1, 2, 3], i) for i in range(6)] == [[1, 2, 3], [1, 3, 2], [2, 1, 3], [2, 3, 1], [3, 1, 2], [3, 2, 1]]
for a in [([1, 2], 2), ([1, 1], 0), ([1, 2], -1), ([1, 2], True), ([1, 2], 1.0), ("12", 0), ([1, 2.0], 0), ([True], 0), (None, 0), ([], 1)]:
    assert rej(PA, *a), a
for a in ([1, True], "12", [1, 1], None, [1.5], {1, 2}):
    assert rej(PR, a), a

random.seed(7018)
for _ in range(60):
    n = random.randint(0, 6)
    items = random.sample(range(-20, 20), n)
    allp = [list(p) for p in permutations(sorted(items))]
    for k in random.sample(range(len(allp)), min(len(allp), 8)):
        assert PA(items, k) == allp[k], (items, k)
        assert PA(tuple(items), k) == allp[k]
        assert PR(allp[k]) == k
    assert rej(PA, items, len(allp))
for _ in range(200):
    n = random.randint(7, 20)
    items = random.sample(range(-1000, 1000), n)
    k = random.randrange(factorial(n))
    p = PA(items, k)
    assert sorted(p) == sorted(items) and PR(p) == k, (items, k)
    if k + 1 < factorial(n):
        assert p < PA(items, k + 1)
    assert PA(items, 0) == sorted(items) and PA(items, factorial(n) - 1) == sorted(items, reverse=True)
''', r'''
from math import factorial


def _distinct_ints(xs):
    if not isinstance(xs, (list, tuple)):
        raise ValueError("a list or tuple is required")
    if any(not isinstance(x, int) or isinstance(x, bool) for x in xs) or len(set(xs)) != len(xs):
        raise ValueError("distinct ints required")
    return sorted(xs)


def perm_at(items, k):
    pool = _distinct_ints(items)
    if not isinstance(k, int) or isinstance(k, bool) or not 0 <= k < factorial(len(pool)):
        raise ValueError("k out of range")
    out = []
    for m in range(len(pool), 0, -1):
        q, k = divmod(k, factorial(m - 1))
        out.append(pool.pop(q))
    return out


def perm_rank(perm):
    pool = _distinct_ints(perm)
    r = 0
    for x in perm:
        j = pool.index(x)
        r += j * factorial(len(pool) - 1)
        pool.pop(j)
    return r
''')

task("v7_19_change_ways", r'''
Write `change_ways(amount, coins, limit=None)` that counts the ways to pay an amount with coins.

`coins` is a list or tuple of distinct positive ints (the coin values); `amount` is an int >= 0. A way to pay is a
choice of how many coins of each value to use so that the values add up to `amount`; the order of coins does not
matter, so 1 + 2 and 2 + 1 are the same way. With `limit` = None any number of each coin may be used; with an int
`limit` >= 0, at most `limit` coins of each value may be used. Return the number of ways (an int, possibly large).
Paying 0 always has exactly one way (use no coins), even with no coins at all.

Validation (ValueError): amount not an int or negative; coins not a list or tuple; a coin that is not an int or is
< 1; repeated coin values; limit neither None nor an int >= 0. A bool is never accepted as an int.

Sizes: amount up to 1000 without a limit and up to 300 with one, at most 10 coins. Use dynamic programming over
amounts (one coin value at a time), not enumeration.

Examples:
- change_ways(5, [1, 2, 5]) == 4   (5, 2+2+1, 2+1+1+1, 1+1+1+1+1)
- change_ways(3, [2]) == 0 and change_ways(0, [7]) == 1 and change_ways(0, []) == 1 and change_ways(4, []) == 0
- change_ways(100, [1, 5, 10, 25, 50]) == 292
- change_ways(5, [1, 2, 5], limit=1) == 1 and change_ways(5, [1, 2, 5], limit=2) == 2
- change_ways(9, [3], limit=3) == 1 and change_ways(12, [3], limit=3) == 0
- ValueError: change_ways(-1, [1]), change_ways(5, [0, 1]), change_ways(5, [2, 2]), change_ways(5, [1], limit=-1),
  change_ways(True, [1])
''', r'''
import random

CW = change_ways

def rej(*a, **kw):
    try:
        CW(*a, **kw)
    except ValueError:
        return True
    return False

assert CW(5, [1, 2, 5]) == 4 and CW(3, [2]) == 0 and CW(0, [7]) == 1 and CW(0, []) == 1 and CW(4, []) == 0
assert CW(100, [1, 5, 10, 25, 50]) == 292 and CW(100, (50, 25, 10, 5, 1)) == 292
assert CW(5, [1, 2, 5], limit=1) == 1 and CW(5, [1, 2, 5], limit=2) == 2
assert CW(9, [3], limit=3) == 1 and CW(12, [3], limit=3) == 0 and CW(0, [1], limit=0) == 1 and CW(1, [1], limit=0) == 0
assert CW(1000, [1, 2, 5, 10, 20, 50, 100, 200]) == 321335886
for a, kw in [((-1, [1]), {}), ((5, [0, 1]), {}), ((5, [2, 2]), {}), ((5, [1]), {"limit": -1}), ((True, [1]), {}),
              ((5, None), {}), ((5, [1.0]), {}), ((5, [True]), {}), ((5.0, [1]), {}), ((5, [1]), {"limit": True}),
              ((5, [1]), {"limit": 2.0}), ((5, "12"), {}), ((5, [-3]), {})]:
    assert rej(*a, **kw), (a, kw)

def brute(amount, coins, limit):
    def go(i, rest):
        if i == len(coins):
            return 1 if rest == 0 else 0
        total, k = 0, 0
        while k * coins[i] <= rest and (limit is None or k <= limit):
            total += go(i + 1, rest - k * coins[i])
            k += 1
        return total
    return go(0, amount)

random.seed(7019)
for _ in range(250):
    coins = random.sample(range(1, 15), random.randint(0, 4))
    amount = random.randint(0, 40)
    limit = random.choice([None, None, 0, 1, 2, 3, 10])
    assert CW(amount, coins, limit) == brute(amount, coins, limit), (amount, coins, limit)
for _ in range(4):
    coins = random.sample(range(1, 40), 10)
    amount = random.randint(250, 300)
    lim = random.randint(1, 12)
    a, b = CW(amount, coins, lim), CW(amount, coins)
    assert 0 <= a <= b
    assert CW(amount, coins, amount) == b
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def change_ways(amount, coins, limit=None):
    if not _isint(amount) or amount < 0:
        raise ValueError("amount must be an int >= 0")
    if not isinstance(coins, (list, tuple)) or not all(_isint(c) and c >= 1 for c in coins):
        raise ValueError("coins must be positive ints")
    if len(set(coins)) != len(coins):
        raise ValueError("repeated coin")
    if limit is not None and (not _isint(limit) or limit < 0):
        raise ValueError("limit must be None or an int >= 0")
    ways = [1] + [0] * amount
    for c in coins:
        if limit is None:
            for a in range(c, amount + 1):
                ways[a] += ways[a - c]
            continue
        new = [0] * (amount + 1)
        for r in range(min(c, amount + 1)):
            idxs = list(range(r, amount + 1, c))
            window = 0
            for j, a in enumerate(idxs):
                window += ways[a]
                if j > limit:
                    window -= ways[idxs[j - limit - 1]]
                new[a] = window
        ways = new
    return ways[amount]
''')

task("v7_20_radix_text", r'''
Write `to_base(n, base)` and `from_base(text, base)` that convert between ints and their text in a base from 2 to 36.

The digits are 0-9 for the values 0 to 9 and the ASCII letters a-z for the values 10 to 35. `base` must be an int from
2 to 36 and `n` an int; a bool is never accepted. Otherwise ValueError.

to_base(n, base): the usual representation with lowercase letters, no leading zeros, "0" for zero, and a "-" in front
of negative numbers. No prefix such as "0x".

from_base(text, base): `text` must be a str (else ValueError). It accepts exactly the canonical form, in either letter
case:
- an optional leading "-" (a "+" is not allowed), then one or more digits, each a valid digit for `base` (upper and
  lower case letters both work: "FF" and "ff" are 255 in base 16);
- no leading zeros, except the single digit "0", and "-0" is not allowed;
- nothing else: no blanks, no underscores, no prefix, no non-ASCII digits.
Anything else raises ValueError. Note that Python's int(text, base) is more permissive than this (it accepts "+5",
" 5", "1_0", "007"), so it cannot be used unchecked.

Examples:
- to_base(255, 16) == "ff" and to_base(-10, 2) == "-1010" and to_base(0, 7) == "0" and to_base(35, 36) == "z"
- from_base("FF", 16) == 255 and from_base("-1010", 2) == -10 and from_base("0", 36) == 0 and from_base("zZ", 36) == 1295
- ValueError: from_base("012", 10), from_base("-0", 10), from_base("+5", 10), from_base("1_0", 10),
  from_base(" 5", 10), from_base("9", 8), from_base("", 10), to_base(5, 1), to_base(5, 37), to_base(True, 10)
''', r'''
import random, re

TB, FB = to_base, from_base
D = "0123456789abcdefghijklmnopqrstuvwxyz"

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert TB(255, 16) == "ff" and TB(-10, 2) == "-1010" and TB(0, 7) == "0" and TB(35, 36) == "z"
assert FB("FF", 16) == 255 and FB("-1010", 2) == -10 and FB("0", 36) == 0 and FB("zZ", 36) == 1295
assert TB(10**30, 36) == "2oy99wnkl1c76diocq9s" and FB("2OY99WNKL1C76DIOCQ9S", 36) == 10**30
for a in [("012", 10), ("-0", 10), ("+5", 10), ("1_0", 10), (" 5", 10), ("9", 8), ("", 10), ("-", 10), ("5 ", 10),
          ("0x1f", 16), ("١", 10), ("K", 36), ("1", 1), ("1", 37), ("1", True), (5, 10), (None, 10), ("00", 2), ("--1", 10), ("1.0", 10)]:
    assert rej(FB, *a), a
for a in [(5, 1), (5, 37), (True, 10), (5.0, 10), ("5", 10), (5, 10.0), (5, False)]:
    assert rej(TB, *a), a

def canon(s, b):
    digits = D[:b] + D[10:b].upper()
    return re.fullmatch(r"-?(0|[%s][%s]*)" % (re.escape(digits.replace("0", "")), re.escape(digits)), s) and s != "-0"

random.seed(7020)
for _ in range(600):
    b = random.randint(2, 36)
    n = random.choice([random.randint(-50, 50), random.randint(-10**12, 10**12), random.randint(-10**40, 10**40)])
    s = TB(n, b)
    assert int(s, b) == n and s == s.lower() and canon(s, b), (n, b, s)
    if b in (2, 8, 10, 16):
        assert s == format(n, {2: "b", 8: "o", 10: "d", 16: "x"}[b])
    mixed = "".join(c.upper() if random.random() < 0.5 else c for c in s)
    assert FB(mixed, b) == n
for _ in range(2500):
    b = random.randint(2, 36)
    s = "".join(random.choice("0129azAZ-+ _") for _ in range(random.randint(0, 4)))
    if canon(s, b):
        assert FB(s, b) == int(s, b), (s, b)
    else:
        assert rej(FB, s, b), (s, b)
''', r'''
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
_ALLOWED = set(DIGITS) | set(DIGITS[10:].upper())


def _check_base(base):
    if not isinstance(base, int) or isinstance(base, bool) or not 2 <= base <= 36:
        raise ValueError("base must be an int from 2 to 36")


def to_base(n, base):
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError("n must be an int")
    _check_base(base)
    if n == 0:
        return "0"
    neg, n, out = n < 0, abs(n), []
    while n:
        n, r = divmod(n, base)
        out.append(DIGITS[r])
    return ("-" if neg else "") + "".join(reversed(out))


def from_base(text, base):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    _check_base(base)
    neg = text.startswith("-")
    s = text[1:] if neg else text
    if not s or (len(s) > 1 and s[0] == "0") or (neg and s == "0"):
        raise ValueError("not canonical")
    v = 0
    for ch in s:
        if ch not in _ALLOWED or DIGITS.index(ch.lower()) >= base:
            raise ValueError("bad digit")
        v = v * base + DIGITS.index(ch.lower())
    return -v if neg else v
''')

task("v7_21_island_stats", r'''
Write `island_stats(grid)` that counts the islands in a grid map and measures the largest one.

`grid` is a list or tuple of str rows, all of the same length, made only of "#" (land) and "." (water). A list with
no rows is fine, and so are rows of length 0. Anything else (not a list or tuple, a row that is not a str, rows of
different lengths, any other character) raises ValueError.

Two land cells belong to the same island when you can walk from one to the other through land cells, stepping up,
down, left or right (not diagonally). Return a tuple (count, largest): the number of islands and the number of cells in
the largest island. With no land at all, return (0, 0).

Grids can be up to 300 by 300, and one island can cover almost all of it, so use an iterative search (a queue or an
explicit stack) rather than recursion, which would exceed Python's recursion limit.

Examples:
- island_stats(["#..#", "##.#", "...."]) == (2, 3)
- island_stats(["#.#", ".#.", "#.#"]) == (5, 1)   (diagonal neighbours do not connect)
- island_stats(["###", "#.#", "###"]) == (1, 8)
- island_stats([]) == (0, 0) and island_stats(["...."]) == (0, 0) and island_stats(["", ""]) == (0, 0)
- ValueError: island_stats(["#.", "#"]), island_stats(["#x"]), island_stats("#."), island_stats([1])
''', r'''
import random

I = island_stats

def rej(x):
    try:
        I(x)
    except ValueError:
        return True
    return False

assert I(["#..#", "##.#", "...."]) == (2, 3) and I(["#.#", ".#.", "#.#"]) == (5, 1) and I(["###", "#.#", "###"]) == (1, 8)
assert I([]) == (0, 0) and I(["...."]) == (0, 0) and I(["", ""]) == (0, 0) and I(("#",)) == (1, 1)
for bad in (["#.", "#"], ["#x"], "#.", [1], None, ["# "], [b"#."], ["#", None]):
    assert rej(bad), bad

def oracle(g):
    H = len(g)
    W = len(g[0]) if H else 0
    parent = {}
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i in range(H):
        for j in range(W):
            if g[i][j] == "#":
                parent[(i, j)] = (i, j)
    for (i, j) in list(parent):
        for nb in ((i + 1, j), (i, j + 1)):
            if nb in parent:
                ra, rb = find((i, j)), find(nb)
                if ra != rb:
                    parent[ra] = rb
    sizes = {}
    for c in parent:
        r = find(c)
        sizes[r] = sizes.get(r, 0) + 1
    return (len(sizes), max(sizes.values()) if sizes else 0)

random.seed(7021)
for _ in range(250):
    H, W = random.randint(0, 12), random.randint(0, 12)
    p = random.random()
    g = ["".join("#" if random.random() < p else "." for _ in range(W)) for _ in range(H)]
    assert I(g) == oracle(g), g
g = ["".join("#" if random.random() < 0.55 else "." for _ in range(300)) for _ in range(300)]
assert I(g) == oracle(g)
snake = ["#" * 300 if r % 2 == 0 else ("." * 299 + "#" if r % 4 == 1 else "#" + "." * 299) for r in range(300)]
assert I(snake) == (1, 150 * 300 + 150)
''', r'''
from collections import deque


def island_stats(grid):
    if not isinstance(grid, (list, tuple)) or not all(isinstance(r, str) for r in grid):
        raise ValueError("grid must be a list or tuple of str")
    if grid and len({len(r) for r in grid}) != 1:
        raise ValueError("rows of different lengths")
    if any(c not in "#." for r in grid for c in r):
        raise ValueError("bad character")
    H = len(grid)
    W = len(grid[0]) if H else 0
    seen = [[False] * W for _ in range(H)]
    count = best = 0
    for i in range(H):
        for j in range(W):
            if grid[i][j] != "#" or seen[i][j]:
                continue
            count += 1
            size = 0
            seen[i][j] = True
            q = deque([(i, j)])
            while q:
                a, b = q.popleft()
                size += 1
                for x, y in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= x < H and 0 <= y < W and grid[x][y] == "#" and not seen[x][y]:
                        seen[x][y] = True
                        q.append((x, y))
            best = max(best, size)
    return (count, best)
''')

task("v7_22_course_order", r'''
Write `course_order(n, prereqs)` that returns the lexicographically smallest order in which to take n courses.

Courses are numbered 0 to n-1. `prereqs` is a list or tuple of pairs (a, b) (tuples or lists of two ints), each
meaning course a must come before course b. An order is a list containing every course exactly once in which, for
every pair, a appears before b. Return the order that is smallest in lexicographic order (compare lists as Python
does); return None if no order exists, which happens exactly when the requirements contain a cycle (a pair (a, a)
counts as a cycle). Repeated pairs are allowed and change nothing.

The smallest order can be built step by step: always take the smallest-numbered course whose prerequisites are all
already taken (a min-heap of available courses does this efficiently).

Validation (ValueError): n is not an int >= 0; prereqs is not a list or tuple; a pair is not a tuple or list of two
ints in 0..n-1. A bool is never accepted as an int. n can be up to 100000 with up to 200000 pairs.

Examples:
- course_order(3, []) == [0, 1, 2]
- course_order(3, [(2, 0)]) == [1, 2, 0]
- course_order(4, [(3, 1), (2, 1)]) == [0, 2, 3, 1]
- course_order(2, [(0, 1), (1, 0)]) is None and course_order(1, [(0, 0)]) is None
- course_order(0, []) == [] and course_order(2, [[1, 0], [1, 0]]) == [1, 0]
- ValueError: course_order(2, [(0, 2)]), course_order(-1, []), course_order(2, [(0,)]), course_order(2, None)
''', r'''
import random
from itertools import permutations

CO = course_order

def rej(*a):
    try:
        CO(*a)
    except ValueError:
        return True
    return False

assert CO(3, []) == [0, 1, 2] and CO(3, [(2, 0)]) == [1, 2, 0] and CO(4, [(3, 1), (2, 1)]) == [0, 2, 3, 1]
assert CO(2, [(0, 1), (1, 0)]) is None and CO(1, [(0, 0)]) is None and CO(0, []) == [] and CO(2, [[1, 0], [1, 0]]) == [1, 0]
assert CO(3, ((1, 0), (2, 0), (2, 1))) == [2, 1, 0]
for bad in [(2, [(0, 2)]), (-1, []), (2, [(0,)]), (2, None), (True, []), (2.0, []), (2, [(0, True)]), (2, [(0, 1.0)]),
            (2, [None]), (2, [(0, 1, 1)]), (2, [(-1, 0)]), (2, "01")]:
    assert rej(*bad), bad

def brute(n, pairs):
    for p in permutations(range(n)):
        pos = {c: i for i, c in enumerate(p)}
        if all(pos[a] < pos[b] for a, b in pairs):
            return list(p)
    return None

random.seed(7022)
for _ in range(300):
    n = random.randint(0, 6)
    pairs = [(random.randrange(n), random.randrange(n)) for _ in range(random.randint(0, 8))] if n else []
    pairs = [p for p in pairs if p[0] != p[1] or random.random() < 0.1]
    assert CO(n, pairs) == brute(n, pairs), (n, pairs)
n = 100000
perm = list(range(n))
random.shuffle(perm)
pairs = [(perm[i], perm[i + 1]) for i in range(n - 1)]
assert CO(n, pairs) == perm
pairs.append((perm[-1], perm[0]))
assert CO(n, pairs) is None
''', r'''
import heapq


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def course_order(n, prereqs):
    if not _isint(n) or n < 0:
        raise ValueError("n must be an int >= 0")
    if not isinstance(prereqs, (list, tuple)):
        raise ValueError("prereqs must be a list or tuple")
    indeg = [0] * n
    adj = [[] for _ in range(n)]
    for p in prereqs:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_isint(x) and 0 <= x < n for x in p):
            raise ValueError("bad pair")
        adj[p[0]].append(p[1])
        indeg[p[1]] += 1
    heap = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        u = heapq.heappop(heap)
        out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)
    return out if len(out) == n else None
''')

task("v7_23_shoelace", r'''
Write `shoelace(points)` that measures a closed polygon given by integer vertices.

`points` is a list or tuple of at least 3 vertices, each a tuple or list of two ints (x, y) (a bool is not an int
here); otherwise ValueError. The polygon goes from each vertex to the next and from the last back to the first. It
does not have to be simple (edges may cross), and repeated vertices are allowed.

Return a tuple (twice_area, boundary, orientation):
- S = the sum over all edges (x1, y1) -> (x2, y2) of x1 * y2 - x2 * y1 (the shoelace sum). twice_area is the absolute
  value of S, an int;
- orientation is "ccw" if S > 0, "cw" if S < 0 and "flat" if S == 0;
- boundary is the sum over all edges of gcd(|x2 - x1|, |y2 - y1|), which is the number of lattice points on the edges
  when no two edges overlap (an edge of length 0 adds 0).

Examples:
- shoelace([(0, 0), (4, 0), (4, 3)]) == (12, 8, "ccw")   (boundary: gcd(4, 0) + gcd(0, 3) + gcd(4, 3) = 4 + 3 + 1)
- shoelace([(0, 0), (0, 2), (2, 2), (2, 0)]) == (8, 8, "cw")
- shoelace([(0, 0), (1, 1), (2, 2)]) == (0, 4, "flat")
- ValueError: shoelace([(0, 0), (1, 1)]), shoelace([(0, 0), (1, 1), (2, 2.5)]), shoelace(None)
''', r'''
import random
from math import gcd

S = shoelace

def rej(x):
    try:
        S(x)
    except ValueError:
        return True
    return False

assert S([(0, 0), (4, 0), (4, 3)]) == (12, 8, "ccw")
assert S([(0, 0), (0, 2), (2, 2), (2, 0)]) == (8, 8, "cw") and S([(0, 0), (1, 1), (2, 2)]) == (0, 4, "flat")
assert S(((0, 0), [3, 0], (0, 3))) == (9, 9, "ccw") and S([(1, 1), (1, 1), (1, 1)]) == (0, 0, "flat")
assert S([(0, 0), (2, 2), (2, 0), (0, 2)]) == (0, 8, "flat")
for bad in ([(0, 0), (1, 1)], [(0, 0), (1, 1), (2, 2.5)], None, [(0, 0), (1, 1), (2,)], [(0, 0), (1, 1), (True, 2)], "abc",
            [(0, 0), (1, 1), None], [(0, 0), (1, 1), (2, 2, 2)]):
    assert rej(bad), bad

def lattice_on_edge(a, b):
    (x1, y1), (x2, y2) = a, b
    if a == b:
        return 0
    cnt = 0
    for x in range(min(x1, x2), max(x1, x2) + 1):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if (x2 - x1) * (y - y1) == (y2 - y1) * (x - x1) and (x, y) != (x1, y1):
                cnt += 1
    return cnt

random.seed(7023)
for _ in range(300):
    pts = [(random.randint(-9, 9), random.randint(-9, 9)) for _ in range(random.randint(3, 8))]
    trap = sum((pts[(i + 1) % len(pts)][0] - pts[i][0]) * (pts[(i + 1) % len(pts)][1] + pts[i][1]) for i in range(len(pts)))
    want_or = "ccw" if trap < 0 else "cw" if trap > 0 else "flat"
    bnd = sum(lattice_on_edge(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    assert S(pts) == (abs(trap), bnd, want_or), pts
    assert S(list(reversed(pts)))[:2] == (abs(trap), bnd)
for _ in range(50):
    pts = [(random.randint(-10**12, 10**12), random.randint(-10**12, 10**12)) for _ in range(random.randint(3, 30))]
    k, dx, dy = random.randint(1, 1000), random.randint(-10**9, 10**9), random.randint(-10**9, 10**9)
    a, b, o = S(pts)
    assert S([(k * x + dx, k * y + dy) for x, y in pts]) == (a * k * k, b * k, o)
''', r'''
from math import gcd


def shoelace(points):
    if not isinstance(points, (list, tuple)) or len(points) < 3:
        raise ValueError("at least 3 vertices required")
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2 or any(not isinstance(c, int) or isinstance(c, bool) for c in p):
            raise ValueError("bad vertex")
    s = b = 0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
        b += gcd(abs(x2 - x1), abs(y2 - y1))
    return (abs(s), b, "ccw" if s > 0 else "cw" if s < 0 else "flat")
''')

task("v7_24_knight_hops", r'''
Write `knight_distance(n, start, goal, blocked=())` that returns the fewest chess-knight moves from start to goal on an
n by n board with some squares blocked.

Squares are (row, col) pairs with 0 <= row, col < n. A knight moves two squares in one direction and one square in a
perpendicular direction (8 possible moves), and may jump over anything, but it may never land on a blocked square or
leave the board. `blocked` is a list, tuple or set of squares.

Return the minimum number of moves, 0 if start == goal (and start is not blocked), or -1 if goal cannot be reached. If
start or goal is itself blocked, return -1.

Validation (ValueError): n is not an int from 1 to 200; start, goal or a blocked entry is not a tuple or list of two
ints inside the board; blocked is not a list, tuple or set. A bool is never accepted as an int.

Use breadth-first search.

Examples:
- knight_distance(8, (0, 0), (7, 7)) == 6
- knight_distance(8, (0, 0), (1, 2)) == 1 and knight_distance(8, (0, 0), (0, 1)) == 3
- knight_distance(3, (0, 0), (1, 1)) == -1   (the centre of a 3 by 3 board cannot be reached)
- knight_distance(1, (0, 0), (0, 0)) == 0
- knight_distance(8, (0, 0), (1, 2), [(1, 2)]) == -1
- knight_distance(4, (0, 0), (3, 3), {(1, 2), (2, 1)}) == -1
- ValueError: knight_distance(0, (0, 0), (0, 0)), knight_distance(8, (8, 0), (0, 0)), knight_distance(8, (0, 0), (0, 0), [(9, 9)])
''', r'''
import random

K = knight_distance
MV = [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]

def rej(*a):
    try:
        K(*a)
    except ValueError:
        return True
    return False

assert K(8, (0, 0), (7, 7)) == 6 and K(8, (0, 0), (1, 2)) == 1 and K(8, (0, 0), (0, 1)) == 3
assert K(3, (0, 0), (1, 1)) == -1 and K(1, (0, 0), (0, 0)) == 0 and K(8, (0, 0), (1, 2), [(1, 2)]) == -1
assert K(4, (0, 0), (3, 3), {(1, 2), (2, 1)}) == -1 and K(2, (0, 0), (1, 1)) == -1 and K(8, [0, 0], [7, 7], ()) == 6
assert K(5, (2, 2), (2, 2), [(2, 2)]) == -1 and K(200, (0, 0), (199, 199)) == 134
for bad in [(0, (0, 0), (0, 0)), (8, (8, 0), (0, 0)), (8, (0, 0), (0, 0), [(9, 9)]), (201, (0, 0), (0, 0)), (True, (0, 0), (0, 0)),
            (8, (0, 0.0), (0, 0)), (8, (0,), (0, 0)), (8, (0, 0), (0, 0), None), (8, (0, 0), (0, 0), [(True, 1)]),
            (8, (0, 0), (0, 0), "ab"), (8, (-1, 0), (0, 0)), (8.0, (0, 0), (0, 0))]:
    assert rej(*bad), bad

def relax(n, s, g, B):
    if s in B or g in B:
        return -1
    INF = float("inf")
    d = {(r, c): INF for r in range(n) for c in range(n) if (r, c) not in B}
    d[s] = 0
    changed = True
    while changed:
        changed = False
        for (r, c), v in list(d.items()):
            if v == INF:
                continue
            for dr, dc in MV:
                t = (r + dr, c + dc)
                if t in d and d[t] > v + 1:
                    d[t] = v + 1
                    changed = True
    return -1 if d[g] == INF else d[g]

random.seed(7024)
for _ in range(200):
    n = random.randint(1, 7)
    cells = [(r, c) for r in range(n) for c in range(n)]
    s, g = random.choice(cells), random.choice(cells)
    B = set(random.sample(cells, random.randint(0, len(cells) // 2)))
    arg = random.choice([list, tuple, set])(B)
    assert K(n, s, g, arg) == relax(n, s, g, B), (n, s, g, B)
''', r'''
from collections import deque

MOVES = ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1))


def knight_distance(n, start, goal, blocked=()):
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 200:
        raise ValueError("n must be an int from 1 to 200")

    def square(p):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("bad square")
        if any(not isinstance(c, int) or isinstance(c, bool) or not 0 <= c < n for c in p):
            raise ValueError("bad square")
        return (p[0], p[1])

    if not isinstance(blocked, (list, tuple, set)):
        raise ValueError("blocked must be a list, tuple or set")
    s, g = square(start), square(goal)
    B = {square(p) for p in blocked}
    if s in B or g in B:
        return -1
    if s == g:
        return 0
    dist = {s: 0}
    q = deque([s])
    while q:
        r, c = q.popleft()
        for dr, dc in MOVES:
            t = (r + dr, c + dc)
            if 0 <= t[0] < n and 0 <= t[1] < n and t not in B and t not in dist:
                dist[t] = dist[(r, c)] + 1
                if t == g:
                    return dist[t]
                q.append(t)
    return -1
''')

task("v7_25_point_location", r'''
Write `locate_points(polygon, points)` that classifies points against a simple polygon with integer vertices.

`polygon` is a list or tuple of at least 3 vertices (tuples or lists of two ints), listed in order around the polygon,
clockwise or counter-clockwise. It is simple: its edges (including the closing edge from the last vertex to the first)
do not cross or touch except at shared vertices, and consecutive vertices are distinct. You do not have to check
simplicity. `points` is a list or tuple of points (tuples or lists of two ints). A bool is not an int here; any wrong
type, or fewer than 3 vertices, raises ValueError.

Return a list with one str per point, in order: "boundary" if the point lies on an edge (vertices included), otherwise
"inside" or "outside".

Method (exact integer arithmetic, no floats): a point is on the edge from A to B when the cross product of B - A and
P - A is 0 and P lies within the bounding box of A and B. Otherwise cast a ray from P to the right (towards +x): P is
inside when the ray crosses an odd number of edges, where an edge counts as crossed when its endpoints lie on
different sides of the horizontal line through P (one strictly above, the other on or below) and its crossing point is
strictly to the right of P.

Examples:
- locate_points([(0, 0), (4, 0), (4, 4), (0, 4)], [(2, 2), (4, 2), (5, 5), (0, 0), (4, 5)]) ==
  ["inside", "boundary", "outside", "boundary", "outside"]
- locate_points([(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)], [(1, 5), (3, 5), (3, 2), (3, 1), (5, 4)]) ==
  ["inside", "outside", "boundary", "inside", "inside"]
- locate_points([(0, 0), (4, 0), (0, 4)], []) == []
- ValueError: locate_points([(0, 0), (1, 1)], [(0, 0)]), locate_points([(0, 0), (1, 0), (0, 1)], [(0.5, 0)])
''', r'''
import random, math

LP = locate_points

def rej(*a):
    try:
        LP(*a)
    except ValueError:
        return True
    return False

SQ = [(0, 0), (4, 0), (4, 4), (0, 4)]
U = [(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)]
assert LP(SQ, [(2, 2), (4, 2), (5, 5), (0, 0), (4, 5)]) == ["inside", "boundary", "outside", "boundary", "outside"]
assert LP(U, [(1, 5), (3, 5), (3, 2), (3, 1), (5, 4)]) == ["inside", "outside", "boundary", "inside", "inside"]
assert LP([(0, 0), (4, 0), (0, 4)], []) == [] and LP(tuple(reversed(SQ)), ((2, 2), [-1, 2])) == ["inside", "outside"]
assert LP(U, [(3, 6), (2, 4), (4, 4), (6, 6), (-1, 0), (7, 0), (3, 0), (5, 2)]) == ["outside", "boundary", "boundary", "boundary", "outside", "outside", "boundary", "inside"]
for bad in [([(0, 0), (1, 1)], [(0, 0)]), ([(0, 0), (1, 0), (0, 1)], [(0.5, 0)]), (None, []), ([(0, 0), (1, 0), (0, 1)], None),
            ([(0, 0), (1, 0), (0, True)], []), ([(0, 0), (1, 0), (0, 1)], [(1,)]), ([(0, 0), (1, 0), (0,)], [])]:
    assert rej(*bad), bad

def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def on_seg(p, a, b):
    return cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])

def star(rng):
    while True:
        pts = {(rng.randint(-20, 20), rng.randint(-20, 20)) for _ in range(rng.randint(3, 10))}
        pts.discard((0, 0))
        vs = sorted(pts, key=lambda p: math.atan2(p[1], p[0]))
        if len(vs) < 3:
            continue
        if all(cross((0, 0), vs[i], vs[(i + 1) % len(vs)]) > 0 for i in range(len(vs))):
            return vs

def classify(p, vs):
    n = len(vs)
    if any(on_seg(p, vs[i], vs[(i + 1) % n]) for i in range(n)):
        return "boundary"
    for i in range(n):
        a, b = vs[i], vs[(i + 1) % n]
        if cross((0, 0), a, p) >= 0 and cross(a, b, p) >= 0 and cross(b, (0, 0), p) >= 0:
            return "inside"
    return "outside"

random.seed(7025)
for _ in range(150):
    vs = star(random)
    k = random.randrange(len(vs))
    poly = vs[k:] + vs[:k]
    if random.random() < 0.5:
        poly = poly[::-1]
    pts = [(random.randint(-22, 22), random.randint(-22, 22)) for _ in range(30)] + random.sample(vs, 2)
    pts += [((a[0] + b[0]) // 2, (a[1] + b[1]) // 2) for a, b in zip(vs, vs[1:] + vs[:1]) if (a[0] + b[0]) % 2 == 0 and (a[1] + b[1]) % 2 == 0]
    assert LP(poly, pts) == [classify(p, vs) for p in pts], (poly, pts)
''', r'''
def _pt(p):
    if not isinstance(p, (list, tuple)) or len(p) != 2 or any(not isinstance(c, int) or isinstance(c, bool) for c in p):
        raise ValueError("bad point")
    return (p[0], p[1])


def locate_points(polygon, points):
    if not isinstance(polygon, (list, tuple)) or len(polygon) < 3 or not isinstance(points, (list, tuple)):
        raise ValueError("bad arguments")
    poly = [_pt(v) for v in polygon]
    pts = [_pt(p) for p in points]
    n = len(poly)
    res = []
    for px, py in pts:
        inside = on = False
        for i in range(n):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
            if (x2 - x1) * (py - y1) == (y2 - y1) * (px - x1) and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2):
                on = True
                break
            if (y1 > py) != (y2 > py):
                lhs, rhs = (px - x1) * (y2 - y1), (py - y1) * (x2 - x1)
                if (lhs < rhs) if y2 > y1 else (lhs > rhs):
                    inside = not inside
        res.append("boundary" if on else "inside" if inside else "outside")
    return res
''')

task("v7_26_teller_queue", r'''
Write `teller_finish(customers, tellers)` that simulates a bank with several tellers and one first-come-first-served
queue.

`customers` is a list or tuple of (arrival, service) pairs (tuples or lists of two ints) with arrival >= 0 and
service >= 1; `tellers` is an int >= 1. A bool is never accepted as an int; anything else raises ValueError.

Rules:
1. Customers are served in order of arrival time; customers who arrive at the same time keep their order in the input.
2. Each teller has a "free at" time, initially 0. A teller is free at time t when its free-at time is <= t.
3. When it is a customer's turn, the customer starts at time t = max(arrival, the smallest free-at time among all
   tellers). Among the tellers free at time t, the customer takes the one with the lowest number (tellers are numbered
   from 0).
4. The customer finishes at t + service, and that teller's free-at time becomes t + service.

Return a list with one tuple (finish_time, teller) per customer, in the order of the input list (not the serving
order).

Examples:
- teller_finish([(0, 5), (1, 3), (2, 1)], 2) == [(5, 0), (4, 1), (5, 1)]
- teller_finish([(3, 2), (0, 4)], 1) == [(6, 0), (4, 0)]
- teller_finish([(0, 2), (0, 2), (0, 2)], 2) == [(2, 0), (2, 1), (4, 0)]
- teller_finish([(10, 1)], 3) == [(11, 0)] and teller_finish([], 1) == []
- ValueError: teller_finish([(0, 0)], 1), teller_finish([(-1, 2)], 1), teller_finish([(0, 1)], 0), teller_finish([(0,)], 1)
''', r'''
import random

TF = teller_finish

def rej(*a):
    try:
        TF(*a)
    except ValueError:
        return True
    return False

assert TF([(0, 5), (1, 3), (2, 1)], 2) == [(5, 0), (4, 1), (5, 1)] and TF([(3, 2), (0, 4)], 1) == [(6, 0), (4, 0)]
assert TF([(0, 2), (0, 2), (0, 2)], 2) == [(2, 0), (2, 1), (4, 0)] and TF([(10, 1)], 3) == [(11, 0)] and TF([], 1) == []
assert TF(([5, 1], (0, 10), (5, 1)), 2) == [(6, 1), (10, 0), (7, 1)]
assert TF([(0, 3), (1, 1), (4, 1)], 2) == [(3, 0), (2, 1), (5, 0)]
for bad in [([(0, 0)], 1), ([(-1, 2)], 1), ([(0, 1)], 0), ([(0,)], 1), (None, 1), ([(0, 1)], True), ([(0, 1.0)], 1),
            ([(True, 1)], 1), ([(0, 1)], 1.0), ([None], 1), ([(0, 1, 1)], 1)]:
    assert rej(*bad), bad

def tick(cs, k):
    order = sorted(range(len(cs)), key=lambda i: (cs[i][0], i))
    free = [0] * k
    res = [None] * len(cs)
    p, t = 0, 0
    while p < len(order):
        while p < len(order) and cs[order[p]][0] <= t:
            idle = [j for j in range(k) if free[j] <= t]
            if not idle:
                break
            j = idle[0]
            free[j] = t + cs[order[p]][1]
            res[order[p]] = (free[j], j)
            p += 1
        t += 1
    return res

random.seed(7026)
for _ in range(400):
    k = random.randint(1, 4)
    cs = [(random.randint(0, 30), random.randint(1, 10)) for _ in range(random.randint(0, 12))]
    assert TF(cs, k) == tick(cs, k), (cs, k)
cs = [(random.randint(0, 10**6), random.randint(1, 1000)) for _ in range(20000)]
r = TF(cs, 7)
assert len(r) == 20000 and all(f >= a + s and 0 <= j < 7 for (f, j), (a, s) in zip(r, cs))
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def teller_finish(customers, tellers):
    if not _isint(tellers) or tellers < 1:
        raise ValueError("tellers must be an int >= 1")
    if not isinstance(customers, (list, tuple)):
        raise ValueError("customers must be a list or tuple")
    for c in customers:
        if not isinstance(c, (list, tuple)) or len(c) != 2 or not all(_isint(x) for x in c) or c[0] < 0 or c[1] < 1:
            raise ValueError("bad customer")
    free = [0] * tellers
    res = [None] * len(customers)
    for i in sorted(range(len(customers)), key=lambda i: (customers[i][0], i)):
        a, s = customers[i]
        t = max(a, min(free))
        k = next(j for j in range(tellers) if free[j] <= t)
        free[k] = t + s
        res[i] = (t + s, k)
    return res
''')

task("v7_27_lis_count", r'''
Write `lis_stats(seq)` that returns the length of the longest strictly increasing subsequence of `seq` and how many
such longest subsequences there are.

`seq` is a list or tuple of ints (a bool is not an int here); anything else raises ValueError. A subsequence keeps the
original order but may skip elements; it is strictly increasing when each element is larger than the one before.
Subsequences are counted by the positions they use, so equal values at different positions give different
subsequences. Return a tuple (length, count). For an empty seq return (0, 1): the empty subsequence is the only one.

seq can have up to 1000 elements, so a quadratic dynamic program is fine: for each position i, keep the length of the
longest increasing subsequence ending at i and how many reach that length; when an earlier j with seq[j] < seq[i]
gives a longer one, replace both; when it gives an equally long one, add its count.

Examples:
- lis_stats([1, 3, 2, 4]) == (3, 2)   ([1, 3, 4] and [1, 2, 4])
- lis_stats([5, 4, 3]) == (1, 3)
- lis_stats([2, 2, 2]) == (1, 3)   (equal values are not increasing)
- lis_stats([1, 2, 3]) == (3, 1) and lis_stats([]) == (0, 1)
- lis_stats([1, 5, 2, 6, 3, 7]) == (4, 3)   ([1, 5, 6, 7], [1, 2, 6, 7], [1, 2, 3, 7])
- ValueError: lis_stats(None), lis_stats([1, 2.0]), lis_stats([True]), lis_stats("123")
''', r'''
import random

LS = lis_stats

def rej(x):
    try:
        LS(x)
    except ValueError:
        return True
    return False

assert LS([1, 3, 2, 4]) == (3, 2) and LS([5, 4, 3]) == (1, 3) and LS([2, 2, 2]) == (1, 3)
assert LS([1, 2, 3]) == (3, 1) and LS([]) == (0, 1) and LS([1, 5, 2, 6, 3, 7]) == (4, 3) and LS((7,)) == (1, 1)
for bad in (None, [1, 2.0], [True], "123", [1, None], {1, 2}):
    assert rej(bad), bad

def brute(s):
    by_len = {0: 1}
    def dfs(last_i, length):
        for j in range(last_i + 1, len(s)):
            if last_i < 0 or s[j] > s[last_i]:
                by_len[length + 1] = by_len.get(length + 1, 0) + 1
                dfs(j, length + 1)
    dfs(-1, 0)
    m = max(by_len)
    return (m, by_len[m])

random.seed(7027)
for _ in range(200):
    s = [random.randint(-5, 5) for _ in range(random.randint(0, 10))]
    assert LS(s) == brute(s), s
s = list(range(1000))
assert LS(s) == (1000, 1) and LS(s[::-1]) == (1, 1000)
s = [v for i in range(40) for v in (2 * i + 1, 2 * i)]
assert LS(s) == (40, 2 ** 40)
''', r'''
def lis_stats(seq):
    if not isinstance(seq, (list, tuple)) or any(not isinstance(x, int) or isinstance(x, bool) for x in seq):
        raise ValueError("seq must be a list or tuple of ints")
    n = len(seq)
    if n == 0:
        return (0, 1)
    length, count = [1] * n, [1] * n
    for i in range(n):
        for j in range(i):
            if seq[j] < seq[i]:
                if length[j] + 1 > length[i]:
                    length[i], count[i] = length[j] + 1, count[j]
                elif length[j] + 1 == length[i]:
                    count[i] += count[j]
    best = max(length)
    return (best, sum(c for l, c in zip(length, count) if l == best))
''')

task("v7_28_life_board", r'''
Write `life_steps(grid, steps)` that runs Conway's Game of Life on a finite board.

`grid` is a list or tuple of str rows of equal length, made of "#" (alive) and "." (dead); it may have no rows, and
rows may have length 0. `steps` is an int >= 0 (not a bool). Anything else raises ValueError.

The board does not wrap around and does not grow: every cell outside the grid is dead forever. Each step updates all
cells at once from the previous generation. A cell's neighbours are the up to 8 cells around it (horizontally,
vertically and diagonally adjacent) that lie on the board.
- A live cell with 2 or 3 live neighbours stays alive; any other live cell dies.
- A dead cell with exactly 3 live neighbours becomes alive; any other dead cell stays dead.

Return the grid after `steps` steps as a list of str in the same format (a new list; with steps = 0 it equals the
input rows).

Examples:
- life_steps([".....", "..#..", "..#..", "..#..", "....."], 1) == [".....", ".....", ".###.", ".....", "....."]
- life_steps(["##", "##"], 5) == ["##", "##"]
- life_steps(["#"], 1) == ["."] and life_steps([], 3) == []
- life_steps(["###"], 1) == [".#."]   (the cells beyond the edge stay dead, so there is no row to grow into)
- ValueError: life_steps(["#.", "#"], 1), life_steps(["#o"], 1), life_steps(["#"], -1), life_steps(["#"], True)
''', r'''
import random
from collections import Counter

LF = life_steps

def rej(*a):
    try:
        LF(*a)
    except ValueError:
        return True
    return False

assert LF([".....", "..#..", "..#..", "..#..", "....."], 1) == [".....", ".....", ".###.", ".....", "....."]
assert LF(["##", "##"], 5) == ["##", "##"] and LF(["#"], 1) == ["."] and LF([], 3) == [] and LF(["###"], 1) == [".#."]
assert LF(("#.", ".#"), 0) == ["#.", ".#"] and LF(["", ""], 2) == ["", ""]
glider = [".#....", "..#...", "###...", "......", "......", "......"]
assert LF(glider, 4) == ["......", "..#...", "...#..", ".###..", "......", "......"]
for bad in [(["#.", "#"], 1), (["#o"], 1), (["#"], -1), (["#"], True), ("#.", 1), ([1], 1), (["#"], 1.0), (None, 0)]:
    assert rej(*bad), bad

def oracle(g, steps):
    H = len(g)
    W = len(g[0]) if H else 0
    live = {(i, j) for i in range(H) for j in range(W) if g[i][j] == "#"}
    for _ in range(steps):
        cnt = Counter((i + di, j + dj) for i, j in live for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj)
        live = {c for c, k in cnt.items() if 0 <= c[0] < H and 0 <= c[1] < W and (k == 3 or (k == 2 and c in live))}
    return ["".join("#" if (i, j) in live else "." for j in range(W)) for i in range(H)]

random.seed(7028)
for _ in range(120):
    H, W = random.randint(0, 9), random.randint(0, 9)
    p = random.random()
    g = ["".join("#" if random.random() < p else "." for _ in range(W)) for _ in range(H)]
    s = random.randint(0, 12)
    assert LF(g, s) == oracle(g, s), (g, s)
g = ["".join("#" if random.random() < 0.35 else "." for _ in range(25)) for _ in range(25)]
assert LF(g, 30) == oracle(g, 30)
''', r'''
def life_steps(grid, steps):
    if not isinstance(grid, (list, tuple)) or not all(isinstance(r, str) for r in grid):
        raise ValueError("grid must be a list or tuple of str")
    if grid and len({len(r) for r in grid}) != 1:
        raise ValueError("rows of different lengths")
    if any(c not in "#." for r in grid for c in r):
        raise ValueError("bad character")
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
        raise ValueError("steps must be an int >= 0")
    H = len(grid)
    W = len(grid[0]) if H else 0
    cur = [[c == "#" for c in row] for row in grid]
    for _ in range(steps):
        nxt = [[False] * W for _ in range(H)]
        for i in range(H):
            for j in range(W):
                n = 0
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if (di or dj) and 0 <= i + di < H and 0 <= j + dj < W and cur[i + di][j + dj]:
                            n += 1
                nxt[i][j] = n == 3 or (cur[i][j] and n == 2)
        cur = nxt
    return ["".join("#" if c else "." for c in row) for row in cur]
''')

task("v7_29_stack_machine", r'''
Write `run_stack(program)` that runs a tiny stack machine and returns the list of numbers it printed.

`program` is a list or tuple of str instructions, indexed from 0. The machine has a stack of ints (initially empty)
and a program counter pc (initially 0). Each instruction is a lowercase name, optionally followed by exactly one space
and one decimal int operand (an optional "-" then ASCII digits):
- "push N": push N.
- "pop": remove the top. "dup": push a copy of the top. "swap": exchange the top two.
- "add", "sub", "mul": pop b (the top), then pop a, and push a + b, a - b or a * b.
- "print": pop the top and append it to the output.
- "jz T": pop the top; if it is 0, continue at instruction T. "jmp T": continue at instruction T.
- "halt": stop.
After every other instruction pc moves to the next one. The machine stops normally on "halt" or when pc equals
len(program); it then returns the output list.

ValueError for: `program` not a list or tuple, or an instruction that is not a str; an unknown name; a wrong operand
(missing, extra, not an int, or given to an instruction that takes none); a jump target outside 0..len(program)
(checked for every jz and jmp before running, reached or not); popping from a stack with too few items; and running
more than 10000 instructions (count each executed instruction; executing a 10001st raises).

Examples:
- run_stack(["push 2", "push 3", "add", "print"]) == [5]
- run_stack(["push 1", "push 2", "swap", "sub", "print"]) == [1]
- run_stack(["push 3", "dup", "print", "push 1", "sub", "dup", "jz 8", "jmp 1", "halt"]) == [3, 2, 1]
- run_stack([]) == [] and run_stack(["push 7", "halt", "print"]) == []
- ValueError: run_stack(["add"]), run_stack(["push x"]), run_stack(["jmp 5"]), run_stack(["jmp 0"]),
  run_stack(["PUSH 1"]), run_stack(["push  1"]), run_stack(["pop 1"])
''', r'''
import random

R = run_stack

def rej(x):
    try:
        R(x)
    except ValueError:
        return True
    return False

assert R(["push 2", "push 3", "add", "print"]) == [5] and R(["push 1", "push 2", "swap", "sub", "print"]) == [1]
assert R(["push 3", "dup", "print", "push 1", "sub", "dup", "jz 8", "jmp 1", "halt"]) == [3, 2, 1]
assert R([]) == [] and R(["push 7", "halt", "print"]) == [] and R(("push -4", "dup", "mul", "print")) == [16]
assert R(["push 0", "jz 3", "push 9", "push 1", "print"]) == [1] and R(["jmp 1"]) == [] and R(["push 5", "pop"]) == []
for bad in (["add"], ["push x"], ["jmp 5"], ["jmp 0"], ["PUSH 1"], ["push  1"], ["pop 1"], ["push"], ["push 1 2"], ["print"],
            ["push 1", "add"], ["swap"], ["jz 0"], ["push 1", "jz -1"], [5], None, "push 1", ["push +1"], ["push 1.0"],
            ["push 0", "jz 3", "jmp 99"], [" push 1"], ["push 1 "], ["push ١"], ["nop"]):
    assert rej(bad), bad
assert rej(["push 1", "jmp 0"])

def gen(depth):
    if depth == 0 or random.random() < 0.3:
        v = random.randint(-20, 20)
        return ["push %d" % v], "(%d)" % v
    op = random.choice("+-*")
    pa, ea = gen(depth - 1)
    pb, eb = gen(depth - 1)
    return pa + pb + [{"+": "add", "-": "sub", "*": "mul"}[op]], "(%s %s %s)" % (ea, op, eb)

random.seed(7029)
for _ in range(300):
    prog, outs = [], []
    for _ in range(random.randint(1, 3)):
        p, e = gen(random.randint(0, 5))
        prog += p + ["print"]
        outs.append(eval(e))
    assert R(prog) == outs, prog
for _ in range(30):
    k = random.randint(1, 300)
    acc = ["push 0", "push %d" % k, "dup", "jz 12", "swap", "push 1", "add", "swap", "push 1", "sub", "jmp 2", "halt", "pop", "print"]
    assert R(acc) == [k], k
''', r'''
import re

_NUM = re.compile(r"-?[0-9]+")
_NOARG = {"pop", "dup", "swap", "add", "sub", "mul", "print", "halt"}
_ARG = {"push", "jz", "jmp"}


def run_stack(program):
    if not isinstance(program, (list, tuple)):
        raise ValueError("program must be a list or tuple")
    code = []
    for ins in program:
        if not isinstance(ins, str):
            raise ValueError("instructions must be str")
        parts = ins.split(" ")
        if parts[0] in _ARG and len(parts) == 2 and _NUM.fullmatch(parts[1]):
            code.append((parts[0], int(parts[1])))
        elif parts[0] in _NOARG and len(parts) == 1:
            code.append((parts[0], None))
        else:
            raise ValueError("bad instruction")
    n = len(code)
    if any(op in ("jz", "jmp") and not 0 <= arg <= n for op, arg in code):
        raise ValueError("jump target out of range")
    stack, out, pc, steps = [], [], 0, 0

    def pop():
        if not stack:
            raise ValueError("stack underflow")
        return stack.pop()

    while pc < n:
        steps += 1
        if steps > 10000:
            raise ValueError("too many steps")
        op, arg = code[pc]
        pc += 1
        if op == "push":
            stack.append(arg)
        elif op == "pop":
            pop()
        elif op == "dup":
            v = pop()
            stack += [v, v]
        elif op == "swap":
            b, a = pop(), pop()
            stack += [b, a]
        elif op in ("add", "sub", "mul"):
            b, a = pop(), pop()
            stack.append(a + b if op == "add" else a - b if op == "sub" else a * b)
        elif op == "print":
            out.append(pop())
        elif op == "jz":
            if pop() == 0:
                pc = arg
        elif op == "jmp":
            pc = arg
        else:
            break
    return out
''')

task("v7_30_wrap_cost", r'''
Write `wrap_min_cost(words, width)` that breaks words into lines with the least raggedness.

`words` is a list or tuple of str; each word must be non-empty, contain no whitespace character (str.isspace), and be
at most `width` characters long. `width` is an int >= 1 (not a bool). Anything else raises ValueError.

A layout splits the words, in order, into consecutive lines; each line is its words joined by single spaces and must
be at most `width` characters. The cost of a layout is the sum, over every line except the last one, of
(width - line length) squared. The last line costs nothing.

Return a tuple (cost, lines): the minimum cost and a layout achieving it, as a list of line strings. If several
layouts have the minimum cost, return the one whose first line has the most words; if that still ties, the one whose
second line has the most words, and so on. With no words, return (0, []).

Use dynamic programming over suffixes: the best layout of words i..end is the best choice of where the first line
ends plus the best layout of the rest (on equal cost, prefer the longer first line).

Examples:
- wrap_min_cost(["aaa", "bb", "cc", "ddddd"], 6) == (10, ["aaa", "bb cc", "ddddd"])
- wrap_min_cost(["a", "b", "c"], 3) == (0, ["a b", "c"])
- wrap_min_cost(["hello"], 5) == (0, ["hello"]) and wrap_min_cost([], 4) == (0, [])
- wrap_min_cost(["ab", "cd", "ef"], 5) == (0, ["ab cd", "ef"])
- ValueError: wrap_min_cost(["toolong"], 3), wrap_min_cost(["a b"], 5), wrap_min_cost([""], 5), wrap_min_cost(["a"], 0)
''', r'''
import random
from itertools import product

WM = wrap_min_cost

def rej(*a):
    try:
        WM(*a)
    except ValueError:
        return True
    return False

assert WM(["aaa", "bb", "cc", "ddddd"], 6) == (10, ["aaa", "bb cc", "ddddd"]) and WM(["a", "b", "c"], 3) == (0, ["a b", "c"])
assert WM(["hello"], 5) == (0, ["hello"]) and WM([], 4) == (0, []) and WM(["ab", "cd", "ef"], 5) == (0, ["ab cd", "ef"])
assert WM(("a", "a", "a", "a"), 3) == (0, ["a a", "a a"]) and WM(["a", "b"], 1) == (0, ["a", "b"])
for bad in [(["toolong"], 3), (["a b"], 5), ([""], 5), (["a"], 0), (["a\t"], 5), (["a"], True), ("ab", 5), ([1], 5), (["a"], 2.0), (None, 3)]:
    assert rej(*bad), bad

def brute(words, w):
    n = len(words)
    best = None
    for cuts in product([0, 1], repeat=max(n - 1, 0)):
        lines, cur = [], [words[0]]
        for i, c in enumerate(cuts):
            if c:
                lines.append(cur)
                cur = [words[i + 1]]
            else:
                cur.append(words[i + 1])
        lines.append(cur)
        txt = [" ".join(l) for l in lines]
        if any(len(t) > w for t in txt):
            continue
        cost = sum((w - len(t)) ** 2 for t in txt[:-1])
        key = (cost, [-len(l) for l in lines])
        if best is None or key < best[0]:
            best = (key, txt)
    return (best[0][0], best[1])

random.seed(7030)
for _ in range(200):
    w = random.randint(3, 12)
    words = ["x" * random.randint(1, min(w, 6)) for _ in range(random.randint(1, 9))]
    assert WM(words, w) == brute(words, w), (words, w)
words = ["w" * random.randint(1, 8) for _ in range(400)]
c, lines = WM(words, 20)
assert " ".join(lines).split(" ") == words and all(len(l) <= 20 for l in lines)
assert c == sum((20 - len(l)) ** 2 for l in lines[:-1])
''', r'''
def wrap_min_cost(words, width):
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise ValueError("width must be an int >= 1")
    if not isinstance(words, (list, tuple)):
        raise ValueError("words must be a list or tuple")
    for w in words:
        if not isinstance(w, str) or not w or len(w) > width or any(c.isspace() for c in w):
            raise ValueError("bad word")
    n = len(words)
    cost = [0] * (n + 1)
    nxt = [n] * (n + 1)
    for i in range(n - 1, -1, -1):
        best, best_j, length = None, None, -1
        for j in range(i + 1, n + 1):
            length += len(words[j - 1]) + 1
            if length > width:
                break
            c = (0 if j == n else (width - length) ** 2) + cost[j]
            if best is None or c <= best:
                best, best_j = c, j
        cost[i], nxt[i] = best, best_j
    lines, i = [], 0
    while i < n:
        lines.append(" ".join(words[i:nxt[i]]))
        i = nxt[i]
    return (cost[0], lines)
''')

TASKS = T
