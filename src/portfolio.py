# -*- coding: utf-8 -*-
"""组合模块：把分层信号变成一个可交易的多空组合，并计算交易成本和绩效。"""

# numpy 的 sqrt 用于年化波动率
import numpy as np


def top_bottom_long_short(factor, returns, quantiles=5, cost_rate=0.0015):
    """构造“买最高组、卖最低组”的多空组合，返回毛收益、净收益和权重。

    注意：这里多空组合是市场中性方向（多头约等于空头），
    现实中 A 股做空受限，实际策略通常只做多最高组，本代码仅作研究演示。
    """
    # 复用分层回测里的分组函数
    from src.layered_backtest import assign_quantiles
    groups = assign_quantiles(factor, quantiles)

    # 最高组的股票记为 1，其余为 0
    top_mask = (groups == quantiles).astype(float)
    # 最高组内部等权
    top_weight = top_mask.div(top_mask.sum(axis=1), axis=0).fillna(0)

    # 最低组的股票记为 1，其余为 0
    bottom_mask = (groups == 1).astype(float)
    # 最低组内部等权
    bottom_weight = bottom_mask.div(bottom_mask.sum(axis=1), axis=0).fillna(0)

    # 最终权重 = 多头（最高组） - 空头（最低组）
    weights = top_weight - bottom_weight

    # 毛收益 = 前一天的权重 * 当天收益率，再按股票求和
    gross_return = (weights.shift(1).fillna(0) * returns).sum(axis=1)

    # 换手率 = 权重变化量的绝对值，再按股票求和
    # 表示今天相对昨天调仓了多少仓位
    turnover = weights.diff().abs().sum(axis=1).fillna(0)

    # 交易成本 = 换手 * 单边成本率
    cost = turnover * cost_rate

    # 净收益 = 毛收益 - 成本
    net_return = gross_return - cost

    # 返回三个结果
    return gross_return, net_return, weights


def performance_metrics(daily_returns, periods_per_year=252):
    """计算一组日收益的年化收益、波动率、夏普和最大回撤。"""
    # 去掉缺失值
    daily_returns = daily_returns.dropna()
    # 期间累计收益
    total_return = (1 + daily_returns).prod() - 1
    # 样本天数
    n = len(daily_returns)
    # 如果没有任何收益数据，直接报错，避免后面除以 0
    if n == 0:
        raise ValueError("收益序列为空，无法计算绩效指标")
    # 年化收益 = 累计收益按复利折算到一年 252 个交易日
    annual_return = (1 + total_return) ** (periods_per_year / n) - 1
    # 年化波动率 = 日收益标准差 * sqrt(252)
    annual_vol = daily_returns.std(ddof=1) * np.sqrt(periods_per_year)
    # 夏普比率 = 日均值 / 日标准差 * sqrt(252)，无风险利率按 0 简化
    sharpe = daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(periods_per_year)
    # 累计净值曲线
    equity = (1 + daily_returns).cumprod()
    # 回撤 = 当前净值相对历史最高净值的跌幅
    drawdown = equity / equity.cummax() - 1
    # 最大回撤取最小值（跌幅最大）
    max_drawdown = drawdown.min()
    # 返回指标字典
    return {
        "年化收益": annual_return,
        "年化波动": annual_vol,
        "夏普比率": sharpe,
        "最大回撤": max_drawdown,
        "累计净值": equity,
        "回撤序列": drawdown,
    }
