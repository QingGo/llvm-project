#!/usr/bin/env python3
"""
Cross‑platform build script for MLIR Python bindings wheel.
Version: 2.1 - Robust version parsing for LLVM tags
"""

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --- Configuration ---
BUILD_DIR = Path("build")
WHEELHOUSE = Path("wheelhouse")
MLIR_PYTHON_PKG = BUILD_DIR / "tools/mlir/python_packages/mlir_core"


def run(cmd, **kwargs):
    """Run a command, printing it and checking its return code."""
    print(f"Running: {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def get_pep440_version(raw_tag: str) -> str:
    """
    Convert an LLVM tag like 'llvmorg-22.1.5' or 'llvmorg-23-init'
    into a valid PEP 440 version.
    """
    # 1. Remove any leading non-numeric prefix (e.g., "llvmorg-")
    version = re.sub(r'^[^0-9]*', '', raw_tag)

    # 2. Handle special development tags
    #    '23-init' -> '23.0.0.dev0'
    #    '23-dev'  -> '23.0.0.dev0'
    if re.search(r'-(init|dev)', version):
        base = version.split('-')[0]
        # If the base is just a major number (e.g., "23"), add ".0.0"
        if re.match(r'^\d+$', base):
            version = f"{base}.0.0.dev0"
        else:
            version = f"{base}.dev0"
        return version

    # 3. For rc / final tags: if the version already looks like X.Y.Z, it's fine
    #    Also add '.0' if only major.minor is given (e.g., "22.1" -> "22.1.0")
    parts = version.split('.')
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        version = f"{version}.0"

    # 4. Replace any remaining invalid characters with a dot (just to be safe)
    version = re.sub(r'[^0-9.]+', '.', version).strip('.')

    return version


def main():
    print("===== Step 1: Clean and create directories =====")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    WHEELHOUSE.mkdir(exist_ok=True)

    python_exe = sys.executable
    raw_version = os.environ.get("LLVM_VERSION", "22.1.5")
    pkg_version = get_pep440_version(raw_version)

    print(f"Raw LLVM tag: {raw_version}")
    print(f"PEP 440 version for wheel: {pkg_version}")

    print(f"===== Step 2: CMake Configuration =====")
    cmake_args = [
        "cmake",
        "-G", "Ninja",
        "-S", str(Path("llvm").resolve()),
        "-B", str(BUILD_DIR.resolve()),
        "-DLLVM_ENABLE_PROJECTS=mlir",
        "-DMLIR_ENABLE_BINDINGS_PYTHON=ON",
        "-DPython3_EXECUTABLE=" + python_exe,
        "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
        "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0",
    ]

    if platform.system() == "Darwin":
        arch = platform.machine()
        cmake_args += [
            "-DCMAKE_OSX_ARCHITECTURES=" + arch,
            "-DLLVM_TARGETS_TO_BUILD=Native",
        ]
        print(f"   -> Cross-compiling for architecture: {arch}")

    if platform.system() == "Windows":
        cmake_args += [
            "-DCMAKE_C_COMPILER=clang-cl",
            "-DCMAKE_CXX_COMPILER=clang-cl",
        ]

    run(cmake_args)

    print("===== Step 3: Ninja Build (MLIRPythonModules) =====")
    run(["ninja", "-C", str(BUILD_DIR), "MLIRPythonModules"])

    print("===== Step 4: Generate setup.py and MANIFEST.in =====")
    pkg_dir = MLIR_PYTHON_PKG
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Generate setup.py
    setup_py = f"""import setuptools

setuptools.setup(
    name="mlir-core",
    version="{pkg_version}",
    packages=setuptools.find_namespace_packages(where="."),
    include_package_data=True,
    python_requires=">=3.10",
    # Mark as having extension modules to generate platform-specific wheel tag
    has_ext_modules=lambda: True,
)
"""
    (pkg_dir / "setup.py").write_text(setup_py)

    # Generate MANIFEST.in
    manifest = """recursive-include mlir *.py
recursive-include mlir *.so
recursive-include mlir *.dylib
recursive-include mlir *.pyi
recursive-include mlir *.h
recursive-include mlir *.typed
include *.so
include *.dylib
global-exclude *.pyc
global-exclude __pycache__
"""
    (pkg_dir / "MANIFEST.in").write_text(manifest)

    print(f"   -> setup.py and MANIFEST.in generated (version {pkg_version})")

    print("===== Step 5: Build Wheel Package =====")
    run([
        python_exe, "-m", "pip", "wheel",
        "-w", str(WHEELHOUSE.resolve()),
        str(pkg_dir.resolve()),
    ])

    print("\n===== Build Complete =====")
    print(f"Wheels in: {WHEELHOUSE}")
    for whl in sorted(WHEELHOUSE.glob("*.whl")):
        size_mb = whl.stat().st_size / (1024 * 1024)
        print(f"  - {whl.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
