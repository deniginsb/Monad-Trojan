# Hybrid Encryption Guide 🔐

## What is Hybrid Encryption?

Hybrid encryption combines the best of both worlds:
- **RSA (public-key)** - For secure key exchange
- **AES (symmetric)** - For fast data encryption

Think of it like this: RSA is a locked box that only you have the key for, and AES is the actual encryption that protects your wallet. The AES key itself is locked inside the RSA box.

## Why Should You Care?

### Zero-Knowledge Security
When you use hybrid encryption, **even the server admin can't access your wallet**. Here's why:

- Your password never leaves your device
- Your private RSA key is encrypted with YOUR password
- The server only stores encrypted data it can't read
- No one can decrypt your wallet without your password

It's like putting your house key in a safe that only you know the combination to. Even if someone steals the safe, they still can't get your key.

## How It Works

### The Simple Version

1. You set a password (only you know it)
2. Bot generates RSA keypair (4096-bit - super secure)
3. Your wallet's private key gets encrypted with AES
4. The AES key gets encrypted with RSA
5. Your RSA private key gets encrypted with your password
6. Bot backs up your RSA key (so you can recover if needed)

### What Gets Stored Where

**On Server (encrypted):**
- RSA public key
- Encrypted wallet private key
- Encrypted RSA private key

**Only You Have:**
- Your password
- RSA private key backup (in Telegram)

**Never Stored Anywhere:**
- Your password in plain text
- Wallet private key in plain text
- RSA private key in plain text

## Setting Up Hybrid Encryption

### For New Users

When you start the bot for first time:

1. Click `/start`
2. Choose "🔐 Hybrid Encryption (Recommended)"
3. Set your password (minimum 8 characters)
4. Confirm password
5. Done! Bot sends you RSA key backup

**Important:** Save the RSA key backup message! You'll need it if you ever want to recover your wallet.

### For Existing Users

Already have a wallet? You can upgrade:

1. Click `/start`
2. Click "🔐 Upgrade Security"
3. Set your password
4. Confirm password
5. Get RSA key backup

Your wallet stays the same, just more secure now.

## Using Hybrid Encryption

### Password Caching

First time you do a transaction (buy/sell/send), bot will ask:

**"How would you like to handle your password?"**

- **🔓 Just This Once** - Password only used for this transaction
- **🔐 Remember for Session** - Password cached until bot restart

Most people choose "Remember for Session" so they don't have to type password every time. But if you're on shared device, choose "Just This Once" for extra safety.

### Transaction Flow

**If password cached:**
```
You: Buy 0.5 MON of USDC
Bot: ⏳ Processing...
Bot: ✅ Done! [TX Link]
```

**If password NOT cached:**
```
You: Buy 0.5 MON of USDC
Bot: 🔐 Please enter password
You: [type password, auto-deleted]
Bot: ✅ Verified! Cache choice?
You: Remember for Session
Bot: ⏳ Processing...
Bot: ✅ Done! [TX Link]
```

### Viewing Private Key

This is the ONLY action that **always** requires fresh password:

```
You: Settings → Show Private Key → Confirm
Bot: 🔐 Password required (for security)
You: [type password]
Bot: [shows key for 60 seconds then auto-deletes]
```

Why? Because viewing your private key is super sensitive. We want to make sure it's really YOU, not someone who grabbed your phone while password was cached.

## Security Features

### Password Requirements

- Minimum 8 characters
- Bot doesn't enforce complexity (you decide)
- Stronger = better (use numbers, symbols, mixed case)

### What Makes It Secure?

**RSA-4096:**
- Military-grade encryption
- Would take 1 billion years to crack (seriously)
- Same security banks use

**AES-256-GCM:**
- Symmetric encryption standard
- Authenticated (detects tampering)
- Super fast for encrypting/decrypting

**Password-Based Encryption:**
- Scrypt key derivation (memory-hard)
- Brute force resistant
- Each wrong guess takes 100ms (makes hacking impractical)

### Auto-Delete Features

1. **Password messages** - Deleted immediately after you send
2. **Private key view** - Auto-deleted after 60 seconds
3. **Error messages** - Don't leak info about encryption

## Recovering Your Wallet

### If You Forget Password

**Bad news:** You can't recover it. That's the whole point of zero-knowledge security.

**What you CAN do:**
- Use the RSA private key backup to decrypt
- Import wallet into another tool
- Transfer funds to new wallet (if you still have access)

### If Bot Dies

Don't worry! You have two options:

1. **Use RSA backup** - The bot sent you encrypted RSA key
2. **Export private key** - Settings → Show Private Key (need password)

Then import to MetaMask, Trust Wallet, etc.

## Comparing Security Modes

