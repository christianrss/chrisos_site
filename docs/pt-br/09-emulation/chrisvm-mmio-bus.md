---
id: chrisvm-mmio-bus
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/buses/mmio.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisMmioSlot
  - chris_mmio_map
  - chris_mmio_find
  - chris_phys_read
  - chris_phys_write
depends_on:
  - chrisvm-memory-map
  - chrisvm-machine
related:
  - chrisvm-io-bus
  - chrisvm-devices
  - emulator-paging
---

# Barramento MMIO do ChrisVM

## Escopo

A camada MMIO genérica do ChrisVM conecta physical addresses do guest fora de RAM/framebuffer a callbacks de devices.

Diferentemente do port-I/O bus, MMIO passa pelo caminho normal de memória:

    instrução do guest
      -> effective virtual address
      -> page translation
      -> physical address
      -> dispatcher físico
      -> MMIO slot
      -> callback do device

A implementação atual valida o caminho real de memory-mapped devices no ChrisCPU, mas ainda é um bus de bring-up.

As principais limitações são capacidade fixa, overlaps não validados, transactions serializadas byte a byte, ausência de trace MMIO funcional e inexistência de modelo explícito de permissions/ordering.

Este capítulo documenta a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Estrutura de registro

Cada ChrisMmioSlot contém:

- used;
- base;
- size;
- read callback;
- write callback;
- contexto opaco.

ChrisMachine possui:

    ChrisMmioSlot mmio[CHRIS_MMIO_MAX]

com:

    CHRIS_MMIO_MAX = 8

A tabela é estática e embutida na máquina.

## Registro de região

chris_mmio_map recebe:

    machine
    base
    size
    read callback
    write callback
    context

Rejeita:

- machine nula;
- size zero.

Depois grava a região no primeiro slot livre.

Falha quando os oito slots já estão ocupados.

Não há check de overlap nem validação dos callbacks.

## Lookup

chris_mmio_find percorre os slots em ordem.

Um slot casa quando:

    pa >= base
    e
    pa - base < size

Esse teste por subtração evita depender de base + size em comparação e reduz um tipo de overflow unsigned.

Quando encontra região, retorna opcionalmente:

    offset = pa - base

e o índice do slot.

Sem match, retorna -1.

## Overlap por first-match

O lookup para no primeiro match.

Logo, regiões sobrepostas são resolvidas pela ordem de registro.

Uma região posterior pode ficar parcial ou totalmente escondida por uma anterior.

O comportamento é determinístico, mas prioridade implícita não é uma boa descrição de máquina.

Uma plataforma estática deve rejeitar overlap acidental ou declarar aliasing explicitamente.

## MMIO é físico, não virtual

chris_mmio_map registra physical addresses.

O guest ainda precisa possuir uma page-table mapping que produza aquele physical address.

O teste de integração demonstra isso: registra MMIO em 0x06000000 e separadamente grava um PDE apontando para a região.

Portanto:

    registro MMIO != mapping virtual

Essa separação é essencial para higher-half, userspace e remapeamento de devices.

## Prioridade do dispatcher

O generic MMIO é fallback de chris_phys_read/write.

A ordem é:

1. RAM;
2. framebuffer;
3. generic MMIO.

Assim, registrar MMIO dentro de RAM não substitui RAM.

O mesmo vale para framebuffer.

A região pode existir na tabela e ser inalcançável devido à prioridade.

## Dispatch de leitura

Quando o request não cabe inteiro em RAM ou framebuffer, chris_phys_read entra no loop MMIO.

Para cada byte:

1. executa chris_mmio_find(pa + i);
2. calcula offset;
3. chama read callback com size 1;
4. pega o low byte do valor retornado;
5. grava no buffer de destino.

Se qualquer byte não tiver mapping ou callback falhar, a função retorna erro.

## Dispatch de escrita

chris_phys_write segue o mesmo padrão.

