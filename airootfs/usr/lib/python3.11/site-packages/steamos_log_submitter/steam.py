# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import logging
import pwd
import subprocess
import vdf  # type: ignore[import]
import steamos_log_submitter as sls
from typing import Optional

__all__ = [
    'get_deck_serial',
    'get_account_id',
    'get_account_name',
]

config = sls.config.get_config(__name__)
logger = logging.getLogger(__name__)
default_uid = 1000


def _setup() -> None:
    global default_uid
    try:
        default_uid = int(config.get('uid') or '1000')
    except ValueError:
        default_uid = 1000


def get_deck_serial(uid: int = default_uid, force_vdf: bool = False) -> Optional[str]:
    if not force_vdf:
        serial = config.get('deck_serial')
        if serial:
            return serial

    try:
        home = pwd.getpwuid(uid).pw_dir
        with open(f'{home}/.steam/root/config/config.vdf') as v:
            steamconf = vdf.load(v)
    except (OSError, SyntaxError, KeyError) as e:
        logger.warning('Could not access config VDF file', exc_info=e)
        return None

    if 'InstallConfigStore' not in steamconf:
        return None

    if 'SteamDeckRegisteredSerialNumber' not in steamconf['InstallConfigStore']:
        return None

    serial = steamconf['InstallConfigStore']['SteamDeckRegisteredSerialNumber']
    if not isinstance(serial, str):
        return None
    return serial


def get_account_id(uid: int = default_uid, force_vdf: bool = False) -> Optional[int]:
    if not force_vdf:
        userid = config.get('account_id')
        if userid:
            try:
                return int(userid)
            except ValueError:
                pass

    try:
        home = pwd.getpwuid(uid).pw_dir
        with open(f'{home}/.steam/root/config/loginusers.vdf') as v:
            loginusers = vdf.load(v)
    except (OSError, SyntaxError, KeyError) as e:
        logger.warning('Failed to read config VDF file', exc_info=e)
        return None

    if 'users' not in loginusers:
        return None

    for user, data in loginusers['users'].items():
        if data.get('MostRecent', '0') == '1':
            return int(user)
        if data.get('mostrecent', '0') == '1':
            return int(user)

    return None


def get_account_name(uid: int = default_uid, force_vdf: bool = False) -> Optional[str]:
    if not force_vdf:
        account_name = config.get('account_name')
        if account_name:
            return account_name

    try:
        home = pwd.getpwuid(uid).pw_dir
        with open(f'{home}/.steam/root/config/loginusers.vdf') as v:
            loginusers = vdf.load(v)
    except (OSError, SyntaxError, KeyError) as e:
        logger.warning('Failed to read config VDF file', exc_info=e)
        return None

    if 'users' not in loginusers:
        return None

    for data in loginusers['users'].values():
        if data.get('MostRecent', '0') == '1':
            return str(data.get('AccountName'))
        if data.get('mostrecent', '0') == '1':
            return str(data.get('AccountName'))

    return None


def get_steamos_branch() -> Optional[str]:
    try:
        result = subprocess.run(['/usr/bin/steamos-select-branch', '-c'], capture_output=True, errors='replace', check=True)
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning('Failed to read SteamOS branch', exc_info=e)
    return None
