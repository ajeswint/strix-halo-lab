"""loop-v9: fresh held-out Python tasks for the verified coding-memory loop v1 eval (docs/memory-loop-v1.md section 4,
docs/memory-eval-v9-protocol.md).

Same layout as tasks_v8.py (id, prompt, tests, ref) plus an explicit `family` and split="held_out" on every task.
Written 2026-11-07 inline in one session by the code-writer seat (Claude Code), CPU only. No evaluated model
(qwen3-32b, r1-distill-qwen-32b) has seen any prompt or answer here; the authors and reviewers have. The writer did
not consult a lesson export while writing. Novelty against v0-v8 is audited by bench/loop/novelty_audit.py
(docs/v9-novelty-audit.md); no claim is made about absence from any model's pretraining data.

Families (memring.KNOWN_FAMILIES): formats v9_01-08, number_theory v9_09-15, graphs_geometry v9_16-22,
simulation_dp v9_23-30. Every test file has exactly one random.seed(N) line, N = 9000 + task number. Seeded random
cases are checked against an oracle built differently from the ref (stdlib routine, brute force, a generator that
builds the expected answer, exact Fraction arithmetic, or properties).
Not in run.SETS: v9 is held out until the eval that spends it (then it moves to the train list).
"""

T = []


def task(id, family, prompt, tests, ref, split="held_out"):
    T.append({"id": id, "family": family, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip(),
              "split": split})


REJ = r'''
def rej(f, *x):
    try:
        f(*x)
    except ValueError:
        return True
    return False
'''

# --- formats ---

task("v9_01_perm_mode", "formats", r'''
Write two functions that convert Unix permission bits to and from the nine-character text that `ls -l` shows after
the file-type character: `mode_to_text(mode)` and `text_to_mode(text)`.

The mode is an int from 0 to 0o7777 (a bool is never accepted as an int; anything else raises ValueError). The low
nine bits are read, write and execute for owner (0o400, 0o200, 0o100), group (0o040, 0o020, 0o010) and others
(0o004, 0o002, 0o001). The three high bits are set-user-id 0o4000, set-group-id 0o2000 and sticky 0o1000.

mode_to_text(mode) returns three triples, owner then group then others. In each triple the first character is "r" or
"-", the second "w" or "-", and the third shows the execute bit as "x" or "-", with one exception: the special bit of
that triple (set-user-id for owner, set-group-id for group, sticky for others) replaces the third character. It is
written in lower case ("s" for the two id bits, "t" for sticky) when the triple's execute bit is also set, and in
upper case ("S" or "T") when it is not.

text_to_mode(text) is the exact inverse. `text` must be a str of exactly nine characters in which every position
holds one of the characters that mode_to_text could put there (so "t" is only legal in the last position and "s"
only in the third or sixth); otherwise raise ValueError. Return the int mode.

Examples:
- mode_to_text(0o755) == "rwxr-xr-x" and mode_to_text(0o4755) == "rwsr-xr-x"
- mode_to_text(0o1777) == "rwxrwxrwt" and mode_to_text(0o2640) == "rw-r-S---"
- mode_to_text(0o1000) == "--------T" and mode_to_text(0) == "---------"
- text_to_mode("rwsr-x---") == 0o4750 and text_to_mode("--------T") == 0o1000
- ValueError: mode_to_text(0o10000), mode_to_text(-1), mode_to_text(True), text_to_mode("rwtr-xr-x"),
  text_to_mode("rwxr-xr-s"), text_to_mode("rwxr-xr-"), text_to_mode("RWXr-xr-x")
''', REJ + r'''
import random, stat

M, X = mode_to_text, text_to_mode
assert M(0o755) == "rwxr-xr-x" and M(0o4755) == "rwsr-xr-x" and M(0o1777) == "rwxrwxrwt"
assert M(0o2640) == "rw-r-S---" and M(0o1000) == "--------T" and M(0) == "---------"
assert M(0o4000) == "--S------" and M(0o7777) == "rwsrwsrwt" and M(0o7000) == "--S--S--T"
assert X("rwsr-x---") == 0o4750 and X("--------T") == 0o1000 and X("rw-r-S---") == 0o2640
assert X("---------") == 0 and X("rwsrwsrwt") == 0o7777
for bad in (0o10000, -1, True, False, 1.0, "755", None, [0o755]):
    assert rej(M, bad), bad
for bad in ("rwtr-xr-x", "rwxr-xr-s", "rwxr-xr-", "RWXr-xr-x", "rwxr-xr-xx", " rwxr-xr-", "rwxrTxr-x", "",
            "xwxr-xr-x", "r-Sr-sr-S", 0o755, None, b"rwxr-xr-x"):
    assert rej(X, bad), bad
random.seed(9001)
ok = {stat.filemode(stat.S_IFREG | m)[1:]: m for m in range(0o10000)}
for _ in range(1500):
    m = random.randrange(0o10000)
    assert M(m) == stat.filemode(stat.S_IFREG | m)[1:], oct(m)
for s, m in random.sample(sorted(ok.items()), 800):
    assert X(s) == m, s
for _ in range(1500):
    s = "".join(random.choice("rwxsStT-") for _ in range(9))
    if s in ok:
        assert X(s) == ok[s], s
    else:
        assert rej(X, s), s
''', r'''
SPECIAL = ((0o4000, "s", "S"), (0o2000, "s", "S"), (0o1000, "t", "T"))


def mode_to_text(mode):
    if not isinstance(mode, int) or isinstance(mode, bool) or not 0 <= mode <= 0o7777:
        raise ValueError("mode must be an int from 0 to 0o7777")
    out = []
    for i, (bit, on, off) in enumerate(SPECIAL):
        b = (mode >> (6 - 3 * i)) & 7
        out.append("r" if b & 4 else "-")
        out.append("w" if b & 2 else "-")
        if mode & bit:
            out.append(on if b & 1 else off)
        else:
            out.append("x" if b & 1 else "-")
    return "".join(out)


def text_to_mode(text):
    if not isinstance(text, str) or len(text) != 9:
        raise ValueError("need a str of 9 characters")
    mode = 0
    for i, (bit, on, off) in enumerate(SPECIAL):
        r, w, x = text[3 * i:3 * i + 3]
        shift = 6 - 3 * i
        if r not in ("r", "-") or w not in ("w", "-") or x not in ("x", "-", on, off):
            raise ValueError("bad character in " + repr(text))
        mode |= (r == "r") << (shift + 2)
        mode |= (w == "w") << (shift + 1)
        if x in ("x", on):
            mode |= 1 << shift
        if x in (on, off):
            mode |= bit
    return mode
''')

task("v9_02_size_units", "formats", r'''
Write `format_size(n)` and `parse_size(text)` for byte counts written with binary (IEC) units. The units are
B (1), KiB (1024), MiB (1024**2), GiB (1024**3), TiB (1024**4) and PiB (1024**5). All arithmetic must be exact; a
float result that is off by one in the last digit is wrong.

format_size(n): `n` must be an int >= 0 (a bool is not an int), otherwise raise ValueError.
- If n < 1024, return f"{n} B".
- Otherwise pick the largest unit U from KiB to PiB with U <= n, divide, and round to one decimal place, rounding a
  value exactly halfway between two tenths upward. Return it with exactly one decimal digit and the unit, e.g.
  "1.5 KiB" or "2.0 MiB".
- If the rounded value is 1024.0 or more and a larger unit exists, use the next larger unit instead (it then reads
  "1.0"). Above PiB there is no larger unit, so values of 1024.0 PiB and more stay in PiB.

parse_size(text): `text` must be a str of the form "<number> <unit>" with exactly one space. The number is one or more
ASCII digits, optionally followed by "." and one or more ASCII digits. The unit is one of the six above, spelled
exactly (case matters). With unit B the number must have no "." part. Return the number times the unit, rounded to the
nearest int with an exact half rounded upward. Anything else raises ValueError (no sign, no leading or trailing space,
no ".5", no "1.", no exponent).

Examples:
- format_size(0) == "0 B" and format_size(1023) == "1023 B" and format_size(1024) == "1.0 KiB"
- format_size(1536) == "1.5 KiB" and format_size(1587) == "1.5 KiB" and format_size(1588) == "1.6 KiB"
- format_size(1048575) == "1.0 MiB" (1023.999... KiB rounds to 1024.0)
- format_size(1024 ** 6) == "1024.0 PiB"
- parse_size("1.5 KiB") == 1536 and parse_size("12 B") == 12 and parse_size("0.0005 KiB") == 1
- parse_size("0.0004 KiB") == 0 and parse_size("2 GiB") == 2147483648
- ValueError: parse_size("1.5 B"), parse_size("1.5KiB"), parse_size("1.5 kib"), parse_size("-1 B"),
  parse_size(".5 KiB"), parse_size("1. KiB"), format_size(-1), format_size(1.0)
''', REJ + r'''
import random
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 80
F, P = format_size, parse_size
UN = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]

def ofmt(n):
    if n < 1024:
        return f"{n} B"
    for k in range(5, 0, -1):
        if n >= 1024 ** k:
            break
    while True:
        v = (Decimal(n) / Decimal(1024 ** k)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if v >= 1024 and k < 5:
            k += 1
            continue
        return f"{v} {UN[k]}"

assert F(0) == "0 B" and F(1023) == "1023 B" and F(1024) == "1.0 KiB" and F(1536) == "1.5 KiB"
assert F(1587) == "1.5 KiB" and F(1588) == "1.6 KiB" and F(1048575) == "1.0 MiB" and F(1024 ** 6) == "1024.0 PiB"
assert F(1024 ** 5 * 1023 + 1024 ** 5 * 99 // 100) == "1024.0 PiB" and F(1126) == "1.1 KiB" and F(1127) == "1.1 KiB"
assert P("1.5 KiB") == 1536 and P("12 B") == 12 and P("0.0005 KiB") == 1 and P("0.0004 KiB") == 0
assert P("2 GiB") == 2147483648 and P("0 B") == 0 and P("007 B") == 7 and P("1.00 PiB") == 1024 ** 5
for bad in ("1.5 B", "1.5KiB", "1.5 kib", "-1 B", ".5 KiB", "1. KiB", "1e3 B", " 1 B", "1 B ", "1  B", "1 KB",
            "1 b", "", "KiB", "1,5 KiB", "+1 B", "1 B\n", "١ B", None, 5):
    assert rej(P, bad), bad
for bad in (-1, 1.0, True, "1024", None):
    assert rej(F, bad), bad
random.seed(9002)
for _ in range(1500):
    k = random.randrange(7)
    n = random.choice([random.randrange(1024 ** k + 1), 1024 ** k - random.randrange(3), 1024 ** k + random.randrange(3),
                       random.randrange(1024 ** max(k - 1, 0)) * 1024 + 512 * random.randrange(2)])
    n = max(n, 0)
    assert F(n) == ofmt(n), n
for _ in range(1500):
    k = random.randrange(6)
    if k == 0:
        s = str(random.randrange(10 ** random.randrange(1, 12)))
        want = int(s)
    else:
        whole = str(random.randrange(5000))
        frac = "".join(random.choice("0123456789") for _ in range(random.randrange(1, 12)))
        s = whole + "." + frac
        want = int((Decimal(s) * 1024 ** k).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    assert P(f"{s} {UN[k]}") == want, (s, UN[k])
''', r'''
UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]


def format_size(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be an int >= 0")
    if n < 1024:
        return f"{n} B"
    k = 1
    while k < 5 and 1024 ** (k + 1) <= n:
        k += 1
    while True:
        u = 1024 ** k
        tenths = (20 * n + u) // (2 * u)
        if tenths >= 10240 and k < 5:
            k += 1
            continue
        return f"{tenths // 10}.{tenths % 10} {UNITS[k]}"


def parse_size(text):
    if not isinstance(text, str) or text.count(" ") != 1:
        raise ValueError("need '<number> <unit>'")
    num, unit = text.split(" ")
    if unit not in UNITS:
        raise ValueError("unknown unit")
    whole, dot, frac = num.partition(".")
    digits = "0123456789"
    if not whole or any(c not in digits for c in whole + frac) or (dot and not frac):
        raise ValueError("bad number")
    if unit == "B" and dot:
        raise ValueError("bytes have no fraction")
    scale = 10 ** len(frac)
    value = int(whole + frac) * 1024 ** UNITS.index(unit)
    return (2 * value + scale) // (2 * scale)
''')

task("v9_03_tab_stops", "formats", r'''
Write `expand_tabs(line, width)` and `collapse_spaces(line, width)` for one line of text with tab stops every `width`
columns (columns are counted from 0, one per character, and the stops are at width, 2*width, 3*width, ...).

Both functions: `line` must be a str containing no "\n" and no "\r", and `width` an int from 1 to 32 (a bool is not
an int); otherwise raise ValueError.

expand_tabs(line, width): replace every tab by one or more spaces so that the next character starts at the next tab
stop strictly after the tab's column. A tab at column 5 with width 4 becomes three spaces (to column 8); a tab at
column 8 becomes four spaces (to column 12). Other characters are copied.

collapse_spaces(line, width): the reverse direction. `line` must also contain no tab (ValueError otherwise). Cut the
line into consecutive chunks of exactly `width` characters, from the left; the last chunk may be shorter. In every
chunk of full length that ends with a run of at least two spaces, replace that whole trailing run of spaces by one
tab. A full chunk that ends with exactly one space, or with no space, is copied unchanged, and so is the short last
chunk. So expand_tabs(collapse_spaces(s, w), w) == s for every legal s.

Examples (width 4 unless stated):
- expand_tabs("a\tb", 4) == "a   b" and expand_tabs("\t\tx", 2) == "    x" and expand_tabs("abcd\te", 4) == "abcd    e"
- collapse_spaces("ab  cd", 4) == "ab\tcd" and collapse_spaces("abc d", 4) == "abc d"
- collapse_spaces("        x", 4) == "\t\tx" and collapse_spaces("a       b", 4) == "a\t\tb"
- collapse_spaces("x   ", 4) == "x\t" and collapse_spaces("x  ", 4) == "x  " (short last chunk)
- ValueError: expand_tabs("a\nb", 4), expand_tabs("a", 0), expand_tabs("a", True), collapse_spaces("a\tb", 4)
''', REJ + r'''
import random

E, C = expand_tabs, collapse_spaces

def ocollapse(s, w):
    out = []
    for i in range(0, len(s), w):
        ch = s[i:i + w]
        body = ch.rstrip(" ")
        out.append(body + "\t" if len(ch) == w and len(ch) - len(body) >= 2 else ch)
    return "".join(out)

assert E("a\tb", 4) == "a   b" and E("\t\tx", 2) == "    x" and E("abcd\te", 4) == "abcd    e"
assert E("", 3) == "" and E("\t", 1) == " " and E("ab\t", 8) == "ab      "
assert C("ab  cd", 4) == "ab\tcd" and C("abc d", 4) == "abc d" and C("        x", 4) == "\t\tx"
assert C("a       b", 4) == "a\t\tb" and C("x   ", 4) == "x\t" and C("x  ", 4) == "x  " and C("", 5) == ""
assert C("  ", 2) == "\t" and C(" ", 1) == " " and C("a b   c", 3) == "a b\tc"
for bad in (("a\nb", 4), ("a", 0), ("a", True), ("a\rb", 2), ("a", 33), (b"a", 4), ("a", 4.0), (None, 4)):
    assert rej(E, *bad) and rej(C, *bad), bad
assert rej(C, "a\tb", 4)
random.seed(9003)
for _ in range(2500):
    w = random.randint(1, 9)
    s = "".join(random.choice("ab\t\t   ") for _ in range(random.randrange(30)))
    assert E(s, w) == s.expandtabs(w), (s, w)
    t = "".join(random.choice("ab    ") for _ in range(random.randrange(40)))
    got = C(t, w)
    assert got == ocollapse(t, w), (t, w)
    assert E(got, w) == t, (t, w)
''', r'''
def _check(line, width):
    if not isinstance(line, str) or "\n" in line or "\r" in line:
        raise ValueError("line must be a str without line breaks")
    if not isinstance(width, int) or isinstance(width, bool) or not 1 <= width <= 32:
        raise ValueError("width must be an int from 1 to 32")


def expand_tabs(line, width):
    _check(line, width)
    out, col = [], 0
    for c in line:
        if c == "\t":
            pad = width - col % width
            out.append(" " * pad)
            col += pad
        else:
            out.append(c)
            col += 1
    return "".join(out)


def collapse_spaces(line, width):
    _check(line, width)
    if "\t" in line:
        raise ValueError("line already contains a tab")
    out = []
    for start in range(0, len(line), width):
        chunk = line[start:start + width]
        n = 0
        while n < len(chunk) and chunk[len(chunk) - 1 - n] == " ":
            n += 1
        if len(chunk) == width and n >= 2:
            out.append(chunk[:width - n] + "\t")
        else:
            out.append(chunk)
    return "".join(out)
''')

task("v9_04_quoted_printable", "formats", r'''
Write `qp_encode(data)` and `qp_decode(text)` for a simplified quoted-printable encoding of arbitrary bytes.

qp_encode(data): `data` must be bytes or bytearray, otherwise raise ValueError. Each byte becomes one token:
- a byte from 33 to 126 other than 61 ("=") is written as that ASCII character;
- a space (32) is written as a space, except when it is the very last byte of `data`;
- every other byte (including "=", tab, CR, LF, a final space and bytes >= 127) is written as "=" plus two upper-case
  hex digits, e.g. "=3D" for "=", "=0A" for LF.
The tokens are then laid out greedily into lines joined by soft breaks. A soft break is "=" followed by "\r\n" and is
not part of the data. Going through the tokens in order: a token is appended to the current line if the line then
has at most 75 characters, or at most 76 characters when it is the last token of the whole output; otherwise the
current line is ended with a soft break and the token starts a new line. A token is never split. Empty data gives "".

qp_decode(text): `text` must be a str, otherwise raise ValueError. Remove every soft break ("=\r\n"). Every other "="
must be followed by exactly two hex digits (upper or lower case), which give one byte. Every other character must be a
printable ASCII character from 32 to 126 (never "="), and stands for its own byte. Anything else raises ValueError: a
"=" with fewer than two hex digits after it, a "\r" or "\n" not inside a soft break, a non-ASCII character. qp_decode
does not check line lengths. Return bytes.

Examples:
- qp_encode(b"caf\xc3\xa9 ok ") == "caf=C3=A9 ok=20"
- qp_encode(b"a=b\n") == "a=3Db=0A" and qp_encode(b"") == ""
- qp_encode(b"x" * 80) == "x" * 75 + "=\r\n" + "xxxxx" and qp_encode(b"x" * 76) == "x" * 76
- qp_decode("caf=c3=a9") == b"caf\xc3\xa9" and qp_decode("ab=\r\ncd") == b"abcd"
- ValueError: qp_decode("a=4"), qp_decode("a=G0"), qp_decode("a\nb"), qp_decode("a="), qp_decode("é"),
  qp_encode("text")
''', REJ + r'''
import random, re

E, D = qp_encode, qp_decode

def oenc(data):
    toks = []
    for i, b in enumerate(data):
        if (33 <= b <= 126 and b != 61) or (b == 32 and i < len(data) - 1):
            toks.append(chr(b))
        else:
            toks.append("=%02X" % b)
    lines, cur = [], ""
    for i, t in enumerate(toks):
        cap = 76 if i == len(toks) - 1 else 75
        if len(cur) + len(t) > cap:
            lines.append(cur)
            cur = ""
        cur += t
    lines.append(cur)
    return "=\r\n".join(lines) if data else ""

assert E(b"caf\xc3\xa9 ok ") == "caf=C3=A9 ok=20" and E(b"a=b\n") == "a=3Db=0A" and E(b"") == ""
assert E(b"x" * 80) == "x" * 75 + "=\r\n" + "xxxxx" and E(b"x" * 76) == "x" * 76 and E(b" ") == "=20"
assert E(b"x" * 74 + b"\xff") == "x" * 74 + "=\r\n=FF" and E(b"x" * 73 + b"\xff") == "x" * 73 + "=FF"
assert E(bytearray(b"  ")) == " =20" and E(b"\t") == "=09"
assert D("caf=c3=a9") == b"caf\xc3\xa9" and D("ab=\r\ncd") == b"abcd" and D("") == b"" and D("=\r\n") == b""
assert D(" =20 ") == b"  " + b" " and D("=3d=3D") == b"=="
for bad in ("a=4", "a=G0", "a\nb", "a=", "é", "a\rb", "=\n", "=\r", "a\tb", "=0g", "\x7f", b"ab", None):
    assert rej(D, bad), bad
for bad in ("text", None, [1, 2], 5):
    assert rej(E, bad), bad
random.seed(9004)
for _ in range(1200):
    n = random.choice([random.randrange(6), random.randrange(200)])
    data = bytes(random.choice([random.randrange(256), random.randrange(32, 127), 32, 61]) for _ in range(n))
    got = E(data)
    assert got == oenc(data), data
    assert D(got) == data, data
    assert all(len(l) <= 76 for l in got.split("\r\n")), got
    if random.random() < 0.5:
        mixed = re.sub(r"=[0-9A-F]{2}", lambda m: m.group().lower() if random.random() < 0.5 else m.group(), got)
        assert D(mixed) == data, mixed
''', r'''
def qp_encode(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    toks = []
    last = len(data) - 1
    for i, b in enumerate(data):
        if 33 <= b <= 126 and b != 61 or b == 32 and i != last:
            toks.append(chr(b))
        else:
            toks.append("=" + format(b, "02X"))
    out, line = [], 0
    for i, t in enumerate(toks):
        limit = 76 if i == last else 75
        if line + len(t) > limit:
            out.append("=\r\n")
            line = 0
        out.append(t)
        line += len(t)
    return "".join(out)


def qp_decode(text):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    hexd = "0123456789abcdefABCDEF"
    out, i = bytearray(), 0
    while i < len(text):
        c = text[i]
        if c == "=":
            if text[i + 1:i + 3] == "\r\n":
                i += 3
                continue
            h = text[i + 1:i + 3]
            if len(h) != 2 or h[0] not in hexd or h[1] not in hexd:
                raise ValueError("bad escape at %d" % i)
            out.append(int(h, 16))
            i += 3
        elif 32 <= ord(c) <= 126:
            out.append(ord(c))
            i += 1
        else:
            raise ValueError("illegal character at %d" % i)
    return bytes(out)
''')

