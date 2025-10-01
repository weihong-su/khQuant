# 多进程保护 - 防止在子进程中意外启动Qt应用
import sys
import os

# 检查是否在子进程中，只在子进程中设置环境变量
def is_subprocess():
    """检查是否在子进程中"""
    import multiprocessing
    try:
        current_process = multiprocessing.current_process()
        return current_process.name != 'MainProcess'
    except:
        return False

# 只在子进程中设置环境变量
if is_subprocess():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['QT_LOGGING_RULES'] = 'qt.*=false'

import csv
import time
from datetime import datetime, timedelta
import pandas as pd
from xtquant import xtdata
# from xtquant.xtdata import get_client
import glob
import numpy as np
import logging
import ast
import holidays  # 添加这个导入，用于处理holidays.China()
from typing import Dict, List, Union, Optional
import math
from khTrade import KhTradeManager
from types import SimpleNamespace

# 延迟导入Qt相关模块，避免在子进程中意外启动Qt应用
try:
    if not is_subprocess():
        # 在主进程中正常导入Qt模块
        from PyQt5.QtCore import QThread, pyqtSignal
    else:
        # 在子进程中创建空的占位符类
        class QThread:
            def __init__(self):
                pass
            def start(self):
                pass
            def run(self):
                pass
        
        def pyqtSignal(*args, **kwargs):
            return lambda: None
except ImportError:
    # 如果导入失败，创建空的占位符类
    class QThread:
        def __init__(self):
            pass
        def start(self):
            pass
        def run(self):
            pass
    
    def pyqtSignal(*args, **kwargs):
        return lambda: None


# ============================================================================
# 独立函数版本 - 可以直接调用，无需实例化类
# ============================================================================

# 初始化全局变量
_trading_periods = [
    ("093000", "113000"),  # 上午
    ("130000", "150000")   # 下午
]
_cn_holidays = holidays.China()

def is_trade_time() -> bool:
    """判断是否为交易时间"""
    current = time.strftime("%H%M%S")
    
    for start, end in _trading_periods:
        if start <= current <= end:
            return True
    return False

def is_trade_day(date_str: str = None) -> bool:
    """判断是否为交易日（工作日且非法定节假日）
    
    Args:
        date_str: 日期字符串，支持格式：
                 - "YYYY-MM-DD" (如: "2024-12-25")
                 - "YYYYMMDD" (如: "20241225")
                 - None (默认为当天)
        
    Returns:
        bool: 是否为交易日
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 标准化日期格式
    try:
        # 尝试解析不同的日期格式
        date_obj = None
        
        # 格式1: YYYY-MM-DD
        if '-' in date_str and len(date_str) == 10:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        # 格式2: YYYYMMDD
        elif date_str.isdigit() and len(date_str) == 8:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
        else:
            # 尝试其他可能的格式
            for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"]:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
        
        if date_obj is None:
            raise ValueError(f"无法解析日期格式: {date_str}")
        
        # 首先排除周末 (5代表周六, 6代表周日)
        if date_obj.weekday() >= 5:
            return False
        
        # 使用holidays库判断是否为法定节假日
        date_only = date_obj.date()
        if date_only in _cn_holidays:
            return False
        
        # 非周末且非法定节假日，则视为交易日
        return True
        
    except Exception as e:
        print(f"判断交易日异常: {str(e)}")
        # 如果出现异常，尝试基本的日期解析
        try:
            # 再次尝试解析常见格式
            date_obj = None
            for fmt in ["%Y-%m-%d", "%Y%m%d"]:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            
            if date_obj is None:
                print(f"无法解析日期格式: {date_str}，默认按交易日处理")
                return True
                
            date_only = date_obj.date()
            if date_only in _cn_holidays:
                print(f"日期 {date_str} 是法定节假日（{_cn_holidays.get(date_only)}），非交易日")
                return False
            # 如果是周末，非交易日
            if date_obj.weekday() >= 5:
                print(f"日期 {date_str} 是周末，非交易日")
                return False
            return True
        except:
            # 实在判断不出来，默认为交易日
            print(f"无法确定 {date_str} 是否为交易日，默认按普通工作日处理")
            return True

def get_trade_days_count(start_date: str, end_date: str) -> int:
    """计算指定日期范围内的交易日天数
    
    Args:
        start_date: 起始日期，格式为"YYYY-MM-DD"
        end_date: 结束日期，格式为"YYYY-MM-DD"
        
    Returns:
        int: 交易日天数
    """
    try:
        # 解析起始和结束日期
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 确保开始日期不晚于结束日期
        if start_dt > end_dt:
            logging.error(f"起始日期 {start_date} 晚于结束日期 {end_date}")
            return 0
            
        # 初始化计数器
        trade_days = 0
        
        # 遍历日期范围内的每一天
        current_dt = start_dt
        while current_dt <= end_dt:
            current_date_str = current_dt.strftime("%Y-%m-%d")
            # 使用is_trade_day函数判断是否为交易日
            if is_trade_day(current_date_str):
                trade_days += 1
            
            # 前进到下一天
            current_dt += timedelta(days=1)
            
        logging.info(f"从 {start_date} 到 {end_date} 共有 {trade_days} 个交易日")
        return trade_days
        
    except Exception as e:
        logging.error(f"计算交易日天数时出错: {str(e)}")
        return 0

# ============================================================================
# 兼容性：保留原有的KhQuTools类，但让类方法调用上面的独立函数
# ============================================================================

class KhQuTools:
    """量化工具类（兼容性保留，推荐直接使用模块级函数）"""
    
    def __init__(self):
        # 为了兼容性保留这些属性，但实际会使用模块级函数
        self.trading_periods = _trading_periods
        self.cn_holidays = _cn_holidays
        
    def is_trade_time(self) -> bool:
        """判断是否为交易时间（调用模块级函数）"""
        return is_trade_time()
        
    def is_trade_day(self, date_str: str = None) -> bool:
        """判断是否为交易日（调用模块级函数）"""
        return is_trade_day(date_str)

    def get_trade_days_count(self, start_date: str, end_date: str) -> int:
        """计算指定日期范围内的交易日天数（调用模块级函数）"""
        return get_trade_days_count(start_date, end_date)

    def calculate_moving_average(self, stock_code: str, period: int, field: str = 'close', fre_step: str = '1d', end_time: Optional[str] = None, fq: str = 'pre') -> float:
        """计算移动平均线

        Args:
            stock_code: 股票代码
            period: 周期长度
            field: 计算字段，默认为'close'
            fre_step: 时间频率，如'1d', '1m'等
            end_time: 结束时间，如果为None使用当前时间
            fq: 复权方式，'pre'前复权, 'post'后复权, 'none'不复权

        Returns:
            float: 移动平均值

        Raises:
            ValueError: 如果不在交易时间（日内频率）或数据不足
        """
        from datetime import datetime
        if end_time is None:
            now = datetime.now()
            if fre_step in ['1m', '5m', 'tick']:
                end_time = now.strftime('%Y%m%d %H%M%S')
            else:
                end_time = now.strftime('%Y%m%d')

        # 结合 is_trade_time 判断（仅对日内频率）
        if fre_step in ['1m', '5m', 'tick'] and not self.is_trade_time():
            raise ValueError("不在交易时间内，无法计算日内移动平均线")

        # 获取历史数据（不包含当前时间点）
        data = khHistory(
            symbol_list=stock_code,
            fields=[field],
            bar_count=period,
            fre_step=fre_step,
            current_time=end_time,
            fq=fq,
            force_download=True  # 确保数据最新
        )

        if stock_code not in data or len(data[stock_code]) < period:
            raise ValueError(f"股票 {stock_code} 数据量不足 {period} 条，无法计算 MA{period}")

        prices = data[stock_code][field]
        return round(prices.mean(), 2)


def khMA(stock_code: str, period: int, field: str = 'close', fre_step: str = '1d', end_time: Optional[str] = None, fq: str = 'pre') -> float:
    """计算移动平均线（独立函数版本）

    Args:
        stock_code: 股票代码
        period: 周期长度
        field: 计算字段，默认为'close'
        fre_step: 时间频率，如'1d', '1m'等
        end_time: 结束时间，如果为None使用当前时间
        fq: 复权方式，'pre'前复权, 'post'后复权, 'none'不复权

    Returns:
        float: 移动平均值

    Raises:
        ValueError: 如果不在交易时间（日内频率）或数据不足
    """
    from datetime import datetime
    
    if end_time is None:
        now = datetime.now()
        if fre_step in ['1m', '5m', 'tick']:
            end_time = now.strftime('%Y%m%d %H%M%S')
        else:
            end_time = now.strftime('%Y%m%d')

    # 结合 is_trade_time 判断（仅对日内频率）
    tools = KhQuTools()
    if fre_step in ['1m', '5m', 'tick'] and not tools.is_trade_time():
        raise ValueError("不在交易时间内，无法计算日内移动平均线")

    # 获取历史数据（不包含当前时间点）
    data = khHistory(
        symbol_list=stock_code,
        fields=[field],
        bar_count=period,
        fre_step=fre_step,
        current_time=end_time,
        fq=fq,
        force_download=False  # 不强制下载数据，提高回测速度
    )

    if stock_code not in data or len(data[stock_code]) < period:
        raise ValueError(f"股票 {stock_code} 数据量不足 {period} 条，无法计算均线{period}")

    prices = data[stock_code][field]
    return round(prices.mean(), 2)


def calculate_max_buy_volume(data: Dict, stock_code: str, price: float, cash_ratio: float = 1.0) -> int:
    """
    计算最大可买入数量，考虑交易成本（包括滑点）

    Args:
        data: 策略接收的数据对象，包含账户信息 __account__ 和框架信息 __framework__
        stock_code: 股票代码
        price: 当前价格
        cash_ratio: 使用可用资金的比例，默认为1.0表示使用全部可用资金

    Returns:
        int: 最大可买入股数(按手取整)
    """
    try:
        # 导入交易管理类
        from khTrade import KhTradeManager

        # 获取账户信息
        account_info = data.get("__account__", {})
        if not account_info:
            logging.warning("无法获取账户信息，无法计算最大买入量")
            return 0

        # 获取资金信息
        available_cash = account_info.get("cash", 0.0)

        # 计算可用的资金
        usable_cash = available_cash * cash_ratio

        # 防止价格为0导致除零错误
        if price <= 0:
            logging.warning(f"股票 {stock_code} 价格异常: {price}，无法计算买入量")
            return 0

        # 对价格进行四舍五入处理，保留2位小数（A股价格精度为分）
        price = round(price, 2)

        # 获取框架对象
        framework = data.get("__framework__", None)
        
        # 获取配置对象
        if framework and hasattr(framework, 'config'):
            config = framework.config
        else:
            logging.warning("未从数据字典中获取到框架对象或框架配置不可用，将使用默认交易成本设置")
            config = SimpleNamespace(config_dict={"backtest": {"trade_cost": {}}})
            
        # 创建交易管理器实例（使用实际配置）
        trade_manager = KhTradeManager(config)
        
        # 获取交易成本参数
        commission_rate = trade_manager.commission_rate
        transfer_fee_rate = 0.00001 if stock_code.startswith("sh.") else 0.0  # 沪市股票才有过户费
        
        # 估算最大股数 (向下取整到100的倍数)
        # 使用更精确的初始估算方式
        estimated_shares = math.floor(usable_cash / price / (1 + commission_rate + transfer_fee_rate))
        shares = math.floor(estimated_shares / 100) * 100

        # 如果估算股数小于100，则无法买入
        if shares < 100:
            return 0

        # 逐步减少股数，使用calculate_trade_cost精确计算成本
        while shares >= 100:
            # 使用calculate_trade_cost计算实际交易成本（包括滑点）
            actual_price, trade_cost = trade_manager.calculate_trade_cost(
                price=price,
                volume=shares,
                direction="buy",
                stock_code=stock_code
            )
            
            # 计算总花费（实际价格 * 数量 + 交易成本）
            total_cost = actual_price * shares + trade_cost

            if total_cost <= usable_cash:
                logging.info(f"计算买入量: 股票={stock_code}, 原始价格={price:.2f}, 考虑滑点后价格={actual_price:.2f}, "
                           f"可用现金={available_cash:.2f}, 使用比例={cash_ratio:.2f}, "
                           f"计划买入={shares}, 成本={trade_cost:.2f}, 总花费={total_cost:.2f}")
                return int(shares) # 确保返回整数

            shares -= 100 # 减少一手

        return 0 # 循环结束仍未找到合适的买入量

    except Exception as e:
        logging.error(f"计算最大可买入数量时出错: {str(e)}", exc_info=True)
        return 0

def generate_signal(data: Dict, stock_code: str, price: float, ratio: float, action: str, reason: str = "") -> List[Dict]:
    """
    生成标准交易信号

    Args:
        data: 包含时间、账户、持仓信息的字典，以及框架信息 __framework__
        stock_code: 股票代码
        price: 交易价格
        ratio: 当ratio≤1时表示交易比例(买入时指占剩余现金比例，卖出时指占可卖持仓比例)
               当ratio>1时表示买入的股数（必须是100的整数倍）
        action: 'buy' 或 'sell'
        reason: 交易原因

    Returns:
        List[Dict]: 包含单个信号的列表，或空列表
    """
    signals = []
    current_time = data.get("__current_time__", {})
    timestamp = current_time.get("timestamp")
    
    # 对价格进行四舍五入处理，保留2位小数（A股价格精度为分）
    price = round(price, 2)

    if action == "buy":
        # 判断ratio是否大于1，若大于1则表示买入股数
        if ratio > 1:
            # 检查股数是否为整百
            target_volume = int(ratio)
            if target_volume % 100 != 0:
                error_msg = f"买入股数必须是100的整数倍: 股票={stock_code}, 输入股数={target_volume}"
                logging.error(error_msg)
                return []
            
            # 计算最大可买入量进行验证
            max_volume = calculate_max_buy_volume(data, stock_code, price, cash_ratio=1.0)
            if max_volume == 0:
                logging.warning(f"无法生成买入信号: 股票={stock_code}, 价格={price:.2f}, 目标股数={target_volume}, 但资金不足无法买入")
                return []
            elif target_volume > max_volume:
                logging.warning(f"目标买入量超过最大可买入量: 股票={stock_code}, 目标={target_volume}, 最大可买={max_volume}, 将调整为最大可买入量")
                actual_volume = max_volume
            else:
                actual_volume = target_volume
                
            signal = {
                "code": stock_code,
                "action": "buy",
                "price": price,  # 价格已在函数开始时四舍五入
                "volume": actual_volume,
                "reason": reason or f"按价格 {price:.2f} 买入 {actual_volume}股({actual_volume//100}手)"
            }
            if timestamp:
                signal["timestamp"] = timestamp
            signals.append(signal)
            logging.info(f"生成买入信号: {signal}")
        else:
            # ratio <= 1时按照资金比例计算可买入股数
            max_volume = calculate_max_buy_volume(data, stock_code, price, cash_ratio=ratio)
            if max_volume > 0:
                signal = {
                    "code": stock_code,
                    "action": "buy",
                    "price": price,  # 价格已在函数开始时四舍五入
                    "volume": max_volume,
                    "reason": reason or f"按价格 {price:.2f} 以 {ratio*100:.0f}% 资金比例买入"
                }
                if timestamp:
                    signal["timestamp"] = timestamp
                signals.append(signal)
                logging.info(f"生成买入信号: {signal}")
            else:
                logging.warning(f"无法生成买入信号: 股票={stock_code}, 价格={price:.2f}, 资金比例={ratio:.2f}, 计算可买量为0")

    elif action == "sell":
        positions_info = data.get("__positions__", {})
        if stock_code in positions_info:
            # 获取可卖数量，优先使用 'can_use_volume'，否则用 'volume'
            position_data = positions_info[stock_code]
            available_volume = position_data.get("can_use_volume", position_data.get("volume", 0))

            if available_volume > 0:
                # 计算要卖出的股数 (向下取整到100的倍数)
                sell_volume = math.floor((available_volume * ratio) / 100) * 100
                if sell_volume > 0:
                    signal = {
                        "code": stock_code,
                        "action": "sell",
                        "price": price,  # 价格已在函数开始时四舍五入
                        "volume": int(sell_volume), # 确保是整数
                        "reason": reason or f"按价格 {price:.2f} 卖出 {ratio*100:.0f}% 可用持仓"
                    }
                    if timestamp:
                        signal["timestamp"] = timestamp
                    signals.append(signal)
                    logging.info(f"生成卖出信号: {signal}")
                else:
                    logging.warning(f"无法生成卖出信号: 股票={stock_code}, 价格={price:.2f}, 持仓比例={ratio:.2f}, 计算可卖量为0 (可用持仓={available_volume})")
            else:
                logging.warning(f"无法生成卖出信号: 股票={stock_code} 无可用持仓")
        else:
            logging.warning(f"无法生成卖出信号: 股票={stock_code} 不在持仓中")

    return signals

def read_stock_csv(file_path):
    """
    读取股票CSV文件，支持多种编码格式，并进行错误处理。
    
    参数:
    - file_path: CSV文件路径
    
    返回:
    - tuple: (股票代码列表, 股票名称列表)
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 尝试的编码列表
    encodings = ['utf-8', 'gb18030', 'gbk', 'gb2312', 'utf-16', 'ascii']
    
    # 存储结果
    stock_codes = []
    stock_names = []
    
    # 尝试不同的编码
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                # 先读取少量内容来验证编码是否正确
                file.read(1024)
                file.seek(0)  # 重置文件指针到开始
                
                csv_reader = csv.reader(file)
                
                # 检查是否有BOM
                first_row = next(csv_reader)
                if first_row and first_row[0].startswith('\ufeff'):
                    first_row[0] = first_row[0][1:]  # 删除BOM
                
                # 处理第一行
                process_row(first_row, stock_codes, stock_names)
                
                # 处理剩余行
                for row in csv_reader:
                    process_row(row, stock_codes, stock_names)
                
                # 如果成功读取，跳出循环
                break
                
        except UnicodeDecodeError:
            # 如果是最后一个编码仍然失败，则抛出异常
            if encoding == encodings[-1]:
                raise Exception(f"无法读取文件 {file_path}，已尝试以下编码：{', '.join(encodings)}")
            continue
            
        except Exception as e:
            # 处理其他可能的异常
            raise Exception(f"读取文件 {file_path} 时发生错误: {str(e)}")

    return stock_codes, stock_names

