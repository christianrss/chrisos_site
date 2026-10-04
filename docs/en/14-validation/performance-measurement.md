---
id: performance-measurement
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/bench.c
  - kernel/gfx/bench.h
  - kernel/metal/pit.c
  - kernel/metal/start.c
  - kernel/wm/main.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/tools/shell.c
  - APPS/SHELL/SHELL.CC
  - APPS/TASKMGR/TASKMGR.CC
  - tools/test_jit_bench.c
  - kernel/fs/cfs.c
  - kernel/fs/storage_limits.h
  - kernel/gfx/vgpu.c
  - kernel/gfx/shader/sh_api.c
  - makefile
symbols:
  - bench_frame_tick
  - bench_fps_estimate
  - bench_frame_ms
  - bench_frame_p50_ms
  - bench_frame_p95_ms
  - pit_ticks
  - lang_tick
  - cfs_cache_hits
  - cfs_cache_misses
depends_on:
  - host-tests
  - qemu-gates
  - hardware-gates
related:
  - fuzzing
  - fault-injection
  - jit
  - chrisfs-cache
  - virtio-gpu-virgl
---

# Performance measurement

## Scope

Performance work is valid only when the quantity being measured is defined precisely.

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisOS has several real measurement mechanisms:

- desktop/frame cadence derived from the PIT;
- rolling frame-time samples and p50/p95 values;
- a host benchmark comparing CLVM interpretation and JIT execution;
- ChrisFS cache hit/miss counters;
- heap/PMM resource telemetry exposed to applications;
- internal cycle counters in the shader compiler;
- internal VirtIO-GPU activity counters and TSC-based wait budgets.

These mechanisms are useful, but they are not one unified profiling subsystem.

ChrisOS currently does **not** provide a general CPU profiler, PMU abstraction, flame graph pipeline, per-process CPU-time accounting, system-wide tracing framework, calibrated high-resolution wall clock, or automated performance-regression database.

This chapter therefore distinguishes three classes:

1. product/runtime telemetry;
2. regression benchmarks;
3. internal diagnostic counters.

## Measurement model

Every performance result should be treated as a tuple:

[
P = (R, E, W, M, S)
]

where:

- (R) is the exact ChrisOS revision;
- (E) is the execution environment;
- (W) is the workload;
- (M) is the measurement method;
- (S) is the resulting sample set.

A number without these dimensions is not reproducible evidence.

For example, "60 FPS" is incomplete unless the reader knows whether the system was running under QEMU TCG, KVM, physical hardware, which resolution was active, what workload was present and what the ChrisOS FPS counter actually counts.

## Clock sources used today

ChrisOS currently uses more than one timing source.

### PIT

The kernel initializes the programmable interval timer with:

    pit_init(60)

The PIT interrupt increments the global `ticks` counter.

The desktop loop waits for tick advancement between frames.

This makes the PIT the primary scheduler/frame cadence source for the current desktop.

### Host monotonic clock

`tools/test_jit_bench.c` uses a host high-resolution monotonic source:

- `clock_gettime(CLOCK_MONOTONIC)` on POSIX systems;
- `QueryPerformanceCounter` on Windows.

This is appropriate for a host benchmark because it measures actual elapsed host time around interpreter and JIT workloads.

### RDTSC

The shader compiler and VirtIO-GPU implementation use `rdtsc` internally.

RDTSC provides a cycle-like timestamp counter, but raw differences are not automatically portable units of time.

Without calibration, invariant-TSC checks and serialization discipline, such values are best interpreted as local diagnostic cycle deltas rather than nanoseconds.

## Desktop loop and frame cadence

The current desktop loop executes:

    net_poll()
    clvm_sys_frame(ticks)
    lang_tick(ticks)
    desktop_frame(ticks)
    gfx_present()

and then waits until the PIT tick changes.

At the intended 60 Hz timer configuration, the loop is therefore paced toward one iteration per PIT interval.

This is why the kernel reports:

    ChrisOS: desktop 60Hz

The statement describes the configured cadence, not proof that every frame is rendered in exactly 16.67 ms.

A slow frame can consume more than one tick.

## FPS estimator

`bench_frame_tick` is called from `lang_tick`.

It increments a frame counter and, whenever at least 60 PIT ticks have elapsed, stores the accumulated count as the FPS estimate.

