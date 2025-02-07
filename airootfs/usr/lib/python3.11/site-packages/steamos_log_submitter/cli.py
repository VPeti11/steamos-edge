# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from types import TracebackType
from typing import ClassVar, Concatenate, Optional, ParamSpec, Type

import steamos_log_submitter as sls
import steamos_log_submitter.client
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.types import DBusEncodable

P = ParamSpec('P')


class ClientWrapper:
    bus: ClassVar[str] = DBUS_NAME

    async def __aenter__(self) -> Optional[sls.client.Client]:
        try:
            client = sls.client.Client(bus=self.bus)
            await client._connect()
            return client
        except ConnectionRefusedError:
            return None

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]) -> bool:
        return not exc_type


def command(fn: Callable[Concatenate[sls.client.Client, P], Awaitable[None]]) -> Callable[P, Awaitable[None]]:
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> None:
        async with ClientWrapper() as client:
            if not client:
                return
            await fn(client, *args, **kwargs)

    return wrapped


@command
async def set_enabled(client: sls.client.Client, enable: bool) -> None:
    await client.enable(enable)


@command
async def set_helper_enabled(client: sls.client.Client, helpers: list[str], enable: bool) -> None:
    helpers, invalid_helpers = sls.helpers.validate_helpers(helpers)
    if invalid_helpers:
        print('Invalid helpers:', ', '.join(invalid_helpers), file=sys.stderr)
    if enable:
        await client.enable_helpers(helpers)
    else:
        await client.disable_helpers(helpers)


@command
async def do_status(client: sls.client.Client, args: argparse.Namespace) -> None:
    status = await client.status()
    helpers: Optional[dict[str, dict[str, DBusEncodable]]] = None
    if args.all:
        helpers = await client.helper_status()
    elif args.helper:
        valid_helpers, invalid_helpers = await client.validate_helpers(args.helper)
        if valid_helpers:
            helpers = await client.helper_status(valid_helpers)
        if invalid_helpers:
            print('Invalid helpers:', ', '.join(invalid_helpers), file=sys.stderr)
    print('Log submission is currently ' + ('enabled' if status else 'disabled'))
    if helpers:
        for helper, helper_status in helpers.items():
            print(f'Helper {helper} is currently ' + ('enabled' if helper_status['enabled'] else 'disabled'))


@command
async def do_list(client: sls.client.Client, args: argparse.Namespace) -> None:
    for helper in sorted(await client.list()):
        print(helper)


@command
async def do_pending(client: sls.client.Client, args: argparse.Namespace) -> None:
    logs: Sequence[str] = []
    if args.helper:
        valid_helpers, invalid_helpers = await client.validate_helpers(args.helper)
        if valid_helpers:
            logs = await client.list_pending(valid_helpers)
        if invalid_helpers:
            print('Invalid helpers:', ', '.join(invalid_helpers), file=sys.stderr)
    else:
        logs = await client.list_pending()
    if logs:
        print(*logs, sep='\n')


@command
async def do_log_level(client: sls.client.Client, args: argparse.Namespace) -> None:
    if args.level is None:
        print(logging.getLevelName(await client.log_level()))
    elif sls.logging.valid_level(args.level):
        await client.set_log_level(getattr(logging, args.level.upper()))
    else:
        print('Please specify a valid log level', file=sys.stderr)


async def set_steam_info(key: str, value: str) -> None:
    if key == 'account-id':
        try:
            int(value)
        except ValueError:
            print('Account ID must be numeric', file=sys.stderr)
            return

    async with ClientWrapper() as client:
        if not client:
            return
        await client.set_steam_info(key.replace('-', '_'), value)


@command
async def do_trigger(client: sls.client.Client, args: argparse.Namespace) -> None:
    await client.trigger(args.wait)


@command
async def do_autoconfig_steam(client: sls.client.Client, args: argparse.Namespace) -> None:
    info = {
        'account_name': sls.steam.get_account_name(force_vdf=True) or '',
        'account_id': sls.steam.get_account_id(force_vdf=True) or '',
        'deck_serial': sls.steam.get_deck_serial(force_vdf=True) or '',
    }

    for key, value in info.items():
        await client.set_steam_info(key, value)


