import { useMemo, useState } from "react";
import { extractDocuments, parse271Message, verifyEligibility } from "./api";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function traceId() {
  return `trace-${Date.now()}`;
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Unable to read file"));
        return;
      }
      const commaIndex = result.indexOf(",");
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    };
    reader.onerror = () => reject(new Error("File read failed"));
    reader.readAsDataURL(file);
  });
}

function toEligibilityPayload(extracted, draft) {
  const dl = extracted.driver_license || {};
  const ic = extracted.insurance_card || {};

  return {
    trace_id: draft.trace_id,
    service_date: draft.service_date,
    patient: {
      dmv_id_number: draft.dmv_id_number || dl.dmv_id_number,
      document_number: draft.document_number || dl.document_number,
      date_of_birth: draft.date_of_birth || dl.date_of_birth,
      gender: draft.gender || dl.gender || "U",
      name: {
        first: draft.name_first || dl.name_first,
        last: draft.name_last || dl.name_last,
      },
      address: {
        line1: draft.address_line1 || dl.address_line1,
        city: draft.address_city || dl.address_city,
        state: draft.address_state || dl.address_state,
        postal_code: draft.address_postal_code || dl.address_postal_code,
      },
    },
    provider: {
      npi: draft.provider_npi,
      tax_id: draft.provider_tax_id,
    },
    insurance: {
      payer_id: draft.payer_id || ic.payer_id,
      payer_name: draft.payer_name || ic.payer_name,
      member_id: draft.member_id || ic.member_id,
      policy_number: draft.policy_number || ic.policy_number || `ACT-${(draft.member_id || ic.member_id || "00000").slice(0, 10)}`,
      group_number: draft.group_number || ic.group_number,
      service_type_code: draft.service_type_code,
      rx_bin: draft.rx_bin || ic.rx_bin,
      rx_pcn: draft.rx_pcn || ic.rx_pcn,
      rx_group: draft.rx_group || ic.rx_group,
      copay: {
        office: Number(draft.copay_office || ic.copay_office || 25),
        specialist: Number(draft.copay_specialist || ic.copay_specialist || 30),
        urgent_care: Number(draft.copay_urgent_care || ic.copay_urgent_care || 150),
        emergency_room: Number(draft.copay_emergency_room || ic.copay_emergency_room || 300),
      },
    },
  };
}

