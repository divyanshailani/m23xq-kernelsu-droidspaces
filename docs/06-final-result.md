# FINAL RESULT — KernelSU + Droidspaces kernel running on SM-E236B (2026-08-26)

Device: Samsung Galaxy F23 5G / SM-E236B / m23xq / Android 14 / E236BXXSEEZB1.
Bootloader: unlocked (Knox 0x1 tripped at unlock).

## Goal → Status

| Goal | Status |
|---|---|
| Custom kernel boots Android | **PASS** — `4.19.152-perf #1 SMP PREEMPT Wed Aug 26 06:54:45 UTC 2026`, daily-usable, survives reboots, /data rw, SELinux Enforcing |
| KernelSU root | **PASS** — manager v3.2.2-10-legacy (32490) reports "Working, legacy version 32473"; `su -c id` → `uid=0(root) context=u:r:ksu:s0` |
| Droidspaces kernel prerequisites | **PASS at kernel level, verified live from userspace** (see below) |
| Droidspaces runtime (containers) | **NOT YET TESTED** — next stage: install Droidspaces binaries, `droidspaces check`, disposable rootfs |

## What the kernel contains

Samsung `m23xq_swa_open` 4.19.152 source + rsuntk/KernelSU @ `648e5988`
(manual-hook fork: five build-time call-site patches, LSM `task_fix_setuid`
hook, zero kprobes) + all 21 Droidspaces prerequisites + `ANDROID_PARANOID_NETWORK`
off. Security posture: `UH/RKP/HDM/PROCA/FIVE/DEFEX/SDP` all kept at stock `y`;
only the `KDP` family is off (structurally incompatible with any root).
`KPROBES` off (stock). Verified in `.config` post-build, 37 invariants.

## Live root verification (the money quotes)

```
$ adb shell su -c id
uid=0(root) gid=0(root) groups=0(root) context=u:r:ksu:s0

$ dmesg | grep KernelSU
KernelSU: set root profile, key: com.android.shell, uid: 2000, gid: 0, context: u:r:ksu:s0
KernelSU: do_execveat_common su->ksud!
```

The su mechanism: the kernel intercepts exec of `/system/bin/su` (which doesn't
exist on disk) and redirects it to `/data/adb/ksud` with root creds — for
allowlisted UIDs only. Shell (2000) was allowlisted via the manager's Superuser
tab. The manager installs under a randomized package name (`wffxxf.nclgit.cawxcw`)
as anti-detection; that is expected.

## Live Droidspaces prerequisite verification (all with root, all PASS)

| Prerequisite | Test | Result |
|---|---|---|
| PID/mount namespaces | `unshare -m -p -f` → `NSpid: 31523 1` (PID 1 in ns) | PASS |
| User namespaces | `unshare -U` → overflowuid (ns unmapped, correct) | PASS |
| IPC namespace | `unshare -i` | PASS |
| UTS namespace | `unshare -u` + hostname change | PASS |
| Net namespace | `unshare -n` → isolated loopback | PASS |
| cgroups: devices/pids/net_prio | `/proc/cgroups` shows all enabled (stock: all off) | PASS |
| SysV IPC | `/proc/sys/kernel/msgmax` = 8192 | PASS |
| POSIX mqueue | `mount -t mqueue` succeeds | PASS |

## The road here (condensed)

1. **Stage 1 (v0.9.5 + kprobes)**: kernel panicked at 1.59 s — `BRK #0x4`,
   kprobe breakpoint in RKP-write-protected text. Root cause established via
   surviving Samsung ramdumps in `/data/log`.
2. **Step C (nohyp)**: removing UH/RKP did not help — upload PASS, Android FAIL,
   same `fs_mgr_mount_all:M02R`. This was actually the ROT failure all along.
3. **Step D (manual-hook fork)**: kprobe panic gone; kernel ran clean to 5.09 s
   and died at vold: `KeyStorage: checkRotStr ROT value was invalid`
   (`0x06` saved vs `0x07` current) → `decryptWithKeystoreKey fail` → M02R.
4. **Path B research**: the ROT is a 16-byte enumerated boot state (not a hash)
   — `0x06` = Samsung-signed boot, `0x07` = custom boot. No custom image can
   hold `0x06`; but one format with a custom kernel in BOOT re-seals /data for
   all future custom kernels (matches BK2 ecosystem behavior — no wipe logic
   in its installer).
5. **Path A (owner-authorized)**: re-flashed the Step D kernel, owner accepted
   the recovery Factory data reset, and the custom kernel booted Android with
   vold sealing a fresh key against ROT `0x07`.

## Current device state & standing caveats

- BOOT = Step D kernel (sha256 `851a9710…`); everything else stock, DTBO never
  written, VBMETA never written in the final path.
- **Stock BOOT would now fail to boot** (mirror-image ROT mismatch: key sealed
  for `0x07`, stock recomputes `0x06`). Returning to permanent stock requires a
  full firmware flash with CSC (wipes again). Staying on custom kernels: no
  further wipes, per the ROT-state analysis.
- Future custom-kernel updates: build → repack flags=0 → flash BOOT. Same
  procedure, no reset.
- Rollback artifacts for the *previous* stock state remain hash-verified in
  `artifacts/device-test-stepd-manualhook-2026-08-26/rollback/` but flashing
  stock BOOT alone will now hit the ROT wall — use the full-stock-firmware
  runbook instead.

## Next stage (not started): Droidspaces runtime

Per the staged plan (`research/droidspaces-requirements-matrix.md`):
1. `droidspaces check` (manual prerequisite checker) — the kernel-side table
   above predicts a clean pass.
2. Manual daemon start, disposable Alpine-style rootfs, networking `none`.
3. Only after stable local operation: NAT/networking, persistence.

## Key artifacts

- Kernel build: `artifacts/ksu-manualhook-droidspaces-qcom-10.0.7/`
- Repack manifest: `artifacts/ksu-manualhook-repack-2026-08-26/manifest.json`
- Manager APK: `artifacts/ksu-manager/KernelSU_v3.2.2-10-legacy-42-g915b4872_32490-release.apk` (sha256 `78fe8098…`)
- Step D protocol/results: `research/stepd-*-2026-08-26.md`
- ROT analysis: `research/pathb-rot-analysis-2026-08-26.md`
