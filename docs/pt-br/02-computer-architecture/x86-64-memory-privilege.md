---
id: x86-64-memory-privilege
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/proc.c
  - kernel/metal/linker.ld
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
symbols:
  - mm_switch
  - mm_map_cr3
  - mm_clone_kernel_space
  - proc_map_user
  - chris_translate
  - chris_va_read
  - chris_va_write
  - chris_raise
depends_on:
  - cpu-datapath-isa
  - x86-registers-flags
  - x86-instruction-encoding
related:
  - virtual-memory
  - kernel-model
---

# Memória, privilégio e estado arquitetural x86-64

## Long mode

O long mode x86-64 fornece registradores gerais de 64 bits e grande espaço virtual mantendo partes importantes da herança da arquitetura. Segmentação é reduzida para endereçamento comum, mas seletores, descriptor tables e metadados de privilégio continuam relevantes para transições e exceções.

ChrisOS liga seu kernel no higher half. O linker script define `kstart` como entry point e coloca o kernel em endereço virtual canônico alto, sem assumir identidade entre endereço físico e virtual.

## Endereços canônicos

Nem todo padrão de 64 bits é um endereço virtual x86-64 válido. Implementações suportam uma largura definida e bits superiores não utilizados precisam formar a extensão canônica do bit significativo implementado. "Inteiro de 64 bits" e "endereço virtual válido" não são conceitos idênticos.

O código de processos do ChrisOS rejeita endereços de usuário acima de sua fronteira configurada; o kernel ocupa a região alta.

## Rings e privilégio

A arquitetura define níveis 0 a 3. Sistemas convencionais usam ring 0 para kernel e ring 3 para programas de usuário.

Privilégio faz parte do estado de execução e dos descritores. Um programa ring 3 não pode simplesmente reescrever CR3 ou desabilitar interrupções. A CPU verifica a permissão da operação.

| Fronteira | Propriedade exigida |
|---|---|
| Execução de usuário | Estado privilegiado e mapeamentos de supervisor permanecem protegidos |
| Entrada no kernel | Gate autorizado seleciona estado de entrada e handler |
| Tratamento do pedido | Kernel valida dados recebidos pela fronteira |
| Retorno | Estado restaurado respeita privilégio e endereços de usuário |

## Control registers

| Registrador | Papel |
|---|---|
| CR0 | controles globais de modo e proteção, incluindo paging |
| CR2 | endereço linear que causou page fault |
| CR3 | base física da estrutura superior de tradução e bits de controle definidos pela arquitetura |
| CR4 | recursos arquiteturais adicionais, inclusive ligados a paging |

`mm_switch` no ChrisOS escreve CR3 ao trocar address spaces. Uma única instrução de máquina muda o contexto de tradução usado pelos acessos virtuais seguintes.

## Descriptor tables

A GDT fornece descritores e seletores ainda necessários para convenções de código/dados, privilégio e TSS. A IDT associa vetores de exceção e interrupção a descritores de handlers.

Uma entrada da IDT não é apenas um ponteiro de função. Ela codifica offset, selector, gate type e propriedades de presença/privilégio. O processador realiza a transferência conforme esses campos.

## Exceções

Exceções são consequências síncronas da execução: invalid opcode, general protection e page fault. Interrupções de dispositivos são assíncronas em relação ao fluxo atual.

O kernel precisa preservar estado suficiente para diagnosticar ou recuperar, determinar a origem e então retomar, encerrar o processo ou falhar de modo controlado.

## Estado arquitetural no ChrisCPU

ChrisCPU representa o estado observável por instruções guest: registradores gerais, instruction pointer, flags e estado de controle/segmentos exigido pelo subset implementado.

O valor documental é direto: o kernel ChrisOS mostra como **usar** x86-64; ChrisCPU mostra como **implementar o comportamento visível** da mesma arquitetura.

## Arquitetura não é microarquitetura

Esses contratos não obrigam um emulador a reproduzir speculative execution, register renaming ou caches comerciais. Tais mecanismos afetam timing e desempenho, mas não o resultado arquitetural básico das instruções suportadas.

