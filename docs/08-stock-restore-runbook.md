# Mac-only stock restore runbook — SM-E236B / INS

Status: preparation only; no live flash command; phone remains locked, stock, and untouched.

## Frozen inputs

Use only the two independently hashed copies of the exact `E236BXXSEEZB1` package:

- Archive size: `7,103,627,005` bytes
- SHA-256: `9038a37d8775623765352812390b593ef291f9c4cbdbe5f4c4ff71dcf7eaa496`
- Package members: matching `BL`, `AP`, `CP`, `CSC_ODM`, and `HOME_CSC_ODM` tar.md5 files
- Firmware generation: `E236BXXSEEZB1`, bootloader binary `E236B`

Do not mix files from another model, CSC, bootloader generation, or firmware release. Do not use a custom boot candidate as a restore input.

## Host gate

The Mac has Heimdall v1.4.2, but its USB detection passes while handshake/protocol initialization and PIT access fail. Pinned `samloader-rs` v2.0.0 was tested on 2026-08-26 in the authorized non-writing boundary:

- The phone left ADB after `adb reboot download`.
- `samloader detect` transiently reported `Device detected` after USB enumeration showed the Samsung Download Mode interface.
- The interface disappeared before the corrected `print-pit` transaction.
- `samloader --verbose print-pit` and one `print-pit --wait` attempt failed without returning PIT data.
- No `flash`, `repartition`, `reboot-download`, or other write-capable action was invoked.

This gate is now proven non-destructively. On 2026-08-26 `samloader-rs` completed the Odin handshake and retrieved the device PIT; the saved 16,384-byte PIT has normalized 92-entry structure matching the exact package PIT. The session ended with samloader's normal reboot cleanup, and the phone returned to Android with verified boot green and locked state. This proves the Mac can establish a Samsung recovery session for this device; it still does not authorize flashing.

## Package/PIT mapping

The archive's CSC package contains `M23XQ_EUR_OPEN.pit`. The PIT is a layout reference only. It must not be supplied to a repartition operation. The exact package's BL/AP/CP/CSC grouping is:

- BL: bootloader and firmware boot-chain payloads
- AP: Android platform payloads, including boot, recovery, super, DTBO, vbmeta, and vbmeta_system
- CP: modem/baseband payloads
- CSC_ODM: clean-region/customer configuration and ODM payloads
- HOME_CSC_ODM: customer configuration variant intended to preserve userdata during ordinary servicing

This document deliberately does not include a live command or GUI click sequence capable of writing partitions.

## Recovery choice

- `HOME_CSC_ODM` is the less-destructive servicing choice when userdata is believed healthy, but it is not a reliable repair for damaged userdata, encryption, or a failed custom boot state.
- `CSC_ODM` is the clean recovery baseline and normally wipes userdata. For an emergency return from a custom-kernel/root failure, use only after the exact package and a proven host workflow are revalidated immediately before the write.
- A complete stock restore means matching BL/AP/CP plus the appropriate CSC package; restoring only `boot` is not an unbrick plan.

## Hard stops before any future write

Stop if any of these is true:

1. Either firmware copy no longer matches the frozen archive hash.
2. Backups, account recovery, Secure Folder expectations, and authenticator/passkey recovery have not been rechecked immediately before the destructive step.
3. The Mac tool cannot complete a non-writing Download Mode protocol/PIT session.
4. The exact package is not readable from the same host and direct USB path intended for recovery.
5. The phone is needed for daily calls, authentication, work, travel, or account recovery.
6. Battery, cable, USB port, or power stability is uncertain.
7. The candidate or recovery state would require relocking with any custom partition still installed.
8. The operation would involve EFS, persist, modem calibration, keymaster, keydata, RPMB, or other device-bound security/radio partitions outside the exact stock package.

## Post-restore verification checklist

If a future authorized stock restoration occurs, verify before calling the phone recovered:

- Android boots completely and verified boot is green.
- Samsung Official/current binary and intended lock/KG/OEM state are shown.
- Cellular registration, calls, SMS, mobile data, SIM behavior.
- Wi-Fi, Bluetooth, GPS, camera, microphone, speaker, vibration.
- USB data/charging and normal Mac Android detection.
- Encryption, screen lock, storage access, and Secure Folder expectations.
- Charging, suspend/resume, thermals, and at least three clean reboots.
- No unexplained SELinux, watchdog, radio, storage, or kernel failures.

## Decision

This runbook documents rollback prerequisites and stop conditions only. It does not prove the Mac recovery workflow, does not authorize an unlock, and does not authorize a flash. Current status remains **NO-GO**.
