---
id: chrisvm-machine
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/config.c
  - chrisvm/machine/boot.c
  - chrisvm/buses/io.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
symbols:
  - ChrisMachine
  - ChrisConfig
  - ChrisCpu
  - chris_machine_create
  - chris_machine_destroy
  - chris_run
  - chris_backend_by_name
  - chris_phys_read
  - chris_phys_write
depends_on:
  - chris-architecture-state
  - chrisvm-chriscpu
related:
  - chrisvm-memory-map
  - chrisvm-io-bus
  - chrisvm-mmio-bus
  - chrisvm-devices
  - chrisvm-boot
---

# ChrisMachine: ownership, lifecycle and platform boundaries

## Scope

ChrisMachine is the top-level runtime container for the current ChrisVM platform. It owns the objects that make a guest executable as a machine rather than merely as an instruction stream: RAM, CPU backend selection, one CPU instance, I/O and MMIO registrations, serial state, framebuffer state, boot/shutdown state, configuration and logging callbacks.

The structure is intentionally small. It is not a PC chipset model and does not yet contain mature PCI, APIC/IOAPIC, timer, storage, network or SMP platform state. Those systems belong to later machine/device layers.

The important design principle is ownership:

    ChrisMachine
      owns platform memory and device state
      selects a ChrisCpuBackend
      owns one backend CPU instance
      exposes lifecycle and host-facing APIs

This chapter documents the implementation at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Public configuration

ChrisConfig currently contains:

- ram_size;
- backend;
- trace;
- trace_memory;
- trace_io;
- trace_mmio;
- deterministic;
- max_steps;
- break_rip;
- has_break;
- debug;
- headless;
- fb_dump.

chris_config_init clears the structure and establishes these defaults:

    RAM          = 16 MiB
    backend      = "chriscpu"
    deterministic = 1
    max_steps    = 1,000,000

The other fields begin at zero/null.

A null configuration passed to chris_machine_create causes a local default configuration to be created automatically.

## Command-line configuration

chris_config_from_args recognizes:

- --trace;
- --trace-memory;
- --trace-io;
- --trace-mmio;
- --deterministic;
- --debug;
- --headless;
- --backend;
- --break;
- --fb-dump;
- --max-steps.

Unknown switches and extra positional arguments are rejected.

The parser requires one guest ELF path.

An important current limitation is that deterministic already defaults to one and the parser only offers a switch that sets it to one again. The inspected runtime has no branch that changes execution behavior based on cfg.deterministic.

Therefore the configuration field expresses project intent, but the flag is not currently a functional mode selector.

## Core ChrisMachine fields

ChrisMachine contains:

| Field | Role |
|---|---|
| cfg | copied machine configuration |
| ram | host allocation backing guest RAM |
| ram_size | guest RAM size |
| io[8] | port-I/O mapping table |
| mmio[8] | MMIO mapping table |
| serial | built-in serial device state |
| fb | built-in framebuffer state |
| cpu | single CPU object |
| backend | selected ChrisCpuBackend |
| entry | loaded guest entry point |
| booted | guest boot state |
| shutdown | machine shutdown request |
| log/log_ctx | optional host logging callback |

The machine currently owns exactly one ChrisCpu pointer. create_cpu is invoked with CPU ID zero.

This is a uniprocessor platform model. Supporting SMP requires more than allowing cpu_id values: ChrisMachine itself must become capable of owning and scheduling multiple CPU instances and routing interrupts among them.

## Fixed-capacity registries

The internal machine header defines:

    CHRIS_IO_MAX   = 8
    CHRIS_MMIO_MAX = 8

Both bus registries are fixed arrays embedded directly in ChrisMachine.

Registration consumes the first unused slot. There is no dynamic growth and no unregister operation.

This is appropriate for a bring-up machine with very few devices, but it becomes a platform limit as soon as multiple PCI-like functions, timers, interrupt controllers and virtio devices are introduced.

## Machine creation: validation

chris_machine_create first validates RAM.

The requested size must be:

- at least 2 MiB;
- aligned to a 2 MiB boundary.

A size below the minimum or one with low 21 address bits set is rejected.

That validation corresponds to the current boot protocol, which identity-maps initial RAM with 2 MiB pages.

However, this is not the final effective RAM constraint.

## Effective 32 MiB RAM ceiling

