import pytest

from rotkehlchen.constants.assets import A_BTC
from rotkehlchen.fval import FVal
from rotkehlchen.order_formatting import MarginPosition
from rotkehlchen.tests.utils.accounting import accounting_history_process
from rotkehlchen.tests.utils.history import prices
from rotkehlchen.typing import Timestamp

DUMMY_HASH = '0x0'
DUMMY_ADDRESS = '0x0'

trades_history = [
    {
        'timestamp': 1446979735,  # 08/11/2015
        'pair': 'BTC_EUR',
        'trade_type': 'buy',
        'rate': 268.678317859,
        'fee': 0,
        'fee_currency': 'BTC',
        'amount': 5,
        'location': 'external',
    }, {
        'timestamp': 1446979735,  # 08/11/2015
        'pair': 'ETH_EUR',
        'trade_type': 'buy',
        'rate': 0.2315893,
        'fee': 0,
        'fee_currency': 'ETH',
        'amount': 1450,
        'location': 'external',
    }, {
        'timestamp': 1467378304,  # 31/06/2016
        'pair': 'BTC_EUR',  # cryptocompare hourly BTC/EUR price 612.45
        'trade_type': 'sell',
        'rate': 612.45,
        'fee': '0.15',
        'fee_currency': 'EUR',
        'amount': 2.5,
        'location': 'kraken',
    }, {
        'timestamp': 1473505138,  # 10/09/2016
        'pair': 'ETH_BTC',  # cryptocompare hourly ETH/EUR price: 10.365
        'trade_type': 'buy',  # Buy ETH with BTC -- taxable (within 1 year)
        'rate': 0.01858275,  # cryptocompare hourly BTC/EUR price: 556.435
        'fee': 0.06999999999999999,
        'fee_currency': 'ETH',
        'amount': 50.0,
        'location': 'poloniex',
    }, {
        'timestamp': 1475042230,  # 28/09/2016
        'pair': 'ETH_BTC',  # cryptocompare hourly ETH/EUR price: 11.925
        'trade_type': 'sell',  # Sell ETH for BTC -- taxable (within 1 year)
        'rate': 0.022165,  # cryptocompare hourly BTC/EUR price: 537.805
        'fee': 0.001,            # asset. In this case 'ETH'. So BTC buy rate is:
        'fee_currency': 'ETH',   # (1 / 0.022165) * 11.925
        'amount': 25,
        'location': 'poloniex',
    }, {
        'timestamp': 1476536704,  # 15/10/2016
        'pair': 'ETH_BTC',  # cryptocompare hourly ETH/EUR price: 10.775
        'trade_type': 'sell',  # Sell ETH for BTC -- taxable (within 1 year)
        'rate': 0.018355,  # cryptocompare hourly BTC/EUR price: 585.96
        'fee': 0.01,             # asset.In this case 'ETH'. So BTC buy rate is:
        'fee_currency': 'ETH',   # (1 / 0.018355) * 10.775
        'amount': 180.0,
        'location': 'poloniex',
    }, {
        'timestamp': 1479200704,  # 15/11/2016
        'pair': 'DASH_BTC',  # cryptocompare hourly DASH/EUR price: 8.9456
        'trade_type': 'buy',  # Buy DASH with BTC -- non taxable (after 1 year)
        'rate': 0.0134,  # cryptocompare hourly BTC/EUR price: 667.185
        'fee': 0.00082871175,
        'fee_currency': 'BTC',
        'amount': 40,
        'location': 'poloniex',
    }, {  # 0.00146445 * 723.505 + 0.005 * 8.104679571509114828039 = 1.10006029511
        'timestamp': 1480683904,  # 02/12/2016
        'pair': 'DASH_BTC',  # cryptocompare hourly DASH/EUR price: 8.104679571509114828039
        'trade_type': 'settlement_sell',  # settlement sell DASH for BTC -- taxable (within 1 year)
        'rate': 0.011265,  # cryptocompare hourly BTC/EUR price: 723.505
        'fee': 0.005,
        'fee_currency': 'DASH',
        'amount': 0.13,
        'location': 'poloniex',
    }, {  # 129.2517-0.01 - ((0.536+0.00082871175)*10/40)*667.185 = 39.7006839878
        'timestamp': 1483520704,  # 04/01/2017
        'pair': 'DASH_EUR',  # cryptocompare hourly DASH/EUR price: 12.92517
        'trade_type': 'sell',  # Sell DASH for EUR -- taxable (within 1 year)
        'rate': 12.92517,
        'fee': 0.01,
        'fee_currency': 'EUR',
        'amount': 10,
        'location': 'kraken',
    }, {  # 0.0079275 * 810.49 + 0.15 * 12.4625608386372145 = 8.29454360079
        'timestamp': 1484629704,  # 17/01/2017
        'pair': 'DASH_BTC',  # DASH/EUR price: 12.4625608386372145
        'trade_type': 'settlement_buy',  # Buy DASH with BTC to settle. Essentially BTC loss
        'rate': 0.015855,  # BTC/EUR price: 810.49
        'fee': 0.15,
        'fee_currency': 'DASH',
        'amount': 0.5,
        'location': 'poloniex',
    }, {  # 0.00244725 * 942.78 + 0.01*15.36169816590634019 = 2.46083533666
        'timestamp': 1486299904,  # 05/02/2017
        'pair': 'DASH_BTC',  # cryptocompare hourly DASH/EUR price: 15.36169816590634019
        'trade_type': 'settlement_sell',  # settlement sell DASH for BTC -- taxable (within 1 year)
        'rate': 0.016315,  # cryptocompare hourly BTC/EUR price: 942.78
        'fee': 0.01,
        'fee_currency': 'DASH',
        'amount': 0.15,
        'location': 'poloniex',
    }, {  # Partly taxable sell.
        'timestamp': 1488373504,  # 29/02/2017
        'pair': 'BTC_EUR',  # cryptocompare hourly DASH/EUR price: 15.36169816590634019
        'trade_type': 'sell',  # sell BTC for EUR -- partly taxable (within 1 year)
        'rate': 1146.22,  # cryptocompare hourly BTC/EUR price: 1146.22
        'fee': 0.01,
        'fee_currency': 'EUR',
        'amount': 2,
        'location': 'kraken',
    },
]

