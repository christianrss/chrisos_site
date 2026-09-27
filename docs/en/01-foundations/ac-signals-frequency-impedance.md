---
id: ac-signals-frequency-impedance
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - rc-rlc-transients
  - vectors-complex-numbers-systems
related:
  - electromagnetic-induction-transformers
  - transmission-lines-differential-signals
  - noise-grounding-signal-integrity
  - power-delivery-regulation
  - cmos-switching-power
---

# AC signals, phase, frequency and impedance

<div class="abstract">
Sinusoidal steady-state analysis converts linear differential circuit equations into algebra over complex numbers. Frequency, phase, RMS value, phasors, impedance and admittance let resistors, capacitors and inductors be solved with the same network methods used for DC, while preserving the physical meaning of stored and dissipated energy. This chapter derives the phasor method, complex impedance, resonance, transfer functions, frequency response, passive complex power, filter behavior, numerical representation and the boundaries of sinusoidal steady-state models.
</div>

## Prerequisites and scope

This chapter assumes:

- complex numbers and Euler's identity;
- Ohm's law, KCL and KVL;
- capacitor and inductor constitutive equations;
- first- and second-order transient behavior;
- the distinction between natural and forced response.

The analysis here is restricted to **linear time-invariant circuits in sinusoidal steady state** unless explicitly stated otherwise.

That phrase carries three assumptions:

~~~text
linear
    superposition applies

time invariant
    component parameters do not change with time

steady state
    natural transients have decayed or are intentionally excluded
~~~

The method does not replace time-domain physics. It is a compact representation of the long-term response to sinusoidal forcing.

Current ChrisOS source does not implement the AC circuit analyzer described here.

## Period, frequency and angular frequency

For a periodic signal with period (T),

~~~text
f = 1/T
~~~

where (f) is measured in hertz.

The BIPM SI Brochure defines hertz as:

~~~text
1 Hz = 1 s^-1
~~~

Angular frequency is

~~~text
ω = 2πf
~~~

with unit rad/s.

Although radians are dimensionless in SI dimensional algebra, writing rad/s is useful because it distinguishes angular frequency from cycles per second.

The 2026 revision of the BIPM SI Brochure remains the metrological reference for these derived units.

## Sinusoidal signals

A sinusoidal voltage can be written:

~~~text
v(t)
=
V_m cos(ωt + φ)
~~~

where:

~~~text
V_m   peak amplitude
ω     angular frequency
φ     phase angle
~~~

Equivalent sine/cosine forms differ only by phase shift.

The signal repeats after:

~~~text
T = 2π/ω
~~~

The phase angle identifies where the waveform lies within its cycle relative to a chosen reference.

Absolute phase without a reference has limited meaning; phase difference is usually the physically relevant quantity.

## Phase difference

For two sinusoids of equal frequency,

~~~text
v1(t) = A cos(ωt + φ1)
v2(t) = B cos(ωt + φ2)
~~~

the phase difference is:

~~~text
Δφ = φ2 - φ1
~~~

If (Deltaphi>0), waveform 2 leads waveform 1 under the usual convention.

If (Deltaphi<0), waveform 2 lags.

A phase difference also corresponds to a time shift:

~~~text
Δt = Δφ / ω
~~~

when phase is expressed in radians.

Because phase wraps modulo (2π), a reported phase must be interpreted with a chosen branch and frequency.

## Peak, peak-to-peak and RMS

For a zero-mean sinusoid:

~~~text
v(t)=V_m cos(ωt+φ)
~~~

the peak value is (V_m).

The peak-to-peak value is:

~~~text
V_pp = 2 V_m
~~~

The RMS value is:

~~~text
V_rms
=
sqrt[
(1/T) ∫_0^T v²(t) dt
]
~~~

which evaluates to:

~~~text
V_rms = V_m / sqrt(2)
~~~

Similarly:

~~~text
I_rms = I_m / sqrt(2)
~~~

for a sinusoidal current.

RMS is not "average magnitude". It is the square root of the mean square and is especially useful because a resistor dissipates the same average power under a sinusoidal RMS value as under a DC value of equal magnitude.

## Mean value and waveform dependence

For a zero-mean sinusoid over a complete period:

~~~text
average(v) = 0
~~~

yet:

~~~text
V_rms != 0
~~~

RMS relationships depend on waveform shape.

For example, (V_m/sqrt{2}) is specific to a sinusoid. A square wave, pulse train or distorted periodic signal has a different peak-to-RMS relation.

