---
id: transmission-lines-differential-signals
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - docs/CURRENT_HARDWARE_AUDIT.md
symbols:
  - pci_read
  - pci_write
depends_on:
  - electromagnetic-induction-transformers
  - ac-signals-frequency-impedance
related:
  - noise-grounding-signal-integrity
  - power-delivery-regulation
  - clock-timing
  - buses-mmio-dma
  - pci-pcie
---

# Transmission lines and differential signaling

<div class="abstract">
A conductor stops behaving like an equipotential wire when propagation delay, distributed inductance and distributed capacitance become significant compared with the signal transition being transported. Transmission-line theory replaces the lumped-wire approximation with traveling electromagnetic waves characterized by propagation constant, characteristic impedance, attenuation and delay. This chapter derives the telegrapher equations, reflection and termination behavior, differential and common modes, coupled-pair impedance, loss, crosstalk, return paths, discontinuities and the relationship between physical links and digital protocols. It then fixes the ChrisOS boundary precisely: current PCI code performs software-visible configuration-space transactions and does not implement the PCI Express electrical PHY, equalization or board-level transmission-line model.
</div>

## Prerequisites and scope

This chapter assumes:

- voltage, current, resistance and power;
- capacitance and inductance;
- sinusoidal steady-state impedance;
- electromagnetic induction;
- basic complex-number notation;
- the distinction between software-visible protocol state and physical electrical behavior.

The purpose is not to turn every interconnect into a full electromagnetic field problem. The purpose is to identify when the ordinary lumped approximation

~~~text
node A voltage ≈ node B voltage at the same instant
~~~

stops being adequate.

A transmission line is not defined by whether the conductor is physically long in centimeters. It is defined by electrical length: propagation delay and distributed behavior relative to the time scale and spectrum of the waveform.

## From lumped wires to distributed circuits

A short, slow interconnect can often be approximated by one resistance, one capacitance and perhaps one inductance.

A physically extended interconnect instead contains resistance, inductance, capacitance and dielectric leakage continuously along its length.

For a differential slice of length (dx), define per-unit-length parameters:

| Symbol | Meaning | SI unit |
|---|---|---|
| R' | series resistance per length | Ω/m |
| L' | series inductance per length | H/m |
| G' | shunt conductance per length | S/m |
| C' | shunt capacitance per length | F/m |

An infinitesimal model is

~~~text
       R'dx        L'dx
----////--------LLLL----->
        |                      |
        | G'dx                 | C'dx
        |                      |
-------+----------------------+--- reference
~~~

No one slice explains propagation. Propagation emerges from the continuum of coupled slices.

## Telegrapher equations

Applying KVL and KCL to an infinitesimal segment and taking the limit gives the telegrapher equations:

~~~text
∂V/∂x = -R' I - L' ∂I/∂t

∂I/∂x = -G' V - C' ∂V/∂t
~~~

These are distributed differential equations. Voltage and current depend on both position and time.

In sinusoidal steady state, replace time differentiation by (jω):

~~~text
dV/dx = -(R' + jωL') I

dI/dx = -(G' + jωC') V
~~~

Differentiating once more produces wave equations:

~~~text
d²V/dx² = γ² V

d²I/dx² = γ² I
~~~

with propagation constant

~~~text
γ = sqrt[(R' + jωL')(G' + jωC')]
~~~

Write

~~~text
γ = α + jβ
~~~

where:

~~~text
α = attenuation constant
β = phase constant
~~~

The general voltage solution is a sum of forward and reverse waves:

~~~text
V(x) = V+ e^(-γx) + V- e^(+γx)
~~~

The reverse term is the mathematical representation of reflection.

## Characteristic impedance

The ratio of voltage to current for a single traveling wave is the characteristic impedance:

~~~text
Z0 = sqrt[(R' + jωL') / (G' + jωC')]
~~~

Z0 is not the DC resistance of the conductor.

It is the voltage/current ratio of a traveling electromagnetic wave supported by the structure.

For a low-loss or ideal lossless line where R' and G' are neglected:

~~~text
Z0 = sqrt(L'/C')
~~~

and

~~~text
γ = jω sqrt(L'C')
~~~

so

~~~text
β = ω sqrt(L'C')
~~~

and phase velocity is

~~~text
v_p = ω/β = 1/sqrt(L'C')
~~~

The one-way delay of a uniform line of length (l) is

~~~text
t_d = l / v_p
~~~

or equivalently

~~~text
t_d = l sqrt(L'C')
~~~

