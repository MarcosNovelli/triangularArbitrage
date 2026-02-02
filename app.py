import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import sys
import requests
from decimal import Decimal, ROUND_DOWN
from binance.client import Client
import os
import datetime as dt
import math


# ===== GUI-safe print redirection =====
class TextRedirector:
    def __init__(self, widget, root):
        self.widget = widget
        self.root = root

    def write(self, string):
        # Schedule text insertion on the main thread
        self.root.after(0, self._append_text, string)

    def _append_text(self, string):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, string)
        self.widget.see(tk.END)  # Always scroll to bottom
        self.widget.configure(state='disabled')

    def flush(self):
        pass

# ===== Trading Bot Class =====
class TradingBot:
    def __init__(self, api_key, api_secret, usdt_amount, threshold, use_limit_entry, max_deviation):
        self.client = Client(api_key=api_key, api_secret=api_secret)
        self.api_key, self.api_secret = api_key, api_secret
        self.usdt_amount = usdt_amount
        self.threshold = threshold
        self.use_limit = use_limit_entry
        self.max_deviation = max_deviation
        self.running = False
        self.fee = 0.001

    def get_all_prices(self):
        tickers = self.client.get_orderbook_tickers()
        return {item['symbol']: (float(item['bidPrice']), float(item['askPrice'])) for item in tickers}

    def get_trading_pairs(self):
        exchange_info = self.client.get_exchange_info()
        pairs = {}
        for s in exchange_info['symbols']:
            if s['status'] == 'TRADING':
                base = s['baseAsset']
                quote = s['quoteAsset']
                symbol = s['symbol']
                pairs.setdefault(base, []).append((quote, symbol, 'base-quote'))
                pairs.setdefault(quote, []).append((base, symbol, 'quote-base'))
        return pairs

    def find_usdt_triangles(self, pairs):
        triangles = []
        start_token = 'USDT'
        for A_info in pairs.get(start_token, []):
            A, sym1, dir1 = A_info
            for B_info in pairs.get(A, []):
                B, sym2, dir2 = B_info
                if B == start_token:
                    continue
                for C_info in pairs.get(B, []):
                    C, sym3, dir3 = C_info
                    if C == start_token:
                        triangles.append([
                            (start_token, A, sym1, dir1),
                            (A, B, sym2, dir2),
                            (B, start_token, sym3, dir3)
                        ])
        return triangles

    def calculate_arbitrage(self, triangle, prices, threshold):
        amt = 1.0
        steps = []
        for from_sym, to_sym, pair, direction in triangle:
            price = prices.get(pair)
            if not price:
                return None
            if direction == 'base-quote':
                amt = amt * price[0] * (1 - self.fee)
                steps.append((pair, direction, price[0], amt))
            else:
                amt = amt / price[1] * (1 - self.fee)
                steps.append((pair, direction, price[1], amt))
        profit_pct = ((amt - 1.0) / 1.0) * 100
        if profit_pct > threshold:
            return {'triangle': triangle, 'steps': steps, 'profit_pct': profit_pct}
        return None

    def main_loop(self):
        print("🔁 Starting trading bot...\n")
        while self.running:
            try:
                pairs = self.get_trading_pairs()
                triangles = self.find_usdt_triangles(pairs)
                prices = self.get_all_prices()
                print(f"({str(dt.datetime.now())[:19]}) 🔍 Checking {len(triangles)} USDT-based triangles...")

                profitable = []
                i = 0
                while len(profitable) < 1 and i < len(triangles):
                    tri = triangles[i]
                    
                    result = self.calculate_arbitrage(tri, prices, self.threshold)
                    if result:
                        profitable.append(result)
                    i += 1
                
                profitable.sort(key=lambda x: x['profit_pct'], reverse=True)
                if profitable:
                    best = profitable[0]
                    print(f"🏅 Best Profit: {best['profit_pct']:.4f}%")
                    for step in best['steps']:
                        pair, direction, price, amt = step
                        print(f" - {pair} ({direction}) @ {price:.8f} → Amount: {amt:.6f}")


                    execute_triangle(self.api_key, self.api_secret, best['triangle'], self.usdt_amount, self.use_limit, self.max_deviation, best['steps'][1][2]) 
                    print(f"Expected final value: { self.usdt_amount + self.usdt_amount * best['profit_pct'] / 100}")
                else:
                    print("No profitable trades found.")
                print("")
                time.sleep(5)
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)

        print("⏹ Bot stopped.")

    def start(self):

        if not self.running:
            self.running = True
            threading.Thread(target=self.main_loop, daemon=True).start()

    def stop(self):
        self.running = False

