---
id: electric-charge-field-potential
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
  - vectors-complex-numbers-systems
related:
  - voltage-current-resistance-power
  - ohm-kirchhoff-circuits
  - capacitance-inductance
  - crystal-bands-doping
  - transistor-cmos
  - logic-levels-noise-margins
---

# Electric charge, field, potential and energy

## Scope

A digital computer eventually manipulates abstract bits, but the physical machine operates through electromagnetic interactions.

Before voltage, current, resistance, capacitance or transistor switching can be used coherently, four ideas must be separated:

~~~text
charge
    property carried by matter

electric field
    local force-per-charge condition in space

electric potential
    energy-per-charge state associated with position

potential difference
    difference in potential between two points
~~~

These quantities are related, but they are not interchangeable.

A wire does not contain voltage in the same sense that a region contains charge. A battery does not inject abstract Boolean values into a chip. A logic HIGH is not a microscopic particle.

The purpose of this chapter is to establish the physical language that later chapters use to derive voltage, current, capacitance, semiconductor electrostatics, CMOS switching, signal integrity and power delivery.

![Charge, field and potential](../../assets/diagrams/electric-charge-field-potential-en.svg)

## Electrical charge

Electric charge is a physical property that determines how matter participates in electromagnetic interaction.

The SI unit of charge is the coulomb:

~~~text
Q [C]
~~~

At the microscopic level, electrons carry negative elementary charge and protons carry positive elementary charge of the same magnitude.

The elementary charge magnitude is:

~~~text
e = 1.602176634 × 10^-19 C
~~~

by the modern SI definition.

Therefore one coulomb corresponds to approximately:

~~~text
1 / e
≈ 6.241509074 × 10^18
~~~

elementary charges.

This is an enormous number because one coulomb is a macroscopic unit.

## Charge is signed

Charge has sign.

Two positive charges repel. Two negative charges repel. Opposite charges attract.

The sign is not a label added after calculating force. It enters the force relation and determines direction.

A system can contain large numbers of positive and negative charges while having nearly zero net charge.

This distinction is important in conductors and semiconductors.

A metal wire can conduct current without accumulating a macroscopically large net charge throughout its bulk.

Likewise, doped semiconductor regions can remain nearly charge-neutral while having very different mobile carrier populations.

## Conservation of charge

In ordinary electronic systems, total electric charge is conserved.

Charge can move from one location to another. Positive and negative carriers can recombine or separate under material-specific processes. But a circuit model must still account for where net charge accumulates and where it leaves.

This principle becomes the physical foundation beneath Kirchhoff's current law.

KCL is not an arbitrary bookkeeping rule. It is a circuit-scale expression of charge conservation under the assumptions of the lumped-element model.

## Discrete carriers and continuous circuit variables

At microscopic scale, charge is quantized in units related to the elementary charge.

At circuit scale, electrical engineering usually treats charge as a continuous variable:

~~~text
Q(t)
~~~

because practical nodes involve enormous numbers of carriers.

Both descriptions can be correct at their own scale.

For a node storing millions or billions of elementary charges, a continuous approximation is usually excellent.

At very small device scales or in single-electron devices, charge discreteness can become directly relevant.

The model must match the scale.

## Coulomb's law

For two idealized point charges in vacuum separated by distance r, the magnitude of electrostatic force is:

~~~text
F = (1 / (4π ε0)) × |q1 q2| / r²
~~~

where:

~~~text
F   force [N]
q1  charge [C]
q2  charge [C]
r   separation [m]
ε0  vacuum permittivity [F/m]
~~~

The direction lies along the line joining the charges.

The force is repulsive for equal signs and attractive for opposite signs.

Coulomb's law is an idealized electrostatic relation.

Real electronic structures contain distributions rather than point charges, conductors, dielectrics, semiconductor interfaces, geometry-dependent fields and time-varying electromagnetic effects.

The law remains foundational because electric field is built from the same interaction.

## Superposition

In the classical linear medium models used here, field contributions superpose.

