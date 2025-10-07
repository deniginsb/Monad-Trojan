"""
Portfolio Module - Enhanced wallet visualization with ASCII charts
Provides portfolio overview with allocation bars and USD estimates
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from blockchain import blockchain_manager
from database import db_manager

# Price cache to avoid repeated API calls (cache for 5 minutes)
_price_cache = {}
_cache_expiry = {}
CACHE_DURATION_SECONDS = 300  # 5 minutes

def get_cached_price(token_address: str) -> Optional[float]:
    """Get cached price if available and not expired"""
    if token_address in _price_cache:
        if token_address in _cache_expiry:
            if datetime.now() < _cache_expiry[token_address]:
                return _price_cache[token_address]
    return None

def cache_price(token_address: str, price: float):
    """Cache a price with expiry time"""
    _price_cache[token_address] = price
    _cache_expiry[token_address] = datetime.now() + timedelta(seconds=CACHE_DURATION_SECONDS)

def ascii_bar(pct: float, width: int = 16) -> str:
    """
    Create ASCII horizontal bar chart
    
    Args:
        pct: Percentage (0.0 to 1.0)
        width: Total width of bar in characters
        
    Returns:
        String with filled (█) and empty (░) blocks
        
    Example:
        ascii_bar(0.75, 16) -> "████████████░░░░"
    """
    if pct < 0:
        pct = 0
    if pct > 1:
        pct = 1
    
    fill = int(pct * width + 0.5)
    return "█" * fill + "░" * (width - fill)

def escape_markdown(text: str) -> str:
    """
    Escape special characters for MarkdownV2
    
    MarkdownV2 special chars that MUST be escaped outside code blocks:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    # Convert to string first if not already
    text = str(text)
    
    # Escape all special MarkdownV2 characters
    # Order matters for some chars, but for MarkdownV2 we escape each individually
    replacements = {
        '_': '\\_',
        '*': '\\*',
        '[': '\\[',
        ']': '\\]',
        '(': '\\(',
        ')': '\\)',
        '~': '\\~',  # Important: strikethrough marker
        '`': '\\`',
        '>': '\\>',
        '#': '\\#',
        '+': '\\+',
        '-': '\\-',
        '=': '\\=',
        '|': '\\|',
        '{': '\\{',
        '}': '\\}',
        '.': '\\.',
        '!': '\\!'
    }
    
    for char, escaped in replacements.items():
        text = text.replace(char, escaped)
    
    return text