def create_logs_file(key, secret):
    filename = "logs.txt"

    # Check if the file exists
    if not os.path.exists(filename):
        # Create the file
        with open(filename, "w") as f:
            f.write(f"{key}\n") 
            f.write(f"{secret}") 

        print(f"File '{filename}' created.")
    else:
        print(f"File '{filename}' already exists.")
    return


def round_step_size(quantity: float, step_size: float) -> str:
    """
    Round quantity down to the nearest step_size.
    """
    if str(step_size) == "1.0":
        quantity = format(float(quantity), '.8f')
        return math.floor(float(quantity))

    precision = int(round(-Decimal(str(step_size)).as_tuple().exponent))
    rounded_qty = Decimal(str(quantity)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)
    return format(rounded_qty, f".{precision}f")

def get_lot_size(symbol):
    url = f"https://api.binance.com/api/v3/exchangeInfo"
    data = requests.get(url).json()

    for s in data["symbols"]:
        if s["symbol"] == symbol.upper():
            for f in s["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    return {
                        "minQty": float(f["minQty"]),
                        "stepSize": float(f["stepSize"]),
                        "maxQty": float(f["maxQty"]),
                    }
    return None

def execute_market_trade(api_key, api_secret, symbol, side, quantity):
    """
    Executes a market buy or sell order.
    - symbol: e.g., 'BTCUSDT'
    - side: 'BUY' or 'SELL'
    - quantity: in base asset (for SELL) or quote asset (for BUY)
    """
    quantity = format(float(quantity), '.8f')
    quantity = round_step_size(quantity, get_lot_size(symbol)['stepSize'])
    client = Client(api_key, api_secret)
    try:
        if side == 'BUY':
            order = client.order_market_buy(
                symbol=symbol,
                quoteOrderQty=quantity  # Use quoteOrderQty for BUY (USDT side)
            )
        else:
            order = client.order_market_sell(
                symbol=symbol,
                quantity=quantity  # Use base quantity for SELL
            )
        print(f"✅ Executed MARKET {side} order on {symbol}: {quantity} -> {sum(float(f['qty']) for f in order['fills']) if side == "BUY" else order['cummulativeQuoteQty']}")
        
        # print(order)
        return order
    except Exception as e:
        print(f"❌ Error executing {side} for {quantity} on {symbol}: {e}")
        return None
    
def get_qty_and_fees(result, to_sym, side):
    if 'fills' in result:
        
        fills = result['fills']
        
        if side == "BUY":
            current_qty = sum(float(f['qty']) for f in fills)
        else:
            current_qty = float(fills['cummulativeQuoteQty'])

        fees = 0
        if to_sym != "BNB":
            fees = sum(float(f['commission']) for f in fills if f['commissionAsset'] != "BNB")
        else:
            fees = sum(float(f['commission']) for f in fills if f['commissionAsset'] == "BNB")
        current_qty -= fees

    else:
        current_qty = float(result['qty']) if side == 'BUY' else float(result['quoteQty'])
        if (to_sym == "BNB" and result['commissionAsset'] == "BNB") or to_sym != "BNB" and result['commissionAsset'] != "BNB":
            current_qty -= float(result['commission'])   
    
    # print(current_qty)
    return current_qty

