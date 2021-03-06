import logging
import pprint
import sys
import time
import traceback
import _thread
from datetime import datetime

from slack_cleaner import __version__
from slack_cleaner.utils import Colors, Counter, TimeRange
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

client = WebClient()
time_range = None
args = None
pp = pprint.PrettyPrinter(indent=4)
counter = Counter()

logger = logging.getLogger('slack-cleaner')
logger.setLevel(10)

user_dict = {}


def init_user_dict():
    res = client.users_list()
    if not res['ok']:
        return
    members = res['members']

    for m in members:
        user_dict[m['id']] = m['name']


def get_id_by_name(list_dict, key_name):
    for d in list_dict:
        if d['name'] == key_name:
            return d['id']


def clean_channel(channel_id, time_range, user_id=None, bot=False):
    # Setup time range for query
    oldest = time_range.start_ts
    latest = time_range.end_ts

    _api_end_point = None
    # Set to the right API end point
    if args.channel_name or args.direct_name or args.group_name or args.mpdirect_name:
        _api_end_point = client.conversations_history

    has_more = True
    while has_more:
        res = _api_end_point(channel=channel_id, oldest=oldest, latest=latest)
        if not res['ok']:
            logger.error('Error occurred on Slack\'s API:')
            pp.pprint(res)
            sys.exit(1)

        messages = res['messages']
        has_more = res['has_more']

        if len(messages) == 0:
            print('No more messsages')
            break

        for m in messages:
            # Delete user messages
            if m['type'] == 'message':
                # If it's a normal user message
                if m.get('user'):
                    # Delete message if user_name matched or `--user=*`
                    if m.get('user') == user_id or user_id == -1:
                        delete_message_on_channel(channel_id, m)

                # Delete bot messages
                if bot and m.get('subtype') == 'bot_message':
                    delete_message_on_channel(channel_id, m)

            # Exceptions
            else:
                print('Weird message')
                pp.pprint(m)

        if args.rate_limit:
            time.sleep(args.rate_limit)


def delete_message_on_channel(channel_id, message):
    def get_user_name(m):
        if m.get('user'):
            _id = m.get('user')
            return user_dict[_id]
        elif m.get('username'):
            return m.get('username')
        else:
            return '_'

    # Actually perform the task
    if args.perform:
        try:
            # No response is a good response
            # FIXME: Why this behaviour differ from Slack's documentation?
            client.chat_delete(channel=channel_id, ts=message['ts'])
        except SlackApiError as e:
            logger.error(Colors.YELLOW + 'Failed to delete ->' + Colors.ENDC)
            if e.response.get('error') == 'ratelimited' and args.rate_limit:
                time.sleep(args.rate_limit)
            else:
                pp.pprint(message)
                traceback.print_exc()
                return
        except:
            logger.error(Colors.YELLOW + 'Failed to delete ->' + Colors.ENDC)
            pp.pprint(message)
            traceback.print_exc()
            return

        logger.warning(Colors.RED + 'Deleted message -> ' + Colors.ENDC
                       + get_user_name(message)
                       + ' : %s'
                       , message.get('text', ''))

    # Just simulate the task
    else:
        logger.warning(Colors.YELLOW + 'Will delete message -> ' + Colors.ENDC
                       + get_user_name(message)
                       + ' :  %s'
                       , message.get('text', ''))

    counter.increase()


def remove_files(time_range, user_id=None, types=None):
    # Setup time range for query
    oldest = time_range.start_ts
    latest = time_range.end_ts
    page = 1

    if user_id == -1:
        user_id = None

    has_more = True
    while has_more:
        res = client.files_list(user=user_id, ts_from=oldest, ts_to=latest,
                                types=types, page=page)

        if not res['ok']:
            logger.error('Error occurred on Slack\'s API:')
            pp.pprint(res)
            sys.exit(1)

        files = res['files']
        current_page = res['paging']['page']
        total_pages = res['paging']['pages']
        has_more = current_page < total_pages
        page = current_page + 1

        for f in files:
            # Delete user file
            delete_file(f)

        if args.rate_limit:
            time.sleep(args.rate_limit)