Para cada byte:

1. resolve slot;
2. calcula offset;
3. chama write callback com size 1 e aquele byte.

Uma falha encerra a operação.

Bytes anteriores podem já ter sido gravados.

Não há transaction rollback.

## A largura original é perdida

A maior limitação semântica é que o callback recebe sempre:

    size = 1

Um store guest de 32 bits vira quatro writes independentes.

Um load de 64 bits vira oito reads.

Isso pode alterar completamente a semântica do device.

Registradores MMIO reais podem:

- aceitar dword e rejeitar byte;
- fazer latch por transaction;
- disparar side effect uma vez por read;
- implementar write-one-to-clear;
- tratar partial write de forma especial.

O bus atual preserva conteúdo byte a byte para devices simples, não a transaction original.

## Diferença em relação a port I/O

Port I/O preserva a largura.

Assim:

    OUT dword -> callback único size 4

enquanto generic MMIO atual faz:

    store dword -> quatro callbacks size 1

Os dois buses possuem fidelidade diferente.

Essa diferença precisa permanecer explícita na documentação de devices.

## Acesso cruzando slots

Como o MMIO é resolvido byte a byte, um request multi-byte pode atravessar de um slot para outro.

Cada byte é enviado de forma independente.

O código não rejeita esse crossing.

Isso é determinístico, mas não representa uma única transaction atômica.

O dispatcher futuro deve identificar a região dona da operação original e validar se crossing é permitido antes de chamar devices.

## Crossing entre RAM/FB e MMIO

O fallback não combina corretamente RAM ou framebuffer com MMIO no mesmo request.

Se um acesso começa dentro da RAM e termina fora, o fast path de RAM falha porque o range completo não cabe.

Então todos os bytes são tratados como MMIO, inclusive os que ainda pertencem à RAM.

A operação pode falhar mesmo com backing em ambos os lados.

Esse problema faz parte do physical memory map, mas aparece diretamente na interação com MMIO.

## Falha de callback

O callback pode retornar erro.

A camada física transforma isso em falha genérica.

Se a page translation era válida, a falha não representa um page fault normal.

Também não existe uma exception x86 genérica equivalente a "device callback failed".

O device precisa diferenciar:

- resposta real de hardware simulada;
- condição de device;
- erro interno do modelo.

Callback failure deve ser reservado para casos realmente anormais.

## Callbacks nulos

chris_mmio_map aceita read/write null.

O dispatcher chama diretamente a direção usada.

Logo, um slot com handler ausente pode causar chamada inválida.

O test device fornece ambos.

O contrato genérico deve rejeitar null ou definir regiões read-only/write-only de forma segura.

## Device de teste em 96 MiB

test_chrisvm.c cria um cell host de oito bytes e expõe em:

    0x06000000

Os callbacks interpretam offset como byte dentro do uint64_t.

Write atualiza um lane:

    shift = offset * 8

Read extrai um lane.

Como o bus já fragmenta byte a byte, esse device foi construído compatível com o dispatcher atual.

O guest escreve 0x2a e lê de volta através de memory operands.

Isso valida:

    instrução
    -> MMU
    -> physical dispatcher
    -> MMIO lookup
    -> callback
    -> resultado no registrador guest

## MMIO e page faults

Falha de page table acontece antes do bus.

Sem mapping virtual ou com permissão negada, o callback MMIO nunca é chamado.

Se a tradução funciona mas não existe backing físico, a máquina pode parar com CHRIS_EXIT_UNMAPPED.

Assim:

    falta de virtual mapping != falta de virtual hardware

Essa distinção é correta e deve permanecer.

## Framebuffer não usa registry genérico

Do ponto de vista do guest, framebuffer é memory-mapped.

Porém, no código ele possui fast path próprio antes de chris_mmio_find.

Portanto, "MMIO" pode significar conceitualmente todos os devices mapeados em memória ou, especificamente, o registry chris_mmio_map.

