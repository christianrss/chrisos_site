---
id: logic-levels-noise-margins
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
  - transistor-cmos
  - cmos-switching-power
  - noise-grounding-signal-integrity
related:
  - boolean-algebra
  - combinational-logic
  - clock-timing
  - transmission-lines-differential-signals
---

# Logic levels, thresholds, fan-out and noise margins

<div class="abstract">
A binary value is not a voltage. Digital hardware assigns ranges of continuous voltage to logical states and leaves a transition region in which a receiver is not guaranteed to interpret an input as either state. This chapter defines input and output limits, static noise margin, drive current, fan-out, loading, hysteresis, level translation and the interaction between signal integrity and timing. It also marks the ChrisOS abstraction boundary: the inspected ChrisCPU and kernel sources manipulate architectural bits and integer values; they do not model board-level VIH/VIL thresholds, CMOS output drive or analog noise margins.
</div>

## Prerequisites and scope

The required prerequisites are MOSFET/CMOS operation, CMOS switching energy and delay, and the electrical origins of noise and ground displacement. The purpose here is to connect transistor-level behavior to the Boolean abstraction used by digital architecture.

The abstraction boundary is:

~~~text
continuous voltage/current waveform
          |
          v
receiver input thresholds
          |
          v
recognized LOW or HIGH
          |
          v
Boolean / architectural state
~~~

A robust digital interface must guarantee that the driver's worst-case output range lies inside the receiver's guaranteed input range while satisfying current, timing and absolute-maximum constraints.

## Four limits, not one threshold

Datasheets normally distinguish input guarantees from output guarantees.

| Symbol | Meaning | Guarantee direction |
|---|---|---|
| V_IL(max) | greatest input voltage guaranteed LOW | input <= limit is LOW |
| V_IH(min) | least input voltage guaranteed HIGH | input >= limit is HIGH |
| V_OL(max) | greatest output voltage guaranteed for LOW under stated load | output <= limit |
| V_OH(min) | least output voltage guaranteed for HIGH under stated load | output >= limit |

The interval between V_IL(max) and V_IH(min) is not a third logical value. It is an **undefined input region** for the static interface contract. A particular device will switch somewhere inside its transfer characteristic, but that actual trip point varies with process, voltage, temperature, edge rate and circuit topology. A design that depends on a typical switching point instead of guaranteed limits has discarded its worst-case proof.

For an ordinary non-Schmitt CMOS input, a useful conceptual transfer curve is:

~~~text
recognized LOW       undefined          recognized HIGH
<----------------|------------------|-------------------->
               V_IL(max)          V_IH(min)
0 V                                                   V_CC
~~~

The exact limits belong to the selected logic family and operating conditions. They must not be guessed from a generic fraction of V_CC when the component datasheet specifies another contract.

Texas Instruments' logic guide, for example, shows that 5 V TTL-compatible inputs and 5 V CMOS inputs have different guaranteed ranges; Nexperia likewise documents family- and supply-dependent input/output limits. The lesson is architectural: "0" and "1" are interface contracts, not universal voltages.

## Static noise margins

A driver and receiver are statically compatible when the worst-case driven HIGH is high enough for the receiver and the worst-case driven LOW is low enough:

[
V_{OH(min,driver)} ge V_{IH(min,receiver)}
]

[
V_{OL(max,driver)} le V_{IL(max,receiver)}
]

The residual voltage budget is the static noise margin:

[
NM_H = V_{OH(min)} - V_{IH(min)}
]

[
NM_L = V_{IL(max)} - V_{OL(max)}
]

Both must be positive for a conventional direct connection under the specified conditions. If a driver guarantees V_OH(min)=2.4 V and the receiver requires V_IH(min)=2.0 V, the high-side static margin is 0.4 V. This does **not** mean that any arbitrary 0.4 V transient is harmless: pulse width, receiver bandwidth, ringing, overshoot, ground bounce and timing aperture still matter.

Noise margin is therefore a voltage-domain budget, not a complete signal-integrity proof.

## Output-level dependence on load

An output is not an ideal voltage source. The pull-up and pull-down networks have finite impedance. Datasheets therefore specify V_OH and V_OL together with output-current conditions.

A first-order Thevenin-like model for a HIGH output is a source near V_CC with effective resistance R_OH. Under source current magnitude I_OH:

[
V_{OH} approx V_{CC} - |I_{OH}|R_{OH}
]

For a LOW output sinking current I_OL through effective R_OL:

[
V_{OL} approx I_{OL}R_{OL}
]

