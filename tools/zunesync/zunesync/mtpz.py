"""MTPZ handshake — application certificate message.

The signature algorithm below is reverse-engineered from libmtp-zune's
``mtpz.c`` and **verified byte-for-byte against a captured message** from the
Zune desktop software (see ``tests/test_mtpz.py``).

Remaining for a full handshake (not implemented yet):
  * custom AES (expand key + InvMixColumns, decrypt_custom, encrypt_mac)
  * response validation and confirmation message
  * the four MTP operations: 0xD406 set, 0x9216 reset, 0x9212 send,
    0x9213 response, 0x9214 enable trusted file operations
"""
from __future__ import annotations

import hashlib
import os
import struct

CERT_LENGTH = 0x275          # 629 bytes carried in the message
ACM_LENGTH = 785
RANDOM_LENGTH = 16


def load_keys(path: str) -> dict:
    """Parse a .mtpz-data file (5 hex lines).

    NOTE: only the ``.be`` variant has a keyset where d matches n (checked by
    ``n == p*q`` round-trip).  Using the file without the ``.be`` suffix makes
    every signature fail - that was the original MTPZ blocker.
    """
    lines = [l.strip() for l in open(path, encoding="utf-8") if l.strip()]
    return {
        "exponent": int(lines[0], 16),
        "aes_key": bytes.fromhex(lines[1]),
        "modulus": int(lines[2], 16),
        "private": int(lines[3], 16),
        "certificates": bytes.fromhex(lines[4]),
    }


def verify_keyset(keys: dict, samples: int = 2) -> bool:
    n, e, d = keys["modulus"], keys["exponent"], keys["private"]
    for a in range(2, 2 + samples):
        if pow(pow(a, e, n), d, n) != a:
            return False
    return True


def custom_6a5dc(msg: bytes, length: int) -> bytes:
    """MTPZ's SHA-1 based expansion: SHA1(msg || BE(counter)) repeated."""
    out = bytearray()
    for i in range(length // 20 + 1):
        out += hashlib.sha1(msg + struct.pack(">I", i)).digest()
    return bytes(out)


def signing_block(body: bytes) -> bytes:
    """Build the 128-byte block that gets RSA-signed."""
    h1 = hashlib.sha1(body).digest()
    v16 = bytearray(28)
    v16[8:28] = h1
    h2 = hashlib.sha1(bytes(v16)).digest()
    v17 = custom_6a5dc(h2, 107)

    block = bytearray(128)
    block[106] = 1
    block[107:127] = h2
    for i in range(107):
        block[i] ^= v17[i]
    block[0] &= 127
    block[127] = 188
    return bytes(block)


def sign(block: bytes, keys: dict) -> bytes:
    value = int.from_bytes(block, "big")
    signature = pow(value, keys["private"], keys["modulus"])
    return signature.to_bytes(128, "big")


def build_acm(keys: dict, certificates: bytes, random16: bytes) -> bytes:
    """Assemble the 785-byte application certificate message."""
    if len(certificates) != CERT_LENGTH:
        raise ValueError(f"certificates must be {CERT_LENGTH} bytes, got {len(certificates)}")
    if len(random16) != RANDOM_LENGTH:
        raise ValueError("random must be 16 bytes")

    acm = bytearray()
    acm += bytes([0x02, 0x01, 0x01, 0x00, 0x00, 0x02, 0x75])
    acm += certificates
    acm += bytes([0x00, 0x10])
    acm += random16

    body = bytes(acm[2:])                       # header tail + certs + random
    block = signing_block(body)
    signature = sign(block, keys)

    acm += bytes([0x01, 0x00, 0x80])
    acm += signature
    assert len(acm) == ACM_LENGTH, len(acm)
    return bytes(acm)


def verify_acm(acm: bytes, keys: dict) -> bool:
    """Check the RSA signature with the public exponent."""
    if len(acm) != ACM_LENGTH:
        return False
    body = acm[2:654]
    block = signing_block(body)
    signature = acm[657:785]
    recovered = pow(int.from_bytes(signature, "big"), keys["exponent"],
                    keys["modulus"]).to_bytes(128, "big")
    return recovered == block
