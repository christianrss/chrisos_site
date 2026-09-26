---
id: installation-real-hardware
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/install.c
  - kernel/fs/part.c
  - docs/INSTALLATION.md
  - docs/HARDWARE_BRINGUP.md
  - docs/HARDWARE_COMPATIBILITY.md
  - docs/REAL_HARDWARE_PLAN.md
symbols: []
depends_on:
  - block-storage
  - power-on-kstart
related:
  - validation-evidence
---

# Installation and physical hardware

## Installation is a destructive storage operation

An installer writes structures that firmware, partition parsers, filesystems and bootloaders will later consume. A wrong disk selection or off-by-one LBA is not a cosmetic defect.

Safe installer architecture separates:

- target selection;
- partition-layout calculation;
- filesystem formatting;
- EFI system partition population;
- kernel/boot configuration copy;
- verification;
- reboot/rollback policy.

## GPT

GUID Partition Table stores a primary header/table and backup structures near the end of disk. Correct installation must calculate usable ranges, checksums and backup locations from actual device geometry.

A disk image that works at one fixed size does not prove geometry for arbitrary physical drives.

## EFI system partition

UEFI firmware reads a FAT-based EFI system partition and searches standard boot paths such as `/EFI/BOOT/BOOTX64.EFI` for removable/default boot.

The ESP is separate from ChrisFS. The bootloader can live in the ESP while the operating-system workspace uses ChrisFS elsewhere.

## Bootloader and kernel

Limine remains an external bootloader in the current architecture. Installation must place compatible Limine/EFI data and the kernel image where the boot configuration expects them.

Self-hosting the kernel does not require replacing UEFI or Limine.

## QEMU versus hardware

Virtual machines control many variables: virtual chipset, predictable firmware, device models and timing. Physical systems introduce variation in ACPI tables, USB controllers, NVMe implementations, firmware behavior, interrupt routing and display setup.

Therefore evidence is classified separately:

| Class | Meaning |
|---|---|
| host-tested | algorithm/tool executes on development host |
| QEMU-tested | behavior observed under declared virtual machine |
| hardware-tested | observed on identified physical hardware/profile |

## Hardware profile

A credible first physical-hardware target should define exact assumptions: x86-64/UEFI, storage controller class, input devices, framebuffer/GOP behavior and fallback paths.

"Runs on my PC" is useful evidence but not a support specification unless the machine and relevant device identities are recorded.

## Safe mode and diagnostics

Real hardware bring-up needs serial or other early diagnostics and ways to disable optional subsystems. A failure in AC97, networking or one GPU path should not necessarily prevent testing storage and boot.

Boot flags and safe-mode paths reduce the number of variables in a failing configuration.

## Destructive-test discipline

Installation to physical media should use explicit target confirmation, capacity/model/serial display where available and ideally dry-run/plan output before writes.

Automated tests should prefer disposable images and virtual disks until the geometry and write sequence are validated.
