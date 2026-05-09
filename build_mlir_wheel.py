#!/usr/bin/env python3
"""Cross‑platform build script for MLIR Python bindings wheel."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path("build")
WHEELHOUSE = Path("wheelhouse")
MLIR_PYTHON_PKG = Path("mlir/tools/mlir/python_packages/mlir_core")


def run(cmd, **kwargs):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main():
    # Clean previous build
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    WHEELHOUSE.mkdir(exist_ok=True)

    # Determine Python executable
    python_exe = sys.executable

    # CMake configuration
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

    # macOS specific: target the appropriate architecture
    if platform.system() == "Darwin":
        arch = platform.machine()  # 'x86_64' or 'arm64'
        cmake_args += [
            "-DCMAKE_OSX_ARCHITECTURES=" + arch,
            "-DLLVM_TARGETS_TO_BUILD=Native",
        ]

    # Windows specific: use clang-cl or MSVC (Ninja works with both)
    if platform.system() == "Windows":
        cmake_args += [
            "-DCMAKE_C_COMPILER=clang-cl",
            "-DCMAKE_CXX_COMPILER=clang-cl",
        ]

    run(cmake_args)

    # Build the Python bindings target
    run(["ninja", "-C", str(BUILD_DIR), "mlir-python-bindings"])

    # Build the wheel using pip
    run([
        python_exe, "-m", "pip", "wheel",
        "-w", str(WHEELHOUSE.resolve()),
        str(MLIR_PYTHON_PKG.resolve()),
    ])

    print(f"\n✅ Wheel built successfully. Find it in: {WHEELHOUSE}")
    for whl in WHEELHOUSE.glob("*.whl"):
        print(whl.name)


if __name__ == "__main__":
    main()
