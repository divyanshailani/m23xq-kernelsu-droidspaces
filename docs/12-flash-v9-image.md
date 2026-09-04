# Flashing the prebuilt v9 boot image (READ EVERYTHING FIRST)

This is the exact BOOT image running on the author's SM-E236B right now —
pulled from the live `/dev/block/sda25` partition and hash-verified.

```
File:    v9-boot.img
Size:    100,663,296 bytes (96 MiB, raw partition image)
SHA-256: 1cf9ff3a16934677a5d1e5cad0943d29bc21e8bf6b19f658b400b36c7008af0a
Kernel:  4.19.152-perf #7 (built 2026-08-30, Snapdragon LLVM 10.0.7)
Base:    stock E236BXXSEEZB1 ramdisk/DTB — BOOT-only, everything else untouched
```

Verify the hash after downloading (`shasum -a 256 v9-boot.img` on macOS,
`sha256sum` on Linux). If it does not match, do not flash it.

## ⚠️ THE DISCLAIMER — read this before you touch anything

**This image is provided as-is, with zero warranty and zero responsibility.
The author is NOT responsible for ANY damage, data loss, bricking, Knox
tripping, SIM issues, banking-app lockouts, security problems, or anything
else that happens to your device before, during, or after flashing. You are
flashing a stranger's kernel onto your phone. That is your decision and your
risk alone. If your phone becomes a paperweight, that is on you.**

You must accept ALL of the following as *facts, not possibilities*:

1. **Knox trips permanently.** The eFuse burns on unlock. Samsung Pay, Secure
   Folder, and every Knox-dependent feature are gone forever. Not reversible.
2. **Your data gets wiped.** The bootloader unlock alone factory-resets the
   phone. Then the custom kernel's FBE Root-of-Trust mismatches stock `/data`
   (stock sealed `0x06`, this kernel reports `0x07`), so the first boot of
   this image fails decryption and needs **one more factory reset** to re-seal.
   After that, this kernel boots cleanly every time — but stock BOOT images
   will **never boot this phone again** (see `docs/03-fbe-rot-analysis.md`).
   Re-locking the bootloader afterwards is NOT a recovery path.
3. **Play Integrity hardware attestation is gone, permanently.** On Android
   13+, `MEETS_DEVICE_INTEGRITY` requires hardware proof of a *locked*
   bootloader. WhatsApp registration and integrity-gated apps will reject
   the device forever. Software-only hiding (banking apps, anti-cheat) works
   via the documented module stack — that's the best that exists.
4. **The image is firmware-version-specific.** It carries the ramdisk/DTB of
   `E236BXXSEEZB1`. If your phone is on a different bootloader patch level
   or firmware, do NOT flash this — build your own from your stock boot.img
   (the repo's build scripts exist exactly for that).
5. **Droidspaces containers are an advanced, self-managed thing.** This repo
   gets you the kernel prerequisites and the verified module stack. The
   author's own container lab (networking, VPN containers, port forwards,
   systemd services) is NOT included — you build your own setup.

## Requirements (all mandatory)

- Galaxy F23 5G / SM-E236B on firmware **E236BXXSEEZB1**, bootloader unlocked
  (the unlock itself wipes the phone — do the unlock BEFORE flashing this).
- Battery > 50%, a good USB cable, direct USB port (no hubs).
- A computer with [Heimdall](https://gitlab.com/BenjaminDobell/Heimdall)
  (macOS/Linux) or Odin (Windows) — your responsibility to set up safely.
- The exact stock firmware `E236BXXSEEZB1` for YOUR device, downloaded via
  [samloader-rs](https://github.com/samloader/samloader-rs), kept as your
  rollback copy. Verify its hash before you start.
- Read `docs/08-stock-restore-runbook.md` BEFORE flashing, not after
  something goes wrong.

## Flashing (BOOT partition only)

```bash
# 1. verify the image
shasum -a 256 v9-boot.img
# must print: 1cf9ff3a...7008af0a

# 2. boot the phone into Download Mode (Vol- + Vol+ while plugging USB)

# 3. flash BOOT only — Heimdall example
heimdall flash --BOOT v9-boot.img

# 4. reboot. First boot fails /data decryption (expected!) →
#    factory reset from recovery, then boot again.
```

Never flash DTBO. Never touch VBMETA. Never repartition or use a custom PIT.
BOOT-only, always.

## After first successful boot

1. Install the **KernelSU legacy manager v3.2.2** (the kernel speaks protocol
   32473; newer managers won't see it). It randomizes its own package name —
   that's normal.
2. Verify root: `adb shell su -c id` → `uid=0(root) ... context=u:r:ksu:s0`.
   SELinux must still report Enforcing.
3. Install the Droidspaces universal APK from
   [Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) — its
   prerequisite checker should go green with this kernel.

## The module stack that the author actually runs (verified live 2026-09-04)

Upstream modules — get them from their own repos/releases:

| Module | Version | Purpose |
|---|---|---|
| Droidspaces | v6.5.0 | the container runtime (KSU module) |
| ZygiskSU | 1.5.0 | Zygisk API on KernelSU |
| Zygisk-Assistant | v2.1.4 | hides Zygisk + spoofs verified-boot props |
| PlayIntegrityFix (osm0sis fork) | v17 | fingerprint spoof for GMS DroidGuard |
| TrickyStore | v1.4.1 | keymaster/attestation spoofing |
| Specter | v1.4.5 | integrity prop management |
| microG (revived) | v1.1.2 | de-Googled Play services (optional) |
| no-shutdown | v1.0 | work-around for the PMIC latch (author's own) |

Author-built modules, included in `release-artifacts/f23-modules.tar.gz`
(verify what's inside before installing anything):

| Module | Version | What it does |
|---|---|---|
| f23_perf | v2.1 | boot-time perf tuning: BBR + fq, TCP buffer raise, KSM force-merge, zstd(L1) zram switch, schedtune boosts, noop elevator. Reverts to stock on uninstall. |
| integrity_rescue ("Boot Rescue") | v1.0 | one-tap post-reboot restore of the integrity-prop stack + Droidspaces autoboot. |

Also included:
- `release-artifacts/r-90-integrity-stack.sh` — boot-completed hook that
  applies the unlock-prop spoofs and starts the containers (see
  `docs/11-post-root-hide-stack.md` for the prop-spoof mechanics).
- `release-artifacts/r-99-f23-perf-launcher.sh` — launches the f23_perf
  keepers after boot.

Install order that was used: unlock → flash v9 → reset → KSU manager →
root grant → Droidspaces → ZygiskSU → Zygisk-Assistant → PIF → TrickyStore →
Specter → f23_perf. Then Droidspaces containers, one at a time.

## If something goes wrong

- Phone bootloops: boot into Download Mode (it doesn't need Android), flash
  your **stock** BOOT, accept that `/data` stays encrypted-junk (the ROT
  re-seal), factory reset, recover from your backups.
- Download Mode itself is unreachable: that's a real brick risk, stop and
  seek hardware help — nothing in this repo can fix that.
- Every failure mode, the captured evidence, and the exact restore runbook
  are in `docs/04`–`docs/08`.

**Again: you flashed it, you own the outcome. The author owes you nothing.**
