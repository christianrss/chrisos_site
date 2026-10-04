---
id: chrisvm-devices
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisSerial
  - ChrisFb
  - chris_serial_attach
  - chris_fb_attach
  - chris_fb_get
  - chris_fb_write_image
  - chris_view_show
depends_on:
  - chrisvm-io-bus
  - chrisvm-mmio-bus
related:
  - chrisvm-machine
  - chrisvm-memory-map
  - chrisvm-boot
---

# Built-in ChrisVM devices

## Scope

The current ChrisVM machine has a deliberately small built-in device set:

- a UART-like serial device at the traditional COM1 port range;
- a project-specific shutdown port;
- a fixed linear framebuffer;
- an optional host-side SDL viewer for the framebuffer.

The generic MMIO cell used in tests is a fixture, not a permanent platform device.

There is no mature PCI bus, block controller, network device, APIC/IOAPIC, keyboard controller, timer complex or ACPI device model in the inspected ChrisVM platform.

This chapter documents the built-in device behavior at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Device ownership model

Serial and framebuffer state are embedded directly in ChrisMachine.

The machine contains:

    ChrisSerial serial
    ChrisFb fb

The serial device registers itself on the port-I/O bus.

The framebuffer is handled by a dedicated physical-address fast path rather than the generic MMIO registry.

The devices therefore use two different attachment mechanisms even though both belong to one machine.

## Serial port range

chris_serial_attach registers:

    0x3f8 .. 0x3ff

This is the conventional COM1 port range.

The model uses the low three port bits as a register selector.

It provides enough UART-like behavior for boot diagnostics, output capture and loopback testing.

It is not a complete 16550A implementation.

## Serial state

ChrisSerial stores:

- ier;
- lcr;
- mcr;
- scr;
- dll;
- dlm;
- loop_data;
- loop_dr;
- TX buffer;
- TX length;
- optional host hook and context.

There is no full receive FIFO, transmit FIFO, interrupt-pending queue or timing engine.

The model is register-oriented and synchronous.

## DLAB behavior

DLAB is bit 7 of LCR.

When DLAB is set:

- port offset 0 accesses DLL;
- port offset 1 accesses DLM.

When DLAB is clear:

- offset 0 is the data register;
- offset 1 is IER.

This matches the basic UART divisor-latch multiplexing convention.

The model stores divisor bytes but does not use them to simulate baud-rate timing.

## Data register

For an ordinary write to offset zero with DLAB clear:

- if loopback is active, the byte goes to loop_data;
- otherwise it is appended to the host-visible TX buffer when capacity allows;
- the optional host serial hook is invoked.

Only the low byte of the written value is used.

Serial output is therefore immediately observable by the host and does not wait for simulated transmit timing.

## TX buffer

The embedded transmit buffer has:

    CHRIS_TX_MAX = 8192

bytes.

The implementation appends while:

    tx_len + 1 < CHRIS_TX_MAX

preserving one byte for the null terminator.

Once full, later bytes are not appended to the string buffer.

The optional host hook is still invoked for ordinary transmitted bytes even when the fixed text buffer is full, because the hook call occurs outside the append condition.

This difference matters if the hook and chris_serial_text are both used as output sinks.

## Host serial hook

chris_serial_set_hook installs:

    callback
    context

on the built-in serial object.

Every ordinary transmitted byte invokes the callback.

This allows frontends/tests to stream guest serial output without polling the fixed TX buffer.

The callback pointer belongs to host process state and is not portable snapshot data.

## Loopback mode

Bit 4 of MCR activates the simplified loopback behavior.

A write to the data register stores the low byte in loop_data and sets loop_dr.

A later read from the data register returns loop_data and clears loop_dr.

LSR bit 0 reflects loop_dr.

The integration test exercises this path and confirms guest OUT/IN round-trip behavior.

## Interrupt Enable Register

IER is stored when DLAB is clear and offset one is written.

The current serial model does not use IER to generate interrupts.

Thus the register is stateful, but interrupt-enable semantics are not implemented.

A guest can write/read the value without gaining a real UART IRQ source.

## Interrupt Identification Register

Offset two reads as:

    0x01

which represents no interrupt pending in the simplified model.

Writes to offset two are accepted as FCR writes but ignored.

There is no FIFO configuration or interrupt identification state machine.

## Line Control Register

