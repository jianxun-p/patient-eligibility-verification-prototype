# Patient Eligibility Verification Prototype

An end-to-end prototype for front-desk insurance eligibility checks.

This project combines:
- A React intake console for uploading ID/insurance images, reviewing extracted data, and running eligibility verification.
- A FastAPI backend that performs document extraction, simulates eligibility verification, generates a HIPAA-style 271 message, and parses 271 content into a front-desk-friendly summary.

## What This Prototype Demonstrates

- Document intake for three images:
	- Driver's license
	- Insurance card front
	- Insurance card back
- AI-assisted extraction of patient/insurance fields from uploaded images
- Validation feedback for extracted fields before eligibility submission
- Eligibility verification request orchestration
- Generated HIPAA 271 response payload display
- Editable 271 message in UI
- Server-side parsing of edited 271 text
- Parsed coverage/copay/pharmacy summary for front desk staff

## Repository Structure

```text
patient-eligibility-verification-prototype/
	client/                  # React + Vite frontend
	server/                  # FastAPI backend
		app/
			main.py              # API routes + error handling + static mount
			models.py            # Pydantic request/response models
			service.py           # Core extraction/verification/parsing logic
		tests/
			test.http            # Sample HTTP requests
```

## Architecture

```text
React Frontend (client)
	-> POST /api/v1/documents/extract
	<- extracted data + validation issues
	-> POST /api/v1/eligibility/verify
	<- eligibility + generated hipaa_271
	-> POST /api/v1/eligibility/parse-271 (editable raw_271)
	<- parsed summary
```

*Note: This is a demonstration prototype and not intended for production use. Due to the unfamiliarity with the subject matter (insurance systems in the United States), some assumptions and simplifications have been made.*

## Design Decisions and Tradeoffs

Since this is a demonstration prototype, several design decisions were made to balance realism with development speed:

- **AI-Assisted Extraction**: We use OpenAI's API to extract structured data from unstructured images. This allows us to demonstrate the potential of AI in document processing without building custom OCR and extraction rules.
- **Simulated Eligibility Logic**: The eligibility verification step simulates payer responses based on extracted data patterns rather than integrating with real payer APIs. This allows us to demonstrate the end-to-end flow without the complexity of real EDI transactions.
- **Simplified 271 Generation/Parsing**: The generated 271 message is a minimal, non-standards-compliant string that includes key fields for demonstration. The parsing logic looks for specific patterns rather than implementing a full X12 parser.
- **No Authentication or Authorization**: The API endpoints are open without auth for simplicity. In production, secure auth and role-based access controls would be essential.
- **Direct Frontend-Backend Coupling**: The frontend directly calls backend endpoints without an API gateway or service mesh. This is suitable for a prototype but may not scale well in a microservices architecture.

## Notes and Limitations

- Eligibility logic is simulated for prototype use.
- 271 generation and parsing are intentionally simplified and not a full standards-compliant implementation.
- Production use should include secure secret handling, auth, audit logging, robust EDI validation, and compliance controls.

## Prerequisites

- Node.js 18+
- Python 3.10+
- pip
- OpenAI API key (required for document extraction)

## Local Development

### 1. Start Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
# Optional:
# export OPENAI_MODEL="gpt-4.1-mini"
uvicorn app.main:app --reload --port 8000
```

Backend URLs:
- API root: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 2. Start Frontend

```bash
cd client
npm install
npm run dev
```

Frontend URL:
- http://localhost:5173

Optional frontend env:
- VITE_API_BASE_URL (defaults to http://localhost:8000)

Example:

```bash
cd client
echo 'VITE_API_BASE_URL="http://localhost:8000"' > .env
```

## Production-Like Local Run

The backend mounts frontend static assets from client/dist. To test that flow:

```bash
cd client
npm install
npm run build

cd ../server
source .venv/bin/activate
# ensure the env variable is set so the backend can call OpenAI for document extraction
# export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
uvicorn app.main:app --port 8000
```

Then open [http://localhost:8000/index.html](http://localhost:8000/index.html).

## API Endpoints

### POST /api/v1/documents/extract

Extracts fields from 3 base64-encoded images.

Request body:

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

Returns extracted driver license + insurance fields, validation issues, and a front desk copay display string.

### POST /api/v1/eligibility/verify

Accepts normalized patient/provider/insurance data and returns:
- Eligibility status
- Benefit list
- Generated raw HIPAA-style 271 message as hipaa_271

### POST /api/v1/eligibility/parse-271

Parses raw 271 text and returns:
- coverage_status
- copayment_amounts
- pharmacy_info
- front_desk_display

Request body:

```json
{
	"raw_271": "ISA*00*...~\nGS*HB*...~\nST*271*...~"
}
```

## Frontend Workflow

1. Upload driver license + insurance front/back.
2. Click Extract With OpenAI.
3. Review and edit extracted values.
4. Click Initiate Eligibility Verification.
5. In Results:
	 - See coverage and raw generated 271.
	 - Edit 271 text if needed.
	 - Click Parse 271 Message.
	 - Review parsed summary and JSON output.

## Dependency Summary

Backend:
- fastapi
- uvicorn
- pydantic
- openai
- pytest

Frontend:
- react
- react-dom
- vite
- @vitejs/plugin-react

## License

No license file is currently included in this repository.
