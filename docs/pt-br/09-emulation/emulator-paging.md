---
id: emulator-paging
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/boot.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_translate
  - canonical
  - read_pte
  - write_pte
  - chris_va_read
  - chris_va_write
  - install_tables
depends_on:
  - emulator-exceptions
  - x86-64-memory-privilege
  - paging-virtual-memory
related:
  - chrisvm-memory-map
  - chrisvm-chriscpu
  - higher-half-kernel
---

# Paginação de quatro níveis e tradução de memória virtual no ChrisCPU

## Escopo

O ChrisCPU implementa um page-table walker x86-64 compacto em cpu/emulator/mmu.c. O walker traduz endereços virtuais do guest em endereços físicos modelados e aplica um subconjunto útil das permissões de paginação de long mode. Ele suporta páginas comuns de 4 KiB e large pages de 2 MiB e 1 GiB, acompanha os bits Accessed e Dirty, modela proteção de escrita do supervisor por CR0.WP, aplica permissão user/supervisor e implementa checks de execução NX quando EFER.NXE está habilitado.

O mesmo módulo também implementa os wrappers de leitura e escrita virtual usados por instruction fetch, operandos, acesso a descriptor tables e construção de exception frames. Esses wrappers traduzem um chunk limitado por página de cada vez e convertem os resultados da tradução em exceções do guest ou saídas para o monitor.

A implementação é deliberadamente menor que uma MMU Intel/AMD completa. Não há TLB, PCID, paginação de cinco níveis, SMEP/SMAP, protection keys ou validação completa de reserved bits. Alguns gaps conhecidos são fixados pela suíte de testes da documentação para que mudanças futuras não invalidem silenciosamente a fronteira documentada.

Este capítulo descreve a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Caminho de identidade com paginação desabilitada

A primeira condição de chris_translate verifica CR0.PG. Se paging estiver limpo, a tradução é direta:

    physical = virtual

Nenhuma memória de page table é lida e nenhum bit de permissão é interpretado.

O teste independente do contrato MMU verifica tanto o resultado identidade quanto a ausência de leituras físicas de page tables nesse caminho.

Esse comportamento é útil para testes isolados, embora o chris_boot normal configure paginação antes de iniciar a execução do guest.

## Canonicalidade de endereço

Com paging habilitado, o ChrisCPU aplica primeiro o teste de endereço canônico de 48 bits do long mode. O endereço virtual é deslocado 47 bits e somente dois valores são aceitos:

    top == 0
    ou
    top == 0x1ffff

Portanto, o bit 47 precisa ser estendido por sinal até os bits 63..48.

Um endereço não canônico retorna um resultado interno distinto, menos dois. chris_va_read e chris_va_write convertem esse retorno em #GP com error code zero, e não em #PF.

Esse é um modelo de quatro níveis e 48 bits. CR4.LA57 e endereços canônicos de 57 bits não são implementados.

## CR3 e o walk de quatro níveis

O endereço da tabela raiz é:

    table = CR3 AND NOT 0xfff

Os doze bits inferiores de CR3 são descartados. Semântica de PCID não é modelada.

O walker usa quatro shifts de índice:

| Nível | Estrutura | Bits do endereço virtual |
|---:|---|---|
| 0 | PML4 | 47..39 |
| 1 | PDPT | 38..30 |
| 2 | PD | 29..21 |
| 3 | PT | 20..12 |

Em cada nível:

    index = (va >> shift[level]) AND 0x1ff
    entry_address = table + index * 8

A entrada de 64 bits é obtida por chris_phys_read. Trata-se de acesso à memória física: o page-table walk não traduz recursivamente os próprios endereços das tabelas.

Se a entrada física da page table não puder ser lida, chris_translate retorna menos três. Esse resultado é intencionalmente diferente de um page fault not-present do guest.

## Checks de Present e error codes

Se o bit 0 de uma entrada está limpo, a tradução retorna o resultado normal de page fault e constrói um error code a partir do contexto do acesso.

Para uma entrada not-present:

- W/R, bit 1, é definido em write;
- U/S, bit 2, é definido quando CPL é 3;
- I/D, bit 4, é definido em instruction fetch;
- P, bit 0, permanece limpo.

A implementação repete esses checks em cada nível percorrido. Uma PML4E, PDPTE, PDE ou PTE ausente gera fault antes que qualquer nível inferior seja acessado.

O wrapper de page fault grava o endereço virtual que falhou em CR2 e gera o vetor 14.

## Propagação da permissão user/supervisor

O ChrisCPU define acesso de user como arch.cpl igual a três.

