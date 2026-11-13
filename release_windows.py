#!/usr/bin/env python3
# release_windows.py
"""
Windows release pipeline.

Produces:  Racing-{version}-win-x64.zip
           Racing-{version}-win-x64-Setup.exe  (only if Racing.iss exists)

Usage:
    python release_windows.py

Steps performed:
    1. Prompt for version bump (patch / minor / major / custom / keep)
    2. Update version.py
    3. Build with MSVC  (python build_windows.py)
    4. Sign all bundled PEs  (signtool + Sectigo timestamp server)  [optional]
    5. Compile Inno Setup installer  (ISCC.exe Racing.iss)          [optional]
    6. Sign the installer EXE
    7. Create ZIP of Racing.dist folder
    8. SHA-256 the ZIP
    9. Print a summary

Environment variables (put in .env or set in shell):
    ISCC_PATH       Path to ISCC.exe (default: standard Inno Setup 6 location)
    SIGNTOOL_PATH   Path to signtool.exe (default: standard Windows SDK location)
    SIGN_SHA1       SHA-1 thumbprint of the code-signing cert
"""

import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from release_utils import (
    load_dotenv,
    sha256_file,
    prompt_version_bump,
    update_version_file,
    artifact_summary,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PLATFORM_TAG  = "win-x64"
APP_NAME      = "Racing"
ISS_FILE      = "Racing.iss"
MSVC_BUILD    = "build_windows.py"
OUTPUT_DIR    = Path("dist_msvc") / f"{APP_NAME}.dist"
INSTALLER_DIR = Path("installer_output")
UPDATE_DIR    = Path("update_output")

ISCC_DEFAULT      = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
ISCC_PATH         = os.getenv("ISCC_PATH", ISCC_DEFAULT)

SIGNTOOL_DEFAULT  = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe"
SIGNTOOL_PATH     = os.getenv("SIGNTOOL_PATH", SIGNTOOL_DEFAULT)

# Explicit signing-cert selection. signtool /a auto-selects the "best" code-
# signing cert in the store, which can wrongly pick a self-signed test cert
# over the Sectigo OV cert on the hardware token. Set SIGN_SHA1 to the Sectigo
# cert's SHA-1 thumbprint to force the right cert. With the token inserted:
#   Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
#     Format-List Subject,Issuer,Thumbprint,NotAfter
SIGN_SHA1 = os.getenv("SIGN_SHA1", "").replace(" ", "").strip()


def _cert_selector() -> list[str]:
    """signtool args selecting the signing cert: /sha1 <thumbprint> if
    SIGN_SHA1 is set, else /a (auto-select) with a warning."""
    if SIGN_SHA1:
        return ["/sha1", SIGN_SHA1]
    print("  ⚠  SIGN_SHA1 not set — using /a (auto-select). signtool may pick the")
    print("     WRONG cert (e.g. a self-signed test cert → untrusted signature).")
    print("     Set SIGN_SHA1 in .env to your Sectigo cert's SHA-1 thumbprint.")
    return ["/a"]


def _verify_trusted(path: Path) -> bool:
    """True if `path` has an Authenticode signature that chains to a trusted
    root (what Defender/SmartScreen require). A self-signed cert fails this."""
    return subprocess.run(
        [SIGNTOOL_PATH, "verify", "/pa", "/q", str(path)],
        capture_output=True,
    ).returncode == 0


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def run_msvc_build() -> bool:
    print()
    print("=" * 60)
    print(f"  STEP 1 — MSVC build  ({MSVC_BUILD})")
    print("=" * 60)
    if not Path(MSVC_BUILD).exists():
        print(f"  ✗ {MSVC_BUILD} not found.")
        return False
    result = subprocess.run([sys.executable, MSVC_BUILD])
    if result.returncode != 0:
        print("\n  ✗ MSVC build failed.")
        return False
    print("\n  ✓ MSVC build complete.")
    return True


# ---------------------------------------------------------------------------
# Code signing
# ---------------------------------------------------------------------------

def sign_file(path: Path) -> bool:
    """
    Sign a PE binary using signtool.exe with the Sectigo RFC 3161 timestamp
    server.

    Returns True if signing succeeded or the user chose to skip.  Returns
    False if the user wants to abort.
    """
    print()
    print("=" * 60)
    print(f"  CODE SIGNING — {path.name}")
    print("=" * 60)

    if not Path(SIGNTOOL_PATH).exists():
        print(f"  ✗ signtool.exe not found at: {SIGNTOOL_PATH}")
        print("    Install the Windows SDK or set SIGNTOOL_PATH in .env")
        ans = input("  Skip signing and continue? (y/n): ").strip().lower()
        return ans == "y"

    result = subprocess.run([
        SIGNTOOL_PATH, "sign",
        "/tr", "http://timestamp.sectigo.com",
        "/td", "sha256",
        "/fd", "sha256",
        *_cert_selector(),
        str(path),
    ])

    if result.returncode != 0:
        print(f"\n  ✗ Code signing failed for {path.name}")
        ans = input("  Skip signing and continue? (y/n): ").strip().lower()
        return ans == "y"

    if not _verify_trusted(path):
        print(f"\n  ✗ Signed, but {path.name}'s signature chain is NOT trusted —")
        print("    signtool likely used the wrong certificate (e.g. a self-signed")
        print("    test cert). Set SIGN_SHA1 to your Sectigo thumbprint and re-run.")
        print("    Do NOT ship this build.")
        ans = input("  Continue anyway? (y/n): ").strip().lower()
        return ans == "y"

    print(f"\n  ✓ Signed: {path.name}")
    return True


def sign_tree(root: Path) -> bool:
    """
    Authenticode-sign every bundled PE (.exe/.dll/.pyd) under `root` that is
    not already validly signed, using the same signtool + Sectigo RFC-3161
    timestamp setup as sign_file().

    Files that already carry a valid Authenticode signature (the Microsoft VC
    runtime, the Python DLL, any already-signed third-party DLL) are left
    untouched.

    Files are batched into as few signtool invocations as the command-line
    length allows, so a hardware-token PIN is requested as few times as
    possible.

    Returns True on success or if the user chooses to skip; False to abort.
    """
    print()
    print("=" * 60)
    print(f"  CODE SIGNING — bundled PEs under {root}")
    print("=" * 60)

    if not Path(SIGNTOOL_PATH).exists():
        print(f"  ✗ signtool.exe not found at: {SIGNTOOL_PATH}")
        print("    Install the Windows SDK or set SIGNTOOL_PATH in .env")
        ans = input("  Skip signing and continue? (y/n): ").strip().lower()
        return ans == "y"

    pe_files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in (".exe", ".dll", ".pyd")
    )
    if not pe_files:
        print("  ⚠  No PE files found to sign.")
        return True

    unsigned: list[Path] = []
    for p in pe_files:
        verify = subprocess.run(
            [SIGNTOOL_PATH, "verify", "/pa", "/q", str(p)],
            capture_output=True,
        )
        if verify.returncode != 0:
            unsigned.append(p)

    already = len(pe_files) - len(unsigned)
    print(f"  {len(pe_files)} PE file(s) found — {already} already signed, "
          f"{len(unsigned)} to sign.")
    if not unsigned:
        print("  ✓ Nothing to sign (all bundled PEs already signed).")
        return True

    # Batch into signtool calls bounded by command-line length.
    MAX_CMDLINE = 28000
    base_cmd = [
        SIGNTOOL_PATH, "sign",
        "/tr", "http://timestamp.sectigo.com",
        "/td", "sha256",
        "/fd", "sha256",
        *_cert_selector(),
    ]
    base_len = sum(len(a) + 3 for a in base_cmd)

    batches: list[list[str]] = []
    batch: list[str] = []
    batch_len = base_len
    for p in unsigned:
        arg = str(p)
        if batch and batch_len + len(arg) + 3 > MAX_CMDLINE:
            batches.append(batch)
            batch, batch_len = [], base_len
        batch.append(arg)
        batch_len += len(arg) + 3
    if batch:
        batches.append(batch)

    for i, group in enumerate(batches, 1):
        print(f"  Signing batch {i}/{len(batches)} ({len(group)} file(s))…")
        result = subprocess.run(base_cmd + group)
        if result.returncode != 0:
            print(f"\n  ✗ Code signing failed on batch {i}.")
            ans = input("  Skip remaining signing and continue? (y/n): ").strip().lower()
            return ans == "y"

    if not _verify_trusted(unsigned[0]):
        print(f"\n  ✗ Signed {len(unsigned)} PE(s), but the signature chain is NOT")
        print("    trusted — signtool used the wrong certificate (e.g. a self-signed")
        print("    test cert). Set SIGN_SHA1 to your Sectigo thumbprint and re-run.")
        print("    Do NOT ship this build.")
        ans = input("  Continue anyway? (y/n): ").strip().lower()
        return ans == "y"

    print(f"\n  ✓ Signed {len(unsigned)} bundled PE(s), chain verified trusted.")
    return True


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def _version_to_win(version: str) -> str:
    base = version.split("-")[0]
    parts = base.split(".")
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts[:4])


