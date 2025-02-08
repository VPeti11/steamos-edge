# SteamOS SDK
- What is this?
SteamOS SDK is a stripped and fixed version of the SteamOS 3 source code leak. You can ONLY compile it
while having the Linux Neptune kernel installed[ [AUR] ](https://aur.archlinux.org/packages/linux-neptune-65).
Note this project is a **WORK IN PROGRESS** expect bugs!

## How to compile.
On Arch Linux or any Arch Linux-based distro run:
```bash
git clone https://gitlab.com/jupiter-linux/steamos-sdk
cd steamos-sdk
sudo sh build.sh
```
On any other distro or Windows run:
```bash
git clone https://gitlab.com/jupiter-linux/steamos-sdk
cd steamos-sdk
docker build --tag 'Dockerfile' .
docker run
```

# Planned Stuff
- [X] Portability aka persistent storage.
- [ ] Installable in generic devices.
- [ ] Replace build system with makefiles, cmake, waf, or a custom one.
- [ ] x86 & arm support 
- [X] Replace Linux kernel with Linux Neptune (FULLY)
- [X] Make it compile.
- [X] Compilable on *BSD, All Linux Distro's and Windows.
- [ ] Make it bootable.

# Bleading edge repo
#### If you want to check out the bleading edge version go to:
##### https://github.com/VPeti1/steamos

---
# About the leak
The SteamOS (3.0) Source Code (and other repositories) were leaked by few amount of individuals (GuestSneezePlayZ, YourLocalMoon, etc), The original leak had a bunch of files missing.
You can find more info here: http://www.mediafire.com/file/yh5t8h2lgbu5kdm/steamos_3.tar.gz
