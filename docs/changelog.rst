=========
Changelog
=========

* :feature:`-` Added support for the following tokens

  - `Contentos <https://coinmarketcap.com/currencies/contentos/>`__

* :release:`1.0.1 <2019-08-02>`
* :feature:`425` Users can now provide arguments to the backend via a config file. For more information check the `docs <https://rotkehlchen.readthedocs.io/en/latest/usage_guide.html#set-the-backend-s-arguments`__. 
* :feature:`-` Added support for the following tokens

  - `Luna Coin <https://coinmarketcap.com/currencies/luna-coin/>`__
  - `Luna Terra <https://coinmarketcap.com/currencies/terra/>`__
  - `Spin Protocol <https://coinmarketcap.com/currencies/spin-protocol/>`__
  - `Blockcloud <https://coinmarketcap.com/currencies/blockcloud/>`__
  - `Bloc.Money <https://coinmarketcap.com/currencies/bloc-money/>`__
  - `Chromia  <https://coinmarketcap.com/currencies/chromia/>`__

* :feature:`428` Better handle unexpected data from external sources.
* :bug:`76` Handle poloniex queries returning null for the fee field.
* :bug:`432` If historical price for a trade is not found gracefully skip the trade. Also handle cryptocompare query edge case.
* :bug:`429` Properly handle 429 http response from blockchain.info by backing off by the suggested number of seconds and then trying again.


* :release:`1.0.0 <2019-07-22>`
* :bug:`420` There are no more negative percentages at tax report generation progress
* :bug:`392` Revisiting usersettings properly updates per account tables if an account has been deleted before.
* :bug:`325` Tracking accounts/tokens in user settings will now be immediately reflected on the dashboard.
* :bug:`368` Fixes broken navigation after visiting Statistics page.
* :bug:`361` Rotkehlchen no longer misses the last trade when processing history inside a timerange.
* :bug:`349` Copy paste should now work on OSX.
* :feature:`332` Add notifications area for actionable warnings/errors.
* :feature:`350` Add support for remote ethereum nodes and not just local ones.
* :feature:`329` Maintain a list of supported assets and converters from/to each exchange or service.
* :feature:`194` Add setting for date display format.
* :bug:`334` Handle too many requests error for the exchangerates api.
* :bug:`323` Properly display usd value For JPY and some other assets in kraken where XXBT is the quote asset.
* :bug:`320` The user settings pane is now always responsive, even when loaded a second time.
* :feature:`313` Premium feature: The statistic pane now has two different graphs to explore the distribution of value of the user. One shows the distribution of the total net value across different locations and the other across all assets the user holds.
* :feature:`312` Premium feature: The statistic pane now has a graph where users can check how any asset's amount and total usd value progresses over time.
* :bug:`314` Exchangerates api is now queried with priority and as such there are no more delays at the startup of the application due to unresponsive FOREX api calls.
* :feature:`272` Added a statistics pane. Premium users can now see a graph of their net value over time there.
* :bug:`299` IOTA historical price queries now work properly.
* :bug:`288` After a user re-login querying fiat prices will no longer throw exceptions.
* :bug:`273` Fallback to fetching NANO Price using XRB (Raiblocks) symbol before the rebranding.
* :bug:`283` OTC Trades table is now properly rendered again
* :feature:`268` Version name is now included in rotkehlchen binaries and other artifacts.

* :release:`0.6.0 <2019-01-21>`
* :feature:`92` Cache and have multiple APIs to query for fiat price queries.
* :feature:`222` Add a progress indicator during the tax report generation.
* :bug:`134` When rotkehlchen makes too many requests to Binance and gets a 429 response it now backs off and waits a bit.
* :bug:`241` When incurring margin trade loss the lost asset's available amount is now also reduced.
* :bug:`240` Poloniex settlement buys now incur the correct amount of BTC loss when processed.
* :bug:`218` Tax report details in the UI should no longer show NaN values in some columns.
* :bug:`231` Selling an asset that will fork, before it does now also reduces the forked asset amount.
* :bug:`232` Multiple rotkehlchen users will no longer share same cache files.
* :feature:`229` Rotkehlchen can now work and migrate to sqlcipher v4.
* :bug:`206` Fixes an error when adding a bitcoin account for the first time.
* :bug:`209` Fixes error during login due to invalid date being saved.
* :bug:`223` Fix error in profit/loss calculation due to bugs in the search of the FIFO queue of buy events.
* :feature:`221` Rotkehlchen is now shielded against incosistencies of cryptocompare FIAT data.
* :bug:`219` Poloniex BTC settlement loss calculation is now correct.
* :bug:`217` Tax report CSV exports should now agree with the app report.
* :bug:`211` Handle the BCHSV fork in Kraken properly.

