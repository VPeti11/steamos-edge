#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -e

if command -v pacman &> /dev/null
then
    echo "Pacman found"
else
    echo "Pacman not found"
    exit 1
fi

sudo chmod +x ./mksteamos
sudo ./mksteamos -v -w build/ -o build/ .

# Legacy Stuff...
#export maker=mksteamos
#if `$1` == `mksteamos`; then
#    export maker=mksteamos
#else
#    export maker=mkarchiso
#fi
#
#if `$2` == `--x86`; then
#    echo "Building for x86"
#    rm -rf profiledef.sh
#    mv profiledef_x86.sh.template profiledef.sh
#else
#     echo "Building for x86_64"
#fi
#
#$maker -v -w build/ -o build/ .
