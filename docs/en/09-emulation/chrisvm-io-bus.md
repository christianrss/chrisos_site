---
id: chrisvm-io-bus
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/buses/io.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisIoSlot
  - chris_io_map
  - chris_io_in
  - chris_io_out
  - do_io
depends_on:
  - chrisvm-memory-map
  - x86-decoding
related:
  - chrisvm-mmio-bus
  - chrisvm-devices
  - chrisvm-machine
---

# ChrisVM port-I/O bus

## Scope

ChrisVM models the x86 port-I/O address space separately from physical memory. The bus connects decoded IN/OUT instructions to registered device callbacks using 16-bit port numbers.

The current implementation is intentionally compact:

- eight registration slots;
- inclusive port ranges;
- byte, word and dword access widths;
- first-match dispatch;
- tolerant behavior for unmapped ports.

This is sufficient for the serial and shutdown devices used by current guests, but it does not yet model privilege checks, TSS I/O bitmaps, string I/O, complex PCI configuration or a scalable device registry.

This chapter documents revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Separate x86 address space

Port I/O is not routed through chris_phys_read/chris_phys_write.

The instruction path is:

    guest IN/OUT instruction
      -> decode.c
      -> do_io()
      -> chris_io_in/chris_io_out
      -> matching ChrisIoSlot callback

The address is a 16-bit port, independent of guest virtual-memory translation and physical RAM/MMIO mappings.

This distinction matters because the same numeric value can exist simultaneously as:

- a memory physical address;
- an I/O port.

They are architecturally different spaces.

## Registration structure

Each ChrisIoSlot stores:

- used;
- start;
- end;
- input callback;
- output callback;
- opaque context pointer.

The range is inclusive:

    start <= port <= end

The machine owns:

    ChrisIoSlot io[CHRIS_IO_MAX]

with:

    CHRIS_IO_MAX = 8

No dynamic allocation is required for bus lookup.

## Registration

chris_io_map validates:

- machine pointer is non-null;
- start is not greater than end.

It then selects the first unused slot and stores the supplied range and callbacks.

Registration fails when all eight slots are occupied.

The function does not validate:

- overlap with existing ranges;
- null input callback;
- null output callback;
- device-specific width requirements.

Those omissions are important parts of the current contract.

## First-match dispatch

find_io scans slots from index zero upward.

The first used slot whose inclusive range contains the requested port wins.

Therefore overlapping registrations are not ambiguous to the implementation; they are resolved by slot order.

However, slot order is an implicit priority rather than a declared platform rule.

A future bus model should reject accidental overlap or make priority explicit.

## Accepted access widths

chris_io_in and chris_io_out accept sizes:

    1 byte
    2 bytes
    4 bytes

Any other width is rejected.

This matches the currently decoded scalar x86 port-I/O forms:

- IN AL;
- IN AX;
- IN EAX;
- OUT AL;
- OUT AX;
- OUT EAX.

There is no 64-bit port-I/O operand.

## Immediate-port IN/OUT

The decoder recognizes opcodes:

    E4 E5 E6 E7

These forms encode an immediate 8-bit port number.

The decoder records:

    imm_src = 1
    imm_bytes = 1

do_io obtains the port from:

    imm & 0xff

Therefore immediate-port instructions can directly address ports 0x00 through 0xff.

This follows the x86 encoding constraint.

## DX-port IN/OUT

The decoder also recognizes:

    EC ED EE EF

These forms use DX.

do_io takes:

    RDX & 0xffff

as the port number.

Thus the complete 16-bit I/O space can be reached through DX.

Only the low sixteen bits matter.

## Operand width selection

Byte forms E4/E6/EC/EE force operand size one.

Non-byte forms use the decoder's operand-size state:

- default 32-bit;
- 0x66 prefix selects 16-bit where applicable.

do_io converts the decoded operand size into callback size:

    os 1 -> size 1
    os 2 -> size 2
    otherwise -> size 4

A REX.W prefix does not create 64-bit IN/OUT semantics. The execution helper caps non-byte/non-word I/O at four bytes.

## Accumulator semantics

IN writes the returned value into the accumulator family through chris_write_gpr.

Depending on size, the destination is effectively:

- AL;
- AX;
- EAX.

