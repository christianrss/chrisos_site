---
id: emulator-exceptions
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_raise
  - deliver_frame
  - chris_push8
  - chris_pop8
  - chris_seg_load_cs
  - chris_translate
  - chris_va_read
  - chris_va_write
  - maybe_irq
depends_on:
  - x86-decoding
  - emulator-flags
  - x86-64-memory-privilege
related:
  - emulator-paging
  - chrisvm-chriscpu
  - determinism-replay
---

# Exceções, interrupções e entrega de faults no ChrisCPU

## Escopo

O ChrisCPU usa um ponto central de entrega, chris_raise, para faults síncronos, interrupções de software e vetores de interrupção externa injetados. A implementação possui dois modos de operação materialmente diferentes.

Quando nenhuma IDT foi carregada, uma exceção é reportada ao monitor do ChrisVM como CHRIS_EXIT_EXCEPTION. Esse modo é útil para bring-up e testes no host porque o guest não precisa instalar handlers antes que faults se tornem observáveis.

Quando IDTR é diferente de zero, o ChrisCPU tenta entregar o evento ao guest por meio de um gate de IDT de 64 bits e de um frame na stack convidada. Se a própria entrega falhar, a implementação tenta double fault e pode finalmente parar com CHRIS_EXIT_TRIPLE.

Este capítulo descreve o que a fonte realmente implementa na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56. O modelo atual é útil para experimentos controlados no emulador, mas ainda não é uma arquitetura completa de interrupções/exceções em long mode.

## Estado de exceção em ChrisCpu

ChrisCpu mantém estado arquitetural e estado de controle do emulador relevante para faults:

| Campo | Papel |
|---|---|
| arch.rip | instruction pointer atual do guest |
| arch.rsp | stack pointer atual do guest |
| arch.rflags | estado de controle/status salvo e restaurado |
| arch.cs / arch.ss | estado modelado dos segmentos de código e stack |
| arch.gdtr / arch.idtr | registradores das tabelas de descritores |
| arch.cr2 | endereço do page fault modelado mais recente |
| arch.cpl | nível de privilégio usado pelos checks de paginação |
| ex_vector | vetor de exceção para diagnóstico |
| ex_error | error code para diagnóstico |
| delivering | diferente de zero enquanto um frame de exceção é construído |
| halted | interrompe o run loop |
| exit_reason | classificação de parada visível ao monitor |
| irq_pending / irq_vector | interrupção externa pendente |
| sti_delay | inibição de uma instrução após STI |
| rip_dirty | impede o incremento normal de RIP pelo run loop |

Os campos diagnósticos ex_vector/ex_error são distintos do frame na stack do guest. Eles são especialmente importantes no modo monitor, em que nenhum handler convidado recebe o evento.

## Modo 1: exceções visíveis ao monitor sem IDT

deliver_frame começa verificando se base e limit de IDTR são ambos zero. Nesse caso, a exceção não é entregue dentro do guest.

Em vez disso, o código:

- define exit_reason como CHRIS_EXIT_EXCEPTION;
- grava vector e error em ex_vector/ex_error;
- define halted;
- retorna um status especial para chris_raise.

chris_raise reconhece esse resultado e retorna ao run loop sem converter o evento em double fault.

É por isso que test_chrisvm.c consegue executar invalid opcode, page fault, general-protection fault ou divide error sem construir uma IDT. O teste host inspeciona depois chris_exception_vector e, para page faults, CR2.

Esse comportamento é uma convenção do monitor ChrisVM, não um modo do hardware x86. Hardware real não substitui entrega de exceção por uma saída ao host apenas porque IDTR contém zeros.

## Modo 2: entrega pela IDT do guest

Com uma IDT presente, deliver_frame calcula o endereço do gate como:

    IDTR.base + vector * 16

O limit da IDT precisa incluir os dezesseis bytes completos do gate em long mode. A implementação lê o gate por chris_va_read, portanto o próprio acesso ao descritor passa pela tradução de memória virtual do guest.

Depois o gate é validado contra um subconjunto estreito:

- Present precisa estar definido;
- o tipo precisa ser 0xE, interrupt gate, ou 0xF, trap gate;
- o campo IST precisa ser zero.

IST diferente de zero é rejeitado. Task gates e outros tipos legacy não são suportados.

O target offset é reconstruído a partir das partes baixa, média e alta do gate. O target selector é passado para chris_seg_load_cs.

## Carregamento do code segment

chris_seg_load_cs resolve selectors somente pela GDT. read_desc rejeita seletor nulo, verifica o limit da GDT e lê um descritor de oito bytes por memória virtual do guest.

O descritor de destino aceito precisa ter:

- Present definido;
- bit de código/executable definido;
- bit L de long mode definido.

O CS carregado recebe base zero, limit 0xffffffff e atributos copiados do descritor.

Essa validação é intencionalmente incompleta. O caminho não implementa todas as regras de long mode para descriptor privilege level, requested privilege level, segmentos conforming, seleção por LDT ou todas as restrições de type. O carregamento deve ser entendido como validação estrutural mínima, não como protection check completo.

## O frame atual do guest

Depois de carregar o CS de destino, deliver_frame registra RSP e RIP atuais. Em seguida empilha cinco valores de 64 bits nesta ordem:

    seletor SS
    RSP antigo
    RFLAGS
    seletor CS de destino
    RIP do frame

Se o evento possui error code, esse valor de 64 bits é empilhado por último.

Como a stack cresce para baixo, o handler encontra o error code no topo quando presente, seguido por RIP, CS, RFLAGS, RSP antigo e SS antigo.

Esse frame é uma convenção simplificada do projeto e difere da entrada arquitetural de long mode em pontos importantes.

### RSP e SS são sempre empilhados

Em x86-64, o frame exato depende de transição de privilégio e de IST/stack switching. A implementação atual sempre salva RSP e SS, embora rejeite IST e não realize mudança de stack por CPL.

O IRETQ em execute.c espelha essa convenção simplificada ao sempre desempilhar RIP, CS, RFLAGS, RSP e SS.

### O CS salvo não é o CS interrompido

deliver_frame chama chris_seg_load_cs com o selector do gate antes de empilhar o frame. Depois empilha esse mesmo selector de destino como o campo CS salvo.

Logo, o frame não preserva o CS original interrompido quando o handler usa selector diferente. Um IRETQ posterior não consegue reconstruir o CS anterior a partir desse frame.

Isso é um defeito concreto de compatibilidade, não apenas uma funcionalidade opcional ainda ausente.

### IRETQ não revalida os segmentos restaurados

O caminho atual de IRETQ desempilha RIP, CS, RFLAGS, RSP e SS e então atribui diretamente os campos selector de CS e SS. Ele não chama chris_seg_load_cs e não reconstrói atributos dos descritores restaurados.

Produtor e consumidor do frame formam, portanto, um par específico do projeto, não um mecanismo completo de retorno de privilégio x86.

### A remoção do error code cabe ao handler

IRETQ não consome error code de exceção. Se deliver_frame empilhou um, o handler convidado precisa ajustar a stack antes de executar IRETQ. Isso segue a convenção geral de x86 de que o error code é separado do frame de IRET, mas é particularmente importante porque o ChrisCPU já usa um frame fixo simplificado de cinco palavras.

## Interrupt gate versus trap gate

Para um gate tipo 0xE, deliver_frame limpa IF em RFLAGS. Um trap gate 0xF mantém IF inalterado.

Para os dois tipos suportados, o caminho atual limpa:

- TF, bit 8;
- RF, bit 16;
- VM, bit 17.

Depois define RIP como o target offset e marca rip_dirty para impedir que o incremento normal do interpretador sobrescreva a transferência.

Esse estado representa apenas um subconjunto da transição arquitetural completa. A implementação não afirma cobrir todas as regras de flags na entrada de long mode.

## Seleção de RIP para fault, trap e interrupt

O RIP salvo no frame é o valor de cpu->arch.rip no instante em que chris_raise é chamado. Portanto, o caller determina se o evento se comporta como fault ou trap.

Para faults comuns de execução, como divide error, o executor chama chris_raise antes que o run loop avance RIP. O endereço salvo aponta para a instrução que falhou.

Para INT de software, execute.c avança explicitamente RIP para a próxima instrução e define rip_dirty antes de chamar chris_raise. O frame contém, assim, o endereço de retorno posterior ao INT.

INT3 usa o mesmo caminho CHRIS_OP_INT e também salva o endereço da próxima instrução, coerente com semântica de restart de breakpoint como trap.

Interrupções externas são consideradas por maybe_irq depois da execução normal e do avanço de RIP. Se IF está definido, há IRQ pendente e sti_delay não bloqueia a entrega, maybe_irq chama chris_raise com o vetor injetado. O RIP salvo corresponde à próxima fronteira de instrução.

O desenho é compacto, mas sua correção depende de todo produtor de fault chamar chris_raise no ponto correto de retirement.

## Caminhos de invalid opcode

Existem dois caminhos importantes para instrução inválida.

Se chris_decode retorna valor negativo por faltar uma parte estrutural da instrução, chriscpu.c gera CHRIS_EX_UD.

