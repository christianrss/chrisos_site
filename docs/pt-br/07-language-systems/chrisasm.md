---
id: chrisasm
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/kcc/kcc.c
  - tools/test_chrisasm.c
symbols:
  - chrisasm_assemble
  - add_sym
  - add_reloc
  - local_find
  - local_define
  - add_fix
  - patch_fixups
  - emit_disp_reloc
  - emit_call_or_jmp
  - emit_local_branch
  - parse_mem
  - parse_line
  - publish_secs
depends_on:
  - native-toolchain
  - machine-code
  - x86-instruction-encoding
  - calling-conventions
related:
  - kcc
  - chriso
  - chrisld
---

# ChrisAsm

## Escopo

ChrisAsm é o assembler x86-64 nativo usado pelo toolchain experimental do ChrisOS. Ele recebe uma linguagem assembly textual deliberadamente limitada e produz uma imagem de objeto ChrisO contendo bytes de seções, símbolos e relocations.

O caminho atual é:

    texto assembly
        -> parser orientado a linhas
        -> encoder x86-64
        -> fixups de rótulos locais
        -> seções, símbolos e relocations ChrisO

O KCC emite assembly na sintaxe aceita pelo ChrisAsm. Portanto, ChrisAsm é a fronteira de código de máquina entre o front end do compilador e as etapas de objeto e linker. Ele não encapsula GNU as, NASM, LLVM MC nem outro assembler externo.

ChrisAsm deve ser entendido como um assembler específico do projeto, com um perfil controlado de instruções e diretivas, e não como um assembler x86-64 de propósito geral.

## Interface pública

O cabeçalho público expõe uma única função:

    int chrisasm_assemble(const char *src, ChrisoImage *out);

O chamador fornece uma string assembly terminada em zero e uma imagem ChrisO de destino. A função retorna zero em sucesso e menos um em falha.

Atualmente não existe objeto público de diagnóstico, estrutura de posição no fonte ou string textual de erro. Falha de parsing, instrução não suportada, estouro de capacidade, símbolo duplicado ou fixup local não resolvido produzem o mesmo retorno.

Isso mantém a interface pequena, mas torna a localização do erro dependente de ferramentas de nível superior ou da redução do caso de teste.

## Estado global e reentrância

A implementação usa estado mutável global ao processo:

- três buffers de 64 KiB para text, rodata e data;
- quatro contadores de tamanho de seção, incluindo o tamanho de BSS;
- seletor da seção corrente;
- flag de overflow;
- flag de binding local;
- tabela de rótulos locais;
- tabela de fixups pendentes na mesma seção.

Os principais limites fixos são:

| Recurso | Limite |
| --- | ---: |
| bytes de text | 65.536 |
| bytes de rodata | 65.536 |
| bytes de data | 65.536 |
| rótulos locais | 1.024 |
| fixups locais | 4.096 |
| buffer de linha | 512 bytes |
| símbolos ChrisO | 256 |
| relocations ChrisO | 512 |

Como buffers e contadores são globais, ChrisAsm não é reentrante. Duas chamadas concorrentes de chrisasm_assemble no mesmo espaço de endereçamento compartilham o estado de encoding e podem corromper uma à outra.

Uma evolução segura para assembly paralelo exige um contexto por execução.

## Estrutura da montagem

chrisasm_assemble percorre o fonte uma vez, linha por linha.

Na entrada ele:

1. inicializa a imagem ChrisO de saída;
2. limpa overflow e estado de fixups locais;
3. seleciona a seção text;
4. zera os tamanhos das seções;
5. copia caracteres para um buffer de linha de 512 bytes;
6. chama parse_line a cada linha completa;
7. resolve fixups de rótulos locais;
8. copia os bytes gerados para buffers alocados na imagem de saída.

Não se trata de um assembler tradicional de várias passagens com tokenização completa e árvore de expressões. ChrisAsm codifica instruções durante a leitura das linhas e usa uma tabela limitada de fixups apenas quando um destino local ainda não foi definido.

