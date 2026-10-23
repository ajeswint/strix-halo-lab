#!/usr/bin/env python3
"""Tests for scripts/llmctl.py. No GPU, no model: LLMCTL_TEST_DIR swaps in test-only endpoints (a stub HTTP
server in a transient user unit, llmctl-test on :18081), a throwaway DB and a fake GTT file, and removes the
real endpoints. Safe to run anytime, including with a model resident.
Usage: python3 scripts/llmctl-test.py
"""
import os, pty, re, sqlite3, subprocess, sys, tempfile, time
from pathlib import Path

CTL = str(Path(__file__).resolve().parent / "llmctl.py")
tmp = tempfile.mkdtemp(prefix="llmctl-test-")
ENV = {**os.environ, "LLMCTL_TEST_DIR": tmp}
GIB = 1 << 30
fails, n = 0, 0


def gtt(v):
    if v is None:
        Path(tmp, "gtt").unlink(missing_ok=True)
    else:
        Path(tmp, "gtt").write_text(str(v))


def ctl(*args, stdin=subprocess.DEVNULL):
    r = subprocess.run([sys.executable, CTL, *args], env=ENV, capture_output=True, text=True, stdin=stdin, timeout=120)
    return r.returncode, r.stdout + r.stderr


def ctl_tty(*args, answer):
    """Run llmctl on a pty and type `answer` at its prompt."""
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(ENV)
        os.execv(sys.executable, [sys.executable, CTL, *args])
    out = b""
    time.sleep(1.5)
    os.write(fd, answer.encode() + b"\n")
    while True:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def rows():
    db = sqlite3.connect(Path(tmp, "test.db"))
    return db.execute("SELECT id, endpoint, state, note FROM sessions ORDER BY id").fetchall()


GROUP_UNITS = ("llmctl-test-a", "llmctl-test-b", "llmctl-test-c")


def unit_active(unit="llmctl-test"):
    return subprocess.run(["systemctl", "--user", "is-active", "-q", unit]).returncode == 0


def check(name, cond, detail=""):
    global fails, n
    n += 1
    if not cond:
        fails += 1
        print(f"FAIL {name}: {detail}")


