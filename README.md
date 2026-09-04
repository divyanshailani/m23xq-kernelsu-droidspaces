# m23xq-kernelsu-droidspaces

Rooted custom kernel for the **Samsung Galaxy F23 5G / SM-E236B (`m23xq`)** that keeps
Samsung's UH/RKP security stack intact while adding **[KernelSU](https://github.com/tiann/KernelSU)**
(build-time manual hooks — zero kprobes) and every kernel prerequisite for
**[Droidspaces](https://github.com/ravindu644/Droidspaces-OSS)**.

Built and verified end-to-end on a real device: custom kernel boots Android 14,
KernelSU root works (`uid=0 ... context=u:r:ksu:s0`), SELinux stays Enforcing, and all
Droidspaces prerequisites verify live.

> **Want to just flash the prebuilt image?** Grab the [v9 release](../../releases) —
> the exact BOOT image running on the author's phone, hash-verified — and follow
> `docs/12-flash-v9-image.md`. **No support, no warranty, no responsibility.**
> If you'd rather build from source (recommended), everything below applies.

> **Read this first:** This project unlocks a bootloader, flashes a custom boot image,
> and performs a factory reset. It will **permanently trip Knox** (eFuse), wipe your
> data, and — critically — **your phone will no longer boot the stock boot image
> afterwards** (Samsung's file-based-encryption Root-of-Trust is re-sealed to the custom
> kernel; see `docs/03-fbe-rot-analysis.md`). Everything here is provided for
> educational/research purposes on hardware you own. You assume all risk.

## What this repo contains

| Path | What it is |
|---|---|
| `scripts/apply-ksu-manual-hooks.py` | Applies the five rsuntk/KernelSU call-site hooks into the Samsung kernel tree |
| `scripts/build-ksu-manualhook-droidspaces-qcom-10.0.7.sh` | Authoritative build: stock embedded config + Droidspaces symbols on, KDP off, KPROBES stays off |
| `scripts/audit-kernelsu-build.py` | Post-build invariant audit |
| `scripts/transplant-kernel-into-stock-boot.py` | Fixed-slot kernel transplanter (for kernels that fit the stock slot) |
| `scripts/compare-boot-structure.py` | Boot image structural comparison |
| `scripts/rehearse-stock-boot-rollback.py` | Off-device rollback rehearsal |
| `scripts/ksu-manual-hook-patch-manifest.json` | Exact per-file edit manifest for the hook patches |
| `docs/01…12` | Full engineering history: build report, panic diagnosis, FBE ROT analysis, flash protocol & results, final verification, restore runbook, **prebuilt v9 image flashing guide (`docs/12`)** |

## Target device / firmware

- Samsung Galaxy F23 5G, model SM-E236B, board `m23xq` (swa_open / Indian board file)
- Android 14, One UI, firmware `E236BXXSEEZB1`, kernel 4.19.152
- Qualcomm Snapdragon 750G (SM7225)

## Why a custom kernel was unavoidable

- Samsung's stock kernel has none of the Droidspaces prerequisites (user namespaces,
  SysV IPC, POSIX mqueues, devices/pids/net_prio cgroups, autofs, …) —
  see `docs/07-droidspaces-requirements-matrix.md`.
- No community kernel for this device enables them either (BoostKernel2 was audited as
  a control; see `docs/09-boostkernel2-control-audit.md`).
- KernelSU's standard integration uses runtime kprobes, which collide with Samsung RKP
  (write-protected kernel text → BRK panic at boot; full postmortem in
  `docs/02-kprobe-panic-diagnosis.md`). The fix is rsuntk's fork
  (`648e5988cf421172769f80ce07f86331b548c053`) with five compile-time call-site hooks
  in `fs/open.c`, `fs/stat.c`, `fs/exec.c`, `fs/read_write.c`, `drivers/input/input.c`
  plus the LSM `task_fix_setuid` hook registered via `security_add_hooks()`.

## Reproduction overview

### 0. Off-device prerequisites

