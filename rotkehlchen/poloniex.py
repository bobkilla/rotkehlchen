#!/usr/bin/env python
import csv
import datetime
import hashlib
import hmac
import logging
import os
import time
import traceback
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Tuple, Union, overload
from urllib.parse import urlencode

from typing_extensions import Literal

from rotkehlchen.assets.asset import Asset
from rotkehlchen.assets.converters import asset_from_poloniex
from rotkehlchen.constants.misc import ZERO
from rotkehlchen.errors import (
    DeserializationError,
    PoloniexError,
    RemoteError,
    UnknownAsset,
    UnsupportedAsset,
)
from rotkehlchen.exchange import Exchange
from rotkehlchen.fval import FVal
from rotkehlchen.inquirer import Inquirer
from rotkehlchen.logging import RotkehlchenLogsAdapter, make_sensitive
from rotkehlchen.order_formatting import (
    AssetMovement,
    Loan,
    Trade,
    TradeType,
    get_pair_position_str,
    invert_pair,
    trade_pair_from_assets,
)
from rotkehlchen.serializer import (
    deserialize_asset_amount,
    deserialize_fee,
    deserialize_price,
    deserialize_timestamp,
    deserialize_timestamp_from_poloniex_date,
    deserialize_trade_type,
)
from rotkehlchen.typing import ApiKey, ApiSecret, Fee, FilePath, Timestamp, TradePair
from rotkehlchen.user_messages import MessagesAggregator
from rotkehlchen.utils.misc import cache_response_timewise, createTimeStamp, retry_calls
from rotkehlchen.utils.serialization import rlk_jsonloads, rlk_jsonloads_dict, rlk_jsonloads_list

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)


def tsToDate(s):
    return datetime.datetime.fromtimestamp(s).strftime('%Y-%m-%d %H:%M:%S')


def trade_from_poloniex(poloniex_trade: Dict[str, Any], pair: TradePair) -> Trade:
    """Turn a poloniex trade returned from poloniex trade history to our common trade
    history format

    Throws:
        - UnsupportedAsset due to asset_from_poloniex()
        - DeserializationError due to the data being in unexpected format
    """

    try:
        trade_type = deserialize_trade_type(poloniex_trade['type'])
        amount = deserialize_asset_amount(poloniex_trade['amount'])
        rate = deserialize_price(poloniex_trade['rate'])
        perc_fee = deserialize_fee(poloniex_trade['fee'])
        base_currency = asset_from_poloniex(get_pair_position_str(pair, 'first'))
        quote_currency = asset_from_poloniex(get_pair_position_str(pair, 'second'))
        timestamp = deserialize_timestamp_from_poloniex_date(poloniex_trade['date'])
    except KeyError as e:
        raise DeserializationError(
            f'Poloniex trade deserialization error. Missing key entry for {str(e)} in trade dict',
        )

    cost = rate * amount
    if trade_type == TradeType.BUY:
        fee = amount * perc_fee
        fee_currency = quote_currency
    elif trade_type == TradeType.SELL:
        fee = cost * perc_fee
        fee_currency = base_currency
    else:
        raise ValueError('Got unexpected trade type "{}" for poloniex trade'.format(trade_type))

    if poloniex_trade['category'] == 'settlement':
        if trade_type == TradeType.BUY:
            trade_type = TradeType.SETTLEMENT_BUY
        else:
            trade_type = TradeType.SETTLEMENT_SELL

    log.debug(
        'Processing poloniex Trade',
        sensitive_log=True,
        timestamp=timestamp,
        order_type=trade_type,
        pair=pair,
        base_currency=base_currency,
        quote_currency=quote_currency,
        amount=amount,
        fee=fee,
        rate=rate,
    )

    # Use the converted assets in our pair
    pair = trade_pair_from_assets(base_currency, quote_currency)
    # Since in Poloniex the base currency is the cost currency, iow in poloniex
    # for BTC_ETH we buy ETH with BTC and sell ETH for BTC, we need to turn it
    # into the Rotkehlchen way which is following the base/quote approach.
    pair = invert_pair(pair)
    return Trade(
        timestamp=timestamp,
        location='poloniex',
        pair=pair,
        trade_type=trade_type,
        amount=amount,
        rate=rate,
        fee=fee,
        fee_currency=fee_currency,
    )


