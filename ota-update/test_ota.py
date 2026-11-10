#!/usr/bin/env python3
"""End-to-end OTA test on one machine, no Pi or systemd needed.

fake app repo -> release.py -> local HTTP update server -> update.py on a fake device folder.
Run with a Python 3.11.4+ that has pycryptodome:  python test_ota.py
"""
import http.server, os, shutil, subprocess, sys, tempfile, threading
from pathlib import Path

from Crypto.PublicKey import ECC

HERE = Path(__file__).resolve().parent
PY = sys.executable
work = Path(tempfile.mkdtemp(prefix="ota-test-"))
repo, dist, device = work / "repo", work / "dist", work / "device"
failures = []


def sh(*cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failures.append(name)
        if detail:
            print("        " + detail.strip().replace("\n", "\n        "))


# --- signing keys: the real one and an attacker's -------------------------------
for name in ("ota", "attacker"):
    k = ECC.generate(curve="Ed25519")
    (work / f"{name}_private.pem").write_text(k.export_key(format="PEM"))
    (work / f"{name}_public.pem").write_text(k.public_key().export_key(format="PEM"))

# --- fake app repo --------------------------------------------------------------
# The healthy app reads conf.ini (must be the DEVICE's copy, not the repo's) and
# touches shared/healthy, like the real main.py would after a good startup.
APP_OK = '''import configparser, os
from pathlib import Path
cfg = configparser.ConfigParser()
cfg.read("conf.ini")
assert cfg["School"]["RoomName"] == "DEVICE-ROOM", "wrong conf.ini"
Path(os.environ["FPS_ROOT"], "shared", "healthy").touch()
'''
APP_BROKEN = 'raise SystemExit("boom: broken release")\n'

repo.mkdir()
sh("git", "init", "-q", cwd=repo)
(repo / "conf.ini").write_text("[School]\nRoomName=DEV-REPO\n")  # tracked, must be excluded
(repo / "requirements.txt").write_text("")
for junk in ("__pycache__/main.cpython-311.pyc", ".vscode/settings.json"):  # tracked in the real repo too
    (repo / junk).parent.mkdir(exist_ok=True)
    (repo / junk).write_text("")


def commit_app(source, msg):
    (repo / "main.py").write_text(source)
    sh("git", "add", "-A", cwd=repo)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", msg, cwd=repo)


def release(version, key="ota"):
    sh(PY, HERE / "release.py", version, dist, cwd=repo, capture_output=True,
       env={**os.environ, "FPS_SIGNING_KEY": str(work / f"{key}_private.pem")})


# --- fake device ----------------------------------------------------------------
# Starts on an empty 0.0.0 release, so the first update is also the first install.
(device / "releases" / "0.0.0").mkdir(parents=True)
(device / "current").symlink_to(device / "releases" / "0.0.0")
(device / "shared" / "assets" / "imgs").mkdir(parents=True)
(device / "shared" / "conf.ini").write_text("[School]\nRoomName=DEVICE-ROOM\n")
(device / "shared" / "user.db").write_bytes(b"precious fingerprint data")
(device / "shared" / ".encryption_key").write_bytes(b"secret")
(device / "shared" / "assets" / "imgs" / "schoollogo.png").write_bytes(b"png")
shutil.copy(work / "ota_public.pem", device / "ota_public.pem")

# --- local update server --------------------------------------------------------
dist.mkdir()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(dist), **kw)

    def log_message(self, *a):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

env = {
    **os.environ,
    "FPS_ROOT": str(device),
    "FPS_UPDATE_URL": f"http://127.0.0.1:{server.server_port}",
    # Stand-in for `systemctl restart fps`: run the app from current/ like systemd would.
    "FPS_RESTART_CMD": f"sh -c 'cd \"$FPS_ROOT/current\" && \"{PY}\" main.py'",
    "FPS_HEALTH_WAIT": "2",
}


def update():
    r = subprocess.run([PY, HERE / "update.py"], env=env, capture_output=True, text=True)
    return r, r.stdout + r.stderr


def current():
    return (device / "current").resolve().name


# --- scenarios ------------------------------------------------------------------
print("1. first install of a good release")
commit_app(APP_OK, "good app")
release("1.0.0")
r, out = update()
check("exits 0", r.returncode == 0, out)
check("current -> 1.0.0", current() == "1.0.0", out)
check("app reported healthy", (device / "shared" / "healthy").exists())
rel = device / "releases" / "1.0.0"
check("conf.ini is a symlink to the device copy",
      (rel / "conf.ini").is_symlink() and "DEVICE-ROOM" in (rel / "conf.ini").read_text())
check("user.db reachable from release", (rel / "user.db").read_bytes() == b"precious fingerprint data")
check("no __pycache__/.vscode shipped", not (rel / "__pycache__").exists() and not (rel / ".vscode").exists())

print("2. running again with nothing new")
r, out = update()
check("no-op, says up to date", r.returncode == 0 and "up to date" in out, out)

print("3. broken release is rolled back")
commit_app(APP_BROKEN, "broken app")
release("1.1.0")
r, out = update()
check("exits non-zero", r.returncode != 0, out)
check("rolled back to 1.0.0", current() == "1.0.0", out)
check("says rolled back", "rolled back" in out, out)
r, out = update()
check("broken version is not retried", r.returncode == 0 and "already tried" in out and current() == "1.0.0", out)

print("4. tampered tarball on the server")
commit_app(APP_OK, "good again")
release("1.2.0")
tarball = dist / "fps-1.2.0.tar.gz"
tarball.write_bytes(tarball.read_bytes() + b"evil")
r, out = update()
check("refused with sha256 mismatch", r.returncode != 0 and "sha256 mismatch" in out, out)
check("still on 1.0.0, nothing installed", current() == "1.0.0" and not (device / "releases" / "1.2.0").exists())

print("5. manifest edited without re-signing")
release("1.2.0")
(dist / "manifest.json").write_text((dist / "manifest.json").read_text().replace("1.2.0", "9.9.9"))
r, out = update()
check("refused, signature invalid", r.returncode != 0 and "signature is invalid" in out, out)
check("still on 1.0.0", current() == "1.0.0")

print("6. release signed with someone else's key")
release("2.0.0", key="attacker")
r, out = update()
check("refused, signature invalid", r.returncode != 0 and "signature is invalid" in out, out)
check("still on 1.0.0", current() == "1.0.0")

print("7. old (validly signed) release replayed")
release("0.9.0")
r, out = update()
check("no downgrade", r.returncode == 0 and current() == "1.0.0", out)

print("8. next good release, device data kept")
release("1.3.0")
r, out = update()
check("current -> 1.3.0", r.returncode == 0 and current() == "1.3.0", out)
check("user.db unchanged", (device / "shared" / "user.db").read_bytes() == b"precious fingerprint data")
check("old releases kept for rollback", (device / "releases" / "1.0.0").exists())

server.shutdown()
if failures:
    print(f"\n{len(failures)} check(s) failed. Test files kept in {work}")
    sys.exit(1)
print("\nall checks passed")
shutil.rmtree(work)
