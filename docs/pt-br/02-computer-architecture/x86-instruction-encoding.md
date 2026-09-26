---
id: x86-instruction-encoding
lang: pt-br
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - ChrisInsn
  - chris_decode
  - read_modrm
  - imm_n
  - chris_format_insn
  - chris_eff_addr
  - chris_imm_sx
  - fetch_insn
depends_on:
  - machine-code
  - x86-registers-flags
related:
  - x86-64-memory-privilege
  - emulator-theory
---

# Codificação x86 e decodificação com limites explícitos

## Uma gramática cujos campos dependem dos anteriores

Um decoder x86 não pode dividir a entrada em palavras fixas e interpretar cada uma isoladamente. Prefixos influenciam largura e seleção de registradores; o opcode determina a necessidade de byte de endereçamento ou imediato; bits de endereço determinam outro byte ou deslocamento. A instrução possui, portanto, uma gramática condicional. Este capítulo acompanha os formatos legados e REX implementados no decoder da revisão declarada. VEX, EVEX e o espaço completo de extensões estão fora desta descrição vinculada à implementação.

O máximo arquitetural de quinze bytes limita uma instrução. Não autoriza ler quinze bytes de qualquer endereço inicial antes de determinar seu comprimento real. Segurança do buffer de entrada, validade do comprimento e acessibilidade da memória convidada são três obrigações distintas. Um decoder que trabalha sobre bytes disponíveis pode verificar limites corretamente enquanto o chamador busca bytes convidados em excesso. `fetch_insn` atualmente faz essa busca antecipada; o capítulo de datapath explica a consequência nas fronteiras de páginas.

![Gramática condicional das instruções](../../assets/diagrams/x86-decode-grammar.svg)

`ChrisInsn` normaliza a entrada em operação, comprimento, tamanho de operando, tamanho de endereço, prefixos, campos de endereçamento, deslocamento e imediato. A execução consome esse registro sem reinterpretar os bytes. Normalizar reduz análise duplicada somente se cada campo tiver invariante explícito: um operando exclusivamente de registrador não pode disparar cálculo de endereço, e uma base ausente não pode ser confundida com registrador zero.

## Estado de prefixos e seleção de largura

`chris_decode` começa com operando de quatro bytes e endereço de oito bytes. Examina prefixos reconhecidos enquanto há entrada e menos de quatorze bytes de prefixo foram consumidos. O prefixo de tamanho de operando registra preferência por 16 bits; o de endereço registra endereçamento de 32 bits. Um REX.W final seleciona operando de 64 bits no cálculo genérico. Famílias específicas podem substituir esse padrão, como PUSH e POP fazem para seus operandos usuais de pilha de 64 bits.

| Prefixo | Estado do decoder | Distinção necessária |
|---|---|---|
| `66` | Preferência por operando de 16 bits | Não muda tamanho de endereço |
| `67` | Endereçamento de 32 bits | Não seleciona sozinho dados de 32 bits |
| `f0` | Liga `lock` | Análise não demonstra execução atômica legal |
| `f2`, `f3` | Seletor de repetição | Significado depende da família de instruções |
| Substituições de segmento | Bytes consumidos | Segmento selecionado não é retido em `ChrisInsn` |
| `40` a `4f` | Byte REX | Presença altera aliases de registradores de byte |

Nesse analisador, um prefixo legado posterior limpa o REX armazenado; outro REX substitui o anterior. São regras observadas no código, não uma afirmação de que toda permutação de prefixos é arquiteturalmente legal para todo opcode. A execução ainda exige validação específica da operação. Reconhecer LOCK não transforma qualquer operação de registrador em instrução atômica válida de memória.

Um byte REX tem nibble superior `0100` e bits inferiores W, R, X e B. W solicita largura quando aplicável; R estende o campo de registrador de ModR/M; X estende índice de SIB; B estende r/m, base ou registrador embutido no opcode conforme o formato. Em `4d`, W, R e B são um, enquanto X é zero. Tratar os quatro bits como um único número de registrador perderia seus papéis distintos.

## ModR/M e extensões de opcode

Para um byte ModR/M m, o decoder extrai `mod = m >> 6`, `digit = (m >> 3) & 7` e `rm_field = m & 7`. O registrador estendido é `digit | (REX.R ? 8 : 0)`; r/m estendido usa REX.B. `digit` sem extensão é preservado porque certos grupos de opcode usam esses três bits para selecionar operação, em vez de registrador. Estender um seletor de grupo como registrador escolheria uma instrução errada.

