---
id: parallel-raster
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/job.c
  - kernel/metal/job.h
  - kernel/gfx/tile.c
  - kernel/gfx/tile.h
  - kernel/gfx/tri_bin.c
  - kernel/gfx/tri_bin.h
  - kernel/gfx/scene.c
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - tools/job_host_stub.c
  - tools/job_host_stub.h
  - tools/test_tile.c
  - tools/test_tile_bin.c
  - tools/test_job_saturate.c
  - tools/test_scene.c
symbols:
  - job_submit
  - job_worker_once
  - job_worker_forever
  - job_wait_idle
  - tile_parallel_clear
  - tile_mesh_raster
  - tri_bin_reset
  - tri_bin_add
  - scene_draw
depends_on:
  - software-3d
  - kernel-jobs-kthreads
related:
  - triangle-rasterization
  - depth-buffer
  - virtio-gpu-virgl
---

# Parallel software rasterization

## Scope

ChrisOS parallelizes selected graphics work through the kernel job queue rather than through a dedicated graphics scheduler.

Two current patterns are important:

1. spatially disjoint framebuffer bands or tiles, where workers own different pixels;
2. triangle/tile jobs, where multiple triangles can target the same tile and therefore potentially the same depth/color cells.

The distinction determines whether ordinary non-atomic framebuffer and z-buffer operations are sufficient.

Parallel rasterization in the current source is therefore not one uniform algorithm. It is a set of scheduling strategies built around `job_submit`, clip rectangles and fixed-capacity work descriptions.

## Job-system foundation

The kernel job queue lives in `kernel/metal/job.c`.

A job contains:

```text
JobFn fn
void *arg
```

and `JobFn` receives the argument plus the CPU index executing the work.

The queue has:

```text
JOB_QUEUE_CAP = 1024
```

entries.

Queue head, tail and count are protected by a spinlock.

## Submission semantics

`job_submit` rejects a null function.

Under the queue lock, it also rejects submission when the queue count already equals 1024.

A successful submission:

- stores function and argument;
- advances the circular tail;
- increments queue count;
- atomically increments `g_inflight`;
- returns 1.

A full queue returns 0.

This return value is part of the correctness contract. Callers that ignore it can silently lose work.

## Worker execution

`job_worker_once(cpu)` first cooperates with TLB runtime fencing and polling.

It then removes at most one job from the circular queue under the spinlock.

The function executes the job after releasing the queue lock.

When the function returns, the worker atomically increments the completed counter and decrements `g_inflight`.

Long-running graphics jobs therefore do not hold the queue lock while rasterizing.

## BSP participation

`job_wait_idle` does more than spin.

While `g_inflight` is nonzero, CPU 0 calls:

```text
job_worker_once(0)
```

and then executes `pause`.

The bootstrap processor therefore helps drain work rather than waiting passively for APs.

This is a work-sharing barrier: return means all successfully submitted in-flight jobs have completed.

It does not mean every attempted submission succeeded.

## AP worker loop

Application processors can remain in `job_worker_forever`.

The loop polls TLB work, enables local APIC interrupts when released, runs one queued job and executes `pause`.

TLB fencing can divert a CPU from normal job work and eventually halt it.

Graphics scheduling therefore shares the same workers with kernel-wide job and TLB responsibilities.

## Queue saturation evidence

`tools/test_job_saturate.c` directly exercises the kernel queue.

It submits exactly 1024 jobs and requires all to succeed.

The next submission must fail.

After manually draining all jobs, another submission must succeed.

This test establishes bounded-queue semantics and queue reuse after drain.

The kernel runtime also has `smp_job_selftest`, which submits smaller waves and waits for completion when multiple CPUs are online.

## 64×64 graphics tiles

`kernel/gfx/tile.h` defines:

```text
TILE_SIZE = 64
```

The same tile size is used by parallel clear and triangle binning.

At a 1920×1080 surface this corresponds to 30 tile columns and 17 rows, or 510 clear jobs when the entire framebuffer is covered.

That count is below the kernel queue capacity when the queue starts empty.

## Parallel clear

`tile_parallel_clear` computes the tile grid covering the framebuffer.

Each tile receives a `TileClearArg` containing:

- destination pointer;
- framebuffer dimensions;
- tile coordinates;
- fill color.

The worker clips the last tile in each row/column to the real width/height and fills each row with `gfx_fast_fill_u32`.

Different clear tiles do not overlap.

This is a naturally race-free partition of the color buffer.

## Clear argument lifetime

The clear arguments live in:

```text
static TileClearArg args[JOB_QUEUE_CAP]
```

The caller increments an index as it submits work.

Before reusing the array after 1024 argument slots, it calls `job_wait_idle` and resets the index.

This creates a lifetime barrier: accepted jobs finish before the corresponding argument storage is reused.

At the current maximum graphics size, a full clear needs only 510 tiles, so ordinary Full HD clear does not need the mid-loop reuse barrier.

