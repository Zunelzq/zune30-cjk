# 01 — Background: hardware, boot chain, protection layers

## Hardware

| Part | Detail |
|---|---|
| Device | Zune 30 GB, codename **Keel**, 2006 |
| SoC | Freescale **i.MX31L** (ARM1136, HAB secure boot) |
| OS | Windows CE 5.0, shell `gemstone.exe` + `xuidll.dll` |
| NOR | Intel **28F160C3** (2 MiB) — holds EBoot + recovery |
| Button/PMIC | Atlas; PMIC firmware in `pmcver.dat` |
| Storage | 1.8" ZIF HDD/SSD, MBR: 150 MB TFAT (system) + remainder TFAT (data) |
| Display | 320×240 QVGA |

## Boot chain

```
i.MX31 Boot ROM
   └─ HAB: verifies EBoot.bin signature against eFuse SRK hash
        └─ EBoot.bin (NOR): verifies nk.bin (MinCrypt), loads it into RAM
             └─ nk.bin (disk): WinCE 5 kernel + modules + ROM file system
                  └─ gemstone.exe (Zune shell) → XUI text/font stack
```

`nk.bin` and `EBoot.bin` are **B000FF** containers: a 15-byte header
(`B000FF\n`, base, span, entry) followed by records `(address, length, checksum, data)`
and a terminator `(0, entry, 0)`. Per-record checksum is a plain byte sum.

## The three protection layers

| Layer | What it does | Evidence from hardware |
|---|---|---|
| **HAB** | Boot ROM verifies EBoot against fuses | changing *one padding byte* in `EBoot.bin` → instant recovery |
| **EBoot MinCrypt** | retail EBoot verifies `nk.bin` incl. its signature block | changing one byte in `nk.bin` → progress bar completes, then recovery; changing one byte inside the signature block → "please wait" then repair prompt |
| **Authenticode** | Zune client + device verify firmware CABs | self-signed CAB → `800B0100`; non-MS chain → `800B0109` |

All three are absolute — with a retail bootloader. The project only works because of the
fourth, undocumented case below.

## The exception: 1.0 TEST EBoot

Microsoft's 1.0-era engineering/TEST builds shipped a bootloader that is
**signed by a key the fuses accept** but **does not verify `nk.bin`**.

Practical test: change one padding byte inside a 1.0 TEST `nk.bin`, boot → it boots.

That single behaviour is what makes every modification in this repository possible.
See `02-lax-bootloader.md`.
