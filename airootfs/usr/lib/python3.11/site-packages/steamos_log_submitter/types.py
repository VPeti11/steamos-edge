# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
from collections.abc import Mapping, Sequence
from typing import Optional, Protocol, TypeAlias, TypeVar, Union

DBusEncodable: TypeAlias = Sequence['DBusEncodable'] | Mapping[Union[str, int], 'DBusEncodable'] | Mapping[str, 'DBusEncodable'] | Mapping[int, 'DBusEncodable'] | tuple['DBusEncodable', ...] | bool | float | int | str
DBusCallable: TypeAlias = Union['DBusCallableAsync', 'DBusCallableSync']
JSON: TypeAlias = list['JSON'] | dict[str, 'JSON'] | bool | float | int | str | None
JSONEncodable: TypeAlias = Sequence['JSONEncodable'] | Mapping[str, 'JSONEncodable'] | JSON

DBusT = TypeVar('DBusT', bound=Optional[DBusEncodable])


class DBusCallableAsync(Protocol):  # pragma: no cover
    async def __call__(*args: DBusEncodable) -> Optional[DBusEncodable]: ...


class DBusCallableSync(Protocol):  # pragma: no cover
    def __call__(*args: DBusEncodable) -> Optional[DBusEncodable]: ...