task("v9_05_header_params", "formats", r'''
Write `parse_params(value)` and `format_params(mediatype, params)` for media-type header values such as
`text/html; charset="utf-8"`.

Definitions. A token is one or more characters from: ASCII letters, digits, and !#$%&'*+-.^_`|~ . A quoted string
is a double quote, then any characters where a backslash escapes the next character (so \" is a quote and \\ a
backslash), then a closing double quote. Optional whitespace (OWS) is any run of spaces and tabs, possibly empty.

parse_params(value): `value` must be a str of this form, otherwise raise ValueError:
OWS, token "/" token, then zero or more of (OWS ";" OWS name "=" val), then OWS. A name is a token; a val is a token or
a quoted string. There is no whitespace around "/" or "=". No empty parameter, so "a/b;" and "a/b;;c=d" are invalid.
A backslash may not be the last character inside a quoted string, and a quoted string may not contain a raw tab, CR,
LF or other control character (code < 32 or 127), even escaped. Names are case-insensitive: a repeated name in any
case is a ValueError. Return a tuple (mediatype, params): the mediatype lower-cased, and a dict from lower-cased name to
the value with quotes and escapes removed (values keep their case).

format_params(mediatype, params): `mediatype` must be a str of the form token "/" token, `params` a dict whose keys are
tokens and whose values are str without control characters (code < 32 or 127); otherwise ValueError. Keys that are
equal ignoring case are a ValueError. Return the mediatype lower-cased, then for every parameter sorted by lower-cased
name: "; " + lower-cased name + "=" + the value written as a bare token if it is a non-empty token, else as a quoted
string with every " and \ escaped by a backslash and nothing else escaped.

Examples:
- parse_params('Text/HTML; Charset="utf-8"') == ("text/html", {"charset": "utf-8"})
- parse_params('multipart/form-data;boundary="a b\\"c"') == ("multipart/form-data", {"boundary": 'a b"c'})
- parse_params(" a/b ") == ("a/b", {}) and parse_params("a/b ;\tx=Y") == ("a/b", {"x": "Y"})
- format_params("text/plain", {"q": "a b", "charset": "utf-8"}) == 'text/plain; charset=utf-8; q="a b"'
- format_params("a/b", {"x": ""}) == 'a/b; x=""'
- ValueError: parse_params("a/b;"), parse_params("a /b"), parse_params("a/b; x = 1"), parse_params("a/b; x=1; X=2"),
  parse_params('a/b; x="unterminated'), format_params("a/b", {"x": "1", "X": "2"})
''', REJ + r'''
import random

P, F = parse_params, format_params
TOK = "abcXYZ019!#$%&'*+-.^_`|~"

assert P('Text/HTML; Charset="utf-8"') == ("text/html", {"charset": "utf-8"})
assert P('multipart/form-data;boundary="a b\\"c"') == ("multipart/form-data", {"boundary": 'a b"c'})
assert P(" a/b ") == ("a/b", {}) and P("a/b ;\tx=Y") == ("a/b", {"x": "Y"}) and P('a/b;x=""') == ("a/b", {"x": ""})
assert P('a/b; x="\\\\"') == ("a/b", {"x": "\\"}) and P('a/b; x="a;b=c"') == ("a/b", {"x": "a;b=c"})
assert F("text/plain", {"q": "a b", "charset": "utf-8"}) == 'text/plain; charset=utf-8; q="a b"'
assert F("a/b", {"x": ""}) == 'a/b; x=""' and F("A/B", {}) == "a/b" and F("a/b", {"N": 'x"\\'}) == 'a/b; n="x\\"\\\\"'
assert F("a/b", {"z": "1", "Y": "é"}) == 'a/b; y="é"; z=1'
for bad in ("a/b;", "a /b", "a/b; x = 1", "a/b; x=1; X=2", 'a/b; x="unterminated', "a/b;;c=d", "a", "/b", "a/",
            "a/b/c", "a/b; x", "a/b; =1", 'a/b; x="a\\"', 'a/b; x="a\tb"', 'a/b; x="a\\\nb"', "a/b x=1",
            'a/b; x="1"y', "a/b; x=1 2", "a b/c", "é/b", None, b"a/b"):
    assert rej(P, bad), bad
for bad in (("a/b", {"x": "1", "X": "2"}), ("ab", {}), ("a/b", {"x y": "1"}), ("a/b", {"x": "a\nb"}),
            ("a/b", {"x": 1}), ("a/b", [("x", "1")]), ("a/b", {"": "1"}), (None, {}), ("a/b", {"x": "\x7f"})):
    assert rej(F, *bad), bad
random.seed(9005)
def rtok():
    return "".join(random.choice(TOK) for _ in range(random.randint(1, 6)))
def ows():
    return "".join(random.choice(" \t") for _ in range(random.choice([0, 0, 1, 2])))
for _ in range(1500):
    mt = rtok() + "/" + rtok()
    want, text = {}, ows() + mt
    for _ in range(random.randrange(5)):
        name = rtok()
        if name.lower() in want:
            continue
        v = "".join(random.choice('ab "\\;=,é') for _ in range(random.randrange(6)))
        istok = v and all(c in TOK for c in v)
        if istok and random.random() < 0.5:
            sv = v
        else:
            sv = '"' + "".join("\\" + c if c in '"\\' or random.random() < 0.1 else c for c in v) + '"'
        want[name.lower()] = v
        text += ows() + ";" + ows() + name + "=" + sv
    text += ows()
    assert P(text) == (mt.lower(), want), text
    f = F(mt, want)
    assert P(f) == (mt.lower(), want), f
    assert list(P(f)[1]) == sorted(want) and f.startswith(mt.lower() + ("; " if want else "")), f
''', r'''
TOKEN = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-.^_`|~")


def _is_token(s):
    return bool(s) and all(c in TOKEN for c in s)


def _ctl(c):
    return ord(c) < 32 or ord(c) == 127


def parse_params(value):
    if not isinstance(value, str):
        raise ValueError("value must be a str")
    s, n, i = value, len(value), 0

    def ows(i):
        while i < n and s[i] in " \t":
            i += 1
        return i

    def token(i):
        j = i
        while j < n and s[j] in TOKEN:
            j += 1
        if j == i:
            raise ValueError("token expected at %d" % i)
        return s[i:j], j

    i = ows(i)
    a, i = token(i)
    if i >= n or s[i] != "/":
        raise ValueError("'/' expected")
    b, i = token(i + 1)
    params = {}
    while True:
        j = ows(i)
        if j == n:
            break
        if s[j] != ";":
            raise ValueError("';' expected at %d" % j)
        name, i = token(ows(j + 1))
        if i >= n or s[i] != "=":
            raise ValueError("'=' expected")
        i += 1
        if i < n and s[i] == '"':
            out, i = [], i + 1
            while True:
                if i >= n:
                    raise ValueError("unterminated quoted string")
                c = s[i]
                if c == "\\":
                    if i + 1 >= n:
                        raise ValueError("dangling backslash")
                    c, i = s[i + 1], i + 1
                elif c == '"':
                    break
                if _ctl(c):
                    raise ValueError("control character")
                out.append(c)
                i += 1
            val, i = "".join(out), i + 1
        else:
            val, i = token(i)
        if name.lower() in params:
            raise ValueError("repeated parameter " + name)
        params[name.lower()] = val
    return (a + "/" + b).lower(), params


def format_params(mediatype, params):
    if not isinstance(mediatype, str) or mediatype.count("/") != 1:
        raise ValueError("bad mediatype")
    a, b = mediatype.split("/")
    if not (_is_token(a) and _is_token(b)) or not isinstance(params, dict):
        raise ValueError("bad mediatype or params")
    low = {}
    for k, v in params.items():
        if not isinstance(k, str) or not _is_token(k) or not isinstance(v, str) or any(_ctl(c) for c in v):
            raise ValueError("bad parameter")
        if k.lower() in low:
            raise ValueError("repeated parameter")
        low[k.lower()] = v
    out = [mediatype.lower()]
    for k in sorted(low):
        v = low[k]
        if not _is_token(v):
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        out.append(k + "=" + v)
    return "; ".join(out)
''')

task("v9_06_flatten_keys", "formats", r'''
Write `flatten(tree)` and `unflatten(flat)` that convert between nested dicts and flat dicts with dotted keys, as used
for configuration files.

A tree is a dict. Each key must be a non-empty str that contains no "."; each value is either a tree (a dict, which may
be empty) or a leaf (any value that is not a dict). Any other key raises ValueError, at any depth.

flatten(tree): `tree` must be a dict, otherwise ValueError. Return a dict that maps the path of every leaf (the keys
from the root joined by ".") to the leaf, and the path of every EMPTY nested dict to a new empty dict {}. An empty
tree gives {}. Do not modify the input.

unflatten(flat): `flat` must be a dict whose keys are str made of one or more non-empty segments joined by "." (no
leading, trailing or doubled "."), and whose values are leaves or empty dicts; a non-empty dict as a value is a
ValueError. Rebuild the tree. A path that would have to be both a leaf (or an empty dict) and a parent of another
path, such as {"a": 1, "a.b": 2} or {"a": {}, "a.b": 2}, raises ValueError, whatever order the keys come in. Each
empty-dict value becomes its own new empty dict in the result. Do not modify the input.

For every legal tree t, unflatten(flatten(t)) == t, and for every legal flat dict f, flatten(unflatten(f)) == f.

Examples:
- flatten({"db": {"host": "x", "port": 5432}, "debug": False}) == {"db.host": "x", "db.port": 5432, "debug": False}
- flatten({"a": {"b": {}}, "c": [1, {"d": 2}]}) == {"a.b": {}, "c": [1, {"d": 2}]} (lists are leaves)
- flatten({}) == {} and unflatten({}) == {}
- unflatten({"x.y.z": 1, "x.w": None}) == {"x": {"y": {"z": 1}, "w": None}}
- ValueError: flatten({"a.b": 1}), flatten({"": 1}), flatten({1: 2}), flatten({"a": {"b.c": 1}}),
  unflatten({"a": 1, "a.b": 2}), unflatten({"a..b": 1}), unflatten({".a": 1}), unflatten({"a": {"b": 1}})
''', REJ + r'''
import copy, random

FL, UN = flatten, unflatten

assert FL({"db": {"host": "x", "port": 5432}, "debug": False}) == {"db.host": "x", "db.port": 5432, "debug": False}
assert FL({"a": {"b": {}}, "c": [1, {"d": 2}]}) == {"a.b": {}, "c": [1, {"d": 2}]}
assert FL({}) == {} and UN({}) == {} and FL({"a": {}}) == {"a": {}} and UN({"a": {}}) == {"a": {}}
assert UN({"x.y.z": 1, "x.w": None}) == {"x": {"y": {"z": 1}, "w": None}}
e = {}
r = UN({"p": e, "q": e})
assert r == {"p": {}, "q": {}} and r["p"] is not e and r["p"] is not r["q"]
src = {"p": {}}
r = FL(src)
r["p"]["z"] = 1
assert src == {"p": {}}
for bad in ({"a.b": 1}, {"": 1}, {1: 2}, {"a": {"b.c": 1}}, {"a": {"": {}}}, {"a": {2: 1}}, [("a", 1)], None):
    assert rej(FL, bad), bad
for bad in ({"a": 1, "a.b": 2}, {"a.b": 2, "a": 1}, {"a..b": 1}, {".a": 1}, {"a.": 1}, {"a": {"b": 1}},
            {"a": {}, "a.b": 2}, {"a.b.c": 1, "a.b": {}}, {"": 1}, {1: 1}, [("a", 1)], None):
    assert rej(UN, bad), bad
random.seed(9006)
def rtree(d):
    t = {}
    for _ in range(random.randrange(4 if d < 3 else 1)):
        k = random.choice(["a", "b", "cc", "d_1", "Ée", "x y"])
        t[k] = rtree(d + 1) if random.random() < 0.45 else random.choice([0, "s", None, [1, {"k": 2}], (3,), 2.5, True])
    return t
def oflat(t, pre, out):
    for k, v in t.items():
        p = pre + "." + k if pre else k
        if isinstance(v, dict) and v:
            oflat(v, p, out)
        else:
            out[p] = {} if isinstance(v, dict) else v
    return out
for _ in range(1500):
    t = rtree(0)
    keep = copy.deepcopy(t)
    f = FL(t)
    assert t == keep
    assert f == oflat(t, "", {}), t
    g = copy.deepcopy(f)
    assert UN(f) == t and f == g, t
    if f:
        k = random.choice(sorted(f))
        clash = dict(f)
        clash[k + ".zz"] = 1
        items = list(clash.items())
        random.shuffle(items)
        assert rej(UN, dict(items)), clash
''', r'''
def _key_ok(k):
    return isinstance(k, str) and k != "" and "." not in k


def flatten(tree):
    if not isinstance(tree, dict):
        raise ValueError("tree must be a dict")
    out = {}

    def walk(node, prefix):
        for k, v in node.items():
            if not _key_ok(k):
                raise ValueError("bad key %r" % (k,))
            path = prefix + k
            if isinstance(v, dict):
                if v:
                    walk(v, path + ".")
                else:
                    out[path] = {}
            else:
                out[path] = v

    walk(tree, "")
    return out


def unflatten(flat):
    if not isinstance(flat, dict):
        raise ValueError("flat must be a dict")
    for k, v in flat.items():
        if not isinstance(k, str) or not all(_key_ok(p) for p in k.split(".")):
            raise ValueError("bad path %r" % (k,))
        if isinstance(v, dict) and v:
            raise ValueError("a non-empty dict is not a leaf")
    for k in flat:
        parts = k.split(".")
        for i in range(1, len(parts)):
            if ".".join(parts[:i]) in flat:
                raise ValueError("path conflict at " + k)
    root = {}
    for k, v in flat.items():
        parts = k.split(".")
        node = root
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = {} if isinstance(v, dict) else v
    return root
''')

task("v9_07_page_ranges", "formats", r'''
Write `parse_pages(text, last)` and `format_pages(pages)` for page selections like the ones a print dialog accepts.

parse_pages(text, last): `last` is the number of pages in the document, an int >= 1 (a bool is not an int). `text`
is a str made of one or more items separated by ","; spaces (only the space character) are allowed before and after
each item and nowhere else. An item is one of:
- "N": the single page N;
- "N-M": pages N to M inclusive, where N <= M;
- "N-": pages N to `last`;
- "-M": pages 1 to M.
Every number is written in ASCII digits without a sign or a leading zero, and must be from 1 to `last`. Items may
overlap and come in any order. Return the sorted list of distinct selected pages. Anything else raises ValueError,
including an empty item ("1,,2" or a trailing ","), a lone "-", "3-1", "0", "07", "1-2-3", "1 - 2" and a page after
`last`.

format_pages(pages): `pages` must be a list, tuple or set of ints >= 1 (no bools), otherwise ValueError. Duplicates
are ignored. Sort the distinct pages and split them into maximal runs of consecutive numbers. A run of one page is
written "N", a run of two pages is written "N,N+1", and a run of three or more is written "N-M". Join everything with
"," (no spaces). An empty selection gives "". format_pages never writes the open forms "N-" or "-M".

Examples:
- parse_pages("1-3,5", 10) == [1, 2, 3, 5] and parse_pages(" 8- , -2 ", 9) == [1, 2, 8, 9]
- parse_pages("4,2-4,3", 4) == [2, 3, 4] and parse_pages("1-", 1) == [1]
- format_pages([5, 1, 2, 3, 3, 9, 10]) == "1-3,5,9,10" and format_pages(set()) == ""
- ValueError: parse_pages("3-1", 5), parse_pages("0", 5), parse_pages("6", 5), parse_pages("1,", 5),
  parse_pages("-", 5), parse_pages("1 - 2", 5), format_pages([0]), format_pages([True])
''', REJ + r'''
import itertools, random

P, F = parse_pages, format_pages
assert P("1-3,5", 10) == [1, 2, 3, 5] and P(" 8- , -2 ", 9) == [1, 2, 8, 9] and P("4,2-4,3", 4) == [2, 3, 4]
assert P("1-", 1) == [1] and P("-1", 1) == [1] and P("2-2", 3) == [2] and P("  3  ", 3) == [3]
assert F([5, 1, 2, 3, 3, 9, 10]) == "1-3,5,9,10" and F(set()) == "" and F((7,)) == "7" and F([4, 5, 6]) == "4-6"
for bad in (("3-1", 5), ("0", 5), ("6", 5), ("1,", 5), ("-", 5), ("1 - 2", 5), ("", 5), (" ", 5), ("1,,2", 5),
            ("07", 9), ("1-2-3", 5), ("+1", 5), ("1\t", 5), ("1", 0), ("1", True), (1, 5), ("a", 5), ("1-06", 9),
            ("２", 5), ("-0", 5), ("5-", 4)):
    assert rej(P, *bad), bad
for bad in ([0], [True], [1.0], "12", None, [1, -2], {"a": 1}):
    assert rej(F, bad), bad
random.seed(9007)
for _ in range(1500):
    last = random.randint(1, 40)
    want, items = set(), []
    for _ in range(random.randint(1, 5)):
        a, b = sorted(random.randint(1, last) for _ in range(2))
        kind = random.randrange(4)
        if kind == 0:
            items.append(str(a)); want.add(a)
        elif kind == 1:
            items.append(f"{a}-{b}"); want.update(range(a, b + 1))
        elif kind == 2:
            items.append(f"{a}-"); want.update(range(a, last + 1))
        else:
            items.append(f"-{b}"); want.update(range(1, b + 1))
    text = ",".join(" " * random.randrange(2) + it + " " * random.randrange(2) for it in items)
    assert P(text, last) == sorted(want), (text, last)
    pages = [random.randint(1, 30) for _ in range(random.randrange(12))]
    parts = []
    for _, g in itertools.groupby(enumerate(sorted(set(pages))), lambda iv: iv[1] - iv[0]):
        run = [v for _, v in g]
        parts += [f"{run[0]}-{run[-1]}"] if len(run) >= 3 else [str(v) for v in run]
    assert F(pages) == ",".join(parts), pages
''', r'''
def parse_pages(text, last):
    if not isinstance(last, int) or isinstance(last, bool) or last < 1 or not isinstance(text, str):
        raise ValueError("bad arguments")

    def num(s):
        if not s or any(c not in "0123456789" for c in s) or s[0] == "0" or int(s) > last:
            raise ValueError("bad page number %r" % s)
        return int(s)

    pages = set()
    for raw in text.split(","):
        item = raw.strip(" ")
        if not item or " " in item:
            raise ValueError("bad item %r" % raw)
        if item.count("-") > 1:
            raise ValueError("bad range %r" % item)
        if "-" in item:
            a, b = item.split("-")
            if not a and not b:
                raise ValueError("lone '-'")
            lo = num(a) if a else 1
            hi = num(b) if b else last
            if lo > hi:
                raise ValueError("descending range")
        else:
            lo = hi = num(item)
        pages.update(range(lo, hi + 1))
    return sorted(pages)


def format_pages(pages):
    if not isinstance(pages, (list, tuple, set)):
        raise ValueError("pages must be a list, tuple or set")
    for p in pages:
        if not isinstance(p, int) or isinstance(p, bool) or p < 1:
            raise ValueError("bad page")
    ps, out, i = sorted(set(pages)), [], 0
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[j] + 1:
            j += 1
        if j - i >= 2:
            out.append(f"{ps[i]}-{ps[j]}")
        else:
            out.extend(str(p) for p in ps[i:j + 1])
        i = j + 1
    return ",".join(out)
''')

