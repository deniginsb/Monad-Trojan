"""
Send & Receive Token Handlers
Handles sending tokens to other addresses and receiving (show wallet address + QR)
"""
import io
import qrcode
from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import BLOCK_EXPLORER_URL, NATIVE_CURRENCY
from database import db_manager
from blockchain import blockchain_manager

# Conversation states
AWAITING_SEND_ADDRESS = 11
AWAITING_SEND_AMOUNT = 12
AWAITING_SEND_PASSPHRASE = 13

def escape_markdown(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def handle_send_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle send token - show list of tokens to send
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    user = db_manager.get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Wallet not found\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
    
    # Get all verified tokens with balance > 0
    all_tokens = blockchain_manager.get_wallet_all_tokens(user.wallet_address)
    
    sendable_tokens = {}
    for symbol, token_data in all_tokens.items():
        if token_data.get('verified', False) and token_data['balance'] > 0:
            sendable_tokens[symbol] = token_data
    
    if not sendable_tokens:
        await query.edit_message_text(
            "❌ You don't have any tokens to send\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
            ]])
        )
        return ConversationHandler.END
    
    # Build token selection keyboard
    keyboard = []
    for symbol, token_data in sorted(sendable_tokens.items(), key=lambda x: x[1]['balance'], reverse=True):
        balance = token_data['balance']
        balance_str = f"{balance:.4f}" if balance < 1000 else f"{balance:.2f}"
        button_text = f"{symbol}: {balance_str}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"send_select_{symbol}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="main_menu")])
    
    await query.edit_message_text(
        "📤 *Send Token*\n\n"
        "Select token to send:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

async def handle_send_select_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle token selection for sending - ask for passphrase ONCE at the start
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    print(f"🔔 handle_send_select_token CALLED! User: {user_id}, Data: {query.data}")
    
    await query.answer()
    
    # Extract token symbol from callback data
    symbol = query.data.replace("send_select_", "")
    print(f"   Symbol extracted: {symbol}")
    
    user = db_manager.get_user(user_id)
    all_tokens = blockchain_manager.get_wallet_all_tokens(user.wallet_address)
    
    if symbol not in all_tokens:
        await query.edit_message_text("❌ Token not found\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
    
    token_data = all_tokens[symbol]
    
    # Store in context
    context.user_data['send_token'] = {
        'symbol': symbol,
        'address': token_data.get('address'),
        'balance': token_data.get('balance'),
        'name': token_data.get('name', symbol)
    }
    
    balance = token_data['balance']
    balance_str = f"{balance:.4f}" if balance < 1000 else f"{balance:.2f}"
    
    # No passphrase needed - go directly to address input
    await query.edit_message_text(
        f"📤 *Send {escape_markdown(symbol)}*\n\n"
        f"*Balance:* `{escape_markdown(balance_str)} {escape_markdown(symbol)}`\n\n"
        f"Please send the *recipient address*\\.\n\n"
        f"Example: `0x1234\\.\\.\\.abcd`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return AWAITING_SEND_ADDRESS

async def handle_send_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle recipient address input
    """
    user_id = update.effective_user.id
    address = update.message.text.strip()
    
    # Validate address format
    if not address.startswith('0x') or len(address) != 42:
        await update.message.reply_text(
            "❌ Invalid address format\\.\n\n"
            "Address must start with `0x` and be 42 characters long\\.\n\n"
            "Please try again or type /cancel\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SEND_ADDRESS
    
    # Store recipient address
    context.user_data['send_token']['recipient'] = address
    
    token = context.user_data['send_token']
    symbol = token['symbol']
    balance = token['balance']
    
    await update.message.reply_text(
        f"📤 *Send {escape_markdown(symbol)}*\n\n"
        f"*To:* `{escape_markdown(address[:10])}...{escape_markdown(address[-8:])}`\n\n"
        f"*Available Balance:* `{escape_markdown(f'{balance:.4f}')} {escape_markdown(symbol)}`\n\n"
        f"How much {escape_markdown(symbol)} do you want to send?\n\n"
        f"Example: `10` or `0\\.5`\n\n"
        f"Type /cancel to abort\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return AWAITING_SEND_AMOUNT

async def handle_send_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle send amount input and execute send immediately (no passphrase needed)
    """
    user_id = update.effective_user.id
    
    try:
        amount = Decimal(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except:
        await update.message.reply_text(
            "❌ Invalid amount\\. Please enter a valid number\\.\n\n"
            "Example: `10` or `0\\.5`\n\n"
            "Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SEND_AMOUNT
    
    token = context.user_data['send_token']
    balance = token['balance']
    
    # Check if amount exceeds balance
    if amount > balance:
        await update.message.reply_text(
            f"❌ *Insufficient balance\\!*\n\n"
            f"*Available:* `{escape_markdown(f'{balance:.4f}')} {escape_markdown(token['symbol'])}`\n"
            f"*Requested:* `{escape_markdown(f'{amount:.4f}')} {escape_markdown(token['symbol'])}`\n\n"
            f"Please enter a smaller amount or type /cancel\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return AWAITING_SEND_AMOUNT
    
    # Store amount
    context.user_data['send_token']['amount'] = amount
    
    symbol = token['symbol']
    recipient = token['recipient']
    
    # Show confirmation and execute immediately
    loading_msg = await update.message.reply_text(
        f"✅ *Confirm Transaction*\n\n"
        f"*Token:* {escape_markdown(symbol)}\n"
        f"*Amount:* `{escape_markdown(f'{amount:.4f}')} {escape_markdown(symbol)}`\n"
        f"*To:* `{escape_markdown(recipient[:10])}...{escape_markdown(recipient[-8:])}`\n\n"
        f"⏳ *Sending transaction\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Execute send immediately without passphrase
    try:
        # Get private key (no passphrase needed)
        private_key = db_manager.get_decrypted_private_key(telegram_id=user_id)
        
        user = db_manager.get_user(user_id)
        token_address = token['address']
        
        # Send transaction
        if symbol in ['MON', 'MONAD']:
            # Native MON transfer
            from web3 import Web3
            from config import GAS_PRICE_MODES
            w3 = blockchain_manager.w3
            
            # Checksum addresses
            checksum_from = Web3.to_checksum_address(user.wallet_address)
            checksum_to = Web3.to_checksum_address(recipient)
            
            nonce = w3.eth.get_transaction_count(checksum_from)
            
            # Get gas settings
            gas_settings = GAS_PRICE_MODES.get('normal', GAS_PRICE_MODES['normal'])
            max_fee = w3.to_wei(gas_settings['maxFeePerGas'], 'gwei')
            max_priority = w3.to_wei(gas_settings['maxPriorityFeePerGas'], 'gwei')
            
            tx = {
                'from': checksum_from,
                'nonce': nonce,
                'to': checksum_to,
                'value': w3.to_wei(amount, 'ether'),
                'gas': 21000,
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority,
                'chainId': w3.eth.chain_id
            }
            
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
        else:
            # ERC20 token transfer
            result = blockchain_manager.send_token(
                token_address=token_address,
                recipient_address=recipient,
                amount=amount,
                wallet_address=user.wallet_address,
                private_key=private_key
            )
            
            if not result:
                raise Exception("Transaction failed")
            
            tx_hash_hex = result.get('tx_hash')
        
        # Clear sensitive data
        del private_key
        del context.user_data['send_token']
        
        # Success message
        tx_url = f"{BLOCK_EXPLORER_URL}/tx/{tx_hash_hex}"
        
        success_msg = (
            f"✅ *Transaction Sent\\!*\n\n"
            f"*Token:* {escape_markdown(symbol)}\n"
            f"*Amount:* `{escape_markdown(f'{amount:.4f}')} {escape_markdown(symbol)}`\n"
            f"*To:* `{escape_markdown(recipient[:10])}...{escape_markdown(recipient[-8:])}`\n"
            f"*TX Hash:* `{escape_markdown(tx_hash_hex[:10])}...`\n\n"
            f"🔗 [View Transaction]({tx_url})\n\n"
            f"⏰ Waiting for confirmation\\.\\.\\."
        )
        
        await loading_msg.edit_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
        
    except ValueError as e:
        error_msg = str(e)
        await loading_msg.edit_text(
            f"❌ *Transaction Failed\\!*\n\n"
            f"Error: {escape_markdown(error_msg)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ *Transaction Failed\\!*\n\n"
            f"Error: {escape_markdown(str(e))}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

async def handle_send_passphrase_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle passphrase input - cache it and ask for address
    """
    user_id = update.effective_user.id
    passphrase = update.message.text.strip()
    
    # Delete passphrase message for security
    try:
        await update.message.delete()
    except:
        pass
    
    # Verify passphrase is correct
    try:
        private_key = db_manager.get_decrypted_private_key(
            telegram_id=user_id,
            passphrase=passphrase
        )
        del private_key  # Clear immediately after verification
        
        # Cache passphrase in session
        context.user_data['cached_passphrase'] = passphrase
        
        # Success - ask for recipient address
        token = context.user_data['send_token']
        symbol = token['symbol']
        balance = token['balance']
        balance_str = f"{balance:.4f}" if balance < 1000 else f"{balance:.2f}"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ *Passphrase Verified\\!*\n\n"
                 f"📤 *Send {escape_markdown(symbol)}*\n\n"
                 f"*Balance:* `{escape_markdown(balance_str)} {escape_markdown(symbol)}`\n\n"
                 f"Please send the *recipient address*\\.\n\n"
                 f"Example: `0x1234\\.\\.\\.abcd`\n\n"
                 f"Type /cancel to abort\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        return AWAITING_SEND_ADDRESS
        
    except ValueError as e:
        error_msg = str(e)
        if "Incorrect passphrase" in error_msg or "Passphrase required" in error_msg:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ *Incorrect Passphrase\\!*\n\n"
                     "Please try again or type /cancel\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return AWAITING_SEND_PASSPHRASE
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ *Error:* {escape_markdown(error_msg)}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ *Error:* {escape_markdown(str(e))}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END


async def handle_send_passphrase_input_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    OLD: Handle passphrase and execute send transaction
    """
    user_id = update.effective_user.id
    passphrase = update.message.text.strip()
    
    # Delete passphrase message for security
    try:
        await update.message.delete()
    except:
        pass
    
    loading_msg = await context.bot.send_message(
        chat_id=user_id,
        text="⏳ *Processing transaction\\.\\.\\.*",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        # Get private key with passphrase
        private_key = db_manager.get_decrypted_private_key(
            telegram_id=user_id,
            passphrase=passphrase
        )
        
        user = db_manager.get_user(user_id)
        token = context.user_data['send_token']
        
        symbol = token['symbol']
        token_address = token['address']
        recipient = token['recipient']
        amount = token['amount']
        
        # Send transaction
        if symbol in ['MON', 'MONAD']:
            # Native MON transfer
            from web3 import Web3
            from config import GAS_PRICE_MODES
            w3 = blockchain_manager.w3
            
            # Checksum addresses
            checksum_from = Web3.to_checksum_address(user.wallet_address)
            checksum_to = Web3.to_checksum_address(recipient)
            
            nonce = w3.eth.get_transaction_count(checksum_from)
            
            # Get gas settings
            gas_settings = GAS_PRICE_MODES.get('normal', GAS_PRICE_MODES['normal'])
            max_fee = w3.to_wei(gas_settings['maxFeePerGas'], 'gwei')
            max_priority = w3.to_wei(gas_settings['maxPriorityFeePerGas'], 'gwei')
            
            tx = {
                'from': checksum_from,
                'nonce': nonce,
                'to': checksum_to,
                'value': w3.to_wei(amount, 'ether'),
                'gas': 21000,
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority,
                'chainId': w3.eth.chain_id
            }
            
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()
        else:
            # ERC20 token transfer
            result = blockchain_manager.send_token(
                token_address=token_address,
                recipient_address=recipient,
                amount=amount,
                wallet_address=user.wallet_address,
                private_key=private_key
            )
            
            if not result:
                raise Exception("Transaction failed")
            
            tx_hash_hex = result.get('tx_hash')
        
        # Clear sensitive data
        del private_key, passphrase
        del context.user_data['send_token']
        
        # Success message
        tx_url = f"{BLOCK_EXPLORER_URL}/tx/{tx_hash_hex}"
        
        success_msg = (
            f"✅ *Transaction Sent\\!*\n\n"
            f"*Token:* {escape_markdown(symbol)}\n"
            f"*Amount:* `{escape_markdown(f'{amount:.4f}')} {escape_markdown(symbol)}`\n"
            f"*To:* `{escape_markdown(recipient[:10])}...{escape_markdown(recipient[-8:])}`\n"
            f"*TX Hash:* `{escape_markdown(tx_hash_hex[:10])}...`\n\n"
            f"🔗 [View Transaction]({tx_url})\n\n"
            f"⏰ Waiting for confirmation\\.\\.\\."
        )
        
        await loading_msg.edit_text(
            success_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )
        
    except ValueError as e:
        error_msg = str(e)
        if "Incorrect passphrase" in error_msg or "Passphrase required" in error_msg:
            await loading_msg.edit_text(
                "❌ *Incorrect Passphrase\\!*\n\n"
                "Transaction cancelled\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await loading_msg.edit_text(
                f"❌ *Error\\!*\n\n"
                f"{escape_markdown(error_msg)}",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ *Transaction Failed\\!*\n\n"
            f"Error: {escape_markdown(str(e))}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

async def handle_receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle receive token - show wallet address with QR code
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    user = db_manager.get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Wallet not found\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
    
    address = user.wallet_address
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(address)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to BytesIO
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    
    # Message text
    message_text = (
        f"📥 *Receive Tokens*\n\n"
        f"*Your Wallet Address:*\n"
        f"`{escape_markdown(address)}`\n\n"
        f"🔗 [View on Explorer]({BLOCK_EXPLORER_URL}/address/{address})\n\n"
        f"💡 *Tip:* Copy the address or scan the QR code below\\."
    )
    
    # Delete previous message
    try:
        await query.message.delete()
    except:
        pass
    
    # Send QR code as photo with caption
    await context.bot.send_photo(
        chat_id=user_id,
        photo=bio,
        caption=message_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
        ]])
    )
    
    return ConversationHandler.END

async def cancel_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel send transaction"""
    await update.message.reply_text(
        "❌ Transaction cancelled\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Clean up context
    if 'send_token' in context.user_data:
        del context.user_data['send_token']
    
    return ConversationHandler.END
