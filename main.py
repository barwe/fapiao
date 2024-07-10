import os
import sys
from typing import Sequence
from argparse import ArgumentParser
from prettytable import PrettyTable

import cache
from extractor import Extractor


COLUMNS = [
    # {"key": "file", "label": "文件", "shown": True},
    {"key": "relpath", "label": "文件", "shown": True},
    {"key": "type", "label": "发票类型", "shown": True},
    # {"key": "code", "label": "发票代码", "shown": True},
    # {"key": "number", "label": "发票号码", "shown": True},
    {"key": "uid", "label": "Code/Number", "shown": True},
    {"key": "date", "label": "开票日期", "shown": True},
    {"key": "total", "label": "价税合计", "shown": True},
    {"key": "buyer", "label": "购买方", "shown": True},
    {"key": "buyer_id", "label": "购买方代码", "shown": False},
    {"key": "seller", "label": "销售方", "shown": False},
    {"key": "seller_id", "label": "销售方代码", "shown": False},
]


def getk(ks, k):
    a = [i for i in ks if k in i]
    if len(a) != 1:
        raise ValueError(k)
    return a[0]


def query(data, conds):
    for cond in conds:
        if "~" in cond:
            k, v = cond.split("~", 1)
            if v in data[k]:
                return True
        if "=" in cond:
            k, v = cond.split("=", 1)
            if isinstance(data[k], int):
                if int(v) == data[k]:
                    return True
            elif isinstance(data[k], float):
                if round(float(v), 2) == round(data[k], 2):
                    return True
            else:
                if v == data[k]:
                    return True

    return False


def rename(record, args):
    if args.rename:
        srcfile = record["path"]
        destdir = os.path.dirname(srcfile)
        newname = args.rename_format.format(**record)
        destfile = os.path.join(destdir, newname + ".pdf")
        if destfile != srcfile:
            os.rename(srcfile, destfile)


def listfiles(target_dir):
    filepaths = []
    for dirpath, _, filenames in os.walk(target_dir):
        for filename in filenames:
            if filename.endswith(".pdf"):
                filepath = os.path.join(dirpath, filename)
                filepaths.append(filepath)
    return filepaths


def extract_info(*args, **kwargs):
    with Extractor(*args, **kwargs) as extractor:
        info = extractor.parse()
    return info


def main(args):
    target_dir: str = args.target_dir
    conds: Sequence[str] = args.query
    sort_key: str = args.sort_key
    remake_cache: bool = args.remake_cache

    total = 0
    numbers = set()
    records = []

    cached_data = cache.read(target_dir)

    current_relpath_set = set()
    for filepath in listfiles(target_dir):
        relpath = os.path.relpath(filepath, target_dir)
        current_relpath_set.add(relpath)

        if remake_cache is False and relpath in cached_data:
            info = cached_data[relpath]
        else:
            info = extract_info(filepath)
            info["relpath"] = relpath
            cached_data[relpath] = info

        if conds and not query(info, conds):
            continue

        if info["number"] in numbers:
            print(f"重复的发票: {filepath}")
        else:
            numbers.add(info["number"])

        total += info["total"]
        records.append(info)

    # remove keys which related files have been deleted
    for k in list(cached_data.keys()):
        if k not in current_relpath_set:
            del cached_data[k]
    cache.write(target_dir, cached_data)

    # sort
    if sort_key:
        is_desc = False
        if sort_key.endswith("-"):
            is_desc = True
            sort_key = sort_key[:-1]
        records = sorted(records, key=lambda d: d[sort_key])
        if is_desc:
            records = records[::-1]

    # table rows
    rows = []
    keys = args.keys or [d["key"] for d in COLUMNS if d["shown"]]
    for record in records:
        rows.append([record.get(k, "--错误--") or "" for k in keys])
        rename(record, args)

    #
    if args.show_zh:
        qd = {d["key"]: d for d in COLUMNS}
        table = PrettyTable([qd[k]["label"] + f"({k})" for k in keys])
    else:
        table = PrettyTable(keys)
    table.add_rows(rows)

    print(table)
    print(f"总计: {round(total,2)}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("target_dir", help="统计该目录下的所有发票文件（pdf 文件，扫描文件不能识别）")
    parser.add_argument("-k", "--keys", nargs="+", dest="keys", help="打印列")
    parser.add_argument("-q", "--query", nargs="+", dest="query", help="过滤，例如 '-q buyer~深圳 type=1'")
    parser.add_argument("-s", "--sort", dest="sort_key", help="排序，例如 '-s date' 表示从小到大，'-s date-' 表示从大到小")
    parser.add_argument("-z", "--show-zh", action="store_true", dest="show_zh", help="打印列显示中文名称")
    parser.add_argument("--rename", dest="rename", action="store_true", help="重命名文件")
    parser.add_argument("--rename-format", dest="rename_format", default="{buyer}-{date}-{uid}-{total}", help="文件重命名格式（默认为 '{buyer}-{date}-{uid}-{total}'）")
    parser.add_argument("--remake-cache", dest="remake_cache", action="store_true", help="重新生成缓存")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        main(args)
