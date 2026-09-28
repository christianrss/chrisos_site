---
id: page-faults
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/panic.c
symbols:
  - irq_dispatch
  - proc_fault_demand
  - proc_commit
  - proc_record_fault
  - panic_user_fault
  - panic_exception
  - mm_map_cr3
  - mm_flush_tlb
depends_on:
  - virtual-memory
  - page-table-layout
  - idt-exceptions
related:
  - address-spaces
  - user-mode-entry
  - process-lifecycle
  - user-copy
  - tlb
---

# Page faults: architectural semantics and ChrisOS recovery paths

## Scope

A page fault is the x86-64 exception raised when an attempted linear-memory access cannot be completed under the current paging rules. It is not synonymous with "page absent." The processor can raise vector 14 because a translation is missing, because a write violates protection, because user mode touches supervisor memory, because a reserved page-table encoding is encountered, or because an instruction fetch conflicts with execution permissions.

ChrisOS uses page faults for two different purposes:

1. **recoverable demand allocation** inside a small set of process-owned virtual regions;
2. **fault containment** when a user access cannot be recovered.

A page fault in kernel context that is not consumed by the demand path remains fatal and reaches the generic exception panic path.

The current implementation is deliberately small. It does not implement a general VM-area manager, copy-on-write, swap, file-backed paging, or a universal protection-fault recovery policy.

![Page-fault entry, demand allocation and containment paths](../../assets/diagrams/page-fault-flow-en.svg)

## Architectural inputs to a page-fault handler

Three pieces of state are particularly important.

### Vector

The architectural exception vector is 14.

ChrisOS installs a normal interrupt gate for all vectors during idt_init. Vector 14 points at isr14 from the generated stub table.

### CR2

When the processor raises #PF, CR2 contains the linear address whose access triggered the fault.

irq_dispatch explicitly reads CR2 before attempting recovery:

~~~text
#PF
 -> irq_dispatch
 -> read CR2
 -> proc_fault_demand(current_pid, cr2)
~~~

CR2 answers **where** the access failed. It does not by itself explain why.

### Error code

Unlike exceptions without a hardware error code, #PF pushes an architectural error value.

idt_stubs.asm classifies vector 14 with ISR_WITH_ERROR, so the stub does not synthesize a zero error value for this exception. The hardware-provided value remains in the irq_frame.error slot passed to C.

Common architectural fields include:

| Bit | Conventional meaning |
|---:|---|
| 0 | 0 = non-present translation; 1 = protection violation |
| 1 | 0 = read-like access; 1 = write |
| 2 | 0 = supervisor access; 1 = user access |
| 3 | reserved paging-structure bit violation |
| 4 | instruction fetch when the architecture reports it |
| higher bits | additional features on CPUs that implement them |

The exact set of high-order meanings depends on processor features. ChrisOS currently **does not decode these bits to select the recovery policy**. The error value is preserved in the interrupt frame and printed in the user-fault diagnostic, while proc_fault_demand makes its decision from the process state and CR2 address alone.

That implementation detail matters: the current demand path is address-driven rather than error-code-driven.

## Exception-stack normalization

The assembly layer normalizes exceptions so irq_dispatch receives one struct irq_frame layout.

For vectors without a hardware error code, ISR_NO_ERROR pushes a synthetic zero and then the vector number.

For vector 14, ISR_WITH_ERROR pushes only the vector number because the CPU already placed the error code on the exception stack.

After the general-purpose registers are pushed, the C-visible ordering includes:

~~~text
...
vector
error
rip
cs
rflags
...
~~~

When the exception crosses privilege levels, x86-64 also saves the user stack state required by IRETQ. Those additional privilege-transition fields are not represented explicitly in the current C irq_frame structure. The assembly stub owns the complete machine stack and eventually executes IRETQ.

This boundary is important when modifying fault-return behavior: the C structure is a convenient prefix of the return state, not a complete independent serialization of every possible hardware exception frame.

## First policy decision: try demand allocation

irq_dispatch gives proc_fault_demand the first opportunity to resolve every vector-14 fault.

The current call does not first check the error code for "not present," nor does it first test whether the fault originated in user mode. Instead, recovery succeeds if all of the following effectively hold:

