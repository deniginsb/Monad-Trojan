// price.js — cek harga realtime 1 file
// Cara pakai: node price.js 0xTOKEN_ADDRESS
// Optional ENV (fallback on-chain):
//   RPC_URL=https://testnet-rpc.monad.xyz
//   ROUTER=0x74a116b1bb7894d3cfbc4b1a12f59ea95f3fff81
//   WMON=0x760afe86e5de5fa0ee542fc7b7b713e1c5425701

const addrArg = (process.argv[2] || "").toLowerCase();
if (!addrArg || !/^0x[0-9a-f]{40}$/.test(addrArg)) {
  console.error("Usage: node price.js <TOKEN_ADDRESS>");
  process.exit(1);
}

// --- 1) Coba via GeckoTerminal (cepat, kalau tersedia) ---
async function getFromGeckoTerminal(tokenAddr) {
  const urls = [
    `https://api.geckoterminal.com/api/v2/networks/monad-testnet/tokens/${tokenAddr}`,
    `https://api.geckoterminal.com/api/v2/networks/monad_testnet/tokens/${tokenAddr}`,
  ];
  for (const url of urls) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) continue;
      const json = await res.json();
      // Struktur umum GT: data.attributes.{price_usd, price_native}
      const a = json?.data?.attributes || {};
      if (a.price_usd || a.price_native) {
        return {
          source: "geckoterminal",
          priceUsd: a.price_usd ? Number(a.price_usd) : null,
          priceNative: a.price_native ? Number(a.price_native) : null,
          symbol: a.symbol || null,
          name: a.name || null,
        };
      }
    } catch (_) {}
  }
  return null;
}

// --- 2) Fallback on-chain via getAmountsOut (perlu ethers & router) ---
async function getOnChainPrice(tokenAddr) {
  const { ethers } = await import("ethers");

  const RPC_URL = process.env.RPC_URL || "https://testnet-rpc.monad.xyz";
  const ROUTER = (process.env.ROUTER || "").toLowerCase() || "0x74a116b1bb7894d3cfbc4b1a12f59ea95f3fff81";
  const WMON   = (process.env.WMON   || "").toLowerCase() || "0x760afe86e5de5fa0ee542fc7b7b713e1c5425701";

  const provider = new ethers.JsonRpcProvider(RPC_URL);

  const ERC20_ABI = [
    "function decimals() view returns (uint8)",
    "function symbol() view returns (string)",
  ];
  const ROUTER_ABI = [
    "function getAmountsOut(uint256 amountIn, address[] calldata path) external view returns (uint256[] memory)"
  ];
  const FACTORY_ABI = [
    "function factory() external view returns (address)"
  ];
  const UNI_FACTORY_ABI = [
    "function getPair(address tokenA, address tokenB) external view returns (address)"
  ];

  const router = new ethers.Contract(ROUTER, [...ROUTER_ABI, ...FACTORY_ABI], provider);
  const factoryAddr = await router.factory().catch(() => ethers.ZeroAddress);
  const factory = factoryAddr !== ethers.ZeroAddress
    ? new ethers.Contract(factoryAddr, UNI_FACTORY_ABI, provider)
    : null;

  const token = new ethers.Contract(tokenAddr, ERC20_ABI, provider);
  const wmon  = new ethers.Contract(WMON, ERC20_ABI, provider);

  const [decT, decW, symT, symW] = await Promise.all([
    token.decimals(), wmon.decimals(),
    token.symbol().catch(()=>null), wmon.symbol().catch(()=>null)
  ]);

  // cek jalur: langsung WMON<->TOKEN? kalau tidak, coba path via WMON
  let path = [WMON, tokenAddr];
  if (factory) {
    const pairDirect = await factory.getPair(WMON, tokenAddr);
    if (pairDirect === ethers.ZeroAddress) {
      // kalau tidak ada pair langsung, nggak ada jalur sederhana — return null
      return null;
    }
  }

  const amountIn = ethers.parseUnits("1", decW); // 1 WMON
  const routerPure = new ethers.Contract(ROUTER, ROUTER_ABI, provider);

  let amounts;
  try {
    amounts = await routerPure.getAmountsOut(amountIn, path);
  } catch {
    return null; // no path/liquidity
  }

  const out = amounts.at(-1);
  const priceInToken = Number(ethers.formatUnits(out, decT)); // berapa TOKEN per 1 WMON

  return {
    source: "onchain_getAmountsOut",
    base: symW || "WMON",
    quote: symT || "TOKEN",
    priceNative: 1 / priceInToken, // 1 TOKEN ≈ ? WMON
    note: "computed from getAmountsOut(1 WMON → TOKEN)"
  };
}

// --- Runner ---
(async () => {
  // 1) Coba API explorer (GT)
  const gt = await getFromGeckoTerminal(addrArg);
  if (gt) {
    console.log(JSON.stringify({
      ok: true,
      method: "geckoterminal",
      token: addrArg,
      name: gt.name,
      symbol: gt.symbol,
      price_usd: gt.priceUsd,
      price_native: gt.priceNative,
    }, null, 2));
    return;
  }

  // 2) Fallback on-chain
  try {
    const oc = await getOnChainPrice(addrArg);
    if (oc) {
      console.log(JSON.stringify({ ok: true, method: oc.source, token: addrArg, ...oc }, null, 2));
    } else {
      console.log(JSON.stringify({ ok: false, reason: "no_liquidity_or_no_path", token: addrArg }, null, 2));
    }
  } catch (e) {
    console.log(JSON.stringify({ ok: false, reason: (e?.message || e), token: addrArg }, null, 2));
  }
})();
