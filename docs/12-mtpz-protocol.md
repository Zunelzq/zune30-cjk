# 12 — The Zune MTPZ protocol, as observed

> Everything below comes from USB captures of the **official Zune 4.8 client** talking to a
> Zune 30 running firmware 3.3. No Microsoft binaries, certificates or keys are reproduced here;
> only opcode sequences and structural observations.
>
> Tools and raw data live outside this repository (they contain device-specific material).

## Why document this at all

The obvious question — "can I copy songs to the device without the Zune client?" — has a
definite answer, and it costs a lot of work to establish. This page saves the next person
that work.

**Short answer: no.** The client authenticates with a certificate chain (`Zune Software CA 1`)
and a per-session value. Replaying a captured handshake fails. Details below.

## Message framing

MTP containers on the bulk endpoints:

```
u32 length | u16 type | u16 code | u32 transaction | payload
```

* `type` 1 = command, 2 = data, 3 = response;
* commands and responses are usually 12–32 bytes; data phases are separate containers that may
  span many USB transfers (reassemble by transaction id and the declared length).

## Cold-start sequence (captured 3×, consistent)

```
0x1002  OpenSession(1)
0x1001  GetDeviceInfo                    → 821 B
0x1016  + 93 B                           → ".Windows/10.0…" (host OS string)
0x1014  property queries                 (several, incl. uuid:…)
0x922b  [3,1,0] + 260 B                  → 12 B response
0x922d  heartbeat ×~300                  (8 B: 03 00 00 00 03 00 00 00)
0x922c  + 24 / 86 / 72 / 76 B
0x922b  [3,2,0]                          ("paired" branch)
0x9801 / 0x9802 / 0x1004
0x1005  + 128 B
0x9212  785 B                            ← the app request
0x9212  767 B
0x9213                                   → 968 B response
0x9212  20 B
0x9217                                   → 206,316 B
0x9214  + 16 B                           ← session key
0x922b  [3,1,0] + 260 B
0x9230  [1]
0x922f  polled ×6                        ← becomes ready on the 6th call
0x9230  [2]
0x922b  [3,2,0]                          → steady state, then 0x100d SendObject
```

### Two traps that cost us hours

1. **`0x922f` is a poll.** The first five calls return 1,036 bytes of zeros; the sixth returns
   `01 00 00 00 64 00 00 00 04 00 00 00 03 00 00 00 …`. A single call looks like "wrong data".
2. **`0x922b` has two branches.** `[3,1,…]` carries 260 bytes of host data (early/"new pairing"),
   `[3,2,…]` appears later ("already paired"). Mixing them from different sessions breaks the
   subsequent handshake.

## The 785-byte `0x9212` request

```
0x000  02 01 01 00 00 02 75       WMDRM-PD message header
0x028  12 "Zune Software CA 1"    certificate name (length-prefixed string)
0x03E …                           fixed material
0x27C  00 10                      length prefix
0x27E  16 bytes                   session value — differs on every session
0x291 …                           signature / ciphertext block, also changes
```

Comparing two cold-start captures:

| Region | Difference |
|---|---|
| `0x000–0x27D` | **identical** |
| `0x27E–0x28D` | 16 bytes, all different |
| `0x2A3–0x30D` | 107 bytes, all different |

So it is **not a timestamp**; it is a fresh 16-byte session value plus a signature over it.
The `0x9214` call that follows carries 16 bytes with the same shape.

## Replay experiment (why this route is closed)

We replayed the **entire** captured sequence from a single session, in order, including the
260-byte `0x922b`, the three `0x9212` payloads, the `0x9213` response and the 16-byte `0x9214`:

| Step | Result |
|---|---|
| `0x1002` / `0x1001` / `0x1016` | OK |
| `0x922b` + 260 B | OK |
| `0x922f` ×10 | never becomes ready (always zeros) |
| `0x9212` 785 B | **`0x2020`** |
| `0x9212` 767 B | OK |
| `0x9213` | 968 B, same as capture |
| `0x9212` 20 B | `0x2021` |
| `0x9214` | `0x2002` |
| `SendObjectInfo` | **`0x200F`** |

Conclusion: the device binds the request to the live session and verifies the signature chain.
Reproducing it needs the `Zune Software CA 1` private key, which is inside the Zune client.
**Only the official client can write to the device.**

## What *is* possible without the client

| Capability | Status |
|---|---|
| Enumerate objects, read metadata, list the library | works (plain MTP) |
| Read file contents | works |
| `SendObjectInfo` / `SendObject` | rejected: `0x200F` / `0x2002` |
| Pair as a trusted host | requires the client's certificate |

## Capturing USB yourself (practical notes)

* **USBPcap 1.5.4** works; run `USBPcapCMD.exe -I` once to enable USB 3.0 capture, then reboot;
* it **needs a real console** — a hidden/background process exits immediately;
* it needs **administrator** rights to open `\\.\USBPcapN`;
* it writes **classic pcap** (`d4 c3 b2 a1`), not pcapng, whatever you name the file;
* the USBPcap pseudo-header is 27 bytes, and the useful fields are at **`endpoint@21`,
  `transfer@22`, `dataLength@23`** — not at the offsets often quoted online (19/21/22);
* kill stale `USBPcapCMD.exe` processes first, otherwise the device is busy;
* capture from **before plugging the device in**, or you will miss the whole handshake — our
  first capture started mid-session and produced a wrong conclusion for two hours.

## Reading the captured data

* bulk OUT, `transfer == 3`, `endpoint & 0x80 == 0`;
* reassemble data phases by transaction id: the first container carries the header and the
  declared length, the following transfers are raw continuation bytes;
* the device also emits 18-byte bulk-IN notifications with a fixed prefix
  `00 28 0e 00 0a 00 04 00 1b 30 00 00 00`; they are **not** MTP containers — skip them.
