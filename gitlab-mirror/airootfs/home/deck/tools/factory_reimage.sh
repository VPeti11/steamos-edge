#!/bin/bash
sudo POWEROFF=1 NOPROMPT=1 FORCEBIOS=1 "${BASH_SOURCE[0]%/*}"/repair_device.sh sanitize
sudo POWEROFF=1 NOPROMPT=1 FORCEBIOS=1 "${BASH_SOURCE[0]%/*}"/repair_device.sh all
