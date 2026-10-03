---
id: ipv4
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/sock.c
  - kernel/net/net_xfer.c
  - makefile
symbols:
  - ip_build
  - ip_checksum
  - csum16
  - net_ipv4
  - net_udp_send
  - net_tcp_xmit
depends_on:
  - ethernet
related:
  - udp
  - tcp
  - sockets
  - network-stack
---

# IPv4 e endereçamento

## Escopo

ChrisOS implementa uma camada IPv4 compacta suficiente para o ambiente QEMU VirtIO-net atual.

O stack consegue:

- construir headers IPv4 para UDP e TCP;
- calcular checksum do header IPv4;
- despachar pacotes IPv4 recebidos para UDP ou TCP;
- reconhecer pacotes endereçados ao IPv4 local fixo;
- usar um único MAC de gateway aprendido para tráfego de saída.

Não existe route table geral, DHCP, fragmentation/reassembly IPv4, ICMP, path-MTU discovery, gerenciamento multicast ou neighbor-resolution completo.

O fluxo atual é:

    Ethernet EtherType 0x0800
            |
            v
        net_ipv4()
        /        \
       v          v
     UDP          TCP

No TX:

    builder UDP/TCP
         |
         v
      ip_build()
         |
         v
    frame Ethernet
         |
         v
    VirtIO-net TX

## Endereçamento fixo

O endereço local está compilado em `net.c`:

    10.0.2.15

O gateway configurado é:

    10.0.2.2

Esses valores correspondem ao ambiente QEMU user-network usado pelo projeto.

Não existe cliente DHCP nem configuração runtime da interface nesta camada.

`net_our_ip` retorna os quatro bytes do endereço local.

## Layout do header IPv4

O builder de transmissão sempre produz header IPv4 de 20 bytes sem options.

O layout é:

| Offset | Tamanho | Campo |
|---|---:|---|
| 0 | 1 | version + IHL |
| 1 | 1 | DSCP/ECN |
| 2 | 2 | total length |
| 4 | 2 | identification |
| 6 | 2 | flags + fragment offset |
| 8 | 1 | TTL |
| 9 | 1 | protocol |
| 10 | 2 | header checksum |
| 12 | 4 | source address |
| 16 | 4 | destination address |

`ip_build` grava todos esses fields explicitamente.

## Version e IHL

No TX, byte zero é:

    0x45

O nibble alto 4 identifica IPv4.

O nibble baixo 5 representa cinco words de 32 bits, ou 20 bytes.

ChrisOS nunca gera IPv4 options.

No RX, UDP e TCP calculam:

    ihl = (ip[0] & 0x0F) * 4

e exigem `ihl >= 20`.

IHL maior que 20 é usado apenas para localizar o transport header; os bytes de options não são interpretados.

## DSCP e ECN

Byte um no TX é sempre zero.

Não existe política de differentiated services nem explicit congestion notification.

Bits DSCP/ECN recebidos são ignorados.

## Total length

`ip_build` grava o tamanho IPv4 total fornecido pelo caller em bytes 2..3 em big-endian.

Em pacotes normais:

    total_length = header IPv4 de 20 bytes + transport header + payload

UDP e TCP calculam esse valor antes de chamar `ip_build`.

O field é 16-bit, mas os limites práticos vêm muito antes por causa do frame Ethernet e buffers estáticos.

## Identification

O identification transmitido é:

    pit_ticks() & 0xFFFF

Ele usa os 16 bits baixos do contador de ticks.

Pacotes criados no mesmo tick podem receber o mesmo valor.

Como todos os pacotes transmitidos usam Don't Fragment, o stack atual não depende desse field para reassembly local.

Não deve ser interpretado como identificador globalmente único.

## Flags e fragment offset

O builder escreve:

    ip[6] = 0x40
    ip[7] = 0x00

Isso representa flag Don't Fragment ativa e fragment offset zero.

ChrisOS transmite apenas datagrams não fragmentados e pede à rede que não os fragmente.