loans_list = [
    {  # before query period -- (0.0002 - 0.000001) * 10.785 = 2.146215e-3
        'id': 1,  # we don't read that in Rotkehlchen
        'rate': '0.001',  # we don't read that in Rotkehlchen
        'duration': '0.001',  # we don't read that in Rotkehlchen
        'interest': '0.00000005',  # we don't read that in Rotkehlchen
        'open': '2016-05-17 10:36:32',
        'close': '2016-05-17 18:03:54',
        'currency': 'ETH',  # cryptocompare hourly ETH/EUR: 10.785
        'fee': '0.000001',
        'earned': '0.0002',
        'amount': '2',
    }, {  # (0.002-0.0001) * 10.9698996 = 0.02084280924
        'id': 2,  # we don't read that in Rotkehlchen
        'rate': '0.001',  # we don't read that in Rotkehlchen
        'duration': '0.001',  # we don't read that in Rotkehlchen
        'interest': '0.00000005',  # we don't read that in Rotkehlchen
        'open': '2017-01-02 01:36:32',
        'close': '2017-01-02 10:05:04',
        'currency': 'DASH',  # cryptocompare hourly DASH/EUR: 10.9698996
        'fee': '0.0001',
        'earned': '0.002',
        'amount': '2',
    }, {  # (0.003-0.00015)*13.22106438 = 0.037680033483
        'id': 3,  # we don't read that in Rotkehlchen
        'rate': '0.001',  # we don't read that in Rotkehlchen
        'duration': '0.001',  # we don't read that in Rotkehlchen
        'interest': '0.00000005',  # we don't read that in Rotkehlchen
        'open': '2017-01-24 06:05:04',
        'close': '2017-01-24 10:05:04',
        'currency': 'DASH',  # cryptocompare hourly DASH/EUR: 13.22106438
        'fee': '0.00015',
        'earned': '0.003',
        'amount': '2',
    }, {  # (0.0035-0.00011)*15.73995672 = 0.0533584532808
        'id': 4,  # we don't read that in Rotkehlchen
        'rate': '0.001',  # we don't read that in Rotkehlchen
        'duration': '0.001',  # we don't read that in Rotkehlchen
        'interest': '0.00000005',  # we don't read that in Rotkehlchen
        'open': '2017-02-13 19:07:01',
        'close': '2017-02-13 23:05:04',
        'currency': 'DASH',  # cryptocompare hourly DASH/EUR: 15.73995672
        'fee': '0.00011',
        'earned': '0.0035',
        'amount': '2',
    }, {  # outside query period -- should not matter
        'id': 5,  # we don't read that in Rotkehlchen
        'rate': '0.001',  # we don't read that in Rotkehlchen
        'duration': '0.001',  # we don't read that in Rotkehlchen
        'interest': '0.00000005',  # we don't read that in Rotkehlchen
        'open': '2018-03-03 19:05:04',
        'close': '2018-03-03 23:05:04',
        'currency': 'DASH',  # cryptocompare hourly DASH/EUR: 475.565
        'fee': '0.0001',
        'earned': '0.0025',
        'amount': '2',
    },
]

