# Examples — end-to-end flows

Flow-oriented sample scripts that drive this SDK's **`DNSEClient`** (REST) and
**`TradingClient`** (WebSocket). Unlike the one-endpoint-per-file scripts under
`trading-api/`, `marketdata-api/`, etc., these show complete real-world flows —
up to a full auto-trader (stream prices → strategy → order → manage TP/SL).

All API work goes through the SDK clients; HMAC request signing lives inside the
SDK (`dnse/api/common.py` for REST, `dnse/websocket/auth.py` for WS) and is
applied automatically. Standard library only — **no extra dependencies**.

## Configure

Recommended: copy `.env.example` to `.env` (same folder) and fill it in.

```bash
cp examples/.env.example examples/.env      # then edit examples/.env
```

```ini
DNSE_API_KEY=your-api-key
DNSE_API_SECRET=your-api-secret
DNSE_ACCOUNT_NO=0001140055                  # a real sub-account (see note)
DNSE_API_VERSION=2026-07-23                 # version header for Orders APIs
DNSE_BASE_URL=https://openapi.dnse.com.vn   # or https://openapi-uat.dnse.com.vn
DNSE_WS_URL=wss://ws-openapi.dnse.com.vn     # or wss://ws-openapi-uat.dnse.com.vn
```

`.env` is **auto-loaded** by the OTP / token / auto-trader scripts (via
`otp_email.py`) regardless of how you launch them (terminal or IDE Run button) —
no `export` needed. Real environment variables still take precedence over `.env`.
It is gitignored, so it never gets committed.

> Sub-account: use `python use-cases/portfolio-check.py` to list the valid
> sub-accounts for your API key. Stock/derivative **orders** need the *deal*
> account (the one with `dealAccount=true`, which has a loan package).

## Auto-fetch OTP from email (optional)

The email-OTP flows can read the OTP straight from your inbox over IMAP instead
of prompting you to type it (handled by `otp_email.py`). Set these in `.env`;
leave them unset to fall back to a manual prompt.

```ini
OTP_EMAIL_USER=you@gmail.com
OTP_EMAIL_PASSWORD=your-app-password        # app password, NOT your login password
# Optional overrides (defaults shown):
OTP_IMAP_HOST=imap.gmail.com
OTP_IMAP_PORT=993
OTP_MAILBOX=INBOX
OTP_FROM=dnse                               # only match senders containing this
OTP_REGEX=\b(\d{6})\b                       # one capture group = the code
OTP_TIMEOUT=120                             # seconds to poll for the email
OTP_POLL_INTERVAL=3                         # seconds between polls
```

**Gmail:** enable IMAP, turn on 2-Step Verification, then create an **App
Password** (Google Account → Security → App passwords) and use that 16-char value
as `OTP_EMAIL_PASSWORD`. Outlook = `imap-mail.outlook.com`, Yahoo =
`imap.mail.yahoo.com` (both also need an app password).

> ⚠ Only ever use a revocable **app password**, never your main password.

## Trading token cache

The trading token (from the OTP flow) is valid ~8h. `token_store.py` caches it to
`.trading_token.json` (0600, gitignored) so you only do the OTP dance once per
window — subsequent runs reuse it. If the server rejects a cached token, it is
cleared automatically and the next run re-authenticates.

## Run

Read-only flows (no OTP, safe):

```bash
python examples/use-cases/portfolio-check.py    # accounts + balances
python examples/use-cases/market-data.py        # security price limits
python examples/use-cases/order-history.py       # order history + positions
```

Order flows (place real orders — prefer the UAT base URL):

```bash
python examples/use-cases/place-a-trade.py       # OTP → order → confirm via WS → cancel
python examples/reference/orders-email-otp.py    # full order lifecycle (email OTP)
python examples/reference/orders-smart-otp.py    # full order lifecycle (SmartOTP)
```

## Orders API version 2026-07-23

The order examples use `POST /accounts/{accountNo}/orders`; `accountNo` is
passed as `account_no` to `post_order()` and is no longer included in the JSON
body. Supported `market_type` / `order_category` combinations are:

| Market type | NORMAL | STOP | OCO |
|-------------|--------|------|-----|
| `STOCK` | Yes | Yes | No |
| `DERIVATIVE` | Yes | Yes | Yes |
| `BOND` | Yes | No | No |

