---
id: memory-controller-dram-organization
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/buses/mmio.c
  - kernel/metal/bootinfo.h
  - kernel/metal/bootinfo.c
  - kernel/metal/pmm.h
  - kernel/metal/pmm.c
symbols:
  - ChrisConfig
  - ChrisMachine
  - chris_machine_create
  - chris_phys_read
  - chris_phys_write
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - pmm_init
depends_on:
  - sram-dram
  - transmission-lines-differential-signals
  - buses-mmio-dma
  - cache-hierarchy
related:
  - physical-memory
  - coherence
  - atomics-memory-model
  - pmm-algorithms
---

# Organização de DRAM e controladores de memória

## Escopo

O gerenciamento de memória de um sistema operacional normalmente começa a partir de um mapa de memória física: intervalos podem ser utilizáveis, reservados, pertencentes ao firmware, mapeados para dispositivos ou indisponíveis. Essa visão fica intencionalmente acima da eletrônica e do scheduling que fazem DRAM responder a um endereço físico.

Abaixo do page allocator existe uma hierarquia de channels, ranks, banks, rows, columns, command timing e refresh. O memory controller transforma requisições vindas de CPUs/interconnects em comandos DRAM preservando ordering, timing, integridade e fairness.

As unidades precisam ser mantidas separadas:

- um **page frame** é unidade de alocação do sistema operacional;
- uma **cache line** é unidade de transferência da cache/coherence;
- uma **DRAM row** é unidade de ativação do array;
- um **burst** é unidade de transferência no memory interface;
- **channel/rank/bank** fazem parte da organização física;
- o **memory controller** agenda comandos respeitando timing e regras arquiteturais.

O kernel atual do ChrisOS não implementa driver de DRAM controller. Ele consome as informações de memória fornecidas no boot e gerencia page frames. O ChrisVM atual é ainda mais abstrato: a RAM guest é um buffer de bytes zero-inicializado no host, e reads/writes físicos dentro da RAM usam <code>memcpy</code>. Não existe no source revisado um modelo de channel, rank, bank, row buffer ou temporização DRAM.

![Da requisição da CPU ao channel, rank, bank e row através do memory controller](../../assets/diagrams/memory-controller-dram-organization-pt-br.svg)

## Da célula DRAM ao address space do sistema

Uma célula DRAM representa um bit usando carga associada a um pequeno capacitor controlado por um access transistor. A carga se dissipa, portanto a informação precisa ser restaurada periodicamente por refresh.

Um chip organiza muitas células em arrays. As células não são selecionadas individualmente pelo barramento externo da mesma forma que software endereça bytes. O dispositivo utiliza organização e comandos internos:

1. selecionar um bank;
2. ativar uma row nos sense amplifiers/row buffer;
3. emitir comandos de read/write orientados por column;
4. transferir dados em burst;
5. eventualmente fazer precharge para permitir a ativação de outra row.

O row buffer está fisicamente associado aos sense amplifiers. "Abrir uma row" significa que o conteúdo daquela linha de células foi sensoriado e está representado nesse domínio.

Por isso dois acessos ao mesmo bank podem ter custos muito diferentes dependendo de a row desejada já estar aberta.

## Hierarquia de termos

Produtos DRAM e memory controllers possuem conceitos aninhados.

| Nível | Significado |
|---|---|
| Channel | Interface independente de command/data controlada pelo memory controller |
| DIMM/module | Módulo físico conectado a channels/subchannels |
| Rank | Grupo de dispositivos DRAM que participa conjuntamente de uma transferência |
| Chip/device | Circuito integrado DRAM individual |
| Bank group | Agrupamento usado em gerações recentes para regras de timing/recursos |
| Bank | Domínio de array que pode manter uma row ativa |
| Row | Grande conjunto de células ativado nos sense amplifiers |
| Column | Posição selecionada na row ativa para read/write |
| Burst | Sequência de transferências disparada por um column command |

A hierarquia exata varia por geração DDR e topologia do módulo. Portanto conceitos gerais devem ser separados de detalhes específicos de um padrão.

