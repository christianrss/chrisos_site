---
id: testing-validation
lang: pt-br
type: guide
status: maintained
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - docs/development/testing.md
  - scripts/qemu.mk
  - makefile
depends_on:
  - build-run-debug
---

# Testes e validação

O ChrisOS utiliza várias classes de teste porque nenhum ambiente único consegue provar todas as afirmações de um sistema operacional. Testes host validam lógica sem boot do kernel; gates QEMU exercitam caminhos do guest em dispositivos emulados; ChrisVM testa o modelo de máquina mantido pelo projeto; somente uma máquina física identificada produz evidência de hardware.

O teste escolhido deve corresponder à afirmação realizada.

## Hierarquia de evidência

| Classe | O que estabelece | O que não estabelece |
|---|---|---|
| source presente | implementação textual existe | execução correta |
| host-tested | lógica host executou e passou | integração guest/hardware |
| QEMU-tested | caminho declarado executou em máquina virtual | hardware arbitrário |
| ChrisVM-tested | passou no emulador/modelo próprio | equivalência com QEMU/hardware |
| hardware-tested | executou em hardware identificado | compatibilidade universal |

Use a classe mais estreita que prova a afirmação e amplie quando a mudança cruza mais fronteiras.

## Gates host

O conjunto amplo é:

~~~bash
make host-gates
~~~

Existem targets mais específicos para filesystem, compilador, runtime, gráficos/matemática e outros componentes. Durante iteração, prefira o target mais próximo do código alterado.

Quando disponíveis:

~~~bash
make host-sanitize
make host-stress
~~~

Sanitizers complementam testes funcionais; não substituem expectativas semânticas.

## Gates QEMU

O conjunto amplo é:

~~~bash
make qemu-gates
~~~

Os gates mantidos usam TCG, salvo targets que declarem outra necessidade. Isso mantém boa parte da integração utilizável sem KVM.

Targets individuais incluem:

~~~bash
make test-qemu-ata
make test-qemu-ahci
make test-qemu-nvme
make test-qemu-vblk
make test-qemu-usb
make test-qemu-gpu
make test-qemu-xhci
make test-qemu-safe
make test-qemu-install
~~~

O runner grava a serial e verifica marcadores. Timeout ou marcador ausente deve ser analisado pelo log, não reduzido a "QEMU falhou".

## ChrisVM

Para o emulador/modelo de máquina:

~~~bash
make chrisvm-test
~~~

Mudanças em ChrisCPU, buses, device models, boot ou tracing devem normalmente começar por esse conjunto.

Um passe no ChrisVM e um passe no QEMU são evidências independentes. Mantê-las separadas ajuda a localizar defeitos no guest, emulador ou contrato de hardware virtual.

## VirGL

VirGL depende de capacidades do host:

~~~bash
make test-qemu-virgl
~~~

O target pode retornar skip. Registre skip como "não testado neste host", nunca como passe. Se o PR altera código específico de VirGL e o autor não tem host compatível, a lacuna de evidência deve ser declarada.

## Validação ampla

Uma sequência ampla local pode ser:

~~~bash
make host-gates
make qemu-gates
make chrisvm-test
~~~

O repositório também oferece:

~~~bash
make full-gates
~~~

Use validação ampla antes do merge para mudanças de grande alcance, mas localize primeiro regressões com testes estreitos.

## Hardware físico

Hardware exige contexto:

~~~text
Máquina/placa:
CPU:
Firmware e modo:
Storage/controller:
GPU/display:
USB/rede relevantes:
Commit:
Procedimento:
Resultado:
Evidência serial:
~~~

Um gate de driver no QEMU não comprova compatibilidade com implementações físicas arbitrárias do mesmo padrão.

## Testes negativos

Código de sistemas deve testar falhas, não apenas sucesso. Casos relevantes incluem metadata malformada, exaustão de alocação, input truncado, descriptors inválidos, dispositivos opcionais ausentes e writes que falham.

Quando já existe um target negativo, execute-o. Quando uma mudança cria uma nova fronteira de erro importante, prefira adicionar regressão focada a apenas documentar uma suposição não testada.

## Registro exato

Um PR deve registrar exatamente o que foi executado:

~~~text
Host:
Commit:
Compiler:
QEMU:
Testes:
Resultados: PASS / FAIL / SKIP
Não testado:
~~~

Evite "todos os testes passaram" quando apenas um subconjunto foi executado.

## Limitações de CI

CI hospedado executa um subconjunto e não deve ser considerado cobertura automática de todos os caminhos QEMU, gráficos, virtualização ou hardware.

Ausência de target no CI não autoriza omitir validação. Significa que a lacuna deve ser declarada e, quando possível, acompanhada de comando local determinístico para outro mantenedor reproduzir.

## Regressões

Ao corrigir bug, um bom teste deve falhar no comportamento antigo e passar no novo. Prefira testes próximos do invariante quebrado. Um panic visto apenas após longa sessão de desktop pode ter uma causa host-testable pequena.

Testes de regressão também funcionam como documentação executável: codificam condições que devem sobreviver a refactors futuros.

## Interpretação correta de sucesso

Build verde significa que o toolchain produziu artefatos. Teste host verde significa que uma lógica host selecionada executou corretamente. Gate QEMU verde significa que um caminho virtual declarado atingiu os marcadores esperados. ChrisVM verde significa que o emulador passou seus testes. Hardware verde significa observação em uma configuração física específica.

Essas afirmações devem permanecer separadas para impedir que presença de código ou um único ambiente seja promovido a uma capacidade mais ampla do que a evidência suporta.
