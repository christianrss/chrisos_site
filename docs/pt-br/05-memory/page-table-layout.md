---
id: page-table-layout
lang: pt-br
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/bootinfo.c
symbols:
  - pml4_index
  - pdpt_index
  - pd_index
  - pt_index
  - table_from_phys
  - ensure_table
  - ensure_table_flags
  - map_4k_ex
  - mm_map_cr3
  - translate_leaf
  - mm_clone_kernel_space
  - free_table_page
  - mm_free_user_space
depends_on:
  - virtual-memory
  - x86-64-memory-privilege
related:
  - page-faults
  - address-spaces
  - tlb
  - physical-memory
  - hhdm
---

# Layout das page tables x86-64 e semântica das entradas

## Escopo

Este capítulo descreve o layout concreto da hierarquia de page tables x86-64 de quatro níveis usada pelo subsistema de memória atual do ChrisOS. O capítulo de memória virtual explica por que a tradução existe e como espaços de endereçamento são construídos. Aqui o foco é mais mecânico: quais bits do endereço virtual escolhem cada entrada, quanto espaço cada nível cobre, como uma entrada combina endereço físico e flags, como o ChrisOS cria e percorre tabelas e quais regras de ownership impedem que páginas de page table sejam confundidas com frames de dados mapeados.

A hierarquia usada atualmente é:

~~~text
CR3 -> PML4 -> PDPT -> PD -> PT -> frame de 4 KiB
~~~

O walker de software também pode terminar antecipadamente ao encontrar huge pages de 1 GiB ou 2 MiB já existentes, mas o caminho atual de criação de mappings produz apenas folhas de 4 KiB.

![Níveis de page table x86-64, spans e operações do ChrisOS](../../assets/diagrams/x86-page-table-layout-pt-br.svg)

## Por que cada tabela ocupa uma página de 4 KiB

Cada estrutura de paging do modelo x86-64 de quatro níveis contém 512 entradas de 64 bits.

~~~text
512 entradas * 8 bytes = 4096 bytes
~~~

Essa igualdade tem consequência direta na implementação. Uma página de page table possui exatamente a mesma granularidade de alocação de uma frame normal do PMM. O ChrisOS pode obter uma nova tabela com pmm_alloc, acessá-la via HHDM, zerar suas 512 entradas e ligar seu endereço físico em uma entrada da tabela pai.

Não há atualmente um alocador especializado de page tables. O PMM não sabe se uma frame será usada para dados de processo, tabela de páginas, buffer do kernel ou outro objeto. O significado da frame é determinado pelo subsistema que a alocou e por suas invariantes de lifetime.

## Decomposição do endereço virtual

Para páginas de 4 KiB no modelo atual:

| Campo | Bits do endereço virtual | Largura | Seleciona |
|---|---:|---:|---|
| Índice PML4 | 47..39 | 9 | uma de 512 entradas PML4 |
| Índice PDPT | 38..30 | 9 | uma de 512 entradas PDPT |
| Índice PD | 29..21 | 9 | uma de 512 entradas PD |
| Índice PT | 20..12 | 9 | uma de 512 PTEs |
| Offset da página | 11..0 | 12 | byte dentro da página de 4 KiB |

Os helpers de mm.c implementam diretamente esses deslocamentos.

Para um endereço virtual V:

~~~text
PML4(V) = (V >> 39) & 0x1ff
PDPT(V) = (V >> 30) & 0x1ff
PD(V)   = (V >> 21) & 0x1ff
PT(V)   = (V >> 12) & 0x1ff
OFF(V)  = V & 0xfff
~~~

Como cada índice contém nove bits, cada nível multiplica por 512 o span representado por uma única entrada.

## Span coberto por cada entrada

A hierarquia pode ser deduzida de baixo para cima.

Uma PTE mapeia uma página de 4 KiB:

~~~text
span da PTE = 2^12 = 4 KiB
~~~

Uma PT contém 512 PTEs:

~~~text
span de uma entrada PD = 512 * 4 KiB = 2 MiB
~~~

Uma PD contém 512 entradas:

~~~text
span de uma entrada PDPT = 512 * 2 MiB = 1 GiB
~~~

