from __future__ import annotations

import base64
import binascii
from datetime import date
from datetime import UTC, datetime
import json
import os
import random
import re
from typing import Any

from .models import (
    Benefit,
    CopaymentSummary,
    CoverageStatusSummary,
    DocumentExtractionRequest,
    DocumentExtractionResponse,
    ExtractedDriverLicenseData,
    ExtractedInsuranceCardData,
    EligibilityRequest,
    EligibilityResponse,
    EligibilityStatus,
    ExtractionValidationIssue,
    Parsed271SummaryResponse,
    PharmacyInfoSummary,
)

SENDER_ID = "UHC"
RECEIVER_ID = "ICLINIC"
INTERCHANGE_CONTROL_NUMBER = "000000905"
FUNCTIONAL_GROUP_CONTROL_NUMBER = "905"


def _build_transaction_id() -> str:
    now = datetime.now(UTC)
    random_suffix = random.randint(1000, 9999)
    return f"TX{now.strftime('%Y%m%d%H%M%S')}{random_suffix}"


def _build_st_control_number(transaction_id: str) -> str:
    digits = "".join(char for char in transaction_id if char.isdigit())
    return digits[-4:].zfill(4)


def _resolve_financials(request: EligibilityRequest) -> tuple[float, float, float, float]:
    copay = request.insurance.copay
    if copay is None:
        return (25.0, 30.0, 150.0, 300.0)
    return (
        float(copay.office),
        float(copay.specialist),
        float(copay.urgent_care),
        float(copay.emergency_room),
    )


def _determine_eligibility(request: EligibilityRequest) -> EligibilityStatus:
    policy = request.insurance.policy_number.upper()

    # Simple rule engine simulation:
    # - policy starts with ACT -> active
    # - policy starts with EXP -> inactive/expired
    # - otherwise deterministic hash-like fallback for mixed mock data
    if policy.startswith("ACT"):
        return EligibilityStatus(active=True, status_code="1", message="Active coverage")

    if policy.startswith("EXP"):
        return EligibilityStatus(active=False, status_code="6", message="Inactive coverage")

    score = sum(ord(char) for char in policy)
    is_active = score % 2 == 0
    return EligibilityStatus(
        active=is_active,
        status_code="1" if is_active else "6",
        message="Active coverage" if is_active else "Inactive coverage",
    )


def _build_benefits(request: EligibilityRequest, active: bool) -> list[Benefit]:
    if not active:
        return []

    service_type = request.insurance.service_type_code
    in_network_copay, out_network_copay, in_network_deductible, out_network_deductible = _resolve_financials(request)
    return [
        Benefit(
            service_type_code=service_type,
            coverage_level="individual",
            network="in",
            copay=in_network_copay,
            deductible_remaining=in_network_deductible,
        ),
        Benefit(
            service_type_code=service_type,
            coverage_level="individual",
            network="out",
            copay=out_network_copay,
            deductible_remaining=out_network_deductible,
        ),
    ]


