# Droidspaces kernel build — SM-E236B (m23xq), official Samsung 4.19.152 source

Date: 2026-08-24
Status: **baseline and KernelSU v0.9.5 builds clean off-device. A structural boot image was rehearsed offline; it is AVB-invalid and was not flashed.**

## What was built

A copy of the official Samsung `SM-E236B_SWA_14_Opensource.zip` kernel tree with the two
Droidspaces non-GKI patches and 16 defconfig edits. The pristine official tree at
`sources/official_samsung/kernel-source` was never modified.

| | value |
|---|---|
| kernel release | `4.19.152-perf` |
| Image | `db84c4229f3f53335b09fc8a8fdb9b2a0dcca8876a62b0c29d72fa67b10b0ea8`, 51,030,032 bytes |
| vmlinux | `6c7e06d3de99e3f658029dd9915a8ddffb6c70b3ddece5f4402b70d3cd89676d` |
| System.map | `ac08cd15ce03c290b9bf1b30b7f814240dc8d87f68519ada5b4552b2faf2f67b` |
| defconfig | `0506f0b202f4519da6c899d6d8718b7fd7f3cec59d82275e3a69dd0189201c19` |
| resolved `.config` | `17c0942a7745272701006288b334ab9742b17ba4cef2e39f49aa61f01e5639a6` |
| compiler | upstream LLVM 10.0.0 (**not** Qualcomm Snapdragon LLVM 10.0.7) |
| DTB | `lagoon.dtb`, 401,068 bytes — **byte-identical to the stock boot image DTB** |
| modules | 7 `.ko`, none of which the device loads at runtime |

Full baseline symbol audit and hashes: `manifests/droidspaces-build.txt`.

KernelSU v0.9.5 integration and build evidence: `manifests/kernelsu-v0.9.5-build.txt`.
The pinned commit is `b766b98513b5a7eb33bc1c4a76b5702bf1288f07` (version 10200). It was
integrated into a separate copy of the patched tree using the legacy non-GKI kprobe path;
`CONFIG_KSU=y`, `CONFIG_KPROBES=y`, and `CONFIG_KPROBE_EVENTS=y` resolve successfully.
The resulting Image is `343a9d7f6379168eccddd6fd5ce3b78023ea54e7eab6738db3fb19406fa8aeb1`,
51,044,368 bytes.

The offline structural boot image is
`artifacts/kernelsu-v0.9.5-build/boot-kernelsu-structural.img`, SHA-256
`bef0f16198b6613e727979e1182024c36b9085ec75bd4d294e8ba1108667329c`. It preserves the
stock header page, ramdisk, DTB, Samsung trailer, embedded vbmeta, AVB footer, and all
post-DTB bytes; only the fixed kernel slot changes. The old embedded and external AVB boot
digests necessarily no longer match, so this is **structural-only and AVB-invalid**, not a
flashable image.

The stock rollback rehearsal passed offline: `research/rollback-rehearsal.json` records a
hash-verified copy of the untouched stock `boot.img` (`3abd7ea170aa7c53eff61d4ee87f60100709166ce6242353aae1e117b293c2be`,
100,663,296 bytes) and confirms that no adb, Odin, or Heimdall operation was invoked.

## The DTB match is the strongest provenance signal so far

`arch/arm64/boot/dts/vendor/qcom/lagoon.dtb` built from this source hashes to
`93612e8e1c49cff5660b733e5ff75e53dfca6511c79c00eee4d0355b5bb92d94`, which is exactly the
`dtb.payload` extracted from the stock `boot.img` of `E236BXXSEEZB1` — same 401,068 bytes.

The device tree portion of the running firmware therefore reproduces bit-for-bit from this
source archive. That does not prove the C sources match the shipped kernel (dtc output is
stable across many builds and Samsung ships no build ID in the archive), but it is
meaningful evidence the archive corresponds to this device and firmware line.

## Size budget

The `boot` partition is 96 MiB. Stock content is kernel 51,138,576 + ramdisk 724,446 +
DTB 401,068. The new kernel is 51,030,032 — 108,544 bytes *smaller* than stock — leaving
48,507,750 bytes of headroom. A repack has ample room, including for a larger ramdisk.

## Config changes: 16 edits, not 13

Edits 1–13 are the Droidspaces container requirements recorded earlier. During artifact
inspection three further symbols turned out to be off, all of which systemd requires:

| symbol | why | severity |
|---|---|---|
| `CONFIG_FHANDLE=y` | systemd hard-requires `name_to_handle_at`/`open_by_handle_at` and refuses to start without them | **blocker for systemd** |
| `CONFIG_AUTOFS4_FS=y` | systemd automount units; selects `AUTOFS_FS` in 4.19 | degraded without |
| `CONFIG_CRYPTO_USER_API_HASH=y` | AF_ALG hash sockets used by systemd and several container tools | recommended |

Samsung had disabled `FHANDLE` explicitly (it is `default y` upstream, gated behind
`EXPERT`). Verified in the rebuilt kernel: both fhandle syscalls are in `System.map`,
60 `autofs_*` symbols are linked, and 6 `algif_hash` symbols are present. OpenRC, runit,
and s6 would not have needed any of the three — this only matters because systemd is the
target init.

## Everything else Droidspaces needs was already on

