#!/bin/bash
set -e

if command -v pacman &> /dev/null
then
    echo "Pacman found"
else
    echo "Pacman not found"
    exit 1
fi

sudo chmod +x ./mksteamos
sudo ./mksteamos -v ./
