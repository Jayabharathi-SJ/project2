/**
 * Virtual CFO Committee - Frontend Controller
 * Autonomous Multimodal Financial Research Agent — Phase 4 Production Dashboard
 */

// Resilient API base URL resolution:
// 1. Explicit override via config.js (window.__API_BASE_URL__)
// 2. Vercel deployment detection -> point to production Render backend
// 3. Same-origin detection (co-hosted via FastAPI /dashboard)
// 4. Local dev fallback
const API_BASE_URL = (() => {
  if (window.__API_BASE_URL__) return window.__API_BASE_URL__.replace(/\/+$/, '');
  if (typeof window !== "undefined" && window.location && window.location.hostname) {
    if (window.location.hostname.endsWith("vercel.app")) {
      return "https://project2-wesp.onrender.com";
    }
    if (window.location.origin && window.location.origin !== "null" &&
        !window.location.origin.startsWith("file:")) {
      return window.location.origin;
    }
  }
  return "http://127.0.0.1:8000";
})();

// Presets data aligned with Malaysian corporate procurement scenarios
const PRESETS = {
  sedan: {
    name: "Toyota Camry 2.5V",
    price: 120000,
    downPayment: 24000,
    hpRate: 4.5,
    hpMonths: 60,
    hpRateType: "fixed",
    leasePayment: 2100,
    leaseMonths: 60,
    cashDiscount: 3000
  },
  ev: {
    name: "BYD Atto 3 Extended",
    price: 168000,
    downPayment: 33600,
    hpRate: 3.8,
    hpMonths: 84,
    hpRateType: "fixed",
    leasePayment: 2450,
    leaseMonths: 48,
    cashDiscount: 5000
  },
  machinery: {
    name: "CNC Milling Workstation",
    price: 250000,
    downPayment: 50000,
    hpRate: 5.2,
    hpMonths: 60,
    hpRateType: "fixed",
    leasePayment: 4600,
    leaseMonths: 60,
    cashDiscount: 8000
  }
};

let currentExtractedData = null;
let currentAnalysisData = null;
let currentScheduleData = [];
let currentChartMode = "total";
let loadingStepInterval = null;
let activePresetKey = "sedan";
let isAnalysisRunning = false;

// ---------------------------------------------------------------------------
// Currency & Number Formatting Helpers
// ---------------------------------------------------------------------------

function formatRM(val) {
  if (val === null || val === undefined) return "RM 0.00";
  const num = parseFloat(val);
  if (isNaN(num)) return "RM 0.00";
  return "RM " + num.toLocaleString('en-MY', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatPercent(val) {
  if (val === null || val === undefined) return "0.00%";
  const num = parseFloat(val);
  if (isNaN(num)) return "0.00%";
  return num.toFixed(2) + "%";
}

// ---------------------------------------------------------------------------
// Navigation Controller
// ---------------------------------------------------------------------------

function toggleMobileNav() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn = document.getElementById('btn-mobile-nav');
  if (!drawer) return;
  const isOpen = drawer.classList.toggle('open');
  if (btn) {
    btn.classList.toggle('open', isOpen);
    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
}

function closeMobileNav() {
  const drawer = document.getElementById('mobile-nav-drawer');
  const btn = document.getElementById('btn-mobile-nav');
  if (drawer) drawer.classList.remove('open');
  if (btn) {
    btn.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  }
}

function initNavigation() {
  const navSections = [
    { id: 'input-section', navId: 'nav-link-params' },
    { id: 'summary-section', navId: 'nav-link-summary' },
    { id: 'visuals-section', navId: 'nav-link-visuals' },
    { id: 'deepdive-section', navId: 'nav-link-deepdive' }
  ];

  // Desktop smooth scroll on click
  navSections.forEach(item => {
    const link = document.getElementById(item.navId);
    if (link) {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.getElementById(item.id);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth' });
          document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
          link.classList.add('active');
        }
      });
    }
  });

  // Mobile nav links smooth scroll and drawer closing
  document.querySelectorAll('.mobile-nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (href && href.startsWith('#')) {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth' });
        }
        document.querySelectorAll('.mobile-nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        closeMobileNav();
      }
    });
  });

  window.addEventListener('scroll', () => {
    const scrollPos = window.scrollY + 140;
    for (let i = navSections.length - 1; i >= 0; i--) {
      const el = document.getElementById(navSections[i].id);
      if (el && el.offsetTop <= scrollPos) {
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        const activeLink = document.getElementById(navSections[i].navId);
        if (activeLink) activeLink.classList.add('active');
        break;
      }
    }
  }, { passive: true });
}

// ---------------------------------------------------------------------------
// Live Backend Health Probe
// ---------------------------------------------------------------------------

