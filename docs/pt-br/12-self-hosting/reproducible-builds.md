---
id: reproducible-builds
lang: pt-br
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - kernel/metal/buildid.c
  - kernel/metal/buildid.h
  - tools/buildstamp.c
  - tools/stamp_kernel.c
  - tools/test_buildstamp.c
  - tools/test_buildinfo.c
  - tools/cfs_mkdisk.c
  - kernel/fs/cfs.c
  - scripts/check-dev-env.sh
  - tests/cc-fixed.sh
  - .cursor/install.sh
symbols:
  - build_git
  - build_id
  - build_date
  - build_compiler
  - build_kernel_sha256
  - buildstamp_seal
  - cfs_set_now
depends_on:
  - stage-compilers
  - internal-kernel-build
related:
  - selfhost-levels
  - validation-evidence
---

# Builds reproduzíveis e proveniência

## Escopo

Build reproduzível não é sinônimo de build bem-sucedido, self-hosted ou com checksum.

No ChrisOS, reprodutibilidade precisa ser tratada por artifact:

- kernel ELF;
- ISO bootável;
- imagem ChrisFS;
- estágios de compiler;
- binaries gerados de aplicações.

O repositório já possui mecanismos úteis de proveniência, especialmente metadata derivada do Git e um hash gravado dentro do kernel. Também existe pelo menos um teste real de fixed point para compiler.

Porém, o build x86-64 atual de kernel e ISO ainda não está configurado para reprodutibilidade byte-a-byte entre horários ou ambientes host independentes.

Os blockers principais são explícitos no source.

## Reprodutibilidade, proveniência e integridade

Reprodutibilidade pergunta:

> Com os mesmos inputs declarados, builds independentes geram output equivalente?

Proveniência pergunta:

> Qual source revision, toolchain, dependencies e condições de build produziram o artifact?

Integridade pergunta:

> Este artifact específico mudou depois de produzido?

São propriedades diferentes.

ChrisOS já possui mecanismo útil de integridade para kernel, mas o registro de proveniência ainda é incompleto e o build default incorpora metadata dependente do tempo.

## Revisão do source no kernel

O makefile define:

```text
CHRIS_GIT := git rev-parse --short=12 HEAD
```

e compila esse valor como:

```text
CHRIS_GIT
```

Isso fornece ao kernel em execução um identificador compacto do commit.

É útil, mas não representa toda a identidade do source state.

## Limite do SHA curto

Somente doze caracteres hexadecimais de HEAD são incorporados.

Isso normalmente é suficiente para identificação humana dentro de um único repositório, mas é mais fraco que armazenar o commit completo em um provenance record.

Um manifest de reprodutibilidade deve preservar o SHA completo.

O identificador curto pode continuar sendo usado na UI e logs.

## Limite do working tree dirty

O build ID não registra se existem mudanças locais não commitadas.

`git rev-parse HEAD` identifica o commit pai, não os bytes efetivamente entregues ao compiler.

Assim, dois kernels podem exibir a mesma revisão Git mesmo que um deles tenha sido compilado a partir de source modificado localmente.

O kernel stamp diferencia binaries distintos, mas não explica de quais alterações de source vieram essas diferenças.

Um gate forte precisa rejeitar working tree dirty ou hash-ear os inputs efetivos.

## Build time é incorporado

O makefile define:

```text
CHRIS_DATE := date -u +%Y-%m-%dT%H:%M:%SZ
```

e:

```text
CHRIS_BUILD_ID = CHRIS_GIT-CHRIS_DATE
```

A data e o build ID são compilados dentro do kernel.

Consequentemente, dois clean builds do mesmo commit em segundos UTC diferentes recebem macros diferentes e geram bytes diferentes.

Só isso já impede reprodutibilidade byte-a-byte no modo default.

## Ausência de SOURCE_DATE_EPOCH

O repositório não utiliza atualmente:

```text
SOURCE_DATE_EPOCH
```

nem mecanismo equivalente de timestamp normalizado.

Um modo reproduzível deveria obter toda metadata temporal a partir de um input determinístico, como commit timestamp ou environment variable explícita.

O horário real da máquina pode continuar sendo registrado fora do artifact, mas não deve alterar os bytes quando o modo determinístico está ativo.

## Build info em runtime

`buildid.c` expõe:

- revisão Git;
- build ID;
- build date;
- compiler version;
- kernel SHA-256 stamp.

`build_info_format` formata esses fields para inspeção.

Isso é útil para provenance visibility.

Também significa que `__VERSION__` do compiler entra no binary, portanto mudar compiler version pode alterar os bytes mesmo quando a lógica gerada fosse equivalente.

## Cobertura das versões de toolchain

O ambiente requer:

- GCC;
- GNU ld/binutils;
- NASM;
- xorriso;
- Python;
- Git.

O checker de ambiente valida presença, não versões hermeticamente exatas.

O build info registra `__VERSION__` do compiler, mas não registra:

- versão do GNU ld;
- versão do NASM;
- versão do xorriso;
- versão do Python.

Releases diferentes dessas tools podem gerar bytes diferentes com source e flags iguais.

Um relatório reproduzível precisa de fingerprint de toolchain completo.

## Compiler escolhido no bootstrap de cloud

O script de instalação de cloud escolhe GCC 11 quando disponível, porque o próprio projeto documenta interação problemática de warnings/errors com GCC mais novo.

Isso já demonstra que compiler version é parte material do ambiente.

Mesmo assim, instalar um package por nome de distribuição não equivale a fixar hermeticamente o binary do compiler.

Um setup mais forte deveria registrar hashes ou uma image/container identity para a toolchain inteira.

## Dependências third-party fixadas

O script de bootstrap possui commit SHAs explícitos para dependencies como Limine e doomgeneric.

Isso é boa prática de proveniência.

Limine, por exemplo, é associado a um commit específico em vez de depender somente de branch móvel.

## Gap de verificação das dependencies

O script busca os commits pinados apenas quando o path correspondente ainda não existe.

Se a directory já estiver presente, ele registra "already present" em vez de verificar se o checkout atual ainda corresponde ao SHA declarado.

Logo, o pin documenta a origem pretendida, mas não a garante em toda execução.

Um gate reproduzível deve verificar os revisions mesmo quando a dependency já existe.

## Mecanismo de kernel stamp

Depois do GNU ld gerar o kernel, o makefile executa:

```text
stamp_kernel
```

O kernel contém:

```text
CHRISOSHASH:
```

seguido por 64 caracteres hexadecimais inicialmente zero.

`buildstamp_seal` encontra esse slot, zera os 64 caracteres, calcula SHA-256 sobre a imagem inteira nesse estado e grava o digest hexadecimal de volta.

## O que o stamp prova

O stamp cria uma identidade determinística para o linked image quando o próprio campo de digest está zerado.

Em runtime:

```text
build_kernel_sha256()
```

retorna esse digest embutido.

Isso permite que logs, panic reports e ferramentas identifiquem exatamente qual kernel estampado está rodando.

É um mecanismo forte de artifact identity.

## O stamp não é o SHA-256 convencional do arquivo final

O valor embutido não é simplesmente:

```text
sha256sum final-kernel.elf
```

porque o digest é calculado enquanto o próprio campo contém zeros.

Depois que o hash é gravado, os bytes finais do arquivo mudam.

Portanto, verificação externa precisa repetir o algoritmo "zerar slot e hash-ear" ou o projeto precisa publicar adicionalmente o SHA-256 convencional do arquivo final.

Essa distinção deve ser explícita em tooling de proveniência.

## Testes do stamp

`tools/test_buildstamp.c` verifica que:

- o digest correto é gravado;
- bytes fora do slot permanecem intactos;
- imagens sem a marker são rejeitadas.

`tools/test_buildinfo.c` verifica os campos de build info e o tamanho de 64 caracteres da identidade.

Esses testes validam o mecanismo.

Não validam que dois builds independentes do kernel geram bytes idênticos.

## Gate de kernel reproduzível ausente

Hoje não há um gate equivalente a:

```text
clean build A
clean build B
compare kernel A and kernel B
```

Não existe modo dedicado com `SOURCE_DATE_EPOCH`, nem teste versionado que faça `cmp`, compare SHA-256 convencionais ou preserve um binary diff entre dois kernels independentemente produzidos.

Logo, a reprodutibilidade byte-a-byte do kernel não está estabelecida.

## Precedente de fixed point existente

O repositório possui um teste importante:

```text
tests/cc-fixed.sh
```

Ele cria estágios do compiler ChrisC de aplicação:

```text
CC1.CLV
CC2.CLV
CC3.CLV
```

e executa:

```text
cmp build/CC2.CLV build/CC3.CLV
```

Isso é evidência real de fixed point byte-a-byte para aquele caminho específico.

Não prova reprodutibilidade de KCC ou kernel, mas oferece um padrão concreto para os gates futuros.

## Gate de kernel inspirado no fixed point

Um teste equivalente para kernel deveria:

1. começar de source state limpo e exato;
2. usar toolchain declarada;
3. aplicar timestamp normalizado;
4. construir kernel A;
5. remover todos os outputs derivados;
6. construir kernel B;
7. comparar hashes convencionais;
8. se diferentes, preservar artifacts e relatório de diferença.

Depois, um segundo ambiente CI pode repetir o processo para separar determinismo no mesmo host de reprodutibilidade entre ambientes.

## Reprodutibilidade da ISO

A ISO é criada por xorriso e depois modificada por:

```text
limine bios-install
```

A invocação atual do xorriso não define uma política de timestamp normalizado no repositório, como SOURCE_DATE_EPOCH ou ISO date fields fixos.

Portanto, mesmo que kernel se torne determinístico, a ISO precisa de um gate independente.

Hash igual do kernel não implica hash igual da ISO.

