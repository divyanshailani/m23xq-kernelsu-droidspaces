# KernelSU custom BOOT failure diagnosis — SM-E236B / m23xq

Date: 2026-08-26
Scope: read-only off-device diagnosis after one controlled BOOT-only upload and exact stock recovery.

## Device outcome

- Structural KernelSU candidate upload: **PASS** (`BOOT upload successful`).
- Candidate reached Samsung unofficial-software warning: **PASS**.
- Candidate reached Android/ADB: **FAIL** within the bounded 120-second observation.
- Exact stock BOOT restore: **PASS**.
- Android Recovery factory data reset: **PASS**.
- Post-reset stock Android and two additional reboots: **PASS**.

## Candidate facts

The flashed candidate was:

- `artifacts/structural-only/boot-kernelsu-v0.9.5-qcom-10.0.7-sizeopt-NONFLASHABLE.img`
- 100,663,296 bytes.
- SHA-256 `07552930a56da2bbb4332a7ee5ef4b57ab48d66283639a8868672b7195c5b24c`.
- Stock header, ramdisk, DTB, Samsung trailer, embedded vbmeta, footer, and non-kernel padding preserved byte-for-byte.
- Raw Qualcomm KernelSU Image: 49,049,616 bytes; stock fixed kernel slot: 51,138,576 bytes; fixed-slot fit: **PASS**.
- Both stock and candidate use an uncompressed arm64 `Image` with `ARMd` magic and `text_offset=0x80000`.
- The copied AVB metadata was not regenerated. Pinned AOSP verification correctly reports the signed boot payload digest mismatch; the candidate was explicitly labelled structural-only/NONFLASHABLE.

## Samsung security-config finding

The exact stock kernel’s embedded config contains:

- `CONFIG_PROCA=y`.
- `CONFIG_PROCA_S_OS=y`.
- `CONFIG_FIVE=y`.

The rebuilt KernelSU image’s final `.config` contains:

- `# CONFIG_FIVE is not set`.
- No `CONFIG_PROCA=y`.

The published Samsung defconfig used for the earlier build itself says `CONFIG_FIVE=n` while requesting `CONFIG_PROCA=y`. In this source, `security/samsung/proca/Kconfig` declares `PROCA` as depending on `FIVE`, so `olddefconfig` necessarily drops PROCA when FIVE is disabled. The candidate therefore differs from the shipping kernel in Samsung’s integrity stack and has the ARM64 Image header’s `0xecefecef` PROCA fallback marker instead of stock’s real PROCA configuration offset.

This is a confirmed build-input mismatch, not yet a complete causal proof of the boot failure. It is sufficient to reject the earlier candidate as a valid reproduction of the shipping Samsung kernel.

## Storage checkpoint

At the corrected rebuild checkpoint:

- Mac internal system volume: approximately 12 GiB free.
- SSD lab volume: approximately 91 GiB free.
- Phone `/data`: approximately 105 GiB free.
- OrbStack/Docker reported approximately 3.3 GiB reclaimable build cache, but existing source/toolchain/output volumes were retained to avoid an unnecessary rebuild.

All new build artifacts remain on the SSD. No cache prune or broad deletion was performed.


No new phone write is authorized by this diagnosis. The phone remains on verified stable unlocked stock Android.
