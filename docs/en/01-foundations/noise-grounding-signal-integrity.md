---
id: noise-grounding-signal-integrity
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/pci.h
symbols: [pci_read, pci_write]
depends_on: [transmission-lines-differential-signals, ac-signals-frequency-impedance]
related: [power-delivery-regulation, clock-timing, buses-mmio-dma, pci-pcie]
---

# Noise, grounding and signal integrity

<div class="abstract">
Digital logic is physically analog: receivers decide logical state from voltages with finite rise time, delay, noise and reference uncertainty. Signal integrity preserves voltage and timing margin from transmitter through interconnect and return path to receiver. This chapter develops noise margins, return-current geometry, crosstalk, reflections, jitter and simultaneous-switching noise, then fixes the ChrisOS boundary: current PCI software performs configuration-space I/O and does not implement or validate board-level electrical signaling.
</div>

## Prerequisites and scope

Required foundations are voltage, current, impedance, capacitance, inductance, edge spectra, transmission lines and differential signaling. Ground is not an everywhere-zero abstraction: real conductors have impedance, so two points called ground can have different instantaneous potentials. Signal integrity asks whether a waveform remains decodable with sufficient voltage and timing margin under transmitter, package, board, connector, return-path, receiver and neighboring activity. Power integrity is coupled because supply/reference motion changes effective thresholds.

## Logic levels and margins

For guaranteed transmitter levels and receiver thresholds,

[
NM_H=V_{OH(min)}-V_{IH(min)},qquad NM_L=V_{IL(max)}-V_{OL(max)}.
]

Positive static margin is necessary, not sufficient. A glitch can cross a threshold; an edge can violate setup or hold time; reference motion can move the threshold itself.

| Margin | Meaning | Exhaustion |
|---|---|---|
| voltage | output-to-threshold distance | wrong logical state |
| setup/hold | stable interval around sampling | capture error or metastability |
| slew | acceptable edge-rate range | timing uncertainty, EMI, crosstalk |
| reference | tolerance to supply/ground motion | threshold moves relative to signal |

The receiver observes the signal relative to its local reference at the sampling instant.

## Ground and return current

Kirchhoff's current law requires a return path. At low frequency current distribution is strongly resistive; at higher frequency inductive impedance matters and return current concentrates near the signal path over a continuous reference plane, reducing loop inductance.

[
V_L = L · di/dt
]

shows why small shared inductance produces transient voltage during fast switching. For shared return impedance (Z_g),

[
V_shift(ω) = Z_g(ω) · Σ I_k(ω).
]

This is ground bounce. Control comes from current geometry, low-impedance references, adequate power/ground connections and decoupling, not from the schematic ground symbol. A plane split can force return current to detour, enlarging loop area, inductance, radiation and susceptibility. Differential pairs reduce common-mode sensitivity but still need a controlled return environment because imbalance creates common-mode current.

## Coupling mechanisms

| Mechanism | First-order model | Typical control |
|---|---|---|
| common impedance | shared R or Z | reduce shared path impedance |
| capacitive | mutual capacitance | spacing, reference plane, edge control |
| inductive | mutual inductance | reduce loop area, preserve return path |
| radiated | electromagnetic field | geometry, shielding, filtering |
| supply/reference | PDN impedance times transient current | decoupling, low-inductance delivery |
| reflection | impedance discontinuity | controlled impedance, termination |

For an aggressor,

[
i_C = C_m · dV_a/dt,    V_M = M · dI_a/dt.
]

Faster edges increase both terms. Signal-integrity bandwidth is governed strongly by rise/fall time, not only by bit frequency. Exact PCB crosstalk requires geometry-derived or measured parameters; driver source cannot supply them.

## Reflections, timing and the eye

For characteristic impedance (Z_0) and load (Z_L),

[
Γ_L = (Z_L - Z_0) / (Z_L + Z_0).
]