def _generate_hipaa_271(
    request: EligibilityRequest,
    transaction_id: str,
    status: EligibilityStatus,
    benefits: list[Benefit],
) -> str:
    now = datetime.now(UTC)
    st_control_number = _build_st_control_number(transaction_id)
    date_yyyymmdd = now.strftime("%Y%m%d")
    date_yymmdd = now.strftime("%y%m%d")
    time_hhmm = now.strftime("%H%M")

    n3_segment = f"N3*{request.patient.address.line1}~"
    if request.patient.address.line2:
        n3_segment = f"N3*{request.patient.address.line1}*{request.patient.address.line2}~"

    transaction_segments = [
        f"ST*271*{st_control_number}*005010X279A1~",
        f"BHT*0022*11*{transaction_id}*{date_yyyymmdd}*{time_hhmm}~",
        "HL*1**20*1~",
        f"NM1*PR*2*{request.insurance.payer_name.upper()}*****PI*{request.insurance.payer_id}~",
        "HL*2*1*21*1~",
        f"NM1*1P*2*{RECEIVER_ID}*****XX*{request.provider.npi}~",
        "HL*3*2*22*0~",
        f"TRN*2*{request.trace_id}*{request.provider.tax_id}~",
        (
            "NM1*IL*1*{last}*{first}****MI*{member_id}~".format(
                last=request.patient.name.last.upper(),
                first=request.patient.name.first.upper(),
                member_id=request.insurance.member_id,
            )
        ),
        n3_segment,
        (
            "N4*{city}*{state}*{postal_code}~".format(
                city=request.patient.address.city.upper(),
                state=request.patient.address.state.upper(),
                postal_code=request.patient.address.postal_code,
            )
        ),
        f"DMG*D8*{request.patient.date_of_birth.strftime('%Y%m%d')}*{request.patient.gender}~",
        f"DTP*291*D8*{request.service_date.strftime('%Y%m%d')}~",
    ]

    if status.active:
        in_network_copay, out_network_copay, in_network_deductible, out_network_deductible = _resolve_financials(request)

        if benefits:
            in_network = next((item for item in benefits if item.network == "in"), benefits[0])
            out_network = next((item for item in benefits if item.network == "out"), benefits[0])
            in_network_copay = int(in_network.copay)
            out_network_copay = int(out_network.copay)
            in_network_deductible = int(in_network.deductible_remaining)
            out_network_deductible = int(out_network.deductible_remaining)

        transaction_segments.extend(
            [
                f"EB*1*IND*{request.insurance.service_type_code}**23~",
                f"EB*B*IND*98**{in_network_copay}~",
                f"EB*B*IND*98**{out_network_copay}~",
                f"EB*B*IND*98**{in_network_deductible}~",
                f"EB*B*IND*98**{out_network_deductible}~",
                "EB*1*IND*88~",
            ]
        )
    else:
        transaction_segments.append(f"EB*6*IND*{request.insurance.service_type_code}**{status.message}~")

    transaction_segments.extend(
        [
            f"REF*6P*{request.insurance.rx_bin or request.provider.npi}~",
            f"REF*HJ*{request.insurance.rx_pcn or request.insurance.group_number or '9999'}~",
            f"REF*CE*{(request.insurance.rx_group or request.insurance.payer_name).replace(' ', '').upper()}~",
        ]
    )

    segment_count = len(transaction_segments) + 1
    segments = [
        f"ISA*00*          *00*          *ZZ*{SENDER_ID:<15}*ZZ*{RECEIVER_ID:<15}*{date_yymmdd}*{time_hhmm}*^*00501*{INTERCHANGE_CONTROL_NUMBER}*0*T*:~",
        (
            "GS*HB*{sender}*{receiver}*{date}*{time}*{group_control}*X*005010X279A1~".format(
                sender=SENDER_ID,
                receiver=RECEIVER_ID,
                date=date_yyyymmdd,
                time=time_hhmm,
                group_control=FUNCTIONAL_GROUP_CONTROL_NUMBER,
            )
        ),
        *transaction_segments,
        f"SE*{segment_count}*{st_control_number}~",
        f"GE*1*{FUNCTIONAL_GROUP_CONTROL_NUMBER}~",
        f"IEA*1*{INTERCHANGE_CONTROL_NUMBER}~",
    ]
    return "\n".join(segments)


def verify_eligibility(request: EligibilityRequest) -> EligibilityResponse:
    transaction_id = _build_transaction_id()
    status = _determine_eligibility(request)
    benefits = _build_benefits(request, status.active)
    generated_at = datetime.now(UTC).isoformat()
    hipaa_271 = _generate_hipaa_271(request, transaction_id, status, benefits)

    return EligibilityResponse(
        trace_id=request.trace_id,
        transaction_id=transaction_id,
        generated_at=generated_at,
        eligibility=status,
        benefits=benefits,
        hipaa_271=hipaa_271,
    )


def _split_271_segments(raw_271: str) -> list[str]:
    normalized = raw_271.replace("\r", "\n")
    if "~" in normalized:
        chunks = normalized.split("~")
    else:
        chunks = normalized.split("\n")
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _to_float(value: str) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace("$", "")
    if cleaned == "":
        return None
    if not re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return None
    return float(cleaned)


