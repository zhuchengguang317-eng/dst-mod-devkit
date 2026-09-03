#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dst_zip_tool.py -- Query Don't Starve Together's official script bundle
(data/databundles/scripts.zip) directly, without manual unpacking.

Zero third-party dependencies. Cross-platform (Windows/Linux/macOS path
auto-detection; override with --dst).

Usage:
    python dst_zip_tool.py list   [PATTERN] [--zip PATH | --dst DIR] [--limit N]
    python dst_zip_tool.py grep   REGEX [--path-glob GLOB] [-n] [--max-lines N]
    python dst_zip_tool.py show   FILE [--start N] [--end N]
    python dst_zip_tool.py extract FILE [--out DIR]

Examples:
    python dst_zip_tool.py list "scripts/components/weapon*"
    python dst_zip_tool.py grep "function.*:SetProjectile" --path-glob "scripts/components/*.lua"
    python dst_zip_tool.py show scripts/components/weapon.lua --start 90 --end 110
    python dst_zip_tool.py extract scripts/modutil.lua --out ./src

Notes:
- grep uses Python regex syntax (escape literal parens as \\( ).
- A one-time extraction cache is created next to this script (or in TMPDIR);
  it auto-invalidates when the game updates (size/mtime change).
"""

import argparse
import fnmatch
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile

ZIP_REL = os.path.join("data", "databundles", "scripts.zip")


def find_dst(user_path):
    """Locate the DST install (folder containing bin/)."""
    candidates = []
    if user_path:
        candidates.append(user_path)
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        candidates.append(os.path.join(
            home, "Library", "Application Support", "Steam",
            "steamapps", "common", "Don't Starve Together"))
    else:
        if sys.platform.startswith("linux"):
            candidates.append(os.path.join(
                home, ".local", "share", "Steam", "steamapps", "common",
                "Don't Starve Together"))
        # Windows-style candidates (also scanned from bash-on-windows etc.)
        for drive in "CDEFGH":
            for base in (
                "%s:\\Program Files (x86)\\Steam\\steamapps\\common" % drive,
                "%s:\\SteamLibrary\\steamapps\\common" % drive,
                "%s:\\steam\\steamapps\\common" % drive,
                "%s:\\Steam\\steamapps\\common" % drive,
            ):
                candidates.append(os.path.join(base, "Don't Starve Together"))
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, "bin")):
            return c
    return None


def locate_zip(args):
    if args.zip:
        if not os.path.isfile(args.zip):
            raise SystemExit("[dst_zip_tool] zip not found: %s" % args.zip)
        return args.zip
    dst = find_dst(args.dst)
    if not dst:
        raise SystemExit(
            "[dst_zip_tool] could not locate Don't Starve Together.\n"
            "  Pass --dst \"<DST install root>\" or --zip <path/to/scripts.zip>.")
    z = os.path.join(dst, ZIP_REL)
    if not os.path.isfile(z):
        raise SystemExit("[dst_zip_tool] scripts.zip not found at %s" % z)
    print("[dst_zip_tool] DST install: %s" % dst, file=sys.stderr)
    return z


def cache_root(zip_path):
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".zip_cache")
    if not os.access(os.path.dirname(base), os.W_OK):
        base = os.path.join(tempfile.gettempdir(), "dst_zip_tool_cache")
    key = "%d_%d" % (os.path.getsize(zip_path), int(os.path.getmtime(zip_path)))
    return os.path.join(base, key)


def ensure_cache(zip_path):
    """Extract the zip into a cache dir keyed by size+mtime (auto-invalidates)."""
    root = cache_root(zip_path)
    done = os.path.join(root, ".done")
    if os.path.isfile(done):
        return root
    if os.path.isdir(root):
        shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    t0 = time.time()
    print("[dst_zip_tool] extracting cache (one-time)...", file=sys.stderr)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(root)
    with open(done, "w") as f:
        f.write("ok\n")
    # prune stale caches of other versions
    parent = os.path.dirname(root)
    try:
        for name in os.listdir(parent):
            p = os.path.join(parent, name)
            if p != root and os.path.isdir(p) and not os.path.isfile(os.path.join(p, ".done")):
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass
    print("[dst_zip_tool] cached in %.1fs -> %s" % (time.time() - t0, root),
          file=sys.stderr)
    return root


def walk_files(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            yield os.path.join(dirpath, fn)


def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def cmd_list(args, root):
    pat = args.pattern or "*"
    n = 0
    for p in sorted(os.path.relpath(f, root).replace("\\", "/")
                    for f in walk_files(root)):
        if fnmatch.fnmatch(p, pat):
            print(p)
            n += 1
            if args.limit and n >= args.limit:
                print("... (truncated, use --limit N)", file=sys.stderr)
                break
    print("[dst_zip_tool] %d file(s)" % n, file=sys.stderr)


def cmd_grep(args, root):
    rx = re.compile(args.regex)
    glob_re = re.compile(
        fnmatch.translate(args.path_glob)) if args.path_glob else None
    hits = 0
    for f in walk_files(root):
        rel = os.path.relpath(f, root).replace("\\", "/")
        if not rel.endswith(".lua") and not rel.endswith(".po") and not rel.endswith(".xml"):
            continue
        if glob_re and not glob_re.match(rel):
            continue
        try:
            text = read_text(f)
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                prefix = "%s:%d:" % (rel, i) if args.line_numbers else "%s:" % rel
                print("%s%s" % (prefix, line.strip()))
                hits += 1
                if args.max_lines and hits >= args.max_lines:
                    print("... (truncated, refine regex)", file=sys.stderr)
                    return
    print("[dst_zip_tool] %d hit(s)" % hits, file=sys.stderr)


def resolve(root, path):
    """Resolve a zip-relative path case-insensitively (zip case may differ)."""
    p = os.path.join(root, path.replace("/", os.sep))
    if os.path.isfile(p):
        return p
    d, name = os.path.split(p)
    if os.path.isdir(d):
        for cand in os.listdir(d):
            if cand.lower() == name.lower():
                return os.path.join(d, cand)
    return None


def cmd_show(args, root):
    p = resolve(root, args.file)
    if not p:
        raise SystemExit("[dst_zip_tool] file not found in zip: %s "
                         "(use 'list' to check the exact path)" % args.file)
    lines = read_text(p).splitlines()
    start = max(1, args.start or 1)
    end = min(len(lines), args.end or (start + 39))
    for i in range(start, end + 1):
        print("%5d  %s" % (i, lines[i - 1]))
    print("[dst_zip_tool] lines %d-%d of %d" % (start, end, len(lines)),
          file=sys.stderr)


def cmd_extract(args, root):
    p = resolve(root, args.file)
    if not p:
        raise SystemExit("[dst_zip_tool] file not found in zip: %s" % args.file)
    out_dir = args.out or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, os.path.basename(p))
    shutil.copyfile(p, dest)
    print("[dst_zip_tool] extracted -> %s" % dest)


def main():
    ap = argparse.ArgumentParser(prog="dst_zip_tool",
                                 description="Query DST's official scripts.zip directly.")
    ap.add_argument("--dst", help="DST install root (auto-detected if omitted)")
    ap.add_argument("--zip", help="explicit path to scripts.zip")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list files matching a glob pattern")
    p.add_argument("pattern", nargs="?", default="*")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("grep", help="regex search across the bundle")
    p.add_argument("regex")
    p.add_argument("--path-glob", default=None,
                   help='e.g. "scripts/components/*.lua"')
    p.add_argument("-n", "--line-numbers", action="store_true")
    p.add_argument("--max-lines", type=int, default=300)
    p.set_defaults(fn=cmd_grep)

    p = sub.add_parser("show", help="print a file with line numbers")
    p.add_argument("file")
    p.add_argument("--start", type=int, default=None)
    p.add_argument("--end", type=int, default=None)
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("extract", help="extract a single file")
    p.add_argument("file")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_extract)

    args = ap.parse_args()
    zip_path = locate_zip(args)
    root = ensure_cache(zip_path)
    args.fn(args, root)


if __name__ == "__main__":
    main()
