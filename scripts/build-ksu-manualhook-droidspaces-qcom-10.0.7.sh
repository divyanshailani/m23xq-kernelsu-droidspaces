#!/bin/bash
# Build a KernelSU kernel for SM-E236B / m23xq using rsuntk's build-time (manual)
# call-site hooks instead of runtime kprobes, plus the Droidspaces prerequisites.
#
# Why this shape:
#  * Step C proved the earlier failure was KernelSU's runtime kprobe colliding with
#    Samsung RKP write-protecting kernel text (BRK #0x4 at __arm64_sys_faccessat+0x0,
#    ESR 0x8600000f / IABT). The manual-hook design has zero kprobe references, so
#    CONFIG_KPROBES stays off exactly as Samsung ships it.
#  * UH and RKP stay ON. The kprobe was the only thing that fought RKP, and SELinux
#    already writes security_hook_heads (which lives in .rodata) from a security_initcall
#    on stock, long before mark_readonly() and rkp_deferred_init(). KernelSU registers
#    from a device_initcall in the same window.
#  * KDP is turned OFF while UH/RKP stay on. This is a legal Kconfig combination:
#    RKP only 'depends on UH', and nothing selects KDP implicitly. KDP_CRED is
#    structurally incompatible with any root solution on this kernel -- commit_creds()
#    routes every cred through the hypervisor's prepare_ro_creds(), execve() demotes
#    root callers to uid 2000 via kdp_restrict_fork(), and every LSM dispatch calls
#    security_integrity_current() which panics on a cred it did not mint.
#  * CONFIG_HDM 'depends on UH' in security/hdm/Kconfig, so keeping UH on keeps HDM,
#    closing the unintended eighth delta from the previous attempt.
#  * Board stays MACH_M23XQ_SWA_OPEN. BoostKernel2 targets EUR_OPEN and its zip carries
#    European DTBO overlays; our device is the Indian swa_open board.
#
# Off-device evidence only; this script never writes to the phone.
set -euo pipefail

LAB="${LAB:-$(pwd)}"
SRC="${SRC_TREE:-$LAB/sources/ksu-rsuntk-manualhook/kernel-source}"
KSU_SRC="${KSU_SRC:-$LAB/sources/ksu-rsuntk-manualhook/ksu-src}"
STOCK_BOOT="${STOCK_BOOT:-$LAB/artifacts/stock-firmware/boot.img}"
OUT_ROOT="${OUT_ROOT:?OUT_ROOT required}"
TAG="${TAG:?TAG required}"
JOBS="${JOBS:-8}"
QCOM_CLANG_DIR=$LAB/toolchains/snapdragon-llvm-10.0.7/sdllvm_arm-10.0.7-install
GCC_DIR=$LAB/toolchains/extracted
SRCVOL="${TAG}-src"
OUTVOL="${TAG}-out"
TCVOL="${TAG}-tc"
export DOCKER_HOST="${DOCKER_HOST:-unix://${HOME}/.orbstack/run/docker.sock}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# The Droidspaces prerequisites, from research/droidspaces-requirements-matrix.md.
# Verified absent from Samsung stock, BoostKernel2's real defconfig, and the
# LineageOS m23xq defconfig alike -- no prebuilt kernel supplies any of them.
DROIDSPACES_ON=(
  SYSVIPC SYSVIPC_SYSCTL SYSVIPC_COMPAT
  POSIX_MQUEUE POSIX_MQUEUE_SYSCTL
  PID_NS IPC_NS USER_NS
  CGROUP_DEVICE CGROUP_PIDS CGROUP_NET_PRIO
  FHANDLE AUTOFS_FS AUTOFS4_FS
  CRYPTO_USER_API CRYPTO_USER_API_HASH
  DEVTMPFS
  BRIDGE_NETFILTER NF_TABLES NETFILTER_XT_MATCH_ADDRTYPE
)
# Removing Android's AID-based socket gate is required by the upstream non-GKI
# guide and is a deliberate host-wide security tradeoff, recorded as such.
DROIDSPACES_OFF=( ANDROID_PARANOID_NETWORK )

# KDP family: disabled while UH/RKP stay enabled.
KDP_OFF=( KDP KDP_CRED KDP_NS RUSTUH_KDP )

# --- preflight: the patched tree must actually carry the five call sites -------
for f in fs/open.c fs/stat.c fs/exec.c fs/read_write.c drivers/input/input.c; do
  grep -q 'CONFIG_KSU' "$SRC/$f" || { echo "missing manual hook in $f"; exit 90; }
