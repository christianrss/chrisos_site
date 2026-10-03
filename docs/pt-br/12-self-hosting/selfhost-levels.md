---
id: selfhost-levels
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/shell.c
  - kernel/metal/start.c
  - tools/seed_selfhost.c
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_install
  - kcc_compile_source
  - chrisasm_assemble
  - chrisld_link
  - chrisld_validate
depends_on:
  - self-hosting-bootstrap
related:
  - stage-compilers
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# Modelo de evidência self-host SH0-SH6

## Objetivo

"Self-hosted" é amplo demais para funcionar como label binário.

ChrisOS já possui infraestrutura suficiente de toolchain nativa para que várias frases pareçam equivalentes mesmo descrevendo milestones muito diferentes.

Por exemplo:

- uma biblioteca de compiler roda dentro do guest;
- esse compiler consegue compilar um programa nativo;
- consegue compilar alguns files reais do kernel;
- consegue produzir um kernel ELF completo;
- esse ELF passa a ser o próximo boot artifact;
- o kernel bootado consegue recompilar compiler e kernel novamente.

Esses estados não são equivalentes.

O modelo SH0-SH6 define uma escada monotônica de evidência para que a documentação declare exatamente o que foi provado.

## Princípio de evidência

Um nível só é atingido quando existem artifact e evidência de execução correspondentes.

Source code que parece capaz de realizar um passo é evidência mais fraca que um gate repetível que realmente executa o passo.

Um log string é mais fraco que um hash associado ao artifact produzido.

Um ELF produzido é mais fraco que a prova de que a máquina bootou exatamente aquele ELF.

Cada nível exige, portanto:

1. inputs declarados;
2. toolchain produtora;
3. artifact;
4. validação do artifact;
5. quando aplicável, evidência de execução;
6. proveniência ligando o estágio anterior ao próximo.

## Evidência histórica versus reproduzível

O projeto deve separar "esse nível já foi atingido uma vez" de "esse nível é reproduzível a partir da revisão atual".

Um log antigo, screenshot ou artifact salvo pode provar que um evento ocorreu, mas não prova que o checkout presente consegue repetir o mesmo resultado.

Para status atual, um nível só deve ser marcado como reproduzível quando todos os sources, manifests, ferramentas, scripts e gates necessários existem na revisão inspecionada e não dependem de arquivos locais ocultos.

Essa distinção é especialmente importante porque o seed atual referencia um manifest ausente da árvore.

## Regra de transição

Promover de SHn para SHn+1 exige nova evidência que feche exatamente a diferença entre os níveis.

Mais testes no mesmo nível fortalecem aquele nível, mas não promovem automaticamente o sistema.

Adicionar mais testes de linguagem ao KCC fortalece SH0, mas não prova SH1 até o compiler executar no guest.

Da mesma forma, compilar mais objetos parciais do kernel em SH2 não produz SH3 até que o artifact graph exigido esteja completo.

A documentação deve registrar tanto a amplitude da evidência dentro do nível quanto o critério explícito de transição para o próximo.

## Monotonicidade

Níveis superiores incluem requisitos dos anteriores.

Se SH4 tiver sido atingido no passado, mas um input indispensável de bootstrap desaparecer do repositório, a reproduzibilidade atual do claim fica quebrada.

O projeto deve registrar separadamente:

- achievement histórico;
- reproduzibilidade na revisão corrente.

Este capítulo classifica apenas a revisão inspecionada.

## SH0 — toolchain nativa host-built validada

SH0 significa que os componentes da toolchain própria do ChrisOS existem em source e suas formas compiladas pelo host passam testes dedicados.

Os componentes centrais são:

- KCC;
- ChrisAsm;
- ChrisO;
- ChrisLd.

GCC ainda pode ser o compiler produtor.

O objetivo não é self-hosting ainda.

O objetivo é provar que a lógica própria de compiler/linker funciona o bastante para se tornar um estágio do bootstrap.

## Evidência SH0

O repositório possui:

```text
host-chrisasm-test
host-chrisld-test
host-kcc-test
host-chriso-test
```

Os tests executam código real da implementação.

KCC tests compilam construções suportadas.

ChrisAsm tests validam encoding e rejection behavior.

ChrisLd tests cobrem ELF, sections, symbols e relocations.

ChrisO tests validam o object representation próprio.

Isso é evidência válida de SH0.

## O que SH0 não prova

SH0 não significa que:

- KCC compilou a si mesmo;
- ChrisOS construiu o kernel atualmente executado;
- GCC foi removido do bootstrap;
- guest já consegue bootar um kernel interno.

A toolchain própria ainda pode ter sido produzida inteiramente pelo host.

## SH1 — tools nativas executam dentro do ChrisOS

SH1 exige que a lógica da toolchain execute dentro do guest e produza artifacts nativos úteis sem invocar processos de compiler do host durante a operação.

