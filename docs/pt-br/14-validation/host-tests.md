---
id: host-tests
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/check_test_gates.py
  - tools/test_cfs_host.c
  - tools/test_pmm_cycle.c
  - tools/test_tlb_proto.c
  - tools/test_klog.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_cfs.c
  - tools/test_jit_bench.c
  - tools/host_metal/metal_stub.c
symbols: []
depends_on:
  - validation-evidence
related:
  - qemu-gates
  - fault-injection
  - fuzzing
  - performance-measurement
---

# Arquitetura dos testes de host

## Escopo

O ChrisOS usa uma camada ampla de testes executados no host para exercitar algoritmos de produção sem bootar o kernel.

O principal target agregado é:

    make host-gates

Esse target compila e executa testes de filesystem, protocolos de memória, helpers de concorrência, linguagem/runtime, algoritmos gráficos, etapas do toolchain, inputs malformados, workloads de fuzz e alguns contratos de desempenho.

Host tests são evidência sobre semântica do código em um processo controlado. Eles não provam que estado privilegiado da CPU, roteamento de interrupts, DMA ou hardware físico funcionem corretamente.

## Modelo de build no host

O makefile de topo define:

    HOST_CC := gcc
    HOST_CFLAGS := -std=c11 -Wall -Wextra -Werror ...

A maioria dos host tests compila diretamente o módulo C de produção sob teste dentro de um executável normal de userspace.

Essa arquitetura traz duas vantagens:

1. o teste executa a mesma implementação algorítmica usada pelo kernel, em vez de um modelo reimplementado separadamente;
2. falhas são baratas de reproduzir com ferramentas comuns de debugging.

O principal risco é substituição de ambiente. Dependências de kernel que não podem executar em userspace são trocadas por stubs, memória sintética, devices falsos ou primitivas de sincronização do host.

Assim, o resultado prova o código alcançado por esse harness, não o caminho completo de integração do kernel.

## Grafo agregado de gates

O target `host-gates` é um grafo de dependências, não um único executável monolítico.

Os pré-requisitos atuais incluem famílias como:

- ChrisFS: format, mount, paths, indirect blocks, journal, chmod, locking e fsck;
- JIT, VM, native code generation e benchmark;
- ChrisO, ChrisAsm, ChrisLd e KCC;
- graphics, shader, VirtIO queue e resource helpers;
- modelos de PMM/heap/SMP;
- helpers de kernel threads e jobs;
- protocolo de TLB;
- klog/build identity/memory information;
- tratamento de ELF malformado;
- ownership de sockets;
- fuzz tests;
- regressões de editor/debugger/runtime;
- stability gates.

Esse layout isola domínios de falha. Um executável que falha identifica um subsistema mais estreito que uma falha de boot do sistema inteiro.

## Auditoria de alcançabilidade

Um target de teste pode existir no makefile e nunca ser executado pela validação contínua.

O ChrisOS trata isso com:

    tools/check_test_gates.py

O script analisa regras do make, começa no root `host-gates`, percorre as arestas de dependência e reporta regras com aparência de teste que não são alcançáveis.

A invariável relevante é:

    todo host test declarado e destinado à suíte
    precisa ser alcançável a partir de host-gates

Isso verifica orquestração, não qualidade do teste.

Evita perda silenciosa de cobertura quando um teste é adicionado, mas não é conectado ao gate agregado.

## Testes de filesystem com device falso

`tools/test_cfs_host.c` constrói um `BlockDevice` apoiado por memória.

Os callbacks falsos de read/write copiam setores entre o filesystem e um buffer de memória do host.

O harness pode injetar falha de I/O em um LBA escolhido e resetar o disco sintético inteiro entre cenários.

Isso torna baratos testes como:

- format e mount;
- persistência após remount;
- cache counters;
- crescimento de diretórios;
- disco cheio;
- propagação de erro de read/write;
- invariantes de metadata.

O padrão útil é substituir a dependência na interface mais estreita.

ChrisFS continua vendo a API real de block device. Apenas controller/media é substituído.

## O que um block device falso não prova

Um disco em memória não reproduz:

- queues reais do controlador;
- ordering de DMA;
- caches voláteis de escrita;
- conclusão parcial de hardware;
- perda de energia entre writes;
- reset de firmware/controller;
- timing de erro da mídia.

Um host test de filesystem que passa é forte evidência para algoritmos on-disk e propagação de erros pela interface abstrata, mas é evidência fraca de integração com controlador de storage.

## Testes de ciclo do allocator

`tools/test_pmm_cycle.c` verifica accounting do allocator em um ciclo grande de allocate/free.

Ele registra o número inicial de páginas livres, aloca 1000 páginas, verifica o decremento, libera tudo e exige:

    free_after == free_before

e:

    used + free == usable

