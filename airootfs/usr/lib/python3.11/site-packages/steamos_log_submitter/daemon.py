# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import dbus_next as dbus
import gc
import importlib.machinery
import inspect
import json
import logging
import os
import psutil
import time
import typing
from collections.abc import Callable
from typing import Optional

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import steamos_log_submitter.runner
import steamos_log_submitter.steam
from steamos_log_submitter.constants import DBUS_NAME, DBUS_ROOT
from steamos_log_submitter.types import DBusEncodable

__loader__: importlib.machinery.SourceFileLoader
config = sls.config.get_config(__loader__.name)
logger = logging.getLogger(__loader__.name)


class Daemon:
    STARTUP: float = 20
    INTERVAL: float = 3600
    WAKEUP_DELAY: float = 10

    def __init__(self, *, exit_on_shutdown: bool = False):
        self._exit_on_shutdown = exit_on_shutdown
        self._periodic_task: Optional[asyncio.Task[None]] = None
        self._async_trigger: Optional[asyncio.Task[None]] = None
        self._serving = False
        self._suspend = 'inactive'
        self._trigger_active = False
        self._next_trigger = 0.0
        self._iface: Optional[DaemonInterface] = None

    async def _trigger_periodic(self) -> None:
        gc.collect()
        next_interval = self._next_trigger - time.time()
        if next_interval > 0:
            logger.debug(f'Sleeping for {next_interval:.3f} seconds')
            await asyncio.sleep(next_interval)

        if not self._serving:
            return
        await self.trigger(wait=True)

    def _setup_dbus(self) -> None:
        assert sls.dbus.system_bus
        self.iface = DaemonInterface(self)
        sls.dbus.system_bus.export(f'{DBUS_ROOT}/Manager', self.iface)
        for helper in sls.helpers.list_helpers():
            helper_module = sls.helpers.create_helper(helper)
            if not helper_module or not helper_module.iface:
                continue
            camel_case = sls.util.camel_case(helper_module.name)
            sls.dbus.system_bus.export(f'{DBUS_ROOT}/helpers/{camel_case}', helper_module.iface)

            for iface in helper_module.extra_ifaces:
                sls.dbus.system_bus.export(f'{DBUS_ROOT}/helpers/{camel_case}', iface)
            for service, iface in helper_module.child_services.items():
                sls.dbus.system_bus.export(f'{DBUS_ROOT}/helpers/{camel_case}/{service}', iface)

    async def _leave_suspend(self, iface: str, prop: str, value: DBusEncodable) -> None:
        assert isinstance(value, str)
        if value == self._suspend:
            return
        self._suspend = value
        logger.debug(f'Suspend state changed to {value}')
        if value == 'inactive':
            if self._trigger_active:
                return
            logger.info('Woke up from suspend, attempting to submit logs')
            await asyncio.sleep(self.WAKEUP_DELAY)
            await self.trigger(wait=True)

    async def start(self) -> None:
        if self._serving:
            return
        logger.info('Daemon starting up')
        sls.config.upgrade()
        self._serving = True

        self._next_trigger = time.time() + self.STARTUP
        last_trigger = config.get('last_trigger')
        if last_trigger is not None:
            next_trigger = float(last_trigger) + self.INTERVAL
            if next_trigger > self._next_trigger:
                self._next_trigger = next_trigger

        if not self.inhibited() and self.enabled():
            self._periodic_task = asyncio.create_task(self._trigger_periodic())

        await sls.dbus.connect()
        assert sls.dbus.system_bus
        try:
            await sls.dbus.system_bus.request_name(DBUS_NAME)
        except (dbus.errors.DBusError, RuntimeError) as e:
            logger.error('Failed to claim D-Bus bus name', exc_info=e)
        self._setup_dbus()

        try:
            suspend_target = sls.dbus.DBusObject('org.freedesktop.systemd1', '/org/freedesktop/systemd1/unit/suspend_2etarget')
            suspend_props = suspend_target.properties('org.freedesktop.systemd1.Unit')
            await suspend_props.subscribe('ActiveState', self._leave_suspend)
        except dbus.errors.DBusError as e:
            logger.error('Failed to subscribe to suspend state', exc_info=e)

    async def shutdown(self) -> None:
        logger.info('Daemon shutting down')
        self._serving = False
        if self._async_trigger:
            await self._async_trigger
            self._async_trigger = None
        if self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
            self._periodic_task = None

        bus = sls.dbus.system_bus
        if bus:
            bus.unexport(f'{DBUS_ROOT}/Manager', self.iface)
            for helper in sls.helpers.list_helpers():
                helper_module = sls.helpers.create_helper(helper)
                if not helper_module or not helper_module.iface:
                    continue
                camel_case = sls.util.camel_case(helper_module.name)
                bus.unexport(f'{DBUS_ROOT}/helpers/{camel_case}', helper_module.iface.name)

                for iface in helper_module.extra_ifaces:
                    bus.unexport(f'{DBUS_ROOT}/helpers/{camel_case}', iface.name)
                for service, iface in helper_module.child_services.items():
                    bus.unexport(f'{DBUS_ROOT}/helpers/{camel_case}/{service}', iface.name)

        if self._exit_on_shutdown:  # pragma: no cover
            loop = asyncio.get_event_loop()
            loop.stop()

    async def _trigger(self) -> None:
        if self.inhibited() or not self.enabled():
            self._async_trigger = None
            return
        if self._trigger_active:
            self._async_trigger = None
            return
        self._trigger_active = True
        await sls.runner.trigger()
        last_trigger = time.time()
        config['last_trigger'] = last_trigger
        sls.config.write_config()
        self._next_trigger = last_trigger + self.INTERVAL
        task = self._periodic_task
        if self._serving:
            self._periodic_task = asyncio.create_task(self._trigger_periodic())
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._trigger_active = False
        self._async_trigger = None

    async def trigger(self, wait: bool = True) -> None:
        if self.inhibited() or not self.enabled():
            return
        if self._trigger_active:
            if not wait:
                return
            stored_coro = self._async_trigger or self._periodic_task
            if not stored_coro:
                logger.error('Neither async trigger nor periodic trigger active. Who owns the trigger lock?')
                return
            await stored_coro
            assert not self._trigger_active
            return
        if self._async_trigger:
            if wait:
                await self._async_trigger
            return
        coro = self._trigger()
        if wait:
            await coro
        else:
            self._async_trigger = asyncio.create_task(coro)

    def enabled(self) -> bool:
        return sls.base_config.get('enable', 'off') == 'on'

    async def enable(self, state: bool) -> None:
        if self.enabled() is state:
            return
        if not state and self._async_trigger:
            await self._async_trigger
        sls.base_config['enable'] = 'on' if state else 'off'
        sls.config.write_config()
        await self._update_schedule()
        if self.iface:
            self.iface.emit_properties_changed({'Enabled': self.enabled()})

    def inhibited(self) -> bool:
        return sls.base_config.get('inhibit', 'off') == 'on'

    async def inhibit(self, state: bool) -> None:
        if self.inhibited() is state:
            return
        if state and self._async_trigger:
            await self._async_trigger
        sls.base_config['inhibit'] = 'on' if state else 'off'
        sls.config.write_config()
        await self._update_schedule()
        if self.iface:
            self.iface.emit_properties_changed({'Inhibited': self.inhibited()})

    async def _update_schedule(self) -> None:
        inhibited = self.inhibited() or not self.enabled()
        if inhibited and self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass
            self._periodic_task = None
        elif not inhibited and not self._periodic_task:
            self._periodic_task = asyncio.create_task(self._trigger_periodic())

    def log_level(self) -> int:
        return typing.cast(int, getattr(logging, (sls.logging.config.get('level') or 'WARNING').upper()))

    async def set_log_level(self, level: int) -> None:
        if not sls.logging.valid_level(level):
            raise sls.exceptions.InvalidArgumentsError({'level': level})
        sls.config.migrate_key('logging', 'level')
        sls.logging.config['level'] = logging.getLevelName(level)
        sls.config.write_config()
        sls.logging.reconfigure_logging(sls.logging.config.get('path'))
        self.iface.emit_properties_changed({'LogLevel': level})

    async def set_steam_info(self, key: str, value: str) -> None:
        if key not in (
            'deck_serial',
            'account_id',
            'account_name'
        ):
            logger.warning(f'Got Steam info change for invalid key {key}')
            raise sls.exceptions.InvalidArgumentsError({'key': key})

        logger.debug(f'Changing Steam info key {key} to {value}')
        sls.steam.config[key] = value
        sls.config.write_config()

        if self.iface:
            if key == 'deck_serial':
                self.iface.emit_properties_changed({'UnitId': sls.util.telemetry_unit_id() or ''})
            else:
                self.iface.emit_properties_changed({'UserId': sls.util.telemetry_user_id() or ''})


