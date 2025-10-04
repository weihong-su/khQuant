# coding: utf-8
"""
KhQuant 统一导入模块
一行代码导入策略开发所需的所有常用模块和工具
使用方式: from khQuantImport import *
"""

# ===== 标准库导入 =====
import os
import sys
import json
import logging
import datetime
from datetime import datetime as dt, date, timedelta
from typing import Dict, List, Optional, Union, Tuple, Any

# ===== 数据处理库 =====
import numpy as np
import pandas as pd

# ===== 量化库 =====
from xtquant import xtdata
try:
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
except ImportError:
    # 如果没有交易模块，提供占位符
    XtQuantTrader = None
    XtQuantTraderCallback = None

# ===== 项目内部工具 =====
import khQTTools as _khq
from khQTTools import (
    generate_signal, calculate_max_buy_volume, KhQuTools, khMA,
    # 新增的独立函数，可以直接使用，无需实例化类
    is_trade_time, is_trade_day, get_trade_days_count
)
# 同时将 khQTTools 的其他常用工具函数暴露出来（如 khHistory 等）
from khQTTools import *

# ===== 指标库（MyTT） =====
import MyTT as _mytt
from MyTT import *  # 暴露 MA/RSI 等指标函数

# ===== 时间标准化类 =====
class TimeInfo:
    """标准化的时间信息类"""
    
    def __init__(self, data: Dict):
        """从策略数据中解析时间信息"""
        self._data = data
        self._current_time = data.get("__current_time__", {})
        
    @property
    def date_str(self) -> str:
        """返回标准日期格式: 2024-06-03"""
        return self._current_time.get("date", "")
    
    @property
    def date_num(self) -> str:
        """返回数字日期格式: 20240603"""
        date_str = self.date_str
        if date_str:
            return date_str.replace("-", "")
        return ""

    @property
    def time_str(self) -> str:
        """返回时间格式: 09:30:00"""
        return self._current_time.get("time", "")
    
    @property
    def datetime_str(self) -> str:
        """返回完整日期时间格式: 2024-06-03 09:30:00"""
        if self.date_str and self.time_str:
            return f"{self.date_str} {self.time_str}"
        return ""
    
    @property
    def datetime_num(self) -> str:
        """返回数字日期时间格式: 20240603093000"""
        if self.date_num and self.time_str:
            time_num = self.time_str.replace(":", "")
            return f"{self.date_num}{time_num}"
        return ""
    
    @property
    def datetime_obj(self) -> Optional[dt]:
        """返回datetime对象"""
        if self.datetime_str:
            try:
                return dt.strptime(self.datetime_str, "%Y-%m-%d %H:%M:%S")
            except:
                pass
        return None
    
    @property
    def timestamp(self) -> Optional[float]:
        """返回时间戳"""
        return self._current_time.get("timestamp")

# ===== 股票数据解析类 =====
class StockDataParser:
    """股票数据解析器"""
    
    def __init__(self, data: Dict):
        self._data = data
    
    def get(self, stock_code: str) -> Dict:
        """获取指定股票的完整数据"""
        return self._data.get(stock_code, {})
    
    def get_price(self, stock_code: str, field: str = "close") -> float:
        """获取指定股票的价格
        
        Args:
            stock_code: 股票代码
            field: 价格字段，如 'open', 'high', 'low', 'close', 'volume'
            
        Returns:
            float: 价格值，如果没有数据返回0.0
        """
        stock_data = self.get(stock_code)
        
        # 检查stock_data是否为空，需要特别处理pandas Series
        if stock_data is None:
            return 0.0
        
        # 对于pandas Series，需要特别处理空判断
        if hasattr(stock_data, 'empty'):
            # pandas Series/DataFrame
            try:
                if stock_data.empty:
                    return 0.0
            except Exception:
                # 如果empty检查失败，继续处理
                pass
        elif not stock_data:
            # 其他类型的空值检查
            return 0.0
            
        # 获取字段值
        value = None
        try:
            # 处理pandas Series对象
            if hasattr(stock_data, 'get'):
                # 类似字典的访问方式
                value = stock_data.get(field, 0.0)
            elif hasattr(stock_data, field):
                # 属性访问方式
                value = getattr(stock_data, field)
            elif hasattr(stock_data, '__getitem__'):
                # 索引访问方式
                try:
                    value = stock_data[field]
                except (KeyError, IndexError):
                    return 0.0
            else:
                return 0.0
        except Exception as e:
            logging.debug(f"获取字段 {field} 时出错: {str(e)}")
            return 0.0
            
        # 确保返回数值类型
        try:
            if value is None:
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            logging.debug(f"无法将 {value} 转换为float")
            return 0.0
    
    def get_close(self, stock_code: str) -> float:
        """获取收盘价"""
        return self.get_price(stock_code, "close")
    
    def get_open(self, stock_code: str) -> float:
        """获取开盘价"""
        return self.get_price(stock_code, "open")
    
    def get_high(self, stock_code: str) -> float:
        """获取最高价"""
        return self.get_price(stock_code, "high")
    
    def get_low(self, stock_code: str) -> float:
        """获取最低价"""
        return self.get_price(stock_code, "low")
    
    def get_volume(self, stock_code: str) -> float:
        """获取成交量"""
        return self.get_price(stock_code, "volume")

