---
id: validation-evidence
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - docs/STABILITY_AUDIT.md
  - docs/STABILITY_REPORT.md
  - docs/CURRENT_CAPABILITIES.md
  - makefile
  - tests
symbols: []
depends_on:
  - kernel-model
related:
  - self-hosting-bootstrap
  - installation-real-hardware
---

# Validação, classes de evidência e confiabilidade

## Código presente não é prova

Arquivo fonte demonstra implementação, não que todos os paths compilam, bootam, sobrevivem concorrência ou funcionam em hardware físico.

## Camadas

**Host tests** isolam algoritmos e são rápidos, mas não reproduzem IRQ/page tables/DMA reais.

**QEMU gates** exercitam kernel e devices virtuais integrados, mas continuam dentro de hardware emulado.

**Hardware tests** adicionam firmware, devices e timing reais e precisam identificar o perfil testado.

## Teste negativo

Confiabilidade exige ELF malformado, metadata corrompida, user pointer inválido, OOM, feature não suportada, timeout e handles inválidos.

## Invariantes

Testes fortes verificam propriedades:

- frame física não pertence simultaneamente a owners independentes;
- processo não mapeia user page acima da fronteira;
- JIT não reutiliza frame com TLB remoto;
- slot não destrói handle de outro slot.

## Revisão

Resultado de gate vale para a revisão testada. Este site registra `reviewed_revision` e gera fila quando sources declaradas mudam.

## Auditorias históricas

Audits antigas são registros valiosos, mas não superam source atual. A pipeline usa main como fonte primária.

## Comandos reproduzíveis

Gate deve informar comando, exit semantics e marker/artifact. Inspeção visual pode complementar, mas é mais fraca que readback, validação estrutural ou counters.

Classes diferentes de evidência não devem ser reduzidas ao rótulo genérico "working".