If several charges contribute electric field at one point:

~~~text
E_total = Σ E_i
~~~

The word vector is essential.

Fields can reinforce or cancel depending on direction.

Adding only magnitudes gives the wrong answer except in special geometries.

## Electric field

Electric field is defined through force on a positive test charge:

~~~text
E = F / q
~~~

Its SI units can be written:

~~~text
N/C
~~~

or equivalently:

~~~text
V/m
~~~

Electric field is a vector field.

At each point in space it has magnitude and direction.

Conceptually:

~~~text
position
    ↓
electric field vector
    ↓
force on a charge placed there
~~~

For charge q:

~~~text
F = qE
~~~

If q is negative, force points opposite the field vector.

This is why electron drift direction and conventional current direction can differ.

## Field is not force

An electric field can exist at a point even if no test charge is present there.

Force requires both a field and a charge experiencing that field.

The distinction is analogous to describing a gravitational field separately from the weight of a particular object.

## Field lines

Field-line drawings are visualization tools.

They indicate direction tangent to the field and often use line density to suggest magnitude.

They are not physical strings and are not trajectories that electrons are required to follow.

A charged particle's actual motion depends on initial velocity, electric field, magnetic field, collisions, material band structure and boundaries.

Field lines are a map of a vector field.

## Continuous charge distributions

Real devices use charge distributed over volumes, surfaces and interfaces.

Common density forms are:

~~~text
linear charge density    λ [C/m]
surface charge density   σ [C/m²]
volume charge density    ρ [C/m³]
~~~

The field is obtained by integrating contributions over the distribution.

Later semiconductor chapters use spatial charge density to explain depletion regions and MOS electrostatics.

## Electric flux

Electric flux measures electric field crossing a surface.

For a small oriented surface element:

~~~text
dΦ_E = E · dA
~~~

The dot product selects the field component normal to the surface.

For a closed surface:

~~~text
Φ_E = ∮ E · dA
~~~

Flux is useful because Gauss's law connects a closed-surface field integral to enclosed charge.

## Gauss's law

In classical electromagnetism:

~~~text
∮ E · dA = Q_enclosed / ε0
~~~

Gauss's law becomes especially useful computationally when symmetry makes E easy to factor from the integral.

Typical idealizations include spherical distributions, infinite lines, infinite planes and simple capacitor geometries.

A law can be universally valid while being computationally convenient only in selected geometries.

## Conductors in electrostatic equilibrium

An ideal conductor in electrostatic equilibrium has important properties.

Inside the conducting bulk:

~~~text
E = 0
~~~

If a sustained internal electric field remained, free carriers would continue moving and the state would not be electrostatic equilibrium.

Excess static charge resides on surfaces in the ideal model.

The conductor is also an equipotential region.

These ideas later support reasoning about wires, shielding, capacitors, ground/reference nodes and electrostatic boundaries.

## Potential energy

A charge placed in an electric field has electric potential energy.

For two point charges:

~~~text
U = (1 / (4π ε0)) × q1 q2 / r
~~~

with the conventional zero at infinite separation.

Unlike force magnitude, the sign matters directly.

Positive U for equal-sign charges reflects work required to bring them closer from infinity.

Negative U for opposite charges reflects an attractive bound configuration under that reference choice.

## Electric potential

Electric potential is potential energy per unit charge:

~~~text
V = U / q
~~~

Its SI unit is the volt:

~~~text
1 V = 1 J/C
~~~

Potential is a scalar field.

At each point:

~~~text
position
    ↓
electric potential value
~~~

This differs from electric field, which is a vector field.

## Potential difference

Only differences in electric potential are physically relevant to most circuit behavior.

Between points A and B:

~~~text
ΔV = V_B - V_A
~~~

Potential difference tells how much potential energy changes per unit charge:

~~~text
ΔU = q ΔV
~~~

This equation is one of the most important bridges between field theory and circuit theory.

For one coulomb moving through a potential difference of one volt, the energy magnitude changes by one joule, subject to sign convention.

