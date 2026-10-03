---
id: self-hosting-bootstrap
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/chrisbuild.h
  - kernel/tools/shell.c
  - kernel/metal/start.c
  - tools/seed_selfhost.c
  - tools/kcc_main.c
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_clean
  - chrisbuild_mk_install
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_merge_text
  - chrisld_link
depends_on:
  - native-toolchain
  - desktop-applications
related:
  - selfhost-levels
  - stage-compilers
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# Self-hosting e bootstrap

## Escopo

ChrisOS já possui um caminho real de compilação nativa dentro do guest, mas o repositório atual ainda não prova self-hosting completo.

É necessário separar três claims diferentes:

1. o kernel em execução contém compiler, assembler, object format e linker capazes de produzir ELF nativo;
2. o guest consegue tentar compilar fontes selecionados do kernel para `BIN/KERNEL.ELF`;
3. o sistema consegue reconstruir, instalar, iniciar e verificar o kernel atual completo sem depender da toolchain do host.

O source atual sustenta fortemente o primeiro claim e implementa parcialmente o segundo. O terceiro ainda não está provado.

Este capítulo trata self-hosting como problema de evidência, não como label.

## O host continua sendo a raiz do bootstrap

O build normal do repositório começa na toolchain externa.

O makefile define:

```text
CC      = gcc
LD      = ld
HOST_CC = gcc
```

Os objetos do kernel de produção são compilados por GCC no host e linkados pelo `ld` do host.

Assembly, geração de mídia e bootstrap também dependem de ferramentas externas como NASM, xorriso, Limine, Python e utilitários de filesystem.

Logo, o caminho normal de `make iso` não é self-hosted.

Ele é a raiz do bootstrap que produz o kernel dentro do qual as ferramentas nativas passam a existir.

## Componentes da toolchain nativa

O caminho emergente é:

```text
KCC
  -> assembly textual ChrisAsm
  -> imagem ChrisO
  -> ChrisLd
  -> executável ELF64
```

KCC é um compilador de subset de C.

Ele emite assembly em um buffer interno e chama `chrisasm_assemble`.

ChrisAsm produz `ChrisoImage`.

ChrisO representa sections, symbols e relocations.

ChrisLd resolve os objetos e produz ELF64 x86-64.

Esses componentes são compilados no próprio kernel e podem executar dentro do guest.

## KCC não é GCC

KCC não deve ser descrito como compilador C completo.

Ele implementa um subset próprio voltado aos padrões de código necessários pelos experimentos do ChrisOS.

O source possui limites fixos explícitos para preprocessed text, assembly, symbols, macros, structs, fields, typedefs, enums, initializers e parameters.

Os testes e diagnostics são relevantes, mas a cobertura da linguagem não equivale a GCC ou Clang.

Um source file aceito pelo GCC não é automaticamente compilável pelo KCC.

## Executável KCC de host

O makefile também cria:

```text
build/host/kcc
```

por meio de `host-kcc`.

Esse binário é compilado por `HOST_CC` a partir de:

- `tools/kcc_main.c`;
- KCC;
- ChrisAsm;
- suporte ChrisO.

Ele permite exercitar a mesma pipeline no host e produzir um artifact de bootstrap.

Esse executável não prova que KCC compilou a si próprio.

Ele continua sendo produzido por GCC.

## Testes de host da toolchain

Existem testes separados:

- `host-chrisasm-test`;
- `host-chrisld-test`;
- `host-kcc-test`;
- `host-chriso-test`.

Eles validam pontos concretos como encoding de instruções, rejeição de assembly inválido, geração ELF, relocations, layout de sections, recursos do subset de C e diagnostics.

São evidência importante porque testam os componentes antes do uso in-guest.

Não provam que o kernel inteiro já pode ser reconstruído por essa toolchain.

## O target kernel-l0

O makefile define:

```text
host-kcc-kernel-l0: host-kcc-test
```

Esse target atualmente é apenas alias do teste geral do KCC.

Existe `tools/kcc_fixtures/level0.c`, mas o próprio comentário diz explicitamente que ele não é `kernel/metal/serial.c` e representa um subset deliberadamente pequeno.

Portanto "kernel-l0" é experimento de bootstrap, não estágio de build completo do kernel.

## Comando KCC dentro do guest

O shell oferece:

```text
kcc <path>
```

Esse comando não executa `BIN/KCC.ELF`.

Ele chama diretamente a biblioteca KCC já linkada no kernel atual:

```text
kcc_compile_source(...)
```

A imagem ChrisO resultante é entregue ao native linker helper para produzir ELF.

Isso é compilação nativa real dentro do guest, mas o compiler executado faz parte de um kernel originalmente produzido pelo host.

Essa distinção de proveniência é essencial.

## Comando assembler dentro do guest

O shell também fornece:

```text
as <path>
```

para arquivos `.S` ou `.ASM`.

Ele lê source de ChrisFS, chama `chrisasm_assemble` e linka a imagem ChrisO para ELF nativo.

Nesse momento não há invocação de NASM do host.

Porém, o kernel que contém ChrisAsm ainda veio do bootstrap externo.

