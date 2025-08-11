# MKEDGE

MKEDGE is a build automation tool designed for SteamOS Edge that prepares and builds custom repository images with various modes and package options. Designed to combat `mkarchiso -v ./`. SteamOS Edge is designed to be flexible so that you can choose what you want in it

---

## Features

* Supports 3 repository modes: Downstream, Upstream, and 32-bit.
* Optionally add extra packages.
* Supports Neptune kernel selection (Upstream mode only).
* Customizable CoW space size.
* Bypass system checks if needed.
* Cleanup existing build folders.
* Fully interactive if flags are omitted, or fully scriptable with flags.
* Help menu for quick reference.

---

## Requirements

* Arch Linux with `pacman`
* Running as root
* Internet connectivity

---

## Usage

```
./mkedge [options]
```

### Options

| Flag         | Description                                               | Notes                                     |
| ------------ | --------------------------------------------------------- | ----------------------------------------- |
| `--mode`     | Repository mode: `1`=Downstream, `2`=Upstream, `3`=32-bit | Interactive prompt if omitted             |
| `--extra`    | Add extra packages (only in modes 1 and 2)                | Optional                                  |
| `--neptune`  | Use Neptune kernel (mode 2 only)                          | Optional                                  |
| `--build`    | Build the image after setup                               | If omitted, prompts the user              |
| `--cowspace` | Set CoW space size (e.g. `2G`) or `skip` to skip          | Defaults to interactive prompt if omitted |
| `--bypass`   | Bypass pacman and root user checks                        | Use with caution                          |
| `--cleanup`  | Remove build folders and files, then exit                 | Skips normal execution                    |
| `--help`     | Show this help menu                                       | Shows usage and exits                     |

---

## Examples

### Fully interactive mode (no flags):

```
./mkedge
```

This will prompt you for all necessary options.

---

### Non-interactive, scriptable example:

```
./mkedge --mode 2 --extra --neptune --cowspace 3G --build
```

This will:

* Use Upstream mode
* Add extra packages
* Use Neptune kernel
* Set CoW space size to 3G
* Build image automatically

---

### Cleanup existing build folders:

```
./mkedge --cleanup
```

This deletes build folders (`work`, `out`, etc.) and exits.

---

## Notes

* The `--mode` flag controls most behavior. If not passed in, you will be prompted.
* The `--cowspace` flag expects a number followed by `G`, e.g. `2G`. Use `skip` to avoid changing CoW space size.
* If `.test` file exists, system checks are bypassed automatically.
* The program must be run as root unless `--bypass` is used.
* Internet connection is required unless `--bypass` is used.
* If the `./work` folder exists, you will be asked whether to continue or clean it.

---

## License

This tool is made by VPeti (Lead Maintainer@EdgeDev) and is provided under the GPL version 3 or later

---
