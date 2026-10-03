---
id: tcp
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
  - kernel/lang/clvm_sys.c
  - tools/test_sock_owner.c
  - tools/cfs_send.py
  - makefile
symbols:
  - tcp_checksum
  - net_tcp_xmit
  - net_tcp
  - sock_on_tcp
  - sock_tick
  - net_xfer_tcp
depends_on:
  - ipv4
related:
  - udp
  - network-stack
  - sockets
  - virtio-net
---

# Fundamentos de TCP e caminho de transferência do ChrisOS

## Escopo

ChrisOS implementa um subconjunto pequeno de TCP suficiente para alguns workflows do projeto, mas não possui um único engine TCP completo no estilo RFC.

Existem três máquinas de estado TCP distintas:

1. uma conexão global de echo na porta 7 em `net.c`;
2. a socket table genérica em `sock.c`;
3. uma conexão de transferência de arquivos na porta 9016 em `net_xfer.c`.

As três compartilham o mesmo builder de packets e a mesma geração de checksum no TX, mas mantêm connection state, receive logic, timers e semântica de aplicação separados.

Este capítulo descreve exatamente esse comportamento, sem tratar esses paths como uma implementação TCP completa.

## Dispatch de receive

IPv4 protocol 6 entra em `net_tcp`.

Depois dos checks mínimos de IPv4/TCP, a ordem efetiva é:

```text
destination port 9016
        -> net_xfer_tcp()

senão
        -> sock_on_tcp()
           se consumir, encerra

senão destination port 7
        -> TCP echo embutido

senão
        -> ignora
```

O serviço de transferência tem prioridade sobre a socket table na sua porta dedicada.

## Header TCP mínimo

Segments gerados pelo ChrisOS usam sempre header TCP de 20 bytes, sem options.

O layout é:

| Offset | Tamanho | Campo |
|---|---:|---|
| 0 | 2 | source port |
| 2 | 2 | destination port |
| 4 | 4 | sequence number |
| 8 | 4 | acknowledgment number |
| 12 | 1 | data offset + reserved |
| 13 | 1 | flags |
| 14 | 2 | window |
| 16 | 2 | checksum |
| 18 | 2 | urgent pointer |

`net_tcp_xmit` grava todos esses fields diretamente no buffer compartilhado.

## Data offset gerado

No TX, byte 12 é sempre:

```text
0x50
```

Nibble alto 5 significa cinco words, ou 20 bytes.

ChrisOS não gera options TCP como MSS, window scale, timestamps ou SACK-permitted.

No RX, os paths leem o data offset e conseguem pular headers maiores que 20 bytes, mas não interpretam as options.

## Flags

O código define os bits:

- FIN = 0x01;
- SYN = 0x02;
- RST = 0x04;
- PSH = 0x08;
- ACK = 0x10.

O TX usa combinações como SYN, SYN|ACK, ACK, PSH|ACK e FIN|ACK.

Não há suporte a ECE/CWR nem NS.

## Window fixa

Todo segment gerado anuncia:

```text
window = 65535
```

O receive window anunciado pelo peer não é usado para controlar TX.

Não existem window scaling, zero-window handling, persist timer nem advertisement dinâmico baseado no espaço real disponível.

Isso é relevante porque cada socket possui apenas 2048 bytes de RX buffer.

## Urgent data

O urgent pointer transmitido é sempre zero.

URG não é tratado pelas state machines.

Semântica de urgent data não existe nesta revisão.

## Geração do checksum TCP

O TX calcula checksum sobre o pseudo-header IPv4 padrão mais header TCP e payload.

O pseudo-header contém:

- source IPv4;
- destination IPv4;
- byte zero;
- protocol 6;
- TCP length de 16 bits.

O código soma words big-endian de 16 bits, trata byte final ímpar no high byte, faz carry folding e retorna one's complement.

`net_tcp_xmit` primeiro grava zero no field de checksum, copia payload, calcula e escreve o resultado no offset 16 do TCP.

## Gap de checksum no RX

Nenhum caminho TCP valida checksum recebido.

Echo, socket table e transfer aceitam segments sem conferir o pseudo-header checksum.

Um segment corrompido ou forjado pode entrar no estado da conexão caso os checks estruturais passem.

