"""Minimal WPD (Windows Portable Devices) writer for MTP media devices.

Only the pieces a sync tool needs: open the device, walk to a folder, create
objects with metadata, attach a cover, and read properties back.

Uses comtypes against the in-box PortableDeviceApi.dll.  No third-party DLLs.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path

import comtypes
import comtypes.client

CLIENT = "{204D9F0C-2292-4080-9F42-40664E70F859}"
OBJECT = "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}"
MEDIA = "{2ED8BA05-0AD3-42DC-B0D0-3DBC3588EEA4}"
MUSIC = "{B324F56A-DC5D-46E5-B6DF-D2EA20FA9C4B}"

# WPD_OBJECT_* pids (verified against the Windows SDK documentation)
PID_PARENT_ID = 3
PID_NAME = 4
PID_FORMAT = 9
PID_SIZE = 13
PID_REFERENCES = 14
PID_ORIGINAL_NAME = 18

# Default media property pids.  These are the values the Zune firmware exposes
# for audio objects; `zunesync probe` prints the device's real key set so they
# can be confirmed or overridden with --props.
DEFAULT_MEDIA_KEYS = {
    "title": (MEDIA, 2),
    "duration": (MEDIA, 3),
    "genre": (MEDIA, 7),
    "album": (MEDIA, 16),
    "artist": (MEDIA, 21),
    "track": (MUSIC, 4),
    "year": (MUSIC, 6),
}

_jpeg = "{38010000-AE6C-4804-98BA-C57B46965FE7}"


@dataclass
class DeviceInfo:
    path: str
    name: str = ""
    serial: str = ""


def _modules():
    api = comtypes.client.GetModule("PortableDeviceApi.dll")
    types = comtypes.client.GetModule("PortableDeviceTypes.dll")
    return comtypes, api, types


def discover() -> list[DeviceInfo]:
    """Return WPD interface paths for Zune-like devices."""
    ct, api, _ = _modules()
    class Interface(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("guid", ct.GUID),
                    ("flags", ctypes.c_ulong), ("reserved", ctypes.c_size_t)]

    setup = ctypes.WinDLL("setupapi", use_last_error=True)
    setup.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(ct.GUID), ctypes.c_wchar_p,
                                           ctypes.c_void_p, ctypes.c_ulong]
    setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setup.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                  ctypes.POINTER(ct.GUID), ctypes.c_ulong,
                                                  ctypes.POINTER(Interface)]
    setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p,
                                                       ctypes.POINTER(Interface),
                                                       ctypes.c_void_p, ctypes.c_ulong,
                                                       ctypes.POINTER(ctypes.c_ulong),
                                                       ctypes.c_void_p]
    setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

    guid = ct.GUID("{6AC27878-A6FA-4155-BA85-F98F491D4F33}")   # WPD device interface
    handle = setup.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    found: list[DeviceInfo] = []
    try:
        for index in range(256):
            iface = Interface()
            iface.size = ctypes.sizeof(Interface)
            if not setup.SetupDiEnumDeviceInterfaces(handle, None, ctypes.byref(guid),
                                                     index, ctypes.byref(iface)):
                if ctypes.get_last_error() == 259:      # ERROR_NO_MORE_ITEMS
                    break
                raise ctypes.WinError(ctypes.get_last_error())
            required = ctypes.c_ulong()
            setup.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(iface), None, 0,
                                                   ctypes.byref(required), None)
            buf = ctypes.create_string_buffer(required.value)
            ctypes.c_ulong.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            setup.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(iface), buf,
                                                   required.value, ctypes.byref(required), None)
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            low = path.lower()
            if "vid_1209&pid_0001" in low or "vid_045e&pid_0710" in low:
                found.append(DeviceInfo(path=path))
    finally:
        setup.SetupDiDestroyDeviceInfoList(handle)
    return found


class WpdError(RuntimeError):
    pass


def _key(api, spec):
    guid, pid = spec
    return api._tagpropertykey(comtypes.GUID(guid), pid)


class Device:
    def __init__(self, path: str):
        self._ct, self._api, self._types = _modules()
        self.path = path
        self._dev = None

    # -- lifecycle ---------------------------------------------------------
    def open(self):
        ct, api, types = self._ct, self._api, self._types
        values = ct.client.CreateObject(types.PortableDeviceValues,
                                        interface=api.IPortableDeviceValues)
        values.SetStringValue(_key(api, (CLIENT, 2)), "zunesync")
        values.SetUnsignedIntegerValue(_key(api, (CLIENT, 3)), 1)
        values.SetUnsignedIntegerValue(_key(api, (CLIENT, 4)), 0)
        values.SetUnsignedIntegerValue(_key(api, (CLIENT, 9)), 0xC0000000)
        self._dev = ct.client.CreateObject(api.PortableDevice, interface=api.IPortableDevice)
        self._dev.Open(self.path, values)
        self._content = self._dev.Content()
        self._props = self._content.Properties()
        return self

    def close(self):
        if self._dev is not None:
            try:
                self._dev.Close()
            except Exception:
                pass
        self._dev = None
        self._content = None
        self._props = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()

    # -- helpers -----------------------------------------------------------
    def _name(self, obj_id: str) -> str:
        try:
            keys = self._ct.client.CreateObject(self._types.PortableDeviceKeyCollection,
                                                interface=self._api.IPortableDeviceKeyCollection)
            k = _key(self._api, (OBJECT, PID_NAME))
            keys.Add(k)
            return self._props.GetValues(obj_id, keys).GetStringValue(k)
        except Exception:
            return ""

    def children(self, parent: str) -> list[str]:
        """Enumerate all children.

        The in-box MTP driver returns one object id per Next() call (the second
        list element is the requested count), so loop until it reports None.
        """
        out: list[str] = []
        try:
            enum = self._content.EnumObjects(0, parent, None)
            while True:
                res = enum.Next(50)
                if not res:
                    break
                first = res[0]
                if not first:
                    break
                out.append(first)
                if len(out) > 20000:
                    break
        except Exception as exc:
            raise WpdError(f"enumeration failed under {parent!r}: {exc}") from exc
        return out

    def find_child(self, parent: str, name: str) -> str | None:
        for oid in self.children(parent):
            if self._name(oid) == name:
                return oid
        return None

    def find_path(self, *names: str) -> str | None:
        parent = "DEVICE"
        for name in names:
            nxt = self.find_child(parent, name)
            if nxt is None:
                return None
            parent = nxt
        return parent

    def list_names(self, parent: str) -> list[str]:
        out = []
        for oid in self.children(parent):
            n = self._name(oid)
            if n:
                out.append(n)
        return out

    # -- creation ----------------------------------------------------------
    def create_object(self, parent: str, name: str, format_guid: str,
                      props: dict[str, object], data: bytes,
                      progress=None) -> str:
        ct, api, types = self._ct, self._api, self._types
        values = ct.client.CreateObject(types.PortableDeviceValues,
                                        interface=api.IPortableDeviceValues)
        values.SetStringValue(_key(api, (OBJECT, PID_PARENT_ID)), parent)
        values.SetStringValue(_key(api, (OBJECT, PID_NAME)), name)
        values.SetStringValue(_key(api, (OBJECT, PID_ORIGINAL_NAME)), name)
        values.SetGuidValue(_key(api, (OBJECT, PID_FORMAT)), ct.GUID(format_guid))

        for spec, value in (props or {}).items():
            key = _key(api, spec)
            if isinstance(value, str):
                values.SetStringValue(key, value)
            elif isinstance(value, int):
                values.SetUnsignedIntegerValue(key, value)
            elif isinstance(value, bool):
                values.SetBoolValue(key, value)
            else:
                raise TypeError(f"unsupported property value {value!r}")

        stream, optimal, cookie = self._content.CreateObjectWithPropertiesAndData(values)
        written = 0
        chunk = max(65536, int(optimal or 65536))
        for i in range(0, len(data), chunk):
            part = data[i:i + chunk]
            _istream_write(stream, part)
            written += len(part)
            if progress:
                progress(written, len(data))
        _istream_commit(stream)
        return str(cookie)

    def set_references(self, obj_id: str, refs: list[str]) -> None:
        ct, api, types = self._ct, self._api, self._types
        collection = ct.client.CreateObject(types.PortableDevicePropVariantCollection,
                                            interface=api.IPortableDevicePropVariantCollection)
        for ref in refs:
            variant = api.tag_inner_PROPVARIANT()
            variant.vt = 31                                  # VT_LPWSTR
            ptr = ctypes.c_wchar_p(ref)
            ctypes.memmove(ctypes.byref(variant, 8), ctypes.byref(ptr),
                           ctypes.sizeof(ctypes.c_void_p))
            collection.Add(ctypes.byref(variant))
        values = ct.client.CreateObject(types.PortableDeviceValues,
                                        interface=api.IPortableDeviceValues)
        values.SetIPortableDevicePropVariantCollectionValue(
            _key(api, (OBJECT, PID_REFERENCES)), collection)
        self._props.SetValues(obj_id, values)

    def get_string_props(self, obj_id: str) -> dict[tuple[str, int], str]:
        """Every string-readable property of an object, keyed by (GUID, pid)."""
        out: dict[tuple[str, int], str] = {}
        try:
            keys = self._props.GetSupportedProperties(obj_id)
            count = keys.GetCount()
        except Exception:
            return out
        for i in range(count):
            try:
                single = self._ct.client.CreateObject(
                    self._types.PortableDeviceKeyCollection,
                    interface=self._api.IPortableDeviceKeyCollection)
                k = keys.GetAt(i)
                single.Add(k)
                value = self._props.GetValues(obj_id, single)
                out[(str(k.fmtid).upper(), k.pid)] = value.GetStringValue(k)
            except Exception:
                continue
        return out

# ---------------------------------------------------------------------------
# Raw IStream calls: comtypes' wrapper only exposes Commit, so drive the
# vtable directly.  IStream layout: Read(3) Write(4) Seek(5) SetSize(6)
# CopyTo(7) Commit(8) Revert(9) ...
# ---------------------------------------------------------------------------
_HRESULT = ctypes.c_long


def _vtable_call(ptr, index, *argtypes):
    interface = ctypes.cast(ptr, ctypes.c_void_p).value
    vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.c_void_p))[0]
    fn_ptr = ctypes.cast(vtable, ctypes.POINTER(ctypes.c_void_p))[index]
    proto = ctypes.WINFUNCTYPE(_HRESULT, ctypes.c_void_p, *argtypes)
    return proto(fn_ptr)


def _istream_write(stream, payload: bytes) -> None:
    ptr = ctypes.cast(stream, ctypes.c_void_p).value
    written = ctypes.c_ulong(0)
    buf = ctypes.create_string_buffer(payload, len(payload))
    fn = _vtable_call(ptr, 4, ctypes.c_void_p, ctypes.c_ulong,
                      ctypes.POINTER(ctypes.c_ulong))
    hr = fn(ptr, buf, len(payload), ctypes.byref(written))
    if hr < 0:
        raise WpdError(f"IStream.Write failed: 0x{hr & 0xFFFFFFFF:08X}")
    if written.value != len(payload):
        raise WpdError(f"IStream.Write short write: {written.value}/{len(payload)}")


def _istream_commit(stream) -> None:
    ptr = ctypes.cast(stream, ctypes.c_void_p).value
    fn = _vtable_call(ptr, 8, ctypes.c_ulong)
    hr = fn(ptr, 0)
    if hr < 0:
        raise WpdError(f"IStream.Commit failed: 0x{hr & 0xFFFFFFFF:08X}")