LCR is fully stored as one byte.

Its DLAB bit affects register multiplexing.

Other line-format bits do not influence an actual serial wire model because character width, parity, stop bits and baud timing are not simulated.

## Modem Control Register

MCR is stored.

Bit 4 activates the project loopback path.

Other modem-control outputs do not drive a modeled modem.

## Line Status Register

LSR reads with:

    0x60

set by default, representing transmitter-empty style readiness.

If loop_data is waiting, bit 0 is also set.

The model does not maintain detailed overrun, parity, framing, break or FIFO status.

## Modem Status Register

The simplified MSR read returns zero.

There is no external modem-signal model.

## Scratch Register

Offset seven stores and returns SCR.

This is useful for driver probing because traditional UART detection often checks scratch-register behavior.

## Serial width behavior

The port-I/O bus preserves byte/word/dword width, but the serial callback ignores size.

Writes are reduced to uint8_t.

Thus wider I/O operations do not model multi-register UART access; only the low byte is meaningful.

Current guests use ordinary byte operations.

## Serial timing limitations

The device has no model of:

- baud rate;
- clock divisor timing;
- TX shift register delay;
- RX arrival time;
- FIFO thresholds;
- IRQ timing;
- DMA;
- host input stream scheduling.

This makes output deterministic and simple but unsuitable for software that depends on UART timing.

## Shutdown port

chris_serial_attach also registers:

    0x501

as CHRIS_SHUTDOWN_PORT.

Despite being attached in serial.c, this is conceptually a machine-control device rather than a UART register.

A write whose low byte equals 0x01:

- sets machine shutdown state;
- halts the CPU;
- sets CHRIS_EXIT_SHUTDOWN.

Reads return zero.

This is a ChrisVM paravirtual power-off mechanism.

## Framebuffer configuration

The built-in framebuffer is fixed at:

    physical base = 0x02000000
    width         = 640
    height        = 480
    bytes/pixel   = 4
    pitch         = 2560
    size          = 1,228,800 bytes

chris_fb_attach allocates a zeroed host pixel buffer.

The device has no guest-visible register block.

The guest interacts directly with the mapped pixel memory.

## Pixel format

Host rendering and image export treat each stored 32-bit pixel as containing RGB components in bits:

    red   = bits 23..16
    green = bits 15..8
    blue  = bits 7..0

The SDL viewer uploads the buffer as SDL_PIXELFORMAT_ARGB8888.

The high byte is therefore treated as the alpha/reserved component by the viewer format, while PNG/PPM export uses RGB channels explicitly.

The current guest splash tests write values consistent with this representation.

## Dirty tracking

Any physical write that lands entirely inside framebuffer backing sets:

    fb.dirty = 1

chris_fb_dirty exposes the flag.

There is no dirty rectangle or per-page tracking.

Once dirty becomes set, ordinary writes do not clear it.

The frontend uses the flag to decide whether displaying the framebuffer is useful after execution.

## Framebuffer read API

chris_fb_get validates:

- machine;
- output pointer;
- backing allocation;
- x < width;
- y < height.

It then reads one 32-bit pixel from:

    y * pitch + x * 4

This is a host-side inspection API, not a guest device register.

## Image export

chris_fb_write_image chooses format based on filename extension.

For a .png path, it uses the project's minimal PNG writer.

Otherwise it writes binary PPM.

The PNG path builds:

- PNG signature;
- IHDR;
- IDAT with simple zlib/deflate stored blocks;
- IEND.

This avoids requiring a PNG library for framebuffer dumps.

Image export is a host debugging/output facility and does not alter guest state.

## SDL viewer

chris_view_show is available when ChrisVM is built with CHRIS_HAVE_SDL.

It:

1. copies framebuffer pixels through chris_fb_get;
2. opens a 640x480 SDL window;
3. creates a software renderer;
4. creates an ARGB8888 texture;
5. uploads the copied pixels;
6. presents the frame;
7. processes close events for the requested duration.

The viewer is a snapshot display.

It does not continuously mirror guest writes while the CPU runs in the same function.

If SDL support is absent, chris_view_show returns failure.

## Headless behavior

The frontend checks cfg.headless before attempting to show a dirty framebuffer.

Framebuffer backing still exists in the machine even in headless mode.

Headless therefore affects host presentation, not the guest hardware layout.

The guest sees the same framebuffer memory.

