#!/usr/bin/env python3
"""Deterministic teaching checks for the circuit-foundation chapters.

Scope:
- ohm-kirchhoff-circuits
- capacitance-inductance

These checks validate arithmetic examples, conservation residuals, simple
small-matrix topology cases, and bilingual document anchors. They are not
SPICE, electromagnetic field simulation, component qualification, or
hardware-conformance tests.
"""

from __future__ import annotations

import math
from pathlib import Path


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def parallel(a: float, b: float) -> float:
    assert a > 0 and b > 0
    return (a * b) / (a + b)


def det2(a: float, b: float, c: float, d: float) -> float:
    return a * d - b * c


def solve2(a: float, b: float, c: float, d: float, y0: float, y1: float) -> tuple[float, float]:
    det = det2(a, b, c, d)
    if approx(det, 0.0, rel=0.0, abs_tol=1e-15):
        raise ValueError("singular matrix")
    x0 = (y0 * d - b * y1) / det
    x1 = (a * y1 - y0 * c) / det
    return x0, x1


def check_resistive_networks() -> None:
    # Series and parallel equivalents.
    r1, r2 = 1000.0, 2000.0
    assert r1 + r2 == 3000.0
    assert approx(parallel(r1, r2), 666.6666666666666)

    # Unloaded voltage divider: 12 V across 1 kΩ + 2 kΩ.
    source = 12.0
    current = source / (r1 + r2)
    vx = current * r2
    assert approx(current, 0.004)
    assert approx(vx, 8.0)

    # Loaded divider: 2 kΩ lower leg loaded by 2 kΩ -> 1 kΩ lower equivalent.
    load = 2000.0
    rlow = parallel(r2, load)
    loaded_vx = source * rlow / (r1 + rlow)
    assert approx(rlow, 1000.0)
    assert approx(loaded_vx, 6.0)

    # Current division: 3 A into 2 Ω || 4 Ω.
    total_i = 3.0
    ra, rb = 2.0, 4.0
    ia = total_i * rb / (ra + rb)
    ib = total_i * ra / (ra + rb)
    assert approx(ia, 2.0)
    assert approx(ib, 1.0)
    assert approx(ia + ib - total_i, 0.0)

    # Two-node nodal system:
    # Node 1: (V1-10)/5 + (V1-V2)/10 = 0
    # Node 2: (V2-V1)/10 + V2/10 = 0
    # => 3V1 - V2 = 20; -V1 + 2V2 = 0
    v1, v2 = solve2(3.0, -1.0, -1.0, 2.0, 20.0, 0.0)
    assert approx(v1, 8.0)
    assert approx(v2, 4.0)

    # KCL residuals at the same nodes.
    node1 = (v1 - 10.0) / 5.0 + (v1 - v2) / 10.0
    node2 = (v2 - v1) / 10.0 + v2 / 10.0
    assert approx(node1, 0.0)
    assert approx(node2, 0.0)

    # KVL around source -> 5Ω -> 10Ω(to node2) -> 10Ω(to reference).
    # Voltage changes: +10 - 2 - 4 - 4 = 0.
    kvl = 10.0 - (10.0 - v1) - (v1 - v2) - v2
    assert approx(kvl, 0.0)

    # Thévenin/Norton equivalence at one port.
    vth, rth = 12.0, 3.0
    inorton = vth / rth
    assert approx(inorton, 4.0)
    for rload in (1.0, 3.0, 9.0):
        i_thevenin = vth / (rth + rload)
        v_port_th = i_thevenin * rload
        v_port_no = inorton * parallel(rth, rload)
        assert approx(v_port_th, v_port_no)

    # Passive-sign power balance for a 10 V source driving 5 Ω + 5 Ω.
    i = 1.0
    p_r1 = i * i * 5.0
    p_r2 = i * i * 5.0
    p_source = 10.0 * (-i)  # passive convention: source delivers power
    assert approx(p_r1 + p_r2 + p_source, 0.0)

    # Floating two-node resistor matrix has gauge freedom and is singular.
    g = 0.25
    assert approx(det2(g, -g, -g, g), 0.0)


