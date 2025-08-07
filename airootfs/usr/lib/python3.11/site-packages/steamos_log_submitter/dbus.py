# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import inspect
import typing
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from types import CoroutineType, UnionType
from typing import Optional, Type, Union

from steamos_log_submitter.types import DBusCallable, DBusCallableAsync, DBusCallableSync, DBusEncodable

connected = False
system_bus = None


async def connect() -> None:
    global system_bus
    global connected
    if connected:
        return

    system_bus = dbus.aio.MessageBus(bus_type=dbus.BusType.SYSTEM)

    await system_bus.connect()
    connected = True


def signature(type_annotation: Union[type, UnionType]) -> str:
    if type_annotation is int:
        return 'i'
    if type_annotation is float:
        return 'd'
    if type_annotation is bool:
        return 'b'
    if type_annotation is str:
        return 's'
    origin = typing.get_origin(type_annotation)
    types = typing.get_args(type_annotation)
    if origin is None:
        raise TypeError
    if origin is Union or issubclass(origin, UnionType):
        return 'v'
    if issubclass(origin, Mapping):
        key = signature(types[0])
        value = signature(types[1])
        return 'a{' + key + value + '}'
    if issubclass(origin, tuple):
        return '(' + ''.join(signature(typ) for typ in types) + ')'
    if issubclass(origin, Sequence):
        value = signature(types[0])
        return 'a' + value
    raise TypeError


def fn_signature(fn: DBusCallable) -> inspect.Signature:
    inspection = inspect.signature(fn)
    arguments_signature = [inspect.Parameter('self', inspect._ParameterKind.POSITIONAL_ONLY)]
    for i, arg in enumerate(inspection.parameters.values()):
        if not i:
            continue
        arguments_signature.append(inspect.Parameter(arg.name, arg.kind, annotation=signature(arg.annotation)))
    return_signature: Union[Type[inspect._empty], str] = inspect._empty
    if inspection.return_annotation is not inspect._empty:
        return_signature = signature(inspection.return_annotation)

    return inspect.Signature(arguments_signature, return_annotation=return_signature)


def adbusify(fn: DBusCallableAsync) -> DBusCallableAsync:
    async def wrapped(*args: DBusEncodable) -> Optional[DBusEncodable]:
        coro = typing.cast(DBusCallableAsync, fn)(*args)
        assert isinstance(coro, CoroutineType)
        return typing.cast(DBusEncodable, await coro)

    wrapped.__signature__ = fn_signature(fn)  # type: ignore[attr-defined]
    return wrapped


def dbusify(fn: DBusCallableSync) -> DBusCallableSync:
    def wrapped(*args: DBusEncodable) -> Optional[DBusEncodable]:
        return typing.cast(DBusCallableSync, fn)(*args)

    wrapped.__signature__ = fn_signature(fn)  # type: ignore[attr-defined]
    return wrapped


class DBusInterface:
    def __init__(self, obj: 'DBusObject', iface: str):
        self._obj = obj
        self._iface = iface
        self._iface_handle: Optional[dbus.aio.ProxyInterface] = None

    def __getattr__(self, name: str) -> DBusCallableAsync:
        async def call(*args: DBusEncodable) -> Optional[DBusEncodable]:
            if not self._iface_handle:
                await self._obj._connect()
                self._iface_handle = self._obj.object.get_interface(self._iface)
            method: DBusCallableAsync = getattr(self._iface_handle, f'call_{name}')
            setattr(self, name, method)  # Memoize the method so we only have to look it up once
            return await method(*args)
        return call


class DBusProperties:
    def __init__(self, obj: 'DBusObject', iface: str):
        self._properties_iface: Optional[dbus.aio.ProxyInterface] = None
        self._iface_handle: Optional[dbus.aio.ProxyInterface] = None
        self._obj = obj
        self._iface = iface
        self._subscribed: dict[str, list[Callable[[str, str, DBusEncodable], Awaitable[None]]]] = {}

    async def __getitem__(self, name: str) -> DBusEncodable:
        if not self._properties_iface:
            await self._obj._connect()
            self._properties_iface = self._obj.object.get_interface('org.freedesktop.DBus.Properties')
        variant = await self._properties_iface.call_get(self._iface, name)  # type: ignore[attr-defined]
        return typing.cast(DBusEncodable, variant.value)

    async def set(self, name: str, value: DBusEncodable) -> None:
        if not self._iface_handle:
            await self._obj._connect()
            self._iface_handle = self._obj.object.get_interface(self._iface)
        name = dbus.proxy_object.BaseProxyInterface._to_snake_case(name)
        await getattr(self._iface_handle, f'set_{name}')(value)

    def _update_props(self, iface: str, changed: dict[str, dbus.Variant], invalidated: list[str]) -> None:
        async def do_cb(cb: Callable[[str, str, DBusEncodable], Awaitable[None]], iface: str, prop: str, value: Optional[dbus.Variant]) -> None:
            if value is None:
                assert self._properties_iface
                value = await self._properties_iface.call_get(self._iface, prop)  # type: ignore[attr-defined]
            await cb(iface, prop, value.value)

        for prop, value in changed.items():
            if prop not in self._subscribed:
                continue
            for handler in self._subscribed[prop]:
                asyncio.create_task(do_cb(handler, iface, prop, value))
        for prop in invalidated:
            if prop not in self._subscribed:
                continue
            for handler in self._subscribed[prop]:
                asyncio.create_task(do_cb(handler, iface, prop, None))

    async def subscribe(self, prop: str, cb: Callable[[str, str, DBusEncodable], Awaitable[None]]) -> None:
        await self._obj._connect()
        if not self._subscribed:
            iface_handle = self._obj.object.get_interface('org.freedesktop.DBus.Properties')
            iface_handle.on_properties_changed(self._update_props)  # type: ignore[attr-defined]
        self._subscribed[prop] = self._subscribed.get(prop, [])
        self._subscribed[prop].append(cb)


class DBusObject:
    def __init__(self, bus_name: str, object_path: str):
        self.bus = system_bus
        self.bus_name = bus_name
        self.object_path = object_path
        self.connected = False

    async def _connect(self) -> None:
        if self.connected:
            return
        if not connected:
            await connect()
        if not self.bus:
            self.bus = system_bus
        assert self.bus
        introspection = await self.bus.introspect(self.bus_name, self.object_path)
        self.object = self.bus.get_proxy_object(self.bus_name, self.object_path, introspection)

    def properties(self, iface: str) -> DBusProperties:
        return DBusProperties(self, iface)

    async def interface(self, iface: str) -> DBusInterface:
        await self._connect()
        return DBusInterface(self, iface)

    async def list_children(self) -> Iterable[str]:
        await self._connect()
        return self.object.child_paths