done
grep -q 'obj-$(CONFIG_KSU) += kernelsu/' "$SRC/drivers/Makefile" || { echo "drivers/Makefile not wired"; exit 90; }
grep -q 'source "drivers/kernelsu/Kconfig"' "$SRC/drivers/Kconfig" || { echo "drivers/Kconfig not wired"; exit 90; }
grep -q '^config KSU_MANUAL_HOOK$' "$SRC/drivers/kernelsu/Kconfig" || { echo "KSU_MANUAL_HOOK absent from KernelSU Kconfig"; exit 90; }
[ "$(grep -rc kprobe "$SRC/drivers/kernelsu/" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')" = 0 ] \
  || { echo "KernelSU still references kprobes"; exit 90; }

# --- authoritative config: the shipping kernel's own embedded .config ----------
python3 - "$STOCK_BOOT" "$TMP/stock-kernel" <<'PY'
import sys
from pathlib import Path
boot = Path(sys.argv[1]).read_bytes()
if len(boot) != 100663296 or boot[:8] != b"ANDROID!":
    raise SystemExit("unexpected stock boot image")
size = int.from_bytes(boot[8:12], "little")
if size != 51138576:
    raise SystemExit(f"unexpected stock kernel slot: {size}")
Path(sys.argv[2]).write_bytes(boot[4096:4096 + size])
PY
LC_ALL=C "$SRC/scripts/extract-ikconfig" "$TMP/stock-kernel" > "$TMP/stock.config"
for want in CONFIG_UH=y CONFIG_RKP=y CONFIG_KDP=y CONFIG_HDM=y CONFIG_PROCA=y CONFIG_FIVE=y \
            CONFIG_MACH_M23XQ_SWA_OPEN=y CONFIG_SECURITY_DEFEX=y; do
  grep -q "^${want}\$" "$TMP/stock.config" || { echo "stock config lacks $want"; exit 89; }
done
grep -q '^# CONFIG_KPROBES is not set$' "$TMP/stock.config" || { echo "stock unexpectedly enables KPROBES"; exit 89; }
log "authoritative stock config: $(wc -l < "$TMP/stock.config") lines, sha256 $(shasum -a 256 "$TMP/stock.config" | cut -c1-16)"

# --- container volumes --------------------------------------------------------
if [ "${REUSE_VOLUMES:-0}" != 1 ]; then
  docker volume rm -f "$SRCVOL" "$OUTVOL" "$TCVOL" >/dev/null 2>&1 || true
fi
docker volume create "$SRCVOL" >/dev/null
docker volume create "$OUTVOL" >/dev/null
docker volume create "$TCVOL" >/dev/null
if [ "${REUSE_VOLUMES:-0}" != 1 ]; then
  log "streaming Qualcomm LLVM 10.0.7 into $TCVOL"
  tar -C "$QCOM_CLANG_DIR" -cf - . | docker run -i --rm --platform linux/amd64 -v "$TCVOL":/v ubuntu:18.04 bash -c 'mkdir -p /v/clang && tar -C /v/clang -xf -'
  tar -C "$GCC_DIR" --exclude='./clang+llvm-*' -cf - . | docker run -i --rm --platform linux/amd64 -v "$TCVOL":/v ubuntu:18.04 bash -c 'mkdir -p /v/gcc && tar -C /v/gcc -xf -'
fi

# The tree carries drivers/kernelsu as a relative symlink out to ../../ksu-src/...,
# so both halves must land side by side under /src for it to resolve in-container.
log "streaming patched Samsung source into $SRCVOL"
tar -C "$SRC" -cf - . | docker run -i --rm --platform linux/amd64 -v "$SRCVOL":/v ubuntu:18.04 bash -c 'mkdir -p /v/kernel-source && tar -C /v/kernel-source -xf -'
tar -C "$KSU_SRC" -cf - . | docker run -i --rm --platform linux/amd64 -v "$SRCVOL":/v ubuntu:18.04 bash -c 'mkdir -p /v/ksu-src && tar -C /v/ksu-src -xf -'
tar -C "$TMP" -cf - stock.config | docker run -i --rm --platform linux/amd64 -v "$OUTVOL":/out ubuntu:18.04 tar -C /out -xf -

