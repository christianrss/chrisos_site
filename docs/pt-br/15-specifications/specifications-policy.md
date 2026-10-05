---
id: specifications-policy
lang: pt-br
type: technical-chapter
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - compiler/chrisld/chriso.h
  - compiler/clvm/clvm_format.c
  - kernel/gfx/shader/sh_pub.h
symbols:
  - cfs_super_encode
  - cfs_super_decode
  - chriso_write
  - chriso_read
  - clvm_parse
  - clvm_write_image_v2
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on: []
related:
  - validation-evidence
  - bibliography
  - chrisfs-spec
  - chriso-spec
  - clvm-spec
  - shader-spec
---

# Especificações, formatos e política de revisão

## Propósito

Especificação é um contrato explícito o suficiente para que implementations, readers, writers e tests concordem sem depender de uma única função do source.

ChrisOS possui várias interfaces próprias que funcionam como compatibility boundaries:

- estruturas on-disk do ChrisFS;
- object files ChrisO;
- images executáveis CLVM e contratos visíveis à VM;
- direct boot do ChrisVM;
- serialization de shader/CSIR;
- syscalls e resource interfaces públicas.

Este capítulo define como esses contratos devem ser escritos, versionados e alterados.

## Especificação versus implementação

Source code responde:

> O que esta revisão faz atualmente?

Specification responde:

> Qual comportamento pertence ao contrato que producers e consumers compatíveis devem preservar?

As duas respostas podem coincidir inicialmente, mas possuem papéis diferentes.

Implementation pode conter:

- optimizations;
- helper functions privadas;
- temporary internal structures;
- caching policy;
- debug counters.

Esses detalhes não devem virar compatibility requirements automaticamente.

Specification deve expor apenas o comportamento necessário para interoperabilidade.

## Comportamento de facto não é automaticamente normativo

Um reader pode observar que a implementação atual sempre grava zero em um reserved field.

Isso não significa necessariamente que futuros readers precisam rejeitar nonzero values.

Transformar todo detalhe observado em regra normativa congela escolhas acidentais.

Antes de declarar algo normativo, pergunte:

1. outro componente independentemente compilado depende disso?
2. o comportamento é serialized, transmitted ou ABI-visible?
3. mudar isso quebra artifact válido existente?
4. algum test já trata o comportamento como required?

Se não, provavelmente é implementation detail.

## Linguagem normativa

Specifications devem separar requirement de explanation.

Termos úteis:

- MUST / MUST NOT;
- SHALL / SHALL NOT;
- SHOULD / SHOULD NOT;
- MAY.

Depois o prose explica o rationale.

Exemplo:

> Reader ChrisFS MUST validar o superblock checksum antes de confiar na geometry.

A requirement é regra de compatibilidade; a explicação descreve risco de corruption.

## Superfície do contrato

Binary-format specification completa normalmente define:

- magic/signature;
- version;
- byte order;
- integer widths;
- record sizes;
- field offsets;
- alignment;
- reserved fields;
- checksums;
- validity rules;
- maximum sizes;
- error behavior;
- compatibility;
- upgrade/migration.

API/ABI specification enfatiza:

- symbol ou syscall identity;
- argument types;
- ownership;
- lifetime;
- caller/callee responsibilities;
- failure codes;
- concurrency;
- side effects;
- version compatibility.

## Estado persistido funciona como ABI

Qualquer dado escrito em disco ou trocado entre componentes independentemente construídos é externamente observável.

Exemplos:

- filesystem sectors;
- object files;
- bytecode images;
- serialized shaders;
- protocol messages.

Alterar struct C em memória é simples.

Alterar layout já persistido pode invalidar dados existentes.

Formats persistentes precisam de explicit encoding e compatibility policy.

## Não serialize native structs acidentalmente

Um padrão perigoso é escrever diretamente:

    write(fd, &native_struct, sizeof native_struct)

quando o formato não define exatamente aquela representação.

Native structs variam por:

- padding;
- alignment;
- compiler;
- endianness;
- width assumptions.

ChrisFS usa abordagem mais segura: helpers escrevem 16/32 bits explicitamente em little-endian e em offsets definidos.

O on-disk representation não depende de padding de `CfsSuper`.

## ChrisFS: encoding explícito

`cfs_super_encode()` constrói um superblock de 512 bytes.

Grava explicitamente:

- magic;
- version;
- sector size;
- geometry;
- root inode;
- clean/generation state;
- journal geometry;
- checksum.

`cfs_super_decode()` valida magic, version, sector size, checksum e constraints de geometry antes de aceitar.

Isso é implementation amigável a specification porque field positions e validation independem de layout nativo.

## Compatibilidade ChrisFS

O decoder atual reconhece a versão corrente e versões legacy/compat nomeadas.

Versões antigas são interpretadas com geometry conhecida.

A versão atual lê geometry dos serialized fields e a valida.

Regra útil:

> compatibilidade deve aparecer como reader branch explícito, não como esperança de que old layout ainda pareça com a struct nova.

Quando uma versão deixa de ser suportada, a specification deve declarar isso.

## Checksums

Checksum specification deve definir exatamente quais bytes participam.

