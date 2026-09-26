---
id: crystal-bands-doping
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - atom-semiconductor
related:
  - pn-junction
  - transistor-cmos
---

# Crystal structure, energy bands and doping

<div class="abstract">
Semiconductor behavior is not explained by the statement that silicon is “between a conductor and an insulator.” The useful engineering model begins with periodic crystal structure, allowed and forbidden electron energies, the Fermi level, carrier statistics and the way dopants alter carrier concentration without destroying bulk charge neutrality. This chapter develops that chain because MOS transistors, junctions, leakage, threshold behavior and ultimately digital logic all depend on it.
</div>

## From isolated atoms to a solid

An isolated silicon atom has discrete quantum states. A macroscopic crystal contains an enormous number of atoms whose electronic states interact. The Pauli exclusion principle prevents all electrons from occupying a single state, and the periodic crystal potential changes the set of permitted wave states. The discrete atomic levels therefore split into very closely spaced levels that are treated macroscopically as energy bands.

The exact band structure is a quantum-mechanical result, but digital-system engineering usually needs three consequences rather than a full solution of the Schrödinger equation. First, electrons can occupy only allowed states. Second, there can be intervals of energy with no permitted states. Third, whether a material conducts depends strongly on which states are occupied and whether nearby unoccupied states are available for carriers to move into under an applied electric field.

In crystalline silicon each atom participates in covalent bonding with neighbors. At low excitation the states associated with bonding form the valence band, while higher-energy mobile states form the conduction band. Between them lies a forbidden interval called the band gap.

## Valence band, conduction band and band gap

The valence band is normally almost full. A completely full band cannot contribute to ordinary conduction in the same way as a partially filled band because available nearby states are absent. The conduction band is normally much less occupied. Electrons promoted into it can respond to an electric field and become mobile carriers.

The band gap, often written as Eg, is the energy separation between the top of the valence band and the bottom of the conduction band. A simplified material comparison is:

| Material class | Electronic condition | Engineering consequence |
|---|---|---|
| conductor | many accessible states near occupied states | current flows readily |
| semiconductor | moderate forbidden gap | carrier density can be controlled |
| insulator | large forbidden gap | ordinary carrier density is very low |

This classification is not a binary law of nature. Temperature, field strength, impurities, crystal defects and geometry can all modify observed behavior. Semiconductor technology is useful precisely because the carrier population is controllable over many orders of magnitude.

## Electrons and holes

When an electron is excited from a valence-band state, it leaves an unoccupied state behind. Tracking every missing electron is inconvenient, so solid-state physics introduces the hole: an effective positive carrier representing an unoccupied valence state.

A hole is not an independent elementary particle inside the chip. It is a quasiparticle description of the collective behavior of electrons in an almost filled band. The model is powerful because electron and hole motion can be described with carrier densities, mobilities and currents.

Two carrier populations therefore matter:

| Symbolic quantity | Meaning |
|---|---|
| n | electron concentration |
| p | hole concentration |
| ni | intrinsic carrier concentration |

For intrinsic material near thermal equilibrium, electron and hole concentrations are equal: n = p = ni. Silicon at ordinary temperatures has enough thermal excitation to create some carriers, but not enough for intrinsic material alone to provide the controlled behavior needed for dense digital circuits.

## The Fermi level

The Fermi level is an energy reference tied to the probability that electronic states are occupied. It is not simply “the energy of the electrons.” In equilibrium it provides a compact way to describe carrier population.

Moving the Fermi level closer to the conduction band corresponds to conditions with a larger electron population. Moving it toward the valence band corresponds to a larger hole population. Doping changes this equilibrium relationship.

This matters later because semiconductor device diagrams often show band edges bending relative to a Fermi level. That band bending is a compact representation of electrostatic potential and carrier redistribution. MOS capacitor and MOSFET behavior are difficult to understand without this vocabulary.

## Intrinsic silicon and thermal generation

Even a perfect crystal at nonzero temperature experiences thermal excitation. Some electrons gain enough energy to cross the band gap, creating electron-hole pairs. Recombination is the reverse process in which a conduction electron loses energy and fills an available valence state.

At equilibrium, generation and recombination balance statistically. Increasing temperature usually increases intrinsic carrier concentration strongly. This is one reason leakage current rises with temperature and why thermal design affects not only reliability but also transistor behavior.

