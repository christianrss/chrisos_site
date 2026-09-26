---
id: specifications-policy
lang: pt-br
type: technical-chapter
volume: 15-specifications
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - docs/chrisvm-spec-v1.md
  - docs/chrisvm-boot-protocol.md
  - docs/CHRISO_FORMAT.md
  - kernel/fs/cfs_format.h
  - docs/GLSL_SUPPORT.md
symbols: []
depends_on: []
related:
  - validation-evidence
---

# Especificações, formatos e política de revisão

## Especificação e implementação

Especificação descreve contrato com independência suficiente para testar uma implementação. Código pode definir comportamento de facto, mas especificação explícita permite compatibilidade e implementações alternativas.

Superfícies do ChrisOS incluem contratos ChrisVM/boot, ChrisO, ChrisFS, CLVM, shader subset e layout do kernel.

## Estado externo estável

Dados persistidos ou consumidos por componentes independentes funcionam como ABI: disk format, bytecode, executáveis, syscall numbers, device protocols e blobs.

Alterar struct C sem versionar esse dado pode quebrar artifacts silenciosamente.

## Versionamento

Formato versionado precisa definir identificação, campos/endianness/largura, compatibilidade, migração e writer.

## Texto normativo

Requisito deve ser inequívoco; explicação justifica a regra. Documentação ensina ambos sem misturar obrigação com comentário.

## Standards externos

x86-64, UEFI, ELF, PCI, VirtIO e protocolos de rede não pertencem ao ChrisOS. O site explica o subset usado e referencia especificações primárias.

## Revisão e versão

Commit documental identifica fonte inspecionada; protocol version identifica contrato persistente. São eixos diferentes e ambos precisam ser registrados.
