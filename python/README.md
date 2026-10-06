# DNSE OpenAPI Python SDK

Official Python SDK for integrating applications with **DNSE OpenAPI**.

The SDK provides a convenient Python interface for accessing DNSE trading, account, broker, and market data services, including REST APIs, real-time market data, and real-time trading events.

---

## Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Requirements](#requirements)
* [Installation](#installation)
* [Configuration](#configuration)

  * [Environments](#environments)
  * [Initialize the Client](#initialize-the-client)
  * [Configuration Parameters](#configuration-parameters)
  * [Environment Variables](#environment-variables)
* [Authentication](#authentication)
* [Basic Usage](#basic-usage)
* [Dry Run](#dry-run)
* [Trading API](#trading-api)
* [Broker API](#broker-api)
* [Market Data API](#market-data-api)
* [WebSocket Market Data](#websocket-market-data)
* [WebSocket Trading Events](#websocket-trading-events)
* [Examples](#examples)
* [Response and Error Handling](#response-and-error-handling)
* [Security Best Practices](#security-best-practices)
* [Support](#support)

---

# Overview

**DNSE OpenAPI** is an API-first trading platform that enables applications to integrate brokerage, trading, account, and market data services.

The **DNSE OpenAPI Python SDK** provides a Python client for interacting with DNSE OpenAPI.

The SDK handles common API communication requirements, including:

* Request authentication
* Request signing
* API version configuration
* HTTP communication
* Trading API requests
* Market data requests
* Real-time market data subscriptions
* Real-time trading event subscriptions

This allows developers to focus on building trading systems, investment applications, automation strategies, and market data applications.

---

# Features

| Module                       | Capabilities                                                                                                                                                    |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trading API**              | Account information, balances, loan packages, buying/selling power, orders, executions, positions, PnL configuration, close position, and reverse position      |
| **Broker API**               | Broker-specific account and care-by information                                                                                                                 |
| **Authentication**           | API Key, API Secret, request signing, Email OTP, Smart OTP, and Trading Token                                                                                   |
| **Market Data API**          | Security definitions, instruments, trades, quotes, OHLC, expected prices, foreign trading, market indices, volume profiles, trading sessions, and working dates |
| **WebSocket Market Data**    | Security definitions, quotes, trades, OHLC, expected prices, foreign investor data, market indices, sessions, and related market events                         |
| **WebSocket Trading Events** | Order and position events, including broker order and broker position events                                                                                    |
| **Dry Run**                  | Preview API requests without sending network requests                                                                                                           |

---

# Requirements

* Python **3.8+**
* A valid DNSE OpenAPI **API Key** and **API Secret**

API credentials are provided when you register for the corresponding DNSE OpenAPI environment.

---

# Installation

Install the SDK from PyPI:

```console
pip3 install dnse-sdk-openapi
```

To upgrade to the latest version:

```console
pip3 install --upgrade dnse-sdk-openapi
```

Verify the installation:

```python
from dnse import DNSEClient
```

If no import error is returned, the SDK has been installed successfully.

---

# Configuration

## Environments

DNSE OpenAPI provides separate **Production** and **Sandbox** environments.

|                 | Production                      | Sandbox                           |
| --------------- | ------------------------------- | --------------------------------- |
| **REST API**    | `https://openapi.dnse.com.vn`   | `https://sb-openapi.dnse.com.vn`  |
| **WebSocket**   | `wss://ws-openapi.dnse.com.vn`  | `wss://ws-sb-openapi.dnse.com.vn` |
| **API Version** | `2026-07-23`                    | `2026-07-23`                      |
| **Credentials** | Production API Key & API Secret | Sandbox API Key & API Secret      |

> **Important:** Production and Sandbox use **different API credentials**. Use the API Key and API Secret provided for the corresponding environment.

Do not use Production credentials with Sandbox endpoints or Sandbox credentials with Production endpoints.

---

## Initialize the Client

### Production

```python
from dnse import DNSEClient

client = DNSEClient(
    api_key="your_production_api_key",
    api_secret="your_production_api_secret",
    base_url="https://openapi.dnse.com.vn",
    api_version="2026-07-23",
)
```

### Sandbox

```python
from dnse import DNSEClient

client = DNSEClient(
    api_key="your_sandbox_api_key",
    api_secret="your_sandbox_api_secret",
    base_url="https://sb-openapi.dnse.com.vn",
    api_version="2026-07-23",
)
```

---

## Configuration Parameters

| Parameter     | Required | Description                                                                          |
| ------------- | -------- | ------------------------------------------------------------------------------------ |
| `api_key`     | Yes      | API Key for the selected environment. Production and Sandbox use different API Keys. |
| `api_secret`  | Yes      | API Secret corresponding to the API Key and selected environment.                    |
| `base_url`    | Yes      | REST API endpoint of the selected DNSE environment.                                  |
| `api_version` | No       | API version sent in the `version` request header.                                    |

### API Credentials

Your API Key and API Secret are provided when you register for DNSE OpenAPI.

Make sure to use the credentials corresponding to the environment you are connecting to.

| Environment | API Key            | API Secret            |
| ----------- | ------------------ | --------------------- |
| Production  | Production API Key | Production API Secret |
| Sandbox     | Sandbox API Key    | Sandbox API Secret    |

> **Security:** Never expose your API Secret in public repositories, frontend applications, logs, or other publicly accessible locations.

---

## Environment Variables

For production applications, avoid hard-coding credentials in source code.

```console
export DNSE_API_KEY="your_api_key"
export DNSE_API_SECRET="your_api_secret"
export DNSE_API_VERSION="2026-07-23"
```

The API Key and API Secret should correspond to the environment configured in `base_url`.

---

# Authentication

The SDK handles the authentication and request signing required when communicating with DNSE OpenAPI.

Developers provide the API credentials when creating the client:

```python
client = DNSEClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    base_url="https://openapi.dnse.com.vn",
    api_version="2026-07-23",
)
```

The SDK automatically handles the authentication-related request details.

## Trading Authentication

Trading operations that require a **Trading Token** can use the following examples:

| Example                       | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| `send_email_otp.py`           | Request an OTP to be sent to the registered email address |
| `create_smart_otp_handoff.py` | Create a Smart OTP handoff                                |
| `create_trading_token.py`     | Generate a Trading Token required for trading operations  |

---

# Basic Usage

Once the client has been initialized, API methods can be called directly.

For example, retrieve the trading accounts associated with the API Key:

```python
from dnse import DNSEClient

client = DNSEClient(
    api_key="your_api_key",
    api_secret="your_api_secret",
    base_url="https://openapi.dnse.com.vn",
    api_version="2026-07-23",
)

status, body = client.get_accounts()

print(status)
print(body)
```

The SDK returns:

```text
status
body
```

where:

* `status` contains the HTTP response status.
* `body` contains the API response payload.

---

# Dry Run

The SDK supports **Dry Run** mode for previewing requests without sending them to DNSE servers.

Set:

```python
dry_run=True
```

Example:

```python
status, body = client.get_accounts(dry_run=True)

print(status)
print(body)
```

When Dry Run is enabled:

* The request is prepared by the SDK.
* No network request is sent.
* No request reaches DNSE servers.
* Developers can inspect or validate request construction during development.

---

# Trading API

The Trading API provides access to account information, order management, positions, executions, and trading configuration.

## Account & Portfolio

| Example                 | Description                                                 |
| ----------------------- | ----------------------------------------------------------- |
| `get_accounts.py`       | Retrieve all trading sub-accounts managed under the API Key |
| `get_balances.py`       | Retrieve asset balances of a trading sub-account            |
| `get_loan_packages.py`  | Retrieve available loan package codes                       |
| `get_loans.py`          | Retrieve loan information                                   |
| `get_ppse.py`           | Retrieve buying power and selling power                     |
| `get_positions.py`      | Retrieve current holding positions                          |
| `get_position_by_id.py` | Retrieve detailed information of a specific position        |

## Order Management

| Example                           | Description                                       |
| --------------------------------- | ------------------------------------------------- |
| `get_orders.py`                   | Retrieve the intraday order book                  |
| `get_order_detail.py`             | Retrieve detailed information of a specific order |
| `get_order_history.py`            | Retrieve historical orders                        |
| `get_execution_detail.py`         | Retrieve execution information of an order        |
| `get_corporate_action_history.py` | Retrieve corporate action history                 |
| `post_order.py`                   | Submit a new trading order                        |
| `put_order.py`                    | Modify an existing order                          |
| `cancel_order.py`                 | Cancel an existing order                          |

## Position Management

| Example                 | Description                                 |
| ----------------------- | ------------------------------------------- |
| `get_positions.py`      | Retrieve current holding positions          |
| `get_position_by_id.py` | Retrieve detailed information of a position |
| `close_position.py`     | Close an existing position                  |
| `reverse_position.py`   | Reverse an existing derivative position     |

## PnL Configuration

| Example                        | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| `get_position_pnl_configs.py`  | Retrieve PnL configuration of a derivative position         |
| `get_account_pnl_configs.py`   | Retrieve PnL configuration of a derivative sub-account      |
| `post_position_pnl_configs.py` | Create or update PnL configuration of a derivative position |
| `patch_account_pnl_configs.py` | Update PnL configuration of a derivative sub-account        |

## Trading Authentication

| Example                       | Description                                              |
| ----------------------------- | -------------------------------------------------------- |
| `send_email_otp.py`           | Request an OTP sent to the registered email address      |
| `create_smart_otp_handoff.py` | Create a Smart OTP handoff                               |
| `create_trading_token.py`     | Generate a Trading Token required for trading operations |

---

# Broker API

The Broker API provides broker-specific functionality available through the SDK.

| Example               | Description                              |
| --------------------- | ---------------------------------------- |
| `get_list_care_by.py` | Retrieve the list of care-by information |

---

# Market Data API

The Market Data API provides access to reference and historical market data.

| Example                        | Description                                               |
| ------------------------------ | --------------------------------------------------------- |
| `get_security_definition.py`   | Retrieve security definition and instrument details       |
| `get_instruments.py`           | Retrieve available trading instruments and their metadata |
| `get_trades.py`                | Retrieve trade data for a specific instrument             |
| `get_latest_trade.py`          | Retrieve the latest trade for a specific instrument       |
| `get_trades_volume_profile.py` | Retrieve trade volume profile                             |
| `get_quotes.py`                | Retrieve quote data                                       |
| `get_latest_quote.py`          | Retrieve the latest quote                                 |
| `get_ohlc.py`                  | Retrieve OHLC data for a specified time range             |
| `get_expected_price.py`        | Retrieve expected price data                              |
| `get_foreign_trading.py`       | Retrieve foreign investor trading data                    |
| `get_market_index.py`          | Retrieve market index data                                |
| `get_latest_session.py`        | Retrieve the latest trading session                       |
| `get_close_price.py`           | Retrieve the latest closing price                         |
| `get_working_dates.py`         | Retrieve trading working dates                            |

### Example

Retrieve the latest trade data:

```python
status, body = client.get_latest_trade(
    symbol="VNM"
)
print(status, body)
```

For complete request parameters, supported values, and response schemas, refer to the DNSE OpenAPI API Reference.

---

# WebSocket Market Data

The SDK provides WebSocket support for subscribing to real-time market data.

WebSocket is suitable for applications that require continuously updated market information instead of periodically polling REST APIs.

| Example                     | Description                                                   |
| --------------------------- | ------------------------------------------------------------- |
| `sec_def.py`                | Subscribe to real-time security definition updates            |
| `quote.py`                  | Subscribe to real-time quote updates                          |
| `trade.py`                  | Subscribe to real-time trade updates                          |
| `trade_extra.py`            | Subscribe to real-time trade data with additional information |
| `ohlc.py`                   | Subscribe to real-time OHLC updates                           |
| `ohlc_closed.py`            | Subscribe to completed OHLC candle updates                    |
| `expected_price.py`         | Subscribe to real-time expected price updates                 |
| `foreign_investor.py`       | Subscribe to foreign investor trading updates                 |
| `market_index.py`           | Subscribe to real-time market index updates                   |
| `estimated_market_index.py` | Subscribe to estimated market index updates                   |
| `market_index_influence.py` | Subscribe to market index influence updates                   |
| `session.py`                | Subscribe to trading session updates                          |

---

# WebSocket Trading Events

The SDK supports real-time trading event notifications through WebSocket.

| Example              | Description                         |
| -------------------- | ----------------------------------- |
| `order.py`           | Subscribe to order events           |
| `position.py`        | Subscribe to position events        |
| `broker_order.py`    | Subscribe to broker order events    |
| `broker_position.py` | Subscribe to broker position events |

Order and position events can be used to monitor trading activity in real time.

---

# Examples

The `examples/` directory contains scripts organized into two groups:

- `reference/` — authentication flows: obtaining a trading token via Email OTP, SmartOTP manual entry, or SmartOTP programmatic handoff.
- `use-cases/` — end-to-end trading flows: portfolio check, market data, order history, place a trade, and a full signal-driven auto-trader with TP/SL management.

For individual API operations, refer to the `trading-api/`, `broker-api/`, `marketdata-api/`, `websocket-marketdata/`, and `websocket-trading/` directories at the root of the SDK.

For setup instructions, environment variables, and a full file guide, see examples/README.md.

All scripts are configured via environment variables. Copy `.env.example` to `.env` and fill in your credentials before running.

---

## Trading Token — Authentication Flows

Every order mutation (place, modify, cancel) requires a **trading token** — a short-lived credential valid for 8 hours. The scripts in `examples/reference/` each cover one way to obtain a token, then run a full order lifecycle (place → modify → cancel) to confirm everything works end-to-end.

Choose the flow that matches your integration type:

| Script | OTP source | Best for |
|---|---|---|
| `orders-email-otp.py` | Email inbox | Integrations where the end user has access to their registered email |
| `orders-smart-otp.py` | DNSE mobile app (manual entry) | Integrations where the end user manually copies the OTP from the app |
| `smart-otp-handoff-flow.py` | DNSE mobile app (in-app confirmation) | Integrations that trigger the OTP request programmatically and let the user approve via an app popup |

### Email OTP

Calls `send_email_otp()` to trigger a passcode to your registered email, then prompts you to enter it. After you submit it, the script exchanges it for a trading token via `create_trading_token(otp_type="email_otp")` and runs the order lifecycle against `HPG` as a test symbol.

The `otp_email.py` helper can auto-fetch the OTP from a configured mailbox if you want to remove the manual input step in test environments.

```
python examples/reference/orders-email-otp.py
```

### Smart OTP — Manual Entry

For accounts with SmartOTP enabled. Generate the OTP in the DNSE mobile app, enter it when prompted, and the script calls `create_trading_token(otp_type="smart_otp")`. No email step needed. The order lifecycle that follows is identical to the Email OTP example.

```
python examples/reference/orders-smart-otp.py
```

### Smart OTP — Programmatic Handoff

Calls `create_smart_otp_handoff()` to trigger an OTP request from the server side. DNSE then pushes a confirmation popup to the user's DNSE mobile app — the user approves it there, and the API returns the SmartOTP in the same response. The script immediately passes that value to `create_trading_token()` to obtain a trading token.

This is the recommended flow for integrations that want to keep the user in-app rather than switching to email, while still driving the OTP request programmatically from your backend.

```
python examples/reference/smart-otp-handoff-flow.py
```

---

## Use Cases

The scripts in `examples/use-cases/` combine token management, REST calls, and WebSocket events into complete trading flows. Each is a working starting point you can adapt to your own integration.

### Place a Trade

Covers the core integration pattern: place an order and confirm it via real-time events.

**Flow:**
1. Fetch the current price band for the target symbol via `get_security_definition()`.
2. Retrieve a valid `loanPackageId` via `get_loan_packages()` — required for all order placements, both stock and derivative.
3. Obtain a trading token (cached if still valid, otherwise triggers OTP).
4. Subscribe to order and position events over WebSocket — *before* placing the order to avoid missing the confirmation event.
5. Place a limit buy order via `post_order()`.
6. Wait for either an order event with a live status (`PENDINGNEW`, `NEW`, `ACTIVE`, ...) or a position event for the symbol (indicates a fill). Timeout defaults to 15 seconds.
7. Cancel the order at the end of the demo.

Step 4 is the key detail: subscribing before placing ensures the WebSocket is ready to receive the exchange acknowledgment, which arrives asynchronously and can precede the REST response in some cases.

```
python examples/use-cases/place-a-trade.py
```

### Auto-Trader: Signal-Driven Position Management

Demonstrates a complete signal-to-exit lifecycle: receive a trading signal, size the position, place the entry order, monitor it via WebSocket events, then exit automatically when price hits the take-profit or stop-loss level.

This use case is built from three cooperating modules:

**`position_manager.py`** is the execution layer. `PositionManager` exposes two entry points depending on whether a position is being opened or resumed:

- `run(signal)` — takes a `Signal` (side, entry price, stop-loss, take-profit), places the entry order, and waits up to `entry_fill_timeout` seconds for a fill confirmation via the order event stream. Once filled, it hands off to the exit monitor.
- `resume(saved)` — re-attaches to an existing open position loaded from disk, skipping the entry step and going directly to TP/SL monitoring. Used on application restart.

Exit logic runs on every price tick delivered via `feed_price()`, called by the application's live OHLC WebSocket stream. When price crosses the take-profit or stop-loss level, a closing order is placed immediately for the full filled quantity. An optional `manage_timeout` parameter forces a close after a fixed number of seconds regardless of price — useful for end-of-session risk control.

Position sizing is handled by `size_by_risk(entry, stop_loss, risk_points)`, which calculates quantity such that a full stop-out loses approximately `risk_points` in total value, keeping risk consistent across trades with varying volatility.

**`position_store.py`** handles crash recovery. When an entry fills, the full position state (symbol, side, quantity, average price, stop-loss, take-profit, entry order ID) is written to a local file. On the next startup, the application detects this file and calls `resume()` instead of opening a new trade. The file is deleted when the position closes.

**`strategy_base.py`** defines the `Signal` dataclass and the base `Strategy` interface. The bundled strategy scripts (`strategy_ichimoku.py`, `strategy_price_action.py`, `strategy_scalping.py`) each implement a `Strategy` subclass that emits a `Signal` when entry conditions are met. Swap in any of these — or write your own — without changing the position management layer.

---

# Response and Error Handling

SDK API methods return the HTTP status and response body:

```python
status, body = client.get_accounts()

if status == 200:
    print(body)
else:
    print("Request failed:", status, body)
```

* `status` contains the HTTP response status.
* `body` contains the API response payload.

Applications should handle unsuccessful responses appropriately.

For production trading applications, consider implementing:

* HTTP status validation
* API error handling
* Request retry strategy where appropriate
* Logging
* Timeout handling
* Order status verification
* WebSocket reconnect handling

> **Important:** Do not automatically retry trading requests unless the operation is safe to retry. For order-related operations, verify the order status before retrying a failed request.

---

# Security Best Practices

## Keep Credentials Secure

Do not hard-code API credentials in source code that is committed to a public or shared repository.

Use environment variables or a secure secret-management solution instead.

## Do Not Expose API Credentials

Never expose the following in:

* Frontend applications
* Public Git repositories
* Client-side JavaScript
* Logs
* Screenshots
* Public documentation

```text
API Key
API Secret
Trading Token
OTP
```

## Use Appropriate API Permissions

Configure the API Key with only the permissions required by your application.

For example, an application that only consumes market data does not need trading permissions.

## Use the Correct Environment

Always make sure that the credentials and endpoints belong to the same environment.

| Environment | REST API                         | Credentials            |
| ----------- | -------------------------------- | ---------------------- |
| Production  | `https://openapi.dnse.com.vn`    | Production credentials |
| Sandbox     | `https://sb-openapi.dnse.com.vn` | Sandbox credentials    |

---

# Support

For detailed information about:

* Available endpoints
* Request parameters
* Authentication
* API permissions
* Response schemas
* WebSocket topics

refer to the **DNSE OpenAPI Documentation**.

Before using trading functionality in a production application, make sure that:

* The API Key has been registered successfully.
* Required API permissions have been enabled.
* The correct environment is configured.
* API credentials are stored securely.
* Trading authentication requirements have been completed.
* API errors are handled appropriately.
* WebSocket disconnections and reconnections are handled appropriately.