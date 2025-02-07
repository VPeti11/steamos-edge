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

# Needed to support list annotation for Python 3.7, without using the
# deprecated "typing.List".
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Union, Any

from steamosatomupd.image import Image


@dataclass
class UpdateCandidate:
    """An update candidate

    An update candidate is simply an image with an update path.
    """

    image: Image
    update_path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpdateCandidate:
        """Create an UpdateCandidate from a dictionary

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        image = Image.from_dict(data['image'])
        update_path = data['update_path']
        return cls(image, update_path)

    def to_dict(self) -> dict[str, Any]:
        """Export an UpdateCandidate to a dictionary"""

        return {'image': self.image.to_dict(), 'update_path': self.update_path}

    def __repr__(self) -> str:
        return "{}, {}".format(self.image, self.update_path)


class UpdatePath:

    """An update path

    An update path is a list of update candidates, sorted. It's created for
    a particular image, and it represents all the updates that this image
    should apply in order to be up-to-date.

    An update path can be imported/exported as a dictionary:

      {
        'release': 'clockwerk',
        'candidates': [ CANDIDATE1, CANDIDATE2, ... ]
      }
    """

    def __init__(self, release: str, candidates: list[UpdateCandidate]):
        self.release = release
        self.candidates = []

        if not candidates:
            return

        self.candidates = sorted(candidates, key=lambda c: c.image)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UpdatePath:
        """Create an UpdatePath from a dictionary

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        release = data['release']
        candidates = []

        for cdata in data['candidates']:
            candidate = UpdateCandidate.from_dict(cdata)
            candidates.append(candidate)

        return cls(release, candidates)

    def to_dict(self) -> dict[str, Any]:
        """Export an UpdatePath to a dictionary"""

        array = []
        for candidate in self.candidates:
            cdata = candidate.to_dict()
            array.append(cdata)

        return {'release': self.release, 'candidates': array}


@dataclass
class Update:
    """An update

    An update lists the update paths possible for an image. It's just
    made of two update paths, both optionals:
    - minor, for updates available within the same release
    - major, for updates available in the next release

    An update file can be imported/exported as a dictionary:

      {
        'minor': { UPDATE_PATH },
        'major': { UPDATE_PATH },
      }
    """

    minor: Union[UpdatePath, None]
    major: Union[UpdatePath, None]

    @classmethod
    def from_dict(cls, data) -> Update:
        """Create an Update from a dictionary

        Raise exceptions if the dictionary doesn't contain the expected keys,
        or if values are not valid.
        """

        minor: UpdatePath | None = None
        if 'minor' in data:
            minor = UpdatePath.from_dict(data['minor'])

        major: UpdatePath | None = None
        if 'major' in data:
            major = UpdatePath.from_dict(data['major'])

        return cls(minor, major)

    def to_dict(self) -> dict[str, Any]:
        """Export an Update to a dictionary"""

        data = {}
        if self.minor:
            data['minor'] = self.minor.to_dict()
        if self.major:
            data['major'] = self.major.to_dict()

        return data

    def to_string(self) -> str:
        """Export an Update to string"""

        data = self.to_dict()
        return json.dumps(data, indent=2)
