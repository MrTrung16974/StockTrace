"""Official trace source catalog."""

from __future__ import annotations

from stocktrace.domain.entities.trace import TraceSource, TraceSourceType


def official_trace_sources() -> tuple[TraceSource, ...]:
    """Return official source metadata used to seed the trace engine."""
    return (
        TraceSource(
            code="VNX",
            name="Vietnam Exchange",
            source_type=TraceSourceType.EXCHANGE,
            base_url="https://www.vnx.vn/",
            rank=1,
            official=True,
            description="Exchange-level market information, members, and legal documents.",
        ),
        TraceSource(
            code="HOSE",
            name="Ho Chi Minh Stock Exchange",
            source_type=TraceSourceType.EXCHANGE,
            base_url="https://www.hsx.vn/",
            rank=1,
            official=True,
            description="HOSE listed equities, indices, trading data, and issuer disclosures.",
        ),
        TraceSource(
            code="HNX",
            name="Hanoi Stock Exchange",
            source_type=TraceSourceType.EXCHANGE,
            base_url="https://www.hnx.vn/",
            rank=1,
            official=True,
            description="HNX equities, UPCoM, bonds, derivatives, and issuer disclosures.",
        ),
        TraceSource(
            code="SSC",
            name="State Securities Commission of Vietnam",
            source_type=TraceSourceType.REGULATORY,
            base_url="https://ssc.gov.vn/",
            rank=1,
            official=True,
            description="Securities regulation, enforcement, policy, and market warnings.",
        ),
        TraceSource(
            code="VSDC",
            name="Viet Nam Securities Depository and Clearing Corporation",
            source_type=TraceSourceType.CORPORATE_ACTION,
            base_url="https://vsd.vn/",
            rank=1,
            official=True,
            description="Corporate actions, foreign ownership, registration, and settlement.",
        ),
        TraceSource(
            code="SBV",
            name="State Bank of Vietnam",
            source_type=TraceSourceType.MACRO,
            base_url="https://www.sbv.gov.vn/",
            rank=1,
            official=True,
            description="FX, rates, credit, banking statistics, and monetary policy.",
        ),
        TraceSource(
            code="GSO",
            name="General Statistics Office of Vietnam",
            source_type=TraceSourceType.MACRO,
            base_url="https://www.gso.gov.vn/",
            rank=1,
            official=True,
            description="CPI, GDP, and macroeconomic indicators.",
        ),
        TraceSource(
            code="MOF",
            name="Ministry of Finance",
            source_type=TraceSourceType.REGULATORY,
            base_url="https://mof.gov.vn/",
            rank=1,
            official=True,
            description="Fiscal policy, tax policy, and securities-related legal documents.",
        ),
    )
