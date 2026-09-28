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
  - docs/CURRENT_HARDWARE_AUDIT.md
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
V_L=Lrac{di}{dt}
]

shows why small shared inductance produces transient voltage during fast switching. For shared return impedance (Z_g),

[
V_{shift}(omega)=Z_g(omega)sum_k I_k(omega).
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
i_C=C_mrac{dV_a}{dt},qquad V_M=Mrac{dI_a}{dt}.
]

Faster edges increase both terms. Signal-integrity bandwidth is governed strongly by rise/fall time, not only by bit frequency. Exact PCB crosstalk requires geometry-derived or measured parameters; driver source cannot supply them.

## Reflections, timing and the eye

For characteristic impedance (Z_0) and load (Z_L),

[
Gamma_L=rac{Z_L-Z_0}{Z_L+Z_0}.
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
Delta Vapprox L_sNrac{Delta I}{Delta t}.
]

Package and power-distribution inductance therefore matter even for modest individual currents. Decoupling supplies local transient charge but is limited by ESR, ESL, placement and plane impedance.

For pair voltages,

[
V_d=V_p-V_n,qquad V_{cm}=rac{V_p+V_n}{2}.
]

Real receivers have finite common-mode rejection and an allowed common-mode range. Skew, unequal loss, asymmetric vias and return discontinuities convert differential energy to common mode; pair matching preserves mode balance and timing.

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