An open approaches +1, a short -1, and a matched load 0. Reflections create overshoot, undershoot, ringing and repeated threshold crossings. Series, parallel and differential termination trade power, topology and waveform shape; the interface specification determines the valid strategy.

Jitter is transition-time variation relative to an ideal reference. Inter-symbol interference occurs when channel response to previous symbols alters the present symbol. An eye diagram overlays unit intervals: vertical opening approximates voltage margin and horizontal opening timing margin.

~~~text
amplitude
 ^       \      /
 | \      \____/      /
 |  \     /    \     /
-+---\---/------\---/---- threshold
 |    \_/        \_/
 +-----------------------> time
           < eye >
~~~

An eye is diagnostic, not automatically a compliance result: standards define measurement points, masks, fixtures and equalization.

## Simultaneous switching and differential mode

If N outputs each change current by delta-I over delta-t through shared inductance (L_s),

[
ΔV ≈ L_s · N · ΔI/Δt.
]

Package and power-distribution inductance therefore matter even for modest individual currents. Decoupling supplies local transient charge but is limited by ESR, ESL, placement and plane impedance.

For pair voltages,

[
V_d = V_p - V_n,    V_cm = (V_p + V_n)/2.
]

Real receivers have finite common-mode rejection and an allowed common-mode range. Skew, unequal loss, asymmetric vias and return discontinuities convert differential energy to common mode; pair matching preserves mode balance and timing.

## Signal and disturbance model

A useful receiver-local model is

~~~text
V_observed(t)
=
V_intended(t)
+
V_coupled(t)
+
V_supply_error(t)
-
V_reference_error(t)
~~~

The terms are not necessarily statistically independent. For example, an output transition can simultaneously create crosstalk on a neighboring line and move the local ground through shared package inductance.

Disturbances can be classified as:

- deterministic, such as periodic switching or data-dependent interference;
- random, such as thermal/device noise;
- common-mode;
- differential-mode;
- conducted through shared impedance;
- capacitively or inductively coupled;
- radiated;
- generated by the power-distribution network.

The useful engineering quantity is remaining margin after the disturbances are combined under the interface's measurement model. Merely measuring a nonzero noise voltage does not establish failure.

## Static versus dynamic margin

Static noise margin answers a DC question. High-speed correctness adds a sampling-time dimension.

A receiver can fail despite valid final voltage when:

- the edge arrives after the setup deadline;
- ringing crosses the threshold more than once;
- the local reference moves during the aperture;
- the transition is slow enough to increase timing uncertainty;
- previous symbols leave residual channel response.

Therefore digital robustness is better represented conceptually as:

~~~text
usable decision region
=
voltage margin
×
timing margin
~~~

An eye diagram is one visualization of this two-dimensional decision region.

## Edge rate and relevant bandwidth

Clock frequency and bit rate do not by themselves define signal-integrity bandwidth.

A fast transition contains spectral components well above the repetition frequency. A generic first-order scale is:

~~~text
relevant bandwidth ∝ 1 / rise_time
~~~

The coefficient depends on the waveform model and the definition of rise time, so no universal coefficient is asserted here.

The physical consequence is robust:

~~~text
faster edge
    ↓
more high-frequency content
    ↓
greater sensitivity to discontinuity, loss, crosstalk and radiation
~~~

Slowing an edge can improve integrity when the receiver's slew and timing constraints still remain satisfied. Excessively slow edges can instead consume timing margin or violate an interface's input requirements.

## Common-impedance coupling

Two circuits can couple even when their signal traces are not adjacent.

If they share return impedance Z_s, current from circuit A creates a reference error seen by circuit B:

~~~text
V_error,B(ω) = Z_s(ω) · I_A(ω)
~~~

Common examples are:

- shared package ground pins;
- narrow plane necks;
- connector return pins;
- long shared traces;
- cable shield connections;
- shared power-distribution paths.

Reducing the shared impedance or separating current paths can reduce this mechanism.

