---
id: udp
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
  - makefile
symbols:
  - net_udp_echo
  - net_udp_send
  - sock_on_udp
  - sock_dns
depends_on:
  - ethernet
  - ipv4
related:
  - network-stack
  - tcp
  - sockets
---

# UDP

## Escopo

ChrisOS implementa um caminho UDP sobre IPv4 pequeno, usado principalmente para:

- echo UDP embutido na porta 7;
- entrega de um datagrama para a socket table do projeto;
- datagramas de saída usados por helpers como o client DNS.

A implementação é deliberadamente mínima.

Não existe API completa de datagram sockets com peer addressing, filas de packets, validação de checksum, multicast, política de broadcast ou demultiplexação independente do restante do stack.

O RX segue:

```text
Ethernet 0x0800
    |
    v
IPv4 protocol 17
    |
    v
net_udp_echo()
    |
    +-- destination port 7 --> echo reply
    |
    +-- outra porta --> sock_on_udp()
```

No TX, `net_udp_send` constrói Ethernet, IPv4 e UDP diretamente no buffer compartilhado.

## Header UDP

O header UDP possui oito bytes:

| Offset | Tamanho | Significado |
|---|---:|---|
| 0 | 2 | source port |
| 2 | 2 | destination port |
| 4 | 2 | UDP length |
| 6 | 2 | checksum |

Todos os integers são big-endian.

O length inclui header de oito bytes e payload.

## Entrada de receive

O dispatch IPv4 chama `net_udp_echo` quando protocol byte 9 vale 17.

A função exige pelo menos 42 bytes recebidos:

```text
14 Ethernet
20 IPv4 mínimo
 8 UDP
```

Depois confirma IPv4 version 4 e recalcula IHL a partir do packet.

IHL precisa ser ao menos 20 e o frame físico precisa conter Ethernet + IHL + header UDP completo.

## Destination local

Antes de escolher o port, o caminho UDP exige destination IPv4 igual ao endereço fixo do ChrisOS, 10.0.2.15.

Isso importa porque o dispatcher IPv4 genérico não centraliza essa validação.

UDP aplica seu próprio local-address check.

Não existe comportamento específico para IPv4 broadcast ou multicast.

## Echo na porta 7

Destination UDP port 7 é tratado pelo echo service embutido.

Nesse path, `net_udp_echo` lê:

- source port no offset UDP 0;
- destination port no offset 2;
- length no offset 4.

A resposta inverte source/destination ports, responde ao source IPv4 e usa o source MAC Ethernet como destino.

O payload é copiado sem alteração.

Para input bem formado, o resultado é um echo UDP convencional.

## Bounds do echo

O path de echo exige UDP length ao menos 8.

Payload offset é:

```text
14 + IHL + 8
```

e payload length é:

```text
UDP length - 8
```

Depois aplica dois checks físicos:

```text
14 + IPv4 total_length <= tamanho do frame recebido
payload_offset + payload_length <= tamanho do frame recebido
```

Esses checks evitam que o echo copie bytes além do que foi realmente entregue pelo driver.

## Inconsistência entre layers

O echo não exige igualdade estrita entre IPv4 total length e UDP length.

Não existe check:

```text
IPv4 total_length == IHL + UDP length
```

Um packet malformado com lengths inconsistentes ainda pode ser aceito se os dois bounds independentes contra o frame físico passarem.

Uma validação mais forte deve relacionar:

- bytes físicos recebidos;
- IPv4 total length;
- UDP length.

## Checksum UDP no TX

Todos os paths atuais de UDP escrevem zero no checksum:

- replies do echo;
- `net_udp_send`.

Em UDP/IPv4, checksum zero significa checksum omitido.

Isso é permitido pelo protocolo IPv4, mas remove detecção end-to-end de corrupção no nível UDP.

ChrisOS não possui gerador de UDP pseudo-header checksum nesta revisão.

## Checksum UDP no RX

O checksum UDP recebido também não é validado.

Checksum não zero é ignorado.

Checksum zero é aceito.

O stack depende, portanto, da integridade oferecida pelas camadas inferiores e pelo ambiente virtual.

Uma implementação hardened deve calcular pseudo-header checksum quando o field recebido for diferente de zero.

## API de transmissão

A função de baixo nível é:

```text
net_udp_send(dst_ip, src_port, dst_port, payload, payload_len)
```

Retorna -1 quando:

- rede não está ready;
- destination IP é nulo;
- payload supera 1400 bytes;
- MAC do gateway ainda não foi aprendido.

Nos demais casos constrói um datagram e retorna o payload length pedido.

## Contrato do payload pointer

`net_udp_send` valida `dst_ip`, mas não valida `payload` quando `payload_len > 0`.

