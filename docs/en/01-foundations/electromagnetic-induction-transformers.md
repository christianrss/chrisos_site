---
id: electromagnetic-induction-transformers
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - ac-signals-frequency-impedance
  - capacitance-inductance
related:
  - transmission-lines-differential-signals
  - power-delivery-regulation
  - clock-timing
---

# Electromagnetic induction and transformers

<div class="abstract">
Electromagnetic induction links changing magnetic flux to electric field and voltage. It is the physical basis of transformers, inductors, generators, current transformers, many power converters and a large class of unwanted coupling mechanisms. This chapter derives Faraday's law, Lenz's law, flux linkage, mutual inductance, ideal and non-ideal transformer models, reflected impedance, magnetizing current, core loss, saturation, leakage inductance, parasitic capacitance, isolation constraints and the limits of lumped models. It also separates these physical mechanisms from current ChrisOS behavior: the operating system does not implement a field solver or transformer model.
</div>

## Prerequisites and scope

Required foundations are:

- electric charge, field, potential and energy;
- voltage, current, resistance and power;
- capacitance and inductance;
- Kirchhoff circuit laws;
- AC frequency, phase, phasors and impedance;
- basic vector orientation and signed quantities.

The chapter uses the lumped-circuit approximation where appropriate, but begins from field quantities because a transformer cannot be understood correctly as a mysterious voltage-ratio component.

Current ChrisOS source does **not** implement electromagnetic field simulation, magnetic-component design or a transformer solver. The reviewed source revision is recorded only to make that implementation boundary explicit.

## Magnetic flux

Magnetic flux through an oriented surface (S) is

~~~text
Φ_B = ∫_S B · dA
~~~

where (B) is magnetic flux density and (dA) is the oriented differential area.

For approximately uniform (B) over a planar area (A),

~~~text
Φ_B = B A cos θ
~~~

where θ is the angle between the field and the surface normal.

The SI unit of magnetic flux is the weber:

~~~text
1 Wb = 1 V·s
~~~

Flux is therefore not "the amount of current in a core." It is a surface integral of magnetic flux density. Current may produce magnetic field, but geometry and material response determine the resulting flux.

## Faraday-Maxwell law

The integral form of Faraday's law is

~~~text
∮_C E · dl = - d/dt ∫_S B · dA
~~~

for a contour (C) bounding surface (S).

The left side is the circulation of electric field around the contour. The right side is the negative time derivative of magnetic flux.

For a conducting loop represented as a circuit, the induced electromotive force is

~~~text
e = - dΦ_B/dt
~~~

For a winding of (N) turns that link approximately the same flux,

~~~text
λ = N Φ_B
e = - dλ/dt = -N dΦ_B/dt
~~~

where λ is flux linkage.

The minus sign is not decoration. It encodes orientation and the physical opposition summarized by Lenz's law.

## Lenz's law and energy consistency

Lenz's law states that the induced response has a direction that opposes the change in flux that produced it.

A useful energy argument explains why. If induced current reinforced the initiating change without another energy source, a small change could create more field, which would create more current, producing energy without work. The negative sign in Faraday's law prevents that interpretation.

"Opposes the change" does not mean the induced field is always opposite the original field. If original flux is decreasing, the induced response tends to support its previous direction. The opposition is to (dΦ/dt).

## Flux linkage and self-inductance

For a linear magnetic system, flux linkage can be proportional to winding current:

~~~text
λ = L i
~~~

Then

~~~text
v = dλ/dt = L di/dt
~~~

under the passive circuit sign convention.

More generally,

~~~text
v = dλ(i,t)/dt
~~~

and (L) need not be constant. Ferromagnetic cores can make λ versus i nonlinear and history-dependent.

The familiar ideal-inductor equation is therefore a reduced circuit model of electromagnetic induction, not an independent law.

## Two coupled windings

Consider two windings. In a linear reciprocal model,

~~~text
λ1 = L1 i1 + M i2
λ2 = M i1 + L2 i2
~~~

Differentiating,

~~~text
v1 = L1 di1/dt + M di2/dt
v2 = M di1/dt + L2 di2/dt
~~~

The parameter (M) is mutual inductance.

A common dimensionless coupling coefficient is

~~~text
k = M / sqrt(L1 L2)
~~~

so that

~~~text
M = k sqrt(L1 L2)
~~~

For passive coupled inductors in the ordinary linear model,

~~~text
0 ≤ |k| ≤ 1
~~~

The sign of mutual terms depends on winding orientation and the selected reference directions.

## Dot convention

Circuit diagrams use dots to preserve winding polarity without drawing the physical winding direction.