A arquitetura é simples e adequada ao assembly gerado pelo KCC, mas também é uma restrição sintática.

## Comportamento de linhas longas

O buffer de linha comporta 511 caracteres de fonte mais o terminador.

Quando uma linha ultrapassa essa capacidade, caracteres adicionais são ignorados até a quebra de linha. A implementação não transforma essa truncagem em erro explícito.

Assim, linhas muito longas geradas ou escritas manualmente podem ser silenciosamente encurtadas antes de parse_line processá-las.

O KCC normalmente produz linhas compactas, então isso não é esperado no caminho comum, mas é uma fronteira real do parser e deveria futuramente falhar de forma explícita.

## Seções

ChrisAsm reconhece quatro seções lógicas:

| Diretiva | Seção ChrisO | Bytes armazenados |
| --- | --- | --- |
| .text | CHRISO_SEC_TEXT | sim |
| .rodata | CHRISO_SEC_RODATA | sim |
| .data | CHRISO_SEC_DATA | sim |
| .bss | CHRISO_SEC_BSS | apenas tamanho |

As três primeiras possuem buffers fixos de 64 KiB no assembler.

BSS é diferente. .zero ou .skip em BSS aumenta o tamanho da seção sem emitir bytes. Na publicação final da imagem ChrisO, o ponteiro de BSS permanece nulo e seu tamanho registra a necessidade de espaço de endereçamento reservado.

Essa distinção é preservada pelo serializador ChrisO e posteriormente pelo linker.

## Diretivas de dados e símbolos

O perfil atual de diretivas inclui:

- .global e global;
- .local;
- .extern e extern;
- .zero e .skip;
- .ascii;
- .asciz;
- .byte;
- .quad;
- diretivas de seção text, rodata, data e BSS.

.global é aceita, mas não mantém uma tabela separada de exportação. Rótulos ordinários não locais já são emitidos como símbolos globais ChrisO.

.local afeta o binding da próxima definição de rótulo.

.extern cria ou reutiliza imediatamente um símbolo de função indefinido.

As diretivas de string usam um buffer temporário limitado a 256 bytes. O tratamento de escapes reconhece newline, carriage return e zero. Isso não constitui uma linguagem completa de escapes de assembler.

## Modelo de símbolos

ChrisAsm emite símbolos ChrisO por add_sym.

Um símbolo registra:

- nome em campo fixo de 64 bytes;
- índice de seção;
- offset relativo à seção;
- tamanho;
- binding;
- kind.

Os bindings usados são local, global e indefinido.

Um alvo externo referenciado antes da definição pode ser criado como indefinido e promovido quando sua definição aparece. Redefinir um símbolo já definido é rejeitado.

Rótulos em text são classificados como funções. Rótulos em outras seções são classificados como objetos.

Essa classificação é deliberadamente simples. O assembler não tenta reproduzir todo o modelo de símbolos ELF.

## Por que rótulos .L são especiais

Assembly gerado por compilador pode conter grande quantidade de rótulos internos. Colocar todo rótulo de controle de fluxo na tabela ChrisO consumiria rapidamente o limite de 256 símbolos do formato.

Por isso nomes iniciados por .L recebem tratamento especial.

Rótulos .L na mesma seção são mantidos numa tabela privada do assembler e não se tornam automaticamente símbolos ChrisO. Referências adiantadas são registradas numa tabela privada de fixups.

Após o parsing, patch_fixups calcula diretamente cada deslocamento relativo de 32 bits:

    deslocamento = offset_destino - (offset_campo + 4)

Em seguida os quatro bytes do deslocamento são escritos na seção gerada.

Isso evita trabalho desnecessário do linker para branches internos do compilador e preserva espaço na tabela de símbolos para nomes relevantes externamente.

## Fluxo de controle externo e entre seções

Um rótulo com aparência local nem sempre pode ser resolvido privadamente.

Se um alvo estiver definido em outra seção, ou se precisar sobreviver até o linker, ChrisAsm passa a usar símbolo real mais relocation ChrisO.

