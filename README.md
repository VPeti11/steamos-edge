# SteamOS Edge

**SteamOS Edge** is a modded version of the leaked 2025 SteamOS base, built for broader hardware compatibility and packed with community-driven gaming features. It provides a persistent liveboot experience designed for general x86 hardware, not just the Steam Deck with added packages, driver tweaks, and customization options.

This project builds on the original SteamOS leak and adds Arch-based tooling, extended package support, and an extensible ISO creation system using ArchISO and `mkedgescript`

***In short:***

SteamOS Edge is a and fixed version of the SteamOS 3 source code leak. This project is **WORK IN PROGRESS** expect bugs!

---

## Key Features

* Persistent **liveboot ISO** built on Arch Linux tools
* Based on the 2025 **SteamOS leak** (forked and extended)
* Hardware support for generic x86\_64 devices (not limited to Steam Deck)
* Optional [**Neptune kernel**](https://aur.archlinux.org/packages/linux-firmware-valve)
* Optional extra packages: PrismLauncher, Lutris, Bottles, GZDoom, yay, and more
* Easily extendable with your own packages during ISO creation
* Generated using a custom Go script: `./mkedgescript`

---

## What’s in This Repository

This repo contains:

* A complete **ArchISO build layout** for creating SteamOS Edge images
* Configuration files: modified pacman.conf, packages list, overlays and a lot more
* A **Go-based ISO generation script** (`mkedgescript`) that automates build config and execution
* Optional kernel and package enhancements (To make it actually work)

---

## Installation & ISO Creation

SteamOS Edge is designed to be built on Arch Linux or Arch-based systems. It will not work out-of-the-box on Debian, Fedora, etc. But you can use [Distrobox](https://github.com/89luca89/distrobox)

### 1. Run the ISO Build Script

Make the script executable if it isn't already:

```
chmod +x ./mkedgescript
```

Then launch the script:

```
./mkedgescript
```

### 2. Script Workflow

The script will guide you through a few choices:

* **Upstream or Downstream repos** – choose Valve’s original or the Arch ones
* **Extra packages** – add optional gaming tools like Lutris, PrismLauncher, etc.
* **Kernel options** – optionally include Neptune (Valve’s Steam Deck kernel)
* **CoWspace size** - adjust the copy-on-write tmpfs size
* **Build confirmation** – proceed to image creation or exit

Once confirmed, the script:

* Installs required build tools using pacman
* Sets up the ArchISO directory structure
* Copies and modifies config files
* Runs `helper.sh` to create a working persistent liveboot ISO

At the end, the script outputs:
`steamos-edge.iso`

---

## Usage

Once built, write the ISO to a USB drive using `dd`, `balenaEtcher`, `Rufus`, or any ISO tool of your choice. You can use dd like this:

```
sudo dd if=steamos-edge.iso of=/dev/sdX bs=4M status=progress
```

Note: replace `/dev/sdX` with your USB device path. And in most cases that isnt /dev/sda

---

## Changes

| Feature                           | **SteamOS 3**              | **SteamOS Edge**                  |
| --------------------------------- | -------------------------- | --------------------------------- |
| **SteamOS repositories**          | ✅ Yes                      | ✅ Yes                             |
| **Arch Linux packages**           | 📦 Old                     | 📦 New  and old                           |
| **Boot compatibility**            | UEFI only                  | UEFI & Legacy BIOS                |
| **Graphics drivers**              | AMD                        | AMD, Intel<br>*(NVIDIA untested but driver is installed)* |
| **Read-only file system**         | ✅ Yes                      | ❌ No                              |
| **Encrypted file system**         | ❌ No                       | ❌ No                              |
| **File system backup slots**      | 1                          | Unlimited                         |
| **CLI Package managers**          | `flatpak`, `nix`, `pacman` | `flatpak`, `pacman`        |
| **Preferred CLI package manager** | `flatpak`                  | `flatpak`                         |
| **GUI Package manager**           | Discover (flatpak)         | Discover (flatpak)                |
| **Update mechanism**              | Image-based (A/B)          | `steamos_edge_update` (custom)    |
| **Installed package count**       | Small                      | Small/Medium                             |
| **Game launchers**                | Steam,PrismLauncher, Lutris and more                     | Steam                             |
| **Linux kernel options**          | Neptune (6.5)              | Mainline Linux, Linux Neptune     |
| **Desktop environment**           | KDE Plasma 5               | KDE Plasma 6                      |
| **Desktop theme**                 | Vapor                      | Vapor                             |


---

## Compatible Hardware

SteamOS Edge runs on most x86\_64 PCs, including:

* Laptops and desktops
* Handhelds like the AYANEO
* Virtual machines (e.g. QEMU, VMware, VirtualBox) (Tested on KVM)
* Steam Deck (native-ish) (Also tested, not sure why you want to run it there)

If it boots an Arch ISO, it can likely boot this. Or not. Depends. And with the Neptune kernel enabled it likely only boots on the Steam Deck

---

## Advanced: Add Your Own Packages

To extend the image, you can edit:

```
mkedge/upstream.conf / mkedge/downstream.conf
```

You can also add overlay files, kernel modules, or configs in:

```
strootfs/syslinux
```

If you’re familiar with ArchISO, you’ll feel right at home. Mostly

---

## Maintainers & Contributors

SteamOS Edge is maintained by a small but growing group of community developers:

| Role             | Name                 |
| ---------------- | -------------------- |
| Project Lead     | **GuestSneezeOSDev** |
| Dev / Maintainer | **VPeti11**          |
| Contributor      | **realGamebreaker**  |
| Contributor      | **Quota**            |



---

## Licensing

SteamOS Edge is open-source and licensed under:

* [**GPLv3**](LICENSE.md) – for source code

* [ **GFDL**](fdl.md) – for this documentation and included README files

You’re free to use, modify, and redistribute under the terms of these licenses.
Full license texts can be found in the repository.

If you want to read the SteamOS license click [here](STEAMOS_LICENSE.txt)

---

## Disclaimer

* This is an **unstable build** and may contain bugs or unfinished features
* Use at your own risk — no guarantees are made regarding stability or data safety
* This is not affiliated with Valve or the official SteamOS project. Not even the maintainers of [evlaV](https://gitlab.com/evlaV)

----

## Planned Stuff
A list of planned and completed goals for SteamOS Edge. Most of these are already implemented, but the roadmap is kept for clarity, accountability, and your reading enjoyment.


| Status | Feature                                                                                                                                                                                                                                                               |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ✅      | **Portability** via persistent storage support                                                                                                                                                                                                                        |
| ✅      | **Generic device installability** |
| ✅      | Replace the build system with Makefiles, CMake, Waf, or a custom Go-based setup                                                                                                                                                                                       |
| ✅      | Full **x86\_64 hardware support**                                                                                                                                                                                                                                     |
| ✅      | Replace kernel with **Linux Neptune** (Valve)                                                                                                                                                                                                                         |
| ✅      | Make the project **compile and build consistently**                                                                                                                                                                                                                   |
| ✅      | Cross-platform **compilation support**:<br>    - Works on \*BSD, Linux distros, and Windows                                                                                                                                                                           |
| ✅      | Make the ISO fully bootable on **non-Neptune** hardware                                                                                                                                                                                                               |
| ✅      | Pre-install a wide set of **gaming packages**: PrismLauncher, Lutris, Bottles, etc.                                                                                                                                                                                   |
| ✅      | Include `linux-firmware-valve` by [@LukeShortCloud](https://aur.archlinux.org/packages/linux-firmware-valve)                                                                                                                                                          |
| ✅      | **Pre-installed drivers** for broader compatibility                                                                                                                                                                                                                   |


---

## Want to contribute?

First if you want you can [Join the Discord](https://discord.gg/ChDGTpvzZv)

Also check out [this](CONTRIBUTING.md) if you want to contribute

---

# An EdgeDev project