def process_row(row, stock_codes, stock_names):
    """
    处理CSV的单行数据，处理带有交易所后缀的股票代码
    
    参数:
    - row: CSV行数据
    - stock_codes: 股票代码列表（会被修改）
    - stock_names: 股票名称列表（会被修改）
    """
    if len(row) >= 2:
        stock_code = row[0].strip()
        stock_name = row[1].strip()
        
        logging.info(f"处理股票: {stock_code} - {stock_name}")

        # 检查股票代码格式 - 简化筛选，只要有交易所后缀就接受
        if '.' in stock_code:  # 已经包含后缀
            # 接受所有标准格式的证券代码（包括股票、ETF、指数、可转债等）
            if stock_code.endswith(('.SH', '.SZ', '.BJ')):  # 支持上海、深圳、北交所
                stock_codes.append(stock_code)
                stock_names.append(stock_name)
                logging.info(f"添加证券: {stock_code} - {stock_name}")
            else:
                logging.info(f"跳过证券（交易所代码不支持）: {stock_code}")
        else:
            logging.info(f"跳过证券（无交易所后缀）: {stock_code}")

def download_and_store_data(local_data_path, stock_files, field_list, period_type, start_date, end_date, dividend_type='none', time_range='all', progress_callback=None, log_callback=None, check_interrupt=None):
    """
    下载并存储指定股票、字段、周期类型和时间段的数据到文件。

    函数功能:
        1. 从指定的股票代码列表文件中读取股票代码。
        2. 创建本地数据存储目录(如果不存在)。
        3. 对于每只股票:
           - 下载指定周期类型的数据到本地。
           - 从本地读取指定字段的数据。
           - 将 "time" 列转换为日期时间格式。
           - 如果指定了时间段,则筛选出指定时间段内的数据。
           - 将筛选出的数据添加到结果 DataFrame 中。
           - 将结果 DataFrame 存储到本地文件。
        4. 输出数据读取和存储完成的提示信息。

    文件命名规则:
        - 存储的文件名格式: "{股票代码}_{周期类型}_{起始日期}_{结束日期}_{时间段}_{复权方式}.csv"
        - 示例1: "000001.SZ_tick_20240101_20240430_all_none.csv"
          - 股票代码: 000001.SZ
          - 周期类型: tick
          - 起始日期: 20240101
          - 结束日期: 20240430
          - 时间段: all (表示全部时间段)
          - 复权方式: none (表示不复权)
        - 示例2: "000001.SZ_1d_20240101_20240430_all_front.csv"
          - 复权方式: front (表示前复权)
        - 如果指定了具体的时间段,时间段部分将替换为 "HH_MM-HH_MM" 的格式
          - 示例: "000001.SZ_1m_20240101_20240430_09_30-11_30_none.csv"
          - 时间段: 09_30-11_30 (表示 09:30 到 11:30 的时间段)

    参数:
    - local_data_path (str): 本地数据存储路径。
      - 该参数指定存储数据的本地目录路径。
      - 如果目录不存在，会自动创建。
      - 示例: "I:/stock_data_all_2"
      
    - stock_files (list): 股票代码列表文件路径列表。
      - 该参数指定包含股票代码的文件路径列表。
      - 每个文件应包含股票代码和名称两列。
      - 支持的股票类型：
        - A股：上海（600/601/603/605/688）、深圳（000/002/300/301）
        - 指数：上证（000）、深证（399）
      - 示例: ["HS300idx.csv", "otheridx.csv"]
      
    - field_list (list): 要存储的字段列表。
      - 该参数指定要下载和存储的股票数据字段列表。
      - 常用字段包括：open（开盘价）、high（最高价）、low（最低价）、close（收盘价）、
                    volume（成交量）、amount（成交额）等。
      - 示例: ["open", "high", "low", "close", "volume"]
      
    - period_type (str): 要读取的周期类型。
      - 该参数指定要下载和存储的数据周期类型。
      - 可选值: 
        - 'tick': 逐笔数据
        - '1m': 1分钟线
        - '5m': 5分钟线
        - '1d': 日线数据
      - 示例: "1d"
      
    - start_date (str): 起始日期。
      - 该参数指定数据的起始日期。
      - 格式为 "YYYYMMDD"。
      - 示例: "20240101"
      
    - end_date (str): 结束日期。
      - 该参数指定数据的结束日期。
      - 格式为 "YYYYMMDD"。
      - 示例: "20240430"

    - dividend_type (str, optional): 复权方式。
      - 该参数指定数据的复权方式，默认为'none'。
      - 可选值:
        - 'none': 不复权，使用原始价格
        - 'front': 前复权，基于最新价格进行前复权计算
        - 'back': 后复权，基于首日价格进行后复权计算
        - 'front_ratio': 等比前复权，基于最新价格进行等比前复权计算
        - 'back_ratio': 等比后复权，基于首日价格进行等比后复权计算
      - 注意：复权设置仅对股票价格数据有效，对指数和成交量等数据无影响
      - 示例: "front"
      
    - time_range (str, optional): 要读取的时间段。
      - 该参数指定要筛选的数据时间段。
      - 格式为 "HH:MM-HH:MM"。
      - 如果指定为 "all"，则不进行时间段筛选，保留全部时间段的数据。
      - 仅对分钟和tick级别数据有效。
      - 示例: "09:30-11:30" 或 "all"
      
    - progress_callback (function, optional): 进度回调函数。
      - 该函数用于更新下载进度。
      - 接受一个整数参数，表示完成百分比（0-100）。
      - 可用于更新GUI进度条等。
      
    - log_callback (function, optional): 日志回调函数。
      - 该函数用于记录处理过程中的日志信息。
      - 接受一个字符串参数，表示日志消息。
      - 可用于在GUI中显示处理状态等。
    
    - check_interrupt (function, optional): 中断检查函数。
      - 该函数用于检查是否需要中断下载过程。
      - 返回True表示需要中断，返回False表示继续执行。

    返回值:
    - 无返回值，数据直接保存到指定目录。

    异常:
    - 如果股票代码文件不存在或格式错误，会记录警告并跳过。
    - 如果数据下载失败，会记录错误并继续处理下一只股票。
    - 如果保存文件失败，会记录错误信息。
    - 如果中断检查函数返回True，会抛出InterruptedError异常。
    """
    try:
        # 获取所有股票代码
        stocks = []
        for stock_file in stock_files:
            # 检查是否需要中断
            if check_interrupt and check_interrupt():
                logging.info("下载过程被中断")
                raise InterruptedError("下载过程被用户中断")
                
            if os.path.exists(stock_file):
                logging.info(f"读取股票文件: {stock_file}")
                codes, names = read_stock_csv(stock_file)
                stocks.extend(codes)
        
        logging.info(f"股票列表: {stocks}")
        
        if not os.path.exists(local_data_path):
            os.makedirs(local_data_path)

        total_stocks = len(stocks)
        for index, stock in enumerate(stocks, 1):
            try:
                # 检查是否需要中断
                if check_interrupt and check_interrupt():
                    logging.info("下载过程被中断")
                    raise InterruptedError("下载过程被用户中断")
                    
                if log_callback:
                    log_callback(f"正在处理 {stock} ({index}/{total_stocks})")

                # 判断是否为指数
                is_index = stock in ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH", 
                                   "000300.SH", "000905.SH", "000852.SH"]

                try:
                    # 每次主要操作前检查中断
                    if check_interrupt and check_interrupt():
                        logging.info("下载过程被中断")
                        raise InterruptedError("下载过程被用户中断")
                        
                    if is_index:
                        # 指数数据处理
                        logging.info(f"获取指数数据: {stock}")
                        xtdata.download_history_data(stock, period=period_type, 
                                                   start_time=start_date, end_time=end_date)
                        
                        # 再次检查中断
                        if check_interrupt and check_interrupt():
                            logging.info("下载过程被中断")
                            raise InterruptedError("下载过程被用户中断")
                            
                        data = xtdata.get_market_data_ex(
                            field_list=['time'] + field_list,
                            stock_list=[stock],
                            period=period_type,
                            start_time=start_date,
                            end_time=end_date,
                            count=-1,
                            dividend_type=dividend_type,  # 添加复权参数
                            fill_data=True
                        )
                        if data and stock in data:
                            df = data[stock]
                            logging.info(f"成功获取指数数据: {stock}")
                        else:
                            raise Exception(f"未能获取指数数据: {stock}")
                    else:
                        # 普通股票数据处理
                        logging.info(f"获取股票数据: {stock}")
                        xtdata.download_history_data(stock, period=period_type, 
                                                   start_time=start_date, end_time=end_date)
                        
                        # 再次检查中断
                        if check_interrupt and check_interrupt():
                            logging.info("下载过程被中断")
                            raise InterruptedError("下载过程被用户中断")
                            
                        data = xtdata.get_local_data(  
                            field_list=['time'] + field_list,
                            stock_list=[stock],
                            period=period_type,
                            start_time=start_date,
                            end_time=end_date,
                            dividend_type=dividend_type,  # 添加复权参数
                            fill_data=True
                        )
                        df = data[stock]

                    # 检查中断
                    if check_interrupt and check_interrupt():
                        logging.info("下载过程被中断")
                        raise InterruptedError("下载过程被用户中断")
                        
                    # 开始数据处理和保存
                    logging.debug(f"准备处理数据 - 股票代码: {stock}")
                    
                    # 检查df是否为DataFrame类型
                    if not isinstance(df, pd.DataFrame):
                        error_msg = f"处理 {stock} 数据失败: 返回的数据不是DataFrame格式"
                        logging.error(error_msg)
                        if log_callback:
                            log_callback(error_msg)
                        continue
                        
                    logging.debug(f"原始数据形状: {df.shape}")
                    logging.debug(f"原始数据列: {df.columns.tolist()}")
                    
                    # 统一的数据处理逻辑
                    df["time"] = pd.to_datetime(df["time"].astype(float), unit='ms') + pd.Timedelta(hours=8)
                    logging.debug(f"时间列转换后的前5行:\n{df['time'].head()}")

                    if period_type == '1d':
                        df["date"] = df["time"].dt.strftime("%Y-%m-%d")
                        df = df[["date"] + field_list]
                    else:
                        if time_range != 'all':
                            start_time, end_time = time_range.split('-')
                            start_time = datetime.strptime(start_time, "%H:%M").time()
                            end_time = datetime.strptime(end_time, "%H:%M").time()
                            df["time_obj"] = df["time"].dt.time
                            mask = (df["time_obj"] >= start_time) & (df["time_obj"] <= end_time)
                            df = df.loc[mask].copy()
                            df.drop(columns=["time_obj"], inplace=True)
                        
                        df["date"] = df["time"].dt.strftime("%Y-%m-%d")
                        df["time"] = df["time"].dt.strftime("%H:%M:%S")
                        df = df[["date", "time"] + field_list]

                    # 检查中断
                    if check_interrupt and check_interrupt():
                        logging.info("下载过程被中断")
                        raise InterruptedError("下载过程被用户中断")
                        
                    # 保存数据
                    logging.debug(f"准备保存数据 - 股票代码: {stock}")
                    logging.debug(f"处理后数据形状: {df.shape}")
                    logging.debug(f"处理后数据列: {df.columns.tolist()}")
                    logging.debug(f"处理后前5行数据:\n{df.head()}")
                    
                    if not df.empty:
                        time_range_filename = time_range.replace(":", "_")
                        # 在文件名中添加复权信息
                        file_name = f"{stock}_{period_type}_{start_date}_{end_date}_{time_range_filename}_{dividend_type}.csv"
                        file_path = os.path.join(local_data_path, file_name)
                        
                        logging.info(f"保存文件 - 路径: {file_path}")
                        df.to_csv(file_path, index=False)
                        logging.info(f"文件保存成功: {file_path}")
                        
                        # 验证文件是否成功保存并获取更多信息
                        if os.path.exists(file_path):
                            file_size = os.path.getsize(file_path)
                            # 获取文件大小的可读形式
                            if file_size < 1024:
                                readable_size = f"{file_size} 字节"
                            elif file_size < 1024 * 1024:
                                readable_size = f"{file_size/1024:.2f} KB"
                            else:
                                readable_size = f"{file_size/(1024*1024):.2f} MB"
                                
                            # 获取行数和列数信息
                            rows_count = len(df)
                            cols_count = len(df.columns)
                            
                            logging.info(f"已保存文件信息: 大小={readable_size}, 行数={rows_count}, 列数={cols_count}")
                            
                            # 通过log_callback提供详细信息
                            if log_callback:
                                file_info = f"{stock} {period_type} 数据已存储: 文件大小={readable_size}, 行数={rows_count}, 列数={cols_count}, 路径: {file_path}"
                                log_callback(file_info)
                        else:
                            logging.error(f"文件保存失败: {file_path}")
                            if log_callback:
                                log_callback(f"保存失败: {file_path}")
                    else:
                        logging.warning(f"股票 {stock} 的数据为空，跳过保存")
                        if log_callback:
                            log_callback(f"股票 {stock} 的数据为空，跳过保存")

                except InterruptedError:
                    logging.info(f"处理{stock}时被中断")
                    raise
                except Exception as e:
                    logging.error(f"处理{stock}时出错: {str(e)}", exc_info=True)
                    raise

                if progress_callback:
                    progress_callback(int(index / total_stocks * 100))
                
                # 检查中断
                if check_interrupt and check_interrupt():
                    logging.info("下载过程被中断")
                    raise InterruptedError("下载过程被用户中断")
                    
                time.sleep(1)  # 添加延迟避免请求过快

            except InterruptedError:
                logging.info(f"处理股票 {stock} 时被用户中断")
                raise
            except Exception as e:
                logging.error(f"处理股票 {stock} 时出错: {str(e)}", exc_info=True)
                raise
        
        if log_callback:
            log_callback("数据下载和存储完成.")

    except InterruptedError:
        logging.info("下载和存储过程被用户中断")
        raise
    except Exception as e:
        logging.error(f"下载存储数据时出错: {str(e)}", exc_info=True)
        raise

