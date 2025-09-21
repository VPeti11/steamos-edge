# Contributing to SteamOS Edge

First off thanks for checking out SteamOS Edge and wanting to help. Whether you're fixing a bug, adding features, or improving docs, contributions are welcome.

This project is community-maintained and constantly evolving (technically), so collaboration is key.

---

## Things You Can Contribute

* **Code changes** – improvements to the ISO build system, overlay scripts, kernel configs, etc.
* **New features** – package support, config presets, liveboot enhancements
* **Documentation** – edits to the README, VERSIONS.md, usage guides, etc.
* **Testing** – trying builds on various hardware and reporting results
* **Bug fixes** – squash them, no matter how small (Sorry for the terrible joke)
* **Packaging** – better ways to bundle/optimize included software
* **Suggestions** – ideas and feedback are always appreciated

---


## Development Setup

### Requirements

* Arch Linux (or compatible) host system or Distrobox
* Go (for mkedgescript)
* `mkarchiso` and `base-devel` packages

Install with:

```
sudo pacman -Sy --noconfirm base-devel mkarchiso go
```

---

## How to Contribute

### 1. Fork the Repo

Click the **Fork** button on GitLab and clone your fork:

```
git clone https://gitlab.com/yourusername/steamos-edge
cd steamos-edge
```

### 2. Make Your Changes

* Code changes should be clear and commented
* Try to avoid hardcoding 
* Keep new package additions optional if possible, add them to [edge-repo](gitlab.com/edgedev1/edge-repo)

### 3. Test Your Changes

Build the image locally:

```
chmod +x ./mkedgescript
./mkedgescript
```

Boot the generated ISO on physical hardware or in a VM (e.g., QEMU or VirtualBox) and verify that your change works.

### 4. Submit a Merge Request / Pull Request

Push your changes to your fork, then open an MR/PR to the main repository. Include:

* A clear title
* A short description of what you changed

---

## Style & Guidelines

* Stick to the existing formatting and tone for documentation
* Keep commits atomic and readable (`git commit -m "Add: driver X support"` is great)
* Don't break stuff without a reason

---

## Maintainers

| Name             | Role             |
| ---------------- | ---------------- |
| GuestSneezeOSDev | Project Lead     |
| VPeti11          | Dev / Maintainer |
| realGamebreaker  | Contributor      |
| Quota            | Contributor      |

Feel free to @mention VPeti11 if you need anything

---

## Licensing

By contributing, you agree to license your changes under:

* **GPLv3** – for code contributions
* **GFDL** – for documentation

This keeps SteamOS Edge open and available to everyone.

---

## Questions?

Open an issue or start a discussion in the repo. We’re happy to help clarify how the system works or guide you through your first contribution.

---

# An EdgeDev project