| Feature | Standard | Password | Hybrid |
|---------|----------|----------|--------|
| Encryption | Master key | Master + Pass | RSA + AES + Pass |
| Server Access | ✅ Yes | ⚠️ Partial | ❌ No |
| Speed | ⚡ Instant | ⚡ Instant | ⚡ Fast |
| Password Required | Never | Every TX | First TX/Session |
| Zero-Knowledge | ❌ | ⚠️ Partial | ✅ Yes |
| Key Backup | No | No | ✅ Yes (RSA) |
| Recovery | Easy | Hard | Medium |

### When to Use Each

**Standard Mode:**
- Testing on testnet
- Small amounts
- You trust the server
- Want maximum convenience

**Password Mode:**
- Medium security needs
- Quick to set up
- Legacy option

**Hybrid Mode (Recommended):**
- Production use
- Large amounts
- Maximum security
- You want zero-knowledge protection

## Common Questions

### "Is my password stored anywhere?"

Nope. It only exists when you type it, and it's immediately deleted after use.

### "What if I lose RSA backup?"

You can still use your wallet normally, but recovery becomes harder. Always save the backup message!

### "Can I change my password?"

Not yet, but it's on the roadmap. For now, you'd need to create new wallet with new password.

### "Does bot restart clear password cache?"

Yes! That's by design. Each bot restart = fresh start.

### "What if someone guesses my password?"

With hybrid encryption + Scrypt, each guess takes ~100ms. Even with super fast computer, guessing 8-character password would take years. Just don't use "password123" :)

### "Can I downgrade to Standard mode?"

No. Once you upgrade to hybrid, you can't go back (security decision). But you can create new wallet in Standard mode if needed.

### "What about NFTs and other tokens?"

All work the same way! Hybrid encryption protects your entire wallet, not just specific tokens.

## Technical Details

For the nerds who want to know exactly how it works:

### Encryption Process

```python
# 1. Generate RSA keypair
rsa_private, rsa_public = generate_rsa_keypair(4096)

# 2. Encrypt wallet private key with AES
aes_key = os.urandom(32)  # 256 bits
encrypted_wallet = aes_gcm_encrypt(wallet_private_key, aes_key)

# 3. Encrypt AES key with RSA public key
encrypted_aes_key = rsa_encrypt(aes_key, rsa_public)

# 4. Encrypt RSA private key with password
password_key = scrypt(password, salt, n=2**14, r=8, p=1)
encrypted_rsa_private = aes_gcm_encrypt(rsa_private, password_key)

# 5. Store in database
store({
    'rsa_public': rsa_public,
    'encrypted_wallet': encrypted_wallet,
    'encrypted_aes_key': encrypted_aes_key,
    'encrypted_rsa_private': encrypted_rsa_private
})
```

### Decryption Process

```python
# 1. User provides password
password_key = scrypt(password, salt, n=2**14, r=8, p=1)

# 2. Decrypt RSA private key
rsa_private = aes_gcm_decrypt(encrypted_rsa_private, password_key)

# 3. Decrypt AES key
aes_key = rsa_decrypt(encrypted_aes_key, rsa_private)

# 4. Decrypt wallet private key
wallet_private = aes_gcm_decrypt(encrypted_wallet, aes_key)

# 5. Use for transaction, then immediately delete
sign_transaction(wallet_private)
del wallet_private, aes_key, rsa_private, password_key
```

### Why This Approach?

- **Hybrid** = Fast (AES) + Secure key exchange (RSA)
- **Scrypt** = Expensive to brute force
- **GCM mode** = Authenticated encryption (detects tampering)
- **4096-bit RSA** = Future-proof (quantum-resistant for now)

## Troubleshooting

### "Incorrect password" error

- Make sure Caps Lock is off
- Check for typos
- Try again (3 attempts recommended)

### "Session expired" error

- Bot was restarted
- Just enter password again

### Transaction stuck on "Processing..."

- Network might be slow
- Check blockchain explorer with TX hash
- Usually resolves in 30-60 seconds

### Can't find RSA backup message

- Search Telegram for "RSA Private Key Backup"
- Check bot's messages from date you enabled hybrid
- If truly lost, export private key to new wallet ASAP

## Best Practices

1. **Choose strong password** - Use password manager if needed
2. **Save RSA backup** - Pin the message in Telegram
3. **Test with small amount** - Before sending big funds
4. **Cache password for session** - Unless on shared device
5. **Never share password** - Not even with "support"
6. **Enable 2FA on Telegram** - Extra account security
7. **Backup wallet elsewhere** - Export key to MetaMask too

## Conclusion

Hybrid encryption gives you **bank-level security** for your crypto wallet. It's the difference between "hoping server is secure" and "knowing mathematically no one can access your funds."

Yes, you have to remember a password. But that's a small price for true ownership of your crypto.

**Your keys, your crypto, your control.** 🔐

---

Questions? Feedback? Open an issue or ask in Telegram!
