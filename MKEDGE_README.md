# MKEDGE

MKEDGE is a build automation tool designed for **SteamOS Edge** that prepares and builds custom repository images with various modes, package options, and installation profiles.
It is designed as a replacement for the `mkarchiso -v ./` workflow, making **SteamOS Edge flexible and customizable**.

---

## Features

* Supports **3 repository modes**: Downstream, Upstream, and 32-bit.
* Optional **extra package sets** (games, launchers, tools).
* Supports **Neptune kernel selection** (64-bit modes only).
* **Lite mode** option (LXQt instead of Plasma, with autologin/startx setup).
* Customizable **CoW (copy-on-write) space size**.
* **Bypass checks** for pacman/root/internet if needed.
* **Cleanup** existing build folders to start fresh.
* Fully **interactive** if flags are omitted, or fully **scriptable** with flags.
* Automatic installation of all required dependencies (unless bypassed).
* Colorized and user-friendly interactive prompts.

---

## Requirements

* Arch Linux with `pacman`
* Root privileges
* Internet connectivity (unless `--bypass` is used)
* Go 1.20+ (to build MKEDGE itself)

---

## Usage

```
./mkedge [options]
```

### Options

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


---

## Examples

### Fully interactive mode (no flags):

```
./mkedge
```

Prompts you for all options (mode, packages, kernel, cowspace size, build confirmation, lite mode).

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

Custom scripts in airootfs/root/customize_airootfs.sh

---

## Notes

* The `--mode` flag controls most behavior. If not passed, you will be prompted.
* `--extra` pulls in a curated set of gaming/utility packages like PrismLauncher, Lutris, Moonlight, ProtonUp-Qt, etc.
* The `--cowspace` flag expects a number followed by `G` (e.g. `2G`). Use `skip` to avoid changing it.
* If `.test` file exists, all system checks are bypassed automatically.
* The tool installs its **own build dependencies** (e.g., `arch-install-scripts`, `squashfs-tools`, `xorriso`, `erofs-utils`, etc.) unless bypassed.
* **Lite mode** strips Plasma packages and replaces them with LXQt, Xorg, and autologin/startx configuration (on 32-bit it also configures TTY autologin instead of SDDM).
* If the `./work` folder exists, you’ll be asked whether to continue or clean it.

---

## License

This tool is made by **VPeti (Lead Maintainer @ EdgeDev)** and is provided under the **GPL version 3 or later**.

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
