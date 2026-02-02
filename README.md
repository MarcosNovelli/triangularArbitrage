# Triangular Arbitrage Bot

A simple triangular arbitrage trading bot for Binance with a Tkinter GUI interface. This bot automatically scans for profitable triangular arbitrage opportunities and executes trades when profitable opportunities are found.

## ⚠️ **IMPORTANT DISCLAIMER**

**This software is provided for educational and learning purposes only. It is NOT financial advice, and should NOT be used for actual trading without thorough understanding of the risks involved.**

- **Trading cryptocurrencies involves substantial risk of loss**
- **Past performance does not guarantee future results**
- **You may lose all or more than your initial investment**
- **Use this software at your own risk**
- **The authors and contributors are not responsible for any financial losses**

This project is intended for:
- Learning about triangular arbitrage concepts
- Understanding cryptocurrency trading APIs
- Educational purposes in algorithmic trading

**DO NOT use real funds unless you fully understand the risks and have tested extensively with small amounts.**

## Features

- 🔍 Automatic scanning for USDT-based triangular arbitrage opportunities
- 🖥️ Simple Tkinter GUI for easy interaction
- ⚙️ Configurable profit threshold
- 📊 Real-time price monitoring
- 🔄 Support for both market and limit orders
- 📝 Automatic logging of all trades to `logs.txt`
- 🔐 Secure API key storage (stored locally in `logs.txt`)

## Requirements

- Python 3.7+
- `python-binance` library
- `tkinter` (usually included with Python)
- Binance API key and secret

## Usage

1. Run the application:
```bash
python app.py
```

2. Enter your Binance API credentials in the GUI:
   - API Key
   - API Secret

3. Configure trading parameters:
   - **USDT Amount**: Starting capital for each arbitrage cycle
   - **Profit Threshold**: Minimum profit percentage required (e.g., 0.5%)
   - **Limit Order**: Check to use limit orders for the second trade in the triangle
   - **Max Deviation %**: Maximum price deviation allowed for limit orders

4. Click "Start Bot" to begin scanning for opportunities

5. Monitor the log output for:
   - Triangle discovery
   - Profit calculations
   - Trade executions
   - Error messages

## How It Works

1. **Triangle Discovery**: The bot finds all possible USDT-based triangular arbitrage paths (e.g., USDT → BTC → ETH → USDT)

2. **Profit Calculation**: For each triangle, it calculates potential profit after accounting for trading fees (0.1% per trade)

3. **Opportunity Detection**: When a triangle shows profit above the threshold, it's flagged for execution

4. **Trade Execution**: The bot executes three sequential trades to complete the arbitrage cycle:
   - Trade 1: Market order
   - Trade 2: Market or limit order (configurable)
   - Trade 3: Market order

5. **Logging**: All trades are logged to `logs.txt` for review

## File Structure

- `app.py` - Main application with GUI and trading logic
- `logs.txt` - Stores API keys and trade logs (automatically created, **not tracked in git**)
- `.gitignore` - Excludes sensitive files from version control

## Important Notes

- The bot uses a 0.1% fee assumption per trade
- Real fees may vary based on your Binance account tier
- Network latency can affect arbitrage profitability
- Market conditions change rapidly - opportunities may disappear before execution
- Always test with small amounts first
- Monitor the bot while it's running
- Ensure you have sufficient balance for the configured USDT amount

## Security Considerations

- **Never commit `logs.txt` to version control** (already in `.gitignore`)
- Use API keys with minimal required permissions
- Enable IP whitelisting on your Binance API keys
- Consider using a separate test account
- Regularly rotate your API keys

## Limitations

- Only scans USDT-based triangles
- Fixed fee assumption (may not match actual fees)
- No risk management beyond profit threshold
- No position sizing optimization
- Limited error recovery
- Single-threaded execution

## Contributing

This is an educational project. Contributions, improvements, and suggestions are welcome, but please remember this is for learning purposes only.

## License

This project is provided as-is for educational purposes. Use at your own risk.

---

**Remember: This is NOT financial advice. Use for learning purposes only. Trade at your own risk.**