Se o decode termina mas classifica a instrução como CHRIS_OP_UD, execute.c chega ao caminho de operação inválida e gera CHRIS_EX_UD.

Checks selecionados de legalidade também usam fail_ud. Por exemplo, uso de LOCK não suportado em formas ALU sobre registrador é rejeitado por #UD.

O capítulo de decodificação explica por que truncamento estrutural e codificações reconhecidamente inválidas permanecem resultados de parser distintos mesmo quando ambos terminam no vetor 6.

## Divide error

DIV e IDIV geram CHRIS_EX_DE em dois casos explícitos:

- divisor igual a zero;
- quociente calculado não cabe na largura do destino.

O executor verifica o limite antes de gravar quotient e remainder. Isso evita truncar silenciosamente um quociente maior que a largura permitida.

test_chrisvm.c verifica divisão por zero e overflow de quociente, observando vetor zero no modo monitor.

## General protection vinda da MMU e de operações de sistema

chris_translate distingue endereço virtual não canônico de uma falha normal de paginação. Um endereço não canônico retorna status próprio para chris_va_read/chris_va_write, que gera CHRIS_EX_GP com error code zero.

Alguns acessos de sistema inválidos ou não suportados também usam #GP. O caminho de MSR, por exemplo, gera #GP para índice fora do conjunto modelado.

Ainda é apenas um subconjunto das origens possíveis de #GP. Validação completa de segmentação, privilégio, descritores, target canônico e system instructions geraria mais protection faults em x86-64 real.

## Geração de page fault

Falhas de paginação surgem em chris_translate. Quando um check normal de presença ou permissão falha, o helper de memória virtual grava o endereço virtual que falhou em CR2 e gera CHRIS_EX_PF.

Os bits de error code de page fault modelados são:

| Bit | Significado | Fonte atual |
|---:|---|---|
| 0 | P: protection violation versus not-present | definido em faults de permissão |
| 1 | W/R | definido para writes |
| 2 | U/S | definido quando CPL atual é 3 |
| 4 | I/D | definido em instruction fetch quando NX se aplica |

A implementação ainda não modela todos os bits modernos de page fault, como reserved-bit violation, protection keys, shadow stack ou estados específicos de SGX.

Para write protection, writes de supervisor respeitam páginas read-only quando CR0.WP está definido. Acessos de user exigem user bit ao longo do page-table walk. Permissão de execução verifica NX quando EFER.NXE está ativo.

CR2 recebe o endereço virtual corrente do chunk que falhou. Em uma operação que cruza páginas, ele pode ser posterior ao endereço inicial da solicitação de memória.

## Falhas do backing físico não são page faults do guest

Leituras das page tables e acessos físicos finais podem falhar porque o endereço físico modelado não corresponde a RAM ou a um device.

A implementação distingue essa falha do modelo da máquina de um fault normal das page tables do guest. Em vários desses caminhos ela define CHRIS_EXIT_UNMAPPED, para a CPU e registra o endereço para diagnóstico, em vez de gerar #PF ao guest.

A separação é útil: uma tradução válida das page tables para um recurso físico que o emulador não implementa não é a mesma condição que um PTE not-present.

## Faults durante entrega de exceção

A própria entrega de exceção lê a IDT, lê descritor da GDT e escreve um frame na stack do guest. Qualquer uma dessas operações pode sofrer falha de memória virtual.

O campo delivering impede chamadas recursivas a chris_raise por chris_va_read/chris_va_write enquanto um frame já está sendo construído. O helper de memória devolve falha para deliver_frame, que transforma isso em falha de entrega.

Isso evita recursão sem controle:

    page fault ao empilhar frame de page fault
    -> page fault ao empilhar frame de page fault
    -> ...

A falha segue em vez disso para o caminho de escalada de double fault.

## Escalada para double fault

chris_raise oferece no máximo dois estágios de entrega.

O primeiro tenta o vetor original.

Se deliver_frame informa falha de entrega em vez de modo monitor, chris_raise substitui o vetor por CHRIS_EX_DF, força error code zero e realiza uma segunda tentativa.

Se a entrega de double fault funciona, o guest pode continuar no handler de #DF. Se falha, o emulador classifica a situação como triple fault.

Essa política é deliberadamente mais simples que a classificação de pares de exceções Intel/AMD. Em hardware real, a geração de double fault depende da combinação entre exceptions contributory e page faults durante a entrega. O ChrisCPU atualmente transforma qualquer falha de construção do frame em tentativa de #DF, em vez de implementar a matriz completa de classes.

## Triple fault

Depois de duas tentativas de entrega que falham, chris_raise:

- limpa delivering;
- define exit_reason como CHRIS_EXIT_TRIPLE;
- define halted;
- despeja o trace ring;
- retorna falha.

