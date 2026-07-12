# Official Data Source Map

This document defines the first-party and regulator-grade sources that should
drive StockTrace trace events. Commercial/community providers may still be used
for cache, enrichment, or fallback, but they must not silently override official
sources.

## Source Priority

| Rank | Source group | Usage |
| --- | --- | --- |
| 1 | Official exchange, regulator, depository, central bank, statistics authority | Source of truth |
| 2 | Company investor relations pages and published reports | Issuer-confirmed source |
| 3 | Licensed commercial providers | Fallback and enrichment |
| 4 | News and community sources | Context only |

Every ingested trace event must store `source_name`, `source_url`,
`published_at`, `fetched_at`, `checksum`, `confidence`, and whether the source is
official.

## Vietnam Official Sources

| Code | Source | URL | Trace coverage |
| --- | --- | --- | --- |
| VNX | Vietnam Exchange | https://www.vnx.vn/ | Exchange-level market information, member disclosures, market rules |
| HOSE | Ho Chi Minh Stock Exchange | https://www.hsx.vn/ | HOSE listed equities, indices, trading data, issuer disclosures |
| HNX | Hanoi Stock Exchange | https://www.hnx.vn/ | HNX equities, UPCoM, bonds, derivatives, issuer disclosures |
| SSC | State Securities Commission of Vietnam | https://ssc.gov.vn/ | Regulation, enforcement, policy notices, market warnings |
| VSDC | Viet Nam Securities Depository and Clearing Corporation | https://vsd.vn/ | Corporate actions, foreign ownership, registration, settlement events |
| SBV | State Bank of Vietnam | https://www.sbv.gov.vn/ | FX, rates, credit, banking system statistics, monetary policy |
| GSO | General Statistics Office of Vietnam | https://www.gso.gov.vn/ | CPI, GDP, macro indicators |
| MOF | Ministry of Finance | https://mof.gov.vn/ | Tax, fiscal policy, securities-related legal documents |

## Initial Trace Types

| Trace type | Primary source | Meaning |
| --- | --- | --- |
| `TRACE_PRICE` | HOSE, HNX | Official price movement |
| `TRACE_VOLUME` | HOSE, HNX | Liquidity and volume anomaly |
| `TRACE_DISCLOSURE` | HOSE, HNX, VNX | Issuer/member disclosure |
| `TRACE_FINANCIAL_STATEMENT` | HOSE, HNX, company IR | Periodic financial filing |
| `TRACE_CORPORATE_ACTION` | VSDC, HOSE, HNX | Dividend, rights issue, listing/platform shift |
| `TRACE_FOREIGN_OWNERSHIP` | VSDC | Foreign ownership disclosure |
| `TRACE_REGULATORY` | SSC, MOF, VNX | Rule, circular, policy, trading regulation |
| `TRACE_ENFORCEMENT` | SSC | Sanction, warning, supervision event |
| `TRACE_MACRO_RATE` | SBV | Policy and interbank rate events |
| `TRACE_FX` | SBV | Central/reference exchange-rate changes |
| `TRACE_SECTOR` | HOSE, HNX, VNX | Sector/index context |
| `TRACE_MARKET_STRUCTURE` | VNX, HOSE, HNX, VSDC | Membership, platform, settlement, market infrastructure |

## Ingestion Rules

1. Normalize source documents before analysis.
2. Compute a checksum from canonical URL, published timestamp, title, and body.
3. Deduplicate by checksum first, then by source, symbol, event type, and date.
4. Store raw text for audit and reprocessing.
5. Assign confidence `1.0` to official source events unless parsing is partial.
6. Never emit an investment recommendation directly from an ingestion adapter.

## Implementation Phases

1. Add trace domain entities, provider ports, repositories, ORM models, and migrations.
2. Seed official source metadata for VNX, HOSE, HNX, SSC, VSDC, SBV, GSO, and MOF.
3. Build read-only pollers for VSDC corporate actions and VNX/HOSE/HNX disclosures.
4. Build `/trace SYMBOL`, `/events SYMBOL`, and `/why SYMBOL` query surfaces.
5. Add scoring, alert deduplication, and AI explanation after deterministic traces exist.
