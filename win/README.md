# MKEDGE Windows

## Overview

This script automates the installation of **WSL** (Windows Subsystem for Linux) and **Arch Linux** on WSL.
It runs `mkedgescript` inside the newly installed Arch WSL environment.

## What the Script Does

1. **Checks for WSL installation:**

   * If WSL is already installed, it skips to installing Arch.
   * If not installed, it installs WSL using `wsl --install`.

2. **Checks for required features:**

   * Uses **DISM** to enable WSL-related Windows features if they are missing.
   * Triggers a **system reboot** if features were enabled, since a reboot is required.

3. **Installs Arch Linux:**

   * Runs `wsl --install archlinux` to install Arch as a WSL distribution.

4. **Runs the actual mkedgescript:**

   * Goes one directory up, makes `mkedgescript` executable, and runs it inside the Arch WSL environment.

## Requirements

* Windows 10 (Build 2004 or later) or Windows 11 with WSL support.
* Administrator privileges (script must be run in an elevated PowerShell session).
* Internet connection.

## Usage

1. Go to the win directory
2. Run PowerShell as Administrator.
3. Execute:

   ```
   .\runOnWSL.ps1
   ```
4. If WSL features were missing, your PC will reboot automatically. After reboot, rerun the script.
5. Once Arch Linux is installed, the script will automatically run `mkedgescript` inside WSL.

---
