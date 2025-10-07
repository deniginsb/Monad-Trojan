"""
Notification Monitor - Background task to monitor wallet for new tokens
Sends Telegram notifications when new verified tokens are detected
"""
import asyncio
from typing import List, Dict
from telegram import Bot
from telegram.constants import ParseMode
from blockchain import blockchain_manager
from database import db_manager
from config import BLOCK_EXPLORER_URL

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
        
        # Build message
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
        current_tokens = blockchain_manager.get_wallet_all_tokens(wallet_address, telegram_id)
        
        if not current_tokens:
            return
        
        # Get last known snapshot
        last_snapshot = db_manager.get_token_snapshot(telegram_id)
        
        # Find new verified tokens
        new_tokens = []
        for symbol, token_data in current_tokens.items():
            # Only notify for verified tokens
            if not token_data.get('verified'):
                continue
            
            # Skip native token
            if symbol in ['MON', 'MONAD']:
                continue
            
            # Check if token is new (not in last snapshot)
            if symbol not in last_snapshot:
                # Check if balance > 0
                if token_data.get('balance', 0) > 0:
                    new_tokens.append(token_data)
                    print(f"🔔 New verified token detected for user {telegram_id}: {symbol} ({token_data.get('balance')})")
        
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
    Runs every 60 seconds
    
    Args:
        bot: Telegram Bot instance
    """
    print("🔔 Notification monitor started")
    
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
                    await asyncio.sleep(2)
            
        except Exception as e:
            print(f"⚠️ Monitor error: {e}")
        
        # Wait 60 seconds before next check
        await asyncio.sleep(60)
