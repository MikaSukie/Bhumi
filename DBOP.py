#!/usr/bin/env python3
import sys
import os
import subprocess
import shutil
import argparse

def parse_bool(items):
    if not items:
        return False
    v = items[0].strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def list_from_value(items):
    return items or []

def parse_op_file(path):
    config = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                k = key.strip().lower()
                items = [v.strip() for v in value.split(",") if v.strip() != ""]
                config[k] = items
    return config

def run(cmd, **kwargs):
    if isinstance(cmd, (list, tuple)):
        printable = " ".join(cmd)
    else:
        printable = str(cmd)
    print("+ " + printable)
    return subprocess.run(cmd, **kwargs)

def ensure_tool(name, required=True):
    if shutil.which(name) is None and not os.path.exists(name):
        msg = f"ERROR: required tool '{name}' not found in PATH or current directory."
        if required:
            print(msg)
            sys.exit(1)
        else:
            print(f"WARNING: {msg} (continuing, but functionality may be limited)")

def pkg_config_cflags(pkg_libs):
    if not pkg_libs:
        return []
    cmd = ["pkg-config", "--cflags"] + pkg_libs
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        flags = res.stdout.strip()
        return flags.split() if flags else []
    except subprocess.CalledProcessError as e:
        print("ERROR: pkg-config failed for --cflags with packages:", pkg_libs)
        print(e.stderr.strip() if e.stderr else e)
        sys.exit(1)

def pkg_config_libs(pkg_libs):
    if not pkg_libs:
        return []
    cmd = ["pkg-config", "--libs"] + pkg_libs
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        flags = res.stdout.strip()
        return flags.split() if flags else []
    except subprocess.CalledProcessError as e:
        print("ERROR: pkg-config failed for --libs with packages:", pkg_libs)
        print(e.stderr.strip() if e.stderr else e)
        sys.exit(1)

def build_package(op_file, overrides):
    print("Reading:", op_file)
    config = parse_op_file(op_file)

    package_name = overrides.package_name or config.get("package_name", ["main"])[0]
    c_files = overrides.c_sources or config.get("c_sources", [])
    bhumi_files = overrides.bhumi_sources or config.get("bhumi_sources", [])
    pkg_libs = overrides.pkg_libs or config.get("pkg_libs", [])
    manual_libs = config.get("manual_libs", [])[:]
    manual_libs += (overrides.manual_libs or [])

    link_paths = config.get("link_paths", [])[:]
    link_paths += (overrides.link_paths or [])
    link_libs = config.get("link_libs", [])[:]
    link_libs += (overrides.link_libs or [])

    extra_link_flags = config.get("extra_link_flags", [])[:]
    extra_link_flags += (overrides.extra_link_flags or [])
    extra_clang_flags = config.get("extra_clang_flags", [])[:]
    extra_clang_flags += (overrides.extra_clang_flags or [])
    extra_bhumi_args = config.get("extra_bhumi_args", [])[:]
    extra_bhumi_args += (overrides.extra_bhumi_args or [])

    optimize = overrides.optimize if overrides.optimize is not None else parse_bool(config.get("optimize", []))
    opt_level = overrides.opt_level or (config.get("opt_level", ["O2"])[0] if config.get("opt_level") else "O2")
    autorun = overrides.autorun if overrides.autorun is not None else parse_bool(config.get("autorun", []))
    run_args = overrides.run_args or config.get("run_args", [])
    bhumi_binary = config.get("bhumi_binary", ["./BHUMI.py"])[0]

    ensure_tool(bhumi_binary)
    ensure_tool("clang")
    if optimize:
        ensure_tool("opt")

    cflags = pkg_config_cflags(pkg_libs)
    ldflags = pkg_config_libs(pkg_libs)

    if extra_clang_flags:
        cflags += extra_clang_flags

    llvm_files = []
    if bhumi_files:
        entry = None
        for src in bhumi_files:
            try:
                with open(src, 'r', encoding='utf-8', errors='ignore') as f:
                    txt = f.read()
                if 'fn main' in txt:
                    entry = src
                    break
            except Exception:
                pass
        if entry is None:
            entry = bhumi_files[0]

        out_ll = entry[:-6] + ".ll" if entry.endswith(".bhumi") else entry + ".ll"
        opt_out_ll = os.path.splitext(out_ll)[0] + f".{opt_level}.ll" if optimize else out_ll

        bhumi_cmd = [bhumi_binary, entry, "-o", out_ll] + extra_bhumi_args
        run(bhumi_cmd, check=True)

        if optimize:
            opt_cmd = ["opt", f"-{opt_level}", out_ll, "-o", opt_out_ll]
            run(opt_cmd, check=True)
            llvm_files = [opt_out_ll]
        else:
            llvm_files = [out_ll]

    obj_files = []
    for c in c_files:
        if not c.endswith(".c"):
            print(f"WARNING: C source '{c}' does not end with .c (skipping).")
            continue
        obj = c[:-2] + ".o"
        cmd = ["clang", "-c", c, f"-{opt_level}" if optimize else "-O2"] + cflags + ["-o", obj]
        run(cmd, check=True)
        obj_files.append(obj)

    manual_ld = []
    for lib in manual_libs:
        if lib.startswith("-"):
            manual_ld.append(lib)
        elif os.path.exists(lib) or "/" in lib or lib.endswith(".a") or lib.endswith(".so"):
            manual_ld.append(lib)
        else:
            manual_ld.append(f"-l{lib}")

    for lib in link_libs:
        if lib.startswith("-"):
            manual_ld.append(lib)
        else:
            if os.path.exists(lib) or "/" in lib or lib.endswith(".a") or lib.endswith(".so"):
                manual_ld.append(lib)
            else:
                manual_ld.append(f"-l{lib}")

    manual_ld += link_paths

    manual_ld += ldflags
    manual_ld += extra_link_flags

    link_cmd = ["clang"] + llvm_files + obj_files + manual_ld + ["-o", package_name]

    print("\nLink command:")
    print(" ".join(link_cmd))
    run(link_cmd, check=True)

    print(f"\nBuild complete: {package_name}")

    if autorun:
        print("\nAutorun enabled. Running the built binary...")
        try:
            res = run(["./" + package_name] + run_args)
            print("Exit code:", res.returncode)
        except KeyboardInterrupt:
            print("Interrupted by user.")
    return package_name

