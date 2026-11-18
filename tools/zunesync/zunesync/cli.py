"""Command line entry point for zunesync."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import core
from .core import Plan, Track, build_plan, scan, summarize


def _emit(msg: str) -> None:
    print(msg, flush=True)


def cmd_scan(args) -> int:
    tracks = scan(args.paths, recursive=not args.no_recursive)
    for t in tracks:
        bits = [t.fmt.label, f"{t.size/1e6:.1f}MB"]
        if t.title:
            bits.append(t.title)
        if t.album:
            bits.append("album=" + t.album)
        if t.cover:
            bits.append(f"cover={len(t.cover)//1024}KB")
        if t.error:
            bits.append("ERROR " + t.error)
        _emit(f"{t.path}\n    " + " | ".join(bits))
    _emit(f"\n{len(tracks)} file(s)")
    return 0


def _open_device(args):
    from . import wpd

    devices = wpd.discover()
    if not devices:
        raise SystemExit("no WPD device found (is the Zune connected and the shell unlocked?)")
    chosen = devices[0]
    if args.device:
        for d in devices:
            if args.device.lower() in d.path.lower():
                chosen = d
                break
    _emit(f"device: {chosen.path}")
    return wpd.Device(chosen.path).open()


def _music_folder(dev, path: str) -> str:
    parts = [p for p in path.split("/") if p]
    oid = dev.find_path(*parts)
    if oid is not None:
        return oid
    # Some firmware revisions do not expose a named "Music" folder through
    # WPD; fall back to the first content node under the storage object.
    storage = dev.find_child("DEVICE", "Storage")
    if storage is None:
        raise SystemExit("device storage not found")
    kids = dev.children(storage)
    if not kids:
        raise SystemExit("device storage has no content node")
    print(f"note: {path} not found, using content root {kids[0]}", flush=True)
    return kids[0]


def cmd_plan(args) -> int:
    tracks = scan(args.paths, recursive=not args.no_recursive)
    existing: list[str] = []
    if not args.offline:
        dev = _open_device(args)
        try:
            music = _music_folder(dev, args.folder)
            existing = dev.list_names(music)
        finally:
            dev.close()
    plan = build_plan(tracks, existing)
    _emit(summarize(plan))
    return 0


def _media_props(track: Track, mapping: dict) -> dict:
    out: dict = {}
    if track.title:
        out[mapping["title"]] = track.title
    if track.artist:
        out[mapping["artist"]] = track.artist
    if track.album:
        out[mapping["album"]] = track.album
    if track.genre:
        out[mapping["genre"]] = track.genre
    if track.track:
        out[mapping["track"]] = track.track
    if track.year:
        out[mapping["year"]] = track.year
    if track.duration_ms:
        out[mapping["duration"]] = track.duration_ms
    return retuple(out)


def retuple(d: dict) -> dict:
    return {tuple(k) if isinstance(k, list) else k: v for k, v in d.items()}


def cmd_sync(args) -> int:
    from . import wpd

    tracks = scan(args.paths, recursive=not args.no_recursive)
    if not tracks:
        _emit("nothing to sync")
        return 0

    dev = _open_device(args)
    try:
        music = _music_folder(dev, args.folder)
        existing = dev.list_names(music)
        plan = build_plan(tracks, existing)
        _emit(summarize(plan))
        if args.dry_run:
            _emit("dry run: nothing written")
            return 0

        mapping = dict(wpd.DEFAULT_MEDIA_KEYS)
        if args.props:
            data = json.loads(Path(args.props).read_text(encoding="utf-8"))
            for k, v in data.items():
                mapping[k] = tuple(v)

        ok = 0
        failed = 0
        for n, item in enumerate(plan.to_add, 1):
            t = item.track
            _emit(f"[{n}/{len(plan.to_add)}] {t.path.name}")
            try:
                data = t.path.read_bytes()
                props = _media_props(t, mapping) if not args.no_metadata else {}
                if args.limit and n > args.limit:
                    _emit("limit reached")
                    break

                def progress(done, total):
                    if args.verbose:
                        _emit(f"    {done*100//max(total,1)}%")

                dev.create_object(music, t.remote_name, t.fmt.object_format,
                                  props, data, progress=progress)
                ok += 1
                _emit("    ok")
            except Exception as exc:
                failed += 1
                _emit(f"    failed: {type(exc).__name__}: {exc}")
        _emit(f"\nadded {ok}, failed {failed}")
        return 0 if failed == 0 else 1
    finally:
        dev.close()


def cmd_probe(args) -> int:
    dev = _open_device(args)
    try:
        folders = dev.list_names("DEVICE")
        _emit(f"DEVICE children: {folders}")
        for storage_name in folders:
            storage_id = dev.find_child("DEVICE", storage_name)
            if not storage_id:
                continue
            kids = dev.list_names(storage_id)
            _emit(f"  {storage_name}: {kids}")
            for folder in ("Music", "Playlists"):
                if folder in kids:
                    fid = dev.find_child(storage_id, folder)
                    names = dev.list_names(fid)
                    _emit(f"    {folder}: {len(names)} item(s)")
                    for nm in names[:args.sample]:
                        _emit(f"      {nm}")
                    if args.props and names:
                        target = dev.find_child(fid, names[0])
                        if target:
                            _emit(f"    properties of {names[0]}:")
                            for (guid, pid), value in dev.get_string_props(target).items():
                                _emit(f"      {{{guid}}}, {pid} = {value!r}")
    finally:
        dev.close()
    return 0


def cmd_verify(args) -> int:
    dev = _open_device(args)
    try:
        music = _music_folder(dev, args.folder)
        names = dev.list_names(music)
        want = {Path(p).name.lower() for p in args.names}
        missing = [n for n in want if n not in {x.lower() for x in names}]
        _emit(f"device has {len(names)} item(s) in {args.folder}")
        _emit("present: " + (", ".join(Path(n).name for n in want if n not in missing) or "-"))
        _emit("missing: " + (", ".join(Path(n).name for n in missing) or "-"))
        return 0 if not missing else 2
    finally:
        dev.close()



def cmd_enrich(args) -> int:
    """Patch metadata on an object that is already on the device."""
    from . import mtp

    paths = mtp.discover()
    if not paths:
        raise SystemExit("no device found")
    t = mtp.Transport(paths[0])
    try:
        storage = t.storages()[0]
        music = [h for h in t.handles(storage) if t.object_info(h).name == "Music"][0]
        target = None
        for h in t.handles(storage, 0, music):
            try:
                if t.object_info(h).name == args.name:
                    target = h
                    break
            except Exception:
                continue
        if target is None:
            raise SystemExit(f"object not found on device: {args.name}")

        props: dict[int, object] = {}
        if args.title:
            props[0xDC44] = args.title
        if args.artist:
            props[0xDC46] = args.artist
        if args.genre:
            props[0xDC8C] = args.genre
        if args.album:
            props[0xDC4F] = args.album

        for code, value in props.items():
            try:
                t.set_properties(target, {code: value})
                print(f"set {code:#06x} = {value!r}", flush=True)
            except Exception as exc:
                print(f"set {code:#06x} failed: {exc}", flush=True)
        return 0
    finally:
        t.close()

def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="zunesync",
                                 description="Sync local music to a Zune (MTP) device")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = dict()
    p = sub.add_parser("scan", help="list local files with parsed metadata")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-recursive", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("plan", help="compare local files with the device")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-recursive", action="store_true")
    p.add_argument("--folder", default="Storage/Music")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--device", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("sync", help="upload files to the device")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-recursive", action="store_true")
    p.add_argument("--folder", default="Storage/Music")
    p.add_argument("--device", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--no-metadata", action="store_true")
    p.add_argument("--props", default="", help="JSON overrides for media property keys")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("probe", help="show device tree and, optionally, property keys")
    p.add_argument("--device", default="")
    p.add_argument("--sample", type=int, default=5)
    p.add_argument("--props", action="store_true")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("verify", help="check that files are present on the device")
    p.add_argument("names", nargs="+")
    p.add_argument("--folder", default="Storage/Music")
    p.add_argument("--device", default="")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("enrich", help="set metadata on an object already on the device")
    p.add_argument("name", help="object name as shown on the device")
    p.add_argument("--title", default="")
    p.add_argument("--artist", default="")
    p.add_argument("--album", default="")
    p.add_argument("--genre", default="")
    p.set_defaults(func=cmd_enrich)

    args = ap.parse_args(argv)
    code = args.func(args)
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    # comtypes can crash while releasing COM objects at interpreter shutdown;
    # exit without running finalizers.
    os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
