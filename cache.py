import os
import shelve
from os.path import exists, join


def get_prefix(target_dir: str):
    cached_dir = join(target_dir, ".cached")
    if not exists(cached_dir):
        os.mkdir(cached_dir)
    return join(cached_dir, "info")


def read(target_dir: str):
    data = {}
    prefix = get_prefix(target_dir)
    with shelve.open(prefix) as db:
        if "data" in db:
            data = db["data"]
    return data


def write(target_dir: str, data):
    prefix = get_prefix(target_dir)
    with shelve.open(prefix) as db:
        db["data"] = data