in the ideal lossless approximation.

## Propagation is finite

A transition launched at one end does not appear everywhere simultaneously.

A simplified timeline is:

~~~text
driver changes voltage
      |
      v
forward wave launched
      |
      |  propagation delay t_d
      v
load sees first incident edge
      |
      v
reflection may be generated
      |
      |  propagation delay t_d
      v
source sees returning reflection
~~~

A complete round trip requires approximately (2 t_d).

This fact is central to digital timing. A receiver can temporarily see a voltage determined by incident and reflected waves before the source has any information about the load mismatch.

## Electrical length and rise time

For a sine wave, electrical length can be compared with wavelength:

~~~text
λ = v_p / f
~~~

For a digital edge, the more relevant scale is usually rise/fall time because a fast edge contains harmonics far above the nominal bit or clock frequency.

There is no universal physical law saying that a trace becomes a transmission line at exactly one particular fraction of rise time. Engineering rules such as comparing one-way delay with a fraction of edge time are approximation criteria.

The safe reasoning sequence is:

~~~text
find edge time / relevant spectrum
      ↓
estimate propagation delay
      ↓
compare the two
      ↓
if delay is material, use distributed analysis
~~~

A low clock frequency does not guarantee lumped behavior if edge transitions are fast.

## Reflection coefficient

Let a line of characteristic impedance (Z0) terminate in load (ZL).

At the load, the voltage reflection coefficient is

~~~text
Γ_L = (Z_L - Z0) / (Z_L + Z0)
~~~

The reflected voltage is

~~~text
V_reflected = Γ_L V_incident
~~~

and the load voltage at the arrival instant is

~~~text
V_load = V_incident + V_reflected
       = V_incident (1 + Γ_L)
~~~

Important ideal cases are:

| Load | ΓL | Consequence |
|---|---:|---|
| ZL = Z0 | 0 | no reflected wave |
| open circuit | +1 | reflected voltage has same polarity |
| short circuit | -1 | reflected voltage has opposite polarity |
| ZL > Z0, finite | between 0 and +1 | positive partial reflection |
| 0 < ZL < Z0 | between -1 and 0 | negative partial reflection |

Current reflection has the opposite sign convention for the reverse wave because reverse-wave current travels in the opposite direction.

## Source reflection coefficient

A reflected wave that reaches the source sees source impedance (ZS).

The source-end voltage reflection coefficient is

~~~text
Γ_S = (Z_S - Z0) / (Z_S + Z0)
~~~

If neither source nor load is matched, waves can bounce repeatedly:

~~~text
source -> load -> source -> load -> ...
~~~

Each round trip is scaled by products of reflection coefficients and line attenuation.

This is why ringing can persist after a digital transition even when the logical value is already known.

## Initial launched amplitude

A source with Thevenin voltage (VS) and source impedance (ZS) launching into a line initially behaves as though the line presents (Z0):

~~~text
V+ = VS Z0 / (ZS + Z0)
~~~

Only after reflections return does the source learn about the remote load.

Example:

~~~text
VS = 1.0 V
ZS = 50 Ω
Z0 = 50 Ω

V+ = 0.5 V
~~~

If the far end is open, ΓL = +1 and the load voltage becomes 1.0 V when the incident edge arrives.

## Standing waves and VSWR

For a sinusoidal line with reflection magnitude |Γ|, interference between forward and reverse waves produces standing-wave maxima and minima.

The voltage standing-wave ratio is

~~~text
VSWR = (1 + |Γ|) / (1 - |Γ|)
~~~

for |Γ| < 1.

A matched line has

~~~text
Γ = 0
VSWR = 1
~~~

VSWR is useful for periodic RF behavior. For isolated digital transitions, time-domain reflection diagrams are usually more intuitive.

## Input impedance of a lossless line

A lossless line of length (l), phase constant (β) and load (ZL) presents input impedance

~~~text
Z_in =
Z0 [ZL + j Z0 tan(βl)]
   -------------------
   [Z0 + j ZL tan(βl)]
~~~

Therefore a line can transform impedance as a function of electrical length.

A quarter-wave section can invert impedance in the ideal case:

~~~text
l = λ/4

Z_in = Z0² / ZL
~~~

This is conceptually related to transformer impedance conversion, but the physical mechanism is distributed-wave propagation rather than magnetic mutual induction.

## Termination strategies

Termination attempts to control reflections by making one or more discontinuities look like the line impedance over the relevant spectrum.

Common strategies include:

| Strategy | Principle | Typical trade-off |
|---|---|---|
| parallel termination | load approximates Z0 | continuous DC power |
| source/series termination | ZS + added R approximates Z0 | load may settle after one reflection |
| Thevenin termination | resistor network creates target impedance/bias | static power and component count |
| AC termination | series C-R presents match mainly to transitions | baseline/waveform dependence |
| differential termination | resistor across pair approximates Zdiff | dissipates differential signal power |

Termination values are not chosen from logic voltage alone. They depend on interconnect impedance, topology, driver impedance, receiver behavior and the applicable interface standard.

## Lossy lines

Real lines attenuate and distort.

The propagation constant

~~~text
γ = α + jβ
~~~

contains both loss and phase.

Loss mechanisms include:

- conductor resistance;
- skin effect;
- proximity effect;
- dielectric loss;
- radiation or leakage;
- connector and via discontinuities;
- roughness effects at sufficiently high frequency.

As frequency rises, R' and G' need not remain constant, so both attenuation and characteristic impedance can become frequency-dependent.

A digital edge is therefore filtered while it propagates.

## Dispersion

If phase velocity varies with frequency, different spectral components of an edge arrive with different delay.

That is dispersion.

Consequences include:

- slower apparent edges;
- pulse broadening;
- inter-symbol interference;
- phase distortion.

A lossless nondispersive line is an idealization. Real board, cable and package structures are only approximately nondispersive over limited bands.

## Differential signaling

Differential signaling uses two conductors and encodes information primarily in their voltage difference.

Define conductor voltages relative to a reference:

~~~text
V_p
V_n
~~~

Then

~~~text
V_diff = V_p - V_n

V_cm = (V_p + V_n) / 2
~~~

Equivalently,

~~~text
V_p = V_cm + V_diff/2
V_n = V_cm - V_diff/2
~~~

These definitions separate differential mode from common mode.

An ideal purely differential transition changes the two conductors symmetrically about a constant common-mode level.

## Differential current and return field

In an ideal symmetric pair, differential currents are equal in magnitude and opposite in direction:

~~~text
I_p = +I
I_n = -I
~~~

The electromagnetic fields couple strongly between conductors, so much of the return path is associated with the other member of the pair.

But "differential" does not mean the surrounding reference planes and structures are irrelevant.

Real links also support common-mode current, displacement current and coupling to chassis/planes. Asymmetry can convert differential energy into common mode.

## Even and odd modes

Coupled lines support modal solutions.

For a symmetric pair:

- odd mode corresponds to opposite voltages/currents;
- even mode corresponds to equal-polarity excitation.

A common convention relates differential impedance to odd-mode impedance by

~~~text
Z_diff = 2 Z_odd
~~~

and common-mode impedance to even-mode impedance according to the selected current/voltage normalization.

The factor conventions matter. A simulator or measurement report must define whether impedance is per conductor, modal or port-to-port.

## Coupling changes impedance

Two traces do not have the same field distribution when far apart and when tightly coupled.

Reducing pair spacing can:

- increase mutual capacitance;
- alter mutual inductance;
- change odd/even-mode impedances;
- change crosstalk to neighboring structures;
- change sensitivity to geometry variation.

Therefore differential impedance is a property of the whole cross-section:

~~~text
trace width
spacing
copper thickness
dielectric height
dielectric constant
reference-plane geometry
mask/cover materials
~~~

It is not determined by spacing alone.

## Skew

If the two members of a differential pair have unequal delay, their transitions do not arrive simultaneously.

Define pair skew approximately as

~~~text
t_skew = |t_p - t_n|
~~~

Skew can temporarily convert differential energy into common-mode voltage and reduce the available sampling margin.

Length matching is one method of controlling skew, but equal geometric length is only a proxy. Different local dielectric environment or discontinuities can still create unequal electrical delay.

## Common-mode conversion

Perfect symmetry keeps differential and common modes separated.

Real asymmetries include:

- unequal trace geometry;
- one-sided via transitions;
- connector pin imbalance;
- reference-plane interruptions;
- unequal package paths;
- asymmetric ESD or filtering components;
- pair skew.

These can generate mode conversion:

~~~text
differential -> common mode
common mode  -> differential
~~~

Common-mode energy can increase electromagnetic emissions and receiver stress even when the logical differential signal appears functional.

## Crosstalk

Changing voltage and current on one interconnect couple electromagnetically into nearby interconnects.

Capacitive coupling is associated with changing electric field; inductive coupling is associated with changing magnetic field.

