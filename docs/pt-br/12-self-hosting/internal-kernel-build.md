---
id: internal-kernel-build
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/chrisbuild.h
  - kernel/tools/shell.c
  - kernel/tools/native_link.c
  - compiler/kcc/kcc.c
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/metal/linker.ld
  - tools/stamp_kernel.c
  - tools/buildstamp.c
  - tools/seed_selfhost.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_clean
  - chrisbuild_mk_install
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - self-hosting-bootstrap
  - stage-compilers
related:
  - selfhost-levels
  - reproducible-builds
  - validation-evidence
---

# Kernel produzido internamente

## Escopo

ChrisOS contém um comando executado dentro do guest:

```text
mk kernel
```

Ele tenta compilar sources C selecionados do kernel com KCC, combinar as imagens ChrisO resultantes, linká-las com ChrisLd e gravar:

```text
BIN/KERNEL.ELF
```

Esse é um caminho interno real de build.

Ele ainda não é equivalente ao build de produção do repositório.

A diferença é estrutural, e não apenas falta de acabamento.

O build host e o build interno consomem artifact graphs diferentes, suportam conjuntos diferentes de linguagem e code generation, usam modelos de link distintos e integram o boot de formas diferentes.

## Comandos expostos no shell

O shell oferece:

```text
mk kernel
mk clean
mk install
```

`mk kernel` chama `chrisbuild_mk_kernel`.

`mk clean` chama `chrisbuild_mk_clean`.

`mk install` chama `chrisbuild_mk_install`.

Os três executam dentro do kernel já bootado e trabalham sobre ChrisFS.

## Manifest interno

O builder espera:

```text
SYS/BUILD.MK
```

e interpreta apenas um subset pequeno de sintaxe semelhante a Make.

Os controles reconhecidos são:

- `KERNEL_OUT=`;
- `KERNEL_LD=`;
- `C_OBJECTS=`;
- `ASM_OBJECTS=`, apenas como marcador que encerra a coleta de C.

O output default é:

```text
BIN/KERNEL.ELF
```

e o load address default é:

```text
0xffffffff80000000
```

O parser não é GNU Make.

Ele não avalia variables, rules, dependencies, pattern rules, recipes, conditionals ou dependencies de generated files.

## Ausência de dependency graph

O builder executa uma passagem linear pelos paths C listados.

Não compara mtimes, não acompanha dependencies de headers, não mantém cache de objects, não detecta translation units inalteradas e não faz incremental rebuild.

Cada `mk kernel` recompila todas as entradas do manifest.

Isso simplifica o bootstrap, mas transforma o manifest no único build graph real.

Qualquer header, generated input ou source não presente no estado seeded de ChrisFS fica fora do modelo.

## Limite de quantidade de objetos

`BuildManifest` armazena no máximo:

```text
BUILD_MAX_OBJ = 48
```

paths C.

O makefile de produção atual expande para aproximadamente:

```text
129 objetos C
1 objeto assembly
130 objetos de kernel no total
```

antes mesmo dos helper artifacts usados durante o build.

Logo, o manifest interno não consegue sequer enumerar todo o conjunto C atual sem aumentar sua capacidade.

Esse é um blocker imediato para build completo.

## Assembly não é construído

O kernel de produção inclui:

```text
kernel/metal/idt_stubs.o
```

montado por NASM.

O parser interno reconhece:

```text
ASM_OBJECTS=
```

somente para deixar de coletar C.

Ele não interpreta uma lista de assembly, não chama ChrisAsm e não acrescenta esses objects ao link.

Assim, o artifact interno omite assembly arquitetural que faz parte do kernel host.

## Inputs gerados não fazem parte do modelo

O build de produção contém dependencies geradas.

Por exemplo, GLSL é convertido em:

```text
kernel/gfx/shader/sh_src.h
```

por um script Python antes de determinados graphics objects serem compilados.

O builder interno não possui dependency graph nem executor de generators.

