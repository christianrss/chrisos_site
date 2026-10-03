---
id: stage-compilers
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - tools/seed_selfhost.c
  - kernel/tools/shell.c
  - kernel/tools/chrisbuild.c
  - kernel/metal/kcc_job.c
  - makefile
symbols:
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_write
  - chriso_read
  - chrisld_link
  - chrisld_link_objects
depends_on:
  - self-hosting-bootstrap
  - selfhost-levels
related:
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# Staging de compiladores e convergência

## Escopo

Compiler staging responde a uma pergunta mais estreita que self-hosting geral:

> Um estágio do compiler consegue produzir o estágio seguinte, e estágios sucessivos podem ser comparados por uma regra de equivalência definida?

Para o ChrisOS, a notação natural é:

```text
KCC0 -> KCC1 -> KCC2
```

Cada seta significa que o compiler à esquerda produziu o compiler à direita.

O repositório atual ainda não implementa essa cadeia completa.

Ele possui os componentes necessários para iniciar esse processo, mas ainda há problemas concretos de source size, headers, driver, runtime, linking e proveniência que impedem tratar KCC1 como compiler self-produced demonstrado.

## Definição de KCC0

KCC0 deve significar o KCC bootstrap produzido pela toolchain externa.

O target:

```text
host-kcc
```

gera:

```text
build/host/kcc
```

usando `HOST_CC`, atualmente GCC.

O source set é:

- `tools/kcc_main.c`;
- `compiler/kcc/kcc.c`;
- `compiler/chrisasm/chrisasm.c`;
- `compiler/chrisld/chriso.c`.

Esse é um bootstrap legítimo.

Porém, continua sendo software produzido pelo host.

## O que o driver host realmente produz

`tools/kcc_main.c` lê um source C com stdio/malloc do host.

Depois chama:

```text
kcc_compile_named(...)
```

e serializa a `ChrisoImage` por:

```text
chriso_write(...)
```

O executável de linha de comando produz um object ChrisO, não um compiler ELF final.

Seu uso é essencialmente:

```text
kcc input.c output.chriso
```

Ainda é necessário um estágio de link posterior.

## KCC0 depende da ABI do host

O driver host inclui:

- `stdio.h`;
- `stdlib.h`;
- `string.h`.

Ele usa `FILE`, `fopen`, `fseek`, `ftell`, `fread`, `fwrite`, `malloc` e `free`.

Logo, `build/host/kcc` é um programa da runtime do host.

O seed copia esse arquivo para:

```text
BIN/KCC.ELF
```

em ChrisFS, mas o filename não altera sua proveniência nem suas assumptions de runtime.

O shell do guest não executa esse arquivo quando o usuário digita `kcc`.

## O comando `kcc` no guest é compiler embutido

No ChrisOS, o shell:

```text
kcc path.c
```

aloca source buffer e chama diretamente:

```text
kcc_compile_source(...)
```

a partir da biblioteca KCC já linkada no kernel em execução.

Há compilação real dentro do guest, mas o compiler foi incorporado a um kernel bootstrap produzido pelo host.

Isso é evidência de execução nativa no guest, não de KCC0 produzindo KCC1.

## KCC1 precisa de definição de artifact

Antes do staging, o projeto precisa definir o que exatamente é KCC1.

Possibilidades:

1. executável ELF nativo ChrisOS com KCC, ChrisAsm, ChrisO e driver próprio;
2. conjunto de objects ChrisO posteriormente linkado em outro estágio;
3. biblioteca de compiler reconstruída e incorporada a um novo kernel.

São artifacts diferentes com provas diferentes.

A árvore atual não possui target KCC1 nem gate que escolha uma dessas formas como canonical.

## KCC1 standalone exige driver nativo

O `tools/kcc_main.c` atual não pode simplesmente virar driver de guest sem alteração porque usa libc e file I/O do host.

Um KCC1 standalone precisa de interface nativa para:

- abrir/ler source;
- escrever output;
- emitir diagnostics;
- alocar memória;
- retornar status de processo.

O shell atual já demonstra partes desses serviços, mas elas ainda não estão empacotadas como um compiler ELF standalone.

## O seed atual não cria KCC1

`tools/seed_selfhost.c` copia:

```text
build/host/kcc
```

para:

```text
BIN/KCC.ELF
```

Isso é bootstrap seeding.

Não executa KCC0 sobre o source do KCC.

Não linka KCC1.

Não executa o resultado.

Portanto, a existência de `BIN/KCC.ELF` não pode ser tratada como compiler staging.

## Blocker de tamanho do source

`compiler/kcc/kcc.c` possui aproximadamente 141 KiB.

Os entry points de compilação do guest leem muito menos.

O shell aloca:

```text
65536 bytes
```

e chama:

```text
fs_read(path, src_buf, 65535)
```

O KCC job em background também usa limite da ordem de 64 KiB.

`chrisbuild_mk_kernel` define:

```text
BUILD_SRC_MAX = 65536
```

