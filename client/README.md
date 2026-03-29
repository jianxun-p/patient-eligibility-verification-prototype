# Eligibility Frontend (React)

## Features

- Upload 3 images:
  - Driver's license
  - Insurance card front
  - Insurance card back
- Calls `POST /api/v1/documents/extract` for OpenAI-powered extraction
- Shows extracted fields and validation issues
- Lets staff edit extracted data
- Calls `POST /api/v1/eligibility/verify` to initiate verification
- Displays front desk copay summary and full eligibility response

## Run

```bash
cd client
cp .env.example .env
npm install
npm run dev
```

App URL:

- `http://localhost:5173`

Set backend URL if needed in `.env`:

- `VITE_API_BASE_URL=http://localhost:8000`