O loop de cópia dereferencia o pointer diretamente.

Caller que usar payload nulo com tamanho não zero pode gerar fault em kernel.

A API deveria exigir explicitamente length zero ou payload não nulo.

## Budget de tamanho

O application payload máximo é 1400 bytes.

Os tamanhos resultantes são:

```text
UDP:       8 + 1400 = 1408
IPv4:     20 + 1408 = 1428
Ethernet: 14 + 1428 = 1442
```

O frame fica abaixo do limite 1514 do VirtIO driver.

Diferente do helper TCP bruto atual, UDP mantém margem conservadora abaixo do link limit.

## Routing pelo gateway

Todo `net_udp_send` usa o único MAC de gateway cacheado.

O destination IPv4 pode variar, mas Ethernet destination não muda com base em decisão local-subnet/off-subnet.

Não existe route table nem subnet-mask calculation.

O código pressupõe a topologia QEMU simples.

## Dependência de ARP

Se o gateway MAC ainda não estiver válido, `net_udp_send` retorna -1.

UDP não dispara ARP request automaticamente.

O datagram também não fica queued enquanto a resolução ocorre.

DNS e outros clients UDP têm, portanto, a precondição escondida de que o gateway MAC já tenha sido aprendido.

## Gap de sucesso no TX

Depois de construir o packet, `net_udp_send` chama `net_send_frame`.

Esse wrapper ignora o resultado de `virtio_net_tx`.

A função retorna payload length mesmo se a transmissão foi recusada pelo device.

Um retorno positivo significa que o packet chegou ao send call, não que o frame foi efetivamente transmitido.

## Dispatch de portas não-echo

Se destination port não for 7, `net_udp_echo` chama:

```text
sock_on_udp(frame, n)
```

e retorna.

Não existe outro service registry UDP.

A socket table recebe, portanto, todo o tráfego UDP não-echo.

## Socket sem tipo de protocolo

A estrutura `Sock` não contém field identificando TCP ou UDP.

Um socket LISTEN é reconhecido somente por state e local port.

O mesmo state LISTEN é usado também pela lógica TCP.

A abstração atual não separa explicitamente "UDP socket" de "TCP listening socket".

Isso é uma limitação estrutural da API.

## Bug crítico no offset do port

A implementação atual de `sock_on_udp` contém um bug direto de demultiplexação.

O código faz:

```text
dport = be16(udp + 0)
```

mas offset zero do UDP é **source port**.

Destination port fica no offset 2.

Depois esse valor incorreto é usado para:

- rejeitar ports abaixo de 40000;
- encontrar socket LISTEN cujo local port seja igual.

Na prática, o código compara remote source port com local listener port.

## Consequência para DNS

O helper DNS cria um local ephemeral port 40000+ e envia query ao server port 53.

Uma resposta DNS normal possui:

```text
source port      = 53
destination port = local ephemeral
```

Como `sock_on_udp` lê offset zero, enxerga 53, rejeita por ser menor que 40000 e não entrega a resposta ao socket DNS.

Na revisão inspecionada, o receive path planejado de DNS está quebrado para respostas normais.

O primeiro fix correto é ler destination port de `udp + 2`.

## Bug de bounds no socket UDP

`sock_on_udp` recebe o comprimento físico `n`, mas o descarta explicitamente com:

```text
(void)n;
```

Payload length é derivado somente do UDP length field e depois copiado, limitado apenas pelo RX buffer de 2048 bytes.

O caller garante que existe ao menos header UDP, mas o field de length ainda pode afirmar que há mais payload que o frame físico.

Isso permite read além do RX descriptor.

É um problema de memory-safety hardening.

## Semântica de entrega ao socket

Para um LISTEN socket "matching", payload UDP só é copiado quando:

```text
socket.rx_len == 0
```

Se já houver dados não lidos, o novo datagram não entra em queue.

Não existe ring de datagrams nem fila de mensagens.

Packets sucessivos podem ser descartados simplesmente porque o application ainda não consumiu o anterior.

## Fronteiras de datagram

O RX array armazena somente payload e um length.

Não preserva:

- source IPv4;
- source port;
- destination address;
- metadata por datagram.

Como só existe uma mensagem por vez, `rx_len` implicitamente representa o tamanho do datagram.

Porém, `sock_recv` pode ler parcialmente e compactar o restante, aproximando a API de um byte stream.

Não é semântica convencional de UDP socket.

## Limite de receive

`SOCK_RX` vale 2048.

`sock_on_udp` limita a cópia a esse tamanho.

Com packets válidos sob o Ethernet MTU atual, UDP payload deveria ser menor que isso.

O cap de 2048 é mais relevante para length malformado ou transports futuros do que para datagrams normais de 1500-byte Ethernet.

