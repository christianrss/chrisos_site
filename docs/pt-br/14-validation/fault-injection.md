---
id: fault-injection
lang: pt-br
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/test_cfs_host.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_elf.c
  - user/fault.asm
  - tools/qemu_gate.py
  - scripts/qemu.mk
  - kernel/metal/panic.c
  - kernel/fs/storage.c
symbols:
  - panic
  - panic_exception
  - storage_format_if_empty
depends_on:
  - host-tests
  - qemu-gates
  - hardware-gates
related:
  - fuzzing
  - performance-measurement
  - process-isolation
  - chrisfs
---

# Testes negativos e injeção de falhas

## Escopo

Fault injection responde a uma pergunta diferente do teste de caminho feliz:

> O que o ChrisOS faz quando um recurso, input, device, allocation ou invariant esperado falha?

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, o ChrisOS já possui mecanismos úteis de testes negativos, mas ainda não tem um framework geral de fault injection compartilhado por todo o kernel.

Os mecanismos atuais são locais e determinísticos:

- falha de block I/O em LBA escolhido;
- budget limitado de allocations durante carregamento ELF;
- images ELF deliberadamente malformadas;
- ELF de userspace que gera fault proposital;
- topologias QEMU negativas, como boot sem o root ATA normal;
- detecção de fatal markers nos testes integrados QEMU.

Isso cobre caminhos importantes, mas não permite afirmar cobertura sistemática de falhas do kernel inteiro.

## Modelo de falha

Um modelo útil separa falhas por fronteira:

| Fronteira | Falha | Evidência atual |
|---|---|---|
| Storage | read/write retorna I/O error | host test ChrisFS |
| Memory allocation | page allocation indisponível | ELF malformed/fuzz |
| Executable format | offsets/sizes/flags inválidos | malformed ELF |
| Privilege boundary | userspace acessa endereço inválido | fault ELF |
| Device topology | device esperado ausente | QEMU no-ATA |
| Kernel safety | panic/exception/corruption marker | QEMU fatal scan |

A meta não é gerar falha arbitrária, mas quebrar uma premissa por vez e verificar se o subsistema preserva seu contrato.

## Determinismo

Os melhores testes negativos atuais são determinísticos.

Com a mesma revisão e input, a mesma operação falha no mesmo ponto.

Isso é essencial porque uma falha não reproduzível custa muito mais para depurar.

Um experimento pode ser modelado como:

[
F = (R, S, P, E)
]

onde:

- (R) é a revisão;
- (S) é o estímulo injetado;
- (P) é o ponto de injeção;
- (E) é o resultado observável esperado.

Um injector randômico futuro deve sempre registrar seed e schedule escolhidos.

## Injeção de I/O no ChrisFS

`tools/test_cfs_host.c` contém o mecanismo mais claro de fault injection atual.

O fake block device usa:

    g_fail_lba

`fake_read` e `fake_write` retornam `BD_EIO` quando o range solicitado contém o LBA selecionado.

Assim o teste força storage failure sem modificar a implementação do ChrisFS.

Essa separação é importante: o filesystem de produção recebe um block-device error normal por sua própria interface.

## Falha de mount

O teste formata device válido e define:

    g_fail_lba = CFS_SUPER_LBA

O mount deve retornar:

    CFS_EIO

Depois o fault é removido e o teste confirma que mount volta a funcionar.

Isso prova:

1. propagação correta em vez de classificação como erro de formato;
2. ausência de estado permanente corrompido após a falha.

## Falha no caminho de escrita

O mesmo teste injeta falha em:

    CFS_BITMAP_LBA

A escrita de `Z.TXT` deve retornar:

    CFS_EIO

Isso exercita erro abaixo do caminho de allocation/update do filesystem.

A cobertura ainda é estreita: um único LBA falha, não cada possível write de uma transação multietapas.

## Mídia desconhecida

Outro teste negativo não simula perda de I/O.

Os primeiros bytes do fake disk recebem `0xFF`.

O prepare deve retornar:

    CFS_EFORMAT

sem modificar a mídia.

O invariant de segurança é:

> mídia desconhecida não equivale a mídia vazia.

Isso impede que conteúdo não reconhecido seja formatado silenciosamente.

## Exaustão de recursos

A suíte também cria muitos arquivos e testa limites de file size e name length.

