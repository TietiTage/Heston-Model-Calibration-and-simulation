import QuantLib as ql
import numpy as np
import pandas as pd
from model_calibrator import HestonParameterSet
from typing import Union, Dict, Literal, Optional, List, Tuple
from datetime import datetime
from data_processor import HestonDataProcessor

class HestonModelPricer:
    """
    基于半解析法的 Heston 定价器
    """
    def __init__(self, 
                 params: HestonParameterSet, 
                 spot: float, 
                 risk_free_curve: ql.YieldTermStructureHandle, 
                 dividend_curve: ql.YieldTermStructureHandle) -> None:
        """初始化半解析 Heston 定价器。"""
        self.params: HestonParameterSet = params
        self.spot: float = spot
        self.risk_free_curve: ql.YieldTermStructureHandle = risk_free_curve
        self.dividend_curve: ql.YieldTermStructureHandle = dividend_curve

    @staticmethod
    def _to_ql_date(value: Union[str, pd.Timestamp, ql.Date, datetime]) -> ql.Date:
        """将字符串 / pandas 时间戳 / QuantLib 日期统一转换为 QuantLib Date。"""
        if isinstance(value, ql.Date):
            return value
        ts = pd.Timestamp(value)
        return ql.Date(ts.day, ts.month, ts.year)

    def _build_engine(self, eval_date:Union[str, pd.Timestamp, datetime, ql.Date]) -> ql.AnalyticHestonEngine:
        """以给定评估日构建 Heston 模型的高精度半解析引擎（relTol=1e-7, maxEval=10000）。"""
        eval_date_ql: ql.Date = self._to_ql_date(eval_date)
        with ql.SavedSettings():
            process = ql.HestonProcess(
                self.risk_free_curve,
                self.dividend_curve,
                ql.QuoteHandle(ql.SimpleQuote(float(self.spot))),
                self.params.v0,
                self.params.kappa,
                self.params.theta,
                self.params.sigma,
                self.params.rho
            )
            model = ql.HestonModel(process)
            engine = ql.AnalyticHestonEngine(model, 1e-7, 10000)
        return engine
        
            

    def price(self, option_type:Literal["C","P"], 
              strike:float, 
              expiry_date:Union[str, pd.Timestamp, datetime, ql.Date], 
              eval_date:Union[str, pd.Timestamp, datetime, ql.Date]) -> float:
        """返回指定欧式期权的 Heston 半解析价格。"""
        eval_d: ql.Date = self._to_ql_date(eval_date)
        with ql.SavedSettings():
            engine = self._build_engine(eval_date)
            payoff = ql.PlainVanillaPayoff(
                ql.Option.Call if option_type == 'C' else ql.Option.Put,
                float(strike)
            )
            exercise = ql.EuropeanExercise(self._to_ql_date(expiry_date))
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(engine)
            return float(option.NPV())
       


# def _generate_heston_paths_numba(S0, v0, kappa, theta, sigma, rho, r, q, dt, n_steps, n_paths, antithetic=True):
#     """独立函数，生成到期价格（全截断 Euler + 对偶路径）"""
#     sqrt_dt = np.sqrt(dt)

#     Z = np.random.normal(0, 1, size=(n_paths, n_steps, 2))
#     if antithetic:
#         Z = np.concatenate([Z, -Z], axis=0)

#     Z1 = Z[:, :, 0]
#     Z2 = rho * Z[:, :, 0] + np.sqrt(max(0.0, 1 - rho ** 2)) * Z[:, :, 1]

#     S = np.zeros((Z.shape[0], n_steps + 1))
#     v = np.zeros_like(S)
#     S[:, 0] = S0
#     v[:, 0] = v0

#     for i in range(n_steps):
#         v_pos = np.maximum(v[:, i], 0.0)

