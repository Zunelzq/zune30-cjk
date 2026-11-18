"""MTP client over the Windows WPD pass-through transport.

The Zune driver exposes standard MTP through WPD `SendCommand`
(WPD_CATEGORY_MTP_DEVICE_COMMANDS).  Going through MTP directly - instead of
the high-level WPD object API - lets us send a complete ObjectInfo dataset and
set media properties, which is what the library uses to show album/artist.

Protocol constants are from the MTP specification (PIMA 15740 / MTP 1.1).
"""
from __future__ import annotations

import ctypes
import struct
from dataclasses import dataclass

import comtypes
import comtypes.client

COMMON = "{F0422A9C-5DC8-4440-B5BD-5DF28835658A}"
MTP = "{4D545058-1A2E-4106-A357-771E0819FC56}"

# MTP operations
OP_GET_DEVICE_INFO = 0x1001
OP_GET_STORAGE_IDS = 0x1004
OP_GET_STORAGE_INFO = 0x1005
OP_GET_NUM_OBJECTS = 0x1006
OP_GET_OBJECT_HANDLES = 0x1007
OP_GET_OBJECT_INFO = 0x1008
OP_GET_OBJECT = 0x1009
OP_SEND_OBJECT_INFO = 0x100C
OP_SEND_OBJECT = 0x100D
OP_GET_OBJECT_PROP_SUPPORTED = 0x9801
OP_GET_OBJECT_PROP_DESC = 0x9802
OP_GET_OBJECT_PROP_VALUE = 0x9803
OP_SET_OBJECT_PROP_VALUE = 0x9804
OP_GET_OBJECT_PROP_LIST = 0x9805
OP_SET_OBJECT_PROP_LIST = 0x9806

# Object format codes
FMT_MP3 = 0x3009
FMT_WMA = 0xB901
FMT_FLAC = 0xB906
FMT_AAC = 0xB903
FMT_WAV = 0x3008
FMT_JPEG = 0x3801
FMT_ABSTRACT_PLAYLIST = 0xBA05

# Object property codes (MTP 1.1)
PROP_STORAGE_ID = 0xDC01
PROP_OBJECT_FORMAT = 0xDC02
PROP_PROTECTION = 0xDC03
PROP_OBJECT_SIZE = 0xDC04
PROP_FILE_NAME = 0xDC07
PROP_DATE_CREATED = 0xDC08
PROP_DATE_MODIFIED = 0xDC09
PROP_PARENT_OBJECT = 0xDC0B
PROP_NAME = 0xDC44
PROP_ARTIST = 0xDC46
PROP_DATE_AUTHORED = 0xDC47
PROP_DESCRIPTION = 0xDC48
PROP_GENRE = 0xDC4E
PROP_ALBUM_NAME = 0xDC4F
PROP_TRACK_NUMBER = 0xDC5B

MTP_ERRORS = {
    0x2001: "OK",
    0x2002: "General error",
    0x2003: "Session not open",
    0x2004: "Invalid transaction id",
    0x2005: "Operation not supported",
    0x2006: "Parameter not supported",
    0x2007: "Incomplete transfer",
    0x2008: "Invalid storage id",
    0x2009: "Invalid object handle",
    0x200A: "Device property not supported",
    0x200B: "Invalid object format code",
    0x200C: "Store full",
    0x200D: "Object write protected",
    0x200E: "Store read-only",
    0x2019: "Invalid parent object",
    0x201D: "Invalid parameter",
    0x201E: "Session already open",
    0xA801: "Access denied",
}


class MtpError(RuntimeError):
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"MTP error 0x{code:04X}: {MTP_ERRORS.get(code, 'unknown')}")


