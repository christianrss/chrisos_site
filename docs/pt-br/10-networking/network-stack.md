---
id: network-stack
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/sock.c
  - kernel/net/sock.h
  - kernel/net/net_xfer.c
  - kernel/net/net_xfer.h
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - makefile
symbols:
  - net_init
  - net_poll
  - net_rx_ethernet
  - virtio_net_init
  - virtio_net_poll
  - virtio_net_tx
  - sock_init
  - sock_on_tcp
  - sock_on_udp
  - sock_tick
  - net_xfer_tcp
depends_on:
  - buses-mmio-dma
  - interrupts-smp
related:
  - ethernet
  - ipv4
  - udp
  - tcp
  - virtio-net
  - sockets
---

# Stack de rede e VirtIO networking

## Escopo

A rede do ChrisOS é um stack compacto, orientado a polling, construído em torno de um único device PCI VirtIO-net legacy e de um pequeno conjunto de máquinas de estado em kernel.

A implementação é deliberadamente estreita. Ela atende o ambiente QEMU user-network usado pelo projeto, paths de echo UDP/TCP, clients e listeners simples, consultas DNS, canal de host rebuild e um serviço TCP próprio de transferência de arquivos.

Não é um stack de rede geral compatível com BSD sockets.

A arquitetura implementada é:

```text
processo / aplicação CLVM
        |
        v
socket table / serviços do projeto
        |
        v
UDP ou pequenas máquinas TCP
        |
        v
IPv4
        |
        v
Ethernet II
        |
        v
VirtIO-net legacy PCI
        |
        v
virtqueues / QEMU user network
```

Este capítulo documenta a integração entre essas camadas. Os wire formats específicos são tratados em capítulos próprios.

## Arquitetura global

O stack é distribuído principalmente em quatro arquivos.

`virtio_net.c` controla device PCI, negociação VirtIO, virtqueues RX/TX, buffers DMA-visible, MAC address e polling dos used rings.

`net.c` controla dispatch Ethernet, ARP, geração IPv4, paths embutidos de echo UDP/TCP, um cache de MAC do gateway e o buffer global de transmissão.

`sock.c` implementa socket table voltada a processos/aplicações, operações básicas de listen/connect/send/recv/close, estado auxiliar de DNS e client de host rebuild.

`net_xfer.c` implementa uma state machine TCP específica do projeto na porta 9016.

Esses componentes compartilham estado global e foram desenhados para o modelo atual de execução serializada por polling.

## Ordem de inicialização

`net_init` zera três estados principais:

- `g_net_ready = 0`;
- MAC do gateway invalidado;
- conexão TCP embutida de echo marcada inativa.

Depois chama `virtio_net_init`.

Se o device não inicializar, retorna zero e a rede permanece indisponível.

Após sucesso do driver:

1. marca a rede ready;
2. inicializa o serviço de transferência;
3. inicializa a socket table;
4. registra no serial o IPv4 fixo.

O endereço local é 10.0.2.15.

## Descoberta VirtIO

O driver procura no PCI o device VirtIO-net legacy e recebe um I/O-port base.

Ele reseta status, configura ACKNOWLEDGE e DRIVER, lê features do host e negocia apenas:

- `VIRTIO_NET_F_MAC`;
- `VIRTIO_NET_F_STATUS`.

Se FEATURES_OK não for aceito, a inicialização falha e VIRTIO_FAILED é marcado.

Depois da negociação, os seis bytes do MAC são lidos da configuração do device.

## Topologia de filas

O driver usa duas virtqueues:

- queue 0 para RX;
- queue 1 para TX.

A memória física dos rings é dimensionada conforme o queue size reportado pelo device, mas ChrisOS exige pelo menos oito entradas.

`NET_QUEUE_SIZE` vale 8.

Somente oito RX descriptors são populados.

O TX usa descriptor zero.

A memória dos rings é alocada em páginas físicas contíguas e acessada pelo mapeamento físico→virtual do kernel.

## Buffers RX

Cada um dos oito RX descriptors recebe uma página física própria via `pmm_alloc`.

