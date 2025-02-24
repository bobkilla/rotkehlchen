import hashlib
import hmac
import logging
import time
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Tuple, Union, overload
from urllib.parse import urlencode

from typing_extensions import Literal

from rotkehlchen.assets.asset import Asset
from rotkehlchen.assets.converters import asset_from_bittrex
from rotkehlchen.errors import (
    DeserializationError,
    RemoteError,
    UnknownAsset,
    UnprocessableTradePair,
    UnsupportedAsset,
)
from rotkehlchen.exchange import Exchange
from rotkehlchen.fval import FVal
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.order_formatting import (
    Trade,
    get_pair_position_asset,
    get_pair_position_str,
    pair_get_assets,
    trade_pair_from_assets,
)
from rotkehlchen.serializer import (
    deserialize_asset_amount,
    deserialize_fee,
    deserialize_price,
    deserialize_timestamp_from_bittrex_date,
    deserialize_trade_type,
)
from rotkehlchen.typing import ApiKey, ApiSecret, FilePath, Timestamp, TradePair
from rotkehlchen.user_messages import MessagesAggregator
from rotkehlchen.utils.misc import cache_response_timewise
from rotkehlchen.utils.serialization import rlk_jsonloads_dict

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)


BITTREX_MARKET_METHODS = {
    'getopenorders',
    'cancel',
    'sellmarket',
    'selllimit',
    'buymarket',
    'buylimit',
}
BITTREX_ACCOUNT_METHODS = {
    'getbalances',
    'getbalance',
    'getdepositaddress',
    'withdraw',
    'getorderhistory',
}


def bittrex_pair_to_world(given_pair: str) -> TradePair:
    """
    Turns a pair written in the bittrex way to Rotkehlchen way

    Throws:
        - UnsupportedAsset due to asset_from_bittrex()
        - UnprocessableTradePair if the pair can't be split into its parts
    """
    if not isinstance(given_pair, str):
        raise DeserializationError(
            f'Could not deserialize bittrex trade pair. Expected a string '
            f'but found {type(given_pair)}',
        )
    pair = TradePair(given_pair.replace('-', '_'))
    base_currency = asset_from_bittrex(get_pair_position_str(pair, 'first'))
    quote_currency = asset_from_bittrex(get_pair_position_str(pair, 'second'))

    # Since in Bittrex the base currency is the cost currency, iow in Bittrex
    # for BTC_ETH we buy ETH with BTC and sell ETH for BTC, we need to turn it
    # into the Rotkehlchen way which is following the base/quote approach.
    pair = trade_pair_from_assets(quote_currency, base_currency)
    return pair


def world_pair_to_bittrex(pair: TradePair) -> str:
    """Turns a rotkehlchen pair to a bittrex pair"""
    base_asset, quote_asset = pair_get_assets(pair)

    base_asset_str = base_asset.to_bittrex()
    quote_asset_str = quote_asset.to_bittrex()

    # In bittrex the pairs are inverted and use '-'
    return f'{quote_asset_str}-{base_asset_str}'


def trade_from_bittrex(bittrex_trade: Dict[str, Any]) -> Trade:
    """Turn a bittrex trade returned from bittrex trade history to our common trade
    history format

    Throws:
        - UnsupportedAsset due to bittrex_pair_to_world()
        - DeserializationError due to unexpected format of dict entries
        - KeyError due to dict entries missing an expected entry
    """
    amount = (
        deserialize_asset_amount(bittrex_trade['Quantity']) -
        deserialize_asset_amount(bittrex_trade['QuantityRemaining'])
    )
    timestamp = deserialize_timestamp_from_bittrex_date(bittrex_trade['TimeStamp'])
    rate = deserialize_price(bittrex_trade['PricePerUnit'])
    order_type = deserialize_trade_type(bittrex_trade['OrderType'])
    bittrex_price = deserialize_price(bittrex_trade['Price'])
    fee = deserialize_fee(bittrex_trade['Commission'])
    pair = bittrex_pair_to_world(bittrex_trade['Exchange'])
    quote_currency = get_pair_position_asset(pair, 'second')

    log.debug(
        'Processing bittrex Trade',
        sensitive_log=True,
        amount=amount,
        rate=rate,
        order_type=order_type,
        price=bittrex_price,
        fee=fee,
        bittrex_pair=bittrex_trade['Exchange'],
        pair=pair,
    )

    return Trade(
        timestamp=timestamp,
        location='bittrex',
        pair=pair,
        trade_type=order_type,
        amount=amount,
        rate=rate,
        fee=fee,
        fee_currency=quote_currency,
    )