Isso é um teste orientado a invariantes.

Não confirma apenas que uma allocation retorna valor diferente de zero; verifica conservação do estado do allocator ao longo do ciclo completo.

A complexidade do próprio teste é (O(n)) para (n) alocações e frees.

Seu valor diagnóstico é alto porque frame perdido ou contabilizado duas vezes aparece como divergência ao final.

## Modelos de protocolos sensíveis a SMP

Alguns mecanismos de concorrência são separados para que sua state machine execute sem instruções privilegiadas reais.

O protocolo de TLB shootdown é exemplo importante.

`tools/test_tlb_proto.c` exercita:

- publicação de nova geração de invalidation;
- acknowledgements de CPUs remotas;
- timeout/fencing de CPU silenciosa;
- bloqueio de reuse até acknowledgements necessários;
- buracos no conjunto de CPUs online;
- transições de CPUs halted/fenced;
- heartbeat.

Esses testes provam a state machine do protocolo.

Eles não provam que:

- IPIs reais são entregues;
- `invlpg` executa no core correto;
- ordering do APIC está correto;
- memory ordering do hardware corresponde às premissas.

Essas propriedades exigem evidência QEMU ou física.

## Substituição host-metal

Alguns módulos do kernel são compilados com:

    -DCHRIS_HOST_METAL

e ligados com:

    tools/host_metal/metal_stub.c

Isso expõe um modelo compatível com host para serviços de baixo nível.

O objetivo não é emular x86-64 completamente.

É tornar transições de estado algorítmicas testáveis enquanto exclui operações privilegiadas do executável.

Um teste que usa host-metal precisa documentar qual fronteira foi substituída; caso contrário, um host pass pode ser confundido com evidência de integração arquitetural.

## Camada de sanitizers

O makefile contém o target `host-sanitize`.

Testes selecionados são recompilados com:

    -fsanitize=address,undefined

incluindo casos orientados a memória/concorrência como PMM/heap/SMP e kernel threads/jobs.

AddressSanitizer e UndefinedBehaviorSanitizer fornecem classe de evidência diferente de asserts comuns.

Podem detectar:

- acesso fora de limites;
- use-after-free em allocations visíveis ao host;
- shifts e operações com undefined behavior;
- algumas falhas de lifetime/aliasing.

Continuam operando sob ABI do host e não detectam problemas que só aparecem no mapa freestanding do kernel ou em execução privilegiada.

## Testes negativos de parser e loader

`tools/test_elf_malformed.c` constrói deliberadamente inputs ELF inválidos.

Os casos incluem inconsistências em:

- magic;
- offsets de program headers;
- tamanhos de segments;
- ranges de virtual address;
- offsets de arquivo;
- tipos de segmento não suportados;
- mappings sobrepostos.

O harness também acompanha estado de recursos antes e depois da rejeição.

Falhar o parse só é correto quando a rejeição também não vaza frames do processo nem deixa estado inconsistente.

Isso é mais forte que verificar apenas error code.

## Fuzz determinístico

O ChrisOS também usa testes pseudo-randômicos limitados.

`tools/test_fuzz_cfs.c` parte de seed fixa de PRNG e gera uma série de mutações de paths e operações de filesystem antes de executar fsck.

A seed fixa torna o workload reproduzível.

Isso não é coverage-guided fuzzing. É workload adversarial determinístico.

Seu valor está em detectar regressões sobre inputs incomuns sem perder um caminho estável de reprodução.

Uma camada futura de fuzzing pode adicionar mutation corpus e coverage guidance sem substituir esse gate determinístico.

## Testes de kernel log

`tools/test_klog.c` verifica tanto cópia comum quanto wrap do ring.

A invariável central de capacidade é:

    bytes retidos pelo klog <= 8192

Depois de escrever mais de uma capacidade completa, o teste exige comprimento copiado de exatamente 8192 bytes e preservação do byte mais recente.

Isso isola semântica do ring buffer de serial hardware e persistência em filesystem.

Transmissão serial e persistência de `SYS/BOOT.LOG` continuam sendo problemas de integração.

## Testes de compiler e runtime

Grande parte da suíte cobre a stack ChrisC/CLVM/toolchain nativa.

Host tests funcionam especialmente bem aqui porque parsing, semantic analysis, bytecode generation, object generation, linking e grande parte do JIT são transformações determinísticas comuns.

Invariantes úteis incluem:

- input malformado é rejeitado;
- metadata do objeto gerado é consistente;
- relocation/link preserva semântica de symbols;
- execuções VM e JIT concordam em resultados observáveis;
- pointer width permanece estável;
- debugger/source mapping não regride.

Essa camada encontra muitos erros antes de qualquer boot de kernel.

## Gate de desempenho do JIT

