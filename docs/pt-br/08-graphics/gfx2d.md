---
id: gfx2d
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/gfx2d.h
  - kernel/gfx/gfx2d.c
  - kernel/gfx/gfx_fast.h
  - kernel/gfx/gfx_fast.c
  - kernel/gfx/zbuf.h
  - kernel/gfx/zbuf.c
  - kernel/gfx/tile.h
  - kernel/gfx/tile.c
  - tools/test_gfx2d.c
symbols:
  - gfx2d_palette
  - gfx2d_color
  - gfx2d_clear
  - gfx2d_put
  - gfx2d_fill
  - gfx2d_line
  - gfx2d_sprite
  - gfx2d_tilemap
  - gfx2d_layer
  - gfx_fast_fill_u32
  - tile_parallel_clear
depends_on:
  - pixels-framebuffer
  - color-formats
  - algorithmic-complexity
related:
  - desktop-compositor
  - software-3d
  - parallel-raster
---

# Primitivas 2D e composição

## Escopo

kernel/gfx/gfx2d.c implementa uma camada compacta de renderização 2D por software usada por experimentos e workloads de teste do ChrisOS.

As operações públicas cobrem:

- consulta de paleta indexada;
- escrita de pixels;
- clear da superfície inteira;
- retângulos preenchidos;
- rasterização inteira de linhas;
- sprites indexados com transparência por color key;
- tilemaps com layout fixo de atlas;
- cópia de layers usando uma janela de câmera.

A implementação opera sobre buffers uint32_t pertencentes ao chamador, em vez da abstração global GfxFramebuffer de graphics.c.

A distinção importa: gfx2d é principalmente uma biblioteca de renderização sobre memória; graphics.c é responsável pelo caminho de backbuffer/frontbuffer e apresentação.

## Modelo de superfície

A maior parte das funções gfx2d recebe:

    uint32_t *pixels
    int width
    int height

O layout esperado é row-major sem padding:

    index = y * width + x

Não existe argumento de pitch.

Assim, cada linha lógica começa imediatamente depois da linha anterior.

Um framebuffer de hardware com padding entre linhas não deve ser passado diretamente, a menos que seu pitch físico seja exatamente width * 4 bytes.

O padrão natural é renderizar em uma superfície de software compacta e usar posteriormente uma camada de apresentação ou conversão quando necessário.

## Paleta fixa de 16 cores

gfx2d define uma paleta de 16 entradas inspirada em interfaces tradicionais de baixa profundidade de cor.

Cada entrada é RGB de 24 bits armazenado em uint32_t.

gfx2d_color converte um índice inteiro no RGB correspondente.

Índice inválido retorna a entrada zero.

Funções de desenho que recebem índice normalmente rejeitam valores inválidos em vez de fazer clamp silencioso.

Assim, a API possui dois comportamentos distintos:

- lookup pode fornecer fallback;
- mutação pode rejeitar a solicitação.

Essa diferença aparece nos testes unitários.

## Limite geométrico

area_ok protege operações cujas dimensões podem criar loops aninhados grandes.

Ela rejeita:

- largura ou altura não positivas;
- qualquer dimensão acima de 4096;
- área acima de 4096 * 4096.

A multiplicação é promovida explicitamente para int64_t antes da comparação.

Isso evita overflow signed de 32 bits dentro da própria verificação de área.

O limite é uma proteção algorítmica e de robustez; não significa que toda superfície de destino possa realmente ter 4096 por 4096.

As dimensões do destino são fornecidas separadamente e o clipping determina as escritas visíveis.

## Operação de um pixel

gfx2d_put realiza a escrita indexada básica com clipping.

Ela verifica:

- ponteiro de destino;
- dimensões positivas;
- x e y dentro da superfície;
- índice de cor dentro da paleta.

Só então grava:

    pixels[y * w + x] = palette[color]

Coordenadas fora da superfície são simplesmente ignoradas.

Isso torna gfx2d_put uma primitiva segura conveniente para algoritmos como linhas e sprites.

A contrapartida é repetir testes de bounds e paleta para cada pixel.

Rotinas de nível superior às vezes escrevem diretamente quando já garantiram o clipping.

## Clear da superfície

gfx2d_clear valida superfície e índice de paleta, resolve o valor RGB e limpa cada linha.

Em builds normais usa gfx_fast_fill_u32 por linha.

gfx_fast_fill_u32 replica a cor de 32 bits em registrador SSE2 e grava quatro pixels por vez com stores de 128 bits, seguido por loop escalar para o restante.

O clear separa, assim, a geometria da operação do kernel vetorizado de preenchimento.

Depois de limpar o color buffer, gfx2d_clear também redefine as dimensões do z-buffer global e limpa o depth buffer.

