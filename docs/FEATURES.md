# Features Guide

## Trading Features

### Buy Tokens
- Quick buy amounts: 0.1, 0.5, 1.0, 5.0 MONAD
- Custom amount support
- Real-time price preview
- Slippage protection

### Sell Tokens  
- Quick sell: 25%, 50%, 75%, 100%
- Custom amount support
- Only verified tokens shown
- Transaction confirmation

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

### Two Modes
- **Quick Mode**: Fast, master key only
- **Secure Mode**: Passphrase protected

### Encryption
- AES-128 (Fernet)
- Scrypt key derivation
- Zero-knowledge passphrases

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
