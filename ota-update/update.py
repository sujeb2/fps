#!/usr/bin/env python3
"""fps OTA updater. Runs outside the app, from a systemd timer.

The defaults are for the real device; the FPS_* environment variables let you
point it at a test setup instead.
"""
import hashlib, json, os, shlex, subprocess, sys, tarfile, tempfile, time, urllib.request
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

ROOT = Path(os.environ.get("FPS_ROOT", "/opt/fps"))
BASE_URL = os.environ.get("FPS_UPDATE_URL", "https://updates.example.com/fps")
RESTART_CMD = shlex.split(os.environ.get("FPS_RESTART_CMD", "systemctl restart fps"))
HEALTH_WAIT = float(os.environ.get("FPS_HEALTH_WAIT", "60"))
PUBLIC_KEY_FILE = Path(os.environ.get("FPS_PUBLIC_KEY", ROOT / "ota_public.pem"))

CURRENT = ROOT / "current"
HEALTHY = ROOT / "shared" / "healthy"
# Per-device files that live in shared/ and are symlinked into every release.
SHARED = ["conf.ini", "user.db", ".encryption_key", "assets/imgs/schoollogo.png"]


def fetch(name):
    with urllib.request.urlopen(f"{BASE_URL}/{name}", timeout=60) as r:
        return r.read()


def version_tuple(v):
    return tuple(int(p) for p in v.split("."))


def switch_to(target):
    tmp = ROOT / "current.new"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    tmp.replace(CURRENT)  # atomic rename over the old link


def restart():
    # No check=True: a release that fails to start must still reach the rollback below.
    subprocess.run(RESTART_CMD)


def main():
    raw, sig = fetch("manifest.json"), fetch("manifest.json.sig")
    try:
        eddsa.new(ECC.import_key(PUBLIC_KEY_FILE.read_text()), "rfc8032").verify(raw, sig)
    except ValueError:
        sys.exit("manifest signature is invalid, refusing to update")
    manifest = json.loads(raw)

    previous = CURRENT.resolve()
    version = manifest["version"]
    release = ROOT / "releases" / version
    if version_tuple(version) <= version_tuple(previous.name):
        print(f"up to date ({previous.name})")
        return
    if release.exists():
        print(f"{version} was already tried and rolled back, skipping")
        return

    archive = fetch(manifest["file"])
    if hashlib.sha256(archive).hexdigest() != manifest["sha256"]:
        sys.exit("sha256 mismatch, refusing to update")

    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        path = Path(tmp) / "release.tar.gz"
        path.write_bytes(archive)
        staging = Path(tmp) / version
        staging.mkdir()
        with tarfile.open(path) as t:
            t.extractall(staging, filter="data")  # needs Python 3.11.4+ / 3.12
        for name in SHARED:
            link = staging / name
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(ROOT / "shared" / name)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r",
                        str(staging / "requirements.txt")], check=True)
        staging.rename(release)

    print(f"installed {version}, restarting")
    HEALTHY.unlink(missing_ok=True)
    switch_to(release)
    restart()

    deadline = time.monotonic() + HEALTH_WAIT
    while time.monotonic() < deadline and not HEALTHY.exists():
        time.sleep(0.5)
    if HEALTHY.exists():
        print(f"updated {previous.name} -> {version}")
        return

    switch_to(previous)
    restart()
    sys.exit(f"{version} did not report healthy within {HEALTH_WAIT:g}s, rolled back to {previous.name}")


if __name__ == "__main__":
    main()
