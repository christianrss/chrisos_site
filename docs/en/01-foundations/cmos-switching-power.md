---
id: cmos-switching-power
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
  - mos-capacitor
  - transistor-cmos
  - capacitance-inductance
  - power-delivery-regulation
related:
  - logic-levels-noise-margins
  - combinational-logic
  - clock-timing
  - latches-flipflops
---

# CMOS switching, delay and power

<div class="abstract">
CMOS logic obtains useful digital behavior by repeatedly charging and discharging physical capacitances through transistor networks with finite resistance and finite transition time. The stable Boolean function is only one layer of the mechanism. Performance depends on charge movement, effective drive, fan-out, parasitic capacitance, input slew and path topology; power depends on switching activity, supply voltage, frequency, short-circuit current and leakage. This chapter derives first-order CMOS delay and energy models, explains glitching, sizing, fan-out, clock loading, power-delay trade-offs and the coupling between logic activity and the power-delivery network. It then reconciles the ChrisOS boundary: architectural-state updates in ChrisCPU and bitwise operations in kernel code are software-visible behavior, not transistor switching counts, physical capacitance or measured processor power.
</div>

## Prerequisites and scope

This chapter assumes:

- MOS capacitor accumulation, depletion and inversion;
- MOSFET and CMOS inverter operation;
- capacitance and stored energy;
- resistance and RC transients;
- power-delivery impedance and supply droop;
- Boolean logic and propagation delay.

The central abstraction stack is:

~~~text
Boolean transition
      ↓
transistor network changes conduction
      ↓
node capacitances charge or discharge
      ↓
analog waveform crosses receiver threshold
      ↓
new logical value becomes valid
~~~

Static truth tables describe only the endpoints.

Delay and power require the continuous transition between those endpoints.

## The CMOS inverter as a switching system

A CMOS inverter has:

- a PMOS pull-up path to V_DD;
- an NMOS pull-down path to ground;
- an output node with effective load capacitance C_L.

Conceptually:

~~~text
V_DD
 |
PMOS
 |
 +------ output ---- C_L
 |
NMOS
 |
GND
~~~

When the output goes low-to-high, the PMOS network supplies charge to C_L.

When the output goes high-to-low, the NMOS network removes charge from C_L.

The ideal Boolean result is NOT(input), but the physical transition takes finite time.

## Effective load capacitance

C_L is not one literal capacitor.

It can include:

- input capacitance of driven gates;
- transistor drain junction capacitance;
- interconnect capacitance;
- coupling capacitance;
- package or I/O capacitance where relevant.

A first-order lumped model writes:

~~~text
C_L = C_gate + C_diffusion + C_wire + C_other
~~~

The decomposition depends on physical design.

At sufficiently high speed or long interconnect, a distributed RC or transmission-line model can be more appropriate than one lumped C_L.

## Charging a capacitive node

For an ideal capacitor charged from 0 to V_DD:

~~~text
Q = C_L V_DD
~~~

The final stored energy is:

~~~text
E_stored = 1/2 C_L V_DD²
~~~

An ideal voltage source charging through a resistive path delivers:

~~~text
E_from_supply = C_L V_DD²
~~~

The other half:

~~~text
E_dissipated_charge = 1/2 C_L V_DD²
~~~

is dissipated in the charging path in the simple RC model.

When the node later discharges to ground, the stored half is dissipated in the pull-down path.

Therefore one complete 0→1→0 cycle draws approximately:

~~~text
E_cycle = C_L V_DD²
~~~

from the supply in the ideal first-order CMOS dynamic model.

## Dynamic switching power

If a node has probability/activity factor α of making a 0→1 transition per clock opportunity and opportunities occur at frequency f:

~~~text
P_dynamic = α C_L V_DD² f
~~~

Conventions for α differ across texts.

Some define activity in terms of all transitions rather than 0→1 charging events.

Therefore any numeric use of α must state its definition.

The robust dependencies are:

~~~text
P_dynamic ∝ activity
P_dynamic ∝ capacitance
P_dynamic ∝ V_DD²
P_dynamic ∝ frequency
~~~

The quadratic voltage term makes supply-voltage reduction especially powerful for dynamic energy.

## Numerical example

Suppose:

~~~text
C_L = 10 fF
V_DD = 1.0 V
α = 0.2
f = 1 GHz
~~~

Then:

~~~text
P_dynamic
=
0.2 · 10e-15 · 1² · 1e9
=
2 µW
~~~

for that modeled node.

A real chip contains many nodes with different capacitances and activities, so total dynamic power is a sum.

This example is illustrative and is not a power estimate for any processor running ChrisOS.

## Transition energy and supply current

A low-to-high transition requires charge:

~~~text
ΔQ = C_L ΔV
~~~

If it occurs in transition time Δt, average charging current magnitude is approximately:

~~~text
I_avg ≈ ΔQ / Δt
~~~

Faster transitions therefore demand larger transient current for the same C and voltage swing.

That current flows through the PDN.

Thus logic activity couples directly to:

- local droop;
- package inductance;
- ground bounce;
- regulator transient response.

CMOS timing and power integrity cannot be separated completely.

## First-order RC delay

Treat the conducting transistor network as effective resistance R_eq charging or discharging C_L.

For a first-order RC response:

~~~text
V_charge(t)
=
V_DD (1 - e^(-t/(R_eq C_L)))
~~~

The time to reach 50 percent V_DD is:

~~~text
t_50
=
ln(2) R_eq C_L
≈
0.693 R_eq C_L
~~~

A common first-order propagation-delay estimate is therefore:

~~~text
t_p ∝ R_eq C_L
~~~

The proportionality constant depends on the threshold definition and waveform.

## Rise and fall delay

Pull-up and pull-down paths need not have identical effective resistance.

Define approximately:

~~~text
t_pLH
≈
0.69 R_p C_L

t_pHL
≈
0.69 R_n C_L
~~~

Then average propagation delay is often summarized as:

~~~text
t_p
=
(t_pLH + t_pHL) / 2
~~~

This is a pedagogical RC model.

Modern standard-cell timing is characterized with richer nonlinear models over input slew, output load, voltage, process and temperature.

## Input slew matters

The input itself does not switch infinitely fast.

A slow input causes pull-up and pull-down devices to spend longer in intermediate conduction states.

Consequences can include:

- larger propagation delay;
- larger short-circuit current;
- greater timing uncertainty;
- different output slew.

Therefore delay is better described as a function:

~~~text
delay
=
F(
  input slew,
  output capacitance,
  supply,
  process,
  temperature
)
~~~

rather than one fixed number per gate.

## Short-circuit current

During an input transition, NMOS and PMOS can both conduct simultaneously for a finite interval.

That creates a direct current path:

~~~text
V_DD
  ↓
PMOS partly on
  ↓
NMOS partly on
  ↓
GND
~~~

The resulting short-circuit or crowbar power is additional to ideal capacitive switching power.

It depends on:

- input slew;
- transistor sizing;
- supply voltage;
- threshold voltages;
- output loading.

An infinitely fast ideal input would reduce the overlap interval, but real edges are finite.

## Leakage power

CMOS is not perfectly static.

Leakage mechanisms include:

- subthreshold current;
- reverse-biased junction leakage;
- gate tunneling;
- gate-induced drain leakage and related device effects in scaled technologies.

A first-order total static-power relation is:

~~~text
P_leak ≈ V_DD I_leak
~~~

I_leak depends strongly on:

- temperature;
- threshold;
- process;
- device state;
- geometry.

At advanced nodes, leakage can be a substantial part of total power.

## Temperature feedback

Electrical power becomes heat.

Rising temperature can increase leakage.

That produces a feedback path:

~~~text
more power
   ↓
higher temperature
   ↓
more leakage
   ↓
more power
~~~

Thermal management and circuit design must keep the operating point stable.

The exact relation is technology-specific.

## Fan-out

