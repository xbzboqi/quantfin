# quantfin - 个人量化理财助手

基于 Python 的 A 股量化分析 CLI 工具，通过**多因子评分选品 + 估值择时**生成买卖信号和持有建议，支持微信推送日报。

> ⚠️ **免责声明**: 本工具仅供学习研究参考，不构成任何投资建议。投资有风险，入市需谨慎。

## 功能

| 功能 | 说明 |
|------|------|
| 多因子评分 | 10 因子 (动量/价值/质量/波动率/流动性) z-score 加权合成 0-100 分 |
| 估值择时 | 市场 PE/PB 百分位 + 股债利差 → 超卖/低估/中性/高估/过买 5 档信号 |
| 买入信号 | 综合评分 + 择时信号 → STRONG_BUY / BUY / WATCH |
| 止盈信号 | 到达目标收益 / PE过贵 / 评分下滑 → TAKE_PROFIT / SELL / REDUCE |
| 持有分类 | 短(1-3月) / 中(3-12月) / 长(12月+) 三级建议 |
| 微信推送 | PushPlus / WxPusher 推送 Markdown 日报 |

## 数据范围

- **A 股** (沪深): 多因子评分 + 估值择时
- **ETF**: 多因子评分 + 趋势跟踪
- **黄金**: 期货现价 + 短期趋势

不含：加密货币、美股、自动交易、Web UI。

## 快速开始

### 1. 环境要求

- Python 3.12+
- pip

### 2. 安装

```bash
git clone https://github.com/xbzboqi/quantfin.git
cd quantfin
pip install -e .
```

### 3. 配置

```bash
# 复制配置模板
cp config.yaml.example config.yaml

# 编辑 config.yaml 填入你的推送 token
# 或使用环境变量:
#   export PUSHPLUS_TOKEN="your_token"
#   export WXPUSHER_APP_TOKEN="your_app_token"
#   export WXPUSHER_UID="your_uid"
```

### 4. 运行

```bash
# 扫描 A 股
python -m quantfin scan stocks

# 扫描 ETF
python -m quantfin scan etfs

# 全市场扫描 + 黄金
python -m quantfin scan all

# 输出 Markdown 日报
python -m quantfin report

# 推送微信 (先配置 token)
python -m quantfin notify

# 预览报告不推送
python -m quantfin notify --dry-run

# 生成定时任务配置
python -m quantfin schedule
```

## 命令参考

```
quantfin scan stocks   [-n 20]    扫描 A 股 → Top N 排名
quantfin scan etfs     [-n 10]    扫描 ETF → Top N 排名
quantfin scan gold                查询黄金现价 + 趋势
quantfin scan all      [-n 20]    全市场扫描
quantfin report                   输出 Markdown 日报到 stdout
quantfin notify                  扫描 + 推送微信
quantfin notify --dry-run        仅生成报告，不推送
quantfin schedule                输出 crontab 配置建议
quantfin --version               查看版本
quantfin --help                  帮助信息
```

## 因子引擎

### 10 因子权重

| 因子 | 方向 | 默认权重 | 说明 |
|------|------|----------|------|
| momentum_3m | ↑ | 15% | 3 个月价格动量 |
| momentum_12m_1m | ↑ | 10% | 12-1 月动量 (Carhart) |
| pe_percentile | ↓ | 15% | PE 历史分位 (越低越好) |
| pb_percentile | ↓ | 10% | PB 历史分位 (越低越好) |
| roe | ↑ | 15% | 净资产收益率 |
| roe_stability | ↓ | 5% | ROE 波动性 (越稳越好) |
| gross_margin | ↑ | 10% | 毛利率 |
| volatility_60d | ↓ | 5% | 60 日波动率 |
| max_drawdown_60d | ↓ | 5% | 60 日最大回撤 |
| avg_turnover_20d | ↑ | 10% | 日均换手率 |

### 评分流程

1. 计算全市场每只股票的原始因子值
2. Winsorize 缩尾 (1% / 99%)
3. Z-score 标准化
4. 负向因子翻转
5. 加权合成 → 百分位排名 → 0-100 分

## 择时矩阵

| 市场 \ 个股 | PE<30% & PB<30% | PE>70% or PB>70% | 其他 |
|-------------|-----------------|------------------|------|
| 超卖 | 🔥 STRONG_BUY | HOLD | BUY |
| 低估 | BUY | HOLD | HOLD |
| 中性 | BUY | REDUCE | HOLD |
| 高估 | HOLD | REDUCE | REDUCE |
| 过买 | HOLD | SELL | SELL |

## 止盈规则

| 条件 | 信号 |
|------|------|
| 短期(≤3月)收益 ≥ 8% | TAKE_PROFIT |
| 中期(3-12月)收益 ≥ 15% | TAKE_PROFIT |
| 长期(>12月)收益 ≥ 25% | TAKE_PROFIT |
| PE 分位 > 95% | SELL |
| PE 分位 > 85% | REDUCE |
| 评分下降 > 50% + 动量为负 | SELL |
| 评分下降 > 30% | WEAKENING |

## 推送配置

### PushPlus

1. 注册 [pushplus.plus](https://www.pushplus.plus/)
2. 获取 token
3. 配置 `PUSHPLUS_TOKEN` 环境变量

### WxPusher

1. 注册 [wxpusher.zjiecode.com](https://wxpusher.zjiecode.com/)
2. 创建应用 → 获取 appToken 和 UID
3. 配置 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UID` 环境变量

## 定时运行

```bash
# Linux / macOS crontab
0 18 * * 1-5 cd /path/to/quantfin && python -m quantfin notify

# Windows 计划任务
schtasks /create /tn quantfin /tr "python -m quantfin notify" /sc daily /st 18:00
```

## 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 项目结构

```
quantfin/
├── quantfin/
│   ├── cli.py              # Click CLI 入口
│   ├── config.py           # YAML 配置加载
│   ├── data/               # AKShare 数据层 + 缓存
│   ├── factors/            # 5 因子模块 + 评分引擎
│   ├── valuation/          # 市场估值 + 个股估值 + 择时
│   ├── signals/            # 买入/止盈/持有/排名
│   ├── notify/             # PushPlus / WxPusher + 报告格式化
│   └── utils/              # 日志/重试/交易日历
├── tests/
├── config.yaml.example
├── pyproject.toml
├── requirements.txt
├── README.md
└── LICENSE
```

## License

MIT License. See [LICENSE](LICENSE).
