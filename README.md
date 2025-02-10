# SteamOS Edge
- What is this?
SteamOS Edge is a and fixed version of the SteamOS 3 source code leak. Note this project is a **WORK IN PROGRESS** expect bugs!

## How to compile.
On Arch Linux or any Arch Linux-based distro run:
```bash
git clone https://gitlab.com/edgedev1/steamos-edge
cd steamos-edge
chmod +x ./build.sh
sudo ./build.sh
```
On any other distro or Windows run:
```bash
git clone https://gitlab.com/edgedev1/steamos-edge
cd steamos-edge
docker build --tag 'Dockerfile' .
docker run
```

# Planned Stuff
- [X] Portability aka persistent storage.
- [ ] Installable on generic devices.
- [X] Replace build system with makefiles, cmake, waf, or a custom one.
- [X] x86 support 
- [X] Replace Linux kernel with Linux Neptune (FULLY)
- [X] Make it compile.
- [X] Compilable on *BSD, All Linux Distro's and Windows.
- [X] Make it bootable.
- [ ] Pre-install a bunch of gaming packages.
- [ ] Pre-install `linux-firmware-valve` package by `@LukeShortCloud`.
- [ ] Pre-install Drivers .

# Download: 
To install this/download the image, you have to build the images yourself, if you want prebuilt images, we recommend [SteamOS Edge-dev](https://gitlab.com/VPeti11/steamos-edge-dev) (Community Repository).

---

# Variations
#### If you want to check out variations of this project read VERSIONS.md

| Features | SteamOS 3 | SteamOS Edge |
| --- | --- | --- |
| SteamOS repositories | Yes | Yes |
| Arch Linux packages | Old | New |
| Boot compatibility | UEFI | UEFI and legacy BIOS |
| Graphics drivers | AMD | AMD, Intel [Test if NVIDIA drivers work.] |
| Read-only file system | Yes | No |
| Encrypted file system | No | No |
| Number of possible file system backups | 1 | Unlimited |
| Package managers (CLI) | flatpak, nix, pacman | flatpak, nix, pacman  |
| Preferred package manager (CLI) | flatpak | flatpak |
| Package managers (GUI) | Discover (flatpak) | Discover (flatpak) |
| Update type | Image-based | Image-based |
| Number of installed packages | Small | Small |
| Game launchers | Steam | Steam |
| Linux kernels | Neptune (6.5) | Linux, Linux Neptune |
| Desktop environment | KDE Plasma 5 | KDE Plasma 6 |
| Desktop theme | Vapor | Vapor |