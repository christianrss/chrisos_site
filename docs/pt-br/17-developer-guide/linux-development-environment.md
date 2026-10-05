---
id: development-environment-linux
lang: pt-br
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/environment.md
  - scripts/check-dev-env.sh
  - .cursor/install.sh
  - makefile
depends_on:
  - developer-guide
---

# Ambiente de desenvolvimento Linux

O host de referência do ChrisOS é uma instalação Debian ou Ubuntu x86-64 recente. As instruções operacionais do repositório são escritas para esse ambiente e esse é o caminho com menor diferença entre a linha de comando documentada e o build real.

O build combina compilação de kernel freestanding, utilitários host, criação de ISO, manipulação de imagens de disco e validação em QEMU. Instalar apenas GCC não é suficiente.

## Pacotes básicos

Em Debian ou Ubuntu:

~~~bash
sudo apt update
sudo apt install   build-essential   binutils   nasm   xorriso   qemu-system-x86   qemu-utils   python3   git
~~~

O gate de integração do instalador também utiliza OVMF:

~~~bash
sudo apt install ovmf
~~~

Esses pacotes fornecem as ferramentas principais verificadas por scripts/check-dev-env.sh: Git, GNU Make, GCC, GNU ld, NASM, xorriso, QEMU x86-64 e Python 3.

Após instalar:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
./scripts/check-dev-env.sh
~~~

Se o script indicar uma ferramenta obrigatória ausente, resolva o problema do host antes de investigar código do sistema operacional. Uma dependência host ausente não é evidência sobre o ChrisOS.

## Seleção do compilador

O contrato geral exige GCC, mas não fixa globalmente uma única versão para todo workstation. O bootstrap de agentes em .cursor/install.sh seleciona GCC 11 porque versões mais novas produziram, naquele baseline de automação, um warning promovido a erro em uma compilação host do ChrisC.

Isso representa uma configuração conhecida como funcional para a automação; não significa que todo desenvolvedor deva substituir o GCC padrão do sistema.

Comece com:

~~~bash
gcc --version
make
~~~

Se a falha for especificamente um warning dependente da versão do compilador promovido pela política de warnings-as-errors, preserve o diagnóstico, registre a versão e compare com o caminho conhecido usando GCC 11. Não desative warnings globalmente apenas para obter build verde.

## Capacidades opcionais

O checker separa ferramentas opcionais das obrigatórias.

O bring-up RISC-V utiliza Clang/LLD e precisa de qemu-system-riscv64 para executar o guest. Os nomes de pacotes variam entre distribuições.

ChrisVM pode utilizar SDL quando sdl2-config está presente; testes headless não dependem disso.

VirGL exige mais que simplesmente possuir QEMU instalado. O QEMU do host precisa oferecer dispositivo VirtIO GPU com GL, e o host precisa fornecer um caminho de display/OpenGL utilizável. O target test-qemu-virgl detecta ausência de capacidade no host e retorna skip, em vez de transformar incapacidade do host em falha do guest.

## KVM

O checker testa /dev/kvm separadamente:

~~~bash
test -r /dev/kvm -a -w /dev/kvm   && echo "KVM usable"   || echo "KVM unavailable"
~~~

KVM é uma capacidade de aceleração, não requisito para todos os testes. O make run interativo solicita KVM na revisão analisada; os gates headless em scripts/qemu.mk usam TCG.

Isso permite executar integração mesmo em máquinas sem virtualização por hardware disponível ao usuário.

Se /dev/kvm existir mas não puder ser acessado, investigue configuração de virtualização e permissões do dispositivo. Evite usar QEMU como root como solução rotineira.

## Checkout e artefatos

Use um clone normal:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
git status
~~~

A árvore gerada inclui:

| Caminho | Função |
|---|---|
| build/obj/ | objetos de kernel/compiler |
| build/iso/ | filesystem temporário da ISO |
| build/os.iso | imagem bootável |
| build/disk.img | workspace ChrisFS |
| build/host/ | utilitários e testes host |
| build/user/ | binários user-mode |
| build/chrisvm/ | executável e fixtures ChrisVM |

Tudo isso é reproduzível e deve permanecer fora dos commits.

## Primeiro build

Uma sequência inicial útil é:

~~~bash
./scripts/check-dev-env.sh
make
make disk.img
make test-qemu-ata
~~~

Cada etapa prova algo diferente: presença do ambiente, compilação e geração de imagem, criação do disco de workspace e um smoke test guest com TCG e marcadores seriais.

Somente depois desse baseline funcionar o caminho interativo deve ser usado como ambiente de depuração:

~~~bash
make run
~~~

## Outras distribuições

Outras distribuições Linux podem hospedar o projeto, mas não existe hoje receita oficial para cada gerenciador de pacotes. Traduza capacidades, não nomes de pacotes. O contrato obrigatório é a lista de comandos verificada por check-dev-env.sh; OVMF, SDL, VirGL e RISC-V são capacidades adicionais.

Ao relatar problema em distribuição diferente, inclua:

~~~bash
./scripts/check-dev-env.sh
gcc --version
ld --version | head -n 1
nasm -v
qemu-system-x86_64 --version | head -n 1
git rev-parse HEAD
~~~

Inclua também o target exato e o primeiro erro relevante. A última linha retornada por make normalmente contém menos informação que o primeiro erro de compilador, linker, xorriso ou QEMU.

## Identidade das ferramentas e PATH

Quando existem várias instalações de compiler, QEMU ou Python, registre qual executable o shell realmente seleciona.

Checks úteis:

~~~bash
command -v gcc
command -v ld
command -v qemu-system-x86_64
command -v python3
~~~

Não presuma que instalar um pacote alterou o executable usado pelo terminal atual. Diferenças de PATH explicam por que dois ambientes aparentemente iguais podem produzir diagnostics, capabilities de QEMU ou comportamento Python diferentes.

## Reprodutibilidade do host

Evite alterar silenciosamente flags ou ferramentas para conseguir um passe local. O repositório utiliza warnings-as-errors em componentes importantes e targets determinísticos para vários subsistemas.

Se uma configuração local exige mudança, determine se é apenas um problema de setup ou um defeito de portabilidade que deve ser corrigido no projeto.

Um ambiente útil não é aquele que faz qualquer comando passar a qualquer custo; é aquele cujas diferenças são explícitas o suficiente para outro desenvolvedor reproduzir o resultado.
