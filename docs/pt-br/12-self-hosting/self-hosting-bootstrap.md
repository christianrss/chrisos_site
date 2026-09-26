---
id: self-hosting-bootstrap
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - docs/CURRENT_SELFHOST_AUDIT.md
  - docs/KCC_STATUS.md
  - docs/KERNEL_SELFHOST_PLAN.md
  - kernel/tools/chrisbuild.c
  - tools/seed_selfhost.c
symbols: []
depends_on:
  - native-toolchain
  - desktop-applications
related:
  - installation-real-hardware
  - validation-evidence
---

# Self-hosting, bootstrap e reprodutibilidade

## Definição

Sistema self-hosting consegue construir partes significativas de si com ferramentas executadas ou produzidas pelo próprio sistema segundo critério declarado.

Sem níveis, o termo é ambíguo. Compilar uma aplicação, reconstruir kernel e gerar mídia completa são claims diferentes.

## Cadeia de bootstrap

```text
toolchain host
    ↓
compiler stage 0
    ↓
stage 1
    ↓
stage 2
    ↓
convergência / testes
```

A cadeia é um grafo de proveniência.

## Níveis ChrisOS

A auditoria define SH0–SH6 e mantém estágios altos como não provados. Na revisão atual, GCC/ld host ainda produzem kernel; KCC cobre parte substancial mas não todas as units; ChrisLd não gerou o kernel bootado; não há instalação/reboot de kernel interno como SH5; reprodução completa ainda depende do host.

## Por que compiler não basta

Self-host do kernel exige C, assembly, generated assets, linker semantics, estruturas do boot protocol, ELF final, instalação e prova do binário executado. Se algum estágio ainda chama NASM/ld host, a dependência existe.

## Reprodutibilidade

Self-hosting responde quem constrói. Reproducibilidade responde se inputs equivalentes produzem artifact ou comportamento conforme critério. Timestamps e build IDs podem impedir igualdade byte-a-byte sem invalidar equivalência semântica.

## Prova prática

Um gate forte registra revisão, tools, hash do kernel interno, validação ELF, instalação do mesmo artifact, reboot sem substituição e build identity observável.