def get_wallet_overview(user_id: int, wallet_address: str, fetch_prices_for_top: int = 25) -> Dict:
    """
    Get complete wallet overview with all balances
    
    Args:
        user_id: Telegram user ID
        wallet_address: Wallet address
        
    Returns:
        Dict with:
            - native: Native balance (MONAD)
            - tokens: List of token dicts with balance, symbol, name, address, decimals
            - total_positions: Total number of positions (including native)
    """
    # Get native balance
    native_balance = blockchain_manager.get_native_balance(wallet_address)
    
    # Get all tokens using BlockVision API
    all_tokens = blockchain_manager.get_wallet_all_tokens(wallet_address)
    
    # Fallback: Check token history if BlockVision didn't return enough
    non_native_count = sum(1 for s in all_tokens.keys() if s not in ['MON', 'MONAD'])
    if non_native_count == 0:
        user_token_addresses = db_manager.get_user_tokens(user_id)
        
        if user_token_addresses:
            history_tokens = blockchain_manager.get_tokens_from_history(
                wallet_address,
                user_token_addresses
            )
            
            # Merge with all_tokens
            for symbol, token_data in history_tokens.items():
                if symbol not in all_tokens or all_tokens[symbol]['balance'] == 0:
                    all_tokens[symbol] = token_data
    
    # Build token list (exclude native)
    tokens = []
    for symbol, token_data in all_tokens.items():
        if symbol not in ['MON', 'MONAD'] and token_data['balance'] > 0:
            tokens.append({
                'symbol': symbol,
                'name': token_data.get('name', symbol),
                'balance': token_data['balance'],
                'decimals': token_data.get('decimals', 18),
                'address': token_data.get('address', ''),
                'verified': token_data.get('verified', False),
                'price_usd': None,
                'value_usd': None
            })
    
    # Sort: VERIFIED tokens first (for price priority), then by balance
    tokens.sort(key=lambda x: (not x.get('verified', False), -float(x['balance'])))
    
    # Fetch MON price ONCE and apply to all derivatives
    mon_price_usd = None
    try:
        # Try to get WMON price (wrapped MON)
        wmon_address = '0x760afe86e5de5fa0ee542fc7b7b713e1c5425701'  # WMON address
        
        # Check cache first
        mon_price_usd = get_cached_price('MON')
        if mon_price_usd:
            print(f"✅ MON price from cache: ${mon_price_usd:.6f}")
        else:
            # Fetch from API
            mon_price = blockchain_manager.get_token_price_from_nodejs(wmon_address)
            if mon_price and mon_price > 0 and mon_price < 100:  # Sanity check
                mon_price_usd = float(mon_price)
                cache_price('MON', mon_price_usd)
                print(f"✅ MON price fetched: ${mon_price_usd:.6f}")
            else:
                # Fallback to on-chain
                onchain_price = blockchain_manager.get_token_price_onchain(wmon_address)
                if onchain_price and onchain_price > 0:
                    mon_price_usd = float(onchain_price)
                    cache_price('MON', mon_price_usd)
                    print(f"✅ MON price (on-chain): ${mon_price_usd:.6f}")
    except Exception as e:
        print(f"⚠️ Failed to fetch MON price: {e}")
    
    # Fallback: if still no MON price, use $1
    if not mon_price_usd or mon_price_usd <= 0:
        mon_price_usd = 1.0
        print(f"⚠️ Using fallback MON price: $1.00")
    
    # Fetch prices for top N tokens (prioritize verified tokens)
    if fetch_prices_for_top > 0:
        # Prioritize verified tokens for pricing
        verified_tokens = [t for t in tokens if t.get('verified')]
        unverified_tokens = [t for t in tokens if not t.get('verified')]
        
        # Fetch prices for verified tokens first, then top unverified
        tokens_to_price = verified_tokens[:fetch_prices_for_top]
        remaining_slots = fetch_prices_for_top - len(tokens_to_price)
        if remaining_slots > 0:
            tokens_to_price.extend(unverified_tokens[:remaining_slots])
        
        print(f"🔍 Fetching prices for {len(tokens_to_price)} tokens ({len([t for t in tokens_to_price if t.get('verified')])} verified)...")
        
        for token in tokens_to_price:
            token_address = token['address']
            balance = token['balance']
            symbol = token['symbol']
            
            # Skip LP tokens (liquidity pool tokens have unreliable prices)
            if 'LP' in symbol.upper() or '-LP' in symbol or 'POOL' in symbol.upper():
                print(f"⚠️ Skipping LP token: {symbol} (LP tokens have unreliable prices)")
                continue
            
            if token_address:
                try:
                    # Special case: MON derivatives = 1 MON (use real MON price)
                    MON_DERIVATIVES = ['gMON', 'aprMON', 'shMON', 'sMON', 'WMON', 'stMON', 'FMON', 'swMON']
                    if symbol in MON_DERIVATIVES:
                        price = mon_price_usd  # Use real MON price
                        token['price_usd'] = float(price)
                        token['value_usd'] = float(balance) * token['price_usd']
                        print(f"✅ {symbol}: ${price:.6f} (MON derivative) × {float(balance):.2f} = ${token['value_usd']:.2f}")
                        continue
                    
                    # Check cache first
                    cached_price = get_cached_price(token_address)
                    if cached_price:
                        token['price_usd'] = cached_price
                        token['value_usd'] = float(balance) * cached_price
                        print(f"✅ {symbol}: ${cached_price:.6f} (cached) × {float(balance):.2f} = ${token['value_usd']:.2f}")
                        continue
                    
                    price = blockchain_manager.get_token_price_from_nodejs(token_address)
                    if price and price > 0:
                        # Sanity check: If price seems too high, try on-chain fallback
                        if price > 1000:  # $1000+ per token is suspicious for testnet
                            print(f"⚠️ Suspicious price for {symbol}: ${price:.2f} - trying on-chain DEX...")
                            
                            # Try on-chain price as fallback
                            try:
                                onchain_price = blockchain_manager.get_token_price_onchain(token_address)
                                if onchain_price and onchain_price > 0 and onchain_price < 1000:
                                    price = onchain_price
                                    print(f"✅ On-chain price for {symbol}: ${price:.6f}")
                                else:
                                    print(f"⚠️ On-chain price also suspicious or unavailable, skipping {symbol}")
                                    continue
                            except Exception as e:
                                print(f"⚠️ On-chain price fetch failed for {symbol}: {e}")
                                continue
                        
                        token['price_usd'] = float(price)
                        token['value_usd'] = float(balance) * token['price_usd']
                        
                        # Cache the price
                        cache_price(token_address, float(price))
                        
                        print(f"✅ {symbol}: ${token['price_usd']:.6f} × {float(balance):.2f} = ${token['value_usd']:.2f}")
                except Exception as e:
                    print(f"⚠️ Price fetch failed for {symbol}: {e}")
        
        # Re-sort by USD value if we have prices
        tokens_with_value = [t for t in tokens if t.get('value_usd')]
        tokens_without_value = [t for t in tokens if not t.get('value_usd')]
        
        if tokens_with_value:
            tokens_with_value.sort(key=lambda x: x['value_usd'], reverse=True)
            tokens = tokens_with_value + tokens_without_value  # Valued tokens first
    
    # Sort by balance (descending) - but this is RAW balance
    # For better UX, we should normalize first but that requires more data
    tokens.sort(key=lambda x: x['balance'], reverse=True)
    
    return {
        'native': native_balance,
        'tokens': tokens,
        'total_positions': 1 + len(tokens)
    }

