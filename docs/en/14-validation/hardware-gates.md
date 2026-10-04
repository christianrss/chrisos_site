---
id: hardware-gates
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/buildid.c
  - kernel/metal/klog.c
  - kernel/metal/panic.c
  - kernel/metal/bootinfo.c
  - kernel/metal/pci.c
  - kernel/metal/acpi.c
  - kernel/fs/storage.c
  - scripts/qemu.mk
symbols:
  - kstart
  - serial_init
  - build_info_log
  - klog_copy
  - panic
  - panic_exception
  - bootinfo_init
  - pci_read
  - acpi_probe
  - storage_init
depends_on:
  - qemu-gates
  - driver-compatibility
  - bringup-diagnostics
related:
  - installation-real-hardware
  - hardware-profile
  - fault-injection
  - performance-measurement
---

# Physical-hardware validation and hardware gates

## Scope

Physical-hardware validation is the highest evidence layer currently defined for ChrisOS device and platform compatibility.

At the reviewed revision, ChrisOS contains the logging, build identity, boot markers and device paths needed to perform disciplined physical tests.

It does **not** yet contain a repository-integrated automated hardware-gate harness equivalent to `tools/qemu_gate.py`.

This distinction is fundamental:

    hardware-testable != hardware-gated

A manually observed boot can establish evidence for one named machine and revision.

A hardware gate requires a repeatable controller around that machine: power/reset control, image deployment, serial capture, machine identity, marker evaluation and retained artifacts.

## Evidence hierarchy

The physical layer should be interpreted after the lower layers:

    source present
        -> host tested
        -> QEMU tested
        -> physically observed
        -> hardware gated

Each promotion adds environmental realism.

It does not erase the lower-level tests.

A physical AHCI pass, for example, should still be backed by the host filesystem tests and QEMU AHCI gate because those layers provide cheaper failure localization.

## Minimum evidence tuple

A physical result should be represented as:

[
H = (R, M, F, D, C, O)
]

where:

- (R) — ChrisOS Git revision and kernel hash;
- (M) — machine identity;
- (F) — firmware identity and mode;
- (D) — target device identity;
- (C) — exact boot/configuration conditions;
- (O) — ordered observations and result.

A result without (R) cannot be reliably reproduced after the code changes.

A result without (D) cannot establish device compatibility.

## Build provenance

ChrisOS emits build identity early in boot.

The current build record includes:

- Build ID;
- Git revision;
- build date;
- compiler version;
- SHA-256 embedded into the linked kernel image.

The kernel log therefore already provides a strong key for tying a hardware result to source.

A physical evidence record should copy the complete build block rather than relying on a handwritten version label.

## Early serial dependency

The current earliest diagnostic channel is legacy COM1 at:

    0x3f8

`serial_init` configures the UART and performs a loopback check.

If the loopback test fails, `kstart` disables interrupts and halts.

This has two consequences for physical testing:

1. a machine with a compatible serial port provides excellent early observability;
2. a machine without compatible COM1 can fail before later diagnostics even when the rest of the platform might have been usable.

Therefore the first hardware-gate targets should preferably expose a real or reliably bridged COM1.

A future early framebuffer/debug-port fallback would broaden the physical test pool.

## Serial capture contract

A real hardware gate needs an external serial capture path.

The capture system should:

- open the serial device before reset/power-on;
- record raw bytes with timestamps;
- avoid terminal transformations that alter the guest stream;
- retain the complete log;
- associate the log with one test run ID;
- detect loss/disconnect separately from guest failure.

The serial session should start before firmware handoff because the absence of the first ChrisOS marker is itself evidence.

## Build markers and boot stages

The physical gate should evaluate ordered milestones.

Useful stages already emitted by the kernel include:

1. build identity;
2. BootInfo/HHDM/framebuffer/memory-map information;
3. CPU topology;
4. SMP online count or safe-mode state;
5. ACPI observations;
6. storage device discovery;
7. selected root device;
8. ChrisFS mount;
9. desktop readiness;
10. optional device markers.

A pass criterion should be specific to the capability under test.

For example, a storage gate should require controller discovery plus a successful operation, not merely desktop readiness.

## Fatal evidence

Physical gates should reject the same fatal classes as QEMU gates and preserve their architectural context.

The kernel currently emits:

    PANIC:
    EXCEPTION vector=

and for fatal exceptions can include:

- vector;
- error code;
- RIP;
- CR2;
- CPU;
- CR3;
- RSP;
- Build ID;
- Git revision;
- kernel SHA-256.

This is enough to turn many physical failures into revision-bound debugging artifacts.

The physical runner should stop classifying the run as healthy after any fatal marker, even if the target marker was observed earlier.

## In-memory log

Serial output is mirrored into an 8192-byte kernel log ring.

Once ChrisFS is available, boot code attempts to persist part of the log to:

    SYS/BOOT.LOG

This is useful as a secondary artifact.

It must not replace external serial capture because:

- the ring can overwrite early data;
- the boot may fail before filesystem mount;
- filesystem failure may prevent persistence;
- a crash can occur before the write.

External serial remains the primary physical-gate channel.

## Machine identity

A physical record should identify at least:

| Field | Example category |
|---|---|
| System vendor/model | motherboard or complete system |
| CPU | exact processor model |
| RAM | capacity and relevant topology |
| Firmware | vendor/version |
| Boot mode | UEFI/legacy |
| Secure Boot | enabled/disabled |
| GPU/framebuffer | firmware-visible path |
| Storage controller | PCI ID/model |
| Storage device | model/serial/sector geometry |
| USB controller | PCI ID/model when tested |
| Network/audio | device identity when tested |

"Tested on a PC" is not sufficient evidence.

## PCI identity

Physical compatibility must be tied to concrete PCI identities where appropriate.

Current ChrisOS PCI discovery is incomplete:

- several generic helpers scan only bus 0;
- some drivers perform wider flat scans;
- there is no general recursive bridge traversal;
- there is no general ECAM/MCFG enumeration layer.

A device can therefore be supported at the protocol level but invisible in a specific topology.

The hardware record should include observed bus/device/function and vendor/device IDs whenever possible.

## Firmware evidence

Firmware behavior is a major source of divergence from QEMU.

The current boot path depends on Limine and expects:

- framebuffer response;
- HHDM response;
- memory map;
- multiprocessor information.

A physical record should preserve:

- firmware version;
- UEFI/legacy mode;
- Secure Boot state;
- framebuffer geometry;
- memory-map summary;
- CPU count.

A failure before device initialization can therefore be classified as platform/boot-contract failure rather than driver failure.

## ACPI evidence

The current ACPI code is diagnostic and limited.

It scans for RSDP in the legacy physical range and reports selected XSDT tables such as:

    APIC
    MCFG
    FACP

The physical log should preserve these markers.

Their presence is useful platform evidence, but current ChrisOS does not yet consume a complete ACPI/PCIe platform description.

Absence or incomplete discovery should therefore be recorded as a platform limitation, not silently ignored.

## Storage safety

Physical storage testing is dangerous at the current revision.

The storage initialization path can perform write/read/restore tests on writable non-root devices.

Blank-device discovery can also format a sufficiently empty writable device when searching for a root.

Therefore a hardware gate must use:

- disposable media;
- a dedicated test disk;
- or an isolated clone.

It must never point at a disk containing valuable data.

A future read-only discovery mode is a prerequisite for safer broad hardware testing.

## Storage gate procedure

A minimal AHCI or NVMe physical gate should:

1. identify the exact controller and disk;
2. record logical sector size and capacity;
3. boot a revision-bound ChrisOS image;
4. capture serial from power-on;
5. require controller discovery;
6. require block-device registration;
7. require a known read/write marker on dedicated media;
8. require filesystem mount when testing root operation;
9. reboot;
10. verify persistence or repeated healthy discovery;
11. preserve the log and machine record.

A one-time detection marker alone is not enough.

## Input gate procedure

For PS/2 or xHCI HID, a useful hardware gate requires more than a "ready" marker.

It should verify:

- controller discovery;
- keyboard event delivery;
- key press/release behavior;
- mouse motion/button behavior when applicable;
- sustained input after desktop start;
- no fatal markers during repeated interaction.

Input tests require a source of reproducible stimuli.

A mature physical harness can use a USB relay/emulator or other programmable input source rather than human interaction.

## Graphics gate procedure

The baseline physical graphics path is the Limine-provided framebuffer.

A framebuffer gate should record:

- address;
- width;
- height;
- pitch;
- bits per pixel;
- successful desktop marker;
- repeated presentation without corruption.

This does **not** prove a native GPU driver.

Modern native GPU compatibility remains outside the current implementation.

