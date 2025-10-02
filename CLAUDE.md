# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**khQuant（看海量化回测平台）** 是一个基于Python+PyQt5的A股量化交易回测系统，支持本地化部署、图形化操作、灵活的策略开发。

**版本**: V2.2.0
**技术栈**: Python 3.8+, PyQt5, pandas, xtquant(MiniQMT), mootdx(可选)

---

## 快速启动

### 环境配置
```bash
# 安装依赖
pip install -r requirements.txt

# 主要依赖
# - PyQt5==5.15.11 (GUI框架)
# - pandas==2.3.1, numpy==2.3.2
# - matplotlib==3.10.0
# - xtquant (MiniQMT接口)
# - holidays==0.69
```

### 启动命令
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

### 实用命令
```bash
# 检查依赖是否完整
python check_dependencies.py

# 查看当前版本信息
python -c "from version import get_version_info; print(get_version_info())"

# 测试相关命令
python test_settings.py          # 测试系统设置
python test_date_formats.py      # 测试日期格式处理
python test_record_count.py      # 测试数据记录统计
```

### MiniQMT前置依赖
1. 安装并启动MiniQMT客户端（勾选"极简模式"）
2. 在系统设置中配置`userdata_path`路径
3. 确保连接状态指示灯为绿色

---

## 核心架构（大局观）

### 模块层次关系

```
┌─────────────────────────────────────────────────┐
│  UI层: GUIkhQuant.py (主界面控制器)              │
│         ↕ QThread + pyqtSignal                  │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  框架层: khFrame.py (策略执行引擎)               │
│  - TriggerFactory (触发器工厂)                   │
│  - 回测循环控制                                  │
│  - 策略生命周期管理                              │
└─────────────────────────────────────────────────┘
        ↓                           ↓
┌──────────────────┐      ┌───────────────────────┐
│ 交易层:          │      │ 工具层:                │
│ khTrade.py       │      │ khQTTools.py          │
│ - 订单管理        │      │ - 数据获取            │
│ - 成本计算        │      │ - 交易日判断          │
│ - 持仓管理        │      │ - 便捷函数            │
│ - T+1模拟        │      │ MyTT.py (技术指标)    │
└──────────────────┘      └───────────────────────┘
        ↓                           ↓
┌─────────────────────────────────────────────────┐
│  数据抽象层: khDataProvider.py (V2.2.0新增)      │
│  - DataProviderInterface (统一接口)             │
│  - DataProviderFactory (工厂创建)               │
│  - 配置驱动切换数据源                            │
└─────────────────────────────────────────────────┘
        ↓                           ↓
┌──────────────────────┐  ┌───────────────────────┐
│  xtquant (MiniQMT)   │  │  mootdx (通达信)      │
│  - 实盘/模拟交易     │  │  - 回测历史数据(可选) │
│  - 精确复权数据      │  │  - 在线/离线模式      │
└──────────────────────┘  └───────────────────────┘
```

### 策略执行完整流程

```
1. 初始化阶段
   ├── khFrame.__init__() - 加载配置和策略模块
   ├── TriggerFactory.create_trigger() - 创建触发器
   ├── KhTradeManager() - 初始化虚拟交易账户
   └── strategy.init() - 调用策略初始化函数

2. 数据加载阶段
   ├── xtdata.get_market_data_ex() - 批量加载历史数据
   └── 提取所有时间点序列

3. 回测循环 (for timestamp in timeline)
   ├── 日期切换检测:
   │   ├── khPostMarket(data) - 前一日收盘后回调
   │   └── khPreMarket(data) - 新一日开盘前回调
   │
   ├── 构建数据字典:
   │   ├── __current_time__ (时间信息)
   │   ├── __account__ (账户信息)
   │   ├── __positions__ (持仓信息)
   │   ├── __stock_list__ (股票池)
   │   └── {股票代码: pandas.Series(OHLCV)}
   │
   ├── 触发器判断: trigger.should_trigger()
   ├── 风控检查: risk_mgr.check_risk()
   │
   ├── 调用策略: signals = khHandlebar(data)
   │
   ├── 处理信号: trade_mgr.process_signals()
   │   ├── 计算交易成本 (滑点+佣金+印花税+过户费+流量费)
   │   ├── 检查资金/持仓充足性
   │   ├── 更新账户资产和持仓
   │   └── 触发交易回调 (on_stock_order, on_stock_trade)
   │
   └── 记录回测结果

4. 结束阶段
   └── 生成回测报告
```

### 数据流转路径

