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

| Flag         | Description                                               | Notes                                                              |
| ------------ | --------------------------------------------------------- | ------------------------------------------------------------------ |
| `--mode`     | Repository mode: `1`=Downstream, `2`=Upstream, `3`=32-bit | Interactive prompt if omitted                                      |
| `--extra`    | Add extra packages (only in modes 1 and 2)                | Installs extras like PrismLauncher, Lutris, Moonlight, etc.        |
| `--neptune`  | Use Neptune kernel (64-bit only)                          | Adds Neptune kernel + firmware (mode 1) or Valve firmware (mode 2) |
| `--lite`     | Enable Lite mode (LXQt + xorg, autologin)                 | Replaces Plasma with LXQt + Xorg/Xterm   |
| `--build`    | Build the image after setup                               | If omitted, asks interactively                                     |
| `--cowspace` | Set CoW space size (e.g. `2G`) or `skip` to skip          | Defaults to 2G if omitted                                          |
| `--bypass`   | Bypass pacman/root/internet checks                        | Use with caution                                                   |
| `--cleanup`  | Remove build folders and files, then exit                 | Skips normal execution                                             |
| `--help`     | Show help menu                                            | Shows usage and exits     
| `--staging`     | Use staging edge-repo                                            | Use staging edge-repo                                           |

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

### Cleanup existing build folders:

```
./mkedge --cleanup
```

This deletes build folders (`work`, `out`, `grub`, `efiboot`, etc.) and exits.

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

## Execution Flow (Step-by-Step)

This section documents the control flow and key helpers, so contributors can modify or extend behavior safely.

1. **Startup & flag parsing**

   * Parses flags: `--mode`, `--extra`, `--neptune`, `--build`, `--cowspace`, `--bypass`, `--cleanup`, `--lite`, `--help`.
   * If `--help`: prints usage and exits.

2. **Cleanup fast-path**

   * If `--cleanup`:

     * If **not** `--bypass`: requires root (`isSudo()`), else exits with error.
     * Runs `cleanup()` and exits.
     * `cleanup()` removes: `work/`, `out/`, `grub/`, `neptune/`, `efiboot/`, `syslinux/`, and generated files: `packages.x86_64`, `packages.i686`, `helper.sh`, `pacman.conf`, `profiledef.sh`.

3. **Cowspace flag validation**

   * If `--cowspace` is set and not `"skip"`, validates `^\d+G$`; otherwise coerces to `"skip"` and prints a notice.

4. **Environment checks & bypass logic**

   * If `.test` exists → **bypass all checks**.
   * Else if **not** `--bypass`:

     * Rejects Windows hosts (`runtime.GOOS == "windows"`).
     * Requires `pacman` (`isPacmanAvailable()`).
     * Requires root (`isSudo()`).
     * Requires internet (`checkInternet()` → `ping -c 5 1.1.1.1`).
   * On failure, prints reason and exits.

5. **Greeting & screen clear**

   * Prints “MKEDGE made by VPeti” with color (`printFancy`) and `clearScreen()`.

6. **Existing build detection**

   * If `./work` exists:

     * In **non-interactive** mode (`--mode` provided): assumes **continue**.
     * In **interactive** mode: asks `"'./work' folder exists. Continue build? (y/n)"`.
     * If **continue**: runs `runHelper("sudo", "./helper.sh", "-v", ".", "/")`, clears screen, prints completion, and exits.
     * If **no**: runs `cleanup()` and continues fresh.

7. **Repository mode selection**

   * If `--mode` omitted: prompts `[1] Downstream [2] Upstream [3] 32-bit`.
   * Sets `zipName` and copies mode scaffolding:

     * **Downstream (1)**

       * `zipName = boot64.zip`
       * Copy: `mkedge/packages.x86_64.base → packages.x86_64`, `mkedge/64dwn.sh → profiledef.sh`, `mkedge/cust_64.sh → airootfs/root/customize_airootfs.sh`
       * If `--extra`: `appendExtraPackagesdwn()` (curated AUR/binaries).
       * **Neptune on?** Adds: `linux-neptune`, `linux-firmware-neptune`, `steamdeck-dsp`.
       * **Neptune off**: Adds `linux-firmware`.
     * **Upstream (2)**

       * `zipName = boot64.zip`
       * Copy: `mkedge/packages.x86_64.base → packages.x86_64`, `mkedge/64.sh → profiledef.sh`, `mkedge/cust_64.sh → airootfs/root/customize_airootfs.sh`
       * If `--extra`: `appendExtraPackages()` (AUR/binaries).
       * **Neptune on?** Adds `linux-firmware-valve`.
     * **32-bit (3)**

       * `zipName = boot32.zip`
       * Copy: `mkedge/packages.i686.base → packages.i686`, `mkedge/32.sh → profiledef.sh`, `mkedge/cust_32.sh → airootfs/root/customize_airootfs.sh`
   * Always copy `mkedge/helper.sh → ./helper.sh`.

8. **Repository configuration**

   * `configureRepos(mode)` writes `./pacman.conf` from one of:

     * `mkedge/downstream.conf`, `mkedge/upstream.conf`, or `mkedge/32.conf`.

9. **Boot assets extraction**

   * `extractZip("mkedge/"+zipName, ".")`: safe extraction with path traversal guard.
   * Prints `Extracted: <path>` for each item.

10. **CoW space replacement**

    * If `--cowspace` provided: `replaceCowspaceFlag(value)`.
    * Else: `replaceCowspacePrompt()` asks size (default `2G`), then calls `replaceCowspaceFlag`.
    * Replacement logic (`replaceCowspaceFlag`):

      * Scans all files under `.` replacing `cow_spacesize = <...>` with `cow_spacesize=<VALUE>`.
      * **Skips** `airootfs/`, `mkedge/` dirs and `mkedge.go`.

11. **Lite mode handling**

    * If `--lite` or interactive **Yes**:

      * `handleLite(mode)`:

        * Chooses package file (`packages.x86_64` for 64-bit, `packages.i686` for 32-bit).
        * Removes any line starting with `plasma`.
        * Appends: `lxqt`, `xorg`, `xorg-xinit`, `xterm`.
        * Edits `airootfs/root/customize_airootfs.sh`:

          * Removes lines between pairs of `# MAGIC BRACKET` markers (`RemoveMagicBrackets`).
          * Appends:

            * A minimal `/home/deck/.xinitrc` (`exec startlxqt`).
            * `/home/deck/.bash_profile` to auto `startx` when no `$DISPLAY`.
            * **Mode 3 (32-bit)** only: systemd override for `getty@tty1` to autologin user `deck`, and enables the unit.
        * Prints “Lite mode enabled successfully.”

12. **Build decision**

    * If `--build` omitted: prompts “Do you want to build the image? (y/n)”.
    * If **No**: prints message and exits.

13. **Dependency installation (unless bypassed)**

    * Runs `sudo pacman -Sy --noconfirm --needed` for:
      `arch-install-scripts base-devel git squashfs-tools mtools dosfstools xorriso e2fsprogs erofs-utils libarchive libisoburn gnupg grub openssl python-docutils shellcheck`
    * On failure: exits.

14. **Helper execution**

    * `chmod 0755 ./helper.sh`.
    * `runHelper("sudo", "./helper.sh", "-v", ".", "/")`

      * Streams stdio through to the user.
      * Exits on error.

15. **Finish**

    * Clears screen and prints “MKEDGE complete”.

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
