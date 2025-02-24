from functools import total_ordering
from typing import Any, Optional

from dataclasses import dataclass, field

from rotkehlchen.assets.resolver import AssetResolver
from rotkehlchen.constants.cryptocompare import WORLD_TO_CRYPTOCOMPARE
from rotkehlchen.errors import UnknownAsset, UnsupportedAsset
from rotkehlchen.typing import AssetType, ChecksumEthAddress, Timestamp

WORLD_TO_BITTREX = {
    # In Rotkehlchen Bitswift is BITS-2 but in Bittrex it's BITS
    'BITS-2': 'BITS',
    # In Rotkehlchen NuBits is USNBT but in Bittrex it's NBT
    'USNBT': 'NBT',
    # In Rotkehlchen BTM-2 is Bytom but in Bittrex it's BTM
    'BTM-2': 'BTM',
    # In Rotkehlchen PAI-2 is PCHAIN token but in Bittrex it's PI
    'PAI-2': 'PI',
    # In Rotkehlchen PLA-2 is Playchip but in Bittrex is PLA
    'PLA-2': 'PLA',
    # In Rotkehlchen LUNA-2 is Terra Luna but in Bittrex it's LUNA
    'LUNA-2': 'LUNA',
}

WORLD_TO_POLONIEX = {
    # AIR-2 is aircoin for us and AIR is airtoken. Poloniex has only aircoin
    'AIR-2': 'AIR',
    # APH-2 is Aphrodite coin for us and APH is Aphelion. Poloniex has only aphrodite
    'APH-2': 'APH',
    # Poloniex listed BTCtalkcoin as BCC as it was its original ticker but the
    # ticker later changes and it is now known to the world  as TALK
    'TALK': 'BCC',
    # Poloniex delisted BCH and listed it as BCHABC after the Bitcoin Cash
    # ABC / SV fork. In Rotkehlchen we consider BCH to be the same as BCHABC
    'BCH': 'BCHABC',
    # Poloniex has the BCH Fork, Bitcoin Satoshi's vision listed as BCHSV.
    # We know it as BSV
    'BSV': 'BCHSV',
    # Caishen is known as CAI in Poloniex. This is before the swap to CAIX
    'CAIX': 'CAI',
    # CCN is Cannacoin in Poloniex but in Rotkehlchen we know it as CCN-2
    'CCN-2': 'CCN',
    # CCN is CustomContractNetwork in Rotkehlchen but does not exist in Cryptocompare
    # Putting it as conversion to make sure we don't accidentally ask for wrong price
    'CCN': '',
    # Faircoin is known as FAIR outside of Poloniex. Seems to be the same as the
    # now delisted Poloniex's FAC if you look at the bitcointalk announcement
    # https://bitcointalk.org/index.php?topic=702675.0
    'FAIR': 'FAC',
    # KeyCoin in Poloniex is KEY but in Rotkehlchen it's KEY-3
    'KEY-3': 'KEY',
    # Marscoin in Poloniex is MRS but in Rotkehlchen it's MARS
    'MARS': 'MRS',
    # Mazacoin in Poloniex is MZC but in Rotkehlchen it's MAZA
    'MAZA': 'MZC',
    # Myriadcoin in Poloniex is MYR but in Rotkehlchen it's XMY
    'XMY': 'MYR',
    # NuBits in Poloniex is NBT but in Rotkehlchen it's USNBT
    'USNBT': 'NBT',
    # Stellar is XLM everywhere, apart from Poloniex
    'XLM': 'STR',
    # Poloniex still has the old name WC for WhiteCoin
    'XWC': 'WC',
}

WORLD_TO_KRAKEN = {
    'ATOM': 'ATOM',
    'ETC': 'XETC',
    'ETH': 'XETH',
    'LTC': 'XLTC',
    'REP': 'XREP',
    'BTC': 'XXBT',
    'XMR': 'XXMR',
    'XRP': 'XXRP',
    'ZEC': 'XZEC',
    'EUR': 'ZEUR',
    'USD': 'ZUSD',
    'GBP': 'ZGBP',
    'CAD': 'ZCAD',
    'JPY': 'ZJPY',
    'KRW': 'ZKRW',
    'DAO': 'XDAO',
    'MLN': 'XMLN',
    'ICN': 'XICN',
    'GNO': 'GNO',
    'BCH': 'BCH',
    'XLM': 'XXLM',
    'DASH': 'DASH',
    'EOS': 'EOS',
    'USDT': 'USDT',
    'KFEE': 'KFEE',
    'ADA': 'ADA',
    'QTUM': 'QTUM',
    'NMC': 'XNMC',
    'VEN': 'XXVN',
    'DOGE': 'XXDG',
    'XTZ': 'XTZ',
    'BSV': 'BSV',
}

