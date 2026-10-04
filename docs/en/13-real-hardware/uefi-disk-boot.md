---
id: uefi-disk-boot
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/storage.c
  - kernel/fs/part.c
  - kernel/metal/bootinfo.c
  - scripts/qemu.mk
  - tools/check_install_img.py
  - iso_root/boot/limine/limine.conf
symbols:
  - install_device
  - write_esp
  - write_gpt_backup
  - storage_init
depends_on:
  - installation-real-hardware
  - gpt-esp
  - uefi
  - limine
related:
  - hardware-profile
  - bringup-diagnostics
  - driver-compatibility
  - validation-evidence
---

# UEFI disk boot: from firmware to the installed ChrisOS system

## Scope

ChrisOS now has an end-to-end disk-installation gate that proves a disk produced by the in-kernel installer can boot without the installation ISO under QEMU with OVMF.

The validated chain is:

    blank target disk
        ↓ ChrisOS installer
    GPT + EFI System Partition + ChrisFS
        ↓
    OVMF UEFI firmware
        ↓
    EFI/BOOT/BOOTX64.EFI
        ↓
    Limine
        ↓
    /boot/kernel.elf
        ↓
    ChrisOS kernel
        ↓
    native storage discovery
        ↓
    ChrisFS root mount
        ↓
    desktop 60Hz

This is significant evidence because the second boot uses only the installed disk plus UEFI firmware.

It is not yet proof that every physical UEFI machine will discover and boot the same disk.

This chapter documents the exact current boot chain, the QEMU/OVMF evidence and the remaining firmware-compatibility boundaries.

## Current evidence

The authoritative integration target is:

    make test-qemu-install

The target first boots a source system with a blank AHCI target and requires installation markers.

It then runs:

    tools/check_install_img.py

against the target image.

Finally it launches a new QEMU instance with OVMF and the installed target as its only operating-system disk.

The second boot must emit:

    cfs mounted
    desktop 60Hz

That establishes a real disk-only UEFI boot gate in the current CI/tooling model.

## What the second boot excludes

The second QEMU invocation does not attach the ChrisOS ISO.

It provides:

- QEMU PC machine;
- OVMF code flash;
- copied OVMF variable flash;
- the installed target image as IDE disk;
- serial log output.

Therefore successful boot cannot be attributed to the ISO's El Torito or ISO-specific boot structures.

The installed disk itself contains the required boot chain.

## Installed disk layout

The installer writes:

    LBA 0             protective MBR
    LBA 1             primary GPT header
    LBA 2..33         primary GPT entries
    LBA 2048..        EFI System Partition
    after ESP         ChrisFS partition
    final sectors     backup GPT entries/header

The host-side checker validates both primary and backup GPT headers.

The boot path is therefore based on GPT, not an MBR bootstrap.

## No legacy BIOS boot code

The protective MBR exists only to identify the GPT disk to MBR-aware software.

The installer does not place a legacy BIOS bootloader in MBR boot code.

Therefore the installed disk should be classified as:

    x86-64 UEFI boot disk

not:

    BIOS + UEFI hybrid installed disk

The ISO remains a separate artifact with broader boot support.

## EFI System Partition

Partition one uses the standard EFI System Partition type GUID and begins at LBA 2048.

The installer creates the filesystem structures itself and writes the boot payload.

The relevant installed hierarchy is:

    EFI/
      BOOT/
        BOOTX64.EFI

    BOOT/
      KERNEL.ELF
      LIMINE/
        limine.conf

The EFI application is Limine's x86-64 UEFI binary.

## Why BOOTX64.EFI matters

UEFI defines an architecture-specific default boot filename for removable-media-style boot discovery.

For x86-64 the conventional path is:

    EFIBOOTBOOTX64.EFI

The current installer deliberately uses that fallback path.

This avoids requiring ChrisOS to create or modify firmware NVRAM Boot#### entries during installation.

## Fixed disks and fallback discovery

The fallback path is highly useful, but firmware behavior for non-removable media is more policy-dependent than the simple removable-media rule.

UEFI firmware can boot a fixed disk through explicit Boot#### device paths.

When no usable boot option exists, platform firmware may also search candidate filesystems using default boot behavior.

