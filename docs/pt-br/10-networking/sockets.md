---
id: sockets
lang: pt-br
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/sock.c
  - kernel/net/sock.h
  - kernel/net/net.c
  - kernel/lang/clvm_sys.c
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - tools/test_sock_owner.c
  - APPS/NET/BROWSER.CC
  - APPS/NET/SSH.CC
  - APPS/NET/TLS.CC
symbols:
  - sock_init
  - sock_listen_for
  - sock_accept_for
  - sock_connect_for
  - sock_send_for
  - sock_recv_for
  - sock_close_for
  - sock_close_slot
  - sock_close_proc
  - sock_on_tcp
  - sock_on_udp
depends_on:
  - tcp
  - udp
related:
  - network-stack
---

# Ownership e API de sockets

## Escopo

ChrisOS expõe uma pequena socket table em kernel para processos nativos e aplicações CLVM.

A API é muito menor que BSD/POSIX sockets.

Não existe uma chamada separada `socket()`, objeto de address family, integração com file descriptors genéricos, `bind()`, `sendto()`, `recvfrom()`, `select/poll/epoll` ou socket options.

As operações principais são:

- listen;
- accept;
- connect;
- send;
- receive;
- close.

Descriptors são índices diretos em um array global fixo.

A mesma tabela também é reutilizada pelo caminho UDP limitado do projeto.

## Tamanho da tabela

A implementação define:

```text
SOCK_MAX = 16
SOCK_RX  = 2048
```

O array possui dezesseis objetos `Sock`.

Porém, `alloc_sk` percorre índices 1 até 15 e nunca retorna índice zero.

Existem, portanto, no máximo quinze descriptors simultaneamente utilizáveis por aplicações.

O descriptor zero fica efetivamente reservado/não usado.

## Estrutura Sock

Cada `Sock` guarda:

- state;
- parent listener descriptor;
- remote IPv4;
- remote port;
- local port;
- remote MAC;
- send-next sequence;
- receive-next sequence;
- receive buffer de 2048 bytes;
- receive length;
- scratch de último segment com 256 bytes;
- last transmit tick;
- flag de MAC conhecido;
- owner PID de processo nativo;
- CLVM slot.

O objeto mistura transport state, buffering, ownership e retry metadata.

Não existe protocol control block separado.

## Estados implementados

Só existem quatro states:

```text
FREE
LISTEN
SYN_SENT
ESTABLISHED
```

Não há field de protocolo dizendo TCP ou UDP.

Isso importa porque o receive UDP também procura sockets LISTEN.

Um LISTEN é, portanto, um objeto sobrecarregado cujo significado depende do path de protocolo que o encontra.

## Inicialização

`sock_init` percorre os dezesseis slots e configura state como FREE.

Não zera explicitamente todos os fields de cada estrutura.

A alocação reseta os fields necessários para ownership e buffering:

- state;
- rx_len;
- last_len;
- parent;
- owner;
- slot.

Outros fields são sobrescritos depois por listen/connect/accept quando passam a ser relevantes.

Um design mais rígido deveria zerar ou inicializar completamente o objeto ao alocar.

## Alocação

`alloc_sk(owner, slot)` retorna o primeiro entry FREE entre 1 e 15.

Antes que o caller defina o estado semântico final, a função marca temporariamente o objeto como ESTABLISHED.

Callers como `sock_listen_for` e `sock_connect_for` substituem esse state imediatamente.

Quando todos os quinze slots estão ocupados, retorna -1.

Não existe crescimento dinâmico.

## Modelo de ownership

Cada socket possui duas identidades:

```text
owner = PID do processo nativo
slot  = CLVM application slot ou negativo
```

A regra de acesso fica em `fd_visible`.

Para caller CLVM com `slot >= 0`:

```text
socket.slot deve ser igual ao slot do caller
```

Para caller nativo:

```text
socket.slot < 0
e
socket.owner == proc_current()
```