This distinction matters when digital waveforms or switching regulators are analyzed; they are not generally single-frequency sinusoids.

## Complex exponential representation

Euler's identity gives:

~~~text
e^(jθ) = cos θ + j sin θ
~~~

A real sinusoid can be represented as the real part of a rotating complex exponential:

~~~text
v(t)
=
Re{ V_m e^(jφ) e^(jωt) }
~~~

Define the complex amplitude:

~~~text
V_hat = V_m e^(jφ)
~~~

Then:

~~~text
v(t)=Re{V_hat e^(jωt)}
~~~

Because every signal in a linear sinusoidal steady-state network shares the same (e^{jωt}) factor, circuit equations can be solved using only the complex amplitudes.

This is the core of the phasor method.

## Phasor convention

A phasor may be represented using either peak or RMS magnitude.

Both conventions are valid if used consistently.

This chapter uses **RMS phasors** for power calculations and identifies peak magnitude explicitly when deriving time-domain signals.

An RMS phasor can be written:

~~~text
V = V_rms ∠φ
~~~

or in rectangular form:

~~~text
V = V_rms(cosφ + j sinφ)
~~~

Conversion:

~~~text
rectangular:
    a + jb

polar:
    M ∠φ

M = sqrt(a²+b²)
φ = atan2(b,a)
~~~

## Differentiation in the phasor domain

For:

~~~text
x(t)
=
Re{X e^(jωt)}
~~~

the derivative is:

~~~text
dx/dt
=
Re{jωX e^(jωt)}
~~~

Therefore differentiation maps to:

~~~text
d/dt
    ↔
jω
~~~

for sinusoidal steady-state phasors.

Integration maps to:

~~~text
∫ dt
    ↔
1/(jω)
~~~

subject to exclusion of independent integration constants, which correspond to natural/DC components not represented by the steady-state phasor.

## Resistor impedance

For a resistor:

~~~text
v = Ri
~~~

so in phasor form:

~~~text
V = R I
~~~

Therefore:

~~~text
Z_R = R
~~~

A positive ideal resistor has zero phase angle:

~~~text
∠Z_R = 0
~~~

Voltage and current are in phase.

## Inductor impedance

For an ideal inductor:

~~~text
v = L di/dt
~~~

Using the phasor derivative:

~~~text
V = jωL I
~~~

Therefore:

~~~text
Z_L = jωL
~~~

Magnitude:

~~~text
|Z_L| = ωL
~~~

Phase:

~~~text
∠Z_L = +90°
~~~

Thus voltage leads current by (90^circ), or current lags voltage by (90^circ).

At DC limit (omega	o0), ideal inductor impedance tends to zero, matching the DC steady-state short-circuit model.

## Capacitor impedance

For an ideal capacitor:

~~~text
i = C dv/dt
~~~

so:

~~~text
I = jωC V
~~~

and:

~~~text
Z_C
=
V/I
=
1/(jωC)
=
-j/(ωC)
~~~

Magnitude:

~~~text
|Z_C| = 1/(ωC)
~~~

Phase:

~~~text
∠Z_C = -90°
~~~

Current leads voltage by (90^circ).

As (omega	o0), capacitor impedance magnitude tends to infinity, matching the DC open-circuit model.

## Impedance and admittance

Impedance generalizes resistance:

~~~text
Z = V/I
~~~

with units of ohms.

Write:

~~~text
Z = R + jX
~~~

where:

~~~text
R   resistance
X   reactance
~~~

For ideal passive elements:

~~~text
X_L = +ωL
X_C = -1/(ωC)
~~~

Admittance is:

~~~text
Y = 1/Z
~~~

with units of siemens.

Write:

~~~text
Y = G + jB
~~~

where (G) is conductance and (B) susceptance.

Admittance is often convenient for parallel networks, just as conductance is convenient for parallel resistors.

## KCL and KVL with phasors

Because the phasor transform is linear, Kirchhoff equations retain their algebraic form.

KCL:

~~~text
Σ I_k = 0
~~~

KVL:

~~~text
Σ V_k = 0
~~~

Constitutive relations become:

~~~text
V = Z I
~~~

Therefore nodal analysis can use complex admittance matrices:

~~~text
Y V = I
~~~

The algorithms are structurally similar to DC nodal analysis, except arithmetic is complex and element values depend on frequency.

## Series impedance

For elements in series, the same current flows and voltages add:

~~~text
Z_eq = Σ Z_k
~~~

For series RLC:

~~~text
Z
=
R
+
jωL
+
1/(jωC)
~~~

which simplifies to:

~~~text
Z
=
R
+
j[
ωL - 1/(ωC)
]
~~~

Magnitude:

~~~text
|Z|
=
sqrt{
R²
+
[ωL - 1/(ωC)]²
}
~~~

Phase:

~~~text
φ_Z
=
atan2(
ωL - 1/(ωC),
R
)
~~~

## Parallel admittance

For elements in parallel, voltage is common and currents add.

Therefore:

~~~text
Y_eq = Σ Y_k
~~~

For ideal R, L and C in parallel:

~~~text
Y
=
1/R
+
1/(jωL)
+
jωC
~~~

or:

~~~text
Y
=
1/R
+
j[
ωC - 1/(ωL)
]
~~~

Parallel analysis is often cleaner in admittance than by repeatedly computing reciprocal impedances.

## Series resonance

For a series RLC circuit, resonance occurs when net reactance is zero:

~~~text
ωL - 1/(ωC) = 0
~~~

Therefore:

~~~text
ω_0 = 1/sqrt(LC)
~~~

and:

~~~text
f_0 = 1/(2πsqrt(LC))
~~~

At ideal series resonance:

~~~text
Z = R
~~~

and current magnitude is maximized for a fixed sinusoidal source voltage when (R>0).

Although source current is limited by (R), individual capacitor and inductor voltages can be much larger than the source when (Q) is high.

## Parallel resonance

An ideal parallel RLC network resonates when its net susceptance is zero:

~~~text
ωC - 1/(ωL) = 0
~~~

giving the same ideal:

~~~text
ω_0 = 1/sqrt(LC)
~~~

At resonance, ideal reactive branch currents can be large while net source current is reduced.

Real parallel resonators include losses and parasitics, so the exact resonant frequency and peak impedance depend on the practical topology.

## Q factor in series RLC

For the ideal series RLC model at resonance:

~~~text
Q
=
ω_0 L/R
=
1/(ω_0 R C)
=
(1/R)sqrt(L/C)
~~~

For weak damping:

~~~text
Q ≈ 1/(2ζ)
~~~

where (zeta) is the damping ratio from the transient chapter.

This connects time-domain decay to frequency-domain selectivity.

Higher Q generally means:

- narrower resonance;
- slower decay of stored oscillatory energy;
- larger reactive energy relative to dissipation per cycle.

## Bandwidth relationship

For a canonical series RLC resonance, the half-power bandwidth is:

~~~text
Δω = R/L
~~~

and:

~~~text
Q = ω_0 / Δω
~~~

under the ideal model.

Half-power points occur where the power dissipated in the resistor is half the resonant maximum for a constant source voltage.

Equivalent bandwidth relations depend on topology and definition; the formula should not be transferred blindly to arbitrary filters.

## Transfer functions

A linear circuit can be described by a transfer function:

~~~text
H(jω)
=
V_out(jω)/V_in(jω)
~~~

or another chosen output/input ratio.

The magnitude response is:

~~~text
|H(jω)|
~~~

and phase response:

~~~text
∠H(jω)
~~~

The transfer function describes the forced sinusoidal steady-state relationship.

It does not by itself encode arbitrary initial conditions; those belong to the complete time-domain solution or Laplace transform with initial terms.

## RC low-pass filter

For a series resistor followed by a capacitor to reference, with output across the capacitor:

~~~text
Z_C = 1/(jωC)
~~~

Voltage division gives:

~~~text
H(jω)
=
Z_C/(R+Z_C)
=
1/(1+jωRC)
~~~

Magnitude:

~~~text
|H|
=
1/sqrt(1+(ωRC)²)
~~~

Phase:

~~~text
φ
=
-atan(ωRC)
~~~

The cutoff angular frequency is:

~~~text
ω_c = 1/(RC)
~~~

and:

~~~text
f_c = 1/(2πRC)
~~~

At cutoff:

~~~text
|H| = 1/sqrt(2)
~~~

which corresponds to approximately (-3.0103) dB in power-compatible voltage ratio for equal impedances.

## RC high-pass filter

For a series capacitor followed by resistor to reference, with output across the resistor:

~~~text
H(jω)
=
jωRC/(1+jωRC)
~~~

Magnitude:

~~~text
|H|
=
ωRC/sqrt(1+(ωRC)²)
~~~

Phase tends from (+90^circ) at very low frequency toward (0^circ) at high frequency.

