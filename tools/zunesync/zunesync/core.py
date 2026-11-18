"""zunesync — offline core: format table, tag/cover extraction, sync planning.

No device access here; everything is testable without hardware.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# --------------------------------------------------------------------------
# MTP object formats.  GUIDs follow the WPD convention: the low 16 bits of
# Data1 carry the MTP object format code, the remainder is fixed
# (AE6C-4804-98BA-C57B46965FE7), except for a few legacy formats.
# --------------------------------------------------------------------------
FIXED_TAIL = "AE6C-4804-98BA-C57B46965FE7"


def format_guid(code: int) -> str:
    return "{%08X-%s}" % (code << 16, FIXED_TAIL)


@dataclass(frozen=True)
class MediaFormat:
    ext: str
    code: int            # MTP object format code sent to the device
    kind: str            # audio | video | image
    label: str
    guid: str = ""       # explicit GUID override when not the standard pattern

    @property
    def object_format(self) -> str:
        return self.guid or format_guid(self.code)


# Codes observed on / declared by the Zune 30 firmware.  The FLAC code is the
# one the community firmware registers (47366 = 0xB906).
FORMATS: dict[str, MediaFormat] = {
    ".mp3": MediaFormat(".mp3", 0x3009, "audio", "MP3"),
    ".wma": MediaFormat(".wma", 0xB901, "audio", "WMA"),
    ".asf": MediaFormat(".asf", 0xB901, "audio", "WMA/ASF"),
    ".wav": MediaFormat(".wav", 0x3008, "audio", "WAV"),
    ".m4a": MediaFormat(".m4a", 0x300A, "audio", "AAC/M4A",
                        guid="{30ABA7AC-6FFD-4C23-A359-3E9B52F3F1C8}"),
    ".aac": MediaFormat(".aac", 0xB903, "audio", "AAC"),
    ".flac": MediaFormat(".flac", 0xB906, "audio", "FLAC"),
    ".wmv": MediaFormat(".wmv", 0xB982, "video", "WMV"),
    ".mp4": MediaFormat(".mp4", 0xB984, "video", "MP4"),
    ".jpg": MediaFormat(".jpg", 0x3801, "image", "JPEG"),
    ".jpeg": MediaFormat(".jpeg", 0x3801, "image", "JPEG"),
    ".png": MediaFormat(".png", 0x3800, "image", "PNG"),
}

SUPPORTED_AUDIO = tuple(e for e, f in FORMATS.items() if f.kind == "audio")
SUPPORTED_VIDEO = tuple(e for e, f in FORMATS.items() if f.kind == "video")


def detect(path: os.PathLike | str) -> MediaFormat | None:
    return FORMATS.get(Path(path).suffix.lower())


# --------------------------------------------------------------------------
# Tag and cover extraction
# --------------------------------------------------------------------------
@dataclass
class Track:
    path: Path
    fmt: MediaFormat
    size: int
    title: str = ""
    artist: str = ""
    album: str = ""
    albumartist: str = ""
    genre: str = ""
    track: int = 0
    year: str = ""
    duration_ms: int = 0
    cover: bytes = b""
    cover_mime: str = ""
    error: str = ""

    @property
    def remote_name(self) -> str:
        """Name the device will show.  Keep the real extension."""
        return self.path.name

    def key(self) -> str:
        """Stable identity for de-duplication."""
        h = hashlib.sha1()
        h.update(self.path.name.lower().encode("utf-8", "ignore"))
        h.update(b"|")
        h.update(str(self.size).encode())
        h.update(b"|")
        h.update((self.title or "").lower().encode("utf-8", "ignore"))
        return h.hexdigest()[:16]


def _first(value) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return "" if value is None else str(value)


def read_track(path: os.PathLike | str) -> Track | None:
    p = Path(path)
    fmt = detect(p)
    if fmt is None or fmt.kind not in ("audio", "video"):
        return None
    t = Track(path=p, fmt=fmt, size=p.stat().st_size)
    try:
        _read_tags(t)
    except Exception as exc:                      # corrupt/unsupported file
        t.error = f"{type(exc).__name__}: {exc}"
    return t


def _read_tags(t: Track) -> None:
    from mutagen import File as MutagenFile

    audio = MutagenFile(t.path)
    if audio is None:
        return
    tags = audio.tags or {}

    def get(*names):
        for n in names:
            try:
                value = tags.get(n) if hasattr(tags, "get") else None
            except Exception:
                value = None
            if value:
                return _first(value)
        return ""

    t.title = get("TIT2", "title", "\xa9nam", "Title")
    t.artist = get("TPE1", "artist", "\xa9ART", "Author")
    t.album = get("TALB", "album", "\xa9alb", "WM/AlbumTitle")
    t.albumartist = get("TPE2", "albumartist", "aART", "WM/AlbumArtist")
    t.genre = get("TCON", "genre", "\xa9gen", "WM/Genre")
    year = get("TDRC", "date", "\xa9day", "WM/Year")
    t.year = year[:4] if year else ""
    trk = get("TRCK", "tracknumber", "trkn", "WM/TrackNumber")
    try:
        t.track = int(str(trk).split("/")[0])
    except (TypeError, ValueError):
        t.track = 0
    if getattr(audio, "info", None) is not None:
        t.duration_ms = int(getattr(audio.info, "length", 0) * 1000)
    t.cover, t.cover_mime = _read_cover(audio)


def _read_cover(audio) -> tuple[bytes, str]:
    # ID3 (MP3)
    tags = getattr(audio, "tags", None)
    if tags is not None:
        for key in list(getattr(tags, "keys", lambda: [])()):
            if str(key).startswith("APIC"):
                apic = tags[key]
                return bytes(apic.data), apic.mime or "image/jpeg"
        # FLAC / Ogg
        pics = getattr(audio, "pictures", None)
        if pics:
            return bytes(pics[0].data), pics[0].mime or "image/jpeg"
        # MP4
        covr = tags.get("covr") if hasattr(tags, "get") else None
        if covr:
            item = covr[0]
            mime = "image/png" if getattr(item, "imageformat", None) == 14 else "image/jpeg"
            return bytes(item), mime
        # ASF (WMA)
        pic = tags.get("WM/Picture") if hasattr(tags, "get") else None
        if pic:
            item = pic[0] if isinstance(pic, list) else pic
            data = getattr(item, "value", b"") or b""
            mime = getattr(item, "mime", "") or "image/jpeg"
            if data:
                return bytes(data), mime
    return b"", ""


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------
@dataclass
class PlanItem:
    track: Track
    action: str          # add | replace | skip
    reason: str = ""


@dataclass
class Plan:
    items: list[PlanItem] = field(default_factory=list)
    skipped: list[PlanItem] = field(default_factory=list)

    @property
    def to_add(self) -> list[PlanItem]:
        return [i for i in self.items if i.action in ("add", "replace")]


def scan(paths: Iterable[os.PathLike | str], recursive: bool = True) -> list[Track]:
    tracks: list[Track] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            t = read_track(p)
            if t:
                tracks.append(t)
            continue
        if not p.is_dir():
            continue
        it = p.rglob("*") if recursive else p.glob("*")
        for f in sorted(it):
            if not f.is_file():
                continue
            t = read_track(f)
            if t:
                tracks.append(t)
    return tracks


def build_plan(tracks: list[Track], existing: Iterable[str] = ()) -> Plan:
    """existing: names already present on the device (case-insensitive)."""
    have = {n.lower() for n in existing}
    plan = Plan()
    for t in tracks:
        if t.fmt.kind == "video":
            reason = "video not covered by this build"
            plan.skipped.append(PlanItem(t, "skip", reason))
            continue
        if t.error:
            plan.skipped.append(PlanItem(t, "skip", t.error))
            continue
        if t.remote_name.lower() in have:
            plan.skipped.append(PlanItem(t, "skip", "already on device"))
            continue
        plan.items.append(PlanItem(t, "add", ""))
    return plan


def summarize(plan: Plan) -> str:
    lines = [f"to add : {len(plan.to_add)}", f"skipped: {len(plan.skipped)}"]
    for it in plan.items[:50]:
        t = it.track
        flags = []
        if t.cover:
            flags.append("cover")
        if t.album:
            flags.append("album")
        lines.append(f"  + {t.path.name}  [{t.fmt.label}]  {t.size/1e6:.1f} MB"
                     + (("  (" + ", ".join(flags) + ")") if flags else ""))
    for it in plan.skipped[:50]:
        lines.append(f"  - {it.track.path.name}: {it.reason}")
    return "\n".join(lines)
