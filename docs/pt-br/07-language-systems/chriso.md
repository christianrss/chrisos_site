---
id: chriso
lang: pt-br
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - tools/test_chriso.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
symbols:
  - ChrisoSym
  - ChrisoRel
  - ChrisoImage
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
depends_on:
  - native-toolchain
  - data-representation-layout
  - elf-linking
related:
  - chrisasm
  - chrisld
  - kcc
  - chriso-spec
---

# Formato de objeto ChrisO

## Escopo

ChrisO é a representação compacta de objeto usada entre ChrisAsm/KCC e ChrisLd.

Ela carrega a informação mínima necessária ao toolchain nativo atual:

- bytes de text;
- bytes de dados somente leitura;
- bytes de dados graváveis;
- tamanho de BSS;
- símbolos;
- relocations.

ChrisO não é o formato de objeto relocável ELF e não tenta reproduzir todos os recursos de ELF64 ET_REL. É um contrato intermediário específico do projeto, mais simples de construir dentro do ChrisOS e mais simples para o ChrisLd consumir.

O objeto possui uma representação em memória, ChrisoImage, e uma representação serializada escrita por chriso_write e lida por chriso_read.

## Constantes e versões

As constantes atuais são:

| Constante | Valor |
| --- | ---: |
| CHRISO_MAGIC | 0x4F524843 |
| versão atual | 2 |
| versão legada aceita | 1 |
| seções | 4 |
| máximo de símbolos | 256 |
| máximo de relocations | 512 |

A versão 2 adiciona tamanho explícito de BSS no cabeçalho e usa registro de relocation de 20 bytes contendo o tipo da relocation.

A versão 1 continua legível por compatibilidade. Ao ler objeto versão 1, o tamanho de BSS é tratado como zero e registros legados de símbolo são normalizados para semântica local/notype.

O writer sempre produz a versão atual.

## Imagem em memória

ChrisoImage contém conceitualmente:

    uint8_t *sec[4]
    uint32_t sec_size[4]
    ChrisoSym sym[256]
    uint32_t nsym
    ChrisoRel rel[512]
    uint32_t nrel

Os quatro índices de seção são text, rodata, data e BSS.

Para text, rodata e data, sec pode apontar para bytes materializados.

BSS é representada somente por sec_size. Um buffer de bytes de BSS não é necessário porque a seção descreve armazenamento inicializado com zero, e não payload do arquivo.

A imagem usa arrays de capacidade fixa para símbolos e relocations, portanto a construção do objeto não cresce dinamicamente essas tabelas.

## Semântica das seções

O modelo de seções é intencionalmente pequeno.

| Seção | Finalidade | Payload serializado |
| --- | --- | --- |
| text | código de máquina executável | sim |
| rodata | constantes somente leitura | sim |
| data | dados graváveis inicializados | sim |
| BSS | armazenamento gravável zerado | não |

A ausência de bytes de BSS é importante para o tamanho do arquivo e para a semântica do linker. Uma BSS de 64 KiB não adiciona 64 KiB de zeros ao arquivo ChrisO; apenas seu tamanho é registrado.

O linker posteriormente reserva espaço de endereçamento para essa seção lógica.

## Layout serializado

O formato serializado começa com cabeçalho fixo de 64 bytes.

As oito primeiras words de 32 bits são atualmente:

| Word | Significado |
| ---: | --- |
| 0 | magic |
| 1 | versão |
| 2 | quantidade de símbolos |
| 3 | quantidade de relocations |
| 4 | tamanho de text |
| 5 | tamanho de rodata |
| 6 | tamanho de data |
| 7 | tamanho de BSS na versão 2 |

O restante do cabeçalho de 64 bytes é zerado pelo writer atual.

Depois do cabeçalho o arquivo é sequencial:

    cabeçalho de 64 bytes
    bytes de text
    bytes de rodata
    bytes de data
    registros de símbolos
    registros de relocations

BSS não ocupa faixa de bytes no arquivo.

Não existe tabela de offsets de arquivo por seção porque os offsets são deriváveis da ordem fixa e dos tamanhos.

