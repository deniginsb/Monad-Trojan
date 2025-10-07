"""
Notification Monitor - Background task to monitor wallet for new tokens
Sends Telegram notifications when new verified tokens are detected
"""
import asyncio
from typing import List, Dict, Optional
from telegram import Bot
from telegram.constants import ParseMode
from blockchain import blockchain_manager
from database import db_manager
from config import BLOCK_EXPLORER_URL, MONAD_TESTNET_RPC_URL
from web3 import Web3

# Web3 instance for transaction queries
w3 = Web3(Web3.HTTPProvider(MONAD_TESTNET_RPC_URL))

async def find_recent_transaction(wallet_address: str, amount: float) -> Optional[str]:
    """
    Find recent transaction that matches the received amount
    
    Args:
        wallet_address: Wallet address
        amount: Amount received in MON
        
    Returns:
        Transaction hash if found, None otherwise
    """
    try:
        # Get latest block
        latest_block = w3.eth.block_number
        
        # Check last 500 blocks for incoming transactions (covers ~25 min on Monad)
        for block_num in range(latest_block, max(latest_block - 500, 0), -1):
            try:
                block = w3.eth.get_block(block_num, full_transactions=True)
                
                for tx in block.transactions:
                    # Check if transaction is TO our wallet
                    if tx['to'] and tx['to'].lower() == wallet_address.lower():
                        # Check if it's a native transfer (not contract call)
                        if tx['input'] == '0x' or tx['input'] == '0x0':
                            # Convert value from wei to MON
                            tx_amount = float(w3.from_wei(tx['value'], 'ether'))
                            
                            # Match with tolerance (0.0001 MON)
                            if abs(tx_amount - amount) < 0.0001:
                                return tx['hash'].hex()
            except Exception as e:
                continue
        
        return None
    except Exception as e:
        print(f"⚠️ Error finding transaction: {e}")
        return None

