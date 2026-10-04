---
id: bringup-diagnostics
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/klog.c
  - kernel/metal/panic.c
  - kernel/metal/buildid.c
  - kernel/metal/bootinfo.c
  - kernel/metal/smp.c
  - kernel/metal/acpi.c
  - kernel/fs/storage.c
  - tools/qemu_gate.py
  - scripts/qemu.mk
symbols:
  - kstart
  - serial_init
  - klog_copy
  - panic
  - panic_exception
  - build_info_log
  - bootinfo_init
  - smp_init
  - storage_init
depends_on:
  - hardware-profile
  - validation-evidence
related:
  - driver-compatibility
  - qemu-gates
  - hardware-gates
  - fault-injection
---

# Bring-up diagnostics and failure localization

## Scope

Hardware bring-up is a problem of locating the first stage whose invariants stop being true.

ChrisOS already provides several useful mechanisms:

- COM1 serial initialization before most kernel subsystems;
- an in-memory circular kernel log;
- build, Git and kernel-hash identity;
- verbose Limine boot-information dumps;
- explicit subsystem progress markers;
- panic and exception records;
- CPU, CR3 and RSP identity on fatal failures;
- persistence of the early log into ChrisFS;
- QEMU gates judged by expected and fatal markers.

The diagnostic rule is:

    record the last confirmed invariant
    investigate the next transition

rather than treating every failed boot as one undifferentiated failure.

## Boot-stage timeline

The practical sequence is:

    firmware
      -> Limine
      -> kstart
      -> serial and build identity
      -> bootinfo
      -> GDT / IDT / syscall / PIC / PIT / PS2
      -> PMM / MM / heap / process state
      -> framebuffer
      -> APIC / SMP / jobs
      -> ACPI probe
      -> storage discovery
      -> filesystem / installer
      -> language/runtime
      -> audio
      -> desktop
      -> network

The last serial marker reached narrows the next subsystem to inspect.

## Stage 0: firmware and loader

If no ChrisOS serial byte appears, possible domains include:

- UEFI did not discover the disk;
- BOOTX64.EFI was not started;
- Secure Boot policy rejected the EFI image;
- Limine could not find configuration or kernel;
- loader handoff failed;
- the kernel entered but COM1 is not reachable under current assumptions.

No serial output therefore does not by itself prove the kernel was never entered.

Firmware/loader screen output or another early channel is needed to resolve that ambiguity.

## Stage 1: serial

kstart starts with:

    serial_init()

The driver configures COM1 at:

    0x3f8

and uses UART loopback by writing and reading:

    0xae

If the test fails, kstart disables interrupts and halts forever.

Current ChrisOS therefore has a hard early dependency on a legacy-compatible COM1 path.

This is both a diagnosability advantage on compatible machines and a physical-compatibility limitation on machines without that interface.

## Serial and klog

Every serial_putc first writes the character into klog.

If the serial UART is available, it then transmits to COM1.

Thus the in-memory kernel log mirrors serial-style output after klog initialization.

The ring is useful even when later serial capture is incomplete.

## Serial transmit stall

The transmit path busy-waits for the UART transmitter-ready bit and has no timeout.

A UART that passes initialization and later stops reporting ready can stall the kernel inside logging.

Consequently, a hang immediately after a marker is not proof that the next subsystem caused the hang.

The output path itself remains part of the failure surface.

## Build identity

After serial setup, kstart emits:

    ChrisOS selfhost=1

and build_info_log writes:

- Build ID;
- Git revision;
- date;
- compiler;
- kernel SHA-256.

Every hardware result should preserve this block.

A log without image identity cannot reliably be tied to source.

## Kernel hash

The linked image contains a CHRISOSHASH stamp populated with the linked kernel SHA-256.

Fatal panic output includes that hash.

This is stronger provenance than a manually maintained version string.

## Stage 2: bootinfo

bootinfo_init validates Limine responses.

It panics when any required object is absent:

- framebuffer;
- HHDM;
- memory map;
- MP response.

It also rejects an empty CPU topology and a non-32-bpp framebuffer.