def amain(args: Sequence[str] = sys.argv[1:]) -> Coroutine:
    parser = argparse.ArgumentParser(
        prog='steamos-log-submitter',
        description='SteamOS log collection and submission tool')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug logging')
    subparsers = parser.add_subparsers(required=True, metavar='command')

    status = subparsers.add_parser('status',
                                   description='''Display the current status of the log
                                                  collection service and helper modules.''',
                                   help='Current status')
    status.add_argument('-a', '--all', action='store_true', help='Show the status of all helpers')
    status.add_argument('helper', nargs='*', help='Which helpers to show the status of')
    status.set_defaults(func=do_status)

    trigger = subparsers.add_parser('trigger',
                                    description='Trigger an immediate log collection and submission',
                                    help='Trigger collection/submission')
    trigger.add_argument('--wait', action='store_true', help='Wait until complete')
    trigger.set_defaults(func=do_trigger)

    enable = subparsers.add_parser('enable',
                                   description='Enable the log collection service.',
                                   help='Enable log collection')
    enable.set_defaults(func=lambda _: set_enabled(True))

    disable = subparsers.add_parser('disable',
                                    description='Disable the log collection service.',
                                    help='Disable log collection')
    disable.set_defaults(func=lambda _: set_enabled(False))

    pending = subparsers.add_parser('pending',
                                    description='''Output a list of log files that are
                                                   currently pending submission.''',
                                    help='List log files pending submission')
    pending.add_argument('helper', nargs='*', help='''Which helpers to show the pending logs for.
                                                      If not specified, all pending logs are shown.''')
    pending.set_defaults(func=do_pending)

    list_cmd = subparsers.add_parser('list',
                                     description='''List all available helper modules. Each helper
                                                    module handles one or more types of logs that have
                                                    a common method of collection and submission.''',
                                     help='List helper modules')
    list_cmd.set_defaults(func=do_list)

    enable_helper = subparsers.add_parser('enable-helper',
                                          description='Enable one or more specific helper modules.',
                                          help='Enable helper modules')
    enable_helper.add_argument('helper', nargs='+')
    enable_helper.set_defaults(func=lambda args: set_helper_enabled(args.helper, True))

    disable_helper = subparsers.add_parser('disable-helper',
                                           description='Enable one or more specific helper modules.',
                                           help='Disable helper modules')
    disable_helper.add_argument('helper', nargs='+')
    disable_helper.set_defaults(func=lambda args: set_helper_enabled(args.helper, False))

    log_level = subparsers.add_parser('log-level',
                                      description='''Set or get the log level. If no argument is passed,
                                                     print the current log level, otherwise set a new
                                                     log level.''',
                                      help='Set or get the log level')
    log_level.add_argument('level', type=str, nargs='?',
                           help='''Which new log level to set. The possible levels are DEBUG, INFO,
                                   WARNING, ERROR, and CRITICAL, in order from least to most severe.''')
    log_level.set_defaults(func=do_log_level)

    set_steam = subparsers.add_parser('set-steam-info',
                                      description='''Set a value relating to the current Steam configuration.
                                                     This command should not be used directly, as any values
                                                     manually set may be changed by Steam directly.''')
    set_steam.add_argument('key', choices=('account-name', 'account-id', 'deck-serial'))
    set_steam.add_argument('value', type=str)
    set_steam.set_defaults(func=lambda args: set_steam_info(args.key, args.value))

    autoconfig_steam = subparsers.add_parser('autoconfig-steam-info',
                                             description='''Automatically set values relating to the current Steam
                                                            configuration. This command should only be used for testing,
                                                            as any values set may be changed by Steam directly.''')
    autoconfig_steam.set_defaults(func=do_autoconfig_steam)

    parsed_args = parser.parse_args(args)

    sls.logging.reconfigure_logging(level='DEBUG' if parsed_args.debug else 'WARNING')

    coro = parsed_args.func(parsed_args)
    assert asyncio.iscoroutine(coro)
    return coro


def main(args: Sequence[str] = sys.argv[1:]) -> None:  # pragma: no cover
    asyncio.run(amain(args))


if __name__ == '__main__':  # pragma: no cover
    main()