def process_polo_loans(
        msg_aggregator: MessagesAggregator,
        data: List[Dict],
        start_ts: Timestamp,
        end_ts: Timestamp,
) -> List[Loan]:
    """Takes in the list of loans from poloniex as returned by the returnLendingHistory
    api call, processes it and returns it into our loan format
    """
    new_data = list()

    for loan in reversed(data):
        log.debug('processing poloniex loan', **make_sensitive(loan))
        try:
            close_time = deserialize_timestamp_from_poloniex_date(loan['close'])
            open_time = deserialize_timestamp_from_poloniex_date(loan['open'])
            if open_time < start_ts:
                continue
            if close_time > end_ts:
                continue

            our_loan = Loan(
                open_time=open_time,
                close_time=close_time,
                currency=asset_from_poloniex(loan['currency']),
                fee=deserialize_fee(loan['fee']),
                earned=deserialize_asset_amount(loan['earned']),
                amount_lent=deserialize_asset_amount(loan['amount']),
            )
        except UnsupportedAsset as e:
            msg_aggregator.add_warning(
                f'Found poloniex loan with unsupported asset'
                f' {e.asset_name}. Ignoring it.',
            )
            continue
        except UnknownAsset as e:
            msg_aggregator.add_warning(
                f'Found poloniex loan with unknown asset'
                f' {e.asset_name}. Ignoring it.',
            )
            continue
        except (DeserializationError, KeyError) as e:
            msg = str(e)
            if isinstance(e, KeyError):
                msg = f'Missing key entry for {msg}.'
            msg_aggregator.add_error(
                'Deserialization error while reading a poloniex loan. Check '
                'logs for more details. Ignoring it.',
            )
            log.error(
                'Deserialization error while reading a poloniex loan',
                loan=loan,
                error=msg,
            )
            continue

        new_data.append(our_loan)

    new_data.sort(key=lambda loan: loan.open_time)
    return new_data


def _post_process(before: Dict) -> Dict:
    """Poloniex uses datetimes so turn them into timestamps here"""
    after = before
    if('return' in after):
        if(isinstance(after['return'], list)):
            for x in range(0, len(after['return'])):
                if(isinstance(after['return'][x], dict)):
                    if('datetime' in after['return'][x] and
                       'timestamp' not in after['return'][x]):
                        after['return'][x]['timestamp'] = float(
                            createTimeStamp(after['return'][x]['datetime']),
                        )

    return after


