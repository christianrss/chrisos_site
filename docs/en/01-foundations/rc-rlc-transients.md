---
id: rc-rlc-transients
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - capacitance-inductance
related:
  - ac-signals-frequency-impedance
  - power-delivery-regulation
  - cmos-switching-power
  - transmission-lines-differential-signals
---

# RC, RL and RLC transients

<div class="abstract">
Resistors dissipate energy while capacitors and inductors store it. Once these elements are connected, switching and changing sources produce transient responses governed by differential equations, initial conditions and conservation laws. This chapter derives first-order RC and RL responses, second-order RLC dynamics, damping regimes, natural and forced response, state-space form, energy flow, switching constraints, numerical integration concerns and the limits of lumped transient models before frequency-domain analysis.
</div>

## Prerequisites and scope

The prerequisite chapters established:

- Ohm's law and Kirchhoff's laws;
- capacitor relation (i_C=C,dv_C/dt);
- inductor relation (v_L=L,di_L/dt);
- capacitor voltage continuity for finite current;
- inductor current continuity for finite voltage;
- stored energies (U_C=	frac12CV^2) and (U_L=	frac12LI^2).

A transient is the time-domain evolution that occurs when a circuit's state or forcing changes.

Typical triggers include:

~~~text
switch closes or opens
source steps to a new value
load current changes
initially stored energy is released
control system changes a converter state
~~~

This chapter treats linear lumped circuits with constant R, L and C unless stated otherwise. Nonlinear semiconductor switching, distributed transmission lines and regulator control loops require additional models.

No current ChrisOS implementation is asserted here.

## State, algebraic variables and memory

A resistor is algebraic:

~~~text
v_R = R i_R
~~~

Its terminal variables at one instant do not require a stored previous value in the ideal model.

A capacitor and inductor are dynamic:

~~~text
i_C = C dv_C/dt
v_L = L di_L/dt
~~~

Their energy-storage variables carry state across time.

A convenient state choice is

~~~text
capacitor voltage
inductor current
~~~

because these variables obey continuity constraints under finite ordinary excitation.

The complete network still obeys KCL and KVL at every time.

## Initial conditions

Transient analysis requires the state immediately before switching.

For an ideal capacitor:

~~~text
v_C(0+) = v_C(0-)
~~~

For an ideal inductor:

~~~text
i_L(0+) = i_L(0-)
~~~

These equalities do not imply every voltage or current is continuous.

For example:

- resistor voltage may jump if current jumps;
- capacitor current may jump while voltage remains continuous;
- inductor voltage may jump while current remains continuous.

The switching topology at (t<0) and (t>0) may differ, so the circuit must be analyzed on each side of the switching event.

## Final-value reasoning

Before solving a first-order DC switching problem, it is often useful to determine the expected final state.

For a stable circuit under constant DC excitation as (t	oinfty):

~~~text
ideal capacitor -> open circuit
ideal inductor  -> short circuit
~~~

This identifies (v_C(infty)) or (i_L(infty)) without solving the differential equation first.

The rule applies only to DC steady state. It does not say capacitors are always open or inductors are always short.

## First-order canonical response

A stable linear first-order state (x(t)) driven from initial value (x_0) toward final value (x_f) has the form

~~~text
x(t) = x_f + (x_0 - x_f) e^(-t/τ)
~~~

where (	au>0) is the time constant.

This separates the response into

~~~text
forced/final component: x_f
natural component:      (x_0 - x_f)e^(-t/τ)
~~~

At (t=	au), the distance to the final value has fallen to

~~~text
e^-1 ≈ 0.367879
~~~

of its initial distance.

Useful remaining fractions are approximately:

| Time | Remaining natural component |
|---|---:|
| (1	au) | 36.8% |
| (2	au) | 13.5% |
| (3	au) | 5.0% |
| (4	au) | 1.83% |
| (5	au) | 0.674% |

"Settled after five time constants" is therefore an engineering approximation, not exact equality.

## Series RC charging circuit

