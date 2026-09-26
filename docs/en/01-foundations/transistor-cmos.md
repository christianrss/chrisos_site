---
id: transistor-cmos
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
related:
  - logic-sequential
---

# Transistors and CMOS logic

## MOSFET as a controlled device

A MOSFET has gate, source, drain and body terminals. The gate is separated from the semiconductor by an insulating dielectric. Gate voltage alters the electric field in the channel region and therefore controls whether source and drain are connected by a sufficiently conductive path.

For digital reasoning, the transistor is approximated as a voltage-controlled switch. That approximation is intentionally incomplete: real devices have threshold voltage, finite resistance, capacitance, leakage, transition time and nonlinear current-voltage behavior. Those analog properties determine power and speed, while logic design usually operates on the restored binary state.

## NMOS and PMOS

CMOS logic combines complementary device types.

- An **NMOS** device conducts strongly when its gate is driven high relative to its source.
- A **PMOS** device conducts strongly under the complementary gate condition.

The canonical CMOS inverter uses a PMOS pull-up network and an NMOS pull-down network.

```text
             VDD
              │
            PMOS
input ─────── gate
              │──── output
input ─────── gate
            NMOS
              │
             GND
```

When the input is low, the PMOS tends to conduct and the NMOS tends not to, pulling the output toward the high supply. When the input is high, the opposite path dominates and pulls the output toward ground.

The important property is restoration: a valid low input produces a strongly high output, and a valid high input produces a strongly low output.

## Static and dynamic behavior

Static CMOS ideally draws little direct current between supply rails when settled because one side of the complementary network is off. Real chips consume static leakage, but a large portion of active power comes from charging and discharging capacitance during transitions.

A useful first-order dynamic-power relation is

```text
P_dynamic ≈ α C V² f
```

where `α` is switching activity, `C` effective capacitance, `V` supply voltage and `f` switching frequency. This explains why clock frequency, voltage and transistor count interact strongly with CPU power.

Propagation is not instantaneous. A change at a gate input takes finite time to alter the output. Combinational paths therefore have a maximum delay, and synchronous circuits must choose a clock period that allows required state to settle before the next capture event.

## CMOS networks and Boolean functions

Series and parallel transistor networks implement logical conditions. NAND and NOR gates are particularly natural in CMOS. Since NAND or NOR alone is functionally complete, arbitrary Boolean functions can be constructed from repeated gates.

Boolean algebra abstracts away voltage and device geometry. Variables take values 0 or 1; operations such as NOT, AND and OR describe the stable logic relation.

| Boolean form | Gate meaning |
|---|---|
| `¬A` | NOT |
| `A ∧ B` | AND |
| `A ∨ B` | OR |
| `¬(A ∧ B)` | NAND |
| `¬(A ∨ B)` | NOR |

The distinction between Boolean expression and physical implementation is important. A CPU schematic may describe an adder using XOR, AND and OR, while a cell library eventually maps those gates to transistor networks with timing and power characteristics.

## Fan-out, loading and signal integrity

A gate output can drive only finite capacitance. Connecting it to many following inputs increases loading and slows transitions. Real logic design therefore uses buffers, sizing and carefully characterized cells.

Noise margin permits small disturbances without changing interpreted logic. If a signal enters the undefined transition region near a sampling event, sequential elements can become metastable. Synchronous design reduces this risk through timing constraints and synchronization structures but cannot make the underlying analog phenomenon disappear.

## Why CMOS leads to stateful machines

Pure combinational logic computes outputs solely from current inputs. A computer must also remember previous state. Feedback around gates produces bistable circuits; clocked storage elements constrain when new values are accepted. These structures become latches, flip-flops, registers, counters, caches and memory interfaces.

At the software-visible level, an x86-64 register such as RAX appears to contain 64 exact bits. Physically it is implemented by state-holding circuitry embedded in a much larger microarchitecture. The ISA deliberately hides the transistor topology.

## Abstraction boundary for ChrisOS

ChrisOS begins above this hardware boundary. Neither the kernel nor ChrisCPU models individual MOSFETs. ChrisCPU emulates **architectural state**: registers, flags, control registers, memory effects and exceptions. This is possible precisely because the x86-64 ISA provides a stable abstraction over lower-level circuits.

The next chapter constructs the path from gates to state elements, arithmetic blocks and clocked machines.