São boundary tests negativos, não faults sintéticos.

Mesmo assim pertencem à mesma família porque forçam control-flow raro e verificam erros definidos em vez de corrupção de metadata.

## ELF malformado

`tools/test_elf_malformed.c` constrói images ELF64 inválidas de forma precisa.

Os casos incluem:

- arquivo truncado;
- magic ELF inválido;
- program-header offset com overflow;
- `filesz > memsz`;
- virtual-address overflow;
- file-offset overflow;
- load segment de tamanho zero;
- segment fora do user range permitido;
- load segments sobrepostos;
- program-header type não suportado;
- segment simultaneamente writable e executable;
- entry point não executável.

Esses são testes estruturados.

Para invariants conhecidos, são mais fortes que bytes randômicos porque cada input tem uma rejeição esperada.

## Injeção de allocation failure

O teste ELF também implementa budget de pages.

`pmm_alloc` retorna zero quando o budget acaba.

No caso `oom mid`:

    g_budget = 1

enquanto a image exige mais memória.

A falha deve deixar zero page leak e nenhum current process residual.

O invariant é:

[
Delta pages = 0
]

depois de load rejeitado.

Assim OOM deixa de ser suposição e passa a ser evidência executável.

## ELF fuzz sob pressão de memória

`tools/test_fuzz_elf.c` reutiliza o budget durante inputs pseudo-randômicos.

Cada iteração registra pages em uso, reduz budget, chama o loader real e verifica cleanup em caso de falha.

O teste combina:

- binary data malformado;
- disponibilidade parcial de recursos.

Essa combinação é importante porque cleanup bugs frequentemente aparecem depois que algumas allocations já ocorreram.

## ELF de userspace deliberadamente faltoso

`user/fault.asm` produz ELF válido cuja primeira ação relevante é:

    mov rax, [0]

Depois existe sequência normal de exit que não deveria ser atingida se isolation/fault delivery funcionarem.

A fixture é útil para testar o caminho real de privilege/fault handling.

Sozinha, porém, não é um host fault-injection gate automatizado.

A evidência depende de como a image é executada e do que o kernel registra.

## Diagnóstico fatal

Quando ocorre condição fatal, a camada de panic registra contexto arquitetural ligado à revisão.

`panic` inclui:

- CPU;
- CR3;
- RSP;
- Build ID;
- Git;
- kernel SHA-256.

`panic_exception` adiciona:

- vector;
- error code;
- RIP;
- CR2.

Um sistema de injection deve preservar esse output integralmente.

## Rejeição de fatal markers no QEMU

`tools/qemu_gate.py` falha runs contendo:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

Isso não injeta falha.

É o **oracle** que impede que uma falha seja escondida por marker positivo anterior.

Experimento negativo precisa de estímulo e de oracle confiável.

## Topologia negativa

`test-qemu-noata` remove o caminho normal ATA.

O sistema precisa registrar:

    ata missing

e ainda alcançar root AHCI, mount ChrisFS e desktop.

Isso é melhor classificado como **negative topology testing** do que device fault injection.

Nenhum comando ATA falha no meio da execução; o device simplesmente não existe na topologia.

## Safe mode como controle

O gate safe-mode confirma boot com várias capacidades opcionais reduzidas/desabilitadas.

Safe mode não é fault injection, mas funciona como experimento de controle após falhas envolvendo SMP, APIC, áudio, rede ou JIT.

Uma campanha de faults deve ter configuração reduzida conhecida para facilitar localização.

## Classes ainda ausentes

O repositório ainda não oferece mecanismo geral para injetar sistematicamente:

- falha em cada allocation point;
- short reads/writes;
- partial DMA completion;
- controller timeout;
- interrupt perdido;
- interrupt duplicado;
- interrupt atrasado;
- MMIO failure;
- PCI config corrompido;
- packet loss/reordering/corruption;
- power loss durante update do filesystem;
- CPU stop/start anômalo;
- preemption do scheduler em pontos escolhidos;
- failures aleatórios de APIs do kernel.

São áreas de roadmap.

## Crash consistency

O experimento de storage mais importante ainda ausente é crash/power-loss controlado.

Filesystem pode propagar `EIO` corretamente e ainda corromper estado caso execução pare entre updates de metadata.

Um harness futuro deve:

1. partir de image conhecida;
2. executar uma filesystem operation;
3. interromper guest em write/flush boundary controlada;
4. rebootar a image resultante;
5. executar fsck;
6. validar estados antigos/novos permitidos;
7. rejeitar estados intermediários impossíveis.

Isso é diferente de apenas retornar `BD_EIO`.

## Cobertura por pontos de injection

Uma métrica futura útil é fault-point coverage.

Para (N) pontos explícitos:

[
C_f = rac{N_{exercised}}{N}
]

Cada ponto deve ter:

- stable ID;
- subsystem;
- operation;
- estado default disabled;
- condição determinística de ativação;
- resultado esperado;
- cleanup invariant.

Sem IDs estáveis, campanhas são difíceis de comparar entre revisões.

## API futura

Uma facility test-only poderia expor conceitualmente:

    fault_point("pmm.alloc")
    fault_point("bdev.read")
    fault_point("bdev.write")
    fault_point("irq.delivery")
    fault_point("net.rx")

A implementação normal desabilitada deve ter impacto semântico mínimo.

A test build poderia selecionar:

- falhar na N-ésima chamada;
- falhar em intervalo;
- falhar somente para device;
- atrasar em vez de falhar;
- corromper campo controlado.

O estado de injeção nunca deve ser habilitado silenciosamente em artifact normal.

## Segurança

Fault injection pode ser destrutivo.

Testes em storage físico devem usar mídia descartável ou clone.

Builds com test hooks precisam ser claramente identificadas.

Um gate deve separar:

    expected injected failure
    unexpected kernel failure
    test infrastructure failure

Agrupar os três elimina valor diagnóstico.

## Relação com fuzzing

Fault injection e fuzzing se sobrepõem, mas não são iguais.

Fault injection controla **falhas ambientais/de recursos**.

Fuzzing altera o **input space**.

ELF malformado combinado com OOM usa as duas técnicas.

Separar os conceitos ajuda a identificar se um bug vem do parser, da pressão de recursos ou da interação.

## Resumo da cobertura atual

Na revisão `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, há evidência negativa relevante para:

- propagação de I/O no ChrisFS;
- rejeição de mídia desconhecida;
- limites de capacidade do filesystem;
- validação estrutural ELF;
- cleanup ELF sob allocation failure;
- cleanup com ELF malformado/randômico;
- fixture explícita de page fault em userspace;
- topologia sem ATA;
- fatal-marker rejection no QEMU.

Ainda não existe scheduling de injection para kernel inteiro nem power-failure consistency testing.

## Próximos passos

Prioridade recomendada:

1. Nth-call allocation failure genérico e determinístico;
2. short/error/flush injection no block device;
3. crash-consistency do ChrisFS;
4. reset QEMU em checkpoints de storage;
5. hooks de drop/delay de interrupts em test builds;
6. injection IDs estruturados no log;
7. sweep automático por todos os fault points;
8. execução com sanitizers onde aplicável;
9. retenção automática do primeiro seed/point que falha;
10. somente depois fault experiments físicos em mídia/hardware dedicados.

## Ativação determinística e artifacts de falha

Uma campanha de faults é mais útil quando a mesma source revision e a mesma regra de ativação reproduzem a mesma transition defeituosa.

Prefira controles determinísticos como:

    falhar operação X na chamada N
    falhar block request em uma faixa de LBA
    esgotar allocation budget após K pages bem-sucedidas

em vez de failure randômica sem registro.

Quando randomização for útil, seed e caso gerado precisam ser retidos.

A primeira execução que falha deve preservar contexto suficiente para reprodução:

- source revision;
- identidade do injection point;
- activation count ou seed;
- machine/test configuration;
- serial ou host log;
- disk/image mutada quando aplicável;
- oracle esperado;
- exit status observado.

Sem esse artifact bundle, uma falha rara pode ficar indistinguível de ruído da infraestrutura de teste.

Determinismo também permite medir a correção: depois do fix, o mesmo ponto anteriormente defeituoso deve passar antes de retomar exploração randômica mais ampla.

## Nota de revisão

Este capítulo foi reconciliado contra ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

O projeto já exercita caminhos negativos importantes, principalmente I/O do ChrisFS e rejeição/cleanup ELF. A limitação principal é arquitetural: são mecanismos locais de teste, ainda não um framework sistemático de fault injection para todo o kernel.
