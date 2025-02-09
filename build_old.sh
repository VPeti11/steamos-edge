#!/bin/zsh
#
# Copyright Mohamed, Febuary 7th 2025, Some rights reserved.
#
# SPDX-License-Identifier: GPL-3.0-or-later
export maker=mksteamos
if `$1` == `mksteamos`; then
    export maker=mksteamos
else
    export maker=mkarchiso
fi

if `$2` == `--x86`; then
    echo "Building for x86"
    rm -rf profiledef.sh
    mv profiledef_x86.sh.template profiledef.sh
else
     echo "Building for x86_64"
fi

$maker -v -w build/ -o build/ .
