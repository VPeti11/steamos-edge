# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import datetime
import gzip
import httpx
import io
import json
import logging
import typing
import urllib.parse
import uuid
from collections.abc import Iterable
from typing import IO, Optional

import steamos_log_submitter as sls
from steamos_log_submitter.types import JSONEncodable

logger = logging.getLogger(__name__)


class SentryEvent:
    def __init__(self, dsn: str):
        self._raw_envelope: Optional[io.BytesIO] = None
        self._envelope: Optional[gzip.GzipFile] = None
        self._event_id = uuid.uuid4().hex

        self._event: dict[str, JSONEncodable]
        self._sent_at: str

        self.dsn = dsn
        self.ua_string = f'SteamOS Log Submitter/{sls.__version__}'
        self.appid: Optional[int] = None
        self.attachments: list[dict[str, str | bytes]] = []
        self.exceptions: list[dict[str, JSONEncodable]] = []
        self.tags: dict[str, JSONEncodable] = {}
        self.fingerprint: Iterable[str] = ()
        self.timestamp: Optional[float] = None
        self.environment: Optional[str] = sls.steam.get_steamos_branch()
        self.message: Optional[str] = None
        self.build_id: Optional[str] = sls.util.get_build_id()

    def add_attachment(self, *attachments: dict[str, str | bytes]) -> None:
        self.attachments.extend(attachments)

    def _append_json(self, j: JSONEncodable) -> None:
        assert self._envelope
        self._envelope.write(json.dumps(j).encode())
        self._envelope.write(b'\n')

    def _append_item(self, j: JSONEncodable, item: bytes = b'') -> None:
        assert self._envelope
        self._append_json(j)
        self._envelope.write(item)
        self._envelope.write(b'\n')

    def _initialize(self) -> None:
        self._raw_envelope = io.BytesIO()
        self._envelope = gzip.GzipFile(fileobj=self._raw_envelope, mode='wb')

        self._sent_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self._event = {
            'event_id': self._event_id,
            'timestamp': self.timestamp or self._sent_at,
            'platform': 'native',
        }

    def seal(self, *, minidump: bool = False) -> None:
        self._initialize()
        assert self._envelope

        if self.build_id:
            self._event['release'] = self.build_id

        if self.message:
            self._event['message'] = self.message

        if self.environment:
            self._event['environment'] = self.environment

        tags = dict(self.tags)
        fingerprint = list(self.fingerprint)
        if self.appid is not None:
            if f'appid:{self.appid}' not in fingerprint:
                fingerprint.append(f'appid:{self.appid}')
            tags['appid'] = str(self.appid)

        user_id = sls.util.telemetry_user_id()
        if user_id:
            tags['user_id'] = user_id

        unit_id = sls.util.telemetry_unit_id()
        if unit_id:
            tags['unit_id'] = unit_id

        if tags:
            self._event['tags'] = tags
        if fingerprint:
            self._event['fingerprint'] = fingerprint

        if self.exceptions:
            self._event['exception'] = {'values': list(self.exceptions)}

        if self.attachments:
            self._append_json({
                'dsn': self.dsn,
                'event_id': self._event_id,
                'sent_at': self._sent_at,
            })

            for attachment in self.attachments:
                attachment_info: dict[str, JSONEncodable] = {
                    'type': 'attachment',
                    'length': len(attachment['data'])
                }
                if 'mime-type' in attachment:
                    attachment_info['content_type'] = attachment['mime-type']
                if 'filename' in attachment:
                    attachment_info['filename'] = attachment['filename']
                assert isinstance(attachment['data'], bytes)
                self._append_item(attachment_info, attachment['data'])

        if self._envelope.tell():
            self._envelope.close()
        else:
            self._envelope.close()
            self._envelope = None
            self._raw_envelope = None

    async def send(self) -> bool:
        self.seal()

        dsn_parsed = urllib.parse.urlparse(self.dsn)
        store_endpoint = dsn_parsed._replace(path=f'/api{dsn_parsed.path}/store/').geturl()
        envelope_endpoint = dsn_parsed._replace(path=f'/api{dsn_parsed.path}/envelope/').geturl()

        async with httpx.AsyncClient() as client:
            store_post = await client.post(store_endpoint, json=self._event, headers={
                'User-Agent': self.ua_string
            })

            if store_post.status_code != 200:
                logger.error(f'Failed to submit event: {store_post.content.decode()}')
                return False

            if self._envelope:
                assert self._raw_envelope
                envelope_post = await client.post(envelope_endpoint, content=self._raw_envelope.getvalue(), headers={
                    'Content-Type': 'application/x-sentry-envelope',
                    'Content-Encoding': 'gzip',
                    'User-Agent': self.ua_string
                })

                if envelope_post.status_code != 200:
                    logger.error(f'Failed to submit attachment: {envelope_post.content.decode()}')
                    return False

        return True


class MinidumpEvent(SentryEvent):
    def _initialize(self) -> None:
        super()._initialize()
        self._event = {}

    @classmethod
    def _flatten(cls, d: dict[str, JSONEncodable], prefix: str) -> dict[str, JSONEncodable]:
        flat: dict[str, JSONEncodable] = {}
        for key, value in d.items():
            key = f'{prefix}[{key}]'
            if isinstance(value, dict):
                flat.update(cls._flatten(typing.cast(dict[str, JSONEncodable], value), key))
            else:
                flat[key] = value
        return flat

    async def send_minidump(self, minidump: IO[bytes]) -> bool:
        self.seal()

        metadata: dict[str, JSONEncodable] = self._flatten(self._event, 'sentry')

        async with httpx.AsyncClient() as client:
            post = await client.post(self.dsn, files={'upload_file_minidump': minidump}, data=metadata)

        if post.status_code == 200:
            return True

        logger.error(f'Attempting to upload minidump failed with status {post.status_code}')
        if post.status_code == 400:
            try:
                data = post.json()
                if data.get('detail') == 'invalid minidump':
                    logger.warning('Minidump appears corrupted. Removing to avoid indefinite retrying.')
                    raise ValueError
            except json.decoder.JSONDecodeError:
                pass
        return False