O shell atual oferece:

```text
kcc <source>
as <source>
```

As implementações chamam KCC e ChrisAsm já linkados no kernel.

Depois usam ChrisLd através do native linker helper para gerar ELF.

Isso é compilação/assembly genuína dentro do guest.

## Limitação de proveniência em SH1

O código que roda no guest foi incorporado em um kernel originalmente produzido por GCC.

SH1 demonstra independência operacional da compilação naquele momento, não independência da origem binária do compiler.

Essa diferença é essencial.

Compiler executando no ChrisOS não significa compiler produzido pelo ChrisOS.

## Evidência de aceitação para SH1

Um gate forte deveria:

1. bootar imagem conhecida;
2. criar/carregar source C em ChrisFS;
3. executar `kcc`;
4. produzir ELF;
5. validar ELF;
6. executar o resultado;
7. verificar output determinístico.

O mesmo deve existir para ChrisAsm.

O source suporta essa arquitetura, mas o gate end-to-end precisa ser formalizado.

## SH2 — unidades reais do kernel compilam no guest

SH2 sai de fixtures e programas simples.

Ele exige KCC executando no guest sobre source files reais da árvore do kernel.

`chrisbuild_mk_kernel` aponta para esse estágio.

A função lê `SYS/BUILD.MK`, resolve paths em `SYS/KERNEL` e chama `kcc_compile_source` para cada unidade listada.

É a direção correta para SH2.

## Artifact de SH2

O output normal é:

```text
BIN/KERNEL.ELF
```

Mas o nome do artifact não prova que ele contém o kernel inteiro.

Em SH2 o ELF pode representar apenas um subconjunto.

A evidência precisa declarar exatamente quais source files reais participaram.

## Blocker atual de SH2

O seed utility espera:

```text
learn/fase16-selfhost64/stubs/SYS_BUILD.MK
```

porém esse path não existe na revisão inspecionada.

Assim, a árvore atual não contém todo o input declarado necessário para reproduzir o workflow seeded pretendido.

O builder existe, mas o gate SH2 reproduzível está incompleto.

## Cobertura de compiler em SH2

Um report correto deve listar por source:

- compilou;
- feature de linguagem não suportada;
- external não resolvido;
- problema de section/link;
- runtime gate quando aplicável.

"Suporta bastante do kernel" não é critério mensurável sem lista versionada.

Hash do manifest faz parte de uma evidência forte.

## SH3 — kernel ELF estruturalmente completo é produzido internamente

SH3 exige que a toolchain no guest produza um kernel ELF que represente todo o artifact graph necessário.

Isso é muito mais forte que compilar alguns files.

O build precisa incluir:

- todas as unidades C necessárias;
- assembly;
- generated sources/assets;
- symbols;
- TEXT/RODATA/DATA/BSS;
- relocations;
- link address;
- entry point válido.

## Blockers atuais de SH3

O builder possui vários blockers.

Primeiro, o parser coleta somente `C_OBJECTS`.

Ao encontrar `ASM_OBJECTS=`, ele interrompe a coleta de C, mas não processa a lista de assembly.

Segundo, usa:

```text
chriso_merge_text
```

que combina TEXT, mas não agrega integralmente RODATA/DATA/BSS de cada unidade.

Terceiro, o text buffer combinado é limitado a 65536 bytes.

Por isso `mk kernel` não pode ser tratado como build completo do kernel contemporâneo.

## Validação SH3

Um ELF de SH3 deve passar `chrisld_validate`.

O validator checa propriedades estruturais importantes:

- identidade ELF64 little-endian;
- machine x86-64;
- program headers;
- filesz <= memsz;
- ausência de segment W+X;
- load segments sem overlap;
- entry point dentro de memória executável.

Um gate futuro deve tornar essa validação obrigatória.

## SH4 — kernel interno é instalado como boot artifact

SH4 exige promoção de "existe um kernel file" para "o próximo boot path contém exatamente esse file".

A diferença entre:

```text
BIN/KERNEL.ELF
```

e:

```text
BOOT/KERNEL.ELF
```

é central.

O host-side build popula `BOOT/KERNEL.ELF`.

O internal builder escreve `BIN/KERNEL.ELF`.

## Blocker atual de SH4

`chrisbuild_mk_install` não copia o ELF interno para o boot path.

Ele lê `BIN/KERNEL.ELF` e grava novamente no mesmo path.

Não substitui boot artifact nem atualiza configuração do bootloader.

Logo, `mk install` não estabelece SH4.

## Atomicidade de SH4

Install robusto deve evitar destruir o único kernel bootável.

Um caminho melhor:

1. validar ELF novo;
2. escrever boot artifact temporário;
3. sincronizar storage;
4. trocar de forma atômica;
5. manter rollback;
6. registrar o hash esperado para o próximo boot.

