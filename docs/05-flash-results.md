# Step D results — manual-hook KernelSU + Droidspaces kernel (2026-08-26)

Device: SM-E236B / m23xq / Android 14 / `E236BXXSEEZB1`, bootloader unlocked.
Candidate: `boot-ksu-manualhook-droidspaces-qcom-10.0.7-repack-flags0` (sha256
`851a97100c28256282129e6324d766777557831321dd756835af3348a965876d`).
Protocol: `research/stepd-manualhook-droidspaces-test-protocol-2026-08-26.md`.

## Classification

| item | result |
|---|---|
| Baseline (stock banner, /data rw, battery 100% @ 32.6 °C, both firmware copies rehashed `9038a37d…`) | **PASS** |
| Download Mode entry + samloader-rs session (pinned, hash-verified) | **PASS** |
| BOOT upload (`--no-reboot`, no VBMETA, no other partition) | **PASS** — clean `EndSession` |
| Bootloader acceptance of oversized-kernel repack (53,248,016 > 51,138,576 slot) | **PASS** |
| Custom kernel execution past the 1.59 s kprobe panic point | **PASS** — no KP dump, no BRK, ran to 5.09 s |
| KernelSU init | **PASS** — 42 log lines; feature mgmt, LSM SIDs cached, init.rc appended |
| Android userspace mount of /data | **FAIL** — `checkRotStr ROT value was invalid` → `decryptWithKeystoreKey fail` → `security.fbe.fail_cause: M02R` → init rebooted to recovery |
| KernelSU root / Droidspaces runtime | **NOT TESTED** (never reached Android) |
| Stock restore + /data intact + 2 clean NP reboots | **PASS** |

## The decisive evidence

Boot history shows **no KP entry** in the Step D window — the only new dump
(14:15) is `MP` (manual power-off, from the button exit), and its kmsg contains
our kernel's banner (`root@89bbd86122a3`, built 06:54:45 UTC) followed by a
healthy boot:

- 0.0 s kernel starts, all drivers probe normally
- 1.09 s `KernelSU: feature management initialized`, full IOCTL table, handlers
  registered
- 2.83 s `KernelSU: /system/bin/init second_stage executed`, SIDs cached
  (su=68, zygote=69, init=70, ksu_file=71)
- 2.92 s `KernelSU: read init.rc … append done`
- 3.0 s ueventd, apexd bootstrap, servicemanager
- 4.4–4.5 s system/persist/omr ext4 partitions mount fine
- 4.85 s `MetadataCrypt: read_key /metadata/vold/metadata_encryption/key`
- 5.07 s **the failure**, verbatim:

```
KeyStorage: checkRotStr ROT value was invalid
KeyStorage: checkRotStr current rot value : 07000200000000000000000000000000
KeyStorage: checkRotStr saved rot value   : 06000200000000000000000000000000
KeyStorage: decryptWithKeystoreKey fail
voldUtils: PROP : security.fbe.fail_cause : , value M02R
vdc: Command: cryptfs mountFstab …/userdata /data Failed: Status(-8)
init: reboot, recovery
```

Also present: `convertKeyParametersToLegacy : KM_TAG_SAMSUNG_ROT_REQUIRED = 10`
and `begin : result = -33` (KE_… error from the keymaster TA) immediately before.

## Interpretation

1. **The stage-1 kernel problem is solved.** The v0.9.5 kprobe `BRK #0x4` panic
   is gone. The rsuntk manual-hook fork with `CONFIG_KPROBES=n`, `KDP` family
   off, `UH/RKP` on, is boot-stable on this device. This also retroactively
   explains the nohyp test: disabling UH never addressed this failure either —
   both kernels died here, at the same place, for the same reason.

2. **The remaining blocker is Samsung's FBE key ROT (Root of Trust) check.**
   vold asks Keymaster to decrypt the /data metadata key; Samsung's keymaster
   TA (`skeymast`/fabrickeymaster) binds key operations to a Root-of-Trust
   value derived from verified-boot state. The saved ROT (`0x06…`, written when
   /data was formatted under stock boot) no longer matches the current ROT
   (`0x07…`, computed now that our custom BOOT is in place). The unwrap fails,
   vold reports M02R, init reboots to recovery with the "Can't load Android
   system" screen.

   This is stronger than the earlier `vbmeta.digest` hypothesis: the ROT is a
   Samsung extension (`KM_TAG_SAMSUNG_ROT_REQUIRED`), and its value is a small
   counter/flags word (byte 0: 0x06 vs 0x07 — likely an enumerated
   verified-boot/locked-state code, not a digest). One byte changed.

3. **Why stock boots fine:** under stock BOOT the current ROT recomputes to the
   same `0x06…` as saved, the key unwraps, /data mounts. Nothing about /data
   itself is corrupt — restoration proved the partition and its key are both
   intact.

## What this means for the goal (KernelSU + Droidspaces)

The kernel is no longer the gate. The gate is the FBE metadata key, and there
are exactly three families of resolution:

- **A. Re-format /data with the custom kernel installed** (accept the recovery
  factory data reset, or `fastboot -w` equivalent). After format, vold writes a
  fresh metadata key sealed against ROT `0x07…`, and the custom kernel then
  boots with /data mounted. Cost: full data loss (backups exist; Knox already
  tripped). This is what every m23xq custom-kernel guide implicitly does.
- **B. Understand and normalize the ROT byte** — determine exactly what
  keymaster hashes into the ROT (boot hash? verified-boot state flags? unlock
  state?) and whether any *stock-shaped* boot image can hold ROT at `0x06`
  while carrying our kernel. The repack changes boot bytes, so if the ROT is
  boot-hash-derived this can't converge; if it is state-flag-derived, a flags
  variant might. Off-device research only.
- **C. Avoid the ROT check** — e.g. ship a kernel whose userspace disables FBE
  key rotation checks; requires modifying ramdisk (currently byte-identical to
  stock, a property we've preserved deliberately).

Recommendation: pursue **B** off-device first (cheap, may be decisive), with
**A** as the authorized-destructive fallback the owner has already been
braced for. Do not re-flash the candidate until B is answered or A is
authorized.

## Operational notes from this run

- Exit from Download Mode requires **unplugging USB first**; with power applied
  the Power+VolD combo can re-enter Download Mode instead of rebooting.
- The first exit attempt left the phone in Download Mode with **USB not
  enumerating** on the host (hub-mediated). Unplug/replug + direct port
  recovered it. `samloader reboot-download` cannot force a reboot *out* of
  Download Mode (it re-enters it).
- All recovery "Factory data reset" prompts were declined per standing rule;
  /data survived all four flash/restore cycles byte-verified intact.

## Artifacts

- Postmortem: `artifacts/device-test-stepd-manualhook-2026-08-26/postmortem/`
  (14:15 MP dump + extracted kmsg + recovery.log + power_off_reset_reason.txt)
- Flash logs: `research/stepd-flash-upload.log`, `research/stepd-stock-restore.log`
- Repack manifest: `artifacts/ksu-manualhook-repack-2026-08-26/manifest.json`
