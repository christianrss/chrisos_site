---
id: kernel-model
lang: pt-br
type: technical-chapter
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/syscall.c
  - kernel/wm/main.c
symbols: []
depends_on:
  - power-on-kstart
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - processes-syscalls
---

# Modelo de kernel e fronteiras de confiança

## O que é um kernel

Kernel é a camada privilegiada que controla mecanismos globais da máquina que programas comuns não podem manipular diretamente: address spaces, estado privilegiado da CPU, interrupções, memória física, dispositivos e políticas de recursos compartilhados.

"Kernel" não implica uma arquitetura interna única. Sistemas podem ser monolíticos, microkernel, híbridos ou usar outras divisões. A questão concreta é onde o código executa, qual address space ocupa e quais fronteiras de falha realmente existem.

## Modelo do ChrisOS

O ChrisOS atual é melhor descrito como **monolítico modular**. Gerenciamento de memória, filesystems, drivers, gráficos, window manager, rede e integração com runtime estão no kernel privilegiado ou acessam serviços privilegiados.

"Modular" descreve separação de fonte e interfaces, não isolamento por processo. Um bug em driver ring 0 ainda pode corromper memória global do kernel.

## Trusted computing base

A TCB contém componentes cuja correção é necessária para preservar integridade e isolamento: memória, page tables, entrada de interrupções, isolamento de processos, user-copy e drivers capazes de DMA.

```text
mais privilégio
      +
maior alcance de memória
      +
mais comportamento assíncrono
      =
maior consequência de falhas
```

Quantidade de linhas não mede criticidade.

## Fronteiras do ChrisOS

| Fronteira | Separação |
|---|---|
| ring 3 → ring 0 | processo nativo e kernel |
| memória CLVM → kernel | offsets guest e ponteiros privilegiados |
| CR3 do processo → high half compartilhado | address spaces de usuário e kernel |
| API do driver → registradores do device | política do subsistema e protocolo de hardware |
| app ChrisC → syscalls CLVM | aplicação de linguagem e serviços do kernel |

As fronteiras não possuem a mesma força. Chamada entre módulos C do kernel é principalmente fronteira de interface; syscall também é fronteira de privilégio imposta por hardware.

## Mecanismo e política

Mecanismo responde **como** executar uma operação: mapear página, submeter I/O, trocar processo. Política responde **qual escolha** deve ser feita: qual processo roda, quais permissões são permitidas, qual disco vira root.

Em kernel experimental essas duas dimensões podem estar próximas no código. A documentação registra a implementação atual sem fingir separações ainda inexistentes.

## Estado global

Estado global exige contratos explícitos:

- quem inicializa;
- qual CPU pode alterar;
- qual lock protege;
- se IRQ pode acessar;
- como teardown funciona;
- qual processo/VM possui o recurso.

`docs/LOCKING.md` e `docs/RESOURCE_OWNERSHIP.md` registram vários desses contratos no código atual.

## Domínios de falha

Page fault de user process pode ser contido no processo. Page fault do kernel segurando lock crítico pode impedir recuperação segura. DMA incorreto pode sobrescrever memória sem uma store executada pela CPU.

Por isso código de kernel valida entradas, overflow, permissões e ownership com rigor maior que aplicações comuns.

## Ordem de boot como arquitetura

`kstart` codifica dependências: memória física precede allocators; handlers precedem uso de IRQ; storage precede montagem do ChrisFS; runtime de linguagem vem depois das fundações de máquina e armazenamento.

A ordem é um grafo de dependências expresso como fluxo executável.

## Kernel como produtor de interfaces

O kernel expõe syscalls nativas, syscalls CLVM, filesystem, gráficos, lifecycle de processos/tasks e rede. Um sistema estável não é apenas um binário que chega ao desktop; é um conjunto de contratos suficientemente definidos para que software acima dependa deles.