## Inputs da ISO

A staging tree inclui:

- kernel ELF;
- configuração Limine;
- Limine BIOS files;
- Limine UEFI image.

Para reproduzir a ISO, tanto o conteúdo quanto metadata/layout gerados pela toolchain de filesystem óptico precisam ser determinísticos.

Esse boundary é diferente do kernel.

## Pós-processamento Limine

`limine bios-install` modifica a ISO depois de xorriso.

Essa mutação faz parte do artifact pipeline e precisa ser incluída no boundary de reprodutibilidade.

O hash final da ISO deve ser calculado depois desse passo.

Versão/tool binary do Limine também faz parte da provenance da ISO.

## Imagem ChrisFS

`cfs_mkdisk` começa criando um arquivo novo de tamanho fixo, inicialmente zerado, e formata CFS.

CFS não depende automaticamente do wall clock host para seu relógio normal de metadata.

O global clock começa em:

```text
1
```

e cada inode stamp incrementa esse valor, a menos que `cfs_set_now` seja usado explicitamente.

Isso remove uma fonte comum de não determinismo baseada no relógio durante uma formatação nova.

## Comportamento persistente de disk.img

O target normal não recria `build/disk.img` quando o arquivo já existe.

Ele informa que a imagem existe e recomenda removê-la manualmente para recriar.

Diversos targets de apps, smoke tests e seed depois modificam essa imagem copiando files.

Logo, `disk.img` funciona normalmente como workspace state persistente, não como artifact reproduzível.

Seus bytes podem refletir ações de desenvolvimento anteriores.

## Duas classes de disk image

A documentação deve separar:

```text
workspace disk
reference/release disk
```

A workspace image é propositalmente mutável e persistente.

Uma reference image reproduzível deveria sempre começar de arquivo novo zerado e receber files em ordem fixa a partir de manifest declarado.

Esses dois casos não devem compartilhar o mesmo claim.

## Ordem de sources e objects

O makefile define uma lista ordenada de objects e entrega essa ordem ao GNU ld.

Isso fornece um input ordering estável.

Porém, ordem fixa não resolve:

- build date variável;
- working tree dirty;
- drift de compiler/binutils;
- generated inputs diferentes;
- third-party checkouts incorretos.

Reprodutibilidade é propriedade end-to-end.

## Níveis de reprodutibilidade

Uma classificação útil para o ChrisOS é:

```text
R0  artifact possui identidade/hash
R1  rebuild no mesmo ambiente é byte-identical
R2  ambiente independente com tools pinadas produz bytes iguais
R3  builders independentes reproduzem artifact publicado
R4  chain self-hosted/staged também converge
```

O kernel atual possui evidência mais forte em R0.

O fixed-point de ChrisC demonstra uma propriedade especializada semelhante a R1/R4 para aquele compiler artifact, não para o kernel.

## Manifest de proveniência necessário

Um release-quality manifest deveria registrar:

- full Git commit;
- dirty-tree state ou source-tree hash;
- normalized build timestamp;
- GCC version e binary hash;
- GNU ld version;
- NASM version;
- xorriso version;
- Python version;
- Limine commit;
- outros third-party commits;
- build flags;
- hashes de generated inputs;
- SHA-256 convencional do kernel final;
- embedded zero-slot kernel stamp;
- SHA-256 final da ISO;
- SHA-256 da reference disk quando houver.

Assim, uma diferença pode ser explicada e não apenas detectada.

## Critério mínimo para um release reproduzível

Um release só deveria receber claim de reprodutibilidade quando pelo menos dois builders começarem do mesmo source manifest completo, usarem a toolchain declarada, produzirem kernel e ISO a partir de workspace limpo e chegarem aos mesmos hashes definidos pelo projeto.

O relatório deve preservar os manifests dos dois builders e não apenas o resultado "pass".

Se o kernel for igual, mas a ISO divergir, o status precisa indicar claramente que a reprodutibilidade foi atingida apenas no nível do kernel.

## Caminho de engenharia imediato

O caminho mais curto é:

1. adicionar deterministic-build mode;
2. substituir wall-clock `CHRIS_DATE` por input normalizado nesse modo;
3. registrar full Git SHA e rejeitar ou registrar dirty tree;
4. fixar e verificar toolchain host completa;
5. verificar third-party revisions mesmo quando já presentes;
6. executar dois clean builds e compará-los;
7. registrar final-file hash convencional além do embedded stamp;
8. criar gate separado para ISO;
9. criar manifest/gate para reference disk nova;
10. aplicar o mesmo processo a KCC1/KCC2.

## Nota de revisão

Este capítulo foi criado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. ChrisOS já possui artifact identity forte para kernel e um fixed-point test byte-a-byte real para o compiler ChrisC de aplicação. O kernel default não é byte-reproduzível entre horários diferentes porque incorpora UTC atual, e a provenance completa entre ambientes ainda não está totalmente pinada nem verificada.