- the current PID identifies a valid non-kernel process;
- the process exists and is still marked alive;
- CR2 falls inside one of the specific virtual ranges that proc_fault_demand recognizes;
- proc_commit can materialize the page.

If proc_fault_demand returns true, irq_dispatch returns immediately. The assembly stub restores state and IRETQ retries execution.

This makes page-fault recovery part of the process memory-allocation mechanism.

## Regions eligible for demand allocation

proc_fault_demand aligns CR2 down to a 4 KiB page boundary and checks four region classes.

### VM region

The VM region starts at PROC_VM_VIRT, currently 0x02000000.

proc_set_vm records vm_bytes and commits the first page immediately. Later page faults in:

~~~text
PROC_VM_VIRT <= page < PROC_VM_VIRT + vm_bytes
~~~

can allocate more pages lazily.

This is used by the language/VM pipeline as a bounded process memory arena.

### Stack window

The process subsystem recognizes:

~~~text
PROC_STACK_VIRT <= page < PROC_STACK_VIRT + 4 * 4096
~~~

with PROC_STACK_VIRT currently 0x07F00000.

proc_create commits the first page at PROC_STACK_VIRT.

This is a fixed four-page demand window. It is not a dynamically growing stack with guard-page relocation or an arbitrary maximum-stack policy.

A separate current ELF launch path passes 0x400FF8 to enter_user rather than PROC_STACK_VIRT, so this stack window is not yet a universal user ABI. That mismatch is documented more fully in the address-space chapter.

### Heap region

The process heap begins at PROC_HEAP_VIRT, currently 0x04000000.

proc_sbrk advances heap_brk, subject to a hard current cap of 256 KiB beyond the base. Physical pages are not allocated by proc_sbrk itself.

A fault is demand-eligible when:

~~~text
PROC_HEAP_VIRT <= page < heap_brk
~~~

Thus the logical heap boundary is advanced first, and physical commitment can occur later when the page is touched.

### Process framebuffer region

PROC_FB_VIRT is currently 0x06000000.

proc_fb_ptr records a process framebuffer-page count, capped at 16 pages, and currently commits the requested pages eagerly. proc_fault_demand nevertheless recognizes the recorded framebuffer interval too.

That makes the fault path robust to an absent page within the declared framebuffer region, although the normal proc_fb_ptr path already attempts commitment.

## What proc_commit actually does

Recovering a page fault is not merely writing a PTE.

proc_commit performs an ownership transaction across PMM, MM, and the process table:

1. validate PID and process state;
2. align the requested virtual address to 4 KiB;
3. return success if the process already records the page;
4. enforce the fixed PROC_PAGES ownership-array capacity;
5. allocate one physical frame from PMM;
6. obtain its HHDM alias;
7. zero the complete 4096-byte frame;
8. install a user, writable mapping through proc_map_user and mm_map_cr3;
9. if mapping fails, free the physical frame;
10. on success, append the virtual/physical pair to Proc.pages;
11. if this process is currently active, reload CR3 through mm_flush_tlb.

The zero-fill step prevents newly allocated user memory from exposing data that happened to remain in a recycled physical frame.

The current demand path maps pages with MM_PRESENT | MM_WRITE and proc_map_user adds MM_USER. It does not add MM_NX. Therefore demand-allocated VM/heap/stack/framebuffer pages are not currently expressed as non-executable by this path.

That is a present security limitation of the implementation, distinct from the ELF loader, which derives write and execute permissions from segment flags and rejects W+X load segments.

## Retry semantics

A successfully handled page fault normally returns to the same instruction address.

The handler does not advance RIP after proc_fault_demand succeeds.

That is correct for a missing-page recovery: the instruction that failed has not completed its memory operation, so after the required mapping exists the CPU must retry it.

This differs from some syscall paths in syscall_dispatch, which explicitly advance frame->rip after an INT-based syscall operation.

## Important limitation: recovery ignores the error-code cause

Because proc_fault_demand currently considers only CR2 and region membership, a fault inside a demand-eligible region can attempt proc_commit regardless of whether the architectural error code indicates non-presence or a protection violation.

If the page is already recorded in Proc.pages, proc_commit returns success immediately.

