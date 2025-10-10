# 🤖 MonadTrojan Bot - Monad Testnet Telegram Bot

A Telegram bot for interacting with the Monad blockchain testnet. Built with Python and integrated with Alchemy API for fast and reliable blockchain data.

## ✨ Features

### 🔐 Secure Wallet Management
- **Three encryption modes** - Choose your security level:
  - **Standard Mode** - Quick access, master key encryption
  - **Password Mode** - Add passphrase for extra layer
  - **Hybrid Mode (NEW!)** - Zero-knowledge RSA + AES encryption
- **Wallet import** - Import existing wallets easily
- **Balance checking** - Real-time MON and token balances
- **Password caching** - Remember password for session or prompt each time (you choose!)
- **Security features** - Your keys, your control

### 💰 Portfolio Management
- **Real-time portfolio tracking** with USD values
- **Price caching** - 5-minute cache for instant load times (2-3 sec vs 8-10 sec)
- **MON derivatives pricing** - Automatic pricing for gMON, aprMON, shMON, sMON, WMON
- **Verified tokens priority** - Fetch prices for verified tokens first
- **ASCII visualization** - Beautiful portfolio display with percentage allocations
- **LP token filtering** - Skip unreliable LP token pricing
- **Displays up to 25 tokens** with balance and USD value

### 🔔 Smart Notifications (NEW!)
Real-time notifications when you receive tokens on Monad testnet:

#### MON Received Notifications
- **TX hash links** - Direct link to transaction (not wallet address!)
- **Balance increase detection** - Automatic detection of native MON received
- **Fast delivery** - 30-second check interval

#### Verified Token Notifications
- **New token detection** - Get notified when receiving a token for the first time
- **Balance increase alerts** - Notifications when receiving more of existing tokens
- **TX hash tracking** - Direct links to ERC20 token transfer transactions
- **Works for all verified tokens**: shMON, USDC, USDT, WETH, WBTC, etc.

#### Notification Settings
- **Toggle ON/OFF** - Enable/disable notifications via ⚙️ Settings menu
- **No spam** - First-run initialization without notification spam
- **Smart snapshot system** - Only notifies for NEW changes, not existing balances

### 💱 Token Swapping
- **DEX integration** - Swap tokens via Monad DEX
- **Buy/Sell interface** - Simple commands for trading
- **Real-time price quotes** - Get current prices before swapping
- **Slippage protection** - Configurable slippage tolerance

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Telegram Bot Token
- Alchemy API Key (for Monad testnet)

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/deniginsb/Monad-Trojan
cd Monad-Trojan
chmod +x setup.sh
./setup.sh
```

2. **Configure environment:**
```bash
cp .env.example .env
nano .env
```

Required variables:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ALCHEMY_MONAD_URL=https://monad-testnet.g.alchemy.com/v2/YOUR_API_KEY
MONAD_TESTNET_RPC_URL=https://testnet-rpc.monad.xyz
```

3. **Start the bot:**
```bash
python3 main.py
```

## 📱 Bot Commands

- `/start` - Initialize bot and create/import wallet
- `/wallet` - View wallet address and balance
- `/portfolio` - View detailed portfolio with USD values
- `/buy <token> <amount>` - Buy tokens
- `/sell <token> <amount>` - Sell tokens
- `/price <token>` - Get token price
- `⚙️ Settings` - Toggle notification settings

## 🏗️ Architecture

### Core Components

**main.py** - Bot entry point and command handlers
- Telegram bot initialization
- Command routing
- Conversation handlers with password flow
- Transaction password prompts (buy/sell/send)
- Show private key with mandatory password
- Settings management

**notification_monitor.py** - Background notification system (NEW!)
- Wallet monitoring every 30 seconds
- Token snapshot comparison
- TX hash finding via Alchemy API
- Telegram notification delivery

**blockchain.py** - Blockchain interaction layer
- Alchemy API integration (primary)
- Token balance fetching
- DEX price queries
- Transaction building

**portfolio.py** - Portfolio management
- Real-time price fetching
- Price caching system (5-min TTL)
- USD value calculations
- ASCII visualization

**database.py** - Data persistence
- SQLAlchemy ORM models
- User wallet storage
- Notification settings
- Token snapshots for change detection

**security.py** - Wallet security (Standard/Password modes)
- Passphrase-based key derivation
- AES-256 encryption with master key
- Per-user salt generation

