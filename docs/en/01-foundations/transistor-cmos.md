---
id: transistor-cmos
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/chris_arch.h
- chrisvm/cpu/emulator/chriscpu.c
- kernel/gfx/graphics.c
symbols:
- ChrisArchitectureState
- cpu_run
- gfx_rgb
depends_on:
- atom-semiconductor
- crystal-bands-doping
- pn-junction
related:
- logic-sequential
---


# Transistors and CMOS logic

## MOSFET as a controlled device

A MOSFET has gate, source, drain and body terminals. The gate is separated from the semiconductor by an insulating dielectric. Gate voltage alters the electric field in the channel region and therefore controls whether source and drain are connected by a sufficiently conductive path.

For digital reasoning, the transistor is approximated as a voltage-controlled switch. That approximation is intentionally incomplete: real devices have threshold voltage, finite resistance, capacitance, leakage, transition time and nonlinear current-voltage behavior. Those analog properties determine power and speed, while logic design usually operates on the restored binary state.

## Terminal voltages and the channel model

For an NMOS device, gate control is normally discussed using `V_GS`, the gate voltage relative to source, rather than an absolute voltage relative to an arbitrary diagram origin. `V_DS` is the drain-to-source voltage. The body terminal also matters because its bias changes electrostatic conditions. For a PMOS device, a source-referenced magnitude convention can be used, but signs must be defined consistently. Saying only that a gate is “high” hides the reference on which conduction depends.

A simple long-channel model divides NMOS operation into regions. Below threshold, an ideal switch model calls the device off, while a real device still has subthreshold current. With sufficient overdrive `V_GS - V_T`, a small `V_DS` produces a channel behaving approximately like a controlled resistive path. As `V_DS` grows, the channel conditions near the drain change; the saturation-region approximation describes a different current-voltage relation. Saturation in this MOSFET model does not mean the same thing as saturation in every other transistor model.

Under the idealized long-channel, strong-inversion assumptions, a common current expression in the linear region is `I_D = μ C_ox (W/L) [(V_GS-V_T)V_DS - V_DS²/2]`. The saturation approximation is `I_D = μ C_ox (W/L)(V_GS-V_T)²/2`, neglecting channel-length modulation. Here mobility, oxide capacitance per area and width-to-length ratio determine the scale. These equations expose design dependencies; they are not an accurate universal simulation of modern short-channel devices.

In particular, the threshold is not an infinitely sharp event at which all current instantly appears. The switch abstraction intentionally discards part of the continuous characteristic. It is appropriate when reasoning about the final Boolean value under specified voltage ranges, but inadequate for estimating all leakage, analog gain or transition timing. A digital explanation becomes more reliable when the boundary of its simplification is explicit.

## NMOS and PMOS

CMOS logic combines complementary device types.

- An **NMOS** device conducts strongly when its gate is driven high relative to its source.
- A **PMOS** device conducts strongly under the complementary gate condition.

The canonical CMOS inverter uses a PMOS pull-up network and an NMOS pull-down network.

![CMOS inverter / inversor CMOS](../../assets/diagrams/cmos-inverter.svg)

When the input is low, the PMOS tends to conduct and the NMOS tends not to, pulling the output toward the high supply. When the input is high, the opposite path dominates and pulls the output toward ground.

The important property is restoration: a valid low input produces a strongly high output, and a valid high input produces a strongly low output.

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

## Constructing a NAND network

A two-input static CMOS NAND has two NMOS devices in series in the pull-down network and two PMOS devices in parallel in the pull-up network. The output has a conducting path to ground only when both NMOS gates are high. A low value on either input enables a corresponding PMOS path toward the supply. Under settled valid input levels, the output realizes the complement of AND.

| A | B | Pull-down series path | Pull-up parallel path | Output |
|---|---|---|---|---|
| 0 | 0 | Open | Conducting | 1 |
| 0 | 1 | Open | Conducting | 1 |
| 1 | 0 | Open | Conducting | 1 |
| 1 | 1 | Conducting | Open | 0 |

This derivation explains the gate from conduction conditions rather than attaching a truth table to an unexplained symbol. A NOR uses the dual organization: NMOS in parallel and PMOS in series. Its output becomes low if either pull-down branch conducts, and remains high only when both inputs permit the series pull-up path.

The complementarity of the networks avoids a permanent ideal conducting path between rails in a valid settled state. During transitions, both networks can conduct partially, so real switching still has a short-circuit component. Series stacks also change effective drive and intermediate-node behavior. Two expressions that are Boolean-equivalent need not have the same area, delay or energy after implementation.

## Restoration and noise margins

An inverter's voltage-transfer curve relates a continuous input voltage to the resulting output voltage. In stable low and high regions, changes in input need not destroy the output's logical interpretation. Around the transition region, gain can be large and both devices participate in determining the output. Digital interfaces specify input and output limits so that an upstream gate's valid output remains a valid input to the next stage despite tolerances and disturbances.

Using conventional names, the low noise margin is `V_IL,max - V_OL,max`, and the high noise margin is `V_OH,min - V_IH,min`. Positive margins provide room between guaranteed output levels and acceptable input limits. The undefined input region is not an extra Boolean symbol: it is a range for which the interface does not guarantee either logical interpretation.

For an explicitly hypothetical 1 V interface, take `V_OL,max = 0.1 V`, `V_IL,max = 0.3 V`, `V_IH,min = 0.7 V` and `V_OH,min = 0.9 V`. Each margin is 0.2 V. These values illustrate the inequalities; they are not a specification for the hardware running ChrisOS. A correct design must use its actual library or device limits rather than transplanting example numbers.

