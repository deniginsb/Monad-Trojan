#!/usr/bin/env node
/**
 * getTokensAlchemy.js
 * Fetch all ERC-20 token balances using Alchemy Enhanced APIs
 * 
 * Features:
 * - alchemy_getTokenBalances: Get ALL tokens in one call
 * - alchemy_getTokenMetadata: Get token details (name, symbol, decimals)
 * - Works for Monad Testnet
 * 
 * Usage:
 *   node getTokensAlchemy.js <walletAddress>
 * 
 * Example:
 *   node getTokensAlchemy.js 0xb0079307d6143030D841CF0b9C4de42EB67119F2
 */

import fetch from "node-fetch";

// ======= CONFIGURATION =======
// Alchemy URL with API key already included
const ALCHEMY_URL = process.env.ALCHEMY_MONAD_URL || 
  "https://monad-testnet.g.alchemy.com/v2/XNBMVXBwNDnoNZHXqcpzB";
// ============================

/**
 * Make JSON-RPC call to Alchemy
 */
async function alchemyRPC(method, params) {
  try {
    const response = await fetch(ALCHEMY_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 1,
        method,
        params,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    const data = await response.json();

    if (data.error) {
      throw new Error(`RPC Error: ${data.error.message || JSON.stringify(data.error)}`);
    }

    return data.result;
  } catch (error) {
    throw new Error(`Alchemy RPC failed: ${error.message}`);
  }
}

/**
 * Get native balance (MON/MONAD)
 */
async function getNativeBalance(address) {
  try {
    const balanceHex = await alchemyRPC("eth_getBalance", [address, "latest"]);
    const balanceWei = BigInt(balanceHex);
    const balanceEther = Number(balanceWei) / 1e18;
    return balanceEther.toString();
  } catch (error) {
    console.error(`Error getting native balance: ${error.message}`);
    return "0";
  }
}

/**
 * Get all ERC-20 token balances for an address
 * Uses Alchemy's enhanced API - gets ALL tokens in one call!
 */
async function getTokenBalances(address) {
  try {
    // "erc20" = get ALL ERC-20 tokens ever held by this address
    const result = await alchemyRPC("alchemy_getTokenBalances", [address, "erc20"]);
    
    return result.tokenBalances || [];
  } catch (error) {
    console.error(`Error getting token balances: ${error.message}`);
    return [];
  }
}

/**
 * Get token metadata (name, symbol, decimals)
 */
async function getTokenMetadata(contractAddress) {
  try {
    const metadata = await alchemyRPC("alchemy_getTokenMetadata", [contractAddress]);
    return metadata;
  } catch (error) {
    console.error(`Error getting metadata for ${contractAddress}: ${error.message}`);
    return {
      name: "Unknown",
      symbol: "UNKNOWN",
      decimals: 18,
    };
  }
}

/**
 * Format token balance from hex to human-readable
 */
function formatTokenBalance(balanceHex, decimals) {
  try {
    if (!balanceHex || balanceHex === "0x" || balanceHex === "0x0") {
      return "0";
    }

    const balance = BigInt(balanceHex);
    if (balance === 0n) {
      return "0";
    }

    const divisor = BigInt(10 ** decimals);
    const intPart = balance / divisor;
    const fracPart = balance % divisor;

    if (fracPart === 0n) {
      return intPart.toString();
    }

    const fracStr = fracPart.toString().padStart(decimals, "0");
    const trimmedFrac = fracStr.replace(/0+$/, "");
    
    return `${intPart}.${trimmedFrac}`;
  } catch (error) {
    console.error(`Error formatting balance ${balanceHex}:`, error);
    return "0";
  }
}

/**
 * Get complete wallet overview with all tokens
 */
async function getWalletTokens(walletAddress) {
  console.error(`\n🔍 Fetching tokens via Alchemy Enhanced API...`);
  console.error(`📍 Wallet: ${walletAddress}`);
  console.error(`🔗 Network: Monad Testnet\n`);

  const results = {
    ok: true,
    source: "alchemy-enhanced",
    wallet: walletAddress,
    native_balance: "0",
    tokens: [],
  };

  try {
    // Step 1: Get native balance
    console.error(`⏳ Fetching native balance...`);
    results.native_balance = await getNativeBalance(walletAddress);
    console.error(`✅ Native: ${results.native_balance} MON`);

    // Step 2: Get all token balances in ONE call!
    console.error(`⏳ Fetching all ERC-20 token balances...`);
    const tokenBalances = await getTokenBalances(walletAddress);
    console.error(`✅ Found ${tokenBalances.length} token holdings`);

    // Step 3: Filter non-zero balances and get metadata
    console.error(`⏳ Fetching token metadata...`);
    const nonZeroTokens = tokenBalances.filter(
      (t) => t.tokenBalance && t.tokenBalance !== "0x" && t.tokenBalance !== "0x0"
    );

    if (nonZeroTokens.length === 0) {
      console.error(`ℹ️  No tokens with non-zero balance found`);
      return results;
    }

    // Fetch metadata for all tokens in parallel (fast!)
    const metadataPromises = nonZeroTokens.map(async (token) => {
      const metadata = await getTokenMetadata(token.contractAddress);
      const decimals = metadata.decimals || 18;
      const formattedBalance = formatTokenBalance(token.tokenBalance, decimals);

      // Skip if still zero after formatting
      if (formattedBalance === "0" || formattedBalance === "0.0") {
        return null;
      }

      return {
        address: token.contractAddress,
        symbol: metadata.symbol || "UNKNOWN",
        name: metadata.name || "Unknown Token",
        decimals,
        balance: formattedBalance,
        raw_balance: token.tokenBalance,
      };
    });

    const tokensWithMetadata = await Promise.all(metadataPromises);
    
    // Filter out nulls
    results.tokens = tokensWithMetadata.filter((t) => t !== null);

    console.error(`✅ Processed ${results.tokens.length} tokens with metadata`);

    return results;
  } catch (error) {
    console.error(`❌ Error: ${error.message}`);
    results.ok = false;
    results.error = error.message;
    return results;
  }
}

/**
 * CLI Interface
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length < 1) {
    console.error("Usage: node getTokensAlchemy.js <walletAddress>");
    console.error("\nExample:");
    console.error("  node getTokensAlchemy.js 0xb0079307d6143030D841CF0b9C4de42EB67119F2");
    console.error("\nNote: Uses Alchemy Enhanced APIs (alchemy_getTokenBalances + alchemy_getTokenMetadata)");
    console.error("      This is MUCH faster than checking tokens one by one!");
    process.exit(1);
  }

  const walletAddress = args[0];

  try {
    const results = await getWalletTokens(walletAddress);

    if (!results.ok) {
      console.error(`\n❌ Failed: ${results.error}`);
      process.exit(1);
    }

    // Output as JSON for easy parsing
    console.log(
      JSON.stringify(
        {
          ok: true,
          source: results.source,
          wallet: walletAddress,
          native_balance: results.native_balance,
          token_count: results.tokens.length,
          tokens: results.tokens,
        },
        null,
        2
      )
    );

    console.error(`\n✅ Success! Found ${results.tokens.length} tokens`);
  } catch (error) {
    console.error(`\n❌ Unexpected error: ${error.message}`);
    console.error(error.stack);
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error("Fatal error:", err);
    process.exit(1);
  });
}

// Export for use as module
export { getWalletTokens, getNativeBalance, getTokenBalances, getTokenMetadata };
