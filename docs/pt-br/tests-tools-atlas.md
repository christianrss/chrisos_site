---
title: "36 Atlas de testes e ferramentas"
description: "Mapa de testes host, gates QEMU, geradores, utilitários de transferência e ferramentas de validação."
---

<div class="retro-kicker">REFERÊNCIA · 36</div>

# Atlas de testes e ferramentas

<div class="lang-switch"><a href="../../tests-tools-atlas/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Mapa de testes host, gates QEMU, geradores, utilitários de transferência e ferramentas de validação.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>tools/ · tests / make gates</code>
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

[37 Atlas de build e plataforma](./build-platform-atlas.md)
