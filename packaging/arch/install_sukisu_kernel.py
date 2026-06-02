#!/usr/bin/env python3
"""Install the locally built linux-zen kernel packages and refresh boot files.

This is intended for the SukiSU-Ultra + SUSFS linux-zen build in this tree.
Run it from a real terminal so sudo can ask for a password when needed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_CONFIGS = (
    "CONFIG_ANDROID_BINDER_IPC=y",
    "CONFIG_ANDROID_BINDERFS=y",
    "CONFIG_KSU=y",
    "CONFIG_KPM=y",
    "CONFIG_KSU_SUSFS=y",
)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Install built linux-zen SukiSU/SUSFS packages and update initramfs/GRUB.",
    )
    parser.add_argument(
        "--pkgdir",
        type=Path,
        default=script_dir,
        help="Directory containing linux-zen package files. Default: script directory.",
    )
    parser.add_argument(
        "--kernel-pkg",
        type=Path,
        help="Explicit linux-zen package path.",
    )
    parser.add_argument(
        "--headers-pkg",
        type=Path,
        help="Explicit linux-zen-headers package path.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=script_dir / "config.x86_64",
        help="Kernel config to validate before installing. Default: ./config.x86_64.",
    )
    parser.add_argument(
        "--grub-config",
        default="/boot/grub/grub.cfg",
        help="GRUB output path. Default: /boot/grub/grub.cfg.",
    )
    parser.add_argument(
        "--skip-initramfs",
        action="store_true",
        help="Do not run mkinitcpio -P after package installation.",
    )
    parser.add_argument(
        "--skip-grub",
        action="store_true",
        help="Do not run grub-mkconfig after package installation.",
    )
    parser.add_argument(
        "--noconfirm",
        action="store_true",
        help="Pass --noconfirm to pacman -U.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Do not prompt before running install commands.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without changing the system.",
    )
    return parser.parse_args()


def latest_match(pkgdir: Path, pattern: str, regex: str) -> Path:
    compiled = re.compile(regex)
    matches = [
        path
        for path in pkgdir.glob(pattern)
        if path.is_file() and compiled.fullmatch(path.name)
    ]
    if not matches:
        raise SystemExit(f"Package not found in {pkgdir}: {pattern}")
    return max(matches, key=lambda path: path.stat().st_mtime)


def find_packages(args: argparse.Namespace) -> tuple[Path, Path]:
    pkgdir = args.pkgdir.resolve()
    kernel_pkg = args.kernel_pkg.resolve() if args.kernel_pkg else latest_match(
        pkgdir,
        "linux-zen-*.pkg.tar.zst",
        r"linux-zen-[0-9].*-x86_64\.pkg\.tar\.zst",
    )
    headers_pkg = args.headers_pkg.resolve() if args.headers_pkg else latest_match(
        pkgdir,
        "linux-zen-headers-*.pkg.tar.zst",
        r"linux-zen-headers-[0-9].*-x86_64\.pkg\.tar\.zst",
    )
    for path in (kernel_pkg, headers_pkg):
        if not path.exists():
            raise SystemExit(f"Package does not exist: {path}")
    return kernel_pkg, headers_pkg


def validate_config(config: Path) -> None:
    if not config.exists():
        raise SystemExit(f"Config not found: {config}")
    text = config.read_text(encoding="utf-8", errors="replace")
    missing = [entry for entry in REQUIRED_CONFIGS if entry not in text]
    if missing:
        formatted = "\n".join(f"  - {entry}" for entry in missing)
        raise SystemExit(f"Required config entries are missing:\n{formatted}")


def sudo_prefix() -> list[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required command not found in PATH: {name}")


def run(command: list[str], *, dry_run: bool) -> None:
    printable = " ".join(command)
    print(f"+ {printable}")
    if dry_run:
        return
    subprocess.run(command, check=True)


def confirm(args: argparse.Namespace, kernel_pkg: Path, headers_pkg: Path) -> None:
    print("Kernel package:")
    print(f"  {kernel_pkg}")
    print("Headers package:")
    print(f"  {headers_pkg}")
    print()
    if args.dry_run or args.yes:
        return
    answer = input("Install these packages and update boot files? [y/N] ").strip().lower()
    if answer not in {"y", "yes", "s", "sim"}:
        raise SystemExit("Aborted.")


def main() -> int:
    args = parse_args()
    args.pkgdir = args.pkgdir.resolve()
    args.config = args.config.resolve()

    require_command("pacman")
    if not args.skip_initramfs:
        require_command("mkinitcpio")
    if not args.skip_grub:
        require_command("grub-mkconfig")

    kernel_pkg, headers_pkg = find_packages(args)
    validate_config(args.config)
    confirm(args, kernel_pkg, headers_pkg)

    pacman_cmd = sudo_prefix() + ["pacman", "-U"]
    if args.noconfirm:
        pacman_cmd.append("--noconfirm")
    pacman_cmd.extend([str(kernel_pkg), str(headers_pkg)])
    run(pacman_cmd, dry_run=args.dry_run)

    if not args.skip_initramfs:
        run(sudo_prefix() + ["mkinitcpio", "-P"], dry_run=args.dry_run)

    if not args.skip_grub:
        run(
            sudo_prefix() + ["grub-mkconfig", "-o", args.grub_config],
            dry_run=args.dry_run,
        )

    print()
    if args.dry_run:
        print("Dry-run complete. No system changes were made.")
    else:
        print("Installation complete. Reboot into the new linux-zen kernel before testing Waydroid.")
    print("Post-reboot checks:")
    print("  uname -a")
    print(
        "  zgrep -E 'CONFIG_KSU|CONFIG_KPM|CONFIG_KSU_SUSFS|CONFIG_ANDROID_BINDER|CONFIG_ANDROID_BINDERFS' /proc/config.gz "
        "2>/dev/null || grep -E 'CONFIG_KSU|CONFIG_KPM|CONFIG_KSU_SUSFS|CONFIG_ANDROID_BINDER|CONFIG_ANDROID_BINDERFS' /boot/config-$(uname -r)"
    )
    print("  sudo systemctl restart waydroid-container")
    print("  waydroid session start")
    print("  waydroid shell su -c id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
