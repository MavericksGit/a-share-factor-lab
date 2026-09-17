# -*- coding: utf-8 -*-
"""生成离线测试用的合成数据，方便在没有网络时跑通整个流程。

数据是人为构造的，并特意在收益里加入了一点“动量效应”，
这样工具应该能“发现”动量因子有效，用来验证代码本身没有写错。
注意：这只是自测数据，不能用来得出任何真实市场结论。
"""

# os 用于创建目录
import os
# numpy 用于生成随机数和模拟
import numpy as np
# pandas 用于拼表并保存
import pandas as pd


def make_sample_data(n_stocks=30, n_days=250, seed=42):
    """生成 n_stocks 只股票、n_days 个交易日的合成收盘价和换手率。"""
    # 固定随机种子，保证每次生成的数据完全一样，结果可复现
    rng = np.random.default_rng(seed)

    # 生成交易日序列（只取工作日）
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    # 股票代码用 6 位数字表示
    codes = [f"{i:06d}" for i in range(1, n_stocks + 1)]

    # 先用矩阵存每天的收益率，形状是 (天数, 股票数)
    returns = np.zeros((n_days, n_stocks))
    # 存每只股票“持续的趋势因子”，用来制造动量效应
    trend = np.zeros((n_days, n_stocks))

    # 第一天先给一个初始趋势
    trend[0] = rng.normal(0, 0.1, n_stocks)
    # 从第二天开始模拟：趋势高度自相关，意味着“过去涨的股票未来也容易涨”
    for t in range(1, n_days):
        # AR(1)：今天的趋势 = 0.97 * 昨天趋势 + 随机扰动
        trend[t] = 0.97 * trend[t - 1] + rng.normal(0, 0.02, n_stocks)

    # 收益 = 基准漂移 + 趋势的贡献 + 个体随机噪声
    returns = 0.0005 + 0.05 * trend + rng.normal(0, 0.015, (n_days, n_stocks))

    # 从初始价 10 元开始，用 (1+收益) 连乘得到价格序列
    prices = 10 * np.cumprod(1 + returns, axis=0)
    # 换手率用 0.5~5 之间的随机数模拟，和收益没有必然联系
    turnover = rng.uniform(0.5, 5.0, (n_days, n_stocks))

    # 把数组转成 DataFrame，行是日期、列是股票代码
    price_df = pd.DataFrame(prices, index=dates, columns=codes)
    turnover_df = pd.DataFrame(turnover, index=dates, columns=codes)
    # 给索引命名，保存 CSV 后第一列就是 date
    price_df.index.name = "date"
    turnover_df.index.name = "date"
    return price_df, turnover_df


if __name__ == "__main__":
    # 生成数据
    price_df, turnover_df = make_sample_data()
    # 输出目录
    out_dir = os.path.join("data", "processed")
    # 创建目录（如果不存在）
    os.makedirs(out_dir, exist_ok=True)
    # 保存收盘价和换手率
    price_df.to_csv(os.path.join(out_dir, "prices.csv"))
    turnover_df.to_csv(os.path.join(out_dir, "turnover.csv"))
    # 打印完成信息
    print(f"样本数据已生成：{out_dir}/prices.csv 和 {out_dir}/turnover.csv")
