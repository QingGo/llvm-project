#!/usr/bin/env python3
"""
Cross‑platform build script for MLIR Python bindings wheel.
Version: 2.0 - Fix wheel platform tag
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

# --- Helper Functions ---
def run(cmd, **kwargs):
    """Run a command, printing it and checking its return code."""
    print(f"Running: {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, **kwargs)

def get_generated_packages(base_dir: Path) -> list[str]:
    """Scans the base directory to find all generated Python packages."""
    packages = set()
    for root, dirs, files in os.walk(base_dir):
        # Filter out __pycache__ and other hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        # Add all directories that contain Python files
        if any(f.endswith('.py') for f in files):
            rel_path = Path(root).relative_to(base_dir)
            packages.add(str(rel_path).replace(os.sep, '.'))
    return list(packages)

# --- Main Script ---
def main():
    print("===== Step 1: Clean and create directories =====")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    WHEELHOUSE.mkdir(exist_ok=True)

    python_exe = sys.executable
    raw_version = os.environ.get("LLVM_VERSION", "22.1.5")
    pkg_version = re.sub(r'^[^0-9]*', '', raw_version)  # e.g., llvmorg-22.1.5 -> 22.1.5

    print(f"===== Step 2: CMake Configuration (LLVM {raw_version}) =====")
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
        # 👇 设置最低部署目标版本，确保生成的二进制兼容性
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

    # Dynamically discover packages to ensure nothing is missed
    packages = get_generated_packages(pkg_dir)
    packages = [p for p in packages if p and not p.startswith('.')]
    packages_str = ',\n        '.join(f'"{p}"' for p in sorted(packages))
    
    print(f"   -> Found {len(packages)} packages to include")

    # --- Generate setup.py ---
    setup_py = f"""import setuptools

setuptools.setup(
    name="mlir-core",
    version="{pkg_version}",
    packages=setuptools.find_namespace_packages(where="."),
    include_package_data=True,
    python_requires=">=3.10",
    # 👇 核心修复：标记为包含外部模块，强制生成平台标签（如 macosx_11_0_x86_64）
    has_ext_modules=lambda: True,
)
"""
    (pkg_dir / "setup.py").write_text(setup_py)

    # --- Generate MANIFEST.in ---
    # Explicitly include binary and type stub files that setuptools might otherwise miss
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

    print("   -> setup.py and MANIFEST.in generated successfully.")

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
