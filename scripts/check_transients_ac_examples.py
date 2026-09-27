#!/usr/bin/env python3
"""Deterministic teaching checks for transient and AC foundation chapters.

Scope:
- rc-rlc-transients
- ac-signals-frequency-impedance

These checks validate documented equations and bilingual anchors. They are not
SPICE, RF calibration, hardware waveform validation, or electromagnetic field
simulation.
"""

from __future__ import annotations

import cmath
import math
from pathlib import Path


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def capprox(a: complex, b: complex, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_transients() -> None:
    # RC charging from 0 V toward 10 V with R=1k, C=100uF.
    r = 1000.0
    c = 100e-6
    tau = r * c
    assert approx(tau, 0.1)

    vs = 10.0
    t = tau
    vc = vs * (1.0 - math.exp(-t / tau))
    assert approx(vc, vs * (1.0 - math.exp(-1.0)))
    assert approx((vs - vc) / vs, math.exp(-1.0))

    # RC discharge and stored energy exponent.
    v0 = 8.0
    t = 2.0 * tau
    v = v0 * math.exp(-t / tau)
    energy_ratio = (v / v0) ** 2
    assert approx(v / v0, math.exp(-2.0))
    assert approx(energy_ratio, math.exp(-4.0))

    # Five time constants are close to final, not exact.
    remaining_5tau = math.exp(-5.0)
    assert approx(remaining_5tau, 0.006737946999085467)
    assert remaining_5tau > 0.0

    # RL energization.
    l = 0.2
    r_rl = 20.0
    tau_rl = l / r_rl
    assert approx(tau_rl, 0.01)
    i_final = 12.0 / r_rl
    i_at_tau = i_final * (1.0 - math.exp(-1.0))
    assert approx(i_at_tau / i_final, 1.0 - math.exp(-1.0))

    # Continuity invariants: state is explicitly preserved at switching.
    vc_before = 3.25
    il_before = -0.4
    vc_after = vc_before
    il_after = il_before
    assert vc_after == vc_before
    assert il_after == il_before

    # RLC damping classification.
    l_rlc = 10e-3
    c_rlc = 1e-6
    omega0 = 1.0 / math.sqrt(l_rlc * c_rlc)

    r_under = 50.0
    alpha_under = r_under / (2.0 * l_rlc)
    zeta_under = alpha_under / omega0
    assert 0.0 < zeta_under < 1.0
    omega_d = math.sqrt(omega0**2 - alpha_under**2)
    assert omega_d < omega0

    r_critical = 2.0 * math.sqrt(l_rlc / c_rlc)
    alpha_critical = r_critical / (2.0 * l_rlc)
    assert approx(alpha_critical, omega0)

    r_over = 400.0
    alpha_over = r_over / (2.0 * l_rlc)
    assert alpha_over > omega0

    # Canonical second-order overshoot at zeta=0.5.
    zeta = 0.5
    overshoot = math.exp(-zeta * math.pi / math.sqrt(1.0 - zeta * zeta))
    assert approx(overshoot, 0.16303353482158048)

    # Passive source-free series RLC energy derivative is -R i^2.
    current = 0.3
    r_loss = 10.0
    d_energy_dt = -r_loss * current**2
    assert d_energy_dt < 0.0
    assert approx(d_energy_dt, -0.9)

    # Explicit Euler for x'=-x/tau: dt > 2*tau is unstable in magnitude.
    dt = 2.5 * tau
    amplification = 1.0 - dt / tau
    assert abs(amplification) > 1.0


def check_ac() -> None:
    # Frequency, period and angular frequency.
    f = 1000.0
    period = 1.0 / f
    omega = 2.0 * math.pi * f
    assert approx(period, 1e-3)
    assert approx(omega, 2000.0 * math.pi)

    # Peak, p-p and RMS for a sinusoid.
    v_peak = 10.0
    v_pp = 2.0 * v_peak
    v_rms = v_peak / math.sqrt(2.0)
    assert approx(v_pp, 20.0)
    assert approx(v_rms, 7.0710678118654755)

    # Phase/time conversion: 90 degrees at 1 kHz is 250 us.
    phase = math.pi / 2.0
    dt = phase / omega
    assert approx(dt, 250e-6)

    # Element impedances at 1 kHz.
    r = 100.0
    l = 10e-3
    c = 1e-6
    z_r = complex(r, 0.0)
    z_l = 1j * omega * l
    z_c = 1.0 / (1j * omega * c)
    assert capprox(z_r, 100.0 + 0j)
    assert approx(z_l.real, 0.0)
    assert z_l.imag > 0.0
    assert approx(z_c.real, 0.0)
    assert z_c.imag < 0.0

    # Series RLC resonance.
    l_r = 10e-3
    c_r = 1e-6
    omega0 = 1.0 / math.sqrt(l_r * c_r)
    z_series = 25.0 + 1j * (omega0 * l_r - 1.0 / (omega0 * c_r))
    assert approx(z_series.imag, 0.0, abs_tol=1e-9)
    assert approx(abs(z_series), 25.0)

    # RC low-pass/high-pass at cutoff omega=1/RC.
    r_f = 1000.0
    c_f = 1e-6
    omega_c = 1.0 / (r_f * c_f)
    x = omega_c * r_f * c_f
    h_lp = 1.0 / (1.0 + 1j * x)
    h_hp = (1j * x) / (1.0 + 1j * x)
    target = 1.0 / math.sqrt(2.0)
    assert approx(abs(h_lp), target)
    assert approx(cmath.phase(h_lp), -math.pi / 4.0)
    assert approx(abs(h_hp), target)
    assert approx(cmath.phase(h_hp), math.pi / 4.0)

    # -3.0103 dB at 1/sqrt(2) amplitude.
    db = 20.0 * math.log10(target)
    assert approx(db, -3.010299956639812)

    # Real/reactive/apparent power for 120 Vrms, 10 Arms, lagging by 60°.
    v = 120.0
    i = 10.0
    phi = math.radians(60.0)
    p = v * i * math.cos(phi)
    q = v * i * math.sin(phi)
    s_abs = v * i
    pf = p / s_abs
    assert approx(p, 600.0)
    assert approx(q, 1039.2304845413264)
    assert approx(s_abs, 1200.0)
    assert approx(pf, 0.5)

    # Time/frequency duality for first-order RC.
    tau = r_f * c_f
    assert approx(omega_c, 1.0 / tau)

    # Small complex nodal example: source Vs through R feeding C to ground.
    # Vout = Vs * Zc/(R+Zc), equivalent to low-pass formula.
    vs = 1.0 + 0j
    zc = 1.0 / (1j * omega_c * c_f)
    vout_divider = vs * zc / (r_f + zc)
    assert capprox(vout_divider, h_lp)

    # Rectangular/polar consistency and quadrant-safe phase.
    z = complex(-1.0, 1.0)
    assert approx(abs(z), math.sqrt(2.0))
    assert approx(cmath.phase(z), 3.0 * math.pi / 4.0)


def check_documents() -> None:
    root = Path(__file__).resolve().parents[1]
    revision = "da3df29cb397932c43d32373871fb9380e688ade"

    required = {
        "rc-rlc-transients.md": (
            "τ = RC",
            "τ = L/R",
            "ω_0 = 1/sqrt(LC)",
            "ζ = α/ω_0",
            "ChrisOS",
        ),
        "ac-signals-frequency-impedance.md": (
            "ω = 2πf",
            "V_rms = V_m / sqrt(2)",
            "Z_L = jωL",
            "Z_C",
            "S = V I*",
            "BIPM",
            "ChrisOS",
        ),
    }

    for lang in ("en", "pt-br"):
        for filename, anchors in required.items():
            path = root / "docs" / lang / "01-foundations" / filename
            text = path.read_text(encoding="utf-8")
            if revision not in text:
                raise AssertionError(f"{path}: missing reviewed revision")
            for anchor in anchors:
                if anchor not in text:
                    raise AssertionError(f"{path}: missing {anchor!r}")


def main() -> None:
    check_transients()
    check_ac()
    check_documents()
    print(
        "transient/AC examples passed: RC/RL time constants, RLC damping, "
        "energy, Euler stability, RMS, phase, impedance, resonance, filters, "
        "decibels and complex power"
    )
    print(
        "scope: deterministic teaching checks only; no SPICE, calibrated RF "
        "measurement, hardware waveform or electromagnetic-conformance claim"
    )


if __name__ == "__main__":
    main()
