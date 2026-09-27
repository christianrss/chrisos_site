---
id: sram-dram
lang: pt-br
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/metal/pmm.c
- kernel/metal/pmm.h
- kernel/gfx/graphics.c
- chrisvm/machine/machine.c
symbols:
- bitmap_is_used
- mark_usable_free
- mark_range_used
- pmm_init
- gfx_init
- chris_machine_create
- chris_machine_destroy
depends_on:
  - latches-flipflops
  - clock-timing
  - transistor-cmos
  - capacitance-inductance
related:
- physical-memory
- virtual-memory
- cache-hierarchy
- pixels-framebuffer
---

# SRAM, DRAM e a abstração de memória utilizada pelo ChrisOS

## Do bit armazenado ao recurso endereçável

Uma célula de memória preserva um estado dentre um conjunto de estados físicos distinguíveis. Um array acrescenta um mecanismo de seleção para ler ou escrever uma posição sem exigir um fio externo independente para cada bit armazenado. A memória endereçável por bytes vista pelo programa já é uma abstração acima de células, decodificadores de linha, amplificadores de leitura, comandos do controlador, barramentos e mapeamento de endereços. Compreender essa abstração evita dois erros de categoria: identificar uma página do sistema operacional com uma linha física de DRAM e pressupor que “alocado” significa “eletricamente inicializado”.

Os fundamentos necessários são chaveamento CMOS, realimentação positiva e temporização sequencial. Este capítulo explica princípios convencionais de SRAM e DRAM e os conecta a `pmm.c`, à alocação gráfica e à RAM do ChrisVM respaldada pelo hospedeiro. Não afirma que o ChrisOS constrói um controlador DRAM ou expõe a geometria dos transistores da máquina. Esses detalhes são fornecidos pela plataforma ou modelados abaixo da interface de software do convidado.

## A célula SRAM de seis transistores

Uma célula SRAM convencional de seis transistores contém dois inversores CMOS com realimentação cruzada e dois transistores de acesso. Os inversores formam um circuito biestável: um nó interno permanece alto e o outro baixo, ou vice-versa. Os transistores de acesso conectam esses nós a um par de linhas de bit quando a linha de palavra é habilitada. O estado é mantido pela realimentação ativa enquanto existe alimentação, em vez de depender da leitura e reescrita periódicas de um pequeno capacitor de armazenamento.

Essa é a razão do termo “estática”. Ele não significa consumo nulo nem preservação dos dados sem energia. Correntes de fuga e atividade periférica continuam relevantes. Também não significa que sinais arbitrários de leitura e escrita possam ser aplicados sem restrições temporais. Duração da linha de palavra, desenvolvimento do sinal nas linhas de bit e detecção precisam respeitar o projeto da célula e do array.

Em uma leitura simplificada, as linhas de bit são preparadas e a linha de palavra habilita as células selecionadas. Seus valores produzem um pequeno sinal diferencial, resolvido por um amplificador de leitura. A leitura não pode perturbar o estado interno a ponto de invertê-lo. Na escrita, os drivers das linhas de bit impõem um valor diferencial forte o suficiente para mudar a célula selecionada. O dimensionamento dos dispositivos equilibra estabilidade de leitura, capacidade de escrita e densidade. A contagem de transistores, sozinha, não descreve velocidade, robustez ou energia.

## A célula DRAM de um transistor e um capacitor

Uma célula DRAM convencional usa um transistor de acesso e um capacitor de armazenamento. Habilitar a linha de palavra conecta o capacitor a uma linha de bit. Sua carga corresponde a um estado lógico segundo a convenção de detecção do projeto. Essa carga diminui por fuga, portanto a informação não é preservada indefinidamente sem atualização periódica, denominada refresh. Comparada à célula de seis transistores, essa organização favorece densidade elevada, mas exige acesso e restauração mais elaborados.

