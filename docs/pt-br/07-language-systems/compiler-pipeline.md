---
id: compiler-pipeline
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - cpu-datapath-isa
  - elf-linking
related:
  - chrisc-clvm
  - native-toolchain
---

# Construção de compiladores: do texto à semântica executável

## Estágios

Compilador transforma uma linguagem formal em outra preservando o significado definido.

<figure class="figure">
<img src="../../assets/diagrams/compiler.svg" alt="Estágios de compilação">
<figcaption>Decomposição comum; compiladores concretos podem combinar estágios.</figcaption>
</figure>

## Lexer

Converte caracteres em tokens: identificadores, keywords, literais, operadores e pontuação. Posição de fonte permite diagnostics.

Lexer responde "qual token é este texto?", não se a expressão é semanticamente válida.

## Parser

Verifica gramática e produz árvore ou representação equivalente. Precedência precisa distinguir `a + b * c` de `(a + b) * c`.

## Semântica

Programa sintaticamente válido ainda pode ter símbolo indefinido, tipos incompatíveis, argumentos errados, lvalue inválido ou definições duplicadas.

Semantic analysis utiliza symbol tables, scopes e sistema de tipos.

## IR

Intermediate representation separa sintaxe fonte de machine code. Facilita verificação, otimização e múltiplos backends.

## Codegen

Geração precisa obedecer ISA e ABI: encoding, registradores, stack frame, calling convention, data layout e relocations. Bytes decodificáveis não bastam; devem preservar semântica.

## Objetos e linker

Objetos relocáveis permitem separate compilation. Linker resolve símbolos e endereços finais.

## Diagnostics

Compilador que ignora sintaxe desconhecida silenciosamente é perigoso. Sucesso precisa significar que o subset aceito foi realmente traduzido. Localização, severidade e mensagem fazem parte do contrato.

## Bootstrap

Self-hosting cria linhagem entre compiladores. Prova exige validar artifacts e comportamento entre estágios; não basta o compilador ser escrito na própria linguagem.

## Dois caminhos no ChrisOS

ChrisOS possui ChrisC → CLVM para aplicações e KCC/ChrisAsm/ChrisO/ChrisLd para código nativo/kernel. São pipelines diferentes e os capítulos seguintes os tratam separadamente.