Portanto, o source atual do KCC nem sequer pode ser lido por completo por esses caminhos.

Esse é um blocker direto de KCC1 antes do parser começar.

## Buffers internos do KCC

Internamente existem buffers maiores:

```text
KCC_PP_MAX  = 256 KiB
KCC_ASM_MAX = 256 KiB
```

O source bruto cabe em 256 KiB, desde que o caller consiga fornecê-lo por completo.

Ainda não está provado que o source preprocessado ou o assembly gerado permaneçam abaixo dos dois limites.

Um stage gate precisa medir isso.

## Blocker de resolução de header

`compiler/kcc/kcc.c` inclui:

```text
<string.h>
```

O preprocessor do próprio KCC trata como headers built-in apenas:

- `stdint.h`;
- `stdbool.h`;
- `stddef.h`;
- `stdarg.h`.

Para outros includes ele procura uma lista fixa de diretórios do projeto.

A árvore possui `kernel/metal/string.c` e `LIB/STRING.H` para ChrisC, mas não há um `string.h` nos paths usados pelo include resolver do KCC que satisfaça diretamente esse include.

Assim, self-compilation direta encontra um problema real de header availability.

## KCC seleciona o branch freestanding

O compiler predefine macros como:

```text
__x86_64__ = 1
__freestanding__ = 1
__VERSION__ = "KCC"
```

Portanto, ao compilar seu próprio source, o branch `__freestanding__` é selecionado.

Esse branch usa `heap.h` e `fs.h` em vez de stdio/stdlib do host.

Esses diretórios já aparecem no include search do KCC.

Isso ajuda o bootstrap, mas não resolve o include incondicional de `string.h`.

## ChrisAsm e ChrisLd também dependem de string API

KCC1 não é apenas `kcc.c`.

A pipeline usa ChrisAsm e ChrisO e, no caso de artifact ELF standalone, também ChrisLd.

Esses sources também incluem `string.h`.

Portanto, o problema precisa ser resolvido para a toolchain inteira.

Uma opção coerente é criar uma interface freestanding `string.h` compatível com os prototypes reais do kernel e torná-la parte explícita do bootstrap.

## A linguagem precisa compilar o próprio compiler

Depois de resolver source size e headers, KCC ainda precisa aceitar toda a sintaxe usada por sua própria implementação.

O source do KCC utiliza:

- enums;
- typedefs;
- structs aninhadas;
- arrays fixos;
- pointers;
- arithmetic 64-bit;
- preprocessing condicional;
- macros;
- calls;
- estado global static;
- string literals;
- loops e branches.

KCC suporta vários desses recursos isoladamente.

Isso não prova que consegue compilar a implementação completa.

A única prova válida é compilar o source real da revisão.

## Exclusões intencionais da linguagem

KCC rejeita classes de C que estão fora do subset.

Por exemplo, valores floating-point comuns são explicitamente rejeitados.

Também há limites fixos de símbolos, macros, structs, fields, typedefs, enums, initializers e parameters.

Para staging sustentável, o próprio source da toolchain precisa permanecer dentro de um perfil "C compilável por KCC".

Uma alteração válida para GCC pode quebrar o bootstrap.

## Perfil source seguro para staging

O projeto deve formalizar um perfil verificável por CI para os files da toolchain.

Esse perfil deve declarar:

- sintaxe permitida;
- directives de preprocessor permitidas;
- headers permitidos;
- include depth;
- source/preprocessed size máximo;
- runtime calls permitidas;
- object/relocation features permitidas.

Mudança que saia desse perfil deve falhar CI até o KCC ganhar suporte correspondente.

## Construção de KCC1 com múltiplos objects

ChrisLd já possui:

```text
chrisld_link_objects(...)
```

capaz de combinar múltiplas `ChrisoImage`.

Ele lida com TEXT, RODATA, DATA e BSS, resolve globals e aplica relocations.

Essa função é base melhor para compiler staging que `chriso_merge_text`.

Porém, existe limite:

```text
LD_OBJS = 32
```

Um build de KCC1 precisa caber nessa quantidade ou ampliar o limite.

## Limites do ChrisO

Cada `ChrisoImage` possui:

```text
CHRISO_SYM_MAX = 256
CHRISO_REL_MAX = 512
```

Esses limits são por object.

Translation units grandes podem atingir esses limites.

Dividir a toolchain em múltiplos objects reduz pressão individual, mas exige build graph e link dependencies explícitos.

## Manifest de stage e proveniência

Cada estágio precisa de um manifest próprio, e esse manifest deve ser tratado como parte do artifact de evidência.

Ele deve registrar pelo menos:

- hash do compiler produtor;
- revisão exata dos sources;
- lista ordenada de translation units;
- hashes dos headers freestanding;
- hashes de ChrisAsm, ChrisO e ChrisLd usados;
- opções/defines da compilação;
- hashes de cada object ChrisO;
- hash do ELF final.