A gate driving more gate inputs sees larger total input capacitance.

If each load contributes approximately C_in:

~~~text
C_load
≈
N C_in + C_wire + C_parasitic
~~~

for fan-out N in a simplified model.

Larger fan-out therefore increases:

- delay;
- charging energy;
- transient current.

A Boolean net can have one logical value and still be physically expensive to distribute.

## Transistor sizing

Increasing transistor width generally increases drive capability, reducing effective on resistance.

But larger width also increases:

- gate capacitance presented to the preceding stage;
- diffusion capacitance;
- area;
- dynamic energy.

Thus:

~~~text
wider device
    ↓
stronger drive
but
larger capacitance
~~~

Sizing is an optimization across the entire path, not one gate in isolation.

## Buffer chains

A very small gate should not always drive a huge load directly.

A chain of progressively larger buffers can distribute the capacitance ratio.

Conceptually:

~~~text
small gate
  ↓
medium buffer
  ↓
larger buffer
  ↓
large load
~~~

Each stage adds intrinsic delay but reduces the extreme load seen by the preceding stage.

The optimum staging depends on the delay model, parasitics and physical library.

## Logical effort as an abstraction

Logical effort separates a gate's topology-dependent difficulty from its electrical fan-out.

In a simplified model, stage delay is written conceptually as:

~~~text
d = g h + p
~~~

where:

- g is logical effort;
- h is electrical effort or capacitance ratio;
- p is parasitic delay.

This model is useful for reasoning about path sizing.

It is not a transistor-level timing signoff method.

## Elmore delay intuition

For a distributed RC network, delay depends on where capacitance is located relative to upstream resistance.

The Elmore first-moment approximation can be written conceptually as:

~~~text
t_delay
≈
Σ_i R_common,i C_i
~~~

where each capacitance is weighted by resistance common to the source-to-capacitor path.

This explains why long resistive interconnect can dominate gate delay.

Physical timing tools use richer extraction and models, but Elmore delay provides useful intuition.

## Series transistor stacks

A CMOS NAND pull-down network may place NMOS devices in series.

Series conduction raises effective resistance compared with one device of the same size.

A NOR pull-up can similarly contain series PMOS devices.

Consequences include topology-dependent:

- delay;
- sizing;
- logical effort;
- parasitic capacitance.

A truth table alone does not expose this cost.

## Internal node capacitance

Complex gates can contain internal diffusion nodes.

Those nodes can charge or discharge even when the output does not make a full rail-to-rail transition.

Internal switching contributes energy and delay.

A gate-level model that counts only output transitions may therefore underestimate physical activity.

## Glitching and hazards

Combinational paths rarely have exactly equal delay.

Suppose two logically related inputs reach a gate at different times.

The output can briefly change even though its final Boolean value should remain unchanged.

That transient is a glitch.

A glitch can:

- consume dynamic energy;
- propagate downstream;
- reduce timing margin;
- create unwanted pulses if captured.

The final truth table does not describe this switching activity.

## Activity factor

For power estimation, each node can be assigned an activity factor.

Conceptually:

~~~text
α_i
=
expected charging events per reference interval
~~~

Then:

~~~text
P_dynamic,total
≈
Σ_i α_i C_i V_DD² f
~~~

Activity depends on:

- workload;
- data statistics;
- clock gating;
- logic topology;
- glitches;
- architectural state transitions.

It cannot generally be inferred from static source code alone.

## Clock power

Clock networks switch regularly and drive many sequential elements.

They can therefore contribute substantial dynamic power.

A clock-distribution tree contains:

- buffers;
- wire capacitance;
- local clock pins;
- gating structures.

Clock activity is often close to deterministic while enabled.

Clock gating reduces unnecessary switching by preventing parts of the tree or downstream sequential logic from toggling when no state update is required.

## Data gating and operand isolation

Unnecessary combinational activity can be reduced by preventing irrelevant inputs from toggling internal logic.

Techniques include:

- operand isolation;
- enable-based gating;
- architectural clock gating;
- power gating at larger granularity.

