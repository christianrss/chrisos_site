---
id: atom-semiconductor
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/gfx/graphics.c
symbols:
- gfx_rgb
depends_on: []
related:
- crystal-bands-doping
- transistor-cmos
- pixels-framebuffer
---


# Matter, atoms, charge and physical models

<div class="abstract">
Digital computers are discrete-state machines built from continuous physical phenomena. This chapter establishes the matter, atomic-state, charge, energy and modeling concepts required before electrostatics, circuit theory and semiconductor-device physics are introduced as separate layers.
</div>

## Matter and charge

Ordinary electronic hardware is made from atoms: nuclei containing protons and neutrons surrounded by quantum states occupied by electrons. For computer engineering, the relevant property is not a miniature planetary model of the atom but the existence of electrically charged particles and permitted energy states.

An electron carries negative elementary charge. A proton carries the same magnitude of positive charge. A body is electrically neutral when the net charge balances. A potential difference establishes an electric field; mobile charge carriers subjected to that field can produce current.

Three electrical quantities recur throughout hardware:

| Quantity | Meaning | SI unit |
|---|---|---|
| charge `Q` | net electrical charge | coulomb |
| voltage `V` | potential difference, energy per unit charge | volt |
| current `I` | rate of charge flow, `dQ/dt` | ampere |

Resistance describes how strongly a structure opposes current. Ohm's law, `V = IR`, is a macroscopic relation useful for conductors and resistive elements; transistor operation requires the additional physics of semiconductors and electric fields.

## Models, scales and electron-state interpretation

An orbital is a quantum state, not a small classical orbit around the nucleus. The squared magnitude of its wavefunction determines a probability density for position measurements under the model. Energy levels and the occupation of available states constrain the behavior of electrons. In a solid, the collective arrangement of atoms changes the allowed states, so copying an isolated-atom picture directly into a transistor gives the wrong model.

Several descriptions are useful at different scales. A quantum treatment explains permitted states and band structure. A semiclassical transport model describes carrier populations moving through a material. Circuit theory aggregates voltage and current at terminals. Logic theory then assigns discrete values to ranges of electrical conditions. Passing between these descriptions requires assumptions; it does not make their variables interchangeable. A C boolean is not an electron, and a particular bit does not generally correspond to one identifiable electron moving through the processor.

The relevant distinction between a model and a measurement is also essential. A simple drawing of energy bands conveys allowed and forbidden energy intervals. It does not show the physical height of electrons above a silicon surface. A potential-energy diagram uses a spatial axis and an energy axis with different units. Confusing those axes would turn an explanation of carrier motion into an incorrect geometric picture.

## Fields, force and potential energy

An electric field gives the force per unit positive test charge. In a quasistatic description, a carrier with charge `q` experiences force `F = qE`. Because an electron has negative charge, its force direction is opposite the field direction. Conventional current is defined in the direction of positive charge flow, so electron drift and current can point in opposite directions without contradiction.

Potential difference measures energy change per charge. For a charge moved through potential difference `ΔV`, the potential-energy change is `ΔU = q ΔV`. A volt is a joule per coulomb. This dimensional relation is a useful check: multiplying voltage by charge yields energy, while multiplying voltage by current yields power. Voltage is not an amount of current, and charge is not itself a rate.

| Expression | Dimensions | Interpretation |
|---|---|---|
| `I = dQ/dt` | C/s | Charge flow rate |
| `ΔU = q ΔV` | C · J/C | Potential-energy change |
| `P = VI` | J/C · C/s | Electrical power |
| `C = Q/V` | C/V | Capacitance in the linear model |
| `R = V/I` | V/A | Resistance for the specified operating relation |

The last two rows describe component models. A constant capacitance or resistance may be adequate over one operating range and inadequate over another. Nonlinear devices require their actual terminal relationships; the symbols do not guarantee linearity. This is the reason Ohm's law cannot, by itself, explain MOSFET switching or diode rectification.

## Charge storage and switching energy

For an ideal linear capacitor, `Q = CV`. The stored electrostatic energy is `U = C V² / 2`, obtained by integrating the work of adding charge as the capacitor voltage rises. If a load capacitance is charged from zero to a supply `V` through a resistive path, the supply provides `C V²`: half becomes stored energy and half is dissipated in the simplified charging path. Discharging loses the stored half unless the circuit deliberately recovers it.

This calculation explains the squared-voltage dependence of ordinary switching energy. A hypothetical 10 fF load charged to 1 V stores 5 fJ. One complete charge/discharge cycle in the simple model draws 10 fJ from the supply. These are explicitly illustrative values, not measured parameters of any specific processor. They show why reducing voltage can change energy substantially even when the Boolean computation is unchanged.

An ideal gate insulator blocks steady conduction, but its capacitance must still be charged and discharged when the input changes. “Voltage controlled” therefore does not mean “requires no energy.” Leakage, short-circuit current during transitions and interconnect add further costs. Software-visible power behavior is many layers above this model, but it cannot be understood by counting only arithmetic results while ignoring how frequently electrical nodes switch.

## Energy bands in solids

When large numbers of atoms form a crystal, individual atomic energy levels combine into bands of allowed energies. Two are central:

- the **valence band**, whose electrons participate in bonding;
- the **conduction band**, whose available states permit mobile carriers to conduct current.

The energy interval between them is the **band gap**. Conductors have readily available mobile states. Insulators have a large band gap that strongly suppresses carriers under ordinary conditions. Semiconductors occupy the useful middle ground: their carrier population can be controlled by temperature, impurities and electric fields.

Silicon is useful because its crystal and oxide chemistry allow highly repeatable structures whose conductivity can be modified locally.