## Cálculo do tamanho

Na versão 2, chriso_file_bytes calcula:

    total =
        64
        + text_size
        + rodata_size
        + data_size
        + nsym * 80
        + nrel * 20

O writer verifica se a capacidade do buffer de destino é pelo menos esse valor.

chriso_write retorna a quantidade de bytes gravados ou -1 em falha.

Como a API usa capacidades uint32_t e o acumulador interno também é de 32 bits, a implementação é voltada a objetos relativamente pequenos, e não a arquivos de objeto de múltiplos gigabytes.

## Registro de símbolo

ChrisoSym possui tamanho on-disk fixo de 80 bytes, garantido por static assertion.

Os campos são:

| Campo | Significado |
| --- | --- |
| name[64] | armazenamento fixo do nome |
| section | índice da seção de definição |
| offset | offset relativo à seção |
| size | campo de tamanho do símbolo |
| binding | local, global ou indefinido |
| kind | notype, função ou objeto |
| reserved | campo reservado de 16 bits |

O nome inline simplifica serialização, pois não existe string table variável.

A contrapartida é não representar nomes arbitrariamente longos sem uma política upstream para caber no campo de 64 bytes.

ChrisAsm já constrói símbolos dentro dessa representação.

## Bindings

Três bindings são definidos:

- CHRISO_BIND_LOCAL;
- CHRISO_BIND_GLOBAL;
- CHRISO_BIND_UNDEF.

Um símbolo indefinido é uma solicitação ao linker, não uma definição. Seu endereço final precisa ser encontrado em outro objeto ou símbolo fornecido externamente.

O formato atual não modela weak symbols, classes de visibility, symbol versioning ou partições equivalentes às tabelas ELF.

## Kinds de símbolo

Três kinds existem:

- notype;
- function;
- object.

ChrisAsm usa function para rótulos em text e object para rótulos em seções de dados.

O kind é metadado descritivo usado pelo toolchain; ele não cria um sistema de tipos de linguagem.

## Registro de relocation

ChrisoRel versão 2 tem tamanho fixo de 20 bytes, também protegido por static assertion.

Ele armazena:

| Campo | Significado |
| --- | --- |
| section | seção que contém o campo a corrigir |
| offset | offset do campo de relocation |
| sym_index | índice na tabela de símbolos do objeto |
| addend | addend signed |
| type | tipo de relocation |

O formato reutiliza um subset dos identificadores numéricos de relocation ELF x86-64:

- R_X86_64_NONE;
- R_X86_64_64;
- R_X86_64_PC32;
- R_X86_64_PLT32;
- R_X86_64_32;
- R_X86_64_32S.

Reutilizar essas semânticas permite que ChrisAsm e ChrisLd apliquem fórmulas conhecidas de relocation x86-64 sem usar ELF como container de objeto.

## Semântica PC-relative

ChrisAsm normalmente emite relocations PC32 e PLT32 com addend -4.

Para um campo PC-relative de quatro bytes, a relação conceitual é:

    resultado = S + A - P

onde S é o endereço do símbolo resolvido, A é o addend e P é o local da relocation.

O ajuste -4 corresponde à convenção usada pelo assembler para deslocamento relativo ao endereço posterior ao campo de quatro bytes.

ChrisLd aplica o valor final depois de resolver o símbolo.

## Inicialização

chriso_init zera toda a ChrisoImage.

Isso estabelece invariantes iniciais:

- todos os ponteiros de seção nulos;
- todos os tamanhos de seção zero;
- zero símbolos;
- zero relocations.

Chamadores que constroem objeto devem começar desse estado ou de outro estado completamente controlado.

## Serialização

chriso_write primeiro valida que imagem e buffer de saída são não nulos.

Depois calcula o tamanho necessário, rejeita capacidade insuficiente e zera exatamente a faixa serializada.

O writer grava os words de cabeçalho, copia text/rodata/data quando tamanho é não zero e ponteiro está presente, e então copia todos os registros de símbolo e relocation na ordem dos arrays.

Bytes de BSS nunca são copiados.