## Channels

Vários memory channels aumentam paralelismo e bandwidth agregada porque requisições podem trafegar por interfaces independentes.

Se um channel transfere D bits por data beat em taxa efetiva R transfers/s:

    bandwidth = (D / 8) * R bytes/s

Com C channels idênticos:

    aggregate_peak = C * (D / 8) * R

É bandwidth de pico, não bandwidth sustentada por aplicação. Commands, refresh, turnaround, row conflicts, queueing, cache behavior e mistura de reads/writes reduzem o valor observado.

Um controller pode interleavar endereços físicos entre channels para distribuir cache lines sequenciais. O mapping exato é específico da plataforma.

## Ranks

Um rank contém dispositivos que, em conjunto, fornecem a largura de dados da transferência.

O controller seleciona um rank e comunica-se com os chips daquele rank em paralelo.

Múltiplos ranks aumentam capacidade e podem oferecer oportunidades adicionais de scheduling, embora rank switching introduza suas próprias restrições.

Rank não é sinônimo de NUMA node. NUMA é um domínio superior de localidade envolvendo processadores, controllers e custo de acesso.

## Banks e bank-level parallelism

Um DRAM bank pode manter uma row ativa enquanto outro bank trabalha de forma relativamente independente. Isso permite **bank-level parallelism**.

Exemplo:

    request A -> bank 0, row 10
    request B -> bank 1, row 42

Parte das operações pode se sobrepor, respeitando recursos compartilhados.

Se ambos acessam bank 0 mas rows diferentes, normalmente a row atual precisa ser fechada e a nova ativada antes do segundo acesso.

Por isso address mapping afeta diretamente paralelismo.

## Rows, columns e row buffer

Uma row activation transfere uma grande quantidade de estado interno para o domínio de sense amplifiers.

Há três casos fundamentais.

### Row hit

A row desejada já está ativa no bank.

Caminho típico:

    READ/WRITE column -> burst

Não é necessário precharge + activate para a requisição.

### Row closed

Nenhuma row está ativa.

    ACTIVATE -> aguardar delay -> READ/WRITE -> burst

### Row conflict

Outra row está ativa.

    PRECHARGE -> aguardar -> ACTIVATE nova row -> aguardar -> READ/WRITE -> burst

Row conflict possui maior command latency que row hit.

Controllers podem otimizar throughput explorando row locality, mas preferência excessiva por hits pode prejudicar fairness.

## Address mapping

A CPU fornece um physical address. O memory controller transforma bits do endereço — às vezes combinados por hashing/XOR — em:

- channel;
- rank;
- bank group;
- bank;
- row;
- column;
- byte position.

Um mapping ilustrativo simples:

    bits baixos      -> byte/burst offset
    bits seguintes  -> column
    alguns bits     -> channel/bank
    bits altos      -> row

Sistemas reais podem misturar bits para distribuir tráfego.

O OS frequentemente não conhece esse mapping em detalhe. Não se deve assumir que page number crescente corresponde linearmente a rows DRAM.

## Princípio de transferência DDR

DDR transfere dados em ambas as transições de uma relação de clock e também utiliza prefetch interno em gerações modernas, permitindo data rate externo superior ao clock do core array.

Taxas em MT/s representam transfers/s, não CPU clock.

Para interface de dados de 64 bits:

    bytes_per_transfer = 64 / 8 = 8

Com R MT/s:

    ideal_bandwidth_GBps ~= 8 * R / 1000

desde que as convenções de unidade sejam explicitadas.

DIMMs ECC possuem bits físicos adicionais, mas payload e redundancy não devem ser confundidos no cálculo de useful bandwidth.

## Commands

Conceitualmente, comandos importantes incluem:

- ACTIVATE — abrir uma row;
- READ — ler columns da row ativa;
- WRITE — escrever columns;
- PRECHARGE — fechar a row e preparar nova ativação;
- REFRESH — restaurar carga conforme requisitos do dispositivo.

Padrões reais contêm regras adicionais. Um simulador simplificado deve declarar explicitamente o subset implementado.

