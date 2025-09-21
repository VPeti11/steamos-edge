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

import json

from steamosatomupd.image import Image


class Manifest:

    """An image manifest"""

    def __init__(self, image: Image):
        self.image = image

    @classmethod
    def from_file(cls, filename: str):
        """Create a Manifest from file

        Raise exceptions if needed
        """

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        image = Image.from_dict(data)
        return cls(image)

    def to_string(self) -> str:
        """Export a Manifest to string"""

        data = self.image.to_dict()
        return json.dumps(data, indent=2)
