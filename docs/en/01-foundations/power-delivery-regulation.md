---
id: power-delivery-regulation
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/acpi.c
  - kernel/metal/acpi.h
  - docs/CURRENT_HARDWARE_AUDIT.md
  - docs/REAL_HARDWARE_PLAN.md
symbols:
  - acpi_probe
depends_on:
  - noise-grounding-signal-integrity
  - ac-signals-frequency-impedance
  - rc-rlc-transients
related:
  - cmos-switching-power
  - clock-timing
  - acpi-platform
  - installation-real-hardware
---

# Power delivery, regulation and decoupling

<div class="abstract">
A digital system requires a stable supply only in the logical sense; physically, every switching event draws time-varying current through a distribution network with finite resistance, inductance, capacitance and regulator bandwidth. Power integrity is the problem of keeping supply and reference rails inside their electrical limits across frequencies ranging from the upstream power source and voltage-regulator control loop to package and die transients. This chapter develops regulation, converter operation, load transients, target impedance, decoupling, ESR/ESL, anti-resonance, load-line behavior, sequencing, protection, efficiency, measurement and thermal trade-offs. It then reconciles the software boundary: current ChrisOS ACPI discovery can report selected ACPI table signatures but does not implement motherboard VRM control, ACPI power-state policy, suspend/resume or a power-rail telemetry subsystem.
</div>

## Prerequisites and scope

This chapter assumes:

- voltage, current, resistance, energy and power;
- capacitors and inductors;
- RC/RL/RLC transients;
- AC impedance and frequency response;
- noise, grounding and signal-integrity foundations;
- basic control-loop terminology.

The physical path is broader than one regulator:

~~~text
external source
    ↓
power supply / adapter
    ↓
board-level conversion
    ↓
voltage regulator module
    ↓
planes and vias
    ↓
package
    ↓
on-die distribution
    ↓
transistors and logic
~~~

Every stage contributes impedance and dynamic limits.

Power delivery and software power management are related but distinct. Software can request states or change workload; it does not directly repeal the electrical dynamics of the PDN.

## Why a supply rail moves

For a load current i(t) flowing through a nonzero supply impedance Z_PDN,

~~~text
ΔV(ω) = Z_PDN(ω) · ΔI(ω)
~~~

This is the central small-signal relationship of power integrity.

A rail remains inside specification only when the product of current disturbance and network impedance stays inside the allowed voltage deviation.

The PDN is frequency-dependent because:

- resistance dominates some low-frequency losses;
- regulator control acts over a finite bandwidth;
- capacitors dominate selected bands;
- parasitic inductance dominates at sufficiently high frequency;
- package and die structures add additional resonances.

A single DC resistance number therefore cannot characterize rail quality.

## Allowed droop and target impedance

Suppose the maximum allowed supply deviation is ΔV_allowed for a worst-case current step ΔI_step.

A common first-order target-impedance criterion is:

~~~text
Z_target = ΔV_allowed / ΔI_step
~~~

Example:

~~~text
nominal rail       = 1.0 V
allowed deviation  = 30 mV
current step       = 20 A

Z_target
=
0.030 / 20
=
1.5 mΩ
~~~

The engineering objective is to keep the relevant PDN impedance below the target over the frequency range that contributes materially to the load transient.

The criterion is useful but not sufficient by itself. The actual load waveform, regulator dynamics, package/die network and measurement point matter.

## Time-domain load transient

A sudden increase in current produces several first-order voltage components:

~~~text
resistive:
    ΔV_R = ΔI · R

inductive:
    ΔV_L = L · dI/dt

capacitive:
    ΔV_C = (1/C) ∫ i_deficit(t) dt
~~~

The three mechanisms occur together.

A simplified sequence is:

~~~text
load current rises
      ↓
local capacitors respond first
      ↓
package/board inductance produces L·di/dt drop
      ↓
bulk capacitance supplies intermediate energy
      ↓
regulator control loop increases delivered current
      ↓
rail returns toward regulated operating point
~~~

No single capacitor spans all time scales efficiently.

## Regulation

A voltage regulator compares an output-related feedback signal with a reference and adjusts a power stage to reduce error.

Conceptually:

~~~text
reference
   ↓
error amplifier / controller
   ↓
