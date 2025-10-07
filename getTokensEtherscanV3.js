#!/usr/bin/env node
/**
 * getTokensEtherscanV3.js
 * Fetch wallet tokens using Etherscan v2 API with BlockVision fallback
 * 
 * Usage:
 *   node getTokensEtherscanV3.js <walletAddress> [blockvisionApiKey]
 * 
 * Example:
 *   node getTokensEtherscanV3.js 0xb0079307d6143030D841CF0b9C4de42EB67119F2
 */

import fetch from "node-fetch";

// ======= CONFIGURATION =======
const ETHERSCAN_API_KEY = "1BKWWWJSXUF9PJVG49SH7VP3PEPNFY41N6";
const CHAIN_ID = 10143; // Monad Testnet
const ETHERSCAN_BASE = "https://api.etherscan.io/v2/api";
const BLOCKVISION_BASE = "https://api.blockvision.org/v2/monad";
// ============================

// Helper: Build query string
const qs = (obj) =>
  Object.entries(obj)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");

// Helper: Format big number with decimals
function formatUnits(value, decimals = 18) {
  const bi = BigInt(value);
  const s = bi.toString().padStart(decimals + 1, "0");
  const intPart = s.slice(0, -decimals) || "0";
  const fracPart = s.slice(-decimals).replace(/0+$/, "");
  return fracPart ? `${intPart}.${fracPart}` : intPart;
}

// ===== ETHERSCAN V2 API =====

async function callEtherscan(params) {
  const url = `${ETHERSCAN_BASE}?${qs({
    chainid: CHAIN_ID,
    apikey: ETHERSCAN_API_KEY,
    ...params,
  })}`;

  try {
    const res = await fetch(url, {
      timeout: 10000,
      headers: { "User-Agent": "MonadTrojanBot/1.0" },
    });

    const text = await res.text();

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`Failed to parse JSON: ${text.slice(0, 200)}`);
    }

    // Check API response status
    if (data.status && data.status !== "1") {
      const msg = data.message || data.result || "Unknown error";
      throw new Error(`Etherscan API error: ${msg}`);
    }

    return data;
  } catch (error) {
    throw new Error(`Etherscan request failed: ${error.message}`);
  }
}

async function getEtherscanNativeBalance(address) {
  const data = await callEtherscan({
    module: "account",
    action: "balance",
    address,
    tag: "latest",
  });
  return BigInt(data.result || "0");
}

async function getEtherscanTokens(address) {
  const data = await callEtherscan({
    module: "account",
    action: "addresstokenbalance",
    address,
  });

  const result = data.result || [];
  
  // Format tokens
  const tokens = [];
  for (const t of result) {
    try {
      const balance = BigInt(t.TokenQuantity || "0");
      if (balance === 0n) continue; // Skip zero balance

      const decimals = Number(t.TokenDivisor || "18");
      const symbol = t.TokenSymbol || t.TokenName || "UNKNOWN";
      const name = t.TokenName || symbol;
      const address_token = t.TokenAddress || "";

      tokens.push({
        symbol,
        name,
        balance: formatUnits(balance, decimals),
        decimals,
        address: address_token,
        raw_balance: balance.toString(),
        source: "etherscan",
      });
    } catch (e) {
      console.error(`Error parsing token:`, e.message, t);
    }
  }

  return tokens;
}

// ===== BLOCKVISION API (FALLBACK) =====

