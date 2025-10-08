"""
Blockchain Module - Handles all Web3 interactions with Monad Testnet
"""
import time
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from web3 import Web3
from web3.exceptions import ContractLogicError
from eth_account import Account
import requests

from config import (
    MONAD_TESTNET_RPC_URL, DEX_ROUTER_ADDRESS, ERC20_ABI, 
    DEX_ROUTER_ABI, WETH_ADDRESS, NATIVE_CURRENCY, CHAIN_ID,
    GAS_PRICE_MODES, BLOCK_EXPLORER_API_URL, BLOCK_EXPLORER_API_KEY,
    BLOCKVISION_API_KEY, ALCHEMY_MONAD_URL,
    VERIFIED_TOKENS, HIGH_VALUE_TOKENS  # Import from config (80 tokens!)
)

class BlockchainManager:
    """Manages all blockchain interactions"""
    
    def __init__(self):
        """Initialize Web3 connection"""
        if not MONAD_TESTNET_RPC_URL:
            raise ValueError("MONAD_TESTNET_RPC_URL not configured")
        
        self.w3 = Web3(Web3.HTTPProvider(MONAD_TESTNET_RPC_URL))
        
        if not self.w3.is_connected():
            raise Exception(f"Failed to connect to Monad Testnet RPC: {MONAD_TESTNET_RPC_URL}")
        
        self.router_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(DEX_ROUTER_ADDRESS),
            abi=DEX_ROUTER_ABI
        )
    
    def _is_token_verified(self, token_address: str, symbol: str) -> bool:
        """
        Check if a token is verified/legitimate
        
        Args:
            token_address: Token contract address
            symbol: Token symbol
            
        Returns:
            True if verified, False otherwise
        """
        # Check if in verified list
        if token_address.lower() in VERIFIED_TOKENS:
            return True
        
        # Check if symbol matches known high-value tokens
        if symbol in HIGH_VALUE_TOKENS:
            return True
        
        # Check if it's a stablecoin (usually safe)
        stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD', 'FRAX', 'R2USD']
        if symbol in stablecoins or symbol.endswith('.a'):  # .a = Atlantis versions
            return True
        
        # Otherwise not verified
        return False
    
    def create_wallet(self) -> Tuple[str, str]:
        """
        Create a new wallet
        
        Returns:
            Tuple of (address, private_key)
        """
        account = Account.create()
        return account.address, account.key.hex()
    
    def validate_address(self, address: str) -> bool:
        """Validate if address is a valid Ethereum address"""
        try:
            return Web3.is_address(address)
        except:
            return False
    
    def validate_private_key(self, private_key: str) -> Optional[str]:
        """
        Validate private key and return address if valid
        
        Args:
            private_key: Private key as hex string
            
        Returns:
            Wallet address if valid, None otherwise
        """
        try:
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            
            account = Account.from_key(private_key)
            return account.address
        except:
            return None
    
    def get_native_balance(self, address: str) -> Decimal:
        """
        Get native currency balance (MONAD)
        
        Args:
            address: Wallet address
            
        Returns:
            Balance in MONAD (Decimal)
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.w3.eth.get_balance(checksum_address)
            balance_monad = Decimal(self.w3.from_wei(balance_wei, 'ether'))
            return balance_monad
        except Exception as e:
            print(f"Error getting native balance: {e}")
            return Decimal('0')
    
    def get_token_info(self, token_address: str) -> Optional[Dict]:
        """
        Get token information (name, symbol, decimals)
        
        Args:
            token_address: Token contract address
            
        Returns:
            Dict with token info or None if error
        """
        try:
            checksum_address = Web3.to_checksum_address(token_address)
            token_contract = self.w3.eth.contract(address=checksum_address, abi=ERC20_ABI)
            
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            
            return {
                'address': token_address,
                'name': name,
                'symbol': symbol,
                'decimals': decimals
            }
        except Exception as e:
            print(f"Error getting token info for {token_address}: {e}")
            return None
    
    def get_token_balance(self, token_address: str, wallet_address: str) -> Tuple[Decimal, int]:
        """
        Get ERC-20 token balance
        
        Args:
            token_address: Token contract address
            wallet_address: Wallet address
            
        Returns:
            Tuple of (balance as Decimal, decimals)
        """
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_wallet = Web3.to_checksum_address(wallet_address)
            
            token_contract = self.w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            balance_raw = token_contract.functions.balanceOf(checksum_wallet).call()
            decimals = token_contract.functions.decimals().call()
            
            balance = Decimal(balance_raw) / Decimal(10 ** decimals)
            return balance, decimals
        except Exception as e:
            print(f"Error getting token balance: {e}")
            return Decimal('0'), 18
    
    def get_all_tokens_balances(self, wallet_address: str, token_addresses: List[str]) -> List[Dict]:
        """
        Get balances for multiple tokens
        
        Args:
            wallet_address: Wallet address
            token_addresses: List of token addresses
            
        Returns:
            List of dicts with token info and balance
        """
        balances = []
        
        for token_address in token_addresses:
            try:
                info = self.get_token_info(token_address)
                if not info:
                    continue
                
                balance, _ = self.get_token_balance(token_address, wallet_address)
                
                if balance > 0:
                    balances.append({
                        'address': token_address,
                        'name': info['name'],
                        'symbol': info['symbol'],
                        'decimals': info['decimals'],
                        'balance': balance
                    })
            except Exception as e:
                print(f"Error processing token {token_address}: {e}")
                continue
        
        return balances
    
    def get_wallet_all_tokens(self, wallet_address: str) -> Dict[str, Dict]:
        """
        Get all tokens in wallet using Alchemy API (primary) with fallbacks
        
        Priority:
        1. Alchemy Enhanced API (fast, complete)
        2. BlockVision API (legacy, trial ended)
        3. Native balance only (fallback)
        
        Args:
            wallet_address: Wallet address to check
            
        Returns:
            Dict with token info and balances
        """
        import subprocess
        import json
        import os
        
        # Try Alchemy first (PRIMARY)
        try:
            print("🔍 Trying Alchemy Enhanced API...")
            script_path = os.path.join(os.path.dirname(__file__), 'getTokensAlchemy.js')
            
            result = subprocess.run(
                ['node', script_path, wallet_address],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                
                if data.get('ok'):
                    print(f"✅ Alchemy: Found {data.get('token_count', 0)} tokens")
                    balances = {}
                    
                    # Add native balance
                    native_balance_str = data.get('native_balance', '0')
                    if native_balance_str and float(native_balance_str) > 0:
                        balances['MON'] = {
                            'symbol': 'MON',
                            'name': 'Monad',
                            'balance': Decimal(native_balance_str),
                            'decimals': 18,
                            'address': '0x0000000000000000000000000000000000000000',
                            'verified': True
                        }
                    
                    # Add all tokens
                    for token in data.get('tokens', []):
                        symbol = token.get('symbol', 'UNKNOWN')
                        balance_str = token.get('balance', '0')
                        token_address = token.get('address', '')
                        
                        if float(balance_str) > 0:
                            # Check if token is in verified list
                            is_verified = self._is_token_verified(token_address, symbol)
                            
                            balances[symbol] = {
                                'symbol': symbol,
                                'name': token.get('name', symbol),
                                'balance': Decimal(balance_str),
                                'decimals': token.get('decimals', 18),
                                'address': token_address,
                                'verified': is_verified
                            }
                    
                    return balances
                    
        except Exception as e:
            print(f"⚠️ Alchemy API failed: {e}")
        
        # Fallback to BlockVision (SECONDARY - likely to fail due to trial ended)
        try:
            print("🔄 Falling back to BlockVision API...")
            script_path = os.path.join(os.path.dirname(__file__), 'getTokensBlockVision.js')
            
            # Get API key from config
            api_key = BLOCKVISION_API_KEY
            if not api_key:
                raise ValueError("BLOCKVISION_API_KEY not configured")
            
            result = subprocess.run(
                ['node', script_path, wallet_address, api_key],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise ValueError("BlockVision returned non-zero exit code")
            
            data = json.loads(result.stdout.strip())
            
            if data.get('code') != 0:
                raise ValueError(f"BlockVision error code: {data.get('code')}")
            
            print(f"✅ BlockVision: Processing tokens...")
            balances = {}
            tokens_data = data.get('result', {}).get('data', [])
            
            for token in tokens_data:
                symbol = token.get('symbol', 'UNKNOWN')
                balance = token.get('balance', '0')
                address = token.get('contractAddress', '')
                name = token.get('name', symbol)
                
                # Skip tokens with 0 balance
                try:
                    if float(balance) == 0:
                        continue
                except:
                    continue
                
                balances[symbol] = {
                    'symbol': symbol,
                    'name': name,
                    'balance': Decimal(balance),
                    'address': address,
                    'verified': token.get('verified', False),
                    'imageURL': token.get('imageURL', '')
                }
            
            return balances
            
        except Exception as e:
            print(f"⚠️ BlockVision also failed: {e}")
        
        # Final fallback: Native balance only (TERTIARY)
        print("ℹ️  Using native balance fallback (all APIs unavailable)")
        balances = {}
        native_balance = self.get_native_balance(wallet_address)
        if native_balance:
            balances['MON'] = {
                'symbol': 'MON',
                'name': 'Monad',
                'balance': native_balance,
                'decimals': 18,
                'address': '0x0000000000000000000000000000000000000000',
                'verified': True
            }
        return balances
    
    def get_tokens_from_history(self, wallet_address: str, token_addresses: List[str]) -> Dict[str, Dict]:
        """
        Get token balances from user's history by checking blockchain directly
        Used as fallback when BlockVision API fails
        
        Args:
            wallet_address: Wallet address to check
            token_addresses: List of token addresses from user history
            
        Returns:
            Dict with token info and balances (verified=True for all)
        """
        balances = {}
        
        # Always include native balance
        native_balance = self.get_native_balance(wallet_address)
        if native_balance:
            balances['MON'] = {
                'symbol': 'MON',
                'name': 'Monad',
                'balance': native_balance,
                'address': '0x0000000000000000000000000000000000000000',
                'verified': True
            }
        
        # Check each token from history
        for token_address in token_addresses:
            try:
                info = self.get_token_info(token_address)
                if not info:
                    continue
                
                balance, _ = self.get_token_balance(token_address, wallet_address)
                
                # Only include tokens with balance > 0
                if balance > 0:
                    symbol = info['symbol']
                    balances[symbol] = {
                        'symbol': symbol,
                        'name': info['name'],
                        'balance': balance,
                        'address': token_address,
                        'verified': True,  # Assume tokens from history are verified
                        'decimals': info['decimals']
                    }
            except Exception as e:
                print(f"⚠️ Error checking token {token_address}: {e}")
                continue
        
        return balances
    
    def get_token_price_from_nodejs(self, token_address: str) -> Optional[Decimal]:
        """
        Get token price using Node.js script (GeckoTerminal API + on-chain fallback)
        
        Args:
            token_address: Token contract address
            
        Returns:
            Price in USD or WMON or None if not available
        """
        try:
            import subprocess
            import json
            import os
            
            # Path to price.js script
            script_path = os.path.join(os.path.dirname(__file__), 'price.js')
            
            print(f"🔍 Fetching price via Node.js script for {token_address[:10]}...")
            
            # Set environment variables for the Node.js script
            env = os.environ.copy()
            env['RPC_URL'] = MONAD_TESTNET_RPC_URL
            env['ROUTER'] = DEX_ROUTER_ADDRESS
            env['WMON'] = WETH_ADDRESS
            
            # Call Node.js script
            result = subprocess.run(
                ['node', script_path, token_address],
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            
            if result.returncode != 0:
                print(f"⚠️ Node.js script error: {result.stderr}")
                return None
            
            # Parse JSON output
            output = result.stdout.strip()
            data = json.loads(output)
            
            if not data.get('ok'):
                reason = data.get('reason', 'unknown')
                print(f"⚠️ Price not available: {reason}")
                return None
            
            # Priority: price_usd > price_native
            method = data.get('method', 'unknown')
            
            if data.get('price_usd'):
                price = Decimal(str(data['price_usd']))
                print(f"✅ Price from {method}: ${price} USD")
                return price
            elif data.get('priceNative'):
                price = Decimal(str(data['priceNative']))
                print(f"✅ Price from {method}: {price} WMON")
                return price
            
            print(f"⚠️ No price in response")
            return None
            
        except subprocess.TimeoutExpired:
            print(f"⏱️ Node.js script timeout")
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse Node.js output: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error calling Node.js script: {type(e).__name__}: {e}")
            return None
    
    def get_token_price_onchain(self, token_address: str) -> Optional[Decimal]:
        """
        Get token price directly from DEX on-chain (no external APIs)
        More accurate but slower. Used as fallback when API prices are suspicious.
        
        Args:
            token_address: Token contract address
            
        Returns:
            Price in USD (estimated) or None if unavailable
        """
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_weth = Web3.to_checksum_address(WETH_ADDRESS)
            
            info = self.get_token_info(token_address)
            if not info:
                return None
            
            # Query: 1 token = how many WMON?
            amount_in_wei = int(1 * (10 ** info['decimals']))
            
            path = [checksum_token, checksum_weth]
            amounts = self.router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            
            price_wei = amounts[-1]
            price_in_monad = Decimal(self.w3.from_wei(price_wei, 'ether'))
            
            # For testnet, estimate MONAD = $1 USD
            # In production, you'd fetch real MONAD price
            monad_usd_price = Decimal('1.0')
            price_usd = price_in_monad * monad_usd_price
            
            return price_usd
        except Exception as e:
            # No liquidity or router error
            print(f"⚠️ On-chain price query failed: {e}")
            return None
    
    def get_token_price_in_native(self, token_address: str, amount_in: Decimal = Decimal('1')) -> Optional[Decimal]:
        """
        Get token price - tries multiple sources
        
        Args:
            token_address: Token contract address
            amount_in: Amount of tokens to check price for
            
        Returns:
            Price in native currency or None (if no liquidity or router error)
        """
        # Method 1: Try Node.js script (GeckoTerminal + on-chain)
        nodejs_price = self.get_token_price_from_nodejs(token_address)
        if nodejs_price and nodejs_price > 0:
            return nodejs_price
        
        # Method 2: Try DEX router (may not work if no liquidity)
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_weth = Web3.to_checksum_address(WETH_ADDRESS)
            
            info = self.get_token_info(token_address)
            if not info:
                return None
            
            amount_in_wei = int(amount_in * (10 ** info['decimals']))
            
            path = [checksum_token, checksum_weth]
            amounts = self.router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            
            price_wei = amounts[-1]
            price_native = Decimal(self.w3.from_wei(price_wei, 'ether'))
            
            return price_native
        except Exception as e:
            # Price not available from both sources
            return None
    
    def approve_token(self, token_address: str, spender_address: str, amount: int, 
                     private_key: str, gas_mode: str = 'normal') -> Optional[str]:
        """
        Approve token spending
        
        Args:
            token_address: Token contract address
            spender_address: Spender address (usually router)
            amount: Amount to approve (in wei)
            private_key: Private key for signing
            gas_mode: Gas price mode
            
        Returns:
            Transaction hash or None
        """
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_spender = Web3.to_checksum_address(spender_address)
            
            account = Account.from_key(private_key)
            token_contract = self.w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            
            current_allowance = token_contract.functions.allowance(
                account.address, checksum_spender
            ).call()
            
            if current_allowance >= amount:
                return "ALREADY_APPROVED"
            
            nonce = self.w3.eth.get_transaction_count(account.address)
            
            gas_params = GAS_PRICE_MODES.get(gas_mode, GAS_PRICE_MODES['normal'])
            
            transaction = token_contract.functions.approve(
                checksum_spender, amount
            ).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'maxFeePerGas': self.w3.to_wei(gas_params['maxFeePerGas'], 'gwei'),
                'maxPriorityFeePerGas': self.w3.to_wei(gas_params['maxPriorityFeePerGas'], 'gwei'),
                'chainId': CHAIN_ID
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return tx_hash.hex()
        except Exception as e:
            print(f"Error approving token: {e}")
            return None
    
    def buy_token(self, token_address: str, amount_monad: Decimal, wallet_address: str,
                  private_key: str, slippage: float = 5.0, gas_mode: str = 'normal') -> Optional[Dict]:
        """
        Buy tokens using native currency
        
        Args:
            token_address: Token to buy
            amount_monad: Amount of MONAD to spend
            wallet_address: Buyer's wallet address
            private_key: Private key for signing
            slippage: Slippage tolerance in percentage
            gas_mode: Gas price mode
            
        Returns:
            Dict with transaction info or None
        """
        private_key_to_delete = private_key
        
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_weth = Web3.to_checksum_address(WETH_ADDRESS)
            checksum_wallet = Web3.to_checksum_address(wallet_address)
            
            account = Account.from_key(private_key_to_delete)
            
            amount_in_wei = self.w3.to_wei(amount_monad, 'ether')
            
            path = [checksum_weth, checksum_token]
            amounts_out = self.router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            expected_output = amounts_out[-1]
            
            min_output = int(expected_output * (1 - slippage / 100))
            
            deadline = int(time.time()) + 300
            
            nonce = self.w3.eth.get_transaction_count(account.address)
            gas_params = GAS_PRICE_MODES.get(gas_mode, GAS_PRICE_MODES['normal'])
            
            transaction = self.router_contract.functions.swapExactETHForTokens(
                min_output, path, checksum_wallet, deadline
            ).build_transaction({
                'from': account.address,
                'value': amount_in_wei,
                'nonce': nonce,
                'maxFeePerGas': self.w3.to_wei(gas_params['maxFeePerGas'], 'gwei'),
                'maxPriorityFeePerGas': self.w3.to_wei(gas_params['maxPriorityFeePerGas'], 'gwei'),
                'chainId': CHAIN_ID
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key_to_delete)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            result = {
                'tx_hash': tx_hash.hex(),
                'amount_in': str(amount_monad),
                'expected_output': expected_output,
                'min_output': min_output
            }
            
            return result
            
        except Exception as e:
            print(f"Error buying token: {e}")
            return None
        finally:
            private_key_to_delete = None
            del private_key_to_delete
    
    def sell_token(self, token_address: str, amount_tokens: Decimal, wallet_address: str,
                   private_key: str, slippage: float = 5.0, gas_mode: str = 'normal') -> Optional[Dict]:
        """
        Sell tokens for native currency
        
        Args:
            token_address: Token to sell
            amount_tokens: Amount of tokens to sell
            wallet_address: Seller's wallet address
            private_key: Private key for signing
            slippage: Slippage tolerance in percentage
            gas_mode: Gas price mode
            
        Returns:
            Dict with transaction info or None
        """
        private_key_to_delete = private_key
        
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_weth = Web3.to_checksum_address(WETH_ADDRESS)
            checksum_wallet = Web3.to_checksum_address(wallet_address)
            checksum_router = Web3.to_checksum_address(DEX_ROUTER_ADDRESS)
            
            info = self.get_token_info(token_address)
            if not info:
                return None
            
            amount_in_wei = int(amount_tokens * (10 ** info['decimals']))
            
            approve_hash = self.approve_token(
                token_address, DEX_ROUTER_ADDRESS, amount_in_wei * 2, 
                private_key_to_delete, gas_mode
            )
            
            if approve_hash and approve_hash != "ALREADY_APPROVED":
                time.sleep(3)
            
            account = Account.from_key(private_key_to_delete)
            
            path = [checksum_token, checksum_weth]
            amounts_out = self.router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            expected_output = amounts_out[-1]
            
            min_output = int(expected_output * (1 - slippage / 100))
            
            # Deadline: 20 minutes (same as Monad official repo)
            deadline = int(time.time()) + (60 * 20)
            
            nonce = self.w3.eth.get_transaction_count(account.address)
            gas_params = GAS_PRICE_MODES.get(gas_mode, GAS_PRICE_MODES['normal'])
            
            transaction = self.router_contract.functions.swapExactTokensForETH(
                amount_in_wei, min_output, path, checksum_wallet, deadline
            ).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'maxFeePerGas': self.w3.to_wei(gas_params['maxFeePerGas'], 'gwei'),
                'maxPriorityFeePerGas': self.w3.to_wei(gas_params['maxPriorityFeePerGas'], 'gwei'),
                'chainId': CHAIN_ID
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key_to_delete)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            result = {
                'tx_hash': tx_hash.hex(),
                'amount_in': str(amount_tokens),
                'expected_output': self.w3.from_wei(expected_output, 'ether'),
                'min_output': self.w3.from_wei(min_output, 'ether'),
                'approve_hash': approve_hash if approve_hash != "ALREADY_APPROVED" else None
            }
            
            return result
            
        except Exception as e:
            print(f"Error selling token: {e}")
            return None
        finally:
            private_key_to_delete = None
            del private_key_to_delete
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> bool:
        """
        Wait for transaction confirmation
        
        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return receipt['status'] == 1
        except Exception as e:
            print(f"Error waiting for transaction: {e}")
            return False
    
    def send_token(self, token_address: str, recipient_address: str, amount: Decimal,
                   wallet_address: str, private_key: str) -> Optional[Dict]:
        """
        Send ERC20 tokens to another address
        
        Args:
            token_address: Token contract address
            recipient_address: Recipient's wallet address  
            amount: Amount of tokens to send
            wallet_address: Sender's wallet address
            private_key: Private key for signing
            
        Returns:
            Dict with transaction info or None
        """
        private_key_to_delete = private_key
        
        try:
            checksum_token = Web3.to_checksum_address(token_address)
            checksum_recipient = Web3.to_checksum_address(recipient_address)
            checksum_wallet = Web3.to_checksum_address(wallet_address)
            
            # Get token contract
            token_contract = self.w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            
            # Get token decimals
            decimals = token_contract.functions.decimals().call()
            
            # Convert amount to smallest unit
            amount_in_smallest_unit = int(amount * Decimal(10 ** decimals))
            
            # Build transfer transaction
            nonce = self.w3.eth.get_transaction_count(checksum_wallet)
            
            # Get gas price
            gas_settings = GAS_PRICE_MODES.get('normal', GAS_PRICE_MODES['normal'])
            max_fee = self.w3.to_wei(gas_settings['maxFeePerGas'], 'gwei')
            max_priority = self.w3.to_wei(gas_settings['maxPriorityFeePerGas'], 'gwei')
            
            # Build transaction
            transfer_txn = token_contract.functions.transfer(
                checksum_recipient,
                amount_in_smallest_unit
            ).build_transaction({
                'from': checksum_wallet,
                'nonce': nonce,
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': max_priority,
                'gas': 100000,
                'chainId': CHAIN_ID
            })
            
            # Sign and send
            signed_txn = self.w3.eth.account.sign_transaction(transfer_txn, private_key_to_delete)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            result = {
                'tx_hash': tx_hash.hex(),
                'amount': str(amount),
                'recipient': recipient_address
            }
            
            return result
            
        except Exception as e:
            print(f"Error sending token: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            private_key_to_delete = None
            del private_key_to_delete

blockchain_manager = BlockchainManager()
