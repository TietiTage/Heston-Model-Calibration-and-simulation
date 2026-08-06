import QuantLib as ql
import pandas as pd
import numpy as np
from QuantLib import FdmHestonSolver, FdmSchemeDesc
from typing import List, Literal, Optional, Dict, Any, Union
from model_calibrator import HestonParameterSet
from data_processor import HestonDataProcessor
from typing import TypedDict
from datetime import datetime

class OptionSpec(TypedDict):
    """目标期权规格：行权价、类型与到期日。"""
    strike: int
    type: Literal["C","P"]
    expiry: datetime
    
class GreeksRecord(TypedDict):
    """单日希腊字母记录：五个希腊字母 + 评估日 + 标的资产价格。"""
    delta: float
    gamma: float
    theta: float
    rho: float
    vega: float
    date: pd.Timestamp
    spot: float

class HestonGreeksCalculator:
    """基于有限差分引擎（FdHestonVanillaEngine）的 Heston 希腊字母计算器。"""
    def __init__(self, params: HestonParameterSet, 
                 spot:float, 
                 risk_free_curve:ql.YieldTermStructureHandle, 
                 dividend_curve:ql.YieldTermStructureHandle, 
                 eval_date: Union[str, ql.Date, pd.Timestamp, datetime]) -> None:
        """
        参数
        ----------
        params : HestonParameterSet
            校准后的 Heston 参数。
        spot : float
            标的资产现货价格。
        risk_free_curve : ql.YieldTermStructureHandle
            无风险利率曲线。
        dividend_curve : ql.YieldTermStructureHandle
            股息率曲线。
        eval_date : 可转换为 ql.Date 时间字符串
            评估日期。
        """
        self.params = params
        self.spot = spot
        self.spot_quote = ql.SimpleQuote(float(spot))
        self.spot_handle = ql.QuoteHandle(self.spot_quote)
        self.risk_free_curve: ql.YieldTermStructureHandle = risk_free_curve
        self.dividend_curve: ql.YieldTermStructureHandle = dividend_curve
        self.eval_date: ql.Date = self._to_ql_date(eval_date)
        # 初始化对象时，设置引擎
        self._setup_engine()

    @staticmethod
    def _to_ql_date(value:Union[str, ql.Date, pd.Timestamp, datetime]) -> ql.Date:
        """将输入转换为 QuantLib Date 对象。"""
        if isinstance(value, ql.Date):
            return value
        ts = pd.Timestamp(value)
        return ql.Date(ts.day, ts.month, ts.year)

    def _setup_engine(self) -> None:
        """基于当前参数构建 Heston 模型并创建有限差分引擎。"""
        process = ql.HestonProcess(
            self.risk_free_curve,
            self.dividend_curve,
            self.spot_handle,
            self.params.v0,
            self.params.kappa,
            self.params.theta,
            self.params.sigma,
            self.params.rho
        )
        self.model = ql.HestonModel(process)
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = self.eval_date
            self.engine = ql.FdHestonVanillaEngine(
                            self.model)

    def update_spot(self, new_spot: float) -> None:
        """更新标的价格。"""
        self.spot_quote.setValue(float(new_spot))

    def get_greeks(self, 
                   option_type:Literal["C","P"], 
                   strike:float, 
                   expiry_date:Union[str,pd.Timestamp, ql.Date],
                   spot_override:Optional[float]=None) -> Dict[str, float]:
        """
        计算指定期权的希腊字母。
        返回字典包含 'delta', 'gamma', 'theta', 'rho', 'vega'（市场惯例 Vega）。
        """
        original_spot = self.spot_quote.value()
        if spot_override is not None:
            self.update_spot(spot_override)
        try:
            # 构建欧式期权
            payoff = ql.PlainVanillaPayoff(
                ql.Option.Call if option_type == 'C' else ql.Option.Put,
                float(strike)
            )
            exercise = ql.EuropeanExercise(self._to_ql_date(expiry_date))
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(self.engine)
            # Greeks
            delta = option.delta()
            gamma = option.gamma()
            theta = option.theta()
            rho = self._compute_rho(option_type, strike, expiry_date, spot_override)
            vega_v0 = self._compute_vega(option_type, strike, expiry_date, spot_override)

            # 转换为市场标准 Vega (∂Price/∂σ)
            sigma0 = np.sqrt(max(self.params.v0, 0.0))
            if sigma0 > 1e-10:
                vega_standard = 2.0 * sigma0 * vega_v0
            else:
                vega_standard = 0.0
            return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'rho': rho,
            'vega': vega_standard,  # 市场惯例 Vega
            # 'vega_v0': vega_v0  # 对初始方差的敏感度，供调试
        }
        finally:
            if spot_override is not None:
                self.update_spot(original_spot)

        
        
            
    def _compute_rho(self,
                     option_type: Literal["C","P"], 
                     strike:float, 
                     expiry_date: Union[str, pd.Timestamp, ql.Date], 
                     spot_override: Optional[float]=None) -> float:
        """通过扰动利率曲线计算 Rho（利率变化 1% 导致的价格变动）
        bump 0.01.
        """
        base_price = self._price_with_current_params(option_type, strike, expiry_date, spot_override)
        bump = 0.01  # 1%
        spot = self.spot_quote.value()
        # 基准曲线
        base_curve = self.risk_free_curve.currentLink()  # 获取底层曲线对象（可能需要解引用）
        # 创建一个恒定的利差曲线（bump = 0.01 的连续复利）
        spread_quote = ql.SimpleQuote(bump)
        spread_handle = ql.QuoteHandle(spread_quote)
        spread_curve = ql.FlatForward(self.eval_date, spread_handle, ql.Actual365Fixed())
        bumped_curve = ql.ZeroSpreadedTermStructure(
        ql.YieldTermStructureHandle(base_curve),
        spread_handle
        )
        # 用 bumped_curve 构建临时计算器
        temp_calc = HestonGreeksCalculator(
            self.params,
            spot,
            ql.YieldTermStructureHandle(bumped_curve),  # 传入新的曲线句柄
            self.dividend_curve,
            self.eval_date
        )
        bumped_price = temp_calc._price_with_current_params(option_type, strike, expiry_date)
        rho = (bumped_price - base_price)
        return float(rho)


    def _compute_vega(self, 
                      option_type: Literal["C","P"], 
                      strike: float, 
                      expiry_date: Union[str, pd.Timestamp, ql.Date],
                      spot_override: Optional[float]=None) -> float:
        """通过扰动初始方差 v0 计算 Vega（严格说是对 v0 的敏感度）"""
        base_price = self._price_with_current_params(option_type, strike, expiry_date, spot_override)
        bump = max(1e-4, 0.01 * max(self.params.v0, 1e-4))

        bumped_params = HestonParameterSet(
            v0=self.params.v0 + bump,
            kappa=self.params.kappa,
            theta=self.params.theta,
            sigma=self.params.sigma,
            rho=self.params.rho
        )
        bumped_price = self._price_with_given_params(
            bumped_params, option_type, strike, expiry_date, spot_override
        )
        vega = (bumped_price - base_price) / bump
        return float(vega)

    def _price_with_current_params(self, 
                                   option_type: Literal["C","P"], 
                                   strike: float, 
                                   expiry_date :Union[str, pd.Timestamp, ql.Date], 
                                   spot_override: Optional[float]=None)->float:
        """使用当前引擎和参数计算期权价格"""
        ql.Settings.instance().evaluationDate = self.eval_date
        original_spot = self.spot_quote.value()

        if spot_override is not None:
            self.update_spot(spot_override)

        payoff = ql.PlainVanillaPayoff(
            ql.Option.Call if option_type == 'C' else ql.Option.Put,
            float(strike)
        )
        exercise = ql.EuropeanExercise(self._to_ql_date(expiry_date))
        option = ql.VanillaOption(payoff, exercise)
        option.setPricingEngine(self.engine)
        price = float(option.NPV())

        if spot_override is not None:
            self.update_spot(original_spot)

        return price

    def _price_with_given_params(self, 
                                 params:HestonParameterSet, 
                                 option_type: Literal["C","P"], 
                                 strike: float, 
                                 expiry_date:Union[str, pd.Timestamp, ql.Date],
                                 spot_override:Optional[float]=None)->float:
        """使用指定参数临时构建计算器并返回价格"""
        spot = self.spot_quote.value() if spot_override is None else float(spot_override)
        temp_calc = HestonGreeksCalculator(
            params,
            spot,
            self.risk_free_curve,
            self.dividend_curve,
            self.eval_date
        )
        price = temp_calc._price_with_current_params(option_type, strike, expiry_date, spot_override)
        return float(price)