Ele assume que todo source referenciado já existe em ChrisFS na forma final.

Um build completo precisará ou copiar artifacts gerados para ChrisFS ou implementar geração equivalente dentro do próprio sistema.

## Limite por source file

Cada source C listado é lido em:

```text
BUILD_SRC_MAX = 65536
```

bytes.

Files acima de 65535 bytes não podem ser consumidos integralmente.

O próprio `compiler/kcc/kcc.c` possui aproximadamente 141 KiB.

Portanto, o builder atual não consegue compilar esse translation unit como está.

Qualquer outro source que ultrapasse o mesmo limite sofre a mesma restrição.

## Etapa de compilação

Para cada path C o builder:

1. converte o path do manifest para um path ChrisFS;
2. lê o source;
3. chama `kcc_compile_source`;
4. recebe uma `ChrisoImage`;
5. faz merge na imagem combinada.

A primeira falha de leitura ou compilação aborta o processo.

Não há object cache, dependency tracking, build paralelo ou retenção de artifacts intermediários.

## Conversão de paths

Um path iniciado por:

```text
kernel/
```

é convertido para:

```text
SYS/KERNEL/
```

e as letras são transformadas em maiúsculas.

O build interno trabalha, portanto, sobre uma cópia do source tree mantida em ChrisFS.

Ele não lê diretamente o checkout host.

Um source desatualizado em ChrisFS pode produzir artifact diferente mesmo quando o host aponta para o Git revision esperado.

Por isso um gate forte deve hash-ear o source set realmente presente no guest.

## Mismatch entre KCC e o perfil do kernel atual

O kernel de produção não usa um único perfil de C/codegen.

O makefile aplica flags especiais a partes gráficas, incluindo SSE2, execução floating-point em XMM e `-ffast-math`.

KCC rejeita valores escalares comuns de `float` como fora do subset atual.

Logo, vários translation units do kernel gráfico contemporâneo não podem ser presumidos compiláveis pelo KCC interno.

O projeto precisa ampliar o KCC ou definir um bootstrap kernel reduzido.

## O perfil de compilação host é mais rico

O build host também controla propriedades de ABI/codegen por flags como:

```text
-ffreestanding
-fno-stack-protector
-fno-pic
-fno-pie
-mno-red-zone
-mcmodel=kernel
```

e algumas unidades mudam para SSE2/XMM.

KCC possui seu próprio code generator x86-64 e não traduz essas flags individualmente.

Portanto, conseguir parsear e gerar machine code não prova equivalência de ABI.

Um gate completo precisa validar calling convention, relocations, high-half addressing, ausência de red zone e comportamento de registers relevantes a interrupts.

## Algoritmo de merge

Depois de cada compile, o builder chama:

```text
chriso_merge_text(&merged, &unit)
```

Esse é um dos limites centrais do path atual.

Apesar de KCC produzir uma `ChrisoImage` completa, o build agrega somente TEXT em um buffer compartilhado de 64 KiB.

## O que `chriso_merge_text` preserva

A função:

- concatena os bytes de TEXT;
- ajusta offsets de symbols definidos em TEXT;
- copia symbol entries;
- copia relocations;
- ajusta relocation offsets dentro de TEXT.

Ela não implementa uma composição completa de múltiplas sections.

## O que é descartado

RODATA, DATA e BSS dos objects individuais não são acumulados na imagem final.

Isso pode eliminar storage necessário para:

- string literals;
- globals inicializados;
- globals zerados;
- static data;
- tables;
- constant arrays.

Mesmo quando KCC compila uma unidade corretamente, conservar apenas TEXT não é suficiente para semântica geral de kernel.

## Limite do TEXT combinado

O merge possui teto explícito de:

```text
65536 bytes
```

para TEXT.

O kernel de produção atual tem complexidade muito superior a um estágio educacional text-only de 64 KiB.

Assim, o builder atual deve ser entendido como bootstrap subset builder, não como substituto do pipeline de produção.

