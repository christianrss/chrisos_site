---
id: chriso-spec
lang: pt-br
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/tools/native_link.c
  - kernel/tools/native_link.h
symbols:
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - specifications-policy
  - object-files
  - linker
related:
  - elf-linking
  - chrisasm
  - chrisld
  - native-toolchain
---

# Formato de objeto ChrisO

## Status

ChrisO é o formato de objeto nativo usado pelo toolchain do ChrisOS entre assembly/compilation e o ELF final.

Esta especificação descreve o **ChrisO versão 2** implementado na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O reader também aceita objetos versão 1 segundo as regras de compatibilidade descritas abaixo.

ChrisO é propositalmente menor que um ELF relocatable completo. Ele contém apenas as seções, símbolos e relocations necessários ao pipeline atual ChrisAsm/ChrisLd.

## Magic e versão

As constantes são:

    CHRISO_MAGIC   = 0x4F524843
    CHRISO_VERSION = 2

Nos hosts x86-64 little-endian usados pelo projeto, o magic aparece em disco como:

    C H R O

A versão antiga é:

    CHRISO_VERSION_V1 = 1

O writer atual sempre emite versão 2.

## Endianness

O writer atual grava words de 32 bits por stores nativos de `uint32_t` e copia diretamente structs de symbol/relocation.

O ambiente-alvo do projeto é x86-64 little-endian.

Assim, o contrato prático do ChrisO v2 é **little-endian com os tamanhos de campos definidos nesta especificação**.

A implementação ainda não é um serializer endian-neutral.

Uma implementação portável futura deve codificar os inteiros explicitamente.

## Layout do arquivo

Um arquivo v2 possui:

    header de 64 bytes
    payload .text
    payload .rodata
    payload .data
    symbol table
    relocation table

BSS possui tamanho declarado, porém nenhum payload serializado.

Formalmente:

[
file_size =
64 +
text_size +
rodata_size +
data_size +
80 cdot nsym +
20 cdot nrel
]

para versão 2.

## Header

O header tem exatamente 64 bytes.

Os oito primeiros words de 32 bits são:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | magic |
| 4 | 4 | version |
| 8 | 4 | symbol count |
| 12 | 4 | relocation count |
| 16 | 4 | text size |
| 20 | 4 | rodata size |
| 24 | 4 | data size |
| 28 | 4 | BSS size |

Bytes 32 a 63 são zerados pelo writer atual e permanecem reservados.

## Identificadores de seção

ChrisO define quatro seções lógicas:

    CHRISO_SEC_TEXT   = 0
    CHRISO_SEC_RODATA = 1
    CHRISO_SEC_DATA   = 2
    CHRISO_SEC_BSS    = 3

Não existe tabela arbitrária de section names nem section-header table.

O formato é construído em torno dessas quatro classes fixas.

## Ordem dos payloads

Os bytes de payload aparecem sempre na ordem:

1. text;
2. rodata;
3. data.

BSS não ocupa bytes no arquivo.

Os offsets são derivados acumulando os tamanhos a partir do byte 64.

Seção de tamanho zero não contribui bytes.

## Limites de seção

O formato serializado usa tamanhos de 32 bits.

Entretanto ChrisAsm usa buffers estáticos de 64 KiB para text/rodata/data.

`chriso_merge_text` também rejeita crescimento de text acima de:

    65536 bytes

Portanto o limite prático do producer pode ser menor que a capacidade teórica do campo serializado.

## Symbol table

Cada símbolo v2 ocupa exatamente 80 bytes.

O source garante:

    sizeof(ChrisoSym) == 80

Layout:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 64 | name |
| 64 | 4 | section |
| 68 | 4 | offset |
| 72 | 4 | size |
| 76 | 1 | binding |
| 77 | 1 | kind |
| 78 | 2 | reserved |

O nome usa campo fixo de 64 bytes.

Producers atuais zeram o record e deixam espaço para NUL terminator.

## Limite de símbolos

O modelo possui:

    CHRISO_SYM_MAX = 256

O reader rejeita arquivo que declare mais de 256 símbolos.

Callers do writer também precisam respeitar o bound do array interno.

## Bindings

Os bindings são:

    CHRISO_BIND_LOCAL  = 0
    CHRISO_BIND_GLOBAL = 1
    CHRISO_BIND_UNDEF  = 2

