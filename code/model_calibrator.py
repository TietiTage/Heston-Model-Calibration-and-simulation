import QuantLib as ql
import numpy as np
from dataclasses import dataclass
import pandas as pd
from typing import List, Optional, Tuple, Union, Literal
from data_processor import HestonDataProcessor, filter_calibration_options
from datetime import datetime

@dataclass
class HestonParameterSet:
    """Heston 模型参数集合（与 QuantLib 内部参数顺序不同，使用前需映射）。"""
    v0: float
    kappa: float
    theta: float
    sigma: float
    rho: float

from typing import TypedDict

class OptionHelper(TypedDict):
    """校准辅助对象：单期权的元数据与缓存好的 QuantLib 期权对象。"""
    T: float
    strike: float
    cp: Literal['C', 'P']  
    market_price: float
    expiry_date: ql.Date
    ql_option: ql.VanillaOption





class HestonModelCalibrator:
    """针对单日数据进行Heston模型校准（加入数据驱动的弱BS先验）"""

    def __init__(self, 
                 eval_date: Union[ql.Date, str, pd.Timestamp], 
                 option_data: pd.DataFrame, 
                 spot:float, 
                 risk_free_curve: ql.YieldTermStructureHandle, 
                 dividend_curve:ql.YieldTermStructureHandle) -> None:
        """
        Parameters
        ----------
        eval_date : Union[ql.Date, str, pd.Timestamp]
            评估日。
        option_data : pd.DataFrame
            当日期权数据 DataFrame。
        spot : float
            标的资产价格（点）。
        risk_free_curve : ql.YieldTermStructureHandle
            无风险利率曲线（连续复利）。
        dividend_curve : ql.YieldTermStructureHandle
            股息率曲线。

        Attributes
        ----------
        helpers : List[OptionHelper]
            根据 option_data 使用 ql 创建的当日所有可用期权列表。
        model : Optional[ql.HestonModel]
            校准所用数学模型。
        engine : Optional[ql.AnalyticHestonEngine]
            校准数学模型使用的引擎。
        """
        self.eval_date = eval_date
        self.option_data: pd.DataFrame = option_data
        self.spot = float(spot)
        self.risk_free_curve: ql.YieldTermStructureHandle = risk_free_curve
        self.dividend_curve: ql.YieldTermStructureHandle = dividend_curve
        self.helpers:List[OptionHelper] = []
        self.model: Optional[ql.HestonModel] = None
        self.engine: Optional[ql.AnalyticHestonEngine] = None

        # 根据当日市场数据计算 BS 弱先验中心
        self.prior_v0_center: Optional[float] = None
        self.prior_theta_center: Optional[float] = None
        self.prior_skew: Optional[float] = None
        self.prior_convexity: Optional[float] = None
        
        self._compute_bs_priors()

    def _compute_bs_priors(self) -> None:
        """
        利用当日 BS 隐含波动率计算 v0, theta, skew, convexity 的先验中心
        """
        df: pd.DataFrame = self.option_data
        if 'bs_iv' not in df.columns or df['bs_iv'].dropna().empty:
            return

        ivs = df['bs_iv'].dropna().clip(0.05, 1.0)
        if len(ivs) < 5:   # 数据太少，拟合不可靠
            return

        # theta / v0 先验 (已有)
        mean_iv = ivs.mean()
        self.prior_theta_center = mean_iv ** 2

        if 'delta' in df.columns and df['delta'].notna().any():
            atm_idx = int((df['delta'].abs() - 0.5).abs().idxmin())
            atm_iv = df.loc[atm_idx, 'bs_iv']
            # atm_iv = df['bs_iv'].iat[atm_idx]
            if not pd.isna(atm_iv):
                self.prior_v0_center = max(atm_iv, 0.05) ** 2
        if self.prior_v0_center is None:
            self.prior_v0_center = self.prior_theta_center

        # ---------- 新增：微笑斜率与曲率先验 ----------
        try:
            #from scipy.optimize import curve_fit
            from numpy import log, polyfit

            # 取当日所有期权的数据
            valid = df.dropna(subset=['bs_iv', 'strike', 'T'])
            if valid.empty:
                return

            # 避免期限混合，我们只取主力期限（例如 T 最接近中位数的合约）
            median_T = valid['T'].median()
            group = valid[(valid['T'] - median_T).abs() < 0.01]  # 近似同一到期日
            if len(group) < 5:
                group = valid  # 若不够则用全体，虽粗糙但仍具参考

            log_moneyness:np.ndarray = np.log(group['strike'] / self.spot)
            iv:np.ndarray = group['bs_iv'].to_numpy()

            # 二次拟合
            coeffs = np.polyfit(log_moneyness, iv, 2)
            a1 = coeffs[1]  # 线性项系数（斜率）
            a2 = coeffs[2]  # 二次项系数（曲率）

            if np.isfinite(a1) and np.isfinite(a2):
                self.prior_skew = a1      # 典型值 -0.5 ~ -2.0
                self.prior_convexity = a2 # 典型值 1.0 ~ 10.0
            else:
                self.prior_skew = None
                self.prior_convexity = None
        except Exception:
            self.prior_skew = None
            self.prior_convexity = None

    @staticmethod
    def _to_ql_date(value:Union[str,ql.Date, pd.Timestamp]) -> ql.Date:
        """将字符串 / QuantLib 日期 / pandas 时间戳统一转换为 QuantLib Date。"""
        if isinstance(value, ql.Date):
            return value
        ts = pd.Timestamp(value)
        return ql.Date(ts.day, ts.month, ts.year)

    def setup_calibration_helpers(self) -> None:
        """
        构建校准用的期权辅助对象列表（先应用统一的校准过滤条件）。
        """
        self.helpers = []
        eval_date_ql = self._to_ql_date(self.eval_date)
        ql.Settings.instance().evaluationDate = eval_date_ql

        filtered_data = filter_calibration_options(self.option_data)

        for _, row in filtered_data.iterrows():
            expiry = self._to_ql_date(row['expiry'])
            if expiry <= eval_date_ql:
                continue

            T = float(row['T'])
            price = float(row['close'])
            cp_raw = str(row['cp']).upper().strip()
            assert cp_raw in ('C', 'P'), f"Invalid option type: {cp_raw}"
            cp: Literal['C', 'P'] = cp_raw
            payoff = ql.PlainVanillaPayoff(
            ql.Option.Call if str(row['cp']).upper().strip() == 'C' else ql.Option.Put,
            float(row['strike'])
        )
            exercise = ql.EuropeanExercise(self._to_ql_date(row['expiry']))
            option = ql.VanillaOption(payoff, exercise)
            # 将其绑定到当前的 engine（需要在 __init__ 或 calibrate 初期提早初始化 engine）
            if self.engine is not None:
                option.setPricingEngine(self.engine)
            item:OptionHelper = {
            'T': T,
            'strike': float(row['strike']),
            'cp': cp,
            'market_price': price,
            'expiry_date': self._to_ql_date(row['expiry']),
            'ql_option': option  # 缓存构建好的对象
        }
            self.helpers.append(item)
        print()
        print(f"[DEBUG] 原始数据行数: {len(self.option_data)}, 筛选后 helpers: {len(self.helpers)}")
        if len(self.helpers) == 0:
            print("警告: 没有期权通过筛选，请检查过滤条件（T>=0.02, 短期流动性, delta 0.1~0.9, 价格>0, 到期日>评估日）")

    def _price_one_option(self, option_type: Literal["C","P"], strike: float, expiry_date: ql.Date) -> float:
        """使用当前引擎对单只欧式期权定价，非法价格返回 NaN。"""
        try:
            ql.Settings.instance().evaluationDate = self._to_ql_date(self.eval_date)
            payoff = ql.PlainVanillaPayoff(
                ql.Option.Call if option_type == 'C' else ql.Option.Put,
                float(strike)
            )
            exercise = ql.EuropeanExercise(expiry_date)
            option = ql.VanillaOption(payoff, exercise)
            option.setPricingEngine(self.engine)
            price = option.NPV()
            if not np.isfinite(price) or price < -1e-6 or price > 1e5:
                return np.nan
            return float(price)
        except Exception:
            return np.nan
        

    def calibrate(self, initial_params: HestonParameterSet, aggressive: bool = False,
                seed_individual: Optional[np.ndarray] = None, prior_weight: float = 0.5) -> Tuple[HestonParameterSet, ql.HestonModel]:
        """
        两阶段校准，损失函数包含：
        - 价格匹配（RMSE + 0.3*MAPE）
        - 软截断保证梯度连续
        - 极弱 L2 正则
        - 极轻 Feller 软约束
        - 数据驱动的 BS 弱先验
        """
        from scipy.optimize import differential_evolution, minimize

        eval_date_ql = self._to_ql_date(self.eval_date)
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = eval_date_ql
            # 构建初始过程与模型
            process = ql.HestonProcess(
                self.risk_free_curve,
                self.dividend_curve,
                ql.QuoteHandle(ql.SimpleQuote(float(self.spot))),
                float(initial_params.v0),
                float(initial_params.kappa),
                float(initial_params.theta),
                float(initial_params.sigma),
                float(initial_params.rho)
            )
            self.model = ql.HestonModel(process)

            # 低精度引擎（DE阶段）
            engine_low = ql.AnalyticHestonEngine(self.model, 1e-3, 500)
            self.engine = engine_low
            if not self.helpers:
                self.setup_calibration_helpers()
            if len(self.helpers) == 0:
                raise ValueError("没有可用的期权进行校准")

            # 权重计算
            weights = []
            for opt in self.helpers:
                T = max(opt['T'], 1e-6)
                w = self.spot * np.sqrt(T)
                weights.append(w)
            avg_weight = np.mean(weights) if weights else 1.0
            norm_weights = [w / avg_weight for w in weights]

            # 损失超参数
            PRIOR_WEIGHT = prior_weight

            def _loss_function(params: np.ndarray) -> float:
                """损失函数：平滑 Huber 价格误差 + 离群值软屏障 + 适度 Feller 与 L2 正则 + BS 先验"""
                import numpy as np
                import QuantLib as ql

                params = np.asarray(params, dtype=float)
                if not np.all(np.isfinite(params)):
                    return 1e12

                v0, kappa, theta, sigma, rho = map(float, params)

                # ==================== 硬边界 ====================
                if v0 <= 1e-10 or theta <= 1e-10 or sigma <= 1e-10 or kappa <= 1e-10:
                    return 1e12
                if abs(rho) >= 1.0:
                    return 1e12
                # ==================== 更新模型参数 ====================
                arr = ql.Array(5)
                arr[0] = theta     # QuantLib 内部顺序固定为 theta, kappa, sigma, rho, v0
                arr[1] = kappa
                arr[2] = sigma
                arr[3] = rho
                arr[4] = v0
                
                assert self.model is not None, "Model not initialized"
                self.model.setParams(arr)

                # 重建引擎，保证积分刷新
                engine_current = ql.AnalyticHestonEngine(self.model, 1e-3, 500)
                for opt in self.helpers:
                    opt['ql_option'].setPricingEngine(engine_current)

                # ==================== 第一部分：加权伪 Huber 价格误差 ====================
                HUBER_DELTA = 25.0        # 阈值 25 元
                total_huber = 0.0
                valid_count = 0
                for i, opt in enumerate(self.helpers):
                    try:
                        model_val = opt['ql_option'].NPV()
                        market_val = opt['market_price']

                        # 硬拒绝对明显非法的模型价格
                        if not np.isfinite(model_val) or model_val <= 0 or model_val > 5000:
                            return 1e12   # 直接拒绝这组参数

                        diff = model_val - market_val
                        w = norm_weights[i]

                        # 伪 Huber 贡献
                        scaled = diff / HUBER_DELTA
                        huber_val = (HUBER_DELTA ** 2) * (np.sqrt(1.0 + scaled ** 2) - 1.0)

                        # # 轻量离群值软屏障（防止 Huber 线性段无限容忍巨大误差）
                        # rel_err = abs(diff) / max(market_val, 1e-4)
                        # SOFT_BARRIER_THRESHOLD = 5.0   # 相对误差超过 5 倍开始惩罚
                        # SOFT_BARRIER_WEIGHT = 500.0    # 惩罚权重
                        

                        if np.isfinite(huber_val):
                            total_huber += w * huber_val
                            valid_count += 1

                    except Exception:
                        pass

                # 成功率要求：至少一半的期权成功定价
                if valid_count < max(6, len(self.helpers) // 2):
                    return 1e12

                avg_price_loss = total_huber / valid_count

                # ==================== 第二部分：轻度 L2 正则 ====================
                L2_REG = 1e-6        # 极轻，仅防止无意义漂移
                reg_penalty = L2_REG * (v0**2 + kappa**2 + theta**2 + sigma**2 + rho**2)

                # ==================== 第三部分：Feller 软约束====================
                feller_violation = max(0.0, sigma**2 - 2.0 * kappa * theta)
                FELLER_WEIGHT = 10.0
                feller_penalty = FELLER_WEIGHT * abs(feller_violation)

                # ==================== 第四部分：BS 弱先验 ====================
                prior_pen = 0.0
                if self.prior_v0_center is not None:
                    prior_pen += (v0 - self.prior_v0_center) ** 2
                if self.prior_theta_center is not None:
                    prior_pen += (theta - self.prior_theta_center) ** 2

                smile_prior = 0.0
                if hasattr(self, 'prior_skew') and self.prior_skew is not None:
                    smile_prior += (rho - (-self.prior_skew)) ** 2
                if hasattr(self, 'prior_convexity') and self.prior_convexity is not None:
                    target_sigma = min(max(self.prior_convexity * 0.05, 0.01), 2.0)
                    smile_prior += (sigma - target_sigma) ** 2

                prior_pen = PRIOR_WEIGHT * (prior_pen + smile_prior)

                # ==================== 总损失（限制上界防止爆炸） ====================
                total_loss = avg_price_loss + reg_penalty + feller_penalty + prior_pen
                return min(total_loss, 1e10)
            
            # 参数边界
            bounds = [
                (1e-4, 1),      # v0
                (0.1, 50),       # kappa
                (1e-6, 0.4),      # theta
                (1e-4, 2.0),      # sigma
                (-0.65, 0.65)      # rho
            ]

            # 设置 DE 参数
            if aggressive:
                maxiter_de = 500
                popsize_de = 120
                seed_de = 2333
            else:
                maxiter_de = 300
                popsize_de = 70
                seed_de = 114514

            # 构造初始种群
            if seed_individual is not None:
                seed_ind = np.asarray(seed_individual, dtype=float)
                # 用局部随机生成器保证可重复
                rng = np.random.default_rng(seed_de)
                random_pop = rng.uniform(
                    low=[b[0] for b in bounds],
                    high=[b[1] for b in bounds],
                    size=(popsize_de - 1, len(bounds))
                )
                init_pop = np.vstack([random_pop, seed_ind])
                de_init = init_pop
                # 此时 popsize 参数被 init 覆盖，但仍可传递，不影响
                actual_popsize = popsize_de
            else:
                de_init = 'latinhypercube'
                actual_popsize = popsize_de

            print(f"全局优化开始，期权数量: {len(self.helpers)}")
            de_result = differential_evolution(
                _loss_function,
                bounds,
                maxiter=maxiter_de,
                popsize=actual_popsize,   
                rng=seed_de,
                disp=False,
                workers=1,
                mutation=(0.75, 1.2),
                recombination=0.75,
                polish=False,
                init=de_init              
            )

            if not de_result.success:
                print(f"差分进化警告: {de_result.message}")

            # 切换为高精度引擎给局部优化
            engine_high = ql.AnalyticHestonEngine(self.model, 1e-7, 10000)
            self.engine = engine_high
            for opt in self.helpers:
                opt['ql_option'].setPricingEngine(self.engine)

            local_result = minimize(
                _loss_function,
                de_result.x,
                method='L-BFGS-B',
                bounds=bounds,
                options={
                    'maxiter': 700,
                    'ftol': 1e-6,
                    'gtol': 1e-5,
                    'eps': 1e-5,
                    'maxls': 30
                }
            )
            if not local_result.success:
                print(f"局部优化警告: {local_result.message}")

            final_params = local_result.x
            v0, kappa, theta, sigma, rho = map(float, final_params)
            arr = ql.Array(5)
            arr[0] = theta    # arguments_[0] = theta
            arr[1] = kappa    # arguments_[1] = kappa
            arr[2] = sigma    # arguments_[2] = sigma
            arr[3] = rho      # arguments_[3] = rho
            arr[4] = v0       # arguments_[4] = v0
            self.model.setParams(arr)
        
            calibrated = HestonParameterSet(
                v0=float(final_params[0]),
                kappa=float(final_params[1]),
                theta=float(final_params[2]),
                sigma=float(final_params[3]),
                rho=float(final_params[4])
            )
            process = ql.HestonProcess(
                self.risk_free_curve,
                self.dividend_curve,
                ql.QuoteHandle(ql.SimpleQuote(float(self.spot))),
                v0, kappa, theta, sigma, rho)
            self.model = ql.HestonModel(process)
            # 最终高精度引擎（用于后续 calculate_calibration_error）
            self.engine = ql.AnalyticHestonEngine(self.model, 1e-7, 10000)
            for opt in self.helpers:
                opt['ql_option'].setPricingEngine(self.engine)
        return calibrated, self.model

    def calculate_calibration_error(self) -> Tuple[float, float]:
        """
        计算校准后的模型在各期权上的价格RMSE和MAE
        """
        if self.model is None:
            raise ValueError("请先调用 calibrate()")
        if not self.helpers:
            raise ValueError("请先调用 setup_calibration_helpers()")
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = self._to_ql_date(self.eval_date)

            model_prices = []
            market_prices = []

            for opt in self.helpers:
                try:
                    mp = float(opt['market_price'])
                    modp = self._price_one_option(opt['cp'], opt['strike'], opt['expiry_date'])

                    if np.isfinite(mp) and np.isfinite(modp):
                        market_prices.append(mp)
                        model_prices.append(modp)
                except Exception:
                    continue

            if len(model_prices) == 0:
                return np.inf, np.inf

            market_prices = np.array(market_prices, dtype=float)
            model_prices = np.array(model_prices, dtype=float)

            rmse = np.sqrt(np.mean((market_prices - model_prices) ** 2))
            mae = np.mean(np.abs(market_prices - model_prices))
            if not np.isfinite(rmse) or rmse > 1e6:
                return np.inf, np.inf
        return rmse, mae


def run_daily_calibration(
    processor: 'HestonDataProcessor',
    start_date: Union[str, pd.Timestamp, datetime],
    end_date: Union[str, pd.Timestamp, datetime],
    initial_params: HestonParameterSet,
    calibration_options_csv: Optional[str] = 'calibration_options.csv'
) -> pd.DataFrame:
    """
    高层函数：遍历日期范围，每天校准并返回参数 DataFrame。

    Parameters
    ----------
    processor : HestonDataProcessor
        HestonDataProcessor 实例，已经调用过 load_and_clean_data。
    start_date : Union[str, pd.Timestamp, datetime]
        起始日期。
    end_date : Union[str, pd.Timestamp, datetime]
        结束日期。
    initial_params : HestonParameterSet
        初始参数。
    calibration_options_csv : Optional[str]
        保存每日校准所用期权数据的 CSV 路径（若为 None 则不保存）。

    Returns
    -------
    pd.DataFrame
        每天校准得到的参数 DataFrame。
    """
    results = []
    all_filtered = []  # 用来存所有日期的过滤后期权数据
    date_range = pd.date_range(start_date, end_date, freq='D')

    current_initial = initial_params

    for dt in date_range:
        with ql.SavedSettings():
            ql.Settings.instance().evaluationDate = ql.Date(dt.day, dt.month, dt.year)
            restart_flag = False
            day_data = processor.calculate_implied_volatility(dt)

            if day_data.empty:
                continue

            # 先过滤，得到与校准时完全相同的期权集合
            filtered_data = filter_calibration_options(day_data)
            if filtered_data.empty:
                continue

            try:
                spot = processor.get_underlying_quote(dt)
                r_curve = processor._build_rate_curve(dt)
                q = processor.get_dividend_yield(dt)
                q_curve = ql.YieldTermStructureHandle(
                    ql.FlatForward(ql.Date(dt.day, dt.month, dt.year), q, ql.Actual365Fixed())
                )

                seed_ind = np.array([
                    current_initial.v0,
                    current_initial.kappa,
                    current_initial.theta,
                    current_initial.sigma,
                    current_initial.rho
                ])

                calibrator = HestonModelCalibrator(
                    dt, filtered_data, spot,
                    ql.YieldTermStructureHandle(r_curve), q_curve
                )
                calibrator.setup_calibration_helpers()
                calib_params, _ = calibrator.calibrate(
                    current_initial,
                    seed_individual=seed_ind
                )
                rmse, mae = calibrator.calculate_calibration_error()

                # 初始化最佳结果
                best_rmse = rmse
                best_mae = mae
                best_params = calib_params

                # ----- 分层恢复策略（保持不变）-----
                if rmse > 20 or not np.isfinite(rmse):
                    if not restart_flag:
                        print(f"RMSE={rmse:.2f}，mae={mae:.2f},尝试 BS 先验引导优化")
                        bs_fallback = initial_params
                        if (calibrator.prior_v0_center is not None and 
                            calibrator.prior_theta_center is not None):
                            bs_v0 = max(1e-4, calibrator.prior_v0_center)
                            bs_theta = max(1e-4, calibrator.prior_theta_center)
                            bs_kappa = 2.0
                            bs_sigma = 0.2
                            bs_rho = -0.01
                            if calibrator.prior_skew is not None and np.isfinite(calibrator.prior_skew):
                                bs_rho = max(-0.95, min(0.1, -calibrator.prior_skew))
                            if calibrator.prior_convexity is not None and np.isfinite(calibrator.prior_convexity):
                                bs_sigma = min(2.0, max(0.01, calibrator.prior_convexity * 0.05))
                            bs_fallback = HestonParameterSet(bs_v0, bs_kappa, bs_theta, bs_sigma, bs_rho)
                            print(f"BS 先验种子: v0={bs_v0:.4f}, theta={bs_theta:.4f}, rho={bs_rho:.4f}, sigma={bs_sigma:.4f}")
                        else:
                            print("无 BS 先验信息，仍用 initial_params")

                        bs_seed = np.array([
                            bs_fallback.v0, bs_fallback.kappa,
                            bs_fallback.theta, bs_fallback.sigma, bs_fallback.rho
                        ])
                        calib_params, _ = calibrator.calibrate(
                            bs_fallback,
                            seed_individual=bs_seed,
                            prior_weight = 0.3
                        )
                        rmse, mae = calibrator.calculate_calibration_error()
                        # 更新最佳结果
                        if np.isfinite(rmse) and rmse < best_rmse:
                            best_rmse = rmse
                            best_mae = mae
                            best_params = calib_params
                        restart_flag = True
                        
                    if rmse > 20 or not np.isfinite(rmse):
                        print(f"RMSE={rmse:.2f}，mae={mae:.2f},尝试增强搜索（aggressive + 新种子）")
                        calib_params, _ = calibrator.calibrate(
                            current_initial,
                            aggressive=True,
                            seed_individual=seed_ind,
                            prior_weight = 0.1) 
            
                        rmse, mae = calibrator.calculate_calibration_error()
                        # 更新最佳结果
                        if np.isfinite(rmse) and rmse < best_rmse:
                            best_rmse = rmse
                            best_mae = mae
                            best_params = calib_params
                        restart_flag = True

                    # 最终使用最佳结果来决定状态，并记录最佳参数
                    if best_rmse > 25 or not np.isfinite(best_rmse):
                        status = 'failed'
                        print(f"所有重试后最佳 RMSE 仍 > 25 或 inf，标记为失败")
                        # 失败后设置下一天初始参数
                        if (hasattr(calibrator, 'prior_v0_center') 
                            and calibrator.prior_v0_center is not None):
                            bs_v0   = max(1e-4, calibrator.prior_v0_center)
                            bs_theta = max(1e-4, calibrator.prior_theta_center) if calibrator.prior_theta_center else bs_v0
                            bs_kappa = 2.0
                            bs_sigma = 0.3
                            bs_rho   = -0.5
                            if hasattr(calibrator, 'prior_skew') and calibrator.prior_skew is not None:
                                bs_rho = max(-0.95, min(0.1, -calibrator.prior_skew))
                            if hasattr(calibrator, 'prior_convexity') and calibrator.prior_convexity is not None:
                                bs_sigma = min(2.0, max(0.01, calibrator.prior_convexity * 0.05))
                            current_initial = HestonParameterSet(bs_v0, bs_kappa, bs_theta, bs_sigma, bs_rho)
                            print(f"使用当日 BS 先验作为下一天初始: v0={bs_v0:.4f}, theta={bs_theta:.4f}, rho={bs_rho:.4f}, sigma={bs_sigma:.4f}")
                        else:
                            current_initial = initial_params
                    else:
                        status = 'ok'
                        current_initial = best_params
                else:
                    status = 'ok'
                    current_initial = calib_params

                rmse, mae = best_rmse, best_mae
                calib_params = best_params
                # ----- 记录最佳校准参数 -----
                results.append({
                    'date': pd.Timestamp(dt).normalize(),
                    'v0': best_params.v0,
                    'kappa': best_params.kappa,
                    'theta': best_params.theta,
                    'sigma': best_params.sigma,
                    'rho': best_params.rho,
                    'rmse': best_rmse,
                    'mae': best_mae,
                    'status': status
                })
                # ----- 收集当日的过滤后期权数据（附带 date 列，用于保存）-----
                filtered_data = filtered_data.copy()
                filtered_data['date'] = pd.Timestamp(dt).normalize()
                all_filtered.append(filtered_data)

                print(f"校准完成 {dt}: RMSE={rmse:.4f}, MAE={mae:.4f}, 状态={status}")

            except Exception as e:
                print(f"校准异常 {dt}: {e}")
                continue

    # 保存校准参数 DataFrame
    params_df = pd.DataFrame(results)

    # 保存校准所用期权数据到 CSV（如果提供了路径）
    if calibration_options_csv and all_filtered:
        options_df = pd.concat(all_filtered, ignore_index=True)
        # 确保保存时包含 bs_iv 等全部列
        options_df.to_csv(calibration_options_csv, index=False, encoding='gbk')
        print(f"校准期权数据已保存至: {calibration_options_csv}")

    return params_df
