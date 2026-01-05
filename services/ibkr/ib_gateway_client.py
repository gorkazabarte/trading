from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, Contract
from typing import Optional, Dict, List
import os

TWS_PORT = 7496
GATEWAY_PORT = 4001
DEFAULT_HOST = '127.0.0.1'
DEFAULT_CLIENT_ID = 1
DATA_WAIT_SECONDS = 3
ORDER_WAIT_SECONDS = 2
POSITION_WAIT_SECONDS = 1

class IBGatewayClient:
    """Client for connecting to Interactive Brokers TWS or IB Gateway."""

    def __init__(self, host: str = DEFAULT_HOST, port: Optional[int] = None,
                 client_id: int = DEFAULT_CLIENT_ID, use_tws: Optional[bool] = None):
        self.ib = IB()
        self.host = host
        self.client_id = client_id
        self.use_tws = self._determine_platform_type(use_tws)
        self.port = self._determine_port(port)
        self.connected = False
        print(f"Configured for {self._get_platform_name()} on port {self.port}")

    def _determine_platform_type(self, use_tws: Optional[bool]) -> bool:
        """Determine whether to use TWS or Gateway from parameter or environment."""
        if use_tws is None:
            return os.getenv('IB_USE_TWS', 'false').lower() == 'true'
        return use_tws

    def _determine_port(self, port: Optional[int]) -> int:
        """Determine the connection port based on platform type or explicit port."""
        if port is not None:
            return port
        return TWS_PORT if self.use_tws else GATEWAY_PORT

    def _get_platform_name(self) -> str:
        """Get the name of the current platform."""
        return 'TWS' if self.use_tws else 'IB Gateway'

    def connect(self) -> bool:
        """Establish connection to IB Gateway or TWS."""
        try:
            platform_name = self._get_platform_name()
            print(f"Connecting to {platform_name} at {self.host}:{self.port}...")
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            print(f"Successfully connected to {platform_name}")
            return True
        except Exception as e:
            self._print_connection_error(e)
            self.connected = False
            return False

    def _print_connection_error(self, error: Exception):
        """Print detailed connection error and troubleshooting steps."""
        platform_name = self._get_platform_name()
        print(f"✗ Failed to connect to {platform_name}: {error}")
        print(f"\nTroubleshooting:")
        if self.use_tws:
            self._print_tws_troubleshooting()
        else:
            self._print_gateway_troubleshooting()

    def _print_tws_troubleshooting(self):
        """Print TWS-specific troubleshooting steps."""
        print("  1. Make sure TWS is running")
        print("  2. In TWS: File → Global Configuration → API → Settings")
        print("     - Enable 'Enable ActiveX and Socket Clients'")
        print("     - Check Socket port is 7496")
        print("     - Uncheck 'Read-Only API'")

    def _print_gateway_troubleshooting(self):
        """Print IB Gateway-specific troubleshooting steps."""
        print("  1. Make sure IB Gateway is running")
        print("  2. Check port is 4001 (live) or 4002 (paper)")
        print("  3. Verify API settings are enabled")

    def disconnect(self):
        """Disconnect from IB Gateway or TWS."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False

    def get_market_data(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD',
                       use_delayed: Optional[bool] = None) -> Optional[Dict]:
        """
        Retrieve real-time or delayed market data for a stock ticker.

        Args:
            ticker: Stock symbol
            exchange: Exchange routing (default: SMART for best execution)
            currency: Currency denomination
            use_delayed: Use delayed data feed; auto-detects from IB_USE_DELAYED_DATA env var if None

        Returns:
            Dictionary containing price data or None if unavailable
        """
        if not self.connected:
            return None

        if use_delayed is None:
            use_delayed = os.getenv('IB_USE_DELAYED_DATA', 'false').lower() == 'true'

        try:
            contract = Contract(symbol=ticker, secType='STK', exchange=exchange, currency=currency)
            self.ib.qualifyContracts(contract)
            ticker_obj = self.ib.reqMktData(contract, '', use_delayed, False)

            self.ib.sleep(DATA_WAIT_SECONDS)

            market_data = self._extract_market_data(ticker_obj, ticker, contract, use_delayed)

            self.ib.cancelMktData(contract)

            return market_data

        except Exception as e:
            print(f"Error getting market data for {ticker}: {e}")
            return None

    def _extract_market_data(self, ticker_obj, ticker: str, contract, use_delayed: bool) -> Optional[Dict]:
        """Extract and validate market data from ticker object."""
        last_price = self._get_valid_price(ticker_obj.last)
        bid_price = self._get_valid_price(ticker_obj.bid)
        ask_price = self._get_valid_price(ticker_obj.ask)
        close_price = self._get_valid_price(ticker_obj.close)
        volume = ticker_obj.volume if ticker_obj.volume else 0

        if not any([last_price, bid_price, ask_price, close_price]):
            print(f"No market data available for {ticker} - may need additional subscription")
            return None

        return {
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

    def _get_valid_price(self, price) -> Optional[float]:
        """Return price if valid (non-null and positive), otherwise None."""
        return price if price and price > 0 else None


    def get_contract_details(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD') -> Optional[int]:
        """Retrieve contract ID for a stock ticker."""
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
        """Retrieve all open positions with current market data."""
        if not self.connected:
            return []

        try:
            positions = self.ib.positions()
            return [self._build_position_dict(position) for position in positions]
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def _build_position_dict(self, position) -> Dict:
        """Build position dictionary with current market data."""
        contract = position.contract

        ticker_obj = self.ib.reqMktData(contract, '', False, False)
        self.ib.sleep(POSITION_WAIT_SECONDS)

        market_price = self._get_market_price(ticker_obj, position.avgCost)
        market_value = market_price * position.position
        unrealized_pnl = market_value - (position.avgCost * position.position)

        self.ib.cancelMktData(contract)

        return {
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

    def _get_market_price(self, ticker_obj, fallback_price: float) -> float:
        """Get market price from ticker object or fallback to average cost."""
        return ticker_obj.last if ticker_obj.last and ticker_obj.last > 0 else fallback_price


    def place_market_order(self, ticker: str, quantity: int, action: str = 'BUY',
                          exchange: str = 'SMART', currency: str = 'USD') -> Dict:
        """
        Submit a market order for immediate execution.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            action: Order action ('BUY' or 'SELL')
            exchange: Exchange routing (default: SMART)
            currency: Currency denomination

        Returns:
            Dictionary with order status and details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            order = MarketOrder(action, quantity)
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(ORDER_WAIT_SECONDS)

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
        Submit a bracket order with market entry, stop loss, and take profit.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            stop_loss_price: Stop loss trigger price
            take_profit_price: Take profit limit price
            exchange: Exchange routing (default: SMART)
            currency: Currency denomination

        Returns:
            Dictionary with order status and details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            parent = MarketOrder('BUY', quantity)
            parent.orderId = self.ib.client.getReqId()
            parent.transmit = False

            take_profit = LimitOrder('SELL', quantity, take_profit_price)
            take_profit.orderId = self.ib.client.getReqId()
            take_profit.parentId = parent.orderId
            take_profit.transmit = False

            stop_loss = StopOrder('SELL', quantity, stop_loss_price)
            stop_loss.orderId = self.ib.client.getReqId()
            stop_loss.parentId = parent.orderId
            stop_loss.transmit = True

            parent_trade = self.ib.placeOrder(contract, parent)
            self.ib.placeOrder(contract, take_profit)
            self.ib.placeOrder(contract, stop_loss)

            self.ib.sleep(ORDER_WAIT_SECONDS)

            return {
                'success': True,
                'order_id': parent_trade.order.orderId,
                'status': parent_trade.orderStatus.status,
                'filled': parent_trade.orderStatus.filled,
                'remaining': parent_trade.orderStatus.remaining,
                'bracket_orders': 3
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def place_stop_bracket_order(self, ticker: str, quantity: int, stop_price: float,
                                 stop_loss_price: float, take_profit_price: float,
                                 exchange: str = 'SMART', currency: str = 'USD') -> Dict:
        """
        Submit a bracket order with STOP entry, stop loss, and take profit.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            stop_price: Price at which to trigger the buy order
            stop_loss_price: Stop loss trigger price
            take_profit_price: Take profit limit price
            exchange: Exchange routing (default: SMART)
            currency: Currency denomination

        Returns:
            Dictionary with order status and details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            parent = StopOrder('BUY', quantity, stop_price)
            parent.orderId = self.ib.client.getReqId()
            parent.transmit = False

            take_profit = LimitOrder('SELL', quantity, take_profit_price)
            take_profit.orderId = self.ib.client.getReqId()
            take_profit.parentId = parent.orderId
            take_profit.transmit = False

            stop_loss = StopOrder('SELL', quantity, stop_loss_price)
            stop_loss.orderId = self.ib.client.getReqId()
            stop_loss.parentId = parent.orderId
            stop_loss.transmit = True

            parent_trade = self.ib.placeOrder(contract, parent)
            self.ib.placeOrder(contract, take_profit)
            self.ib.placeOrder(contract, stop_loss)

            self.ib.sleep(ORDER_WAIT_SECONDS)

            return {
                'success': True,
                'order_id': parent_trade.order.orderId,
                'status': parent_trade.orderStatus.status,
                'filled': parent_trade.orderStatus.filled,
                'remaining': parent_trade.orderStatus.remaining,
                'bracket_orders': 3,
                'order_type': 'STOP'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def place_limit_bracket_order(self, ticker: str, quantity: int, limit_price: float,
                                  stop_loss_price: float, take_profit_price: float,
                                  exchange: str = 'SMART', currency: str = 'USD') -> Dict:
        """
        Submit a bracket order with LIMIT entry, stop loss, and take profit.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            limit_price: Maximum price to pay for the buy order
            stop_loss_price: Stop loss trigger price
            take_profit_price: Take profit limit price
            exchange: Exchange routing (default: SMART)
            currency: Currency denomination

        Returns:
            Dictionary with order status and details
        """
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway'}

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)

            parent = LimitOrder('BUY', quantity, limit_price)
            parent.orderId = self.ib.client.getReqId()
            parent.transmit = False

            take_profit = LimitOrder('SELL', quantity, take_profit_price)
            take_profit.orderId = self.ib.client.getReqId()
            take_profit.parentId = parent.orderId
            take_profit.transmit = False

            stop_loss = StopOrder('SELL', quantity, stop_loss_price)
            stop_loss.orderId = self.ib.client.getReqId()
            stop_loss.parentId = parent.orderId
            stop_loss.transmit = True

            parent_trade = self.ib.placeOrder(contract, parent)
            self.ib.placeOrder(contract, take_profit)
            self.ib.placeOrder(contract, stop_loss)

            self.ib.sleep(ORDER_WAIT_SECONDS)

            return {
                'success': True,
                'order_id': parent_trade.order.orderId,
                'status': parent_trade.orderStatus.status,
                'filled': parent_trade.orderStatus.filled,
                'remaining': parent_trade.orderStatus.remaining,
                'bracket_orders': 3,
                'order_type': 'LIMIT'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

_ib_client = None

def get_ib_client(use_tws: Optional[bool] = None) -> IBGatewayClient:
    """Get or create singleton IB Gateway/TWS client instance."""
    global _ib_client
    if _ib_client is None:
        _ib_client = IBGatewayClient(use_tws=use_tws)
        _ib_client.connect()
    return _ib_client

def disconnect_ib_client():
    """Disconnect and reset IB Gateway/TWS client singleton."""
    global _ib_client
    if _ib_client:
        _ib_client.disconnect()
        _ib_client = None

