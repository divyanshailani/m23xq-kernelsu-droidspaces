# BoostKernel2 control-package audit — 2026-08-26

Two releases audited: **v10.3.5** (Feb 2026) and **v11.6.1** (May 2026). See the
"Second control package" section at the end for the v11.6.1 delta.

## Scope

Off-device audit of the first known-good, device-specific custom kernel package for
Samsung SM-E236B / m23xq. This is **control evidence only**. BoostKernel2 is not a
project deliverable, is not to be flashed as a product artifact, and its kernel is
not to be reused in any PocketWright/Droidspaces build. The phone was not touched.

## Provenance

- XDA thread 4750211, "BoostKernel 2", 2025-07-16, by mrsiri.
- Telegram artifact `Boostkernel2-v10.3.5.zip`, caption "This is the same as 10.3.4 but NO SUSFS", dated Feb 13 07:12.
- Downloaded by the device owner; staged at
  `artifacts/control-boostkernel2-v10.3.5/Boostkernel2-v10.3.5.zip`.
- Size `21,996,885` bytes.
- SHA-256 `623f9304c0cd698a1055996365b473aa130b84ba3a16182b78007d36fe6e5613`.
- Source repository (live): `Aflaungos/android_kernel_samsung_sm7225_testing`,
  branch `Boostkernel2`, HEAD `d841bda2ef8300d35dfe29225146b24e614e0221` (2026-08-07).
- Legacy repository: `Aflaungos/android_kernel_samsung_sm7225`, default branch
  `lineage-23.0`, HEAD `902611e85cac`, last push 2026-03-13. This is a LineageOS
  kernel tree, not the BoostKernel2 build tree; it carries
  `arch/arm64/configs/vendor/lineage-m23xq_defconfig` and
  `arch/arm64/configs/vendor/m23xq_eur_open_defconfig`, has **no** `KernelSU`
  directory and **no** `drivers/kernelsu`, and is the ROM-side companion rather
  than the shipping kernel source.
- `Aflaungos/android_kernel_samsung_m23xq` — the repository named in the Brave
  screenshot — **does not exist**.

## Member hashes

| Member | Size | SHA-256 |
| --- | --- | --- |
| `Image` | 39,817,232 | `a5f391b71286f42a3e2ce21062c2163d40ea926916591e2bee0d4a8d5839c990` |
| `dtb` | 340,965 | `f4b47a37840f5e3c269e2b404aedc9dbf3fc084e5a189d1dd74f085eb9b858dd` |
| `dtbo` | 1,229,985 | `7ccafefa86c7d3bb360ec9631cb4a18c5fdad03dc2bb8c1287549a9a756472dc` |
| `anykernel.sh` | 3,493 | `552a1010b2b2a3024bc7552900a4aed0c1644787675ea26250b4d61ebfd97ee2` |
| `tools/magiskboot` | 621,588 | `58abd6b6d468f5d1f2eba7cebd3c00643e9a834fc2d0a5d87c0a8ae4621db2ab` |
| `tools/ak3-core.sh` | 34,023 | `0019d398688fe7b0a43ea82a55880dee85408e59b13471f410cd33a8f14ff774` |

`modules/system/lib/modules/`, `patch/`, and `ramdisk/` are **empty** directories.
AnyKernel3 base version `AK_BASE_VERSION=20240509`.

## Kernel identity — PASS (read directly from `Image`)

```
Linux version 4.19.325-Boostkernel 2 v10.4 (Mrsiri@Mrsiri)
  (Android (10087095, +pgo, +bolt, +lto, -mlgo, based on r487747c)
   clang version 17.0.2 (... d9f89f4d16663d5012e5c09495f3b30ece3d2362), LLD 17.0.2)
  #10 SMP PREEMPT Thu Feb 12 22:29:06 -03 2026
```

- ARM64 header: `magic=ARMd`, `text_offset=0x80000`, `image_size=51,081,216`, `flags=0xa`.
  Identical `text_offset` and `flags` to stock; stock `image_size` is `63,135,744`.
- Kernel release: `4.19.325-Boostkernel 2 v10.4`.
- KernelSU present: the `/data/adb/ksud` marker that `ak3-core.sh` greps for **is**
  in the image, along with `ksud post-fs-data` / `services` / `boot-completed`
  invocations and KernelSU log strings. So this shipping build has KernelSU
  compiled in.