def calculate_intraday_features(file_path, sample_file_name, daily_file_name_pattern, feature_types, output_path, output_file_name, trading_minutes=240):
    """
    计算股票的日内特征,并将结果保存到csv文件中。

    参数:
    - file_path: str
        股票数据文件所在的目录路径。
    - sample_file_name: str
        样本文件名,用于提取周类型、起始日期和束日期。
        样文件名应该遵循以下格式: "股票代码_周期类型_起始日_结束日期_时间范围.csv"
        例如: "000001.SZ_1m_20240101_20240430_09_30-11_30.csv"
    - daily_file_name_pattern: str
        日数据文件名的模式,用构造与分钟数据对应的日数据文件名。
        模式中应该包含股票代码的占位符,例如: "000001.SZ_1d_20240101_20240430_all.csv"
    - feature_types: list
        要计算的特征类型列表,可选值包括: 'volume_ratio', 'return_rate'。
    - output_path: str
        输出文件的目录路径。
    - output_file_name: str
        输出文件名。
    - trading_minutes: int, 可选, 默认为240
        每个交易日的交易分钟数,用于计算成交量比例。默认为240分钟(4小时)

    函数功能:
    1. 根据样本文件名提取周期类型、起始日期和结束日期。
    2. 获取与样本文件名格式相同的所有文件。
    3. 对每个文件:
       - 从文件路径中提取股票代码。
       - 读取逐分钟数据文件。
       - 构造正确的日数据文件名,并读取日数据文件。
       - 计算过去5天的平均交易量。
       - 获取前一天的收盘价。
       - 将分钟数据和日数据按日期合并。
       - 根据指定的特征类型计算相应的特征值。
       - 删除不要的列,并添加股票代码列。
       - 去掉前5天(包括第5天)和最后一天的数据。
    4. 如果输出路径不存在,则创建文件夹。
    5. 将计算结果保存到csv文件中,如果文件已经存在,则追加数据。

    返回值:
    无返回值,计算结果直接保存到指定的输出文件中。
    """

    # 从样本文件名中提取周期类型、起始日期和结束日期
    file_name_parts = sample_file_name.split('_')
    data_type = file_name_parts[1]
    start_date = file_name_parts[2]
    end_date = file_name_parts[3]

    # 获取与样本文件名格式相同的所有文件
    file_pattern = f"*_{data_type}_{start_date}_{end_date}_*.csv"
    file_list = glob.glob(os.path.join(file_path, file_pattern))

    # 理每文件
    for idx, minute_file_path in enumerate(file_list):
        # 从文件路径中提取股票代码
        stock_code = os.path.basename(minute_file_path).split('_')[0]

        # 读取逐分钟数据文件
        minute_data = pd.read_csv(minute_file_path)

        # 构造正确的日数据文件名
        stock_code_example = daily_file_name_pattern.split('_')[0]
        daily_file_name = daily_file_name_pattern.replace(stock_code_example, stock_code)
        daily_file_path = os.path.join(file_path, daily_file_name)
        daily_data = pd.read_csv(daily_file_path)

        # 计算过去5天的平均交易量
        daily_data['past_avg_volume'] = daily_data['volume'].rolling(window=5).mean().shift(1)

        # 获取前一天的收盘价
        daily_data['prev_close'] = daily_data['close'].shift(1)

        minute_data['date'] = pd.to_datetime(minute_data['date'])
        daily_data['date'] = pd.to_datetime(daily_data['date'])

        # 检查分钟数据否有 'close' 列,如果没有,则使用 'price' 列
        if 'close' not in minute_data.columns:
            minute_data['price'] = minute_data['price']
        else:
            minute_data['price'] = minute_data['close']

        # 按日期合并分钟据和日数据
        merged_data = pd.merge(minute_data, daily_data[['date', 'past_avg_volume', 'prev_close']], on='date', how='left')

        eps = 1e-8  # 添加一个小的常数

        # 计算特征
        for feature_type in feature_types:
            if feature_type == 'volume_ratio':
                merged_data['volume_ratio'] = merged_data.apply(lambda x: x['volume'] / (x['past_avg_volume'] / trading_minutes + eps) if pd.notna(x['past_avg_volume']) else np.nan, axis=1)
            elif feature_type == 'return_rate':
                merged_data['return_rate'] = merged_data.apply(lambda x: (x['price'] - x['prev_close']) / x['prev_close'] if pd.notna(x['prev_close']) else np.nan, axis=1)

        # 删除不要的列
        merged_data = merged_data[['date', 'time'] + feature_types]
        merged_data['stock_code'] = stock_code  # 添加股票代码列

        # 去掉前6天(包括第6天)和最后一天的数据
        min_date = merged_data['date'].min()
        max_date = merged_data['date'].max()
        merged_data = merged_data[(merged_data['date'] > min_date + pd.Timedelta(days=6)) & (merged_data['date'] < max_date)]

        # 如果输出路径不存在,则创建文件夹
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 保存结果到csv文件,如果文件已经存在,则追加数据
        output_file_path = os.path.join(output_path, output_file_name)
        header = idx == 0  # 如果是第一个文件,则写入表头,否则不写入
        mode = 'w' if idx == 0 else 'a'  # 如果是第一个文件,则写入模式为'w',否则为'a'(追加)
        merged_data.to_csv(output_file_path, index=False, header=header, mode=mode)

