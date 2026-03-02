#!/usr/bin/env python3

import sys
import os
import subprocess
import shutil
os.system("clear")
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
    print("+ " + " ".join(cmd))
    return subprocess.run(cmd, **kwargs)

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

def ensure_tool(name):
    if shutil.which(name) is None and not os.path.exists(name):
        print(f"ERROR: required tool '{name}' not found in PATH or current directory.")
        sys.exit(1)

def build_package(op_file):
    print("Reading:", op_file)
    config = parse_op_file(op_file)

    package_name = config.get("package_name", ["main"])[0]
    c_files = config.get("c_sources", [])
    bhumi_files = config.get("bhumi_sources", [])
    pkg_libs = config.get("pkg_libs", [])
    manual_libs = config.get("manual_libs", [])

    ensure_tool("./BHUMI.py")
    ensure_tool("opt")
    ensure_tool("clang")

    cflags = pkg_config_cflags(pkg_libs)
    ldflags = pkg_config_libs(pkg_libs)

    if not bhumi_files:
        llvm_files = []
    else:
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
        opt_out = out_ll

        run(["./BHUMI.py", entry, "-o", out_ll], check=True)
        # run(["opt", "-O2", out_ll, "-o", opt_out], check=True)
        llvm_files = [opt_out]

    obj_files = []
    for c in c_files:
        if not c.endswith(".c"):
            print(f"WARNING: C source '{c}' does not end with .c (skipping).")
            continue
        obj = c[:-2] + ".o"
        # cmd = ["clang", "-O2", "-c", c] + cflags + ["-o", obj]
        cmd = ["clang", "-c", c] + cflags + ["-o", obj]
        run(cmd, check=True)
        obj_files.append(obj)

    manual_ld = []
    for lib in manual_libs:
        if lib.startswith("-l"):
            manual_ld.append(lib)
        elif lib.startswith("-"):
            manual_ld.append(lib)
        else:
            manual_ld.append(f"-l{lib}")

    link_cmd = ["clang"] + llvm_files + obj_files + ldflags + manual_ld + ["-o", package_name]
    print("\nLink command:")
    print(" ".join(link_cmd))
    run(link_cmd, check=True)

    print(f"\nBuild complete: {package_name}")

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
    print("Multiple .op files found. Specify which one:")
    for i, f in enumerate(files):
        print(f"{i+1}: {f}")
    try:
        choice = int(input("> ")) - 1
        if choice < 0 or choice >= len(files):
            raise ValueError()
    except Exception:
        print("Invalid choice.")
        sys.exit(1)
    return files[choice]

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    op_path = choose_op_file(arg)
    build_package(op_path)