Não existe fallback de fragmentation local.

## Gap de fragments no RX

O receive não rejeita packets fragmentados.

Ele não verifica More Fragments nem fragment offset antes de entregar bytes a UDP/TCP.

Essa é uma limitação importante de correção e segurança.

Um fragment diferente do primeiro não começa com transport header, mas o parser atual ainda pode interpretar seus primeiros bytes como UDP ou TCP.

Não existe tabela de reassembly, timeout, política para overlap nem tratamento de duplicate fragments.

Um design hardened deve:

1. rejeitar explicitamente todos os fragments; ou
2. implementar reassembly validado antes do dispatch de transporte.

## TTL

TTL transmitido é fixo em:

    64

TTL recebido não é validado nem decrementado porque ChrisOS não age como router IPv4 nesse caminho.

Também não existe ICMP Time Exceeded.

## Protocol

O stack reconhece:

    17 -> UDP
     6 -> TCP

`net_ipv4` lê o byte 9 e despacha somente esses dois protocols.

Outros valores são ignorados silenciosamente.

Não existe handler ICMP.

## Source e destination addresses

`ip_build` copia quatro bytes de origem e quatro de destino para o header.

Pacotes normais de saída usam o endereço local fixo.

Handlers UDP/TCP de entrada exigem destination igual a 10.0.2.15 antes de processar seus paths de serviço.

Source IP é aceito do packet recebido e reaproveitado nas respostas.

## Onde destination é validado

`net_ipv4` não verifica destination address.

A checagem `ip_is_us(ip + 16)` acontece nos handlers UDP e TCP.

A responsabilidade de validar o destino está, portanto, distribuída na camada de transporte em vez de centralizada no IPv4.

Se novos protocols forem adicionados a `net_ipv4`, eles também precisarão repetir essa validação ou o check deverá ser movido para a camada IPv4.

## Internet checksum

ChrisOS gera checksum de header no estilo one's complement.

`csum16`:

1. lê words 16-bit em big-endian;
2. soma em accumulator de 32 bits;
3. se sobrar um byte, coloca-o na parte alta;
4. faz carry fold até restarem 16 bits;
5. retorna o complemento de um.

Para TX IPv4, `ip_checksum` primeiro zera bytes 10 e 11 e calcula sobre o comprimento do header.

O path gerado sempre usa 20 bytes.

## Gap de checksum no RX

O receive nunca valida o checksum do header IPv4.

Um packet com header corrompido ainda pode chegar ao parsing UDP/TCP se os checks de tamanho seguintes passarem.

Esse é um gap importante de validação.

A implementação de checksum existente pode ser reutilizada, mas o verifier de RX não deve modificar bytes não confiáveis enquanto valida.

Um path read-only separado seria preferível.

## Fronteira mínima de RX

`net_ipv4` exige apenas:

    14 bytes Ethernet + 20 bytes IPv4 mínimo = 34 bytes

antes de ler protocol.

A função não valida diretamente:

- version;
- IHL;
- total length;
- header checksum;
- flags/fragment offset;
- TTL;
- destination address.

Parte desses checks é adiada para UDP/TCP.

## Checks do caminho UDP

O path UDP faz validação estrutural IPv4 mais forte que `net_ipv4`.

Ele exige:

- version 4;
- IHL ao menos 20;
- bytes suficientes para Ethernet + IHL + 8-byte UDP header;
- destination IP igual ao local.

Ele também lê `ip_total` e rejeita quando:

    14 + ip_total > tamanho real recebido

antes de aceitar o payload do echo.

Isso impede um total-length maior que o RX buffer nesse path direto.

## Inconsistência de lengths no UDP

O código UDP não exige consistência completa entre:

- IPv4 total length;
- IHL;
- UDP length.

Ele valida UDP length e bounds físicos separadamente, mas não exige:

    ip_total == ihl + udp_len

nem obriga o fim do datagram UDP a coincidir exatamente com o fim indicado pelo IPv4.

