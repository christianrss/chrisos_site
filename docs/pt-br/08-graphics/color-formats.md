---
id: color-formats
lang: pt-br
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/graphics.h
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.h
  - kernel/gfx/gfx2d.c
  - tools/test_graphics_present.c
  - tools/test_gfx2d.c
symbols:
  - gfx_rgb
  - gfx_blit_rgba
  - gfx2d_palette
  - gfx2d_color
  - gfx2d_put
  - gfx2d_layer
depends_on:
  - pixels-framebuffer
  - data-representation-layout
related:
  - gfx2d
  - desktop-compositor
  - textures
  - software-3d
---

# Formatos de cor e alfa

## Escopo

Um valor de cor só possui significado quando seu layout de bits, interpretação de canais, premissas de transferência e convenção de alfa são conhecidos.

O ChrisOS usa atualmente vários contratos de pixels de 32 bits relacionados, porém distintos:

- cores comuns do framebuffer e da interface são inteiros 0x00RRGGBB;
- gfx_blit_rgba recebe pixels de origem 0xAARRGGBB;
- a paleta 2D armazena RGB de 24 bits dentro de words uint32_t;
- gfx2d_layer interpreta o byte superior da origem como presença/opacidade binária, mas não faz blend de alfa parcial.

Esses contratos são parecidos o suficiente para serem confundidos e diferentes o suficiente para produzirem defeitos visuais quando confundidos.

Este capítulo separa representação inteira, ordem de bytes na memória, semântica de alfa e comportamento atual do ChrisOS.

## Formato de pixel é um contrato de dados

Um inteiro de 32 bits pode representar muitas coisas.

Para gráficos, uma definição de formato precisa responder pelo menos:

- quais bits representam vermelho, verde e azul;
- se existe canal alfa;
- se o alfa é straight ou premultiplied;
- como o inteiro é armazenado na memória;
- se os canais representam luz linear ou valores codificados para display;
- se todos os consumidores usam a mesma convenção.

O tipo uint32_t sozinho não responde a nenhuma dessas perguntas.

O ChrisOS depende de convenções nas fronteiras entre subsistemas, portanto documentá-las faz parte da correção do sistema.

## Convenção RGB principal do ChrisOS

gfx_rgb recebe três canais de 8 bits e retorna:

    (red << 16) | (green << 8) | blue

O inteiro resultante é:

    0x00RRGGBB

Bits 31 a 24 são zero.

Bits 23 a 16 contêm vermelho.

Bits 15 a 8 contêm verde.

Bits 7 a 0 contêm azul.

Por exemplo:

    red   = 0x12
    green = 0x34
    blue  = 0x56

produz:

    0x00123456

Essa representação também aparece nas constantes da paleta visual em graphics.h.

Valores como CHRIS_DESKTOP_COLOR e CHRIS_TEXT_COLOR são inteiros 0x00RRGGBB comuns.

## Layout inteiro não é ordem de bytes

x86-64 é little-endian.

Assim, o inteiro de 32 bits:

    0x00123456

ocupa endereços crescentes como:

    56 34 12 00

A ordem lógica dos canais no inteiro continua sendo vermelho=0x12, verde=0x34 e azul=0x56.

A sequência de bytes na memória é consequência do endianess do inteiro.

Essa distinção evita um erro frequente de documentação: chamar os quatro bytes em memória de “RGBA” apenas porque existem quatro bytes.

Se um dispositivo definir canais pela posição física dos bytes, em vez da interpretação inteira da CPU, o contrato precisa reconciliar as duas visões explicitamente.

O caminho gráfico atual assume que a representação usada pelo framebuffer/dispositivo é compatível com essas escritas.

## Premissas do framebuffer

O boot verifica que o framebuffer possui 32 bits por pixel antes de inicializar a camada gráfica.

Entretanto, 32 bpp não é automaticamente sinônimo de 0x00RRGGBB.

Uma descrição genérica de framebuffer pode incluir máscaras ou shifts diferentes para cada canal.

A API atual de inicialização recebe:

- endereço;
- largura;
- altura;
- pitch em bytes.

Ela não recebe máscaras dos canais vermelho, verde e azul.

Portanto, o caminho atual assume layout de canais compatível em vez de adaptar-se dinamicamente a qualquer framebuffer de 32 bpp.

Essa é uma fronteira concreta da implementação.

Um caminho futuro para hardware físico deve validar máscaras fornecidas pelo firmware ou converter para um formato canônico definido.

## Cores da paleta gfx2d

gfx2d expõe uma paleta fixa de 16 cores.

As entradas são valores uint32_t como:

    0x000000
    0x000080
    0x008000
    ...
    0xFFFFFF

Novamente são valores RGB sem alfa significativo no byte superior.

gfx2d_color retorna o valor correspondente ao índice.

Índice fora da faixa retorna a entrada zero da paleta.

gfx2d_put é mais estrito: se o índice estiver fora de 0 a 15, nenhuma escrita é feita.

Essa diferença é relevante para o comportamento de erro.