def calculate_next_day_return(file_path, sample_file_name, feature_types, output_path, output_file_name):
    """
    计算股票的下一个交易日收益率,并将结果保存到csv文件中。

    参数:
    - file_path: str
        股票数据文件所在的目录路径。
    - sample_file_name: str
        样本文件名,用于提取起始日期和结束日期。
        样本文件名应该遵循以下格式: "股票代码_1d_起始日期_结束日期_all.csv"
        例如: "000001.SZ_1d_20240101_20240430_all.csv"
    - feature_types: list
        要计算的特征类型列表,目前支持: 'next_day_return_rate' (下一个交易日收益率)。
    - output_path: str
        输出文件的目录路径。
    - output_file_name: str
        输出文件名。

    函数功能:
    1. 根据样本文件名提取起始日期和结束日期
    2. 获取与样本文件名格式相同的所有文件。
    3. 对每个文件:
       - 从文件路径中提取股票代码。
       - 取日数据文件。
       - 将期列转换为日期时间类型。
       - 如果 'next_day_return_rate' 在特征类型列表中,计算下一个交易日的收盘价收益率,并将其记录到当前交易日。
       - 提取日级别的数据,每个日期只保留一条记录,包括日期和指定的特征。
       - 添加股票代码列。
       - 去掉前6天(包括第6天)和最后一天的数据。
    4. 如果输出路径不存在,则创建文件夹。
    5. 将计算结果保存到csv文件中,如果文件已经存在,则追加数据。

    返回值:
    无返回值,计算结果直接保存到指定的输出文件中。
    """
    # 从样本文件名中提取起始日期和结束日期
    file_name_parts = sample_file_name.split('_')
    start_date = file_name_parts[2]
    end_date = file_name_parts[3]

    # 获取与样本文件名格式相同的所有文件
    file_pattern = f"*_1d_{start_date}_{end_date}_all.csv"
    file_list = glob.glob(os.path.join(file_path, file_pattern))

    # 处理每个文件
    for idx, daily_file_path in enumerate(file_list):
        # 从文路径中提取股票代码
        stock_code = os.path.basename(daily_file_path).split('_')[0]

        # 读取日数据文件
        daily_data = pd.read_csv(daily_file_path)

        # 将日期列转换为日期时间类型
        daily_data['date'] = pd.to_datetime(daily_data['date'])

        # 计算第二天的收盘收益率,并将其记录到当天
        if 'next_day_return_rate' in feature_types:
            daily_data['next_day_return_rate'] = daily_data['close'].pct_change().shift(-1)

        # 提取日级别的数据,每个日期只保留一条记录
        daily_data = daily_data[['date'] + [feature for feature in feature_types if feature in daily_data.columns]].dropna().drop_duplicates(subset='date')
        daily_data['stock_code'] = stock_code  # 添加股票代码列

        # 去掉前6天(包括第6天)和最后一天的数据
        min_date = daily_data['date'].min()
        max_date = daily_data['date'].max()
        second_last_date = max_date  
        daily_data = daily_data[(daily_data['date'] > min_date + pd.Timedelta(days=6)) & (daily_data['date'] <= second_last_date)]

        # 如果输出路径不存在,则创建文件夹
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 保存结果到csv文件,如果文件已经存在,则追加数据
        output_file_path = os.path.join(output_path, output_file_name)
        header = idx == 0  # 如果是第一个文件,则写入表头,否则不写入
        mode = 'w' if idx == 0 else 'a'  # 如果是第一个文件,则写入模式为'w',否则为'a'(追加)
        daily_data.to_csv(output_file_path, index=False, header=header, mode=mode)

def get_available_sectors():
    """获取所有可用的板块代码"""
    try:
        # 获取 miniQMT 客户端连接
        # c = get_client()
        # # 确保客户端已连接
        # if not c.connect():
        #     raise Exception("无法连接到 miniQMT 客户端")
        
        # 获取所有板块
        sectors = xtdata.get_sector_list()
        
        logging.info("可用的板块列表：")
        for sector in sectors:
            # 尝试获取该板块的成分股
            components = xtdata.get_stock_list_in_sector(sector)
            count = len(components) if components else 0
            logging.info(f"板块: {sector}, 成分股数量: {count}")
        
        return sectors
    except Exception as e:
        logging.error(f"获取板块列表时出错: {str(e)}")
        return []

def get_stock_list():
    """获取所有股票代码和名称，包括上证A股、创业板、沪深A股、深证A股、科创板、指数及其集合，以及重要指数的成分股"""
    try:
        # 获取 miniQMT 客户端连接
        # c = get_client()
        # # 确保客户端已连接
        # if not c.connect():
        #     raise Exception("无法连接到 miniQMT 客户端")
        
        xtdata.download_sector_data()

        logging.info("开始获取股票列表...")
        
        # 初始化返回的字典
        stock_dict = {
            'sh_a': [],      # 上证A股
            'sz_a': [],      # 深证A股
            'gem': [],       # 创业板
            'sci': [],       # 科创板
            'hs_a': [],      # 沪深A股
            'indices': [],   # 指数
            'all_stocks': [], # 所有股票的集合
            'hs300_components': [],  # 沪深300成分股
            'zz500_components': [],  # 中证500成分股
            'sz50_components': [],   # 上证50成分股
            'hs_convertible_bonds': [],  # 沪深转债
        }
        
        # 重要指数列表
        important_indices = [
            {'code': '000001.SH', 'name': '上证指数'},
            {'code': '399001.SZ', 'name': '深证成指'},
            {'code': '399006.SZ', 'name': '创业板指'},
            {'code': '000688.SH', 'name': '科创50'},
            {'code': '000300.SH', 'name': '沪深300'},
            {'code': '000905.SH', 'name': '中证500'},
            {'code': '000852.SH', 'name': '中证1000'}
        ]

        # 板块映射
        sector_mapping = {
            '上证A股': 'sh_a',
            '深证A股': 'sz_a',
            '创业板': 'gem',
            '科创板': 'sci',
            '沪深A股': 'hs_a'
        }
        
        # 指数成分股映射
        index_components_mapping = {
            '沪深300': 'hs300_components',
            '中证500': 'zz500_components',
            '上证50': 'sz50_components'
        }

        # 获取各个板块的股票
        for sector_name, dict_key in sector_mapping.items():
            try:
                logging.info(f"获取{sector_name}股票列表...")
                print(f"[更新进度] 正在获取{sector_name}股票列表...")
                stocks = xtdata.get_stock_list_in_sector(sector_name)
                if stocks:
                    logging.info(f"获取到 {len(stocks)} 只{sector_name}股票")
                    for code in stocks:
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name:
                                    stock_info = {
                                        'code': code,
                                        'name': name
                                    }
                                    stock_dict[dict_key].append(stock_info)
                                    # 将所有股票（除了沪深A股）添加到all_stocks中
                                    if dict_key != 'hs_a':  # 不添加沪深A股，因为它包含了其他所有股票
                                        stock_dict['all_stocks'].append(stock_info)
                        except Exception as e:
                            logging.error(f"处理股票 {code} 时出错: {str(e)}")
                            continue
                    logging.info(f"成功添加 {len(stock_dict[dict_key])} 只{sector_name}股票")
                else:
                    logging.warning(f"未获取到{sector_name}股票")
            except Exception as e:
                logging.error(f"获取{sector_name}股票列表时出错: {str(e)}")

        # 获取指数成分股
        for index_name, dict_key in index_components_mapping.items():
            try:
                logging.info(f"获取{index_name}成分股...")
                components = xtdata.get_stock_list_in_sector(index_name)
                if components:
                    logging.info(f"获取到 {len(components)} 只{index_name}成分股")
                    for code in components:
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name:
                                    stock_info = {
                                        'code': code,
                                        'name': name
                                    }
                                    stock_dict[dict_key].append(stock_info)
                                    # 将成分股也添加到all_stocks中
                                    stock_dict['all_stocks'].append(stock_info)
                        except Exception as e:
                            logging.error(f"处理{index_name}成分股 {code} 时出错: {str(e)}")
                            continue
                    logging.info(f"成功添加 {len(stock_dict[dict_key])} 只{index_name}成分股")
                else:
                    logging.warning(f"未获取到{index_name}成分股")
            except Exception as e:
                logging.error(f"获取{index_name}成分股列表时出错: {str(e)}")

        # 获取沪深转债成分股
        convertible_bonds_mapping = {
            '沪深转债': 'hs_convertible_bonds'
        }
        
        for cb_name, dict_key in convertible_bonds_mapping.items():
            try:
                logging.info(f"获取{cb_name}成分股...")
                cb_stocks = xtdata.get_stock_list_in_sector(cb_name)
                if cb_stocks:
                    logging.info(f"获取到 {len(cb_stocks)} 只{cb_name}")
                    for code in cb_stocks:
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name and '转债' in name:
                                    bond_info = {
                                        'code': code,
                                        'name': name
                                    }
                                    stock_dict[dict_key].append(bond_info)
                                    # 不将转债添加到all_stocks中，因为它们是债券而非股票
                        except Exception as e:
                            logging.error(f"处理{cb_name} {code} 时出错: {str(e)}")
                            continue
                    logging.info(f"成功添加 {len(stock_dict[dict_key])} 只{cb_name}")
                else:
                    logging.warning(f"未获取到{cb_name}")
            except Exception as e:
                logging.error(f"获取{cb_name}列表时出错: {str(e)}")

        # 添加指数并同时添加到all_stocks
        stock_dict['indices'] = important_indices
        for index in important_indices:
            stock_dict['all_stocks'].append(index)
        
        # 对每个板块按照代码排序并去重
        for board in stock_dict:
            if board == 'all_stocks':
                # 对集合进行去重
                unique_stocks = {stock['code']: stock for stock in stock_dict[board]}.values()
                stock_dict[board] = sorted(unique_stocks, key=lambda x: x['code'])
            else:
                stock_dict[board].sort(key=lambda x: x['code'])
            logging.info(f"{board} 数量: {len(stock_dict[board])}")
        
        return stock_dict
        
    except Exception as e:
        logging.error(f"获取股票列表时出错: {str(e)}", exc_info=True)
        raise