power stage
   ↓
LC/output network
   ↓
load
   └──────── feedback ────────↑
~~~

The loop has finite bandwidth, delay and stability margin.

A regulator cannot respond instantaneously to arbitrarily fast load changes.

Fast transient energy must come from energy already stored near the load.

## Linear regulation

A linear regulator controls a pass element continuously.

A first-order efficiency limit for an idealized linear regulator is approximately:

~~~text
η ≈ V_out / V_in
~~~

when load current dominates quiescent current.

The dissipated power is approximately:

~~~text
P_loss ≈ (V_in - V_out) · I_load
~~~

Advantages can include simplicity and low noise.

Disadvantages include potentially high dissipation for large voltage drops or currents.

Modern CPU/core rails are therefore generally associated with switching conversion rather than high-drop linear regulation.

## Switching regulation

A switching regulator transfers energy through switched states and reactive storage.

Common topologies include:

- buck;
- boost;
- buck-boost families;
- multiphase converters;
- isolated topologies upstream.

For a basic ideal continuous-conduction buck converter:

~~~text
V_out ≈ D · V_in
~~~

where D is the duty ratio.

The inductor current changes according to:

~~~text
di_L/dt = V_L / L
~~~

During the high-side interval:

~~~text
V_L,on ≈ V_in - V_out
~~~

During the low-side interval:

~~~text
V_L,off ≈ -V_out
~~~

Steady-state volt-second balance requires average inductor voltage over a switching period to be approximately zero.

## Buck inductor ripple

For switching period T_s and duty D, a first-order continuous-conduction ripple estimate is:

~~~text
ΔI_L,on
=
(V_in - V_out) · D · T_s / L
~~~

The falling interval should return the inductor current to the same periodic state in steady operation.

Higher switching frequency can reduce required L for a given ripple, but increases switching loss and can worsen EMI.

Larger L reduces ripple but can slow transient response and increase size.

## Output-capacitor ripple

A capacitor carries the difference between inductor current and load current:

~~~text
i_C = i_L - i_load
~~~

The voltage change follows:

~~~text
dv/dt = i_C / C
~~~

For a triangular capacitor-current ripple, ideal capacitance produces a corresponding ripple voltage.

Real output ripple also includes ESR contribution:

~~~text
ΔV_ESR ≈ ΔI_C · ESR
~~~

and switching-edge inductive effects from ESL and interconnect.

## Multiphase regulation

High-current rails often use multiple interleaved phases.

If N phases are shifted in time, their ripple currents can partially cancel at the output.

Potential benefits include:

- lower effective output ripple;
- distributed thermal load;
- higher total current capability;
- smaller per-phase inductors;
- improved transient response.

Costs include:

- controller complexity;
- current balancing;
- more switching nodes;
- layout complexity.

The cancellation depends on duty ratio, phase count and operating point; it is not perfect at all conditions.

## Feedback and loop stability

A regulator loop can be represented by open-loop transfer function L(s).

Closed-loop stability depends on gain and phase around the crossover region.

Useful concepts include:

- crossover frequency;
- phase margin;
- gain margin;
- poles and zeros;
- output-filter resonance;
- compensation network.

A fast loop is attractive for transient response but cannot be made arbitrarily fast because power-stage delays, sampling, switching frequency and resonances limit stable bandwidth.

Poor compensation can produce ringing or instability even when the DC operating point is correct.

## Control bandwidth and PDN bands

A useful conceptual frequency hierarchy is:

~~~text
very low frequency:
    upstream source and average power balance

low/intermediate:
    VRM control loop and bulk capacitance

higher:
    board decoupling

still higher:
    package capacitance/inductance

highest:
    on-die structures
~~~

The boundaries overlap and depend on the platform.

The PDN should be analyzed as one impedance network rather than as isolated capacitor values.

## Decoupling-capacitor model

An ideal capacitor has:

~~~text
Z_C = 1/(jωC)
~~~

A practical capacitor plus mounting path is approximated by:

~~~text
Z(ω)
=
ESR
+
jω·ESL
+
1/(jωC)
~~~

The self-resonant frequency of the idealized series RLC model occurs approximately when:

~~~text
ω_0 = 1 / sqrt(ESL · C)
~~~

or

