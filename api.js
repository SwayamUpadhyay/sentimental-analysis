// Base URL for the FastAPI backend.
// Set VITE_API_BASE_URL in a .env file (local dev) or as an environment
// variable on your Render Static Site (production) to point at your
// deployed backend, e.g. https://sentimental-analysis-api.onrender.com
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });

  let payload = null;
  try {
    payload = await res.json();
  } catch {
    // no JSON body
  }

  if (!res.ok) {
    const detail = payload?.detail || res.statusText || "Request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

export const api = {
  analyze: (product) =>
    request("/analyze", { method: "POST", body: JSON.stringify({ product }) }),
  status: () => request("/status"),
  history: () => request("/history"),
  latest: () => request("/latest"),
  keywords: () => request("/keywords"),
  nextBatch: () => request("/next_batch", { method: "POST" }),
  health: () => request("/health"),
  uploadCsv: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/upload-csv", { method: "POST", body: form });
  },
};

export { BASE_URL };
