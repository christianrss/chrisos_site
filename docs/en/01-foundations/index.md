---
id: volume-01-foundations
lang: en
type: volume-index
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Foundations

<div class="abstract">This collection contains the physical, electrical, digital, mathematical and algorithmic prerequisites used by the rest of the ChrisOS corpus. Its internal order follows the canonical curriculum rather than source-directory chronology.</div>

## Position in the corpus

The foundations establish the lowest abstraction layers required by later architecture, kernel, compiler, graphics, networking and emulation chapters.

~~~text
matter and physical models
    ↓
mathematical tools required by the physical model
    ↓
electric charge, field and potential
    ↓
circuit quantities and network laws
    ↓
energy storage, transients and AC behavior
    ↓
high-speed signaling, noise and power delivery
    ↓
semiconductor electrostatics
    ↓
MOSFET and CMOS
    ↓
logic levels and Boolean abstraction
    ↓
combinational arithmetic
    ↓
sequential state, clocks and memory cells
    ↓
representation
    ↓
complexity
    ↓
data structures
    ↓
systems algorithms
~~~

## Physical and electrical foundations

The canonical sequence is:

1. matter, atoms and physical models;
2. vectors and complex-number tools required later by field/circuit analysis;
3. electric charge, field, potential and energy;
4. voltage, current, resistance, energy and power;
5. Ohm's law, Kirchhoff's laws and circuit analysis;
6. capacitance and inductance;
7. RC, RL and RLC transients;
8. AC signals, phase, frequency and impedance;
9. electromagnetic induction and transformers;
10. transmission lines and differential signaling;
11. noise, grounding and signal integrity;
12. power delivery, regulation and decoupling.

These topics define the physical assumptions behind semiconductor and digital behavior.

## Semiconductor and digital foundations

The device sequence is:

1. crystal structure, bands and doping;
2. p-n junctions;
3. MOS capacitor electrostatics;
4. MOSFET and CMOS;
5. CMOS delay and power;
6. logic thresholds, fan-out and noise margins;
7. Boolean algebra;
8. binary number systems;
9. combinational logic;
10. arithmetic circuits;
11. sequential logic;
12. latches and flip-flops;
13. registers, counters and state machines;
14. clock timing;
15. SRAM and DRAM.

The transition from electrical voltage ranges to abstract Boolean state is therefore explicit.

## Representation and algorithms

The software-foundation sequence is:

1. discrete mathematics: sets, relations and functions;
2. proof, invariants and induction;
3. data representation, layout and pointers;
4. algorithmic complexity and systems cost models;
5. recursion, recurrences and amortized analysis;
6. arrays, lists, stacks and queues;
7. hash tables;
8. trees, heaps and tries;
9. graphs and disjoint-set union;
10. bitmaps, rings and free lists;
11. sorting and searching;
12. graph algorithms;
13. string and parsing algorithms;
14. algorithms implemented by ChrisOS.

## Dependency rule

A later chapter may assume a concept only when one of the following is true:

- the concept is defined in an earlier curriculum chapter;
- the chapter contains a bounded local derivation sufficient for its use;
- the concept is marked as a forward reference rather than treated as established knowledge.

This rule prevents hidden jumps between physical, mathematical and software abstractions.

## Implementation linkage

Foundational theory is connected to current implementation at the first appropriate boundary.

Examples include:

| Foundation | Later implementation |
|---|---|
| finite-width arithmetic and flags | ChrisCPU arithmetic semantics |
| registers and state machines | ChrisArchitectureState |
| bitmaps | PMM allocation state |
| ring buffers | VirtIO queues and kernel job queues |
| trees/graphs | filesystem, compiler and dependency structures |
| charge/capacitance/timing | physical limits beneath memory and CPU timing models |

A foundational chapter does not claim that ChrisOS directly implements the underlying physical device.

## Evidence rule

Physical and mathematical chapters distinguish:

- normative equations and definitions;
- model assumptions;
- illustrative numerical examples;
- limits of the model;
- later architectural consequences;
- current ChrisOS linkage.

Source-linked claims are revision-bound. Physical-device claims rely on primary technical references rather than inference from kernel code.