Essa fronteira também explica por que QEMU ou ChrisVM podem executar software compilado para uma ISA sem conter fisicamente o mesmo projeto de processador.

## Domínios de endereço e estrutura de tradução

Um endereço efetivo resulta dos operandos da instrução. O endereço linear inclui o tratamento de segmentos aplicável à arquitetura. O endereço físico seleciona uma posição no mapa físico da máquina, que pode conter RAM, registradores de dispositivos ou regiões sem recurso associado. São domínios distintos mesmo quando algum mapeamento faz seus números coincidirem. O ponteiro hospedeiro que armazena RAM convidada pertence a um quarto domínio. Somar endereço físico convidado a ponteiro arbitrário sem verificar a região de suporte violaria a fronteira de memória do emulador.

Em paginação de quatro níveis, tabelas de 4 KiB com entradas de oito bytes contêm 512 entradas. Selecionar uma exige nove bits. Quatro índices e um deslocamento de doze bits consomem 48 bits. Os bits superiores restantes precisam repetir o bit 47 para formar endereços canônicos nesse modelo. Os intervalos são `0x0000000000000000` a `0x00007fffffffffff` e `0xffff800000000000` a `0xffffffffffffffff`. O intervalo numérico entre eles não se torna acessível apenas pela instalação de uma entrada de paginação.

| Bits do endereço | Papel | Deslocamento usado por ChrisCPU |
|---|---|---:|
| 47:39 | Índice PML4 | 39 |
| 38:30 | Índice PDPT | 30 |
| 29:21 | Índice PD | 21 |
| 20:12 | Índice PT | 12 |
| 11:0 | Posição na página de 4 KiB | 0 |

`chris_translate` começa com CR3 alinhado para baixo pela limpeza dos doze bits inferiores. Em cada nível, calcula `table + index * 8`, lê a entrada pela memória física e verifica permissões. Entrada intermediária fornece a próxima tabela; folha combina base de quadro com posição na página. Com CR0.PG desligado, a função retorna diretamente o endereço recebido, antes de verificar canonicalidade. Essa é a ordem implementada, não um modelo completo de todos os modos sem paginação.

## Uma caminhada reconstruível byte a byte

![Descida pelas tabelas, permissões e acesso físico](../../assets/diagrams/paging-permission-walk.svg)

Considere CR3 = `0x1000`, entrada PML4 em `0x1000` contendo `0x2007`, entrada PDPT em `0x2000` contendo `0x3007`, entrada PD em `0x3000` contendo `0x4007` e entrada PT em `0x4008` contendo `0x8007`. O valor inferior sete liga presença, escrita e acesso de usuário. Traduzir virtual `0x1234` usa índices zero, zero, zero e um, depois posição `0x234`. O endereço físico final é `0x8234`.

Todos os endereços das entradas nesse exemplo são físicos. A caminhada não os traduz recursivamente pelo mesmo mapeamento virtual; isso faria a tradução depender de si mesma sem caso-base terminante. ChrisCPU usa `chris_phys_read`; o kernel obtém uma visão virtual acessível das tabelas físicas pelo helper de mapeamento das informações de boot. São estratégias distintas para interpretar a mesma estrutura de tabelas.

O bit de página grande no nível PDPT encerra a caminhada em folha de 1 GiB; no nível PD seleciona folha de 2 MiB. A posição restante tem respectivamente trinta ou vinte e um bits. Páginas grandes encurtam caminhadas e reduzem armazenamento de tabelas, mas tornam alocação e proteção menos granulares. Uma caminhada de quatro níveis tem no máximo quatro leituras de entradas; processar uma faixa de n bytes ainda depende das fronteiras atravessadas e de como a implementação divide a operação.

## Permissões se acumulam pelo caminho