def estimate_token_price(token_address: str) -> Optional[float]:
    """
    Estimate token price in USD
    Uses price.js service with fallback to on-chain data
    
    Args:
        token_address: Token contract address
        
    Returns:
        Price in USD or None if unavailable
    """
    try:
        # Use correct function name from blockchain.py
        price_info = blockchain_manager.get_token_price_from_nodejs(token_address)
        
        if price_info and price_info.get('ok'):
            # Try to get USD price first
            price_usd = price_info.get('price_usd')
            if price_usd:
                return float(price_usd)
            
            # Fallback: Use native price * MONAD price estimate
            # For testnet, we use dummy MONAD price of $1.0
            price_native = price_info.get('price_native')
            if price_native:
                monad_price_usd = 1.0  # Dummy price for testnet
                return float(price_native) * monad_price_usd
        
        return None
    except Exception as e:
        print(f"⚠️ Price estimation failed for {token_address}: {e}")
        return None

def render_portfolio(overview: Dict, include_prices: bool = True, max_tokens: int = 25) -> str:
    """
    Render portfolio as formatted text with ASCII charts
    
    Args:
        overview: Wallet overview from get_wallet_overview()
        include_prices: Whether to include USD price estimates
        max_tokens: Maximum number of tokens to display (default: 15)
        
    Returns:
        Formatted text ready for Telegram (MarkdownV2)
    """
    native = overview.get('native', Decimal('0'))
    tokens = overview.get('tokens', [])
    total_positions = overview.get('total_positions', 1)
    
    # Limit tokens to prevent message too long (Telegram has 4096 char limit)
    tokens_to_display = tokens[:max_tokens] if len(tokens) > max_tokens else tokens
    hidden_count = len(tokens) - len(tokens_to_display) if len(tokens) > max_tokens else 0
    
    # Build message
    lines = []
    lines.append("*📊 Portfolio Overview*")
    lines.append("")
    
    # Summary
    lines.append(f"*Holdings:* {escape_markdown(str(total_positions))} positions")
    
    # Format native balance
    if native < Decimal('0.0001'):
        native_str = f"{native:.8f}"
    elif native < Decimal('1'):
        native_str = f"{native:.6f}"
    else:
        native_str = f"{native:.4f}"
    
    lines.append(f"*Native:* `{escape_markdown(native_str)} MONAD`")
    lines.append("")
    
    # If no tokens, show message
    if not tokens_to_display:
        lines.append("_No ERC\\-20 tokens yet_")
        lines.append("")
        lines.append("💡 *Tip:* Use 🚀 Buy Token to add tokens to your portfolio")
        return "\n".join(lines)
    
    # Calculate allocation based on USD VALUE (not quantity!)
    # This gives accurate portfolio representation
    
    # Separate tokens with prices vs without
    tokens_with_price = [t for t in tokens_to_display if t.get('value_usd')]
    tokens_without_price = [t for t in tokens_to_display if not t.get('value_usd')]
    
    # Calculate total USD value
    total_value_usd = sum(t.get('value_usd', 0) for t in tokens_with_price)
    
    # Determine if we can use price-based allocation
    use_price_allocation = len(tokens_with_price) >= 3 and total_value_usd > 0
    
    if use_price_allocation:
        # PRICE-BASED ALLOCATION (Accurate!)
        print(f"✅ Using price-based allocation (${total_value_usd:.2f} total)")
        tokens_for_calc = tokens_with_price
        outlier_tokens = []  # No outlier detection needed with prices
        allocation_mode = "value"
    else:
        # QUANTITY-BASED FALLBACK (when prices unavailable)
        print(f"⚠️ Using quantity-based allocation (prices unavailable)")
        
        # Use outlier detection for quantity-based
        if len(tokens_to_display) >= 4:
            sorted_tokens = sorted(tokens_to_display, key=lambda x: float(x['balance']), reverse=True)
            reference_balance = float(sorted_tokens[3]['balance'])
            outlier_threshold = reference_balance * 10
            
            filtered_tokens = []
            outlier_tokens = []
            
            for t in tokens_to_display:
                if float(t['balance']) > outlier_threshold:
                    outlier_tokens.append(t)
                else:
                    filtered_tokens.append(t)
            
            if len(filtered_tokens) < 3:
                filtered_tokens = tokens_to_display
                outlier_tokens = []
            
            tokens_for_calc = filtered_tokens
        else:
            tokens_for_calc = tokens_to_display
            outlier_tokens = []
        
        allocation_mode = "quantity"
    
    # Show allocation
    lines.append("*📈 Token Allocation:*")
    
    if use_price_allocation:
        lines.append(f"_\\(By USD value: ${escape_markdown(f'{total_value_usd:.2f}')} total\\)_")
    else:
        lines.append("_\\(By quantity \\- prices unavailable\\)_")
    
    if hidden_count > 0:
        lines.append(f"_\\(Showing top {max_tokens} of {len(tokens)} tokens\\)_")
    if outlier_tokens:
        outlier_symbols = ', '.join(t['symbol'] for t in outlier_tokens)
        lines.append(f"_\\(Excluding outliers: {escape_markdown(outlier_symbols)}\\)_")
    lines.append("")
    
    # Fetch prices if requested (disable for now to avoid slowdown)
    # Too many API calls for large portfolios
    # if include_prices:
    #     for token in tokens_to_display[:5]:  # Only fetch for top 5
    #         if token['address']:
    #             token['price_usd'] = estimate_token_price(token['address'])
    
    # Display each token with bar
    for token in tokens_to_display:
        symbol = token['symbol']
        balance = token['balance']
        value_usd = token.get('value_usd')
        price_usd = token.get('price_usd')
        
        # Check if this token is in calculation set
        is_outlier = token in outlier_tokens
        
        # Calculate percentage based on allocation mode
        if use_price_allocation and value_usd and total_value_usd > 0:
            # PRICE-BASED: percentage of USD value
            pct = value_usd / total_value_usd
        elif not is_outlier and allocation_mode == "quantity":
            # QUANTITY-BASED: percentage of token count
            total_count = sum(float(t['balance']) for t in tokens_for_calc)
            pct = float(balance / total_count) if total_count > 0 else 0
        else:
            pct = 0
        
        # Format balance
        if balance < Decimal('0.0001'):
            balance_str = f"{balance:.8f}"
        elif balance < Decimal('1'):
            balance_str = f"{balance:.6f}"
        else:
            balance_str = f"{balance:.4f}"
        
        # Create ASCII bar
        bar = ascii_bar(pct, width=14)
        pct_str = f"{pct * 100:.1f}%"
        
        # Build line with value if available
        line_parts = [
            f"`{escape_markdown(symbol[:8].ljust(8))}`",
            bar,
            f"{escape_markdown(pct_str.rjust(6))}",
        ]
        
        # Show USD value if available, otherwise show balance
        if value_usd:
            line_parts.append(f"\\(`${escape_markdown(f'{value_usd:.2f}')}`\\)")
        else:
            line_parts.append(f"\\(`{escape_markdown(balance_str)}`\\)")
        
        # Add outlier label if needed
        if is_outlier:
            line_parts.append("_\\*outlier_")
        
        lines.append(" ".join(line_parts))
    
    lines.append("")
    
    # Show token count summary
    if hidden_count > 0:
        lines.append(f"_\\+{hidden_count} more tokens not shown_")
        lines.append("")
    
    # Footer
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("💡 *Legend:* █ \\= allocation \\| ░ \\= remaining")
    
    return "\n".join(lines)

def render_portfolio_simple(overview: Dict) -> str:
    """
    Render simple portfolio without price estimates
    Faster for quick views
    
    Args:
        overview: Wallet overview from get_wallet_overview()
        
    Returns:
        Formatted text ready for Telegram (MarkdownV2)
    """
    return render_portfolio(overview, include_prices=False)

# Quick access function for handlers
def get_portfolio_text(user_id: int, wallet_address: str, include_prices: bool = True) -> str:
    """
    One-shot function to get formatted portfolio text
    
    Args:
        user_id: Telegram user ID
        wallet_address: Wallet address
        include_prices: Whether to include USD estimates
        
    Returns:
        Formatted portfolio text
    """
    overview = get_wallet_overview(user_id, wallet_address)
    return render_portfolio(overview, include_prices)
