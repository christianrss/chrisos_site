---
id: developer-guide
lang: pt-br
type: guide
status: maintained
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - CONTRIBUTING.md
  - docs/README.md
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - docs/development/workflow.md
  - docs/development/testing.md
depends_on: []
---

# Guia do desenvolvedor

Este guia é o ponto de entrada canônico para compilar, executar, testar e contribuir com o ChrisOS. O ambiente de desenvolvimento é tratado como um sistema de engenharia reproduzível, não apenas como uma lista de pacotes. O toolchain do host produz um kernel x86-64 freestanding e utilitários host; o QEMU fornece modelos de máquina controlados para testes de integração; o ChrisVM fornece o caminho de máquina/emulação mantido pelo próprio projeto; e Git mais os gates de teste definem como uma alteração se transforma em evidência revisável.

Comandos operacionais que podem mudar junto com a árvore de código permanecem próximos do source no repositório ChrisOS. Este guia explica como esses comandos se relacionam, quais configurações de host são caminhos de referência, como classificar falhas e qual evidência um contribuidor deve produzir antes de abrir um pull request.

## Modelo de host de referência

O caminho de menor atrito é um sistema Debian ou Ubuntu x86-64 recente. Em Windows, o caminho recomendado é WSL2 com uma distribuição Ubuntu para executar o build orientado a GNU. Shells Windows nativos não são hoje o ambiente de referência porque o build principal assume GNU Make, GCC/binutils, NASM, utilitários de shell, xorriso e fluxos de QEMU orientados a Linux.

Essa diferença é importante. Um ambiente pode conseguir compilar arquivos C sem reproduzir o fluxo completo do ChrisOS. O desenvolvimento também inclui criação de ISO, manipulação de imagens de disco, testes host, dispositivos virtuais do QEMU, aceleração KVM opcional, testes UEFI com OVMF e caminhos gráficos como VirGL.

| Configuração de host | Build | Testes host | Gates QEMU headless | QEMU interativo | Estado |
|---|---:|---:|---:|---:|---|
| Debian/Ubuntu x86-64 | sim | sim | sim | sim | referência |
| Windows + WSL2 Ubuntu | sim | sim | sim com QEMU instalado | depende do host | caminho suportado |
| Shell Windows nativo | não canônico | não canônico | não canônico | específico do helper | não é referência |
| Outras distribuições Linux | geralmente | geralmente | depende dos pacotes | depende do host | mantido pela comunidade |

## Fluxo de desenvolvimento

Uma contribuição normal deve seguir uma progressão estreita para ampla:

~~~text
clone
  ↓
verificar ferramentas do host
  ↓
compilar o alvo mais estreito
  ↓
executar o teste mais específico
  ↓
inspecionar evidência serial/teste
  ↓
executar gates mais amplos
  ↓
atualizar documentação canônica quando o comportamento mudar
  ↓
abrir pull request focado
~~~

A primeira verificação é:

~~~bash
./scripts/check-dev-env.sh
~~~

O script verifica git, make, gcc, ld, nasm, xorriso, qemu-system-x86_64 e python3. Também informa capacidades opcionais, como QEMU RISC-V, Clang/LLD, SDL e acesso a /dev/kvm.

O build básico é:

~~~bash
make
~~~

O alvo padrão produz build/os.iso. A imagem persistente do workspace ChrisFS pode ser criada com:

~~~bash
make disk.img
~~~

O caminho interativo é:

~~~bash
make run
~~~

Na revisão analisada, esse alvo solicita KVM. Ausência de /dev/kvm utilizável não deve ser tratada como falha do kernel. Os gates QEMU headless mantidos pelo projeto usam TCG e são o caminho portátil de validação:

~~~bash
make test-qemu-ata
make qemu-gates
~~~

## Próximos capítulos

Use [Ambiente Linux](linux-development-environment.md) para workstation Linux nativa e [Windows e WSL2](windows-wsl-development-environment.md) para desenvolvimento a partir de Windows. Em seguida, [Build, execução e depuração](build-run-debug.md) descreve artefatos, modos de execução, logs seriais e a separação entre falha do host e falha do guest.

[Testes e validação](testing-validation.md) define a hierarquia de evidência. [Fluxo de contribuição](contribution-workflow.md) define branches, escopo, propriedade da documentação e conteúdo esperado de PRs. [Troubleshooting de desenvolvimento](troubleshooting.md) mapeia sintomas para a primeira camada que deve ser investigada.

## Propriedade da documentação

O ChrisOS separa documentação operacional da árvore de source e documentação técnica canônica.

O repositório ChrisOS mantém instruções que precisam acompanhar nomes exatos de comandos: setup, build, execução, targets de teste, mecânica de contribuição e segurança. O chrisos_site mantém arquitetura, comportamento dos subsistemas, interfaces, interpretação de validação, pesquisa, conteúdo educacional e este guia de desenvolvimento.

Uma alteração que muda um comando deve atualizar a documentação operacional do source. Uma alteração que muda arquitetura ou comportamento deve atualizar o site canônico. Mudanças relevantes podem exigir ambos.

## Evidência antes de conveniência

Os ambientes de execução provam coisas diferentes. Um teste host prova lógica executada no host. Um gate QEMU prova um caminho do guest em uma configuração virtual declarada. Testes ChrisVM provam comportamento no emulador/modelo de máquina do projeto. Evidência de hardware exige uma máquina física identificada.

Não reduza tudo a "funciona". Um registro útil contém:

~~~text
Commit:
Host:
Versões de compiler/ferramentas:
Comando:
Resultado:
Marcador serial/teste relevante:
Não testado:
~~~

Em hardware físico, registre também firmware e dispositivos relevantes.

## Saída gerada

A árvore build/ é descartável. Ela contém objetos, imagens de boot, binários host, logs, binários user e artefatos ChrisVM. ISO, imagens de disco, objetos e logs transitórios não devem entrar em commits.

Use:

~~~bash
make clean
~~~

quando artefatos antigos forem uma causa plausível.

## Disciplina de escopo

ChrisOS inclui kernel, memória, storage, filesystem, linguagens/runtime, gráficos, desktop, rede, ferramentas nativas e emulação. Antes de alterar código, identifique o subsistema proprietário do comportamento e evite cruzar fronteiras arquiteturais apenas para fazer um sintoma local desaparecer.

Uma alteração útil deve ser estreita o suficiente para que sua afirmação possa ser testada. Uma mudança em VirtIO-GPU deve preferir o gate específico de GPU antes da suíte inteira; uma mudança em resolução de caminhos ChrisFS deve preferir o teste host relevante antes de um boot completo.

O ambiente de desenvolvimento faz parte do método de engenharia: ele existe para tornar cada afirmação reproduzível, revisável e ligada a uma revisão específica do source.