OVMF successfully discovers the current installed ChrisOS disk in the integration gate.

Physical firmware should not be assumed to behave identically.

A future production installer should consider registering an explicit UEFI boot option while preserving BOOTX64.EFI as recovery/fallback.

## No Boot#### installation

Current ChrisOS does not create:

- Boot####;
- BootOrder;
- BootNext.

The installer only writes disk contents.

This has advantages:

- no dependency on UEFI Runtime Services after ChrisOS boot;
- no firmware-variable permission problems;
- no stale NVRAM records;
- simpler test images.

The trade-off is weaker boot discovery on firmware that does not scan the fixed-disk fallback path under current platform policy.

## BOOTX64.EFI is not the kernel

BOOTX64.EFI is a UEFI executable.

The ChrisOS kernel is still an ELF image.

The firmware does not directly load KERNEL.ELF as an EFI application.

The stages are:

    firmware
        ↓ loads PE32+ EFI executable
    BOOTX64.EFI / Limine
        ↓ interprets Limine configuration
    KERNEL.ELF
        ↓ loaded under Limine protocol
    ChrisOS kstart

This distinction is important for debugging.

A failure before Limine output is different from a failure after the kernel ELF is loaded.

## Limine configuration

The installed configuration currently contains:

    /ChrisOS
        protocol: limine
        path: boot():/boot/kernel.elf
        resolution: 1920x1080x32

Limine remains the bootloader and implements the firmware-to-kernel handoff.

ChrisOS currently depends on Limine-provided boot information rather than implementing a UEFI loader directly.

## Meaning of boot()

The configuration asks Limine to resolve the kernel on the boot volume visible to the bootloader.

The installer therefore must ensure that BOOTX64.EFI, the Limine configuration and kernel payload form one internally consistent boot filesystem.

The host checker verifies the presence of the relevant directory entries.

It does not yet cryptographically verify that every installed file matches the intended source bytes.

## ESP filesystem implementation

The current ESP writer creates a FAT16-style filesystem.

Source evidence includes:

- uint16_t FAT entries;
- fixed root-directory region;
- FAT16 filesystem label;
- FAT16 cluster-chain encoding.

This is important because project documentation and the ideal physical-hardware target often refer to a FAT32 ESP.

The current disk-only OVMF gate proves that OVMF accepts the generated image.

It does not prove equivalent acceptance by all physical UEFI firmware.

## FAT16 compatibility boundary

The correct current claim is:

    FAT16-style ESP + BOOTX64.EFI:
    validated under current OVMF gate

not:

    universally validated physical UEFI ESP

A high-value compatibility improvement is to replace the hand-written FAT16 ESP with a standards-oriented FAT32 ESP implementation and rerun both QEMU and physical gates.

## Firmware stage

On the second integration boot, OVMF acts as UEFI firmware.

Conceptually firmware must:

1. initialize the platform;
2. discover the disk/controller;
3. parse the GPT/partition environment;
4. expose the ESP through firmware storage/filesystem protocols;
5. locate a bootable EFI image according to boot policy;
6. authenticate it if Secure Boot policy requires authentication;
7. load and start the EFI image.

ChrisOS itself does not execute during these steps.

## Limine stage

After BOOTX64.EFI starts, Limine owns the loader stage.

It is responsible for tasks including:

- locating configuration;
- locating KERNEL.ELF;
- loading the ELF image;
- establishing the kernel execution environment;
- obtaining firmware/platform information;
- preparing framebuffer information;
- producing Limine boot-protocol responses;
- transferring control to the ChrisOS kernel.

The kernel starts after these loader responsibilities.

## ExitBootServices boundary

The current ChrisOS kernel does not call UEFI Boot Services.

Limine owns the firmware handoff, including the transition away from Boot Services.

Therefore the kernel cannot diagnose an earlier ExitBootServices failure through ordinary ChrisOS logs unless the bootloader exposes such failure before kernel entry.

This creates a diagnostic boundary:

    no kernel serial output
        may mean firmware/bootloader failure

whereas:

    kstart output begins
        proves firmware + loader reached kernel entry

## Kernel stage

After Limine transfers control, ChrisOS consumes the boot protocol through its boot information layer.

The kernel then initializes its own:

- memory management;
- interrupts;
- storage drivers;
- filesystem layer;
- graphics/desktop path;
- other kernel subsystems.

UEFI block services are no longer the normal storage mechanism.

## Firmware storage versus native storage

The same physical disk can be accessed by two entirely different software stacks during one boot:

    before kernel:
        UEFI firmware storage/filesystem driver

    after kernel:
        ChrisOS ATA/AHCI/NVMe/VirtIO/USB driver

This means a disk can be readable enough for firmware to start Limine but later fail when ChrisOS tries to mount its native root.

The reverse is also possible in development environments.

Boot success therefore requires compatibility at both stages.

## Root filesystem transition

The installed disk contains a ChrisFS partition after the ESP.

After kernel entry, ChrisOS native storage discovery must locate the block device and its partition.

The storage/partition layer then identifies and mounts ChrisFS.

The QEMU gate requires:

    cfs mounted

This marker proves the boot proceeded beyond firmware and Limine into native ChrisOS disk access.

## Why cfs mounted is strong evidence

If only BOOTX64.EFI and KERNEL.ELF worked, the kernel could start but still fail to use the installed system.

Requiring ChrisFS mount demonstrates more:

- native controller path works;
- partition discovery works;
- ChrisFS superblock is readable;
- root filesystem is accepted.

The later desktop marker demonstrates additional higher-level progress.

## Controller asymmetry in the current gate

The installation phase writes the target through the AHCI path:

    -device ich9-ahci
    -device ide-hd,drive=target,bus=ahci.0

The second disk-only boot attaches the installed image using QEMU's IDE disk path.

Therefore the current gate proves:

- installation through ChrisOS AHCI target handling;
- subsequent UEFI boot from the produced disk;
- subsequent ChrisOS root boot under the controller configuration used in the second launch.

It should not be summarized as one identical controller path across both phases.

## Host-side disk checker

Before the second boot, tools/check_install_img.py verifies structural conditions including:

- protective MBR;
- primary GPT signature and CRC;
- backup GPT signature and CRC;
- ChrisFS partition type GUID;
- ChrisFS superblock at declared partition start;
- BOOTX64.EFI directory entry;
- KERNEL.ELF entry;
- limine.conf long filename.

This catches many formatter bugs before firmware execution.

## What the checker does not establish

The checker does not currently prove:

- exact byte-for-byte BOOTX64.EFI source identity;
- cryptographic hash of KERNEL.ELF;
- complete FAT filesystem consistency;
- every GPT entry-array CRC relation beyond the checked fields;
- FAT32 conformance;
- Secure Boot signature validity;
- firmware portability.

The second boot supplies behavioral evidence beyond the static checker.

## OVMF variable store

The test copies:

    /usr/share/OVMF/OVMF_VARS_4M.fd

to a writable build-local variable image.

This gives the QEMU UEFI firmware a writable NVRAM variable store without modifying the system template.

The disk installation itself does not depend on a pre-created ChrisOS Boot#### entry in that variable store.

## Secure Boot

The current gate does not establish Secure Boot.

There is no ChrisOS signing/enrollment workflow in this path.

Therefore a physical system with Secure Boot enforcing trust policy may reject BOOTX64.EFI.

The safe compatibility claim remains:

    UEFI boot validated without an established Secure Boot chain

Physical bring-up should explicitly record Secure Boot state.

## Graphics dependency

The Limine configuration requests:

    1920x1080x32

ChrisOS boot code expects a usable 32-bpp framebuffer.

Physical firmware may choose or expose different modes.

The installed-disk boot chain therefore depends not only on storage discovery but also on successful graphics handoff.

A future hardware profile should record:

- framebuffer width/height;
- pitch;
- pixel layout;
- firmware mode selected.

## Device-path variability

Real UEFI firmware can identify boot devices through complex device paths including:

- PCI;
- SATA;
- NVMe;
- USB;
- partition nodes;
- vendor-specific path components.

Because current installation does not create an explicit Boot#### entry, ChrisOS avoids having to synthesize such a device path.

If explicit NVRAM registration is later added, robust device-path construction becomes part of the installer.

## Removable USB installation

The presence of BOOTX64.EFI makes the current layout conceptually compatible with x86-64 fallback boot behavior on removable media.

