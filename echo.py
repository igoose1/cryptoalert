#!/usr/bin/env python

# Copyright 2021 Oskar Sharipov <oskarsh[at]riseup[dot]net
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#   http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys

import hjson
import requests
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
BASE_URL = "https://pro-api.coinmarketcap.com/v1/{}"

"""
Every element must be the same structure:

    sign_of_when_cell: (
        "the string used in \"currency costs {} it was expected\"",
        lambda asked, from_cap: whether_approaches(asked, from_cap)),
    )

"""
WHEN_TRANSLATER = {
    ">": ("more than", lambda asked, from_cap: from_cap > asked),
    "<": ("less than", lambda asked, from_cap: from_cap < asked),
}


def currencies():
    headers = {"Accepts": "application/json", "X-CMC_PRO_API_KEY": os.getenv("key", "")}
    session = requests.Session()
    session.headers.update(headers)

    url = BASE_URL.format("cryptocurrency/listings/latest")
    try:
        response = session.get(url)
        j = response.json()
        return j.get("data", {})
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        logging.error("Couldn't fetch currency listings: %s.", e)
        return {}


def cmp_function(s: str):
    try:
        than_what = float(s[1:])
        then_what, then_how = WHEN_TRANSLATER[s[0]]
        then_what = (
            "{symbol} costs "
            + then_what
            + " it was expected. Its current price is {price:.4f} USD."
        )
        f = lambda from_cap: then_what if then_how(than_what, from_cap) else None
        return f
    except (IndexError, ValueError, KeyError):
        logging.error('Asked "when" is a trash: "%s".', s)
        return lambda x: None


def main():
    key = os.getenv("key", None)
    if not key:
        logging.error("No key available. Set `key` environment variable.")
        return 1

    try:
        watching = hjson.load(sys.stdin)
    except hjson.scanner.HjsonDecodeError as e:
        logging.error("Invalid syntax in stdin: %s", e)
        return 1

    listings = currencies()
    if not listings:
        return 2

    functions = [None] * len(watching)
    for i, w in enumerate(watching):
        functions[i] = cmp_function(w["when"])

    for currency in listings:
        for i in range(len(watching)):
            if watching[i]["symbol"] != currency["symbol"]:
                continue
            try:
                s = functions[i](currency["quote"]["USD"]["price"])
            except ValueError:
                logging.error(
                    "Fetched currency listings are ugly. Where is the price placed?\n%s",
                    hjson.dumps(currency),
                )
                continue
            if s:
                to_echo = s.format(
                    symbol=currency["symbol"], price=currency["quote"]["USD"]["price"]
                )
                print(to_echo)


if __name__ == "__main__":
    status = main()
    if status:
        logging.info("Terminating...")
    sys.exit(status)
