# SPDX-License-Identifier: LGPL-2.1-or-later
# vim:ts=4:sw=4:et
#
# Copyright (c) 2022-2023 Valve Software
# Maintainer: Vicki Pfau <vi@endrift.com>
import asyncio
import logging
import os
from collections.abc import Iterable

import steamos_log_submitter as sls
import steamos_log_submitter.helpers
from steamos_log_submitter.lockfile import LockHeldError

logger = logging.getLogger(__name__)


async def collect_category(helper: sls.helpers.Helper) -> None:
    logger.info(f'Collecting logs for {helper.name}')
    try:
        with helper.lock():
            await helper.collect()
    except LockHeldError:
        # Another process is currently working on this directory
        logger.warning(f'Lock already held trying to collect logs for {helper.name}')
    except Exception as e:
        logger.error(f'Encountered error collecting logs for {helper.name}', exc_info=e)


async def collect() -> None:
    if sls.base_config.get('collect', 'on') != 'on':
        return
    logger.info('Starting log collection')
    tasks = []
    for category in sls.helpers.list_helpers():
        helper = sls.helpers.create_helper(category)
        if not helper:
            continue

        if not helper.enabled() or not helper.collect_enabled():
            continue
        tasks.append(asyncio.create_task(collect_category(helper)))
    if tasks:
        await asyncio.wait(tasks)
    logger.info('Finished log collection')


async def submit_category(helper: sls.helpers.Helper, logs: Iterable[str]) -> None:
    try:
        with helper.lock():
            for log in logs:
                if log.startswith('.'):
                    continue
                logger.debug(f'Found log {helper.name}/{log}')
                result = await helper.submit(f'{sls.pending}/{helper.name}/{log}')
                if result.code == sls.helpers.HelperResult.OK:
                    logger.debug(f'Succeeded in submitting {helper.name}/{log}')
                    os.replace(f'{sls.pending}/{helper.name}/{log}', f'{sls.uploaded}/{helper.name}/{log}')
                else:
                    logger.warning(f'Failed to submit log {helper.name}/{log} with code {result.code}')
                if result.code == sls.helpers.HelperResult.PERMANENT_ERROR:
                    os.replace(f'{sls.pending}/{helper.name}/{log}', f'{sls.failed}/{helper.name}/{log}')
                elif result.code == sls.helpers.HelperResult.CLASS_ERROR:
                    break
    except LockHeldError:
        # Another process is currently working on this directory
        logger.warning(f'Lock already held trying to submit logs for {helper.name}')
    except Exception as e:
        logger.error(f'Encountered error submitting logs for {helper.name}', exc_info=e)


async def submit() -> None:
    if sls.base_config.get('submit', 'on') != 'on':
        return
    logger.info('Starting log submission')
    if not sls.util.check_network():
        logger.info('Network is offline, bailing out')
        return

    tasks = []
    for category in sls.helpers.list_helpers():
        helper = sls.helpers.create_helper(category)
        if not helper:
            continue

        if not helper.enabled() or not helper.submit_enabled():
            continue
        logger.info(f'Submitting logs for {category}')
        logs = helper.list_pending()

        if not logs:
            logger.info('No logs found, skipping')
            continue
        tasks.append(asyncio.create_task(submit_category(helper, logs)))
    if tasks:
        await asyncio.wait(tasks)
    logger.info('Finished log submission')


async def trigger() -> None:
    if sls.base_config['enable'] == 'on':
        logger.info('Routine collection/submission triggered')
        try:
            await collect()
        except Exception as e:
            logger.critical('Unhandled exception while collecting logs', exc_info=e)
        try:
            await submit()
        except Exception as e:
            logger.critical('Unhandled exception while submitting logs', exc_info=e)
    else:
        logger.debug('Routine collection/submission is disabled')