def escape_markdown(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    text = str(text)
    replacements = {
        '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]',
        '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
        '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-',
        '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}',
        '.': '\\.', '!': '\\!'
    }
    for char, escaped in replacements.items():
        text = text.replace(char, escaped)
    return text

async def send_token_notification(bot: Bot, user_id: int, new_tokens: List[Dict]):
    """
    Send notification about new tokens received
    
    Args:
        bot: Telegram Bot instance
        user_id: Telegram user ID
        new_tokens: List of new token data dicts
    """
    for token in new_tokens:
        symbol = token.get('symbol', 'Unknown')
        name = token.get('name', symbol)
        balance = token.get('balance', 0)
        address = token.get('address', '')
        balance_increase = token.get('balance_increase')  # For native MON
        
        # Build message
        if balance_increase:
            # Token received (MON or other verified token)
            symbol = token.get('symbol', 'Token')
            
            if symbol in ['MON', 'MONAD']:
                # Native MON
                message = f"💰 *MON Received\\!*\n\n"
                message += f"*Amount:* `\\+{escape_markdown(f'{balance_increase:.4f}')} MON`\n"
                message += f"*New Balance:* `{escape_markdown(f'{balance:.4f}')} MON`\n"
            else:
                # Other verified token
                message = f"💰 *{escape_markdown(name)} Received\\!*\n\n"
                message += f"*Token:* {escape_markdown(symbol)}\n"
                message += f"*Amount:* `\\+{escape_markdown(f'{balance_increase:.4f}')} {escape_markdown(symbol)}`\n"
                message += f"*New Balance:* `{escape_markdown(f'{balance:.4f}')} {escape_markdown(symbol)}`\n"
            
            # Add explorer link for transaction
            tx_hash = token.get('tx_hash')
            if tx_hash and BLOCK_EXPLORER_URL:
                explorer_link = f"{BLOCK_EXPLORER_URL}/tx/{tx_hash}"
                message += f"\n🔗 [View Transaction]({explorer_link})"
            elif BLOCK_EXPLORER_URL:
                # Fallback to wallet if no tx hash found
                from database import db_manager as db
                user_obj = db.get_user(user_id)
                if user_obj:
                    explorer_link = f"{BLOCK_EXPLORER_URL}/address/{user_obj.wallet_address}"
                    message += f"\n🔗 [View Wallet on Explorer]({explorer_link})"
        else:
            # New token received
            message = f"🎉 *New Token Received\\!*\n\n"
            message += f"*Token:* {escape_markdown(symbol)}"
            
            if name != symbol:
                message += f" \\({escape_markdown(name)}\\)"
            
            message += f"\n*Amount:* `{escape_markdown(f'{balance:.4f}')} {escape_markdown(symbol)}`\n"
            
            # Add explorer link if available
            if address and BLOCK_EXPLORER_URL:
                explorer_link = f"{BLOCK_EXPLORER_URL}/token/{address}"
                message += f"\n🔗 [View on Explorer]({explorer_link})"
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
            print(f"✅ Notification sent to {user_id}: {symbol}")
        except Exception as e:
            print(f"⚠️ Failed to send notification to {user_id}: {e}")

async def check_user_for_new_tokens(bot: Bot, user, wallet_address: str):
    """
    Check a single user's wallet for new verified tokens
    
    Args:
        bot: Telegram Bot instance
        user: User object from database
        wallet_address: User's wallet address
    """
    try:
        telegram_id = user.telegram_id
        
        # Get current tokens from blockchain
        current_tokens = blockchain_manager.get_wallet_all_tokens(wallet_address)
        
        if not current_tokens:
            return
        
        # Get last known snapshot
        last_snapshot = db_manager.get_token_snapshot(telegram_id)
        
        # If first run (empty snapshot), just initialize and skip notifications
        if not last_snapshot:
            print(f"📸 First run for user {telegram_id}: Initializing snapshot (no notifications)")
            db_manager.update_token_snapshot(telegram_id, current_tokens)
            return
        
        # Find new verified tokens OR native MON increase
        new_tokens = []
        print(f"🔍 Comparing {len(current_tokens)} current tokens with {len(last_snapshot)} snapshot tokens for user {telegram_id}")
        
        for symbol, token_data in current_tokens.items():
            # Check if token is new (not in last snapshot)
            is_new = symbol not in last_snapshot
            
            # Debug: Log token check
            if is_new and token_data.get('verified'):
                print(f"  🆕 Found NEW verified token: {symbol} (balance: {token_data.get('balance')})")
            
            # For native MON, check if balance increased
            if symbol in ['MON', 'MONAD']:
                if not is_new and symbol in last_snapshot:
                    old_balance = float(last_snapshot[symbol].get('balance', 0))
                    new_balance = float(token_data.get('balance', 0))
                    # Only notify if balance increased (received MON)
                    if new_balance > old_balance:
                        balance_increase = new_balance - old_balance
                        token_data['balance_increase'] = balance_increase
                        
                        # Try to find the transaction hash using Alchemy API (fast & reliable)
                        try:
                            import requests
                            from config import ALCHEMY_MONAD_URL
                            
                            # Use Alchemy getAssetTransfers to get recent transactions
                            payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "alchemy_getAssetTransfers",
                                "params": [{
                                    "toAddress": wallet_address,
                                    "category": ["external"],  # Native MON transfers only
                                    "order": "desc",  # Most recent first
                                    "maxCount": "0xa",  # Last 10 transactions
                                    "withMetadata": True
                                }]
                            }
                            
                            response = requests.post(ALCHEMY_MONAD_URL, json=payload, timeout=5)
                            
                            if response.ok:
                                data = response.json()
                                if 'result' in data:
                                    transfers = data['result'].get('transfers', [])
                                    
                                    # Find transaction matching the balance increase
                                    for tx in transfers:
                                        tx_value = float(tx.get('value', 0))
                                        # Match with tolerance (0.001 MON)
                                        if abs(tx_value - balance_increase) < 0.001:
                                            token_data['tx_hash'] = tx.get('hash')
                                            print(f"🔔 Found TX via Alchemy: {tx.get('hash')}")
                                            break
                                else:
                                    print(f"⚠️ Alchemy response missing result: {data}")
                            else:
                                print(f"⚠️ Alchemy API failed: {response.status_code}")
                                
                        except Exception as e:
                            print(f"⚠️ Could not fetch TX hash: {e}")
                        
                        new_tokens.append(token_data)
                        print(f"🔔 Native MON received for user {telegram_id}: +{balance_increase} MON")
                continue
            
            # For other tokens: only notify for verified tokens
            if not token_data.get('verified'):
                if is_new:
                    print(f"  ⏭️ Skipping non-verified new token: {symbol}")
                continue
            
            # For verified tokens: notify for NEW token OR balance increase
            if is_new:
                # New token
                balance = token_data.get('balance', 0)
                print(f"  ✅ New verified token qualifies: {symbol}, balance={balance}")
                if balance > 0:
                    new_tokens.append(token_data)
                    print(f"🔔 New verified token detected for user {telegram_id}: {symbol} ({balance})")
                else:
                    print(f"  ⚠️ Skipped: balance is 0")
            elif symbol in last_snapshot:
                # Existing token - check if balance increased
                old_balance = float(last_snapshot[symbol].get('balance', 0))
                new_balance = float(token_data.get('balance', 0))
                if new_balance > old_balance:
                    balance_increase = new_balance - old_balance
                    token_data['balance_increase'] = balance_increase
                    
                    # Try to find the transaction hash for ERC20 token transfer
                    print(f"🔍 Searching ERC20 TX for {symbol}: +{balance_increase}")
                    try:
                        import requests
                        from config import ALCHEMY_MONAD_URL
                        
                        # Use Alchemy getAssetTransfers for ERC20 tokens
                        payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "alchemy_getAssetTransfers",
                            "params": [{
                                "toAddress": wallet_address,
                                "category": ["erc20"],  # ERC20 token transfers
                                "order": "desc",
                                "maxCount": "0xa",  # Last 10 transactions
                                "withMetadata": True
                            }]
                        }
                        
                        response = requests.post(ALCHEMY_MONAD_URL, json=payload, timeout=5)
                        
                        if response.ok:
                            data = response.json()
                            if 'result' in data:
                                transfers = data['result'].get('transfers', [])
                                print(f"  📦 Got {len(transfers)} ERC20 transfers from Alchemy")
                                
                                # Find transaction matching token address and amount
                                token_address = token_data.get('address', '').lower()
                                print(f"  🔍 Looking for token: {token_address}, amount: {balance_increase}")
                                
                                for i, tx in enumerate(transfers):
                                    tx_token = tx.get('rawContract', {}).get('address', '').lower()
                                    tx_value = float(tx.get('value', 0))
                                    tx_hash = tx.get('hash')
                                    
                                    print(f"  TX {i+1}: {tx_hash}")
                                    print(f"    Token: {tx_token} (match: {tx_token == token_address})")
                                    print(f"    Amount: {tx_value} (diff: {abs(tx_value - balance_increase)})")
                                    
                                    # Match by token address and amount
                                    if tx_token == token_address and abs(tx_value - balance_increase) < 0.001:
                                        token_data['tx_hash'] = tx_hash
                                        print(f"  ✅ MATCH! Found TX via Alchemy: {tx_hash}")
                                        break
                                else:
                                    print(f"  ❌ No matching TX found in {len(transfers)} transfers")
                            else:
                                print(f"⚠️ Alchemy ERC20 response missing result: {data}")
                        else:
                            print(f"⚠️ Alchemy ERC20 API failed: {response.status_code}")
                    
                    except Exception as e:
                        print(f"⚠️ Could not fetch ERC20 TX hash: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    new_tokens.append(token_data)
                    print(f"🔔 Verified token received for user {telegram_id}: +{balance_increase} {symbol}")
        
        # Send notifications for new tokens
        if new_tokens:
            await send_token_notification(bot, telegram_id, new_tokens)
        
        # Update snapshot with current tokens
        db_manager.update_token_snapshot(telegram_id, current_tokens)
        
    except Exception as e:
        print(f"⚠️ Error checking tokens for user {user.telegram_id}: {e}")

async def monitor_tokens(bot: Bot):
    """
    Background task to monitor all users' wallets for new tokens
    Runs every 30 seconds (faster notifications)
    
    Args:
        bot: Telegram Bot instance
    """
    print("🔔 Notification monitor started (30s interval)")
    
    while True:
        try:
            # Get all users with notifications enabled
            users = db_manager.get_users_with_notifications()
            
            if not users:
                print("⏸️ No users with notifications enabled")
            else:
                print(f"🔍 Checking {len(users)} users for new tokens...")
                
                for user in users:
                    # Check each user
                    await check_user_for_new_tokens(bot, user, user.wallet_address)
                    
                    # Small delay between users to avoid rate limits
                    await asyncio.sleep(1)
            
        except Exception as e:
            print(f"⚠️ Monitor error: {e}")
        
        # Wait 30 seconds before next check (faster!)
        await asyncio.sleep(30)
