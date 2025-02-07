# SPDX-License-Identifier: LGPL-2.1+
#
# Copyright © 2018-2019 Collabora Ltd
#
# This package is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This package is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this package.  If not, see
# <http://www.gnu.org/licenses/>.

# Needed until PEP 563 string-based annotations is not enabled by default
# (scheduled for Python 3.11)
from __future__ import annotations

import datetime
import logging
import platform
import re
import urllib.parse
from dataclasses import dataclass, asdict
from typing import Any

import semantic_version

log = logging.getLogger(__name__)

def _load_os_release():
    """Load /etc/os-release in a dictionary"""

    envre = re.compile(r'''^([^\s=]+)=(?:[\s"']*)(.+?)(?:[\s"']*)$''')
    data = {}

    with open('/etc/os-release', encoding='utf-8') as f:
        for line in f:
            match = envre.match(line)
            if match is not None:
                data[match.group(1)] = match.group(2)

    return data


@dataclass
class BuildId:

    """A build ID"""

    date: datetime.date
    incr: int

    @classmethod
    def from_string(cls, text: str) -> BuildId:
        """Create a BuildId from a string containing the date and the increment.

        The date is expected to be ISO-8601, basic format. The increment is separated
        from the date by a dot, and is optional. It's set to zero if missing.

        Examples: 20181105, 20190211.1
        """

        incr = 0

        fields = text.split('.')

        if len(fields) > 2:
            raise ValueError("the version string should match YYYYMMDD[.N]")
        if len(fields) > 1:
            incr = int(fields[1])
            if incr < 0:
                raise ValueError("the increment should be positive")
        # Parse date, raise ValueError if need be
        date = datetime.datetime.strptime(fields[0], '%Y%m%d').date()

        return cls(date, incr)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BuildId):
            return NotImplemented
        return (self.date, self.incr) == (other.date, other.incr)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, BuildId):
            return NotImplemented
        return not self == other

    def __lt__(self, other: BuildId) -> bool:
        return (self.date, self.incr) < (other.date, other.incr)

    def __le__(self, other: BuildId) -> bool:
        return (self.date, self.incr) <= (other.date, other.incr)

    def __gt__(self, other: BuildId) -> bool:
        return (self.date, self.incr) > (other.date, other.incr)

    def __ge__(self, other: BuildId) -> bool:
        return (self.date, self.incr) >= (other.date, other.incr)

    def __repr__(self) -> str:
        return "{}.{}".format(self.date.strftime('%Y%m%d'), self.incr)

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class Image:
    """An OS image"""

    product: str
    release: str
    variant: str
    arch: str
    version: semantic_version.Version
    buildid: BuildId
    checkpoint: bool
    estimated_size: int
    skip: bool

    @classmethod
    def from_values(cls, product: str, release: str, variant: str, arch: str,
                    version_str: str, buildid_str: str, checkpoint: bool,
                    estimated_size: int, skip: bool) -> Image:
        """Create an Image from mandatory values

        This method performs mandatory conversions and sanity checks before
        feeding the values to the constructor. Every other classmethod
        constructors should call it.
        """

        # Parse version, raise ValueError if need be
        if version_str == 'snapshot':
            version = None
        else:
            # https://github.com/rbarrois/python-semanticversion/issues/29
            version = semantic_version.Version.coerce(version_str)

        # Parse buildid, raise ValueError if need be
        buildid = BuildId.from_string(buildid_str)

        # Tweak architecture a bit
        if arch == 'x86_64':
            arch = 'amd64'

        # Return an instance
        return cls(product, release, variant, arch, version, buildid, checkpoint, estimated_size, skip)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Image:
        """Create an Image from a dictionary.

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        # Create a shallow copy because we don't want to edit the original dictionary
        data_copy = data.copy()

        # Get mandatory fields, raise KeyError if need be
        product = data_copy.pop('product')
        release = data_copy.pop('release')
        variant = data_copy.pop('variant')
        arch = data_copy.pop('arch')
        version_str = data_copy.pop('version')
        buildid_str = data_copy.pop('buildid')

        # Get optional fields
        checkpoint = data_copy.pop('checkpoint', False)
        estimated_size = data_copy.pop('estimated_size', 0)
        skip = data_copy.pop('skip', False)

        if len(data_copy) > 0:
            log.warning('The image manifest has some unknown key-values: %s', data_copy)

        # Return an instance
        return cls.from_values(product, release, variant, arch,
                               version_str, buildid_str, checkpoint,
                               estimated_size, skip)

    @classmethod
    def from_os(cls, product='', release='', variant='', arch='',
                version_str='', buildid_str='', checkpoint=False,
                estimated_size: int = 0, skip=False) -> Image:
        """Create an Image with parameters, use running OS for defaults.

        All arguments are optional, and default values are taken by inspecting the
        current system. The os-release file provides for most of the default values.

        'checkpoint' does not exist in any standard place, hence it's assumed to be
        false if it's not provided. Note that os-release allows custom additional
        fields (and recommends to use some kind of namespacing), so we could look for
        'checkpoint' in a custom field named ${PRODUCT}_CHECKPOINT, for example.

        If a value is not specified and can't be found in the os-release, we raise
        a RuntimeError exception.
        """

        # Load the os-release file
        osrel = _load_os_release()

        # All these parameters are mandatory. If they're not specified, they
        # must have a default value in the os-release file.
        try:
            if not product:
                product = osrel['ID']
            if not release:
                release = osrel['VERSION_CODENAME']
            if not variant:
                variant = osrel['VARIANT_ID']
            if not version_str:
                version_str = osrel['VERSION_ID']
            if not buildid_str:
                buildid_str = osrel['BUILD_ID']
        except KeyError as e:
            raise RuntimeError("Missing key in os-release") from e

        # Arch comes from the platform
        if not arch:
            arch = platform.machine()

        # Return an instance, might raise exceptions
        return cls.from_values(product, release, variant, arch,
                               version_str, buildid_str, checkpoint,
                               estimated_size, skip)

    def to_dict(self) -> dict[str, Any]:
        """Export an Image to a dictionary"""

        data = asdict(self)
        data['version'] = self.get_version_str()
        data['buildid'] = str(self.buildid)

        # This is an internal flag used to decide if we should propose this image as an
        # update or not. There is no need to export it in the update dictionary/JSON
        data.pop('skip')

        return data

    def get_version_str(self) -> str:
        """Get the image version as a string"""
        if self.version:
            return str(self.version)

        return 'snapshot'

    @staticmethod
    def quote(string: str) -> str:
        """Quote a string by replacing the eventual initial '.' with a '_', and then
        following the RFC 3986 Uniform Resource Identifier (URI)"""
        if string.startswith('.'):
            string = '_' + string[1:]

        return urllib.parse.quote(string.replace('/', '_'))

    def to_update_path(self) -> str:
        """Give an update path in the form of
        <product>/<arch>/<version>/<variant>/<buildid>.json """

        bits = [self.product, self.arch, self.get_version_str(),
                self.variant, str(self.buildid)]

        return '/'.join([self.quote(b) for b in bits]) + '.json'

    def is_snapshot(self) -> bool:
        """Whether an Image is a snapshot"""

        return not self.version

    def is_stable(self) -> bool:
        """Whether an Image is stable (i.e. it has a stable version)"""

        if self.version:
            return not self.version.prerelease

        return False

    def get_unique_name(self) -> str:
        """Generates a string that is unique for this image"""

        return f"{self.get_version_str()}_{self.release}_{self.buildid}"

    def should_be_skipped(self) -> bool:
        """Whether the image should be skipped and not be considered as a valid update"""

        return self.skip

    # A note regarding comparison operators.
    #
    # When comparing images, we care about version, release and buildid.
    #
    # When versions are defined for both images, we just compare it.
    #
    # When there is no version for both images, we compare releases first,
    # then build IDs. We expect releases to be strings such as 'brewmaster',
    # 'clockwerk' and so on, sorted alphabetically. It means that when we
    # compare 'brewmaster 20190201' and 'clockwerk 20180201', clockwerk is
    # higher.
    #
    # If we need to compare an image with a version against an image without,
    # we simply use the release and buildid values. This allows us to mix
    # snapshot and versioned images. This is useful, for example, when we want
    # to allow older snaphot images to update to newer versioned images.

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Image):
            return NotImplemented
        if self.version and other.version:
            return (self.version, self.release, self.buildid) == (
                other.version, other.release, other.buildid)
        return (self.release, self.buildid) == (other.release, other.buildid)

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Image):
            return NotImplemented
        return not self == other

    def __lt__(self, other: Image) -> bool:
        if self.version and other.version:
            return (self.version, self.release, self.buildid) < (
                other.version, other.release, other.buildid)
        return (self.release, self.buildid) < (other.release, other.buildid)

    def __le__(self, other: Image) -> bool:
        if self.version and other.version:
            return (self.version, self.release, self.buildid) <= (
                other.version, other.release, other.buildid)
        return (self.release, self.buildid) <= (other.release, other.buildid)

    def __gt__(self, other: Image) -> bool:
        if self.version and other.version:
            return (self.version, self.release, self.buildid) > (
                other.version, other.release, other.buildid)
        return (self.release, self.buildid) > (other.release, other.buildid)

    def __ge__(self, other: Image) -> bool:
        if self.version and other.version:
            return (self.version, self.release, self.buildid) >= (
                other.version, other.release, other.buildid)
        return (self.release, self.buildid) >= (other.release, other.buildid)

    def __repr__(self) -> str:
        return "{{ {}, {}, {}, {}, {}, {}, {} }}".format(
            self.product, self.release, self.variant, self.arch,
            self.version, self.buildid, self.checkpoint)