`UNDEF` representa uma referência que precisa ser resolvida pelo linker.

Símbolo local definido resolve no próprio objeto.

Símbolo global participa de resolução cross-object.

## Kinds

Kinds:

    CHRISO_KIND_NOTYPE = 0
    CHRISO_KIND_FUNC   = 1
    CHRISO_KIND_OBJECT = 2

São metadata descritiva.

Não criam namespaces separados.

## Section e offset do símbolo

Para símbolo definido:

    section

identifica uma das quatro seções, e:

    offset

é relativo ao início da seção daquele objeto.

ChrisLd converte isso em endereço virtual final após empacotar os objetos.

Símbolos undefined são resolvidos por nome.

## Labels locais do assembler

ChrisAsm resolve labels same-section começando com `.L` internamente.

Eles podem ser patched antes da emissão do objeto e não precisam entrar na symbol table ChrisO.

Isso evita consumir o limite de 256 símbolos com labels temporários.

## Relocation table

Cada relocation v2 ocupa exatamente 20 bytes.

O source garante:

    sizeof(ChrisoRel) == 20

Layout:

| Offset | Tamanho | Campo |
|---:|---:|---|
| 0 | 4 | section |
| 4 | 4 | offset |
| 8 | 4 | symbol index |
| 12 | 4 | signed addend |
| 16 | 4 | relocation type |

O addend é signed 32-bit.

## Limite de relocations

O formato em memória suporta:

    CHRISO_REL_MAX = 512

O reader rejeita valor maior.

ChrisAsm também verifica esse limite.

## Tipos suportados

ChrisO reutiliza valores numéricos de alguns x86-64 ELF relocation types:

    R_X86_64_NONE  = 0
    R_X86_64_64    = 1
    R_X86_64_PC32  = 2
    R_X86_64_PLT32 = 4
    R_X86_64_32    = 10
    R_X86_64_32S   = 11

ChrisLd implementa essas formas.

Outros valores não fazem parte do contrato atual.

## Alvo de relocation

Cada record identifica:

- seção contendo o patch;
- offset dentro da seção;
- índice do símbolo;
- addend;
- tipo.

O linker rejeita symbol index fora da tabela do objeto.

Os patch sites atuais podem estar em text, rodata ou data.

BSS não possui bytes serializados para patch.

## Relocation PC-relative

Para tipos PC-relative:

[
value = S + A - P
]

onde:

- (S) é o endereço do símbolo;
- (A) é o addend;
- (P) é o endereço do patch site.

O resultado precisa caber em signed 32-bit.

ChrisAsm normalmente usa addend (-4) nos campos rel32, pois o displacement x86 é relativo ao endereço após o campo de quatro bytes.

## Relocation absoluta

Para `R_X86_64_64`, ChrisLd escreve:

[
S + A
]

em 64 bits.

Para as formas de 32 bits, aplica o range check implementado e escreve quatro bytes.

Objetos que precisem de semânticas diferentes não são atualmente linkáveis.

## Compatibilidade v1

O reader aceita versão 1.

Há duas diferenças importantes.

Primeiro, BSS é tratado como tamanho zero.

Segundo, cada relocation v1 possui:

    16 bytes

em vez de 20.

Logo não existe serialized relocation-type no record v1 lido pelo compatibility path.

O record v2 em memória é zerado antes do copy, portanto o type ausente fica:

    R_X86_64_NONE

A compatibilidade v1 é limitada e não deve ser usada para gerar novos objetos.

## Symbols v1

Symbols v1 ainda são lidos como records de 80 bytes.

Depois, o reader força:

    binding = LOCAL
    kind = NOTYPE
    reserved = 0

Isso evita interpretar metadata inexistente como se fosse semântica v2.

## Validação do reader

`chriso_read` rejeita:

- input menor que 64 bytes;
- magic incorreto;
- versão diferente de 1 ou 2;
- mais de 256 symbols;
- mais de 512 relocations;
- payload/tables truncados.

O parser calcula o tamanho mínimo completo antes de caminhar pelos records.

## Ownership do input

Ao ler seções, `chriso_read` aponta `sec[]` diretamente para dentro do buffer fornecido pelo caller.

Ele não copia text/rodata/data.