~~~text
f_0 = 1 / (2π sqrt(ESL · C))
~~~

Below resonance the component looks primarily capacitive.

Above resonance it looks primarily inductive.

## Why placement matters

A capacitor connected through long traces or vias has additional inductance.

During a fast transient, the relevant loop is:

~~~text
capacitor
   ↓
power path
   ↓
load
   ↓
return path
   ↓
capacitor
~~~

A small physical loop reduces inductance.

A large capacitor far away can store substantial energy while still being ineffective for a very fast local transient because its connection inductance limits current slew.

## Capacitance hierarchy

PDNs commonly use capacitance across several physical scales:

| Scale | Main role |
|---|---|
| bulk/source | slower energy support |
| board near regulator/load | intermediate transient support |
| package | high-frequency local support |
| on-die | very high-frequency support |

This is a conceptual hierarchy rather than a universal component prescription.

The optimum values depend on target impedance, package model, regulator characteristics and load spectrum.

## Anti-resonance

Combining capacitors of different values and parasitics can create anti-resonant impedance peaks.

A simplified mechanism is:

~~~text
one branch looks inductive
another branch looks capacitive
        ↓
parallel resonance
        ↓
high impedance peak
~~~

Adding more capacitors can therefore make a PDN worse at selected frequencies if the network is not analyzed.

ESR, intentional damping, plane loss and component diversity can alter peak magnitude.

## Plane and via inductance

Power and ground planes form a distributed structure.

Current moving through vias and spreading across planes produces parasitic inductance.

A simple scalar L is often insufficient at high frequency because geometry distributes current.

Still, the local principle remains:

~~~text
smaller current loop
and
wider/shorter low-inductance connection
    ↓
lower high-frequency impedance
~~~

This connects power integrity directly to the grounding and signal-integrity chapter.

## Load-line regulation and intentional droop

Not every regulator attempts to keep exactly the same voltage at every current.

Intentional load-line behavior can set:

~~~text
V_target(I)
=
V_no_load
-
R_loadline · I
~~~

This controlled droop can reduce overshoot/undershoot during rapid current changes and manage voltage/current guard bands.

The exact load-line policy is processor/platform specific.

This chapter does not assign a load-line value to ChrisOS hardware.

## Remote sensing

A regulator can measure voltage at a point closer to the load rather than at the regulator output terminals.

Remote sensing compensates for DC/intermediate-frequency distribution drop:

~~~text
regulator output
   ↓ cable/plane resistance
load sense point
   ↑ feedback
~~~

Remote sense does not eliminate high-frequency local inductance.

The sense path itself must be routed and filtered according to the regulator design.

## Current sensing

Regulators may infer or measure current using:

- shunt resistance;
- inductor DCR;
- current-sense amplifiers;
- integrated power-stage telemetry;
- magnetic sensors.

Current information can support:

- current limiting;
- phase balancing;
- telemetry;
- load-line control;
- fault protection.

Accuracy depends on temperature, bandwidth, calibration and sensing topology.

## Power sequencing

Many systems require rails to rise and fall in a defined order.

Reasons include:

- device absolute-maximum ratings;
- reset behavior;
- I/O back-powering prevention;
- PLL/reference startup;
- memory/controller dependencies.

A simplified sequence can be:

~~~text
input valid
   ↓
standby rail
   ↓
main conversion enabled
   ↓
rail reaches power-good window
   ↓
reset released
   ↓
processor begins execution
~~~

Power sequencing is a hardware/firmware platform contract.

A kernel begins after substantial power sequencing has already occurred.

## Power-good and reset

A power-good signal indicates that a supply is inside a specified operating window under the platform's rules.

It is not the same as proving zero ripple or perfect transient performance.

Reset logic can keep digital logic inactive until rails/clocks are acceptable.

Brownout detection can reassert reset or trigger protective behavior when a rail falls below a safe threshold.

The exact implementation is platform-specific.

## Upstream power supply behavior

Desktop platforms may receive regulated rails from an ATX-family supply before local VRMs generate processor/memory/device voltages.

Intel's public ATX12VO desktop power-supply design guide, version dated 2024-05-01, lists ATX12V-specific guidelines revision 3.1 within that guide.

This is an example platform power-supply contract, not a universal ChrisOS requirement.

