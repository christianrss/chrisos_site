---
id: gdt-tss
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/linker.ld
  - kernel/metal/user_enter.c
symbols:
  - gdt_init
  - gdt_reload_kernel_segments
  - gdt_read_tr
  - enter_user
depends_on:
  - x86-64-memory-privilege
  - privilege-rings
related:
  - idt-exceptions
  - user-mode-entry
  - processes-syscalls
---

# GDT e TSS

## Escopo e pré-requisitos

A Global Descriptor Table continua fazendo parte do contrato arquitetural do x86-64 mesmo que o long mode não utilize mais segmentação como mecanismo principal para traduzir endereços comuns. No ChrisOS, paginação fornece o isolamento de espaços de endereçamento, mas o processador ainda consulta descritores de segmento para metadados de privilégio, estado dos segmentos de código/dados e para o Task State Segment. Portanto, um kernel que atravessa a fronteira entre ring 0 e ring 3 não pode tratar a GDT como simples legado histórico.

Este capítulo descreve o mecanismo de tabelas de descritores, o conjunto exato instalado pelo ChrisOS, a representação do TSS de 64 bits, a codificação binária usada para seu descritor, a sequência necessária para recarregar segmentos depois de `lgdt`, o papel de `rsp0` e a relação entre essas estruturas e a entrada em user mode via `iretq`. Paginação é tratada separadamente: a GDT não substitui page tables.

## Segmentação em long mode

Nos modos x86 legados, um endereço lógico envolve seletor de segmento e deslocamento, e o descritor selecionado contribui base, limite, tipo e atributos de privilégio. Em 64 bits, o comportamento de base e limite de CS, DS, ES e SS é em grande parte achatado, mas os seletores e os descritores continuam carregando semântica de proteção. CS participa da determinação do nível corrente de privilégio, e transições como entrega de interrupções e `iretq` validam as relações entre privilégios.

Um seletor não é um endereço em bytes da GDT. Os bits a partir do bit 3 codificam o índice; os bits inferiores carregam indicador da tabela e Requested Privilege Level. O ChrisOS define:

| Símbolo | Seletor | Uso |
|---|---:|---|
| `GDT_KERNEL_CODE` | `0x08` | código 64-bit em ring 0 |
| `GDT_KERNEL_DATA` | `0x10` | dados/stack em ring 0 |
| `GDT_USER_DATA` | `0x18` | descritor de dados/stack de ring 3 |
| `GDT_USER_CODE` | `0x20` | código 64-bit de ring 3 |
| `GDT_TSS` | `0x28` | descritor de sistema do TSS de 64 bits |

Ao entrar em user mode, os seletores de usuário são combinados com `3`. Assim `enter_user` usa `GDT_USER_CODE | 3` para CS e `GDT_USER_DATA | 3` para SS, explicitando RPL 3.

## Layout de descritores no ChrisOS

`gdt.c` reserva sete slots de 64 bits, alinhados a 16 bytes. O slot 0 é o descritor nulo. Os slots 1 a 4 são descritores comuns de código/dados. Os slots 5 e 6 juntos formam o descritor de sistema de 16 bytes exigido pelo TSS no long mode.

Os quatro valores são:

| Slot | Valor | Significado |
|---:|---|---|
| 1 | `0x00af9a000000ffff` | código do kernel |
| 2 | `0x00cf92000000ffff` | dados do kernel |
| 3 | `0x00cff2000000ffff` | dados de usuário |
| 4 | `0x00affa000000ffff` | código de usuário |

Os access bytes diferenciam código executável e dados graváveis e codificam DPL 0 ou DPL 3. Os descritores de código usados em 64 bits têm o bit L apropriado. O kernel zera a tabela antes de gravá-la, evitando que slots não utilizados contenham acidentalmente bits Present ou campos de endereço herdados de memória não inicializada.

## Task State Segment de 64 bits

O TSS x86-64 não é usado pelo ChrisOS como objeto de hardware para troca completa de processos. Seu papel relevante é fornecer ao processador estado de stack privilegiada e os slots da Interrupt Stack Table.

A estrutura packed `tss64` contém os campos arquiteturais:

- `rsp0`, `rsp1` e `rsp2` para ponteiros de stack associados a transições de privilégio;
- `ist1` a `ist7` para stacks especiais de interrupção;
- campos reservados definidos pela arquitetura;
- `iomap_base`, que posiciona o bitmap de permissões de I/O.