Sem esse registro, é possível produzir um arquivo chamado KCC1 sem conseguir provar qual compiler realmente produziu cada parte.

O manifest também permite detectar mistura acidental de objects antigos, support code host-built ou artifacts cacheados de um estágio anterior.

## KCC jobs não são compiler stages

`kernel/metal/kcc_job.c` permite compilar source em background pelo job system e escrever:

```text
<source>.CHRISO
```

É infraestrutura útil para compilação nativa paralela.

Mas continua com input máximo de 65536 bytes.

Além disso, compila um source isolado e não produz automaticamente um compiler stage seguinte.

Paralelismo de compilação é independente de proveniência.

## Critério de aceitação de KCC1

Um gate forte para KCC1 precisa:

1. começar de hash declarado de KCC0;
2. compilar o source real de KCC/ChrisAsm/ChrisO;
3. usar apenas headers/runtime freestanding declarados;
4. linkar um artifact KCC1 nativo;
5. validar seu ELF;
6. executar KCC1 dentro do ChrisOS;
7. compilar corpus de conformidade fixo;
8. registrar hashes e diagnostics dos outputs.

Só depois disso KCC1 deve ser considerado atingido.

## Definição de KCC2

KCC2 deve ser produzido por KCC1 usando a mesma revisão de source e as mesmas regras de build de KCC1.

A cadeia é:

```text
GCC -> KCC0
KCC0 -> KCC1
KCC1 -> KCC2
```

Se KCC1 for apenas copiado ou relinkado de objects produzidos por KCC0, a cadeia não é válida.

O compiler que efetivamente produz KCC2 precisa ser KCC1.

## Significado de convergência

KCC1 e KCC2 não precisam ser byte-identical enquanto o build não for determinístico.

Mas a regra precisa ser declarada antes da comparação.

Possíveis níveis:

1. ambos passam o mesmo corpus;
2. ambos geram ChrisO semanticamente equivalente;
3. loadable sections dos executáveis são idênticas;
4. ELF completo é byte-identical.

O objetivo final mais forte é o nível 4 após remover metadata não determinística.

## Comparação de ChrisO

Como KCC naturalmente produz ChrisO, object-level convergence é particularmente útil.

Para corpus fixo, pode-se comparar:

- section sizes;
- section bytes;
- symbol tables;
- relocation tables.

`chriso_write` já fornece serialization estável para gerar hashes.

Isso permite detectar divergência entre stages antes de envolver diferenças de ELF/linker.

## Comparação de comportamento

Hash de object não deve ser a única evidência enquanto o bootstrap ainda evolui.

Também é útil comparar:

- casos de compile success/failure;
- diagnostics relevantes;
- generated symbols;
- runtime results dos programas compilados.

Isso detecta regressões semânticas mesmo quando layout binário muda de forma legítima.

## Staging de ChrisAsm e ChrisLd

Um compiler stage real é na prática um toolchain stage.

KCC1 precisa usar versões identificadas de:

```text
KCC
ChrisAsm
ChrisO
ChrisLd
driver/runtime
```

Caso contrário, um KCC novo pode continuar dependendo silenciosamente de support code host-built, enfraquecendo a proveniência.

O record do stage deve armazenar hashes de todos esses componentes.

## Trusting trust

Compiler staging não elimina confiança no bootstrap inicial.

Um host compiler ou KCC0 malicioso pode injetar comportamento não visível no source.

Convergência reduz divergência acidental, mas não prova ausência de comportamento malicioso.

No longo prazo, a confiança pode ser reduzida por:

- diverse double compilation;
- build de KCC0 com compilers independentes;
- comparação de stage outputs;
- bootstrap mínimo;
- publicação de hashes e receitas.

## Status atual

Para a revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, a classificação conservadora é:

```text
KCC0:
  implementação host-built existe e é testada

KCC1:
  não demonstrado como compiler artifact self-produced

KCC2:
  não demonstrado

convergência:
  não demonstrada
```

O KCC embutido no guest é útil, mas não deve ser renomeado para KCC1 porque não foi produzido por KCC0.

## Caminho de engenharia imediato

O caminho mais curto para staging real é:

1. fornecer contrato freestanding de `string.h`;
2. remover o teto de input de 64 KiB;
3. criar driver KCC standalone nativo do guest;
4. definir manifest exato da toolchain;
5. compilar units em ChrisO;
6. linkar com `chrisld_link_objects`;
7. validar e executar KCC1;
8. usar KCC1 para produzir KCC2;
9. comparar KCC1/KCC2 por regra definida;
10. automatizar tudo como gate fail-closed.

## Nota de revisão

Este capítulo foi criado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. O projeto possui KCC0 host-built válido e compiler real executando dentro do guest, mas ainda não possui prova KCC0→KCC1→KCC2. O limite de input de 64 KiB, a falta de resolução freestanding de `string.h`, ausência de driver KCC standalone no guest e falta de gates de comparação entre stages são blockers concretos.
