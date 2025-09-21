# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import os
import time
from types import TracebackType
from typing import Optional, TextIO, Type
from steamos_log_submitter.exceptions import LockHeldError, LockNotHeldError

logger = logging.getLogger(__name__)


class Lockfile:
    def __init__(self, path: str):
        self._path = path
        self.lockfile: Optional[TextIO] = None

    def __enter__(self) -> 'Lockfile':
        self.lock()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> bool:
        self.unlock()
        return not exc_type

    def lock(self) -> None:
        logger.debug(f'Attempting to get lock on {self._path}')
        if self.lockfile:
            logger.debug(f'Lock on {self._path} already held, bailing out')
            return
        while not self.lockfile:
            try:
                self.lockfile = open(self._path, 'x')
            except FileExistsError:
                # The lock exists...let's figure out if it's stale
                logger.debug(f'Lockfile {self._path} already exists, testing staleness')
                try:
                    lockfile = open(self._path, 'r')
                except FileNotFoundError:
                    # The lock was just deleted
                    continue
                lockinfo = None
                for _ in range(3):
                    # There is a slight race condition if the lock has been opened
                    # but the file info hasn't been written yet--let's try a few
                    # times to get that info before giving up
                    lockinfo = lockfile.read()
                    if lockinfo:
                        break
                    time.sleep(0.01)
                lockfile.close()
                if lockinfo is None:
                    # Couldn't get info about the lock...let's assume it's held
                    logger.warning(f'Failed to read lockfile {self._path}, assuming held')
                    raise LockHeldError
                if lockinfo.startswith('/proc/'):
                    pathstat = os.stat(self._path)
                    try:
                        lockstat = os.stat(lockinfo.strip())
                        if (lockstat.st_ino, lockstat.st_dev) == (pathstat.st_ino, pathstat.st_dev):
                            # The lock is currently held
                            raise LockHeldError(f'Lock on {self._path} is already held')
                    except (FileNotFoundError, PermissionError):
                        pass
                # The lock is stale, clean it up
                logger.debug(f'Lockfile {self._path} appears to be stale, taking it')
                self.lockfile = open(self._path, 'w')

        # Store the /proc info on this lock in the file for easy lookup
        self.lockfile.write(f'/proc/{os.getpid()}/fd/{self.lockfile.fileno()}')
        self.lockfile.flush()
        logger.debug(f'Lock on {self._path} obtained')

    def unlock(self) -> None:
        if not self.lockfile:
            raise LockNotHeldError(f'Lock on {self._path} not held')
        # The lock must be deleted before closing to avoid race conditoins
        os.unlink(self._path)
        self.lockfile.close()
        self.lockfile = None
        logger.debug(f'Lock on {self._path} released')


class LockRetry:
    def __init__(self, lock: Lockfile, attempts: int = 5, delay: float = 0.1):
        self.lock = lock
        self._attempts = attempts
        self._delay = delay

    def __enter__(self) -> None:
        for _ in range(self._attempts):
            try:
                self.lock.lock()
            except LockHeldError:
                if _ + 1 == self._attempts:
                    raise
                time.sleep(self._delay)

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> bool:
        self.lock.unlock()
        return not exc_type