The archive is labelled v10.3.5 but the kernel inside identifies as v10.4; the
in-tree defconfig currently reads v11.9.3. Version labels in this project are not
reliable identifiers — only the `Linux version` string and hashes are.

## IKCONFIG anomaly — the embedded config is NOT this kernel's config

`Image` contains exactly one `IKCFG_ST`…`IKCFG_ED` region (offset 23,508,760).
Decompressed it is `178,926` bytes / 6,652 lines, SHA-256
`74871c58d6716c062ce3d8451d07faf2d65d75a6146fd55f0ae5d0a329f41f74`, and its header
reads:

```
# Linux/arm64 4.19.152 Kernel Configuration
# Compiler: clang version 10.0.7 for Android NDK
CONFIG_CLANG_VERSION=100007
CONFIG_LOCALVERSION="-perf"
```

That is byte-identical to `arch/arm64/configs/vendor/stock_defconfig` in the
BoostKernel2 tree (blob `cd2e5c8c8b49f93bf79b351a0998465f586eb2f7`), and it
contradicts the binary itself, which is 4.19.325 built with clang 17.0.2. It also
contains no `CONFIG_KSU` at all while the binary demonstrably has KernelSU.

The kernel actually built from `vendor/m23xq_eur_open_defconfig`
(blob `68a0b523f011e1f91673cdd6b674bcc6e1b4ef1e`, `179,056` bytes / 6,633 lines,
SHA-256 `3ac8e9f2c83d3494968e717bf6d62aafaed8cfe13e853793ade5959c75273b82`), which
matches the binary: `CONFIG_CLANG_VERSION=170002`, `CONFIG_LD_IS_LLD=y`,
`CONFIG_LTO_CLANG=y`, `CONFIG_LOCALVERSION="-Boostkernel 2 v11.9.3"`.

**Consequence:** `/proc/config.gz` on a BoostKernel2 device reports the stock
4.19.152 config, not the running kernel's. Any conclusion drawn from a
BoostKernel2 `/proc/config.gz` would be wrong. The tree ships a stale checked-in
`stock_defconfig` copy that ends up embedded. We must not use `/proc/config.gz`
from this kernel as evidence of anything.

## The decisive finding: BoostKernel2 removes Samsung's hypervisor and integrity stack

The real BoostKernel2 defconfig does not merely disable these symbols — the
symbols **do not exist in its Kconfig at all**:

| Symbol | Stock device kernel | Our KernelSU build | BoostKernel2 |
| --- | --- | --- | --- |
| `CONFIG_UH` | `y` | `y` | absent from Kconfig |
| `CONFIG_RKP` | `y` | `y` | absent |
| `CONFIG_KDP` | `y` | `y` | absent |
| `CONFIG_KDP_CRED` | `y` | `y` | absent |
| `CONFIG_KDP_NS` | `y` | `y` | absent |
| `CONFIG_RUSTUH_RKP` | `y` | `y` | absent |
| `CONFIG_RUSTUH_KDP` | `y` | `y` | absent |
| `CONFIG_SECURITY_DEFEX` | `y` | `y` | absent |
| `CONFIG_PROCA` | `y` | `y` | absent |
| `CONFIG_FIVE` | `y` | `y` | absent |
| `CONFIG_SECURITY_DSMS` | `y` | `y` | absent |
| `CONFIG_TZDEV` | present | present | absent |

Confirmed structurally: `security/samsung/`, `drivers/uh/`, and `init/uh/` are all
**404 in the BoostKernel2 tree**. Only the orphan header `include/linux/uh.h`
(826 bytes) survives. The tree is a de-Samsung-ised 4.19.325 upstream-merged
kernel with `drivers/kernelsu` and a `KernelSU` directory added.

Other material config deltas:

| Symbol | Our build | BoostKernel2 |
| --- | --- | --- |
| `CONFIG_MODULE_SIG` | `y` | not set |
| `CONFIG_MODULE_SIG_FORCE` | `y` | not set |
| `CONFIG_CC_OPTIMIZE_FOR_SIZE` | `y` | `PERFORMANCE` |
| `CONFIG_LTO` | `LTO_NONE` | `LTO_CLANG` |
| `CONFIG_LD_IS_LLD` | absent (GNU ld) | `y` |
| `CONFIG_ANDROID_VENDOR_HOOKS` | absent | `y` |
| `CONFIG_MACH_M23XQ_*` | `SWA_OPEN` | `EUR_OPEN` |
| `CONFIG_BUILD_ARM64_DT_OVERLAY` | not set | `y` |
| `CONFIG_AUDIT` | `y` | not set |
| `CONFIG_LOG_BUF_SHIFT` | 17 | 20 |

`CONFIG_ANDROID_PARANOID_NETWORK=y` in BoostKernel2 — it does **not** take the
host-wide security tradeoff our Droidspaces build takes.

## Container prerequisites — Brave's Image 3 is refuted twice over

BoostKernel2 enables `CGROUPS`, `MEMCG`, `NAMESPACES`, `SECCOMP`, `BLK_DEV_LOOP`,
`VETH`, `FUSE_FS`, `OVERLAY_FS` — i.e. roughly what the stock kernel already
enables, and **less** than our Droidspaces build, which has every LXC prerequisite
PASS in `research/droidspaces-qcom-10.0.7-sizeopt-verified-audit.json`. The stock
device config itself already carries `CONFIG_NAMESPACES=y`, `CONFIG_MEMCG=y`,
`CONFIG_SECCOMP=y`, `CONFIG_OVERLAY_FS=y`, `CONFIG_CGROUP_FREEZER=y`.

Missing container flags were never the cause of the boot failure. Separately, the
image actually flashed was the **KernelSU stock-config** build, not the
Droidspaces container build, so container flags were never the variable under test.

## Device-tree deltas — a real, previously untested difference

Stock `dtb.payload` is `401,068` bytes and contains **one** FDT blob of 401,068
bytes. BoostKernel2's `dtb` is `340,965` bytes, one FDT blob, entirely different
content. Our fixed-slot transplant preserved the stock DTB byte-for-byte.

`dtbo` is more informative:

| | Stock `dtbo.img` | BoostKernel2 `dtbo` |
| --- | --- | --- |
| File size | 8,388,608 (padded; content ends at 1,230,549) | 1,229,985 |
| Overlay entries | **5** | **4** |
| Page size | 4096 | 4096 |

Per-overlay SHA-256 (first 16 hex) shows 3 of 5 stock overlays reproduced
byte-identically, one stock 294-byte stub dropped, and stock overlay
`31b928d0591df3d7` (307,159 bytes) replaced by BoostKernel2's `521654e0bd738d2a`
(306,921 bytes). So BoostKernel2 rebuilds the overlay set (its `build.sh` runs
`tools/mkdtimg create ... --page_size=4096` over
`arch/arm64/boot/dts/samsung/m23/m23xq/`) and **flashes it**: `write_boot()` in
`ak3-core.sh` calls `flash_generic dtbo` unconditionally.

Our attempt never wrote `dtbo`. Whether the stock 5-entry dtbo is compatible with
a rebuilt kernel is untested.

## Installer semantics — read from this package's own `ak3-core.sh`

`anykernel.sh` (this package):

```sh
device.name1..5=m23xq        do.devicecheck=1
do.modules=0                 do.systemless=1
BLOCK=/dev/block/bootdevice/by-name/boot;
IS_SLOT_DEVICE=0;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;
dump_boot; ... write_boot;
```

Confirmations and corrections:

- `PATCH_VBMETA_FLAG=auto` resolves in `ak3-core.sh` to `PATCHVBMETAFLAG=false`.
  The installer therefore does **not** patch the boot image's embedded vbmeta
  flags. VBMETA disabling is handled entirely by the separate Odin
  `vbmeta_disabled.tar` write. Brave's framing of repack as the AVB fix is wrong.
- `do.modules=0` and the empty `modules/` directory: no vendor module replacement
  is attempted. The stock ramdisk contains **no** `.ko` files at all
  (`ramdisk-unpacked/` holds only `init`, `fstab.default`, `dpolicy`, and mount
  points), so first-stage init does not depend on modules. Our seven rebuilt
  modules are not on the first-stage path.