def _format_money(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value.is_integer():
        return f"${int(value)}"
    return f"${value:.2f}"


def parse_271_summary(raw_271: str) -> Parsed271SummaryResponse:
    segments = _split_271_segments(raw_271)
    if not segments:
        raise ValueError("raw_271 does not contain parseable segments")

    coverage_status = CoverageStatusSummary(message="Coverage status not present in 271")
    copay_values: list[float] = []
    rx_bin: str | None = None
    rx_pcn: str | None = None
    rx_group: str | None = None

    for segment in segments:
        parts = segment.split("*")
        if not parts:
            continue

        tag = parts[0]

        if tag == "EB" and len(parts) >= 2:
            eb_code = parts[1]
            if eb_code in {"1", "6"} and coverage_status.status_code is None:
                is_active = eb_code == "1"
                message = "Active coverage" if is_active else "Inactive coverage"
                if len(parts) >= 6 and parts[5].strip():
                    message = parts[5].strip()
                coverage_status = CoverageStatusSummary(
                    active=is_active,
                    status_code=eb_code,
                    message=message,
                )

            if eb_code == "B" and len(parts) >= 6:
                amount = _to_float(parts[5])
                if amount is not None:
                    copay_values.append(amount)

        if tag == "REF" and len(parts) >= 3:
            ref_code = parts[1]
            ref_value = parts[2].strip()
            if ref_code == "6P":
                rx_bin = ref_value
            elif ref_code == "HJ":
                rx_pcn = ref_value
            elif ref_code == "CE":
                rx_group = ref_value

    copayment_amounts = CopaymentSummary(
        office=copay_values[0] if len(copay_values) > 0 else None,
        specialist=copay_values[1] if len(copay_values) > 1 else None,
        urgent_care=copay_values[2] if len(copay_values) > 2 else None,
        emergency_room=copay_values[3] if len(copay_values) > 3 else None,
        extracted_values=copay_values,
    )

    pharmacy_info = PharmacyInfoSummary(
        present=any(value is not None for value in (rx_bin, rx_pcn, rx_group)),
        rx_bin=rx_bin,
        rx_pcn=rx_pcn,
        rx_group=rx_group,
    )

    coverage_text = "Unknown"
    if coverage_status.active is True:
        coverage_text = "Active"
    elif coverage_status.active is False:
        coverage_text = "Inactive"

    front_desk_display = (
        "Coverage: {coverage} | Office: {office} | Specialist: {specialist} | "
        "Urgent Care: {urgent_care} | ER: {emergency_room}"
    ).format(
        coverage=coverage_text,
        office=_format_money(copayment_amounts.office),
        specialist=_format_money(copayment_amounts.specialist),
        urgent_care=_format_money(copayment_amounts.urgent_care),
        emergency_room=_format_money(copayment_amounts.emergency_room),
    )

    return Parsed271SummaryResponse(
        coverage_status=coverage_status,
        copayment_amounts=copayment_amounts,
        pharmacy_info=pharmacy_info,
        front_desk_display=front_desk_display,
    )


def _validate_base64_image(data: str, field_name: str) -> None:
    try:
        base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ValueError(f"{field_name} is not valid base64 image content") from err


def _to_data_url(image_base64: str, mime_type: str) -> str:
    return f"data:{mime_type};base64,{image_base64}"


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace("$", "")
        if stripped == "":
            return None
        if re.fullmatch(r"\d+(\.\d+)?", stripped):
            return float(stripped)
    return None


def _build_front_desk_copay_display(insurance: ExtractedInsuranceCardData) -> str:
    return (
        "Office: {office} | Specialist: {specialist} | Urgent Care: {urgent_care} | ER: {er}"
    ).format(
        office=_format_money(insurance.copay_office),
        specialist=_format_money(insurance.copay_specialist),
        urgent_care=_format_money(insurance.copay_urgent_care),
        er=_format_money(insurance.copay_emergency_room),
    )


def _validate_extracted_data(
    driver_license: ExtractedDriverLicenseData,
    insurance: ExtractedInsuranceCardData,
) -> list[ExtractionValidationIssue]:
    issues: list[ExtractionValidationIssue] = []

    if not driver_license.dmv_id_number:
        issues.append(ExtractionValidationIssue(field="driver_license.dmv_id_number", message="DMV ID number is missing"))
    if not driver_license.document_number:
        issues.append(ExtractionValidationIssue(field="driver_license.document_number", message="Document number is missing"))
    if not driver_license.name_first:
        issues.append(ExtractionValidationIssue(field="driver_license.name_first", message="First name is missing"))
    if not driver_license.name_last:
        issues.append(ExtractionValidationIssue(field="driver_license.name_last", message="Last name is missing"))

    if driver_license.gender and driver_license.gender not in {"M", "F", "U"}:
        issues.append(ExtractionValidationIssue(field="driver_license.gender", message="Gender must be M, F, or U"))

    if driver_license.date_of_birth:
        try:
            date.fromisoformat(driver_license.date_of_birth)
        except ValueError:
            issues.append(
                ExtractionValidationIssue(
                    field="driver_license.date_of_birth",
                    message="Date of birth must be ISO format YYYY-MM-DD",
                )
            )

    if driver_license.address_state and len(driver_license.address_state) != 2:
        issues.append(
            ExtractionValidationIssue(
                field="driver_license.address_state",
                message="State code should be two letters",
            )
        )

    if not insurance.payer_id:
        issues.append(ExtractionValidationIssue(field="insurance_card.payer_id", message="Payer ID is missing"))
    elif not re.fullmatch(r"[A-Za-z0-9]{3,15}", insurance.payer_id):
        issues.append(ExtractionValidationIssue(field="insurance_card.payer_id", message="Payer ID format is invalid"))

    if not insurance.member_id:
        issues.append(ExtractionValidationIssue(field="insurance_card.member_id", message="Member ID is missing"))
    if not insurance.group_number:
        issues.append(ExtractionValidationIssue(field="insurance_card.group_number", message="Group number is missing"))

    for field_name, value in [
        ("insurance_card.copay_office", insurance.copay_office),
        ("insurance_card.copay_specialist", insurance.copay_specialist),
        ("insurance_card.copay_urgent_care", insurance.copay_urgent_care),
        ("insurance_card.copay_emergency_room", insurance.copay_emergency_room),
    ]:
        if value is not None and value < 0:
            issues.append(ExtractionValidationIssue(field=field_name, message="Copay cannot be negative"))

    return issues


def _call_openai_for_extraction(request: DocumentExtractionRequest) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    try:
        from openai import OpenAI
    except ImportError as err:
        raise ValueError("openai package is not installed") from err

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Extract structured data from these images: a US driver's license, an insurance card front, "
        "and an insurance card back. Return JSON only with keys driver_license and insurance_card. "
        "Use null if a value is not visible. For date_of_birth use YYYY-MM-DD if possible. "
        "driver_license keys: dmv_id_number, document_number, date_of_birth, gender, name_first, "
        "name_last, address_line1, address_city, address_state, address_postal_code. "
        "insurance_card keys: payer_id, payer_name, member_id, policy_number, group_number, rx_bin, "
        "rx_pcn, rx_group, copay_office, copay_specialist, copay_urgent_care, copay_emergency_room."
    )

    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Driver's license image"},
                    {
                        "type": "image_url",
                        "image_url": {"url": _to_data_url(request.drivers_license_image.image_base64, request.drivers_license_image.mime_type)},
                    },
                    {"type": "text", "text": "Insurance card front image"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _to_data_url(
                                request.insurance_card_front_image.image_base64,
                                request.insurance_card_front_image.mime_type,
                            )
                        },
                    },
                    {"type": "text", "text": "Insurance card back image"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _to_data_url(
                                request.insurance_card_back_image.image_base64,
                                request.insurance_card_back_image.mime_type,
                            )
                        },
                    },
                ],
            },
        ],
    )

    raw = completion.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        raise ValueError("OpenAI response is not valid JSON") from err

    if not isinstance(parsed, dict):
        raise ValueError("OpenAI response JSON must be an object")
    return parsed


