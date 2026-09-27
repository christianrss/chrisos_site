---
id: data-representation-layout
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/chris_arch.h
- compiler/chrisld/chriso.h
- kernel/fs/cfs_format.h
- kernel/gfx/virtq.c
- kernel/gfx/virtq.h
symbols:
- ChrisArchitectureState
- ChrisoImage
- virtq_set
- virtq_bytes
- virtq_publish
- cfs_get16
- cfs_get32
- cfs_put16
- cfs_put32
depends_on:
  - number-systems-binary-arithmetic
  - registers-counters
related:
- data-structures
- cpu-datapath-isa
---

# Representação de dados, layout de memória e ponteiros

<div class="abstract">
Software nunca manipula “dados” abstratos diretamente. Manipula padrões de bits armazenados em endereços segundo contratos de representação. Largura, sinal, endianness, alinhamento, layout de estruturas, interpretação de ponteiros e serialização determinam como os mesmos bits adquirem significado. Este capítulo estabelece essas regras antes de estruturas de dados e algoritmos, porque um algoritmo sobre array, árvore, page table ou formato de arquivo só é correto quando a representação subjacente é definida.
</div>

## Bits recebem significado por contrato

A sequência <code>11111111</code> não possui significado intrínseco de software. Em um contrato é o inteiro sem sinal 255; em outro, o inteiro em complemento de dois -1; pode ainda ser byte de instrução, componente de cor, máscara de flags ou parte de uma estrutura codificada.

Representação possui duas camadas:

1. padrão físico ou arquitetural de bits;
2. interpretação atribuída por tipo, protocolo ou formato.

Sistemas operacionais atravessam continuamente essas fronteiras. Um endereço físico é armazenado em campo inteiro; uma entrada de page table combina endereço e flags; um cabeçalho ELF interpreta bytes consecutivos como campos tipados; um pacote de rede define ordem dos bytes; um emulador reconstrói operandos a partir do stream de instruções.

Código de sistemas correto torna esses contratos explícitos.

## Largura

Um inteiro sem sinal de n bits possui 2^n padrões e representa 0 até 2^n-1. Um inteiro com sinal em complemento de dois usa os mesmos padrões para representar -2^(n-1) até 2^(n-1)-1.

Largura interfere em:

- overflow e wrap;
- shifts;
- máscaras;
- truncamento de ponteiros;
- layout de ABI;
- compatibilidade de formatos persistentes;
- encoding de instruções;
- garantias de atomicidade.

Converter 64 bits para 32 bits não é mudança cosmética. Informação é descartada se não houver prova de que o valor cabe. Bugs de kernel e compilador frequentemente surgem quando valores do tamanho de endereço são estreitados.

## Campos de bits e máscaras

Software de baixo nível frequentemente empacota vários campos em uma palavra.

    63                              12 11             0
    +--------------------------------+----------------+
    | endereço / bits de implementação|     flags      |
    +--------------------------------+----------------+

Extração:

    flags    = entry & FLAG_MASK
    endereco = entry & ADDRESS_MASK

Modificação precisa preservar bits não relacionados:

    entry = (entry & ~TARGET_MASK) | new_bits

O invariante central não é a expressão em C, mas a definição de quais posições pertencem a cada campo semântico.

## Endianness

Endianness define a ordem dos bytes de valores multibyte.

Para 0x12345678 em endereços crescentes:

| Offset | Little-endian | Big-endian |
|---:|---:|---:|
| +0 | 0x78 | 0x12 |
| +1 | 0x56 | 0x34 |
| +2 | 0x34 | 0x56 |
| +3 | 0x12 | 0x78 |

x86-64 usa little-endian para representação ordinária de inteiros em memória. Um formato de software pode definir outra ordem. Protocolos de rede tradicionalmente utilizam big-endian, enquanto executáveis e filesystems declaram explicitamente sua codificação.

Endianness se torna observável quando bytes brutos atravessam uma fronteira.

## Alinhamento

Um objeto está alinhado quando seu endereço satisfaz determinada divisibilidade. Um objeto de alinhamento 16 começa em endereço divisível por 16.

Motivações incluem:

- requisitos da ISA;
- desempenho;
- atomicidade;
- exigências de DMA;
- alinhamento de page tables;
- operações vetoriais;
- regras de ABI e formatos.

Alinhamento cria padding. Uma estrutura com um byte seguido de um inteiro de 64 bits pode ocupar mais de nove bytes porque o segundo campo é reposicionado para offset adequado.

## Layout de estruturas

Uma estrutura de linguagem é uma sequência de campos submetida às regras do compilador e da ABI.

Por isso uma <code>struct</code> em memória não deve ser tratada automaticamente como formato de disco ou wire format.

Um formato estável deve definir:

- larguras exatas;
- offsets exatos;
- ordem de bytes;
- versão;
- alinhamento/packing;
- campos reservados;
- cobertura de checksum;
- limites e quantidades máximas.

ChrisO, ChrisFS e formatos executáveis exigem estabilidade entre produtores e consumidores.

## Padding