Quando a célula se conecta à linha de bit previamente carregada, o compartilhamento de carga produz uma pequena variação de tensão. O amplificador detecta essa diferença, conduz o sinal a um nível lógico completo e restaura a carga da célula conectada. A leitura participa, portanto, da restauração; o capacitor não é uma fonte permanente de tensão observável sem consequência. Os amplificadores de uma linha mantêm a linha ativada, formando o que costuma ser chamado row buffer.

O refresh revisita linhas dentro das restrições de retenção. Como a retenção varia com as condições físicas, a política pertence ao contrato entre dispositivo e controlador. Um kernel que aloca um frame físico comum normalmente não atualiza cada byte em um laço de software. A plataforma mantém esse serviço abaixo da interface de memória. Desabilitar o refresh não transforma DRAM em SRAM mais lenta: torna a informação armazenada não confiável.

| Propriedade | SRAM convencional | DRAM convencional |
|---|---|---|
| Estado armazenado | Realimentação biestável | Carga em um capacitor |
| Modelo comum de célula | Seis transistores | Um transistor e um capacitor |
| Refresh periódico | Não exigido para retenção normal da célula | Exigido |
| Mecanismo de leitura | Detecção diferencial preservando o estado | Compartilhamento de carga, detecção e restauração |
| Papel arquitetural típico | Arrays pequenos e rápidos no chip, incluindo caches | Memória principal de grande capacidade |
| Não volátil | Não | Não |

Esses são modelos convencionais, não uma afirmação de que todo array de processador ou produto de memória possui exatamente essas células. Variantes negociam densidade, portas, estabilidade de leitura, fabricação e energia. Os conceitos arquiteturais continuam úteis sem pressupor a implementação de um fabricante específico.

## Linhas, colunas e estado dos bancos

Um acesso DRAM depende do estado atual do banco relevante. Uma ativação disponibiliza uma linha aos amplificadores. Operações de coluna selecionam partes dessa linha ativa. Antes de ativar outra linha no mesmo banco, é necessário fechar a anterior e preparar as linhas de bit, respeitando as restrições temporais do protocolo. Uma solicitação dirigida à linha já ativa pode, assim, ter custo diferente de outra que exige troca de linha.

Um banco não é um processo do sistema operacional, e uma linha não é uma página de memória virtual. O controlador mapeia bits do endereço físico em canais, ranks, bancos, linhas e colunas segundo a plataforma. Bytes adjacentes possuem uma ordem definida para o software, mas o endereço visível não revela toda a geometria física. Intercalação e escalonamento do controlador podem distribuir tráfego para explorar paralelismo ou satisfazer temporização.

Essa distinção explica as várias camadas da localidade. Acessar palavras adjacentes pode aproveitar melhor linhas de cache mesmo sem conhecer o mapeamento de bancos. Tocar repetidamente um conjunto maior que o cache pode expor largura de banda e comportamento da memória principal. Um experimento com passos regulares de acesso pode revelar um padrão de desempenho, mas identificar sua causa física exata exige informações adicionais e medições controladas.

## Decodificação de endereços e seleção de palavras

Um array com `N` posições selecionáveis exige combinações suficientes para identificá-las: pelo menos `ceil(log2(N))` bits de endereço. A largura de dados de cada palavra é independente da quantidade de bits de endereço. Um array hipotético de 1.024 palavras de 32 bits armazena 32.768 bits de dados e necessita de dez bits de endereço de palavra. Uma visão endereçável por byte dos seus 4.096 bytes exige doze bits, pois os dois inferiores selecionam um byte dentro da palavra.

Esse exemplo descreve uma organização lógica, não a pinagem de um chip. Uma interface DRAM pode multiplexar partes do endereço em comandos diferentes. Um cache armazena também tags e estado, portanto seu número físico de bits excede a capacidade de dados anunciada. Metadados de correção de erros e redundância podem acrescentar armazenamento. Capacidade, largura do barramento e número de pinos não são grandezas intercambiáveis em um cálculo.

![Camadas de memória e suas diferentes unidades](../../assets/diagrams/memory-cells.svg)

