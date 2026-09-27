#!/usr/bin/env python3
"""Numerical and curriculum checks for electric-charge-field-potential."""

from __future__ import annotations

import math
from pathlib import Path

E_CHARGE = 1.602176634e-19
EPS0 = 8.8541878128e-12
K_E = 1.0 / (4.0 * math.pi * EPS0)


def approx(a: float, b: float, rel: float = 1e-10) -> bool:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) <= rel * scale


def main() -> None:
    charges_per_coulomb = 1.0 / E_CHARGE
    assert abs(charges_per_coulomb - 6.241509074460763e18) / charges_per_coulomb < 1e-12

    # Two +1 nC point charges separated by 0.1 m in vacuum.
    q = 1e-9
    r = 0.1
    force = K_E * q * q / (r * r)
    assert abs(force - 8.9875517923e-7) / force < 2e-10

    # One elementary charge crossing 1 V has one electronvolt of energy.
    one_ev_joules = E_CHARGE * 1.0
    assert one_ev_joules == E_CHARGE

    # Uniform-field relation: delta V = -E delta x.
    field = 1000.0
    distance = 0.002
    delta_v = -field * distance
    assert delta_v == -2.0

    # Energy-per-charge and power identities used by the text.
    charge = 3.0
    voltage = 2.0
    energy = charge * voltage
    assert energy == 6.0
    current = 0.5
    power = voltage * current
    assert power == 1.0

    root = Path(__file__).resolve().parents[1]
    curriculum = (root / "data/curriculum.yml").read_text(encoding="utf-8")
    required_order = [
        "atom-semiconductor",
        "electric-charge-field-potential",
        "voltage-current-resistance-power",
        "ohm-kirchhoff-circuits",
        "capacitance-inductance",
        "rc-rlc-transients",
        "ac-signals-frequency-impedance",
        "electromagnetic-induction-transformers",
        "transmission-lines-differential-signals",
        "noise-grounding-signal-integrity",
        "power-delivery-regulation",
        "crystal-bands-doping",
        "pn-junction",
        "mos-capacitor",
        "transistor-cmos",
        "cmos-switching-power",
        "logic-levels-noise-margins",
    ]
    positions = [curriculum.index(f"- {chapter}") for chapter in required_order]
    assert positions == sorted(positions), "electrical foundation curriculum order drifted"

    for lang in ("en", "pt-br"):
        chapter = root / "docs" / lang / "01-foundations" / "electric-charge-field-potential.md"
        text = chapter.read_text(encoding="utf-8")
        for needle in (
            "1.602176634",
            "E = -",
            "Poisson",
            "1 eV",
            "ChrisOS",
            "ChrisCPU",
        ):
            if needle not in text:
                raise AssertionError(f"{chapter}: missing {needle!r}")

    print(
        "electric-field examples passed: elementary charge, Coulomb force, "
        "qΔV energy, eV conversion and uniform-field potential arithmetic"
    )
    print(
        "curriculum contract passed: matter -> electrostatics -> circuits -> "
        "signal integrity -> semiconductors -> CMOS -> logic remains explicit"
    )
    print(
        "scope: classical electrostatic teaching checks; no semiconductor-device "
        "or transmission-line simulation is claimed"
    )


if __name__ == "__main__":
    main()
