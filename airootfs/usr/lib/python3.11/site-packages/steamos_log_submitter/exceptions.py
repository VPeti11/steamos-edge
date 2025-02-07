# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.types import JSONEncodable
from typing import ClassVar, Optional, Self, Type


class Error(RuntimeError):
    map: ClassVar[dict[str, Type[Self]]] = {}
    name: ClassVar[str]

    @classmethod
    def __init_subclass__(cls) -> None:
        cls.name = f'{DBUS_NAME}.{cls.__name__}'
        cls.map[cls.__name__] = cls
        cls.map[cls.name] = cls

    def __init__(self, data: Optional[JSONEncodable] = None):
        if data:
            super().__init__(data)
        else:
            super().__init__()
        self.data = data


class UnknownError(Error):
    pass


class InvalidArgumentsError(Error):
    pass


class LockHeldError(Error):
    pass


class LockNotHeldError(Error):
    pass


class RateLimitingError(Error):
    pass