## Grounding strategy depends on frequency and geometry

A star connection can be useful for preventing low-frequency shared current from flowing through a sensitive reference.

A continuous reference plane is often superior at high frequency because it creates a short, distributed return path with low loop inductance.

These are not contradictory rules. They apply to different field/current regimes.

The design objective is:

~~~text
control the actual return-current path
and minimize harmful shared impedance
~~~

rather than drawing a particular ground symbol pattern.

## Decoupling impedance and signal integrity

Supply/reference motion couples directly into signal quality.

For an ideal capacitor:

~~~text
Z_C = 1 / (jωC)
~~~

A practical decoupling capacitor is better approximated over a useful band by:

~~~text
Z_dec(ω)
=
ESR
+
jω·ESL
+
1/(jωC)
~~~

where ESR is equivalent series resistance and ESL represents effective series/mounting inductance.

Below self-resonance, the capacitive term can dominate. Above self-resonance, inductance can dominate.

This means nominal capacitance alone is insufficient. Placement, mounting geometry, plane inductance and capacitor distribution affect the current loop.

The next chapter develops the PDN and regulation problem directly.

## Differential balance and common-mode conversion

For pair voltages:

~~~text
V_diff = V_p - V_n

V_cm = (V_p + V_n) / 2
~~~

A perfectly symmetric channel preserves modal separation.

Real asymmetries include:

- pair skew;
- unequal loss;
- asymmetric vias;
- connector imbalance;
- unequal ESD/filter structures;
- reference-plane changes.

They can convert energy:

~~~text
differential -> common mode
common mode  -> differential
~~~

Common-mode conversion matters because it can reduce receiver margin and increase electromagnetic emissions even when the nominal differential amplitude looks acceptable.

## Common-mode rejection

A conceptual common-mode rejection ratio is:

~~~text
CMRR = |A_diff / A_cm|
~~~

and is often expressed as:

~~~text
CMRR_dB = 20 log10(CMRR)
~~~

CMRR is frequency-dependent.

A receiver can reject low-frequency common-mode disturbance strongly while performing significantly worse at high frequency.

The allowed common-mode input range is also finite. A large common-mode excursion can cause failure even if the differential voltage is otherwise valid.

## Jitter and timing uncertainty

Jitter is variation in transition time relative to an ideal or recovered reference.

Useful measurement models often distinguish:

- deterministic jitter;
- random jitter;
- data-dependent jitter;
- periodic jitter;
- duty-cycle distortion.

These categories are analysis models, not independent physical laws.

At the sampling point, the important result is how much horizontal timing margin remains after all timing uncertainty is accounted for.

## Inter-symbol interference

A bandwidth-limited channel has memory.

The response to earlier bits can remain present during the current symbol:

~~~text
sample_now
=
response(current symbol)
+
Σ residual response(previous symbols)
+
noise
~~~

This is inter-symbol interference (ISI).

Contributors include:

- dielectric/conductor loss;
- reflection;
- dispersion;
- filtering;
- insufficient equalization.

ISI can shift both voltage and threshold-crossing time.

## Bit-error rate and evidence

Bit-error rate is:

~~~text
BER = erroneous_bits / observed_bits
~~~

A zero-error test run does not prove a true BER of zero.

Confidence depends on observation length and the assumed statistical model.

Likewise:

~~~text
one successful boot
!=
physical channel qualification
~~~

Electrical qualification needs the interface-specific compliance and measurement procedure.

## Shielding and chassis return

A cable shield or enclosure adds another conductive structure that can carry common-mode current.

Shield performance depends on:

- bond impedance;
- connector geometry;
- continuity;
- apertures;
- termination method;
- frequency.

A long pigtail connection can have enough inductance to be ineffective at frequencies where a broad low-inductance bond would work better.

The phrase "connected to ground" is therefore incomplete without geometry and frequency.

## Signal integrity and EMC