`tools/test_jit_bench.c` não é apenas teste funcional.

Ele roda workload interpretado e versão compilada por JIT e exige:

    speedup >= 5.0x

na configuração de benchmark do host.

O benchmark usa clock monotônico do host e várias rodadas.

É um guard contra regressão de desempenho, não um resultado absoluto de desempenho do ChrisOS em hardware.

O resultado depende de:

- CPU do host;
- compiler do host;
- flags de otimização;
- estado térmico/frequência;
- scheduling do sistema operacional;
- arquitetura.

Um threshold é útil em ambiente razoavelmente controlado, mas números não devem ser comparados entre máquinas não relacionadas como se descrevessem desempenho do kernel.

## Testes gráficos no host

Algoritmos gráficos são bons candidatos a host tests porque muitas operações são transformações puras de memória.

A suíte cobre componentes como:

- desenho 2D;
- matemática de vetores/matrizes;
- depth buffer;
- triângulos e meshes;
- tile/bin processing;
- comportamento de shader/IR;
- construção de comandos de VirtIO queue/resource.

Um array de framebuffer no host pode validar pixels e depth exatos.

Ele não prova framebuffer de boot, transporte VirtIO-GPU, stack VirGL do host ou GPU física.

## Limite de concorrência

Threads do host são úteis, mas não idênticas ao modelo de execução do kernel.

Diferenças incluem:

- política de scheduler;
- comportamento de signal/interrupt;
- privilege level;
- entrega APIC;
- semântica de TLB;
- ownership de page table;
- cache topology;
- ambiente de compiler/libc.

Um teste de race no host pode revelar falha de sincronização.

Um host pass não prova ausência de races em execução SMP do kernel.

## Semântica de falha

Host tests comunicam resultado por exit status:

    0  sucesso
    !=0 falha

Também imprimem diagnóstico específico antes de falhar.

Isso cria contrato simples para CI.

O diagnóstico deve identificar a invariável violada, não apenas imprimir "failed".

## Contrato de reprodutibilidade

Um bom host test deve ser:

- determinístico, salvo quando randomness é o objeto explícito;
- autocontido ou claro sobre fixtures;
- independente do estado local do desenvolvedor;
- limitado em runtime;
- não interativo;
- estrito com return code;
- explícito sobre a invariável verificada.

Quando input pseudo-randômico é usado, a seed deve ser fixa ou registrada.

## Onde host tests são mais fortes

Host tests oferecem melhor relação custo/feedback para:

- parsers;
- compilers;
- filesystems sobre block devices abstratos;
- allocators e accounting;
- protocol state machines;
- matemática/graphics puros;
- serialization e object formats;
- semântica determinística de runtime;
- tratamento de input inválido.

São mais fracos para:

- boot;
- interrupts;
- transições privilegiadas;
- DMA;
- timing de MMIO;
- SMP/TLB reais;
- contratos de firmware;
- devices físicos.

## Promoção de evidência

Uma feature deve progredir por camadas de evidência:

    host invariant test
        -> QEMU integration gate
        -> observação física
        -> hardware gate repetível

Um QEMU gate não torna host test redundante.

O host test continua sendo a camada mais barata para localizar falhas.

Da mesma forma, um physical pass não elimina a necessidade de testes algorítmicos determinísticos.

## Comando atual de validação no host

O comando agregado canônico na revisão analisada é:

    make host-gates

Uma execução mais ampla de estabilidade inclui sanitizers e, quando QEMU está instalado, pode estender para QEMU stress gates pelo target `stability`.

A documentação deve registrar o target exato usado quando citar evidência.

## Isolamento de fixtures e artifacts

Host test deve possuir seu temporary state em vez de depender de arquivos locais deixados por outra execução.

Quando tests criam disk images, object files, logs ou binaries gerados, o fixture contract deve registrar:

- quem cria o artifact;
- estado inicial;
- se o test pode mutá-lo;
- como failure preserva diagnostic output;
- como a próxima execução volta a um estado limpo.

Isso importa porque stale artifacts produzem false positives e false negatives. Um test pode parecer aprovado ao ler output de revisão anterior ou falhar porque run interrompida deixou state parcialmente modificado.

Aggregate gates devem preferir fixture creation determinística e paths explícitos dentro do build tree. Artifact persistente só é útil quando retention é intencional e o report identifica qual run o produziu.

## Nota de revisão

Este capítulo foi reconciliado contra a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56` do ChrisOS.

Nesta revisão, a suíte de host é uma primeira camada de validação substancial, com agregação explícita, auditoria de testes órfãos, negative testing determinístico, variantes com sanitizers, workloads de fuzz e guards de desempenho. Seus resultados devem permanecer classificados como evidência de host até que o comportamento integrado correspondente seja exercitado no QEMU ou em hardware físico.
