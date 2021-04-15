import logging
import re

import maigret
from maigret.result import QueryStatus
from maigret.sites import MaigretDatabase
from aiogram import Bot, Dispatcher, executor, types

API_TOKEN = os.getenv('API_TOKEN')

MAIGRET_DB_URL = 'https://raw.githubusercontent.com/soxoj/maigret/main/maigret/resources/data.json'
USERNAME_REGEXP = r'^[a-zA-Z0-9-_\.]{5,}$'
ADMIN_USERNAME = '@soxoj'

# top popular sites from the Maigret database
TOP_SITES_COUNT = 1500
# Maigret HTTP requests timeout
TIMEOUT = 30

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


def setup_logger(log_level, name):
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    return logger


async def maigret_search(username):
    """
        Main Maigret search function
    """
    logger = setup_logger(logging.WARNING, 'maigret')

    db = MaigretDatabase().load_from_url(MAIGRET_DB_URL)

    sites = db.ranked_sites_dict(top=TOP_SITES_COUNT)

    results = await maigret.search(username=username,
                                   site_dict=sites,
                                   timeout=TIMEOUT,
                                   logger=logger,
                                   )
    return results


async def merge_sites_into_messages(found_sites):
    """
        Join links to found accounts and make telegram messages list
    """
    if not found_sites:
        return ['No accounts found!']

    found_accounts = len(found_sites)
    found_sites_messages = []
    found_sites_entry = found_sites[0]

    for i in range(len(found_sites) - 1):
        found_sites_entry = ', '.join([found_sites_entry, found_sites[i + 1]])

        if len(found_sites_entry) >= 4096:
            found_sites_messages.append(found_sites_entry)
            found_sites_entry = ''

    if found_sites_entry != '':
        found_sites_messages.append(found_sites_entry)

    output_messages = [f'{found_accounts} accounts found:\n{found_sites_messages[0]}'] + found_sites_messages[1:]
    return output_messages


async def search(username):
    """
        Do Maigret search on a chosen username
        :return:
            - list of telegram messages
            - list of dicts with found results data
    """
    try:
        results = await maigret_search(username)
    except Exception as e:
        logging.error(e)
        return ['An error occurred, send username once again.'], []

    found_exact_accounts = []

    for site, data in results.items():
        if data['status'].status != QueryStatus.CLAIMED:
            continue
        url = data['url_user']
        account_link = f'[{site}]({url})'

        # filter inaccurate results
        if not data.get('is_similar'):
            found_exact_accounts.append(account_link)

    if not found_exact_accounts:
        return [], []

    messages = await merge_sites_into_messages(found_exact_accounts)

    # full found results data
    results = list(filter(lambda x: x['status'].status == QueryStatus.CLAIMED, list(results.values())))

    return messages, results

@dp.message_handler()
async def echo(message: types.Message):       
        # checking for username format
        msg = message.text.lstrip('@')
        username_regexp = re.search(USERNAME_REGEXP, msg)
        
        if not username_regexp:
                bot_logger.warning('Too short username!')
                await message.reply('Username must be more than 4 characters '
                                  'and can only consist of Latin letters, '
                                  'numbers, minus and underscore.')
                return

        bot_logger.info(f'Started a search by username {msg}.')
        await message.reply(f'Searching by username `{msg}`...')

        # call Maigret
        output_messages, sites = await search(msg)
        bot_logger.info(f'Completed: {len(sites)} sites/results and {len(output_messages)} text messages.')

        if not output_messages:
            pass
            await message.reply('No accounts found!')
        else:
            for output_message in output_messages:
                try:
                    await message.reply(output_message, parse_mode='MARKDOWN')
                except Exception as e:
                        bot_logger.error(e, exc_info=True)
                        await message.reply('Unexpected error has been occurred. '
                                          f'Write a message {ADMIN_USERNAME}, he will fix it.')

if __name__ == '__main__':
    logging.basicConfig(
        format='[%(filename)s:%(lineno)d] %(levelname)-3s  %(asctime)s      %(message)s',
        datefmt='%H:%M:%S',
        level=logging.WARNING,
    )

    bot_logger = setup_logger(logging.INFO, 'maigret-bot')
    bot_logger.info('I am started.')
    
    executor.start_polling(dp, skip_updates=False)
