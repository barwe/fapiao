依赖:
```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple prettytable pdfplumber
```

基本用法：

```bash
python main.py <target_dir> ...
```

默认显示的列有：
- 文件 (relpath): 相对于 `<target_dir>` 的路径
- 发票类型 (type): 参考 type-1.png 和 type-2.png
- Code/Number (uid): 1类发票由发票代码和发票号码拼接而成；2类发票没有发票代码，只有发票号码
- 开票日期 (date): 格式为 yyyymmdd
- 价税合计 (total)
- 购买方 (buyer)

用法举例:
- `-k relpath total`: 只打印文件路径和价税合计两列
- `-q buyer~深圳`: 只打印 buyer 值包含“深圳”的数据
- `-q date=20240709`: 只打印 date 等于“20240709”的数据
- `-q buyer~深圳 date=20240709`: 指定多个查询条件时取交集
- `-s date`: 按 date 列升序打印
- `-s date-`: 按 date 列降序打印
- `-z`: 打印列同时显示中文含义

其他参数：
- `--rename`: 重命名文件，格式由 --rename-format 参数指定
- `--rename-format`: 重命名格式，默认为 "{buyer}-{date}-{uid}-{total}"
- `--remake-cache`: 强制刷新缓存