`get_orders()` requires `page_index` and `page_size`, and its response includes
pagination metadata. Order IDs returned by the order APIs are strings; pass
them unchanged to `get_order_detail()`, `put_order()`, and `cancel_order()`.

Auto-trader (strategy → entry → manage TP/SL):

```bash
# DRY RUN (default): stream prices, print the strategy's trade plan, no order
python examples/use-cases/auto-trader.py

# LIVE: place the entry and manage the exit
PLACE_ORDER=1 STRATEGY=ichimoku_cloud RISK_POINTS=6 python examples/use-cases/auto-trader.py
```

## File guide

| File | Demonstrates | OTP? |
|------|--------------|------|
| `use-cases/portfolio-check.py` | `get_accounts` + `get_balances` | No |
| `use-cases/market-data.py` | `get_security_definition` price limits | No |
| `use-cases/order-history.py` | `get_order_history` + `get_positions` | No |
| `use-cases/place-a-trade.py` | OTP → `post_order` → confirm over WS → `cancel_order` (**real order**) | Yes |
| `use-cases/auto-trader.py` | **Full loop**: stream OHLC → strategy → entry → TP/SL exit, with risk sizing + restart-safe position | Yes (if `PLACE_ORDER=1`) |
| `reference/orders-email-otp.py` | Full order lifecycle, Email OTP | Yes |
| `reference/orders-smart-otp.py` | Full order lifecycle, SmartOTP | Yes |

## Auto-trader

`use-cases/auto-trader.py` wires the pieces together:

1. Subscribe to **closed OHLC bars** over WebSocket, keeping a rolling history.
2. Run a pluggable **Strategy** on each bar → a `Signal(side, entry, stop_loss, take_profit)`.
3. **Risk sizing** (`position_manager.size_by_risk`): quantity from a risk budget.
4. Place the **entry**, wait for the fill, then **exit when price hits TP or SL**
   (or a time limit) — `PositionManager`.