## Ownership de memória por unidade

KCC retorna `ChrisoImage` com storage de TEXT alocado dinamicamente.

Depois do merge, `chrisbuild_mk_kernel` libera:

```text
unit.sec[CHRISO_SEC_TEXT]
```

e zera esse pointer.

Isso é compatível com o design text-only atual.

Um builder multi-object futuro precisa definir ownership também para RODATA, DATA e demais buffers antes de reter objects completos até o link.

## ChrisLd é mais capaz que o builder atual

ChrisLd já possui:

```text
chrisld_link_objects(...)
```

que combina múltiplas imagens preservando:

- TEXT;
- RODATA;
- DATA;
- BSS;
- global symbols;
- relocations.

Essa API é muito mais próxima do que o kernel build interno realmente precisa.

Porém, `chrisbuild_mk_kernel` não a utiliza.

Ele reduz tudo por `chriso_merge_text` e só depois chama:

```text
chrisld_link(...)
```

sobre uma única imagem.

## Limite do linker multi-object

O próprio linker possui:

```text
LD_OBJS = 32
```

como limite de input.

Mesmo que o builder migrasse diretamente para `chrisld_link_objects`, o kernel de produção com cerca de 130 objects continuaria acima desse teto.

É necessário redesenhar tanto o limite do manifest quanto o do linker.

## Semântica do linker host

O kernel de produção é linkado por GNU ld com:

```text
kernel/metal/linker.ld
```

O script define explicitamente:

- entry `kstart`;
- base high-half `0xffffffff80000000`;
- segmento dedicado `.limine_requests`;
- `.text` alinhado;
- `.rodata`;
- `.data`;
- `.bss`;
- stack de kernel de um MiB;
- symbols `__kernel_start`, `__stack_bottom`, `__stack_top` e `__kernel_end`;
- regras de discard.

Essas propriedades fazem parte do contrato do kernel bootável.

## ChrisLd não reproduz o linker script

ChrisLd conhece as quatro classes ChrisO:

```text
TEXT
RODATA
DATA
BSS
```

e produz um segmento RX e, quando necessário, um RW.

Ele escolhe `kstart` como entry quando o symbol existe.

Mas não implementa a section dedicada de Limine nem os symbols/layout definidos pelo linker script host.

Portanto, um ELF interno pode ser estruturalmente válido e ainda assim não ser equivalente ao kernel que o Limine espera bootar.

## Preservação dos Limine requests

O linker host usa:

```text
KEEP(*(.limine_requests_start))
KEEP(*(.limine_requests))
KEEP(*(.limine_requests_end))
```

dentro de um load segment próprio.

O modelo ChrisO genérico não possui uma section correspondente.

Um kernel interno realmente bootável precisa modelar explicitamente esses requests.

Ter somente `kstart` como entry não resolve essa parte do protocolo de boot.

## Contrato da stack do kernel

O linker host reserva um MiB em BSS e define:

```text
__stack_bottom
__stack_top
```

em torno desse espaço.

São symbols produzidos pelo linker, não globals C comuns.

ChrisLd não sintetiza atualmente esse contrato.

Qualquer kernel interno que dependa desses symbols ou desse layout precisa de mecanismo equivalente.

## Limite do ELF interno

O buffer final é limitado por:

```text
CHRISLD_ELF_MAX = 1 MiB
```

O artifact inteiro precisa caber nesse espaço.

Esse limite pode servir a um bootstrap kernel reduzido, mas precisa ser medido contra o artifact completo antes de qualquer claim de equivalência.

## Ausência de validação do ELF

Depois do link, `chrisbuild_mk_kernel` grava o artifact diretamente.

Ele não chama:

```text
chrisld_validate(...)
```

apesar de o validator existir.

No mínimo, um kernel produzido internamente deveria ser rejeitado antes de write/install se a estrutura ELF não passar por essa validação.

## Stamping do kernel de produção

Depois do GNU ld, o build host executa:

```text
stamp_kernel
```

