# Off-device preflight go/no-go — SM-E236B / m23xq

Date: 2026-08-24

## PASS — completed off-device evidence

- [x] Two independent Smart Switch backup copies were compared previously; recheck required immediately before any unlock.
- [x] Exact stock firmware archive exists on two disks and both copies match SHA-256 `9038a37d8775623765352812390b593ef291f9c4cbdbe5f4c4ff71dcf7eaa496`.
- [x] Qualcomm Snapdragon LLVM ARM 10.0.7 package was authorized, hash-verified, installed privately, and its QSC authorization artifacts were deleted.
- [x] Droidspaces Qualcomm build completed with defconfig/compile exit 0 and no `error:` lines.
- [x] KernelSU v0.9.5 Qualcomm build completed with defconfig/compile exit 0 and no `error:` lines.
- [x] KernelSU source commit/tag, config, kprobe settings, expected symbols, compiler identity, and module metadata were audited.
- [x] Droidspaces kernel prerequisite config and syscall evidence was audited.
- [x] Stock boot, recovery, and DTBO images verify with pinned AOSP AVB tooling.
- [x] Existing structural image proves non-kernel byte preservation and fails the signed boot digest as expected.
- [x] Verified Qualcomm 10.0.7 sizeopt Droidspaces and KernelSU Images fit the stock fixed slot; both structural-only candidates preserve non-kernel bytes and are explicitly nonflashable.
- [x] Pinned AOSP `avbtool` rejects both current structural candidates with the expected signed-payload digest mismatch.
- [x] Exact AP `super.img.lz4` extraction, sparse-to-raw conversion, dynamic-partition inventory, and four logical-partition hashes are recorded with pinned tools.
- [x] `odm`, `product`, `system`, and `vendor` each pass signed footer and SHA-256 hashtree verification; complete `vbmeta_system.img --follow_chain_partitions` verification passes.
- [x] The stock `abl`, `hyp`, `tz`, and `xbl` descriptor-covered prefixes match the top-level signed hash descriptors.
- [x] A pinned universal macOS `samloader-rs` 2.0.0 binary and exact-package Mac-only restore runbook are prepared without invoking a phone-side write.
- [x] Offline stock boot rollback copy is size/hash verified.
- [x] Official bootloader unlock and mandatory userdata wipe completed; post-reset stock Android is stable.
- [x] Final storage check remains above the 16 GiB safety floor.

## BLOCKED — required before any unlock or flash

- [x] A usable Mac Samsung Download Mode recovery host is proven non-destructively. On 2026-08-26 pinned `samloader-rs` 2.0.0 completed the Odin protocol handshake and read the device PIT without invoking firmware transfer, repartition, or another write. The 16,384-byte device PIT was saved and its normalized 92-entry structure matches the exact package's embedded `M23XQ_EUR_OPEN.pit`; the phone returned to Android through samloader's normal cleanup reboot. Heimdall remains protocol-incompatible, but samloader now proves the required Mac recovery session capability. Odin, Windows, Parallels, VM USB passthrough, and Fastboot remain outside this plan.
- [ ] Full top-level AVB verification succeeds. Every descriptor input is now inventoried, the complete system chain passes, and recovery/DTBO plus `abl`/`hyp`/`tz`/`xbl` pass; however, exact-firmware `prism` and `optics` extractions have valid signed embedded vbmeta but unresolved payload hashtree mismatches. AOSP sparse `DONT_CARE` semantics establish that the omitted covered bytes cannot be recovered by ordinary expansion. PIT is now verified separately and does not contain those payload bytes. See `research/avb-resolution-research-2026-08-26.md`.
- [ ] A valid AVB policy is established. Both structural candidates change AVB-covered bytes and fail the signed payload digest; preserving stock metadata is insufficient, and no stock private key is available.
- [ ] The user explicitly accepts mandatory userdata wipe, likely permanent Knox trip, Secure Folder/payment/enterprise impact, and daily-phone downtime.
- [x] Backup and account recovery checks are repeated immediately before any destructive step. Both Smart Switch trees are present at approximately 21 GiB; the only difference is one 18,436-byte Apple Desktop Services metadata file, with no content-change records. Exact firmware copies and rollback artifacts rehashed successfully. Full details: `research/final-pre-unlock-verification-2026-08-26.md`.

## NOT TESTED — requires an unlocked device

- [ ] KernelSU manager installation, root grant, allowlist, safe mode, and post-fs-data behavior.
- [x] Official bootloader unlock completed; userdata wipe completed; untouched stock Android baseline passed three clean reboots with ADB/boot completion, `device_state=unlocked`, `flash_locked=0`, AVB `orange`, SELinux enforcing, file-based encryption active, exact stock kernel unchanged, and USB charging stable. Full evidence: `research/post-unlock-stock-baseline-2026-08-26.md`.
- [ ] Kernel boot, suspend/resume, repeated reboot, cellular/radio, Wi-Fi, Bluetooth, camera, audio, charging, encryption, and thermal stability for a custom kernel.
- [ ] Vendor module loading and Samsung kernel ABI compatibility.
- [ ] Android SELinux transitions and AVC behavior.
- [ ] FBE/keyring behavior and loop-backed rootfs mounting.
- [ ] Manual Droidspaces requirement checker.
- [ ] Disposable container with networking disabled.
- [ ] Cgroup, namespace, mount, systemd, shutdown, and orphan recovery behavior.
- [ ] NAT/firewall coexistence.
- [ ] Userspace daemon persistence and process-lifetime behavior.
- [ ] Native init/vendor/CIL integration; this remains a separate high-risk path.

## Current decision

**NO-GO for custom-image flash until the next staged gate is completed.** The official unlock and wipe are complete, and untouched stock Android passed the three-reboot baseline. The top-level `prism`/`optics` audit remains an offline reconstruction limitation; it does not authorize AVB metadata changes. The next custom-image stage remains untested and must be treated as a separate boot/recovery experiment.

Off-device builds and static image/kernel evidence collection are complete. Exact super extraction and the complete system AVB chain pass. The top-level chain remains blocked at the exact-firmware `prism`/`optics` payload hashtrees, but the Mac recovery-host protocol gate is now PASS: samloader completed a non-writing PIT read and the phone returned to Android normally. AVB deployment policy, user risk acceptance, and all Android runtime gates remain incomplete. Compile success, compiler matching, DTB equality, kernel prerequisites, fixed-slot fit, and a valid stock system chain do not establish custom-kernel bootability, AVB acceptance, vendor compatibility, SELinux compatibility, or flashability.

The next safe device-side boundary, when explicitly authorized, is not PIT testing—the Mac PIT/recovery-session gate is complete. Any future device work would require a separate destructive authorization boundary. Separately, the `prism`/`optics` extraction mismatch remains an offline investigation. Until AVB policy, risk acceptance, and runtime gates are resolved, keep the phone locked, stock, and untouched.
