#!/usr/bin/env python3
"""Executable arithmetic and document checks for voltage-current-resistance-power.

These checks validate deterministic teaching examples and bilingual document
anchors. They are not circuit simulation, device characterization, safety
certification, or electrical-hardware conformance tests.
"""

from __future__ import annotations

from pathlib import Path

E_CHARGE = 1.602176634e-19


def approx(a: float, b: float, rel: float = 1e-12) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= rel * scale


def main() -> None:
    # Constant current: Q = I t.
    current = 2.5
    duration = 4.0
    charge = current * duration
    assert charge == 10.0

    # One ampere corresponds to this many elementary charges per second.
    charges_per_second = 1.0 / E_CHARGE
    assert abs(charges_per_second - 6.241509074460763e18) / charges_per_second < 1e-12

    # Linear resistor operating point.
    voltage = 5.0
    current = 0.25
    resistance = voltage / current
    assert resistance == 20.0

    # Uniform conductor: R = rho L / A.
    rho = 1.68e-8
    length = 2.0
    area = 1.0e-6
    conductor_r = rho * length / area
    assert approx(conductor_r, 0.0336)

    # Power identities for the same positive linear resistor.
    power_vi = voltage * current
    power_i2r = current * current * resistance
    power_v2r = voltage * voltage / resistance
    assert approx(power_vi, 1.25)
    assert approx(power_vi, power_i2r)
    assert approx(power_vi, power_v2r)

    # Constant power integrated over time.
    power = 100.0
    seconds = 10.0
    energy = power * seconds
    assert energy == 1000.0

    # Passive-sign convention: negative p means delivery for the chosen
    # current-entering-positive-terminal orientation.
    source_v = 12.0
    source_i = -2.0
    source_p = source_v * source_i
    assert source_p == -24.0

    root = Path(__file__).resolve().parents[1]
    for lang in ("en", "pt-br"):
        chapter = (
            root
            / "docs"
            / lang
            / "01-foundations"
            / "voltage-current-resistance-power.md"
        )
        text = chapter.read_text(encoding="utf-8")
        for needle in (
            "voltage-current-resistance-power",
            "da3df29cb397932c43d32373871fb9380e688ade",
            "1.602176634",
            "R = ρ L / A",
            "p(t) = v(t) i(t)",
            "P = V I",
            "ChrisOS",
            "BIPM",
        ):
            if needle not in text:
                raise AssertionError(f"{chapter}: missing {needle!r}")

    print(
        "voltage/current/resistance/power examples passed: Q=It, elementary "
        "charge rate, R=V/I, rho*L/A, P=VI=I^2R=V^2/R, E=Pt and power sign"
    )
    print(
        "scope: deterministic documentation arithmetic only; no SPICE, device, "
        "safety or hardware-conformance claim"
    )


if __name__ == "__main__":
    main()