Calls, jumps e branches condicionais para símbolos externos não resolvidos usam relocations relativas ao PC.

O caminho de call/jump emite deslocamento zero e cria relocation R_X86_64_PLT32 com addend -4.

O addend -4 corresponde à semântica PC-relative do x86-64: o deslocamento é calculado em relação ao endereço imediatamente posterior ao campo de quatro bytes.

O teste host verifica diretamente:

    call foo

Ele exige uma relocation, tipo R_X86_64_PLT32, addend -4 e símbolo indefinido chamado foo.

## Referências RIP-relative a dados

O parser de memória suporta a sintaxe do projeto:

    [rel simbolo]

Nesse caso ChrisAsm codifica forma RIP-relative de ModR/M, escreve placeholder zero de 32 bits e cria relocation R_X86_64_PC32 com addend -4.

O símbolo referenciado é criado como objeto indefinido quando necessário.

Esse é o mecanismo principal para referências position-relative a globais produzidas pelo KCC.

## Operandos de memória baseados em registrador

O parser também aceita formas simples:

    [registrador]
    [registrador + deslocamento]
    [registrador - deslocamento]

O deslocamento é literal inteiro. Não existe parser geral para base mais índice vezes escala mais aritmética simbólica.

emit_mem_modrm seleciona a largura do deslocamento:

- sem deslocamento quando possível;
- deslocamento de 8 bits com sinal para -128 a 127;
- caso contrário, deslocamento de 32 bits.

Bases RSP/R12 recebem o byte SIB exigido. RBP/R13 sem deslocamento explícito são forçados para uma forma com deslocamento porque a codificação ModR/M zero teria outro significado.

## Modelo de encoding

ChrisAsm emite bytes x86-64 diretamente.

A implementação constrói:

- prefixos REX;
- opcodes;
- bytes ModR/M;
- bytes SIB quando necessários;
- immediates e displacements;
- placeholders de relocation.

O encoder é C explícito, e não uma tabela gerada de instruções.

Isso torna o subset suportado inspecionável, mas significa que cada nova forma de instrução exige implementação e validação específicas.

## Famílias de instruções suportadas

O parser atual contém formas necessárias ao KCC e ao caminho do toolchain nativo. Entre elas:

- mov e movzx;
- lea;
- add, sub e imul;
- div;
- xor, or, and e not;
- cmp e test;
- shl;
- push e pop;
- call e ret;
- jmp e branches condicionais;
- sete;
- syscall;
- cli, sti, hlt e pause;
- in e out;
- lretq e iretq;
- str e ltr;
- invlpg;
- operações suportadas com prefixo lock.

Branches reconhecem igualdade, desigualdade, comparações unsigned e comparações signed.

A lista não implica cobertura completa de x86-64. Uma instrução só é aceita quando parse_line implementa aquela forma concreta de operandos.

## Perfil de registradores

ChrisAsm contém helpers próprios para mapear nomes de registradores x86-64 em números e larguras de encoding.

O encoder suporta registradores gerais usados pelo compilador, incluindo registradores estendidos que exigem bits REX.

O teste host valida um caso diretamente: push r8 precisa produzir prefixo REX 0x41 seguido pelo opcode 0x50.

SIMD, x87 e superfícies amplas de AVX/AVX-512 não fazem parte do perfil atual.

## Complexidade dos fixups locais

local_find realiza busca linear na tabela de rótulos locais.

Com L rótulos, cada lookup é O(L). patch_fixups faz um lookup para cada fixup pendente, então o pior caso é O(F vezes L), onde F é a quantidade de fixups.

Com limites atuais de 4.096 fixups e 1.024 rótulos, o custo é finito, porém não é assintoticamente eficiente.

Hash table ou estrutura ordenada seria mais adequada se unidades de assembly crescerem significativamente.

O desenho atual prioriza estado fixo simples e comportamento previsível de alocação.

## Publicação das seções e ownership

O encoding acontece em buffers estáticos do assembler.