These techniques require correctness conditions.

Saving energy cannot violate state-update semantics.

## Power gating

Power gating disconnects a block from its supply using sleep transistors or equivalent physical mechanisms.

Potential benefits:

- greatly reduced leakage in an inactive block.

Costs and constraints include:

- wake-up latency;
- state retention or loss;
- inrush current;
- area;
- power-domain isolation;
- sequencing.

Power gating is a physical design feature, not an operating-system assumption unless the hardware exposes a controlled interface.

## Dynamic voltage and frequency scaling

A simplified dynamic-power model is:

~~~text
P_dynamic = α C V² f
~~~

Reducing V decreases dynamic power quadratically.

Reducing f decreases it approximately linearly.

However maximum safe frequency generally depends on voltage because lower voltage reduces transistor overdrive and current drive.

Thus DVFS couples performance and voltage:

~~~text
lower V
    ↓
lower dynamic energy
but
slower circuits / reduced timing margin
~~~

The actual voltage-frequency table belongs to the processor/platform.

## Energy per operation

If an operation causes a set of nodes to switch, a first-order energy model is:

~~~text
E_operation
≈
Σ_i transitions_i · C_i V_DD²
+
short-circuit energy
+
leakage energy during execution
~~~

This is more informative than power alone when comparing operations that finish at different times.

But mapping software instructions to transistor-level node transitions requires microarchitectural and circuit knowledge.

## Power-delay product

One simple metric is:

~~~text
PDP = power · delay
~~~

which has units of energy.

Another is energy-delay product:

~~~text
EDP = energy · delay
~~~

These metrics weight efficiency and performance differently.

No single metric is universally optimal.

Battery life, thermal density, throughput and latency can demand different objectives.

## Critical paths

A synchronous pipeline clock period must exceed the worst relevant path delay plus timing margins.

A simplified relation is:

~~~text
T_clk
>=
t_clk-q
+
t_logic,max
+
t_setup
+
t_skew/jitter_margin
~~~

The logic term is built from transistor/gate/interconnect delays.

Reducing average power does not automatically improve worst-case timing.

Likewise, a path that rarely toggles can still determine maximum clock frequency.

## Process, voltage and temperature variation

Gate delay and leakage depend on PVT:

~~~text
process
voltage
temperature
~~~

Examples:

- slower device corner increases delay;
- lower supply often increases delay;
- higher temperature can alter mobility and leakage.

Timing and power signoff therefore use characterized operating corners and statistical models.

One nominal RC estimate is educational, not signoff evidence.

## Noise and delay interaction

Supply droop can reduce transistor drive during a transition.

That increases delay and can alter output slew.

Ground bounce can shift local thresholds.

Crosstalk can either speed or slow a victim transition depending on aggressor direction and timing.

Thus:

~~~text
signal integrity
+
power integrity
+
timing
~~~

are coupled.

## Energy conservation and the PDN

Every 0→1 charge event draws energy from the supply network.

At chip scale, many simultaneous transitions create a current transient:

~~~text
I_total(t)
=
Σ_i C_i dV_i/dt
+
short-circuit current
+
leakage
+
analog/support currents
~~~

The regulator and decoupling hierarchy must support this current while maintaining rail voltage.

This directly connects the previous power-delivery chapter to gate-level activity.

## State storage and switching

Latches and flip-flops contain feedback nodes and clocked transistor networks.

Their power includes:

- internal clock switching;
- data-dependent internal switching;
- output load;
- leakage.

A register that holds its logical value can still consume clock-tree energy unless the relevant clock is gated.

The later sequential-logic chapters develop the state semantics; this chapter explains the physical cost of transitions.

## CMOS power is not source-code operation count

A software expression such as:

~~~text
(red << 16) | (green << 8) | blue
~~~

can compile into a sequence of machine instructions.

The processor may execute those instructions using:

- pipelines;
- renamed physical registers;
- caches;
- branch prediction;
- multiple execution units;
- clock gating;
- speculative activity.