A mesma tabela serve, portanto, dois domínios de ownership.

## Wrappers nativos

As funções simples:

- `sock_listen`;
- `sock_accept`;
- `sock_connect`;
- `sock_send`;
- `sock_recv`;
- `sock_close`

chamam equivalentes `*_for` com slot = -1.

Isso faz a visibilidade depender do PID atual.

Um processo nativo não consegue normalmente operar descriptor de outro processo.

## Wrappers CLVM

As syscalls CLVM usam application slot explícito.

Os cases relevantes são:

```text
140 listen
141 accept
142 connect
143 send
144 recv
145 close
146 DNS helper
```

Antes da chamada de socket, a camada CLVM executa `vm_sync_slot`.

O slot é passado para `sock_*_for`.

Isso liga o descriptor ao application slot, não apenas ao processo que hospeda a VM.

## Listen

`sock_listen_for(port, slot)` aloca descriptor, muda state para LISTEN, grava local port e limpa parent.

Não verifica se outro socket já escuta a mesma porta.

Vários LISTEN entries podem existir para o mesmo port.

`find_listen` retorna o primeiro match da tabela, então duplicate listeners não são rejeitados nem balanceados; o menor índice correspondente vence.

## Ausência de protocol binding

`sock_listen_for` não escolhe TCP ou UDP.

O mesmo LISTEN pode ser analisado por:

- `sock_on_tcp`;
- `sock_on_udp`.

A API não consegue expressar "listen somente TCP" ou "bind somente UDP".

É uma lacuna fundamental da abstração.

## Accept

`sock_accept_for` primeiro verifica ownership e exige state LISTEN.

Depois percorre toda a tabela procurando child com:

```text
child.parent == listener_fd
child.state == ESTABLISHED
```

Quando encontra, limpa `parent` e devolve o descriptor do child.

Se não houver child, retorna -1.

Não existe accept backlog explícito.

Connections pendentes são apenas entries da socket table cujo parent ainda aponta para o listener.

## ESTABLISHED antecipado

O path TCP cria child quando chega SYN.

Esse child já é marcado ESTABLISHED antes de validar o ACK final do peer.

Logo, `sock_accept` pode retornar uma conexão antes de um three-way handshake convencional estar concluído.

Isso altera materialmente o significado de "accepted".

## Connect

`sock_connect_for(ip, port, slot)` aloca descriptor e configura:

- SYN_SENT;
- remote IPv4;
- remote port;
- ephemeral local port;
- initial sequence;
- receive-next = 0;
- estado do MAC remoto/gateway.

O contador ephemeral começa em 40000.

Após wrap de 16 bits, qualquer valor abaixo de 40000 é resetado para 40000.

Não existe busca por collision antes de escolher port.

## Semântica do retorno de connect

`sock_connect_for` retorna o descriptor logo depois de tentar enviar SYN.

Não espera ESTABLISHED.

Se o MAC do gateway ainda não existir, o helper interno não envia SYN, mas o socket permanece SYN_SENT e é retornado ao caller.

`sock_tick` pode tentar novamente depois, quando o MAC estiver disponível.

Resultado não negativo significa "socket alocado e tentativa iniciada", não "conectado".

## Send

`sock_send_for` exige:

- descriptor visível;
- state ESTABLISHED;
- length não negativo.

Valores acima de 200 são truncados para 200.

O segment sai como PSH|ACK e a função retorna o length truncado.

Não espera acknowledgment.

Também não expõe falha real de link porque o chain inferior não propaga erro do device até a API.

## Gap de send buffer nulo

`sock_send_for` não rejeita `buf == NULL` quando `n > 0`.

O builder TCP inferior pode dereferenciar esse pointer.

Um caller de kernel incorreto pode gerar fault.

O path CLVM evita isso copiando memória guest validada para um buffer local de 200 bytes antes da chamada.

