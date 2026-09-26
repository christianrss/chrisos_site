---
id: processes-syscalls
lang: en
type: technical-chapter
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
depends_on:
  - virtual-memory
  - kernel-model
related:
  - elf-linking
---

# Processes, address spaces and system calls

## Process abstraction

A process groups an execution identity with resources and an address space. Different operating systems choose different exact contents, but isolation normally requires at least a protected virtual-memory context and controlled entry into the kernel.

ChrisOS `Proc` records state such as usage/aliveness, process state, CR3, committed memory accounting, heap break, name and owned page records.

## Creating an address space

`proc_create` searches for a free process slot and calls `mm_clone_kernel_space`. The new CR3 receives the kernel mappings needed for privileged execution while permitting a distinct user portion.

A user stack is committed before process creation returns successfully. If later initialization fails, destruction is used to unwind the partially created process.

This is an ownership principle: allocation sequences require a cleanup path for every successfully acquired resource.

## Mapping ownership

Mapping a physical page and owning it are different concepts. A page can be mapped in several places, and unmapping an address does not automatically establish who should free the underlying frame.

ChrisOS therefore tracks user leaf frames in the process page array. `proc_map_owned` records virtual and physical addresses after a successful mapping. `proc_destroy` can later unmap and return those frames.

## Switching CR3

A process switch changes the active page-table root. `proc_switch` updates global process identity and calls `mm_switch` for the selected CR3.

Current implementation has an explicit invariant: user process switching is BSP-only. Calling it on an AP panics. This is an architectural limitation, not merely a missing optimization.

## User and kernel pointers

A pointer supplied by ring-3 code is not automatically safe for the kernel to dereference. It can be outside the allowed user range, unmapped, non-user-accessible, cross a page boundary or refer to a page without required write permission.

ChrisOS syscall code therefore translates and validates user spans page by page through `user_copy`. It accesses the physical page via the kernel's direct-map path instead of letting an arbitrary user address fault while kernel code blindly dereferences it.

## System calls

A system call is a controlled transition from less privileged code into a kernel service. Its design includes:

- entry mechanism;
- syscall number and argument ABI;
- validation;
- ownership/permission checks;
- result/error convention;
- return to user mode.

The specific instruction used for transition is only one part of the interface.

## File descriptors and ownership

ChrisOS native syscall code associates user-file slots with an owner process. Process teardown calls `syscall_close_owner`. This prevents a resource from remaining indefinitely attached to a process identity after the address space has been destroyed.

The same ownership pattern appears in sockets and other process-scoped resources.

## Fault containment

`proc_record_fault` records PID, thread identifier, CR2 and RIP and marks the affected process not alive. The intent is to contain a user failure rather than immediately convert every process fault into a kernel panic.

Containment depends on the fault really occurring in a user context and on kernel data structures remaining trustworthy.

## Scheduler scope

A timer can mark that a slice is due, but the existence of a tick flag is not equivalent to a production preemptive multiprocessor scheduler. Scheduler maturity should be documented through the actual process states, switch paths, CPU restrictions and tests.

## Native processes versus CLVM

ChrisOS has two distinct execution contracts. Native ELF processes use page tables and ring transitions. ChrisC applications execute through CLVM slots and a VM syscall interface.

They should not be conflated merely because both are "programs." Their memory models, fault handling and kernel interfaces differ.
