# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import dbus_next as dbus
import importlib
import logging
import os
import pkgutil
import sys
import tempfile
import typing
from collections.abc import Container, Iterable
from types import TracebackType
from typing import Any, ClassVar, Final, Optional, Type

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
import steamos_log_submitter.sentry
import steamos_log_submitter.lockfile
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)


class HelperResult:
    OK: Final[int] = 0
    TRANSIENT_ERROR: Final[int] = -1
    PERMANENT_ERROR: Final[int] = -2
    CLASS_ERROR: Final[int] = -3

    def __init__(self, code: int = OK):
        super(HelperResult, self).__init__()
        self.code = code

    @staticmethod
    def check(result: bool, *, true_code: int = OK, false_code: int = TRANSIENT_ERROR) -> 'HelperResult':
        if result:
            return HelperResult(true_code)
        return HelperResult(false_code)


class HelperInterface(dbus.service.ServiceInterface):
    def __init__(self, helper: Type['Helper']):
        super().__init__(f'{DBUS_NAME}.Helper')
        self.helper = helper

    @dbus.service.dbus_property()
    def Enabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.enabled()

    @Enabled.setter
    def set_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable(enable)

    @dbus.service.dbus_property()
    def CollectEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.collect_enabled()

    @CollectEnabled.setter
    def set_collect_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable_collect(enable)

    @dbus.service.dbus_property()
    def SubmitEnabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.helper.submit_enabled()

    @SubmitEnabled.setter
    def set_submit_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        return self.helper.enable_submit(enable)

    @dbus.service.method()
    async def Collect(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return await self.helper.collect()

    @dbus.service.method()
    async def ListPending(self) -> 'as':  # type: ignore[valid-type] # NOQA: F821, F722
        return list(self.helper.list_pending())


class Helper:
    defaults: ClassVar[Optional[dict[str, JSONEncodable]]] = None
    valid_extensions: ClassVar[Container[str]] = frozenset()

    __name__: str
    name: str
    config: sls.config.ConfigSection
    data: sls.data.DataStore
    iface: Optional[HelperInterface]
    extra_ifaces: list[dbus.service.ServiceInterface]
    child_services: dict[str, dbus.service.ServiceInterface]
    logger: logging.Logger

    @classmethod
    def __init_subclass__(cls) -> None:
        module = cls.__module__
        cls.logger = logging.getLogger(module)
        cls.iface = None
        cls.extra_ifaces = []
        cls.child_services = {}
        if module == __name__:
            return
        sys.modules[module].helper = cls  # type: ignore[attr-defined]

    @classmethod
    def _setup(cls) -> None:
        module = cls.__module__
        if module == __name__:
            return
        cls.name = module.split('.', 2)[2]
        cls.config = sls.config.get_config(module)
        cls.data = sls.data.get_data(module, defaults=cls.defaults)
        cls.iface = HelperInterface(cls)

    @classmethod
    async def collect(cls) -> bool:
        return False

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        raise NotImplementedError

    @classmethod
    def enabled(cls) -> bool:
        return cls.config.get('enable', 'on') == 'on'

    @classmethod
    def enable(cls, enabled: bool, /) -> None:
        cls.config['enable'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'Enabled': enabled})

    @classmethod
    def collect_enabled(cls) -> bool:
        return cls.config.get('collect', 'on') == 'on'

    @classmethod
    def enable_collect(cls, enabled: bool, /) -> None:
        cls.config['collect'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'CollectEnabled': enabled})

    @classmethod
    def submit_enabled(cls) -> bool:
        return cls.config.get('submit', 'on') == 'on'

    @classmethod
    def enable_submit(cls, enabled: bool, /) -> None:
        cls.config['submit'] = 'on' if enabled else 'off'
        if cls.iface:
            cls.iface.emit_properties_changed({'SubmitEnabled': enabled})

    @classmethod
    def lock(cls) -> sls.lockfile.Lockfile:
        return sls.lockfile.Lockfile(f'{sls.pending}/{cls.name}/.lock')

    @classmethod
    def filter_log(cls, fname: str) -> bool:
        if fname.startswith('.'):
            return False
        _, ext = os.path.splitext(os.path.basename(fname))
        if cls.valid_extensions and ext not in cls.valid_extensions:
            return False
        return True

    @classmethod
    def list_pending(cls) -> Iterable[str]:
        try:
            return (log for log in os.listdir(f'{sls.pending}/{cls.name}') if cls.filter_log(log))
        except OSError as e:
            cls.logger.error(f'Encountered error listing logs for {cls.name}', exc_info=e)
            return ()


def create_helper(category: str) -> Optional[Helper]:
    try:
        helper = importlib.import_module(f'steamos_log_submitter.helpers.{category}')
    except ModuleNotFoundError:
        logger.error('Helper module not found')
        return None
    if not hasattr(helper, 'helper'):
        logger.error('Helper module does not contain helper class')
        return None
    helper.helper._setup()
    assert issubclass(helper.helper, Helper)
    return typing.cast(Helper, helper.helper)


def list_helpers() -> Iterable[str]:
    return (helper.name for helper in pkgutil.iter_modules(__path__))


def validate_helpers(helpers: Iterable[str]) -> tuple[list[str], list[str]]:
    all_helpers = set(list_helpers())
    requested_helpers = set(helpers)
    invalid_helpers = requested_helpers - all_helpers
    valid_helpers = requested_helpers & all_helpers
    return sorted(valid_helpers), sorted(invalid_helpers)


class StagingFile:
    def __init__(self, category: str, name: str, mode: str = 'w+b'):
        self._final_name = f'{sls.pending}/{category}/{name}'
        self._tempfile = tempfile.NamedTemporaryFile(mode=mode, dir=f'{sls.pending}/{category}', prefix='.staging-', delete=False)

    def close(self) -> None:
        self._tempfile.close()
        os.rename(self.name, self._final_name)

    def __getattr__(self, attr: str) -> Any:  # type: ignore[misc]
        return getattr(self._tempfile, attr)

    def __enter__(self) -> 'StagingFile':
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]) -> bool:
        self.close()
        return not exc_type
