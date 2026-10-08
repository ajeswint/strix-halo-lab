"""loop-v6: 30 held-out Python tasks for the end-to-end pipeline run (Roadmap item 2).

Same layout as tasks_v5.py: id, prompt, tests, ref. Written 2026-10-08 by four parallel writers (one domain
bucket each: formats and encodings 01-08, number theory and combinatorics 09-16, graphs and geometry 17-23,
simulation and DP 24-30) who did not read bench/loop/results/ or the README and ran no model. Unaimed: no
family was chosen from the v4/v5 failures, difficulty was not adjusted, and no test or prompt comes from a
stored error. Sealed held-out set: nobody iterates a prompt, a loop or a design on these tasks. Every test
file has exactly one random.seed(N) line, N = 6000 + task number, so agent.py's fresh-seed grade applies.
Seeded random cases are checked against an oracle built differently from the ref. Each ref is at most 150 lines.
Cold review (2026-10-08): four fresh reviewers saw only the prompts, wrote their own solutions and graded them
against the hidden tests; all 30 reached PASS (6 needed a second attempt, all their own bugs), no prompt changed.
v6_01 wire_records, v6_02 bencode_canonical, v6_03 crc_rocksoft, v6_04 crockford_check, v6_05 strict_csv,
v6_06 ipv6_canonical, v6_07 udp_ipv4_inspect, v6_08 url_normalize, v6_09 sqfree_progression,
v6_10 proper_bracelets, v6_11 nonzero_digit_sum_kth, v6_12 achilles_count, v6_13 simplest_fraction,
v6_14 clamped_lattice, v6_15 square_roots_mod, v6_16 derangement_unrank, v6_17 lexmin_route,
v6_18 hull_peel_layers, v6_19 weight_runs, v6_20 circ_exact_count, v6_21 staircase_log,
v6_22 segment_pair_kinds, v6_23 bridge_free_labels, v6_24 regvm_eight, v6_25 mlfq_finish_times,
v6_26 best_fit_heap, v6_27 wrap_cubic_lines, v6_28 rank_mini_league, v6_29 sweep_ring_state,
v6_30 replay_editor_log.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})

task("v6_01_wire_records", r'''
Write `wiredecode(data)` that strictly decodes a protobuf-style wire message into a list of records. `data` must be a
`bytes` or `bytearray` (anything else raises ValueError). The result is a list (empty for empty data) of tuples
`(field, wire, value)` in input order; `field` and `wire` are ints.

A message is a concatenation of records until the data ends. A record starts with a tag varint T; then `wire = T & 7`
and `field = T >> 3`. The payload depends on `wire`:
- 0: a varint; `value` is that int.
- 1: the next 8 bytes read as a little-endian unsigned int.
- 5: the next 4 bytes read as a little-endian unsigned int.
- 2: a length varint L, then exactly L bytes; `value` is those bytes as a `bytes` object (also when `data` was a
  bytearray; L = 0 gives b"").
- 3, 4, 6, 7: ValueError.

Varint: 1 to 10 bytes, least significant 7-bit group first; bit 0x80 of a byte means another byte follows. Strict rules,
each a ValueError: the data ends in the middle of a varint; a varint longer than 10 bytes; a value of 2**64 or more
(so a 10-byte varint must end in 0x01); a non-minimal encoding, meaning a varint of two or more bytes whose last byte
is 0x00 (b"\x80\x00" is rejected, while the single byte b"\x00" is the valid value 0). The same rules apply to the tag
and to the length varint.

Field numbers: `1 <= field <= 2**29 - 1` is required, and the range 19000..19999 (reserved) is also rejected; any
other field value raises ValueError. A payload that needs more bytes than remain (a fixed width, or a length L larger
than what is left, however large L is) raises ValueError. Trailing bytes are not ignored: they are parsed as further
records, so a dangling partial record is an error. Nothing is returned for a message that fails anywhere; the whole
call either returns the full list or raises ValueError.

Examples:
- `wiredecode(b"\x08\x96\x01") == [(1, 0, 150)]`
- `wiredecode(b"\x12\x07testing") == [(2, 2, b"testing")]`
- `wiredecode(b"\x0d\x01\x00\x00\x00") == [(1, 5, 1)]`
- `wiredecode(b"\x09" + b"\xff" * 8) == [(1, 1, 2**64 - 1)]`
- `wiredecode(b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01") == [(1, 0, 2**64 - 1)]`
- ValueError: `b"\x08\x80\x00"`, `b"\x00\x01"` (field 0), `b"\x0b"` (wire 3), `b"\x12\x05abc"`, `b"\x08\x96"`.
''', r'''
import random
random.seed(6001)

def ev(v):
    out = bytearray()
    while True:
        b = v & 127
        v >>= 7
        if v:
            out.append(b | 128)
        else:
            out.append(b)
            return bytes(out)

def rec(field, wire, value):
    t = ev((field << 3) | wire)
    if wire == 0:
        return t + ev(value)
    if wire == 1:
        return t + value.to_bytes(8, "little")
    if wire == 5:
        return t + value.to_bytes(4, "little")
    return t + ev(len(value)) + value

def o_var(d, p):
    q = p
    while q < len(d) and d[q] >= 128:
        q += 1
    if q >= len(d) or q - p > 9:
        return None
    chunk = d[p:q + 1]
    if len(chunk) > 1 and chunk[-1] == 0:
        return None
    v = 0
    for b in reversed(chunk):
        v = (v << 7) | (b & 127)
    if v >= 1 << 64:
        return None
    return v, q + 1

def oracle(d):
    d = bytes(d)
    p = 0
    out = []
    while p < len(d):
        r = o_var(d, p)
        if r is None:
            return None
        t, p = r
        f, w = t >> 3, t & 7
        if f < 1 or f > 2 ** 29 - 1 or 19000 <= f <= 19999:
            return None
        if w == 0:
            r = o_var(d, p)
            if r is None:
                return None
            out.append((f, 0, r[0]))
            p = r[1]
        elif w in (1, 5):
            k = 8 if w == 1 else 4
            if p + k > len(d):
                return None
            out.append((f, w, int.from_bytes(d[p:p + k], "little")))
            p += k
        elif w == 2:
            r = o_var(d, p)
            if r is None:
                return None
            L, p = r
            if p + L > len(d):
                return None
            out.append((f, 2, d[p:p + L]))
            p += L
        else:
            return None
    return out

def run(d):
    try:
        return wiredecode(d)
    except ValueError:
        return None

def good(d, exp):
    got = wiredecode(d)
    assert type(got) is list and got == exp, (d, got, exp)
    for t in got:
        assert type(t) is tuple and len(t) == 3 and type(t[0]) is int and type(t[1]) is int, t
        assert type(t[2]) is (bytes if t[1] == 2 else int), t

def bad(d):
    try:
        r = wiredecode(d)
    except ValueError:
        return
    raise AssertionError((d, r))

def chk(d):
    got = run(d)
    exp = oracle(d)
    assert got == exp, (bytes(d), got, exp)
    if got is not None:
        for t in got:
            assert type(t[2]) is (bytes if t[1] == 2 else int), t

good(b"", [])
good(b"\x08\x96\x01", [(1, 0, 150)])
good(b"\x12\x07testing", [(2, 2, b"testing")])
good(b"\x0d\x01\x00\x00\x00", [(1, 5, 1)])
good(b"\x09" + b"\xff" * 8, [(1, 1, 2 ** 64 - 1)])
good(b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01", [(1, 0, 2 ** 64 - 1)])
good(b"\x08\x00", [(1, 0, 0)])
good(b"\x08\x80\x01", [(1, 0, 128)])
good(b"\x0a\x00", [(1, 2, b"")])
good(bytearray(b"\x12\x02hi\x08\x01"), [(2, 2, b"hi"), (1, 0, 1)])
good(rec(1, 2, bytes(100000)), [(1, 2, bytes(100000))])
good(rec(18999, 0, 5) + rec(20000, 0, 6) + rec(2 ** 29 - 1, 5, 7),
     [(18999, 0, 5), (20000, 0, 6), (2 ** 29 - 1, 5, 7)])
good(ev(18999 << 3) + b"\x01", [(18999, 0, 1)])
good(b"\x0a\x03abc\x0a\x03abc", [(1, 2, b"abc")] * 2)

for d in (b"\x08\x80\x00", b"\x00\x01", b"\x0b", b"\x12\x05abc", b"\x08\x96", b"\x08", b"\x09" + b"\x00" * 7,
          b"\x0d\x01\x00\x00", b"\x80", b"\x80\x00", b"\x00", b"\x08\x01\x08", b"\x13", b"\x0c", b"\x0e", b"\x0f",
          b"\x08\xff\xff\xff\xff\xff\xff\xff\xff\xff\x02", b"\x08" + b"\x80" * 10 + b"\x01",
          b"\x08" + b"\xff" * 9 + b"\x00", b"\x0a\xff\xff\xff\xff\xff\xff\xff\xff\x7f",
          b"\x0a\x80\x00", b"\x0a\x82\x00ab", b"\x0a\x01", b"\x12\x03ab", b"\x08\x01\x12", b"\xff" * 11 + b"\x01",
          ev(19000 << 3) + b"\x01", ev(19999 << 3) + b"\x01", ev(19500 << 3 | 2) + b"\x00", ev(2 ** 29 << 3) + b"\x01",
          ev(2 ** 32 << 3) + b"\x01", ev(7) + b"\x00", ev(1 << 3 | 4)):
    bad(d)
for d in (None, "\x08\x01", [8, 1], 5, memoryview(b"\x08\x01"), (8, 1), {}):
    bad(d)

for L in range(0, 5):
    bad(rec(1, 2, b"x" * 5)[:-1 - L] if L < 5 else b"")

msgs = []
for _ in range(120):
    n = random.randint(0, 6)
    rs = []
    for _ in range(n):
        w = random.choice([0, 0, 1, 2, 2, 5])
        f = random.choice([1, 2, 15, 16, 2047, 2048, 18999, 20000, 2 ** 29 - 1, random.randint(1, 10 ** 6)])
        if 19000 <= f <= 19999:
            f = 19999 + random.randint(1, 5)
        if w == 0:
            v = random.choice([0, 1, 127, 128, 16383, 16384, 2 ** 64 - 1, random.getrandbits(random.randint(1, 64))])
        elif w == 1:
            v = random.getrandbits(64)
        elif w == 5:
            v = random.getrandbits(32)
        else:
            v = bytes(random.getrandbits(8) for _ in range(random.choice([0, 1, 2, 127, 128, 129, 300])))
        rs.append((f, w, v))
    d = b"".join(rec(*r) for r in rs)
    good(d, rs)
    msgs.append(d)

for d in msgs:
    for _ in range(12):
        m = bytearray(d)
        kind = random.randint(0, 3)
        if kind == 0 and m:
            del m[random.randrange(len(m)):]
        elif kind == 1 and m:
            m[random.randrange(len(m))] = random.getrandbits(8)
        elif kind == 2:
            m.insert(random.randint(0, len(m)), random.choice([0, 0x80, 0xff, 0x7f, 1, 2, 8]))
        else:
            m += bytes(random.choice([0, 1, 0x80, 0x08, 0x0a, 0x0d, 0x09, 0xff]) for _ in range(random.randint(1, 4)))
        chk(bytes(m))

ALPHA = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 13, 0x80, 0x81, 0xff, 0x7f, 0xc0, 0x20]
for _ in range(4000):
    chk(bytes(random.choice(ALPHA) for _ in range(random.randint(0, 9))))
''', r'''
def wiredecode(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("type")
    data = bytes(data)
    n = len(data)
    pos = 0

    def varint():
        nonlocal pos
        val = 0
        for i in range(10):
            if pos >= n:
                raise ValueError("truncated")
            b = data[pos]
            pos += 1
            val |= (b & 0x7F) << (7 * i)
            if not b & 0x80:
                if i > 0 and b == 0:
                    raise ValueError("overlong")
                if val >> 64:
                    raise ValueError("range")
                return val
        raise ValueError("too long")

    def fixed(k):
        nonlocal pos
        if pos + k > n:
            raise ValueError("short")
        v = int.from_bytes(data[pos:pos + k], "little")
        pos += k
        return v

    out = []
    while pos < n:
        tag = varint()
        wire = tag & 7
        field = tag >> 3
        if not 1 <= field <= 2 ** 29 - 1 or 19000 <= field <= 19999:
            raise ValueError("field")
        if wire == 0:
            out.append((field, 0, varint()))
        elif wire == 1:
            out.append((field, 1, fixed(8)))
        elif wire == 5:
            out.append((field, 5, fixed(4)))
        elif wire == 2:
            length = varint()
            if pos + length > n:
                raise ValueError("short")
            out.append((field, 2, data[pos:pos + length]))
            pos += length
        else:
            raise ValueError("wire")
    return out
''')

task("v6_02_bencode_canonical", r'''
Write `benc_strict_load(data)` that parses one bencode value and accepts only its canonical encoding. `data` must be
a `bytes` object (bytearray, str, anything else raises ValueError). Return an int, a `bytes`, a list, or a dict whose
keys are `bytes`, with the dict keeping the key order of the input. Any violation below raises ValueError.

Grammar:
- Integer: `i`, optional `-`, decimal digits, `e`. The digits are ASCII 0-9 only, at most 100 of them, with no leading
  zero (so `i0e` is fine, `i03e` is not), at least one digit, and negative zero `i-0e` is rejected. No `+`, no spaces,
  no underscores: `i+5e`, `i 5e`, `i1_0e`, `ie`, `i-e` are all errors.
- String: a decimal length, `:`, then exactly that many bytes. The length has no sign and no leading zero (`0:` is the
  empty string; `00:`, `01:a` and `+1:a` are errors). A length larger than the bytes that remain is an error, however
  large the digits are.
- List: `l`, zero or more values, `e`.
- Dict: `d`, zero or more key/value pairs, `e`. Every key is a string, and the keys must be strictly increasing when
  compared as raw bytes (Python `bytes` comparison, so `b"Z" < b"a"` and `b"a" < b"ab"`). A repeated key counts as
  not increasing. A key without a value (`d3:fooe`) is an error.
- Nesting: containers may be nested at most 64 deep. The outermost list or dict has depth 1, so 64 nested `l` is
  accepted and 65 is a ValueError. The check must hold for inputs with hundreds of thousands of nested openers
  without hitting any other exception type.
- The whole input must be exactly one value: empty input, missing terminators, or any byte after the value is an error.

Examples:
- `benc_strict_load(b"i42e") == 42`, `benc_strict_load(b"i-42e") == -42`, `benc_strict_load(b"i0e") == 0`
- `benc_strict_load(b"4:spam") == b"spam"`, `benc_strict_load(b"0:") == b""`
- `benc_strict_load(b"l4:spami42ee") == [b"spam", 42]`
- `benc_strict_load(b"d3:cow3:moo4:spam4:eggse") == {b"cow": b"moo", b"spam": b"eggs"}`
- ValueError: `b"d4:spam4:eggs3:cow3:mooe"` (keys out of order), `b"i03e"`, `b"i-0e"`, `b"3:ab"`, `b"i1ex"`, `b"l"`.
''', r'''
import random
random.seed(6002)

def enc(v):
    if type(v) is int:
        return b"i%de" % v
    if type(v) is bytes:
        return b"%d:%s" % (len(v), v)
    if type(v) is list:
        return b"l" + b"".join(enc(x) for x in v) + b"e"
    return b"d" + b"".join(enc(k) + enc(v[k]) for k in sorted(v)) + b"e"

def same(a, b):
    assert type(a) is type(b), (a, b)
    if type(a) is list:
        assert len(a) == len(b)
        for x, y in zip(a, b):
            same(x, y)
    elif type(a) is dict:
        assert list(a) == list(b), (list(a), list(b))
        for k in a:
            same(a[k], b[k])
    else:
        assert a == b, (a, b)

def good(d, exp):
    got = benc_strict_load(d)
    same(got, exp)

def bad(d):
    try:
        r = benc_strict_load(d)
    except ValueError:
        return
    raise AssertionError((d, r))

def rval(depth):
    k = random.randint(0, 5 if depth < 4 else 3)
    if k <= 1:
        return random.choice([0, 1, -1, 9, 10, -10, 12345, 2 ** 70, -2 ** 70, random.randint(-10 ** 9, 10 ** 9)])
    if k <= 3:
        return bytes(random.choice(b"abz:ie019-\x00\xff") for _ in range(random.randint(0, 12)))
    if k == 4:
        return [rval(depth + 1) for _ in range(random.randint(0, 4))]
    d = {}
    for _ in range(random.randint(0, 4)):
        d[bytes(random.choice(b"aAbZz01") for _ in range(random.randint(0, 3)))] = rval(depth + 1)
    return dict(sorted(d.items()))

good(b"i42e", 42)
good(b"i-42e", -42)
good(b"i0e", 0)
good(b"4:spam", b"spam")
good(b"0:", b"")
good(b"l4:spami42ee", [b"spam", 42])
good(b"d3:cow3:moo4:spam4:eggse", {b"cow": b"moo", b"spam": b"eggs"})
good(b"le", [])
good(b"de", {})
good(b"d0:i1e1:ai2e2:aai3ee", {b"": 1, b"a": 2, b"aa": 3})
good(b"d1:Zi1e1:ai2ee", {b"Z": 1, b"a": 2})
good(b"d1:a0:e", {b"a": b""})
good(b"i" + b"9" * 100 + b"e", int("9" * 100))
good(b"i-" + b"9" * 100 + b"e", -int("9" * 100))
good(b"10:abcdefghij", b"abcdefghij")
good(b"3:i1e", b"i1e")
good(b"3:\x00\xff\x80", b"\x00\xff\x80")
nest = []
for _ in range(63):
    nest = [nest]
good(b"l" * 64 + b"e" * 64, nest)
good(b"d1:ad1:blee" + b"e", {b"a": {b"b": []}})

for d in (b"d4:spam4:eggs3:cow3:mooe", b"i03e", b"i-0e", b"3:ab", b"i1ex", b"l", b"", b"i", b"ie", b"i-e", b"i+5e",
          b"i 5e", b"i1_0e", b"i1.5e", b"i00e", b"i-03e", b"i5", b"i5ee", b"00:", b"01:a", b"+1:a", b"-1:", b"1:",
          b":", b"1a:b", b"3:abcd" + b"x", b"d3:fooe", b"d3:foo3:bar3:fooi1ee", b"d1:ai1e1:ai2ee", b"d1:bi1e1:ai2ee",
          b"di1ei2ee", b"d1:ai1e", b"l1:a", b"x", b"e", b"d1:a1:be1", b"li1e", b"lie", b"l1:ae1:b",
          b"i" + b"9" * 101 + b"e", b"i-" + b"9" * 101 + b"e", b"i" + b"0" * 5 + b"e", b"99999999999999999999:ab",
          b"9" * 5000 + b":a", b"d2:ab1:a1:a1:be", b"d1:ai1e1:Zi2ee", b"d1:Zi1e1:Zi1ee",
          b"l" * 65 + b"e" * 65, b"d1:a" * 65 + b"i1e" + b"e" * 65, b"l" * 300000, b"l" * 300000 + b"e" * 300000,
          b"d" * 100000, b"i1e\n", b" i1e", b"i1e i1e", b"i1ei1e", b"1:a1:b", b"\xef\xbb\xbfi1e"):
    bad(d)
for d in (None, "i1e", 5, [b"i1e"], bytearray(b"i1e"), memoryview(b"i1e"), {}, True):
    bad(d)

for _ in range(300):
    v = rval(0)
    d = enc(v)
    good(d, v)
    for i in range(len(d)):
        if random.random() < 0.15:
            bad(d[:i])
    for tail in (b"e", b"0", b"i1e", b" ", b"\n", b"l"):
        bad(d + tail)
    bad(d + d)
    m = bytearray(d)
    if m:
        for _ in range(4):
            m[random.randrange(len(m))] = random.choice(b"0123456789:ilde-")
        try:
            r = benc_strict_load(bytes(m))
        except ValueError:
            r = None
        if r is not None:
            assert enc(r) == bytes(m), (bytes(m), r)
    m = bytearray(d)
    if len(m) > 2:
        p = random.randrange(len(m))
        m.insert(p, random.choice(b"0:-ie "))
        try:
            r = benc_strict_load(bytes(m))
        except ValueError:
            r = None
        if r is not None:
            assert enc(r) == bytes(m), (bytes(m), r)

big = {b"k%05d" % i: [i, b"v" * (i % 7)] for i in range(3000)}
good(enc(big), big)
''', r'''
def benc_strict_load(data):
    if type(data) is not bytes:
        raise ValueError("type")
    n = len(data)

    def digits(p):
        q = p
        while q < n and 48 <= data[q] <= 57:
            q += 1
        return q

    def string(p):
        r = digits(p)
        ds = data[p:r]
        if not ds or r >= n or data[r] != 58 or (len(ds) > 1 and ds[0] == 48):
            raise ValueError("string")
        if len(ds) > 20:
            raise ValueError("length")
        length = int(ds)
        start = r + 1
        if length > n - start:
            raise ValueError("short")
        return data[start:start + length], start + length

    def parse(p, depth):
        if p >= n:
            raise ValueError("eof")
        c = data[p]
        if c == 0x69:
            q = p + 1
            neg = q < n and data[q] == 0x2D
            if neg:
                q += 1
            r = digits(q)
            ds = data[q:r]
            if not ds or len(ds) > 100 or (ds[0] == 48 and (len(ds) > 1 or neg)):
                raise ValueError("int")
            if r >= n or data[r] != 0x65:
                raise ValueError("int end")
            v = int(ds)
            return (-v if neg else v), r + 1
        if 48 <= c <= 57:
            return string(p)
        if c == 0x6C or c == 0x64:
            if depth + 1 > 64:
                raise ValueError("depth")
            if c == 0x6C:
                items = []
                p += 1
                while True:
                    if p >= n:
                        raise ValueError("eof")
                    if data[p] == 0x65:
                        return items, p + 1
                    v, p = parse(p, depth + 1)
                    items.append(v)
            result = {}
            prev = None
            p += 1
            while True:
                if p >= n:
                    raise ValueError("eof")
                if data[p] == 0x65:
                    return result, p + 1
                if not 48 <= data[p] <= 57:
                    raise ValueError("key")
                k, p = string(p)
                if prev is not None and not k > prev:
                    raise ValueError("order")
                prev = k
                v, p = parse(p, depth + 1)
                result[k] = v
        raise ValueError("token")

    value, end = parse(0, 0)
    if end != n:
        raise ValueError("trailing")
    return value
''')

task("v6_03_crc_rocksoft", r'''
Write `crcrocksoft(data, width, poly, init, refin, refout, xorout)` that computes a CRC in the Rocksoft parameter
model for any register width from 1 to 64 bits, and returns it as an int.

Arguments: `data` is `bytes` or `bytearray`; `width` is an int with 1 <= width <= 64; `poly`, `init` and `xorout` are
ints with 0 <= value < 2**width (bool is not an int here); `refin` and `refout` must be exactly True or False. Anything
else raises ValueError (a bool for width/poly/init/xorout, an int for refin/refout, wrong ranges, wrong data type).

Definition. `poly` is always given in normal (non-reflected) form: the implicit top x**width term is left out, and
reflection only changes how bits are fed and read. The register is `width` bits wide and starts as `init` (also given as
is, never reflected). Process the message bytes in order; for each byte, if `refin` is True take its 8 bits least
significant first, otherwise most significant first. For each message bit b: let t be the register's top bit (bit
width-1); shift the register left by one bit, dropping the old top bit (keep `width` bits); if t xor b is 1, xor `poly`
into the register. After the last bit, if `refout` is True reverse the order of the register's `width` bits (bit 0
becomes bit width-1 and so on); finally xor with `xorout` and return the result. `refin` and `refout` are independent,
and widths that are not multiples of 8 (3, 5, 12, 15, ...) are fully supported. Empty data is valid: the result is the
(optionally reflected) `init` xor `xorout`.

Check values for the ASCII data b"123456789":
- `crcrocksoft(b"123456789", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF) == 0xCBF43926`
- `crcrocksoft(b"123456789", 16, 0x1021, 0xFFFF, False, False, 0) == 0x29B1`
- `crcrocksoft(b"123456789", 12, 0x80F, 0, False, True, 0) == 0xDAF` (input not reflected, output reflected)
- `crcrocksoft(b"123456789", 5, 0x05, 0x1F, True, True, 0x1F) == 0x19`
- `crcrocksoft(b"123456789", 3, 0x3, 0, False, False, 0x7) == 0x4`
- `crcrocksoft(b"", 8, 0x07, 0x80, False, True, 0) == 0x01`
- `crcrocksoft(b"", 8, 0x07, 0x80, False, False, 0x0F) == 0x8F`
''', r'''
import random
random.seed(6003)

def pmod(a, p):
    pl = p.bit_length()
    while a.bit_length() >= pl:
        a ^= p << (a.bit_length() - pl)
    return a

def rev(x, w):
    return int(format(x, "0%db" % w)[::-1], 2)

def oracle(data, w, poly, init, ri, ro, xo):
    bits = ""
    for b in data:
        s = format(b, "08b")
        bits += s[::-1] if ri else s
    L = len(bits)
    m = int(bits, 2) if bits else 0
    P = (1 << w) | poly
    r = pmod((m << w) ^ (init << L), P)
    if ro:
        r = rev(r, w)
    return r ^ xo

def same(*a):
    got = crcrocksoft(*a)
    assert type(got) is int and got == oracle(*a), (a, got, oracle(*a))
    return got

def rej(*a):
    try:
        crcrocksoft(*a)
    except ValueError:
        return True
    return False

S = b"123456789"
MODELS = [
    ("CRC-32/ISO-HDLC", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xCBF43926),
    ("CRC-32/BZIP2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0xFFFFFFFF, 0xFC891918),
    ("CRC-32/MPEG-2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0, 0x0376E6E7),
    ("CRC-32/ISCSI", 32, 0x1EDC6F41, 0xFFFFFFFF, True, True, 0xFFFFFFFF, 0xE3069283),
    ("CRC-16/CCITT-FALSE", 16, 0x1021, 0xFFFF, False, False, 0, 0x29B1),
    ("CRC-16/ARC", 16, 0x8005, 0, True, True, 0, 0xBB3D),
    ("CRC-16/XMODEM", 16, 0x1021, 0, False, False, 0, 0x31C3),
    ("CRC-16/KERMIT", 16, 0x1021, 0, True, True, 0, 0x2189),
    ("CRC-16/MODBUS", 16, 0x8005, 0xFFFF, True, True, 0, 0x4B37),
    ("CRC-8/SMBUS", 8, 0x07, 0, False, False, 0, 0xF4),
    ("CRC-8/MAXIM", 8, 0x31, 0, True, True, 0, 0xA1),
    ("CRC-5/USB", 5, 0x05, 0x1F, True, True, 0x1F, 0x19),
    ("CRC-12/UMTS", 12, 0x80F, 0, False, True, 0, 0xDAF),
    ("CRC-3/GSM", 3, 0x3, 0, False, False, 0x7, 0x4),
    ("CRC-4/G-704", 4, 0x3, 0, True, True, 0, 0x7),
    ("CRC-7/MMC", 7, 0x09, 0, False, False, 0, 0x75),
    ("CRC-10/ATM", 10, 0x233, 0, False, False, 0, 0x199),
    ("CRC-15/CAN", 15, 0x4599, 0, False, False, 0, 0x059E),
    ("CRC-64/XZ", 64, 0x42F0E1EBA9EA3693, 2 ** 64 - 1, True, True, 2 ** 64 - 1, 0x995DC9BBDF1939FA),
    ("CRC-64/ECMA-182", 64, 0x42F0E1EBA9EA3693, 0, False, False, 0, 0x6C40DF5F0B497347),
]
for name, w, poly, init, ri, ro, xo, exp in MODELS:
    got = crcrocksoft(S, w, poly, init, ri, ro, xo)
    assert type(got) is int and got == exp, (name, hex(got), hex(exp))
    assert got == oracle(S, w, poly, init, ri, ro, xo), name
    assert crcrocksoft(bytearray(S), w, poly, init, ri, ro, xo) == exp, name

assert same(b"", 8, 0x07, 0x80, False, True, 0) == 0x01
assert same(b"", 8, 0x07, 0x80, False, False, 0x0F) == 0x8F
assert same(b"", 8, 0x07, 0x80, True, False, 0) == 0x80
assert same(b"", 1, 1, 1, True, True, 0) == 1
assert same(b"", 64, 1, 2 ** 64 - 1, False, True, 0) == 2 ** 64 - 1
assert same(b"", 12, 0x80F, 0x001, False, True, 0) == 0x800
assert same(b"", 12, 0x80F, 0x001, False, False, 0) == 0x001
assert same(b"\x00", 8, 0x07, 0, False, False, 0) == 0
assert same(b"\x01", 8, 0x07, 0, False, False, 0) == 0x07
assert same(b"\x80", 8, 0x07, 0, True, False, 0) == 0x07
assert same(b"\x80", 8, 0x07, 0, True, True, 0) == 0xE0

for w in range(1, 65):
    for ri in (False, True):
        for ro in (False, True):
            poly = random.getrandbits(w)
            init = random.choice([0, (1 << w) - 1, random.getrandbits(w)])
            xo = random.choice([0, (1 << w) - 1, random.getrandbits(w)])
            data = bytes(random.getrandbits(8) for _ in range(random.randint(0, 12)))
            same(data, w, poly, init, ri, ro, xo)

for _ in range(250):
    w = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 15, 16, 17, 24, 31, 32, 33, 40, 63, 64])
    data = bytes(random.getrandbits(8) for _ in range(random.randint(0, 40)))
    same(data, w, random.getrandbits(w), random.getrandbits(w), random.random() < 0.5, random.random() < 0.5,
         random.getrandbits(w))

a = same(S, 16, 0x1021, 0xFFFF, False, False, 0)
assert a == 0x29B1
big = bytes(random.getrandbits(8) for _ in range(300))
same(big, 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF)
same(big, 7, 0x09, 0x55, True, False, 0x2A)
same(big, 64, 0x42F0E1EBA9EA3693, 2 ** 64 - 1, True, True, 2 ** 64 - 1)

for bad in (0, -1, 65, 100, True, 8.0, "8", None):
    assert rej(S, bad, 1, 0, False, False, 0), bad
assert rej(S, 8, 256, 0, False, False, 0)
assert rej(S, 8, -1, 0, False, False, 0)
assert rej(S, 8, 1, 256, False, False, 0)
assert rej(S, 8, 1, -1, False, False, 0)
assert rej(S, 8, 1, 0, False, False, 256)
assert rej(S, 8, 1, 0, False, False, -1)
assert rej(S, 3, 8, 0, False, False, 0)
assert rej(S, 3, 1, 8, False, False, 0)
assert rej(S, 3, 1, 0, False, False, 8)
assert rej(S, 64, 2 ** 64, 0, False, False, 0)
assert rej(S, 8, True, 0, False, False, 0)
assert rej(S, 8, 1, True, False, False, 0)
assert rej(S, 8, 1, 0, False, False, True)
assert rej(S, 1, 1, 0, False, False, True)
assert not rej(S, 1, 1, 0, False, False, 1)
assert rej(S, 8, 1, 0, 1, False, 0)
assert rej(S, 8, 1, 0, False, 0, 0)
assert rej(S, 8, 1, 0, None, False, 0)
assert rej(S, 8, 1, 0, False, "yes", 0)
assert rej(S, 8, 1.0, 0, False, False, 0)
assert rej("123456789", 8, 7, 0, False, False, 0)
assert rej([49, 50], 8, 7, 0, False, False, 0)
assert rej(None, 8, 7, 0, False, False, 0)
assert rej(memoryview(S), 8, 7, 0, False, False, 0)
assert rej(5, 8, 7, 0, False, False, 0)
''', r'''
def crcrocksoft(data, width, poly, init, refin, refout, xorout):
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data")
    if type(width) is not int or not 1 <= width <= 64:
        raise ValueError("width")
    limit = 1 << width
    for v in (poly, init, xorout):
        if type(v) is not int or not 0 <= v < limit:
            raise ValueError("value")
    if type(refin) is not bool or type(refout) is not bool:
        raise ValueError("flag")
    mask = limit - 1
    top = 1 << (width - 1)
    reg = init
    for byte in data:
        if refin:
            byte = int(format(byte, "08b")[::-1], 2)
        for i in range(7, -1, -1):
            bit = (byte >> i) & 1
            feedback = (1 if reg & top else 0) ^ bit
            reg = (reg << 1) & mask
            if feedback:
                reg ^= poly
    if refout:
        reg = int(format(reg, "0%db" % width)[::-1], 2)
    return reg ^ xorout
''')

task("v6_04_crockford_check", r'''
Write `crock32_value(text, check=False)` that decodes a Crockford Base32 string to a non-negative int. `text` must be
a `str` and `check` must be exactly True or False; otherwise raise ValueError. All problems below raise ValueError.

Alphabet. The 32 symbols are `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (digits 0-9, then letters with I, L, O, U left out),
with values 0..31 in that order. Decoding is the usual big-endian base 32: "10" is 32, "ZZ" is 1023. Leading zero symbols
are fine ("0007" is 7).

Normalisation, applied first. Every hyphen `-` is removed from anywhere in the text (any number of them, at the start
or the end too). Letters are case-insensitive, but only the ASCII letters a-z: the whole text must be ASCII, and any
non-ASCII character (even one that Python's `str.upper()` or `str.lower()` would map to an ASCII letter, such as the
dotless i U+0131 or the long s U+017F) is a ValueError. After removing hyphens, `O` and `o` are read as 0, and `I`, `i`,
`L`, `l` are read as 1. This aliasing applies at every position, including the check symbol position below. Any other
character (spaces, `_`, `U`/`u` in the data part, punctuation, control characters) is invalid. If nothing is left after
removing hyphens, that is a ValueError.

Check symbol. When `check` is False, the remaining text is the number and has no check symbol. When `check` is True, the
LAST remaining symbol is a check symbol and the symbols before it (at least one) are the number; the result is the
number only. The check symbol set is the 32 alphabet symbols followed by `*`, `~`, `$`, `=` and `U` (in that order),
which stand for the values 32, 33, 34, 35, 36, so 37 symbols with values 0..36 (case-insensitive for `U`). It is valid
only when it equals the number modulo 37. Characters `*~$=` and `U` are valid only in the check position and only
when `check` is True. If `check` is True and fewer than two symbols remain, or the check symbol is wrong, ValueError.

Examples: `crock32_value("10") == 32`, `crock32_value("zz") == 1023`, `crock32_value("O-I1l0") == 33824` (digits
0,1,1,1,0), `crock32_value("14U", True) == 36`, `crock32_value("14u", True) == 36`, `crock32_value("13=", True) == 35`,
`crock32_value("10*", True) == 32`, `crock32_value("00", True) == 0`. Errors: `crock32_value("14=", True)`,
`crock32_value("1*")`, `crock32_value("1U")`, `crock32_value("")`, `crock32_value("---")`, `crock32_value("\u0131")`.
''', r'''
import random
random.seed(6004)

AL = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
EXT = AL + "*~$=U"

def enc(v):
    s = ""
    while v:
        s = AL[v % 32] + s
        v //= 32
    return s or "0"

ALIAS = {"0": "0Oo", "1": "1IiLl"}

def spell_sym(c):
    if c in ALIAS:
        return random.choice(ALIAS[c])
    if c.isalpha():
        return random.choice([c, c.lower()])
    return c

def sprinkle(s):
    out = ""
    for c in s:
        if random.random() < 0.2:
            out += "-" * random.randint(1, 2)
        out += c
    if random.random() < 0.2:
        out += "-"
    return out

def good(*a, exp):
    got = crock32_value(*a)
    assert type(got) is int and got == exp, (a, got, exp)

def rej(*a, **k):
    try:
        crock32_value(*a, **k)
    except ValueError:
        return True
    return False

good("10", exp=32)
good("zz", exp=1023)
good("ZZ", exp=1023)
good("O-I1l0", exp=33824)
good("0007", exp=7)
good("0", exp=0)
good("o", exp=0)
good("-0-", exp=0)
good("---1", exp=1)
good("14U", True, exp=36)
good("14u", True, exp=36)
good("13=", True, exp=35)
good("10*", True, exp=32)
good("00", True, exp=0)
good("11", True, exp=1)
good("1-1", True, exp=1)
good("l-I", True, exp=1)
good("OO", True, exp=0)
good("0o", True, exp=0)
good("10", False, exp=32)
good("1Z", exp=63)
good("z", exp=31)
good("Z" * 2000, exp=32 ** 2000 - 1)
good("1" + "0" * 3000, exp=32 ** 3000)
good("15" + "0", True, exp=37)
good("1" + "5" + "-0", True, exp=37)
good(enc(36) + "U", True, exp=36)

for s in ("", "-", "---", "U", "u1", "1U", "1*", "1~", "1$", "1=", "1 ", " 1", "1_1", "\u0131", "\u017f", "\u212a",
          "1\u0131", "\uff21", "\u0663", "1\n", "\t1", "1.", "1,1", "A#", "1\x00", "\xe91", "\u00dfa", "\U0001d7ce"):
    assert rej(s), s
assert rej("14=", True)
assert rej("14*", True)
assert rej("14~", True)
assert rej("14$", True)
assert rej("140", True)
assert rej("1", True)
assert rej("-1-", True)
assert rej("", True)
assert rej("-", True)
assert rej("0", True) and rej("U", True) and rej("-U-", True)
assert rej("1U1", True)
assert rej("U1", True)
assert rej("*0", True) and rej("1*0", True)
assert rej("01", True)
assert rej("\u0131U", True) and rej("1\u017f", True)
assert rej("10\u212a", True)
assert rej("1 U", True)
for bad in (None, 5, b"10", ["1"], 1.5, True):
    assert rej(bad) and rej(bad, True), bad
for chk in (1, 0, None, "yes", "", 1.0, [True]):
    assert rej("10", chk), chk
    assert rej("10", check=chk), chk
good("14U", True, exp=36)

for _ in range(500):
    v = random.choice([random.randint(0, 40), random.randint(0, 2 ** 20), random.getrandbits(random.randint(1, 200))])
    body = enc(v)
    if random.random() < 0.3:
        body = "0" * random.randint(1, 4) + body
    chk = random.random() < 0.5
    s = "".join(spell_sym(c) for c in body)
    if chk:
        s += spell_sym(EXT[v % 37])
    s = sprinkle(s)
    good(s, chk, exp=v)
    if chk:
        wrong = random.choice([c for c in EXT if c != EXT[v % 37]])
        bs = "".join(spell_sym(c) for c in body) + spell_sym(wrong)
        assert rej(sprinkle(bs), True), (bs, v)
        assert rej(s[:-1] + "\u0131" if s[-1] not in "iI" else s[:-1] + "\u017f", True)
    else:
        extra = random.choice("U*~$=uÅ_ ")
        pos = random.randint(0, len(s))
        assert rej(s[:pos] + extra + s[pos:]), (s, extra)
''', r'''
def crock32_value(text, check=False):
    if type(text) is not str or type(check) is not bool:
        raise ValueError("type")
    if not text.isascii():
        raise ValueError("non-ascii")
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    extended = alphabet + "*~$=U"
    aliases = {"O": "0", "I": "1", "L": "1"}
    syms = []
    for ch in text:
        if ch == "-":
            continue
        c = ch.upper()
        syms.append(aliases.get(c, c))
    if check:
        if len(syms) < 2:
            raise ValueError("short")
        body, tail = syms[:-1], syms[-1]
    else:
        body, tail = syms, None
    if not body:
        raise ValueError("empty")
    value = 0
    for c in body:
        i = alphabet.find(c)
        if i < 0:
            raise ValueError("symbol")
        value = value * 32 + i
    if check:
        j = extended.find(tail)
        if j < 0 or value % 37 != j:
            raise ValueError("check")
    return value
''')

task("v6_05_strict_csv", r'''
Write `strictcsv_rows(text)` that parses CSV text strictly and returns a list of rows, each row a list of `str`. `text`
must be a `str`, otherwise raise ValueError. The result for an input is either the complete list of rows or a
ValueError; every rule below that says "error" raises ValueError.

Records and fields:
- A record ends at `\n` or `\r\n` (outside quotes). The last record may omit its terminator. The empty text gives `[]`.
  A terminator at the very end of the text does NOT start another record, so `"a\n"` is one row.
- Fields in a record are separated by `,`. A record with zero characters (an empty line) is a record with exactly one
  empty field, `[""]`. A trailing comma adds an empty last field: `"a,"` is `[["a", ""]]`.
- An unquoted field holds any characters except `,`, `"`, `\r` and `\n`. A `"` inside an unquoted field is an error, and
  so is a `\r` that is not immediately followed by `\n` when it appears outside quotes.
- A quoted field starts with `"` at the very start of a field. Inside it, `""` stands for one `"` character, and every
  other character, including `,`, `\r` and `\n`, is kept exactly as written (no newline normalisation). The field
  ends at the first `"` that is not part of a `""` pair. The character right after the closing quote must be `,`, the
  start of a terminator, or the end of the text; anything else is an error. A quoted field that never closes is an error.
- Every record must have the same number of fields as the first record; otherwise error. So `"a,b\n\n"` is an error
  (the empty line is a one-field record), while `"x\n\ny"` is `[["x"], [""], ["y"]]`.
- No other special handling: spaces are data, there is no trimming, a leading U+FEFF is an ordinary character.

Examples:
- `strictcsv_rows("a,b\r\n1,2\n")` is `[["a", "b"], ["1", "2"]]`
- `strictcsv_rows('"a,""b""",c')` is `[['a,"b"', "c"]]`
- `strictcsv_rows('"x\r\ny"\n')` is `[["x\r\ny"]]`
- `strictcsv_rows("")` is `[]`, `strictcsv_rows("\n")` is `[[""]]`, `strictcsv_rows(",\n,")` is `[["", ""], ["", ""]]`
- Errors: `'a"b'`, `'"ab"c'`, `'"ab'`, `"a\rb"`, `"a,b\n\n"`, `"a,b\nc"`, `'"a""'`.
''', r'''
import random
import re
random.seed(6005)