async function callBlockVision(endpoint, apiKey) {
  if (!apiKey) {
    throw new Error("BlockVision API key required");
  }

  const url = `${BLOCKVISION_BASE}${endpoint}`;

  try {
    const res = await fetch(url, {
      timeout: 10000,
      headers: {
        "x-api-key": apiKey,
        "Content-Type": "application/json",
        "User-Agent": "MonadTrojanBot/1.0",
      },
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }

    return await res.json();
  } catch (error) {
    throw new Error(`BlockVision request failed: ${error.message}`);
  }
}

async function getBlockVisionTokens(address, apiKey) {
  const data = await callBlockVision(`/account/tokens?address=${address}`, apiKey);

  if (data.code !== 0) {
    throw new Error(`BlockVision error: ${data.message || "Unknown error"}`);
  }

  const tokens = [];
  const tokenList = data.data || [];

  for (const t of tokenList) {
    try {
      const balance = BigInt(t.balance || "0");
      if (balance === 0n) continue;

      const decimals = Number(t.decimals || "18");
      const symbol = t.symbol || t.name || "UNKNOWN";

      tokens.push({
        symbol,
        name: t.name || symbol,
        balance: formatUnits(balance, decimals),
        decimals,
        address: t.address || "",
        raw_balance: balance.toString(),
        source: "blockvision",
      });
    } catch (e) {
      console.error(`Error parsing token:`, e.message, t);
    }
  }

  return tokens;
}

// ===== MAIN FUNCTION WITH FALLBACK =====

async function getAllTokens(walletAddress, blockvisionApiKey = null) {
  const results = {
    success: false,
    source: null,
    native_balance: "0",
    tokens: [],
    error: null,
  };

  // Try Etherscan first
  try {
    console.error("🔍 Trying Etherscan v2 API...");
    
    // Get native balance
    const nativeBalance = await getEtherscanNativeBalance(walletAddress);
    results.native_balance = formatUnits(nativeBalance, 18);

    // Get tokens
    const tokens = await getEtherscanTokens(walletAddress);
    
    results.success = true;
    results.source = "etherscan";
    results.tokens = tokens;

    console.error(`✅ Etherscan: Found ${tokens.length} tokens`);
    return results;

  } catch (etherscanError) {
    console.error(`⚠️  Etherscan failed: ${etherscanError.message}`);

    // Fallback to BlockVision
    if (blockvisionApiKey) {
      try {
        console.error("🔄 Falling back to BlockVision API...");
        
        const tokens = await getBlockVisionTokens(walletAddress, blockvisionApiKey);
        
        // BlockVision includes native balance in tokens (MON symbol)
        const monToken = tokens.find(t => t.symbol === "MON" || t.symbol === "MONAD");
        if (monToken) {
          results.native_balance = monToken.balance;
        }

        results.success = true;
        results.source = "blockvision";
        results.tokens = tokens.filter(t => t.symbol !== "MON" && t.symbol !== "MONAD");

        console.error(`✅ BlockVision: Found ${results.tokens.length} tokens`);
        return results;

      } catch (blockvisionError) {
        console.error(`⚠️  BlockVision failed: ${blockvisionError.message}`);
        results.error = `Both APIs failed - Etherscan: ${etherscanError.message}, BlockVision: ${blockvisionError.message}`;
      }
    } else {
      results.error = `Etherscan failed: ${etherscanError.message}`;
    }
  }

  return results;
}

// ===== CLI INTERFACE =====

async function main() {
  const args = process.argv.slice(2);
  
  if (args.length < 1) {
    console.error("Usage: node getTokensEtherscanV3.js <walletAddress> [blockvisionApiKey]");
    console.error("\nExample:");
    console.error("  node getTokensEtherscanV3.js 0xb0079307d6143030D841CF0b9C4de42EB67119F2");
    console.error("  node getTokensEtherscanV3.js 0xb00... YOUR_BLOCKVISION_KEY");
    process.exit(1);
  }

  const walletAddress = args[0];
  const blockvisionApiKey = args[1] || process.env.BLOCKVISION_API_KEY;

  console.error(`\n📊 Fetching tokens for wallet: ${walletAddress}`);
  console.error(`🔗 Chain: Monad Testnet (${CHAIN_ID})\n`);

  try {
    const results = await getAllTokens(walletAddress, blockvisionApiKey);

    if (!results.success) {
      console.error(`\n❌ Error: ${results.error}`);
      process.exit(1);
    }

    // Output results as JSON for easy parsing
    console.log(JSON.stringify({
      ok: true,
      source: results.source,
      wallet: walletAddress,
      native_balance: results.native_balance,
      token_count: results.tokens.length,
      tokens: results.tokens,
    }, null, 2));

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
export { getAllTokens, getEtherscanTokens, getBlockVisionTokens };
