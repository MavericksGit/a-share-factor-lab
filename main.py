# -*- coding: utf-8 -*-
"""主入口：串起 数据 -> 因子 -> 检验 -> 分层回测 -> 组合 -> 报告 全流程。"""

# argparse 用于解析命令行参数，例如 --fetch
import argparse
# os 用于处理文件路径
import os
# pandas 用于读取数据
import pandas as pd

# 导入本项目各模块
from src.config import load_config
from src.factors import build_factors
from src.factor_test import test_all_factors
from src.layered_backtest import quantile_returns, long_short_return, quantile_summary
from src.preprocess import preprocess, build_exposures
from src.portfolio import top_bottom_long_short, performance_metrics
from src.report import plot_layered_backtest, plot_portfolio, write_report


def load_processed(processed_dir):
    """从本地 CSV 读取收盘价和换手率宽表。"""
    # 拼接文件路径
    price_path = os.path.join(processed_dir, "prices.csv")
    turnover_path = os.path.join(processed_dir, "turnover.csv")
    # 若文件不存在，给出明确提示而不是抛一堆报错
    if not (os.path.exists(price_path) and os.path.exists(turnover_path)):
        raise FileNotFoundError(
            "找不到处理后的数据。请先运行 python scripts/make_sample_data.py 生成样本数据，"
            "或在有网环境运行 python main.py --fetch 下载真实数据。"
        )
    # 第一列是日期索引，parse_dates 自动转成日期类型
    prices = pd.read_csv(price_path, index_col=0, parse_dates=True)
    turnover = pd.read_csv(turnover_path, index_col=0, parse_dates=True)
    # 如果读进来是空表，给出明确提示，而不是让后面的计算崩溃
    if prices.empty:
        raise ValueError("数据为空，请先下载真实数据（--fetch）或生成样本数据")
    return prices, turnover


def _load_series(processed_dir, filename):
    """读取单列 CSV（行业、市值），返回 Series；文件不存在则返回 None。"""
    # 拼接路径
    path = os.path.join(processed_dir, filename)
    # 不存在就返回 None，让后续逻辑跳过对应的中性化
    if not os.path.exists(path):
        return None
    # 第一列是索引，squeeze 把单列 DataFrame 压成 Series
    return pd.read_csv(path, index_col=0).squeeze("columns")


def main():
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="A股单因子研究工具")
    # --fetch 是一个开关，指定则下载真实数据
    parser.add_argument("--fetch", action="store_true", help="下载真实 A 股数据")
    # --source 指定数据源，缺省时用配置文件里的 data.source
    parser.add_argument("--source", default=None, choices=["akshare", "tushare"], help="数据源")
    # --config 可指定自定义配置文件
    parser.add_argument("--config", default=None, help="配置文件路径")
    # 解析命令行参数
    args = parser.parse_args()

    # 读取配置
    config = load_config(args.config)
    processed_dir = config["data"]["processed_dir"]
    output_dir = config["report"]["output_dir"]
    # 确定数据源：命令行参数优先，否则用配置文件
    source = args.source or config["data"].get("source", "akshare")

    # 如果需要下载真实数据，按数据源调用对应模块
    if args.fetch:
        if source == "tushare":
            from src.fetch_data_tushare import download
            download(config["tushare"], processed_dir)
        else:
            from src.fetch_data import get_universe, build_dataset
            codes = get_universe(config["fetch"]["index"], config["fetch"]["max_stocks"])
            build_dataset(
                codes,
                config["fetch"]["start"],
                config["fetch"]["end"],
                config["fetch"]["adjust"],
                processed_dir,
            )

    # 读取处理好的宽表数据
    prices, turnover = load_processed(processed_dir)

    # 构造因子，同时得到日收益率
    returns, factors = build_factors(prices, turnover, config["factors"])

    # 加载行业和市值元数据，用于因子中性化
    industry = _load_series(processed_dir, "industry.csv")
    market_cap = _load_series(processed_dir, "market_cap.csv")
    pre_cfg = config.get("preprocess", {})
    # 构造中性化暴露矩阵（对数市值 + 行业哑变量）
    exposures = build_exposures(
        market_cap,
        industry,
        use_size=pre_cfg.get("neutralize_size", False),
        use_industry=pre_cfg.get("neutralize_industry", False),
    )

    # 对每个因子执行 去极值 -> 中性化 -> 标准化
    processed_factors = {
        name: preprocess(f, pre_cfg, exposures) for name, f in factors.items()
    }

    # 对处理后的因子做 IC / Rank IC / t 检验
    summary = test_all_factors(processed_factors, returns, config["test"]["forward_period"])
    print("\n===== 因子检验汇总 =====")
    print(summary.round(4).to_string())

    # 取出用于组合的因子
    factor_name = config["portfolio"]["factor"]
    factor = processed_factors[factor_name]
    quantiles = config["test"]["quantiles"]

    # 分层回测：计算 5 组收益和多空收益
    quantile_ret = quantile_returns(factor, returns, quantiles)
    long_short = long_short_return(quantile_ret, quantiles)
    # 计算各档年化收益和单调性
    group_summary, mono_corr, mono_p = quantile_summary(quantile_ret)
    print("\n===== 分层各档年化收益 =====")
    print(group_summary.apply(lambda x: f"{x:.2%}").to_string())
    print(f"单调性 Spearman 相关: {mono_corr:.3f} (p={mono_p:.3f})")

    # 多空组合（含交易成本）
    gross, net, weights = top_bottom_long_short(
        factor, returns, quantiles, config["portfolio"]["cost_rate"]
    )
    metrics = performance_metrics(net)

    # 打印组合指标
    print(f"\n===== {factor_name} 多空组合绩效 =====")
    print(f"年化收益: {metrics['年化收益']:.2%}")
    print(f"年化波动: {metrics['年化波动']:.2%}")
    print(f"夏普比率: {metrics['夏普比率']:.2f}")
    print(f"最大回撤: {metrics['最大回撤']:.2%}")
    print(f"最终累计净值: {metrics['累计净值'].iloc[-1]:.3f}")

    # 生成图表和报告
    plot_layered_backtest(quantile_ret, long_short, factor_name, output_dir)
    plot_portfolio(metrics, factor_name, output_dir)
    report_path = write_report(
        summary, metrics, output_dir, factor_name, group_summary, mono_corr
    )

    # 打印输出位置
    print(f"\n报告已生成：{report_path}")


# 当直接运行 python main.py 时执行 main()；被其它模块 import 时不会自动执行
if __name__ == "__main__":
    main()
