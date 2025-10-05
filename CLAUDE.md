# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**khQuant（看海量化回测平台）** 是一个基于Python+PyQt5的A股量化交易回测系统，支持本地化部署、图形化操作、灵活的策略开发。

**版本**: V2.2.0
**技术栈**: Python 3.8+, PyQt5, pandas, xtquant(MiniQMT), mootdx(可选)
**项目类型**: 开源免费量化交易平台
**核心依赖**: MiniQMT (券商交易终端)

---

## 快速启动命令

### 环境设置
```bash
# 安装依赖
pip install -r requirements.txt

# 验证环境（推荐首次运行）
python check_dependencies.py
python tests/quick_test.py  # V2.2.0新增快速验证

# 查看版本信息
python -c "from version import get_version_info; print(get_version_info())"
```

### 启动应用
```bash
# 主界面（策略回测）
python GUIkhQuant.py

# 数据下载界面
python GUI.py

# 数据查看器
python run_data_viewer.py

# 定时数据补充
python run_scheduled_supplement.py
```

### 运行测试
```bash
# 单元测试
python test_settings.py          # 测试系统设置
python test_date_formats.py      # 测试日期格式
python test_record_count.py      # 测试数据统计

# 数据提供者测试（V2.2.0）
python tests/test_data_provider.py      # 完整单元测试套件
python tests/benchmark_data_provider.py # 性能基准对比
```

---

## 核心架构

### 三层架构设计

```
┌─────────────────────────────────────────────────┐
│  UI层 (PyQt5)                                   │
│  - GUIkhQuant.py: 主界面控制器                  │
│  - QThread异步执行策略                          │
│  - pyqtSignal跨线程通信                         │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  框架层 (策略引擎)                              │
│  - khFrame.py: 策略执行引擎                     │
│  - TriggerFactory: 触发器工厂（工厂模式）       │
│  - 回测循环控制                                 │
│  - 策略生命周期管理                             │
└─────┬──────────────────────────┬────────────────┘
      │                          │
┌─────▼──────────┐    ┌──────────▼─────────────┐
│  交易层        │    │  工具层                │
│  khTrade.py    │    │  khQTTools.py          │
│  - 订单管理    │    │  - 数据获取            │
│  - 成本计算    │    │  - 交易日判断          │
│  - 持仓管理    │    │  - 便捷函数            │
│  - T+1模拟     │    │  MyTT.py (技术指标库)  │
└────────┬───────┘    └────────┬───────────────┘
         │                     │
┌────────▼─────────────────────▼────────────────┐
│  数据抽象层 (V2.2.0新增)                      │
│  khDataProvider.py                            │
│  - DataProviderInterface (统一接口)          │
│  - DataProviderFactory (工厂模式)            │
│  - XtQuantAdapter / MootdxAdapter            │
└────────┬──────────────────────┬───────────────┘
         │                      │
┌────────▼──────────┐  ┌────────▼──────────────┐
│  xtquant          │  │  mootdx               │
│  (MiniQMT)        │  │  (通达信)             │
│  - 实盘/模拟交易  │  │  - 回测历史数据       │
└───────────────────┘  └───────────────────────┘
```

### 策略执行流程

```
初始化阶段:
  khFrame.__init__()
    ↓
  TriggerFactory.create_trigger()  # 工厂模式创建触发器
    ↓
  KhTradeManager()  # 虚拟账户初始化
    ↓
  strategy.init()  # 用户策略初始化

数据加载阶段:
  DataProvider.get_market_data()  # 批量加载历史数据
    ↓
  构建时间序列索引

回测循环 (for timestamp in timeline):
  ├─ 日期切换检测
  │   ├─ khPostMarket(data)  # 前一日收盘后
  │   └─ khPreMarket(data)   # 新一日开盘前
  │
  ├─ 构建数据字典
  │   ├─ __current_time__    # 时间信息
  │   ├─ __account__         # 账户信息
  │   ├─ __positions__       # 持仓信息
  │   ├─ __stock_list__      # 股票池
  │   └─ {股票代码: Series}  # 行情数据
  │
  ├─ trigger.should_trigger()  # 触发器判断
  ├─ risk_mgr.check_risk()     # 风控检查
  │
  ├─ signals = khHandlebar(data)  # 执行策略
  │
  ├─ trade_mgr.process_signals()  # 处理交易信号
  │   ├─ 计算交易成本 (滑点+佣金+印花税+过户费)
  │   ├─ 检查资金/持仓充足性
  │   ├─ 更新账户资产和持仓
  │   └─ 触发交易回调
  │
  └─ 记录回测结果

结束阶段:
  生成回测报告 → GUI展示
```

