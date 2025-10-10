"""
NFT Handlers Module - Display and manage NFTs on Monad testnet
"""
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ALCHEMY_MONAD_URL, BLOCK_EXPLORER_URL
from database import db_manager
from telegram.helpers import escape_markdown

async def handle_show_nfts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display all NFTs owned by user
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    # Show loading message
    loading_msg = await query.edit_message_text(
        "🔍 *Loading your NFTs\\.\\.\\.*\n\n"
        "Please wait, fetching from blockchain\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Get user wallet address
    user = db_manager.get_user(user_id)
    if not user:
        await loading_msg.edit_text(
            "❌ Wallet not found\\. Please use /start",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    wallet_address = user.wallet_address
    
    # Fetch NFTs using Alchemy API
    nfts = await fetch_nfts_from_alchemy(wallet_address)
    
    if not nfts:
        # No NFTs found
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
        await loading_msg.edit_text(
            "🖼️ *Your NFT Collection*\n\n"
            "You don't have any NFTs yet\\.\n\n"
            "📍 Your wallet: `{}`\n\n"
            "💡 *Tips:*\n"
            "• Visit [Monad Explorer]({}) to view your wallet\n"
            "• Mint or buy NFTs on Monad testnet marketplaces\n"
            "• NFT collections on Monad testnet are growing\\!".format(
                escape_markdown(wallet_address[:10] + "..." + wallet_address[-8:]),
                escape_markdown(f"{BLOCK_EXPLORER_URL}/address/{wallet_address}")
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        return
    
    # Display NFTs
    await display_nft_gallery(loading_msg, nfts, wallet_address, page=0)


async def fetch_nfts_from_alchemy(wallet_address: str) -> list:
    """
    Fetch NFTs owned by wallet using Alchemy NFT API v3 (REST endpoint)
    
    Args:
        wallet_address: Wallet address to query
        
    Returns:
        List of NFT objects with metadata
    """
    try:
        print(f"🔍 Fetching NFTs for {wallet_address}...")
        
        # Extract API key from ALCHEMY_MONAD_URL
        # Format: https://monad-testnet.g.alchemy.com/v2/API_KEY
        from urllib.parse import urlparse
        parsed = urlparse(ALCHEMY_MONAD_URL)
        api_key = parsed.path.split('/')[-1]  # Get last part of path
        
        # Alchemy NFT API v3 REST endpoint (NOT JSON-RPC!)
        base_url = f"https://monad-testnet.g.alchemy.com/nft/v3/{api_key}"
        endpoint = f"{base_url}/getNFTsForOwner"
        
        # Build query parameters
        params = {
            'owner': wallet_address,
            'withMetadata': 'true',
            'pageSize': '100'
        }
        
        response = requests.get(endpoint, params=params, timeout=10)
        
        if response.ok:
            data = response.json()
            
            # REST API v3 structure: { "ownedNfts": [...], "totalCount": X, "pageKey": ... }
            # NOT wrapped in "result" like JSON-RPC
            owned_nfts = data.get('ownedNfts', data.get('nfts', []))
            total_count = data.get('totalCount', len(owned_nfts))
            
            print(f"✅ Alchemy NFT API v3: Found {total_count} NFTs")
            
            # Parse and format NFT data
            nfts = []
            for nft in owned_nfts:
                # v3 structure can vary: contract, contractMetadata, etc
                contract = nft.get('contract', nft.get('contractMetadata', {}))
                
                # Get contract address from multiple possible locations
                contract_addr = (
                    contract.get('address') or 
                    nft.get('contractAddress') or 
                    nft.get('contract', {}).get('contractAddress', '')
                )
                
                # Get symbol from multiple possible locations
                symbol = (
                    contract.get('symbol') or 
                    nft.get('contractMetadata', {}).get('symbol') or
                    nft.get('rawMetadata', {}).get('symbol') or
                    ''
                )
                
                # Get name from multiple possible locations
                contract_name = (
                    contract.get('name') or 
                    nft.get('contractMetadata', {}).get('name') or
                    nft.get('rawMetadata', {}).get('name') or
                    'Unknown'
                )
                
                # Get token ID - prefer decoded over hex
                token_id = (
                    nft.get('tokenIdDecoded') or
                    nft.get('tokenId') or
                    nft.get('id', {}).get('tokenId') or
                    nft.get('tokenIdHex') or
                    nft.get('id', '?')
                )
                
                # Get metadata (can be in different places)
                metadata = nft.get('metadata', nft.get('rawMetadata', {}))
                nft_name = metadata.get('name', nft.get('name', f'#{token_id}'))
                description = metadata.get('description', nft.get('description', ''))
                image = metadata.get('image', nft.get('image', ''))
                
                # Parse metadata
                nft_data = {
                    'contract_address': contract_addr,
                    'contract_name': contract_name,
                    'contract_symbol': symbol,
                    'token_id': str(token_id),
                    'name': nft_name,
                    'description': description,
                    'image': image,
                    'attributes': metadata.get('attributes', [])
                }
                
                nfts.append(nft_data)
            
            return nfts
        else:
            print(f"⚠️ Alchemy API failed: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error fetching NFTs: {e}")
        import traceback
        traceback.print_exc()
        return []


async def display_nft_gallery(message, nfts: list, wallet_address: str, page: int = 0):
    """
    Display NFT gallery with pagination
    
    Args:
        message: Telegram message to edit
        nfts: List of NFT objects
        wallet_address: Wallet address
        page: Current page number (0-indexed)
    """
    total_nfts = len(nfts)
    nfts_per_page = 5
    total_pages = (total_nfts + nfts_per_page - 1) // nfts_per_page
    
    # Get NFTs for current page
    start_idx = page * nfts_per_page
    end_idx = min(start_idx + nfts_per_page, total_nfts)
    page_nfts = nfts[start_idx:end_idx]
    
    # Build message text
    text = f"🖼️ *Your NFT Collection*\n\n"
    text += f"📍 Address: `{escape_markdown(wallet_address[:10])}...{escape_markdown(wallet_address[-8:])}`\n"
    text += f"🎨 Total NFTs: *{escape_markdown(str(total_nfts))}*\n"
    text += f"📄 Page {page + 1} of {total_pages}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Add NFT details
    for i, nft in enumerate(page_nfts, start=start_idx + 1):
        collection = nft.get('contract_name', 'Unknown')
        name = nft.get('name', f"#{nft.get('token_id', '?')}")
        token_id = nft.get('token_id', '?')
        
        text += f"*{i}\\. {escape_markdown(collection)}*\n"
        text += f"   🏷️ {escape_markdown(name)}\n"
        text += f"   🔢 Token ID: `{escape_markdown(str(token_id))}`\n"
        
        # Add description if available (truncate if too long)
        description = nft.get('description', '')
        if description and len(description) > 0:
            desc_short = description[:80] + "..." if len(description) > 80 else description
            text += f"   📝 {escape_markdown(desc_short)}\n"
        
        # Add image link if available
        image_url = nft.get('image', '')
        if image_url:
            # Handle IPFS URLs
            if image_url.startswith('ipfs://'):
                image_url = image_url.replace('ipfs://', 'https://ipfs.io/ipfs/')
            text += f"   🖼️ [View Image]({escape_markdown(image_url)})\n"
        
        # Add explorer link
        contract_address = nft.get('contract_address', '')
        if contract_address and BLOCK_EXPLORER_URL:
            explorer_link = f"{BLOCK_EXPLORER_URL}/token/{contract_address}?a={token_id}"
            text += f"   🔗 [View on Explorer]({escape_markdown(explorer_link)})\n"
        
        text += "\n"
    
    # Build pagination keyboard
    keyboard = []
    
    # Pagination buttons
    if total_pages > 1:
        pagination_row = []
        if page > 0:
            pagination_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"nft_page_{page-1}"))
        if page < total_pages - 1:
            pagination_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"nft_page_{page+1}"))
        if pagination_row:
            keyboard.append(pagination_row)
    
    # Action buttons
    action_row = [
        InlineKeyboardButton("🔄 Refresh", callback_data="nfts"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
    ]
    keyboard.append(action_row)
    
    # Edit message with NFT gallery
    try:
        await message.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"⚠️ Error displaying NFT gallery: {e}")
        # Fallback without markdown
        await message.edit_text(
            "🖼️ Your NFT Collection\n\n"
            f"Found {total_nfts} NFTs in your wallet.\n\n"
            "❌ Error displaying details. Please try again.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def handle_nft_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle NFT gallery pagination
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    # Extract page number from callback data
    page = int(query.data.split('_')[-1])
    
    # Get user wallet
    user = db_manager.get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Wallet not found\\. Please use /start")
        return
    
    # Fetch NFTs again (or cache them in context.user_data)
    wallet_address = user.wallet_address
    
    # Check if NFTs are cached
    if 'nfts' in context.user_data:
        nfts = context.user_data['nfts']
    else:
        nfts = await fetch_nfts_from_alchemy(wallet_address)
        context.user_data['nfts'] = nfts
    
    # Display page
    await display_nft_gallery(query.message, nfts, wallet_address, page=page)


async def send_nft_image(update: Update, context: ContextTypes.DEFAULT_TYPE, nft_index: int) -> None:
    """
    Send NFT image as photo (optional feature)
    
    Args:
        update: Telegram update
        context: Context
        nft_index: Index of NFT in user's collection
    """
    user_id = update.effective_user.id
    
    # Get user wallet
    user = db_manager.get_user(user_id)
    if not user:
        return
    
    # Fetch NFTs
    wallet_address = user.wallet_address
    nfts = await fetch_nfts_from_alchemy(wallet_address)
    
    if nft_index >= len(nfts):
        await update.message.reply_text("❌ NFT not found")
        return
    
    nft = nfts[nft_index]
    image_url = nft.get('image', '')
    
    if not image_url:
        await update.message.reply_text("❌ No image available for this NFT")
        return
    
    # Handle IPFS URLs
    if image_url.startswith('ipfs://'):
        image_url = image_url.replace('ipfs://', 'https://ipfs.io/ipfs/')
    
    # Send photo
    try:
        caption = f"🖼️ {nft.get('name', 'NFT')}\n"
        caption += f"📦 {nft.get('contract_name', 'Unknown Collection')}\n"
        caption += f"🔢 Token ID: {nft.get('token_id', '?')}"
        
        await context.bot.send_photo(
            chat_id=user_id,
            photo=image_url,
            caption=caption
        )
    except Exception as e:
        print(f"❌ Error sending NFT image: {e}")
        await update.message.reply_text(
            f"❌ Could not load image.\n\n"
            f"View online: {image_url}"
        )
