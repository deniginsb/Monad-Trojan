"""
Configuration Module - Constants, ABIs, and blockchain configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Blockchain Configuration
MONAD_TESTNET_RPC_URL = os.getenv('MONAD_TESTNET_RPC_URL')
# UniswapV2Router02 on Monad testnet (Official from monad-developers repo)
DEX_ROUTER_ADDRESS = os.getenv('DEX_ROUTER_ADDRESS', '0xfb8e1c3b833f9e67a71c859a132cf783b645e436')
NATIVE_CURRENCY = 'MONAD'
CHAIN_ID = 10143

# BlockVision API Configuration (Legacy - use Alchemy instead)
BLOCKVISION_API_KEY = os.getenv('BLOCKVISION_API_KEY', '')

# Alchemy API Configuration (Primary)
ALCHEMY_MONAD_URL = os.getenv('ALCHEMY_MONAD_URL', 'https://monad-testnet.g.alchemy.com/v2/XNBMVXBwNDnoNZHXqcpzB')

# Block Explorer
BLOCK_EXPLORER_URL = 'https://testnet.monadexplorer.com'
BLOCK_EXPLORER_API_URL = os.getenv('BLOCK_EXPLORER_API_URL', '')
BLOCK_EXPLORER_API_KEY = os.getenv('BLOCK_EXPLORER_API_KEY', '')

# Gas Configuration (Updated for Monad Testnet - base fee ~50 gwei)
GAS_PRICE_MODES = {
    'normal': {'maxFeePerGas': 100, 'maxPriorityFeePerGas': 2},      # 2x base fee
    'fast': {'maxFeePerGas': 150, 'maxPriorityFeePerGas': 5},        # 3x base fee
    'very_fast': {'maxFeePerGas': 200, 'maxPriorityFeePerGas': 10}   # 4x base fee
}

# ERC-20 Token ABI (Standard Functions)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

# Universal Router / DEX Router ABI (zkSwap-like)
DEX_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# WMON Address (Wrapped MONAD) - Correct address for Monad Testnet
WETH_ADDRESS = '0x760afe86e5de5fa0ee542fc7b7b713e1c5425701'

# Verified Tokens - Only these tokens will appear in balance, sell menu, and notifications
VERIFIED_TOKENS = {
    '0x760afe86e5de5fa0ee542fc7b7b713e1c5425701': 'WMON',
    '0xf817257fed379853cde0fa4f97ab987181b1e5ea': 'USDC',
    '0xb2f82d0f38dc453d596ad40a37799446cc89274a': 'aprMON',
    '0x88b8e2161dedc77ef4ab7585569d2415a1c1055d': 'USDT',
    '0xe0590015a873bf326bd645c3e1266d4db41c4e6b': 'CHOG',
    '0x0f0bdedbf0f83cd1ee3974779bcb7315f9808c714': 'DAK',
    '0xfe140e1dce99be9f4f15d657cd9b7bf622270c50': 'YAKI',
    '0xaeef2f6b429cb59c9b2d7bb2141ada993e8571c3': 'gMON',
    '0x3a98250f98dd388c211206983453837c8365bdc1': 'shMON',
    '0xb5a30b0fdc5ea94a52fdc42e3e9760cb8449fb37': 'WETH',
    '0xe1d2439b75fb9746e7bc6cb777ae10aa7f7ef9c5': 'sMON',
    '0x268e4e24e0051ec27b3d27a95977e71ce6875a05': 'BEAN',
    '0xc8527e96c3cb9522f6e35e95c0a28feab8144f15': 'MAD',
    '0x89e4a70de5f2ae468b18b6b6300b249387f9adf0': 'fMON',
    '0xcf5a6076cfa32686c0df13abada2b40dec133f1d': 'WBTC',
    '0xcc5b42f9d6144dfdfb6fb3987a2a916af902f5f8': 'JAI',
    '0x5d876d73f4441d5f2438b1a3e2a51771b337f27a': 'USDC',
    '0xb5481b57ff4e23ea7d2fda70f3137b16d0d99118': 'CVE',
    '0x6bb379a2056d1304e73012b99338f8f581ee2e18': 'WBTC',
    '0x0efed4d9fb7863ccc7bb392847c08dcd00fe9be2': 'muBOND',
    '0x5387c85a4965769f6b0df430638a1388493486f1': 'WSOL',
    '0x4aa50e8208095d9594d18e8e3008abb811125dce': 'MOON',
    '0x7fdf92a43c54171f9c278c67088ca43f2079d09b': 'LUSD',
    '0x5b54153100e40000f6821a7ea8101dc8f5186c2d': 'SWETH',
    '0x57c914e3240c837ebe87f096e0b4d9a06e3f489b': 'monUSD',
    '0x38a3321a419b8688f539a600e3c7898a0528737f': 'BLZP',
    '0xb38bb873cca844b20a9ee448a87af3626a6e1ef5': 'MIST',
    '0x04a9d9d4aea93f512a4c7b71993915004325ed38': 'HEDGE',
    '0x786f4aa162457ecdf8fa4657759fa3e86c9394ff': 'MAD-LP',
    '0xceb564775415b524640d9f688278490a7f3ef9cd': 'iceMON',
    '0x954a9b30f5aece2c1581e33b16d9ddfcd473a0f8': 'KESO',
    '0x0e1c9362cdea1d556e5ff89140107126baaf6b09': 'aprMON',
    '0x199c0da6f291a897302300aaae4f20d139162916': 'stMON',
    '0xbdd352f339e27e07089039ba80029f9135f6146f': 'USDm',
    '0xa2426cd97583939e79cfc12ac6e9121e37d0904d': 'PINGU',
    '0xfa47b094a9666422848f459b54dab88b0e8255e9': 'MONKA',
    '0x4c632c40c2dcd39c20ee7ecdd6f9743a3c7ffe6b': 'TED',
    '0x3b428df09c3508d884c30266ac1577f099313cf6': 'mamaBTC',
    '0xca9a4f46faf5628466583486fd5ace8ac33ce126': 'OCTO',
    '0x0c0c92fcf37ae2cbcc512e59714cd3a1a1cbc411': 'MONDA',
    '0x43e52cbc0073caa7c0cf6e64b576ce2d6fb14eb8': 'NOM',
    '0x8f3a8ae1f1859636e82ca4e30db9fb129b02d825': 'suUSD',
    '0xc85548e0191cd34be8092b0d42eb4e45eba0d581': 'NSTR',
    '0x8589a0dd9ecd77b7d70ff76147dce366bf31254e': 'gigaETH',
    '0x301f38161dd907b7602c91b8e6303ed6992c0d8e': 'MONDA-V2',
    '0x93e9cae50424c7a4e3c5eceb7855b6dab74bc803': 'NAP',
    '0x7b55354900d2a7c241785fe178e90a0f7685bf57': 'HASH',
    '0xcd6b9ff949bd7336f29cc9520ff9fdf200e8b8f6': 'AUSD',
    '0x2c7d4cc1f7377a2a2b581669b40e5b3383b9a949': 'OWL',
    '0x8a86d48c867b76ff74a36d3af4d2f1e707b143ed': 'RBSD',
    '0x11517333d9a65ca3331c3c60bb288fa98013a2ed': 'CHOG',
    '0xb5e5fa5837304fea6b9ce7e09623e63669ad95fb': 'NFT',
    '0x3247b7d8100556ce6fc1a4141c117104ef806850': 'suETH',
    '0xfe5bc01ff7631d495630331e02b4aeaa0bf9840d': 'ANGLER',
    '0x4961c832469fcbb468c0a794de32faaa30ccd2f6': 'suBTC',
    '0x8a056df4d7f23121a90aca1ca1364063d43ff3b8': 'KEYS',
    '0x6ce1890eeadae7db01026f4b294cb8ec5ecc6563': 'HALLI',
    '0x3552f8254263ea8880c7f7e25cb8dbbd79c0c4b1': 'BMONAD',
    '0x44369aafdd04cd9609a57ec0237884f45dd80818': 'P1',
    '0x24d2fd6c5b29eebd5169cc7d6e8014cd65decd73': 'TFAT',
    '0x92eac40c98b383ea0f0efda747bdac7ac891d300': 'RED',
    '0xd875ba8e2cad3c0f7e2973277c360c8d2f92b510': 'USDX',
    '0x4a5c952c446d5c4bba9f4517b473ec1718c5f27a': 'BUN',
    '0x7a1a3679a5fe97d1da3683c3807a179e26f532b1': 'ZF',
    '0x6200db750d4a6a2ed84181dbddc5e0029c238cba': 'RTMD',
    '0xd2707f681ee0c1b5f3a0eb2618628477f31edbce': 'KOL',
    '0xa998716fdc8da0bd024235dd208a70d257eca763': 'APR',
    '0x88aac8165144564ee8b8abdc9099992345fbb56a': 'NEX',
    '0x8d71ccf6bc1358e677e84ddcbe8386ccb36134ea': '$DASH',
    '0x0569049e527bb151605eec7bf48cfd55bd2bf4c8': 'DAKIMAKURA',
    '0x739d4f237623583852db0d102b37996c35f400b5': 'Doon',
    '0x1b4cb47622705f0f67b6b18bbd1cb1a91fc77d37': 'shMON',
    '0xb91615806c743c03d7584d7c688dffd2e7077af4': 'moonpig',
    '0xfaaad2849f35282e96151a4944bd9e0082b60a08': 'MNAD',
    '0xf793fde80c3a92eb8a6074803ca6976c87b1a90a': 'BERZAN',
    '0x111f0d8c86c61cc73713720d7899e1b40d8297d5': 'LONG',
    '0x8a618e0266a87581c5d3d5135afe6ea16bcf5d52': 'PN',
    '0x1498fcb65fcf4237b57b75fafecdebbdef22e119': 'MONFUN',
    '0xafb0d64f308423d16ef8833b901dbdd750554438': 'NOM',
    '0x6c6a73cb3549c8480f08420ee2e5dfaf9d2d4cdb': 'LINK',
}

# High value tokens (alternative check)
HIGH_VALUE_TOKENS = ['MON', 'MONAD', 'WMON', 'USDC', 'USDT', 'WETH', 'WBTC']

# Bot Messages
WELCOME_MESSAGE = """
🤖 *Welcome to MonadTrojan Bot\\!* 🚀

