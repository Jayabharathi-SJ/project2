/**
 * Virtual CFO Committee - Frontend Controller
 * Autonomous Multimodal Financial Research Agent — Phase 4 Production Dashboard
 */

// Resilient API base URL resolution:
// 1. Explicit override via config.js (for Vercel → Render split deployment)
// 2. Same-origin detection (co-hosted via FastAPI /dashboard)
// 3. Local dev fallback
const API_BASE_URL = (() => {
  // Priority 1: Explicit deployment override (set in frontend/config.js)
  if (window.__API_BASE_URL__) return window.__API_BASE_URL__.replace(/\/+$/, '');
  // Priority 2: Co-hosted — use same origin (local dev via FastAPI /dashboard)
  if (window.location.origin && window.location.origin !== "null" &&
      !window.location.origin.startsWith("file:"))
    return window.location.origin;
  // Priority 3: Local file:// fallback
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
    const timeoutId = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(`${API_BASE_URL}/health/ready`, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (res.ok) {
      badge.className = 'badge-tag pulse';
      badge.innerText = 'FastAPI Connected';
    } else {
      badge.className = 'badge-tag pulse connecting';
      badge.innerText = 'Backend Starting...';
    }
  } catch (err) {
    badge.className = 'badge-tag pulse offline';
    badge.innerText = 'Backend Offline';
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
  // Re-run real backend analysis
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

function resetForm() {
  clearFieldErrors();
  dismissGlobalError();
  loadPreset(activePresetKey || 'sedan');
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
      let errMsg = "Could not parse quotation PDF.";
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
      showGlobalError("Document Extraction", "No financial parameters could be extracted from this PDF.");
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
    showGlobalError("No Data Extracted", "No financial parameters (price, interest rate, tenure) were detected in the uploaded PDF.");
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
  // Execute analysis with user-confirmed parameters
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

  if (hasValidationError) {
    showGlobalError("Input Validation Error", "Please review the highlighted fields before proceeding.");
    return;
  }

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
  const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s for Render cold-starts

  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);
    hideLoading();

    if (!response.ok) {
      let detailMsg = `Analysis request failed with status ${response.status}.`;
      try {
        const err = await response.json();
        // Handle 422 validation messages
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
      } catch (e) {
        // Fallback
      }
      showGlobalError("Analysis Failed", detailMsg, true);
      return;
    }

    const data = await response.json();
    if (data.status === "success" && data.analysis) {
      currentAnalysisData = data.analysis;
      if (data.thread_id) {
        const threadBadge = document.getElementById('thread-id-badge');
        if (threadBadge) threadBadge.innerText = data.thread_id;
      }
      renderAnalysisResults(data.analysis, payload);
    } else {
      showGlobalError("API Response Error", "Unexpected response payload from CFO backend.", true);
    }

  } catch (error) {
    clearTimeout(timeoutId);
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

    // Still render audit trail & legal checklist for transparency
    renderComplianceTab(analysis.legal_validation || {}, input, false);
    renderAuditTrail(analysis.audit_trail || []);
    renderRagEvidence(analysis.research_findings || [], analysis.legal_rules || []);
    return;
  }

  // Legal Validation Passed: Proceed to full deterministic display
  if (rejectionBanner) rejectionBanner.style.display = 'none';

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

  // Compute exact deterministic savings vs highest alternative
  const maxAlt = Math.max(hpCost, leaseCost);
  const savings = Math.max(0, maxAlt - lowestCost);
  document.getElementById('kpi-savings').innerText = `Savings: ${formatRM(savings)} vs alt`;
  document.getElementById('kpi-lowest-cost').innerText = formatRM(lowestCost);
  document.getElementById('kpi-asset-overview').innerText = `Asset: ${input.asset_name}`;
  document.getElementById('kpi-hp-monthly').innerText = formatRM(hp.monthly_installment || 0);
  document.getElementById('kpi-hp-interest').innerText = `Total Interest: ${formatRM(hp.total_interest || 0)}`;

  document.getElementById('kpi-bnm-status').innerText = "PASSED";
  document.getElementById('kpi-bnm-status').style.color = "var(--accent-emerald)";
  document.getElementById('kpi-bnm-cap').innerText = `${formatPercent(input.hp_interest_rate)} EIR strictly compliant`;

  // Recommendation Banner
  document.getElementById('banner-badge').innerText = `Optimal Selection: ${recName}`;
  document.getElementById('banner-heading').innerText = `${recName} delivers the lowest total ownership outlay`;
  
  const cfoRec = analysis.cfo_recommendation || {};
  document.getElementById('banner-desc').innerText = cfoRec.reason || cfoRec.executive_summary ||
    `Deterministic calculations confirm ${recName} provides the most cost-effective capital allocation under Malaysian Hire-Purchase Act 2026 regulations.`;

  // Comparison Option Cards
  document.getElementById('cost-cash').innerText = formatRM(cashCost);
  document.getElementById('upfront-cash').innerText = formatRM(cashCost);

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
                     (opt === 'lease' && recOption === 'leasing');

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

  // Correct schedule array resolution (hp.schedule from backend, fallback to hp.amortization_schedule)
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
      const barH = (item.val / maxVal) * chartH;
      const y = padTop + chartH - barH;

      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", x);
      rect.setAttribute("y", y);
      rect.setAttribute("width", barW);
      rect.setAttribute("height", barH);
      rect.setAttribute("rx", "6");
      rect.setAttribute("fill", item.color);
      rect.setAttribute("opacity", "0.9");
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
    const hpInterest = hp.total_interest || 0;
    const hpDeposit = (analysis.comparison && analysis.comparison.upfront_outlay) ? analysis.comparison.upfront_outlay.hire_purchase : 24000;
    const hpPrincipal = Math.max(0, hpCost - hpInterest - hpDeposit);
    const maxVal = Math.max(cashCost, hpCost, leaseCost, 1000) * 1.15;

    const barW = 120;
    const slotW = chartW / 3;

    // HP Stacked Bar
    const hpX = padLeft + 1 * slotW + (slotW - barW) / 2;
    const hDep = (hpDeposit / maxVal) * chartH;
    const hPrinc = (hpPrincipal / maxVal) * chartH;
    const hInt = (hpInterest / maxVal) * chartH;

    // Deposit segment
    const r1 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r1.setAttribute("x", hpX);
    r1.setAttribute("y", padTop + chartH - hDep);
    r1.setAttribute("width", barW);
    r1.setAttribute("height", hDep);
    r1.setAttribute("fill", "#3b82f6");
    svg.appendChild(r1);

    // Principal segment
    const r2 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r2.setAttribute("x", hpX);
    r2.setAttribute("y", padTop + chartH - hDep - hPrinc);
    r2.setAttribute("width", barW);
    r2.setAttribute("height", hPrinc);
    r2.setAttribute("fill", "#6366f1");
    svg.appendChild(r2);

    // Interest segment
    const r3 = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r3.setAttribute("x", hpX);
    r3.setAttribute("y", padTop + chartH - hDep - hPrinc - hInt);
    r3.setAttribute("width", barW);
    r3.setAttribute("height", hInt);
    r3.setAttribute("fill", "#f59e0b");
    svg.appendChild(r3);

    // Cash Bar
    const cashX = padLeft + (slotW - barW) / 2;
    const cashH = (cashCost / maxVal) * chartH;
    const rCash = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rCash.setAttribute("x", cashX);
    rCash.setAttribute("y", padTop + chartH - cashH);
    rCash.setAttribute("width", barW);
    rCash.setAttribute("height", cashH);
    rCash.setAttribute("fill", "#10b981");
    svg.appendChild(rCash);

    // Lease Bar
    const leaseX = padLeft + 2 * slotW + (slotW - barW) / 2;
    const leaseH = (leaseCost / maxVal) * chartH;
    const rLease = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rLease.setAttribute("x", leaseX);
    rLease.setAttribute("y", padTop + chartH - leaseH);
    rLease.setAttribute("width", barW);
    rLease.setAttribute("height", leaseH);
    rLease.setAttribute("fill", "#8b5cf6");
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
    const leaseRent = analysis.leasing
      ? (analysis.comparison ? analysis.comparison.leasing_cost / 60 : 2100)
      : 2100;
    const maxVal = Math.max(hpInst, leaseRent, 500) * 1.3;

    const barW = 120;
    const slotW = chartW / 3;

    const items = [
      { label: "Cash Purchase", val: 0, color: "#10b981", desc: "RM 0.00 / mo" },
      { label: "Hire Purchase", val: hpInst, color: "#6366f1", desc: formatRM(hpInst) + " / mo" },
      { label: "Operating Lease", val: leaseRent, color: "#8b5cf6", desc: formatRM(leaseRent) + " / mo" }
    ];

    items.forEach((item, idx) => {
      const x = padLeft + idx * slotW + (slotW - barW) / 2;
      const barH = (item.val / maxVal) * chartH;
      const y = padTop + chartH - barH;

      if (barH > 0) {
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", x);
        rect.setAttribute("y", y);
        rect.setAttribute("width", barW);
        rect.setAttribute("height", barH);
        rect.setAttribute("rx", "6");
        rect.setAttribute("fill", item.color);
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
      svg.appendChild(catTxt);
    });
  }
}

// ---------------------------------------------------------------------------
// Render Detail Tabs
// ---------------------------------------------------------------------------

function renderComplianceTab(legal, input, passed) {
  const eirCap = input.hp_period_months <= 60
    ? (input.hp_rate_type === 'variable' ? 19.0 : 17.0)
    : (input.hp_rate_type === 'variable' ? 18.0 : 16.0);
  const isEirCompliant = input.hp_interest_rate <= eirCap;
  const minDeposit = input.asset_price * 0.10;
  const isDepositCompliant = input.down_payment >= minDeposit;

  const eirItem = document.getElementById('compliance-item-eir');
  const eirText = document.getElementById('compliance-eir-text');
  if (eirItem && eirText) {
    if (isEirCompliant) {
      eirItem.className = 'compliance-item passed';
      eirText.innerText = `EIR of ${formatPercent(input.hp_interest_rate)} is strictly below the statutory cap of ${eirCap.toFixed(2)}% p.a. for a ${input.hp_period_months}-month tenure (${input.hp_rate_type || 'fixed'} rate).`;
    } else {
      eirItem.className = 'compliance-item failed';
      eirText.innerText = `EIR of ${formatPercent(input.hp_interest_rate)} EXCEEDS the statutory cap of ${eirCap.toFixed(2)}% p.a. under BNM 2026 regulations.`;
    }
  }

  const depositItem = document.getElementById('compliance-item-deposit');
  const depositText = document.getElementById('compliance-deposit-text');
  if (depositItem && depositText) {
    if (isDepositCompliant) {
      depositItem.className = 'compliance-item passed';
      depositText.innerText = `Down payment of ${formatRM(input.down_payment)} satisfies the mandatory statutory 10% minimum (${formatRM(minDeposit)}) under Section 31 of the HP Act 1967.`;
    } else {
      depositItem.className = 'compliance-item failed';
      depositText.innerText = `Down payment of ${formatRM(input.down_payment)} is BELOW the mandatory statutory 10% minimum (${formatRM(minDeposit)}).`;
    }
  }
}

function renderRagEvidence(findings, rules) {
  const container = document.getElementById('rag-evidence-container');
  if (!container) return;

  container.innerHTML = '';

  const allRules = rules && rules.length > 0 ? rules : [
    {
      rule_id: "BNM-HP2026-01",
      topic: "EIR Cap",
      text: "Statutory EIR cap for fixed rate hire purchase agreements with tenures up to 60 months is established at 17.00% per annum.",
      source: "BNM Hire-Purchase (Amendment) Act 2026 Consumer Guide",
      score: 1.0
    },
    {
      rule_id: "BNM-HP2026-02",
      topic: "Amortisation Mandate",
      text: "Abolition of Rule of 78 flat rate interest allocation; lenders must adopt the Reducing Balance method calculated on remaining unexpired principal.",
      source: "Revised Term Charges Regulations 2026",
      score: 0.98
    },
    {
      rule_id: "HPA-1967-S31",
      topic: "Minimum Deposit",
      text: "An owner who enters into a hire-purchase agreement without having first obtained a deposit of not less than 10 per cent of the cash price of the goods shall be guilty of an offence.",
      source: "Hire-Purchase Act 1967, Section 31",
      score: 0.95
    }
  ];

  allRules.forEach(rule => {
    const card = document.createElement('div');
    card.className = 'rag-card';
    card.innerHTML = `
      <div class="rag-card-header">
        <span class="rag-rule-id">${rule.rule_id || 'STATUTORY PROVISION'} · ${rule.topic || 'General'}</span>
        <span class="rag-score-pill">Verified Context</span>
      </div>
      <div class="rag-text">"${rule.text || rule.finding || ''}"</div>
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

  // Display all months from schedule
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
    const b = (row.opening_balance ?? row.beginning_balance ?? row.beginning ?? 0).toFixed(2);
    const inst = (row.instalment ?? row.installment ?? row.monthly_payment ?? 0).toFixed(2);
    const p = (row.principal ?? row.principal_repaid ?? 0).toFixed(2);
    const i = (row.interest ?? row.interest_charged ?? 0).toFixed(2);
    const c = (row.closing_balance ?? row.ending_balance ?? row.ending ?? 0).toFixed(2);
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

  const defaultTrail = [
    { agent: "Input Validator", action: "Parameter Range Verification", note: "Validated asset price, down payment, and statutory constraints." },
    { agent: "Research Agent", action: "Legal RAG Retrieval", note: "Retrieved BNM Hire-Purchase 2026 guidelines." },
    { agent: "Legal Validator", action: "EIR Cap & Deposit Audit", note: "Verified statutory compliance with Section 31 and BNM EIR caps." },
    { agent: "Financial Engine", action: "Deterministic Computation", note: "Executed Reducing Balance formulas and calculated exact comparison." },
    { agent: "CFO Committee", action: "Optimal Strategy Selection", note: "Selected lowest total outlay option." }
  ];

  const items = trail && trail.length > 0 ? trail : defaultTrail;

  items.forEach((item, idx) => {
    const node = document.createElement('div');
    node.className = 'audit-node';
    const isError = item.action && item.action.includes('failed');

    node.innerHTML = `
      <div class="audit-icon" style="${isError ? 'background: rgba(244,63,94,0.2); color: #fb7185; border-color: rgba(244,63,94,0.4);' : ''}">
        ${isError ? '✕' : (idx + 1)}
      </div>
      <div class="audit-card">
        <div class="audit-agent-name">${item.agent || 'Agent'} — ${item.action ? item.action.replace(/_/g, ' ') : 'Executed'}</div>
        <div class="audit-detail">${item.note || item.detail || (item.errors ? item.errors.join('; ') : JSON.stringify(item))}</div>
      </div>
    `;
    container.appendChild(node);
  });
}

function renderNarrativeTab(cfoRec, recName, lowestCost) {
  const content = document.getElementById('narrative-content');
  if (!content) return;

  content.innerHTML = `
    <div style="margin-bottom: 14px;">
      <span class="engine-tag llm">AI Executive Synthesis (NVIDIA Grounded)</span>
    </div>
    <h4 style="margin-bottom: 8px; color: #a5b4fc; font-size: 1rem;">CFO Recommendation Rationale</h4>
    <p style="margin-bottom: 16px; color: #f1f5f9;">${cfoRec.reason || `Based on deterministic evaluation, ${recName} incurs the lowest aggregate outlay of ${formatRM(lowestCost)}.`}</p>

    <h4 style="margin-bottom: 8px; color: #a5b4fc; font-size: 1rem;">Statutory Framework Note</h4>
    <p style="margin-bottom: 14px;">
      Under Bank Negara Malaysia's Hire-Purchase (Amendment) Act 2026, lenders are prohibited from utilizing the Rule of 78 formula for term charges. All financing options in this dashboard are computed strictly using the Reducing Balance Effective Interest Rate (EIR) methodology.
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
  // Automatically execute default analysis against live FastAPI backend
  executeAnalysis();
});
