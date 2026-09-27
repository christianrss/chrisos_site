---
id: volume-01-foundations
lang: en
type: volume-index
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Physical, electrical, digital and algorithmic foundations

<div class="abstract">This volume follows the causal chain from matter and electric charge to fields, circuits, semiconductor devices, digital logic, stored state, mathematical representation, data structures and algorithms. Later kernel, compiler, graphics, networking and emulator chapters should not depend on an unexplained primitive.</div>

## Scope

This volume is not a survey. It is the prerequisite layer for the entire ChrisOS corpus.

The intended progression is:

~~~text
matter
  ↓
charge
  ↓
electric field and potential
  ↓
voltage / current / resistance / power
  ↓
circuit laws
  ↓
capacitors / inductors / transients / AC
  ↓
signal integrity and power delivery
  ↓
semiconductor bands / junctions / MOS electrostatics
  ↓
MOSFET / CMOS
  ↓
logic levels and noise margins
  ↓
Boolean logic
  ↓
combinational circuits
  ↓
arithmetic circuits
  ↓
sequential logic
  ↓
registers / clocks / memory cells
  ↓
representation
  ↓
data structures
  ↓
algorithms
  ↓
computer architecture
  ↓
ChrisOS
~~~

<figure class="figure">
<img src="../../assets/diagrams/foundations-chain.svg" alt="Foundations chain">
<figcaption>The documentation proceeds from physical carriers to structured state and executable algorithms.</figcaption>
</figure>

## Electrical and physical sequence

The curriculum now treats the following topics as explicit prerequisites rather than hidden assumptions:

1. Matter, atomic structure and electrical charge.
2. Electric field, force, electric potential and potential energy.
3. Voltage, current, resistance, resistivity, energy and power.
4. Ohm's law, Kirchhoff's laws and lumped circuit models.
5. Capacitance, inductance and stored electric/magnetic energy.
6. RC, RL and RLC transients and the meaning of a time constant.
7. Sinusoids, frequency, phase, impedance and frequency-domain reasoning.
8. Electromagnetic induction and transformer fundamentals.
9. Transmission lines, differential signaling, reflections and termination.
10. Noise, grounding, return current, crosstalk and signal integrity.
11. Power delivery, regulation, decoupling and supply transients.
12. Crystal structure, energy bands and carrier statistics.
13. Doping, p-n junctions and semiconductor interfaces.
14. MOS capacitor electrostatics.
15. MOSFET and CMOS switching.
16. Dynamic/static CMOS power, capacitance and delay.
17. Logic thresholds, noise margins, fan-out and electrical restoration.

## Digital sequence

Only after the electrical layer is explicit does the curriculum proceed through:

1. Boolean algebra.
2. Combinational logic.
3. Adders, arithmetic circuits and ALUs.
4. Sequential logic.
5. Latches and flip-flops.
6. Metastability and timing constraints.
7. Registers, counters and finite-state machines.
8. Clocking, propagation, setup/hold and clock-domain concerns.
9. SRAM and DRAM cells.

## Mathematical and software sequence

The next volume-level bridge makes the mathematics needed by software explicit:

1. Number systems and binary arithmetic.
2. Sets, relations and functions.
3. Proof, invariants and induction.
4. Vectors and complex numbers where systems/electronics later need them.
5. Data representation, layout and pointers.
6. Complexity analysis.
7. Recurrences and amortized reasoning.
8. Arrays, lists, stacks and queues.
9. Hash tables.
10. Trees, heaps and tries.
11. Graphs and union-find.
12. Bitmaps, rings and free lists.
13. Sorting and searching.
14. Graph algorithms.
15. String and parsing algorithms.
16. Applied systems algorithms in ChrisOS.

## Required reasoning model

Every later implementation chapter should be readable through:

~~~text
physical mechanism
    ↓
electrical behavior
    ↓
digital abstraction
    ↓
representation
    ↓
data structure
    ↓
invariant
    ↓
algorithm
    ↓
complexity and locality
    ↓
synchronization / ownership
    ↓
observable ChrisOS behavior
~~~

A subsystem is not documented completely when only its API is described.

## Mathematical tools are introduced where they become necessary

The corpus is not intended to become a generic mathematics degree.

Algebra, dimensional analysis, vectors, complex numbers, derivatives, integrals and differential equations are introduced when they become necessary to derive an electrical, algorithmic or architectural result.

The rule is that no equation may rely on unexplained mathematics that is essential to understanding the result.

## ChrisOS linkage rule

Every foundational topic eventually reconnects to the implementation.

Examples:

~~~text
electric field
  -> MOS channel control
  -> CMOS gate
  -> flip-flop
  -> register
  -> architectural register
  -> ChrisCPU state

capacitance
  -> switching energy / propagation delay
  -> clock and memory timing
  -> cache/DRAM behavior
  -> performance assumptions visible to ChrisOS

bitmap
  -> resource representation
  -> PMM free-page state
  -> pmm_alloc()

ring buffer
  -> producer/consumer invariant
  -> VirtIO queues / job queues

tree / graph
  -> hierarchy / dependency representation
  -> filesystem, compiler and build-system algorithms
~~~

Theory that never reconnects to an implemented or explicitly future subsystem is not a sufficient chapter.

## Reading rule

Lower layers need not be memorized. They must be available, precise and linked when a higher chapter depends on them.

The machine-readable curriculum is authoritative for chapter order. Missing chapters are intentionally counted as coverage gaps until written in both languages.
