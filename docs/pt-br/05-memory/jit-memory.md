---
id: jit-memory
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/jit/jit.c
  - compiler/jit/jit.h
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_compile.h
  - compiler/jit/jit_emit.c
  - compiler/jit/jit_runtime.c
  - compiler/lang_pipeline.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/smp.c
  - tools/test_jit_vm.c
  - tools/test_jit_native.c
  - tools/test_tlb_proto.c
symbols:
  - jit_alloc
  - jit_emit
  - jit_seal
  - jit_free
  - jit_compile_image
  - jit_compile_image_locked
  - jit_set_sys_context
  - jit_sys_trampoline
  - mm_tlb_shootdown_range
  - mm_tlb_quarantine
depends_on:
  - virtual-memory
  - tlb
  - tlb-shootdown
  - resource-lifetime
  - spinlocks
related:
  - chrisc-clvm
  - compiler-pipeline
  - kernel-jobs-kthreads
  - address-spaces
---

# Memória executável, aliases JIT e W^X

## Escopo

Um JIT possui um problema de memória diferente de uma alocação comum.

Os bytes começam como dados escritos pelo compilador e depois passam a ser instruções buscadas pelo processador. Essa transição cruza:

- alocação física;
- alocação virtual;
- permissão de escrita;
- permissão de execução;
- visibilidade em TLB;
- execução concorrente em CPUs;
- unmap;
- reclamation segura dos frames.

O ChrisOS usa atualmente dois aliases virtuais para os mesmos frames físicos:

- buf->w: alias gravável no Higher-Half Direct Map usado para emissão e patch;
- buf->x: alias alto dedicado à execução nativa.

O alias executável não é inicialmente mapeado. O compilador escreve pelo HHDM e jit_seal cria depois o mapping de execução.

![Ciclo atual da memória JIT do ChrisOS](../../assets/diagrams/jit-memory-pt-br.svg)

O desenho separa os endereços de escrita e execução, porém ainda não implementa W^X estrito no nível do frame físico porque o alias HHDM gravável permanece acessível depois que o alias executável é criado.

## JitBuf

O objeto central é:

~~~c
typedef struct JitBuf {
    uint64_t phys;
    uint8_t *w;
    uint8_t *x;
    uint32_t used;
    uint32_t cap;
    uint32_t pages;
} JitBuf;
~~~

phys é a base da alocação física contígua.

w é o endereço usado para mutação pelo compilador.

x é o endereço usado para execução nativa.

used mede bytes emitidos.

cap é a capacidade total.

pages registra a quantidade de páginas.

Um JitBuf representa o mesmo recurso em três domínios:

~~~text
frames físicos
    |
    +-> alias HHDM gravável
    |
    +-> alias executável dedicado
~~~

## Alocação física

jit_alloc pede ao PMM:

~~~text
pmm_alloc_contig(buf->pages)
~~~

O header define:

~~~text
JIT_PAGES = 6144
JIT_MAX   = 6144 * 4096
          = 24 MiB
~~~

Se pages é zero ou maior que JIT_PAGES, o allocator bruto redefine para JIT_PAGES.

O caminho normal do compilador calcula um valor mais específico antes da alocação.

## Política de sizing

jit_compile_image_locked estima:

~~~text
need = bytecode_size * 64 + 262144
pages = ceil(need / 4096)
~~~

Depois limita:

~~~text
mínimo = 64 páginas
máximo = 6144 páginas
~~~

O mínimo é 256 KiB.

O fator cobre expansão para código nativo, patch tables e estruturas de dispatch.

É uma heurística de capacidade, não uma garantia de que qualquer programa caberá. Os emitters ainda verificam used + n contra cap.

## Consequência da contiguidade física

Backing contíguo simplifica o mapping.

A página executável i corresponde a:

~~~text
buf->phys + i * 4096
~~~

O custo é sensibilidade à fragmentação física.

Uma compilação grande pode falhar mesmo com RAM total suficiente se o PMM não encontrar um único run contíguo.

Uma implementação scatter-backed evitaria essa dependência, porém exigiria bookkeeping físico por página.

## Janela virtual do JIT

Os aliases executáveis começam em:

~~~text
JIT_VIRT_BASE = 0xffffffffc0000000
~~~

A janela possui:

~~~text
8192 páginas = 32 MiB
~~~

O comentário de source registra que uma localização JIT anterior compartilhava uma região ampla com kernel higher-half, LAPIC e outros mappings.