## Timing parameters como restrições

Parâmetros de timing descrevem separações mínimas entre eventos. Não são "latências" independentes que sempre devem ser somadas.

| Parâmetro | Restrição conceitual |
|---|---|
| tRCD | ACTIVATE até column command permitido |
| tCL / CAS latency | relação temporal de READ até dados |
| tRP | PRECHARGE até próximo ACTIVATE |
| tRAS | tempo mínimo de row ativa |
| tRC | row-cycle constraint |
| tRRD | espaçamento entre activates |
| tFAW | limite de activates em janela temporal |
| tWR | write recovery antes de precharge |
| tRFC | ocupação associada a refresh |
| tREFI | relação de intervalo de refresh |

Definições exatas variam por padrão e operating point.

Um modelo correto trata esses parâmetros como restrições de máquina de estados, e não como um único valor fixo de "DRAM latency".

## Row-hit latency versus request latency

A latência observada inclui:

    request latency =
        queue wait
        + command scheduling delay
        + row-state delay
        + bus turnarounds
        + data transfer
        + controller/interconnect overhead

Sob carga, queueing pode dominar.

Modelar tRCD e tCL sem filas ainda produz comportamento irrealista quando existem várias requisições.

## Open-page e close-page policy

Após um acesso, o controller pode:

- manter a row aberta, esperando reuse;
- fazer precharge antecipado, reduzindo custo caso o próximo acesso use outra row.

**Open-page** favorece locality.
**Close-page** pode favorecer workloads com baixa row reuse.

Políticas adaptativas tentam estimar isso dinamicamente.

A escolha afeta performance, não correção arquitetural, desde que timing e ordering sejam respeitados.

## Request queues

Um memory controller possui filas finitas.

Uma request pode conter:

- physical address;
- read/write;
- arrival time;
- requester/core;
- channel/rank/bank/row/column decodificados;
- metadata de ordering;
- completion tag/callback.

Capacidade finita cria backpressure. Quando a fila está cheia, caches/interconnects não podem injetar misses infinitos.

Um modelo temporal do ChrisVM precisa de queue capacity explícita; uma lista ilimitada esconderia saturação.

## FR-FCFS

First-Ready First-Come-First-Serve (FR-FCFS) é uma política clássica de scheduling.

Versão simplificada:

1. entre commands legais agora, priorizar requests prontas, frequentemente row hits;
2. entre equivalentes, escolher a mais antiga.

Pode melhorar row-buffer locality em relação a FIFO.

Porém preferência a hits pode gerar starvation de requests conflitantes. Controllers práticos usam age limits, fairness windows ou mecanismos por requester.

É uma política didática útil por tornar explícita a troca throughput/fairness.

## Complexidade do scheduling

Com Q requests em fila, um scheduler ingênuo pode percorrer todas a cada ciclo:

    O(Q)

Estruturas por bank e ready sets podem reduzir o custo no simulador.

Hardware avalia regras com lógica paralela; complexidade de software não é o mesmo que delay físico.

## Read/write turnaround

O data bus muda de direção entre reads e writes, e essa transição pode introduzir ciclos vazios.

Controllers frequentemente agrupam writes:

- priorizam reads por latency;
- quando write queue atinge threshold, drenam writes;
- voltam a read mode.

Isso melhora eficiência do bus, mas altera latências individuais.

Um timing model precisa representar direção do bus ou ao menos penalty de turnaround.

## Refresh

A carga da DRAM decai e precisa de refresh.

Refresh ocupa recursos de memória por um período. Dependendo da organização, pode afetar um conjunto de banks ou uma região maior.

Um modelo pode manter eventos periódicos:

1. refresh torna-se due;
2. recursos afetados são reservados;
3. commands normais ficam bloqueados conforme política;
4. execução retorna quando refresh termina.

Deve ser documentado se o modelo usa all-bank ou per-bank refresh e se suporta postponement/pull-in.

Omitir refresh é aceitável em RAM funcional, mas não em uma alegação de timing DRAM completo.

## Temperatura e refresh

