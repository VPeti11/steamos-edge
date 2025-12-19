# SteamOS Edge

**SteamOS Edge** is a modded version of the leaked 2025 SteamOS base, built for broader hardware compatibility and packed with community-driven gaming features. It provides a persistent liveboot experience designed for general x86 hardware, not just the Steam Deck  with added packages, driver tweaks, and customization options.

This project builds on the original SteamOS leak and adds Arch-based tooling, extended package support, and an extensible ISO creation system using ArchISO and the **MKEDGE tool**. While building the image yourself is recommended, ISO files can be found in the Discord or GitHub.

***In short:***

SteamOS Edge is a fixed and modernized version of the SteamOS 3 source leak. This project is **WORK IN PROGRESS**  expect bugs!
Currently the **32-bit build** is less stable, while **x86\_64 builds are stable**.

## Downloads

Downloads avalible at github releases and at [My site](http://pub.vpeti.online/steamos-edge)

## Builds

[![SteamOS Edge Upstream](https://github.com/VPeti11/steamos-edge/actions/workflows/buildup.yml/badge.svg)](https://github.com/VPeti11/steamos-edge/actions/workflows/buildup.yml)

[![SteamOS Edge Downstream](https://github.com/VPeti11/steamos-edge/actions/workflows/builddwn.yml/badge.svg)](https://github.com/VPeti11/steamos-edge/actions/workflows/builddwn.yml)

[![SteamOS Edge 32](https://github.com/VPeti11/steamos-edge/actions/workflows/build32.yml/badge.svg)](https://github.com/VPeti11/steamos-edge/actions/workflows/build32.yml)

[![SteamOS Edge Lite](https://github.com/VPeti11/steamos-edge/actions/workflows/buildlite.yml/badge.svg)](https://github.com/VPeti11/steamos-edge/actions/workflows/buildlite.yml)

[![Staging edge-repo](https://github.com/VPeti11/edge-repo/actions/workflows/build.yml/badge.svg)](https://github.com/VPeti11/edge-repo/actions/workflows/build.yml)

[![Mirror to GitLab (steamos-edge)](https://github.com/VPeti11/steamos-edge/actions/workflows/push_gitlab.yml/badge.svg)](https://github.com/VPeti11/steamos-edge/actions/workflows/push_gitlab.yml)

---

## Key Features

* Persistent **liveboot ISO** built on Arch Linux tools
* Based on the 2025 **SteamOS leak** (forked and extended)
* Hardware support for generic **x86\_64** devices (not limited to Steam Deck)
* **32-bit build mode** available
* Optional [**Neptune kernel**](https://aur.archlinux.org/packages/linux-firmware-valve)
* Optional extra packages: PrismLauncher, Lutris, Bottles, GZDoom, yay, Sunshine, and more
* Lite mode with **LXQt instead of KDE Plasma**
* Easily extendable with your own packages during ISO creation
* Generated using the custom Go tool: `mkedge`

---

## What’s in This Repository

This repo contains:

* A complete **ArchISO build layout** for creating SteamOS Edge images
* Modified configuration files: pacman.conf, packages lists, overlays, etc.
* **MKEDGE**: a Go-based ISO build and management tool
* Scripts for **install**, **update**, and **deployment**
* Optional kernel and package enhancements to make the system actually work

---

## Installation & ISO Creation

SteamOS Edge must be built on **Arch Linux** or an Arch-based system.
It will not work natively on Debian, Fedora, etc. You can, however, build inside a [Distrobox](https://github.com/89luca89/distrobox) or a privileged Arch Docker container.

## What is MKEDGE?

MKEDGE is a build automation tool designed for **SteamOS Edge** that prepares and builds custom repository images with various modes, package options, and installation profiles.
It is designed as a replacement for the `mkarchiso -v ./` workflow, making **SteamOS Edge flexible and customizable**.

### 1. Build with MKEDGE

Make the tool executable:

```
chmod +x ./mkedgescript
```

Then run:

```
./mkedgescript
```

---

### 2. MKEDGE Options

MKEDGE accepts both **interactive input** and **command-line flags**.

| Flag            | Description                                          |
| --------------- | ---------------------------------------------------- |
| `-mode`         | Repository mode: 1=Downstream, 2=Upstream, 3=32-bit  |
| `-extra`        | Add extra packages (only for modes 1 & 2)            |
| `-neptune`      | Use Neptune kernel (mode 2 only)                     |
| `-build`        | Build the image after setup                          |
| `-cowspace`     | Set cowspace size (default 2G). Use `'skip'` to skip |
| `-bypass`       | Bypass all checks                                    |
| `-cleanup`      | Clean all build artifacts and exit                   |
| `-lite`         | Enable lite mode (LXQt + Xorg)                       |
| `-staging`      | Use staging edge repositories                        |
| `-addextra`     | Add extra packages (repeatable)                      |
| `-nocolor`      | Disable rainbow output                               |
| `-nocleanup`    | Skip cleanup after build                             |
| `-nosighandler` | Disable Ctrl+C handler                               |

If no flags are given, MKEDGE runs interactively, prompting you for choices.

---

### 3. Script Workflow

Depending on your selections, MKEDGE will:

1. **Validate environment**

   * Checks runtime conditions (unless `--bypass` is set)
   * Installs required packages with pacman (arch-install-scripts, base-devel, git, grub, squashfs-tools, etc.)

2. **Repository setup**

   * Copies the correct repo config (`downstream.conf`, `upstream.conf`, or `32.conf`) into pacman.conf

3. **Mode selection**

   * **Downstream (1)** → Valve repos
   * **Upstream (2)** → Arch repos
   * **32-bit (3)** → i686 repos

4. **Package list configuration**

   * Adds base package lists for selected mode
   * Optionally adds **extra packages** (game launchers, tools, drivers, etc.)
   * Optionally switches kernel (mainline vs Neptune)
   * Optionally applies **Lite mode** (removes Plasma, installs LXQt + autologin Xorg setup)
   * Optionally uses staging repos

5. **Boot setup**

   * Extracts required boot files (`boot64.zip` or `boot32.zip`)
   * Adjusts **cowspace size** (default 2G unless changed or skipped)

6. **Final build**

   * Runs `helper.sh` to assemble the persistent liveboot ISO

---

### 4. Output

MKEDGE produces ISO files with the following naming scheme:

```
SteamOS_Edge_Upstream_<date>_x86_64.iso
SteamOS_Edge_Downstream_<date>_x86_64.iso
SteamOS_Edge_i686_<date>.iso
```

---

## Usage

To flash the ISO to a USB stick:

```
sudo dd if=steamos-edge.iso of=/dev/sdX bs=4M status=progress
```

*(replace `/dev/sdX` with your USB device, usually not `/dev/sda`)*

---

## How to install to HDD?

To install:

```
sudo edge-deploy
```

For a mutable Arch-like install:

```
sudo edge-deploy-exp
```

---

## How to update system?

Simply run:

```
sudo steamos_edge_update
```

---

## Changes

| Feature                           | **SteamOS 3**        | **SteamOS Edge**                                     |
| --------------------------------- | -------------------- | ---------------------------------------------------- |
| **SteamOS repositories**          | ✅ Yes                | ✅ Yes                                                |
| **Arch Linux packages**           | 📦 Old               | 📦 New + old                                         |
| **Boot compatibility**            | UEFI only            | UEFI & Legacy BIOS                                   |
| **Graphics drivers**              | AMD                  | AMD, Intel *(NVIDIA drivers installed but untested)* |
| **Read-only file system**         | ✅ Yes                | ❌ No                                                 |
| **Encrypted file system**         | ❌ No                 | ❌ No                                                 |
| **File system backup slots**      | 1                    | Unlimited                                            |
| **CLI Package managers**          | flatpak, nix, pacman | flatpak, pacman                                      |
| **Preferred CLI package manager** | flatpak              | pacman                                               |
| **GUI Package manager**           | Discover (flatpak)   | Discover (flatpak)                                   |
| **Update mechanism**              | Image-based (A/B)    | `steamos_edge_update`                                |
| **Installed package count**       | Small                | Small/Medium                                         |
| **Game launchers**                | Steam only           | Steam, PrismLauncher, Lutris, etc.                   |
| **Linux kernel options**          | Neptune (6.5)        | Mainline, Neptune                                    |
| **Desktop environment**           | KDE Plasma 5         | KDE Plasma 6 *(or LXQt in lite)*                     |
| **Desktop theme**                 | Vapor                | Vapor                                                |

---

## Compatible Hardware

Runs on most x86\_64 hardware:

* Laptops, desktops, and handhelds (tested on AYANEO, Steam Deck, etc.)
* Virtual machines (QEMU, KVM, VMware, VirtualBox)
* If it boots ArchISO, it usually boots this too.

---

## Maintainers & Contributors

| Role             | Name                 |
| ---------------- | -------------------- |
| Project Lead     | **GuestSneezeOSDev** |
| Dev / Maintainer | **VPeti11**          |
| Contributor      | **realGamebreaker**  |
| Contributor      | **Quota**            |

---

## Contributing

Want to help?

* [Join the Discord](https://discord.gg/ChDGTpvzZv)
* Read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines

---

## Licensing

SteamOS Edge is licensed under:

* [GPLv3](LICENSE.md)  for source code
* [GFDL](fdl.md)  for docs and README files

---

## Disclaimer

* Use at your own risk  no guarantees on stability or data safety
* Not affiliated with Valve or the official SteamOS project

---

# How does MKEDGE work?

---

### Checks and Validation

Internet connection

Running as root

Disk space >= 10 GB

Non-NTFS/FAT32 root filesystem

Pacman availability

Single instance check

SHA512 checksum verification of critical files and running executable


### Key helpers & utilities

* `printFancy`, `printFancyInline`, `randColor`, `enableColor`, `colors`
  Colored output and inline prompts.
* `isSudo()`, `isPacmanAvailable()`, `checkInternet()`
  Environment and prerequisite checks (root, pacman, ping).
* `configureRepos(mode)`
  Copies the appropriate `pacman.conf` template.
* `appendExtraPackages() / appendExtraPackagesdwn()`
  Appends extras to `packages.x86_64`.
* `extractZip(zipPath, destDir)`
  Safe ZIP extraction with traversal guard.
* `replaceCowspaceFlag(value)` / `replaceCowspacePrompt()`
  Rewrites `cow_spacesize` occurrences.
* `handleLite(mode)` / `RemoveMagicBrackets(file)`
  Swaps desktop stack to LXQt and injects autostart/autologin config.
* `cleanup()`
  Removes generated files and build artifacts.
* `runHelper(args...)`
  Thin wrapper over `exec.Command` for `helper.sh`.

### Generated/consumed files

* **Inputs/templates (under `mkedge/`)**:
  `*.conf` (repo configs), `*.sh` (profile/customize scripts), `packages.*.base`, `boot64.zip`, `boot32.zip`, `helper.sh`
* **Generated in project root**:
  `packages.x86_64` or `packages.i686`, `profiledef.sh`, `pacman.conf`, `helper.sh`
* **Build artifacts**:
  `work/`, `out/`, plus bootloader dirs (`grub/`, `efiboot/`, `syslinux/`) depending on profile

---

### Cleanup

The -cleanup flag or Ctrl+C will remove:

work/

grub/

neptune/

efiboot/

syslinux/

Package files (packages.x86_64, packages.i686)

helper.sh

pacman.conf

profiledef.sh

airootfs/root/customize_airootfs.sh

---

### Non-interactive, scriptable example:

```
./mkedge --mode 2 --extra --neptune --cowspace 3G --lite --build
```

This will:

* Use **Upstream mode**
* Add **extra packages**
* Use the **Neptune kernel**
* Set **CoW space size to 3G**
* Enable **Lite mode (LXQt)**
* Build the image automatically

---

# Developer Workflow – MKEDGE
This document explains the **end-to-end workflow** of the `mkedge` script at a level developers can extend or debug.
Unlike a user guide, this focuses on **internal execution order**, **function responsibilities**, and **failure modes**.

---

## 1. Startup & Flag Parsing

**Triggered first** when the script launches.

* **Responsible code:** `main()` → flag parsing logic.
* **Inputs:** Command-line arguments.
* **Key flags:**

  * `--mode <int>` → Selects architecture/build profile.
  * `--extra` → Enable gaming/utility extras.
  * `--staging` → Use staging repositories.
  * `--lite` → Replace Plasma with LXQt.
  * `--cowspace` → Enable special overlayfs cowspace handling.
  * `--cleanup` → Force cleanup before building.
  * `--bypass` → Skip environment checks.
  * `--help` → Print usage and exit.

**Outputs:**

* Internal state variables: `modeFlag`, `stagingFlag`, `extraEnable`, `liteFlag`, etc.

**Failure conditions:**

* Invalid/unrecognized flag → exits immediately.

---

## 2. Initial Environment Validation (`doChecks`)

Executed unless `--bypass` is provided.

* **Responsible functions:**

  * `doChecks()`
  * `validateChecksums()`
  * `checkMkedgeScript()`

* **Inputs:** None directly; depends on system state and contents of `mkedge/`.

* **Steps performed in order:**

  1. **Cleanup:** Clear temporary or stale build state.
  2. **Connectivity check:** Ensures internet access (`checkInternet()`).
  3. **OS check:** Rejects Windows (enforces Linux).
  4. **Process lock:** Prevents multiple mkedge instances (`isAnotherInstanceRunning()`).
  5. **Disk space check:** Requires ≥10GB free.
  6. **Filesystem type check:** Root FS must be ext4/btrfs.
  7. **Pacman check:** Must be on Arch Linux.
  8. **Root check:** Must be run as root (`isSudo()`).
  9. **Static file validation:** Every known file in `mkedge/` (scripts, configs, zips) is hashed with SHA512 and compared against **hardcoded expected values** (`validateChecksums()`).
  10. **Executable self-validation:** Running binary is hashed and compared with stored checksum (`script.sha512`).

* **Side effects:**

  * If all checks pass, attempts to **install required system dependencies** silently using `pacman`.

* **Failure conditions (fatal exit):**

  * No internet.
  * Running on Windows.
  * Another instance active.
  * Insufficient disk space.
  * Unsupported filesystem.
  * `pacman` not found.
  * Not root.
  * Any checksum mismatch.
  * Dependency installation fails.

---

## 3. Repository Configuration (`handleStaging`)

Executed after checks, based on `--mode` and `--staging`.

* **Responsible function:** `handleStaging(stagingFlag, modeFlag, extraEnable, amode)`

* **Inputs:**

  * `stagingFlag` (bool, from `--staging` or interactive prompt).
  * `modeFlag` (int, defines build type).
  * `extraEnable` (bool, from `--extra`).
  * `amode` (arch mode: downstream, upstream, etc.).

* **Steps performed:**

  1. **Prompt user (if unset):** Asks “Do you want to use staging repos?” if no flag was given.
  2. **Append repository entries:**

     * If **normal mode** → Add `[edge-repo]` with **master branch** URLs (GitHub + GitLab).
     * If **staging mode** → Add `[edge-repo]` with **staging branch** URL (GitHub only).
     * Writes both to:

       * `pacman.conf` (host build environment).
       * `./airootfs/root/customize_airootfs.sh` (live ISO environment).
  3. **If extras enabled** → Call `appendExtraPackages(mode)`.

* **Outputs:**

  * Modified repo configuration files.
  * Updated package inclusion lists.

* **Failure conditions:**

  * None fatal; only invalid mode string prints warning.

---

## 4. Extra Package Injection (`appendExtraPackages`)

Adds optional apps/utilities for gaming and desktop use.

* **Inputs:**

  * Mode string (`normal`, `stage`, `dwn`, `dwnstage`).

* **Steps performed:**

  * Defines a **base set** of packages:

    * `prismlauncher`, `lutris-git`, `bottles`, `antimicrox-git`, `polychromatic-git`, `gzdoom`.
  * Defines a **mode-specific set**, with logic for renaming/swapping:

    * `sunshine` → normal = stable package, staging = `sunshine-beta-bin`.
    * `peazip-qt` → staging = `peazip`.
    * `ventoy` → staging only.
    * `balena-etcher` → normal only.
  * Writes combined list into `packages.x86_64`.

* **Outputs:**

  * Extended package file for ISO build.

---

## 5. Lite Mode (`handleLite`)

Executed if `--lite` is enabled.

* **Inputs:** `mode` (int, defines arch).

* **Steps performed:**

  1. Selects correct package list (`packages.x86_64` or `packages.i686`).
  2. Removes Plasma packages.
  3. Adds lightweight alternatives: `lxqt`, `xorg`, `xinit`, `xterm`.
  4. Edits `customize_airootfs.sh`:

     * Creates `.xinitrc` to start LXQt.
     * Creates `.bash_profile` to autostart X.
     * If 32-bit: also sets **tty1 auto-login into LXQt**.
  5. Removes any lines inside `# MAGIC BRACKET` sections before appending.

* **Outputs:**

  * New package set with LXQt.
  * Customized autologin/session start scripts in ISO.

---

## 6. Boot File Extraction & Prep

* **Triggered later** in main build flow.
* Extracts `boot32.zip` or `boot64.zip` depending on mode.
* Prepares kernel/initrd hooks.
* Applies **cowspace settings** if requested via `--cowspace`.

---

## 7. Mode-Specific Helper Execution

* Runs architecture/mode-specific shell scripts inside `mkedge/`:

  * `32.sh`, `64.sh` → Base config.
  * `cust_32.sh`, `cust_64.sh` → Custom tweaks.
  * `downstream.conf` / `upstream.conf` → Repo adjustments.
  * `helper.sh` → Shared helper routines.

---

## 8. ISO Build

* Calls Arch’s `mkarchiso` tool with the prepared config tree.
* Builds full live ISO image into output directory.
* Logs are mostly suppressed unless errors occur.

---

## 9. Cleanup (Optional)

* If `--cleanup` flag set:

  * Deletes previous `work/`, `out/`, and cached package directories.
  * Leaves environment clean for fresh rebuild.

---

## End-to-End Workflow Summary

1. **Parse flags** → Internal mode/config setup.
2. **Run checks** → Validate environment, files, privileges, dependencies.
3. **Configure repos** → Append staging/master URLs.
4. **Inject extras** → Add gaming/utility packages.
5. **Enable Lite mode** → Switch Plasma → LXQt if flagged.
6. **Extract boot files** → Copy boot zips into build tree.
7. **Run helpers** → Execute arch/mode scripts.
8. **Build ISO** → Generate via mkarchiso.
9. **Cleanup** → Remove leftovers if requested.

---

# An EdgeDev Project

---
:)