A 32-bit GPR write clears the upper half according to the existing register-write contract.

OUT reads the matching accumulator width through chris_read_gpr.

The bus therefore receives only the architecturally selected low accumulator bits.

## Unmapped reads

When no slot matches an IN operation, chris_io_in returns success and supplies all-one data:

    size 1 -> 0xff
    size 2 -> 0xffff
    size 4 -> 0xffffffff

This is a deliberate tolerant-device-probing behavior.

Guest software can therefore probe unknown ports without forcing an emulator exception or exit.

The value is part of ChrisVM's observable platform behavior.

## Unmapped writes

When no slot matches an OUT operation, chris_io_out returns success and discards the value.

Again, this is deliberately permissive.

It prevents unknown legacy writes from terminating current test guests.

A more strict machine profile could choose different semantics, but that would be a guest-visible platform change.

## Callback width is preserved

Unlike generic MMIO dispatch, port-I/O callbacks receive the original scalar access width.

For example, an OUT with size 2 results in one callback carrying:

    port
    size = 2
    value

This is a stronger transaction model than the current generic MMIO byte loop.

Individual devices are still free to ignore the width, as the current serial device does for several registers.

## Built-in serial range

chris_serial_attach registers:

    0x3f8 .. 0x3ff

for the built-in UART-like serial model.

This corresponds to the traditional COM1 base range.

The model supports selected register behavior:

- divisor latch access;
- interrupt-enable storage;
- line-control storage;
- modem-control storage;
- scratch register;
- status values;
- loopback transmit/receive;
- host TX capture.

It is not a timing-accurate 16550 implementation.

## Serial loopback

When the serial modem-control loopback bit is set, writes to the data register are stored in loop_data instead of transmitted to the host buffer.

A following read can return that byte and clear the loop-data-ready marker.

test_chrisvm.c exercises this path through real IN/OUT guest instructions.

This provides an end-to-end check across:

    decoder
    -> do_io
    -> bus dispatch
    -> serial callback
    -> accumulator result

## Serial width simplification

serial_in and serial_out receive the size argument but currently ignore it.

serial_out casts the value to uint8_t.

Thus a word or dword OUT directed at a serial register effectively uses only the low byte in the current model.

That is sufficient for current guests, but should not be generalized as complete UART bus semantics.

A more accurate device can use the preserved size parameter to define width-specific behavior.

## Shutdown port

The machine also registers:

    CHRIS_SHUTDOWN_PORT = 0x501

The shutdown callback checks the low byte of the output value.

When it equals 0x01, the machine:

- sets shutdown;
- sets CPU exit reason to CHRIS_EXIT_SHUTDOWN;
- halts the CPU.

This is a ChrisVM-specific paravirtual convention.

It is intentionally simple and independent of ACPI power management.

## Fixed slot capacity

Serial and shutdown already consume two of the eight port-I/O slots.

That leaves six slots for additional devices in the current machine.

There is no dynamic expansion.

A future platform with PCI configuration ports, timers, keyboard controller, PIC compatibility or additional legacy devices can exhaust the registry quickly.

The capacity should therefore be seen as a bring-up constant, not a scalable bus architecture.

## Overlap behavior

Suppose a later device registers:

    0x3f8 .. 0x3f8

after the serial device.

Both mappings are stored successfully.

find_io sees the earlier serial slot first, so the later device is unreachable at that port.

Reversing registration order reverses ownership.

This implicit priority can hide configuration errors.

An explicit overlap check is preferable for a machine with deterministic static topology.

## Callback nullability gap

chris_io_map stores callback pointers without validating them.

If a port matches a slot and the requested direction's callback is null, dispatch attempts to call it.

The current built-in devices provide both directions, so ordinary ChrisVM operation is safe.

The generic API itself, however, does not enforce this invariant.

A hardened design should either:

- reject missing handlers;
- or define safe semantics for read-only/write-only port ranges.

## No unregister or remap

Once a slot is registered, the current API has no unmap operation.

There is also no region replacement or lifecycle hook associated with a slot.

This is acceptable for static machine construction, but limits hotplug, device reset/reconfiguration and reusable test fixtures.

## No I/O privilege enforcement

The current execution path for IN/OUT does not check:

