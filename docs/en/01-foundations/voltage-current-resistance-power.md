---
id: voltage-current-resistance-power
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - electric-charge-field-potential
related:
  - ohm-kirchhoff-circuits
  - capacitance-inductance
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - power-delivery-regulation
  - cmos-switching-power
---

# Voltage, current, resistance, energy and power

<div class="abstract">
Circuit theory replaces a spatial electromagnetic problem with node potentials, branch currents and component relations. This chapter derives the quantities that make that abstraction useful: voltage as potential difference, current as charge flow rate, resistance as a constitutive relation, and power as energy transfer rate. It also separates ideal linear models from real conductors, fixes sign conventions, and establishes the energy accounting later used for CMOS switching, power delivery and thermal limits.
</div>

## Prerequisites and scope

The prerequisite chapter established charge (Q), electric potential (V), potential difference, field and energy. The central bridge was

~~~text
ΔU = q ΔV
~~~

and current was introduced only as the derivative of transported charge. Here those quantities become circuit variables.

The lumped-circuit abstraction is assumed: each ideal node is treated as approximately equipotential and propagation across the structure is neglected at the scale of the problem. This is not valid for every physical interconnect. Transmission-line behavior, parasitics and high-frequency field effects are deferred to later chapters.

This chapter does not assign electrical-circuit behavior to ChrisOS source code. It is a physical prerequisite for understanding the hardware whose architectural contracts ChrisOS consumes.

## SI definitions and dimensional structure

The International System of Units defines the ampere as the SI base unit of electric current. Under the present SI, the elementary charge has the exact value

~~~text
e = 1.602176634 × 10^-19 C
~~~

and

~~~text
1 C = 1 A·s
~~~

The derived units used throughout this chapter are

| Quantity | Symbol | SI unit | Dimensional relation |
|---|---|---|---|
| charge | (Q) | coulomb, C | A·s |
| current | (I) | ampere, A | C/s |
| potential difference | (V) | volt, V | J/C |
| resistance | (R) | ohm, Ω | V/A |
| conductance | (G) | siemens, S | A/V |
| energy | (E) or (U) | joule, J | N·m |
| power | (P) | watt, W | J/s = V·A |

Dimensional analysis is a mechanical correctness check. For example,

~~~text
V I = (J/C)(C/s) = J/s = W
~~~

so voltage multiplied by current has the dimensions of power.

Primary metrology references for these units are the BIPM *SI Brochure*, 9th edition, version 4.01 (June 2026), and the current NIST SI base-unit material.

## Voltage is a difference, not a stored substance

Circuit voltage is an electric potential difference. With a chosen reference,

~~~text
v_ab = V_a - V_b
~~~

The polarity label is part of the variable definition. If measurement gives (v_{ab}=-3	ext{ V}), the result means point (b) is three volts above point (a) under the chosen convention. Negative voltage is not an invalid voltage.

Node notation such as

~~~text
V_cpu = 1.0 V
~~~

implicitly means relative to a specified reference node. That reference may be called ground, but circuit ground is a modeling reference and is not automatically protective Earth.

Voltage measures energy difference per unit charge:

~~~text
ΔU = q ΔV
~~~

For a positive charge, moving through a positive potential rise increases potential energy. Electron motion requires extra care because electron charge is negative.

## Current is charge transfer per unit time

Current through a chosen oriented surface is

~~~text
I = dQ/dt
~~~

For constant current,

~~~text
Q = I t
~~~

One ampere corresponds to one coulomb per second. Using the exact elementary-charge value, a current of one ampere corresponds in magnitude to approximately

~~~text
1 / e
≈ 6.241509074 × 10^18
~~~

elementary charges crossing the reference surface per second.

Current direction is a convention. Conventional current is defined in the direction positive charge would move. In a metal, mobile electrons drift in the opposite direction. The conventional current variable remains useful because component and network equations are written consistently in that reference direction.

## Current density and microscopic transport

A branch current compresses spatial transport into one scalar. The more local quantity is current density (mathbf{J}), measured in A/m². For uniform current density normal to an area (A),

~~~text
I = J A
~~~

More generally,

~~~text
I = ∫ J · dA
~~~

For a simple carrier model with carrier number density (n), carrier charge (q), cross-sectional area (A), and average drift velocity (v_d),