Therefore source-level operators do not map one-to-one to:

- CMOS gates;
- transistor transitions;
- capacitance charged;
- joules consumed.

The abstraction boundary must remain explicit.

## ChrisOS source reconciliation

Current ChrisOS revision da3df29cb397932c43d32373871fb9380e688ade exposes architectural and software state, not transistor-level power state.

The reviewed sources are:

~~~text
chrisvm/chris_arch.h
chrisvm/cpu/emulator/chriscpu.c
kernel/gfx/graphics.c
~~~

The concrete symbols are:

~~~text
ChrisArchitectureState
cpu_run
gfx_rgb
~~~

These sources establish the upper abstraction boundary.

## ChrisArchitectureState

ChrisArchitectureState records software-visible architectural quantities such as:

- general-purpose registers;
- RIP;
- RFLAGS;
- control registers;
- segment state;
- selected MSRs;
- XMM state;
- a modeled TSC.

It does not record:

- transistor capacitance;
- gate delay;
- rail current;
- clock-tree activity;
- die temperature;
- leakage.

An architectural state vector is not a physical switching-state vector.

## cpu_run

The ChrisCPU cpu_run loop:

- fetches bytes;
- decodes an instruction;
- executes modeled instruction semantics;
- updates RIP when appropriate;
- handles modeled interrupts;
- increments step and modeled TSC counters.

The increments:

~~~text
cpu->steps++
cpu->arch.tsc++
~~~

do not represent physical clock-tree transitions or joules consumed by a real CPU.

They are emulator-model counters.

This distinction is essential when connecting software execution to CMOS energy.

## gfx_rgb

gfx_rgb packs three 8-bit channels using shifts and OR operations.

It establishes a software representation rule:

~~~text
red   -> bits 16..23
green -> bits 8..15
blue  -> bits 0..7
~~~

It does not establish how many transistor gates a compiler or CPU uses to execute the expression.

Different processors or compiled instruction sequences can realize the same software result with different physical switching activity.

## Initialization boundary

There is no CMOS power-model initialization in the cited ChrisOS source.

ChrisCPU initializes architectural emulator state.

Graphics initializes buffers and framebuffer metadata.

Neither path initializes:

- transistor capacitance tables;
- standard-cell timing libraries;
- voltage-frequency curves;
- leakage models.

Therefore no transistor-power initialization is inferred.

## State and data structures

The physical state relevant to CMOS switching includes:

~~~text
node voltages
node charges
transistor conduction states
supply current
local temperature
clock phase
~~~

Those quantities are not stored in ChrisArchitectureState.

ChrisArchitectureState is a software model of ISA-visible state.

The invariant is:

~~~text
architectural state
!=
microarchitectural state
!=
transistor electrical state
~~~

## Algorithms and complexity

Computing the simple dynamic-power equation for one node is O(1).

Summing a known list of N node activities is O(N).

Detailed circuit simulation can be far more expensive because it solves nonlinear differential/algebraic equations over many devices and time points.

ChrisCPU instruction emulation complexity is a different problem.

Its step loop cannot be used as evidence of transistor simulation complexity.

## Memory ownership

Current ChrisOS has no owned data structure for physical CMOS power.

The cited emulator owns architectural state and machine-model structures.

Graphics owns framebuffer/backbuffer state.

None of those buffers is a power waveform or gate-level netlist.

A future power-estimation tool would need explicit ownership for:

- event traces;
- capacitance models;
- activity counters;
- voltage/frequency state;
- thermal state.

## ABI boundary

The ISA and device ABIs expose functional behavior.

They generally do not expose every internal transistor transition.

Even hardware performance counters, when available, are aggregate microarchitectural events rather than direct transistor counts.

Current cited ChrisOS sources define no ABI for:

- measured watts;
- joules per instruction;
- node capacitance;
- rail current;
- transistor leakage.

## Concurrency

Real silicon switches many nodes concurrently.

ChrisCPU, in the reviewed emulator path, executes its modeled CPU loop according to software control.