async function checkBackendHealth() {
  const badge = document.getElementById('agent-status-badge');
  if (!badge) return;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${API_BASE_URL}/health/ready`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      if (data.status === "ready") {
        badge.className = 'badge-tag pulse';
        badge.innerText = 'Connected';
      } else if (data.status === "degraded") {
        badge.className = 'badge-tag pulse connecting';
        badge.innerText = 'Degraded';
      } else {
        badge.className = 'badge-tag pulse connecting';
        badge.innerText = 'Starting';
      }
    } else if (res.status === 502 || res.status === 503) {
      badge.className = 'badge-tag pulse connecting';
      badge.innerText = 'Starting';
    } else {
      badge.className = 'badge-tag pulse offline';
      badge.innerText = 'Offline';
    }
  } catch (err) {
    badge.className = 'badge-tag pulse offline';
    badge.innerText = 'Offline';
  }
}

// ---------------------------------------------------------------------------
// Presets Loader
// ---------------------------------------------------------------------------

function loadPreset(key) {
  const preset = PRESETS[key];
  if (!preset) return;
  activePresetKey = key;

  document.querySelectorAll('.preset-chip').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`preset-${key}`);
  if (activeBtn) activeBtn.classList.add('active');

  document.getElementById('asset_name').value = preset.name;
  document.getElementById('asset_price').value = preset.price;
  document.getElementById('down_payment').value = preset.downPayment;
  document.getElementById('hp_interest_rate').value = preset.hpRate;
  document.getElementById('hp_period_months').value = preset.hpMonths;
  document.getElementById('hp_rate_type').value = preset.hpRateType || "fixed";
  document.getElementById('lease_monthly_payment').value = preset.leasePayment;
  document.getElementById('lease_period_months').value = preset.leaseMonths;
  document.getElementById('cash_discount').value = preset.cashDiscount;

  clearFieldErrors();
  executeAnalysis();
}

// ---------------------------------------------------------------------------
// Form Error Management & Reset
// ---------------------------------------------------------------------------

function clearFieldErrors() {
  document.querySelectorAll('.field-error').forEach(el => {
    el.innerText = '';
    el.classList.remove('visible');
  });
  document.querySelectorAll('.form-control').forEach(el => {
    el.classList.remove('is-invalid');
  });
}

function setFieldError(fieldId, message) {
  const input = document.getElementById(fieldId);
  const errorEl = document.getElementById('error-' + fieldId);
  if (input) input.classList.add('is-invalid');
  if (errorEl) {
    errorEl.innerText = message;
    errorEl.classList.add('visible');
  }
}

function initInputListeners() {
  const fieldIds = [
    'asset_name', 'asset_price', 'down_payment', 'hp_interest_rate',
    'hp_period_months', 'hp_rate_type', 'cash_discount',
    'lease_monthly_payment', 'lease_period_months'
  ];
  fieldIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', () => {
        el.classList.remove('is-invalid');
        const err = document.getElementById('error-' + id);
        if (err) {
          err.innerText = '';
          err.classList.remove('visible');
        }
      });
    }
  });
}

/**
 * Reset MUST actually work (Requirement 6):
 * - clear all user inputs / restore intended defaults
 * - clear uploaded PDF
 * - clear validation errors
 * - clear old analysis results
 * - clear charts
 * - clear amortization schedule
 * - clear recommendation
 * - clear audit trail
 * - allow a completely NEW analysis without stale results
 */
function resetForm() {
  clearFieldErrors();
  dismissGlobalError();
  discardExtractedValues();

  // Reset file input
  const fileInput = document.getElementById('pdf-file-input');
  if (fileInput) fileInput.value = '';

  // Restore preset form values cleanly
  const preset = PRESETS['sedan'];
  activePresetKey = 'sedan';
  document.querySelectorAll('.preset-chip').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById('preset-sedan');
  if (activeBtn) activeBtn.classList.add('active');

  document.getElementById('asset_name').value = preset.name;
  document.getElementById('asset_price').value = preset.price;
  document.getElementById('down_payment').value = preset.downPayment;
  document.getElementById('hp_interest_rate').value = preset.hpRate;
  document.getElementById('hp_period_months').value = preset.hpMonths;
  document.getElementById('hp_rate_type').value = preset.hpRateType || "fixed";
  document.getElementById('lease_monthly_payment').value = preset.leasePayment;
  document.getElementById('lease_period_months').value = preset.leaseMonths;
  document.getElementById('cash_discount').value = preset.cashDiscount;

  // Clear data models
  currentAnalysisData = null;
  currentScheduleData = [];

  // Hide rejection banner
  const rejectionBanner = document.getElementById('rejection-banner');
  if (rejectionBanner) rejectionBanner.style.display = 'none';

  // Reset KPI cards
  document.getElementById('kpi-optimal').innerText = "--";
  document.getElementById('kpi-savings').innerText = "Awaiting analysis execution";
  document.getElementById('kpi-lowest-cost').innerText = "--";
  document.getElementById('kpi-asset-overview').innerText = "Asset: Not yet evaluated";
  document.getElementById('kpi-hp-monthly').innerText = "--";
  document.getElementById('kpi-hp-interest').innerText = "Total Interest: --";
  document.getElementById('kpi-bnm-status').innerText = "--";
  document.getElementById('kpi-bnm-status').style.color = "var(--text-secondary)";
  document.getElementById('kpi-bnm-cap').innerText = "Statutory EIR & deposit check";

  // Reset recommendation banner
  document.getElementById('banner-badge').innerText = "Virtual CFO Ready";
  document.getElementById('banner-heading').innerText = "Ready for Virtual CFO Analysis";
  document.getElementById('banner-desc').innerText =
    'Configure acquisition parameters on the left or upload a quotation PDF, then click "Execute Virtual CFO Analysis" to generate deterministic financial calculations, statutory legal compliance validation, and executive recommendations.';

  // Reset option cards
  ['cash', 'hp', 'lease'].forEach(opt => {
    const card = document.getElementById(`card-${opt}`);
    const badge = document.getElementById(`badge-${opt}`);
    if (card) card.classList.remove('winner');
    if (badge) badge.style.display = 'none';
  });
  document.getElementById('cost-cash').innerText = "--";
  document.getElementById('upfront-cash').innerText = "--";
  document.getElementById('liquidity-cash').innerText = "--";
  document.getElementById('cost-hp').innerText = "--";
  document.getElementById('upfront-hp').innerText = "--";
  document.getElementById('monthly-hp').innerText = "--";
  document.getElementById('interest-hp').innerText = "--";
  document.getElementById('liquidity-hp').innerText = "--";
  document.getElementById('cost-lease').innerText = "--";
  document.getElementById('upfront-lease').innerText = "--";
  document.getElementById('monthly-lease').innerText = "--";
  document.getElementById('liquidity-lease').innerText = "--";

  // Reset chart
  const svg = document.getElementById('financial-chart-svg');
  if (svg) {
    svg.innerHTML = '<text x="380" y="130" text-anchor="middle" fill="#64748b" font-size="14">Enter parameters and execute analysis to view financial comparison</text>';
  }

  // Reset tabs
  const compList = document.getElementById('compliance-checklist');
  if (compList) {
    compList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 28px;">No legal validation executed yet. Run an analysis above to verify statutory compliance under the Malaysian Hire-Purchase Act 1967 and 2026 Regulations.</div>';
  }

  const ragContainer = document.getElementById('rag-evidence-container');
  if (ragContainer) {
    ragContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 28px;">No legal research executed yet. Run an analysis above to retrieve authoritative statutory context from the Qdrant vector store.</div>';
  }

  const amortBody = document.getElementById('amort-table-body');
  if (amortBody) {
    amortBody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">No amortization schedule available. Execute an analysis above.</td></tr>';
  }

  const auditTimeline = document.getElementById('audit-timeline');
  if (auditTimeline) {
    auditTimeline.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 28px;">No audit trail recorded. Execute an analysis above to trace the 10-stage execution pipeline.</div>';
  }

  const threadBadge = document.getElementById('thread-id-badge');
  if (threadBadge) threadBadge.innerText = 'session-standby';

  const narrative = document.getElementById('narrative-content');
  if (narrative) {
    narrative.innerHTML = '<p style="color: var(--text-muted); margin: 0;">No executive rationale generated yet. Execute an analysis to review deterministic CFO recommendations and AI synthesis.</p>';
  }

  const navLegalBadge = document.getElementById('nav-legal-badge');
  if (navLegalBadge) {
    navLegalBadge.innerText = 'Awaiting Analysis';
    navLegalBadge.className = 'badge-tag';
  }
}

// ---------------------------------------------------------------------------
// Tab Switcher
// ---------------------------------------------------------------------------

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

  const btn = document.getElementById(`tab-btn-${tabId}`);
  const pane = document.getElementById(`tab-${tabId}`);
  if (btn && pane) {
    btn.classList.add('active');
    pane.classList.add('active');
  }
}

// ---------------------------------------------------------------------------
// Chart Mode Switcher
// ---------------------------------------------------------------------------

function switchChartMode(mode) {
  currentChartMode = mode;
  document.querySelectorAll('.chart-toggle-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`btn-chart-${mode}`);
  if (activeBtn) activeBtn.classList.add('active');

  if (currentAnalysisData) {
    renderFinancialChart(currentAnalysisData);
  }
}

// ---------------------------------------------------------------------------
// Global Alert & Error Handling
// ---------------------------------------------------------------------------

function showGlobalError(title, message, showRetry = false) {
  const banner = document.getElementById('global-error-banner');
  const titleEl = document.getElementById('global-error-title');
  const msgEl = document.getElementById('global-error-message');
  const retryBtn = document.getElementById('btn-error-retry');
  if (banner && titleEl && msgEl) {
    titleEl.innerText = title;
    msgEl.innerText = message;
    if (retryBtn) retryBtn.style.display = showRetry ? 'inline-block' : 'none';
    banner.style.display = 'flex';
  }
}

function dismissGlobalError() {
  const banner = document.getElementById('global-error-banner');
  if (banner) banner.style.display = 'none';
}

function retryLastAnalysis() {
  dismissGlobalError();
  executeAnalysis();
}

// ---------------------------------------------------------------------------
// Multimodal PDF Quotation Ingestion & Traceability
// ---------------------------------------------------------------------------

function initDropzone() {
  const dropzone = document.getElementById('pdf-dropzone');
  const fileInput = document.getElementById('pdf-file-input');

  if (!dropzone || !fileInput) return;

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handlePdfUpload(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handlePdfUpload(e.target.files[0]);
    }
  });
}

async function handlePdfUpload(file) {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    showGlobalError("Invalid File Type", "Please upload a valid PDF quotation or hire-purchase agreement.");
    return;
  }

  // Client-side file size guard (10 MB maximum)
  if (file.size > 10 * 1024 * 1024) {
    showGlobalError("File Too Large", "The uploaded PDF exceeds the 10 MB limit. Please upload a smaller document.");
    return;
  }

  showLoading("Multimodal parser analyzing PDF quotation...");

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE_URL}/analyze-document`, {
      method: 'POST',
      body: formData
    });

    hideLoading();

    if (!response.ok) {
      let errMsg = "Unable to reliably extract required financial information. Please review the document or enter the values manually.";
      try {
        const err = await response.json();
        errMsg = err.detail || errMsg;
      } catch (e) {
        errMsg = `Server responded with status ${response.status}`;
      }
      showGlobalError("Document Processing Error", errMsg);
      return;
    }

    const data = await response.json();
    if (data.status === "success" && data.extraction) {
      displayExtractedParameters(data.extraction, file.name);
    } else {
      showGlobalError("Document Extraction", "Unable to reliably extract required financial information. Please review the document or enter the values manually.");
    }

  } catch (error) {
    hideLoading();
    showGlobalError("Upload Connection Error", `Failed to communicate with /analyze-document: ${error.message}`);
  }
}