The framebuffer is fixed at:

    CHRIS_FB_PHYS = 0x02000000

which is 32 MiB.

chris_fb_attach rejects a machine when:

    ram_size > CHRIS_FB_PHYS

Therefore the current machine can only be created with RAM up to 32 MiB, despite chris_machine_create's earlier validation accepting any aligned size above 2 MiB.

This is a concrete platform constraint.

The paging boot code can conceptually generate identity mappings for much larger RAM, up to one PD worth in the current layout, but machine creation is stopped earlier by the framebuffer placement rule.

A future memory map should make device placement independent of such an implicit maximum or allocate framebuffer/MMIO address space above configurable RAM.

## Backend selection

chris_backend_by_name currently recognizes:

- null or "chriscpu";
- "chrishv".

Any other backend name returns null.

The default is ChrisCPU.

ChrisHV exists in the registry but its init callback fails in the inspected revision, so selecting it causes machine creation to fail.

This means backend discovery and machine ownership are already generalized, while only the interpreter backend is operational.

## Creation lifecycle

Successful chris_machine_create follows this order:

1. allocate zeroed ChrisMachine;
2. copy configuration;
3. choose the backend;
4. call backend->init(machine);
5. allocate zeroed RAM;
6. attach serial/shutdown-port mappings;
7. attach framebuffer;
8. call backend->create_cpu(machine, 0);
9. return the machine.

The ordering matters because each later stage assumes earlier machine resources are valid.

The zero-initialized ChrisMachine also means all I/O/MMIO mapping slots begin unused without an explicit registry initializer.

## Failure cleanup

The function contains cleanup for several allocation failures.

If RAM allocation fails, the machine object is freed.

If framebuffer creation fails, RAM and the machine are freed.

If CPU creation fails, framebuffer pixels, RAM and the machine are freed.

This is sufficient for the current ChrisCPU backend because backend init has no persistent machine-owned resources before CPU creation.

For a future backend whose init allocates host virtualization resources, the lifecycle contract is incomplete: failure after successful backend->init does not call a backend-level teardown hook unless a CPU exists and normal machine destruction is reached.

A robust backend lifecycle should either make init side-effect free, add machine-backend cleanup, or route every partial-construction failure through a common destroy path.

## RAM ownership

Guest RAM is a single host allocation:

    calloc(1, ram_size)

It is therefore initially zero-filled.

The machine owns the allocation and frees it during destruction.

chris_write_ram and chris_read_ram are public wrappers over chris_phys_write and chris_phys_read rather than raw memcpy operations.

That means the public "RAM" functions actually pass through the complete physical-address routing layer and can access other mapped physical regions if the supplied address falls outside RAM.

The naming is therefore slightly broader in behavior than it appears.

## Framebuffer ownership

chris_fb_attach creates a built-in framebuffer with:

    base   = 0x02000000
    width  = 640
    height = 480
    pitch  = width * 4
    size   = pitch * height

Pixels are stored in a separate host allocation rather than inside the RAM array.

Physical reads/writes route framebuffer addresses to this allocation.

Writes mark fb.dirty.

Host APIs can:

- read an individual pixel;
- query dirty state;
- write the image as PNG or PPM;
- display it through the viewer layer.

The framebuffer's fixed address is the cause of the current 32 MiB RAM ceiling.

## Serial ownership

ChrisMachine embeds a ChrisSerial structure rather than allocating it separately.

chris_serial_attach clears the state and registers two port-I/O ranges:

    0x3f8..0x3ff  serial device
    0x501         shutdown port

The serial state includes UART-like register storage, loopback state, a fixed transmission buffer and an optional host callback.

The transmit buffer capacity is:

    CHRIS_TX_MAX = 8192

The model is intentionally small and does not reproduce complete UART timing, FIFOs or interrupt behavior.

## Shutdown port

A write with low byte 0x01 to port 0x501 sets:

    machine->shutdown = 1

and, when a CPU exists:

    exit_reason = CHRIS_EXIT_SHUTDOWN
    halted = 1

This is a project-specific virtual platform convention used for deterministic guest shutdown.

It is not a standard PC firmware or ACPI power-control interface.

## Port-I/O registry

Each ChrisIoSlot contains:

- used;
- start/end port;
- input callback;
- output callback;
- opaque context pointer.