def parse_args():
    p = argparse.ArgumentParser(description="BHUMI build driver (flexible .op handling)")
    p.add_argument("opfile", nargs="?", help=".op file to use (auto-selects if omitted)")
    p.add_argument("--package-name", help="override package name (output binary name)")
    p.add_argument("--c-source", action="append", dest="c_sources", help="add a C source (can be given multiple times)")
    p.add_argument("--bhumi-source", action="append", dest="bhumi_sources", help="add a BHUMI source (can be given multiple times)")
    p.add_argument("--pkg-lib", action="append", dest="pkg_libs", help="pkg-config packages to query (appendable)")
    p.add_argument("--manual-lib", action="append", dest="manual_libs", help="manual link lib (appendable), can be -lNAME or path")
    p.add_argument("--link-path", action="append", dest="link_paths", help="explicit library path to pass to linker (appendable)")
    p.add_argument("--link-lib", action="append", dest="link_libs", help="link lib name (will become -lNAME if not a path)")
    p.add_argument("--extra-link-flag", action="append", dest="extra_link_flags", help="extra linker flags (appendable)")
    p.add_argument("--extra-clang-flag", action="append", dest="extra_clang_flags", help="extra clang flags (appendable)")
    p.add_argument("--extra-bhumi-arg", action="append", dest="extra_bhumi_args", help="extra arg passed to BHUMI.py")
    p.add_argument("--optimize", dest="optimize", action="store_true", help="enable optimization pass (runs opt)")
    p.add_argument("--no-optimize", dest="optimize", action="store_false", help="disable optimization pass (explicit)")
    p.set_defaults(optimize=None)
    p.add_argument("--opt-level", dest="opt_level", help="optimization level for opt and clang (O2, O3, etc.)")
    p.add_argument("--autorun", dest="autorun", action="store_true", help="run binary after successful build")
    p.add_argument("--no-autorun", dest="autorun", action="store_false", help="do not run after build (explicit)")
    p.set_defaults(autorun=None)
    p.add_argument("--run-arg", action="append", dest="run_args", help="argument to pass on autorun (appendable)")
    return p.parse_args()

def choose_op_file(arg_path=None):
    if arg_path:
        if not os.path.exists(arg_path):
            print("ERROR: specified .op file does not exist:", arg_path)
            sys.exit(1)
        return arg_path
    files = [f for f in os.listdir(".") if f.endswith(".op")]
    if len(files) == 0:
        print("ERROR: no .op files found in current directory.")
        sys.exit(1)
    if len(files) == 1:
        return files[0]
    print("Multiple .op files found. Specify which one on the command line.")
    for i, f in enumerate(files):
        print(f"{i+1}: {f}")
    print("Use: ./build.py <filename.op>")
    sys.exit(1)

if __name__ == "__main__":
    args = parse_args()
    op_path = choose_op_file(args.opfile)
    build_package(op_path, args)
