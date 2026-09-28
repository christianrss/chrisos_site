---
id: hhdm
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - pmm_selftest
  - mm_selftest
  - map_mmio_page
  - mm_virt_to_phys
depends_on:
  - boot-information
  - x86-64-memory-privilege
  - physical-memory
related:
  - pmm-algorithms
  - virtual-memory
  - page-table-layout
  - buses-mmio-dma
---

# Higher-half direct map

## Escopo

O kernel precisa frequentemente dereferenciar RAM física que veio do PMM, contém page table, armazena estrutura DMA ou pertence a outro subsistema de baixo nível. Código x86-64 comum não faz load diretamente de endereço físico: instruções usam endereços virtuais traduzidos pelas page tables ativas.

O ChrisOS usa o **higher-half direct map (HHDM)** fornecido pelo Limine. O bootloader constrói uma região virtual em que RAM física comum pode ser alcançada por um offset virtual fixo. O ChrisOS recebe esse offset no boot e o usa para transformar endereço físico de RAM em alias virtual de kernel.

A relação conceitual é:

```text
virtual_hhdm = fisico + hhdm_offset
```

A aritmética é simples. A validade do resultado não é. O endereço só pode ser dereferenciado quando o bootloader realmente mapeou aquele range físico com semântica adequada. Em especial, somar HHDM a um endereço MMIO não cria mapping correto para device.

![RAM física, offset HHDM e o caminho separado para MMIO](../../assets/diagrams/hhdm-address-translation-pt-br.svg)

É necessário separar três conceitos:

- ownership do endereço físico;
- tradução virtual através do HHDM;
- mapping de devices/MMIO com atributos específicos.

## Por que usar direct map

Sem direct map, cada frame físico recebido pelo kernel poderia exigir reserva de endereço virtual temporário, instalação de PTE, acesso e remoção posterior do mapping.

O HHDM oferece alias estável:

```text
frame físico P
      |
      | + offset HHDM
      v
endereço virtual V do kernel
      |
      | page tables preparadas pelo bootloader
      v
mesmo frame físico P
```

Isso é útil cedo no boot porque:

- PMM já pode devolver frames antes de existir heap;
- page-table code precisa dereferenciar páginas que armazenam tabelas;
- self-tests conseguem escrever em RAM recém-alocada;
- heap transforma arenas físicas em ponteiros de kernel;
- não é necessário manter temporary mapper apenas para acessar RAM comum.

HHDM é mecanismo de addressability, não allocator de ownership.

## Request do Limine e contrato de boot

`bootinfo.c` declara request HHDM do Limine dentro de `.limine_requests`. Em `bootinfo_init`, resposta ausente causa panic.

O offset recebido é armazenado em:

```text
info.hhdm_offset = hhdm->offset
```

Depois o bootinfo é marcado ready.

O kernel também exige framebuffer, memory map e resposta multiprocessor antes de considerar a camada de boot completa. HHDM faz parte do contrato obrigatório de inicialização atual, não é otimização opcional.

O valor do offset é escolhido pelo bootloader. O source revisado não fixa uma constante única de base HHDM.

## Helper de conversão

A API pública executa:

```c
uint64_t bootinfo_phys_to_virt(uint64_t phys) {
    if (!bootinfo_ready) {
        panic(...);
    }
    return phys + info.hhdm_offset;
}
```

Isso centraliza a base do HHDM e impede uso antes de `bootinfo_init`.

O helper, porém, não verifica se o endereço físico pertence a RAM normal, se está atualmente alocado pelo PMM ou se aparece no memory map. Depois do check de readiness, ele apenas soma.

O contrato correto é:

> calcular o endereço virtual onde o HHDM do Limine representa aquele endereço físico, assumindo que o range físico seja válido para acesso pelo direct map.

Não é uma função genérica “torne qualquer endereço físico dereferenciável”.

## HHDM versus identity mapping

Direct map não significa que endereço virtual seja igual ao físico.

Identity mapping obedeceria:

```text
virtual = físico
```

enquanto HHDM obedece:

```text
virtual = físico + offset
```

A diferença é relevante porque um endereço físico numericamente válido pode não ser ponteiro válido do kernel. Ambientes de firmware às vezes possuem identity mappings e podem esconder bugs: cast acidental de físico para ponteiro parece funcionar até o kernel operar somente no higher half.

O ChrisOS precisa manter essa distinção conceitual mesmo que ambos os valores sejam representados como `uint64_t`. Frame devolvido pelo PMM deve ser convertido ou explicitamente mapeado antes de dereference em C.

## Dependência da ordem de boot

A ordem funcional é:

```text
Limine estabelece page tables e HHDM
    -> kernel entra
    -> bootinfo_init valida resposta HHDM
    -> bootinfo_ready = 1
    -> PMM inicializa usando memory map
    -> PMM/heap/MM podem usar bootinfo_phys_to_virt
```

Usar o helper antes disso é violação de invariante e causa panic.

Isso também mostra que o PMM não cria o HHDM. O direct map já existe antes de `pmm_init`; o allocator apenas o consome.

## HHDM e PMM

O PMM trabalha em frames físicos.

`pmm_selftest` aloca páginas, converte cada endereço com `bootinfo_phys_to_virt`, escreve assinaturas diferentes pelos aliases HHDM e lê novamente.

Isso valida a cadeia:

```text
memory map USABLE
   -> PMM libera frame
   -> pmm_alloc reclama endereço físico
   -> HHDM gera endereço virtual de kernel
   -> load/store alcança a mesma RAM
```

Acesso HHDM bem-sucedido não prova que o PMM deveria possuir aquele frame. Os dois contratos precisam ser válidos: range precisa ser RAM mapeada e ownership precisa permitir uso.

## HHDM e construção das page tables

Page tables são armazenadas em frames físicos. O hardware espera endereços físicos nas entradas, enquanto o código C precisa de ponteiros virtuais para ler e escrever os bytes da tabela.

O padrão é:

```text
PTE guarda endereço físico
implementação precisa de ponteiro para os bytes
ponteiro = HHDM(endereço físico)
```

Por isso direct map simplifica fortemente MMU code inicial.

Virtual e físico pertencem a namespaces diferentes. Colocar um ponteiro HHDM dentro de PTE que espera frame físico quebraria tradução. Dereferenciar endereço físico bruto como ponteiro C também não significa “acessar memória física”; a CPU trataria o número como endereço virtual.

## HHDM não é mapping MMIO

O limite mais explícito aparece no Local APIC.

O próprio ChrisOS registra que:

```text
HHDM + 0xFEE00000 não é mapping MMIO válido; não dereferenciar
```

A camada de boot também examina o memory map e entra em panic se o endereço físico LAPIC aparecer classificado como `LIMINE_MEMMAP_USABLE`.

Devices podem exigir:

- mapping virtual dedicado;
- cache-disable ou write-through;
- permissões específicas;
- regras de ordering;
- ranges nem sequer cobertos pelo direct map.

O ChrisOS usa `map_mmio_page`, que reserva endereço na janela MMIO e instala flags como `MM_PWT`, `MM_PCD` e `MM_NX`.

Portanto:

```text
aritmética HHDM != política de mapping MMIO
```

## Nuance do framebuffer

Framebuffer também não é “RAM livre comum”.

O Limine fornece endereço virtual do framebuffer e o memory map classifica sua memória separadamente de USABLE. O PMM mantém esses frames indisponíveis para alocação geral.

Gráficos devem usar o mapping fornecido/validado para framebuffer em vez de inferir que qualquer endereço físico de framebuffer é frame PMM normal.

Addressability e allocatability são propriedades diferentes.

## Soma e overflow

A conversão é uma soma `uint64_t`:

```text
virt = phys + offset
```

O helper atual não faz check explícito de overflow nem de canonical address.

No contrato esperado do Limine, o bootloader fornece offset válido e mapeia o range suportado em endereços canônicos de higher half.

O ChrisOS delega essa garantia de layout ao ambiente de boot.

Uma abstração mais defensiva poderia validar:

- teto físico suportado;
- overflow aritmético;
- forma canônica x86-64;
- classe do range no memory map.

A implementação atual permanece menor.

## Endereços canônicos x86-64

Nem todo valor de 64 bits é endereço virtual legal. Dependendo do modo de paginação, apenas parte dos bits participa do walk e os bits superiores precisam obedecer canonical sign extension.

Logo higher-half map precisa ocupar região canônica.

HHDM não significa simplesmente “ligar o bit mais alto”. É um conjunto de page-table mappings em que intervalo virtual alto aponta para RAM física correspondente.

O ChrisOS não reconstrói essas entradas durante `bootinfo_init`; ele consome o ambiente criado pelo Limine antes da entrada no kernel.

## Relação com CR3 ativo

Um endereço HHDM só funciona se o address space ativo contiver mappings compatíveis do kernel.

`mm_clone_kernel_space` copia a metade superior do PML4 do kernel ao criar address space de processo.

Isso mantém HHDM e outros mappings privilegiados disponíveis enquanto CR3 de processo está ativo.

É um invariante importante para syscall, exception e memory management: trocar para processo não pode fazer a infraestrutura de kernel desaparecer.

## Lifetime do HHDM

A arquitetura atual trata o direct map do Limine como infraestrutura persistente.

Não existe no fluxo revisado uma fase que destrua o HHDM e migre todos os callers para outra base.

