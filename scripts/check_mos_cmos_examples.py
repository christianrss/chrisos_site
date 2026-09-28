#!/usr/bin/env python3
"""Deterministic checks for MOS electrostatics and CMOS switching foundations."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-18) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_mos_electrostatics() -> None:
    eps0 = 8.8541878128e-12
    eps_ox = 3.9 * eps0
    eps_si = 11.7 * eps0
    tox = 2.0e-9
    cox = eps_ox / tox
    assert approx(cox, 0.017265666235)

    q = 1.602176634e-19
    na = 1.0e23
    psi_s = 0.5
    wd = math.sqrt(2.0 * eps_si * psi_s / (q * na))
    qd = q * na * wd
    cdep = eps_si / wd
    cmos = cox * cdep / (cox + cdep)

    assert wd > 0.0
    assert approx(qd, q * na * wd)
    assert approx(cdep, eps_si / wd)
    assert cmos < cox
    assert cmos < cdep

    vt = 0.02585
    ni = 1.0e16
    phi_f = vt * math.log(na / ni)
    qd_max = math.sqrt(4.0 * q * eps_si * na * phi_f)
    vfb = -0.2
    vtn = vfb + 2.0 * phi_f + qd_max / cox
    assert phi_f > 0.0
    assert qd_max > 0.0
    assert vtn > 0.0

    t_high_k = 4.0e-9
    eps_r_high_k = 20.0
    eot = t_high_k * 3.9 / eps_r_high_k
    assert approx(eot, 0.78e-9)

    capacitance = 10e-15
    voltage = 1.0
    energy = 0.5 * capacitance * voltage * voltage
    assert approx(energy, 5e-15)


def check_cmos_switching() -> None:
    c = 10e-15
    v = 1.0
    alpha = 0.2
    f = 1.0e9

    stored = 0.5 * c * v * v
    cycle = c * v * v
    dynamic_power = alpha * c * v * v * f
    charge = c * v

    assert approx(stored, 5e-15)
    assert approx(cycle, 10e-15)
    assert approx(dynamic_power, 2e-6)
    assert approx(charge, 10e-15)

    transition_time = 100e-12
    avg_current = charge / transition_time
    assert approx(avg_current, 100e-6)

    resistance = 1.0e3
    t50 = math.log(2.0) * resistance * c
    assert approx(t50, 6.931471805599453e-12)

    fanout = 4
    cin = 2e-15
    cwire = 2e-15
    cload = fanout * cin + cwire
    assert approx(cload, 10e-15)

    z_pdn = 1e-3
    delta_i = 10.0
    delta_v = z_pdn * delta_i
    assert approx(delta_v, 10e-3)


def check_source_contract(source_root: Path) -> None:
    arch_h = (source_root / "chrisvm" / "chris_arch.h").read_text(encoding="utf-8")
    cpu_c = (source_root / "chrisvm" / "cpu" / "emulator" / "chriscpu.c").read_text(encoding="utf-8")
    gfx_c = (source_root / "kernel" / "gfx" / "graphics.c").read_text(encoding="utf-8")

    for anchor in (
        "typedef struct ChrisArchitectureState",
        "uint64_t tsc;",
        "uint8_t xmm[16][16];",
    ):
        if anchor not in arch_h:
            raise AssertionError(f"chris_arch.h missing reviewed anchor {anchor!r}")

    for anchor in (
        "static int cpu_run",
        "cpu->steps++;",
        "cpu->arch.tsc++;",
    ):
        if anchor not in cpu_c:
            raise AssertionError(f"chriscpu.c missing reviewed anchor {anchor!r}")

    for anchor in (
        "uint32_t gfx_rgb",
        "((uint32_t)red << 16)",
        "((uint32_t)green << 8)",
    ):
        if anchor not in gfx_c:
            raise AssertionError(f"graphics.c missing reviewed anchor {anchor!r}")


def check_documents(root: Path) -> None:
    mos_paths = {
        "en": root / "docs" / "en" / "01-foundations" / "mos-capacitor.md",
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / "mos-capacitor.md",
    }
    mos_required = (
        "C_ox = ε_ox / t_ox",
        "W_d",
        "C_dep",
        "φ_F",
        "V_TN",
        "EOT",
        "sources: []",
        "symbols: []",
        "MIT 6.012",
        "BIPM",
    )

    for lang, path in mos_paths.items():
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in mos_required:
            if anchor not in text:
                raise AssertionError(f"{lang} MOS chapter missing {anchor!r}")

    cmos_paths = {
        "en": root / "docs" / "en" / "01-foundations" / "cmos-switching-power.md",
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / "cmos-switching-power.md",
    }
    cmos_required = (
        "P_dynamic = α C_L V_DD² f",
        "E_cycle = C_L V_DD²",
        "0.69",
        "ChrisArchitectureState",
        "cpu_run",
        "gfx_rgb",
        "chrisvm/chris_arch.h",
        "chrisvm/cpu/emulator/chriscpu.c",
        "kernel/gfx/graphics.c",
        "MIT 6.012",
        "BIPM",
    )

    for lang, path in cmos_paths.items():
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in cmos_required:
            if anchor not in text:
                raise AssertionError(f"{lang} CMOS chapter missing {anchor!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source)

    check_mos_electrostatics()
    check_cmos_switching()
    check_source_contract(source_root)
    check_documents(root)

    print(
        "MOS/CMOS checks passed: oxide/depletion capacitance, threshold construction, "
        "EOT, stored/dynamic energy, transition current, RC delay, fan-out load, "
        "PDN coupling and reviewed ChrisOS architecture/software boundary"
    )
    print(
        "scope: deterministic teaching equations and source anchors only; no fabricated-device, "
        "standard-cell, timing-signoff or measured-silicon power claim"
    )


if __name__ == "__main__":
    main()