def analyze_greeks_dynamics(processor:HestonDataProcessor, 
                            params_df:pd.DataFrame, 
                            target_option_spec:OptionSpec, 
                            eval_dates:List[Union[str, pd.Timestamp, datetime]]
                            ) -> pd.DataFrame:
    """
    参数:
        processor: HestonDataProcessor实例
        params_df: run_daily_calibration返回的DataFrame，包含每天校准的参数
        target_option_spec: dict，如 {'strike': 3900, 'type': 'C', 'expiry': datetime(2025,6,20)}
        eval_dates: 要分析的日期列表（datetime）
    返回:
        greeks_df: DataFrame，每天对应的希腊字母值
    """
    greeks_list = []

    for dt in eval_dates:
        dt_norm: pd.Timestamp = pd.Timestamp(dt).normalize()
        date_series = pd.to_datetime(params_df['date']).dt.normalize()
        row = params_df[date_series == dt_norm]
        if row.empty:
            continue
        with ql.SavedSettings():
            eval_date_ql = ql.Date(dt_norm.day, dt_norm.month, dt_norm.year)
            expiry = pd.Timestamp(target_option_spec['expiry'])
            expiry_ql = ql.Date(expiry.day, expiry.month, expiry.year)
            ql.Settings.instance().evaluationDate = eval_date_ql
            params = HestonParameterSet(
                v0=float(row['v0'].values[0]),
                kappa=float(row['kappa'].values[0]),
                theta=float(row['theta'].values[0]),
                sigma=float(row['sigma'].values[0]),
                rho=float(row['rho'].values[0])
            )
            spot = processor.get_underlying_quote(dt)
            

            r_curve = processor._build_rate_curve(dt_norm)
            q = processor.get_dividend_yield(dt_norm)
            q_curve = ql.YieldTermStructureHandle(
                ql.FlatForward(eval_date_ql, q, ql.Actual365Fixed())
            )
            try:
                calculator = HestonGreeksCalculator(
                    params, spot,
                    ql.YieldTermStructureHandle(r_curve),
                    q_curve,
                    eval_date=eval_date_ql
                )
                greeks = calculator.get_greeks(
                    option_type=target_option_spec['type'],
                    strike=target_option_spec['strike'],
                    expiry_date=expiry_ql
                )
                record: GreeksRecord = {
                    'delta': greeks['delta'],
                    'gamma': greeks['gamma'],
                    'theta': greeks['theta'],
                    'rho': greeks['rho'],
                    'vega': greeks['vega'],
                    'date': dt_norm,
                    'spot': spot,
                }
                greeks_list.append(record)
            except Exception as e:
                print(f"{dt_norm.strftime('%Y-%m-%d')} Greeks失败: {type(e).__name__}: {e}", flush=True)
            
            
    return pd.DataFrame(greeks_list)