- The `anykernel.sh` still carries the **unmodified AnyKernel3 template**
  `init.tuna.rc` / `fstab.tuna` / `omap_hsmmc` example patches. Those files do not
  exist on m23xq, so `backup_file` / `insert_line` / `patch_fstab` are no-ops.
  The installer performs **no** real ramdisk modification. It is a kernel+dtb+dtbo
  swap with the stock ramdisk repacked unchanged.
- `write_boot()` = `repack_ramdisk; flash_boot; flash_generic vendor_boot;
  flash_generic vendor_kernel_boot; flash_generic vendor_dlkm;
  flash_generic system_dlkm; flash_generic dtbo;`. On this A-only device only
  `boot` and `dtbo` exist, so effectively boot + dtbo.
- In `flash_boot`, the KernelSU branch is gated on `-d /data/data/me.weishu.kernelsu`
  and only sets up a helper module; it is not required for the kernel swap.

## Build provenance — BoostKernel2 is not compiler-authentic to this firmware

`build.sh` / `build_kernel.sh` in the tree:

```sh
CLANG="${HOME}/linux-x86-main/clang-r563880/bin"   # build.sh
CLANG="${HOME}/linux-x86-main/clang-r487747c/bin"  # build_kernel.sh
make O=out ARCH=arm64 CC=clang LLVM_IAS=1 LLVM=1 vendor/m23xq_eur_open_defconfig
tools/mkdtimg create out/arch/arm64/boot/dtbo.img --page_size=4096 <m23xq dtbos>
```

AOSP prebuilt clang, LLVM_IAS, LLD — not Qualcomm SD LLVM 10.0.7 and not GNU ld,
both of which stock uses. So BoostKernel2 proves a custom kernel *can* boot this
device, but it proves nothing about whether a Qualcomm-10.0.7 / GNU-ld /
Samsung-integrity-intact kernel boots.

## Our build vs the stock device kernel — the complete delta

`/proc/config.gz`-equivalent extracted from stock `kernel.payload`
(IKCFG at 26,785,992; SHA-256 `bdfa4a56e2fb310b336c9d613e613575d7d7df6e79cdb599087e0f96ac4c5ec9`)
diffed against `artifacts/kernelsu-stock-config-qcom-10.0.7/compile/.config` is
only 67 diff lines. The functional changes are:

- `CONFIG_FHANDLE` off → `y`
- `CONFIG_KPROBES` off → `y`, plus `KRETPROBES=y`, `KPROBE_EVENTS=y`
- `CONFIG_KSU=y` added
- `CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE` → `CONFIG_CC_OPTIMIZE_FOR_SIZE`
- Lost from our config: `CONFIG_PROCA_CERTIFICATES_XATTR`,
  `CONFIG_PROCA_CERT_ENG="x509_proca_eng.der"`,
  `CONFIG_PROCA_CERT_USER="x509_proca_user.der"`,
  `CONFIG_DISABLE_LOCKSCREEN_USB_RESTRICTION`, `CONFIG_SEC_AUTO_INPUT`,
  and the twelve `CONFIG_SEC_*_PROJECT` / `CONFIG_MACH_M23XQ_*` "is not set"
  variant lines (cosmetic — the selected variant `MACH_M23XQ_SWA_OPEN=y` matches
  stock).

`CONFIG_MACH_M23XQ_SWA_OPEN=y` matches the device. BoostKernel2 builds
`EUR_OPEN` instead and still boots on INS units, so the variant symbol is not
boot-critical.

The **PROCA certificate symbols disappearing from our config while `CONFIG_PROCA=y`
and `CONFIG_FIVE=y` remain enabled** is the most concerning single line in this
diff, and it is consistent with the previously recorded `0xecefecef` PROCA
fallback marker and the earlier `CONFIG_FIVE`/`CONFIG_PROCA` build-input mismatch.
An enabled PROCA/FIVE with missing certificate inputs is a plausible early-boot
integrity failure that BoostKernel2 sidesteps entirely by deleting the subsystem.

## Kernel release / vermagic

- Stock: `Linux version 4.19.152-perf-28692722-abE236BXXSEEZB1 (dpi@SWDM8415) (clang version 10.0.7 for Android NDK, GNU ld (binutils-2.27-bd24d23f) 2.27.0.20170315) #1 SMP PREEMPT Sat Feb 7 02:27:42 KST 2026`
- Ours: `4.19.152-perf`
- BoostKernel2: `4.19.325-Boostkernel 2 v10.4`

