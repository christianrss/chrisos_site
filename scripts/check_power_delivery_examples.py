#!/usr/bin/env python3
"""Deterministic checks for power-delivery, regulation and decoupling foundations."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_target_impedance() -> None:
    dv = 30e-3
    di = 20.0
    z = dv / di
    assert approx(z, 1.5e-3)


def check_transient_terms() -> None:
    current = 10.0
    resistance = 2e-3
    assert approx(current * resistance, 20e-3)

    inductance = 0.5e-9
    di_dt = 0.4e9
    assert approx(inductance * di_dt, 0.2)

    dq = 100e-6
    capacitance = 1000e-6
    assert approx(dq / capacitance, 0.1)


def check_buck() -> None:
    vin = 12.0
    duty = 0.1
    vout = duty * vin
    assert approx(vout, 1.2)

    switching_frequency = 500e3
    ts = 1.0 / switching_frequency
    inductance = 1e-6
    ripple = (vin - vout) * duty * ts / inductance
    assert approx(ripple, 2.16)


def check_self_resonance() -> None:
    capacitance = 100e-9
    esl = 1e-9
    f0 = 1.0 / (2.0 * math.pi * math.sqrt(esl * capacitance))
    assert approx(f0, 15_915_494.309189534)


def check_load_line_and_efficiency() -> None:
    v0 = 1.0
    r_loadline = 2e-3
    current = 20.0
    target = v0 - r_loadline * current
    assert approx(target, 0.96)

    pin = 110.0
    pout = 100.0
    eta = pout / pin
    assert approx(eta, 0.9090909090909091)


def check_source_contract(source_root: Path) -> None:
    acpi_c = (source_root / "kernel" / "metal" / "acpi.c").read_text(encoding="utf-8")
    acpi_h = (source_root / "kernel" / "metal" / "acpi.h").read_text(encoding="utf-8")
    audit = (source_root / "docs" / "CURRENT_HARDWARE_AUDIT.md").read_text(encoding="utf-8")
    plan = (source_root / "docs" / "REAL_HARDWARE_PLAN.md").read_text(encoding="utf-8")

    for anchor in (
        "void acpi_probe(void)",
        "RSD PTR ",
        "XSDT",
        "APIC",
        "MCFG",
        "FACP",
        "serial_puts",
    ):
        if anchor not in acpi_c:
            raise AssertionError(f"acpi.c missing reviewed anchor {anchor!r}")

    if "void acpi_probe(void);" not in acpi_h:
        raise AssertionError("acpi.h missing reviewed acpi_probe declaration")

    if "No physical machine was booted." not in audit:
        raise AssertionError("hardware audit no longer states reviewed physical-test boundary")

    if "suspend and resume" not in plan:
        raise AssertionError("real-hardware plan no longer carries reviewed suspend/resume boundary")


def check_documents(root: Path) -> None:
    filename = "power-delivery-regulation.md"
    paths = {
        "en": root / "docs" / "en" / "01-foundations" / filename,
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / filename,
    }

    required = (
        "Z_target = ΔV_allowed / ΔI_step",
        "ΔV_L = L · dI/dt",
        "V_out ≈ D · V_in",
        "f_0 = 1 / (2π sqrt(ESL · C))",
        "V_target(I)",
        "η = P_out / P_in",
        "acpi_probe",
        "kernel/metal/acpi.c",
        "kernel/metal/acpi.h",
        "docs/CURRENT_HARDWARE_AUDIT.md",
        "docs/REAL_HARDWARE_PLAN.md",
        "ACPI Specification Version 6.6",
        "USB Power Delivery Specification Revision 3.2 Version 1.2",
        "BIPM",
    )

    for lang, path in paths.items():
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in required:
            if anchor not in text:
                raise AssertionError(f"{path}: missing {anchor!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source)

    check_target_impedance()
    check_transient_terms()
    check_buck()
    check_self_resonance()
    check_load_line_and_efficiency()
    check_source_contract(source_root)
    check_documents(root)

    print(
        "power-delivery checks passed: target impedance, R/L/C transient terms, "
        "buck ratio/ripple, capacitor self resonance, load line, efficiency and "
        "reviewed ChrisOS ACPI evidence boundary"
    )
    print(
        "scope: deterministic equations/source anchors only; no measured PDN, VRM, "
        "thermal, ACPI power-state or physical-hardware validation claim"
    )


if __name__ == "__main__":
    main()