É uma prioridade alta de hardening.

## Builder comum de TX

`net_tcp_xmit` constrói:

```text
Ethernet
+ IPv4 de 20 bytes
+ TCP de 20 bytes
+ payload
```

O source IPv4 é sempre o endereço fixo do ChrisOS.

Ports, sequence, acknowledgment e flags são fornecidos pelo caller.

A função retorna `void`, então o caller não consegue saber se o link realmente transmitiu.

## Limite do buffer software

O builder aceita packet enquanto:

```text
14 + IPv4 total length <= 1600
```

Com headers IPv4/TCP mínimos, isso permite payload TCP de até 1546 bytes dentro de `g_tx`.

Porém, `virtio_net_tx` rejeita frames Ethernet acima de 1514 bytes, então o payload efetivo máximo com headers normais é 1460 bytes.

Um payload de 1461..1546 pode ser construído e depois rejeitado silenciosamente pelo driver através do wrapper atual.

## Contrato de payload nulo

`net_tcp_xmit` copia payload quando `payload_len > 0`.

Não existe reject explícito para pointer nulo com length não zero.

Os callers internos normalmente passam storage válido, mas o contrato não está hardened contra callers inválidos no kernel.

## Initial sequence numbers

Echo, sockets e transfer geram sequence inicial por:

```text
pit_ticks() * 2654435761
```

É determinístico em relação ao tick counter e não é um ISN criptograficamente imprevisível.

Conexões criadas em timings relacionados podem gerar sequences correlacionados.

É suficiente para ambiente experimental, não para proteção contra ataques off-path.

## Estado do echo TCP

`net.c` possui um único `TcpConn g_tcp`.

Ele guarda:

- active;
- remote MAC;
- remote IPv4;
- remote port;
- `snd_nxt`;
- `rcv_nxt`.

Somente uma conexão de echo pode existir nesse state.

Novo SYN aceito sobrescreve a conexão anterior.

## Handshake do echo

Na porta 7, SYN sem ACK inicia conexão.

ChrisOS:

1. ativa `g_tcp`;
2. salva MAC/IP/port remoto;
3. gera ISN;
4. define `rcv_nxt = incoming_seq + 1`;
5. envia SYN|ACK;
6. incrementa `snd_nxt` em um.

Um ACK-only posterior apenas gera o log `tcp established`.

O acknowledgment recebido é lido, mas não validado contra `snd_nxt`.

## Dados no echo

Para remote IP/port ativo, PSH com payload é refletido.

O código define:

```text
rcv_nxt = incoming_seq + payload_length
```

envia ACK|PSH com os mesmos bytes e incrementa `snd_nxt` pelo tamanho.

Não exige `incoming_seq == rcv_nxt` anterior.

Segments fora de ordem, duplicados ou sobrepostos não recebem semântica TCP correta.

## Vulnerabilidade de bounds no echo

O path de echo deriva payload length do IPv4 total length.

Não exige antes:

```text
14 + IPv4 total length <= tamanho real recebido
```

e depois usa `frame + payload_off` com esse tamanho para retransmitir.

Um `ip_total` forjado maior que o frame físico pode causar read fora de bounds durante o echo.

## Estados da socket table

O layer genérico implementa somente:

- FREE;
- LISTEN;
- SYN_SENT;
- ESTABLISHED.

Não existem SYN_RECEIVED, FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT, LAST_ACK, CLOSING ou TIME_WAIT.

Isso afeta handshake e teardown.

## Passive open

Um socket LISTEN é encontrado pela local destination port.

Ao receber SYN sem ACK e sem conexão existente, o código aloca child.

Esse child é imediatamente marcado ESTABLISHED, recebe parent=listener e envia SYN|ACK.

Não espera o ACK final do peer antes de considerar a conexão established.

`sock_accept` pode devolver o child antes da confirmação completa do three-way handshake.

## Active open

`sock_connect` aloca socket, marca SYN_SENT, escolhe local ephemeral port a partir de 40000, gera ISN e tenta transmitir SYN.

Se o MAC do gateway não estiver disponível, o descriptor continua alocado mas o SYN pode não sair.

Quando chega segment com:

```text
(flags & (SYN|ACK)) == (SYN|ACK)
```

