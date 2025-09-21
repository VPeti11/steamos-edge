#!/usr/bin/python
# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import importlib.machinery
import logging
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable
from typing import BinaryIO

import steamos_log_submitter as sls
import steamos_log_submitter.helpers
from steamos_log_submitter.logging import reconfigure_logging
from steamos_log_submitter.hooks import trigger

__loader__: importlib.machinery.SourceFileLoader
logger = logging.getLogger(__loader__.name)


def tee(infd: BinaryIO, outprocs: Iterable[subprocess.Popen]) -> None:
    while True:
        buffer = infd.read(4096)
        if not buffer:
            break
        for proc in outprocs:
            if not proc.stdin:
                continue
            try:
                proc.stdin.write(buffer)
            except Exception:
                pass

    for proc in outprocs:
        if proc.stdin:
            try:
                proc.stdin.close()
            except Exception:
                pass
        try:
            proc.wait(5)
        except Exception:
            pass


def should_collect(path: str) -> bool:
    if path.startswith('/tmp/.mount_'):
        # AppImage
        return False
    if path.startswith('/app'):
        # Flatpak
        return False
    if '/.local/share/Steam/' in path:
        # Steam-managed application, has its own handler
        return False

    return True


def run() -> bool:
    P, e, u, g, s, t, c, h, f, E = sys.argv[1:]

    logger.info(f'Process {P} ({e}) dumped core with signal {s} at {time.ctime(int(t))}')
    try:
        appid = sls.util.get_appid(int(P))
    except ValueError:
        appid = None
    minidump = f'{t}-{e}-{P}-{appid}.dmp'
    tmpfile = f'{sls.pending}/minidump/.staging-{minidump}'
    systemd = subprocess.Popen(['/usr/lib/systemd/systemd-coredump', P, u, g, s, t, c, h], stdin=subprocess.PIPE)

    if should_collect(E):
        breakpad = subprocess.Popen(['/usr/lib/breakpad/core_handler', P, tmpfile], stdin=subprocess.PIPE)
        tee(sys.stdin.buffer, (breakpad, systemd))

        if breakpad.returncode:
            logger.error(f'Breakpad core_handler failed with status {breakpad.returncode}')

        try:
            os.setxattr(tmpfile, 'user.executable', f.encode())
            os.setxattr(tmpfile, 'user.comm', e.encode())
            os.setxattr(tmpfile, 'user.path', E.replace('!', '/').encode())
        except OSError as e:
            logger.warning('Failed to set xattrs', exc_info=e)

        shutil.chown(tmpfile, user='steamos-log-submitter')
        os.rename(tmpfile, f'{sls.pending}/minidump/{minidump}')
    else:
        tee(sys.stdin.buffer, (systemd,))

    if systemd.returncode:
        logger.error(f'systemd-coredump failed with status {systemd.returncode}')

    return should_collect(E)


if __name__ == '__main__':  # pragma: no cover
    reconfigure_logging(f'{sls.base}/crash-hook.log', remote=True)
    try:
        if run():
            trigger()
    except Exception as e:
        logger.critical('Unhandled exception', exc_info=e)