Esse é um efeito colateral importante entre subsistemas: um clear 2D também estabelece o estado de profundidade para renderização 3D posterior.

## Caminho paralelo de clear

Em build freestanding, uma superfície suficientemente grande pode usar outro caminho.

A condição é:

    width * height >= 512 * 512
    e pelo menos duas CPUs online

Nesse caso gfx2d_clear chama tile_parallel_clear.

tile_parallel_clear divide a superfície em tiles de 64 por 64.

Cada tile vira um job contendo:

- ponteiro de destino;
- geometria total;
- coordenadas do tile;
- cor.

Workers preenchem regiões retangulares independentes usando gfx_fast_fill_u32.

Como tiles não se sobrepõem, as stores de cor não exigem lock por pixel.

A função aguarda o sistema de jobs ficar idle antes de retornar, portanto o clear possui semântica de conclusão para o chamador.

## Batching da fila de jobs

tile_parallel_clear usa um array estático de TileClearArg dimensionado por JOB_QUEUE_CAP.

Quando todos os slots de argumentos são usados, a função espera o job system ficar idle e volta a reutilizar o array desde o slot zero.

Isso evita sobrescrever uma estrutura de argumento que ainda pode estar sendo lida por um worker.

Ao final ocorre nova espera para o lote restante.

O algoritmo limita metadados temporários sem alocar um objeto por tile.

## Limitações do clear paralelo

O caminho paralelo depende de estado global do scheduler/job system e de cpu_online_count.

Ele existe apenas em builds freestanding.

Os testes host dedicados de gfx2d não exercitam esse caminho.

A correção depende de job_wait_idle funcionar como barreira de conclusão dos jobs enviados.

Os tiles são disjuntos, mas a superfície ainda não deve ser modificada simultaneamente por renderizadores independentes, a menos que uma regra de ownership de nível superior permita.

O buffer estático de argumentos também significa que duas chamadas simultâneas a tile_parallel_clear compartilhariam armazenamento e não seriam reentrantes entre si.

## Retângulos preenchidos

gfx2d_fill recebe origem, largura/altura do retângulo e índice de paleta.

Primeiro valida área e cor.

Depois calcula:

    x0 = x
    y0 = y
    x1 = x + rw
    y1 = y + rh

e recorta as extremidades ao destino.

Somente a interseção visível é escrita.

Os loops aninhados visitam cada pixel restante.

Para um retângulo visível de largura W e altura H, a complexidade é O(W * H).

O custo adicional de memória é O(1).

## Comportamento de clipping

Origens negativas são permitidas.

Por exemplo, um retângulo iniciado em (-2,-2) com tamanho 4 por 4 é recortado ao canto visível 2 por 2.

tools/test_gfx2d.c verifica esse caso.

O clipping evita out-of-bounds comuns.

Como em muitas APIs geométricas C, coordenadas signed extremas ainda podem provocar overflow em expressões como x + rw antes do clipping.

Os chamadores atuais são esperados como código controlado pelo projeto e com coordenadas limitadas.

## Rasterização de linhas

gfx2d_line implementa algoritmo incremental inteiro equivalente à família simétrica de Bresenham.

Ele calcula:

- dx e dy absolutos;
- direções de passo em x e y;
- termo acumulado de erro.

Em cada iteração chama gfx2d_put e atualiza x e/ou y com base no dobro do erro.

Não usa ponto flutuante.

O mesmo state machine cobre linhas horizontais, verticais, diagonais e inclinações gerais.

## Complexidade da linha

Para extremos (x0,y0) e (x1,y1), o número de iterações é proporcional a:

    max(abs(x1 - x0), abs(y1 - y0))

Logo a complexidade é O(max(dx,dy)) e a memória auxiliar O(1).

Como cada passo chama gfx2d_put, partes fora da tela ainda são calculadas e depois descartadas pelo clipping por pixel.

Para linhas muito longas quase inteiramente fora da tela, um algoritmo de line clipping anterior reduziria trabalho desnecessário.

## Representação de sprites

gfx2d_sprite usa origem indexada de 8 bits.

A origem é row-major, com dimensões sw por sh.

Cada byte representa índice da paleta.

Se o índice for igual a key, o destino não é alterado.

Caso contrário chama gfx2d_put.

Isso combina:

- conversão da paleta;
- clipping do destino;
- transparência por color key.

key pode ser -1 para efetivamente desativar transparência, porque índices uint8_t ficam entre 0 e 255 e não se tornam -1 quando promovidos para int.

## Complexidade de sprites

O sprite percorre sempre sw * sh células depois da validação.

A complexidade é O(sw * sh), mesmo se o sprite estiver quase totalmente fora da superfície.

O clipping por pixel mantém as escritas seguras, mas não elimina linhas ou colunas invisíveis em nível mais alto.