def create_installer(version: str) -> Path | None:
    print()
    print("=" * 60)
    print(f"  STEP 2 — Inno Setup installer  ({ISS_FILE})")
    print("=" * 60)
    if not Path(ISS_FILE).exists():
        print(f"  → {ISS_FILE} not found — skipping installer.")
        return None
    if not Path(ISCC_PATH).exists():
        print(f"  ✗ ISCC.exe not found at: {ISCC_PATH}")
        print("    Install Inno Setup 6  https://jrsoftware.org/isdl.php")
        print("    or set ISCC_PATH in .env")
        return None
    if not OUTPUT_DIR.exists():
        print(f"  ✗ Build output not found: {OUTPUT_DIR}")
        print("    Run the MSVC build first.")
        return None
    INSTALLER_DIR.mkdir(exist_ok=True)
    win_version = _version_to_win(version)
    result = subprocess.run([
        ISCC_PATH,
        f"/DMyAppVersion={version}",
        f"/DMyAppWinVersion={win_version}",
        f"/O{INSTALLER_DIR}",
        ISS_FILE,
    ])
    if result.returncode != 0:
        print("\n  ✗ Inno Setup compilation failed.")
        return None
    # ISS OutputBaseFilename should be: {#MyAppName}-{#MyAppVersion}-win-x64-Setup
    installer_path = INSTALLER_DIR / f"{APP_NAME}-{version}-win-x64-Setup.exe"
    if not installer_path.exists():
        print(f"\n  ✗ Expected installer not found: {installer_path}")
        print(f"    Check that {ISS_FILE} has:")
        print("      OutputBaseFilename={#MyAppName}-{#MyAppVersion}-win-x64-Setup")
        return None
    size_mb = installer_path.stat().st_size / 1_048_576
    print(f"\n  ✓ Installer created: {installer_path}  ({size_mb:.1f} MB)")
    return installer_path


