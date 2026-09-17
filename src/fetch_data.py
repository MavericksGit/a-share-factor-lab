# -*- coding: utf-8 -*-
"""数据获取模块：用 AkShare 下载 A 股日线并整理成宽表 CSV。

说明：这个模块需要联网。项目默认先用 scripts/make_sample_data.py 生成的
本地样本数据跑通流程，之后在有网环境里执行 python main.py --fetch 即可换成真实数据。
"""

# os 用于创建目录
import os
# time 用于下载失败后暂停一下再重试
import time
# pandas 用于整理成宽表
import pandas as pd
# akshare 是 A 股数据的免费开源接口库
import akshare as ak


# 当“拉取沪深300成分股”失败时使用的兜底股票池（一批沪深300里的蓝筹股）
# 这些代码都是 6 位数字，不含交易所后缀
FALLBACK_UNIVERSE = [
    "600519", "601318", "600036", "000858", "000333", "600900",
    "601899", "002594", "300750", "600276", "601166", "600030",
    "601012", "600887", "000001", "000002", "600028", "601088",
    "600690", "000651", "601668", "600050", "601601", "600000",
    "000568", "002415", "601988", "601857", "600309", "002475",
]


def _clean_code(raw_code):
    """把“600519.SH”这种带后缀的代码清理成“600519”。"""
    # split(".") 按点切分，取第一部分就是 6 位代码
    return str(raw_code).split(".")[0]


def get_universe(index_code="000300", max_stocks=30):
    """获取沪深300成分股代码列表，失败时退回兜底股票池。"""
    # 用一个空列表存结果
    codes = []
    try:
        # 尝试用中证指数官网接口拿沪深300成分股
        # 注意：AkShare 不同版本列名可能变化，这里只做尽力而为
        df = ak.index_stock_cons_csindex(symbol=index_code)
        # 取成分券代码那一列
        raw_codes = df["成分券代码"].tolist()
        # 逐个清洗代码并去重
        codes = list(dict.fromkeys(_clean_code(c) for c in raw_codes))
    except Exception as exc:
        # 如果接口报错（例如列名变化或网络失败），打印提示并继续
        print(f"获取沪深300成分股失败（{type(exc).__name__}），改用内置兜底股票池")

    # 如果上面没拿到任何代码，就用兜底股票池
    if not codes:
        codes = FALLBACK_UNIVERSE

    # 只取前 max_stocks 只，控制下载速度
    return codes[:max_stocks]


def fetch_one(code, start, end, adjust="qfq", retries=4):
    """下载单只股票的日线数据，返回 (date, close, turnover) 三列。"""
    # 记录最后一次异常，用于重试次数用尽后抛出
    last_error = None
    # 最多尝试 retries 次，网络抖动时自动重试
    for attempt in range(1, retries + 1):
        try:
            # stock_zh_a_hist 是 AkShare 的 A 股历史行情接口
            # adjust="qfq" 表示前复权，避免分红除权造成价格跳空
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust=adjust,
            )
            # 下载成功后跳出重试循环
            break
        except Exception as exc:
            # 记住这次异常，打印提示后等待重试
            last_error = exc
            print(f"    第 {attempt}/{retries} 次尝试失败：{type(exc).__name__}")
            # 每次重试前暂停 2 秒，给代理/网络一点恢复时间
            time.sleep(2)
    else:
        # 如果 for 循环没有 break（全部重试都失败），抛出最后一次异常
        raise last_error

    # 只保留需要的三列，并统一成英文列名
    result = pd.DataFrame({
        "date": pd.to_datetime(df["日期"]),
        "close": pd.to_numeric(df["收盘"], errors="coerce"),
        "turnover": pd.to_numeric(df["换手率"], errors="coerce"),
    })
    # 去掉停牌导致的缺失值
    return result.dropna()


def build_dataset(codes, start, end, adjust="qfq", processed_dir="data/processed"):
    """下载多只股票，拼成收盘价和换手率两张宽表并保存 CSV。"""
    # 确保输出目录存在
    os.makedirs(processed_dir, exist_ok=True)

    # 用字典分别收集每只股票的收盘价和换手率序列
    price_dict = {}
    turnover_dict = {}

    # 逐个下载
    for i, code in enumerate(codes, start=1):
        # 打印进度，下载多只股票时比较直观
        print(f"[{i}/{len(codes)}] 下载 {code} ...")
        try:
            # 下载单只股票，fetch_one 内部已经带自动重试
            df = fetch_one(code, start, end, adjust)
        except Exception as exc:
            # 单只股票下载失败不中断整个流程，打印错误后跳过
            print(f"  下载 {code} 失败：{type(exc).__name__}，跳过")
            continue
        # 以日期为索引，分别保存收盘价和换手率
        price_dict[code] = df.set_index("date")["close"]
        turnover_dict[code] = df.set_index("date")["turnover"]
        # 每只股票之间暂停 0.3 秒，避免请求过快被限流
        time.sleep(0.3)

    # 如果一只都没下载成功，直接报错，并且不覆盖旧的已处理数据
    if not price_dict:
        raise RuntimeError(
            "没有成功下载任何股票数据，请检查网络/代理设置；"
            "已有的 data/processed 数据未覆盖。"
        )

    # 把字典转成两张宽表（行=日期，列=股票代码）
    prices = pd.DataFrame(price_dict).sort_index()
    turnover = pd.DataFrame(turnover_dict).sort_index()

    # 保存成 CSV，第一列是日期索引
    prices.to_csv(os.path.join(processed_dir, "prices.csv"))
    turnover.to_csv(os.path.join(processed_dir, "turnover.csv"))

    # 打印统计信息，方便检查下载结果
    print(f"完成：共 {prices.shape[1]} 只股票，{prices.shape[0]} 个交易日")
    return prices, turnover
