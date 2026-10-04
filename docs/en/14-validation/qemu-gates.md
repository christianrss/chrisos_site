---
id: qemu-gates
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - scripts/qemu.mk
  - tools/qemu_gate.py
  - tools/check_install_img.py
  - kernel/metal/start.c
  - kernel/fs/storage.c
  - kernel/fs/xhci.c
  - kernel/gfx/vgpu.c
symbols: []
depends_on:
  - host-tests
  - validation-evidence
related:
  - hardware-gates
  - driver-compatibility
  - bringup-diagnostics
  - installation-real-hardware
  - performance-measurement
---

# QEMU gate architecture

## Scope

ChrisOS uses QEMU as the principal integrated validation layer between host-only algorithm tests and physical-hardware evidence.

The canonical aggregate target is:

    make qemu-gates

A QEMU gate boots the actual ChrisOS image with an explicit virtual hardware topology, captures the guest serial log and judges the run from observable markers.

The central rule is:

    elapsed time is not success

A guest can remain alive while initialization silently failed. Conversely, a kernel designed to keep running indefinitely must not be classified as failed merely because the test runner terminated QEMU at a timeout.

The gate therefore evaluates state recorded in the serial log.

## Gate runner

The common runner is:

    tools/qemu_gate.py

Each invocation supplies:

- a timeout;
- a serial-log path;
- zero or more required markers;
- the complete QEMU command after `--`.

The runner starts QEMU with `subprocess.run`.

If QEMU exceeds the timeout, the runner records synthetic exit code 124.

A result is acceptable when the process code is:

    0
    or
    124

provided every expected marker exists and no fatal marker exists.

Any other QEMU exit status fails the gate.

This design treats timeout as controlled termination of a long-running OS, not as success by itself.

## Positive-marker semantics

Each gate declares strings that must appear in the serial log.

Examples include:

    cpu_online_count=4
    root ata
    cfs mounted
    ahci disk sectors=
    bdev rw ok ahci
    xhci hid ready
    virtio-gpu ready
    ChrisOS: desktop 60Hz

The marker should prove the property under test.

A gate for an AHCI data path does not pass merely because the desktop starts; it requires AHCI discovery and block-device read/write evidence.

A gate for the installed-disk path requires both installer markers and a second boot from the produced disk.

## Fatal markers

The runner rejects a log containing any of these current fatal patterns:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

Fatal detection is independent of the positive-marker list.

Therefore a log that reaches an expected marker and later panics still fails.

This is important because late corruption must not be hidden by early success.

## Evidence model

A QEMU gate establishes a tuple of evidence:

[
Q = (R, M, D, O)
]

where:

- (R) is the exact ChrisOS revision;
- (M) is the QEMU machine/device configuration;
- (D) is the guest disk/image state;
- (O) is the required observable marker set.

Changing any element changes the experiment.

A statement such as "AHCI passes in QEMU" is incomplete unless the tested topology and revision are recoverable.

## Common x86-64 machine configuration

Most x86-64 gates use the shared definition:

    -M pc
    -m 2048
    -smp $(QEMU_SMP)
    -display none
    -serial file:build/qemu-test.txt
    -no-reboot
    -cpu qemu64
    -accel tcg

The default:

    QEMU_SMP ?= 4

means the ordinary ATA gate also validates that four logical CPUs reach the expected online marker.

TCG is deliberately deterministic and portable compared with requiring host KVM availability.

This improves CI portability at the cost of performance and some loss of physical timing fidelity.

## ATA baseline gate

`test-qemu-ata` is the basic integrated x86-64 boot gate.

It requires:

    cpu_online_count=$(QEMU_SMP)
    root ata
    cfs mounted

The root disk is attached through QEMU IDE.

This gate jointly exercises:

- image boot;
- Limine handoff;
- CPU bring-up;
- ATA root discovery;
- ChrisFS mount.

Because several subsystems are crossed before the markers appear, a failure should be localized using the ordered boot log rather than assuming ATA is always the cause.

## AHCI gate

`test-qemu-ahci` creates a separate 32 MiB image and attaches it through:

    ich9-ahci

The required markers are:

    ahci disk sectors=
    bdev rw ok ahci

The root filesystem remains on the ordinary boot disk. The extra AHCI disk is therefore a secondary device under test.

This separation matters because ChrisOS can boot far enough to test the controller even when that secondary disk is not the root.

The read/write marker comes from the common block-device exercise and proves more than PCI discovery alone.

## NVMe gate

`test-qemu-nvme` creates a 32 MiB image and attaches:

    -device nvme,serial=chris,drive=nvmedisk

