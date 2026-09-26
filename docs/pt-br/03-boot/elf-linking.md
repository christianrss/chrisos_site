---
id: elf-linking
lang: pt-br
type: technical-chapter
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/elf.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.h
symbols: []
depends_on:
  - cpu-datapath-isa
related:
  - power-on-kstart
  - native-toolchain
  - processes-syscalls
---

# ELF, arquivos de objeto e linkedição do kernel

## Unidade de compilação não é executável

Compilar um arquivo C normalmente produz um objeto com machine code, dados, símbolos e relocations. Endereços de funções externas ou posições finais de seções ainda podem ser desconhecidos.

O linker combina objetos, resolve símbolos, aplica relocations e cria o layout executável.

```text
C / assembly
      │
      ▼
compiler / assembler
      │
      ▼
objetos relocáveis
      │
      ▼
    linker
      │
      ▼
      ELF
```

## Seções e segmentos

ELF distingue organização de linkedição de organização de carregamento.

**Sections** organizam text, rodata, data, BSS, símbolos e relocations para linker e ferramentas.

**Program headers/segments** dizem ao loader quais intervalos mapear e com quais propriedades.

Um linker script do kernel controla endereços de símbolos e também intenção de proteção de memória.

## Relocations

Se um objeto chama função definida em outro, o assembler pode não conhecer o displacement final. Ele emite uma relocation descrevendo o patch necessário depois do layout.

Tipos distintos representam operações diferentes: endereços absolutos, deslocamentos PC-relative, larguras limitadas e semântica específica da ISA.

Um linker que apenas concatena bytes de text sem resolver corretamente relocations não equivale a um linker completo.

## Símbolos

Símbolos nomeiam código e dados e, em formatos maduros, possuem binding, visibilidade e tipo. Linkers precisam detectar referências indefinidas e normalmente definições globais duplicadas.

O toolchain nativo do ChrisOS usa ChrisO como representação própria no caminho de self-hosting. O formato precisa evoluir até suportar os requisitos do kernel real, não apenas executáveis triviais.

## Linker script do kernel

`kernel/metal/linker.ld` é parte da arquitetura. Ele fixa modelo higher-half, entry point e segmentos de saída. Alterá-lo pode quebrar boot e memória virtual sem tocar em C.

Linker script é política arquitetural executável.

## Carregamento ELF de usuário

`kernel/metal/elf.c` implementa a operação inversa: consumir executável. Loader seguro valida antes de mapear:

- identidade ELF e arquitetura;
- limites da program-header table;
- relação file size/memory size;
- overflow de inteiros;
- política de endereços virtuais;
- sobreposição;
- validade do entry point;
- combinações writable/executable proibidas.

Depois aloca páginas, mapeia no address space, copia bytes do arquivo e zera BSS.

## W^X

Memória simultaneamente writable e executable amplia superfície de exploração. O loader pode impor W^X recusando segmentos com ambas as permissões ou construindo mappings mais restritos.

A política concreta é do sistema operacional e utiliza bits de permissão das page tables.

## ChrisLd e maturidade do bootstrap

ChrisLd existe porque self-hosting eventualmente exige controle do executável final. O marco importante não é apenas o arquivo começar com magic ELF, e sim equivalência semântica para a imagem alvo:

- todos os objetos necessários;
- símbolos resolvidos;
- relocations aplicadas;
- alinhamento correto;
- entry do kernel exato;
- estruturas exigidas pelo Limine preservadas;
- stack e BSS representados;
- permissões adequadas.

Validação do toolchain precisa comparar estrutura e comportamento, não somente assinatura do arquivo.
