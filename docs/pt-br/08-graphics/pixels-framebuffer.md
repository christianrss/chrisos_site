---
id: pixels-framebuffer
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/gfx/graphics.c
- kernel/gfx/graphics.h
- kernel/gfx/gfx_fast.c
- kernel/metal/start.c
- tools/test_graphics_present.c
symbols:
- gfx_init
- gfx_rgb
- gfx_put_pixel
- gfx_mark_dirty
- gfx_present
- kstart
depends_on:
- data-representation-layout
- buses-mmio-dma
- heap-ownership
related:
- software-3d
- virtio-gpu-virgl
---

# Pixels, memória de framebuffer e apresentação

## Escopo e pré-requisitos

Este capítulo acompanha o caminho concreto do framebuffer em `kernel/gfx/graphics.c` e seu primeiro chamador, `kstart`, em `kernel/metal/start.c`. Explica como uma cor inteira se transforma em uma atualização de memória, como uma coordenada bidimensional se transforma em endereço, por que o rastreamento de regiões alteradas participa da correção e o que a apresentação garante ou não. Pressupõe inteiros binários, ponteiros, layout de arrays, endereços físicos e virtuais e alocação no heap. Os pré-requisitos estão vinculados acima; os exemplos matemáticos abaixo explicitam os cálculos de coordenadas.

Um pixel é uma amostra discreta de uma imagem. Uma tela física contém elementos que emitem ou modulam luz, enquanto o software manipula um valor de cor codificado. Um framebuffer é a representação em memória utilizada em um caminho de exibição. Uma escrita de software não controla diretamente um transistor do painel: altera a memória, após o que um controlador de vídeo ou dispositivo virtual transporta dados da imagem até a varredura de saída, denominada scanout. A distinção importa no diagnóstico de uma tela preta. Renderização correta, mapeamento válido, apresentação pelo dispositivo e saída ativa são condições separadas.

## Da carga elétrica à imagem observável

A base física forma uma sequência de interfaces. Dispositivos semicondutores implementam chaveamento e armazenamento de estado. Registradores mantêm operandos e endereços. Uma instrução calcula um valor ou solicita uma operação de memória. A tradução de endereços seleciona o destino físico de um endereço virtual; caches e o subsistema de memória realizam a transferência segundo as regras do tipo de memória. O hardware de vídeo finalmente lê a imagem e aciona uma saída. Nenhuma dessas camadas pode ser deduzida apenas da existência de um ponteiro C não nulo.

Em um emulador, o mesmo contrato visível pelo convidado pode ser implementado com memória do hospedeiro e uma janela de exibição. O pixel do convidado não sabe se seu destino é memória de vídeo física ou um recurso modelado. Inversamente, código C idêntico não comprova atributos de cache, temporização ou sincronização idênticos em dois backends. O ChrisOS precisa, portanto, de evidências separadas para o algoritmo do framebuffer e para o caminho do dispositivo que consome sua saída.

![Propriedade dos buffers e apresentação](../../assets/diagrams/pixel-memory.svg)

## A cor é um contrato sobre inteiros

`gfx_rgb` desloca vermelho para os bits 23–16, verde para 15–8 e azul para 7–0. O resultado é `0x00RRGGBB`; o byte superior é zero. Para vermelho `0x12`, verde `0x34` e azul `0x56`, o inteiro é `0x00123456`. Em x86 little-endian, endereços crescentes contêm os bytes `56 34 12 00`. A nomenclatura dos canais no inteiro e a ordem dos bytes descrevem aspectos diferentes do mesmo armazenamento. Chamar esses bytes de “RGBA” sem definir a convenção descreveria incorretamente sua ordem.

| Bits | Significado em `gfx_rgb` | Valor do exemplo |
|---|---|---|
| 31–24 | Zero; não é uma opacidade fornecida por `gfx_rgb` | `00` |
| 23–16 | Vermelho | `12` |
| 15–8 | Verde | `34` |
| 7–0 | Azul | `56` |

