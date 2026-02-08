import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


def daily_average(df: pd.DataFrame) -> float:
    """
    Calculate daily average electricity price

    Args:
        df: DataFrame with 'Hour' column and price columns

    Returns:
        Average price in €/kWh
    """
    price_columns = [col for col in df.columns if col != 'Hour']
    if not price_columns:
        return 0.0

    prices = df[price_columns].values.flatten()
    prices = prices[~np.isnan(prices)]

    if len(prices) == 0:
        return 0.0

    return float(np.mean(prices))


def find_optimal_windows(df: pd.DataFrame, day: str = "Today",
                         window_sizes: List[int] = [3, 6]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Find optimal time windows for electricity consumption

    Args:
        df: DataFrame with price data
        day: "Today" or "Tomorrow"
        window_sizes: List of window sizes in hours to analyze

    Returns:
        Tuple of (best_hours, best_windows, worst_hours)
    """
    # Filter columns for the specified day
    day_columns = [col for col in df.columns if day in col]
    if not day_columns:
        return [], [], []

    # Create a flat list of all prices with their times
    prices_by_time = []

    for _, row in df.iterrows():
        hour_range = row['Hour']
        start_hour = int(hour_range.split('-')[0])

        for col in day_columns:
            if pd.isna(row[col]):
                continue

            time_str = col.split(' ')[1]  # Get time like "00:00"
            hour = int(time_str.split(':')[0])
            minute = int(time_str.split(':')[1])

            # Calculate actual hour (0-23)
            actual_hour = start_hour + (hour // 100)

            prices_by_time.append({
                'hour': actual_hour,
                'minute': minute,
                'time': f"{actual_hour:02d}:{minute:02d}",
                'price': row[col],
                'datetime': datetime.now().replace(hour=actual_hour, minute=minute, second=0)
            })

    if not prices_by_time:
        return [], [], []

    # Sort by time
    prices_by_time.sort(key=lambda x: x['datetime'])

    # Find best individual hours (cheapest)
    best_hours = sorted(prices_by_time, key=lambda x: x['price'])[:10]

    # Find worst individual hours (most expensive)
    worst_hours = sorted(prices_by_time, key=lambda x: x['price'], reverse=True)[:10]

    # Find best windows for each window size
    best_windows = []

    for window_size in window_sizes:
        window_hours = window_size

        # Convert to 15-minute intervals
        window_intervals = window_hours * 4

        # Find sliding windows
        for i in range(len(prices_by_time) - window_intervals + 1):
            window = prices_by_time[i:i + window_intervals]
            avg_price = sum(item['price'] for item in window) / len(window)

            best_windows.append({
                'start': window[0]['time'],
                'end': window[-1]['time'],
                'start_time': window[0]['datetime'],
                'end_time': window[-1]['datetime'],
                'avg_price': avg_price,
                'window_size': window_size,
                'prices': [item['price'] for item in window]
            })

    # Sort windows by average price
    best_windows.sort(key=lambda x: x['avg_price'])

    # Keep only top 5 windows per size
    final_windows = []
    for size in window_sizes:
        size_windows = [w for w in best_windows if w['window_size'] == size]
        final_windows.extend(size_windows[:5])

    return best_hours, final_windows, worst_hours


def calculate_price_statistics(df: pd.DataFrame) -> Dict:
    """
    Calculate comprehensive price statistics

    Args:
        df: DataFrame with price data

    Returns:
        Dictionary with price statistics
    """
    stats = {}

    # Today's statistics
    today_cols = [c for c in df.columns if "Today" in c]
    if today_cols:
        today_prices = df[today_cols].values.flatten()
        today_prices = today_prices[~np.isnan(today_prices)]

        stats['today'] = {
            'min': float(np.min(today_prices)) if len(today_prices) > 0 else 0,
            'max': float(np.max(today_prices)) if len(today_prices) > 0 else 0,
            'avg': float(np.mean(today_prices)) if len(today_prices) > 0 else 0,
            'std': float(np.std(today_prices)) if len(today_prices) > 0 else 0,
            'q25': float(np.percentile(today_prices, 25)) if len(today_prices) > 0 else 0,
            'q75': float(np.percentile(today_prices, 75)) if len(today_prices) > 0 else 0,
        }

    # Tomorrow's statistics
    tomorrow_cols = [c for c in df.columns if "Tomorrow" in c]
    if tomorrow_cols:
        tomorrow_prices = df[tomorrow_cols].values.flatten()
        tomorrow_prices = tomorrow_prices[~np.isnan(tomorrow_prices)]

        stats['tomorrow'] = {
            'min': float(np.min(tomorrow_prices)) if len(tomorrow_prices) > 0 else 0,
            'max': float(np.max(tomorrow_prices)) if len(tomorrow_prices) > 0 else 0,
            'avg': float(np.mean(tomorrow_prices)) if len(tomorrow_prices) > 0 else 0,
        }

    # Price volatility
    if 'today' in stats and len(today_prices) > 1:
        price_changes = np.diff(today_prices)
        stats['volatility'] = {
            'max_change': float(np.max(np.abs(price_changes))) if len(price_changes) > 0 else 0,
            'avg_change': float(np.mean(np.abs(price_changes))) if len(price_changes) > 0 else 0,
        }

    # Peak/Off-peak analysis
    if 'today' in stats:
        peak_threshold = stats['today']['q75']
        off_peak_threshold = stats['today']['q25']

        peak_hours = today_prices[today_prices >= peak_threshold]
        off_peak_hours = today_prices[today_prices <= off_peak_threshold]

        stats['peak_analysis'] = {
            'peak_hours_count': len(peak_hours),
            'off_peak_hours_count': len(off_peak_hours),
            'peak_avg': float(np.mean(peak_hours)) if len(peak_hours) > 0 else 0,
            'off_peak_avg': float(np.mean(off_peak_hours)) if len(off_peak_hours) > 0 else 0,
        }

    return stats


def predict_tomorrow_based_on_history(current_prices: np.ndarray,
                                      historical_avg: float = 0.18) -> Dict:
    """
    Simple prediction based on historical comparison

    Args:
        current_prices: Today's prices
        historical_avg: Historical average price (7-30 days)

    Returns:
        Prediction dictionary
    """
    if len(current_prices) == 0:
        return {'prediction': 'No data', 'confidence': 0}

    today_avg = np.mean(current_prices)
    diff = today_avg - historical_avg
    diff_percent = (diff / historical_avg) * 100

    if diff_percent < -10:
        prediction = "Significantly cheaper than average"
        confidence = 0.8
    elif diff_percent < -5:
        prediction = "Cheaper than average"
        confidence = 0.6
    elif diff_percent < 5:
        prediction = "Normal price range"
        confidence = 0.5
    elif diff_percent < 10:
        prediction = "More expensive than average"
        confidence = 0.6
    else:
        prediction = "Significantly expensive"
        confidence = 0.8

    return {
        'prediction': prediction,
        'confidence': confidence,
        'today_avg': today_avg,
        'historical_avg': historical_avg,
        'difference': diff,
        'difference_percent': diff_percent
    }