export default function App() {
  const [files, setFiles] = useState({
    drivers_license: null,
    insurance_front: null,
    insurance_back: null,
  });
  const [draft, setDraft] = useState({
    trace_id: traceId(),
    service_date: todayIso(),
    provider_npi: "1234567893",
    provider_tax_id: "987728123",
    service_type_code: "30",
  });
  const [extracting, setExtracting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [parsing271, setParsing271] = useState(false);
  const [error, setError] = useState("");
  const [extracted, setExtracted] = useState(null);
  const [eligibilityResult, setEligibilityResult] = useState(null);
  const [raw271, setRaw271] = useState("");
  const [parsed271, setParsed271] = useState(null);

  const canExtract = files.drivers_license && files.insurance_front && files.insurance_back;

  const frontDeskCopay = useMemo(() => {
    if (eligibilityResult?.benefits?.length) {
      const inNetwork = eligibilityResult.benefits.find((b) => b.network === "in") || eligibilityResult.benefits[0];
      const outNetwork = eligibilityResult.benefits.find((b) => b.network === "out") || eligibilityResult.benefits[0];
      return `Office: $${inNetwork.copay} | Specialist: $${outNetwork.copay}`;
    }
    if (extracted?.front_desk_copay_display) {
      return extracted.front_desk_copay_display;
    }
    return "Copay not available yet";
  }, [eligibilityResult, extracted]);

  async function handleExtract() {
    setError("");
    setEligibilityResult(null);
    setRaw271("");
    setParsed271(null);
    setExtracting(true);
    try {
      const [licenseB64, frontB64, backB64] = await Promise.all([
        fileToBase64(files.drivers_license),
        fileToBase64(files.insurance_front),
        fileToBase64(files.insurance_back),
      ]);

      const response = await extractDocuments({
        drivers_license_image: {
          image_base64: licenseB64,
          mime_type: files.drivers_license.type || "image/jpeg",
        },
        insurance_card_front_image: {
          image_base64: frontB64,
          mime_type: files.insurance_front.type || "image/jpeg",
        },
        insurance_card_back_image: {
          image_base64: backB64,
          mime_type: files.insurance_back.type || "image/jpeg",
        },
      });

      setExtracted(response);

      setDraft((previous) => ({
        ...previous,
        dmv_id_number: response.driver_license?.dmv_id_number || "",
        document_number: response.driver_license?.document_number || "",
        date_of_birth: response.driver_license?.date_of_birth || "",
        gender: response.driver_license?.gender || "U",
        name_first: response.driver_license?.name_first || "",
        name_last: response.driver_license?.name_last || "",
        address_line1: response.driver_license?.address_line1 || "",
        address_city: response.driver_license?.address_city || "",
        address_state: response.driver_license?.address_state || "",
        address_postal_code: response.driver_license?.address_postal_code || "",
        payer_id: response.insurance_card?.payer_id || "",
        payer_name: response.insurance_card?.payer_name || "",
        member_id: response.insurance_card?.member_id || "",
        policy_number: response.insurance_card?.policy_number || "",
        group_number: response.insurance_card?.group_number || "",
        rx_bin: response.insurance_card?.rx_bin || "",
        rx_pcn: response.insurance_card?.rx_pcn || "",
        rx_group: response.insurance_card?.rx_group || "",
        copay_office: response.insurance_card?.copay_office ?? "",
        copay_specialist: response.insurance_card?.copay_specialist ?? "",
        copay_urgent_care: response.insurance_card?.copay_urgent_care ?? "",
        copay_emergency_room: response.insurance_card?.copay_emergency_room ?? "",
      }));
    } catch (err) {
      setError(err.message || "Document extraction failed.");
    } finally {
      setExtracting(false);
    }
  }

  async function handleVerify() {
    if (!extracted) {
      setError("Extract document data first.");
      return;
    }

    setError("");
    setVerifying(true);
    try {
      const payload = toEligibilityPayload(extracted, draft);
      const response = await verifyEligibility(payload);
      setEligibilityResult(response);
      setRaw271(response.hipaa_271 || "");
      setParsed271(null);
    } catch (err) {
      setError(err.message || "Eligibility verification failed.");
    } finally {
      setVerifying(false);
    }
  }

  async function handleParse271() {
    if (!raw271.trim()) {
      setError("No 271 message to parse. Run verification or paste a 271 message.");
      return;
    }

    setError("");
    setParsing271(true);
    try {
      const response = await parse271Message({ raw_271: raw271 });
      setParsed271(response);
    } catch (err) {
      setError(err.message || "271 parse failed.");
    } finally {
      setParsing271(false);
    }
  }

  return (
    <div className="page-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="hero">
        <p className="eyebrow">Patient Eligibility Verification</p>
        <h1>Front Desk Intake Console</h1>
        <p className="subtitle">
          Upload a driver&apos;s license plus insurance card images, extract member data, and run live eligibility verification in one flow.
        </p>
      </header>

      <main className="grid-layout">
        <section className="card upload-card">
          <h2>1. Upload Documents</h2>
          <label>
            Driver&apos;s License
            <input type="file" accept="image/*" onChange={(e) => setFiles((s) => ({ ...s, drivers_license: e.target.files?.[0] || null }))} />
          </label>
          <label>
            Insurance Card Front
            <input type="file" accept="image/*" onChange={(e) => setFiles((s) => ({ ...s, insurance_front: e.target.files?.[0] || null }))} />
          </label>
          <label>
            Insurance Card Back
            <input type="file" accept="image/*" onChange={(e) => setFiles((s) => ({ ...s, insurance_back: e.target.files?.[0] || null }))} />
          </label>

          <button className="primary" disabled={!canExtract || extracting} onClick={handleExtract}>
            {extracting ? "Extracting..." : "Extract With OpenAI"}
          </button>

          {extracted && (
            <div className="status success">
              {extracted.is_valid ? "Extraction validated." : "Extraction has validation issues. Review before submit."}
            </div>
          )}
        </section>

        <section className="card details-card">
          <h2>2. Review and Edit</h2>
          <div className="form-grid">
            {[
              ["trace_id", "Trace ID"],
              ["service_date", "Service Date"],
              ["provider_npi", "Provider NPI"],
              ["provider_tax_id", "Provider Tax ID"],
              ["dmv_id_number", "DMV ID Number"],
              ["document_number", "Document Number"],
              ["date_of_birth", "DOB (YYYY-MM-DD)"],
              ["gender", "Gender (M/F/U)"],
              ["name_first", "First Name"],
              ["name_last", "Last Name"],
              ["address_line1", "Address Line 1"],
              ["address_city", "City"],
              ["address_state", "State"],
              ["address_postal_code", "Postal Code"],
              ["payer_id", "Payer ID"],
              ["payer_name", "Payer Name"],
              ["member_id", "Member ID"],
              ["policy_number", "Policy Number"],
              ["group_number", "Group Number"],
              ["service_type_code", "Service Type"],
              ["rx_bin", "Rx BIN"],
              ["rx_pcn", "Rx PCN"],
              ["rx_group", "Rx Group"],
              ["copay_office", "Copay Office"],
              ["copay_specialist", "Copay Specialist"],
              ["copay_urgent_care", "Copay Urgent Care"],
              ["copay_emergency_room", "Copay ER"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input value={draft[key] || ""} onChange={(e) => setDraft((s) => ({ ...s, [key]: e.target.value }))} />
              </label>
            ))}
          </div>

          <button className="primary" disabled={!extracted || verifying} onClick={handleVerify}>
            {verifying ? "Verifying..." : "Initiate Eligibility Verification"}
          </button>
        </section>

        <section className="card result-card">
          <h2>3. Results</h2>
          <div className="copay-banner">
            <p>Front Desk Copay Display</p>
            <strong>{frontDeskCopay}</strong>
          </div>

          {error && <div className="status error">{error}</div>}

          {extracted?.validation_issues?.length > 0 && (
            <div className="status warn">
              <p>Validation issues:</p>
              <ul>
                {extracted.validation_issues.map((issue, index) => (
                  <li key={`${issue.field}-${index}`}>
                    {issue.field}: {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {eligibilityResult && (
            <>
              <div className="status success">
                Coverage: {eligibilityResult.eligibility.active ? "Active" : "Inactive"}
              </div>

              <div className="section-block">
                <p className="section-title">Produced 271 Message</p>
                <textarea
                  className="edi-editor"
                  value={raw271}
                  onChange={(e) => setRaw271(e.target.value)}
                  placeholder="Generated 271 appears here. You can edit and re-parse it."
                />
                <button className="primary" onClick={handleParse271} disabled={parsing271 || !raw271.trim()}>
                  {parsing271 ? "Parsing 271..." : "Parse 271 Message"}
                </button>
              </div>

              {parsed271 && (
                <div className="section-block parsed-summary">
                  <p className="section-title">Parsed 271 Summary</p>
                  <div className="parsed-grid">
                    <p>
                      <strong>Coverage:</strong> {parsed271.coverage_status?.active === true ? "Active" : parsed271.coverage_status?.active === false ? "Inactive" : "Unknown"}
                    </p>
                    <p>
                      <strong>Status Code:</strong> {parsed271.coverage_status?.status_code || "N/A"}
                    </p>
                    <p>
                      <strong>Rx BIN:</strong> {parsed271.pharmacy_info?.rx_bin || "N/A"}
                    </p>
                    <p>
                      <strong>Rx PCN:</strong> {parsed271.pharmacy_info?.rx_pcn || "N/A"}
                    </p>
                    <p>
                      <strong>Rx Group:</strong> {parsed271.pharmacy_info?.rx_group || "N/A"}
                    </p>
                  </div>
                  <pre>{JSON.stringify(parsed271, null, 2)}</pre>
                </div>
              )}

              <pre>{JSON.stringify(eligibilityResult, null, 2)}</pre>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
