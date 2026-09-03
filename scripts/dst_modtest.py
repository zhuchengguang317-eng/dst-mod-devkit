#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dst-modtest -- Headless boot & behavior tester for Don't Starve Together mods.

Boots the game's own dedicated server (nullrenderer) with your mod enabled in a
disposable offline cluster, watches the log, and reports PASS/FAIL -- no game
client, no Steam login, no GUI. Exit code 0/1 makes it CI-friendly.

Vendored into dst-mod-devkit from the standalone project:
    https://github.com/zhuchengguang317-eng/dst-modtest
(updates happen there first; see testing.md for full usage docs)

Usage:
    python dst_modtest.py <mod_folder> [more_mod_folders...] [options]

    python dst_modtest.py "D:/dst_mods/MyMod"
    python dst_modtest.py workshop-123456789 --script my_test.lua
    python dst_modtest.py MyMod ItsDependency --timeout 300

Requires: Don't Starve Together installed (the dedicated server binary ships
with the base game). Windows-first; no third-party dependencies.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

# Markers ---------------------------------------------------------------

# Phase 1: every enabled mod loaded without dying (most boot crashes die here)
MARK_LUA_LOADED = "LOADING LUA SUCCESS"
# Phase 2: world generated and the shard is up
MARK_WORLD_UP = "Telling Client our new session identifier"
# Optional phase 3: user behavior script reported success
MARK_SCRIPT_OK = "[MODTEST] SCRIPT_OK"

# Patterns that mean the run is doomed (checked before success is declared).
# NOTE: DST is very forgiving -- a mod with a broken modmain still boots the
# server ("Error loading mod!" is printed and the game continues). Without
# watching for these, a completely dead mod would report PASS!
FAIL_PATTERNS = [
    "Error loading mod!",
    "Error loading modinfo.lua",
    "LUA ERROR",
    "[Error]",
    "Error loading file",
    "terminated prematurely",
    "Couldn't find mod",
    "Could not find mod",
]
# Benign log line that contains "Error" but is harmless (seen on healthy boots)
BENIGN_PATTERNS = ["Error trying to change cluster setting"]

DEFAULT_CLUSTER_PREFIX = "DstModTest"
DEFAULT_TIMEOUT = 240


def find_dst(user_path):
    """Locate the Don't Starve Together install (folder containing bin/)."""
    candidates = []
    if user_path:
        candidates.append(user_path)
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


def server_binary(dst):
    exe = os.path.join(dst, "bin", "dontstarve_dedicated_server_nullrenderer.exe")
    if os.path.isfile(exe):
        return exe
    raise SystemExit("[dst-modtest] dedicated server not found at %s\n"
                     "Pass --dst \"<DST install>\" explicitly." % exe)


def read_modinfo_name(mod_dir):
    """Best-effort: read `name = "..."` from modinfo.lua (for nicer output)."""
    try:
        with open(os.path.join(mod_dir, "modinfo.lua"), "r",
                  encoding="utf-8", errors="replace") as f:
            m = re.search(r'name\s*=\s*"([^"]*)"', f.read())
            return m.group(1) if m else os.path.basename(mod_dir)
    except OSError:
        return os.path.basename(mod_dir)


class TempMod(object):
    """A mod to enable. `staged_dir` is set when we had to copy it into <DST>/mods."""

    def __init__(self, src, dst_root):
        self.src = os.path.abspath(src)
        self.staged_dir = None
        if not os.path.isfile(os.path.join(self.src, "modinfo.lua")):
            raise SystemExit("[dst-modtest] not a mod folder (no modinfo.lua): %s" % self.src)
        name = os.path.basename(self.src.rstrip("\\/"))
        mods_root = os.path.join(dst_root, "mods")
        if os.path.isdir(os.path.join(mods_root, name)):
            self.key = name  # already inside <DST>/mods, load as-is
        else:
            key = "_modtest_" + re.sub(r"[^A-Za-z0-9_]", "_", name)
            self.staged_dir = os.path.join(mods_root, key)
            shutil.copytree(self.src, self.staged_dir, dirs_exist_ok=True)
            self.key = key

    def cleanup(self):
        if self.staged_dir and os.path.isdir(self.staged_dir):
            shutil.rmtree(self.staged_dir, ignore_errors=True)


