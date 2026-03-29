from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Name(BaseModel):
    first: str = Field(min_length=1, max_length=50)
    last: str = Field(min_length=1, max_length=50)


class Address(BaseModel):
    line1: str = Field(min_length=1, max_length=100)
    line2: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=50)
    state: str = Field(min_length=2, max_length=2, description="Two-letter state code")
    postal_code: str = Field(min_length=5, max_length=10)

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.upper()


class Patient(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dmv_id_number: str = Field(min_length=5, max_length=30)
    document_number: str = Field(min_length=5, max_length=30)
    date_of_birth: date
    gender: Literal["M", "F", "U"]
    name: Name
    address: Address


class Provider(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    npi: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")
    tax_id: str = Field(min_length=9, max_length=9, pattern=r"^\d{9}$")


class CopayInfo(BaseModel):
    office: float = Field(ge=0)
    specialist: float = Field(ge=0)
    urgent_care: float = Field(ge=0)
    emergency_room: float = Field(ge=0)


class Insurance(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payer_id: str = Field(min_length=3, max_length=15)
    payer_name: str = Field(min_length=2, max_length=80)
    member_id: str = Field(min_length=5, max_length=30)
    policy_number: str = Field(min_length=5, max_length=30)
    group_number: str | None = Field(default=None, max_length=30)
    service_type_code: str = Field(default="30", min_length=2, max_length=2)
    rx_bin: str | None = Field(default=None, min_length=3, max_length=12)
    rx_pcn: str | None = Field(default=None, min_length=2, max_length=20)
    rx_group: str | None = Field(default=None, min_length=2, max_length=30)
    copay: CopayInfo | None = None


class EligibilityRequest(BaseModel):
    trace_id: str = Field(min_length=8, max_length=64)
    service_date: date
    patient: Patient
    provider: Provider
    insurance: Insurance

    @field_validator("service_date")
    @classmethod
    def service_date_not_too_old(cls, value: date) -> date:
        cutoff = date(2000, 1, 1)
        if value < cutoff:
            raise ValueError("service_date cannot be before 2000-01-01")
        return value


class Benefit(BaseModel):
    service_type_code: str
    coverage_level: Literal["individual", "family"]
    network: Literal["in", "out"]
    copay: float
    deductible_remaining: float


class EligibilityStatus(BaseModel):
    active: bool
    status_code: Literal["1", "6"]
    message: str


class EligibilityResponse(BaseModel):
    trace_id: str
    transaction_id: str
    generated_at: str
    eligibility: EligibilityStatus
    benefits: list[Benefit]
    hipaa_271: str


class ApiError(BaseModel):
    error_code: str
    message: str
    details: str | None = None


class Parse271Request(BaseModel):
    raw_271: str = Field(min_length=20, description="Raw HIPAA 271 message with segments delimited by ~ or new lines")


class CoverageStatusSummary(BaseModel):
    active: bool | None = None
    status_code: str | None = None
    message: str


class CopaymentSummary(BaseModel):
    office: float | None = None
    specialist: float | None = None
    urgent_care: float | None = None
    emergency_room: float | None = None
    extracted_values: list[float] = Field(default_factory=list)


class PharmacyInfoSummary(BaseModel):
    present: bool
    rx_bin: str | None = None
    rx_pcn: str | None = None
    rx_group: str | None = None


class Parsed271SummaryResponse(BaseModel):
    coverage_status: CoverageStatusSummary
    copayment_amounts: CopaymentSummary
    pharmacy_info: PharmacyInfoSummary
    front_desk_display: str


class DocumentImageInput(BaseModel):
    image_base64: str = Field(min_length=16)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"


class DocumentExtractionRequest(BaseModel):
    drivers_license_image: DocumentImageInput
    insurance_card_front_image: DocumentImageInput
    insurance_card_back_image: DocumentImageInput


class ExtractedDriverLicenseData(BaseModel):
    dmv_id_number: str | None = None
    document_number: str | None = None
    date_of_birth: str | None = None
    gender: Literal["M", "F", "U"] | None = None
    name_first: str | None = None
    name_last: str | None = None
    address_line1: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_postal_code: str | None = None


class ExtractedInsuranceCardData(BaseModel):
    payer_id: str | None = None
    payer_name: str | None = None
    member_id: str | None = None
    policy_number: str | None = None
    group_number: str | None = None
    rx_bin: str | None = None
    rx_pcn: str | None = None
    rx_group: str | None = None
    copay_office: float | None = None
    copay_specialist: float | None = None
    copay_urgent_care: float | None = None
    copay_emergency_room: float | None = None


class ExtractionValidationIssue(BaseModel):
    field: str
    message: str


class DocumentExtractionResponse(BaseModel):
    driver_license: ExtractedDriverLicenseData
    insurance_card: ExtractedInsuranceCardData
    is_valid: bool
    validation_issues: list[ExtractionValidationIssue]
    front_desk_copay_display: str