Any boot that reaches later stages has therefore already proven a substantial loader contract.

## Bootinfo diagnostics

Successful initialization prints information such as:

    ChrisOS: bootinfo revision 3
    HHDM offset=...
    fb WIDTHxHEIGHT pitch=... bpp=... addr=...
    mmap[...] type=... base=... len=...
    usable_bytes=...
    memmap_entries=...
    cpu_count=...
    bsp_lapic_id=...

This should be captured as the first major hardware evidence block.

It records what the kernel actually received from the loader.

## Memory-map evidence

The detailed map helps identify:

- unexpected reserved holes;
- ACPI regions;
- framebuffer regions;
- bootloader-reclaimable regions;
- memory incorrectly marked usable.

The code also checks the LAPIC physical area against the reported memory map so MMIO is not accidentally treated as ordinary RAM.

## Stage 3: early architecture

After bootinfo, ChrisOS initializes:

- GDT;
- IDT;
- syscall layer;
- PIC;
- PIT.

PIT initialization at 60 Hz is mandatory.

A panic or loss of progress after bootinfo but before memory/device markers should focus investigation on this transition.

## Panic contract

panic prints:

    PANIC: MESSAGE

followed by:

- current CPU;
- CR3;
- RSP;
- Build ID;
- Git revision;
- kernel SHA-256.

panic_exception additionally prints:

- exception vector;
- error code;
- RIP;
- CR2.

This provides a compact revision-bound fatal record before source-level debugging exists.

## Interpreting CR2

CR2 is primarily meaningful for page faults.

For other exception vectors it may contain an older page-fault address.

Investigators must interpret CR2 together with the exception vector.

## Mapping RIP to source

The raw RIP must be resolved against the exact kernel image identified by the same panic record.

Resolving it against another build can produce a plausible but false diagnosis.

RIP and build identity are one evidence unit.

## Stage 4: PS/2

PS/2 initialization is nonfatal.

When it fails, ChrisOS prints:

    ChrisOS: PS/2 unavailable (keyboard/mouse disabled)

and continues.

This is degraded operation, not a failed platform boot.

Diagnostic tooling must distinguish optional-device absence from fatal stage failure.

## Stage 5: memory subsystems

The kernel initializes and self-tests PMM, virtual memory and heap.

QEMU fatal-marker policy includes corruption strings such as:

    PMM corruption
    heap corruption

Once memory corruption is detected, later storage or graphics symptoms should be treated as secondary until the memory failure is fixed.

## Stage 6: framebuffer

After memory setup, kstart initializes graphics from the boot framebuffer.

An incompatible framebuffer leads to a panic such as:

    PANIC: gfx_init recusou o framebuffer

A physical report should preserve:

- address;
- width;
- height;
- pitch;
- bpp.

Pitch is especially important because it need not equal width times four.

## Stage 7: optional virtual GPU

virtio_gpu_boot runs after framebuffer initialization.

The firmware framebuffer remains the base graphical path.

Absence of VirtIO GPU on physical hardware is therefore not a core boot failure.

## Stage 8: SMP

The SMP path emits either:

    cpu_online_count=N (BSP+AP)

or, when disabled:

    smp off

A system that reaches desktop only with nosmp or safe mode has already localized the problem substantially.

The BSP/core path works; the failure lies in SMP/APIC behavior or another feature disabled by safe mode.

## Partial AP startup

smp_init waits for APs up to a bounded spin count and then reports the observed online count.

A count below the expected topology is evidence of partial AP startup.

Both expected CPU topology and observed cpu_online_count belong in the hardware record.

## Safe-mode differential test

The safe flag disables:

- SMP;
- APIC;
- AC97;
- networking;
- JIT.

This makes safe mode a useful differential experiment.

If normal boot fails but safe boot succeeds, re-enable one feature category at a time rather than changing multiple variables simultaneously.

## Stage 9: ACPI probe

The current probe can print markers such as:

    acpi rsdp oem=...
    acpi xsdt
    acpi APIC
    acpi MCFG
    acpi FACP

or:

    acpi rsdp missing

The probe is diagnostic rather than a complete ACPI platform layer.