ChrisFS calcula checksum sobre prefixo definido de records e armazena resultado em offset fixo.

"Record tem checksum" é insuficiente.

É preciso especificar:

- algorithm;
- initial value quando relevante;
- byte range;
- stored location;
- se checksum field é excluído;
- comportamento do reader em mismatch.

Checksum detecta accidental corruption; não deve ser chamado de cryptographic authenticity sem construction apropriada.

## ChrisO: object contract versionado

ChrisO declara:

    CHRISO_MAGIC
    CHRISO_VERSION = 2
    CHRISO_VERSION_V1 = 1

e possui bounded sections, symbols e relocations.

O header usa compile-time assertions para record sizes:

    sizeof(ChrisoSym) == 80
    sizeof(ChrisoRel) == 20

Isso protege a implementação contra mudança acidental de compiler/layout.

A specification normativa ainda deve declarar serialized representation diretamente, em vez de obrigar outro reader a inferir layout pelo compiler usado no ChrisLd.

## Semântica de version field

Version deve responder mais que "novo ou antigo".

Para cada versão, defina:

- reader que aceita;
- writer que emite;
- necessidade de migration;
- se conversion é lossless;
- se newer reader preserva fields desconhecidos;
- se older reader deve rejeitar.

Writer normalmente emite uma current version.

Reader pode aceitar múltiplas.

Essa assimetria é normal.

## Compatibility matrix

Documento útil pode trazer uma matriz:

| Reader | Input v1 | Input v2 | Writes |
|---|---|---|---|
| atual | suportado | suportado | v2 |
| antigo | suportado | rejeitado | v1 |

A tabela real deve refletir evidence.

O objetivo é tornar compatibilidade directional.

"Backward compatible" sem identificar direção reader/writer é ambíguo.

## CLVM: duas versões de image

O parser CLVM atual reconhece v1 e v2 explicitamente.

As versões possuem diferenças de header:

- v1 usa header menor e entry de 16 bits;
- v2 usa header expandido com entry de 32 bits e memory hint.

As duas validam:

- magic;
- known flags;
- code size;
- entry range;
- bytecode checksum.

Os writers também são explícitos: uma função emite v1 e outra v2.

É um exemplo claro de contract evolution deliberada.

## Compatibilidade não é permissividade

Parser não deve aceitar fields futuros arbitrários só para parecer compatível.

Unknown flags, sizes impossíveis e versions desconhecidas podem alterar semantics.

CLVM rejeita unknown flags e unsupported versions.

Fail-closed é melhor quando o implementation não sabe interpretar o novo contrato com segurança.

Forward compatibility precisa ser desenhada.

## Bounds fazem parte do contrato

Maximum sizes são comportamento observável quando producer pode exceder ou reader rejeita.

Exemplos:

- maximum bytecode;
- maximum symbols;
- maximum relocations;
- source size;
- resource slots.

Se bound é contract estável, documente normativamente.

Se é apenas current implementation capacity que pode crescer sem quebra de compatibilidade, marque como implementation limit.

Isso evita transformar table size temporário em ABI eterno.

## Shader: standard externo versus subset próprio

`sh_pub.h` declara explicitamente:

> ChrisOS GLSL subset. This is not a GLSL 3.30 implementation.

Essa frase representa uma regra importante.

Usar syntax familiar de standard externo não importa automaticamente o standard inteiro.

A shader specification do ChrisOS precisa definir:

- stages suportados;
- types;
- built-ins;
- qualifiers;
- resource limits;
- linking;
- IR;
- serialization.

Uma linha `#version 330` não amplia capabilities além do subset implementado/documentado.

## Internal format versus backend format

Shader stack possui source subset e IR/CSIR próprios, enquanto TGSI é backend format para VirGL.

São compatibility surfaces diferentes.

CSIR não deve ser chamado de TGSI só porque TGSI é produzido depois.

Specification precisa nomear cada boundary precisamente.

## Standards externos

ChrisOS consome standards que não controla, incluindo x86-64, ELF, UEFI, ACPI, PCIe, VirtIO, NVMe, USB e network protocols.

O projeto não deve redefini-los.

Documentação deve dizer:

1. qual external specification é authoritative;
2. qual revision/profile importa;
3. qual subset ChrisOS implementa;
4. onde há diferença/incompletude;
5. quais tests demonstram interoperabilidade.

A bibliografia mantém essas authorities.

## Conformance versus subset support

Quatro claims precisam permanecer separados:

1. format reconhecido;
2. subset implementado;
3. interoperability testada;
4. standards conformance estabelecida.

Reconhecer ELF não implica suportar todo ELF.

VirtIO funcionar em um QEMU model não prova todos transports.

Parser GLSL-like não implica GLSL conformance.

Use sempre o claim mais fraco que é precisamente verdadeiro.

## ABI stability

ABI inclui mais que binary layout.

Pode incluir:

- syscall IDs;
- calling convention;
- register usage;
- pointer width;
- error-code meanings;
- handle ownership;
- lifetime;
- alignment;
- synchronization expectations.

Alterar qualquer item pode quebrar software independentemente compilado mesmo que function name continue igual.