Symbols e relocations são copiados para os arrays de `ChrisoImage`.

Portanto o buffer original precisa continuar vivo enquanto os pointers de seção forem utilizados.

## Writer

`chriso_write`:

1. calcula required size;
2. verifica capacidade;
3. zera a saída;
4. grava os oito header words;
5. copia text/rodata/data;
6. copia symbols;
7. copia relocations v2;
8. retorna byte count.

O writer sempre produz v2.

## Merge helper

`chriso_merge_text` não é um linker geral.

Ele concatena apenas text do objeto source na text do destination.

Depois copia symbols e relocations ajustando:

- offsets de symbols definidos em text;
- offsets de relocations em text;
- symbol indices.

Rejeita text acima de 64 KiB e overflow das tabelas.

Outras seções não são merged por esse helper.

## Link final multi-object

`chrisld_link_objects` é mais geral.

Aceita até:

    32 objetos

Ele empacota cada seção lógica dos objetos.

Contribuições são alinhadas a 16 bytes quando necessário.

Global definitions são resolvidas por name.

Duplicate globals falham.

Undefined sem resolução falha.

## Resolução global

Símbolo local definido permanece no objeto de origem.

Para global ou undefined, o linker procura um global definido com o mesmo nome.

Mais de uma definição global é erro.

Nenhuma definição para undefined também é erro.

É um modelo simples de static linking.

Não existem weak symbols ou dynamic visibility em v2.

## ELF final

ChrisLd produz ELF64 x86-64 executable.

Text e rodata entram em segmento RX.

Quando data ou BSS existem, é criado segundo segmento RW.

BSS aumenta `memsz` do segmento RW sem ocupar file bytes.

## Seleção do entry point

ChrisLd escolhe entry na ordem:

1. primeiro símbolo definido chamado `kstart`;
2. senão primeiro símbolo definido chamado `main`;
3. senão o load address fornecido.

Essa regra pertence ao linker.

ChrisO não possui campo próprio de entry point.

## Native user linking

O linker dentro do kernel usa:

    NATIVE_USER_LOAD = 0x400000

e grava executáveis `.ELF`.

O fluxo esperado é:

    source
      -> ChrisAsm / compiler
      -> ChrisO
      -> ChrisLd
      -> ELF64 executable

ChrisO é formato intermediário, não o container runtime principal.

## Limitações do formato

ChrisO v2 não possui:

- sections arbitrárias por nome;
- section flags;
- alignment por section;
- COMDAT;
- weak binding;
- visibility;
- TLS;
- DWARF/debug sections;
- named relocation sections;
- endian marker;
- architecture field;
- checksum;
- build ID;
- string table;
- dynamic linking metadata.

São simplificações deliberadas, mas limitam interoperabilidade.

## Requisitos de estabilidade

Como arquivos ChrisO podem atravessar stages compilados independentemente, mudanças incompatíveis precisam de versionamento.

Não devem mudar silenciosamente em v2:

- header de 64 bytes;
- magic;
- section IDs;
- symbol record layout;
- relocation record layout;
- valores de binding;
- valores de kind;
- números/semântica dos relocations suportados;
- ordem dos payloads.

Mudança incompatível exige nova versão.

## Candidato a v3

Uma versão futura deve considerar:

1. encode/decode little-endian explícito;
2. architecture/ABI identifier;
3. alignment/flags por seção;
4. validação forte de symbol/section offsets;
5. undefined-section sentinel explícito;
6. checksum/content hash;
7. provenance;
8. debug records opcionais;
9. relocations independentes do layout de C struct;
10. migration strategy v2 -> v3.

## Resumo de conformidade

Um reader v2 conforme precisa compreender:

- magic `CHRO`;
- header de 64 bytes;
- IDs fixos text/rodata/data/BSS;
- BSS sem payload;
- symbol record de 80 bytes;
- relocation record de 20 bytes;
- limite de 256 symbols;
- limite de 512 relocations;
- bindings, kinds e relocation types listados.

O writer atual emite versão 2 preservando esses contratos.

## Nota de revisão

Esta especificação foi reconciliada contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

ChrisO é um formato estático compacto e específico do projeto. O maior risco de compatibilidade atual é a serialização ainda depender parcialmente da representação C little-endian nativa; isso está documentado explicitamente aqui.