~~~text
I = n q A v_d
~~~

with sign determined by the chosen directions and carrier charge.

This relation is a model, not a universal microscopic law for every material. Metals, semiconductors, plasmas and electrolytes differ in carrier populations and transport physics. Later semiconductor chapters replace the crude conductor picture with band structure, drift, diffusion and field-dependent device behavior.

## Charge motion does not mean signal propagation at drift velocity

Electron drift velocity in a conductor can be much smaller than the speed at which an electrical disturbance propagates through the electromagnetic structure. Closing a switch does not require one electron to travel from the source to the load before the load responds.

A circuit signal is associated with changing electromagnetic fields and distributed charge rearrangement. The lumped model hides this propagation when the structure is electrically small enough. Transmission-line theory restores it when geometry and edge rate make propagation delay important.

## Component relations and constitutive laws

Circuit topology alone does not determine behavior. Each component also needs a constitutive relation connecting its terminal variables.

For a two-terminal element, choose voltage polarity and current direction. A component law can then relate (v(t)), (i(t)), charge, flux, temperature or internal state.

Examples developed later include

~~~text
resistor:      v = R i        under the ideal linear model
capacitor:     i = C dv/dt
inductor:      v = L di/dt
~~~

These equations are not interchangeable. They encode different physical storage and dissipation mechanisms.

## Resistance and the ideal resistor

For an ideal linear resistor,

~~~text
v = R i
~~~

where (R>0) is constant. Therefore

~~~text
R = v/i
~~~

for nonzero current, and conductance is

~~~text
G = 1/R
i = G v
~~~

The phrase "resistance equals voltage divided by current" must be used carefully. For a nonlinear device, the ratio (v/i) at one operating point is not necessarily a constant material/component property and is not necessarily equal to the local slope

~~~text
r_d = dv/di
~~~

A diode, MOSFET or protection element can have a nonlinear (i)-(v) curve. Ohm's law in the simple (v=Ri) form is a model for an ohmic linear element over a stated operating range.

## Resistivity and geometry

For a uniform conductor that can be modeled as ohmic,

~~~text
R = ρ L / A
~~~

where

~~~text
ρ   resistivity [Ω·m]
L   conductor length [m]
A   cross-sectional area [m²]
~~~

Longer conductors have more resistance; larger cross-sectional area reduces resistance. Resistivity is a material property only within the limits of the model and depends on conditions such as temperature, composition and microstructure.

A common first-order temperature model near a reference temperature (T_0) is

~~~text
R(T) ≈ R(T0) [1 + α(T - T0)]
~~~

for a range where a linear temperature coefficient (alpha) is adequate. This is not universal. Semiconductor resistive behavior can differ strongly from simple metallic trends.

## Open circuit and short circuit are limiting models

An ideal open circuit carries no current:

~~~text
i = 0
~~~

while its voltage may be nonzero.

An ideal short circuit has zero voltage across it:

~~~text
v = 0
~~~

while its current is determined by the surrounding network and source constraints.

Neither idealization permits arbitrary simultaneous assignments. Saying "a short has zero resistance, therefore infinite current" omits the source impedance, interconnect resistance, protection behavior and other network constraints. The ideal zero-resistance relation alone cannot set the current magnitude.

## Instantaneous power

Power is the rate of energy transfer:

~~~text
p = dE/dt
~~~

For a two-terminal electrical element under a consistent reference convention,

~~~text
p(t) = v(t) i(t)
~~~

The sign depends on how voltage polarity and current direction were defined.

### Passive sign convention

Under the passive sign convention, current is defined as entering the terminal labeled positive for voltage.

Then

~~~text
p > 0   element absorbs power
p < 0   element delivers power
~~~

This convention allows sources and loads to be treated with the same equation. A battery delivering energy will have negative (p) under a passive reference orientation; during charging it can have positive (p).

## Energy is the integral of power

Energy transferred over an interval is

~~~text
E = ∫ p(t) dt
~~~

For constant power,

~~~text
E = P t
~~~

Power and energy must not be conflated. A 100 W load describes a rate. Running it for 10 s transfers 1000 J. A device can have a high instantaneous power demand but modest total energy if the interval is brief, or low power but large energy consumption over a long interval.

This distinction becomes central for boost behavior, thermal time constants, battery runtime and dynamic CMOS activity.

