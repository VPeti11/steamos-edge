# SteamOS Edge
- What is this?
SteamOS Edge is a and fixed version of the SteamOS 3 source code leak. Note this project is a **WORK IN PROGRESS** expect bugs!

## How to compile.
On Arch Linux or any Arch Linux-based distro run:
```bash
git clone https://gitlab.com/jupiter-linux/steamos-edge
cd steamos-edge
chmod +x ./build.sh
sudo ./build.sh
```
On any other distro or Windows run:
```bash
git clone https://gitlab.com/jupiter-linux/steamos-edge
cd steamos-edge
docker build --tag 'Dockerfile' .
docker run
```

# Planned Stuff
- [X] Portability aka persistent storage.
- [X] Installable on generic devices.
- [X] Replace build system with makefiles, cmake, waf, or a custom one.
- [X] x86 support 
- [X] Replace Linux kernel with Linux Neptune (FULLY)
- [X] Make it compile.
- [X] Compilable on *BSD, All Linux Distro's and Windows.
- [X] Make it bootable.

# Bleading edge repo
#### If you want to check out the bleading edge version go to:
##### https://github.com/VPeti1/steamos

---
# About the leak
The SteamOS (3.0) Source Code (and other repositories) were leaked by few amount of individuals (GuestSneezePlayZ, YourLocalMoon, etc), The original leak had a bunch of files missing. if you want to know about the devlopment history of the project, check DEV.md.
# Download 
https://github.com/VPeti1/steamos-edge-dev/releases/tag/img1

# Variations
#### If you want to check out variations of this project read VERSIONS.md