5. The open position is **persisted** to `.position.json`; if the app restarts it
   reloads and keeps managing that position instead of opening a new one
   (reconciled against the broker's open quantity first).

Both the **strategy** and the **risk/position manager** are separate modules, so
customers can swap either without touching the rest.

### Modules

| Module | Role |
|--------|------|
| `strategy_base.py` | `Candle`, `Signal`, `Strategy` interface + `@register`/`get_strategy` registry |
| `strategy_price_action.py` | `price_action` — range-breakout with structure stop + R:R target |
| `strategy_ichimoku.py` | `ichimoku_cloud` — Ichimoku (cloud/Tenkan-Kijun/Chikou) + RSI + ADX filter |
| `strategy_scalping.py` | `scalping` — EMA 8/21 + RSI 7 + MACD 8/17/9 momentum, ATR-based stops |
| `indicators.py` | Pure-Python `rsi`, `adx`, `ema`, `macd`, `atr`, `ichimoku` (26-period displacement) |
| `position_manager.py` | `size_by_risk` + `PositionManager` (fill → monitor TP/SL → close; persistence) |
| `position_store.py` | Persist / load / clear the open position (`.position.json`) |
| `token_store.py` | Cache the trading token (`.trading_token.json`, ~8h) |
| `otp_email.py` | Auto-fetch OTP over IMAP + load `.env` |
| `market_utils.py` | `to_order_price` (STOCK ×1000, DERIVATIVE unchanged) |

### Add your own strategy

Create `examples/strategy_myname.py`:

```python
from strategy_base import Candle, Signal, Strategy, register

@register
class MyStrategy(Strategy):
    name = "my_strategy"

    def analyze(self, candles: list[Candle]) -> Signal:
        # ... your logic over the candle history (oldest -> newest) ...
        return Signal(side="NB",          # "NB" long / "NS" short / None flat
                      entry=candles[-1].close,
                      stop_loss=...,
                      take_profit=...,
                      reason="...")
```

Import it in `auto-trader.py` (next to the other `import strategy_*`) and run with
`STRATEGY=my_strategy`. Nothing else changes.

> `side`: `NB` = buy/long, `NS` = sell/short. Short (`NS`) is only valid for
> `DERIVATIVE`; Vietnamese stocks cannot be shorted.

## Environment variables

| Variable | Used by | Default | Notes |
|----------|---------|---------|-------|
| `DNSE_API_KEY` / `DNSE_API_SECRET` | all | – | credentials (per environment: UAT vs prod) |
| `DNSE_ACCOUNT_NO` | order flows | `0001000115` | must be a valid deal sub-account |
| `DNSE_API_VERSION` | all REST flows | `2026-07-23` | sent in the `version` header |
| `DNSE_BASE_URL` | REST | `https://openapi.dnse.com.vn` | UAT: `https://openapi-uat.dnse.com.vn` |
| `DNSE_WS_URL` | WebSocket | `wss://ws-openapi.dnse.com.vn` | UAT: `wss://ws-openapi-uat.dnse.com.vn` |
| `OTP_EMAIL_USER` / `OTP_EMAIL_PASSWORD` | OTP flows | – | enable IMAP auto-fetch |
| `OTP_IMAP_HOST` / `OTP_IMAP_PORT` / `OTP_MAILBOX` / `OTP_FROM` / `OTP_REGEX` / `OTP_TIMEOUT` / `OTP_POLL_INTERVAL` | OTP flows | see above | IMAP tuning |
| `DNSE_TOKEN_CACHE` | token cache | `examples/.trading_token.json` | override path |
| `DNSE_POSITION_STORE` | auto-trader | `examples/.position.json` | override path |
| `CONFIRM_TIMEOUT` / `HOLD_SECONDS` | place-a-trade | `15` / `5` | wait-for-confirm / hold-before-cancel |
| `SYMBOL` | auto-trader | `41I1G7000` | trading symbol (orders + order/trade/position events) |
| `OHLC_SYMBOL` | auto-trader | `VN30F1M` | OHLC data symbol (generic front-month alias) |
| `MARKET_TYPE` | auto-trader / order flows | `DERIVATIVE` | `STOCK` or `DERIVATIVE` |
| `RESOLUTION` | auto-trader | `5` | OHLC bar minutes |
| `STRATEGY` | auto-trader | `price_action` | registered strategy name |
| `QUANTITY` | auto-trader | `1` | fixed size (fallback) |
| `RISK_POINTS` | auto-trader | `0` | >0 → size by risk budget / stop distance |
| `ENTRY_FILL_TIMEOUT` | auto-trader | `30` | cancel entry if unfilled (s) |
| `MANAGE_TIMEOUT` | auto-trader | `0` | 0 = wait until TP/SL; else time-based exit (s) |
| `PLACE_ORDER` | auto-trader | `0` | `1` = trade for real |
| `WS_ENCODING` | place-a-trade / auto-trader | `msgpack` | WebSocket stream encoding (`msgpack` or `json`) |

## Local (gitignored) files

`.env` (secrets), `.trading_token.json` (cached token), `.position.json` (open
position) are written under `examples/` and are all gitignored — never committed.

## Notes

- **UAT vs prod:** UAT has its own market data (prices differ from the real
  market) and its own credentials — a UAT key returns 401 on prod and vice-versa.
- **Price units:** STOCK prices from secdef/stream are in *thousands of VND*; the
  order API wants VND, so `to_order_price` multiplies STOCK by 1000. DERIVATIVE
  (index points) is sent unchanged.
- **WebSocket encoding:** the price/trading streams default to **msgpack** (binary,
  smaller/faster). Both the connection *and* every `subscribe_*` call use it. Set
  `WS_ENCODING=json` for human-readable frames when debugging.
- These are **demos**, not a production trading system: single position,
  whole-position exit, no partials/trailing, minimal reconciliation. Live orders
  are real money — test on UAT first.

## Mapping from the `dnse-py` resource API

The order flows were ported from `dnse-py`; they use `DNSEClient` methods directly:

| dnse-py (resource) | this SDK (`DNSEClient`) |
|--------------------|-------------------------|
| `registration.send_otp()` | `send_email_otp()` |
| `registration.verify_otp(otp, otp_type=...)` | `create_trading_token(otp_type=..., passcode=otp)` → `tradingToken` |
| `market.security_info(sym, board_id)` | `get_security_definition(sym, board_id="G1")` |
| `accounts.list()` / `accounts.balances()` | `get_accounts()` / `get_balances()` |
| `accounts.loan_packages(...)` | `get_loan_packages(...)` |
| `orders.list()` / `orders.history()` | `get_orders()` / `get_order_history()` |
| `orders.place(PlaceOrderRequest(...))` | `post_order(account_no, payload, trading_token=...)` |
| `orders.get()` / `orders.update()` / `orders.cancel()` | `get_order_detail()` / `put_order()` / `cancel_order()` |
| `deals.list()` | `get_positions()` |