A folha não é a única autoridade. Acesso de usuário exige permissão adequada em todos os ancestrais e na folha. Uma folha gravável sob ancestral somente de leitura não recupera permissão de escrita. ChrisCPU verifica cada entrada antes de descer. Classifica acesso como usuário quando CPL vale três, como escrita quando o argumento de acesso vale um e como busca de instrução quando vale dois.

Em escrita para entrada sem bit de gravação, usuário recebe falha; supervisor recebe falha quando CR0.WP está ligado. Desligar WP permite escrita de supervisor nesse caminho, mas nunca concede escrita de usuário. Na busca de instruções, NX impede execução quando EFER.NXE está ligado. NX restringe execução, não leitura comum de dados. A máscara correta de quadro precisa, portanto, remover NX do endereço físico mesmo quando a leitura é permitida.

O código atual usa `entry & ~0xfff` para folha de 4 KiB e para seguir uma tabela intermediária. Isso limpa atributos inferiores, mas retém bits altos como NX. A sonda independente demonstra tradução de dados com folha `0x8000000000008007` retornando `0x8000000000008234`, em vez de físico `0x8234`. Os caminhos de páginas grandes usam máscaras explícitas de endereço. É uma diferença concreta entre ramos, não um aviso hipotético nem uma afirmação de que NX deveria compor o endereço físico.

## Bits de acesso e modificação são escritas da caminhada

Traduzir pode modificar tabelas. O walker liga o bit de acesso cinco nas entradas atravessadas e o bit de modificação seis na folha escrita. Esses registros permitem observar utilização sem registrar cada acesso da aplicação em software. Também significam que a tabela não é imutável apenas porque a operação convidada é uma leitura.

Na primeira caminhada do exemplo, a sonda observa quatro leituras e quatro tentativas de escrita do bit de acesso. Ler mantém o bit de modificação desligado; escrever depois o liga. A implementação converte o retorno de `write_pte` para void. Assim, memória física que rejeita essas escritas não faz a tradução falhar. Uma caracterização separada reproduz sucesso enquanto os bits de acesso continuam ausentes. Corrigir exige política de falha definida e testes dos efeitos sobre tabelas, além de verificar o endereço retornado.

O walker não aloca memória nem consulta cache. Seu estado temporário inclui endereço de tabela, uma entrada e índice de nível. Não estabelece atomicidade multiprocessada das atualizações de acesso/modificação, validação de bits reservados, paginação de cinco níveis ou todas as regras de transição de registradores de controle. A presença de `tlb_gen` em outra parte da CPU não atribui a essa função um TLB semelhante ao hardware.

## Classificação de falhas e operações parciais

| Resultado da tradução | Significado nesta implementação | Ação do wrapper |
|---|---|---|
| 0 | Tradução bem-sucedida | Acessar recurso físico |
| −1 | Falha de presença ou permissão | Definir CR2 e solicitar falta de página |
| −2 | Endereço paginado não canônico | Solicitar proteção geral |
| −3 | Falha na leitura física da tabela | Parar com saída unmapped e registrar CR2 |

O código de erro de falta de página registra condições pertinentes de presença/proteção, escrita, usuário e busca de instrução. Escrita de usuário em página ausente informa seis: escrita mais usuário, com presença desligada. Leitura de usuário negada por ancestral exclusivo de supervisor informa cinco: proteção mais usuário. Busca de instrução de usuário negada por NX informa vinte e um: proteção, usuário e execução. A sonda verifica esses valores diretamente; não os deduz do sucesso da compilação documental.

`chris_va_read` e `chris_va_write` percorrem trechos limitados por posições de páginas físicas de 4 KiB, mesmo quando a tradução termina em página grande. Tamanho zero retorna imediatamente. Nos demais casos, cada trecho é traduzido e acessado antes de examinar o seguinte. Se a segunda página está ausente, o primeiro trecho já foi lido para o destino ou gravado na memória convidada. A sonda reproduz dois bytes retidos em uma escrita de quatro bytes atravessando página ausente. É comportamento observável do helper, não certificação geral da atomicidade de falhas de instruções x86.