Uma versão otimizada poderia calcular uma interseção visível uma vez e iterar somente sobre a parte relevante da origem.

A forma atual prioriza simplicidade.

## Layout binário do tilemap

gfx2d_tilemap espera um único buffer compacto.

O começo contém atlas de exatamente 16 tiles:

    atlas_bytes = 16 * tile_width * tile_height

Logo depois aparece o mapa:

    map_bytes = map_width * map_height

Cada byte do mapa seleciona um dos 16 tiles.

Não existe estrutura separada com offsets; o layout é derivado das dimensões.

É um formato pequeno e fixo, não um parser genérico de arquivos de mapas.

## Restrições do tilemap

A função rejeita:

- ponteiros nulos;
- dimensões não positivas;
- mapas acima de 512 por 512;
- tiles acima de 256 por 256;
- área de tile rejeitada por area_ok.

Atlas e mapa são calculados como int.

Com os caps explícitos, os produtos esperados permanecem na faixa usual de signed int.

Cada célula válida seleciona a origem do tile e chama gfx2d_sprite.

Valores de tile acima do limite de 16 entradas são ignorados.

## Complexidade do tilemap

Para M = mapw * maph células e T = tw * th pixels por tile, o custo direto é:

    O(M * T)

porque cada célula chama um scan completo do sprite.

Não existe culling de viewport antes da escolha dos tiles.

Portanto um mapa grande renderizado com offset continua percorrendo tiles que podem terminar inteiramente fora da tela.

Uma versão camera-aware poderia calcular primeiro quais coordenadas de tiles intersectam a viewport.

## Operação de layer

gfx2d_layer copia uma visão determinada pela câmera de uma superfície uint32_t de origem para um destino.

Para cada coordenada do destino:

    source_x = x + camx
    source_y = y + camy

Coordenadas fora da origem são ignoradas.

Depois o byte superior do pixel é examinado.

Se for zero, o pixel é transparente.

Se for diferente de zero, a word de 32 bits inteira substitui o destino.

Isso é gating binário de alfa, não blend de alfa parcial.

## Complexidade do layer

A função percorre todos os pixels do destino:

    O(destination_width * destination_height)

O offset de câmera muda apenas os endereços de origem, não os bounds do loop.

Para viewports pequenas sobre mundos maiores, o custo é previsível.

Para layers esparsos, estruturas com runs, dirty rectangles ou tiles poderiam reduzir o trabalho, ao custo de metadados e complexidade adicional.

## Diferença entre gfx2d e graphics.c

gfx2d e a camada gráfica geral possuem capacidades sobrepostas, mas contratos diferentes.

gfx2d:

- desenha em buffers compactos fornecidos pelo chamador;
- frequentemente recebe índices de paleta;
- expõe linhas, sprites, tilemaps e layers;
- não mantém dirty rectangles de apresentação.

graphics.c:

- possui par global backbuffer/frontbuffer;
- recebe cores RGB cruas;
- rastreia regiões alteradas;
- implementa scaling, blend RGBA, texto e apresentação.

Um chamador pode combinar ambas, mas não deve assumir automaticamente que compartilham pitch, alfa ou ownership.

## Preenchimento acelerado

gfx_fast_fill_u32 replica a cor de 32 bits em registrador SSE2 e grava quatro pixels por iteração com _mm_storeu_si128.

O loop final trata de um a três pixels restantes.

Como usa store unaligned, o destino não precisa ter alinhamento de 16 bytes.

Entretanto, o ambiente precisa ter estado SSE2 habilitado.

O caminho de inicialização geral do ChrisOS habilita SSE antes de depender das rotinas gráficas rápidas.

## Acoplamento ao z-buffer

gfx2d_clear chama:

    zbuf_set_size(w, h)
    zbuf_clear()

O z-buffer armazena um uint32_t de profundidade por célula.

ZBUF_FAR é 0xFFFFFFFF.

zbuf_test aceita nova profundidade apenas quando:

    new_z < stored_z

e atualiza o valor armazenado.

Assim, um clear de cor também reinicializa os testes de profundidade.

Esse acoplamento faz sentido em um software renderer orientado a frames, mas significa que gfx2d_clear não é puramente operação de color buffer.

Uma futura separação entre superfícies 2D e 3D pode mover esse reset para uma API explícita de frame.

## Capacidade estática do z-buffer

O z-buffer interno estático possui 1024 por 768.

zbuf_set_size permite tamanhos lógicos até 1920 por 1080, porém se o buffer ativo ainda for o array estático e as dimensões excederem sua capacidade, o ponteiro global do z-buffer vira nulo.

Um depth buffer externo pode ser instalado com zbuf_bind.

Quando o ponteiro está nulo, zbuf_clear vira no-op e zbuf_test rejeita todos os samples.