A digital abstraction may label a node HIGH or LOW, but leakage, subthreshold current and junction current are consequences of physical carrier populations underneath that abstraction.

## Doping as controlled modification of carrier density

Doping introduces small, controlled concentrations of impurity atoms into silicon. The dopant is chosen so that it changes the number of readily available carriers.

Donor dopants contribute electrons that require relatively little energy to become mobile. Material in which electrons are the majority carriers is called n-type. Acceptor dopants create accessible states that make holes the majority carriers; this is p-type material.

The names do not mean that an n-type region contains a large net negative charge or that a p-type region contains a large net positive charge. In the bulk, ionized dopant atoms and mobile carriers nearly balance. Doping changes carrier concentration and electrical response while macroscopic charge neutrality remains a useful approximation away from junctions and depleted regions.

## Majority and minority carriers

In n-type material, electrons are majority carriers and holes are minority carriers. In p-type material, holes are majority carriers and electrons are minority carriers.

Minority carriers cannot be ignored. Junction leakage, recombination, bipolar effects and transient device behavior depend on them. For introductory digital reasoning, however, majority-carrier density explains why a doped region can be made far more conductive than intrinsic silicon.

A simplified equilibrium relation often used as a first approximation is the mass-action relation:

n × p ≈ ni²

Increasing one equilibrium carrier population therefore corresponds to a reduction in the other. The full physical picture depends on degeneracy, temperature and material properties, but the relation captures the reciprocal character of equilibrium carrier populations in ordinary nondegenerate semiconductor conditions.

## Conductivity and mobility

Carrier concentration alone does not determine conductivity. Mobility describes how effectively carriers drift in response to an electric field. A common first-order relation is:

conductivity ≈ q × (n μn + p μp)

where q is elementary charge magnitude and μn and μp are electron and hole mobility.

Doping raises carrier concentration, but heavy doping can also reduce mobility because scattering increases. Device design is therefore not “more dopant is always better.” Semiconductor engineering is an optimization across conductivity, junction shape, threshold behavior, electric field, leakage, capacitance and manufacturing constraints.

## Spatial doping profiles

Real integrated circuits do not contain infinite uniform regions. Dopant concentration varies spatially. Ion implantation, diffusion and subsequent processing create profiles whose depth and lateral shape matter.

A sharp conceptual boundary between p and n material is useful for theory, but fabricated junctions have finite transition regions. Modern transistors use carefully engineered wells, source/drain extensions, channel doping and other structures to control short-channel behavior and electric fields.

For operating-system documentation, the important lesson is that a transistor is not an ideal symbolic switch fabricated directly from Boolean algebra. Its switching properties come from continuous material profiles and electrostatics that are engineered so higher layers can safely use a discrete abstraction.

## Energy-band diagrams as engineering maps

Energy-band diagrams plot conduction-band and valence-band edges as a function of position. They are not literal physical hills inside silicon. They are maps of permitted energy relative to electrostatic conditions.

When the band edges are flat, the electrostatic potential is spatially uniform in the simplified picture. When they bend, carrier energy changes with position. At a p-n junction or MOS surface, band bending reveals the electric field and explains why carriers are attracted, repelled or depleted.

Three different diagrams should not be confused:

| Diagram | Horizontal axis | What it explains |
|---|---|---|
| crystal lattice | physical position | atomic arrangement |
| band structure E(k) | wave vector | allowed energy relation |
| band-edge diagram E(x) | physical position | electrostatic carrier barriers |

Keeping these representations separate prevents many common conceptual errors.

## Why doping is the bridge to devices

Digital logic requires regions with predictable carrier types and regions whose carrier density can be altered by an electric field. Doping supplies the fixed background that makes both junctions and MOS channels possible.

The conceptual sequence is:

    silicon crystal
        ↓
    allowed energy bands
        ↓
    thermal carrier population
        ↓
    donor or acceptor doping
        ↓
    engineered n-type and p-type regions
        ↓
    junctions and MOS field control
        ↓
    transistors
        ↓
    digital gates

The next chapter uses these doped regions to construct the p-n junction, depletion region and diode relation before the text proceeds to MOS electrostatics and CMOS logic.