```
MiniQMT数据源
    ↓ xtquant接口
历史数据 (DataFrame)
    ↓ 构建数据字典
data = {
    "000001.SZ": Series(open, high, low, close, volume),
    "__current_time__": {timestamp, date, time, datetime},
    "__account__": {cash, market_value, total_asset},
    "__positions__": {code: {volume, avg_price, can_use_volume}},
    "__stock_list__": [codes],
    "__framework__": framework实例
}
    ↓ 传入策略
signals = khHandlebar(data)
    ↓ 信号格式
[{
    "code": "000001.SZ",
    "action": "buy"/"sell",
    "price": 10.50,
    "volume": 1000,
    "reason": "金叉买入"
}]
    ↓ 交易处理
交易记录 + 持仓更新 + 资产变动
```

### 触发器系统设计

**工厂模式 + 策略模式**

```python
# 触发器基类 (khFrame.py)
class TriggerBase:
    def should_trigger(self, timestamp, data) -> bool:
        """判断是否触发策略"""
        raise NotImplementedError

    def get_data_period(self) -> str:
        """返回数据周期"""
        raise NotImplementedError

# 具体触发器
class TickTrigger(TriggerBase):
    """每个Tick触发"""
    def should_trigger(self, timestamp, data):
        return True

class KLineTrigger(TriggerBase):
    """K线周期触发（1m/5m/15m/30m/1h/1d）"""
    def should_trigger(self, timestamp, data):
        # 检查是否到达K线结束点
        # 避免同一根K线重复触发
        pass

class DailyTrigger(TriggerBase):
    """日线触发（支持盘前/盘后回调）"""
    pass

# 工厂类
class TriggerFactory:
    @staticmethod
    def create_trigger(framework, config):
        trigger_type = config["backtest"]["trigger"]["type"]
        # 根据配置创建对应触发器
        pass
```

**配置示例**:
```json
{
  "backtest": {
    "trigger": {
      "type": "1d",  // "tick"/"1m"/"5m"/"1d"/"custom"
      "pre_market": {"enabled": true, "time": "08:00:00"},
      "post_market": {"enabled": true, "time": "15:30:00"}
    }
  }
}
```

### 交易成本计算机制

**完整成本公式 (khTrade.py)**:

```python
# 1. 滑点计算
if slippage_type == "tick":
    # Tick模式: 按最小变动价跳数
    买入价 = 原价 + (tick_size × tick_count)
    卖出价 = 原价 - (tick_size × tick_count)
elif slippage_type == "ratio":
    # 比例模式: 按百分比
    买入价 = 原价 × (1 + ratio/2)
    卖出价 = 原价 × (1 - ratio/2)

# 2. 佣金 (双向)
佣金 = max(成交金额 × 0.0003, 5.0)

# 3. 印花税 (仅卖出)
印花税 = 成交金额 × 0.001

# 4. 过户费 (仅沪市,双向)
过户费 = 成交金额 × 0.00001

# 5. 流量费 (每笔固定)
流量费 = 0.1

# 6. 总成本
买入所需 = 成交金额 + 佣金 + 过户费 + 流量费
卖出到账 = 成交金额 - (佣金 + 印花税 + 过户费 + 流量费)
```

**示例计算**:
```python
# 买入1000股@10元
实际价格 = 10.00 × (1 + 0.001/2) = 10.005
佣金 = max(10005 × 0.0003, 5.0) = 5.0
过户费 = 10005 × 0.00001 = 0.10
流量费 = 0.1
买入支出 = 10005 + 5.0 + 0.10 + 0.1 = 10010.2元

# 卖出1000股@11元
实际价格 = 11.00 × (1 - 0.001/2) = 10.9945
佣金 = 5.0
印花税 = 10994.5 × 0.001 = 10.99
过户费 = 0.11
流量费 = 0.1
卖出到账 = 10994.5 - 16.2 = 10978.3元
```

### 事件驱动回调机制

**两层回调系统**:

```python
# 第1层: 策略层回调 (用户实现)
def init(stocks, data):
    """策略初始化回调"""
    pass

def khHandlebar(data) -> List[Dict]:
    """主策略逻辑回调 (每个触发点)"""
    return signals

def khPreMarket(data) -> List[Dict]:
    """盘前回调 (每日开盘前)"""
    return []

def khPostMarket(data) -> List[Dict]:
    """盘后回调 (每日收盘后)"""
    return []

# 第2层: 交易层回调 (框架实现)
class MyTraderCallback:
    def on_stock_order(self, order):
        """委托回报"""
        pass

    def on_stock_trade(self, trade):
        """成交回报"""
        pass

    def on_order_error(self, error_id, error_msg, order):
        """委托错误 (error_id: -1资金不足, -2持仓不足)"""
        pass

    def on_stock_position(self, positions):
        """持仓变动"""
        pass

    def on_stock_asset(self, assets):
        """资产变动"""
        pass
```