def write_cluster(klei_root, cluster_name, mod_keys):
    """Create a disposable offline cluster enabling exactly `mod_keys`."""
    import random
    cluster = os.path.join(klei_root, cluster_name)
    master = os.path.join(cluster, "Master")
    os.makedirs(master, exist_ok=True)
    # random port: avoid clashing with a running game/dedicated server on 10999
    port = random.randint(10990, 10999)
    with open(os.path.join(cluster, "cluster.ini"), "w", encoding="utf-8") as f:
        f.write("[gameplay]\nmax_players = 1\npvp = false\ngame_mode = survival\n\n"
                "[network]\nlan_only_cluster = true\ncluster_intention = cooperative\n"
                "cluster_name = DstModTest\n\n"
                "[shard]\nshard_enabled = false\n")
    with open(os.path.join(master, "server.ini"), "w", encoding="utf-8") as f:
        f.write("[network]\nport = %d\n\n[shard]\nis_master = true\n\n"
                "[account]\ndedicated_lan_server = true\n" % port)
    overrides = ["return {"]
    for k in mod_keys:
        overrides.append('  ["%s"] = { enabled = true, configuration_options = {} },' % k)
    overrides.append("}")
    with open(os.path.join(master, "modoverrides.lua"), "w", encoding="utf-8") as f:
        f.write("\n".join(overrides) + "\n")
    return cluster


RUNNER_MODINFO = '''name = "dst_modtest_runner"
author = "dst-modtest"
version = "1.0.0"
api_version = 10
dst_compatible = true
all_clients_require_mod = false
client_only_mod = false
server_only_mod = true
description = "Temporary behavior-test runner generated by dst-modtest"
'''

RUNNER_MODMAIN = '''-- Generated by dst-modtest. Runs the user test script 10s after world load.
AddPrefabPostInit("world", function(inst)
    if not GLOBAL.TheWorld.ismastersim then
        return
    end
    inst:DoTaskInTime(10, function()
        GLOBAL.print("[MODTEST] runner: executing test script")
        modimport("test_script.lua")
    end)
end)
'''


def stage_runner(dst_root, script_path, stamp):
    """Create a temporary runner mod that executes the user's test script."""
    key = "_modtest_runner_%s" % stamp
    mod_dir = os.path.join(dst_root, "mods", key)
    os.makedirs(mod_dir, exist_ok=True)
    with open(os.path.join(mod_dir, "modinfo.lua"), "w", encoding="utf-8") as f:
        f.write(RUNNER_MODINFO)
    with open(os.path.join(mod_dir, "modmain.lua"), "w", encoding="utf-8") as f:
        f.write(RUNNER_MODMAIN)
    shutil.copy(script_path, os.path.join(mod_dir, "test_script.lua"))
    return key, mod_dir


def _pump(proc, log_file, quiet, queue):
    """Background thread: keep reading server output so we never block forever."""
    try:
        for line in proc.stdout:
            log_file.write(line)
            if not quiet and line.strip():
                sys.stdout.write(line if line.endswith("\n") else line + "\n")
            queue.put(line)
    except (ValueError, OSError):
        pass  # stream closed / terminated


def run_server(bin_dir, cluster_name, timeout, quiet, need_script):
    """Boot the server, stream the log, classify the outcome."""
    import queue
    import threading

    exe = os.path.join(bin_dir, "dontstarve_dedicated_server_nullrenderer.exe")
    if not os.path.isfile(exe):  # future-proofing: Linux dedicated server layout
        exe = os.path.join(bin_dir, "dontstarve_dedicated_server_nullrenderer")
    log_path = os.path.join(bin_dir, "..", "dst_modtest_last_run.log")
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [exe, "-offline", "-console", "-cluster", cluster_name, "-shard", "Master"],
        cwd=bin_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    lua_loaded = False
    world_up = False
    script_ok = False
    fail_reason = None
    interesting = []
    deadline = time.time() + timeout
    q = queue.Queue()
    t = threading.Thread(target=_pump, args=(proc, log_file, quiet, q), daemon=True)
    t.start()

    def shutdown():
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=15)
            except Exception:
                pass

    try:
        while True:
            # deadline is checked even when the server stops printing
            if time.time() > deadline:
                if fail_reason is None:
                    fail_reason = "timeout: boot milestones not reached in %ds" % timeout
                shutdown()
                break
            try:
                line = q.get(timeout=0.5)
            except queue.Empty:
                if proc.poll() is not None:
                    break  # server exited on its own (e.g. script called os.exit)
                continue
            if any(p in line for p in BENIGN_PATTERNS):
                continue
            if MARK_LUA_LOADED in line:
                lua_loaded = True
            if MARK_WORLD_UP in line:
                world_up = True
            if MARK_SCRIPT_OK in line:
                script_ok = True
            if any(p in line for p in FAIL_PATTERNS) and fail_reason is None:
                fail_reason = line.strip()
                interesting.append(line.strip())
                shutdown()
                break
            if line.strip() and (
                    "Registering prefab" in line or "Mod:" in line
                    or "Error" in line or "MODTEST" in line
                    or "LOADING LUA" in line or "Telling Client" in line):
                interesting.append(line.strip())
            # all required milestones hit -> clean shutdown, report PASS
            if lua_loaded and world_up and (script_ok or not need_script):
                shutdown()
                break
    finally:
        if proc.poll() is None:
            shutdown()
        log_file.close()

    return {
        "lua_loaded": lua_loaded,
        "world_up": world_up,
        "script_ok": script_ok,
        "fail_reason": fail_reason,
        "rc": proc.returncode,
        "interesting": interesting[-30:],
        "log": os.path.abspath(log_path),
    }