`gfx_blit_rgba` possui outro contrato de entrada, documentado em `graphics.h`: os pixels de origem são `0xAARRGGBB`. A função ignora alfa zero, copia RGB diretamente para alfa 255 e mistura valores intermediários com o destino atual. Por canal, o cálculo inteiro é `(origem * alfa + destino * (255-alfa)) / 255`, com truncamento. Trata-se de aritmética com alfa não pré-multiplicado nos valores armazenados dos canais. A função não estabelece uma composição em luz linear com gerenciamento de cor, nem preserva um canal alfa composto no destino. Essas diferenças afetam bordas translúcidas mesmo quando os endereços estão corretos.

## Dois arrays com passos de linha diferentes

`GfxFramebuffer` contém `front`, `back`, `width`, `height` e `pitch_pixels`. O ponteiro frontal é fornecido pelo chamador. O ponteiro traseiro identifica uma alocação separada, pertencente à implementação gráfica. Uma imagem lógica contém `width * height` pixels ativos, mas o buffer frontal pode incluir bytes sem uso entre as linhas. Essa separação explica por que a estrutura registra o pitch independentemente da largura.

Para um pixel de quatro bytes na coordenada `(x,y)`, os deslocamentos em bytes são:

```text
back_offset  = 4 * (y * width + x)
front_offset = y * pitch_bytes + 4 * x
pitch_pixels = pitch_bytes / 4
```

Considere largura 4, altura 3 e pitch de 24 bytes, como no teste no hospedeiro. O backbuffer utiliza 16 bytes por linha e 48 bytes no total. Cada linha frontal ocupa 24 bytes: quatro pixels ativos e dois pixels de preenchimento. O pixel `(1,1)` fica no deslocamento 20 no backbuffer e 28 no frontal. Copiar os 12 pixels ativos como uma única região contígua sobrescreveria o preenchimento e posicionaria as linhas seguintes incorretamente. `gfx_present` evita isso copiando separadamente cada linha alterada.

| Coordenada | Índice no backbuffer | Índice no frontal | Interpretação |
|---|---:|---:|---|
| `(0,0)` | 0 | 0 | Primeiro pixel ativo |
| `(3,0)` | 3 | 3 | Último pixel ativo da linha zero |
| `(0,1)` | 4 | 6 | O preenchimento existe apenas no caminho frontal |
| `(1,1)` | 5 | 7 | Mesma coordenada, índice diferente |
| `(3,2)` | 11 | 15 | Último pixel ativo da imagem |

O domínio válido é `0 <= x < width` e `0 <= y < height`. Limites superiores exclusivos fazem a largura coincidir com o número de colunas válidas. Um retângulo `[x0,x1) × [y0,y1)` contém, assim, `(x1-x0)*(y1-y0)` pixels e pode ser vazio sem uma convenção especial de coordenadas.

## Inicialização e propriedade da memória

`gfx_init` rejeita endereço nulo, dimensões não positivas, dimensões acima de `GFX_MAX_WIDTH` ou `GFX_MAX_HEIGHT`, pitch menor que uma linha e pitch não divisível por quatro. O cabeçalho limita as dimensões a 1920 por 1080. Essas verificações validam a geometria esperada pela implementação; não comprovam que o ponteiro abrange um mapeamento gravável do tamanho necessário nem que o dispositivo utiliza as máscaras de cor esperadas.

A função libera um backbuffer privado existente e aloca uma região de `width * height * sizeof(uint32_t)` com `kmalloc`. Quando a alocação funciona, instala os ponteiros e a geometria, zera a contagem de regiões alteradas e marca toda a imagem. Essa marcação inicial não inicializa os valores dos pixels. `kstart` limpa a imagem antes de apresentá-la, preenchendo o backbuffer recém-alocado.

Há uma distinção importante na falha de reinicialização. A alocação antiga é liberada antes da obtenção da nova. Se a nova alocação falhar, a função retorna falso sem restaurar o estado anterior; `g_gfx.back` pode continuar contendo o endereço liberado. No chamador de boot, a falha leva a `panic`, portanto não há continuação do desenho. Um futuro chamador de troca de modo em execução não pode pressupor reversão transacional. Essa observação decorre da ordem do código; esta alteração da documentação não corrige o comportamento do kernel.