### 设计模式应用

**工厂模式**:
- `TriggerFactory`: 根据配置动态创建触发器类型 (TickTrigger/KLineTrigger/DailyTrigger)
- `DataProviderFactory`: 根据配置创建数据源适配器 (XtQuant/Mootdx)

**适配器模式**:
- `XtQuantAdapter`: 封装MiniQMT的xtquant接口
- `MootdxAdapter`: 封装通达信mootdx接口
- 统一的`DataProviderInterface`接口

**策略模式**:
- `TriggerBase`: 触发器基类，各子类实现不同触发逻辑

**单例模式**:
- `DataProviderFactory`: 确保同一配置返回相同的数据提供者实例

---

## 策略开发快速参考

### 最小化策略模板

```python
from khQuantImport import *

def init(stocks=None, data=None):
    """策略初始化 (必需但可为空)"""
    pass

def khHandlebar(data: Dict) -> List[Dict]:
    """主策略函数 (每个触发点调用)"""
    signals = []

    # 1. 获取股票代码
    stock_code = khGet(data, "first_stock")

    # 2. 获取当前价格
    current_price = khPrice(data, stock_code, "close")

    # 3. 计算技术指标
    ma5 = khMA(stock_code, 5)
    ma20 = khMA(stock_code, 20)

    # 4. 交易逻辑
    if ma5 > ma20 and not khHas(data, stock_code):
        signals = khBuy(data, stock_code, 1.0, reason="金叉买入")
    elif ma5 < ma20 and khHas(data, stock_code):
        signals = khSell(data, stock_code, 1.0, reason="死叉卖出")

    return signals

# 可选回调
def khPreMarket(data: Dict) -> List[Dict]:
    """开盘前回调"""
    return []

def khPostMarket(data: Dict) -> List[Dict]:
    """收盘后回调"""
    return []
```

### 数据字典结构 (data参数)

```python
data = {
    # 股票行情 (每个股票一个Series)
    "000001.SZ": pd.Series({
        "time": 1727750100000,  # 毫秒时间戳
        "open": 10.50,
        "high": 10.85,
        "low": 10.45,
        "close": 10.80,
        "volume": 1234567,
        "amount": 13246789.0
    }),

    # 时间信息
    "__current_time__": {
        "timestamp": 1727750100,      # Unix时间戳(秒)
        "datetime": "2024-10-01 09:35:00",
        "date": "2024-10-01",
        "time": "09:35:00"
    },

    # 账户信息
    "__account__": {
        "cash": 980000.0,
        "frozen_cash": 0.0,
        "market_value": 20000.0,
        "total_asset": 1000000.0,
        "benchmark": "000300.SH"
    },

    # 持仓信息
    "__positions__": {
        "000001.SZ": {
            "volume": 1000,           # 总持仓
            "can_use_volume": 1000,   # 可卖数量(T+1)
            "avg_price": 10.50,
            "current_price": 10.80,
            "market_value": 10800.0,
            "profit": 300.0
        }
    },

    # 股票池
    "__stock_list__": ["000001.SZ", "000002.SZ"],

    # 框架引用
    "__framework__": <KhQuantFramework实例>
}
```

### 常用工具函数

```python
# 时间判断
is_trade_time()                        # 是否交易时间(9:30-15:00)
is_trade_day("20241001")               # 是否交易日
get_trade_days_count(start, end)       # 计算交易日天数

# 数据获取
khGet(data, "date")                    # 获取当前日期
khGet(data, "time")                    # 获取当前时间
khGet(data, "first_stock")             # 获取第一只股票代码
khGet(data, "total_asset")             # 获取总资产

khPrice(data, code, "close")           # 获取收盘价
khPrice(data, code, "open")            # 获取开盘价

khHas(data, code)                      # 检查是否持仓

# 历史数据
khHistory(
    stock_code="000001.SZ",
    period="1d",                       # "1m"/"5m"/"1d"
    count=100,                         # K线数量
    dividend_type="front"              # 复权类型
)

# 技术指标 (封装)
khMA(code, n=5, period="1d")           # 移动平均线

# 信号生成
khBuy(data, code, ratio=1.0, reason="")
khSell(data, code, ratio=1.0, reason="")
# ratio <= 1: 按仓位比例 (1.0=满仓, 0.5=半仓)
# ratio > 1: 按股数 (必须是100整数倍)
```

### 技术指标库 (MyTT.py)