O comportamento antigo de mapping/TLB nessa região causou travamento durante setup.

A base atual foi movida para outro espaço de paging na arquitetura revisada.

## Registry virtual

O JIT mantém:

~~~text
JIT_VA_SLOTS = 128
~~~

Cada entry armazena:

- base virtual;
- número de páginas;
- flag used.

jit_va_alloc procura primeiro um entry livre com exatamente a mesma quantidade de páginas.

Se não encontra, avança g_jit_virt_next.

jit_va_free apenas marca o entry como livre.

Não há merge de ranges nem rewind do bump pointer.

## Fragmentação virtual

A reutilização exige igualdade de tamanho.

Um range liberado de 100 páginas não atende pedido de 99 ou 101 páginas.

Depois que o high-water mark alcança o fim dos 32 MiB, somente entries livres com page count exato podem ser reutilizados.

É possível, portanto, esgotar a janela mesmo com espaço virtual total ainda fragmentado em entries livres.

## Capacidade de metadata

Há somente 128 registros de VA.

Não existe árvore VMA, bitmap expandível ou estrutura dinâmica.

O limite de metadata é separado do limite de 32 MiB da janela.

O desenho é propositalmente simples.

## Alias gravável

Depois da alocação física, jit_alloc define:

~~~text
buf->w = bootinfo_phys_to_virt(buf->phys)
~~~

Esse é o alias pelo direct map.

jit_emit escreve bytes nessa região e incrementa used.

Patches do compilador também usam w.

O alias de execução não precisa de WRITE para nenhuma dessas operações.

## Alias executável

jit_alloc reserva a faixa virtual e armazena em x.

Ainda não instala PTE executável.

O código é gerado primeiro.

jit_seal publica os mappings depois.

## Permissões em jit_seal

Cada página é mapeada conceitualmente por:

~~~text
map_4k(exec_va, physical_page, MM_PRESENT)
~~~

Logo:

- PRESENT está ativo;
- WRITE está desligado;
- USER está desligado;
- NX está desligado.

O alias dedicado é supervisor-only e executável, porém não gravável por esse endereço.

Isso é melhor que um único mapping RWX.

## Por que ainda não é W^X estrito

W^X estrito precisa considerar todos os aliases do frame físico.

O alias de execução não é gravável.

Entretanto w continua apontando para os mesmos frames pelo HHDM e permanece usado como alias gravável.

jit_seal não revoga nem write-protect esse caminho.

Assim o mesmo frame físico está:

~~~text
writable via HHDM
executable via JIT VA
~~~

simultaneamente.

A descrição correta é:

> o ChrisOS separa aliases W e X, mas ainda não aplica W^X estrito ao frame físico.

Hardening completo precisaria incluir a política do direct map.

## Dependência do HHDM

jit.c não controla a construção completa do HHDM.

Ele recebe um endereço kernel através de bootinfo_phys_to_virt.

Portanto alterar apenas os flags do execution alias não elimina todas as permissões de escrita.

A política do direct map faz parte da superfície de segurança do JIT.

## Mappings anteriormente ausentes

O comentário em jit_seal registra um detalhe histórico importante.

As traduções executáveis ainda não existiam antes do seal.

map_4k instala cada PTE e executa INVLPG local.

Uma operação mais ampla de CR3/TLB usada no design anterior levou a falha da máquina durante o setup JIT.

O código atual prefere invalidation local na publicação.

## Seal versus teardown

Criar mapping novo e destruir mapping antigo possuem riscos diferentes.

No seal o endereço anteriormente estava not-present.

No free, uma CPU pode ainda possuir tradução executável antiga no TLB mesmo depois de o PTE ter sido removido.

Por isso o teardown precisa de protocolo cross-CPU mais forte.

## Instruction cache

jit_seal não chama uma rotina separada de flush de instruction cache.

O alvo atual é x86-64, cuja coerência de cache difere de arquiteturas em que um JIT precisa explicitamente limpar D-cache e invalidar I-cache.

Esse comportamento não deve ser copiado automaticamente para um backend ARM ou outra arquitetura.

A publicação de código precisa ser definida por arquitetura.

## Scratch global do compilador

jit_compile.c mantém estruturas globais:

- tabela bytecode-PC -> native offset;
- patch sites;
- patch targets;
- quantidade de patches;
- offsets compartilhados de fault/dispatch.

O próprio source diz que esse scratch é process-global.

