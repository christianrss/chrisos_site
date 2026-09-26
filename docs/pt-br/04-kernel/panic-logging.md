---
id: panic-logging
lang: pt-br
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/panic.c
  - kernel/metal/panic.h
  - kernel/metal/klog.c
  - kernel/metal/klog.h
  - kernel/metal/serial.c
  - kernel/metal/serial.h
  - kernel/metal/buildid.c
  - kernel/metal/buildid.h
  - kernel/metal/syscall.c
  - kernel/metal/start.c
symbols:
  - panic
  - panic_exception
  - panic_identity
  - klog_init
  - klog_putc
  - klog_puts
  - klog_copy
  - panic_user_fault
depends_on:
  - idt-exceptions
related:
  - validation-evidence
  - process-lifecycle
---

# Panic, diagnóstico serial e kernel log

## Escopo

Logging em kernel opera justamente quando dependências comuns podem estar quebradas. Heap pode estar corrompido, filesystem ausente, gráficos falhando, interrupções inseguras e CPU em exception context. Por isso o ChrisOS mantém o fatal path pequeno e usa serial como canal de último recurso. Separadamente, mantém um ring log fixo em memória, sem alocação, que pode ser persistido em ChrisFS depois que storage fica disponível.

A arquitetura também distingue exception fatal em ring 0 de fault em processo user. A primeira paralisa a máquina; a segunda pode ser registrada e contida.

## Serial no início do boot

`kstart` inicializa serial antes da maioria dos subsistemas. Se `serial_init` falha, executa `cli` e `hlt` indefinidamente.

Assim serial é raiz do diagnóstico. Bootinfo, self-tests, device status e panic podem aparecer sem heap, filesystem ou desktop.

Quanto menos dependências o caminho de emergência tiver, menor a chance de a própria observabilidade falhar recursivamente.

## `panic`

`panic(message)` é `_Noreturn`.

Primeiro executa `cli`. Depois imprime “PANIC: ”, mensagem e identidade. Por fim entra em loop de `hlt`.

Não há branch de recuperação. Violação fatal é tratada como fail-stop para evitar continuar com invariantes desconhecidos já quebrados.

## `panic_exception`

Também é non-return. Desliga interrupções, lê CR2 e registra:
- vector;
- error;
- RIP;
- CR2.

Depois inclui identidade e halta.

CR2 é mais relevante no #PF, mas estar presente no registro padroniza diagnóstico.

## Identidade

`panic_identity` lê:
- índice da CPU;
- CR3;
- RSP;
- build ID;
- revisão Git;
- SHA-256 do kernel.

Esses dados tornam o crash revision-bound. Analisar um RIP contra source de outra compilação pode produzir diagnóstico completamente errado.

CR3 ajuda a identificar address space ativo. RSP ajuda a inferir stack/contexto.

## Por que build identity importa

Kernel layout muda com pequenas alterações. Timing e offsets também.

Um crash report sem revisão pode ser impossível de reproduzir. Ao imprimir Git/hash, o sistema conecta a falha ao binário e à documentação da mesma revisão.

## Ring klog

`klog.c` usa array estático de 8.192 bytes, posição, length, spinlock e ready flag.

`klog_init` inicializa uma vez. Não aloca e não usa filesystem.

Esse desenho permite log antes do allocator e evita que crescimento de log consuma memória sem limite.

## Escrita

`klog_putc` faz lazy init, pega lock, escreve em `g_pos`, avança modulo capacidade e aumenta length até 8192.

Depois de cheio, bytes novos sobrescrevem os mais antigos.

`klog_puts` chama putc por caractere.

Como lock é adquirido em cada caractere, dois `klog_puts` concorrentes podem intercalar mensagens por caractere. O lock protege estrutura do ring, não atomicidade de mensagens completas.

## Leitura

`klog_copy(dst, cap)` valida destino/cap/ready.

Sob lock:
- n = min(length, cap);
- start = (pos + capacity - n) % capacity;
- copia n bytes em ordem cronológica.

Isso recompõe corretamente a ordem depois do wrap.

A função retorna count e não insere NUL. Consumer deve tratar como bytes.

## Persistência no boot