def execute_triangle(api_key, api_secret, triangle, usdt_amount, use_limit, max_deviation, price):
    """
    Execute a triangle arbitrage using a starting USDT balance.
    Expects triangle of [(from, to, symbol, direction), ...]
    """
    current_asset = 'USDT'
    current_qty = usdt_amount
    trades = []

    for from_sym, to_sym, symbol, direction in triangle:

        if direction != 'base-quote':
            # USDT → Token → token → USDT
            if current_asset == from_sym:
                side = 'BUY'

                if use_limit and len(trades) == 1:

                    notional = price * current_qty
                    if notional > get_min_notional_filter(symbol, Client(api_key, api_secret)):
                        result = place_limit_order_and_wait(api_key, api_secret, symbol, side, current_qty, price, max_deviation)
                    else:
                        print("🚨 Moving to market order due to minNotional")
                        result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)

                else:
                    result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                
                if result:

                    current_qty = get_qty_and_fees(result, to_sym, side)                                     

                    current_asset = to_sym
                    trades.append(result)
            else:
                side = 'SELL'
                
                if use_limit and len(trades) == 1:
                    notional = price * current_qty
                    if notional > get_min_notional_filter(symbol, Client(api_key, api_secret)):
                        result = place_limit_order_and_wait(api_key, api_secret, symbol, side, current_qty, price, max_deviation)
                    else:
                        print("🚨 Moving to market order due to minNotional")
                        result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                else:
                    result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)                
                
                if result:
                    current_qty = get_qty_and_fees(result, to_sym, side)
                    
                    current_asset = to_sym
                    trades.append(result)

        else:
            # Reverse direction (quote-base)
            if current_asset == from_sym:
                side = 'SELL'
                
                if use_limit and len(trades) == 1:

                    notional = price * current_qty
                    if notional > get_min_notional_filter(symbol, Client(api_key, api_secret)):
                        result = place_limit_order_and_wait(api_key, api_secret, symbol, side, current_qty, price, max_deviation)
                    else:
                        print("🚨 Moving to market order due to minNotional")
                        result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                else:
                    result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                
                if result:
                    current_qty = get_qty_and_fees(result, to_sym, side)

                    current_asset = to_sym
                    trades.append(result)

            else:
                side = 'BUY'
                
                if use_limit and len(trades) == 1:
                    
                    notional = price * current_qty
                    if notional > get_min_notional_filter(symbol, Client(api_key, api_secret)):
                        result = place_limit_order_and_wait(api_key, api_secret, symbol, side, current_qty, price, max_deviation)
                    else:
                        print("🚨 Moving to market order due to minNotional")
                        result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                else:
                    result = execute_market_trade(api_key, api_secret, symbol, side, current_qty)
                
                if result:

                    current_qty = get_qty_and_fees(result, to_sym, side)

                    current_asset = to_sym
                    trades.append(result)


        if not result:
            print("⚠️ Stopping due to failed trade.")
            break

    if current_asset != "USDT":
        print(f"🔁 Converting remaining {current_asset} back to USDT...")
        client = Client(api_key, api_secret)
        balance = float(client.get_asset_balance(asset=current_asset)['free'])

        symbol = f"{current_asset}USDT"
        try:
            # Try common quote direction first
            result = execute_market_trade(api_key, api_secret, symbol, 'SELL', balance)
        except:
            # If it fails, maybe it's the reverse pair (e.g., USDTXXX)
            symbol = f"USDT{current_asset}"
            result = execute_market_trade(api_key, api_secret, symbol, 'BUY', balance)

        if result:
            print(f"✅ Successfully converted back to USDT via {symbol}")
            current_asset = "USDT"
            fills = result['fills']
            current_qty = float(result['cummulativeQuoteQty'])#sum(float(f['qty']) for f in fills) - sum(float(f['commission']) for f in fills if f['commissionAsset'] != "BNB")
            trades.append(result)
        
        else:
            print(f"❌ Failed to convert {current_asset} back to USDT.")


    
    with open("logs.txt", "a") as f:
        for line in trades:
            f.write("\n" + str(line))

    print(f"✅ Final asset: {current_asset} | Final amount: {current_qty:.6f}") # NO CONSIDERA SI LOS FEES SE USARON EN BNB

def get_min_notional_filter(symbol, client):
    exchange_info = client.get_symbol_info(symbol)
    for f in exchange_info['filters']:
        if f['filterType'] == 'NOTIONAL':
            return float(f['minNotional'])
    return None