Bytes de padding não pertencem semanticamente aos campos comuns. Copiar uma estrutura como bloco opaco pode expor padding não inicializado ou quebrar compatibilidade se o layout do compilador mudar.

Para formatos persistentes, encode/decode explícito é frequentemente mais seguro.

    estrutura lógica
        ↓
    layout da linguagem
        ↓
    representação externa codificada

As três camadas podem ser diferentes por projeto.

## Ponteiros

Um ponteiro é um valor interpretado como localização de um objeto em um espaço de endereços. Não é apenas “um inteiro com endereço”, mesmo quando a implementação de máquina usa codificação numérica.

Validade depende de:

- espaço de endereços;
- permissões;
- alinhamento;
- lifetime do objeto;
- regras de provenance da linguagem;
- mapeamento das page tables;
- nível de privilégio.

O mesmo número pode ser endereço válido em um processo e não mapeado em outro.

## Endereços físicos e virtuais

Endereço físico identifica posição no espaço físico da máquina. Endereço virtual é interpretado por estruturas de tradução associadas a um address space.

    endereço virtual
        ↓
    page-table walk
        ↓
    frame físico + offset

Endereços virtuais distintos podem apontar para o mesmo frame. O mesmo endereço virtual em processos diferentes pode apontar para frames distintos. Regiões podem não possuir mapeamento.

Algoritmos que recebem endereços precisam declarar qual representação manipulam.

## Offset versus ponteiro

Formatos persistentes usam normalmente offsets ou identificadores, não ponteiros do processo produtor. Ponteiro depende de um address space e de lifetime; offset pode ser reconstruído a partir de uma base conhecida.

Relocation é, em essência, uma regra para converter representação simbólica ou relativa em endereço final.

## Arrays

Array armazena elementos de tamanho igual contiguamente.

Se base é o endereço inicial e cada elemento ocupa S bytes:

endereço(i) = base + i × S

Acesso indexado é O(1) porque nenhum elemento anterior precisa ser percorrido.

Contiguidade também favorece localidade espacial: cache lines trazem bytes vizinhos e travessias sequenciais usam melhor largura de banda.

A contrapartida aparece em resize e inserção no meio, que podem exigir mover muitos elementos.

## Strings

String não possui representação universal.

Modelos comuns:

- bytes terminados em zero;
- comprimento explícito + bytes;
- buffers de capacidade fixa;
- strings prefixadas por comprimento;
- sequências de code units Unicode.

String terminada em zero exige busca O(n) para descobrir comprimento, salvo cache. Representação com comprimento permite O(1), mas ainda precisa de capacidade e regras de encoding.

No kernel, strings não confiáveis precisam sempre de limite. Procurar terminador indefinidamente através de memória inválida é incompatível com uma fronteira de privilégio segura.

## Unions com e sem tag

Uma área de armazenamento pode representar vários tipos de valor. Em uma representação tagged existe discriminador explícito:

    kind = INTEGER
    payload = 42

Sem tag, a interpretação depende de invariante externo.

Tags consomem espaço, mas facilitam detectar interpretações ilegais. Estruturas untagged podem ser compactas quando o contrato é forte.

Decoders, ASTs, mensagens de dispositivos e registros variantes usam esses padrões.

## Handles e índices

Um kernel pode expor um handle inteiro em vez de ponteiro direto. O handle indexa uma tabela protegida que contém referência real e metadados.

Vantagens:

- impedir alteração direta de ponteiro de kernel;
- validar ownership;
- permitir revogação;
- desacoplar ABI externa de endereços internos;
- explicitar lifetime.

O custo é lookup adicional e gerenciamento seguro de reutilização.

## Serialização

Serializar converte modelo em memória para sequência de bytes com regras explícitas. Desserializar executa o caminho inverso validando a entrada.

Todo comprimento, offset e count vindo do exterior deve ser considerado não confiável até prova de bounds.

Para uma região em offset O, comprimento L e buffer N, testar apenas O + L <= N é insuficiente porque a soma pode overflow. Forma robusta:

    O <= N
    L <= N - O

Esse padrão é fundamental em loaders e parsers de filesystem.

## Overflow como falha de representação

Quando cálculo determina tamanho de alocação, span de arquivo ou intervalo de endereço, overflow pode converter valor enorme inválido em valor pequeno aparentemente válido.

Para count elementos de tamanho S:

    bytes = count × S

precisa de verificação antes da multiplicação ou de aritmética checked.

Validação de bounds é um algoritmo sobre inteiros finitos, não sobre inteiros matemáticos infinitos.

## Ownership

Ponteiro ou índice diz onde está o objeto, mas não quem deve liberá-lo.

Software de sistemas trabalha com categorias como:

- lifetime estático;
- lifetime de stack;
- alocação pertencente ao processo;
- alocação global do kernel;
- DMA buffer pertencente ao driver;
- objeto reference-counted;
- referência emprestada;
- transferência de ownership.

Mesmo quando o tipo da linguagem não codifica ownership, a documentação precisa fazê-lo.

## Layout e localidade de cache

Representações logicamente equivalentes podem apresentar desempenho muito diferente.

Array of structures:

    [A0 B0 C0][A1 B1 C1][A2 B2 C2]

