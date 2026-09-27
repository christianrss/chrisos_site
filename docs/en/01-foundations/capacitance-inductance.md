---
id: capacitance-inductance
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - ohm-kirchhoff-circuits
related:
  - rc-rlc-transients
  - ac-signals-frequency-impedance
  - electromagnetic-induction-transformers
  - transmission-lines-differential-signals
  - power-delivery-regulation
  - cmos-switching-power
---

# Capacitance, inductance and stored field energy

<div class="abstract">
Resistors dissipate electrical energy; capacitors and inductors store it in electric and magnetic fields. Their constitutive relations introduce state and time dependence into circuit analysis. This chapter derives charge-voltage and flux-current relations, field-energy formulas, equivalent combinations, initial-condition constraints, parasitic behavior, physical realizations, numerical state representation and the boundaries of ideal lumped C/L models before transient and AC analysis.
</div>

## Prerequisites and scope

The previous chapters established voltage, current, power, Ohm's law, KCL, KVL and linear resistive network analysis.

A purely resistive network has no ideal memory: once independent source values are specified, the operating point is determined algebraically.

Capacitors and inductors change that.

Their present terminal behavior depends on stored field state:

~~~text
capacitor state
    charge / electric field
    represented by voltage

inductor state
    magnetic flux linkage
    represented by current
~~~

This makes differential equations unavoidable.

This chapter derives the storage relations and physical limits. Explicit RC, RL and RLC transient solutions belong to the next chapter; sinusoidal impedance and phasors belong to the AC chapter.

No current ChrisOS source implementation is asserted here.

## Capacitor: physical idea

A capacitor consists conceptually of two conductors separated by an insulating region or dielectric.

Moving charge from one conductor to the other creates:

- opposite net charge on the conductors;
- an electric field in the intervening region;
- a potential difference between the conductors;
- stored electric-field energy.

For a linear capacitor,

~~~text
Q = C V
~~~

where

~~~text
Q   charge magnitude on one conductor [C]
C   capacitance [F]
V   terminal voltage [V]
~~~

One farad is

~~~text
1 F = 1 C/V
~~~

Capacitance is a geometric and material property under the selected model. It is not "the amount of charge" and it is not itself energy.

## Parallel-plate capacitor

For two large parallel plates of area (A), separation (d), and dielectric permittivity (epsilon), neglecting fringing,

~~~text
C = ε A / d
~~~

This ideal relation exposes the design dependencies:

- larger plate area increases capacitance;
- smaller separation increases capacitance;
- larger permittivity increases capacitance.

The approximation fails when plate dimensions are not large relative to spacing, when fringing dominates, when the dielectric is nonlinear, or when geometry is more complex.

Integrated-circuit capacitances arise from device junctions, gate structures, interconnect coupling and many other geometries; not every capacitance resembles a discrete parallel-plate component.

## Dielectrics and polarization

A dielectric changes the relation between electric field and stored charge through material polarization.

In a simple linear isotropic material,

~~~text
D = ε E
~~~

where (D) is electric displacement and (E) electric field.

Real dielectric behavior can depend on:

- frequency;
- temperature;
- field strength;
- manufacturing process;
- aging;
- mechanical stress.

Losses and dielectric absorption mean a real capacitor cannot always be modeled by one ideal (C).

The ideal linear capacitor remains a foundational first model because its state equation is simple and powerful.

## Capacitor current relation

Start from

~~~text
Q = C V
~~~

for constant (C).

Current is

~~~text
i = dQ/dt
~~~

therefore

~~~text
i = C dV/dt
~~~

under passive sign convention.

Equivalently,

~~~text
dV/dt = i/C
~~~

and integration gives

~~~text
V(t)
=
V(t0)
+
(1/C) ∫[t0..t] i(τ) dτ
~~~

The initial voltage (V(t0)) is part of the state.

This is the first important difference from a resistor: terminal voltage cannot be determined from instantaneous current alone without knowing history or initial condition.

## Capacitor voltage continuity

For a finite capacitance,

~~~text
i = C dV/dt
~~~

An instantaneous finite jump in voltage would require an impulse of current with unbounded magnitude in the ideal mathematical model.