Em cada nível present, um acesso user exige o bit U/S naquela entrada. Se qualquer ancestor ou leaf for supervisor-only, a tradução falha com P definido porque a página está presente, mas a proteção negou o acesso.

A fixture de contrato verifica explicitamente a negação em uma entrada ancestor, e não apenas no leaf. Isso importa porque as permissões efetivas de x86 são a interseção da hierarquia.

O modelo distingue apenas CPL 3 de CPL diferente de 3 nessa decisão. Semântica completa de rings e interação de privilégio com segmentação ficam fora do walker.

## Permissão de escrita e CR0.WP

Em um write, cada entrada percorrida é verificada quanto ao bit R/W.

Se R/W estiver limpo:

- um acesso user gera fault;
- um acesso supervisor gera fault quando CR0.WP está definido;
- um acesso supervisor é permitido quando CR0.WP está limpo.

O teste independente de contrato exercita os três casos. Ele confirma que limpar CR0.WP permite o write do supervisor, mas não concede o mesmo write a CPL 3.

Esse comportamento é arquiteturalmente relevante porque código de sistema operacional frequentemente depende de CR0.WP para proteger mappings read-only mesmo durante execução no kernel.

## Checks de execução NX

Execução usa a classe de acesso dois. Quando EFER.NXE está habilitado, o bit 63 de cada entrada percorrida é tratado como NX. Encontrar NX durante instruction fetch retorna um page fault de proteção com:

    P = 1
    I/D = 1
    U/S conforme o CPL

A fixture verifica o caso de execução em user mode e espera error code decimal 21, correspondente a P, U/S e I/D.

Quando EFER.NXE está limpo, o walker não trata o bit 63 como negação de execução.

O protocolo de boot atual define LME e LMA, mas não NXE. Assim, NX não está ativo no identity map padrão a menos que software do guest o habilite.

## Bit Accessed

Para cada entrada present, o walker verifica o bit 5. Se estiver limpo, o ChrisCPU o define na cópia local da entrada e tenta gravá-la de volta na memória física.

Consequentemente, um cold walk bem-sucedido de 4 KiB normalmente toca quatro entradas e tenta quatro updates do bit Accessed.

O teste de contrato verifica que os quatro níveis recebem A em uma leitura bem-sucedida.

Não existe TLB nessa implementação. Traduções posteriores releem as entradas das page tables da memória física modelada, embora bits A já definidos evitem novos writes.

## Bit Dirty

O bit Dirty, 6, é atualizado somente no leaf que encerra uma tradução de write.

Para página de 4 KiB, a PTE recebe D em write. Para uma large page de 2 MiB ou 1 GiB, a própria entrada large-page recebe D.

Uma leitura deixa D limpo.

A fixture verifica explicitamente ambos os comportamentos.

## Leaves de 4 KiB

No nível três, o endereço físico é atualmente formado como:

    physical = (entry AND NOT 0xfff) OR (va AND 0xfff)

A expressão é compacta, mas contém um defeito conhecido de máscara de endereço. NOT 0xfff preserva bits altos que são atributos, e não parte do physical address, inclusive NX no bit 63.

Se um leaf de 4 KiB possui NX definido e o acesso atual é uma leitura de dados, a tradução é permitida, mas o bit 63 vaza para o endereço físico retornado.

O probe independente caracteriza esse gap intencionalmente. Ele espera um endereço traduzido ainda contendo o bit NX alto, para que uma correção futura force uma alteração explícita e revisada no teste.

O desenho correto deve mascarar o campo de endereço físico implementado, em vez de apenas limpar o page offset.

## Large pages de 2 MiB

No nível PD, o bit 7 seleciona uma página de 2 MiB. A implementação usa:

    page = entry AND 0x000fffffffe00000
    offset = va AND ((1 << 21) - 1)

O walker retorna depois de três leituras de page-table entries.

Como a máscara da base física é explícita, atributos altos como NX não são incorporados ao physical address nesse caminho.

A fixture verifica um mapping de 2 MiB e a quantidade esperada de leituras.

## Large pages de 1 GiB

No nível PDPT, o bit 7 seleciona uma página de 1 GiB. A implementação usa:

    page = entry AND 0x000fffffc0000000
    offset = va AND ((1 << 30) - 1)

O walker retorna depois de duas leituras de page-table entries.

A fixture verifica de forma independente uma tradução de 1 GiB.

O ChrisCPU não valida todos os bits reserved ou de alinhamento associados a large-page entries. Uma MMU x86 completa rejeitaria codificações malformadas adicionais.

## Ausência de validação de reserved bits