Compilações simultâneas corromperiam essas estruturas.

## Lock de compilação

jit_compile_image protege a compilação inteira com g_jit_compile_lock.

O fluxo é:

~~~text
spin_lock
  -> preparar scratch
  -> emitir
  -> patch
  -> alocar backing quando necessário
  -> seal
spin_unlock
~~~

Esse lock é requisito de correção.

## Limite de concorrência do VA allocator

g_jit_va e g_jit_virt_next não possuem lock próprio.

No caminho normal, jit_alloc é chamado dentro de jit_compile_image_locked e portanto sob g_jit_compile_lock.

jit_free, porém, não adquire esse lock ao chamar jit_va_free.

O allocator virtual não deve ser considerado um allocator SMP genérico independente.

A correção atual depende da serialização e do lifecycle ao redor.

Se create/free JIT se tornarem livremente concorrentes, esse estado global precisará de proteção explícita.

## Emissão e patches

O compilador escreve instruções nativas através de w.

Branches são inicialmente emitidos com deslocamentos placeholder.

O compiler registra patch sites e targets, termina a geração e resolve os offsets.

Também grava endereços da dispatch table e do native blob.

Essas mutações acontecem antes do seal no fluxo normal.

O function pointer publicado usa x.

## Tabelas de tradução

O compilador mantém um offset nativo para posições de bytecode.

Limites atuais:

~~~text
JIT_MAX_PCS   = 1.048.576
JIT_MAX_PATCH = 131.072
~~~

São arrays globais estáticos.

O lock protege acesso concorrente, mas a capacidade continua fixa.

## Caminho fallback

Quando uma imagem não consegue usar a tradução nativa completa, emit_fallback produz um wrapper que chama o interpreter.

Mesmo esse wrapper segue:

~~~text
emit em w
seal em x
execução por x
teardown JIT
~~~

As regras de executable memory continuam valendo.

## Contexto de syscall por CPU

Código nativo precisa alcançar VM e contexto de usuário ao entrar em helpers.

Um ponteiro global seria incorreto em SMP.

jit.c mantém um array por CPU.

jit_set_sys_context grava o VM e o user pointer no slot da CPU atual.

jit_sys_trampoline consulta exatamente esse slot.

O comentário de source explica que um contexto global permitiria que VM A em uma CPU substituísse o contexto usado pela VM B em outra.

## Lifetime do contexto

Os ponteiros armazenados no contexto por CPU são borrowed references.

O JIT não se torna owner do VM nem do graphics/user context.

lang_pipeline configura o contexto imediatamente antes de chamar a função JIT.

O runtime precisa manter esses objetos vivos até o retorno da execução nativa.

## Teardown de JIT

jit_free executa teardown ordenado.

Para buffer com alias executável:

1. calcula range e número de páginas;
2. faz unmap de cada execution page;
3. chama mm_tlb_shootdown_range;
4. marca o registro virtual JIT como reutilizável;
5. libera frames físicos se reuse foi comprovado seguro;
6. caso contrário, envia os frames para MM quarantine;
7. limpa JitBuf.

A invariante é:

~~~text
nenhum frame físico volta ao PMM enquanto stale executable translations
ainda puderem apontar para ele
~~~

## Por que unmap não basta

Page table não é consultada em todo instruction fetch.

Uma CPU pode manter tradução antiga no TLB.

Se o frame for imediatamente reutilizado, um alias stale pode continuar executando bytes que já pertencem a outro subsystem.

A ordem segura é:

~~~text
unmap
  -> invalidar CPUs relevantes
  -> provar reuse seguro
  -> liberar frame
~~~

## Invalidation local

unmap_4k remove o PTE e executa INVLPG local.

jit_free faz isso página por página.

mm_tlb_shootdown_range depois executa o protocolo cross-CPU.

A CPU iniciadora pode invalidar o range mais de uma vez.

É comportamento conservador.

## Completion do shootdown

O protocolo TLB usa gerações e acknowledgements por CPU.

Reuse é liberado quando todos os participantes necessários chegaram ao estado seguro.

Para CPU fenced, o protocolo exige condições adicionais de flush/halt.

Se isso não é provado, mm_tlb_shootdown_range falha.

jit_free usa exatamente esse resultado para decidir free versus quarantine.

## Quarantine

Em sucesso:

~~~text
pmm_free_contig
~~~

Em falha:

~~~text
mm_tlb_quarantine
~~~