def reset():
    for u in ("llmctl-test", *GROUP_UNITS):
        subprocess.run(["systemctl", "--user", "stop", u], capture_output=True)
        subprocess.run(["systemctl", "--user", "reset-failed", u], capture_output=True)
    Path(tmp, "test.db").unlink(missing_ok=True)
    for ext in ("-wal", "-shm"):
        Path(tmp, "test.db" + ext).unlink(missing_ok=True)
    gtt(GIB // 2)


try:
    # 1 happy path: invite -> ACTIVE -> run -> bye -> ENDED
    reset()
    rc, out = ctl("invite", "test")
    check("invite test rc", rc == 0, out)
    check("invite ACTIVE row", [r[2] for r in rows()] == ["ACTIVE"], rows())
    check("ACTIVE note compares delta to delta", re.search(r"\+[\d.]+ over the [\d.]+ GiB before \(expected \+0 GiB\)", rows()[0][3] or ""), rows())
    check("unit running", unit_active())
    rc, out = ctl("status")
    check("status ACTIVE", rc == 0 and "state: ACTIVE test" in out, out)
    rc, out = ctl("invite", "test")
    check("second invite refused (one session)", rc == 3 and "bye or swap first" in out, out)
    rc, out = ctl("run", "--", sys.executable, "-c", "print('hello')")
    check("run ok", rc == 0 and "memory.peak=" in out and "hello" in out, out)
    check("run noted on the session", "memory.peak" in (rows()[0][3] or ""), rows())
    rc, out = ctl("bye")
    check("bye rc", rc == 0, out)
    check("bye ENDED, unit stopped", rows()[0][2] == "ENDED" and not unit_active(), rows())
    rc, out = ctl("run", "--", "true")
    check("run without a session refused", rc == 3 and "ACTIVE session" in out, out)

    # 2 failed preflight and failed start leave nothing resident
    reset()
    rc, out = ctl("invite", "testbad")
    check("failed preflight rc", rc == 1 and "NOT READY" in out, out)
    check("failed preflight row", rows()[0][2] == "FAILED" and "preflight NOT READY" in rows()[0][3] and not unit_active(), rows())
    rc, out = ctl("invite", "teststartfail")
    check("failed start rc", rc == 1, out)
    check("failed start row", rows()[-1][2] == "FAILED" and not unit_active(), rows())

    # 3 ABORTED after the process is killed
    reset()
    ctl("invite", "test")
    subprocess.run(["systemctl", "--user", "kill", "-s", "SIGKILL", "llmctl-test"], check=True)
    time.sleep(1)
    rc, out = ctl("status")
    check("killed process -> ABORTED", rows()[0][2] == "ABORTED" and "ABORTED" in out, (rows(), out))
    subprocess.run(["systemctl", "--user", "reset-failed", "llmctl-test"], capture_output=True)
    rc, out = ctl("invite", "test")
    check("invite works again after ABORTED", rc == 0, out)
    ctl("bye")

    # 4 UNOWNED: GTT high with no session; a resident registered unit with no session
    reset()
    gtt(30 * GIB)
    rc, out = ctl("status")
    check("UNOWNED status", rc == 3 and "UNOWNED" in out, out)
    rc, out = ctl("invite", "test")
    check("UNOWNED invite refused", rc == 3 and "UNOWNED" in out, out)
    rc, out = ctl("bye")
    check("bye on GTT with no unit refuses", rc == 3, out)
    gtt(GIB // 2)
    subprocess.run(["systemd-run", "--user", "-q", "--unit=llmctl-test", "--collect", "sleep", "300"], check=True)
    rc, out = ctl("status")
    check("resident unit with no row is UNOWNED", rc == 3 and "unit active: llmctl-test" in out, out)
    rc, out = ctl("bye")
    check("bye ends the unowned unit", rc == 0 and not unit_active() and rows()[-1][1] == "unowned:llmctl-test"
          and rows()[-1][2] == "ENDED", (out, rows()))

    # 5 unreadable GTT fails closed
    reset()
    gtt(None)
    rc, out = ctl("invite", "test")
    check("unreadable GTT: invite refused", rc == 3 and "unreadable" in out and not unit_active(), out)
    rc, out = ctl("swap", "test")
    check("unreadable GTT: swap refused", rc == 3 and "unreadable" in out and not unit_active(), out)
    rc, out = ctl("status")
    check("unreadable GTT: status says so", rc == 3 and "UNREADABLE" in out, out)

    # 6 ending a confirm_end endpoint needs a TTY and the word yes
    reset()
    ctl("invite", "testconf")
    rc, out = ctl("bye")
    check("no TTY: bye refused", rc == 3 and "interactive terminal" in out, out)
    check("no TTY: session still ACTIVE", rows()[0][2] == "ACTIVE" and unit_active(), rows())
    rc, out = ctl("swap", "test")
    check("no TTY: swap away refused", rc == 3 and rows()[0][2] == "ACTIVE" and len(rows()) == 1, (out, rows()))
    rc, out = ctl_tty("bye", answer="no")
    check("TTY, answer no: refused, still ACTIVE", rc == 3 and rows()[0][2] == "ACTIVE", (rc, out, rows()))
    rc, out = ctl_tty("bye", answer="yes")
    check("TTY, answer yes: ENDED", rc == 0 and rows()[0][2] == "ENDED" and not unit_active(), (rc, out, rows()))

    # 7 swap: one recorded transition; a failing invite half leaves nothing resident
    reset()
    ctl("invite", "test")
    rc, out = ctl("swap", "testconf")
    check("swap rc", rc == 0, out)
    r = rows()
    check("swap rows", [x[2] for x in r] == ["ENDED", "ACTIVE"] and "swap -> testconf" in r[0][3]
          and "swap from session 1" in r[1][3], r)
    ctl_tty("bye", answer="yes")
    reset()
    ctl("invite", "test")
    rc, out = ctl("swap", "teststartfail")
    r = rows()
    check("swap with failing invite: FAILED, nothing resident", rc == 1 and [x[2] for x in r] == ["ENDED", "FAILED"]
          and not unit_active(), (out, r))

    # 8 run: cgroup cap kills the child, the session survives; RLIMIT_AS gives MemoryError
    reset()
    ctl("invite", "test")
    big = "x = bytearray(1 << 30); print('allocated')"
    rc, out = ctl("run", "--mem", "128M", "--as", "4G", "--", sys.executable, "-c", big)
    check("cap kill exits 137 with 'memory cap'", rc == 137 and "memory cap" in out and "allocated" not in out, (rc, out))
    check("session untouched by the cap kill", rows()[0][2] == "ACTIVE" and unit_active(), rows())
    rc, out = ctl("run", "--mem", "2G", "--as", "512M", "--", sys.executable, "-c", big)
    check("RLIMIT_AS: MemoryError, not a cap kill", rc != 0 and rc != 137 and "MemoryError" in out and "memory cap" not in out, (rc, out))
    rc, out = ctl("run", "--mem", "2G", "--", sys.executable, "-c", "x = bytearray(300 << 20); print('ok300')")
    check("memory.peak recorded (300 MiB alloc)", rc == 0 and "ok300" in out
          and any(int(w.split("=")[1]) >= 300 for w in out.split() if w.startswith("memory.peak=")), out)
    ctl("bye")

    # 9 the unique partial index is the one-live-session rule
    reset()
    ctl("invite", "test")
    try:
        sqlite3.connect(Path(tmp, "test.db")).execute("INSERT INTO sessions (endpoint, state) VALUES ('test', 'ACTIVE')")
        check("unique index blocks a second live row", False, "insert succeeded")
    except sqlite3.IntegrityError:
        check("unique index blocks a second live row", True)
    ctl("bye")

    # 10 the real registry is not reachable in test mode, and real endpoints exist outside it
    rc, out = ctl("invite", "qwen")
    check("test mode hides the real endpoints", rc == 2 and "unknown endpoint" in out, out)
    rc, out = ctl("invite", "crawdad")
    check("test mode hides the real group", rc == 2 and "unknown endpoint" in out, out)

    # 11 group: one session over several units, each on its own port
    reset()
    rc, out = ctl("invite", "testgroup")
    check("group invite rc", rc == 0 and ":18082, :18083" in out, out)
    check("group: one ACTIVE row, both members up", [r[2] for r in rows()] == ["ACTIVE"]
          and unit_active("llmctl-test-a") and unit_active("llmctl-test-b"), rows())
    rc, out = ctl("status")
    check("group status ACTIVE, member units listed", rc == 0 and "state: ACTIVE testgroup" in out
          and "unit llmctl-test-a: active" in out and "unit llmctl-test-b: active" in out, out)
    rc, out = ctl("invite", "test")
    check("nothing loads beside a group", rc == 3 and "bye or swap first" in out and not unit_active(), out)
    rc, out = ctl("run", "--", sys.executable, "-c", "print('ingroup')")
    check("run inside a group session", rc == 0 and "ingroup" in out, out)
    rc, out = ctl("bye")
    check("group bye stops every member", rc == 0 and rows()[0][2] == "ENDED"
          and not any(unit_active(u) for u in GROUP_UNITS), (out, rows()))

    # 12 group: a member gone while ACTIVE -> ABORTED; the survivor is UNOWNED and bye ends it
    reset()
    ctl("invite", "testgroup")
    subprocess.run(["systemctl", "--user", "kill", "-s", "SIGKILL", "llmctl-test-b"], check=True)
    time.sleep(1)
    rc, out = ctl("status")
    check("member killed -> ABORTED, survivor UNOWNED", rows()[0][2] == "ABORTED" and rc == 3
          and "unit active: llmctl-test-a" in out, (rows(), out))
    rc, out = ctl("bye")
    check("bye ends the surviving member", rc == 0 and not unit_active("llmctl-test-a"), (out, rows()))

    # 13 group: a member that fails to start stops the members already up; nothing resident
    reset()
    rc, out = ctl("invite", "testgroupfail")
    check("group member start fails: FAILED", rc == 1 and rows()[-1][2] == "FAILED" and "testgroup.bad" in (rows()[-1][3] or ""), (out, rows()))
    check("group member start fails: nothing resident", not any(unit_active(u) for u in GROUP_UNITS))

    # 14 group: invite options are refused (members run at the measured defaults)
    reset()
    rc, out = ctl("invite", "testgroup", "--ctx", "65536")
    check("group invite with options refused", rc == 2 and "no options" in out and not rows(), out)

    # 15 the real group's argv, no load: one preflight over all five files with the summed need, then each member on
    # its own port with the group preflight marker; single endpoints keep :8081 and their own preflight
    probe = ("import importlib.util,sys,json\n"
             "s=importlib.util.spec_from_file_location('l',sys.argv[1]);l=importlib.util.module_from_spec(s);s.loader.exec_module(l)\n"
             "g=l.REGISTRY['crawdad'];o={'backend':'vk','ctx':None,'np':1}\n"
             "print(json.dumps({'need':g.gtt_need,'members':[p.name for p in l.parts(g)],"
             "'argv':[l.start_argv(p,o) for p in l.parts(g)],'single':l.start_argv(l.REGISTRY['qwen32'],o),"
             "'units':sorted({p.unit for p in l.all_units()})}))\n")
    env = {k: v for k, v in os.environ.items() if k != "LLMCTL_TEST_DIR"}
    r = subprocess.run([sys.executable, "-I", "-c", probe, CTL], env=env, capture_output=True, text=True)
    import json
    try:
        d = json.loads(r.stdout)
    except ValueError:
        d = {}
    check("real group: five members in order, need 64.9",
          d.get("members") == ["crawdad.qwen32", "crawdad.r1d32", "crawdad.rag1", "crawdad.rag2", "crawdad.rerank"]
          and d.get("need") == 64.9, (d, r.stderr))
    want = [("8082", "qwen32", "32768"), ("8083", "r1d32", "32768"), ("8084", "rag1", "8192"), ("8085", "rag2", "8192"), ("8086", "rerank", "8192")]
    check("real group: member argv", [(a[1].split("=")[1], a[5], a[7]) for a in d.get("argv", [])] == want
          and all(a[0] == "env" and a[2] == "LLM_SERVE_NO_PREFLIGHT=llmctl-group" and a[4] == "start" for a in d.get("argv", [])), d.get("argv"))
    check("real single endpoint unchanged", d.get("single", [""])[0].endswith("llm-serve.sh")
          and d.get("single", [])[1:] == ["start", "qwen32", "vk", "32768", "1"], d.get("single"))
    check("real units: 8081-8086 and llama-deepseek", d.get("units") == ["llama-deepseek", "llm-8081", "llm-8082", "llm-8083",
                                                                         "llm-8084", "llm-8085", "llm-8086"], d.get("units"))
finally:
    for u in ("llmctl-test", *GROUP_UNITS):
        subprocess.run(["systemctl", "--user", "stop", u], capture_output=True)
        subprocess.run(["systemctl", "--user", "reset-failed", u], capture_output=True)

print(f"{n - fails}/{n} passed")
sys.exit(1 if fails else 0)
