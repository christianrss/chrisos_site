---
id: mos-capacitor
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - crystal-bands-doping
  - pn-junction
  - electric-charge-field-potential
  - capacitance-inductance
related:
  - transistor-cmos
  - cmos-switching-power
---

# MOS capacitor electrostatics

<div class="abstract">
The metal-oxide-semiconductor capacitor is the electrostatic core of MOS technology. It converts gate voltage into a controlled redistribution of charge at a semiconductor surface without requiring direct DC conduction through the gate dielectric. The same field-control mechanism later becomes the channel-control mechanism of a MOSFET. This chapter derives the MOS structure from electrostatics, oxide capacitance, work-function difference, flat-band voltage, surface potential, accumulation, depletion and inversion. It then develops depletion charge, threshold concepts, low- and high-frequency C-V behavior, interface charge, oxide field, scaling, equivalent oxide thickness and energy storage. The ChrisOS boundary is explicit: the current source tree contains no MOS device solver or transistor-level electrical model; the chapter is a physical prerequisite for understanding the hardware on which the software executes.
</div>

## Prerequisites and scope

The required foundations are:

- electric field and electrostatic potential;
- capacitance and stored electric-field energy;
- crystal bands, Fermi level and doping;
- p-n junction depletion electrostatics;
- logarithms and one-dimensional differential equations.

The MOS capacitor is usually introduced as three stacked regions:

~~~text
gate conductor
====================
oxide / dielectric
--------------------
semiconductor
~~~~~~~~~~~~~~~~~~~~
bulk contact
~~~

The gate is separated from the semiconductor by an insulating dielectric. Ideally, no steady gate current is required to establish an electric field. The gate voltage changes the electrostatic potential near the semiconductor surface, and that potential changes carrier concentration.

This chapter uses an ideal one-dimensional planar structure first, then adds non-ideal effects. It does not claim that modern transistors are literally described by one classical oxide and one uniform substrate.

## Geometry and coordinate system

Let x be normal to the surface.

A conventional coordinate choice is:

~~~text
x < 0        gate
0..t_ox      oxide
x > t_ox     semiconductor
~~~

For compact equations it is often convenient to place the semiconductor surface at x = 0 and treat the oxide as a separate series element. The exact coordinate origin is arbitrary if signs are defined consistently.

Important quantities are:

| Symbol | Meaning |
|---|---|
| t_ox | dielectric thickness |
| ε_ox | dielectric permittivity |
| ε_s | semiconductor permittivity |
| C_ox | oxide capacitance per area |
| V_G | gate voltage relative to body/bulk |
| ψ_s | semiconductor surface potential relative to bulk |
| Q_s | net semiconductor charge per area |
| Q_g | gate charge per area |
| V_FB | flat-band voltage |
| φ_F | bulk Fermi potential magnitude under the adopted convention |

The signs of ψ_s and Q_s depend on substrate type and convention. This chapter states the p-type-substrate case explicitly when discussing accumulation and inversion.

## Oxide capacitance

For a uniform ideal dielectric, capacitance per unit area is:

~~~text
C_ox = ε_ox / t_ox
~~~

Total capacitance for gate area A is:

~~~text
C_ox,total = A ε_ox / t_ox
~~~

The field in an ideal oxide with uniform normal displacement is related to charge by:

~~~text
D = ε_ox E_ox

Q_g = D
~~~

with sign determined by the chosen normal direction.

A thinner oxide or a higher-permittivity dielectric increases capacitance per unit area.

That increases electrostatic gate control for a given gate-voltage change, but it also changes field stress, tunneling probability, fabrication difficulty and parasitic behavior.

## Charge neutrality across the ideal stack

Ignoring fixed oxide charge and interface charge for the moment, the gate and semiconductor charges are equal and opposite:

~~~text
Q_g + Q_s = 0
~~~

This is a capacitor statement.

The semiconductor charge Q_s is not necessarily a thin sheet. In depletion, it extends through a finite spatial region of ionized dopants.

In inversion, the total semiconductor charge can contain both depletion charge and a mobile inversion-layer contribution.

Therefore the MOS capacitor is not merely a parallel-plate capacitor with a fixed second plate.

## Gate voltage decomposition

A useful electrostatic relation is:

~~~text
V_G
=
V_FB
+
ψ_s
-
Q_s / C_ox
~~~

for a common sign convention in which Q_s is semiconductor charge per unit area.

This equation separates gate voltage into:

- flat-band offset;
- surface-potential change inside the semiconductor;
- voltage drop across the oxide.

Equivalent sign forms appear in textbooks because Q_s and ψ_s conventions differ. The physical content is unchanged: gate bias is divided between dielectric field and semiconductor electrostatics.