Nos dois casos o objeto JIT deixa de existir logicamente.

A diferença é se os frames já podem ser reutilizados fisicamente.

## Overflow de quarantine

A quarantine possui capacidade finita.

Quando está cheia e o extent ainda não é seguro, MM não devolve os frames ao PMM.

Isso cria leak intencional.

A prioridade é:

~~~text
perder memória > executar stale code sobre memória reutilizada
~~~

## Reuso de VA

jit_va_free libera o registro virtual após a tentativa de shootdown.

Outro JIT pode futuramente usar a mesma faixa com frames diferentes.

Por isso stale translations do lifecycle anterior precisam ser resolvidas corretamente.

O protocolo protege não apenas physical reuse, mas também o significado do endereço virtual reutilizado.

## Privilégio

A janela JIT fica no upper kernel half.

O mapping não possui MM_USER.

O código gerado executa em privilégio de kernel.

Um bug no emitter ou patcher não está isolado por ring 3.

O JIT faz parte do trusted computing base.

## Bounds checks gerados

O JIT emite checks explícitos para guest-memory accesses.

Loads e stores verificam offset contra vm->mem_size e encaminham acessos inválidos para fault paths.

Isso protege a abstração CLVM quando o código é gerado corretamente.

Não protege contra instruções nativas incorretas produzidas por bug do próprio compilador.

## Rollback de falha

Existem caminhos explícitos.

Se a alocação física funciona e VA allocation falha, jit_alloc devolve o run ao PMM.

Se emissão nativa falha depois, jit_compile_image_locked chama jit_free.

Centralizar o destructor evita duplicação de teardown de mappings e frames.

## Validação

O repositório possui vários testes JIT:

- test_jit_vm;
- test_jit_native;
- testes de load/store e 64-bit;
- ferramentas Doom para smoke, patch e comparação diferencial.

Esses testes verificam semântica gerada.

Os testes de TLB validam a outra metade:

- reuse bloqueado antes de remote ack;
- fencing sozinho não basta;
- halt sem invalidation não basta;
- reuse só é permitido depois do estado de segurança requerido.

JIT correctness depende das duas camadas.

## Performance

Os dois aliases apontam para os mesmos frames.

Isso evita copiar código de um buffer RW temporário para outro buffer executável.

Custos:

- PMM contíguo;
- lock global de compilação;
- mapping página por página;
- INVLPG no seal;
- unmap página por página;
- shootdown cross-CPU no free.

Para código nativo de longa duração, o custo de compilação pode ser amortizado.

Para código efêmero, lifecycle pode custar mais que o ganho da execução JIT.

## Limitações atuais

Na revisão analisada:

- código JIT executa em kernel privilege;
- W^X estrito por frame físico não existe;
- alias HHDM gravável permanece após seal;
- VA window possui 32 MiB;
- metadata possui 128 slots;
- range livre só é reutilizado para page count idêntico;
- não existe coalescing/rebobinamento do bump pointer;
- backing físico precisa ser contíguo;
- scratch de compilação é globalmente serializado;
- VA allocate/free não é isoladamente thread-safe como allocator geral;
- não existe interface architecture-neutral para instruction-cache publication;
- quarantine pode reter frames indefinidamente quando reuse não é comprovado.

Esses são fatos do código atual.

## Modelo futuro de W^X mais forte

Uma arquitetura mais restrita poderia usar:

~~~text
aloca frames
  -> mapping temporário RW + NX
  -> emit e patch
  -> remove ou write-protect mapping gravável
  -> invalidation necessária
  -> mapping RX
  -> execução
  -> unmap RX
  -> shootdown
  -> reclamation
~~~

Com HHDM permanente, W^X verdadeiro também exige mudar a permissão do direct map para esses frames ou não usar um alias HHDM permanentemente gravável.

Isso é direção de roadmap, não comportamento implementado.

## Fronteira de revisão

Este capítulo foi reconciliado com ChrisOS main na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

O lifecycle atual é:

~~~text
frames físicos contíguos
  -> alias HHDM gravável
  -> emissão e patch nativos
  -> alias executável supervisor-only não gravável
  -> execução por x
  -> remoção dos mappings executáveis
  -> TLB shootdown cross-CPU
  -> PMM free quando seguro
     ou quarantine quando segurança ainda não foi provada
~~~

A implementação já trata reclamation executável como problema de lifetime cross-CPU, enquanto W^X estrito e hardening do allocator continuam pendentes.