task("v9_08_outline_numbers", "formats", r'''
Write `number_headings(lines)` and `parse_numbered(lines)` that convert between Markdown-style headings and a numbered
outline.

A heading line is 1 to 6 "#" characters, one space, and a title. A title is a non-empty str that does not start or
end with whitespace and contains no "\n". A numbered line is a number, one space and a title, where the number is one
or more positive ints without leading zeros joined by "." (for example "2", "1.3", "4.1.2").

number_headings(lines): `lines` must be a list of heading lines (a str that is not a heading line is a ValueError).
The first heading must have level 1 (one "#"), and no heading may be more than one level deeper than the heading just
before it; it may be any number of levels shallower. Number them like a book outline: the level-L heading gets L
numbers; the first L-1 are copied from the most recent heading of each shallower level, and the last counts the
level-L headings since the most recent heading of level L-1 (or from the start, for L = 1). Return the list of
numbered lines.

parse_numbered(lines): `lines` must be a list of numbered lines whose numbers are exactly the numbers
number_headings would produce for some list of headings, in order (so the first is "1", and each next number either
appends ".1", or increments the last component, or drops one or more trailing components and then increments the new
last one). Otherwise raise ValueError. Return the heading lines: a number with L components gives L "#" characters.
A number with more than 6 components is invalid.

Examples:
- number_headings(["# Intro", "## Scope", "## Terms", "# Body", "## Part", "### Detail", "# End"]) ==
  ["1 Intro", "1.1 Scope", "1.2 Terms", "2 Body", "2.1 Part", "2.1.1 Detail", "3 End"]
- number_headings([]) == [] and parse_numbered([]) == []
- parse_numbered(["1 A", "1.1 B", "2 C"]) == ["# A", "## B", "# C"]
- ValueError: number_headings(["## A"]), number_headings(["# A", "### B"]), number_headings(["#A"]),
  number_headings(["# "]), number_headings(["####### A"]), parse_numbered(["2 A"]), parse_numbered(["1 A", "1.2 B"]),
  parse_numbered(["1 A", "3 B"]), parse_numbered(["1 A", "01.1 B"]), parse_numbered(["1  A"])
''', REJ + r'''
import random

N, P = number_headings, parse_numbered
H = ["# Intro", "## Scope", "## Terms", "# Body", "## Part", "### Detail", "# End"]
assert N(H) == ["1 Intro", "1.1 Scope", "1.2 Terms", "2 Body", "2.1 Part", "2.1.1 Detail", "3 End"]
assert N([]) == [] and P([]) == [] and P(["1 A", "1.1 B", "2 C"]) == ["# A", "## B", "# C"]
assert P(N(H)) == H and N(["# a b", "## c#"]) == ["1 a b", "1.1 c#"]
assert N(["# a", "## b", "### c", "#### d", "# e", "## f"]) == ["1 a", "1.1 b", "1.1.1 c", "1.1.1.1 d", "2 e", "2.1 f"]
for bad in (["## A"], ["# A", "### B"], ["#A"], ["# "], ["####### A"], ["# A "], [" # A"], ["# A\nB"], "# A",
            None, [1], ["#\tA"], ["# \tA"]):
    assert rej(N, bad), bad
for bad in (["2 A"], ["1 A", "1.2 B"], ["1 A", "3 B"], ["1 A", "01.1 B"], ["1  A"], ["1.1 A"], ["0 A"],
            ["1 A", "1.1 B", "1.1.1 C", "1.3 D"], ["1. A"], ["1 A", "1..1 B"], ["1A"], ["1 "],
            ["1 a", "1.1 b", "1.1.1 c", "1.1.1.1 d", "1.1.1.1.1 e", "1.1.1.1.1.1 f", "1.1.1.1.1.1.1 g"], "1 A", None):
    assert rej(P, bad), bad
random.seed(9008)
for _ in range(800):
    heads, nums, stack = [], [], []
    for _ in range(random.randrange(25)):
        lvl = random.randint(1, min(6, len(stack) + 1))
        if lvl > len(stack):
            stack.append(1)
        else:
            del stack[lvl:]
            stack[-1] += 1
        title = random.choice(["A", "b c", "x#y", "Ω", "1.2", "z"])
        heads.append("#" * lvl + " " + title)
        nums.append(".".join(map(str, stack)) + " " + title)
    assert N(heads) == nums, heads
    assert P(nums) == heads, nums
    if nums:
        i = random.randrange(len(nums))
        num, _, title = nums[i].partition(" ")
        parts = [int(x) for x in num.split(".")]
        parts[-1] += random.choice([1, 2])
        assert rej(P, nums[:i] + [".".join(map(str, parts)) + " " + title] + nums[i + 1:]), (nums, i)
''', r'''
def _title_ok(t):
    return t != "" and t == t.strip() and "\n" not in t


def number_headings(lines):
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")
    out, stack = [], []
    for ln in lines:
        if not isinstance(ln, str):
            raise ValueError("not a str")
        hashes, sep, title = ln.partition(" ")
        lvl = len(hashes)
        if not sep or not 1 <= lvl <= 6 or hashes != "#" * lvl or not _title_ok(title):
            raise ValueError("bad heading %r" % ln)
        if lvl > len(stack) + 1:
            raise ValueError("heading jumps a level: %r" % ln)
        if lvl == len(stack) + 1:
            stack.append(1)
        else:
            del stack[lvl:]
            stack[-1] += 1
        out.append(".".join(map(str, stack)) + " " + title)
    return out


def parse_numbered(lines):
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")
    out, stack = [], []
    for ln in lines:
        if not isinstance(ln, str):
            raise ValueError("not a str")
        num, sep, title = ln.partition(" ")
        parts = num.split(".")
        if not sep or not _title_ok(title) or len(parts) > 6:
            raise ValueError("bad line %r" % ln)
        for p in parts:
            if not p or any(c not in "0123456789" for c in p) or p[0] == "0":
                raise ValueError("bad number %r" % ln)
        parts = [int(p) for p in parts]
        lvl = len(parts)
        if lvl > len(stack) + 1:
            raise ValueError("level jump %r" % ln)
        want = stack[:lvl - 1] + ([1] if lvl == len(stack) + 1 else [stack[lvl - 1] + 1])
        if parts != want:
            raise ValueError("unexpected number %r" % ln)
        stack = parts
        out.append("#" * lvl + " " + title)
    return out
''')

# --- number_theory ---

task("v9_09_zeckendorf", "number_theory", r'''
Every positive integer is a sum of distinct Fibonacci numbers from 1, 2, 3, 5, 8, 13, ... (each next one is the sum of
the two before it) in which no two consecutive Fibonacci numbers are both used, and that sum is unique (Zeckendorf's
theorem). Write three functions around it.

zeckendorf(n): `n` must be an int from 0 to 10**30 (a bool is not an int), otherwise raise ValueError. Return the
Fibonacci numbers of n's representation as a list, largest first. zeckendorf(0) == [].

fib_code(n): `n` must be an int from 1 to 10**30, otherwise ValueError. Return n's Fibonacci code as a str of "0" and
"1": character i (counting from 0 at the left) is "1" exactly when the (i+1)-th number of the list 1, 2, 3, 5, 8, ...
is used, the string stops at the largest one used, and one extra "1" is appended. Because the representation never
uses two consecutive numbers, "11" first appears at the very end of every code.

fib_decode(bits): `bits` must be a str containing only "0" and "1", otherwise ValueError. It is a concatenation of
zero or more Fibonacci codes. Read it from the left: each code ends at the first "11" that starts inside it, and the
next code starts right after that. Return the list of decoded ints. If bits remain after the last complete code,
raise ValueError. fib_decode("") == [].

Examples:
- zeckendorf(100) == [89, 8, 3] and zeckendorf(1) == [1] and zeckendorf(4) == [3, 1]
- fib_code(1) == "11" and fib_code(2) == "011" and fib_code(4) == "1011" and fib_code(11) == "001011"
- fib_decode("11011") == [1, 2] and fib_decode("0011" + "1011") == [3, 4]
- ValueError: zeckendorf(-1), zeckendorf(10**30 + 1), zeckendorf(True), fib_code(0), fib_decode("0110"),
  fib_decode("111"), fib_decode("12")
''', REJ + r'''
import random

Z, C, D = zeckendorf, fib_code, fib_decode
FS = [1, 2]
while len(FS) < 160:
    FS.append(FS[-1] + FS[-2])
assert Z(100) == [89, 8, 3] and Z(1) == [1] and Z(4) == [3, 1] and Z(0) == [] and Z(2) == [2] and Z(12) == [8, 3, 1]
assert C(1) == "11" and C(2) == "011" and C(4) == "1011" and C(11) == "001011" and C(3) == "0011" and C(12) == "101011"
assert D("11011") == [1, 2] and D("0011" + "1011") == [3, 4] and D("") == [] and D("1111") == [1, 1]
assert sum(Z(10 ** 30)) == 10 ** 30 and D(C(10 ** 30)) == [10 ** 30]
for bad in (-1, 10 ** 30 + 1, True, 1.0, "5", None):
    assert rej(Z, bad), bad
for bad in (0, -3, 10 ** 30 + 1, False, 2.0, None):
    assert rej(C, bad), bad
for bad in ("0110", "111", "12", "0", "1", "11 ", "1101", None, 11, ["1", "1"], "１１"):
    assert rej(D, bad), bad
random.seed(9009)
seq, text = [], ""
for _ in range(800):
    idx, i = set(), random.randrange(3)
    top = random.choice([12, 40, 140])
    while i <= top:
        if random.random() < 0.4:
            idx.add(i)
            i += 2
        else:
            i += 1
    n = sum(FS[i] for i in idx)
    if n == 0 or n > 10 ** 30:
        continue
    assert Z(n) == [FS[i] for i in sorted(idx, reverse=True)], n
    code = "".join("1" if i in idx else "0" for i in range(max(idx) + 1)) + "1"
    assert C(n) == code, n
    seq.append(n)
    text += code
assert D(text) == seq
for _ in range(300):
    s = "".join(random.choice("01") for _ in range(random.randrange(30)))
    try:
        got = D(s)
    except ValueError:
        got = None
    want, cur, out = [], "", s
    while out:
        k = out.find("11")
        if k < 0:
            want = None
            break
        want.append(out[:k + 2])
        out = out[k + 2:]
    assert got == (None if want is None else [sum(FS[i] for i, b in enumerate(w[:-1]) if b == "1") for w in want]), s
''', r'''
LIMIT = 10 ** 30


def _fibs(n):
    fs = [1, 2]
    while fs[-1] <= n:
        fs.append(fs[-1] + fs[-2])
    return fs


def _check(n, lo):
    if not isinstance(n, int) or isinstance(n, bool) or not lo <= n <= LIMIT:
        raise ValueError("n out of range")


def zeckendorf(n):
    _check(n, 0)
    out = []
    for f in reversed(_fibs(n)):
        if f <= n:
            out.append(f)
            n -= f
    return out


def fib_code(n):
    _check(n, 1)
    fs = _fibs(n)
    bits = ["0"] * len(fs)
    for i in range(len(fs) - 1, -1, -1):
        if fs[i] <= n:
            bits[i] = "1"
            n -= fs[i]
    return "".join(bits).rstrip("0") + "1"


def fib_decode(bits):
    if not isinstance(bits, str) or any(c not in "01" for c in bits):
        raise ValueError("bits must be a str of 0 and 1")
    out, fs, val, k, prev = [], [1, 2], 0, 0, "0"
    for c in bits:
        if c == "1" and prev == "1":
            out.append(val)
            val, k, prev = 0, 0, "0"
            continue
        while len(fs) <= k:
            fs.append(fs[-1] + fs[-2])
        if c == "1":
            val += fs[k]
        k += 1
        prev = c
    if k:
        raise ValueError("incomplete code at the end")
    return out
''')

task("v9_10_aliquot_chain", "number_theory", r'''
Write `aliquot_chain(n, limit)`. Let s(m) be the sum of the proper divisors of m (the divisors smaller than m), so
s(1) = 0, s(6) = 6, s(10) = 1 + 2 + 5 = 8. The aliquot sequence of n is n, s(n), s(s(n)), ...

Arguments: `n` must be an int from 1 to 10**6 and `limit` an int from 1 to 1000 (a bool is not an int), otherwise
raise ValueError.

Start with terms = [n] and compute at most `limit` further terms, one at a time. For each new value t = s(last term):
- if t == 0: append 0 and stop with kind "terminates";
- if t already occurs in terms at index i: do NOT append it; the sequence has entered a cycle of length
  L = len(terms) - i. Stop with kind "perfect" if i == 0 and L == 1, "amicable" if i == 0 and L == 2, "sociable" if
  i == 0 and L >= 3, "aspiring" if i > 0 and L == 1, and "cyclic" if i > 0 and L >= 2;
- otherwise append t; if t > 10**9 stop with kind "unknown".
If `limit` terms were computed without stopping, the kind is "unknown". Return the tuple (kind, terms).

Factor each term by trial division up to its square root; a term of up to 10**9 needs at most about 31623 trial
divisors.

Examples:
- aliquot_chain(10, 10) == ("terminates", [10, 8, 7, 1, 0]) and aliquot_chain(1, 1) == ("terminates", [1, 0])
- aliquot_chain(6, 1) == ("perfect", [6]) and aliquot_chain(220, 5) == ("amicable", [220, 284])
- aliquot_chain(12496, 10) == ("sociable", [12496, 14288, 15472, 14536, 14264])
- aliquot_chain(12496, 3) == ("unknown", [12496, 14288, 15472, 14536])
- aliquot_chain(95, 10) == ("aspiring", [95, 25, 6]) and aliquot_chain(562, 10) == ("cyclic", [562, 284, 220])
- aliquot_chain(7, 1) == ("unknown", [7, 1])
- ValueError: aliquot_chain(0, 5), aliquot_chain(10, 0), aliquot_chain(10 ** 6 + 1, 5), aliquot_chain(True, 5)
''', REJ + r'''
import random

A = aliquot_chain

def s(m):
    t, d = 0, 1
    while d * d <= m:
        if m % d == 0:
            t += d + (m // d if d * d != m else 0)
        d += 1
    return t - m

def oracle(n, limit):
    terms = [n]
    for _ in range(limit):
        t = s(terms[-1])
        if t == 0:
            return "terminates", terms + [0]
        if t in terms:
            i = terms.index(t)
            L = len(terms) - i
            if i == 0:
                return ("perfect" if L == 1 else "amicable" if L == 2 else "sociable"), terms
            return ("aspiring" if L == 1 else "cyclic"), terms
        terms.append(t)
        if t > 10 ** 9:
            return "unknown", terms
    return "unknown", terms

assert A(10, 10) == ("terminates", [10, 8, 7, 1, 0]) and A(1, 1) == ("terminates", [1, 0])
assert A(6, 1) == ("perfect", [6]) and A(220, 5) == ("amicable", [220, 284]) and A(284, 1) == ("unknown", [284, 220])
assert A(12496, 10) == ("sociable", [12496, 14288, 15472, 14536, 14264])
assert A(12496, 3) == ("unknown", [12496, 14288, 15472, 14536]) and A(7, 1) == ("unknown", [7, 1])
assert A(95, 10) == ("aspiring", [95, 25, 6]) and A(562, 10) == ("cyclic", [562, 284, 220])
assert A(1, 1000) == ("terminates", [1, 0]) and A(28, 3) == ("perfect", [28]) and A(25, 2) == ("aspiring", [25, 6])
assert A(14316, 30)[0] == "sociable" and len(A(14316, 30)[1]) == 28
assert A(997920, 2) == oracle(997920, 2)
for bad in ((0, 5), (10, 0), (10 ** 6 + 1, 5), (True, 5), (10, False), (10.0, 5), ("10", 5), (10, 1001), (-4, 3)):
    assert rej(A, *bad), bad
random.seed(9010)
for _ in range(70):
    n, limit = random.randint(1, 1500), random.randint(1, 14)
    assert A(n, limit) == oracle(n, limit), (n, limit)
''', r'''
CAP = 10 ** 9


def _s(m):
    total, rest, p = 1, m, 2
    while p * p <= rest:
        if rest % p == 0:
            pk, part = 1, 1
            while rest % p == 0:
                rest //= p
                pk *= p
                part += pk
            total *= part
        p += 1 if p == 2 else 2
    if rest > 1:
        total *= rest + 1
    return total - m


def aliquot_chain(n, limit):
    for v, hi in ((n, 10 ** 6), (limit, 1000)):
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= hi:
            raise ValueError("argument out of range")
    terms, where = [n], {n: 0}
    for _ in range(limit):
        t = _s(terms[-1])
        if t == 0:
            terms.append(0)
            return "terminates", terms
        if t in where:
            i = where[t]
            L = len(terms) - i
            if i == 0:
                kind = "perfect" if L == 1 else "amicable" if L == 2 else "sociable"
            else:
                kind = "aspiring" if L == 1 else "cyclic"
            return kind, terms
        where[t] = len(terms)
        terms.append(t)
        if t > CAP:
            return "unknown", terms
    return "unknown", terms
''')

task("v9_11_primitive_root", "number_theory", r'''
Write `smallest_primitive_root(n)` and `count_primitive_roots(n)`.

For a modulus n >= 2, an integer g with 1 <= g < n and gcd(g, n) = 1 is a primitive root modulo n when the powers
g, g**2, g**3, ... modulo n run through every residue coprime to n before returning to 1, that is, when the smallest
k >= 1 with g**k % n == 1 equals phi(n) (Euler's totient: how many integers from 1 to n are coprime to n). Primitive
roots exist exactly when n is 2, 4, p**k or 2 * p**k for an odd prime p and k >= 1. When they exist there are
phi(phi(n)) of them.

Both functions take `n`, an int from 2 to 10**10 (a bool is not an int); anything else raises ValueError.

smallest_primitive_root(n) returns the smallest primitive root modulo n, or None if n has none.
count_primitive_roots(n) returns how many primitive roots modulo n there are (0 if none).

A g that is coprime to n is a primitive root exactly when pow(g, phi(n) // q, n) != 1 for every prime q dividing
phi(n). Do not compute the order of g by repeated multiplication: phi(n) can be close to 10**10. Trial division up to
10**5 is enough to factor any n in range.

Examples:
- smallest_primitive_root(2) == 1 and count_primitive_roots(2) == 1
- smallest_primitive_root(4) == 3 and smallest_primitive_root(7) == 3 and smallest_primitive_root(41) == 6
- smallest_primitive_root(8) is None and count_primitive_roots(8) == 0 and smallest_primitive_root(15) is None
- smallest_primitive_root(18) == 5 and count_primitive_roots(18) == 2 and count_primitive_roots(7) == 2
- smallest_primitive_root(998244353) == 3 and smallest_primitive_root(10 ** 9 + 7) == 5
- ValueError: smallest_primitive_root(1), smallest_primitive_root(10 ** 10 + 1), count_primitive_roots(True),
  count_primitive_roots(7.0)
''', REJ + r'''
import math, random

G, K = smallest_primitive_root, count_primitive_roots

def brute(n):
    units = [g for g in range(1, n) if math.gcd(g, n) == 1]
    phi = len(units)
    roots = []
    for g in units:
        x, k = g % n, 1
        while x != 1 % n:
            x, k = x * g % n, k + 1
        if k == phi:
            roots.append(g)
    return (roots[0] if roots else None), len(roots)

assert G(2) == 1 and K(2) == 1 and G(4) == 3 and G(7) == 3 and G(41) == 6 and G(8) is None and K(8) == 0
assert G(15) is None and G(18) == 5 and K(18) == 2 and K(7) == 2 and G(3) == 2 and G(9) == 2
assert G(998244353) == 3 and K(998244353) == 402653184 and G(10 ** 9 + 7) == 5 and K(10 ** 9 + 7) == 500000002
assert G(2 * (10 ** 9 + 7)) == 5 and G(3 ** 20) == 2 and K(3 ** 20) == 774840978 and G(10 ** 10) is None
assert G(2 * 3 ** 20) == 5 and K(2 * 3 ** 20) == 774840978 and K(2 * (10 ** 9 + 7)) == 500000002
assert G(191) == 19 and G(409) == 21 and K(10 ** 10) == 0 and G(4 * 7) is None and G(2 * 25) == 3
for bad in (1, 0, 10 ** 10 + 1, True, 7.0, "7", None):
    assert rej(G, bad) and rej(K, bad), bad
random.seed(9011)
for n in [random.randint(60, 110) for _ in range(30)] + list(range(2, 60)):
    assert (G(n), K(n)) == brute(n), n
''', r'''
def _factor(m):
    out, p = {}, 2
    while p * p <= m:
        while m % p == 0:
            out[p] = out.get(p, 0) + 1
            m //= p
        p += 1 if p == 2 else 2
    if m > 1:
        out[m] = out.get(m, 0) + 1
    return out


def _check(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 2 <= n <= 10 ** 10:
        raise ValueError("n must be an int from 2 to 10**10")


def _phi(f):
    r = 1
    for p, e in f.items():
        r *= (p - 1) * p ** (e - 1)
    return r


def _has_root(n, f):
    odd = [p for p in f if p != 2]
    return n in (2, 4) or (len(odd) == 1 and f.get(2, 0) <= 1)


def smallest_primitive_root(n):
    _check(n)
    if n == 2:
        return 1
    f = _factor(n)
    if not _has_root(n, f):
        return None
    phi = _phi(f)
    qs = list(_factor(phi))
    g = 2
    while True:
        if all(g % p for p in f) and all(pow(g, phi // q, n) != 1 for q in qs):
            return g
        g += 1


def count_primitive_roots(n):
    _check(n)
    f = _factor(n)
    if not _has_root(n, f):
        return 0
    return _phi(_factor(_phi(f)))
''')

