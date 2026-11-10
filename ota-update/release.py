#!/usr/bin/env python3
"""Build and sign an fps release from the committed HEAD.

usage (inside the repo):  python release.py VERSION [OUT_DIR]
Signing key: $FPS_SIGNING_KEY, default ~/.fps/ota_private.pem
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

version = sys.argv[1]
tuple(int(p) for p in version.split("."))  # fail early on a malformed version
dist = Path(sys.argv[2] if len(sys.argv) > 2 else "dist")
key_file = Path(os.environ.get("FPS_SIGNING_KEY", Path.home() / ".fps/ota_private.pem"))

if subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip():
    print("warning: uncommitted changes are NOT in this release (it is built from HEAD)")

dist.mkdir(parents=True, exist_ok=True)
file = f"fps-{version}.tar.gz"
subprocess.run(["git", "archive", "--format=tar.gz", "-o", str(dist / file), "HEAD", "--", ".",
                ":(exclude)conf.ini", ":(exclude)__pycache__", ":(exclude).vscode"], check=True)

manifest = json.dumps({
    "version": version,
    "file": file,
    "sha256": hashlib.sha256((dist / file).read_bytes()).hexdigest(),
}).encode()

key = ECC.import_key(key_file.read_text())
(dist / "manifest.json").write_bytes(manifest)
(dist / "manifest.json.sig").write_bytes(eddsa.new(key, "rfc8032").sign(manifest))
print(f"published {version} to {dist}")