def delete_file(file):
    # Actually perform the task
    if args.perform:
        try:
            # No response is a good response
            client.files_delete(file['id'])
        except SlackApiError as e:
            logger.error(Colors.YELLOW + 'Failed to delete ->' + Colors.ENDC)
            if e.response.get('error') == 'ratelimited' and args.rate_limit:
                time.sleep(args.rate_limit)
            else:
                pp.pprint(file)
                traceback.print_exc()
                return
        except:
            logger.error(Colors.YELLOW + 'Failed to delete ->' + Colors.ENDC)
            pp.pprint(file)
            traceback.print_exc()
            return

        logger.warning(Colors.RED + 'Deleted file -> ' + Colors.ENDC
                       + file.get('title', ''))

    # Just simulate the task
    else:
        logger.warning(Colors.YELLOW + 'Will delete file -> ' + Colors.ENDC
                       + file.get('title', ''))

    counter.increase()


def get_user_id_by_name(name):
    for k, v in user_dict.iteritems():
        if v == name:
            return k


def get_channel_id_by_name(name):
    res = client.conversations_list(types="public_channel,private_channel")
    if not res['ok']:
        return
    channels = res['channels']
    if len(channels) > 0:
        return get_id_by_name(channels, name)


def get_direct_id_by_name(name):
    res = client.conversations_list(types="im")
    if not res['ok']:
        return
    ims = res['ims']
    if len(ims) > 0:
        _user_id = get_user_id_by_name(name)
        for i in ims:
            if i['user'] == _user_id:
                return i['id']


def get_mpdirect_id_by_name(name):
    res = client.conversations_list(types="mpim")
    # create set of user ids
    members = set([get_user_id_by_name(x) for x in name.split(',')])

    if not res['ok']:
        return

    mpims = res['groups']

    if len(mpims) > 0:
        for mpim in mpims:
            # match the mpdirect user ids
            if set(mpim['members']) == members:
                return mpim['id']


def get_group_id_by_name(name):
    res = client.conversations_list(types="private_channel")
    if not res['ok']:
        return
    groups = res['groups']
    if len(groups) > 0:
        return get_id_by_name(groups, name)


def message_cleaner():
    _channel_id = None
    _user_id = None

    # If channel's name is supplied
    if args.channel_name:
        _channel_id = get_channel_id_by_name(args.channel_name)

    # If DM's name is supplied
    if args.direct_name:
        _channel_id = get_direct_id_by_name(args.direct_name)

    # If channel's name is supplied
    if args.group_name:
        _channel_id = get_group_id_by_name(args.group_name)

    # If group DM's name is supplied
    if args.mpdirect_name:
        _channel_id = get_mpdirect_id_by_name(args.mpdirect_name)

    if _channel_id is None:
        sys.exit('Channel, direct message or private group not found')

    # If user's name is also supplied
    if args.user_name:
        # A little bit tricky here, we use -1 to indicates `--user=*`
        if args.user_name == "*":
            _user_id = -1
        else:
            _user_id = get_user_id_by_name(args.user_name)

        if _user_id is None:
            sys.exit('User not found')

    # Delete messages on certain channel
    clean_channel(_channel_id, time_range, _user_id, args.bot)


def file_cleaner():
    _user_id = None
    _types = None

    if args.user_name:
        # A little bit tricky here, we use -1 to indicates `--user=*`
        if args.user_name == "*":
            _user_id = -1
        else:
            _user_id = get_user_id_by_name(args.user_name)

        if _user_id is None:
            sys.exit('User not found')

    if args.types:
        _types = args.types

    remove_files(time_range, _user_id, _types)


def start(token, cmd_args):
    global client, time_range, args
    args = cmd_args
    client = WebClient(token=token)
    time_range = TimeRange(args.start_time, args.end_time)
    init_user_dict()
    # Log deleted messages/files if we're gonna actually log the task
    if args.log:
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        file_log_handler = logging.FileHandler('slack-cleaner.' + ts + '.log')
        logger.addHandler(file_log_handler)

    stderr_log_handler = logging.StreamHandler()
    logger.addHandler(stderr_log_handler)
    logger.info('Running slack-cleaner v' + __version__)

    if args.delete_message:
        message_cleaner()
    elif args.delete_file:
        file_cleaner()

    result = Colors.GREEN + str(counter.total) + Colors.ENDC
    if args.delete_message:
        result += ' message(s)'
    elif args.delete_file:
        result += ' file(s)'

    if not args.perform:
        result += ' will be cleaned.'
    else:
        result += ' cleaned.'

    # Print result
    logger.info('\n' + result + '\n')

    if not args.perform:
        logger.info('Now you can re-run this program with `--perform`' +
                    ' to actually perform the task.' + '\n')

    logger.info('\nPress Ctrl+C to finish')