One consistent interpretation is:

~~~text
current entering dotted terminal of winding 1
    → positive mutually induced voltage at dotted terminal of winding 2
~~~

provided the voltage reference is defined dotted-to-undotted.

Changing either current or voltage reference changes the algebraic sign. Memorizing a sign without declaring references is unsafe.

The dot convention becomes critical in flyback converters, coupled inductors, current transformers and feedback windings.

## Ideal transformer assumptions

The ideal transformer is a limiting model with:

- perfect coupling;
- zero winding resistance;
- zero leakage inductance;
- infinite magnetizing inductance;
- no hysteresis or eddy-current loss;
- no parasitic capacitance;
- no dielectric leakage;
- no saturation;
- no propagation delay.

It is deliberately unrealizable. Its value is that it isolates the turns-ratio constraint from losses and parasitics.

Let the turns ratio be

~~~text
a = N1 / N2
~~~

With compatible dot and voltage references,

~~~text
V1 / V2 = N1 / N2 = a
~~~

Thus

~~~text
V2 = V1 / a
~~~

for this definition of (a).

## Current ratio and power

An ideal transformer stores no net energy and dissipates no power. Instantaneous power balance, with signs chosen consistently, requires

~~~text
p1 + p2 = 0
~~~

In magnitude for sinusoidal steady state,

~~~text
|V1 I1| = |V2 I2|
~~~

Combining with the voltage ratio gives the inverse current ratio:

~~~text
I1 / I2 = N2 / N1 = 1/a
~~~

in magnitude.

A step-up transformer raises voltage and correspondingly lowers current capability for the same transferred apparent power. It does not create power.

## Reflected impedance

Suppose an impedance (Z_L) is connected to the secondary.

~~~text
Z_L = V2 / I2
~~~

Using the ideal ratios, the impedance seen at the primary is

~~~text
Z_in = V1 / I1
     = (N1/N2)^2 Z_L
     = a² Z_L
~~~

This square law is fundamental.

Example:

~~~text
N1/N2 = 10
Z_L   = 8 Ω

Z_in = 10² × 8 Ω
     = 800 Ω
~~~

The transformer changes the voltage/current scaling through which the source observes the load.

## Sinusoidal volts-per-turn relation

For sinusoidal core flux,

~~~text
Φ(t) = Φ_peak sin(ωt)
~~~

Faraday's law gives

~~~text
v(t) = N ω Φ_peak cos(ωt)
~~~

so

~~~text
V_peak = N ω Φ_peak
~~~

and because (V_rms = V_peak/sqrt(2)),

~~~text
V_rms = (2π/sqrt(2)) f N Φ_peak
      ≈ 4.44288 f N Φ_peak
~~~

If flux density is approximately uniform in effective core area (A_e),

~~~text
Φ_peak = B_peak A_e
~~~

therefore

~~~text
V_rms ≈ 4.44 f N A_e B_peak
~~~

for a sinusoidal waveform.

This equation explains why transformer size, frequency, turns and allowable flux density are coupled design variables.

## Volt-seconds and arbitrary waveforms

The more general relation is

~~~text
ΔΦ = (1/N) ∫ v(t) dt
~~~

or, in flux density form under the uniform-core approximation,

~~~text
ΔB = (1/(N A_e)) ∫ v(t) dt
~~~

Therefore core excitation is governed by **volt-seconds**, not voltage alone.

A square-wave transformer in a switching converter must be designed from the applied waveform and duty cycle. Applying the sinusoidal 4.44 coefficient blindly to a square wave is incorrect.

DC voltage is especially dangerous: after switching transients, a sustained nonzero winding voltage drives flux approximately as an integral until saturation or another circuit limitation intervenes.

## Magnetizing inductance

A real transformer requires current to establish alternating core flux.

A first-order equivalent circuit places a magnetizing inductance (L_m) across the ideal transformer's primary.

At angular frequency ω,

~~~text
Z_m = jωL_m
I_m = V1 / (jωL_m)
~~~

Even with the secondary open, the source therefore supplies magnetizing current.

Higher (L_m) reduces idealized magnetizing current at a given voltage and frequency, but real core loss adds an in-phase current component.

## Core permeability and magnetic reluctance

A simple magnetic-circuit analogy uses reluctance

~~~text
ℜ = l / (μ A)
~~~

for a uniform section of magnetic path length (l), area (A) and permeability μ.

Magnetomotive force is

~~~text
F = N i
~~~

and the linear magnetic-circuit approximation gives

~~~text
Φ = F / ℜ
~~~

Then

~~~text
L = N² / ℜ
~~~