def save_stock_list_to_csv(stock_dict, output_dir):
    """将股票列表保存为CSV文件"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"创建输出目录: {output_dir}")
        
        # 定义板块中文名称
        board_names = {
            'sh_a': '上证A股',
            'sz_a': '深证A股',
            'gem': '创业板',
            'sci': '科创板',
            'hs_a': '沪深A股',
            'indices': '指数',
            'all_stocks': '全部股票',
            'hs300_components': '沪深300成分股',
            'zz500_components': '中证500成分股',
            'sz50_components': '上证50成分股',
            'hs_convertible_bonds': '沪深转债'
        }
        
        # 为每个板块创建CSV文件
        for board, stocks in stock_dict.items():
            # 保存单个板块文件，沪深转债使用特定文件名
            if board == 'hs_convertible_bonds':
                file_path = os.path.join(output_dir, "沪深转债_列表.csv")
            else:
                file_path = os.path.join(output_dir, f"{board_names[board]}_股票列表.csv")
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                for stock in stocks:
                    f.write(f"{stock['code']},{stock['name']}\n")
                    
        logging.info(f"股票列表已保存到目录: {output_dir}")
        logging.info(f"总共生成了 {len(board_names)} 个列表文件")
        
    except Exception as e:
        logging.error(f"保存股票列表时出错: {str(e)}", exc_info=True)
        raise

def stock_list_worker(output_dir, queue):
    """多进程工作函数：在子进程中执行股票列表更新"""
    try:
        # Windows multiprocessing 保护
        import multiprocessing
        if hasattr(multiprocessing, 'set_start_method'):
            try:
                multiprocessing.set_start_method('spawn', force=True)
            except RuntimeError:
                pass  # 可能已经设置过了
        
        # 在子进程中导入模块，避免Qt冲突
        from xtquant import xtdata
        import ast
        import logging
        
        # 发送进度消息
        queue.put(("progress", "正在初始化客户端连接..."))
        
        # 发送进度消息
        queue.put(("progress", "正在下载板块数据..."))
        xtdata.download_sector_data()
        queue.put(("progress", "板块数据下载完成"))
        
        # 发送进度消息
        queue.put(("progress", "正在获取股票列表..."))
        stock_dict = get_stock_list_for_subprocess(queue)
        queue.put(("progress", "股票列表获取完成"))
        
        # 发送进度消息
        queue.put(("progress", "正在保存股票列表..."))
        save_stock_list_to_csv_for_subprocess(stock_dict, output_dir, queue)
        queue.put(("progress", "股票列表保存完成"))
        
        # 发送完成消息
        queue.put(("finished", True, "股票列表更新成功！"))
        
    except Exception as e:
        error_msg = f"更新股票列表时出错: {str(e)}"
        logging.error(error_msg, exc_info=True)
        queue.put(("finished", False, error_msg))

def get_stock_list_for_subprocess(queue):
    """子进程版本的获取股票列表函数，带进度反馈"""
    from xtquant import xtdata
    import ast
    
    # 初始化返回的字典
    stock_dict = {
        'sh_a': [],      # 上证A股
        'sz_a': [],      # 深证A股
        'gem': [],       # 创业板
        'sci': [],       # 科创板
        'hs_a': [],      # 沪深A股
        'indices': [],   # 指数
        'all_stocks': [], # 所有股票的集合
        'hs300_components': [],  # 沪深300成分股
        'zz500_components': [],  # 中证500成分股
        'sz50_components': [],   # 上证50成分股
        'hs_convertible_bonds': [],  # 沪深转债
    }
    
    # 重要指数列表
    important_indices = [
        {'code': '000001.SH', 'name': '上证指数'},
        {'code': '399001.SZ', 'name': '深证成指'},
        {'code': '399006.SZ', 'name': '创业板指'},
        {'code': '000688.SH', 'name': '科创50'},
        {'code': '000300.SH', 'name': '沪深300'},
        {'code': '000905.SH', 'name': '中证500'},
        {'code': '000852.SH', 'name': '中证1000'}
    ]

    # 板块映射
    sector_mapping = {
        '上证A股': 'sh_a',
        '深证A股': 'sz_a',
        '创业板': 'gem',
        '科创板': 'sci',
        '沪深A股': 'hs_a'
    }
    
    # 指数成分股映射
    index_components_mapping = {
        '沪深300': 'hs300_components',
        '中证500': 'zz500_components',
        '上证50': 'sz50_components'
    }

    # 获取各个板块的股票
    for sector_name, dict_key in sector_mapping.items():
        queue.put(("progress", f"正在获取{sector_name}股票列表..."))
        print(f"[更新进度] 正在获取{sector_name}股票列表...", flush=True)
        try:
            stocks = xtdata.get_stock_list_in_sector(sector_name)
            if stocks:
                print(f"[更新进度] 获取到 {len(stocks)} 只{sector_name}股票，正在处理详细信息...", flush=True)
                processed_count = 0
                for code in stocks:
                    try:
                        detail = xtdata.get_instrument_detail(code)
                        if detail:
                            if isinstance(detail, str):
                                detail = ast.literal_eval(detail)
                            name = detail.get('InstrumentName', '')
                            if name:
                                stock_info = {'code': code, 'name': name}
                                stock_dict[dict_key].append(stock_info)
                                if dict_key != 'hs_a':
                                    stock_dict['all_stocks'].append(stock_info)
                                processed_count += 1
                                # 每处理100只股票输出一次进度
                                if processed_count % 100 == 0:
                                    print(f"[更新进度] {sector_name} 已处理 {processed_count}/{len(stocks)} 只股票", flush=True)
                                    queue.put(("progress", f"{sector_name} 已处理 {processed_count}/{len(stocks)} 只股票"))
                    except Exception as e:
                        continue
                
                print(f"[更新进度] {sector_name} 完成，共获取 {len(stock_dict[dict_key])} 只有效股票", flush=True)
            else:
                print(f"[更新进度] {sector_name} 板块没有股票", flush=True)

        except Exception as e:
            print(f"[更新进度] 获取{sector_name}股票列表失败: {str(e)}", flush=True)

    # 获取指数成分股
    for index_name, dict_key in index_components_mapping.items():
        queue.put(("progress", f"正在获取{index_name}成分股..."))
        print(f"[更新进度] 正在获取{index_name}成分股...", flush=True)
        try:
            components = xtdata.get_stock_list_in_sector(index_name)
            if components:
                print(f"[更新进度] 获取到 {len(components)} 只{index_name}成分股，正在处理详细信息...", flush=True)
                for code in components:
                    try:
                        detail = xtdata.get_instrument_detail(code)
                        if detail:
                            if isinstance(detail, str):
                                detail = ast.literal_eval(detail)
                            name = detail.get('InstrumentName', '')
                            if name:
                                stock_info = {'code': code, 'name': name}
                                stock_dict[dict_key].append(stock_info)
                                stock_dict['all_stocks'].append(stock_info)
                    except Exception as e:
                        continue
                print(f"[更新进度] {index_name} 完成，共获取 {len(stock_dict[dict_key])} 只有效成分股", flush=True)
            else:
                print(f"[更新进度] {index_name} 没有成分股", flush=True)
        except Exception as e:
            print(f"[更新进度] 获取{index_name}成分股列表失败: {str(e)}", flush=True)

    # 获取沪深转债成分股
    queue.put(("progress", "正在获取沪深转债..."))
    print(f"[更新进度] 正在获取沪深转债...", flush=True)
    try:
        cb_stocks = xtdata.get_stock_list_in_sector('沪深转债')
        if cb_stocks:
            print(f"[更新进度] 获取到 {len(cb_stocks)} 只沪深转债，正在筛选转债...", flush=True)
            for code in cb_stocks:
                try:
                    detail = xtdata.get_instrument_detail(code)
                    if detail:
                        if isinstance(detail, str):
                            detail = ast.literal_eval(detail)
                        name = detail.get('InstrumentName', '')
                        if name and '转债' in name:
                            bond_info = {'code': code, 'name': name}
                            stock_dict['hs_convertible_bonds'].append(bond_info)
                except Exception as e:
                    continue
            print(f"[更新进度] 沪深转债 完成，共获取 {len(stock_dict['hs_convertible_bonds'])} 只有效转债", flush=True)
        else:
            print(f"[更新进度] 沪深转债 没有证券", flush=True)
    except Exception as e:
        print(f"[更新进度] 获取沪深转债失败: {str(e)}", flush=True)

    # 添加指数
    stock_dict['indices'] = important_indices
    for index in important_indices:
        stock_dict['all_stocks'].append(index)

    # 对每个板块去重并排序
    for board in stock_dict:
        if board == 'all_stocks':
            unique_stocks = {stock['code']: stock for stock in stock_dict[board]}.values()
            stock_dict[board] = sorted(unique_stocks, key=lambda x: x['code'])
        else:
            stock_dict[board].sort(key=lambda x: x['code'])

    return stock_dict

def save_stock_list_to_csv_for_subprocess(stock_dict, output_dir, queue):
    """子进程版本的保存CSV函数，带进度反馈"""
    import os
    
    os.makedirs(output_dir, exist_ok=True)

    board_names = {
        'sh_a': '上证A股',
        'sz_a': '深证A股',
        'gem': '创业板',
        'sci': '科创板',
        'hs_a': '沪深A股',
        'indices': '指数',
        'all_stocks': '全部股票',
        'hs300_components': '沪深300成分股',
        'zz500_components': '中证500成分股',
        'sz50_components': '上证50成分股',
        'hs_convertible_bonds': '沪深转债'
    }

    for board, stocks in stock_dict.items():
        queue.put(("progress", f"正在保存{board_names[board]}列表..."))
        print(f"[更新进度] 正在保存{board_names[board]}列表...", flush=True)
        # 沪深转债使用特定文件名
        if board == 'hs_convertible_bonds':
            file_path = os.path.join(output_dir, "沪深转债_列表.csv")
        else:
            file_path = os.path.join(output_dir, f"{board_names[board]}_股票列表.csv")
        with open(file_path, 'w', encoding='utf-8-sig') as f:
            for stock in stocks:
                f.write(f"{stock['code']},{stock['name']}\n")
        print(f"[更新进度] {board_names[board]}列表保存完成，共 {len(stocks)} 只证券", flush=True)

# 定义多进程版本的更新管理器类
if not is_subprocess():
    from PyQt5.QtCore import QObject, pyqtSignal, QTimer
    import multiprocessing
    import queue
    
    class StockListUpdateManager(QObject):
        """多进程股票列表更新管理器"""
        progress = pyqtSignal(str)  # 用于发送进度信息
        finished = pyqtSignal(bool, str)  # 用于发送完成状态和消息

        def __init__(self, output_dir):
            super().__init__()
            self.output_dir = output_dir
            self.process = None
            self.queue = None
            self.timer = None
            self.running = True

        def start(self):
            """启动多进程更新"""
            try:
                # Windows multiprocessing 配置
                if hasattr(multiprocessing, 'set_start_method'):
                    try:
                        multiprocessing.set_start_method('spawn', force=True)
                    except RuntimeError:
                        pass  # 可能已经设置过了
                
                # 创建进程间通信队列
                self.queue = multiprocessing.Queue()
                
                # 创建子进程
                self.process = multiprocessing.Process(
                    target=stock_list_worker,
                    args=(self.output_dir, self.queue)
                )
                
                # 启动子进程
                self.process.start()
                
                # 创建定时器检查队列消息
                self.timer = QTimer()
                self.timer.timeout.connect(self.check_queue)
                self.timer.start(100)  # 每100ms检查一次
                
            except Exception as e:
                error_msg = f"启动多进程更新时出错: {str(e)}"
                logging.error(error_msg, exc_info=True)
                self.finished.emit(False, error_msg)

        def check_queue(self):
            """检查进程队列中的消息"""
            try:
                while True:
                    try:
                        # 非阻塞获取消息
                        message = self.queue.get_nowait()
                        
                        if message[0] == "progress":
                            # 进度消息
                            self.progress.emit(message[1])
                        elif message[0] == "finished":
                            # 完成消息
                            success, msg = message[1], message[2]
                            self.stop()
                            self.finished.emit(success, msg)
                            break
                            
                    except queue.Empty:
                        break
                        
                # 检查进程是否还在运行
                if self.process and not self.process.is_alive():
                    # 进程已结束，但没有收到完成消息，可能是异常结束
                    exit_code = self.process.exitcode
                    if exit_code != 0:
                        self.stop()
                        self.finished.emit(False, f"更新进程异常结束，退出码: {exit_code}")
                        
            except Exception as e:
                logging.error(f"检查队列消息时出错: {str(e)}")

        def stop(self):
            """停止更新进程"""
            self.running = False
            
            if self.timer:
                self.timer.stop()
                self.timer = None
                
            if self.process and self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)  # 等待5秒
                if self.process.is_alive():
                    self.process.kill()  # 强制结束
                    
            self.process = None
            self.queue = None

def get_and_save_stock_list(output_dir):
    """获取并保存股票列表的便捷函数，返回多进程更新管理器实例"""
    # 检查是否在主进程中
    if not is_subprocess():
        # 在主进程中使用多进程管理器
        update_manager = StockListUpdateManager(output_dir)
        return update_manager
    else:
        # 在子进程中直接执行，不使用Qt相关功能
        try:
            from xtquant import xtdata
            stock_dict = get_stock_list()
            save_stock_list_to_csv(stock_dict, output_dir)
            return True, "股票列表更新成功！"
        except Exception as e:
            error_msg = f"更新股票列表时出错: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return False, error_msg
# 只在主进程中定义Qt线程类
if not is_subprocess():
    class StockListUpdateThread(QThread):
        """股票列表更新线程"""
        progress = pyqtSignal(str)  # 用于发送进度信息
        finished = pyqtSignal(bool, str)  # 用于发送完成状态和消息

        def __init__(self, output_dir):
            super().__init__()
            self.output_dir = output_dir
            self.running = True
else:
    # 在子进程中创建空的占位符类
    class StockListUpdateThread:
        def __init__(self, output_dir):
            self.output_dir = output_dir
            self.running = True
        
        def start(self):
            pass
        
        def run(self):
            pass

    def run(self):
        try:
            if not self.running:
                return

            progress_msg = "正在初始化客户端连接..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            # c = get_client()
            # if not c.connect():
            #     raise Exception("无法连接到 miniQMT 客户端")

            progress_msg = "正在下载板块数据..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            xtdata.download_sector_data()
            print("[更新进度] 板块数据下载完成", flush=True)

            progress_msg = "正在获取股票列表..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            stock_dict = self.get_stock_list()
            print("[更新进度] 股票列表获取完成", flush=True)

            progress_msg = "正在保存股票列表..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            self.save_stock_list_to_csv(stock_dict)
            print("[更新进度] 股票列表保存完成", flush=True)

            if self.running:
                self.finished.emit(True, "股票列表更新成功！")

        except Exception as e:
            error_msg = f"更新股票列表时出错: {str(e)}"
            logging.error(error_msg, exc_info=True)
            if self.running:
                self.finished.emit(False, error_msg)

    def stop(self):
        self.running = False

    def get_stock_list(self):
        """获取所有股票列表"""
        stock_dict = {
            'sh_a': [],      # 上证A股
            'sz_a': [],      # 深证A股
            'gem': [],       # 创业板
            'sci': [],       # 科创板
            'hs_a': [],      # 沪深A股
            'indices': [],   # 指数
            'all_stocks': [], # 所有股票的集合
            'hs300_components': [],  # 沪深300成分股
            'zz500_components': [],  # 中证500成分股
            'sz50_components': [],   # 上证50成分股
            'hs_convertible_bonds': [],  # 沪深转债
        }

        # 重要指数列表
        important_indices = [
            {'code': '000001.SH', 'name': '上证指数'},
            {'code': '399001.SZ', 'name': '深证成指'},
            {'code': '399006.SZ', 'name': '创业板指'},
            {'code': '000688.SH', 'name': '科创50'},
            {'code': '000300.SH', 'name': '沪深300'},
            {'code': '000905.SH', 'name': '中证500'},
            {'code': '000852.SH', 'name': '中证1000'}
        ]

        # 板块映射
        sector_mapping = {
            '上证A股': 'sh_a',
            '深证A股': 'sz_a',
            '创业板': 'gem',
            '科创板': 'sci',
            '沪深A股': 'hs_a'
        }

        # 指数成分股映射
        index_components_mapping = {
            '沪深300': 'hs300_components',
            '中证500': 'zz500_components',
            '上证50': 'sz50_components'
        }

        # 获取各个板块的股票
        for sector_name, dict_key in sector_mapping.items():
            if not self.running:
                return stock_dict

            progress_msg = f"正在获取{sector_name}股票列表..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            try:
                stocks = xtdata.get_stock_list_in_sector(sector_name)
                if stocks:
                    print(f"[更新进度] 获取到 {len(stocks)} 只{sector_name}股票，正在处理详细信息...", flush=True)
                    processed_count = 0
                    for code in stocks:
                        if not self.running:
                            return stock_dict
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name:
                                    stock_info = {'code': code, 'name': name}
                                    stock_dict[dict_key].append(stock_info)
                                    if dict_key != 'hs_a':
                                        stock_dict['all_stocks'].append(stock_info)
                                    processed_count += 1
                                    # 每处理100只股票输出一次进度
                                    if processed_count % 100 == 0:
                                        print(f"[更新进度] {sector_name} 已处理 {processed_count}/{len(stocks)} 只股票", flush=True)
                        except Exception as e:
                            logging.error(f"处理股票 {code} 时出错: {str(e)}")
                            continue
                    
                    print(f"[更新进度] {sector_name} 完成，共获取 {len(stock_dict[dict_key])} 只有效股票", flush=True)
                else:
                    print(f"[更新进度] {sector_name} 板块没有股票", flush=True)

            except Exception as e:
                logging.error(f"获取{sector_name}股票列表时出错: {str(e)}")
                print(f"[更新进度] 获取{sector_name}股票列表失败: {str(e)}", flush=True)

        # 获取指数成分股
        for index_name, dict_key in index_components_mapping.items():
            if not self.running:
                return stock_dict

            progress_msg = f"正在获取{index_name}成分股..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            try:
                components = xtdata.get_stock_list_in_sector(index_name)
                if components:
                    print(f"[更新进度] 获取到 {len(components)} 只{index_name}成分股，正在处理详细信息...", flush=True)
                    for code in components:
                        if not self.running:
                            return stock_dict
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name:
                                    stock_info = {'code': code, 'name': name}
                                    stock_dict[dict_key].append(stock_info)
                                    stock_dict['all_stocks'].append(stock_info)
                        except Exception as e:
                            logging.error(f"处理{index_name}成分股 {code} 时出错: {str(e)}")
                            continue
                    print(f"[更新进度] {index_name} 完成，共获取 {len(stock_dict[dict_key])} 只有效成分股", flush=True)
                else:
                    print(f"[更新进度] {index_name} 没有成分股", flush=True)
            except Exception as e:
                logging.error(f"获取{index_name}成分股列表时出错: {str(e)}")
                print(f"[更新进度] 获取{index_name}成分股列表失败: {str(e)}", flush=True)

        # 获取沪深转债成分股
        convertible_bonds_mapping = {
            '沪深转债': 'hs_convertible_bonds'
        }
        
        for cb_name, dict_key in convertible_bonds_mapping.items():
            if not self.running:
                return stock_dict
                
            progress_msg = f"正在获取{cb_name}..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            try:
                cb_stocks = xtdata.get_stock_list_in_sector(cb_name)
                if cb_stocks:
                    print(f"[更新进度] 获取到 {len(cb_stocks)} 只{cb_name}，正在筛选转债...", flush=True)
                    for code in cb_stocks:
                        if not self.running:
                            return stock_dict
                        try:
                            detail = xtdata.get_instrument_detail(code)
                            if detail:
                                if isinstance(detail, str):
                                    detail = ast.literal_eval(detail)
                                name = detail.get('InstrumentName', '')
                                if name and '转债' in name:
                                    bond_info = {'code': code, 'name': name}
                                    stock_dict[dict_key].append(bond_info)
                                    # 不将转债添加到all_stocks中，因为它们是债券而非股票
                        except Exception as e:
                            continue
                    print(f"[更新进度] {cb_name} 完成，共获取 {len(stock_dict[dict_key])} 只有效转债", flush=True)
                else:
                    print(f"[更新进度] {cb_name} 没有证券", flush=True)
            except Exception as e:
                print(f"[更新进度] 获取{cb_name}失败: {str(e)}", flush=True)

        # 添加指数
        stock_dict['indices'] = important_indices
        for index in important_indices:
            stock_dict['all_stocks'].append(index)

        # 对每个板块去重并排序
        for board in stock_dict:
            if board == 'all_stocks':
                unique_stocks = {stock['code']: stock for stock in stock_dict[board]}.values()
                stock_dict[board] = sorted(unique_stocks, key=lambda x: x['code'])
            else:
                stock_dict[board].sort(key=lambda x: x['code'])

        return stock_dict

    def save_stock_list_to_csv(self, stock_dict):
        """将股票列表保存为CSV文件"""
        os.makedirs(self.output_dir, exist_ok=True)

        board_names = {
            'sh_a': '上证A股',
            'sz_a': '深证A股',
            'gem': '创业板',
            'sci': '科创板',
            'hs_a': '沪深A股',
            'indices': '指数',
            'all_stocks': '全部股票',
            'hs300_components': '沪深300成分股',
            'zz500_components': '中证500成分股',
            'sz50_components': '上证50成分股',
            'hs_convertible_bonds': '沪深转债'
        }

        for board, stocks in stock_dict.items():
            if not self.running:
                return
            progress_msg = f"正在保存{board_names[board]}列表..."
            self.progress.emit(progress_msg)
            print(f"[更新进度] {progress_msg}", flush=True)
            # 沪深转债使用特定文件名
            if board == 'hs_convertible_bonds':
                file_path = os.path.join(self.output_dir, "沪深转债_列表.csv")
            else:
                file_path = os.path.join(self.output_dir, f"{board_names[board]}_股票列表.csv")
            with open(file_path, 'w', encoding='utf-8-sig') as f:
                for stock in stocks:
                    f.write(f"{stock['code']},{stock['name']}\n")
            print(f"[更新进度] {board_names[board]}列表保存完成，共 {len(stocks)} 只证券", flush=True)

def supplement_history_data(stock_files, field_list, period_type, start_date, end_date, dividend_type='none', time_range='all', progress_callback=None, log_callback=None, check_interrupt=None):
    """
    补充历史行情数据。

    参数:
    - stock_files (list): 股票代码列表文件路径列表
    - field_list (list): 要存储的字段列表
    - period_type (str): 要读取的周期类型 ('tick', '1m', '5m', '1d')
    - start_date (str): 起始日期,格式为 "YYYYMMDD"
    - end_date (str): 结束日期,格式为 "YYYYMMDD"
    - dividend_type (str): 复权方式，可选值：
        - 'none': 不复权
        - 'front': 前复权
        - 'back': 后复权
        - 'front_ratio': 等比前复权
        - 'back_ratio': 等比后复权
    - time_range (str): 要读取的时间段,格式为 "HH:MM-HH:MM"，默认为 "all"
    - progress_callback (function): 用于更新进度的回调函数
    - log_callback (function): 用于记录日志的回调函数
    - check_interrupt (function, optional): 中断检查函数
        - 该函数用于检查是否需要中断数据补充过程
        - 返回True表示需要中断，返回False表示继续执行
    """
    # 在函数开始时设置环境变量，防止意外启动Qt应用（仅在子进程中）
    if is_subprocess():
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        # 获取所有股票代码
        stocks = []
        for stock_file in stock_files:
            # 检查是否需要中断
            if check_interrupt and check_interrupt():
                logging.info("补充数据过程被中断")
                raise InterruptedError("补充数据过程被用户中断")
                
            if os.path.exists(stock_file):
                logging.info(f"读取股票文件: {stock_file}")
                codes, names = read_stock_csv(stock_file)
                stocks.extend(codes)
        
        if not stocks:
            if log_callback:
                log_callback("没有找到需要补充数据的股票")
            return

        total_stocks = len(stocks)
        for index, stock in enumerate(stocks, 1):
            try:
                # 检查是否需要中断
                if check_interrupt and check_interrupt():
                    logging.info("补充数据过程被中断")
                    raise InterruptedError("补充数据过程被用户中断")
                    
                if log_callback:
                    log_callback(f"正在补充 {stock} 的数据 ({index}/{total_stocks})")

                # 检查是否需要中断
                if check_interrupt and check_interrupt():
                    logging.info("补充数据过程被中断")
                    raise InterruptedError("补充数据过程被用户中断")
                    
                # 调用download_history_data进行数据补充
                xtdata.download_history_data(
                    stock,
                    period=period_type,
                    start_time=start_date,
                    end_time=end_date,
                    incrementally=True
                )

                # 检查是否需要中断
                if check_interrupt and check_interrupt():
                    logging.info("补充数据过程被中断")
                    raise InterruptedError("补充数据过程被用户中断")
                    
                    
                # 获取数据（带复权参数）
                data = xtdata.get_market_data_ex(
                    field_list=field_list,
                    stock_list=[stock],
                    period=period_type,
                    start_time=start_date,
                    end_time=end_date,
                    dividend_type=dividend_type,
                    fill_data=True
                )

                # 添加更详细的数据信息
                if stock in data and data[stock] is not None:
                    df = data[stock]
                    
                    # 检查df是否为DataFrame类型
                    is_dataframe = isinstance(df, pd.DataFrame)
                    
                    # 获取数据信息
                    rows_count = len(df) if df is not None else 0
                    cols_count = len(df.columns) if is_dataframe else 0
                    
                    if rows_count > 0:
                        # 计算时间跨度
                        if is_dataframe and 'time' in df.columns:
                            try:
                                times = pd.to_datetime(df['time'].astype(float), unit='ms')
                                min_time = times.min()
                                max_time = times.max()
                                time_span = f"{min_time.strftime('%Y-%m-%d')} 至 {max_time.strftime('%Y-%m-%d')}"
                                
                                # 输出详细信息
                                if log_callback:
                                    data_info = f"补充 {stock} 数据成功: 获取 {rows_count} 行, {cols_count} 列, 时间跨度: {time_span}"
                                    log_callback(data_info)
                            except Exception as e:
                                if log_callback:
                                    log_callback(f"补充 {stock} 数据完成，但获取详细信息时出错: {str(e)}")
                        else:
                            if log_callback:
                                log_callback(f"补充 {stock} 数据成功: 获取 {rows_count} 行, {cols_count} 列")
                    else:
                        if log_callback:
                            log_callback(f"补充 {stock} 数据成功，但数据为空")
                else:
                    if log_callback:
                        log_callback(f"未能获取 {stock} 的数据")

                if progress_callback:
                    progress = int((index / total_stocks) * 100)
                    progress_callback(progress)

                # 检查是否需要中断
                if check_interrupt and check_interrupt():
                    logging.info("补充数据过程被中断")
                    raise InterruptedError("补充数据过程被用户中断")

            except InterruptedError:
                logging.info(f"补充 {stock} 数据时被中断")
                raise
            except Exception as e:
                error_msg = f"补充 {stock} 数据时出错: {str(e)}"
                logging.error(error_msg)
                if log_callback:
                    log_callback(error_msg)

    except InterruptedError:
        logging.info("补充数据过程被用户中断")
        raise
    except Exception as e:
        error_msg = f"补充数据时出错: {str(e)}"
        logging.error(error_msg, exc_info=True)
        if log_callback:
            log_callback(error_msg)
        raise

def get_stock_names(stock_codes, stock_list_file):
    """
    从股票列表文件中查询股票名称
    
    Args:
        stock_codes (list): 股票代码列表
        stock_list_file (str): 股票列表文件路径
    
    Returns:
        dict: 股票代码到股票名称的映射字典
    """
    stock_names = {}
    try:
        with open(stock_list_file, 'r', encoding='utf-8-sig') as f:  # 使用utf-8-sig处理BOM
            for line in f:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        code = parts[0].strip()
                        name = parts[1].strip()
                        if code in stock_codes:
                            stock_names[code] = name
    except Exception as e:
        logging.error(f"读取股票列表文件出错: {str(e)}")
    
    return stock_names

def khHistory(symbol_list, fields, bar_count, fre_step, current_time=None, skip_paused=False, fq='pre', force_download=False):
    """
    获取股票历史数据（不包含当前时间点）
    
    参数:
        symbol_list: 股票代码列表或单个股票代码字符串
        fields: 数据字段列表，如['open', 'high', 'low', 'close', 'volume', 'amount']
        bar_count: 获取的K线数量
        fre_step: 时间频率，如'1d', '1m', '5m'等
        current_time: 当前时间，支持多种格式：
                     - 日线数据：'YYYYMMDD' 或 'YYYY-MM-DD'
                     - 分钟/tick数据：'YYYYMMDD HHMMSS' 或 'YYYY-MM-DD HH:MM:SS'
                     - 如果为None则使用当前日期时间
        skip_paused: 是否跳过停牌数据，True跳过，False不跳过
        fq: 复权方式，'pre'前复权, 'post'后复权, 'none'不复权
        force_download: 是否强制下载最新数据，True强制下载，False使用本地缓存
    
    返回:
        dict: {股票代码: DataFrame}，DataFrame包含time列和指定的数据字段
        
    注意: 返回的数据不包含current_time这个时间点，确保回测逻辑正确
    """
    
    # 导入必要的模块
    try:
        from xtquant import xtdata
        import pandas as pd
        from datetime import datetime, timedelta
    except ImportError as e:
        print(f"导入模块失败: {str(e)}")
        return {}
    
    # 参数验证
    if not symbol_list:
        raise ValueError("symbol_list不能为空")
    if not fields:
        raise ValueError("fields不能为空")
    if bar_count <= 0:
        raise ValueError("bar_count必须大于0")
    
    # 统一处理股票代码列表
    if isinstance(symbol_list, str):
        stock_codes = [symbol_list]
    else:
        stock_codes = list(symbol_list)
    
    # 处理当前时间
    current_datetime = None
    current_date_str = None
    
    if current_time is None:
        # 如果没有指定时间，使用当前时间
        current_datetime = datetime.now()
        current_date_str = current_datetime.strftime('%Y%m%d')
    else:
        # 解析输入的时间格式
        if isinstance(current_time, str):
            current_time = current_time.strip()
            
            # 尝试解析不同的时间格式
            time_formats = [
                '%Y%m%d %H%M%S',     # YYYYMMDD HHMMSS
                '%Y-%m-%d %H:%M:%S', # YYYY-MM-DD HH:MM:SS
                '%Y%m%d',            # YYYYMMDD
                '%Y-%m-%d'           # YYYY-MM-DD
            ]
            
            for fmt in time_formats:
                try:
                    current_datetime = datetime.strptime(current_time, fmt)
                    break
                except ValueError:
                    continue
            
            if current_datetime is None:
                raise ValueError(f"无法解析时间格式: {current_time}，支持的格式: YYYYMMDD, YYYY-MM-DD, YYYYMMDD HHMMSS, YYYY-MM-DD HH:MM:SS")
            
            current_date_str = current_datetime.strftime('%Y%m%d')
        else:
            raise ValueError("current_time必须是字符串格式")
    
    #print(f"解析的当前时间: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')} (不包含此时间点)")
    
    # 转换复权方式
    dividend_type_map = {
        'pre': 'front',
        'post': 'back', 
        'none': 'none'
    }
    dividend_type = dividend_type_map.get(fq, 'front')
    
    # 转换时间步长格式
    period_map = {
        '1d': '1d',
        '1m': '1m',
        '5m': '5m',
        'tick': 'tick'
    }
    period = period_map.get(fre_step, fre_step)
    
    result = {}
    
    try:
        if force_download:
            # 强制下载模式：先下载最新数据到指定时间，再获取
            print(f"强制下载模式：基于时间 {current_date_str} 下载最新数据")
            
            # 根据当前时间和bar_count计算开始时间
            start_date = None
            try:
                # 根据数据类型确定需要的历史天数
                if period == 'tick':
                    # tick数据只需要当天的数据，但要向前多取一些天以防当天无数据
                    target_days = 3
                elif period in ['1m', '5m']:
                    # 分钟数据，计算需要的天数，增加缓冲
                    target_days = max(10, (bar_count * 10 + 1439) // 1440)  # 增加缓冲
                elif period in ['1d']:
                    # 日线数据，增加缓冲天数
                    target_days = bar_count * 5  # 增加缓冲
                else:
                    target_days = bar_count * 3
                
                # 计算开始日期（往前推target_days天）
                start_dt = current_datetime - timedelta(days=target_days)
                start_date = start_dt.strftime('%Y%m%d')
                
                print(f"计算的数据范围: {start_date} 到 {current_date_str}")
                
            except Exception as e:
                print(f"计算时间范围出错: {str(e)}")
                # 如果计算失败，使用默认的往前推算逻辑
                start_dt = current_datetime - timedelta(days=bar_count * 5)
                start_date = start_dt.strftime('%Y%m%d')
            
            # 使用xtdata.download_history_data下载数据到指定时间
            download_count = 0
            for stock_code in stock_codes:
                try:
                    xtdata.download_history_data(
                        stock_code=stock_code,
                        period=period,
                        start_time=start_date,
                        end_time=current_date_str
                    )
                    download_count += 1
                except Exception as e:
                    print(f"下载 {stock_code} 数据失败: {str(e)}")
            
            print(f"成功下载 {download_count}/{len(stock_codes)} 只股票的数据")
        
        # 使用xtdata.get_market_data_ex获取数据
        #print(f"从本地获取数据，基于时间: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 计算实际的数据获取范围
        # 根据频率确定往前推算的天数，增加缓冲以确保有足够的历史数据
        if period == 'tick':
            # tick数据只获取当天的，但向前多取几天
            lookback_days = 3
        elif period in ['1m', '5m']:
            # 分钟数据，往前推算较多天数以确保有足够数据
            lookback_days = max(10, (bar_count * 10 + 1439) // 1440)  # 增加缓冲
        elif period in ['1d']:
            # 日线数据，往前推算更多天数以确保有足够的交易日
            lookback_days = bar_count * 5  # 增加缓冲
        else:
            lookback_days = bar_count * 3
        
        start_dt = current_datetime - timedelta(days=lookback_days)
        start_time = start_dt.strftime('%Y%m%d')
        end_time = current_date_str
        
        #print(f"实际查询范围: {start_time} 到 {end_time}")
        
        # 获取数据
        data = xtdata.get_market_data_ex(
            field_list=['time'] + fields,
            stock_list=stock_codes,
            period=period,
            start_time=start_time,
            end_time=end_time,
            count=-1,
            dividend_type=dividend_type,
            fill_data=True
        )
        
        if not data:
            print("未获取到任何数据")
            return {}
        
        # 处理每只股票的数据
        for stock_code in stock_codes:
            if stock_code not in data:
                print(f"警告: 股票 {stock_code} 无数据")
                result[stock_code] = pd.DataFrame()
                continue
            
            stock_data = data[stock_code]
            
            if stock_data is None or stock_data.empty:
                print(f"警告: 股票 {stock_code} 数据为空")
                result[stock_code] = pd.DataFrame()
                continue
            
            # 复制数据避免修改原始数据
            stock_data = stock_data.copy()
            
            # 处理时间列
            if 'time' in stock_data.columns:
                # 转换时间列
                stock_data['time'] = pd.to_datetime(stock_data['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)
                
                # 筛选到指定时间之前的数据（不包含当前时间点）
                if period == 'tick':
                    # tick数据按精确时间筛选，不包含当前时间点
                    mask = stock_data['time'] < current_datetime
                elif period in ['1m', '5m']:
                    # 分钟数据按精确时间筛选，不包含当前时间点
                    mask = stock_data['time'] < current_datetime
                else:
                    # 日线数据只比较日期部分，不包含当前日期
                    mask = stock_data['time'].dt.date < current_datetime.date()
                
                stock_data = stock_data[mask]
                
                # 按时间排序
                stock_data = stock_data.sort_values('time').reset_index(drop=True)
            
            # 跳过停牌数据处理
            if skip_paused and 'volume' in stock_data.columns:
                # 过滤掉成交量为0的数据（停牌日）
                original_len = len(stock_data)
                stock_data = stock_data[stock_data['volume'] > 0].reset_index(drop=True)
                filtered_len = len(stock_data)
                if original_len != filtered_len:
                    print(f"股票 {stock_code} 过滤停牌数据: {original_len} -> {filtered_len}")
            
            # 取最近的bar_count条记录
            if not stock_data.empty and len(stock_data) > bar_count:
                stock_data = stock_data.tail(bar_count).reset_index(drop=True)
            
            # 重新整理列顺序，确保time列在前
            columns_order = ['time'] + [col for col in fields if col in stock_data.columns]
            stock_data = stock_data[columns_order]
            
            result[stock_code] = stock_data
            #print(f"股票 {stock_code}: 获取 {len(stock_data)} 条记录")
            
            # 显示时间范围
            if not stock_data.empty and 'time' in stock_data.columns:
                time_range = f"{stock_data['time'].min()} 到 {stock_data['time'].max()}"
                #print(f"  时间范围: {time_range}")
                
                # 验证数据确实不包含当前时间点
                if period in ['1d']:
                    latest_date = stock_data['time'].dt.date.max()
                    if latest_date >= current_datetime.date():
                        print(f"  ⚠️ 警告: 数据包含当前日期或之后的日期")
                else:
                    latest_time = stock_data['time'].max()
                    if latest_time >= current_datetime:
                        print(f"  ⚠️ 警告: 数据包含当前时间或之后的时间")
    
    except Exception as e:
        print(f"获取历史数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}
    
    return result


def test_khHistory():
    """测试khHistory函数的各种参数组合"""
    print("开始测试khHistory函数...")
    print("=" * 50)
    
    # 测试1: 基本功能测试（使用当前时间）
    print("\n测试1: 基本功能测试（当前时间）")
    print("-" * 40)
    try:
        result1 = khHistory(
            symbol_list='000001.SZ',
            fields=['open', 'close', 'volume'],
            bar_count=10,
            fre_step='1d',
            force_download=True
        )
        if '000001.SZ' in result1 and not result1['000001.SZ'].empty:
            df = result1['000001.SZ']
            print(f"✓ 当前时间测试: 获取 {len(df)} 条记录")
            print(f"  列名: {list(df.columns)}")
            if 'time' in df.columns:
                time_range = f"{df['time'].min()} 到 {df['time'].max()}"
                print(f"  时间范围: {time_range}")
                # 验证不包含当前日期
                from datetime import datetime
                today = datetime.now().date()
                latest_date = df['time'].dt.date.max()
                if latest_date < today:
                    print(f"  ✓ 验证通过: 数据不包含当前日期 {today}")
                else:
                    print(f"  ✗ 验证失败: 数据包含当前日期或之后的日期")
        else:
            print("✗ 当前时间测试: 未获取到数据")
    except Exception as e:
        print(f"✗ 当前时间测试: 出错 - {str(e)}")
    
    # 测试2: 指定历史日期测试
    print("\n测试2: 指定历史日期测试")
    print("-" * 40)
    test_dates = ['20241201', '2024-12-01', '20241115']
    
    for test_date in test_dates:
        try:
            result2 = khHistory(
                symbol_list='000001.SZ',
                fields=['close', 'volume'],
                bar_count=5,
                fre_step='1d',
                current_time=test_date,
                force_download=True
            )
            if '000001.SZ' in result2 and not result2['000001.SZ'].empty:
                df = result2['000001.SZ']
                print(f"✓ 日期{test_date}: 获取 {len(df)} 条记录")
                if 'time' in df.columns:
                    time_range = f"{df['time'].min()} 到 {df['time'].max()}"
                    print(f"  时间范围: {time_range}")
                    # 验证不包含指定日期
                    from datetime import datetime
                    if '-' in test_date:
                        target_date = datetime.strptime(test_date, '%Y-%m-%d').date()
                    else:
                        target_date = datetime.strptime(test_date, '%Y%m%d').date()
                    latest_date = df['time'].dt.date.max()
                    if latest_date < target_date:
                        print(f"  ✓ 验证通过: 数据不包含目标日期 {target_date}")
                    else:
                        print(f"  ✗ 验证失败: 数据包含目标日期或之后的日期")
            else:
                print(f"✗ 日期{test_date}: 未获取到数据")
        except Exception as e:
            print(f"✗ 日期{test_date}: 出错 - {str(e)}")
    
    # 测试3: 指定精确时间测试（分钟数据）
    print("\n测试3: 指定精确时间测试（分钟数据）")
    print("-" * 40)
    test_times = [
        '20241201 143000',      # YYYYMMDD HHMMSS
        '2024-12-01 14:30:00',  # YYYY-MM-DD HH:MM:SS
        '20241201 100000',      # 上午10点
        '2024-12-01 15:00:00'   # 下午3点
    ]
    
    for test_time in test_times:
        try:
            result3 = khHistory(
                symbol_list='000001.SZ',
                fields=['close', 'volume'],
                bar_count=10,
                fre_step='5m',
                current_time=test_time,
                force_download=True
            )
            if '000001.SZ' in result3 and not result3['000001.SZ'].empty:
                df = result3['000001.SZ']
                print(f"✓ 时间{test_time}: 获取 {len(df)} 条记录")
                if 'time' in df.columns:
                    time_range = f"{df['time'].min()} 到 {df['time'].max()}"
                    print(f"  时间范围: {time_range}")
                    # 验证不包含指定时间
                    from datetime import datetime
                    if ' ' in test_time:
                        if ':' in test_time:
                            target_time = datetime.strptime(test_time, '%Y-%m-%d %H:%M:%S')
                        else:
                            target_time = datetime.strptime(test_time, '%Y%m%d %H%M%S')
                    else:
                        target_time = datetime.strptime(test_time, '%Y%m%d')
                    
                    latest_time = df['time'].max()
                    if latest_time < target_time:
                        print(f"  ✓ 验证通过: 数据不包含目标时间 {target_time}")
                    else:
                        print(f"  ✗ 验证失败: 数据包含目标时间或之后的时间")
            else:
                print(f"✗ 时间{test_time}: 未获取到数据")
        except Exception as e:
            print(f"✗ 时间{test_time}: 出错 - {str(e)}")
    
    # 测试4: 多股票测试（指定时间）
    print("\n测试4: 多股票测试（指定时间）")
    print("-" * 40)
    try:
        result4 = khHistory(
            symbol_list=['000001.SZ', '600000.SH'],
            fields=['close', 'volume'],
            bar_count=3,
            fre_step='1d',
            current_time='20241201',
            force_download=True
        )
        for stock_code in ['000001.SZ', '600000.SH']:
            if stock_code in result4 and not result4[stock_code].empty:
                df = result4[stock_code]
                print(f"✓ {stock_code}: 获取 {len(df)} 条记录")
            else:
                print(f"✗ {stock_code}: 未获取到数据")
    except Exception as e:
        print(f"✗ 多股票测试: 出错 - {str(e)}")
    
    # 测试5: 跳过停牌数据测试（指定时间）
    print("\n测试5: 跳过停牌数据测试（指定时间）")
    print("-" * 40)
    for skip in [False, True]:
        try:
            result5 = khHistory(
                symbol_list='000001.SZ',
                fields=['close', 'volume'],
                bar_count=20,
                fre_step='1d',
                current_time='20241201',
                skip_paused=skip,
                force_download=True
            )
            if '000001.SZ' in result5 and not result5['000001.SZ'].empty:
                df = result5['000001.SZ']
                zero_volume_count = (df['volume'] == 0).sum()
                print(f"✓ 跳过停牌={skip}: 获取 {len(df)} 条记录，其中成交量为0的有 {zero_volume_count} 条")
            else:
                print(f"✗ 跳过停牌={skip}: 未获取到数据")
        except Exception as e:
            print(f"✗ 跳过停牌={skip}: 出错 - {str(e)}")
    
    # 测试6: 强制下载性能测试（指定时间）
    print("\n测试6: 强制下载性能测试（指定时间）")
    print("-" * 40)
    try:
        import time
        start_time = time.time()
        
        result6 = khHistory(
            symbol_list='000001.SZ',
            fields=['close', 'volume'],
            bar_count=5,
            fre_step='1d',
            current_time='20241201',
            force_download=True
        )
        
        end_time = time.time()
        elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        if '000001.SZ' in result6 and not result6['000001.SZ'].empty:
            df = result6['000001.SZ']
            print(f"✓ 强制下载性能测试: 获取 {len(df)} 条记录，耗时 {elapsed_time:.1f}ms")
            if 'time' in df.columns:
                time_range = f"{df['time'].min()} 到 {df['time'].max()}"
                print(f"  时间范围: {time_range}")
        else:
            print(f"✗ 强制下载性能测试: 未获取到数据，耗时 {elapsed_time:.1f}ms")
    except Exception as e:
        print(f"✗ 强制下载性能测试: 出错 - {str(e)}")
    
    # 测试7: 分钟数据精确时间控制测试
    print("\n测试7: 分钟数据精确时间控制测试")
    print("-" * 40)
    minute_tests = [
        ('1m', '2024-12-01 10:30:00', 30),   # 1分钟数据，获取30条
        ('5m', '2024-12-01 14:30:00', 12),   # 5分钟数据，获取12条
        ('1d', '20241201', 8)                # 日线数据，获取8条
    ]
    
    for freq, test_time, count in minute_tests:
        try:
            result7 = khHistory(
                symbol_list='000001.SZ',
                fields=['close', 'volume'],
                bar_count=count,
                fre_step=freq,
                current_time=test_time,
                force_download=True
            )
            if '000001.SZ' in result7 and not result7['000001.SZ'].empty:
                df = result7['000001.SZ']
                print(f"✓ {freq}数据到{test_time}: 获取 {len(df)} 条记录")
                if 'time' in df.columns:
                    time_range = f"{df['time'].min()} 到 {df['time'].max()}"
                    print(f"  时间范围: {time_range}")
            else:
                print(f"✗ {freq}数据到{test_time}: 未获取到数据")
        except Exception as e:
            print(f"✗ {freq}数据到{test_time}: 出错 - {str(e)}")
    
    # 测试8: 复权方式测试（指定时间）
    print("\n测试8: 复权方式测试（指定时间）")
    print("-" * 40)
    for fq_type in ['none', 'pre', 'post']:
        try:
            result8 = khHistory(
                symbol_list='000001.SZ',
                fields=['close'],
                bar_count=3,
                fre_step='1d',
                current_time='20241201',
                fq=fq_type,
                force_download=True
            )
            if '000001.SZ' in result8 and not result8['000001.SZ'].empty:
                df = result8['000001.SZ']
                close_prices = df['close'].tolist()
                print(f"✓ 复权方式{fq_type}: 获取 {len(df)} 条记录，收盘价: {close_prices}")
            else:
                print(f"✗ 复权方式{fq_type}: 未获取到数据")
        except Exception as e:
            print(f"✗ 复权方式{fq_type}: 出错 - {str(e)}")
    
    # 测试9: 时间边界验证测试
    print("\n测试9: 时间边界验证测试")
    print("-" * 40)
    boundary_tests = [
        ('20241201', '获取2024-12-01之前的数据'),
        ('2024-12-01 09:30:00', '获取9:30之前的分钟数据'),
        ('20241215 143000', '获取14:30之前的数据')
    ]
    
    for time_str, desc in boundary_tests:
        try:
            is_minute = ' ' in time_str
            freq = '5m' if is_minute else '1d'
            
            result9 = khHistory(
                symbol_list='000001.SZ',
                fields=['close'],
                bar_count=5,
                fre_step=freq,
                current_time=time_str,
                force_download=True
            )
            if '000001.SZ' in result9 and not result9['000001.SZ'].empty:
                df = result9['000001.SZ']
                print(f"✓ {desc}: 获取 {len(df)} 条记录")
                if 'time' in df.columns and len(df) > 0:
                    latest_time = df['time'].max()
                    print(f"  最新时间: {latest_time}")
                    
                    # 解析目标时间进行验证
                    from datetime import datetime
                    if ':' in time_str:
                        if '-' in time_str:
                            target_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            target_time = datetime.strptime(time_str, '%Y%m%d %H%M%S')
                    else:
                        if '-' in time_str:
                            target_time = datetime.strptime(time_str, '%Y-%m-%d')
                        else:
                            target_time = datetime.strptime(time_str, '%Y%m%d')
                    
                    if is_minute:
                        # 分钟数据精确时间比较
                        if latest_time < target_time:
                            print(f"  ✓ 时间边界验证通过: {latest_time} < {target_time}")
                        else:
                            print(f"  ✗ 时间边界验证失败: {latest_time} >= {target_time}")
                    else:
                        # 日线数据按日期比较
                        if latest_time.date() < target_time.date():
                            print(f"  ✓ 日期边界验证通过: {latest_time.date()} < {target_time.date()}")
                        else:
                            print(f"  ✗ 日期边界验证失败: {latest_time.date()} >= {target_time.date()}")
            else:
                print(f"✗ {desc}: 未获取到数据")
        except Exception as e:
            print(f"✗ {desc}: 出错 - {str(e)}")
    
    print("\n" + "=" * 50)
    print("khHistory函数测试完成（不包含当前时间点，适合回测场景）")


# ============================================================================
# 便利实例 - 为了向后兼容，创建一个默认实例
# ============================================================================

# 创建一个默认的工具实例，供旧代码兼容使用
# 这样 `from khQTTools import KhQuTools; tools = KhQuTools()` 和 `from khQTTools import tools` 都能工作
tools = KhQuTools()

if __name__ == "__main__":
    test_khHistory()