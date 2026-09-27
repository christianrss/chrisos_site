#!/usr/bin/env python3
"""Deterministic checks for the electromagnetic-induction/transformer chapter.

Scope:
- Faraday scaling
- ideal transformer ratios
- reflected impedance
- sinusoidal volts-per-turn relation
- mutual inductance and passive coupling bound
- volt-second integration
- bilingual/revision anchors

These checks validate documented equations and editorial contracts. They do not
validate a physical transformer, insulation system, thermal design, EMI
compliance, or ChrisOS hardware behavior.
"""

from __future__ import annotations

import math
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_faraday_scaling() -> None:
    # Same dPhi/dt, different turn count: induced voltage scales linearly with N.
    dphi_dt = 2.5e-3
    e_20 = -20.0 * dphi_dt
    e_80 = -80.0 * dphi_dt
    assert approx(e_20, -0.05)
    assert approx(e_80, -0.20)
    assert approx(e_80 / e_20, 4.0)


def check_ideal_transformer() -> None:
    n1 = 500.0
    n2 = 100.0
    a = n1 / n2
    v1 = 230.0
    v2 = v1 / a
    i2 = 4.0
    i1 = i2 / a

    assert approx(a, 5.0)
    assert approx(v2, 46.0)
    assert approx(i1, 0.8)

    # Ideal apparent-power magnitude is preserved.
    assert approx(v1 * i1, v2 * i2)


def check_reflected_impedance() -> None:
    a = 10.0
    z_load = 8.0
    z_in = a * a * z_load
    assert approx(z_in, 800.0)


def check_sinusoidal_volts_per_turn() -> None:
    f = 60.0
    turns = 1000.0
    phi_peak = 1.0e-3
    vrms = (2.0 * math.pi / math.sqrt(2.0)) * f * turns * phi_peak
    assert approx(vrms, 266.572976289502)

    # Equivalent 4.44 engineering approximation stays close to the exact factor.
    approx_vrms = 4.44 * f * turns * phi_peak
    assert abs(approx_vrms - vrms) / vrms < 0.001


def check_mutual_inductance() -> None:
    l1 = 100e-3
    l2 = 25e-3
    k = 0.8
    m = k * math.sqrt(l1 * l2)

    assert approx(m, 0.04)
    assert 0.0 <= abs(k) <= 1.0

    # Passive two-winding inductance matrix requires M^2 <= L1*L2.
    assert m * m <= l1 * l2 + 1e-15


def check_volt_seconds() -> None:
    # Constant applied winding voltage over a finite interval.
    voltage = 12.0
    duration = 100e-6
    turns = 20.0
    delta_phi = voltage * duration / turns

    assert approx(delta_phi, 60e-6)

    # Equal positive/negative volt-seconds reset ideal flux over one cycle.
    positive = 12.0 * 100e-6
    negative = -12.0 * 100e-6
    assert approx((positive + negative) / turns, 0.0)


def check_documents() -> None:
    root = Path(__file__).resolve().parents[1]
    filename = "electromagnetic-induction-transformers.md"

    required_common = (
        "M = k sqrt(L1 L2)",
        "Z_in",
        "4.44288",
        "ΔΦ = (1/N)",
        "ChrisOS",
        "C57.12.80-2024",
        "C57.12.00-2021",
        "BIPM",
    )

    paths = {
        "en": root / "docs" / "en" / "01-foundations" / filename,
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / filename,
    }

    texts = {}
    for lang, path in paths.items():
        text = path.read_text(encoding="utf-8")
        texts[lang] = text
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in required_common:
            if anchor not in text:
                raise AssertionError(f"{path}: missing {anchor!r}")

        if "sources: []" not in text or "symbols: []" not in text:
            raise AssertionError(f"{path}: foundation chapter must preserve empty source/symbol boundary")

    # Technical-equivalence guardrails: both editions carry the same core equations.
    equations = (
        "Φ_B = ∫_S B · dA",
        "e = - dΦ_B/dt",
        "V1 / V2 = N1 / N2 = a",
        "I1 / I2 = N2 / N1 = 1/a",
        "V_rms = (2π/sqrt(2)) f N Φ_peak",
        "i_C = C_ps dv_common/dt",
        "W = 1/2 L1 i1² + M i1 i2 + 1/2 L2 i2²",
    )
    for equation in equations:
        for lang, text in texts.items():
            if equation not in text:
                raise AssertionError(f"{lang}: missing shared technical equation {equation!r}")


def main() -> None:
    check_faraday_scaling()
    check_ideal_transformer()
    check_reflected_impedance()
    check_sinusoidal_volts_per_turn()
    check_mutual_inductance()
    check_volt_seconds()
    check_documents()
    print(
        "induction/transformer examples passed: Faraday scaling, turns/current ratios, "
        "reflected impedance, sinusoidal volts-per-turn, mutual inductance, "
        "volt-seconds and bilingual revision anchors"
    )
    print(
        "scope: deterministic teaching checks only; no physical transformer, "
        "insulation, thermal, EMI or ChrisOS-hardware validation claim"
    )


if __name__ == "__main__":
    main()