O código usa `_Static_assert` para exigir exatamente 104 bytes. Essa verificação protege uma ABI de hardware: se padding do compilador alterasse deslocamentos, o processador passaria a ler campos errados mesmo que o código C parecesse correto.

Na inicialização, TSS e GDT são zerados. `tss.rsp0` recebe `__stack_top`. O linker script cria essa stack em `.bss` reservando 1 MiB entre `__stack_bottom` e `__stack_top`. `iomap_base` recebe `sizeof(tss)`. Como não há bitmap anexado depois do TSS, o offset aponta além do limite do segmento e não cria permissões de I/O acidentais.

Todos os campos IST permanecem zero na revisão analisada. Portanto, o ChrisOS ainda não direciona double fault, NMI ou outras exceções a stacks dedicadas via IST. A entrada NMI existente roda sobre a stack interrompida. Isso é uma limitação concreta da implementação atual.

## Codificação do descritor do TSS

O descritor do TSS em 64 bits ocupa 16 bytes. `install_tss_descriptor` obtém o endereço linear do TSS estático, usa `sizeof(tss) - 1` como limite e distribui os campos de base e limite entre `gdt[5]` e `gdt[6]`.

O access byte é `0x89`: Present, DPL 0, descritor de sistema e tipo “available 64-bit TSS”. A primeira metade contém as porções inferiores da base e do limite; a segunda carrega os 32 bits superiores da base.

O código usa máscaras e shifts em vez de bit-fields C. Isso evita transformar um formato binário definido pela CPU em dependência do layout de bit-fields escolhido pelo compilador.

## Sequência de carregamento

`gdt_init` realiza:

```text
zerar GDT e TSS
    |
gravar descritores kernel/user
    |
definir TSS.rsp0 e iomap_base
    |
codificar descritor TSS
    |
montar operando { limit, base } para GDTR
    |
lgdt
    |
far return para recarregar CS = 0x08
    |
DS/ES/SS = 0x10
FS/GS = 0
    |
ltr 0x28
    |
str -> verificar TR == 0x28
```

`lgdt` altera GDTR, mas não recarrega retroativamente os caches ocultos de descritores associados aos registradores de segmento já ativos. Por isso o ChrisOS faz imediatamente uma transferência de controle distante: empilha o seletor de código do kernel e o RIP de um label local e executa `lretq`. Assim CS é revalidado contra a GDT nova.

Depois, DS, ES e SS recebem `0x10`; FS e GS têm seus seletores zerados. `ltr` carrega o task register com `0x28`. `gdt_read_tr` usa `str` para ler o seletor visível de TR, e `gdt_init` chama `panic` caso o resultado não seja `GDT_TSS`.

## Por que `rsp0` é necessário

Uma transição de um contexto menos privilegiado para ring 0 exige uma stack confiável. A stack do usuário não pode simplesmente continuar sendo usada como stack do kernel: ela pertence a um contexto não confiável, pode estar não mapeada e pode ser deliberadamente construída para corromper estado privilegiado.

O TSS fornece o ponteiro de stack de ring 0 que a CPU usa quando uma entrada privilegiada exige troca de stack. No ChrisOS atual, `rsp0` aponta para a stack única definida pelo linker. Isso corresponde ao modelo corrente, no qual a execução e a troca dos processos de usuário são restritas ao BSP.

Esse arranjo não equivale a uma arquitetura geral de stacks de kernel por thread. Um scheduler preemptivo com múltiplas threads de usuário normalmente precisaria atualizar `rsp0` para a stack de kernel da thread ativa ou fazer a entrada inicialmente em uma stack segura por CPU. A implementação revisada ainda não precisa nem implementa esse mecanismo.

## Relação com entrada em ring 3

`enter_user` mostra a direção oposta da fronteira. O TSS não “troca para user mode”. O código monta manualmente o frame consumido por `iretq`:

```text
SS = GDT_USER_DATA | 3
RSP = stack solicitada do usuário
RFLAGS = 0x202
CS = GDT_USER_CODE | 3
RIP = entry point solicitado
iretq
```

A CPU valida os seletores e a transição contra a GDT. Logo, os descritores de usuário são pré-requisito para executar em CPL 3, embora tradução e isolamento de memória sejam controlados por CR3 e pelos bits U/S das page tables.

