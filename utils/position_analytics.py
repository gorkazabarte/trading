"""
Utility functions to analyze closed positions over different time periods.
"""
from datetime import datetime, timedelta
from typing import List, Dict
import json
import os


def get_date_range(days_back: int) -> List[tuple]:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    date_list = []
    current_date = start_date

    while current_date <= end_date:
        year = current_date.year
        month = current_date.month
        day = current_date.day
        date_list.append((year, month, day))
        current_date += timedelta(days=1)

    return date_list


def load_closed_positions_for_date(year: int, month: int, day: int, base_path: str = './files') -> List[Dict]:
    file_path = f"{base_path}/{year}/{month:02d}/{day:02d}/closed_positions.json"

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def load_closed_positions_from_s3_for_date(s3_client, year: int, month: int, day: int, bucket: str = 'dev-trading-data-storage') -> List[Dict]:
    s3_key = f"{year}/{month:02d}/{day:02d}/closed_positions.json"
    local_path = f"./temp_closed_positions_{year}_{month:02d}_{day:02d}.json"

    try:
        s3_client.download_file(bucket, s3_key, local_path)

        with open(local_path, 'r') as f:
            data = json.load(f)

        os.remove(local_path)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_closed_positions_for_period(days_back: int, s3_client=None, bucket: str = 'dev-trading-data-storage', use_s3: bool = False) -> List[Dict]:
    date_range = get_date_range(days_back)
    all_positions = []

    for year, month, day in date_range:
        if use_s3 and s3_client:
            positions = load_closed_positions_from_s3_for_date(s3_client, year, month, day, bucket)
        else:
            positions = load_closed_positions_for_date(year, month, day)

        all_positions.extend(positions)

    return all_positions


def calculate_statistics(positions: List[Dict]) -> Dict:
    if not positions:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'avg_profit_per_trade': 0.0,
            'win_rate': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'avg_return_pct': 0.0
        }

    total_trades = len(positions)
    winning_trades = sum(1 for p in positions if p.get('profit', 0) > 0)
    losing_trades = sum(1 for p in positions if p.get('profit', 0) < 0)
    total_profit = sum(p.get('profit', 0) for p in positions)
    avg_profit = total_profit / total_trades if total_trades > 0 else 0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    profits = [p.get('profit', 0) for p in positions]
    largest_win = max(profits) if profits else 0
    largest_loss = min(profits) if profits else 0

    returns = [p.get('return_pct', 0) for p in positions]
    avg_return = sum(returns) / len(returns) if returns else 0

    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'total_profit': round(total_profit, 2),
        'avg_profit_per_trade': round(avg_profit, 2),
        'win_rate': round(win_rate, 2),
        'largest_win': round(largest_win, 2),
        'largest_loss': round(largest_loss, 2),
        'avg_return_pct': round(avg_return, 2)
    }


def get_positions_by_ticker(positions: List[Dict]) -> Dict[str, List[Dict]]:
    by_ticker = {}
    for position in positions:
        ticker = position.get('symbol', 'UNKNOWN')
        if ticker not in by_ticker:
            by_ticker[ticker] = []
        by_ticker[ticker].append(position)
    return by_ticker


def format_statistics_report(stats: Dict, period_name: str) -> str:
    report = f"\n{'='*60}\n"
    report += f"Trading Statistics - {period_name}\n"
    report += f"{'='*60}\n"
    report += f"Total Trades: {stats['total_trades']}\n"
    report += f"Winning Trades: {stats['winning_trades']}\n"
    report += f"Losing Trades: {stats['losing_trades']}\n"
    report += f"Win Rate: {stats['win_rate']}%\n"
    report += f"Total Profit/Loss: ${stats['total_profit']:.2f}\n"
    report += f"Average P/L per Trade: ${stats['avg_profit_per_trade']:.2f}\n"
    report += f"Average Return: {stats['avg_return_pct']:.2f}%\n"
    report += f"Largest Win: ${stats['largest_win']:.2f}\n"
    report += f"Largest Loss: ${stats['largest_loss']:.2f}\n"
    report += f"{'='*60}\n"
    return report


def generate_performance_report(days_back: int, s3_client=None, use_s3: bool = False) -> str:
    positions = get_closed_positions_for_period(days_back, s3_client, use_s3=use_s3)
    stats = calculate_statistics(positions)

    period_name = f"Last {days_back} days"
    report = format_statistics_report(stats, period_name)

    if positions:
        by_ticker = get_positions_by_ticker(positions)
        report += "\nTop Performers:\n"

        ticker_stats = []
        for ticker, ticker_positions in by_ticker.items():
            ticker_profit = sum(p.get('profit', 0) for p in ticker_positions)
            ticker_stats.append((ticker, ticker_profit, len(ticker_positions)))

        ticker_stats.sort(key=lambda x: x[1], reverse=True)

        for ticker, profit, count in ticker_stats[:10]:
            report += f"  {ticker}: ${profit:.2f} ({count} trade{'s' if count > 1 else ''})\n"

    return report

