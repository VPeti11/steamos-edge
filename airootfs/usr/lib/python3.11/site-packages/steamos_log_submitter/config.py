# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import configparser
import logging
import pwd
from typing import Optional

import steamos_log_submitter as sls
from steamos_log_submitter.types import JSONEncodable

__all__ = [
    'get_config',
    'reload_config',
    'write_config',
]

base_config_path = '/usr/lib/steamos-log-submitter/base.cfg'
user_config_path = None

local_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
local_config_path = None

config: configparser.ConfigParser

logger = logging.getLogger(__name__)


class ConfigSection:
    def __init__(self, name: str, *, defaults: Optional[dict[str, str]] = None):
        self.name = name
        self._defaults = defaults or {}

    def __getitem__(self, name: str) -> str:
        if local_config.has_section(self.name) and local_config.has_option(self.name, name):
            return local_config.get(self.name, name)
        if config.has_section(self.name) and config.has_option(self.name, name):
            return config.get(self.name, name)
        if name in self._defaults:
            return self._defaults[name]
        raise KeyError(name)

    def __setitem__(self, name: str, value: JSONEncodable) -> None:
        if not local_config.has_section(self.name):
            local_config.add_section(self.name)
        local_config.set(self.name, name, str(value))

    def __contains__(self, name: str) -> bool:
        if local_config.has_section(self.name) and local_config.has_option(self.name, name):
            return True
        if config.has_section(self.name) and config.has_option(self.name, name):
            return True
        return False

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        try:
            return self[name]
        except KeyError:
            return default


def get_config(mod: str, defaults: Optional[dict[str, str]] = None) -> ConfigSection:
    if mod == 'steamos_log_submitter':
        return ConfigSection('sls', defaults=defaults)
    if not mod.startswith('steamos_log_submitter.'):
        raise KeyError(mod)
    return ConfigSection(mod.split('.', 1)[1], defaults=defaults)


def reload_config() -> None:
    global config
    global local_config_path
    global user_config_path
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())

    try:
        with open(base_config_path) as f:
            config.read_file(f, source=base_config_path)
    except FileNotFoundError:
        logger.warning('No config file found')

    user_config_path = None
    if config.has_section('sls'):
        if config.has_option('sls', 'user-config'):
            user_config_path = config.get('sls', 'user-config')
        elif config.has_option('sls', 'uid'):
            try:
                uid = config.get('sls', 'uid')
                user_home = pwd.getpwuid(int(uid)).pw_dir
                user_config_path = f'{user_home}/.steam/root/config/steamos-log-submitter.cfg'
            except KeyError:
                logger.error(f'Configured uid {uid} does not exist')
            except ValueError:
                logger.error(f'Configured uid {uid} is not numeric')
    if user_config_path:
        try:
            with open(user_config_path) as f:
                config.read_file(f, source=user_config_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.error("Couldn't open user configuration file")

    local_config_path = None
    if config.has_section('sls') and config.has_option('sls', 'local-config'):
        local_config_path = config.get('sls', 'local-config')
    if local_config_path is not None:
        try:
            with open(local_config_path) as f:
                local_config.read_file(f, source=local_config_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.error("Couldn't open local configuration file")


def write_config() -> None:
    if local_config_path is None:
        raise FileNotFoundError
    with open(local_config_path, 'w') as f:
        local_config.write(f)


def migrate_key(section: str, key: str) -> bool:
    if not user_config_path:
        return False
    user_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    try:
        with open(user_config_path) as f:
            user_config.read_file(f, source=user_config_path)
    except OSError:
        return False
    if not user_config.has_section(section):
        return False
    if not user_config.has_option(section, key):
        return False
    value = user_config.get(section, key)
    if not local_config.has_section(section):
        local_config.add_section(section)
    elif local_config.has_option(section, key):
        return False
    user_config.remove_option(section, key)
    local_config.set(section, key, value)
    write_config()
    with open(user_config_path, 'w') as f:
        user_config.write(f)
    return True


def upgrade() -> None:
    reload_config()
    migrations = [
        ('sls', 'enable'),
        ('steam', 'account_id'),
        ('steam', 'account_name'),
        ('steam', 'deck_serial'),
    ]
    for helper in sls.helpers.list_helpers():
        migrations.append((f'helpers.{helper}', 'enable'))

    if any([migrate_key(s, k) for s, k in migrations]):
        reload_config()


reload_config()