task("v9_12_factorial_zeros", "number_theory", r'''
Write `trailing_zeros(n, b)` and `binomial_zeros(n, k, b)`.

trailing_zeros(n, b) returns how many zeros n! (n factorial, with 0! = 1) ends with when written in base b.
binomial_zeros(n, k, b) returns how many zeros the binomial coefficient C(n, k) = n! / (k! * (n - k)!) ends with in
base b.

Arguments: `n` must be an int from 0 to 10**18, `k` an int with 0 <= k <= n, and `b` an int from 2 to 10**6 (a bool is
never accepted as an int); anything else raises ValueError.

Never build n! or C(n, k): n can be 10**18. Instead use the exponent of each prime p in m!, which is
floor(m / p) + floor(m / p**2) + floor(m / p**3) + ... (Legendre's formula). The number of trailing zeros of a
positive integer x in base b is the largest z such that b**z divides x; if b = p1**e1 * p2**e2 * ... then
z = min over i of floor(v_i / e_i), where v_i is the exponent of p_i in x. For C(n, k) the exponent of p is the
exponent in n! minus the exponents in k! and (n - k)!.

Examples:
- trailing_zeros(10, 10) == 2 (10! = 3628800) and trailing_zeros(5, 2) == 3 (120 = 0b1111000)
- trailing_zeros(0, 7) == 0 and trailing_zeros(6, 12) == 2 (720 = 5 * 12**2)
- trailing_zeros(100, 10) == 24 and trailing_zeros(10 ** 18, 10) == 249999999999999995
- binomial_zeros(10, 5, 2) == 2 (C(10, 5) = 252) and binomial_zeros(100, 50, 10) == 0
- binomial_zeros(1000, 500, 3) == 4 and binomial_zeros(5, 0, 2) == 0
- ValueError: trailing_zeros(-1, 10), trailing_zeros(5, 1), trailing_zeros(5, 10 ** 6 + 1), trailing_zeros(True, 10),
  binomial_zeros(5, 6, 10), binomial_zeros(5, -1, 10)
''', REJ + r'''
import math, random

TZ, BZ = trailing_zeros, binomial_zeros

def zeros(x, b):
    z = 0
    while x % b == 0:
        x //= b
        z += 1
    return z

def leg(m, p):
    e, q = 0, p
    while q <= m:
        e += m // q
        q *= p
    return e

assert TZ(10, 10) == 2 and TZ(5, 2) == 3 and TZ(0, 7) == 0 and TZ(6, 12) == 2 and TZ(100, 10) == 24
assert TZ(10 ** 18, 10) == 249999999999999995 and TZ(1, 2) == 0 and TZ(10 ** 18, 999983) == leg(10 ** 18, 999983)
assert TZ(10 ** 18, 2 ** 19) == leg(10 ** 18, 2) // 19 and TZ(10 ** 18, 720720) == min(
    leg(10 ** 18, 2) // 4, leg(10 ** 18, 3) // 2, leg(10 ** 18, 5), leg(10 ** 18, 7), leg(10 ** 18, 11), leg(10 ** 18, 13))
assert BZ(10, 5, 2) == 2 and BZ(100, 50, 10) == 0 and BZ(1000, 500, 3) == 4 and BZ(5, 0, 2) == 0 and BZ(0, 0, 9) == 0
assert BZ(10 ** 18, 10 ** 17, 10) == min(leg(10 ** 18, p) - leg(10 ** 17, p) - leg(9 * 10 ** 17, p) for p in (2, 5))
for bad in ((-1, 10), (5, 1), (5, 10 ** 6 + 1), (True, 10), (5, True), (5.0, 10), (10 ** 18 + 1, 10), ("5", 10)):
    assert rej(TZ, *bad), bad
for bad in ((5, 6, 10), (5, -1, 10), (5, 2, 1), (5, True, 10), (5, 2.0, 10), (10 ** 18 + 1, 0, 10)):
    assert rej(BZ, *bad), bad
random.seed(9012)
for _ in range(300):
    n, b = random.randint(0, 220), random.choice([random.randint(2, 40), random.randint(2, 5000)])
    assert TZ(n, b) == zeros(math.factorial(n), b), (n, b)
    k = random.randint(0, n)
    assert BZ(n, k, b) == zeros(math.comb(n, k), b), (n, k, b)
''', r'''
def _int(v, lo, hi):
    if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
        raise ValueError("argument out of range")


def _primes_of(b):
    out, p = {}, 2
    while p * p <= b:
        while b % p == 0:
            out[p] = out.get(p, 0) + 1
            b //= p
        p += 1
    if b > 1:
        out[b] = out.get(b, 0) + 1
    return out


def _legendre(m, p):
    e = 0
    while m:
        m //= p
        e += m
    return e


def trailing_zeros(n, b):
    _int(n, 0, 10 ** 18)
    _int(b, 2, 10 ** 6)
    return min(_legendre(n, p) // e for p, e in _primes_of(b).items())


def binomial_zeros(n, k, b):
    _int(n, 0, 10 ** 18)
    _int(k, 0, n)
    _int(b, 2, 10 ** 6)
    return min((_legendre(n, p) - _legendre(k, p) - _legendre(n - k, p)) // e for p, e in _primes_of(b).items())
''')

task("v9_13_lucky_sieve", "number_theory", r'''
Write `lucky_numbers(limit)` and `nth_lucky(k)` for the lucky numbers of Gardiner, Lazarus, Metropolis and Ulam.

The lucky numbers come from a sieve that deletes by position, not by value:
1. Start with the odd numbers 1, 3, 5, 7, 9, 11, ...
2. The second number in the list is 3. Delete every 3rd number of the list (the numbers at positions 3, 6, 9, ...,
   counting positions from 1): 1, 3, 7, 9, 13, 15, 19, 21, 25, ... remain.
3. The next number in the list after 3 is 7. Delete every 7th number of the list as it is now.
4. Continue: take the next surviving number after the one just used, say m, and delete every m-th number of the
   current list. Numbers that survive every step are lucky.
Each step renumbers the positions of the list that is left; never delete by value or by the original positions.

lucky_numbers(limit): `limit` must be an int from 0 to 10**5 (a bool is not an int), otherwise raise ValueError.
Return the sorted list of all lucky numbers <= limit. Running the sieve on the odd numbers up to `limit` gives exactly
these, because deleting by position never depends on numbers further right.

nth_lucky(k): `k` must be an int from 1 to 5000, otherwise ValueError. Return the k-th lucky number (nth_lucky(1) is
1). The 5000th lucky number is below 60000.

Examples:
- lucky_numbers(25) == [1, 3, 7, 9, 13, 15, 21, 25] and lucky_numbers(0) == [] and lucky_numbers(2) == [1]
- lucky_numbers(80)[-5:] == [67, 69, 73, 75, 79]
- nth_lucky(1) == 1 and nth_lucky(4) == 9 and nth_lucky(20) == 79
- ValueError: lucky_numbers(-1), lucky_numbers(10 ** 5 + 1), lucky_numbers(True), nth_lucky(0), nth_lucky(5001)
''', REJ + r'''
import random

L, N = lucky_numbers, nth_lucky

def olucky(limit):
    keep = [True] * (limit + 1)
    for v in range(0, limit + 1, 2):
        keep[v] = False
    step = 1
    while True:
        alive = [v for v in range(limit + 1) if keep[v]]
        if step >= len(alive) or alive[step] > len(alive):
            return alive
        m = alive[step]
        for pos, v in enumerate(alive, 1):
            if pos % m == 0:
                keep[v] = False
        step += 1

FIRST = [1, 3, 7, 9, 13, 15, 21, 25, 31, 33, 37, 43, 49, 51, 63, 67, 69, 73, 75, 79, 87, 93, 99]
assert L(25) == [1, 3, 7, 9, 13, 15, 21, 25] and L(0) == [] and L(2) == [1] and L(1) == [1]
assert L(80)[-5:] == [67, 69, 73, 75, 79] and L(100) == FIRST
assert N(1) == 1 and N(4) == 9 and N(20) == 79 and [N(i) for i in range(1, 24)] == FIRST
for bad in (-1, 10 ** 5 + 1, True, 3.0, "9", None):
    assert rej(L, bad), bad
for bad in (0, 5001, False, 1.0, None):
    assert rej(N, bad), bad
big = L(10 ** 5)
assert big[:len(FIRST)] == FIRST and big == sorted(set(big)) and all(v % 2 for v in big)
assert N(5000) == big[4999] < 60000 and N(4321) == big[4320]
assert big[:400] == olucky(big[399])
random.seed(9013)
for _ in range(25):
    lim = random.randint(0, 2500)
    assert L(lim) == olucky(lim), lim
for _ in range(40):
    k = random.randint(1, 5000)
    assert N(k) == big[k - 1], k
''', r'''
def _sieve(limit):
    lst = list(range(1, limit + 1, 2))
    i = 1
    while i < len(lst) and lst[i] <= len(lst):
        m = lst[i]
        del lst[m - 1::m]
        i += 1
    return lst


def lucky_numbers(limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 10 ** 5:
        raise ValueError("limit must be an int from 0 to 10**5")
    return _sieve(limit)


def nth_lucky(k):
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 5000:
        raise ValueError("k must be an int from 1 to 5000")
    limit = 1024
    while True:
        lst = _sieve(limit)
        if len(lst) >= k:
            return lst[k - 1]
        limit *= 2
''')

task("v9_14_consecutive_sums", "number_theory", r'''
Write `consecutive_sums(n)` and `count_consecutive_sums(n)`.

A run is a sum of two or more consecutive positive integers a + (a + 1) + ... + b with 1 <= a < b. For example
15 = 1 + 2 + 3 + 4 + 5 = 4 + 5 + 6 = 7 + 8, so 15 has three runs, and 8 has none.

consecutive_sums(n): `n` must be an int from 1 to 10**12 (a bool is not an int), otherwise raise ValueError. Return
every run that sums to n as a tuple (a, b), in a list sorted by a ascending.

count_consecutive_sums(n): same argument rules. Return how many runs sum to n.

A run of k terms starting at a sums to k * (2a + k - 1) / 2, so k must divide 2n. Do not try every a: n can be
10**12. Factoring n by trial division up to 10**6 and walking the divisors of 2n is fast enough; the number of runs
equals the number of odd divisors of n, minus one.

Examples:
- consecutive_sums(15) == [(1, 5), (4, 6), (7, 8)] and count_consecutive_sums(15) == 3
- consecutive_sums(8) == [] and consecutive_sums(1) == [] and consecutive_sums(2) == []
- consecutive_sums(9) == [(2, 4), (4, 5)] and consecutive_sums(3) == [(1, 2)]
- count_consecutive_sums(2 ** 39) == 0 and count_consecutive_sums(3 ** 25) == 25
- consecutive_sums(10 ** 12)[-1] == (199999999998, 200000000002) and count_consecutive_sums(10 ** 12) == 12
- ValueError: consecutive_sums(0), consecutive_sums(10 ** 12 + 1), count_consecutive_sums(True),
  count_consecutive_sums(2.0)
''', REJ + r'''
import random

S, K = consecutive_sums, count_consecutive_sums

def brute(n):
    out = []
    for a in range(1, n):
        t, b = 0, a
        while t < n:
            t += b
            b += 1
        if t == n and b - 1 > a:
            out.append((a, b - 1))
    return out

assert S(15) == [(1, 5), (4, 6), (7, 8)] and K(15) == 3 and S(8) == [] and S(1) == [] and S(2) == []
assert S(9) == [(2, 4), (4, 5)] and S(3) == [(1, 2)] and K(2 ** 39) == 0 and K(3 ** 25) == 25
assert S(10 ** 12)[-1] == (199999999998, 200000000002) and K(10 ** 12) == 12 and len(S(10 ** 12)) == 12
big = 999999999989
assert S(big) == [(499999999994, 499999999995)] and K(big) == 1
r = S(3 ** 25)
assert len(r) == 25 and all((a + b) * (b - a + 1) // 2 == 3 ** 25 for a, b in r) and r == sorted(r)
for bad in (0, 10 ** 12 + 1, True, 2.0, "15", None, -15):
    assert rej(S, bad) and rej(K, bad), bad
random.seed(9014)
for n in [random.randint(1, 1200) for _ in range(150)] + list(range(1, 60)):
    want = brute(n)
    assert S(n) == want and K(n) == len(want), n
for _ in range(20):
    n = random.randint(1, 10 ** 12)
    r = S(n)
    assert len(r) == K(n) and r == sorted(r) and all(1 <= a < b and (a + b) * (b - a + 1) == 2 * n for a, b in r), n
''', r'''
def _check(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10 ** 12:
        raise ValueError("n must be an int from 1 to 10**12")


def _divisors(m):
    f, p = {}, 2
    while p * p <= m:
        while m % p == 0:
            f[p] = f.get(p, 0) + 1
            m //= p
        p += 1 if p == 2 else 2
    if m > 1:
        f[m] = f.get(m, 0) + 1
    ds = [1]
    for p, e in f.items():
        ds = [d * p ** i for d in ds for i in range(e + 1)]
    return ds


def consecutive_sums(n):
    _check(n)
    out = []
    for k in _divisors(2 * n):
        if k < 2:
            continue
        twice_a = 2 * n // k - k + 1
        if twice_a >= 2 and twice_a % 2 == 0:
            a = twice_a // 2
            out.append((a, a + k - 1))
    return sorted(out)


def count_consecutive_sums(n):
    _check(n)
    while n % 2 == 0:
        n //= 2
    return len(_divisors(n)) - 1
''')

task("v9_15_gaussian_gcd", "number_theory", r'''
Write `gauss_divmod(a, b)` and `gauss_gcd(a, b)` for Gaussian integers x + y*i, written as pairs (x, y).

Arguments: each of `a` and `b` must be a tuple or list of exactly two ints (a bool is not an int) with absolute values
at most 10**18; anything else raises ValueError. Results are tuples of two ints. Use only exact integer arithmetic;
complex floats lose precision long before 10**18.

Arithmetic: (x1, y1) * (x2, y2) = (x1*x2 - y1*y2, x1*y2 + y1*x2). The norm of (x, y) is x*x + y*y. The units are
(1, 0), (0, 1), (-1, 0) and (0, -1).

gauss_divmod(a, b): `b` must not be (0, 0) (ValueError). Let a / b = u + v*i with rational u and v. The quotient q is
(round(u), round(v)), where each component is rounded to the nearest integer and an exact half is rounded up (toward
plus infinity), so 2.5 -> 3 and -2.5 -> -2. The remainder is r = a - q * b. Return (q, r). The norm of r is always at
most half the norm of b.

gauss_gcd(a, b): a greatest common divisor of a and b, found by Euclid's algorithm with gauss_divmod. A gcd is unique
only up to multiplication by a unit; return the one associate (g times a unit) with x > 0 and y >= 0. gauss_gcd of
(0, 0) and (0, 0) is (0, 0).

Examples:
- gauss_divmod((7, 0), (2, 0)) == ((4, 0), (-1, 0)) and gauss_divmod((5, 0), (-2, 0)) == ((-2, 0), (1, 0))
- gauss_divmod((3, 4), (1, 2)) == ((2, 0), (1, 0))
- gauss_gcd((3, 4), (1, 2)) == (1, 0) and gauss_gcd((4, 2), (6, 8)) == (4, 2)
- gauss_gcd((0, 0), (0, 5)) == (5, 0) and gauss_gcd((0, 0), (0, 0)) == (0, 0) and gauss_gcd((-2, 0), (0, 0)) == (2, 0)
- gauss_gcd((5, 0), (3, 4)) == (2, 1)
- ValueError: gauss_divmod((1, 0), (0, 0)), gauss_gcd((1, 2, 3), (1, 0)), gauss_gcd((True, 0), (1, 0)),
  gauss_gcd((1.0, 0), (1, 0)), gauss_gcd((10 ** 18 + 1, 0), (1, 0))
''', REJ + r'''
import math, random
from fractions import Fraction

DM, GG = gauss_divmod, gauss_gcd

def mul(a, b):
    return (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0])

def norm(a):
    return a[0] * a[0] + a[1] * a[1]

def unit_normal(g):
    for _ in range(4):
        if g[0] > 0 and g[1] >= 0:
            return g
        g = (-g[1], g[0])
    return (0, 0)

def odm(a, b):
    n = norm(b)
    u = Fraction(a[0] * b[0] + a[1] * b[1], n)
    v = Fraction(a[1] * b[0] - a[0] * b[1], n)
    q = (math.floor(u + Fraction(1, 2)), math.floor(v + Fraction(1, 2)))
    qb = mul(q, b)
    return q, (a[0] - qb[0], a[1] - qb[1])

assert DM((7, 0), (2, 0)) == ((4, 0), (-1, 0)) and DM((5, 0), (-2, 0)) == ((-2, 0), (1, 0))
assert DM((3, 4), (1, 2)) == ((2, 0), (1, 0)) and DM([0, 0], [3, 3]) == ((0, 0), (0, 0))
assert DM((1, 0), (0, 2)) == ((0, 0), (1, 0)) and DM((-1, 0), (2, 0)) == ((0, 0), (-1, 0))
assert GG((3, 4), (1, 2)) == (1, 0) and GG((4, 2), (6, 8)) == (4, 2) and GG((0, 0), (0, 5)) == (5, 0)
assert GG((0, 0), (0, 0)) == (0, 0) and GG((-2, 0), (0, 0)) == (2, 0) and GG((5, 0), (3, 4)) == (2, 1)
assert GG((0, -7), (0, 0)) == (7, 0) and GG((1, 1), (1, -1)) == (1, 1) and GG([2, 0], [0, 2]) == (2, 0)
B = 10 ** 18
assert GG((B, B), (B, -B)) == (B, B) and DM((B, B), (1, 0)) == ((B, B), (0, 0))
for bad in (((1, 0), (0, 0)), ((1, 2, 3), (1, 0)), ((True, 0), (1, 0)), ((1.0, 0), (1, 0)), ((B + 1, 0), (1, 0)),
            ((1,), (1, 0)), ("ab", (1, 0)), ((1, 0), None), (1 + 2j, (1, 0)), ((1, 0), (0, -B - 1))):
    assert rej(DM, *bad), bad
for bad in (((1, 2, 3), (1, 0)), ((True, 0), (1, 0)), ((1.0, 0), (1, 0)), ((B + 1, 0), (1, 0)), ((0, 0), [0, False])):
    assert rej(GG, *bad), bad
random.seed(9015)
for _ in range(1500):
    lim = random.choice([5, 1000, 10 ** 8])
    a = (random.randint(-lim, lim), random.randint(-lim, lim))
    b = (random.randint(-lim, lim), random.randint(-lim, lim))
    if b != (0, 0):
        got = DM(a, b)
        assert got == odm(a, b), (a, b)
        assert 2 * norm(got[1]) <= norm(b), (a, b)
for _ in range(1000):
    lim = random.choice([3, 40, 10 ** 4])
    d = (random.randint(-lim, lim), random.randint(-lim, lim))
    u = (random.randint(-30, 30), random.randint(-30, 30))
    v = (random.randint(-30, 30), random.randint(-30, 30))
    if math.gcd(norm(u), norm(v)) != 1:
        continue
    assert GG(mul(d, u), mul(d, v)) == unit_normal(d), (d, u, v)
''', r'''
LIM = 10 ** 18


def _arg(z):
    if not isinstance(z, (tuple, list)) or len(z) != 2:
        raise ValueError("need a pair")
    for c in z:
        if not isinstance(c, int) or isinstance(c, bool) or abs(c) > LIM:
            raise ValueError("bad component")
    return int(z[0]), int(z[1])


def _round_half_up(num, den):
    return (2 * num + den) // (2 * den)


def _divmod(a, b):
    n = b[0] * b[0] + b[1] * b[1]
    q = (_round_half_up(a[0] * b[0] + a[1] * b[1], n), _round_half_up(a[1] * b[0] - a[0] * b[1], n))
    r = (a[0] - (q[0] * b[0] - q[1] * b[1]), a[1] - (q[0] * b[1] + q[1] * b[0]))
    return q, r


def gauss_divmod(a, b):
    a, b = _arg(a), _arg(b)
    if b == (0, 0):
        raise ValueError("division by zero")
    return _divmod(a, b)


def gauss_gcd(a, b):
    a, b = _arg(a), _arg(b)
    while b != (0, 0):
        a, b = b, _divmod(a, b)[1]
    x, y = a
    if (x, y) == (0, 0):
        return (0, 0)
    while not (x > 0 and y >= 0):
        x, y = -y, x
    return (x, y)
''')

# --- graphs_geometry ---

