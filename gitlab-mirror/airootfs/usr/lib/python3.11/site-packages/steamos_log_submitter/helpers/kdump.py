# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import calendar
import io
import os
import re
import time
import zipfile
from typing import Optional, TextIO
from . import Helper, HelperResult

import steamos_log_submitter as sls
from steamos_log_submitter.sentry import SentryEvent
from steamos_log_submitter.types import JSONEncodable


class KdumpHelper(Helper):
    valid_extensions = frozenset({'.zip'})

    @classmethod
    def get_summaries(cls, dmesg: TextIO) -> tuple[str, list[dict[str, JSONEncodable]]]:
        crash_summary_list: list[str] = []
        call_trace_list: list[str] = []
        call_trace_grab = False

        # Extract only the lines between "Kernel panic -" and
        # "Kernel Offset:" / "Sending NMI" into the crash summary, and
        # the subset of those lines after " <TASK>" and until the " </TASK>"
        # into the call trace log - notice we remove the useless lines
        # like "Call Trace / <TASK>" and "Sending NMI / Kernel Offset".
        for line in dmesg:
            if crash_summary_list or 'Kernel panic -' in line:
                crash_summary_list.append(line)

                if call_trace_grab:
                    call_trace_list.append(line)
                    if ' </TASK>' in line:
                        call_trace_grab = False
                elif ' <TASK>' in line:
                    call_trace_grab = True

                if 'Kernel Offset:' in line or 'Sending NMI' in line:
                    crash_summary_list.pop()
                    break

        crash_summary = ''.join(crash_summary_list)

        call_trace: list[dict[str, JSONEncodable]] = []
        if call_trace_list:
            call_trace = cls.parse_traces(call_trace_list[0:-1])
        return crash_summary, call_trace

    @classmethod
    def parse_traces(cls, log: list[str]) -> list[dict[str, JSONEncodable]]:
        strip_re = re.compile(r'^(?:<\d>)?\[\d+\.\d+\] ')
        frame_re = re.compile(r'(?P<symbol>[_a-zA-Z][_a-zA-Z0-9]*)\+(?P<offset>0x[0-9a-f]+)/(?P<size>0x[0-9a-f]+)(?: \[(?P<module>[_a-zA-Z0-9]+)(?: [0-9a-f]+)?\])?')
        rsp_re = re.compile(r'RSP: [0-9a-f]{4}:([0-9a-f]{16})')
        registers_re = re.compile(r'([A-Z0-9]{3}): ([0-9a-f]{16})')
        traces: list[dict[str, JSONEncodable]] = []
        frames: Optional[list[dict[str, str]]] = None
        registers: Optional[dict[str, str]] = None

        def append(frames: Optional[list[dict[str, str]]], regsiters: Optional[dict[str, str]]) -> None:
            if not frames:
                return
            frames.reverse()
            if registers:
                traces.append({
                    'frames': frames,
                    'registers': registers
                })
            else:
                traces.append({
                    'frames': frames,
                })

        for line in log:
            line = strip_re.sub('', line.strip())
            frame = frame_re.search(line)
            if line.startswith('RIP: '):
                append(frames, registers)
                frames = None
                registers = None

            if frame:
                frame_info = {
                    'function': frame.group('symbol'),
                    'instruction_addr': frame.group('offset'),
                    'addr_mode': 'rel'
                }
                if frame.group('module'):
                    frame_info['package'] = frame.group('module')

                if not frames:
                    frames = []
                frames.append(frame_info)
                continue

            rsp = rsp_re.search(line)
            if rsp:
                if not registers:
                    registers = {}
                registers['rsp'] = "0x" + rsp.group(1)
                continue

            registers_matches = registers_re.findall(line)
            if registers_matches:
                if not registers:
                    registers = {}
                for reg, addr in registers_matches:
                    registers[reg.lower()] = "0x" + addr
                continue

        if frames:
            append(frames, registers)
        return traces

    @classmethod
    async def submit(cls, fname: str) -> HelperResult:
        name, _ = os.path.splitext(os.path.basename(fname))
        stack = None
        event = SentryEvent(cls.config['dsn'])
        try:
            with zipfile.ZipFile(fname) as f:
                for zname in f.namelist():
                    with f.open(zname) as zf:
                        data = zf.read()
                        event.add_attachment({
                            'mime-type': 'text/plain',
                            'filename': zname,
                            'data': data
                        })
                        if zname.startswith('version'):
                            event.tags['kernel'] = data.decode().strip()
                        zf.seek(0)
                        print(zname)
                        if zname.startswith('build'):
                            with io.TextIOWrapper(zf) as build:
                                event.build_id = sls.util.get_build_id(build)
                        if zname.startswith('dmesg'):
                            with io.TextIOWrapper(zf) as dmesg:
                                event.message, stack = cls.get_summaries(dmesg)
            with open(fname, 'rb') as f:
                attachment = f.read()
        except zipfile.BadZipFile:
            return HelperResult(HelperResult.PERMANENT_ERROR)
        except OSError:
            return HelperResult(HelperResult.TRANSIENT_ERROR)

        if event.message is None or stack is None:
            return HelperResult(HelperResult.PERMANENT_ERROR)

        t = time.strptime(name.split('-')[-1], '%Y%m%d%H%M')
        event.timestamp = calendar.timegm(t)
        event.add_attachment({
                'mime-type': 'application/zip',
                'filename': 'kdump.zip',
                'data': attachment
            })
        event.exceptions = [{'stacktrace': frames, 'type': 'PANIC'} for frames in stack]
        return HelperResult.check(await event.send())