The same cutoff:

~~~text
ω_c = 1/(RC)
~~~

separates the transition region.

## Decibels

A dimensionless amplitude ratio (A) may be expressed as:

~~~text
20 log10 |A| dB
~~~

when (A) is a voltage/current-like amplitude ratio under compatible impedance assumptions.

A power ratio uses:

~~~text
10 log10(P2/P1) dB
~~~

The factor difference exists because power often scales with amplitude squared.

Decibels are logarithmic ratios, not absolute physical units unless referenced to a specified level such as dBm.

## Bode magnitude asymptotes

For a first-order low-pass:

~~~text
H(s)=1/(1+s/ω_c)
~~~

the magnitude is approximately:

~~~text
0 dB/decade
    below the corner

-20 dB/decade
    well above the corner
~~~

A first-order high-pass has the opposite low-frequency slope.

Each simple pole contributes approximately (-20) dB/decade at frequencies well above its break frequency; each simple zero contributes approximately (+20) dB/decade.

Exact response near corners differs from the straight-line asymptotes.

## Pole/zero interpretation

A rational transfer function can be written conceptually:

~~~text
H(s)
=
K
Π(s-z_k)
/
Π(s-p_k)
~~~

where (z_k) are zeros and (p_k) are poles.

Evaluating on:

~~~text
s = jω
~~~

gives the sinusoidal frequency response.

Poles near the imaginary axis create strong frequency-selective behavior and slow time-domain decay.

The same poles that governed RLC transients therefore govern AC resonance.

## Average power for sinusoidal signals

Let:

~~~text
v(t)=sqrt(2)V_rms cos(ωt+φ_v)
i(t)=sqrt(2)I_rms cos(ωt+φ_i)
~~~

Define phase difference:

~~~text
φ = φ_v - φ_i
~~~

Average real power is:

~~~text
P
=
V_rms I_rms cosφ
~~~

For a pure resistor:

~~~text
φ = 0
P = V_rms I_rms
~~~

For an ideal pure inductor or capacitor:

~~~text
|φ| = 90°
P = 0
~~~

because energy is alternately stored and returned with zero net average over a cycle.

## Complex power

Using RMS phasors and passive sign convention:

~~~text
S = V I*
~~~

where (I^*) is the complex conjugate of current.

Write:

~~~text
S = P + jQ
~~~

where:

~~~text
P   real/active power [W]
Q   reactive power [var]
|S| apparent power [VA]
~~~

For sinusoidal steady state:

~~~text
P = V_rms I_rms cosφ
Q = V_rms I_rms sinφ
|S| = V_rms I_rms
~~~

With the common passive convention:

~~~text
inductive load: Q > 0
capacitive load: Q < 0
~~~

## Power factor

For sinusoidal voltage and current:

~~~text
PF = P/|S| = cosφ
~~~

A low-magnitude power factor means more RMS current is required for a given real power at fixed RMS voltage.

For distorted nonsinusoidal waveforms, displacement phase angle alone is insufficient. Total power factor also depends on harmonic distortion.

Therefore (PF=cosphi) must be identified as the sinusoidal case, not a universal rule.

## Reactive energy exchange

Reactive power does not mean "power that does nothing".

Capacitors and inductors exchange energy with the source and with each other.

For ideal elements, average real power over a cycle is zero, but instantaneous power is not.

Reactive current still causes:

- conductor (I²R) loss elsewhere;
- source and converter current stress;
- voltage drop across nonzero impedance.

This is why reactive compensation matters in AC power systems even when ideal reactive components dissipate no average power themselves.

## Frequency response versus transient response

Time and frequency descriptions are two views of the same linear dynamics.

For a first-order low-pass:

~~~text
time domain:
    τ = RC

frequency domain:
    ω_c = 1/(RC)
~~~

therefore:

~~~text
ω_c = 1/τ
~~~

For second-order systems, damping ratio and natural frequency likewise map to resonance shape and pole location.

A design cannot independently choose arbitrary time response and frequency response; both arise from the same poles and zeros.

## Fourier-series context

Any sufficiently well-behaved periodic waveform can be represented by a sum of sinusoids:

~~~text
x(t)
=
a0
+
Σ[
a_n cos(nω0 t)
+
b_n sin(nω0 t)
]
~~~

A linear circuit can process each harmonic separately and the responses can be summed.

This makes frequency response useful even for non-sinusoidal periodic signals.

However:

- nonlinear circuits generate new frequencies;
- switching discontinuities can require many harmonics;
- distributed effects may become important at high harmonic frequency.

