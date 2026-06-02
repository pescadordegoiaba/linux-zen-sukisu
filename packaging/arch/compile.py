#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_REPO = Path("/home/gullin/kernel-builds/linux-zen")
DEFAULT_BUILDDIR = Path("/home/gullin/kernel-builds/builddir")


def die(msg: str, code: int = 1) -> None:
    print(f"[ERRO] {msg}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None,
        check: bool = True, log_file: Path | None = None) -> subprocess.CompletedProcess:
    line = " ".join(cmd)
    print(f"\n[CMD] {line}")
    if cwd:
        print(f"[CWD] {cwd}")

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8", errors="replace") as f:
            f.write(f"\n\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            f.write(f"$ {line}\n")
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
            )
            assert proc.stdout is not None
            for out in proc.stdout:
                print(out, end="")
                f.write(out)
            rc = proc.wait()
            if check and rc != 0:
                raise subprocess.CalledProcessError(rc, cmd)
            return subprocess.CompletedProcess(cmd, rc)

    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)


def find_kdir(builddir: Path) -> Path:
    candidates: list[Path] = []
    src = builddir / "linux-zen" / "src"
    if src.is_dir():
        candidates.extend(sorted(src.glob("linux-*")))

    for c in reversed(candidates):
        if (c / "Makefile").is_file() and (c / ".config").is_file():
            return c.resolve()

    candidates.extend(sorted(builddir.glob("**/src/linux-*")))

    for c in reversed(candidates):
        if (c / "Makefile").is_file() and (c / ".config").is_file():
            return c.resolve()

    die(f"não achei source viva do kernel dentro de {builddir}")
    raise AssertionError


def find_repo_config(repo: Path) -> Path:
    for name in ("config.x86_64", "config"):
        p = repo / name
        if p.is_file():
            return p
    configs = sorted(p for p in repo.glob("config.*") if ".bak" not in p.name)
    if configs:
        return configs[0]
    die(f"não achei config.x86_64/config em {repo}")
    raise AssertionError


