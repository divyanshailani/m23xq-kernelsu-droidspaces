# Step D — manual-hook KernelSU + Droidspaces BOOT-only test protocol (2026-08-26)

Device: SM-E236B / m23xq / Android 14 / `E236BXXSEEZB1`, bootloader unlocked.
Authorization: **pending.** This document stages the procedure; it authorizes no write.
The owner must explicitly authorize the upload (and separately, any factory data reset —
see the `/data` section) before it runs.

## What this candidate is

The merged kernel: Samsung `m23xq_swa_open` 4.19.152 source, `rsuntk/KernelSU` at
`648e5988` (the exact fork and commit BK2 pins), the five build-time call-site hooks
(`fs/open.c`, `fs/stat.c`, `fs/exec.c`, `fs/read_write.c`, `drivers/input/input.c`),
and all 21 Droidspaces kernel prerequisites. Packaged by magiskboot repack at
`PATCHVBMETAFLAG=false` (flags=0) because the Image (53,248,016 bytes) exceeds the
stock kernel slot by 2.1 MB — the same packaging the nohyp device test proved the
bootloader accepts (51,154,960 bytes over slot, upload PASS).

## Hypothesis under test

The stage-1 panic was `BRK #0x4` at `__arm64_sys_faccessat` under `CONFIG_RKP=y`:
KernelSU v0.9.5's **runtime kprobe** tried to write a breakpoint into RKP
write-protected kernel text. This candidate removes the mechanism entirely —
rsuntk's fork registers an **LSM hook** (`task_fix_setuid` via `security_add_hooks`,
the same window SELinux uses) and patches the five call sites **at build time**, so
no kprobe is ever registered and `CONFIG_KPROBES` stays off exactly as Samsung ships.
Privilege interception now happens where the hypervisor expects kernel code to live
legitimately.

Versus the panicking build, the deltas are: KSU fork swap (kprobe → LSM + manual
hooks), `KPROBES` off, `KDP` family off, 21 Droidspaces symbols on,
`ANDROID_PARANOID_NETWORK` off. Versus the nohyp build (upload PASS, Android FAIL),
the deltas are: `UH/RKP/HDM` **restored to stock `y`**, `KDP` family off,
Droidspaces symbols on.

`KDP` stays off deliberately and permanently: `KDP_CRED` routes every `commit_creds()`
through the hypervisor's RO-cred minting, demotes root `execve` callers to uid 2000,
and panics on foreign creds — it is structurally incompatible with any root
implementation. `UH=y RKP=y KDP=n` is a legal Kconfig combination (verified: RKP only
`depends on UH`; nothing selects KDP).

## Artifacts

| role | file | SHA-256 | bytes |
|---|---|---|---|
| candidate | `test/boot.img` | `851a97100c28256282129e6324d766777557831321dd756835af3348a965876d` | 100,663,296 |
| rollback | `rollback/boot.img` | `3abd7ea170aa7c53eff61d4ee87f60100709166ce6242353aae1e117b293c2be` | 100,663,296 |

Candidate provenance: `artifacts/structural-only/boot-ksu-manualhook-droidspaces-qcom-10.0.7-repack-flags0-NONFLASHABLE.img`,
full manifest at `artifacts/ksu-manualhook-repack-2026-08-26/manifest.json`.
Embedded kernel: `Image` sha256 `5034788912c69a1e5ad8856ad8861d56dd28463bb549eadeaba1429e935cff66`,
banner `Linux version 4.19.152-perf (root@89bbd86122a3) (clang version 10.0.7 …)`,
261 KernelSU strings, all five `ksu_handle_*` symbols present in vmlinux as text symbols.

## Upload controls

Identical to the nohyp protocol, inherited unchanged:

- Pinned `samloader-rs` 2.0.0, SHA-256 `ec3e3c2f891d816b8bbe8c3ce891a6ff3e20402414f83920a1d6773d8ca095fd`.
- **BOOT only** (`--partition BOOT`, PIT `0x19`). No VBMETA — the ramdump already
  proved the bootloader accepts these images and both flags=3 vbmeta artifacts are
  permanently burned.