# --------------------------------------------------------------------------
# Datasets
# --------------------------------------------------------------------------
def _string(text: str) -> bytes:
    if not text:
        return b"\x00"
    data = (text + "\x00").encode("utf-16-le")
    if len(data) // 2 > 255:
        raise ValueError("string too long for MTP")
    return bytes([len(data) // 2]) + data


class Reader:
    def __init__(self, data: bytes):
        self.data, self.at = data, 0

    def take(self, n: int) -> bytes:
        if self.at + n > len(self.data):
            raise ValueError("truncated dataset")
        out = self.data[self.at:self.at + n]
        self.at += n
        return out

    def u8(self) -> int:
        return struct.unpack("<B", self.take(1))[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.take(8))[0]

    def string(self) -> str:
        n = self.u8()
        raw = self.take(n * 2)
        return raw[:-2].decode("utf-16-le") if n else ""

    def array16(self) -> list[int]:
        n = self.u32()
        if n > 4096:
            raise ValueError("array too long")
        return [self.u16() for _ in range(n)]


def object_info_data(name: str, size: int, format_code: int,
                     parent: int = 0, sequence: int = 0) -> bytes:
    """Standard MTP ObjectInfo dataset (PIMA 15740, section 5.2.2.3)."""
    parts = [
        struct.pack("<I", 0xFFFFFFFF),        # StorageID
        struct.pack("<HH", format_code, 0),   # ObjectFormat, ProtectionStatus
        struct.pack("<I", size),              # ObjectCompressedSize
        struct.pack("<H", 0),                 # ThumbFormat
        struct.pack("<I", 0),                 # ThumbCompressedSize
        struct.pack("<II", 0, 0),             # ThumbPixWidth/Height
        struct.pack("<III", 0, 0, 0),         # ImagePixWidth/Height/BitDepth
        struct.pack("<I", parent),            # ParentObject
        struct.pack("<H", 0),                 # AssociationType
        struct.pack("<I", 0),                 # AssociationDesc
        struct.pack("<I", sequence),          # SequenceNumber
        _string(name), _string(""), _string(""), _string(""),
    ]
    return b"".join(parts)

@dataclass
class ObjectInfo:
    handle: int
    storage: int
    format: int
    parent: int
    name: str
    size: int
    sequence: int


def parse_object_info(data: bytes) -> ObjectInfo:
    r = Reader(data)
    storage = r.u32()
    fmt = r.u16()
    r.u16()                       # protection
    size = r.u32()
    r.u16()                       # thumb format
    r.u32()                       # thumb size
    r.u32(); r.u32()              # thumb w/h
    r.u32(); r.u32(); r.u32()     # image w/h/depth
    parent = r.u32()
    r.u16()                       # association type
    r.u32()                       # association desc
    sequence = r.u32()
    name = r.string()
    r.string(); r.string(); r.string()
    return ObjectInfo(0, storage, fmt, parent, name, size, sequence)


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------
class Transport:
    def __init__(self, device_path: str):
        self._api = comtypes.client.GetModule("PortableDeviceApi.dll")
        self._types = comtypes.client.GetModule("PortableDeviceTypes.dll")
        self._params: list[int] = []
        values = self._values()
        # MTP pass-through requires GENERIC_READ | GENERIC_WRITE.
        values.SetUnsignedIntegerValue(self._key(COMMON, 9), 0xC0000000)
        self.dev = comtypes.client.CreateObject(self._api.PortableDevice,
                                                interface=self._api.IPortableDevice)
        self.dev.Open(device_path, values)

    # -- plumbing ----------------------------------------------------------
    def _key(self, guid, pid):
        return self._api._tagpropertykey(comtypes.GUID(guid), pid)

    def _values(self):
        return comtypes.client.CreateObject(self._types.PortableDeviceValues,
                                            interface=self._api.IPortableDeviceValues)

    def _request(self, command: int, values=()):
        query = self._values()
        query.SetGuidValue(self._key(COMMON, 1001), comtypes.GUID(MTP))
        query.SetUnsignedIntegerValue(self._key(COMMON, 1002), command)
        for pid, kind, value in values:
            key = self._key(MTP, pid)
            if kind == "u32":
                query.SetUnsignedIntegerValue(key, value)
            elif kind == "u64":
                query.SetUnsignedLargeIntegerValue(key, value)
            elif kind == "str":
                query.SetStringValue(key, value)
            elif kind == "buf":
                arr = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
                query.SetBufferValue(key, arr, len(value))
            elif kind == "params":
                collection = comtypes.client.CreateObject(
                    self._types.PortableDevicePropVariantCollection,
                    interface=self._api.IPortableDevicePropVariantCollection)
                collection.ChangeType(19)
                for param in value:
                    variant = self._api.tag_inner_PROPVARIANT()
                    variant.vt = 19
                    ctypes.c_uint32.from_buffer(variant, 8).value = param
                    collection.Add(ctypes.byref(variant))
                query.SetIPortableDevicePropVariantCollectionValue(key, collection)
        response = self.dev.SendCommand(0, query)
        hr = response.GetErrorValue(self._key(COMMON, 1003)) & 0xFFFFFFFF
        if hr:
            raise RuntimeError(f"WPD error 0x{hr:08X} (command {command})")
        return response

    def _code(self, response) -> int:
        self._params = []
        try:
            collection = response.GetIPortableDevicePropVariantCollectionValue(
                self._key(MTP, 1004))
            count = ctypes.c_ulong()
            collection.GetCount(ctypes.byref(count))
            for i in range(min(count.value, 8)):
                variant = self._api.tag_inner_PROPVARIANT()
                collection.GetAt(i, ctypes.byref(variant))
                self._params.append(ctypes.c_uint32.from_buffer(variant, 8).value)
        except (OSError, comtypes.COMError):
            pass
        code = response.GetUnsignedIntegerValue(self._key(MTP, 1003))
        if code not in (0x2001, 0xA221):
            raise MtpError(code)
        return code

    # -- public API --------------------------------------------------------
    def operation(self, opcode: int, params=(), data: bytes | None = None,
                  read: bool = False) -> bytes | None:
        args = [(1001, "u32", opcode), (1002, "params", list(params))]
        if data is None and not read:
            self._code(self._request(12, args))
            return None
        if data is not None:
            args.append((1007, "u64", len(data)))
        response = self._request(13 if read else 14, args)
        context = response.GetStringValue(self._key(MTP, 1006))
        out = bytearray()
        try:
            if read:
                size = response.GetUnsignedLargeIntegerValue(self._key(MTP, 1007))
                while len(out) < size:
                    want = min(65536, size - len(out))
                    reply = self._request(15, [(1006, "str", context),
                                               (1008, "u32", want),
                                               (1012, "buf", bytes(want))])
                    got = reply.GetUnsignedIntegerValue(self._key(MTP, 1009))
                    pointer, allocated = reply.GetBufferValue(self._key(MTP, 1012))
                    try:
                        if not 0 < got <= want or allocated < got:
                            raise ValueError("bad read length")
                        out.extend(ctypes.string_at(pointer, got))
                    finally:
                        ole = ctypes.WinDLL("ole32")
                        ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
                        ole.CoTaskMemFree(pointer)
            else:
                offset = 0
                while offset < len(data):
                    chunk = data[offset:offset + 65536]
                    reply = self._request(16, [(1006, "str", context),
                                               (1010, "u32", len(chunk)),
                                               (1012, "buf", chunk)])
                    sent = reply.GetUnsignedIntegerValue(self._key(MTP, 1011))
                    if not 0 < sent <= len(chunk):
                        raise ValueError("bad write length")
                    offset += sent
        finally:
            end = self._request(17, [(1006, "str", context)])
        self._code(end)
        return bytes(out) if read else None

    # -- convenience -------------------------------------------------------
    def device_info(self) -> dict:
        data = self.operation(OP_GET_DEVICE_INFO, read=True)
        r = Reader(data)
        r.u16(); r.u32(); r.u16()
        r.string()
        r.u16()
        ops = r.array16()
        r.array16(); r.array16(); r.array16()
        formats = r.array16()
        manufacturer, model, firmware, serial = (r.string() for _ in range(4))
        return {"manufacturer": manufacturer, "model": model,
                "firmware": firmware, "serial": serial,
                "operations": ops, "formats": formats}

    def storages(self) -> list[int]:
        data = self.operation(OP_GET_STORAGE_IDS, read=True)
        r = Reader(data)
        n = r.u32()
        return [r.u32() for _ in range(n)]

    def handles(self, storage: int, fmt: int = 0, parent: int = 0xFFFFFFFF) -> list[int]:
        data = self.operation(OP_GET_OBJECT_HANDLES, [storage, fmt, parent], read=True)
        r = Reader(data)
        n = r.u32()
        if n > 50000:
            raise ValueError("too many objects")
        return [r.u32() for _ in range(n)]

    def object_info(self, handle: int) -> ObjectInfo:
        data = self.operation(OP_GET_OBJECT_INFO, [handle], read=True)
        info = parse_object_info(data)
        info.handle = handle
        return info

    def read_object(self, handle: int) -> bytes:
        return self.operation(OP_GET_OBJECT, [handle], read=True)

    def send_object(self, storage: int, parent: int, name: str, size: int,
                    format_code: int, payload: bytes, sequence: int = 0) -> int:
        dataset = object_info_data(name, size, format_code, parent, sequence)
        self.operation(OP_SEND_OBJECT_INFO, [storage, parent], data=dataset)
        # SendObjectInfo returns StorageID, ParentObject, ObjectHandle as the
        # response parameters.
        if len(self._params) < 3:
            raise MtpError(0x2002)
        handle = self._params[2]
        self.operation(OP_SEND_OBJECT, [handle], data=payload)
        return handle

    def set_properties(self, handle: int, props: dict[int, object]) -> None:
        """Set object properties via MTP 0x9804.

        The Zune firmware expects the bare MTP value (length-prefixed UTF-16
        string, or a UINT32); a DataType prefix is swallowed as data and shows
        up as a stray leading character, so it must be omitted.
        """
        for code, value in props.items():
            if isinstance(value, str):
                body = (value + "\0").encode("utf-16-le")
                payload = bytes([len(body) // 2]) + body
            elif isinstance(value, int):
                payload = struct.pack("<I", value)
            else:
                raise TypeError(value)
            self.operation(OP_SET_OBJECT_PROP_VALUE, [handle, code], data=payload)

    def close(self):
        try:
            self.dev.Close()
        except Exception:
            pass


def discover() -> list[str]:
    """Return WPD interface paths for Zune-like devices."""
    from .wpd import discover as wpd_discover
    return [d.path for d in wpd_discover()]
