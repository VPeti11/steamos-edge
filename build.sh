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

$maker -v -w ../work/ -o ../out/ .
