---
id: atom-semiconductor
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: []
related:
  - transistor-cmos
---

# Atom, electrical charge and semiconductor physics

<div class="abstract">
Digital computers are discrete-state machines built from continuous physical phenomena. The purpose of this chapter is to establish the minimum physical chain required to understand why a transistor can represent and transform binary state without treating a logic gate as an unexplained primitive.
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

## Energy bands in solids

When large numbers of atoms form a crystal, individual atomic energy levels combine into bands of allowed energies. Two are central:

- the **valence band**, whose electrons participate in bonding;
- the **conduction band**, whose available states permit mobile carriers to conduct current.

The energy interval between them is the **band gap**. Conductors have readily available mobile states. Insulators have a large band gap that strongly suppresses carriers under ordinary conditions. Semiconductors occupy the useful middle ground: their carrier population can be controlled by temperature, impurities and electric fields.

Silicon is useful because its crystal and oxide chemistry allow highly repeatable structures whose conductivity can be modified locally.

## Doping

Pure crystalline silicon is an intrinsic semiconductor. Integrated circuits deliberately introduce small concentrations of impurity atoms.

**n-type material** provides additional electrons that can act as majority carriers. **p-type material** creates electron vacancies conventionally called holes, which behave as positive mobile carriers in the semiconductor model.

Doping does not simply make silicon "positive" or "negative." Bulk material remains nearly charge neutral. Doping changes the density and type of mobile carriers and therefore the electrical behavior of junctions and field-effect structures.

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

```text
continuous voltage
       │
       ├── low range  ──> logical 0
       │
       ├── undefined / transition region
       │
       └── high range ──> logical 1
```

The abstraction works because subsequent gates restore degraded analog signals toward valid voltage levels. Digital design therefore relies on analog device physics while exposing discrete logical behavior.

## Why this matters to operating systems

A kernel manipulates registers, page-table bits, interrupt flags and device registers as if each bit were exact. The physical machine underneath stores those states as charges and voltages in transistor networks. The software abstraction is reliable because multiple layers enforce discrete contracts:

```text
semiconductor device
    ↓
transistor switching
    ↓
logic gate
    ↓
latch / flip-flop
    ↓
register or memory cell
    ↓
architectural bit
    ↓
instruction-set contract
    ↓
kernel data structure
```

The operating system does not solve semiconductor equations during execution. Nevertheless, terms such as volatile memory, propagation delay, clock frequency, metastability, power state and hardware fault originate in this physical layer.

## Boundary of the model

The documentation uses semiconductor physics only to the depth needed to explain computer mechanisms. Detailed solid-state quantum mechanics, fabrication process chemistry and transistor device simulation belong to semiconductor engineering rather than kernel engineering. The next chapter moves from controllable semiconductor conduction to the MOSFET and CMOS logic gate.