Depois de storage/fs/install, `kstart` verifica backend ChrisFS. Usa buffer estático de 4096 bytes e chama `klog_copy`. Se houver dados, escreve `SYS/BOOT.LOG`.

Portanto:
- logging pode começar antes de disco;
- depois um snapshot pode ser persistido.

O snapshot é de até 4 KiB, embora ring comporte 8 KiB.

## Serial versus klog

São mecanismos distintos. Não se deve assumir que todo `serial_puts` automaticamente entra no ring sem verificar serial implementation.

`panic.c` chama serial diretamente. Isso é útil porque fatal path não depende de `g_lock` do klog. Se outro CPU morresse segurando esse lock, panic baseado obrigatoriamente em klog poderia deadlockar.

## Fault user não é panic global

`panic_user_fault` registra fault, destrói processo, loga RIP/CR2/error/CPU/build, define -11 e reescreve o frame para voltar ao kernel.

Não chama `panic`.

Assim uma aplicação inválida não derruba necessariamente todo o S.O.

## O que permanece fatal

Depois de demand paging e tratamento de origem user, exceptions abaixo de 32 chegam a `panic_exception`.

Fault não recuperável de kernel, invalid opcode privilegiado e protection fault em ring 0 param o sistema.

Em kernel experimental, continuar depois de invariantes desconhecidos pode ser mais perigoso que parar.

## Concorrência

Klog tem spinlock. Panic desliga interrupções localmente, mas não para automaticamente todos os outros CPUs.

Mais de um CPU pode tentar imprimir serial ao mesmo tempo se o driver não serializar. O número da CPU ajuda a atribuir linhas.

Kernels maduros podem eleger uma panic CPU e parar as outras. ChrisOS já tem NMI para TLB fencing, mas `panic.c` não implementa nem reivindica um protocolo completo de SMP panic stop.

## Grafo de dependência do fatal path

```text
fatal condition
    |
cli
    |
serial
    |
register/build identity
    |
hlt
```

Não depende de heap, filesystem, graphics, scheduler recovery ou userspace.

Klog normal pode ser persistido depois, mas não faz parte da cadeia mínima obrigatória do panic.

## Reprodutibilidade

Para conectar crash ao estado do sistema, os campos principais são revisão, CPU, CR3, RIP, vector/error, CR2 e RSP.

O código atual fornece esse núcleo.

Backtrace simbolizado seria útil, porém unwind confiável exige metadata e validação de stack. Não deve ser inventado a partir de um único RIP.

## Segurança

Logs de desenvolvimento revelam endereços e build identity. Em sistema multiusuário hardened, exposição desses dados teria de ser controlada.

Serial aqui é canal privilegiado de debug, não API sanitizada para aplicação.

O ring limitado evita que erro repetitivo cresça memória indefinidamente.

## Desempenho

Lock por caractere e serial character-oriented podem alterar bastante timing sob log intenso.

Para throughput alto, buffers per-CPU e records estruturados seriam alternativas, ao custo de merge/order/timestamps mais complexos.

## Validação

Testes controlados devem:
- chamar panic e confirmar halt;
- provocar exception kernel conhecida e verificar campos;
- preencher/wrapar klog;
- copiar com cap menor;
- persistir boot log em ChrisFS;
- provocar fault user e confirmar que kernel segue;
- executar writers concorrentes e checar integridade do ring;
- validar build/hash contra binário.

## Limitações atuais

Não há severity/facility estruturada, timestamp no ring, atomicidade de mensagem inteira, coordenador global de panic SMP, stack unwinder nem crash dump persistente produzido diretamente no fatal path.

A base existente ainda é sólida: serial cedo, identidade revisionada, fatal fail-stop, ring bounded sem alocação e persistência posterior.

## Mapa de fonte

Panic: `kernel/metal/panic.c`/`panic.h`. Ring: `klog.c`/`klog.h`. Serial: `serial.c`/`serial.h`. Build metadata: `buildid.c`/`buildid.h`. Fault user: `syscall.c`. Persistência: `start.c`. O Source Atlas publica tudo integralmente na revisão `da3df29cb397932c43d32373871fb9380e688ade`.