É menos grave que o gap TCP porque o payload é conferido contra o frame real, mas combinations malformadas ainda não são rejeitadas sistematicamente.

## Checks do caminho TCP

O path TCP exige:

- ao menos 54 bytes;
- IPv4 version 4;
- IHL ao menos 20;
- bytes suficientes para IHL + TCP mínimo de 20;
- destination IP igual ao local.

Depois lê o TCP data offset para encontrar o payload.

## Gap de segurança no total length TCP

O echo TCP calcula payload length a partir de `ip_total`:

    payload_len = 14 + ip_total - payload_off

quando o endpoint do total length fica depois do header TCP calculado.

Porém, não exige antes:

    14 + ip_total <= tamanho real recebido

Um packet forjado com IPv4 total length maior que o frame físico pode produzir payload length lógico que ultrapassa os bytes realmente recebidos.

O transfer path em `net_xfer.c` segue padrão semelhante.

É um gap concreto de hardening e memória segura que deve ser corrigido antes de tratar o stack como robusto contra packets hostis.

## Modelo de routing

ChrisOS não possui route table nem subnet mask nesta camada.

`net_udp_send` sempre exige o MAC cacheado do gateway configurado.

Não distingue:

- destination no mesmo subnet;
- destination fora do subnet.

Todo tráfego UDP client é enviado ao mesmo gateway MAC.

Isso funciona no QEMU user-network atual, mas não é routing IPv4 geral.

## Dependência do gateway

Se `g_gw_mac_valid` for false, `net_udp_send` retorna -1.

Como documentado em Ethernet, o stack atual não possui builder geral de ARP request.

Tráfego IPv4 de saída depende, portanto, do MAC do gateway já ter sido aprendido por atividade ARP recebida.

Não existe queue de packets aguardando neighbor resolution.

## Limite do UDP transmitido

`net_udp_send` limita application payload a:

    1400 bytes

O packet IPv4 resultante pode chegar a:

    20 IP
    + 8 UDP
    + 1400 payload
    = 1428 bytes

Com header Ethernet de 14 bytes, o frame máximo é 1442 bytes, abaixo do limite de 1514 bytes do driver.

Existe margem intencional abaixo do payload IP clássico de 1500 bytes.

## Mismatch de tamanho no TX TCP

`net_tcp_xmit` aplica outro limite:

    14 + ip_total <= NET_TX_BUF

com `NET_TX_BUF = 1600`.

Isso permite construir frames de até 1600 bytes.

Entretanto, `virtio_net_tx` rejeita frames Ethernet acima de 1514 bytes.

Payloads TCP acima de aproximadamente 1460 bytes podem caber em `g_tx`, mas serem recusados pelo driver.

Como `net_send_frame` ignora o return do driver, essa falha não chega ao caller.

É um mismatch de MTU entre camadas.

## Ausência de PMTU discovery

ChrisOS não trata ICMP Fragmentation Needed nem implementa path-MTU discovery.

Como DF=1 é usado em todo packet gerado, um datagram grande não pode ser fragmentado localmente e também não é automaticamente reduzido com base em feedback ICMP.

O limite pequeno do UDP evita o problema nesse caminho.

TCP depende dos callers respeitarem o MTU efetivo.

## Options IPv4

TX nunca gera options.

RX consegue pular um header acima de 20 bytes porque UDP/TCP usam IHL para localizar transport data.

O conteúdo das options não é interpretado nem validado.

Options malformadas são essencialmente tratadas como bytes opacos.

Como checksum de RX não é validado, nem esses bytes recebem proteção de integridade na camada IPv4.

## Ausência de ICMP

Não existe ICMP echo, destination unreachable, time exceeded ou fragmentation needed.

As consequências incluem:

- ausência de resposta a ping;
- ausência de protocol-unreachable;
- ausência de path-MTU discovery;
- ausência de TTL-expiry messaging;
- ausência de network-layer error reporting para sockets.

Por isso o ambiente atual depende de topologia QEMU conhecida e serviços fixos.

## Forwarding