Consider a voltage source (V_s), resistor (R) and capacitor (C) in series.

KVL gives

~~~text
V_s = v_R + v_C
~~~

with

~~~text
v_R = Ri
i = C dv_C/dt
~~~

therefore

~~~text
RC dv_C/dt + v_C = V_s
~~~

For constant (V_s), the time constant is

~~~text
τ = RC
~~~

and the solution is

~~~text
v_C(t)
=
V_s
+
[v_C(0+) - V_s] e^(-t/RC)
~~~

For an initially uncharged capacitor,

~~~text
v_C(t) = V_s [1 - e^(-t/RC)]
~~~

The current is

~~~text
i(t)
=
(V_s - v_C(0+))/R
* e^(-t/RC)
~~~

For (v_C(0)=0),

~~~text
i(t) = (V_s/R)e^(-t/RC)
~~~

The largest ideal current occurs immediately after the step because the capacitor voltage cannot jump.

## RC discharge

For a capacitor initially at (V_0) discharging through (R) with no independent source,

~~~text
RC dv_C/dt + v_C = 0
~~~

so

~~~text
v_C(t) = V_0 e^(-t/RC)
~~~

and, under a chosen passive orientation,

~~~text
i(t) = C dv_C/dt
     = -(V_0/R)e^(-t/RC)
~~~

The negative sign means the current direction is opposite the reference chosen for capacitor charging.

Stored energy decays as

~~~text
U_C(t)
=
1/2 C V_0² e^(-2t/RC)
~~~

The energy decays twice as fast in exponent because it depends on voltage squared.

## RC energy accounting

Charging an ideal capacitor from an ideal voltage source (V_s) through a resistor has a useful energy result.

The final capacitor energy is

~~~text
U_C = 1/2 C V_s²
~~~

The source delivers

~~~text
E_source = C V_s²
~~~

for a zero-initial-voltage step through any positive (R).

The resistor dissipates the difference:

~~~text
E_R = 1/2 C V_s²
~~~

Under this ideal step model, half the source energy is stored and half is dissipated, independent of the resistance value. (R) changes the time scale, not that total split.

Real drivers, finite source rise time, inductance and energy-recovery circuits can change the detailed energy flow.

## General first-order RC time constant

A capacitor does not always see one explicit series resistor.

For a linear one-capacitor network, the natural time constant can often be found from the Thévenin resistance seen by the capacitor with independent sources zeroed:

~~~text
τ = R_th C
~~~

Dependent sources remain active. If present, a test-source method may be required to find (R_{th}).

This is a network property, not merely the label on one resistor.

## Series RL energization

Consider a DC source (V_s), resistor (R) and inductor (L) in series.

KVL gives

~~~text
V_s = Ri + L di/dt
~~~

or

~~~text
L di/dt + Ri = V_s
~~~

The time constant is

~~~text
τ = L/R
~~~

and

~~~text
i(t)
=
V_s/R
+
[i(0+) - V_s/R]e^(-tR/L)
~~~

For an initially unenergized inductor,

~~~text
i(t)
=
(V_s/R)[1-e^(-tR/L)]
~~~

The inductor voltage is

~~~text
v_L(t)
=
[V_s - R i(0+)] e^(-tR/L)
~~~

and for zero initial current,

~~~text
v_L(t)=V_s e^(-tR/L)
~~~

The current starts continuously while the inductor voltage can change immediately.

## RL decay

If an inductor carrying current (I_0) is connected across a resistance (R) with no independent source,

~~~text
L di/dt + Ri = 0
~~~

so

~~~text
i(t) = I_0 e^(-tR/L)
~~~

Stored magnetic energy decays as

~~~text
U_L(t)
=
1/2 L I_0² e^(-2tR/L)
~~~

and is dissipated in the resistor under the ideal model.

If the current path is broken without a controlled discharge path, the ideal inductor attempts to generate whatever voltage is required to maintain current continuity. Real circuits therefore require flyback, clamp or snubber paths when inductive energy is significant.