task("v9_16_lca_queries", "graphs_geometry", r'''
Write `lca_answers(parent, queries)` that answers lowest-common-ancestor queries on a rooted tree.

The tree has nodes 0 to n-1 and is given by `parent`, a list of n ints (1 <= n <= 20000; a bool is not an int):
parent[v] is the parent of v, and exactly one node, the root, has parent -1. Every other entry must be a node index
from 0 to n-1, and following parents from any node must reach the root (no cycles, no self-parent). Anything else
raises ValueError.

`queries` is a list of at most 20000 pairs (u, v), each a tuple or list of two node indices (ints in range, no bools);
otherwise ValueError. For each pair, return a tuple (w, d): w is the lowest common ancestor of u and v (the deepest
node that is an ancestor of both; a node is its own ancestor), and d is the number of edges on the path from u to v.
Return the answers as a list in query order.

The tree can be a single path of 20000 nodes, so do not recurse along it (Python's recursion limit is 1000) and do not
walk parent pointers one step at a time for every query. Compute depths with an explicit stack or queue from the root,
then use binary lifting (a table of 2**j-th ancestors) or another method that is fast for 20000 queries on a deep tree.

Examples:
- parent = [-1, 0, 0, 1, 1, 2]: lca_answers(parent, [(3, 4), (3, 5), (0, 0), (4, 1)]) == [(1, 2), (0, 4), (0, 0), (1, 1)]
- lca_answers([2, 2, -1], [[0, 1]]) == [(2, 2)] and lca_answers([-1], []) == []
- ValueError: lca_answers([-1, -1], []), lca_answers([1, 0], []), lca_answers([-1, 1], []), lca_answers([-1, 5], []),
  lca_answers([-1, 0], [(0, 2)]), lca_answers([-1, 0], [(0,)]), lca_answers([-1, True], []), lca_answers([], [])
''', REJ + r'''
import random

Q = lca_answers

def oracle(parent, qs):
    def chain(v):
        out = [v]
        while parent[out[-1]] != -1:
            out.append(parent[out[-1]])
        return out
    res = []
    for u, v in qs:
        cu, cv = chain(u), chain(v)
        su = set(cu)
        w = next(x for x in cv if x in su)
        res.append((w, cu.index(w) + cv.index(w)))
    return res

P0 = [-1, 0, 0, 1, 1, 2]
assert Q(P0, [(3, 4), (3, 5), (0, 0), (4, 1)]) == [(1, 2), (0, 4), (0, 0), (1, 1)]
assert Q([2, 2, -1], [[0, 1]]) == [(2, 2)] and Q([-1], []) == [] and Q([-1], [(0, 0)]) == [(0, 0)]
for bad in (([-1, -1], []), ([1, 0], []), ([-1, 1], []), ([-1, 5], []), ([-1, 0], [(0, 2)]), ([-1, 0], [(0,)]),
            ([-1, True], []), ([], []), ([-1, 0, 3, 2], []), ([-1, 0], [(True, 0)]), ([-1, 0], [(0, -1)]),
            ((-1, 0), []), ([-1, 0.0], []), ([-1, 0], None), ([-1, 0], [0, 1])):
    assert rej(Q, *bad), bad
n = 20000
path = [-1] + list(range(n - 1))
qs = [(n - 1, 0), (n - 1, n - 2), (12345, 19999), (7, 7)]
assert Q(path, qs) == [(0, n - 1), (n - 2, 1), (12345, 19999 - 12345), (7, 0)]
random.seed(9016)
order = list(range(n))
random.shuffle(order)
par = [-1] * n
for i in range(1, n):
    par[order[i]] = order[i - 1] if random.random() < 0.97 else order[random.randrange(i)]
qs = [(random.randrange(n), random.randrange(n)) for _ in range(20000)]
got = Q(par, qs)
sample = random.sample(range(20000), 60)
assert [got[i] for i in sample] == oracle(par, [qs[i] for i in sample])
for _ in range(300):
    m = random.randint(1, 40)
    lab = list(range(m))
    random.shuffle(lab)
    par = [-1] * m
    for i in range(1, m):
        par[lab[i]] = lab[random.randrange(i)]
    qs = [(random.randrange(m), random.randrange(m)) for _ in range(10)]
    assert Q(par, qs) == oracle(par, qs), (par, qs)
''', r'''
def _node(x, n):
    return isinstance(x, int) and not isinstance(x, bool) and 0 <= x < n


def lca_answers(parent, queries):
    if not isinstance(parent, list) or not 1 <= len(parent) <= 20000 or not isinstance(queries, list):
        raise ValueError("bad arguments")
    n = len(parent)
    roots = [v for v, p in enumerate(parent) if p == -1 and not isinstance(p, bool)]
    if len(roots) != 1 or any(p != -1 and (not _node(p, n) or p == v) for v, p in enumerate(parent)):
        raise ValueError("bad parent list")
    children = [[] for _ in range(n)]
    for v, p in enumerate(parent):
        if p != -1:
            children[p].append(v)
    depth, order, stack = [0] * n, [], [roots[0]]
    while stack:
        v = stack.pop()
        order.append(v)
        for c in children[v]:
            depth[c] = depth[v] + 1
            stack.append(c)
    if len(order) != n:
        raise ValueError("cycle in parent list")
    up = [[p if p != -1 else v for v, p in enumerate(parent)]]
    while (1 << len(up)) < n:
        prev = up[-1]
        up.append([prev[prev[v]] for v in range(n)])
    out = []
    for q in queries:
        if not isinstance(q, (tuple, list)) or len(q) != 2 or not (_node(q[0], n) and _node(q[1], n)):
            raise ValueError("bad query")
        u, v = q
        a, b = (u, v) if depth[u] >= depth[v] else (v, u)
        diff, j = depth[a] - depth[b], 0
        while diff:
            if diff & 1:
                a = up[j][a]
            diff >>= 1
            j += 1
        if a != b:
            for j in range(len(up) - 1, -1, -1):
                if up[j][a] != up[j][b]:
                    a, b = up[j][a], up[j][b]
            a = parent[a]
        out.append((a, depth[u] + depth[v] - 2 * depth[a]))
    return out
''')

task("v9_17_key_maze", "graphs_geometry", r'''
Write `maze_steps(grid)` that returns the fewest moves needed to get from the start to the exit of a maze with keys and
doors, or -1 if the exit cannot be reached.

`grid` is a list of 1 to 30 strs, all of the same length from 1 to 30, using only these characters:
- "#" wall, "." floor;
- "S" the start (exactly one), "E" the exit (exactly one); both are floor;
- "a" to "d": a key, picked up automatically when you step on the cell (and kept for good; the cell stays floor);
- "A" to "D": a door; you may step onto it only while holding the key with the same letter in lower case.
Anything else (wrong type, ragged rows, other characters, not exactly one S or E, more than 30 rows or columns, an
empty grid) raises ValueError.

A move goes one cell up, down, left or right, never off the grid and never into a wall. Several keys and doors may
share a letter. Reaching E ends the walk; return the number of moves. A key on the start cell does not exist (S is
its own character). Use breadth-first search over states (row, column, set of keys held); with four key letters there
are at most 30 * 30 * 16 states.

Examples:
- maze_steps(["S.E"]) == 2 and maze_steps(["S#E"]) == -1
- maze_steps(["SAE", "a##"]) == 4 (down to the key a, back up, then right through the door A to E)
- maze_steps(["SA.E", "a###"]) == 5 (down to the key, back up, right through A, right, right)
- maze_steps(["SBE", "a##"]) == -1 (the key a does not open door B)
- ValueError: maze_steps(["S.", "E"]), maze_steps(["S.e"]), maze_steps(["S.."]), maze_steps(["SSE"]), maze_steps([])
''', REJ + r'''
import random

M = maze_steps

def oracle(grid):
    h, w = len(grid), len(grid[0])
    start = next((r, c) for r in range(h) for c in range(w) if grid[r][c] == "S")
    seen = {(start, frozenset())}
    layer, d = [(start, frozenset())], 0
    while layer:
        nxt = []
        for (r, c), keys in layer:
            if grid[r][c] == "E":
                return d
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < h and 0 <= cc < w):
                    continue
                ch = grid[rr][cc]
                if ch == "#" or (ch.isupper() and ch not in "SE" and ch.lower() not in keys):
                    continue
                k2 = keys | {ch} if ch in "abcd" else keys
                st = ((rr, cc), k2)
                if st not in seen:
                    seen.add(st)
                    nxt.append(st)
        layer, d = nxt, d + 1
    return -1

assert M(["S.E"]) == 2 and M(["S#E"]) == -1 and M(["SAE", ".#.", "a.."]) == 6 and M(["SAE", "a##"]) == 4 and M(["SA.E", "a###"]) == 5
assert M(["SBE", "a##"]) == -1 and M(["SE"]) == 1 and M(["S", "E"]) == 1
assert M(["a.S.A.E", "b######", "B#....."]) == oracle(["a.S.A.E", "b######", "B#....."])
for bad in (["S.", "E"], ["S.e"], ["S.."], ["SSE"], [], ["S.E", 5], "S.E", ["S.G", "..E"], ["S.F", "..E"], [""], ["SE"] * 31,
            ["S" + "." * 29 + "E"], None, ["S\tE"]):
    assert rej(M, bad), bad
random.seed(9017)
for _ in range(400):
    h, w = random.randint(1, 9), random.randint(2, 9)
    cells = [random.choice("....##abcABC") for _ in range(h * w)]
    i, j = random.sample(range(h * w), 2)
    cells[i], cells[j] = "S", "E"
    grid = ["".join(cells[r * w:(r + 1) * w]) for r in range(h)]
    assert M(grid) == oracle(grid), grid
big = ["S" + "." * 29] + ["." * 30] * 28 + ["." * 29 + "E"]
assert M(big) == 58
''', r'''
from collections import deque

ALLOWED = set("#.SEabcdABCD")


def maze_steps(grid):
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        raise ValueError("grid must be a list of 1 to 30 rows")
    if not all(isinstance(r, str) for r in grid):
        raise ValueError("rows must be str")
    w = len(grid[0])
    if not 1 <= w <= 30 or any(len(r) != w for r in grid) or any(c not in ALLOWED for r in grid for c in r):
        raise ValueError("bad grid shape or character")
    flat = "".join(grid)
    if flat.count("S") != 1 or flat.count("E") != 1:
        raise ValueError("need exactly one S and one E")
    h = len(grid)
    s = flat.index("S")
    start = (s // w, s % w, 0)
    seen = {start}
    q = deque([(start, 0)])
    while q:
        (r, c, keys), d = q.popleft()
        if grid[r][c] == "E":
            return d
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if not (0 <= rr < h and 0 <= cc < w):
                continue
            ch = grid[rr][cc]
            if ch == "#":
                continue
            k = keys
            if "A" <= ch <= "D" and not keys >> (ord(ch) - 65) & 1:
                continue
            if "a" <= ch <= "d":
                k = keys | 1 << (ord(ch) - 97)
            st = (rr, cc, k)
            if st not in seen:
                seen.add(st)
                q.append((st, d + 1))
    return -1
''')

task("v9_18_eq_constraints", "graphs_geometry", r'''
Write `satisfiable(constraints)` and `eq_classes(constraints)` for systems of equalities and disequalities between
variables.

`constraints` must be a list of strs, each exactly of the form "x==y" or "x!=y" where x and y are variable names: a
lower-case ASCII letter followed by up to seven lower-case ASCII letters or digits. No spaces anywhere. Anything else
(another type, a bad name, "x=y", "x<>y", "x == y") raises ValueError. The same constraint may appear more than once.

The system is satisfiable when values can be given to all the variables so that every constraint holds. Equalities
are transitive: "a==b" and "b==c" force a == c, so adding "a!=c" makes the system unsatisfiable, and so does "a!=a".
Treat the variables as nodes and every equality as an edge; the system is satisfiable exactly when no disequality
joins two variables of the same connected component. Use a union-find (disjoint-set) structure or a graph search.

satisfiable(constraints): return True or False.

eq_classes(constraints): if the system is not satisfiable return None. Otherwise return the classes of variables that
must be equal: every variable mentioned anywhere (in an equality or a disequality) belongs to exactly one class. Each
class is a sorted list of names, and the list of classes is sorted (by its first name). An empty system gives [].

Examples:
- satisfiable(["a==b", "b!=c"]) is True and satisfiable(["a==b", "b==c", "a!=c"]) is False
- satisfiable(["x1!=x1"]) is False and satisfiable([]) is True
- eq_classes(["b==a", "c!=d", "e==c"]) == [["a", "b"], ["c", "e"], ["d"]]
- eq_classes(["p==q", "q!=p"]) is None
- ValueError: satisfiable(["a=b"]), satisfiable(["a == b"]), satisfiable(["A==b"]), satisfiable(["1a==b"]),
  satisfiable(["abcdefghi==a"]), satisfiable("a==b"), eq_classes([["a", "b"]])
''', REJ + r'''
import random

SAT, CL = satisfiable, eq_classes

def oracle(cs):
    names, eqs, neqs = set(), [], []
    for c in cs:
        op = "==" if "==" in c else "!="
        a, b = c.split(op)
        names |= {a, b}
        (eqs if op == "==" else neqs).append((a, b))
    comp = {v: {v} for v in names}
    changed = True
    while changed:
        changed = False
        for a, b in eqs:
            if comp[a] is not comp[b]:
                merged = comp[a] | comp[b]
                for v in merged:
                    comp[v] = merged
                changed = True
    if any(comp[a] is comp[b] for a, b in neqs):
        return None
    return sorted(sorted(s) for s in {id(s): s for s in comp.values()}.values())

assert SAT(["a==b", "b!=c"]) is True and SAT(["a==b", "b==c", "a!=c"]) is False and SAT(["x1!=x1"]) is False
assert SAT([]) is True and CL([]) == [] and CL(["b==a", "c!=d", "e==c"]) == [["a", "b"], ["c", "e"], ["d"]]
assert CL(["p==q", "q!=p"]) is None and CL(["z==z"]) == [["z"]] and CL(["abcdefgh==a1"]) == [["a1", "abcdefgh"]]
for bad in (["a=b"], ["a == b"], ["A==b"], ["1a==b"], ["abcdefghi==a"], "a==b", [["a", "b"]], ["a<>b"], ["a==b=="],
            ["a==b", None], ["a!==b"], ["==b"], ["a=="], ["a==b\n"], ["é==b"], ["a_b==c"], ["a==b==c"], None):
    assert rej(SAT, bad) and rej(CL, bad), bad
random.seed(9018)
for _ in range(1500):
    vs = ["v%d" % i for i in range(random.randint(1, 10))] + ["x", "abc"]
    cs = [random.choice(vs) + random.choice(["==", "==", "!="]) + random.choice(vs) for _ in range(random.randrange(14))]
    want = oracle(cs)
    assert SAT(cs) is (want is not None), cs
    assert CL(cs) == want, cs
''', r'''
import re

NAME = re.compile(r"[a-z][a-z0-9]{0,7}")


def _parse(constraints):
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list")
    out = []
    for c in constraints:
        if not isinstance(c, str):
            raise ValueError("constraint must be a str")
        for op in ("==", "!="):
            parts = c.split(op)
            if len(parts) == 2 and all(NAME.fullmatch(p) for p in parts):
                out.append((parts[0], op, parts[1]))
                break
        else:
            raise ValueError("bad constraint %r" % c)
    return out


def _solve(constraints):
    cs = _parse(constraints)
    root = {}

    def find(x):
        root.setdefault(x, x)
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    for a, op, b in cs:
        find(a)
        find(b)
        if op == "==":
            root[find(a)] = find(b)
    ok = all(find(a) != find(b) for a, op, b in cs if op == "!=")
    return ok, root, find


def satisfiable(constraints):
    return _solve(constraints)[0]


def eq_classes(constraints):
    ok, root, find = _solve(constraints)
    if not ok:
        return None
    groups = {}
    for v in list(root):
        groups.setdefault(find(v), []).append(v)
    return sorted(sorted(g) for g in groups.values())
''')

task("v9_19_func_graph_tails", "graphs_geometry", r'''
Write `rho_shapes(f)` for a functional graph: nodes 0 to n-1 where every node v has exactly one outgoing edge, to
f[v]. Starting at any node and following edges, the walk eventually enters a cycle and goes around it forever, so the
walk looks like the Greek letter rho: a tail, then a loop.

`f` must be a list of n ints (1 <= n <= 10**5; a bool is not an int), each from 0 to n-1; anything else raises
ValueError.

Return a list of n tuples; entry v is (tail, cycle) where `tail` is the number of edges followed from v before the
first node that lies on a cycle (0 if v itself is on a cycle), and `cycle` is the length of the cycle that the walk
from v ends in. A node with f[v] == v is a cycle of length 1.

n can be 10**5 and a single tail can be about 10**5 long, so the whole computation must take about O(n) steps: do not
simulate the walk from every node separately, and do not recurse along tails (Python's recursion limit is 1000). One
way: walk from each node not yet finished, marking the nodes of the current walk; if the walk meets a node of the
current walk, those nodes from the meeting point on form a new cycle; then fill in the rest of the walk backwards,
each node getting tail = tail of its successor + 1 and the same cycle length.

Examples:
- rho_shapes([1, 2, 0]) == [(0, 3), (0, 3), (0, 3)]
- rho_shapes([1, 2, 3, 2]) == [(2, 2), (1, 2), (0, 2), (0, 2)]
- rho_shapes([0]) == [(0, 1)] and rho_shapes([1, 1, 1, 0]) == [(1, 1), (0, 1), (1, 1), (2, 1)]
- ValueError: rho_shapes([]), rho_shapes([1]), rho_shapes([-1]), rho_shapes([True]), rho_shapes((0,)),
  rho_shapes([0.0])
''', REJ + r'''
import random

R = rho_shapes

def oracle(f):
    out = []
    for v in range(len(f)):
        seen, x, i = {}, v, 0
        while x not in seen:
            seen[x] = i
            x, i = f[x], i + 1
        out.append((seen[x], i - seen[x]))
    return out

assert R([1, 2, 0]) == [(0, 3)] * 3 and R([1, 2, 3, 2]) == [(2, 2), (1, 2), (0, 2), (0, 2)] and R([0]) == [(0, 1)]
assert R([1, 1, 1, 0]) == [(1, 1), (0, 1), (1, 1), (2, 1)]
for bad in ([], [1], [-1], [True], (0,), [0.0], None, [0, 2], "0", [0, None]):
    assert rej(R, bad), bad
n = 10 ** 5
f = list(range(1, n)) + [n - 7]
got = R(f)
assert got[0] == (n - 7, 7) and got[n - 1] == (0, 7) and got[n - 8] == (1, 7) and len(got) == n
random.seed(9019)
f = [random.randrange(n) for _ in range(n)]
got = R(f)
for v in random.sample(range(n), 200):
    t, c = got[v]
    x = v
    for _ in range(t):
        x = f[x]
    y = x
    for _ in range(c):
        y = f[y]
    assert y == x and (t == 0 or got[f[v]] == (t - 1, c)), v
for _ in range(500):
    m = random.randint(1, 25)
    f = [random.randrange(m) for _ in range(m)]
    assert R(f) == oracle(f), f
''', r'''
def rho_shapes(f):
    if not isinstance(f, list) or not 1 <= len(f) <= 10 ** 5:
        raise ValueError("f must be a list of 1 to 10**5 ints")
    n = len(f)
    for x in f:
        if not isinstance(x, int) or isinstance(x, bool) or not 0 <= x < n:
            raise ValueError("bad edge")
    tail, cyc, state = [0] * n, [0] * n, [0] * n
    for s in range(n):
        if state[s]:
            continue
        path, pos, x = [], {}, s
        while state[x] == 0 and x not in pos:
            pos[x] = len(path)
            path.append(x)
            x = f[x]
        if x in pos:
            i = pos[x]
            length = len(path) - i
            for y in path[i:]:
                tail[y], cyc[y], state[y] = 0, length, 2
            path = path[:i]
        for y in reversed(path):
            tail[y], cyc[y], state[y] = tail[f[y]] + 1, cyc[f[y]], 2
    return list(zip(tail, cyc))
''')

