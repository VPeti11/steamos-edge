# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import collections
import dbus_next as dbus
import json
import logging
import os
import pyalsa.alsacard as alsacard  # type: ignore[import]
import pyalsa.alsacontrol as alsacontrol  # type: ignore[import]
import pyalsa.alsahcontrol as alsahcontrol  # type: ignore[import]
import re
import struct
import time
import typing
from collections.abc import Callable
from typing import Optional, Type, Union

import steamos_log_submitter as sls
import steamos_log_submitter.dbus
from steamos_log_submitter.constants import DBUS_NAME
from steamos_log_submitter.dbus import DBusObject
from steamos_log_submitter.types import JSON, JSONEncodable
from . import Helper, HelperResult


def read_file(path: str, binary: bool = False) -> Union[bytes, str, None]:
    try:
        with open(path, 'rb' if binary else 'r') as f:
            data: bytes = f.read()
            if binary:
                return data
            return data.strip()
    except FileNotFoundError:
        return None


class SysinfoType:
    logger: logging.Logger
    name: str
    version: int

    @classmethod
    def __init_subclass__(cls) -> None:
        cls.logger = SysinfoHelper.logger
        assert cls.__name__.endswith('Type')
        cls.name = cls.__name__[:-len('Type')]
        SysinfoHelper.register_type(cls)

    @classmethod
    async def list(cls) -> JSONEncodable:  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def enabled(cls) -> bool:
        return SysinfoHelper.config.get(f'{sls.util.snake_case(cls.name)}.enabled', 'on') == 'on'

    @classmethod
    def enable(cls, enabled: bool, /) -> None:
        SysinfoHelper.config[f'{sls.util.snake_case(cls.name)}.enabled'] = 'on' if enabled else 'off'
        sls.config.write_config()


class SysinfoHelper(Helper):
    version = 1
    valid_extensions = frozenset({'.json'})
    defaults = {'timestamp': None}

    device_types: dict[str, Type[SysinfoType]] = {}

    @classmethod
    def _setup(cls) -> None:
        super()._setup()
        cls.child_services = {device_type.name: SysinfoInterface(device_type) for device_type in cls.device_types.values()}

    @classmethod
    def register_type(cls, type: Type[SysinfoType]) -> None:
        cls.device_types[sls.util.snake_case(type.name)] = type

    @classmethod
    async def list(cls, type: str) -> Optional[JSONEncodable]:
        try:
            return await cls.device_types[type].list()
        except Exception as e:
            cls.logger.error(f'Failed to list {type}', exc_info=e)
        return None

    @classmethod
    async def collect(cls) -> bool:
        types = sorted(cls.device_types.items())
        results = await asyncio.gather(*[cls.list(name) for name, type in types if type.enabled()])
        devices = {type: result for type, result in zip((name for name, _ in types), results) if result is not None}
        os.makedirs(sls.data.data_root, exist_ok=True)
        known = {}
        try:
            with open(f'{sls.data.data_root}/sysinfo-pending.json') as f:
                known = json.load(f)
        except FileNotFoundError:
            pass
        except json.decoder.JSONDecodeError:
            cls.logger.warning('Parsing error loading cache file')

        for section in devices.keys():
            # Use an ordered dict to easily deduplicate identical entries
            # while making sure to maintain the order they were added in
            devs = collections.OrderedDict()
            if section in known:
                for dev in known[section]:
                    devs[json.dumps(dev)] = True

            value = devices[section]
            if isinstance(value, list):
                for dev in value:
                    if isinstance(dev, dict):
                        dev['_version'] = cls.device_types[section].version
                        devs[json.dumps(collections.OrderedDict(sorted(dev.items())))] = True
                    else:
                        devs[json.dumps(dev)] = True
            elif isinstance(value, dict):
                value['_version'] = cls.device_types[section].version
                devs[json.dumps(value)] = True
            known[section] = [json.loads(dev) for dev in devs.keys()]

        with open(f'{sls.data.data_root}/sysinfo-pending.json', 'w') as f:
            json.dump(known, f)

        now = time.time()
        timestamp = cls.data['timestamp']
        new_file = False
        if isinstance(timestamp, int | float):
            if now - timestamp >= float(cls.config.get('interval') or 60 * 60 * 24 * 7):
                # If last submitted over a week ago, submit now
                os.unlink(f'{sls.data.data_root}/sysinfo-pending.json')
                for name, device_type in cls.device_types.items():
                    # Filter out disabled devices
                    if not device_type.enabled() and name in known:
                        del known[name]
                with open(f'{sls.pending}/sysinfo/{now:.0f}.json', 'w') as f:
                    json.dump(known, f)
                new_file = True
        else:
            timestamp = None

        if not timestamp or new_file:
            cls.data['timestamp'] = now
            try:
                cls.data.write()
            except OSError as e:
                cls.logger.error('Failed writing updated timestamp information', exc_info=e)

        return new_file

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        raise NotImplementedError