## General first-order RL time constant

For a one-inductor linear network, the natural time constant can often be expressed as

~~~text
τ = L/R_th
~~~

where (R_{th}) is the resistance seen by the inductor after independent sources are zeroed, again preserving dependent sources.

The duality with RC is:

| RC | RL |
|---|---|
| state (v_C) | state (i_L) |
| (	au=R_{th}C) | (	au=L/R_{th}) |
| capacitor initially resembles voltage source equal to (v_C(0)) | inductor initially resembles current source equal to (i_L(0)) |
| final DC capacitor open | final DC inductor short |

## Piecewise switching procedure

A disciplined switching analysis can use the following sequence:

~~~text
1. solve the t < 0 circuit
2. determine v_C(0-) and i_L(0-)
3. apply continuity:
       v_C(0+) = v_C(0-)
       i_L(0+) = i_L(0-)
4. construct the t > 0 topology
5. determine the final stable DC state if it exists
6. derive the differential equation or time constant
7. solve the response
8. verify KCL/KVL and energy/power signs
~~~

Skipping step 2 or 3 is a common source of physically impossible solutions.

## Second-order series RLC equation

Consider a source-free series RLC loop.

Using capacitor charge (q),

~~~text
i = dq/dt
v_C = q/C
v_R = R dq/dt
v_L = L d²q/dt²
~~~

KVL gives

~~~text
L d²q/dt²
+
R dq/dt
+
q/C
=
0
~~~

Dividing by (L),

~~~text
d²q/dt²
+
(R/L) dq/dt
+
(1/LC)q
=
0
~~~

Define

~~~text
α = R/(2L)
ω_0 = 1/sqrt(LC)
~~~

Then the characteristic equation is

~~~text
s² + 2αs + ω_0² = 0
~~~

with roots

~~~text
s = -α ± sqrt(α² - ω_0²)
~~~

The root structure determines the damping regime.

## Damping ratio

Define

~~~text
ζ = α/ω_0
  = (R/2) sqrt(C/L)
~~~

for the series RLC form.

Then:

| Regime | Condition | Pole behavior |
|---|---|---|
| overdamped | (zeta>1) | two distinct negative real poles |
| critically damped | (zeta=1) | repeated negative real pole |
| underdamped | (0<zeta<1) | complex-conjugate poles with negative real part |
| lossless | (zeta=0) | purely imaginary poles in ideal model |

A negative resistance or active network can move poles into the right half-plane and produce growth rather than decay.

## Overdamped response

If

~~~text
α > ω_0
~~~

the roots (s_1,s_2) are distinct negative real numbers for (R,L,C>0).

The natural response has form

~~~text
x(t) = A e^(s1 t) + B e^(s2 t)
~~~

There is no oscillation.

The slower pole, the one closer to zero, dominates at long times.

## Critical damping

If

~~~text
α = ω_0
~~~

the repeated pole is

~~~text
s = -α
~~~

and the natural response is

~~~text
x(t)
=
(A + Bt)e^(-αt)
~~~

Critical damping marks the boundary between oscillatory and non-oscillatory behavior in the ideal second-order model.

It is often associated with fast monotonic settling, but the exact engineering optimum depends on the measured variable and performance criterion.

## Underdamped response

If

~~~text
α < ω_0
~~~

define damped natural frequency

~~~text
ω_d = sqrt(ω_0² - α²)
~~~

The natural response can be written

~~~text
x(t)
=
e^(-αt)
[A cos(ω_d t) + B sin(ω_d t)]
~~~

or equivalently as a decaying sinusoid with amplitude and phase.

Energy moves repeatedly between electric and magnetic fields while resistance removes part of it each cycle.

## Lossless LC oscillation

For (R=0),

~~~text
α = 0
ω_d = ω_0
~~~

and the ideal source-free LC network satisfies

~~~text
x'' + ω_0² x = 0
~~~

Its total energy

~~~text
U =
1/2 C v_C²
+
1/2 L i_L²
~~~