for a winding whose flux follows the modeled path.

This analogy is useful but limited. Real cores have fringing, leakage, distributed fields, nonlinear permeability and frequency-dependent loss.

## Saturation

Ferromagnetic materials do not preserve constant permeability indefinitely.

As magnetizing force increases, incremental increases in flux density eventually become much smaller. In a transformer this can cause the effective magnetizing inductance to collapse.

Consequences include:

- rapidly increasing magnetizing current;
- winding heating;
- switch or fuse stress;
- waveform distortion;
- increased core loss;
- possible converter failure.

Saturation is therefore not simply "the core cannot hold more flux." It is a nonlinear region in the constitutive relation between magnetic field strength and flux density.

## Hysteresis

In ferromagnetic material, (B) can depend on magnetic history, not only instantaneous (H).

A cyclic (B-H) trajectory forms a hysteresis loop. The enclosed loop area is associated with energy loss per unit volume per cycle under the usual magnetic interpretation.

This loss increases heating and contributes to no-load transformer power.

A linear constant-(L) model cannot represent hysteresis.

## Eddy currents

A time-varying magnetic field also induces electric fields inside conductive core material. Those fields can drive circulating currents, which dissipate resistive heat.

Mitigation depends on frequency and material:

- laminated electrical steel interrupts large current loops at mains frequencies;
- ferrites have high electrical resistivity and are common at higher switching frequencies;
- powdered cores distribute insulating boundaries.

The best material is application-dependent; high permeability alone is not a sufficient selection criterion.

## Core-loss representation

A simple transformer equivalent circuit often places a resistance (R_c) in parallel with (L_m).

~~~text
            ┌── R_c ──┐
primary ────┤         ├── ideal transformer
            └── jωL_m ┘
~~~

(R_c) is an equivalent loss element, not a literal resistor inside the core.

The model can represent aggregate no-load real power near a chosen operating point, but core loss is nonlinear and frequency-dependent. Wideband converter analysis needs better empirical or physical models.

## Winding resistance

Copper or other conductor has finite resistance.

A practical winding therefore includes series resistance:

~~~text
R_w ≈ ρ l / A_c
~~~

under a DC uniform-current approximation.

At higher frequency, skin and proximity effects redistribute current and increase effective AC resistance. The DC resistance alone can underpredict loss.

Winding resistance produces:

~~~text
P_cu ≈ I_rms² R_ac
~~~

with (R_ac) evaluated for the relevant waveform spectrum and temperature.

## Leakage inductance

Not all flux generated by one winding links the other.

The unshared component appears in circuit models as leakage inductance.

A common equivalent topology is:

~~~text
source
  │
 R1
  │
jωLσ1
  │
[ ideal transformer ]
  │
jωLσ2
  │
 R2
  │
 load
~~~

Leakage inductance causes load-dependent voltage drop and stores energy that can produce switching spikes when current is interrupted.

In power converters it may be undesirable, intentionally exploited, or both depending on topology.

## Parasitic capacitance

Conductors separated by dielectric form capacitance. Transformer windings therefore possess:

- turn-to-turn capacitance;
- layer-to-layer capacitance;
- primary-to-secondary capacitance;
- winding-to-core/shield capacitance.

At sufficiently high frequency, these parasitics create resonances with leakage and magnetizing inductance.

They also provide a displacement-current path across what would otherwise be galvanic isolation.

Thus "isolated transformer" does not mean infinite high-frequency impedance between windings.

## Self-resonance and bandwidth

A transformer has finite bandwidth.

At low frequency, magnetizing reactance may be too small and core flux may become excessive.

At high frequency:

- leakage inductance matters;
- parasitic capacitance matters;
- winding AC resistance rises;
- core loss rises;
- distributed propagation may invalidate the lumped model.

A wideband transformer is therefore a coupled electromagnetic network, not merely an ideal turns ratio.

## Galvanic isolation

A transformer can transfer energy and signals without a direct conductive connection between primary and secondary.

This can establish a galvanic isolation boundary, but the safety properties depend on construction and certification, including:

- insulation system;
- creepage distance;
- clearance distance;
- dielectric withstand;
- working voltage;
- pollution degree;
- material group;
- overvoltage category;
- winding arrangement.

A schematic transformer symbol alone does not establish safe isolation.

Documentation for a real product must use the applicable safety standard and certified component ratings.

## Common-mode coupling

Interwinding capacitance allows common-mode current:

~~~text
i_C = C_ps dv_common/dt
~~~

Fast switching edges can therefore inject noise across an isolation transformer even when no DC conduction path exists.