ChrisOS não encaminha packets IPv4 entre interfaces.

Existe uma única instância VirtIO-net e nenhum router state.

Packets que não entram nos paths locais são ignorados.

TTL nunca é decrementado por essa implementação.

## Broadcast e multicast

Não há política explícita de IPv4 broadcast ou multicast em `net.c`.

Handlers de transporte esperam principalmente destination igual ao endereço unicast local.

Não existe IGMP nem membership table.

## Memória e ownership

Parsing IPv4 é zero-copy em relação ao frame Ethernet recebido do VirtIO.

Pointers para o IP header só permanecem válidos enquanto o RX descriptor estiver sob ownership do stack.

Handlers processam synchronously e copiam estado persistente, como IPs remotos, para estruturas próprias.

TX reutiliza o mesmo `g_tx[1600]` global descrito no capítulo Ethernet.

Não existe allocation por packet IPv4.

## Concorrência

IPv4 TX/RX compartilha estado mutável com Ethernet e transport layers.

Não existe lock protegendo `g_tx`, gateway state ou o estado simples da conexão TCP embutida.

O modelo de polling serializa a operação normal.

Callers concorrentes em APs diferentes poderiam competir durante a construção de packets.

O subsystem de rede não é SMP-safe geral nesta revisão.

## Complexidade

Construção do header IPv4 é O(1), excluindo montagem do payload em camadas superiores.

Checksum é O(IHL), que no TX atual é sempre 20 bytes.

Dispatch RX é O(1).

Não existe route-table lookup, reassembly search, neighbor-table search ou option processing.

A simplicidade é deliberada, mas deixa várias responsabilidades padrão fora da implementação.

## Ambiente QEMU

A execução padrão usa QEMU user networking com VirtIO-net.

O guest fixo 10.0.2.15 e gateway 10.0.2.2 seguem esse ambiente.

Host forwarding dá acesso a serviços TCP/UDP do guest.

Echo e file transfer bem-sucedidos demonstram que os headers IPv4 gerados são utilizáveis nesse ambiente.

Não provam interoperabilidade geral em redes roteadas arbitrárias.

## Evidência de validação

Não existe `test_ipv4.c` dedicado na árvore inspecionada.

A evidência atual é indireta:

- UDP echo usa headers gerados por `ip_build`;
- TCP echo e transfer usam o mesmo builder;
- QEMU port forwarding exercita RX e TX;
- paths de socket/DNS dependem de packets IPv4 de saída.

O parser ainda não possui suite sistemática de malformed headers.

## Testes recomendados

Uma suite IPv4 determinística deve verificar:

- bytes exatos do header de 20 bytes produzido por `ip_build`;
- known checksum vectors;
- version diferente de 4;
- IHL menor que 5 e IHL maior que o frame;
- header checksum inválido;
- total length menor que IHL;
- total length maior que o frame recebido;
- total length inconsistente com UDP/TCP;
- DF, MF e fragment offsets não zero;
- TTL zero;
- protocols desconhecidos;
- destination diferente do IP local;
- TCP com total length forjado maior que RX frame;
- TX com payload 1460 e 1461 bytes para expor a fronteira do driver.

## Limitações atuais

O IPv4 atual é estático e orientado ao QEMU.

Não existe DHCP, route table, subnet mask logic, ICMP, fragmentation/reassembly, PMTU discovery, multicast control, forwarding, checksum validation de RX ou normalização robusta de lengths antes do transport dispatch.

Packets gerados são mais simples e melhor restringidos do que packets aceitos no RX.

As prioridades imediatas de hardening são:

1. validar checksum IPv4;
2. rejeitar ou remontar fragments;
3. centralizar version/IHL/total-length validation;
4. garantir `ip_total <= bytes recebidos`;
5. alinhar limite TCP com o MTU Ethernet real.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta o builder IPv4 de endereço fixo e o receive dispatch exatamente como implementados, incluindo gaps de fragmentation, checksum, routing, MTU e malformed lengths ainda não resolvidos.