Assim install vira state transition controlada.

## SH5 — reboot prova o kernel interno em execução

SH5 é o primeiro nível em que a frase "o kernel ChrisOS em execução foi construído pelo próprio sistema" se torna defensável.

A máquina precisa rebootar após SH4 e provar que o running image é exatamente o artifact interno produzido.

Um string fixo como:

```text
ChrisOS selfhost=1
```

não basta.

Hoje ele é impresso de forma incondicional.

## Evidência de identidade SH5

A prova forte deve usar um identificador conhecido antes do reboot.

Exemplos:

- SHA-256 completo do artifact;
- hash do build manifest;
- source revision + stage ID;
- build record estruturado.

Depois do reboot, o kernel deve reportar essa identidade.

O gate compara runtime identity com o artifact interno anterior ao reboot.

## Controles negativos SH5

Também é necessário provar que um kernel host-built não foi restaurado silenciosamente.

Controles úteis:

- remover/renomear boot alternatives;
- conferir hash do boot path antes do reboot;
- inserir nonce/build ID gerado internamente;
- falhar se a identidade após boot ainda for a do bootstrap kernel.

Sem isso, reboot bem-sucedido pode apenas provar que algum kernel bootou.

## SH6 — convergência entre estágios

SH6 é o nível de convergência de compiler/bootstrap.

O sistema self-built precisa produzir um estágio seguinte segundo regra de equivalência declarada.

Modelo:

```text
host bootstrap
    -> stage A
    -> stage B produzido por A
    -> stage C produzido por B
```

Depois B e C são comparados.

## Igualdade de bytes versus convergência semântica

ChrisOS inclui Git revision e build date na identidade normal.

Por isso igualdade byte-a-byte não pode ser presumida enquanto metadata não determinística não for normalizada.

SH6 precisa declarar a regra:

- bytes idênticos após deterministic-build fixes;
- loadable sections idênticas;
- compiler output idêntico em corpus;
- execução equivalente nos gates definidos.

O alvo mais forte no longo prazo é byte identity para inputs controlados.

## Compiler produzindo compiler

Uma história completa de SH6 deve incluir o próprio KCC.

Não basta KCC construir o kernel enquanto KCC sempre nasce de GCC.

Uma cadeia mais forte é:

```text
GCC -> KCC0
KCC0 -> KCC1
KCC1 -> KCC2
comparar KCC1/KCC2
```

Depois KCC1 ou KCC2 constrói o kernel.

A revisão atual não fornece evidência de que essa cadeia foi concluída.

## Classificação da revisão atual

A classificação conservadora é:

```text
SH0  suportado por host tests diretos
SH1  implementação real existe no guest
SH2  implementação parcial; seed reproduzível está quebrado
SH3  não estabelecido
SH4  não estabelecido
SH5  não estabelecido
SH6  não estabelecido
```

A classificação é intencionalmente mais rigorosa que linguagem promocional.

Ela depende de proveniência e transição de artifacts.

## Por que a classificação estrita importa

Claims de self-hosting são fáceis de inflar sem intenção.

Exemplos:

- compiler source embutido no kernel não é self-compilation;
- produzir ELF não é bootá-lo;
- imprimir "selfhost=1" não é proveniência;
- copiar compiler host-built para ChrisFS não é self-production;
- compilar fixture não é compilar kernel atual;
- bootar uma vez não é reprodutibilidade.

A escada SH impede essas confusões.

## Registro obrigatório de evidência

Cada milestone deve preservar:

```text
source revision
bootstrap tool hashes
input manifest hash
tool versions/hashes
comando ou gate
artifact hash
resultado de validação
runtime result
logs
data/ambiente
```

Em SH4+, hashes do boot path são obrigatórios.

Em SH5+, runtime identity após reboot é obrigatória.

Em SH6, critério e resultado da comparação entre stages são obrigatórios.

## Semântica de falha

Falhar em nível superior não invalida automaticamente o inferior.

Se install falhar depois de um ELF interno válido, SH3 pode continuar provado enquanto SH4 falha.

Se stages forem não determinísticos, SH5 pode permanecer válido e SH6 continuar aberto.

Separar níveis melhora diagnóstico e reporting.

## Gates automatizados recomendados

O repositório deve evoluir para targets explícitos como:

```text
selfhost-sh0
selfhost-sh1
selfhost-sh2
selfhost-sh3
selfhost-sh4
selfhost-sh5
selfhost-sh6
```

Cada gate depende do anterior e emite resultado machine-readable.

O comportamento deve ser fail-closed: manifest ausente, validação pulada, artifact inexistente ou identity mismatch precisam falhar, não gerar warning.

## Nota de revisão

Este modelo foi escrito contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele separa a infraestrutura guest-native que realmente existe do claim ainda não provado de self-hosting completo e define critérios concretos para futuras promoções de SH0 até SH6.
