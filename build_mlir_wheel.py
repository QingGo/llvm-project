#!/usr/bin/env python3
"""Cross‑platform build script for MLIR Python bindings wheel."""
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path("build")
WHEELHOUSE = Path("wheelhouse")
MLIR_PYTHON_PKG = BUILD_DIR / "tools/mlir/python_packages/mlir_core"


def run(cmd, **kwargs):
    print(f"Running: {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main():
    # Clean previous build
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    WHEELHOUSE.mkdir(exist_ok=True)

    python_exe = sys.executable

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
    ]

    if platform.system() == "Darwin":
        arch = platform.machine()
        cmake_args += [
            "-DCMAKE_OSX_ARCHITECTURES=" + arch,
            "-DLLVM_TARGETS_TO_BUILD=Native",
        ]

    if platform.system() == "Windows":
        cmake_args += [
            "-DCMAKE_C_COMPILER=clang-cl",
            "-DCMAKE_CXX_COMPILER=clang-cl",
        ]

    run(cmake_args)
    run(["ninja", "-C", str(BUILD_DIR), "MLIRPythonModules"])

    # Generate a PEP 440 version from the LLVM tag (e.g. llvmorg-22.1.5 → 22.1.5)
    raw_version = os.environ.get("LLVM_VERSION", "22.1.5")
    pkg_version = re.sub(r'^[^0-9]*', '', raw_version)

    pkg_dir = MLIR_PYTHON_PKG
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # ---- setup.py ----
    setup_py = f"""\
import setuptools  # noqa: E402

setuptools.setup(
    name="mlir-core",
    version="{pkg_version}",
    packages=setuptools.find_namespace_packages(where="."),
    include_package_data=True,
    python_requires=">=3.10",
)
"""
    (pkg_dir / "setup.py").write_text(setup_py)

    # ---- MANIFEST.in ----
    manifest = """\
recursive-include mlir *.py
recursive-include mlir *.so
recursive-include mlir *.dylib
recursive-include mlir *.pyi
recursive-include mlir *.h
recursive-include mlir *.typed
"""
    (pkg_dir / "MANIFEST.in").write_text(manifest)

    print(f"Generated setup.py and MANIFEST.in for version {pkg_version}")

    run([
        python_exe, "-m", "pip", "wheel",
        "-w", str(WHEELHOUSE.resolve()),
        str(pkg_dir.resolve()),
    ])

    print(f"\n✅ Wheel built successfully. Find it in: {WHEELHOUSE}")
    for whl in WHEELHOUSE.glob("*.whl"):
        print(whl.name)


if __name__ == "__main__":
    main()