## O significado de uma leitura ou escrita em C

Um ponteiro C denota um endereço segundo a implementação da linguagem e o ambiente de execução. Uma leitura pode ser atendida pelo cache, sem acesso a uma linha DRAM. Uma escrita pode atualizar uma linha de cache e tornar-se visível a outros observadores conforme o modelo de memória e os atributos do mapeamento. Memória de dispositivos pode obedecer a regras diferentes da RAM comum. A tecnologia física das células não especifica, sozinha, essas garantias arquiteturais de ordenação.

Coerência diz respeito ao acordo entre cópias em cache de uma posição. Ordenação diz respeito às relações entre acessos nas quais os observadores podem confiar. Refresh diz respeito à retenção interna na DRAM. São mecanismos distintos. Acrescentar `volatile` a um ponteiro C não atualiza DRAM nem estabelece automaticamente a ordem necessária para transferir propriedade a um dispositivo. Os capítulos de atomics, MMIO e DMA precisam explicar esses contratos superiores explicitamente.

Uma alocação não inicializada é outro problema separado. O controlador pode preservar os bits perfeitamente enquanto o alocador entrega conteúdos antigos de um proprietário anterior. Inicializar é uma obrigação de fluxo de informação no software; reter é uma propriedade física. Proteção de memória determina quem pode endereçar uma região, não se seus bytes possuem valores iniciais adequados.

## Frames físicos em `pmm.c`

O ChrisOS representa disponibilidade de alocação com `pmm_bitmap` em `kernel/metal/pmm.c`. Um endereço físico é convertido em número de página pela divisão por `PMM_PAGE`; esse número seleciona um byte do bitmap por divisão por oito e um bit pelo resto módulo oito. `bitmap_is_used` testa esse bit, enquanto os auxiliares de marcação e liberação o modificam. Um bit descreve o estado de alocação de um frame inteiro. Não é um mapa do valor elétrico de cada bit da memória.

Para `N` frames gerenciados, o bitmap custa aproximadamente `N/8` bytes. Com frames de 4 KiB, um byte de bitmap descreve 32 KiB de capacidade. Como exemplo didático, 1 GiB dividido em frames de 4 KiB contém 262.144 frames e exige 32.768 bytes de bitmap. A faixa efetivamente gerenciada depende das constantes do projeto; o exemplo deriva o custo da representação, sem afirmar uma quantidade particular de RAM instalada.

`pmm_init` começa marcando o bitmap como ocupado. Em seguida, libera frames completos nas faixas do mapa de boot classificadas como utilizáveis e reserva regiões da plataforma, bootloader, executável e framebuffer tratadas pelo código. Começar pelo estado indisponível é conservador: uma faixa ausente do mapa utilizável não é silenciosamente entregue à alocação. Reservar o framebuffer demonstra também por que o espaço de endereços físicos não pode ser identificado com um único conjunto homogêneo de RAM comum.

## Alinhamento e faixas parciais

O auxiliar de faixas utilizáveis arredonda o início para cima e o fim para baixo nos limites de página. Somente frames completos, inteiramente contidos na região utilizável, são liberados. Inversamente, o auxiliar de reserva arredonda para fora, mantendo indisponível qualquer frame tocado por um byte reservado. As direções são deliberadamente assimétricas.

Para páginas hipotéticas de 4 KiB, o intervalo utilizável de `0x1800` até `0x4800`, exclusivo, contém frames completos iniciados em `0x2000` e `0x3000`. O frame parcial em `0x1000` e o parcial em `0x4000` não podem ser liberados apenas com base nesse intervalo. Uma reserva de um único byte impede entregar o frame inteiro a outro proprietário. A unidade do algoritmo é uma granularidade de propriedade, não uma fronteira de linha DRAM.