## Fixed framebuffer consequences

The framebuffer base at 32 MiB means RAM above 32 MiB would collide with it.

chris_fb_attach therefore refuses machine creation when RAM exceeds the framebuffer base.

The device's fixed placement currently determines the machine's effective maximum RAM.

This is a strong reason to move device placement into an authoritative configurable physical map.

## No mode setting

The guest cannot program:

- resolution;
- pitch;
- pixel format;
- framebuffer base;
- refresh rate.

There are no VBE/GOP-like registers or PCI display device.

The framebuffer is a boot-protocol contract: one preconfigured linear surface.

## No scanout timing

There is no:

- vertical blank;
- horizontal timing;
- refresh cycle;
- display interrupt;
- tearing model;
- scanout DMA.

Writes immediately modify backing memory.

The host viewer displays a copied snapshot.

## Test evidence

test_chrisvm.c includes a STOS-based framebuffer test.

Guest code:

- sets RDI to the framebuffer address;
- sets RCX;
- loads a 32-bit pixel value;
- executes REP STOSD;
- halts.

The host test checks multiple pixels and the dirty flag.

A larger splash guest is also loaded and executed, then specific pixel coordinates and serial output are checked.

This is meaningful end-to-end evidence that:

    instruction execution
    -> paging
    -> physical framebuffer backing
    -> host pixel inspection

works for the current fixed mode.

## Device inventory versus fixtures

The generic MMIO test cell at 0x06000000 exists only inside test_chrisvm.c.

It is registered by the test at runtime.

It is not created by chris_machine_create and is not part of the standard guest platform.

Similarly, future experimental mappings should not be listed as built-in devices merely because a test registers them.

The standard machine inventory should be derived from machine construction and built-in attach calls.

## Missing platform devices

The inspected ChrisVM machine does not yet provide mature built-in implementations of:

- local APIC;
- IOAPIC;
- PIC/PIT compatibility;
- HPET;
- PCI/PCIe root complex;
- block storage;
- NVMe;
- virtio block;
- virtio net;
- USB;
- keyboard/mouse;
- RTC;
- ACPI power-management hardware.

The ChrisOS kernel may contain drivers for some of these classes, but that does not mean ChrisVM emulates the corresponding hardware.

The virtual platform and guest kernel driver inventory are separate concerns.

## Interrupt gap

Neither built-in serial nor framebuffer currently injects hardware interrupts.

The serial IER is storage only.

The framebuffer has no interrupt source.

This keeps the device set synchronous and simple but prevents realistic interrupt-driven driver behavior.

Future device modeling needs to connect device events to a proper interrupt-controller topology, not directly hard-code vectors into each device.

## Reset semantics

Machine creation zero-initializes serial and framebuffer state.

There is no device-specific runtime reset API separate from destroying and recreating the machine.

A future machine reset should define which device registers return to power-on state and which host resources persist.

## Snapshot implications

Built-in device state is not contained in ChrisArchitectureState.

A complete VM snapshot needs at least:

- ChrisSerial register and loopback/TX state;
- framebuffer pixel contents and dirty state;
- shutdown state;
- future device queues/timers.

Host callback pointers such as serial hook must not be serialized directly.

This reinforces the distinction between CPU architectural state and machine/device state.

## Hardening priorities

The highest-value device work is:

1. move fixed device placement into an authoritative machine map;
2. implement real UART interrupt behavior if serial drivers require it;
3. decide whether RX host input and deterministic scheduling are required;
4. define UART width/timing semantics instead of ignoring size;
5. remove the framebuffer-imposed RAM ceiling;
6. define a guest-discoverable framebuffer contract beyond hard-coded constants;
7. add device reset and snapshot serialization rules;
8. introduce interrupt-controller infrastructure before adding interrupt-driven devices;
9. keep test-only fixtures separate from the standard device inventory;
10. add stable device identity for tracing and map generation;
11. add storage/network devices only with explicit bus, DMA and interrupt contracts;
12. keep host presentation such as SDL outside guest architectural state.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, the standard ChrisVM device platform consists of a simplified COM1-compatible serial path, a project shutdown port and a fixed 640x480 linear framebuffer with host dump/view support. These devices are sufficient for deterministic boot diagnostics and graphics smoke tests, but they intentionally omit timing, device interrupts, enumeration and general PC platform hardware.
