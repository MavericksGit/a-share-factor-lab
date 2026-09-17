# -*- coding: utf-8 -*-
"""Tushare 数据源：下载沪深300成分股的前复权日线和换手率，整理成宽表 CSV。

用法：
    先把 token 放进环境变量，再运行 python main.py --fetch --source tushare。
    例如在终端：export TUSHARE_TOKEN="你的token"
    token 不写进配置文件，避免上传 GitHub 时泄露。
"""

# os 用于读取环境变量和创建目录
import os
# time 用于限速和重试
import time
# pandas 用于整理成宽表
import pandas as pd
# tushare 是 A 股数据接口库
import tushare as ts


def get_pro(tushare_config):
    """根据配置创建 Tushare Pro 接口对象，并指向自定义镜像地址。"""
    # 从环境变量读取 token，比硬编码在代码里更安全
    token = os.environ.get(tushare_config["token_env"])
    # 没设置 token 就给出明确提示
    if not token:
        raise RuntimeError(
            f"请先设置环境变量 {tushare_config['token_env']}，例如 export "
            f"{tushare_config['token_env']}='你的token'"
        )
    # 镜像地址优先从环境变量读，没设置再用配置里的值
    url = os.environ.get("TUSHARE_URL") or tushare_config.get("url")
    if not url:
        raise RuntimeError("请设置 TUSHARE_URL 环境变量，或在 config.yaml 的 tushare.url 里填写镜像地址")
    # 用 token 创建接口对象
    pro = ts.pro_api(token)
    # 把默认接口地址改成自定义镜像地址（这里是用户提供的加速/镜像节点）
    pro._DataApi__http_url = url
    return pro


def get_universe(pro, index_code, max_stocks, start):
    """获取沪深300成分股，按权重从高到低取前 max_stocks 只。"""
    # 取 start 所在月份的第一天和最后一天，用来拿那个月的成分截面
    start_ym = start.replace("-", "")
    # Period(...).end_time 得到该月最后一天，再格式化成 YYYYMMDD
    end_ym = pd.Period(start, freq="M").end_time.strftime("%Y%m%d")

    # index_weight 返回每月成分股及其权重
    df = pro.index_weight(index_code=index_code, start_date=start_ym, end_date=end_ym)

    # 同一只股票可能出现在多个交易日，取它在该月权重最大的一次
    weight = df.groupby("con_code")["weight"].max()
    # 按权重从高到低排序，取前 max_stocks 只
    codes = weight.sort_values(ascending=False).head(max_stocks).index.tolist()
    # 返回带 .SZ/.SH 后缀的代码列表
    return codes


def fetch_one(pro, code, start, end, retries=3):
    """下载单只股票的前复权收盘价和换手率，返回 (date, close, turnover)。"""
    # 日期格式转成 Tushare 需要的 YYYYMMDD
    start_ym = start.replace("-", "")
    end_ym = end.replace("-", "")

    # 记录最后一次异常，用于重试耗尽后抛出
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            # pro_bar 返回前复权日线；api=pro 表示走同一个自定义接口对象
            bar = ts.pro_bar(api=pro, ts_code=code, adj="qfq",
                             start_date=start_ym, end_date=end_ym)
            # daily_basic 里有换手率 turnover_rate
            basic = pro.daily_basic(
                ts_code=code, start_date=start_ym, end_date=end_ym,
                fields="ts_code,trade_date,turnover_rate",
            )
            # 两个接口都成功就跳出重试循环
            break
        except Exception as exc:
            # 记录异常并等待后重试
            last_error = exc
            time.sleep(1)
    else:
        # 全部失败就抛出最后一次异常
        raise last_error

    # 只保留需要的列，并统一 trade_date 为字符串方便合并
    bar = bar[["trade_date", "close"]].copy()
    bar["trade_date"] = bar["trade_date"].astype(str)
    basic = basic[["trade_date", "turnover_rate"]].copy()
    basic["trade_date"] = basic["trade_date"].astype(str)
    # 把列名从 turnover_rate 统一成 turnover，和项目里其它数据源保持一致
    basic = basic.rename(columns={"turnover_rate": "turnover"})

    # 按交易日期把收盘价和换手率合并到一起
    merged = bar.merge(basic, on="trade_date", how="left")
    # 把 YYYYMMDD 字符串转成真正的日期
    merged["date"] = pd.to_datetime(merged["trade_date"], format="%Y%m%d")
    # 按日期升序排列，保证时间顺序正确
    merged = merged.sort_values("date")
    # 返回三列，并去掉缺失值（停牌等）
    return merged[["date", "close", "turnover"]].dropna()