# ===== 持仓数据解析类 =====
class PositionParser:
    """持仓数据解析器"""
    
    def __init__(self, data: Dict):
        self._positions = data.get("__positions__", {})
    
    def has(self, stock_code: str) -> bool:
        """检查是否持有某股票"""
        return stock_code in self._positions and self._positions[stock_code].get("volume", 0) > 0
    
    def get_volume(self, stock_code: str) -> float:
        """获取持仓数量"""
        if stock_code in self._positions:
            return self._positions[stock_code].get("volume", 0)
        return 0
    
    def get_cost(self, stock_code: str) -> float:
        """获取持仓成本价"""
        if stock_code in self._positions:
            return self._positions[stock_code].get("avg_price", 0)
        return 0
    
    def get_all(self) -> Dict:
        """获取所有持仓"""
        return self._positions.copy()

# ===== 股票池解析类 =====
class StockPoolParser:
    """股票池解析器"""
    
    def __init__(self, data: Dict):
        self._stock_list = data.get("__stock_list__", [])
    
    def get_all(self) -> List[str]:
        """获取所有股票代码"""
        return self._stock_list.copy()
    
    def size(self) -> int:
        """获取股票池大小"""
        return len(self._stock_list)
    
    def contains(self, stock_code: str) -> bool:
        """检查是否包含某股票"""
        return stock_code in self._stock_list
    
    def first(self) -> Optional[str]:
        """获取第一个股票代码"""
        return self._stock_list[0] if self._stock_list else None

# ===== 策略上下文类 =====
class StrategyContext:
    """策略上下文，提供便捷的数据访问和信号生成方法"""
    
    def __init__(self, data: Dict):
        self.data = data
        self.time = TimeInfo(data)
        self.stocks = StockDataParser(data)
        self.positions = PositionParser(data)
        self.pool = StockPoolParser(data)
    
    def buy_signal(self, stock_code: str, ratio: float = 1.0, volume: Optional[int] = None, reason: str = "") -> Dict:
        """生成买入信号"""
        current_price = self.stocks.get_close(stock_code)
        if current_price <= 0:
            logging.warning(f"无法获取股票 {stock_code} 的价格信息")
            return {}
        
        if reason == "":
            reason = f"策略买入信号"
        
        signals = generate_signal(self.data, stock_code, current_price, ratio, 'buy', reason)
        return signals[0] if signals else {}
    
    def sell_signal(self, stock_code: str, ratio: float = 1.0, volume: Optional[int] = None, reason: str = "") -> Dict:
        """生成卖出信号"""
        current_price = self.stocks.get_close(stock_code)
        if current_price <= 0:
            logging.warning(f"无法获取股票 {stock_code} 的价格信息")
            return {}
        
        if reason == "":
            reason = f"策略卖出信号"
        
        signals = generate_signal(self.data, stock_code, current_price, ratio, 'sell', reason)
        return signals[0] if signals else {}

# ===== 便捷函数 =====
def parse_context(data: Dict) -> StrategyContext:
    """解析策略数据为上下文对象"""
    return StrategyContext(data)

