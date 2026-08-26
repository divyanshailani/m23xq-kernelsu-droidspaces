#!/usr/bin/env python3
"""Audit KernelSU build evidence without executing or modifying the build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


REQUIRED_CONFIG = {
    "CONFIG_CLANG_VERSION": "100007",
    "CONFIG_FHANDLE": "y",
    "CONFIG_HAVE_KPROBES": "y",
    "CONFIG_KPROBES": "y",
    "CONFIG_KPROBE_EVENTS": "y",
    "CONFIG_KSU": "y",
    "CONFIG_MODULE_SIG": "y",
    "CONFIG_MODULE_SIG_FORCE": "y",
    "CONFIG_MODVERSIONS": "y",
    "CONFIG_OVERLAY_FS": "y",
}

REQUIRED_SYMBOLS = (
    "ksu_core_init",
    "ksu_handle_execveat",
    "ksu_handle_prctl",
    "ksu_kprobe_init",
    "ksu_ksud_init",
    "ksu_lsm_hook_init",
    "ksu_manager_uid",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    return values


def git_value(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def module_strings(path: Path) -> dict[str, str | bool | int]:
    data = path.read_bytes()
    fields: dict[str, str | bool | int] = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "signature_marker_present": b"~Module signature appended~\n" in data,
    }
    for item in data.split(b"\0"):
        for key in (
            b"name=",
            b"vermagic=",
            b"depends=",
            b"signer=",
            b"sig_key=",
            b"sig_hashalgo=",
        ):
            if item.startswith(key):
                fields[key[:-1].decode()] = item[len(key) :].decode("utf-8", "replace")
    return fields


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build-log", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    required_files = (
        args.compile / ".config",
        args.compile / "System.map",
        args.compile / "vmlinux",
        args.compile / "arch/arm64/boot/Image",
        args.compile / "include/config/kernel.release",
        args.build_log,
    )
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise SystemExit(f"missing audit inputs: {missing}")

    config = parse_config(args.compile / ".config")
    config_checks = {
        key: {
            "expected": expected,
            "actual": config.get(key),
            "pass": config.get(key) == expected,
        }
        for key, expected in REQUIRED_CONFIG.items()
    }

    system_map = (args.compile / "System.map").read_text(errors="replace")
    symbol_names = {
        line.rsplit(" ", 1)[-1]
        for line in system_map.splitlines()
        if " " in line
    }
    symbol_checks = {symbol: symbol in symbol_names for symbol in REQUIRED_SYMBOLS}

    log_text = args.build_log.read_text(errors="replace")
    version_match = re.search(r"KernelSU version:\s*(\d+)", log_text)
    clang_match = re.search(r"^clang=(.+)$", log_text, re.MULTILINE)
    gcc_match = re.search(r"^gcc=(.+)$", log_text, re.MULTILINE)

    source_commit = git_value(args.source, "rev-parse", "HEAD")
    source_tag = git_value(args.source, "describe", "--tags", "--exact-match", "HEAD")
    modules = {
        str(path.relative_to(args.compile)): module_strings(path)
        for path in sorted(args.compile.rglob("*.ko"))
    }
    kernel_release = (args.compile / "include/config/kernel.release").read_text().strip()
    module_vermagic_matches_build = all(
        str(metadata.get("vermagic", "")).startswith(kernel_release + " ")
        for metadata in modules.values()
    )

    checks = {
        "source_commit": source_commit == args.expected_commit,
        "source_tag": source_tag == args.expected_tag,
        "config": all(item["pass"] for item in config_checks.values()),
        "symbols": all(symbol_checks.values()),
        "build_log_defconfig_exit": "DEFCONFIG_EXIT=0" in log_text,
        "build_log_compile_exit": "COMPILE_EXIT=0" in log_text,
        "module_count": len(modules) == 7,
        "module_vermagic_matches_build": module_vermagic_matches_build,
    }

    result = {
        "classification": "off_device_build_evidence_only",
        "phone_touched": False,
        "kernel_su_runtime_verified": False,
        "root_verified": False,
        "device_compatibility_verified": False,
        "source": {
            "path": str(args.source),
            "commit": source_commit,
            "tag": source_tag,
            "expected_commit": args.expected_commit,
            "expected_tag": args.expected_tag,
        },
        "build": {
            "compile_path": str(args.compile),
            "kernel_release": kernel_release,
            "kernel_su_version_from_log": int(version_match.group(1)) if version_match else None,
            "clang": clang_match.group(1) if clang_match else None,
            "gcc": gcc_match.group(1) if gcc_match else None,
            "image": {
                "bytes": (args.compile / "arch/arm64/boot/Image").stat().st_size,
                "sha256": sha256(args.compile / "arch/arm64/boot/Image"),
            },
            "vmlinux": {
                "bytes": (args.compile / "vmlinux").stat().st_size,
                "sha256": sha256(args.compile / "vmlinux"),
            },
        },
        "config_checks": config_checks,
        "symbol_checks": symbol_checks,
        "modules": modules,
        "checks": checks,
        "audit_pass": all(checks.values()),
        "limitations": [
            "Compiled symbols and config do not prove that KernelSU initializes or grants root on the device.",
            "The rebuilt module vermagic matches this build, not the stock Samsung release suffix.",
            "CONFIG_MODULE_SIG_FORCE is enabled, but the seven extracted modules contain no appended module-signature marker.",
            "Vendor module loading and symbol-version compatibility require device-side evidence and remain unverified.",
            "No manager APK, post-fs-data behavior, SELinux transition, or boot behavior was tested.",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {"audit_pass": result["audit_pass"], "output": str(args.output)},
            indent=2,
        )
    )
    if not result["audit_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