Therefore ordinary finite-current circuits obey the useful state constraint:

~~~text
V_C(0+) = V_C(0-)
~~~

unless an impulsive source/model is explicitly included.

This continuity rule is central when solving switching transients.

It is not a statement that real capacitors can never change rapidly; it states what the ideal finite-(C) lumped model requires.

## DC steady state of an ideal capacitor

If capacitor voltage is constant,

~~~text
dV/dt = 0
~~~

then

~~~text
i = 0
~~~

So after an ideal DC network reaches steady state, an ideal capacitor behaves as an open circuit with respect to DC current.

This does **not** mean the capacitor has zero voltage or zero energy.

A charged capacitor can have

~~~text
i = 0
V != 0
U != 0
~~~

at steady state.

## Energy stored in a capacitor

Instantaneous power absorbed is

~~~text
p = v i
~~~

Using

~~~text
i = C dv/dt
~~~

gives

~~~text
p = C v dv/dt
~~~

Integrating from zero voltage to (V),

~~~text
U_C
=
∫ C v dv
=
1/2 C V²
~~~

Equivalent form using (Q=CV):

~~~text
U_C = Q²/(2C)
~~~

for the ideal linear capacitor.

Energy is nonnegative because it resides in the electric field under this model.

## Energy density of the electric field

In a linear dielectric, electric-field energy density is

~~~text
u_E = 1/2 E · D
~~~

and for a simple isotropic medium,

~~~text
u_E = 1/2 ε |E|²
~~~

Total stored energy is the volume integral:

~~~text
U_E = ∫ u_E dV
~~~

The lumped expression (1/2 CV²) is a compressed representation of this field energy for a component geometry whose terminal behavior is captured by (C).

This connects circuit theory back to the electromagnetic foundation.

## Capacitors in parallel

Capacitors in parallel share the same terminal voltage.

Total charge is the sum of branch charges:

~~~text
Q_total
=
C1 V + C2 V + ...
=
(C1 + C2 + ...) V
~~~

Therefore,

~~~text
C_eq = Σ C_k
~~~

Parallel capacitance increases because the structure can store more charge for the same voltage.

## Capacitors in series

For ideal capacitors connected in series with an initially neutral internal node, the charge magnitude on each series capacitor becomes equal.

The total voltage is

~~~text
V = V1 + V2 + ...
~~~

with

~~~text
V_k = Q/C_k
~~~

so

~~~text
1/C_eq = Σ 1/C_k
~~~

For two capacitors,

~~~text
C_eq = (C1 C2)/(C1 + C2)
~~~

The smaller capacitor receives the larger voltage magnitude for the same series charge.

In real high-voltage capacitor strings, leakage mismatch may prevent ideal voltage sharing, so balancing components can be necessary.

## Charge sharing

Connecting charged capacitors can redistribute charge.

For two ideal capacitors initially at (V_1) and (V_2), connected in parallel with matching polarity and isolated from external charge flow, charge conservation gives

~~~text
C1 V1 + C2 V2
=
(C1 + C2) V_f
~~~

therefore

~~~text
V_f
=
(C1 V1 + C2 V2)/(C1 + C2)
~~~

If (V_1 != V_2), the final stored energy computed from (1/2CV²) is generally smaller than the initial sum.

The "missing" energy is not destroyed. The ideal zero-resistance connection omits the real electromagnetic radiation, conductor resistance and other dissipative dynamics that occur during redistribution. The paradox is a warning about idealization boundaries.

## Real capacitor model

A practical capacitor may require a network such as

~~~text
        ESR      ESL
---+---/\/\----LLLL---+---
   |                    |
   |         C          |
   +---------||---------+
   |                    |
   +------- Rleak ------+
~~~

Important nonidealities include:

| Effect | Consequence |
|---|---|
| ESR | loss, heating, damping |
| ESL | high-frequency inductive behavior |
| leakage | finite DC discharge path |
| dielectric absorption | history-dependent recovery |
| voltage coefficient | capacitance changes with bias |
| temperature coefficient | capacitance changes with temperature |
| tolerance | actual C differs from nominal |
| breakdown voltage | field limit of dielectric |
| ripple-current limit | thermal/loss constraint |