Physical electrical concurrency and software-thread concurrency are different concepts.

No lock in the kernel can serialize transistor switching inside the host CPU.

Conversely, multiple software threads can increase physical switching indirectly by increasing workload.

## Failure and recovery

CMOS-level failure modes include:

| Mechanism | Possible effect |
|---|---|
| excessive path delay | timing violation |
| excessive supply droop | slower transition or logic error |
| high leakage | thermal/power budget violation |
| overheating | throttling, fault or damage |
| excessive electric field | reliability degradation |
| clock instability | sampling failure |
| excessive crosstalk | timing/noise failure |

Software may observe:

- incorrect computation;
- reset;
- machine-check behavior;
- device timeout;
- performance throttling.

Those symptoms are not sufficient to identify one physical mechanism.

## Security and privilege

Dynamic power and timing can leak information about computation.

Examples of physical-security research include:

- timing side channels;
- power analysis;
- electromagnetic analysis;
- voltage/clock fault injection.

This chapter does not assert a specific ChrisOS exploit.

The security lesson is architectural: software-visible behavior can modulate lower-level physical activity even though the software does not directly address transistors.

## Performance trade-offs

CMOS optimization is multiobjective.

| Decision | Speed effect | Power/energy effect |
|---|---|---|
| increase width | stronger drive | larger capacitance/leakage |
| raise V_DD | faster switching | quadratic dynamic-energy increase |
| raise frequency | more throughput | roughly linear dynamic-power increase |
| add buffering | reduces extreme fan-out delay | extra internal capacitance |
| clock gate | little active-path effect when enabled | lowers idle switching |
| power gate | wake-up penalty | reduces leakage |
| slower edge | can reduce noise/short-circuit interactions | may increase delay |

The optimum depends on workload, physical library and product constraints.

## Validation evidence for this chapter

The deterministic checker validates illustrative first-order relationships:

~~~text
stored capacitor energy:
    E = 1/2 C V²

full charge-discharge supply energy:
    E_cycle = C V²

dynamic power:
    P = α C V² f

charge:
    Q = C V

average transition current:
    I = ΔQ/Δt

RC 50-percent delay:
    t_50 = ln(2) R C

fan-out capacitance:
    C_load = N C_in + C_wire

PDN coupling:
    ΔV = Z_PDN ΔI
~~~

The source-contract portion checks the current ChrisOS symbols and explicitly verifies that architecture/emulator sources do not claim transistor-level power state.

The checker is not silicon power characterization.

## Current limitations

This chapter does not provide:

- a foundry standard-cell library;
- SPICE netlists;
- extracted parasitic networks;
- BSIM parameters;
- measured host-CPU power;
- hardware performance-counter energy calibration;
- processor DVFS tables;
- transistor-level ChrisCPU simulation;
- timing signoff.

Those require implementation/process/hardware evidence beyond the current repository.

## Roadmap boundary

The conceptual progression is:

~~~text
MOS electrostatics
      ↓
MOSFET conduction
      ↓
CMOS pull-up/pull-down logic
      ↓
node capacitance and RC delay
      ↓
dynamic + short-circuit + leakage power
      ↓
fan-out and path timing
      ↓
logic thresholds and noise margins
      ↓
sequential timing and clocking
~~~

The next missing curriculum chapter, logic-levels-noise-margins, formalizes logic-family voltage thresholds, input/output loading and restoration on top of the device-level switching behavior developed here.

## Revision provenance

Implementation-facing claims were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

The exact reviewed sources are chrisvm/chris_arch.h, chrisvm/cpu/emulator/chriscpu.c and kernel/gfx/graphics.c, with symbols ChrisArchitectureState, cpu_run and gfx_rgb.

Physical theory was cross-checked against MIT 6.012 material on MOS capacitors, CMOS inverter behavior and CMOS scaling. SI quantities follow the BIPM SI Brochure 9th edition version 4.01.

No mapping from ChrisCPU step count or kernel source operators to real transistor energy is claimed.