FIELD = re.compile(r'"((?:[^"]|"")*)"|([^",\r\n]*)')

def oracle(t):
    if t == "":
        return []
    rows, row, i, n = [], [], 0, len(t)
    while True:
        m = FIELD.match(t, i)
        row.append(m.group(1).replace('""', '"') if m.group(1) is not None else m.group(2))
        i = m.end()
        if i >= n:
            rows.append(row)
            break
        if t[i] == ",":
            i += 1
            continue
        if t.startswith("\r\n", i):
            i += 2
        elif t[i] == "\n":
            i += 1
        else:
            return None
        rows.append(row)
        row = []
        if i >= n:
            break
    if any(len(r) != len(rows[0]) for r in rows):
        return None
    return rows

def run(t):
    try:
        return strictcsv_rows(t)
    except ValueError:
        return None

def good(t, exp):
    got = strictcsv_rows(t)
    assert got == exp, (t, got, exp)
    assert type(got) is list and all(type(r) is list and all(type(f) is str for f in r) for r in got), got

def bad(t):
    r = run(t)
    assert r is None, (t, r)

good("a,b\r\n1,2\n", [["a", "b"], ["1", "2"]])
good('"a,""b""",c', [['a,"b"', "c"]])
good('"x\r\ny"\n', [["x\r\ny"]])
good("", [])
good("\n", [[""]])
good("\r\n", [[""]])
good(",\n,", [["", ""], ["", ""]])
good("x\n\ny", [["x"], [""], ["y"]])
good("a", [["a"]])
good("a,", [["a", ""]])
good(",", [["", ""]])
good(",,", [["", "", ""]])
good('""', [[""]])
good('""\n', [[""]])
good('"",""', [["", ""]])
good('""""', [['"']])
good('""""""', [['""']])
good('"a""b"', [['a"b']])
good('"\n"', [["\n"]])
good('"\r"', [["\r"]])
good('"a\nb",c\r\n"d\r\ne",f', [["a\nb", "c"], ["d\r\ne", "f"]])
good('"a"\r\n"b"', [["a"], ["b"]])
good('a,"b"\n', [["a", "b"]])
good('"a",b,"c"', [["a", "b", "c"]])
good(" a , b ", [[" a ", " b "]])
good("\ufeffa,b", [["\ufeffa", "b"]])
good("a\n\n\n", [["a"], [""], [""]])
good("a\r\n\r\n", [["a"], [""]])
good("\n\n", [[""], [""]])
good("a,b\r\nc,d\r\n", [["a", "b"], ["c", "d"]])
good("a,b\nc,d", [["a", "b"], ["c", "d"]])
good('"a,b"', [["a,b"]])
good('"a\r\nb"\r\n', [["a\r\nb"]])
good("é,ü\n\u4e2d,\U0001f600", [["é", "ü"], ["\u4e2d", "\U0001f600"]])
good('a,"",c', [["a", "", "c"]])
good("a;b\tc", [["a;b\tc"]])
good("a'b", [["a'b"]])

for t in ('a"b', '"ab"c', '"ab', "a\rb", "a,b\n\n", "a,b\nc", '"a""', "a\r", "\r", "a,b\r", "a\r\r\nb", '"', '"""',
          'a,"b', '"a"b', '"a" ', ' "a"', '"a",b"', 'a,"b"c', '"a""b', '""a"', '"a"\r', '"a"\rb', '"a"\n"b', 'a,b,c\na,b',
          'a\n\n,', "\n,", 'a\nb,c', '"a",\n"b"', 'x"', '""x', '"a"""b"', 'a\n"b"c', 'a,\r'):
    bad(t)
for t in (None, b"a,b", 5, ["a"], ("a",), 1.5, True):
    assert run(t) is None, t

def esc(f, force):
    if force or any(c in f for c in ',"\r\n'):
        return '"' + f.replace('"', '""') + '"'
    return f

for _ in range(600):
    w = random.randint(1, 4)
    nr = random.randint(1, 5)
    rows = [["".join(random.choice('ab ,"\r\n\té') for _ in range(random.randint(0, 4))) for _ in range(w)]
            for _ in range(nr)]
    final = random.random() < 0.5
    parts = []
    for i, r in enumerate(rows):
        lastbare = i == nr - 1 and not final
        fs = []
        for f in r:
            force = random.random() < 0.3 or (w == 1 and f == "" and lastbare)
            fs.append(esc(f, force))
        parts.append(",".join(fs))
    text = ""
    for i, p in enumerate(parts):
        text += p
        if i < nr - 1 or final:
            text += random.choice(["\n", "\r\n"])
    good(text, rows)
    assert oracle(text) == rows

for _ in range(6000):
    t = "".join(random.choice('ab,"\r\n') for _ in range(random.randint(0, 11)))
    assert run(t) == oracle(t), (t, run(t), oracle(t))

for _ in range(1500):
    t = "".join(random.choice('a,,""\n') for _ in range(random.randint(0, 14)))
    assert run(t) == oracle(t), (t, run(t), oracle(t))

big = [["f%d" % i, "q,%d" % i, 'x"%d' % i] for i in range(2000)]
text = "\n".join(",".join(esc(f, False) for f in r) for r in big)
good(text, big)
good('"' + 'a""b,\n' * 30000 + '"', [['a"b,\n' * 30000]])
bad('"' + 'a""b,\n' * 30000)
''', r'''
def strictcsv_rows(text):
    if type(text) is not str:
        raise ValueError("type")
    n = len(text)
    if n == 0:
        return []
    rows = []
    row = []
    i = 0

    def finish():
        if rows and len(row) != len(rows[0]):
            raise ValueError("ragged")
        rows.append(row)

    while True:
        if i < n and text[i] == '"':
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise ValueError("unterminated")
                ch = text[i]
                if ch == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(ch)
                i += 1
            field = "".join(buf)
        else:
            j = i
            while j < n and text[j] not in ',"\r\n':
                j += 1
            if j < n and text[j] == '"':
                raise ValueError("quote in field")
            field = text[i:j]
            i = j
        row.append(field)
        if i >= n:
            finish()
            return rows
        ch = text[i]
        if ch == ",":
            i += 1
            continue
        if ch == "\r":
            if i + 1 >= n or text[i + 1] != "\n":
                raise ValueError("lone CR")
            i += 2
        elif ch == "\n":
            i += 1
        else:
            raise ValueError("after quote")
        finish()
        row = []
        if i >= n:
            return rows
''')

task("v6_06_ipv6_canonical", r'''
Write `v6canon(text)` that parses a textual IPv6 address and returns its canonical text form (RFC 5952 style) as a `str`.
`text` must be a `str`, otherwise ValueError. Anything that is not a valid address raises ValueError.

Accepted syntax (nothing else is accepted: no whitespace anywhere, no zone suffix such as `%eth0`, no `/prefix`, no
brackets):
- The text is only ASCII. Non-ASCII characters (for example Arabic-Indic or full-width digits, which Python's `int()`
  would accept) are a ValueError.
- Groups are separated by `:`. A group is 1 to 4 hex digits `0-9a-fA-F`; leading zeros are allowed (`0001`).
- `::` may appear at most once. It stands for one or more groups of zero (at least one: `1:2:3:4:5:6:7::` is valid and
  means 8 groups, while `1:2:3:4:5:6:7:8::` and `::1:2:3:4:5:6:7:8` are errors). Three colons in a row are an error.
  A single colon at the start or at the end that is not part of `::` is an error (`:1::2`, `1::2:`, `1:2:3:4:5:6:7:`).
- Without `::` there must be exactly 8 groups.
- The last piece of the whole text may be an IPv4 dotted quad `a.b.c.d`, which counts as two groups (it is the
  last 32 bits). `a`, `b`, `c`, `d` are 1 to 3 ASCII digits, value at most 255, with no leading zero unless the
  octet is exactly `0`. An IPv4 piece anywhere else (`1.2.3.4::`, `::1.2.3.4:5`) is an error. Dotted notation counts
  toward the group total (`1:2:3:4:5:6:1.2.3.4` is valid, `1:2:3:4:5:6:7:1.2.3.4` and `1:2:3:4:5:6::1.2.3.4` are not).

Canonical output: always eight groups conceptually; each written as lowercase hex without leading zeros, joined by
`:`. The longest run of two or more consecutive zero groups is replaced by `::`; when several runs have the same
longest length, the leftmost is replaced. A single zero group is never replaced. A dotted quad is always output as hex
groups (`::ffff:192.0.2.128` gives `::ffff:c000:280`). The all-zero address is `::`.

Examples:
- `v6canon("2001:0DB8:0:0:1:0:0:1") == "2001:db8::1:0:0:1"` (two runs of length 2, the leftmost wins)
- `v6canon("1:0:2:3:4:5:6:7") == "1:0:2:3:4:5:6:7"` and `v6canon("1:0:0:2:0:0:0:3") == "1:0:0:2::3"`
- `v6canon("0:0:0:0:0:0:0:0") == "::"`, `v6canon("::1") == "::1"`, `v6canon("FE80::") == "fe80::"`
- `v6canon("::ffff:192.0.2.128") == "::ffff:c000:280"`, `v6canon("1:2:3:4:5:6:7::") == "1:2:3:4:5:6:7:0"`
- Errors: `"1::2::3"`, `":::"`, `"12345::"`, `"::01.2.3.4"`, `"::1%eth0"`, `" ::1"`, `""`.
''', r'''
import random
import ipaddress
random.seed(6006)

def canon(v):
    best_len, best_start = 0, -1
    i = 0
    while i < 8:
        if v[i] == 0:
            j = i
            while j < 8 and v[j] == 0:
                j += 1
            if j - i > best_len:
                best_len, best_start = j - i, i
            i = j
        else:
            i += 1
    hx = ["%x" % x for x in v]
    if best_len >= 2:
        return ":".join(hx[:best_start]) + "::" + ":".join(hx[best_start + best_len:])
    return ":".join(hx)

def good(t, exp):
    got = v6canon(t)
    assert type(got) is str and got == exp, (t, got, exp)

def rej(t):
    try:
        v6canon(t)
    except ValueError:
        return True
    return False

def grp(x):
    h = "%x" % x
    h = "0" * random.randint(0, 4 - len(h)) + h
    return random.choice([h.lower(), h.upper()])

def spell(v, s, l, v4):
    def tail_pieces(vals):
        if v4:
            vals_g = vals[:-2]
            a, b, c, d = vals[-2] >> 8, vals[-2] & 255, vals[-1] >> 8, vals[-1] & 255
            return [grp(x) for x in vals_g] + ["%d.%d.%d.%d" % (a, b, c, d)]
        return [grp(x) for x in vals]
    if l == 0:
        return ":".join(tail_pieces(list(v)))
    head = ":".join(grp(x) for x in v[:s])
    return head + "::" + ":".join(tail_pieces(list(v[s + l:])))

def rand_vec():
    v = [random.choice([0, 0, 0, 1, 0xffff, random.getrandbits(16), random.getrandbits(4)]) for _ in range(8)]
    if random.random() < 0.2:
        v = [0] * 8
    return v

good("2001:0DB8:0:0:1:0:0:1", "2001:db8::1:0:0:1")
good("1:0:2:3:4:5:6:7", "1:0:2:3:4:5:6:7")
good("1:0:0:2:0:0:0:3", "1:0:0:2::3")
good("0:0:0:0:0:0:0:0", "::")
good("::", "::")
good("::1", "::1")
good("FE80::", "fe80::")
good("::ffff:192.0.2.128", "::ffff:c000:280")
good("1:2:3:4:5:6:7::", "1:2:3:4:5:6:7:0")
good("::2:3:4:5:6:7:8", "0:2:3:4:5:6:7:8")
good("1:2:3:4:5:6:1.2.3.4", "1:2:3:4:5:6:102:304")
good("1:2:3:4:5::1.2.3.4", "1:2:3:4:5:0:102:304")
good("::0.0.0.0", "::")
good("::255.255.255.255", "::ffff:ffff")
good("::0.0.0.1", "::1")
good("1::", "1::")
good("0:0:1:0:0:0:0:0", "0:0:1::")
good("1:0:0:0:2:0:0:0", "1::2:0:0:0")
good("1:0:0:2:0:0:3:4", "1::2:0:0:3:4")
good("0:0:0:1:1:0:0:0", "::1:1:0:0:0")
good("1:0:0:0:0:0:0:1", "1::1")
good("0:1:0:1:0:1:0:1", "0:1:0:1:0:1:0:1")
good("1:2:3:4:5:6:0:0", "1:2:3:4:5:6::")
good("0:0:3:4:5:6:7:8", "::3:4:5:6:7:8")
good("1:0:3:4:5:6:7:0", "1:0:3:4:5:6:7:0")
good("00AB:0000:0000:000a:0:0:0:0001", "ab:0:0:a::1")
good("::0001", "::1")
good("ABCD:EF01:2345:6789:ABCD:EF01:2345:6789", "abcd:ef01:2345:6789:abcd:ef01:2345:6789")
good("1:2:3:4:5:6:7:8", "1:2:3:4:5:6:7:8")
good("::ffff:0.0.0.0", "::ffff:0:0")
good("64:ff9b::192.0.2.33", "64:ff9b::c000:221")
good("a::b", "a::b")
good("0::0", "::")
good("0:0::0:0", "::")
good("::0:0:1", "::1")
good("0::1:0:0", "::1:0:0")

for t in ("1::2::3", ":::", "12345::", "::01.2.3.4", "::1%eth0", " ::1", "::1 ", "", ":", "1:::2", "::::", "g::", "1:2:3:4:5:6:7",
          "1:2:3:4:5:6:7:8:9", "1:2:3:4:5:6:7:8::", "::1:2:3:4:5:6:7:8", ":1:2:3:4:5:6:7", "1:2:3:4:5:6:7:",
          ":1::2", "1::2:", "1.2.3.4", "::1.2.3", "::1.2.3.4.5", "::1.2.3.256", "::1.2.3.4:5", "1.2.3.4::",
          "1:2:3:4:5:6:7:1.2.3.4", "1:2:3:4:5:6::1.2.3.4", "::1/64", "[::1]", "::\u0661", "::\u0663.1.1.1",
          "::1.2.3.\u0664", "\uff41::", "::1.2.3.", "::1..3.4", "::.1.2.3", "::1.2.3.-4", "::1.2.3.+4", "::a.2.3.4",
          "::1.2.3.4a", "::0x1", "1:2:3:4:5:6:7:8\n", "\n::1", "::1\x00", "1::2::", "::1::", "1:2:3:4::5:6:7:8",
          "1:2:3:4:5:6:7::8", "1:2:3:4:5:6:7:8:", ":1:2:3:4:5:6:7:8", "-1::", "::+1", "::1_0", "::0001a", "::10000",
          "1:2:3:4:5:6:1.2.3.04", "::1.2.3.0004", "::00.1.1.1", "::1.1.1.1.", "2001:db8:::1", "1: 2::", "::1:",
          ":1::", "::ffff:1.2.3.4:", "::\u00e9", "\u0630::", "1:2:3:4:5:6:7:\u0668"):
    assert rej(t), t
for bad in (None, 5, b"::1", ["::1"], ("::1",), 1.5, True):
    assert rej(bad), bad

for _ in range(600):
    v = rand_vec()
    runs = [(s, l) for s in range(8) for l in range(1, 9 - s) if all(x == 0 for x in v[s:s + l])]
    s, l = (0, 0)
    if runs and random.random() < 0.8:
        s, l = random.choice(runs)
    v4 = (l == 0 or s + l <= 6) and random.random() < 0.3
    t = spell(v, s, l, v4)
    good(t, canon(v))

ALPHA = ["0", "1", "f", ":", ":", ":", ".", "12", "ab", "a", "255", "25", "7", "::"]
for _ in range(3000):
    t = "".join(random.choice(ALPHA) for _ in range(random.randint(1, 10)))
    try:
        exp = canon([(int(ipaddress.IPv6Address(t)) >> (16 * (7 - i))) & 0xffff for i in range(8)])
    except ValueError:
        exp = None
    try:
        got = v6canon(t)
    except ValueError:
        got = None
    assert got == exp, (t, got, exp)

for _ in range(1500):
    v = rand_vec()
    t = spell(v, 0, 0, random.random() < 0.3)
    k = random.randrange(len(t))
    ch = random.choice(["0", "1", "f", ":", ".", "g", "9", "", "::"])
    t2 = t[:k] + ch + t[k + 1:]
    try:
        exp = canon([(int(ipaddress.IPv6Address(t2)) >> (16 * (7 - i))) & 0xffff for i in range(8)])
    except ValueError:
        exp = None
    try:
        got = v6canon(t2)
    except ValueError:
        got = None
    assert got == exp, (t2, got, exp)
''', r'''
def v6canon(text):
    if type(text) is not str or not text.isascii():
        raise ValueError("input")
    hexd = "0123456789abcdefABCDEF"
    if ":::" in text or text.count("::") > 1:
        raise ValueError("colons")
    gap = "::" in text
    if gap:
        head, tail = text.split("::")
        lists = [head.split(":") if head else [], tail.split(":") if tail else []]
    else:
        lists = [text.split(":"), []]
    last = lists[1] if gap else lists[0]

    def quad(piece):
        parts = piece.split(".")
        if len(parts) != 4:
            raise ValueError("quad")
        out = []
        for p in parts:
            if not 1 <= len(p) <= 3 or any(c not in "0123456789" for c in p):
                raise ValueError("octet")
            if len(p) > 1 and p[0] == "0":
                raise ValueError("leading zero")
            if int(p) > 255:
                raise ValueError("octet range")
            out.append(int(p))
        return [out[0] * 256 + out[1], out[2] * 256 + out[3]]

    vals = [[], []]
    for li, lst in enumerate(lists):
        for k, piece in enumerate(lst):
            if "." in piece:
                if lst is not last or k != len(lst) - 1:
                    raise ValueError("quad position")
                vals[li].extend(quad(piece))
            else:
                if not 1 <= len(piece) <= 4 or any(c not in hexd for c in piece):
                    raise ValueError("group")
                vals[li].append(int(piece, 16))
    total = len(vals[0]) + len(vals[1])
    if gap:
        if total > 7:
            raise ValueError("too many groups")
    elif total != 8:
        raise ValueError("group count")
    v = vals[0] + [0] * (8 - total) + vals[1]
    best_len, best_start = 0, -1
    i = 0
    while i < 8:
        if v[i] == 0:
            j = i
            while j < 8 and v[j] == 0:
                j += 1
            if j - i > best_len:
                best_len, best_start = j - i, i
            i = j
        else:
            i += 1
    hx = ["%x" % x for x in v]
    if best_len >= 2:
        return ":".join(hx[:best_start]) + "::" + ":".join(hx[best_start + best_len:])
    return ":".join(hx)
''')

task("v6_07_udp_ipv4_inspect", r'''
Write `udp4_inspect(packet)` that validates a raw IPv4 packet carrying a UDP datagram and returns its contents.
`packet` must be `bytes` or `bytearray`, otherwise ValueError. All checks below raise ValueError when they fail.

IPv4 header (big-endian fields):
1. At least 20 bytes. Byte 0: high nibble is the version and must be 4; low nibble is IHL, header length = IHL * 4
   bytes, which must be at least 20 and at most `len(packet)`.
2. Total length (bytes 2-3) must be at least the header length and at most `len(packet)`. Bytes after total length
   (link-layer padding) are ignored entirely.
3. Header checksum: take the header (all IHL * 4 bytes, options included, checksum field included) as 16-bit
   big-endian words and add them with end-around carry (fold any carry above 16 bits back in until none is left).
   The result must be exactly 0xFFFF.
4. Flags/fragment field (bytes 6-7): the reserved bit 0x8000 must be 0, the more-fragments bit 0x2000 must be 0, and
   the 13-bit fragment offset must be 0. The don't-fragment bit 0x4000 may be anything.
5. Protocol (byte 9) must be 17 (UDP).

UDP: the segment is `packet[header_length:total_length]`; it needs at least 8 bytes. UDP length (segment bytes 4-5)
must be at least 8 and at most the segment size; the datagram is the first UDP-length bytes of the segment, and any
segment bytes after that are ignored. Checksum (datagram bytes 6-7): if it is 0, no checksum was sent and nothing is
checked. Otherwise take the pseudo-header (source address 4 bytes, destination address 4 bytes, a zero byte, the
protocol byte 17, UDP length as 16 bits), followed by the whole datagram (checksum field included); if the datagram
has odd length, append one zero byte for the summation only. Sum all 16-bit big-endian words with end-around carry as
above; the result must be exactly 0xFFFF. (A sender whose computed checksum would be 0 transmits 0xFFFF; it passes this
test and must be accepted.)

Return a dict with exactly these keys: "src" and "dst" (dotted decimal str, e.g. "192.168.0.1"), "ttl" (int, byte 8),
"sport" and "dport" (ints), "payload" (bytes: datagram bytes from 8 to UDP length; `bytes` type even for bytearray
input), and "checksummed" (bool: True only if a non-zero UDP checksum was present and verified).

Example: `bytes.fromhex("4500001e123440004011a747c0a80001c0a8000204d20035000a11166869")` gives `{"src": "192.168.0.1",
"dst": "192.168.0.2", "ttl": 64, "sport": 1234, "dport": 53, "payload": b"hi", "checksummed": True}`; the same bytes
followed by any extra bytes give the same result. `bytes.fromhex("4500001f12344000011153980a0000010a00000200070009000b0000616263")`
gives ttl 1, 10.0.0.1 to 10.0.0.2, ports 7 and 9, payload b"abc", "checksummed": False. For the first packet, changing its
last byte 0x69 to 0x6a is a ValueError (UDP checksum), and dropping its last byte is a ValueError (total length).
''', r'''
import random
import struct
random.seed(6007)

def fold(b):
    if len(b) % 2:
        b = b + b"\x00"
    s = 0
    for i in range(0, len(b), 2):
        s += (b[i] << 8) | b[i + 1]
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return s

def build(src, dst, sport, dport, payload, ttl=64, opts=b"", pad=b"", trail=b"", ver=4, ihl=None, tl=None,
          ff=0x4000, proto=17, ulen=None, uck="auto", hbad=False):
    n_ihl = 5 + len(opts) // 4
    if ihl is None:
        ihl = n_ihl
    ul = 8 + len(payload) if ulen is None else ulen
    dg = struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload
    ps = bytes(src) + bytes(dst) + bytes([0, 17]) + struct.pack(">H", 8 + len(payload))
    c = (~fold(ps + dg)) & 0xFFFF
    if c == 0:
        c = 0xFFFF
    if uck == "none":
        c = 0
    elif uck != "auto":
        c = uck
    dg = dg[:4] + struct.pack(">H", ul) + struct.pack(">H", c) + dg[8:]
    seg = dg + trail
    total = n_ihl * 4 + len(seg) if tl is None else tl
    h = struct.pack(">BBHHHBBH", (ver << 4) | ihl, 0, total, 0x1234, ff, ttl, proto, 0) + bytes(src) + bytes(dst) + opts
    hc = (~fold(h)) & 0xFFFF
    if hbad:
        hc ^= 0x0100
    h = h[:10] + struct.pack(">H", hc) + h[12:]
    return h + seg + pad

def rb(n):
    return bytes(random.getrandbits(8) for _ in range(n))

def good(p, exp):
    got = udp4_inspect(p)
    assert type(got) is dict and got == exp, (bytes(p).hex(), got, exp)
    assert type(got["payload"]) is bytes and type(got["ttl"]) is int and type(got["sport"]) is int
    assert type(got["dport"]) is int and type(got["checksummed"]) is bool
    assert type(got["src"]) is str and type(got["dst"]) is str

def bad(p):
    try:
        r = udp4_inspect(p)
    except ValueError:
        return
    raise AssertionError((bytes(p).hex() if isinstance(p, (bytes, bytearray)) else p, r))

def ip(a):
    return ".".join(str(x) for x in a)

A = bytes.fromhex("4500001e123440004011a747c0a80001c0a8000204d20035000a11166869")
EA = {"src": "192.168.0.1", "dst": "192.168.0.2", "ttl": 64, "sport": 1234, "dport": 53, "payload": b"hi",
      "checksummed": True}
good(A, EA)
good(bytearray(A), EA)
good(A + b"\x00\x00\x00", EA)
good(A + rb(30), EA)
bad(A[:-1])
bad(A[:-1] + b"\x6a")
bad(A[:-2] + b"\x68\x6a")
B = bytes.fromhex("4500001f12344000011153980a0000010a00000200070009000b0000616263")
good(B, {"src": "10.0.0.1", "dst": "10.0.0.2", "ttl": 1, "sport": 7, "dport": 9, "payload": b"abc",
         "checksummed": False})
assert build((192, 168, 0, 1), (192, 168, 0, 2), 1234, 53, b"hi") == A
assert build((10, 0, 0, 1), (10, 0, 0, 2), 7, 9, b"abc", ttl=1, uck="none") == B

S1, D1 = (1, 2, 3, 4), (250, 251, 252, 253)
good(build(S1, D1, 0, 65535, b""), {"src": "1.2.3.4", "dst": "250.251.252.253", "ttl": 64, "sport": 0,
                                    "dport": 65535, "payload": b"", "checksummed": True})
good(build(S1, D1, 5, 6, b"x", ff=0x0000), {"src": "1.2.3.4", "dst": "250.251.252.253", "ttl": 64, "sport": 5,
                                            "dport": 6, "payload": b"x", "checksummed": True})
good(build(S1, D1, 5, 6, b"x", ttl=0, ff=0x4000), {"src": "1.2.3.4", "dst": "250.251.252.253", "ttl": 0, "sport": 5,
                                                   "dport": 6, "payload": b"x", "checksummed": True})
good(build(S1, D1, 5, 6, b"xyz", ttl=255, opts=bytes(range(1, 41))), {"src": "1.2.3.4", "dst": "250.251.252.253",
     "ttl": 255, "sport": 5, "dport": 6, "payload": b"xyz", "checksummed": True})

# forced transmitted checksum 0xFFFF
for k in range(6):
    src, dst = tuple(rb(4)), tuple(rb(4))
    pl = rb(random.choice([2, 4, 6, 20]))
    base = pl[:-2] + b"\x00\x00"
    dg = struct.pack(">HHHH", 1000 + k, 2000, 8 + len(pl), 0) + base
    ps = bytes(src) + bytes(dst) + bytes([0, 17]) + struct.pack(">H", 8 + len(pl))
    t = fold(ps + dg)
    w = 0xFFFF - t
    pl2 = base[:-2] + struct.pack(">H", w)
    pk = build(src, dst, 1000 + k, 2000, pl2)
    assert pk[26:28] == b"\xff\xff", pk.hex()
    good(pk, {"src": ip(src), "dst": ip(dst), "ttl": 64, "sport": 1000 + k, "dport": 2000, "payload": pl2,
              "checksummed": True})
    z = build(src, dst, 1000 + k, 2000, pl2, uck="none")
    good(z, {"src": ip(src), "dst": ip(dst), "ttl": 64, "sport": 1000 + k, "dport": 2000, "payload": pl2,
             "checksummed": False})

# checksum field 0 accepted even though the payload is wrong for it; a wrong nonzero field is rejected
P = build(S1, D1, 10, 20, b"hello")
bad(P[:-1] + bytes([P[-1] ^ 1]))
Z = bytearray(P)
Z[26:28] = b"\x00\x00"
Z[-1] ^= 1
good(bytes(Z), {"src": "1.2.3.4", "dst": "250.251.252.253", "ttl": 64, "sport": 10, "dport": 20,
                "payload": bytes(Z[28:]), "checksummed": False})
