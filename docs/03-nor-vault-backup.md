# 03 — Dumping NOR and the vault without desoldering

You need the 2 MiB NOR (for the `AUTH196` build) and the old vault (64 KiB at NOR
`0x70000–0x7FFFF`). Reading the NOR chip with a programmer works, but there is a
software-only route that the community already automated.

## The trick: the TEST firmware's boot-time helper hook

1.0 TEST firmware contains an `Init` entry:

```
Launch85 = \Hard Disk2\firmware\qtk.exe
```

That is a **test entry point**: at boot the device executes that file with kernel
privileges. So:

1. over MTP, create a plain "carrier" file (a large zero-filled object) on the device;
2. push a small ARM program as `qtk.exe` through the firmware channel;
3. the device reboots, runs `qtk.exe`;
4. the program maps physical `0xA0000000` (NOR) with `MmMapIoSpace`, reads 2 MiB, and
   writes it into the carrier file;
5. read the carrier back over MTP.

The ARM program also uses `SetKMode(1)` / `SetProcPermissions(~0)` to reach kernel APIs.

## Reference implementation

`ZZAudio-Zune30-Assistant` (built on `zune30-research`) automates exactly this:

* device must be a supported **1.0 (186) TEST** build
  (MTP firmware string `01.00.00186.00-02.04`);
* "check connection" → "start backup" → two rounds, one reboot, then it reads back:

```
nk.original.PRIVATE.bin              10,689,955 B
nor.original.PRIVATE.bin              2,097,152 B
vault.legacy.PRIVATE.bin                 65,536 B
disk-prefix.original.PRIVATE.bin      1,048,576 B
```

Verify hashes against the tool's inventory before doing anything else.

## If the tool refuses your unit

The guard is a bootloader-hash check (`nor[:0x40000]` must equal a pinned value). Our unit
carried the 2009 hack's modified EBoot, so the check failed. Because we only needed the
backup (not the upgrade), we could have bypassed it — but if your unit has the stock TEST
loader the tool runs unmodified.

## Manual fallback

If you cannot run the assistant:

* find another TEST unit and borrow its dumped NOR/vault (only valid for AUTH196 if the
  vault belongs to *your* device — the image embeds it, so a foreign vault produces a
  non-booting image);
* or desolder the `28F160C3` and read it (SO-44, 3.3 V; any TL866-class programmer works).