- `--no-reboot`; classify upload before boot.
- No `--repartition`, `--pit`, `--skip-size-check`, `--skip-md5`.
- No USERDATA, no EFS/persist/modem/keymaster/keydata/RPMB/recovery/super/dtbo/vbmeta.
- DTBO untouched (our overlays are semantically identical to stock; BK2's are a
  different board variant and must never be written).

## Sequence

1. Baseline: stock kernel booted, `/data` mounted, battery ≥ 95%, USB stable, both
   firmware copies rehashed to `9038a37d8775623765352812390b593ef291f9c4cbdbe5f4c4ff71dcf7eaa496`.
2. `adb reboot download`, confirm Download Mode enumeration.
3. Upload `test/boot.img` to `BOOT` with `--no-reboot`. Classify upload PASS/FAIL.
4. Reboot. Allow at most 120 seconds for Android/ADB.
5. **If Android reaches ADB:** capture `uname -a`, verified-boot properties, SELinux
   state, `/data` mount state, bounded `dmesg` (look for `KernelSU:` init lines and
   confirm no `BRK`/kprobe traces), and — new for this candidate — the namespace/
   IPC availability the Droidspaces prerequisites provide (`/proc/self/status`
   `NStgid` line, `ls /sys/fs/cgroup` device/pids controllers). Do not install the
   KernelSU manager and do not run `droidspaces` in this pass.
6. **If it does not:** classify FAIL, harvest diagnostics (below), return to Download
   Mode, restore `rollback/boot.img`.
7. Regardless of outcome, restore exact stock `BOOT`, verify the stock banner and at
   least two clean reboots.

## Diagnostics on failure (the most valuable output)

- Harvest `/data/log/power_off_reset_reason.txt` and any new
  `dumpstate_lastkmsg_*_KP.log.gz` immediately — the surviving ramdump is what made
  every prior diagnosis possible.
- Read `/data/log/recovery.log` off-device, not off the phone screen.
- The decisive question the ramdump answers: did the `BRK #0x4` kprobe panic move,
  disappear (kernel died later for another reason), or never happen (failure is in
  the vendor/userspace handoff)? Each answer picks a different next experiment.
- A fresh `--reason=fs_mgr_mount_all:M02R` entry **with no kprobe panic preceding
  it** would be strong evidence for the AVB-measurement-bound `/data` hypothesis
  (Keymaster key derivation incorporates `ro.boot.vbmeta.digest`; every published
  m23xq custom-kernel procedure includes a userdata format for this reason).

## The `/data` question — separate authorization required

The nohyp test (identical packaging) reached the Samsung warning screen and then
Android Recovery with "Can't load Android system." If this candidate gets past the
kernel (no panic in the ramdump) and still lands in the same place, the remaining
suspect is `/data` metadata-encryption key derivation, which binds to
`ro.boot.vbmeta.digest`. Resolving it requires accepting the recovery
**factory data reset** prompt — a destructive action that needs explicit owner
authorization at that moment, not in advance. Everything in this protocol up to that
prompt is non-destructive; the prompt itself must be declined unless the owner says
otherwise, and stock BOOT is restored instead.

## Stop conditions

Before upload: any baseline, hash, storage, battery, or USB deviation.

During upload: on failure, do not reboot Android; fresh Download Mode session and
restore stock BOOT with no auto-reboot. If stock restoration fails, stop.

After reboot: restore stock immediately on repeated warning/reboot cycling, abnormal
heat, display/touch failure, charging loss, radio loss, or ADB absence past the
bounded wait. Never accept the recovery "Factory data reset" prompt without separate
explicit authorization.

## Classification rules

Upload acceptance, bootloader policy, kernel execution past 1.59 s, Android
userspace, `/data` mount, encryption, hardware basics, KernelSU runtime, and
Droidspaces runtime are **independent** results. A successful upload or warning
screen is not a boot. `droidspaces check` passing config-level prerequisites is not
a container. Do not merge these into a single pass/fail.
