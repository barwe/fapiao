import os
import re
import pdfplumber
from pdfplumber.page import Page
from functools import reduce
from collections import defaultdict


def find(obj_list, callback):
    for obj in obj_list:
        if callback(obj):
            return obj
    return None


def has_password(s):
    return re.search(r"[\d<>+-/*]{27}", s)


class Extractor(object):
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.data = {
            "path": filepath,
            "file": os.path.basename(filepath),
        }
        # declarations
        self.pdf = None  # PDF
        self.lines = None  # dict[]
        self.words = None  # dict[]
        self.item_headers = None  # str[]
        self.s1 = ""
        self.s2 = ""
        self.s3 = ""

    def __enter__(self):
        self.pdf = pdfplumber.open(self.filepath)
        self.type = self.infer_type()
        self.type_conf = self.get_type_conf(self.type)
        return self

    def __exit__(self, type, value, traceback):
        """
        - type: 异常类型，如果有异常的话，是异常的类
        - value: 异常实例，包含异常的具体信息
        - traceback: 追溯对象，记录异常发生的位置和调用栈信息
        """
        self.pdf.close()

    def get_page_lines(self, page: Page):
        lines = page.extract_text_lines()
        return self.merge_lines(lines, self.type_conf["merge_line_y_tolerance"])

    def parse(self):
        pages = self.pdf.pages
        find_header = lambda o: "税率" in o["text"]
        find_total = lambda o: "价税合计" in o["text"]
        header_tole = self.type_conf["header_line_x_tolerance"]
        total_tole = self.type_conf["total_line_x_tolerance"]

        main_lines = self.get_page_lines(pages[0])
        header_line = find(main_lines, find_header)
        assert header_line, self.filepath
        self.parse_header_line(header_line, header_tole)

        total_line = find(main_lines, find_total)
        if total_line is None:
            for page in pages[1:]:
                _lines = self.get_page_lines(page)
                total_line = find(_lines, find_total)
                if total_line:
                    break
        assert total_line, self.filepath
        self.parse_total_line(total_line, total_tole)

        for line in main_lines:
            if line["bottom"] < header_line["top"]:
                self.s1 += line["text"] + "\n"
            elif header_line["top"] < line["bottom"] < total_line["top"]:
                self.s2 += line["text"] + "\n"
            elif line["bottom"] > header_line["top"]:
                self.s3 += line["text"] + "\n"

        self.extract_common()
        getattr(self, f"extract_for_type_{self.type}")()

        return self.data

    def parse_header_line(self, line, x_tolerance: float):
        word_char_groups = self.merge_line_chars(line["chars"], x_tolerance)
        self.item_headers = [x["text"] for x in word_char_groups]

    def parse_total_line(self, line, x_tolerance: float):
        word_char_groups = self.merge_line_chars(line["chars"], x_tolerance)
        text = "".join([x["text"] for x in word_char_groups])
        mt = re.search(r"价税合计.+?大写.+?([\u4e00-\u9fa5]+).*?小写.*?([\d\.]+)", text)
        if mt:
            self.data["total_zh"] = mt.group(1)
            self.data["total"] = float(mt.group(2))
        else:
            self.log_error(f"价税合计匹配失败: {text}")

    def extract_common(self):
        # 发票号码
        if mt := re.search(r"发+票+号+码+\s*[:：]+\s*(\d+)", self.s1):
            self.data["number"] = mt.group(1)
        # 开票日期
        if mt := re.search(r"开+票+日+期+[:：]*(\d{4})年(\d{2})月(\d{2})日", self.s1):
            self.data["date"] = f"{mt.group(1)}{mt.group(2)}{mt.group(3)}"

    def extract_for_type_1(self):
        # 发票代码
        if mt := re.search(r"发票代码\s*[:：]\s*(\d+)", self.s1):
            self.data["code"] = mt.group(1)
        # 销售/购买方信息
        if mt := re.search(r"名称[:：](.*?)密?[0-9]", self.s1):
            self.data["buyer"] = mt.group(1)
        if mt := re.search(r"纳税人识别号[:：]([0-9A-Z]{18})", self.s1):
            self.data["buyer_id"] = mt.group(1)

        if rs := re.search(r"电+话+(.*)", self.s1):
            ss = rs.group(1)
            # 以27位密码结尾
            if m := re.search(r"[:：](.*)[\d<>+-/*]{27}", ss):
                self.data["buyer_contact"] = m.group(1)
            else:
                self.log_error("buyer_contact")
        else:
            self.data["buyer_contact"] = "-"

        if mt := re.search(r"名称[:：](.*?)订单号:(\d+)", self.s3):
            self.data["seller"] = mt.group(1)
            self.data["order_number"] = mt.group(2)
        if mt := re.search(r"纳+税+人+识+别+号+[:：]*([0-9A-Z]{18})", self.s3):
            self.data["seller_id"] = mt.group(1)

        if rs := re.search(r"电+话+(.*)", self.s3):
            ss = rs.group(1)
            if m := re.search(r"[:：](.*)", ss):
                self.data["seller_contact"] = m.group(1)
            else:
                self.log_error("seller_contact")
        else:
            self.data["seller_contact"] = "-"

        self.data["uid"] = self.data["code"] + self.data["number"]

    def extract_for_type_2(self):
        # 发票代码
        self.data["code"] = "-"
        self.data["order_number"] = "-"
        # 销售/购买方信息
        if mt := re.search(r"名+称+[:：]*(.*?公司).*?名+称+[:：]*(.*?公司)", self.s1):
            self.data["buyer"] = mt.group(1)
            self.data["seller"] = mt.group(2)
        if mt := re.search(r"纳+税+人+识+别+号+[:：]*([0-9A-Z]{18}).*?纳+税+人+识+别+号+[:：]*([0-9A-Z]{18})", self.s1):
            self.data["buyer_id"] = mt.group(1)
            self.data["seller_id"] = mt.group(1)

        self.data["uid"] = self.data["number"]

    # 发票类型
    def infer_type(self) -> int:
        for line in self.pdf.pages[0].extract_text_lines():
            text = line["text"]
            if "增值税电子普通发票" in text:
                mt = re.search(r"([\u4e00-\u9fa5]+)增值税电子普通发票", text)
                self.data["type"] = 1
                self.data["type_desc"] = mt.group(0)
                break
            elif "普通发票" in text:
                if re.search(r"电子发票\s*[(（]普通发票[）)]", text):
                    self.data["type"] = 2
                    self.data["type_desc"] = "电子发票(普通发票)"
                    break
                else:
                    self.log_error(f"发票类型匹配失败: {text}")
        return self.data["type"]

    def print(self, s):
        print(f"{os.path.basename(self.filepath):<32}{s}")

    def log_error(self, s, v=None):
        print(f"[ERROR] {os.path.basename(self.filepath)} {s}: {v}")

    @staticmethod
    def merge_lines(lines, y_tolerance):
        """同一行可能因为水平没对齐被拆分到了不同的行，这里先预合并一下"""
        data = defaultdict(list)
        for line in lines:
            y = (line["top"] + line["bottom"]) / 2
            for k in data:
                if abs(y - k) <= y_tolerance:
                    data[k].append(line)
                    break
            else:
                data[y].append(line)

        new_lines = []
        for k in sorted(data.keys()):
            lst = sorted(data[k], key=lambda d: d["x0"])
            chars = reduce(lambda t, d: [*t, *d["chars"]], lst, [])
            chars = sorted(chars, key=lambda d: d["x0"])
            item = {
                "text": "".join([d["text"] for d in chars]),
                "x0": lst[0]["x0"],
                "x1": lst[-1]["x1"],
                "top": min([d["top"] for d in lst]),
                "bottom": max([d["bottom"] for d in lst]),
                "chars": chars,
            }
            new_lines.append(item)

        return new_lines

    @staticmethod
    def merge_line_chars(chars, x_tolerance):
        """合并单行的字符列表为单词"""
        char_groups = []
        lst = []
        prev_x1 = chars[0]["x1"]
        for char in chars:
            if char["x0"] - prev_x1 < x_tolerance:
                lst.append(char)
            else:
                char_groups.append(lst)
                lst = [char]
            prev_x1 = char["x1"]
        char_groups.append(lst)

        groups = []
        for lst in char_groups:
            item = {
                "text": "".join([c["text"] for c in lst]),
                "x0": lst[0]["x0"],
                "x1": lst[-1]["x1"],
                "chars": lst,
            }
            groups.append(item)

        return groups

    @staticmethod
    def get_type_conf(type: int):
        if type == 1:
            return {
                "merge_line_y_tolerance": 2,
                "header_line_x_tolerance": 20,
                "total_line_x_tolerance": 20,
            }
        elif type == 2:
            return {
                "merge_line_y_tolerance": 4,
                "header_line_x_tolerance": 20,
                "total_line_x_tolerance": 20,
            }
