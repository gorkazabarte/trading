from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, Contract
from typing import Optional, Dict, List
import os
import logging

TWS_PORT = 7496
GATEWAY_PORT = 4001
DEFAULT_HOST = '127.0.0.1'
DEFAULT_CLIENT_ID = 1
DATA_WAIT_SECONDS = 3
ORDER_WAIT_SECONDS = 2
POSITION_WAIT_SECONDS = 1

logger = logging.getLogger(__name__)

class IBGatewayClient:

    def __init__(self, host: str = DEFAULT_HOST, port: Optional[int] = None,
                 client_id: int = DEFAULT_CLIENT_ID, use_tws: Optional[bool] = None):
        self.ib = IB()
        self.host = host
        self.client_id = client_id
        self.use_tws = self._determine_platform_type(use_tws)
        self.port = self._determine_port(port)
        self.connected = False
        logger.info(f"Configured for {self._get_platform_name()} on port {self.port}")

    def _determine_platform_type(self, use_tws: Optional[bool]) -> bool:
        if use_tws is None:
            return os.getenv('IB_USE_TWS', 'false').lower() == 'true'
        return use_tws

    def _determine_port(self, port: Optional[int]) -> int:
        if port is not None:
            return port
        return TWS_PORT if self.use_tws else GATEWAY_PORT

    def _get_platform_name(self) -> str:
        return 'TWS' if self.use_tws else 'IB Gateway'

    def connect(self) -> bool:
        try:
            platform_name = self._get_platform_name()
            logger.info(f"Connecting to {platform_name} at {self.host}:{self.port}...")
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"Successfully connected to {platform_name}")
            return True
        except Exception as e:
            self._log_connection_error(e)
            self.connected = False
            return False

    def _log_connection_error(self, error: Exception):
        platform_name = self._get_platform_name()
        logger.error(f"Failed to connect to {platform_name}: {error}")
        logger.error("Troubleshooting:")
        if self.use_tws:
            self._log_tws_troubleshooting()
        else:
            self._log_gateway_troubleshooting()

    def _log_tws_troubleshooting(self):
        logger.error("  1. Make sure TWS is running")
        logger.error("  2. In TWS: File → Global Configuration → API → Settings")
        logger.error("     - Enable 'Enable ActiveX and Socket Clients'")
        logger.error("     - Check Socket port is 7496")
        logger.error("     - Uncheck 'Read-Only API'")

    def _log_gateway_troubleshooting(self):
        logger.error("  1. Make sure IB Gateway is running")
        logger.error("  2. Check port is 4001 (live) or 4002 (paper)")
        logger.error("  3. Verify API settings are enabled")

    def disconnect(self):
        if self.connected:
            self.ib.disconnect()
            self.connected = False

    def get_market_data(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD',
                       use_delayed: Optional[bool] = None) -> Optional[Dict]:
        if not self.connected:
            return None

        if use_delayed is None:
            use_delayed = os.getenv('IB_USE_DELAYED_DATA', 'false').lower() == 'true'

        try:
            contract = Contract(symbol=ticker, secType='STK', exchange=exchange, currency=currency)
            self.ib.qualifyContracts(contract)

            ticker_obj = self.ib.reqMktData(contract, '233', use_delayed, False)

            for attempt in range(3):
                self.ib.sleep(DATA_WAIT_SECONDS)

                if ticker_obj.last and ticker_obj.last > 0:
                    break

                if attempt < 2:
                    logger.debug(f"{ticker} - Waiting for market data (attempt {attempt + 1}/3)")

            market_data = self._extract_market_data(ticker_obj, ticker, contract, use_delayed)

            self.ib.cancelMktData(contract)

            return market_data

        except Exception as e:
            logger.error(f"Error getting market data for {ticker}: {e}")
            return None

    def _extract_market_data(self, ticker_obj, ticker: str, contract, use_delayed: bool) -> Optional[Dict]:
        last_price = self._get_valid_price(ticker_obj.last)
        bid_price = self._get_valid_price(ticker_obj.bid)
        ask_price = self._get_valid_price(ticker_obj.ask)

        if not last_price and bid_price and ask_price:
            last_price = (bid_price + ask_price) / 2

        close_price = (
            self._get_valid_price(ticker_obj.close) or
            self._get_valid_price(getattr(ticker_obj, 'previousClose', None)) or
            self._get_valid_price(getattr(ticker_obj, 'prevClose', None))
        )

        if not close_price:
            logger.debug(f"{ticker} - Fetching previous closing price from historical data")
            close_price = self._get_previous_close(contract)

        volume = ticker_obj.volume if ticker_obj.volume else 0

        if not any([last_price, bid_price, ask_price]):
            logger.warning(f"No market data available for {ticker} - may need additional subscription")
            return None

        if not close_price:
            logger.warning(f"{ticker} - No closing price available, trading evaluation will be skipped")

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
        return price if price and price > 0 else None

    def _get_previous_close(self, contract) -> Optional[float]:
        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='2 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if bars and len(bars) >= 2:
                return bars[-2].close
            elif bars and len(bars) == 1:
                return bars[0].close

            return None
        except Exception as e:
            logger.error(f"Error fetching previous close: {e}")
            return None


    def get_contract_details(self, ticker: str, exchange: str = 'SMART', currency: str = 'USD') -> Optional[int]:
        if not self.connected:
            return None

        try:
            contract = Stock(ticker, exchange, currency)
            self.ib.qualifyContracts(contract)
            return contract.conId
        except Exception as e:
            logger.error(f"Error getting contract details for {ticker}: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        if not self.connected:
            return []

        try:
            positions = self.ib.positions()
            return [self._build_position_dict(position) for position in positions]
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def cancel_all_orders(self) -> Dict:
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway', 'cancelled_count': 0}

        try:
            trades = self.ib.openTrades()
            cancelled_count = 0

            for trade in trades:
                try:
                    order = trade.order
                    self.ib.cancelOrder(order)
                    cancelled_count += 1
                    logger.info(f"Cancelled order {order.orderId}")
                except Exception as e:
                    order_id = getattr(trade.order, 'orderId', 'unknown')
                    logger.error(f"Failed to cancel order {order_id}: {e}")

            self.ib.sleep(ORDER_WAIT_SECONDS)

            return {
                'success': True,
                'cancelled_count': cancelled_count,
                'message': f'Cancelled {cancelled_count} order(s)'
            }

        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
            return {'success': False, 'error': str(e), 'cancelled_count': 0}

    def verify_no_open_orders(self) -> Dict:
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway', 'open_orders_count': 0}

        try:
            trades = self.ib.openTrades()
            open_orders_count = len(trades)

            return {
                'success': True,
                'open_orders_count': open_orders_count,
                'has_open_orders': open_orders_count > 0
            }

        except Exception as e:
            logger.error(f"Error checking open orders: {e}")
            return {'success': False, 'error': str(e), 'open_orders_count': 0}

    def verify_no_open_positions(self) -> Dict:
        if not self.connected:
            return {'success': False, 'error': 'Not connected to IB Gateway', 'open_positions_count': 0}

        try:
            positions = self.ib.positions()
            open_positions_count = len(positions)

            return {
                'success': True,
                'open_positions_count': open_positions_count,
                'has_open_positions': open_positions_count > 0
            }

        except Exception as e:
            logger.error(f"Error checking open positions: {e}")
            return {'success': False, 'error': str(e), 'open_positions_count': 0}

    def _build_position_dict(self, position) -> Dict:
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
        return ticker_obj.last if ticker_obj.last and ticker_obj.last > 0 else fallback_price


    def place_market_order(self, ticker: str, quantity: int, action: str = 'BUY',
                          exchange: str = 'SMART', currency: str = 'USD') -> Dict:
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
    global _ib_client
    if _ib_client is None:
        _ib_client = IBGatewayClient(use_tws=use_tws)
        _ib_client.connect()
    return _ib_client

def disconnect_ib_client():
    global _ib_client
    if _ib_client:
        _ib_client.disconnect()
        _ib_client = None