def download(tushare_config, processed_dir="data/processed"):
    """下载整个股票池，保存成 prices.csv 和 turnover.csv 宽表。"""
    # 确保输出目录存在
    os.makedirs(processed_dir, exist_ok=True)

    # 创建接口对象
    pro = get_pro(tushare_config)
    # 获取股票池
    codes = get_universe(
        pro, tushare_config["index_code"],
        tushare_config["max_stocks"], tushare_config["start"],
    )
    print(f"股票池：{len(codes)} 只（沪深300按权重取前 {tushare_config['max_stocks']}）")

    # 用字典收集每只股票的收盘价和换手率
    price_dict = {}
    turnover_dict = {}

    # 逐个下载
    for i, code in enumerate(codes, start=1):
        # 打印进度
        print(f"[{i}/{len(codes)}] 下载 {code} ...")
        try:
            df = fetch_one(
                pro, code,
                tushare_config["start"], tushare_config["end"],
            )
        except Exception as exc:
            # 单只失败不中断，打印后跳过
            print(f"  下载 {code} 失败：{type(exc).__name__}，跳过")
            continue
        # 保存收盘价和换手率
        price_dict[code] = df.set_index("date")["close"]
        turnover_dict[code] = df.set_index("date")["turnover"]
        # 每只之间暂停 0.2 秒，避免请求过快
        time.sleep(0.2)

    # 一只都没成功就报错，不覆盖旧数据
    if not price_dict:
        raise RuntimeError("没有成功下载任何股票数据，请检查 token 和网络")

    # 拼成两张宽表
    prices = pd.DataFrame(price_dict).sort_index()
    turnover = pd.DataFrame(turnover_dict).sort_index()

    # 保存 CSV
    prices.to_csv(os.path.join(processed_dir, "prices.csv"))
    turnover.to_csv(os.path.join(processed_dir, "turnover.csv"))
    print(f"完成：共 {prices.shape[1]} 只股票，{prices.shape[0]} 个交易日")
    return prices, turnover


def fetch_meta(tushare_config, processed_dir="data/processed"):
    """下载因子中性化需要的行业和市值数据，保存成 CSV。

    行业来自 stock_basic，市值用数据第一天那个时点的总市值做静态近似。
    """
    # 创建接口对象
    pro = get_pro(tushare_config)
    # 读取已经下载好的价格，得到股票池
    prices = pd.read_csv(
        os.path.join(processed_dir, "prices.csv"), index_col=0, parse_dates=True
    )
    codes = list(prices.columns)

    # 下载全市场股票行业，再筛出我们的股票池
    industry_all = pro.stock_basic(fields="ts_code,industry", list_status="L")
    industry = industry_all[industry_all["ts_code"].isin(codes)].set_index("ts_code")["industry"]
    # 保存行业
    industry.to_csv(os.path.join(processed_dir, "industry.csv"), index_label="ts_code")

    # 用数据第一天的总市值做静态规模代理
    first_date = prices.index[0].strftime("%Y%m%d")
    mv_all = pro.daily_basic(trade_date=first_date, fields="ts_code,total_mv")
    mv = mv_all[mv_all["ts_code"].isin(codes)].set_index("ts_code")["total_mv"]
    # 保存市值
    mv.to_csv(os.path.join(processed_dir, "market_cap.csv"), index_label="ts_code")

    # 打印统计信息
    print(f"元数据已保存：{len(industry)} 只行业、{len(mv)} 只市值")
    return industry, mv
