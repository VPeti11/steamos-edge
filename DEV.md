# SteamOS: Edge
`export` 100% Open-Source SteamOS.

# Preface.
Back in `2/7/2025`, the SteamOS Linux distribution had a Source code leak (leaked by GuestSneezePlayZ and other Klapan Hack Members.), since then I've been developing a project named SteamOS: Edge.

# `The Leaked Code`
*taken from readme.md*
The SteamOS (3.0) Source Code (and other repositories) were leaked by few amount of individuals (GuestSneezePlayZ, YourLocalMoon, etc), The original leak had a bunch of files missing.

# Opening the leak
What is exactly in the leak? Let's see!
```
airootfs
efiboot
neptune
syslinux
bootstrap_packages.x86_64
packages.x86_64
lastsync
lastupdate
mksteamos
pacman.conf
profiledef.sh
README.txt
```
Wait a readme.txt? what does this say?
```
steamos_3.tar.gz is the entirety SteamOS (3) and some other shit.
These were willingly held onto by a select few of people, and kept in a very small team of schizoids. It was some kind of medium for them to jerk off about having secret shit.
A few schizoids managed to grab both these codebases during his work on some 60th attempt of a SteamOS-like Operating system (Basically a wanna-be Adam Jafarov) and his major goal was to have this circle, leak it to the public and commit suicide. Absolutely fucking insane.
A lot of interesting knowledge can be gained from the SteamOS codebase and a lot of resourceful information can come of it. Go wild!
(By-the-way most of these files have been slightly edited so dont expect to it to compile because we've fucked up alot of shit.)
```
Okay.

# Building SteamOS: mksteamos
So the mksteamos script was a bit rigged.
First off "mksteamos" was somehow broken. I know, I was the original leaker but I had to enshitten(TM) the leak because why not.
The first thing I did to fix this was to replace the code with the default mkarchiso. So I did that but you can see the SteamOS recovery image is a `.img` format so maybe `mksteamos` was a little to enshitted(TM). So after a while I made it output a .img format.

# Building SteamOS: Portability & Restoring the kernel.
So the original source code that I had (unedited) had portability support, so
I added the portability code from the unedited SteamOS, after that I restored more code (like the linux-neptune) kernel. But it caused alot of booting problems so I added support for both linux and neptune.

# Building SteamOS: The x86 processor
So I wanted my SteamOS fork to be superior than the other forks that will come out of this sooner or later, so I tried implementing x86 support. You can enable it by using the `--x86` flag.