def main():
    ap = argparse.ArgumentParser(
        prog="dst-modtest",
        description="Headless boot & behavior tester for Don't Starve Together mods.")
    ap.add_argument("mods", nargs="+", help="mod folder(s); first = test target, "
                    "rest = dependencies enabled alongside")
    ap.add_argument("--dst", help="DST install root (auto-detected if omitted)")
    ap.add_argument("--klei", help="Klei documents root "
                    "(default: %%USERPROFILE%%/Documents/Klei/DoNotStarveTogether)")
    ap.add_argument("--script", help="optional Lua behavior-test script "
                    '(must print "[MODTEST] SCRIPT_OK" on success)')
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="seconds to wait for the server (default %(default)s)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the temp cluster / staged mods for debugging")
    ap.add_argument("--quiet", action="store_true", help="do not stream server log")
    args = ap.parse_args()

    dst = find_dst(args.dst)
    if not dst:
        raise SystemExit("[dst-modtest] could not locate Don't Starve Together; "
                         "pass --dst \"<install root>\"")
    bin_dir = os.path.join(dst, "bin")
    print("[dst-modtest] DST install: %s" % dst)

    klei = args.klei or os.path.join(
        os.environ.get("USERPROFILE", os.path.expanduser("~")),
        "Documents", "Klei", "DoNotStarveTogether")
    os.makedirs(klei, exist_ok=True)

    stamp = "%d" % (int(time.time()) % 100000)
    cluster_name = DEFAULT_CLUSTER_PREFIX + "_" + stamp
    mods = [TempMod(m, dst) for m in args.mods]
    keys = [m.key for m in mods]
    if args.script:
        rkey, rdir = stage_runner(dst, args.script, stamp)
        keys.append(rkey)
        print("[dst-modtest] runner mod staged: %s (script: %s)" % (rkey, args.script))
    print("[dst-modtest] enabling mods: %s" % ", ".join(keys))

    names = ", ".join(read_modinfo_name(m.src) for m in mods)
    print("[dst-modtest] testing: %s" % names)

    cluster_dir = write_cluster(klei, cluster_name, keys)
    print("[dst-modtest] cluster: %s" % cluster_dir)
    print("[dst-modtest] booting dedicated server (offline, up to %ds)..." % args.timeout)

    res = run_server(bin_dir, cluster_name, args.timeout, args.quiet,
                     need_script=args.script is not None)

    passed = (res["lua_loaded"] and res["world_up"]
              and (args.script is None or res["script_ok"])
              and res["fail_reason"] is None)

    print("")
    print("=" * 64)
    if passed:
        print("[dst-modtest] RESULT: PASS  ✔")
    else:
        print("[dst-modtest] RESULT: FAIL  ✘")
        if res["fail_reason"]:
            print("  fail line : %s" % res["fail_reason"])
        print("  lua loaded: %s | world up: %s | script ok: %s"
              % (res["lua_loaded"], res["world_up"], res["script_ok"]))
    print("  full log  : %s" % res["log"])
    print("=" * 64)

    if not args.keep:
        shutil.rmtree(cluster_dir, ignore_errors=True)
        for m in mods:
            m.cleanup()
        if args.script:
            rdir = os.path.join(dst, "mods", "_modtest_runner_%s" % stamp)
            shutil.rmtree(rdir, ignore_errors=True)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
