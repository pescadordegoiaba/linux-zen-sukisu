# SukiSU Manager (APK)

This is the matching manager APK for the SukiSU-Ultra kernel integration in this tree.

**Included build:**  
`SukiSU_v4.1.3_40793-debug.apk` (debug build from this workspace)

This APK corresponds to the kernel features enabled here:
- CONFIG_KSU + KPM
- Full SUSFS support (all the sus_* options)
- Desktop / Waydroid adaptations in the kernel side

## Usage
- Install the APK on the target Android environment (e.g. via Waydroid in this desktop kernel setup).
- It should be able to talk to the kernel module via the usual KernelSU / SukiSU protocol.
- For production/release builds with custom signing (randomized signature to evade detection), use the upstream `repack_apk.py` + your own keys (see SukiSU-Ultra root for `repack-config.example.json` and `manager/sign.example.properties`).

## Source
The full manager source is included in this repository as a git submodule:

- `SukiSU-Ultra/manager/` (after `git submodule update --init --recursive`)
- Pinned to the exact version used when adapting the kernel: commit `57430528fcdd8b05ac299cb1ee113f262228766d`

You can also find it on GitHub at:
https://github.com/SukiSU-Ultra/SukiSU-Ultra/tree/57430528fcdd8b05ac299cb1ee113f262228766d/manager

The APK here was built from the SukiSU-Ultra source at the matching commit.

Version: v4.1.3 (40793)

If you need a release variant or different signing, rebuild from the SukiSU-Ultra source using the same kernel config/features.