## Work-function difference

Even when the externally applied gate voltage is zero, gate and semiconductor need not have identical electrochemical work functions.

Define:

~~~text
Φ_MS = Φ_M - Φ_S
~~~

where Φ_M and Φ_S are gate and semiconductor work functions expressed in volts when divided by elementary charge as appropriate.

For an ideal oxide with no fixed charge, the gate voltage required to make semiconductor bands flat is related to this work-function difference.

With non-ideal oxide/interface charge Q_ox, a common first-order form is:

~~~text
V_FB = Φ_MS - Q_ox / C_ox
~~~

The exact charge term can represent several physical populations and may require a more detailed model.

## Flat-band condition

Flat band means the semiconductor band edges are not bent by an electric field near the surface in the simplified one-dimensional model.

At flat band:

~~~text
ψ_s = 0
~~~

and the semiconductor space-charge region associated with MOS band bending is absent.

Flat band does not mean:

- no microscopic carrier motion;
- no gate-semiconductor work-function difference;
- no atomic-scale fields;
- zero capacitance.

It means the macroscopic semiconductor bands are flat under the adopted model.

## P-type substrate reference case

Consider a uniformly doped p-type semiconductor with acceptor concentration N_A.

Far from the interface, holes are majority carriers.

Changing gate voltage changes surface carrier populations.

Three canonical regimes are:

~~~text
negative gate bias
    -> accumulation

small/moderate positive gate bias
    -> depletion

larger positive gate bias
    -> inversion
~~~

These labels assume the p-type-substrate convention. An n-type substrate reverses the carrier roles and bias polarities.

## Accumulation

A sufficiently negative gate voltage relative to a p-type body attracts holes toward the oxide-semiconductor interface.

The surface hole concentration becomes larger than the bulk hole concentration.

Conceptually:

~~~text
negative gate charge
       ||
oxide  ||
       ||
+++++++    holes accumulate near surface
p-type semiconductor
~~~

The induced semiconductor charge is mobile majority-carrier charge concentrated near the surface.

In the quasi-static ideal limit, the MOS capacitance in strong accumulation approaches C_ox because the semiconductor behaves as an effective conducting plate very near the interface.

## Depletion

A positive gate bias repels holes from the surface.

The depleted region exposes ionized acceptor charge that is fixed in the crystal.

For a one-dimensional depletion approximation:

~~~text
ρ(x) ≈ -q N_A
~~~

within depletion width W_d, while the neutral bulk outside the depletion region remains approximately charge neutral.

Poisson's equation is:

~~~text
d²ψ/dx² = -ρ/ε_s
~~~

so in depletion:

~~~text
d²ψ/dx² = q N_A / ε_s
~~~

under the stated sign convention.

## Depletion width

Integrating Poisson's equation with zero electric field at the depletion edge yields:

~~~text
W_d
=
sqrt(
  2 ε_s ψ_s / (q N_A)
)
~~~

for positive surface potential in the p-type-substrate depletion approximation.

The magnitude of depletion charge per unit area is:

~~~text
|Q_d|
=
q N_A W_d
=
sqrt(
  2 q ε_s N_A ψ_s
)
~~~

The semiconductor depletion capacitance per unit area is approximately:

~~~text
C_dep
=
ε_s / W_d
~~~

As depletion widens, C_dep decreases.

## Series capacitance in depletion

The small-signal gate sees oxide capacitance in series with depletion capacitance:

~~~text
1/C_MOS
=
1/C_ox
+
1/C_dep
~~~

or:

~~~text
C_MOS
=
(C_ox C_dep) / (C_ox + C_dep)
~~~

Therefore the measured capacitance falls below C_ox in depletion.

This is a direct electrical signature of the fact that the effective separation of charge extends into the semiconductor.

## Surface potential and carrier concentration

In nondegenerate equilibrium statistics, carrier concentrations vary approximately exponentially with electrostatic potential.

For a p-type substrate, increasing positive surface potential reduces the local hole concentration and increases electron concentration.

The exact formulas depend on the potential and Fermi-level sign convention, but the physical progression is:

~~~text
positive surface potential
        ↓
bands bend
        ↓
holes depleted
        ↓
electron concentration rises
        ↓
surface can become n-type relative to p-type bulk
~~~

That surface carrier-type reversal is inversion.

## Strong inversion

Strong inversion is conventionally associated with a surface potential magnitude near twice the bulk Fermi potential in the long-channel classical model.

Define the magnitude:

~~~text
φ_F
=
V_T ln(N_A / n_i)
~~~