gfx2d_color fornece cor fallback; gfx2d_put rejeita a operação inválida.

## Representação indexada de sprites

gfx2d_sprite não recebe pixels de 32 bits.

Sua origem é um array de uint8_t contendo índices da paleta.

Cada célula do sprite é interpretada como índice em gfx2d_palette.

O argumento key identifica um índice a ser ignorado.

Isso é transparência por color key, e não alpha blending.

Se key for zero, células com índice zero deixam o destino inalterado.

Outros índices sobrescrevem o destino com o RGB correspondente.

Color-key possui baixo custo e combina com sprites indexados em estilo retrô, mas não representa transparência parcial.

## Entrada 0xAARRGGBB em gfx_blit_rgba

A camada gráfica geral possui outro contrato para gfx_blit_rgba.

graphics.h declara que os pixels de origem são:

    0xAARRGGBB

O canal alfa ocupa bits 31 a 24.

Vermelho, verde e azul permanecem nas mesmas posições inferiores da convenção RGB comum.

Isso permite extrair canais por shifts e máscaras sem alterar as posições de RGB.

O backbuffer de destino continua sendo RGB: o caminho de blend grava apenas os 24 bits inferiores de cor.

Não existe um canal alfa persistente sendo composto no destino principal.

## Caminhos rápidos transparente e opaco

gfx_blit_rgba extrai:

    a = pixel >> 24

Para alfa zero, o pixel é ignorado.

Para alfa 255, o RGB substitui o destino diretamente:

    destino = pixel & 0x00FFFFFF

Esses dois casos evitam a aritmética do alfa parcial.

No caso opaco, o byte superior do destino também fica zero.

## Blend straight-alpha

Para alfa intermediário, o ChrisOS calcula cada canal como:

    saida = (origem * alfa + destino * (255 - alfa)) / 255

É uma composição de fonte straight-alpha sobre um destino tratado como existente/opaco.

Os canais RGB da origem não são armazenados pré-multiplicados por alfa.

Com alfa 128, aproximadamente metade da origem e metade do destino contribuem.

A divisão inteira trunca o resultado.

O cálculo é independente para vermelho, verde e azul.

Nenhum alfa de destino é produzido.

## Straight e premultiplied alpha

Em straight alpha, RGB descreve a cor sem atenuação e alfa é aplicado durante a composição.

Em premultiplied alpha, RGB já está multiplicado pelo alfa.

Os dois formatos não são intercambiáveis.

Fornecer entrada premultiplied ao gfx_blit_rgba faria o código multiplicar a contribuição da origem por alfa novamente, escurecendo pixels translúcidos.

Fornecer straight alpha a um compositor que espera premultiplied pode criar franjas claras.

O contrato atual de gfx_blit_rgba é straight alpha.

## Limitação de gamma e luz linear

A equação atual opera diretamente sobre valores armazenados de 8 bits.

Não existe conversão para espaço de luz linear antes da interpolação.

Para valores RGB codificados para display, interpolar numericamente no espaço codificado não equivale a interpolar intensidade física de luz.

Isso pode alterar gradientes translúcidos e bordas antialiased em comparação com um compositor color-managed.

O ChrisOS atual prioriza um caminho inteiro simples sobre composição com gerenciamento de cor.

É uma troca de qualidade de renderização, não um problema de segurança de memória.

## Alfa em gfx2d_layer é diferente

gfx2d_layer copia de uma superfície uint32_t para outra.

Para cada pixel de origem verifica:

    if ((c >> 24) == 0)
        continue;

Se o byte superior for diferente de zero, copia a word inteira.

Não há blend de alfa intermediário.

Assim, o alfa nessa função atua como teste binário:

- alfa 0: transparente;
- alfa 1 a 255: copiar.

Um pixel com alfa 1 e outro com alfa 255 são igualmente opacos para gfx2d_layer.

Esse contrato difere materialmente de gfx_blit_rgba.

## Interação entre RGB sem alfa e layers

A paleta gfx2d contém valores cujo byte superior é zero.

Se um desses pixels for escrito em um buffer e esse buffer for posteriormente usado como origem de gfx2d_layer, a função interpreta o pixel como transparente.

Portanto, uma superfície destinada a gfx2d_layer precisa de byte superior não zero para pixels visíveis.

As rotinas comuns da paleta escrevem 0x00RRGGBB e não adicionam alfa opaco automaticamente.

Cada subsistema precisa saber se o buffer é:

- superfície RGB final;
- destino de desenho indexado;
- superfície ARGB-like para composição por layer.

O mesmo uint32_t representa todos esses papéis, então a distinção é semântica, e não imposta pelo sistema de tipos C.

## Perda de informação de formato nas APIs

Várias APIs recebem apenas uint32_t cru.

Isso mantém rotinas simples e rápidas.

O custo é permitir combinações incompatíveis sem diagnóstico do compilador.

Por exemplo, uma cor 0xAARRGGBB passada como cor comum do framebuffer preserva o byte alfa na memória mesmo que muitos consumidores o considerem sem significado.