## Wakeup de processo

Depois de copiar payload, se o socket tiver owner de processo nativo positivo, `proc_unblock(owner)` é chamado.

Isso conecta receive de rede ao scheduler/process blocking.

Ownership de CLVM slot também existe, mas o helper só chama diretamente `proc_unblock` para owner process positivo.

## Construção do DNS query

`sock_dns` cria query DNS em buffer local de 128 bytes.

Usa:

```text
transaction ID = 0x1234
flags          = 0x0100
QDCOUNT        = 1
QTYPE          = A
QCLASS         = IN
server         = 10.0.2.3:53
```

Labels do hostname são codificados diretamente.

O source port vem do ephemeral counter global.

## Limites do parser DNS

Mesmo após corrigir UDP demultiplexing, o parser DNS é propositalmente simples.

Ele percorre bytes da resposta a partir do offset 12 procurando padrão type A/class IN.

Depois assume positions relativas fixas e lê quatro bytes de endereço.

Não implementa robustamente:

- transaction-ID matching;
- traversal de compression pointers;
- parser formal de question/answer sections;
- validação completa de flags/counts.

É um helper de projeto, não resolver DNS completo.

## Ephemeral ports

O contador ephemeral começa em 40000.

É compartilhado por TCP connect e pelo listener interno de DNS.

Ao ultrapassar 65535 e voltar para valor abaixo de 40000, o código restaura 40000.

Não existe busca de collision antes de escolher a nova porta.

Um socket novo pode teoricamente reutilizar port já ativo.

## Ausência de retransmission

UDP não possui estado de retransmission.

`net_udp_send` constrói uma única mensagem e retorna.

O helper DNS não implementa timeout/retry robusto na revisão inspecionada.

Perda de datagram precisa ser resolvida por lógica superior, que atualmente é limitada.

## Sem bind/connect UDP dedicado

O header público de sockets oferece operações genéricas listen/connect/send/recv.

Não existe `bind`, `sendto` ou `recvfrom` específicos de UDP.

Receive UDP é conectado a LISTEN sockets de portas altas.

TX explícito usa diretamente `net_udp_send`.

Não há API que retorne peer address/port junto com o datagram recebido.

## Concorrência

UDP compartilha o global `g_tx[1600]` com ARP e TCP.

A socket table também é global.

Não existe lock específico de UDP.

Transmitters concorrentes podem corromper packet construction.

Receive/socket operations simultâneos podem disputar `rx_len` e payload.

A operação normal depende do modelo serializado de polling/system call.

## Prioridades de segurança

Os fixes de maior prioridade são claros:

1. corrigir destination-port offset em `sock_on_udp`;
2. validar UDP length contra frame físico e IPv4 total length;
3. rejeitar UDP length < 8 antes de qualquer payload access;
4. validar checksum quando não zero;
5. exigir payload não nulo para TX com length > 0;
6. propagar status real do link-layer TX;
7. preservar datagram boundaries e source metadata;
8. adicionar queue bounded de receive em vez de buffer único.

## Evidência de validação

Não existe `test_udp.c` dedicado na árvore inspecionada.

O echo da porta 7 e QEMU port forwarding oferecem evidência end-to-end do happy path.

O DNS helper pretendia exercer UDP client-side, mas o bug source-port/destination-port impede que ele seja evidência válida de demultiplexação UDP por socket.

A documentação precisa distinguir esses dois fatos.

## Testes recomendados

Uma suite UDP determinística deve incluir:

- datagram mínimo de oito bytes;
- payload zero;
- decode exato de source/destination ports;
- echo port 7;
- checksum zero em IPv4;
- checksum não zero válido após implementação;
- UDP length abaixo de oito;
- UDP length maior que frame físico;
- UDP length maior que IPv4 total length;
- padding Ethernet depois do IPv4 total length;
- listener em destination ephemeral port;
- resposta DNS source 53 → destination 40000+;
- novo datagram com payload anterior ainda não lido;
- payload nulo com send length não zero;
- gateway MAC indisponível;
- falha de TX do device.

## Limitações atuais

UDP é um caminho narrow e somente IPv4.

Não existe geração/validação de UDP checksum, IPv6 UDP, queue de datagrams, multicast API, política de broadcast, source metadata, sendto/recvfrom ou seleção geral de interface/routing.

O path de echo embutido é mais robusto que o UDP via socket.

O erro de offset na demultiplexação e a ausência de physical-length check são problemas de correção da revisão atual, não apenas features futuras.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta tanto o path funcional de echo UDP quanto o path genérico de socket/DNS atualmente quebrado, incluindo o erro exato source-port/destination-port e o gap de receive bounds.
