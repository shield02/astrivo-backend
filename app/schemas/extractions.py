from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Evidence(BaseModel):
    """Source location supporting an extracted value."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: Literal["document_intelligence", "llm", "human_review"]
    page_number: int = Field(ge=1)
    bounding_box: tuple[float, float, float, float] | None = None
    text: str | None = None


class FinancialLineItem(BaseModel):
    """A monetary value extracted from a document."""

    model_config = ConfigDict(strict=True, extra="forbid")

    line_name: str = Field(min_length=1)
    amount: Decimal
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    fiscal_period: str = Field(min_length=1)
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class ComplianceCheckbox(BaseModel):
    """A checkbox or selection mark with its associated label."""

    model_config = ConfigDict(strict=True, extra="forbid")

    checkbox_label: str = Field(min_length=1)
    is_checked: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class DueDiligenceExtractionV1(BaseModel):
    """Version 1 of the validated due-diligence extraction payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    company_name: str = Field(min_length=1)
    document_date: date
    financial_figures: list[FinancialLineItem] = Field(default_factory=list)
    checkboxes: list[ComplianceCheckbox] = Field(default_factory=list)
    risk_summary: str | None = None
