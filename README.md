# SteamOS Edge

**SteamOS Edge** is a modded version of the leaked 2025 SteamOS base, built for broader hardware compatibility and packed with community-driven gaming features. It provides a persistent liveboot experience designed for general x86 hardware, not just the Steam Deck  with added packages, driver tweaks, and customization options.

This project builds on the original SteamOS leak and adds Arch-based tooling, extended package support, and an extensible ISO creation system using ArchISO and the **MKEDGE tool**. While building the image yourself is recommended, ISO files can be found in the Discord.

***In short:***

SteamOS Edge is a fixed and modernized version of the SteamOS 3 source leak. This project is **WORK IN PROGRESS**  expect bugs!
Currently the **32-bit build** is less stable, while **x86\_64 builds are stable**.

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

### 1. Build with MKEDGE

Make the tool executable:

```
chmod +x ./mkedge
```

Then run:

```
./mkedge
```

---

### 2. MKEDGE Options

MKEDGE accepts both **interactive input** and **command-line flags**.

Available flags:

```
--mode        Repository mode: 1=Downstream, 2=Upstream, 3=32-bit
--extra       Add extra packages (modes 1,2 only)
--neptune     Use Neptune kernel (mode 2 only)
--build       Build the image after setup
--cowspace    Set cowspace size (default 2G, use 'skip' to skip)
--lite        Enable Lite mode (LXQt instead of Plasma)
--cleanup     Wipe previous ./work and build artifacts
--bypass      Bypass checks (root, pacman, internet)
--help        Show help menu
```

If no flags are given, MKEDGE runs interactively, prompting you for choices.

---

### 3. Script Workflow

Depending on your selections, MKEDGE will:

1. **Validate environment**

   * Checks root, pacman, internet (unless `--bypass` is set)
   * Installs required packages with pacman (arch-install-scripts, base-devel, git, grub, squashfs-tools, etc.)

2. **Repository setup**

   * Copies the correct repo config (`downstream.conf`, `upstream.conf`, or `32.conf`) into pacman.conf

3. **Mode selection**

   * **Downstream (1)** → Community-maintained repos
   * **Upstream (2)** → Valve repos + Arch base
   * **32-bit (3)** → Experimental i686 build

4. **Package list configuration**

   * Adds base package lists for selected mode
   * Optionally adds **extra packages** (game launchers, tools, drivers, etc.)
   * Optionally switches kernel (mainline vs Neptune)
   * Optionally applies **Lite mode** (removes Plasma, installs LXQt + autologin Xorg setup)

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

Note: Neptune kernel mode is **Steam Deck only**.

---

## Maintainers & Contributors

| Role             | Name                 |
| ---------------- | -------------------- |
| Project Lead     | **GuestSneezeOSDev** |
| Dev / Maintainer | **VPeti11**          |
| Contributor      | **realGamebreaker**  |
| Contributor      | **Quota**            |

---

## Planned / Completed Work

✅ Persistent liveboot support
✅ x86\_64 support (generic hardware)
✅ Steam Deck kernel support (Linux Neptune)
✅ Extra package sets (launchers, controllers, etc.)
✅ Lite mode (LXQt)
✅ Automated build system with Go (MKEDGE)
✅ BIOS + UEFI boot support
✅ i686 experimental builds

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

# An EdgeDev Project

---