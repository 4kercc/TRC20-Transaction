from flask import Flask, render_template, request
import requests
import time
from datetime import datetime

app = Flask(__name__)

# TRON GRID API 配置
API_KEY = "f7b303cb-aa53-47d0-bfa2-e5f4398e0f14"
BASE_URL = "https://api.trongrid.io"

def to_timestamp(dt_str):
    """将日期时间字符串（支持 'YYYY-MM-DDTHH:MM' 和 'YYYY-MM-DD HH:MM:SS'）转换为毫秒级时间戳"""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(dt_str, fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间格式: {dt_str}")

def get_trc20_tx(address, start_ts, end_ts, contract=None):
    """
    获取指定地址在给定时间范围内的 TRC20 交易数据。

    Args:
        address (str): TRON 地址。
        start_ts (int): 开始时间戳（毫秒）。
        end_ts (int): 结束时间戳（毫秒）。
        contract (str, optional): TRC20 合约地址。如果为空，则获取所有 TRC20 交易。

    Returns:
        tuple: (收入总额, 收入笔数, 支出总额, 支出笔数)
    """
    url = f"{BASE_URL}/v1/accounts/{address}/transactions/trc20"
    headers = {"TRON-PRO-API-KEY": API_KEY}
    params = {
        "only_confirmed": "true",
        "limit": 200,
        "order_by": "block_timestamp,desc"
    }

    income_total = 0.0
    income_count = 0
    outgo_total = 0.0
    outgo_count = 0
    fingerprint = None
    page = 0
    max_pages = 30  # 设置最大页数，防止无限循环

    while page < max_pages:
        if fingerprint:
            params["fingerprint"] = fingerprint
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10) # 增加超时
            response.raise_for_status() # 检查HTTP错误
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"请求TRON API失败: {e}")
            break # 退出循环
        
        tx_list = data.get("data", [])
        if not tx_list:
            break

        for tx in tx_list:
            ts = tx.get("block_timestamp")
            if ts is None:
                continue

            # 过滤掉超出结束时间戳的交易
            if ts > end_ts:
                continue
            
            # 如果交易时间早于开始时间戳，说明已经遍历到旧数据，可以直接返回
            if ts < start_ts:
                # 注意：API是按desc排序，所以一旦遇到早于start_ts的，后续的也都会更早
                return income_total, income_count, outgo_total, outgo_count

            # 如果指定了合约地址，则过滤
            if contract and tx.get("token_info", {}).get("address") != contract:
                continue

            # 检查 'value' 键是否存在，并处理可能的类型转换错误
            try:
                amount = float(tx.get("value", 0)) / (10 ** int(tx.get("token_info", {}).get("decimals", 0)))
            except (ValueError, TypeError):
                print(f"解析交易金额失败，交易ID: {tx.get('transaction_id')}")
                continue

            if tx.get("to") == address:
                income_total += amount
                income_count += 1
            elif tx.get("from") == address:
                outgo_total += amount
                outgo_count += 1

        fingerprint = data.get("meta", {}).get("fingerprint")
        if not fingerprint:
            break

        page += 1
        time.sleep(0.25) # 降低请求频率

    return income_total, income_count, outgo_total, outgo_count

@app.route("/", methods=["GET", "POST"])
def index():
    """主页路由，处理表单提交和结果显示"""
    result = None
    address = request.form.get("address", "") # 默认地址
    start_time_str = request.form.get("start_time", "2023-01-01 00:00:00") # 默认开始时间
    end_time_str = request.form.get("end_time", "2023-02-01 00:00:00") # 默认结束时间
    token_contract = request.form.get("token_contract", "") # 默认不填合约地址

    if request.method == "POST":
        try:
            start_ts = to_timestamp(start_time_str)
            end_ts = to_timestamp(end_time_str)

            income_total, income_count, outgo_total, outgo_count = get_trc20_tx(
                address, start_ts, end_ts, token_contract
            )

            result = {
                "address": address,
                "start_time": start_time_str,
                "end_time": end_time_str,
                "income_count": income_count,
                "income_total": f"{income_total:.6f}",
                "outgo_count": outgo_count,
                "outgo_total": f"{outgo_total:.6f}",
                "token_contract": token_contract if token_contract else "所有TRC20代币"
            }
        except ValueError:
            result = {"error": "日期时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 格式。"}
        except Exception as e:
            result = {"error": f"发生错误: {e}"}

    return render_template("index.html", result=result, 
                           address=address, start_time=start_time_str, 
                           end_time=end_time_str, token_contract=token_contract)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