## Static and dynamic behavior

Static CMOS ideally draws little direct current between supply rails when settled because one side of the complementary network is off. Real chips consume static leakage, but a large portion of active power comes from charging and discharging capacitance during transitions.

A useful first-order dynamic-power relation is

```text
P_dynamic ≈ α C V² f
```

where `α` is switching activity, `C` effective capacitance, `V` supply voltage and `f` switching frequency. This explains why clock frequency, voltage and transistor count interact strongly with CPU power.

Propagation is not instantaneous. A change at a gate input takes finite time to alter the output. Combinational paths therefore have a maximum delay, and synchronous circuits must choose a clock period that allows required state to settle before the next capture event.

## Fan-out, loading and signal integrity

A gate output can drive only finite capacitance. Connecting it to many following inputs increases loading and slows transitions. Real logic design therefore uses buffers, sizing and carefully characterized cells.

Noise margin permits small disturbances without changing interpreted logic. If a signal enters the undefined transition region near a sampling event, sequential elements can become metastable. Synchronous design reduces this risk through timing constraints and synchronization structures but cannot make the underlying analog phenomenon disappear.

## Loading, fanout and why buffers exist

A gate output sees wiring capacitance and the input capacitances of following gates. To change the voltage, it must transfer charge into or out of that load. A rough delay estimate therefore grows with effective output resistance and load capacitance. Increasing transistor width can improve current drive, but increases capacitance presented to the preceding stage and consumes area. Optimizing one gate in isolation can move the problem upstream.

A buffer chain distributes a large drive requirement over stages. Its useful design depends on the ratio of final load to initial input capacitance and the characterized delay model. The purpose is not to change the logical value but to deliver it under electrical and timing constraints. Similarly, a signal used by thousands of storage elements requires a distribution network; it cannot be modeled as a zero-cost connection simply because all endpoints receive the same Boolean clock value.

Glitches add another cost. Unequal path delays can briefly switch a node even when its final value does not change between two logical observations. Such transitions charge capacitance and can consume energy. A truth table describes steady-state functionality, so it does not by itself predict all switching activity needed by the `α C V² f` power model.

## Why CMOS leads to stateful machines

Pure combinational logic computes outputs solely from current inputs. A computer must also remember previous state. Feedback around gates produces bistable circuits; clocked storage elements constrain when new values are accepted. These structures become latches, flip-flops, registers, counters, caches and memory interfaces.

At the software-visible level, an x86-64 register such as RAX appears to contain 64 exact bits. Physically it is implemented by state-holding circuitry embedded in a much larger microarchitecture. The ISA deliberately hides the transistor topology.

## Feedback, startup and controlled state

Connecting inverter outputs back to each other's inputs creates two stable logical arrangements. That positive feedback is the foundation of bistable storage, but startup does not guarantee which arrangement will be selected. A reset mechanism or an explicit initialization sequence is needed when a known starting state matters. This is conceptually related to software initialization, although the mechanisms operate at different abstraction levels.

When external inputs try to change the state near a sensitive sampling event, the analog circuit may take longer to resolve. Timing contracts and synchronizers address that behavior; ordinary Boolean algebra cannot prove its absence. The sequential-logic and clock chapters therefore follow the combinational derivation rather than treating a register as an unexplained box.

At the architecture boundary, software receives guarantees about register operations and reset state, not a list of transistor nodes. `ChrisArchitectureState` in `chrisvm/chris_arch.h` represents those software-visible quantities as C fields. `cpu_run` manipulates this state through instruction semantics. Neither file contains a transistor netlist, capacitance model or device solver. The emulator reproduces the higher-level contract while relying on its host machine to realize electrical computation.

## Abstraction boundary for ChrisOS

ChrisOS begins above this hardware boundary. Neither the kernel nor ChrisCPU models individual MOSFETs. ChrisCPU emulates **architectural state**: registers, flags, control registers, memory effects and exceptions. This is possible precisely because the x86-64 ISA provides a stable abstraction over lower-level circuits.

The next chapter constructs the path from gates to state elements, arithmetic blocks and clocked machines.

## From gate reasoning to code review

The connection to kernel code is through composition of contracts. Bitwise AND can mask selected fields, shifts can position bits, and OR can combine nonoverlapping fields. At the logical level, those operations have truth-table definitions. At the ISA level, instructions define operand widths and results. At the physical level, implementation is free to use different gate arrangements provided it satisfies the architectural behavior and timing requirements.

For example, the RGB encoder in `graphics.c` combines three eight-bit channels in a wider unsigned integer. Understanding AND, OR and shifting makes that representation reconstructible. It does not allow an inference that the CPU executes the expression through exactly three particular gates, because compilation and microarchitecture intervene. Source-level correctness and circuit-level correctness require different evidence even when they describe the same eventual computation.

Validation should consequently match the claim. Truth-table enumeration checks a finite Boolean relation. Timing analysis checks setup and hold constraints under a physical model. Electrical characterization checks voltage limits and currents. A host test of the RGB function checks software encoding. None of these tests substitutes for all the others. This separation is the basis for connecting transistor theory to ChrisOS without pretending that its kernel source specifies the physical processor.

## Primary references

- [MIT 6.012 — Microelectronic Devices and Circuits](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/).