remains constant.

Real circuits always contain loss mechanisms, so indefinitely sustained passive LC oscillation is an idealization.

## Forced second-order response

With an applied source, a second-order response contains both

~~~text
natural response
+
forced response
~~~

The natural part depends on initial stored energy and the circuit poles.

The forced part depends on the source.

For a stable DC step, the natural response decays and the state approaches the forced final value.

For sinusoidal forcing, the long-term forced response motivates the phasor and impedance methods of the next chapter.

## Initial conditions in RLC circuits

A second-order system generally requires two independent initial conditions.

A convenient pair is often

~~~text
v_C(0+)
i_L(0+)
~~~

inherited from the pre-switch circuit.

The constants in the homogeneous solution are then found by applying these initial state values and, when necessary, derivatives obtained from KCL/KVL.

Arbitrarily setting all initial conditions to zero discards stored energy and can fundamentally change the response.

## State-space formulation

A series RLC circuit can use state vector

~~~text
x =
[ v_C
  i_L ]
~~~

For a source (u(t)), one possible form is

~~~text
dv_C/dt = i_L/C

di_L/dt =
[u - R i_L - v_C]/L
~~~

Therefore

~~~text
d/dt [v_C] = [ 0      1/C ] [v_C] + [ 0 ]u
     [i_L]   [-1/L  -R/L ] [i_L]   [1/L]
~~~

This exposes the two energy-storage states and makes eigenvalues of the state matrix equal to the natural poles.

State-space representation is especially useful for simulation, control and multi-state systems.

## Step response metrics

For underdamped systems, common response metrics include:

- rise time;
- peak time;
- percent overshoot;
- settling time.

For the normalized standard second-order form

~~~text
s² + 2ζω_n s + ω_n²
~~~

with (0<zeta<1), the damped frequency is

~~~text
ω_d = ω_n sqrt(1-ζ²)
~~~

and ideal percent overshoot for a canonical step response is

~~~text
M_p
=
exp[-ζπ/sqrt(1-ζ²)]
~~~

as a fraction of final value.

This formula applies to the standard second-order transfer form with the usual numerator assumptions; it must not be applied blindly to every measured variable in every RLC topology.

## Q factor preview

For a lightly damped series RLC circuit,

~~~text
Q ≈ ω_0 L/R
  = 1/(ω_0 R C)
  = (1/R)sqrt(L/C)
~~~

and for the standard second-order denominator,

~~~text
Q = 1/(2ζ)
~~~

under the corresponding model.

High (Q) means relatively weak damping and more pronounced resonance.

The full frequency-domain meaning of (Q) is developed in the AC chapter.

## Natural response and poles

The exponential modes of a linear circuit are determined by poles.

For first-order systems:

~~~text
pole = -1/τ
~~~

For stable passive RC/RL systems, the pole lies on the negative real axis.

For second-order RLC systems, poles may be:

~~~text
two negative real
one repeated negative real
complex conjugates with negative real part
~~~

Pole position provides a compact link between time-domain settling and frequency-domain behavior.

## Laplace-transform preview

The Laplace transform converts differentiation into algebra while preserving initial conditions.

For example,

~~~text
L{dx/dt}
=
sX(s) - x(0-)
~~~

and

~~~text
L{d²x/dt²}
=
s²X(s) - s x(0-) - x'(0-)
~~~

This allows circuit differential equations to become algebraic equations in (s).

The next chapter focuses on sinusoidal steady state using (s=jω); full transform methods are broader than phasor analysis.

## Convolution and arbitrary forcing

For a stable linear time-invariant system with impulse response (h(t)), output can be written

~~~text
y(t)
=
∫ h(τ)u(t-τ)dτ
~~~

over the appropriate interval.

This means step and impulse responses characterize how the system reacts to more general inputs through superposition.

Circuit simulation in the time domain may instead integrate the state equations directly.

## Numerical time integration

A simulator cannot manipulate continuous time directly; it approximates state updates at discrete time points.