O walker atual concentra-se em Present, R/W, U/S, A, D, PS e NX. Ele não implementa checks abrangentes de reserved bits.

Entre as consequências estão a ausência da classificação #PF.RSVD para entradas malformadas e a aceitação de combinações que hardware real rejeitaria.

O builder do page-fault error code não define o bit 3 para reserved-bit violation porque atualmente não existe esse caminho de validação.

Checks da largura do endereço físico também não são derivados de CPUID MAXPHYADDR.

## Falha de write-back de Accessed/Dirty

read_pte e write_pte chamam a interface de memória física da máquina. Entretanto, os updates A/D descartam deliberadamente o retorno de write_pte.

Assim, a tradução pode reportar sucesso mesmo quando o emulador não conseguiu persistir o bit Accessed ou Dirty na page table.

A fixture independente da MMU força essas escritas a falharem e registra o comportamento como KNOWN GAP.

Isso é um problema de correção para guests que inspecionam estado A/D das page tables. O resultado da tradução e os metadados arquiteturalmente visíveis podem divergir.

Uma implementação endurecida deve propagar ou resolver corretamente a falha de write-back em vez de ignorá-la.

## Leituras virtuais

chris_va_read processa um intervalo arbitrário de bytes repetindo:

1. traduzir o endereço virtual corrente;
2. calcular quantos bytes restam até o próximo limite físico de 4 KiB;
3. limitar o chunk ao comprimento restante solicitado pelo caller;
4. ler o chunk por chris_phys_read;
5. avançar até completar a solicitação.

Leituras de comprimento zero retornam sucesso sem tradução ou acesso físico.

Usar chunks de 4 KiB é correto para dividir crossings comuns, embora seja conservador em mappings de large pages e possa gerar mais iterações que o necessário.

## Escritas virtuais

chris_va_write segue a mesma estrutura, mas sempre traduz com acesso de write e chama chris_phys_write em cada chunk.

Writes de tamanho zero não fazem nada e retornam sucesso.

Como tradução e physical write acontecem chunk a chunk, um write que cruza páginas não é transacional.

## Faults cross-page e efeitos parciais

O contrato MMU testa intencionalmente uma leitura iniciada dois bytes antes do final de uma página mapeada quando a página seguinte está ausente.

Os dois primeiros bytes são copiados para o buffer do caller; depois, a tradução da segunda página gera #PF e CR2 aponta para o endereço na segunda página.

Um teste correspondente de write é marcado como gap conhecido: os dois primeiros bytes são gravados na memória do guest antes que a segunda página gere fault. Não existe rollback do primeiro chunk.

Esse comportamento importa para a precisão do emulador. Helpers de instrução que usam chris_va_write podem expor modificação parcial de memória proveniente de um único acesso lógico do guest se uma página posterior falhar.

Uma futura camada de acesso preciso deve preflight todas as traduções necessárias ou fornecer semântica de rollback/commit nos casos em que a arquitetura exige fault sem estado parcial visível.

## Resultados de tradução e roteamento de exceções

chris_translate usa três classes de falha:

| Retorno | Significado | Comportamento do wrapper |
|---:|---|---|
| -1 | falha de presença/permissão nas page tables do guest | grava CR2, gera #PF |
| -2 | endereço virtual não canônico | gera #GP(0) |
| -3 | backing físico/page-table read indisponível | para com CHRIS_EXIT_UNMAPPED |

Essa separação impede que uma deficiência do mapa físico do emulador seja reportada incorretamente como fault das page tables do guest.

Durante entrega de exceção, cpu->delivering suprime chamadas recursivas a chris_raise. A falha de tradução retorna ao builder do exception frame, que pode escalar para double fault.

## Paginação inicial instalada por chris_boot

chris_boot chama install_tables antes de iniciar a execução do guest.

O protocolo de boot reserva as quatro páginas finais de 4 KiB da RAM do guest para estruturas de paginação e estado relacionado. install_tables posiciona:

    PML4 em RAM_size - 0x4000
    PDPT em RAM_size - 0x3000
    PD   em RAM_size - 0x2000

PML4[0] aponta para o PDPT e PDPT[0] aponta para o PD. A RAM é identity-mapped com PDEs de 2 MiB contendo base OR 0x83, ou seja, Present, Writable e Page Size.

A quantidade de páginas de 2 MiB não pode exceder 512. Portanto, esse layout do protocolo de boot trata no máximo um PD de mapping inicial de RAM, isto é, um GiB.

Se existe framebuffer, install_tables mapeia suas regiões de 2 MiB por identidade em slots PDE livres do mesmo PD.

