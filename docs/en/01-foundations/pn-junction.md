---
id: pn-junction
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - crystal-bands-doping
  - electric-charge-field-potential
related:
- transistor-cmos
---

# P-N junctions and semiconductor interfaces

<div class="abstract">
The p-n junction is the first semiconductor structure in which spatially separated doping produces a self-consistent electric field. It introduces diffusion, depletion, built-in potential, bias, reverse leakage and breakdown. These mechanisms are needed to understand diodes, parasitic junctions inside CMOS, electrostatic isolation and the physical constraints surrounding MOS transistor operation.
</div>

## Joining p-type and n-type material

For p-type and n-type regions brought into contact, Before contact, each bulk region is approximately charge neutral, but their mobile-carrier concentrations differ. The n side contains a high concentration of electrons; the p side contains a high concentration of holes.

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

## Deriving depletion width from Poisson's equation

Consider an abrupt junction with uniform acceptor density N_A on the p side and donor density N_D on the n side. Put the metallurgical junction at x = 0. In the depletion approximation, mobile carriers are neglected between −x_p and x_n, while the adjacent neutral regions have negligible electric field. Ionized acceptors contribute charge density −qN_A and ionized donors contribute +qN_D. The assumption is an approximation to a continuous carrier profile, not a literal absence of all carriers.

One-dimensional Poisson electrostatics gives dE/dx = rho/epsilon_s and E = −dphi/dx. Starting with E = 0 at the p-side depletion edge, integration gives E(x) = −qN_A(x + x_p)/epsilon_s on the p side. On the n side, E(x) = qN_D(x − x_n)/epsilon_s. Continuity of field at zero requires N_A x_p = N_D x_n: the positive and negative uncovered charge magnitudes must match.

The field is negative with this coordinate choice, meaning it points from the n region toward the p region. Integrating −E across the depletion region gives a positive potential rise from p to n. Its magnitude is V_dep = q(N_A x_p² + N_D x_n²)/(2 epsilon_s). With W = x_p + x_n and charge balance, the width becomes W = sqrt((2 epsilon_s/q)(1/N_A + 1/N_D)V_dep). Also x_p = W N_D/(N_A + N_D) and x_n = W N_A/(N_A + N_D).

![Charge, field and potential in a normalized abrupt-junction model](../../assets/diagrams/junction-profiles.svg)

The less heavily doped side therefore contains more depletion width. Equal widths are correct only for equal dopant densities in this model. The peak field magnitude is qN_A x_p/epsilon_s, equivalently qN_D x_n/epsilon_s. Its value and spatial distribution matter for breakdown; the total voltage alone does not specify the local field stress.

## A dimensioned example and bias dependence

Take illustrative model inputs N_A = 10^16 cm⁻³, N_D = 10^15 cm⁻³, n_i = 10^10 cm⁻³, epsilon_s = 1.04 × 10⁻¹² F/cm, q = 1.602 × 10⁻¹⁹ C and V_T = 0.02585 V. The ideal equilibrium expression gives V_bi = V_T ln(N_A N_D/n_i²), approximately 0.655 V. Substitution gives W approximately 0.967 micrometres, of which about 0.088 micrometres lies on the p side and 0.879 on the n side. These are computed examples using declared inputs, not measured ChrisOS hardware parameters.

Under moderate reverse bias V_R, use V_dep = V_bi + V_R in the depletion model. Three volts of reverse bias increase the example width to about 2.285 micrometres. Under forward bias V_F, the simple electrostatic barrier becomes V_bi − V_F, but extrapolating the depletion formula through zero barrier is invalid. Strong injection, series resistance and nonequilibrium carrier populations require a more complete model.

Built-in potential is an internal electrostatic difference, not a free battery available at external terminals in thermal equilibrium. Contact potentials and equilibrium electrochemical conditions must also be included when considering a complete measurement circuit. Ignoring that distinction would wrongly imply a perpetual current source from an unpowered junction.

## Incremental capacitance and conductance

The magnitude of charge per area on either depletion side is Q_A = qN_A x_p = qN_D x_n. Differentiating with respect to reverse-bias magnitude gives depletion capacitance per area C_A = epsilon_s/W for this abrupt-junction approximation. As reverse bias widens depletion, capacitance decreases. Multiplying by junction area gives total capacitance before accounting for edge and parasitic contributions.

Forward conduction introduces stored minority charge and therefore diffusion capacitance, a different mechanism. A small-signal model linearizes around a selected operating point. For the ideal diode exponential, incremental conductance is g_d = I_S exp(V/(nV_T))/(nV_T), approximately I/(nV_T) when forward current greatly exceeds I_S. The corresponding incremental resistance is approximately nV_T/I. Neither quantity is a constant resistance of the diode over its entire voltage range.

| Regime | Dominant model concern | Invalid shortcut |
|---|---|---|
| Thermal equilibrium | Balanced drift and diffusion | Treat internal barrier as an external supply |
| Moderate reverse bias | Depletion widening and generation leakage | Assume exactly zero current |
| Forward low injection | Minority-carrier injection and diffusion | Assign one universal turn-on voltage |
| Strong forward drive | Series resistance, heating, high injection | Extrapolate ideal exponential indefinitely |
| Breakdown | Large field and multiplication or tunneling | Assume all reverse voltages are nondestructive |

These distinctions connect junction theory to CMOS parasitic junctions and to the load seen by switching circuitry. They do not establish a diode simulator, process model or electrical protection feature in ChrisOS. The theory is a prerequisite for interpreting devices; implementation claims in later chapters must return to their own source evidence. [MIT 6.012 lecture notes](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/) provide primary study material on equilibrium junctions, terminal characteristics and small-signal capacitance.