Signal integrity and electromagnetic compatibility are related but distinct.

Signal integrity asks whether the intended receiver obtains a valid waveform.

EMC asks whether the system emits and tolerates disturbances within required limits.

A fast edge can simultaneously:

- improve transition time;
- increase high-frequency loss sensitivity;
- increase crosstalk;
- increase reflection sensitivity;
- increase conducted/radiated emissions.

Good physical design can improve both, but EMC compliance requires the applicable regulatory/product test.

## Sampling and metastability boundary

Signal-integrity degradation can place a receiver input close to its threshold during the sampling aperture.

In synchronous logic that can consume setup/hold margin and increase the chance that a storage element enters metastability.

The conceptual chain is:

~~~text
channel voltage/timing uncertainty
        ↓
setup/hold margin
        ↓
sampling element
        ↓
possible metastability
        ↓
synchronizer/system containment
~~~

The internal metastability behavior belongs to the sequential-logic and timing chapters. This chapter supplies the channel-side causes.

## Standards context

The BIPM SI Brochure, 9th edition version 4.01 revised in June 2026, is the current metrological reference for the SI quantities and units used here.

PCI-SIG lists PCI Express Base Specification Revision 7.1, dated 2026-09-17, as the current approved Base specification. PCI-SIG describes the Base specification as including electrical, protocol, platform-architecture and programming-interface elements. That separation is directly relevant: software access to configuration space does not imply software ownership of the electrical channel.

IEEE 802.3-2022 remains an approved IEEE Ethernet standard while active amendment and revision projects continue. It spans MAC behavior, management information and multiple physical-layer media and speeds.

This chapter uses these standards only to establish architectural boundaries. Interface-specific insertion-loss budgets, eye masks, jitter limits, receiver equalization and compliance fixtures remain governed by the applicable specification revision and medium.

## Initialization and control-flow boundary

There is no signal-integrity initialization routine in the reviewed ChrisOS source.

The relevant software control flow is:

~~~text
caller requests PCI configuration value
        ↓
bus / slot / function / offset encoded
        ↓
pci_read or pci_write
        ↓
x86 I/O-port access
        ↓
platform/controller behavior
        ↓
physical link if real hardware is present
~~~

Any serializer, clock/data recovery, lane equalizer or analog termination belongs below the current software interface.

## State and data structures

The cited source stores no:

- channel impulse response;
- eye histogram;
- sampled waveform;
- S-parameter matrix;
- equalizer state;
- impedance profile.

The visible PCI values are scalar software transaction state:

~~~text
bus
slot
function
offset
configuration address
configuration value
~~~

The invariant is:

~~~text
configuration state != physical channel state
~~~

## ABI and wire-format boundary

The reviewed kernel declarations are conceptually:

~~~text
pci_read(bus, slot, func, off) -> 32-bit configuration value

pci_write(bus, slot, func, off, value)
~~~

They form a software interface for PCI configuration access.

The electrical encoding of a physical serial link is governed by the physical/link specification, not by this C-level API.

Likewise, no waveform sample format or signal-integrity telemetry ABI exists in the cited ChrisOS files.

## Concurrency boundary

The reviewed pci_read and pci_write functions perform direct I/O-port accesses and contain no lock internally.

This chapter does not infer a global serialization guarantee from absence of a local lock.

If multiple CPUs can issue configuration operations concurrently, the PCI subsystem documentation must establish the real ordering/serialization contract from explicit source evidence.

That software concurrency question is separate from the electromagnetic channel.

## Diagnostic hierarchy

Electrical faults and software faults can produce similar external symptoms.

A disciplined investigation moves through evidence layers:

~~~text
software invariant / return code
        ↓
controller and link state
        ↓
protocol counters or analyzer
        ↓
electrical measurement
        ↓
package / connector / PCB cause
~~~

Jumping directly from a timeout to "bad signal integrity" is not justified.

## Physical/software boundary

~~~text
driver request
    |