publish_secs transforma esses buffers temporários na imagem ChrisO. Para cada seção não vazia entre text, rodata e data, aloca exatamente o tamanho gerado e copia os bytes.

Build host usa malloc. Build freestanding usa kmalloc.

BSS não recebe alocação.

A imagem resultante contém, portanto, armazenamento alocado dinamicamente para as seções materializadas. Consumidores precisam obedecer ao ciclo de vida esperado pelo toolchain. ChrisAsm não expõe uma função pública correspondente de destruição.

Essa assimetria de ownership é uma área em que uma API futura de ciclo de vida do objeto aumentaria a robustez.

## Comportamento de falhas

ChrisAsm rejeita entrada não suportada ou malformada retornando -1.

Fontes de falha incluem:

- mnemonic desconhecido;
- forma de operando não suportada;
- definição duplicada de símbolo;
- registrador inválido;
- limite de símbolos ou relocations;
- overflow de bytes de seção;
- overflow da tabela de rótulos locais;
- overflow da tabela de fixups;
- fixup privado não resolvido;
- falha de alocação ao publicar as seções.

Em geral o parser falha de forma fechada para uma operação desconhecida.

A principal exceção é linha de fonte longa demais, que é truncada em vez de rejeitada.

## Evidência de validação

tools/test_chrisasm.c fornece evidência executável host para contratos importantes.

O teste confirma que:

1. uma função pequena com mov rax, 42 e ret é montada;
2. o text produzido começa com prefixo REX de 64 bits;
3. mnemonic desconhecido é rejeitado;
4. call não resolvido produz relocation PLT32 com addend -4;
5. a relocation aponta para símbolo indefinido chamado foo;
6. push r8 gera a codificação esperada de registrador estendido.

Isso demonstra o comportamento das formas testadas. Não comprova todas as ramificações de parse_line nem todas as combinações possíveis de encoding x86-64.

## Fronteira de segurança e privilégio

ChrisAsm consegue codificar instruções privilegiadas como cli, sti, hlt, ltr e invlpg.

O assembler não impõe privilégio de execução. Ele apenas transforma texto em bytes.

A validade de privilégio depende de onde o código gerado será executado. Ferramentas do kernel devem tratar código montado como conteúdo nativo executável com as mesmas implicações de confiança de qualquer compilador ou assembler.

ChrisAsm não é sandbox.

## Limitações atuais

As limitações mais importantes são:

- estado global não reentrante;
- limite fixo de 64 KiB por seção materializada;
- limites de 256 símbolos e 512 relocations do ChrisO;
- 1.024 rótulos locais;
- 4.096 fixups locais;
- ausência de diagnósticos ricos;
- truncagem silenciosa de linhas longas;
- gramática de diretivas específica do projeto;
- cobertura incompleta de instruções x86-64;
- ausência de avaliador geral de expressões assembly;
- ausência de gramática geral base-index-scale;
- ausência de superfície SIMD/x87/AVX;
- implementação manual das formas de instrução.

Essas são fronteiras da implementação, não limitações da arquitetura x86-64.

## Limite entre estado atual e roadmap

Uma evolução do ChrisAsm pode incluir:

- trocar estado global por contexto explícito;
- adicionar diagnósticos estruturados com linha e coluna;
- rejeitar explicitamente overflow do buffer de linha;
- substituir busca linear de rótulos quando unidades maiores exigirem;
- ampliar instruções a partir de descrição orientada por tabelas;
- adicionar motor de expressões para constantes, símbolos e aritmética relocável;
- definir regras explícitas de destruição e ownership da imagem;
- tornar dinâmicas as capacidades de seção, símbolo e relocation.

Nenhum desses itens deve ser confundido com comportamento já implementado.

## Proveniência da revisão

Este capítulo documenta ChrisAsm conforme observado no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

A autoridade principal é compiler/chrisasm/chrisasm.c, com a interface pública em compiler/chrisasm/chrisasm.h. As estruturas ChrisO vêm de compiler/chrisld/chriso.h, e tools/test_chrisasm.c é a evidência host executável citada.