ABI changes precisam da mesma disciplina de disk-format changes.

## Reserved fields

Reserved fields precisam de policy explícita.

Políticas comuns:

- writer MUST gravar zero;
- reader MUST ignorar;
- reader MUST rejeitar nonzero;
- field reservado para extension nomeada.

A escolha define forward compatibility.

Sem policy, implementations divergem.

## Unknown enum values

Enums em persistent/ABI boundary precisam de política para value desconhecido.

Possibilidades:

- rejeitar;
- ignorar;
- preservar em round-trip;
- mapear para generic unknown.

A escolha depende do impacto semântico.

Nunca deixe isso depender acidentalmente do `default` de um switch.

## Migration

Format evolution pode exigir migration.

Contrato de migration deve definir:

- source versions aceitas;
- target version;
- in-place ou copy;
- rollback;
- crash behavior;
- dados não preserváveis;
- como success é verificado.

Migration vira uma compatibility surface e precisa de tests.

## Atomicidade e crash behavior

Persisted format pode precisar definir estados válidos durante update interrompido.

Filesystem journaled, por exemplo, precisa de rules para:

- transaction boundary;
- committed/uncommitted;
- recovery;
- generation;
- clean/dirty state.

Crash consistency pertence ao contract quando reader pode encontrar update parcial.

## Segurança e malformed input

Todo parser boundary também é security boundary.

Validity rules devem permitir rejeição de:

- integer overflow;
- offset overflow;
- overlapping regions;
- impossible lengths;
- invalid ownership;
- unsupported flags;
- invalid checksum;
- version mismatch.

"Undefined behavior" não deve ser resposta conveniente a serialized input malformado.

## Normative test vectors

Specification forte deveria possuir machine-readable vectors.

Casos úteis:

- menor object válido;
- object válido representativo;
- old-version object;
- rejection classes importantes;
- checksum mismatch;
- maximum boundary;
- round-trip encode/decode.

Isso permite implementations alternativas concordarem sem copiar o source original.

## Binding com implementation

Project specification deve apontar current readers/writers.

Modelo:

    specification
       |
       +-- writer
       +-- reader
       +-- validation tests

Isso torna drift visível.

Se writer muda e specification/tests não mudam, review deve perguntar se contract mudou ou apenas implementation interna.

## Git revision versus protocol version

Git revision e protocol version são eixos independentes.

Exemplo:

    Git revision R42
    implements CLVM v2

Revisão posterior pode continuar em v2 após refactoring.

Uma revisão também pode ler v1 e v2 simultaneamente.

Documentation precisa preservar as duas identidades.

## Classificação de mudanças

### Editorial

Clarifica wording sem mudar input/output válido.

### Compatible extension

Adiciona capability preservando artifacts antigos conforme regra explícita.

### Breaking change

Altera layout, interpretação, required field, ABI ou validity e pode quebrar producer/consumer antigo.

### Implementation-only

Altera code interno preservando observable contract.

Essa classificação ajuda a decidir quando version/migration muda.

## Procedimento para breaking change

Breaking persistent-format ou ABI change não deve ser casual struct edit.

Sequência disciplinada:

1. definir novo contract;
2. decidir version;
3. definir reader compatibility;
4. definir migration;
5. atualizar writer;
6. atualizar reader;
7. adicionar old/new fixtures;
8. adicionar rejection tests;
9. atualizar specification;
10. registrar limitations.

Version muda porque contract mudou, não porque houve refactor.

## Evidência da specification

Specification fica mais forte quando testada em mais de uma direção.

Evidence útil:

- writer output parseado pelo reader;
- fixture manual parseada;
- malformed fixture rejeitada;
- round-trip equality;
- old-version fixture aceita quando prometido;
- unknown-version rejeitada quando exigido;
- interoperabilidade com implementation independente.

O capítulo de validação define como reportar evidence classes.

## Política atual do projeto

Para formats próprios externamente visíveis:

- use magic/version explícitos quando aplicável;
- defina byte order e widths;
- limite variable-size data;
- valide antes de confiar em offsets/sizes;
- separe writer version de reader versions aceitas;
- rejeite unsupported semantics explicitamente;
- mantenha implementation/specification revision-bound;
- use migration em vez de reinterpretar silentemente old data;
- diferencie implementation limit de normative limit.

## Checklist de review

Antes de alterar format/ABI:

1. O state é persistido ou consumido independentemente?
2. Reader de outra revisão precisa entender?
3. Byte order está explícito?
4. Size/offset arithmetic pode overflow?
5. Version behavior está definido?
6. Unknown flags/values têm policy?
7. Writer emite qual versão?
8. Migration é necessária?
9. Existem old fixtures?
10. Tests cobrem rejection/compatibility?
11. Specification precisa mudar?
12. Roadmap está separado do current contract?

## Nota de revisão

Esta política foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O source atual mostra contracts versionados explícitos em ChrisFS, ChrisO e CLVM, enquanto shader API restringe deliberadamente o claim de linguagem externa. A direção do projeto é clara: compatibilidade deve ser codificada e testada de forma deliberada, nunca inferida de C layout acidental ou de terminologia familiar de standards externos.