Automated trading bot for *Monad Testnet* with enterprise\\-grade security\\. This bot allows you to:

✅ Buy and sell ERC\\-20 tokens quickly
✅ Manage wallet with military\\-grade encryption
✅ Trade with configurable slippage and gas
✅ Monitor balance and transaction history real\\-time

🔐 *Key Security:*
Your private key is encrypted using Fernet \\(AES\\-128\\) and never stored as plain text\\.

📱 *Your Wallet is Ready\\!*
Use the menu below to start trading\\.

⚠️ *IMPORTANT:* This is testnet\\. Do not use your mainnet private key\\!
"""

WALLET_INFO_TEMPLATE = """
💼 *Your Wallet Information*

📍 *Address:* `{address}`
🔗 [View on Explorer]({explorer_url})

💰 *Native Balance:*
   {native_balance} {currency}

🪙 *ERC\\-20 Tokens:*
{token_list}

💵 *Total Estimate:* {total_value}

⏰ *Last Updated:* {timestamp}
"""

# Quick Buy Amounts (in MONAD)
QUICK_BUY_AMOUNTS = [0.1, 0.5, 1.0, 5.0]

# Quick Sell Percentages
QUICK_SELL_PERCENTAGES = [25, 50, 75, 100]

# Slippage Options
SLIPPAGE_OPTIONS = [0.5, 1.0, 5.0, 10.0]
