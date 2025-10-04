# coding: utf-8
"""
数据提供者抽象层 - 支持多数据源切换
适配器模式实现，方便在 xtquant 和 mootdx 之间切换

作者: khQuant团队
版本: V1.0.0
日期: 2025-10-02
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
import pandas as pd
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# Mootdx原始数据缓存 (模块级)
_mootdx_raw_cache = {}


# ============================================================================
# 抽象接口层
# ============================================================================

class DataProviderInterface(ABC):
    """数据提供者抽象接口"""

    @abstractmethod
    def download_history_data(
        self,
        stock_code: Union[str, List[str]],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        **kwargs
    ) -> bool:
        """下载历史数据到本地

        Args:
            stock_code: 股票代码或代码列表
            period: 周期 ('1m', '5m', '15m', '30m', '1h', '1d', '1w', '1mon')
            start_time: 开始时间 (格式: '20240101')
            end_time: 结束时间 (格式: '20241231')

        Returns:
            bool: 是否成功
        """
        pass

    @abstractmethod
    def get_market_data(
        self,
        field_list: List[str],
        stock_list: List[str],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        count: int = -1,
        dividend_type: str = 'none',
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """获取市场行情数据

        Args:
            field_list: 字段列表 ['open', 'high', 'low', 'close', 'volume', 'amount']
            stock_list: 股票代码列表
            period: 周期
            start_time: 开始时间
            end_time: 结束时间
            count: 获取数量 (-1表示全部)
            dividend_type: 复权类型 ('none', 'front', 'back')

        Returns:
            Dict[str, pd.DataFrame]: {股票代码: DataFrame}
        """
        pass

    @abstractmethod
    def get_stock_list_in_sector(
        self,
        sector_name: str,
        **kwargs
    ) -> List[str]:
        """获取板块成分股列表

        Args:
            sector_name: 板块名称 ('沪深A股', '沪深300', '科创板', 等)

        Returns:
            List[str]: 股票代码列表
        """
        pass

    @abstractmethod
    def get_stock_list(self, market: str = 'stock', **kwargs) -> List[str]:
        """获取股票列表

        Args:
            market: 市场类型 ('stock', 'index', 'etf', 等)

        Returns:
            List[str]: 股票代码列表
        """
        pass

    @abstractmethod
    def normalize_stock_code(self, code: str) -> str:
        """标准化股票代码格式

        Args:
            code: 原始代码 (如 '600036' 或 '600036.SH')

        Returns:
            str: 标准化后的代码
        """
        pass

    @abstractmethod
    def get_sector_list(self, **kwargs) -> List[str]:
        """获取所有板块列表

        Returns:
            List[str]: 板块名称列表
        """
        pass

    @abstractmethod
    def download_sector_data(self, **kwargs) -> bool:
        """下载板块数据

        Returns:
            bool: 是否成功
        """
        pass

    @abstractmethod
    def get_instrument_detail(self, stock_code: str, **kwargs) -> Optional[Dict]:
        """获取证券详细信息

        Args:
            stock_code: 股票代码

        Returns:
            Dict: 证券详细信息 (包含InstrumentID, InstrumentName等字段)
        """
        pass


# ============================================================================
# XtQuant 适配器
# ============================================================================

class XtQuantAdapter(DataProviderInterface):
    """XtQuant (MiniQMT) 数据适配器"""

    def __init__(self):
        """初始化 XtQuant 适配器"""
        try:
            from xtquant import xtdata
            self.xtdata = xtdata
            logger.info("XtQuant 数据适配器初始化成功")
        except ImportError as e:
            logger.error(f"XtQuant 导入失败: {e}")
            raise RuntimeError("请先安装并启动 MiniQMT 客户端")

    def download_history_data(
        self,
        stock_code: Union[str, List[str]],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        **kwargs
    ) -> bool:
        """下载历史数据"""
        try:
            if isinstance(stock_code, str):
                stock_code = [stock_code]

            # 调用 xtdata.download_history_data2
            self.xtdata.download_history_data2(
                stock_code,
                period=period,
                start_time=start_time,
                end_time=end_time,
                incrementally=kwargs.get('incrementally', True)
            )
            logger.info(f"成功下载 {len(stock_code)} 只股票的历史数据")
            return True
        except Exception as e:
            logger.error(f"下载历史数据失败: {e}")
            return False

    def get_market_data(
        self,
        field_list: List[str],
        stock_list: List[str],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        count: int = -1,
        dividend_type: str = 'none',
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """获取市场行情数据"""
        try:
            # 调用 xtdata.get_market_data_ex
            data = self.xtdata.get_market_data_ex(
                field_list=['time'] + field_list,
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
                dividend_type=dividend_type
            )
            return data
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return {}

    def get_stock_list_in_sector(self, sector_name: str, **kwargs) -> List[str]:
        """获取板块成分股"""
        try:
            stocks = self.xtdata.get_stock_list_in_sector(sector_name)
            return stocks if stocks else []
        except Exception as e:
            logger.error(f"获取板块成分股失败: {e}")
            return []

    def get_stock_list(self, market: str = 'stock', **kwargs) -> List[str]:
        """获取股票列表"""
        try:
            # XtQuant 通过板块获取
            sector_mapping = {
                'stock': '沪深A股',
                'index': '指数',
                'etf': 'ETF'
            }
            sector = sector_mapping.get(market, '沪深A股')
            return self.get_stock_list_in_sector(sector)
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def get_sector_list(self, **kwargs) -> List[str]:
        """获取所有板块列表"""
        try:
            return self.xtdata.get_sector_list()
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")
            return []

    def download_sector_data(self, **kwargs) -> bool:
        """下载板块数据"""
        try:
            self.xtdata.download_sector_data()
            return True
        except Exception as e:
            logger.error(f"下载板块数据失败: {e}")
            return False

    def get_instrument_detail(self, stock_code: str, **kwargs) -> Optional[Dict]:
        """获取证券详细信息"""
        try:
            detail = self.xtdata.get_instrument_detail(stock_code)
            if detail:
                return detail
            return None
        except Exception as e:
            logger.error(f"获取证券详情失败 {stock_code}: {e}")
            return None

    def normalize_stock_code(self, code: str) -> str:
        """XtQuant 使用 '代码.市场' 格式 (如 '600036.SH')"""
        if '.' in code:
            return code

        # 自动添加市场后缀
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"
        else:
            return code


# ============================================================================
# Mootdx 适配器
# ============================================================================

class MootdxAdapter(DataProviderInterface):
    """Mootdx (通达信) 数据适配器"""

    def __init__(self, mode: str = 'online', tdxdir: str = None):
        """初始化 Mootdx 适配器

        Args:
            mode: 模式 ('online' 在线, 'offline' 离线)
            tdxdir: 通达信数据目录（离线模式必需）
        """
        try:
            from mootdx.quotes import Quotes
            from mootdx.reader import Reader
            from mootdx.consts import MARKET_SH, MARKET_SZ

            self.mode = mode
            self.MARKET_SH = MARKET_SH
            self.MARKET_SZ = MARKET_SZ

            if mode == 'online':
                self.client = Quotes.factory(
                    market='std',
                    multithread=True,
                    heartbeat=True,
                    bestip=False,  # 关闭最优IP选择以提高速度
                    timeout=15
                )
                logger.info("Mootdx 在线模式初始化成功")
            else:
                if not tdxdir:
                    raise ValueError("离线模式需要指定 tdxdir 参数")
                self.reader = Reader.factory(market='std', tdxdir=tdxdir)
                logger.info(f"Mootdx 离线模式初始化成功: {tdxdir}")

        except ImportError as e:
            logger.error(f"Mootdx 导入失败: {e}")
            raise RuntimeError("请先安装 mootdx: pip install mootdx")

    def _call_mootdx_with_retry(self, is_index, clean_code, frequency, offset, adjust=None, max_retries=3):
        """带缓存和重试的Mootdx调用"""
        # 生成缓存键
        cache_key = (clean_code, frequency, offset, adjust, is_index)

        # 检查缓存
        global _mootdx_raw_cache
        if cache_key in _mootdx_raw_cache:
            # logger.info(f"✅ [Mootdx缓存命中] {clean_code}")
            return _mootdx_raw_cache[cache_key].copy()

        # 缓存未命中,网络请求 (带重试)
        logger.info(f"❌ [Mootdx缓存未命中] {clean_code}, 开始网络请求...")

        for attempt in range(max_retries):
            try:
                start_time = time.time()

                if is_index:
                    df = self.client.index_bars(symbol=clean_code, frequency=frequency, offset=offset)
                else:
                    df = self.client.bars(symbol=clean_code, frequency=frequency, offset=offset, adjust=adjust)

                elapsed = time.time() - start_time

                if df is not None and not df.empty:
                    _mootdx_raw_cache[cache_key] = df.copy()
                    logger.info(f"💾 [Mootdx缓存已更新] {clean_code}, shape={df.shape}, 耗时={elapsed:.2f}秒")
                    return df
                elif df is not None:
                    logger.warning(f"⚠️ [Mootdx返回空数据] {clean_code}")
                    return df

            except Exception as e:
                logger.warning(f"Mootdx调用失败 (尝试{attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避

        logger.error(f"❌ [Mootdx调用最终失败] {clean_code}")
        return None

    @classmethod
    def clear_mootdx_cache(cls):
        """清理缓存"""
        global _mootdx_raw_cache
        count = len(_mootdx_raw_cache)
        _mootdx_raw_cache.clear()
        logger.info(f"已清理Mootdx缓存, 释放{count}条记录")
        return count

    def download_history_data(
        self,
        stock_code: Union[str, List[str]],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        **kwargs
    ) -> bool:
        """下载历史数据（Mootdx 自动在线获取，无需单独下载）"""
        # Mootdx采用按需加载模式,无需预下载 (正常设计,不需要WARNING)
        logger.debug("Mootdx 模式采用按需加载,跳过预下载步骤")
        return True

    def get_market_data(
        self,
        field_list: List[str],
        stock_list: List[str],
        period: str = '1d',
        start_time: str = '',
        end_time: str = '',
        count: int = -1,
        dividend_type: str = 'none',
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """获取市场行情数据"""
        try:
            result = {}

            # 转换周期参数
            frequency_map = {
                '1m': 7,
                '5m': 0,
                '15m': 1,
                '30m': 2,
                '60m': 3,
                '1h': 3,
                '1d': 9,
                '1w': 5,
                '1mon': 6
            }
            frequency = frequency_map.get(period, 9)

            # 转换复权参数
            adjust_map = {
                'none': '',
                'front': 'qfq',
                'back': 'hfq'
            }
            adjust = adjust_map.get(dividend_type, '')

            # 计算需要获取的数量
            offset = min(count if count > 0 else 800, 800)

            for code in stock_list:
                clean_code = self._clean_code(code)
                is_index = self._is_index(code)
                logger.debug(f"正在获取 {code} ({clean_code}) 的数据, period={period}, frequency={frequency}, offset={offset}, is_index={is_index}")

                if self.mode == 'online':
                    # 在线模式 (使用带缓存的调用)
                    df = self._call_mootdx_with_retry(
                        is_index=is_index,
                        clean_code=clean_code,
                        frequency=frequency,
                        offset=offset,
                        adjust=adjust
                    )
                    # 移除冗余DEBUG日志
                    # if df is not None and hasattr(df, 'shape'):
                    #     logger.debug(f"Mootdx返回: shape={df.shape}")
                else:
                    # 离线模式
                    if period == '1d':
                        df = self.reader.daily(symbol=clean_code)
                    elif period in ['1m', '5m']:
                        df = self.reader.minute(symbol=clean_code)
                    else:
                        logger.warning(f"离线模式不支持周期: {period}")
                        continue

                if df is not None and not df.empty:
                    # 重命名列以匹配 xtquant 格式
                    # 移除冗余DEBUG日志: logger.debug(f"标准化前: columns={list(df.columns)}, shape={df.shape}")
                    df = self._normalize_dataframe(df, field_list)
                    # 移除冗余DEBUG日志: logger.debug(f"标准化后: columns={list(df.columns)}, shape={df.shape}")

                    # 按时间范围筛选（mootdx不支持时间范围参数，需要手动筛选）
                    if not df.empty and start_time and end_time:
                        df = self._filter_by_time_range(df, start_time, end_time)
                        # 移除冗余DEBUG日志: logger.debug(f"时间筛选后: shape={df.shape}")

                    if not df.empty:
                        result[code] = df
                        logger.info(f"成功添加 {code} 数据到结果集")
                    else:
                        logger.warning(f"标准化后 {code} 数据为空")
                else:
                    logger.warning(f"{code} 原始数据为空或None")

            return result

        except Exception as e:
            logger.error(f"Mootdx 获取市场数据失败: {e}")
            return {}

    def get_stock_list_in_sector(self, sector_name: str, **kwargs) -> List[str]:
        """获取板块成分股"""
        try:
            if self.mode == 'offline':
                logger.warning("离线模式不支持获取板块成分股")
                return []

            # 获取板块数据
            df = self.client.block_stocks(block_name=sector_name)

            if df is not None and not df.empty:
                codes = df['code'].tolist()
                # 添加市场后缀
                return [self.normalize_stock_code(c) for c in codes]
            return []

        except Exception as e:
            logger.error(f"获取板块成分股失败: {e}")
            return []

    def get_stock_list(self, market: str = 'stock', **kwargs) -> List[str]:
        """获取股票列表"""
        try:
            if self.mode == 'offline':
                logger.warning("离线模式不支持获取股票列表")
                return []

            df = self.client.stocks(market=0 if market == 'stock' else 1)

            if df is not None and not df.empty:
                codes = df['code'].tolist()
                return [self.normalize_stock_code(c) for c in codes]
            return []

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    def get_sector_list(self, **kwargs) -> List[str]:
        """获取所有板块列表"""
        try:
            # mootdx 不直接支持获取板块列表,返回常用板块
            return [
                '沪深A股', '沪深300', '上证50', '中证500', '创业板',
                '科创板', '沪深京A股', '北交所', '沪深转债'
            ]
        except Exception as e:
            logger.error(f"获取板块列表失败: {e}")
            return []

    def download_sector_data(self, **kwargs) -> bool:
        """下载板块数据 (mootdx不需要此操作)"""
        logger.info("Mootdx不需要下载板块数据")
        return True

    def get_instrument_detail(self, stock_code: str, **kwargs) -> Optional[Dict]:
        """获取证券详细信息"""
        try:
            # mootdx 不直接支持获取详细信息,返回基本信息
            clean_code = self._clean_code(stock_code)
            return {
                'InstrumentID': stock_code,
                'InstrumentName': '',  # mootdx没有名称信息
                'ExchangeID': 'SH' if clean_code.startswith('6') else 'SZ'
            }
        except Exception as e:
            logger.error(f"获取证券详情失败 {stock_code}: {e}")
            return None

    def normalize_stock_code(self, code: str) -> str:
        """Mootdx 转换为 xtquant 格式 (添加市场后缀)"""
        # 去除已有后缀
        clean_code = self._clean_code(code)

        # 添加标准后缀
        if clean_code.startswith('6'):
            return f"{clean_code}.SH"
        elif clean_code.startswith('0') or clean_code.startswith('3'):
            return f"{clean_code}.SZ"
        else:
            return clean_code

    def _clean_code(self, code: str) -> str:
        """去除股票代码的市场后缀"""
        return code.split('.')[0] if '.' in code else code

    def _is_index(self, code: str) -> bool:
        """判断是否为指数代码

        区分规则:
        - 上海指数: 000开头 + .SH后缀 (如 000001.SH, 000300.SH)
        - 深圳指数: 399开头 + .SZ后缀 (如 399001.SZ, 399006.SZ)
        - 深圳股票: 000/001/002/003开头 + .SZ后缀 (如 000001.SZ 平安银行)

        注意: 必须同时判断代码和市场后缀！
        """
        if '.' not in code:
            return False

        clean_code, market = code.split('.')

        # 上海市场: 000开头的是指数
        if market == 'SH' and clean_code.startswith('000'):
            return True

        # 深圳市场: 只有 399开头的是指数
        if market == 'SZ' and clean_code.startswith('399'):
            return True

        return False

    def _normalize_dataframe(self, df: pd.DataFrame, field_list: List[str]) -> pd.DataFrame:
        """标准化 DataFrame 列名和格式"""
        # Mootdx 列名: ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
        # XtQuant 列名: ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']

        if 'date' in df.columns:
            df = df.rename(columns={'date': 'time'})

        # 只保留需要的字段
        available_fields = [f for f in ['time'] + field_list if f in df.columns]
        return df[available_fields]

    def _filter_by_time_range(self, df: pd.DataFrame, start_time: str, end_time: str) -> pd.DataFrame:
        """按时间范围筛选数据

        Args:
            df: DataFrame with DatetimeIndex
            start_time: 开始时间 '20250101'
            end_time: 结束时间 '20250703'

        Returns:
            筛选后的 DataFrame
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning("数据索引不是 DatetimeIndex，无法按时间筛选")
            return df

        try:
            # 解析时间字符串
            start_dt = pd.to_datetime(start_time, format='%Y%m%d')
            end_dt = pd.to_datetime(end_time, format='%Y%m%d')

            # 筛选数据（包含起止日期）
            mask = (df.index.date >= start_dt.date()) & (df.index.date <= end_dt.date())
            filtered_df = df[mask]

            logger.info(f"时间筛选: {start_time} ~ {end_time}, 原始{len(df)}条 -> 筛选后{len(filtered_df)}条")
            return filtered_df

        except Exception as e:
            logger.error(f"时间筛选失败: {e}")
            return df