For a scalar first-order equation

~~~text
dx/dt = f(x,t)
~~~

explicit Euler uses

~~~text
x[n+1]
=
x[n] + Δt f(x[n],t[n])
~~~

This method is simple but conditionally stable.

For an RC decay

~~~text
dx/dt = -x/τ
~~~

explicit Euler gives

~~~text
x[n+1]
=
(1-Δt/τ)x[n]
~~~

If (Delta t) is too large, the numerical solution can oscillate or diverge even though the physical system is stable.

## Stiffness and implicit methods

Circuits with widely separated time constants can be stiff.

Example:

~~~text
fast parasitic pole: nanoseconds
slow control/storage pole: milliseconds
~~~

A method forced to use the fastest explicit stable step can become inefficient.

Implicit methods such as backward Euler trade per-step algebraic solve cost for stronger stability properties.

Trapezoidal integration offers different accuracy/damping behavior and can exhibit numerical ringing in some stiff switching problems.

Production transient simulation therefore requires method selection, local error estimation, adaptive step control and robust nonlinear iteration.

## Companion models

Circuit simulators often transform dynamic devices into algebraic companion models at each time step.

Under backward Euler, a capacitor relation can become an equivalent conductance plus history source.

Starting from

~~~text
i_C = C dv/dt
~~~

approximate

~~~text
dv/dt
≈
[v_n - v_(n-1)]/Δt
~~~

so

~~~text
i_n
=
(C/Δt)v_n
-
(C/Δt)v_(n-1)
~~~

At the current time step, (C/Delta t) acts like a conductance and the previous-state term becomes a known source contribution.

This allows transient analysis to reuse matrix assembly machinery.

## Discrete simulation state

A generic transient solver may maintain:

~~~text
ElementState {
    accepted_state
    trial_state
    history_terms
}

SolverState {
    time
    proposed_dt
    matrix
    rhs
    convergence_status
}
~~~

A safe step sequence is:

~~~text
assemble trial system
    ↓
solve
    ↓
check residual/convergence
    ↓
estimate integration error
    ↓
accept or reject step
    ↓
publish accepted state only
~~~

Rejected steps must not overwrite the last accepted physical state.

These are general numerical-solver principles, not current ChrisOS structures.

## Complexity and sparsity

For a circuit with (n) unknowns, a dense factorization is approximately (O(n^3)), but circuit matrices are usually sparse.

Transient simulation repeatedly solves matrices with similar topology.

Performance therefore depends on:

- sparse matrix ordering;
- factorization reuse;
- nonlinear iteration count;
- number of time steps;
- adaptive-step acceptance rate;
- event density from switches and piecewise models.

The total cost can be dominated by many solves rather than one large solve.

## Energy validation

Energy provides strong transient invariants.

For an ideal source-free RLC network with (R>0),

~~~text
d/dt
[
1/2 C v_C²
+
1/2 L i_L²
]
=
- R i²
<= 0
~~~

under the series orientation.

So stored energy must monotonically decrease in the passive source-free model.

If a numerical simulation produces growing total energy without an active source, either the model contains an active element, the sign convention is inconsistent, or the integration method/time step is unstable.

## Switching and impulse boundaries

Ideal switches can create mathematically singular events.

Examples:

- connecting ideal capacitors with different voltages using zero resistance;
- forcing an ideal inductor current to change instantaneously;
- switching incompatible ideal voltage sources together.

Real circuits contain finite resistance, inductance, capacitance, switch transition time and electromagnetic radiation.

A physically meaningful model often requires adding those nonidealities rather than accepting infinite current or voltage as a literal prediction.

## Measurement bandwidth

Observed transient behavior depends on measurement bandwidth and probe loading.

A fast voltage edge contains high-frequency spectral components. A limited-bandwidth instrument can report:

- slower apparent rise time;
- reduced overshoot;
- altered ringing.

Probe capacitance or ground inductance can also modify the circuit.

Transient validation therefore requires both model bandwidth and measurement bandwidth to be stated.