asset_movements_list = [
    {  # before query period -- 8.915 * 0.001 = 8.915e-3
        'exchange': 'kraken',
        'category': 'withdrawal',
        'timestamp': 1479510304,  # 18/11/2016,
        'asset': 'ETH',  # cryptocompare hourly ETH/EUR: 8.915
        'amount': 95,
        'fee': 0.001,
    }, {  # 0.0087*52.885 = 0.4600995
        'exchange': 'kraken',
        'category': 'withdrawal',
        'timestamp': 1493291104,  # 27/04/2017,
        'asset': 'ETH',  # cryptocompare hourly ETH/EUR: 52.885
        'amount': 125,
        'fee': 0.0087,
    }, {  # deposit have no effect
        'exchange': 'kraken',
        'category': 'deposit',
        'timestamp': 1493636704,  # 01/05/2017,
        'asset': 'EUR',
        'amount': 750,
        'fee': 0,
    }, {  # 0.00029*1964.685 = 0.56975865
        'exchange': 'poloniex',
        'category': 'withdrawal',
        'timestamp': 1495969504,  # 28/05/2017,
        'asset': 'BTC',  # cryptocompare hourly BTC/EUR: 1964.685
        'amount': 8.5,
        'fee': 0.00029,
    }, {  # 0.0078*173.77 = 1.355406
        'exchange': 'poloniex',
        'category': 'withdrawal',
        'timestamp': 1502715904,  # 14/08/2017,
        'asset': 'DASH',  # cryptocompare hourly DASH/EUR: 173.77
        'amount': 20,
        'fee': 0.0078,
    }, {  # after query period -- should not matter
        'exchange': 'bittrex',
        'category': 'withdrawal',
        'timestamp': 1517663104,  # 03/02/2018,
        'asset': 'ETH',
        'amount': 120,
        'fee': 0.001,
    },
]

eth_tx_list = [
    {  # before query period: ((2000000000 * 25000000) / (10 ** 18)) * 9.185 = 0.45925
        'timestamp': 1463184190,  # 14/05/2016
        'block_number': 1512689,  # cryptocompare hourtly ETH/EUR: 9.186
        'hash': DUMMY_HASH,
        'from_address': DUMMY_ADDRESS,
        'to_address': DUMMY_ADDRESS,
        'value': 12323,
        'gas': 5000000,
        'gas_price': 2000000000,
        'gas_used': 25000000,
    }, {  # ((2000000000 * 1000000) / (10 ** 18)) * 47.5 = 0.095
        'timestamp': 1491062063,  # 01/04/2017
        'block_number': 3458409,  # cryptocompare hourly ETH/EUR: 47.5
        'hash': DUMMY_HASH,
        'from_address': DUMMY_ADDRESS,
        'to_address': DUMMY_ADDRESS,
        'value': 12323,
        'gas': 5000000,
        'gas_price': 2000000000,
        'gas_used': 1000000,
    }, {  # ((2200000000 * 2500000) / (10 ** 18)) * 393.955 = 2.1667525
        'timestamp': 1511626623,  # 25/11/2017
        'block_number': 4620323,  # cryptocompare hourly ETH/EUR: 393.955
        'hash': DUMMY_HASH,
        'from_address': DUMMY_ADDRESS,
        'to_address': DUMMY_ADDRESS,
        'value': 12323,
        'gas': 5000000,
        'gas_price': 2200000000,
        'gas_used': 2500000,
    }, {  # after query period -- should not matter
        'timestamp': 1523399409,  # 10/04/2018
        'block_number': 5417790,
        'hash': DUMMY_HASH,
        'from_address': DUMMY_ADDRESS,
        'to_address': DUMMY_ADDRESS,
        'value': 12323,
        'gas': 5000000,
        'gas_price': 2100000000,
        'gas_used': 1900000,
    },
]

