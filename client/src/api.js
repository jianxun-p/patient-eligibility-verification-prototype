const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = data?.message || data?.detail || "Request failed";
    throw new Error(message);
  }

  return data;
}

export function extractDocuments(payload) {
  return postJson("/api/v1/documents/extract", payload);
}

export function verifyEligibility(payload) {
  return postJson("/api/v1/eligibility/verify", payload);
}

export function parse271Message(payload) {
  return postJson("/api/v1/eligibility/parse-271", payload);
}
