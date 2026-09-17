# -*- coding: utf-8 -*-
"""因子预处理模块：去极值、中性化、标准化。

这是因子研究里非常关键的一步。原始因子值往往有极端值、被市值或行业“污染”，
直接算 IC 会失真。标准流程通常是：去极值 -> 中性化 -> 标准化。
"""

# numpy 用于矩阵运算（中性化时做投影）
import numpy as np
# pandas 用于 DataFrame 计算
import pandas as pd


def winsorize(factor, mad_n=3):
    """去极值：把偏离中位数太远的值截断到中位数 ± mad_n 倍 MAD。

    MAD = 1.4826 * 中位数绝对偏差，比均值±标准差更抗极端值。
    这里按“每一天”做横截面处理：axis=1 表示对每一行（同一天）计算。
    """
    # 每一天（每一行）的中位数
    median = factor.median(axis=1)
    # 每一天的中位数绝对偏差（MAD），乘以 1.4826 换算成类似标准差的尺度
    mad = (factor.sub(median, axis=0)).abs().median(axis=1) * 1.4826
    # 截断下限 = 中位数 - n*MAD
    lower = median - mad_n * mad
    # 截断上限 = 中位数 + n*MAD
    upper = median + mad_n * mad
    # clip 把超出上下限的值压到边界上，axis=0 表示 lower/upper 按日期对齐
    return factor.clip(lower=lower, upper=upper, axis=0)


def standardize(factor):
    """标准化：把因子转成每一天横截面的 z-score（均值 0、标准差 1）。"""
    # 每一天的均值
    mean = factor.mean(axis=1)
    # 每一天的标准差
    std = factor.std(axis=1)
    # 标准差为 0 时替换成 NaN，避免除以 0
    std = std.replace(0, np.nan)
    # 先减均值，再除以标准差，axis=0 按日期对齐
    return factor.sub(mean, axis=0).div(std, axis=0)


def build_exposures(market_cap=None, industry=None, use_size=True, use_industry=True):
    """构造中性化用的暴露矩阵（横截面回归的自变量）。

    市值取对数后再 z-score，行业用独热编码（drop_first 去掉一列避免共线性）。
    注意：这里用“某个时点”的静态市值做近似，真实研究会用每个调仓日的时点市值。
    """
    # 用列表收集各个暴露变量
    parts = []
    # 市值中性化：对总市值取对数，因为市值分布严重右偏
    if use_size and market_cap is not None:
        log_mv = np.log(market_cap.astype(float))
        # 对对数市值做标准化，让回归更稳定
        log_mv = (log_mv - log_mv.mean()) / log_mv.std()
        parts.append(log_mv.rename("log_size"))

    # 行业中性化：把行业变成 0/1 哑变量
    if use_industry and industry is not None:
        dummies = pd.get_dummies(industry, drop_first=True).astype(float)
        parts.append(dummies)

    # 一个暴露变量都没有就返回 None
    if not parts:
        return None
    # 横向拼接所有暴露变量，并删掉有缺失值的股票
    exposures = pd.concat(parts, axis=1)
    return exposures.dropna()


def neutralize(factor, exposures):
    """中性化：把因子对暴露变量做横截面回归，取残差，去掉市值/行业影响。"""
    # 只保留同时出现在因子和暴露矩阵里的股票
    common = factor.columns.intersection(exposures.index)
    X = exposures.loc[common].copy()
    # 在最前面加一列常数 1，代表截距项
    X.insert(0, "const", 1.0)
    Xv = X.values.astype(float)
    # 因子值矩阵：行是日期，列是股票
    Y = factor[common].values.astype(float)

    # 投影矩阵 P = X (X'X)^-1 X'，用它把 Y 投影到 X 张成的空间
    # 因为暴露矩阵对每天都是同一个，所以 P 只需算一次，可以向量化处理所有日期
    P = Xv @ np.linalg.pinv(Xv)
    # 残差 = Y - Y 在 X 上的投影，即去掉了 X 能解释的部分
    residual = Y - Y @ P.T
    # 把残差转回 DataFrame，保持原来的日期索引和股票列
    return pd.DataFrame(residual, index=factor.index, columns=common)


def preprocess(factor, config, exposures=None):
    """按顺序执行 去极值 -> 中性化 -> 标准化。"""
    # 复制一份，避免修改原始因子
    f = factor.copy()
    # 第一步：去极值（开关和 MAD 倍数来自配置）
    if config.get("winsorize", True):
        f = winsorize(f, config.get("mad_n", 3))
    # 第二步：中性化（只有提供了暴露矩阵才做）
    if exposures is not None:
        f = neutralize(f, exposures)
    # 第三步：标准化
    if config.get("standardize", True):
        f = standardize(f)
    return f