margin_history = [
    MarginPosition(  # before query period -- BTC/EUR: 422.90
        exchange='poloniex',
        open_time=Timestamp(1463184190),  # 14/05/2016
        close_time=Timestamp(1464393600),  # 28/05/2016
        profit_loss=FVal(0.05),
        pl_currency=A_BTC,
        notes='margin1',
    ), MarginPosition(  # before query period -- BTC/EUR: 542.87
        exchange='poloniex',
        open_time=Timestamp(1472428800),  # 29/08/2016
        close_time=Timestamp(1473897600),  # 15/09/2016
        profit_loss=FVal('-0.042'),
        pl_currency=A_BTC,
        notes='margin2',
    ), MarginPosition(  # BTC/EUR: 1039.935
        exchange='poloniex',
        open_time=Timestamp(1489276800),  # 12/03/2017
        close_time=Timestamp(1491177600),  # 03/04/2017
        profit_loss=FVal('-0.042'),
        pl_currency=A_BTC,
        notes='margin3',
    ), MarginPosition(  # BTC/EUR: 2244.255
        exchange='poloniex',
        open_time=Timestamp(1496534400),  # 04/06/2017
        close_time=Timestamp(1498694400),  # 29/06/2017
        profit_loss=FVal(0.124),
        pl_currency=A_BTC,
        notes='margin4',
    )]


@pytest.mark.parametrize('mocked_price_queries', [prices])
def test_end_to_end_tax_report(accountant):
    result = accounting_history_process(
        accountant=accountant,
        start_ts=0,
        end_ts=1514764799,  # 31/12/2017
        history_list=trades_history,
        loans_list=loans_list,
        asset_movements_list=asset_movements_list,
        eth_transaction_list=eth_tx_list,
        margin_list=margin_history,
    )
    result = result['overview']
    # Make sure that the "started_processing_timestamp" is the ts of the first
    # action in history
    assert accountant.started_processing_timestamp == 1446979735
    # Make sure that the "currently_processing_timestamp" is the ts of the last
    # action seen in history before end_ts
    assert accountant.currently_processing_timestamp == 1511626623
    general_trade_pl = FVal(result['general_trade_profit_loss'])
    assert general_trade_pl.is_close('5032.30394444')
    taxable_trade_pl = FVal(result['taxable_trade_profit_loss'])
    assert taxable_trade_pl.is_close('3954.94067484')
    loan_profit = FVal(result['loan_profit'])
    assert loan_profit.is_close('0.114027511004')
    settlement_losses = FVal(result['settlement_losses'])
    assert settlement_losses.is_close('11.8554392326')
    asset_movement_fees = FVal(result['asset_movement_fees'])
    assert asset_movement_fees.is_close('2.39417915')
    ethereum_transaction_gas_costs = FVal(result['ethereum_transaction_gas_costs'])
    assert ethereum_transaction_gas_costs.is_close('2.7210025')
    margin_pl = FVal(result['margin_positions_profit_loss'])
    assert margin_pl.is_close('232.95481')
    expected_total_taxable_pl = (
        taxable_trade_pl +
        margin_pl +
        loan_profit -
        settlement_losses -
        asset_movement_fees -
        ethereum_transaction_gas_costs
    )
    total_taxable_pl = FVal(result['total_taxable_profit_loss'])
    assert expected_total_taxable_pl.is_close(total_taxable_pl)
    expected_total_pl = (
        general_trade_pl +
        margin_pl +
        loan_profit -
        settlement_losses -
        asset_movement_fees -
        ethereum_transaction_gas_costs
    )
    total_pl = FVal(result['total_profit_loss'])
    assert expected_total_pl.is_close(total_pl)