task("v9_20_grid_line", "graphs_geometry", r'''
Write `line_cells(x0, y0, x1, y1)` and `line_of_sight(grid, a, b)` for straight lines drawn on an integer grid.

line_cells(x0, y0, x1, y1): all four arguments must be ints with absolute value at most 10**6 (a bool is not an int);
otherwise raise ValueError. Let dx = x1 - x0 and dy = y1 - y0. If |dx| >= |dy|, x is the major axis: return the
|dx| + 1 points (x0 + i*sx, y0 + r_i) for i = 0, 1, ..., |dx|, where sx is the sign of dx (1 if dx is 0) and r_i is
i * dy / |dx| (0 when dx = 0) rounded to the nearest integer, an exact half being rounded AWAY from zero (0.5 -> 1,
-0.5 -> -1, 1.5 -> 2). Otherwise y is the major axis and the roles of x and y swap: the points are (x0 + r_i, y0 + i*sy)
for i = 0 to |dy| with r_i = i * dx / |dy| rounded the same way. Return a list of (x, y) tuples, starting at (x0, y0)
and ending at (x1, y1). Use exact integer arithmetic. Note that the line from B to A is not always the reverse of the
line from A to B, because of the rounding direction.

line_of_sight(grid, a, b): `grid` is a non-empty list of equal-length non-empty strs whose characters are "." and "#";
a point (x, y) is the character grid[y][x]. `a` and `b` are tuples of two ints that lie on the grid. Anything else
raises ValueError. Return True when no point of line_cells(a[0], a[1], b[0], b[1]) other than a and b is "#".

Examples:
- line_cells(0, 0, 4, 2) == [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2)]
- line_cells(4, 2, 0, 0) == [(4, 2), (3, 1), (2, 1), (1, 0), (0, 0)]
- line_cells(0, 0, 0, -3) == [(0, 0), (0, -1), (0, -2), (0, -3)] and line_cells(5, 5, 5, 5) == [(5, 5)]
- line_cells(0, 0, 1, 3) == [(0, 0), (0, 1), (1, 2), (1, 3)]
- line_of_sight(["....", ".#..", "...."], (0, 0), (3, 1)) is True and the same with (2, 2) as b is False
- ValueError: line_cells(0, 0, 10 ** 6 + 1, 0), line_cells(0.0, 0, 1, 1), line_cells(True, 0, 1, 1),
  line_of_sight(["..", "..."], (0, 0), (1, 1)), line_of_sight([".."], (0, 0), (2, 0)), line_of_sight([".x"], (0, 0), (1, 0))
''', REJ + r'''
import math, random
from fractions import Fraction

LC, LS = line_cells, line_of_sight

def rnd(t):
    q = math.floor(abs(t) + Fraction(1, 2))
    return q if t >= 0 else -q

def oracle(x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    if abs(dx) >= abs(dy):
        n, s = abs(dx), (1 if dx >= 0 else -1)
        return [(x0 + i * s, y0 + (rnd(Fraction(i * dy, n)) if n else 0)) for i in range(n + 1)]
    n, s = abs(dy), (1 if dy >= 0 else -1)
    return [(x0 + rnd(Fraction(i * dx, n)), y0 + i * s) for i in range(n + 1)]

assert LC(0, 0, 4, 2) == [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2)] and LC(4, 2, 0, 0) == [(4, 2), (3, 1), (2, 1), (1, 0), (0, 0)]
assert LC(0, 0, 0, -3) == [(0, 0), (0, -1), (0, -2), (0, -3)] and LC(5, 5, 5, 5) == [(5, 5)]
assert LC(0, 0, 1, 3) == [(0, 0), (0, 1), (1, 2), (1, 3)] and LC(0, 0, -2, 1) == [(0, 0), (-1, 1), (-2, 1)]
assert LC(0, 0, 3, -3) == [(0, 0), (1, -1), (2, -2), (3, -3)]
assert LC(10 ** 6, -10 ** 6, 10 ** 6 - 2, -10 ** 6 + 3) == [(10 ** 6, -10 ** 6), (10 ** 6 - 1, -10 ** 6 + 1), (10 ** 6 - 1, -10 ** 6 + 2), (10 ** 6 - 2, -10 ** 6 + 3)]
G = ["....", ".#..", "...."]
assert LS(G, (0, 0), (3, 1)) is True and LS(G, (0, 0), (3, 2)) is False and LS(G, (0, 0), (2, 2)) is False and LS(G, (1, 1), (1, 1)) is True
assert LS(["#.#"], (0, 0), (2, 0)) is True and LS(["#.#"], (0, 0), (2, 0)) is True and LS([".#."], (0, 0), (2, 0)) is False
for bad in ((0, 0, 10 ** 6 + 1, 0), (0.0, 0, 1, 1), (True, 0, 1, 1), ("0", 0, 1, 1), (0, None, 1, 1)):
    assert rej(LC, *bad), bad
for bad in ((["..", "..."], (0, 0), (1, 1)), ([".."], (0, 0), (2, 0)), ([".x"], (0, 0), (1, 0)), ([], (0, 0), (0, 0)),
            ([""], (0, 0), (0, 0)), ([".."], (0, 0, 0), (1, 0)), ([".."], (0, -1), (1, 0)), ("..", (0, 0), (1, 0)),
            ([".."], (True, 0), (1, 0)), ([".."], [0, 0.0], (1, 0))):
    assert rej(LS, *bad), bad
random.seed(9020)
for _ in range(2500):
    lim = random.choice([3, 12, 200])
    p = [random.randint(-lim, lim) for _ in range(4)]
    assert LC(*p) == oracle(*p), p
for _ in range(400):
    h, w = random.randint(1, 8), random.randint(1, 8)
    g = ["".join(random.choice("...#") for _ in range(w)) for _ in range(h)]
    a, b = (random.randrange(w), random.randrange(h)), (random.randrange(w), random.randrange(h))
    cells = oracle(a[0], a[1], b[0], b[1])
    assert LS(g, a, b) is all(g[y][x] == "." for x, y in cells[1:-1]), (g, a, b)
''', r'''
LIM = 10 ** 6


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _round_away(num, den):
    q, r = divmod(abs(num), den)
    if 2 * r >= den:
        q += 1
    return q if num >= 0 else -q


def line_cells(x0, y0, x1, y1):
    for v in (x0, y0, x1, y1):
        if not _int(v) or abs(v) > LIM:
            raise ValueError("coordinates must be ints with |v| <= 10**6")
    dx, dy = x1 - x0, y1 - y0
    if abs(dx) >= abs(dy):
        n, s = abs(dx), 1 if dx >= 0 else -1
        return [(x0 + i * s, y0 + (_round_away(i * dy, n) if n else 0)) for i in range(n + 1)]
    n, s = abs(dy), 1 if dy >= 0 else -1
    return [(x0 + _round_away(i * dx, n), y0 + i * s) for i in range(n + 1)]


def line_of_sight(grid, a, b):
    if not isinstance(grid, list) or not grid or not all(isinstance(r, str) for r in grid):
        raise ValueError("grid must be a non-empty list of str")
    w = len(grid[0])
    if w == 0 or any(len(r) != w or set(r) - {".", "#"} for r in grid):
        raise ValueError("bad grid")
    for p in (a, b):
        if not isinstance(p, tuple) or len(p) != 2 or not all(_int(v) for v in p):
            raise ValueError("points must be (x, y) int tuples")
        if not (0 <= p[0] < w and 0 <= p[1] < len(grid)):
            raise ValueError("point off the grid")
    cells = line_cells(a[0], a[1], b[0], b[1])
    return all(grid[y][x] != "#" for x, y in cells[1:-1])
''')

task("v9_21_rdp_simplify", "graphs_geometry", r'''
Write `rdp_simplify(points, eps)` that simplifies a polyline with the Ramer-Douglas-Peucker algorithm, using exact
arithmetic.

Arguments: `points` must be a list of at most 500 points, each a tuple or list of two ints with absolute value at most
10**6 (a bool is not an int); `eps` must be an int >= 0. Anything else raises ValueError. Points may repeat.

The distance from a point P to the segment AB is the Euclidean distance from P to the closest point of the segment (if
A == B, simply the distance from P to A). Compute it exactly: compare squared distances, which are rational numbers,
and never use floats.

Algorithm, on the index range [i, j] (start with i = 0 and j = len(points) - 1):
- if j <= i + 1, nothing between them can be removed;
- otherwise find the index k strictly between i and j whose point is farthest from the segment points[i] to
  points[j]; if several are equally far, take the smallest such k;
- if that distance is greater than eps (strictly), keep points[k] and process [i, k] and [k, j] the same way;
  otherwise drop every point strictly between i and j.
The first and the last point are always kept. Return the kept points, in their original order, as a list of (x, y)
tuples. Lists of 0, 1 or 2 points are returned unchanged (as tuples). Do not modify the input. Use an explicit stack
instead of recursion if you like; with 500 points either works.

Examples:
- rdp_simplify([(0, 0), (1, 0), (2, 0), (3, 0)], 0) == [(0, 0), (3, 0)]
- rdp_simplify([(0, 0), (1, 1), (2, 0)], 0) == [(0, 0), (1, 1), (2, 0)]
- rdp_simplify([(0, 0), (1, 1), (2, 0)], 1) == [(0, 0), (2, 0)] (distance exactly 1 is not greater than 1)
- rdp_simplify([(0, 0), (5, 3), (0, 0)], 5) == [(0, 0), (5, 3), (0, 0)] (distance sqrt(34) > 5)
- rdp_simplify([(0, 0), (-3, 0), (10, 0)], 2) == [(0, 0), (-3, 0), (10, 0)] (the closest point of the segment is its end
  (0, 0), at distance 3)
- rdp_simplify([], 3) == [] and rdp_simplify([[1, 2]], 0) == [(1, 2)]
- ValueError: rdp_simplify([(0, 0)], -1), rdp_simplify([(0, 0.5)], 1), rdp_simplify([(0, 0, 0)], 1),
  rdp_simplify([(True, 0)], 1), rdp_simplify([(0, 0)], 1.0), rdp_simplify([(0, 0)] * 501, 1)
''', REJ + r'''
import random
from fractions import Fraction

R = rdp_simplify

def d2(p, a, b):
    if a == b:
        t = Fraction(0)
    else:
        t = Fraction((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1]), (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        t = min(max(t, Fraction(0)), Fraction(1))
    cx, cy = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
    return (p[0] - cx) ** 2 + (p[1] - cy) ** 2

def oracle(pts, eps):
    pts = [tuple(p) for p in pts]
    if len(pts) < 3:
        return pts
    def go(i, j):
        if j <= i + 1:
            return [i]
        best = max(range(i + 1, j), key=lambda k: (d2(pts[k], pts[i], pts[j]), -k))
        if d2(pts[best], pts[i], pts[j]) > eps * eps:
            return go(i, best) + go(best, j)
        return [i]
    return [pts[k] for k in go(0, len(pts) - 1)] + [pts[-1]]

assert R([(0, 0), (1, 0), (2, 0), (3, 0)], 0) == [(0, 0), (3, 0)] and R([(0, 0), (1, 1), (2, 0)], 0) == [(0, 0), (1, 1), (2, 0)]
assert R([(0, 0), (1, 1), (2, 0)], 1) == [(0, 0), (2, 0)] and R([(0, 0), (5, 3), (0, 0)], 5) == [(0, 0), (5, 3), (0, 0)]
assert R([(0, 0), (-3, 0), (10, 0)], 2) == [(0, 0), (-3, 0), (10, 0)] and R([], 3) == [] and R([[1, 2]], 0) == [(1, 2)]
assert R([(0, 0), (5, 3), (0, 0)], 6) == [(0, 0), (0, 0)] and R([[0, 0], [9, 9]], 0) == [(0, 0), (9, 9)]
src = [[0, 0], [1, 5], [2, 0]]
assert R(src, 1) == [(0, 0), (1, 5), (2, 0)] and src == [[0, 0], [1, 5], [2, 0]]
for bad in (([(0, 0)], -1), ([(0, 0.5)], 1), ([(0, 0, 0)], 1), ([(True, 0)], 1), ([(0, 0)], 1.0), ([(0, 0)] * 501, 1),
            ([(0, 0)], True), ([(10 ** 6 + 1, 0)], 0), ("ab", 1), ([None], 1), (((0, 0),), 1)):
    assert rej(R, *bad), bad
random.seed(9021)
for _ in range(400):
    n = random.randint(0, 40)
    lim = random.choice([3, 20, 10 ** 6])
    pts = [(random.randint(-lim, lim), random.randint(-lim, lim)) for _ in range(n)]
    if random.random() < 0.3 and n:
        pts = [pts[0]] * random.randint(1, 3) + pts
    eps = random.choice([0, 1, 2, 5, lim // 3])
    assert R(pts, eps) == oracle(pts, eps), (pts, eps)
pts = [(i, (i * i) % 7) for i in range(500)]
assert R(pts, 2) == oracle(pts, 2)
''', r'''
LIM = 10 ** 6


def _pt(p):
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise ValueError("a point is a pair")
    for v in p:
        if not isinstance(v, int) or isinstance(v, bool) or abs(v) > LIM:
            raise ValueError("bad coordinate")
    return (p[0], p[1])


def _dist2(p, a, b):
    """Squared distance from p to segment ab as a (num, den) pair with den > 0."""
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = p[0] - a[0], p[1] - a[1]
    vv = vx * vx + vy * vy
    dot = wx * vx + wy * vy
    if vv == 0 or dot <= 0:
        return wx * wx + wy * wy, 1
    if dot >= vv:
        return (p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2, 1
    cross = wx * vy - wy * vx
    return cross * cross, vv


def rdp_simplify(points, eps):
    if not isinstance(points, list) or len(points) > 500:
        raise ValueError("points must be a list of at most 500 points")
    if not isinstance(eps, int) or isinstance(eps, bool) or eps < 0:
        raise ValueError("eps must be an int >= 0")
    pts = [_pt(p) for p in points]
    if len(pts) < 3:
        return pts
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        best, bn, bd = None, -1, 1
        for k in range(i + 1, j):
            n, d = _dist2(pts[k], pts[i], pts[j])
            if n * bd > bn * d:
                best, bn, bd = k, n, d
        if bn > eps * eps * bd:
            keep.add(best)
            stack += [(i, best), (best, j)]
    return [pts[k] for k in sorted(keep)]
''')

task("v9_22_polar_order", "graphs_geometry", r'''
Write `polar_sort(points, origin)` and `count_directions(points, origin)` that order integer points by angle around an
origin, using exact integer arithmetic.

Arguments: `points` is a list of points and `origin` one point; a point is a tuple or list of two ints with absolute
value at most 10**6 (a bool is not an int). Anything else raises ValueError.

The angle of a point P != origin is the direction of the vector P - origin, measured counterclockwise from the
positive x-axis, in [0, 360) degrees: (1, 0) has angle 0, (0, 1) has 90, (-1, 0) has 180, (0, -1) has 270, and
(1, -1) has 315, so it comes last.

polar_sort(points, origin): return all the points as (x, y) tuples, sorted as follows. Points equal to the origin come
first. The others are sorted by angle ascending, and points with exactly the same angle (on the same ray from the
origin) by squared distance from the origin ascending. Equal points stay together. Compare angles exactly: split the
plane into two halves (angle in [0, 180) and in [180, 360)), and inside a half compare two vectors u and v by the sign
of the cross product u.x * v.y - u.y * v.x. Never use atan2 or floats.

count_directions(points, origin): return the number of distinct angles among the points that differ from the origin.
Two points have the same angle exactly when their vectors are positive multiples of each other.

Examples:
- polar_sort([(1, -1), (0, 1), (2, 0), (1, 0), (0, 0), (-1, 0)], (0, 0)) ==
  [(0, 0), (1, 0), (2, 0), (0, 1), (-1, 0), (1, -1)]
- polar_sort([(5, 5), (6, 6), (4, 6)], (5, 5)) == [(5, 5), (6, 6), (4, 6)]
- count_directions([(1, 1), (2, 2), (-1, -1), (0, 0), (3, 1)], (0, 0)) == 3
- polar_sort([], (0, 0)) == [] and count_directions([], (7, 7)) == 0
- ValueError: polar_sort([(1, 2.0)], (0, 0)), polar_sort([(1, 2)], (0,)), polar_sort([(True, 1)], (0, 0)),
  count_directions([(10 ** 6 + 1, 0)], (0, 0)), count_directions((1, 2), (0, 0))
''', REJ + r'''
import math, random

PS, CD = polar_sort, count_directions

def okey(p, o):
    dx, dy = p[0] - o[0], p[1] - o[1]
    if dx == 0 and dy == 0:
        return (0, 0.0, 0)
    g = math.gcd(dx, dy)
    a = math.atan2(dy // g, dx // g)
    if a < 0:
        a += 2 * math.pi
    return (1, a, dx * dx + dy * dy)

def odirs(pts, o):
    out = set()
    for p in pts:
        dx, dy = p[0] - o[0], p[1] - o[1]
        if dx or dy:
            g = math.gcd(dx, dy)
            out.add((dx // g, dy // g))
    return len(out)

assert PS([(1, -1), (0, 1), (2, 0), (1, 0), (0, 0), (-1, 0)], (0, 0)) == [(0, 0), (1, 0), (2, 0), (0, 1), (-1, 0), (1, -1)]
assert PS([(5, 5), (6, 6), (4, 6)], (5, 5)) == [(5, 5), (6, 6), (4, 6)] and PS([], (0, 0)) == [] and CD([], (7, 7)) == 0
assert CD([(1, 1), (2, 2), (-1, -1), (0, 0), (3, 1)], (0, 0)) == 3 and PS([[0, -1], [0, 1]], [0, 0]) == [(0, 1), (0, -1)]
assert PS([(-1, -1), (-1, 0), (-1, 1)], (0, 0)) == [(-1, 1), (-1, 0), (-1, -1)]
assert PS([(10 ** 6, -1), (10 ** 6, 0), (-10 ** 6, 1), (-10 ** 6, 0)], (0, 0)) == [(10 ** 6, 0), (-10 ** 6, 1), (-10 ** 6, 0), (10 ** 6, -1)]
for bad in (([(1, 2.0)], (0, 0)), ([(1, 2)], (0,)), ([(True, 1)], (0, 0)), ([(10 ** 6 + 1, 0)], (0, 0)), ((1, 2), (0, 0)),
            ([(1, 2)], None), ([None], (0, 0)), ([(1, 2)], (0, False)), ([(1, 2, 3)], (0, 0)), ("ab", (0, 0))):
    assert rej(PS, *bad) and rej(CD, *bad), bad
random.seed(9022)
for _ in range(700):
    lim = random.choice([2, 6, 50])
    o = (random.randint(-lim, lim), random.randint(-lim, lim))
    pts = [(random.randint(-lim, lim), random.randint(-lim, lim)) for _ in range(random.randrange(30))]
    pts += [o] * random.randrange(2)
    got = PS(pts, o)
    assert got == sorted((tuple(p) for p in pts), key=lambda p: okey(p, o)), (pts, o)
    assert CD(pts, o) == odirs(pts, o), (pts, o)
''', r'''
from functools import cmp_to_key

LIM = 10 ** 6


def _pt(p):
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise ValueError("a point is a pair")
    for v in p:
        if not isinstance(v, int) or isinstance(v, bool) or abs(v) > LIM:
            raise ValueError("bad coordinate")
    return (p[0], p[1])


def _prep(points, origin):
    if not isinstance(points, list):
        raise ValueError("points must be a list")
    o = _pt(origin)
    return [_pt(p) for p in points], o


def _half(v):
    return 0 if v[1] > 0 or (v[1] == 0 and v[0] > 0) else 1


def _cmp_dir(u, v):
    hu, hv = _half(u), _half(v)
    if hu != hv:
        return hu - hv
    c = u[0] * v[1] - u[1] * v[0]
    return -1 if c > 0 else (1 if c < 0 else 0)


def polar_sort(points, origin):
    pts, o = _prep(points, origin)
    at = [p for p in pts if p == o]
    rest = [p for p in pts if p != o]

    def cmp(p, q):
        u, v = (p[0] - o[0], p[1] - o[1]), (q[0] - o[0], q[1] - o[1])
        c = _cmp_dir(u, v)
        if c:
            return c
        du, dv = u[0] ** 2 + u[1] ** 2, v[0] ** 2 + v[1] ** 2
        return (du > dv) - (du < dv)

    return at + sorted(rest, key=cmp_to_key(cmp))


def count_directions(points, origin):
    srt = [p for p in polar_sort(points, origin) if p != _pt(origin)]
    o = _pt(origin)
    n = 0
    for i, p in enumerate(srt):
        if i == 0 or _cmp_dir((srt[i - 1][0] - o[0], srt[i - 1][1] - o[1]), (p[0] - o[0], p[1] - o[1])) != 0:
            n += 1
    return n
''')

# --- simulation_dp ---

task("v9_23_egg_drop", "simulation_dp", r'''
Write `min_drops(eggs, floors)` and `first_drop(eggs, floors)` for the egg-drop puzzle.

A building has floors 1 to `floors`. There is an unknown threshold h from 0 to `floors`: an egg dropped from floor x
breaks exactly when x > h. A broken egg is gone; an unbroken egg can be reused. You have `eggs` identical eggs and must
determine h exactly. A strategy chooses each next floor from the results so far.

min_drops(eggs, floors): `eggs` must be an int from 1 to 64 and `floors` an int from 0 to 10**18 (a bool is not an
int), otherwise raise ValueError. Return the smallest number of drops that suffices in the worst case.

first_drop(eggs, floors): same rules, but `floors` must be at least 1. Among all floors x that can start an optimal
strategy (one that never needs more than min_drops(eggs, floors) drops), return the highest.

Hint: with t drops and e eggs you can resolve at most f(t, e) floors, where f(t, e) = f(t-1, e-1) + 1 + f(t-1, e),
f(0, e) = 0 and f(t, 0) = 0; equivalently f(t, e) = C(t, 1) + C(t, 2) + ... + C(t, e). A first drop from x is optimal
with t drops exactly when x - 1 <= f(t-1, e-1) and floors - x <= f(t-1, e). With one egg the answer can be 10**18, so
search for t instead of counting up one at a time, and stop summing binomials once the sum passes `floors`.

Examples:
- min_drops(2, 100) == 14 and first_drop(2, 100) == 14
- min_drops(1, 10) == 10 and first_drop(1, 10) == 1
- min_drops(3, 0) == 0 and min_drops(2, 1) == 1 and first_drop(2, 1) == 1
- min_drops(2, 6) == 3 and first_drop(2, 6) == 3 and first_drop(3, 7) == 4
- min_drops(64, 10 ** 18) == 60 and min_drops(1, 10 ** 18) == 10 ** 18
- ValueError: min_drops(0, 10), min_drops(65, 10), min_drops(2, -1), min_drops(2, 10 ** 18 + 1), min_drops(True, 5),
  first_drop(2, 0), first_drop(2, 5.0)
''', REJ + r'''
import math, random

MD, FD = min_drops, first_drop
NMAX, EMAX = 70, 4
T = [[0] * (NMAX + 1) for _ in range(EMAX + 1)]
for e in range(1, EMAX + 1):
    for n in range(1, NMAX + 1):
        T[e][n] = n if e == 1 else min(1 + max(T[e - 1][x - 1], T[e][n - x]) for x in range(1, n + 1))

def ofirst(e, n):
    return max(x for x in range(1, n + 1) if 1 + max(T[e - 1][x - 1], T[e][n - x]) == T[e][n])

assert MD(2, 100) == 14 and FD(2, 100) == 14 and MD(1, 10) == 10 and FD(1, 10) == 1 and MD(3, 0) == 0
assert MD(2, 1) == 1 and FD(2, 1) == 1 and MD(2, 6) == 3 and FD(2, 6) == 3 and FD(3, 7) == 4
assert MD(64, 10 ** 18) == 60 and MD(1, 10 ** 18) == 10 ** 18 and FD(1, 10 ** 18) == 1 and MD(60, 10 ** 18) == 60
assert MD(64, 2 ** 59 - 1) == 59 and MD(64, 2 ** 59) == 60 and FD(64, 10 ** 18) == 2 ** 59
t = math.isqrt(2 * 10 ** 18)
while t * (t + 1) // 2 < 10 ** 18:
    t += 1
while (t - 1) * t // 2 >= 10 ** 18:
    t -= 1
assert MD(2, 10 ** 18) == t and FD(2, 10 ** 18) == t
for bad in ((0, 10), (65, 10), (2, -1), (2, 10 ** 18 + 1), (True, 5), (2, False), (2.0, 5), ("2", 5)):
    assert rej(MD, *bad) and rej(FD, *bad), bad
assert rej(FD, 2, 0) and rej(FD, 2, 5.0)
random.seed(9023)
for _ in range(200):
    e, n = random.randint(1, EMAX), random.randint(0, NMAX)
    assert MD(e, n) == T[e][n], (e, n)
    if n:
        assert FD(e, n) == ofirst(e, n), (e, n)
for _ in range(100):
    e, n = random.randint(5, 64), random.randint(0, 10 ** 18)
    t = MD(e, n)
    f = lambda t: sum(math.comb(t, i) for i in range(1, e + 1))
    assert f(t) >= n and (t == 0 or f(t - 1) < n), (e, n)
''', r'''
def _check(eggs, floors, lo):
    for v, a, b in ((eggs, 1, 64), (floors, lo, 10 ** 18)):
        if not isinstance(v, int) or isinstance(v, bool) or not a <= v <= b:
            raise ValueError("argument out of range")


def _cover(t, e, cap):
    total, c = 0, 1
    for i in range(1, min(t, e) + 1):
        c = c * (t - i + 1) // i
        total += c
        if total > cap:
            break
    return total


def _min(eggs, floors):
    lo, hi = 0, floors
    while lo < hi:
        mid = (lo + hi) // 2
        if _cover(mid, eggs, floors) >= floors:
            hi = mid
        else:
            lo = mid + 1
    return lo


def min_drops(eggs, floors):
    _check(eggs, floors, 0)
    return _min(eggs, floors)


def first_drop(eggs, floors):
    _check(eggs, floors, 1)
    t = _min(eggs, floors)
    return min(floors, _cover(t - 1, eggs - 1, floors) + 1)
''')

