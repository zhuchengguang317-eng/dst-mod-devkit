#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_api.py -- Verify that component/entity methods called in your DST mod
Lua files actually exist in the official game source.

Catches the "syntactically valid, crashes at runtime" class of bugs, e.g.:
    inventory:Count()          (does not exist; use NumItems)
    SetOnPickUpFn              (typo; correct is SetOnPickupFn)
    hunger:GetCurrent()        (server component has no such method)

Zero third-party dependencies. Locates the official scripts.zip the same way
dst_zip_tool.py does (auto-detect / --dst / --zip / --scripts-dir for a
pre-unpacked tree).

Usage:
    python check_api.py <file.lua> [more.lua ...]
    python check_api.py ./scripts/            (checks all .lua under a dir)
Options:
    --dst DIR          DST install root override
    --zip PATH         explicit scripts.zip path
    --scripts-dir DIR  use a pre-unpacked scripts tree instead of the zip
    --quiet            only print problems
Exit code: 0 = PASS, 1 = FAIL (unknown method found), 2 = setup error.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dst_zip_tool as zt  # reuse path detection + cache

ALLOWED_INST_METHODS = {
    "AddComponent", "RemoveComponent", "ListenForEvent", "RemoveEventCallback",
    "PushEvent", "DoTaskInTime", "DoPeriodicTask", "SpawnChild",
    "GetDisplayName", "IsValid", "Remove",
}


def collect_component_methods(root):
    """{component_name: set(method_or_field)} from scripts/components/*.lua."""
    comps_dir = os.path.join(root, "scripts", "components")
    result = {}
    if not os.path.isdir(comps_dir):
        return result
    fn_rx = re.compile(r"function\s+[\w.]+\s*:\s*(\w+)\s*\(")
    field_rx = re.compile(r"self\.(\w+)\s*=")
    for fn in os.listdir(comps_dir):
        if not fn.endswith(".lua"):
            continue
        name = fn[:-4]
        if name.endswith("_replica"):
            name = name[:-8]  # merge replica methods into the main component
        try:
            text = zt.read_text(os.path.join(comps_dir, fn))
        except OSError:
            continue
        methods = result.setdefault(name, set())
        methods.update(fn_rx.findall(text))
        methods.update(field_rx.findall(text))
    return result


def collect_entityscript_methods(root):
    es = os.path.join(root, "scripts", "entityscript.lua")
    if not os.path.isfile(es):
        return set()
    text = zt.read_text(es)
    return set(re.findall(r"function\s+[\w.]+\s*:\s*(\w+)\s*\(", text))


def lua_files_from_args(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _d, files in os.walk(p):
                for f in files:
                    if f.endswith(".lua"):
                        yield os.path.join(dirpath, f)
        elif os.path.isfile(p):
            yield p


def check_file(path, comp_methods, es_methods, quiet):
    problems = []
    checked = 0
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return ["[?] cannot read %s: %s" % (path, e)], 0
    # strip Lua comments so commented-out calls are not flagged
    src_nc = re.sub(r"--\[\[[\s\S]*?\]\]", "", src)
    src_nc = re.sub(r"--[^\n]*", "", src_nc)

    added = sorted(set(re.findall(
        r'AddComponent\s*\(\s*["\'](\w+)["\']', src_nc)))
    if not quiet:
        print("  components used: %s" % (", ".join(added) or "(none)"))

    for m in re.finditer(r'components\.(\w+)\s*[:.]\s*(\w+)\s*\(', src_nc):
        comp, method = m.group(1), m.group(2)
        checked += 1
        known = comp_methods.get(comp)
        if known is None:
            problems.append("[?] %s:%s() -- component source not found "
                            "(may be non-standard)" % (comp, method))
        elif method not in known:
            sample = sorted(k for k in known if k[:2] == method[:2])[:8] or sorted(known)[:12]
            problems.append("[X] %s:%s() -- NOT FOUND. similar/available: %s"
                            % (comp, method, sample))
        elif not quiet:
            print("  [ok] %s:%s()" % (comp, method))

    for m in re.finditer(r'(?<![\w.])inst\s*:\s*(\w+)\s*\(', src_nc):
        method = m.group(1)
        checked += 1
        if method in ALLOWED_INST_METHODS:
            continue
        if method not in es_methods:
            problems.append("[?] inst:%s() -- not in entityscript.lua "
                            "(may be engine-level or undefined)" % method)

    return problems, checked


def main():
    ap = __import__("argparse").ArgumentParser(prog="check_api")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--dst"); ap.add_argument("--zip"); ap.add_argument("--scripts-dir")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.scripts_dir:
        root = args.scripts_dir
        if not os.path.isdir(root):
            raise SystemExit("[check_api] --scripts-dir not found: %s" % root)
    else:
        zip_path = zt.locate_zip(args)
        root = zt.ensure_cache(zip_path)

    comp_methods = collect_component_methods(root)
    es_methods = collect_entityscript_methods(root)
    if not comp_methods:
        print("[check_api] WARNING: no components found under %s" % root,
              file=sys.stderr)

    total_problems, total_checked = [], 0
    for path in lua_files_from_args(args.files):
        if not args.quiet:
            print("checking %s" % path)
            print("-" * 60)
        problems, checked = check_file(path, comp_methods, es_methods, args.quiet)
        total_problems.extend("  (%s) %s" % (os.path.basename(path), p) for p in problems)
        total_checked += checked
        if not args.quiet:
            print()

    print("=" * 60)
    if total_problems:
        print("check_api: FAIL -- %d problem(s) in %d calls:"
              % (len(total_problems), total_checked))
        for p in total_problems:
            print(p)
        sys.exit(1)
    print("check_api: PASS -- %d component/entity calls verified, "
          "0 unknown methods" % total_checked)
    sys.exit(0)


if __name__ == "__main__":
    main()