## Fourier-transform context

Aperiodic signals can be represented through a continuous frequency spectrum under appropriate transform conditions.

The Fourier transform conceptually maps:

~~~text
time waveform
    ↔
frequency spectrum
~~~

For linear time-invariant systems:

~~~text
Y(jω)
=
H(jω) X(jω)
~~~

This relation underlies filtering, channel analysis and signal integrity.

Full transform theory extends beyond the sinusoidal circuit methods required here.

## Sampling and aliasing boundary

If an analog waveform is sampled in software or hardware, frequency-domain interpretation must account for sampling.

For an ideal band-limited signal with highest frequency (f_{max}), reconstruction requires sampling above twice that bandwidth under the Nyquist-Shannon condition:

~~~text
f_s > 2 f_max
~~~

Real anti-alias filters, finite aperture and non-band-limited signals complicate this ideal statement.

This is relevant to hardware telemetry and oscilloscopes but is not a claim about current ChrisOS sampling code.

## Complex nodal analysis

A frequency-domain circuit solver can assemble a complex admittance matrix at each frequency.

For a branch between nodes (a) and (b) with admittance (Y), stamping contributes:

~~~text
A[a,a] += Y
A[b,b] += Y
A[a,b] -= Y
A[b,a] -= Y
~~~

The matrix equation is:

~~~text
A(ω) V(ω) = b(ω)
~~~

Because capacitor and inductor admittances depend on (omega), a frequency sweep changes matrix values even when topology remains fixed.

The solver can often reuse sparsity structure while recomputing numeric factorization.

## Frequency sweeps

A logarithmic sweep is common because electronic systems often span many decades of frequency.

Example sequence:

~~~text
10 Hz
100 Hz
1 kHz
10 kHz
...
~~~

At each point:

~~~text
assemble/update complex matrix
solve
measure requested transfer quantities
record magnitude and phase
~~~

The computational cost is roughly the cost of a complex solve times the number of frequency points, with opportunities for symbolic sparsity reuse.

## Numerical issues in complex arithmetic

Complex circuit solving inherits ordinary linear-algebra problems:

- singular matrices;
- ill conditioning;
- extreme scale separation;
- cancellation;
- overflow/underflow.

Additional practical issues include phase wrapping and branch cuts.

For example, a phase plotted as:

~~~text
+179°
-179°
~~~

may represent a smooth physical change of only (2^circ) after unwrapping.

Numerical software must separate raw principal phase from continuous unwrapped presentation.

## Representation in software

A generic phasor representation might use:

~~~text
Complex {
    real
    imag
}
~~~

or polar magnitude/phase.

Rectangular form is usually better for addition and linear solves.

Polar form is convenient for interpretation, multiplication and division.

Conversions should use:

~~~text
magnitude = hypot(real, imag)
phase     = atan2(imag, real)
~~~

rather than arctangent of imag/real, which loses quadrant information.

These are generic numerical practices, not ChrisOS implementation claims.

## Memory and ownership in a frequency solver

A generic frequency-domain solver may own:

~~~text
topology
sparse matrix pattern
frequency-dependent values
right-hand side
solution vector
measurement definitions
~~~

Topology can be immutable across a sweep while numeric values change.

Parallelizing independent frequencies is often straightforward because each frequency point is independent, provided each worker has isolated numeric matrix state or safe factorization storage.

Again, this describes general solver architecture only.

## Performance trade-offs

Frequency-domain analysis is efficient when:

- the system is linear;
- interest is in steady-state response;
- many time cycles would otherwise be required;
- only selected frequencies are needed.

Time-domain simulation is preferable when:

- switching is nonlinear;
- initial conditions matter;
- events are nonperiodic;
- saturation or clipping occurs;
- waveform shape itself is central.

No single domain is universally superior.

## Real components and frequency dependence

Ideal R, L and C values are constant parameters.

Real components have frequency-dependent models.

Examples:

~~~text
capacitor:
    ESR + ESL + dielectric loss

inductor:
    winding resistance + core loss + parasitic C

resistor:
    parasitic L/C + skin effect at high frequency
~~~

A component can cross self-resonance and behave unlike its low-frequency label.

Frequency analysis is only as accurate as the component model.

## Transmission-line boundary

The lumped impedance method assumes dimensions are electrically small enough that one node potential can represent a conductor segment.

When propagation delay becomes comparable to signal timing, a distributed model is needed.