#         v_drift = v_pos + kappa * (theta - v_pos) * dt
#         v[:, i + 1] = v_drift + sigma * np.sqrt(v_pos) * sqrt_dt * Z2[:, i]
#         v[:, i + 1] = np.maximum(v[:, i + 1], 0.0)
#         S[:, i + 1] = S[:, i] * np.exp(
#             (r - q - 0.5 * v_pos) * dt + np.sqrt(v_pos) * sqrt_dt * Z1[:, i]
#         )
#     return S[:, -1]


class HestonMonteCarloPricer:
    """基于全截断 Euler 离散的 Heston 蒙特卡洛定价器，支持对偶变量。"""
    def __init__(self,
             params: HestonParameterSet,
             spot: float,
             risk_free_ts: ql.YieldTermStructureHandle,
             dividend_ts: ql.YieldTermStructureHandle,
             eval_date: Union[str, pd.Timestamp, ql.Date],
             expiry_date: Union[str, pd.Timestamp, ql.Date],
             n_steps: int = 252,
             n_paths: int = int(1e7),
             antithetic: bool = True,
             seed: int = 42) -> None:
        """初始化蒙特卡洛定价器：固定评估日、到期日、路径数与随机种子。"""
        
        self.params: HestonParameterSet = params
        self.spot = float(spot)
        self.risk_free_ts = risk_free_ts
        self.dividend_ts = dividend_ts
        self.n_steps: int = max(1, int(n_steps))
        self.n_paths: int = max(1, int(n_paths))
        self.antithetic: bool = antithetic
        self.seed: int = seed
        self.eval_date = self._to_ql_date(eval_date)
        self.expiry = self._to_ql_date(expiry_date)

    @staticmethod
    def _to_ql_date(value: Union[str, pd.Timestamp, ql.Date]) -> ql.Date:
        """将字符串 / pandas 时间戳 / QuantLib 日期统一转换为 QuantLib Date。"""
        if isinstance(value, ql.Date):
            return value
        ts = pd.Timestamp(value)
        return ql.Date(ts.day, ts.month, ts.year)

    def _build_engine(self) -> ql.MCEuropeanHestonEngine:
        """构建全截断 Euler MC 引擎（PseudoRandom + 对偶变量 + requiredSamples）。"""
        # 直接使用传入的曲线句柄，不再自己构建 FlatForward
        r_ts = self.risk_free_ts
        q_ts = self.dividend_ts
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(self.spot))

        process = ql.HestonProcess(
            r_ts, q_ts, spot_handle,
            self.params.v0,
            self.params.kappa,
            self.params.theta,
            self.params.sigma,
            self.params.rho,
            # ql.HestonProcess.QuadraticExponential #QE更先进，极端参数下可能不稳定。
            #全截断Euler
            ql.HestonProcess.FullTruncation
        )

       
        engine = ql.MCEuropeanHestonEngine(
            process,
            'PseudoRandom',
            timeStepsPerYear=self.n_steps,                 
            antitheticVariate=self.antithetic,
            requiredSamples=self.n_paths,                     
            requiredTolerance=0.15,
            maxSamples=self.n_paths,               
            seed=self.seed
        )
        return engine


    def price(self, strike: float, option_type: str = 'C') -> float:
        """
        返回 (价格)
        """
        engine = self._build_engine()

        payoff = ql.PlainVanillaPayoff(
            ql.Option.Call if option_type.upper() == 'C' else ql.Option.Put,
            float(strike)
        )
        exercise = ql.EuropeanExercise(self.expiry)
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = self.eval_date
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(engine)
        # 确保使用正确的评估日期（固定参考日），避免干扰全局设置
            npv = option.NPV()
            return float(npv)
        
    

    def price_with_error(self, strike: float, option_type: str = 'C') -> Tuple[float, float]:
        """
        返回 (价格, 蒙特卡洛标准误)
        标准误 = engine.errorEstimate()
        """
        engine = self._build_engine()

        payoff = ql.PlainVanillaPayoff(
            ql.Option.Call if option_type.upper() == 'C' else ql.Option.Put,
            float(strike)
        )
        exercise = ql.EuropeanExercise(self.expiry)
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = self.eval_date
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(engine)
            npv = option.NPV()
            error = option.errorEstimate()    # MC SE
            return float(npv), float(error)
        
            