The useful model depends on frequency and operating condition.

## Decoupling interpretation

A decoupling capacitor near a digital load stores local field energy and can provide transient current while the upstream power-distribution network responds.

The idealized relation

~~~text
ΔV = (1/C) ∫ i dt
~~~

shows why larger capacitance can reduce voltage droop for a given net charge deficit.

But real decoupling performance also depends on ESR, ESL, placement, interconnect inductance, frequency spectrum and regulator dynamics.

"Add more capacitance" is therefore not a universal high-frequency solution.

## Inductor: physical idea

An inductor stores energy in a magnetic field associated with current.

For an ideal linear inductor,

~~~text
λ = L i
~~~

where

~~~text
λ   magnetic flux linkage [Wb-turn]
L   inductance [H]
i   current [A]
~~~

One henry is

~~~text
1 H = 1 V·s/A
~~~

Flux linkage (lambda) incorporates the magnetic flux coupled through turns of a winding. For a single effective turn it reduces to the relevant flux under the model.

## Faraday's law and inductor voltage

Faraday's law relates induced electromotive force to changing magnetic flux.

For the ideal lumped inductor under passive sign convention,

~~~text
v = dλ/dt
~~~

With constant (L),

~~~text
v = L di/dt
~~~

Equivalently,

~~~text
di/dt = v/L
~~~

and

~~~text
i(t)
=
i(t0)
+
(1/L) ∫[t0..t] v(τ) dτ
~~~

The initial current (i(t0)) is part of the inductor state.

## Inductor current continuity

For finite (L),

~~~text
v = L di/dt
~~~

An instantaneous finite jump in current would require an impulsive/unbounded voltage in the ideal model.

Thus, in ordinary finite-voltage switching analysis,

~~~text
I_L(0+) = I_L(0-)
~~~

unless an impulse is explicitly included.

This is the magnetic dual of capacitor voltage continuity.

## DC steady state of an ideal inductor

If inductor current is constant,

~~~text
di/dt = 0
~~~

then

~~~text
v = 0
~~~

So an ideal inductor behaves as a short circuit in DC steady state.

Again, this does not mean zero current or zero stored energy.

An ideal inductor can have

~~~text
v = 0
i != 0
U != 0
~~~

under a sustained DC current.

Real inductors contain winding resistance and core losses, so real steady-state voltage may not be zero.

## Energy stored in an inductor

With passive sign convention,

~~~text
p = v i
~~~

and

~~~text
v = L di/dt
~~~

so

~~~text
p = L i di/dt
~~~

Integrating from zero current to (I),

~~~text
U_L
=
∫ L i di
=
1/2 L I²
~~~

The ideal linear inductor stores nonnegative magnetic-field energy.

## Magnetic-field energy density

In a linear magnetic medium,

~~~text
u_B = 1/2 B · H
~~~

and under simple isotropic linear behavior where (B=mu H),

~~~text
u_B = B²/(2μ)
    = 1/2 μ H²
~~~

Total magnetic energy is obtained by integrating over volume.

The lumped expression (1/2LI²) compresses the field distribution into a terminal parameter.

## Solenoid approximation

For a long ideal solenoid with (N) turns, length (ell), cross-sectional area (A), and permeability (mu),

~~~text
L ≈ μ N² A / ℓ
~~~

This reveals first-order dependencies:

- more turns strongly increase inductance;
- larger magnetic cross-section increases inductance;
- longer magnetic path reduces inductance;
- higher permeability increases inductance.

Real magnetic components require attention to fringing, air gaps, nonlinear permeability, core geometry, leakage flux and winding structure.

## Inductors in series

For uncoupled ideal inductors in series, the same current flows through each and voltages add:

~~~text
v
=
L1 di/dt + L2 di/dt + ...
~~~

therefore

~~~text
L_eq = Σ L_k
~~~

This assumes negligible mutual inductance.

If magnetic coupling exists, the series equivalent can be larger or smaller depending on winding orientation and mutual inductance.

## Inductors in parallel

For uncoupled ideal inductors in parallel with compatible initial conditions, the same voltage appears across each.

The equivalent relation is

~~~text
1/L_eq = Σ 1/L_k
~~~

