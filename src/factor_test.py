# -*- coding: utf-8 -*-
"""因子检验模块：计算 IC、Rank IC、ICIR，并对 IC 序列做 t 检验。"""

# pandas 用于 DataFrame 计算
import pandas as pd
# ttest_1samp 用于对 IC 序列做单样本 t 检验，判断均值是否显著不为 0
from scipy.stats import ttest_1samp


def ic_series(factor, forward_return):
    """计算每一天的横截面 IC（信息系数）。

    IC 的直觉：同一天里，因子值越高的股票，未来收益是否也越高。
    数学上就是“某天因子值与下期收益在横截面上的相关系数”。
    来源：https://www.joinquant.com/community/post/detailMobile?postId=15290
    """
    # corrwith(other, axis=1)：按“行”配对，计算每一天的因子值序列和未来收益序列的相关系数
    # axis=1 是关键：它做的是横截面（同一日期、跨股票）相关，而不是时间序列相关
    return factor.corrwith(forward_return, axis=1)


def rank_ic_series(factor, forward_return):
    """计算每一天的 Rank IC（秩相关系数）。"""
    # rank(axis=1) 先在同一天内把因子值转成排名，减少极端值对 IC 的影响
    factor_rank = factor.rank(axis=1)
    # 未来收益也做同样排名
    forward_rank = forward_return.rank(axis=1)
    # 再用排名和排名求横截面相关，得到 Rank IC
    return factor_rank.corrwith(forward_rank, axis=1)


def test_factor(factor, returns, forward_period=1):
    """对单个因子做完整检验，返回一个结果字典。"""
    # 未来收益 = 未来第 forward_period 天的收益
    # shift(-1) 向上取未来一天，避免用到当天才产生的信息
    forward_return = returns.shift(-forward_period)

    # 计算 IC 和 Rank IC 的逐日序列
    ic = ic_series(factor, forward_return)
    rank_ic = rank_ic_series(factor, forward_return)

    # 去掉 IC 序列里的 NaN（例如因子刚形成、或某天只有一只股票有效时会产生 NaN）
    ic_clean = ic.dropna()

    # IC 均值：衡量因子的平均预测方向，正数代表“因子值越高、未来收益越高”
    ic_mean = ic_clean.mean()
    # IC 标准差：衡量 IC 的稳定性
    ic_std = ic_clean.std(ddof=1)
    # ICIR = IC 均值 / IC 标准差，衡量“单位风险能换来多少稳定预测力”
    # 值越大通常越稳定（例如 >0.3 常被视为较好）
    icir = ic_mean / ic_std if ic_std > 0 else float("nan")

    # 对 IC 序列做单样本 t 检验，原假设是“IC 均值 = 0”
    # 返回 (t 统计量, p 值)
    t_stat, p_value = ttest_1samp(ic_clean, popmean=0)

    # IC 大于 0 的天数占比，反映因子方向是否稳定
    positive_ratio = (ic_clean > 0).mean()

    # 把所有指标放进字典返回
    return {
        "IC均值": ic_mean,
        "IC标准差": ic_std,
        "ICIR": icir,
        "RankIC均值": rank_ic.dropna().mean(),
        "t统计量": t_stat,
        "p值": p_value,
        "IC为正占比": positive_ratio,
        "显著(5%)": p_value < 0.05,
    }


def test_all_factors(factors, returns, forward_period=1):
    """对所有因子做检验，并把结果整理成一张汇总表。"""
    # 用一个列表收集每个因子的结果
    rows = []
    # 遍历所有因子
    for name, factor in factors.items():
        # 检验单个因子
        result = test_factor(factor, returns, forward_period)
        # 把因子名放进结果，方便之后当行索引
        result["因子"] = name
        rows.append(result)

    # 把列表转成 DataFrame，并设“因子”列为行索引
    summary = pd.DataFrame(rows).set_index("因子")
    # 返回汇总表
    return summary