Electrostatic shields, winding arrangement, reduced capacitance and controlled (dv/dt) can reduce coupling, with trade-offs in size, leakage, cost and other parasitics.

## Transformer equivalent circuit

A useful engineering model combines the dominant nonidealities:

~~~text
                 R1       Lσ1
V1 ─────────────/\/\/────LLLL─────┬────[ ideal N1:N2 ]────Lσ2──/\/\/── ZL
                                    │                         L        R2
                                    ├──── Rc ────┤
                                    │            │
                                    └──── Lm ────┘
~~~

The exact placement of referred elements varies by convention. Secondary quantities can be reflected to the primary by multiplying impedance by (a²), reducing the circuit to one side for analysis.

## Regulation and load behavior

A real transformer's secondary voltage changes with load because winding resistance and leakage reactance produce internal drop.

A simplified phasor estimate is

~~~text
V2,terminal ≈ V2,ideal - I2 (R2 + jXσ2)
~~~

after all quantities are expressed consistently on the same side.

Load power factor matters because the phase of (I2) changes the vector drop. Resistive, inductive and capacitive loads can therefore produce different regulation behavior at equal RMS current.

## Efficiency

Efficiency is

~~~text
η = P_out / P_in
~~~

with

~~~text
P_in = P_out + P_copper + P_core + P_other
~~~

Loss mechanisms depend differently on load and frequency:

| Loss | First-order dependency |
|---|---|
| winding copper | roughly (I²R) |
| core hysteresis | frequency, flux swing, material |
| eddy-current/core dynamic loss | frequency and flux swing |
| dielectric | voltage, frequency, material |
| stray structural loss | leakage field and current |

This is why maximum efficiency occurs at an operating point rather than being a fixed property.

## Autotransformers

An autotransformer shares part of a winding electrically between input and output.

It can reduce copper and size for modest conversion ratios, but it does **not** provide galvanic isolation between the connected terminals.

The ideal ratio equations still help with voltage/current scaling, but the safety topology is fundamentally different from an isolated two-winding transformer.

## Current transformers

A current transformer uses transformer action to scale current for measurement or protection.

An important failure mode is an open secondary while primary current flows. The secondary current that normally counteracts primary ampere-turns disappears, so core flux and secondary voltage can rise dangerously.

Therefore current-transformer secondary handling follows application-specific safety practices. It must not be treated like an ordinary low-power voltage transformer.

## Pulse and switching transformers

Pulse transformers transfer non-sinusoidal waveforms.

Relevant constraints include:

- volt-second balance;
- magnetizing current;
- leakage inductance;
- interwinding capacitance;
- rise/fall-time distortion;
- duty cycle;
- reset mechanism;
- insulation.

A waveform with unequal positive and negative volt-seconds can walk the core toward saturation over repeated cycles.

## Energy-storage boundary: transformer versus coupled inductor

An ideal transformer is conceptually an energy-transfer element with negligible stored magnetizing energy.

A flyback magnetic component intentionally stores substantial energy in its magnetizing inductance during one switching interval and releases it during another. It is often physically called a transformer because it has multiple windings, but its magnetic design is closer to a gapped coupled inductor.

The distinction matters for core gap, energy density, waveforms and equivalent-circuit reasoning.

## Control-flow analogy must not become an implementation claim

Software diagrams sometimes use "transformer" metaphorically for conversion stages. That terminology has no physical implication.

The current ChrisOS boot, kernel, graphics, storage and language paths are digital software systems. This chapter does not assign transformer equations to any source module.

The physical concepts become relevant when reasoning about the hardware that powers or connects the machine: VRMs, isolation supplies, Ethernet magnetics, audio interfaces and external power conversion.

## Memory, ownership, concurrency and privilege

The electromagnetic system itself has no software heap ownership, lock order or CPU privilege level.

If future ChrisOS code controls a power converter, ADC, magnetometer or transformer-coupled interface, the implementation chapter must separately document:

- MMIO or bus register ownership;
- DMA buffers;
- sampling clocks;
- interrupt synchronization;
- calibration data;
- numeric representation;
- user/kernel access;
- fault shutdown behavior.

None of those software contracts can be inferred from Faraday's law.

## Numerical modeling

A linear coupled-inductor model can be represented by an inductance matrix:

~~~text
[λ1]   [L1  M][i1]
[λ2] = [M  L2][i2]
~~~

For (n) windings:

~~~text
λ = L i
v = dλ/dt
~~~

The matrix must satisfy physical constraints associated with stored magnetic energy.

For the two-winding linear case,

~~~text
W = 1/2 L1 i1² + M i1 i2 + 1/2 L2 i2²
~~~

