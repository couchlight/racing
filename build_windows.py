#!/usr/bin/env python3
"""
Windows MSVC / Nuitka build.

Run from 'Developer PowerShell for VS 2022' in the project root:
    python build_windows.py

Output: dist_msvc/Racing.dist/Racing.exe
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

from version import get_version

APP_NAME = "Racing"
ENTRY_POINT = "main.py"
DIST_ROOT = Path("dist_msvc")
DIST = DIST_ROOT / f"{APP_NAME}.dist"
APP_VERSION = get_version()
COMPANY_NAME = "Couchlight LLC"
COPYRIGHT = "© 2026 Couchlight LLC. All rights reserved."


def _nuitka_is_commercial():
    """True if the installed Nuitka is the commercial (drop-in) edition.

    Nuitka's `--version` output carries a "Commercial:" line — a value for the
    commercial build, "None" for the open-source one. Returns False if Nuitka
    is missing or the line is absent, so callers default to the OSS behavior.
    """
    try:
        result = subprocess.run([sys.executable, '-m', 'nuitka', '--version'],
                                capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    for ln in result.stdout.splitlines():
        if ln.strip().lower().startswith('commercial:'):
            return ln.split(':', 1)[1].strip().lower() not in ('', 'none')
    return False


def check_build_environment():
    """Check if we're in the right build environment"""
    print("🔍 Checking build environment...")

    if not os.path.exists(ENTRY_POINT):
        print(f"❌ {ENTRY_POINT} not found - run this script from the project folder")
        return False

    # Check for MSVC compiler
    try:
        result = subprocess.run(['cl'], capture_output=True, text=True)
        if 'Microsoft' in result.stderr or 'Microsoft' in result.stdout:
            output = result.stderr if result.stderr else result.stdout
            for line in output.split('\n'):
                if 'Microsoft' in line and 'C/C++' in line:
                    print(f"✅ MSVC compiler available: {line.strip()}")
                    break
        else:
            raise FileNotFoundError
    except FileNotFoundError:
        print("❌ MSVC compiler not found")
        print("   Run this from 'Developer PowerShell for VS 2022'")
        print("   Or 'Developer Command Prompt for VS 2022'")
        return False

    py_version = sys.version_info
    print(f"✅ Python {py_version.major}.{py_version.minor}.{py_version.micro}")

    for module in ("pygame", "moderngl"):
        try:
            __import__(module)
            print(f"✅ {module} available")
        except ImportError:
            print(f"❌ {module} not installed - run: pip install {module}")
            return False

    # Check Nuitka
    try:
        result = subprocess.run([sys.executable, '-m', 'nuitka', '--version'],
                                capture_output=True, text=True, check=True)
        nuitka_version = result.stdout.strip().split('\n')[0]
        print(f"✅ Nuitka found: {nuitka_version}")
        if _nuitka_is_commercial():
            print("🔒 Nuitka Commercial detected — IP-protection plugins will be enabled")
        else:
            print("🔓 Open-source Nuitka — commercial plugins unavailable")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Nuitka not found - run: pip install nuitka")
        return False

    print("✅ Build environment ready")
    return True


def find_vcruntime_dlls():
    """Find Visual C++ runtime DLLs needed for MSVC builds"""
    print("\n🔍 Locating Visual C++ runtime DLLs...")

    runtime_dlls = {}

    search_paths = [
        r"C:\Windows\System32",
        r"C:\Windows\SysWOW64",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Redist\MSVC",
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Redist\MSVC",
    ]

    required_dlls = [
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'msvcp140.dll',
        'msvcp140_1.dll',
        'msvcp140_2.dll',
    ]

    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue

        # If it's a Redist folder, search subdirectories
        if 'Redist' in search_path:
            for root, dirs, files in os.walk(search_path):
                for dll_name in required_dlls:
                    if dll_name in files and dll_name not in runtime_dlls:
                        dll_path = os.path.join(root, dll_name)
                        # Prefer x64 versions
                        if 'x64' in root.lower() or 'x86_64' in root.lower():
                            runtime_dlls[dll_name] = dll_path
        else:
            for dll_name in required_dlls:
                dll_path = os.path.join(search_path, dll_name)
                if os.path.exists(dll_path) and dll_name not in runtime_dlls:
                    runtime_dlls[dll_name] = dll_path

    print(f"   Found {len(runtime_dlls)} runtime DLLs:")
    for dll_name in runtime_dlls:
        print(f"     ✅ {dll_name}")

    if len(runtime_dlls) < 3:
        print("   ⚠️  Some runtime DLLs missing - build may not be portable")

    return runtime_dlls


