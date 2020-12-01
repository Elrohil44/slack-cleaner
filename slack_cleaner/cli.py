# -*- coding: utf-8 -*-
from slack_cleaner.args import Args
from slack_cleaner.oauth import obtain_token_and_run
from slack_cleaner.cleaner import start

args = Args()


def main():
    if not args.token:
        obtain_token_and_run(args)
    else:
        start(args.token, args)


if __name__ == '__main__':
    main()
