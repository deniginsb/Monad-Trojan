# Features Guide

## Trading Features

### Buy Tokens
- Quick buy amounts: 0.1, 0.5, 1.0, 5.0 MONAD
- Custom amount support (any value you want)
- Real-time price preview from DEX
- Slippage protection
- Password prompt for hybrid users (with caching!)

### Sell Tokens  
- Quick sell: 25%, 50%, 75%, 100%
- Custom amount support (specify exact tokens)
- Only verified tokens shown
- Transaction confirmation
- Password prompt for hybrid users (with caching!)

### Send Tokens
- Native MON transfers
- ERC20 token transfers
- QR code generation for receiving
- Password support for hybrid encryption

## Portfolio

### Value-Based Allocation
- Calculate % by USD value (not quantity)
- Top 15 tokens with prices
- ASCII bar visualization
- Total portfolio value

### Price Sources
1. GeckoTerminal API
2. On-chain DEX prices
3. Smart filtering (skip LP tokens)

## Security

### Three Encryption Modes
- **Standard Mode**: Fast, master key only (testnet)
- **Password Mode**: Legacy passphrase protection
- **Hybrid Mode**: RSA + AES, true zero-knowledge (RECOMMENDED!)

### Hybrid Encryption Features
- RSA-4096 keypair generation
- AES-256-GCM for wallet encryption
- Password-protected RSA private key
- Server CANNOT decrypt your wallet
- Password caching options (your choice!)
- RSA key backup (text + file)

### Password Caching
- "Just This Once" - Password for single transaction
- "Remember for Session" - Cache until bot restart
- You decide the balance between security and convenience

### Special Protection
- Show private key ALWAYS requires fresh password
- No cache used for viewing keys (extra security)
- Auto-delete password messages
- 60-second auto-delete for displayed keys

## Token Discovery

### Alchemy Enhanced APIs
- Auto-detect all ERC-20 tokens
- Complete metadata (name, symbol, decimals)
- Fast parallel processing

### Fallbacks
1. Alchemy API (primary)
2. BlockVision API (legacy)
3. Database history

## Settings

### Customizable
- Slippage: 0.5% to 10%
- Gas mode: Normal, Fast, Very Fast
- Anti-MEV: ON/OFF

## Verification

### Token Whitelist
- Known safe tokens marked ✓
- Scam protection
- Easy to extend
