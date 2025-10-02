# coding: utf-8
# 策略说明：
# - 策略名称：双均线精简（使用 khMA）
# - 功能：单只股票，比较当日 khMA5 与 khMA20；khMA5>khMA20 买入，khMA5<khMA20 卖出
# - 指标来源：使用 khQTTools 中的 khMA（内部封装的行情获取 + 移动平均）
from khQuantImport import *  # 导入所有量化工具

def init(stocks=None, data=None):  # 策略初始化函数
    """策略初始化"""

def khHandlebar(data: Dict) -> List[Dict]:  # 主策略函数
    """策略主逻辑，在每个K线或Tick数据到来时执行"""
    signals = []  # 初始化信号列表
    stock_code = khGet(data, "first_stock")  # 获取第一只股票代码
    current_price = khPrice(data, stock_code, "open")  # 获取当前开盘价
    current_date_str = khGet(data, "date_num")  # 获取当前日期数字格式

    ma_short = khMA(stock_code, 5, end_time=current_date_str)  # 计算5日均线
    ma_long = khMA(stock_code, 20, end_time=current_date_str)  # 计算20日均线

    # 如果均线计算失败（数据不足），跳过本次交易
    if ma_short is None or ma_long is None:
        return signals

    has_position = khHas(data, stock_code)  # 检查是否持有该股票

    if ma_short > ma_long and not has_position:  # 金叉且无持仓
        signals = generate_signal(data, stock_code, current_price, 1.0, 'buy', f"5日线({ma_short:.2f}) 上穿 20日线({ma_long:.2f})，全仓买入")  # 生成买入信号

    elif ma_short < ma_long and has_position:  # 死叉且有持仓
        signals = generate_signal(data, stock_code, current_price, 1.0, 'sell', f"5日线({ma_short:.2f}) 下穿 20日线({ma_long:.2f})，全仓卖出")  # 生成卖出信号

    return signals  # 返回交易信号

# khPreMarket 和 khPostMarket 函数省略，本次策略未使用
