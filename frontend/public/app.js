const { createElement: h, useEffect, useState } = React;

const API_BASE = '/api';

function parseList(value) {
  return value.split(',').map((item) => item.trim()).filter(Boolean);
}

function fmt(value) {
  if (!value) return 'N/A';
  return new Date(value).toLocaleString();
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

const api = {
  dashboard: () => request('/dashboard'),
  plans: () => request('/plans'),
  createPlan: (payload) => request('/plans', { method: 'POST', body: JSON.stringify(payload) }),
  vehicles: () => request('/vehicles'),
  createVehicle: (payload) => request('/vehicles', { method: 'POST', body: JSON.stringify(payload) }),
  runs: () => request('/runs'),
  createRun: (payload) => request('/runs', { method: 'POST', body: JSON.stringify(payload) }),
  issues: () => request('/issues'),
  createIssue: (payload) => request('/issues', { method: 'POST', body: JSON.stringify(payload) }),
  files: () => request('/files'),
  uploadFile: async (runId, file) => {
    const fd = new FormData();
    fd.append('run_id', String(runId));
    fd.append('file', file);
    const response = await fetch(`${API_BASE}/files/upload`, { method: 'POST', body: fd });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || 'Upload failed');
    }
    return response.json();
  },
  testCases: () => request('/test-cases'),
  createTestCase: (payload) => request('/test-cases', { method: 'POST', body: JSON.stringify(payload) }),
  caseResults: () => request('/test-case-results'),
  createCaseResult: (payload) => request('/test-case-results', { method: 'POST', body: JSON.stringify(payload) }),
};

function Section(title, children) {
  return h('section', { className: 'panel' }, h('h2', null, title), children);
}