**事件流**:
```
市场数据到达 → 触发器判断 → khHandlebar() → 生成信号
→ process_signals() → 更新持仓/资金 → 触发交易回调
→ GUI日志更新
```

---

## 策略开发规范

### 最小化策略结构

```python
from khQuantImport import *

def init(stocks=None, data=None):
    """策略初始化 (必需但可为空)"""
    pass

def khHandlebar(data: Dict) -> List[Dict]:
    """主策略函数 (必需,必须返回信号列表)"""
    signals = []

    # 1. 获取当前股票
    stock_code = khGet(data, "first_stock")

    # 2. 获取当前价格
    current_price = khPrice(data, stock_code, "close")

    # 3. 计算指标
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
    # ========== 股票行情 (每个股票一个Series) ==========
    "000001.SZ": pd.Series({
        "time": 1727750100000,  # 毫秒级时间戳
        "open": 10.50,
        "high": 10.85,
        "low": 10.45,
        "close": 10.80,
        "volume": 1234567,
        "amount": 13246789.0
    }),

    # ========== 时间信息 (必需) ==========
    "__current_time__": {
        "timestamp": 1727750100,      # Unix时间戳(秒)
        "datetime": "2024-10-01 09:35:00",
        "date": "2024-10-01",
        "time": "09:35:00"
    },

    # ========== 账户信息 (必需) ==========
    "__account__": {
        "cash": 980000.0,             # 可用资金
        "frozen_cash": 0.0,           # 冻结资金
        "market_value": 20000.0,      # 持仓市值
        "total_asset": 1000000.0,     # 总资产
        "benchmark": "000300.SH"      # 基准指数
    },

    # ========== 持仓信息 (必需) ==========
    "__positions__": {
        "000001.SZ": {
            "volume": 1000,           # 总持仓
            "can_use_volume": 1000,   # 可卖数量(T+1)
            "avg_price": 10.50,       # 持仓均价
            "current_price": 10.80,   # 当前价
            "market_value": 10800.0,  # 持仓市值
            "profit": 300.0,          # 浮动盈亏
            "profit_ratio": 0.0286    # 盈亏比例
        }
    },

    # ========== 股票池 (必需) ==========
    "__stock_list__": ["000001.SZ", "000002.SZ"],

    # ========== 框架引用 (必需,供高级功能使用) ==========
    "__framework__": <KhQuantFramework实例>
}
```

### 交易信号格式 (返回值)

```python
signal = {
    "code": str,        # 必需: 股票代码 "000001.SZ"
    "action": str,      # 必需: "buy" 或 "sell"
    "price": float,     # 必需: 委托价格
    "volume": int,      # 必需: 委托数量 (必须是100的整数倍)
    "reason": str,      # 建议: 交易原因说明
    "timestamp": int,   # 可选: 时间戳 (自动填充)
}

# 示例1: 手动构建信号
signals = [{
    "code": "000001.SZ",
    "action": "buy",
    "price": 10.50,
    "volume": 1000,
    "reason": "金叉买入"
}]

# 示例2: 使用便捷函数 (推荐)
signals = khBuy(data, "000001.SZ", ratio=1.0, reason="满仓买入")
# ratio <= 1: 按仓位比例 (1.0=满仓, 0.5=半仓)
# ratio > 1: 按股数 (必须是100整数倍)

signals = khSell(data, "000001.SZ", ratio=0.5, reason="减半仓")
```

### 常用工具函数 (khQTTools.py)

```python
# ========== 时间判断 ==========
is_trade_time()                        # 是否交易时间(9:30-15:00)
is_trade_day("20241001")               # 是否交易日(排除周末和节假日)
get_trade_days_count(start, end)       # 计算交易日天数

# ========== 数据获取 ==========
khGet(data, "date")                    # 获取当前日期
khGet(data, "time")                    # 获取当前时间
khGet(data, "first_stock")             # 获取第一只股票代码
khGet(data, "total_asset")             # 获取总资产

khPrice(data, code, "close")           # 获取收盘价
khPrice(data, code, "open")            # 获取开盘价

khHas(data, code)                      # 检查是否持仓

# ========== 历史数据 ==========
khHistory(
    stock_code="000001.SZ",
    period="1d",                       # "1m"/"5m"/"1d"
    count=100,                         # 获取K线数量
    dividend_type="front"              # 复权类型: front/back/none
)

# ========== 技术指标 (封装) ==========
khMA(code, n=5, period="1d")           # 移动平均线
# 内部调用: khHistory() + MyTT.MA()

# ========== 信号生成 ==========
khBuy(data, code, ratio=1.0, reason="")
khSell(data, code, ratio=1.0, reason="")

generate_signal(data, code, "buy", ratio=1.0, reason="")
# 自动计算最大买入量或按比例/股数生成信号

# ========== 最大买入量计算 ==========
calculate_max_buy_volume(
    cash=100000,
    price=10.50,
    slippage_config={"type": "ratio", "ratio": 0.001},
    period="1d"
)
# 精确计算考虑所有成本的最大可买股数
```