log "building: manual-hook KernelSU + Droidspaces, UH/RKP on, KDP off"
set +e
docker run --rm --platform linux/amd64 \
  -v "$SRCVOL":/src \
  -v "$OUTVOL":/out \
  -v "$TCVOL":/tc:ro \
  -w /src/kernel-source \
  f23-kernel-builder:qcom-10.0.7 \
  bash -uo pipefail -c "
    test -f /src/kernel-source/drivers/kernelsu/Kconfig || { echo 'SYMLINK_BROKEN'; exit 88; }
    mv /out/stock.config /out/.config
    for s in ${DROIDSPACES_ON[*]} KSU KSU_MANUAL_HOOK KSU_FEATURE_ADBROOT; do
      sed -i \"/^# CONFIG_\${s} is not set\$/d;/^CONFIG_\${s}=/d\" /out/.config
      echo \"CONFIG_\${s}=y\" >> /out/.config
    done
    for s in ${DROIDSPACES_OFF[*]} ${KDP_OFF[*]}; do
      sed -i \"/^CONFIG_\${s}=/d\" /out/.config
      echo \"# CONFIG_\${s} is not set\" >> /out/.config
    done
    export ARCH=arm64 PROJECT_NAME=m23xq PATH=/tc/clang/bin:/tc/gcc/bin:\$PATH
    /tc/clang/bin/clang --version | grep -q 'Snapdragon LLVM ARM Compiler 10.0.7' || exit 97
    ARGS=( -C /src/kernel-source O=/out ARCH=arm64 CC=/tc/clang/bin/clang
      CROSS_COMPILE=/tc/gcc/bin/aarch64-linux-android-
      REAL_CC=/tc/clang/bin/clang CLANG_TRIPLE=aarch64-linux-gnu-
      CONFIG_SECTION_MISMATCH_WARN_ONLY=y DTC_EXT=/src/kernel-source/tools/dtc
      CONFIG_BUILD_ARM64_DT_OVERLAY=y KCONFIG_CONFIG=/out/.config --no-print-directory )
    make \"\${ARGS[@]}\" olddefconfig
    dc=\$?; echo DEFCONFIG_EXIT=\$dc
    [ \$dc -eq 0 ] || exit \$dc

    # Post-olddefconfig invariants. Kconfig drops symbols whose dependencies are
    # unmet rather than writing '# CONFIG_x is not set', so assert both directions.
    fail=0
    for s in KSU KSU_MANUAL_HOOK ${DROIDSPACES_ON[*]}; do
      grep -q \"^CONFIG_\${s}=y\$\" /out/.config || { echo \"MISSING:\$s\"; fail=1; }
    done
    for s in UH RKP HDM PROCA FIVE SECURITY_DEFEX SDP FSCRYPT_SDP MACH_M23XQ_SWA_OPEN \\
             SCSI_UFS_CRYPTO SCSI_UFS_CRYPTO_QTI FS_ENCRYPTION_INLINE_CRYPT DM_DEFAULT_KEY; do
      grep -q \"^CONFIG_\${s}=y\$\" /out/.config || { echo \"REGRESSED:\$s\"; fail=1; }
    done
    for s in KPROBES ${KDP_OFF[*]} ${DROIDSPACES_OFF[*]} MACH_M23XQ_EUR_OPEN; do
      if grep -q \"^CONFIG_\${s}=\" /out/.config; then echo \"STILL_SET:\$s\"; fail=1; fi
    done
    [ \$fail -eq 0 ] || exit 96
    grep -E '^(CONFIG_(KSU|UH|RKP|KDP|HDM|PROCA|FIVE|SYSVIPC|USER_NS|PID_NS|IPC_NS|DEVTMPFS|FHANDLE)|# CONFIG_(KPROBES|KDP|ANDROID_PARANOID_NETWORK))' /out/.config

    make -j$JOBS \"\${ARGS[@]}\"
    rc=\$?; echo COMPILE_EXIT=\$rc; exit \$rc
  "
BUILD_RC=$?
set -e
log "build rc=$BUILD_RC"

mkdir -p "$OUT_ROOT/compile"
docker run --rm --platform linux/amd64 -v "$OUTVOL":/out ubuntu:18.04 \
  bash -c 'cd /out && tar -cf - .config Makefile include/config/kernel.release \
      include/generated/compile.h System.map vmlinux arch/arm64/boot/Image \
      $(find arch/arm64/boot/dts -name "*.dtb" -o -name "*.dtbo" 2>/dev/null) \
      $(find . -name "*.ko" 2>/dev/null) 2>/dev/null' \
  | tar -C "$OUT_ROOT/compile" -xf - || log "artifact extraction incomplete"
exit "$BUILD_RC"