O estágio reduz dependência operacional do host, mas não elimina a dependência histórica do bootstrap.

## Ferramenta executada versus ferramenta autoproduzida

Há uma diferença decisiva entre executar uma ferramenta dentro do ChrisOS e provar que essa ferramenta foi produzida pelo próprio ChrisOS.

Hoje KCC, ChrisAsm e ChrisLd executam como código incorporado ao kernel. Esse kernel, porém, foi criado pela toolchain externa. Portanto a execução ocorre no guest, mas a origem binária da ferramenta continua no bootstrap do host.

Um estágio mais forte exigiria que um KCC anterior compilasse o source do próprio KCC, que o resultado fosse linkado por ChrisLd, executado no guest e usado para compilar o próximo estágio. Só então seria possível comparar stage N e stage N+1 e discutir convergência.

A mesma distinção vale para o kernel: produzir um arquivo chamado `BIN/KERNEL.ELF` não basta. É necessário demonstrar que o bootloader carregou exatamente aquele arquivo, que o kernel iniciou com identidade correspondente e que nenhum artifact host-built foi silenciosamente substituído no processo.

## Caminho `mk kernel`

O centro da tentativa de self-build é:

```text
chrisbuild_mk_kernel()
```

exposto pelo shell como:

```text
mk kernel
```

A função lê:

```text
SYS/BUILD.MK
```

em ChrisFS e interpreta um manifest simples.

Os defaults são:

```text
KERNEL_OUT = BIN/KERNEL.ELF
KERNEL_LD  = 0xffffffff80000000
```

O manifest pode listar arquivos C em `C_OBJECTS`.

## Limites do manifest

O builder aceita no máximo:

```text
BUILD_MAX_OBJ = 48
```

unidades C.

O source buffer é:

```text
BUILD_SRC_MAX = 65536
```

bytes.

O ELF final é limitado por:

```text
CHRISLD_ELF_MAX = 1 MiB
```

Esses valores são limites de implementação.

## Lista interna somente de C

O parser reconhece o início de `C_OBJECTS`.

Ao encontrar `ASM_OBJECTS=`, ele apenas encerra a coleta de C.

Não existe parsing posterior dessa lista para montar fontes Assembly.

Logo, `chrisbuild_mk_kernel` não substitui o build completo do repositório, que depende também de assembly e generated assets.

Esse ponto sozinho impede claim de self-hosting completo do kernel atual.

## Tradução de paths

Paths do manifest são convertidos para ChrisFS.

Por exemplo, um path iniciado em:

```text
kernel/
```

é mapeado sob:

```text
SYS/KERNEL/
```

com letras convertidas para maiúsculas.

O guest builder trabalha, portanto, sobre uma segunda representação da source tree copiada para ChrisFS.

Não é acesso direto ao checkout do host.

## Compilação por unidade

Para cada source C, o builder:

1. lê até 64 KiB;
2. chama `kcc_compile_source`;
3. recebe uma `ChrisoImage`;
4. faz merge no objeto combinado.

Qualquer falha aborta o build.

O serial log registra o source atual com prefixo `mk: kcc`.

## Limitação crítica: merge somente de TEXT

O merge usado é:

```text
chriso_merge_text(&merged, &unit)
```

O comportamento é mais restrito do que uma linkagem completa de objetos.

Ele concatena a section TEXT e ajusta symbols/relocations relacionadas a TEXT.

Não combina RODATA, DATA ou BSS de cada unidade na imagem final.

Além disso, o merged text buffer é limitado a 65536 bytes.

Por isso o builder atual só combina corretamente um conjunto muito restrito de unidades.

Um kernel real com globals, strings, static data, BSS e tables não pode ser presumido correto nesse caminho.

## Estágio de link

Depois do merge, o builder chama:

```text
chrisld_link(&merged, kernel_ld, ...)
```

ChrisLd em si possui suporte mais geral a TEXT, RODATA, DATA e BSS, multiple relocations, symbols e segmentos RX/RW.

Porém, `mk kernel` entrega ao linker uma única imagem que já passou pelo merge restrito a TEXT.

As capacidades mais amplas do linker não recuperam sections descartadas no estágio anterior.

## Output do kernel interno

Em caso de sucesso, o ELF é escrito para o path do manifest, normalmente:

```text
BIN/KERNEL.ELF
```

O serial registra:

```text
mk: kernel ok bytes=...
```

Isso é evidência de que determinado conjunto de fontes foi compilado e linkado.

Não é evidência de que o artifact chegou a bootar.

## `mk clean`

O comando:

```text
mk clean
```

remove:

```text
BIN/KERNEL.ELF
```

quando existe.

O lifecycle de limpeza é simples.

## `mk install` não instala no boot path

`chrisbuild_mk_install` atualmente:

1. lê `BIN/KERNEL.ELF`;
2. grava os mesmos bytes novamente em `BIN/KERNEL.ELF`;
3. imprime `mk: install ok`.

Ele não copia esse arquivo para:

```text
BOOT/KERNEL.ELF
```

nem atualiza EFI System Partition ou ISO.