| Bits mod | Interpretação geral | Deslocamento adicional |
|---|---|---|
| `00` | Endereçamento de memória | Ausente, salvo formatos especiais |
| `01` | Endereçamento de memória | Byte com sinal |
| `10` | Endereçamento de memória | Deslocamento de 32 bits com sinal |
| `11` | Operando de registrador | Ausente |

Em `48 01 d8`, ModR/M `d8` equivale a `11011000`: mod é três, reg é três e r/m é zero. A direção do opcode define destino RAX e fonte RBX. REX.W fornece operando de oito bytes. Não seguem SIB, deslocamento ou imediato; o comprimento é três. Essa decomposição conecta os campos ao caminho de ADD examinado no capítulo de datapath.

A tabela orienta a estrutura, mas não enumera todos os endereçamentos legais. Valores especiais dos campos inferiores introduzem SIB ou endereçamento relativo. O modo também importa: o decoder está organizado em torno do modelo de execução de 64 bits escolhido. Aceitar substituições de largura de operando e endereço não o transforma em decoder genérico dos modos de 16, 32 e 64 bits.

## SIB e cálculo completo de um endereço

Com operando de memória e campo r/m inferior quatro, `read_modrm` consome o byte scale-index-base. Os dois bits superiores fornecem expoente de escala; os três seguintes selecionam índice; os três inferiores selecionam base. Escala dois significa multiplicação por quatro, implementada por deslocamento de dois bits. REX.X e REX.B estendem índice e base independentemente.

Considere `48 8b 44 8d f0`. REX.W seleciona dados de oito bytes; `8b` seleciona destino registrador com fonte registrador/memória; ModR/M `44` seleciona RAX, endereçamento SIB e deslocamento de oito bits. SIB `8d` seleciona expoente dois, RCX como índice e RBP como base. O byte final `f0` representa −16 com sinal. Com RBP = `0x6000` e RCX = `0x2000`, o endereço efetivo é `0x6000 + 4 × 0x2000 − 16 = 0xdff0`.

Calcular esse valor não carrega o dado endereçado. O helper de operando solicita posteriormente oito bytes pela memória virtual. Permissões, mapeamento e comportamento de dispositivos pertencem a esse acesso. Uma fixture bem-sucedida de endereço valida aritmética e interpretação de campos, sem provar que a memória correspondente é legível ou contém um valor específico.

O campo de índice inferior quatro em SIB significa ausência de índice somente sem REX.X. Com REX.X, identifica R12. Base SIB inferior cinco com mod zero significa ausência de base e exige deslocamento. `no_index` e `no_base` preservam essas exceções explicitamente. Impedem que a execução some acidentalmente um registrador comum porque o campo bruto se parece com seu índice.

## Endereçamento relativo a RIP e lacuna documentada

Com mod zero, sem SIB e r/m inferior cinco, endereçamento de 64 bits usa deslocamento de 32 bits com sinal relativo à próxima instrução. `48 8b 05 78 56 34 12` tem sete bytes. Em RIP inicial `0x100000`, o endereço é `0x100007 + 0x12345678`. Usar RIP inicial sem acrescentar sete seria incorreto, mesmo que os campos isolados parecessem plausíveis.

O decoder marca esse formato como `rip_rel` somente quando o tamanho de endereço é oito. Com tamanho quatro, ainda consome deslocamento, mas não marca `no_base` para esse caso especial sem SIB. Consequentemente, `chris_eff_addr` percorre o caminho de base comum e soma o registrador selecionado por r/m antes de truncar para 32 bits. É uma inconsistência observada no caminho com substituição de endereço. As fixtures positivas de endereçamento não certificam esse caminho como correto.

Prefixos de segmento expõem outra limitação completa do percurso. O analisador consome seus bytes sem reter o segmento selecionado, e o helper de endereço não soma bases FS/GS. Um campo de `ChrisArchitectureState` não recupera informação descartada na decodificação. Suporte correto exige mudar a representação, acrescentar semântica correspondente e testes; atribuir valor a um MSR isoladamente não basta.

## Imediatos, extensão de sinal e representação hospedeira