For two uncoupled inductors,

~~~text
L_eq = (L1 L2)/(L1 + L2)
~~~

Initial currents matter because inductors contain state. Blindly replacing an arbitrary switched set of inductors by an equivalent (L) can erase state constraints.

## Mutual inductance

Two magnetically coupled windings can share flux.

A linear two-coil model may be written

~~~text
λ1 = L1 i1 + M i2
λ2 = M i1 + L2 i2
~~~

with sign determined by winding orientation/dot convention.

Voltages are

~~~text
v1 = L1 di1/dt + M di2/dt
v2 = M di1/dt + L2 di2/dt
~~~

The coupling coefficient is commonly defined by

~~~text
k = M / sqrt(L1 L2)
~~~

with

~~~text
0 <= |k| <= 1
~~~

for passive physical coupling under the ordinary model.

Transformers are developed in a later chapter because turns ratio, leakage, magnetizing inductance and core behavior deserve separate treatment.

## Real inductor model

A practical inductor includes nonideal effects:

| Effect | Consequence |
|---|---|
| winding resistance | (I²R) loss and DC voltage drop |
| core loss | hysteresis/eddy-current heating |
| saturation | inductance decreases at high current/flux |
| parasitic capacitance | self-resonance |
| leakage flux | imperfect coupling |
| skin/proximity effects | frequency-dependent winding resistance |
| tolerance | actual L differs from nominal |
| thermal limit | winding/core temperature constraint |

A simple high-frequency equivalent may include series resistance, ideal (L), and parallel parasitic capacitance.

Above self-resonant frequency, a nominal inductor may appear capacitive.

## Inductive switching and overvoltage

Because ideal inductor current cannot change discontinuously, interrupting a current path forces the circuit to find another way to satisfy the current-state constraint.

From

~~~text
v = L di/dt
~~~

a very rapid change in current requires a large voltage.

Real circuits use flyback diodes, snubbers, clamps or controlled switching paths to limit that voltage and provide a path for stored magnetic energy.

This is directly relevant to relays, motors, switch-mode power converters and inductive loads.

A software command that disables a real load can therefore trigger physical transients governed by hardware, even though software operates at a higher abstraction layer.

## State-variable duality

Capacitors and inductors form a useful dual pair:

| Capacitor | Inductor |
|---|---|
| state commonly represented by voltage | state commonly represented by current |
| (q=Cv) | (lambda=Li) |
| (i=C dv/dt) | (v=L di/dt) |
| voltage continuous for finite current | current continuous for finite voltage |
| DC steady state: open | DC steady state: short |
| (U=1/2CV²) | (U=1/2LI²) |
| electric-field energy | magnetic-field energy |

This duality helps organize later RC and RL transient analysis.

It is not perfect in every physical implementation; real devices have asymmetric parasitics and losses.

## Energy exchange in an ideal LC system

An ideal capacitor and inductor can exchange energy:

~~~text
electric field energy
    <-> magnetic field energy
~~~

For a lossless LC network,

~~~text
U_total
=
1/2 C v²
+
1/2 L i²
~~~

is conserved.

The resulting oscillatory dynamics are derived in the RLC chapter.

Adding resistance dissipates part of that energy and produces damping.

## State-space viewpoint

A network containing capacitors and inductors can be described by a state vector such as

~~~text
x =
[ capacitor voltages
  inductor currents ]
~~~

under an independent-state formulation.

For a linear time-invariant network, equations can often be arranged as

~~~text
dx/dt = A x + B u
y     = C x + D u
~~~

The exact state count can be smaller than the number of energy-storage elements when topological constraints make states dependent.

This state-space view later connects circuit dynamics with control theory, numerical integration and simulation.

## Topological degeneracies in dynamic circuits

Not every arbitrary arrangement of ideal C/L elements yields an independent state for every element.

Examples include:

- loops composed only of ideal capacitors and ideal voltage sources;
- cutsets composed only of ideal inductors and ideal current sources.

Such structures can impose algebraic constraints among storage variables.

In circuit simulation, this can produce differential-algebraic equations rather than a simple explicit ordinary differential equation.

That distinction becomes important for robust numerical solvers.