Quando `cpu->delivering` é diferente de zero, os wrappers retornam sem provocar recursivamente outra exceção. `chris_raise` tenta separadamente a entrega e depois o caminho de falta dupla; falha de ambos produz saída por falta tripla. Sua implementação do quadro é simplificada e não estabelece todas as regras de transição de privilégio. A sonda da MMU substitui deliberadamente a entrega, verificando vetor solicitado e código de erro sem afirmar entrada bem-sucedida em handler convidado.

## Como o kernel cria e compartilha mapeamentos

`mm_init` registra a raiz física de CR3, inicializa trava e infraestrutura de invalidação e marca o subsistema como pronto. `mm_map_cr3` rejeita subsistema indisponível, raiz zero e endereços virtual ou físico desalinhados. Sob `mm_lock`, obtém tabelas intermediárias por `ensure_table_flags`, alocando e zerando as ausentes. Mapeamentos de usuário propagam o bit correspondente pelos ancestrais antes de instalar a folha. Por isso, adicionar MM_USER somente à folha seria insuficiente.

Alocação intermediária pode falhar e retornar erro. Tabelas já instaladas em etapas anteriores não são revertidas nessa função: tratar a falha exige distinguir uma folha solicitada ausente de uma árvore inteira inalterada. `mm_map_cr3` não executa por si só invalidação de traduções após instalar a folha. Saber se o espaço está inativo ou se o chamador precisa invalidar depende do caminho de chamada; o helper não demonstra sozinho substituição segura de mapeamento ativo.

`mm_clone_kernel_space` aloca raiz nova e copia entradas 256 a 511 da raiz do kernel. Compartilha as subárvores altas referenciadas, sem duplicá-las recursivamente. Isso cria uma restrição de propriedade: liberar a raiz de processo não pode liberar a hierarquia compartilhada do kernel. O cabeçalho separa explicitamente liberação de tabelas intermediárias de usuário da propriedade dos quadros folha, associados à lista de páginas do processo.

`proc_map_user` rejeita endereços a partir de `0x0000800000000000` e adiciona MM_USER. `proc_switch` restringe troca de processos ao processador de bootstrap porque o estado de escalonamento é global; chama então `mm_switch`, cujo assembly escreve CR3 com clobber de memória para o compilador. Esse clobber restringe movimentação pelo compilador, mas não substitui protocolo de invalidação multiprocessada. Mapear, trocar, desmapear e reutilizar páginas físicas são operações distintas com exigências próprias de sincronização.

## Descritores e alcance da proteção atual

A GDT do kernel contém código/dados de kernel, dados/código de usuário e descritor TSS de dois slots. `gdt_init` zera TSS de 104 bytes, inicializa RSP0 com o topo da pilha do kernel, coloca o deslocamento do mapa de E/S além da estrutura, carrega GDT, recarrega segmentos e carrega TR. Depois verifica o seletor TSS. Esses campos fornecem ingredientes para entrada controlada; não dispensam auditoria da propriedade de pilhas ao escalonar ou suportar múltiplos processadores.

A IDT contém 256 gates de dezesseis bytes. A inicialização comum usa atributo `0x8e`; `idt_set_user_gate` usa `0xee`, alterando privilégio do gate e preservando presença e tipo de interrupção. DPL do gate controla invocação por software; não faz o handler executar no privilégio do chamador. Todos esses gates usam IST zero. Essa observação identifica a seleção de pilha configurada, sem inventar uma pilha de emergência separada não instalada pelo código.

A sonda `python scripts/check_mmu.py --source .source` passou em 22 verificações de contrato e reproduziu três lacunas explicitamente nomeadas. A RAM é sintética e a entrega de exceções é substituída. O resultado estabelece comportamento do walker na revisão declarada; não estabelece boot do kernel, recuperação completa de faltas ou isolamento de privilégios. Os [manuais de programação de sistemas Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) continuam sendo referência normativa para permissões, falhas e transições. Capítulos específicos ainda precisam desenvolver alocação, invalidações, quadros de exceção e recuperação de recursos antes de considerar esses assuntos completamente documentados.
