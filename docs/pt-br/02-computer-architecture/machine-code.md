---
id: machine-code
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - tools/test_chrisasm.c
symbols:
  - chrisasm_assemble
  - emit_u32
  - emit_call_or_jmp
  - patch_fixups
  - publish_secs
  - chris_decode
depends_on:
  - cpu-datapath-isa
  - data-representation-layout
related:
  - x86-instruction-encoding
  - x86-registers-flags
  - elf-linking
---

# Código de máquina, assembly e significado relocável

## Bytes adquirem significado por um contrato

Um byte é um inteiro entre zero e 255. A memória não marca determinado byte como opcode, caractere, endereço ou pixel. Quem o consome fornece essa interpretação. Na execução de instruções, ela depende do conjunto de instruções, do modo de execução e do endereço inicial. Os mesmos bytes podem indicar instruções diferentes em modos diferentes; começar no meio de uma instrução de comprimento variável pode produzir outra sequência. Uma desmontagem é, portanto, uma afirmação sobre contexto, não apenas uma apresentação de valores hexadecimais.

O capítulo de datapath descreve execução como transição de estado. Código de máquina fornece a operação e os operandos codificados dessa transição. A sintaxe determina onde os campos começam e terminam; a semântica determina seus efeitos. Reconhecer uma sequência não demonstra que a instrução é suportada pelo emulador, permitida no privilégio atual ou capaz de acessar seus operandos. Essas perguntas pertencem a etapas diferentes e exigem distinguir seus motivos de falha.

Assembly torna os bytes manipuláveis por meio de mnemônicos, nomes de registradores, endereços simbólicos e diretivas. O montador escolhe codificações e registra relações ainda não resolvidas. O ligador posiciona seções e resolve relações entre objetos. O carregador estabelece mapeamentos e estado inicial de processo. A execução consome o resultado dessa cadeia. Confundir essas responsabilidades atribui indevidamente ao montador a inicialização da pilha ou ao decoder a localização de funções externas.

## Uma pequena sequência completa de bytes

Considere estes bytes literais em um ambiente de execução de 64 bits:

| Deslocamento | Bytes | Interpretação | Comprimento |
|---|---|---|---|
| 0 | `b8 2a 00 00 00` | Mover o imediato 42 para EAX | 5 |
| 5 | `83 c0 01` | Somar a EAX o imediato 1 estendido com sinal | 3 |
| 8 | `c3` | Retorno próximo | 1 |

O imediato 42 aparece com o byte menos significativo primeiro. B8 identifica o formato registrador-imediato para o registrador inferior selecionado no opcode. Nesse formato, sem prefixo modificando largura, o operando possui 32 bits. Escrever EAX em modo de 64 bits também zera a metade superior de RAX. A segunda instrução realiza soma de 32 bits: suas flags correspondem a essa largura, embora a implementação C hospedeira armazene registradores em campos de 64 bits.

Depois das duas primeiras instruções, EAX vale 43. O retorno não significa que a CPU para ou imprime 43. Ele obtém um endereço de retorno na pilha e transfere o controle para lá. Um chamador, uma ABI e uma pilha válida são pré-requisitos para interpretar a sequência como uma função que retorna. Um buffer bruto de nove bytes não possui, por si só, cabeçalho executável, resolução de importações, permissões de memória ou pilha inicial. Essas propriedades não decorrem da validade dos opcodes.

As fixtures usam bytes literais deliberadamente, em vez de gerá-los com o próprio montador sob teste. Uma ida e volta por codificador e decodificador pode esconder erro compartilhado: ambos podem concordar com a mesma interpretação incorreta. Bytes conhecidos de forma independente tornam o contrato explícito. Ainda assim, cobrem apenas formatos selecionados e não constituem uma suíte completa de conformidade x86.

## Seleção de instruções e equivalência semântica

Uma operação assembly pode admitir várias codificações. Uma constante pode caber em imediato curto, imediato estendido com sinal ou imediato de largura completa. O montador precisa preservar largura e valor solicitados ao escolher formatos suportados. Menor comprimento não garante correção: um imediato negativo estendido com sinal e uma escrita de registrador de 32 bits estendida com zeros produzem valores diferentes em 64 bits. Largura integra o significado, além do custo de armazenamento.

