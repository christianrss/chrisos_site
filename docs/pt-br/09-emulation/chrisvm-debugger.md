---
id: chrisvm-debugger
lang: pt-br
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/config.c
  - chrisvm/frontend/main.c
  - chrisvm/debug/trace.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/common/exceptions.c
symbols:
  - chris_dump_cpu
  - chris_trace_push
  - chris_trace_dump
  - CHRIS_EXIT_BREAK
depends_on:
  - chrisvm-boot
  - chrisvm-chriscpu
related:
  - determinism-replay
  - x86-decoding
---

# Debugger e trace do ChrisVM

## Escopo

O ChrisVM possui atualmente um debugger host-side mínimo ao redor do interpretador ChrisCPU. Ele serve principalmente para bring-up, não para debugging source-level.

As facilities disponíveis são:

- loop interativo de step/continue/registers;
- um breakpoint por RIP;
- trace de instruções;
- ring com 256 instruções recentes;
- dump de registradores;
- exit reasons como break, exception e step limit.

Não há symbol lookup, source mapping, watchpoints, reverse execution, protocolo remoto GDB ou debugger multi-CPU.

Este capítulo documenta a revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Ativação

A CLI aceita:

    --debug

Nesse modo, a frontend entra em debug_loop em vez de chamar chris_run uma única vez com todo o budget.

O debugger usa stdin para comandos e stderr/logging para saída.

A opção:

    --headless

limpa cfg.debug no parser, desabilitando o loop interativo.

## Comandos

O conjunto atual é:

    s       step
    c       continue
    r       registers
    q       quit
    b HEX   set breakpoint address

A seleção é feita apenas pelo primeiro caractere da linha.

Não existe parser estruturado, histórico ou expressions.

## Dump de registradores

O comando r chama:

    chris_dump_cpu

O dump atual inclui:

- RIP;
- RSP;
- RFLAGS;
- RAX;
- RCX;
- RDX;
- RBX;
- RSP;
- RBP;
- RSI;
- RDI;
- CR0;
- CR2;
- CR3;
- CR4.

Somente os oito primeiros GPRs aparecem.

Ficam ausentes:

- R8-R15;
- CR8;
- segmentos;
- GDTR/IDTR;
- EFER/MSRs;
- XMM;
- CPL;
- exception state;
- IRQ pending.

É um dump útil para bring-up, não uma visão completa de ChrisArchitectureState.

## Step

O comando s limpa halted e executa:

    chris_run(machine, 1)

O loop ChrisCPU processa no máximo uma instrução.

Se nada mais encerrar a CPU, o retorno normal é CHRIS_EXIT_STEP_LIMIT.

Depois o debugger imprime os registradores novamente.

Não existe um segundo executor de single-step: o debugger reutiliza o run loop normal.

## Continue

O comando c limpa cpu->has_break antes de executar com max_steps.

Esse comportamento contém um defeito concreto.

A sequência interativa esperada:

    b ADDRESS
    c

ativa o breakpoint no primeiro comando, mas o segundo o desativa antes da execução.

Logo, "set breakpoint e continue até ele" não funciona como esperado.

O breakpoint ainda pode permanecer em steps unitários ou quando configurado por --break antes da execução.

Esse problema deve ser corrigido antes de b/c ser descrito como workflow convencional.

## Mecanismo de breakpoint

ChrisCPU possui:

    break_rip
    has_break

No início de cada iteração, antes do fetch:

    if has_break && RIP == break_rip
        exit_reason = CHRIS_EXIT_BREAK
        halted = 1

A instrução no endereço não é executada.

Esse é um breakpoint do host/interpreter, não DR0-DR7 x86.

O guest não enxerga esse mecanismo.

## Um único breakpoint

Existe apenas um break_rip.

Novo breakpoint substitui o anterior.

Não há:

- lista;
- enable/disable individual;
- temporary breakpoint;
- condition expression.

## Breakpoint por CLI

O parser aceita:

    --break=ADDRESS

e define cfg.break_rip/cfg.has_break.

