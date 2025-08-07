# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import logging.handlers
import steamos_log_submitter as sls
import steamos_log_submitter.client
from typing import ClassVar, Optional, Union

__all__ = [
    'reconfigure_logging',
]

config = sls.config.get_config(__name__)
logger = logging.getLogger(__name__)
root_logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')


class RemoteHandler(logging.Handler):
    _tasks: ClassVar[list[logging.LogRecord]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self._tasks.append(record)

    @classmethod
    async def drain(cls) -> None:
        client = sls.client.Client()
        await asyncio.gather(*[asyncio.create_task(client.log(record.name, record.levelno, record.getMessage(), record.created)) for record in cls._tasks])
        cls._tasks = []


def valid_level(level: Union[str, int]) -> bool:
    if isinstance(level, str):
        return level.upper() in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    elif isinstance(level, int):
        return level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)


def add_handler(handler: logging.Handler, level: int) -> None:
    handler.setFormatter(formatter)
    handler.setLevel(level)
    root_logger.addHandler(handler)


def reconfigure_logging(path: Optional[str] = None, level: Optional[str] = None, remote: bool = False) -> None:
    level = (level or config.get('level') or 'WARNING').upper()
    if valid_level(level):
        level_int = getattr(logging, level)
    else:
        level_int = logging.WARNING

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    add_handler(logging.StreamHandler(), level_int)

    if path:
        try:
            add_handler(logging.handlers.TimedRotatingFileHandler(path, when='W6', backupCount=4, encoding='utf-8'), level_int)
        except OSError:
            logger.warning("Couldn't open log file")
    if remote:
        try:
            add_handler(RemoteHandler(), level_int)
        except RuntimeError:
            logger.warning("Couldn't open remote log")
    root_logger.setLevel(level_int)

    if level_int < logging.INFO:
        foreign_logger = logging.getLogger('asyncio')
        foreign_logger.setLevel(logging.INFO)