def _reraise(exc: sls.exceptions.Error) -> None:
    blob = json.dumps(exc.data)
    raise dbus.errors.DBusError(exc.name, blob) from exc


def exc_awrap(fn: Callable) -> Callable:
    async def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return await fn(*args, **kwargs)
        except sls.exceptions.Error as e:
            _reraise(e)

    wrapped.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    wrapped.__name__ = fn.__name__
    return wrapped


def exc_wrap(fn: Callable) -> Callable:
    def wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
        try:
            return fn(*args, **kwargs)
        except sls.exceptions.Error as e:
            _reraise(e)

    wrapped.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    wrapped.__name__ = fn.__name__
    return wrapped


class DaemonInterface(dbus.service.ServiceInterface):
    def __init__(self, daemon: 'sls.daemon.Daemon'):
        super().__init__(f'{DBUS_NAME}.Manager')
        self.daemon = daemon

    @dbus.service.dbus_property(access=dbus.constants.PropertyAccess.READ)
    def Version(self) -> 's':  # type: ignore[name-defined] # NOQA: F821
        return sls.__version__

    @dbus.service.dbus_property()
    @exc_wrap
    def Enabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.daemon.enabled()

    @Enabled.setter
    @exc_awrap
    async def set_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        await self.daemon.enable(enable)

    @dbus.service.dbus_property()
    @exc_wrap
    def Inhibited(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.daemon.inhibited()

    @Inhibited.setter
    @exc_awrap
    async def set_inhibited(self, inhibit: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        await self.daemon.inhibit(inhibit)

    @dbus.service.dbus_property()
    @exc_wrap
    def CollectEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return sls.base_config.get('collect', 'on') == 'on'

    @CollectEnabled.setter
    @exc_wrap
    def set_collect_enabled(self, enabled: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        sls.base_config['collect'] = 'on' if enabled else 'off'
        sls.config.write_config()

    @dbus.service.dbus_property()
    @exc_wrap
    def SubmitEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return sls.base_config.get('submit', 'on') == 'on'

    @SubmitEnabled.setter
    @exc_wrap
    def set_submit_enabled(self, enabled: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        sls.base_config['submit'] = 'on' if enabled else 'off'
        sls.config.write_config()

    @dbus.service.dbus_property()
    @exc_wrap
    def LogLevel(self) -> 'u':  # type: ignore[name-defined] # NOQA: F821
        return self.daemon.log_level()

    @LogLevel.setter
    @exc_awrap
    async def set_log_level(self, level: 'u'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        await self.daemon.set_log_level(level)

    @dbus.service.method()
    @exc_awrap
    async def Trigger(self):  # type: ignore[no-untyped-def]
        await self.daemon.trigger(wait=True)

    @dbus.service.method()
    @exc_awrap
    async def TriggerAsync(self):  # type: ignore[no-untyped-def]
        await self.daemon.trigger(wait=False)

    @dbus.service.method()
    @exc_awrap
    async def Shutdown(self):  # type: ignore[no-untyped-def]
        await self.daemon.shutdown()

    @dbus.service.method()
    @exc_awrap
    async def SetSteamInfo(self, key: 's', value: 's'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        await self.daemon.set_steam_info(key, value)

    @dbus.service.dbus_property(access=dbus.constants.PropertyAccess.READ)
    def UserId(self) -> 's':  # type: ignore[name-defined] # NOQA: F821
        return sls.util.telemetry_user_id() or ''

    @dbus.service.dbus_property(access=dbus.constants.PropertyAccess.READ)
    def UnitId(self) -> 's':  # type: ignore[name-defined] # NOQA: F821
        return sls.util.telemetry_unit_id() or ''

    @dbus.service.method()
    @exc_awrap
    async def ListPending(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        pending: list[str] = []
        for helper in sls.helpers.list_helpers():
            helper_module = sls.helpers.create_helper(helper)
            if helper_module:
                pending.extend(f'{helper}/{log}' for log in helper_module.list_pending())
        return pending

    @dbus.service.method()
    @exc_awrap
    async def Log(self, timestamp: 'd', module: 's', level: 'u', message: 's'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        if not sls.logging.valid_level(level):
            raise sls.exceptions.InvalidArgumentsError({'level': level})
        logger = logging.getLogger(module)
        real_time = time.time
        time.time = lambda: typing.cast(float, timestamp)
        try:
            logger.log(level, message)
        finally:
            time.time = real_time


if __name__ == '__main__':  # pragma: no cover
    sls.logging.reconfigure_logging(sls.logging.config.get('path'))
    try:
        os.nice(10)  # De-prioritize background work
        psutil.Process().ionice(psutil.IOPRIO_CLASS_BE, value=7)
    except OSError as e:
        logger.error('Failed to downgrade process priority', exc_info=e)
    daemon = Daemon(exit_on_shutdown=True)
    loop = asyncio.get_event_loop()
    loop.create_task(daemon.start())
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