Retenção física depende de condições como temperatura. Sistemas reais podem ajustar comportamento conforme regras do dispositivo/plataforma.

Um emulator didático não precisa modelar termodinâmica, mas não deve apresentar um único intervalo fixo como universal.

## ECC

Error-correcting code memory adiciona redundância para detectar e corrigir classes de erro.

Fluxo conceitual:

1. calcular check bits em write;
2. armazenar data + redundancy;
3. recomputar syndrome em read;
4. corrigir classes suportadas;
5. reportar corrected/uncorrectable errors.

ECC é independente de virtual-memory permissions.

Um futuro ChrisVM poderia injetar bit faults determinísticos para testar mecanismos de reliability. A RAM guest atual não possui ECC model.

## Scrubbing

Memory scrubbing lê periodicamente memória, corrige erros recuperáveis e reescreve dados.

Se um modelo introduzir ECC faults, deve definir se scrubbing existe; caso contrário o comportamento de longo prazo fica indefinido.

## Memory ordering versus DRAM scheduling

CPU memory-order semantics limitam o que software pode observar. O controller pode reordenar atendimento físico desde que a visibilidade arquitetural definida por caches/coherence/ordering permaneça válida.

Portanto são camadas diferentes:

- program order;
- cache/coherence order;
- controller queue order;
- DRAM command order.

Arrival order no controller não define sozinho legalidade arquitetural.

## Coherence e memory controller

Em sistemas coerentes, loads/stores normalmente passam primeiro pelas caches. DRAM recebe principalmente:

- cache-line fills;
- dirty writebacks;
- prefetch traffic;
- tráfego especial dependendo da arquitetura.

O controller não deve ser confundido com o protocolo inteiro de cache coherence.

Um DRAM model abaixo da cache pode operar com transactions do tamanho de cache lines, e não diretamente com instruções.

## Cache-line granularity versus burst granularity

Uma cache line pode ter 64 bytes, enquanto o channel transmite partes menores por beat/burst.

Não são equivalentes:

    uma load instruction
    uma cache line
    um DRAM command
    um burst

Um load desalinhado pode tocar duas cache lines; uma line fill pode usar várias transferências; uma activated row cobre muito mais dados que uma line.

## NUMA

Sistemas Non-Uniform Memory Access associam memória a domínios mais próximos de determinados sockets/CPUs.

Remote access atravessa interconnects adicionais e pode ter latência/bandwidth diferente.

O OS pode usar topology para:

- colocar páginas perto da CPU;
- bind de threads/memória;
- migrar páginas;
- balancear bandwidth.

O PMM atual do ChrisOS não implementa um NUMA allocator nos arquivos revisados. Ele trata os usable physical pages do boot memory map como universo de alocação até seu limite físico.

## Fronteira de inicialização por firmware

Em PCs comuns, o OS não realiza treinamento de DRAM a partir do estado elétrico bruto no power-on. Firmware/platform initialization configura controller e memória antes da execução normal do bootloader/kernel.

Depois, o kernel recebe um physical memory map.

Isso evita um erro conceitual importante: page allocator não é DRAM training.

O ChrisOS reflete essa fronteira. <code>bootinfo.c</code> solicita o Limine memory map e <code>pmm_init</code> gerencia page ranges. Não existem comandos ACTIVATE/PRECHARGE/REFRESH no PMM.

## Visão de memória no boot do ChrisOS

<code>bootinfo_memmap_count</code> e <code>bootinfo_memmap_entry</code> expõem o mapa fornecido pelo bootloader.

<code>pmm_init</code>:

1. parte de pages indisponíveis;
2. percorre ranges USABLE;
3. marca frames alinhados como livres;
4. reserva low memory;
5. reserva categorias do memory map não alocáveis;
6. inicializa accounting e cursor;
7. reserva pool DMA32.

Essa lógica opera em frames de 4 KiB. Ela não conhece a row DRAM que contém cada frame.

Essa separação é intencional.

## RAM guest atual do ChrisVM

Na revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>:

- <code>CHRIS_RAM_DEFAULT</code> = 16 MiB;
- <code>ChrisConfig</code> contém <code>ram_size</code>;
- machine creation rejeita menos de 2 MiB ou tamanho não alinhado a 2 MiB;
- <code>chris_machine_create</code> usa <code>calloc</code> para criar buffer host zero-filled;
- <code>ChrisMachine</code> guarda pointer <code>ram</code> e <code>ram_size</code>.

Para endereço físico dentro da RAM, <code>chris_phys_read</code> e <code>chris_phys_write</code> usam <code>memcpy</code> entre backing store e buffer do chamador.

Endereços fora da RAM podem seguir framebuffer/MMIO.

A RAM atual é, portanto, um byte store funcional, não um DRAM timing simulator.

## Consequências da abstração atual

Não existem hoje:

- channel selection;
- rank;
- bank/bank group;
- row/column;
- row-buffer state;
- ACT/PRE/READ/WRITE command timing;
- refresh;
- controller queues;
- scheduler;
- bus turnaround;
- ECC;
- NUMA distance;
- latency variável;
- bandwidth saturation.

O tempo de CPU host consumido por <code>memcpy</code> não é definido como guest DRAM timing.

O campo <code>deterministic</code> também não transforma esse tempo host em um modelo temporal da guest.

## Correção funcional versus temporal

O backing store simples oferece:

- semântica clara de physical addresses;
- conteúdo determinístico;
- testes rápidos;
- snapshots/debugging simples;
- independência de um timing model incompleto.

Por isso um futuro DRAM model deve ser opcional e ficar abaixo de uma interface estável.

Backend funcional:

    physical request -> operação imediata no byte store

Backend temporal:

    physical request
        -> decode topology
        -> enqueue
        -> schedule commands
        -> advance simulated time
        -> complete byte-store operation

O backing array pode continuar sendo o mesmo.

## Modelo proposto para ChrisVM

Topologia inicial explícita:

    channels = C
    ranks_per_channel = R
    banks_per_rank = B
    rows_per_bank = N
    row_bytes = S

Estado:

    Channel {
        read_queue
        write_queue
        bus_direction
        available_cycle
        Rank ranks[]
    }

    Bank {
        open_row
        next_activate_cycle
        next_precharge_cycle
        next_read_cycle
        next_write_cycle
    }

O backing data continua em <code>m->ram</code>. O controller decide quando a request completa, não onde os bytes vivem no host.

## Address decoder

Mapping determinístico configurável:

    line = physical_address / cache_line_size
    channel = line % C
    line /= C
    bank = line % B
    line /= B
    column_line = line % lines_per_row
    row = line / lines_per_row

É um mapping de simulador, não uma alegação sobre Intel/AMD.

Uma variante posterior pode XORar bits para experimentos de distribution.

O decoder deve ser pure function e testável.

## Legalidade de commands

Cada bank/rank/channel mantém earliest legal cycle.

Para ACTIVATE em t:

    legal se t >= bank.next_activate_cycle
             e constraints de activate do rank/channel permitirem

Depois:

    bank.open_row = requested_row
    bank.next_read_cycle = t + tRCD
    bank.next_write_cycle = t + tRCD
    bank.next_precharge_cycle = max(anterior, t + tRAS)

Depois de PRECHARGE:

    bank.open_row = NONE
    bank.next_activate_cycle = t + tRP

READ/WRITE atualizam constraints de bank, bus e turnaround conforme o modelo selecionado.

Essa state machine é superior a uma constante única de latency.

## Lifecycle de request

Estados possíveis:

    NEW
      -> QUEUED
      -> WAITING_FOR_PRECHARGE
      -> WAITING_FOR_ACTIVATE
      -> READY_FOR_COLUMN
      -> DATA_TRANSFER
      -> COMPLETE

Row hit pula fases de PRE/ACT.

Row conflict percorre o caminho completo.

Estados explícitos facilitam tracing e assertions.

## Scheduling policies

### FIFO

Oldest request first quando legal.

Vantagens:
- simples;
- previsível;
- fairness forte.