Samsung's own defconfig already enables `BRIDGE`, `VETH`, `TUN`, `FUSE_FS`, `OVERLAY_FS`,
`NF_NAT` with `MASQUERADE`, `NF_CONNTRACK`, `IP_ADVANCED_ROUTER`, `IP_MULTIPLE_TABLES`,
every cgroup controller that matters (`CGROUP_FREEZER`, `CPUSETS`, `MEMCG`, `BLK_CGROUP`,
`CGROUP_SCHED`, `CGROUP_CPUACCT`, `CGROUP_BPF`), `EXT4_FS` with ACL and security xattrs,
`TMPFS_XATTR`, `SECCOMP_FILTER`, `BLK_DEV_LOOP`, `IKCONFIG_PROC` and `IKHEADERS`.

So `nat` and `gateway` networking modes are viable, not just `host`/`none`.

Deliberately left off: `CHECKPOINT_RESTORE`, `SQUASHFS`, `MACVLAN`, `VLAN_8021Q`, `VXLAN`,
`NET_CLS_CGROUP`, `CFS_BANDWIDTH`, `RT_GROUP_SCHED`, `CGROUP_PERF`, `DEBUG_FS`. None are
required; each would be a further deviation from stock for no current benefit.

`DEVTMPFS_MOUNT` stays off on purpose — Android's `ueventd` owns `/dev`, and letting the
kernel auto-mount devtmpfs there is the riskier combination.

## Security tradeoff that needs a decision: `ANDROID_PARANOID_NETWORK=n`

Droidspaces requires this, and it is the one edit with a real security cost on the host.

With `ANDROID_PARANOID_NETWORK=y` (stock), the kernel gates socket creation on Android
group IDs: `AID_INET` for `AF_INET`/`AF_INET6`, `AID_NET_RAW` for raw sockets,
`AID_NET_ADMIN` for `NET_ADMIN` capability checks. Apps that Android has not granted the
`INTERNET` permission cannot open a network socket at all — the block is in the kernel,
below any framework check.

Turning it off means **every process on the device can create sockets regardless of
Android permissions**, including raw sockets subject only to normal capability rules. The
framework's `INTERNET` permission becomes advisory rather than kernel-enforced. On a
personal device with a curated app set this is a considered tradeoff, not a silent one;
it is worth knowing before flashing, because it changes the host's security posture and not
just the container's.

## Vendor module ABI is not a blocker here

`CONFIG_MODULE_SIG_FORCE=y` and `CONFIG_MODVERSIONS=y` would normally mean stock vendor
`.ko` files cannot load against a rebuilt kernel, and our `vermagic` does differ
(`4.19.152-perf` vs stock `4.19.152-perf-28692722-abE236BXXSEEZB1`). But `/proc/modules`
on the running device is empty — zero modules loaded — so the six `.ko` files under
`/vendor/lib/modules/` are not in use in this configuration. `modules.load` and
`modules.dep` could not be read from adb shell (SELinux Enforcing) so their contents remain
unverified; the empty `/proc/modules` is the load-bearing evidence.

## Build infrastructure fix worth keeping

The first attempt at this build failed with hundreds of `Bad file descriptor` errors
reading `/src` — including `/src/scripts/Makefile.build` itself — and died at
`kernel/kheaders_data.tar.xz`. That was not a source defect: bind-mounting
an external SSD into the OrbStack VM over virtiofs is unreliable under `-j10` compile load
combined with `gen_kheaders.sh` tarring the whole `include/` tree.

`scripts/build-in-volume.sh` fixes it by streaming the tree in over stdin (macOS tar reads
the SSD natively) into a Docker volume, building entirely against container-local storage,
and streaming artifacts back out. Zero I/O errors across both runs since.

Note the container runs `--platform linux/amd64` under emulation on Apple Silicon, so
fork-heavy Kbuild shell loops are slow — a full build is roughly 20 minutes and even a
no-op tree traversal costs several minutes.

## What is explicitly not established

- **Not stock-equivalent.** The stock kernel was built with Qualcomm Snapdragon LLVM
  10.0.7 (`CONFIG_CLANG_VERSION=100007`); ours records `100000`. Byte-comparing our Image
  to `kernel.payload` is meaningless and was not attempted.
- **No build ID ties the archive to `E236BXXSEEZB1`.** `E236B` appears only in
  `android/abi_gki_aarch64.xml`; there is no `SEC_BUILD_OPTION`. Samsung's OSRC record for
  this package referenced `E236BXXU5DWL2`.
- **The structural image is not flashable.** It preserves the stock geometry but its embedded
  and external AVB boot digests are stale, and the stock private signing key is not present.
  No AVB repair, SELinux policy work, or device boot test has been performed.
- **The phone is untouched** — still locked, stock, warranty bit 0, `flash locked=1`.
- **KernelSU is integrated only in a disposable source copy.** The successful baseline build
  remains separate and unchanged.
- **The phone is untouched** — still locked, stock, warranty bit 0, `flash locked=1`.

## Remaining gates before anything touches the device

1. Obtain/review the authorized Qualcomm Snapdragon LLVM 10.0.7 toolchain if compiler
   equivalence is required; the current builds use upstream LLVM 10.0.0.
2. Decide the later AVB policy and signing route. The stock private signing key is absent,
   so the structural image cannot be made accepted by a locked stock boot chain as-is.
3. If proceeding after all recovery gates, separately review KernelSU manager/userspace
   packaging, SELinux policy, Samsung AVB behavior, and the exact Download Mode restore
   workflow. None has been tested on hardware.
4. Only then consider unlocking, which must be treated as a mandatory userdata wipe and as
   likely to trip Knox permanently.