def build_app():
    """Build with the MSVC compiler"""
    print(f"\n🔨 Building {APP_NAME} with MSVC...")

    if DIST_ROOT.exists():
        print("🧹 Cleaning previous build...")
        try:
            shutil.rmtree(DIST_ROOT)
            print("   Cleanup successful")
        except Exception as e:
            print(f"⚠️  Warning: Cleanup had issues: {e}")
            print("   Continuing anyway...")

    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--assume-yes-for-downloads",
        "--msvc=latest",
        "--output-dir=" + str(DIST_ROOT),
        "--output-filename=" + APP_NAME,
        "--windows-console-mode=attach",
        # Windows exe metadata (Properties > Details tab)
        "--company-name=" + COMPANY_NAME,
        "--product-name=" + APP_NAME,
        "--file-version=" + APP_VERSION,
        "--product-version=" + APP_VERSION,
        "--file-description=" + APP_NAME,
        "--copyright=" + COPYRIGHT,
        "--jobs=12",
        "--nofollow-import-to=*.tests",
    ]

    # Nuitka Commercial IP protection — only when the commercial (drop-in)
    # edition is installed, so open-source/dev builds stay a no-op.
    # Signing is NOT done here — release_windows.py signs post-build.
    if _nuitka_is_commercial():
        print("🔒 Enabling Nuitka Commercial protections: data-hiding, no_docstrings")
        cmd.append("--enable-plugin=data-hiding")
        cmd.append("--python-flag=no_docstrings")

    if os.path.exists("icon.ico"):
        cmd.append("--windows-icon-from-ico=icon.ico")
        cmd.append("--include-data-file=icon.ico=icon.ico")

    if os.path.isdir("assets"):
        cmd.append("--include-data-dir=assets=assets")

    cmd.append(ENTRY_POINT)

    print("🚀 Running Nuitka compilation with MSVC...")
    print("   This may take several minutes...")

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True)

        for line in process.stdout:
            line = line.strip()
            if any(keyword in line for keyword in [
                'error', 'Error', 'ERROR', 'failed', 'Failed', 'FAILED',
                'warning', 'Warning', 'WARNING', 'Successfully created',
                'Nuitka:', 'Backend C compiler', 'Included', 'files DLLs'
            ]):
                print(f"   {line}")

        process.wait()

        if process.returncode != 0:
            print(f"❌ Nuitka compilation failed (return code: {process.returncode})")
            return False

        # Nuitka names the dist folder after the entry script (main.dist).
        nuitka_dist = DIST_ROOT / f"{Path(ENTRY_POINT).stem}.dist"
        if nuitka_dist != DIST:
            nuitka_dist.rename(DIST)
        print("✅ Nuitka compilation successful")
        return True

    except Exception as e:
        print(f"❌ Build error: {e}")
        return False


def bundle_vcruntime(runtime_dlls):
    """Bundle Visual C++ runtime DLLs"""
    print("\n📋 Bundling Visual C++ runtime DLLs...")

    if not DIST.exists():
        print("❌ Nuitka dist folder not found")
        return False

    if not runtime_dlls:
        print("⚠️  No runtime DLLs to bundle - may not work on clean systems")
        return True

    try:
        copied_count = 0
        for dll_name, dll_path in runtime_dlls.items():
            dest_path = DIST / dll_name
            if not dest_path.exists():
                shutil.copy2(dll_path, dest_path)
                copied_count += 1
                print(f"   ✅ Bundled: {dll_name}")
            else:
                print(f"   ⏭️  Already present: {dll_name}")

        print(f"✅ Bundled {copied_count} new runtime DLLs")
        return True

    except Exception as e:
        print(f"❌ Error bundling runtime DLLs: {e}")
        return False


def analyze_build_result():
    """Analyze the build result"""
    print("\n📊 Analyzing build...")

    exe_path = DIST / f"{APP_NAME}.exe"

    if not exe_path.exists():
        print("❌ Executable not found")
        return False

    total_size = sum(f.stat().st_size for f in DIST.rglob('*') if f.is_file())
    exe_size = exe_path.stat().st_size

    print("✅ Build successful!")
    print(f"   Executable: {exe_path}")
    print(f"   Size: {exe_size / (1024 * 1024):.1f} MB "
          f"(Total: {total_size / (1024 * 1024):.1f} MB)")

    runtime_dlls = ['vcruntime140.dll', 'msvcp140.dll']
    found_runtime = [dll for dll in runtime_dlls if (DIST / dll).exists()]
    if found_runtime:
        print(f"   Runtime DLLs: {len(found_runtime)} bundled (portable)")

    return True


def create_zip_archive():
    """Creates a zip archive of the final distribution folder."""
    print("\n📦 Creating final ZIP archive...")

    if not DIST.exists():
        print(f"❌ Distribution folder not found at: {DIST}")
        return False

    try:
        shutil.make_archive(
            base_name=str(DIST),
            format='zip',
            root_dir=str(DIST_ROOT),
            base_dir=DIST.name,
        )
        print(f"✅ ZIP archive created: {DIST}.zip")
        return True
    except Exception as e:
        print(f"❌ Failed to create ZIP archive: {e}")
        return False


def main():
    print(f"🚀 {APP_NAME} MSVC Windows Build System")
    print("=" * 50)

    if not check_build_environment():
        return 1

    runtime_dlls = find_vcruntime_dlls()

    if not build_app():
        return 1

    if not bundle_vcruntime(runtime_dlls):
        print("\n⚠️  Runtime DLL bundling had issues")

    if not analyze_build_result():
        return 1

    create_zip_archive()

    print("\n🎉 Build complete!")
    print(f"🚀 Run: {DIST / (APP_NAME + '.exe')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
