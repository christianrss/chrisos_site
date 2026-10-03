---
id: ethernet
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - makefile
symbols:
  - eth_build
  - net_rx_ethernet
  - net_arp
  - net_send_arp_reply
  - net_send_frame
  - net_init
  - virtio_process_rx
  - virtio_net_tx
depends_on: []
related:
  - ipv4
  - virtio-net
  - network-stack
---

# Framing Ethernet

## Escopo

Ethernet é o formato de link usado pelo stack de rede atual do ChrisOS.

Neste caminho, ChrisOS não implementa um controlador Ethernet físico genérico. O device ativo é a interface PCI VirtIO-net legacy usada sob QEMU, mas a camada de rede recebe e emite bytes comuns de frames Ethernet depois que o header VirtIO específico de 10 bytes é removido ou inserido pelo driver.

A fronteira arquitetural de RX é:

    descritor VirtIO RX
       -> header virtio-net de 10 bytes
       -> frame Ethernet
       -> dispatch por EtherType
       -> ARP ou IPv4

No TX:

    builder ARP / IPv4
       -> header Ethernet
       -> frame L2 completo
       -> virtio_net_tx()
       -> header virtio-net de 10 bytes
       -> fila VirtIO TX

O foco deste capítulo é essa fronteira Ethernet, e não os internals de IPv4, UDP, TCP, sockets ou virtqueues documentados em capítulos próprios.

## Header Ethernet II

O stack atual pressupõe header Ethernet II de 14 bytes:

| Offset | Tamanho | Significado |
|---|---:|---|
| 0 | 6 | MAC de destino |
| 6 | 6 | MAC de origem |
| 12 | 2 | EtherType, big-endian |
| 14 | variável | payload |

`ETH_HDR_LEN` vale 14.

`net_rx_ethernet` rejeita frames menores que 14 bytes e lê o EtherType nos bytes 12 e 13.

Não existe parser de tag 802.1Q VLAN nem caminho 802.3 length/LLC nesta revisão.

## Endereços MAC

MACs são representados como seis bytes crus.

O endereço local não é hard-coded na camada de rede. `virtio_net_init` lê seis bytes da configuração do device VirtIO e `virtio_net_mac` expõe o array resultante.

Headers de saída combinam:

- MAC de destino escolhido pelo protocol path;
- MAC de origem retornado por `virtio_net_mac`;
- EtherType de dois bytes.

O código atual não possui um tipo dedicado para endereço MAC.

## Construção do header

`eth_build` escreve os 14 bytes completos.

Ele copia exatamente seis bytes do destino e seis da origem e grava EtherType com `write_be16`.

A função não aloca memória e não valida os pointers recebidos. Os callers passam posições dentro do buffer TX estático.

O custo é constante: doze cópias de byte mais uma escrita 16-bit.

## Network byte order

EtherType é codificado em big-endian.

O stack usa helpers pequenos, como `read_be16`, `read_be32`, `write_be16` e `write_be32`, sem depender das rotinas libc de byte order.

No header Ethernet:

    frame[12] = byte alto do EtherType
    frame[13] = byte baixo do EtherType

A mesma política explícita de byte order é usada por IPv4 e transport headers.

## Entry point de RX

O parser L2 é:

    net_rx_ethernet(const uint8_t *frame, uint32_t len)

Antes do parse exige:

- stack de rede ready;
- pointer não nulo;
- comprimento mínimo de 14.

Depois lê EtherType e reconhece somente:

    0x0806 -> ARP
    0x0800 -> IPv4

Qualquer outro EtherType é ignorado silenciosamente.

Não existe registry de protocolos nem diagnostic no default path.

## Filtragem do MAC de destino

`net_rx_ethernet` não examina bytes 0..5 antes do dispatch.

O código depende do network device/backend para decidir quais frames unicast, broadcast ou outros serão entregues ao guest.

Depois que um frame chega ao parser, a seleção de protocolo considera somente EtherType.

O stack de software atual, portanto, não aplica por conta própria a regra "MAC de destino deve ser o nosso".

## Fronteira RX com VirtIO

Buffers RX do VirtIO-net começam com um `virtio_net_hdr` de 10 bytes antes do frame Ethernet.

`virtio_process_rx` recebe um descritor usado, obtém seu buffer e chama:

    net_rx_ethernet(buf + 10, total_len - 10)

quando o comprimento reportado supera o header VirtIO.

O parser Ethernet nunca vê os 10 bytes do transporte.

Isso mantém o formato do device separado do protocolo L2.

## Ownership do buffer RX

O driver provisiona oito descritores RX.

Cada descritor possui um buffer de 2048 bytes.

A regra de lifetime é síncrona:

1. VirtIO marca o descritor como used.
2. O driver aponta `net_rx_ethernet` diretamente para o buffer desse descritor.
3. Todo processamento Ethernet/ARP/IP ocorre antes do retorno.
4. Somente depois o `rx_repost` devolve o descritor ao device.

Camadas superiores não podem guardar o pointer do frame depois do retorno.