A distributed pair of aggressor/victim lines can exhibit near-end and far-end crosstalk.

The exact signs and magnitudes depend on:

- geometry;
- coupling length;
- edge rate;
- terminations;
- propagation velocity;
- capacitive versus inductive coupling balance.

It is unsafe to assign a universal NEXT or FEXT percentage without the geometry and interface conditions.

## Return-path continuity

A single-ended signal requires a return path.

At high frequency, return current tends to follow the path of low electromagnetic impedance associated with the signal's field, often close to the trace over a reference plane.

A split or void in that reference can force a larger loop.

Consequences can include:

- increased inductance;
- larger radiation loop;
- impedance discontinuity;
- crosstalk;
- mode conversion.

The schematic netlist may still show "ground" as one node while the physical high-frequency return path is poor. Logical connectivity is not sufficient for signal integrity.

## Vias, connectors and discontinuities

Any geometry transition can disturb characteristic impedance.

Examples:

- vias;
- via stubs;
- connectors;
- packages;
- neck-down regions;
- test pads;
- layer changes;
- reference-plane changes;
- AC coupling capacitors;
- ESD devices.

A discontinuity can be approximated locally by excess capacitance, excess inductance or a short distributed section, but wideband behavior may require a field-derived model or measured S-parameters.

## Stubs

An unused branch or via stub can reflect energy.

A stub behaves as a frequency-dependent impedance because the wave travels to the stub end and back.

At certain electrical lengths it can create strong notches or resonances.

This is one reason high-speed interconnect design often controls unused via barrels and branch topology.

## S-parameters

At high frequency, direct voltage/current impedance descriptions can become awkward because incident and reflected waves are the natural measured quantities.

Scattering parameters describe relations among traveling waves at ports.

For a two-port network:

~~~text
S11  input reflection
S21  forward transmission
S12  reverse transmission
S22  output reflection
~~~

The values depend on port reference impedances and frequency.

A small |S11| generally corresponds to good matching under the chosen reference, while |S21| characterizes transmitted amplitude/phase. Full interpretation requires the measurement or simulation convention.

This chapter does not substitute a complete microwave network treatment.

## Time-domain reflectometry

Time-domain reflectometry launches an edge and observes returned energy versus time.

Conceptually:

~~~text
launch known edge
     ↓
measure reflection versus delay
     ↓
map delay to distance using propagation velocity
     ↓
infer impedance discontinuities
~~~

Positive or negative reflection polarity can indicate whether local impedance rises or falls relative to the reference line.

Spatial resolution is limited by the source rise time, instrument bandwidth and propagation characteristics.

## Eye diagrams and sampling margin

A receiver does not only care about one isolated transition. A stream of symbols creates a distribution of voltages and transition times.

An eye diagram overlays many unit intervals.

It visualizes effects such as:

- inter-symbol interference;
- noise;
- deterministic/random jitter;
- attenuation;
- reflections;
- duty-cycle distortion;
- crosstalk.

The eye is not itself a proof of protocol compliance. Standards define particular masks, test fixtures, equalization states and measurement procedures.

## Equalization

Lossy channels can suppress high-frequency content more strongly than low-frequency content.

High-speed serial links may compensate with:

- transmitter pre-emphasis/de-emphasis;
- receiver continuous-time linear equalization;
- decision-feedback equalization;
- adaptive training.

Equalization deliberately reshapes the spectrum; it does not remove the underlying transmission-line physics.

A software-visible PCIe device can operate correctly while these mechanisms are handled entirely by PHY logic below the operating system.

## Differential signaling is not automatically noise-proof

A differential receiver rejects common-mode disturbance only to the degree that:

- the disturbance couples similarly to both conductors;
- receiver common-mode range is not exceeded;
- common-mode rejection is finite but sufficient;
- pair balance is preserved;
- timing skew remains acceptable.

Noise that couples asymmetrically becomes differential error and cannot be removed by common-mode subtraction.

"Use differential" is therefore not a substitute for impedance, return-path and symmetry control.

## Encoding and protocol are different layers

A digital protocol defines symbols, framing, state transitions and error handling.

The physical channel determines whether the encoded waveform reaches the receiver with adequate amplitude and timing margin.

A useful hierarchy is:

~~~text
software-visible transaction
        ↓
link/protocol framing
        ↓
coding / serialization
        ↓
PHY transmitter
        ↓
package + connector + PCB/cable transmission line
        ↓
PHY receiver
        ↓
clock/data recovery and decoding
        ↓
software-visible result
~~~

