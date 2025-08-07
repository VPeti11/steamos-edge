# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import json
import logging
import os
import steamos_log_submitter as sls
from typing import Optional
from steamos_log_submitter.types import JSONEncodable

datastore: dict[str, 'DataStore'] = {}
data_root: str

logger = logging.getLogger(__name__)


class DataStore:
    def __init__(self, name: str, *, defaults: Optional[dict[str, JSONEncodable]] = {}):
        self.name = name
        self._defaults: dict[str, JSONEncodable] = defaults or {}
        self._data: dict[str, JSONEncodable] = {}
        self._dirty = False

        try:
            with open(f'{data_root}/{name}.json') as f:
                self._data = json.load(f)
        except FileNotFoundError:
            pass

    def __getitem__(self, name: str) -> JSONEncodable:
        if name in self._data:
            return self._data[name]
        if name in self._defaults:
            return self._defaults[name]
        raise KeyError(name)

    def __setitem__(self, name: str, value: JSONEncodable) -> None:
        self._data[name] = value
        self._dirty = True

    def __contains__(self, name: str) -> bool:
        return name in self._data

    def get(self, name: str, default: Optional[JSONEncodable] = None) -> Optional[JSONEncodable]:
        try:
            return self[name]
        except KeyError:
            return default

    def write(self) -> None:
        if not self._dirty:
            return
        os.makedirs(data_root, mode=0o750, exist_ok=True)
        with open(f'{data_root}/{self.name}.json', 'w') as f:
            json.dump(self._data, f)
        self._dirty = False

    def add_defaults(self, defaults: dict[str, JSONEncodable]) -> None:
        self._defaults.update(defaults)


def write_all() -> None:
    os.makedirs(data_root, mode=0o750, exist_ok=True)
    for data in datastore.values():
        try:
            data.write()
        except (OSError, TypeError, RecursionError) as e:
            logger.error('Failed to write data to disk', exc_info=e)


def get_data(name: str, defaults: Optional[dict[str, JSONEncodable]] = None) -> DataStore:
    if name == 'steamos_log_submitter':
        name = 'sls'
    elif name.startswith('steamos_log_submitter.'):
        name = name.split('.', 1)[1]

    if name not in datastore:
        datastore[name] = DataStore(name, defaults=defaults)
    elif defaults:
        datastore[name].add_defaults(defaults)
    return datastore[name]


def _setup() -> None:
    global data_root
    data_root = f'{sls.base}/data'