def check_capacitance_and_inductance() -> None:
    eps0 = 8.8541878128e-12

    # Parallel-plate approximation: 1 cm², 1 mm vacuum gap.
    area = 1.0e-4
    distance = 1.0e-3
    c_plate = eps0 * area / distance
    assert approx(c_plate, 8.8541878128e-13, rel=1e-12)

    # Q = C V, i = C dV/dt, U = 1/2 C V².
    c = 10.0e-6
    v = 5.0
    q = c * v
    assert approx(q, 50.0e-6)

    dv_dt = 2000.0
    i_c = c * dv_dt
    assert approx(i_c, 0.02)

    u_c = 0.5 * c * v * v
    assert approx(u_c, 125.0e-6)

    # Capacitor combinations.
    c1, c2 = 2.0e-6, 3.0e-6
    c_parallel = c1 + c2
    c_series = (c1 * c2) / (c1 + c2)
    assert approx(c_parallel, 5.0e-6)
    assert approx(c_series, 1.2e-6)

    # Charge sharing: 2uF@6V with 4uF@0V -> 2V.
    vf = (2.0e-6 * 6.0 + 4.0e-6 * 0.0) / 6.0e-6
    assert approx(vf, 2.0)

    # Solenoid approximation L = mu N² A / length.
    mu0 = 4.0 * math.pi * 1e-7
    n_turns = 100
    sol_area = 1.0e-4
    sol_length = 0.1
    l_solenoid = mu0 * n_turns**2 * sol_area / sol_length
    assert approx(l_solenoid, 1.2566370614359173e-5)

    # v = L di/dt and U = 1/2 L I².
    l = 10.0e-3
    di_dt = 300.0
    v_l = l * di_dt
    assert approx(v_l, 3.0)

    i_l = 2.0
    u_l = 0.5 * l * i_l * i_l
    assert approx(u_l, 0.02)

    # Inductor combinations, explicitly uncoupled.
    l1, l2 = 2.0e-3, 6.0e-3
    l_series = l1 + l2
    l_parallel = (l1 * l2) / (l1 + l2)
    assert approx(l_series, 8.0e-3)
    assert approx(l_parallel, 1.5e-3)

    # Time constants: RC and L/R both reduce to seconds.
    r = 1000.0
    c_tau = 10.0e-6
    assert approx(r * c_tau, 0.01)

    l_tau = 20.0e-3
    r_tau = 10.0
    assert approx(l_tau / r_tau, 0.002)

    # Ideal LC energy state is non-negative.
    total_energy = 0.5 * c * v * v + 0.5 * l * i_l * i_l
    assert total_energy >= 0.0


def check_documents() -> None:
    root = Path(__file__).resolve().parents[1]
    revision = "da3df29cb397932c43d32373871fb9380e688ade"

    required = {
        "ohm-kirchhoff-circuits.md": (
            "Σ i_k = 0",
            "Σ v_k = 0",
            "G v = b",
            "Thévenin",
            "Norton",
            "ChrisOS",
        ),
        "capacitance-inductance.md": (
            "Q = C V",
            "i = C dV/dt",
            "v = L di/dt",
            "1/2 C V²",
            "1/2 L I²",
            "ChrisOS",
        ),
    }

    for lang in ("en", "pt-br"):
        for filename, anchors in required.items():
            chapter = root / "docs" / lang / "01-foundations" / filename
            text = chapter.read_text(encoding="utf-8")
            if revision not in text:
                raise AssertionError(f"{chapter}: missing reviewed revision")
            for anchor in anchors:
                if anchor not in text:
                    raise AssertionError(f"{chapter}: missing {anchor!r}")


def main() -> None:
    check_resistive_networks()
    check_capacitance_and_inductance()
    check_documents()
    print(
        "circuit-foundation examples passed: Ohm/KCL/KVL, series/parallel, "
        "dividers, nodal solution, Thevenin/Norton, power balance, C/L state, "
        "energy, combinations, charge sharing and time constants"
    )
    print(
        "scope: deterministic teaching checks only; no SPICE, field solver, "
        "component qualification or hardware-conformance claim"
    )


if __name__ == "__main__":
    main()