@pytest.mark.parametrize('mocked_price_queries', [prices])
def test_end_to_end_tax_report_in_period(accountant):
    result = accounting_history_process(
        accountant=accountant,
        start_ts=1483228800,  # 01/01/2017
        end_ts=1514764799,  # 31/12/2017
        history_list=trades_history,
        loans_list=loans_list,
        asset_movements_list=asset_movements_list,
        eth_transaction_list=eth_tx_list,
        margin_list=margin_history,
    )
    # Make sure that the "started_processing_timestamp" is the ts of the first
    # action in history
    assert accountant.started_processing_timestamp == 1446979735
    # Make sure that the "currently_processing_timestamp" is the ts of the last
    # action seen in history before end_ts
    assert accountant.currently_processing_timestamp == 1511626623
    result = result['overview']
    general_trade_pl = FVal(result['general_trade_profit_loss'])
    assert general_trade_pl.is_close('1506.96912912')
    taxable_trade_pl = FVal(result['taxable_trade_profit_loss'])
    assert taxable_trade_pl.is_close('642.652537097')
    loan_profit = FVal(result['loan_profit'])
    assert loan_profit.is_close('0.111881296004')
    settlement_losses = FVal(result['settlement_losses'])
    assert settlement_losses.is_close('10.7553789375')
    asset_movement_fees = FVal(result['asset_movement_fees'])
    assert asset_movement_fees.is_close('2.38526415')
    ethereum_transaction_gas_costs = FVal(result['ethereum_transaction_gas_costs'])
    assert ethereum_transaction_gas_costs.is_close('2.2617525')
    margin_pl = FVal(result['margin_positions_profit_loss'])
    assert margin_pl.is_close('234.61035')
    expected_total_taxable_pl = (
        taxable_trade_pl +
        margin_pl +
        loan_profit -
        settlement_losses -
        asset_movement_fees -
        ethereum_transaction_gas_costs
    )
    total_taxable_pl = FVal(result['total_taxable_profit_loss'])
    assert expected_total_taxable_pl.is_close(total_taxable_pl)
    expected_total_pl = (
        general_trade_pl +
        margin_pl +
        loan_profit -
        settlement_losses -
        asset_movement_fees -
        ethereum_transaction_gas_costs
    )
    total_pl = FVal(result['total_profit_loss'])
    assert expected_total_pl.is_close(total_pl)


# Calculation notes for all events in this end to end test
# --> 1467378304 (taxable)

# Sell BTC for EUR

# gain: 612.45*2.5 - 0.15 = 1530.975

# bought_cost: 671.695794648

# profit: 1530.975 - 671.695794648 = 859.279205352


# --> 1473505138 (taxable)

# Buy ETH with BTC -- Sell BTC for EUR

# gain: 0.9291375*556.435 - 0.06999999999999999*10.365
# gain: 516.279074813

# bought_cost: 0.9291375 *268.678317859
# bought_cost: 249.63910056

# profit: 516.279074813 - 249.63910056
# profit: 266.639974253


# --> 1475042230 (taxable)

# Sell ETH for BTC

# gain: 0.554125 * 537.805 - 0.001 * 11.925
# gain: 297.999270625

# bought_cost: 25 * 0.2315893
# bought_cost: 5.7897325

# profit: 297.999270625 - 5.7897325 = 292.209538125

# --> 1476536704

# Sell ETH for BTC

# gain: 3.3039 * 585.96 - 0.01*10.775
# gain: 1935.845494

# bought_cost: 180 * 0.2315893
# bought_cost: 41.686074

# profit: 1935.845494 - 41.686074
# profit: 1894.15942

# --> 1479200704  (sell is non taxable -- after 1 year)

# Buy Dash with BTC -- Sell BTC for EUR

# gain: (0.536 - 0.00082871175)* 667.185
# gain: 357.058255951

# part_from_1st_btc_buy =  2.5-0.5136 = 1.9864

# bought_cost = 0.536 * 268.678317859 = 144.011578372

