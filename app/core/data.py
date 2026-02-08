import requests
import pandas as pd
from io import StringIO
from datetime import datetime, date, timedelta

# Фиксированный URL с ПВН
URL = "https://nordpool.didnt.work/?vat"


def get_lv_prices_15min():
    """Загрузка 15-минутных интервалов NordPool (Latvia)"""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers)
    response.raise_for_status()

    dfs = pd.read_html(StringIO(response.text), header=[0, 1])
    df = dfs[0]

    cols_to_keep = [0]
    for i, col in enumerate(df.columns):
        if any(day in str(col[0]).lower() for day in ["šodien", "rīt"]):
            cols_to_keep.append(i)

    df_combined = df.iloc[:, cols_to_keep].copy()
    new_names = ["Hour"]
    for col in df_combined.columns[1:]:
        day = "Today" if "šodien" in str(col[0]).lower() else "Tomorrow"
        new_names.append(f"{day} {col[1]}")
    df_combined.columns = new_names

    df_combined = df_combined.dropna(subset=["Hour"])
    for col in df_combined.columns[1:]:
        df_combined[col] = (
            df_combined[col].astype(str).str.replace(",", ".", regex=False)
            .str.extract(r'(\d+\.\d+|\d+)').astype(float)
        )
    return df_combined


def transform_for_pro_chart(df):
    """Подготовка данных для чистого графика (ось X — время)"""
    rows = []
    today = date.today()
    tomorrow = today + timedelta(days=1)

    for _, row in df.iterrows():
        h = int(row['Hour'].split('-')[0])
        for col in df.columns[1:]:
            day_str, min_str = col.split(' ')
            m = int(min_str.replace(':', ''))
            price = row[col]
            if pd.notna(price):
                target_date = today if day_str == "Today" else tomorrow
                timestamp = datetime.combine(target_date, datetime.min.time()).replace(hour=h, minute=m)
                rows.append({"Time": timestamp, "Price": price, "Day": day_str})

    return pd.DataFrame(rows).sort_values("Time")