O estado inicial de controle é:

    CR0: PE, NE, WP, PG
    CR3: endereço físico da PML4
    CR4: PAE
    EFER: LME, LMA
    CPL: 0

Os bits User não são definidos no identity mapping inicial. O guest inicia, portanto, com mappings supervisor-only.

## Sem TLB ou cache de tradução

Embora ChrisCpu possua um campo tlb_gen para estado mais amplo da máquina, o caminho MMU inspecionado executa diretamente o page-table walk em cada chamada de chris_translate. Não há translation lookup cache em mmu.c.

Isso produz duas consequências.

Primeiro, mudanças em page tables tornam-se visíveis imediatamente às traduções seguintes sem emulação explícita de INVLPG.

Segundo, instruction fetch e workloads intensivos em memória pagam repetidamente as leituras físicas das page tables. O desempenho difere bastante de hardware e de um emulador com TLB.

Uma TLB futura precisa definir comportamento de invalidação para writes em CR3, INVLPG, global pages, PCID e mutações das page tables.

## Funcionalidades de paginação não suportadas

O walker atual não modela:

- paginação de cinco níveis e CR4.LA57;
- PCID e semântica no-flush de CR3;
- global pages e PGE;
- INVLPG;
- SMEP;
- SMAP;
- protection keys;
- permissões de shadow stack;
- semântica PAT/cache-type completa;
- reserved bits dependentes de MAXPHYADDR;
- validação abrangente de entries malformadas;
- cache TLB e invalidação;
- tradução nested/EPT/NPT.

Essas omissões são fronteiras de compatibilidade, em especial para kernels modernos que detectam ou habilitam recursos avançados de CR4.

## Evidência reproduzível da MMU

scripts/check_mmu.py compila o mmu.c real junto com tests/source/mmu_contract.c contra um backend sintético de memória física e uma função stub para exception delivery.

A fixture verifica:

- tradução identidade quando paging está desabilitado;
- walk de quatro níveis para 4 KiB;
- bits Accessed em todos os níveis;
- comportamento Dirty em writes;
- rejeição de endereço não canônico de 48 bits;
- error code de write user em entrada not-present;
- negação U/S em ancestor;
- comportamento supervisor de CR0.WP;
- negação de write user com WP limpo;
- negação de execução por NX;
- páginas de 2 MiB;
- páginas de 1 GiB;
- resultado distinto para page table sem backing;
- #PF e CR2 gerados pelo wrapper;
- #GP gerado pelo wrapper;
- CHRIS_EXIT_UNMAPPED;
- supressão de fault recursivo durante exception delivery;
- leituras cross-page;
- acessos de tamanho zero.

Ela também caracteriza deliberadamente dois gaps conhecidos:

- vazamento de NX para o physical address de dados em leaf de 4 KiB;
- falha de write-back do bit Accessed sendo ignorada.

Uma terceira caracterização de gap cobre um write cross-page que mantém o primeiro chunk gravado quando a segunda página gera fault.

O probe é reproduzível e vinculado à fonte real, mas usa memória física sintética. Ele não prova compatibilidade com um guest OS, timing de hardware ou funcionalidades de paginação ausentes de mmu.c.

## Prioridades de hardening

Os próximos trabalhos de maior valor na MMU são:

1. substituir a máscara do leaf de 4 KiB por uma máscara explícita de endereço físico que exclua NX e outros atributos;
2. propagar ou tratar corretamente falhas de write-back de A/D;
3. adicionar validação de reserved bits e largura de endereço físico com #PF.RSVD;
4. definir semântica precisa de write multi-page e eliminar updates parciais não desejados;
5. adicionar testes de interseção de permissões em todos os níveis das page tables;
6. adicionar testes de entries malformadas de 2 MiB e 1 GiB;
7. implementar ou rejeitar explicitamente recursos de paginação CR4 ainda não suportados;
8. introduzir TLB somente junto com um contrato completo de invalidação;
9. expandir os mappings de boot além do protocolo de um único PD quando mais memória guest for necessária;
10. adicionar testes guest-level de page-fault handler conectando tradução, CR2, error code, IDT delivery e IRETQ.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisCPU possui um walker de long mode de quatro níveis funcional, com enforcement relevante de permissões, suporte a large pages e comportamento A/D verificado de forma independente. As principais limitações atuais são a máscara incorreta do endereço físico em leaf de 4 KiB quando há atributos altos, falhas de write-back A/D ignoradas, ausência de reserved-bit validation e writes cross-page não transacionais. Essas fronteiras são caracterizadas explicitamente por testes em vez de serem ocultadas sob uma afirmação genérica de suporte à paginação x86-64.