That means the present control flow does not explicitly distinguish:

~~~text
not-present page in a valid region
from
protection fault on an already-owned page
~~~

at the first recovery decision.

For normal demand allocation the expected case is a non-present page, but the policy is broader than that expectation.

A future stronger handler would normally inspect frame->error before deciding that page materialization is a valid recovery, and would route write, user/supervisor, NX, reserved-bit, or other protection faults according to their cause.

This chapter records the current implementation rather than silently assuming that stronger policy already exists.

## Unrecoverable user fault

If demand allocation does not resolve the exception, irq_dispatch examines the saved code-segment privilege:

~~~text
(frame->cs & 3) != 0
~~~

indicates a return context with nonzero requested privilege level, i.e. the current user-mode path.

panic_user_fault then performs containment rather than halting the entire OS.

Its sequence is:

1. obtain proc_current();
2. record PID, CR2, and fault RIP in the single global ProcFault record;
3. mark the process non-alive;
4. destroy the process if PID > 0;
5. log RIP, CR2, error code, CPU and build identity;
6. set the user exit code to -11;
7. rewrite the return frame toward the previously recorded kernel return point.

The name panic_user_fault is therefore historical/diagnostic in character: for a user process it does not call the global non-returning panic() function.

## Process destruction during a fault

proc_destroy first switches back to the kernel process if the dying PID is current.

Then it:

- clears and frees the process-owned user pages;
- destroys the user-half page-table hierarchy;
- closes syscall-owned files;
- closes process-owned sockets;
- marks the process slot free.

The important ordering is that leaf data frames are released through Proc.pages before mm_free_user_space recursively frees the remaining page-table pages.

Because proc_switch(PROC_KERNEL) writes the kernel CR3 before the dying process hierarchy is freed, the current CPU no longer depends on that PML4 for its active translation context.

Current user processes are restricted to the BSP, simplifying private user-space TLB lifetime.

## Returning to the kernel after a user fault

enter_user records a kernel return RIP before transitioning to ring 3.

panic_user_fault eventually calls syscall_return_to_kernel, which edits the saved frame:

- RIP becomes g_user_kernel_rip;
- CS becomes the kernel code selector;
- RFLAGS becomes 0x202;
- the user-exited flag is set.

The ISR assembly later executes IRETQ.

The current irq_frame C type models RIP, CS and RFLAGS but does not expose the privilege-transition RSP/SS fields as named C members. Therefore this return mechanism depends closely on the actual hardware/stub stack layout.

Any future redesign of exception frames, IST usage, or user-return conventions must review this path as an ABI-like dependency.

## Unrecoverable kernel fault

If demand handling fails and frame->cs indicates kernel privilege, irq_dispatch reaches the generic exception case.

For vector values below 32, panic_exception prints:

- vector;
- error code;
- RIP;
- CR2;
- CPU identity;
- CR3;
- RSP;
- build and source identity.

It disables interrupts and halts indefinitely.

There is currently no kernel page-fault recovery table, exception fixup mechanism, copy-from-user fault trampoline, or per-thread signal-like recovery.

This is why user_copy avoids directly dereferencing untrusted user virtual addresses in ring 0. It walks the process tables with mm_translate and copies through HHDM aliases instead. A missing user page returns an error from the copy helper instead of deliberately causing a kernel #PF.

## Fault containment boundary

The present system therefore has a simple containment model:

| Fault class | Current outcome |
|---|---|
| Eligible missing-like access in process demand region and commit succeeds | map page and retry |
| Demand-region access but commitment fails | falls through to user/kernel failure path |
| User fault outside recoverable path | record, destroy process, return to kernel |
| Kernel fault outside recoverable path | global panic/halt |

The handler does not currently classify processes by fault policy, deliver a signal, create a core dump, restart a task, or invoke a userspace pager.

## Memory exhaustion on a demand fault

proc_commit can fail because:

- Proc.pages has reached its fixed capacity;
- PMM cannot allocate a frame;
- mm_map_cr3 cannot construct the required page-table path.

proc_fault_demand converts any such failure into "not handled."

For a user-mode fault, the process is consequently terminated.