for bitpos in range(28 * 8, len(P) * 8):
    Q = bytearray(P)
    Q[bitpos // 8] ^= 1 << (bitpos % 8)
    bad(bytes(Q))
for i in range(1, 20):
    for bit in range(8):
        Q = bytearray(P)
        Q[i] ^= 1 << bit
        bad(bytes(Q))
for i in range(20, 24):
    for bit in range(8):
        Q = bytearray(P)
        Q[i] ^= 1 << bit
        bad(bytes(Q))

# header rule isolation (checksums recomputed)
bad(build(S1, D1, 1, 2, b"ab", ver=6))
bad(build(S1, D1, 1, 2, b"ab", ver=0))
bad(build(S1, D1, 1, 2, b"ab", ihl=4))
bad(build(S1, D1, 1, 2, b"ab", ihl=0))
bad(build(S1, D1, 1, 2, b"ab", ihl=15))
bad(build(S1, D1, 1, 2, b"ab", tl=19))
bad(build(S1, D1, 1, 2, b"ab", tl=20 + 7))
bad(build(S1, D1, 1, 2, b"ab", tl=20 + 10 + 1))
bad(build(S1, D1, 1, 2, b"ab", tl=0))
bad(build(S1, D1, 1, 2, b"ab", tl=65535))
bad(build(S1, D1, 1, 2, b"ab", ff=0x2000))
bad(build(S1, D1, 1, 2, b"ab", ff=0x6000))
bad(build(S1, D1, 1, 2, b"ab", ff=0x0001))
bad(build(S1, D1, 1, 2, b"ab", ff=0x4001))
bad(build(S1, D1, 1, 2, b"ab", ff=0x1FFF))
bad(build(S1, D1, 1, 2, b"ab", ff=0x8000))
bad(build(S1, D1, 1, 2, b"ab", ff=0xC000))
bad(build(S1, D1, 1, 2, b"ab", proto=6))
bad(build(S1, D1, 1, 2, b"ab", proto=1))
bad(build(S1, D1, 1, 2, b"ab", proto=0))
bad(build(S1, D1, 1, 2, b"ab", hbad=True))
bad(build(S1, D1, 1, 2, b"ab", tl=20 + 7, uck="none"))
bad(build(S1, D1, 1, 2, b"ab", ulen=7, uck="none"))
bad(build(S1, D1, 1, 2, b"ab", ulen=0, uck="none"))
bad(build(S1, D1, 1, 2, b"ab", ulen=11, uck="none"))
bad(build(S1, D1, 1, 2, b"ab", ulen=11))
bad(build(S1, D1, 1, 2, b"ab", ulen=65535, uck="none"))
bad(build(S1, D1, 1, 2, b"ab", uck=0x1234))
bad(build(S1, D1, 1, 2, b"ab", uck=1))
bad(b"")
bad(b"\x45" * 19)
bad(bytes(20))
bad(bytes(60))
bad(P[:19])
bad(P[:20])
bad(P[:27])
for pk in (P, A, B):
    bad(pk[:-1])
    bad(pk[:20])
for x in (None, "E", [69], 5, memoryview(A), (69, 0), {}):
    bad(x)

# ihl > 5 with a packet shorter than the header
bad(build(S1, D1, 1, 2, b"", opts=bytes(8))[:28])

for _ in range(300):
    src, dst = tuple(rb(4)), tuple(rb(4))
    opts = rb(4 * random.choice([0, 0, 1, 2, 5, 10]))
    pl = rb(random.choice([0, 1, 2, 3, 4, 5, 8, 17, 33, 100]))
    trail = rb(random.choice([0, 0, 1, 2, 3]))
    pad = rb(random.choice([0, 0, 1, 6, 20]))
    sp, dp = random.getrandbits(16), random.getrandbits(16)
    ttl = random.getrandbits(8)
    ff = random.choice([0x4000, 0x0000])
    mode = random.choice(["auto", "auto", "none"])
    pk = build(src, dst, sp, dp, pl, ttl=ttl, opts=opts, pad=pad, trail=trail, ff=ff, uck=mode)
    exp = {"src": ip(src), "dst": ip(dst), "ttl": ttl, "sport": sp, "dport": dp, "payload": pl,
           "checksummed": mode == "auto"}
    good(pk, exp)
    if random.random() < 0.5:
        good(bytearray(pk), exp)
    hl = 20 + len(opts)
    for _ in range(3):
        Q = bytearray(pk)
        i = random.choice([j for j in range(1, hl) if j not in (10, 11)])
        Q[i] ^= 1 << random.randrange(8)
        bad(bytes(Q))
    if mode == "auto":
        i = random.choice([j for j in range(hl, hl + 8 + len(pl)) if j not in (hl + 4, hl + 5)])
        Q = bytearray(pk)
        Q[i] ^= 1 << random.randrange(8)
        bad(bytes(Q))
    bad(pk[:hl + 7] if not pad and not trail else pk[:hl - 1])
''', r'''
def udp4_inspect(packet):
    if not isinstance(packet, (bytes, bytearray)):
        raise ValueError("type")
    p = bytes(packet)
    n = len(p)

    def fold(b):
        if len(b) % 2:
            b += b"\x00"
        s = sum((b[i] << 8) | b[i + 1] for i in range(0, len(b), 2))
        while s >> 16:
            s = (s & 0xFFFF) + (s >> 16)
        return s

    if n < 20 or p[0] >> 4 != 4:
        raise ValueError("version")
    hl = (p[0] & 15) * 4
    if hl < 20 or hl > n:
        raise ValueError("ihl")
    total = (p[2] << 8) | p[3]
    if total < hl or total > n:
        raise ValueError("total length")
    if fold(p[:hl]) != 0xFFFF:
        raise ValueError("header checksum")
    ff = (p[6] << 8) | p[7]
    if ff & 0x8000 or ff & 0x2000 or ff & 0x1FFF:
        raise ValueError("fragment")
    if p[9] != 17:
        raise ValueError("protocol")
    seg = p[hl:total]
    if len(seg) < 8:
        raise ValueError("short segment")
    ulen = (seg[4] << 8) | seg[5]
    if ulen < 8 or ulen > len(seg):
        raise ValueError("udp length")
    dg = seg[:ulen]
    checksummed = False
    if dg[6] or dg[7]:
        pseudo = p[12:20] + bytes([0, 17, ulen >> 8, ulen & 255])
        if fold(pseudo + dg) != 0xFFFF:
            raise ValueError("udp checksum")
        checksummed = True
    return {
        "src": ".".join(str(x) for x in p[12:16]),
        "dst": ".".join(str(x) for x in p[16:20]),
        "ttl": p[8],
        "sport": (dg[0] << 8) | dg[1],
        "dport": (dg[2] << 8) | dg[3],
        "payload": dg[8:],
        "checksummed": checksummed,
    }
''')

task("v6_08_url_normalize", r'''
Write `urlnorm3986(url)` that normalizes an absolute URL of the form `scheme://authority path ?query #fragment` and
returns a `str`. `url` must be a `str` made only of printable ASCII characters 0x21..0x7E (no space, no control or
non-ASCII character), otherwise ValueError. Every violation below raises ValueError.

Sets: unreserved = letters, digits and `-._~`; sub-delims = `!$&'()*+,;=`. A percent triplet is `%` plus exactly two hex
digits (either case); any other `%` is an error. A character not allowed for its component is an error.

Split: scheme is the text before the first `:`; it must be a letter followed by letters, digits, `+`, `-`, `.`, and
must be followed by `://`. Output scheme is lowercase. The authority runs to the first `/`, `?` or `#`; the path to the
first `?` or `#`; the query (after the first `?`) to the first `#`; the fragment is the rest after the first `#`. A
query or fragment that is present but empty keeps its `?` or `#`.

Percent normalization (all components): a triplet that decodes to an unreserved character is replaced by that character
(`%7e` becomes `~`, `%41` becomes `A`); any other triplet stays encoded with uppercase hex digits (`%2f` becomes `%2F`,
`%c3%a9` becomes `%C3%A9`). Other characters are kept as written.

Components:
- Authority is `[userinfo@]host[:port]`. At most one `@`. Userinfo allows unreserved, sub-delims, triplets and `:`; an
  empty userinfo (`http://@h/`) is dropped together with its `@`. Case is kept.
- Host: non-empty. Either `[...]` holding only hex digits, `:` and `.` (non-empty), lowercased, kept with its brackets;
  or a name of unreserved, sub-delims and triplets, normalized as above and then lowercased, where the hex digits of a
  remaining triplet stay uppercase (`%41` decodes to `A`, then becomes `a`; `%C3` stays `%C3`). After `]` only `:port`
  or nothing may follow.
- Port: after the host, `:` then ASCII digits only (an empty port is dropped with its colon). Value above 65535 is an
  error. Leading zeros are removed (`:0080` is 80, `:00` is 0). A port equal to the scheme's default is dropped:
  http 80, https 443, ftp 21, ws 80, wss 443.
- Path: allows unreserved, sub-delims, triplets, `:`, `@`, `/`. After percent normalization remove dot segments: split the
  path on `/`; a segment `.` is dropped, `..` drops the segment before it (nothing at the root), and a `.` or `..`
  as the last segment leaves the path ending in `/`. Empty segments are real segments (`/a//../b` is `/a/b`). An empty
  path becomes `/`.
- Query and fragment allow unreserved, sub-delims, triplets and the characters `: @ / ?`; nothing else.

Examples:
- `urlnorm3986("HTTP://User@EXAMPLE.com:80/a/./b/../c/%7euser/%e2%82%AC?q=%3d#F%41")` is
  `"http://User@example.com/a/c/~user/%E2%82%AC?q=%3D#FA"`
- `urlnorm3986("http://a/b/c/./../../g")` is `"http://a/g"`; `urlnorm3986("http://a/../../x/.")` is `"http://a/x/"`
- `urlnorm3986("http://%41%42.COM?x")` is `"http://ab.com/?x"`; `urlnorm3986("https://h:00443#")` is `"https://h/#"`
- `urlnorm3986("x-y://@[FE80::1]:8080/p")` is `"x-y://[fe80::1]:8080/p"`
- Errors: `"http:/x"`, `"http:///p"`, `"http://h:65536/"`, `"http://a/%2"`, `"http://u@v@h/"`.
''', r'''
import random
import string
random.seed(6008)

UNR = string.ascii_letters + string.digits + "-._~"
SUBD = "!$&'()*+,;="
DEFP = {"http": 80, "https": 443, "ftp": 21, "ws": 80, "wss": 443}

def rds(path):
    inp, out = path, ""
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
            out = out[:out.rfind("/")] if "/" in out else ""
        elif inp == "/..":
            inp = "/"
            out = out[:out.rfind("/")] if "/" in out else ""
        elif inp in (".", ".."):
            inp = ""
        else:
            k = inp.find("/", 1)
            if k < 0:
                k = len(inp)
            out += inp[:k]
            inp = inp[k:]
    return out

def good(u, exp):
    got = urlnorm3986(u)
    assert type(got) is str and got == exp, (u, got, exp)

def rej(u):
    try:
        urlnorm3986(u)
    except ValueError:
        return True
    return False

good("HTTP://User@EXAMPLE.com:80/a/./b/../c/%7euser/%e2%82%AC?q=%3d#F%41",
     "http://User@example.com/a/c/~user/%E2%82%AC?q=%3D#FA")
good("http://a/b/c/./../../g", "http://a/g")
good("http://a/../../x/.", "http://a/x/")
good("http://%41%42.COM?x", "http://ab.com/?x")
good("https://h:00443#", "https://h/#")
good("x-y://@[FE80::1]:8080/p", "x-y://[fe80::1]:8080/p")
good("http://a.com", "http://a.com/")
good("http://a.com/", "http://a.com/")
good("http://h:/x", "http://h/x")
good("http://h:0/x", "http://h:0/x")
good("http://h:00/x", "http://h:0/x")
good("http://h:80/x", "http://h/x")
good("http://h:8080/x", "http://h:8080/x")
good("https://h:80/", "https://h:80/")
good("http://h:443/", "http://h:443/")
good("ftp://h:21", "ftp://h/")
good("ws://h:80", "ws://h/")
good("wss://h:443", "wss://h/")
good("wss://h:80", "wss://h:80/")
good("gopher://h:70", "gopher://h:70/")
good("gopher://h:80", "gopher://h:80/")
good("http://h:65535", "http://h:65535/")
good("http://h:000065535", "http://h:65535/")
good("http://EX%C3%A9.com", "http://ex%C3%A9.com/")
good("http://EX%c3%a9.com", "http://ex%C3%A9.com/")
good("http://a%2Eb.com", "http://a.b.com/")
good("http://%7E%5F.x", "http://~_.x/")
good("http://U%7eS:p%41ss@h/", "http://U~S:pAss@h/")
good("http://@h/", "http://h/")
good("http://:@h/", "http://:@h/")
good("http://u@h/", "http://u@h/")
good("http://[::1]", "http://[::1]/")
good("http://[::1]:", "http://[::1]/")
good("http://[::1]:80/", "http://[::1]/")
good("http://[2001:DB8::AB]:81/", "http://[2001:db8::ab]:81/")
good("http://[::ffff:1.2.3.4]/", "http://[::ffff:1.2.3.4]/")
good("HtTpS://H/", "https://h/")
good("a1+b-c.d://h", "a1+b-c.d://h/")
good("http://h?", "http://h/?")
good("http://h#", "http://h/#")
good("http://h?#", "http://h/?#")
good("http://h/?a?b/c:d@e#x?y/z:w@v", "http://h/?a?b/c:d@e#x?y/z:w@v")
good("http://h/p?q=%7e%2f%2F%41#f%7E", "http://h/p?q=~%2F%2FA#f~")
good("http://h/%2e%2E/a", "http://h/a")
good("http://h/a/%2e/b/%2E%2e/c", "http://h/a/c")
good("http://h/a/b/..", "http://h/a/")
good("http://h/a/b/.", "http://h/a/b/")
good("http://h/..", "http://h/")
good("http://h/.", "http://h/")
good("http://h/./", "http://h/")
good("http://h/a/../..", "http://h/")
good("http://h/a//../b", "http://h/a/b")
good("http://h//a/../b", "http://h//b")
good("http://h//", "http://h//")
good("http://h///", "http://h///")
good("http://h/a/b/../../../c", "http://h/c")
good("http://h/..a/.../b./.c", "http://h/..a/.../b./.c")
good("http://h/a/b/c/../../..", "http://h/")
good("http://h/a/b/c/../../../", "http://h/")
good("http://h/a%2Fb/../c", "http://h/c")
good("http://h/a%2fb", "http://h/a%2Fb")
good("http://h/%25", "http://h/%25")
good("http://h/%25%32%35", "http://h/%2525")
good("http://h/:@!$&'()*+,;=", "http://h/:@!$&'()*+,;=")
good("http://h/~user/a_b-c.d", "http://h/~user/a_b-c.d")
good("http://h/%00%1F%7F%80%FF", "http://h/%00%1F%7F%80%FF")
good("http://h/%61%7A%41%5A%30%39%2D%2E%5F%7E", "http://h/azAZ09-._~")
good("http://!$&'()*+,;=.x/", "http://!$&'()*+,;=.x/")
good("http://h/a?b#c", "http://h/a?b#c")
good("http://h/p#a/b?c", "http://h/p#a/b?c")
good("http://h/p?a=b&c=d#e", "http://h/p?a=b&c=d#e")

for u in ("", "http", "http:/x", "http:x", "://x", "1http://x", "ht tp://x", "ht_tp://x", "+h://x", "http//x", "h:ttp://x",
          "http://", "http:///p", "http://:80/", "http://@/x", "http://a b/", "http://a/b c", "http://a/\u00e9",
          "http://a/%zz", "http://a/%2", "http://a/%", "http://a/%2g", "http://a/<", "http://a/>", "http://a/\\",
          "http://a/[", "http://a/]", "http://a/{", "http://a/}", "http://a/|", "http://a/^", "http://a/`", 'http://a/"',
          "http://a?q[", "http://a?q]", "http://a?q<", "http://a/p#f#g", "http://a/p#f<", "http://a/p#f[",
          "http://u@v@h/", "http://@@h/", "http://h:80a/", "http://h:65536/", "http://h:-1/", "http://h:+1/",
          "http://h:1:2/", "http://h:0x50/", "http://h::80/", "http://[::1/", "http://[]/", "http://[::1]x/",
          "http://[::g]/", "http://[::1]:x/", "http://[::1]:99999/", "http://[::1%25eth0]/", "http://[ ::1]/",
          "http://a[b]/", "http://a]/", "http://a[/", "http://h%/", "http://h%4/", "http://h%4g/", "http://u:p@/",
          "http://u%/@h/", "http://u[@h/", "http://u@h:/x/y z", "http:// h/", "http://h/ ",
          " http://h/", "http://h/\n", "http://h/\t", "http://h/\x00", "http://h/\x7f", "http://\uff48/", "http://h:\u0668\u0660/",
          "http://h:\u0661/", "http://h/\U0001f600", "http://h/?#%", "http://h/?%G0", "http://h/#%0", "http://u\"@h/",
          "http://h/a%", "http://h/a%a", "http://[::1]/%q", "http://us^er@h/", "http://h<h/", "http://h|h/", "http://h/a?b?c#d%",
          "http://h:80:80/", "http://[::1]:80:80/", "http://[]:80/", "http://[:]x", "ht!tp://h/", "ht@tp://h/",
          "http://h\\p"):
    assert rej(u), u
for bad in (None, 5, b"http://h/", ["http://h/"], 1.5, True):
    assert rej(bad), bad

def atoms_for(extra, kind):
    """Return (canonical, noisy) for one random atom."""
    r = random.random()
    if r < 0.6:
        c = random.choice(UNR if kind != "host" else string.ascii_lowercase + string.digits + "-._~")
        if kind == "host":
            opts = [c, c.upper(), "%%%02X" % ord(c), "%%%02x" % ord(c), "%%%02X" % ord(c.upper()), "%%%02x" % ord(c.upper())]
            return c, random.choice(opts)
        return c, random.choice([c, c, c, "%%%02X" % ord(c), "%%%02x" % ord(c)])
    if r < 0.8:
        c = random.choice(SUBD + extra)
        return c, c
    b = random.choice([0, 1, 31, 32, 34, 35, 37, 47, 63, 64, 91, 127, 128, 195, 169, 226, 255, 0x2F, 0x3F, 0x23, 0x40, 0x25])
    return "%%%02X" % b, random.choice(["%%%02X" % b, "%%%02x" % b])

def comp(extra, kind, lo, hi):
    cs, ns = "", ""
    for _ in range(random.randint(lo, hi)):
        c, n = atoms_for(extra, kind)
        cs += c
        ns += n
    return cs, ns

def seg():
    while True:
        c, n = comp(":@", "path", 0, 4)
        if c not in (".", ".."):
            return c, n

def case_scheme(s):
    return "".join(random.choice([ch, ch.upper()]) for ch in s)

def rand_url():
    scheme = random.choice(["http", "https", "ftp", "ws", "wss", "git+ssh", "x-y.z", "a1", "gopher"])
    ns = case_scheme(scheme)
    cs_auth, ns_auth = "", ""
    if random.random() < 0.35:
        cu, nu = comp(":", "user", 0, 5)
        if cu:
            cs_auth += cu + "@"
        ns_auth += nu + "@"
    if random.random() < 0.1:
        lit = random.choice(["::1", "fe80::1", "2001:db8::ab", "::ffff:1.2.3.4", "1:2:3:4:5:6:7:8"])
        ch = "[" + lit + "]"
        nh = "[" + case_scheme(lit) + "]"
    else:
        while True:
            ch, nh = comp("", "host", 1, 8)
            if ch:
                break
    cs_auth += ch
    ns_auth += nh
    pk = random.random()
    if pk < 0.35:
        pass
    elif pk < 0.5:
        ns_auth += ":" if random.random() < 0.5 else ":" + "0" * random.randint(0, 3) + str(DEFP.get(scheme, 80)) if scheme in DEFP else ":"
    else:
        port = random.choice([0, 1, 79, 81, 442, 444, 8080, 65535, random.randint(0, 65535)])
        if DEFP.get(scheme) == port:
            port = 1234
        cs_auth += ":%d" % port
        ns_auth += ":" + "0" * random.randint(0, 3) + str(port)
    segs = [seg() for _ in range(random.choice([0, 0, 1, 2, 3, 5]))]
    cpath = "".join("/" + c for c, n in segs)
    npath = ""
    for c, n in segs:
        npath += "/"
        for _ in range(random.choice([0, 0, 0, 1, 2])):
            q = random.choice(["", "", seg()[1]])
            npath += random.choice(["./", "%2E/", "%2e/", q + "/../", q + "/%2e%2E/", q + "/.%2e/".replace(".%2e", "%2E.")])
        npath += n
    if random.random() < 0.3:
        tail = random.choice(["/.", "/%2e", "/" + seg()[1] + "/..", "/" + seg()[1] + "/%2E%2E"])
        npath += tail
        cpath += "/"
    if cpath == "":
        cpath = "/"
        npath = random.choice(["", "", "/", "/.", "/" + seg()[1] + "/..", "/./"]) if True else ""
    cexp = cpath
    out_c = scheme + "://" + cs_auth + cexp
    out_n = ns + "://" + ns_auth + npath
    if random.random() < 0.4:
        cq, nq = comp(":@/?", "query", 0, 6)
        out_c += "?" + cq
        out_n += "?" + nq
    if random.random() < 0.4:
        cf, nf = comp(":@/?", "frag", 0, 6)
        out_c += "#" + cf
        out_n += "#" + nf
    return out_n, out_c

for _ in range(1500):
    n, c = rand_url()
    assert all(0x21 <= ord(ch) <= 0x7e for ch in n), n
    good(n, c)
    good(c, c)

# differential check of the dot-segment step against the RFC 5.2.4 text algorithm
for _ in range(1500):
    path = "/" + "/".join(random.choice(["a", "b", ".", "..", "", "c.d", "..."]) for _ in range(random.randint(0, 8)))
    exp = rds(path)
    if exp == "":
        exp = "/"
    good("http://h" + path, "http://h" + exp)

N = 3000
good("http://h" + "/a" * N + "/.." * N, "http://h/")
good("http://h" + "/a" * N + "/.." * (N - 1), "http://h/a/")
good("http://h" + "/a/." * N, "http://h" + "/a" * N + "/")
good("http://h" + "/.." * N + "/z", "http://h/z")
good("http://h" + "/%61" * 5000, "http://h" + "/a" * 5000)
good("http://h/" + "%2f" * 5000, "http://h/" + "%2F" * 5000)
good("http://h/" + "/" * 5000, "http://h/" + "/" * 5000)
''', r'''
def urlnorm3986(url):
    if type(url) is not str or not url or any(not 0x21 <= ord(c) <= 0x7E for c in url):
        raise ValueError("chars")
    unres = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")
    subd = set("!$&'()*+,;=")
    hexd = set("0123456789abcdefABCDEF")
    defaults = {"http": 80, "https": 443, "ftp": 21, "ws": 80, "wss": 443}

    def pct(s, extra, lower=False):
        out = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == "%":
                h = s[i + 1:i + 3]
                if len(h) != 2 or any(x not in hexd for x in h):
                    raise ValueError("percent")
                ch = chr(int(h, 16))
                if ch in unres:
                    out.append(ch.lower() if lower else ch)
                else:
                    out.append("%" + h.upper())
                i += 3
                continue
            if c not in unres and c not in subd and c not in extra:
                raise ValueError("char")
            out.append(c.lower() if lower else c)
            i += 1
        return "".join(out)

    i = url.find(":")
    if i <= 0 or url[i:i + 3] != "://":
        raise ValueError("scheme")
    scheme = url[:i]
    if not scheme[0].isalpha() or not scheme.isascii():
        raise ValueError("scheme")
    if any(not (c.isalnum() or c in "+-.") for c in scheme):
        raise ValueError("scheme")
    scheme = scheme.lower()
    rest = url[i + 3:]
    k = len(rest)
    for ch in "/?#":
        j = rest.find(ch)
        if j >= 0:
            k = min(k, j)
    auth, rem = rest[:k], rest[k:]
    frag = None
    if "#" in rem:
        rem, frag = rem.split("#", 1)
    query = None
    if "?" in rem:
        rem, query = rem.split("?", 1)
    path = rem

    if auth.count("@") > 1:
        raise ValueError("userinfo")
    userinfo = ""
    hostport = auth
    if "@" in auth:
        ui, hostport = auth.split("@")
        userinfo = pct(ui, ":")
    portstr = None
    if hostport.startswith("["):
        j = hostport.find("]")
        if j < 0:
            raise ValueError("bracket")
        lit = hostport[1:j]
        if not lit or any(c not in hexd and c not in ":." for c in lit):
            raise ValueError("literal")
        host = "[" + lit.lower() + "]"
        after = hostport[j + 1:]
        if after:
            if after[0] != ":":
                raise ValueError("after literal")
            portstr = after[1:]
    else:
        if ":" in hostport:
            hs, portstr = hostport.split(":", 1)
        else:
            hs = hostport
        if not hs:
            raise ValueError("host")
        host = pct(hs, "", True)
    port = ""
    if portstr:
        if any(c not in "0123456789" for c in portstr):
            raise ValueError("port")
        v = int(portstr)
        if v > 65535:
            raise ValueError("port range")
        if defaults.get(scheme) != v:
            port = ":" + str(v)

    stack = []
    if path:
        norm = pct(path, ":@/")
        segs = norm[1:].split("/")
        for idx, s in enumerate(segs):
            last = idx == len(segs) - 1
            if s == ".":
                if last:
                    stack.append("")
            elif s == "..":
                if stack:
                    stack.pop()
                if last:
                    stack.append("")
            else:
                stack.append(s)
        path = "/" + "/".join(stack)
    else:
        path = "/"

    out = scheme + "://"
    if userinfo:
        out += userinfo + "@"
    out += host + port + path
    if query is not None:
        out += "?" + pct(query, ":@/?")
    if frag is not None:
        out += "#" + pct(frag, ":@/?")
    return out
''')

task("v6_09_sqfree_progression", r'''
Write `sqfree_in_progression(a, m, n)` that returns how many positive squarefree integers x satisfy
x <= n and x is congruent to a modulo m. A positive integer is squarefree when no square of a prime
divides it; 1 is squarefree.
Inputs: a, m, n must be ints (bool is not an int) with 1 <= m <= 10**6, 1 <= n <= 10**10 and
abs(a) <= 10**18, otherwise raise ValueError. The result is an int.
Details that matter:
- The congruence is the mathematical one: a may be negative or larger than m, so a = -1 and a = m - 1
  mean the same thing.
- x ranges over positive integers only, so 0 is never counted even when a is a multiple of m.
- m is arbitrary: it need not be squarefree and it need not be coprime to anything. For example no
  squarefree number is divisible by 4 (so the count is 0 for a = 0, m = 4) and no squarefree number
  is divisible by 9, but numbers congruent to 3 modulo 9 can be squarefree.
- n can be 10**10, so testing the numbers one by one is far too slow.
Examples:
- sqfree_in_progression(0, 1, 10) == 7   (1, 2, 3, 5, 6, 7, 10)
- sqfree_in_progression(-1, 5, 50) == 5   (14, 19, 29, 34, 39)
- sqfree_in_progression(0, 4, 100) == 0
- sqfree_in_progression(3, 9, 100) == 7   (3, 21, 30, 39, 57, 66, 93; 12, 48, 75, 84 are not squarefree)
- sqfree_in_progression(0, 6, 100) == 5   (6, 30, 42, 66, 78)
''', r'''
import random
from math import gcd

LIM = 4000
SF = [True] * (LIM + 1)
for p in range(2, 64):
    for q in range(p * p, LIM + 1, p * p):
        SF[q] = False

def brute(a, m, n):
    return sum(1 for x in range(1, n + 1) if SF[x] and (x - a) % m == 0)

def rej(*args):
    try:
        sqfree_in_progression(*args)
    except ValueError:
        return True
    return False

def chk(a, m, n):
    got = sqfree_in_progression(a, m, n)
    assert type(got) is int and got == brute(a, m, n), (a, m, n, got, brute(a, m, n))

for a, m, n, e in [(0, 1, 10, 7), (-1, 5, 50, 5), (0, 4, 100, 0), (3, 9, 100, 7), (0, 6, 100, 5),
                   (0, 1, 1, 1), (1, 1, 1, 1), (0, 2, 1, 0), (1, 2, 1, 1), (5, 1, 1, 1), (0, 10**6, 10**6, 0),
                   (1, 10**6, 10, 1), (0, 1, 100, 61), (0, 1, 1000, 608)]:
    got = sqfree_in_progression(a, m, n)
    assert type(got) is int and got == e, (a, m, n, got, e)

assert sqfree_in_progression(10**18, 7, 500) == sqfree_in_progression(10**18 % 7, 7, 500) == brute(10**18 % 7, 7, 500)
assert sqfree_in_progression(-10**18, 1000, 3000) == brute(-10**18 % 1000, 1000, 3000)
for m in (4, 8, 9, 16, 25, 27, 36, 49, 100, 121, 169, 225, 3 * 49):
    assert sqfree_in_progression(0, m, 3000) == brute(0, m, 3000) == 0
for m in (2, 3, 4, 6, 8, 9, 10, 12, 18, 30, 36, 49, 60, 210):
    for a in range(-3, m + 3):
        chk(a, m, 600)
chk(2, 4, 4000)
chk(0, 3, 3999)
chk(5, 8, 4000)

random.seed(6009)
for _ in range(220):
    m = random.choice([random.randint(1, 30), random.randint(1, 300), random.choice([4, 9, 12, 18, 25, 36, 50, 72, 100, 180, 360, 2520])])
    a = random.choice([random.randint(-2 * m, 3 * m), random.randint(-10**18, 10**18), random.randint(0, m - 1)])
    n = random.choice([random.randint(1, 80), random.randint(1, LIM)])
    chk(a, m, n)

def f(a, m, n):
    return sqfree_in_progression(a, m, n)

# large n: identities that hold for the true count, plus a density sanity check
n = 10**9 + 7
tot = f(0, 1, n)
assert f(0, 2, n) + f(1, 2, n) == tot
assert f(0, 2, n) == f(1, 2, n // 2)
assert f(0, 4, n) == 0
assert f(3, 9, n) == f(1, 3, n // 3)
assert abs(tot - 0.6079271018540267 * n) < 3 * n ** 0.5, tot
big = f(7, 10**6, 10**10)
assert type(big) is int and 0 < big < 10**10 // 10**6 * 2

for bad in (0, -3, 10**6 + 1, 2.0, "5", None, True, [3]):
    assert rej(1, bad, 10), bad
for bad in (0, -1, 10**10 + 1, 5.0, "7", None, False, [9]):
    assert rej(1, 3, bad), bad
for bad in (10**18 + 1, -10**18 - 1, 1.0, "1", None, True, [1]):
    assert rej(bad, 3, 10), bad
assert rej(0, 0, 0) and rej(True, True, True)
assert sqfree_in_progression(10**18, 10**6, 10) == 0
assert sqfree_in_progression(-10**18, 3, 10) == brute(-10**18 % 3, 3, 10)
''', r'''
from math import gcd, isqrt

def sqfree_in_progression(a, m, n):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not (isint(a) and isint(m) and isint(n)) or not 1 <= m <= 10**6 or not 1 <= n <= 10**10 or abs(a) > 10**18:
        raise ValueError("range")
    a %= m
    r = isqrt(n)
    mu = [1] * (r + 1)
    sieve = bytearray([1]) * (r + 1)
    for p in range(2, r + 1):
        if sieve[p]:
            for q in range(2 * p, r + 1, p):
                sieve[q] = 0
            for q in range(p, r + 1, p):
                mu[q] = -mu[q]
            pp = p * p
            for q in range(pp, r + 1, pp):
                mu[q] = 0
    total = 0
    for d in range(1, r + 1):
        s = mu[d]
        if not s:
            continue
        D = d * d
        g = gcd(D, m)
        if a % g:
            continue
        M = m // g
        t0 = (a // g) * pow(D // g, -1, M) % M if M > 1 else 0
        top = n // D
        if t0 == 0:
            c = top // M
        elif t0 > top:
            c = 0
        else:
            c = (top - t0) // M + 1
        total += s * c
    return total
''')

task("v6_10_proper_bracelets", r'''
Write `proper_bracelet_count(n, k)` that returns the number of distinct bracelets made of n beads,
each bead painted one of k labelled colours, in which no two neighbouring beads have the same colour.
The beads sit on a circle: bead i neighbours beads i-1 and i+1, and bead n neighbours bead 1.
Two paintings are the same bracelet when one can be turned into the other by rotating the circle,
by flipping the circle over (a reflection), or by both. The colours are labelled, so permuting
colour names gives a different bracelet in general; only rotations and reflections of the circle
identify paintings.
Inputs: n and k must be ints (bool is not an int) with 3 <= n <= 5000 and 1 <= k <= 10**6,
otherwise raise ValueError. The result is an exact int (it can have thousands of digits, so no
floats and no modulus). It is 0 whenever no proper painting exists, for instance k = 1, or k = 2
with odd n.
Details that matter:
- A painting that is fixed by a rotation or reflection is still counted once, so the answer is
  not simply the number of proper paintings divided by 2n.
- "No two neighbouring beads equal" is checked around the whole circle, including the pair
  (bead n, bead 1).
- Reflections matter: flipping the circle over can turn a painting into a different painting of the
  same bracelet, and a painting symmetric under a flip or a rotation is still just one bracelet.
Examples:
- proper_bracelet_count(4, 2) == 1      (RBRB and BRBR are one bracelet)
- proper_bracelet_count(3, 3) == 1      (all three colours, whichever way round)
- proper_bracelet_count(5, 3) == 3
- proper_bracelet_count(6, 3) == 13
- proper_bracelet_count(4, 3) == 6
- proper_bracelet_count(5, 2) == 0
''', r'''
import random
from math import gcd

def rej(*args):
    try:
        proper_bracelet_count(*args)
    except ValueError:
        return True
    return False

def brute(n, k):
    seen = set()
    cur = []
    def rec():
        if len(cur) == n:
            if cur[0] != cur[-1]:
                best = None
                for r in range(n):
                    rot = tuple(cur[r:] + cur[:r])
                    for cand in (rot, rot[::-1]):
                        if best is None or cand < best:
                            best = cand
                seen.add(best)
            return
        for c in range(k):
            if not cur or cur[-1] != c:
                cur.append(c)
                rec()
                cur.pop()
    rec()
    return len(seen)

def explicit(n, k, mod):
    # sum over the 2n dihedral elements, all arithmetic modulo a prime
    tot = 0
    for r in range(n):
        g = gcd(r, n)
        tot += (pow(k - 1, g, mod) + (-1) ** g * (k - 1)) % mod
    refl = 0
    if n % 2 == 0:
        for axis in range(n):
            if axis % 2 == 0:
                refl += k * pow(k - 1, n // 2, mod)
    tot = (tot + refl) % mod
    return tot * pow(2 * n, -1, mod) % mod

EX = [(4, 2, 1), (3, 3, 1), (5, 3, 3), (6, 3, 13), (4, 3, 6), (5, 2, 0), (3, 1, 0), (3, 2, 0), (6, 2, 1), (8, 2, 1),
      (3, 4, 4), (3, 5, 10), (4, 4, 21)]
for n, k, e in EX:
    got = proper_bracelet_count(n, k)
    assert type(got) is int and got == e, (n, k, got, e)
    assert got == brute(n, k), (n, k)

for n in range(3, 9):
    for k in range(1, 6):
        if k ** n <= 40000:
            assert proper_bracelet_count(n, k) == brute(n, k), (n, k)
for n in range(3, 13):
    assert proper_bracelet_count(n, 3) == brute(n, 3), n
    assert proper_bracelet_count(n, 2) == (1 if n % 2 == 0 else 0), n
for n in range(3, 40):
    assert proper_bracelet_count(n, 1) == 0

random.seed(6010)
for _ in range(40):
    n = random.randint(3, 9)
    k = random.randint(1, 4)
    assert proper_bracelet_count(n, k) == brute(n, k), (n, k)

# exact check by summing over the dihedral group with big integers
for n in (10, 12, 15, 16, 30, 36, 45):
    for k in (2, 3, 4, 7, 10**6):
        P = 1
        tot = 0
        for r in range(n):
            g = gcd(r, n)
            tot += (k - 1) ** g + (-1) ** g * (k - 1)
        if n % 2 == 0:
            tot += (n // 2) * k * (k - 1) ** (n // 2)
        assert tot % (2 * n) == 0
        got = proper_bracelet_count(n, k)
        assert type(got) is int and got * 2 * n == tot, (n, k)

# large inputs: compare modulo primes with an explicit group sum
for n, k in [(5000, 10**6), (4999, 999983), (4096, 3), (3600, 12345), (2310, 2), (3125, 5), (1001, 10**6), (97, 10**6), (5000, 2), (4999, 3)]:
    got = proper_bracelet_count(n, k)
    assert type(got) is int and got >= 0
    for mod in (1000000007, 998244353):
        assert got % mod == explicit(n, k, mod), (n, k, mod)
assert proper_bracelet_count(5000, 2) == 1 and proper_bracelet_count(4999, 2) == 0
assert proper_bracelet_count(4999, 10**6) * 2 * 4999 * 10 > 9 * (10**6 - 1) ** 4999

for bad in (0, 1, 2, -3, 5001, 3.0, "4", None, True, [4]):
    assert rej(bad, 3), bad
for bad in (0, -1, 10**6 + 1, 2.0, "3", None, False, [3]):
    assert rej(5, bad), bad
assert rej(True, True) and rej(2, 0) and rej(5001, 10**6 + 1)
''', r'''
def proper_bracelet_count(n, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not isint(k) or not 3 <= n <= 5000 or not 1 <= k <= 10**6:
        raise ValueError("range")
    def phi(x):
        r = x
        p = 2
        while p * p <= x:
            if x % p == 0:
                while x % p == 0:
                    x //= p
                r -= r // p
            p += 1
        if x > 1:
            r -= r // x
        return r
    def cyc(g):
        return (k - 1) ** g + (-1) ** g * (k - 1)
    tot = 0
    for g in range(1, n + 1):
        if n % g == 0:
            tot += phi(n // g) * cyc(g)
    if n % 2 == 0:
        tot += (n // 2) * k * (k - 1) ** (n // 2)
    return tot // (2 * n)
''')

task("v6_11_nonzero_digit_sum_kth", r'''
Write `nonzero_digit_sum_kth(b, s, k)` that returns the k-th smallest positive integer whose
representation in base b uses only nonzero digits and whose digits add up to exactly s
(k = 1 is the smallest). The result is returned as an ordinary Python int (its value, not a
digit string).
Inputs: b, s, k must be ints (bool is not an int) with 2 <= b <= 16, 1 <= s <= 60 and
1 <= k <= 10**20, otherwise raise ValueError. If fewer than k such numbers exist, raise ValueError too.
Details that matter:
- Digits of a base-b numeral are 0 .. b-1, and here digit 0 is forbidden, so only digits
  1 .. b-1 appear. The numeral has no leading zeros (there are none anyway).
- Because every digit is at least 1, a numeral with digit sum s has at most s digits, so only
  finitely many numbers qualify. For b = 2 the digits are all 1, so exactly one number qualifies:
  2**s - 1.
- Order is by numeric value. Numbers with fewer digits are smaller; numbers with the same number
  of digits compare digit by digit from the most significant digit.
- The number of qualifying numbers can be around 5 * 10**17 (b = 16, s = 60), so they cannot be
  listed and sorted.
Examples:
- nonzero_digit_sum_kth(10, 3, 1) == 3 and nonzero_digit_sum_kth(10, 3, 4) == 111; the qualifying
  numbers are 3, 12, 21, 111, so k = 5 raises ValueError.
- b = 3, s = 4: the numerals are 22, 112, 121, 211, 1111 in base 3, which are 8, 14, 16, 22, 40,
  so nonzero_digit_sum_kth(3, 4, 2) == 14 and nonzero_digit_sum_kth(3, 4, 5) == 40.
- nonzero_digit_sum_kth(2, 5, 1) == 31 and nonzero_digit_sum_kth(2, 5, 2) raises ValueError.
- nonzero_digit_sum_kth(16, 3, 4) == 273 (the numeral 111 in base 16).
''', r'''
import random
from math import comb

def rej(*args):
    try:
        nonzero_digit_sum_kth(*args)
    except ValueError:
        return True
    return False

def all_numbers(b, s):
    out = []
    def rec(val, rem):
        if rem == 0:
            out.append(val)
            return
        for d in range(1, min(b - 1, rem) + 1):
            rec(val * b + d, rem - d)
    rec(0, s)
    out.sort()
    return out

def comps(L, s, b):
    # number of strings of L digits in 1..b-1 with sum s, by inclusion-exclusion
    if L == 0:
        return 1 if s == 0 else 0
    tot = 0
    for j in range(L + 1):
        top = s - L - j * (b - 1)
        if top < 0:
            break
        tot += (-1) ** j * comb(L, j) * comb(top + L - 1, L - 1)
    return tot

def digits(x, b):
    out = []
    while x:
        out.append(x % b)
        x //= b
    return out[::-1]

def total(b, s):
    return sum(comps(L, s, b) for L in range(1, s + 1))

def rank(x, b, s):
    ds = digits(x, b)
    L = len(ds)
    r = sum(comps(j, s, b) for j in range(1, L))
    used = 0
    for i, d in enumerate(ds):
        for c in range(1, d):
            r += comps(L - i - 1, s - used - c, b)
        used += d
    return r + 1

for k, e in [(1, 3), (2, 12), (3, 21), (4, 111)]:
    got = nonzero_digit_sum_kth(10, 3, k)
    assert type(got) is int and got == e, (k, got)
assert rej(10, 3, 5)
for k, e in zip(range(1, 6), [8, 14, 16, 22, 40]):
    assert nonzero_digit_sum_kth(3, 4, k) == e
assert rej(3, 4, 6)
assert nonzero_digit_sum_kth(2, 5, 1) == 31 and rej(2, 5, 2)
assert nonzero_digit_sum_kth(16, 3, 4) == 273 and nonzero_digit_sum_kth(16, 3, 1) == 3
assert nonzero_digit_sum_kth(2, 60, 1) == 2**60 - 1 and rej(2, 60, 2)
assert nonzero_digit_sum_kth(2, 1, 1) == 1 and rej(2, 1, 2)
assert nonzero_digit_sum_kth(16, 1, 1) == 1 and rej(16, 1, 2)
assert nonzero_digit_sum_kth(16, 15, 1) == 15 and nonzero_digit_sum_kth(16, 16, 1) == 1 * 16 + 15
assert nonzero_digit_sum_kth(16, 16, 2) == 2 * 16 + 14

for b in range(2, 9):
    for s in range(1, 11):
        nums = all_numbers(b, s)
        assert len(nums) == total(b, s)
        for k in range(1, len(nums) + 1):
            got = nonzero_digit_sum_kth(b, s, k)
            assert type(got) is int and got == nums[k - 1], (b, s, k, got, nums[k - 1])
        assert rej(b, s, len(nums) + 1) and rej(b, s, len(nums) + 7)
for b, s in [(10, 7), (16, 8), (10, 9), (13, 9), (11, 8)]:
    nums = all_numbers(b, s)
    for k in list(range(1, 6)) + [len(nums) - 1, len(nums)]:
        assert nonzero_digit_sum_kth(b, s, k) == nums[k - 1]
    assert rej(b, s, len(nums) + 1)

random.seed(6011)
for _ in range(60):
    b = random.randint(2, 16)
    s = random.randint(1, 60)
    tt = total(b, s)
    k = min(tt, random.choice([random.randint(1, 10**20), random.randint(1, 10**6), int(10 ** random.uniform(0, 20)) or 1]))
    x = nonzero_digit_sum_kth(b, s, k)
    assert type(x) is int
    ds = digits(x, b)
    assert ds and all(1 <= d < b for d in ds) and sum(ds) == s, (b, s, k, x)
    assert rank(x, b, s) == k, (b, s, k, x)
for b, s in [(16, 60), (10, 60), (8, 60), (5, 60), (3, 60), (12, 47)]:
    tt = total(b, s)
    assert tt <= 10**20
    last = nonzero_digit_sum_kth(b, s, tt)
    assert rank(last, b, s) == tt
    assert set(digits(last, b)) == {1} or True
    assert rej(b, s, tt + 1)
    first = nonzero_digit_sum_kth(b, s, 1)
    assert rank(first, b, s) == 1
    prev = None
    for k in (1, 2, 3, 4, tt // 3, tt // 2, tt - 1, tt):
        x = nonzero_digit_sum_kth(b, s, k)
        assert prev is None or x > prev
        prev = x

for bad in (1, 0, 17, -2, 2.0, "10", None, True, [10]):
    assert rej(bad, 3, 1), bad
for bad in (0, -1, 61, 3.0, "3", None, False, [3]):
    assert rej(10, bad, 1), bad
for bad in (0, -1, 10**20 + 1, 1.0, "1", None, True, [1]):
    assert rej(10, 3, bad), bad
assert rej(True, True, True) and rej(10, 60, 10**20 + 1)
''', r'''
_cache = {}

def nonzero_digit_sum_kth(b, s, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not (isint(b) and isint(s) and isint(k)) or not 2 <= b <= 16 or not 1 <= s <= 60 or not 1 <= k <= 10**20:
        raise ValueError("range")
    if b not in _cache:
        w = [[0] * 61 for _ in range(61)]
        w[0][0] = 1
        for L in range(1, 61):
            for t in range(L, 61):
                w[L][t] = sum(w[L - 1][t - d] for d in range(1, min(b - 1, t) + 1))
        _cache[b] = w
    w = _cache[b]
    for L in range(1, s + 1):
        c = w[L][s]
        if k <= c:
            break
        k -= c
    else:
        raise ValueError("fewer than k numbers")
    val = 0
    rem = s
    for pos in range(L):
        left = L - pos - 1
        for d in range(1, b):
            if d > rem:
                break
            c = w[left][rem - d]
            if k <= c:
                val = val * b + d
                rem -= d
                break
            k -= c
    return val
''')

task("v6_12_achilles_count", r'''
Write `achilles_up_to(n)` that returns how many Achilles numbers lie in the range 1 .. n.
A positive integer m is an Achilles number when both hold:
- m is powerful: for every prime p dividing m, p*p also divides m;
- m is not a perfect power: there are no integers c >= 2 and e >= 2 with m == c**e.
The number 1 is not an Achilles number (by convention), so the smallest Achilles number is
72 = 2**3 * 3**2.
Input: n must be an int (bool is not an int) with 1 <= n <= 10**15, otherwise raise ValueError.
The result is an int.
n can be 10**15, so examining the numbers one by one is impossible; there are roughly 3.7 * 10**7
Achilles numbers below 10**15, and even listing them is too slow. Integer square, cube and higher
roots must be exact: at this size a float root can be off by one, which miscounts when n is
itself c**e or just below it.
Details that matter:
- Every perfect power greater than 1 is powerful, so it is powerful but excluded here. Numbers such
  as 2**3 * 3**3 = 216 = 6**3 or 2**2 * 3**4 = 324 = 18**2 are not Achilles; 2**3 * 3**2 = 72 is.
- A powerful number that is not a perfect power can have one prime or many; for example
  2**5 * 3**3 = 864 and 2**2 * 3**3 * 5**5 are Achilles, while 2**4 * 3**6 = 108**2 is not:
  the exponents 4 and 6 share the factor 2, so it is a perfect square.
- A number with a prime dividing it exactly once, such as 2**3 * 3 = 24, is not powerful.
Examples:
- achilles_up_to(71) == 0 and achilles_up_to(72) == 1
- achilles_up_to(500) == 7   (72, 108, 200, 288, 392, 432, 500)
- achilles_up_to(1000) == 13
- achilles_up_to(10**4) == 60
- achilles_up_to(10**6) == 916
''', r'''
import random
from math import gcd
from bisect import bisect_right

def factor_exps(x):
    es = []
    p = 2
    while p * p <= x:
        if x % p == 0:
            e = 0
            while x % p == 0:
                x //= p
                e += 1
            es.append(e)
        p += 1
    if x > 1:
        es.append(1)
    return es

def is_ach(x):
    if x == 1:
        return False
    es = factor_exps(x)
    g = 0
    for e in es:
        if e < 2:
            return False
        g = gcd(g, e)
    return g == 1

LIST = [x for x in range(1, 20001) if is_ach(x)]

def small(n):
    return bisect_right(LIST, n)

PR = [p for p in range(2, 6000) if all(p % q for q in range(2, int(p ** 0.5) + 1))]

def dfs_count(n):
    # build every powerful number <= n as a product of prime powers with exponent >= 2,
    # keep those whose exponents have gcd 1
    cnt = 0
    stack = [(0, 1, 0)]
    while stack:
        i, cur, g = stack.pop()
        if g == 1:
            cnt += 1
        for j in range(i, len(PR)):
            p = PR[j]
            v = cur * p * p
            if v > n:
                break
            e = 2
            while v <= n:
                stack.append((j + 1, v, gcd(g, e)))
                v *= p
                e += 1
    return cnt

def fa(n):
    got = achilles_up_to(n)
    assert type(got) is int, (n, type(got))
    return got

def rej(*args):
    try:
        achilles_up_to(*args)
    except ValueError:
        return True
    return False

for n, e in [(1, 0), (71, 0), (72, 1), (108, 2), (500, 7), (1000, 13), (10**4, 60), (10**6, 916)]:
    assert fa(n) == e, (n, fa(n), e)
assert LIST[:6] == [72, 108, 200, 288, 392, 432]
for n in list(range(1, 400)) + [499, 500, 501, 971, 972, 973, 1124, 1125, 1126, 19999, 20000]:
    assert fa(n) == small(n), (n, fa(n), small(n))

random.seed(6012)
for _ in range(120):
    n = random.randint(1, 20000)
    assert fa(n) == small(n), n
for n in (10**8, 2 * 10**8 + 12345, 99999999, 123456789):
    assert fa(n) == dfs_count(n), n

# a number m is counted exactly when f(m) - f(m - 1) == 1, whatever its size
def step(m):
    return fa(m) - fa(m - 1)

ach = [2**5 * 3**3 * 5**2 * 7**2 * 11**3 * 13**2, 2**3 * 3**2 * 10007**2, 2**2 * 3**3 * 5**5 * 7**7,
       71**2 * 73**3 * 79**2, 2**3 * 3**2 * 17**5, 999983**2 * 7**3]
non = [2**4 * 3**4 * 5**6 * 7**2, 6**7 * 10**7, 2**3 * 3**3 * 5**3 * 7**3 * 11**3, 3**27, 10**13, 999983**2,
       2**10 * 3, 2**5 * 3**5 * 5**5 * 7**2 * 13, 31622776**2, 99999**3, 1000003**2]
for m in ach:
    assert m <= 10**15
    assert step(m) == 1, m
for m in non:
    assert m <= 10**15
    assert step(m) == 0, m

# perfect powers at the top of the range and their neighbours
for m in (10**15, 2**49):
    assert fa(m) == fa(m - 1), m

# asymptotics: powerful ~ 2.1732 sqrt(n), perfect powers ~ sqrt(n), so Achilles ~ 1.1732 sqrt(n)
n = 10**15
v = fa(n)
assert abs(v - 1.1732 * n ** 0.5) < 0.02 * n ** 0.5, v
assert fa(10**13) > fa(10**12) > fa(10**11) > fa(10**10)

for bad in (0, -1, 10**15 + 1, 10**18, 1.0, 72.0, "72", None, True, False, [72]):
    assert rej(bad), bad
''', r'''
from math import isqrt

def achilles_up_to(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10**15:
        raise ValueError("range")
    def iroot(x, e):
        r = int(round(x ** (1.0 / e)))
        while r ** e > x:
            r -= 1
        while (r + 1) ** e <= x:
            r += 1
        return r
    lim = iroot(n, 3)
    sf = bytearray([1]) * (lim + 1)
    for p in range(2, isqrt(lim) + 1):
        for q in range(p * p, lim + 1, p * p):
            sf[q] = 0
    powerful = 0
    for b in range(1, lim + 1):
        if sf[b]:
            powerful += isqrt(n // b ** 3)
    def mobius(k):
        r = 1
        x = k
        p = 2
        while p * p <= x:
            if x % p == 0:
                x //= p
                if x % p == 0:
                    return 0
                r = -r
            p += 1
        if x > 1:
            r = -r
        return r
    perfect = 0
    e = 2
    while 2 ** e <= n:
        perfect += -mobius(e) * (iroot(n, e) - 1)
        e += 1
    return powerful - 1 - perfect
''')

task("v6_13_simplest_fraction", r'''
Write `simplest_between(lo, hi, lo_incl=True, hi_incl=True)` that returns the simplest fraction in
the interval from lo to hi, as a `fractions.Fraction`.
lo and hi are ints or `Fraction` objects (not bool, not float); lo_incl and hi_incl must be bool.
The interval contains lo only when lo_incl is True and contains hi only when hi_incl is True; all
points strictly between them are always inside.
"Simplest" means: among all rational numbers in the interval, the one with the smallest
denominator (in lowest terms); if several have that denominator, the one with the smallest
absolute numerator. The result is always a `Fraction` object, also when it is an integer
(then its denominator is 1 and the "simplest" integer is the one closest to 0, so 0 whenever
0 is in the interval). Negative intervals work too, with the same rule, and the interval may
cross zero.
Raise ValueError when an argument has the wrong type (a bool, a float, a str, None for lo or hi;
a non-bool for a flag), when lo > hi, or when the interval is empty because lo == hi and not both
ends are included. lo == hi with both ends included is the single point lo.
The numerators and denominators can have dozens of digits, so scanning denominators one by one
is impossible; exact rational arithmetic is required (no floats).
Examples:
- simplest_between(Fraction(1, 3), Fraction(1, 2)) == Fraction(1, 2)   (the closed interval holds 1/2)
- simplest_between(Fraction(1, 3), Fraction(1, 2), False, False) == Fraction(2, 5)
- simplest_between(-3, 5) == Fraction(0)
- simplest_between(Fraction(7, 3), Fraction(5, 2), False, False) == Fraction(12, 5)
- simplest_between(1, Fraction(3, 2), False, False) == Fraction(4, 3)   (the integer 1 is excluded)
- simplest_between(Fraction(-1, 2), 0, True, False) == Fraction(-1, 2)
- simplest_between(Fraction(314159, 100000), Fraction(31416, 10000)) == Fraction(355, 113)
''', r'''
import random
from fractions import Fraction as F

def inside(r, lo, hi, li, hi_i):
    return (lo < r or (li and r == lo)) and (r < hi or (hi_i and r == hi))

def brute(lo, hi, li, hi_i):
    for q in range(1, 200):
        best = None
        for p in range(int(lo * q) - 2, int(hi * q) + 3):
            if inside(F(p, q), lo, hi, li, hi_i):
                if best is None or (abs(p), p) < (abs(best), best):
                    best = p
        if best is not None:
            return F(best, q)
    raise AssertionError("no fraction found")

def rej(*args):
    try:
        simplest_between(*args)
    except ValueError:
        return True
    return False

def same(lo, hi, li, hi_i, exp):
    got = simplest_between(lo, hi, li, hi_i)
    assert type(got) is F and got == exp and got.denominator == exp.denominator, (lo, hi, li, hi_i, got, exp)

EX = [(F(1, 3), F(1, 2), True, True, F(1, 2)), (F(1, 3), F(1, 2), False, False, F(2, 5)), (-3, 5, True, True, F(0)),
      (F(7, 3), F(5, 2), False, False, F(12, 5)), (1, F(3, 2), False, False, F(4, 3)), (F(-1, 2), 0, True, False, F(-1, 2)),
      (F(314159, 100000), F(31416, 10000), True, True, F(355, 113)), (F(1, 3), F(1, 2), False, True, F(1, 2)),
      (F(1, 3), F(1, 2), True, False, F(1, 3)), (3, 3, True, True, F(3)), (F(5, 7), F(5, 7), True, True, F(5, 7)),
      (0, 0, True, True, F(0)), (2, 9, True, True, F(2)), (2, 9, False, True, F(3)), (-9, -2, True, False, F(-3)),
      (-9, -2, True, True, F(-2)), (0, 5, False, True, F(1)), (-5, 0, True, False, F(-1)), (-1, 1, False, False, F(0)),
      (F(-1, 2), F(1, 2), False, False, F(0)), (F(1, 2), 1, False, False, F(2, 3)), (F(1, 2), 1, True, False, F(1, 2)),
      (F(-1), F(-1, 2), False, False, F(-2, 3)), (5, F(11, 2), False, False, F(16, 3)), (F(1, 100), F(1, 99), True, True, F(1, 99)),
      (F(1, 100), F(1, 99), False, False, F(2, 199))]
for lo, hi, li, hi_i, e in EX:
    same(lo, hi, li, hi_i, e)
    assert e == brute(F(lo), F(hi), li, hi_i), (lo, hi, li, hi_i)
assert simplest_between(F(1, 3), F(1, 2)) == F(1, 2) and simplest_between(F(1, 3), F(1, 2), False) == F(1, 2)
assert simplest_between(F(1, 3), F(1, 2), hi_incl=False) == F(1, 3)
assert type(simplest_between(2, 2)) is F

random.seed(6013)
for _ in range(500):
    lo = F(random.randint(-60, 60), random.randint(1, 12))
    hi = lo + F(random.randint(0, 40), random.randint(1, 15))
    li = random.random() < 0.5
    hi_i = random.random() < 0.5
    if lo == hi and not (li and hi_i):
        assert rej(lo, hi, li, hi_i)
        continue
    if random.random() < 0.3:
        lo = lo.numerator if lo.denominator == 1 else lo
    same(lo, hi, li, hi_i, brute(F(lo), hi, li, hi_i))
for _ in range(200):
    lo = F(random.randint(-10**4, 10**4), random.randint(1, 10**4))
    hi = lo + F(random.randint(1, 30), random.randint(10**3, 10**5))
    li = random.random() < 0.5
    hi_i = random.random() < 0.5
    r = simplest_between(lo, hi, li, hi_i)
    assert type(r) is F and inside(r, lo, hi, li, hi_i)
    for q in range(1, r.denominator):
        p0 = int(lo * q) - 1
        for p in range(p0, p0 + 3 + int((hi - lo) * q) + 1):
            assert not inside(F(p, q), lo, hi, li, hi_i), (lo, hi, li, hi_i, r, p, q)

# Farey neighbours with huge terms: the open interval's simplest point is the mediant, an
# included end wins by its smaller denominator
def neighbours(steps):
    a, b, c, d = 0, 1, 1, 1
    for _ in range(steps):
        m = (a + c, b + d)
        if random.random() < 0.5:
            a, b = m
        else:
            c, d = m
    return a, b, c, d

for steps in (1, 2, 5, 30, 90, 200, 400):
    for _ in range(4):
        a, b, c, d = neighbours(steps)
        shift = random.randint(-10**6, 10**6) * random.choice([0, 1])
        lo = F(a + shift * b, b)
        hi = F(c + shift * d, d)
        assert lo.denominator == b and hi.denominator == d
        mid = F(a + c + shift * (b + d), b + d)
        same(lo, hi, False, False, mid)
        same(lo, hi, True, False, lo)
        same(lo, hi, False, True, hi)
        same(lo, hi, True, True, lo if b < d else hi)

big = 10**40
same(F(big, 3), F(big, 3) + 1, True, True, F(big // 3 + 1))
same(F(10**60 + 1, 10**60), F(10**60 + 2, 10**60), False, False, F(5 * 10**59 + 2, 5 * 10**59 + 1))
same(F(-10**60 - 2, 10**60), F(-10**60 - 1, 10**60), False, False, F(-5 * 10**59 - 2, 5 * 10**59 + 1))
same(F(10**30, 10**30 + 1), 1, True, False, F(10**30, 10**30 + 1))
same(F(10**30, 10**30 + 1), 1, False, False, F(10**30 + 1, 10**30 + 2))
same(F(-10**30, 10**30 + 1), F(10**30, 10**30 + 1), False, False, F(0))

for lo, hi in [(2, 1), (F(1, 2), F(1, 3)), (F(1, 2), F(1, 2) - F(1, 10**30)), (0, -1)]:
    assert rej(lo, hi), (lo, hi)
for li, hi_i in [(False, True), (True, False), (False, False)]:
    assert rej(F(1, 3), F(1, 3), li, hi_i) and rej(0, 0, li, hi_i)
for bad in (0.5, "1/2", None, True, False, [1], (1, 2), 1j):
    assert rej(bad, 1), bad
    assert rej(0, bad), bad
for flag in (1, 0, None, "yes", 1.0, [True]):
    assert rej(0, 1, flag, True), flag
    assert rej(0, 1, True, flag), flag
assert rej(0.0, 1.0) and rej(True, True) and rej(None, None)
''', r'''
from fractions import Fraction

def simplest_between(lo, hi, lo_incl=True, hi_incl=True):
    def isnum(v):
        return isinstance(v, (int, Fraction)) and not isinstance(v, bool)
    if not isnum(lo) or not isnum(hi) or not isinstance(lo_incl, bool) or not isinstance(hi_incl, bool):
        raise ValueError("type")
    lo = Fraction(lo)
    hi = Fraction(hi)
    if lo > hi or (lo == hi and not (lo_incl and hi_incl)):
        raise ValueError("empty")

    def solve(lo, hi, li, hi_i):
        # hi may be None meaning +infinity; lo >= 0 or the interval touches 0 from the integer branch
        a = -(-lo.numerator // lo.denominator)
        if lo.denominator == 1 and not li:
            a += 1
        if hi is None:
            b = None
        else:
            b = hi.numerator // hi.denominator
            if hi.denominator == 1 and not hi_i:
                b -= 1
        if b is None or a <= b:
            if a <= 0 and (b is None or b >= 0):
                return Fraction(0)
            return Fraction(a) if a > 0 else Fraction(b)
        if hi <= 0:
            return -solve(-hi, -lo, hi_i, li)
        f = lo.numerator // lo.denominator
        lo2 = lo - f
        hi2 = hi - f
        new_hi = None if lo2 == 0 else 1 / lo2
        r = solve(1 / hi2, new_hi, hi_i, li)
        return f + 1 / r
    return solve(lo, hi, lo_incl, hi_incl)
''')

task("v6_14_clamped_lattice", r'''
Write `clamped_floor_lattice(n, a, b, c)` that counts the lattice points (x, y) with integers
1 <= x <= n, y >= 1 and c*y <= a*x + b. Equivalently it returns the sum over x = 1 .. n of
max(0, floor((a*x + b) / c)), where floor rounds toward minus infinity.
Inputs: n, a, b, c must be ints (bool is not an int) with 1 <= n <= 10**12, abs(a) <= 10**18,
abs(b) <= 10**18 and 1 <= c <= 10**12, otherwise raise ValueError. The result is an int.
n can be 10**12, so summing term by term is impossible, and the values a*x + b can reach
10**30, so the arithmetic must be exact (Python ints, no floats).
Details that matter:
- a and b may be negative. A column x whose line height (a*x + b) / c is below 1 contains no
  point and adds 0; it must never add a negative amount. The sum is clamped term by term, not
  at the end, so for a > 0 and b very negative the early columns add nothing and the later
  ones do, and for a < 0 the early columns count and the later ones add nothing.
- floor((a*x + b) / c) can be positive only when a*x + b >= c.
- a == 0 is allowed: every column then has height floor(b / c) if that is at least 1, else 0.
- The line height may not be an integer: use floor, not rounding.
Examples:
- clamped_floor_lattice(10, 3, -5, 4) == 26
  (heights floor((3x - 5) / 4) for x = 1 .. 10 are -1, 0, 1, 1, 2, 3, 4, 4, 5, 6 -> 0, 0, 1, 1, 2,
  3, 4, 4, 5, 6)
- clamped_floor_lattice(5, -2, 9, 3) == 4   (heights 2, 1, 1, 0, -1 -> 2 + 1 + 1 + 0 + 0)
- clamped_floor_lattice(7, 0, 10, 3) == 21
- clamped_floor_lattice(7, 0, 2, 3) == 0
- clamped_floor_lattice(10**12, 1, 0, 1) == 500000000000500000000000
''', r'''
import random

def brute(n, a, b, c):
    return sum(max(0, (a * x + b) // c) for x in range(1, n + 1))

def rej(*args):
    try:
        clamped_floor_lattice(*args)
    except ValueError:
        return True
    return False

def g(n, a, b, c):
    got = clamped_floor_lattice(n, a, b, c)
    assert type(got) is int
    return got

for args, e in [((10, 3, -5, 4), 26), ((5, -2, 9, 3), 4), ((7, 0, 10, 3), 21), ((7, 0, 2, 3), 0),
                ((10**12, 1, 0, 1), 500000000000500000000000), ((1, 0, 0, 1), 0), ((1, 1, 0, 1), 1), ((1, 0, 1, 1), 1),
                ((1, -1, 1, 1), 0), ((3, -5, -5, 2), 0), ((4, 1, -3, 1), 1)]:
    assert g(*args) == e, (args, g(*args), e)
    if args[0] <= 1000:
        assert e == brute(*args), args

random.seed(6014)
for _ in range(500):
    n = random.randint(1, 60)
    a = random.randint(-12, 12)
    b = random.randint(-70, 70)
    c = random.randint(1, 15)
    assert g(n, a, b, c) == brute(n, a, b, c), (n, a, b, c)
for _ in range(120):
    n = random.randint(1, 400)
    a = random.choice([random.randint(-10**6, 10**6), random.randint(-10**18, 10**18)])
    b = random.choice([random.randint(-10**8, 10**8), random.randint(-10**18, 10**18), 0])
    c = random.choice([random.randint(1, 50), random.randint(1, 10**12), random.randint(1, 10**4)])
    assert g(n, a, b, c) == brute(n, a, b, c), (n, a, b, c)
for n in (1, 2, 3, 50):
    for a in (-10**18, -3, -1, 0, 1, 3, 10**18):
        for b in (-10**18, -7, 0, 7, 10**18):
            for c in (1, 2, 7, 10**12):
                assert g(n, a, b, c) == brute(n, a, b, c), (n, a, b, c)

# huge inputs, checked by structure
def arith(lo, hi, a, b):
    # sum of a*x + b for x = lo .. hi
    k = hi - lo + 1
    return k * b + a * (lo + hi) * k // 2

for _ in range(20):
    n = random.randint(1, 10**12)
    a = random.randint(1, 10**6)
    b = random.randint(1, 10**15)
    assert g(n, a, b, 1) == arith(1, n, a, b)
    # c = 1, a < 0: positive only for x <= (b - 1) // -a
    X = min(n, (b - 1) // a)
    assert g(n, -a, b, 1) == (arith(1, X, -a, b) if X >= 1 else 0)
    # c = 1, a > 0, b negative: a*x - b is at least 1 only for x >= x0
    x0 = max(1, -(-(1 + b) // a))
    got = g(n, a, -b, 1)
    ex = arith(x0, n, a, -b) if x0 <= n else 0
    assert got == ex, (n, a, b, got, ex)

for _ in range(15):
    c = random.randint(1, 3000)
    q = random.randint(1, 10**12 // c)
    a = random.randint(0, 10**18)
    b = random.randint(c, 10**18)
    S = sum((a * x + b) // c for x in range(1, c + 1))
    assert g(q * c, a, b, c) == q * S + a * c * q * (q - 1) // 2, (c, q, a, b)
for _ in range(15):
    c = random.randint(1, 10**12)
    n = random.randint(1, 10**12)
    b = random.randint(0, 10**18)
    assert g(n, c, b, c) == n * (n + 1) // 2 + n * (b // c)

for _ in range(40):
    n = random.randint(2, 10**12)
    k = random.randint(1, n - 1)
    a = random.randint(-10**5, 10**5)
    b = random.randint(-10**17, 10**17)
    c = random.randint(1, 10**12)
    whole = g(n, a, b, c)
    assert whole == g(k, a, b, c) + g(n - k, a, b + a * k, c), (n, k, a, b, c)
    assert whole == g(n, -a, b + a * (n + 1), c), (n, a, b, c)
assert g(10**12, 10**18, -10**18, 10**12) == 10**6 * (10**12 * (10**12 - 1) // 2)
assert g(10**12, 10**12, 10**12, 10**12) == 10**12 * (10**12 + 1) // 2 + 10**12
assert g(10**12, 0, 10**18, 10**12) == 10**12 * 10**6
assert g(10**12, 0, 10**12 - 1, 10**12) == 0
assert g(10**12, -1, 10**18, 1) == 10**12 * 10**18 - 10**12 * (10**12 + 1) // 2

for bad in (0, -1, 10**12 + 1, 3.0, "3", None, True, [3]):
    assert rej(bad, 1, 1, 1), bad
for bad in (10**18 + 1, -10**18 - 1, 1.0, "1", None, True, [1]):
    assert rej(5, bad, 1, 1), bad
    assert rej(5, 1, bad, 1), bad
for bad in (0, -1, 10**12 + 1, 2.0, "2", None, False, [2]):
    assert rej(5, 1, 1, bad), bad
assert rej(True, True, True, True) and rej(0, 0, 0, 0)
''', r'''
def clamped_floor_lattice(n, a, b, c):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not all(isint(v) for v in (n, a, b, c)) or not 1 <= n <= 10**12 or abs(a) > 10**18 or abs(b) > 10**18 or not 1 <= c <= 10**12:
        raise ValueError("range")

    def floor_sum(cnt, m, a, b):
        # sum of floor((a*i + b) / m) for i = 0 .. cnt - 1, any integer a and b
        ans = 0
        while True:
            if a >= m or a < 0:
                ans += cnt * (cnt - 1) // 2 * (a // m)
                a %= m
            if b >= m or b < 0:
                ans += cnt * (b // m)
                b %= m
            y = a * cnt + b
            if y < m:
                break
            cnt, b = divmod(y, m)
            m, a = a, m
        return ans

    if a == 0:
        return n * (b // c) if b >= c else 0
    if a > 0:
        x1 = max(1, -(-(c - b) // a))
        x2 = n
    else:
        x1 = 1
        x2 = min(n, (b - c) // (-a))
    if x1 > x2:
        return 0
    return floor_sum(x2 - x1 + 1, c, a, a * x1 + b)
''')

task("v6_15_square_roots_mod", r'''
Write `square_roots_mod(a, n)` that returns how many integers x with 0 <= x < n satisfy
x*x is congruent to a modulo n (that is, n divides x*x - a).
Inputs: a and n must be ints (bool is not an int) with 1 <= n <= 10**10 and abs(a) <= 10**18,
otherwise raise ValueError. The result is an int. a may be negative or larger than n; the
congruence is the mathematical one, so only a modulo n matters (a = -1 and a = n - 1 are the
same). n is not necessarily prime and a is not necessarily coprime to n.
n can be 10**10, so trying every x is impossible.
Details that matter:
- n = 1: the only x is 0 and 0 is congruent to everything, so the answer is 1.
- When a and n share factors the count is not 0 or 2. For example x*x = 0 (mod 36) holds exactly
  for the multiples of 6, so there are 6 solutions in 0 .. 35, and x*x = 9 (mod 27) has 6
  solutions (3, 6, 12, 15, 21, 24).
- Powers of two are special: modulo 8 the odd squares are all congruent to 1, so x*x = 1
  (mod 8) has 4 solutions (1, 3, 5, 7), while x*x = 5 (mod 8) has none.
- Count each x in 0 .. n-1 once. For an odd prime n the answer is 1 when a is a multiple of n and
  otherwise 2 or 0; for n = 2 it is always 1 (x = 0 or x = 1, whichever matches a mod 2).
Examples:
- square_roots_mod(1, 8) == 4 and square_roots_mod(0, 8) == 2   (x = 0 and 4)
- square_roots_mod(4, 16) == 4   (x = 2, 6, 10, 14)
- square_roots_mod(-1, 13) == 2   (x = 5 and 8)
- square_roots_mod(0, 36) == 6 and square_roots_mod(9, 27) == 6
- square_roots_mod(2, 17) == 2 and square_roots_mod(3, 17) == 0
- square_roots_mod(7, 1) == 1
''', r'''
import random
from collections import Counter
from math import gcd

random.seed(6015)

def table(n):
    return Counter(x * x % n for x in range(n))

def rej(*args):
    try:
        square_roots_mod(*args)
    except ValueError:
        return True
    return False

def f(a, n):
    got = square_roots_mod(a, n)
    assert type(got) is int
    return got

for (a, n), e in [((1, 8), 4), ((0, 8), 2), ((4, 16), 4), ((-1, 13), 2), ((0, 36), 6), ((9, 27), 6), ((2, 17), 2),
                  ((3, 17), 0), ((7, 1), 1), ((5, 8), 0), ((0, 1), 1), ((0, 2), 1), ((1, 2), 1), ((1, 4), 2), ((2, 4), 0),
                  ((3, 4), 0), ((0, 4), 2), ((0, 9), 3), ((3, 9), 0), ((0, 27), 3), ((0, 16), 4), ((8, 16), 0), ((9, 16), 4)]:
    assert f(a, n) == e, (a, n, f(a, n), e)
    assert table(n)[a % n] == e, (a, n)

for n in range(1, 65):
    t = table(n)
    tot = 0
    for a in range(-n, 2 * n):
        assert f(a, n) == t[a % n], (a, n)
    for a in range(n):
        tot += f(a, n)
    assert tot == n, n

for n in (128, 256, 512, 1024, 4096, 729, 2187, 3125, 1458, 2500, 2016, 1155, 2310, 4725, 1000, 3969, 5040, 4608, 3 * 7 * 11 * 13, 97 * 41):
    t = table(n)
    if n <= 1100:
        pool = range(n)
    else:
        pool = list(set([random.randint(-3 * n, 3 * n) for _ in range(250)] + [x * x for x in range(0, 60)] + [0, n, -n, n // 2, n // 4, n // 8]))
    for a in pool:
        assert f(a, n) == t[a % n], (a, n)

for _ in range(60):
    n = random.randint(1, 5000)
    t = table(n)
    for _ in range(12):
        a = random.choice([random.randint(-10**18, 10**18), random.randint(0, n - 1), random.randint(0, 70) ** 2, random.randint(-n, 2 * n)])
        assert f(a, n) == t[a % n], (a, n)

# large prime moduli: Euler's criterion
for p in (9999999967, 4294967291, 2147483647, 1000000009, 998244353, 99991, 999983):
    assert f(0, p) == 1 and f(p, p) == 1 and f(-p, p) == 1
    for _ in range(6):
        x = random.randint(1, p - 1)
        r = x * x % p
        assert f(r, p) == 2 and f(r - p, p) == 2
        y = random.randint(1, p - 1)
        want = 2 if pow(y, (p - 1) // 2, p) == 1 else 0
        assert f(y, p) == want and f(y - p, p) == want

# prime powers
p = 99991
n = p * p
assert f(0, n) == p and f(p, n) == 0 and f(5 * p, n) == 0 and f(n, n) == p
for _ in range(5):
    x = random.randint(1, n - 1)
    if x % p:
        assert f(x * x % n, n) == 2
assert f(p * p * 3, n) == p
p = 2003
n = p ** 3
assert f(0, n) == p and f(p, n) == 0 and f(p * p, n) == 2 * p and f(-p * p, n) == (2 * p if p % 4 == 1 else 0)
assert f(4 * p * p, n) == 2 * p
nr = next(u for u in range(2, p) if pow(u, (p - 1) // 2, p) != 1)
assert f(nr * p * p, n) == 0 and f(nr, n) == 0
x = 12345
assert f(x * x, n) == 2

# powers of two
for e in (3, 10, 20, 33):
    n = 2 ** e
    assert f(1, n) == 4 and f(9, n) == 4 and f(17, n) == 4 and f(25, n) == 4
    assert f(3, n) == 0 and f(5, n) == 0 and f(7, n) == 0 and f(2, n) == 0 and f(6, n) == 0
    assert f(4, n) == 8 or e == 3
    assert f(0, n) == 2 ** (e // 2)
assert f(4, 2 ** 33) == 8 and f(4, 16) == 4 and f(4, 32) == 8 and f(4, 8) == 2 and f(4, 4) == 2
assert f(36, 2 ** 33) == 8 and f(16 * 17, 2 ** 33) == 16 and f(16 * 5, 2 ** 33) == 0 and f(8, 2 ** 33) == 0

# unit squares modulo a product of t odd primes number 2**t, with a factor 2, 4, 8 giving 1, 2, 4 times that
odd = [3, 5, 7, 11, 13, 17, 19, 23, 29]
prod = 1
for t, q in enumerate(odd, 1):
    prod *= q
    if prod * 8 <= 10**10:
        for mult, ex in ((1, 1), (2, 1), (4, 2), (8, 4)):
            n = prod * mult
            if n <= 10**10:
                x = random.randint(2, 10**6)
                while gcd(x, n) != 1:
                    x += 1
                assert f(x * x, n) == 2 ** t * ex, (t, mult, x)
assert f(1, 2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * 29) == 2 ** 9
assert f(0, 2 * 3 * 5 * 7 * 11 * 13 * 17 * 19 * 23 * 29) == 1

# multiplicativity over coprime moduli, with non-coprime a
for _ in range(25):
    n1 = random.choice([2 ** 5, 3 ** 4, 5 ** 3, 7 ** 2, 8 * 9, 25 * 4, 16, 27, 11, 13 * 13])
    n2 = random.choice([101, 103 ** 2, 7 * 11 * 13, 997 * 991, 31 ** 3, 125, 243, 17 * 19 * 23])
    if gcd(n1, n2) != 1 or n1 * n2 > 10**10:
        continue
    a = random.choice([random.randint(0, 10**18), random.randint(0, 50) ** 2 * random.randint(1, 50), n1 * random.randint(0, 5), n2 * random.randint(1, 30) ** 2])
    assert f(a, n1 * n2) == f(a, n1) * f(a, n2), (a, n1, n2)

assert f(10**18, 10**10) == f(10**18 % 10**10, 10**10) and f(-10**18, 7) == table(7)[(-10**18) % 7]
assert f(0, 10**10) == 10 ** 5 and f(0, 2 ** 33 * 1) == 2 ** 16

for bad in (0, -1, 10**10 + 1, 5.0, "5", None, True, [5]):
    assert rej(1, bad), bad
for bad in (10**18 + 1, -10**18 - 1, 1.0, "1", None, False, [1]):
    assert rej(bad, 5), bad
assert rej(True, True) and rej(0, 0) and rej(10**18 + 1, 10**10 + 1)
''', r'''
def square_roots_mod(a, n):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(a) or not isint(n) or not 1 <= n <= 10**10 or abs(a) > 10**18:
        raise ValueError("range")

    def prime_power(a, p, e):
        pe = p ** e
        a %= pe
        if a == 0:
            return p ** (e // 2)
        v = 0
        while a % p == 0:
            a //= p
            v += 1
        if v % 2:
            return 0
        k = v // 2
        m = e - v
        if p == 2:
            if m == 1:
                c = 1
            elif m == 2:
                c = 2 if a % 4 == 1 else 0
            else:
                c = 4 if a % 8 == 1 else 0
        else:
            c = 2 if pow(a % p, (p - 1) // 2, p) == 1 else 0
        return c * p ** k

    res = 1
    x = n
    p = 2
    while p * p <= x:
        if x % p == 0:
            e = 0
            while x % p == 0:
                x //= p
                e += 1
            res *= prime_power(a, p, e)
        p += 1 if p == 2 else 2
    if x > 1:
        res *= prime_power(a, x, 1)
    return res
''')

task("v6_16_derangement_unrank", r'''
Write `derangement_unrank(n, k)` that returns the k-th derangement of 1 .. n in lexicographic
order, as a tuple of ints. A derangement is a permutation (p_1, ..., p_n) of the numbers
1 .. n with p_i != i for every position i (positions are 1-based, so p_1 != 1, p_2 != 2, and so
on). Derangements are compared as tuples, first entry first, the way Python compares tuples,
and k = 1 is the smallest one.
Inputs: n and k must be ints (bool is not an int) with 1 <= n <= 25 and k >= 1, otherwise
raise ValueError. If there are fewer than k derangements of 1 .. n, raise ValueError too (for
n = 1 there are none, so every k raises ValueError). k has no upper limit other than that; for
n = 25 there are about 5.7 * 10**24 derangements, so they cannot be generated and counted.
Details that matter:
- The order is lexicographic on the tuples, not an order by "number of moved elements" or by
  recursion tree: for n = 4 the first derangement is (2, 1, 4, 3), the second is (2, 3, 4, 1).
- A prefix is only usable if it can still be completed to a derangement. For example for n = 3
  the prefix (2,) completes only to (2, 3, 1); (2, 1) cannot be completed.
- Two entries of the tuple can never be equal, and entry i can never be i, also for the last
  positions: (.., n) is only possible at positions before n.
Examples:
- derangement_unrank(3, 1) == (2, 3, 1) and derangement_unrank(3, 2) == (3, 1, 2);
  derangement_unrank(3, 3) raises ValueError.
- The nine derangements of 1 .. 4 in order: (2,1,4,3), (2,3,4,1), (2,4,1,3), (3,1,4,2), (3,4,1,2),
  (3,4,2,1), (4,1,2,3), (4,3,1,2), (4,3,2,1); so derangement_unrank(4, 4) == (3, 1, 4, 2).
- derangement_unrank(5, 1) == (2, 1, 4, 5, 3) and derangement_unrank(5, 44) == (5, 4, 2, 3, 1);
  derangement_unrank(5, 45) raises ValueError.
- derangement_unrank(2, 1) == (2, 1); derangement_unrank(1, 1) raises ValueError.
''', r'''
import random
from itertools import permutations
from functools import lru_cache
from math import factorial

random.seed(6016)

@lru_cache(maxsize=None)
def G(r, c):
    # ways to place r values into r positions when c of the values must avoid one specific position each
    if c == 0:
        return factorial(r)
    return G(r, c - 1) - G(r - 1, c - 1)

def total(n):
    d = [1, 0]
    for m in range(2, n + 1):
        d.append((m - 1) * (d[m - 1] + d[m - 2]))
    return d[n]

def rank(t):
    n = len(t)
    used = set()
    r = 1
    for i in range(1, n + 1):
        for v in range(1, t[i - 1]):
            if v in used or v == i:
                continue
            c = sum(1 for w in range(i + 1, n + 1) if w not in used and w != v)
            r += G(n - i, c)
        used.add(t[i - 1])
    return r

def rej(*args):
    try:
        derangement_unrank(*args)
    except ValueError:
        return True
    return False

def u(n, k):
    got = derangement_unrank(n, k)
    assert type(got) is tuple and len(got) == n and all(type(v) is int for v in got), (n, k, got)
    assert sorted(got) == list(range(1, n + 1)) and all(got[i] != i + 1 for i in range(n)), (n, k, got)
    return got

assert u(3, 1) == (2, 3, 1) and u(3, 2) == (3, 1, 2) and rej(3, 3)
L4 = [(2, 1, 4, 3), (2, 3, 4, 1), (2, 4, 1, 3), (3, 1, 4, 2), (3, 4, 1, 2), (3, 4, 2, 1), (4, 1, 2, 3), (4, 3, 1, 2), (4, 3, 2, 1)]
for k, e in enumerate(L4, 1):
    assert u(4, k) == e
assert rej(4, 10)
assert u(5, 1) == (2, 1, 4, 5, 3) and u(5, 44) == (5, 4, 2, 3, 1) and rej(5, 45)
assert u(2, 1) == (2, 1) and rej(2, 2) and rej(1, 1) and rej(1, 2) and rej(1, 10**30)

for n in range(2, 8):
    ds = sorted(p for p in permutations(range(1, n + 1)) if all(p[i] != i + 1 for i in range(n)))
    assert len(ds) == total(n)
    for k in range(1, len(ds) + 1):
        assert u(n, k) == ds[k - 1], (n, k)
    assert rej(n, len(ds) + 1) and rej(n, len(ds) + 1000) and rej(n, 10**40)

assert [total(n) for n in range(1, 11)] == [0, 1, 2, 9, 44, 265, 1854, 14833, 133496, 1334961]
for n in range(2, 26):
    D = total(n)
    first = u(n, 1)
    assert rank(first) == 1
    last = u(n, D)
    assert rank(last) == D
    if n % 2 == 0:
        assert last == tuple(range(n, 0, -1)), n
    assert rej(n, D + 1) and rej(n, D + 10**6)
    assert first < u(n, 2) < u(n, 3) if D >= 3 else True

for _ in range(70):
    n = random.randint(8, 25)
    D = total(n)
    k = random.choice([random.randint(1, D), random.randint(1, 10**6), D - random.randint(0, 1000), int(D ** random.random())])
    k = max(1, min(k, D))
    t = u(n, k)
    assert rank(t) == k, (n, k, t)
    if k < D:
        assert t < u(n, k + 1)
    if k > 1:
        assert u(n, k - 1) < t
t = u(25, 10**24)
assert rank(t) == 10**24
assert u(25, total(25))[0] == 25 and u(25, 1)[:2] == (2, 1)

for bad in (0, -1, 26, 100, 4.0, "4", None, True, [4]):
    assert rej(bad, 1), bad
for bad in (0, -1, -10**20, 2.0, "1", None, True, [1]):
    assert rej(4, bad), bad
assert rej(True, True) and rej(0, 0) and rej(26, 10**30)
''', r'''
from math import comb, factorial

_W = {}

def derangement_unrank(n, k):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not isint(k) or not 1 <= n <= 25 or k < 1:
        raise ValueError("range")

    def ways(r, c):
        key = (r, c)
        if key not in _W:
            _W[key] = sum((-1) ** j * comb(c, j) * factorial(r - j) for j in range(c + 1))
        return _W[key]

    if k > ways(n, n):
        raise ValueError("fewer than k derangements")
    used = [False] * (n + 2)
    out = []
    for i in range(1, n + 1):
        free_later = sum(1 for w in range(i + 1, n + 1) if not used[w])
        for v in range(1, n + 1):
            if used[v] or v == i:
                continue
            c = free_later - (1 if v > i else 0)
            cnt = ways(n - i, c)
            if k <= cnt:
                out.append(v)
                used[v] = True
                break
            k -= cnt
    return tuple(out)
''')

task("v6_17_lexmin_route", r'''
Write `lexmin_route(n, edges, s, t)` that picks one route through a directed multigraph and returns it as a list of edge indices.

Input: `n` is the number of vertices (vertices are 0 .. n-1), 1 <= n <= 200000. `edges` is a list or tuple of at most 400000 items; item i is a list or tuple (u, v, w): directed edge number i from u to v with weight w. 0 <= u, v < n and 0 <= w <= 10**12. Parallel edges and self-loops are allowed. `s` and `t` are the start and target vertices, 0 <= s, t < n. All of n, s, t, u, v, w must be ints (bool is not an int).

A route is a walk from s to t, written as the sequence of edge indices it uses. Choose among all routes by these rules, in order:
1. smallest total weight;
2. among those, fewest edges;
3. among those, the lexicographically smallest list of edge indices (compare the lists of ints position by position, the first difference decides).
Return that route as a list of ints. If s == t the answer is [] (the empty walk). If t cannot be reached from s return None.

Raise ValueError for any input that violates the types or ranges above (wrong container type, an item that is not a triple, a bool or non-int anywhere, a vertex out of range, a negative or too large weight, too many edges). The check applies to the whole input even when the answer would be None or [].

Details that matter:
- Rule 3 compares edge indices, not vertex numbers: two routes through different vertices are ordered by the numbers of the edges they use.
- Weights can be 0, so zero-weight cycles exist; rule 2 keeps them out of the answer.
- Weight sums can exceed 2**53, so they must be exact (no floats).

Examples:
- n=4, edges=[(0,1,5),(0,2,2),(2,1,3),(1,3,1),(2,3,6)], s=0, t=3: weight 6 is reached by 0->1->3 (edges 0, 3) and by 0->2->1->3 (edges 1, 2, 3); fewest edges picks [0, 3].
- n=2, edges=[(0,1,4),(0,1,4),(0,1,3)], s=0, t=1: [2]. With edges=[(0,1,4),(0,1,4)] the answer is [0].
- n=4, edges=[(0,2,1),(0,1,1),(2,3,1),(1,3,1)], s=0, t=3: both routes weigh 2 and use 2 edges; [0, 2] < [1, 3], so the answer is [0, 2] (the route through vertex 2).
- n=3, edges=[(0,1,0),(1,0,0),(1,2,0)], s=0, t=2: [0, 2]. With s=t=0 the answer is [].
- n=3, edges=[(0,1,1)], s=1, t=0: None.
''', r'''
import random

def brute(n, edges, s, t):
    if s == t:
        return []
    out = [[] for _ in range(n)]
    for i, (u, v, w) in enumerate(edges):
        out[u].append((i, v, w))
    best = [None]

    def dfs(u, seen, path, wt):
        if u == t:
            key = (wt, len(path), tuple(path))
            if best[0] is None or key < best[0]:
                best[0] = key
            return
        for i, v, w in out[u]:
            if v not in seen:
                seen.add(v)
                path.append(i)
                dfs(v, seen, path, wt + w)
                path.pop()
                seen.discard(v)
    dfs(s, {s}, [], 0)
    return None if best[0] is None else list(best[0][2])

def same(n, edges, s, t, exp):
    got = lexmin_route(n, edges, s, t)
    if exp is None:
        assert got is None, (n, edges, s, t, got)
    else:
        assert type(got) is list and all(type(x) is int for x in got), (n, edges, s, t, got)
        assert got == exp, (n, edges, s, t, got, exp)

def rej(*a):
    try:
        lexmin_route(*a)
    except ValueError:
        return True
    return False

E1 = [(0, 1, 5), (0, 2, 2), (2, 1, 3), (1, 3, 1), (2, 3, 6)]
same(4, E1, 0, 3, [0, 3])
same(2, [(0, 1, 4), (0, 1, 4), (0, 1, 3)], 0, 1, [2])
same(2, [(0, 1, 4), (0, 1, 4)], 0, 1, [0])
same(4, [(0, 2, 1), (0, 1, 1), (2, 3, 1), (1, 3, 1)], 0, 3, [0, 2])
same(3, [(0, 1, 0), (1, 0, 0), (1, 2, 0)], 0, 2, [0, 2])
same(3, [(0, 1, 0), (1, 0, 0), (1, 2, 0)], 0, 0, [])
same(3, [(0, 1, 1)], 1, 0, None)
same(1, [], 0, 0, [])
same(1, [(0, 0, 0)], 0, 0, [])
same(2, [], 0, 1, None)
same(2, [(1, 1, 0), (0, 0, 0), (0, 1, 7), (1, 0, 1)], 0, 1, [2])
same(2, [[0, 1, 7], [0, 1, 7]], 0, 1, [0])
# reaching t early: never continue through t
same(3, [(0, 1, 0), (1, 2, 0), (2, 1, 0)], 0, 1, [0])
# lowest first edge is a dead end or too heavy: it must not be taken
same(3, [(0, 2, 9), (0, 1, 1), (1, 2, 1), (0, 0, 0)], 0, 2, [1, 2])
same(3, [(0, 0, 0), (0, 1, 0), (1, 2, 0), (0, 2, 0)], 0, 2, [3])
# equal weight, fewer edges beats lower indices
same(3, [(0, 1, 1), (1, 2, 1), (0, 2, 2)], 0, 2, [2])
# t reachable but only through a heavier edge listed later
same(3, [(0, 1, 0), (1, 2, 5), (0, 2, 4)], 0, 2, [2])

random.seed(6017)
for _ in range(250):
    n = random.randint(1, 7)
    m = random.randint(0, 14)
    wmax = random.choice([0, 1, 2, 3])
    edges = [(random.randrange(n), random.randrange(n), random.randint(0, wmax)) for _ in range(m)]
    s = random.randrange(n)
    t = random.randrange(n)
    same(n, edges, s, t, brute(n, edges, s, t))

for _ in range(40):
    n = random.randint(2, 7)
    m = random.randint(5, 14)
    edges = [(random.randrange(n), random.randrange(n), random.choice([0, 10**12, 10**12 - 1, 5, 10**12 - 2])) for _ in range(m)]
    s = random.randrange(n)
    t = random.randrange(n)
    same(n, edges, s, t, brute(n, edges, s, t))

# long chain with a duplicate of every edge: the lower index of each pair
N = 30001
edges = []
for i in range(N - 1):
    edges.append((i, i + 1, 1))
    edges.append((i, i + 1, 1))
r = lexmin_route(N, edges, 0, N - 1)
assert r == [2 * i for i in range(N - 1)]

# skip edges of weight 2 give the same weight with half the edges
edges = [(i, i + 1, 1) for i in range(N - 1)] + [(i, i + 2, 2) for i in range(N - 2)]
r = lexmin_route(N, edges, 0, N - 1)
assert r == [N - 1 + i for i in range(0, N - 2, 2)]
r = lexmin_route(N, edges, 0, N - 2)
assert r == [0] + [N - 1 + i for i in range(1, N - 3, 2)]

# sums beyond 2**53: the cheaper edge by 1 must win
M = 10001
edges = [(i, i + 1, 10**12) for i in range(M - 1)] + [(5000, 5001, 10**12 - 1)]
r = lexmin_route(M, edges, 0, M - 1)
assert r == list(range(5000)) + [M - 1] + list(range(5001, M - 1))
edges = [(i, i + 1, 10**12) for i in range(M - 1)] + [(5000, 5001, 10**12)]
r = lexmin_route(M, edges, 0, M - 1)
assert r == list(range(M - 1))

for bad in (0, -1, 200001, True, 2.0, "3", None, [3]):
    assert rej(bad, [], 0, 0), bad
for bad in (None, {}, "ab", 5, set()):
    assert rej(3, bad, 0, 0), bad
assert rej(3, [(0, 0, 0)] * 400001, 0, 0)
for bad in ((0, 1), (0, 1, 2, 3), (0.0, 1, 1), (0, 1, 1.0), (True, 1, 1), (0, 1, True), (-1, 1, 1), (0, 3, 1),
            (3, 0, 1), (0, 1, -1), (0, 1, 10**12 + 1), ("0", 1, 1), (None, 1, 1), 7, "abc", (0, 1, None)):
    assert rej(3, [(0, 1, 1), bad], 0, 1), bad
    assert rej(3, [bad], 0, 0), bad
for bad in (-1, 3, True, 1.0, None, "0"):
    assert rej(3, [(0, 1, 1)], bad, 0), bad
    assert rej(3, [(0, 1, 1)], 0, bad), bad
assert rej(3, [(0, 1, -1)], 2, 2)
assert rej(3, [(0, 5, 1)], 0, 1)
assert rej(3, [(0, 1, 1)], 0, 3)
''', r'''
import heapq

def lexmin_route(n, edges, s, t):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not 1 <= n <= 200000:
        raise ValueError("n")
    if not isinstance(edges, (list, tuple)) or len(edges) > 400000:
        raise ValueError("edges")
    if not isint(s) or not isint(t) or not 0 <= s < n or not 0 <= t < n:
        raise ValueError("s/t")
    out = [[] for _ in range(n)]
    inc = [[] for _ in range(n)]
    for i, e in enumerate(edges):
        if not isinstance(e, (list, tuple)) or len(e) != 3:
            raise ValueError("edge")
        u, v, w = e
        if not (isint(u) and isint(v) and isint(w)) or not (0 <= u < n and 0 <= v < n and 0 <= w <= 10 ** 12):
            raise ValueError("edge")
        out[u].append((i, v, w))
        inc[v].append((u, w))
    dist = [None] * n
    dist[t] = (0, 0)
    pq = [(0, 0, t)]
    while pq:
        W, C, v = heapq.heappop(pq)
        if dist[v] != (W, C):
            continue
        for u, w in inc[v]:
            nd = (W + w, C + 1)
            if dist[u] is None or nd < dist[u]:
                dist[u] = nd
                heapq.heappush(pq, (nd[0], nd[1], u))
    if dist[s] is None:
        return None
    route = []
    u = s
    while u != t:
        W, C = dist[u]
        for i, v, w in out[u]:
            dv = dist[v]
            if dv is not None and (dv[0] + w, dv[1] + 1) == (W, C):
                route.append(i)
                u = v
                break
    return route
''')

task("v6_18_hull_peel_layers", r'''
Write `hull_peel_layers(points)` that returns how many convex-hull layers a set of integer points has.

`points` is a list or tuple of at most 2000 items; each item is a list or tuple (x, y) of two ints (bool is not an int) with |x|, |y| <= 10**9. Duplicate points are allowed. Anything else (wrong container, wrong item shape, non-int or bool coordinates, out-of-range coordinates, more than 2000 items) raises ValueError. The empty list is valid.

Peeling: let S be the current multiset of points. One round: take the convex hull of S as a closed region (a polygon, a segment or a single point). Remove from S every point that lies on the boundary of that region: hull vertices, points in the middle of a hull edge (collinear with the edge), and every duplicate copy of any such point. Then repeat on what is left until S is empty. The answer is the number of rounds, as an int; 0 for an empty list.

Details that matter:
- If all points of S are collinear (this includes all points being equal) the hull is a segment or a point, its boundary is the whole segment, and one round removes everything.
- A point lying on an edge of the hull counts as boundary even though it is not a vertex.
- A point strictly inside the hull is not removed in that round, even if it has duplicates; duplicates of a boundary point are removed together with it.
- Coordinates reach 10**9, so cross products reach about 8*10**18 and must be exact.

Examples:
- [(0,0),(2,0),(2,2),(0,2),(1,1)] -> 2 (the corners go first, then the centre).
- [(0,0),(1,1),(2,2)] -> 1 (collinear, one round).
- [(0,0),(4,0),(4,4),(0,4),(2,0),(4,2)] -> 1 (the extra points sit on hull edges).
- [(0,0),(0,0),(0,0)] -> 1.
- [(0,0),(6,0),(6,6),(0,6),(1,1),(5,1),(5,5),(1,5),(3,3),(3,3)] -> 3.
- [] -> 0.
''', r'''
import random

def cr(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

def brute(pts):
    S = list(pts)
    rounds = 0
    while S:
        U = sorted(set(S))
        if len(U) <= 2:
            return rounds + 1
        rem = set()
        for p in U:
            for q in U:
                if q == p:
                    continue
                pos = neg = False
                for r in U:
                    c = cr(p, q, r)
                    if c > 0:
                        pos = True
                    elif c < 0:
                        neg = True
                if not (pos and neg):
                    rem.add(p)
                    break
        S = [p for p in S if p not in rem]
        rounds += 1
    return rounds

def same(pts, exp):
    got = hull_peel_layers(pts)
    assert type(got) is int and got == exp, (pts, got, exp)

def rej(*a):
    try:
        hull_peel_layers(*a)
    except ValueError:
        return True
    return False

same([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1)], 2)
same([(0, 0), (1, 1), (2, 2)], 1)
same([(0, 0), (4, 0), (4, 4), (0, 4), (2, 0), (4, 2)], 1)
same([(0, 0), (0, 0), (0, 0)], 1)
same([(0, 0), (6, 0), (6, 6), (0, 6), (1, 1), (5, 1), (5, 5), (1, 5), (3, 3), (3, 3)], 3)
same([], 0)
same([(7, 7)], 1)
same([(1, 2), (1, 2), (3, 4)], 1)
same(((0, 0), (2, 0), (1, 1), (1, 1), (1, 0)), 1)
same([[0, 0], [4, 0], [0, 4], [1, 1], [1, 1], [2, 2]], 2)
# inner point on the new hull's edge, and an inner duplicated vertex
same([(0, 0), (8, 0), (8, 8), (0, 8), (2, 2), (6, 2), (6, 6), (2, 6), (4, 2), (4, 4)], 3)
same([(0, 0), (8, 0), (4, 8), (3, 1), (3, 1), (5, 1), (4, 2)], 2)
# huge coordinates, exact near-collinear tests
B = 10**9
same([(-B, -B), (B, B), (0, 1)], 1)
same([(-B, -B), (B, B), (1, 1)], 1)
same([(-B, -B), (B, B), (B, -B), (0, -1)], 2)
same([(-B, -B), (B, B), (B, -B), (0, 1)], 1)
same([(-B, -B), (B, B), (B, -B), (B - 1, B - 2)], 2)
same([(-B, -B), (B, B), (B, -B), (B - 1, B - 1)], 1)
same([(-B, B), (B, -B), (B, B - 1), (-B, -B), (1, 0), (0, 0)], 2)

random.seed(6018)
for k in range(1, 7):
    pts = [(3 * i, -2 * j) for i in range(k) for j in range(k)]
    random.shuffle(pts)
    same(pts, (k + 1) // 2)
    same(pts + pts[:5], (k + 1) // 2)
    if k <= 3:
        assert brute(pts) == (k + 1) // 2
pts = [(i, j) for i in range(30) for j in range(30)]
pts = pts + pts[::7]
random.shuffle(pts)
same(pts, 15)
same([(i, 0) for i in range(30)] * 2, 1)

pts = []
for i in range(40):
    h = B - 7 * i
    pts += [(h, h), (-h, h), (h, -h), (-h, -h)]
    if i % 3 == 0:
        pts.append((0, h))
    if i % 4 == 1:
        pts.append((h, h))
random.shuffle(pts)
same(pts, 40)

for _ in range(120):
    n = random.randint(0, 12)
    mode = random.randint(0, 2)
    if mode == 0:
        pts = [(random.randint(0, 3), random.randint(0, 3)) for _ in range(n)]
    elif mode == 1:
        pts = [(random.randint(-6, 6), random.randint(-6, 6)) for _ in range(n)]
    else:
        pts = [(random.choice([-B, -B + 1, 0, 1, B - 1, B]), random.choice([-B, -B + 1, 0, 1, B - 1, B])) for _ in range(n)]
    if random.random() < 0.3:
        pts = [random.choice([list, tuple])(p) for p in pts]
    same(pts, brute([tuple(p) for p in pts]))

for _ in range(15):
    n = random.randint(20, 40)
    pts = [(random.randint(-30, 30), random.randint(-30, 30)) for _ in range(n)]
    same(pts, brute(pts))

for bad in (None, 5, "ab", {(1, 2)}, {}):
    assert rej(bad), bad
assert rej([(0, 0)] * 2001)
for bad in ((1,), (1, 2, 3), (1.0, 2), (1, 2.0), (True, 2), (1, False), (B + 1, 0), (0, -B - 1), ("1", 2), (None, 2), 5, "ab", None, (10**30, 0)):
    assert rej([(0, 0), bad]), bad
    assert rej([bad]), bad
same([(B, B), (-B, -B)] * 1000, 1)
''', r'''
def hull_peel_layers(points):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(points, (list, tuple)) or len(points) > 2000:
        raise ValueError("points")
    cur = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("item")
        x, y = p
        if not isint(x) or not isint(y) or abs(x) > 10 ** 9 or abs(y) > 10 ** 9:
            raise ValueError("coordinate")
        cur.append((x, y))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    rounds = 0
    while cur:
        rounds += 1
        U = sorted(set(cur))
        if len(U) <= 2:
            break
        lower = []
        for p in U:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper = []
        for p in reversed(U):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            break
        sides = list(zip(hull, hull[1:] + hull[:1]))
        gone = set()
        for p in U:
            for a, b in sides:
                if (cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])):
                    gone.add(p)
                    break
        cur = [p for p in cur if p not in gone]
    return rounds
''')

task("v6_19_weight_runs", r'''
Write `weight_runs(items)` that sweeps weighted half-open integer intervals and reports the stretches of constant non-zero total weight.

`items` is a list or tuple of at most 200000 triples (a, b, w) (lists or tuples). An item means: weight w is added at every integer position p with a <= p < b. a, b, w are ints (bool is not an int) with |a|, |b| <= 10**18 and |w| <= 10**9; w may be negative or zero. b < a raises ValueError; b == a is allowed and is an empty interval that contributes nothing. Any other violation (wrong container, an item that is not a triple, bool or non-int values, out-of-range values, too many items) also raises ValueError. The empty list is valid.

For every integer position p let total(p) be the sum of w over the items covering p. Return a list of triples (lo, hi, c) of ints, in increasing order of lo, that describes exactly the positions where total(p) != 0:
- every position p with lo <= p < hi has total(p) == c, and c != 0;
- the runs are maximal: a run is never directly followed by another run that starts at its hi and has the same c (touching runs with equal c must be one run), and no position with total(p) != 0 is left out.
Positions with total 0 are not reported, so a gap, or a stretch where the weights cancel, separates runs. The result is [] if no position has a non-zero total.

Details that matter:
- Events of different items at the same position must be combined before deciding whether the total changes there: an item ending at p and another starting at p with the same weight leave the total unchanged, so no boundary appears at p.
- Positions can be as large as 10**18 in magnitude, so a solution must not iterate over positions.
- Totals can be negative; a run may have a negative c.

Examples:
- [(0,3,1),(1,5,1)] -> [(0,1,1),(1,3,2),(3,5,1)]
- [(0,2,1),(2,4,1)] -> [(0,4,1)]  (touching, equal weight: one run)
- [(0,4,2),(0,2,3),(2,4,3)] -> [(0,4,5)]  (the events at 2 cancel out)
- [(0,4,2),(2,6,-2)] -> [(0,2,2),(4,6,-2)]  (the total is 0 on positions 2 and 3, which is not reported)
- [(1,1,5),(0,2,1),(3,3,-4)] -> [(0,2,1)]  (empty intervals do nothing)
- [(0,5,0)] -> []
''', r'''
import random
from bisect import bisect_right

def brute(items, lo=-6, hi=14):
    tot = []
    for p in range(lo, hi):
        tot.append(sum(w for a, b, w in items if a <= p < b))
    runs = []
    i = 0
    while i < len(tot):
        if tot[i] == 0:
            i += 1
            continue
        j = i
        while j < len(tot) and tot[j] == tot[i]:
            j += 1
        runs.append((lo + i, lo + j, tot[i]))
        i = j
    return runs

def same(items, exp):
    got = weight_runs(items)
    assert type(got) is list and all(type(r) is tuple and len(r) == 3 and all(type(v) is int for v in r) for r in got), (items, got)
    assert got == exp, (items, got, exp)

def rej(*a):
    try:
        weight_runs(*a)
    except ValueError:
        return True
    return False

same([(0, 3, 1), (1, 5, 1)], [(0, 1, 1), (1, 3, 2), (3, 5, 1)])
same([(0, 2, 1), (2, 4, 1)], [(0, 4, 1)])
same([(0, 4, 2), (0, 2, 3), (2, 4, 3)], [(0, 4, 5)])
same([(0, 4, 2), (2, 6, -2)], [(0, 2, 2), (4, 6, -2)])
same([(1, 1, 5), (0, 2, 1), (3, 3, -4)], [(0, 2, 1)])
same([(0, 5, 0)], [])
same([], [])
same(((0, 1, 1), [1, 2, 1], (2, 3, 1)), [(0, 3, 1)])
same([(0, 3, 1), (0, 3, -1)], [])
same([(0, 3, 1), (3, 6, -1)], [(0, 3, 1), (3, 6, -1)])
same([(0, 6, 1), (2, 4, -1), (3, 5, 1)], [(0, 2, 1), (3, 4, 1), (4, 5, 2), (5, 6, 1)])
same([(5, 7, 2), (0, 2, 2), (2, 5, 2)], [(0, 7, 2)])
same([(0, 2, 1), (0, 2, 1), (2, 4, 2)], [(0, 4, 2)])
same([(-10**18, 10**18, 1)], [(-10**18, 10**18, 1)])
same([(-10**18, 0, 7), (0, 10**18, 7), (5, 5, 3)], [(-10**18, 10**18, 7)])
same([(-10**18, 10**18, 5 * 10**8), (-10**18, 10**18, 5 * 10**8), (0, 1, -10**9)], [(-10**18, 0, 10**9), (1, 10**18, 10**9)])
same([(3, 4, 1), (3, 4, 1), (3, 4, -2)], [])

random.seed(6019)
for _ in range(300):
    m = random.randint(0, 9)
    items = []
    for _ in range(m):
        a = random.randint(-3, 9)
        b = random.randint(a, 11) if random.random() < 0.9 else a
        items.append((a, b, random.randint(-3, 3)))
    same(items, brute(items))

for _ in range(40):
    m = random.randint(5, 12)
    items = []
    for _ in range(m):
        a = random.randint(-3, 9)
        b = random.randint(a, 11)
        w = random.choice([-2, -1, 1, 2])
        items.append((a, b, w))
        if random.random() < 0.5:
            items.append((b, b + random.randint(0, 2), w))
    random.shuffle(items)
    same(items, brute(items, -6, 20))

# large positions: structural checks plus probes against direct summation
for _ in range(6):
    m = 1500
    pool = [random.randint(-10**18, 10**18) for _ in range(120)] + [-10**18, 10**18, 0]
    items = []
    for _ in range(m):
        a = random.choice(pool)
        b = random.choice(pool)
        if a > b:
            a, b = b, a
        items.append((a, b, random.randint(-10**9, 10**9) if random.random() < 0.5 else random.choice([-1, 1, 2, -2])))
    got = weight_runs(items)
    prev = None
    for lo, hi, c in got:
        assert type(lo) is int and type(hi) is int and type(c) is int
        assert lo < hi and c != 0
        if prev is not None:
            assert prev[1] <= lo
            assert not (prev[1] == lo and prev[2] == c)
        prev = (lo, hi, c)
    assert sum((hi - lo) * c for lo, hi, c in got) == sum((b - a) * w for a, b, w in items)
    los = [r[0] for r in got]
    probes = random.sample(pool, 30) + [random.randint(-10**18, 10**18) for _ in range(10)]
    probes += [p - 1 for p in probes[:20]] + [p + 1 for p in probes[:20]]
    for p in probes:
        direct = sum(w for a, b, w in items if a <= p < b)
        i = bisect_right(los, p) - 1
        inside = i >= 0 and got[i][0] <= p < got[i][1]
        assert (got[i][2] if inside else 0) == direct, (p, direct)

# a staircase of 3000 touching unit steps with equal weight collapses to one run
items = [(i * 10**14, (i + 1) * 10**14, 3) for i in range(-1500, 1500)]
random.shuffle(items)
same(items, [(-1500 * 10**14, 1500 * 10**14, 3)])
items = [(i, i + 2, 1) for i in range(0, 4000, 2)] + [(i, i + 1, 1) for i in range(1, 4000, 2)]
same(items, [(p, p + 1, 1 if p % 2 == 0 else 2) for p in range(4000)])

for bad in (None, 5, "ab", {}, {(0, 1, 1)}):
    assert rej(bad), bad
assert rej([(0, 0, 0)] * 200001)
for bad in ((1, 0, 1), (5, -5, 1), (0, 1), (0, 1, 1, 1), (0.0, 1, 1), (0, 1.0, 1), (0, 1, 1.0), (True, 2, 1), (0, True, 1),
            (0, 1, True), (-10**18 - 1, 0, 1), (0, 10**18 + 1, 1), (0, 1, 10**9 + 1), (0, 1, -10**9 - 1), ("0", 1, 1),
            (None, 1, 1), 7, "abc", None, (0, 1, None)):
    assert rej([(0, 5, 1), bad]), bad
    assert rej([bad]), bad
same([(-10**18, -10**18, 10**9), (10**18, 10**18, -10**9)], [])
''', r'''
def weight_runs(items):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(items, (list, tuple)) or len(items) > 200000:
        raise ValueError("items")
    ev = {}
    for it in items:
        if not isinstance(it, (list, tuple)) or len(it) != 3:
            raise ValueError("item")
        a, b, w = it
        if not (isint(a) and isint(b) and isint(w)):
            raise ValueError("type")
        if abs(a) > 10 ** 18 or abs(b) > 10 ** 18 or abs(w) > 10 ** 9 or b < a:
            raise ValueError("range")
        if a < b and w:
            ev[a] = ev.get(a, 0) + w
            ev[b] = ev.get(b, 0) - w
    ks = sorted(k for k in ev if ev[k])
    out = []
    cur = 0
    for i, p in enumerate(ks):
        cur += ev[p]
        if cur:
            out.append((p, ks[i + 1], cur))
    return out
''')

task("v6_20_circ_exact_count", r'''
Write `circ_exact_count(a, queries)` that answers queries about windows of a circular array.

`a` is a list or tuple of ints (bool is not an int), 1 <= len(a) <= 3000, each |a[i]| <= 10**9. Let n = len(a). `queries` is a list or tuple of at most 3000 items; each item is a list or tuple (l, r, k) of three ints with 0 <= l < n, 0 <= r < n, 1 <= k <= n. Anything else raises ValueError (wrong container types, empty `a`, wrong item shape, non-int or bool values, out-of-range values, too many queries). An empty `queries` is valid and gives [].

The window of a query (l, r, k) is the run of positions that starts at index l and walks forward, wrapping from index n-1 to index 0, until it has visited index r (inclusive):
- if l <= r the window is a[l], a[l+1], ..., a[r] (length r - l + 1);
- if l > r the window is a[l], ..., a[n-1], a[0], ..., a[r] (length n - l + r + 1).
So l == r is a single element, while l == r + 1 (which has l > r) is the whole array, read starting at index l, with length n. A position never appears twice in a window.

The answer to a query is the number of distinct values that occur exactly k times in its window. A value occurring 2 times in the window is counted when k == 2 and not when k == 1 or k == 3; values that do not occur in the window are never counted. Return a list of ints, one per query, in query order.

Examples (a = [1, 2, 1, 2, 3], n = 5):
- (0, 4, 2) -> 2 (window 1 2 1 2 3: the values 1 and 2 each occur twice)
- (4, 1, 2) -> 0 (window 3 1 2, it wraps: every value occurs once)
- (4, 1, 1) -> 3
- (3, 2, 2) -> 2 (l = r + 1: the whole array read from index 3: 2 3 1 2 1)
- (2, 2, 1) -> 1 (a single element)
- (1, 3, 1) -> 1 (window 2 1 2: only the value 1 occurs exactly once)
''', r'''
import random

def brute(a, queries):
    n = len(a)
    res = []
    for l, r, k in queries:
        pos = []
        i = l
        while True:
            pos.append(i)
            if i == r:
                break
            i = (i + 1) % n
        cnt = 0
        for v in set(a[i] for i in pos):
            if sum(1 for i in pos if a[i] == v) == k:
                cnt += 1
        res.append(cnt)
    return res

def same(a, qs, exp):
    got = circ_exact_count(a, qs)
    assert type(got) is list and all(type(x) is int for x in got), (a, qs, got)
    assert got == exp, (a, qs, got, exp)

def rej(*x):
    try:
        circ_exact_count(*x)
    except ValueError:
        return True
    return False

A = [1, 2, 1, 2, 3]
same(A, [(0, 4, 2), (4, 1, 2), (4, 1, 1), (3, 2, 2), (2, 2, 1), (1, 3, 1)], [2, 0, 3, 2, 1, 1])
same(A, [(0, 4, 3), (0, 0, 2), (0, 0, 1), (2, 1, 2), (2, 1, 1), (1, 0, 2)], [0, 0, 1, 2, 1, 2])
same(A, [], [])
same([7], [(0, 0, 1)], [1])
same([7], [[0, 0, 1]], [1])
same((7,), ((0, 0, 1),), [1])
same([5, 5], [(0, 1, 2), (1, 0, 2), (0, 0, 2), (0, 0, 1), (1, 1, 1)], [1, 1, 0, 1, 1])
same([4, 4, 4, 4], [(1, 0, 4), (2, 0, 3), (3, 0, 2), (0, 3, 4), (1, 3, 3), (0, 3, 3)], [1, 1, 1, 1, 1, 0])
same([-1, 1, -1, 0, 0, 10**9, -10**9], [(5, 4, 2), (6, 3, 2), (3, 4, 2), (5, 6, 1), (6, 0, 1)], [2, 1, 1, 2, 2])

random.seed(6020)
for _ in range(120):
    n = random.randint(1, 12)
    vals = random.choice([2, 3, 5, 100])
    a = [random.randint(-vals, vals) for _ in range(n)]
    qs = [(random.randrange(n), random.randrange(n), random.randint(1, n)) for _ in range(30)]
    qs += [(l, (l - 1) % n, random.randint(1, min(n, 4))) for l in range(n)]
    qs += [(l, l, 1) for l in range(n)]
    same(a, qs, brute(a, qs))

# larger inputs, structural properties
n = 3000
a = list(range(n))
random.shuffle(a)
qs = [(random.randrange(n), random.randrange(n), 1) for _ in range(300)]
exp = [(r - l + 1) if l <= r else (n - l + r + 1) for l, r, k in qs]
same(a, qs, exp)
same(a, [(l, r, 2) for l, r, k in qs[:50]], [0] * 50)
a = [7] * n
qs = [(random.randrange(n), random.randrange(n), random.randint(1, n)) for _ in range(300)]
exp = [1 if ((r - l + 1) if l <= r else (n - l + r + 1)) == k else 0 for l, r, k in qs]
same(a, qs, exp)
a = [i % 3 for i in range(n)]
qs = [(0, n - 1, 1000), (0, n - 1, 999), (5, 4, 1000), (5, 3, 1000), (5, 3, 999), (5, 3, 1001)]
same(a, qs, [3, 0, 3, 2, 1, 0])

n = 1500
a = [random.randint(0, 30) for _ in range(n)]
qs = [(random.randrange(n), random.randrange(n), random.randint(1, 80)) for _ in range(120)]
exp = []
for l, r, k in qs:
    idx = range(l, r + 1) if l <= r else list(range(l, n)) + list(range(0, r + 1))
    cnt = 0
    for v in range(31):
        c = 0
        for i in idx:
            if a[i] == v:
                c += 1
        cnt += c == k
    exp.append(cnt)
same(a, qs, exp)

for bad in (None, [], (), 5, "abc", {1: 2}):
    assert rej(bad, []), bad
for bad in ([1.0, 2], [True, 2], ["1", 2], [None], [10**9 + 1], [-10**9 - 1], [[1], 2]):
    assert rej(bad, []), bad
    assert rej(bad, [(0, 0, 1)]), bad
for bad in (None, 5, "abc", {(0, 0, 1)}, {}):
    assert rej([1, 2, 3], bad), bad
assert rej([1], [(0, 0, 1)] * 3001)
for bad in ((0, 0), (0, 0, 1, 1), (0.0, 0, 1), (0, 0.0, 1), (0, 0, 1.0), (True, 0, 1), (0, True, 1), (0, 0, True), (-1, 0, 1),
            (0, -1, 1), (3, 0, 1), (0, 3, 1), (0, 0, 0), (0, 0, 4), (0, 0, -1), ("0", 0, 1), (None, 0, 1), 5, "abc", None):
    assert rej([1, 2, 3], [(0, 0, 1), bad]), bad
    assert rej([1, 2, 3], [bad]), bad
same([1, 2, 3], [(2, 1, 3)], [0])
same([1, 2, 3], [(2, 1, 1)], [3])
''', r'''
def circ_exact_count(a, queries):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(a, (list, tuple)) or not 1 <= len(a) <= 3000:
        raise ValueError("a")
    for v in a:
        if not isint(v) or abs(v) > 10 ** 9:
            raise ValueError("value")
    if not isinstance(queries, (list, tuple)) or len(queries) > 3000:
        raise ValueError("queries")
    n = len(a)
    doubled = list(a) + list(a)
    res = []
    for q in queries:
        if not isinstance(q, (list, tuple)) or len(q) != 3:
            raise ValueError("query")
        l, r, k = q
        if not (isint(l) and isint(r) and isint(k)) or not (0 <= l < n and 0 <= r < n and 1 <= k <= n):
            raise ValueError("query")
        length = r - l + 1 if l <= r else n - l + r + 1
        cnt = {}
        for v in doubled[l:l + length]:
            cnt[v] = cnt.get(v, 0) + 1
        res.append(sum(1 for c in cnt.values() if c == k))
    return res
''')

task("v6_21_staircase_log", r'''
Write `staircase_log(points)` that processes points one at a time and tracks which ones are not dominated.

`points` is a list or tuple of at most 200000 items, each a list or tuple (x, y) of two ints (bool is not an int) with |x|, |y| <= 10**18. Anything else raises ValueError. The empty list is valid.

Point p dominates point q when p != q, p.x >= q.x and p.y >= q.y. So a point never dominates an identical copy of itself, and a point with the same x and a larger y does dominate.

Return a tuple (flags, front):
- flags is a list of bools, one per input point: flags[i] is True exactly when no point with an index smaller than i dominates points[i] (later points are irrelevant for flags[i]);
- front is a list of tuples (x, y): the distinct points that no point of the whole input dominates, sorted by x ascending (they then have strictly decreasing y).

Details that matter:
- A repeat of a point that is currently undominated gets True (it is not dominated by itself); a repeat of a point that is already dominated by an earlier point gets False.
- A new point can dominate several earlier points; those earlier points keep their flags (a flag describes the moment of insertion), but they are not in front.
- Coordinates reach 10**18; use exact integer comparisons.
- Each front entry is a tuple, even when the input items are lists.

Examples:
- [(1,1),(2,2),(1,1),(3,0),(0,5),(2,2)] -> ([True, True, False, True, True, True], [(0,5),(2,2),(3,0)])
- [] -> ([], [])
- [(5,5),(5,5),(5,5)] -> ([True, True, True], [(5,5)])
- [(1,1),(1,2),(1,2),(1,1)] -> ([True, True, True, False], [(1,2)])
- [(0,0),(1,1),(2,2),(3,3)] -> ([True, True, True, True], [(3,3)])
- [(3,3),(2,2),(1,1)] -> ([True, False, False], [(3,3)])
''', r'''
import random
from bisect import bisect_left

def dom(p, q):
    return p != q and p[0] >= q[0] and p[1] >= q[1]

def brute(pts):
    pts = [tuple(p) for p in pts]
    flags = [not any(dom(pts[j], pts[i]) for j in range(i)) for i in range(len(pts))]
    front = sorted(set(p for p in pts if not any(dom(q, p) for q in pts)))
    return flags, front

def same(pts, exp):
    got = staircase_log(pts)
    assert type(got) is tuple and len(got) == 2, (pts, got)
    fl, fr = got
    assert type(fl) is list and all(type(f) is bool for f in fl), (pts, got)
    assert type(fr) is list and all(type(p) is tuple and len(p) == 2 and type(p[0]) is int and type(p[1]) is int for p in fr), (pts, got)
    assert got == exp, (pts, got, exp)

def rej(*a):
    try:
        staircase_log(*a)
    except ValueError:
        return True
    return False

same([(1, 1), (2, 2), (1, 1), (3, 0), (0, 5), (2, 2)], ([True, True, False, True, True, True], [(0, 5), (2, 2), (3, 0)]))
same([], ([], []))
same([(5, 5), (5, 5), (5, 5)], ([True, True, True], [(5, 5)]))
same([(1, 1), (1, 2), (1, 2), (1, 1)], ([True, True, True, False], [(1, 2)]))
same([(0, 0), (1, 1), (2, 2), (3, 3)], ([True] * 4, [(3, 3)]))
same([(3, 3), (2, 2), (1, 1)], ([True, False, False], [(3, 3)]))
same([[0, 3], [1, 2], [2, 1], [3, 0]], ([True] * 4, [(0, 3), (1, 2), (2, 1), (3, 0)]))
same(((2, 1), (2, 1)), ([True, True], [(2, 1)]))
same([(2, 1), (2, 2), (2, 1), (2, 2)], ([True, True, False, True], [(2, 2)]))
same([(1, 3), (2, 3)], ([True, True], [(2, 3)]))
same([(2, 3), (1, 3)], ([True, False], [(2, 3)]))
same([(0, 9), (9, 0), (4, 4), (5, 5), (3, 6), (6, 3), (5, 5)], ([True, True, True, True, True, True, True], [(0, 9), (3, 6), (5, 5), (6, 3), (9, 0)]))
same([(0, 9), (9, 0), (4, 4), (5, 5), (4, 6), (6, 3), (4, 4)], ([True, True, True, True, True, True, False], [(0, 9), (4, 6), (5, 5), (6, 3), (9, 0)]))
same([(-10**18, 10**18), (10**18, -10**18), (10**18, 10**18)], ([True, True, True], [(10**18, 10**18)]))
same([(10**18, 10**18 - 1), (10**18 - 1, 10**18), (10**18 - 1, 10**18 - 1), (10**18, 10**18 - 1)], ([True, True, False, True], [(10**18 - 1, 10**18), (10**18, 10**18 - 1)]))
same([(-5, -5), (-5, -6), (-6, -5), (-4, -6)], ([True, False, False, True], [(-5, -5), (-4, -6)]))

random.seed(6021)
for _ in range(200):
    n = random.randint(0, 25)
    c = random.choice([2, 4, 6])
    pts = [(random.randint(-c, c), random.randint(-c, c)) for _ in range(n)]
    if random.random() < 0.3:
        pts = [random.choice([list, tuple])(p) for p in pts]
    same(pts, brute(pts))

for _ in range(10):
    n = 40
    pts = [(random.randint(-10**18, 10**18), random.randint(-10**18, 10**18)) for _ in range(n)]
    pts += [random.choice(pts) for _ in range(10)]
    same(pts, brute(pts))

# big inputs: structure checks that do not run the quadratic oracle
N = 20000
pts = [(random.randint(-10**18, 10**18), random.randint(-10**18, 10**18)) for _ in range(N)]
fl, fr = staircase_log(pts)
assert len(fl) == N and fr == sorted(fr)
assert all(fr[i][1] > fr[i + 1][1] for i in range(len(fr) - 1))
S = set(pts)
assert all(p in S for p in fr)
xs = [p[0] for p in fr]
for p in pts:
    i = bisect_left(xs, p[0])
    assert i < len(fr) and fr[i][1] >= p[1], p
for f in fr:
    assert not any(dom(q, f) for q in pts)
for i in random.sample(range(N), 12):
    assert fl[i] == (not any(dom(pts[j], pts[i]) for j in range(i))), i
for i in range(0, 60):
    assert fl[i] == (not any(dom(pts[j], pts[i]) for j in range(i)))

M = 6000
anti = [(10**17 + i, 10**17 - i) for i in range(M)]
same(anti, ([True] * M, anti))
same(anti[::-1], ([True] * M, anti))
chain = [(i, i) for i in range(M)]
same(chain, ([True] * M, [(M - 1, M - 1)]))
same(chain[::-1], ([True] + [False] * (M - 1), [(M - 1, M - 1)]))
mix = chain + [(M, -5)] + chain[::-1]
same(mix, ([True] * M + [True, True] + [False] * (M - 1), [(M - 1, M - 1), (M, -5)]))
same(anti + anti, ([True] * M + [True] * M, anti))
same([(i, 0) for i in range(M)], ([True] * M, [(M - 1, 0)]))
same([(0, i) for i in range(M)], ([True] * M, [(0, M - 1)]))
same([(M - i, 0) for i in range(M)], ([True] + [False] * (M - 1), [(M, 0)]))

for bad in (None, 5, "ab", {(1, 2)}, {}):
    assert rej(bad), bad
assert rej([(0, 0)] * 200001)
for bad in ((1,), (1, 2, 3), (1.0, 2), (1, 2.0), (True, 2), (1, False), (10**18 + 1, 0), (0, -10**18 - 1), ("1", 2),
            (None, 2), 5, "ab", None, (10**30, 0)):
    assert rej([(0, 0), bad]), bad
    assert rej([bad]), bad
same([(10**18, -10**18), (-10**18, 10**18)], ([True, True], [(-10**18, 10**18), (10**18, -10**18)]))
''', r'''
from bisect import bisect_left

def staircase_log(points):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(points, (list, tuple)) or len(points) > 200000:
        raise ValueError("points")
    pts = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("item")
        x, y = p
        if not isint(x) or not isint(y) or abs(x) > 10 ** 18 or abs(y) > 10 ** 18:
            raise ValueError("coordinate")
        pts.append((x, y))
    xs = []
    ys = []
    flags = []
    for x, y in pts:
        i = bisect_left(xs, x)
        if i < len(xs) and ys[i] >= y:
            flags.append(xs[i] == x and ys[i] == y)
            continue
        flags.append(True)
        j = i
        while j > 0 and ys[j - 1] <= y:
            j -= 1
        k = i + 1 if i < len(xs) and xs[i] == x else i
        xs[j:k] = [x]
        ys[j:k] = [y]
    return flags, list(zip(xs, ys))
''')

task("v6_22_segment_pair_kinds", r'''
Write `segment_pair_kinds(segs)` that classifies how every pair of line segments meets and returns the three counts.

`segs` is a list or tuple of at most 2000 items; each item is a list or tuple (x1, y1, x2, y2) of four ints (bool is not an int) with every |coordinate| <= 10**9. A segment is the closed set of points between (x1, y1) and (x2, y2), endpoints included. The two endpoints may coincide: that segment is a single point. Any violation of these rules raises ValueError; the empty list is valid.

For every pair of items i < j let I be the intersection of the two closed segments. Count the pair in exactly one of three categories:
- "cross": I is exactly one point and that point is not an endpoint of either segment (it lies strictly inside both);
- "touch": I is exactly one point and that point is an endpoint of at least one of the two segments (a shared endpoint, a T-junction, a point segment lying on the other segment, two equal point segments, or two collinear segments that only meet end to end);
- "overlap": I contains more than one point (it is then a segment of positive length; both segments are collinear and non-degenerate).
Pairs whose intersection is empty are not counted. Return the tuple (cross, touch, overlap) of three ints.

Details that matter:
- Identical segments, or the same segment written in the opposite direction, form an "overlap" pair; two identical point segments form a "touch" pair.
- Collinear segments separated by a gap do not intersect, even though their lines do.
- The crossing point of two "cross" segments need not have integer coordinates; it still counts as "cross".
- Coordinates reach 10**9, so cross products reach about 8*10**18 and must be computed exactly (no floating point).

Examples:
- [(0,0,4,4),(0,4,4,0)] -> (1, 0, 0)
- [(0,0,4,0),(2,0,2,3)] -> (0, 1, 0)  (the second one ends on the first)
- [(0,0,2,0),(2,0,5,0)] -> (0, 1, 0)  (collinear, meeting end to end)
- [(0,0,4,0),(2,0,6,0)] -> (0, 0, 1)
- [(0,0,1,0),(2,0,3,0),(1,1,1,1)] -> (0, 0, 0)
- [(1,1,1,1),(0,0,2,2),(2,2,0,0)] -> (0, 2, 1)
''', r'''
import random

def orient(o, a, b):
    v = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    return (v > 0) - (v < 0)

def onseg(p, a, b):
    return orient(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])

def kind(s, t):
    p1, p2 = (s[0], s[1]), (s[2], s[3])
    q1, q2 = (t[0], t[1]), (t[2], t[3])
    d1 = orient(q1, q2, p1)
    d2 = orient(q1, q2, p2)
    d3 = orient(p1, p2, q1)
    d4 = orient(p1, p2, q2)
    hit = (d1 * d2 < 0 and d3 * d4 < 0) or onseg(p1, q1, q2) or onseg(p2, q1, q2) or onseg(q1, p1, p2) or onseg(q2, p1, p2)
    if not hit:
        return None
    if d1 * d2 < 0 and d3 * d4 < 0:
        return "cross"
    if d1 == d2 == d3 == d4 == 0 and p1 != p2 and q1 != q2:
        xo = min(max(p1[0], p2[0]), max(q1[0], q2[0])) - max(min(p1[0], p2[0]), min(q1[0], q2[0]))
        yo = min(max(p1[1], p2[1]), max(q1[1], q2[1])) - max(min(p1[1], p2[1]), min(q1[1], q2[1]))
        if xo > 0 or yo > 0:
            return "overlap"
    return "touch"

def brute(segs):
    c = {"cross": 0, "touch": 0, "overlap": 0}
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            k = kind(segs[i], segs[j])
            if k:
                c[k] += 1
    return (c["cross"], c["touch"], c["overlap"])

def same(segs, exp):
    got = segment_pair_kinds(segs)
    assert type(got) is tuple and len(got) == 3 and all(type(v) is int for v in got), (segs, got)
    assert got == exp, (segs, got, exp)

def rej(*a):
    try:
        segment_pair_kinds(*a)
    except ValueError:
        return True
    return False

same([(0, 0, 4, 4), (0, 4, 4, 0)], (1, 0, 0))
same([(0, 0, 4, 0), (2, 0, 2, 3)], (0, 1, 0))
same([(0, 0, 2, 0), (2, 0, 5, 0)], (0, 1, 0))
same([(0, 0, 4, 0), (2, 0, 6, 0)], (0, 0, 1))
same([(0, 0, 1, 0), (2, 0, 3, 0), (1, 1, 1, 1)], (0, 0, 0))
same([(1, 1, 1, 1), (0, 0, 2, 2), (2, 2, 0, 0)], (0, 2, 1))
same([], (0, 0, 0))
same([(0, 0, 1, 1)], (0, 0, 0))
same([(3, 3, 3, 3), (3, 3, 3, 3)], (0, 1, 0))
same([(3, 3, 3, 3), (3, 3, 3, 3), (3, 3, 3, 3)], (0, 3, 0))
same([(0, 0, 5, 5), (5, 5, 0, 0)], (0, 0, 1))
same([(0, 0, 5, 5), (0, 0, 5, 5), (5, 5, 0, 0)], (0, 0, 3))
same([(0, 0, 3, 0), (0, 0, 0, 3)], (0, 1, 0))
same([(0, 0, 4, 0), (4, 0, 4, 4), (4, 4, 0, 4), (0, 4, 0, 0)], (0, 4, 0))
same([(0, 0, 4, 0), (1, 0, 3, 0)], (0, 0, 1))
same([[0, 0, 4, 0], (0, 1, 4, 1)], (0, 0, 0))
same([(0, 0, 3, 3), (1, 2, 2, 1)], (1, 0, 0))
same([(0, 0, 3, 3), (0, 3, 3, 0)], (1, 0, 0))
same([(0, 0, 2, 1), (0, 1, 2, 0)], (1, 0, 0))
same([(0, 0, 4, 0), (5, 0, 6, 0), (7, 0, 7, 0)], (0, 0, 0))
same([(0, 0, 4, 4), (2, 2, 2, 2), (5, 5, 5, 5), (1, 1, 1, 2)], (0, 2, 0))
same([(0, 0, 4, 0), (2, 1, 2, 5), (2, -3, 2, 0)], (0, 1, 0))
same([(0, 0, 4, 0), (2, -3, 2, 5)], (1, 0, 0))
B = 10**9
same([(-B, -B, B, B), (-B, B, B, -B)], (1, 0, 0))
same([(-B, -B, B, B - 1), (-B, B, B, -B)], (1, 0, 0))
same([(-B, -B, B, B - 1), (B - 1, B, B, B - 1)], (0, 1, 0))
same([(-B, -B, B, B), (B, B, B, -B), (B, -B, -B, -B)], (0, 3, 0))
same([(-B, 0, B, 0), (B, 0, -B, 0), (0, 0, 0, 0)], (0, 2, 1))

random.seed(6022)
for _ in range(60):
    n = random.randint(0, 14)
    c = random.choice([2, 3, 5])
    segs = []
    for _ in range(n):
        if random.random() < 0.1:
            x, y = random.randint(0, c), random.randint(0, c)
            segs.append((x, y, x, y))
        else:
            segs.append((random.randint(0, c), random.randint(0, c), random.randint(0, c), random.randint(0, c)))
    if segs and random.random() < 0.3:
        segs.append(random.choice(segs))
    if random.random() < 0.3:
        segs = [random.choice([list, tuple])(s) for s in segs]
    same(segs, brute(segs))

for _ in range(10):
    segs = []
    for _ in range(22):
        segs.append(tuple(random.choice([-B, -B + 1, -1, 0, 1, B - 1, B]) for _ in range(4)))
    same(segs, brute(segs))

for _ in range(4):
    segs = [tuple(random.randint(-20, 20) for _ in range(4)) for _ in range(60)]
    same(segs, brute(segs))

# collinear structures along the x axis at huge scale
n = 120
S = 5 * 10**6
segs = [(i * S, 0, (i + 1) * S, 0) for i in range(n)]
random.shuffle(segs)
same(segs, (0, n - 1, 0))
segs = [(i * S, B - 5, (i + 2) * S, B - 5) for i in range(n)]
same(segs, (0, n - 2, n - 1))
segs = [((i + 2) * S, B - 5, i * S, B - 5) for i in range(n)]
same(segs, (0, n - 2, n - 1))
segs = [(-(i + 1), -(B - i), i + 1, B - i) for i in range(50)]
same(segs, (50 * 49 // 2, 0, 0))
segs = [(-(i + 1), -(B - i), i + 1, B - i) for i in range(50)] + [(0, 0, 0, 0)]
same(segs, (50 * 49 // 2, 50, 0))
segs = [(0, 0, 0, 0)] * 60
same(segs, (0, 60 * 59 // 2, 0))
segs = [(0, 0, B, B)] * 40 + [(B, B, 0, 0)] * 40
same(segs, (0, 0, 80 * 79 // 2))
segs = [(0, 0, B, B - 1), (0, 0, B - 1, B), (B, B - 1, B - 1, B)]
same(segs, (0, 3, 0))

for bad in (None, 5, "ab", {}, {(0, 0, 1, 1)}):
    assert rej(bad), bad
assert rej([(0, 0, 0, 0)] * 2001)
for bad in ((1, 2, 3), (1, 2, 3, 4, 5), (1.0, 2, 3, 4), (1, 2, 3.0, 4), (True, 2, 3, 4), (1, 2, 3, False), (B + 1, 0, 0, 0),
            (0, 0, 0, -B - 1), ("1", 2, 3, 4), (None, 2, 3, 4), 5, "abcd", None, (10**30, 0, 0, 0), ((0, 0), (1, 1))):
    assert rej([(0, 0, 1, 1), bad]), bad
    assert rej([bad]), bad
''', r'''
def segment_pair_kinds(segs):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(segs, (list, tuple)) or len(segs) > 2000:
        raise ValueError("segs")
    S = []
    for it in segs:
        if not isinstance(it, (list, tuple)) or len(it) != 4:
            raise ValueError("item")
        for v in it:
            if not isint(v) or abs(v) > 10 ** 9:
                raise ValueError("coordinate")
        S.append(tuple(it))

    def on_seg(px, py, s):
        x1, y1, x2, y2 = s
        return ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) == 0
                and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2))

    def kind(s, t):
        px, py, qx, qy = s
        rx, ry, ux, uy = t
        d1x, d1y = qx - px, qy - py
        d2x, d2y = ux - rx, uy - ry
        deg1 = d1x == 0 and d1y == 0
        deg2 = d2x == 0 and d2y == 0
        if deg1 and deg2:
            return 1 if (px, py) == (rx, ry) else 0
        if deg1:
            return 1 if on_seg(px, py, t) else 0
        if deg2:
            return 1 if on_seg(rx, ry, s) else 0
        den = d1x * d2y - d1y * d2x
        wx, wy = rx - px, ry - py
        if den != 0:
            tn = wx * d2y - wy * d2x
            un = wx * d1y - wy * d1x
            if den < 0:
                den, tn, un = -den, -tn, -un
            if 0 <= tn <= den and 0 <= un <= den:
                return 2 if (0 < tn < den and 0 < un < den) else 1
            return 0
        if wx * d1y - wy * d1x != 0:
            return 0
        L = d1x * d1x + d1y * d1y
        b1 = wx * d1x + wy * d1y
        b2 = (ux - px) * d1x + (uy - py) * d1y
        lo = max(0, min(b1, b2))
        hi = min(L, max(b1, b2))
        if lo > hi:
            return 0
        return 1 if lo == hi else 3

    cnt = [0, 0, 0, 0]
    for i in range(len(S)):
        for j in range(i + 1, len(S)):
            cnt[kind(S[i], S[j])] += 1
    return (cnt[2], cnt[1], cnt[3])
''')

task("v6_23_bridge_free_labels", r'''
Write `bridge_free_labels(n, edges)` that labels the 2-edge-connected components of an undirected multigraph.

`n` is the number of vertices (numbered 0 .. n-1), an int with 1 <= n <= 200000. `edges` is a list or tuple of at most 400000 items; each item is a list or tuple (u, v) of two ints with 0 <= u, v < n (bool is not an int). Parallel edges (the same pair several times) and self-loops (u == v) are allowed. Any violation of these rules raises ValueError.

A bridge is an edge whose removal increases the number of connected components of the graph. Delete all bridges; the connected components that remain are the 2-edge-connected components (an isolated vertex is a component of its own). Return a list `label` of n ints where label[v] is the number of the component containing v. Numbering is canonical: scan v = 0, 1, ..., n-1 and give each component the next unused number 0, 1, 2, ... the first time one of its vertices is met. So label[0] == 0, and two vertices have equal labels exactly when they are in the same component.

Details that matter:
- Two parallel copies of an edge are not bridges (removing one leaves the other); a single copy can be a bridge. A self-loop is never a bridge and never connects anything new.
- The graph need not be connected; bridges are judged inside each connected component.
- Numbers follow vertex order over the whole graph, not the order of the connected components of the original graph (see the last example).
- The graph can be one long path of 100000 vertices, so the algorithm must not rely on deep recursion.

Examples:
- n=4, edges=[(0,1),(1,2),(2,0),(2,3)] -> [0, 0, 0, 1]  (the triangle, then vertex 3 behind a bridge)
- n=3, edges=[(0,1),(1,2)] -> [0, 1, 2]
- n=3, edges=[(0,1),(0,1),(1,2)] -> [0, 0, 1]
- n=3, edges=[(1,1)] -> [0, 1, 2]
- n=4, edges=[(0,3),(1,2),(2,1)] -> [0, 1, 1, 2]
''', r'''
import random

def brute(n, es):
    def connected(skip, u, v):
        adj = [[] for _ in range(n)]
        for i, (a, b) in enumerate(es):
            if i != skip:
                adj[a].append(b)
                adj[b].append(a)
        seen = {u}
        todo = [u]
        while todo:
            x = todo.pop()
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return v in seen
    keep = [(u, v) for i, (u, v) in enumerate(es) if u == v or connected(i, u, v)]
    adj = [[] for _ in range(n)]
    for u, v in keep:
        adj[u].append(v)
        adj[v].append(u)
    label = [-1] * n
    nxt = 0
    for s in range(n):
        if label[s] != -1:
            continue
        label[s] = nxt
        todo = [s]
        while todo:
            x = todo.pop()
            for y in adj[x]:
                if label[y] == -1:
                    label[y] = nxt
                    todo.append(y)
        nxt += 1
    return label

def same(n, es, exp):
    got = bridge_free_labels(n, es)
    assert type(got) is list and len(got) == n and all(type(x) is int for x in got), (n, es, got)
    assert got == exp, (n, es, got, exp)

def rej(*a):
    try:
        bridge_free_labels(*a)
    except ValueError:
        return True
    return False

same(4, [(0, 1), (1, 2), (2, 0), (2, 3)], [0, 0, 0, 1])
same(3, [(0, 1), (1, 2)], [0, 1, 2])
same(3, [(0, 1), (0, 1), (1, 2)], [0, 0, 1])
same(3, [(1, 1)], [0, 1, 2])
same(4, [(0, 3), (1, 2), (2, 1)], [0, 1, 1, 2])
same(1, [], [0])
same(1, [(0, 0), (0, 0)], [0])
same(2, [(0, 1)], [0, 1])
same(2, [(1, 0), (0, 1)], [0, 0])
same(2, [[1, 0], (0, 1), (0, 0)], [0, 0])
same(5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], [0] * 5)
same(5, [(0, 1), (1, 2), (2, 3), (3, 4)], [0, 1, 2, 3, 4])
same(6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3)], [0, 0, 0, 1, 1, 1])
same(6, [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3), (2, 3)], [0] * 6)
same(6, [(5, 4), (4, 5), (3, 2), (2, 1), (1, 0), (0, 3), (3, 4)], [0, 0, 0, 0, 1, 1])
# two triangles sharing a vertex are one component (no bridge between them)
same(5, [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)], [0] * 5)
# isolated vertices between components keep vertex-order numbering
same(7, [(6, 0), (6, 0), (2, 4), (4, 2), (4, 2), (3, 3)], [0, 1, 2, 3, 2, 4, 0])
same(4, [(3, 2), (2, 1), (1, 3), (0, 0)], [0, 1, 1, 1])

random.seed(6023)
for _ in range(250):
    n = random.randint(1, 10)
    m = random.randint(0, 14)
    es = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    if random.random() < 0.3:
        es = [random.choice([list, tuple])(e) for e in es]
    same(n, es, brute(n, [tuple(e) for e in es]))

for _ in range(60):
    n = random.randint(8, 14)
    es = [(i, random.randrange(i)) for i in range(1, n)]
    for _ in range(random.randint(0, 4)):
        es.append(random.choice(es))
    for _ in range(random.randint(0, 3)):
        es.append((random.randrange(n), random.randrange(n)))
    es = [e if random.random() < 0.5 else (e[1], e[0]) for e in es]
    random.shuffle(es)
    perm = list(range(n))
    random.shuffle(perm)
    es = [(perm[u], perm[v]) for u, v in es]
    same(n, es, brute(n, es))

# big path: edge i joins i and i+1; doubled when i % 3 == 0 (shuffled, flipped)
N = 20000
es = []
for i in range(N - 1):
    es.append((i, i + 1))
    if i % 3 == 0:
        es.append((i + 1, i))
es = [e if random.random() < 0.5 else (e[1], e[0]) for e in es]
random.shuffle(es)
exp = [0]
for i in range(N - 1):
    exp.append(exp[-1] if i % 3 == 0 else exp[-1] + 1)
same(N, es, exp)

# plain path of 100000 vertices: recursion-depth check
P = 100000
same(P, [(i, i + 1) for i in range(P - 1)], list(range(P)))
Q = 30000
same(Q, [(i + 1, i) for i in range(Q - 2, -1, -1)] + [(Q - 1, 0)], [0] * Q)

# long cycle with a hanging path
C = 20000
es = [(i, (i + 1) % C) for i in range(C)] + [(0, C)] + [(C + i, C + i + 1) for i in range(9999)]
random.shuffle(es)
same(C + 10000, es, [0] * C + list(range(1, 10001)))

# random tree: every vertex alone
n = 10000
es = [(i, random.randrange(i)) for i in range(1, n)]
random.shuffle(es)
same(n, es, list(range(n)))
es2 = es + es
same(n, es2, [0] * n)

for bad in (0, -1, 200001, True, 2.0, "3", None, [3]):
    assert rej(bad, []), bad
for bad in (None, {}, "ab", 5, set()):
    assert rej(3, bad), bad
assert rej(3, [(0, 0)] * 400001)
for bad in ((0,), (0, 1, 2), (0.0, 1), (0, 1.0), (True, 1), (0, False), (-1, 1), (0, 3), (3, 0), ("0", 1), (None, 1), 7, "ab", None, (10**30, 0)):
    assert rej(3, [(0, 1), bad]), bad
    assert rej(3, [bad]), bad
''', r'''
def bridge_free_labels(n, edges):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(n) or not 1 <= n <= 200000:
        raise ValueError("n")
    if not isinstance(edges, (list, tuple)) or len(edges) > 400000:
        raise ValueError("edges")
    es = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2:
            raise ValueError("edge")
        u, v = e
        if not isint(u) or not isint(v) or not (0 <= u < n and 0 <= v < n):
            raise ValueError("edge")
        es.append((u, v))
    adj = [[] for _ in range(n)]
    for i, (u, v) in enumerate(es):
        if u != v:
            adj[u].append((v, i))
            adj[v].append((u, i))
    tin = [-1] * n
    low = [0] * n
    ptr = [0] * n
    pe = [-1] * n
    bridge = [False] * len(es)
    timer = 0
    for r in range(n):
        if tin[r] != -1:
            continue
        tin[r] = low[r] = timer
        timer += 1
        stack = [r]
        while stack:
            v = stack[-1]
            if ptr[v] < len(adj[v]):
                to, ei = adj[v][ptr[v]]
                ptr[v] += 1
                if ei == pe[v]:
                    continue
                if tin[to] == -1:
                    tin[to] = low[to] = timer
                    timer += 1
                    pe[to] = ei
                    stack.append(to)
                elif tin[to] < low[v]:
                    low[v] = tin[to]
            else:
                stack.pop()
                if stack:
                    p = stack[-1]
                    if low[v] < low[p]:
                        low[p] = low[v]
                    if low[v] > tin[p]:
                        bridge[pe[v]] = True
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, (u, v) in enumerate(es):
        if u != v and not bridge[i]:
            parent[find(u)] = find(v)
    ids = {}
    out = []
    for v in range(n):
        r = find(v)
        if r not in ids:
            ids[r] = len(ids)
        out.append(ids[r])
    return out
''')

task("v6_24_regvm_eight", r'''
Write `run_regvm8(program, regs, max_steps)`, an interpreter for a tiny register machine with 8-bit registers.

`program` is a list of at most 200 strings (one source line each), `regs` is a dict mapping register names (a single lowercase letter 'a'..'z') to initial values (ints 0..255, bool is not an int), `max_steps` is an int 0..10**6 (bool is not an int). Anything else raises ValueError.

Source lines. Everything from the first ';' to the end of a line is a comment. The rest is split on whitespace; a line with no tokens is ignored. A line that is exactly one token ending in ':' defines a label (name matches [a-z_][a-z0-9_]*; it names the next instruction, or the end of the program). Every other line is one instruction: an upper-case opcode and its operands (r = register letter, L = label name):
  INC r, DEC r      add 1 / subtract 1, wrapping modulo 256 (255 + 1 -> 0, 0 - 1 -> 255)
  ADD r s           r = (r + s) % 256 (r and s may be the same register)
  JZ r L, JNZ r L   jump to label L if r == 0 / if r != 0
  JMP L             jump to label L
  CALL L            push the return address (the next instruction) and jump to L
  RET               pop the return address and jump to it; with an empty call stack the machine halts
  HALT              the machine halts
Opcodes are case sensitive. Raise ValueError for: an unknown opcode, a wrong operand count, an operand of the wrong kind, a bad label name (including "name :" or a label plus an instruction on one line), a duplicated label, a jump or call to an undefined label. The whole program is checked before anything runs, reachable or not.

Execution starts at instruction 0 with the registers from `regs`; registers that appear only in the program text start at 0. Executing one instruction (HALT and RET on an empty stack included) is one step. The call stack holds at most 8 return addresses: a CALL made while it holds 8 only counts its step and ends the run with status "fault".

Before each instruction: if the program counter is at or past the end, the status is "halt"; otherwise if steps == max_steps the status is "limit"; otherwise execute. So reaching the end exactly at step max_steps is "halt", and with max_steps == 0 a program without instructions is "halt" while any other is "limit" with 0 steps.

Returns a tuple (status, steps, final) where status is one of "halt", "limit", "fault", steps is the int number of instructions executed, and final is a dict holding every register that is either a key of `regs` or named as an operand anywhere in the program text (reachable or not), with its final int value.

Examples (P = ["  ; double a into b", "loop:", "JZ a done", "DEC a", "INC b", "INC b", "JMP loop", "done:", "HALT"]):
run_regvm8(P, {"a": 3}, 100) == ("halt", 17, {"a": 0, "b": 6})
run_regvm8(P, {"a": 3}, 9) == ("limit", 9, {"a": 1, "b": 4})
run_regvm8(["INC a", "INC a"], {}, 2) == ("halt", 2, {"a": 2})
run_regvm8(["INC a", "INC a"], {}, 1) == ("limit", 1, {"a": 1})
run_regvm8(["f:", "CALL f"], {}, 100) == ("fault", 9, {})
run_regvm8(["DEC a", "JNZ a end", "end:"], {}, 10) == ("halt", 2, {"a": 255})
run_regvm8([], {"q": 5}, 0) == ("halt", 0, {"q": 5})
''', r'''
import random
import re

def rej(*a):
    try:
        run_regvm8(*a)
    except ValueError:
        return True
    return False

LINE = re.compile(r"\s*(?:(?P<lab>[a-z_][a-z0-9_]*):|(?P<op>[A-Z]+)(?P<args>(?:\s+[a-z_][a-z0-9_]*)*))?\s*(?:;.*)?")
SHAPE = {"INC": "r", "DEC": "r", "ADD": "rr", "JZ": "rl", "JNZ": "rl", "JMP": "l", "CALL": "l", "RET": "", "HALT": ""}

def oracle(program, regs, max_steps):
    labels, ins = {}, []
    for line in program:
        m = LINE.fullmatch(line)
        if m is None:
            raise ValueError
        if m.group("lab") is not None:
            if m.group("lab") in labels:
                raise ValueError
            labels[m.group("lab")] = len(ins)
        elif m.group("op") is not None:
            op, args = m.group("op"), m.group("args").split()
            if op not in SHAPE or len(args) != len(SHAPE[op]):
                raise ValueError
            for k, a in zip(SHAPE[op], args):
                if k == "r" and (len(a) != 1 or not a.isalpha()):
                    raise ValueError
            ins.append((op, args))
    st = dict(regs)
    for op, args in ins:
        for k, a in zip(SHAPE[op], args):
            if k == "r":
                st.setdefault(a, 0)
            elif a not in labels:
                raise ValueError
    pc, n, calls = 0, 0, []
    while True:
        if pc >= len(ins):
            return ("halt", n, st)
        if n >= max_steps:
            return ("limit", n, st)
        op, a = ins[pc]
        n += 1
        nxt = pc + 1
        if op in ("INC", "DEC"):
            st[a[0]] = (st[a[0]] + (1 if op == "INC" else 255)) & 255
        elif op == "ADD":
            st[a[0]] = (st[a[0]] + st[a[1]]) & 255
        elif op == "JMP" or (op == "JZ" and st[a[0]] == 0) or (op == "JNZ" and st[a[0]] != 0):
            nxt = labels[a[-1]]
        elif op == "CALL":
            if len(calls) >= 8:
                return ("fault", n, st)
            calls.append(nxt)
            nxt = labels[a[0]]
        elif op == "RET":
            if not calls:
                return ("halt", n, st)
            nxt = calls.pop()
        elif op == "HALT":
            return ("halt", n, st)
        pc = nxt

def same(program, regs, ms, exp=None):
    got = run_regvm8(program, regs, ms)
    ref = oracle(program, regs, ms)
    assert type(got) is tuple and len(got) == 3, got
    assert type(got[0]) is str and type(got[1]) is int and type(got[2]) is dict, got
    assert all(type(v) is int for v in got[2].values()), got
    assert got == ref, (program, regs, ms, got, ref)
    if exp is not None:
        assert got == exp, (program, regs, ms, got, exp)

P = ["  ; double a into b", "loop:", "JZ a done", "DEC a", "INC b", "INC b", "JMP loop", "done:", "HALT"]
same(P, {"a": 3}, 100, ("halt", 17, {"a": 0, "b": 6}))
same(P, {"a": 3}, 9, ("limit", 9, {"a": 1, "b": 4}))
same(P, {"a": 3}, 17, ("halt", 17, {"a": 0, "b": 6}))
same(P, {"a": 3}, 16, ("limit", 16, {"a": 0, "b": 6}))
same(["INC a", "INC a"], {}, 2, ("halt", 2, {"a": 2}))
same(["INC a", "INC a"], {}, 1, ("limit", 1, {"a": 1}))
same(["f:", "CALL f"], {}, 100, ("fault", 9, {}))
same(["f:", "CALL f"], {}, 9, ("fault", 9, {}))
same(["f:", "CALL f"], {}, 8, ("limit", 8, {}))
same(["DEC a", "JNZ a end", "end:"], {}, 10, ("halt", 2, {"a": 255}))
same([], {"q": 5}, 0, ("halt", 0, {"q": 5}))
same(["INC a"], {"q": 5}, 0, ("limit", 0, {"q": 5, "a": 0}))
same(["end:"], {}, 0, ("halt", 0, {}))
same(["CALL g", "INC a", "HALT", "g:", "INC b", "RET"], {}, 100, ("halt", 5, {"a": 1, "b": 1}))
same(["RET", "INC a"], {}, 100, ("halt", 1, {"a": 0}))
same(["ADD a a", "ADD a a"], {"a": 200}, 5, ("halt", 2, {"a": 32}))
same(["INC a ; x", "  \t INC\tb  ;;", ";", "", "   "], {}, 5, ("halt", 2, {"a": 1, "b": 1}))
same(["INC a", "JZ a out", "HALT", "out:", "INC b"], {"a": 255}, 50, ("halt", 3, {"a": 0, "b": 1}))
same(["HALT", "INC n"], {}, 5, ("halt", 1, {"n": 0}))
same(["x:", "JMP x"], {}, 1000, ("limit", 1000, {}))
same(["a:", "b:", "INC c", "b2:"], {"z": 255}, 3, ("halt", 1, {"z": 255, "c": 1}))
same(["DEC a", "ADD a b", "JZ a w", "w:"], {"a": 1, "b": 255}, 9, ("halt", 3, {"a": 255, "b": 255}))
deep = ["main:", "CALL f1", "HALT"] + [x for i in range(1, 8) for x in ("f%d:" % i, "CALL f%d" % (i + 1), "RET")] + ["f8:", "INC a", "RET"]
same(deep, {}, 100, ("halt", 1 + 7 + 2 + 7 + 1, {"a": 1}))
deep2 = deep[:-3] + ["f8:", "CALL f9", "RET", "f9:", "INC a", "RET"]
same(deep2, {}, 100, ("fault", 9, {"a": 0}))
same(deep2, {}, 8, ("limit", 8, {"a": 0}))

bad_programs = [["inc a"], ["INC"], ["INC a b"], ["INC A"], ["INC ab"], ["INC 1"], ["ADD a"], ["JZ a"], ["JZ L a"], ["JMP"],
                ["JMP nowhere"], ["x:", "x:"], ["x :"], ["x: INC a"], ["X:"], ["1x:"], ["a-b:"], [":"], ["HALT now"], ["RET 1"],
                ["HALT", "JMP nowhere"], ["HALT", "FOO"], ["HALT", "end:end:"], ["CALL Q"], ["JNZ a b c"], ["INC a;", "INC b c"],
                ["x:", "y:", "x:"], ["JMP L-1"], ["JZ aa L", "L:"]]
for bp in bad_programs:
    assert rej(bp, {}, 10), bp
    assert rej(bp, {}, 0), bp
assert not rej(["x:", "y:"], {}, 0)
assert not rej(["_:", "JMP _"], {}, 3)
assert not rej(["a1_:", "HALT", "JMP a1_"], {}, 3)
for bad in (None, "INC a", ("INC a",), [1], ["INC a", None], ["INC a"] * 201, [b"INC a"]):
    assert rej(bad, {}, 5), bad
assert not rej(["HALT"] * 200, {}, 5)
for bad in (None, [("a", 1)], {"A": 1}, {"ab": 1}, {1: 1}, {"": 0}, {"a": 256}, {"a": -1}, {"a": 1.0}, {"a": True}, {"a": "1"}, {"a": None}, {"\u00e9": 1}):
    assert rej(["HALT"], bad, 5), bad
for bad in (-1, 10**6 + 1, 3.0, "3", None, True, False, [3]):
    assert rej(["HALT"], {}, bad), bad
same(["HALT"], {"a": 255, "z": 0}, 10**6, ("halt", 1, {"a": 255, "z": 0}))
same(["x:", "INC a", "JMP x"], {}, 10**5)

random.seed(6024)
NAMES = ["L0", "L1", "L2", "E"]
def rline(n):
    r = random.choice
    reg = lambda: r("abcd")
    k = random.random()
    if k < 0.12:
        return "INC " + reg()
    if k < 0.3:
        return r(["INC", "DEC"]) + " " + reg()
    if k < 0.4:
        return "ADD %s %s" % (reg(), reg())
    if k < 0.55:
        return "%s %s %s" % (r(["JZ", "JNZ"]), reg(), r(NAMES).lower())
    if k < 0.65:
        return "JMP " + r(NAMES).lower()
    if k < 0.75:
        return "CALL " + r(NAMES).lower()
    if k < 0.83:
        return "RET"
    if k < 0.93:
        return "HALT"
    return r(["INC a ; c", "  DEC\tb", "; only", "", "INC a ; c", "  DEC\tb", "; only", "", "L0 :", "inc a", "INC", "x: INC a", "JMP", "ADD a", "FOO a"])
ok = bad = 0
for _ in range(500):
    prog = [rline(i) for i in range(random.randint(1, 14))]
    for nm in NAMES:
        if random.random() < 0.93:
            prog.insert(random.randint(0, len(prog)), nm.lower() + ":")
    regs = {c: random.randint(0, 255) for c in random.sample("abcdxy", random.randint(0, 4))}
    ms = random.choice([0, 1, 2, 5, 20, 100, 400])
    try:
        ref = oracle(prog, regs, ms)
    except ValueError:
        assert rej(prog, regs, ms), (prog, regs, ms)
        bad += 1
        continue
    same(prog, regs, ms)
    ok += 1
assert ok > 120, (ok, bad)
''', r'''
import re

def run_regvm8(program, regs, max_steps):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(program, list) or len(program) > 200 or not all(isinstance(x, str) for x in program):
        raise ValueError("program")
    if not isinstance(regs, dict):
        raise ValueError("regs")
    for k, v in regs.items():
        if not (isinstance(k, str) and len(k) == 1 and "a" <= k <= "z" and isint(v) and 0 <= v <= 255):
            raise ValueError("regs")
    if not isint(max_steps) or not 0 <= max_steps <= 10 ** 6:
        raise ValueError("max_steps")
    shapes = {"INC": "r", "DEC": "r", "ADD": "rr", "JZ": "rl", "JNZ": "rl", "JMP": "l", "CALL": "l", "RET": "", "HALT": ""}
    name = re.compile(r"[a-z_][a-z0-9_]*")
    code, labels = [], {}
    for line in program:
        toks = line.split(";")[0].split()
        if not toks:
            continue
        if len(toks) == 1 and toks[0].endswith(":"):
            lab = toks[0][:-1]
            if not name.fullmatch(lab) or lab in labels:
                raise ValueError("label")
            labels[lab] = len(code)
            continue
        op = toks[0]
        if op not in shapes or len(toks) - 1 != len(shapes[op]):
            raise ValueError("instruction")
        for kind, t in zip(shapes[op], toks[1:]):
            if kind == "r" and not (len(t) == 1 and "a" <= t <= "z"):
                raise ValueError("register")
            if kind == "l" and not name.fullmatch(t):
                raise ValueError("label ref")
        code.append(toks)
    out = {k: v for k, v in regs.items()}
    for toks in code:
        for kind, t in zip(shapes[toks[0]], toks[1:]):
            if kind == "r":
                out.setdefault(t, 0)
            elif t not in labels:
                raise ValueError("undefined label")
    pc = steps = 0
    stack = []
    while True:
        if pc >= len(code):
            status = "halt"
            break
        if steps == max_steps:
            status = "limit"
            break
        toks = code[pc]
        op = toks[0]
        steps += 1
        pc += 1
        if op == "INC":
            out[toks[1]] = (out[toks[1]] + 1) % 256
        elif op == "DEC":
            out[toks[1]] = (out[toks[1]] - 1) % 256
        elif op == "ADD":
            out[toks[1]] = (out[toks[1]] + out[toks[2]]) % 256
        elif op == "JZ":
            if out[toks[1]] == 0:
                pc = labels[toks[2]]
        elif op == "JNZ":
            if out[toks[1]] != 0:
                pc = labels[toks[2]]
        elif op == "JMP":
            pc = labels[toks[1]]
        elif op == "CALL":
            if len(stack) == 8:
                status = "fault"
                break
            stack.append(pc)
            pc = labels[toks[1]]
        elif op == "RET":
            if not stack:
                status = "halt"
                break
            pc = stack.pop()
        else:
            status = "halt"
            break
    return (status, steps, out)
''')

task("v6_25_mlfq_finish_times", r'''
Write `mlfq_finish_times(jobs, quanta)` that simulates a multilevel feedback queue on one CPU and returns the finish time of every job.

`jobs` is a list of at most 100 pairs (arrival, burst) (tuples or lists of two ints, bool is not an int) with 0 <= arrival <= 10**6 and 1 <= burst <= 10**4. `quanta` is a list of 1 to 5 ints, each 1 <= q <= 10**4; level 0 is the highest priority and has quantum quanta[0], and so on. Anything else raises ValueError. The result is a list of ints: element i is the time at which job i completes (jobs keep their input positions; an empty job list gives []). Time is an integer; the clock starts at 0.

Rules:
- Every job enters level 0 when it arrives. Jobs arriving at the same instant are queued in input order.
- Each level is a FIFO queue. The CPU always takes the job at the head of the highest-priority non-empty level and runs it, with a fresh full quantum of that level every time it is picked. If every queue is empty the CPU idles until the next arrival.
- A job that has run for its full quantum without finishing is demoted: it goes to the tail of the next level down; at the last level it goes back to the tail of the same level (round robin). A job whose burst ends exactly when its quantum ends has simply finished.
- A job running at a level with index >= 1 is preempted by any arrival that lands strictly inside its current run (after the run started, before the run's scheduled end). It stops at the arrival instant, keeps its remaining burst, and goes back to the FRONT of its own level, not demoted. Its next run starts with a fresh quantum. A job running at level 0 is never preempted. An arrival exactly at the instant a run ends does not preempt anything.
- At an instant where a run ends and jobs arrive, the arrivals are queued first, and only then is the job that just used its quantum placed in its new queue (this matters when there is a single level, because then the demoted job lands in level 0's queue).
- Switching jobs takes no time.

Examples:
mlfq_finish_times([(0, 5), (1, 3), (2, 2)], [2, 4]) == [9, 10, 6]
mlfq_finish_times([(0, 10), (3, 1)], [2, 4, 8]) == [11, 4]   # the level-1 run 2..6 is preempted at 3
mlfq_finish_times([(0, 4), (2, 1)], [2]) == [5, 3]   # job 1 arrives when job 0's quantum ends and queues first
mlfq_finish_times([(4, 2), (4, 1), (0, 1)], [1, 2]) == [7, 6, 1]
mlfq_finish_times([(0, 9), (1, 1), (1, 1)], [1, 3]) == [11, 2, 3]
mlfq_finish_times([], [3]) == []
''', r'''
import random

def rej(*a):
    try:
        mlfq_finish_times(*a)
    except ValueError:
        return True
    return False

def tick_oracle(jobs, quanta):
    n = len(jobs)
    rem = [b for a, b in jobs]
    fin = [None] * n
    qs = [[] for _ in quanta]
    cur, lvl, used, t = None, 0, 0, 0
    while any(f is None for f in fin):
        new = [i for i in range(n) if jobs[i][0] == t]
        qs[0].extend(new)
        if cur is not None:
            if rem[cur] == 0:
                fin[cur] = t
                cur = None
            elif used == quanta[lvl]:
                qs[min(lvl + 1, len(qs) - 1)].append(cur)
                cur = None
            elif new and lvl > 0:
                qs[lvl].insert(0, cur)
                cur = None
        if cur is None:
            for l, q in enumerate(qs):
                if q:
                    cur = q.pop(0)
                    lvl, used = l, 0
                    break
        if cur is not None:
            rem[cur] -= 1
            used += 1
        t += 1
    return fin

def same(jobs, quanta, exp=None):
    got = mlfq_finish_times(jobs, quanta)
    assert type(got) is list and all(type(x) is int for x in got), got
    if exp is not None:
        assert got == exp, (jobs, quanta, got, exp)
    return got

same([(0, 5), (1, 3), (2, 2)], [2, 4], [9, 10, 6])
same([(0, 10), (3, 1)], [2, 4, 8], [11, 4])
same([(0, 4), (2, 1)], [2], [5, 3])
same([(4, 2), (4, 1), (0, 1)], [1, 2], [7, 6, 1])
same([(0, 9), (1, 1), (1, 1)], [1, 3], [11, 2, 3])
same([], [3], [])
same([(5, 2)], [1], [7])
same([(0, 3), (0, 3)], [3], [3, 6])
same([[0, 3], [0, 3], [1, 1]], [1, 2, 4], [5, 7, 3])
same([(0, 5), (3, 4)], [2, 4], [7, 9])
same([(0, 6), (2, 1), (4, 1)], [2, 6], [8, 3, 5])
same([(10**6, 10**4), (0, 1)], [10**4], [10**6 + 10**4, 1])
same([(0, 1)] * 3, [1, 1], [1, 2, 3])
same([(0, 2), (1, 1)], [1, 5], [3, 2])
same([(0, 4), (1, 1)], [1, 5], [5, 2])
same([(0, 4), (1, 1)], [2, 5], [5, 3])

for bad in (None, (), "ab", [(0, 1)] * 101, [(0, 1, 2)], [(0,)], [0], [(-1, 1)], [(0, 0)], [(0, 10**4 + 1)], [(10**6 + 1, 1)],
            [(0.0, 1)], [(0, 1.0)], [(True, 1)], [(0, True)], [("0", 1)], [None], [(0, 1), [1]], {(0, 1)}):
    assert rej(bad, [2]), bad
for bad in (None, [], [0], [-1], [10**4 + 1], [1] * 6, [1.0], [True], ["2"], (2,), 2, [2, 0], [None]):
    assert rej([(0, 1)], bad), bad
assert not rej([(0, 1)] * 100, [1] * 5)
assert not rej([], [10**4])

random.seed(6025)
for _ in range(400):
    n = random.randint(0, 7)
    quanta = [random.randint(1, 5) for _ in range(random.randint(1, 4))]
    mx = random.choice([3, 8, 20])
    jobs = [(random.randint(0, mx), random.randint(1, 9)) for _ in range(n)]
    same(jobs, quanta, tick_oracle(jobs, quanta))
for _ in range(60):
    n = random.randint(15, 30)
    quanta = sorted(random.randint(1, 8) for _ in range(random.randint(1, 5)))
    jobs = [(random.randint(0, 80), random.randint(1, 14)) for _ in range(n)]
    same(jobs, quanta, tick_oracle(jobs, quanta))
# invariants on a big instance: finish >= arrival + burst, and total busy time bounds the makespan
jobs = [(random.randint(0, 10**6), random.randint(1, 10**4)) for _ in range(100)]
res = same(jobs, [3, 50, 700, 9000, 10**4])
assert all(f >= a + b for (a, b), f in zip(jobs, res))
jobs = [(random.randint(0, 100), 10**4) for _ in range(100)]
res = mlfq_finish_times(jobs, [10**4])
assert max(res) == min(a for a, b in jobs) + 100 * 10**4
assert len(set(res)) == 100
''', r'''
from collections import deque

def mlfq_finish_times(jobs, quanta):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(jobs, list) or len(jobs) > 100:
        raise ValueError("jobs")
    if not isinstance(quanta, list) or not 1 <= len(quanta) <= 5 or not all(isint(q) and 1 <= q <= 10 ** 4 for q in quanta):
        raise ValueError("quanta")
    for j in jobs:
        if not (isinstance(j, (tuple, list)) and len(j) == 2 and isint(j[0]) and isint(j[1])
                and 0 <= j[0] <= 10 ** 6 and 1 <= j[1] <= 10 ** 4):
            raise ValueError("job")
    n = len(jobs)
    order = sorted(range(n), key=lambda i: (jobs[i][0], i))
    rem = [j[1] for j in jobs]
    fin = [0] * n
    queues = [deque() for _ in quanta]
    nxt = 0
    t = 0
    done = 0
    while done < n:
        while nxt < n and jobs[order[nxt]][0] <= t:
            queues[0].append(order[nxt])
            nxt += 1
        lvl = next((l for l, q in enumerate(queues) if q), None)
        if lvl is None:
            t = jobs[order[nxt]][0]
            continue
        i = queues[lvl].popleft()
        run = min(quanta[lvl], rem[i])
        if lvl > 0 and nxt < n and jobs[order[nxt]][0] < t + run:
            run = jobs[order[nxt]][0] - t
            rem[i] -= run
            t += run
            queues[lvl].appendleft(i)
            continue
        rem[i] -= run
        t += run
        while nxt < n and jobs[order[nxt]][0] <= t:
            queues[0].append(order[nxt])
            nxt += 1
        if rem[i] == 0:
            fin[i] = t
            done += 1
        else:
            queues[min(lvl + 1, len(quanta) - 1)].append(i)
    return fin
''')

task("v6_26_best_fit_heap", r'''
Write `sim_best_fit_heap(size, ops)` that simulates a heap allocator over the address range [0, size) and returns (results, free_blocks).

`size` is an int, a multiple of 8, with 8 <= size <= 10**12 (bool is not an int). `ops` is a list of at most 3000 operations, each a tuple or list: ("alloc", id, n), ("realloc", id, n) or ("free", id), with id an int 0..10**9 and n an int 1..10**12 (bool is not an int). Any other shape, op name, type or range raises ValueError, and so does ("alloc", id, n) while that id is currently live (allocated and not freed).

Every request size n is rounded up to a multiple of 8; all blocks have such sizes and addresses. The heap starts as one free block (0, size). Free blocks are kept coalesced: two free blocks that touch are always one block.

- alloc: best fit. Take the smallest free block whose size >= the rounded request; among equal sizes take the lowest address. The new block is placed at the START of that free block and the rest (if any) stays free. Result: the address, or -1 if no free block is big enough (nothing changes and the id is not live).
- free: if the id is live, release its block, coalescing with free neighbours on both sides; result True. Otherwise nothing happens; result False.
- realloc, id not live: result -1, nothing changes. Otherwise let cur be the block's size and new the rounded size:
  * new == cur: result is the same address.
  * new < cur: shrink in place; the freed tail [addr + new, addr + cur) is released (coalescing with a free block that follows it); result is the same address.
  * new > cur: if the block that starts at addr + cur is free and its size >= new - cur, grow in place by taking the first new - cur bytes of that free block; result is the same address. Otherwise look for a best-fit free block of size >= new, exactly as for alloc, while the old block is still allocated (so the old block does not count as free space and nothing is merged with it). If there is none, result -1 and nothing changes (the old block stays). If there is one, the id moves there, then the old block is released (coalescing), and the result is the new address.

results is a list with one entry per operation, in order: int for alloc and realloc, bool for free. free_blocks is the final list of free blocks as (address, size) tuples of ints sorted by address (a list, possibly empty).

Examples:
sim_best_fit_heap(64, [("alloc", 1, 10), ("alloc", 2, 8), ("alloc", 3, 20), ("free", 2), ("alloc", 4, 5), ("free", 9), ("realloc", 1, 17)]) == ([0, 16, 24, True, 16, False, -1], [(48, 16)])
sim_best_fit_heap(64, [("alloc", 1, 16), ("alloc", 2, 16), ("alloc", 3, 16), ("free", 1), ("free", 3), ("alloc", 4, 16), ("alloc", 5, 24)]) == ([0, 16, 32, True, True, 0, 32], [(56, 8)])
sim_best_fit_heap(64, [("alloc", 1, 8), ("alloc", 2, 8), ("free", 1), ("realloc", 2, 40), ("realloc", 2, 48)]) == ([0, 8, True, 8, 8], [(0, 8), (56, 8)])
sim_best_fit_heap(40, [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 3, 8), ("free", 1), ("realloc", 2, 16)]) == ([0, 8, 16, True, 24], [(0, 16)])
sim_best_fit_heap(32, [("alloc", 1, 32), ("realloc", 1, 8), ("alloc", 2, 24), ("realloc", 1, 16)]) == ([0, 0, 8, -1], [])
''', r'''
import random

def rej(*a):
    try:
        sim_best_fit_heap(*a)
    except ValueError:
        return True
    return False

class Cells:
    """One cell = 8 bytes; owner id per cell, None = free."""
    def __init__(self, size):
        self.n = size // 8
        self.c = [None] * self.n
        self.live = {}

    def runs(self):
        out, i = [], 0
        while i < self.n:
            if self.c[i] is None:
                j = i
                while j < self.n and self.c[j] is None:
                    j += 1
                out.append((i, j - i))
                i = j
            else:
                i += 1
        return out

    def find(self, need):
        cand = [(l, s) for s, l in self.runs() if l >= need]
        return min(cand) if cand else None

    def put(self, ident, s, l):
        for i in range(s, s + l):
            self.c[i] = ident
        self.live[ident] = (s, l)

    def step(self, op):
        kind, ident = op[0], op[1]
        if kind == "free":
            if ident not in self.live:
                return False
            s, l = self.live.pop(ident)
            for i in range(s, s + l):
                self.c[i] = None
            return True
        if kind == "alloc":
            assert ident not in self.live
        elif ident not in self.live:
            return -1
        need = -(-op[2] // 8)
        if kind == "alloc":
            f = self.find(need)
            if f is None:
                return -1
            self.put(ident, f[1], need)
            return f[1] * 8
        s, l = self.live[ident]
        if need <= l:
            for i in range(s + need, s + l):
                self.c[i] = None
            self.live[ident] = (s, need)
            return s * 8
        if s + need <= self.n and all(self.c[i] is None for i in range(s + l, s + need)):
            self.put(ident, s, need)
            return s * 8
        f = self.find(need)
        if f is None:
            return -1
        for i in range(s, s + l):
            self.c[i] = None
        # old block was still occupied while searching; now move
        self.put(ident, f[1], need)
        return f[1] * 8

def oracle(size, ops):
    m = Cells(size)
    res = [m.step(op) for op in ops]
    return res, [(s * 8, l * 8) for s, l in m.runs()]

def same(size, ops, exp=None):
    got = sim_best_fit_heap(size, ops)
    assert type(got) is tuple and len(got) == 2, got
    res, fr = got
    assert type(res) is list and type(fr) is list, got
    for op, r in zip(ops, res):
        assert type(r) is (bool if op[0] == "free" else int), (op, r)
    assert all(type(t) is tuple and len(t) == 2 and type(t[0]) is int and type(t[1]) is int for t in fr), fr
    if exp is not None:
        assert got == exp, (size, ops, got, exp)
    return got

same(64, [("alloc", 1, 10), ("alloc", 2, 8), ("alloc", 3, 20), ("free", 2), ("alloc", 4, 5), ("free", 9), ("realloc", 1, 17)],
     ([0, 16, 24, True, 16, False, -1], [(48, 16)]))
same(64, [("alloc", 1, 16), ("alloc", 2, 16), ("alloc", 3, 16), ("free", 1), ("free", 3), ("alloc", 4, 16), ("alloc", 5, 24)],
     ([0, 16, 32, True, True, 0, 32], [(56, 8)]))
same(64, [("alloc", 1, 8), ("alloc", 2, 8), ("free", 1), ("realloc", 2, 40), ("realloc", 2, 48)], ([0, 8, True, 8, 8], [(0, 8), (56, 8)]))
same(40, [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 3, 8), ("free", 1), ("realloc", 2, 16)], ([0, 8, 16, True, 24], [(0, 16)]))
same(32, [("alloc", 1, 32), ("realloc", 1, 8), ("alloc", 2, 24), ("realloc", 1, 16)], ([0, 0, 8, -1], []))
same(8, [], ([], [(0, 8)]))
same(8, [("alloc", 0, 8), ("alloc", 1, 1), ("free", 0), ("alloc", 1, 1)], ([0, -1, True, 0], []))
same(8, [("alloc", 0, 9)], ([-1], [(0, 8)]))
same(16, [("alloc", 5, 1), ("realloc", 5, 8), ("realloc", 5, 9), ("realloc", 5, 16), ("realloc", 5, 17), ("free", 5), ("free", 5)],
     ([0, 0, 0, 0, -1, True, False], [(0, 16)]))
same(48, [("alloc", 1, 16), ("alloc", 2, 16), ("alloc", 3, 16), ("free", 2), ("realloc", 1, 24), ("realloc", 3, 8)],
     ([0, 16, 32, True, 0, 32], [(24, 8), (40, 8)]))
same(48, [("alloc", 1, 8), ("alloc", 2, 16), ("alloc", 3, 8), ("free", 1), ("free", 3), ("alloc", 4, 8), ("alloc", 5, 8)],
     ([0, 8, 24, True, True, 0, 24], [(32, 16)]))
# best fit beats first fit; equal sizes take the lowest address
same(80, [("alloc", 1, 24), ("alloc", 2, 8), ("alloc", 3, 8), ("alloc", 4, 8), ("alloc", 5, 8), ("alloc", 6, 24),
          ("free", 1), ("free", 3), ("free", 5), ("alloc", 7, 8), ("alloc", 8, 8)],
     oracle(80, [("alloc", 1, 24), ("alloc", 2, 8), ("alloc", 3, 8), ("alloc", 4, 8), ("alloc", 5, 8), ("alloc", 6, 24),
                 ("free", 1), ("free", 3), ("free", 5), ("alloc", 7, 8), ("alloc", 8, 8)]))
# a moving realloc cannot reuse its own old block, and the old block is merged only after the move
same(56, [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 3, 16), ("alloc", 4, 8), ("free", 3), ("realloc", 2, 24), ("free", 4)],
     oracle(56, [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 3, 16), ("alloc", 4, 8), ("free", 3), ("realloc", 2, 24), ("free", 4)]))
same(56, [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 3, 8), ("alloc", 4, 24), ("free", 3), ("realloc", 2, 16)], ([0, 8, 16, 24, True, 8], [(48, 8)]))
H = 10**12
same(H, [("alloc", 1, H)], ([0], []))
same(H - 8, [("alloc", 1, H)], ([-1], [(0, H - 8)]))
same(H, [("alloc", 1, 1), ("alloc", 2, H - 8)], ([0, 8], []))
same(H, [("alloc", 1, 5), ("free", 1)], ([0, True], [(0, H)]))
same(H, [("alloc", 1, H // 2), ("alloc", 2, H // 4), ("free", 1), ("realloc", 2, H // 2 + 1), ("free", 2)],
     ([0, H // 2, True, -1, True], [(0, H)]))
same(H, [("alloc", 1, 10**11), ("realloc", 1, H), ("realloc", 1, 8), ("alloc", 2, 8)], ([0, 0, 0, 8], [(16, H - 16)]))
same(H, [("alloc", 1, 10 ** 12 - 7), ("realloc", 1, 10 ** 12), ("free", 1)], ([0, 0, True], [(0, H)]))

for bad in (0, 7, 12, -8, H + 8, 16.0, True, "16", None, [16], 4):
    assert rej(bad, []), bad
assert not rej(8, []) and not rej(H, [])
for bad in (None, (), "alloc", {"alloc": 1}, [("alloc", 1, 8)] * 3001):
    assert rej(64, bad), bad
for bad in ([("alloc", 1)], [("alloc", 1, 8, 8)], [("free", 1, 8)], [("free",)], [("realloc", 1)], [("grow", 1, 8)], [("ALLOC", 1, 8)],
            [("alloc", -1, 8)], [("alloc", 10**9 + 1, 8)], [("alloc", 1.0, 8)], [("alloc", True, 8)], [("alloc", "1", 8)],
            [("alloc", 1, 0)], [("alloc", 1, -8)], [("alloc", 1, H + 1)], [("alloc", 1, 8.0)], [("alloc", 1, True)], [("alloc", 1, None)],
            [("free", -1)], [("free", 1.5)], [("free", None)], [("realloc", 1, 0)], [("realloc", 1, H + 1)], [()], [None], ["free"], [5],
            [(1, 1, 8)], [("alloc", 1, 8), ("alloc", 1, 8)], [("alloc", 1, 8), ("alloc", 2, 8), ("alloc", 1, 1)],
            [("alloc", 1, 8), ("bogus", 1)]):
    assert rej(64, bad), bad
# alloc of a live id is rejected even when the previous alloc could not have failed; a failed alloc leaves the id free
assert rej(64, [("alloc", 1, 8), ("realloc", 1, 16), ("alloc", 1, 8)])
same(16, [("alloc", 1, 100), ("alloc", 1, 8), ("free", 1), ("alloc", 1, 8)], ([-1, 0, True, 0], [(8, 8)]))
assert not rej(64, [["alloc", 1, 8], ["free", 1], ["alloc", 1, 8], ["realloc", 9, 8]])
same(64, [["alloc", 1, 8], ["free", 1], ["alloc", 1, 8], ["realloc", 9, 8]], ([0, True, 0, -1], [(8, 56)]))
assert rej(64, [("alloc", 1, 8), ("free", 1), ("free", True)])

random.seed(6026)
for _ in range(700):
    size = 8 * random.choice([1, 2, 3, 5, 8, 13, 24, 40])
    m = Cells(size)
    ops, res = [], []
    ids = random.randint(2, 7)
    for _ in range(random.randint(1, 45)):
        kind = random.choice(["alloc", "alloc", "alloc", "free", "free", "realloc", "realloc", "realloc"])
        ident = random.randrange(ids)
        if kind == "alloc":
            if ident in m.live:
                kind = random.choice(["free", "realloc"])
        n = random.choice([1, 7, 8, 9, 15, 16, 17, 24, 33, random.randint(1, size + 9)])
        op = (kind, ident) if kind == "free" else (kind, ident, n)
        ops.append(op)
        res.append(m.step(op))
    got = same(size, ops)
    assert got == (res, [(s * 8, l * 8) for s, l in m.runs()]), (size, ops, got, res)
for _ in range(25):
    size = 8 * random.randint(100, 220)
    m = Cells(size)
    ops, res = [], []
    for _ in range(random.randint(100, 220)):
        kind = random.choice(["alloc", "alloc", "free", "realloc"])
        ident = random.randrange(30)
        if kind == "alloc" and ident in m.live:
            kind = "realloc"
        n = random.randint(1, 120)
        op = (kind, ident) if kind == "free" else (kind, ident, n)
        ops.append(op)
        res.append(m.step(op))
    got = same(size, ops)
    assert got == (res, [(s * 8, l * 8) for s, l in m.runs()]), (size, ops)
''', r'''
import bisect

def sim_best_fit_heap(size, ops):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isint(size) or size < 8 or size > 10 ** 12 or size % 8:
        raise ValueError("size")
    if not isinstance(ops, list) or len(ops) > 3000:
        raise ValueError("ops")
    for op in ops:
        if not isinstance(op, (tuple, list)) or not op or not isinstance(op[0], str):
            raise ValueError("op")
        want = {"alloc": 3, "realloc": 3, "free": 2}.get(op[0])
        if want is None or len(op) != want or not isint(op[1]) or not 0 <= op[1] <= 10 ** 9:
            raise ValueError("op")
        if want == 3 and not (isint(op[2]) and 1 <= op[2] <= 10 ** 12):
            raise ValueError("op")
    free = [(0, size)]
    live = {}
    out = []

    def best(need):
        pick = None
        for k, (a, s) in enumerate(free):
            if s >= need and (pick is None or s < free[pick][1]):
                pick = k
        if pick is None:
            return None
        a, s = free[pick]
        if s == need:
            del free[pick]
        else:
            free[pick] = (a + need, s - need)
        return a

    def release(a, s):
        k = bisect.bisect_left(free, (a, 0))
        if k < len(free) and free[k][0] == a + s:
            s += free[k][1]
            del free[k]
        if k > 0 and free[k - 1][0] + free[k - 1][1] == a:
            a, s = free[k - 1][0], free[k - 1][1] + s
            del free[k - 1]
            k -= 1
        free.insert(k, (a, s))

    for op in ops:
        kind, ident = op[0], op[1]
        if kind == "alloc":
            if ident in live:
                raise ValueError("live id")
            need = (op[2] + 7) // 8 * 8
            a = best(need)
            if a is None:
                out.append(-1)
            else:
                live[ident] = (a, need)
                out.append(a)
        elif kind == "free":
            if ident in live:
                a, s = live.pop(ident)
                release(a, s)
                out.append(True)
            else:
                out.append(False)
        else:
            if ident not in live:
                out.append(-1)
                continue
            a, cur = live[ident]
            need = (op[2] + 7) // 8 * 8
            if need == cur:
                out.append(a)
            elif need < cur:
                live[ident] = (a, need)
                release(a + need, cur - need)
                out.append(a)
            else:
                k = bisect.bisect_left(free, (a + cur, 0))
                if k < len(free) and free[k][0] == a + cur and free[k][1] >= need - cur:
                    fa, fs = free[k]
                    grow = need - cur
                    if fs == grow:
                        del free[k]
                    else:
                        free[k] = (fa + grow, fs - grow)
                    live[ident] = (a, need)
                    out.append(a)
                else:
                    b = best(need)
                    if b is None:
                        out.append(-1)
                    else:
                        live[ident] = (b, need)
                        release(a, cur)
                        out.append(b)
    return (out, list(free))
''')

task("v6_27_wrap_cubic_lines", r'''
Write `wrap_cubic_lines(lens, width, breaks)` that splits a paragraph of words into lines with minimum "raggedness" and returns how many words go on each line.

`lens` is a list of at most 2000 word lengths (ints, 1 <= len <= 10**6; bool is not an int), `width` is an int with 1 <= width <= 10**6, `breaks` is a list of word indices (ints with 0 <= i < len(lens); duplicates allowed). Words keep their order. A line with k words of total length S needs S + (k - 1) columns (one space between neighbours) and must fit: columns <= width. Raise ValueError if lens, width or breaks has the wrong type or range (for an empty `lens` any entry in `breaks` is out of range), and also if any single word is longer than `width`.

A hard break after word i means a line must end right after word i (no line may contain both word i and word i + 1). The last word always ends a line.

Cost. A line that ends at a hard break or at the last word costs 0, however short it is. Every other line costs (width - columns) ** 3 (an exact int; a line that fills the width exactly costs 0). The total cost is the sum over lines.

Return the list of per-line word counts (positive ints summing to len(lens); [] for no words) of an arrangement with the minimum total cost. If several arrangements share the minimum cost, return the one whose list of word counts is lexicographically smallest: compare the first line's count first, then the second line's, and so on.

Examples:
wrap_cubic_lines([3, 3, 3, 3], 7, []) == [2, 2]
wrap_cubic_lines([5, 5], 5, []) == [1, 1]
wrap_cubic_lines([1, 1, 1, 1, 1, 1, 1], 5, []) == [3, 3, 1]
wrap_cubic_lines([2, 4, 1, 2, 4, 4], 9, []) == [2, 3, 1]    # [3, 2, 1] has the same cost 8, but [2, 3, 1] is smaller
wrap_cubic_lines([1, 1, 2, 3, 3], 6, [4]) == [2, 2, 1]    # [3, 1, 1] ties on cost 27; a hard break at the last word changes nothing
wrap_cubic_lines([5, 1, 1, 5], 6, [1]) == [1, 1, 1, 1]    # "5 1" needs 7 columns; word 0 alone costs 1, the hard-break line costs 0
wrap_cubic_lines([], 5, []) == []
wrap_cubic_lines([6], 5, []) raises ValueError
''', r'''
import random
from itertools import product

def rej(*a):
    try:
        wrap_cubic_lines(*a)
    except ValueError:
        return True
    return False

def brute(lens, W, breaks):
    n = len(lens)
    if n == 0:
        return []
    hard = set(breaks) | {n - 1}
    best = None
    for flags in product((0, 1), repeat=n - 1):
        ends = [i for i, f in enumerate(flags) if f] + [n - 1]
        if any(h not in ends for h in hard):
            continue
        s, cost, counts = 0, 0, []
        ok = True
        for e in ends:
            cols = sum(lens[s:e + 1]) + (e - s)
            if cols > W:
                ok = False
                break
            if e not in hard:
                cost += (W - cols) ** 3
            counts.append(e - s + 1)
            s = e + 1
        if ok and (best is None or (cost, counts) < best):
            best = (cost, counts)
    return best[1]

def cost_of(lens, W, breaks, counts):
    hard = set(breaks) | {len(lens) - 1}
    s, total = 0, 0
    for c in counts:
        e = s + c - 1
        cols = sum(lens[s:e + 1]) + c - 1
        assert 1 <= c and cols <= W, (lens, W, counts)
        for h in hard:
            assert not (s <= h < e), "hard break inside a line"
        if e not in hard:
            total += (W - cols) ** 3
        s = e + 1
    assert s == len(lens)
    return total

def fwd_cost(lens, W, breaks):
    n = len(lens)
    hard = set(breaks) | {n - 1}
    INF = float("inf")
    dp = [INF] * (n + 1)
    dp[0] = 0
    for j in range(1, n + 1):
        cols = -1
        for i in range(j - 1, -1, -1):
            if i < j - 1 and i in hard:
                break
            cols += lens[i] + 1
            if cols > W:
                break
            c = 0 if (j - 1) in hard else (W - cols) ** 3
            if dp[i] + c < dp[j]:
                dp[j] = dp[i] + c
    return dp[n]

def same(lens, W, br, exp=None):
    got = wrap_cubic_lines(lens, W, br)
    assert type(got) is list and all(type(x) is int for x in got), got
    if exp is not None:
        assert got == exp, (lens, W, br, got, exp)
    return got

same([3, 3, 3, 3], 7, [], [2, 2])
same([5, 5], 5, [], [1, 1])
same([1, 1, 1, 1, 1, 1, 1], 5, [], [3, 3, 1])
same([2, 4, 1, 2, 4, 4], 9, [], [2, 3, 1])
same([1, 1, 2, 3, 3], 6, [4], [2, 2, 1])
same([5, 1, 1, 5], 6, [1], [1, 1, 1, 1])
same([], 5, [], [])
same([7], 7, [], [1])
same([7], 9, [0], [1])
same([1], 1, [0, 0, 0], [1])
same([4, 4, 4, 4, 4, 4], 9, [], [2, 2, 2])
same([3, 3, 3, 3, 3], 8, [], [2, 2, 1])
same([1, 1, 1, 1, 1, 1], 100, [], [6])
same([1, 1, 1, 1, 1, 1], 100, [2], [3, 3])
same([1, 1, 1, 1, 1, 1], 100, [0, 1, 2, 3, 4, 5], [1] * 6)
same([1, 1, 1, 1, 1, 1], 100, [4], [5, 1])
same([10**6, 10**6], 10**6, [], [1, 1])
same([499999, 500000], 10**6, [], [2])
same([5, 5, 5], 11, [], [2, 1])
same([5, 5, 5], 11, [0], [1, 2])
same([6, 6, 6], 13, [1], [2, 1])
same([2, 2, 2, 2], 5, [], [2, 2])
same([4, 1, 4, 1], 6, [], brute([4, 1, 4, 1], 6, []))
same([2, 2, 2, 2], 3, [], [1, 1, 1, 1])

for bad in (None, (3,), "abc", [0], [-1], [10**6 + 1], [1.0], [True], ["1"], [None], [[1]], [1] * 2001):
    assert rej(bad, 10**6, []), bad
for bad in (0, -1, 10**6 + 1, 5.0, True, None, "5", [5]):
    assert rej([1, 1], bad, []), bad
for bad in (None, (0,), 0, "0", [2], [-1], [0.0], [True], ["0"], [None], [[0]], {0}):
    assert rej([1, 1], 5, bad), bad
assert rej([], 5, [0]) and rej([1], 5, [1]) and rej([1, 2], 5, [0, 2])
assert rej([6], 5, []) and rej([1, 6, 1], 5, []) and rej([1, 2, 6], 5, [0, 1]) and rej([5, 5, 6], 5, [])
assert not rej([5, 5], 5, [])
assert not rej([1] * 2000, 10**6, [])
assert not rej([], 1, [])

random.seed(6027)
for _ in range(300):
    n = random.randint(0, 10)
    W = random.randint(1, 14)
    lens = [random.randint(1, min(W, random.choice([3, 6, 14]))) for _ in range(n)]
    br = [random.randrange(n) for _ in range(random.choice([0, 0, 1, 2]))] if n else []
    got = same(lens, W, br)
    assert got == brute(lens, W, br), (lens, W, br, got, brute(lens, W, br))
for _ in range(20):
    n = random.randint(120, 260)
    W = random.choice([40, 100, 1000, 10**6])
    cap = min(W, random.choice([5, 30, 60]))
    lens = [random.randint(1, cap) for _ in range(n)]
    br = [random.randrange(n) for _ in range(random.choice([0, 3, 15]))]
    got = same(lens, W, br)
    assert cost_of(lens, W, br, got) == fwd_cost(lens, W, br), (n, W)
for k in (3, 4, 5):
    lens = [2] * 30
    W = 2 * k + (k - 1) + 1
    got = same(lens, W, [])
    assert cost_of(lens, W, [], got) == fwd_cost(lens, W, [])
''', r'''
def wrap_cubic_lines(lens, width, breaks):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(lens, list) or len(lens) > 2000 or not all(isint(x) and 1 <= x <= 10 ** 6 for x in lens):
        raise ValueError("lens")
    if not isint(width) or not 1 <= width <= 10 ** 6:
        raise ValueError("width")
    n = len(lens)
    if not isinstance(breaks, list) or not all(isint(b) and 0 <= b < n for b in breaks):
        raise ValueError("breaks")
    if any(x > width for x in lens):
        raise ValueError("word too long")
    hard = set(breaks)
    hard.add(n - 1)
    pre = [0]
    for x in lens:
        pre.append(pre[-1] + x)
    best = [None] * (n + 1)
    best[n] = (0, ())
    for i in range(n - 1, -1, -1):
        cand = None
        for j in range(i + 1, n + 1):
            used = pre[j] - pre[i] + (j - i - 1)
            if used > width:
                break
            cost = 0 if (j - 1) in hard else (width - used) ** 3
            rest_cost, rest = best[j]
            key = (cost + rest_cost, (j - i,) + rest)
            if cand is None or key < cand:
                cand = key
            if (j - 1) in hard:
                break
        best[i] = cand
    return list(best[0][1])
''')

task("v6_28_rank_mini_league", r'''
Write `rank_mini_league(results)` that returns the final order of a league table, using head-to-head tie-breaks among teams level on points.

`results` is a list of at most 400 matches, each a tuple or list (home, away, home_goals, away_goals): home and away are non-empty strs with home != away, the goals are ints 0..99 (bool is not an int). Anything else raises ValueError. The same pairing may occur any number of times, and every occurrence counts as a separate match. The teams are exactly the names that occur in some match. `results == []` gives [].

Points per match: win 3, draw 1 each, loss 0. A team's overall goal difference is goals scored minus goals conceded over all its matches; overall goals scored is the total goals it scored.

Order of the table (best first):
1. Total points, higher first.
2. Teams with exactly the same total points form a group. For every group, build a mini table from only those matches in which BOTH teams belong to that same group (matches against teams outside the group are ignored, and a team that played nobody in its group has all zeros). Within the group compare, in this order: mini points (higher first), mini goal difference (higher), mini goals scored (higher), mini away goals (higher; goals scored by the team in those group matches in which it was the away side). The mini criteria are applied once, to the whole group; do not recompute a mini table for a subset of teams that are still level.
3. Teams still level after step 2 are compared by overall goal difference (higher), then overall goals scored (higher), then team name in ascending code point order (plain str comparison, so "B" < "a").

The result is a list of team names (strs) in table order.

Examples:
rank_mini_league([("A", "B", 0, 0), ("A", "C", 0, 1), ("A", "D", 1, 0), ("B", "C", 0, 0), ("B", "D", 2, 1), ("C", "D", 0, 2)]) == ["B", "C", "A", "D"]
  (A and C both have 4 points; C beat A 1-0 in their only mini match, so C is ahead although A has the better overall goal difference.)
rank_mini_league([("A", "B", 1, 1), ("A", "C", 0, 0), ("A", "D", 1, 1), ("B", "C", 1, 1), ("B", "D", 2, 2), ("C", "D", 1, 1)]) == ["D", "B", "C", "A"]
  (all four have 3 points and identical mini points and difference; mini goals scored are D 4, B 4, C 2, A 2; away goals then give D 4 over B 1 and C 1 over A 0.)
rank_mini_league([("B", "A", 2, 2), ("A", "B", 2, 2)]) == ["A", "B"]
rank_mini_league([("x", "y", 3, 0)]) == ["x", "y"]
rank_mini_league([("a", "b", 0, 0), ("c", "b", 0, 0)]) == ["b", "a", "c"]
rank_mini_league([("a", "a", 1, 1)]) raises ValueError
''', r'''
import random
from functools import cmp_to_key

def rej(r):
    try:
        rank_mini_league(r)
    except ValueError:
        return True
    return False

def table(results, member):
    t = {}
    for h, a, x, y in results:
        if not (member(h) and member(a)):
            continue
        for team in (h, a):
            t.setdefault(team, [0, 0, 0, 0])
        t[h][1] += x - y
        t[a][1] += y - x
        t[h][2] += x
        t[a][2] += y
        t[a][3] += y
        if x > y:
            t[h][0] += 3
        elif y > x:
            t[a][0] += 3
        else:
            t[h][0] += 1
            t[a][0] += 1
    return t

def oracle(results):
    teams = sorted({n for m in results for n in m[:2]})
    overall = table(results, lambda n: True)
    cache = {}
    def mini(team):
        p = overall[team][0]
        if p not in cache:
            grp = {n for n in teams if overall[n][0] == p}
            cache[p] = table(results, lambda n: n in grp)
        return cache[p].get(team, [0, 0, 0, 0])
    def cmp(a, b):
        if overall[a][0] != overall[b][0]:
            return -1 if overall[a][0] > overall[b][0] else 1
        for x, y in ((mini(a), mini(b)), ([overall[a][1], overall[a][2]], [overall[b][1], overall[b][2]])):
            if x != y:
                return -1 if x > y else 1
        return -1 if a < b else 1
    return sorted(teams, key=cmp_to_key(cmp))

def same(results, exp=None):
    got = rank_mini_league(results)
    assert type(got) is list and all(type(x) is str for x in got), got
    ref = oracle(results)
    assert got == ref, (results, got, ref)
    if exp is not None:
        assert got == exp, (results, got, exp)

same([("A", "B", 0, 0), ("A", "C", 0, 1), ("A", "D", 1, 0), ("B", "C", 0, 0), ("B", "D", 2, 1), ("C", "D", 0, 2)], ["B", "C", "A", "D"])
same([("A", "B", 1, 1), ("A", "C", 0, 0), ("A", "D", 1, 1), ("B", "C", 1, 1), ("B", "D", 2, 2), ("C", "D", 1, 1)], ["D", "B", "C", "A"])
same([("B", "A", 2, 2), ("A", "B", 2, 2)], ["A", "B"])
same([("x", "y", 3, 0)], ["x", "y"])
same([("a", "b", 0, 0), ("c", "b", 0, 0)], ["b", "a", "c"])
same([], [])
same([("B", "a", 1, 1)], ["a", "B"])
same([("B", "a", 1, 1), ("a", "B", 1, 1)], ["B", "a"])
same([("a", "B", 1, 1)], ["B", "a"])
same([("a", "b", 1, 0), ("b", "a", 1, 0)], ["a", "b"])
same([("a", "b", 3, 0), ("b", "a", 1, 0), ("a", "c", 0, 5), ("b", "c", 0, 0)], oracle([("a", "b", 3, 0), ("b", "a", 1, 0), ("a", "c", 0, 5), ("b", "c", 0, 0)]))
# head-to-head decides before overall goal difference
same([("p", "q", 1, 0), ("q", "r", 9, 0), ("p", "r", 0, 1), ("r", "z", 0, 0), ("p", "z", 0, 0)], oracle([("p", "q", 1, 0), ("q", "r", 9, 0), ("p", "r", 0, 1), ("r", "z", 0, 0), ("p", "z", 0, 0)]))
same([("m", "n", 0, 1), ("n", "o", 1, 0), ("o", "m", 1, 0), ("m", "x", 8, 0), ("n", "x", 1, 0), ("o", "x", 2, 0)],
     oracle([("m", "n", 0, 1), ("n", "o", 1, 0), ("o", "m", 1, 0), ("m", "x", 8, 0), ("n", "x", 1, 0), ("o", "x", 2, 0)]))
# the mini table of a group ignores matches against outsiders, and a group is by total points only
same([("a", "b", 0, 1), ("a", "c", 5, 0), ("b", "d", 0, 0), ("c", "d", 0, 0), ("a", "d", 0, 0), ("b", "c", 0, 0)],
     oracle([("a", "b", 0, 1), ("a", "c", 5, 0), ("b", "d", 0, 0), ("c", "d", 0, 0), ("a", "d", 0, 0), ("b", "c", 0, 0)]))
same([("a", "b", 99, 99), ("b", "a", 99, 98)], ["b", "a"])
same([("\u00e9", "z", 1, 1), ("Z", "\u00e9", 1, 1)], oracle([("\u00e9", "z", 1, 1), ("Z", "\u00e9", 1, 1)]))
same([["k", "j", 1, 0]], ["k", "j"])

for bad in (None, (), "ab", {("a", "b", 1, 1)}, [("a", "b", 1, 1)] * 401):
    assert rej(bad), bad
for m in (("a", "b", 1), ("a", "b", 1, 1, 1), ("a", "a", 1, 1), ("", "b", 1, 1), ("a", "", 1, 1), (1, "b", 1, 1), ("a", 2, 1, 1),
          (None, "b", 1, 1), ("a", "b", -1, 0), ("a", "b", 0, -1), ("a", "b", 100, 0), ("a", "b", 0, 100), ("a", "b", 1.0, 0),
          ("a", "b", 0, 1.0), ("a", "b", True, 0), ("a", "b", 0, False), ("a", "b", "1", 0), ("a", "b", None, 0), "abcd", None, 7,
          ["a", "b", 1], {"a": 1}, (b"a", "b", 1, 1)):
    assert rej([m]), m
    assert rej([("c", "d", 1, 1), m]), m
assert not rej([("a", "b", 99, 0)] * 400)
assert not rej([("a", "b", 0, 0), ["b", "a", 0, 0]])

random.seed(6028)
for _ in range(500):
    k = random.randint(2, 7)
    pool = random.sample(["A", "B", "C", "D", "E", "F", "G", "a", "b", "Zed", "z"], k)
    if random.random() < 0.4:
        res = [(h, a, random.randint(0, 2), random.randint(0, 2)) for h in pool for a in pool if h != a]
        random.shuffle(res)
        res = res[:random.randint(0, len(res))]
    else:
        res = []
        for _ in range(random.randint(0, 30)):
            h, a = random.sample(pool, 2)
            res.append((h, a, random.randint(0, 3), random.randint(0, 3)))
    same(res)
for _ in range(10):
    pool = ["T%02d" % i for i in range(random.randint(10, 30))]
    res = []
    for _ in range(random.randint(200, 400)):
        h, a = random.sample(pool, 2)
        res.append((h, a, random.choice([0, 0, 1, 1, 2, 3, 99]), random.choice([0, 1, 1, 2])))
    same(res)
''', r'''
def rank_mini_league(results):
    def isgoal(v):
        return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 99
    if not isinstance(results, list) or len(results) > 400:
        raise ValueError("results")
    for r in results:
        if not (isinstance(r, (tuple, list)) and len(r) == 4):
            raise ValueError("match")
        h, a, hg, ag = r
        if not (isinstance(h, str) and isinstance(a, str) and h and a and h != a and isgoal(hg) and isgoal(ag)):
            raise ValueError("match")
    pts, gf, ga = {}, {}, {}
    for h, a, hg, ag in results:
        for t in (h, a):
            pts.setdefault(t, 0)
            gf.setdefault(t, 0)
            ga.setdefault(t, 0)
        gf[h] += hg
        ga[h] += ag
        gf[a] += ag
        ga[a] += hg
        if hg > ag:
            pts[h] += 3
        elif hg < ag:
            pts[a] += 3
        else:
            pts[h] += 1
            pts[a] += 1
    groups = {}
    for t, p in pts.items():
        groups.setdefault(p, set()).add(t)
    mini = {t: [0, 0, 0, 0] for t in pts}
    for h, a, hg, ag in results:
        if pts[h] != pts[a]:
            continue
        mh, ma = mini[h], mini[a]
        mh[1] += hg - ag
        ma[1] += ag - hg
        mh[2] += hg
        ma[2] += ag
        ma[3] += ag
        if hg > ag:
            mh[0] += 3
        elif hg < ag:
            ma[0] += 3
        else:
            mh[0] += 1
            ma[0] += 1
    def key(t):
        m = mini[t]
        return (-pts[t], -m[0], -m[1], -m[2], -m[3], -(gf[t] - ga[t]), -gf[t], t)
    return sorted(pts, key=key)
''')

task("v6_29_sweep_ring_state", r'''
Write `sweep_ring_state(bits, rule, steps)` that runs a one-dimensional binary cellular automaton on a ring whose cells are updated one after another within a step, and returns the final configuration.

`bits` is a str of 1 to 16 characters, each '0' or '1'; character i is cell i, and the cells form a ring (cell n-1 is next to cell 0, n = len(bits)). `rule` is an int 0..255 and `steps` is an int 0..10**18 (bool is not an int for either). Anything else raises ValueError. The result is a str of the same length.

One step is a sweep over the cells in the order 0, 1, ..., n-1. Each cell is updated IN PLACE, immediately, using the values the cells hold at that moment: when cell i is updated, its left neighbour is cell (i-1) mod n and its right neighbour is cell (i+1) mod n, each read as it currently is. So cells 1..n-1 see the already-updated value of their left neighbour, cell 0 sees the old value of cell n-1 (not yet updated), cells 0..n-2 see the old value of their right neighbour, and cell n-1 sees the NEW value of cell 0. With a single cell (n == 1) both neighbours are the cell itself; with n == 2 the neighbours of a cell are both the other cell.

The new value of a cell with left neighbour l, own value c and right neighbour r (each 0 or 1) is bit number 4*l + 2*c + r of `rule` (Wolfram numbering: for rule 110 the pattern 111 gives bit 7 = 0 and the pattern 110 gives bit 6 = 1).

steps can be 10**18, so the steps cannot all be simulated one by one; the configuration space has only 2**n states, so the sequence of configurations is eventually periodic. steps == 0 returns bits unchanged.

Worked example, rule 110, bits "0110", one step: cell 0 sees (l, c, r) = (0, 0, 1) -> 1; cell 1 sees (1, 1, 1) -> 0; cell 2 sees (0, 1, 0) -> 1; cell 3 sees (1, 0, 1) with the new cell 0 on its right -> 1. The result is "1011".

Examples:
sweep_ring_state("0110", 110, 0) == "0110"
sweep_ring_state("0110", 110, 1) == "1011"
sweep_ring_state("0110", 110, 3) == "0111"
sweep_ring_state("0110", 110, 10**18) == "1011"
sweep_ring_state("1", 1, 1) == "0"
sweep_ring_state("0000", 255, 1) == "1111"
sweep_ring_state("1000", 170, 1) == "0000"
sweep_ring_state("0001000100010001", 30, 10**18) == "0101010101010101"
sweep_ring_state("1001", 204, 10**18) == "1001"
''', r'''
import random

def rej(*a):
    try:
        sweep_ring_state(*a)
    except ValueError:
        return True
    return False

def osweep(s, rule):
    n = len(s)
    new = ""
    for i in range(n):
        left = new[-1] if i > 0 else s[-1]
        mid = s[i]
        if i < n - 1:
            right = s[i + 1]
        else:
            right = new[0] if i > 0 else s[0]
        new += str((rule >> int(left + mid + right, 2)) & 1)
    return new

def direct(s, rule, k):
    for _ in range(k):
        s = osweep(s, rule)
    return s

def doubling(s, rule, k):
    n = len(s)
    f = [int(osweep(format(x, "0%db" % n), rule), 2) for x in range(1 << n)]
    x = int(s, 2)
    while k:
        if k & 1:
            x = f[x]
        f = [f[f[y]] for y in range(1 << n)]
        k >>= 1
    return format(x, "0%db" % n)

def same(bits, rule, steps, exp=None):
    got = sweep_ring_state(bits, rule, steps)
    assert type(got) is str and len(got) == len(bits), got
    if exp is not None:
        assert got == exp, (bits, rule, steps, got, exp)
    return got

same("0110", 110, 0, "0110")
same("0110", 110, 1, "1011")
same("0110", 110, 2, "1101")
same("0110", 110, 3, "0111")
same("0110", 110, 10**18, "1011")
same("1", 1, 1, "0")
same("0", 1, 1, "1")
same("1", 0, 1, "0")
same("0", 255, 10**18, "1")
same("0000", 255, 1, "1111")
same("1000", 170, 1, "0000")
same("0001000100010001", 30, 10**18, "0101010101010101")
same("1001", 204, 10**18, "1001")
same("10", 90, 1, "00")
same("1" * 16, 0, 1, "0" * 16)
same("1011001110001111", 204, 10**18, "1011001110001111")
same("1011001110001111", 204, 7, "1011001110001111")
for s in ("0", "1", "01", "10", "110", "0101"):
    same(s, 204, 12345, s)
    same(s, 0, 1, "0" * len(s))
    same(s, 255, 2, "1" * len(s))
    same(s, 85, 0, s)
assert direct("0110", 110, 3) == "0111" and direct("0110", 110, 1) == "1011"

for bad in ("", "0" * 17, "012", "01 ", "a", None, 101, [0, 1], b"01", ("0", "1"), "\u0660\u0661", "0\n"):
    assert rej(bad, 30, 5), bad
for bad in (-1, 256, 30.0, True, False, None, "30", [30], 10**9):
    assert rej("0110", bad, 5), bad
for bad in (-1, 10**18 + 1, 5.0, True, False, None, "5", [5], 10**30):
    assert rej("0110", 30, bad), bad
assert not rej("0" * 16, 255, 10**18) and not rej("1", 0, 0) and not rej("01", 0, 10**18)

random.seed(6029)
for _ in range(250):
    n = random.randint(1, 9)
    s = "".join(random.choice("01") for _ in range(n))
    rule = random.randint(0, 255)
    k = random.choice([0, 1, 2, 3, random.randint(0, 40)])
    same(s, rule, k, direct(s, rule, k))
for _ in range(60):
    n = random.randint(1, 8)
    s = "".join(random.choice("01") for _ in range(n))
    rule = random.randint(0, 255)
    k = random.choice([10**18, 10**18 - 1, random.randint(1, 10**18), random.randint(41, 5000), 2**59 + 1])
    same(s, rule, k, doubling(s, rule, k))
for _ in range(3):
    n = random.randint(10, 11)
    s = "".join(random.choice("01") for _ in range(n))
    rule = random.choice([30, 90, 110, 150, random.randint(0, 255)])
    k = random.randint(10**17, 10**18)
    same(s, rule, k, doubling(s, rule, k))
# composition: running a then b steps equals a + b steps, also for 16 cells and huge counts
for _ in range(6):
    n = random.randint(12, 16)
    s = "".join(random.choice("01") for _ in range(n))
    rule = random.choice([30, 90, 110, 150, 45, 54, random.randint(0, 255)])
    a = random.randint(1, 10**18 // 2)
    b = random.randint(1, 10**18 // 2)
    mid = same(s, rule, a)
    assert same(mid, rule, b) == same(s, rule, a + b)
    assert same(s, rule, a + 1) == osweep(mid, rule)
''', r'''
def sweep_ring_state(bits, rule, steps):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(bits, str) or not 1 <= len(bits) <= 16 or any(ch not in "01" for ch in bits):
        raise ValueError("bits")
    if not isint(rule) or not 0 <= rule <= 255:
        raise ValueError("rule")
    if not isint(steps) or not 0 <= steps <= 10 ** 18:
        raise ValueError("steps")
    n = len(bits)
    table = [(rule >> k) & 1 for k in range(8)]

    def advance(s):
        c = [int(ch) for ch in s]
        for i in range(n):
            c[i] = table[4 * c[i - 1] + 2 * c[i] + c[(i + 1) % n]]
        return "".join(map(str, c))

    seen = {}
    order = []
    cur = bits
    t = 0
    while t < steps:
        if cur in seen:
            start = seen[cur]
            period = t - start
            return order[start + (steps - start) % period]
        seen[cur] = t
        order.append(cur)
        cur = advance(cur)
        t += 1
    return cur
''')

task("v6_30_replay_editor_log", r'''
Write `replay_editor_log(commands)` that replays a log of commands on a one-line text editor with undo and redo, and returns (text, cursor, undo_depth, redo_depth).

`commands` is a list of at most 2000 tuples or lists; anything else raises ValueError. The editor starts with text "" and cursor 0 (a position between characters). Commands (names are case sensitive):
  ("type", s)    s is a str of 1 to 20 characters (any characters). Insert s at the cursor; the cursor moves to just after it.
  ("back", n)    n is an int 1..10**6 (bool is not an int). Delete the min(n, cursor) characters before the cursor; the cursor moves to the start of the deleted part.
  ("del", n)     same range for n. Delete the min(n, len(text) - cursor) characters after the cursor; the cursor stays.
  ("left", n), ("right", n)    n as above. Move the cursor by n, clamped to 0 and len(text).
  ("home",), ("end",)    move the cursor to 0 / to len(text).
  ("undo",), ("redo",)
A wrong arity, an unknown name, or an argument of the wrong type or range raises ValueError.

Undo groups. An undo group is the unit that "undo" reverts.
- A maximal run of "type" commands that directly follow one another in the log (nothing between them, not even a no-effect command) is one group.
- Every "back" or "del" that actually deletes at least one character is a group of its own.
- Nothing else makes a group: moves, home, end, undo, redo, and a "back" or "del" that deletes nothing (cursor at 0 or at the end). Each of these also ends a run of "type" commands, even if it changes nothing (a clamped "left", an "undo" with nothing to undo, ...).
- Any command that creates or extends a group empties the redo stack. A command that creates no group (including a "back" or "del" that deletes nothing) leaves the redo stack alone.

"undo" takes the most recent group off the undo stack, puts the text back as it was just before the group's first command, puts the cursor where it was just before that command, and pushes the group onto the redo stack. With an empty undo stack it does nothing. "redo" takes the most recent group off the redo stack and puts the text and the cursor back as they were just after the group's last command (a typed run keeps its whole effect), and pushes the group onto the undo stack; with an empty redo stack it does nothing. Cursor moves are not undoable; an undo restores the cursor stored with the group, whatever moves happened since.

The result is (text, cursor, len(undo stack), len(redo stack)) with types (str, int, int, int).

Examples:
replay_editor_log([("type", "ab"), ("type", "cd"), ("left", 1), ("type", "X"), ("undo",)]) == ("abcd", 3, 1, 1)
replay_editor_log([("type", "hello"), ("back", 2), ("back", 1), ("undo",), ("undo",), ("redo",)]) == ("hel", 3, 2, 1)
replay_editor_log([("type", "ab"), ("undo",), ("back", 1), ("redo",)]) == ("ab", 2, 1, 0)
replay_editor_log([("type", "a"), ("del", 1), ("type", "b")]) == ("ab", 2, 2, 0)   # the no-effect "del" ends the run
replay_editor_log([("type", "abc"), ("home",), ("del", 1), ("del", 5), ("del", 1), ("undo",), ("undo",), ("undo",)]) == ("", 0, 0, 3)
replay_editor_log([]) == ("", 0, 0, 0)
''', r'''
import random

def rej(c):
    try:
        replay_editor_log(c)
    except ValueError:
        return True
    return False

def oracle(cmds):
    st = ("", 0)
    undo, redo = [], []
    run = False
    for c in cmds:
        txt, cur = st
        n = c[0]
        if n == "type":
            new = (txt[:cur] + c[1] + txt[cur:], cur + len(c[1]))
            if run:
                undo[-1][1] = new
            else:
                undo.append([st, new])
                run = True
            redo = []
            st = new
            continue
        run = False
        if n in ("back", "del"):
            if n == "back":
                k = min(c[1], cur)
                new = (txt[:cur - k] + txt[cur:], cur - k)
            else:
                k = min(c[1], len(txt) - cur)
                new = (txt[:cur] + txt[cur + k:], cur)
            if k:
                undo.append([st, new])
                redo = []
                st = new
        elif n == "left":
            st = (txt, max(0, cur - c[1]))
        elif n == "right":
            st = (txt, min(len(txt), cur + c[1]))
        elif n == "home":
            st = (txt, 0)
        elif n == "end":
            st = (txt, len(txt))
        elif n == "undo":
            if undo:
                g = undo.pop()
                st = g[0]
                redo.append(g)
        elif n == "redo":
            if redo:
                g = redo.pop()
                st = g[1]
                undo.append(g)
    return (st[0], st[1], len(undo), len(redo))

def same(cmds, exp=None):
    got = replay_editor_log(cmds)
    assert type(got) is tuple and len(got) == 4, got
    assert type(got[0]) is str and all(type(x) is int for x in got[1:]), got
    ref = oracle(cmds)
    assert got == ref, (cmds, got, ref)
    if exp is not None:
        assert got == exp, (cmds, got, exp)

same([("type", "ab"), ("type", "cd"), ("left", 1), ("type", "X"), ("undo",)], ("abcd", 3, 1, 1))
same([("type", "hello"), ("back", 2), ("back", 1), ("undo",), ("undo",), ("redo",)], ("hel", 3, 2, 1))
same([("type", "ab"), ("back", 5), ("back", 1), ("undo",), ("type", "Z"), ("redo",)], ("abZ", 3, 2, 0))
same([("type", "ab"), ("undo",), ("back", 1), ("redo",)], ("ab", 2, 1, 0))
same([("type", "a"), ("del", 1), ("type", "b")], ("ab", 2, 2, 0))
same([("type", "abc"), ("home",), ("del", 1), ("del", 5), ("del", 1), ("undo",), ("undo",), ("undo",)], ("", 0, 0, 3))
same([], ("", 0, 0, 0))
same([("undo",), ("redo",), ("undo",)], ("", 0, 0, 0))
same([("left", 4), ("right", 4), ("home",), ("end",), ("back", 1), ("del", 1)], ("", 0, 0, 0))
same([("type", "a"), ("left", 1), ("type", "b")], ("ba", 1, 2, 0))
same([("type", "a"), ("right", 1), ("type", "b")], ("ab", 2, 2, 0))
same([("type", "a"), ("redo",), ("type", "b")], ("ab", 2, 2, 0))
same([("type", "a"), ("undo",), ("redo",), ("type", "b")], ("ab", 2, 2, 0))
same([("type", "a"), ("type", "b"), ("undo",), ("redo",), ("undo",)], ("", 0, 0, 1))
same([("type", "xyz"), ("left", 2), ("back", 1), ("home",), ("undo",)], ("xyz", 1, 1, 1))
same([("type", "xyz"), ("left", 2), ("del", 1), ("end",), ("undo",), ("undo",)], ("", 0, 0, 2))
same([("type", "xyz"), ("left", 2), ("del", 1), ("end",), ("undo",), ("undo",), ("redo",), ("redo",)], ("xz", 1, 2, 0))
same([("type", "ab"), ("back", 1), ("type", "c"), ("undo",), ("undo",), ("undo",), ("redo",), ("redo",), ("redo",)], ("ac", 2, 3, 0))
same([("type", "ab"), ("back", 1), ("undo",), ("del", 1), ("redo",)], ("a", 1, 2, 0))
same([("type", "ab"), ("left", 1), ("del", 1), ("undo",), ("redo",), ("redo",)], ("a", 1, 2, 0))
same([("type", "one"), ("type", " two"), ("home",), ("type", ">"), ("end",), ("type", "!"), ("undo",), ("undo",)], ("one two", 0, 1, 2))
same([("type", "\u00e9\n\t "), ("left", 2), ("type", "\u00fc")], ("\u00e9\n\u00fc\t ", 3, 2, 0))
same([["type", "q"], ["back", 1], ["undo"]], ("q", 1, 1, 1))
same([("type", "ab"), ("undo",), ("type", "cd"), ("undo",), ("redo",), ("redo",)], ("cd", 2, 1, 0))
same([("left", 1), ("type", "a"), ("left", 1), ("left", 1), ("type", "b"), ("undo",)], ("a", 0, 1, 1))

for bad in (None, (), "type", {"type": "a"}, [("type", "a")] * 2001, 5):
    assert rej(bad), bad
for bad in (("type",), ("type", "a", "b"), ("type", ""), ("type", "a" * 21), ("type", 5), ("type", None), ("type", b"a"), ("type", ["a"]),
            ("back",), ("back", 0), ("back", -1), ("back", 10**6 + 1), ("back", 1.0), ("back", True), ("back", "1"), ("back", None), ("back", 1, 1),
            ("del",), ("del", 0), ("del", -3), ("del", 2.5), ("del", False), ("left",), ("left", 0), ("left", 10**6 + 1), ("left", True),
            ("right",), ("right", 0), ("right", "2"), ("right", 1, 2), ("home", 1), ("end", 0), ("undo", 1), ("redo", 1), ("redo", None),
            ("Type", "a"), ("TYPE", "a"), ("UNDO",), ("insert", "a"), ("", "a"), (), [], (1,), (None,), (5, "a"), "type", "undo", None, 7, {"type": 1}):
    assert rej([bad]), bad
    assert rej([("type", "a"), bad]), bad
    assert rej([bad, ("type", "a")]), bad
assert not rej([("type", "a" * 20), ("back", 10**6), ("del", 10**6), ("left", 10**6), ("right", 10**6), ["home"], ["end"], ("undo",), ("redo",)])
assert not rej([("undo",)] * 2000)

random.seed(6030)
def rcmd():
    k = random.random()
    if k < 0.28:
        return ("type", "".join(random.choice("abc xy") for _ in range(random.randint(1, 3))))
    if k < 0.38:
        return ("back", random.randint(1, 4))
    if k < 0.46:
        return ("del", random.randint(1, 4))
    if k < 0.54:
        return ("left", random.randint(1, 3))
    if k < 0.62:
        return ("right", random.randint(1, 3))
    if k < 0.66:
        return ("home",)
    if k < 0.70:
        return ("end",)
    if k < 0.85:
        return ("undo",)
    return ("redo",)
for _ in range(700):
    same([rcmd() for _ in range(random.randint(0, 40))])
for _ in range(12):
    same([rcmd() for _ in range(random.randint(300, 600))])
# long log: many 20-character runs, then deep undo and redo
cmds = []
for i in range(300):
    cmds.append(("type", chr(97 + i % 26) * 20))
    if i % 3 == 0:
        cmds.append(("left", 7))
    if i % 5 == 0:
        cmds.append(("del", 13))
cmds += [("undo",)] * 200 + [("redo",)] * 150
same(cmds)
r = replay_editor_log([("type", "z" * 20)] * 100 + [("undo",)])
assert r == ("", 0, 0, 1), r
r = replay_editor_log([("type", "z" * 20), ("left", 1)] * 100 + [("undo",)] * 50)
assert r[2] == 50 and r[3] == 50 and len(r[0]) == 1000, r
''', r'''
def replay_editor_log(commands):
    def isint(v):
        return isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(commands, list) or len(commands) > 2000:
        raise ValueError("commands")
    arity = {"type": 2, "back": 2, "del": 2, "left": 2, "right": 2, "home": 1, "end": 1, "undo": 1, "redo": 1}
    for c in commands:
        if not isinstance(c, (tuple, list)) or not c or not isinstance(c[0], str) or arity.get(c[0]) != len(c):
            raise ValueError("command")
        if c[0] == "type":
            if not isinstance(c[1], str) or not 1 <= len(c[1]) <= 20:
                raise ValueError("type")
        elif len(c) == 2 and not (isint(c[1]) and 1 <= c[1] <= 10 ** 6):
            raise ValueError("count")
    text, cur = "", 0
    undo, redo = [], []
    open_run = False

    def apply(ops, forward):
        nonlocal text
        seq = ops if forward else reversed(ops)
        for kind, pos, s in seq:
            if (kind == "ins") == forward:
                text = text[:pos] + s + text[pos:]
            else:
                text = text[:pos] + text[pos + len(s):]

    for c in commands:
        name = c[0]
        if name == "type":
            op = ("ins", cur, c[1])
            if open_run:
                undo[-1][0].append(op)
                undo[-1][2] = cur + len(c[1])
            else:
                undo.append([[op], cur, cur + len(c[1])])
                open_run = True
            redo.clear()
            text = text[:cur] + c[1] + text[cur:]
            cur += len(c[1])
            continue
        open_run = False
        if name in ("back", "del"):
            if name == "back":
                k = min(c[1], cur)
                pos = cur - k
            else:
                k = min(c[1], len(text) - cur)
                pos = cur
            if k:
                s = text[pos:pos + k]
                text = text[:pos] + text[pos + k:]
                undo.append([[("rem", pos, s)], cur, pos])
                redo.clear()
                cur = pos
        elif name == "left":
            cur = max(0, cur - c[1])
        elif name == "right":
            cur = min(len(text), cur + c[1])
        elif name == "home":
            cur = 0
        elif name == "end":
            cur = len(text)
        elif name == "undo":
            if undo:
                g = undo.pop()
                apply(g[0], False)
                cur = g[1]
                redo.append(g)
        else:
            if redo:
                g = redo.pop()
                apply(g[0], True)
                cur = g[2]
                undo.append(g)
    return (text, cur, len(undo), len(redo))
''')

TASKS = T
