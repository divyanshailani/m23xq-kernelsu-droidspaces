#!/usr/bin/env python3
"""Apply rsuntk-KernelSU manual (build-time) call-site hooks to a Samsung 4.19 tree.

This replaces KernelSU's runtime kprobe registration, which panicked on this device
because Samsung RKP write-protects kernel text (BRK #0x4 at __arm64_sys_faccessat+0x0,
ESR 0x8600000f / IABT). The five call sites and the extern declarations mirror
Aflaungos/android_kernel_samsung_sm7225_testing @ Boostkernel2 exactly.

Idempotent: refuses to patch a file that already contains CONFIG_KSU. Fails loudly if
an anchor is missing or ambiguous rather than guessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Each edit: (relative path, anchor line that must appear exactly once,
#            text inserted before the anchor, text inserted after the anchor's '{')
EDITS = [
    dict(
        path="fs/open.c",
        anchor="SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)\n",
        before=(
            "#ifdef CONFIG_KSU\n"
            "__attribute__((hot))\n"
            "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,\n"
            "\t\t\t\tint *mode, int *flags);\n"
            "#endif\n"
            "\n"
        ),
        body="#ifdef CONFIG_KSU\n\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n#endif\n",
    ),
    dict(
        path="fs/stat.c",
        anchor="SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,\n",
        before=(
            "#ifdef CONFIG_KSU\n"
            "__attribute__((hot))\n"
            "extern int ksu_handle_stat(int *dfd, const char __user **filename_user,\n"
            "\t\t\t\tint *flags);\n"
            "#endif\n"
            "\n"
        ),
        # newfstatat declares locals first; the hook goes after them, matching BK2.
        after_line="\tint error;\n",
        body="#ifdef CONFIG_KSU\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n",
    ),
    dict(
        path="fs/exec.c",
        anchor="int do_execve(struct filename *filename,\n",
        before=(
            "#ifdef CONFIG_KSU\n"
            "__attribute__((hot))\n"
            "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,\n"
            "\t\t\t\tvoid *argv, void *envp, int *flags);\n"
            "#endif\n"
            "\n"
        ),
        after_line="\tstruct user_arg_ptr envp = { .ptr.native = __envp };\n",
        body="#ifdef CONFIG_KSU\n\tksu_handle_execveat((int *)AT_FDCWD, &filename, &argv, &envp, 0);\n#endif\n",
    ),
    dict(
        path="fs/read_write.c",
        anchor="SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n",
        before=(
            "#ifdef CONFIG_KSU\n"
            "extern bool ksu_vfs_read_hook __read_mostly;\n"
            "extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd,\n"
            "\t\t\t\tchar __user **buf_ptr, size_t *count_ptr);\n"
            "#endif\n"
            "\n"
        ),
        body=(
            "#ifdef CONFIG_KSU\n"
            "\tif (unlikely(ksu_vfs_read_hook))\n"
            "\t\tksu_handle_sys_read(fd, &buf, &count);\n"
            "#endif\n"
        ),
    ),
    dict(
        path="drivers/input/input.c",
        anchor="static void input_handle_event(struct input_dev *dev,\n",
        before=(
            "#ifdef CONFIG_KSU\n"
            "extern bool ksu_input_hook __read_mostly;\n"
            "extern int ksu_handle_input_handle_event(unsigned int *type, unsigned int *code, int *value);\n"
            "#endif\n"
            "\n"
        ),
        after_line="\tint disposition = input_get_disposition(dev, type, code, &value);\n",
        body=(
            "#ifdef CONFIG_KSU\n"
            "\tif (unlikely(ksu_input_hook))\n"
            "\t\tksu_handle_input_handle_event(&type, &code, &value);\n"
            "#endif\n"
        ),
    ),
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def apply_edit(root: Path, edit: dict) -> dict:
    f = root / edit["path"]
    if not f.is_file():
        raise SystemExit(f"missing source file: {f}")
    before_hash = sha256(f)
    text = f.read_text()

    if "CONFIG_KSU" in text:
        raise SystemExit(f"{edit['path']} already references CONFIG_KSU; refusing to patch")

    anchor = edit["anchor"]
    if text.count(anchor) != 1:
        raise SystemExit(
            f"{edit['path']}: anchor appears {text.count(anchor)} times, expected 1: {anchor!r}"
        )

    lines = text.splitlines(keepends=True)
    ai = next(i for i, l in enumerate(lines) if l == anchor)

    # Locate the opening brace of the function that starts at the anchor.
    bi = next(i for i in range(ai, min(ai + 8, len(lines))) if lines[i].rstrip("\n") == "{")

    # Where the hook body goes: right after the brace, or after a named local decl.
    if "after_line" in edit:
        al = edit["after_line"]
        window = lines[bi : bi + 10]
        if window.count(al) != 1:
            raise SystemExit(
                f"{edit['path']}: after_line appears {window.count(al)} times in the "
                f"function prologue, expected 1: {al!r}"
            )
        insert_at = bi + window.index(al) + 1
    else:
        insert_at = bi + 1

    out = lines[:insert_at] + [edit["body"]] + lines[insert_at:]
    out = out[:ai] + [edit["before"]] + out[ai:]
    f.write_text("".join(out))

    return dict(
        path=edit["path"],
        sha256_before=before_hash,
        sha256_after=sha256(f),
        extern_line=ai + 1,
        hook_line=insert_at + 1 + edit["before"].count("\n"),
    )


def wire_driver(root: Path) -> dict:
    """Add the obj- rule and Kconfig source line, matching KernelSU's setup.sh."""
    changes = {}

    mk = root / "drivers/Makefile"
    text = mk.read_text()
    if "kernelsu" not in text:
        text = text.rstrip("\n") + "\n\nobj-$(CONFIG_KSU) += kernelsu/\n"
        mk.write_text(text)
    changes["drivers/Makefile"] = sha256(mk)

    kc = root / "drivers/Kconfig"
    text = kc.read_text()
    if 'source "drivers/kernelsu/Kconfig"' not in text:
        lines = text.splitlines(keepends=True)
        last_endmenu = max(i for i, l in enumerate(lines) if l.rstrip("\n") == "endmenu")
        lines.insert(last_endmenu, 'source "drivers/kernelsu/Kconfig"\n')
        kc.write_text("".join(lines))
    changes["drivers/Kconfig"] = sha256(kc)

    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True, help="kernel source root")
    ap.add_argument("--ksu", required=True, help="extracted rsuntk/KernelSU root")
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    root = Path(args.tree).resolve()
    ksu = Path(args.ksu).resolve()

    if not (ksu / "kernel" / "Kconfig").is_file():
        raise SystemExit(f"not a KernelSU checkout: {ksu}")
    kconfig = (ksu / "kernel" / "Kconfig").read_text()
    for required in ("config KSU\n", "config KSU_MANUAL_HOOK\n"):
        if required not in kconfig:
            raise SystemExit(f"KernelSU Kconfig lacks {required.strip()!r}")

    # The symlink must be relative so the tree stays relocatable into a container.
    link = root / "drivers" / "kernelsu"
    if link.is_symlink() or link.exists():
        raise SystemExit(f"{link} already exists; refusing to overwrite")
    target = Path("../..") / ksu.relative_to(root.parent) / "kernel"
    link.symlink_to(target)
    if not (link / "Kconfig").is_file():
        raise SystemExit(f"symlink {link} -> {target} does not resolve")

    result = dict(
        tree=str(root),
        ksu=str(ksu),
        ksu_kernel_symlink=str(target),
        edits=[apply_edit(root, e) for e in EDITS],
        wiring=wire_driver(root),
    )

    Path(args.manifest).write_text(json.dumps(result, indent=2) + "\n")
    for e in result["edits"]:
        print(f"patched {e['path']}: extern@{e['extern_line']} hook@{e['hook_line']}")
    print(f"manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