## Fronteira de send na CLVM

Syscall 143 limita `n` a 200.

Ela verifica:

- endereço e length não negativos;
- memória VM existente;
- range dentro da memória;
- slot synchronization.

Só depois copia bytes guest para stack buffer do kernel e chama `sock_send_for`.

A fronteira de user memory é mais forte que a API interna crua.

## Receive

`sock_recv_for` exige:

- descriptor visível;
- destination pointer não nulo;
- requested length positivo;
- state ESTABLISHED.

Sem bytes buffered, retorna zero.

Com dados, copia até o length pedido a partir do começo do array de 2048 bytes.

Depois move os bytes restantes para o início.

O receive buffer funciona como byte stream compactado, não queue de packet buffers.

## Complexidade de receive

Depois de uma leitura parcial, todos os bytes restantes são deslocados.

Uma leitura muito pequena pode custar O(bytes restantes).

Repetir reads de um byte sobre buffer cheio pode produzir custo quadrático em relação ao tamanho originalmente buffered.

Um ring buffer com head/tail evitaria essa compactação.

## Blocking para callers nativos

O wrapper nativo `sock_recv` apenas retorna zero quando não há dados.

A própria biblioteca não bloqueia o processo.

Código nativo precisa fazer polling, yield ou construir blocking em camada superior.

## Blocking para CLVM

Syscall 144 adiciona blocking em torno de `sock_recv_for`.

Quando receive retorna zero, a camada CLVM:

1. coloca a VM em `CLVM_WAITING`;
2. bloqueia o processo com `PROC_ST_BLOCK_SOCK`;
3. recoloca argumentos e número da syscall na stack da VM;
4. retorna para permitir resume posterior.

Quando chega network input, o socket path pode chamar `proc_unblock(owner)`.

Essa é a ponte entre chegada de pacote e scheduling CLVM.

## Wakeup de receive

Payload TCP chama `proc_unblock` quando `owner > 0`.

UDP faz o mesmo.

Mesmo sockets criados por CLVM guardam o native process owner atual junto com o slot.

Assim, o processo hospedando a VM pode ser acordado, enquanto o slot continua protegendo visibilidade contra outras aplicações CLVM.

## Close

`sock_close_for` verifica visibilidade.

Se o state for ESTABLISHED, envia FIN|ACK.

Logo depois marca entry FREE e configura slot = -1.

Não aguarda ACK do FIN nem shutdown remoto.

O descriptor pode ser reutilizado imediatamente.

## Cleanup no exit de processo

O teardown em `proc.c` chama:

```text
sock_close_proc(pid)
```

depois de fechar outros recursos de syscall.

`sock_close_proc` percorre sockets e fecha cada entry não FREE cujo owner seja o PID em saída.

Sockets ESTABLISHED recebem FIN|ACK best-effort antes de serem liberados.

Isso evita leakage normal de socket entries entre lifetimes de processos.

## Cleanup de CLVM slot

O cleanup de recursos CLVM chama:

```text
sock_close_slot(slot_id)
```

junto com cleanup de shader, voxel, input capture e file descriptors.

Todo socket do slot é liberado; ESTABLISHED recebe FIN|ACK best-effort.

Network resources ficam, portanto, vinculados ao lifetime do application slot.

## Evidência de ownership

`tools/test_sock_owner.c` testa diretamente as regras de acesso.

Ele prova que:

- slot 2 não fecha socket do slot 1;
- slot 2 não faz accept no listener do slot 1;
- owner slot consegue fechar seu socket;
- cleanup por slot invalida seus sockets;
- processo nativo não fecha socket de outro processo;
- processo owner consegue fechar.

É evidência host-side real para access control.

## Limites do teste

O test usa stubs para networking.

Não valida:

- handshake TCP;
- packet parsing;
- wakeup;
- port collision;
- accept backlog;
- FIN de cleanup;
- concorrência.

