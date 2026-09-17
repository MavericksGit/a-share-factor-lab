# -*- coding: utf-8 -*-
"""因子构造模块：只用价格和换手率构造几个常见因子。"""

# pandas 用来做 DataFrame 的滚动计算
import pandas as pd


def build_factors(prices, turnover, factor_config):
    """根据配置构造一组因子，并返回日收益率。

    参数：
        prices        : 收盘价宽表，行是日期，列是股票代码
        turnover      : 换手率宽表，行是日期，列是股票代码（单位是百分比）
        factor_config : 因子名到窗口长度的字典，例如 {"momentum_20": 20}
    返回：
        (returns, factors)
        returns : 日收益率宽表
        factors : 因子名到因子宽表的字典
    """
    # 日收益率 = 当日收盘价相对前一日收盘价的变化率
    # 第一行因为缺少前一天，所以是 NaN
    returns = prices.pct_change(fill_method=None)

    # 用一个字典存放所有构造出来的因子
    factors = {}

    # 遍历配置里的每个因子
    for name, window in factor_config.items():
        # 根据因子名的前缀判断它是哪一类因子
        if name.startswith("momentum"):
            # 动量因子：当前价相对 N 天前价格的变化率，涨幅越大代表动量越强
            factors[name] = prices.pct_change(window, fill_method=None)
        elif name.startswith("reversal"):
            # 反转因子：取负号后，“最近跌得多”的股票因子值反而更大，代表博反弹
            factors[name] = -prices.pct_change(window, fill_method=None)
        elif name.startswith("volatility"):
            # 波动率因子：收益率滚动 N 天的标准差，衡量风险大小
            factors[name] = returns.rolling(window).std()
        elif name.startswith("turnover"):
            # 换手率因子：换手率滚动 N 天的平均值，衡量交易活跃度
            factors[name] = turnover.rolling(window).mean()
        else:
            # 遇到不认识的前缀就报错，避免拼错因子名却悄悄算了错误结果
            raise ValueError(f"未知的因子类型：{name}")

    # 返回收益率和全部因子
    return returns, factors