class UsbType(SysinfoType):
    version = 1

    @classmethod
    async def list(cls) -> list[dict[str, str]]:
        usb = '/sys/bus/usb/devices'
        devices = []
        for dev in os.listdir(usb):
            if dev.startswith('usb'):
                # This is a hub/root
                continue
            vid = read_file(f'{usb}/{dev}/idVendor')
            pid = read_file(f'{usb}/{dev}/idProduct')
            if not vid or not pid:
                continue
            assert isinstance(vid, str)
            assert isinstance(pid, str)
            info = {
                'vid': vid,
                'pid': pid,
            }
            manufacturer = read_file(f'{usb}/{dev}/manufacturer')
            if manufacturer is not None:
                assert isinstance(manufacturer, str)
                info['manufacturer'] = manufacturer

            product = read_file(f'{usb}/{dev}/product')
            if product is not None:
                assert isinstance(product, str)
                info['product'] = product

            devices.append(info)
        return devices


class MonitorsType(SysinfoType):
    version = 1

    @classmethod
    def parse_display_descriptor(cls, desc: bytes) -> dict[str, str]:
        type = desc[1]
        if type not in (0xFC, 0xFE, 0xFF):
            return {'type': 'unknown'}
        value = desc[3:].decode('cp437')
        info = {'value': value.split('\n')[0]}
        if type == 0xFC:
            info['type'] = 'name'
        if type == 0xFE:
            info['type'] = 'text'
        if type == 0xFF:
            info['type'] = 'serial'
        return info

    @classmethod
    def parse_edid(cls, edid: bytes) -> Optional[dict[str, JSONEncodable]]:
        if len(edid) < 128:
            cls.logger.warning('Invalid EDID')
            return None
        info: dict[str, JSONEncodable] = {}
        magic, pnp_id, mfg_pid, serial, major, minor, \
            desc0, desc1, desc2, desc3 = \
            struct.unpack('''<q HHI xx BB xxxxx xxxxxxxxxx xxx
                             xx xx xx xx xx xx xx xx
                             Hxxxxxxxxxxxxxxxx
                             Hxxxxxxxxxxxxxxxx
                             Hxxxxxxxxxxxxxxxx
                             Hxxxxxxxxxxxxxxxx
                             xx''', edid[:128])
        if magic != 0xFFFFFFFFFFFF00:
            cls.logger.warning('Invalid EDID magic')
            return None
        pnp_id = (pnp_id >> 8) | (pnp_id << 8)
        info['pnp'] = chr(((pnp_id >> 10) & 0x1F) + 0x40) + \
            chr(((pnp_id >> 5) & 0x1F) + 0x40) + \
            chr((pnp_id & 0x1F) + 0x40)
        info['pid'] = f'{mfg_pid:04x}'
        info['serial'] = f'{serial:08x}'
        info['version'] = f'{major}.{minor}'
        info['checksum'] = (sum(edid[:128]) & 0xFF) == 0
        if not desc0:
            info['desc0'] = cls.parse_display_descriptor(edid[56:72])
        if not desc1:
            info['desc1'] = cls.parse_display_descriptor(edid[74:90])
        if not desc2:
            info['desc2'] = cls.parse_display_descriptor(edid[92:108])
        if not desc3:
            info['desc3'] = cls.parse_display_descriptor(edid[110:126])
        return info

    @classmethod
    async def list(cls) -> list[dict[str, JSONEncodable]]:
        drm = '/sys/class/drm'
        devices = []
        for dev in os.listdir(drm):
            if not re.match(r'card\d+-', dev):
                continue
            info: dict[str, JSONEncodable] = {}
            modes = read_file(f'{drm}/{dev}/modes', binary=False)
            if isinstance(modes, str):
                info['modes'] = modes.split('\n')
            edid = read_file(f'{drm}/{dev}/edid', binary=True)
            if edid:
                assert isinstance(edid, bytes)
                info['edid'] = edid.hex()
                parsed_edid = cls.parse_edid(edid)
                if parsed_edid:
                    info.update(parsed_edid)
            if info:
                devices.append(info)
        return devices