function displayExtractedParameters(extraction, filename) {
  const fields = extraction.extracted_fields || {};
  const validation = extraction.validation || {};
  const docInfo = extraction.document_info || {};

  currentExtractedData = fields;
  const container = document.getElementById('extraction-items');
  const previewBox = document.getElementById('extraction-preview');
  const metaInfo = document.getElementById('doc-meta-info');

  container.innerHTML = '';
  if (metaInfo) {
    metaInfo.innerText = `${filename || 'Document'} (${docInfo.page_count || 1} page${(docInfo.page_count || 1) > 1 ? 's' : ''})`;
  }

  let fieldCount = 0;
  for (const [key, item] of Object.entries(fields)) {
    if (item && item.value !== null && item.value !== undefined) {
      fieldCount++;
      const fieldVal = validation.field_validations ? validation.field_validations[key] : null;
      const confidence = fieldVal ? fieldVal.confidence : "unverified";
      const sourcePage = item.source_page ? `Page ${item.source_page}` : "Document Stream";

      const div = document.createElement('div');
      div.className = 'extraction-item';
      div.innerHTML = `
        <div>
          <div class="extraction-key">${key.replace(/_/g, ' ')}</div>
          <div class="extraction-trace">Source: ${sourcePage} · ${confidence.toUpperCase()} CONFIDENCE</div>
        </div>
        <div class="extraction-val">
          ${key.includes('rate') ? formatPercent(item.value) : (key.includes('months') ? item.value + ' months' : (typeof item.value === 'number' || !isNaN(parseFloat(item.value)) ? formatRM(item.value) : item.value))}
        </div>
      `;
      container.appendChild(div);
    }
  }

  if (fieldCount > 0) {
    previewBox.style.display = 'block';
  } else {
    showGlobalError("Document Extraction", "Unable to reliably extract required financial information. Please review the document or enter the values manually.");
  }
}

function applyExtractedValues() {
  if (!currentExtractedData) return;

  if (currentExtractedData.asset_name && currentExtractedData.asset_name.value) {
    document.getElementById('asset_name').value = currentExtractedData.asset_name.value;
  }
  if (currentExtractedData.asset_price && currentExtractedData.asset_price.value) {
    document.getElementById('asset_price').value = parseFloat(currentExtractedData.asset_price.value);
  }
  if (currentExtractedData.down_payment && currentExtractedData.down_payment.value) {
    document.getElementById('down_payment').value = parseFloat(currentExtractedData.down_payment.value);
  }
  if (currentExtractedData.hp_interest_rate && currentExtractedData.hp_interest_rate.value) {
    document.getElementById('hp_interest_rate').value = parseFloat(currentExtractedData.hp_interest_rate.value);
  }
  if (currentExtractedData.hp_period_months && currentExtractedData.hp_period_months.value) {
    document.getElementById('hp_period_months').value = parseInt(currentExtractedData.hp_period_months.value, 10);
  }
  if (currentExtractedData.lease_monthly_payment && currentExtractedData.lease_monthly_payment.value) {
    document.getElementById('lease_monthly_payment').value = parseFloat(currentExtractedData.lease_monthly_payment.value);
  }
  if (currentExtractedData.lease_period_months && currentExtractedData.lease_period_months.value) {
    document.getElementById('lease_period_months').value = parseInt(currentExtractedData.lease_period_months.value, 10);
  }

  discardExtractedValues();
  executeAnalysis();
}