Isso é uma limitação importante quando um gfx2d_clear de alta resolução é seguido por software 3D sem um depth buffer externo previamente associado.

## Ownership e reentrância

A maioria das rotinas gfx2d não aloca memória.

Elas modificam buffers pertencentes ao chamador.

Isso simplifica ownership da superfície de cor.

Entretanto, o subsistema também toca estado global/compartilhado:

- z-buffer global;
- cpu_online_count na escolha do clear paralelo;
- fila global de jobs;
- armazenamento estático dos argumentos dos tiles.

Logo a API não pode ser descrita como globalmente reentrante apenas porque quase todas as funções recebem ponteiro de destino explícito.

Fills simples em buffers diferentes podem ser mecanicamente independentes, mas o efeito colateral de clear sobre profundidade e o caminho paralelo introduzem estado compartilhado.

## Evidência de validação

tools/test_gfx2d.c fornece evidência host para o caminho escalar principal.

Ele verifica:

- clear completo para índice de paleta 1;
- pixel writes com clipping;
- rejeição de índice de paleta inválido;
- retângulos preenchidos;
- clipping parcial de retângulo fora da tela;
- linhas horizontais;
- linhas diagonais;
- transparência keyed de sprite;
- endereçamento do atlas de tilemap.

O teste compara valores exatos do framebuffer, e não apenas return codes.

Isso oferece boa evidência para os algoritmos e mapeamentos de paleta exercitados.

## Lacunas de validação

O teste dedicado atual não cobre diretamente:

- gfx2d_layer;
- rejeição de geometrias máximas;
- clear paralelo;
- batching do job system;
- efeitos no z-buffer;
- todos os octantes de linhas;
- clipping de tilemap com offsets grandes;
- uso concorrente.

Esses são alvos apropriados para expansão futura de testes.

A documentação não deve sugerir que estejam cobertos apenas porque as funções existem.

## Comportamento de falhas

A maior parte das APIs gfx2d retorna void.

Entradas inválidas normalmente produzem retorno antecipado sem diagnóstico.

Exemplos:

- superfície nula;
- geometria inválida;
- índice de cor inválido;
- dimensões inválidas de tile;
- coordenadas fora do range.

Esse estilo facilita compor chamadas de desenho, mas perde informação sobre por que nada foi desenhado.

Para call sites internos e confiáveis pode ser aceitável.

Para ABI de aplicações ou API focada em debug, erros estruturados ou contadores de validação melhorariam a observabilidade.

## Características de desempenho

Os custos dominantes são proporcionais aos pixels visitados.

- put: O(1);
- fill: O(área visível);
- line: O(max(dx,dy));
- sprite: O(sw * sh);
- tilemap: O(células * pixels por tile);
- layer: O(área do destino);
- clear: O(w * h), com execução paralela opcional.

O layout row-major contíguo favorece localidade de cache em fills e scans horizontais.

Sprites e tilemaps também acessam sequencialmente as linhas da origem dentro de cada tile.

Layer percorre origem e destino em sequência quando as coordenadas da câmera estão válidas.

## Limitações atuais

As principais fronteiras incluem:

- paleta indexada fixa de 16 cores;
- superfícies de destino obrigatoriamente compactas;
- ausência de pitch;
- formas vetoriais limitadas a linhas e retângulos;
- ausência de clipping geométrico prévio das linhas;
- ausência de coarse clipping de sprites;
- ausência de viewport culling no tilemap;
- atlas limitado a 16 tiles;
- alfa binário no layer;
- efeito colateral global no z-buffer durante clear;
- armazenamento estático para argumentos de jobs;
- clear paralelo sem cobertura no teste host dedicado;
- ausência de contrato explícito de thread safety;
- APIs void com diagnósticos limitados.

As restrições são coerentes com um renderer experimental compacto.

## Limite entre estado atual e roadmap

Uma evolução do subsistema pode adicionar:

- surface descriptors com pitch e formato;
- culling de sprites e tiles pela viewport;
- atlas de tamanho variável;
- algoritmos de line clipping;
- composição de layer com alfa parcial;
- sprites transformados;
- dirty tracking por superfície;
- APIs explícitas de reset de frame/depth;
- contextos por operação no lugar de estado compartilhado;
- kernels SIMD para sprite/layer;
- testes de propriedades e fuzzing de clipping.

Nada disso deve ser confundido com o comportamento atual.

## Proveniência da revisão

Este capítulo documenta o caminho 2D conforme observado no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

As fontes principais são kernel/gfx/gfx2d.c e gfx2d.h. gfx_fast.c define a primitiva SIMD de preenchimento, tile.c define o clear paralelo freestanding, zbuf.c define o efeito colateral no depth buffer e tools/test_gfx2d.c fornece evidência executável para o contrato escalar de renderização.