Ele valida apenas ownership de descriptors.

## Lookup de conexão TCP

Connections TCP estabelecidas são encontradas pelo tuple:

```text
remote IP
remote port
local port
```

PID owner e CLVM slot não entram em `find_conn`.

Normalmente local port diferencia as conexões.

Porém, duplicate listeners e collisions de ephemeral port são possíveis, então não existe uma namespace guarantee forte por owner.

## Duplicate local ports

Não há check que impeça duas aplicações de escutar o mesmo TCP port.

Também não há busca garantindo que ephemeral port esteja livre.

Isso pode gerar routing ambíguo.

O primeiro listener/connection encontrado no scan global vence.

Uma socket API robusta deveria definir binding rules e unicidade de tuples.

## Reuso de LISTEN por UDP

O receive UDP também percorre sockets LISTEN.

Como documentado no capítulo UDP, o path atual contém bug de source/destination port e não valida payload contra frame physical length.

Mesmo corrigindo esses bugs, o objeto socket ainda não guarda metadata de peer por datagram nem protocol type.

A tabela atual é muito mais orientada a TCP stream que a uma API dual-protocol real.

## Socket interno de DNS

`sock_dns` aloca um descriptor persistente interno e o coloca em LISTEN em uma ephemeral port.

O helper acessa diretamente o RX buffer sem usar os wrappers públicos de visibility.

Ele é um consumidor interno da mesma tabela global, não um resolver independente.

O bug de demultiplexação UDP impede a resposta DNS normal de chegar a esse socket na revisão inspecionada.

## Aplicações consumidoras

Algumas aplicações CLVM demonstram o uso esperado.

Browser:

- resolve `example.com`;
- conecta na porta 80;
- envia request HTTP/1.0 curto;
- recebe até 120 bytes.

O exemplo SSH conecta à porta 22 e envia banner SSH.

O exemplo TLS executa pequeno X25519 e envia 32 bytes à porta 443.

São consumidores da API e experimentos, não prova de interoperabilidade completa de TCP ou protocolos de aplicação.

## Sem file descriptor genérico

Socket descriptors são índices de `g_sk`, não entries de uma tabela POSIX unificada.

CLVM possui management separado de file descriptors para filesystem.

Não existem operações genéricas read/write/close sobre um único namespace.

A API de sockets continua explicitamente específica de rede.

## Sem multiplexação de readiness

Não há `select`, `poll`, `epoll`, event object ou callbacks de readiness.

O caller:

- tenta receive e recebe bytes/zero;
- usa blocking CLVM;
- ou faz polling na aplicação.

Isso atende os usos pequenos atuais, mas limita servidores multiplexados.

## Concorrência

A socket table inteira é global e sem locks.

Allocation, close, RX delivery, send, retry timers e cleanup podem mutar os mesmos entries.

O sistema depende de network polling e syscalls efetivamente serializados.

Acesso concorrente por múltiplos CPUs não é geralmente seguro.

Um design futuro deve usar locking ou confinar todas as transições de socket a um único execution context.

## Prioridades de correção

As melhorias de maior impacto são:

1. adicionar protocol/type explícito;
2. definir política e rejeitar duplicate TCP listeners quando necessário;
3. garantir ephemeral-port uniqueness;
4. separar "descriptor alocado" de "connect concluído";
5. validar send buffer nulo;
6. substituir compactação de RX por ring/queue;
7. considerar accepted apenas após handshake válido;
8. implementar close/error states reais;
9. preservar boundaries e peer metadata de UDP;
10. adicionar locking ou execution-context confinement;
11. ampliar host tests para lifecycle, blocking, collisions e receive.

## Nota de revisão

Este capítulo foi criado contra a revisão ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Ele documenta a socket table fixa de 16 entries, regras de ownership native/CLVM, descriptors por índice, bridge de blocking, cleanup hooks e limitações do modelo de protocolo presentes na implementação atual.
