"""
MonadTrojan Bot - Main Bot File
Secure Trading Bot for Monad Testnet
"""
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import (
    TELEGRAM_BOT_TOKEN, WELCOME_MESSAGE, WALLET_INFO_TEMPLATE,
    NATIVE_CURRENCY, QUICK_BUY_AMOUNTS, QUICK_SELL_PERCENTAGES,
    SLIPPAGE_OPTIONS, BLOCK_EXPLORER_URL, MONAD_TESTNET_RPC_URL,
    DEX_ROUTER_ADDRESS
)
from database import db_manager
from blockchain import blockchain_manager
from security_passphrase import validate_passphrase
from portfolio import get_portfolio_text

# Conversation states
AWAITING_TOKEN_ADDRESS = 1
AWAITING_BUY_AMOUNT = 2
AWAITING_SELL_PERCENTAGE = 3
AWAITING_PRIVATE_KEY = 4
AWAITING_CUSTOM_SLIPPAGE = 5
AWAITING_BUY_CUSTOM_AMOUNT = 6
AWAITING_SELL_CUSTOM_AMOUNT = 7
AWAITING_SET_PASSPHRASE = 8
AWAITING_CONFIRM_PASSPHRASE = 9
AWAITING_TRANSACTION_PASSPHRASE = 10

# Temporary storage for ongoing transactions
user_context: Dict[int, Dict] = {}