## Voltage is potential difference

In circuit language, voltage means electric potential difference.

A statement such as:

~~~text
node A is at 3.3 V
~~~

is incomplete without an implied or explicit reference node.

It normally means:

~~~text
V_A - V_reference = 3.3 V
~~~

This is why voltage is measured between two points.

An oscilloscope probe likewise establishes a reference relationship.

## Reference potential and ground

Electric potential has freedom in the choice of zero.

If every potential in a circuit is increased by the same constant, all potential differences remain unchanged.

Ordinary circuit behavior depends on those differences.

Choosing a node called ground often defines:

~~~text
V_ground = 0
~~~

as a convenient reference.

That name does not automatically mean the node is physically connected to Earth.

Circuit ground, chassis ground and protective Earth are different concepts and will be separated in the grounding chapter.

## Relation between field and potential

In electrostatics:

~~~text
E = -∇V
~~~

In one dimension:

~~~text
E_x = -dV/dx
~~~

The minus sign means electric field points toward decreasing electric potential.

For a uniform field along one axis:

~~~text
ΔV = -E Δx
~~~

with sign determined by the chosen direction.

This relation explains why a spatial voltage difference corresponds to an electric field.

It is also the bridge to field-effect devices: gate voltage changes electrostatic potential, which changes electric field and carrier distribution.

## Gradient

The gradient ∇V is a vector formed from the spatial rate of change of scalar potential.

In Cartesian coordinates:

~~~text
∇V =
(∂V/∂x, ∂V/∂y, ∂V/∂z)
~~~

A steep potential change over a short distance corresponds to a large electric field magnitude.

This matters in semiconductor devices because nanometer-scale structures can create very large electric fields from modest terminal voltages.

## Potential as a scalar computational model

Electric field is a vector. Potential is a scalar.

In many electrostatic problems it is easier to compute potential and derive field from its gradient.

This idea scales into semiconductor electrostatics, where potential and charge density are coupled through Poisson's equation.

## Poisson's equation

For electrostatic potential in a medium with permittivity ε:

~~~text
∇²V = -ρ / ε
~~~

where ρ is volume charge density.

If the region contains no net volume charge:

~~~text
ρ = 0
~~~

then potential satisfies Laplace's equation:

~~~text
∇²V = 0
~~~

These equations become central in device electrostatics.

A full semiconductor solution also couples potential to carrier statistics and material boundaries.

This chapter establishes the meaning of the quantities before those coupled models appear.

## Work and path independence in electrostatics

For an electrostatic field, work between two points depends only on endpoints.

Equivalently:

~~~text
∮ E · dl = 0
~~~

around a closed path in the electrostatic case.

This permits a consistent scalar electric potential.

Time-varying magnetic fields change the picture.

Faraday's law introduces non-conservative electric fields.

That distinction is deferred to the induction chapter.

## The electrostatic approximation

Computer electronics are dynamic.

Signals switch, clocks oscillate and currents change.

The electrostatic model is introduced first because it isolates field and potential relationships before time-dependent electromagnetic propagation is added.

Because many local relationships can first be understood by assuming fields change slowly enough that propagation and radiation can be ignored.

This is a quasi-static approximation.

It becomes the basis of lumped circuit theory.

At sufficiently fast edge rates or long interconnects, propagation delay is no longer negligible and transmission-line theory becomes necessary.

## Lumped nodes

Circuit theory compresses spatial electromagnetic behavior into node variables.

Instead of solving V(x,y,z) everywhere, a lumped model assigns approximately uniform potentials:

~~~text
node A -> V_A
node B -> V_B
node C -> V_C
~~~

Components connect nodes and impose current-voltage relations.

This abstraction is powerful because it discards field geometry unnecessary to the circuit problem.

Its validity is an assumption that later high-speed chapters revisit.

## Energy from moving charge through voltage

If charge Q moves through potential difference ΔV:

~~~text
ΔU = Q ΔV
~~~

