---
id: user-copy
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/bootinfo.c
symbols:
  - user_span_ok
  - user_copy
  - copy_to_user
  - copy_from_user
  - mm_translate
  - proc_cr3
depends_on:
  - virtual-memory
  - user-mode-entry
related:
  - processes-syscalls
  - page-faults
---

# Safe user-memory access

## Scope

A user pointer is data supplied by an untrusted address space. Kernel code cannot safely cast it to a normal C pointer and dereference it merely because the numeric address looks plausible. The mapping can be absent, supervisor-only, read-only, cross a page boundary, change relative to process lifetime, or point at an address whose direct kernel dereference would fault while the kernel is executing with elevated privilege.

ChrisOS handles syscall buffer access with an explicit copy path in `syscall.c`. The path validates the declared user range, walks the current process page tables through `mm_translate`, checks page permissions and accesses the underlying physical frame through the kernel's physical-to-virtual mapping. Missing pages return an error rather than being demand-faulted from inside the ring-0 copy operation.

This chapter documents the complete contract and the reasons for every stage.

## Threat model

For a syscall such as write or file I/O, the kernel receives an integer that user code intends as an address. The kernel must assume that the value can be:
- outside the process's intended ABI range;
- noncanonical;
- close enough to the canonical boundary that length arithmetic overflows;
- mapped as supervisor-only;
- mapped read-only while the operation intends to write;
- split across multiple pages with different permissions;
- unmapped;
- stale relative to process teardown.

A correct copy primitive treats each page independently and proves that the complete span satisfies the operation.

## Declared user span

The syscall layer keeps `g_user_map_lo` and `g_user_map_hi`. Their initial values are `0x400000` and `0x500000`. `syscall_set_user_map` can replace them.

`user_span_ok(uaddr, n)` first accepts a zero-length operation. For nonzero spans it requires the start to remain below `0x0000800000000000`, which is the lower-half canonical boundary used by the current design.

It also checks the length before addition:

```text
n <= 0x0000800000000000 - uaddr
```

This form avoids computing `uaddr + n` first and then discovering that unsigned arithmetic wrapped.

The function then requires:
- `uaddr >= g_user_map_lo`;
- `uaddr < g_user_map_hi`;
- `n <= g_user_map_hi - uaddr`.

The final subtraction-based test again avoids overflow.

These checks constrain the syscall ABI's permitted buffer window. They do not prove page presence or page permissions. That is the next stage.

## Why range checks alone are insufficient

Suppose a buffer begins at a legal address and fits entirely inside the declared user range. It could still cross from a present user page into an unmapped page. Or the second page could be mapped supervisor-only. A single arithmetic range check has no knowledge of page tables.

Conversely, a virtual address may translate to a physical frame but still be inappropriate for the requested operation because the PTE lacks `MM_USER` or `MM_WRITE`.

ChrisOS therefore combines virtual-range validation with translation and flag validation.

## Selecting the address space

`user_copy` obtains `proc_cr3(proc_current())`. A zero CR3 is rejected.

This is a key ownership rule: translation is not performed against whichever address space happens to be convenient. It is performed against the CR3 recorded for the current process.

The current architecture restricts process switching and user syscall execution to the BSP, which simplifies the meaning of `proc_current()`. If userspace later runs concurrently on multiple CPUs, “current process” must become CPU-local or thread-local state.

## Page-by-page translation

The function maintains a byte count `done`. On every iteration it forms `addr = uaddr + done` and asks:

```c
mm_translate(cr3, addr, &phys, &flags)
```

Failure immediately returns -1.

It then requires `MM_PRESENT` and `MM_USER`. For a kernel-to-user copy it additionally requires `MM_WRITE`.

This asymmetry is correct. Reading from a user mapping only needs a readable/present user page under the current page-table model. Writing into user memory must not bypass the PTE's write-protection rule.

## Crossing page boundaries

After translation, `user_copy` computes:
- page offset = low bits of the current virtual address;
- remaining bytes in this page = page size - page offset;
- chunk = minimum of page remainder and total bytes still needed.

It copies that chunk and repeats. Therefore a buffer can span any number of pages, and every page receives its own translation and permission check.

This prevents a common bug in which only the first page is validated and a long buffer silently crosses into a privileged or unmapped page.

## Physical access through the kernel mapping

`mm_translate` returns the physical address corresponding to the current virtual address. `user_copy` converts it to a kernel-accessible virtual pointer using `bootinfo_phys_to_virt(phys)`.

The copy loops over bytes through that kernel mapping rather than directly dereferencing `uaddr`.

The intent is explicit in the source comment: “Copy through the HHDM of pages that are present in this process. A missing page returns an error instead of faulting in ring 0.”

This protects the kernel from taking a normal page fault simply because a syscall passed a missing user page. The syscall path chooses an error result rather than relying on fault recovery from a privileged copy.

## Interaction with demand paging

The process page-fault handler can demand-commit VM, stack, heap and framebuffer pages when a user instruction faults. `user_copy` deliberately does not invoke `proc_fault_demand`.

This creates two different policies:
- user execution may fault naturally, be validated as a legal lazy region and retry after allocation;
- kernel syscall copying requires pages to be present and returns error if they are not.

The distinction avoids page allocation in the middle of a copy primitive and reduces the complexity of recovering a kernel-mode fault. It also means a user program must ensure a syscall buffer is resident by touching or otherwise committing it before the syscall.

## Copy direction

The internal function takes `to_user`:
- false: physical/user page → kernel buffer;
- true: kernel buffer → physical/user page.

`copy_from_user` wraps the first case. `copy_to_user` wraps the second.

The kernel buffer itself is trusted kernel memory supplied by the syscall implementation. The primitive does not allocate it and does not infer its size; the caller provides the exact byte count.