- CPL;
- IOPL in RFLAGS;
- TSS I/O-permission bitmap.

If an instruction decodes successfully, do_io can access the virtual bus regardless of guest privilege level.

Real x86 privilege rules can raise #GP for unauthorized port access.

Therefore user-mode protection around IN/OUT is not yet architecturally complete.

This is one of the highest-value correctness gaps in the current port-I/O path.

## No string I/O instructions

The inspected decoder implements scalar IN/OUT opcodes E4-E7 and EC-EF.

There is no ChrisVM execution path for x86 string I/O families such as INS and OUTS in this revision.

REP string-I/O semantics, DF interaction and interruptible repeated I/O are therefore absent.

The presence of STOS support elsewhere does not imply generic string-I/O support.

## No TSS I/O bitmap

ChrisArchitectureState reserves TR state, but the current exception/segmentation model does not provide a complete TSS.

Accordingly, the port-I/O path cannot consult a guest TSS I/O bitmap.

Implementing correct ring-3 IN/OUT permission requires both privilege logic and a usable task-state representation.

## I/O tracing asymmetry

do_io contains a trace hook for output when trace_io is enabled.

The inspected helper logs a generic "io out" line before chris_io_out.

The IN path does not contain equivalent logging in the same function.

Therefore trace_io is not yet a symmetric bus-transaction trace.

For debugging devices, logs should ideally include:

- direction;
- port;
- width;
- value/result;
- device owner.

## Failure propagation

A mapped device callback can return failure.

chris_io_in/chris_io_out propagate that status to do_io.

do_io then propagates failure into instruction execution.

If execution returns failure without another explicit exit/fault state, the interpreter can classify it as CHRIS_EXIT_EXCEPTION.

There is no dedicated guest hardware exception for an arbitrary virtual-device callback failure.

Device models should therefore define carefully which conditions are guest-visible and which are emulator-internal failures.

## Bus versus device semantics

The port bus should be understood as transport and routing.

It determines:

- which range owns a port;
- whether width is valid;
- which callback receives the transaction;
- fallback behavior for unmapped ports.

Device-specific register semantics belong to the callback.

Keeping that separation clear is important as ChrisVM adds more devices.

## Current tests

The main test suite includes guest code that:

- configures the serial loopback path;
- writes a byte;
- reads it back through IN;
- verifies the accumulator result;
- reads an unassigned port and expects 0xff;
- writes 0x01 to shutdown port and expects CHRIS_EXIT_SHUTDOWN.

These are valuable end-to-end bus tests.

They do not cover:

- 16-bit and 32-bit device-width semantics broadly;
- overlap behavior;
- slot exhaustion;
- null handlers;
- privilege enforcement;
- string I/O;
- callback failure behavior.

## Hardware-virtualization boundary

A future ChrisHV backend may need to intercept host VM exits for guest port I/O and route them into this same ChrisVM bus.

The logical bus contract should remain backend-independent.

That means VMX/SVM exit decoding should ultimately produce the same transaction description:

    port
    direction
    width
    value

rather than creating a second hardware-backend-specific device path.

This is another reason to strengthen the bus contract before ChrisHV becomes active.

## Hardening priorities

The highest-value port-I/O work is:

1. implement CPL/IOPL/TSS I/O-bitmap permission checks;
2. reject accidental overlapping port ranges;
3. define safe read-only/write-only registration semantics;
4. replace the fixed eight-slot limit or make it a deliberate machine-profile constraint;
5. add unregister/reset support if dynamic devices are required;
6. implement INS/OUTS and REP string-I/O semantics;
7. make trace_io symmetric and transaction-specific;
8. add tests for byte/word/dword forms with immediate and DX ports;
9. add slot-exhaustion and overlap tests;
10. define callback failure as guest fault, device condition or emulator error explicitly;
11. share the same bus transaction interface with future VMX/SVM I/O exits;
12. document and version built-in port assignments centrally.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, the ChrisVM port-I/O bus provides a small but functional scalar IN/OUT path with preserved access width, deterministic first-match routing, permissive unmapped-port behavior and working serial/shutdown devices. Its major compatibility gaps are missing x86 I/O privilege checks, fixed capacity, overlap ambiguity, absent string I/O and incomplete transaction tracing.