## Numerical integration boundary

From

~~~text
i_C = C dv_C/dt
v_L = L di_L/dt
~~~

a simulator must integrate state over time.

Simple explicit Euler updates might be written

~~~text
v_C[n+1]
=
v_C[n] + dt * i_C[n]/C

i_L[n+1]
=
i_L[n] + dt * v_L[n]/L
~~~

but explicit Euler can be unstable or inaccurate for stiff circuits or poorly chosen time steps.

Practical circuit simulators use more sophisticated integration schemes and adaptive step control.

This chapter records the state equations, not a recommendation that explicit Euler is sufficient for production simulation.

## Time constants as a preview

When a capacitor interacts with a resistance, the natural time scale has units

~~~text
τ_RC = R C
~~~

because

~~~text
Ω·F = s
~~~

When an inductor interacts with a resistance,

~~~text
τ_RL = L/R
~~~

because

~~~text
H/Ω = s
~~~

These dimensional relationships foreshadow the exponential responses derived in the next chapter.

## Frequency-dependent preview

For sinusoidal steady-state analysis, differentiation maps to multiplication by (jω).

The ideal capacitor and inductor then obtain impedances

~~~text
Z_C = 1/(jωC)
Z_L = jωL
~~~

These formulas are intentionally only previewed here. Their derivation, phase interpretation, RMS quantities and network use belong to the AC chapter.

## Parasitic capacitance and inductance

Capacitance and inductance are not confined to components labeled C and L.

Any separated conductors can exhibit capacitance.

Any current loop creates magnetic flux and therefore inductance.

Examples in computers include:

- PCB trace-to-plane capacitance;
- trace and via inductance;
- package inductance;
- MOS gate and junction capacitances;
- cable capacitance and inductance;
- connector parasitics;
- memory-bus coupling.

At low enough frequency these may be ignored. At high edge rates they can dominate behavior.

The distinction between "component" and "parasitic" is about design intent, not different physics.

## Power-delivery relevance

A digital power-distribution network contains intentional and parasitic R, L and C.

A simplified chain may be viewed as

~~~text
voltage regulator
    ↓
board/interconnect impedance
    ↓
bulk + local decoupling capacitance
    ↓
package inductance
    ↓
die capacitance
    ↓
switching transistors
~~~

Fast changes in load current interact with inductance to produce voltage changes, while capacitance supplies or absorbs transient charge.

This is why power delivery cannot be understood from DC resistance alone.

## Signal-integrity relevance

Interconnect capacitance and inductance determine propagation, characteristic impedance and coupling in distributed structures.

When interconnect length is no longer electrically small, one lumped capacitor and one lumped inductor are insufficient.

A transmission line can be modeled from distributed parameters per unit length:

~~~text
R'
L'
G'
C'
~~~

The transmission-line chapter develops that model.

The current chapter provides the physical meaning of (C) and (L) required to understand it.

## CMOS switching relevance

A CMOS logic node must charge and discharge capacitance.

For a capacitance driven approximately between 0 and (V), the stored field energy at the high state is

~~~text
1/2 C V²
~~~

A complete switching-energy analysis must track where energy comes from and where it is dissipated over charge/discharge cycles.

That subject belongs to the CMOS switching chapter, but the quadratic dependence on voltage already appears here.

It explains why supply voltage is such a strong term in dynamic-power engineering.

## Software representation of storage state

A generic circuit simulator might represent:

~~~text
Capacitor {
    node_a
    node_b
    capacitance
    previous_voltage
}

Inductor {
    node_a
    node_b
    inductance
    previous_current
}
~~~

A production transient solver usually stores more history depending on its integration method.

Important invariants include:

- (C > 0) and (L > 0) for ordinary passive ideal elements;
- units are consistent;
- state corresponds to the same polarity/orientation used by the element stamp;
- initial conditions are explicit;
- time step is positive and finite;
- updates do not silently accept NaN or overflow.

These are general modeling principles, not ChrisOS implementation details.

## Memory, ownership and concurrency in a hypothetical solver

If dynamic circuit elements are simulated in software, state ownership matters.