These are explanatory approximations, not replacements for datasheet limits. They show why loading reduces margin: sourcing current pulls a HIGH downward and sinking current lifts a LOW upward.

DC loading includes receiver input leakage, pull resistors, termination networks and any other static path. Dynamic loading is often dominated by capacitance.

## Fan-out: DC and dynamic limits

Historically, fan-out often meant the number of logic inputs that one output could drive while meeting DC current limits. A conservative current-based check is:

[
N_H le rac{|I_{OH,max}|}{|I_{IH,max}|}, qquad
N_L le rac{I_{OL,max}}{I_{IL,max}}
]

and the DC fan-out is bounded by the smaller admissible count. CMOS input leakage can make this number very large, but that does not imply that an output can drive an arbitrary number of inputs at useful speed.

Every receiver contributes input capacitance, and routing contributes interconnect capacitance. With total load C_L, a first-order transition time scales with effective driver resistance:

[
	au approx R_{out} C_L
]

Increasing fan-out therefore increases edge time and propagation delay even when static current limits are satisfied. Large clock, reset or enable networks are commonly buffered as trees because one source driving all capacitance directly creates excessive delay, slew and simultaneous-switching current.

A useful design sequence is:

1. verify absolute voltage compatibility;
2. verify V_OH/V_OL against V_IH/V_IL;
3. verify static source/sink current;
4. sum input and interconnect capacitance;
5. verify edge-rate and propagation-time requirements;
6. evaluate transmission-line behavior when interconnect electrical length is significant;
7. verify overshoot, undershoot and clamp-current limits.

## Thresholds, gain and restoration

CMOS gates are useful not merely because they classify a voltage, but because they **restore** logic levels. Around the transition region an inverter has high voltage gain: a small input change can cause a large output change. Away from the transition, the output approaches a supply rail subject to loading and device limits.

This restoration prevents small analog deviations from accumulating indefinitely through a chain of properly designed logic gates. Each stage maps a valid input range back toward a valid output range.

Restoration has limits. If an input remains in the transition region, both pull-up and pull-down devices may conduct significantly. Consequences can include increased supply current, slower or multiple transitions downstream, and sensitivity to coupled noise. Ordinary CMOS inputs should therefore not be intentionally parked at an undefined voltage unless the device specification explicitly permits the use case.

## Hysteresis and Schmitt-trigger inputs

A Schmitt-trigger receiver uses different switching thresholds for rising and falling inputs:

- V_T+ for a rising input;
- V_T- for a falling input;
- hysteresis V_H = V_T+ - V_T-.

~~~text
rising edge:   LOW -------- V_T+ --------> HIGH
falling edge:  HIGH <------- V_T- -------- LOW
                       <--- V_H --->
~~~

The state depends on both present voltage and transition history inside the hysteresis band. This suppresses repeated toggling when a slow or noisy waveform crosses the decision region. Nexperia's 74LV14 documentation explicitly defines this two-threshold behavior and positions Schmitt inputs for slowly changing or noisy signals.

Hysteresis is not a license to ignore maximum input transition times, protection limits or analog bandwidth. The device-specific datasheet remains authoritative.

## TTL-compatible and CMOS-compatible interfaces

Logic-family names encode different electrical contracts. A 5 V CMOS output may drive a TTL-compatible input comfortably, while a legacy TTL HIGH guarantee may be insufficient for a 5 V CMOS input that requires a much higher V_IH. Supply voltage equality alone does not prove compatibility.

Similarly, modern low-voltage families may provide 5 V-tolerant inputs without producing 5 V outputs. "5 V tolerant" describes an input stress capability under specified conditions; it does not mean that the device operates internally at 5 V or translates both directions automatically.

The correct compatibility relation is directional:

~~~text
driver output specification
          |
          +--> receiver input thresholds
          +--> receiver absolute maximum ratings
          +--> current / clamp constraints
          +--> timing / slew constraints
~~~

The reverse direction must be checked separately for a bidirectional bus.

## Level translation

When output and input contracts do not overlap with adequate margin, a level translator is required. Translation strategies include dedicated dual-supply translators, single-supply translating logic, open-drain/open-collector interfaces with an appropriate pull-up, resistor networks for suitable unidirectional cases, and protocol-specific transceivers.

A translator must be selected by directionality, voltage domains, edge rate, drive current, power sequencing, partial-power-down behavior and whether the signal is push-pull or open-drain. A resistor divider that is acceptable for a slow unidirectional CMOS input is not a general substitute for a bidirectional high-speed translator.