def escape_markdown(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def safe_edit_message(query, text, **kwargs):
    """Safely edit message, catching BadRequest if message content is identical"""
    try:
        return await query.edit_message_text(text, **kwargs)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Message content is identical, no need to update
            return None
        raise

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🚀 Buy Token", callback_data="buy_token"),
            InlineKeyboardButton("💹 Sell Token", callback_data="sell_token")
        ],
        [
            InlineKeyboardButton("💼 My Wallet", callback_data="wallet"),
            InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_wallet_menu_keyboard() -> InlineKeyboardMarkup:
    """Get wallet management keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance")],
        [
            InlineKeyboardButton("➕ Import Wallet", callback_data="import_wallet"),
            InlineKeyboardButton("🗑️ Create New Wallet", callback_data="create_new_wallet")
        ],
        [InlineKeyboardButton("🔑 Show Private Key", callback_data="show_private_key")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard(current_settings: Dict) -> InlineKeyboardMarkup:
    """Get settings keyboard"""
    slippage = current_settings.get('slippage', 1.0)
    gas_mode = current_settings.get('gas_price_mode', 'normal')
    anti_mev = current_settings.get('anti_mev', 0)
    
    keyboard = [
        [InlineKeyboardButton(f"📊 Slippage: {slippage}%", callback_data="set_slippage")],
        [InlineKeyboardButton(f"⛽ Gas: {gas_mode.upper()}", callback_data="set_gas")],
        [InlineKeyboardButton(f"🛡️ Anti-MEV: {'ON' if anti_mev else 'OFF'}", callback_data="toggle_mev")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user_id = update.effective_user.id
    
    user = db_manager.get_user(user_id)
    
    if not user:
        # New user - must import private key first
        keyboard = [
            [InlineKeyboardButton("🔑 Import Private Key", callback_data="import_wallet_first")],
        ]
        
        await update.message.reply_text(
            "👋 *Welcome to MonadTrojan Bot\\!*\n\n"
            "🔐 To start trading, you must import your private key first\\.\n\n"
            "⚠️ *Important:*\n"
            "• Private key will be encrypted securely\n"
            "• Never stored as plain text\n"
            "• Only you can access your wallet\n\n"
            "Click the button below to import your private key:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Existing user - show main menu
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_menu_keyboard()
    )

async def show_wallet_info(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    """Show wallet information with balances"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if edit and query:
        await query.answer()
        message = query.message
    else:
        message = update.message
    
    loading_text = "🔍 *Checking balance on blockchain\\.\\.\\.*"
    
    if edit:
        await message.edit_text(loading_text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        sent_message = await message.reply_text(loading_text, parse_mode=ParseMode.MARKDOWN_V2)
        message = sent_message
    
    user = db_manager.get_user(user_id)
    
    if not user:
        await message.edit_text("❌ Wallet not found\\. Please use /start")
        return
    
    address = user.wallet_address
    
    # Get all tokens using BlockVision API
    all_tokens = blockchain_manager.get_wallet_all_tokens(address)
    
    # Fallback: If BlockVision only returned MON or nothing, check token history
    non_native_tokens_count = sum(1 for s in all_tokens.keys() if s not in ['MON', 'MONAD'])
    if non_native_tokens_count == 0:
        user_token_addresses = db_manager.get_user_tokens(user_id)
        
        if user_token_addresses:
            print(f"📋 Wallet view: Found {len(user_token_addresses)} tokens in history, checking balances...")
            history_tokens = blockchain_manager.get_tokens_from_history(
                address, 
                user_token_addresses
            )
            
            # Merge with all_tokens (history tokens take precedence for duplicates)
            for symbol, token_data in history_tokens.items():
                if symbol not in all_tokens or all_tokens[symbol]['balance'] == 0:
                    all_tokens[symbol] = token_data
            
            if len(history_tokens) > 1:  # More than just MON
                print(f"✅ Wallet view: Added tokens from history")
    
    native_balance = Decimal('0')
    token_list = ""
    
    if all_tokens:
        for symbol, token_data in all_tokens.items():
            balance = token_data['balance']
            
            # Track MON balance separately
            if symbol == 'MON' or symbol == 'MONAD':
                native_balance = balance
            
            # Format balance
            if balance < Decimal('0.0001'):
                balance_str = f"{balance:.8f}"
            elif balance < Decimal('1'):
                balance_str = f"{balance:.6f}"
            else:
                balance_str = f"{balance:.4f}"
            
            symbol_esc = escape_markdown(symbol)
            balance_esc = escape_markdown(balance_str)
            
            # Add verified badge
            verified = token_data.get('verified', False)
            badge = " ✓" if verified else ""
            
            token_list += f"   • {balance_esc} {symbol_esc}{badge}\n"
    else:
        token_list = "   _No tokens yet_\n"
    
    explorer_url = f"{BLOCK_EXPLORER_URL}/address/{address}"
    
    wallet_text = WALLET_INFO_TEMPLATE.format(
        address=escape_markdown(address),
        explorer_url=explorer_url,
        native_balance=escape_markdown(f"{native_balance:.4f}"),
        currency=NATIVE_CURRENCY,
        token_list=token_list,
        total_value=escape_markdown(f"{native_balance:.4f} {NATIVE_CURRENCY}"),
        timestamp=escape_markdown(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    
    try:
        await message.edit_text(
            wallet_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_wallet_menu_keyboard(),
            disable_web_page_preview=True
        )
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button callbacks"""
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data
    
    await query.answer()
    
    if data == "main_menu":
        await safe_edit_message(
            query,
            WELCOME_MESSAGE,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    elif data == "import_wallet_first":
        # New user wants to import wallet
        await query.edit_message_text(
            "🔑 *Import Private Key*\n\n"
            "Please send your private key\\.\n\n"
            "⚠️ *Security:*\n"
            "• Private key will be encrypted\n"
            "• Message will be auto-deleted\n"
            "• Never share your private key with anyone\n\n"
            "Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_PRIVATE_KEY
    
    elif data == "import_mode_quick":
        # User chose quick mode (no passphrase)
        user_id = update.effective_user.id
        private_key = context.user_data.get('pending_private_key')
        address = context.user_data.get('pending_address')
        
        if not private_key or not address:
            await query.edit_message_text("❌ Session expired\\. Please start again\\.")
            return ConversationHandler.END
        
        # Store with simple encryption (no passphrase)
        db_manager.update_user_wallet(user_id, address, private_key, passphrase=None)
        
        # Cleanup
        del context.user_data['pending_private_key']
        del context.user_data['pending_address']
        del private_key
        
        await query.edit_message_text(
            f"✅ *Wallet Imported \\(Quick Mode\\)\\!*\n\n"
            f"📍 Address: `{escape_markdown(address[:10])}...{escape_markdown(address[-8:])}`\n\n"
            f"🚀 Your wallet is ready for trading\\!\n\n"
            f"🔐 *Security:* Encrypted with master key\n"
            f"⚡ *Speed:* Instant transactions \\(no passphrase needed\\)",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    elif data == "import_mode_secure":
        # User chose secure mode (with passphrase)
        await query.edit_message_text(
            "🔐 *Secure Mode: Set Passphrase*\n\n"
            "Create a strong passphrase to protect your key\\.\n\n"
            "⚠️ *CRITICAL WARNING:*\n"
            "• If you forget this passphrase, your key is *LOST FOREVER*\n"
            "• Developer *CANNOT* recover it\n"
            "• No \\'forgot password\\' option exists\n\n"
            "✅ *Requirements:*\n"
            "• Minimum 8 characters\n"
            "• 12\\+ characters recommended\n"
            "• Mix of letters, numbers, symbols\n\n"
            "Enter your passphrase:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SET_PASSPHRASE
    
    elif data == "wallet" or data == "refresh_balance":
        await show_wallet_info(update, context, edit=True)
        return ConversationHandler.END
    
    elif data == "portfolio":
        # Show portfolio with enhanced visualization
        user = db_manager.get_user(user_id)
        if not user:
            await query.edit_message_text(
                "❌ *Wallet not found*\n\nPlease use /start to set up your wallet\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
        
        # Show loading message
        await query.edit_message_text(
            "📊 *Loading portfolio\\.\\.\\.*\n\n"
            "Fetching balances and calculating allocation\\.\\.\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        try:
            # Get portfolio text with price estimates
            portfolio_text = get_portfolio_text(
                user_id=user_id,
                wallet_address=user.wallet_address,
                include_prices=True
            )
            
            # Create back button keyboard
            keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Update message with portfolio
            await query.edit_message_text(
                portfolio_text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            print(f"❌ Portfolio error: {e}")
            import traceback
            traceback.print_exc()
            
            await query.edit_message_text(
                "❌ *Error loading portfolio*\n\n"
                f"Failed to fetch portfolio data\\. Please try again\\.\n\n"
                f"_Error: {escape_markdown(str(e))}_",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
                ]])
            )
        
        return ConversationHandler.END
    
    elif data == "buy_token":
        await query.edit_message_text(
            "🚀 *Buy Token*\n\n"
            "Please send the *Contract Address* of the token you want to buy\\.\n\n"
            "Example: `0x1234...abcd`\n\n"
            "Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_TOKEN_ADDRESS
    
    elif data == "buy_custom":
        # Request custom buy amount input
        await query.edit_message_text(
            "✏️ *Enter MON Amount*\n\n"
            "Enter the amount of MON you want to use for buying\\.\n\n"
            "Example: `0.3` or `1.5` or `10`\n\n"
            "Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_BUY_CUSTOM_AMOUNT
    
    elif data.startswith("buy_"):
        # Handle buy amount buttons (buy_0.1, buy_0.5, etc)
        return await handle_buy_amount(update, context)
    
    elif data == "sell_token":
        user = db_manager.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ Wallet not found\\.")
            return ConversationHandler.END
        
        # Get all tokens from BlockVision API (verified only)
        all_tokens = blockchain_manager.get_wallet_all_tokens(user.wallet_address)
        
        # Filter: only verified tokens, exclude MON (native)
        sellable_tokens = {}
        for symbol, token_data in all_tokens.items():
            if token_data.get('verified', False) and symbol not in ['MON', 'MONAD']:
                # Only include tokens with balance > 0
                if token_data['balance'] > 0:
                    sellable_tokens[symbol] = token_data
        
        # Fallback: If no sellable tokens from BlockVision, try token history
        if not sellable_tokens:
            print(f"📋 No tokens from BlockVision, checking token history for user {user_id}")
            user_token_addresses = db_manager.get_user_tokens(user_id)
            
            if user_token_addresses:
                print(f"📋 Found {len(user_token_addresses)} tokens in history, checking balances...")
                history_tokens = blockchain_manager.get_tokens_from_history(
                    user.wallet_address, 
                    user_token_addresses
                )
                
                # Filter out MON/MONAD
                for symbol, token_data in history_tokens.items():
                    if symbol not in ['MON', 'MONAD'] and token_data['balance'] > 0:
                        sellable_tokens[symbol] = token_data
                
                if sellable_tokens:
                    print(f"✅ Found {len(sellable_tokens)} sellable tokens from history")
        
        if not sellable_tokens:
            await safe_edit_message(
                query,
                "❌ You don't have any verified tokens to sell\\.\n\n"
                "Only verified tokens can be sold\\!",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=get_main_menu_keyboard()
            )
            return ConversationHandler.END
        
        keyboard = []
        for symbol, token_data in sellable_tokens.items():
            balance = token_data['balance']
            # Format balance
            if balance < Decimal('0.0001'):
                balance_str = f"{balance:.8f}"
            elif balance < Decimal('1'):
                balance_str = f"{balance:.6f}"
            else:
                balance_str = f"{balance:.4f}"
            
            button_text = f"{symbol} ({balance_str})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{token_data['address']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
        
        await safe_edit_message(
            query,
            "💹 *Sell Token*\n\n"
            "Select the verified token you want to sell:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data == "sell_custom":
        # Request custom sell amount input - MUST BE BEFORE general sell_ handler!
        if user_id not in user_context or user_context[user_id].get('action') != 'sell':
            await query.edit_message_text("❌ Session expired\\. Please start again\\.")
            return ConversationHandler.END
        
        token_address = user_context[user_id]['token_address']
        info = blockchain_manager.get_token_info(token_address)
        user = db_manager.get_user(user_id)
        balance, _ = blockchain_manager.get_token_balance(token_address, user.wallet_address)
        
        await query.edit_message_text(
            f"✏️ *Enter Amount {escape_markdown(info['symbol'])}*\n\n"
            f"Balance: {escape_markdown(f'{balance:.4f}')} {escape_markdown(info['symbol'])}\n\n"
            f"Enter the amount of {escape_markdown(info['symbol'])} you want to sell\\.\n\n"
            f"Example: `50` or `100\\.5` or `{escape_markdown(f'{balance:.2f}')}`\n\n"
            f"Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SELL_CUSTOM_AMOUNT
    
    elif data.startswith("sell_"):
        token_address = data[5:]
        user_context[user_id] = {'action': 'sell', 'token_address': token_address}
        
        info = blockchain_manager.get_token_info(token_address)
        if not info:
            await query.edit_message_text("❌ Failed to fetch token information\\.")
            return ConversationHandler.END
        
        user = db_manager.get_user(user_id)
        balance, _ = blockchain_manager.get_token_balance(token_address, user.wallet_address)
        
        keyboard = []
        for percentage in QUICK_SELL_PERCENTAGES:
            amount = balance * Decimal(percentage) / Decimal(100)
            button_text = f"Sell {percentage}% ({amount:.4f} {info['symbol']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"confirm_sell_{percentage}")])
        
        # Add custom input button
        keyboard.append([InlineKeyboardButton("✏️ Custom Amount", callback_data="sell_custom")])
        keyboard.append([InlineKeyboardButton("🔙 Batal", callback_data="main_menu")])
        
        await query.edit_message_text(
            f"💹 *Sell {escape_markdown(info['symbol'])}*\n\n"
            f"Balance: {escape_markdown(f'{balance:.4f}')} {escape_markdown(info['symbol'])}\n\n"
            f"Select percentage or custom amount:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data.startswith("confirm_sell_"):
        percentage = int(data.split("_")[-1])
        
        if user_id not in user_context or user_context[user_id].get('action') != 'sell':
            await query.edit_message_text("❌ Session expired\\. Please start again\\.")
            return ConversationHandler.END
        
        token_address = user_context[user_id]['token_address']
        
        await query.edit_message_text("⏳ *Processing sell transaction\\.\\.\\.*", parse_mode=ParseMode.MARKDOWN_V2)
        
        user = db_manager.get_user(user_id)
        balance, _ = blockchain_manager.get_token_balance(token_address, user.wallet_address)
        amount_to_sell = balance * Decimal(percentage) / Decimal(100)
        
        settings = db_manager.get_user_settings(user_id)
        slippage = settings.slippage if settings else 1.0
        gas_mode = settings.gas_price_mode if settings else 'normal'
        
        private_key = db_manager.get_decrypted_private_key(user_id)
        
        result = blockchain_manager.sell_token(
            token_address, amount_to_sell, user.wallet_address,
            private_key, slippage, gas_mode
        )
        
        private_key = None
        del private_key
        
        if result:
            info = blockchain_manager.get_token_info(token_address)
            tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
            
            db_manager.add_token_history(
                user_id, token_address, 'sell', str(amount_to_sell),
                result['tx_hash'], info['name'] if info else None,
                info['symbol'] if info else None
            )
            
            expected_output = float(result['expected_output'])
            
            success_msg = (
                f"✅ *Sell Transaction Successful\\!*\n\n"
                f"🪙 Token: {escape_markdown(info['symbol']) if info else 'Unknown'}\n"
                f"📊 Amount: {escape_markdown(f'{amount_to_sell:.4f}')}\n"
                f"💰 Estimasi: {escape_markdown(f'{expected_output:.4f}')} {NATIVE_CURRENCY}\n"
                f"🔗 [View Transaction]({tx_url})\n\n"
                f"⏰ Menunggu konfirmasi\\.\\.\\."
            )
            
            await query.edit_message_text(
                success_msg,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=get_main_menu_keyboard(),
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text(
                "❌ *Transaction Failed\\!*\n\n"
                "Please try again or check your balance and gas\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=get_main_menu_keyboard()
            )
        
        if user_id in user_context:
            del user_context[user_id]
        
        return ConversationHandler.END
    
    elif data == "settings":
        settings = db_manager.get_user_settings(user_id)
        settings_dict = {
            'slippage': settings.slippage if settings else 1.0,
            'gas_price_mode': settings.gas_price_mode if settings else 'normal',
            'anti_mev': settings.anti_mev if settings else 0,
            'notifications_enabled': settings.notifications_enabled if settings else 1
        }
        
        await safe_edit_message(
            query,
            "⚙️ *Settings Trading*\n\n"
            "Sesuaikan parameter trading Anda:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_settings_keyboard(settings_dict)
        )
        return ConversationHandler.END
    
    elif data == "set_slippage":
        keyboard = []
        for slippage in SLIPPAGE_OPTIONS:
            keyboard.append([InlineKeyboardButton(f"{slippage}%", callback_data=f"slippage_{slippage}")])
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="settings")])
        
        await query.edit_message_text(
            "📊 *Select Slippage Tolerance*\n\n"
            "Slippage is the tolerance for price changes during transaction\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data.startswith("slippage_"):
        slippage = float(data.split("_")[1])
        db_manager.update_user_settings(user_id, slippage=slippage)
        
        await query.answer(f"✅ Slippage diatur ke {slippage}%")
        
        settings = db_manager.get_user_settings(user_id)
        settings_dict = {
            'slippage': settings.slippage,
            'gas_price_mode': settings.gas_price_mode,
            'anti_mev': settings.anti_mev,
            'notifications_enabled': settings.notifications_enabled
        }
        
        await query.edit_message_text(
            "⚙️ *Settings Trading*\n\n"
            "Sesuaikan parameter trading Anda:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_settings_keyboard(settings_dict)
        )
        return ConversationHandler.END
    
    elif data == "set_gas":
        keyboard = [
            [InlineKeyboardButton("🐢 Normal", callback_data="gas_normal")],
            [InlineKeyboardButton("🚗 Fast", callback_data="gas_fast")],
            [InlineKeyboardButton("🚀 Very Fast", callback_data="gas_very_fast")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="settings")]
        ]
        
        await query.edit_message_text(
            "⛽ *Select Gas Price Mode*\n\n"
            "Gas mode determines transaction confirmation speed\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data.startswith("gas_"):
        gas_mode = data.split("_")[1]
        db_manager.update_user_settings(user_id, gas_price_mode=gas_mode)
        
        await query.answer(f"✅ Gas mode diatur ke {gas_mode.upper()}")
        
        settings = db_manager.get_user_settings(user_id)
        settings_dict = {
            'slippage': settings.slippage,
            'gas_price_mode': settings.gas_price_mode,
            'anti_mev': settings.anti_mev,
            'notifications_enabled': settings.notifications_enabled
        }
        
        await query.edit_message_text(
            "⚙️ *Settings Trading*\n\n"
            "Sesuaikan parameter trading Anda:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_settings_keyboard(settings_dict)
        )
        return ConversationHandler.END
    
    elif data == "toggle_mev":
        settings = db_manager.get_user_settings(user_id)
        current_mev = settings.anti_mev if settings else 0
        new_mev = 0 if current_mev else 1
        
        db_manager.update_user_settings(user_id, anti_mev=new_mev)
        
        await query.answer(f"✅ Anti-MEV {'diaktifkan' if new_mev else 'dinonaktifkan'}")
        
        settings = db_manager.get_user_settings(user_id)
        settings_dict = {
            'slippage': settings.slippage,
            'gas_price_mode': settings.gas_price_mode,
            'anti_mev': settings.anti_mev,
            'notifications_enabled': settings.notifications_enabled
        }
        
        await query.edit_message_text(
            "⚙️ *Settings Trading*\n\n"
            "Sesuaikan parameter trading Anda:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_settings_keyboard(settings_dict)
        )
        return ConversationHandler.END
    
    elif data == "import_wallet":
        await query.edit_message_text(
            "🔑 *Import Wallet*\n\n"
            "⚠️ *PERINGATAN:* Jangan pernah membagikan private key Anda\\!\n\n"
            "Kirim private key Anda \\(dengan or tanpa 0x\\)\\.\n"
            "Private key will be encrypted dan disimpan dengan aman\\.\n\n"
            "Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_PRIVATE_KEY
    
    elif data == "show_private_key":
        keyboard = [
            [InlineKeyboardButton("✅ Ya, Tampilkan", callback_data="confirm_show_pk")],
            [InlineKeyboardButton("❌ Batal", callback_data="wallet")]
        ]
        
        await query.edit_message_text(
            "⚠️ *PERINGATAN KEAMANAN*\n\n"
            "Anda akan melihat private key Anda\\.\n"
            "Pastikan tidak ada orang lain yang melihat layar Anda\\!\n\n"
            "Lanjutkan\\?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data == "confirm_show_pk":
        user = db_manager.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ Wallet not found\\.")
            return ConversationHandler.END
        
        private_key = db_manager.get_decrypted_private_key(user_id)
        
        await query.edit_message_text(
            f"🔑 *Private Key Anda*\n\n"
            f"`{escape_markdown(private_key)}`\n\n"
            f"⚠️ *JANGAN BAGIKAN KE SIAPAPUN\\!*\n\n"
            f"Pesan ini akan dihapus dalam 60 detik\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_wallet_menu_keyboard()
        )
        
        private_key = None
        del private_key
        
        await asyncio.sleep(60)
        
        try:
            await query.message.delete()
        except:
            pass
        
        return ConversationHandler.END
    
    elif data == "create_new_wallet":
        keyboard = [
            [InlineKeyboardButton("✅ Ya, Buat Baru", callback_data="confirm_new_wallet")],
            [InlineKeyboardButton("❌ Batal", callback_data="wallet")]
        ]
        
        await query.edit_message_text(
            "⚠️ *PERINGATAN*\n\n"
            "Membuat wallet baru akan menghapus wallet lama Anda\\.\n"
            "Pastikan Anda telah mencadangkan private key lama\\!\n\n"
            "Lanjutkan\\?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    elif data == "confirm_new_wallet":
        address, private_key = blockchain_manager.create_wallet()
        db_manager.update_user_wallet(user_id, address, private_key)
        private_key = None
        del private_key
        
        await query.edit_message_text(
            f"✅ *New Wallet Successfully Created\\!*\n\n"
            f"Alamat: `{escape_markdown(address)}`\n\n"
            f"Please save your private key securely\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_wallet_menu_keyboard()
        )
        return ConversationHandler.END
    
    elif data == "help":
        help_text = (
            "❓ *Bantuan MonadTrojan Bot*\n\n"
            "*Fitur Utama:*\n"
            "🚀 *Buy Token* \\- Beli token ERC\\-20 dengan MONAD\n"
            "💹 *Sell Token* \\- Sell tokens to get MONAD\n"
            "💼 *Wallet* \\- Manage wallet and check balance\n"
            "⚙️ *Settings* \\- Atur slippage, gas, dan anti\\-MEV\n\n"
            "*Security:*\n"
            "• Private key dienkripsi dengan AES\\-128\n"
            "• Never stored as plain text\n"
            "• Only decrypted when signing transactions\n\n"
            "*Commands:*\n"
            "/start \\- Mulai bot\n"
            "/cancel \\- Batalkan operasi\n\n"
            "⚠️ *Ini adalah TESTNET\\. Jangan gunakan private key mainnet\\!*"
        )
        
        await safe_edit_message(
            query,
            help_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    return ConversationHandler.END

async def handle_token_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle token address input for buying"""
    user_id = update.effective_user.id
    token_address = update.message.text.strip()
    
    if not blockchain_manager.validate_address(token_address):
        await update.message.reply_text(
            "❌ Invalid token address\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_TOKEN_ADDRESS
    
    loading_msg = await update.message.reply_text("🔍 Mengambil informasi token\\.\\.\\.")
    
    info = blockchain_manager.get_token_info(token_address)
    
    if not info:
        await loading_msg.edit_text(
            "❌ Failed to fetch token information\\. Make sure the address is correct\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        await update.message.reply_text(
            "Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Update loading message
    await loading_msg.edit_text("🔍 Mengambil informasi token\\.\\.\\.\n⏳ Checking price\\.\\.\\.")
    
    price = blockchain_manager.get_token_price_in_native(token_address)
    
    # Log for debugging
    print(f"Token: {info['symbol']}, Price: {price}")
    
    user_context[user_id] = {'action': 'buy', 'token_address': token_address, 'token_info': info}
    
    keyboard = []
    for amount in QUICK_BUY_AMOUNTS:
        button_text = f"Buy {amount} {NATIVE_CURRENCY}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"buy_{amount}")])
    
    # Add custom input button
    keyboard.append([InlineKeyboardButton("✏️ Custom Amount", callback_data="buy_custom")])
    keyboard.append([InlineKeyboardButton("🔙 Batal", callback_data="main_menu")])
    
    # Format price display
    if price and price > 0:
        # Check if price is very small
        if price < 0.00000001:
            price_text = f"{escape_markdown(f'{price:.12f}')} USD"
        elif price < 0.0001:
            price_text = f"${escape_markdown(f'{price:.8f}')}"
        else:
            price_text = f"${escape_markdown(f'{price:.4f}')}"
    else:
        price_text = "_Not available_"
        print(f"⚠️ Price not available for {info['symbol']}")
    
    token_text = (
        f"🚀 *Buy {escape_markdown(info['symbol'])}*\n\n"
        f"📝 Nama: {escape_markdown(info['name'])}\n"
        f"🔤 Simbol: {escape_markdown(info['symbol'])}\n"
        f"🏷️ Address: `{escape_markdown(token_address[:10])}...{escape_markdown(token_address[-8:])}`\n"
        f"💰 Price: {price_text}\n\n"
        f"Select amount {NATIVE_CURRENCY} to use:"
    )
    
    print(f"📊 Displaying token: {info['symbol']}, Price: {price}")
    
    await update.message.reply_text(
        token_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

async def handle_buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle buy amount from button callback"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    if user_id not in user_context or user_context[user_id].get('action') != 'buy':
        await query.edit_message_text("❌ Session expired\\. Please start again\\.")
        return ConversationHandler.END
    
    amount_str = query.data.split("_")[1]
    amount = Decimal(amount_str)
    
    token_address = user_context[user_id]['token_address']
    token_info = user_context[user_id]['token_info']
    
    user = db_manager.get_user(user_id)
    settings = db_manager.get_user_settings(user_id)
    slippage = settings.slippage if settings else 1.0
    gas_mode = settings.gas_price_mode if settings else 'normal'
    
    # Check if user has passphrase-protected wallet
    if user and user.passphrase_salt:
        # Secure mode - need passphrase
        context.user_data['pending_buy'] = {
            'token_address': token_address,
            'amount': amount,
            'slippage': slippage,
            'gas_mode': gas_mode
        }
        context.user_data['current_token_info'] = token_info
        
        await query.edit_message_text(
            "🔐 *Enter Passphrase*\\n\\n"
            "Enter your passphrase to sign this transaction:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        return AWAITING_TRANSACTION_PASSPHRASE
    
    # Quick mode - proceed normally
    await query.edit_message_text("⏳ *Processing buy transaction\\.\\.\\.*", parse_mode=ParseMode.MARKDOWN_V2)
    
    private_key = db_manager.get_decrypted_private_key(user_id)
    
    result = blockchain_manager.buy_token(
        token_address, amount, user.wallet_address,
        private_key, slippage, gas_mode
    )
    
    private_key = None
    del private_key
    
    if result:
        tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
        
        db_manager.add_token_history(
            user_id, token_address, 'buy', str(amount),
            result['tx_hash'], token_info['name'], token_info['symbol']
        )
        
        success_msg = (
            f"✅ *Buy Transaction Successful\\!*\n\n"
            f"🪙 Token: {escape_markdown(token_info['symbol'])}\n"
            f"💰 Amount: {escape_markdown(str(amount))} {NATIVE_CURRENCY}\n"
            f"🔗 [View Transaction]({tx_url})\n\n"
            f"⏰ Menunggu konfirmasi\\.\\.\\."
        )
        
        await query.edit_message_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard(),
            disable_web_page_preview=True
        )
    else:
        await query.edit_message_text(
            "❌ *Transaction Failed\\!*\n\n"
            "Please try again or check your balance and gas\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
    
    if user_id in user_context:
        del user_context[user_id]
    
    return ConversationHandler.END

async def handle_private_key_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle private key import - ask user to choose security mode"""
    user_id = update.effective_user.id
    private_key = update.message.text.strip()
    
    await update.message.delete()
    
    address = blockchain_manager.validate_private_key(private_key)
    
    if not address:
        await update.message.reply_text(
            "❌ Invalid private key\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_PRIVATE_KEY
    
    # Store temporarily for next step
    context.user_data['pending_private_key'] = private_key
    context.user_data['pending_address'] = address
    
    # Ask user to choose security mode
    keyboard = [
        [InlineKeyboardButton("🚀 Quick Mode (Simple)", callback_data="import_mode_quick")],
        [InlineKeyboardButton("🔐 Secure Mode (Passphrase)", callback_data="import_mode_secure")],
    ]
    
    await update.message.reply_text(
        "🔒 *Choose Security Mode*\n\n"
        "*Quick Mode:*\n"
        "• Fast and easy\n"
        "• Encrypted with master key\n"
        "• Good for testnet\n\n"
        "*Secure Mode:*\n"
        "• Zero\\-knowledge encryption\n"
        "• Protected by YOUR passphrase\n"
        "• Developer CANNOT access your key\n"
        "• ⚠️ Forget passphrase = LOST FOREVER\n\n"
        "Which mode do you prefer?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return AWAITING_PRIVATE_KEY

async def handle_buy_custom_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom buy amount input from user"""
    user_id = update.effective_user.id
    amount_text = update.message.text.strip()
    
    # Validate amount
    try:
        amount = Decimal(amount_text)
        if amount <= 0:
            await update.message.reply_text(
                "❌ Amount must be greater than 0\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return AWAITING_BUY_CUSTOM_AMOUNT
    except:
        await update.message.reply_text(
            "❌ Invalid amount\\. Enter a number like: 0\\.3, 1\\.5, 10",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_BUY_CUSTOM_AMOUNT
    
    if user_id not in user_context or user_context[user_id].get('action') != 'buy':
        await update.message.reply_text("❌ Session expired\\. Please start again\\.")
        return ConversationHandler.END
    
    token_address = user_context[user_id]['token_address']
    token_info = user_context[user_id]['token_info']
    
    loading_msg = await update.message.reply_text("⏳ *Processing buy transaction\\.\\.\\.*", parse_mode=ParseMode.MARKDOWN_V2)
    
    user = db_manager.get_user(user_id)
    settings = db_manager.get_user_settings(user_id)
    slippage = settings.slippage if settings else 5.0
    gas_mode = settings.gas_price_mode if settings else 'normal'
    
    private_key = db_manager.get_decrypted_private_key(user_id)
    
    result = blockchain_manager.buy_token(
        token_address, amount, user.wallet_address,
        private_key, slippage, gas_mode
    )
    
    private_key = None
    del private_key
    
    if result:
        tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
        
        db_manager.add_token_history(
            user_id, token_address, 'buy', str(amount),
            result['tx_hash'], token_info['name'],
            token_info['symbol']
        )
        
        # db_manager.add_user_token(user_id, token_address)  # Not needed with BlockVision API
        
        expected_output = float(result['expected_output']) / (10 ** token_info['decimals'])
        
        success_msg = (
            f"✅ *Buy Transaction Successful\\!*\n\n"
            f"🪙 Token: {escape_markdown(token_info['symbol'])}\n"
            f"📊 MON Amount: {escape_markdown(str(amount))}\n"
            f"💰 Estimasi: {escape_markdown(f'{expected_output:.4f}')} {escape_markdown(token_info['symbol'])}\n"
            f"🔗 [View Transaction]({tx_url})\n\n"
            f"⏰ Menunggu konfirmasi\\.\\.\\."
        )
        
        await loading_msg.edit_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard(),
            disable_web_page_preview=True
        )
    else:
        await loading_msg.edit_text(
            "❌ *Transaction Failed\\!*\n\n"
            "Please try again or check your balance and gas\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
    
    if user_id in user_context:
        del user_context[user_id]
    
    return ConversationHandler.END

async def handle_sell_custom_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom sell amount input from user"""
    user_id = update.effective_user.id
    amount_text = update.message.text.strip()
    
    # Validate amount
    try:
        amount = Decimal(amount_text)
        if amount <= 0:
            await update.message.reply_text(
                "❌ Amount must be greater than 0\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return AWAITING_SELL_CUSTOM_AMOUNT
    except:
        await update.message.reply_text(
            "❌ Invalid amount\\. Enter a number like: 50, 100\\.5",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SELL_CUSTOM_AMOUNT
    
    if user_id not in user_context or user_context[user_id].get('action') != 'sell':
        await update.message.reply_text("❌ Session expired\\. Please start again\\.")
        return ConversationHandler.END
    
    token_address = user_context[user_id]['token_address']
    
    loading_msg = await update.message.reply_text("⏳ *Processing sell transaction\\.\\.\\.*", parse_mode=ParseMode.MARKDOWN_V2)
    
    user = db_manager.get_user(user_id)
    
    # Check if amount exceeds balance
    balance, _ = blockchain_manager.get_token_balance(token_address, user.wallet_address)
    if amount > balance:
        await loading_msg.edit_text(
            f"❌ *Amount exceeds balance\\!*\n\n"
            f"Balance: {escape_markdown(f'{balance:.4f}')}\n"
            f"Requested: {escape_markdown(f'{amount:.4f}')}\n\n"
            f"Please try again dengan jumlah yang lebih kecil\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    settings = db_manager.get_user_settings(user_id)
    slippage = settings.slippage if settings else 5.0
    gas_mode = settings.gas_price_mode if settings else 'normal'
    
    private_key = db_manager.get_decrypted_private_key(user_id)
    
    result = blockchain_manager.sell_token(
        token_address, amount, user.wallet_address,
        private_key, slippage, gas_mode
    )
    
    private_key = None
    del private_key
    
    if result:
        info = blockchain_manager.get_token_info(token_address)
        tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
        
        db_manager.add_token_history(
            user_id, token_address, 'sell', str(amount),
            result['tx_hash'], info['name'] if info else None,
            info['symbol'] if info else None
        )
        
        expected_output = float(result['expected_output'])
        
        success_msg = (
            f"✅ *Sell Transaction Successful\\!*\n\n"
            f"🪙 Token: {escape_markdown(info['symbol']) if info else 'Unknown'}\n"
            f"📊 Amount: {escape_markdown(f'{amount:.4f}')}\n"
            f"💰 Estimasi: {escape_markdown(f'{expected_output:.4f}')} {NATIVE_CURRENCY}\n"
            f"🔗 [View Transaction]({tx_url})\n\n"
            f"⏰ Menunggu konfirmasi\\.\\.\\."
        )
        
        await loading_msg.edit_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard(),
            disable_web_page_preview=True
        )
    else:
        await loading_msg.edit_text(
            "❌ *Transaction Failed\\!*\n\n"
            "Please try again or check your balance and gas\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_menu_keyboard()
        )
    
    if user_id in user_context:
        del user_context[user_id]
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current operation"""
    user_id = update.effective_user.id
    
    if user_id in user_context:
        del user_context[user_id]
    
    await update.message.reply_text(
        "❌ Operasi dibatalkan\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


async def handle_set_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle passphrase setup"""
    passphrase = update.message.text.strip()
    await update.message.delete()
    
    is_valid, msg = validate_passphrase(passphrase)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ {escape_markdown(msg)}\n\nTry again:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SET_PASSPHRASE
    
    context.user_data['pending_passphrase'] = passphrase
    
    if msg:
        await update.message.reply_text(
            f"⚠️ {escape_markdown(msg)}\n\nConfirm your passphrase:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "✅ Strong passphrase\\!\n\nConfirm your passphrase:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return AWAITING_CONFIRM_PASSPHRASE

async def handle_confirm_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle passphrase confirmation"""
    confirm = update.message.text.strip()
    await update.message.delete()
    
    passphrase = context.user_data.get('pending_passphrase')
    private_key = context.user_data.get('pending_private_key')
    address = context.user_data.get('pending_address')
    
    if not passphrase or not private_key or not address:
        await update.message.reply_text(
            "❌ Session expired\\. Please start again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END
    
    if confirm != passphrase:
        await update.message.reply_text(
            "❌ Passphrases don't match\\!\n\nSet your passphrase again:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        del context.user_data['pending_passphrase']
        return AWAITING_SET_PASSPHRASE
    
    user_id = update.effective_user.id
    db_manager.update_user_wallet(
        telegram_id=user_id,
        wallet_address=address,
        private_key=private_key,
        passphrase=passphrase
    )
    
    del context.user_data['pending_private_key']
    del context.user_data['pending_address']
    del context.user_data['pending_passphrase']
    del private_key, passphrase, confirm
    
    await update.message.reply_text(
        "✅ *Wallet Imported \\(Secure Mode\\)\\!*\n\n"
        f"📍 Address: `{escape_markdown(address[:10])}...{escape_markdown(address[-8:])}`\n\n"
        "🔐 *Zero\\-Knowledge Security:*\n"
        "• Your key is encrypted with YOUR passphrase\n"
        "• Developer CANNOT access your key\n"
        "• You\'ll need passphrase for transactions\n\n"
        "⚠️ *Remember: Forget passphrase = LOST FOREVER\\!*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END

async def handle_transaction_passphrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle passphrase for transaction signing"""
    passphrase = update.message.text.strip()
    await update.message.delete()
    
    user_id = update.effective_user.id
    user = db_manager.get_user(user_id)
    
    pending_buy = context.user_data.get('pending_buy')
    pending_sell = context.user_data.get('pending_sell')
    
    if not user:
        await update.message.reply_text("❌ User not found\\.")
        return ConversationHandler.END
    
    loading_msg = await update.message.reply_text(
        "⏳ *Processing transaction\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        private_key = db_manager.get_decrypted_private_key(
            telegram_id=user_id,
            passphrase=passphrase
        )
        
        if pending_buy:
            result = blockchain_manager.buy_token(
                token_address=pending_buy['token_address'],
                amount_monad=pending_buy['amount'],
                wallet_address=user.wallet_address,
                private_key=private_key,
                slippage=pending_buy.get('slippage', 5.0),
                gas_mode=pending_buy.get('gas_mode', 'normal')
            )
            
            del private_key, passphrase
            del context.user_data['pending_buy']
            
            if result:
                tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
                token_info = context.user_data.get('current_token_info', {})
                
                await loading_msg.edit_text(
                    f"✅ *Buy Transaction Successful\\!*\n\n"
                    f"🪙 Token: {escape_markdown(token_info.get('symbol', 'Unknown'))}\n"
                    f"📊 MON Amount: {escape_markdown(str(pending_buy['amount']))}\n"
                    f"🔗 [View Transaction]({tx_url})\n\n"
                    f"Transaction completed\\!",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await loading_msg.edit_text(
                    "❌ *Transaction Failed\\!*\n\n"
                    "Please try again or check your balance and gas\\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        
        elif pending_sell:
            result = blockchain_manager.sell_token(
                token_address=pending_sell['token_address'],
                amount_tokens=pending_sell['amount'],
                wallet_address=user.wallet_address,
                private_key=private_key,
                slippage=pending_sell.get('slippage', 5.0),
                gas_mode=pending_sell.get('gas_mode', 'normal')
            )
            
            del private_key, passphrase
            del context.user_data['pending_sell']
            
            if result:
                tx_url = f"{BLOCK_EXPLORER_URL}/tx/{result['tx_hash']}"
                token_info = context.user_data.get('current_token_info', {})
                
                await loading_msg.edit_text(
                    f"✅ *Sell Transaction Successful\\!*\n\n"
                    f"🪙 Token: {escape_markdown(token_info.get('symbol', 'Unknown'))}\n"
                    f"📊 Amount: {escape_markdown(f'{pending_sell["amount"]:.4f}')}\n"
                    f"🔗 [View Transaction]({tx_url})\n\n"
                    f"Transaction completed\\!",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                await loading_msg.edit_text(
                    "❌ *Transaction Failed\\!*\n\n"
                    "Please try again or check your balance and gas\\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        else:
            await loading_msg.edit_text("❌ No pending transaction found\\.")
        
    except ValueError as e:
        error_msg = str(e)
        if "Incorrect passphrase" in error_msg or "Passphrase required" in error_msg:
            await loading_msg.edit_text(
                "❌ *Incorrect Passphrase\\!*\n\n"
                "Transaction cancelled\\. Try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await loading_msg.edit_text(
                f"❌ *Error:* {escape_markdown(error_msg)}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ *Transaction failed:* {escape_markdown(str(e))}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

def main():
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not configured in .env file")
        return
    
    print("🤖 Starting MonadTrojan Bot...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(button_callback)
        ],
        states={
            AWAITING_TOKEN_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_address)
            ],
            AWAITING_PRIVATE_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_private_key_import)
            ],
            AWAITING_BUY_CUSTOM_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buy_custom_amount_input)
            ],
            AWAITING_SELL_CUSTOM_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sell_custom_amount_input)
            ],
            AWAITING_SET_PASSPHRASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_passphrase)
            ],
            AWAITING_CONFIRM_PASSPHRASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm_passphrase)
            ],
            AWAITING_TRANSACTION_PASSPHRASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transaction_passphrase)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(handle_buy_amount, pattern=r'^buy_'))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot started successfully!")
    print("🔗 Monad Testnet RPC:", MONAD_TESTNET_RPC_URL)
    print("🔗 DEX Router:", DEX_ROUTER_ADDRESS)
    print("\n⏳ Listening for messages...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