o socket atualiza `rcv_nxt = seq + 1`, muda para ESTABLISHED, aprende o source MAC e envia ACK.

O acknowledgment number recebido não é comparado ao sequence esperado local.

## Retransmission de SYN

`sock_tick` roda dentro de `net_poll`.

Se o socket continuar SYN_SENT por mais de 30 ticks, o SYN é retransmitido usando o sequence original.

Não existem:

- limite de retries;
- exponential backoff;
- timeout final de connect;
- erro entregue ao caller.

O retry pode continuar indefinidamente enquanto houver polling.

## TX de dados por socket

`sock_send` exige ESTABLISHED.

Uma chamada é limitada a 200 bytes.

O segment sai como PSH|ACK.

`snd_nxt` avança imediatamente pelo número de bytes enviados.

Não existe send queue aguardando ACK.

Também não existe timer de retransmission para application data.

## Estado de último segment

Cada socket possui `last[256]`, `last_len` e `last_tick`.

`remember` salva flags e até 250 bytes do último payload.

Porém, `sock_tick` só retransmite SYN no estado SYN_SENT.

Esse estado "last" não implementa retransmission genérica de data nesta revisão.

## Sequenciamento no RX

Quando payload TCP passa o bounds check do socket path, o código faz:

```text
rcv_nxt = incoming_seq + payload_length
```

Não compara `incoming_seq` com o `rcv_nxt` esperado anterior.

Não há queue de out-of-order, duplicate detection, overlap trimming ou reassembly cumulativo.

Cada payload aceito redefine diretamente o próximo sequence esperado.

## Bounds no socket path

O path de sockets deriva payload length de IPv4 total length, mas só copia se:

```text
payload_offset + payload_length <= tamanho físico do frame
```

Isso é mais seguro que echo e transfer.

Ainda assim, checksum TCP não é validado e outros malformed-header cases dependem de validação anterior.

## Bug sob pressão do RX buffer

Cada socket tem array RX de 2048 bytes.

Se chegar payload maior que o room restante, apenas o que cabe é copiado.

Mesmo assim, `rcv_nxt` avança pelo payload completo recebido e um ACK é enviado.

O peer recebe confirmação de bytes que foram descartados.

A semântica de reliable stream quebra quando o receive buffer enche.

## Integração com blocking

Para processo nativo, payload recebido chama `proc_unblock(owner)`.

Na syscall CLVM 144, se `sock_recv_for` retorna zero, a VM passa para `CLVM_WAITING`, o processo é bloqueado com reason de socket e a syscall é preparada para retry posterior.

O buffer temporário da syscall limita send/recv CLVM a 200 bytes.

Isso coincide com o cap de `sock_send`.

## Close

`sock_close` envia FIN|ACK quando o socket está ESTABLISHED.

Logo depois marca o socket FREE.

Não existe FIN_WAIT nem espera por ACK ou FIN do peer.

FIN recebido também não leva a uma state transition de fechamento.

RST não é tratado como abort.

O teardown é apenas best-effort notification.

## FIN e RST recebidos

As constants existem, mas o receive de sockets não tem branches próprias para FIN ou RST.

Echo e transfer também não implementam teardown completo.

Um peer encerrando conexão não conduz a state machine TCP clássica.

## Flow control

O receive window do peer é ignorado.

ChrisOS sempre anuncia 65535 mesmo quando o RX buffer local está quase cheio.

Não existe backpressure coerente com a capacidade real.

Somado ao comportamento de truncar e ACKar payload completo, o flow control não é confiável.

## Congestion control

Não há congestion window, slow start, congestion avoidance, RTT estimator, retransmission timeout adaptativo, fast retransmit ou fast recovery.

TX é conduzido diretamente por application calls e pelo timer simples de SYN.

O código atual não deve ser descrito como TCP com congestion control.

## TCP options

Headers recebidos com data offset maior que 5 são simplesmente pulados.

MSS não é negociado.

Não há window scale, timestamps, SACK ou outras options.

SYN/SYN+ACK gerados não carregam MSS.

## File transfer na porta 9016

Destination TCP port 9016 ignora a socket table e entra em `net_xfer_tcp`.

Há apenas uma global transfer connection.

Novo SYN reseta estado anterior, salva remote endpoint, envia SYN|ACK e coloca o application protocol em fase HDR.

