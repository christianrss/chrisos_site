---
id: systems-algorithms
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.c
  - kernel/metal/job.c
  - kernel/metal/mm.c
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - kernel/gfx/virtq.c
  - kernel/gfx/tile.c
  - compiler/chrisc/chrisc.c
  - chrisvm/machine/machine.h
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/debug/trace.c
symbols:
  - pmm_alloc
  - pmm_alloc_contig
  - job_submit
  - job_worker_once
  - ChrisMachine
  - ChrisCpu
  - chris_decode
depends_on:
  - data-structures
related:
  - physical-memory
  - kernel-jobs-kthreads
  - chrisfs
  - virtio-gpu-virgl
  - compiler-pipeline
  - chrisvm-chriscpu
---

# Algoritmos utilizados pelo ChrisOS

<div class="abstract">
Este capítulo é um mapa algorítmico da revisão atual da branch <code>main</code> do ChrisOS. Ele não atribui nomes de livro-texto por semelhança. Cada seção identifica a representação realmente visível no source, a operação executada, o invariante principal, as características de complexidade e o modelo de concorrência. O objetivo é ligar teoria de estruturas de dados ao comportamento concreto de kernel, filesystem, gráficos, compilador e emulador.
</div>

## Como ler o atlas

Um mesmo algoritmo pode ser adequado em um subsistema e inadequado em outro. O ChrisOS atual utiliza várias estruturas propositalmente limitadas: arrays, bitmaps e rings. Elas frequentemente trocam lookup sofisticado por uso de memória previsível e implementação simples.

| Subsistema | Estrutura / algoritmo atual |
|---|---|
| PMM | bitmap por página, cursor de busca, scan de runs, máscara DMA32 |
| jobs | FIFO circular limitada sob spinlock |
| page tables | walk hierárquico x86-64 de profundidade fixa |
| TLB | protocolo de geração/acknowledgement para shootdown |
| ChrisFS allocation | bitmap com allocation hint por mount |
| blocos de arquivo | direct + indirect + double/triple indirect |
| durabilidade ChrisFS | journal pequeno BEGIN/COMMIT + replay |
| VirtIO | split ring de descriptor/available/used |
| gráficos software | tile partition/binning + z-buffer |
| ChrisC | tabelas limitadas e parsing/codegen manual |
| ChrisCPU | decoder de prefix/opcode seguido por execute explícito |
| trace ChrisVM | ring circular fixo |
| buses ChrisVM | arrays pequenos de slots com range matching |

## PMM: bitmap e cursor

<code>kernel/metal/pmm.c</code> armazena estado de páginas em <code>pmm_bitmap</code>. Um bit representa uma página física.

Testar uma página conhecida é O(1). Alocar exige encontrar run livre.

<code>scan_usable_for_run(count, from_phys)</code> percorre regiões utilizáveis vindas do mapa de memória do Limine, alinha limites e varre o bitmap. Existe uma otimização importante: quando o scan está alinhado a byte e o byte do bitmap vale <code>0xFF</code>, oito páginas ocupadas são puladas de uma vez.

Fluxo comum:

    entrar na seção crítica do PMM
        ↓
    scan a partir de pmm_cursor
        ↓ se falhar
    wrap e scan a partir de zero
        ↓
    marcar página/run como usado
        ↓
    avançar pmm_cursor
        ↓
    sair da seção crítica

O cursor é hint de próxima busca, não índice de free list. Pior caso permanece O(P), com P igual ao número de páginas representadas.

### Invariantes

- um bit corresponde a uma página;
- páginas reservadas/não utilizáveis permanecem ocupadas;
- contadores acompanham usado/livre;
- run escolhido é marcado sob sincronização do PMM;
- cursor indica início da próxima busca, não necessariamente página livre.

### Concorrência

O PMM usa spinlock, profundidade de recursão por CPU e flags de interrupção salvas. A recursão existe porque callback no mesmo CPU pode reivindicar páginas enquanto um scan já possui o lock. Interrupções ficam desabilitadas na aquisição externa.

Isso é mais preciso que dizer apenas “o allocator é thread-safe”.

## Alocação física contígua

<code>pmm_alloc_contig</code> enumera runs livres com <code>pmm_foreach_free_run</code> e escolhe o primeiro que atende ao tamanho, reivindicando a região. Há fallback de scan desde zero.

É first-fit sobre runs descobertos no bitmap.

Pior caso O(P). Não há extent tree balanceada ou buddy hierarchy; alocações grandes podem falhar por fragmentação apesar de memória total suficiente.

A vantagem é baixo custo de metadados.

## Reserva DMA32

O PMM separa uma região fixa de 16 páginas abaixo de 4 GiB. Disponibilidade é representada por máscara de bits.

Para pedido de k páginas, constrói-se máscara de k bits e ela é deslocada pelas posições possíveis até encontrar sequência livre.

Como o universo é rigidamente limitado a 16 páginas, o custo é constante no tamanho do sistema.

É um exemplo de estrutura especializada pequena em vez de reutilizar cegamente o algoritmo geral.