ChrisCPU copia os valores ao criar a CPU.

No run não interativo esse breakpoint não é limpo automaticamente.

Assim, atualmente --break fornece comportamento de "run until address" mais consistente que b seguido de c no debugger.

## Exit reason BREAK persistente

cpu_run limpa halted no início.

Porém, só troca exit_reason para CHRIS_EXIT_NONE quando o reason anterior não é CHRIS_EXIT_BREAK.

Ao retomar depois de um breakpoint, BREAK pode continuar temporariamente presente enquanto a execução avança.

Normalmente outro resultado final o substitui, como step limit ou HLT.

Mesmo assim, isso complica a classificação de errors porque alguns caminhos convertem falha em CHRIS_EXIT_EXCEPTION somente quando exit_reason é NONE.

O resume explícito deveria limpar o resultado BREAK anterior.

## Trace contínuo

Com cfg.trace ativo, cada instrução decodificada produz uma linha semelhante a:

    CPU0 #N RIP ADDRESS TEXT

antes de executar.

A linha contém:

- step counter + 1;
- RIP atual;
- texto produzido por chris_format_insn.

O label é sempre CPU0, coerente com a máquina atual de uma CPU.

O formatter é diagnóstico, não disassembler completo.

## Ring de instruções recentes

Mesmo com --trace desabilitado, cada instrução decodificada com sucesso é enviada a:

    chris_trace_push

A capacidade é:

    CHRIS_TRACE_RING = 256

Cada entry guarda:

- RIP;
- comprimento até 15 bytes;
- raw bytes;
- texto formatado.

Assim existe histórico recente mesmo sem trace contínuo.

## Sobrescrita do ring

ring_i cresce continuamente.

ring_n cresce até 256.

Entries novas sobrescrevem antigas modulo a capacidade.

chris_trace_dump calcula o início lógico e imprime em ordem cronológica.

O índice usa:

    index & (CHRIS_TRACE_RING - 1)

Isso funciona porque 256 é potência de dois.

A invariável não possui static assertion. Mudar a constante para valor não potência de dois quebraria a indexação.

## Dump do ring

chris_trace_dump imprime:

    recent instructions:

seguido de RIP e texto formatado.

Embora os bytes crus estejam armazenados, o dump atual não os mostra.

Isso perde evidência valiosa quando o formatter ou decoder é justamente o objeto de análise.

## Triple fault

No caminho de triple fault, exceptions.c chama automaticamente:

    chris_trace_dump(cpu)

antes de retornar falha.

Portanto, os 256 últimos decodes podem ser disponibilizados no log após falha terminal de exception delivery.

Não existe comando equivalente no debug_loop para pedir esse dump manualmente.

## Dependência direta de cpu->arch

chris_dump_cpu lê diretamente:

    m->cpu->arch

em vez de backend->get_state.

É o mesmo vazamento de abstração documentado no capítulo de estado arquitetural.

Funciona em ChrisCPU.

Em ChrisHV real, debugger confiável exigirá sincronização com VMCS/VMCB ou retrieval backend-neutral.

## Logging

Trace/dump usam:

    chris_log

ChrisMachine armazena callback e context.

A frontend padrão instala callback que escreve em stderr.

Isso desacopla geração de mensagens do destino host.

## Flags de trace

ChrisConfig expõe:

- trace;
- trace_memory;
- trace_io;
- trace_mmio.

trace é efetivamente usado para instruções.

trace_io possui logging parcial apenas no caminho de output.

trace_memory e trace_mmio são copiados para ChrisCpu, mas não foi encontrado caminho geral consumindo essas flags na revisão inspecionada.

Portanto, a superfície de configuração é mais ampla que o observability implementado.

## Sem memory examine

O loop não possui comando para:

- ler virtual memory;
- ler physical memory;
- escrever memória;
- dump de stack;
- page-table walk.

Existem APIs internas/host, mas não são expostas pelo debugger.

Para OS bring-up isso é uma lacuna de alto valor.

## Sem edição de registradores

O debugger imprime registradores, mas não possui comando para alterá-los.