Da mesma forma, sequências que deixam o mesmo valor final em um registrador geral podem não ser intercambiáveis. Podem diferir em flags, acessos à memória, exceções, atomicidade ou comprimento. Substituir uma movimentação de zero por uma operação lógica que limpa o registrador muda flags. Substituir uma operação de memória por várias instruções pode expor estados intermediários. Um otimizador precisa demonstrar equivalência para as observações permitidas pelo modelo da linguagem e do alvo, em vez de comparar um único resultado.

A sintaxe do montador é outra camada independente. Notação com destino primeiro define uma convenção textual, não obriga que o destino seja codificado antes da fonte nos bytes. Bits de direção do opcode e campos ModR/M selecionam papéis diferentes. ChrisCPU representa essa distinção em campos de formato de operandos, permitindo que os helpers encontrem destino antigo e fonte sem analisar novamente o texto assembly.

## Imediato, deslocamento e origem relativa

Um imediato é um valor embutido na instrução. Um deslocamento contribui para um endereço ou destino de controle. Ambos ocupam bytes, mas têm interpretações diferentes. `chris_imm_sx` estende larguras suportadas com sinal quando a semântica exige. O decoder deve preservar largura codificada e conteúdo numérico; caso contrário, perde a informação necessária para distinguir o byte 254 do deslocamento relativo −2.

A sequência `eb fe`, com dois bytes no endereço `0x1000`, ilustra controle relativo. Seu deslocamento é −2 com sinal. A origem relativa é o endereço seguinte à instrução, `0x1002`, portanto o destino é `0x1000`. Somar −2 ao endereço inicial produziria destino errado. Essa convenção também explica por que relocar um deslocamento exige considerar a posição e a largura do campo que será corrigido.

Para relocação relativa ao contador de programa com quatro bytes, escreva valor = S + A − P: S é endereço do símbolo, A é adendo e P é endereço do campo corrigido. Uma chamada em `0x1000` tem campo em `0x1001` e próxima instrução em `0x1005`. Para destino `0x1100`, adendo −4 fornece `0x1100 − 4 − 0x1001 = 0xfb`. A CPU soma `0xfb` a `0x1005` e alcança `0x1100`.

## Representações e propriedade em ChrisASM

`chrisasm_assemble` recebe texto-fonte e uma saída `ChrisoImage`. Inicializa a saída, reinicia contadores e analisa linhas acumulando seções, símbolos e correções pendentes. Três buffers estáticos contêm TEXT, RODATA e DATA inicializadas, cada um com capacidade de 65.536 bytes. Quatro contadores incluem BSS, cujo tamanho é significativo sem buffer de bytes inicializados. A estrutura expressa a diferença entre bytes armazenados no objeto e espaço que será alocado e inicializado posteriormente.

`ChrisoImage` contém quatro ponteiros e tamanhos de seção, um vetor limitado a 256 símbolos e outro limitado a 512 relocações. `ChrisoSym` registra nome, seção, deslocamento, tamanho, vinculação e espécie. `ChrisoRel` registra seção, deslocamento, índice de símbolo, adendo com sinal e tipo de relocação. Asserções estáticas fixam os tamanhos dos registros de símbolo e relocação em 80 e 20 bytes. A imagem em memória também possui ponteiros: a estrutura C inteira não é diretamente uma imagem de disco portátil.

`emit_u32` decompõe um inteiro em quatro bytes little-endian usando deslocamentos e máscaras. Esse método independe da ordem de bytes do hospedeiro. `emit_u8` verifica seção inicializada atual e capacidade; destino inválido ou buffer cheio liga `g_overflow`. A função superior rejeita overflow antes de publicar. Distinguir uma flag de erro de um retorno imediato é necessário ao inspecionar o restante da análise depois que a capacidade foi atingida.

`publish_secs` aloca espaço para cada seção inicializada não vazia usando `malloc` ou `kmalloc` e copia os buffers estáticos. BSS recebe ponteiro nulo e tamanho. Essas cópias separam os bytes de uma saída bem-sucedida da reutilização posterior dos buffers de emissão. Porém, se a alocação de uma seção posterior falha, a função retorna sem liberar visivelmente as seções já alocadas. Chamadores e uma futura auditoria de propriedade precisam considerar saída parcialmente preenchida; copiar no caminho de sucesso não demonstra reversão completa em todos os erros.

## Correções locais e relocações externas

![Montagem, correções locais e relocação](../../assets/diagrams/machine-code-relocation.svg)

