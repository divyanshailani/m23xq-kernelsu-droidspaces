#!/usr/bin/env python3
"""Compare a stock Samsung boot image with a structural candidate, read-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


PAGE = 4096
EXPECTED_STOCK_SHA256 = "3abd7ea170aa7c53eff61d4ee87f60100709166ce6242353aae1e117b293c2be"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def align(value: int) -> int:
    return (value + PAGE - 1) // PAGE * PAGE


def parse_header(data: bytes) -> dict[str, int | str]:
    if data[:8] != b"ANDROID!":
        raise SystemExit("missing Android boot magic")
    return {
        "kernel_size": u32le(data, 8),
        "kernel_addr": u32le(data, 12),
        "ramdisk_size": u32le(data, 16),
        "ramdisk_addr": u32le(data, 20),
        "second_size": u32le(data, 24),
        "second_addr": u32le(data, 28),
        "tags_addr": u32le(data, 32),
        "page_size": u32le(data, 36),
        "header_version": u32le(data, 40),
        "name": data[48:64].split(b"\0", 1)[0].decode("ascii", "replace"),
        "recovery_dtbo_size": u32le(data, 1632),
        "recovery_dtbo_offset": u64le(data, 1636),
        "header_size": u32le(data, 1644),
        "dtb_size": u32le(data, 1648),
        "dtb_addr": u64le(data, 1652),
    }


def parse_footer(data: bytes) -> dict[str, int]:
    footer = data[-64:]
    if footer[:4] != b"AVBf":
        raise SystemExit("missing AVB footer")
    major, minor, original_size, vbmeta_offset, vbmeta_size = struct.unpack(
        ">IIQQQ", footer[4:36]
    )
    return {
        "version_major": major,
        "version_minor": minor,
        "original_image_size": original_size,
        "vbmeta_offset": vbmeta_offset,
        "vbmeta_size": vbmeta_size,
        "footer_offset": len(data) - 64,
    }


def component_ranges(
    header: dict[str, int | str], footer: dict[str, int]
) -> dict[str, tuple[int, int]]:
    page = int(header["page_size"])
    kernel_start = page
    kernel_end = kernel_start + int(header["kernel_size"])
    kernel_slot_end = align(kernel_end)
    ramdisk_start = kernel_slot_end
    ramdisk_end = ramdisk_start + int(header["ramdisk_size"])
    ramdisk_slot_end = align(ramdisk_end)
    second_start = ramdisk_slot_end
    second_end = second_start + int(header["second_size"])
    dtb_start = align(second_end)
    dtb_end = dtb_start + int(header["dtb_size"])
    trailer_start = align(dtb_end)
    original_size = footer["original_image_size"]
    vbmeta_offset = footer["vbmeta_offset"]
    vbmeta_end = vbmeta_offset + footer["vbmeta_size"]
    footer_offset = footer["footer_offset"]
    return {
        "header_page": (0, page),
        "kernel_payload": (kernel_start, kernel_end),
        "kernel_slot_padding": (kernel_end, kernel_slot_end),
        "ramdisk": (ramdisk_start, ramdisk_end),
        "ramdisk_padding": (ramdisk_end, ramdisk_slot_end),
        "dtb": (dtb_start, dtb_end),
        "dtb_padding": (dtb_end, trailer_start),
        "samsung_trailer_and_avb_covered_tail": (trailer_start, original_size),
        "pre_vbmeta_padding": (original_size, vbmeta_offset),
        "embedded_vbmeta": (vbmeta_offset, vbmeta_end),
        "post_vbmeta_partition_padding": (vbmeta_end, footer_offset),
        "avb_footer": (footer_offset, footer_offset + 64),
    }


def validate_ranges(ranges: dict[str, tuple[int, int]], size: int) -> None:
    for name, (start, end) in ranges.items():
        if start < 0 or end < start or end > size:
            raise SystemExit(f"invalid {name} range: {start}:{end} for {size} bytes")


def region_result(
    stock: bytes, candidate: bytes, bounds: tuple[int, int]
) -> dict[str, int | str | bool]:
    start, end = bounds
    stock_region = stock[start:end]
    candidate_region = candidate[start:end]
    return {
        "start": start,
        "end": end,
        "bytes": end - start,
        "stock_sha256": sha256(stock_region),
        "candidate_sha256": sha256(candidate_region),
        "identical": stock_region == candidate_region,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--candidate-boot", type=Path)
    parser.add_argument("--raw-kernel", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    stock = args.stock.read_bytes()
    if sha256(stock) != EXPECTED_STOCK_SHA256:
        raise SystemExit("stock image hash does not match the frozen baseline")
    header = parse_header(stock)
    footer = parse_footer(stock)
    ranges = component_ranges(header, footer)
    validate_ranges(ranges, len(stock))

    result: dict[str, object] = {
        "classification": "read_only_structural_and_metadata_inspection",
        "phone_touched": False,
        "stock": {
            "path": str(args.stock),
            "bytes": len(stock),
            "sha256": sha256(stock),
        },
        "header": header,
        "avb_footer": footer,
        "ranges": {name: list(bounds) for name, bounds in ranges.items()},
        "avb_signature_verified": False,
        "flashable": False,
    }

    kernel_capacity = int(header["kernel_size"])
    if args.raw_kernel:
        raw = args.raw_kernel.read_bytes()
        if len(raw) < 60 or raw[56:60] != b"ARMd":
            raise SystemExit("raw kernel is missing ARM64 Image magic")
        result["raw_kernel"] = {
            "path": str(args.raw_kernel),
            "bytes": len(raw),
            "sha256": sha256(raw),
            "fixed_slot_capacity": kernel_capacity,
            "fits_existing_fixed_slot": len(raw) <= kernel_capacity,
            "overflow_bytes": max(0, len(raw) - kernel_capacity),
        }

    if args.candidate_boot:
        candidate = args.candidate_boot.read_bytes()
        if len(candidate) != len(stock):
            raise SystemExit("candidate partition image size differs from stock")
        candidate_header = parse_header(candidate)
        candidate_footer = parse_footer(candidate)
        regions = {
            name: region_result(stock, candidate, bounds)
            for name, bounds in ranges.items()
        }
        non_kernel_identical = all(
            bool(details["identical"])
            for name, details in regions.items()
            if name not in {"kernel_payload", "kernel_slot_padding"}
        )
        result["candidate_boot"] = {
            "path": str(args.candidate_boot),
            "bytes": len(candidate),
            "sha256": sha256(candidate),
            "header_identical": candidate_header == header,
            "footer_identical": candidate_footer == footer,
            "regions": regions,
            "all_non_kernel_regions_identical": non_kernel_identical,
            "avb_covered_prefix_changed": (
                stock[: footer["original_image_size"]]
                != candidate[: footer["original_image_size"]]
            ),
            "structural_check_pass": (
                non_kernel_identical
                and regions["kernel_payload"]["identical"] is False
            ),
            "avb_valid": False,
        }

    raw_result = result.get("raw_kernel")
    fixed_slot_possible = bool(
        isinstance(raw_result, dict) and raw_result["fits_existing_fixed_slot"]
    )
    result["decision"] = {
        "fixed_slot_transplant_possible": fixed_slot_possible,
        "general_repack_required": bool(raw_result and not fixed_slot_possible),
        "blocked_for_flash": True,
        "reason": (
            "The candidate fits the existing fixed kernel slot and passes structural "
            "comparison, but changing the AVB-covered kernel payload invalidates the "
            "signed boot digest; it remains blocked for flash."
            if fixed_slot_possible
            else "The raw kernel overflows the existing fixed slot, and changing the "
            "AVB-covered payload would also invalidate the signed boot digest."
        ),
    }
    result["limitations"] = [
        "Footer fields and byte ranges are parsed as metadata; AVB cryptographic verification is separate.",
        "Preserving the stock footer or embedded vbmeta does not preserve validity after changing covered bytes.",
        "This tool never updates header sizes, rebuilds a ramdisk, signs vbmeta, or writes a device.",
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"decision": result["decision"], "output": str(args.output)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