A transmission line uses per-unit-length quantities:

~~~text
R'
L'
G'
C'
~~~

and supports traveling waves, reflections and characteristic impedance.

The next relevant chapter develops those effects.

## Signal-integrity relevance

Digital edges contain broad spectra.

A nominal "100 MHz" digital clock can require modeling well above 100 MHz because edge rate determines high-frequency content.

Frequency response helps identify:

- resonances;
- attenuation;
- phase distortion;
- coupling;
- power-distribution impedance peaks.

The important engineering frequency is therefore not always the repetition frequency printed on a digital specification.

## Power-delivery relevance

A power-distribution network is often characterized by impedance versus frequency:

~~~text
Z_PDN(f)
~~~

Different elements dominate at different frequencies:

~~~text
regulator/control loop
    low frequency

bulk capacitors
    low-mid frequency

MLCC/local decoupling
    mid-high frequency

package/die parasitics
    high frequency
~~~

Resonances and anti-resonances can increase impedance at specific frequencies.

The dedicated power-delivery chapter builds on the impedance concepts established here.

## Relation to ChrisOS

ChrisOS usually observes hardware through digital architectural interfaces rather than by manipulating phasors.

Still, AC and frequency behavior underlies:

- clock distribution;
- serial links;
- memory buses;
- power-delivery networks;
- oscillators;
- analog sensor front ends;
- EMI/EMC behavior.

Current ChrisOS source does not provide the generic phasor/frequency-domain circuit solver described in this chapter.

Any future telemetry, DSP or hardware-analysis implementation must be documented from concrete source files and device specifications.

## Privilege, concurrency and ABI boundary

Frequency, phase and impedance have no CPU privilege level.

Software that measures or computes them may have:

- sampling APIs;
- buffer ownership;
- synchronization;
- numeric format contracts;
- device register ABIs.

Those contracts are implementation-specific and must not be inferred from the circuit equations.

No such current ChrisOS ABI is claimed here.

## Failure modes

| Failure | Consequence |
|---|---|
| mixing peak and RMS phasors | factor-of-(sqrt2) or factor-of-2 power errors |
| degrees/radians confusion | wrong phase/time conversion |
| using sinusoidal impedance for transient initial conditions | natural response is lost |
| applying (PF=cosphi) to distorted waveforms | incorrect total power factor |
| ignoring component parasitics | wrong resonance/high-frequency behavior |
| using lumped model beyond propagation limit | reflections/distributed effects omitted |
| phase without atan2 | wrong quadrant |
| no phase unwrapping | artificial discontinuities in plots |
| singular complex nodal matrix | floating/inconsistent network |
| too-sparse frequency sweep | narrow resonances may be missed |

## Validation evidence

The executable checker for this batch verifies deterministic cases for:

- Hz/period/angular-frequency conversion;
- sinusoidal RMS and peak-to-peak values;
- phase-to-time conversion;
- resistor, capacitor and inductor impedance;
- series RLC resonance;
- RC low-pass magnitude and phase at cutoff;
- RC high-pass magnitude at cutoff;
- decibel conversion at (1/sqrt2);
- real/reactive/apparent power and power factor;
- equivalence between (omega_c=1/RC) and (1/	au);
- complex nodal arithmetic for a small network;
- bilingual documentation anchors.

The checks validate equations and documentation invariants, not a calibrated impedance analyzer or RF measurement system.

## Current limitations

This chapter intentionally stops before:

- transformer turns-ratio and magnetizing models;
- transmission-line wave equations;
- S-parameters;
- electromagnetic radiation;
- nonlinear harmonic generation;
- oscillator startup;
- PLL/control-loop analysis;
- concrete ChrisOS AC/DSP implementation.

These require additional device, field or software evidence.

## Roadmap boundary

The conceptual chain now becomes:

~~~text
time-domain R/C/L dynamics
    ↓
sinusoidal steady state
    ↓
phasors and complex impedance
    ↓
frequency response and resonance
    ↓
induction/transformers
    ↓
transmission lines and differential signaling
    ↓
noise, grounding and signal integrity
    ↓
power-delivery impedance
~~~

The phasor method remains valid only inside its linear sinusoidal steady-state assumptions.

## Revision provenance

Reviewed against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because this chapter does not claim that current ChrisOS implements a phasor, impedance or frequency-domain circuit solver. The reviewed revision records corpus provenance and the implementation boundary. Metrological unit references were checked against the BIPM SI Brochure, 9th edition, updated in June 2026.