Os caminhos atuais copiam dados persistentes, como bytes do MAC do gateway, em vez de armazenar pointers para buffers RX.

## Cópias em RX

Não há uma segunda cópia do frame entre o driver e `net_rx_ethernet`.

O parser trabalha diretamente sobre o buffer postado, começando depois do header VirtIO.

Isso reduz custo de cópia por pacote.

O trade-off é o contrato rígido de lifetime do buffer.

## Fronteira de confiança do comprimento RX

O driver recebe `elem.len` do used ring VirtIO.

Ele verifica se o descriptor ID pertence aos oito buffers e se o comprimento é maior que o header VirtIO.

Porém, não clampa explicitamente o comprimento reportado contra os 2048 bytes realmente postados antes de entregar o valor lógico ao stack.

Com QEMU/VirtIO esperado, isso segue o contrato do device.

Um device malicioso ou defeituoso que reportasse um comprimento impossível enfraqueceria as garantias dos parsers superiores.

Um driver endurecido deve validar completion length contra a capacidade do descritor.

## Buffer de transmissão

A camada de rede possui um único array global:

    static uint8_t g_tx[1600];

Builders de ARP, UDP e TCP reutilizam o mesmo storage.

O header Ethernet sempre começa no offset zero.

Headers superiores e payload seguem em sequência.

Isso evita allocation no TX, mas torna a construção não reentrante.

## Limite do driver TX

`virtio_net_tx` aceita frames Ethernet de 1 até 1514 bytes.

O máximo corresponde a:

    14 bytes de header Ethernet
    + 1500 bytes de payload

sem FCS dentro do buffer fornecido pela camada de software.

O driver acrescenta seu próprio header VirtIO de 10 bytes antes de publicar o TX.

Jumbo frames não são suportados nesse caminho.

## Cópia e ownership no TX

A camada de rede passa `g_tx` para `virtio_net_tx`.

O driver copia o frame inteiro para seu próprio buffer TX logo depois do header VirtIO.

Assim, a camada superior pode reutilizar `g_tx` depois do retorno; o device não faz DMA diretamente sobre esse array.

O driver usa descriptor zero e drena completion antes/depois do submit.

O modelo é simples e serial.

## Gap de propagação de erro

`net_send_frame` chama `virtio_net_tx` e descarta o valor retornado.

A geração de ARP reply e outros paths de transmissão não recebem feedback explícito quando o driver rejeita o frame.

Por exemplo, device não ready pode fazer `virtio_net_tx` retornar zero e o caller não recebe uma falha.

Uma interface futura deve propagar status de TX para cima.

## FCS e padding

ChrisOS constrói somente header MAC e payload de rede.

`eth_build` e `virtio_net_tx` não acrescentam FCS de quatro bytes.

Também não existe padding explícito de frame curto até o mínimo tradicional de Ethernet.

O ARP reply atual possui exatamente 42 bytes:

    14 bytes Ethernet
    + 28 bytes ARP

antes do header VirtIO.

Isso funciona no ambiente virtual atual, onde camadas inferiores cuidam da representação efetiva do link.

Não se deve concluir a partir disso que ChrisOS já implementa Ethernet físico com preamble, inter-packet gap, padding ou geração de FCS.

## ARP como primeiro consumidor L2

EtherType 0x0806 é entregue a `net_arp`.

A implementação ARP atual é pequena.

Ela trata:

- opcode 1: request;
- opcode 2: reply.

O receive exige ao menos 42 bytes, que correspondem ao header Ethernet mais o payload ARP comum para Ethernet/IPv4.

## Tratamento de ARP request

`net_send_arp_reply` extrai:

- sender hardware address no offset 22;
- sender protocol address no offset 28;
- target protocol address no offset 38.

Só responde se o target protocol address for o IPv4 fixo do ChrisOS.

A resposta usa:

    EtherType      = 0x0806
    hardware type  = 1
    protocol type  = 0x0800
    hardware size  = 6
    protocol size  = 4
    operation      = 2

O MAC Ethernet de destino é o sender MAC do request.

## Limites de validação ARP

O receive ARP não valida todos os fields do header antes de usar offsets fixos.

Ele verifica comprimento e operation, mas não exige primeiro que hardware type, protocol type, HLEN e PLEN descrevam exatamente Ethernet/IPv4.

Um pacote ARP malformado com 42 bytes pode ser interpretado como se tivesse o layout esperado mesmo quando seus metadados dizem outra coisa.

É um gap de hardening do parser.

## Configuração IPv4 estática

O comportamento Ethernet/ARP está acoplado a:

    IP do guest = 10.0.2.15
    gateway     = 10.0.2.2

Esses valores correspondem ao ambiente QEMU user-network esperado pelo projeto.

Não existe DHCP em `net.c`.

`net_status` mostra o MAC VirtIO e o endereço fixo 10.0.2.15.

## Cache do MAC do gateway

ChrisOS não mantém uma neighbor table ARP genérica.

Há somente:

    g_gw_mac[6]

e a flag:

    g_gw_mac_valid

