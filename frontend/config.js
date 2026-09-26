// ---------------------------------------------------------------------------
// Virtual CFO — Deployment Configuration
// ---------------------------------------------------------------------------
// This file is loaded BEFORE app.js to set the production backend URL.
//
// For LOCAL DEVELOPMENT:
//   When running on localhost or 127.0.0.1, app.js automatically routes
//   to your local FastAPI backend (http://127.0.0.1:8000).
//
// For PRODUCTION (Vercel → Render):
//   When hosted on Vercel or remote hosting, API requests are routed
//   to the production Render backend below.
// ---------------------------------------------------------------------------

const PRODUCTION_RENDER_BACKEND = "https://project2-wesp.onrender.com";

// Only override if not running on local development host
if (
  typeof window !== "undefined" &&
  window.location.hostname !== "localhost" &&
  window.location.hostname !== "127.0.0.1" &&
  window.location.hostname !== "0.0.0.0"
) {
  window.__API_BASE_URL__ = PRODUCTION_RENDER_BACKEND;
}