def khGet(data: Dict, key: str) -> Any:
    """通用的数据获取函数
    
    Args:
        data: 策略数据字典
        key: 要获取的数据键，支持以下简洁格式：
            - 'date', 'date_str': 获取日期字符串 "2024-01-15"
            - 'date_num': 获取数字日期 "20240115"
            - 'time', 'time_str': 获取时间字符串 "09:30:00"
            - 'datetime', 'datetime_str': 获取完整日期时间 "2024-01-15 09:30:00"
            - 'datetime_obj': 获取 Python 的 datetime 对象
            - 'timestamp': 获取时间戳
            - 'cash': 获取可用资金
            - 'market_value': 获取持仓总市值
            - 'total_asset': 获取总资产
            - 'stocks': 获取所有股票代码
            - 'first_stock': 获取股票池第一个股票
            - 'positions': 获取所有持仓信息
    
    Returns:
        Any: 对应的数据值
    """
    # 时间相关
    if key in ["date", "date_str", "time", "time_str", "datetime", "datetime_str", "date_num", "timestamp", "datetime_obj"]:
        time_info = TimeInfo(data)
        if key in ["date", "date_str"]:
            return time_info.date_str
        elif key == "date_num":
            return time_info.date_num
        elif key in ["time", "time_str"]:
            return time_info.time_str
        elif key in ["datetime", "datetime_str"]:
            return time_info.datetime_str
        elif key == "timestamp":
            return time_info.timestamp
        elif key == "datetime_obj":
            return time_info.datetime_obj
    
    # 股票池相关
    elif key in ["first_stock", "stocks"]:
        pool = StockPoolParser(data)
        if key == "first_stock":
            return pool.first()
        elif key == "stocks":
            return pool.get_all()
    
    # 账户相关
    elif key in ["cash", "total_asset", "market_value"]:
        account = data.get("__account__", {})
        return account.get(key, 0)
    
    # 持仓相关
    elif key == "positions":
        positions = PositionParser(data)
        return positions.get_all()
    
    # 如果没有匹配到预定义键，直接从data中获取
    try:
        return data.get(key)
    except (AttributeError, TypeError):
        return None

def khPrice(data: Dict, stock_code: str, field: str = 'close') -> float:
    """获取股票价格的便捷函数
    
    Args:
        data: 策略数据字典
        stock_code: 股票代码
        field: 价格字段，默认为'close'
        
    Returns:
        float: 股票价格，如果获取失败返回0.0
    """
    try:
        stocks = StockDataParser(data)
        price = stocks.get_price(stock_code, field)
        
        # 首先检查是否为None
        if price is None:
            logging.warning(f"股票 {stock_code} 的 {field} 价格数据为None")
            return 0.0
        
        # 处理pandas Series的情况
        if hasattr(price, 'iloc'):
            # pandas Series
            try:
                if len(price) > 0:
                    price_val = price.iloc[-1]
                else:
                    logging.warning(f"股票 {stock_code} 的 {field} 价格Series为空")
                    return 0.0
            except Exception as e:
                logging.warning(f"处理pandas Series时出错: {str(e)}")
                return 0.0
        elif hasattr(price, '__len__') and hasattr(price, '__getitem__') and not isinstance(price, str):
            # 数组类型（但不是字符串）
            try:
                if len(price) > 0:
                    price_val = price[-1]
                else:
                    logging.warning(f"股票 {stock_code} 的 {field} 价格数组为空")
                    return 0.0
            except Exception as e:
                logging.warning(f"处理数组类型价格时出错: {str(e)}")
                return 0.0
        else:
            # 标量值
            price_val = price
        
        # 转换为float并检查有效性
        try:
            result = float(price_val)
            # 检查是否为有效数字
            if np.isnan(result) or np.isinf(result):
                # 价格为NaN通常是节假日或停牌,降级为DEBUG避免误导用户
                logging.debug(f"跳过 {stock_code} 的 {field} 数据 (值为{result}, 可能是节假日或停牌)")
                return 0.0
            return result
        except (ValueError, TypeError):
            # 数据转换失败也降级为DEBUG
            logging.debug(f"股票 {stock_code} 的 {field} 价格数据无法转换为数字: {price_val}")
            return 0.0
            
    except Exception as e:
        logging.error(f"获取股票 {stock_code} 价格时出错: {str(e)}")
        return 0.0