class BlackScholesPricer:
    """Black-Scholes公式定价器"""
    @staticmethod
    def price(spot: float, strike: float, r: float, q: float, T: float,
              sigma: float, option_type: str = 'C') -> float:
        """BS 闭式定价：输入标的价格、行权价、无风险利率、股息率、期限与波动率；T<=0 或 sigma<=0 时返回内在价值。"""
        from scipy.stats import norm

        spot = float(spot)
        strike = float(strike)
        r = float(r)
        q = float(q)
        T = float(T)
        sigma = float(sigma)

        if T <= 0 or sigma <= 0:
            intrinsic = max(0.0, spot - strike) if option_type == 'C' else max(0.0, strike - spot)
            return float(intrinsic)

        d1 = (np.log(spot / strike) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'C':
            price = spot * np.exp(-q * T) * norm.cdf(d1) - strike * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = strike * np.exp(-r * T) * norm.cdf(-d2) - spot * np.exp(-q * T) * norm.cdf(-d1)

        return float(price)


def compare_pricing_on_date(eval_date: Union[str, pd.Timestamp, datetime],
                            processor: HestonDataProcessor,
                            calibrated_params: HestonParameterSet,
                            calibration_csv: str = 'calibration_options.csv') -> Optional[pd.DataFrame]:
    """
    对指定评估日进行多模型定价验证。

    Parameters
    ----------
    eval_date : Union[str, pd.Timestamp, datetime]
        评估日。
    processor : HestonDataProcessor
        已清洗数据的处理器，用于取当日期权与市场环境。
    calibrated_params : HestonParameterSet
        当日校准得到的 Heston 参数。
    calibration_csv : str
        校准期权 CSV 路径（保留参数，用于样本一致性说明）。

    Returns
    ----------
    Optional[pd.DataFrame]
        列 = strike, type, T, market, BlackScholes, BS_const, Heston_analytic, Heston_MC；
        当日无数据时返回 None。
    """
    print(f"\n===== 定价验证 (基于保存的校准期权数据) =====")
    print(f"评估日: {eval_date}")
    print(f"校准参数: v0={calibrated_params.v0:.6f}, kappa={calibrated_params.kappa:.4f}, "
          f"theta={calibrated_params.theta:.6f}, sigma={calibrated_params.sigma:.4f}, "
          f"rho={calibrated_params.rho:.4f}")
    day_data = processor.get_calibration_data(eval_date)
    if day_data.empty:
        print(f"{eval_date} 无对应校准期权数据")
        return None
    print(f"载入当日校准期权数量: {len(day_data)}")

    # 2. 获取市场环境数据（依旧从 processor 动态获取，确保一致）
    spot = processor.get_underlying_quote(eval_date)
    print(f"标的资产价格: {spot}")
    q = processor.get_dividend_yield(eval_date)
    eval_date_ql = ql.Date(eval_date.day, eval_date.month, eval_date.year)
    with ql.SavedSettings():
        ql.Settings.instance().evaluationDate = eval_date_ql
    
        r_curve = processor._build_rate_curve(eval_date)
        q_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date_ql, q, ql.Actual365Fixed())
        )

        # 3. 计算 BS‑Const 固定波动率（平值 IV）
        sigma_const = None
        if 'delta' in day_data.columns and day_data['delta'].notna().any():
            atm_idx = (day_data['delta'].abs() - 0.5).abs().idxmin()
            atm_row = day_data.loc[atm_idx]
            if 'bs_iv' in atm_row and pd.notna(atm_row['bs_iv']):
                sigma_const = float(atm_row['bs_iv'])
        if sigma_const is None:
            valid_ivs = day_data['bs_iv'].dropna()
            if not valid_ivs.empty:
                sigma_const = float(valid_ivs.median())
        if sigma_const is None or sigma_const <= 0:
            print("警告：无法确定平值隐含波动率，使用 v0 平方根替代")
            sigma_const = float(np.sqrt(max(calibrated_params.v0, 1e-8)))
        print(f"BS‑Const 固定波动率: {sigma_const:.4f}")

        # 4. 构建 Heston 定价器（使用高精度引擎，与校准最终阶段一致）
        heston_pricer = HestonModelPricer(
            calibrated_params,
            spot,
            ql.YieldTermStructureHandle(r_curve),
            q_curve
        )
        i = 0
        results = []
        day_counter = ql.Actual365Fixed()
        for _, row in day_data.iterrows():
            strike = float(row['strike'])
            opt_type_raw = str(row['cp']).upper()
            assert opt_type_raw in ('C', 'P'), f"期权类型必须是 'C' 或 'P'，但得到 {opt_type_raw.__class__}"
            opt_type:Literal["C","P"] = opt_type_raw
            market_price = float(row['close'])
            expiry_ts = pd.Timestamp(row['expiry'])
            expiry_date = ql.Date(expiry_ts.day, expiry_ts.month, expiry_ts.year)
            T = day_counter.yearFraction(eval_date_ql, expiry_date)
            r = processor.get_risk_free_rate(T, eval_date)
            i=i+1
            print(f"[{i}/{len(day_data)}] 正在定价: strike={strike}, type={opt_type}", flush=True)
            # 1) Heston 半解析价格
            heston_analytic_price = heston_pricer.price(opt_type, strike, expiry_date, eval_date)

            # 2) Heston 蒙特卡洛价格
            mc_pricer = HestonMonteCarloPricer(
                calibrated_params,
                spot,
                ql.YieldTermStructureHandle(r_curve),   # 与半解析用同一个利率曲线句柄
                q_curve,                                # 与半解析用同一个股息率曲线句柄
                eval_date=eval_date,           # 真实的评估日
                expiry_date=row['expiry'],     # 真实的到期日
            )
            heston_mc_price = mc_pricer.price(strike, opt_type)

            # BS‑IV
            if 'bs_iv' in row and pd.notna(row['bs_iv']):
                sigma_bs_iv = float(row['bs_iv'])
            else:
                sigma_bs_iv = sigma_const  # 回退到平值
            bs_iv_price = BlackScholesPricer.price(spot, strike, r, q, T, sigma_bs_iv, opt_type)

            # BS‑Const
            bs_const_price = BlackScholesPricer.price(spot, strike, r, q, T, sigma_const, opt_type)

            results.append({
                'strike': strike,
                'type': opt_type,
                'T': T,
                'market': market_price,
                'BlackScholes': bs_iv_price,
                'BS_const': bs_const_price,
                'Heston_analytic': heston_analytic_price,
                'Heston_MC': heston_mc_price,
            })

            print(f"strike={strike}, type={opt_type}, market={market_price:.2f},"
                f"Heston_analytic={heston_analytic_price:.2f}, "
                f"BS_const={bs_const_price:.2f}, "
                f"Heston_MC={heston_mc_price:.2f}")
            F = spot * np.exp((r - q) * T)
            print(f"T={T:.4f}, r={r:.6f}, q={q:.6f}, F={F:.2f}")

        comparison_df = pd.DataFrame(results)

        # 误差总结
        if 'market' in comparison_df.columns:
            mae_bs_iv = (comparison_df['BlackScholes'] - comparison_df['market']).abs().mean()
            mae_bs_const = (comparison_df['BS_const'] - comparison_df['market']).abs().mean()
            mae_heston_analytic = (comparison_df['Heston_analytic'] - comparison_df['market']).abs().mean()
            mae_heston_mc = (comparison_df['Heston_MC'] - comparison_df['market']).abs().mean()

            print(f"\n===== 误差总结 =====")
            print(f"BS‑IV (自身 IV) MAE: {mae_bs_iv:.4f} 点")
            print(f"BS‑Const (平值 IV) MAE: {mae_bs_const:.4f} 点")
            print(f"Heston 半解析 MAE: {mae_heston_analytic:.4f} 点")
            print(f"Heston MC MAE: {mae_heston_mc:.4f} 点")

        return comparison_df
   