## Clear submission weakness

`tile_parallel_clear` calls `job_submit` but does not check its return value.

If the graphics caller owns an otherwise empty kernel queue, the maximum current display size fits below queue capacity.

However, the job queue is global to the kernel. Other work may already occupy entries.

In that situation, a clear job can fail submission and the code still increments its local argument index as though the job existed.

The affected tile is then never cleared.

The current implementation therefore relies on queue availability that is not encoded in the API.

## Host job stub

Graphics host tests do not run the real kernel worker loop.

`tools/job_host_stub.c` implements a pthread-backed substitute.

It permits one to eight workers and starts worker threads during `job_wait_idle`.

Its internal queue capacity is:

```text
JOB_Q_CAP = 512
```

which differs from the 1024 capacity exposed by the kernel header.

For current `test_tile`, only twelve clear jobs are generated, so the mismatch does not affect that test.

The host stub should not be treated as proof of kernel queue-capacity behavior.

## Parallel-clear test

`tools/test_tile.c` uses a 256×192 framebuffer.

That surface produces four tile columns and three tile rows: twelve jobs.

The test renders the same magenta clear with one host worker and with two workers.

It verifies the first and last pixels and compares a framebuffer checksum.

This establishes deterministic disjoint-tile clear for that workload.

It does not test queue pressure, unrelated concurrent jobs or maximum resolution.

## Triangle binning

`tile_mesh_raster` begins by building a `TriBin`.

For each triangle, it finds the projected min/max X and Y and passes the rectangle to `tri_bin_add`.

The bin converts screen coordinates to tile coordinates using six-bit shifts, corresponding to 64-pixel tiles.

For every tile overlapped by the rectangle, it packs one entry:

```text
bits 31..16 : triangle ID
bits 15..8  : tile Y
bits 7..0   : tile X
```

## Bin capacity

`TRI_BIN_MAX` is 4096.

The capacity counts triangle/tile overlaps, not source triangles.

A large triangle touching many tiles consumes many entries.

Once `b->count` reaches 4096, additional overlaps are silently omitted.

There is no overflow flag returned to `tile_mesh_raster`.

This means bin saturation can produce missing raster work.

## Screen dimensions in TriBin

`tri_bin_reset` stores `screen_w` and `screen_h` in the `TriBin`.

The current `tri_bin_add` implementation does not use those fields to clamp its tile ranges.

Range checking happens later in `tile_mesh_raster` after packed entries have already consumed bin capacity.

Therefore completely or partially off-screen bounds can waste bin entries before being rejected.

## Negative-coordinate robustness

Projected triangles can have negative screen coordinates while still being geometrically visible.

`tri_bin_add` shifts and packs its signed tile coordinates without first clipping to a nonnegative screen tile range.

The later raster loop rejects decoded tile indices outside the actual grid, but that late rejection does not establish a clean portable C contract for negative signed packing and does not recover capacity already consumed.

A robust binning layer should clip min/max tile coordinates before packing them.

## Tile-triangle arguments

For each valid bin entry, `tile_mesh_raster` fills one element of:

```text
static TileTriArg args[TRI_BIN_MAX]
```

The structure contains the framebuffer, tile clip rectangle, all three projected vertices/depths and the palette color.

The worker simply calls `tri_fill_clip`.

Each accepted job has a unique argument slot until the final `job_wait_idle`, so argument reuse does not occur during that call.

## Raster clip ownership

A triangle overlapping multiple tiles is intentionally submitted multiple times.

Every invocation uses the full triangle geometry but a different clip rectangle.

The scalar triangle rasterizer intersects its bounding box with that rectangle.

For two different tiles, clip rectangles are disjoint, so the same triangle cannot write the same pixel from two tile jobs.

This is safe spatial decomposition across tiles.

## Same-tile triangle overlap

The harder case is multiple different triangles in the same tile.

They become separate jobs with the same tile clip rectangle.

Those triangles can target identical pixels.

`zbuf_test` uses ordinary load/compare/store operations and the later color write is also ordinary memory.

There is no atomic depth/color fragment transaction.

Two workers processing overlapping triangles can therefore race.

## Possible depth/color race

Consider two incoming depths A and B targeting the same cell.

Both workers may read the old far value before either store becomes visible.

Both can conclude that their depth passes.

Each then stores depth and later writes color.

The final color does not have to correspond to the final nearest depth under arbitrary interleaving.

Sequential z-buffer semantics are not automatically preserved.

This is the central correctness limit of the current triangle/tile parallel path.

## Submission saturation in tile_mesh_raster

The triangle bin can contain up to 4096 entries, while the kernel queue holds only 1024 jobs.

`tile_mesh_raster` does not batch after 1024 submissions and does not retry when `job_submit` returns 0.

Workers may drain the queue concurrently, so many workloads can still submit more than 1024 jobs successfully over time.

But success is scheduling-dependent rather than guaranteed.

