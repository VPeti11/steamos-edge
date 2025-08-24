#!/bin/bash
chmod +x /home/deck/Desktop/* || true
chmod +x /home/deck/tools/* || true
id -u deck &>/dev/null || useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | passwd deck
echo -e "root\nroot" | passwd root
systemctl enable /etc/systemd/system/pr.service
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/autologin.conf <<EOF
[Autologin]
User=deck
Session=plasma.desktop
EOF
getent group wheel >/dev/null || groupadd wheel
usermod -aG wheel deck
cp /etc/sudoers /etc/sudoers.bak
sed -i -e '/^%wheel ALL=(ALL) ALL/ s/^# *//' -e '/^%wheel ALL=(ALL) NOPASSWD: ALL/ d' /etc/sudoers
cat >> /etc/sudoers <<EOF
%wheel ALL=(ALL) NOPASSWD: ALL
EOF
sed -i 's/^#Server/Server/' /etc/pacman.d/mirrorlist
pacman-key --init
sed -i -E 's/^\s*SigLevel\s*=\s*Required\s+DatabaseOptional\s*/SigLevel = Never/' /etc/pacman.conf
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
systemctl enable auto-sync-time.service

cat > /etc/pacman.conf <<'EOF'
#
# /etc/pacman.conf
#
# See the pacman.conf(5) manpage for option and repository directives

#
# GENERAL OPTIONS
#
[options]
# The following paths are commented out with their default values listed.
# If you wish to use different paths, uncomment and update the paths.
#RootDir     = /
#DBPath      = /var/lib/pacman/
#CacheDir    = /var/cache/pacman/pkg/
#LogFile     = /var/log/pacman.log
#GPGDir      = /etc/pacman.d/gnupg/
#HookDir     = /etc/pacman.d/hooks/
HoldPkg     = pacman glibc
#XferCommand = /usr/bin/curl -L -C - -f -o %o %u
#XferCommand = /usr/bin/wget --passive-ftp -c -O %o %u
#CleanMethod = KeepInstalled
Architecture = auto

# Pacman won't upgrade packages listed in IgnorePkg and members of IgnoreGroup
#IgnorePkg   =
#IgnoreGroup =

#NoUpgrade   =
#NoExtract   =

# Misc options
#UseSyslog
#Color
#TotalDownload
# We cannot check disk space from within a chroot environment
CheckSpace
#VerbosePkgLists
ParallelDownloads = 20
Architecture = i686

# By default, pacman accepts packages signed by keys that its local keyring
# trusts (see pacman-key and its man page), as well as unsigned packages.
SigLevel    = Required DatabaseOptional
LocalFileSigLevel = Optional
#RemoteFileSigLevel = Required

# NOTE: You must run `pacman-key --init` before first using pacman; the local
# keyring can then be populated with the keys of all official Arch Linux
# packagers with `pacman-key --populate archlinux`.

#
# REPOSITORIES
#   - can be defined here or included from another file
#   - pacman will search repositories in the order defined here
#   - local/custom mirrors can be added here or in separate files
#   - repositories listed first will take precedence when packages
#     have identical names, regardless of version number
#   - URLs will have $repo replaced by the name of the current repo
#   - URLs will have $arch replaced by the name of the architecture
#
# Repository entries are of the format:
#       [repo-name]
#       Server = ServerName
#       Include = IncludePath
#
# The header [repo-name] is crucial - it must be present and
# uncommented to enable the repo.
#

# The testing repositories are disabled by default. To enable, uncomment the
# repo name header and Include lines. You can add preferred servers immediately
# after the header, and they will be used before the default mirrors.

#[testing]
#Include = /etc/pacman.d/mirrorlist

[core]
SigLevel = Never
Server = http://de.mirror.archlinux32.org/i686/$repo
Server = http://mirror.datacenter.by/pub/archlinux32/$arch/$repo
Server = http://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = https://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = http://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://32.arlm.tyzoid.com/$arch/$repo
Server = http://mirror.yandex.ru/archlinux32/$arch/$repo
Server = https://mirror.yandex.ru/archlinux32/$arch/$repo
Server = http://gr.mirror.archlinux32.org/$arch/$repo
Server = https://mirror.franscorack.com/arch32/$arch/$repo
Server = http://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://mirror.archlinux32.org/$arch/$repo
Server = http://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.archlinux32.org/$arch/$repo
Server = https://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.juniorjpdj.pl/archlinux32/$arch/$repo
Server = https://mirror.juniorjpdj.pl/archlinux32/$arch/$repo

[extra]
SigLevel = Never
Server = http://de.mirror.archlinux32.org/i686/$repo
Server = http://mirror.datacenter.by/pub/archlinux32/$arch/$repo
Server = http://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = https://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = http://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://32.arlm.tyzoid.com/$arch/$repo
Server = http://mirror.yandex.ru/archlinux32/$arch/$repo
Server = https://mirror.yandex.ru/archlinux32/$arch/$repo
Server = http://gr.mirror.archlinux32.org/$arch/$repo
Server = https://mirror.franscorack.com/arch32/$arch/$repo
Server = http://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://mirror.archlinux32.org/$arch/$repo
Server = http://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.archlinux32.org/$arch/$repo
Server = https://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.juniorjpdj.pl/archlinux32/$arch/$repo
Server = https://mirror.juniorjpdj.pl/archlinux32/$arch/$repo

[community]
SigLevel = Never
Server = http://de.mirror.archlinux32.org/i686/$repo
Server = http://mirror.datacenter.by/pub/archlinux32/$arch/$repo
Server = http://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = https://mirror.clarkson.edu/archlinux32/$arch/$repo
Server = http://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://mirror.math.princeton.edu/pub/archlinux32/$arch/$repo
Server = https://32.arlm.tyzoid.com/$arch/$repo
Server = http://mirror.yandex.ru/archlinux32/$arch/$repo
Server = https://mirror.yandex.ru/archlinux32/$arch/$repo
Server = http://gr.mirror.archlinux32.org/$arch/$repo
Server = https://mirror.franscorack.com/arch32/$arch/$repo
Server = http://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://archlinux32.andreasbaumann.cc/$arch/$repo
Server = https://mirror.archlinux32.org/$arch/$repo
Server = http://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.archlinux32.org/$arch/$repo
Server = https://de.mirror.archlinux32.org/$arch/$repo
Server = http://mirror.juniorjpdj.pl/archlinux32/$arch/$repo
Server = https://mirror.juniorjpdj.pl/archlinux32/$arch/$repo
EOF
chmod +x /usr/bin/*
chmod +x /usr/local/bin/*
systemctl enable NetworkManager

# MAGIC BRACKET
systemctl enable sddm
# MAGIC BRACKET
