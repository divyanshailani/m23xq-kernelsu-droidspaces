#!/usr/bin/env python3
"""Safely transplant a replacement raw arm64 Image into a stock Samsung boot.img.

This is deliberately not a general mkbootimg implementation. It preserves the stock
header, fixed kernel slot geometry, ramdisk, embedded DTB, Samsung trailer, AVB footer,
and embedded vbmeta byte-for-byte. It refuses all unexpected layouts and never writes
back to the input image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

PAGE = 4096
ANDROID_MAGIC = b"ANDROID!"
HEADER_VERSION = 2
HEADER_SIZE = 1660
STOCK_SIZE = 100663296

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def align(value: int, page: int = PAGE) -> int:
    return (value + page - 1) // page * page

def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]

def u64(buf: bytes, off: int) -> int:
    return struct.unpack_from("<Q", buf, off)[0]

def parse_header(img: bytes) -> dict[str, int | str]:
    if len(img) < PAGE:
        raise SystemExit(f"stock image too small: {len(img)}")
    if img[:8] != ANDROID_MAGIC:
        raise SystemExit("stock image is missing ANDROID! magic")
    h = {
        "kernel_size": u32(img, 8),
        "kernel_addr": u32(img, 12),
        "ramdisk_size": u32(img, 16),
        "ramdisk_addr": u32(img, 20),
        "second_size": u32(img, 24),
        "second_addr": u32(img, 28),
        "tags_addr": u32(img, 32),
        "page_size": u32(img, 36),
        "header_version": u32(img, 40),
        "recovery_dtbo_size": u32(img, 1632),
        "recovery_dtbo_offset": u64(img, 1636),
        "header_size": u32(img, 1644),
        "dtb_size": u32(img, 1648),
        "dtb_addr": u64(img, 1652),
    }
    h["name"] = img[48:64].split(b"\0", 1)[0].decode("ascii", "replace")
    return h

def ranges(h: dict[str, int | str]) -> dict[str, tuple[int, int]]:
    page = int(h["page_size"])
    kernel_start = page
    kernel_end = kernel_start + int(h["kernel_size"])
    ramdisk_start = align(kernel_end, page)
    ramdisk_end = ramdisk_start + int(h["ramdisk_size"])
    second_start = align(ramdisk_end, page)
    second_end = second_start + int(h["second_size"])
    dtbo_start = int(h["recovery_dtbo_offset"]) if int(h["recovery_dtbo_size"]) else 0
    dtb_start = align(second_end, page)
    dtb_end = dtb_start + int(h["dtb_size"])
    trailer_start = align(dtb_end, page)
    return {
        "header_page": (0, page),
        "kernel": (kernel_start, kernel_end),
        "ramdisk": (ramdisk_start, ramdisk_end),
        "second": (second_start, second_end),
        "dtb": (dtb_start, dtb_end),
        "post_dtb": (trailer_start, STOCK_SIZE),
        "avb_footer": (STOCK_SIZE - PAGE, STOCK_SIZE),
        "dtbo": (dtbo_start, dtbo_start + int(h["recovery_dtbo_size"])) if dtbo_start else (0, 0),
    }

def require_stock_layout(img: bytes, h: dict[str, int | str], r: dict[str, tuple[int, int]]) -> None:
    expected = {
        "page_size": PAGE,
        "header_version": HEADER_VERSION,
        "header_size": HEADER_SIZE,
        "kernel_size": 51138576,
        "ramdisk_size": 724446,
        "second_size": 0,
        "recovery_dtbo_size": 0,
        "dtb_size": 401068,
        "kernel_addr": 0x8000,
        "ramdisk_addr": 0x02000000,
        "tags_addr": 0x01E00000,
        "dtb_addr": 0x01F00000,
    }
    for key, value in expected.items():
        if h[key] != value:
            raise SystemExit(f"unexpected stock {key}: {h[key]!r}, expected {value!r}")
    if len(img) != STOCK_SIZE:
        raise SystemExit(f"unexpected stock image size: {len(img)}")
    for name, (start, end) in r.items():
        if start < 0 or end < start or end > len(img):
            raise SystemExit(f"{name} range outside stock image: {start}:{end}")
    if img[r["post_dtb"][0]:r["post_dtb"][0] + 16] != b"SEANDROIDENFORCE":
        raise SystemExit("stock image lacks expected SEANDROIDENFORCE trailer")
    avb_footer_offset = len(img) - 64
    if img[avb_footer_offset:avb_footer_offset + 4] != b"AVBf":
        raise SystemExit("stock image lacks AVBf footer at the final 64-byte footer")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock", type=Path, required=True)
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    stock = args.stock.read_bytes()
    candidate = args.image.read_bytes()
    h = parse_header(stock)
    r = ranges(h)
    require_stock_layout(stock, h, r)
    if len(candidate) < 64 or candidate[56:60] != b"ARMd":
        raise SystemExit("replacement is not an arm64 Linux Image (ARMd magic missing at 0x38)")
    kernel_capacity = r["kernel"][1] - r["kernel"][0]
    if len(candidate) > kernel_capacity:
        raise SystemExit(f"replacement Image is too large: {len(candidate)} > {kernel_capacity}")

    out = bytearray(stock)
    ks, ke = r["kernel"]
    out[ks:ke] = b"\0" * (ke - ks)
    out[ks:ks + len(candidate)] = candidate
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out)

    result = {
        "stock_sha256": sha256(stock),
        "candidate_sha256": sha256(candidate),
        "output_sha256": sha256(out),
        "stock_bytes": len(stock),
        "candidate_bytes": len(candidate),
        "output_bytes": len(out),
        "candidate_padding_bytes": kernel_capacity - len(candidate),
        "layout": h,
        "ranges": {k: list(v) for k, v in r.items()},
        "kernel_capacity": kernel_capacity,
        "avb_original_image_size": 52273680,
        "stock_avb_covered_sha256": sha256(stock[:52273680]),
        "output_avb_covered_sha256": sha256(out[:52273680]),
        "avb_digest_changed": sha256(stock[:52273680]) != sha256(out[:52273680]),
        "structural_only": True,
        "avb_valid": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
