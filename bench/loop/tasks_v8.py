"""loop-v8: held-out Python tasks for the CRAwDAD retrieval test (README "v8 tasks" section).

Same layout as tasks_v7.py: id, prompt, tests, ref. Written 2026-10-19 inline in one session (no subagents), every
check run under prlimit --as=4294967296. Families are v7's four writing buckets, because retrieve() reads one family of
the v7 corpus: formats v8_01-08, number_theory v8_09-15, graphs_geometry v8_16-22, simulation_dp v8_23-30 (memring
FAMILIES["v8"]). Style is v7_11-30's: one or two functions, about six rules each with an example, validation of a type
and a range, at most one stated size, the algorithm named when one is needed, references of at most about 40 lines.
New problems: no task is a near-copy of a v7 task (the corpus), so a retrieved module is never already the answer.
v8 never enters the corpus. Sealed held-out set: nobody iterates a prompt, a loop or a design on these tasks. Every
test file has exactly one random.seed(N) line, N = 8000 + task number. Seeded random cases are checked against an
oracle built differently from the ref (brute force, a generator that builds the expected answer, a stdlib routine, or
properties).
v8_01 hex_color, v8_02 morse_text, v8_03 case_convert, v8_04 money_text, v8_05 cidr_range, v8_06 clock_12h,
v8_07 luhn_digits, v8_08 query_pairs, v8_09 digit_persistence, v8_10 euler_phi, v8_11 goldbach_pairs,
v8_12 pascal_mod, v8_13 primitive_triples, v8_14 happy_count, v8_15 egyptian_greedy, v8_16 two_color,
v8_17 lattice_segment, v8_18 closest_pair, v8_19 euler_trail, v8_20 triangle_kind, v8_21 manhattan_center,
v8_22 tree_centers, v8_23 robot_walk, v8_24 elevator_scan, v8_25 josephus_order, v8_26 max_subarray,
v8_27 stair_ways, v8_28 lcs_smallest, v8_29 matrix_chain, v8_30 ledger_events.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


# --- formats ---

task("v8_01_hex_color", r'''
Write two functions for CSS-style hex colors: `parse_color(text)` and `format_color(rgb)`.

parse_color(text): `text` must be a str of one of two forms, otherwise raise ValueError:
- "#RRGGBB": a "#" followed by six hex digits, two per channel (red, green, blue);
- "#RGB": a "#" followed by three hex digits, each standing for that digit written twice ("#f80" means "#ff8800").
Hex digits are 0-9, a-f and A-F; upper and lower case mean the same. Nothing else is allowed: no surrounding spaces,
no "0x", no missing "#", no other length. Return a tuple (r, g, b) of ints from 0 to 255.

format_color(rgb): `rgb` must be a tuple or list of exactly three ints, each from 0 to 255; a bool is never accepted
as an int. Otherwise raise ValueError. Return the color as "#rrggbb" with lowercase hex digits, except that when every
channel's two digits are equal the short form "#rgb" is returned instead.

Examples:
- parse_color("#ff8800") == (255, 136, 0) and parse_color("#F80") == (255, 136, 0)
- parse_color("#000") == (0, 0, 0) and parse_color("#123456") == (18, 52, 86)
- format_color((255, 136, 0)) == "#f80" and format_color([18, 52, 86]) == "#123456"
- format_color((17, 34, 51)) == "#123" and format_color((255, 255, 254)) == "#fffffe"
- ValueError: parse_color("ff8800"), parse_color("#ff880"), parse_color("#gg0000"), parse_color(" #fff"),
  format_color((256, 0, 0)), format_color((1, 2)), format_color((True, 0, 0))
''', r'''
import random, re

P, F = parse_color, format_color

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert P("#ff8800") == (255, 136, 0) and P("#F80") == (255, 136, 0) and P("#000") == (0, 0, 0)
assert P("#123456") == (18, 52, 86) and P("#AbCdEf") == (171, 205, 239)
assert F((255, 136, 0)) == "#f80" and F([18, 52, 86]) == "#123456" and F((17, 34, 51)) == "#123"
assert F((255, 255, 254)) == "#fffffe" and F((0, 0, 0)) == "#000" and F((255, 255, 255)) == "#fff"
for bad in ("ff8800", "#ff880", "#gg0000", " #fff", "#fff ", "#", "#ffff", "0xfff", "#0x0", "##fff", "", None, 255,
            "#ff88001", "#ｆｆｆ"):
    assert rej(P, bad), bad
for bad in ((256, 0, 0), (1, 2), (True, 0, 0), (0, 0, -1), (1.0, 2, 3), "abc", None, (1, 2, 3, 4), [0, 0, False]):
    assert rej(F, bad), bad

GOOD = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")

def ofmt(c):
    s = "#" + "".join(format(v, "02x") for v in c)
    return "#" + s[1] + s[3] + s[5] if s[1] == s[2] and s[3] == s[4] and s[5] == s[6] else s

random.seed(8001)
for _ in range(500):
    c = tuple(random.choice([random.randrange(256), 17 * random.randrange(16)]) for _ in range(3))
    s = F(c if random.random() < 0.5 else list(c))
    assert s == ofmt(c), (c, s)
    assert P(s) == c and P(s.upper()) == c
for _ in range(1500):
    s = "#" * random.choice([0, 1, 1, 1, 2]) + "".join(random.choice("0aF9g x") for _ in range(random.choice([3, 4, 6, 5])))
    if GOOD.fullmatch(s):
        h = s[1:] if len(s) == 7 else "".join(ch * 2 for ch in s[1:])
        assert P(s) == (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)), s
    else:
        assert rej(P, s), s
''', r'''
_HEX = "0123456789abcdef"


def parse_color(text):
    if not isinstance(text, str) or len(text) not in (4, 7) or text[0] != "#":
        raise ValueError("expected #RGB or #RRGGBB")
    digits = text[1:]
    if any(c not in "0123456789abcdefABCDEF" for c in digits):
        raise ValueError("bad hex digit")
    digits = digits.lower()
    if len(digits) == 3:
        digits = "".join(c + c for c in digits)
    return tuple(_HEX.index(digits[i]) * 16 + _HEX.index(digits[i + 1]) for i in (0, 2, 4))


def format_color(rgb):
    if not isinstance(rgb, (tuple, list)) or len(rgb) != 3:
        raise ValueError("need three channels")
    for v in rgb:
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 255:
            raise ValueError("channel must be an int from 0 to 255")
    pairs = [_HEX[v // 16] + _HEX[v % 16] for v in rgb]
    if all(p[0] == p[1] for p in pairs):
        return "#" + "".join(p[0] for p in pairs)
    return "#" + "".join(pairs)
''')


task("v8_02_morse_text", r'''
Write `to_morse(text)` and `from_morse(code)` for International Morse code over letters and digits.

The code table (letter or digit, then its code):
A .-    B -...  C -.-.  D -..   E .     F ..-.  G --.   H ....  I ..    J .---  K -.-   L .-..  M --
N -.    O ---   P .--.  Q --.-  R .-.   S ...   T -     U ..-   V ...-  W .--   X -..-  Y -.--  Z --..
0 ----- 1 .---- 2 ..--- 3 ...-- 4 ....- 5 ..... 6 -.... 7 --... 8 ---.. 9 ----.

to_morse(text): `text` must be a str of words separated by single spaces, each word made of ASCII letters (either
case) and ASCII digits. The codes of the characters of one word are joined with one space, and the words are joined
with " / ". The empty string gives "". Anything else raises ValueError: other characters, two spaces in a row, or a
space at the start or end.

from_morse(code): the exact inverse. `code` must be a str; "" gives "". Otherwise it is words joined with " / ", each
word being codes from the table joined with single spaces. Letters come back in upper case. Any code not in the table,
an empty word, or any other spacing raises ValueError.

Examples:
- to_morse("SOS") == "... --- ..." and to_morse("Hi 5") == ".... .. / ....."
- from_morse(".- -...") == "AB" and from_morse("... --- ... / -.-.") == "SOS C"
- to_morse("") == "" and from_morse("") == "" and from_morse("----.") == "9"
- ValueError: to_morse("a  b"), to_morse(" a"), to_morse("a!"), from_morse("...---"), from_morse(".- /"),
  from_morse("/ .-"), from_morse(".-  -...")
''', r'''
import random

TM, FM = to_morse, from_morse

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert TM("SOS") == "... --- ..." and TM("Hi 5") == ".... .. / ....." and TM("") == ""
assert FM(".- -...") == "AB" and FM("... --- ... / -.-.") == "SOS C" and FM("") == "" and FM("----.") == "9"
assert TM("abc XYZ 0189") == ".- -... -.-. / -..- -.-- --.. / ----- .---- ---.. ----."
for bad in ("a  b", " a", "a ", "a!", "é", "a\tb", "a\nb", None, 7, ["a"], "٣"):
    assert rej(TM, bad), bad
for bad in ("...---", ".- /", "/ .-", ".-  -...", "/", " / ", ".- / / -...", " .-", ".- ", "x", ".-/-...", None, 5,
            ".- //  -...", "-----."):
    assert rej(FM, bad), bad

ROWS = """A.- B-... C-.-. D-.. E. F..-. G--. H.... I.. J.--- K-.- L.-.. M-- N-. O--- P.--. Q--.- R.-. S... T- U..-
V...- W.-- X-..- Y-.-- Z--.. 0----- 1.---- 2..--- 3...-- 4....- 5..... 6-.... 7--... 8---.. 9----."""
TAB = {e[0]: e[1:] for e in ROWS.split()}
ALPH = sorted(TAB)

random.seed(8002)
for _ in range(400):
    words = ["".join(random.choice(ALPH) for _ in range(random.randint(1, 6))) for _ in range(random.randint(1, 4))]
    text = " ".join("".join(c.lower() if random.random() < 0.3 else c for c in w) for w in words)
    want = " / ".join(" ".join(TAB[c] for c in w) for w in words)
    assert TM(text) == want, text
    assert FM(want) == " ".join(words), want
for _ in range(400):
    s = "".join(random.choice([".", "-", " ", " / ", "/"]) for _ in range(random.randint(1, 7)))
    words = s.split(" / ")
    ok = all(w and all(t in TAB.values() for t in w.split(" ")) for w in words)
    if ok:
        inv = {v: k for k, v in TAB.items()}
        assert FM(s) == " ".join("".join(inv[t] for t in w.split(" ")) for w in words), s
    else:
        assert rej(FM, s), s
''', r'''
_CODES = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
          "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
          "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
          "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
          "7": "--...", "8": "---..", "9": "----."}
_BACK = {v: k for k, v in _CODES.items()}


def to_morse(text):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    if text == "":
        return ""
    words = []
    for w in text.split(" "):
        if not w:
            raise ValueError("bad spacing")
        if any(c.upper() not in _CODES or not c.isascii() for c in w):
            raise ValueError("bad character")
        words.append(" ".join(_CODES[c.upper()] for c in w))
    return " / ".join(words)


def from_morse(code):
    if not isinstance(code, str):
        raise ValueError("code must be a str")
    if code == "":
        return ""
    words = []
    for w in code.split(" / "):
        toks = w.split(" ")
        if any(t not in _BACK for t in toks):
            raise ValueError("bad code or spacing")
        words.append("".join(_BACK[t] for t in toks))
    return " ".join(words)
''')


task("v8_03_case_convert", r'''
Write `snake_to_camel(name)` and `camel_to_snake(name)` that convert identifiers between snake_case and camelCase.

A snake_case name is one or more words joined by single underscores, where every word is an ASCII lowercase letter
followed by zero or more ASCII lowercase letters or digits ("user_id", "x1_y2", "a"). A camelCase name is the same
words written together, the first word unchanged and every later word with its first letter in upper case ("userId",
"x1Y2", "a").

snake_to_camel(name): `name` must be a str that is a snake_case name as defined above; otherwise raise ValueError.
That rules out upper-case letters, a word starting with a digit, a leading or trailing underscore, two underscores in
a row, non-ASCII letters and the empty string. Return the camelCase name.

camel_to_snake(name): the exact inverse. `name` must be a str that snake_to_camel could have produced, otherwise
ValueError: it starts with an ASCII lowercase letter and contains only ASCII letters and digits. Every upper-case
letter starts a new word, so "getHTTP" has the words get, h, t, t, p. Return the snake_case name.

Examples:
- snake_to_camel("user_id") == "userId" and snake_to_camel("parse_http_response") == "parseHttpResponse"
- snake_to_camel("x1_y2") == "x1Y2" and snake_to_camel("a") == "a"
- camel_to_snake("userId") == "user_id" and camel_to_snake("getHTTP") == "get_h_t_t_p"
- camel_to_snake("x1Y2") == "x1_y2"
- ValueError: snake_to_camel("User_id"), snake_to_camel("user__id"), snake_to_camel("_id"), snake_to_camel("user_2id"),
  snake_to_camel(""), camel_to_snake("UserId"), camel_to_snake("user_id"), camel_to_snake("")
''', r'''
import random, re

SC, CS = snake_to_camel, camel_to_snake

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert SC("user_id") == "userId" and SC("parse_http_response") == "parseHttpResponse" and SC("x1_y2") == "x1Y2"
assert SC("a") == "a" and CS("userId") == "user_id" and CS("getHTTP") == "get_h_t_t_p" and CS("x1Y2") == "x1_y2"
assert CS("a") == "a" and CS("a9b") == "a9b" and SC("a_b_c") == "aBC" and CS("aBC") == "a_b_c"
for bad in ("User_id", "user__id", "_id", "user_2id", "", "id_", "user-id", "user id", "é_a", "a_É", "ab_C", None, 3,
            "١a", "a_"):
    assert rej(SC, bad), bad
for bad in ("UserId", "user_id", "", "1abc", "a-b", "a b", "aÉ", "é", None, ["a"], "aB_c", "a٣"):
    assert rej(CS, bad), bad

SNAKE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*")
CAMEL = re.compile(r"[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)*")

random.seed(8003)
for _ in range(600):
    words = [random.choice("abxyz") + "".join(random.choice("ab09") for _ in range(random.randint(0, 3)))
             for _ in range(random.randint(1, 5))]
    snake, camel = "_".join(words), words[0] + "".join(w[0].upper() + w[1:] for w in words[1:])
    assert SC(snake) == camel, snake
    assert CS(camel) == snake, camel
for _ in range(2000):
    s = "".join(random.choice("abZ0_é") for _ in range(random.randint(0, 6)))
    if SNAKE.fullmatch(s):
        assert CS(SC(s)) == s, s
    else:
        assert rej(SC, s), s
    if CAMEL.fullmatch(s):
        assert SC(CS(s)) == s, s
    else:
        assert rej(CS, s), s
''', r'''
_LOW = set("abcdefghijklmnopqrstuvwxyz")
_UP = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_DIG = set("0123456789")


def snake_to_camel(name):
    if not isinstance(name, str):
        raise ValueError("name must be a str")
    words = name.split("_")
    for w in words:
        if not w or w[0] not in _LOW or any(c not in _LOW and c not in _DIG for c in w):
            raise ValueError("not a snake_case name")
    return words[0] + "".join(w[0].upper() + w[1:] for w in words[1:])


def camel_to_snake(name):
    if not isinstance(name, str) or not name or name[0] not in _LOW:
        raise ValueError("not a camelCase name")
    out = []
    for c in name:
        if c in _UP:
            out.append("_" + c.lower())
        elif c in _LOW or c in _DIG:
            out.append(c)
        else:
            raise ValueError("not a camelCase name")
    return "".join(out)
''')


task("v8_04_money_text", r'''
Write `cents_to_text(cents)` and `text_to_cents(text)` that convert an amount of money in cents to and from text.

cents_to_text(cents): `cents` must be an int (a bool is not accepted), otherwise ValueError; it may be negative and
has no size limit. The text is an optional "-" (only for negative amounts), then the whole dollars, then "." and
exactly two digits of cents. The dollars are written without leading zeros ("0" when there are none), with a comma
between every group of three digits counted from the right.

text_to_cents(text): the exact inverse. `text` must be a str that cents_to_text could have produced, and the function
returns that int; anything else raises ValueError. So, among others, these are rejected: a missing or misplaced comma,
a leading zero, one or three digits after the ".", a "+" sign, spaces, "-0.00", and a missing "." part.

Examples:
- cents_to_text(0) == "0.00" and cents_to_text(5) == "0.05" and cents_to_text(-5) == "-0.05"
- cents_to_text(123456789) == "1,234,567.89" and cents_to_text(-100000) == "-1,000.00"
- cents_to_text(99999) == "999.99"
- text_to_cents("1,234,567.89") == 123456789 and text_to_cents("-0.05") == -5 and text_to_cents("12.30") == 1230
- ValueError: text_to_cents("1234.00"), text_to_cents("01.00"), text_to_cents("1,23.00"), text_to_cents("1.5"),
  text_to_cents("-0.00"), text_to_cents("+1.00"), text_to_cents(" 1.00"), text_to_cents("1,000"),
  cents_to_text(True), cents_to_text(1.5)
''', r'''
import random, re

CT, TC = cents_to_text, text_to_cents

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert CT(0) == "0.00" and CT(5) == "0.05" and CT(-5) == "-0.05" and CT(123456789) == "1,234,567.89"
assert CT(-100000) == "-1,000.00" and CT(99999) == "999.99" and CT(100000) == "1,000.00" and CT(10 ** 20) == "1" + ",000" * 6 + ".00"
assert TC("1,234,567.89") == 123456789 and TC("-0.05") == -5 and TC("12.30") == 1230 and TC("0.00") == 0
for bad in ("1234.00", "01.00", "1,23.00", "1.5", "-0.00", "+1.00", " 1.00", "1,000", "", "1.500", ".50", "1.", "-",
            "1,000.0", "1,0000.00", ",100.00", "1,,000.00", "--1.00", "1.00 ", "١.00", "0,100.00", None, 100):
    assert rej(TC, bad), bad
for bad in (True, 1.5, "100", None, [1]):
    assert rej(CT, bad), bad

GRAMMAR = re.compile(r"-?(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)\.[0-9]{2}")

def ofmt(c):
    s = f"{abs(c) // 100:,}.{abs(c) % 100:02d}"
    return "-" + s if c < 0 else s

random.seed(8004)
for _ in range(800):
    c = random.choice([random.randint(-999, 999), random.randint(-10 ** 9, 10 ** 9), random.randint(-10 ** 25, 10 ** 25)])
    assert CT(c) == ofmt(c), c
    assert TC(ofmt(c)) == c, c
for _ in range(2000):
    base = list(ofmt(random.randint(-10 ** 8, 10 ** 8)))
    for _ in range(random.randint(1, 2)):
        i = random.randrange(len(base) + 1)
        op = random.random()
        if op < 0.4 and i < len(base):
            del base[i]
        elif op < 0.8:
            base.insert(i, random.choice("0,.-5"))
        elif i < len(base):
            base[i] = random.choice("0,.9")
    s = "".join(base)
    if GRAMMAR.fullmatch(s) and s != "-0.00":
        v = int(s.replace(",", "").replace(".", ""))
        assert TC(s) == v, s
    else:
        assert rej(TC, s), s
''', r'''
def cents_to_text(cents):
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise ValueError("cents must be an int")
    dollars, rest = divmod(abs(cents), 100)
    digits = str(dollars)
    groups = []
    while len(digits) > 3:
        groups.append(digits[-3:])
        digits = digits[:-3]
    groups.append(digits)
    text = ",".join(reversed(groups)) + "." + str(rest).rjust(2, "0")
    return "-" + text if cents < 0 else text


def text_to_cents(text):
    if not isinstance(text, str) or len(text) < 4 or text[-3] != ".":
        raise ValueError("not an amount")
    body = text[1:] if text.startswith("-") else text
    plain = body.replace(",", "").replace(".", "")
    if not plain or any(c not in "0123456789" for c in plain):
        raise ValueError("not an amount")
    value = int(plain)
    if text.startswith("-"):
        value = -value
    if cents_to_text(value) != text:
        raise ValueError("not in canonical form")
    return value
''')


task("v8_05_cidr_range", r'''
Write `cidr_range(text)` that reads an IPv4 block in CIDR notation and returns its first address, last address and
size.

`text` must be a str of the form "a.b.c.d/n", otherwise raise ValueError:
- a, b, c and d are decimal numbers from 0 to 255 written without leading zeros ("0" is fine, "01" is not);
- n is a decimal number from 0 to 32, also without leading zeros;
- only ASCII digits, exactly three dots and one "/" appear; no spaces or signs.
The address does not have to be the start of its block. The block keeps the first n bits of the 32-bit address
(a is the most significant byte). The first address has all the remaining bits 0, the last has them all 1, and the
size is 2 to the power (32 - n).

Return a tuple (first, last, size): first and last as dotted strings in the same no-leading-zero form, size an int.

Examples:
- cidr_range("192.168.1.77/24") == ("192.168.1.0", "192.168.1.255", 256)
- cidr_range("10.1.2.3/8") == ("10.0.0.0", "10.255.255.255", 16777216)
- cidr_range("172.16.5.9/20") == ("172.16.0.0", "172.16.15.255", 4096)
- cidr_range("0.0.0.0/0") == ("0.0.0.0", "255.255.255.255", 4294967296)
- cidr_range("1.2.3.4/32") == ("1.2.3.4", "1.2.3.4", 1)
- ValueError: cidr_range("1.2.3/8"), cidr_range("1.2.3.4"), cidr_range("1.2.3.256/8"), cidr_range("1.2.3.04/8"),
  cidr_range("1.2.3.4/33"), cidr_range("1.2.3.4/08"), cidr_range(" 1.2.3.4/8"), cidr_range("1.2.3.4/")
''', r'''
import ipaddress, random, re

CR = cidr_range

def rej(x):
    try:
        CR(x)
    except ValueError:
        return True
    return False

assert CR("192.168.1.77/24") == ("192.168.1.0", "192.168.1.255", 256)
assert CR("10.1.2.3/8") == ("10.0.0.0", "10.255.255.255", 16777216)
assert CR("172.16.5.9/20") == ("172.16.0.0", "172.16.15.255", 4096)
assert CR("0.0.0.0/0") == ("0.0.0.0", "255.255.255.255", 4294967296) and CR("1.2.3.4/32") == ("1.2.3.4", "1.2.3.4", 1)
assert CR("255.255.255.255/31") == ("255.255.255.254", "255.255.255.255", 2)
for bad in ("1.2.3/8", "1.2.3.4", "1.2.3.256/8", "1.2.3.04/8", "1.2.3.4/33", "1.2.3.4/08", " 1.2.3.4/8", "1.2.3.4/",
            "1.2.3.4/-1", "1.2.3.4/+8", "1..3.4/8", "1.2.3.4.5/8", "1.2.3.4/8/8", "a.2.3.4/8", "1.2.3.٤/8", "1.2.3.4 /8",
            "/8", "", None, 5, "1.2.3.4/3 2", "00.1.1.1/8"):
    assert rej(bad), bad

OCT = r"(?:0|[1-9][0-9]?|1[0-9][0-9]|2[0-4][0-9]|25[0-5])"
GOOD = re.compile(r"(?:%s\.){3}%s/(?:[0-9]|[12][0-9]|3[0-2])" % (OCT, OCT))

random.seed(8005)
for _ in range(800):
    a = [random.choice([0, 255, random.randrange(256)]) for _ in range(4)]
    n = random.randint(0, 32)
    s = ".".join(map(str, a)) + "/" + str(n)
    net = ipaddress.ip_network(s, strict=False)
    assert CR(s) == (str(net.network_address), str(net.broadcast_address), net.num_addresses), s
for _ in range(1500):
    s = "".join(random.choice("0129./5") for _ in range(random.randint(5, 12)))
    if GOOD.fullmatch(s):
        net = ipaddress.ip_network(s, strict=False)
        assert CR(s) == (str(net.network_address), str(net.broadcast_address), net.num_addresses), s
    else:
        assert rej(s), s
''', r'''
def _num(s, hi):
    if not s or any(c not in "0123456789" for c in s) or (len(s) > 1 and s[0] == "0") or int(s) > hi:
        raise ValueError("bad number")
    return int(s)


def cidr_range(text):
    if not isinstance(text, str) or text.count("/") != 1:
        raise ValueError("expected a.b.c.d/n")
    addr, bits = text.split("/")
    parts = addr.split(".")
    if len(parts) != 4:
        raise ValueError("expected four octets")
    value = 0
    for p in parts:
        value = value * 256 + _num(p, 255)
    n = _num(bits, 32)
    host = (1 << (32 - n)) - 1
    first, last = value & ~host & 0xFFFFFFFF, value | host

    def dotted(v):
        return ".".join(str((v >> s) & 255) for s in (24, 16, 8, 0))
    return dotted(first), dotted(last), host + 1
''')


task("v8_06_clock_12h", r'''
Write `to_24h(text)` and `to_12h(text)` that convert a time of day between the 12-hour and the 24-hour clock.

The 12-hour form is "h:mm AM" or "h:mm PM": the hour from 1 to 12 with no leading zero, a colon, the minutes as two
digits from 00 to 59, one space, and "AM" or "PM" in upper case. 12:mm AM is just after midnight (00:mm on the 24-hour
clock), 12:mm PM is just after noon (12:mm), and every other hour h PM is h + 12.

The 24-hour form is "HH:MM": the hour as two digits from 00 to 23, a colon, the minutes as two digits from 00 to 59.

to_24h(text) takes a str in the 12-hour form and returns the 24-hour form; to_12h(text) takes a str in the 24-hour
form and returns the 12-hour form. Each raises ValueError for anything that is not exactly its input form: a non-str,
an hour or minute out of range, a leading zero on the 12-hour hour, a missing digit, lower-case "am", a missing or
doubled space, other characters.

Examples:
- to_24h("12:05 AM") == "00:05" and to_24h("1:30 PM") == "13:30"
- to_24h("12:00 PM") == "12:00" and to_24h("9:07 AM") == "09:07"
- to_12h("00:00") == "12:00 AM" and to_12h("23:59") == "11:59 PM"
- to_12h("12:30") == "12:30 PM" and to_12h("07:05") == "7:05 AM"
- ValueError: to_24h("13:00 PM"), to_24h("0:15 AM"), to_24h("09:15 AM"), to_24h("9:5 AM"), to_24h("9:15 am"),
  to_24h("9:15PM"), to_12h("24:00"), to_12h("7:05"), to_12h("12:60")
''', r'''
import random

T24, T12 = to_24h, to_12h

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert T24("12:05 AM") == "00:05" and T24("1:30 PM") == "13:30" and T24("12:00 PM") == "12:00" and T24("9:07 AM") == "09:07"
assert T12("00:00") == "12:00 AM" and T12("23:59") == "11:59 PM" and T12("12:30") == "12:30 PM" and T12("07:05") == "7:05 AM"
for bad in ("13:00 PM", "0:15 AM", "09:15 AM", "9:5 AM", "9:15 am", "9:15PM", "9:15  PM", " 9:15 PM", "9:15 PM ", "9:60 AM",
            "9:15 XM", "9-15 PM", "9:1５ AM", "", None, 915, "12:00", "9:15 P M"):
    assert rej(T24, bad), bad
for bad in ("24:00", "7:05", "12:60", "007:05", "07:5", "07-05", " 07:05", "07:05 ", "0٧:05", "", None, 705, "1:00 PM"):
    assert rej(T12, bad), bad

def twelve(m):
    h, mm = divmod(m, 60)
    return "%d:%02d %s" % ((h + 11) % 12 + 1, mm, "AM" if h < 12 else "PM")

def twentyfour(m):
    return "%02d:%02d" % divmod(m, 60)

V12 = {twelve(m): m for m in range(1440)}
V24 = {twentyfour(m): m for m in range(1440)}
for m in range(1440):
    assert T24(twelve(m)) == twentyfour(m), m
    assert T12(twentyfour(m)) == twelve(m), m

random.seed(8006)
for _ in range(3000):
    s = "".join(random.choice("0129:5 AMP") for _ in range(random.randint(4, 8)))
    if s in V12:
        assert T24(s) == twentyfour(V12[s]), s
    else:
        assert rej(T24, s), s
    if s in V24:
        assert T12(s) == twelve(V24[s]), s
    else:
        assert rej(T12, s), s
''', r'''
_D = "0123456789"


def _two(s, hi):
    if len(s) != 2 or s[0] not in _D or s[1] not in _D or int(s) > hi:
        raise ValueError("bad field")
    return int(s)


def to_24h(text):
    if not isinstance(text, str) or text.count(" ") != 1:
        raise ValueError("expected h:mm AM or h:mm PM")
    clock, half = text.split(" ")
    if half not in ("AM", "PM") or clock.count(":") != 1:
        raise ValueError("expected h:mm AM or h:mm PM")
    h, m = clock.split(":")
    if not h or h[0] == "0" or any(c not in _D for c in h) or not 1 <= int(h) <= 12:
        raise ValueError("bad hour")
    minutes = _two(m, 59)
    hour = int(h) % 12 + (12 if half == "PM" else 0)
    return "%02d:%02d" % (hour, minutes)


def to_12h(text):
    if not isinstance(text, str) or len(text) != 5 or text[2] != ":":
        raise ValueError("expected HH:MM")
    hour, minutes = _two(text[:2], 23), _two(text[3:], 59)
    return "%d:%02d %s" % (hour % 12 or 12, minutes, "AM" if hour < 12 else "PM")
''')


task("v8_07_luhn_digits", r'''
Write `luhn_valid(number)` and `luhn_append(partial)` for the Luhn check digit used on card and account numbers.

The Luhn test on a string of digits: starting from the rightmost digit (the check digit) and moving left, leave the
first digit as it is, double the second, leave the third, double the fourth, and so on. When doubling gives a number
above 9, subtract 9 from it. Add up all the resulting values; the number passes when the total is a multiple of 10.

luhn_valid(number): `number` must be a str of at least two ASCII digits (leading zeros are fine), otherwise raise
ValueError. Return True if it passes the Luhn test and False if it does not.

luhn_append(partial): `partial` must be a str of at least one ASCII digit, otherwise raise ValueError. Return partial
with one more digit appended at the right: the only digit 0-9 that makes the result pass the Luhn test.

Spaces, dashes, signs and non-ASCII digits are not digits here, and a non-str (such as an int) is a ValueError.

Examples:
- luhn_valid("79927398713") is True and luhn_valid("79927398710") is False
- luhn_append("7992739871") == "79927398713"
- luhn_valid("00") is True and luhn_append("0") == "00" and luhn_append("4") == "42"
- luhn_valid("4539578763621486") is True
- ValueError: luhn_valid("7"), luhn_valid("79a"), luhn_valid(""), luhn_append(""), luhn_append("12 3"),
  luhn_valid(1234)
''', r'''
import random

LV, LA = luhn_valid, luhn_append

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert LV("79927398713") is True and LV("79927398710") is False and LA("7992739871") == "79927398713"
assert LV("00") is True and LA("0") == "00" and LA("4") == "42" and LV("4539578763621486") is True
assert LV("18") is True and LV("81") is False and LA("000") == "0000"
for bad in ("7", "79a", "", "12 3", " 12", "12-3", "+12", "١٢", None, 1234, ["1", "2"]):
    assert rej(LV, bad), bad
for bad in ("", "12 3", "a", "9.", None, 5, "٣"):
    assert rej(LA, bad), bad

def osum(s):
    t = 0
    for i, ch in enumerate(reversed(s)):
        d = "0123456789".index(ch)
        if i % 2:
            d = sum(divmod(2 * d, 10))
        t += d
    return t

random.seed(8007)
for _ in range(1500):
    s = "".join(random.choice("0123456789") for _ in range(random.randint(2, 25)))
    assert LV(s) is (osum(s) % 10 == 0), s
    p = s[:-1]
    good = [p + d for d in "0123456789" if osum(p + d) % 10 == 0]
    assert len(good) == 1 and LA(p) == good[0], p
''', r'''
def _check(s, least):
    if not isinstance(s, str) or len(s) < least or any(c not in "0123456789" for c in s):
        raise ValueError("expected a str of ASCII digits")


def _total(digits):
    total = 0
    for i, ch in enumerate(digits[::-1]):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total


def luhn_valid(number):
    _check(number, 2)
    return _total(number) % 10 == 0


def luhn_append(partial):
    _check(partial, 1)
    return partial + str(-_total(partial + "0") % 10)
''')


task("v8_08_query_pairs", r'''
Write `parse_query(text)` and `build_query(pairs)` for a simple URL query string such as "a=1&b=two+words".

Encoding of a single key or value: the characters A-Z, a-z, 0-9 and "-", ".", "_", "~" stand for themselves; "+"
stands for a space; "%" followed by two hex digits (either case) stands for the ASCII character with that code, which
must be from 00 to 7F. No other character may appear in an encoded key or value.

parse_query(text): `text` must be a str, otherwise ValueError. "" gives []. Otherwise the text is split on "&" into
parts, each part must contain exactly one "=", the key before it must not be empty (the value may be), and both sides
must follow the encoding above. Return the list of decoded (key, value) tuples in order; repeated keys are kept.
Anything else raises ValueError: an empty part, a part with no "=" or two, a bad or incomplete "%" escape, a code above
7F, a space or other raw character.

build_query(pairs): `pairs` is a list or tuple of (key, value) pairs of str, where every character is ASCII and the
key is not empty; otherwise ValueError. Encode each key and value (letters, digits and "-._~" as themselves, space as
"+", every other ASCII character as "%" and two upper-case hex digits), join each pair with "=" and the pairs with "&".

Examples:
- parse_query("a=1&b=two+words") == [("a", "1"), ("b", "two words")]
- parse_query("q=50%25&q=x%2By") == [("q", "50%"), ("q", "x+y")]
- parse_query("") == [] and parse_query("k=") == [("k", "")]
- build_query([("a", "1"), ("b", "two words")]) == "a=1&b=two+words"
- build_query([("path", "/tmp/x y")]) == "path=%2Ftmp%2Fx+y" and build_query([]) == ""
- ValueError: parse_query("a"), parse_query("=1"), parse_query("a=1=2"), parse_query("a=%G1"), parse_query("a=%4"),
  parse_query("a=%80"), parse_query("a=b c"), parse_query("a=1&&b=2"), build_query([("", "x")]),
  build_query([("k", "é")])
''', r'''
import random, re
from urllib.parse import quote_plus, unquote_plus

PQ, BQ = parse_query, build_query

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert PQ("a=1&b=two+words") == [("a", "1"), ("b", "two words")] and PQ("q=50%25&q=x%2By") == [("q", "50%"), ("q", "x+y")]
assert PQ("") == [] and PQ("k=") == [("k", "")] and PQ("%41%7e=%2f") == [("A~", "/")] and PQ("x=-._~") == [("x", "-._~")]
assert BQ([("a", "1"), ("b", "two words")]) == "a=1&b=two+words" and BQ([("path", "/tmp/x y")]) == "path=%2Ftmp%2Fx+y"
assert BQ([]) == "" and BQ((("k", ""),)) == "k=" and BQ([("a&b", "c=d")]) == "a%26b=c%3Dd" and BQ([("t", "\x00~")]) == "t=%00~"
for bad in ("a", "=1", "a=1=2", "a=%G1", "a=%4", "a=%80", "a=b c", "a=1&&b=2", "&a=1", "a=1&", "a=é", "a=%", "a=\n",
            "a=1&=2", None, 5, b"a=1", "a=%e9", "a=*"):
    assert rej(PQ, bad), bad
for bad in ([("", "x")], [("k", "é")], [("k",)], [("k", 1)], [("k", "v", "w")], None, "a=1", [["k", None]], [(None, "v")]):
    assert rej(BQ, bad), bad

TOKEN = re.compile(r"(?:[A-Za-z0-9\-._~+]|%[0-7][0-9A-Fa-f])*")
ALPH = "aZ9-._~ +/%&=?#\x7f\x01"

random.seed(8008)
for _ in range(600):
    pairs = [("".join(random.choice(ALPH) for _ in range(random.randint(1, 5))),
              "".join(random.choice(ALPH) for _ in range(random.randint(0, 5)))) for _ in range(random.randint(0, 4))]
    q = BQ(pairs)
    assert q == "&".join(quote_plus(k, safe="") + "=" + quote_plus(v, safe="") for k, v in pairs), pairs
    assert PQ(q) == pairs, q
for _ in range(2000):
    s = "".join(random.choice(["a", "=", "&", "+", "%4", "%41", "%7F", "%8", "%g", " ", "~", "1"]) for _ in range(random.randint(1, 6)))
    parts = s.split("&")
    ok = all(p.count("=") == 1 and p.split("=")[0] and all(TOKEN.fullmatch(x) for x in p.split("=")) for p in parts)
    if ok:
        assert PQ(s) == [tuple(unquote_plus(x) for x in p.split("=")) for p in parts], s
    else:
        assert rej(PQ, s), s
''', r'''
_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _decode(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "%":
            h = s[i + 1:i + 3]
            if len(h) != 2 or h[0] not in "01234567" or h[1] not in "0123456789abcdefABCDEF":
                raise ValueError("bad escape")
            out.append(chr(int(h, 16)))
            i += 3
            continue
        if c != "+" and c not in _SAFE:
            raise ValueError("bad character")
        out.append(" " if c == "+" else c)
        i += 1
    return "".join(out)


def parse_query(text):
    if not isinstance(text, str):
        raise ValueError("text must be a str")
    out = []
    for part in text.split("&") if text else []:
        if part.count("=") != 1 or part.startswith("="):
            raise ValueError("bad part")
        k, v = part.split("=")
        out.append((_decode(k), _decode(v)))
    return out


def build_query(pairs):
    if not isinstance(pairs, (list, tuple)):
        raise ValueError("pairs must be a list or tuple")
    enc = lambda s: "".join(c if c in _SAFE else "+" if c == " " else "%%%02X" % ord(c) for c in s)
    out = []
    for p in pairs:
        if (not isinstance(p, (list, tuple)) or len(p) != 2 or not p[0]
                or not all(isinstance(x, str) and x.isascii() for x in p)):
            raise ValueError("bad pair")
        out.append(enc(p[0]) + "=" + enc(p[1]))
    return "&".join(out)
''')


# --- number_theory ---

task("v8_09_digit_persistence", r'''
Write `persistence(n)` and `digital_root(n)` about repeatedly combining the decimal digits of a number.

`n` must be an int >= 0 for both functions; a bool is not accepted, and anything else raises ValueError. There is no
upper limit: n can have hundreds of digits.

persistence(n) returns a tuple (additive, multiplicative):
- additive is how many times n must be replaced by the sum of its decimal digits before it has a single digit;
- multiplicative is the same count when n is replaced by the product of its decimal digits instead.
Each count starts again from the original n. A number that already has one digit (0-9) has (0, 0).

digital_root(n) returns the single digit that repeated digit sums end at, so digital_root(n) is a number from 0 to 9
(0 only for n = 0).

Examples:
- persistence(39) == (2, 3): 39 -> 12 -> 3 adds twice, and 39 -> 27 -> 14 -> 4 multiplies three times
- persistence(999) == (2, 4) and persistence(7) == (0, 0) and persistence(10) == (1, 1)
- persistence(277777788888899) == (2, 11)
- digital_root(0) == 0 and digital_root(38) == 2 and digital_root(10 ** 100) == 1
- ValueError: persistence(-1), persistence(True), persistence(2.0), digital_root("5"), digital_root(-3)
''', r'''
import random

PE, DR = persistence, digital_root

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert PE(39) == (2, 3) and PE(999) == (2, 4) and PE(7) == (0, 0) and PE(10) == (1, 1) and PE(0) == (0, 0)
assert PE(277777788888899) == (2, 11) and PE(25) == (1, 2)
assert DR(0) == 0 and DR(38) == 2 and DR(10 ** 100) == 1 and DR(9) == 9 and DR(18) == 9
for f in (PE, DR):
    for bad in (-1, True, False, 2.0, "5", -3, None, [1]):
        assert rej(f, bad), (f, bad)

def steps(n, fold):
    k = 0
    while len(str(n)) > 1:
        n, k = fold(str(n)), k + 1
    return k

def add(s):
    return sum(int(c) for c in s)

def mul(s):
    r = 1
    for c in s:
        r *= int(c)
    return r

random.seed(8009)
for _ in range(600):
    n = random.choice([random.randint(0, 99), random.randint(0, 10 ** 6), random.randint(0, 10 ** 30),
                       int("".join(random.choice("2346789") for _ in range(random.randint(1, 20))))])
    assert PE(n) == (steps(n, add), steps(n, mul)), n
    assert DR(n) == (0 if n == 0 else 1 + (n - 1) % 9), n
big = 10 ** 400 - 1
assert PE(big) == (steps(big, add), steps(big, mul)) and DR(big) == 9
''', r'''
def _check(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be an int >= 0")


def _digits(n):
    out = []
    while n:
        n, d = divmod(n, 10)
        out.append(d)
    return out or [0]


def persistence(n):
    _check(n)
    counts = []
    for fold in ("sum", "product"):
        m, k = n, 0
        while m >= 10:
            ds = _digits(m)
            if fold == "sum":
                m = sum(ds)
            else:
                m = 1
                for d in ds:
                    m *= d
            k += 1
        counts.append(k)
    return tuple(counts)


def digital_root(n):
    _check(n)
    while n >= 10:
        n = sum(_digits(n))
    return n
''')


task("v8_10_euler_phi", r'''
Write `phi(n)` and `totient_sum(limit)` for Euler's totient function.

phi(n) is the number of integers k with 1 <= k <= n and gcd(k, n) == 1. `n` must be an int from 1 to 10**12; a bool is
not accepted, and anything else raises ValueError. Use the product formula: if p1, ..., pr are the distinct primes
dividing n, then phi(n) = n * (1 - 1/p1) * ... * (1 - 1/pr). Find the primes by trial division up to the square root of
n, and keep the arithmetic in integers (n // p * (p - 1)) so the answer is exact.

totient_sum(limit) is phi(1) + phi(2) + ... + phi(limit). `limit` must be an int from 1 to 100000 (no bool), otherwise
ValueError. Calling phi() for every k is too slow here; compute every phi(k) at once with a sieve: start with
t[k] = k, and for each prime p (a p with t[p] still equal to p), subtract t[m] // p from t[m] for every multiple m of p.

Examples:
- phi(1) == 1 and phi(9) == 6 and phi(36) == 12 and phi(97) == 96
- phi(10 ** 12) == 400000000000 and phi(999999999989) == 999999999988 (999999999989 is prime)
- totient_sum(1) == 1 and totient_sum(10) == 32 and totient_sum(100000) == 3039650754
- ValueError: phi(0), phi(10 ** 12 + 1), phi(True), phi(2.5), totient_sum(0), totient_sum(100001), totient_sum(None)
''', r'''
import random
from math import gcd

PH, TS = phi, totient_sum

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert PH(1) == 1 and PH(9) == 6 and PH(36) == 12 and PH(97) == 96 and PH(2) == 1
assert PH(10 ** 12) == 400000000000 and PH(999999999989) == 999999999988
assert TS(1) == 1 and TS(10) == 32 and TS(100000) == 3039650754 and TS(2) == 2
for bad in (0, 10 ** 12 + 1, True, 2.5, -4, "9", None):
    assert rej(PH, bad), bad
for bad in (0, 100001, None, True, 10.0, -1):
    assert rej(TS, bad), bad

PR = [2, 3, 5, 7, 11, 13, 101, 997, 9973, 99991, 999983]
random.seed(8010)
for _ in range(400):
    n = random.randint(1, 3000)
    assert PH(n) == sum(1 for k in range(1, n + 1) if gcd(k, n) == 1), n
for _ in range(300):
    fac, n = {}, 1
    for _ in range(random.randint(1, 6)):
        p = random.choice(PR)
        if n * p <= 10 ** 12:
            n *= p
            fac[p] = fac.get(p, 0) + 1
    want = 1
    for p, e in fac.items():
        want *= (p - 1) * p ** (e - 1)
    assert PH(n) == want, n
lim = random.randint(1, 500)
assert TS(lim) == sum(PH(k) for k in range(1, lim + 1)), lim
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def phi(n):
    if not _isint(n) or not 1 <= n <= 10 ** 12:
        raise ValueError("n must be an int from 1 to 10**12")
    result, m, p = n, n, 2
    while p * p <= m:
        if m % p == 0:
            result = result // p * (p - 1)
            while m % p == 0:
                m //= p
        p += 1 if p == 2 else 2
    if m > 1:
        result = result // m * (m - 1)
    return result


def totient_sum(limit):
    if not _isint(limit) or not 1 <= limit <= 100000:
        raise ValueError("limit must be an int from 1 to 100000")
    t = list(range(limit + 1))
    for p in range(2, limit + 1):
        if t[p] == p:
            for m in range(p, limit + 1, p):
                t[m] -= t[m] // p
    return sum(t[1:])
''')


task("v8_11_goldbach_pairs", r'''
Write `goldbach_pairs(n)` and `goldbach_smallest(n)` about writing an even number as a sum of two primes.

`n` must be an even int with 4 <= n <= 1000000 for both functions; a bool is not accepted, and anything else (odd n,
n below 4 or above 1000000, a float, a str) raises ValueError.

goldbach_pairs(n) returns how many pairs of primes (p, q) with p <= q and p + q == n exist. Each unordered pair counts
once, and p == q is allowed (4 = 2 + 2).

goldbach_smallest(n) returns the pair (p, q) with p <= q, p + q == n and p as small as possible, as a tuple of ints.
Every even n in the allowed range has at least one pair.

Find the primes up to n with the sieve of Eratosthenes (a list of flags, crossing out the multiples of each prime
starting at its square); testing every candidate by trial division is too slow for n near 1000000.

Examples:
- goldbach_pairs(4) == 1 and goldbach_pairs(10) == 2 (3 + 7 and 5 + 5) and goldbach_pairs(100) == 6
- goldbach_pairs(1000000) == 5402
- goldbach_smallest(4) == (2, 2) and goldbach_smallest(100) == (3, 97) and goldbach_smallest(98) == (19, 79)
- ValueError: goldbach_pairs(7), goldbach_pairs(2), goldbach_pairs(1000002), goldbach_pairs(True), goldbach_smallest(10.0)
''', r'''
import random

GP, GS = goldbach_pairs, goldbach_smallest

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert GP(4) == 1 and GP(10) == 2 and GP(100) == 6 and GP(1000000) == 5402 and GP(6) == 1
assert GS(4) == (2, 2) and GS(100) == (3, 97) and GS(98) == (19, 79) and GS(6) == (3, 3)
for f in (GP, GS):
    for bad in (7, 2, 0, -4, 1000002, True, 10.0, "10", None, 3):
        assert rej(f, bad), (f, bad)

def isprime(k):
    if k < 2:
        return False
    d = 2
    while d * d <= k:
        if k % d == 0:
            return False
        d += 1
    return True

random.seed(8011)
for _ in range(120):
    n = 2 * random.randint(2, 1500)
    pairs = [(p, n - p) for p in range(2, n // 2 + 1) if isprime(p) and isprime(n - p)]
    assert GP(n) == len(pairs) and GS(n) == pairs[0], n
n = 2 * random.randint(400000, 500000)
p, q = GS(n)
assert p + q == n and isprime(p) and isprime(q) and not any(isprime(r) and isprime(n - r) for r in range(2, p)), n
''', r'''
def _check(n):
    if not isinstance(n, int) or isinstance(n, bool) or n % 2 or not 4 <= n <= 1000000:
        raise ValueError("n must be an even int from 4 to 1000000")


def _sieve(n):
    flags = bytearray([1]) * (n + 1)
    flags[0] = flags[1] = 0
    p = 2
    while p * p <= n:
        if flags[p]:
            flags[p * p::p] = bytearray(len(range(p * p, n + 1, p)))
        p += 1
    return flags


def goldbach_pairs(n):
    _check(n)
    f = _sieve(n)
    return sum(1 for p in range(2, n // 2 + 1) if f[p] and f[n - p])


def goldbach_smallest(n):
    _check(n)
    f = _sieve(n)
    for p in range(2, n // 2 + 1):
        if f[p] and f[n - p]:
            return (p, n - p)
''')


task("v8_12_pascal_mod", r'''
Write `pascal_row_mod(n, m)` and `count_divisible(n, m)` about one row of Pascal's triangle.

Row n of Pascal's triangle is the list of binomial coefficients C(n, 0), C(n, 1), ..., C(n, n), so it has n + 1
entries: row 0 is [1], row 4 is [1, 4, 6, 4, 1].

For both functions `n` must be an int from 0 to 2000 and `m` an int from 2 to 10**9; a bool is never accepted as an int.
Anything else raises ValueError.

pascal_row_mod(n, m) returns row n with every entry replaced by its remainder modulo m, as a list of ints.

count_divisible(n, m) returns how many entries of row n are divisible by m (that is, are 0 in pascal_row_mod(n, m)).

The coefficients of row 2000 have hundreds of digits, which Python's ints handle exactly. Either build the row from
C(n, k) = C(n, k - 1) * (n - k + 1) // k with exact integers and reduce at the end, or build rows 0..n by adding
neighbours modulo m. Do not use floating point.

Examples:
- pascal_row_mod(4, 10) == [1, 4, 6, 4, 1] and pascal_row_mod(0, 7) == [1]
- pascal_row_mod(5, 3) == [1, 2, 1, 1, 2, 1] (row 5 is 1, 5, 10, 10, 5, 1)
- pascal_row_mod(10, 1000000000) == [1, 10, 45, 120, 210, 252, 210, 120, 45, 10, 1]
- count_divisible(5, 5) == 4 and count_divisible(4, 2) == 3 and count_divisible(8, 2) == 7
- ValueError: pascal_row_mod(-1, 5), pascal_row_mod(2001, 5), pascal_row_mod(3, 1), pascal_row_mod(3, 10 ** 9 + 1),
  pascal_row_mod(True, 5), count_divisible(3, 2.0)
''', r'''
import random
from math import comb

PR, CD = pascal_row_mod, count_divisible

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert PR(4, 10) == [1, 4, 6, 4, 1] and PR(0, 7) == [1] and PR(5, 3) == [1, 2, 1, 1, 2, 1]
assert PR(10, 10 ** 9) == [1, 10, 45, 120, 210, 252, 210, 120, 45, 10, 1] and PR(1, 2) == [1, 1]
assert CD(5, 5) == 4 and CD(4, 2) == 3 and CD(8, 2) == 7 and CD(0, 2) == 0
for f in (PR, CD):
    for bad in ((-1, 5), (2001, 5), (3, 1), (3, 10 ** 9 + 1), (True, 5), (3, 2.0), (3, False), ("3", 5), (3, None)):
        assert rej(f, *bad), (f, bad)

random.seed(8012)
for _ in range(150):
    n, m = random.randint(0, 120), random.choice([2, 3, 4, 7, 10, 12, 97, random.randint(2, 10 ** 9)])
    want = [comb(n, k) % m for k in range(n + 1)]
    assert PR(n, m) == want, (n, m)
    assert CD(n, m) == want.count(0), (n, m)
n, m = 2000, random.randint(2, 10 ** 9)
assert PR(n, m) == [comb(n, k) % m for k in range(n + 1)]
assert CD(2000, 2) == 2001 - 2 ** bin(2000).count("1")
''', r'''
def _check(n, m):
    for x in (n, m):
        if not isinstance(x, int) or isinstance(x, bool):
            raise ValueError("n and m must be ints")
    if not 0 <= n <= 2000 or not 2 <= m <= 10 ** 9:
        raise ValueError("n or m out of range")


def pascal_row_mod(n, m):
    _check(n, m)
    row, c = [1], 1
    for k in range(1, n + 1):
        c = c * (n - k + 1) // k
        row.append(c)
    return [x % m for x in row]


def count_divisible(n, m):
    return pascal_row_mod(n, m).count(0)
''')


task("v8_13_primitive_triples", r'''
Write `primitive_triples(limit)` and `count_triples(limit)` for primitive Pythagorean triples.

A Pythagorean triple is three positive ints (a, b, c) with a < b and a*a + b*b == c*c. It is primitive when a, b and
c have no common divisor above 1. For both functions `limit` must be an int from 0 to 100000 (a bool is not accepted),
otherwise raise ValueError.

primitive_triples(limit) returns the list of all primitive triples with c <= limit, each as a tuple (a, b, c),
sorted by c and, for equal c, by a.

count_triples(limit) returns how many there are, which is len(primitive_triples(limit)).

Euclid's formula produces every primitive triple exactly once: for ints m > k > 0 with gcd(m, k) == 1 and m - k odd,
the numbers m*m - k*k, 2*m*k and m*m + k*k form a primitive triple (swap the first two when needed so that a < b).
Loop over m while m*m + 1 <= limit. Checking every (a, b) pair is far too slow for limit = 100000.

Examples:
- primitive_triples(30) == [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29)]
- primitive_triples(4) == [] and primitive_triples(5) == [(3, 4, 5)]
- primitive_triples(65)[-3:] == [(11, 60, 61), (16, 63, 65), (33, 56, 65)]
- count_triples(100) == 16 and count_triples(0) == 0 and count_triples(100000) == 15919
- ValueError: primitive_triples(-1), primitive_triples(100001), primitive_triples(True), count_triples(10.0)
''', r'''
import random
from math import gcd, isqrt

PT, CT = primitive_triples, count_triples

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert PT(30) == [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29)] and PT(4) == [] and PT(5) == [(3, 4, 5)]
assert PT(65)[-3:] == [(11, 60, 61), (16, 63, 65), (33, 56, 65)]
assert CT(100) == 16 and CT(0) == 0 and CT(100000) == 15919 and PT(0) == []
for f in (PT, CT):
    for bad in (-1, 100001, True, 10.0, "5", None):
        assert rej(f, bad), (f, bad)

def brute(lim):
    out = []
    for c in range(1, lim + 1):
        for a in range(1, c):
            b2 = c * c - a * a
            b = isqrt(b2)
            if b * b == b2 and a < b and gcd(a, b) == 1:
                out.append((a, b, c))
    return out

random.seed(8013)
for lim in [random.randint(0, 400) for _ in range(6)] + [1, 13, 25]:
    assert PT(lim) == brute(lim), lim
    assert CT(lim) == len(brute(lim)), lim
big = PT(100000)
assert len(big) == 15919 and big == sorted(big, key=lambda t: (t[2], t[0]))
assert all(a < b and a * a + b * b == c * c and gcd(a, gcd(b, c)) == 1 and c <= 100000 for a, b, c in random.sample(big, 300))
''', r'''
from math import gcd


def _check(limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 100000:
        raise ValueError("limit must be an int from 0 to 100000")


def primitive_triples(limit):
    _check(limit)
    out, m = [], 2
    while m * m + 1 <= limit:
        for k in range(1, m):
            if (m - k) % 2 == 1 and gcd(m, k) == 1:
                c = m * m + k * k
                if c <= limit:
                    a, b = m * m - k * k, 2 * m * k
                    out.append((min(a, b), max(a, b), c))
        m += 1
    out.sort(key=lambda t: (t[2], t[0]))
    return out


def count_triples(limit):
    return len(primitive_triples(limit))
''')


task("v8_14_happy_count", r'''
Write `is_happy(n)` and `happy_count(limit)` for happy numbers.

Start from a positive int and repeatedly replace it by the sum of the squares of its decimal digits. If this reaches
1, the starting number is happy. Otherwise the numbers fall into a cycle that never contains 1 (the cycle through 4,
16, 37, 58, 89, 145, 42, 20), and the number is not happy.

is_happy(n): `n` must be an int >= 1 (no bool), otherwise ValueError; there is no upper limit. Return True or False.
Detect the cycle by remembering the numbers seen so far (or by stopping at 4).

happy_count(limit): `limit` must be an int from 0 to 100000 (no bool), otherwise ValueError. Return how many happy
numbers there are from 1 to limit inclusive. After one step every number up to 100000 has become at most 405
(5 digits of 9 give 5 * 81), so answering the small numbers once and looking each first step up keeps this fast.

Examples:
- is_happy(1) is True and is_happy(7) is True (7 -> 49 -> 97 -> 130 -> 10 -> 1) and is_happy(19) is True
- is_happy(4) is False and is_happy(2) is False and is_happy(10 ** 50) is True
- happy_count(10) == 3 (1, 7 and 10) and happy_count(100) == 20 and happy_count(0) == 0
- happy_count(100000) == 14377
- ValueError: is_happy(0), is_happy(-7), is_happy(True), is_happy(7.0), happy_count(-1), happy_count(100001)
''', r'''
import random

IH, HC = is_happy, happy_count

def rej(f, x):
    try:
        f(x)
    except ValueError:
        return True
    return False

assert IH(1) is True and IH(7) is True and IH(19) is True and IH(4) is False and IH(2) is False and IH(10 ** 50) is True
assert HC(10) == 3 and HC(100) == 20 and HC(0) == 0 and HC(100000) == 14377 and HC(1) == 1
for bad in (0, -7, True, 7.0, "7", None):
    assert rej(IH, bad), bad
for bad in (-1, 100001, True, 5.0, None):
    assert rej(HC, bad), bad

def ohappy(n):
    slow = fast = n
    step = lambda k: sum(int(c) ** 2 for c in str(k))
    while True:
        slow, fast = step(slow), step(step(fast))
        if fast == 1 or slow == 1:
            return True
        if slow == fast:
            return False

random.seed(8014)
for _ in range(500):
    n = random.choice([random.randint(1, 1000), random.randint(1, 10 ** 9), random.randint(1, 10 ** 40)])
    assert IH(n) is ohappy(n), n
for lim in [random.randint(0, 3000) for _ in range(5)]:
    assert HC(lim) == sum(ohappy(k) for k in range(1, lim + 1)), lim
''', r'''
def _step(n):
    s = 0
    while n:
        n, d = divmod(n, 10)
        s += d * d
    return s


def is_happy(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be an int >= 1")
    seen = set()
    while n != 1 and n not in seen:
        seen.add(n)
        n = _step(n)
    return n == 1


def happy_count(limit):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 100000:
        raise ValueError("limit must be an int from 0 to 100000")
    small = [False] + [is_happy(k) for k in range(1, 406)]
    return sum(1 for k in range(1, limit + 1) if small[_step(k)])
''')


task("v8_15_egyptian_greedy", r'''
Write `egyptian(p, q)` and `unit_sum(denominators)` for Egyptian fractions (sums of distinct fractions 1/n).

egyptian(p, q) writes the fraction p/q as a sum of unit fractions with the greedy method: take the largest unit
fraction 1/n that is not larger than what is left (the smallest such n is ceil(left_den / left_num)), subtract it,
and repeat until nothing is left. Return the list of denominators in the order they were taken; they come out strictly
increasing. `p` and `q` must be ints with 1 <= p < q <= 200 (no bool), otherwise ValueError. Work with exact integers:
the denominators can have more than 1000 digits, so floating point gives wrong answers.

unit_sum(denominators): `denominators` must be a list or tuple of ints >= 1 (no bool; repeats are allowed), otherwise
ValueError. Return the sum of 1/d over the list as a reduced fraction, a tuple (numerator, denominator) with the
denominator >= 1; the empty list gives (0, 1).

Examples:
- egyptian(2, 3) == [2, 6] and egyptian(1, 7) == [7] and egyptian(4, 13) == [4, 18, 468]
- egyptian(5, 121) == [25, 757, 763309, 873960180913, 1527612795642093418846225]
- unit_sum([2, 6]) == (2, 3) and unit_sum([2, 3, 6]) == (1, 1) and unit_sum([]) == (0, 1) and unit_sum((4, 4)) == (1, 2)
- unit_sum(egyptian(5, 121)) == (5, 121)
- ValueError: egyptian(3, 3), egyptian(0, 5), egyptian(1, 201), egyptian(True, 3), egyptian(1.0, 3), unit_sum([0]),
  unit_sum([2, True]), unit_sum(None)
''', r'''
import random
from fractions import Fraction

EG, US = egyptian, unit_sum

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert EG(2, 3) == [2, 6] and EG(1, 7) == [7] and EG(4, 13) == [4, 18, 468]
assert EG(5, 121) == [25, 757, 763309, 873960180913, 1527612795642093418846225]
assert US([2, 6]) == (2, 3) and US([2, 3, 6]) == (1, 1) and US([]) == (0, 1) and US((4, 4)) == (1, 2)
assert US(EG(5, 121)) == (5, 121) and US([1]) == (1, 1) and US([3, 6]) == (1, 2)
for bad in ((3, 3), (0, 5), (1, 201), (True, 3), (1.0, 3), (5, 2), (-1, 3), (1, None), ("1", 3)):
    assert rej(EG, *bad), bad
for bad in ([0], [2, True], None, [2, -3], [1.5], "23", [None]):
    assert rej(US, bad), bad

random.seed(8015)
for _ in range(400):
    q = random.randint(2, 200)
    p = random.randint(1, q - 1)
    ds = EG(p, q)
    left = Fraction(p, q)
    for d in ds:
        assert Fraction(1, d) <= left and (d == 1 or Fraction(1, d - 1) > left), (p, q, ds)
        left -= Fraction(1, d)
    assert left == 0 and ds == sorted(set(ds)), (p, q)
    f = Fraction(p, q)
    assert US(ds) == (f.numerator, f.denominator), (p, q)
for _ in range(300):
    ds = [random.randint(1, 60) for _ in range(random.randint(0, 8))]
    s = sum((Fraction(1, d) for d in ds), Fraction(0))
    assert US(ds) == (s.numerator, s.denominator), ds
''', r'''
from math import gcd


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def egyptian(p, q):
    if not _isint(p) or not _isint(q) or not 1 <= p < q <= 200:
        raise ValueError("need ints with 1 <= p < q <= 200")
    out = []
    while p:
        n = (q + p - 1) // p
        out.append(n)
        p, q = p * n - q, q * n
        g = gcd(p, q)
        p, q = p // g, q // g
    return out


def unit_sum(denominators):
    if not isinstance(denominators, (list, tuple)) or not all(_isint(d) and d >= 1 for d in denominators):
        raise ValueError("denominators must be ints >= 1")
    num, den = 0, 1
    for d in denominators:
        num, den = num * d + den, den * d
        g = gcd(num, den)
        num, den = num // g, den // g
    return num, den
''')


# --- graphs_geometry ---

task("v8_16_two_color", r'''
Write `two_color(n, edges)` that colors the vertices of an undirected graph with two colors so that every edge joins
vertices of different colors, or reports that this is impossible.

The vertices are 0 to n-1. `edges` is a list or tuple of pairs (a, b), each a tuple or list of two ints, meaning an
edge between a and b. Repeated edges are allowed. A pair (a, a) is a loop, and a graph with a loop cannot be colored.

Return a list `color` of length n with color[v] in {0, 1} and color[a] != color[b] for every edge, choosing the list
that is smallest in lexicographic order (compare lists as Python does). Return None when no such coloring exists,
which happens exactly when the graph has a cycle of odd length (a loop counts).

The smallest list is built like this: go through the vertices in increasing order; when a vertex has no color yet,
give it color 0 and color its whole connected component by breadth-first search, each neighbour getting the opposite
color. Meeting an edge whose two ends got the same color means no coloring exists.

Validation (ValueError): n is not an int >= 0; edges is not a list or tuple; a pair is not a tuple or list of two ints
in 0..n-1. A bool is never accepted as an int. n can be up to 100000 with up to 200000 edges.

Examples:
- two_color(4, [(0, 1), (1, 2), (2, 3)]) == [0, 1, 0, 1]
- two_color(3, [(0, 1), (1, 2), (2, 0)]) is None and two_color(1, [(0, 0)]) is None
- two_color(3, []) == [0, 0, 0] and two_color(4, [(3, 2)]) == [0, 0, 0, 1] and two_color(0, []) == []
- ValueError: two_color(2, [(0, 2)]), two_color(-1, []), two_color(2, [(0,)]), two_color(2, None), two_color(True, [])
''', r'''
import random
from itertools import product

TC = two_color

def rej(*a):
    try:
        TC(*a)
    except ValueError:
        return True
    return False

assert TC(4, [(0, 1), (1, 2), (2, 3)]) == [0, 1, 0, 1] and TC(3, [(0, 1), (1, 2), (2, 0)]) is None and TC(1, [(0, 0)]) is None
assert TC(3, []) == [0, 0, 0] and TC(4, [(3, 2)]) == [0, 0, 0, 1] and TC(0, []) == [] and TC(2, ([1, 0], [0, 1])) == [0, 1]
assert TC(5, [(4, 1), (1, 3), (3, 0)]) == [0, 0, 0, 1, 1]
for bad in [(2, [(0, 2)]), (-1, []), (2, [(0,)]), (2, None), (True, []), (2.0, []), (2, [(0, True)]), (2, [(0, 1.0)]),
            (2, [None]), (2, [(0, 1, 1)]), (2, [(-1, 0)]), (2, "01")]:
    assert rej(*bad), bad

def brute(n, edges):
    for c in product((0, 1), repeat=n):
        if all(c[a] != c[b] for a, b in edges):
            return list(c)
    return None

random.seed(8016)
for _ in range(400):
    n = random.randint(0, 9)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(random.randint(0, 9))] if n else []
    edges = [e for e in edges if e[0] != e[1] or random.random() < 0.05]
    assert TC(n, edges) == brute(n, edges), (n, edges)
n = 30000
side = [random.randrange(2) for _ in range(n)]
edges = []
while len(edges) < 2 * n:
    a, b = random.randrange(n), random.randrange(n)
    if side[a] != side[b]:
        edges.append((a, b))
col = TC(n, edges)
parent = list(range(n))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
for a, b in edges:
    parent[find(a)] = find(b)
first = {}
for v in range(n):
    first.setdefault(find(v), v)
assert all(col[a] != col[b] for a, b in edges) and all(col[v] == 0 for v in first.values())
a, b = random.sample([v for v in range(n) if side[v] == 0], 2)
assert TC(n, edges + [(a, b)]) is None or find(a) != find(b)
''', r'''
from collections import deque


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def two_color(n, edges):
    if not _isint(n) or n < 0:
        raise ValueError("n must be an int >= 0")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a list or tuple")
    adj = [[] for _ in range(n)]
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2 or not all(_isint(x) and 0 <= x < n for x in e):
            raise ValueError("bad edge")
        adj[e[0]].append(e[1])
        adj[e[1]].append(e[0])
    color = [-1] * n
    for s in range(n):
        if color[s] >= 0:
            continue
        color[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if color[v] < 0:
                    color[v] = 1 - color[u]
                    queue.append(v)
                elif color[v] == color[u]:
                    return None
    return color
''')


task("v8_17_lattice_segment", r'''
Write `segment_lattice_count(p, q)` and `segment_lattice_points(p, q)` for the integer points on a line segment.

`p` and `q` are the two ends of a segment in the plane, each a tuple or list of two ints (x, y) with
-10**9 <= x, y <= 10**9; a bool is never accepted as an int. Anything else raises ValueError. p and q may be equal.

segment_lattice_count(p, q) returns how many points with integer coordinates lie on the closed segment from p to q, the two
ends included. For integer ends this is gcd(|x2 - x1|, |y2 - y1|) + 1, which is 1 when p == q.

segment_lattice_points(p, q) returns those points as a list of tuples (x, y), in order along the segment from p to q, so the
first is p and the last is q. Consecutive points differ by the same step (dx / g, dy / g), where (dx, dy) = q - p and
g is the gcd above. It is only called when the answer has at most 100000 points.

Examples:
- segment_lattice_count((0, 0), (6, 4)) == 3 and segment_lattice_points((0, 0), (6, 4)) == [(0, 0), (3, 2), (6, 4)]
- segment_lattice_count((1, 1), (1, 1)) == 1 and segment_lattice_points([1, 1], [1, 1]) == [(1, 1)]
- segment_lattice_count((0, 0), (-5, 0)) == 6
- segment_lattice_points((2, 5), (-1, -1)) == [(2, 5), (1, 3), (0, 1), (-1, -1)]
- segment_lattice_count((0, 0), (10 ** 9, 10 ** 9 - 1)) == 2
- ValueError: segment_lattice_count((0, 0), (1,)), segment_lattice_count([0, 0], (1.5, 2)), segment_lattice_count((True, 0), (1, 1)),
  segment_lattice_count((0, 0), (10 ** 9 + 1, 0)), segment_lattice_points(None, (0, 0))
''', r'''
import random
from math import gcd

LC, LP = segment_lattice_count, segment_lattice_points

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert LC((0, 0), (6, 4)) == 3 and LP((0, 0), (6, 4)) == [(0, 0), (3, 2), (6, 4)] and LC((1, 1), (1, 1)) == 1
assert LP([1, 1], [1, 1]) == [(1, 1)] and LC((0, 0), (-5, 0)) == 6 and LP((2, 5), (-1, -1)) == [(2, 5), (1, 3), (0, 1), (-1, -1)]
assert LC((0, 0), (10 ** 9, 10 ** 9 - 1)) == 2 and LC((-10 ** 9, -10 ** 9), (10 ** 9, 10 ** 9)) == 2 * 10 ** 9 + 1
assert LP((0, 3), (0, -1)) == [(0, 3), (0, 2), (0, 1), (0, 0), (0, -1)]
for f in (LC, LP):
    for bad in [((0, 0), (1,)), ([0, 0], (1.5, 2)), ((True, 0), (1, 1)), ((0, 0), (10 ** 9 + 1, 0)), (None, (0, 0)),
                ((0, 0, 0), (1, 1)), ("ab", (1, 1)), ((0, 0), (1, -10 ** 9 - 1))]:
        assert rej(f, *bad), (f, bad)

def brute(p, q):
    (x1, y1), (x2, y2) = p, q
    pts = [(x, y) for x in range(min(x1, x2), max(x1, x2) + 1) for y in range(min(y1, y2), max(y1, y2) + 1)
           if (x - x1) * (y2 - y1) == (y - y1) * (x2 - x1)]
    return sorted(pts, key=lambda t: abs(t[0] - x1) + abs(t[1] - y1))

random.seed(8017)
for _ in range(800):
    p = (random.randint(-12, 12), random.randint(-12, 12))
    q = (random.randint(-12, 12), random.randint(-12, 12))
    want = brute(p, q)
    assert LP(p, q) == want and LC(p, q) == len(want), (p, q)
for _ in range(200):
    g = random.randint(1, 1000)
    d = (random.randint(-10 ** 5, 10 ** 5), random.randint(-10 ** 5, 10 ** 5))
    while d == (0, 0) or gcd(*d) != 1:
        d = (random.randint(-10 ** 5, 10 ** 5), random.randint(-10 ** 5, 10 ** 5))
    p = (random.randint(-10 ** 8, 10 ** 8), random.randint(-10 ** 8, 10 ** 8))
    q = (p[0] + g * d[0], p[1] + g * d[1])
    assert LC(p, q) == g + 1, (p, q)
    pts = LP(p, q)
    assert len(pts) == g + 1 and pts[0] == p and pts[-1] == q and pts[1] == (p[0] + d[0], p[1] + d[1]), (p, q)
''', r'''
from math import gcd


def _point(p):
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise ValueError("a point is two ints")
    for v in p:
        if not isinstance(v, int) or isinstance(v, bool) or not -10 ** 9 <= v <= 10 ** 9:
            raise ValueError("coordinates must be ints with |v| <= 10**9")
    return p[0], p[1]


def segment_lattice_count(p, q):
    (x1, y1), (x2, y2) = _point(p), _point(q)
    return gcd(x2 - x1, y2 - y1) + 1


def segment_lattice_points(p, q):
    (x1, y1), (x2, y2) = _point(p), _point(q)
    g = gcd(x2 - x1, y2 - y1)
    if g == 0:
        return [(x1, y1)]
    dx, dy = (x2 - x1) // g, (y2 - y1) // g
    return [(x1 + i * dx, y1 + i * dy) for i in range(g + 1)]
''')


task("v8_18_closest_pair", r'''
Write `closest_pair(points)` that finds the two points of a list that are closest together.

`points` must be a list or tuple of 2 to 500 points, each a tuple or list of two ints (x, y) with
-10**6 <= x, y <= 10**6; a bool is never accepted as an int. Otherwise raise ValueError. Points may repeat.

Distances are compared exactly as squared Euclidean distances, (x1 - x2)**2 + (y1 - y2)**2, which are ints, so there
is no rounding. Return a tuple (d2, i, j) with i < j: d2 is the smallest squared distance between two different
positions i and j of the list, and (i, j) is the pair of positions that attains it. When several pairs attain it,
return the one with the smallest i, and among those the smallest j. Two equal points at different positions have
distance 0.

With at most 500 points, checking every pair (i, j) with i < j in order and keeping a pair only when it is strictly
closer than the best so far is fast enough and gives the required tie order.

Examples:
- closest_pair([(0, 0), (5, 5), (1, 1)]) == (2, 0, 2)
- closest_pair([(0, 0), (3, 4)]) == (25, 0, 1)
- closest_pair([(1, 1), (0, 0), (1, 1)]) == (0, 0, 2)
- closest_pair([(0, 0), (1, 0), (5, 0), (6, 0)]) == (1, 0, 1)
- closest_pair(((9, 9), [2, 2], (2, 3), (8, 9))) == (1, 0, 3)
- ValueError: closest_pair([(0, 0)]), closest_pair([(0, 0), (1,)]), closest_pair([(0, 0), (True, 1)]),
  closest_pair([(0, 0), (10 ** 6 + 1, 0)]), closest_pair(None)
''', r'''
import random
from itertools import combinations

CP = closest_pair

def rej(x):
    try:
        CP(x)
    except ValueError:
        return True
    return False

assert CP([(0, 0), (5, 5), (1, 1)]) == (2, 0, 2) and CP([(0, 0), (3, 4)]) == (25, 0, 1)
assert CP([(1, 1), (0, 0), (1, 1)]) == (0, 0, 2) and CP([(0, 0), (1, 0), (5, 0), (6, 0)]) == (1, 0, 1)
assert CP(((9, 9), [2, 2], (2, 3), (8, 9))) == (1, 0, 3)
assert CP([(-10 ** 6, -10 ** 6), (10 ** 6, 10 ** 6)]) == (8 * 10 ** 12, 0, 1)
for bad in ([(0, 0)], [(0, 0), (1,)], [(0, 0), (True, 1)], [(0, 0), (10 ** 6 + 1, 0)], None, [], [(0, 0), (1.0, 1)],
            [(0, 0), None], [(0, 0)] * 501, "ab"):
    assert rej(bad), bad

def brute(pts):
    return min(((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2, i, j)
               for i, j in combinations(range(len(pts)), 2))

random.seed(8018)
for _ in range(400):
    k = random.randint(2, 12)
    span = random.choice([2, 5, 50, 10 ** 6])
    pts = [(random.randint(-span, span), random.randint(-span, span)) for _ in range(k)]
    assert CP(pts) == brute(pts), pts
for _ in range(2):
    pts = [(random.randint(-10 ** 6, 10 ** 6), random.randint(-10 ** 6, 10 ** 6)) for _ in range(500)]
    assert CP(pts) == brute(pts)
''', r'''
def closest_pair(points):
    if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 500:
        raise ValueError("need 2 to 500 points")
    pts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("a point is two ints")
        for v in p:
            if not isinstance(v, int) or isinstance(v, bool) or not -10 ** 6 <= v <= 10 ** 6:
                raise ValueError("coordinates must be ints with |v| <= 10**6")
        pts.append((p[0], p[1]))
    best = None
    for i in range(len(pts)):
        xi, yi = pts[i]
        for j in range(i + 1, len(pts)):
            d2 = (xi - pts[j][0]) ** 2 + (yi - pts[j][1]) ** 2
            if best is None or d2 < best[0]:
                best = (d2, i, j)
    return best
''')


task("v8_19_euler_trail", r'''
Write `euler_trail(n, edges)` that finds a walk through a directed graph using every edge exactly once.

The vertices are 0 to n-1 and `edges` is a list or tuple of pairs (a, b), each a tuple or list of two ints, meaning a
directed edge from a to b. Repeated edges and loops (a, a) are allowed; each copy must be used once.

Return the walk as the list of vertices visited, so it has len(edges) + 1 entries and consecutive entries follow the
edges. Return [] when there are no edges, and None when no such walk exists. A walk exists exactly when every edge can
be reached and the degrees work out: either every vertex has as many outgoing as incoming edges (then the walk may
start at any vertex with an edge, and starts at the smallest one), or exactly one vertex has one more outgoing than
incoming edge (the walk must start there), exactly one has one more incoming than outgoing, and all others are equal.

Among all walks that use every edge once, return the one whose vertex list is smallest in lexicographic order.
Hierholzer's algorithm gives exactly that walk when, at every vertex, it always follows the smallest unused outgoing
edge first: keep a stack starting at the start vertex; while the top vertex has an unused edge, push its smallest
target; otherwise pop it onto the result; finally reverse the result.

Validation (ValueError): n is not an int >= 0; edges is not a list or tuple; a pair is not a tuple or list of two ints
in 0..n-1. A bool is never accepted as an int. n can be up to 100000 with up to 200000 edges.

Examples:
- euler_trail(3, [(0, 1), (1, 2), (2, 0)]) == [0, 1, 2, 0]
- euler_trail(4, [(0, 1), (1, 2), (1, 3), (3, 1)]) == [0, 1, 3, 1, 2]
- euler_trail(3, [(0, 1), (0, 2), (1, 0), (2, 0)]) == [0, 1, 0, 2, 0]
- euler_trail(2, [(0, 1), (0, 1)]) is None and euler_trail(4, [(0, 1), (1, 0), (2, 3), (3, 2)]) is None
- euler_trail(3, []) == [] and euler_trail(2, [(1, 1)]) == [1, 1]
- ValueError: euler_trail(2, [(0, 2)]), euler_trail(-1, []), euler_trail(2, [(0,)]), euler_trail(2, None)
''', r'''
import random

ET = euler_trail

def rej(*a):
    try:
        ET(*a)
    except ValueError:
        return True
    return False

assert ET(3, [(0, 1), (1, 2), (2, 0)]) == [0, 1, 2, 0] and ET(4, [(0, 1), (1, 2), (1, 3), (3, 1)]) == [0, 1, 3, 1, 2]
assert ET(3, [(0, 1), (0, 2), (1, 0), (2, 0)]) == [0, 1, 0, 2, 0] and ET(2, [(0, 1), (0, 1)]) is None
assert ET(4, [(0, 1), (1, 0), (2, 3), (3, 2)]) is None and ET(3, []) == [] and ET(2, [(1, 1)]) == [1, 1]
assert ET(0, []) == [] and ET(2, ([1, 0],)) == [1, 0] and ET(3, [(2, 1), (1, 2), (1, 0)]) == [1, 2, 1, 0]
for bad in [(2, [(0, 2)]), (-1, []), (2, [(0,)]), (2, None), (True, []), (2.0, []), (2, [(0, True)]), (2, [(0, 1.0)]),
            (2, [None]), (2, [(0, 1, 1)]), (2, [(-1, 0)]), (2, "01")]:
    assert rej(*bad), bad

def brute(n, edges):
    m, best = len(edges), None
    if m == 0:
        return []
    def go(path, used):
        nonlocal best
        if len(path) == m + 1:
            if best is None or path < best:
                best = list(path)
            return
        for k in range(m):
            if not used >> k & 1 and edges[k][0] == path[-1]:
                path.append(edges[k][1])
                go(path, used | 1 << k)
                path.pop()
    for s in range(n):
        go([s], 0)
    return best

random.seed(8019)
for _ in range(300):
    n = random.randint(1, 4)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(random.randint(0, 6))]
    assert ET(n, edges) == brute(n, edges), (n, edges)
n = 2000
cycle = list(range(n))
random.shuffle(cycle)
edges = [(cycle[i], cycle[(i + 1) % n]) for i in range(n)] + [(random.randrange(n),) * 2 for _ in range(500)]
random.shuffle(edges)
w = ET(n, edges)
assert len(w) == len(edges) + 1 and w[0] == 0 and sorted(zip(w, w[1:])) == sorted(map(tuple, edges))
''', r'''
def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def euler_trail(n, edges):
    if not _isint(n) or n < 0:
        raise ValueError("n must be an int >= 0")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a list or tuple")
    out, indeg = [[] for _ in range(n)], [0] * n
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2 or not all(_isint(x) and 0 <= x < n for x in e):
            raise ValueError("bad edge")
        out[e[0]].append(e[1])
        indeg[e[1]] += 1
    if not edges:
        return []
    diff = [len(out[v]) - indeg[v] for v in range(n)]
    starts = [v for v in range(n) if diff[v] == 1]
    if any(abs(d) > 1 for d in diff) or len(starts) > 1 or diff.count(-1) != len(starts):
        return None
    start = starts[0] if starts else min(v for v in range(n) if out[v])
    for targets in out:
        targets.sort(reverse=True)
    stack, walk = [start], []
    while stack:
        v = stack[-1]
        if out[v]:
            stack.append(out[v].pop())
        else:
            walk.append(stack.pop())
    walk.reverse()
    return walk if len(walk) == len(edges) + 1 else None
''')


task("v8_20_triangle_kind", r'''
Write `triangle_kind(a, b, c)` that classifies the triangle with corners a, b and c.

Each corner is a tuple or list of two ints (x, y) with -10**9 <= x, y <= 10**9; a bool is never accepted as an int.
Anything else raises ValueError.

If the three corners lie on one line (this includes two or three equal corners), return the str "degenerate". Test
it exactly with the cross product: (b - a) x (c - a) == 0.

Otherwise return a tuple (sides, angle) of two str:
- sides is "isosceles" when at least two sides have the same length and "scalene" otherwise. An equilateral triangle
  cannot have all three corners at integer points, so it never occurs.
- angle is "right", "obtuse" or "acute" according to the largest angle. Compare squared side lengths, which are exact
  ints: with s1 <= s2 <= s3 the three squared lengths, the triangle is right when s3 == s1 + s2, obtuse when
  s3 > s1 + s2 and acute when s3 < s1 + s2.

Examples:
- triangle_kind((0, 0), (4, 0), (0, 3)) == ("scalene", "right")
- triangle_kind((0, 0), (2, 0), (1, 3)) == ("isosceles", "acute")
- triangle_kind((0, 0), (4, 0), (1, 1)) == ("scalene", "obtuse")
- triangle_kind((0, 0), (1, 0), [0, 1]) == ("isosceles", "right")
- triangle_kind((0, 0), (1, 1), (2, 2)) == "degenerate" and triangle_kind((3, 3), (3, 3), (1, 0)) == "degenerate"
- ValueError: triangle_kind((0, 0), (1, 0), (1,)), triangle_kind((0, 0), (1, 0), (0.5, 1)),
  triangle_kind((0, 0), (True, 0), (0, 1)), triangle_kind((0, 0), (1, 0), (0, 10 ** 9 + 1))
''', r'''
import random

TK = triangle_kind

def rej(*a):
    try:
        TK(*a)
    except ValueError:
        return True
    return False

assert TK((0, 0), (4, 0), (0, 3)) == ("scalene", "right") and TK((0, 0), (2, 0), (1, 3)) == ("isosceles", "acute")
assert TK((0, 0), (4, 0), (1, 1)) == ("scalene", "obtuse") and TK((0, 0), (1, 0), [0, 1]) == ("isosceles", "right")
assert TK((0, 0), (1, 1), (2, 2)) == "degenerate" and TK((3, 3), (3, 3), (1, 0)) == "degenerate"
assert TK((-10 ** 9, -10 ** 9), (10 ** 9, -10 ** 9), (10 ** 9, 10 ** 9 - 1)) == ("scalene", "right")
assert TK((-10 ** 9, 0), (10 ** 9, 0), (0, 10 ** 9)) == ("isosceles", "right") and TK((0, 0), (10 ** 9, 1), (1, 10 ** 9)) == ("isosceles", "acute")
for bad in [((0, 0), (1, 0), (1,)), ((0, 0), (1, 0), (0.5, 1)), ((0, 0), (True, 0), (0, 1)), ((0, 0), (1, 0), (0, 10 ** 9 + 1)),
            ((0, 0), (1, 0), None), ((0, 0), (1, 0), "01"), ((0, 0), (1, 0), (0, 1, 2))]:
    assert rej(*bad), bad

def oracle(a, b, c):
    pts = [a, b, c]
    vec = lambda p, q: (q[0] - p[0], q[1] - p[1])
    u, v = vec(a, b), vec(a, c)
    if u[0] * v[1] - u[1] * v[0] == 0:
        return "degenerate"
    dots = []
    for i in range(3):
        p, q, r = pts[i], pts[(i + 1) % 3], pts[(i + 2) % 3]
        x, y = vec(p, q), vec(p, r)
        dots.append(x[0] * y[0] + x[1] * y[1])
    lens = {(p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for p, q in ((a, b), (b, c), (c, a))}
    angle = "obtuse" if min(dots) < 0 else "right" if min(dots) == 0 else "acute"
    return ("isosceles" if len(lens) < 3 else "scalene", angle)

random.seed(8020)
for _ in range(3000):
    span = random.choice([2, 4, 10, 10 ** 9])
    a, b, c = [(random.randint(-span, span), random.randint(-span, span)) for _ in range(3)]
    assert TK(a, b, c) == oracle(a, b, c), (a, b, c)
''', r'''
def _point(p):
    if not isinstance(p, (tuple, list)) or len(p) != 2:
        raise ValueError("a corner is two ints")
    for v in p:
        if not isinstance(v, int) or isinstance(v, bool) or not -10 ** 9 <= v <= 10 ** 9:
            raise ValueError("coordinates must be ints with |v| <= 10**9")
    return p[0], p[1]


def triangle_kind(a, b, c):
    (x1, y1), (x2, y2), (x3, y3) = _point(a), _point(b), _point(c)
    if (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1) == 0:
        return "degenerate"
    s1, s2, s3 = sorted([(x1 - x2) ** 2 + (y1 - y2) ** 2, (x2 - x3) ** 2 + (y2 - y3) ** 2,
                         (x3 - x1) ** 2 + (y3 - y1) ** 2])
    sides = "isosceles" if s1 == s2 or s2 == s3 else "scalene"
    angle = "right" if s3 == s1 + s2 else "obtuse" if s3 > s1 + s2 else "acute"
    return sides, angle
''')


task("v8_21_manhattan_center", r'''
Write `manhattan_center(points)` that finds the integer point with the smallest total Manhattan distance to a list of
points.

`points` must be a non-empty list or tuple of at most 100000 points, each a tuple or list of two ints (x, y) with
-10**9 <= x, y <= 10**9; a bool is never accepted as an int. Otherwise raise ValueError. Points may repeat.

The Manhattan distance from (x, y) to (px, py) is |x - px| + |y - py|. Return a tuple (x, y, total) where (x, y) is a
point with integer coordinates that makes the sum of the distances to all the points as small as possible, and total
is that sum. When several points attain the smallest sum, return the one with the smallest x, and among those the
smallest y.

The x and y parts of the sum do not depend on each other, so each can be minimized on its own. The sum of |x - px|
over a sorted list of n values is smallest for any x between the two middle values (the single middle value when n is
odd); the smallest such x is the value at position (n - 1) // 2 of the sorted list.

Examples:
- manhattan_center([(1, 1)]) == (1, 1, 0)
- manhattan_center([(0, 0), (2, 2)]) == (0, 0, 4)
- manhattan_center([(1, 5), (2, 1), (9, 3)]) == (2, 3, 12)
- manhattan_center([(0, 0), (0, 10), (10, 0), (10, 10)]) == (0, 0, 40)
- manhattan_center(([3, -1], (3, -1), (-2, 4))) == (3, -1, 10)
- ValueError: manhattan_center([]), manhattan_center([(0,)]), manhattan_center([(0, True)]), manhattan_center(None),
  manhattan_center([(0, 10 ** 9 + 1)])
''', r'''
import random

MC = manhattan_center

def rej(x):
    try:
        MC(x)
    except ValueError:
        return True
    return False

assert MC([(1, 1)]) == (1, 1, 0) and MC([(0, 0), (2, 2)]) == (0, 0, 4) and MC([(1, 5), (2, 1), (9, 3)]) == (2, 3, 12)
assert MC([(0, 0), (0, 10), (10, 0), (10, 10)]) == (0, 0, 40) and MC(([3, -1], (3, -1), (-2, 4))) == (3, -1, 10)
assert MC([(-10 ** 9, 10 ** 9), (10 ** 9, -10 ** 9)]) == (-10 ** 9, -10 ** 9, 4 * 10 ** 9)
for bad in ([], [(0,)], [(0, True)], None, [(0, 10 ** 9 + 1)], [(0, 1.0)], [None], "ab", [(0, 0)] * 100001):
    assert rej(bad), bad

def brute(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    best = None
    for x in range(min(xs), max(xs) + 1):
        for y in range(min(ys), max(ys) + 1):
            t = sum(abs(x - px) + abs(y - py) for px, py in pts)
            if best is None or (t, x, y) < best:
                best = (t, x, y)
    return (best[1], best[2], best[0])

random.seed(8021)
for _ in range(400):
    pts = [(random.randint(-6, 6), random.randint(-6, 6)) for _ in range(random.randint(1, 7))]
    assert MC(pts) == brute(pts), pts
pts = [(random.randint(-10 ** 9, 10 ** 9), random.randint(-10 ** 9, 10 ** 9)) for _ in range(100000)]
x, y, t = MC(pts)
xs, ys = sorted(p[0] for p in pts), sorted(p[1] for p in pts)
assert (x, y) == (xs[49999], ys[49999]) and t == sum(abs(x - a) for a in xs) + sum(abs(y - b) for b in ys)
''', r'''
def manhattan_center(points):
    if not isinstance(points, (list, tuple)) or not 1 <= len(points) <= 100000:
        raise ValueError("need 1 to 100000 points")
    xs, ys = [], []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("a point is two ints")
        for v in p:
            if not isinstance(v, int) or isinstance(v, bool) or not -10 ** 9 <= v <= 10 ** 9:
                raise ValueError("coordinates must be ints with |v| <= 10**9")
        xs.append(p[0])
        ys.append(p[1])
    xs.sort()
    ys.sort()
    k = (len(xs) - 1) // 2
    x, y = xs[k], ys[k]
    return x, y, sum(abs(x - v) for v in xs) + sum(abs(y - v) for v in ys)
''')


task("v8_22_tree_centers", r'''
Write `tree_centers(n, edges)` that finds the center of a tree and its radius.

The tree has vertices 0 to n-1 and the undirected edges in `edges`, a list or tuple of n - 1 pairs (a, b), each a
tuple or list of two ints. The edges always form a tree (connected, no cycles), so that does not need checking; only
this is validated (ValueError): n is not an int from 1 to 100000, edges is not a list or tuple of exactly n - 1
pairs, or a pair is not a tuple or list of two ints in 0..n-1. A bool is never accepted as an int.

The distance between two vertices is the number of edges on the path between them. The eccentricity of a vertex is
its largest distance to any other vertex. The radius is the smallest eccentricity, and the centers are the vertices
whose eccentricity equals the radius; a tree always has one center or two adjacent ones.

Return a tuple (centers, radius) with centers as a sorted list.

A fast method: breadth-first search from vertex 0 finds a farthest vertex u; a second search from u finds a farthest
vertex v and a longest path from u to v. If that path has D edges, the radius is (D + 1) // 2 and the centers are the
middle vertex of the path (D even) or its two middle vertices (D odd). Repeatedly removing all leaves also works.

Examples:
- tree_centers(1, []) == ([0], 0) and tree_centers(2, [(1, 0)]) == ([0, 1], 1)
- tree_centers(3, [(0, 1), (1, 2)]) == ([1], 1)
- tree_centers(4, [(0, 1), (1, 2), (2, 3)]) == ([1, 2], 2)
- tree_centers(4, [(0, 1), (0, 2), (0, 3)]) == ([0], 1)
- tree_centers(6, [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5)]) == ([2], 2)
- ValueError: tree_centers(0, []), tree_centers(2, []), tree_centers(2, [(0, 2)]), tree_centers(2, [(0,)]),
  tree_centers(True, []), tree_centers(2, None)
''', r'''
import random
from collections import deque

TCN = tree_centers

def rej(*a):
    try:
        TCN(*a)
    except ValueError:
        return True
    return False

assert TCN(1, []) == ([0], 0) and TCN(2, [(1, 0)]) == ([0, 1], 1) and TCN(3, [(0, 1), (1, 2)]) == ([1], 1)
assert TCN(4, [(0, 1), (1, 2), (2, 3)]) == ([1, 2], 2) and TCN(4, [(0, 1), (0, 2), (0, 3)]) == ([0], 1)
assert TCN(6, [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5)]) == ([2], 2) and TCN(3, ([2, 0], [0, 1])) == ([0], 1)
for bad in [(0, []), (2, []), (2, [(0, 2)]), (2, [(0,)]), (True, []), (2, None), (100001, []), (2.0, [(0, 1)]),
            (2, [(0, True)]), (2, [None]), (3, [(0, 1)]), (2, [(0, 1), (0, 1)])]:
    assert rej(*bad), bad

def brute(n, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    ecc = []
    for s in range(n):
        dist, q = {s: 0}, deque([s])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
        ecc.append(max(dist.values()))
    r = min(ecc)
    return [v for v in range(n) if ecc[v] == r], r

def rtree(n):
    lab = list(range(n))
    random.shuffle(lab)
    return [(lab[i], lab[random.randrange(i)]) for i in range(1, n)]

random.seed(8022)
for _ in range(300):
    n = random.randint(1, 40)
    edges = rtree(n)
    assert TCN(n, edges) == brute(n, edges), (n, edges)
n = 50000
lab = list(range(n))
random.shuffle(lab)
edges = [(lab[i], lab[i + 1]) for i in range(n - 1)]
random.shuffle(edges)
assert TCN(n, edges) == (sorted([lab[24999], lab[25000]]), 25000)
''', r'''
from collections import deque


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def tree_centers(n, edges):
    if not _isint(n) or not 1 <= n <= 100000:
        raise ValueError("n must be an int from 1 to 100000")
    if not isinstance(edges, (list, tuple)) or len(edges) != n - 1:
        raise ValueError("edges must hold n - 1 pairs")
    adj = [[] for _ in range(n)]
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2 or not all(_isint(x) and 0 <= x < n for x in e):
            raise ValueError("bad edge")
        adj[e[0]].append(e[1])
        adj[e[1]].append(e[0])

    def bfs(s):
        parent, queue, last = {s: None}, deque([s]), s
        while queue:
            last = queue.popleft()
            for v in adj[last]:
                if v not in parent:
                    parent[v] = last
                    queue.append(v)
        return last, parent
    u, _ = bfs(0)
    v, parent = bfs(u)
    path = [v]
    while path[-1] != u:
        path.append(parent[path[-1]])
    d = len(path) - 1
    return sorted({path[d // 2], path[(d + 1) // 2]}), (d + 1) // 2
''')


# --- simulation_dp ---

task("v8_23_robot_walk", r'''
Write `robot_walk(grid, commands)` that simulates a robot on a grid and reports where it ends.

`grid` is a non-empty list or tuple of rows, each a non-empty str, all of the same length, made only of the
characters "." (free), "#" (wall) and "S" (the robot's start, which is a free cell). Exactly one "S" appears. Row 0 is
the top row and column 0 is the left column. `commands` is a str made only of "L", "R" and "F" (it may be empty).
Anything else raises ValueError. The grid has at most 1000 rows and 1000 columns and commands at most 100000
characters.

The robot starts on the S cell facing north (towards row 0). It runs the commands in order:
- "L" turns it 90 degrees to the left and "R" 90 degrees to the right, without moving;
- "F" moves it one cell forward, unless that cell is a wall or outside the grid, in which case it stays where it is.
The four directions in clockwise order are "N", "E", "S", "W"; north decreases the row and east increases the column.

Return a tuple (row, col, facing, visited): the final cell, the final direction as one of "N", "E", "S", "W", and the
number of different cells the robot has stood on, the start included.

Examples, with g = ["...", ".S.", "..."]:
- robot_walk(g, "F") == (0, 1, "N", 2) and robot_walk(g, "FF") == (0, 1, "N", 2)
- robot_walk(g, "RFF") == (1, 2, "E", 2) and robot_walk(g, "LLFF") == (2, 1, "S", 2)
- robot_walk(g, "") == (1, 1, "N", 1) and robot_walk(g, "FRRF") == (1, 1, "S", 2)
- robot_walk(["S#", ".."], "FRFRF") == (1, 0, "S", 2)
- robot_walk(("S..", "##."), "RFFRF") == (1, 2, "S", 4)
- ValueError: robot_walk([], "F"), robot_walk(["S", ".."], ""), robot_walk(["..."], "F"), robot_walk(["SS"], ""),
  robot_walk(["S."], "X"), robot_walk(["S*"], ""), robot_walk("S..", "F")
''', r'''
import random

RW = robot_walk

def rej(*a):
    try:
        RW(*a)
    except ValueError:
        return True
    return False

g = ["...", ".S.", "..."]
assert RW(g, "F") == (0, 1, "N", 2) and RW(g, "FF") == (0, 1, "N", 2) and RW(g, "RFF") == (1, 2, "E", 2)
assert RW(g, "LLFF") == (2, 1, "S", 2) and RW(g, "") == (1, 1, "N", 1) and RW(g, "FRRF") == (1, 1, "S", 2)
assert RW(["S#", ".."], "FRFRF") == (1, 0, "S", 2) and RW(("S..", "##."), "RFFRF") == (1, 2, "S", 4)
assert RW(["S"], "FLFRFRRF") == (0, 0, "S", 1) and RW(g, "LLLL") == (1, 1, "N", 1) and RW(g, "RRRF") == (1, 0, "W", 2)
for bad in [([], "F"), (["S", ".."], ""), (["..."], "F"), (["SS"], ""), (["S."], "X"), (["S*"], ""), ("S..", "F"),
            ([""], ""), (["S."], "f"), (["S."], None), ([None], ""), (["S.", 5], ""), (["S."], ["F"])]:
    assert rej(*bad), bad

def oracle(grid, cmds):
    cells = {complex(c, r): ch for r, row in enumerate(grid) for c, ch in enumerate(row)}
    pos = next(p for p, ch in cells.items() if ch == "S")
    d, seen = -1j, {pos}
    for ch in cmds:
        if ch == "R":
            d *= 1j
        elif ch == "L":
            d *= -1j
        elif cells.get(pos + d, "#") != "#":
            pos += d
            seen.add(pos)
    return int(pos.imag), int(pos.real), {-1j: "N", 1: "E", 1j: "S", -1: "W"}[d], len(seen)

random.seed(8023)
for _ in range(300):
    h, w = random.randint(1, 7), random.randint(1, 7)
    rows = [[random.choice("..#") for _ in range(w)] for _ in range(h)]
    rows[random.randrange(h)][random.randrange(w)] = "S"
    grid = ["".join(r) for r in rows]
    if sum(r.count("S") for r in grid) != 1:
        continue
    cmds = "".join(random.choice("LRFFF") for _ in range(random.randint(0, 40)))
    assert RW(grid, cmds) == oracle(grid, cmds), (grid, cmds)
rows = [["#" if random.random() < 0.2 else "." for _ in range(200)] for _ in range(200)]
rows[100][100] = "S"
grid = ["".join(r) for r in rows]
cmds = "".join(random.choice("LRFFFF") for _ in range(100000))
assert RW(grid, cmds) == oracle(grid, cmds)
''', r'''
_DIRS = "NESW"
_STEP = {"N": (-1, 0), "E": (0, 1), "S": (1, 0), "W": (0, -1)}


def robot_walk(grid, commands):
    if not isinstance(grid, (list, tuple)) or not 1 <= len(grid) <= 1000:
        raise ValueError("grid must be a list or tuple of 1 to 1000 rows")
    width = len(grid[0]) if isinstance(grid[0], str) else 0
    if not 1 <= width <= 1000 or any(not isinstance(r, str) or len(r) != width or set(r) - set(".#S") for r in grid):
        raise ValueError("rows must be equal-length str of . # S")
    starts = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if ch == "S"]
    if len(starts) != 1:
        raise ValueError("exactly one S")
    if not isinstance(commands, str) or len(commands) > 100000 or set(commands) - set("LRF"):
        raise ValueError("commands must be a str of L, R and F")
    (r, c), d = starts[0], 0
    seen = {(r, c)}
    for ch in commands:
        if ch == "L":
            d = (d + 3) % 4
        elif ch == "R":
            d = (d + 1) % 4
        else:
            dr, dc = _STEP[_DIRS[d]]
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(grid) and 0 <= nc < width and grid[nr][nc] != "#":
                r, c = nr, nc
                seen.add((r, c))
    return r, c, _DIRS[d], len(seen)
''')


task("v8_24_elevator_scan", r'''
Write `elevator_stops(start, requests, direction)` that plans the stops of an elevator with the LOOK rule.

The elevator is at floor `start` and moving in `direction`, which is "up" or "down". `requests` is a list or tuple of
floors where someone is waiting; a floor may appear more than once and is still served only once. Floors are ints
from 0 to 1000 (a bool is never accepted), there are at most 10000 requests, and anything else raises ValueError.

The LOOK rule:
- a request at the elevator's own floor is served first, without moving;
- then the elevator keeps going in its direction and serves the requested floors on that side in the order it
  reaches them, nearest first;
- after the farthest request on that side it turns around at once (it does not travel on to the top or bottom), and
  serves the requests on the other side in the order it reaches them;
- if there is no request on the side it is moving towards, it turns around right away.

Return a tuple (stops, distance): stops is the list of floors in the order they are served (each requested floor
once), and distance is the total number of floors travelled, which is 0 when nothing is requested.

Examples:
- elevator_stops(5, [3, 8, 6, 1], "up") == ([6, 8, 3, 1], 10)
- elevator_stops(5, [5, 2], "up") == ([5, 2], 3) and elevator_stops(4, [], "down") == ([], 0)
- elevator_stops(3, [7, 7, 1], "down") == ([1, 7], 8)
- elevator_stops(2, (4, 9), "down") == ([4, 9], 7) and elevator_stops(0, [0, 0], "up") == ([0], 0)
- ValueError: elevator_stops(5, [1001], "up"), elevator_stops(-1, [], "up"), elevator_stops(5, [2], "sideways"),
  elevator_stops(5, [True], "up"), elevator_stops(5, None, "up"), elevator_stops(5.0, [], "up")
''', r'''
import random

ES = elevator_stops

def rej(*a):
    try:
        ES(*a)
    except ValueError:
        return True
    return False

assert ES(5, [3, 8, 6, 1], "up") == ([6, 8, 3, 1], 10) and ES(5, [5, 2], "up") == ([5, 2], 3) and ES(4, [], "down") == ([], 0)
assert ES(3, [7, 7, 1], "down") == ([1, 7], 8) and ES(2, (4, 9), "down") == ([4, 9], 7) and ES(0, [0, 0], "up") == ([0], 0)
assert ES(1000, [0, 1000, 500], "up") == ([1000, 500, 0], 1000) and ES(10, [12, 8, 11, 9], "down") == ([9, 8, 11, 12], 6)
for bad in [(5, [1001], "up"), (-1, [], "up"), (5, [2], "sideways"), (5, [True], "up"), (5, None, "up"), (5.0, [], "up"),
            (5, [2], "UP"), (5, [2.0], "up"), (5, "12", "up"), (1001, [], "down"), (5, [-1], "down"), (5, [1] * 10001, "up")]:
    assert rej(*bad), bad

def simulate(start, reqs, direction):
    pending, pos, step, stops, dist = set(reqs), start, 1 if direction == "up" else -1, [], 0
    while pending:
        if pos in pending:
            pending.discard(pos)
            stops.append(pos)
            continue
        if not any((f - pos) * step > 0 for f in pending):
            step = -step
        pos += step
        dist += 1
    return stops, dist

random.seed(8024)
for _ in range(1500):
    start = random.choice([0, 1000, random.randint(0, 1000), random.randint(0, 20)])
    reqs = [random.choice([start, random.randint(0, 1000), random.randint(0, 20)]) for _ in range(random.randint(0, 8))]
    d = random.choice(["up", "down"])
    assert ES(start, reqs, d) == simulate(start, reqs, d), (start, reqs, d)
''', r'''
def _floor(x):
    if not isinstance(x, int) or isinstance(x, bool) or not 0 <= x <= 1000:
        raise ValueError("floors are ints from 0 to 1000")
    return x


def elevator_stops(start, requests, direction):
    _floor(start)
    if direction not in ("up", "down"):
        raise ValueError("direction must be up or down")
    if not isinstance(requests, (list, tuple)) or len(requests) > 10000:
        raise ValueError("requests must be a list or tuple of at most 10000 floors")
    pending = {_floor(f) for f in requests}
    stops, pos, distance = [], start, 0
    if start in pending:
        stops.append(start)
    above = sorted(f for f in pending if f > start)
    below = sorted((f for f in pending if f < start), reverse=True)
    for f in (above + below if direction == "up" else below + above):
        distance += abs(f - pos)
        pos = f
        stops.append(f)
    return stops, distance
''')


task("v8_25_josephus_order", r'''
Write `josephus(n, k)` and `josephus_survivor(n, k)` for the Josephus elimination game.

n people numbered 1 to n stand in a circle in order. Counting starts at person 1, who counts as 1; the person who is
counted k is removed, and counting starts again at 1 with the next person still in the circle. This repeats until
nobody is left. With k = 1 people simply leave in order 1, 2, ..., n.

josephus(n, k) returns the list of people in the order they are removed (so its last entry is the survivor). `n` must
be an int from 1 to 5000 and `k` an int from 1 to 1000000. Removing from a Python list by index is fast enough for
these sizes: keep an index i and use i = (i + k - 1) % len(people).

josephus_survivor(n, k) returns just the number of the last person left, for n up to 1000000 and k from 1 to
1000000. Simulating is too slow for the largest n; use the recurrence on 0-based positions: J(1) = 0 and
J(m) = (J(m - 1) + k) % m for m = 2..n; the survivor is J(n) + 1.

For both functions a bool is never accepted as an int, and anything out of range raises ValueError.

Examples:
- josephus(7, 3) == [3, 6, 2, 7, 5, 1, 4] and josephus(4, 2) == [2, 4, 3, 1]
- josephus(5, 1) == [1, 2, 3, 4, 5] and josephus(1, 5) == [1]
- josephus_survivor(7, 3) == 4 and josephus_survivor(1, 1) == 1 and josephus_survivor(1000000, 2) == 951425
- ValueError: josephus(0, 3), josephus(5001, 2), josephus(5, 0), josephus(True, 2), josephus_survivor(1000001, 2),
  josephus_survivor(5, 1000001), josephus_survivor(5, 2.0)
''', r'''
import random
from collections import deque

JO, JS = josephus, josephus_survivor

def rej(f, *a):
    try:
        f(*a)
    except ValueError:
        return True
    return False

assert JO(7, 3) == [3, 6, 2, 7, 5, 1, 4] and JO(4, 2) == [2, 4, 3, 1] and JO(5, 1) == [1, 2, 3, 4, 5] and JO(1, 5) == [1]
assert JS(7, 3) == 4 and JS(1, 1) == 1 and JS(1000000, 2) == 951425 and JS(5, 1) == 5
for bad in ((0, 3), (5001, 2), (5, 0), (True, 2), (5, 1000001), (5, 2.0), ("5", 2), (5, None)):
    assert rej(JO, *bad), bad
for bad in ((1000001, 2), (5, 1000001), (5, 2.0), (0, 1), (3, False), (-2, 2)):
    assert rej(JS, *bad), bad

def oracle(n, k):
    q, out = deque(range(1, n + 1)), []
    while q:
        q.rotate(-((k - 1) % len(q)))
        out.append(q.popleft())
    return out

random.seed(8025)
for _ in range(300):
    n, k = random.randint(1, 60), random.choice([1, 2, 3, random.randint(1, 100), random.randint(1, 10 ** 6)])
    want = oracle(n, k)
    assert JO(n, k) == want, (n, k)
    assert JS(n, k) == want[-1], (n, k)
n, k = 5000, random.randint(1, 10 ** 6)
want = oracle(n, k)
assert JO(n, k) == want and JS(n, k) == want[-1]
''', r'''
def _check(n, k, top):
    for x in (n, k):
        if not isinstance(x, int) or isinstance(x, bool):
            raise ValueError("n and k must be ints")
    if not 1 <= n <= top or not 1 <= k <= 1000000:
        raise ValueError("n or k out of range")


def josephus(n, k):
    _check(n, k, 5000)
    people, out, i = list(range(1, n + 1)), [], 0
    while people:
        i = (i + k - 1) % len(people)
        out.append(people.pop(i))
    return out


def josephus_survivor(n, k):
    _check(n, k, 1000000)
    j = 0
    for m in range(2, n + 1):
        j = (j + k) % m
    return j + 1
''')


task("v8_26_max_subarray", r'''
Write `max_subarray(nums)` that finds the contiguous run of a list with the largest sum.

`nums` must be a non-empty list or tuple of at most 100000 ints, each with -10**9 <= v <= 10**9; a bool is never
accepted as an int. Anything else raises ValueError.

A run is nums[i..j] for 0 <= i <= j < len(nums), both ends included, and its sum is nums[i] + ... + nums[j]. A run
always has at least one element, so for a list of negative numbers the answer is its largest element.

Return a tuple (best, i, j): best is the largest sum of any run, and (i, j) are the ends of a run with that sum. When
several runs have the largest sum, return the one that starts first, and among those the one that ends first.

One pass is enough (Kadane's algorithm, or prefix sums): walk j from left to right keeping the running prefix sum and
the smallest prefix sum seen before position j together with the first position where it occurred. The best run that
ends at j starts at that position. Keep a new candidate only when its sum is strictly larger than the best so far.

Examples:
- max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == (6, 3, 6)
- max_subarray([1]) == (1, 0, 0) and max_subarray([-3, -1, -2]) == (-1, 1, 1)
- max_subarray([2, -2, 2]) == (2, 0, 0) and max_subarray([0, 0]) == (0, 0, 0)
- max_subarray((-1, 3, -3, 3)) == (3, 1, 1) and max_subarray([5, -9, 5, 0]) == (5, 0, 0)
- ValueError: max_subarray([]), max_subarray([1, True]), max_subarray([1.5]), max_subarray(None),
  max_subarray([10 ** 9 + 1])
''', r'''
import random

MS = max_subarray

def rej(x):
    try:
        MS(x)
    except ValueError:
        return True
    return False

assert MS([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == (6, 3, 6) and MS([1]) == (1, 0, 0) and MS([-3, -1, -2]) == (-1, 1, 1)
assert MS([2, -2, 2]) == (2, 0, 0) and MS([0, 0]) == (0, 0, 0) and MS((-1, 3, -3, 3)) == (3, 1, 1) and MS([5, -9, 5, 0]) == (5, 0, 0)
assert MS([-5, 0, -1, 0]) == (0, 1, 1) and MS([1, -1, 1, -1, 2]) == (2, 0, 4)
assert MS([-10 ** 9]) == (-10 ** 9, 0, 0) and MS([10 ** 9, -10 ** 9, 10 ** 9]) == (10 ** 9, 0, 0)
for bad in ([], [1, True], [1.5], None, [10 ** 9 + 1], "12", [1, None], [0] * 100001, [-10 ** 9 - 1]):
    assert rej(bad), bad

def brute(a):
    return min((-sum(a[i:j + 1]), i, j) for i in range(len(a)) for j in range(i, len(a)))

random.seed(8026)
for _ in range(1500):
    a = [random.choice([random.randint(-3, 3), random.randint(-10 ** 9, 10 ** 9)]) for _ in range(random.randint(1, 12))]
    s, i, j = brute(a)
    assert MS(a) == (-s, i, j), a
a = [random.randint(-10 ** 9, 10 ** 9) for _ in range(100000)]
best, i, j = MS(a)
assert sum(a[i:j + 1]) == best and 0 <= i <= j < len(a)
pre, lo, hi = 0, 0, None
for v in a:
    pre += v
    hi = pre - lo if hi is None else max(hi, pre - lo)
    lo = min(lo, pre)
assert hi == best
''', r'''
def max_subarray(nums):
    if not isinstance(nums, (list, tuple)) or not 1 <= len(nums) <= 100000:
        raise ValueError("nums must be a list or tuple of 1 to 100000 ints")
    for v in nums:
        if not isinstance(v, int) or isinstance(v, bool) or not -10 ** 9 <= v <= 10 ** 9:
            raise ValueError("values must be ints with |v| <= 10**9")
    best = None
    prefix, low, low_at = 0, 0, 0
    for j, v in enumerate(nums):
        prefix += v
        if best is None or prefix - low > best[0]:
            best = (prefix - low, low_at, j)
        if prefix < low:
            low, low_at = prefix, j + 1
    return best
''')


task("v8_27_stair_ways", r'''
Write `stair_ways(n, steps, broken)` that counts the ways to climb a staircase that has some broken stairs.

You start on stair 0 and want to stand exactly on stair n. Each move goes up by one of the sizes in `steps`. You may
never stand on a broken stair. Two ways are different when their sequences of moves differ. Return the number of ways
modulo 1000000007 (so a single int from 0 to 1000000006). Standing still is the one way to "climb" when n == 0.

Validation (ValueError):
- n must be an int from 0 to 100000;
- steps must be a list, tuple or set of 1 to 10 different ints, each from 1 to 100;
- broken must be a list, tuple or set of ints, each from 1 to n - 1 (stairs 0 and n are never broken); repeats are
  allowed and change nothing.
A bool is never accepted as an int.

Use dynamic programming over the stairs: ways[0] = 1; for each stair i from 1 to n, ways[i] is 0 if i is broken and
otherwise the sum of ways[i - s] over the step sizes s <= i, taken modulo 1000000007. The answer is ways[n].

Examples:
- stair_ways(4, [1, 2], []) == 5 and stair_ways(4, [1, 2], [2]) == 1
- stair_ways(0, [3], []) == 1 and stair_ways(5, [2], []) == 0
- stair_ways(10, [1, 3, 5], [4, 7]) == 11 and stair_ways(6, {2, 3}, (3, 3)) == 1
- stair_ways(100000, [1, 2], []) == 967618232
- ValueError: stair_ways(-1, [1], []), stair_ways(3, [], []), stair_ways(3, [1, 1], []), stair_ways(3, [0], []),
  stair_ways(3, [1], [3]), stair_ways(3, [1], [0]), stair_ways(3, [True], []), stair_ways(3, [1], None)
''', r'''
import random
from functools import lru_cache

SW = stair_ways
M = 1000000007

def rej(*a):
    try:
        SW(*a)
    except ValueError:
        return True
    return False

assert SW(4, [1, 2], []) == 5 and SW(4, [1, 2], [2]) == 1 and SW(0, [3], []) == 1 and SW(5, [2], []) == 0
assert SW(10, [1, 3, 5], [4, 7]) == 11 and SW(6, {2, 3}, (3, 3)) == 1 and SW(100000, [1, 2], []) == 967618232
assert SW(3, (1,), {1}) == 0 and SW(1, [1], []) == 1
for bad in [(-1, [1], []), (3, [], []), (3, [1, 1], []), (3, [0], []), (3, [1], [3]), (3, [1], [0]), (3, [True], []),
            (3, [1], None), (100001, [1], []), (3, [101], []), (3, list(range(1, 12)), []), (3.0, [1], []), (3, "12", []),
            (3, [1], [1.0]), (3, None, [])]:
    assert rej(*bad), bad

def oracle(n, steps, broken):
    bad = set(broken)
    @lru_cache(maxsize=None)
    def f(i):
        if i == n:
            return 1
        if i > n or i in bad:
            return 0
        return sum(f(i + s) for s in steps) % M
    return f(0)

random.seed(8027)
for _ in range(400):
    n = random.randint(0, 40)
    steps = random.sample(range(1, 8), random.randint(1, 4))
    broken = [random.randint(1, n - 1) for _ in range(random.randint(0, 5))] if n >= 2 else []
    assert SW(n, steps, broken) == oracle(n, steps, broken), (n, steps, broken)
n = 20000
steps = random.sample(range(1, 101), 10)
broken = random.sample(range(1, n), 300)
bs = set(broken)
ways = [0] * (n + 101)
ways[0] = 1
for i in range(n):
    if i in bs:
        ways[i] = 0
        continue
    w = ways[i] % M
    for s in steps:
        ways[i + s] += w
assert SW(n, steps, broken) == ways[n] % M
''', r'''
MOD = 1000000007


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


def stair_ways(n, steps, broken):
    if not _isint(n) or not 0 <= n <= 100000:
        raise ValueError("n must be an int from 0 to 100000")
    if not isinstance(steps, (list, tuple, set)) or not 1 <= len(steps) <= 10 or len(set(steps)) != len(steps) \
            or not all(_isint(s) and 1 <= s <= 100 for s in steps):
        raise ValueError("steps must be 1 to 10 different ints from 1 to 100")
    if not isinstance(broken, (list, tuple, set)) or not all(_isint(b) and 1 <= b <= n - 1 for b in broken):
        raise ValueError("broken stairs must be ints from 1 to n - 1")
    bad = set(broken)
    ways = [1] + [0] * n
    for i in range(1, n + 1):
        if i not in bad:
            ways[i] = sum(ways[i - s] for s in steps if s <= i) % MOD
    return ways[n]
''')


task("v8_28_lcs_smallest", r'''
Write `lcs(a, b)` that returns the longest common subsequence of two strings, choosing the smallest one when there are
several.

A subsequence of a str is what is left after deleting any number of its characters (possibly none), keeping the rest
in order. A common subsequence of a and b is a subsequence of both. Return a longest common subsequence; when several
different strings have that length, return the smallest of them in Python's str order. Return "" when a and b have no
character in common.

`a` and `b` must both be str of at most 300 characters each (any characters, compared by their code points); anything
else raises ValueError.

A method that fits these sizes:
1. Fill a table L where L[i][j] is the length of a longest common subsequence of the suffixes a[i:] and b[j:]
   (L[i][j] = L[i+1][j+1] + 1 when a[i] == b[j], otherwise max(L[i+1][j], L[i][j+1]); the last row and column are 0).
2. Build the answer from the front: at position (i, j) with r = L[i][j] > 0 still to go, try the characters that
   occur in both strings in increasing order; for a character c take its first occurrence x >= i in a and y >= j in
   b, and pick the first c with L[x+1][y+1] == r - 1. Append c and continue from (x + 1, y + 1).

Examples:
- lcs("ABCBDAB", "BDCABA") == "BCAB" (BDAB and BCBA have the same length but are larger)
- lcs("abc", "def") == "" and lcs("", "x") == ""
- lcs("aaa", "aa") == "aa" and lcs("xyz", "xzy") == "xy"
- lcs("banana", "atana") == "aana"
- ValueError: lcs("a" * 301, "a"), lcs(None, "a"), lcs("a", 5), lcs(["a"], "a")
''', r'''
import random
from itertools import combinations

LS = lcs

def rej(*a):
    try:
        LS(*a)
    except ValueError:
        return True
    return False

assert LS("ABCBDAB", "BDCABA") == "BCAB" and LS("abc", "def") == "" and LS("", "x") == "" and LS("aaa", "aa") == "aa"
assert LS("xyz", "xzy") == "xy" and LS("banana", "atana") == "aana" and LS("same", "same") == "same" and LS("ba", "ab") == "a"
assert LS("aé€", "€aé") == "aé"
for bad in [("a" * 301, "a"), (None, "a"), ("a", 5), (["a"], "a"), ("a", "b" * 301), (b"ab", "ab")]:
    assert rej(*bad), bad

def issub(s, t):
    it = iter(t)
    return all(c in it for c in s)

def brute(a, b):
    for r in range(min(len(a), len(b)), -1, -1):
        cands = {"".join(c) for c in combinations(a, r) if issub("".join(c), b)}
        if cands:
            return min(cands)

def length(a, b):
    prev = [0] * (len(b) + 1)
    for ch in a:
        cur = [0]
        for j, d in enumerate(b):
            cur.append(prev[j] + 1 if ch == d else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]

random.seed(8028)
for _ in range(500):
    al = random.choice(["ab", "abc", "abcd", "xyzé"])
    a = "".join(random.choice(al) for _ in range(random.randint(0, 8)))
    b = "".join(random.choice(al) for _ in range(random.randint(0, 8)))
    assert LS(a, b) == brute(a, b), (a, b)
for _ in range(2):
    a = "".join(random.choice("acgt") for _ in range(300))
    b = "".join(random.choice("acgt") for _ in range(300))
    s = LS(a, b)
    assert issub(s, a) and issub(s, b) and len(s) == length(a, b)
''', r'''
def lcs(a, b):
    if not isinstance(a, str) or not isinstance(b, str) or len(a) > 300 or len(b) > 300:
        raise ValueError("a and b must be str of at most 300 characters")
    n, m = len(a), len(b)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if a[i] == b[j] else max(L[i + 1][j], L[i][j + 1])
    chars = sorted(set(a) & set(b))
    out, i, j = [], 0, 0
    while L[i][j]:
        for c in chars:
            x, y = a.find(c, i), b.find(c, j)
            if x >= 0 and y >= 0 and L[x + 1][y + 1] == L[i][j] - 1:
                out.append(c)
                i, j = x + 1, y + 1
                break
    return "".join(out)
''')


task("v8_29_matrix_chain", r'''
Write `chain_order(dims)` that finds the cheapest order in which to multiply a chain of matrices.

`dims` is a list or tuple of 2 to 27 ints, each from 1 to 1000 (a bool is never accepted); anything else raises
ValueError. It describes len(dims) - 1 matrices named "A", "B", "C", ... in order, where matrix number t (0-based) has
dims[t] rows and dims[t + 1] columns. Multiplying a p x q matrix by a q x r matrix costs p * q * r scalar
multiplications and gives a p x r matrix.

Return a tuple (cost, order): cost is the smallest total number of scalar multiplications needed to compute the whole
product, and order is a str showing how to group it: a single matrix is its letter, and a product of two groups X and
Y is written "(" + X + Y + ")", with no spaces. A chain of one matrix costs 0 and its order is just "A".

When several groupings have the smallest cost, choose by this rule, applied at every level: the product of matrices
i..j is split into i..s and s+1..j at the smallest s that gives the smallest cost for i..j.

Use dynamic programming over chain lengths: cost[i][j] = min over s from i to j - 1 of
cost[i][s] + cost[s + 1][j] + dims[i] * dims[s + 1] * dims[j + 1], with cost[i][i] = 0, remembering the chosen s
(keep a new s only when it is strictly cheaper) to rebuild the order.

Examples:
- chain_order([10, 30, 5, 60]) == (4500, "((AB)C)")
- chain_order([40, 20, 30, 10, 30]) == (26000, "((A(BC))D)")
- chain_order([5, 7]) == (0, "A") and chain_order((2, 3, 4)) == (24, "(AB)")
- chain_order([1, 1, 1, 1]) == (2, "(A(BC))")
- ValueError: chain_order([5]), chain_order([]), chain_order([2, 0, 3]), chain_order([2, 1001]),
  chain_order([2, True, 3]), chain_order(None), chain_order([1] * 28)
''', r'''
import random
from functools import lru_cache

CO = chain_order

def rej(x):
    try:
        CO(x)
    except ValueError:
        return True
    return False

assert CO([10, 30, 5, 60]) == (4500, "((AB)C)") and CO([40, 20, 30, 10, 30]) == (26000, "((A(BC))D)")
assert CO([5, 7]) == (0, "A") and CO((2, 3, 4)) == (24, "(AB)") and CO([1, 1, 1, 1]) == (2, "(A(BC))")
for bad in ([5], [], [2, 0, 3], [2, 1001], [2, True, 3], None, [1] * 28, [2.0, 3], "23", [2, None]):
    assert rej(bad), bad

def oracle(d):
    @lru_cache(maxsize=None)
    def best(i, j):
        if i == j:
            return 0, chr(65 + i)
        top = None
        for s in range(i, j):
            c1, t1 = best(i, s)
            c2, t2 = best(s + 1, j)
            c = c1 + c2 + d[i] * d[s + 1] * d[j + 1]
            if top is None or c < top[0]:
                top = (c, "(" + t1 + t2 + ")")
        return top
    return best(0, len(d) - 2)

def all_orders(d, i, j):
    if i == j:
        yield 0, chr(65 + i)
        return
    for s in range(i, j):
        for c1, t1 in all_orders(d, i, s):
            for c2, t2 in all_orders(d, s + 1, j):
                yield c1 + c2 + d[i] * d[s + 1] * d[j + 1], "(" + t1 + t2 + ")"

random.seed(8029)
for _ in range(300):
    d = [random.choice([1, 2, random.randint(1, 10), random.randint(1, 1000)]) for _ in range(random.randint(2, 9))]
    want = oracle(d)
    assert CO(d) == want, d
    if len(d) <= 7:
        assert want[0] == min(c for c, _ in all_orders(d, 0, len(d) - 2)), d
d = [random.randint(1, 1000) for _ in range(27)]
assert CO(d) == oracle(d)
''', r'''
def chain_order(dims):
    if not isinstance(dims, (list, tuple)) or not 2 <= len(dims) <= 27:
        raise ValueError("dims must hold 2 to 27 ints")
    for v in dims:
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 1000:
            raise ValueError("dimensions must be ints from 1 to 1000")
    k = len(dims) - 1
    cost = [[0] * k for _ in range(k)]
    split = [[0] * k for _ in range(k)]
    for length in range(2, k + 1):
        for i in range(k - length + 1):
            j = i + length - 1
            for s in range(i, j):
                c = cost[i][s] + cost[s + 1][j] + dims[i] * dims[s + 1] * dims[j + 1]
                if s == i or c < cost[i][j]:
                    cost[i][j], split[i][j] = c, s

    def order(i, j):
        if i == j:
            return chr(65 + i)
        s = split[i][j]
        return "(" + order(i, s) + order(s + 1, j) + ")"
    return cost[0][k - 1], order(0, k - 1)
''')


task("v8_30_ledger_events", r'''
Write `apply_ledger(events)` that runs a bank account through a list of events and reports the result.

The account starts with balance 0. `events` is a list or tuple of events, each a tuple or list:
- ("deposit", amount): add amount to the balance.
- ("withdraw", amount): if amount <= balance, subtract it. Otherwise it is an overdraft: if balance - amount >= -500,
  subtract the amount and also charge an overdraft fee of 25 (the fee may take the balance below -500); if
  balance - amount < -500, the withdrawal is rejected and nothing changes.
- ("month",): the end of a month. If the balance is negative, charge interest of 2 percent of the amount owed,
  rounded down to a whole number: charge = (-balance * 2) // 100, subtracted from the balance (it may be 0).
amount must be an int >= 1 (a bool is never accepted). An unknown event name, a missing or extra field, a bad amount,
or events that is not a list or tuple raises ValueError.

Return a tuple (balance, rejected, fees): the final balance, how many withdrawals were rejected, and the total of all
overdraft fees and interest charged.

Examples:
- apply_ledger([("deposit", 100), ("withdraw", 30)]) == (70, 0, 0)
- apply_ledger([("withdraw", 200)]) == (-225, 0, 25) and apply_ledger([("withdraw", 500)]) == (-525, 0, 25)
- apply_ledger([("withdraw", 501)]) == (0, 1, 0) and apply_ledger([]) == (0, 0, 0)
- apply_ledger([("deposit", 50), ("withdraw", 500), ("month",)]) == (-484, 0, 34)
- apply_ledger([("deposit", 10), ["month"]]) == (10, 0, 0)
- ValueError: apply_ledger([("deposit", 0)]), apply_ledger([("withdraw", True)]), apply_ledger([("month", 1)]),
  apply_ledger([("refund", 5)]), apply_ledger([("deposit",)]), apply_ledger(None), apply_ledger([("deposit", 2.5)])
''', r'''
import random

AL = apply_ledger

def rej(x):
    try:
        AL(x)
    except ValueError:
        return True
    return False

assert AL([("deposit", 100), ("withdraw", 30)]) == (70, 0, 0) and AL([("withdraw", 200)]) == (-225, 0, 25)
assert AL([("withdraw", 500)]) == (-525, 0, 25) and AL([("withdraw", 501)]) == (0, 1, 0) and AL([]) == (0, 0, 0)
assert AL([("deposit", 50), ("withdraw", 500), ("month",)]) == (-484, 0, 34) and AL([("deposit", 10), ["month"]]) == (10, 0, 0)
assert AL([("withdraw", 500), ("withdraw", 1), ("month",), ("month",)]) == (-545, 1, 45)
assert AL((("withdraw", 49), ("month",))) == (-75, 0, 26)
for bad in ([("deposit", 0)], [("withdraw", True)], [("month", 1)], [("refund", 5)], [("deposit",)], None,
            [("deposit", 2.5)], [("deposit", 5, 6)], [()], ["month"], [("Deposit", 5)], [("withdraw", -3)], "month"):
    assert rej(bad), bad

class Account:
    def __init__(self):
        self.bal = self.rej = self.fee = 0
    def deposit(self, a):
        self.bal += a
    def withdraw(self, a):
        if a <= self.bal:
            self.bal -= a
        elif self.bal - a < -500:
            self.rej += 1
        else:
            self.bal -= a + 25
            self.fee += 25
    def month(self):
        if self.bal < 0:
            c = (-self.bal * 2) // 100
            self.bal -= c
            self.fee += c

random.seed(8030)
for _ in range(1500):
    evs, acc = [], Account()
    for _ in range(random.randint(0, 15)):
        r = random.random()
        if r < 0.3:
            e = ("deposit", random.choice([1, 25, 100, random.randint(1, 1000)]))
            acc.deposit(e[1])
        elif r < 0.8:
            e = ("withdraw", random.choice([1, 100, 500, 501, random.randint(1, 1200)]))
            acc.withdraw(e[1])
        else:
            e = ("month",)
            acc.month()
        evs.append(list(e) if random.random() < 0.2 else e)
    assert AL(evs) == (acc.bal, acc.rej, acc.fee), evs
''', r'''
def apply_ledger(events):
    if not isinstance(events, (list, tuple)):
        raise ValueError("events must be a list or tuple")
    balance = rejected = fees = 0
    for e in events:
        if not isinstance(e, (list, tuple)) or not e:
            raise ValueError("an event is a non-empty tuple or list")
        if e[0] == "month" and len(e) == 1:
            if balance < 0:
                charge = (-balance * 2) // 100
                balance -= charge
                fees += charge
            continue
        if e[0] not in ("deposit", "withdraw") or len(e) != 2:
            raise ValueError("unknown event")
        amount = e[1]
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise ValueError("amount must be an int >= 1")
        if e[0] == "deposit":
            balance += amount
        elif amount <= balance:
            balance -= amount
        elif balance - amount >= -500:
            balance -= amount + 25
            fees += 25
        else:
            rejected += 1
    return balance, rejected, fees
''')


TASKS = T
