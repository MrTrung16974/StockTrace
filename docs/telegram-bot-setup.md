# Telegram Bot Setup and Connection Guide

## Goal

Telegram is the primary control plane for StockTrace. Users will manage watchlists, request prices, read news, check system status, and receive alerts directly from Telegram.

Planned commands:

```text
/add SYMBOL      add a stock to the watchlist
/remove SYMBOL   remove a stock from the watchlist
/list            show current watchlist
/price SYMBOL    get latest quote
/news SYMBOL     get latest related news
/status          show system and provider health
```

## Telegram Integration Architecture

```text
Telegram User
      |
      v
Telegram Bot API
      |
      v
Telegram Adapter
      |
      +--> Authorization Middleware
      +--> Command Dispatcher
      +--> Command Handlers
      |
      v
Application Services
      |
      v
Domain Layer
      |
      v
Repositories / Providers / Cache
      |
      v
MessageBuilder
      |
      v
TelegramNotifier
      |
      v
Telegram User
```

The Telegram adapter belongs to infrastructure because it depends on the Telegram SDK and external network calls. It must not contain business rules. Business rules remain in domain/application services.

## Step 1: Create the Bot with BotFather

1. Open Telegram.
2. Search for `@BotFather`.
3. Start a conversation with BotFather.
4. Send:

```text
/newbot
```

5. Enter a human-readable bot name, for example:

```text
StockTrace Monitor
```

6. Enter a unique username ending in `bot`, for example:

```text
stocktrace_monitor_bot
```

7. BotFather returns a bot token. The token looks like:

```text
1234567890:AA...secret...
```

Store this token as a secret. Do not commit it to Git.

## Step 2: Configure Local Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Set these values:

```text
STOCKTRACE_TELEGRAM__BOT_TOKEN=1234567890:AA...secret...
STOCKTRACE_TELEGRAM__CHAT_ID=your-chat-id
STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS=[123456789]
```

Meaning:

- `BOT_TOKEN`: secret token used by the app to call Telegram Bot API.
- `CHAT_ID`: default destination for system alerts.
- `ALLOWED_USER_IDS`: whitelist of Telegram user ids allowed to control the bot.

## Step 3: Find Your Telegram User ID and Chat ID

For a private chat:

1. Send any message to your newly created bot, for example:

```text
/start
```

2. Call Telegram `getUpdates`:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

3. Find these fields in the response:

```json
{
  "message": {
    "from": {
      "id": 123456789
    },
    "chat": {
      "id": 123456789
    }
  }
}
```

Use:

```text
STOCKTRACE_TELEGRAM__CHAT_ID=123456789
STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS=[123456789]
```

For a Telegram group, add the bot to the group, send a message, then call `getUpdates`. Group chat ids are often negative numbers.

## Step 4: Choose Polling or Webhook

StockTrace should support both modes.

### Polling

```text
StockTrace process
      |
      v
Repeatedly calls Telegram getUpdates
      |
      v
Receives commands
```

Best for:

- Local development.
- VPS without public HTTPS endpoint.
- Simple private bot.

Tradeoffs:

- Easy to operate.
- One active poller should run at a time.
- Not ideal for many replicas unless only one bot worker is elected leader.

### Webhook

```text
Telegram Bot API
      |
      v
Public HTTPS endpoint
      |
      v
FastAPI webhook router
      |
      v
Telegram command dispatcher
```

Best for:

- Production with a public domain and TLS.
- Lower latency.
- Better fit for horizontally scaled API when requests are routed safely.

Tradeoffs:

- Requires public HTTPS.
- Requires webhook secret validation.
- Needs reverse proxy or ingress configuration.

Recommended path:

```text
development: polling
single VPS: polling or webhook
scaled production: webhook with secret validation
```

## Step 5: Runtime Connection Flow

```text
Application startup
      |
      v
Load Settings from env and .env
      |
      v
Validate Telegram token and whitelist
      |
      v
Create Telegram Bot client
      |
      v
Register command handlers
      |
      v
Start polling or expose webhook
      |
      v
Receive command
      |
      v
Authorize Telegram user id
      |
      v
Execute application service
      |
      v
Build Telegram message
      |
      v
Send response
```

## Step 5.1: Connect the Current StockTrace Build

The current implementation starts Telegram polling together with the FastAPI application when
`STOCKTRACE_TELEGRAM__BOT_TOKEN` is configured.

Set `.env`:

```text
STOCKTRACE_TELEGRAM__BOT_TOKEN=your-botfather-token
STOCKTRACE_TELEGRAM__CHAT_ID=your-chat-id
STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS=[your-telegram-user-id]
STOCKTRACE_TELEGRAM__POLLING_ENABLED=true
STOCKTRACE_TELEGRAM__DROP_PENDING_UPDATES=true
```