Desvantagem:
- baixa exploração de row locality.

### FR-FCFS

Priorizar ready row hits e, depois, oldest request.

Vantagem:
- maior throughput em padrões com locality.

Risco:
- starvation.

### Age-capped FR-FCFS

Row hits têm prioridade até uma request ultrapassar age threshold.

É boa política experimental para estudar fairness.

## Read/write drain mode

Estado possível:

    mode = READS | WRITES

Entrar em write-drain quando:

    write_queue >= high_watermark
    OR nao existem reads

Voltar a reads quando:

    write_queue <= low_watermark
    AND existem reads

Thresholds devem ser configuração explícita.

## Refresh model

Estado simplificado por rank:

    next_refresh_due
    refresh_busy_until

Ao atingir deadline, scheduler reserva recurso e bloqueia commands normais pelo intervalo de refresh.

A documentação deve declarar se o modelo suporta:

- all-bank;
- per-bank;
- postponement;
- efeitos de temperatura.

Implementação inicial pode usar all-bank periódico.

## Unidade de tempo

Possíveis time bases:

- memory cycles;
- controller cycles;
- ps/ns;
- global ChrisCPU cycle.

Usar CPU cycle é simples, mas acopla frequências.

Usar picoseconds fornece timeline comum para componentes com clocks diferentes.

Uma primeira implementação pode usar abstract cycles se todos os parameters estiverem na mesma unidade e não houver claim de calibração física.

## Interface assíncrona

Possível API:

    request_id = mem_submit(address, size, type, requester)

    mem_tick(now)

    mem_poll(request_id, &result)

Queue full precisa retornar backpressure/retry, não aceitar infinitamente.

<code>chris_phys_read/write</code> permanece como API funcional síncrona.

## Data integrity e commit

Timing não deve alterar semântica de dados.

Read:
- bytes são copiados para o result no completion point definido.

Write:
- data pode ser capturado no submission, mas backing-store visibility deve obedecer o commit point do modelo.

Overlapping accesses precisam de ordering definido pela camada superior.

## MMIO não é DRAM

O código atual separa RAM, framebuffer e MMIO.

Um timing layer deve preservar:

- endereço RAM -> DRAM/controller;
- device/framebuffer -> device/MMIO.

Passar MMIO pelo row scheduler é incorreto.

Logo physical region classification ocorre antes de DRAM topology decoding.

## DMA

DMA acessa physical memory sem executar CPU load/store.

Um controller temporal deve aceitar requesters:

    CPU0
    CPU1
    DEVICE_X
    ...

Isso permite estudar competição por bandwidth e fairness.

O PMM atual já possui uma restrição DMA32 para determinadas necessidades de device allocation. Isso é diferente de scheduling DRAM.

## Page allocation e DRAM locality

Se o OS conhece address-to-channel/bank mapping, page allocation pode influenciar paralelismo.

Políticas possíveis de pesquisa:

- channel-aware page coloring;
- bank-aware allocation;
- NUMA-local placement;
- bandwidth partitioning.

O PMM atual não usa topology DRAM. Implementar isso exigiria uma fonte confiável de topology.

## Segurança

Organização DRAM produz timing compartilhado por row hits/conflicts e controller queues. Adjacência física também é relevante para fenômenos como Rowhammer.

O byte-array model funcional atual não reproduz esses efeitos.

Se futuramente modelados, a documentação deve separar:

- timing channels;
- row conflicts;
- refresh effects;
- fault injection/disturbance;
- ECC mitigation.

Um modelo parcial de banks/rows não deve ser chamado de Rowhammer simulator fiel sem validação física.

## Determinismo

Um modelo reprodutível precisa registrar:

- topology;
- address mapping;
- timing parameters;
- queue capacities;
- scheduling policy;
- initial open rows;
- refresh phase;
- tie-break rules.

Tie-breaking deve usar request IDs/age, não host thread scheduling.

## Trace

Exemplo:

    cycle 1200 SUBMIT R id=41 pa=0x12345000 ch=0 rank=0 bank=3 row=291
    cycle 1201 PRE bank=3
    cycle 1215 ACT bank=3 row=291
    cycle 1229 READ id=41 col=64
    cycle 1243 COMPLETE id=41