Under pressure, rejected submissions become silently missing triangle/tile work.

This is stronger than a performance issue: it can alter the rendered image.

## Why final wait is insufficient

The function calls `job_wait_idle` after attempting all bin entries.

That waits for every successfully submitted job.

It cannot wait for jobs whose submissions failed, because they never incremented `g_inflight`.

A barrier at the end therefore does not repair lost submissions.

Correctness requires checking submission results and either retrying, draining/batching or falling back synchronously.

## Scene-band strategy

`scene_draw` uses a different parallel pattern.

It divides the framebuffer into at most four horizontal bands.

If height is less than four, it uses one band.

Each `SceneBand` has an exclusive half-open Y range.

A worker loops over all visible scene nodes but rasterizes each node through `tri_fill_clip` restricted to its band.

## Scene-band pixel ownership

Band boundaries are disjoint.

One worker cannot write a row owned by another band.

The z-buffer is global, but workers address different cells because Y ownership is exclusive.

This makes ordinary non-atomic depth and color operations safe with respect to inter-band competition.

The approach performs redundant per-node setup across bands, but it has a much clearer correctness model.

## Scene queue-full fallback

Scene submission also differs in failure handling:

```text
if (!job_submit(band_job, &g_band[i]))
    band_job(&g_band[i], 0);
```

If the queue is full, the BSP executes that band synchronously.

No band is silently lost.

After all submissions/fallbacks, `job_wait_idle` completes accepted asynchronous jobs before return.

This is the stronger submission pattern that tile rasterization should emulate.

## Static band lifetime

`g_band[4]` is static.

`scene_draw` does not return until `job_wait_idle` completes all submitted bands.

Therefore the arguments remain valid for the lifetime of the jobs.

Concurrent independent calls to `scene_draw` would still share `g_band` and global visible-node state, so the API is not reentrant.

## Determinism

Disjoint clear tiles and scene bands can be deterministic because each pixel has one spatial owner.

Triangle/tile jobs do not have that property when distinct triangles overlap inside a tile.

Strict LESS depth comparison also means equal-depth coplanar fragments depend on arrival order even in a race-free serial path.

Parallel correctness therefore requires distinguishing mathematical visibility, equal-depth policy and worker ordering.

## Performance trade-offs

Parallel clear divides a memory-bandwidth operation into cache-friendly 64×64 regions.

Scene bands parallelize broad screen work but repeat node traversal in every band.

Triangle binning avoids rasterizing a triangle outside touched tiles but expands one source triangle into several jobs.

Small triangles may create enough job overhead that parallel execution costs more than scalar rasterization.

The current legacy mesh path only enables tile rasterization for larger framebuffer areas, reflecting this overhead trade-off.

## Queue contention with non-graphics work

The kernel job queue is shared.

Kthreads and other subsystems can submit jobs to the same structure.

Graphics code cannot assume all 1024 entries are available merely because it has fewer than 1024 local tasks.

This is especially relevant to the unchecked submission calls in `tile.c`.

A future renderer-specific scheduler or reservation policy could make capacity assumptions explicit.

## Security and fault containment

All tile jobs operate in kernel context on pointers prepared by kernel graphics code.

The job queue does not copy argument data; it stores raw pointers.

Correctness therefore depends on argument lifetime and trusted construction.

The static arrays plus wait barriers satisfy lifetime for ordinary sequential calls.

Reentrant calls or premature reuse would violate that ownership model.

## Validation gaps

There is no direct host test for `tile_mesh_raster` with overlapping triangles and multiple workers.

There is no test that saturates graphics submissions while unrelated jobs occupy the queue.

There is no bin-overflow test at 4096 overlaps.

There is no test for negative/off-screen bin bounds.

The existing clear checksum test cannot prove depth/color race freedom because clear jobs do not overlap.

## Recommended fixes

The smallest correctness improvement is to handle every `job_submit` result.

A failed triangle submission can execute synchronously or trigger a drain-and-retry policy.

A stronger design groups work by tile and gives one job ownership of all triangles for that tile. Then one worker serializes depth/color updates inside each tile while different tiles execute in parallel.

That model preserves spatial ownership and aligns more closely with conventional tiled software rasterizers.

Bin creation should also clamp tile ranges before packing and report capacity exhaustion explicitly.

## Recommended tests

A stronger suite should include:

- full-frame clear with queue pressure;
- bin saturation;
- off-screen negative bounding boxes;
- many triangles in one tile;
- overlapping near/far triangles repeated under multiple workers;
- framebuffer/depth checksums across repeated runs;
- forced submission failures with synchronous fallback;
- comparison between scalar and parallel output for the same scene.

The intended invariant should be pixel-equivalent output for workloads where the serial renderer defines a deterministic result.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It distinguishes race-free disjoint partitioning from the current triangle/tile path, where queue saturation and overlapping fragments remain explicit correctness limitations.