```python
from MyTT import *

# 基础函数
REF(S, N)       # 序列后移N位
DIFF(S, N)      # 差分
SUM(S, N)       # N日累计和
HHV(S, N)       # N日最高价
LLV(S, N)       # N日最低价
MA(S, N)        # 简单移动平均
EMA(S, N)       # 指数移动平均
STD(S, N)       # 标准差

# 应用函数
COUNT(S, N)     # N日内满足条件次数
EVERY(S, N)     # N日内全部满足
EXIST(S, N)     # N日内存在满足
CROSS(S1, S2)   # S1上穿S2 (金叉)

# 技术指标
BOLL(CLOSE, N=20, P=2)              # 布林带
MACD(CLOSE, SHORT=12, LONG=26, M=9) # MACD
KDJ(CLOSE, HIGH, LOW, N=9, M1=3, M2=3) # KDJ
RSI(CLOSE, N=14)                    # RSI
CCI(CLOSE, HIGH, LOW, N=14)         # CCI
ATR(CLOSE, HIGH, LOW, N=14)         # ATR

# 使用示例
hist = khHistory("000001.SZ", "1d", count=100)
ma5 = MA(hist['close'], 5)
ma20 = MA(hist['close'], 20)
if CROSS(ma5, ma20).iloc[-1]:
    print("金叉信号")
```

---

## 配置文件格式 (.kh)

### 标准配置模板 (V2.2.0)

```json
{
  "system": {
    "run_mode": "backtest",
    "userdata_path": "D:/国金证券QMT交易端/userdata_mini",
    "session_id": 1234567890,
    "data_provider": {
      "type": "mootdx",
      "mootdx": {
        "mode": "online",
        "tdxdir": "",
        "use_cache": true,
        "use_xtquant_for_adjust": false
      }
    }
  },
  "account": {
    "account_id": "test_account",
    "account_type": "SECURITY_ACCOUNT"
  },
  "backtest": {
    "start_time": "20240101",
    "end_time": "20241231",
    "init_capital": 1000000,
    "benchmark": "000300.SH",
    "trigger": {
      "type": "1d",
      "pre_market": {
        "enabled": true,
        "time": "08:00:00"
      },
      "post_market": {
        "enabled": true,
        "time": "15:30:00"
      }
    },
    "trade_cost": {
      "commission_rate": 0.0003,
      "min_commission": 5.0,
      "stamp_tax_rate": 0.001,
      "flow_fee": 0.1,
      "slippage": {
        "type": "ratio",
        "ratio": 0.001
      }
    }
  },
  "data": {
    "kline_period": "1d",
    "stock_list": ["000001.SZ", "600000.SH"]
  },
  "risk": {
    "position_limit": 0.95,
    "order_limit": 100,
    "loss_limit": 0.1
  },
  "strategy_file": "strategies/双均线策略.py"
}
```

### 数据源配置说明 (V2.2.0)

| 数据源 | 适用场景 | 优势 | 劣势 |
|--------|---------|------|------|
| **mootdx** (默认) | 回测 | 免费、支持离线、多种模式 | 需额外安装 |
| **xtquant** | 回测/模拟/实盘 | 官方接口、稳定可靠 | 需MiniQMT运行 |

**重要规则**:
- ✅ 回测模式：默认使用mootdx，可配置为xtquant
- ✅ 模拟/实盘模式：**强制使用xtquant** (硬编码，不可覆盖)
- ✅ 向后兼容：不配置data_provider的旧配置仍可运行

---

## 关键注意事项

### T+1制度模拟