ChrisOS currently targets x86-64 hardware broadly enough that the documentation must not assume one motherboard PSU topology.

## USB Power Delivery as another layer

USB Power Delivery negotiates power at the connector/protocol level before local regulators convert that input into board rails.

USB-IF's document library lists USB Power Delivery Specification Revision 3.2 Version 1.2 dated 2026-09-14.

This provides a useful architectural example:

~~~text
negotiated source contract
        ↓
connector voltage/current
        ↓
board conversion
        ↓
local regulated rails
~~~

A negotiated external power contract does not replace local PDN design.

## Efficiency

Converter efficiency is:

~~~text
η = P_out / P_in
~~~

Loss terms can include:

- MOSFET conduction loss;
- switching loss;
- gate-drive loss;
- inductor copper/core loss;
- capacitor ESR loss;
- controller/quiescent power;
- PCB conduction loss.

At high load, conduction losses can dominate.

At light load, fixed switching/control losses can become relatively important.

Power-stage mode changes may optimize efficiency across the range.

## Thermal coupling

Electrical loss becomes heat.

For dissipated power P_loss and effective thermal resistance θ,

~~~text
ΔT ≈ P_loss · θ
~~~

as a first-order steady-state model.

Real thermal systems include multiple paths, transient thermal capacitance, airflow and temperature-dependent electrical parameters.

Higher temperature can increase conductor resistance and alter semiconductor behavior, coupling thermal and electrical performance.

## Protection

Power systems use protection mechanisms such as:

- overcurrent protection (OCP);
- overvoltage protection (OVP);
- undervoltage lockout (UVLO);
- overtemperature protection (OTP);
- short-circuit protection;
- soft start;
- current limiting.

Protection thresholds and response times are part of the specific regulator/platform design.

A protection event may appear to software as reset, shutdown or device loss, but the software symptom does not identify the physical cause by itself.

## Brownout and data integrity

Insufficient supply voltage can violate digital timing before the system visibly powers off.

Potential consequences include:

- CPU reset;
- memory corruption;
- storage-controller failure;
- incomplete writes;
- device disappearance.

Storage and filesystem correctness must therefore assume that abrupt power loss can occur unless the hardware provides guaranteed energy hold-up and software participates in a defined shutdown protocol.

This is a system-design boundary, not a claim that current ChrisFS implements power-fail atomicity.

## Measurement

Useful PDN measurements can include:

- DC rail voltage;
- load-transient response;
- oscilloscope ripple/noise;
- impedance versus frequency;
- regulator switch-node behavior;
- current waveform;
- temperature;
- telemetry registers where available.

Measurement quality depends on probe method.

A long oscilloscope ground lead can add inductance and report ringing partly created by the measurement loop.

For very small high-frequency ripple, low-inductance probing technique is essential.

## Frequency-domain impedance measurement

A PDN can be characterized by applying a known small-signal excitation and measuring response.

Conceptually:

~~~text
Z(ω) = V_response(ω) / I_excitation(ω)
~~~

The practical method depends on frequency, operating point and instrument.

The measurement must avoid driving the regulator outside its small-signal region when using linear impedance interpretation.

## Simulation and model hierarchy

Power-delivery analysis can range from:

- ideal RLC networks;
- SPICE regulator models;
- control-loop models;
- distributed plane models;
- package models;
- transistor-level models.

The model must match the question.

Using an ideal capacitor model to predict GHz package behavior is inappropriate.

Using a 3D field solver to estimate a slow DC load-line can be unnecessary.

## Standards context

The BIPM SI Brochure version 4.01 revised in June 2026 is the metrological reference for units used in the equations above.

UEFI Forum lists ACPI Specification Version 6.6, released May 2025, as the latest ACPI specification. ACPI covers system, device and processor power management among its functional areas. That is a software/firmware management interface, not an electrical VRM design specification.

Intel's public ATX12VO desktop power-supply design guide dated 2024-05-01 includes ATX12V-specific guidelines revision 3.1.

USB-IF lists USB Power Delivery Specification Revision 3.2 Version 1.2 dated 2026-09-14.

These standards illustrate different layers:

~~~text
ACPI       -> OS/firmware power-management interface
ATX family -> platform power-supply contract
USB PD     -> connector-level negotiated power contract
PDN/VRM    -> local electrical conversion/distribution
~~~

