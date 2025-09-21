#!/bin/bash

lsblk -lnpo NAME,TYPE | while read -r dev type; do
    if [[ "$type" == "part" ]]; then
        mountpoint=$(lsblk -no MOUNTPOINT "$dev")
        if [[ -z "$mountpoint" ]]; then
            label=$(lsblk -no LABEL "$dev")
            mount_dir="/mnt/${label:-$(basename "$dev")}"
            mkdir -p "$mount_dir"

            if blkid "$dev" | grep -q "ntfs"; then
                mount -t ntfs-3g -o permissions,umask=000 "$dev" "$mount_dir"
            else
                mount -o umask=000 "$dev" "$mount_dir"
            fi
        fi
    fi
done