WORLD_TO_BINANCE = {
    # When BCH forked to BCHABC and BCHSV, binance renamed the original to ABC
    'BCH': 'BCHABC',
    'BSV': 'BCHSV',
    # ETHOS is known as BQX in Binance
    'ETHOS': 'BQX',
    # GXChain is GXS in Binance but GXC in Rotkehlchen
    'GXC': 'GXS',
    # YOYOW is known as YOYO in Binance
    'YOYOW': 'YOYO',
}


@total_ordering
@dataclass(init=True, repr=True, eq=False, order=False, unsafe_hash=False, frozen=True)
class Asset():
    identifier: str
    name: str = field(init=False)
    symbol: str = field(init=False)
    active: bool = field(init=False)
    asset_type: AssetType = field(init=False)
    started: Timestamp = field(init=False)
    ended: Optional[Timestamp] = field(init=False)
    forked: Optional[str] = field(init=False)
    swapped_for: Optional[str] = field(init=False)

    def __post_init__(self):
        if not AssetResolver().is_identifier_canonical(self.identifier):
            raise UnknownAsset(self.identifier)
        data = AssetResolver().get_asset_data(self.identifier)

        # Ugly hack to set attributes of a frozen data class as post init
        # https://docs.python.org/3/library/dataclasses.html#frozen-instances
        object.__setattr__(self, 'name', data.name)
        object.__setattr__(self, 'symbol', data.symbol)
        object.__setattr__(self, 'active', data.active)
        object.__setattr__(self, 'asset_type', data.asset_type)
        object.__setattr__(self, 'started', data.started)
        object.__setattr__(self, 'ended', data.ended)
        object.__setattr__(self, 'forked', data.forked)
        object.__setattr__(self, 'swapped_for', data.swapped_for)

    def is_fiat(self) -> bool:
        return self.asset_type == AssetType.FIAT

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<Asset identifier:{self.identifier} name:{self.name} symbol:{self.symbol}>'

    def to_kraken(self) -> str:
        return WORLD_TO_KRAKEN[self.identifier]

    def to_bittrex(self) -> str:
        return WORLD_TO_BITTREX.get(self.identifier, self.identifier)

    def to_binance(self) -> str:
        return WORLD_TO_BINANCE.get(self.identifier, self.identifier)

    def to_cryptocompare(self) -> str:
        cryptocompare_str = WORLD_TO_CRYPTOCOMPARE.get(self.identifier, self.identifier)
        # There is an asset which should not be queried in cryptocompare
        if cryptocompare_str is None:
            if self.identifier == 'MRS':
                raise UnsupportedAsset(
                    'Marginless is not in cryptocompare. Asking for MRS '
                    'will return MARScoin',
                )
            else:
                raise RuntimeError(
                    f'Got {self.identifier} as a cryptocompare query but it is '
                    f'documented as returning None and is not handled',
                )

        return cryptocompare_str

    def __hash__(self):
        return hash(self.identifier)

    def __eq__(self, other: Any) -> bool:
        if other is None:
            return False

        if isinstance(other, Asset):
            return self.identifier == other.identifier
        elif isinstance(other, str):
            return self.identifier == other
        else:
            raise ValueError(f'Invalid comparison of asset with {type(other)}')

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Asset):
            return self.identifier < other.identifier
        elif isinstance(other, str):
            return self.identifier < other
        else:
            raise ValueError(f'Invalid comparison of asset with {type(other)}')


@dataclass(init=True, repr=True, eq=False, order=False, unsafe_hash=False, frozen=True)
class HasEthereumToken(Asset):
    """ Marker to denote assets having an Ethereum token address """
    ethereum_address: ChecksumEthAddress = field(init=False)
    decimals: int = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        data = AssetResolver().get_asset_data(self.identifier)

        if not data.ethereum_address:
            raise ValueError('Tried to initialize a non Ethereum asset as Ethereum Token')

        object.__setattr__(self, 'ethereum_address', data.ethereum_address)
        object.__setattr__(self, 'decimals', data.decimals)


@dataclass(init=True, repr=True, eq=False, order=False, unsafe_hash=False, frozen=True)
class EthereumToken(HasEthereumToken):
    pass