O formato atual não contém checksum, hash ou footer.

Integridade depende do transporte confiável e da validação do parser, não de mecanismo criptográfico embutido.

## Desserialização e views zero-copy

chriso_read valida:

- ponteiros não nulos;
- entrada com ao menos 64 bytes;
- magic correto;
- versão suportada;
- nsym no máximo 256;
- nrel no máximo 512;
- tamanho de entrada ao menos igual ao tamanho serializado calculado.

Após inicializar a imagem, ele aponta diretamente as seções text, rodata e data para dentro do buffer de entrada.

Isso torna a leitura dessas seções zero-copy.

Símbolos e relocations são copiados para os arrays fixos dentro de ChrisoImage.

A consequência de ownership é importante: depois de chriso_read, o buffer de entrada precisa continuar vivo e imutável enquanto qualquer código usar img.sec das seções materializadas.

O reader não cria cópias independentes dos bytes dessas seções.

## Compatibilidade com versão 1

Registros de relocation da versão 1 possuem 16 bytes em vez de 20.

O reader escolhe o tamanho conforme a versão.

Para símbolos lidos da versão 1, ele força:

- binding local;
- kind notype;
- reserved zero.

Versão 1 não fornece o tamanho de BSS reconhecido pela versão atual, então BSS é tratada como zero.

Esse caminho permite consumir objetos antigos enquanto normaliza sua representação em memória.

## Limites de validação do reader

O reader faz verificações estruturais básicas, mas não é um verificador endurecido para objetos arbitrariamente não confiáveis.

Por exemplo, o código atual não valida de forma independente todas as relações semânticas após a leitura, como:

- índice de seção válido em cada símbolo conforme o binding;
- índice de seção válido em cada relocation;
- sym_index de cada relocation menor que nsym;
- campo de relocation inteiramente dentro da seção alvo;
- offset de símbolo dentro da seção que o define.

No desenho atual, parte dessas verificações pertence à validação do linker.

Além disso, o tamanho necessário usa acumulação de 32 bits. O formato é destinado a objetos limitados produzidos pelo projeto, não a entradas hostis de tamanho arbitrário.

Um verificador futuro independente deve checar overflow aritmético e cada referência cruzada antes de permitir uso pelo linker.

## chriso_merge_text

chriso_merge_text é helper especializado de composição, não linker geral de objetos.

Ele anexa apenas text do objeto source ao final de text do destination.

A função exige:

- source e destination não nulos;
- buffer de text já existente no destination;
- text combinado de no máximo 65.536 bytes;
- capacidade restante de símbolos;
- capacidade restante de relocations.

Os bytes de source text são copiados para o final do destination text.

## Ajuste de símbolos no merge

Ao anexar símbolos do source, símbolos definidos em text recebem incremento do offset igual ao tamanho original de destination text.

Símbolos indefinidos não recebem ajuste.

Símbolos definidos em outras seções são copiados sem que o conteúdo dessas seções seja combinado. Essa é uma das razões para chriso_merge_text não poder ser tratado como linker multi-section completo.

O helper só é apropriado quando seu contrato text-only é intencional.

## Ajuste de relocations no merge

Relocations do source são anexadas após as existentes no destination.

Quando o campo a corrigir está em text, o relocation offset recebe o incremento do tamanho original de destination text.

Cada relocation copiada também tem sym_index deslocado pela quantidade de símbolos que já existia no destino antes da anexação dos símbolos source.

Isso preserva a associação da relocation copiada com a entrada de símbolo correspondente.

O ajuste é mecânico e limitado pelas capacidades fixas.

## O que merge_text não faz

chriso_merge_text não:

- combina rodata;
- combina data;
- soma BSS;
- coalesce símbolos duplicados;
- resolve símbolos indefinidos;
- aplica relocations;
- executa alinhamento de seções;
- produz ELF;
- implementa regras gerais de resolução de linker.

Essas funções pertencem ao linker.

O nome deve ser interpretado literalmente: merge de text sob contrato estreito.

## Relação com ChrisAsm

ChrisAsm constrói ChrisoImage diretamente.