Bitmap e contadores são metadados compartilhados. A implementação possui `pmm_enter` e `pmm_leave`, spinlock, profundidade de aninhamento por CPU e flags de interrupção salvas. Os comentários explicam a recursão na mesma CPU durante um callback de faixa livre e a necessidade de impedir reentrada por interrupção. Isso controla concorrência de software sobre metadados de alocação. Não bloqueia células elétricas nem impede o controlador de atender acessos independentes.

## Um buffer gráfico acima do alocador de frames

`gfx_init` obtém seu backbuffer de `kmalloc`, usando um tamanho em bytes derivado de largura, altura e pixels de quatro bytes. Heap e memória física estabelecem a propriedade do armazenamento abaixo dessa solicitação. O código gráfico interpreta os bytes retornados como um array de pixels `uint32_t`. O mesmo armazenamento participa, portanto, de várias descrições: células no dispositivo, endereços na arquitetura, frames no alocador, alocações no heap e pixels nos gráficos.

São descrições compatíveis, com invariantes diferentes. O alocador não pode entregar a mesma alocação viva a dois proprietários independentes. O código gráfico precisa permanecer dentro da região e distinguir largura de pitch. O caminho de exibição precisa interpretar a cor corretamente. O sucesso em uma camada não elimina as obrigações das outras. Um bitmap PMM correto não impede que uma função gráfica calcule um deslocamento fora dos limites.

## A RAM do ChrisVM é uma alocação do hospedeiro

`chris_machine_create`, em `chrisvm/machine/machine.c`, aloca RAM convidada com `calloc`, registra seu tamanho e conecta dispositivos antes de criar a CPU. A configuração rejeita tamanho inferior a 2 MiB ou que não seja múltiplo de 2 MiB. Essas verificações são propriedades do modelo atual da máquina; não significam que células DRAM físicas existem em unidades de 2 MiB.

Na criação, `calloc` fornece armazenamento zerado no hospedeiro. Acessos físicos convidados passam pelas funções da máquina; acessos virtuais acrescentam tradução de endereços do convidado. O sistema operacional e o hardware do hospedeiro continuam determinando o respaldo físico da alocação. Um endereço físico convidado não é, portanto, um endereço físico hospedeiro e não pode ser convertido com segurança em ponteiro hospedeiro sem tradução e verificação de limites do emulador.

O destrutor encerra o backend da CPU e libera seu armazenamento, o framebuffer, a RAM e a máquina. Caminhos de criação parcial liberam alocações anteriores antes de retornar falha. Isso estabelece uma fronteira concreta de ciclo de vida. Não emula refresh DRAM, temporização de linhas ou falhas de retenção. Semântica funcional de RAM e modelo físico temporal são níveis distintos de simulação.

## Falhas, segurança e validação

A memória física pode sofrer falhas de retenção, sinalização ou células. Sistemas de correção de erros podem detectar ou corrigir certas classes conforme seu código e política de hardware. O software também pode corromper memória saudável por ponteiros obsoletos, comprimentos incorretos ou corridas. Um pixel corrompido, isoladamente, não identifica a camada que falhou. O diagnóstico exige evidências que delimitem a fronteira: teste de segurança de memória no hospedeiro, invariantes do alocador, logs, diagnóstico de dispositivos ou notificações de erro de hardware.

Os caminhos revisados estabelecem representações e ordem do ciclo de vida, não confiabilidade exaustiva. Reproduzir a aritmética do bitmap verifica o modelo de metadados; testar fronteiras verifica arredondamento; provocar falha de alocação verifica limpeza; comparar leituras e escritas convidadas verifica armazenamento funcional. Nenhum desses procedimentos é um teste físico de retenção DRAM. Da mesma forma, uma alocação grande bem-sucedida não comprova que todas as células físicas foram exercitadas ou que o emulador representa falhas do hardware.

Os próximos assuntos arquiteturais são caches e ordenação; os próximos assuntos de sistema operacional são alocação física e tradução virtual. Devem ser lidos como contratos adicionais acima dessas células. A evidência atual está limitada aos arquivos e à revisão declarados, mantendo a organização elétrica específica da plataforma fora das afirmações sobre o ChrisOS.