**hybrid_encryption.py** - Zero-knowledge encryption (NEW!)
- RSA-4096 keypair generation
- AES-256-GCM data encryption
- Password-protected private key backup
- True end-to-end encryption (server can't decrypt!)

**hybrid_handlers.py** - Hybrid encryption flows
- Password setup for new users
- Upgrade existing users to hybrid mode
- RSA key backup (text + file format)
- Password verification with retry

**send_receive_handlers.py** - Token transfer handlers
- Send tokens with password prompt
- Receive token QR code generation
- Native MON and ERC20 support
- Password caching for convenience

### Scripts

**getTokensAlchemy.js** - Fast token fetching via Alchemy Enhanced API
**price.js** - DEX price queries via on-chain calls
**getTokensEtherscanV3.js** - Backup token fetching (fallback)

## 🔔 Notification System Deep Dive

The notification system uses a smart snapshot-based approach:

### How It Works

1. **Background Monitor** - Runs every 30 seconds checking all users with notifications enabled
2. **Token Snapshot** - Stores current token balances in database
3. **Change Detection** - Compares current balance with last snapshot
4. **TX Hash Finding** - Uses Alchemy API to find matching transaction:
   - Native MON: `category: ["external"]`
   - ERC20 tokens: `category: ["erc20"]`
   - Matches by token address + amount
5. **Notification Delivery** - Sends formatted Telegram message with TX link

### First-Run Behavior
When you first enable notifications:
- System takes snapshot of all current tokens
- **NO notifications sent** for existing tokens
- Only NEW changes trigger notifications

### Supported Notifications

✅ Native MON received (balance increase)
✅ New verified token received (first time)
✅ Verified token balance increase (more of existing token)
✅ Direct TX hash links (not wallet address!)

## 🔧 Configuration

### Verified Tokens
Edit `config.py` to add/remove verified tokens:
```python
VERIFIED_TOKENS = {
    '0x3a98250f98dd388c211206983453837c8365bdc1': 'shMON',
    '0x...': 'USDC',
    # Add more...
}
```

### Notification Settings
Users can toggle notifications:
1. Open bot → ⚙️ Settings
2. Click "🔔 Notifications: ON" to toggle

### Cache Settings
Adjust price cache TTL in `portfolio.py`:
```python
PRICE_CACHE_TTL = 300  # 5 minutes
```

## 📊 Performance

- **Portfolio load**: ~2-3 seconds (with cache)
- **Token fetch**: ~1-2 seconds (Alchemy API)
- **Notification delivery**: Max 30 seconds after transaction
- **TX hash finding**: ~1-2 seconds (Alchemy getAssetTransfers)

## 🔐 Security Notes

- Private keys stored encrypted in SQLite
- Each user has unique encryption key
- Passphrase never stored in plain text
- Bot token in environment variables only
- No API keys in source code

## 🐛 Troubleshooting

**Notifications not working?**
- Check if enabled in ⚙️ Settings
- Verify bot is running: `ps aux | grep main.py`
- Check logs: `tail -f bot_startup.log`

**TX links go to wallet instead of transaction?**
- This is fixed in current version
- Links now use Alchemy API to find exact TX hash
- MON: Uses `category: ["external"]`
- Tokens: Uses `category: ["erc20"]`

**Portfolio showing 0%?**
- Old issue, fixed - now uses price-based allocation
- Run `/portfolio` to see updated percentages

## 📝 Version History

**v1.5.0** (Current) 
- ✅ Hybrid encryption with RSA-4096 + AES-256-GCM
- ✅ Zero-knowledge security (server can't decrypt)
- ✅ Password caching with user choice
- ✅ Unified password flow for all transactions
- ✅ Show private key with mandatory re-auth
- ✅ Send token with password support

**v.1.4.0**
- ✅ check nft

**v1.3.0**
- ✅ Send Token — easily transfer MON or any verified token
- ✅ Receive Token — view your wallet



**v1.2.0**
- ✅ Complete notification system with TX hash links
- ✅ MON + verified token notifications
- ✅ Smart snapshot system (no spam)
- ✅ 30-second check interval
- ✅ Alchemy API for TX finding

**v1.1.0**
- ✅ Portfolio optimization with caching
- ✅ Real MON price fetching
- ✅ GitHub export preparation
- ✅ Price-based allocation calculations

**v1.0.0**
- ✅ Basic wallet management
- ✅ Token swapping
- ✅ Portfolio tracking

## 🤝 Contributing

This is a testnet bot for Monad blockchain. Feel free to fork and modify for your needs.

## ⚠️ Disclaimer

This bot is for Monad testnet only. Do not use with mainnet funds. No warranty provided - use at your own risk.

## 📞 Support

For issues or questions, check the logs in `bot_startup.log` first. Most problems can be diagnosed from log output.

## 🎯 Roadmap

- [ ] Multi-hop swaps
- [ ] LP token support in notifications
- [ ] Transaction history command
- [ ] Gas price estimation
- [ ] Batch notifications (digest mode)

---

**Built with 💙 for Monad Testnet**