for a nondegenerate p-type substrate, where:

~~~text
V_T = kT/q
~~~

Then the classical strong-inversion condition is often approximated by:

~~~text
ψ_s ≈ 2 φ_F
~~~

At this point the surface electron concentration is comparable, under the idealized model, to the bulk majority-hole concentration before inversion.

This is a model-based threshold convention, not an abrupt physical phase transition.

## Threshold-voltage construction

A long-channel idealized NMOS threshold-voltage expression is:

~~~text
V_TN
=
V_FB
+
2 φ_F
+
|Q_d,max| / C_ox
~~~

where:

~~~text
|Q_d,max|
=
sqrt(
  4 q ε_s N_A φ_F
)
~~~

under zero body-source bias and the classical strong-inversion criterion.

Threshold voltage is therefore influenced by:

- gate-semiconductor work-function difference;
- oxide capacitance;
- substrate doping;
- temperature;
- oxide/interface charge;
- body bias.

Modern devices require more complete models, but this equation exposes the electrostatic origin of threshold.

## Inversion charge beyond threshold

Once strong inversion forms, additional positive gate voltage does not simply keep widening depletion without limit.

Much of the incremental gate charge is balanced by mobile inversion charge near the surface.

A simplified strong-inversion charge-control relation is:

~~~text
Q_inv
≈
-C_ox (V_G - V_TN)
~~~

for an appropriate local channel voltage reference and neglecting second-order effects.

This relation is one bridge from the two-terminal MOS capacitor to MOSFET channel charge.

A MOSFET adds source and drain contacts so that the inversion layer can conduct laterally.

## Band diagrams

A MOS band diagram plots electron energy versus position through gate, dielectric and semiconductor.

Band bending in the semiconductor reflects electrostatic potential variation.

For electrons, increasing electrostatic potential shifts electronic potential energy with the opposite sign because electron charge is negative.

The diagram therefore must not be interpreted as literal mechanical hills.

Three distinct views are useful:

| View | Primary purpose |
|---|---|
| cross-section | physical geometry and material stack |
| charge diagram | gate, depletion and inversion charge |
| band-edge diagram | carrier energetics and surface potential |

Using all three avoids confusing geometry, charge and energy.

## Electric field in the oxide

For an ideal oxide:

~~~text
E_ox
≈
V_ox / t_ox
~~~

and:

~~~text
V_ox = -Q_s / C_ox
~~~

under the adopted sign convention.

High field can cause:

- tunneling current;
- charge trapping;
- time-dependent dielectric degradation;
- eventual breakdown.

Thus scaling t_ox downward improves electrostatic coupling but increases field and leakage challenges for a given voltage.

## Equivalent oxide thickness

High-permittivity dielectrics allow a physically thicker dielectric to provide capacitance similar to a thinner silicon-dioxide layer.

Equivalent oxide thickness, EOT, expresses the capacitance in terms of an equivalent SiO2 thickness:

~~~text
EOT
=
t_high-k
·
(ε_SiO2 / ε_high-k)
~~~

in the simplest single-layer idealization.

A smaller EOT means stronger capacitance per area.

The real gate stack can include interfacial layers, quantum effects and series capacitances, so this expression is a conceptual first approximation.

## Gate leakage and tunneling

An ideal capacitor passes no DC current through its dielectric.

A sufficiently thin real dielectric does not satisfy that idealization perfectly.

Quantum tunneling can create gate leakage even before catastrophic breakdown.

Therefore:

~~~text
ideal MOS electrostatics:
    gate current = 0

real scaled gate stack:
    gate current may be finite
~~~

This distinction becomes important for static power and reliability.

## Interface traps

The oxide-semiconductor interface can contain electronic states inside the semiconductor band gap.

Interface traps can exchange charge with the semiconductor depending on:

- surface potential;
- temperature;
- signal frequency;
- capture/emission time constants.

They can modify:

- flat-band voltage;
- threshold voltage;
- subthreshold behavior;
- measured capacitance;
- device noise.

A measured C-V curve can therefore differ from the ideal curve even when oxide thickness is known precisely.

## Fixed oxide charge and mobile ionic charge

Real dielectrics can contain charge not described by the ideal gate-semiconductor capacitor model.

A first-order shift appears through:

~~~text
ΔV = -Q_ox / C_ox
~~~

for an appropriately defined effective oxide charge.

The sign and spatial location matter.

Device processing therefore controls not only geometry but also charge defects and contamination.

## Quasi-static capacitance-voltage behavior

At sufficiently low measurement frequency, minority carriers may respond quickly enough for inversion charge to track the AC excitation.

For a p-type substrate:

~~~text
negative V_G:
    accumulation
    C ≈ C_ox

toward positive V_G:
    depletion
    C decreases

strong inversion, quasi-static:
    inversion charge responds
    C can rise toward C_ox
~~~

The exact curve depends on device area, temperature, doping and non-ideal charge.

## High-frequency C-V behavior

At high frequency, thermally generated minority carriers may not respond to the small AC signal quickly enough.

Then strong-inversion small-signal capacitance can remain near the minimum series value:

~~~text
C_min
≈
(C_ox C_dep,max)
/
(C_ox + C_dep,max)
~~~

instead of returning to C_ox.

This is why "the MOS capacitance in inversion" is not one universal number without specifying measurement conditions.

## Deep depletion

If gate voltage is swept quickly enough that minority carriers cannot establish equilibrium inversion, the depletion region can temporarily widen beyond its equilibrium maximum.

This is deep depletion.

It is a nonequilibrium measurement condition, not the ordinary long-term strong-inversion state.

Generation of minority carriers eventually changes the condition unless the measurement protocol maintains the nonequilibrium state.

## Small-signal versus large-signal behavior

Large-signal electrostatics determines the operating point.

Small-signal capacitance is the derivative of charge with respect to voltage around that operating point:

~~~text
C = dQ/dV
~~~

A nonlinear device can therefore have a voltage-dependent incremental capacitance.

The statement "capacitance equals εA/t" applies directly to the ideal oxide geometry, not necessarily to the total terminal capacitance of the semiconductor system at every bias.

## Stored energy

For a linear ideal capacitor:

~~~text
E = 1/2 C V²
~~~

For a nonlinear MOS capacitor, stored incremental energy is more generally related to the integral of charge with voltage:

~~~text
E = ∫ V dQ
~~~

or equivalently under suitable parametrization:

~~~text
E = ∫ Q dV
~~~

with limits and sign conventions defined for the selected terminal energy.

The simple 1/2 C V² relation remains valuable for digital dynamic-energy estimates when capacitance is treated as approximately constant over the voltage swing.

## Electrostatic scaling

Making device dimensions smaller changes multiple quantities simultaneously.

Reducing dielectric thickness tends to:

- increase C_ox;
- strengthen gate control;
- increase oxide field for a fixed voltage;
- increase tunneling sensitivity.

Increasing substrate doping can:

- reduce depletion width;
- alter threshold voltage;
- increase junction capacitance;
- change mobility and variability.

Reducing supply voltage lowers field and dynamic energy but also reduces signal headroom.

Scaling is therefore a coupled optimization problem.

## Short-channel boundary

The classical MOS capacitor is one-dimensional.

A short-channel MOSFET has lateral electric fields from source and drain in addition to vertical gate electrostatics.

Effects such as:

- drain-induced barrier lowering;
- velocity saturation;
- short-channel threshold shift;
- source/drain depletion interaction;

are not captured by the simple MOS capacitor alone.

The MOS capacitor remains useful because it isolates the vertical electrostatic mechanism.

## Temperature dependence

Temperature affects:

- thermal voltage kT/q;
- intrinsic carrier concentration;
- carrier mobility;
- generation/recombination rates;
- leakage;
- threshold behavior.

The classical φ_F expression changes with temperature through both V_T and n_i.

Thus a threshold voltage derived at one temperature cannot automatically be treated as constant across all operating conditions.

## Variability

Real devices vary because of:

- dielectric-thickness variation;
- work-function variation;
- dopant statistics;
- interface-trap density;
- line-edge roughness;
- local stress;
- process gradients.

A digital logic family is designed with margins so that useful Boolean behavior survives within a characterized distribution of device parameters.

## Failure mechanisms and reliability

MOS gate stacks can fail or degrade through mechanisms including:

- excessive electric field;
- dielectric breakdown;
- charge trapping;
- hot-carrier-related damage in transistor operation;
- bias-temperature instability in device contexts;
- contamination-induced leakage.

The detailed reliability model depends on dielectric material, geometry, electric field, temperature and time.

This chapter does not assign lifetime numbers to any physical processor used with ChrisOS.

## Security boundary

MOS electrostatics itself has no software privilege level.

Physical effects can participate in security phenomena such as:

- voltage glitch fault injection;
- data-dependent power leakage;
- electromagnetic side channels;
- rowhammer-like disturbance mechanisms at higher architectural levels.

Those require separate threat and measurement models.

Understanding device charge explains why physical side channels exist, but it does not prove that a specific ChrisOS system is vulnerable to a particular attack.

## ChrisOS architectural boundary