They must not be collapsed into one abstraction.

## ChrisOS current architectural boundary

Current ChrisOS source reviewed here contains:

~~~text
kernel/metal/acpi.c
kernel/metal/acpi.h
~~~

with exported symbol:

~~~text
acpi_probe
~~~

The implementation scans boot-information memory-map ranges for the ACPI RSDP signature.

For ACPI revision 2 or later it obtains the XSDT address, checks the XSDT signature and walks a bounded set of table pointers.

The reviewed code prints selected table signatures when they match:

~~~text
APIC
MCFG
FACP
~~~

This is discovery/logging behavior.

It is not a complete ACPI interpreter or power-management implementation.

## What the current ACPI code does not establish

The cited acpi_probe implementation does not show:

- AML parsing/evaluation;
- ACPI global sleep-state transition logic;
- processor P-state control;
- processor C-state control;
- battery management;
- thermal-policy control;
- voltage-rail telemetry;
- VRM programming;
- regulator-loop control.

The repository code search at the reviewed revision also found no _S5 symbol.

That search result is supporting evidence, not a general proof that no power-related mechanism exists anywhere outside the reviewed scope.

## Hardware-audit boundary

docs/CURRENT_HARDWARE_AUDIT.md classifies ACPI RSDP, MADT and MCFG support as EXPERIMENTAL and states that no physical machine was booted in that audit.

Therefore current source/audit evidence cannot establish:

- physical rail stability;
- VRM transient response;
- ACPI power-state behavior on hardware;
- platform thermal control;
- battery behavior.

Those require separate implementation and hardware evidence.

## Real-hardware plan boundary

docs/REAL_HARDWARE_PLAN.md explicitly places suspend and resume out of scope until a later project.

The plan requires ACPI for the intended hardware profile, but planned requirement is not current implementation evidence.

This distinction matters:

~~~text
planned ACPI power management
!=
implemented ACPI power management
~~~

## Initialization sequence in current ChrisOS

The current acpi_probe path is discovery-oriented:

~~~text
kernel has boot information
        ↓
acpi_probe
        ↓
scan memory range for RSDP
        ↓
read XSDT pointer
        ↓
inspect table signatures
        ↓
print selected signatures to serial
~~~

There is no regulator initialization sequence in the cited source.

There is no current ChrisOS step that tunes motherboard compensation, sets a load line or selects physical decoupling.

## State and data structures

The current acpi_probe function uses local scalar variables for:

- memory-map iteration;
- physical base/length/type;
- RSDP/XSDT addresses;
- table pointer traversal;
- temporary signature strings.

No persistent PDN state structure is defined by the cited files.

There is no current structure for:

- rail voltage;
- rail current;
- regulator phase state;
- PDN impedance;
- capacitor inventory;
- telemetry history.

## Algorithms and complexity

The current ACPI discovery code scans eligible physical-address ranges in 16-byte increments over the legacy RSDP search region:

~~~text
0xE0000 .. 0x100000
~~~

and then scans XSDT entries with explicit bounds in the reviewed source.

This is bounded discovery work.

It is unrelated to converter-control algorithms.

A real regulator controller may run periodic control equations in hardware/firmware at switching-control rates. ChrisOS does not implement such an algorithm in the cited source.

## Memory ownership

The ACPI probe reads firmware-described physical tables through the boot-information physical-to-virtual mapping.

It does not allocate or own regulator control buffers.

The cited header exposes only:

~~~text
void acpi_probe(void);
~~~

There is no power-telemetry ABI in these files.

## Concurrency

The current function shown is a probe routine with local state.

No lock or multicore synchronization for ACPI power management appears in the cited files because such a subsystem is not implemented there.

Future power-management code would need explicit contracts for:

- CPU coordination;
- interrupt/event handling;
- device suspend ordering;
- shared controller registers;
- timeout/recovery behavior.

Those contracts must be documented only after corresponding source exists.

## ABI and firmware boundary

ACPI is a firmware/OS contract described by the ACPI specification.

Current ChrisOS only inspects a limited subset of the table hierarchy in the cited code.

It does not establish a general AML interpreter ABI.

Physical power rails are below even that layer.

Thus:

~~~text
ACPI object/state
!=
VRM electrical state
~~~

unless a particular ACPI method or telemetry interface explicitly exposes that relation and ChrisOS implements it.

## Failure and recovery

Power-delivery failure modes include:

| Failure | Possible physical result |
|---|---|
| excessive DC resistance | steady droop/heating |
| excessive inductance | fast transient droop/overshoot |
| insufficient capacitance | larger intermediate transient |
| anti-resonance | narrow-band impedance peak |
| unstable regulator loop | sustained/ringing rail oscillation |
| OCP trip | rail shutdown/reset |
| UVLO/brownout | reset or malfunction |
| overheating | throttling/protection/shutdown |
| bad sequencing | device startup failure |

The software symptom can be nonspecific.

A reset is not proof of a VRM problem.

## Security and privilege

Physical regulator equations do not have a kernel privilege level.

Power-management control interfaces can.

If future ChrisOS code gains the ability to:

- request sleep states;
- alter performance states;
- control platform power;
- write power-management registers;

then access must be privileged and validated because incorrect power-state transitions can corrupt system state or deny service.

No such generalized interface is claimed in the current cited source.

## Performance trade-offs

Power delivery affects performance because voltage margin, current capacity and thermal limits constrain achievable activity.

Trade-offs include:

| Choice | Benefit | Cost |
|---|---|---|
| higher switching frequency | smaller L/C possible, faster response | switching loss, EMI |
| larger capacitance | lower selected-band impedance | area, cost, anti-resonance |
| lower ESR | lower resistive drop | potentially less damping |
| stronger droop/load-line | transient headroom | lower load voltage |
| more phases | current sharing/ripple reduction | cost/complexity |
| faster control loop | transient recovery | stability/noise constraints |
| thicker/wider conductors | lower resistance/inductance | area/material |

No one variable can be optimized independently.

## Validation evidence for this chapter

The deterministic checker associated with this chapter verifies:

~~~text
target impedance:
    Ztarget = ΔVallowed / ΔI

resistive droop:
    ΔV = I·R

inductive droop:
    ΔV = L·di/dt

capacitor transient:
    ΔV = ΔQ/C

buck ideal ratio:
    Vout = D·Vin

buck inductor ripple:
    ΔI = (Vin-Vout)·D·Ts/L

self resonance:
    f0 = 1/(2πsqrt(ESL·C))

load line:
    Vtarget = V0 - Rloadline·I

efficiency:
    η = Pout/Pin
~~~

The checker also validates current-source anchors for acpi_probe, RSDP/XSDT discovery, APIC/MCFG/FACP signature logging and the hardware-plan/audit evidence boundaries.

These checks are not electrical measurements of a motherboard PDN.

## Current limitations

This chapter does not provide:

- a specific motherboard stack-up;
- a specific VRM compensation network;
- processor-vendor load-line numbers;
- measured PDN impedance;
- oscilloscope captures;
- thermal model for a real ChrisOS machine;
- ACPI AML interpretation;
- suspend/resume implementation;
- battery-management implementation;
- platform power telemetry.

Those require implementation or hardware evidence that is not present in the reviewed current source.

## Roadmap boundary

The foundation progression now reaches semiconductor and digital-device behavior:

~~~text
circuits and fields
      ↓
transients and AC impedance
      ↓
transmission lines
      ↓
signal integrity
      ↓
power delivery and regulation
      ↓
semiconductor device electrostatics
      ↓
CMOS switching and digital timing
~~~

Future ChrisOS power-management documentation should be implementation-driven and should cite concrete ACPI/firmware/controller source once those facilities exist.

## Revision provenance

Reviewed against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Implementation claims were reconciled directly against:

- kernel/metal/acpi.c;
- kernel/metal/acpi.h;
- docs/CURRENT_HARDWARE_AUDIT.md;
- docs/REAL_HARDWARE_PLAN.md.

The concrete symbol acpi_probe was inspected. The current behavior documented here is limited to ACPI discovery/logging evidenced by those files.

External standards context was checked against BIPM SI Brochure version 4.01, UEFI Forum ACPI 6.6, Intel's public ATX12VO design guide and USB-IF's current USB Power Delivery document library. Product-specific electrical limits are intentionally not generalized.
