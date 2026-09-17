# -*- coding: utf-8 -*-
"""分层回测模块：把股票按因子值分成 5 组，观察各组未来的收益差异。"""

# numpy 的 ceil 用于向上取整，把排名映射到分组
import numpy as np
# pandas 用于 DataFrame 计算
import pandas as pd
# spearmanr 计算单调性的秩相关系数
from scipy.stats import spearmanr


def assign_quantiles(factor, quantiles=5):
    """把每天的因子值按横截面排名划分成若干组，返回分组编号（1 到 quantiles）。"""
    # rank(axis=1, pct=True)：在同一天内按因子值排名，并换算成 0~1 的百分位
    rank_pct = factor.rank(axis=1, pct=True)
    # 百分位乘组数再向上取整，把股票映射到 1~quantiles 组
    # 例如百分位 0.9 在第 5 组，百分位 0.1 在第 1 组
    groups = np.ceil(rank_pct * quantiles)
    # clip 保证结果落在 1 到 quantiles 之间，避免边界错误
    groups = groups.clip(lower=1, upper=quantiles)
    # 因子尚未形成的早期日期是 NaN，先填成 0 表示“未分组”，再转成整数
    return groups.fillna(0).astype(int)


def quantile_returns(factor, returns, quantiles=5):
    """计算每个因子分组的等权组合日收益，返回 (组号 -> 收益序列) 的 DataFrame。"""
    # 先给每天的股票分好组
    groups = assign_quantiles(factor, quantiles)

    # 用字典保存每一组的日收益
    group_result = {}

    # 依次计算第 1 组到第 quantiles 组
    for g in range(1, quantiles + 1):
        # 属于当前组的股票记为 1，否则记为 0
        mask = (groups == g).astype(float)
        # 组内等权：每只股票分到 1 / 该组股票数量
        # div(axis=0) 用每一行的和做归一化
        weight = mask.div(mask.sum(axis=1), axis=0).fillna(0)
        # 组收益 = 前一天的权重 * 当天收益率，再按股票求和
        # shift(1) 用昨天确定的组持仓，交易今天的收益，避免未来函数
        group_result[g] = (weight.shift(1).fillna(0) * returns).sum(axis=1)

    # 把字典转成 DataFrame，列名就是组号 1..5
    return pd.DataFrame(group_result)


def long_short_return(quantile_ret, quantiles=5):
    """用最高组减最低组的收益，得到因子多空组合的日收益。"""
    # 第 quantiles 组（最高因子值）减第 1 组（最低因子值）
    return quantile_ret[quantiles] - quantile_ret[1]


def quantile_summary(quantile_ret, periods_per_year=252):
    """计算每一组的年化收益，以及“组号 vs 收益”的单调性。"""
    # 用字典保存每组的年化收益
    annual_returns = {}
    # 遍历每一组
    for g in quantile_ret.columns:
        # 去掉缺失值
        r = quantile_ret[g].dropna()
        n = len(r)
        # 年化收益 = 累计收益按复利折算到一年 252 个交易日
        annual_returns[g] = (1 + r).prod() ** (periods_per_year / n) - 1
    # 把字典转成 Series
    summary = pd.Series(annual_returns, name="年化收益")
    # 单调性：组号与年化收益的 Spearman 秩相关，越接近 1 表示越高组收益越高
    mono_corr, mono_p = spearmanr(summary.index.astype(int), summary.values)
    # 返回每档收益、单调相关系数和 p 值
    return summary, mono_corr, mono_p