O comprimento anunciado ao device é:

```text
NET_RX_BUF_SIZE = 2048 bytes
```

Cada descriptor recebe flag WRITE porque o device grava os bytes recebidos na memória guest.

Os oito descriptors entram no available ring antes da notificação da queue RX.

## Header VirtIO de pacote

O driver espera um header VirtIO-net legacy de 10 bytes antes do frame Ethernet em RX e TX.

Esse header de transporte não pertence ao Ethernet.

No receive, o driver entrega:

```text
net_rx_ethernet(buf + 10, total_len - 10)
```

No transmit, grava dez bytes zero antes de copiar o frame Ethernet.

Assim, as camadas acima sempre trabalham com framing Ethernet normal.

## Ownership síncrono de RX

O ownership de RX é simples e crítico.

Quando um descriptor aparece no used ring, ele permanece sob controle do stack enquanto `net_rx_ethernet` e todos os parsers/handlers inferiores executam de forma síncrona.

Somente depois de toda a cadeia retornar o `rx_repost` devolve o descriptor ao device.

O fluxo efetivo é:

```text
used descriptor
  -> Ethernet
  -> ARP ou IPv4
  -> UDP/TCP
  -> socket/serviço
  -> retorno
  -> repost do descriptor
```

Nenhuma camada pode manter pointer para o RX buffer após o retorno.

Estado persistente de conexão é copiado para estruturas próprias.

## Receive sem cópia genérica

Do buffer VirtIO até Ethernet, IPv4 e UDP/TCP, o stack não cria uma cópia genérica do packet.

Os parsers operam por offsets no mesmo frame recebido.

Isso reduz tráfego de memória e mantém o custo previsível.

Em contrapartida, bounds checks e regras de lifetime tornam-se parte central da segurança.

## Trust boundary do completion length

O driver confere que o descriptor ID pertence aos oito RX descriptors e que o comprimento supera os 10 bytes do header VirtIO.

Ele não rejeita explicitamente um used length acima da capacidade real de 2048 bytes do buffer postado.

Com VirtIO/QEMU correto, o device deve respeitar o descriptor.

Contra device malicioso ou defeituoso, um comprimento lógico impossível poderia chegar aos parsers superiores.

É um gap de hardening na fronteira de device.

## Dispatch Ethernet e IPv4

O primeiro entry point é `net_rx_ethernet`.

Ele reconhece apenas:

- EtherType 0x0806 → ARP;
- EtherType 0x0800 → IPv4.

O IPv4, por sua vez, despacha apenas:

- protocol 17 → UDP;
- protocol 6 → TCP.

Não existe registry dinâmico de protocolos.

EtherTypes e protocols desconhecidos são ignorados.

## Configuração estática

O stack está alinhado ao QEMU user networking:

```text
guest:   10.0.2.15
gateway: 10.0.2.2
DNS:     10.0.2.3
```

Não existem DHCP client, route table, subnet configuration, lista de interfaces ou objeto de endereço configurável em runtime.

O UDP de saída depende de um único MAC de gateway cacheado.

## Integração ARP

ARP tem duas funções principais.

ChrisOS responde ARP requests destinados a 10.0.2.15.

Também aprende um único MAC quando recebe ARP reply cujo sender protocol address é 10.0.2.2.

O resultado vai para `g_gw_mac`, controlado por `g_gw_mac_valid`.

Não há neighbor table geral.

Também não existe state machine ativa de ARP request/retry nesta revisão.

Clients podem falhar ao transmitir até que o MAC do gateway tenha sido aprendido.

## Buffer global de TX

A construção de packets usa:

```text
static uint8_t g_tx[1600];
```

ARP, UDP, TCP, sockets e serviços específicos reutilizam o mesmo array.

O path normal não aloca packet buffer a cada envio.

Isso é eficiente em execução serializada, mas torna a construção não reentrante.

Dois transmissores concorrentes podem sobrescrever o mesmo pacote.

## Transmissão VirtIO

`virtio_net_tx` aceita frames Ethernet de no máximo 1514 bytes.

O driver:

1. drena completion anterior;
2. grava header VirtIO de 10 bytes zerado;
3. copia o frame para o buffer TX privado do driver;
4. configura descriptor zero;
5. adiciona descriptor ao available ring;
6. notifica queue 1;
7. drena completion novamente.

O DMA do device lê o buffer privado do driver, não `g_tx`.

Após a cópia, `g_tx` pode ser reutilizado.

## TX serial

Existe um único TX physical buffer e descriptor zero é reutilizado.

`virtio_drain_tx` verifica o used ring em um loop limitado a 200000 iterações por chamada.

Não existe uma queue de objetos TX pendentes mantida por software nem callback assíncrono de completion para a camada superior.

O modelo minimiza complexidade de ownership, mas limita throughput e concorrência.

## Propagação de falha TX

`virtio_net_tx` retorna sucesso/falha.

Entretanto, `net_send_frame` descarta esse retorno.

Alguns callers podem considerar o envio concluído após construir o packet mesmo se o device rejeitou o frame.

Há também mismatch de tamanho: `net_tcp_xmit` aceita o que couber em 1600 bytes, enquanto o driver rejeita frame Ethernet acima de 1514.

Um stack robusto deve propagar falha de link às camadas superiores.

## Poll loop

`net_poll` é o mecanismo central de progresso.

Com a rede ready, executa:

1. `virtio_net_poll()`;
2. `sock_tick()`;
3. `host_rebuild_tick()`.

O driver lê/acknowledges ISR, processa RX completado e drena TX.

Timers de sockets e fluxo de host rebuild só avançam enquanto `net_poll` é chamado.

Não existe thread dedicada de networking.

## IRQ versus polling

O device possui ISR register e o driver o lê, mas o processamento de protocolo ocorre no caminho de `virtio_net_poll`.

Não existe uma fila intermediária que entregue packet completion para um worker de rede separado.

O contexto efetivo do parser Ethernet/IP/TCP é o caller de `net_poll`.

Isso simplifica sincronização, mas também faz o custo do packet aparecer no loop que realiza o polling.

## UDP embutido

UDP port 7 é tratado diretamente em `net.c` como echo.

Outros destination ports podem seguir para `sock_on_udp`.

`net_udp_send` limita payload a 1400 bytes e exige MAC do gateway cacheado.

O checksum UDP transmitido é zero, válido em IPv4, porém sem proteção de checksum no nível UDP para esses datagrams.

O capítulo UDP detalha wire format e validação.

## TCP embutido

`net.c` contém ainda uma conexão TCP simples, global, em `g_tcp`, usada no echo da porta 7.

Ela guarda remote MAC, IPv4, remote port, `snd_nxt` e `rcv_nxt`.

Essa máquina de estado é separada da socket table.

ChrisOS possui, portanto, múltiplos mini-engines TCP em vez de um único transport core.

## Ordem de dispatch TCP

Um packet TCP recebido segue aproximadamente:

1. destination port 9016 → `net_xfer_tcp`;
2. tentativa de consumo por `sock_on_tcp`;
3. se não consumido, port 7 → echo TCP embutido;
4. outros cases → ignorados.

O file-transfer service tem prioridade sobre a socket table na porta dedicada.

## Socket table

`sock.c` define:

```text
SOCK_MAX = 16
SOCK_RX  = 2048
```

`alloc_sk` nunca usa índice zero, portanto há no máximo quinze descriptors utilizáveis.

Os estados implementados são:

- FREE;
- LISTEN;
- SYN_SENT;
- ESTABLISHED.

Não existe state graph TCP completo com SYN_RECEIVED, FIN_WAIT, TIME_WAIT ou CLOSE_WAIT.

## Ownership de sockets

Cada socket guarda:

- owner PID de processo nativo;
- slot opcional de aplicação CLVM.

A visibilidade muda conforme o caller.

Para CLVM, o slot precisa coincidir.

Para processo nativo, o slot deve ser negativo e owner igual a `proc_current()`.

Helpers de cleanup fecham sockets por process ou por CLVM slot.