Uma PDPT contém 512 entradas:

~~~text
span de uma entrada PML4 = 512 * 1 GiB = 512 GiB
~~~

E 512 entradas PML4 descrevem 256 TiB de combinações de endereços virtuais antes das regras de canonical addressing separarem as regiões válidas inferior e superior.

| Tipo de entrada | Span representado por uma entrada |
|---|---:|
| PTE | 4 KiB |
| PDE | 2 MiB |
| PDPTE | 1 GiB |
| PML4E | 512 GiB |

Essa aritmética explica por que um mapping esparso pode consumir várias páginas de metadados. Uma única página de 4 KiB isolada pode exigir uma PDPT, uma PD e uma PT novas abaixo de uma PML4 já existente.

## Endereços canônicos e metades da PML4

No modelo de quatro níveis com 48 bits virtuais, os bits acima do bit 47 devem formar a extensão canônica do bit 47. O espaço utilizável é, portanto, dividido em uma região inferior e uma região superior separadas por um intervalo não canônico.

No nível da PML4, o ChrisOS explora diretamente essa divisão:

- entradas 0..255 são tratadas como half de usuário;
- entradas 256..511 são tratadas como half do kernel.

mm_clone_kernel_space aloca uma PML4 nova, mantém as 256 entradas inferiores zeradas e copia as 256 entradas superiores da PML4 do kernel.

O processo recebe, assim, raízes privadas para mappings de usuário e referências compartilhadas para a hierarquia do kernel.

Essa fronteira estrutural não substitui a política de privilégio. O acesso em user mode continua dependendo dos bits de permissão em todos os níveis percorridos.

## Forma geral de uma entrada de 64 bits

Uma entrada de paging x86-64 combina:

1. bits inferiores de controle e status;
2. endereço físico alinhado de uma frame ou de uma tabela filha;
3. bits arquiteturais superiores, incluindo NX quando disponível e habilitado.

O ChrisOS expõe atualmente:

~~~c
MM_PRESENT = 1 << 0
MM_WRITE   = 1 << 1
MM_USER    = 1 << 2
MM_PWT     = 1 << 3
MM_PCD     = 1 << 4
MM_NX      = 1 << 63
~~~

e mascara endereços comuns com:

~~~text
MM_ADDR_MASK = 0x000ffffffffff000
~~~

Logo, os 12 bits inferiores não pertencem ao endereço da frame de 4 KiB.

O código atual não tenta modelar todos os bits arquiteturais por meio de constantes de alto nível. Bits de accessed, dirty, global, detalhes de PAT e outros estados não formam ainda uma abstração completa de software no MM.

## PRESENT é propriedade do caminho

Em um walk normal de 4 KiB, o hardware precisa encontrar PRESENT em todos os níveis necessários.

Uma folha presente abaixo de um pai não presente é inalcançável. De forma inversa, uma entrada intermediária presente apenas informa que a estrutura filha existe; isso não significa que uma página virtual específica esteja mapeada.

Os walkers do ChrisOS seguem a mesma regra. translate_leaf retorna falha imediatamente quando a entrada selecionada em qualquer nível não contém MM_PRESENT.

Por isso uma nova tabela zerada é um estado válido: a entrada pai passa a apontar para uma estrutura existente, mas todas as entradas filhas começam como não presentes.

## Endereço físico versus flags

Ao seguir uma entrada intermediária, o ChrisOS remove os bits de flags antes de converter o endereço físico da tabela filha em ponteiro virtual acessível pelo kernel.

table_from_phys aplica MM_ADDR_MASK e depois bootinfo_phys_to_virt:

~~~text
child_phys = entry & ADDRESS_MASK
child_virt = HHDM(child_phys)
~~~

O endereço físico codificado na page table não é dereferenciado diretamente como ponteiro C. O kernel acessa a página física por seu alias virtual no higher-half direct map.

Essa separação impede a suposição incorreta de que endereço físico e endereço virtual possuem o mesmo valor numérico.

## Criação de tabela intermediária

ensure_table é o caminho usado por mappings do kernel.

Quando a entrada pai selecionada está ausente:

1. aloca uma frame com PMM;
2. obtém o ponteiro HHDM;
3. zera as 512 entradas;
4. grava o endereço físico da nova tabela na entrada pai;
5. adiciona PRESENT e WRITE;
6. devolve o ponteiro virtual da tabela filha.

Se a entrada já existir e contiver PS, a função entra em panic porque map_4k não consegue atravessar uma huge-page leaf.

Se a entrada existente for intermediária normal, a tabela filha é reutilizada.

O custo do walk é constante em relação ao tamanho total do espaço virtual. O trabalho mais significativo ao criar uma tabela é zerar seus 4096 bytes. Depois disso, mappings próximos reutilizam a mesma estrutura.

## Mappings de usuário e propagação de permissões

ensure_table_flags é a variante recuperável usada por mm_map_cr3.

Para mappings de usuário, extra contém MM_USER. Quando uma nova tabela intermediária é criada, a entrada pai recebe:

~~~text
child_phys | PRESENT | WRITE | USER
~~~

Se a tabela já existir mas a entrada pai não possuir USER, ensure_table_flags faz upgrade dessa entrada adicionando MM_USER.

Isso corresponde a uma propriedade fundamental da paginação x86: permissões são combinadas ao longo de todo o caminho.

Para que um acesso em user mode alcance a folha, nenhum ancestral pode permanecer supervisor-only. Portanto, colocar USER apenas na PTE final não seria suficiente.

A permissão de escrita também sofre restrições cumulativas. O ChrisOS cria níveis intermediários com WRITE e deixa a PTE folha decidir se o mapping individual pode ou não receber escrita.

As rotinas atuais não criam entradas intermediárias NX; nos mappings criados por essa API, o controle de execução é aplicado principalmente na folha por MM_NX.

## Instalação da folha

Depois que PML4, PDPT, PD e PT foram resolvidas, o mapping de 4 KiB grava:

~~~text
PTE = (phys & MM_ADDR_MASK) | flags | MM_PRESENT
~~~

Os endereços virtual e físico recebidos precisam estar alinhados em 4 KiB.

O offset não fica armazenado na PTE. Durante a tradução, os 12 bits inferiores do endereço virtual original são combinados com a base física alinhada codificada na folha:

~~~text
physical = (PTE & MM_ADDR_MASK) | (virtual & 0xfff)
~~~

## Semântica de huge pages

O bit PS altera o significado de uma entrada PDPT ou PD.

No translator atual:

- PS no nível PDPT representa folha de 1 GiB;
- PS no nível PD representa folha de 2 MiB;
- no nível PT, a folha normal representa 4 KiB.

Os masks usados pelo código são:

| Nível folha | Tamanho | Mask de base no walker | Mask do offset |
|---|---:|---|---|
| PDPT | 1 GiB | 0x000fffffc0000000 | 0x3fffffff |
| PD | 2 MiB | 0x000fffffffe00000 | 0x1fffff |
| PT | 4 KiB | MM_ADDR_MASK | 0xfff |

translate_leaf consegue, assim, interpretar huge mappings já existentes na hierarquia herdada do boot.

As APIs de mapping não criam essas folhas e ensure_table/ensure_table_flags se recusam a atravessá-las. Não há atualmente uma operação de split que transforme uma huge page em tabelas de nível inferior.

## Walk recursivo de software

translate_leaf recebe:

- endereço físico da tabela corrente;
- endereço virtual procurado;
- número do nível;
- ponteiros de saída para endereço físico e flags.

O nível determina qual grupo de nove bits deve ser usado como índice.

Se a entrada estiver ausente, a tradução falha.

Se PS estiver ativo ou se o walk tiver chegado ao nível zero, a função calcula o endereço físico final e devolve a entrada folha como conjunto de flags.

Caso contrário, recursa usando como próxima tabela o endereço físico codificado na entrada.

Como a profundidade da hierarquia é limitada, a profundidade da recursão também é limitada. O custo é O(1) em relação à quantidade total de memória virtual mapeada.

## Walker específico do kernel

mm_virt_to_phys implementa uma versão não recursiva especializada na raiz do kernel.

