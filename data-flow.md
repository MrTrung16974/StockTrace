# StockTrace Data Flow

## Request Lifecycle

```text
HTTP Client
    |
    v
FastAPI Middleware
    | validate request id, timing, errors
    v
Router
    | parse schema
    v
Dependency Container
    | settings, services, repositories
    v
Application Service
    | use-case orchestration
    v
Domain Layer
    | invariants and business rules
    v
Repository / Provider / Cache Port
    |
    v
Infrastructure Adapter
    |
    v
Database / Redis / External Provider
```

## Telegram Command Lifecycle

```text
Telegram Command
        |
        v
Telegram Authorization Middleware
        |
        v
Command Dispatcher
        |
        v
Telegram Handler
        |
        v
Application Service
        |
        v
Domain Layer
        |
        v
Repository / Provider / Cache
        |
        v
MessageBuilder
        |
        v
QueueSender
        |
        v
TelegramNotifier
```

Commands planned for later phases:

- `/add SYMBOL`
- `/remove SYMBOL`
- `/list`
- `/news SYMBOL`
- `/price SYMBOL`
- `/status`

## Stock Quote Fetch Lifecycle

```text
Scheduler: stock fetch job
        |
        v
Load active watchlist items
        |
        v
ProviderManager
        |
        +--> ProviderSelector
        |       |
        |       v
        |   health score + coverage + rate limit budget
        |
        +--> Concurrent provider calls
                |
                +--> YahooFinanceProvider
                +--> FinnhubProvider
                +--> AlphaVantageProvider
                +--> VNStockProvider
        |
        v
Normalize provider response
        |
        v
StockQuote domain entity
        |
        v
Persist quote snapshot
        |
        v
Publish in-process QuoteFetched event
        |
        v
Alert evaluation job or future event consumer
```

## News Fetch Lifecycle

```text
Scheduler: news fetch job
        |
        v
Feed registry
        |
        +--> RSS
        +--> Google News
        +--> CafeF
        +--> Vietstock
        +--> Yahoo Finance
        |
        v
FeedFetcher
        |
        v
ParserEngine
        |
        v
ArticleHashService
        |
        +--> duplicate exists? yes -> suppress
        |
        v
KeywordExtractor
        |
        v
Sentiment placeholder
        |
        v
Persist NewsArticle
        |
        v
Breaking news rule evaluation
```

## Alert Lifecycle

```text
QuoteFetched / NewsArticleFetched
        |
        v
AlertEvaluationService
        |
        v
Load active AlertRule records
        |
        v
RuleEvaluator pipeline
        |
        +--> price increase %
        +--> price drop %
        +--> unusual volume
        +--> breaking news
        |
        v
CooldownGuard
        |
        v
DebounceGuard
        |
        v
PriorityAssigner
        |
        v
AlertEvent
        |
        v
Persist event
        |
        v
Notification queue
        |
        v
TelegramNotifier
```

## Scheduler Lifecycle

```text
Application startup
        |
        v
Create AsyncIOScheduler
        |
        v
Register jobs
        |
        +--> stock fetch job
        +--> news fetch job
        +--> alert evaluation job
        +--> cleanup job
        +--> heartbeat job
        |
        v
Start scheduler
        |
        v
Isolated job execution
        |
        +--> per-job timeout
        +--> retry policy
        +--> structured logs
        +--> metrics hooks
        |
        v
Graceful shutdown
```

## Component Interaction Diagram

```text
+-----------+      +-------------+      +------------------+
| Telegram  |----->| Bot Adapter |----->| Application Core |
+-----------+      +-------------+      +--------+---------+
                                                   |
+-----------+      +-------------+                 |
| REST User |----->| FastAPI API |-----------------+
+-----------+      +-------------+                 |
                                                   v
                                           +-------+-------+
                                           | Domain Model  |
                                           +-------+-------+
                                                   |
                 +---------------------------------+----------------------------------+
                 |                                 |                                  |
                 v                                 v                                  v
          +-------------+                  +---------------+                  +---------------+
          | PostgreSQL  |                  | Redis / Cache |                  | Stock/News API|
          +-------------+                  +---------------+                  +---------------+
```

## Data Ownership

```text
StockQuote      owned by quote ingestion and used by alert evaluation
NewsArticle     owned by news aggregation and used by breaking-news rules
WatchlistItem   owned by Telegram/API commands
AlertRule       owned by Telegram/API commands
AlertEvent      owned by alert engine and notification pipeline
ProviderHealth  owned by provider manager
```