Este capítulo trata principalmente do segundo.

## Gap de trace_mmio

ChrisConfig possui:

    trace_mmio

e ChrisCPU copia para:

    cpu->trace_mmio

Entretanto, o dispatcher MMIO inspecionado não lê esse campo e não gera logs.

Logo, --trace-mmio existe como configuração sem implementação efetiva de trace.

Um trace útil deveria registrar:

- RIP/instrução;
- physical address;
- device;
- direção;
- largura original;
- valor;
- retorno do callback.

Resolver a largura original é pré-requisito para um trace fiel.

## Sem modelo de memory ordering

Callbacks são executados sincronamente na ordem do interpretador.

Não existe modelo explícito de:

- posted writes;
- write combining;
- UC/WC;
- fences;
- cacheability;
- speculative device access.

No interpretador single-threaded isso gera ordem determinística, mas não representa fidelidade arquitetural de MMIO.

SMP e ChrisHV exigirão contrato mais forte.

## Sem metadados de permissão

ChrisMmioSlot não contém:

- read-only;
- write-only;
- executable;
- widths permitidas;
- alignment;
- endian;
- memory type.

Todas essas regras precisam ser implementadas dentro do callback.

Um region model mais rico poderia centralizar invariantes comuns.

## Sem conexão automática de IRQ

Registrar MMIO apenas cria roteamento de endereço.

Não existe vector/IRQ associado ao ChrisMmioSlot.

Devices interrupt-driven precisam usar facilities separadas da máquina/CPU.

É uma separação razoável, mas um futuro device descriptor pode conectar regiões e interrupt topology.

## Sem identidade do device no slot

O slot possui callbacks e context, mas não nome ou type ID.

O bus, portanto, não consegue gerar sozinho mensagens como "write to nvme0 BAR0".

Adicionar identity melhora trace, diagnostics e collision reports.

## Capacidade e lifecycle

Existem oito slots.

Não há:

- unmap;
- resize;
- remap;
- hotplug;
- reset por slot.

A topologia atual é estática durante a vida da máquina.

## Fronteira com ChrisHV

Um ChrisHV futuro poderá receber acessos MMIO via VM exits ou mecanismos de nested paging.

Esses acessos devem chegar à mesma camada lógica de devices, em vez de criar semântica separada por backend.

Para isso, o bus precisa de um transaction interface que preserve width e seja independente da implementação byte-oriented do ChrisCPU.

## Evidência atual

Os testes demonstram:

- registro MMIO;
- page mapping até a região;
- write do guest atingindo o cell;
- read retornando o valor;
- physical unmapped em outros casos.

Ainda faltam testes para:

- overlap;
- exhaustion;
- handlers nulos;
- transaction width;
- crossing entre slots;
- callback failure;
- trace_mmio;
- ordering.

## Prioridades de hardening

Os trabalhos de maior valor são:

1. preservar largura original da transaction;
2. rejeitar ou modelar crossings entre regiões;
3. rejeitar overlaps acidentais;
4. suportar read-only/write-only com segurança;
5. tornar --trace-mmio funcional;
6. adicionar identidade de device;
7. ampliar ou formalizar o limite de oito slots;
8. declarar alignment e widths suportadas;
9. separar erro interno de resposta guest-visible;
10. testar overlap, width, boundaries e failure;
11. aproximar framebuffer e generic MMIO de um region model autoritativo;
12. criar transaction interface comum a ChrisCPU e ChrisHV.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisVM possui registry MMIO genérico funcional e um caminho guest-to-device validado. O desenho atual é fortemente byte-oriented: operações multi-byte perdem largura e podem ser fragmentadas entre slots. Somado a first-match overlap, capacidade fixa e trace_mmio inativo, isso torna o bus adequado a devices simples de bring-up, mas ainda não a um subsistema MMIO geral de alta fidelidade.