## A primeira apresentação em `kstart`

O caminho de inicialização prepara memória física, memória virtual e heap antes de solicitar armazenamento gráfico. Também inicializa o suporte SSE do processador de bootstrap antes da limpeza e cópia gráficas. Depois de obter as informações de boot, verifica `fb_bpp == 32` e chama `gfx_init` com endereço, largura, altura e pitch em bytes. A rejeição provoca um panic. Em seguida, chama `virtio_gpu_boot`, descarta seu retorno, limpa a imagem com `0x00101828` e a apresenta.

Essa sequência estabelece uma fronteira útil de diagnóstico: um fundo visível depende do caminho básico de alocação e apresentação, mas não comprova que desktop, entrada, compilador da linguagem, sistema de arquivos ou rede estejam prontos. Esses componentes possuem inicialização separada mais adiante. A operação gráfica inicial ocorre antes da inicialização SMP subsequente, mas essa ordem não estabelece, por si só, uma política geral de concorrência para toda a renderização posterior.

## Escrita de pixels e recorte

`put_pixel_raw` retorna sem escrever se o backbuffer não existe ou a coordenada está fora do domínio válido. Caso contrário, escreve em `back[y * width + x]`. `gfx_put_pixel` chama esse auxiliar e marca um retângulo de um pixel. O recorte de regiões alteradas descarta retângulos sem interseção com a tela, portanto um pixel comum fora da tela não cria uma entrada válida de alteração.

`gfx_fill_rect` recorta um retângulo à área visível e preenche cada linha restante com `gfx_fast_fill_u32`. O trabalho cresce com o número de pixels escritos. Diferentemente do auxiliar de pixel, essa rotina não protege independentemente todos os estados de inicialização inválida. Os chamadores precisam respeitar a inicialização bem-sucedida. Além disso, expressões como `x + width` são cálculos inteiros com sinal. Entradas extremas não confiáveis podem provocar overflow antes do recorte. Recortar na tela não substitui validar os intervalos de argumentos de uma ABI externa.

## Rastreamento de alterações como algoritmo

Uma região alterada indica que o backbuffer difere do conteúdo apresentado anteriormente em uma área que precisa ser copiada. O ChrisOS armazena até 32 registros `GfxDirtyRect` em um array estático. Cada registro possui quatro extremidades inteiras. A contagem determina quais estão ativos; não existe alocação dinâmica por atualização.

`gfx_mark_dirty` rejeita extensões não positivas, calcula a extremidade distante, recorta na tela e rejeita um resultado vazio. Depois percorre o array buscando retângulos que se tocam. Ao encontrar um, substitui o candidato pelo retângulo delimitador das duas regiões, remove o registro antigo movendo o último para sua posição, reduz a contagem e reinicia a varredura no índice zero. Reiniciar é necessário porque a expansão pode fazer o candidato tocar um retângulo examinado antes da união.

A operação usa uma caixa delimitadora, não a união exata dos pixels cobertos. Duas regiões adjacentes por borda ou diagonal podem fazer pixels inalterados dentro da caixa serem copiados. Isso é conservador: copiar em excesso desperdiça largura de banda, mas deixar de copiar um pixel alterado mantém uma imagem obsoleta. A implementação considera fronteiras compartilhadas como contato porque `rects_touch` usa comparações inclusivas entre as extremidades exclusivas.

Com `D` retângulos armazenados, uma chamada pode exigir trabalho quadrático de comparação no pior caso, pois cada união pode reiniciar a varredura. Aqui `D` é limitado a 32, restringindo o custo dos metadados. Quando um novo retângulo disjunto excederia a capacidade, o algoritmo substitui a lista por um retângulo de tela inteira. Essa alternativa preserva a cobertura sob saturação. Troca tráfego adicional de cópia por uma estrutura fixa e um caminho simples de inserção sem falha de alocação.

## Apresentação e seus limites