Structure of arrays:

    [A0 A1 A2] [B0 B1 B2] [C0 C1 C2]

Se o algoritmo percorre apenas A, a segunda forma pode usar cache lines melhor. Se consome registros completos, a primeira pode ser superior.

Escolher estrutura de dados também significa escolher layout.

## Exemplos no ChrisOS

A árvore atual mostra várias classes:

| Fonte | Papel de representação |
|---|---|
| <code>chrisvm/chris_arch.h</code> | estado arquitetural da CPU em campos de largura explícita |
| <code>compiler/chrisld/chriso.h</code> | seções, símbolos e relocations com arrays limitados |
| <code>kernel/fs/cfs_format.h</code> | contratos persistentes do filesystem |
| page tables | endereço combinado com flags |
| drivers VirtIO | descritores compartilhados com dispositivo |
| gráficos | pixels, vértices, matrizes e command buffers |

A representação já é parte do algoritmo. Um PMM com um bit por frame possui comportamento diferente de um alocador que mantém objetos completos por frame; ring buffers dependem de índices modulares; parsers dependem de tokens.

Os capítulos seguintes passam de representação para modelos de custo e depois para organizações estruturadas de dados.

## Reconstrução de um descritor byte por byte

`virtq_set` fornece um exemplo concreto de serialização. Cada descritor ocupa dezesseis bytes em um buffer compartilhado. A função calcula seu início como o deslocamento da base mais dezesseis vezes o índice. Depois escreve endereço, tamanho, flags e próximo índice com funções little-endian explícitas. O layout independe de um compilador C inserir padding em uma estrutura equivalente.

| Deslocamentos no descritor | Largura | Significado | Bytes de exemplo, menor endereço primeiro |
|---|---|---|---|
| 0–7 | 64 bits | Endereço do buffer visível ao dispositivo | `88 77 66 55 44 33 22 11` |
| 8–11 | 32 bits | Tamanho, aqui 4096 | `00 10 00 00` |
| 12–13 | 16 bits | Flags, aqui NEXT | `01 00` |
| 14–15 | 16 bits | Próximo descritor, aqui 7 | `07 00` |

O endereço codificado é `0x1122334455667788`. Trata-se de um valor ilustrativo, não de uma alocação válida ou mapeamento DMA fornecido pelo projeto. A ordem de bytes define a representação do número; nada diz sobre a permissão do dispositivo para acessar esse endereço. Tradução, tempo de vida e propriedade exigem contratos adicionais.

Para uma fila de oito entradas, os descritores ocupam 8 × 16 = 128 bytes. A área available consome 4 + 2 × 8 + 2 = 22 bytes. A implementação alinha a área used seguinte a quatro bytes, iniciando-a no deslocamento 152 em vez de 150. Essa área ocupa 4 + 8 × 8 + 2 = 70 bytes, totalizando 222. Os dois bytes de padding decorrem do layout, não são entradas extras. Os cálculos seguem `virtq_bytes`; escolher uma estrutura packed arbitrária não os explicaria.

## Um objeto em memória não é sua imagem serializada

`ChrisoImage` contém ponteiros de seções, tamanhos e arrays limitados de símbolos e relocações. Um ponteiro de seção pertence ao espaço de endereços do processo hospedeiro. Escrever os bytes crus da estrutura em arquivo preservaria endereços sem significado para outro processo. Em contraste, `ChrisoSym` e `ChrisoRel` têm asserções explícitas de tamanho de 80 e 20 bytes no cabeçalho inspecionado. Essas asserções restringem tamanho, mas não provam ordem de bytes, índices válidos ou a gramática completa do arquivo.

A distinção também aparece no CFS. `CfsSuper` e `CfsInode` são representações úteis em memória, enquanto `cfs_get16`, `cfs_get32`, `cfs_put16` e `cfs_put32` montam ou distribuem bytes explicitamente. Converter um ponteiro arbitrário de bytes em ponteiro para inteiro multibyte pode acrescentar hipóteses de alinhamento e aliasing. Operações explícitas tornam a ordem visível e evitam presumir que todo buffer externo possui alinhamento de objeto nativo.

## Limites, tempo de vida e publicação são provas separadas

Antes de acessar um campo de tamanho L no deslocamento O de um buffer com tamanho N, deve-se provar O ≤ N e depois L ≤ N − O. A forma com subtração evita overflow em O + L. Em arrays, é preciso provar o limite do índice e a representabilidade da multiplicação pelo stride antes de formar o endereço. Após essas verificações, a alocação subjacente ainda precisa estar viva e sob responsabilidade de quem possui permissão de acesso.

Por fim, publicar memória compartilhada exige ordenação: um consumidor não pode observar o novo índice antes de os bytes correspondentes estarem prontos. `virtq_publish` coloca barreiras ao redor da publicação, mas o serializador de descritores não bloqueia a fila nem valida o mapeamento do dispositivo. Bytes corretos, limites válidos, tempo de vida estável e sincronização correta são quatro obrigações distintas. Um exemplo de serialização aprovado demonstra apenas a primeira, a menos que as demais sejam verificadas explicitamente.