Da mesma forma, 0x00RRGGBB usado como pixel de layer pode desaparecer porque o layer interpreta o byte superior.

Uma API futura mais rica pode usar tipos ou descritores específicos para reduzir esse tipo de uso incorreto.

## Scaling não altera formato

gfx_blit_scaled faz nearest-neighbor scaling.

Seleciona coordenadas da origem por razões inteiras e copia diretamente a word uint32_t.

Nenhuma conversão de canais ou interpretação de alfa acontece.

Portanto o significado dos bits copiados continua sendo determinado pelo contrato do chamador.

Isso difere de gfx_blit_rgba, que interpreta alfa e produz RGB no destino.

## Dirty tracking é independente do formato

O sistema de damage tracking registra retângulos, não semântica de cor.

gfx_mark_dirty não examina canais nem alfa.

Tanto faz se um pixel mudou de azul para vermelho, de opaco para transparente ou entre duas representações binárias: o contrato é apenas marcar a região cujos bytes do backbuffer mudaram.

Essa separação é útil porque a política de apresentação não precisa conhecer color science.

## Aritmética e precisão

Os canais atuais possuem oito bits.

Cada canal tem 256 valores possíveis.

No blend, produtos como:

    255 * 255

cabem com ampla margem em inteiros de 32 bits.

A soma dos dois termos ponderados também permanece segura.

A divisão por 255 devolve valor entre 0 e 255.

A implementação não usa ponto flutuante.

Isso é adequado ao caminho de baixo nível do kernel e fornece resultado determinístico no ambiente inteiro suportado.

## Evidência de validação

tools/test_graphics_present.c verifica valores RGB concretos na camada geral.

Entre outros pontos, testa:

- clear completo com 0x00112233;
- retângulos com 0x00445566;
- cópia escalada preservando exatamente as words uint32_t.

tools/test_gfx2d.c verifica a paleta.

Confirma que:

- índice 1 corresponde a 0x000080;
- índice 12 corresponde a 0xFF0000;
- escrita com índice inválido não altera destino;
- células de sprite com key são ignoradas;
- índices de tilemap geram os RGB esperados.

Esses testes estabelecem as convenções numéricas para as funções exercitadas.

Os testes atuais não cobrem diretamente todos os valores intermediários de alfa de gfx_blit_rgba nem a semântica binária do byte superior em gfx2d_layer.

Esses são alvos úteis para regressões futuras.

## Características de desempenho

Escritas RGB comuns são stores de 32 bits.

Blits opacos também podem ser cópias diretas.

Alfa parcial custa mais porque cada pixel exige:

- load da origem;
- load do destino;
- extração do alfa;
- multiplicações por canal;
- somas;
- divisões por 255;
- recomposição dos canais;
- store.

O caminho atual é escalar.

Uma implementação SIMD futura poderia processar vários pixels, desde que preserve arredondamento e clipping ou defina explicitamente um novo contrato numérico.

## Segurança e robustez

Formato de cor costuma ser questão visual, mas dimensões e ownership continuam questões de segurança de memória.

As funções gráficas validam várias geometrias, porém o formato cru não é auto-descritivo.

Arquivo externo, imagem de rede ou aplicação não confiável não deve poder escolher livremente dimensões, stride ou formato sem validação na fronteira.

O kernel deve converter dados não confiáveis para uma representação interna validada antes do desenho.

O código documentado atualmente opera principalmente sobre buffers controlados pelo projeto.

## Limitações atuais

As principais fronteiras do subsistema são:

- framebuffer assume layout 32-bpp compatível;
- ausência de conversão por channel masks em runtime;
- ausência de perfis de cor;
- ausência de blend em luz linear;
- ausência de HDR ou canais acima de oito bits;
- ausência de alfa persistente no framebuffer principal;
- gfx2d_layer usa gating binário de alfa;
- a paleta não adiciona alfa opaco automaticamente;
- APIs uint32_t não codificam o formato no tipo C;
- cobertura de testes de alfa parcial é limitada.

São propriedades da implementação atual, não requisitos gerais de sistemas gráficos.

## Limite entre estado atual e roadmap

Evoluções futuras podem incluir:

- descritores explícitos de pixel format;
- validação de máscaras do framebuffer de boot;
- conversão entre RGB canônico e formato nativo do dispositivo;
- abstração tipada de superfícies ARGB;
- premultiplied alpha onde for vantajoso;
- kernels SIMD de blend;
- metadados de espaço de cor;
- composição em luz linear para caminhos de maior qualidade;
- testes cobrindo valores de alfa e semântica de layers.

Nada disso deve ser inferido como já implementado.

## Proveniência da revisão

Este capítulo documenta formatos de cor conforme observados no main do ChrisOS na revisão e05a17fd76333114a3fb5c2452f38ca747d4ac56.

A autoridade principal é kernel/gfx/graphics.c e graphics.h para RGB/ARGB, e kernel/gfx/gfx2d.c e gfx2d.h para paleta e layers. tools/test_graphics_present.c e tools/test_gfx2d.c fornecem evidência executável para as convenções numéricas que exercitam.