Both stock and our build set `CONFIG_LOCALVERSION="-perf"` with
`CONFIG_LOCALVERSION_AUTO` off, so the `-28692722-abE236BXXSEEZB1` suffix comes
from Samsung's build environment `LOCALVERSION=`, not the defconfig.

BoostKernel2 boots with a release string that shares *nothing* with stock beyond
`4.19`, and its modules would have a completely different vermagic. Since the
stock ramdisk carries no modules and first-stage init loads none, **release-string
and vermagic mismatch are demonstrably not fatal on this device.** That closes a
previously open lead: the short `4.19.152-perf` release is not the boot blocker.

## Claim-by-claim verdict on the Brave AI output

| Claim | Verdict |
| --- | --- |
| Kernel config mismatch / missing `NAMESPACES`, `CGROUPS`, `SECCOMP` | **FALSE.** Present in stock, present in our build, and BoostKernel2 enables fewer container flags than we do. |
| Stock container features "disabled or unloadable signed modules" | **FALSE.** They are built in, and no modules are on the first-stage path. |
| Repacking with `magiskboot` is *mandatory* for AVB reasons | **FALSE as stated.** `magiskboot repack` never recomputes the AVB payload digest and never re-signs; `PATCHVBMETAFLAG` writes `flags=3` without signing. Repack fixes header/checksum, DTB splitting and block layout — not cryptography. |
| Keep the stock ramdisk | **TRUE**, and already what we did. Confirmed by the empty `ramdisk/`/`patch/` dirs and the no-op template patches. |
| "Mismatched ramdisks cause the bootloop you saw" | **UNSUPPORTED.** Our transplant preserved the stock ramdisk byte-for-byte. |
| Flash a `.tar` to AP, never a raw `.img`; `vbmeta_disabled.tar` separately | Consistent with `PATCH_VBMETA_FLAG=auto` resolving to false. Already our practice. |
| BoostKernel2 "v8.5+", check `USER_NS`/`CGROUPS` with mrsiri | **Version wrong** (v10.3.5 archive / v10.4 binary / v11.9.3 tree). The config question is answered locally and needs no developer contact. |
| Source is `Aflaungos/android_kernel_samsung_m23xq` | **FALSE.** Repository does not exist. |
| A custom kernel with LXC support is mandatory | Unproven as the cause; our container build already has every prerequisite. |

The one genuinely load-bearing lead the Brave output pointed at — flash `dtbo`
alongside `boot` — it never actually stated. That came out of reading the package.

## New leads, ranked

1. **PROCA/FIVE enabled without certificate inputs.** Our config keeps
   `CONFIG_PROCA=y` / `CONFIG_FIVE=y` but lost all four
   `PROCA_CERT*` / `PROCA_CERTIFICATES_*` lines relative to stock. Highest-value
   off-device fix, and it is a config/build-input change, not a device test.
2. **`dtbo` never written.** BoostKernel2 rebuilds and flashes a 4-entry dtbo
   against stock's 5-entry one. Untested on our side.
3. **`CONFIG_CC_OPTIMIZE_FOR_SIZE`** diverges from stock and from BoostKernel2.
   Cheap to revert.
4. **Samsung uH/RKP/KDP retained in our build.** BoostKernel2 removes the whole
   hypervisor-assisted integrity stack. A KernelSU kernel that keeps RKP/KDP
   active is plausibly killed by them; `hyp.mbn` and `tz.mbn` are separate
   partitions we are not touching, so the hypervisor is live.

Items 1, 3 and 4 are all *config-level* and can be tested by rebuilding, not by
flashing. Item 2 needs a device write.

## Classification

- BoostKernel2 acquisition, hashing, extraction, and static audit: **PASS**.
- BoostKernel2 as proof that a custom kernel can boot unlocked SM-E236B: **PASS
  (third-party evidence, not reproduced here)**.
- Root cause of our boot failure: **NOT DETERMINED**.
- Any device write: **NOT PERFORMED, NOT AUTHORIZED BY THIS AUDIT**.
- BoostKernel2 kernel as a project artifact: **EXCLUDED** — wrong compiler, wrong
  kernel version, Samsung integrity stack deleted, unverifiable embedded config.

## Storage checkpoint