* :release:`0.5.0 <2018-11-10>`
* :bug:`201` Having ICN in Kraken from 31/10 to 31/11 2018 will not lead rotkehlchen to crash.
* :feature:`186` Pressing Enter at signin/create new account and other popups will submit them just like clicking the form button.
* :bug:`197` Rotkehlchen no longer crashes at restart if a "No" tax_free_period is given
* :bug:`185` Ethereum node connection indicator should always properly indicate the connection status to the underlying ethereum node
* :bug:`184` If Rotkehlchen brand name in top left is clicked, open browser to rotkehlchen.io instead of showing the sign-in popup
* :bug:`187` Exchange balance tables no longer become unresponsive if visited multiple times.
* :feature:`178` New logout api call. Users can now logout of a rotkehlchen session.
* :bug:`181` Take 0 net balance into account when doing balance queries and not crash.
* :bug:`156` Overflow should now scroll completely and properly on mac.
* :feature:`138` Add an option to allow for anonymizing of all sensitive rotkehlchen logs.
* :feature:`132` Added a UI widget showing if rotkehlchen is connected to an ethereum node
* :bug:`173` Price querying for IOTA should now work properly with cryptocompare

* :release:`0.4.0 <2018-09-23>`
* :feature:`144` Rotkehlchen now starts fully supporting Bitmex and allows querying Bitmex history for tax calculations.
* :bug:`163` Properly handle errors in the tax report calculation and in other asynchronous tasks.
* :bug:`155` Check if the local ethereum node is synced before querying balances from it.
* :feature:`153` Add a ``version`` command to display the rotkehlchen version.
* :bug:`159` Gracefully exit if an invalid argument is provided.
* :bug:`151` If an asset stored at Bittrex does not have a BTC market rotkehlchen no longer crashes.
* :feature:`148` Add icons for all tokens to the UI.
* :feature:`74` Add experimental support for Bitmex. Supporting only simple balance query for now.
* :bug:`135` Fix bug in converting binance sell trades to the common rotkehlchen format
* :bug:`140` Don't log an error if the manual margin file is not found

* :release:`0.3.2 <2018-08-25>`
* :feature:`95` Add a UI widget to display the last time the balance data was saved in the DB.
* :bug:`126` Refuse to generate a new tax report if one is in progress and also clean previous report before generating a new one.
* :bug:`123` Return USD as default main currency if DB is new
* :bug:`101` Catch the web3 exception if using a local client with an out of sync chain and report a proper error in the UI
* :bug:`86` Fixed race condition at startup that could result in the banks balance displaying as NaN.
* :bug:`103` After removing an exchange's API key the new api key/secret input form is now properly re-enabled
* :bug:`99` Show proper error if kraken or binance api key validation fails due to an invalid key having been provided.

* :release:`0.3.1 <2018-06-25>`
* :bug:`96` Periodic balance data storage should now also work from the UI.

* :release:`0.3.0 <2018-06-24>`
* :feature:`90` Add configuration option for it and periodically save balances data in the database
* :bug:`91` Provide more accurate name for the setting for the date from which historical data starts
* :bug:`89` Many typing bugs were found and fixed
* :bug:`83` Fix a bug that did not allow adding or removing ethereum tokens from the tracker
* :feature:`79` Do not crash with exception if an exchange is unresponsive, but instead warn the user.
* :bug:`77` Fix bug caused by reading `taxfree_after_period` from the database

* :release:`0.2.2 <2018-06-05>`
* :bug:`73` Fixer.io api switched to be subscription based and its endpoints are now locked, so we switch to a different currency converter api.
* :bug:`68` All kraken pairs should now work properly. Users who hold XRP, ZEC, USD, GP, CAD, JPY, DASH, EOSD and USDT in kraken will no longer have any problems.

* :release:`0.2.1 <2018-05-26>`
* :bug:`66` Persist all eth accounts in the database as checksummed. Upgrade all existing DB accounts.
* :bug:`63` Unlocking a user account for an application is no longer slow if you have lots of historical price cache files.
* :bug:`61` Overcome etherscan's limit of 20 accounts per query by splitting the accounts list

* :release:`0.2.0 <2018-05-13>`
* :feature:`51` Add customization for the period of time after which trades are tax free.
* :bug:`50` rotkehlchen --help now works again
* :feature:`45` Add option to customize including crypto to crypto trades.
* :feature:`42` Move the accounting settings to their own page.

* :release:`0.1.1 <2018-04-27>`
* :bug:`37` Fix a bug where adding an ethereum account was throwing an exception in the UI.

* :release:`0.1.0 <2018-04-23>`
