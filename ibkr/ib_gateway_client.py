from ib_insync import IB, Stock, MarketOrder, LimitOrder, Order, Contract
from typing import Optional, Dict, List
import os

class IBGatewayClient:
    """
    Client for connecting to IBKR TWS or IB Gateway

    Default Ports:
    - TWS Live: 7496
    - TWS Paper: 7497
    - IB Gateway Live: 4001
    - IB Gateway Paper: 4002

    Set environment variable IB_USE_TWS=true to use TWS, or pass use_tws=True
    """
    def __init__(self, host: str = '127.0.0.1', port: Optional[int] = None,
                 client_id: int = 1, use_tws: Optional[bool] = None):
        self.ib = IB()
        self.host = host
        self.client_id = client_id

        # Determine if using TWS or Gateway
        if use_tws is None:
            use_tws = os.getenv('IB_USE_TWS', 'false').lower() == 'true'

        self.use_tws = use_tws

        # Set port based on TWS or Gateway
        if port is None:
            self.port = 7496 if use_tws else 4001  # TWS: 7496, Gateway: 4001
        else:
            self.port = port

        self.connected = False

        print(f"Configured for {'TWS' if use_tws else 'IB Gateway'} on port {self.port}")

    def connect(self) -> bool:
        """Connect to IB Gateway or TWS"""
        try:
            print(f"Connecting to {'TWS' if self.use_tws else 'IB Gateway'} at {self.host}:{self.port}...")
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            print(f"✓ Successfully connected to {'TWS' if self.use_tws else 'IB Gateway'}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to {'TWS' if self.use_tws else 'IB Gateway'}: {e}")
            print(f"\nTroubleshooting:")
            if self.use_tws:
                print("  1. Make sure TWS is running")
                print("  2. In TWS: File → Global Configuration → API → Settings")
                print("     - Enable 'Enable ActiveX and Socket Clients'")
                print("     - Check Socket port is 7496")
                print("     - Uncheck 'Read-Only API'")
            else:
                print("  1. Make sure IB Gateway is running")
                print("  2. Check port is 4001 (live) or 4002 (paper)")
                print("  3. Verify API settings are enabled")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False

    def get_market_data(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD',
                       use_delayed: Optional[bool] = None) -> Optional[Dict]:
        """
        Get real-time market data for a ticker

        Args:
            ticker: Stock symbol
            exchange: Exchange (default: SMART)
            currency: Currency (default: USD)
            use_delayed: True for delayed data (free), False for real-time, None to auto-detect from env

        Returns: dict with last_price, bid_price, ask_price, volume, etc.
        """
        if not self.connected:
            return None

        if use_delayed is None:
            use_delayed = os.getenv('IB_USE_DELAYED_DATA', 'false').lower() == 'true'

        try:
            contract = Contract(symbol=ticker, secType='STK', exchange=exchange, currency=currency)
            self.ib.qualifyContracts(contract)
            ticker_obj = self.ib.reqMktData(contract, '', use_delayed, False)

            # Wait for data to arrive
            self.ib.sleep(3)

            # Extract data with None handling
            last_price = ticker_obj.last if ticker_obj.last and ticker_obj.last > 0 else None
            bid_price = ticker_obj.bid if ticker_obj.bid and ticker_obj.bid > 0 else None
            ask_price = ticker_obj.ask if ticker_obj.ask and ticker_obj.ask > 0 else None
            close_price = ticker_obj.close if ticker_obj.close and ticker_obj.close > 0 else None
            volume = ticker_obj.volume if ticker_obj.volume else 0

            # Cancel market data subscription
            self.ib.cancelMktData(contract)

            # If no price data available, return None
            if last_price is None and bid_price is None and ask_price is None and close_price is None:
                print(f"No market data available for {ticker} - may need additional subscription")
                return None

            result = {
                'ticker': ticker,
                'conid': contract.conId,
                'last_price': last_price,
                'bid_price': bid_price,
                'ask_price': ask_price,
                'volume': volume,
                'close_price': close_price,
                'exchange': contract.exchange,
                'currency': contract.currency,
                'data_type': 'delayed' if use_delayed else 'real-time'
            }


            return result

        except Exception as e:
            print(f"Error getting market data for {ticker}: {e}")
            return None

    def get_contract_details(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD') -> Optional[int]:
        """Get contract ID (conid) for a ticker"""
        if not self.connected:
            return None

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)
            return contract.conId
        except Exception as e:
            print(f"Error getting contract details for {ticker}: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """
        Get all open positions from IB Gateway
        Returns: list of position dicts with ticker, conid, quantity, avg_price, market_value, etc.
        """
        if not self.connected:
            return []

        try:
            positions = self.ib.positions()

            result = []
            for position in positions:
                contract = position.contract

                # Get current market price
                ticker_obj = self.ib.reqMktData(contract, '', False, False)
                self.ib.sleep(1)

                market_price = ticker_obj.last if ticker_obj.last and ticker_obj.last > 0 else position.avgCost
                market_value = market_price * position.position
                unrealized_pnl = market_value - (position.avgCost * position.position)

                # Cancel market data to avoid subscription limits
                self.ib.cancelMktData(contract)

                position_data = {
                    'ticker': contract.symbol,
                    'conid': contract.conId,
                    'position': position.position,
                    'average_price': position.avgCost,
                    'market_price': market_price,
                    'market_value': market_value,
                    'unrealized_pnl': unrealized_pnl,
                    'currency': contract.currency,
                    'exchange': contract.exchange
                }
                result.append(position_data)

            return result

        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def place_market_order(self, ticker: str, quantity: int, action: str = 'BUY',
                          exchange: str = 'SMART', currency: str = 'USD') -> Dict:
        """
        Place a market order
        Args:
            ticker: Stock symbol
            quantity: Number of shares
            action: 'BUY' or 'SELL'
            exchange: Exchange to route order (default: SMART)
            currency: Currency (default: USD)
        Returns: dict with success status and order details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            # Create contract
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            # Create market order
            order = MarketOrder(action, quantity)

            # Place order
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(1)  # Wait for order to be submitted

            return {
                'success': True,
                'order_id': trade.order.orderId,
                'status': trade.orderStatus.status,
                'filled': trade.orderStatus.filled,
                'remaining': trade.orderStatus.remaining
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def place_bracket_order(self, ticker: str, quantity: int,
                           stop_loss_price: float, take_profit_price: float,
                           exchange: str = 'SMART', currency: str = 'USD') -> Dict:
        """
        Place a bracket order (market entry + stop loss + take profit)
        Args:
            ticker: Stock symbol
            quantity: Number of shares
            stop_loss_price: Stop loss trigger price
            take_profit_price: Take profit limit price
            exchange: Exchange to route order (default: SMART)
            currency: Currency (default: USD)
        Returns: dict with success status and order details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            # Create contract
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            # Create bracket order using ib_insync's bracket order helper
            bracket = self.ib.bracketOrder(
                'BUY',
                quantity,
                limitPrice=None,  # Market order for entry
                takeProfitPrice=take_profit_price,
                stopLossPrice=stop_loss_price
            )

            # Place all orders in the bracket
            trades = []
            for order in bracket:
                trade = self.ib.placeOrder(contract, order)
                trades.append(trade)

            self.ib.sleep(2)  # Wait for orders to be submitted

            # Get status of parent (entry) order
            parent_trade = trades[0]

            return {
                'success': True,
                'order_id': parent_trade.order.orderId,
                'status': parent_trade.orderStatus.status,
                'filled': parent_trade.orderStatus.filled,
                'remaining': parent_trade.orderStatus.remaining,
                'bracket_orders': len(trades)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

# Global singleton instance
_ib_client = None

def get_ib_client(use_tws: Optional[bool] = None) -> IBGatewayClient:
    """
    Get or create IB Gateway/TWS client singleton

    Args:
        use_tws: True to use TWS, False for Gateway, None to auto-detect from env

    Returns:
        IBGatewayClient instance
    """
    global _ib_client
    if _ib_client is None:
        _ib_client = IBGatewayClient(use_tws=use_tws)
        _ib_client.connect()
    return _ib_client

def disconnect_ib_client():
    """Disconnect IB Gateway/TWS client"""
    global _ib_client
    if _ib_client:
        _ib_client.disconnect()
        _ib_client = None

