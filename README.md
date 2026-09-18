# A股单因子研究工具（a-share-factor-lab）

一个用于学习的 A 股单因子研究最小框架，跑通从「数据 → 因子 → 预处理 → 检验 → 回测 → 报告」的完整链路。

目标不是给出一个能赚钱的策略，而是搭建一套能客观回答「某个因子到底有没有效」的研究工具。

## 功能

- 用 Tushare 下载沪深300成分股的前复权日线、换手率、行业、市值
- 构造动量（20/60/120 日）、反转、波动率、换手率因子
- 因子预处理：去极值（MAD winsorize）、市值/行业中性化、z-score 标准化
- 因子检验：IC、Rank IC、ICIR、t 检验
- 分层回测：分 5 组观察收益和单调性
- 多空组合回测：含交易成本，输出年化收益、夏普、最大回撤
- 自动生成 Markdown 报告和图表

## 项目结构

```text
a-share-factor-lab/
├── main.py                   # 主入口
├── config.yaml               # 配置
├── requirements.txt          # 依赖
├── .env.example              # 环境变量示例
├── scripts/
│   └── make_sample_data.py   # 离线生成自测样本数据
└── src/
    ├── config.py             # 读配置
    ├── fetch_data.py         # AkShare 数据源
    ├── fetch_data_tushare.py # Tushare 数据源
    ├── factors.py            # 因子构造
    ├── preprocess.py         # 去极值 / 中性化 / 标准化
    ├── factor_test.py        # IC / Rank IC / ICIR / t 检验
    ├── layered_backtest.py   # 分层回测
    ├── portfolio.py          # 多空组合与绩效
    └── report.py             # 报告与图表
```

## 快速开始（离线，不需要联网）

```bash
pip install -r requirements.txt
python scripts/make_sample_data.py   # 生成合成自测数据
python main.py
```

运行后会在 `output/` 生成 `report.md`、分层回测图和组合净值图。

## 使用真实数据（Tushare）

先设置环境变量（token 不写进代码，避免泄露）：

```bash
export TUSHARE_TOKEN="你的token"
export TUSHARE_URL="你的镜像地址"   # 可选，也可填在 config.yaml 的 tushare.url
```

然后下载并跑通：

```bash
python main.py --fetch --source tushare
```

也可以切换回 AkShare：`python main.py --fetch --source akshare`。

> 说明：真实行情数据不会提交到仓库，`data/processed/` 和 `output/` 已在 `.gitignore` 中忽略，需按上面脚本重新生成。

## 示例结果

下面是一次真实运行的输出（沪深300全成分、2020–2025 年，因子经过去极值、市值/行业中性化、标准化）：

![因子分层回测](docs/layered_backtest.png)

- 完整因子检验报告：[docs/report.md](docs/report.md)
- 多空组合净值与回撤图：[docs/portfolio.png](docs/portfolio.png)

## 配置

在 `config.yaml` 中可调整：股票池、回测区间、因子、预处理开关、分层组数、交易成本等。

## 已知局限（学习用途）

- 股票池采用期初固定成分快照，未做时点成分（point-in-time），存在选择偏差
- 市值中性化使用静态市值近似
- 分层回测未扣交易成本，且未做严格的停牌/幸存者偏差处理

## 免责声明

本项目仅用于量化学习，结果不代表任何投资建议，不能用于实盘决策。
