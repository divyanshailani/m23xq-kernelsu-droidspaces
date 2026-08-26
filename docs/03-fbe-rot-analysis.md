# Path B research — what feeds the FBE key ROT byte (2026-08-26)

Question: the Step D failure showed vold's keymaster key sealed against ROT
`06000200…` refusing to unwrap under ROT `07000200…`. Is that ROT a **content
hash** of the boot image (then every custom kernel differs, and maybe none can
match) or an **enumerated boot state** (then one format covers all future
custom kernels)? And can any custom boot image hold the ROT at `0x06`?

## Evidence

1. **The ROT blob is 16 bytes, 14 of them zero.**
   `06 00 02 00 00 …` vs `07 00 02 00 00 …`. A SHA-256 content hash (32 bytes)
   or even a truncated one cannot be mostly zeros. This is a state enumeration.
   Byte 2 (`0x02`) matches the AOSP `verified boot state` enum where
   `2 = UNVERIFIED` — consistent with `androidboot.verifiedbootstate=orange`
   in **both** the stock and custom boots. Byte 0 is the Samsung-specific
   boot-integrity composite: `0x06` = unlocked + Samsung-verified boot,
   `0x07` = unlocked + unverified (custom) boot.

2. **AOSP keymaster version binding** (source.android.com): keys are
   cryptographically bound to the Root of Trust that the *bootloader* passes to
   the TEE — verified boot state and verified boot key — exactly the mechanism
   we're hitting. The bootloader computes verification, the TEE seals keys
   against the result.

3. **BK2's AnyKernel3 installer contains no wipe/format logic** (audited:
   `anykernel.sh` + `ak3-core.sh`). Its users flash kernel updates without
   wiping data. If the ROT were content-derived, every BK2 update would break
   /data and the kernel would be unusable in practice. The only consistent
   model: **all custom (non-Samsung-signed) boots produce the same ROT state
   `0x07`**, and the community's one-time format at first custom-kernel install
   re-seals /data against `0x07` permanently.

4. **Returning to `0x06` with a custom kernel is cryptographically impossible.**
   `0x06` requires the boot image hash to match the Samsung-signed hash
   descriptor in the vbmeta partition (digest `a4c36521…` over the first
   52,273,680 bytes of stock boot). Matching it requires Samsung's private
   signing key. The repack preserves the signed vbmeta struct, but the payload
   digest genuinely differs — and that digest is the whole point of the
   integrity check.

## Conclusion

**Path B is dead as a no-wipe route**: no custom boot image can hold ROT at
`0x06`. But it converts Path A from "wipe every time" into a **one-time cost**:

- Format /data **while the custom kernel is in BOOT** → vold creates a fresh
  FBE key sealed against ROT `0x07` → custom kernel boots with /data.
- All future custom-kernel flashes then work **without further wipes** (same
  ROT state), matching BK2 community behavior.
- Caveat (the mirror image): after that format, **stock BOOT would also fail**
  the ROT check (0x06 ≠ 0x07). Returning to permanent stock requires a full
  firmware flash with CSC/HOME_CSC (which wipes again). Each direction switch
  costs a wipe; staying on custom kernels costs nothing further.

## Recommended procedure (requires explicit owner authorization for the reset)

1. Owner re-verifies backups (SmartSwitch copy from 2026-08-24 exists; anything
   created since must be re-backed-up — this reset destroys it).
2. Re-flash `test/boot.img` (Step D kernel, `851a9710…`) to BOOT via samloader
   (BOOT-only, `--no-reboot`).
3. Exit Download Mode (unplug first, Power+VolD).
4. Device lands in the same Recovery screen; this time the owner **accepts
   Factory data reset** (the one authorized destructive action).
5. Reboot → custom kernel boots → vold seals a fresh key against ROT `0x07` →
   Android comes up on the Step D kernel.
6. Verify: custom kernel banner, KernelSU markers in dmesg, then (later, staged)
   KernelSU manager sideload and `droidspaces check`.

Rollback after step 5 (if needed): full stock firmware via Odin/Heimdall with
CSC — costs another wipe, which is unavoidable in that direction.