# ---------------------------------------------------------------------------
# ZIP creation
# ---------------------------------------------------------------------------

def create_dist_zip(version: str) -> Path | None:
    print()
    print("=" * 60)
    print(f"  STEP 3 — Create ZIP  ({OUTPUT_DIR.name})")
    print("=" * 60)
    if not OUTPUT_DIR.exists():
        print(f"  ✗ Build output not found: {OUTPUT_DIR}")
        return None
    UPDATE_DIR.mkdir(exist_ok=True)
    zip_path = UPDATE_DIR / f"{APP_NAME}-{version}-{PLATFORM_TAG}.zip"
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file in OUTPUT_DIR.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(OUTPUT_DIR))
                file_count += 1
    size_mb = zip_path.stat().st_size / 1_048_576
    print(f"  ✓ ZIP created : {zip_path.name}  ({size_mb:.1f} MB, {file_count} files)")
    return zip_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 60)
    print(f"  {APP_NAME} — Windows Release Pipeline  [{PLATFORM_TAG}]")
    print("=" * 60)

    print()
    ans = input("  Code-sign binaries? (y/n, default n): ").strip().lower()
    do_sign = ans == "y"
    print(f"  → {'Yes — will sign bundled PEs and installer' if do_sign else 'No — skipping signing'}")

    new_version = prompt_version_bump()
    if not new_version:
        return

    print()
    print("=" * 60)
    print("  STEP 0 — Update version")
    print("=" * 60)
    update_version_file(new_version)

    if not run_msvc_build():
        return

    pe_signed = False
    if do_sign:
        if not sign_tree(OUTPUT_DIR):
            return
        pe_signed = True

    installer_path = create_installer(new_version)
    installer_signed = False
    installer_checksum: str | None = None
    if installer_path and installer_path.exists():
        if do_sign:
            if not sign_file(installer_path):
                return
            installer_signed = True
        installer_checksum = sha256_file(installer_path)
        hash_file = installer_path.with_suffix(".sha256")
        hash_file.write_text(f"{installer_checksum}  {installer_path.name}\n")
        print(f"  SHA-256 : {installer_checksum}")
        print(f"  ✓ Hash saved → {hash_file.name}")

    zip_path = create_dist_zip(new_version)
    zip_checksum: str | None = None
    if zip_path and zip_path.exists():
        print()
        print("=" * 60)
        print("  STEP 3b — SHA-256 ZIP")
        print("=" * 60)
        zip_checksum = sha256_file(zip_path)
        hash_file = zip_path.with_suffix(".sha256")
        hash_file.write_text(f"{zip_checksum}  {zip_path.name}\n")
        print(f"  SHA-256   : {zip_checksum}")
        print(f"  ✓ Hash saved → {hash_file.name}")

    print()
    print("=" * 60)
    print("  RELEASE SUMMARY")
    print("=" * 60)
    print(f"  Platform     : {PLATFORM_TAG}")
    print(f"  Version      : {new_version}")
    print(f"  Release date : {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Build output : {OUTPUT_DIR}")
    artifact_summary("Installer", installer_path, installer_checksum)
    artifact_summary("ZIP", zip_path, zip_checksum)
    print(f"  PE signing   : {'✓ (all bundled PEs)' if pe_signed else '✗ (skipped)'}")
    print(f"  Installer sig: {'✓' if installer_signed else '✗ (skipped or no installer)'}")
    print()
    print(f"  Test the build: {OUTPUT_DIR / (APP_NAME + '.exe')}")
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