## Fila de jobs: FIFO circular

<code>kernel/metal/job.c</code> define:

- <code>Job g_queue[JOB_QUEUE_CAP]</code>;
- <code>g_q_head</code>;
- <code>g_q_tail</code>;
- <code>g_q_count</code>;
- spinlock.

Enqueue escreve no tail e faz:

    tail = (tail + 1) mod capacidade

Dequeue lê head e avança da mesma maneira.

Ambos O(1), sem allocation. Saturação é explícita: <code>job_submit</code> falha quando count atinge capacidade.

Jobs são registros pequenos com function pointer e arg. Ring limitado mantém storage estável e evita allocator no worker path.

O trade-off é fila cheia. Produtores precisam tratar backpressure.

## Algoritmo do worker

<code>job_worker_once</code> atende primeiro o protocolo de TLB, retira no máximo um job, libera o lock e então executa a função.

O loop:

1. verifica se CPU foi fenced;
2. processa TLB polling;
3. habilita interrupções de AP quando permitido;
4. retira/executa um job;
5. executa <code>pause</code>.

É shared queue simples, não work stealing per-CPU.

A arquitetura é fácil de provar, mas pode virar ponto de contenção com muitos CPUs.

## Page-table walk

Tradução x86-64 percorre hierarquia de profundidade fixa. <code>kernel/metal/mm.c</code> mapeia, desmapeia e traduz percorrendo tabelas.

Em relação à quantidade total de mappings, o walk é O(1), pois a arquitetura limita níveis. Porém cada nível pode causar acesso dependente à memória.

Estruturalmente, page table é uma radix tree esparsa cujo fan-out é definido pelo encoding x86-64.

Não deve ser confundida com BST de ponteiros em C.

## TLB shootdown: geração e acknowledgement

Após mudar mapping, CPUs remotos podem manter traduções antigas. O ChrisOS usa geração/seen coordenados com IPI e fallback de polling.

    alterar mapping
        ↓
    publicar nova geração
        ↓
    notificar CPUs participantes
        ↓
    cada CPU invalida / observa pedido
        ↓
    cada CPU registra geração vista
        ↓
    updater aguarda acknowledgements
        ↓
    frame pode ser reutilizado

O invariante é temporal: frame não pode ser reciclado enquanto CPU remota ainda puder traduzir mapping antigo para ele.

O problema principal não é Big-O, e sim ordering, membership e lifetime.

## ChrisFS: bitmap com allocation hint

ChrisFS registra blocos em bitmap. Uma implementação anterior reiniciava scan em zero em toda allocation, degradando cópia de arquivos grandes.

O atual <code>Cfs.alloc_hint</code> registra o próximo índice a tentar.

O allocator começa pelo hint, procura bloco livre e avança o hint após sucesso. Pior caso continua O(B) em data sectors, mas o comportamento típico deixa de visitar repetidamente o prefixo já ocupado.

É melhoria algorítmica sem troca da estrutura básica.

## Endereçamento de blocos em inode

O inode do ChrisFS contém referências direct, indirect, double indirect e triple indirect.

A hierarquia troca tamanho pequeno do inode por capacidade maior.

    inode
     ├─ direct → blocos de dados
     ├─ indirect → tabela → dados
     ├─ double → tabela → tabela → dados
     └─ triple → três níveis → dados

Blocos iniciais possuem resolução direta. Blocos mais distantes exigem leituras adicionais de pointer tables.

A profundidade é limitada pelo formato, portanto assintoticamente constante dentro dos limites, mas custo de I/O varia com o nível e o cache.

## Journal do ChrisFS

O journal usa estados como <code>JNL_BEGIN</code>, <code>JNL_COMMIT</code> e vazio e possui quantidade máxima de records.

Na recuperação:

- vazio não exige ação;
- BEGIN incompleto é descartado/limpo conforme o protocolo;
- COMMIT provoca replay dos records e posterior limpeza.

Não é uma transaction engine genérica. É recuperação limitada de metadados para o modelo do ChrisFS.

Custo O(R), com R limitado por <code>JNL_MAX_REC</code>.

## Cache do filesystem

O repositório descreve cache pequeno de setores com número limitado de linhas e política semelhante a LRU por clock.

Como a capacidade é deliberadamente pequena, mesmo lookup linear O(C) tem bound pequeno e previsível.

Manter tree/hash poderia custar mais complexidade que benefício nessa escala.

## VirtIO split ring

Uma split virtqueue possui:

1. descriptor table;
2. available ring escrito pelo driver;
3. used ring escrito pelo device.

O driver constrói descriptor chain, publica índices no available ring respeitando memory ordering, atualiza o available index e notifica o device.

Completion observa used index e recupera o descriptor retornado.

O invariante central é ownership e ordem:

    preencher descriptor
        ↓
    memory barrier
        ↓
    publicar available entry/index
        ↓
    device consome
        ↓
    device publica used entry/index
        ↓
    driver observa após barrier

Reordenar passos pode expor descriptor parcialmente inicializado.

## Gráficos: tiles e binning

