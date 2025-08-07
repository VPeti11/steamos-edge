# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import json
import os
from typing import Optional

import steamos_log_submitter as sls
from steamos_log_submitter.dbus import DBusObject
from steamos_log_submitter.sentry import SentryEvent
from steamos_log_submitter.types import JSONEncodable

from . import Helper, HelperResult


class JournalHelper(Helper):
    valid_extensions = frozenset({'.json'})
    units = [
        'gpu-trace.service',
        'jupiter-biosupdate.service',
        'jupiter-controller-update.service',
        'jupiter-fan-control.service',
        'rauc.service',
        'steam-web-debug-portforward.service',
        'steamos-boot.service',
        'steamos-cfs-debugfs-tunings.service',
        'steamos-create-homedir.service',
        'steamos-devkit-service.service',
        'steamos-dump-info.service',
        'steamos-finish-oobe-migration.service',
        'steamos-glx-backend.service',
        'steamos-install-grub.service',
        'steamos-install-steamcl.service',
        'steamos-kdumpst-layer.service',
        'steamos-log-submitter.service',
        'steamos-mkvarboot.service',
        'steamos-offload.target',
        'steamos-settings-importer.service',
        'steamos-update-os-plymouth.service',
        'steamos-update-os.service',
        'steamos-update-os.target',
    ]

    @classmethod
    async def read_journal(cls, unit: str, cursor: Optional[str] = None) -> tuple[Optional[list[dict]], Optional[str]]:
        cmd = ['journalctl', '-o', 'json', '-u', unit]
        if cursor is not None:
            cmd.extend(['--after-cursor', cursor])
        try:
            journal = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            assert journal.stdout

            invocations: dict[str, list] = {}
            cursor = None
            while True:
                line = await journal.stdout.readline()
                if not line:
                    break
                log = json.loads(line.decode())
                invocation = log.get('INVOCATION_ID')
                if not invocation:
                    invocation = log.get('_SYSTEMD_INVOCATION_ID', '')
                logs = invocations.get(invocation, [])
                logs.append(log)
                invocations[invocation] = logs

                cursor = log['__CURSOR']
        except OSError as e:
            cls.logger.error('Failed to exec journalctl', exc_info=e)
            return None, None

        pruned_invocations = []
        for logs in invocations.values():
            if 'UNIT_RESULT' in logs[-1]:
                pruned_invocations.extend(logs)

        return pruned_invocations, cursor

    @classmethod
    def escape(cls, name: str) -> str:
        alphabet = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        alphanumeric = frozenset(b for b in alphabet)
        bname = name.encode()
        return ''.join([chr(char) if char in alphanumeric else f'_{char:2x}' for char in bname])

    @classmethod
    def unescape(cls, escaped: str) -> str:
        unescaped = []
        progress: Optional[list[str]] = None
        for char in escaped:
            if progress is None:
                if char != '_':
                    unescaped.append(char)
                else:
                    progress = []
            else:
                progress.append(char)
                if len(progress) == 2:
                    try:
                        unescaped.append(chr(int(''.join(progress), 16)))
                    except ValueError:
                        cls.logger.warning(f'Malformed escaped unit name {escaped}')
                    progress = None
        return ''.join(unescaped)

    @classmethod
    async def collect(cls) -> bool:
        bus = 'org.freedesktop.systemd1'
        updated = False
        for unit in cls.units:
            try:
                dbus_unit = DBusObject(bus, f'/org/freedesktop/systemd1/unit/{cls.escape(unit)}')
                props = dbus_unit.properties('org.freedesktop.systemd1.Unit')
                state = await props['ActiveState']
            except (dbus.errors.DBusError, KeyError) as e:
                cls.logger.warning(f'Exception getting state of unit {unit}', exc_info=e)
                continue
            if state != 'failed':
                continue

            cursor = cls.data.get(f'{cls.escape(unit)}.cursor')
            assert cursor is None or isinstance(cursor, str)
            journal, cursor = await cls.read_journal(unit, cursor)

            if not journal:
                cls.logger.error(f'Failed reading journal for unit {unit}')
                continue

            old_journal = []
            try:
                with open(f'{sls.pending}/journal/{cls.escape(unit)}.json', 'rt') as f:
                    old_journal = json.load(f)
            except FileNotFoundError:
                pass
            except json.decoder.JSONDecodeError as e:
                cls.logger.warning(f'Failed decoding log pending/journal/{cls.escape(unit)}.json', exc_info=e)
            except OSError as e:
                cls.logger.error(f'Failed loading log pending/journal/{cls.escape(unit)}.json', exc_info=e)
                continue

            old_journal.extend(journal)
            journal = old_journal

            try:
                with open(f'{sls.pending}/journal/{cls.escape(unit)}.json', 'wt') as f:
                    json.dump(journal, f)
                cls.data[f'{cls.escape(unit)}.cursor'] = cursor
                updated = True
            except OSError as e:
                cls.logger.error(f'Failed writing log pending/journal/{cls.escape(unit)}.json', exc_info=e)

        if updated:
            try:
                cls.data.write()
            except OSError as e:
                cls.logger.error('Failed writing updated cursor information', exc_info=e)

        return updated

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))

        try:
            with open(fname, 'rb') as f:
                attachment = f.read()
        except OSError:
            return HelperResult(HelperResult.TRANSIENT_ERROR)

        tags: dict[str, JSONEncodable] = {}
        fingerprint = []

        unit = cls.unescape(name)
        tags['unit'] = unit
        fingerprint.append(f'unit:{unit}')

        tags['kernel'] = os.uname().release

        event = SentryEvent(cls.config['dsn'])
        event.add_attachment({
            'mime-type': 'application/json',
            'filename': os.path.basename(fname),
            'data': attachment
        })
        event.tags = tags
        event.fingerprint = fingerprint
        event.message = unit
        return HelperResult.check(await event.send())