⚠️ **已知Bug**: 当前代码在买入时直接增加 `can_use_volume`（[khTrade.py:385](khTrade.py#L385)），未严格实现T+1制度。

**正确实现**:
```python
# 当前实现（错误）
def _process_buy_signal():
    position["volume"] += volume
    position["can_use_volume"] += volume  # ❌ 应该在日切时更新

# 正确实现
def _on_new_trading_day():
    for code, pos in positions.items():
        pos["can_use_volume"] = pos["volume"]  # ✅ 日切时同步
```

### 数据不泄露原则

```python
# 错误：直接使用当前Bar数据
ma5 = MA(data["000001.SZ"]["close"], 5)  # 包含当前未完成Bar

# 正确：使用khHistory获取历史数据
hist = khHistory("000001.SZ", "1d", count=10)  # 不包含当前日
ma5 = MA(hist['close'], 5)
```

### 多线程安全

- 策略在独立 `QThread` 中运行
- 使用 `pyqtSignal` 跨线程传递数据
- 子进程自动设置 `QT_QPA_PLATFORM=offscreen`

### 股票代码格式

**标准格式**: `市场代码.股票代码`
- 上海: `600000.SH`, `601318.SH`
- 深圳: `000001.SZ`, `300001.SZ`

系统自动标准化代码格式 (`600036` → `600036.SH`)

---

## 常见开发任务

### 创建新策略

1. 在 `strategies/` 目录创建策略文件 (Python)
2. 创建对应配置文件 (.kh)
3. 通过GUI加载并运行

### 调试策略

```python
# 方法1: print输出 (显示在GUI日志窗口)
def khHandlebar(data):
    stock_code = khGet(data, "first_stock")
    price = khPrice(data, stock_code, "close")
    print(f"当前价格: {price}")

# 方法2: 日志系统
import logging
logger = logging.getLogger(__name__)

def khHandlebar(data):
    logger.info(f"策略执行: {khGet(data, 'date')}")
    logger.debug(f"数据字典: {data.keys()}")

# 方法3: 保存中间结果
def khHandlebar(data):
    with open("debug.txt", "a") as f:
        f.write(f"{khGet(data, 'date')}: {data}\n")
```

### 下载历史数据

```python
# 方法1: GUI (推荐)
python GUI.py

# 方法2: 代码
from xtquant import xtdata

xtdata.download_history_data2(
    stock_list=["000001.SZ", "600000.SH"],
    period="1d",
    start_time="20240101",
    end_time="20241231",
    incrementally=True
)
```

---

## 代码修改建议

### 修改核心模块注意事项

**khFrame.py (策略引擎)**:
- 修改触发器逻辑前理解完整回测循环
- 添加新触发器需更新TriggerFactory
- 注意线程安全 (QThread)

**khTrade.py (交易管理)**:
- 修改交易成本影响所有策略回测
- 修改T+1逻辑需同步持仓管理
- 注意浮点数精度 (round 2位小数)

**khQTTools.py (工具集)**:
- 修改函数接口需更新所有调用处
- 新增函数需在khQuantImport.py导出
- 注意子进程兼容性

**MyTT.py (技术指标库)**:
- 保持与通达信公式语法一致
- 新增指标需编写测试用例
- 注意Series索引对齐

### 常见开发陷阱

**1. 数据泄露风险**:
```python
# 错误
ma5 = MA(data["000001.SZ"]["close"], 5)  # 包含未完成Bar

# 正确
hist = khHistory("000001.SZ", "1d", count=10)
ma5 = MA(hist['close'], 5)
```

**2. 浮点数比较**:
```python
# 错误
if price == 10.50:  # 精度问题

# 正确
if abs(price - 10.50) < 0.01:
```

**3. T+1规则遗漏**:
```python
# 错误
khBuy(data, code, 1.0)
khSell(data, code, 1.0)  # 当天买入无法卖出

# 正确
if khHas(data, code):
    position = data["__positions__"][code]
    if position["can_use_volume"] > 0:
        khSell(data, code, 1.0)
```

**4. 股票代码格式**:
```python
# 错误
"000001"     # 缺少市场后缀
"sh600000"   # 格式错误

# 正确
"000001.SZ"  # 深圳
"600000.SH"  # 上海
```

---

## 项目文件结构

```
khQuant/
├── GUIkhQuant.py          # 主界面 (4851行)
├── khFrame.py             # 策略引擎 (2666行)
├── khTrade.py             # 交易管理 (560行)
├── khQTTools.py           # 工具集 (2309行)
├── MyTT.py                # 技术指标库 (624行)
├── khQuantImport.py       # 统一导入模块 (521行)
├── khConfig.py            # 配置管理
├── khRisk.py              # 风险管理
├── khDataProvider.py      # 数据接口抽象层 (V2.2.0)
│
├── GUI.py                 # 数据下载界面
├── GUIDataViewer.py       # 数据查看器
├── GUIScheduler.py        # 定时任务调度
├── SettingsDialog.py      # 系统设置
├── version.py             # 版本管理
├── update_manager.py      # 更新管理器
├── check_dependencies.py  # 依赖检查工具
│
├── strategies/            # 策略文件目录
│   ├── *.py              # Python策略
│   └── *.kh              # JSON配置
│
├── tests/                 # 测试目录 (V2.2.0)
│   ├── test_data_provider.py       # 数据提供者单元测试
│   ├── benchmark_data_provider.py  # 性能基准测试
│   └── quick_test.py               # 快速功能验证
│
├── backtest_results/      # 回测结果
├── requirements.txt       # 依赖列表
└── README.md              # 用户手册
```

---

## 数据接口抽象层 (V2.2.0)

### 架构设计

从 V2.2.0 开始，引入数据接口抽象层 ([khDataProvider.py](khDataProvider.py))，采用适配器模式实现多数据源支持。

```python
from khDataProvider import DataProviderFactory

# 使用 XtQuant (默认)
provider = DataProviderFactory.get_provider('xtquant')

# 使用 Mootdx (在线模式)
provider = DataProviderFactory.get_provider('mootdx', mode='online')

# 获取数据
data = provider.get_market_data(
    stock_list=['600036.SH'],
    period='1d',
    start_time='20240101',
    end_time='20241231',
    fields=['open', 'high', 'low', 'close', 'volume'],
    dividend_type='front'
)
```

### 支持的数据源

| 数据源 | 类型 | 优势 | 劣势 | 适用场景 |
|-------|------|------|------|---------|
| **XtQuant** | 券商数据 | 稳定、支持实盘、复权准确 | 需MiniQMT环境 | 实盘交易、精确回测 |
| **Mootdx** | 通达信数据 | 免费、无需客户端、易上手 | 复权有Bug、800条限制 | 学习、简单回测 |

⚠️ **重要说明**:
- Mootdx **不支持**实盘/模拟交易
- 实盘和模拟模式**必须**使用 XtQuant
- Mootdx 复权功能有已知Bug，建议混合模式

---

## API快速参考

### 触发器配置

| type值 | 说明 | 适用场景 |
|--------|------|----------|
| `"tick"` | 每个Tick触发 | 高频策略 |
| `"1m"` | 1分钟K线触发 | 短线策略 |
| `"5m"` | 5分钟K线触发 | 日内策略 |
| `"1d"` | 日线触发 | 趋势策略 |
| `"custom"` | 自定义时间触发 | 事件驱动策略 |

### 回调函数时机

| 函数 | 调用时机 | 返回值 |
|------|---------|--------|
| `init(stocks, data)` | 策略启动时一次 | 无 |
| `khHandlebar(data)` | 每个触发点 | `List[Dict]` 信号列表 |
| `khPreMarket(data)` | 每日开盘前 | `List[Dict]` 信号列表 |
| `khPostMarket(data)` | 每日收盘后 | `List[Dict]` 信号列表 |

### 交易回调

| 回调方法 | 触发时机 | 参数 |
|---------|---------|------|
| `on_stock_order(order)` | 委托下单时 | 委托信息字典 |
| `on_stock_trade(trade)` | 委托成交时 | 成交信息字典 |
| `on_order_error(error_id, msg, order)` | 委托错误时 | 错误ID(-1资金不足/-2持仓不足) |
| `on_stock_position(positions)` | 持仓变动时 | 全部持仓字典 |
| `on_stock_asset(assets)` | 资产变动时 | 资产信息字典 |

---

## 关键设计决策

### 为何使用工厂模式创建触发器？
- **扩展性**: 轻松添加新触发器类型，无需修改核心代码
- **配置驱动**: 通过JSON配置动态选择触发方式
- **解耦**: 策略代码与触发机制分离

### 为何数据字典包含 `__framework__` 引用？
- 允许高级策略访问框架内部状态
- 支持动态调整参数 (如修改股票池)
- 提供扩展接口 (如获取其他市场数据)

### 为何使用独立QThread运行策略？
- **响应性**: 避免GUI界面冻结
- **可中断**: 支持用户停止策略
- **信号通信**: 实时更新日志和进度
- **异常隔离**: 策略错误不影响主界面

---

## 进一步学习

- **README.md**: 完整用户手册
- **项目文件说明.md**: 各模块功能概述
- **示例策略**: [strategies/双均线精简_使用khMA函数.py](strategies/双均线精简_使用khMA函数.py)
- **官方文档**: https://khsci.com/khQuant/tutorial/
- **数据接口文档**: [DATA_PROVIDER_README.md](DATA_PROVIDER_README.md)

---

**最后更新**: 2025-10-05
**适用版本**: V2.2.0

**V2.2.2 (2025-10-05)** - CLAUDE.md优化:
- 🎯 重构文档结构，聚焦核心架构和常用命令
- ✨ 新增"快速启动命令"章节，提供实用命令速查
- 📐 简化架构图，突出三层设计和设计模式
- 🔧 整合"策略开发快速参考"，提供完整代码示例
- 📊 优化表格展示，增强可读性
- 🔗 添加文件路径引用链接
- 🗑️ 移除冗余内容，减少文档长度50%
- 💡 保留所有关键技术细节和已知问题说明