If charge moves continuously, define current:

~~~text
I = dQ/dt
~~~

Differentiating energy with respect to time gives:

~~~text
P = dU/dt
  = V dQ/dt
  = VI
~~~

The next chapter develops current, resistance and power carefully.

This derivation shows why P = VI is rooted in energy-per-charge and charge-per-time.

## Electronvolt

The electronvolt is a convenient energy unit in semiconductor physics.

One electronvolt is the energy magnitude acquired by one elementary charge moving through one volt:

~~~text
1 eV
=
e × 1 V
=
1.602176634 × 10^-19 J
~~~

The electronvolt is a unit of energy, not voltage.

That distinction is essential when reading band-gap values.

## Potential in semiconductor physics

Later chapters use electrostatic potential to explain:

- band bending;
- depletion;
- built-in junction potential;
- accumulation;
- inversion;
- MOS threshold behavior.

These are consequences of field, potential and charge distribution in material.

Without this layer, the statement that gate voltage controls a transistor channel remains incomplete.

## Potential in CMOS logic

A CMOS gate maps ranges of electrical potential into logical states.

Conceptually:

~~~text
electrical potential at input
    ↓
electric field in transistor structure
    ↓
channel conductivity changes
    ↓
output node charges or discharges
    ↓
output potential reaches a valid range
    ↓
next gate interprets LOW or HIGH
~~~

The Boolean value is therefore an abstraction over physical potential ranges.

## Logic level is not one exact voltage

A logic family defines ranges rather than one exact value.

Conceptually:

~~~text
valid LOW region
undefined / transition region
valid HIGH region
~~~

Exact thresholds depend on technology.

Noise margin describes how much disturbance can be tolerated between guaranteed output levels and required input thresholds.

That topic is developed after CMOS switching.

## Potential and capacitance

Separated conductors can store opposite charge.

The proportionality:

~~~text
Q = CV
~~~

defines capacitance in a linear capacitor model.

Stored electric-field energy is:

~~~text
U = 1/2 C V²
~~~

This directly connects electrostatics to switching energy in digital circuits.

A CMOS node has capacitance even when no explicit schematic capacitor was placed there.

## Finite digital-edge transition time

Changing a node from LOW to HIGH requires charge movement.

If a node has capacitance, changing potential changes stored charge.

Finite available current therefore creates finite transition time.

The causal chain is:

~~~text
charge
    ↓
capacitance
    ↓
node voltage
    ↓
finite charging time
    ↓
propagation delay
    ↓
timing constraint / maximum frequency
~~~

This is one reason physical electrical theory matters to architecture.

## Differential signaling

A single-ended signal is interpreted relative to a reference.

A differential signal is primarily interpreted through:

~~~text
V_diff = V_plus - V_minus
~~~

Modern high-speed interfaces such as PCI Express use differential signaling.

The detailed advantages, common-mode behavior, characteristic impedance and termination belong to the transmission-line chapter.

## Electrostatic shielding

A conductor can redistribute surface charge to strongly constrain electrostatic field inside an ideal closed conducting enclosure.

Practical shielding depends on frequency, apertures, geometry and bonding, but the electrostatic principle begins here.

Computers use related ideas in chassis, cables, connector shells and PCB reference structures.

## Electrostatic discharge

Charge separation can create large potential difference.

If the field becomes sufficient to establish a rapid discharge path, electrostatic discharge can occur.

ESD can damage semiconductor structures because small geometries can experience extreme local field/current stress.

Software cannot repair physical oxide breakdown.

The ISA assumes the physical hardware continues satisfying its digital contract.

## Dimensional analysis

Units are a first-line correctness test.

Examples:

~~~text
E = F/q
[N/C]

V = U/q
[J/C]

ΔU = qΔV
[C × J/C = J]

P = VI
[J/C × C/s = J/s = W]
~~~

If dimensions do not reduce correctly, an equation or substitution is likely wrong.

This method remains useful throughout electronics and systems modeling.

## Sign conventions