configuration/register transaction
    |
controller and link protocol
    |
PHY
    |
package + channel + return path
    |
receiver
~~~

Only the upper software-visible part is represented by the current ChrisOS PCI code reviewed here.

## Current ChrisOS implementation

At revision `da3df29cb397932c43d32373871fb9380e688ade`, `kernel/metal/pci.c` builds a legacy PCI configuration address, writes it to I/O port `0xCF8`, and transfers a 32-bit value through `0xCFC`. Thus `pci_read` and `pci_write` are software transactions at the configuration-mechanism boundary.

The same source scans bus 0 for selected devices and enables I/O-space and bus-master command bits where applicable. It does not configure transmitter swing, receiver equalization, termination, lane training, PCB impedance, connector loss or reference-plane geometry. The hardware audit states that no physical machine was booted in that audit and provides no TDR, oscilloscope, BER or eye-diagram evidence.

| Source | Evidence used |
|---|---|
| `kernel/metal/pci.c` | configuration I/O and selected-device scans |
| `kernel/metal/pci.h` | exported PCI configuration interface |
| `docs/CURRENT_HARDWARE_AUDIT.md` | validation status and absence of physical proof |

## Algorithms, state, ownership and complexity

ChrisOS has no signal-integrity algorithm or kernel-owned electrical-channel state. The nearby software algorithm is bounded PCI discovery: bus 0, up to 32 slots and 8 functions, with configuration reads. Generalized enumeration is O(BSF) for buses, slots and functions. Electrical propagation instead follows distributed network dynamics and has no heap ownership or lock ordering in ChrisOS.

This separation is an invariant: a software-visible transaction must never be presented as evidence that the underlying electrical channel is compliant.

## Failure, recovery and fault isolation

Electrical defects may appear as retries, device disappearance, timeouts, corrupted traffic or link-down state. Those symptoms are not specific: protocol, firmware, controller or driver defects can look similar.

~~~text
software invariant/test
        |
controller/link status
        |
protocol counters/analyzer
        |
electrical measurement
        |
channel/package/board cause
~~~

TDR, high-bandwidth probing, eye analysis and bit-error-rate testing belong to hardware validation. Their absence must be stated rather than replaced by inference. Recovery is interface-specific: software may retry or reset a controller, but that cannot repair an out-of-spec physical channel.

## Security, performance and trade-offs

A privileged driver must validate device-visible lengths, descriptors and state even when the physical channel is assumed reliable; unstable input can otherwise amplify into a kernel fault. Software validation does not replace electrical compliance.

Faster edges reduce transition time but broaden spectral content and can increase crosstalk, reflection sensitivity and emissions. Termination can improve waveforms while consuming power. Spacing and continuous reference planes consume routing resources. Equalization can recover lossy channels at the cost of complexity, latency and power.

## Validation evidence and limitations

A physical platform should combine schematic/layout review, impedance verification, PDN analysis, simulation where justified, measurements at specified points, protocol/link counters, environmental margin testing and software fault isolation. For this revision, only the declared ChrisOS source and audit evidence were inspected; no new physical-hardware measurement was executed.

ChrisOS does not currently expose a signal-integrity measurement subsystem, model PCB channels, perform PCIe PHY training in software, or provide physical compliance evidence in the reviewed audit. The current PCI code is legacy configuration-I/O plus selected-device discovery. This chapter is not a claim of PCI/PCIe electrical compliance.

## Roadmap

Future hardware profiles can bind motherboard identity, negotiated link state, error counters and measured compliance artifacts to reproducible validation records. Native PCIe AER or richer link telemetry, if implemented later, would improve diagnosis but still would not replace board-level measurement.

## Revision provenance

Implementation claims were reconciled against ChrisOS `main` revision `da3df29cb397932c43d32373871fb9380e688ade`; the reviewed files are exactly those declared in frontmatter. Theory and repository-observed behavior remain explicitly separated.