Ela testa explicitamente PML4, PDPT, PD e PT nessa ordem e também pode terminar em huge pages nos níveis PDPT e PD.

A função retorna zero quando o mapping está ausente.

Zero é, portanto, um sentinel dessa interface. O chamador não possui uma representação separada para distinguir “mapping inexistente” de um caso hipotético em que uma tradução válida resultasse no endereço físico zero. Os call sites atuais operam dentro desse contrato.

## Semântica de falha ao alocar tabelas

Existem duas políticas.

map_4k usa alloc_zero_table e entra em panic se o PMM não conseguir fornecer a página necessária.

mm_map_cr3 usa alloc_zero_table_try e retorna -1 quando uma tabela intermediária não pode ser criada.

Entretanto, mm_map_cr3 não desfaz tabelas que já foram criadas antes da falha. Se a chamada conseguiu criar e ligar uma PDPT mas falhou ao tentar criar a PD ou PT seguinte, a estrutura já ligada permanece alcançável.

O desenho privilegia simplicidade e futura reutilização em vez de semântica transacional. A frame intermediária não fica perdida: ela permanece no espaço e pode ser reaproveitada por mapping posterior ou liberada no teardown. Porém um retorno de erro não significa que a árvore permaneceu bit a bit idêntica.

## Compartilhamento do half do kernel

Uma nova PML4 de processo recebe cópias das entradas 256..511 da raiz do kernel.

A operação copia valores de 64 bits, e não as páginas inferiores. Várias PML4s de processo podem apontar para as mesmas PDPTs, PDs e PTs do kernel.

Isso produz duas consequências.

Primeiro, o overhead por processo é reduzido porque mappings do kernel não são duplicados.

Segundo, uma mudança em uma estrutura compartilhada pode ser observável por todos os espaços que apontam para ela. CPUs que já armazenaram traduções antigas no TLB ainda precisam ser invalidados corretamente.

Por isso o teardown de mappings compartilhados do kernel se relaciona ao protocolo multiprocessado de TLB e não apenas ao unmap local do processo.

## Liberação das estruturas de usuário

mm_free_user_space recebe o endereço físico da PML4 de um processo.

A função rejeita estado MM não inicializado, CR3 zero e a própria raiz do kernel.

Depois percorre somente as entradas PML4 de 0 a 255.

Para cada entrada presente e não-huge, free_table_page libera recursivamente as páginas de tabelas inferiores. A recursão é construída de modo a não liberar as frames de dados apontadas pelas PTEs finais.

A divisão de ownership é:

~~~text
frames de page table -> teardown da árvore MM
frames de dados mapeados -> teardown de Proc.pages
~~~

Antes de mm_free_user_space, proc_release_user deve limpar mappings folha e devolver ao PMM as frames de dados possuídas pelo processo.

Ao final, a própria frame da PML4 do processo é liberada.

## Por que a recursão para antes das frames folha

free_table_page recebe uma frame de tabela e um nível.

Quando o nível é maior que um, percorre entradas e visita recursivamente páginas filhas presentes que não sejam huge pages.

Ao chegar ao nível correspondente a uma PT, a recursão não interpreta as PTEs como ponteiros para outras page tables. Ela libera a página da PT e termina aquele ramo.

Essa regra codifica a fronteira entre metadados de tradução e objetos mapeados.

Se a função seguisse as PTEs finais como se fossem tabelas, trataria frames de aplicação como estruturas de paging e corromperia o ownership de memória.

## Invariantes de alinhamento

Estruturas de page table e frames folha de 4 KiB precisam estar alinhadas em página.

O ChrisOS verifica:

~~~text
virt % 4096 == 0
phys % 4096 == 0
~~~

map_4k trata violação como fatal. mm_map_cr3 retorna -1.

O alinhamento libera os bits baixos para flags e garante que MM_ADDR_MASK recupere a base correta da frame.

Huge pages possuem requisitos arquiteturais de alinhamento ainda maiores. O walker atual pressupõe que huge entries herdadas já sejam válidas.

## Overhead de memória das page tables