## SYS_WRITE example

`SYS_WRITE` accepts only file descriptor 1 and at most 80 bytes. It allocates a local 81-byte array.

The extra byte is deliberate. After copying `n` bytes, `syscall_write_term` writes a NUL at `buf[n]`. Earlier code with an 80-byte array would overflow when `n == 80`. The source contains a comment preserving that bug history.

The sequence is:
1. validate fd and length;
2. copy from user;
3. append terminator with capacity-aware helper;
4. print to serial;
5. return byte count.

Even a trivial console write therefore does not directly pass the user pointer to `serial_puts`.

## File-read example

`SYS_FREAD` validates a process-owned descriptor and caps the request at 512 bytes. The filesystem writes into a local kernel buffer. Only after `fs_read` returns a nonnegative byte count does the kernel call `copy_to_user` for exactly that many bytes.

If destination user pages are missing, supervisor-only or read-only, the syscall returns -1 rather than letting the filesystem layer write through an unsafe pointer.

This separation keeps the filesystem API operating on kernel buffers and concentrates privilege-boundary checks in one layer.

## File-write example

`SYS_FWRITE` caps size at 512 and first copies user data into a kernel buffer. Descriptor ownership is then checked for normal files; fd 1 is handled as serial output.

This “copy then act” model means lower filesystem code does not need to understand user page tables. It also prevents the filesystem operation from observing a user buffer that changes while it is being consumed one byte at a time by an arbitrary lower layer.

It is not a complete defense against all time-of-check/time-of-use concerns in shared-memory designs, but it creates a stable kernel snapshot for this syscall.

## File paths

`SYS_FOPEN` copies up to `UPATH_MAX - 1` bytes from user space into a fixed 128-byte kernel path buffer, then forces the last byte to NUL and scans to the first terminator.

The copy primitive itself treats the requested length literally; it does not stop at NUL. String semantics belong to the caller after the boundary copy.

This is a useful layering rule: `user_copy` is a byte-span primitive, not a C-string primitive.

## Canonicality and lower-half policy

The threshold `0x0000800000000000` corresponds to the transition out of the conventional lower canonical half for 48-bit virtual addressing. The current code rejects any buffer beginning at or extending beyond that threshold.

The architecture may support wider canonical addressing on systems with LA57, but the ChrisOS reviewed virtual-memory model uses this lower-half boundary. Documentation must describe the implemented policy rather than assuming every x86-64 paging extension is enabled.

## Permission interpretation

`MM_PRESENT`, `MM_USER` and `MM_WRITE` are the flags the translation layer exposes for this policy. A user copy must not infer access rights solely from the requested virtual region.

The write check is especially important for executable or shared read-only mappings. A kernel that writes through a read-only user PTE merely because it has ring-0 privilege would violate the process's own memory-protection contract and could bypass intended immutability.

## Fault containment

Because the copy walks page tables before accessing each chunk through kernel mapping, expected bad user pointers become ordinary syscall error returns rather than kernel exceptions.

This does not guarantee the copy path can never fault: corrupted page tables, invalid HHDM mappings or bugs in `mm_translate` can still be kernel failures. The property is narrower and important: user-controlled absence/permission failures are checked before the memory access.

## Process teardown

`proc_destroy` can release owned pages and free the user address space. In the current BSP-only user/syscall model, the syscall copying a current process buffer is not racing a separate CPU executing process teardown for the same task.

If the architecture later permits concurrent process destruction, the copy path will require a lifetime reference or lock that prevents page-table and physical-frame reclamation during translation/copy.

This is why the current concurrency restriction is part of memory-safety reasoning rather than merely a scheduler limitation.

## Side-channel and speculative considerations

The reviewed code implements architectural permission validation. It does not claim hardened user-copy machinery comparable to mature kernels with exception tables, speculative-execution barriers, SMAP toggling, hardened accessors or fault-recoverable assembly copies.

Those mechanisms solve additional threat models. Their absence should be recorded as a limitation rather than silently implied by the phrase “safe copy”.

## Performance

The current implementation translates every page and copies byte-by-byte. This is straightforward and auditable but not optimized for throughput.

For small syscall limits—80-byte console writes and 512-byte file operations—the overhead is bounded. A future large-I/O path would benefit from page-granular bulk copies, validated iovecs, pinning or more efficient primitives.

Optimization must preserve the rule that every crossed page is independently authorized.

## Validation

Tests should cover:
- zero length;
- exact lower/upper boundary;
- arithmetic overflow attempts;
- one-page buffer;
- buffer crossing two or more valid pages;
- second page missing;
- supervisor-only page;
- read-only destination during copy-to-user;
- process with invalid CR3;
- maximum 80-byte console write with terminator;
- 512-byte file I/O limit;
- process destruction/descriptor cleanup behavior.

The complete implementation is available through the Source Atlas, so a validation gate can be tied to the exact revision.

## Current limitations

The permitted span is one global low/high pair rather than a full VM-area lookup. Copy is byte-oriented. Missing pages return error instead of faulting them in. There is no SMAP-aware temporary access scheme, exception-table recovery or concurrent teardown reference counting.

Within the current process model, however, the implementation enforces the crucial invariants: canonical/range validation, current-CR3 translation, per-page presence/user checks and write-permission checks before kernel-to-user modification.

## Source map

The boundary implementation is in `kernel/metal/syscall.c`. Current process CR3 comes from `kernel/metal/proc.c`. Page translation and flag definitions belong to `kernel/metal/mm.c`/`mm.h`. Physical-to-kernel addressing comes through `kernel/metal/bootinfo.c`. The Source Atlas contains the complete reviewed sources at `da3df29cb397932c43d32373871fb9380e688ade`.