O trace deve separar mapping e scheduling.

## Validação do decoder

Property tests:

- índices dentro dos limits;
- todos os bytes de uma cache line mapeiam corretamente;
- avanço por row size muda row conforme fórmula;
- channel/bank interleaving corresponde ao contrato;
- mapping determinístico.

Mapping simples pode oferecer encode/decode round-trip.

## Validação temporal

Para todo command trace:

- ACT respeita next_activate;
- READ/WRITE só ocorre após activation delay;
- PRE respeita minimum active/write recovery;
- refresh exclusion é obedecida;
- bus turnaround respeita penalty.

Validar a sequência é mais forte que checar apenas latency final.

## Casos direcionados

### Row hit

Dois reads na mesma row/bank.

Esperado:
- primeiro abre row;
- segundo usa row existente;
- sem PRE/ACT no segundo sob open-page.

### Row conflict

Segundo read na mesma bank, row diferente.

Esperado:
- precharge;
- activate da nova row;
- column access somente após delays.

### Bank parallelism

Requests em banks distintos.

Esperado:
- overlap conforme shared constraints.

### Queue saturation

Mais requests que capacidade.

Esperado:
- backpressure;
- nenhuma request perdida.

### Refresh collision

Request chega durante refresh obrigatório.

Esperado:
- delay consistente com o modelo.

## Equivalência funcional

Timing mode precisa produzir os mesmos bytes finais que functional mode para a mesma sequência arquitetural legal.

Harness:

1. inicializar backing stores idênticos;
2. aplicar reference sequence;
3. submeter timed requests equivalentes;
4. executar até completion;
5. comparar read results e memory image.

Timing difere; data semantics não.

## Métricas

Contadores úteis:

- read/write requests;
- bytes transferred;
- row hits;
- closed-row misses;
- row conflicts;
- average/max queue depth;
- average read/write latency;
- channel/bank utilization;
- turnaround cycles;
- refresh-blocked cycles;
- oldest-request age;
- backpressure events.

Row-buffer hit rate:

    row_hit_rate = row_hits / column_requests

Queue delay:

    avg_queue_delay = sum(issue_time - arrival_time) / requests

Valores pertencem ao modelo configurado, não a um DIMM físico sem calibração.

## Níveis de fidelidade

Uma hierarquia útil:

1. **functional RAM** — ChrisVM atual;
2. **fixed-latency memory**;
3. **bank/row timing model**;
4. **DDR-specific command model**;
5. **PHY/electrical model**.

ChrisVM está no nível 1.

Um futuro modelo precisa declarar explicitamente seu nível para não confundir pedagogia com fidelity física.

## Limitações atuais

O source revisado não implementa:

- DRAM training;
- topology channel/rank/bank no PMM;
- DRAM command scheduling;
- timing constraints;
- row-buffer policy;
- refresh timing;
- ECC model;
- NUMA-aware allocation;
- controller contention;
- guest DRAM latency.

Esses conceitos são teoria e roadmap.

## Fronteira de roadmap

Sequência disciplinada:

1. preservar functional RAM como reference backend;
2. adicionar generic async memory interface;
3. fixed deterministic latency;
4. topology/address decoder;
5. bank open-row state;
6. ACT/PRE/READ/WRITE constraints;
7. finite queues + FIFO;
8. FR-FCFS + fairness;
9. read/write turnaround;
10. refresh;
11. integrar a future cache/timing CPU backend;
12. adicionar DMA requesters;
13. só então considerar ECC, NUMA experiments ou standard-specific calibration.

Cada etapa deve ser diferencialmente validável contra a semântica funcional.

## Registro de revisão

Este capítulo foi reconciliado com ChrisOS <code>main</code> na revisão <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>. Afirmações sobre implementação atual se restringem aos arquivos declarados. Topologia DRAM, scheduling e timing são teoria arquitetural e proposta futura para ChrisVM, não features da RAM guest atual.