There is no OOM killer, reclaim operation, swap fallback, retry queue, or distinction between transient and permanent allocation failure.

## Fixed ownership capacity

PROC_PAGES is currently 288.

This array records every owned user page as a pair:

~~~text
virtual page -> physical frame
~~~

The limit affects page-fault recovery directly. Even if PMM still has free memory, a process whose ownership array is full cannot commit another page.

The bound also caps proc_set_vm to PROC_PAGES * 4096 bytes, although other mappings such as ELF pages also consume entries in the same ownership array. Therefore the practical aggregate mapped-page capacity is shared across the process's owned mapping classes.

This is a scalability constraint, but it makes teardown simple and deterministic.

## Concurrency model

Process scheduling state is currently global and user processes run only on the BSP.

proc_switch explicitly panics if called from an application processor.

That restriction means a private process address space is not expected to be concurrently active on several CPUs.

Page-table mutation still uses mm_lock, and proc_commit reloads the current CR3 after installing a page. Shared kernel translations remain a multiprocessor problem handled separately by the TLB protocol.

The fault path itself executes in interrupt/exception context. It must not assume that ordinary blocking or scheduler primitives are available.

## Security properties that are implemented

Several concrete protections exist:

- user pages are mapped with MM_USER;
- ELF mappings derive write and execute state from PT_LOAD flags;
- the ELF loader rejects writable-and-executable segments;
- fresh demand pages are zero-filled;
- user-copy checks mapping presence and user permission through a software walk;
- writes from the kernel through user-copy require MM_WRITE;
- unresolved user faults are contained to the process instead of automatically halting the kernel.

These properties are narrower than a production VM security model, but they are concrete and source-backed.

## Security properties not yet encoded in the demand path

Demand-allocated pages are currently created writable and without MM_NX.

The fault policy does not decode error bits before attempting recovery.

There are no guard-page objects, stack-execution policy, per-region permission descriptors, copy-on-write states, dirty tracking policy, or VMA protection transitions.

A future region descriptor model could associate every interval with permitted fault types and target leaf permissions instead of deriving all recovery from hard-coded address comparisons.

## Complexity

The region classification in proc_fault_demand is O(1): four fixed interval checks.

page_owned and proc_commit ownership checks are O(n) in the number of recorded process pages because Proc.pages is a linear array.

At the current maximum n = 288, the bound is small and deterministic.

The page-table insertion itself has fixed four-level depth, so it is O(1) with respect to virtual-address-space size.

Zeroing a new frame costs O(4096) byte stores, which is constant under the fixed 4 KiB page size but materially larger than the metadata checks.

## Validation evidence

The repository contains source-level and documentation gates that exercise memory-management contracts, and existing MM tests validate 4 KiB mapping coherence.

The current page-fault behavior is also structurally testable through:

- vector-14 stub classification as an error-code exception;
- CR2 capture in irq_dispatch;
- demand-page commitment logic;
- process-fault recording;
- user process teardown paths.

However, the documentation build passing does not demonstrate every runtime #PF case.

Important missing or non-exhaustive evidence includes:

- deliberate tests for every architectural error-code combination;
- NX execution faults in each region;
- write-protection faults on read-only ELF pages;
- reserved-bit faults;
- OOM at each intermediate page-table allocation stage;
- nested page faults while already handling a fault;
- exhaustive exception-return validation after user-process destruction.

These remain useful targets for dedicated runtime gates.

## Current limitations

At the reviewed revision, the page-fault subsystem does not provide:

- a VMA tree or interval map;
- error-code-directed demand policy;
- copy-on-write;
- file-backed page-in;
- swap;
- page replacement;
- per-process exception delivery;
- signals;
- userspace pagers;
- stack guard-page movement;
- kernel exception fixups;
- OOM recovery;
- generalized executable/non-executable policy for demand pages.

The current design is a compact experimental mechanism connecting processor exceptions directly to a small process-memory model.

## Revision boundary

This chapter was reconciled against ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The current facts are the vector-14 stub behavior, CR2 capture, fixed-region demand policy, proc_commit implementation, user-fault containment, process destruction path and kernel-panic fallback present in the declared sources.

Future plans for richer paging or process isolation must remain explicitly separate until their source implementation exists.
