# -*- coding: utf-8 -*-
"""报告模块：生成 Markdown 报告和图表。"""

# os 用于创建输出目录
import os
# matplotlib 用于画图
import matplotlib
# 使用 Agg 后端，在无图形界面的服务器上也能保存图片
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _save_png(fig, output_dir, filename):
    """把画布保存成 PNG 文件，并关闭画布释放内存。"""
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    # 拼接完整输出路径
    path = os.path.join(output_dir, filename)
    # 保存图片，dpi 控制清晰度
    fig.savefig(path, dpi=120)
    # 关闭画布
    plt.close(fig)
    return path


def plot_layered_backtest(quantile_ret, long_short, factor_name, output_dir):
    """画分层回测图：上面是 5 组累计净值，下面是多空累计净值。"""
    # 创建一个上下两个子图的画布
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

    # 每个分组的累计净值 = (1 + 组收益) 连乘
    for g in quantile_ret.columns:
        equity = (1 + quantile_ret[g].fillna(0)).cumprod()
        # 画每一组的净值曲线，标签是组号
        axes[0].plot(equity.index, equity.values, label=f"Q{g}")

    # 上图标题和坐标轴标签用英文，避免中文字体缺失问题
    axes[0].set_title(f"{factor_name} Quantile Backtest")
    axes[0].set_ylabel("Cumulative Return")
    axes[0].legend(ncol=5, fontsize=8)
    axes[0].grid(alpha=0.3)

    # 多空组合（最高组减最低组）的累计净值
    ls_equity = (1 + long_short.fillna(0)).cumprod()
    axes[1].plot(ls_equity.index, ls_equity.values, color="#d62728")
    axes[1].set_title("Long-Short (Top - Bottom)")
    axes[1].set_ylabel("Cumulative Return")
    axes[1].grid(alpha=0.3)

    # 自动调整间距
    fig.tight_layout()
    # 保存图片
    return _save_png(fig, output_dir, "layered_backtest.png")


def plot_portfolio(metrics, factor_name, output_dir):
    """画多空组合的净值和回撤图。"""
    # 创建上下两个子图
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

    # 净值曲线
    equity = metrics["累计净值"]
    axes[0].plot(equity.index, equity.values, color="#1f77b4")
    axes[0].set_title(f"{factor_name} Long-Short Net Equity")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.3)

    # 回撤曲线
    drawdown = metrics["回撤序列"]
    axes[1].plot(drawdown.index, drawdown.values, color="#d62728")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown")
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    return _save_png(fig, output_dir, "portfolio.png")


def write_report(summary_df, metrics, output_dir, factor_name,
                 quantile_summary=None, mono_corr=None):
    """把因子汇总表和组合指标写进 Markdown 报告。"""
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 用列表逐行拼报告内容
    lines = []
    lines.append("# 单因子研究报告")
    lines.append("")
    lines.append(f"- 组合因子：{factor_name}")
    lines.append(f"- 年化收益：{metrics['年化收益']:.2%}")
    lines.append(f"- 年化波动：{metrics['年化波动']:.2%}")
    lines.append(f"- 夏普比率：{metrics['夏普比率']:.2f}")
    lines.append(f"- 最大回撤：{metrics['最大回撤']:.2%}")
    lines.append("")
    lines.append("## 因子检验汇总")
    lines.append("")
    # 把 DataFrame 转成 Markdown 表格
    lines.append(summary_df.round(4).to_markdown())
    lines.append("")
    # 如果有分层各档收益，也写进报告
    if quantile_summary is not None:
        lines.append("## 分层各档年化收益")
        lines.append("")
        lines.append(quantile_summary.apply(lambda x: f"{x:.2%}").to_markdown())
        lines.append("")
        if mono_corr is not None:
            lines.append(f"- 单调性 Spearman 相关：{mono_corr:.3f}")
        lines.append("")
    lines.append("")
    lines.append("## 图表")
    lines.append("")
    lines.append("![分层回测](layered_backtest.png)")
    lines.append("")
    lines.append("![组合净值与回撤](portfolio.png)")
    lines.append("")
    lines.append("> 免责声明：本项目仅用于量化学习，结果不代表任何投资建议；"
                 "回测含未来函数、幸存者偏差、停牌处理不完整等已知局限。")
    lines.append("")

    # 写入报告文件
    report_path = os.path.join(output_dir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path