Missing RSDP is not itself a panic and should not automatically be blamed for a later failure.

## Stage 10: storage

storage_init crosses several hardware boundaries at once:

- PCI discovery;
- controller initialization;
- block-device I/O;
- device registration;
- partition discovery;
- root selection;
- ChrisFS validation.

This stage should be diagnosed in layers rather than summarized as disk failure.

## Root and filesystem markers

Root selection prints:

    root DEVICE

Successful filesystem setup later prints:

    cfs mounted

These prove different things.

A controller can work and a root can be selected while filesystem mount still fails.

## Storage failure classes

Useful categories are:

1. controller not discovered;
2. controller discovered but initialization failed;
3. block device registered but read/write failed;
4. no root candidate;
5. GPT/partition discovery failed;
6. ChrisFS superblock invalid or unreadable;
7. mount failed;
8. filesystem corrupted later.

These categories preserve causal information.

## Destructive-diagnostics boundary

Hardware diagnosis must not perform speculative writes on valuable disks.

Use disposable media, clones or a dedicated target.

The existing storage/install design contains write-sensitive paths, so read-only hardware discovery is a high-value future diagnostic mode.

## Persisted boot log

After ChrisFS is available, kstart copies klog into:

    SYS/BOOT.LOG

The circular log capacity is:

    8192 bytes

The kernel reports either:

    boot log SYS/BOOT.LOG

or:

    boot log write failed

This creates a useful post-boot artifact when external serial capture is unavailable.

## Ring behavior

klog retains the newest 8192 bytes.

Older text is overwritten after wraparound.

SYS/BOOT.LOG is therefore not guaranteed to contain the first boot byte on verbose runs.

External serial capture remains the preferred complete evidence source.

## Stage 11: runtime and JIT

After storage, the language/runtime pipeline is initialized.

The nojit flag lets bring-up separate JIT behavior from the rest of the kernel.

A system that mounts ChrisFS and then fails only when JIT is enabled has a substantially narrower investigation surface.

## Stage 12: audio

AC97 is optional.

The noac97 flag provides direct feature isolation.

Failure to initialize unsupported modern audio should not classify the machine as unable to boot.

## Stage 13: desktop

Later kstart enables interrupts, initializes the desktop and emits:

    ChrisOS: desktop 60Hz

This is the primary current whole-system success marker in several QEMU gates.

It proves substantial progress but not every optional device.

## Stage 14: network

Network initialization occurs after desktop setup.

Failure prints:

    ChrisOS: net unavailable

and execution continues.

Because the current network path is VirtIO-oriented, this message is expected on most physical machines and is not a core boot failure.

## Marker-based validation

tools/qemu_gate.py judges a boot by explicit evidence.

It:

- starts QEMU with a timeout;
- reads the serial log;
- rejects unexpected process exits;
- rejects known fatal markers;
- requires every expected positive marker.

A physical gate should follow the same principle.

Elapsed time alone is not success.

## Current fatal markers

The gate treats strings such as these as fatal:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

Physical automation should use an equivalent explicit fatal vocabulary.

## Positive markers by test scope

Examples:

    bootinfo:
        ChrisOS: bootinfo revision 3

    SMP:
        cpu_online_count=4

    storage:
        root ahci
        cfs mounted

    xHCI:
        xhci hid ready

    desktop:
        ChrisOS: desktop 60Hz

The expected marker must prove the subsystem being tested.

## Last-marker method

If a log ends after:

    cpu_online_count=4 (BSP+AP)

but before any storage marker, already confirmed stages include:

- kernel entry;
- serial;
- build identity;
- bootinfo;
- memory;
- framebuffer;
- SMP.

Investigation should begin at the ACPI/storage transition, not at UEFI or linking.

## Ordered markers

Markers are most useful when order is retained.

A future parser should treat boot as a state machine and associate each ordered marker set with one build identity.

This avoids mixing logs from separate reboots.

## Diagnostic session identity

A useful session key is:

    Git revision
    Build ID
    kernel SHA-256

Hardware databases should store this tuple with machine identity and boot flags.

## Missing fatal-state information