## Carrier concentration, mobility and conductivity

Let `n` denote mobile electron concentration, `p` hole concentration, `μ_n` electron mobility and `μ_p` hole mobility. In a simple low-field transport model, conductivity is `σ = q(n μ_n + p μ_p)`, with `q` taken as the positive elementary-charge magnitude. For a uniform material under the corresponding assumptions, drift-current density is proportional to electric field. The relation separates how many carriers are available from how readily they respond to the field.

This separation matters because adding dopants can increase a carrier population while also changing scattering and mobility. Conductivity cannot be predicted from the slogan “more electrons” without stating the regime. High fields, strong nonuniformity, interfaces and small device dimensions can require a model beyond constant mobility. An introductory equation is useful only with those limits attached.

Holes describe missing electron occupation in a nearly filled band. Their effective positive-charge description summarizes the collective response without requiring a literal positive particle identical to a proton moving through the lattice. The language is economical but precise: a hole is a quasiparticle description, while a dopant ion is a different physical entity. Keeping them separate clarifies why a p-type region need not carry a large net positive bulk charge.

## Doping

Pure crystalline silicon is an intrinsic semiconductor. Integrated circuits deliberately introduce small concentrations of impurity atoms.

**n-type material** provides additional electrons that can act as majority carriers. **p-type material** creates electron vacancies conventionally called holes, which behave as positive mobile carriers in the semiconductor model.

Doping does not simply make silicon "positive" or "negative." Bulk material remains nearly charge neutral. Doping changes the density and type of mobile carriers and therefore the electrical behavior of junctions and field-effect structures.

## Drift, diffusion and equilibrium

An electric field can drive carriers, producing drift. A concentration gradient can also produce a net carrier flow, called diffusion. At a junction in thermal equilibrium, opposing transport contributions balance so that there is no net external current, even though microscopic motion has not stopped. Equilibrium is a balance of processes rather than a picture of motionless electrons.

The built-in field develops as charge redistribution leaves ionized dopants exposed near the interface. Those charges and the electrostatic potential are coupled: a charge distribution affects the field, and the field affects carrier populations and motion. Device analysis solves compatible electrostatic and transport conditions with boundary assumptions. Describing the junction only as two differently colored blocks omits the mechanism responsible for its electrical behavior.

Applied bias changes the conditions at the terminals and alters the carrier flow. Temperature also changes available carriers and transport properties. Consequently, a device's operating point and its surroundings matter. There is no single universal current associated with “a silicon junction” independently of geometry, doping, voltage and temperature.

## The p-n junction

Bringing p-type and n-type regions together creates a junction. Carriers initially diffuse across the boundary and recombine. The exposed ionized dopants produce a depletion region and an internal electric field. The resulting potential barrier makes current strongly dependent on applied polarity.

The p-n junction explains diode behavior and remains fundamental inside integrated circuits, although modern CMOS logic is primarily controlled through field-effect transistors rather than by using diodes as switches.

## From electric field to controlled conduction

A computer needs a device whose conductive state can be controlled by another electrical signal. The MOS field-effect transistor supplies this property.

The essential step is electrostatic control: a voltage applied to an insulated gate changes the carrier distribution in a semiconductor region. Above an appropriate threshold, a conductive channel forms or is depleted. The control terminal does not need to drive the same continuous current that flows through the controlled path.

This separation between **control signal** and **controlled current path** is what makes large logic networks possible.

## Binary abstraction

No physical wire contains an abstract mathematical 0 or 1. A digital circuit defines voltage ranges that are interpreted as logic levels. The ranges deliberately leave noise margin between valid low and high levels.

A simplified model is:

![Voltage ranges / faixas de tensão](../../assets/diagrams/voltage-levels.svg)

The abstraction works because subsequent gates restore degraded analog signals toward valid voltage levels. Digital design therefore relies on analog device physics while exposing discrete logical behavior.

## Relevance to operating-system abstractions

A kernel manipulates registers, page-table bits, interrupt flags and device registers as if each bit were exact. The physical machine underneath stores those states as charges and voltages in transistor networks. The software abstraction is reliable because multiple layers enforce discrete contracts:

![From matter to code / da matéria ao código](../../assets/diagrams/foundations-chain.svg)

The operating system does not solve semiconductor equations during execution. Nevertheless, terms such as volatile memory, propagation delay, clock frequency, metastability, power state and hardware fault originate in this physical layer.

## From physical reliability to software invariants

The abstraction of a stable bit depends on sufficient electrical margins, appropriate timing and functioning storage. Higher layers add their own invariants. A memory controller maintains its protocol; an ISA defines observable access semantics; an allocator maintains ownership; a framebuffer function interprets bytes as pixels. These obligations compose, but they are not substitutes for one another.

For example, a pixel encoded as `0x00123456` can be held correctly by the memory cells yet displayed with exchanged channels because software used the wrong format. Conversely, correct integer packing cannot repair a physical storage fault. In ChrisOS, `gfx_rgb` is the source-level point where red, green and blue become bit fields. That function documents an encoding operation above the electrical layer; it does not model carrier motion. The bridge to its exact implementation is developed in the framebuffer chapter.

The correct learning progression therefore retains each model's units, assumptions and validation method. Semiconductor theory explains why controllable and persistent electrical states are possible. Circuit and logic theory explain their composition. Architecture specifies the machine contract consumed by the kernel and emulated by ChrisCPU. A claim at one level should only be promoted to the next when the connecting interface has been explained.

## Primary references

- [MIT 6.012 — Microelectronic Devices and Circuits](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-spring-2009/pages/lecture-notes/).