Assim como echo, não há state machine TCP completa do handshake.

## Framing CFS1

O host utility `tools/cfs_send.py` conecta por TCP e envia:

```text
"CFS1"
path length big-endian de 32 bits
file size big-endian de 32 bits
path bytes
file bytes
```

O header fixo tem 12 bytes.

O guest consome o stream pelas fases HDR, PATH, DATA e DONE.

O parser da aplicação consegue continuar um mesmo transfer através de múltiplos payloads TCP sequenciais.

## Validação do transfer

O serviço valida:

- magic CFS1;
- path length > 0 e < 512;
- file size > 0;
- file size <= limite máximo do filesystem;
- sucesso do `kmalloc`.

O arquivo completo é buffered em memória e depois gravado por `fs_write`.

Sucesso envia 0x06; erro envia 0x15.

O host Python configura timeout de 30 segundos e espera um byte de acknowledgment da aplicação.

## Gap de sequencing do transfer

`net_xfer_tcp` define `rcv_nxt = seq + payload_length` e consome payload imediatamente.

Não exige sequência in-order nem elimina retransmissions.

Um TCP segment duplicado pode inserir bytes duplicados no parser CFS1.

Entrega fora de ordem pode corromper as fases.

O application framing aceita segmentação, mas a camada TCP não oferece stream reassembly confiável.

## Vulnerabilidade de bounds no transfer

Assim como o echo, o transfer deriva payload length de IPv4 total length sem exigir primeiro que o endpoint esteja dentro do frame físico.

O range é passado a `xfer_consume`.

Um `ip_total` forjado pode provocar read além dos bytes realmente recebidos.

Precisa do mesmo hardening central de lengths.

## Evidência de ownership

`tools/test_sock_owner.c` é o principal host test de sockets desta revisão.

Ele confirma que:

- CLVM slot não fecha socket de outro slot;
- slot não aceita no listener alheio;
- cleanup por slot fecha seus sockets;
- processo nativo não fecha socket de outro processo;
- processo dono consegue fechar.

O test usa stub para `net_tcp_xmit`; não valida handshake, checksum, sequencing, retransmission ou parser TCP.

## Evidência end-to-end

O makefile faz host forwarding de TCP host port 7007 para guest 7 e host 9016 para guest 9016.

Isso permite integração de echo e CFS1.

Aplicações Browser, SSH e TLS/X25519 também usam `sock_connect`/`sock_send`.

Elas demonstram consumidores da API, não interoperabilidade TCP completa.

## Concorrência

Todos os paths TCP compartilham `g_tx`.

Echo state, socket table, transfer state e TX buffer do device não possuem locking geral cross-CPU.

O sistema depende de polling e chamadas efetivamente serializadas.

Mutação simultânea por APs arbitrários não é segura.

## Hardening recomendado

As prioridades imediatas são:

1. validar checksum TCP no RX;
2. centralizar bounds IPv4/TCP antes do dispatch;
3. rejeitar ou remontar fragments antes do TCP;
4. validar ACK numbers no handshake;
5. exigir sequence esperado e implementar reassembly;
6. respeitar capacidade real do receive buffer sem ACKar bytes descartados;
7. implementar retransmission de data e FIN;
8. processar FIN/RST e estados de close reais;
9. alinhar payload máximo ao frame Ethernet de 1514 bytes;
10. unificar echo, sockets e transfer em um único engine TCP;
11. adicionar tests determinísticos e fuzzing de malformed packets.

## Limitações atuais

O TCP atual serve para experimentos controlados do ChrisOS/QEMU, não para redes hostis ou com perdas.

Faltam checksum validation no RX, handshake completo, ordered stream reassembly, retransmission geral, timeout adaptativo, flow control correto, congestion control, options, teardown robusto, RST handling, integração PMTU e ownership SMP-safe.

Por outro lado, o projeto já possui checksum real no TX, happy-path SYN/data funcional, ownership de sockets e um fluxo útil de transferência por TCP.

Essas capacidades devem ser descritas com precisão sem sugerir um stack TCP de produção completo.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta as três máquinas TCP distintas, o builder compartilhado, o caminho CFS1 e os gaps exatos de reliability e bounds presentes no source inspecionado.
