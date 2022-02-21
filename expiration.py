#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright 2021 WoozyMasta <woozy.masta@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import json
import re
import os
import requests
import yaml
import click
from time import time
from datetime import datetime, timedelta
from requests.exceptions import HTTPError
from urllib.parse import urljoin
from dotenv import load_dotenv
from columnar import columnar

quay = {}
seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def request_get(path) -> json:
    headers = {
        'Authorization': f'Bearer {quay["token"]}',
        'accept': 'application/json'
    }

    try:
        response = requests.get(urljoin(quay['url'], path), headers=headers)
        response.raise_for_status()
        return response.json()

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')


def request_put(path, data) -> json:
    headers = {
        'Authorization': f'Bearer {quay["token"]}',
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.put(
            urljoin(quay['url'], path), json=data, headers=headers)
        response.raise_for_status()
        return response.json()

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')


def bool_env(env: str, default: bool = False) -> bool:
    return os.environ.get(env, str(default)).lower() in ("yes", "true", "1")


def append_repo(repositories=[]) -> list:
    repositories_list = []
    for repo in repositories:
        if repo['kind'] == 'image':
            repositories_list.append(f'{repo["namespace"]}/{repo["name"]}')
    return repositories_list


def get_repositories(limit=1000) -> list:
    path = '/api/v1/repository?public=true'

    responce = request_get(path)
    repositories = append_repo(responce['repositories'])

    if 'next_page' in responce:
        for _ in range(limit):
            responce = request_get(f'{path}&next_page={responce["next_page"]}')
            repositories += append_repo(responce["repositories"])

            if not 'next_page' in responce:
                return repositories
    else:
        return repositories


def get_expiration_date(seconds) -> str:
    date = datetime.now() + timedelta(seconds=seconds)
    return date.astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")


def put_expiration(repository, tag, expiration=0):
    data = {
        'expiration': expiration
    }

    request_put(f'/api/v1/repository/{repository}/tag/{tag}', data)


def tags_expiration(repo):
    tags = []

    # Get images and tags in repository
    path = f'/api/v1/repository/{repo}?includeTags=true'
    responce = request_get(path)

    if not responce['tags']:
        tags.append([repo, '-', '-', click.style('BLANK', fg='magenta'), '-'])
        return tags

    for tag, values in responce['tags'].items():
        expire_state = expire_sec = expire_date = None

        # Skip get tags for exclude repo
        if repo in quay['excludes']:
            expire_state = click.style('skip', fg='blue')
            expire_sec = 0
            expire_date = click.style('0', fg='blue')

        # Image expiration exist in registry
        elif 'expiration' in values:
            expire_state = click.style('exist', fg='green')
            expire_sec = 0
            expire_date = click.style(values['expiration'], fg='green')

        # Check expiration by regex rules
        else:
            for rule in quay['expire']:
                pattern = re.compile(rule['regex'])
                if pattern.match(tag):
                    expire_sec = to_seconds(rule['expire'])
                    if expire_sec <= 0:
                        expire_state = click.style(rule['name'], fg='cyan')
                        expire_date = click.style('0', fg='cyan')
                    else:
                        expire_state = click.style(rule['name'], fg='yellow')
                        date = get_expiration_date(expire_sec)
                        expire_date = click.style(date, fg='yellow')
                    continue

            # Set default expiration
            if expire_sec is None:
                expire_state = click.style('expire', fg='red')
                expire_sec = to_seconds(quay['defexpire'])
                date = get_expiration_date(expire_sec)
                expire_date = click.style(date, fg='red')

        if expire_sec > 0:
            if not quay['dry_run']:
                put_expiration(repo, tag, int(time()) + expire_sec)

            tags.append([
                repo, tag[:18], expire_state,
                click.style('CHANGED', fg='green'), expire_date
            ])
        else:
            tags.append([
                repo, tag[:18], expire_state,
                click.style('SKIP', fg='blue'), expire_date
            ])

    return tags


def read_config():
    global quay
    basedir = os.path.abspath(os.path.dirname(__file__))
    env_file = os.path.join(basedir, '.env')

    if os.path.isfile(env_file):
        load_dotenv(env_file)

    cfg_file = os.path.join(basedir, 'config.yml')

    if os.path.isfile(cfg_file):
        with open(cfg_file, 'r') as f:
            config = yaml.safe_load(f)
            qcfg = config.get('quay', {})

        quay['url'] = os.environ.get('QUAY_URL', qcfg.get('url', None))
        quay['token'] = os.environ.get('QUAY_TOKEN', qcfg.get('token', None))
        quay['dry_run'] = bool_env('QUAY_DRY_RUN', qcfg.get('dry_run', False))
        quay['defexpire'] = os.environ.get(
            'QUAY_IMAGE_EXPIRE', qcfg.get('default_expiration', '336h'))
        quay['excludes'] = qcfg.get('exclude_projects', [])
        quay['expire'] = qcfg.get('expiration', [])

        if quay['dry_run']:
            print(click.style(
                'Run in dry run mode, do not change anything.',
                fg='yellow', bold=True, underline=True))

    if not quay['url'] and not quay['token']:
        try:
            raise SystemExit('Quay URL and token not set!')
        except:
            print("Program is still open. Kill me!")


def to_seconds(s):
    if s.isdigit():
        return int(s)
    else:
        return int(s[:-1]) * seconds_per_unit[s[-1]]


def main():
    print('Read configuration from config.yml')
    read_config()

    print('Collect repositories from {}'.format(quay["url"]))
    repositories = get_repositories()

    print('Change tag expiration for images in {} repositories'.format(
        len(repositories)))
    expirations = []
    with click.progressbar(repositories) as items:
        for repo in items:
            expirations += tags_expiration(repo)

    headers = ['image', 'tag', 'rule', 'status', 'expire date']
    select = ['image', 'tag', 'rule', 'status']
    table = columnar(expirations, headers, select=select, no_borders=True)
    print(table)

    count = 0
    for i in expirations:
        if i[3] == click.style('CHANGED', fg='green'):
            count += 1
    print('{} Changed {} tags expiration of {} tags in {} repositories'.format(
        click.style('Done.', fg='green', bold=True),
        count, len(expirations), len(repositories)))

if __name__ == '__main__':
    main()