## Joule heating in an ideal resistor

For a positive linear resistor under passive sign convention,

~~~text
v = R i
p = v i
~~~

therefore

~~~text
p = i² R
p = v² / R
~~~

Both forms are consequences of the same two equations and apply under the same model assumptions.

Because (R>0) and the squares are nonnegative, an ideal passive resistor cannot deliver net power in this model. Electrical energy is converted into thermal energy.

At device scale, the temperature rise depends not only on electrical power but also on heat capacity, thermal resistance, geometry, airflow, packaging and time.

## Sources and loads

An ideal voltage source constrains terminal voltage regardless of current demanded by the rest of the ideal network. An ideal current source constrains current regardless of terminal voltage. Real sources cannot maintain those constraints without limit.

Useful real-world deviations include

- finite output resistance or impedance;
- current limits;
- voltage droop;
- efficiency less than 100%;
- thermal shutdown;
- transient response;
- control-loop stability limits.

Power-delivery chapters treat regulators, decoupling and rail transients in more detail. The important boundary here is that "5 V source" is a terminal constraint model, not a claim of infinite power capability.

## Efficiency and loss

If a subsystem receives input power (P_{in}) and provides useful output power (P_{out}),

~~~text
η = P_out / P_in
~~~

for a steady condition with compatible averaging.

Loss is

~~~text
P_loss = P_in - P_out
~~~

For a passive conversion subsystem, (0 ≤ η ≤ 1). Apparent values outside that interval usually indicate inconsistent measurement boundaries, transient stored energy, sign errors or averaging mismatches.

Digital systems distribute power through multiple conversion stages, so local efficiency and loss matter for supply sizing and thermal design.

## Time-varying signals and averaging

The identity

~~~text
p(t) = v(t)i(t)
~~~

is instantaneous.

For periodic or varying signals, average power over interval (T) is

~~~text
P_avg = (1/T) ∫_0^T v(t)i(t) dt
~~~

In general,

~~~text
average(v i) != average(v) average(i)
~~~

unless special conditions hold.

RMS quantities, phase angle, reactive power and complex power require the AC framework developed later. They should not be imported into arbitrary waveforms without stating their definitions and assumptions.

## Measurement models

An ideal voltmeter measures potential difference while drawing zero current: infinite input resistance. An ideal ammeter measures branch current with zero voltage drop: zero series resistance.

Real instruments disturb the circuit.

| Instrument | Ideal property | Important real deviation |
|---|---|---|
| voltmeter | infinite input resistance | finite input resistance/capacitance |
| ammeter | zero series resistance | burden voltage and fuse/shunt limits |
| oscilloscope probe | negligible loading | resistance, capacitance, bandwidth, ground reference |
| current probe | non-invasive idealization | bandwidth, insertion or magnetic limitations |

Measurement is therefore part of the circuit model. A probe can change a high-impedance or high-frequency node enough to alter the observed waveform.

## Reference directions and algebraic signs

For every branch, define both

~~~text
voltage polarity
current arrow
~~~

before solving.

A negative solution reverses the assumed direction; it does not invalidate the equations.

For example, if (i) is defined from A to B and calculation gives

~~~text
i = -2 mA
~~~

the physical current is 2 mA from B to A relative to that chosen reference.

Consistent orientation is what allows Kirchhoff equations to scale from one element to large networks.

## Numerical representation in software models

A software circuit or power model must choose representations for quantities and units. Floating-point values offer range but introduce rounding. Fixed-point values offer deterministic scaling but require explicit overflow analysis. Integers can represent exact counts or scaled units only within their range.

A safe model should keep units visible in names, types or interfaces. Confusing millivolts with volts or milliamperes with amperes can produce errors of factors of (10^3) or (10^6).

For computed power,

~~~text
P = V I
~~~

the numerical implementation must also consider multiplication range. Two values individually within range can overflow when multiplied in a fixed-width representation.

## Data structures, state and ownership

This chapter defines physical variables, not a ChrisOS subsystem. There is therefore no current ChrisOS source structure, ownership graph, allocator, lock, ABI or initialization sequence to document here.

If ChrisOS later gains power-management telemetry, battery management, regulator control or a circuit-level simulator, that implementation will require a separate source-bound chapter with concrete files, symbols, state ownership, concurrency rules and validation evidence.