`imm_n` aceita imediatos codificados em um, dois, quatro ou oito bytes e verifica se cabem em `avail`. Registra conteúdo e `imm_bytes`. Para oito bytes, combina duas partes de 32 bits. Preservar largura é necessário porque o executor decide se deve estender o sinal; guardar apenas um valor sem sinal previamente alargado perderia essa distinção.

Largura do operando não precisa coincidir com largura do imediato. Uma operação aritmética de 64 bits pode transportar imediato de 32 bits com sinal. Um formato MOV registrador-imediato pode transportar 64 bits completos, enquanto outro formato MOV estende seu imediato menor com sinal. O decoder deve determinar tamanho a partir da família selecionada, sem consumir oito bytes de imediato sempre que REX.W aparece. `chris_imm_sx` fornece posteriormente o alargamento com sinal das larguras suportadas.

Os helpers `ru16` e `ru32` usam `memcpy` para inteiros hospedeiros. Isso evita acessos por ponteiro tipado desalinhado e problemas de aliasing, mas interpreta os bytes na ordem nativa. A implementação não é automaticamente portátil para hospedeiro big-endian. Já os emissores de ChrisASM que usam deslocamentos e máscaras escolhem little-endian explicitamente. Portabilidade precisa ser examinada nos dois lados.

## Comprimento consumido, entrada incompleta e publicação

O decoder constrói `ChrisInsn` local inicialmente zerado. Se falta um campo obrigatório, os helpers retornam resultado negativo e a função superior retorna antes de copiar o registro local à saída. O chamador precisa tratar retorno negativo como falha, sem interpretar uma saída antiga como descrição dos bytes tentados. Construir localmente e publicar ao final ajuda a impedir que estado parcial de análise pareça uma instrução completa.

Classificação não suportada ou inválida difere de entrada incompleta. Para `0f 0b`, o decoder atual retorna registro de dois bytes classificado como `UD`; a execução pode então gerar opcode inválido. Quando o comprimento consumido excederia quinze, classifica UD e limita o comprimento registrado a quinze. Isso descreve a interface atual, sem prometer reconhecimento de toda codificação ilegal com prioridade de exceções idêntica à do hardware.

Sucesso informa comprimento de uma instrução, possivelmente menor que a entrada disponível. Para `48 8b 44 8d f0 90`, a primeira consome cinco bytes e deixa o NOP final para a próxima análise. Avançar pelo comprimento do buffer pularia uma instrução. Exigir que todo retorno positivo seja igual ao tamanho fornecido rejeitaria incorretamente buffers válidos com várias instruções.

## Complexidade, formatação e fronteiras de validação

A gramática suportada consome quantidade limitada de bytes, usa estrutura local de tamanho fixo e não aloca heap. O trabalho por instrução é limitado pelo comprimento e pela estrutura fixa de despacho; decodificar fluxo de N bytes em fronteiras conhecidas é linear na quantidade consumida. Isso não determina o custo de localizar código em entrada arbitrária contendo código e dados misturados, problema que exige informações de formato e fluxo de controle.

`chris_format_insn` produz texto de depuração, incluindo operandos abreviados como `[mem]`. Não é serialização sem perda capaz de reconstruir todos os bytes ou prefixos originais. Ferramentas de trace devem preservar bytes brutos e comprimento junto da string. Um futuro cache de instruções decodificadas exigiria regras para escritas em código, mudanças de mapeamento e invalidação; tal cache não é atribuído a este parser.

A sonda do repositório compila decoder e operandos reais com callbacks de memória que rejeitam acessos. Passaram vinte fixtures literais, seus 69 truncamentos próprios, 80 casos de registradores, dois índices inválidos, quatro endereços e uma classificação UD. Ela exercita esses contratos, mantendo fora da prova legalidade completa de prefixos, famílias não suportadas, prioridade de falhas, lacunas de substituição de endereço e execução convidada. Fuzzing e testes diferenciais mais abrangentes complementariam as fixtures; são validação futura, não resultados apresentados como executados.

A referência normativa é o [manual de instruções Intel](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html). As observações de implementação estão vinculadas à revisão e distinguem mecanismo do parser, requisito arquitetural e comportamento ainda aberto. Essa separação permite atualizar um campo ou helper sem ampliar silenciosamente a compatibilidade atribuída ao emulador.
