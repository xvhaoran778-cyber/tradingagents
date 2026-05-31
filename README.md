# Trading Agent — A股多智能体交易分析系统

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License">
  <img src="https://img.shields.io/github/stars/xvhaoran778-cyber/tradingagents?style=social" alt="Stars">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20OpenAI%20%7C%20Any-orange" alt="LLM Compatible">
</p>

**A 股多智能体交易分析系统** — 输入股票代码，自动调度 11 个 AI Agent 完成从数据采集到投资决策的全流程分析。支持任意 OpenAI 兼容 API（DeepSeek/OpenAI/Claude 等）。

[English](./README.md) | [中文](./README.md)

## 系统架构

```
用户输入（股票代码/名称）
    │
    ▼
┌─────────────────────────────────────┐
│           数据采集层                  │
│  mootdx + 腾讯 + 东财 + 同花顺 +...  │
│  K线/实时价/研报/新闻/资金流/公告     │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│          分析师团队（4 个 Agent）      │
│  技术分析 · 情绪分析 · 新闻 · 基本面  │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│          研究员辩论（多/空）           │
│  → 研究经理综合结论                   │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│  交易员 → 风控（激进/保守/中性）       │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│     投资组合经理（最终决策）           │
│  综合所有分析输出评级/目标价/风险提示   │
└─────────────────────────────────────┘
```

## 数据源

| 层 | 数据源 | 覆盖 |
|---|---|---|
| 行情 | mootdx + 腾讯财经 | K线、实时价、PE/PB |
| 研报 | 东财 reportapi | 研报列表、评级、EPS预测 |
| 信号 | 同花顺 + 百度 + 东财 | 热点题材、北向资金、龙虎榜、概念板块 |
| 资金面 | 东财 datacenter | 融资融券、大宗交易、股东户数、分红 |
| 新闻 | 东财 + 新浪 | 个股新闻、全球资讯 |
| 基本面 | mootdx + 东财 + 新浪 | F10、财报三表、季报37字段 |
| 公告 | 巨潮 cninfo | 沪深北全量公告 |

## 快速开始

```bash
# 1. 克隆
git clone <your-repo-url> && cd trading-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY（必填）

# 4. 运行
python main.py analyze 600036     # CLI 分析招商银行
python main.py interactive        # 交互模式
```

## Web 界面

```bash
python web_server.py --port 6789
# 浏览器打开 http://localhost:6789
```

支持：股票搜索、自动补全、历史记录、实时分析、结果导出。

## LLM 配置

支持任意 OpenAI 兼容 API：

| 方式 | 说明 |
|---|---|
| `.env` 文件 | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` |
| `llm_config.json` | 通过 Web 界面修改，优先级高于 `.env` |
| Web UI | 侧栏「LLM 设置」面板，保存后自动重启 |

## 项目结构

```
trading-agent/
├── main.py                 # CLI 入口
├── web_server.py           # Web 服务器
├── config.py               # 全局配置
├── agents/                 # LLM Agent
│   ├── analysts/           #   分析师（技术/情绪/新闻/基本面）
│   ├── researchers/        #   研究员（多头/空头/经理）
│   ├── trader/             #   交易员
│   ├── risk/               #   风控（激进/保守/中性）
│   ├── portfolio_manager.py #   投资组合经理
│   ├── base.py             #   Agent 基类
│   └── schemas.py          #   数据模型
├── data/                   # 数据源
│   ├── market.py           #   K线、技术指标、趋势分析
│   ├── realtime.py         #   腾讯实时行情
│   ├── news.py             #   新闻
│   ├── fundamentals.py     #   基本面
│   ├── signals.py          #   信号层（龙虎榜/北向/资金流等）
│   ├── signals_utils.py    #   东财限流工具
│   ├── filings.py          #   公告
│   ├── cache.py            #   缓存
│   └── search.py           #   搜索
├── llm/                    # LLM 客户端
│   ├── client.py           #   DeepSeek/OpenAI API 封装
│   └── prompts.py          #   Agent 提示词
├── workflow/                # 工作流
│   ├── pipeline.py         #   主流程编排
│   └── state.py            #   状态管理
├── memory/                  # 持久化
│   ├── database.py         #   SQLite
│   └── logger.py           #   决策日志
└── web/                     # 前端
    ├── index.html
    ├── app.js
    └── styles.css
```

## License

Apache License 2.0
