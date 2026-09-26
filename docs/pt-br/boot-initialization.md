---
title: "04 Boot e inicialização"
description: "Transição pelo Limine, entrada higher-half, informações de boot e ordem de inicialização até o loop do desktop."
---

<div class="retro-kicker">FUNDAMENTOS DO SISTEMA · 04</div>

# Boot e inicialização

<div class="lang-switch"><a href="../../boot-initialization/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Transição pelo Limine, entrada higher-half, informações de boot e ordem de inicialização até o loop do desktop.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>kernel/metal/bootinfo.c · kernel/metal/* · linker.ld</code>
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

[05 Memória e ownership](./memory-ownership.md)