O processo procura o slot `CHRISOSHASH:`, substitui temporariamente o digest por zeros, calcula SHA-256 do kernel inteiro e grava o digest final dentro da própria imagem.

Isso cria identidade verificável do artifact.

O path interno não executa esse stamping.

## Mismatch de proveniência

Sem o mesmo processo de identity stamping, o kernel interno não segue a cadeia de proveniência usada pelo artifact de produção.

Isso é especialmente importante para um futuro gate SH5.

Antes do reboot, o sistema precisa conhecer uma identidade ligada aos bytes exatos do kernel interno para compará-la depois com o kernel que realmente iniciou.

## Semântica de falha

O builder é fail-fast.

Allocation failure, manifest ausente ou inválido, source read failure, KCC failure, merge failure, link failure ou write failure encerram o processo com erro.

Os três buffers principais são liberados no path comum de falha e também no sucesso.

Porém, a evidência é basicamente textual no serial.

Não há report estruturado indicando unsupported feature, object responsável, relocation problemática ou dependency ausente.

Um gate de self-hosting deveria persistir diagnóstico machine-readable.

## Escrita do output

Com sucesso, o builder grava os bytes no `KERNEL_OUT`, normalmente:

```text
BIN/KERNEL.ELF
```

e registra:

```text
mk: kernel ok bytes=<n>
```

Isso prova que o manifest selecionado compilou e linkou.

Não prova que o kernel de produção foi reproduzido.

## `mk clean`

`chrisbuild_mk_clean` remove:

```text
BIN/KERNEL.ELF
```

Se o file não existir, registra a condição e ainda retorna sucesso.

Não existem intermediates persistidos para limpar.

## `mk install`

O install atual lê:

```text
BIN/KERNEL.ELF
```

para memória e grava exatamente os mesmos bytes novamente no mesmo:

```text
BIN/KERNEL.ELF
```

Ele não escreve:

```text
BOOT/KERNEL.ELF
```

Não atualiza Limine.

Não valida o ELF.

Não mantém rollback.

Assim, `mk install` atualmente não promove o artifact para o boot chain.

## Boot path de produção

O disk build host copia explicitamente o kernel externo para:

```text
BOOT/KERNEL.ELF
```

junto com:

- `EFI/BOOT/BOOTX64.EFI`;
- `BOOT/LIMINE.CFG`.

Esse é o caminho real de integração de boot que o builder interno precisará assumir.

## Nível de evidência atual

O builder prova algo importante: ChrisOS consegue orquestrar KCC e ChrisLd sobre sources armazenados no próprio filesystem.

É uma arquitetura concreta de bootstrap.

Mas não estabelece SH3 completo porque:

- o limite de objects é insuficiente;
- assembly é omitido;
- generated dependencies não são modeladas;
- KCC não suporta todo o perfil de linguagem atual;
- o merge perde sections não-TEXT;
- o linker script não é reproduzido;
- stamping não existe;
- validação ELF não é executada.

## Redesign recomendado

Um kernel builder interno completo deve:

1. versionar manifest integral;
2. remover o teto de 48 objects;
3. suportar C, assembly e generated inputs;
4. produzir um ChrisO por translation unit;
5. linkar com `chrisld_link_objects` ampliado;
6. preservar todas as sections e relocations;
7. modelar Limine requests e linker symbols necessários;
8. suportar o perfil C/SSE/float real ou definir bootstrap kernel reduzido;
9. validar ELF antes de gravar;
10. aplicar artifact identity/stamp;
11. instalar atomicamente no boot path real;
12. rebootar e provar que exatamente esse artifact está executando.

## Nota de revisão

Este capítulo foi criado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. O path atual de `mk kernel` é um builder bootstrap real dentro do guest, mas não equivale ao kernel de produção de 130 objects. Limites de object count, manifest C-only, merge text-only, divergências de ABI/linker, ausência de Limine/linker-script semantics e install sem promoção real são blockers explícitos.