An operating-system driver normally enters this hierarchy above most analog PHY behavior.

## Standards context

The PCI-SIG PCI Express Base Specification includes electrical, protocol, platform-architecture and programming-interface requirements. As of the reviewed documentation date, PCI-SIG lists PCI Express Base Specification Revision 7.1, dated 2026-09-17, as the current approved Base specification.

IEEE 802.3-2022 remains the base Ethernet standard currently identified by IEEE while an active P802.3 revision project superseding it is in development. IEEE 802.3 separates MAC architecture from speed- and medium-specific physical-layer entities.

These standards are evidence that practical links specify much more than an abstract Z0. They define particular transmitters, receivers, channels, coding, training and compliance methods.

No numerical insertion-loss, eye-mask, jitter, return-loss or equalization limit from one interface should be copied into another. Such limits are revision- and medium-specific.

## ChrisOS architectural boundary

Current ChrisOS source exposes PCI configuration-space access through:

~~~text
pci_read(bus, slot, func, off)
pci_write(bus, slot, func, off, value)
~~~

in:

~~~text
kernel/metal/pci.c
kernel/metal/pci.h
~~~

The implementation forms the legacy PCI configuration address at I/O port 0xCF8 and transfers data through 0xCFC.

That is a software-visible configuration mechanism. It is not a PCI Express serializer, lane equalizer, channel model, TDR, eye analyzer or transmission-line solver.

The current functions carry no parameters for:

~~~text
trace geometry
Z0 / Zdiff
insertion loss
return loss
lane presets
equalizer coefficients
eye masks
S-parameters
propagation delay
~~~

Therefore this chapter must not infer board-level or PCIe-PHY behavior from pci_read/pci_write.

## Current hardware evidence boundary

The reviewed docs/CURRENT_HARDWARE_AUDIT.md explicitly states that nothing in that audit is PROVEN-HARDWARE and that no physical machine was booted in that pass.

That matters here.

A successful QEMU-visible PCI configuration transaction cannot validate:

- physical lane impedance;
- receiver eye opening;
- connector loss;
- PCB return paths;
- equalization convergence;
- electromagnetic compatibility.

Those are separate evidence classes.

## Initialization and control-flow relevance in ChrisOS

There is no transmission-line initialization sequence in the current ChrisOS source reviewed for this chapter.

At the software boundary, a simplified PCI access is:

~~~text
caller selects BDF + config offset
        ↓
pci_read / pci_write
        ↓
x86 I/O-port transaction
        ↓
platform / root-complex abstraction
        ↓
device configuration state
~~~

The physical PCIe link, when real PCIe hardware is present, operates beneath that API.

The source inspected here does not expose the PHY state machine to ChrisOS.

## State and data structures

Transmission-line physics has continuous state distributed in space:

~~~text
V(x,t)
I(x,t)
electromagnetic field state
material polarization/loss state
~~~

A lumped software model might discretize that state into samples, sections or traveling-wave buffers.

Current ChrisOS does not define such a data structure in the files cited by this chapter.

The software state visible in pci.c is configuration transaction state: bus, slot, function, offset, address and returned register value. It must not be relabeled as physical-link state.

## Algorithms and complexity

For a uniform ideal line, evaluating closed-form quantities such as

~~~text
Z0
v_p
t_d
Γ
~~~

is constant-time arithmetic.

A sampled time-domain line model with (N) spatial or temporal samples requires at least O(N) storage for explicit waveform history unless a specialized compressed/recursive representation is used.

A general field solver has a different complexity class and depends on discretization, matrix sparsity, material model and solver choice.

A protocol driver's configuration-space loop cannot be used as evidence about electromagnetic-solver complexity.

## Memory ownership, ABI and wire-format boundary

The telegrapher equations do not have a kernel heap owner or ABI.

When software interacts with a real high-speed device, ownership applies to software-visible objects such as:

- MMIO or configuration registers;
- DMA rings;
- descriptors;
- interrupt state;
- firmware mailbox structures.

Those objects belong to higher layers.

Electrical symbols on a serial lane are a physical encoding governed by the interface specification, not a ChrisOS C ABI.

## Concurrency and timing

Multiple CPUs can concurrently access software data structures, but physical propagation is not a software thread.

A physical link evolves continuously according to electromagnetic dynamics and PHY state machines.

Software concurrency becomes relevant when a driver coordinates:

- device initialization;
- link-status changes;
- interrupts;
- DMA completion;
- reset and recovery.

None of those synchronization contracts should be invented in a foundation chapter unless current source establishes them.