def khHas(data: Dict, stock_code: str) -> bool:
    """检查是否持有某股票的便捷函数
    
    Args:
        data: 策略数据字典
        stock_code: 股票代码
        
    Returns:
        bool: 是否持有该股票
    """
    try:
        positions = PositionParser(data)
        return positions.has(stock_code)
    except Exception as e:
        logging.error(f"检查持仓时出错: {str(e)}")
        return False

def khBuy(data: Dict, stock_code: str, ratio: float = 1.0, volume: Optional[int] = None, reason: str = "") -> Dict:
    """生成买入信号的便捷函数
    
    Args:
        data: 策略数据字典
        stock_code: 股票代码
        ratio: 买入比例，默认1.0（全仓）
        volume: 指定买入数量，如果提供则忽略ratio
        reason: 买入原因
        
    Returns:
        Dict: 买入信号字典
    """
    try:
        current_price = khPrice(data, stock_code)
        if current_price <= 0:
            logging.warning(f"无法获取股票 {stock_code} 的价格信息，跳过买入信号")
            return {}
        
        if reason == "":
            reason = f"策略买入 {stock_code}"
        
        signals = generate_signal(data, stock_code, current_price, ratio, 'buy', reason)
        return signals[0] if signals else {}
    except Exception as e:
        logging.error(f"生成买入信号时出错: {str(e)}")
        return {}

def khSell(data: Dict, stock_code: str, ratio: float = 1.0, volume: Optional[int] = None, reason: str = "") -> Dict:
    """生成卖出信号的便捷函数
    
    Args:
        data: 策略数据字典
        stock_code: 股票代码
        ratio: 卖出比例，默认1.0（全仓）
        volume: 指定卖出数量，如果提供则忽略ratio
        reason: 卖出原因
        
    Returns:
        Dict: 卖出信号字典
    """
    try:
        current_price = khPrice(data, stock_code)
        if current_price <= 0:
            logging.warning(f"无法获取股票 {stock_code} 的价格信息，跳过卖出信号")
            return {}
        
        if reason == "":
            reason = f"策略卖出 {stock_code}"
        
        signals = generate_signal(data, stock_code, current_price, ratio, 'sell', reason)
        return signals[0] if signals else {}
    except Exception as e:
        logging.error(f"生成卖出信号时出错: {str(e)}")
        return {}

def get_default_risk_params() -> Dict:
    """获取默认的风控参数"""
    return {
        "max_position": 1.0,  # 最大持仓比例
        "max_single_position": 0.3,  # 单只股票最大持仓比例
        "stop_loss": 0.1,  # 止损比例
        "stop_profit": 0.2,  # 止盈比例
    }



# ===== 导出所有符号 =====
__all__ = [
    # 标准库
    'os', 'sys', 'json', 'logging', 'datetime', 'dt', 'date', 'timedelta',
    'Dict', 'List', 'Optional', 'Union', 'Tuple', 'Any',
    
    # 数据处理
    'np', 'pd',
    
    # 量化库
    'xtdata', 'XtQuantTrader', 'XtQuantTraderCallback',
    
    # 内部工具
    'generate_signal', 'calculate_max_buy_volume', 'KhQuTools',
    
    # 时间工具函数 - 可直接使用，无需实例化类
    'is_trade_time', 'is_trade_day', 'get_trade_days_count',
    
    # 新增类和函数
    'TimeInfo', 'StockDataParser', 'PositionParser', 'StockPoolParser',
    'StrategyContext', 'parse_context', 'khGet', 'khPrice', 'khHas',
    'khBuy', 'khSell', 'get_default_risk_params',
    # 指标函数（MyTT）与项目内均线
    'MA', 'RSI', 'khMA'
] 

# 自动并入 khQTTools 与 MyTT 的所有公共符号，便于 from khQuantImport import * 统一入口
__all__ += [name for name in dir(_khq) if not name.startswith('_') and name not in __all__]
__all__ += [name for name in dir(_mytt) if not name.startswith('_') and name not in __all__]