A passive energy model constrains the inductance matrix so stored energy cannot become arbitrarily negative.

Nonlinear core models replace constant (L) with state-dependent constitutive behavior and may require hysteresis state.

## Computational complexity

For a small fixed transformer equivalent circuit, analytic phasor evaluation is constant-time with respect to circuit size.

For a general network with (n) unknown node variables, transformer/coupled-inductor elements contribute stamps to the system matrix. Dense direct solution is approximately (O(n³)); sparse solvers can be substantially cheaper depending on topology and fill-in.

A field solver is a different computational problem. Finite-element electromagnetic analysis discretizes geometry into many degrees of freedom and cannot be equated with the lumped model.

## Failure modes and diagnostic signatures

| Failure/model error | Likely consequence |
|---|---|
| wrong dot convention | inverted feedback or unexpected phase |
| too few turns for voltage/frequency | excessive flux and saturation |
| DC bias ignored | reduced flux headroom |
| open CT secondary | dangerous secondary voltage |
| leakage inductance ignored | switching overshoot underestimated |
| interwinding capacitance ignored | common-mode EMI underestimated |
| winding (R_ac) treated as (R_dc) | copper loss underestimated |
| core loss treated as constant | thermal prediction error |
| sinusoidal 4.44 rule used for arbitrary waveform | incorrect flux estimate |
| isolation inferred from symbol only | unsafe insulation assumption |
| lumped model used beyond bandwidth | resonance/propagation errors |

## Validation evidence

A deterministic chapter-specific check should verify at least these invariants:

~~~text
1. N-turn Faraday scaling:
   e ∝ N dΦ/dt

2. ideal turns ratio:
   V1/V2 = N1/N2

3. ideal current ratio:
   I1/I2 = N2/N1

4. reflected impedance:
   Zin = (N1/N2)^2 ZL

5. sinusoidal flux:
   Vrms ≈ 4.44288 f N Φpeak

6. mutual inductance:
   M = k sqrt(L1 L2)

7. volt-second integration:
   ΔΦ = (1/N) ∫v dt
~~~

These equations validate the documented ideal models. They do not validate a physical transformer, insulation system, thermal design or ChrisOS hardware driver.

## Performance and engineering trade-offs

Transformer design is multiobjective.

Increasing turns can reduce flux density at fixed voltage/frequency, but increases conductor length and winding resistance. Larger conductor area lowers resistance but consumes window area. Tighter coupling lowers leakage inductance but may increase interwinding capacitance. Higher switching frequency can shrink required magnetic volume but raises switching, core and AC winding losses.

There is no universally optimal transformer independent of waveform, power, isolation, temperature, size, cost and EMI constraints.

## Current ChrisOS relevance

ChrisOS executes on hardware whose power and communication subsystems can contain magnetic components, but the OS generally sees the digital interfaces above them.

Examples include:

~~~text
mains / adapter
    ↓
power conversion and magnetics
    ↓
voltage regulators
    ↓
CPU / memory / devices
    ↓
ChrisOS software-visible interfaces
~~~

and potentially:

~~~text
Ethernet PHY
    ↕
isolation magnetics
    ↕
cable
~~~

The physical layer can fail while software-visible registers merely report link or power symptoms. Understanding the lower layer prevents incorrectly attributing every failure to software.

No current ChrisOS source file or symbol is cited because no reviewed implementation claim in this chapter requires one.

## Current limitations

This chapter does not provide:

- a complete Maxwell-equation field derivation;
- finite-element magnetic simulation;
- empirical Steinmetz-parameter fitting;
- transformer thermal-network design;
- creepage/clearance values for a particular safety standard;
- RF S-parameter transformer characterization;
- a ChrisOS power-electronics driver.

Those require geometry, materials, frequency range, regulatory context or source code not present in the current implementation evidence.

## Roadmap boundary

The next foundation topics use induction but add propagation and parasitic effects:

~~~text
Faraday induction
    ↓
mutual inductance / transformer
    ↓
leakage + capacitance
    ↓
distributed transmission line
    ↓
reflections / differential signaling
    ↓
noise, grounding and signal integrity
    ↓
power-distribution impedance
~~~

This sequence is conceptual. It does not imply that ChrisOS will implement an electromagnetic simulator.

## Revision provenance

Reviewed against ChrisOS `main` at `da3df29cb397932c43d32373871fb9380e688ade`.

`sources` and `symbols` are intentionally empty because the current ChrisOS source does not implement the electromagnetic models documented here. The physical definitions use SI quantities and the Maxwell-Faraday/induction relations; implementation-specific claims are deliberately absent rather than inferred from hardware analogies.