## Network and audio

The current network path is VirtIO-oriented and the current native audio target is AC97.

These are not broad physical-device families on modern systems.

A physical machine can therefore pass the core boot/storage/input gate while network or audio remains unavailable.

The hardware matrix should classify capabilities independently instead of reducing the entire machine to one pass/fail bit.

## Manual observation versus hardware gate

The evidence classes should remain distinct:

### Physically observed

A human executes the defined procedure, captures logs and records machine identity.

This is valid evidence if provenance is complete.

### Hardware-gated

An automated controller can repeat the experiment without manual interpretation.

A hardware gate should control or observe:

- image selection/deployment;
- power cycle or reset;
- boot target;
- serial capture;
- timeout;
- positive markers;
- fatal markers;
- artifact upload;
- machine identity;
- final status.

ChrisOS currently has the first class available as a methodology, not the second as repository automation.

## Proposed runner contract

A future hardware runner should conceptually accept:

    --machine <profile>
    --image <artifact>
    --serial <device>
    --timeout <seconds>
    --expect <marker>...
    --fatal <marker>...
    --power-cycle <backend>

and emit a structured result:

    run_id
    machine_id
    firmware
    git_revision
    kernel_sha256
    image_sha256
    start/end timestamps
    markers observed in order
    fatal marker if any
    serial artifact
    pass/fail/infra-error

Infrastructure failure must be distinct from guest failure.

A disconnected serial cable is not a ChrisOS regression.

## Power and reset control

A repeatable hardware gate needs deterministic reset.

Possible mechanisms include:

- managed PDU;
- relay wired to the reset/power header;
- BMC/IPMI/Redfish where available;
- network-controlled USB relay;
- development-board reset line.

The important property is not the brand of controller.

It is that the runner can establish a known machine state and repeat the same experiment.

## Boot media management

The runner must know exactly which image booted.

A robust path should:

1. write the image to dedicated media;
2. hash the resulting image or artifact;
3. set/select the intended boot device;
4. record the image hash in the run metadata;
5. prevent accidental reuse of stale media when a new revision is expected.

Without image identity, build provenance in the serial log can reveal mismatch, but the gate should detect it automatically.

## Repetition

Hardware behavior can be intermittent.

A single successful boot proves possibility, not reliability.

For a hardware gate, use repeated trials:

[
p_{obs} = rac{	ext{successful trials}}{	ext{total trials}}
]

This is not a statistical reliability estimate by itself, but it makes flakiness visible.

Cold boots, warm resets and device-specific operations should be counted separately.

## Failure localization

When a physical gate fails:

1. preserve the first failing log;
2. identify the last confirmed marker;
3. compare with the equivalent QEMU gate;
4. retry safe mode where relevant;
5. change only one dimension at a time;
6. repeat on the same revision;
7. classify the failing boundary before changing code.

If QEMU and host gates pass while physical hardware fails consistently, the highest-probability investigation area shifts toward firmware, topology, timing and device-specific assumptions.

## Compatibility matrix rule

A hardware matrix entry should never be inferred from a driver name.

An entry requires a concrete evidence record.

Recommended status values are:

    implemented
    qemu-validated
    physically observed
    hardware-gated
    known incompatible
    not tested

This preserves uncertainty instead of converting absence of evidence into support.

## Current state

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`:

- revision-bound build identity exists;
- early COM1 logging exists;
- fatal exception context exists;
- boot-stage markers exist;
- QEMU marker evaluation exists;
- hardware-profile documentation exists;
- manual physical evidence can be recorded rigorously;
- no general automated physical hardware-gate runner is present in the inspected repository;
- no maintained broad physical compatibility matrix has yet been established.

## Highest-value next steps

The most useful sequence is:

1. select one development machine with accessible COM1;
2. add non-destructive hardware discovery mode;
3. record complete PCI/device identity;
4. validate framebuffer + safe-mode boot;
5. establish first physical AHCI or NVMe result using disposable media;
6. automate serial capture;
7. automate reset/power cycle;
8. store machine profile and artifacts;
9. promote the procedure into a repeatable hardware gate;
10. expand one device class at a time.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

ChrisOS already exposes enough provenance and serial diagnostics for disciplined bare-metal validation, but physical compatibility remains an evidence-collection task rather than an automated gate in the current repository. Claims must distinguish manual observation from repeatable hardware gating.
