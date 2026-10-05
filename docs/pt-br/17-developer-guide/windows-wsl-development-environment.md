---
id: development-environment-windows
lang: pt-br
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - scripts/check-dev-env.sh
  - run.bat
  - makefile
depends_on:
  - developer-guide
---

# Ambiente de desenvolvimento Windows e WSL2

O caminho recomendado em Windows é usar WSL2 com uma distribuição Ubuntu. O build do ChrisOS é orientado ao ecossistema GNU e documentado contra ferramentas Linux; WSL2 permite executar esse ambiente a partir de um workstation Windows sem reconstruir o projeto sobre PowerShell, MSYS2 ou MinGW.

Compilar, executar testes headless e iniciar uma máquina virtual interativa acelerada são capacidades diferentes. WSL2 pode atender às duas primeiras mesmo quando KVM ou gráficos interativos não estiverem disponíveis.

## Toolchain dentro do WSL2

Depois de instalar WSL2 e Ubuntu pelo fluxo suportado pelo Windows, abra o shell Ubuntu e instale os mesmos pacotes do host Linux:

~~~bash
sudo apt update
sudo apt install   build-essential   binutils   nasm   xorriso   qemu-system-x86   qemu-utils   python3   git   ovmf
~~~

Clone e verifique dentro do WSL:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
./scripts/check-dev-env.sh
~~~

O checker é a referência do projeto para disponibilidade das ferramentas obrigatórias e informa capacidades opcionais separadamente.

## Local do repositório

Para um build fortemente Linux, prefira manter a árvore dentro do filesystem Linux do WSL, por exemplo abaixo do home:

~~~bash
cd ~
git clone https://github.com/christianrss/ChrisOS.git
~~~

Isso preserva bits de execução, permissões, semântica de paths e comportamento de shell e reduz diferenças de filesystem.

Editores Windows podem abrir a árvore via integração WSL. A fronteira importante é que Git, Make, GCC, xorriso, Python e QEMU que operam sobre o projeto sejam as versões Linux.

## O que run.bat realmente faz

O repositório possui run.bat, mas ele é apenas um helper fino:

~~~text
@echo off
REM Boot ChrisOS via make (build/os.iso + build/disk.img)
make run
~~~

Esse arquivo não implementa um toolchain Windows nativo. Ele delega para Make. Se o shell Windows não possuir o conjunto GNU, xorriso e QEMU configurados de maneira compatível, o ambiente continua incompleto.

Por isso o caminho canônico de Windows é WSL2.

## Build e smoke test no WSL2

Use a mesma sequência do Linux:

~~~bash
./scripts/check-dev-env.sh
make
make disk.img
make test-qemu-ata
~~~

O último comando é particularmente útil porque o gate mantido utiliza TCG. TCG emula CPU por software e não depende de /dev/kvm.

Um gate passando comprova mais do que compilação: os artefatos foram gerados, QEMU iniciou na configuração declarada, o guest executou e os marcadores seriais esperados foram observados.

## KVM no WSL2

O make run interativo solicita KVM na revisão analisada. A presença e acessibilidade de /dev/kvm dependem da configuração de virtualização do Windows/WSL e devem ser detectadas, não presumidas.

Verifique:

~~~bash
./scripts/check-dev-env.sh
ls -l /dev/kvm 2>/dev/null || true
~~~

Se KVM não estiver disponível, uma falha de aceleração no make run é uma limitação do host, não regressão do kernel. Use gates TCG para validação portátil.

É possível derivar um comando QEMU local usando TCG para investigação, mas um comando ad-hoc não equivale a um target mantido pelo projeto.

## Display e WSLg

QEMU interativo exige também um backend de display. O makefile usa uma configuração orientada a GTK e contém uma observação sobre SDL para ambientes Windows sem GTK.

WSLg pode executar aplicações GUI Linux, mas as capacidades reais dependem do QEMU instalado e do stack gráfico do host. Separe suporte a display de compilação e execução headless.

Para kernel, memória, filesystem, rede e a maioria dos drivers, os gates headless devem ser a primeira validação.

## VirGL

VirGL adiciona requisitos gráficos específicos. O gate verifica se QEMU oferece dispositivo VirtIO GPU com GL e se existe caminho EGL ou GTK utilizável.

Um skip de VirGL significa que o host não forneceu o ambiente necessário. Não significa que o guest passou nem falhou.

## Arquitetura recomendada

~~~text
Windows
├─ navegador e GitHub
├─ editor / IDE
└─ integração WSL
      ↓
WSL2 Ubuntu
├─ git
├─ make
├─ gcc / ld
├─ nasm
├─ xorriso
├─ python3
└─ qemu-system-x86_64
      ↓
artefatos e logs do ChrisOS
~~~

Essa divisão mantém a conveniência do desktop Windows e a semântica do build Linux.

## Finais de linha e permissões

Não converta scripts shell para CRLF em alterações não relacionadas. Não remova bits de execução. Se um script existente retornar erro de interpretador, examine formato do arquivo e permissões antes de modificar sua lógica.

Evite também patches dominados por reformatação automática não relacionada ao objetivo da contribuição.

## Estado do Windows nativo

Um caminho Windows nativo completo exigiria contrato mantido e testado para compiler/linker, Make ou runner equivalente, scripts shell, ferramenta de ISO, Python, QEMU, paths e testes.

Enquanto isso não existir, não deve ser declarada paridade Windows nativa.

Melhorias de portabilidade são válidas quando preservam o caminho Linux de referência e incluem evidência reproduzível do novo ambiente.

## Critério mínimo de prontidão

Um workstation Windows/WSL2 está pronto para contribuições normais quando executa:

~~~bash
./scripts/check-dev-env.sh
make
make test-qemu-ata
make host-gates
~~~

Para mudanças em ChrisVM:

~~~bash
make chrisvm
make chrisvm-test
~~~

KVM, VirGL, RISC-V e hardware físico são capacidades adicionais, não requisitos universais.