def place_limit_order_and_wait(api_key, api_secret, symbol, side, quantity, price, max_deviation):
    client = Client(api_key, api_secret)
    quantity = format(float(quantity), '.8f')
    quantity = round_step_size(quantity, get_lot_size(symbol)['stepSize'])
    

    try:
        # print(price, quantity)
        order = client.create_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            quantity=quantity,
            price=price,
            timeInForce='GTC'
        )
        order_id = order['orderId']
        print(f"🚚 Sent {side} order on {symbol}: {quantity}")

        while True:
            print("⚙️ Checking order status...")
            order_status = client.get_order(symbol=symbol, orderId=order_id)
            if order_status['status'] == 'FILLED':
                trade = client.get_my_trades(symbol=symbol, orderId = order_id)[0]
                # print(trade)
                print(f"✅ Executed LIMIT {side} order on {symbol}: {quantity} -> {trade['qty'] if side == "BUY" else trade['quoteQty']}")
                return trade # return order CREO

            # Check deviation
            book = client.get_order_book(symbol=symbol, limit=5)
            best_bid = float(book['bids'][0][0])
            best_ask = float(book['asks'][0][0])
            market_price = best_bid if side == 'SELL' else best_ask

            deviation = abs((market_price - price) / price) * 100
            if deviation > max_deviation:
                print(f"⚠️ Deviation {deviation:.2f}% > max {max_deviation}%. Cancelling order.")

                client.cancel_order(symbol=symbol, orderId=order_id)
                return None

            time.sleep(1)

    except Exception as e:
        print(f"❌ Limit order error: {e} - {symbol} {side} {quantity}")
        return None


# ===== GUI Functions =====
def start_bot():
    api_key = api_key_entry.get()
    api_secret = api_secret_entry.get()

    test_client = Client(api_key=api_key, api_secret=api_secret)
    try:
        test_client.get_account()
        print("✅ Binance client verified\n")

        usdt_amount = float(amount_entry.get())
        threshold = float(threshold_entry.get())

        use_limit = limit_var.get()
        max_deviation = float(deviation_entry.get())

        create_logs_file(api_key, api_secret)

        global bot
        bot = TradingBot(api_key, api_secret, usdt_amount, threshold, use_limit, max_deviation)
        bot.use_limit = use_limit
        bot.max_deviation = max_deviation
        bot.start()

    except Exception as e:
        print(e)


    

def stop_bot():
    if bot:
        bot.stop()

# ===== Build Tkinter Window =====
root = tk.Tk()
root.title("Binance Triangular Arbitrage Bot")

tk.Label(root, text="API Key:").grid(row=0, column=0, sticky="w")
api_key_entry = tk.Entry(root, width=50)
api_key_entry.grid(row=0, column=1)

tk.Label(root, text="API Secret:").grid(row=1, column=0, sticky="w")
api_secret_entry = tk.Entry(root, width=50, show="*")
api_secret_entry.grid(row=1, column=1)

if os.path.exists("logs.txt"):
    with open("logs.txt") as f:
        key = f.readline().strip()
        secret = f.readline().strip()

    api_key_entry.insert(0, key)
    api_secret_entry.insert(0, secret)

tk.Label(root, text="USDT Amount:").grid(row=2, column=0, sticky="w")
amount_entry = tk.Entry(root, width=20)
amount_entry.grid(row=2, column=1, sticky="w")
amount_entry.insert(0, "40")

tk.Label(root, text="Profit Threshold:").grid(row=3, column=0, sticky="w")
threshold_entry = tk.Entry(root, width=20)
threshold_entry.grid(row=3, column=1, sticky="w")
threshold_entry.insert(0, "0.5")

limit_var = tk.BooleanVar()
tk.Checkbutton(root, text="Limit Order", variable=limit_var).grid(row=4, column=0, sticky="w")

tk.Label(root, text="Max Deviation %:").grid(row=5, column=0, sticky="w")
deviation_entry = tk.Entry(root, width=10)
deviation_entry.grid(row=5, column=1, sticky="w")
deviation_entry.insert(0, "1.0")


start_btn = tk.Button(root, text="Start Bot", command=start_bot)
start_btn.grid(row=6, column=0, pady=10)

stop_btn = tk.Button(root, text="Stop Bot", command=stop_bot)
stop_btn.grid(row=6, column=1, pady=10, sticky="w")

log_box = scrolledtext.ScrolledText(root, width=80, height=20, state='disabled')
log_box.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

# Redirect print() to Tkinter log box
sys.stdout = TextRedirector(log_box, root)
sys.stderr = TextRedirector(log_box, root)

root.mainloop()
