# Eligibility API Layer (FastAPI)

This service exposes an endpoint to initiate eligibility verification and returns a simulated HIPAA 271 payload.

## Endpoint

- `POST /api/v1/eligibility/verify`
- `POST /api/v1/eligibility/parse-271`
- `POST /api/v1/documents/extract`

## Request Body

```json
{
  "trace_id": "trace-12345",
  "service_date": "2026-03-28",
  "patient": {
    "dmv_id_number": "NY-DMV-10001",
    "document_number": "DOC-10001",
    "date_of_birth": "1988-08-23",
    "gender": "F",
    "name": { "first": "Jane", "last": "Doe" },
    "address": {
      "line1": "100 Main St",
      "line2": "Suite 200",
      "city": "Austin",
      "state": "TX",
      "postal_code": "78701"
    }
  },
  "provider": {
    "npi": "1234567890",
    "tax_id": "123456789"
  },
  "insurance": {
    "payer_id": "87726",
    "payer_name": "UnitedHealthcare",
    "member_id": "123456789",
    "policy_number": "ACT-911-87726-04",
    "group_number": "98765",
    "service_type_code": "30",
    "rx_bin": "610279",
    "rx_pcn": "9999",
    "rx_group": "UHEALTH"
  }
}
```

## Response

```json
{
  "trace_id": "trace-12345",
  "transaction_id": "TX202603281212019999",
  "generated_at": "2026-03-28T12:12:01.000000+00:00",
  "eligibility": {
    "active": true,
    "status_code": "1",
    "message": "Active coverage"
  },
  "benefits": [
    {
      "service_type_code": "30",
      "coverage_level": "individual",
      "network": "in",
      "copay": 25.0,
      "deductible_remaining": 600.0
    }
  ],
  "hipaa_271": "ISA*00*...~\nGS*HB*UHC*ICLINIC...~\nST*271*...~\n..."
}
```

## Parse 271 Endpoint

Request:

```json
{
  "raw_271": "ISA*00*...~\nGS*HB*...~\nST*271*...~\n..."
}
```

## Document Extraction Endpoint

Requires:

- `OPENAI_API_KEY` environment variable
- Optional: `OPENAI_MODEL` (default: `gpt-4.1-mini`)

Request:

```json
{
  "drivers_license_image": {
    "image_base64": "<base64>",
    "mime_type": "image/jpeg"
  },
  "insurance_card_front_image": {
    "image_base64": "<base64>",
    "mime_type": "image/jpeg"
  },
  "insurance_card_back_image": {
    "image_base64": "<base64>",
    "mime_type": "image/jpeg"
  }
}
```

Response includes:

- Extracted driver's license fields
- Extracted insurance card fields
- Validation issues list and `is_valid`
- `front_desk_copay_display` for staff

Response summary:

```json
{
  "coverage_status": {
    "active": true,
    "status_code": "1",
    "message": "Active coverage"
  },
  "copayment_amounts": {
    "office": 25,
    "specialist": 30,
    "urgent_care": 150,
    "emergency_room": 300,
    "extracted_values": [25, 30, 150, 300]
  },
  "pharmacy_info": {
    "present": true,
    "rx_bin": "610279",
    "rx_pcn": "9999",
    "rx_group": "UHEALTH"
  },
  "front_desk_display": "Coverage: Active | Office: $25 | Specialist: $30 | Urgent Care: $150 | ER: $300"
}
```

## Error Shape

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request payload failed validation",
  "details": "[...]"
}
```

## Insurance Card Mapping

- Member ID -> `insurance.member_id` -> `NM1*IL ... MI`
- Group Number -> `insurance.group_number`
- Payer ID -> `insurance.payer_id` -> `NM1*PR ... PI`
- Rx BIN -> `insurance.rx_bin` -> `REF*6P`
- Rx PCN -> `insurance.rx_pcn` -> `REF*HJ`
- Rx Group -> `insurance.rx_group` -> `REF*CE`

## Run

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY='YOUR_OPENAI_API_KEY'
uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
pytest -q
```

Swagger UI:

- `http://localhost:8000/docs`

## React Frontend

The React intake UI is in [../client](../client) and supports:

- Uploading driver's license + insurance card front/back
- OpenAI extraction + validation
- Initiating eligibility verification from extracted data
- Displaying copay details for front desk staff