chris_io_map validates only that the machine exists and start <= end.

It does not check for overlap with existing ranges.

find_io scans from slot zero upward and returns the first matching registration.

Therefore overlapping port ranges are legal in the current data structure, and registration order determines which device wins.

That behavior should be treated as a gap. A machine definition should reject unintended overlap or make priority explicit.

## Unknown port behavior

For an unmapped IN:

- byte read returns 0xff;
- word read returns 0xffff;
- dword read returns 0xffffffff.

For an unmapped OUT, the write is silently ignored.

This makes unknown legacy probing relatively tolerant and is a common emulator-style policy.

It is nevertheless part of the virtual platform contract because guest drivers can observe it.

## MMIO registry

ChrisMmioSlot contains:

- used;
- base;
- size;
- read callback;
- write callback;
- context.

Like port I/O, MMIO registration uses the first free slot and does not reject overlap.

chris_mmio_find scans from slot zero and returns the first matching region.

Again, registration order becomes hidden priority when address ranges overlap.

There is no interval tree, dynamic map or region removal.

## Physical address routing

chris_phys_read and chris_phys_write implement the machine's physical address-space dispatcher.

The lookup precedence is:

1. RAM;
2. framebuffer;
3. generic MMIO.

If the complete requested range fits within RAM, the access uses memcpy.

If it fits completely within the framebuffer, the access uses the framebuffer allocation.

Otherwise the generic MMIO path attempts to resolve each byte individually.

This precedence is important. An MMIO registration overlapping an address inside RAM will never receive accesses while the whole request fits in RAM.

Likewise, framebuffer takes priority over generic MMIO for its own range.

## Mixed-region physical access gap

The fast paths require the entire requested range to fit in RAM or the framebuffer.

Consider a multi-byte physical access beginning in the final bytes of RAM and extending into an MMIO region immediately afterward.

The RAM fast path fails because the complete range is not inside RAM.

The code then enters generic MMIO handling for every byte, including the first address that still belongs to RAM.

Unless an MMIO slot is also registered over that RAM byte, the operation fails.

Therefore the current physical layer does not decompose one request across heterogeneous adjacent regions.

The same issue exists for other region-boundary crossings.

A general memory-map implementation should split access at region boundaries and route each chunk to the appropriate owner, while still preserving the guest architecture's atomicity/fault semantics.

## Generic MMIO is byte-serialized

When an access reaches the generic MMIO path, chris_phys_read/chris_phys_write iterate one byte at a time.

The device callback is invoked with:

    size = 1

for every byte.

That means a guest 32-bit or 64-bit physical access is not delivered to the generic MMIO device as one width-aware transaction.

For simple byte-addressable test devices this works.

For real device models, access width can be semantically significant. Some registers reject byte writes, latch on dword access or implement read side effects once per transaction.

The current byte serialization is therefore a platform limitation.

## MMIO callback validation

chris_mmio_map accepts callback pointers without checking them for null.

Similarly, chris_io_map does not require both handlers to exist.

Internal devices provide valid callbacks, but the generic registration API can create a slot whose later access dereferences a missing handler.

A hardened registration contract should either permit absent directions explicitly and handle them safely, or reject invalid callback combinations at registration time.

## Boot ownership boundary

Machine creation does not boot the guest.

chris_load_elf copies accepted load segments into the machine's memory and records the entry point.

chris_boot separately:

- builds initial paging structures;
- builds the initial GDT;
- constructs ChrisArchitectureState;
- chooses RIP/RSP;
- sends state to the CPU backend;
- marks machine->booted.

This separation is useful because machine construction, image loading and CPU reset state are distinct operations.

## Run contract

chris_run rejects execution if:

- machine is null;
- CPU is absent;
- machine has not been booted.

If machine->shutdown is already set, it returns CHRIS_EXIT_SHUTDOWN without entering the backend.

Otherwise it calls:

    backend->run(cpu, max_steps)

The max_steps argument is therefore the immediate execution budget.

ChrisConfig also contains max_steps, but chris_run itself does not substitute cfg.max_steps when the caller passes another value. The frontend is responsible for choosing the configured budget.

## Single-CPU ownership

ChrisMachine stores:

    ChrisCpu *cpu

not an array or collection.

The backend create callback receives CPU ID zero, but no additional IDs are instantiated.

