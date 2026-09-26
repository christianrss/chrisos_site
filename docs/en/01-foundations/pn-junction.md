---
id: pn-junction
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - crystal-bands-doping
related:
  - transistor-cmos
---

# P-N junctions and semiconductor interfaces

<div class="abstract">
The p-n junction is the first semiconductor structure in which spatially separated doping produces a self-consistent electric field. It introduces diffusion, depletion, built-in potential, bias, reverse leakage and breakdown. These mechanisms are needed to understand diodes, parasitic junctions inside CMOS, electrostatic isolation and the physical constraints surrounding MOS transistor operation.
</div>

## Joining p-type and n-type material

Consider p-type and n-type regions brought into contact. Before contact, each bulk region is approximately charge neutral, but their mobile-carrier concentrations differ. The n side contains a high concentration of electrons; the p side contains a high concentration of holes.

Immediately after forming the junction, concentration gradients drive diffusion. Electrons statistically move from the n side toward the p side, while holes move from the p side toward the n side. Near the boundary they recombine with opposite carriers.

Recombination removes mobile carriers from the immediate junction region but leaves behind ionized dopant atoms that are fixed in the crystal lattice. Donors on the n side become uncovered positive fixed charge; acceptors on the p side become uncovered negative fixed charge.

## The depletion region

The region near the junction depleted of mobile majority carriers is called the depletion region. It is not literally empty. It contains crystal atoms and ionized dopants, but far fewer mobile majority carriers than the neutral bulk.

The separated fixed charges create an electric field directed from the positive donor charge toward the negative acceptor charge. That field produces drift forces on carriers which oppose the original diffusion.

A stable equilibrium emerges when diffusion caused by concentration gradients is balanced by drift caused by the built-in electric field. The junction therefore creates a barrier without requiring an external battery.

    p bulk       depletion region       n bulk
    holes      - - - | + + +       electrons
                 ← electric field

The exact sign convention of potential diagrams must be handled carefully; the core physical fact is that fixed space charge creates an electric field that resists further majority-carrier diffusion.

## Built-in potential

The electrostatic potential difference established across the depletion region is the built-in potential. Its magnitude depends on doping concentrations, temperature and intrinsic carrier concentration.

A commonly used ideal relation has the form:

Vbi = (kT/q) ln(NA ND / ni²)

where k is Boltzmann's constant, T absolute temperature, q elementary charge magnitude, NA acceptor concentration, ND donor concentration and ni intrinsic carrier concentration.

The equation is important less as a number to memorize than as a relationship: stronger doping generally changes the equilibrium barrier logarithmically, while temperature changes both the thermal voltage kT/q and intrinsic carrier concentration.

## Equilibrium current is not zero motion

At thermal equilibrium, the net terminal current is zero, but microscopic carrier motion has not stopped. Diffusion and drift currents balance statistically.

This distinction is useful throughout computer engineering. “Stable” rarely means “nothing moves.” A memory cell, clocked circuit or voltage rail can be macroscopically stable while microscopic carriers, leakage currents and thermal fluctuations remain active.

## Forward bias

Forward bias reduces the effective barrier to majority-carrier injection. For a conventional p-n diode, making the p side more positive relative to the n side lowers the barrier.

More majority carriers cross the junction. Electrons injected into the p side and holes injected into the n side become minority carriers there and eventually recombine. Current rises rapidly with applied forward voltage.

The ideal diode equation is commonly written:

I = Is (e^(V/(nVT)) − 1)

where Is is saturation current, VT is thermal voltage and n is an ideality factor. Real devices deviate because of series resistance, recombination, high-level injection, temperature effects and geometry.

The important systems lesson is that a diode does not have a universal fixed “turn-on voltage.” Statements such as “a silicon diode turns on at 0.7 V” are approximations describing a region of a nonlinear current-voltage curve under particular current and temperature conditions.

## Reverse bias

Reverse bias increases the junction barrier and widens the depletion region. Majority-carrier conduction becomes very small, but minority-carrier generation produces a finite reverse current.

At sufficiently large reverse electric field, breakdown mechanisms can produce a large current. Zener tunneling dominates in some heavily doped junctions; avalanche multiplication dominates in other regimes. Breakdown itself is not automatically destructive if current and power are controlled, though ordinary logic junctions are usually operated well below destructive limits.

## Junction capacitance

A depletion region separates fixed charges and therefore behaves partly like a capacitor. Changing reverse bias changes depletion width and charge distribution, producing voltage-dependent junction capacitance.

At higher frequencies and in fast switching, capacitances are not secondary details. They determine delay, dynamic energy and coupling. Transistor source-body and drain-body junctions contribute parasitic capacitances that must be charged or discharged during operation.

This provides another bridge between device physics and digital timing: propagation delay arises partly because real nodes store electrical energy.

## Minority-carrier storage and recovery

When a junction has been strongly forward biased, excess minority carriers can accumulate. Returning the junction to reverse bias may require removing this stored charge before the device fully blocks current. This produces reverse-recovery behavior in many diode structures.

Modern CMOS logic avoids using ordinary p-n junctions as its primary switching mechanism because field-effect control is more suitable for dense low-static-power logic. Junctions remain present, however, at the boundaries between doped regions and semiconductor bodies.

## Junctions inside CMOS

An NMOS fabricated in a p-type body has n-type source and drain regions. Each forms a p-n junction with the body. Under normal logic operation these body junctions are kept reverse biased. Similar complementary relationships appear around PMOS devices in n-type wells.

These parasitic junctions affect:

- leakage current;
- capacitance;
- electrostatic isolation;
- latch-up risk;
- electrostatic-discharge paths;
- body bias and threshold behavior;
- permissible terminal voltages.

The ideal four-terminal MOSFET model therefore sits inside a larger network of semiconductor junctions.

## Interface charge and non-ideal behavior

Real junctions are not perfect mathematical boundaries. Crystal defects, interface states, contamination and mechanical stress can create recombination-generation centers and modify leakage.

Fabrication quality is one reason semiconductor manufacturing is so demanding. Digital architecture depends on billions of devices behaving within characterized statistical ranges. Error margins, redundancy and design rules exist because microscopic variation cannot be eliminated completely.

## From p-n electrostatics to MOS electrostatics

The p-n junction teaches a general principle: spatial charge distribution creates electric field; electric field modifies carrier distribution; carrier distribution determines conductivity.

A MOS structure applies the same electrostatic logic in a different geometry. Instead of relying only on fixed charge exposed by diffusion, it uses an insulated metal or polysilicon gate to impose an electric field at the semiconductor surface.

The progression is:

    doping profile
        ↓
    carrier diffusion
        ↓
    fixed space charge
        ↓
    electric field and potential barrier
        ↓
    bias-controlled carrier transport
        ↓
    junction behavior
        ↓
    MOS surface electrostatics

The next transistor chapter can therefore be read not as a jump to a new abstraction but as an extension of the same field-and-carrier model.