class BluetoothType(SysinfoType):
    version = 1
    bus = 'org.bluez'

    @classmethod
    async def list(cls) -> list[dict[str, JSON]]:
        bluez = DBusObject(cls.bus, '/org/bluez')
        adapters = await bluez.list_children()
        devices = []
        for adapter in adapters:
            adapter_object = DBusObject(cls.bus, adapter)
            known = await adapter_object.list_children()
            for dev in known:
                dev_object = DBusObject(cls.bus, dev)
                dev_dict = {}
                dev_bluez = dev_object.properties('org.bluez.Device1')
                conversions: list[tuple[str, Callable]] = [
                    ('Address', str),
                    ('Alias', str),
                    ('Blocked', bool),
                    ('Bonded', bool),
                    ('Class', hex),
                    ('Connected', bool),
                    ('Icon', str),
                    ('Modalias', str),
                    ('Name', str),
                    ('Paired', bool),
                    ('Trusted', bool)
                ]
                for name, convert in conversions:
                    try:
                        dev_dict[name.lower()] = convert(await dev_bluez[name])
                    except (KeyError, dbus.errors.DBusError):
                        cls.logger.debug(f'Property {name} missing on dev {dev}')
                dev_dict['adapter'] = adapter.split('/')[-1]
                devices.append(dev_dict)

        return devices


class FilesystemsType(SysinfoType):
    version = 1
    bus = 'org.freedesktop.UDisks2'

    @classmethod
    async def list(cls) -> Optional[list[dict[str, JSON]]]:
        findmnt = await asyncio.create_subprocess_exec('findmnt', '-J', '-o', 'uuid,source,target,fstype,size,options', '-b', '--real', '--list', stdout=asyncio.subprocess.PIPE)
        stdout, _ = await findmnt.communicate()
        mntinfo = json.loads(stdout.decode(errors='replace'))
        if 'filesystems' not in mntinfo:
            return None
        filesystems = []
        for fs in mntinfo['filesystems']:
            if fs['fstype'].lower().endswith('.appimage'):
                continue
            if fs['fstype'] == 'fuse.portal':
                continue
            filesystems.append(fs)
            if fs['size'] is None:
                source = fs['source']
                if not source.startswith('/dev/'):
                    cls.logger.info(f'Failed to get size of device {source}: unknown device type')
                    continue
                node = '/'.join(source.split('/')[2:])
                try:
                    block_dev = DBusObject(cls.bus, f'/org/freedesktop/UDisks2/block_devices/{node}')
                    dev_props = block_dev.properties('org.freedesktop.UDisks2.Block')
                    size = await dev_props['Size']
                    if not isinstance(size, (str, int, float)):
                        raise TypeError(type(size))
                    fs['size'] = int(size)
                except (AttributeError, TypeError, ValueError, dbus.errors.DBusError) as e:
                    cls.logger.info(f'Failed to get size of device {source}', exc_info=e)

        return None or filesystems


class SystemType(SysinfoType):
    version = 1

    @classmethod
    async def get_vram(cls) -> Optional[str]:
        vram: Optional[str] = None
        try:
            eglinfo = await asyncio.create_subprocess_exec('eglinfo', '-a', 'glcore', '-p', 'surfaceless', stdout=asyncio.subprocess.PIPE)
            assert eglinfo.stdout
            next_line = False
            while True:
                line = await eglinfo.stdout.readline()
                if not line:
                    break
                if next_line:
                    vram = line.decode().split(':')[-1].strip()
                    break
                if line.startswith(b'Memory info (GL_NVX_gpu_memory_info)'):
                    next_line = True
        except OSError as e:
            cls.logger.error('Failed to exec eglinfo', exc_info=e)
        return vram

    @classmethod
    async def get_ram(cls) -> tuple[Optional[str], Optional[str]]:
        mem: Optional[str] = None
        swap: Optional[str] = None
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        mem = line.split(':')[-1].strip()
                    elif line.startswith('SwapTotal'):
                        swap = line.split(':')[-1].strip()
                    if mem and swap:
                        break
        except OSError as e:
            cls.logger.error('Failed read meminfo', exc_info=e)
        return mem, swap

    @classmethod
    async def list(cls) -> dict[str, JSON]:
        sysinfo: dict[str, JSON] = {
            'branch': sls.steam.get_steamos_branch(),
            'release': sls.util.get_build_id(),
        }

        try:
            sysinfo['devmode'] = os.access('/usr/share/steamos/devmode-enabled', os.F_OK)
        except OSError:
            sysinfo['devmode'] = False

        vram = await cls.get_vram()
        if vram:
            sysinfo['vram'] = vram

        mem, swap = await cls.get_ram()
        if mem:
            sysinfo['mem'] = mem
        if swap:
            sysinfo['swap'] = swap

        return sysinfo


