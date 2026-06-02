# linux-zen-sukisu

Linux ZEN kernel (v7.0.9.zen1) with **SukiSU-Ultra** and **SUSFS** fully integrated and adapted.

This is a complete, ready-to-build kernel source tree for x86_64 desktop (and Waydroid/Android container) use cases. SukiSU provides root with advanced hiding features (similar to KernelSU on Android but ported/adapted here), and SUSFS adds powerful mount/path/kstat spoofing for root hiding.

## Base

- Upstream: Linux 7.0.9
- Zen patches: v7.0.9-zen1 (from https://github.com/zen-kernel/zen-kernel)
- SukiSU-Ultra: vendored kernel component from SukiSU-Ultra (https://github.com/SukiSU-Ultra/SukiSU-Ultra)
- SUSFS: ported via filtered patch from gki-android16-6.12-dev branch + adaptations for 7.0 + zen

## What's included (the adaptations)

- `drivers/kernelsu/` — full SukiSU-Ultra kernel module (core, hooks, kpm, policy, selinux, sulog, supercall, etc.)
- `fs/susfs.c` + hooks in fs/exec.c, fs/namei.c, fs/stat.c, fs/open.c, fs/mount.c, kernel/ etc. and input handling
- `drivers/kernelsu/Kconfig` exposed under KernelSU menu (incl. full SUSFS options)
- `drivers/Makefile` and `fs/Makefile` + `drivers/Kconfig` updated to build the module when `CONFIG_KSU=y`
- Default enabled features in reference config:
  - `CONFIG_KSU=y`
  - `CONFIG_KPM=y`
  - `CONFIG_KSU_SUSFS=y` (and most sub-options: SUS_PATH, SUS_MOUNT, SUS_KSTAT, SPOOF_UNAME, etc.)
  - Binder + binderfs (for Waydroid)
  - Other desktop zen tuning

## Building (generic)

```bash
# 1. Configure (use the provided config as base)
cp config.x86_64 .config
make LLVM=1 LLVM_IAS=1 olddefconfig menuconfig   # tweak as needed (ensure KSU options)

# 2. Build
make LLVM=1 LLVM_IAS=1 -j$(nproc) bzImage modules

# 3. Install (as root, adjust for your distro)
#    modules_install + install the bzImage / vmlinuz + headers as appropriate.
#    For Arch example see below.
```

After build you should see `drivers/kernelsu/ksu.ko` (or built-in) and susfs support.

Verify at runtime (after reboot into new kernel):

```bash
zgrep -E 'CONFIG_KSU|CONFIG_KSU_SUSFS' /proc/config.gz
uname -a
# For SukiSU userspace tooling (ksud, manager) see SukiSU-Ultra docs
```

## Arch Linux (makepkg / linux-zen style)

The original `PKGBUILD` from linux-zen works if you point the source to a pre-prepared tree or adjust for git.

Example workflow used in development (see sibling `linux-zen/compile.py` + `PKGBUILD`):

- Place this tree as the `src/linux-7.0.9` (or adjust `_srcname`)
- Use `makepkg -e -f` (skip extract) with LLVM=1 etc.
- Or modify PKGBUILD `prepare()` to apply any extra local patches and copy config.

See the `linux-zen/` dir in this repo's history / sibling for the exact compile/install scripts used (`compile.py`, `install_sukisu_kernel.py`).

Reference config is provided as `config.x86_64`.

## SukiSU userspace / manager

The kernel side is here. For the full SukiSU experience you also need:

- ksud (rust userspace daemon)
- The manager app (APK)
- Possibly ksuinit / su binary

### Included in this repo

**Prebuilt APK (for quick use):**

- `sukisu-manager/SukiSU_v4.1.3_40793-debug.apk`
- See `sukisu-manager/README.md`

**Full source code (as git submodule):**

- `SukiSU-Ultra/` (submodule)
- Manager source is at `SukiSU-Ultra/manager/`
- Pinned to the exact commit used for this kernel adaptation: `57430528fcdd8b05ac299cb1ee113f262228766d`

After cloning the kernel repo, initialize the submodule:

```bash
git submodule update --init --recursive
```

This gives you the full SukiSU-Ultra source (manager + original kernel module reference).

The prebuilt APK matches the kernel features enabled here (KPM + full SUSFS support etc.).

For production builds with custom/randomized signing, use the tools from the submodule (`repack_apk.py`, etc.).

In this setup it was used together with Waydroid (binder) for Android-in-Linux root scenarios.

## SUSFS usage notes

SUSFS options are configurable via the SukiSU app / ksud or kernel cmdline / modules params in some cases. Refer to SukiSU docs for `add_sus_path`, `sus_mount`, spoofing uname, hiding ksu symbols, etc.

## Credits & References

- zen-kernel: https://github.com/zen-kernel/zen-kernel
- SukiSU-Ultra: https://github.com/SukiSU-Ultra/SukiSU-Ultra (and its KernelSU heritage)
- SUSFS patches originally from https://gitlab.com/simonpunk/susfs4ksu (GKI ports adapted here)
- Original linux-zen packaging and config from Arch Linux

## License

GPL-2.0-only (same as Linux kernel). SukiSU and SUSFS components retain their original licenses (see `drivers/kernelsu/LICENSE` and patch headers).

This tree is provided as a convenience "source fork" with the adaptations applied so you don't have to manually integrate on every rebase.

For updates: rebase the zen changes + re-apply / re-integrate the SukiSU + SUSFS deltas (or use the port patches in the development tree).

---

Built and adapted for pescadordegoiaba's kernel builds (desktop + Waydroid + root hiding experiments).