O raster software divide framebuffer em tiles fixos. Triangles são associados a tiles para que jobs trabalhem sobre regiões menores.

Para W×H e tile S:

    tiles_x = ceil(W / S)
    tiles_y = ceil(H / S)

Binning reduz região de trabalho e cria unidade natural de paralelismo.

O invariante de concorrência é crítico: dois jobs não devem gravar simultaneamente os mesmos pixels/depth de um tile sem sincronização. A auditoria gráfica atual ainda acompanha esse risco.

## Z-buffer

Depth buffer armazena depth por pixel.

Para cada fragmento:

1. calcula/interpola depth;
2. compara com o depth atual;
3. se estiver mais próximo na convenção adotada, atualiza depth e color.

O teste é O(1) por fragmento, mas consome largura de banda. O custo total depende de cobertura e overdraw.

A estrutura é array denso alinhado espacialmente com framebuffer para lookup constante.

## Estruturas do ChrisC

<code>compiler/chrisc/chrisc.c</code> mantém tabelas limitadas para symbols e outros estados de compilação. Não é correto documentá-lo como pipeline moderno com symbol hash e grafos sem que o source demonstre isso.

Lookup em arrays limitados pode ser O(N) no número de símbolos. Na escala atual, storage fixo evita containers gerais e dependência de allocator.

O volume de compiladores deve detalhar tokenizer, parser, representação de tipos e codegen separadamente.

## Decoder do ChrisCPU

<code>chrisvm/cpu/emulator/decode.c</code> realiza decode explícito de x86.

    consumir prefixes legacy/REX
        ↓
    determinar operand/address size
        ↓
    ler opcode primário
        ↓
    opcional opcode 0F
        ↓
    ModR/M + SIB
        ↓
    displacement/immediate
        ↓
    preencher ChrisInsn
        ↓
    execute consome forma normalizada

A implementação atual não é um decoder x86 completo orientado por tabela; grande parte usa dispatch condicional explícito por famílias de opcode.

O comprimento máximo da instrução é limitado pela arquitetura, então decode por instrução tem bound constante, embora com diferentes fatores constantes.

## Slots de I/O e MMIO do ChrisVM

<code>ChrisMachine</code> contém arrays fixos de slots de I/O e MMIO. Cada slot registra intervalo e callbacks/context.

Com quantidade pequena e fixa, localizar range pode usar scan linear O(S), sendo S limitado por constantes como <code>CHRIS_IO_MAX</code> e <code>CHRIS_MMIO_MAX</code>.

Antes de haver centenas de devices, isso é mais simples que interval tree.

Se a VM crescer muito, a estrutura deve ser reavaliada.

## Ring de trace do ChrisVM

Cada <code>ChrisCpu</code> possui <code>ChrisTraceEnt ring[CHRIS_TRACE_RING]</code>, índice e count.

<code>chris_trace_push</code> avança o índice e limita count à capacidade. Depois de cheia, a estrutura sobrescreve entradas mais antigas.

Append é O(1), sem allocation e com memória limitada, apropriado para diagnóstico.

O trade-off é perda intencional do histórico mais antigo.

## Tabela cruzada

| Operação | Representação | Pior caso | Allocation | Sincronização |
|---|---|---:|---|---|
| PMM single page | bitmap + cursor | O(P) | não | PMM spinlock/IRQ |
| PMM DMA32 | bit mask de região fixa | constante limitada | não | PMM |
| enqueue/dequeue de job | ring | O(1) | não | spinlock da fila |
| page-table walk | radix hierarchy fixa | O(1) | somente ao criar mappings | MM/protocolo |
| bloco ChrisFS | bitmap + hint | O(B) | metadata | lock CFS |
| resolver bloco de inode | direct/indirect | profundidade limitada | growth pode alocar | lock CFS |
| replay journal | records limitados | O(R) | scratch limitado | serialização FS |
| alocar/preencher cadeia VirtIO | links + descritores | O(chain) | pool limitado | propriedade do chamador |
| publicar uma cabeça VirtIO | split ring | O(1) local | função não aloca | barreiras/propriedade |
| depth test | depth array | O(1)/fragmento | buffer preexistente | ownership do tile |
| decode ChrisCPU | byte stream → ChrisInsn | constante limitada | não | CPU-local |
| trace append | ring circular | O(1) | não | CPU-local |

## Quando trocar algoritmos

O atlas descreve o presente, não determina que todo design deva permanecer.

Limiares plausíveis:

- memória maior/fragmentada pode justificar bitmap hierárquico, buddy ou extents;
- scheduler altamente paralelo pode exigir filas per-CPU e work stealing;
- muitos ranges MMIO podem justificar interval tree;
- compilação maior pode justificar symbol hash e arenas;
- filesystem maior pode exigir extent trees/B-tree;
- gráficos maiores podem exigir binning espacial mais sofisticado e estruturas GPU-resident.

Mudanças devem seguir medição e invariantes, não preferência estética.

A regra permanece: representação, invariante, algoritmo, complexidade, ownership e concorrência precisam ser documentados juntos.