## Relation to digital timing

Digital signals are interpreted as logic states, but their physical transitions are analog transients.

A simplified timing chain is:

~~~text
driver changes conduction state
    ↓
node capacitance charges/discharges
    ↓
interconnect R/L/C shape waveform
    ↓
receiver threshold is crossed
    ↓
digital state changes
~~~

Propagation delay, slew rate, overshoot and ringing emerge from these dynamics.

A digital abstraction is valid only when electrical behavior remains inside the interface's timing and voltage margins.

## Relation to power delivery

Load transients are central to computer power systems.

A sudden increase in current can produce rail droop through:

~~~text
ΔV_R = I R
ΔV_L = L dI/dt
ΔV_C = (1/C) ∫ i_deficit dt
~~~

These mechanisms act together across regulator, board, package and die.

The dedicated power-delivery chapter develops impedance targets, decoupling hierarchy and regulator response. The present chapter supplies the underlying transient mathematics.

## Relation to ChrisOS

ChrisOS runs above these analog dynamics.

The operating system may cause workload transitions that change CPU or device activity, but the resulting electrical response is implemented by hardware and firmware beneath the OS abstraction.

Current ChrisOS source does not contain an RC/RLC circuit solver documented by this chapter.

If future power-management, telemetry or simulation code is added, its implementation must be documented separately with concrete files, symbols, ownership, concurrency and validation evidence.

## Privilege, concurrency and ABI boundary

RC/RL/RLC differential equations have no CPU privilege level, lock ordering or ABI.

Those concerns appear only when software represents or controls hardware states.

A transient simulator implemented in software would require:

- ownership of state vectors;
- synchronization for parallel assembly;
- deterministic acceptance/rejection of time steps;
- numerical error propagation policies;
- file or API formats if state is externalized.

None of those software contracts are claimed to exist in ChrisOS here.

## Failure modes

| Failure | Meaning |
|---|---|
| missing initial condition | dynamic state is under-specified |
| wrong switch topology | differential equation describes the wrong circuit |
| violated capacitor voltage continuity | implies unmodeled impulse current |
| violated inductor current continuity | implies unmodeled impulse voltage |
| negative passive R | model becomes active/unstable |
| zero damping assumed for real circuit | ringing persists unrealistically |
| unstable numerical step | simulated energy grows spuriously |
| time step too coarse | fast poles/events are missed |
| ignored parasitics | edge/ringing prediction can be wrong |
| using 5τ as exact equality | confuses approximation with asymptotic behavior |

## Validation evidence

The executable checker for this batch verifies deterministic examples for:

- RC charging and discharging;
- RL energization and decay;
- first-order time-constant fractions;
- capacitor/inductor continuity invariants;
- series RLC damping classification;
- damped natural frequency;
- standard second-order overshoot;
- passive source-free RLC energy decrease;
- an explicit-Euler stability boundary example;
- bilingual chapter anchors.

These checks validate equations and editorial invariants. They do not constitute a SPICE transient solver or hardware waveform validation.

## Current limitations

This chapter does not yet develop:

- complex phasors and impedance networks;
- Fourier decomposition;
- RMS and complex power;
- transformer coupling;
- distributed transmission lines;
- nonlinear switch/device models;
- stochastic noise;
- power-regulator control loops;
- current ChrisOS implementation.

Those topics require additional assumptions and are separated in the curriculum.

## Roadmap boundary

The conceptual progression is

~~~text
R/C/L constitutive equations
    ↓
time-domain differential equations
    ↓
natural + forced response
    ↓
poles, damping and settling
    ↓
sinusoidal steady state
    ↓
phasors, impedance and frequency response
~~~

The next chapter replaces repeated sinusoidal differentiation with algebraic complex impedance while preserving the same underlying differential equations.

## Revision provenance

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because this chapter does not claim that current ChrisOS implements an RC/RLC simulator or analog control subsystem. The reviewed revision records corpus provenance and the implementation boundary.