O modelo para no monitor. Ele não emula o reset de plataforma normalmente associado a triple fault no caminho processador/plataforma.

CHRIS_EXIT_TRIPLE é, portanto, uma condição terminal visível ao debugger do ChrisVM.

## Escritas parciais do frame e rollback

chris_push8 calcula RSP menos oito, tenta escrever o valor em memória virtual e somente depois confirma o novo RSP. Isso evita decrementar RSP quando aquela escrita individual falha.

Porém, deliver_frame executa vários pushes em sequência. Se os primeiros funcionam e um push posterior falha, não existe transação que restaure as escritas anteriores ou o RSP original antes de iniciar a entrega de double fault.

Um frame de exceção que falha pode, portanto, deixar a stack parcialmente modificada. A segunda tentativa de entrega observa esse estado já alterado.

Entrega precisa de exceção em x86 possui requisitos arquiteturais mais estritos. Construção transacional ou rollback explícito tornaria o emulador mais previsível e mais próximo do hardware.

## Limitações de descritores e privilégio

O caminho atual de IDT/GDT possui fronteiras explícitas:

- sem suporte a IST;
- sem TSS stack switching;
- sem seleção de stack em transição de CPL;
- sem carregamento de code selector via LDT;
- sem validação completa DPL/RPL/CPL;
- sem regras de conforming code segment;
- INT de software não valida gate DPL;
- selectors CS/SS restaurados por IRETQ não são revalidados por descritores;
- sem semântica completa de nested task ou task gate.

Essas limitações são centrais para qualquer software que espere transições reais entre user e kernel.

## Estado diagnóstico durante double fault

chris_raise grava ex_vector e ex_error antes de entrar no loop de entrega. Quando a primeira tentativa falha e o vetor local é substituído por #DF, esses campos diagnósticos não são regravados na fonte atual.

Assim, um double fault entregue com sucesso ainda pode deixar ex_vector/ex_error descrevendo o evento original em vez do vetor final entregue. O comportamento do guest é controlado pelo frame, mas o diagnóstico do monitor pode se tornar enganoso.

Isso deve ser corrigido antes de ex_vector ser tratado como registro autoritativo do último evento entregue.

## Evidência atual de validação

test_chrisvm.c possui testes diretos em modo monitor para:

- #UD por invalid opcode;
- #PF e CR2 por endereço traduzido sem backing válido;
- #GP por endereço não canônico;
- #DE por divisão por zero;
- #DE por overflow de quociente;
- #GP por MSR não suportado;
- #PF ao fazer push para endereço de stack que falha.

Esses testes verificam origens importantes de exceção e vetores visíveis ao host.

O arquivo de testes inspecionado não constrói uma IDT do guest e não exercita o caminho completo de sucesso de deliver_frame. Portanto, ainda não há evidência de integração equivalente para entrada por interrupt gate versus trap gate, correção do frame salvo, entrega de double fault, triple fault, rejeição de IST, regras de DPL em software INT ou round trip com IRETQ.

## Prioridades de hardening

Os trabalhos de maior valor são:

1. salvar o CS interrompido antes de carregar o CS do handler e colocar o selector correto no frame;
2. definir layouts de frame separados para entrega no mesmo CPL, transições de privilégio e IST;
3. implementar TSS/IST stack switching e validar entradas de IST;
4. validar DPL do gate para software interrupts e regras CPL/RPL/DPL na transferência para code segment;
5. fazer IRETQ revalidar e reconstruir estado de segmentos restaurados;
6. adicionar a matriz arquitetural de pares de exceções em vez de escalar toda falha de entrega de forma idêntica;
7. tornar a construção do frame transacional ou definir rollback para writes parciais;
8. atualizar ex_vector/ex_error quando a escalada altera o vetor entregue;
9. adicionar testes end-to-end com IDT/GDT do guest para interrupt e trap gates;
10. adicionar testes determinísticos para entrega bem-sucedida de #DF e triple fault terminal;
11. ampliar error-code de page fault e checks de reserved bits;
12. separar e documentar machine-unmapped exits de guest protection faults em todas as fronteiras de memória.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisCPU possui report de exceções útil em modo monitor, entrega básica por gate de IDT de long mode, construção de error code de page fault, escalada para double fault e estado terminal de triple fault. A implementação ainda não é um modelo completo de transição de privilégio ou entrega precisa de exceções. Em especial, a convenção atual de frame, o tratamento do CS salvo e a ausência de IST/TSS são fronteiras de compatibilidade que precisam ser corrigidas antes que transições de exceção entre user e kernel possam ser consideradas confiáveis.
