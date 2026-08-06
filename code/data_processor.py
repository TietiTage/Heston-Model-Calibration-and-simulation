import pandas as pd
import numpy as np
import QuantLib as ql
from typing import Dict, Optional, Union, Literal
from datetime import datetime


def filter_calibration_options(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一的期权筛选函数。
    校准（setup_calibration_helpers）、每日校准（run_daily_calibration）
    与定价验证（get_calibration_data）共用同一套过滤条件。
    """
    # 极短到期日剔除
    df = df[df['T'] >= 0.02].copy()

    # 短期高流动性：接近平值的额外要求
    def short_term_filter(row: pd.Series) -> bool:
        """短期合约的流动性/虚实值约束：低流动性或深度虚值/实值合约剔除。"""
        if row['T'] < 0.05:
            if row.get('volume', 0) < 500 or abs(row.get('delta', 0)) > 0.65:
                return False
        return True

    df = df[df.apply(short_term_filter, axis=1)]

    # Delta 范围过滤 (0.1 ~ 0.9)
    if 'delta' in df.columns:
        df = df[(df['delta'].abs() >= 0.1) & (df['delta'].abs() <= 0.9)]

    # 价格必须为正且有限
    df = df[df['close'] > 0]
    df = df[np.isfinite(df['close'])]
    return df


class HestonDataProcessor:
    """数据中枢：加载并清洗期权数据，维护现货、股息率、利率等市场环境并计算 BS 隐含波动率。"""
    def __init__(self,
                 option_csv_path: str,
                 dividend_csv_path: str,
                 rate_df: pd.DataFrame) -> None:
        """
        Parameters
        ----------
        option_csv_path : str
            期权交易数据 CSV 文件路径
        dividend_csv_path : str
            包含沪深300收盘价和股息率的 CSV 文件路径
        rate_df : pd.DataFrame
            包含日期列和期限（0.25, 0.5, 1.0 …）列的利率数据
        """

        self.cleaned_data: Optional[pd.DataFrame] = None
        self.raw_data: Optional[pd.DataFrame] = None
        self.option_csv: str = option_csv_path
        self.dividend_csv: str = dividend_csv_path
        self.rate_df: pd.DataFrame = rate_df
        self.spot_map: Optional[Dict[pd.Timestamp, float]] = None
        self._dividend_df: Optional[pd.DataFrame] = None

        # 初始化时直接从股息率 CSV 中加载现货价格和股息率数据
        self._load_dividend_and_spot()

    @staticmethod
    def _to_timestamp(value: Union[str, pd.Timestamp, datetime]) -> pd.Timestamp:
        """将字符串转换为归一化后的 pd.Timestamp"""
        return pd.Timestamp(value).normalize()


    @staticmethod
    def _to_ql_date(value:Union[str, ql.Date, datetime, pd.Timestamp]) -> ql.Date:
        """将字符串 etc.转换为 QuantLib Date 对象"""
        if isinstance(value, ql.Date):
            return value
        else:
            ts = pd.Timestamp(value)
        return ql.Date(ts.day, ts.month, ts.year)

    def _load_dividend_and_spot(self) -> None:
        """
        读取股息率 CSV 文件，构建 spot_map 与 _dividend_df。
        要求文件中包含 '日期'、'收盘点位' 和 '股息率市值加权' 列。
        """
        div_df = pd.read_csv(self.dividend_csv, parse_dates=['日期'])
        div_df['日期'] = pd.to_datetime(div_df['日期']).dt.normalize()

        # 提取收盘点位作为标的资产价格
        spot_col = '收盘点位'
        if spot_col not in div_df.columns:
            raise ValueError(f"股息率文件中缺少 '{spot_col}' 列，无法获取标的资产价格。")
        div_df[spot_col] = pd.to_numeric(div_df[spot_col], errors='coerce')
        div_df_spot = div_df.dropna(subset=['日期', spot_col]).copy()
        self.spot_map = dict(zip(div_df_spot['日期'], div_df_spot[spot_col]))

        # 处理股息率
        div_col = '股息率市值加权'
        if div_col not in div_df.columns:
            raise ValueError(f"股息率文件中缺少 '{div_col}' 列。")
        div_df[div_col] = pd.to_numeric(div_df[div_col], errors='coerce')
        div_df = div_df.dropna(subset=['日期', div_col]).copy()
        div_df['q_cont'] = np.log1p(div_df[div_col].clip(lower=-0.999999))
        self._dividend_df = div_df.sort_values('日期').reset_index(drop=True)

    def get_underlying_quote(self, eval_date: Union[str, pd.Timestamp, datetime]) -> float:
        """
        根据评估日期返回沪深300收盘价。
        若当天没有数据，向前查找最近一个有效日。
        """
        if self.spot_map is None:
            raise ValueError("spot_map 未正确初始化，请检查股息率文件。")
        dt: pd.Timestamp = self._to_timestamp(eval_date)
        if dt in self.spot_map:
            return float(self.spot_map[dt])
        available_dates: list[pd.Timestamp] = sorted([d for d in self.spot_map.keys() if d <= dt])
        if available_dates:
            return float(self.spot_map[available_dates[-1]])
        raise ValueError(f"未找到 {eval_date} 及之前的沪深300收盘价")

    def load_and_clean_data(self) -> pd.DataFrame:
        """
        加载期权 CSV，进行流动性过滤、Delta 过滤、缺失值去除等清洗操作。
        """
        df = pd.read_csv(self.option_csv, parse_dates=['date', 'expiry'], encoding='gbk')

        # 最小剩余期限过滤---
        df: pd.DataFrame = df[df["T"] > 0.02]
        self.raw_data = df.copy()
        # 日期规范化
        df['date'] = pd.to_datetime(df['date']).dt.normalize()
        df['expiry'] = pd.to_datetime(df['expiry']).dt.normalize()

        # 期权类型标准化
        if 'cp' in df.columns:
            df['cp'] = df['cp'].astype(str).str.upper().str.strip()

        # 数值列类型转换
        numeric_cols = ['strike', 'close', 'volume', 'open_interest', 'delta', 'T']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 缺失值去除
        required_cols = ['date', 'expiry', 'strike', 'cp', 'close', 'T']
        df = df.dropna(subset=required_cols).copy()

        # 流动性过滤 ----
        # 成交量 > 50 且 持仓量 > 100
        if 'volume' in df.columns and 'open_interest' in df.columns:
            before = len(df)
            df = df[(df['volume'] > 50) & (df['open_interest'] > 100)]

            # df['voi_ratio'] = df['volume'] / df['open_interest'].replace(0, np.nan)
            # voi_mask = df['voi_ratio'].isna() | (df['voi_ratio'] <= 5.0)
            # df = df[voi_mask].copy()
            # df.drop(columns=['voi_ratio'], inplace=True)

            print(f"流动性过滤后: {len(df)} 条（过滤前 {before} 条）")

        # Delta 实值/虚值过滤 
        if 'delta' in df.columns:
            # 剔除深度实值和深度虚值
            lower_delta, upper_delta = 0.05, 0.9   
            df = df[(abs(df['delta']) >= lower_delta) & (abs(df['delta']) <= upper_delta)]
            print(f"Delta 过滤后: {len(df)} 条")

        df = df.sort_values(['date', 'expiry', 'strike', 'cp']).reset_index(drop=True)
        self.cleaned_data = df
        return df
    def _load_dividend_df(self) -> pd.DataFrame:
        """返回已加载的股息率 DataFrame"""
        if self._dividend_df is None:
            raise ValueError("股息率数据未加载，请先调用 _load_dividend_and_spot。")
        return self._dividend_df

    def get_dividend_yield(self, eval_date:Union[str, pd.Timestamp]) -> float:
        """
        获取指定评估日期的连续复利股息率。
        使用评估日前最近的可用股息率数据。
        """
        div_df = self._load_dividend_df()
        eval_date_norm = self._to_timestamp(eval_date)
        available = div_df[div_df['日期'] <= eval_date_norm].sort_values('日期')
        if available.empty:
            raise ValueError(f"没有找到 {eval_date} 之前的股息率数据")
        closest = available.iloc[-1]
        return float(closest['q_cont'])

    def _get_daily_rate_dict(self, eval_date: Union[str,pd.Timestamp]) -> Dict[float, float]:
        """获取指定日期的期限-利率字典"""
        eval_date_norm = self._to_timestamp(eval_date)
        available = self.rate_df[self.rate_df['date'] <= eval_date_norm].sort_values('date')
        if available.empty:
            raise ValueError(f"没有找到 {eval_date} 之前的利率数据")
        closest = available.iloc[-1]
        rate_dict = {}
        for col in self.rate_df.columns:
            if col != 'date':
                rate_dict[float(col)] = float(closest[col])
        return rate_dict

    def get_risk_free_rate(self, T: float, eval_date: Union[str, pd.Timestamp]) -> float:
        """
        根据剩余期限 T 和评估日获取连续复利无风险利率。
        使用线性插值填补已知期限点之间的利率。
        """
        daily_rate_dict = self._get_daily_rate_dict(eval_date)
        tenors = sorted(daily_rate_dict.keys())
        if T <= tenors[0]:
            return daily_rate_dict[tenors[0]]
        for i in range(len(tenors) - 1):
            t0, t1 = tenors[i], tenors[i + 1]
            if t0 <= T <= t1:
                r0 = daily_rate_dict[t0]
                r1 = daily_rate_dict[t1]
                w = (T - t0) / (t1 - t0)
                return (1 - w) * r0 + w * r1
        return daily_rate_dict[tenors[-1]]

    
    def _build_rate_curve(self, eval_date: Union[pd.Timestamp,str])-> ql.ZeroCurve:
        """
        构建 QuantLib 零息利率曲线。
        以给定的评估日为参考日，将离散期限点转化为 QuantLib 日期。
        """
        daily_rate_dict = self._get_daily_rate_dict(eval_date)
        today = self._to_ql_date(eval_date)
        dates = [today]          # 插入今天，使参考日正确
        rates = [float(daily_rate_dict[min(daily_rate_dict.keys())])]  # 用最短期限利率作为今日即期
        for T, r in sorted(daily_rate_dict.items()):
            mat_date = today + ql.Period(max(1, int(round(float(T) * 365))), ql.Days)
            dates.append(mat_date)
            rates.append(float(r))
        curve = ql.ZeroCurve(
            dates, rates, ql.Actual365Fixed(), ql.China(),
            ql.Linear(), ql.Continuous
        # curve.enableExtrapolation() #到期期限均在数据范围内，不需要外推
        )
        return curve

    def calculate_implied_volatility(self, eval_date: Union[pd.Timestamp,str])-> pd.DataFrame:
        """
        计算指定日期期权的 BS 隐含波动率 (bs_iv) 并返回成功计算出 IV 的数据。
        """
        df = self.get_data_by_date(eval_date)
        if df.empty:
            return df
        spot = self.get_underlying_quote(eval_date)
        eval_date_ql = self._to_ql_date(eval_date)
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = eval_date_ql
            df = df.copy()
            df['bs_iv'] = np.nan
            q = self.get_dividend_yield(eval_date)
            q_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(eval_date_ql, q, ql.Actual365Fixed()))
            r_ts = ql.YieldTermStructureHandle(self._build_rate_curve(eval_date))
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(float(spot)))

            for idx, row in df.iterrows():
                T = float(row['T'])
                r = self.get_risk_free_rate(T, eval_date)
                strike = float(row['strike'])
                option_type = str(row['cp']).upper()
                market_price = float(row['close'])
                if market_price <= 0:
                    continue

                payoff = ql.PlainVanillaPayoff(
                    ql.Option.Call if option_type == 'C' else ql.Option.Put, strike)
                expiry_ts = pd.Timestamp(row['expiry'])
                exercise = ql.EuropeanExercise(
                    ql.Date(expiry_ts.day, expiry_ts.month, expiry_ts.year))
                option = ql.VanillaOption(payoff, exercise)

                constant_vol = ql.BlackConstantVol(
                    eval_date_ql, ql.NullCalendar(), 0.2, ql.Actual365Fixed())
                vol_handle = ql.BlackVolTermStructureHandle(constant_vol)
                process = ql.BlackScholesMertonProcess(
                    spot_handle, q_ts, r_ts, vol_handle)
                try:
                    iv = option.impliedVolatility(
                        market_price, process, 1e-6, 1000, 1e-6, 5.0)
                    df.at[idx, 'bs_iv'] = float(iv)
                except Exception:
                    continue
                
        return df.dropna(subset=['bs_iv']).copy()

    def get_data_by_date(self, eval_date: Union[pd.Timestamp,str]) -> pd.DataFrame:
        """
        根据评估日期返回清洗后的期权数据。
        """
        if self.cleaned_data is None:
            raise ValueError("请先调用 load_and_clean_data")
        target = self._to_timestamp(eval_date)
        day_data = self.cleaned_data[self.cleaned_data['date'] == target].copy()
        return day_data
    
    def get_calibration_data(self, eval_date:Union[pd.Timestamp,str])-> pd.DataFrame:
        """
        返回与校准时完全相同的期权子集（已包含 bs_iv）。
        用于单日定价验证，保证样本一致性。
        """
        # 1. 获取当日所有期权（已含 bs_iv）
        df = self.calculate_implied_volatility(eval_date)
        if df is None or df.empty:
            return df

        # 2. 应用统一的校准过滤条件（与 setup_calibration_helpers 完全一致）
        return filter_calibration_options(df)
