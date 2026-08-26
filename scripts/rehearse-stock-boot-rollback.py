#!/usr/bin/env python3
"""Rehearse stock boot rollback without touching a device.

The rehearsal copies the verified stock boot image to an offline recovery directory only
after checking the source hash and exact byte length. It never invokes adb, fastboot, Odin,
or Heimdall and never writes a device partition.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_SHA256 = "3abd7ea170aa7c53eff61d4ee87f60100709166ce6242353aae1e117b293c2be"
EXPECTED_BYTES = 100663296

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", type=Path, required=True)
    ap.add_argument("--recovery-dir", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    if not args.stock.is_file():
        raise SystemExit(f"stock image missing: {args.stock}")
    size = args.stock.stat().st_size
    digest = sha256(args.stock)
    if size != EXPECTED_BYTES:
        raise SystemExit(f"stock image size mismatch: {size} != {EXPECTED_BYTES}")
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"stock image hash mismatch: {digest} != {EXPECTED_SHA256}")
    args.recovery_dir.mkdir(parents=True, exist_ok=True)
    target = args.recovery_dir / "boot-stock-verified.img"
    target.write_bytes(args.stock.read_bytes())
    target_digest = sha256(target)
    if target.stat().st_size != EXPECTED_BYTES or target_digest != EXPECTED_SHA256:
        raise SystemExit("rollback copy verification failed")
    result = {
        "rehearsal": "PASS",
        "source": str(args.stock),
        "offline_recovery_copy": str(target),
        "bytes": size,
        "sha256": digest,
        "device_touched": False,
        "adb_invoked": False,
        "odin_invoked": False,
        "heimdall_invoked": False,
        "operational_note": "If a future boot experiment fails, restore this exact stock boot image using the appropriate Samsung Download Mode workflow; do not relock while custom images remain installed.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
