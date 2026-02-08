import pandas as pd


def daily_average(df: pd.DataFrame) -> float:
    return df.iloc[:, 1:].mean().mean()