## Privilege and security boundary

Characteristic impedance and reflection coefficient have no CPU privilege level.

Security enters at higher layers through device ownership, DMA isolation, protocol authentication and privilege checks.

Physical-layer fault injection or electromagnetic side channels are distinct security subjects. They require threat models and measurements not established by the present ChrisOS source evidence.

## Failure modes

| Failure or modeling error | Observable consequence |
|---|---|
| ZL differs materially from Z0 | reflection and ringing |
| source also mismatched | repeated re-reflections |
| edge time ignored | a nominally slow bus is analyzed incorrectly |
| reference-plane break | return-path discontinuity and extra loop inductance |
| pair asymmetry | differential/common-mode conversion |
| skew too large | reduced differential timing margin |
| connector/via discontinuity | localized reflection |
| long stub | notch/resonance behavior |
| conductor/dielectric loss ignored | edge and eye degradation underestimated |
| crosstalk ignored | victim noise/timing error |
| common-mode range ignored | differential receiver may fail despite valid Vdiff |
| protocol success treated as SI proof | physical margin remains unknown |
| emulator success treated as hardware proof | real channel remains unvalidated |

## Recovery and diagnostics

A pure physical channel does not "retry" on its own unless the surrounding protocol provides recovery.

System-level recovery can include:

- link retraining;
- lower negotiated rate;
- equalization retraining;
- packet replay;
- error-correcting code;
- device reset.

Whether a particular interface supports those mechanisms is defined by its standard and implementation.

ChrisOS configuration access alone does not establish which physical recovery path ran.

## Validation evidence

The deterministic checker associated with this chapter verifies:

~~~text
lossless line:
    Z0 = sqrt(L'/C')
    vp = 1/sqrt(L'C')
    td = length/vp

load reflection:
    Γ = (ZL-Z0)/(ZL+Z0)

matched load:
    Γ = 0

open:
    Γ = +1

short:
    Γ = -1

source launch:
    V+ = VS Z0/(ZS+Z0)

differential/common decomposition:
    Vdiff = Vp-Vn
    Vcm = (Vp+Vn)/2

VSWR:
    (1+|Γ|)/(1-|Γ|)
~~~

It also checks bilingual chapter anchors, reviewed revision and the exact ChrisOS source paths/symbol names cited in frontmatter.

These are equation and documentation checks. They are not oscilloscope, VNA, TDR, PCIe compliance or Ethernet compliance tests.

## Performance and trade-offs

Interconnect engineering is multiobjective.

Stronger termination can reduce reflection but consume power or reduce amplitude. Tighter differential coupling can improve field confinement but alter routing constraints and pair impedance. Faster edges reduce transition uncertainty at the receiver but increase high-frequency energy, crosstalk and EMI sensitivity. Equalization can recover lossy channels but consumes power and can amplify noise.

The correct physical design follows the target interface's channel budget and compliance model rather than maximizing one isolated metric.

## Current limitations

This chapter does not provide:

- a full Maxwell field derivation for arbitrary geometry;
- 2D/3D field-solver implementation;
- dielectric-material extraction;
- connector/package S-parameter models;
- PCIe or Ethernet compliance masks and fixtures;
- SerDes CDR mathematics in depth;
- adaptive-equalizer algorithms in depth;
- measured ChrisOS hardware channel data.

Those topics require specific geometry, standards, instrumentation or implementation evidence.

## Roadmap boundary

The conceptual progression is:

~~~text
inductance + capacitance
        ↓
distributed L' and C'
        ↓
traveling waves and Z0
        ↓
reflection / termination
        ↓
differential and common modes
        ↓
crosstalk / return path / discontinuities
        ↓
signal integrity and noise
        ↓
power-distribution and high-speed platform constraints
~~~

The next chapter develops noise, grounding and signal-integrity mechanisms around these transmission-line foundations.

This roadmap is documentation order, not a claim that ChrisOS will implement a field solver.

## Revision provenance

Reviewed against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

The implementation boundary was reconciled with kernel/metal/pci.c, kernel/metal/pci.h and docs/CURRENT_HARDWARE_AUDIT.md. The concrete symbols pci_read and pci_write were inspected as software-level PCI configuration primitives. No claim is made that they implement or expose PCI Express PHY equalization, board transmission lines or physical compliance state.

External standards context was checked against the PCI-SIG current Base-specification catalog and the IEEE 802.3 standards program. The equations in this chapter are general transmission-line relations; interface-specific electrical limits remain governed by the applicable specification revision and medium.