Esse modelo evita que callers comuns usem descriptors vivos pertencentes a outra aplicação.

## Listen e accept

`sock_listen_for` aloca descriptor e o coloca em LISTEN.

Quando chega SYN para a porta, `sock_on_tcp` aloca child, marca imediatamente ESTABLISHED, guarda o listener como parent e envia SYN+ACK.

Não existe estado SYN_RECEIVED explícito.

`sock_accept` pode retornar o child enquanto ele ainda representa uma conexão que não passou por toda a semântica clássica do three-way handshake.

O implementation model antecipa ESTABLISHED.

## Connect outbound

`sock_connect` aloca socket, usa SYN_SENT e escolhe local ephemeral port a partir de 40000.

O sequence inicial é derivado de:

```text
pit_ticks() * 2654435761
```

Se o MAC do gateway já estiver disponível, ele é copiado para o socket.

Quando chega SYN+ACK, o socket guarda remote MAC, atualiza receive-next, muda para ESTABLISHED e envia ACK.

## Retry de SYN

`sock_tick` percorre a tabela.

Se um socket ainda estiver SYN_SENT e passarem mais de 30 ticks desde o último transmit, o SYN é reenviado com o sequence original.

Não existem retry limit, exponential backoff, connection timeout ou notificação de falha nesse loop.

O tick não retransmite data segments comuns.

## Send e recv

`sock_send` exige ESTABLISHED e limita cada chamada a 200 bytes de payload.

O packet sai com ACK|PSH.

Cada socket possui RX array de 2048 bytes.

`sock_recv` copia dados ao caller e compacta os bytes restantes para o início do array.

Não existe scatter/gather nem queue de buffers por socket.

## Pressão no receive buffer

Quando chega payload TCP, o código calcula espaço restante e copia apenas o que couber.

Porém, `rcv_nxt` é avançado pelo tamanho completo do payload recebido antes da truncagem.

Depois envia ACK.

Assim, bytes que não couberam podem ser descartados enquanto o peer recebe confirmação como se todo o segmento tivesse sido aceito.

O flow control atual não é lossless sob pressão de buffer.

## Limitações de sequencing TCP

Não existe queue para segments fora de ordem.

O receive não exige que `seq == rcv_nxt` antes de copiar dados.

Ele simplesmente define:

```text
rcv_nxt = seq + payload_length
```

para payload aceito.

Não há duplicate suppression, SACK, congestion control, receive-window real ou retransmissão de application data.

O TCP de sockets deve ser entendido como state machine pequena, não TCP completo.

## UDP por socket

`sock_on_udp` considera apenas destination ports 40000 ou superiores.

Ele procura socket LISTEN com port igual e RX vazio.

O payload é copiado para o RX array de 2048 bytes e truncado nesse limite.

A função não usa o argumento de comprimento físico do frame para validar os offsets antes de copiar conforme UDP length.

O echo UDP direto possui validações de bounds mais fortes.

Esse é um gap real de hardening.

## DNS helper

`sock_dns` é um client DNS mínimo sobre UDP.

Usa server 10.0.2.3, transaction ID fixo 0x1234, uma única query A/IN e um socket interno persistente.

A resposta é parseada de forma simples: o código procura nos bytes por padrão type-A/class-IN e lê quatro bytes em offset relativo.

Não é um parser DNS completo e não implementa traversal robusto de compression pointers ou transaction matching geral.

## Canal de host rebuild

`host_rebuild_tick` é outro consumidor específico.

Quando ativado, conecta em 10.0.2.2:9017, envia os oito bytes `rebuild\n`, aguarda resposta iniciada por 'O' e chama `machine_reboot()`.

Como roda dentro de `net_poll`, usa as mesmas máquinas de socket e timers do restante da rede.

## Serviço de transferência

`net_xfer.c` recebe TCP port 9016 por dispatch direto em `net.c`.

Há uma conexão global com fases:

- IDLE;
- HDR;
- PATH;
- DATA;
- DONE.

O protocolo de aplicação começa com header CFS1 de 12 bytes contendo path length e file size, seguido de path e file bytes.

