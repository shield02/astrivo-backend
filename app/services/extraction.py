from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol
from uuid import UUID

from app.schemas.extractions import (
    ComplianceCheckbox,
    DueDiligenceExtractionV1,
    Evidence,
    FinancialLineItem,
)
from app.services.ocr import LayoutDocument


class StructuredExtraction(Protocol):
    async def extract(
        self, *, tenant_id: UUID, document_id: UUID, layout: LayoutDocument
    ) -> DueDiligenceExtractionV1: ...


class MockStructuredExtraction:
    """Parses a small explicit fixture format for the portfolio workflow."""

    async def extract(
        self, *, tenant_id: UUID, document_id: UUID, layout: LayoutDocument
    ) -> DueDiligenceExtractionV1:
        values: dict[str, str] = {}
        figures: list[FinancialLineItem] = []
        checkboxes: list[ComplianceCheckbox] = []
        for line in layout.text.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key.strip().lower()] = value.strip()
            if line.lower().startswith("figure:"):
                name, _, amount_text = line[7:].partition("=")
                try:
                    amount = Decimal(amount_text.strip())
                except (InvalidOperation, ValueError) as exc:
                    raise ValueError("Mock financial figure is not a valid decimal.") from exc
                figures.append(
                    FinancialLineItem(
                        line_name=name.strip(),
                        amount=amount,
                        currency=values.get("currency", "USD"),
                        fiscal_period=values.get("fiscal_period", "unknown"),
                        confidence_score=1.0,
                        evidence=[Evidence(source="document_intelligence", page_number=1)],
                    )
                )
            if line.lower().startswith("checkbox:"):
                label, _, checked = line[9:].partition("=")
                checkboxes.append(
                    ComplianceCheckbox(
                        checkbox_label=label.strip(),
                        is_checked=checked.strip().lower() == "true",
                        confidence_score=1.0,
                        evidence=[Evidence(source="document_intelligence", page_number=1)],
                    )
                )

        document_date = date.fromisoformat(values.get("document_date", "2026-01-01"))
        return DueDiligenceExtractionV1(
            company_name=values.get("company_name", "Portfolio Demo Company"),
            document_date=document_date,
            financial_figures=figures,
            checkboxes=checkboxes,
            risk_summary=values.get("risk_summary"),
        )