# profit: 357.058255951 - 144.011578372
# profit: 213.046677579

# --> 1483520704  (taxable)

# Sell DASH for EUR

# gain: 129.2517 - 0.01 = 129.2417

# bought_cost: (0.536 + 0.00082871175)*667.185*(10/40)
# bought_cost: 89.5410160122

# profit: 129.2417 - 89.5410160122 = 39.7006839878

# --> 1484629704 (taxable)

# Buy Dash with BTC for settlement. BTC Loss

# loss in EUR: 0.0079275 * 810.49 + 0.15 * 12.4625608386372145 = 8.29454360079
# loss in BTC: 0.0079275

# --> 1488373504 (partly taxable)


# Sell 2 BTC for EUR

# gain: 2292.44 - 0.01 = 2292.43

# taxfree_bought_cost = 0.984935 * 268.678317859 = 264.630679

# part_from_1st_btc_buy: 5-2.5-0.9291375-0.536-0.0079275  = 0.984935
# part_from_1nd_margin_profit: 0.05
# part_from_2nd_btc_buy: 0.554125
# part_from_3rd_btc_buy: 2 - 0.984935 - 0.554125 - 0.05 = 0.41094

# taxable_bought_cost = 0.05 * 422.90 + 0.554125 * ((1 / 0.022165) * 11.925) + 0.001 *11.925 +
# 0.41094 * ((1 / 0.018355) * 10.775) + (0.41094/3.3039) * 0.01 * 10.775
# taxable_bought_cost = 560.530875871

# general_pl = 2292.43 - (560.530875871 + 264.630679)
# general_pl = 1467.26844513

# taxable_pl = ((0.05+0.554125+0.41094)/2)*2292.43 - 560.530875871
# taxable_pl = 602.951853109


# ---> BTC movements appendix
# 1446979735 - 1st buy: 5
# 1464393600 - 1st margin: 0.05
# 1467378304 - 1st sell: 2.5
# 1473505138 - 2nd sell: 0.9291375
# 1473897600 - 2nd margin: -0.042
# 1475042230 - 2nd buy: 0.554125
# 1476536704 - 3rd buy: 3.3039
# 1479200704 - 3rd sell: 0.536
# 1480683904 - 4th buy: 0.00146445
# 1484629704 - 4th sell: 0.0079275
# 1486299904 - 5th buy: 0.00244725

@pytest.mark.parametrize('use_clean_caching_directory', [True])
@pytest.mark.parametrize('should_mock_price_queries', [False])
def test_cryptocompare_asset_and_price_not_found_in_history_sprocessing(accountant):
    """
    Make sure that in history processing if no price is found for a trade it's skipped
    and an error is logged. Same for price query of an unknown asset.

    Regression for https://github.com/rotkehlchenio/rotkehlchen/issues/432
    Superset test for test_cryptocompare::test_cryptocompare_histohour_query_old_ts_xcp
    When we add multiple price data sources and this test does not use cryptocompare
    the other test should be unskipped.
    """
    bad_trades = [{
        'timestamp': 1392685761,  # Issue 432, XCP trade at 1392685761 has no known price
        'pair': 'XCP_BTC',
        'trade_type': 'buy',
        'rate': '0.100',
        'fee': '0.15',
        'fee_currency': 'XCP',
        'amount': 2.5,
        'location': 'kraken',
    }, {
        'timestamp': 1492685761,
        'pair': 'EXC_BTC',
        'trade_type': 'buy',
        'rate': '0.100',
        'fee': '0.15',
        'fee_currency': 'EXC',
        'amount': 2.5,
        'location': 'kraken',
    }]
    result = accounting_history_process(
        accountant=accountant,
        start_ts=0,
        end_ts=1514764799,  # 31/12/2017
        history_list=bad_trades,
        loans_list=[],
        asset_movements_list=[],
        eth_transaction_list=[],
        margin_list=[],
    )
    result = result['overview']
    errors = accountant.msg_aggregator.consume_errors()
    assert len(errors) == 2
    assert 'due to inability to find a price at that point in time' in errors[0]
    assert 'due to an asset unknown to cryptocompare being involved' in errors[1]
    assert FVal(result['total_profit_loss']) == FVal('0')