Rebuild and run:

```bash
docker compose up -d --build
docker compose logs -f api
```

Then open your bot in Telegram and send:

```text
/start
/status
/help
/price FPT
/news FPT
```

The connected commands are:

- `/start`
- `/help`
- `/status`
- `/add SYMBOL`
- `/remove SYMBOL`
- `/list`
- `/price SYMBOL`
- `/news SYMBOL`

Alert delivery remains an extension point for the next implementation phases.

## Step 6: Security Boundaries

Telegram input is not trusted until it passes whitelist verification.

```text
Telegram Update
      |
      v
Parse safely
      |
      v
Check from_user.id in allowed_user_ids
      |
      +--> not allowed: reject silently or send minimal denial
      |
      v
Validate command arguments
      |
      v
Application service
```

Security rules:

- Never log full bot token.
- Never commit `.env`.
- Use `SecretStr` for token values.
- Keep `ALLOWED_USER_IDS` required in production.
- Use webhook secret token when webhook mode is enabled.
- Rate-limit command handlers to prevent accidental spam.
- Validate symbol input before calling providers.

## Step 7: Message Design

Telegram messages should be concise and operational.

Example `/price FPT` response:

```text
FPT
Price: 123,400 VND
Change: +1.20%
Volume: 2,450,000
Source: VNStock
Updated: 2026-05-28 09:35 ICT
```

Example alert:

```text
ALERT: FPT price increased 5.2%
Current: 123,400 VND
Rule: increase >= 5%
Priority: HIGH
```

Use Markdown carefully. Escape user-controlled text before sending.

## Step 8: Implementation Plan in StockTrace

Telegram code should be introduced in the notification/control phase.

Planned files:

```text
src/stocktrace/infrastructure/notifications/
├── telegram_notifier.py
├── message_builder.py
├── queue_sender.py
└── retry_policy.py

src/stocktrace/infrastructure/telegram/
├── bot.py
├── dispatcher.py
├── middleware.py
└── handlers/
    ├── add.py
    ├── remove.py
    ├── list.py
    ├── news.py
    ├── price.py
    └── status.py
```

Command handlers should call application services:

```text
/add
  -> AddWatchlistItemCommandHandler
  -> WatchlistRepository
  -> MessageBuilder
  -> TelegramNotifier

/price
  -> GetStockQuoteQueryHandler
  -> Cache
  -> ProviderManager
  -> MessageBuilder
  -> TelegramNotifier

/status
  -> GetSystemStatusQueryHandler
  -> ProviderHealthService
  -> SchedulerHealthService
  -> MessageBuilder
  -> TelegramNotifier
```

## Step 9: Docker Environment Strategy

For Docker Compose, keep secrets in `.env`:

```text
STOCKTRACE_TELEGRAM__BOT_TOKEN=...
STOCKTRACE_TELEGRAM__CHAT_ID=...
STOCKTRACE_TELEGRAM__ALLOWED_USER_IDS=[123456789]
```

The API container reads these values through `env_file`.

```text
docker-compose.yml
      |
      v
.env
      |
      v
pydantic-settings
      |
      v
TelegramSettings
```

For production:

- Use Docker secrets, a VPS secret file with restricted permissions, or a managed secret store.
- Do not bake tokens into images.
- Rotate the bot token if it is ever exposed.

## Step 10: Operational Checks

Check token validity:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
```

Expected result includes:

```json
{
  "ok": true,
  "result": {
    "username": "stocktrace_monitor_bot"
  }
}
```

Check updates:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"
```

Common problems:

- Bot did not receive `/start`, so `getUpdates` is empty.
- Token copied with extra spaces.
- Token is missing the numeric prefix before `:`. Valid format is `1234567890:AA...`, not only `AA...`.
- Group privacy mode hides messages that are not commands.
- Multiple pollers are running at the same time.
- Webhook is still configured while polling is expected.

Reset webhook before polling:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
```

## Deployment Lifecycle

```text
Create bot with BotFather
      |
      v
Store token in .env or secret manager
      |
      v
Find chat id and allowed user ids
      |
      v
Start StockTrace
      |
      v
Bot registers handlers
      |
      v
User sends /status
      |
      v
App validates user id
      |
      v
App sends response
      |
      v
Alerts are delivered when rules fire
```

## Future Production Hardening

- Webhook secret token validation.
- Per-user authorization roles.
- Admin-only commands.
- Command audit log.
- Redis-backed rate limiting.
- Dead-letter queue for failed notifications.
- Retry with exponential backoff.
- Alert delivery metrics.
- Multi-tenant Telegram chat mapping.
