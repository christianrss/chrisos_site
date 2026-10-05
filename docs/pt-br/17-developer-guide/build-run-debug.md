---
id: build-run-debug
lang: pt-br
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/build-and-run.md
  - makefile
  - scripts/qemu.mk
  - scripts/check-dev-env.sh
depends_on:
  - developer-guide
---

# Build, execução e depuração

O ChrisOS possui vários caminhos de build e execução. Selecionar o caminho mais estreito que exercita o subsistema alterado reduz o tempo de iteração e torna as falhas mais fáceis de classificar.

## Artefatos principais

Na raiz do repositório:

~~~bash
make
~~~

O alvo padrão produz build/os.iso. O kernel pode ser compilado isoladamente:

~~~bash
make kernel
~~~

A imagem persistente do workspace ChrisFS é criada com:

~~~bash
make disk.img
~~~

Esses comandos provam coisas diferentes. Compilar o kernel não prova criação correta da ISO; produzir a ISO não prova boot; um boot não prova um caminho específico de dispositivo ou filesystem.

## QEMU interativo

O target padrão é:

~~~bash
make run
~~~

Na revisão analisada, ele prepara os artefatos necessários, inicia QEMU x86-64 com o conjunto normal de dispositivos virtuais, envia a serial do guest para o terminal e solicita KVM.

Se make run falhar antes de aparecer qualquer saída serial do ChrisOS, verifique primeiro se o QEMU conseguiu iniciar. Falta de acesso a KVM, backend de display indisponível, opção inválida do QEMU ou artefato ausente são falhas de host.

Falha do guest só começa depois que a máquina virtual está realmente executando código do ChrisOS.

## Execução headless portátil

Para integração reproduzível, prefira gates mantidos pelo projeto. O smoke test comum é:

~~~bash
make test-qemu-ata
~~~

Esse gate utiliza TCG, grava serial em build/qemu-test.txt e verifica marcadores explícitos.

Conjuntos mais amplos:

~~~bash
make host-gates
make qemu-gates
make full-gates
~~~

Durante desenvolvimento, execute primeiro o teste mais específico. A suíte inteira é confirmação posterior, não o melhor instrumento para localizar um defeito local.

## Gates por dispositivo

scripts/qemu.mk define caminhos separados para dispositivos e configurações de boot. Exemplos:

~~~bash
make test-qemu-ahci
make test-qemu-nvme
make test-qemu-vblk
make test-qemu-usb
make test-qemu-gpu
make test-qemu-xhci
make test-qemu-safe
make test-qemu-install
~~~

Esses resultados são evidência em modelos QEMU; não provam compatibilidade com hardware físico arbitrário.

## ChrisVM

O caminho de emulação mantido pelo próprio projeto possui targets separados:

~~~bash
make chrisvm
make chrisvm-test
~~~

Falhas ChrisVM devem ser separadas conceitualmente das falhas QEMU. Uma alteração pode quebrar o emulador sem quebrar o guest no QEMU, ou o ChrisVM pode expor uma suposição do guest que um modelo QEMU tolera.

## RISC-V

O bring-up RISC-V é:

~~~bash
make riscv
make run-riscv
~~~

Esse caminho não representa paridade de funcionalidades com x86-64. Seus resultados devem ser descritos como evidência específica dessa arquitetura.

## Depuração orientada pela serial

A serial é a interface mais confiável para diagnóstico inicial de kernel e dispositivos. make run envia a serial ao terminal; os gates headless gravam logs determinísticos.

Quando um gate falhar:

1. preserve o primeiro log com falha;
2. identifique o último marcador bem-sucedido;
3. repita o gate mais estreito;
4. classifique a falha como host ou guest;
5. instrumente apenas o caminho relevante;
6. remova debug temporário ou transforme-o em logging intencional antes do merge.

Não substitua uma verificação determinística por observação visual do desktop.

## Estado do GDB