task("v9_24_interleave_count", "simulation_dp", r'''
Write `interleave_count(a, b, c)` and `interleave_labels(a, b, c)`.

A string c is an interleaving of a and b when the positions of c can be split into two sets, one of size len(a) whose
characters read left to right give a, and the rest, whose characters read left to right give b. Two interleavings
are different when the sets differ, even if the strings look alike: with a = b = "x" and c = "xx" there are two.

Arguments: `a`, `b` and `c` must be strs, with len(a) <= 300 and len(b) <= 300 (c may have any length); otherwise
raise ValueError.

interleave_count(a, b, c): return the number of different interleavings of a and b that equal c, as an exact int (it
can have well over 100 digits; do not reduce it modulo anything). If len(c) != len(a) + len(b) the answer is 0.

interleave_labels(a, b, c): describe one interleaving as a str of len(c) labels, where label i is "A" if position i
of c comes from a and "B" if it comes from b. Return the lexicographically smallest such str ("A" < "B"), or None if c
is not an interleaving of a and b.

Use dynamic programming over (i, j) = how many characters of a and of b have been used; the answer for a prefix of c
of length i + j depends only on the answers for (i - 1, j) and (i, j - 1). Trying every split of the positions is far
too slow. For the labels, first compute which (i, j) can still complete the rest of c, then choose greedily from the
start.

Examples:
- interleave_count("ab", "cd", "acbd") == 1 and interleave_labels("ab", "cd", "acbd") == "ABAB"
- interleave_count("x", "x", "xx") == 2 and interleave_labels("x", "x", "xx") == "AB"
- interleave_count("ab", "ab", "abab") == 2 and interleave_labels("ab", "ab", "abab") == "AABB"
- interleave_count("ab", "ba", "abba") == 2 and interleave_labels("ab", "ba", "baab") == "BABA"
- interleave_count("a", "b", "abc") == 0 and interleave_labels("a", "b", "ba") == "BA"
- interleave_count("", "", "") == 1 and interleave_labels("", "", "") == "" and interleave_labels("a", "", "b") is None
- ValueError: interleave_count("a" * 301, "", ""), interleave_count(["a"], "b", "ab"), interleave_labels("a", None, "a")
''', REJ + r'''
import itertools, math, random

IC, IL = interleave_count, interleave_labels

def brute(a, b, c):
    if len(c) != len(a) + len(b):
        return 0, None
    n, best, cnt = len(c), None, 0
    for S in itertools.combinations(range(n), len(a)):
        s = set(S)
        if "".join(c[i] for i in S) == a and "".join(c[i] for i in range(n) if i not in s) == b:
            cnt += 1
            lab = "".join("A" if i in s else "B" for i in range(n))
            best = lab if best is None or lab < best else best
    return cnt, best

assert IC("ab", "cd", "acbd") == 1 and IL("ab", "cd", "acbd") == "ABAB" and IC("x", "x", "xx") == 2 and IL("x", "x", "xx") == "AB"
assert IC("ab", "ab", "abab") == 2 and IL("ab", "ab", "abab") == "AABB" and IC("ab", "ba", "abba") == 2
assert IL("ab", "ba", "baab") == "BABA" and IC("a", "b", "abc") == 0 and IL("a", "b", "ba") == "BA"
assert IC("", "", "") == 1 and IL("", "", "") == "" and IL("a", "", "b") is None and IL("a", "b", "abc") is None
assert IC("a" * 300, "a" * 300, "a" * 600) == math.comb(600, 300)
assert IL("a" * 300, "a" * 300, "a" * 600) == "A" * 300 + "B" * 300
assert IL("b" * 300, "a" * 299 + "b", "a" * 299 + "b" * 301) == "B" * 299 + "A" * 300 + "B"
for bad in (("a" * 301, "", ""), (["a"], "b", "ab"), ("a", None, "a"), ("", "b" * 301, "b"), ("a", "b", b"ab")):
    assert rej(IC, *bad) and rej(IL, *bad), bad
random.seed(9024)
for _ in range(600):
    a = "".join(random.choice("ab") for _ in range(random.randint(0, 5)))
    b = "".join(random.choice("ab") for _ in range(random.randint(0, 5)))
    if random.random() < 0.7:
        pos = sorted(random.sample(range(len(a) + len(b)), len(a)))
        it_a, it_b = iter(a), iter(b)
        c = "".join(next(it_a) if i in pos else next(it_b) for i in range(len(a) + len(b)))
    else:
        c = "".join(random.choice("ab") for _ in range(random.randint(0, 9)))
    cnt, lab = brute(a, b, c)
    assert IC(a, b, c) == cnt and IL(a, b, c) == lab, (a, b, c)
''', r'''
def _check(a, b, c):
    if not all(isinstance(s, str) for s in (a, b, c)) or len(a) > 300 or len(b) > 300:
        raise ValueError("a, b, c must be str with len(a), len(b) <= 300")


def interleave_count(a, b, c):
    _check(a, b, c)
    n, m = len(a), len(b)
    if len(c) != n + m:
        return 0
    row = [0] * (m + 1)
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                row[0] = 1
                continue
            v = row[j] if i and a[i - 1] == c[i + j - 1] else 0
            if j and b[j - 1] == c[i + j - 1]:
                v += row[j - 1]
            row[j] = v
    return row[m]


def interleave_labels(a, b, c):
    _check(a, b, c)
    n, m = len(a), len(b)
    if len(c) != n + m:
        return None
    ok = [[False] * (m + 1) for _ in range(n + 1)]
    ok[n][m] = True
    for i in range(n, -1, -1):
        for j in range(m, -1, -1):
            if (i, j) == (n, m):
                continue
            k = i + j
            ok[i][j] = (i < n and a[i] == c[k] and ok[i + 1][j]) or (j < m and b[j] == c[k] and ok[i][j + 1])
    if not ok[0][0]:
        return None
    out, i, j = [], 0, 0
    while i + j < n + m:
        if i < n and a[i] == c[i + j] and ok[i + 1][j]:
            out.append("A")
            i += 1
        else:
            out.append("B")
            j += 1
    return "".join(out)
''')

task("v9_25_turmite_walk", "simulation_dp", r'''
Write `ant_walk(rule, steps)` and `ant_grid(rule, steps)` that simulate a generalized Langton's ant on an infinite
square grid.

`rule` must be a str of 2 to 12 characters, each "L" or "R"; `steps` must be an int from 0 to 10**5 (a bool is not an
int). Anything else raises ValueError. With k = len(rule), every cell has a color from 0 to k-1; all cells start at
color 0. The ant starts on cell (0, 0) facing north. North is +y, east is +x, south is -y, west is -x.

One step, with c the color of the ant's current cell:
1. turn 90 degrees: to the left (counterclockwise) if rule[c] == "L", to the right (clockwise) if rule[c] == "R";
2. set the current cell's color to (c + 1) % k;
3. move forward one cell in the new direction.

ant_walk(rule, steps): run `steps` steps and return (x, y, heading, colored): the ant's cell, its heading as one of
"N", "E", "S", "W", and the number of cells whose color is not 0.

ant_grid(rule, steps): run `steps` steps and return a picture of the colors as a list of strs: the smallest rectangle
that contains every cell whose color is not 0 (the ant's own position does not count). The first str is the row with
the largest y; within a row, x increases from left to right. Each cell is written as one character of
"0123456789ab" (its color). If no cell has a nonzero color, return [].

Examples:
- ant_walk("RL", 0) == (0, 0, "N", 0) and ant_walk("RL", 1) == (1, 0, "E", 1)
- ant_walk("RL", 2) == (1, -1, "S", 2) and ant_walk("RL", 5) == (-1, 0, "W", 3)
- ant_grid("RL", 4) == ["11", "11"] and ant_grid("RL", 0) == [] and ant_grid("LLRR", 1) == ["1"]
- ant_walk("LR", 1) == (-1, 0, "W", 1)
- ValueError: ant_walk("R", 5), ant_walk("RX", 5), ant_walk("rl", 5), ant_walk("RL", -1), ant_walk("RL", 10 ** 5 + 1),
  ant_walk("RL", True), ant_grid("L" * 13, 1)
''', REJ + r'''
import random

W, G = ant_walk, ant_grid
HEAD = {1j: "N", 1: "E", -1j: "S", -1: "W"}

def osim(rule, steps):
    cells, pos, d = {}, 0j, 1j
    for _ in range(steps):
        c = cells.get(pos, 0)
        d = d * (1j if rule[c] == "L" else -1j)
        cells[pos] = (c + 1) % len(rule)
        pos += d
    live = {p: v for p, v in cells.items() if v}
    if live:
        xs = [int(p.real) for p in live]
        ys = [int(p.imag) for p in live]
        pic = ["".join("0123456789ab"[live.get(complex(x, y), 0)] for x in range(min(xs), max(xs) + 1))
               for y in range(max(ys), min(ys) - 1, -1)]
    else:
        pic = []
    return (int(pos.real), int(pos.imag), HEAD[d], len(live)), pic

assert W("RL", 0) == (0, 0, "N", 0) and W("RL", 1) == (1, 0, "E", 1) and W("RL", 2) == (1, -1, "S", 2)
assert W("RL", 5) == (-1, 0, "W", 3) and G("RL", 4) == ["11", "11"] and G("RL", 0) == [] and G("LLRR", 1) == ["1"]
assert W("LR", 1) == (-1, 0, "W", 1) and W("RL", 4) == (0, 0, "N", 4)
assert G("RR", 4) == ["00"] * 0 + G("RR", 4) and G("RR", 4) == osim("RR", 4)[1]
for bad in (("R", 5), ("RX", 5), ("rl", 5), ("RL", -1), ("RL", 10 ** 5 + 1), ("RL", True), ("L" * 13, 1), (["R", "L"], 1),
            ("RL", 2.0), (None, 1)):
    assert rej(W, *bad) and rej(G, *bad), bad
w, g = osim("RL", 11000)
assert W("RL", 11000) == w and G("RL", 11000) == g
random.seed(9025)
for _ in range(40):
    rule = "".join(random.choice("LR") for _ in range(random.randint(2, 12)))
    steps = random.choice([random.randint(0, 30), random.randint(0, 1500)])
    w, g = osim(rule, steps)
    assert W(rule, steps) == w and G(rule, steps) == g, (rule, steps)
''', r'''
DX, DY, NAMES = (0, 1, 0, -1), (1, 0, -1, 0), "NESW"
DIGITS = "0123456789ab"


def _run(rule, steps):
    if not isinstance(rule, str) or not 2 <= len(rule) <= 12 or set(rule) - {"L", "R"}:
        raise ValueError("rule must be 2 to 12 characters L or R")
    if not isinstance(steps, int) or isinstance(steps, bool) or not 0 <= steps <= 10 ** 5:
        raise ValueError("steps must be an int from 0 to 10**5")
    k, grid, x, y, d = len(rule), {}, 0, 0, 0
    for _ in range(steps):
        c = grid.get((x, y), 0)
        d = (d + (1 if rule[c] == "R" else 3)) % 4
        nc = (c + 1) % k
        if nc:
            grid[(x, y)] = nc
        else:
            grid.pop((x, y), None)
        x, y = x + DX[d], y + DY[d]
    return x, y, d, grid


def ant_walk(rule, steps):
    x, y, d, grid = _run(rule, steps)
    return (x, y, NAMES[d], len(grid))


def ant_grid(rule, steps):
    _, _, _, grid = _run(rule, steps)
    if not grid:
        return []
    xs = [p[0] for p in grid]
    ys = [p[1] for p in grid]
    return ["".join(DIGITS[grid.get((x, y), 0)] for x in range(min(xs), max(xs) + 1))
            for y in range(max(ys), min(ys) - 1, -1)]
''')

task("v9_26_sandpile_topple", "simulation_dp", r'''
Write `topple(grid)` that stabilizes an abelian sandpile and counts the topplings.

`grid` must be a non-empty list of 1 to 20 rows, each a list of the same length from 1 to 20, holding ints from 0 to
10**4 (a bool is not an int); anything else raises ValueError. Each number is a pile of grains on that cell.

A cell with 4 or more grains is unstable and may topple: it loses 4 grains and each of its up to four orthogonal
neighbours gains 1. Grains sent off the edge of the grid are lost. Toppling continues until every cell has at most 3
grains. The final grid and the total number of topplings do not depend on the order in which unstable cells are
toppled (that is what "abelian" means), so you may topple a cell with g grains floor(g / 4) times at once; that
counts as floor(g / 4) topplings.

Return a tuple (stable, count): `stable` a new list of lists with the final grains, and `count` the total number of
single topplings. Do not modify the input.

A cell can be toppled many times: 10**4 grains on the centre cell of a 20 x 20 grid need about 300000 single
topplings, so toppling 4 grains at a time per scan over the whole grid is too slow; keep a work list of cells that
may be unstable and topple each popped cell in one batch.

Examples:
- topple([[4]]) == ([[0]], 1) and topple([[16]]) == ([[0]], 4) and topple([[3, 3], [3, 3]]) == ([[3, 3], [3, 3]], 0)
- topple([[0, 4, 0]]) == ([[1, 0, 1]], 1)
- topple([[0, 0, 0], [0, 4, 0], [0, 0, 0]]) == ([[0, 1, 0], [1, 0, 1], [0, 1, 0]], 1)
- topple([[4, 4]]) == ([[1, 1]], 2)
- topple([[0, 0, 0], [0, 16, 0], [0, 0, 0]]) == ([[2, 1, 2], [1, 0, 1], [2, 1, 2]], 9)
- ValueError: topple([]), topple([[]]), topple([[1, 2], [3]]), topple([[-1]]), topple([[10 ** 4 + 1]]),
  topple([[True]]), topple([[1.0]]), topple([(1, 2)])
''', REJ + r'''
import copy, random

TP = topple

def oracle(grid):
    g = [row[:] for row in grid]
    h, w, n = len(g), len(g[0]), 0
    while True:
        cell = next(((r, c) for r in range(h) for c in range(w) if g[r][c] >= 4), None)
        if cell is None:
            return g, n
        r, c = cell
        g[r][c] -= 4
        n += 1
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= rr < h and 0 <= cc < w:
                g[rr][cc] += 1

assert TP([[4]]) == ([[0]], 1) and TP([[16]]) == ([[0]], 4) and TP([[3, 3], [3, 3]]) == ([[3, 3], [3, 3]], 0)
assert TP([[0, 4, 0]]) == ([[1, 0, 1]], 1) and TP([[0, 0, 0], [0, 4, 0], [0, 0, 0]]) == ([[0, 1, 0], [1, 0, 1], [0, 1, 0]], 1)
assert TP([[4, 4]]) == ([[1, 1]], 2) and TP([[0, 0, 0], [0, 16, 0], [0, 0, 0]]) == ([[2, 1, 2], [1, 0, 1], [2, 1, 2]], 9)
src = [[5, 0], [0, 9]]
keep = copy.deepcopy(src)
out = TP(src)
assert src == keep and out[0] is not src
for bad in ([], [[]], [[1, 2], [3]], [[-1]], [[10 ** 4 + 1]], [[True]], [[1.0]], [(1, 2)], [[0] * 21], [[0]] * 21,
            None, [[1], None], "1"):
    assert rej(TP, bad), bad
random.seed(9026)
for _ in range(150):
    h, w = random.randint(1, 5), random.randint(1, 5)
    g = [[random.choice([0, 1, 2, 3, 4, 5, 7, random.randint(0, 14)]) for _ in range(w)] for _ in range(h)]
    assert TP(g) == oracle(g), g
big = [[10 ** 4 if (r, c) == (9, 9) else 0 for c in range(19)] for r in range(19)]
st, cnt = TP(big)
assert all(0 <= v <= 3 for row in st for v in row) and st == [row[::-1] for row in st] and st == st[::-1]
assert st == [list(x) for x in zip(*st)] and cnt > 10 ** 5
st3, cnt3 = TP([[40] * 20 for _ in range(20)])
assert all(0 <= v <= 3 for row in st3 for v in row) and st3 == [row[::-1] for row in st3] and st3 == st3[::-1]
st2, cnt2 = TP([[10 ** 4 if (r, c) == (0, 0) else 0 for c in range(12)] for r in range(12)])
assert all(v <= 3 for row in st2 for v in row) and st2 == [list(x) for x in zip(*st2)]
mid = [[0] * 7 for _ in range(7)]
mid[3][3] = 60
assert TP(mid) == oracle(mid)
''', r'''
def topple(grid):
    if not isinstance(grid, list) or not 1 <= len(grid) <= 20:
        raise ValueError("grid must have 1 to 20 rows")
    if not all(isinstance(r, list) for r in grid):
        raise ValueError("rows must be lists")
    w = len(grid[0])
    if not 1 <= w <= 20 or any(len(r) != w for r in grid):
        raise ValueError("rows must have the same length, 1 to 20")
    for r in grid:
        for v in r:
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 10 ** 4:
                raise ValueError("bad pile")
    h = len(grid)
    g = [list(r) for r in grid]
    work = [(r, c) for r in range(h) for c in range(w) if g[r][c] >= 4]
    count = 0
    while work:
        r, c = work.pop()
        q = g[r][c] // 4
        if not q:
            continue
        g[r][c] -= 4 * q
        count += q
        for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= rr < h and 0 <= cc < w:
                g[rr][cc] += q
                if g[rr][cc] >= 4:
                    work.append((rr, cc))
    return g, count
''')