Portanto, `mk install` não prova que o próximo boot usará o kernel produzido dentro do guest.

O nome é mais forte que o efeito atual.

## Artifact de boot do caminho normal

No build de disco feito pelo host, o kernel produzido externamente é copiado para:

```text
BOOT/KERNEL.ELF
```

junto com configuração Limine e EFI files.

Esse path é distinto de `BIN/KERNEL.ELF`.

Enquanto o ELF interno não for promovido de forma explícita ao boot path e verificado após reboot, o boot self-hosted continua não provado.

## Seed do workspace

O repositório oferece:

```text
make seed-selfhost
```

dependendo de:

- ISO;
- disk image;
- host KCC;
- host seed utility.

O seed monta ChrisFS e tenta copiar:

- `SYS/BUILD.MK`;
- alguns source files do kernel;
- `BIN/KCC.ELF`.

A intenção é criar o workspace de build dentro do guest.

## Dependência quebrada do seed nesta revisão

O seed tenta ler:

```text
learn/fase16-selfhost64/stubs/SYS_BUILD.MK
```

do repositório host.

Esse path não existe na árvore da revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

`put_file` trata failure de leitura como fatal.

Logo, o workflow de seed atual não pode ser considerado reproduzível a partir do checkout inspecionado.

É uma quebra concreta da cadeia de bootstrap.

## Significado de `BIN/KCC.ELF`

O seed copia:

```text
build/host/kcc
```

para:

```text
BIN/KCC.ELF
```

em ChrisFS.

Esse binário foi produzido pelo compiler do host.

Além disso, o shell `kcc` não executa esse arquivo; usa a biblioteca KCC embutida no kernel.

A simples existência de `BIN/KCC.ELF` não prova execução de compiler self-produced.

## Marker de boot

No início de `kstart`, o kernel imprime:

```text
ChrisOS selfhost=1
```

de forma incondicional.

Esse texto não testa qual compiler criou o kernel executado.

Não compara hash do kernel bootado com `BIN/KERNEL.ELF`.

Portanto, é um marker descritivo, não uma evidência de self-hosting.

## Modelo de evidência por níveis

Uma classificação útil para o ChrisOS é:

```text
SH0  KCC/ChrisAsm/ChrisLd host-built passam host tests
SH1  tools embutidas no guest compilam/linkam programas nativos
SH2  guest compila unidades reais selecionadas do kernel
SH3  guest produz kernel ELF estruturalmente completo
SH4  ELF interno é validado e promovido corretamente ao boot path
SH5  máquina reinicia exatamente nesse ELF interno
SH6  novo estágio recompila novamente e demonstra convergência definida
```

Esses nomes são critérios documentais, não claims de que todos os níveis já existem.

## Classificação atual

Na revisão inspecionada, SH0 possui evidência forte e partes significativas de SH1 existem.

Há implementação em direção a SH2 por meio de `chrisbuild_mk_kernel`, mas o manifest ausente e as limitações do builder impedem considerar o workflow completo.

SH3 e superiores não estão provados pelo source atual.

Em particular, não há path checked-in que mostre o kernel completo sendo compilado por KCC e depois bootado.

## Self-hosting versus reprodutibilidade

Self-hosting pergunta qual toolchain produz o artifact.

Reprodutibilidade pergunta se inputs equivalentes geram outputs equivalentes segundo um critério definido.

São propriedades diferentes.

Um kernel produzido por host pode ser reproducible.

Um kernel self-hosted pode não ser reproducible.

ChrisOS inclui Git revision e build date em seu build identity, portanto byte-for-byte convergence exige política específica para timestamps e metadata.

## Prova exigida para claim completo

Um gate forte deveria registrar:

1. Git revision dos sources;
2. hashes dos bootstrap binaries;
3. hash do manifest;
4. hashes/versions de KCC, ChrisAsm e ChrisLd;
5. hash do `BIN/KERNEL.ELF` interno;
6. resultado de `chrisld_validate`;
7. cópia exata para o boot target;
8. reboot;
9. runtime build identity;
10. comparação provando que o kernel em execução é exatamente o artifact interno.

Sem as etapas 7–10, "construiu um kernel ELF" não significa "está executando um kernel self-hosted".

## Próximos passos arquiteturais

As prioridades são:

1. restaurar/versionar o `SYS_BUILD.MK` ausente;
2. representar no manifest o artifact graph completo do kernel;
3. suportar assembly e generated inputs;
4. substituir merge somente de TEXT por linkagem completa de objects;
5. remover o gargalo de 64 KiB de text combinado;
6. rodar `chrisld_validate` no kernel interno;
7. fazer install copiar atomicamente para o boot target real;
8. criar reboot gate que prove o artifact em execução;
9. tornar o próprio compiler compilável por estágio KCC anterior;
10. definir critérios de convergence e reproducibility.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. A árvore atual contém infraestrutura real de compilação nativa dentro do guest, mas ainda não prova self-hosting completo do kernel. O manifest de seed ausente, parsing C-only, merge restrito a TEXT e `mk install` sem instalação no boot path são blockers explícitos da revisão inspecionada.
