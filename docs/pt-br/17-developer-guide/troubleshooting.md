---
id: development-troubleshooting
lang: pt-br
type: guide
status: maintained
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - docs/development/testing.md
  - scripts/check-dev-env.sh
  - scripts/qemu.mk
  - makefile
depends_on:
  - build-run-debug
---

# Troubleshooting de desenvolvimento

Depurar o ChrisOS fica mais simples quando a falha é classificada por camada antes de alterar código. Um comando pode falhar no ambiente host, compiler, linker, construtor de imagem, processo QEMU, boot, kernel, driver, filesystem, emulador ou expectativa do teste.

A primeira tarefa é localizar a camada mais antiga que deixou de se comportar como esperado.

## Comece pelo checker

Execute:

~~~bash
./scripts/check-dev-env.sh
~~~

Se uma ferramenta obrigatória estiver ausente, resolva isso antes de investigar guest.

Registre versões quando a falha puder ser específica do host:

~~~bash
gcc --version
ld --version | head -n 1
nasm -v
qemu-system-x86_64 --version | head -n 1
git rev-parse HEAD
~~~

A revisão do source e versões das ferramentas fazem parte do bug report.

## Comando inexistente

Ausência de gcc, ld, nasm, xorriso, qemu-system-x86_64 ou python3 é falha de setup host. Use os capítulos de Linux ou WSL2.

Não altere o Makefile apenas para contornar dependência obrigatória ausente, salvo se o objetivo for melhorar portabilidade intencionalmente.

## Warnings promovidos a erro

O build utiliza diagnostics estritos em componentes host. Se um compilador mais novo diagnosticar algo novo, preserve a mensagem completa.

Verifique primeiro se o warning revela bug real. O bootstrap de agentes registra GCC 11 como configuração conhecida para um caminho sensível, mas suprimir warnings globalmente não é correção aceitável.

## Erros de linker

Símbolos indefinidos normalmente pertencem a uma destas classes:

- objeto necessário não entrou no link;
- declaration/definition divergem;
- lógica condicional de build excluiu fonte necessária;
- uma camada arquitetural passou a depender de símbolo que não deveria possuir.

Investigue o primeiro símbolo e seu proprietário antes de adicionar objetos ou bibliotecas indiscriminadamente.

## Falha de xorriso ou ISO

Se compilação termina e criação de ISO falha, o kernel pode estar correto. Verifique xorriso, assets Limine e a árvore temporária da ISO.

Mantenha falha de construção de imagem separada de falha de boot.

## make run encerra imediatamente

Sem saída serial do ChrisOS, examine primeiro o startup do QEMU.

Causas comuns:

- /dev/kvm ausente ou inacessível;
- backend de display não suportado;
- imagem ausente ou antiga;
- dispositivo opcional não suportado pelo QEMU do host;
- capacidade gráfica/GL ausente.

Use um gate TCG headless:

~~~bash
make test-qemu-ata
~~~

Se ele passar enquanto make run falha antes da serial, a investigação pertence principalmente à configuração interativa do host.

## KVM indisponível

KVM é opcional para gates TCG. Sem /dev/kvm:

~~~bash
make test-qemu-ata
make qemu-gates
~~~

continuam sendo caminhos válidos.

Não execute QEMU como root apenas para obter acesso sem entender o problema de permissões.

## Timeout em gate QEMU

Abra build/qemu-test.txt e identifique o último marcador observado. "Chegou até X e não atingiu Y" é mais informativo que "QEMU travou".

Repita o target estreito antes de mudar código. Se o timeout for determinístico, instrumente a transição entre o último marcador e o esperado.

## Panic depois da serial iniciar

Depois que a serial do ChrisOS aparece, o guest está executando. Preserve panic e mensagens anteriores.

Mapeie o último subsistema concluído para a área proprietária e evite refactor amplo até reproduzir a falha na configuração mais estreita possível.

Safe mode pode ajudar a separar inicialização opcional de boot básico.

## Skip em VirGL

Skip de VirGL normalmente representa incapacidade do host. Verifique dispositivos disponíveis no QEMU, EGL/GTK, variáveis de display e render nodes.

Não altere shader ou driver do guest para resolver um host que não consegue criar o dispositivo GL necessário.

## Falha de GUI no WSL2

Se o build no WSL2 passa e um gate headless também passa, já existe evidência de que o toolchain e o smoke path funcionam. Se apenas GUI falha, investigue WSLg, backend de display e aceleração separadamente.

Confirme que o repositório está no filesystem WSL e que o QEMU chamado é a versão Linux instalada dentro do WSL.

## Comportamento de build antigo

Quando o resultado parecer incompatível com o source:

~~~bash
make clean
make
~~~

Se um build limpo corrige repetidamente o incremental, pode existir defeito no grafo de dependências. Não normalize a exigência de clean se a dependência correta puder ser expressa.

## Imagem de disco aparentemente corrompida

Pare processos QEMU usando a imagem antes de modificá-la no host. Confirme que o alvo é build/disk.img ou imagem descartável de teste, nunca um dispositivo físico por engano.

Use ferramentas e targets do projeto para ChrisFS.

## Falha apenas no ChrisVM

Se QEMU passa e ChrisVM falha:

~~~bash
make chrisvm-test
~~~

Isole a menor fixture. Não suponha que o guest está correto apenas porque QEMU o aceitou; desenvolvimento de emuladores frequentemente revela pressupostos implícitos.

## Falha apenas no QEMU

Se testes host e ChrisVM passam, mas gate QEMU falha, compare contrato de dispositivo e configuração de máquina específicos do QEMU.

A diferença pode estar no driver guest, configuração virtual ou em uma simplificação feita pelo emulador do projeto.

## Local passa, CI falha

Registre versões locais e compare com o ambiente CI e o comando exato que falhou. Evite adicionar sleeps ou afrouxar diagnostics antes de entender a diferença.

Um teste determinístico deve ser corrigido no invariante divergente, não tornado menos preciso até passar.

## Relatório mínimo

~~~text
Host:
WSL2/Linux nativo/outro:
Commit:
gcc:
ld:
nasm:
QEMU:
Comando:
Primeiro erro relevante:
Último marcador serial:
Reproduz após make clean: sim/não
Log relevante:
~~~

Para hardware, adicione máquina, firmware e dispositivos.

## Regra de troubleshooting

Preserve sempre a primeira falha significativa. A última linha de erro frequentemente representa apenas propagação. Em sistemas, a primeira transição incorreta costuma estar muito mais próxima do defeito que o maior sintoma visível.