The current panic path does not yet emit:

- every GPR;
- RFLAGS;
- segment state;
- APIC state;
- stack trace;
- page-table walk for a page fault.

These are high-value future additions.

CR3, RSP, RIP and CR2 are useful, but difficult faults need more context.

## No stack unwinder

There is no general panic-time stack unwinder in the reviewed path.

A reliable unwinder would need exact symbols, safe memory reads and a stable unwind strategy.

Until then, revision-bound RIP and explicit stage markers are safer evidence.

## Structured hardware record

A future diagnostic artifact should contain:

    machine:
        vendor/model
        firmware/version

    build:
        git
        build_id
        kernel_sha256

    boot:
        command_line
        secure_boot_state

    bootinfo:
        framebuffer
        cpu_count
        memory_map_summary

    devices:
        pci ids
        storage
        input

    markers:
        ordered list

    fatal:
        vector/error/rip/cr2/cr3/rsp

    result:
        last_successful_stage

This is far more actionable than a screenshot saying the machine froze.

## Platforms without COM1

Machines without usable legacy COM1 are currently poor diagnostic targets because serial_init failure halts kstart.

A future hardware roadmap should add another early output path, such as:

- framebuffer text before full graphics;
- a supported hardware debug port;
- USB debug transport;
- a recoverable in-memory crash record.

Until then, accessible serial is highly valuable for first physical targets.

## Feature bisect flags

Available flags support systematic isolation:

- safe;
- nosmp;
- noapic;
- noac97;
- nonet;
- nojit;
- gfx.backend=framebuffer;
- gfx.3d=software;
- gfx.3d=virgl;
- gfx.3d=auto.

Change one dimension per experiment.

Changing storage controller, SMP, graphics and JIT simultaneously destroys diagnostic information.

## Reproducibility procedure

For a hardware failure:

1. identify the exact machine and controller;
2. record build identity;
3. capture the full serial log;
4. repeat the normal boot;
5. repeat with safe mode;
6. reduce the difference to one feature;
7. reproduce the failure at least twice;
8. record the last ordered marker;
9. patch only the suspected subsystem;
10. rerun the same test with the new build.

This creates evidence suitable for regression gates.

## Turning fixes into hardware gates

After fixing a physical failure, define a repeatable gate with:

- reset/power action;
- boot image;
- serial capture;
- timeout;
- positive markers;
- fatal markers;
- reboot cycle when relevant;
- retained artifacts.

One successful debugging session then becomes permanent project capability.

## Highest-value improvements

The next diagnostic improvements are:

1. stop hard-halting when COM1 is absent and add an early fallback console;
2. add timeout/error handling to serial transmit;
3. emit explicit machine-readable stage identifiers around major kstart transitions;
4. dump all GPRs and RFLAGS on panic;
5. add page-table diagnostics for page faults;
6. retain build identity in every artifact;
7. make klog persistence larger/configurable;
8. create a read-only hardware-discovery boot mode;
9. export PCI vendor/device/BAR/IRQ state systematically;
10. store BootInfo/ACPI summaries as structured evidence;
11. convert validated physical machines into automated hardware gates.

## Current diagnostic classification

At the reviewed revision:

    early COM1 logging              implemented
    circular in-memory klog         implemented
    build/git/hash identity         implemented
    verbose bootinfo                implemented
    panic RIP/CR2/CR3/RSP context   implemented
    persisted SYS/BOOT.LOG          implemented after ChrisFS mount
    marker-based QEMU validation    implemented
    safe-mode differential boot     implemented
    automated physical gate         not established
    early non-serial console        not implemented
    complete panic register dump    not implemented
    stack unwinder                  not implemented
    structured hardware record      not implemented

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisOS already has the basis of a serious bring-up workflow: serial starts at the first kernel stage, build identity is embedded in logs, bootinfo is verbose, fatal exceptions preserve key architectural context, output is mirrored into an 8 KiB ring and later persisted to ChrisFS, and QEMU gates use explicit positive/fatal markers. The main physical-debugging weakness is the hard boot dependency on legacy COM1 and the absence of a structured automated hardware evidence pipeline.
