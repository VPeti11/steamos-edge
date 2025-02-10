#!/bin/bash
# GuestSneezePlayZ: Maybe don't FORCEBIOS because
# this will brick the device trying to install SteamOS.
sudo POWEROFF=1 NOPROMPT=1 FORCEBIOS=1 "${BASH_SOURCE[0]%/*}"/repair_device.sh sanitize
sudo POWEROFF=1 NOPROMPT=1 FORCEBIOS=1 "${BASH_SOURCE[0]%/*}"/repair_device.sh all