Rótulos da mesma seção iniciados por `.L` usam uma tabela local separada. Cada entrada contém nome limitado, seção, deslocamento e flag de definição. Referências futuras produzem entradas de correção com nome, seção e posição a corrigir. Separar esses rótulos evita consumir um símbolo público do objeto para cada desvio local, preocupação registrada explicitamente em comentário no código.

`patch_fixups` procura cada destino, rejeita rótulo indefinido ou seção incompatível, verifica se quatro bytes cabem na seção, calcula o deslocamento relativo e grava little-endian. A expressão exata é `target_offset - (patch_offset + 4)`. Como ambas as posições pertencem à mesma seção, o endereço final de carregamento se cancela. Referência entre seções não permite esse cancelamento antes de conhecer o posicionamento.

A tabela local permite 1.024 entradas e a de correções 4.096. `local_find` faz busca linear. Com F correções e L rótulos, a resolução executa O(F × L) comparações de nomes no pior caso, com nomes de comprimento limitado. O consumo de memória é fixado pelas capacidades dos vetores; acrescentar uma correção é constante quando há espaço. Uma tabela hash poderia melhorar o tempo esperado de busca em entradas maiores, acrescentando complexidade de representação e política de colisões. É uma alternativa, não o algoritmo atual.

`emit_call_or_jmp` registra símbolo não resolvido, emite opcode e deslocamento zerado e adiciona relocação `R_X86_64_PLT32` com adendo −4. O nome do tipo não demonstra a existência de uma Procedure Linkage Table dinâmica. Ele descreve um registro consumido pelo ligador. Uma afirmação sobre carregamento dinâmico precisa inspecionar separadamente esse consumidor e o suporte em tempo de execução.

## Falhas de análise, reentrância e observabilidade

O analisador superior usa buffer de linha com 512 bytes. Caracteres além da capacidade retida são consumidos sem serem acrescentados; isso não é um diagnóstico explícito que rejeita toda linha excessiva. O prefixo truncado é o texto que chega à análise. O armazenamento de identificadores também é limitado. Esses limites precisam aparecer na documentação porque aceitar um token ou linha encurtado difere de rejeitar o texto original com diagnóstico útil.

O estado do montador reside em globais estáticas. Duas chamadas concorrentes podem sobrescrever buffers e contadores uma da outra; uso recursivo não se torna seguro porque cada chamador fornece imagem de saída diferente. Um projeto reentrante colocaria buffers, tabelas locais, contadores e diagnóstico em contexto por invocação. Serializar chamadores seria outra contenção possível. O ponto de entrada inspecionado não fornece esse contexto nem uma trava de sincronização.

O resultado público informa sucesso ou falha; não fornece erro estruturado com trecho do fonte, gramática esperada e ação de recuperação. Isso limita ferramentas que precisam apresentar diagnósticos precisos em editores. Melhorar essa interface exige transportar posição de origem pela tokenização e distinguir sintaxe inválida, capacidade esgotada, rótulo indefinido e alocação malsucedida. Descrever esses conceitos separadamente não significa que o código de retorno atual os distingue.

## Evidência reproduzível e fronteiras

`make host-chrisasm-test` compila e executa o teste de montagem do repositório. Ele verifica montagem básica de MOV/RET, rejeição de mnemônico desconhecido, relocação de chamada externa com adendo −4 e codificação de PUSH R8. Passou na revisão declarada. Não enumera todos os mnemônicos, limites de capacidade, operandos malformados ou caminhos de falha de alocação.

`python scripts/check_instruction_contracts.py --source .source` compila separadamente o decoder real e os helpers de operandos. Passaram suas 20 fixtures literais, 69 truncamentos, 80 casos de registradores, dois índices inválidos, quatro endereços efetivos e uma classificação de opcode não suportado. Os callbacks de memória rejeitam acessos; portanto, não é um teste de execução convidada ou inicialização. A relação entre saída do montador, relocação do ligador, carregamento e execução completa permanece uma cadeia de contratos que exige evidência em cada fronteira.

Codificações normativas pertencem aos [manuais de arquitetura Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html). Buffers limitados, algoritmo de rótulos, emissão de relocações e limitações do analisador são observações da revisão declarada do ChrisOS. Melhorias futuras devem preservar essa distinção ao acrescentar diagnósticos estruturados, limpeza explícita de propriedade e fixtures de codificação mais abrangentes e especificadas independentemente.