task("v9_27_snake_game", "simulation_dp", r'''
Write `play_snake(height, width, food, moves)` that plays a game of Snake and reports how it went.

Arguments: `height` and `width` are ints from 1 to 50 (a bool is not an int). `food` is a list of cells, each a tuple
or list (row, col) of two ints with 0 <= row < height and 0 <= col < width. `moves` is a str of the letters "U", "D",
"L", "R". Anything else raises ValueError.

The board has rows 0 to height-1 (row 0 at the top) and columns 0 to width-1. The snake is a sequence of cells, head
first. It starts as the single cell (0, 0). Food appears one item at a time: food[0] is on the board from the start,
and food[i+1] appears at the moment food[i] is eaten. A food item may appear on a cell the snake occupies; it is eaten
only when the head moves onto it. After the last item is eaten there is no food.

Each move shifts the head one cell: "U" is row - 1, "D" row + 1, "L" col - 1, "R" col + 1. In order:
1. If the new head cell is off the board, the game ends.
2. If the new head cell holds the current food item, the snake grows: nothing is removed from its tail. Otherwise
   the last cell of the snake (its tail) is removed first.
3. If the new head cell is now occupied by the rest of the snake, the game ends.
4. Otherwise the head moves there; if food was eaten, the score goes up by 1 and the next food item appears.
Because the tail leaves first, the head may move into the cell the tail just left, and a snake of length 2 may turn
straight back.

Return (score, steps): the number of food items eaten and the number of moves completed. The move that ends the game
does not count, and no later move is played. If every move is played, the game simply stops.

Examples:
- play_snake(3, 3, [(0, 1), (1, 1)], "RDLU") == (2, 4)
- play_snake(3, 3, [(0, 1), (0, 2), (1, 2), (1, 1)], "RRDLU") == (4, 4) (the last move hits the body)
- play_snake(1, 3, [(0, 1)], "RL") == (1, 2) and play_snake(2, 2, [], "RDLU") == (0, 4)
- play_snake(2, 2, [], "U") == (0, 0) and play_snake(1, 1, [], "") == (0, 0)
- play_snake(1, 3, [(0, 1), (0, 2)], "RRLL") == (2, 2) (after eating twice, turning back hits the body)
- ValueError: play_snake(0, 3, [], ""), play_snake(3, 3, [(3, 0)], ""), play_snake(3, 3, [], "X"),
  play_snake(3, 3, [(0, True)], ""), play_snake(51, 3, [], ""), play_snake(3, 3, [(1,)], "")
''', REJ + r'''
import random

PS = play_snake
DELTA = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}

def oracle(h, w, food, moves):
    body, k, score = [(0, 0)], 0, 0
    for n, mv in enumerate(moves):
        r, c = body[0][0] + DELTA[mv][0], body[0][1] + DELTA[mv][1]
        if not (0 <= r < h and 0 <= c < w):
            return score, n
        eat = k < len(food) and (r, c) == tuple(food[k])
        rest = body if eat else body[:-1]
        if (r, c) in rest:
            return score, n
        body = [(r, c)] + rest
        if eat:
            score, k = score + 1, k + 1
    return score, len(moves)

assert PS(3, 3, [(0, 1), (1, 1)], "RDLU") == (2, 4) and PS(3, 3, [(0, 1), (0, 2), (1, 2), (1, 1)], "RRDLU") == (4, 4)
assert PS(1, 3, [(0, 1)], "RL") == (1, 2) and PS(2, 2, [], "RDLU") == (0, 4) and PS(2, 2, [], "U") == (0, 0)
assert PS(1, 1, [], "") == (0, 0) and PS(1, 3, [(0, 1), (0, 2)], "RRLL") == (2, 2) and PS(2, 2, [[0, 0]], "RDLU") == (1, 4)
assert PS(2, 2, [(0, 1), (1, 1), (1, 0)], "RDLU") == (3, 4) and PS(2, 3, [(0, 1), (0, 1)], "RLR") == (1, 2)
for bad in ((0, 3, [], ""), (3, 3, [(3, 0)], ""), (3, 3, [], "X"), (3, 3, [(0, True)], ""), (51, 3, [], ""),
            (3, 3, [(1,)], ""), (3, 3, [], "u"), (3, 3, None, ""), (3, 3, [], None), (True, 3, [], ""), (3, 3.0, [], ""),
            (3, 3, [(0, -1)], ""), (3, 3, [(0, 1, 2)], ""), (3, 3, ((0, 1),), "")):
    assert rej(PS, *bad), bad
random.seed(9027)
for _ in range(800):
    h, w = random.randint(1, 7), random.randint(1, 7)
    food = [(random.randrange(h), random.randrange(w)) for _ in range(random.randrange(12))]
    moves = "".join(random.choice("UDLR") for _ in range(random.randrange(40)))
    assert PS(h, w, food, moves) == oracle(h, w, food, moves), (h, w, food, moves)
food = [(0, c) for c in range(1, 50)] + [(r, 49) for r in range(1, 50)]
moves = "R" * 49 + "D" * 49 + "L" * 49
assert PS(50, 50, food, moves) == oracle(50, 50, food, moves)
''', r'''
from collections import deque

STEP = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}


def _int(v, lo, hi):
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def play_snake(height, width, food, moves):
    if not (_int(height, 1, 50) and _int(width, 1, 50)) or not isinstance(food, list) or not isinstance(moves, str):
        raise ValueError("bad arguments")
    cells = []
    for f in food:
        if not isinstance(f, (tuple, list)) or len(f) != 2 or not (_int(f[0], 0, height - 1) and _int(f[1], 0, width - 1)):
            raise ValueError("bad food cell")
        cells.append((f[0], f[1]))
    if any(m not in STEP for m in moves):
        raise ValueError("bad move")
    body = deque([(0, 0)])
    occupied = {(0, 0): 1}
    k = score = 0
    for n, m in enumerate(moves):
        r, c = body[0][0] + STEP[m][0], body[0][1] + STEP[m][1]
        if not (0 <= r < height and 0 <= c < width):
            return score, n
        eat = k < len(cells) and cells[k] == (r, c)
        if not eat:
            t = body.pop()
            occupied[t] -= 1
            if not occupied[t]:
                del occupied[t]
        if (r, c) in occupied:
            return score, n
        body.appendleft((r, c))
        occupied[(r, c)] = 1
        if eat:
            score += 1
            k += 1
    return score, len(moves)
''')

task("v9_28_tax_lots", "simulation_dp", r'''
Write `realize_gains(trades, method)` that matches sales against earlier purchases of one stock and reports the
realized gain and the lots still held.

`trades` is a list of trades in time order; each trade is a tuple or list of three items (kind, qty, price): kind is
"buy" or "sell", qty an int >= 1 and price an int >= 0 (a price in cents; a bool is never accepted as an int).
`method` is "fifo" or "lifo". Anything else raises ValueError, and so does a sale of more shares than are held at
that moment (the whole call fails; there is no partial result).

Every buy creates a lot (qty, price). Lots are never merged, even when two lots have the same price. A sale of q
shares at price p takes shares from the lots one lot at a time: with "fifo" from the oldest remaining lot first, with
"lifo" from the newest remaining lot first. Taking s shares from a lot bought at price b realizes a gain of
s * (p - b) (negative for a loss) and lowers that lot's quantity by s; a lot whose quantity reaches 0 disappears. A
sale may use part of a lot and leave the rest in place, in its original position.

Return a tuple (gain, lots): `gain` is the total realized gain over all sales, an int, and `lots` is a list of
(qty, price) tuples for the lots still held, oldest first (whatever the method).

Examples:
- realize_gains([("buy", 10, 100), ("buy", 5, 120), ("sell", 12, 130)], "fifo") == (320, [(3, 120)])
- realize_gains([("buy", 10, 100), ("buy", 5, 120), ("sell", 12, 130)], "lifo") == (260, [(3, 100)])
- realize_gains([("buy", 2, 50), ("sell", 1, 40), ("buy", 2, 50), ("sell", 2, 60)], "lifo") == (10, [(1, 50)])
- realize_gains([], "fifo") == (0, []) and realize_gains([["buy", 1, 0]], "lifo") == (0, [(1, 0)])
- ValueError: realize_gains([("sell", 1, 10)], "fifo"), realize_gains([("buy", 0, 10)], "fifo"),
  realize_gains([("buy", 1, -1)], "fifo"), realize_gains([("buy", 1, 10)], "FIFO"),
  realize_gains([("buy", True, 10)], "fifo"), realize_gains([("hold", 1, 10)], "fifo")
''', REJ + r'''
import random

RG = realize_gains

def oracle(trades, method):
    units, lot_of, gain, nxt = [], [], 0, 0
    for kind, q, p in trades:
        if kind == "buy":
            units += [(nxt, p)] * q
            nxt += 1
        else:
            for _ in range(q):
                lid, b = units.pop(0) if method == "fifo" else units.pop()
                gain += p - b
    out = []
    for lid, b in units:
        if out and out[-1][0] == lid:
            out[-1][1] += 1
        else:
            out.append([lid, 1, b])
    return gain, [(n, b) for lid, n, b in out]

assert RG([("buy", 10, 100), ("buy", 5, 120), ("sell", 12, 130)], "fifo") == (320, [(3, 120)])
assert RG([("buy", 10, 100), ("buy", 5, 120), ("sell", 12, 130)], "lifo") == (260, [(3, 100)])
assert RG([("buy", 2, 50), ("sell", 1, 40), ("buy", 2, 50), ("sell", 2, 60)], "lifo") == (10, [(1, 50)])
assert RG([], "fifo") == (0, []) and RG([["buy", 1, 0]], "lifo") == (0, [(1, 0)])
assert RG([("buy", 3, 5), ("buy", 3, 5), ("sell", 4, 5)], "fifo") == (0, [(2, 5)])
assert RG([("buy", 3, 5), ("buy", 3, 5), ("sell", 2, 5)], "fifo") == (0, [(1, 5), (3, 5)])
for bad in (([("sell", 1, 10)], "fifo"), ([("buy", 0, 10)], "fifo"), ([("buy", 1, -1)], "fifo"), ([("buy", 1, 10)], "FIFO"),
            ([("buy", True, 10)], "fifo"), ([("hold", 1, 10)], "fifo"), ([("buy", 1, 10), ("sell", 2, 10)], "lifo"),
            ([("buy", 1)], "fifo"), ([("buy", 1, 1.5)], "fifo"), (None, "fifo"), ([("buy", 1, 10)], None),
            ([("buy", 1, 10, 0)], "fifo"), ([("buy", 1, False)], "fifo")):
    assert rej(RG, *bad), bad
random.seed(9028)
for _ in range(1500):
    trades, held = [], 0
    for _ in range(random.randrange(14)):
        if held and random.random() < 0.45:
            q = random.randint(1, held + (1 if random.random() < 0.05 else 0))
            trades.append(("sell", q, random.randint(0, 200)))
            held -= q
            if held < 0:
                break
        else:
            q = random.randint(1, 6)
            trades.append(("buy", q, random.randint(0, 200)))
            held += q
    for method in ("fifo", "lifo"):
        if held < 0:
            assert rej(RG, trades, method)
        else:
            assert RG(trades, method) == oracle(trades, method), (trades, method)
''', r'''
def _int(v, lo):
    return isinstance(v, int) and not isinstance(v, bool) and v >= lo


def realize_gains(trades, method):
    if not isinstance(trades, list) or method not in ("fifo", "lifo"):
        raise ValueError("bad arguments")
    lots, gain = [], 0
    for t in trades:
        if not isinstance(t, (tuple, list)) or len(t) != 3:
            raise ValueError("a trade has three items")
        kind, qty, price = t
        if kind not in ("buy", "sell") or not _int(qty, 1) or not _int(price, 0):
            raise ValueError("bad trade %r" % (t,))
        if kind == "buy":
            lots.append([qty, price])
            continue
        if qty > sum(l[0] for l in lots):
            raise ValueError("selling more than is held")
        while qty:
            idx = 0 if method == "fifo" else len(lots) - 1
            lot = lots[idx]
            take = min(qty, lot[0])
            gain += take * (price - lot[1])
            lot[0] -= take
            qty -= take
            if lot[0] == 0:
                lots.pop(idx)
    return gain, [(q, p) for q, p in lots]
''')

task("v9_29_jump_reach", "simulation_dp", r'''
Write `min_jumps(lengths)` and `farthest_after(lengths, k)` for jumps along an array.

`lengths` must be a list of 1 to 10**5 ints, each >= 0 (a bool is not an int); otherwise raise ValueError. You start
at index 0. From index i you may jump to any index j with i < j <= i + lengths[i] (and j < len(lengths)); lengths[i]
= 0 means no jump is possible from i.

min_jumps(lengths): return the smallest number of jumps that reaches the last index, 0 if the list has one element,
or -1 if the last index cannot be reached.

farthest_after(lengths, k): `k` must be an int >= 0 (no bool; it may be huge, like 10**18), otherwise ValueError.
Return the largest index that can be reached from index 0 with at most k jumps.

The indices reachable with at most k jumps always form a prefix 0..R of the list, because a jump may stop short. So
both answers come from one left-to-right sweep that tracks the end of the current prefix and the farthest index the
next jump can reach from it; the whole computation must take O(n) steps, not O(n * max(lengths)) and not O(n * k).
Jumping as far as possible each time is NOT optimal: [2, 3, 1, 1, 4] needs 2 jumps (0 -> 1 -> 4), while always taking
the longest jump goes 0 -> 2 -> 3 -> 4.

Examples:
- min_jumps([2, 3, 1, 1, 4]) == 2 and min_jumps([3, 2, 1, 0, 4]) == -1 and min_jumps([0]) == 0
- min_jumps([1, 1, 1, 1]) == 3 and min_jumps([5, 0, 0]) == 1
- farthest_after([2, 3, 1, 1, 4], 0) == 0 and farthest_after([2, 3, 1, 1, 4], 1) == 2
- farthest_after([2, 3, 1, 1, 4], 2) == 4 and farthest_after([3, 2, 1, 0, 4], 10 ** 18) == 3
- farthest_after([0, 5], 3) == 0
- ValueError: min_jumps([]), min_jumps([-1]), min_jumps([True]), min_jumps((1, 2)), farthest_after([1], -1),
  farthest_after([1], True), farthest_after([1.0], 1)
''', REJ + r'''
import random

MJ, FA = min_jumps, farthest_after

def bfs(a):
    n, dist, q = len(a), {0: 0}, [0]
    for i in q:
        for j in range(i + 1, min(n, i + a[i] + 1)):
            if j not in dist:
                dist[j] = dist[i] + 1
                q.append(j)
    return dist

assert MJ([2, 3, 1, 1, 4]) == 2 and MJ([3, 2, 1, 0, 4]) == -1 and MJ([0]) == 0 and MJ([1, 1, 1, 1]) == 3 and MJ([5, 0, 0]) == 1
assert FA([2, 3, 1, 1, 4], 0) == 0 and FA([2, 3, 1, 1, 4], 1) == 2 and FA([2, 3, 1, 1, 4], 2) == 4
assert FA([3, 2, 1, 0, 4], 10 ** 18) == 3 and FA([0, 5], 3) == 0 and FA([9], 0) == 0 and FA([1, 1], 10 ** 18) == 1
assert MJ([0, 1]) == -1 and MJ([1, 0, 1]) == -1 and MJ([2, 0, 0]) == 1
for bad in ([], [-1], [True], (1, 2), None, [1, 2.0], [1, None], "12"):
    assert rej(MJ, bad) and rej(FA, bad, 1), bad
for bad in (-1, True, 1.0, None, "1"):
    assert rej(FA, [1], bad), bad
n = 10 ** 5
assert MJ([1] * n) == n - 1 and FA([1] * n, 12345) == 12345 and MJ([n] + [0] * (n - 1)) == 1
big = [10 ** 9] + [0] * (n - 1)
assert MJ(big) == 1 and FA(big, 1) == n - 1
random.seed(9029)
a = [random.randint(0, 3) for _ in range(n)]
a[0] = 3
d = bfs(a[:3000])
assert FA(a[:3000], 5) == max(i for i, v in d.items() if v <= 5)
for _ in range(1500):
    m = random.randint(1, 18)
    a = [random.choice([0, 0, 1, 1, 2, 3, 5]) for _ in range(m)]
    d = bfs(a)
    assert MJ(a) == d.get(m - 1, -1), a
    k = random.randint(0, m)
    assert FA(a, k) == max(i for i, v in d.items() if v <= k), (a, k)
''', r'''
def _check(lengths):
    if not isinstance(lengths, list) or not 1 <= len(lengths) <= 10 ** 5:
        raise ValueError("lengths must be a list of 1 to 10**5 ints")
    for v in lengths:
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError("bad length")


def _layers(lengths):
    """Yield the end of the reachable prefix after 1, 2, 3, ... jumps while it grows."""
    n, end, far, i = len(lengths), 0, 0, 0
    while True:
        while i <= end:
            far = max(far, i + lengths[i])
            i += 1
        new = min(far, n - 1)
        if new == end:
            return
        end = new
        yield end


def min_jumps(lengths):
    _check(lengths)
    n = len(lengths)
    if n == 1:
        return 0
    for jumps, end in enumerate(_layers(lengths), 1):
        if end == n - 1:
            return jumps
    return -1


def farthest_after(lengths, k):
    _check(lengths)
    if not isinstance(k, int) or isinstance(k, bool) or k < 0:
        raise ValueError("k must be an int >= 0")
    best = 0
    for jumps, end in enumerate(_layers(lengths), 1):
        if jumps > k:
            break
        best = end
    return best
''')

task("v9_30_dice_totals", "simulation_dp", r'''
Write `dice_counts(spec)` and `chance_at_least(spec, target)` for sums of dice written in the usual tabletop notation.

A spec is a str of 1 to 10 terms joined by "+" with no spaces. A term is either
- "NdS": N dice with S faces each (faces 1 to S, all equally likely), with N an int from 1 to 20 and S an int from 2 to
  100, both written in ASCII digits without leading zeros and with a lower-case "d"; or
- a constant: an int from 0 to 1000 written in ASCII digits without leading zeros ("0" itself is fine).
The total number of dice over all terms must be at most 20. Anything else raises ValueError: "2D6", "d6", "0d6", "2d1",
"21d6", "2d06", "2d6+", "+2d6", "2d6 + 1", "-1", "1001", "" and a spec with 11 terms are all invalid, and so is any
argument that is not a str.

dice_counts(spec): return a dict mapping every possible total to the number of equally likely outcomes (one face for
every die) that give it. Only totals with at least one outcome appear. The counts are exact ints and add up to the
product of all the S values.

chance_at_least(spec, target): `target` must be an int (a bool is not an int), otherwise ValueError. Return the exact
probability that the total is at least `target`, as a fractions.Fraction in lowest terms.

Build the distribution by adding one die at a time (a convolution); with 20 dice of 100 faces there are 100**20
outcomes, so never enumerate outcomes. Adding a die to a distribution over T totals takes O(T * S) steps, or O(T)
with a running window sum; either is fast enough here.

Examples:
- dice_counts("2d6")[7] == 6 and len(dice_counts("2d6")) == 11 and sum(dice_counts("2d6").values()) == 36
- dice_counts("1d4+2") == {3: 1, 4: 1, 5: 1, 6: 1} and dice_counts("5") == {5: 1} and dice_counts("0+0") == {0: 1}
- dice_counts("1d2+1d3") == {2: 1, 3: 2, 4: 2, 5: 1}
- chance_at_least("2d6", 10) == Fraction(1, 6) and chance_at_least("1d20+5", 26) == 0
- chance_at_least("3d6", 3) == 1 and chance_at_least("1d6", 4) == Fraction(1, 2)
- ValueError: dice_counts("2D6"), dice_counts("21d6"), dice_counts("11d6+10d6"), dice_counts("2d6+"),
  chance_at_least("2d6", 7.0), chance_at_least("2d6", True)
''', REJ + r'''
import itertools, math, random
from fractions import Fraction

DC, CA = dice_counts, chance_at_least

def brute(dice, const):
    out = {}
    for roll in itertools.product(*[range(1, s + 1) for s in dice]):
        t = sum(roll) + const
        out[t] = out.get(t, 0) + 1
    return out

assert DC("2d6")[7] == 6 and len(DC("2d6")) == 11 and sum(DC("2d6").values()) == 36
assert DC("1d4+2") == {3: 1, 4: 1, 5: 1, 6: 1} and DC("5") == {5: 1} and DC("0+0") == {0: 1}
assert DC("1d2+1d3") == {2: 1, 3: 2, 4: 2, 5: 1} and DC("1000+1000") == {2000: 1}
assert CA("2d6", 10) == Fraction(1, 6) and CA("1d20+5", 26) == 0 and CA("3d6", 3) == 1 and CA("1d6", 4) == Fraction(1, 2)
assert isinstance(CA("1d6", 4), Fraction) and CA("1d6", -50) == 1 and CA("2d2", 4) == Fraction(1, 4)
big = DC("20d100")
assert sum(big.values()) == 100 ** 20 and big[20] == 1 and big[21] == 20 and big[2000] == 1 and big[1010] == max(big.values())
assert big[1009] == big[1011] and len(big) == 1981
assert CA("10d100+10d100", 1011) == Fraction(sum(v for t, v in big.items() if t >= 1011), 100 ** 20)
for bad in ("2D6", "d6", "0d6", "2d1", "21d6", "2d06", "2d6+", "+2d6", "2d6 + 1", "-1", "1001", "", "+".join(["1"] * 11),
            "11d6+10d6", "01", "2d101", "2dd6", "2d6d6", "1d6++1", "２d6", None, 5, ["2d6"], "2d6\n", "1e3"):
    assert rej(DC, bad) and rej(CA, bad, 1), bad
for bad in (7.0, True, "7", None):
    assert rej(CA, "2d6", bad), bad
random.seed(9030)
for _ in range(250):
    terms, dice, const = [], [], 0
    for _ in range(random.randint(1, 4)):
        if random.random() < 0.7 and len(dice) < 4:
            nd, s = random.randint(1, 2), random.randint(2, 7)
            terms.append(f"{nd}d{s}")
            dice += [s] * nd
        else:
            v = random.choice([0, 1, 7, random.randint(0, 1000)])
            terms.append(str(v))
            const += v
    want = brute(dice, const)
    assert DC("+".join(terms)) == want, terms
    tgt = random.randint(min(want) - 2, max(want) + 2)
    assert CA("+".join(terms), tgt) == Fraction(sum(v for t, v in want.items() if t >= tgt), sum(want.values())), terms
''', r'''
import re
from fractions import Fraction

TERM = re.compile(r"([1-9][0-9]*)d([1-9][0-9]*)|(0|[1-9][0-9]*)")


def _parse(spec):
    if not isinstance(spec, str):
        raise ValueError("spec must be a str")
    terms = spec.split("+")
    if not 1 <= len(terms) <= 10:
        raise ValueError("1 to 10 terms")
    dice, const = [], 0
    for t in terms:
        m = TERM.fullmatch(t) if t.isascii() else None
        if not m:
            raise ValueError("bad term %r" % t)
        if m.group(3) is not None:
            v = int(m.group(3))
            if v > 1000:
                raise ValueError("constant above 1000")
            const += v
        else:
            n, s = int(m.group(1)), int(m.group(2))
            if not (1 <= n <= 20 and 2 <= s <= 100):
                raise ValueError("bad dice term %r" % t)
            dice += [s] * n
    if len(dice) > 20:
        raise ValueError("more than 20 dice")
    return dice, const


def dice_counts(spec):
    dice, const = _parse(spec)
    dist, lo = [1], const
    for s in dice:
        new = [0] * (len(dist) + s - 1)
        window = 0
        for i in range(len(new)):
            if i < len(dist):
                window += dist[i]
            if i - s >= 0:
                window -= dist[i - s]
            new[i] = window
        dist, lo = new, lo + 1
    return {lo + i: v for i, v in enumerate(dist) if v}


def chance_at_least(spec, target):
    counts = dice_counts(spec)
    if not isinstance(target, int) or isinstance(target, bool):
        raise ValueError("target must be an int")
    total = sum(counts.values())
    return Fraction(sum(v for t, v in counts.items() if t >= target), total)
''')


TASKS = T