However, installing to USB still depends on:

- the ChrisOS USB mass-storage write path;
- generated ESP compatibility;
- firmware USB boot policy;
- kernel USB driver compatibility after entry.

One successful AHCI/QEMU image is not proof of USB physical installation.

## Cold boot requirement

A real physical validation should be performed from power-on or a clean firmware reset, not only warm reboot after installation.

Cold boot proves that no transient firmware state or previous boot option accidentally enabled success.

The install medium should also be removed for the installed-disk boot test.

## Boot order

On real hardware, firmware boot order can select another disk before ChrisOS.

A support procedure should distinguish:

    disk is bootable
    versus
    firmware selected the disk

Failure to boot automatically does not always mean the ESP is invalid.

The firmware boot manager may simply prefer another Boot#### entry.

## Recovery fallback

Keeping:

    EFI/BOOT/BOOTX64.EFI

is valuable even after future explicit Boot#### registration.

If firmware variables are reset or the boot entry is lost, the fallback file provides a possible recovery path.

The installer should therefore retain fallback and explicit registration as complementary mechanisms.

## Failure classification

UEFI disk boot failures should be classified by stage.

### No EFI loader reached

Symptoms:

- no Limine UI/log;
- no ChrisOS serial.

Likely domains:

- firmware storage discovery;
- GPT/ESP;
- FAT compatibility;
- Boot####/fallback policy;
- Secure Boot;
- invalid BOOTX64.EFI.

### Limine reached, kernel not reached

Likely domains:

- limine.conf;
- KERNEL.ELF location;
- ELF loading;
- framebuffer request;
- bootloader protocol setup.

### Kernel reached, no ChrisFS mount

Likely domains:

- native storage driver;
- partition discovery;
- ChrisFS;
- controller topology.

### ChrisFS mounted, no desktop

Likely domains:

- later kernel/graphics/input/application initialization.

This staged model is more useful than treating every failure as "UEFI did not boot."

## Physical validation record

A real-machine UEFI disk-boot record should capture:

- system/motherboard model;
- firmware vendor/version;
- UEFI mode;
- CSM state;
- Secure Boot state;
- disk/controller model and PCI identity;
- ESP start/size/filesystem type;
- whether Boot#### was present;
- firmware-selected boot path;
- first visible Limine stage;
- first ChrisOS serial marker;
- framebuffer properties;
- native root-controller detection;
- ChrisFS mount marker;
- desktop marker;
- cold reboot result.

This turns anecdotal success into reusable compatibility evidence.

## Improvements needed before broad hardware claims

The highest-value next improvements are:

1. implement a FAT32 ESP intended for physical UEFI compatibility;
2. verify installed boot-file hashes after writing;
3. optionally create a UEFI Boot#### entry while retaining fallback;
4. add explicit firmware-stage diagnostics where possible;
5. define a physical boot evidence format;
6. test SATA/AHCI, NVMe and USB boot separately;
7. test Secure Boot only after a real signing chain exists;
8. test multiple firmware vendors;
9. remove unsafe pre-install writes to unapproved disks;
10. publish controller/firmware compatibility results rather than a binary "real hardware supported" claim.

## Current evidence classification

At the reviewed revision:

    installer creates GPT + ESP + ChrisFS        implemented
    BOOTX64.EFI fallback loader                 implemented
    Limine configuration/kernel payload         implemented
    static installed-image checker              implemented
    disk-only UEFI boot                         QEMU + OVMF validated
    native ChrisFS mount after disk boot         QEMU validated
    physical UEFI firmware compatibility        not established
    explicit Boot#### registration              not implemented
    Secure Boot chain                           not implemented
    broadly conforming FAT32 hard-disk ESP       not implemented

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisOS has a meaningful UEFI disk-boot milestone: its in-kernel installer creates a GPT disk containing BOOTX64.EFI, Limine configuration, kernel payload and ChrisFS; the resulting image passes structural checks and boots without the ISO under OVMF until ChrisFS mount and desktop startup. The remaining gap is portability from that controlled OVMF environment to diverse physical firmware, especially because the current ESP writer is FAT16-style, no Boot#### entry is created and no Secure Boot chain is established.
