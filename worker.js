export default {
  async fetch(request, env, ctx) {
    if (request.method === "GET") {
      return new Response("Go to / (HTML page)", { status: 200 });
    }

    if (request.method === "POST" && new URL(request.url).pathname === "/api") {
      const body = await request.json();
      const { address, start_time, end_time, token_contract } = body;

      const startTs = Date.parse(start_time);
      const endTs = Date.parse(end_time);

      const result = await getTrc20Tx(address, startTs, endTs, token_contract);
      return Response.json(result);
    }

    return new Response("Not Found", { status: 404 });
  }
}

async function getTrc20Tx(address, startTs, endTs, contract) {
  const url = `https://api.trongrid.io/v1/accounts/${address}/transactions/trc20`;
  const headers = {
    "TRON-PRO-API-KEY": "f7b303cb-aa53-47d0-bfa2-e5f4398e0f14"
  };

  let income_total = 0, income_count = 0, outgo_total = 0, outgo_count = 0;
  let fingerprint = null;
  let page = 0;

  while (page < 30) {
    const params = new URLSearchParams({
      only_confirmed: "true",
      limit: "200",
      order_by: "block_timestamp,desc"
    });
    if (fingerprint) params.set("fingerprint", fingerprint);

    const res = await fetch(`${url}?${params.toString()}`, { headers });
    const data = await res.json();
    const txs = data.data || [];
    if (txs.length === 0) break;

    for (const tx of txs) {
      const ts = tx.block_timestamp;
      if (ts > endTs) continue;
      if (ts < startTs) return format(income_total, income_count, outgo_total, outgo_count, contract);

      if (contract && tx.token_info?.address !== contract) continue;

      const amount = parseFloat(tx.value) / 10 ** parseInt(tx.token_info?.decimals || 0);

      if (tx.to === address) {
        income_total += amount;
        income_count++;
      } else if (tx.from === address) {
        outgo_total += amount;
        outgo_count++;
      }
    }

    fingerprint = data.meta?.fingerprint;
    if (!fingerprint) break;
    page++;
  }

  return format(income_total, income_count, outgo_total, outgo_count, contract);
}

function format(income_total, income_count, outgo_total, outgo_count, contract) {
  return {
    income_total: income_total.toFixed(6),
    income_count,
    outgo_total: outgo_total.toFixed(6),
    outgo_count,
    token_contract: contract || "所有 TRC20"
  };
}