class Bittrex(Exchange):
    def __init__(
            self,
            api_key: ApiKey,
            secret: ApiSecret,
            user_directory: FilePath,
            msg_aggregator: MessagesAggregator,
    ):
        super(Bittrex, self).__init__('bittrex', api_key, secret, user_directory)
        self.apiversion = 'v1.1'
        self.uri = 'https://bittrex.com/api/{}/'.format(self.apiversion)
        self.msg_aggregator = msg_aggregator

    def first_connection(self) -> None:
        self.first_connection_made = True

    def validate_api_key(self) -> Tuple[bool, str]:
        try:
            self.api_query('getbalance', {'currency': 'BTC'})
        except ValueError as e:
            error = str(e)
            if error == 'APIKEY_INVALID':
                return False, 'Provided API Key is invalid'
            elif error == 'INVALID_SIGNATURE':
                return False, 'Provided API Secret is invalid'
            else:
                raise
        return True, ''

    @overload
    def api_query(  # pylint: disable=unused-argument, no-self-use
            self,
            method: Literal['getcurrencies', 'getorderhistory', 'getbalances'],
            options: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        ...

    @overload  # noqa: F811
    def api_query(  # pylint: disable=unused-argument, no-self-use
            self,
            method: Literal['getbalance'],
            options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    @overload  # noqa: F811
    def api_query(  # pylint: disable=unused-argument, no-self-use
            self,
            method: str,
            options: Optional[Dict[str, Any]] = None,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        ...

    def api_query(  # noqa: F811
            self,
            method: str,
            options: Optional[Dict[str, Any]] = None,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Queries Bittrex with given method and options
        """
        if not options:
            options = {}
        nonce = str(int(time.time() * 1000))
        method_type = 'public'

        if method in BITTREX_MARKET_METHODS:
            method_type = 'market'
        elif method in BITTREX_ACCOUNT_METHODS:
            method_type = 'account'

        request_url = self.uri + method_type + '/' + method + '?'

        if method_type != 'public':
            request_url += 'apikey=' + self.api_key.decode() + "&nonce=" + nonce + '&'

        request_url += urlencode(options)
        signature = hmac.new(
            self.secret,
            request_url.encode(),
            hashlib.sha512,
        ).hexdigest()
        self.session.headers.update({'apisign': signature})
        log.debug('Bittrex API query', request_url=request_url)
        response = self.session.get(request_url)

        if response.status_code != 200:
            raise RemoteError(
                f'Bittrex query responded with error status code: {response.status_code}'
                f' and text: {response.text}',
            )

        try:
            json_ret = rlk_jsonloads_dict(response.text)
        except JSONDecodeError:
            raise RemoteError(f'Bittrex returned invalid JSON response: {response.text}')

        if json_ret['success'] is not True:
            raise RemoteError(json_ret['message'])

        result = json_ret['result']
        assert isinstance(result, dict) or isinstance(result, list)
        return result

    def get_currencies(self) -> List[Dict[str, Any]]:
        """Gets a list of all currencies supported by Bittrex"""
        result = self.api_query('getcurrencies')
        return result

    @cache_response_timewise()
    def query_balances(self) -> Tuple[Optional[Dict[Asset, Dict[str, Any]]], str]:
        try:
            resp = self.api_query('getbalances')
        except RemoteError as e:
            msg = (
                'Bittrex API request failed. Could not reach bittrex due '
                'to {}'.format(e)
            )
            log.error(msg)
            return None, msg

        returned_balances = dict()
        for entry in resp:
            try:
                asset = asset_from_bittrex(entry['Currency'])
            except UnsupportedAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found unsupported bittrex asset {e.asset_name}. '
                    f' Ignoring its balance query.',
                )
                continue
            except UnknownAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found unknown bittrex asset {e.asset_name}. '
                    f' Ignoring its balance query.',
                )
                continue

            usd_price = Inquirer().find_usd_price(asset=asset)

            balance = dict()
            balance['amount'] = FVal(entry['Balance'])
            balance['usd_value'] = FVal(balance['amount']) * usd_price
            returned_balances[asset] = balance

            log.debug(
                'bittrex balance query result',
                sensitive_log=True,
                currency=asset,
                amount=balance['amount'],
                usd_value=balance['usd_value'],
            )

        return returned_balances, ''

    def query_trade_history(
            self,
            start_ts: Timestamp,
            end_ts: Timestamp,
            end_at_least_ts: Timestamp,
            market: Optional[TradePair] = None,
            count: Optional[int] = None,
    ) -> List[Trade]:

        options: Dict[str, Union[str, int]] = dict()
        cache = self.check_trades_cache_list(start_ts, end_at_least_ts)
        if market is not None:
            options['market'] = world_pair_to_bittrex(market)
        if count is not None:
            options['count'] = count

        if cache is not None:
            raw_data = cache
        else:
            raw_data = self.api_query('getorderhistory', options)
            log.debug('binance order history result', results_num=len(raw_data))
            self.update_trades_cache(raw_data, start_ts, end_ts)

        trades = []
        for raw_trade in raw_data:
            try:
                trade = trade_from_bittrex(raw_trade)
            except UnknownAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found bittrex trade with unknown asset '
                    f'{e.asset_name}. Ignoring it.',
                )
                continue
            except UnsupportedAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found bittrex trade with unsupported asset '
                    f'{e.asset_name}. Ignoring it.',
                )
                continue
            except UnprocessableTradePair as e:
                self.msg_aggregator.add_error(
                    f'Found bittrex trade with unprocessable pair '
                    f'{e.pair}. Ignoring it.',
                )
                continue
            except (DeserializationError, KeyError) as e:
                msg = str(e)
                if isinstance(e, KeyError):
                    msg = f'Missing key entry for {msg}.'
                self.msg_aggregator.add_error(
                    'Error processing a bittrex trade. Check logs '
                    'for details. Ignoring it.',
                )
                log.error(
                    'Error processing a bittrex trade',
                    trade=raw_trade,
                    error=msg,
                )
                continue

            if trade.timestamp < start_ts or trade.timestamp > end_ts:
                continue

            trades.append(trade)

        return trades
