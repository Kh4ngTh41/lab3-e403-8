import requests

def get_crypto_price(symbol="BTC"):
    """
    Tool cho Agent: Lấy giá của một đồng coin bất kỳ qua DIA API.
    """
    url = f"https://api.diadata.org/v1/quotation/{symbol}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Dữ liệu của DIA đã được Normalize sẵn, ta chỉ cần bốc ra xài
        normalized_result = {
            "symbol": data.get("Symbol"),
            "name": data.get("Name"),
            "price_usd": round(data.get("Price", 0), 2),
            "price_yesterday": round(data.get("PriceYesterday", 0), 2),
            "last_updated": data.get("Time")
        }
        return normalized_result

    except Exception as e:
        return f"Lỗi: Không lấy được dữ liệu cho {symbol}. Chi tiết: {e}"

# Khởi chạy thử
print(" Đang lấy giá Bitcoin...")
btc_data = get_crypto_price("BTC")
print(btc_data)
# Output sẽ đẹp như vầy: {'symbol': 'BTC', 'name': 'Bitcoin', 'price_usd': 68500.25, 'price_yesterday': 67100.10, 'last_updated': '2026-04-06T...'}