import json
import os
from itertools import tee

import dateparser

BTC = "sec-z-btc-4ca670cac10139ce8678b84836231606"
ETH = "sec-z-eth-dc40261c82a191b11e53426aa25d91af"


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def json_lines(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    with open(p, "r") as f:
        for ln in f:
            yield json.loads(ln)


def to_date(thing):
    if thing:
        return dateparser.parse(thing)
