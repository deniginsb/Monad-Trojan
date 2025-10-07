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
BLOCKVISION_API_KEY = os.getenv('BLOCKVISION_API_KEY')

# Alchemy API Configuration (Primary)
ALCHEMY_MONAD_URL = os.getenv('ALCHEMY_MONAD_URL')

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
