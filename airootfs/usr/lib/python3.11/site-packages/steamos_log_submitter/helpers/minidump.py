# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import os
from steamos_log_submitter.sentry import MinidumpEvent
from . import Helper, HelperResult


class MinidumpHelper(Helper):
    valid_extensions = frozenset({'.md', '.dmp'})

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))
        name_parts = name.split('-')

        event = MinidumpEvent(cls.config['dsn'])
        try:
            event.appid = int(name_parts[-1])
        except ValueError:
            # Invalid appid
            pass

        for attr in ('executable', 'comm', 'path'):
            try:
                event.tags[attr] = os.getxattr(fname, f'user.{attr}').decode(errors='replace')
            except OSError:
                cls.logger.warning(f'Failed to get {attr} xattr on minidump.')

        cls.logger.debug(f'Uploading minidump {fname}')
        try:
            with open(fname, 'rb') as f:
                return HelperResult.check(await event.send_minidump(f))
        except ValueError:
            return HelperResult(HelperResult.PERMANENT_ERROR)
