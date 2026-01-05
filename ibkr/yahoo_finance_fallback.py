from typing import Optional

import yfinance as yf

def get_current_price_from_yahoo(ticker: str) -> Optional[float]:
    """
    Get current price from Yahoo Finance
    Fast and simple - only fetches current price
    Returns float price or None if failed
    """
    try:
        stock = yf.Ticker(ticker)

        # Try to get current price from fast_info (faster than info)
        try:
            current_price = stock.fast_info.get('lastPrice')
            if current_price:
                return float(current_price)
        except:
            pass

        # Fallback to regular info
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')

        if current_price:
            return float(current_price)

        return None

    except Exception:
        return None



def should_use_yahoo_fallback(exchange_code: str) -> bool:
    """
    Determine if we should use Yahoo Finance fallback
    Returns True if IBKR is returning delayed data (DPB)
    """
    return exchange_code == 'DPB'


def get_current_price_with_fallback(ticker: str, ibkr_price: Optional[float], exchange_code: str) -> tuple[Optional[float], str]:
    """
    Get current price with Yahoo Finance fallback if IBKR returns DPB

    Args:
        ticker: Stock ticker symbol
        ibkr_price: Price from IBKR (can be delayed)
        exchange_code: Exchange code from IBKR (e.g., 'DPB', 'NASDAQ')

    Returns:
        (price, source) tuple where source is 'IBKR' or 'Yahoo Finance'
    """
    if not should_use_yahoo_fallback(exchange_code):
        return (ibkr_price, 'IBKR')

    yahoo_price = get_current_price_from_yahoo(ticker)

    if yahoo_price:
        return (yahoo_price, 'Yahoo Finance')

    return (ibkr_price, 'IBKR (Delayed)')