Ele preenche bytes das seções, adiciona símbolos e cria relocations enquanto codifica assembly.

No final, buffers das seções materializadas são alocados e associados à imagem.

ChrisO é a fronteira de objeto que permite ao assembler não conhecer os endereços finais do executável.

Calls externos e referências RIP-relative permanecem não resolvidos até ChrisLd enxergar todos os objetos participantes.

## Relação com ChrisLd

ChrisLd consome uma ou mais imagens ChrisO e resolve seu conteúdo num layout executável.

ChrisO fornece fatos relativos às seções; ChrisLd fornece posicionamento final.

Essa separação é um invariante central:

- offsets produzidos pelo assembler são locais às seções;
- resolução de símbolo escolhe uma definição final;
- aplicação de relocation converte estado relativo do objeto em endereços executáveis.

Um arquivo ChrisO não é diretamente executável apenas porque text contém código de máquina.

## Complexidade

Serialização e desserialização são lineares no estado armazenado.

Para tamanho de objeto B, S símbolos e R relocations:

- escrita é O(B + S + R);
- leitura é O(B + S + R) em validação/cópia, embora payloads de seções sejam expostos zero-copy;
- merge de text é O(bytes_text + S + R).

Os arrays fixos impõem limites constantes a S e R na versão atual.

## Comportamento de falhas

chriso_write retorna -1 para ponteiros nulos ou capacidade insuficiente.

chriso_read retorna -1 para estrutura de alto nível inválida, como magic incorreto, versão desconhecida, contagens excessivas ou entrada truncada.

chriso_merge_text retorna -1 para ponteiros nulos, ausência de armazenamento text no destino, overflow da capacidade de text, símbolos ou relocations.

A API não retorna enumeração detalhada de erros.

## Evidência de validação

tools/test_chriso.c executa um round trip mínimo:

1. inicializa imagem vazia;
2. serializa em buffer de 64 bytes;
3. lê de volta;
4. verifica o magic.

Isso comprova o caminho básico do cabeçalho para objeto vazio da versão atual.

Evidência adicional aparece indiretamente em tools/test_chrisasm.c e tools/test_chrisld.c, que constroem e consomem símbolos e relocations ChrisO em fluxos não vazios.

O teste dedicado de ChrisO ainda é muito menor que a superfície total do formato. São necessários testes diretos para compatibilidade de versão, cada seção, limites de símbolos, cada tipo de relocation, índices malformados e entradas truncadas.

## Limitações atuais

O formato troca generalidade por simplicidade de implementação.

Limites importantes:

- apenas quatro classes fixas de seção;
- capacidade de 256 símbolos;
- capacidade de 512 relocations;
- nomes inline de 64 bytes;
- ausência de string table;
- ausência de weak/visibility;
- ausência de COMDAT/groups;
- ausência de seções de debug;
- ausência de tag explícita de arquitetura além da convenção do toolchain;
- ausência de checksum ou assinatura;
- validação básica, não endurecida;
- comportamento text-only em chriso_merge_text.

As restrições são aceitáveis para o toolchain experimental atual, mas precisam permanecer explícitas ao discutir self-hosting ou compatibilidade.

## Limite entre estado atual e roadmap

Uma revisão futura de ChrisO pode adicionar:

- offsets e alinhamentos explícitos por seção;
- tabelas maiores ou dinâmicas;
- string tables;
- verificador mais estrito;
- aritmética de tamanho com detecção de overflow;
- identificadores de arquitetura e ABI;
- seções de debug/source mapping;
- binding de símbolos mais rico;
- helpers explícitos de ownership;
- API geral de merge multi-section.

Nada disso é propriedade da versão 2 atual.

## Proveniência da revisão

Este capítulo documenta ChrisO conforme observado no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

A autoridade do formato é compiler/chrisld/chriso.h e compiler/chrisld/chriso.c. A interação com assembly é evidenciada por compiler/chrisasm/chrisasm.c e tools/test_chrisasm.c. O comportamento do linker é representado por compiler/chrisld/chrisld.c e tools/test_chrisld.c.