Antes da transição, o ChrisOS registra um endereço de retorno ao kernel via `syscall_set_kernel_return`. A saída de processo e a manipulação de fault de usuário podem depois reescrever o frame de interrupção e retornar a ring 0. Esse mecanismo pertence aos capítulos de syscalls e entrada de usuário.

## Estado por CPU e SMP

`gdt_reload_kernel_segments` repete `lgdt`, reload de CS, segmentos de dados e `ltr`. A existência dessa função é importante porque GDTR, caches de segmento e TR são estado arquitetural de cada processador lógico. Carregar esses registradores no BSP não os instala automaticamente em um AP.

A memória da tabela pode ser compartilhada, mas o ato de carregar GDTR/TR continua per-CPU. Se futuramente o TSS passar a ser per-CPU, a distinção ficará ainda mais forte: cada processador deverá possuir ou selecionar seu próprio TSS e sua própria stack de entrada segura.

## Invariantes

| Invariante | Falha produzida se violado |
|---|---|
| `sizeof(tss64) == 104` | CPU lê campos em offsets incorretos |
| descritores user têm DPL 3 | load de seletor ou `iretq` falha |
| CS do kernel é válido antes das interrupções | exceção pode virar cascata de faults |
| descritor TSS ocupa slots 5 e 6 | base truncada ou descritor inválido |
| TR contém `0x28` | transição usa estado TSS errado/ausente |
| `rsp0` aponta para memória kernel mapeada e gravável | fault ao construir frame privilegiado |
| seletores user têm RPL 3 | privilégio solicitado não corresponde a CPL 3 |
| GDT/TSS permanecem residentes | registradores apontam para armazenamento inválido |

GDT e TSS são objetos estáticos; sua lifetime é a mesma do kernel e não existe caminho de teardown ou ownership pelo heap.

## Comportamento de falhas

Instalação incorreta da GDT pode gerar #GP, #SS, #TS ou uma sequência de faults durante reload de segmento, entrega de interrupção ou `iretq`. Algumas dessas falhas ocorrem antes de a infraestrutura normal de panic estar em condições de diagnosticá-las. Por isso a tabela deve ser estabelecida cedo e o código verifica diretamente TR depois de `ltr`.

A ausência de IST dedicada reduz a capacidade de diagnóstico quando a stack corrente está corrompida. Uma IST específica para double fault é uma técnica comum de robustez que não está presente nesta revisão.

## Fronteira de segurança

A GDT não substitui permissões de página. No ChrisOS ela estabelece seletores válidos com privilégio e o contrato de stack privilegiada do TSS. O isolamento de memória de usuário depende da paginação; validação de ponteiros de syscalls depende da tradução explícita e de testes dos bits Present/User/Write. Os mecanismos se complementam.

`lgdt` e `ltr` são instruções privilegiadas. Código de usuário não pode reconfigurar GDTR ou TR. Descritores do kernel permanecem DPL 0, enquanto os descritores destinados ao ring 3 são DPL 3.

## Desempenho

Configuração de GDT/TSS pertence à inicialização, não ao hot path de referências comuns à memória. Em long mode, a CPU não percorre a GDT a cada load/store. O ponto crítico é garantir que o estado já esteja correto quando uma transição de privilégio ocorrer.

O uso atual de um `rsp0` fixo evita atualização do TSS a cada context switch. Essa simplicidade deriva do modelo atual de processos de usuário presos ao BSP e deixa de ser válida se o modelo de escalonamento evoluir.

## Evidência e validação

A revisão fornece evidência direta por meio do assert de 104 bytes, constantes explícitas dos descritores, codificação manual do TSS, sequência `ltr`/`str` e consumo dos seletores user por `enter_user`.

Validação dinâmica completa deve incluir execução real em ring 3, entrada por syscall/interrupção, faults deliberados de usuário e transições repetidas. O volume de validação deve registrar esses gates; a mera existência de `gdt_init` não prova todos os casos.

## Limitações atuais

Há um TSS estático, `rsp0` fixo na stack criada pelo linker, ISTs zeradas e nenhum bitmap de permissões de I/O. O ChrisOS não usa hardware task switching; processos são estruturas do próprio sistema e raízes de page tables.

## Mapa de fonte

A implementação principal está em `kernel/metal/gdt.c` e `kernel/metal/gdt.h`. Os símbolos de stack consumidos pelo TSS vêm de `kernel/metal/linker.ld`. `kernel/metal/user_enter.c` consome concretamente os seletores de ring 3. O Source Atlas contém a íntegra desses arquivos na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
