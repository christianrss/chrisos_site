---
title: "37 Atlas de build e plataforma"
description: "Mapa de targets do make, linkedição, staging de boot, imagens e caminhos de build específicos por arquitetura."
---

<div class="retro-kicker">REFERÊNCIA · 37</div>

# Atlas de build e plataforma

<div class="lang-switch"><a href="../../build-platform-atlas/">English</a><span>•</span><a href="https://github.com/christianrss/ChrisOS" target="_blank">GitHub ↗</a></div>

> **Edição da fonte:** `main @ da3df29` · documentação migrada para GitHub Pages

Mapa de targets do make, linkedição, staging de boot, imagens e caminhos de build específicos por arquitetura.

## O que esta página deve responder

Esta rota preserva a arquitetura editorial da documentação original. O conteúdo deve ser atualizado a partir do código e dos testes da branch `main`, nunca apenas por documentação antiga.

<div class="retro-panel">
<strong>Mapa de código</strong><br>
<code>makefile · linker.ld · third_party/limine</code>
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

[Voltar ao início](./inside-chrisos.md)
