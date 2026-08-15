#!/usr/bin/env python3
"""Sign the runtime MANIFEST with Ed25519 (signed update verification).

Protected files = code + static config (runtime.py, graph.json). Mutable
runtime data (state/events/result) is NOT signed — it changes every run.

Usage:
  python sign_manifest.py            # create key (once) + sign MANIFEST
  python sign_manifest.py --keygen   # print the public key hex (pin into runtime.py)
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

RUNTIME_DIR = Path(__file__).parent
PROTECTED = ["runtime.py", "graph.json"]  # code + static config
KEY_PATH = RUNTIME_DIR / "signing_key.pem"
MANIFEST_PATH = RUNTIME_DIR / "MANIFEST.json"
SIG_PATH = RUNTIME_DIR / "MANIFEST.sig"


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_or_create_key() -> Ed25519PrivateKey:
    if KEY_PATH.exists():
        return serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_PATH.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key


def pub_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--keygen", action="store_true", help="print public key hex")
    args = p.parse_args()

    key = load_or_create_key()

    if args.keygen:
        print("PUBLIC_KEY_HEX =", pub_hex(key))
        return 0

    manifest = {
        "schema_version": 1,
        "publisher": "artweb-mimo",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": [
            {"path": f, "sha256": sha256(RUNTIME_DIR / f)} for f in PROTECTED
        ],
    }
    sig = key.sign(canonical_bytes(manifest))
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    SIG_PATH.write_bytes(sig)
    print(f"signed {len(manifest['files'])} files -> MANIFEST.json + MANIFEST.sig")
    print("public key:", pub_hex(key))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
