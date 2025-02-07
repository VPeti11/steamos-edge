# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import json
import logging
import time
import typing
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable, Sequence
from typing import Concatenate, NoReturn, Optional, ParamSpec, Union

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import steamos_log_submitter.exceptions
from steamos_log_submitter.constants import DBUS_NAME, DBUS_ROOT
from steamos_log_submitter.types import DBusEncodable, DBusT

logger = logging.getLogger(__name__)

P = ParamSpec('P')


class Client:
    def __init__(self, *, bus: str = DBUS_NAME):
        self._bus = bus
        self._manager = sls.dbus.DBusObject(bus, f'{DBUS_ROOT}/Manager')
        self._properties = self._manager.properties(f'{DBUS_NAME}.Manager')
        self._iface: Optional[sls.dbus.DBusInterface] = None

    async def _connect(self) -> None:
        if not self._iface:
            try:
                peer = await self._manager.interface('org.freedesktop.DBus.Peer')
                await peer.ping()
            except (dbus.errors.DBusError, dbus.errors.InterfaceNotFoundError) as e:
                if isinstance(e, dbus.errors.DBusError) and e.type == 'org.freedesktop.DBus.Error.ServiceUnknown':
                    logger.error("Can't connect to daemon. Service does not appear to be running.")
                else:
                    logger.error("Can't connect to daemon. Is the service running?", exc_info=e)
                raise ConnectionRefusedError from e
            self._iface = await self._manager.interface(f'{DBUS_NAME}.Manager')

    @staticmethod
    def _rethrow(exc: BaseException) -> NoReturn:
        if isinstance(exc, dbus.errors.DBusError):
            new_exc = sls.exceptions.Error.map.get(exc.type)
            if new_exc:
                raise new_exc(json.loads(exc.text)) from exc
            raise sls.exceptions.UnknownError({'text': exc.text}) from exc
        raise exc

    @staticmethod
    def command(fn: Callable[Concatenate['Client', P], Coroutine[None, None, DBusT]]) -> Callable[Concatenate['Client', P], Coroutine[None, None, DBusT]]:
        async def wrapped(self: 'Client', *args: P.args, **kwargs: P.kwargs) -> DBusT:
            await self._connect()
            try:
                return await fn(self, *args)
            except Exception as e:
                self._rethrow(e)

        return wrapped

    async def validate_helpers(self, requested_helpers: Iterable[str]) -> tuple[list[str], list[str]]:
        valid_names = set(await self.list())
        requested_names = set(requested_helpers)
        return sorted(valid_names & requested_names), sorted(requested_names - valid_names)

    async def _helper_objects(self, helpers: Optional[Iterable[str]]) -> AsyncIterator[tuple[str, sls.dbus.DBusObject]]:
        if helpers is None:
            valid_helpers = await self.list()
        else:
            valid_helpers, invalid_helpers = await self.validate_helpers(helpers)
            if invalid_helpers:
                raise sls.exceptions.InvalidArgumentsError({'invalid-helper': list(invalid_helpers)})
        for helper in valid_helpers:
            camel_case = sls.util.camel_case(helper)
            yield helper, sls.dbus.DBusObject(self._bus, f'{DBUS_ROOT}/helpers/{camel_case}')

    @command
    async def enable(self, state: bool = True) -> None:
        await self._properties.set('Enabled', state)

    async def disable(self) -> None:
        await self.enable(False)

    @command
    async def enable_helpers(self, helpers: list[str]) -> None:
        await self.set_helpers_enabled({helper: True for helper in helpers})

    async def disable_helpers(self, helpers: list[str]) -> None:
        await self.set_helpers_enabled({helper: False for helper in helpers})

    @command
    async def set_helpers_enabled(self, helpers: dict[str, bool]) -> None:
        async for helper, dbus_object in self._helper_objects(helpers.keys()):
            props = dbus_object.properties(f'{DBUS_NAME}.Helper')
            await props.set('Enabled', helpers[helper])

    @command
    async def status(self) -> bool:
        return bool(await self._properties['Enabled'])

    @command
    async def helper_status(self, helpers: Optional[list[str]] = None) -> dict[str, dict[str, DBusEncodable]]:
        status = {}
        async for helper, dbus_object in self._helper_objects(helpers):
            props = dbus_object.properties(f'{DBUS_NAME}.Helper')
            status[helper] = {
                'enabled': await props['Enabled'],
                'collection': await props['CollectEnabled'],
                'submission': await props['SubmitEnabled'],
            }
        return status

    @command
    async def list_pending(self, helpers: Optional[list[str]] = None) -> Sequence[str]:
        if helpers is not None:
            logs: list[str] = []
            async for helper, dbus_object in self._helper_objects(helpers):
                iface = await dbus_object.interface(f'{DBUS_NAME}.Helper')
                logs.extend(f'{helper}/{log}' for log in typing.cast(Iterable[str], await iface.list_pending()))
            return sorted(logs)
        else:
            assert self._iface
            return sorted(typing.cast(Iterable[str], await self._iface.list_pending()))

    @command
    async def log_level(self) -> int:
        return typing.cast(int, await self._properties['LogLevel'])

    @command
    async def set_log_level(self, level: int) -> None:
        return await self._properties.set('LogLevel', level)

    @command
    async def set_steam_info(self, key: str, value: Union[int, str]) -> None:
        assert self._iface
        await self._iface.set_steam_info(key, str(value))

    @command
    async def shutdown(self) -> None:
        assert self._iface
        await self._iface.shutdown()

    @command
    async def trigger(self, wait: bool = True) -> None:
        assert self._iface
        if wait:
            await self._iface.trigger()
        else:
            await self._iface.trigger_async()

    @command
    async def list(self) -> list[str]:
        helpers = sls.dbus.DBusObject(self._bus, f'{DBUS_ROOT}/helpers')
        return [sls.util.snake_case(child.rsplit('/')[-1]) for child in await helpers.list_children()]

    @command
    async def log(self, module: str, level: int, message: str, timestamp: Optional[float] = None) -> None:
        assert self._iface
        await self._iface.log(timestamp or time.time(), module, level, message)