Self-tests do PMM, arenas de heap e acesso a page tables dependem dessa persistência.

Uma futura reconstrução completa das page tables precisaria preservar o direct map ou atualizar todos os locais que convertem físico em ponteiro.

## Tradução reversa é outro problema

O helper HHDM resolve apenas físico -> virtual HHDM.

Perguntar “qual físico está por trás deste endereço virtual arbitrário?” é diferente. O virtual pode ser:

- mapping do executável do kernel;
- página de processo;
- framebuffer;
- janela MMIO;
- outro alias.

O ChrisOS possui `mm_virt_to_phys`, que percorre as page tables e reconhece leaves grandes.

Para endereço sabidamente HHDM, subtrair offset pode fazer sentido dentro do contrato. Para virtual genérico, a resposta correta vem do page-table walk.

## Aliasing

Um frame físico pode ter mais de um alias:

```text
frame físico P
  -> alias HHDM
  -> mapping user/process
  -> mapping de teste do kernel
```

Todos apontam para os mesmos bytes.

`mm_selftest` mapeia um frame PMM em endereço virtual de teste, escreve pelo alias e verifica o valor através do HHDM.

Aliasing afeta:

- cache/coherence;
- permissões;
- invalidação de TLB;
- lifetime.

Liberar ownership físico enquanto qualquer alias ainda está utilizável é unsafe.

## Atributos de memória e aliases

Mapear o mesmo físico com tipos de cache incompatíveis pode ser problemático. RAM comum e registradores MMIO possuem requisitos diferentes.

Isso reforça por que HHDM não deve ser usado como alias universal de device.

O caminho MMIO atual instala flags de cache específicas. Os atributos do HHDM vêm das page tables criadas pelo bootloader e pertencem ao contrato de RAM/direct map.

## Segurança

O HHDM expõe RAM física dentro do espaço virtual privilegiado do kernel. User mode não pode ganhar acesso simplesmente porque process address spaces compartilham a metade superior do PML4.

Permissões supervisor das PTEs mantêm essa região fora do acesso de ring 3.

Se mappings HHDM fossem marcados user-accessible por engano, um processo poderia alcançar RAM arbitrária e contornar isolamento.

Logo a segurança do direct map depende de privilege bits, não apenas do fato de o endereço ser “alto”.

## Desempenho

No código fonte, conversão físico -> HHDM custa apenas soma inteira.

O acesso real continua passando por TLB, page tables e caches da CPU.

Benefícios:

- elimina temporary mapping por frame;
- fornece ponteiros estáveis para RAM de kernel;
- reduz page-table churn no early memory management.

Custos:

- ocupa grande região virtual;
- exige mappings de kernel consistentes entre address spaces;
- aumenta o impacto de um endereço físico incorretamente confiado.

HHDM remove trabalho de software para criar mappings temporários; não remove MMU hardware.

## Validação atual

Evidências no source incluem:

- boot falha se HHDM Limine estiver ausente;
- offset escolhido é impresso;
- helper rejeita uso antes de bootinfo;
- self-test do PMM escreve assinaturas por HHDM;
- self-test de MM compara mapping virtual de teste e alias HHDM do mesmo frame;
- bootinfo registra explicitamente que LAPIC + HHDM não deve ser dereferenciado como MMIO.

Isso valida fronteiras úteis, mas não prova exaustivamente que todo byte abaixo do teto PMM está mapeado pelo bootloader.

## Modos de falha

Falhas relevantes:

- resposta HHDM ausente;
- conversão antes de bootinfo;
- usar HHDM em endereço MMIO;
- confundir ponteiro virtual com físico em PTE;
- trocar para CR3 sem mappings superiores necessários;
- liberar frame PMM enquanto alias continua em uso;
- manter caller HHDM após futura remoção do direct map.

A maioria é violação de contrato arquitetural, não simples erro de soma.

## Limitações atuais

A abstração é deliberadamente mínima:

- um único offset global fornecido pelo bootloader;
- assinatura não diferencia tipo “RAM physical” de “MMIO physical”;
- sem check explícito de overflow/canonical address;
- sem consulta por range confirmando cobertura HHDM;
- sem teardown/remapping dinâmico;
- sem múltiplas regiões direct-map.

O modelo é suficiente para o kernel atual desde que os callers respeitem a fronteira RAM/device.

## Mapa de fonte

`kernel/metal/bootinfo.c` declara request HHDM, valida a resposta, armazena/loga o offset e implementa `bootinfo_phys_to_virt`.

`kernel/metal/pmm.c` usa HHDM no self-test de RAM física.

`kernel/metal/mm.c` implementa mapping MMIO dedicado, virtual-to-physical e self-test de aliases.

As afirmações de implementação foram reconciliadas com ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