def kernel_version(kdir: Path) -> str:
    proc = subprocess.run(
        ["make", "-sC", str(kdir), "kernelversion"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "unknown"


def scan_rejects(kdir: Path) -> list[Path]:
    return sorted(list(kdir.rglob("*.rej")) + list(kdir.rglob("*.orig")))


def show_configs(kdir: Path) -> None:
    wanted = (
        "CONFIG_KSU", "CONFIG_KPM", "CONFIG_KSU_SUSFS",
        "CONFIG_ANDROID_BINDER", "CONFIG_ANDROID_BINDERFS",
        "CONFIG_ANDROID_BINDER_DEVICES", "CONFIG_PSI",
        "CONFIG_DEBUG_INFO_BTF", "CONFIG_WERROR",
    )
    print("\n[CONFIGS IMPORTANTES]")
    text = (kdir / ".config").read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if any(line.startswith(x) or line.startswith(f"# {x}") for x in wanted):
            print(line)


def preflight(repo: Path, builddir: Path, kdir: Path, allow_rejects: bool) -> None:
    if os.geteuid() == 0:
        die("não rode como root; o script usa sudo apenas na instalação.")

    if not (repo / "PKGBUILD").is_file():
        die(f"PKGBUILD não encontrado em {repo}")

    print("[PRE-FLIGHT]")
    print(f"Repo:      {repo}")
    print(f"Builddir:  {builddir}")
    print(f"KDIR:      {kdir}")
    print(f"Kernelver: {kernel_version(kdir)}")

    rejects = scan_rejects(kdir)
    if rejects:
        print("\n[.rej/.orig encontrados]")
        for p in rejects[:100]:
            print(" -", p.relative_to(kdir))
        if not allow_rejects:
            die("existem .rej/.orig. Resolva/remova antes, ou use --allow-rejects se tiver certeza.")
        print("[AVISO] continuando com --allow-rejects.")

    show_configs(kdir)


def backup_config(repo: Path, kdir: Path, repo_config: Path) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = repo / "compile-backups" / stamp
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kdir / ".config", out / ".config")
    shutil.copy2(repo_config, out / repo_config.name)
    print(f"[OK] backup configs: {out}")


def sync_config(repo: Path, kdir: Path, repo_config: Path, log_file: Path) -> None:
    shutil.copy2(kdir / ".config", repo_config)
    print(f"[OK] copiado .config -> {repo_config}")

    if shutil.which("updpkgsums"):
        run(["updpkgsums"], cwd=repo, check=False, log_file=log_file)
    else:
        print("[AVISO] updpkgsums não encontrado; instale pacman-contrib se makepkg reclamar de checksum.")


def clean_objects(kdir: Path, log_file: Path, deep: bool) -> None:
    for d in ("drivers/kernelsu", "fs", "mm", "kernel", "security"):
        if (kdir / d).exists():
            run(["make", "LLVM=1", "LLVM_IAS=1", f"M={d}", "clean"], cwd=kdir, check=False, log_file=log_file)

    for rel in ("vmlinux", "System.map", ".vmlinux.cmd"):
        p = kdir / rel
        if p.exists():
            p.unlink()
            print(f"[OK] removido {rel}")

    if deep:
        patterns = ("*.o", "*.ko", "*.mod", "*.mod.c", "*.cmd", ".*.cmd", "*.lto.o")
        for root in ("drivers/kernelsu", "fs", "mm", "kernel", "security"):
            base = kdir / root
            if not base.exists():
                continue
            for pat in patterns:
                for p in base.rglob(pat):
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass


def build(repo: Path, builddir: Path, jobs: int, log_file: Path) -> None:
    env = os.environ.copy()
    env["BUILDDIR"] = str(builddir)
    env["MAKEFLAGS"] = f"-j{jobs}"
    env["LLVM"] = "1"
    env["LLVM_IAS"] = "1"

    run(["makepkg", "-e", "-f", "-s", "--needed"], cwd=repo, env=env, log_file=log_file)
    print("[OK] build finalizado")


def install(repo: Path, log_file: Path) -> None:
    pkgs = sorted(repo.glob("linux-zen*.pkg.tar.zst"))
    if not pkgs:
        die("nenhum linux-zen*.pkg.tar.zst encontrado para instalar")

    print("\n[PACOTES]")
    for p in pkgs:
        print(" -", p.name)

    run(["sudo", "pacman", "-U", *[str(p) for p in pkgs]], cwd=repo, log_file=log_file)
    run(["sudo", "mkinitcpio", "-P"], cwd=repo, log_file=log_file)
    run(["sudo", "grub-mkconfig", "-o", "/boot/grub/grub.cfg"], cwd=repo, log_file=log_file)
    print("[OK] instalado + initramfs/grub atualizados")


def main() -> None:
    ap = argparse.ArgumentParser(description="Compila o linux-zen custom.")
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--builddir", default=str(DEFAULT_BUILDDIR))
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("JOBS", "6")))
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--allow-rejects", action="store_true")
    ap.add_argument("--no-clean", action="store_true")
    ap.add_argument("--deep-clean-objects", action="store_true")
    ap.add_argument("--skip-sync-config", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    builddir = Path(args.builddir).expanduser().resolve()
    kdir = find_kdir(builddir)
    cfg = find_repo_config(repo)

    log_file = repo / "compile-logs" / f"compile-{time.strftime('%Y%m%d-%H%M%S')}.log"
    print(f"[LOG] {log_file}")

    preflight(repo, builddir, kdir, args.allow_rejects)
    backup_config(repo, kdir, cfg)

    if not args.skip_sync_config:
        sync_config(repo, kdir, cfg, log_file)

    if not args.no_clean:
        clean_objects(kdir, log_file, args.deep_clean_objects)

    build(repo, builddir, args.jobs, log_file)

    if args.install:
        install(repo, log_file)
    else:
        print("\n[OK] build pronto, não instalado.")
        print("Para instalar:")
        print("  sudo pacman -U ./*.pkg.tar.zst")
        print("  sudo mkinitcpio -P")
        print("  sudo grub-mkconfig -o /boot/grub/grub.cfg")

    print("\n[TESTE DEPOIS DO BOOT]")
    print("  uname -a")
    print("  zgrep -E 'CONFIG_KSU|CONFIG_KPM|CONFIG_KSU_SUSFS|CONFIG_ANDROID_BINDER|CONFIG_ANDROID_BINDERFS' /proc/config.gz 2>/dev/null || grep -E 'CONFIG_KSU|CONFIG_KPM|CONFIG_KSU_SUSFS|CONFIG_ANDROID_BINDER|CONFIG_ANDROID_BINDERFS' /boot/config-$(uname -r)")
    print("  sudo systemctl restart waydroid-container")
    print("  waydroid session start")
    print("  waydroid shell su -c id")


if __name__ == "__main__":
    main()
