---
id: installation-real-hardware
lang: pt-br
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/install.c
  - kernel/fs/part.c
  - docs/INSTALLATION.md
  - docs/HARDWARE_BRINGUP.md
  - docs/HARDWARE_COMPATIBILITY.md
  - docs/REAL_HARDWARE_PLAN.md
symbols: []
depends_on:
  - block-storage
  - power-on-kstart
related:
  - validation-evidence
---

# Instalação e hardware físico

## Instalação é operação destrutiva

Installer grava estruturas consumidas por firmware, GPT, filesystem e bootloader. Selecionar disco errado ou errar LBA pode destruir dados.

Arquitetura segura separa seleção de target, layout, format, ESP, cópia de kernel/configuração, verificação e política de reboot/rollback.

## GPT e ESP

GPT possui header/tabela primários e backup no fim do disco. Cálculos dependem da geometria real.

UEFI lê uma EFI System Partition FAT e procura caminhos padrão como `/EFI/BOOT/BOOTX64.EFI`. ESP é diferente do ChrisFS.

## Limine e kernel

Limine continua bootloader externo. Self-hosting do kernel não exige substituir UEFI/Limine.

## QEMU e hardware

VM controla chipset, firmware e devices. Máquina física varia ACPI, USB, NVMe, firmware, IRQ e vídeo.

| Evidência | Significado |
|---|---|
| host-tested | algoritmo/tool no host |
| QEMU-tested | comportamento na VM declarada |
| hardware-tested | comportamento em hardware identificado |

## Perfil de hardware

Primeiro alvo físico deve declarar UEFI/x86-64, storage, input, framebuffer/GOP e fallbacks. "Funcionou no meu PC" vira evidência útil quando hardware e devices são identificados.

## Safe mode

Bring-up físico exige diagnóstico precoce e ability de desabilitar subsistemas opcionais. Falha de áudio/rede não deve impedir testar boot/storage quando possível.

## Disciplina de testes

Escrita física precisa de confirmação de target, capacidade/modelo/serial quando disponíveis e preferência por dry-run. Gates destrutivos devem continuar em imagens descartáveis até o caminho estar validado.