Ao completar, grava por `fs_write` e responde com ACK de sucesso ou erro.

O serviço não usa a socket API genérica.

## Limites do transfer

O path length deve ser maior que zero e menor que 512.

File size deve ser maior que zero e no máximo `CFS_MAX_FILE_SIZE`.

O buffer do arquivo é alocado com `kmalloc`.

Somente uma transferência global pode ficar ativa.

Novo SYN reseta o estado anterior.

## Três máquinas TCP

A revisão atual possui três consumidores TCP distintos:

1. echo port 7 em `net.c`;
2. socket table em `sock.c`;
3. file transfer em `net_xfer.c`.

Eles compartilham packet builder e checksum, mas não um engine geral de conexão.

Essa duplicação é um fato arquitetural central.

Unificar essas máquinas reduziria divergência de sequence/length handling e faria fixes de validação valerem para todos os services.

## Concorrência e SMP

O stack mantém diversos globals mutáveis:

- `g_vnet`;
- `g_tx`;
- MAC do gateway;
- TCP echo state;
- socket table;
- ephemeral-port counter;
- DNS state;
- host-rebuild state;
- transfer state.

Não existe network lock geral.

O design depende de polling e uso efetivamente serializado.

RX/TX/socket mutations simultâneos em APs arbitrários criariam data races.

O stack não é plenamente SMP-safe.

## Fronteira de segurança

Packets RX são input externo ao trust boundary do kernel.

Há vários checks locais, mas a validação não é uniforme.

Gaps conhecidos incluem:

- completion length RX não é clampado aos 2048 bytes do descriptor;
- checksum IPv4 não é validado;
- fragments IPv4 não são rejeitados ou remontados;
- alguns paths TCP confiam demais em IPv4 total length;
- UDP socket delivery não usa o comprimento físico do frame para bounds antes da cópia;
- ARP não valida todos os fields de formato;
- cache ARP do gateway não possui autenticação.

São limitações de implementação, não apenas features futuras.

## Modelo de validação

Não existe uma suite host única que injete sistematicamente frames malformados através de Ethernet, IPv4, UDP, TCP e sockets.

A evidência atual é principalmente integrada:

- boot do VirtIO-net sob QEMU;
- echo UDP/TCP;
- consumidores socket/DNS;
- transferência em 9016;
- rebuild em 9017;
- host forwarding configurado no makefile.

Happy-path integration não prova segurança contra input hostil.

## Integração QEMU

O comando normal usa VirtIO-net com user networking.

Host forwarding expõe serviços do guest, incluindo port 7 e port 9016.

Esse ambiente é o principal hardware/profile de rede atual.

Suporte ao device paravirtual não implica suporte a NIC física arbitrária.

## Características de performance

RX é síncrono e praticamente zero-copy.

TX faz uma cópia extra do packet builder para o buffer VirtIO único.

Lookups são lineares, mas pequenos:

- até quinze sockets utilizáveis;
- uma entrada de gateway;
- uma conexão transfer;
- uma conexão de echo embutida.

Não existem grandes hash tables de routing, neighbors ou connections.

O design privilegia estruturas pequenas e bounded sobre throughput alto.

## Evolução recomendada

As mudanças estruturais de maior impacto são:

1. centralizar validação de packet antes do transport dispatch;
2. limitar completion length à capacidade real dos buffers;
3. implementar ARP ativo e neighbor table bounded;
4. unificar as três máquinas TCP;
5. propagar falhas de TX;
6. implementar sequence, retransmission e flow control corretos;
7. proteger estado compartilhado ou confinar toda rede a um execution context formal;
8. criar testes determinísticos de malformed packets e fuzzing;
9. separar DNS/serviços de aplicação dos internals de transporte;
10. criar modelo real de route/interface antes de expandir além do QEMU user networking.

## Nota de revisão

Este capítulo foi reconciliado com a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele descreve a arquitetura real poll-driven de VirtIO-net, protocolos, sockets e serviços específicos, incluindo assumptions de ownership e concorrência necessárias para o comportamento atual.
