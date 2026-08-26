# Droidspaces requirements matrix — SM-E236B / m23xq

Date: 2026-08-25
Scope: off-device evidence only
Phone state: locked, stock, untouched

## Decision

The Qualcomm LLVM 10.0.7 Droidspaces kernel contains the documented kernel prerequisites, but Droidspaces itself has not run on this device. Kernel evidence is **PASS**; Android root, SELinux, init, encryption, networking, and persistence behavior are **NOT TESTED**.

Native `init.rc` integration is excluded from the first experiment. It modifies `vendor`, adds SELinux CIL policy, and the upstream documentation explicitly warns that missing policy domains can bootloop the device. Any eventual first runtime test must use the less invasive userspace-daemon route, started manually, with a disposable rootfs, networking disabled, no hardware passthrough, and no auto-start.

Machine-readable evidence: `research/droidspaces-qcom-10.0.7-requirements-audit.json`.

## Kernel prerequisites

| Capability | Evidence | Status |
|---|---|---|
| System V IPC and POSIX queues | `CONFIG_SYSVIPC=y`, `CONFIG_POSIX_MQUEUE=y`; `msgget` and `mq_open` syscalls linked | PASS |
| PID, mount, UTS, IPC namespaces | namespace configs enabled; `clone`, `setns`, `unshare`, `pivot_root`, and `mount` linked | PASS |
| Network and user namespaces | `CONFIG_NET_NS=y`, `CONFIG_USER_NS=y` | PASS |
| Seccomp | `CONFIG_SECCOMP=y`, `CONFIG_SECCOMP_FILTER=y`; seccomp syscall linked | PASS |
| Core cgroups | cgroups, device, PIDs, memory, scheduler, freezer, and network-priority configs enabled | PASS |
| Device filesystem | `CONFIG_DEVTMPFS=y`; kernel auto-mount deliberately remains off because Android `ueventd` owns `/dev` | PASS |
| Filesystems/rootfs support | ext4, FUSE, OverlayFS, tmpfs xattrs/ACLs, loop devices enabled | PASS |
| systemd file handles | `CONFIG_FHANDLE=y`; both handle syscalls linked | PASS |
| systemd automount/hash API | `CONFIG_AUTOFS4_FS=y`, `CONFIG_CRYPTO_USER_API_HASH=y` | PASS |
| PTY support | `CONFIG_UNIX98_PTYS=y` | PASS |
| NAT prerequisites | VETH, bridge, netfilter, conntrack, NAT, MASQUERADE, TCPMSS, routing/multiple tables enabled | PASS at config level |
| Qualcomm compiler identity | resolved `CONFIG_CLANG_VERSION=100007`; Snapdragon LLVM ARM Compiler 10.0.7 build | PASS |
| Runtime requirements checker | `droidspaces check` has never run on this kernel/device | NOT TESTED |

## Intended userspace behavior

These are implementation requirements derived from the pinned Droidspaces source and documentation, not verified behavior on this phone.

| Area | Intended behavior | Current status |
|---|---|---|
| Installation | Static binaries stored under `/data/local/Droidspaces/bin` | NOT TESTED |
| Persistent data | Containers/configuration under `/data/local/Droidspaces` | NOT TESTED |
| Userspace daemon | App-togglable daemon started through a root userspace mechanism such as `post-fs-data`; avoids modifying `vendor` | NOT TESTED; preferred first route |
| Native daemon | Android init service plus vendor binary/symlink, autoboot script, file contexts, and CIL policy | BLOCKED for initial testing |
| Container lifecycle | New PID/mount/UTS/IPC/cgroup namespaces with an init process as PID 1 | NOT TESTED |
| Cgroups | Per-container hierarchy under `/sys/fs/cgroup/droidspaces/<name>` with legacy v1 handling on kernel 4.19 | NOT TESTED |
| Rootfs | Directory or ext4 loop-backed image; upstream recommends sparse image on Android/F2FS to reduce SELinux/keyring problems | NOT TESTED |
| Volatile mode | OverlayFS-backed ephemeral changes | NOT TESTED |
| Network modes | Host, none, NAT, and gateway modes | NOT TESTED |
| NAT implementation | VETH/bridge, forwarding, firewall/NAT rules, upstream-interface detection | NOT TESTED |
| systemd | Full init startup using proven kernel primitives | NOT TESTED |
| Shutdown/recovery | Container stop, stale PID cleanup, orphan scanning, metadata recovery | NOT TESTED |
| Persistence | Surviving Android app lifecycle and reboot | NOT TESTED |

## Android-specific gates

| Gate | Why it matters | Status |
|---|---|---|
| Root method | Droidspaces requires root; KernelSU symbols do not prove root works | NOT TESTED |
| KernelSU manager compatibility | Manager identity, allowlist, post-fs-data, and safe mode must match v0.9.5 kernel behavior | NOT TESTED |
| SELinux | Root domain, mount, network, cgroup, device, and file-context operations may be denied | NOT TESTED |
| FBE/keyring behavior | Android encryption and legacy-kernel keyrings can deadlock or break image-backed rootfs | NOT TESTED |
| Cgroup mount topology | Android 14 vendor configuration may not match generic Linux assumptions | NOT TESTED |
| Firewall coexistence | Android netd rules and Droidspaces NAT must not break host connectivity | NOT TESTED |
| Process lifetime | Userspace daemon behavior under LMK, battery restrictions, reboot, and crash | NOT TESTED |
| systemd boot | Modern distributions may exceed kernel 4.19 compatibility expectations | NOT TESTED |
| Thermal/battery behavior | Native workloads can sustain CPU and storage pressure | NOT TESTED |
| Hardware passthrough | Exposes host devices and substantially expands privilege | BLOCKED for initial testing |
| Native init integration | Requires vendor image and SELinux policy changes; upstream warns of bootloops | BLOCKED for initial testing |

## Security tradeoffs

### `CONFIG_ANDROID_PARANOID_NETWORK=n`

This is enabled by the patched kernel as required by the upstream non-GKI guide. It removes Android's kernel-level AID-based socket gate. Processes without the Android framework `INTERNET` permission can create ordinary network sockets; raw/admin operations still depend on capabilities, but the host security posture is weaker.

This affects the entire Android host, not just the container. It must remain an explicit go/no-go decision.

### Shared-kernel containers

Droidspaces is not a virtual machine. A root-controlled container shares the Android kernel, so a kernel exploit, exposed device, broad bind mount, privileged mode, or unsafe capability policy can compromise the host. Do not run untrusted agent-generated commands or third-party images as though they were sandboxed.

### Networking and privileged mode

The first container must use networking `none`, no shared storage, no device passthrough, no privileged mode, and a disposable rootfs. NAT comes only after host firewall and connectivity checks. Persistence and auto-start come last.

## Eventual staged runtime order

These stages are future device-side gates, not authorization to execute now:

1. KernelSU/root alone; no Droidspaces installation.
2. Manual `droidspaces check`; collect sanitized results only.
3. Manual userspace daemon; no auto-start.
4. One disposable Alpine-style rootfs; networking `none`; no bind mounts or hardware.
5. Stop/restart/shutdown tests and repeated phone reboots.
6. NAT mode with host connectivity/firewall verification.
7. A non-disposable container only after clean recovery behavior.
8. Userspace persistence only after sustained testing.
9. Native `init.rc`/vendor integration remains a separate, higher-risk project and is not part of the initial path.

At the first boot issue, SELinux denial storm, keyring/FBE problem, radio/network regression, thermal problem, or unexplained host behavior, stop and return to the stock recovery plan.