Uma árvore completamente preenchida seria grande, mas espaços reais são esparsos e tabelas são alocadas sob demanda.

Para um único mapping de 4 KiB isolado sob uma PML4 existente, o pior caso de novas estruturas é:

- uma página PDPT;
- uma página PD;
- uma página PT;
- uma frame de dados, cujo ownership é separado.

São 12 KiB de metadados de page table para o primeiro mapping de 4 KiB em uma região distante.

O custo cai rapidamente com localidade:

- uma PT descreve 512 páginas de 4 KiB = 2 MiB;
- uma PD pode apontar para 512 PTs = 1 GiB;
- uma PDPT pode cobrir 512 GiB por meio de suas PDs.

Regiões densas amortizam muito melhor o custo de metadados que mappings unitários espalhados pelo espaço virtual.

## Sincronização

Page tables são estruturas compartilhadas mutáveis.

O ChrisOS protege walks e mutações com mm_lock. Isso impede que dois contextos criem simultaneamente tabelas filhas conflitantes ou que um walker observe a hierarquia em um estado intermediário de atualização.

O lock protege a representação em memória. Ele não invalida por si só entradas já armazenadas nos TLBs dos CPUs.

Depois de uma mudança, a forma de invalidação depende do escopo:

- página local individual pode usar INVLPG;
- refresh local amplo pode recarregar CR3;
- mappings compartilhados visíveis em outros CPUs exigem o protocolo multiprocessado de TLB.

Consistência das page tables e coerência dos TLBs são problemas relacionados, mas diferentes.

## Modos de falha

| Condição | Comportamento atual |
|---|---|
| mapping antes de MM estar pronto | caminho de kernel entra em panic; mm_map_cr3 falha |
| mapping de kernel desalinhado | panic |
| mm_map_cr3 desalinhado | -1 |
| PMM esgotado ao criar tabela do kernel | panic |
| PMM esgotado ao criar tabela de processo | -1, podendo restar intermediários alcançáveis |
| PS encontrado no caminho de criação de 4 KiB | panic |
| entrada ausente no walker | falha de tradução |
| tentativa de liberar o CR3 do kernel como user space | ignorada |
| mudança compartilhada sem invalidação adequada | risco de tradução stale no TLB |

O último caso não pode ser diagnosticado apenas olhando as page tables em RAM. Uma PTE correta pode coexistir temporariamente com uma tradução antiga em cache.

## Fronteira de validação

O self-test de MM verifica que uma frame do PMM mapeada em uma nova folha de 4 KiB referencia o mesmo armazenamento observado pelo alias HHDM. Também exercita o caminho de MMIO com a página física do LAPIC.

Essas evidências cobrem construção e tradução básicas.

Ainda não há cobertura exaustiva de:

- todas as combinações de permissões;
- todas as fronteiras canônicas;
- split de huge pages;
- árvores malformadas herdadas;
- todas as posições possíveis de falha de alocação intermediária;
- criação concorrente do mesmo caminho ausente;
- todas as corridas de TLB remoto.

Ausência desses testes não deve ser interpretada como prova de correção desses casos.

## Limite do desenho atual

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o modelo implementado é:

- paginação x86-64 de quatro níveis;
- criação de mappings de 4 KiB pelo ChrisOS;
- reconhecimento de folhas herdadas de 2 MiB e 1 GiB durante tradução;
- alocação esparsa de tabelas intermediárias pelo PMM;
- acesso às estruturas por HHDM;
- compartilhamento do half superior do kernel;
- árvores privadas no half inferior dos processos;
- propagação explícita de USER;
- ausência de criação e split automático de huge pages;
- ausência de paginação de cinco níveis;
- ausência de rollback transacional;
- ausência de gerenciamento de contexto baseado em PCID.

Essas restrições descrevem a implementação atual e devem permanecer separadas de objetivos futuros.

## Fronteira de revisão

Este capítulo foi reconciliado com ChrisOS main na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56. Os arquivos e símbolos declarados no frontmatter são a autoridade para afirmações de implementação. Mudanças no contrato de paging do boot, split do espaço, alocador de tabelas, política de permissões ou tratamento de huge pages exigem nova revisão.