Conceptually:

[
FPS approx rac{frames}{Delta ticks / 60}
]

In the common case where the window is exactly 60 ticks, the stored FPS is simply the number of observed frame ticks during approximately one second.

The shell command:

    bench

prints this value in the native kernel shell.

The ChrisC/CLVM application shell exposes:

    fps

and also prints frame p50 and p95 values.

## What the FPS value really means

The current FPS counter is not a GPU hardware counter.

It is not derived from scanout completion, display vblank, or physical monitor refresh.

It counts calls to `bench_frame_tick`, which occur during `lang_tick` inside the desktop loop.

Therefore it is best interpreted as:

> observed ChrisOS desktop-loop frame cadence at the language/runtime tick point.

This is still useful for regression detection, but the distinction prevents overclaiming graphics throughput.

## Frame-time samples

The benchmark layer also tracks elapsed PIT ticks between consecutive `bench_frame_tick` calls.

The conversion is:

[
ms = rac{ticks cdot 1000 + 30}{60}
]

using integer arithmetic.

The current implementation stores the latest 64 samples.

This is a bounded rolling window.

It requires constant memory and avoids dynamic allocation in the measurement path.

## Timer resolution

Because the frame measurement is based on a 60 Hz PIT, one timer quantum is approximately:

[
T = rac{1}{60}s approx 16.67ms
]

The integer conversion quantizes values at roughly this scale.

A frame that completes in 4 ms and one that completes in 14 ms can both be indistinguishable if they fall within the same PIT interval.

Therefore the current frame p50/p95 values are useful for detecting coarse stalls and missed 60 Hz cadence, but they are not high-resolution latency measurements.

## p50 and p95

The rolling frame samples are copied and sorted when a percentile is requested.

For (N) samples, the implementation selects:

[
index = rac{(N-1)cdot percentile}{100}
]

For p50:

[
index_{50} = leftlfloorrac{(N-1)50}{100}ightfloor
]

For p95:

[
index_{95} = leftlfloorrac{(N-1)95}{100}ightfloor
]

With at most 64 samples, the selection sort is (O(N^2)), but (Nle64), so the absolute cost is bounded and small.

These functions are intended for telemetry, not high-frequency inner-loop use.

## User-visible performance telemetry

The Task Manager application exposes:

- heap used KB;
- heap free KB;
- free PMM pages;
- frame p50;
- frame p95.

The application shell exposes FPS and percentile frame timing.

The CLVM system-call dispatcher provides the corresponding values to guest applications.

This is an important architectural property: performance/resource telemetry is not restricted to kernel debugging output.

Applications can inspect the system through defined runtime services.

## Resource metrics are not timing metrics

Heap and PMM values measure capacity/pressure, not execution speed.

They are still performance-relevant because memory pressure can explain latency, allocation failure and workload scaling behavior.

A useful performance record can therefore combine:

[
Latency, Throughput, Memory, Cache
]

rather than reporting only elapsed time.

## ChrisFS cache counters

ChrisFS maintains:

    cache_hits
    cache_misses

The cache currently contains 64 lines.

A cache hit occurs when the requested LBA is already represented in the in-memory cache.

A miss increments before the underlying block-device read.

The counters can be read through:

    cfs_cache_hits()
    cfs_cache_misses()

and are exposed through CLVM system services.

A basic cache hit ratio is:

[
H = rac{hits}{hits + misses}
]

when the denominator is non-zero.

## Interpreting cache hit ratio

A high hit ratio does not automatically mean the filesystem is fast.

It can reflect:

- a highly repetitive workload;
- an undersized working set;
- repeated metadata reads;
- a benchmark that never exceeds 64 cache lines.

Likewise, a lower ratio can be expected for streaming workloads.

Performance analysis must therefore record the workload shape and number of bytes/operations, not only the ratio.

## Cache counter reset semantics

The ChrisFS cache counters reset when the cache is reset.

They are cumulative after that point.

Comparisons should use either:

- a freshly mounted/reset filesystem;
- or deltas between counter snapshots.

Comparing an old cumulative total with a short new workload gives misleading results.

## JIT benchmark

The most explicit performance regression gate is:

    host-jit-bench-test