A library tem setters parciais de GPR/CR, porém o terminal debugger não os usa.

## Sem symbols

Breakpoints recebem endereço numérico via strtoull.

Não há symbol table lookup.

Um comando:

    b function_name

não é suportado.

O loader também não mantém metadata ELF para isso.

## Sem source-level debug

Não existe DWARF parser ou line mapping.

O debugger opera no nível de máquina.

## Sem watchpoints

Os memory helpers não consultam estado de watchpoint.

Não há break em read/write/access.

## Sem debug registers x86

ChrisArchitectureState não contém DR0-DR7.

O mecanismo host não produz semântica arquitetural #DB.

Breakpoints do debugger e debug registers do guest são conceitos diferentes.

## Sem GDB remote

Não há GDB RSP no caminho inspecionado.

Uma implementação futura deveria primeiro estabilizar APIs backend-neutral de state, memory e breakpoints.

## Stop reasons

Exit reasons relevantes incluem:

- CHRIS_EXIT_BREAK;
- CHRIS_EXIT_STEP_LIMIT;
- CHRIS_EXIT_HLT;
- CHRIS_EXIT_SHUTDOWN;
- CHRIS_EXIT_EXCEPTION;
- CHRIS_EXIT_TRIPLE;
- CHRIS_EXIT_UNMAPPED.

O loop interativo encerra automaticamente para HLT, shutdown, triple e exception.

BREAK e STEP_LIMIT permitem continuar interagindo.

## Step counter

ChrisCPU incrementa cpu->steps no fim de cada iteração.

O trace visual usa:

    steps + 1

na instrução prestes a executar.

É contador determinístico de execução, não medida de cycles.

## Momento do breakpoint

O check acontece antes do fetch.

Se RIP é igual a break_rip:

- não há fetch;
- não entra entry nova no trace ring;
- steps não aumenta;
- TSC não aumenta pela instrução parada.

Isso forma uma fronteira limpa de host breakpoint.

## Falha antes do decode

chris_trace_push só ocorre depois de decode bem-sucedido.

Se fetch ou decode falhar, a instrução problemática não vira entry nova no ring.

Histórico anterior permanece.

Para debugging do decoder seria melhor capturar também os bytes obtidos antes de tentar decodificar.

## Debug state versus architectural state

Campos como:

- break_rip;
- has_break;
- trace flags;
- trace ring;

ficam em ChrisCpu runtime state, fora de ChrisArchitectureState.

Isso é conceitualmente correto.

Porém, snapshot que pretenda retomar uma sessão de debugging pode precisar preservar esses dados separadamente.

## Cobertura de testes

A suíte principal usa intensamente chris_run e exit reasons, mas não testa de forma dedicada o debug_loop interativo.

O bug b + c demonstra por que esses workflows também precisam de automação.

Casos importantes:

- --break para antes da instrução;
- b + c;
- step counter;
- wraparound do ring;
- ordem do ring;
- triple-fault dump;
- completeness do CPU dump;
- stale BREAK no resume.

## Prioridades de hardening

Os próximos trabalhos de maior valor são:

1. corrigir b + c;
2. limpar BREAK antigo ao retomar;
3. múltiplos breakpoints;
4. memory examine/write;
5. dump completo backend-neutral;
6. mostrar raw bytes no trace dump;
7. implementar trace-memory/trace-io/trace-mmio de verdade;
8. comando manual de ring dump;
9. register editing com semântica explícita;
10. symbol lookup;
11. watchpoints;
12. API de debugger independente do backend;
13. opcionalmente GDB RSP;
14. testes automatizados do terminal debugger.

## Nota de revisão

Na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56, o ChrisVM possui um debugger de baixo nível funcional para bring-up: step, dump de CPU, um breakpoint host, instruction trace e ring de 256 instruções usado automaticamente no triple fault. O defeito imediato mais importante é continue limpar o breakpoint configurado por b. As demais fronteiras incluem estado incompleto, ausência de memory/symbol/watchpoint support e dependência direta do layout interno cpu->arch.