1. A Mac (or any Linux host) with Docker (OrbStack works), ~60 GB free, and a good USB cable.
2. Exact stock firmware for **your** device (download via [samloader-rs](https://github.com/samloader/samloader-rs));
   keep two copies, verify SHA-256.
3. Samsung `m23xq` kernel source — public release from Samsung Open Source, plus the
   rsuntk/KernelSU fork pinned above.
4. Qualcomm Snapdragon LLVM ARM Compiler 10.0.7 (Samsung ships the kernel built with it;
   you are responsible for obtaining it under its license).

### 1. Patch and build off-device

```bash
# apply the five manual-hook patches + wire drivers/kernelsu into the tree
python3 scripts/apply-ksu-manual-hooks.py \
  --tree <samsung-kernel-source> \
  --ksu <path/to/KernelSU-648e5988...>

# build in Docker with the Qualcomm toolchain
OUT_ROOT=out TAG=final \
  LAB=<dir containing sources/ toolchains/ artifacts/> \
  scripts/build-ksu-manualhook-droidspaces-qcom-10.0.7.sh
```

The build script asserts 37 invariants after `olddefconfig` (KSU + Droidspaces symbols on;
UH/RKP/HDM/PROCA/FIVE and the swa_open board on; KPROBES/KDP/EUR_OPEN off) and aborts on
any regression. Expect a ~53 MB `Image` — larger than the stock kernel slot, so a plain
fixed-slot transplant will not fit.

### 2. Repack into a stock BOOT image

The kernel exceeds the stock slot, so repack with truthful kernel size using
`magiskboot` (the repack utility only — Magisk is never installed on the phone):

```bash
magiskboot unpack stock-boot.img
cp out/compile/arch/arm64/boot/Image kernel-image
magiskboot repack stock-boot.img custom-boot.img
```

Keep the ramdisk, DTB, and embedded vbmeta byte-identical to stock. Do **not** flash
DTBO, do **not** touch VBMETA, do **not** repartition — BOOT-only.

### 3. Unlock, flash, and the one-time reset

1. Standard Samsung OEM-unlock flow (Download Mode). This wipes the device.
2. Flash the custom BOOT via [Heimdall](https://gitlab.com/BenjaminDobell/Heimdall)
   (`heimdall flash --BOOT custom-boot.img`) or Odin-equivalent.
3. First boot of the custom kernel fails `/data` decryption (Samsung FBE Root-of-Trust
   mismatch — stock sealed `0x06`, custom kernel reports `0x07`). This is expected:
   **one factory reset with the custom kernel installed re-seals `/data` to the custom
   ROT**, and every future custom kernel boots cleanly.
4. After the reset the phone boots Android normally. Verify:
   `adb shell su -c id` → `uid=0(root) ... u:r:ksu:s0`.

Full device-test protocol and captured results: `docs/04`, `docs/05`, `docs/06`.

### 4. Post-root: manager, Droidspaces

- Install the KernelSU **legacy** manager v3.2.2 (kernel speaks protocol 32473); it
  randomizes its own package name — that is expected.
- Grant Shell/ADB root in the manager's Superuser tab if you want `adb shell su`.
- Install the Droidspaces universal APK; its prerequisite checker goes green with this
  kernel.

## Known hard limitation: Play Integrity / hardware attestation

The bootloader of this device is genuinely unlocked, and on Android 13+ Google's
`MEETS_DEVICE_INTEGRITY` requires *hardware-backed proof of a locked bootloader*. No
fingerprint spoof, module, or prop can satisfy that — verify with SPIC (Simple Play
Integrity Checker) if you want to see it yourself. Consequences on this device:

- WhatsApp registration and Play-Integrity-gated apps will reject the device — permanent.
- Relocking is **not** a recovery path: the ROT re-seal means stock BOOT no longer boots
  this phone.

Root *hiding* against **software-only** detection (banking apps, most anti-cheat) still
works — see `docs/11-post-root-hide-stack.md`.

## Safety rules that were followed

- BOOT-only flashes. Never VBMETA/DTBO/repartition/PIT.
- Exact stock firmware archived and hash-verified twice before starting.
- Rollback rehearsed off-device before every flash (see `docs/08-stock-restore-runbook.md`).
- Every failure was classified from captured evidence (ramdumps live in `/data/log` on
  Samsung — read before theorizing).
- One variable changed per flash.

## Credits

- [rsuntk/KernelSU](https://github.com/rsuntk/KernelSU) — the manual-hook fork that made
  KernelSU coexist with Samsung RKP.
- [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) — the
  containerization project whose kernel requirements drove this build.
- [BoostKernel2](https://github.com/BoostKernel/BoostKernel2) — audited as a control;
  its bundled `magiskboot` was used off-device for repacking only.
- [osm0sis/PlayIntegrityFork](https://github.com/osm0sis/PlayIntegrityFork),
  [ZygiskNext](https://github.com/Dr-TSNG/ZygiskNext),
  [Zygisk-Assistant](https://github.com/snake-4/Zygisk-Assistant) — the post-root
  integrity/hiding stack documented in `docs/11`.

## License

Scripts and documentation in this repo: MIT (see `LICENSE`). Samsung kernel source,
KernelSU, and all bundled/upstream projects remain under their own licenses.
