---
title: "26 Bring-up RISC-V"
description: "O bring-up da arquitetura secundária, o que ele prova sobre portabilidade e onde pressupostos x86-64 ainda aparecem."
---

<div class="retro-kicker">HARDWARE E APLICAÇÕES · 26</div>

# Bring-up RISC-V

<div class="lang-switch"><a href="../../riscv/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

O bring-up da arquitetura secundária, o que ele prova sobre portabilidade e onde pressupostos x86-64 ainda aparecem.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>RISC-V build targets and architecture-specific kernel path</code>
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

[27 Roadmap ChrisVM](./chrisvm.md)