function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dashboard, setDashboard] = useState(null);
  const [plans, setPlans] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [runs, setRuns] = useState([]);
  const [issues, setIssues] = useState([]);
  const [files, setFiles] = useState([]);
  const [testCases, setTestCases] = useState([]);
  const [caseResults, setCaseResults] = useState([]);

  const [planForm, setPlanForm] = useState({ title: '', vehicle_platform: '', objective: '', owner: '', route: 'Proving Grounds' });
  const [runForm, setRunForm] = useState({ title: '', plan_id: '', vehicle_id: '', route: '', flash_version: '', status: 'Queued', logger_health: 'Healthy' });
  const [vehicleForm, setVehicleForm] = useState({ vehicle_label: '', vin: '', platform: '', logger_model: '', flash_version: '', sensor_stack: '', instrumentation: '' });
  const [issueForm, setIssueForm] = useState({ run_id: '', severity: 'Medium', category: '', title: '', detail: '' });
  const [caseForm, setCaseForm] = useState({ plan_id: '', case_id: '', title: '', objective: '', subsystem: '', expected_result: '', severity: 'Medium', tags: '' });
  const [resultForm, setResultForm] = useState({ run_id: '', test_case_id: '', verdict: 'Passed', anomaly: '', missing_data: '', notes: '' });
  const [uploadRunId, setUploadRunId] = useState('');
  const [uploadFile, setUploadFile] = useState(null);

  async function refresh() {
    const [d, p, v, r, i, f, tc, cr] = await Promise.all([
      api.dashboard(), api.plans(), api.vehicles(), api.runs(), api.issues(), api.files(), api.testCases(), api.caseResults(),
    ]);
    setDashboard(d);
    setPlans(p);
    setVehicles(v);
    setRuns(r);
    setIssues(i);
    setFiles(f);
    setTestCases(tc);
    setCaseResults(cr);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  async function submit(action, reset) {
    setError('');
    try {
      await action();
      reset();
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  if (loading) return h('div', { className: 'loading-screen' }, 'Loading ADAS TestOps Platform...');

  const metrics = dashboard?.metrics || [];
  const recentRuns = dashboard?.recent_runs || [];

  return h(
    'div',
    { className: 'app-shell' },
    h('div', { className: 'ambient ambient-a' }),
    h('div', { className: 'ambient ambient-b' }),
    h('header', { className: 'hero panel' },
      h('div', { className: 'hero-copy' },
        h('span', { className: 'eyebrow' }, 'ADAS validation ops'),
        h('h1', null, 'Plan, run, and review ADAS sessions with test-case traceability.'),
        h('p', null, 'Manage plans, runs, vehicle instrumentation, logger health, case execution, anomalies, and captured files in one place.'),
      ),
      h('div', { className: 'hero-status' },
        h('div', { className: 'status-ring' }, h('span', null, metrics[0]?.value || '0%'), h('small', null, metrics[0]?.label || 'pass rate')),
      ),
    ),
    error ? h('div', { className: 'error-banner' }, error) : null,
    h('section', { className: 'metric-grid' }, metrics.map((m) => h('article', { className: 'metric-card', key: m.label }, h('span', { className: 'metric-label' }, m.label), h('strong', { className: 'metric-value' }, m.value), h('p', null, m.detail)))),

    h('section', { className: 'summary-grid' },
      Section('Recent Runs', h('div', { className: 'stack-list' }, recentRuns.slice(0, 6).map((run) => h('article', { className: 'stack-card', key: run.id }, h('strong', null, run.title), h('small', null, `${run.status} · ${run.coverage_pct}% coverage · ${run.logger_health}`))))),
      Section('Test Cases', h('div', { className: 'stack-list' }, testCases.slice(0, 6).map((c) => h('article', { className: 'stack-card', key: c.id }, h('strong', null, `${c.case_id} - ${c.title}`), h('small', null, `${c.subsystem} · ${c.severity}`), h('small', null, c.expected_result))))),
      Section('Case Results', h('div', { className: 'stack-list' }, caseResults.slice(0, 6).map((r) => h('article', { className: 'stack-card', key: r.id }, h('strong', null, `${r.case_id || 'Case'} · ${r.verdict}`), h('small', null, `${r.run_title || 'Run'} · ${fmt(r.executed_at)}`), r.anomaly ? h('small', { className: 'warning-text' }, `Anomaly: ${r.anomaly}`) : null, r.missing_data ? h('small', { className: 'warning-text' }, `Missing: ${r.missing_data}`) : null)))),
    ),

    h('section', { className: 'lattice-grid' },
      Section('Create Plan', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); submit(() => api.createPlan({ ...planForm }), () => setPlanForm({ title: '', vehicle_platform: '', objective: '', owner: '', route: 'Proving Grounds' })); } },
        h('input', { required: true, placeholder: 'Plan title', value: planForm.title, onChange: (e) => setPlanForm({ ...planForm, title: e.target.value }) }),
        h('input', { required: true, placeholder: 'Vehicle platform', value: planForm.vehicle_platform, onChange: (e) => setPlanForm({ ...planForm, vehicle_platform: e.target.value }) }),
        h('input', { required: true, placeholder: 'Owner', value: planForm.owner, onChange: (e) => setPlanForm({ ...planForm, owner: e.target.value }) }),
        h('input', { required: true, placeholder: 'Route', value: planForm.route, onChange: (e) => setPlanForm({ ...planForm, route: e.target.value }) }),
        h('textarea', { required: true, rows: 2, placeholder: 'Objective', value: planForm.objective, onChange: (e) => setPlanForm({ ...planForm, objective: e.target.value }) }),
        h('button', { type: 'submit' }, 'Save plan')
      )),

      Section('Create Vehicle Config', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); submit(() => api.createVehicle({ ...vehicleForm, logger_health: 'Healthy', notes: '', sensor_stack: parseList(vehicleForm.sensor_stack), instrumentation: parseList(vehicleForm.instrumentation) }), () => setVehicleForm({ vehicle_label: '', vin: '', platform: '', logger_model: '', flash_version: '', sensor_stack: '', instrumentation: '' })); } },
        h('input', { required: true, placeholder: 'Vehicle label', value: vehicleForm.vehicle_label, onChange: (e) => setVehicleForm({ ...vehicleForm, vehicle_label: e.target.value }) }),
        h('input', { required: true, placeholder: 'VIN', value: vehicleForm.vin, onChange: (e) => setVehicleForm({ ...vehicleForm, vin: e.target.value }) }),
        h('input', { required: true, placeholder: 'Platform', value: vehicleForm.platform, onChange: (e) => setVehicleForm({ ...vehicleForm, platform: e.target.value }) }),
        h('input', { required: true, placeholder: 'Logger model', value: vehicleForm.logger_model, onChange: (e) => setVehicleForm({ ...vehicleForm, logger_model: e.target.value }) }),
        h('input', { required: true, placeholder: 'Flash version', value: vehicleForm.flash_version, onChange: (e) => setVehicleForm({ ...vehicleForm, flash_version: e.target.value }) }),
        h('input', { placeholder: 'Sensors (comma-separated)', value: vehicleForm.sensor_stack, onChange: (e) => setVehicleForm({ ...vehicleForm, sensor_stack: e.target.value }) }),
        h('input', { placeholder: 'Instrumentation (comma-separated)', value: vehicleForm.instrumentation, onChange: (e) => setVehicleForm({ ...vehicleForm, instrumentation: e.target.value }) }),
        h('button', { type: 'submit' }, 'Save vehicle')
      )),

      Section('Create Run', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); submit(() => api.createRun({ ...runForm, plan_id: runForm.plan_id ? Number(runForm.plan_id) : null, vehicle_id: runForm.vehicle_id ? Number(runForm.vehicle_id) : null }), () => setRunForm({ title: '', plan_id: '', vehicle_id: '', route: '', status: 'Queued', logger_health: 'Healthy', flash_version: '', notes: '', started_at: '', ended_at: '' })); } },
        h('input', { required: true, placeholder: 'Run title', value: runForm.title, onChange: (e) => setRunForm({ ...runForm, title: e.target.value }) }),
        h('select', { value: runForm.plan_id, onChange: (e) => setRunForm({ ...runForm, plan_id: e.target.value }) }, h('option', { value: '' }, 'Plan (optional)'), plans.map((p) => h('option', { key: p.id, value: p.id }, p.title))),
        h('select', { value: runForm.vehicle_id, onChange: (e) => setRunForm({ ...runForm, vehicle_id: e.target.value }) }, h('option', { value: '' }, 'Vehicle (optional)'), vehicles.map((v) => h('option', { key: v.id, value: v.id }, v.vehicle_label))),
        h('input', { required: true, placeholder: 'Route', value: runForm.route, onChange: (e) => setRunForm({ ...runForm, route: e.target.value }) }),
        h('input', { required: true, placeholder: 'Flash version', value: runForm.flash_version, onChange: (e) => setRunForm({ ...runForm, flash_version: e.target.value }) }),
        h('button', { type: 'submit' }, 'Save run')
      )),

      Section('Create Test Case', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); submit(() => api.createTestCase({ ...caseForm, plan_id: caseForm.plan_id ? Number(caseForm.plan_id) : null, tags: parseList(caseForm.tags) }), () => setCaseForm({ plan_id: '', case_id: '', title: '', objective: '', subsystem: '', expected_result: '', severity: 'Medium', status: 'Ready', tags: '' })); } },
        h('input', { required: true, placeholder: 'Case ID', value: caseForm.case_id, onChange: (e) => setCaseForm({ ...caseForm, case_id: e.target.value }) }),
        h('input', { required: true, placeholder: 'Case title', value: caseForm.title, onChange: (e) => setCaseForm({ ...caseForm, title: e.target.value }) }),
        h('select', { value: caseForm.plan_id, onChange: (e) => setCaseForm({ ...caseForm, plan_id: e.target.value }) }, h('option', { value: '' }, 'Plan (optional)'), plans.map((p) => h('option', { key: p.id, value: p.id }, p.title))),
        h('input', { required: true, placeholder: 'Subsystem', value: caseForm.subsystem, onChange: (e) => setCaseForm({ ...caseForm, subsystem: e.target.value }) }),
        h('textarea', { required: true, rows: 2, placeholder: 'Objective', value: caseForm.objective, onChange: (e) => setCaseForm({ ...caseForm, objective: e.target.value }) }),
        h('textarea', { required: true, rows: 2, placeholder: 'Expected result', value: caseForm.expected_result, onChange: (e) => setCaseForm({ ...caseForm, expected_result: e.target.value }) }),
        h('input', { placeholder: 'Tags (comma-separated)', value: caseForm.tags, onChange: (e) => setCaseForm({ ...caseForm, tags: e.target.value }) }),
        h('button', { type: 'submit' }, 'Save test case')
      )),

      Section('Record Case Result', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); submit(() => api.createCaseResult({ ...resultForm, run_id: Number(resultForm.run_id), test_case_id: Number(resultForm.test_case_id) }), () => setResultForm({ run_id: '', test_case_id: '', verdict: 'Passed', anomaly: '', missing_data: '', notes: '' })); } },
        h('select', { required: true, value: resultForm.run_id, onChange: (e) => setResultForm({ ...resultForm, run_id: e.target.value }) }, h('option', { value: '' }, 'Run'), runs.map((r) => h('option', { key: r.id, value: r.id }, r.title))),
        h('select', { required: true, value: resultForm.test_case_id, onChange: (e) => setResultForm({ ...resultForm, test_case_id: e.target.value }) }, h('option', { value: '' }, 'Test case'), testCases.map((c) => h('option', { key: c.id, value: c.id }, `${c.case_id} - ${c.title}`))),
        h('select', { value: resultForm.verdict, onChange: (e) => setResultForm({ ...resultForm, verdict: e.target.value }) }, h('option', null, 'Passed'), h('option', null, 'Failed'), h('option', null, 'Blocked')),
        h('input', { placeholder: 'Anomaly (optional)', value: resultForm.anomaly, onChange: (e) => setResultForm({ ...resultForm, anomaly: e.target.value }) }),
        h('input', { placeholder: 'Missing data (optional)', value: resultForm.missing_data, onChange: (e) => setResultForm({ ...resultForm, missing_data: e.target.value }) }),
        h('textarea', { rows: 2, placeholder: 'Notes', value: resultForm.notes, onChange: (e) => setResultForm({ ...resultForm, notes: e.target.value }) }),
        h('button', { type: 'submit' }, 'Save case result')
      )),

      Section('Upload Run Log File', h('form', { className: 'stack-form', onSubmit: (e) => { e.preventDefault(); if (!uploadRunId || !uploadFile) { setError('Choose run and file before upload.'); return; } submit(() => api.uploadFile(Number(uploadRunId), uploadFile), () => { setUploadRunId(''); setUploadFile(null); }); } },
        h('select', { required: true, value: uploadRunId, onChange: (e) => setUploadRunId(e.target.value) }, h('option', { value: '' }, 'Run'), runs.map((r) => h('option', { key: r.id, value: r.id }, r.title))),
        h('input', { required: true, type: 'file', onChange: (e) => setUploadFile(e.target.files?.[0] || null) }),
        h('button', { type: 'submit' }, 'Upload and index')
      ))
    ),

    h('footer', { className: 'footer-note' }, `Plans: ${plans.length} · Runs: ${runs.length} · Issues: ${issues.length} · Files: ${files.length}`)
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(h(App));