class Poloniex(Exchange):

    def __init__(
            self,
            api_key: ApiKey,
            secret: ApiSecret,
            user_directory: FilePath,
            msg_aggregator: MessagesAggregator,
    ):
        super(Poloniex, self).__init__('poloniex', api_key, secret, user_directory)

        self.uri = 'https://poloniex.com/'
        self.public_uri = self.uri + 'public?command='
        self.session.headers.update({  # type: ignore
            'Key': self.api_key,
        })
        self.msg_aggregator = msg_aggregator

    def first_connection(self):
        if self.first_connection_made:
            return

        with self.lock:
            self.first_connection_made = True
        # Also need to do at least a single pass of the market watcher for the ticker
        self.market_watcher()

    def validate_api_key(self) -> Tuple[bool, str]:
        try:
            self.returnFeeInfo()
        except ValueError as e:
            error = str(e)
            if 'Invalid API key/secret pair' in error:
                return False, 'Provided API Key or secret is invalid'
            else:
                raise
        return True, ''

    def api_query(self, command: str, req: Optional[Dict] = None) -> Union[Dict, List]:
        result = retry_calls(
            times=5,
            location='poloniex',
            handle_429=False,
            backoff_in_seconds=0,
            method_name=command,
            function=self._api_query,
            # function's arguments
            command=command,
            req=req,
        )
        if 'error' in result:
            raise PoloniexError(
                'Poloniex query for "{}" returned error: {}'.format(
                    command,
                    result['error'],
                ))
        return result

    def api_query_dict(self, command: str, req: Optional[Dict] = None) -> Dict:
        result = self.api_query(command, req)
        assert isinstance(result, Dict)
        return result

    def api_query_list(self, command: str, req: Optional[Dict] = None) -> List:
        result = self.api_query(command, req)
        assert isinstance(result, List)
        return result

    def _api_query(self, command: str, req: Optional[Dict] = None) -> Union[Dict, List]:
        if req is None:
            req = {}

        if command == 'returnTicker' or command == 'returnCurrencies':
            log.debug(f'Querying poloniex for {command}')
            ret = self.session.get(self.public_uri + command)
            return rlk_jsonloads(ret.text)

        req['command'] = command
        with self.lock:
            # Protect this region with a lock since poloniex will reject
            # non-increasing nonces. So if two greenlets come in here at
            # the same time one of them will fail
            req['nonce'] = int(time.time() * 1000)
            post_data = str.encode(urlencode(req))

            sign = hmac.new(self.secret, post_data, hashlib.sha512).hexdigest()
            self.session.headers.update({'Sign': sign})

            log.debug(
                'Poloniex private API query',
                command=command,
                post_data=req,
            )
            ret = self.session.post('https://poloniex.com/tradingApi', req)

        if ret.status_code != 200:
            raise RemoteError(
                f'Poloniex query responded with error status code: {ret.status_code}'
                f' and text: {ret.text}',
            )

        try:
            if command == 'returnLendingHistory':
                return rlk_jsonloads_list(ret.text)
            else:
                result = rlk_jsonloads_dict(ret.text)
                return _post_process(result)
        except JSONDecodeError:
            raise RemoteError(f'Poloniex returned invalid JSON response: {ret.text}')

    def returnCurrencies(self) -> Dict:
        response = self.api_query_dict('returnCurrencies')
        return response

    def returnTicker(self) -> Dict:
        response = self.api_query_dict('returnTicker')
        return response

    def returnFeeInfo(self) -> Dict:
        response = self.api_query_dict('returnFeeInfo')
        return response

    def returnLendingHistory(
            self,
            start_ts: Optional[Timestamp] = None,
            end_ts: Optional[Timestamp] = None,
            limit: Optional[int] = None,
    ) -> List:
        """Default limit for this endpoint seems to be 500 when I tried.
        So to be sure all your loans are included put a very high limit per call
        and also check if the limit was reached after each call.

        Also maximum limit seems to be 12660
        """
        req: Dict[str, Union[int, Timestamp]] = dict()
        if start_ts is not None:
            req['start'] = start_ts
        if end_ts is not None:
            req['end'] = end_ts
        if limit is not None:
            req['limit'] = limit

        response = self.api_query_list('returnLendingHistory', req)
        return response

    @overload
    def returnTradeHistory(  # pylint: disable=unused-argument, no-self-use
            self,
            currencyPair: Literal['all'],
            start: Timestamp,
            end: Timestamp,
    ) -> Dict:
        ...

    @overload  # noqa: F811
    def returnTradeHistory(  # pylint: disable=unused-argument, no-self-use
            self,
            currencyPair: Union[TradePair, str],
            start: Timestamp,
            end: Timestamp,
    ) -> Union[Dict, List]:
        ...

    # TODO: As soon as a pyflakes release is made including
    # https://github.com/PyCQA/pyflakes/pull/435 then remove the noqa from here,
    # above and from other place in codebase where overload is used likethis
    def returnTradeHistory(  # noqa: F811
            self,
            currencyPair: Union[TradePair, str],
            start: Timestamp,
            end: Timestamp,
    ) -> Union[Dict, List]:
        """If `currencyPair` is all, then it returns a dictionary with each key
        being a pair and each value a list of trades. If `currencyPair` is a specific
        pair then a list is returned"""
        return self.api_query('returnTradeHistory', {
            "currencyPair": currencyPair,
            'start': start,
            'end': end,
            'limit': 10000,
        })

    def returnDepositsWithdrawals(
            self,
            start_ts: Timestamp,
            end_ts: Timestamp,
    ) -> Dict:
        response = self.api_query_dict(
            'returnDepositsWithdrawals',
            {'start': start_ts, 'end': end_ts},
        )
        return response

    def market_watcher(self):
        self.ticker = self.returnTicker()

    def main_logic(self):
        if not self.first_connection_made:
            return

        try:
            self.market_watcher()

        except PoloniexError as e:
            log.error('Poloniex error at main loop', error=str(e))
        except Exception as e:
            log.error(
                "\nException at main loop: {}\n{}\n".format(
                    str(e), traceback.format_exc()),
            )

    # ---- General exchanges interface ----
    @cache_response_timewise()
    def query_balances(self) -> Tuple[Optional[Dict[Asset, Dict[str, Any]]], str]:
        try:
            resp = self.api_query_dict('returnCompleteBalances', {"account": "all"})
        except (RemoteError, PoloniexError) as e:
            msg = (
                'Poloniex API request failed. Could not reach poloniex due '
                'to {}'.format(e)
            )
            log.error(msg)
            return None, msg

        balances = dict()
        for poloniex_asset, v in resp.items():
            available = FVal(v['available'])
            on_orders = FVal(v['onOrders'])
            if (available != FVal(0) or on_orders != FVal(0)):
                try:
                    asset = asset_from_poloniex(poloniex_asset)
                except UnsupportedAsset as e:
                    self.msg_aggregator.add_warning(
                        f'Found unsupported poloniex asset {e.asset_name}. '
                        f' Ignoring its balance query.',
                    )
                    continue
                except UnknownAsset as e:
                    self.msg_aggregator.add_warning(
                        f'Found unknown poloniex asset {e.asset_name}. '
                        f' Ignoring its balance query.',
                    )
                    continue

                entry = {}
                entry['amount'] = available + on_orders
                usd_price = Inquirer().find_usd_price(asset=asset)
                usd_value = entry['amount'] * usd_price
                entry['usd_value'] = usd_value
                balances[asset] = entry

                log.debug(
                    'Poloniex balance query',
                    sensitive_log=True,
                    currency=asset,
                    amount=entry['amount'],
                    usd_value=usd_value,
                )

        return balances, ''

    def query_trade_history(
            self,
            start_ts: Timestamp,
            end_ts: Timestamp,
            end_at_least_ts: Timestamp,
    ) -> Dict:
        with self.lock:
            cache = self.check_trades_cache_dict(start_ts, end_at_least_ts)
        if cache is not None:
            return cache

        result = self.returnTradeHistory(
            currencyPair='all',
            start=start_ts,
            end=end_ts,
        )

        results_length = 0
        for _, v in result.items():
            results_length += len(v)

        log.debug('Poloniex trade history query', results_num=results_length)

        if results_length >= 10000:
            raise ValueError(
                'Poloniex api has a 10k limit to trade history. Have not implemented'
                ' a solution for more than 10k trades at the moment',
            )

        with self.lock:
            self.update_trades_cache(result, start_ts, end_ts)
        return result

    def parseLoanCSV(self) -> List:
        """Parses (if existing) the lendingHistory.csv and returns the history in a list

        It can throw OSError, IOError if the file does not exist and csv.Error if
        the file is not proper CSV"""
        # the default filename, and should be (if at all) inside the data directory
        path = os.path.join(self.user_directory, "lendingHistory.csv")
        lending_history = list()
        with open(path, 'r') as csvfile:
            history = csv.reader(csvfile, delimiter=',', quotechar='|')
            next(history)  # skip header row
            for row in history:
                try:
                    lending_history.append({
                        'currency': asset_from_poloniex(row[0]),
                        'earned': FVal(row[6]),
                        'amount': FVal(row[2]),
                        'fee': FVal(row[5]),
                        'open': row[7],
                        'close': row[8],
                    })
                except UnsupportedAsset as e:
                    self.msg_aggregator.add_warning(
                        f'Found loan with asset {e.asset_name}. Ignoring it.',
                    )
                    continue

        return lending_history

    def query_loan_history(
            self,
            start_ts: Timestamp,
            end_ts: Timestamp,
            end_at_least_ts: Timestamp,
            from_csv: Optional[bool] = False,
    ) -> List:
        """
        WARNING: Querying from returnLendingHistory endpoint instead of reading from
        the CSV file can potentially  return unexpected/wrong results.

        That is because the `returnLendingHistory` endpoint has a hidden limit
        of 12660 results. In our code we use the limit of 12000 but poloniex may change
        the endpoint to have a lower limit at which case this code will break.

        To be safe compare results of both CSV and endpoint to make sure they agree!
        """
        try:
            if from_csv:
                return self.parseLoanCSV()
        except (OSError, IOError, csv.Error):
            pass

        with self.lock:
            # We know Loan history cache is a list
            cache = self.check_trades_cache_list(
                start_ts=start_ts,
                end_ts=end_at_least_ts,
                special_name='loan_history',
            )
        if cache is not None:
            return cache

        loans_query_return_limit = 12000
        result = self.returnLendingHistory(
            start_ts=start_ts,
            end_ts=end_ts,
            limit=loans_query_return_limit,
        )
        data = list(result)
        log.debug('Poloniex loan history query', results_num=len(data))

        # since I don't think we have any guarantees about order of results
        # using a set of loan ids is one way to make sure we get no duplicates
        # if poloniex can guarantee me that the order is going to be ascending/descending
        # per open/close time then this can be improved
        id_set = set()

        while len(result) == loans_query_return_limit:
            # Find earliest timestamp to re-query the next batch
            min_ts = end_ts
            for loan in result:
                ts = deserialize_timestamp_from_poloniex_date(loan['close'])
                min_ts = min(min_ts, ts)
                id_set.add(loan['id'])

            result = self.returnLendingHistory(
                start_ts=start_ts,
                end_ts=min_ts,
                limit=loans_query_return_limit,
            )
            log.debug('Poloniex loan history query', results_num=len(result))
            for loan in result:
                if loan['id'] not in id_set:
                    data.append(loan)

        with self.lock:
            self.update_trades_cache(data, start_ts, end_ts, special_name='loan_history')
        return data

    def query_deposits_withdrawals(
            self,
            start_ts: Timestamp,
            end_ts: Timestamp,
            end_at_least_ts: Timestamp,
    ) -> List[AssetMovement]:
        with self.lock:
            cache = self.check_trades_cache_dict(
                start_ts,
                end_at_least_ts,
                special_name='deposits_withdrawals',
            )
        if cache is None:
            result = self.returnDepositsWithdrawals(start_ts, end_ts)
            with self.lock:
                self.update_trades_cache(
                    result,
                    start_ts,
                    end_ts,
                    special_name='deposits_withdrawals',
                )
        else:
            result = cache

        log.debug(
            'Poloniex deposits/withdrawal query',
            results_num=len(result['withdrawals']) + len(result['deposits']),
        )

        movements = list()
        for withdrawal in result['withdrawals']:
            try:
                movements.append(AssetMovement(
                    exchange='poloniex',
                    category='withdrawal',
                    timestamp=deserialize_timestamp(withdrawal['timestamp']),
                    asset=asset_from_poloniex(withdrawal['currency']),
                    amount=deserialize_asset_amount(withdrawal['amount']),
                    fee=deserialize_fee(withdrawal['fee']),
                ))
            except UnsupportedAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found withdrawal of unsupported poloniex asset {e.asset_name}. Ignoring it.',
                )
                continue
            except UnknownAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found withdrawal of unknown poloniex asset {e.asset_name}. Ignoring it.',
                )
                continue
            except DeserializationError as e:
                log.error(
                    f'Unexpected data encountered during deserialization of poloniex '
                    f'withdrawal: {withdrawal}. Error was: {str(e)}',
                )
                self.msg_aggregator.add_warning(
                    f'Unexpected data encountered during deserialization of a poloniex '
                    f'withdrawal. Check logs for details and open a bug report.',
                )

        for deposit in result['deposits']:
            try:
                movements.append(AssetMovement(
                    exchange='poloniex',
                    category='deposit',
                    timestamp=deserialize_timestamp(deposit['timestamp']),
                    asset=asset_from_poloniex(deposit['currency']),
                    amount=deserialize_asset_amount(FVal(deposit['amount'])),
                    fee=Fee(ZERO),
                ))
            except UnsupportedAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found deposit of unsupported poloniex asset {e.asset_name}. Ignoring it.',
                )
                continue
            except UnknownAsset as e:
                self.msg_aggregator.add_warning(
                    f'Found deposit of unknown poloniex asset {e.asset_name}. Ignoring it.',
                )
                continue
            except DeserializationError as e:
                log.error(
                    f'Unexpected data encountered during deserialization of poloniex '
                    f'deposit: {deposit}. Error was: {str(e)}',
                )
                self.msg_aggregator.add_warning(
                    f'Unexpected data encountered during deserialization of a poloniex '
                    f'deposit. Check logs for details and open a bug report.',
                )

        return movements