The benchmark compiles a small ChrisC program containing a continuous pixel loop.

It creates equivalent CLVM interpreter and JIT VM states.

Both paths are warmed up before timing.

Then each executes a bounded workload using:

    BENCH_ROUNDS = 400
    BENCH_BUDGET = 12000

The benchmark records host elapsed time for both paths.

## JIT speedup metric

The reported metric is:

[
speedup = rac{T_{interp}}{T_{jit}}
]

The current gate requires:

    MIN_SPEEDUP = 5.0

If:

[
speedup < 5
]

the test fails.

The output includes interpreter seconds, JIT seconds and the computed ratio.

This makes performance an executable regression condition rather than only a manually observed number.

## What the 5x threshold proves

The JIT threshold proves something narrow:

> for the benchmark program, build flags and host environment represented by this test, the measured JIT path must be at least five times faster than the interpreter.

It does **not** prove:

- every ChrisC program is 5x faster;
- kernel execution is 5x faster;
- physical ChrisOS applications always obtain that ratio;
- JIT latency, compile time and code-cache effects are negligible in every workload.

The threshold is a regression guard, not a universal performance claim.

## Benchmark compilation conditions

The JIT benchmark is compiled on the host with `-O2` and the relevant project sources.

Therefore benchmark results depend on:

- host CPU;
- compiler/version;
- optimization behavior;
- operating system;
- frequency scaling;
- background load;
- thermal state.

The pass/fail ratio is generally more portable than comparing absolute seconds between unrelated machines, but even the ratio can vary.

## Warm-up

The benchmark runs both interpreter and JIT paths for several rounds before the measured phase.

Warm-up reduces first-use effects such as:

- cold instruction/data caches;
- one-time initialization;
- lazy allocation;
- host scheduling transients.

It does not eliminate all variance.

Repeated samples are still preferable when producing published benchmark numbers.

## Statistical discipline

A single measurement is not a distribution.

For serious performance comparison, collect repeated independent runs.

For samples (x_1...x_n), useful summaries include:

- median;
- p95;
- minimum/maximum;
- interquartile range;
- coefficient of variation when meaningful.

For comparing revisions A and B:

[
Delta% = rac{B-A}{A}	imes100
]

The environment must remain controlled before interpreting the result as a code regression.

## QEMU performance caveat

Most ChrisOS QEMU gates use TCG.

TCG is appropriate for portability and functional validation but is a poor proxy for physical performance.

Timing under TCG is affected by:

- dynamic translation overhead;
- host scheduling;
- emulated timer behavior;
- device-model implementation;
- lack of real hardware latency.

Therefore QEMU gate durations must not be presented as hardware benchmark results.

QEMU can still detect large relative regressions if the machine configuration and runner are controlled, but this should be treated as a separate benchmark class.

## KVM caveat

KVM can provide more realistic CPU execution speed than TCG on supported hosts, but it still does not make virtual devices equivalent to physical devices.

A KVM benchmark must record:

- host CPU;
- vCPU count;
- CPU model exposed to guest;
- memory size;
- QEMU version;
- device models;
- host kernel/hypervisor;
- affinity/frequency policy where relevant.

## Hardware benchmarks

Physical benchmarking adds real firmware, buses, controllers and devices.

It also adds uncontrolled variance.

A hardware performance record should include:

- exact machine profile;
- firmware version;
- CPU governor/power mode;
- CPU temperature if relevant;
- memory configuration;
- storage device/model;
- framebuffer resolution;
- boot mode;
- ChrisOS revision;
- image hash;
- repeated sample count.

Without these fields, performance differences are hard to attribute.

## Shader compiler cycle counters

The shader compiler records RDTSC deltas for phases including:

- lexing;
- parsing;
- semantic analysis;
- IR optimization/verification;
- TGSI emission.

These counters are embedded in internal compiler structures.

They are useful for phase attribution.

At the current revision they should be treated as internal diagnostics, not a stable public performance ABI.

Raw cycle differences also require care across CPUs and execution environments.

## Shader cache effect

The shader subsystem maintains a small compiler cache.

A cache hit can bypass expensive compiler stages.

Therefore a shader compilation benchmark must state whether it measures:

- cold compile;
- warm cached compile;
- repeated same-source compile;
- mixed shader workload.

