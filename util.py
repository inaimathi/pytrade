import json
from itertools import tee


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def json_lines(path):
    with open(path, "r") as f:
        for ln in f:
            yield json.loads(ln)