Um ARP reply recebido atualiza esse cache apenas quando o sender protocol address é exatamente 10.0.2.2.

Replies de outros hosts não entram em uma tabela reutilizável.

## Ausência de ARP request ativo

Na revisão inspecionada, `net.c` possui builder de ARP reply, mas não uma função geral que emita ARP request para um destino ou gateway não resolvido.

Helpers de saída, como `net_udp_send`, exigem `g_gw_mac_valid` e falham quando o MAC do gateway ainda não foi aprendido.

O stack não possui state machine normal de neighbor resolution com request, retry, timeout e aging de cache.

Essa é uma das maiores limitações funcionais na fronteira L2/L3 atual.

## Segurança do cache ARP

O cache do gateway não é autenticado.

Qualquer ARP reply entregue ao guest cujo sender protocol address seja 10.0.2.2 pode substituir `g_gw_mac`.

Não há correlação com request pendente, expiry, duplicate-address detection, trust policy ou defesa contra ARP spoofing.

Isso é aceitável no ambiente experimental QEMU atual, mas não representa um design LAN hardened.

## Handoff para IPv4

EtherType 0x0800 segue para `net_ipv4`.

A camada Ethernet não verifica destination IP, checksum IP, fragmentation ou protocol number.

Esses são problemas da camada de rede.

A separação é explícita no dispatch, mesmo que as funções ainda estejam no mesmo arquivo `net.c`.

O capítulo de IPv4 documenta a próxima fronteira.

## Modelo de concorrência

A implementação usa estado global mutável:

- um `g_tx`;
- um cache de MAC do gateway;
- uma flag global de network ready;
- uma instância global VirtIO-net;
- um único buffer TX do driver.

Não existe lock L2 para packet construction ou atualização do gateway cache.

O design atual pressupõe uso serializado/poll-driven.

Transmissores concorrentes em APs diferentes poderiam sobrescrever `g_tx` durante a construção de outro frame.

Esse stack não deve ser descrito como SMP-safe geral.

## Modelo de polling

`net_poll` chama `virtio_net_poll`.

O driver lê/acknowledges o byte ISR, processa descriptors RX completos e drena TX.

O processamento de protocolo ocorre de forma síncrona no contexto que executa o poll, em vez de ser encaminhado a um worker Ethernet separado.

Isso simplifica ownership, mas também faz parsing e respostas rodarem dentro do mesmo contexto de polling.

## Complexidade

O dispatch Ethernet é O(1): check de comprimento, leitura de EtherType e um branch pequeno.

A construção do header também é O(1).

TX tem custo O(tamanho do frame), pois o driver copia bytes de `g_tx` para seu buffer TX próprio.

RX não adiciona cópia de payload entre driver e parser Ethernet.

Construção de ARP reply é O(1).

O desenho privilegia código pequeno e custos previsíveis em vez de generalidade.

## Integração QEMU

A configuração padrão conecta:

    -device virtio-net-pci,netdev=n0

com QEMU user networking.

Host forwarding mapeia UDP/TCP host port 7007 para guest port 7 e TCP host port 9016 para guest port 9016.

Esses caminhos exercitam indiretamente RX/TX Ethernet/VirtIO por meio de protocolos superiores.

São infraestrutura de integração, não um unit test dedicado do parser Ethernet.

## Evidência de validação

Não existe `test_ethernet.c`, `test_arp.c` ou equivalente host dedicado na árvore inspecionada.

A evidência atual inclui:

- logs de inicialização bem-sucedida do VirtIO-net;
- uso do stack sob QEMU user networking;
- echo e transfer paths que dependem de framing RX/TX válido;
- bounds checks visíveis no código.

Isso não cobre exaustivamente frames malformados.

Uma suite L2 determinística ainda é necessária.

## Testes recomendados

Testes úteis devem montar arrays crus e verificar:

- frame menor que 14 é rejeitado;
- EtherType desconhecido é ignorado;
- 0x0806 vai para ARP e 0x0800 para IPv4;
- `eth_build` produz bytes exatos de destino/origem/EtherType;
- ARP request para 10.0.2.15 produz reply de 42 bytes;
- request para outro IP não produz reply;
- HLEN/PLEN/types inválidos são rejeitados depois do hardening;
- cache do gateway só atualiza para o gateway esperado;
- falha de TX chega ao caller;
- comprimento VirtIO RX não pode exceder o buffer postado.

Também é necessário provar ou rejeitar explicitamente transmissores concorrentes.

## Limitações atuais

A camada de link suporta somente Ethernet II sem tag carregando ARP ou IPv4.

Não há VLAN, IPv6, LLC/SNAP, jumbo frame, API de multicast, neighbor table geral, DHCP, ARP resolution ativa, expiry de cache ou autenticação L2.

FCS, padding e preamble de Ethernet físico não são implementados nessa camada de software.

O desenho está fortemente alinhado ao ambiente QEMU VirtIO-net atual.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta o formato de bytes Ethernet, ownership de buffers, comportamento ARP, limites RX/TX e gaps de validação, mantendo o transporte VirtIO separado do protocolo Ethernet.
