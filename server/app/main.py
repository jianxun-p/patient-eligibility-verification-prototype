from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    ApiError,
    DocumentExtractionRequest,
    DocumentExtractionResponse,
    EligibilityRequest,
    EligibilityResponse,
    Parse271Request,
    Parsed271SummaryResponse,
)
from .service import extract_documents_with_openai, parse_271_summary, verify_eligibility

app = FastAPI(
    title="Eligibility API Layer",
    version="1.0.0",
    description="Initiates eligibility verification and returns a simulated HIPAA 271 response.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    error = ApiError(
        error_code="VALIDATION_ERROR",
        message="Request payload failed validation",
        details=str(exc.errors()),
    )
    return JSONResponse(status_code=422, content=error.model_dump())


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    error = ApiError(
        error_code="HTTP_ERROR",
        message=str(exc.detail),
    )
    return JSONResponse(status_code=exc.status_code, content=error.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error = ApiError(
        error_code="INTERNAL_SERVER_ERROR",
        message="Unexpected server error",
    )
    return JSONResponse(status_code=500, content=error.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/eligibility/verify",
    response_model=EligibilityResponse,
    responses={
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def initiate_eligibility_verification(payload: EligibilityRequest) -> EligibilityResponse:
    try:
        return verify_eligibility(payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post(
    "/api/v1/eligibility/parse-271",
    response_model=Parsed271SummaryResponse,
    responses={
        400: {"model": ApiError},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def parse_eligibility_271(payload: Parse271Request) -> Parsed271SummaryResponse:
    try:
        return parse_271_summary(payload.raw_271)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post(
    "/api/v1/documents/extract",
    response_model=DocumentExtractionResponse,
    responses={
        400: {"model": ApiError},
        422: {"model": ApiError},
        500: {"model": ApiError},
    },
)
def extract_documents(payload: DocumentExtractionRequest) -> DocumentExtractionResponse:
    try:
        return extract_documents_with_openai(payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


app.mount("/", StaticFiles(directory="../client/dist"), name="static")