The required markers are:

    nvme disk sectors=
    bdev rw ok nvme

The gate validates the current controller initialization, namespace discovery and block-device I/O path against QEMU's NVMe model.

It does not prove arbitrary NVMe hardware compatibility or 4 KiB-native namespace support.

## VirtIO block gate

`test-qemu-vblk` uses:

    virtio-blk-pci

and requires:

    virtio-blk sectors=
    bdev rw ok virtio-blk

This path is valuable because it exercises the generic block layer with a queue-based virtual device unrelated to ATA/AHCI/NVMe.

A failure common to several storage gates often points above the controller-specific layer.

## USB mass-storage gate

`test-qemu-usb` creates a 32 MiB image and attaches it through QEMU USB mass storage.

The test also attaches a USB tablet.

The required markers are:

    usb msc sectors=
    bdev rw ok usb

The timeout is 50 seconds, slightly larger than the standard storage gates.

The evidence applies to the current emulated USB path and must not be generalized to arbitrary xHCI storage or UAS.

## VirtIO-GPU gate

`test-qemu-gpu` attaches:

    virtio-gpu-pci

and requires:

    virtio-gpu ready

This is a transport/device bring-up gate.

It does not require the much deeper VirGL shader/rendering marker set.

That separation allows ordinary CI to validate basic VirtIO-GPU availability without requiring a host OpenGL/VirGL environment.

## VirGL gate

`test-qemu-virgl` is intentionally conditional.

Before booting, it checks whether the host QEMU exposes a GL-capable VirtIO GPU and whether a usable GL display path exists.

Possible host display backends include:

    egl-headless
    gtk,gl=on

If the required host support is absent, the target reports:

    SKIP: host QEMU lacks VirGL support

and exits separately from an ordinary pass.

When runnable, the gate requires a much richer marker set, including:

- VirGL feature negotiation;
- clear;
- triangle;
- cube;
- depth;
- textured cube;
- GLSL compilation;
- varying;
- lighting;
- shader switching;
- lit mesh;
- final present;
- `3D backend -> virgl`.

This is one of the deepest rendering integration tests in the repository.

However, it is not a dependency of `qemu-gates`, because ordinary CI cannot assume host GL support.

## RISC-V gate

`test-qemu-riscv` boots:

    qemu-system-riscv64 -M virt

with a VirtIO block device and VirtIO GPU device.

It requires markers including:

    riscv kernel
    sv39 on
    clvm halt
    virtio-blk
    virtio-gpu detected

This provides architectural diversification.

It does not make the x86-64 and RISC-V kernels equivalent in feature coverage; it proves the specific RISC-V bring-up path represented by those markers.

## No-ATA fallback gate

`test-qemu-noata` is a negative-topology integration test.

It deliberately removes the ordinary ATA root path and requires:

    ata missing
    root ahci
    cfs mounted
    install selftest ok
    desktop 60Hz

This gate proves that AHCI can become the root path rather than merely coexist as a secondary device.

It also proves the system does not require successful ATA discovery to reach the desktop.

This kind of topology-removal test is stronger than only testing additive device configurations.

## Installation gate

`test-qemu-install` is a two-stage integration test.

### Stage 1: installation

The target:

1. clones a prepared ChrisFS source image;
2. inserts the current kernel, BOOTX64.EFI and Limine configuration;
3. inserts automatic-install control files;
4. creates a blank 560 MiB AHCI target;
5. boots ChrisOS;
6. requires installer markers.

Expected markers include:

    install auto
    install tree copied
    install gpt+esp+cfs disk=ahci

### Stage 2: structural inspection

After the first boot, the host executes:

    tools/check_install_img.py

The checker validates primary/backup GPT data, ChrisFS placement and expected ESP entries.

This independent parser prevents a guest-side installer bug from being "validated" only by guest code sharing the same assumptions.

### Stage 3: disk-only UEFI boot

The produced disk is then booted again using OVMF pflash firmware.

The second gate requires:

    cfs mounted
    desktop 60Hz

This proves that the installed disk is not merely structurally plausible; it is bootable through the tested UEFI path.

The timeout is 300 seconds because installation and second-stage boot are substantially heavier than device probes.

## SMP variation

`test-qemu-smp1` reuses the ATA gate with:

    QEMU_SMP=1

The ordinary gate uses the default four-vCPU configuration.

Testing both is useful because some errors only appear in SMP state transitions while others are hidden when multiple CPUs are expected.

The single-CPU gate is not part of `qemu-gates`; it is added by:

    full-gates

## Safe-mode gate