# ============================================================================
# 数据提供者工厂
# ============================================================================

class DataProviderFactory:
    """数据提供者工厂类"""

    _instance = None
    _provider: DataProviderInterface = None

    @classmethod
    def get_provider(
        cls,
        provider_type: str = 'xtquant',
        **kwargs
    ) -> DataProviderInterface:
        """获取数据提供者实例（单例模式）

        Args:
            provider_type: 提供者类型 ('xtquant', 'mootdx')
            **kwargs: 初始化参数
                - mode: Mootdx 模式 ('online', 'offline')
                - tdxdir: 通达信目录 (Mootdx 离线模式必需)

        Returns:
            DataProviderInterface: 数据提供者实例

        Example:
            >>> # 使用 XtQuant
            >>> provider = DataProviderFactory.get_provider('xtquant')
            >>>
            >>> # 使用 Mootdx 在线模式
            >>> provider = DataProviderFactory.get_provider('mootdx', mode='online')
            >>>
            >>> # 使用 Mootdx 离线模式
            >>> provider = DataProviderFactory.get_provider(
            ...     'mootdx',
            ...     mode='offline',
            ...     tdxdir='C:/new_tdx'
            ... )
        """
        # 如果已有实例且类型相同，直接返回
        if cls._provider is not None:
            current_type = type(cls._provider).__name__
            requested_type = f"{provider_type.capitalize()}Adapter"
            if current_type == requested_type:
                return cls._provider

        # 创建新实例
        if provider_type.lower() == 'xtquant':
            cls._provider = XtQuantAdapter()
        elif provider_type.lower() == 'mootdx':
            mode = kwargs.get('mode', 'online')
            tdxdir = kwargs.get('tdxdir', None)
            cls._provider = MootdxAdapter(mode=mode, tdxdir=tdxdir)
        else:
            raise ValueError(f"不支持的数据提供者类型: {provider_type}")

        return cls._provider

    @classmethod
    def switch_provider(cls, provider_type: str, **kwargs):
        """切换数据提供者

        Args:
            provider_type: 提供者类型
            **kwargs: 初始化参数
        """
        cls._provider = None
        return cls.get_provider(provider_type, **kwargs)


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 示例1: 使用 XtQuant
    print("=" * 60)
    print("示例1: 使用 XtQuant 数据提供者")
    print("=" * 60)

    try:
        provider = DataProviderFactory.get_provider('xtquant')

        # 下载历史数据
        provider.download_history_data(
            stock_code=['600036.SH', '000001.SZ'],
            period='1d',
            start_time='20240101',
            end_time='20241231'
        )

        # 获取行情数据
        data = provider.get_market_data(
            field_list=['open', 'high', 'low', 'close', 'volume'],
            stock_list=['600036.SH'],
            period='1d',
            count=10
        )

        print(f"获取到 {len(data)} 只股票数据")
        for code, df in data.items():
            print(f"\n{code}:")
            print(df.head())
    except Exception as e:
        print(f"XtQuant 示例失败: {e}")

    # 示例2: 使用 Mootdx (在线模式)
    print("\n" + "=" * 60)
    print("示例2: 使用 Mootdx 数据提供者（在线模式）")
    print("=" * 60)

    try:
        provider = DataProviderFactory.switch_provider('mootdx', mode='online')

        # 获取行情数据
        data = provider.get_market_data(
            field_list=['open', 'high', 'low', 'close', 'volume'],
            stock_list=['600036.SH', '000001.SZ'],
            period='1d',
            count=10
        )

        print(f"获取到 {len(data)} 只股票数据")
        for code, df in data.items():
            print(f"\n{code}:")
            print(df.head())

        # 获取板块成分股
        stocks = provider.get_stock_list_in_sector('沪深300')
        print(f"\n沪深300成分股数量: {len(stocks)}")
        print(f"前10只: {stocks[:10]}")

    except Exception as e:
        print(f"Mootdx 示例失败: {e}")