### 技术指标库 (MyTT.py)

```python
from MyTT import *

# ========== 0级核心函数 ==========
REF(S, N)       # 序列后移N位
DIFF(S, N)      # 差分
SUM(S, N)       # N日累计和
HHV(S, N)       # N日最高价
LLV(S, N)       # N日最低价
MA(S, N)        # 简单移动平均
EMA(S, N)       # 指数移动平均
STD(S, N)       # 标准差

# ========== 1级应用函数 ==========
COUNT(S, N)     # N日内满足条件次数
EVERY(S, N)     # N日内全部满足
EXIST(S, N)     # N日内存在满足
CROSS(S1, S2)   # S1上穿S2 (金叉)

# ========== 2级技术指标 ==========
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

## 关键注意事项

### T+1制度模拟

**持仓结构**:
```python
position = {
    "volume": 1000,              # 总持仓数量
    "can_use_volume": 1000,      # 可卖数量 (T+1限制)
    "avg_price": 10.50,          # 持仓均价
    "yesterday_volume": 1000     # 昨日持仓
}
```

**关键规则**:
- 当日买入的股票 `can_use_volume` 不增加
- 次日开盘前或盘后回调时更新 `can_use_volume`
- 卖出时检查: `volume_to_sell <= can_use_volume`

**注意**: 当前代码在买入时直接增加 `can_use_volume`（khTrade.py:385行），未严格实现T+1，建议在日切时更新。

### 数据不泄露原则

**防止未来数据泄露**:
```python
# khHistory函数确保不包含当前时间点
# 获取历史数据时: end_time = current_time - 1个周期

# 错误示例
ma5 = MA(data["000001.SZ"]["close"], 5)  # 可能包含当前Bar

# 正确示例
hist = khHistory("000001.SZ", "1d", count=10)  # 不包含当前日
ma5 = MA(hist['close'], 5)
```

### 多进程安全

**子进程检测和保护** (khQTTools.py):
```python
def is_subprocess():
    """检查是否在子进程中"""
    return multiprocessing.current_process().name != 'MainProcess'