The build creates a temporary ISO whose Limine command line contains:

    safe

`test-qemu-safe` requires:

    safe mode
    smp off
    desktop 60Hz

Safe mode disables or reduces several optional paths.

The gate proves that the fallback configuration remains bootable as the normal system evolves.

A safe-mode pass is particularly useful when an ordinary gate fails after a change to SMP, APIC, audio, network or JIT-related behavior.

## xHCI HID gate

`test-qemu-xhci` attaches:

    qemu-xhci
    usb-kbd
    usb-mouse

and requires:

    xhci hid ready

The current driver is intentionally narrow, so the gate should be interpreted as proof of the implemented QEMU HID path rather than a broad USB compatibility claim.

## Aggregate target

The current `qemu-gates` dependency list is:

    test-qemu-ata
    test-qemu-ahci
    test-qemu-nvme
    test-qemu-vblk
    test-qemu-usb
    test-qemu-gpu
    test-qemu-riscv
    test-qemu-noata
    test-qemu-install
    test-qemu-safe
    test-qemu-xhci

Notably absent:

    test-qemu-virgl
    test-qemu-smp1

VirGL is environment-dependent.

The single-CPU variant is added separately by `full-gates`.

## Full gate hierarchy

The current top-level composition is:

    host-gates
        algorithmic and userspace evidence

    qemu-gates
        integrated virtual-hardware evidence

    test-qemu-smp1
        explicit uniprocessor variation

and:

    full-gates: host-gates qemu-gates test-qemu-smp1

This hierarchy gives failures a natural localization path.

If a host test fails, QEMU integration should not be trusted.

If host tests pass but QEMU fails, investigate privileged/integration boundaries.

If QEMU passes but physical hardware fails, investigate firmware, topology, device-specific behavior and timing.

## Serial log as evidence artifact

The serial log is the primary artifact used by the gates.

Advantages:

- works without a graphical display;
- survives guest UI failure;
- preserves ordered initialization markers;
- contains build identity and fatal records;
- is easy to inspect in CI.

The log should be retained when a gate fails.

A future validation system can additionally preserve machine-readable event records, disk images, screenshots and QEMU version metadata.

## Ordering and causality

The current runner checks marker presence, not marker order.

Therefore:

    A appears
    B appears

passes the same way as:

    B appears
    A appears

if both strings exist.

For many gates this is adequate because marker uniqueness and boot flow make inversion unlikely.

A stronger future runner should model boot as an ordered state machine and optionally require marker order.

This would prevent stale or repeated log fragments from satisfying an experiment incorrectly.

## Log freshness

Most targets explicitly remove the log before boot:

    rm -f build/qemu-test.txt

This is essential because marker-presence evaluation assumes the file belongs to the current run.

Any future gate that appends to an existing log risks false positives from old markers.

## Timeout design

Timeouts are per experiment rather than globally fixed.

Examples:

- ordinary storage/GPU gates: approximately 40 seconds;
- USB: 50 seconds;
- safe/no-ATA/xHCI: 90 seconds;
- VirGL: 180 seconds;
- installer: 300 seconds.

A timeout is a liveness budget.

Increasing it can reduce false failures on slow CI, but excessively large values hide hangs and slow feedback.

The best timeout is comfortably above healthy runtime while still bounding deadlock detection.

## Limitations of QEMU evidence

QEMU gates do not reproduce:

- arbitrary firmware behavior;
- physical PCIe topology;
- controller-specific errata;
- real DMA/IOMMU interactions;
- physical interrupt routing;
- storage cache/power-loss behavior;
- device thermal or timing behavior;
- all CPU microarchitectural ordering effects.

TCG also changes timing substantially.

Therefore QEMU success is a strong software-integration result but remains below physical-hardware evidence.

## Highest-value improvements

The next improvements to the gate architecture are:

1. record QEMU version with each artifact;
2. preserve complete command line and image hashes;
3. require ordered marker sequences where causality matters;
4. add structured JSON event output beside serial text;
5. retain failed logs automatically in CI artifacts;
6. distinguish explicit skip from pass/failure in aggregate reporting;
7. add more negative-topology gates;
8. add controlled reset/reboot loops;
9. compare boot markers across repeated runs;
10. connect each physical hardware gate to an equivalent QEMU baseline when possible.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

At this revision, QEMU validation is a substantial integration layer with device-specific positive markers, fatal-marker rejection, topology variation, a two-stage installation/OVMF test and explicit separation between ordinary gates and environment-dependent VirGL coverage. QEMU success must remain classified as virtual-hardware evidence, not physical compatibility.