Para cada retângulo alterado, `gfx_present` visita as linhas de `y0` a `y1-1`, calcula o destino com `pitch_pixels`, calcula a origem com `width` e copia `x1-x0` pixels. Em uma compilação freestanding, também forma uma caixa delimitadora de todas as alterações e chama `hw_gpu_flush_rect`. Finalmente zera a contagem. Um teste executado no hospedeiro não inclui essa operação condicional do dispositivo.

Esse caminho apresenta por cópia. Não realiza uma troca atômica de ponteiros entre buffers de scanout do hardware. Um controlador pode ler o buffer frontal durante a cópia; um backbuffer de software isoladamente não comprova ausência de tearing nem sincronização com o intervalo de apagamento vertical. Da mesma forma, a existência da chamada de flush não comprova conclusão pelo dispositivo. O código específico e seu contrato de sincronização precisam fornecer essa evidência.

Nenhum lock deste arquivo protege `g_dirty_count`, o array de retângulos ou as escritas de pixels. Escritores concorrentes, ou um escritor concorrendo com a apresentação, exigem coordenação externa. Zerar a contagem depois de uma atualização concorrente poderia perder seu registro de alteração. Seria incorreto classificar essas variáveis globais como seguras entre threads apenas porque a escrita de um pixel alinhado pode ser naturalmente atômica no processador-alvo.

## Modelo de custo e largura de banda

Uma imagem sem preenchimento de 1920 por 1080, com quatro bytes por pixel, ocupa 8.294.400 bytes, aproximadamente 7,91 MiB. Uma cópia completa a 60 apresentações por segundo transfere 497.664.000 bytes de conteúdo de imagem por segundo ao destino. A leitura da origem e a escrita do destino representam aproximadamente o dobro de bytes transferidos, antes de considerar caches, alocação de linha na escrita e transações do dispositivo. Esse é um modelo aritmético, não um benchmark medido do ChrisOS.

![Volume analítico de apresentação completa](../../assets/diagrams/framebuffer-bandwidth.svg)

Seja `A` a soma das áreas dos registros disjuntos e `R` o total de segmentos de linha cobertos. O trabalho de cópia é proporcional a `A`, com sobrecarga de chamadas e linhas proporcional a `R`. A união por caixa delimitadora pode aumentar `A`, enquanto a alternativa de tela inteira o fixa em `width*height`. Pequenas escritas dispersas podem custar mais do que sua contagem sugere. Alternativas incluem bitmap de tiles ou intervalos por linha, mas modificariam metadados, comportamento de união e laço de apresentação. A substituição precisa decorrer de cargas medidas, não da suposição de que uma estrutura mais elaborada é sempre mais rápida.

## Validação e riscos remanescentes

`tools/test_graphics_present.c` fornece implementações de `kmalloc` e `kfree` baseadas em `malloc` e `free` do hospedeiro. Verifica preservação do preenchimento, retângulo parcial, ausência de cópia quando não existem alterações, alternativa de saturação após 33 atualizações separadas e escalonamento por vizinho mais próximo. A sentinela `0xdeadbeef` no preenchimento detecta um erro de cópia contígua que uma imagem compacta esconderia.

| Evidência | Estabelece | Não estabelece |
|---|---|---|
| Teste do pitch com preenchimento | As linhas ativas respeitam o pitch fornecido | Atributos da memória no hardware |
| Teste de retângulo parcial | Vizinhos externos à região permanecem intactos | Todos os casos de recorte e overflow |
| Teste sem região alterada | Escrita direta não marcada não é apresentada | Correção das marcações em todos os chamadores |
| Teste de 33 atualizações | Saturação provoca cópia de tela inteira | Largura de banda ótima |
| Execução no hospedeiro | O caminho de software testado funciona nessa compilação | Boot convidado, conclusão GPU ou scanout físico |

A implementação possui, portanto, um contrato concreto de software e testes reproduzíveis, enquanto falha de reinicialização, coordenadas extremas externas, propriedade sob concorrência, validação de formato de cor e apresentação sem tearing continuam sendo assuntos de revisão separados. Alterações futuras precisam preservar tanto o invariante de endereçamento quanto o de cobertura das alterações. Uma inspeção apenas do código não certifica essas propriedades mais amplas do sistema.
