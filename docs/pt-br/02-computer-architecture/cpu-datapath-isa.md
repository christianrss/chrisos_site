---
id: cpu-datapath-isa
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - logic-sequential
related:
  - x86-64-memory-privilege
  - emulator-theory
---

# Datapath da CPU e arquitetura do conjunto de instruções

## Processador como máquina arquitetural

Uma CPU não é definida apenas por possuir uma ALU. Na fronteira com software ela é uma máquina de estados governada por uma instruction-set architecture (ISA). A ISA especifica encodings e consequências visíveis: atualização de registradores, acesso à memória, controle de fluxo, exceções e efeitos de privilégio.

Estado arquitetural mínimo contém program counter, registradores gerais, flags e mecanismo de endereçamento de memória. x86-64 acrescenta estado de segmentos, control registers, descriptor tables, MSRs e uma arquitetura extensa de exceções.

## Datapath

O datapath move e transforma valores. Conceitualmente inclui registradores, ALU, shifters, address generation, atualização do instruction pointer, caminhos para memória e multiplexadores.

Uma soma entre registradores ilustra o contrato:

```text
decoder
  │
  ├── seleciona registrador A
  ├── seleciona registrador B
  └── seleciona ADD
             │
             ▼
            ALU
             │
             ├── resultado
             └── flags
             │
             ▼
      registrador destino
```

A ISA pode definir carry, zero, sign e overflow sem expor o circuito que os produz.

## Encoding de instruções

Código de máquina é a representação em bytes das operações e operandos. Assembly atribui nomes simbólicos a esses encodings. O assembler não inventa semântica; traduz uma representação legível para a forma binária definida pela ISA.

Instruções x86 têm comprimento variável e podem conter prefixes, opcode, ModR/M, SIB, displacement e immediate. Decodificação é, por isso, mais complexa que em muitas ISAs de largura fixa.

## Fetch, decode e execução

O ciclo pedagógico é fetch → decode → execute. Cores reais usam pipeline e sobreposição, mas o resultado arquitetural deve respeitar as regras da ISA.

Branches alteram o próximo endereço. Calls preservam retorno conforme instrução e convenção de software. Loads e stores interagem com a hierarquia de memória e podem gerar fault antes de produzir resultado arquitetural.

## ISA e ABI

ISA define o processador. Uma **ABI** define convenções usadas por software acima dela: registradores de argumentos, caller/callee-saved, alinhamento de stack, formatos de objeto e regras de símbolos.

Dois sistemas podem usar x86-64 e possuir ABIs de syscall diferentes. O compilador precisa obedecer ao encoding da ISA e à ABI do ambiente.

## Arquitetura privilegiada

Sistemas operacionais exigem operações indisponíveis a aplicações comuns. x86-64 fornece níveis de privilégio e instruções privilegiadas para trocar page-table root, instalar descriptor tables, controlar interrupções e configurar a máquina.

A autoridade do kernel não é uma convenção de C. Ela é imposta pelo processador durante a execução.

## ChrisOS e contratos arquiteturais

ChrisOS usa x86-64 como alvo principal. `kernel/metal` manipula diretamente page tables, GDT/IDT, interrupções e transições de contexto.

ChrisVM observa o mesmo contrato pelo outro lado. `chrisvm/chris_arch.h` define estado arquitetural que ChrisCPU precisa emular. `chrisvm/cpu/emulator/execute.c` interpreta operações e atualiza esse estado.

```text
visão do kernel                    visão do emulador
----------------                   -----------------
"executar MOV"       <contrato>    implementar MOV
"carregar CR3"       <contrato>    atualizar CR3 e tradução
"receber #PF"        <contrato>    detectar e entregar exceção
"OUT em porta"       <contrato>    despachar para o bus
```

A mesma ISA é um contrato consumido pelo sistema operacional e produzido pelo emulador.