This is a deliberate current limit.

Adding SMP requires changes to:

- machine ownership;
- run scheduling;
- interrupt routing;
- APIC/IOAPIC state;
- per-CPU architectural/runtime state;
- shared-memory ordering;
- device interrupt targeting;
- debugger APIs.

The existing cpu_id parameter is only a seam, not SMP support.

## Destruction lifecycle

chris_machine_destroy performs:

1. backend->shutdown(cpu), when CPU/backend exist;
2. free(cpu);
3. free(framebuffer pixels);
4. free(RAM);
5. free(machine).

The current ChrisCPU creates its CPU with calloc, so generic free is correct.

For future backends, this contract means either the CPU object itself must remain heap-compatible with free or shutdown must not deallocate that outer object.

A cleaner backend abstraction could provide destroy_cpu rather than combining a shutdown callback with unconditional generic free.

## Logging

ChrisMachine stores one optional log callback plus context.

chris_set_log installs it.

Interpreter trace paths route messages through the machine logging layer.

Logging is host control state, not guest architectural state.

A snapshot of the guest does not need to preserve the host callback pointer, and a serialized machine format must never treat such process-local pointers as portable VM state.

## Breakpoint and trace ownership

Trace flags and breakpoint information are copied from ChrisConfig into ChrisCpu at CPU creation.

Therefore some host-debug configuration begins at the machine level but becomes backend CPU runtime state.

This division is acceptable for the current single-backend implementation, but a general debugger interface should define clearly which configuration belongs to the machine and which belongs to each virtual CPU.

## Deterministic configuration is not yet an execution switch

cfg.deterministic defaults to one and can be set from the command line.

The inspected machine, interpreter and device source contains no branch consuming that field to change behavior.

Some individual components are deterministic by construction, such as virtual CPUID and instruction-count-like TSC progression, but that is independent of the config switch.

The future determinism/replay layer should either make this field operational or remove the appearance of a selectable mode.

## Current tests and evidence

test_chrisvm.c exercises machine-level behavior including:

- default machine creation;
- RAM loading;
- boot and run;
- serial I/O and loopback;
- shutdown port;
- unmapped I/O;
- MMIO registration and physical routing;
- framebuffer writes;
- ELF rejection;
- exception exits;
- backend rejection for ChrisHV.

The tests demonstrate that the compact machine is sufficient for current standalone guests and framebuffer/serial smoke workloads.

They do not establish compatibility with a complete PC platform.

## Current platform boundaries

At the inspected revision, ChrisMachine does not provide a mature implementation of:

- SMP;
- local APIC/IOAPIC routing;
- PIT/HPET-style platform timing;
- PCI/PCIe enumeration;
- mature virtio devices;
- disk controller platform;
- network platform;
- ACPI machine tables;
- firmware execution;
- hotplug;
- dynamic memory regions;
- general device-tree/chipset modeling.

These are not omissions from the C container alone; each requires explicit virtual hardware contracts.

## Hardening priorities

The highest-value machine-layer improvements are:

1. remove the implicit 32 MiB RAM ceiling by designing a real physical memory map;
2. replace fixed eight-slot I/O/MMIO arrays or enforce a deliberate platform capacity;
3. reject unintended overlapping I/O and MMIO registrations;
4. split cross-region physical accesses at region boundaries;
5. preserve original access width for MMIO callbacks;
6. validate null/unsupported device callbacks safely;
7. add backend cleanup for partial machine-creation failures;
8. replace unconditional free(cpu) with a backend destroy_cpu contract;
9. make deterministic mode semantically meaningful;
10. define multi-CPU ownership before adding APIC/SMP;
11. separate process-local host callbacks from serializable machine state;
12. add a generated machine-map description so RAM, framebuffer and future devices cannot collide silently.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisMachine is a compact and coherent ownership container for the current ChrisCPU-based virtual platform. It successfully ties together RAM, one CPU, serial, shutdown I/O, framebuffer and test MMIO. Its main structural constraints are the fixed framebuffer-induced 32 MiB RAM ceiling, fixed bus registries, first-match overlap behavior, byte-serialized generic MMIO and lack of mixed-region physical access splitting. These limits define the next platform work before ChrisVM can evolve from a focused execution harness into a broader replacement for QEMU-style machine support.
