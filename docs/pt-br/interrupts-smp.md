---
title: "06 Interrupções e SMP"
description: "GDT/TSS, IDT, exceções, temporizadores, roteamento APIC, processadores secundários e trabalho entre CPUs."
---

<div class="retro-kicker">FUNDAMENTOS DO SISTEMA · 06</div>

# Interrupções e SMP

<div class="lang-switch"><a href="../../interrupts-smp/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

GDT/TSS, IDT, exceções, temporizadores, roteamento APIC, processadores secundários e trabalho entre CPUs.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/metal/smp.c · IDT/APIC/IOAPIC/job infrastructure</code>
</div>

## Modelo de evidência

| Rótulo | Significado |
|---|---|
| **Implemented** | Existe implementação rastreável no código. |
| **Host-tested** | Há teste reproduzível executado fora do guest. |
| **QEMU-proven** | Há gate que prova o comportamento no perfil emulado declarado. |
| **Hardware-proven** | Há evidência em máquina física identificada. |

!!! note "Regra editorial"
    Roadmap, intenção arquitetural e implementação observada são categorias diferentes. Quando houver divergência, registre a revisão e a evidência.

## Próxima leitura

[07 Processos e syscalls](./processes-syscalls.md)