Otherwise a comparison can accidentally measure cache behavior instead of compiler speed.

## VirtIO-GPU counters

The VirtIO-GPU implementation keeps internal counters such as:

- rectangles;
- pixels;
- bytes;
- full updates;
- partial updates;
- waits;
- interrupt count.

It also uses RDTSC-based budgets in command wait paths.

These values can help diagnose whether a graphics workload is dominated by:

- full-frame transfer;
- partial updates;
- synchronization waits;
- command/interrupt behavior.

They are internal instrumentation at this revision.

They are not yet exposed as one stable user-visible statistics interface.

## Throughput

A generic throughput metric is:

[
Throughput = rac{work}{time}
]

For storage, "work" could be bytes or I/O operations.

For rendering, it could be frames, pixels or triangles.

For compilation, it could be source bytes or compilation units.

A benchmark must define work explicitly.

"Faster" without a workload denominator is not a throughput measurement.

## Latency versus throughput

Latency and throughput answer different questions.

A system can improve total throughput while making tail latency worse.

For interactive ChrisOS workloads, p95 frame time can be more relevant than average FPS because visible stutter is a tail event.

For bulk storage or compilation, throughput may dominate.

The metric must match the user-visible or architectural objective.

## Tail performance

The existing p95 frame metric is an important step because average values hide stalls.

If 95 frames take one tick but 5 frames take six ticks, the average can appear acceptable while interaction feels unstable.

Future instrumentation should expand this idea to:

- scheduler wake latency;
- storage I/O latency;
- syscall latency;
- JIT compile latency;
- graphics submit/present latency.

## Measurement overhead

Instrumentation changes the system being measured.

Examples:

- serial logging can be expensive;
- RDTSC calls have non-zero overhead;
- sorting percentile samples consumes CPU;
- debug builds alter code layout;
- tracing can perturb scheduler timing.

A benchmark should use the lowest-overhead instrumentation that still answers the question.

When comparing revisions, instrumentation must remain unchanged.

## Baseline and regression budgets

Performance engineering becomes more actionable when a metric has a baseline and permitted regression.

For metric (m):

[
Regression = rac{m_{new}-m_{base}}{m_{base}}
]

For lower-is-better latency metrics, positive values are regressions.

For higher-is-better throughput metrics, the sign convention should be inverted or explicitly documented.

The JIT test already applies this principle through a minimum speedup threshold.

Other subsystems do not yet have equivalent automated budgets.

## Missing measurement facilities

At the reviewed revision ChrisOS lacks:

- calibrated monotonic nanosecond clock API;
- invariant-TSC calibration layer;
- per-process CPU accounting;
- scheduler latency histogram;
- syscall latency histogram;
- storage latency/IOPS benchmark;
- network throughput/latency benchmark;
- native GPU timestamp queries;
- PMU counters for instructions/cache misses/branches;
- continuous benchmark history across commits;
- automatic statistical regression detection.

These are roadmap items, not current features.

## Recommended benchmark protocol

For any publishable ChrisOS performance result:

1. record source revision and image hash;
2. record environment/hardware/QEMU configuration;
3. define the workload exactly;
4. specify cold or warm state;
5. choose the metric and unit before running;
6. run enough repetitions to expose variance;
7. retain raw samples;
8. report median and a tail/dispersion measure;
9. compare against a revision-bound baseline;
10. avoid mixing TCG, KVM and physical results in one unlabeled series.

## Highest-value improvements

The next maturity steps are:

1. add calibrated monotonic time in micro/nanoseconds;
2. separate desktop-loop, render-submit and actual present timing;
3. expose stable graphics/cache/resource statistics snapshots;
4. add storage throughput and latency microbenchmarks;
5. add scheduler/syscall latency histograms;
6. run fuzz/benchmark targets with repeatable CI hardware classes;
7. preserve benchmark results as artifacts;
8. track performance across commits;
9. add regression thresholds only after variance is understood;
10. later add PMU/performance-counter support on physical x86-64 hardware.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

At this revision, ChrisOS already has meaningful performance evidence: frame cadence/percentiles, a JIT speedup regression gate, filesystem cache counters and subsystem diagnostics. The key limitation is precision and unification: the existing instruments answer local questions but do not yet form a general profiling and benchmark framework.
