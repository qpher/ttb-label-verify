"""Pydantic models for the label verification API."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BeverageType(str, Enum):
    distilled_spirits = "distilled_spirits"
    wine = "wine"
    beer = "beer"


class ApplicationData(BaseModel):
    """What the applicant claims is on the label (from the COLA application)."""

    brand_name: str = Field(..., examples=["OLD TOM DISTILLERY"])
    class_type: str = Field(..., examples=["Kentucky Straight Bourbon Whiskey"])
    alcohol_content: str = Field(..., examples=["45% Alc./Vol. (90 Proof)"])
    net_contents: str = Field(..., examples=["750 mL"])
    beverage_type: BeverageType = BeverageType.distilled_spirits
    # Optional fields — checked only if provided
    producer_name_address: Optional[str] = None
    country_of_origin: Optional[str] = None


class ExtractedWarning(BaseModel):
    """Government warning as read off the label image."""

    present: bool = False
    text: Optional[str] = None
    header_all_caps: Optional[bool] = None
    header_bold: Optional[bool] = None


class ExtractedLabel(BaseModel):
    """Fields Claude extracted from the label image."""

    brand_name: Optional[str] = None
    class_type: Optional[str] = None
    alcohol_content: Optional[str] = None
    net_contents: Optional[str] = None
    producer_name_address: Optional[str] = None
    country_of_origin: Optional[str] = None
    government_warning: ExtractedWarning = ExtractedWarning()
    image_quality_issues: Optional[str] = None
    legibility: str = "ok"  # ok | partial | unreadable


class CheckStatus(str, Enum):
    match = "MATCH"
    needs_review = "NEEDS_REVIEW"
    mismatch = "MISMATCH"
    missing = "MISSING"
    not_checked = "NOT_CHECKED"


class FieldCheck(BaseModel):
    field: str
    status: CheckStatus
    application_value: Optional[str] = None
    label_value: Optional[str] = None
    note: Optional[str] = None


class OverallStatus(str, Enum):
    approved = "APPROVED"
    needs_review = "NEEDS_REVIEW"
    rejected = "REJECTED"
    error = "ERROR"


class VerificationResult(BaseModel):
    filename: Optional[str] = None
    overall_status: OverallStatus
    checks: list[FieldCheck]
    extracted: Optional[ExtractedLabel] = None
    summary: str
    processing_seconds: float
    error: Optional[str] = None