Extraction added roughly 44 MiB to the SSD lab volume. No Mac-internal writes
beyond `/tmp` scratch. No deletions performed.

## Second control package: BoostKernel2 v11.6.1

Acquired by the device owner after the v10.3.5 audit.

- Staged at `artifacts/control-boostkernel2-v11.6.1/Boostkernel2-v11.6.1.zip`.
- Size `22,092,266` bytes.
- SHA-256 `a80b4cfecbf73072c86305deac9e9a978ad3465643c1d342fa34dc99fe11f211`.
- 15 files, same three empty directories (`modules/system/lib/modules`, `patch`,
  `ramdisk`).

| Member | Size | SHA-256 |
| --- | --- | --- |
| `Image` | 39,933,968 | `f3d2f53f68e21ad41d494c96a8078fa790c90d221ae081ace5b70deac9dfac27` |
| `dtb` | 340,965 | `f4b47a37840f5e3c269e2b404aedc9dbf3fc084e5a189d1dd74f085eb9b858dd` |
| `dtbo` | 1,229,985 | `7ccafefa86c7d3bb360ec9631cb4a18c5fdad03dc2bb8c1287549a9a756472dc` |
| `anykernel.sh` | 3,495 | `b92a67e971857dd5a162515036f36bd691b9f8e8330985aae79f573b7dae59ff` |
| `tools/ak3-core.sh` | 34,023 | `0019d398688fe7b0a43ea82a55880dee85408e59b13471f410cd33a8f14ff774` |
| `tools/magiskboot` | 621,588 | `58abd6b6d468f5d1f2eba7cebd3c00643e9a834fc2d0a5d87c0a8ae4621db2ab` |

Kernel identity:

```
Linux version 4.19.325-Boostkernel 2 v11.6 (mrsiri@Mrsiri-PC)
  (Android (10087095, +pgo, +bolt, +lto, -mlgo, based on r487747c)
   clang version 17.0.2 (... d9f89f4d16663d5012e5c09495f3b30ece3d2362), LLD 17.0.2)
  #8 SMP PREEMPT Fri May 1 12:40:49 -03 2026
```

ARM64 header: `magic=ARMd`, `text_offset=0x80000`, `image_size=51,122,176`,
`flags=0xa` — same as v10.3.5 and same as stock apart from `image_size`.

Deltas versus v10.3.5, all of them narrow:

- `Image` differs (39,933,968 vs 39,817,232; +116,736 bytes). Still well inside
  the 51,138,576 fixed kernel slot, and still ~9.1 MB smaller than our
  49,041,424-byte KernelSU `Image`.
- `dtb` and `dtbo` are **byte-identical** to v10.3.5. mrsiri has not changed the
  device tree or overlays between February and May 2026, which makes the 4-entry
  dtbo a stable known-good reference rather than a per-release artefact.
- `tools/ak3-core.sh` is byte-identical, so all installer semantics recorded above
  hold unchanged: `PATCH_VBMETA_FLAG=auto` → `PATCHVBMETAFLAG=false`,
  `do.modules=0`, empty ramdisk/patch, `write_boot()` flashing boot + dtbo.
- `anykernel.sh` differs by exactly one line: the display string
  `BoostKernel for…` → `BoostKernel 2 for…`. All shell variables are unchanged.
- `/data/adb/ksud` marker present (KernelSU compiled in). No SUSFS strings, so
  this is the non-SUSFS line like v10.3.5.
- The IKCONFIG anomaly is **unchanged and therefore systematic**: the embedded
  config is again the stale 4.19.152 / clang-10.0.7 / `LOCALVERSION="-perf"` /
  no-`CONFIG_KSU` blob, SHA-256
  `74871c58d6716c062ce3d8451d07faf2d65d75a6146fd55f0ae5d0a329f41f74`, byte-identical
  to the v10.3.5 embedded config and to the tree's `stock_defconfig`.
  `/proc/config.gz` from any BoostKernel2 release is unusable as evidence.

Nothing in v11.6.1 changes a single conclusion or lead from the v10.3.5 audit. It
confirms them: the dtb/dtbo pair and the installer are stable across releases, and
the misleading embedded config is a persistent property of this build tree rather
than a one-off packaging slip.

Storage: extraction added roughly a further 44 MiB to the SSD lab volume.