# 模块级自动执行
if is_subprocess():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
```

**线程安全通信**:
- 使用 `pyqtSignal` 跨线程传递数据
- 使用 `QMetaObject.invokeMethod` 调用GUI方法
- 策略在独立 `QThread` 中运行

### 配置文件格式 (.kh)

**配置文件创建方法**:

1. **通过GUI创建（推荐）**:
   - 启动 `python GUIkhQuant.py`
   - 在界面中配置所有参数
   - 点击"保存配置"按钮，系统自动生成 .kh 文件

2. **手动创建模板**:
   - 复制下方JSON模板
   - 保存为 `strategies/我的策略.kh`
   - 修改对应参数（注意：JSON不支持注释，实际使用时需删除注释）

**标准配置模板 (V2.2.0)**:

```json
{
  "system": {
    "run_mode": "backtest",                        // "backtest"/"simulate"/"live"
    "userdata_path": "D:/国金证券QMT交易端/userdata_mini",
    "session_id": 1234567890,
    "data_provider": {                             // V2.2.0新增：数据源配置
      "type": "mootdx",                            // "mootdx" (默认) / "xtquant"
      "mootdx": {
        "mode": "online",                          // "online" (在线) / "offline" (离线)
        "tdxdir": "",                              // 通达信目录 (仅offline需要)
        "use_cache": true,                         // 是否使用缓存
        "use_xtquant_for_adjust": true             // 复权数据是否用xtquant
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
      "type": "1d",                                // "tick"/"1m"/"5m"/"1d"
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
      "commission_rate": 0.0003,                   // 万三
      "min_commission": 5.0,
      "stamp_tax_rate": 0.001,                     // 千一(仅卖出)
      "flow_fee": 0.1,
      "slippage": {
        "type": "ratio",                           // "ratio"/"tick"
        "ratio": 0.001                             // 千一
      }
    }
  },
  "data": {
    "kline_period": "1d",
    "stock_list": ["000001.SZ", "600000.SH"]
  },
  "risk": {
    "position_limit": 0.95,                        // 最大仓位95%
    "order_limit": 100,
    "loss_limit": 0.1                              // 最大亏损10%
  },
  "strategy_file": "strategies/双均线策略.py"
}
```

### 数据源配置说明 (V2.2.0新增)

**支持的数据源**:

| 数据源 | 适用场景 | 优势 | 劣势 |
|--------|---------|------|------|
| **mootdx** (默认) | 回测 | 免费、支持离线、多种模式 | 需额外安装 |
| **xtquant** | 回测/模拟/实盘 | 官方接口、稳定可靠 | 需MiniQMT运行 |

**配置策略**:

```json
// 场景1: 回测使用mootdx (默认，推荐)
{
  "system": {
    "run_mode": "backtest",
    "data_provider": {
      "type": "mootdx",
      "mootdx": {
        "mode": "online",              // 在线模式，自动获取数据
        "use_cache": true,             // 使用缓存提高性能
        "use_xtquant_for_adjust": true // 复权数据使用xtquant
      }
    }
  }
}

// 场景2: 回测使用xtquant (兼容旧版)
{
  "system": {
    "run_mode": "backtest",
    "data_provider": {
      "type": "xtquant"  // 显式指定xtquant
    }
  }
}

// 场景3: 离线回测 (使用通达信本地数据)
{
  "system": {
    "run_mode": "backtest",
    "data_provider": {
      "type": "mootdx",
      "mootdx": {
        "mode": "offline",
        "tdxdir": "C:/通达信/TDXData",  // 通达信数据目录
        "use_cache": true
      }
    }
  }
}

// 场景4: 模拟/实盘交易 (强制xtquant)
{
  "system": {
    "run_mode": "simulate",  // 或 "live"
    // 无需配置data_provider，系统自动强制使用xtquant
  }
}
```

**关键规则**:
- ✅ 回测模式：默认使用mootdx，可配置为xtquant
- ✅ 模拟/实盘模式：**强制使用xtquant**（代码硬编码，配置文件无法覆盖）
- ✅ 向后兼容：不配置data_provider的旧配置仍可正常运行

**安装mootdx**:
```bash
pip install mootdx
```

### 股票代码格式

**标准格式**: `市场代码.股票代码`
- 上海: `sh.600000`, `sh.601318` 或 `600000.SH`, `601318.SH`
- 深圳: `sz.000001`, `sz.300001` 或 `000001.SZ`, `300001.SZ`

**注意事项**:
- 系统自动进行代码格式标准化（`600036` → `600036.SH`）
- 过户费仅沪市股票收取 (代码以 `6` 开头或 `sh.`/`.SH` 结尾)
- 数据下载时使用完整代码格式

---

## 常见开发任务

### 创建新策略

1. **在 `strategies/` 目录创建策略文件**:
```python
# strategies/我的策略.py
from khQuantImport import *

def init(stocks=None, data=None):
    print("策略初始化")

def khHandlebar(data):
    signals = []
    # 策略逻辑
    return signals
```

2. **创建对应配置文件**:
```bash
# strategies/我的策略.kh
{配置JSON}
```

3. **通过GUI加载并运行**:
- 启动 `python GUIkhQuant.py`
- 选择策略文件和配置文件
- 点击"启动策略"

### 调试策略

```python
# 方法1: 使用print输出 (会显示在GUI日志窗口)
def khHandlebar(data):
    stock_code = khGet(data, "first_stock")
    price = khPrice(data, stock_code, "close")
    print(f"当前价格: {price}")  # 显示在日志

# 方法2: 使用日志系统
import logging
logger = logging.getLogger(__name__)

def khHandlebar(data):
    logger.info(f"策略执行: {khGet(data, 'date')}")
    logger.debug(f"数据字典: {data.keys()}")

# 方法3: 保存中间结果
def khHandlebar(data):
    # 将调试信息写入文件
    with open("debug.txt", "a") as f:
        f.write(f"{khGet(data, 'date')}: {data}\n")
```

### 下载历史数据

```python
# 方法1: 通过GUI (推荐)
python GUI.py
# 添加股票代码 → 选择周期 → 点击下载

# 方法2: 通过代码
from xtquant import xtdata

xtdata.download_history_data2(
    stock_list=["000001.SZ", "600000.SH"],
    period="1d",
    start_time="20240101",
    end_time="20241231",
    incrementally=True  # 增量下载
)
```

### 查看回测结果

回测完成后自动弹出结果窗口，包含:
- 资产曲线图
- 收益率统计
- 回撤分析
- 交易记录明细

结果数据保存在: `backtest_results/策略名称_时间戳/`

---

## 测试与调试

### 测试文件说明

项目包含以下测试文件：

```python
test_settings.py           # 测试系统设置读写功能
test_date_formats.py       # 测试日期格式转换和处理
test_record_count.py       # 测试MiniQMT数据记录统计
test_supplement_debug.py   # 调试数据补充功能
test_time_fix.py          # 测试时间相关修复
```

### 运行测试

```bash
# 运行单个测试文件
python test_settings.py

# 检查依赖完整性（推荐首次运行）
python check_dependencies.py
```

### 常见故障排查

**问题1: MiniQMT连接失败**
```bash
# 检查步骤
1. 确认MiniQMT客户端已启动（任务管理器中查看进程）
2. 检查系统设置中的userdata_path路径是否正确
3. 在GUIkhQuant主界面观察连接状态指示灯
4. 查看日志窗口的连接错误信息
```

**问题2: 数据下载失败**
```python
# 使用GUI数据查看器诊断
python GUIDataViewer.py
# 查看已下载的数据文件是否完整

# 检查数据目录权限
# MiniQMT数据存储在: {userdata_path}/basedata/
```

**问题3: 策略回测报错**
```python
# 常见原因
1. 数据缺失：确保已下载对应周期的历史数据
2. 日期范围：检查回测起止日期是否在数据范围内
3. 股票池：验证股票代码格式（需带市场后缀如.SZ）
4. T+1限制：当日买入股票无法当日卖出

# 调试方法
# 在策略中添加详细日志输出
def khHandlebar(data):
    import logging
    logging.info(f"当前时间: {khGet(data, 'datetime')}")
    logging.info(f"账户资金: {khGet(data, 'cash')}")
    logging.info(f"持仓信息: {data['__positions__']}")
    # ... 策略逻辑
```

**问题4: GUI界面无响应**
```bash
# 策略运行时GUI可能暂时卡顿（正常现象）
# 策略在独立线程中运行，耐心等待完成
# 可通过日志窗口查看实时进度

# 如果长时间无响应（>5分钟）
# 1. 检查策略代码是否存在死循环
# 2. 检查是否在策略中执行了阻塞操作
# 3. 重启应用程序
```

### 日志系统

系统日志位置和配置：

```python
# 日志输出目标
1. GUI日志窗口（实时显示）
2. 控制台输出（如从命令行启动）
3. 日志文件（可在khConfig.py中配置）

# 在策略中使用日志
import logging
logger = logging.getLogger(__name__)

def khHandlebar(data):
    logger.debug("调试信息")    # 详细调试
    logger.info("一般信息")     # 关键流程
    logger.warning("警告信息")  # 潜在问题
    logger.error("错误信息")    # 错误情况
```

---

## API快速参考

### khQuantImport 模块

导入后自动包含:
```python
# 标准库
import os, sys, json, datetime, logging

# 数据处理
import numpy as np
import pandas as pd

# 量化库
from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader

# 工具类
from khQTTools import (
    TimeInfo, StockDataParser, PositionParser,
    StrategyContext, parse_context
)

# 便捷函数
from khQTTools import (
    khGet, khPrice, khHas, khBuy, khSell,
    khHistory, khMA, generate_signal,
    is_trade_time, is_trade_day
)

# 技术指标
from MyTT import (
    MA, EMA, BOLL, MACD, KDJ, RSI, CCI, ATR,
    CROSS, REF, DIFF, SUM, HHV, LLV
)
```

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
- 支持动态调整参数（如修改股票池）
- 提供扩展接口（如获取其他市场数据）

### 为何交易成本如此详细？
- **真实模拟**: 精确反映实盘交易成本
- **滑点区分**: 支持tick模式和比例模式
- **市场差异**: 区分沪深市场过户费
- **成本优化**: 帮助策略评估交易频率影响

### 为何使用独立QThread运行策略？
- **响应性**: 避免GUI界面冻结
- **可中断**: 支持用户停止策略
- **信号通信**: 实时更新日志和进度
- **异常隔离**: 策略错误不影响主界面

---

## 项目文件结构

```
khQuant/
├── GUIkhQuant.py          # 主界面（4851行）
├── khFrame.py             # 策略引擎（2666行）
├── khTrade.py             # 交易管理（560行）
├── khQTTools.py           # 工具集（2309行）
├── MyTT.py                # 技术指标库（624行）
├── khQuantImport.py       # 统一导入模块（521行）
├── khConfig.py            # 配置管理
├── khRisk.py              # 风险管理
├── khDataProvider.py      # 数据接口抽象层（600+行，V2.2.0新增）
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
├── test_*.py              # 测试文件
├── run_*.py               # 运行脚本
│
├── tests/                 # 测试目录（V2.2.0新增）
│   ├── test_data_provider.py       # 数据提供者单元测试
│   ├── benchmark_data_provider.py  # 性能基准测试
│   └── quick_test.py               # 快速功能验证
│
├── data/                  # 本地数据（如使用）
├── backtest_results/      # 回测结果
├── configs/               # 系统配置
├── requirements.txt       # 依赖列表
├── MIGRATION_PLAN.md      # 数据接口迁移方案（V2.2.0）
└── DATA_PROVIDER_README.md # 数据接口使用指南（V2.2.0）
```

---

## 数据接口抽象层 (V2.2.0新增)

### 概述

从 V2.2.0 版本开始，khQuant 引入了数据接口抽象层 ([khDataProvider.py](c:\github-repo\khQuant\khDataProvider.py))，采用适配器模式实现多数据源支持。

### 架构设计

```
┌─────────────────────────────────────────────────┐
│  策略层 (用户策略代码)                           │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  工具层 (khQTTools, khFrame)                    │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  抽象接口层 (DataProviderInterface)             │
│  • download_history_data()                      │
│  • get_market_data()                            │
│  • get_stock_list_in_sector()                   │
│  • normalize_stock_code()                       │
└─────────────────────┬───────────────────────────┘
                      │
      ┌───────────────┴────────────────┐
      │                                │
┌─────▼──────────┐         ┌──────────▼─────────┐
│  XtQuantAdapter │         │  MootdxAdapter     │
│  (MiniQMT)      │         │  (通达信)          │
│  - 实盘交易     │         │  - 免费数据源      │
│  - 稳定数据源   │         │  - 在线/离线模式   │
└─────────────────┘         └────────────────────┘
```

### 支持的数据源

| 数据源 | 类型 | 优势 | 劣势 | 适用场景 |
|-------|------|------|------|---------|
| **XtQuant** | 券商数据 | 稳定、支持实盘、复权准确 | 需要MiniQMT环境 | 实盘交易、精确回测 |
| **Mootdx** | 通达信数据 | 免费、无需客户端、易上手 | 复权有Bug、单次800条限制 | 学习、简单回测 |

### 基础使用

```python
from khDataProvider import DataProviderFactory

# 使用 XtQuant（默认）
provider = DataProviderFactory.get_provider('xtquant')

# 使用 Mootdx（在线模式）
provider = DataProviderFactory.get_provider('mootdx', mode='online')

# 获取数据
data = provider.get_market_data(
    stock_list=['600036.SH'],
    period='1d',
    start_time='20240101',
    end_time='20241231',
    fields=['open', 'high', 'low', 'close', 'volume'],
    dividend_type='front'  # 复权方式: 'front'前复权, 'back'后复权, 'none'不复权
)
```

### 配置方式

在策略配置文件 (.kh) 中指定数据源：

```json
{
  "system": {
    "data_provider": {
      "type": "mootdx",              // "xtquant" 或 "mootdx"
      "mootdx": {
        "mode": "online",            // "online" 或 "offline"
        "tdxdir": "C:/new_tdx"       // 离线模式的通达信目录
      }
    }
  }
}
```

### 重要说明

⚠️ **实盘交易仍需 XtQuant**

- Mootdx **不支持**实盘/模拟交易
- 实盘和模拟模式**必须**使用 XtQuant
- 回测模式可自由选择数据源

⚠️ **复权数据问题**

- Mootdx 的复权功能有已知Bug
- 建议使用混合模式：基础数据用 Mootdx，复权数据用 XtQuant

### 详细文档

- **完整使用指南**: [DATA_PROVIDER_README.md](c:\github-repo\khQuant\DATA_PROVIDER_README.md)
- **迁移方案**: [MIGRATION_PLAN.md](c:\github-repo\khQuant\MIGRATION_PLAN.md)
- **测试文件**: [tests/test_data_provider.py](c:\github-repo\khQuant\tests\test_data_provider.py)

---

## 开发注意事项

### Git版本控制

**建议的 .gitignore 配置**:

```gitignore
# Python缓存
__pycache__/
*.py[cod]
*$py.class
*.so

# 回测结果（通常不需要提交）
backtest_results/
*.log

# 系统配置（可能包含敏感路径）
configs/*.json
settings.json

# IDE配置
.vscode/
.idea/
*.swp
*.swo

# 数据文件（太大不适合提交）
data/
*.csv
*.pkl

# 临时文件
*.tmp
nul
debug.txt

# 个人配置备份
requirements_backup.txt

# 规范工作流临时目录
.spec-workflow/
```

### 代码修改建议

**修改核心模块时的注意事项**:

1. **khFrame.py（策略引擎）**:
   - 修改触发器逻辑前，理解完整的回测循环流程
   - 添加新触发器类型需更新TriggerFactory
   - 注意线程安全，策略在独立QThread运行

2. **khTrade.py（交易管理）**:
   - 修改交易成本计算影响所有策略回测结果
   - 修改T+1逻辑需同步更新持仓管理
   - 注意浮点数精度问题（使用round保留2位小数）

3. **khQTTools.py（工具集）**:
   - 修改便捷函数接口需更新所有使用该函数的策略
   - 添加新函数时需在khQuantImport.py中导出
   - 注意子进程兼容性（is_subprocess检测）

4. **MyTT.py（技术指标库）**:
   - 保持与通达信公式语法的一致性
   - 新增指标需编写测试用例
   - 注意Series索引对齐问题

### 常见开发陷阱

**1. 数据泄露风险**:
```python
# 错误：直接使用当前Bar数据计算指标
ma5 = MA(data["000001.SZ"]["close"], 5)  # 包含当前未完成的Bar

# 正确：使用khHistory获取历史数据
hist = khHistory("000001.SZ", "1d", count=10)
ma5 = MA(hist['close'], 5)  # 只包含已完成的Bar
```

**2. 浮点数比较**:
```python
# 错误：直接比较浮点数
if price == 10.50:  # 可能因精度问题失败

# 正确：使用容差比较
if abs(price - 10.50) < 0.01:
```

**3. T+1规则遗漏**:
```python
# 错误：忽略T+1限制
if condition:
    khBuy(data, code, 1.0)
    khSell(data, code, 1.0)  # 当天买入无法卖出

# 正确：检查可卖数量
if khHas(data, code):
    position = data["__positions__"][code]
    if position["can_use_volume"] > 0:
        khSell(data, code, 1.0)
```

**4. 股票代码格式**:
```python
# 错误格式
"000001"     # 缺少市场后缀
"sh600000"   # 市场前缀错误

# 正确格式
"000001.SZ"  # 深圳股票
"600000.SH"  # 上海股票
```

### 性能优化建议

1. **批量数据加载**: 使用`xtdata.get_market_data_ex`一次性加载所有股票数据
2. **避免重复计算**: 在`init`函数中预计算不变的指标参数
3. **减少日志输出**: 生产环境减少debug级别日志
4. **合理设置回测周期**: 超长周期回测建议分段进行

### 贡献代码指南

如果您希望为项目贡献代码：

1. **Fork项目并创建功能分支**
2. **遵循现有代码风格**（PEP 8规范）
3. **添加必要的注释和文档字符串**
4. **编写测试用例验证新功能**
5. **提交前运行`check_dependencies.py`确保环境兼容**
6. **Pull Request描述清楚改动内容和动机**

---

## 进一步学习

- **README.md**: 完整用户手册
- **项目文件说明.md**: 各模块功能概述
- **示例策略**: `strategies/双均线精简_使用khMA函数.py`
- **官方文档**: https://khsci.com/khQuant/tutorial/

---

**最后更新**: 2025-10-02
**适用版本**: V2.2.0
**更新内容**:

**V2.2.0 (2025-10-02)** - 数据接口抽象层:
- 🎉 **重大更新**: 新增数据接口抽象层 (khDataProvider.py)
- ✅ **核心模块改造**: khConfig.py, khQTTools.py, khFrame.py全部支持数据提供者切换
- ✅ **双数据源支持**: XtQuantAdapter (MiniQMT) + MootdxAdapter (通达信)
- ✅ **配置驱动切换**: 通过.kh配置文件灵活选择数据源
- ✅ **实盘保护机制**: 实盘/模拟模式强制使用xtquant
- ✅ **100%向后兼容**: 默认使用xtquant，不影响现有代码
- ✅ **设计模式应用**: 工厂模式 + 单例模式 + 适配器模式
- ✅ **完整测试覆盖**: 集成测试100%通过（5/5）
- 📝 **新增文件**:
  - khDataProvider.py (600+行)
  - MIGRATION_PLAN.md (完整迁移方案)
  - DATA_PROVIDER_README.md (使用文档)
  - PHASE2_COMPLETION_REPORT.md (阶段2报告)
  - PHASE3_TEST_REPORT.md (测试报告)
  - tests/test_phase2_simple.py (集成测试)
- 📝 更新 requirements.txt（添加 mootdx>=0.11.7）

**V2.1.3 (2025-10-02)**:
- 修复 requirements.txt 编码问题（UTF-16 → UTF-8）
- 添加"测试与调试"章节（测试文件说明、故障排查、日志系统）
- 补充实用命令参考（依赖检查、版本查询、测试运行）
- 添加配置文件创建指南（GUI创建和手动模板）
- 新增"开发注意事项"章节（Git版本控制、代码修改建议、常见陷阱、性能优化）
