# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import steamos_log_submitter.config as config
import steamos_log_submitter.data as data
import steamos_log_submitter.exceptions as exceptions
import steamos_log_submitter.helpers as helpers
import steamos_log_submitter.logging as logging
import steamos_log_submitter.runner as runner
import steamos_log_submitter.steam as steam
import steamos_log_submitter.util as util

import asyncio

__all__ = [
    # Constants
    'base',
    'pending',
    'failed',
    'uploaded',
    # Utility functions
    'trigger',
    # Submodules
    'config',
    'data',
    'exceptions',
    'helpers',
    'logging',
    'steam',
    'util',
]
__version__ = '0.3.1'

_setup = False

base_config: config.ConfigSection
base: str
pending: str
uploaded: str
failed: str


def setup() -> None:
    global _setup
    global base_config
    global base
    global pending
    global uploaded
    global failed

    if _setup:
        return

    base_config = config.get_config(__name__, defaults={
        'enable': 'off',
        'base': '/var/lib/steamos-log-submitter',
    })

    base = base_config['base']
    pending = f'{base}/pending'
    uploaded = f'{base}/uploaded'
    failed = f'{base}/failed'

    data._setup()
    steam._setup()

    logging.reconfigure_logging()

    _setup = True


def trigger() -> None:
    asyncio.run(runner.trigger())


setup()