class BatteriesType(SysinfoType):
    version = 1
    bus = 'org.freedesktop.UPower'

    @classmethod
    async def list(cls) -> list[dict[str, JSON]]:
        parent = DBusObject(cls.bus, '/org/freedesktop/UPower/devices')
        children = await parent.list_children()
        devices = []
        for child in children:
            dev_object = DBusObject(cls.bus, child)
            dev_dict = {}
            dev_props = dev_object.properties('org.freedesktop.UPower.Device')
            conversions: list[tuple[str, Callable]] = [
                ('EnergyFull', float),
                ('EnergyFullDesign', float),
                ('Model', str),
                ('NativePath', str),
                ('Online', bool),
                ('Type', int),
            ]
            for name, convert in conversions:
                try:
                    dev_dict[sls.util.snake_case(name)] = convert(await dev_props[name])
                except KeyError:
                    pass
            devices.append(dev_dict)

        return devices


class NetworkType(SysinfoType):
    version = 1
    bus = 'org.freedesktop.NetworkManager'

    @classmethod
    async def list(cls) -> list[dict[str, JSON]]:
        nm_device_types = {
            0: 'unknown',
            1: 'ethernet',
            2: 'wifi',
            5: 'bt',
            6: 'olpc_mesh',
            7: 'wimax',
            8: 'modem',
            9: 'infiniband',
            10: 'bond',
            11: 'vlan',
            12: 'adsl',
            13: 'bridge',
            14: 'generic',
            15: 'team',
            16: 'tun',
            17: 'tunnel',
            18: 'macvlan',
            19: 'vxlan',
            20: 'veth',
            21: 'macsec',
            22: 'dummy',
            23: 'ppp',
            24: 'ovs_interface',
            25: 'ovs_port',
            26: 'ovs_bridge',
            27: 'wpan',
            28: '6lowpan',
            29: 'wireguard',
            30: 'wifi_p2p',
            31: 'vrf',
        }
        device_tree = DBusObject(cls.bus, '/org/freedesktop/NetworkManager/Devices')
        children = await device_tree.list_children()
        devices: list[dict[str, JSON]] = []
        for child in children:
            dev_object = DBusObject(cls.bus, child)
            dev_props = dev_object.properties('org.freedesktop.NetworkManager.Device')
            if str(await dev_props['Interface']).startswith('lo'):
                continue
            dev_type = await dev_props['DeviceType']
            assert isinstance(dev_type, int)
            dev_dict: dict[str, JSON] = {
                'device_type': nm_device_types.get(dev_type, f'unknown_{dev_type}')
            }
            conversions: list[tuple[str, Callable]] = [
                ('Interface', str),
                ('Mtu', int),
            ]
            for name, convert in conversions:
                try:
                    dev_dict[sls.util.snake_case(name)] = convert(await dev_props[name])
                except KeyError:
                    pass
            if dev_type == 1:
                # Ethernet
                eth_props = dev_object.properties('org.freedesktop.NetworkManager.Device.Wired')
                dev_dict['carrier'] = bool(await eth_props['Carrier'])
                if dev_dict['carrier']:
                    dev_dict['bitrate'] = typing.cast(int, await eth_props['Speed']) * 1000
            elif dev_type == 2:
                # Wi-Fi
                wifi_props = dev_object.properties('org.freedesktop.NetworkManager.Device.Wireless')
                dev_dict['bitrate'] = typing.cast(int, await wifi_props['Bitrate'])
                pass
            devices.append(dev_dict)
        return devices


class AudioType(SysinfoType):
    version = 1

    @classmethod
    async def list(cls) -> list[dict[str, JSONEncodable]]:
        devices: list[dict[str, JSONEncodable]] = []

        for card in alsacard.card_list():
            controls = alsacontrol.Control(f'hw:{card}').card_info()
            hctl = alsahcontrol.HControl(f'hw:{card}')

            device: dict[str, JSONEncodable] = {
                'id': controls['id'],
                'card': controls['card'],
                'name': controls['name'],
                'mixer': controls['mixername'],
            }

            devices.append(device)
            for info in hctl.list():
                if info[4] != 'Headphone Jack':
                    continue
                elem = alsahcontrol.Element(hctl, info[0])
                value = alsahcontrol.Value(elem)
                device['headphones'], = value.get_tuple(alsahcontrol.element_type['BOOLEAN'], 1)
        return devices


class SysinfoInterface(dbus.service.ServiceInterface):
    def __init__(self, device_type: Type[SysinfoType]):
        super().__init__(f'{DBUS_NAME}.Sysinfo')

        self.device_type = device_type

    @dbus.service.method()
    async def GetJson(self) -> 's':  # type: ignore[name-defined] # NOQA: F821
        return json.dumps(await self.device_type.list())

    @dbus.service.dbus_property()
    def Enabled(self) -> 'b':  # type: ignore[name-defined] # NOQA: F821
        return self.device_type.enabled()

    @Enabled.setter
    async def set_enabled(self, enable: 'b'):  # type: ignore[name-defined,no-untyped-def] # NOQA: F821
        self.device_type.enable(enable)