Nexperia's 74LV1T08 is an example of single-supply translating logic: its input threshold arrangement permits specified translation combinations while the output level follows its supply. That behavior is a property of the device specification, not of an AND gate in the abstract.

## Ground reference, bounce and simultaneous switching

Logic thresholds are measured relative to a reference. The transmitter's "ground" and receiver's local reference are not perfectly identical during fast current changes. Package inductance, return-path inductance and power-distribution impedance produce transient reference movement.

If a receiver sees signal voltage V_signal and local reference V_GND,RX, its relevant single-ended input is approximately:

[
V_{IN,RX}=V_{signal}-V_{GND,RX}
]

A positive signal excursion can therefore lose effective margin if receiver ground moves upward. Simultaneous switching of many outputs can create ground bounce and supply droop, shrinking both noise and timing margins.

Decoupling, short return paths, controlled impedance, appropriate pin assignment and bounded edge rates are part of preserving the digital abstraction.

## Transmission-line effects and edge rate

A trace that is electrically short relative to transition time can often be treated as lumped capacitance. When propagation delay is no longer negligible relative to edge time, reflections must be considered. A receiver can momentarily observe a voltage different from the final DC level.

The relevant question is not merely clock frequency. A low-frequency bus with sub-nanosecond edges can exhibit transmission-line behavior because edge spectral content extends far above the fundamental toggle rate.

Termination and topology are therefore chosen from interconnect impedance, source impedance, load distribution and timing requirements. Static V_OH/V_OL compatibility remains necessary but is not sufficient.

## Timing interaction

A receiving flip-flop requires its input to be stable around the sampling edge according to setup and hold constraints. Noise can become a timing error even without permanently changing the DC state: ringing or a slow threshold crossing changes the time at which the receiver recognizes the transition.

For a monotonic input V(t), threshold uncertainty ΔV maps approximately to timing uncertainty:

[
Delta t approx rac{Delta V}{|dV/dt|}
]

A slower slew rate therefore converts the same voltage uncertainty into greater edge-time uncertainty. This is one reason signal integrity and timing closure cannot be separated completely.

## Undefined, high-impedance and contention states

The electrical layer has conditions that Boolean algebra alone does not represent.

**Undefined input region:** voltage is between guaranteed LOW and HIGH ranges.

**High impedance (Z):** an output driver is disabled and does not intentionally drive either rail. The node voltage is then determined by other drivers, pulls, leakage and capacitance.

**Contention:** two enabled push-pull drivers attempt opposite values. Current can become excessive and the resulting voltage may be undefined.

**Floating input:** no low-impedance source establishes a valid level. Leakage and coupled charge can move the node through the transition region.

These conditions must be resolved by bus ownership, output-enable protocols, pulls and electrical design.

## ChrisOS architectural boundary

The ChrisOS revision reviewed for this chapter is `da3df29cb397932c43d32373871fb9380e688ade`.

The inspected sources establish a software abstraction boundary rather than an electrical implementation model:

| Source | Relevant observed abstraction |
|---|---|
| `chrisvm/chris_arch.h` | `ChrisArchitectureState` represents architectural machine state as software data |
| `chrisvm/cpu/emulator/chriscpu.c` | `cpu_run` advances emulated architectural execution |
| `kernel/gfx/graphics.c` | `gfx_rgb` constructs a digital pixel value |

These files do not specify processor pad V_IH/V_IL, V_OH/V_OL, board fan-out, package drive strength, I/O-standard termination or measured noise margins. No such behavior is inferred here.

Conceptually:

~~~text
physical machine
voltage -> receiver -> bit -> architectural state
                         ^
                         |
ChrisCPU starts here ----+

kernel software operates on the architectural bit/value model
~~~

The distinction matters when ChrisOS moves toward physical hardware bring-up. Firmware and drivers can configure I/O controllers, but electrical compatibility remains a property of the processor/chipset/board interface specifications and layout.

## State, algorithms, ownership and complexity

There is no ChrisOS runtime data structure for analog logic thresholds in the inspected sources, so assigning one would be fictitious. At the electrical-design level, compatibility checking can be expressed as a bounded set of inequalities per connection.

For each driver-receiver edge:

~~~text
assert VOH_min(driver, load) >= VIH_min(receiver)
assert VOL_max(driver, load) <= VIL_max(receiver)
assert receiver absolute limits are respected
assert source/sink current limits are respected
assert edge/timing limits are respected
~~~