function discardExtractedValues() {
  currentExtractedData = null;
  const previewBox = document.getElementById('extraction-preview');
  if (previewBox) previewBox.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Form Submission & Analysis Execution
// ---------------------------------------------------------------------------

function handleAnalyzeSubmit(e) {
  e.preventDefault();
  executeAnalysis();
}

async function executeAnalysis() {
  if (isAnalysisRunning) return;

  dismissGlobalError();
  clearFieldErrors();

  const assetName = document.getElementById('asset_name').value.trim();
  const assetPrice = parseFloat(document.getElementById('asset_price').value);
  const downPayment = parseFloat(document.getElementById('down_payment').value);
  const hpRate = parseFloat(document.getElementById('hp_interest_rate').value);
  const hpMonths = parseInt(document.getElementById('hp_period_months').value, 10);
  const hpRateType = document.getElementById('hp_rate_type').value || "fixed";
  const leaseMonthly = parseFloat(document.getElementById('lease_monthly_payment').value);
  const leaseMonths = parseInt(document.getElementById('lease_period_months').value, 10);
  const cashDiscount = parseFloat(document.getElementById('cash_discount').value) || 0;

  let hasValidationError = false;

  // Immediate frontend validation guards
  if (!assetName) {
    setFieldError('asset_name', 'Asset description is required.');
    hasValidationError = true;
  }
  if (isNaN(assetPrice) || assetPrice <= 0) {
    setFieldError('asset_price', 'Asset price must be greater than RM 0.');
    hasValidationError = true;
  }
  if (isNaN(downPayment) || downPayment < 0) {
    setFieldError('down_payment', 'Down payment cannot be negative.');
    hasValidationError = true;
  } else if (!isNaN(assetPrice) && downPayment > assetPrice) {
    setFieldError('down_payment', 'Down payment cannot exceed the asset price.');
    hasValidationError = true;
  }
  if (isNaN(hpRate) || hpRate < 0) {
    setFieldError('hp_interest_rate', 'Interest rate cannot be negative.');
    hasValidationError = true;
  }
  if (isNaN(hpMonths) || hpMonths < 1) {
    setFieldError('hp_period_months', 'Tenure must be at least 1 month.');
    hasValidationError = true;
  }
  if (isNaN(leaseMonthly) || leaseMonthly <= 0) {
    setFieldError('lease_monthly_payment', 'Monthly lease must be greater than RM 0.');
    hasValidationError = true;
  }
  if (isNaN(leaseMonths) || leaseMonths < 1) {
    setFieldError('lease_period_months', 'Lease term must be at least 1 month.');
    hasValidationError = true;
  }
  if (isNaN(cashDiscount) || cashDiscount < 0) {
    setFieldError('cash_discount', 'Cash discount cannot be negative.');
    hasValidationError = true;
  } else if (!isNaN(assetPrice) && cashDiscount > assetPrice) {
    setFieldError('cash_discount', 'Cash discount cannot exceed the asset price.');
    hasValidationError = true;
  }

  if (hasValidationError) {
    showGlobalError("Input Validation Error", "Please review the highlighted fields before proceeding.");
    return;
  }

  isAnalysisRunning = true;
  showLoading("Virtual CFO Committee executing multi-agent analysis...");

  const payload = {
    asset_name: assetName,
    asset_price: assetPrice,
    down_payment: downPayment,
    hp_period_months: hpMonths,
    hp_interest_rate: hpRate,
    hp_rate_type: hpRateType,
    lease_period_months: leaseMonths,
    lease_monthly_payment: leaseMonthly,
    cash_discount: cashDiscount
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s for Render cold-starts

  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    isAnalysisRunning = false;
    hideLoading();

    if (!response.ok) {
      let detailMsg = `Analysis request failed with status ${response.status}.`;
      try {
        const err = await response.json();
        if (err.messages && Array.isArray(err.messages)) {
          err.messages.forEach(msg => {
            const parts = msg.split(':');
            const field = parts[0].trim();
            const reason = parts.slice(1).join(':').trim();
            if (document.getElementById(field)) {
              setFieldError(field, reason);
            }
          });
          detailMsg = err.messages.join('; ');
        } else if (err.detail) {
          if (Array.isArray(err.detail)) {
            err.detail.forEach(d => {
              const field = d.loc && d.loc[d.loc.length - 1];
              if (field && document.getElementById(field)) {
                setFieldError(field, d.msg);
              }
            });
            detailMsg = err.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') : 'error'}: ${d.msg}`).join('; ');
          } else {
            detailMsg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
          }
        }

        const lowerDetail = detailMsg.toLowerCase();
        if (lowerDetail.includes('down payment')) setFieldError('down_payment', detailMsg);
        else if (lowerDetail.includes('asset price')) setFieldError('asset_price', detailMsg);
        else if (lowerDetail.includes('cash discount')) setFieldError('cash_discount', detailMsg);
        else if (lowerDetail.includes('asset name')) setFieldError('asset_name', detailMsg);
        else if (lowerDetail.includes('interest rate') || lowerDetail.includes('eir')) setFieldError('hp_interest_rate', detailMsg);
        else if (lowerDetail.includes('period') || lowerDetail.includes('tenure')) setFieldError('hp_period_months', detailMsg);
        else if (lowerDetail.includes('monthly payment')) setFieldError('lease_monthly_payment', detailMsg);
      } catch (e) {
        // Fallback
      }
      showGlobalError("Analysis Failed", detailMsg, true);
      return;
    }

    const data = await response.json();
    if (data.status === "success" && data.analysis) {
      currentAnalysisData = data.analysis;
      const threadId = data.thread_id || (data.analysis && data.analysis.thread_id);
      if (threadId) {
        const threadBadge = document.getElementById('thread-id-badge');
        if (threadBadge) threadBadge.innerText = threadId;
      }
      renderAnalysisResults(data.analysis, payload);
    } else {
      showGlobalError("API Response Error", "Unexpected response payload from CFO backend.", true);
    }

  } catch (error) {
    clearTimeout(timeoutId);
    isAnalysisRunning = false;
    hideLoading();
    if (error.name === 'AbortError') {
      showGlobalError(
        "Request Timeout (Cold Start)",
        "The backend server is spinning up from cold-start on Render (free instances sleep when idle). Please click Retry in a few moments.",
        true
      );
    } else {
      showGlobalError(
        "Connection Error",
        `Failed to reach FastAPI backend at ${API_BASE_URL}: ${error.message}. Please ensure the backend server is running.`,
        true
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Render Backend Analysis Results (Deterministic Math & Legal Validation)
// ---------------------------------------------------------------------------

function renderAnalysisResults(analysis, input) {
  const isValidationPassed = analysis.validation_passed !== false;
  const rejectionBanner = document.getElementById('rejection-banner');
  const rejectionList = document.getElementById('rejection-list');
  const navLegalBadge = document.getElementById('nav-legal-badge');

  // Handle Legal Validation Failure State
  if (!isValidationPassed) {
    if (rejectionBanner && rejectionList) {
      rejectionList.innerHTML = '';
      const errors = analysis.validation_errors || (analysis.legal_validation && analysis.legal_validation.errors) || ["Statutory legal check failed."];
      errors.forEach(err => {
        const li = document.createElement('li');
        li.innerText = err;
        rejectionList.appendChild(li);
      });
      rejectionBanner.style.display = 'flex';
    }

    if (navLegalBadge) {
      navLegalBadge.innerText = 'BNM 2026: Non-Compliant';
      navLegalBadge.className = 'badge-tag offline';
    }

    // Update KPI & Banner to indicate blocked status
    document.getElementById('kpi-optimal').innerText = "BLOCKED";
    document.getElementById('kpi-savings').innerText = "Non-Compliant";
    document.getElementById('kpi-lowest-cost').innerText = "N/A";
    document.getElementById('kpi-hp-monthly').innerText = "N/A";
    document.getElementById('kpi-hp-interest').innerText = "N/A";
    document.getElementById('kpi-bnm-status').innerText = "FAILED";
    document.getElementById('kpi-bnm-status').style.color = "var(--accent-rose)";
    document.getElementById('kpi-bnm-cap').innerText = "Statutory violation";

    document.getElementById('banner-badge').innerText = "Committee Action Blocked";
    document.getElementById('banner-heading').innerText = "Financing proposal violates Malaysian statutory regulations";
    document.getElementById('banner-desc').innerText = (analysis.validation_errors && analysis.validation_errors.join('; ')) ||
      "Statutory compliance is a mandatory prerequisite. Please adjust the EIR rate or deposit to comply with BNM 2026 regulations.";

    // Hide winner pills
    ['cash', 'hp', 'lease'].forEach(opt => {
      const card = document.getElementById(`card-${opt}`);
      const badge = document.getElementById(`badge-${opt}`);
      if (card) card.classList.remove('winner');
      if (badge) badge.style.display = 'none';
    });

    renderComplianceTab(analysis.legal_validation || {}, input, false);
    renderAuditTrail(analysis.audit_trail || []);
    renderRagEvidence(analysis.research_findings || [], analysis.legal_rules || []);
    return;
  }

  // Legal Validation Passed: Proceed to full deterministic display
  if (rejectionBanner) rejectionBanner.style.display = 'none';

  if (navLegalBadge) {
    navLegalBadge.innerText = 'BNM 2026: Compliant';
    navLegalBadge.className = 'badge-tag pulse';
  }

  const comp = analysis.comparison || {};
  const hp = analysis.hire_purchase || {};
  const recOption = comp.recommended_option || "cash_purchase";
  const lowestCost = comp.lowest_total_cost || comp.cash_purchase_cost || 0;

  const recName = recOption === "cash_purchase"
    ? "Cash Purchase"
    : (recOption === "hire_purchase" ? "Hire Purchase" : "Operating Lease");

  // KPI updates
  document.getElementById('kpi-optimal').innerText = recName;

  const hpCost = comp.hire_purchase_cost || 0;
  const cashCost = comp.cash_purchase_cost || (input.asset_price - (input.cash_discount || 0));
  const leaseCost = comp.leasing_cost || (input.lease_monthly_payment * input.lease_period_months);

  // Compute exact deterministic savings vs next best alternative
  const otherCosts = [cashCost, hpCost, leaseCost].filter(c => Math.abs(c - lowestCost) > 0.01);
  const nextCheapest = otherCosts.length > 0 ? Math.min(...otherCosts) : lowestCost;
  const savings = Math.max(0, nextCheapest - lowestCost);
  
  if (savings > 0) {
    document.getElementById('kpi-savings').innerText = `Savings: ${formatRM(savings)} vs next best`;
  } else {
    document.getElementById('kpi-savings').innerText = `Equivalent cost across options`;
  }

  document.getElementById('kpi-lowest-cost').innerText = formatRM(lowestCost);
  document.getElementById('kpi-asset-overview').innerText = `Asset: ${input.asset_name}`;
  document.getElementById('kpi-hp-monthly').innerText = formatRM(hp.monthly_installment || 0);
  document.getElementById('kpi-hp-interest').innerText = `Total Interest: ${formatRM(hp.total_interest || 0)}`;

  document.getElementById('kpi-bnm-status').innerText = "PASSED";
  document.getElementById('kpi-bnm-status').style.color = "var(--accent-emerald)";
  document.getElementById('kpi-bnm-cap').innerText = `${formatPercent(input.hp_interest_rate)} EIR strictly compliant`;

  // Recommendation Banner
  document.getElementById('banner-badge').innerText = `Optimal Strategy: ${recName}`;
  document.getElementById('banner-heading').innerText = `${recName} delivers the lowest total lifetime outlay`;
  
  const cfoRec = analysis.cfo_recommendation || {};
  const baseDesc = cfoRec.reason || cfoRec.executive_summary ||
    `Deterministic calculations confirm ${recName} provides the most cost-effective capital allocation under Malaysian Hire-Purchase Act 2026 regulations.`;
  document.getElementById('banner-desc').innerText = `${baseDesc} (Evaluation based on lowest nominal lifetime outlay; review corporate cash reserves and tax deductions for complete operational fit.)`;

  // Comparison Option Cards
  document.getElementById('cost-cash').innerText = formatRM(cashCost);
  document.getElementById('upfront-cash').innerText = formatRM(cashCost);
  document.getElementById('liquidity-cash').innerText = formatRM(0);

  document.getElementById('cost-hp').innerText = formatRM(hpCost);
  document.getElementById('upfront-hp').innerText = formatRM(input.down_payment);
  document.getElementById('monthly-hp').innerText = formatRM(hp.monthly_installment || 0);
  document.getElementById('interest-hp').innerText = formatRM(hp.total_interest || 0);
  document.getElementById('liquidity-hp').innerText = formatRM(Math.max(0, cashCost - input.down_payment));

  document.getElementById('cost-lease').innerText = formatRM(leaseCost);
  document.getElementById('upfront-lease').innerText = formatRM(input.lease_monthly_payment);
  document.getElementById('monthly-lease').innerText = formatRM(input.lease_monthly_payment);
  document.getElementById('liquidity-lease').innerText = formatRM(Math.max(0, cashCost - input.lease_monthly_payment));

  // Winner highlighting
  ['cash', 'hp', 'lease'].forEach(opt => {
    const card = document.getElementById(`card-${opt}`);
    const badge = document.getElementById(`badge-${opt}`);
    const isWinner = (opt === 'cash' && recOption === 'cash_purchase') ||
                     (opt === 'hp' && recOption === 'hire_purchase') ||
                     (opt === 'lease' && (recOption === 'leasing' || recOption === 'lease' || recOption === 'operating_lease'));

    if (isWinner) {
      if (card) card.classList.add('winner');
      if (badge) badge.style.display = 'inline-block';
    } else {
      if (card) card.classList.remove('winner');
      if (badge) badge.style.display = 'none';
    }
  });

  // Render Visual Charts
  renderFinancialChart(analysis);

  // Render Detail Tabs
  renderComplianceTab(analysis.legal_validation || {}, input, true);
  renderRagEvidence(analysis.research_findings || [], analysis.legal_rules || []);

  const scheduleData = hp.schedule || hp.amortization_schedule || [];
  currentScheduleData = scheduleData;
  renderAmortizationSchedule(scheduleData);

  renderAuditTrail(analysis.audit_trail || []);
  renderNarrativeTab(cfoRec, recName, lowestCost);
}

// ---------------------------------------------------------------------------
// Pure SVG Interactive Financial Comparison Chart
// ---------------------------------------------------------------------------

function renderFinancialChart(analysis) {
  const svg = document.getElementById('financial-chart-svg');
  if (!svg) return;

  const comp = analysis.comparison || {};
  const hp = analysis.hire_purchase || {};
  const cashCost = comp.cash_purchase_cost || 0;
  const hpCost = comp.hire_purchase_cost || 0;
  const leaseCost = comp.leasing_cost || 0;
  const recOption = comp.recommended_option || "cash_purchase";

  svg.innerHTML = '';

  const width = 760;
  const height = 250;
  const padLeft = 70;
  const padRight = 30;
  const padTop = 30;
  const padBottom = 40;
  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  if (currentChartMode === "total") {
    // Mode 1: Total Lifetime Outlay Bar Comparison
    const maxVal = Math.max(cashCost, hpCost, leaseCost, 1000) * 1.15;
    const items = [
      { label: "Cash Purchase", val: cashCost, key: "cash_purchase", color: recOption === "cash_purchase" ? "#10b981" : "#3b82f6" },
      { label: "Hire Purchase", val: hpCost, key: "hire_purchase", color: recOption === "hire_purchase" ? "#10b981" : "#6366f1" },
      { label: "Operating Lease", val: leaseCost, key: "leasing", color: recOption === "leasing" ? "#10b981" : "#8b5cf6" }
    ];

    const barW = 120;
    const slotW = chartW / 3;

    // Gridlines
    for (let i = 0; i <= 4; i++) {
      const yVal = (maxVal / 4) * i;
      const yPos = padTop + chartH - (yVal / maxVal) * chartH;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", padLeft);
      line.setAttribute("x2", width - padRight);
      line.setAttribute("y1", yPos);
      line.setAttribute("y2", yPos);
      line.setAttribute("stroke", "rgba(255, 255, 255, 0.08)");
      line.setAttribute("stroke-dasharray", "4,4");
      svg.appendChild(line);

      const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      txt.setAttribute("x", padLeft - 10);
      txt.setAttribute("y", yPos + 4);
      txt.setAttribute("text-anchor", "end");
      txt.setAttribute("fill", "#64748b");
      txt.setAttribute("font-size", "11px");
      txt.textContent = `RM ${(yVal / 1000).toFixed(0)}k`;
      svg.appendChild(txt);
    }

    // Bars
    items.forEach((item, idx) => {
      const x = padLeft + idx * slotW + (slotW - barW) / 2;
      const barH = Math.max(0, (item.val / maxVal) * chartH);
      const y = padTop + chartH - barH;

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", barW);
      rect.setAttribute("height", barH);
      rect.setAttribute("rx", "6");
      rect.setAttribute("fill", item.color);
      rect.setAttribute("opacity", "0.9");

      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${item.label}: ${formatRM(item.val)}`;
      rect.appendChild(title);
      svg.appendChild(rect);

      // Value label on top
      const valTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      valTxt.setAttribute("x", x + barW / 2);
      valTxt.setAttribute("y", y - 8);
      valTxt.setAttribute("text-anchor", "middle");
      valTxt.setAttribute("fill", "#f8fafc");
      valTxt.setAttribute("font-weight", "700");
      valTxt.setAttribute("font-size", "12px");
      valTxt.textContent = formatRM(item.val);
      svg.appendChild(valTxt);

      // Category label below
      const catTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      catTxt.setAttribute("x", x + barW / 2);
      catTxt.setAttribute("y", height - 12);
      catTxt.setAttribute("text-anchor", "middle");
      catTxt.setAttribute("fill", item.key === recOption ? "#34d399" : "#cbd5e1");
      catTxt.setAttribute("font-weight", item.key === recOption ? "800" : "600");
      catTxt.setAttribute("font-size", "13px");
      catTxt.textContent = item.label + (item.key === recOption ? " ★" : "");
      svg.appendChild(catTxt);
    });

  } else if (currentChartMode === "breakdown") {
    // Mode 2: Stacked Structure Breakdown
    const hpInterest = Math.max(0, hp.total_interest || 0);
    const hpDeposit = Math.max(0, (analysis.comparison && analysis.comparison.upfront_outlay && typeof analysis.comparison.upfront_outlay.hire_purchase === 'number')
      ? analysis.comparison.upfront_outlay.hire_purchase
      : (parseFloat(document.getElementById('down_payment').value) || 0));
    const hpPrincipal = Math.max(0, hpCost - hpInterest - hpDeposit);
    const maxVal = Math.max(cashCost, hpCost, leaseCost, 1000) * 1.15;

    const barW = 120;
    const slotW = chartW / 3;

    // Gridlines
    for (let i = 0; i <= 4; i++) {
      const yVal = (maxVal / 4) * i;
      const yPos = padTop + chartH - (yVal / maxVal) * chartH;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", padLeft);
      line.setAttribute("x2", width - padRight);
      line.setAttribute("y1", yPos);
      line.setAttribute("y2", yPos);
      line.setAttribute("stroke", "rgba(255, 255, 255, 0.08)");
      line.setAttribute("stroke-dasharray", "4,4");
      svg.appendChild(line);

      const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      txt.setAttribute("x", padLeft - 10);
      txt.setAttribute("y", yPos + 4);
      txt.setAttribute("text-anchor", "end");
      txt.setAttribute("fill", "#64748b");
      txt.setAttribute("font-size", "11px");
      txt.textContent = `RM ${(yVal / 1000).toFixed(0)}k`;
      svg.appendChild(txt);
    }

    // HP Stacked Bar
    const hpX = padLeft + 1 * slotW + (slotW - barW) / 2;
    const hDep = Math.max(0, (hpDeposit / maxVal) * chartH);
    const hPrinc = Math.max(0, (hpPrincipal / maxVal) * chartH);
    const hInt = Math.max(0, (hpInterest / maxVal) * chartH);

    // Deposit segment
    const r1 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r1.setAttribute("x", hpX);
    r1.setAttribute("y", padTop + chartH - hDep);
    r1.setAttribute("width", barW);
    r1.setAttribute("height", hDep);
    r1.setAttribute("fill", "#3b82f6");
    const t1 = document.createElementNS("http://www.w3.org/2000/svg", "title");
    t1.textContent = `HP Down Payment: ${formatRM(hpDeposit)}`;
    r1.appendChild(t1);
    svg.appendChild(r1);

    // Principal segment
    const r2 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r2.setAttribute("x", hpX);
    r2.setAttribute("y", padTop + chartH - hDep - hPrinc);
    r2.setAttribute("width", barW);
    r2.setAttribute("height", hPrinc);
    r2.setAttribute("fill", "#6366f1");
    const t2 = document.createElementNS("http://www.w3.org/2000/svg", "title");
    t2.textContent = `HP Financed Principal: ${formatRM(hpPrincipal)}`;
    r2.appendChild(t2);
    svg.appendChild(r2);

    // Interest segment
    const r3 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r3.setAttribute("x", hpX);
    r3.setAttribute("y", padTop + chartH - hDep - hPrinc - hInt);
    r3.setAttribute("width", barW);
    r3.setAttribute("height", hInt);
    r3.setAttribute("fill", "#f59e0b");
    const t3 = document.createElementNS("http://www.w3.org/2000/svg", "title");
    t3.textContent = `HP Financing Interest: ${formatRM(hpInterest)}`;
    r3.appendChild(t3);
    svg.appendChild(r3);

    // Cash Bar
    const cashX = padLeft + (slotW - barW) / 2;
    const cashH = Math.max(0, (cashCost / maxVal) * chartH);
    const rCash = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rCash.setAttribute("x", cashX);
    rCash.setAttribute("y", padTop + chartH - cashH);
    rCash.setAttribute("width", barW);
    rCash.setAttribute("height", cashH);
    rCash.setAttribute("fill", "#10b981");
    const tCash = document.createElementNS("http://www.w3.org/2000/svg", "title");
    tCash.textContent = `Cash Purchase (Net Outlay): ${formatRM(cashCost)}`;
    rCash.appendChild(tCash);
    svg.appendChild(rCash);

    // Lease Bar
    const leaseX = padLeft + 2 * slotW + (slotW - barW) / 2;
    const leaseH = Math.max(0, (leaseCost / maxVal) * chartH);
    const rLease = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rLease.setAttribute("x", leaseX);
    rLease.setAttribute("y", padTop + chartH - leaseH);
    rLease.setAttribute("width", barW);
    rLease.setAttribute("height", leaseH);
    rLease.setAttribute("fill", "#8b5cf6");
    const tLease = document.createElementNS("http://www.w3.org/2000/svg", "title");
    tLease.textContent = `Operating Lease (Cumulative Rentals): ${formatRM(leaseCost)}`;
    rLease.appendChild(tLease);
    svg.appendChild(rLease);

    // Labels
    [
      { x: cashX, label: "Cash (Net Price)", val: cashCost },
      { x: hpX, label: "HP (Deposit + Princ. + Int.)", val: hpCost },
      { x: leaseX, label: "Lease (Cumulative Rentals)", val: leaseCost }
    ].forEach(item => {
      const catTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      catTxt.setAttribute("x", item.x + barW / 2);
      catTxt.setAttribute("y", height - 12);
      catTxt.setAttribute("text-anchor", "middle");
      catTxt.setAttribute("fill", "#cbd5e1");
      catTxt.setAttribute("font-size", "11px");
      catTxt.textContent = item.label;
      svg.appendChild(catTxt);

      const valTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      valTxt.setAttribute("x", item.x + barW / 2);
      valTxt.setAttribute("y", padTop + chartH - (item.val / maxVal) * chartH - 8);
      valTxt.setAttribute("text-anchor", "middle");
      valTxt.setAttribute("fill", "#f8fafc");
      valTxt.setAttribute("font-weight", "700");
      valTxt.setAttribute("font-size", "12px");
      valTxt.textContent = formatRM(item.val);
      svg.appendChild(valTxt);
    });

  } else if (currentChartMode === "monthly") {
    // Mode 3: Monthly Cash Outflow
    const hpInst = hp.monthly_installment || 0;
    const leaseRent = (analysis.leasing && analysis.leasing.monthly_payment)
      ? analysis.leasing.monthly_payment
      : (parseFloat(document.getElementById('lease_monthly_payment').value) || 0);
    const maxVal = Math.max(hpInst, leaseRent, 500) * 1.3;

    const barW = 120;
    const slotW = chartW / 3;

    // Gridlines
    for (let i = 0; i <= 4; i++) {
      const yVal = (maxVal / 4) * i;
      const yPos = padTop + chartH - (yVal / maxVal) * chartH;

      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", padLeft);
      line.setAttribute("x2", width - padRight);
      line.setAttribute("y1", yPos);
      line.setAttribute("y2", yPos);
      line.setAttribute("stroke", "rgba(255, 255, 255, 0.08)");
      line.setAttribute("stroke-dasharray", "4,4");
      svg.appendChild(line);

      const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      txt.setAttribute("x", padLeft - 10);
      txt.setAttribute("y", yPos + 4);
      txt.setAttribute("text-anchor", "end");
      txt.setAttribute("fill", "#64748b");
      txt.setAttribute("font-size", "11px");
      txt.textContent = `RM ${(yVal / 1000).toFixed(1)}k`;
      svg.appendChild(txt);
    }

    const items = [
      { label: "Cash Purchase", val: 0, color: "#10b981", desc: "RM 0.00 / mo" },
      { label: "Hire Purchase", val: hpInst, color: "#6366f1", desc: formatRM(hpInst) + " / mo" },
      { label: "Operating Lease", val: leaseRent, color: "#8b5cf6", desc: formatRM(leaseRent) + " / mo" }
    ];

    items.forEach((item, idx) => {
      const x = padLeft + idx * slotW + (slotW - barW) / 2;
      const barH = Math.max(0, (item.val / maxVal) * chartH);
      const y = padTop + chartH - barH;

      if (barH > 0) {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", x);
        rect.setAttribute("y", y);
        rect.setAttribute("width", barW);
        rect.setAttribute("height", barH);
        rect.setAttribute("rx", "6");
        rect.setAttribute("fill", item.color);
        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = `${item.label}: ${item.desc}`;
        rect.appendChild(title);
        svg.appendChild(rect);
      }

      const valTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      valTxt.setAttribute("x", x + barW / 2);
      valTxt.setAttribute("y", y - 8);
      valTxt.setAttribute("text-anchor", "middle");
      valTxt.setAttribute("fill", "#f8fafc");
      valTxt.setAttribute("font-weight", "700");
      valTxt.setAttribute("font-size", "12px");
      valTxt.textContent = item.desc;
      svg.appendChild(valTxt);

      const catTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      catTxt.setAttribute("x", x + barW / 2);
      catTxt.setAttribute("y", height - 12);
      catTxt.setAttribute("text-anchor", "middle");
      catTxt.setAttribute("fill", "#cbd5e1");
      catTxt.setAttribute("font-weight", "600");
      catTxt.setAttribute("font-size", "13px");
      catTxt.textContent = item.label;
    });
  }
}

// ---------------------------------------------------------------------------
// Render Detail Tabs
// ---------------------------------------------------------------------------

function renderComplianceTab(legal, input, passed) {
  const container = document.getElementById('compliance-checklist');
  if (!container) return;

  const rateType = input.hp_rate_type || 'fixed';
  // Malaysian 2026 EIR caps: variable = 17%, fixed <= 60m = 17%, fixed > 60m = 16%
  const eirCap = rateType === 'variable'
    ? 17.0
    : (input.hp_period_months <= 60 ? 17.0 : 16.0);
  const hpRate = Number(input.hp_interest_rate);
  const isEirCompliant = hpRate <= eirCap + 0.0001;
  const isEirAtCap = Math.abs(hpRate - eirCap) <= 0.0001;
  const eirRelationText = isEirAtCap ? 'is within the statutory cap' : 'is below the statutory cap';
  const minDeposit = input.asset_price * 0.10;
  const isDepositCompliant = input.down_payment >= minDeposit;

  container.innerHTML = `
    <div class="compliance-item ${isEirCompliant ? 'passed' : 'failed'}" id="compliance-item-eir">
      <svg class="compliance-icon ${isEirCompliant ? 'success' : 'failed'}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        ${isEirCompliant 
          ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
          : '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'}
      </svg>
      <div class="compliance-content">
        <h4>Statutory EIR Cap Compliance</h4>
        <p id="compliance-eir-text">
          ${isEirCompliant 
            ? `EIR of ${formatPercent(input.hp_interest_rate)} ${eirRelationText} of ${eirCap.toFixed(2)}% p.a. for a ${input.hp_period_months}-month tenure (${rateType} rate).`
            : `EIR of ${formatPercent(input.hp_interest_rate)} EXCEEDS the statutory cap of ${eirCap.toFixed(2)}% p.a. under Hire-Purchase (Term Charges) Regulations 2026.`}
        </p>
        <div class="compliance-legal-source">Source: Hire-Purchase (Term Charges) Regulations & BNM Consumer Guide 2026</div>
      </div>
    </div>

    <div class="compliance-item ${isDepositCompliant ? 'passed' : 'failed'}" id="compliance-item-deposit">
      <svg class="compliance-icon ${isDepositCompliant ? 'success' : 'failed'}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        ${isDepositCompliant
          ? '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
          : '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'}
      </svg>
      <div class="compliance-content">
        <h4>Statutory Minimum Deposit (Section 31)</h4>
        <p id="compliance-deposit-text">
          ${isDepositCompliant
            ? `Down payment of ${formatRM(input.down_payment)} satisfies the mandatory 10% statutory minimum (${formatRM(minDeposit)}) under Section 31(1) of the Malaysian Hire-Purchase Act 1967.`
            : `Down payment of ${formatRM(input.down_payment)} is BELOW the mandatory statutory 10% minimum (${formatRM(minDeposit)}) required under Section 31(1) of Act 212.`}
        </p>
        <div class="compliance-legal-source">Source: Section 31(1), Malaysian Hire-Purchase Act 1967 (Act 212)</div>
      </div>
    </div>

    <div class="compliance-item passed">
      <svg class="compliance-icon success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      <div class="compliance-content">
        <h4>Mandatory Reducing Balance Methodology Applied</h4>
        <p>Rule of 78 flat-rate methodology has been superseded by the reducing balance amortisation where interest accrues strictly on the unexpired principal.</p>
        <div class="compliance-legal-source">Source: BNM HP 2026 Core Reform (Effective 1 June 2026; grace to 31 March 2027)</div>
      </div>
    </div>

    <div class="compliance-item passed">
      <svg class="compliance-icon success" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      <div class="compliance-content">
        <h4>Early Settlement Treatment</h4>
        <p>Under the 2026 reducing-balance methodology, interest is calculated on the outstanding principal. Once the outstanding balance is fully settled, no further interest accrues. Therefore, a separate statutory rebate under the previous methodology does not arise for new agreements.</p>
        <div class="compliance-legal-source">Source: BNM Consumer Guide 2026</div>
      </div>
    </div>
  `;
}

function renderRagEvidence(findings, rules) {
  const container = document.getElementById('rag-evidence-container');
  if (!container) return;

  container.innerHTML = '';

  let evidenceList = (rules && rules.length > 0) ? rules : [];
  if (evidenceList.length === 0 && Array.isArray(findings)) {
    for (const f of findings) {
      if (f && Array.isArray(f.contexts) && f.contexts.length > 0) {
        evidenceList = f.contexts;
        break;
      }
    }
  }

  if (evidenceList.length === 0) {
    container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 28px;">No statutory evidence retrieved for this analysis.</div>';
    return;
  }

  evidenceList.forEach(rule => {
    const card = document.createElement('div');
    card.className = 'rag-card';
    const isFallback = (rule.source && rule.source.includes('fallback')) ||
                       (rule.source && rule.source.includes('legal_rules.py'));

    card.innerHTML = `
      <div class="rag-card-header">
        <span class="rag-rule-id">${rule.rule_id || 'STATUTORY PROVISION'} · ${rule.topic || 'General'}</span>
        <span class="rag-score-pill" style="${isFallback ? 'background: rgba(245, 158, 11, 0.15); color: #fbbf24; border-color: rgba(245, 158, 11, 0.3);' : ''}">
          ${isFallback ? 'Statutory Baseline Fallback' : 'Qdrant Verified Context'}
        </span>
      </div>
      <div class="rag-text">"${rule.text || rule.finding || rule.content || ''}"</div>
      <div class="rag-source-foot">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
        </svg>
        ${rule.source || 'Bank Negara Malaysia Statutory Corpus'}
      </div>
    `;
    container.appendChild(card);
  });
}

function renderAmortizationSchedule(schedule) {
  const tbody = document.getElementById('amort-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!schedule || schedule.length === 0) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">No amortization schedule available.</td>`;
    tbody.appendChild(tr);
    return;
  }

  schedule.forEach(row => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.month}</td>
      <td>${formatRM(row.opening_balance ?? row.beginning_balance ?? row.beginning ?? 0)}</td>
      <td>${formatRM(row.instalment ?? row.installment ?? row.monthly_payment ?? 0)}</td>
      <td>${formatRM(row.principal ?? row.principal_repaid ?? 0)}</td>
      <td>${formatRM(row.interest ?? row.interest_charged ?? 0)}</td>
      <td>${formatRM(row.closing_balance ?? row.ending_balance ?? row.ending ?? 0)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function exportScheduleCSV() {
  if (!currentScheduleData || currentScheduleData.length === 0) {
    showGlobalError("Export Unavailable", "No amortization schedule available to export. Run an analysis first.");
    return;
  }

  const headers = ["Month", "Opening Balance (RM)", "Instalment (RM)", "Principal Repaid (RM)", "Interest Charged (RM)", "Closing Balance (RM)"];
  const csvRows = [headers.join(",")];

  currentScheduleData.forEach(row => {
    const m = row.month;
    const b = (parseFloat(row.opening_balance ?? row.beginning_balance ?? row.beginning ?? 0) || 0).toFixed(2);
    const inst = (parseFloat(row.instalment ?? row.installment ?? row.monthly_payment ?? 0) || 0).toFixed(2);
    const p = (parseFloat(row.principal ?? row.principal_repaid ?? 0) || 0).toFixed(2);
    const i = (parseFloat(row.interest ?? row.interest_charged ?? 0) || 0).toFixed(2);
    const c = (parseFloat(row.closing_balance ?? row.ending_balance ?? row.ending ?? 0) || 0).toFixed(2);
    csvRows.push([m, b, inst, p, i, c].join(","));
  });

  const csvContent = csvRows.join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `virtual_cfo_amortization_schedule_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function renderAuditTrail(trail) {
  const container = document.getElementById('audit-timeline');
  if (!container) return;
  container.innerHTML = '';

  const items = (trail && trail.length > 0) ? trail : [];

  if (items.length === 0) {
    container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 28px;">No audit trail recorded for this session.</div>';
    return;
  }

  items.forEach((item, idx) => {
    const node = document.createElement('div');
    node.className = 'audit-node';
    const isError = item.action && (item.action.includes('failed') || item.action.includes('error'));

    node.innerHTML = `
      <div class="audit-icon" style="${isError ? 'background: rgba(244,63,94,0.2); color: #fb7185; border-color: rgba(244,63,94,0.4);' : ''}">
        ${isError ? '✕' : (idx + 1)}
      </div>
      <div class="audit-card">
        <div class="audit-agent-name">${item.agent ? item.agent.replace(/_/g, ' ').toUpperCase() : 'AGENT'} — ${item.action ? item.action.replace(/_/g, ' ') : 'Executed'}</div>
        <div class="audit-detail">${item.note || item.detail || (item.errors ? item.errors.join('; ') : JSON.stringify(item))}</div>
      </div>
    `;
    container.appendChild(node);
  });
}

function renderNarrativeTab(cfoRec, recName, lowestCost) {
  const content = document.getElementById('narrative-content');
  if (!content) return;

  const rationaleText = cfoRec.reason || cfoRec.executive_summary ||
    `Based on deterministic evaluation, ${recName} incurs the lowest aggregate outlay of ${formatRM(lowestCost)}.`;

  content.innerHTML = `
    <div style="margin-bottom: 14px;">
      <span class="engine-tag llm">AI Executive Synthesis (NVIDIA Grounded)</span>
    </div>
    <h4 style="margin-bottom: 8px; color: #a5b4fc; font-size: 1rem;">CFO Recommendation Rationale</h4>
    <p style="margin-bottom: 16px; color: #f1f5f9;">${rationaleText}</p>

    <h4 style="margin-bottom: 8px; color: #a5b4fc; font-size: 1rem;">Statutory Framework Note</h4>
    <p style="margin-bottom: 14px;">
      Under Bank Negara Malaysia's Hire-Purchase (Amendment) Act 2026, the Hire-Purchase financing scenario in this analysis uses the Reducing Balance / Effective Interest Rate (EIR) methodology. Cash Purchase and Operating Lease are evaluated using their respective deterministic cost calculations.
    </p>

    <div style="padding: 12px 14px; background: rgba(59, 130, 246, 0.08); border-left: 3px solid var(--accent-blue); border-radius: 4px; font-size: 0.8rem; color: #bfdbfe;">
      <strong>Deterministic Guarantee:</strong> The financial ranking and cost values above are computed by deterministic Python calculation tools. The LLM narrative provides executive explanation only and cannot override calculation results.
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Loading UI Controls
// ---------------------------------------------------------------------------

function showLoading(msg) {
  const overlay = document.getElementById('loading-overlay');
  const text = document.getElementById('loading-text');
  if (text) text.innerText = msg;
  if (overlay) overlay.style.display = 'flex';

  const bullets = document.querySelectorAll('.step-bullet');
  let currentStep = 0;
  if (loadingStepInterval) clearInterval(loadingStepInterval);

  bullets.forEach((b, i) => {
    if (i === 0) b.classList.add('active');
    else b.classList.remove('active');
  });

  loadingStepInterval = setInterval(() => {
    currentStep = (currentStep + 1) % bullets.length;
    bullets.forEach((b, i) => {
      if (i === currentStep) b.classList.add('active');
      else b.classList.remove('active');
    });
  }, 1200);

  const submitBtn = document.getElementById('btn-submit-analyze');
  const resetBtn = document.getElementById('btn-reset-form');
  if (submitBtn) submitBtn.disabled = true;
  if (resetBtn) resetBtn.disabled = true;
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.style.display = 'none';

  if (loadingStepInterval) {
    clearInterval(loadingStepInterval);
    loadingStepInterval = null;
  }

  const submitBtn = document.getElementById('btn-submit-analyze');
  const resetBtn = document.getElementById('btn-reset-form');
  if (submitBtn) submitBtn.disabled = false;
  if (resetBtn) resetBtn.disabled = false;
}

// ---------------------------------------------------------------------------
// Initialization on DOM Load
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initInputListeners();
  initDropzone();
  checkBackendHealth();
  setInterval(checkBackendHealth, 20000);
  // Automatically execute default analysis against live FastAPI backend
  executeAnalysis();
});