Keeping this boundary explicit prevents textbook circuit concepts from being misreported as current kernel behavior.

## Control and data flow across abstraction layers

The physical-to-software dependency chain can be represented as

~~~text
electrical source
    ↓
rail voltage and available current
    ↓
transistor switching and interconnect behavior
    ↓
clocked logic and architectural state
    ↓
CPU/device contract
    ↓
ChrisOS code observes registers, memory and interrupts
~~~

ChrisOS normally acts at the architectural end of this chain. Voltage droop or excessive temperature can eventually cause reset, throttling, corrupted computation or hardware fault, but a high-level software symptom does not by itself identify the physical cause.

## Concurrency, privilege and ABI boundary

Voltage, current and power do not have a CPU privilege level. The physical laws apply independently of ring 0 or ring 3.

At the software boundary, access to hardware telemetry or power-control registers may be privileged, concurrent and ABI-sensitive, but those mechanisms must be documented from the actual device interface and ChrisOS implementation. None are asserted here.

Similarly, there is no wire format or on-disk format associated with the physical quantities themselves. Encoded telemetry formats belong to the specifications that define them.

## Failure modes and safety boundaries

Electrical models fail when their assumptions are exceeded.

| Model or operation | Failure boundary |
|---|---|
| (v=Ri) | nonlinear or condition-dependent element |
| (R=ρL/A) | nonuniform geometry/material or frequency-dependent effects |
| lumped node voltage | propagation delay/parasitics are significant |
| constant source voltage | source current/thermal/control limit reached |
| (p=vi) interpretation | inconsistent polarity/current reference |
| average power | averaging interval does not match the phenomenon |
| numeric power calculation | unit mismatch, overflow or precision loss |
| ideal short/open | real parasitics and source limits dominate |

Electrical work also has physical safety limits. High current can heat conductors and start fires; high voltage can create shock and insulation hazards. The equations in this chapter are analytical tools, not a substitute for applicable laboratory and equipment safety procedures.

## Performance and engineering trade-offs

Electrical engineering frequently trades voltage, current, resistance, energy, heat and timing against one another.

Lower interconnect resistance reduces voltage drop and (I^2R) loss but may require wider traces, more copper area or heavier conductors. Lower supply voltage can reduce CMOS switching energy, yet timing margin and noise tolerance constrain how far voltage can fall. Higher current capacity can improve transient response but increases regulator, connector and thermal requirements.

The operating-system layer experiences the results through hardware contracts rather than through these equations directly, but system-level performance ultimately depends on those physical limits.

## Validation evidence

The associated executable checker verifies deterministic examples for

- coulombs transferred by constant current;
- elementary charges per second at one ampere;
- (R=V/I) for a linear resistor;
- (R=ρL/A);
- (P=VI);
- the equivalent resistor identities (P=I^2R=V^2/R);
- energy from constant power over time;
- passive-sign-convention interpretation;
- required bilingual chapter anchors.

These checks validate arithmetic and documentation invariants. They are not SPICE simulation, device characterization, safety certification or hardware conformance tests.

## Current limitations

This chapter intentionally stops before network solution and dynamic reactive behavior. It does not yet derive

- Kirchhoff current and voltage laws as a network solver;
- equivalent resistance networks;
- Thévenin or Norton reduction;
- capacitor or inductor transients;
- sinusoidal impedance and phase;
- transmission lines;
- semiconductor device (i)-(v) equations;
- regulator control loops;
- concrete ChrisOS telemetry or power-management code.

Those topics are assigned separate curriculum IDs so their assumptions and implementation evidence remain explicit.

## Roadmap boundary

Future chapters use this foundation to build the following chain:

~~~text
voltage/current/resistance/power
    ↓
Ohm + Kirchhoff network analysis
    ↓
C/L storage and transients
    ↓
AC impedance and frequency response
    ↓
signal integrity and power delivery
    ↓
CMOS switching energy and timing
~~~

A future ChrisOS power-management subsystem, if implemented, must be documented from source and hardware specifications rather than retrofitted into this physics chapter.

## Revision provenance

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because this chapter makes no claim about current ChrisOS implementation. The reviewed revision records corpus provenance and the implementation boundary. Primary metrology references were checked against the BIPM SI Brochure, 9th edition, version 4.01 (June 2026), and current NIST SI definitions.