One solver instance should have a clear owner for each element state at each integration step. Parallel stamping can be feasible because individual components contribute locally, but writes into shared sparse-matrix structures require partitioning, atomics, thread-local accumulation or another synchronization scheme.

State update must happen at a defined phase:

~~~text
read previous accepted state
    ↓
assemble trial equations
    ↓
solve
    ↓
check convergence/error
    ↓
accept new state
~~~

Publishing partially updated capacitor voltage or inductor current to another worker can corrupt the numerical method.

Again, this describes generic solver requirements, not existing ChrisOS code.

## Failure modes

| Condition | Consequence |
|---|---|
| (C=0) used as dynamic capacitor | degenerate element; state equation invalid |
| (L=0) used as dynamic inductor | degenerate element; state equation invalid |
| negative passive C/L without an explicit active model | nonphysical for ordinary element model |
| capacitor overvoltage | dielectric breakdown risk |
| inductor overcurrent | saturation/thermal damage risk |
| ignored ESR/ESL | wrong high-frequency prediction |
| ignored winding resistance | wrong loss/DC prediction |
| inconsistent initial state | transient solver discontinuity/constraint failure |
| too-large integration step | numerical instability or excessive error |
| floating storage network | singular/underdetermined model |
| ideal switching of incompatible states | impulse behavior hidden by the model |

Robust analysis reports the violated assumption rather than forcing a finite answer.

## Validation invariants

Useful deterministic checks include:

~~~text
capacitor:
    Q = C V
    i = C dV/dt
    U = 1/2 C V²

inductor:
    λ = L i
    v = L di/dt
    U = 1/2 L i²
~~~

For ideal combinations:

~~~text
parallel capacitors: C_eq = Σ C
series capacitors:   1/C_eq = Σ 1/C

series inductors:    L_eq = Σ L
parallel inductors:  1/L_eq = Σ 1/L
~~~

Dimensional checks provide another invariant:

~~~text
F · V = C
F · V² = J
H · A² = J
H/Ω = s
Ω·F = s
~~~

## Relationship to ChrisOS

ChrisOS normally sees digital abstractions rather than field-storage variables.

Yet real hardware beneath the OS depends heavily on capacitance and inductance:

- clock and data edges charge interconnect and transistor capacitances;
- voltage regulators use inductors and capacitors;
- package and board inductance shape rail transients;
- decoupling capacitors supply transient current;
- buses and cables exhibit distributed C and L.

A kernel panic, device timeout or memory error can in some cases be ultimately caused by electrical integrity, but software symptoms do not prove a particular circuit cause.

Concrete ChrisOS hardware-monitoring or power-management behavior must be documented from source and device specifications in implementation chapters.

## Validation evidence

The checker associated with this chapter validates representative calculations for:

- parallel-plate capacitance;
- charge from (Q=CV);
- capacitor current for a constant voltage slope;
- capacitor energy;
- series and parallel capacitance;
- charge sharing;
- solenoid inductance;
- inductor voltage for a constant current slope;
- inductor energy;
- series and parallel inductance;
- RC and RL dimensional time constants;
- bilingual document anchors.

These are deterministic teaching checks, not electromagnetic finite-element analysis, SPICE validation, dielectric qualification or magnetic-core characterization.

## Current limitations

This chapter intentionally does not yet solve:

- step response of RC/RL networks;
- underdamped, critically damped or overdamped RLC systems;
- sinusoidal steady-state networks;
- resonant frequency and Q in practical networks;
- transformer turns ratios and coupled-core design;
- transmission-line equations;
- switched-mode regulator control loops;
- concrete ChrisOS source behavior.

Those are separate chapters because each introduces additional state, frequency-domain assumptions, topology or implementation evidence.

## Roadmap boundary

The next sequence is:

~~~text
C/L field storage
    ↓
RC, RL and RLC differential equations
    ↓
natural and forced transient response
    ↓
AC impedance and resonance
    ↓
induction, transformers and power conversion
    ↓
distributed transmission structures
    ↓
digital power and signal integrity
~~~

The storage equations established here remain the state foundation throughout that progression.

## Revision provenance

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because this chapter makes no current ChrisOS implementation claim. The recorded revision establishes corpus provenance and preserves the boundary between physical theory and source-backed implementation.
