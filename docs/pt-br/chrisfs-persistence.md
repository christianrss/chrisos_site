---
title: "08 ChrisFS e persistência"
description: "Workspace persistente, abstração de block devices, layout do ChrisFS, compatibilidade e implicações para instalação."
---

<div class="retro-kicker">FUNDAMENTOS DO SISTEMA · 08</div>

# ChrisFS e persistência

<div class="lang-switch"><a href="../../chrisfs-persistence/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Workspace persistente, abstração de block devices, layout do ChrisFS, compatibilidade e implicações para instalação.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/fs/cfs.c · kernel/fs/cfs_format.h · block_device.h</code>
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

[09 Linguagem ChrisC](./chrisc-language.md)