def extract_documents_with_openai(request: DocumentExtractionRequest) -> DocumentExtractionResponse:
    _validate_base64_image(request.drivers_license_image.image_base64, "drivers_license_image")
    _validate_base64_image(request.insurance_card_front_image.image_base64, "insurance_card_front_image")
    _validate_base64_image(request.insurance_card_back_image.image_base64, "insurance_card_back_image")

    extracted = _call_openai_for_extraction(request)
    driver_raw = extracted.get("driver_license") if isinstance(extracted.get("driver_license"), dict) else {}
    insurance_raw = extracted.get("insurance_card") if isinstance(extracted.get("insurance_card"), dict) else {}

    driver_license = ExtractedDriverLicenseData(
        dmv_id_number=driver_raw.get("dmv_id_number"),
        document_number=driver_raw.get("document_number"),
        date_of_birth=driver_raw.get("date_of_birth"),
        gender=driver_raw.get("gender"),
        name_first=driver_raw.get("name_first"),
        name_last=driver_raw.get("name_last"),
        address_line1=driver_raw.get("address_line1"),
        address_city=driver_raw.get("address_city"),
        address_state=driver_raw.get("address_state"),
        address_postal_code=driver_raw.get("address_postal_code"),
    )

    insurance = ExtractedInsuranceCardData(
        payer_id=insurance_raw.get("payer_id"),
        payer_name=insurance_raw.get("payer_name"),
        member_id=insurance_raw.get("member_id"),
        policy_number=insurance_raw.get("policy_number"),
        group_number=insurance_raw.get("group_number"),
        rx_bin=insurance_raw.get("rx_bin"),
        rx_pcn=insurance_raw.get("rx_pcn"),
        rx_group=insurance_raw.get("rx_group"),
        copay_office=_to_float_or_none(insurance_raw.get("copay_office")),
        copay_specialist=_to_float_or_none(insurance_raw.get("copay_specialist")),
        copay_urgent_care=_to_float_or_none(insurance_raw.get("copay_urgent_care")),
        copay_emergency_room=_to_float_or_none(insurance_raw.get("copay_emergency_room")),
    )

    validation_issues = _validate_extracted_data(driver_license, insurance)
    front_desk_copay_display = _build_front_desk_copay_display(insurance)

    return DocumentExtractionResponse(
        driver_license=driver_license,
        insurance_card=insurance,
        is_valid=len(validation_issues) == 0,
        validation_issues=validation_issues,
        front_desk_copay_display=front_desk_copay_display,
    )
