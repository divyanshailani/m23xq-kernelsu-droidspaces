# Post-root hide stack (what works and what can't)

State of the device after rooting, as of 2026-08-26. This documents the layering that
hides root from **software-only** detection (most banking apps, generic anti-cheat) and
the hard limit that no stack can cross on this phone.

## Installed stack

| Layer | Version | Purpose |
|---|---|---|
| KernelSU | kernel 32473 (rsuntk manual-hook, in-kernel) | root; non-root apps get module mounts unmounted by default |
| KernelSU manager | v3.2.2-10-legacy (randomized package) | management UI; keep the random package name |
| ZygiskNext | 1.5.0 | Zygisk API on KernelSU (needed by the modules below) |
| Zygisk-Assistant | v2.1.4 | hides Zygisk + spoofs bootloader/verified-boot props |
| PlayIntegrityFork (PIF) | v17 | spoofs device fingerprint to GMS DroidGuard |
| TrickyStore | 1.4.1 (disabled) | key attestation spoofing; broken here, see below |

## The unlock-prop fix (important)

Zygisk-Assistant's late prop block (`{ until boot_completed; …; } &` inside
`service.sh`) is killed before it runs on this device, leaving the real unlock state
exposed: `ro.boot.flash.locked=0`, `ro.boot.vbmeta.device_state=unlocked`,
`ro.boot.verifiedbootstate=orange`. Any app could read these directly.

Fix: `/data/adb/service.d/10-integrity-props.sh` — a `setsid`-detached loop that waits
for boot then applies the spoofs via `ksud resetprop`:

```sh
#!/system/bin/sh
setsid sh -c '
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 1; done
sleep 2
R=/data/adb/ksud
$R resetprop -n ro.boot.flash.locked 1
$R resetprop -n ro.boot.vbmeta.device_state locked
$R resetprop -n ro.boot.verifiedbootstate green
$R resetprop -n vendor.boot.vbmeta.device_state locked
$R resetprop -n ro.boot.veritymode enforcing
$R resetprop -n sys.oem_unlock_allowed 0
$R resetprop -n ro.boot.warranty_bit 0
$R resetprop -n ro.vendor.warranty_bit 0
$R resetprop -n ro.vendor.boot.warranty_bit 0
' < /dev/null > /dev/null 2>&1 &
```

Props only affect processes started after they're set — cold-stop target apps
(`am force-stop <pkg>`), GMS, and `com.google.android.gms.unstable` before testing.

## ZygiskNext denylist semantics on KernelSU

- KernelSU's per-app "Unmount modules" switch **is** the ZygiskNext denylist.
- KernelSU's "Unmount modules by default" (on in our kernel) puts every non-root app on
  the denylist automatically.
- Zygisk-Assistant's required config: denylist populated (✓ via unmount-by-default),
  **Enforce denylist OFF** (`zygiskd enforce-denylist disabled`), so ZA itself stays
  injected into target processes to do the hiding.

## TrickyStore notes (why it's disabled)

- Its `service.sh` wrapper gives up permanently (`exit 1`) if the daemon crashes once
  during early boot — replace with an always-retry loop if you use it.
- On this device the daemon's injector self-test fails (`verify1 failed … unverified!`)
  and Samsung's TEE refuses attestation regardless (`sw_fuse_blown=1`,
  `swd_key_attest() = -21`). Since Strong integrity is unreachable here anyway (below),
  it's disabled to reduce the in-process footprint apps can detect.

## The hard wall: Play Integrity on Android 13+

Official documentation (developer.android.com, Integrity verdicts):

> `MEETS_DEVICE_INTEGRITY`: On Android 13 and higher, there is **hardware-backed proof
> that the device bootloader is locked** and the loaded Android OS is a certified device
> manufacturer image.

This device is genuinely unlocked with a custom boot image (the FBE ROT re-seal is the
same hardware signal), and the Knox eFuse is blown. Therefore:

- `deviceRecognitionVerdict` will always be `NO_INTEGRITY` on this phone.
- PIF fingerprint spoofing only ever fixed this on Android < 13 (the PlayIntegrityFork
  README says exactly this); don't chase newer fingerprints/modules for it.
- WhatsApp registration and Play-Integrity-gated games reject the device permanently.
- **Relocking is not an option**: stock BOOT no longer boots after the ROT re-seal, and
  relocking with a custom image installed bricks the device.

## What the stack DOES cover

Software-only root detection — apps scanning for `su` binaries, mount points, package
names, and system props. That is what most banking apps and generic anti-cheat use.
Test per app; expect anything routed through Google Play Integrity device verdict to
fail regardless.