For E electrical connections, a table-driven static compatibility pass is O(E) time and O(1) additional working storage beyond the interface database and report. Full signal-integrity simulation is a different problem and can require distributed interconnect and nonlinear device models.

Ownership at runtime belongs to the hardware that drives a net; bus protocols determine which output may be enabled. In software architectural state, ownership and synchronization are instead governed by emulator/kernel data structures and concurrency rules documented in their own chapters.

## Failure modes and containment

| Failure | Electrical mechanism | Typical consequence |
|---|---|---|
| negative noise margin | incompatible guaranteed ranges | nondeterministic logic interpretation |
| excessive DC fan-out | output current exceeds valid-load condition | degraded V_OH/V_OL |
| excessive capacitive fan-out | large RC load | slow edges, timing failure |
| floating CMOS input | leakage/coupling controls node | toggling, excess current |
| push-pull contention | opposing drivers enabled | overcurrent, undefined voltage |
| ground bounce | shared inductive return | apparent threshold crossing |
| ringing | impedance discontinuity | false/multiple crossings |
| slow non-Schmitt edge | long residence near threshold | jitter, excess current |
| over/undershoot | interconnect transient | clamp current or reliability stress |

Containment starts with specification-compatible interfaces, explicit pulls and ownership, then extends to layout, termination, decoupling and validation with appropriate instruments.

## Privilege and security implications

Logic levels are below the CPU privilege model, but electrical faults can cross security boundaries indirectly. A marginal clock, reset, memory or peripheral interface can corrupt architectural state before software protection mechanisms execute. Fault-injection research deliberately exploits voltage, clock or electromagnetic disturbances for this reason.

This chapter does not claim ChrisOS implements defenses against physical fault injection. The inspected software sources do not establish such a mechanism.

## Performance and trade-offs

Greater drive strength can charge capacitance faster but increases simultaneous-switching current, electromagnetic emission and ringing risk. Stronger termination can improve waveform quality while increasing static or dynamic power. Wider noise margin improves robustness, but lowering supply voltage reduces available voltage headroom even as it can reduce switching energy.

Schmitt inputs improve tolerance of slow/noisy transitions but introduce hysteresis and family-specific thresholds. Level translators restore compatibility across voltage domains but add propagation delay, power, cost and sequencing constraints.

There is no universal optimum; the interface must satisfy voltage, current, timing, power and integrity constraints simultaneously.

## Validation evidence

For the theory layer, this chapter was checked against current manufacturer primary documentation: Texas Instruments' *Logic Guide* (SDYU001AC, revised November 2025) for logic-level terminology and compatibility, and Nexperia's *Logic Application Handbook* plus 74LV14/74LV1T08 device documentation for guaranteed levels, hysteresis and translation behavior.

For ChrisOS, evidence in this revision is source inspection only. This chapter does not report oscilloscope measurements, I/O-pad characterization, FPGA timing reports or physical-board validation.

A hardware validation plan would measure at least:

- supply and ground at the receiver reference;
- V_OH/V_OL under specified load;
- rise/fall time and propagation delay;
- overshoot, undershoot and ringing;
- simultaneous-switching disturbance;
- setup/hold margin at sampling interfaces;
- behavior across supported voltage and temperature ranges.

## Current limitations

The current documentation boundary has no board-specific I/O-voltage database and no measured ChrisOS hardware signal-integrity corpus. Generic TTL/CMOS examples cannot substitute for the datasheet of the actual processor, FPGA, memory or peripheral used in a future hardware target.

The equations above are first-order reasoning tools. They do not replace IBIS/SPICE models, package parasitics, transmission-line extraction or manufacturer characterization where those are required.

## Roadmap

Future physical-hardware documentation should bind each implemented board interface to its authoritative electrical specification, voltage domain, termination, pull configuration and measured validation evidence. If ChrisVM later acquires an explicit board/electrical fault model, that model should be documented separately from architectural CPU semantics.

No roadmap item in this section is claimed as current ChrisOS behavior.

## Revision provenance

- ChrisOS implementation revision reviewed: `da3df29cb397932c43d32373871fb9380e688ade`.
- Current implementation sources inspected: `chrisvm/chris_arch.h`, `chrisvm/cpu/emulator/chriscpu.c`, `kernel/gfx/graphics.c`.
- Primary electrical references reviewed: TI *Logic Guide* SDYU001AC; Nexperia *Logic Application Handbook*; Nexperia 74LV14 and 74LV1T08 documentation.
- Architectural conclusion: current inspected ChrisOS software consumes the digital abstraction; it does not model transistor/pad electrical thresholds.
