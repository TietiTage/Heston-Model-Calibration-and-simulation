import pandas as pd
import glob
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import QuantLib as ql
from datetime import datetime, timedelta

# 项目根目录 = code/ 的上一级
PROJECT_ROOT = Path(__file__).resolve().parents[1]

def third_friday_of_month(year: int, month: int) -> datetime:
    """
    返回指定年月的IO期权到期日（第三个星期五），
    若当天为交易所假日则提前至前一个交易日。
    """
    # 1. 自然日上的第三个星期五
    first_day = datetime(year, month, 1)
    days_to_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_to_friday)
    third_friday = first_friday + timedelta(days=14)

    # 2. 转换为 QuantLib 日期并调整
    ql_date = ql.Date(third_friday.day, third_friday.month, third_friday.year)

    # 中金所节假日
    calendar = ql.China(ql.China.SSE)
    adjusted = calendar.adjust(ql_date, ql.Preceding)  # 向前移动到最近交易日

    # 3. 转回 datetime 返回
    return datetime(adjusted.year(), adjusted.month(), adjusted.dayOfMonth())
def parse_contract(contract_code: str) -> Optional[Tuple[int, int, str, int]]:
    """解析合约代码，返回 (expiry_year, expiry_month, cp, strike)"""
    pattern = r'IO(\d{2})(\d{2})[-]?([CP])[-]?(\d+)'
    match = re.match(pattern, contract_code)
    if not match:
        return None
    yy = int(match.group(1))
    mm = int(match.group(2))
    cp = match.group(3)
    strike = int(match.group(4))
    year = 2000 + yy
    return year, mm, cp, strike


def process_files(root_dir: Path = PROJECT_ROOT / "data") -> pd.DataFrame:
    """递归处理 root_dir 下所有 CSV 文件，提取IO期权数据，合并到一个DataFrame"""
    all_data = []
    pattern = os.path.join(root_dir, "**/*.csv")
    files = glob.glob(pattern, recursive=True)

    if not files:
        print(f"警告：未找到匹配 {pattern} 的文件")
        return pd.DataFrame()

    print(f"找到 {len(files)} 个文件")
    for file in sorted(files):
        filename = os.path.basename(file)
        # 假设文件名格式仍为 "YYYYMMDD_xxx.csv"，取下划线前部分作为日期
        date_str = filename.split('_')[0]
        try:
            trade_date = datetime.strptime(date_str, '%Y%m%d')
        except ValueError:
            print(f"警告：文件名 {filename} 无法解析日期，跳过文件 {file}")
            continue

        # 以下代码与原 process_files 完全一致
        df = pd.read_csv(file, encoding='gbk')
        df.columns = df.columns.str.strip()
        required_cols = ['合约代码', '今收盘', '成交量', '持仓量', 'Delta']
        if not all(col in df.columns for col in required_cols):
            print(f"⚠️ 文件 {filename} 缺少必要列，跳过")
            continue

        mask = df['合约代码'].str.startswith('IO', na=False)
        io_df = df[mask].copy()
        if io_df.empty:
            continue

        io_df['date'] = trade_date
        parsed = io_df['合约代码'].apply(parse_contract)
        io_df['expiry_year'] = parsed.apply(lambda x: x[0] if x else None)
        io_df['expiry_month'] = parsed.apply(lambda x: x[1] if x else None)
        io_df['cp'] = parsed.apply(lambda x: x[2] if x else None)
        io_df['strike'] = parsed.apply(lambda x: x[3] if x else None)
        io_df.dropna(inplace=True)

        def get_expiry(row: pd.Series) -> datetime:
            """由解析出的年份与月份计算该合约的到期日。"""
            return third_friday_of_month(int(row['expiry_year']), int(row['expiry_month']))

        io_df['expiry'] = io_df.apply(get_expiry, axis=1)
        io_df['date'] = pd.to_datetime(io_df['date'])
        io_df['expiry'] = pd.to_datetime(io_df['expiry'])
        io_df['T'] = (io_df['expiry'] - io_df['date']).dt.days / 365.0

        rename_map = {
            '今收盘': 'close',
            '成交量': 'volume',
            '持仓量': 'open_interest',
            'Delta': 'delta'
        }
        io_df.rename(columns=rename_map, inplace=True)
        final_cols = ['date', '合约代码', 'strike', 'cp', 'close', 'volume', 'open_interest', 'delta', 'expiry', 'T']
        io_df = io_df[final_cols]
        all_data.append(io_df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        print("未找到任何IO数据")
        return pd.DataFrame()


if __name__ == "__main__":
    df = process_files(root_dir=PROJECT_ROOT / "data")
    if not df.empty:
        df.sort_values(['date', '合约代码'], inplace=True)
        output_file = PROJECT_ROOT / "data" / "io_options_processed.csv"
        df.to_csv(output_file, index=False, encoding='gbk')
        print(f"处理完成，共 {len(df)} 条记录，已保存至 {output_file}")
    else:
        print("处理失败，无数据输出")