Current ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade contains no source-level MOSFET, MOS-capacitor or transistor electrical solver found by repository search.

Therefore this chapter intentionally declares:

~~~text
sources: []
symbols: []
~~~

No implementation claim is made.

The boundary is:

~~~text
MOS electrostatics
      ↓
transistor behavior in physical hardware
      ↓
logic gates and storage cells
      ↓
processor/device microarchitecture
      ↓
ISA and device contracts
      ↓
ChrisOS / ChrisVM software
~~~

ChrisOS executes on top of the abstraction produced by the lower layers.

## Initialization

A physical MOS capacitor has no operating-system initialization sequence.

Bias establishes its electrostatic state continuously according to charge, field and material properties.

The current ChrisOS source has no function that initializes a gate oxide, depletion layer or inversion charge.

Therefore no kernel initialization path is assigned here.

## State and data structures

The physical state includes continuous quantities such as:

~~~text
ψ(x)
E(x)
ρ(x)
n(x)
p(x)
Q_g
Q_d
Q_inv
~~~

These are field/carrier variables, not ChrisOS C structures.

A semiconductor device simulator would discretize some of these quantities into arrays or mesh state.

Current ChrisOS does not do that in the reviewed tree.

## Algorithms and complexity

Closed-form idealized equations such as C_ox or W_d are constant-time arithmetic evaluations.

A numerical semiconductor solver can require iterative solutions of coupled Poisson and carrier-transport equations over a spatial mesh.

Complexity then depends on:

- mesh size;
- dimensionality;
- nonlinear iteration;
- matrix sparsity;
- solver/preconditioner.

No such solver exists in current ChrisOS source, so no algorithm name or complexity is attributed to it.

## Memory ownership and ABI

The physical MOS capacitor has no kernel heap owner and no software ABI.

If a future device simulator were added, mesh state and material parameters would need explicit ownership.

No present ChrisOS ABI exposes:

- gate charge;
- surface potential;
- depletion width;
- oxide field;
- interface-trap density.

Those quantities belong below the current software abstraction boundary.

## Concurrency

Carrier dynamics happen physically in parallel throughout the material.

That is not equivalent to software threading or kernel synchronization.

No ChrisOS lock ordering applies to MOS electrostatics.

Future simulation code, if introduced, would require its own concurrency and determinism contract.

## Validation evidence for this chapter

The deterministic checker associated with this chapter validates illustrative idealized relationships:

~~~text
oxide capacitance:
    C_ox = ε_ox / t_ox

depletion width:
    W_d = sqrt(2 ε_s ψ_s / (q N_A))

depletion charge:
    |Q_d| = q N_A W_d

depletion capacitance:
    C_dep = ε_s / W_d

series MOS capacitance:
    C_MOS = C_ox C_dep / (C_ox + C_dep)

Fermi-potential magnitude:
    φ_F = V_T ln(N_A/n_i)

classical threshold:
    V_TN = V_FB + 2φ_F + |Q_d,max|/C_ox

self-consistent strong inversion:
    ψ_s ≈ 2φ_F

equivalent oxide thickness:
    EOT = t_high-k ε_SiO2/ε_high-k

linear-capacitor energy:
    E = 1/2 C V²
~~~

The checker uses declared illustrative physical constants.

It does not validate a fabricated MOS device.

## Current limitations

This chapter intentionally does not provide:

- a foundry process deck;
- a compact BSIM transistor model;
- quantum confinement calculations;
- Schrödinger-Poisson self-consistency;
- short-channel transistor simulation;
- measured C-V data;
- dielectric reliability lifetime prediction;
- transistor-level ChrisOS hardware measurements.

Those belong to device/process modeling and hardware characterization.

## Roadmap boundary

The physical progression is:

~~~text
doping and band structure
        ↓
p-n junction electrostatics
        ↓
MOS surface electrostatics
        ↓
accumulation / depletion / inversion
        ↓
inversion-layer charge
        ↓
MOSFET channel control
        ↓
CMOS logic
        ↓
switching delay and power
~~~

The existing transistor-cmos chapter uses this electrostatic foundation.

The following cmos-switching-power chapter develops the energy, delay and activity consequences of charging real CMOS nodes.

## Revision provenance

The repository boundary was reviewed against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Repository searches for MOSFET, MOS capacitor and capacitance returned no physical-device implementation at that revision, so sources and symbols remain empty rather than inventing a software mapping.

Physical theory was cross-checked against MIT 6.012 Microelectronic Devices and Circuits lecture material covering MOS structure, accumulation, depletion and inversion. SI quantities and units follow the BIPM SI Brochure, 9th edition version 4.01 published in June 2026.