O repositório não define hoje GDB como target de validação de primeira classe. QEMU pode expor genericamente um stub remoto de GDB e isso pode ser útil localmente, mas um comando QEMU ad-hoc continua sendo uma técnica de depuração, não um resultado de teste mantido pelo projeto.

Se um workflow GDB canônico for adicionado, ele deve ganhar target reproduzível e documentação operacional próxima ao build.

## Safe mode

A suíte QEMU possui caminho de safe mode. Ele é útil quando subsistemas opcionais escondem um problema de boot mais baixo.

Se a configuração normal falhar e safe mode funcionar, compare os caminhos de inicialização desativados por safe mode antes de reabrir hipóteses sobre reset, bootloader ou memória básica.

## VirGL

O gate é:

~~~bash
make test-qemu-virgl
~~~

Ele verifica capacidades do host antes do guest e pode retornar skip se QEMU ou stack gráfico não puderem fornecer o ambiente.

| Resultado | Significado |
|---|---|
| pass | expectativas declaradas foram observadas |
| fail | teste executou, mas alguma expectativa falhou |
| skip | host não forneceu ambiente VirGL |

Skip não é pass.

## Build limpo e incremental

Quando artefatos antigos forem plausíveis:

~~~bash
make clean
make
~~~

Porém builds limpos não devem esconder dependências incorretas no Makefile. Se o build incremental falha repetidamente em reconstruir algo que deveria mudar, o grafo de dependências precisa ser corrigido.

## Disciplina com imagens de disco

build/disk.img e imagens temporárias dos gates são artefatos descartáveis. Instalação em disco físico é outro fluxo e não deve ser misturada com debug normal.

Pare o QEMU antes de modificar offline uma imagem ChrisFS.

## Preserve o primeiro artifact de falha

Quando um run falhar, preserve o primeiro log ou image que demonstra a falha antes de alterar flags ou rebuildar repetidamente.

Uma nova execução pode mudar timing, regenerar disk image ou sobrescrever serial log. Preservar o primeiro artifact permite comparar o último marker bem-sucedido, o primeiro marker de falha e a source revision correspondente.

Se a falha desaparecer após `make clean`, registre isso. Pode indicar stale generated state ou dependency incompleta de build, não necessariamente defeito lógico do guest.

## Disciplina de rerun

Depois de alterar source em resposta a uma falha, execute primeiro o mesmo gate estreito. Não pule direto para suite ampla, pois um pass amplo pode esconder se a condição original foi realmente exercitada.

Sequência útil:

1. reproduza a falha original;
2. preserve o artifact;
3. aplique a menor mudança;
4. repita o mesmo comando;
5. confirme que o ponto anterior agora é ultrapassado;
6. só então execute gates de regressão mais amplos.

Isso preserva o vínculo causal entre defeito e correção.

## Depure a partir do último milestone conhecido

Quando a serial parar, não reinicie a análise pelo reset sem evidência de que o problema está ali. Use o último milestone confirmado para limitar o intervalo da falha.

Por exemplo, se existem markers de memory initialization, storage discovery e filesystem mount, mas não existe o marker de desktop, investigue primeiro o código executado depois do mount. Isso reduz o conjunto de candidatos e evita gastar tempo em subsistemas de early boot que já demonstraram progresso.

Ao adicionar instrumentation temporária, use markers específicos ao estado provado e remova-os ou formalize-os antes do merge.

## Classificação de falhas

| Sintoma | Primeira camada |
|---|---|
| comando inexistente | ambiente host |
| erro compiler/linker | toolchain/build |
| erro xorriso | construção de imagem |
| QEMU encerra antes da serial | QEMU/display/aceleração do host |
| serial inicia e ocorre panic | kernel/subsistema guest |
| timeout com marcadores parciais | progresso guest ou expectativa do teste |
| VirGL skip | capacidade gráfica host |
| teste host falha | lógica executada no host |
| somente ChrisVM falha | emulador/modelo de máquina |

Essa separação evita depurar código do guest para um problema que ocorreu antes de o guest executar.