Engineering calculations choose reference directions.

For example:

~~~text
v_ab = V_a - V_b
~~~

A current arrow can also be chosen in either direction.

A negative result means the physical direction/polarity is opposite the chosen reference.

It does not mean the equation failed.

Clear reference conventions prevent many later circuit mistakes.

## Scalar and vector quantities

Scalar examples:

~~~text
charge Q
potential V
energy U
~~~

Vector examples:

~~~text
electric field E
force F
~~~

Later chapters add magnetic field and current density.

Software developers accustomed to scalar register values must not assume every physical quantity is scalar.

## Boundary between physical and circuit models

A circuit node voltage is already an abstraction.

The underlying conductor contains a spatial electromagnetic state.

Treating the whole node as one potential assumes propagation across it is negligible for the problem.

At low frequency or small geometry, this can be excellent.

At fast edges and long traces, the same conductor must be modeled as a distributed transmission structure.

## Boundary between circuit and logic models

A voltage waveform remains analog.

Digital logic interprets it through thresholds and timing windows:

~~~text
continuous waveform
    ↓
receiver sampling
    ↓
electrical threshold comparison
    ↓
logical state
~~~

If the waveform is in an invalid range or changes near a sampling boundary, the digital abstraction can fail.

Metastability and timing chapters develop that problem.

## Boundary between logic and architecture

Architecture normally stops talking about volts.

It talks about bits, registers, instructions, memory and interrupts.

That is possible because lower layers maintain logical states within electrical and timing limits.

The ISA is therefore an abstraction contract built on physical reliability.

## Connection to ChrisOS

ChrisOS operates far above field equations, but its environment depends on them.

A representative chain is:

~~~text
charge redistribution in transistor structures
    ↓
CMOS logic transition
    ↓
register bit changes
    ↓
x86-64 instruction retires
    ↓
MMIO register write becomes visible
    ↓
device changes state
    ↓
ChrisOS observes an interrupt or memory result
~~~

ChrisOS does not evaluate Coulomb's law while handling an interrupt.

But the hardware contract it consumes ultimately emerges from the phenomena defined here.

## Connection to ChrisCPU

ChrisCPU represents architectural state with software variables.

A fabricated x86-64 processor realizes equivalent architectural state through physical circuits.

Therefore:

~~~text
ChrisCPU register field
    software representation of architectural state

physical CPU register
    electrical realization of architectural state
~~~

The emulator need not model charge, field or transistor delay unless the project intentionally moves toward circuit-level simulation.

Architectural equivalence is a higher abstraction.

## Deferred topics

Separate chapters derive:

- current in conductors;
- resistance and resistivity;
- Ohm's law;
- power;
- Kirchhoff circuit analysis;
- capacitor dynamics;
- inductance;
- AC impedance;
- electromagnetic induction;
- transmission lines;
- semiconductor band structure;
- MOS electrostatics;
- transistor switching.

Keeping them separate avoids recreating hidden abstraction jumps inside one oversized electronics overview.

## Reproducible calculations

The checker associated with this chapter validates representative arithmetic:

- elementary-charge count per coulomb;
- Coulomb-force magnitude;
- energy change qΔV;
- electronvolt conversion;
- uniform-field potential difference;
- field/potential unit relationships.

It does not simulate semiconductor geometry.

Its purpose is to keep numerical examples and sign conventions from drifting.

## Validation boundary

This chapter states classical electrostatic relationships used as prerequisites for circuit and semiconductor theory.

Primary external references include MIT OpenCourseWare 8.02 Electricity and Magnetism, NIST SI material for electrical units and the BIPM SI Brochure.

The next chapter converts charge motion and energy-per-charge into voltage, current, resistance, energy and power in circuit form.

## Review triggers

Review when:

- foundation ordering changes;
- numerical examples change;
- later circuit/device chapters require an electrostatic concept not defined here;
- the SI reference/constants used by examples are revised;
- the project adds circuit-level or device-level simulation requiring a more detailed electromagnetic model.
