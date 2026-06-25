/* Governance Intelligence Console — embedded React app.
   Reads window.__GOV__ (records + model constants injected by Python),
   recomputes the governance risk model live as the Zone-3 sliders move,
   and drives the Zone-2 chart colour + Zone-4 explainable-AI feed. */

const { useState, useEffect, useRef, useMemo } = React;

const GOV = (typeof window.__GOV__ === "object") ? window.__GOV__ : null;
const M = GOV ? GOV.model : {};
const RECORDS = GOV ? GOV.records : [];
const WATCH = 40;                       // amber band lower bound
const THRESHOLD = M.THRESHOLD || 55;

const COLORS = { ok: "#22c55e", warn: "#f59e0b", danger: "#ef4444" };
const FILLS = {
  ok: "rgba(34,197,94,0.10)", warn: "rgba(245,158,11,0.12)", danger: "rgba(239,68,68,0.14)",
};
// Oriel (StreamlitPred) institutional chart theme, ported to client-side Plotly.js.
const GOLD = "#D4A85A";
const ORIEL = { border: "#223042", grid: "rgba(42,52,65,0.52)", textSec: "#B0BEC9", elevated: "#1b2532", app: "#0B0F14" };

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const fmt1 = (v) => v.toFixed(1);

function pointRisk(lat, vol, lf, ld, sn) {
  const latC = clamp01((lat * lf - M.LAT_REF) / (M.LAT_MAX - M.LAT_REF));
  const volC = clamp01((vol * ld - M.VOL_REF) / (M.VOL_MAX - M.VOL_REF));
  return Math.max(0, Math.min(100, 100 * sn * (M.W_LAT * latC + M.W_VOL * volC)));
}

function levelOf(composite) {
  return composite > THRESHOLD ? "danger" : composite > WATCH ? "warn" : "ok";
}

// Derive every metric, the chart series and the XAI feed for one slider state.
function computeState(lf, ld, sn) {
  const series = RECORDS.map((r) => pointRisk(r.latency, r.vol, lf, ld, sn));
  const dates = RECORDS.map((r) => r.t);
  const win = Math.min(M.RECENT_WINDOW, RECORDS.length);
  const recent = RECORDS.slice(-win);
  const recentRisk = series.slice(-win);

  const composite = recentRisk.reduce((a, b) => a + b, 0) / win;
  const avgLatency = recent.reduce((a, r) => a + r.latency * lf, 0) / win;
  const avgVolume = recent.reduce((a, r) => a + r.vol * ld, 0) / win;
  const adherence = clamp01(1 - composite / 130) * 100;

  // Driver attribution (weighted component contributions over the window).
  let cLat = 0, cVol = 0, worst = recent[0], worstRisk = -1;
  recent.forEach((r, i) => {
    cLat += M.W_LAT * clamp01((r.latency * lf - M.LAT_REF) / (M.LAT_MAX - M.LAT_REF));
    cVol += M.W_VOL * clamp01((r.vol * ld - M.VOL_REF) / (M.VOL_MAX - M.VOL_REF));
    if (recentRisk[i] > worstRisk) { worstRisk = recentRisk[i]; worst = r; }
  });
  const driver = cLat >= cVol ? "latency" : "volume";

  return { series, dates, composite, avgLatency, avgVolume, adherence,
           driver, worstPhase: worst.phase, level: levelOf(composite) };
}

function buildAlerts(s, lf) {
  const conf = Math.round(Math.min(99, 60 + Math.abs(s.composite - THRESHOLD) * 1.4));
  const latX = (lf).toFixed(1);
  if (s.level === "danger") {
    const root = s.driver === "latency"
      ? { title: "Schema-normalization latency is the dominant risk driver",
          body: <>Processed schema latency in <b>{s.worstPhase}</b> is running at roughly <b>{latX}×</b> the calibrated baseline, throttling downstream governance throughput and inflating predicted schedule slippage.</> }
      : { title: "Ingestion log volume is the dominant risk driver",
          body: <>Sustained ingestion volume in <b>{s.worstPhase}</b> has exceeded the normalization engine's calibrated envelope, creating back-pressure across the governance pipeline.</> };
    const action = s.driver === "latency"
      ? "Re-sequence the ingestion queue for the affected phase and reduce the latency multiplier; auto-escalate to the delivery lead if sustained beyond two cycles."
      : "Scale normalization workers and rebalance batch windows; defer non-critical ingestion sources until composite risk falls below threshold.";
    return [
      { lvl: "danger", tag: "Critical", title: "Risk threshold breached",
        body: <>Composite governance risk is <b>{fmt1(s.composite)}%</b>, above the <b>{THRESHOLD}%</b> action threshold. Automated orchestration has flagged this delivery stream for intervention.</>,
        meta: [["Composite", fmt1(s.composite) + "%"], ["Threshold", THRESHOLD + "%"], ["Confidence", conf + "%"]] },
      { lvl: "warn", tag: "Root cause", title: root.title, body: root.body,
        meta: [["Driver", s.driver === "latency" ? "Schema latency" : "Ingest volume"], ["Phase", s.worstPhase], ["Confidence", conf + "%"]] },
      { lvl: "info", tag: "Recommended action", title: "Orchestration recommendation", body: action,
        meta: [["Type", "Semi-automated"], ["Owner", "Delivery lead"]] },
    ];
  }
  if (s.level === "warn") {
    return [
      { lvl: "warn", tag: "Watch", title: "Composite risk approaching threshold",
        body: <>Composite governance risk is <b>{fmt1(s.composite)}%</b>, within the watch band below the <b>{THRESHOLD}%</b> threshold. Primary signal: <b>{s.driver === "latency" ? "schema latency" : "ingest volume"}</b> in {s.worstPhase}.</>,
        meta: [["Composite", fmt1(s.composite) + "%"], ["Trend", "Elevated"], ["Confidence", conf + "%"]] },
      { lvl: "ok", tag: "Status", title: "No automated action required",
        body: "Governance signals remain within tolerance. Continuous monitoring active across all ingestion sources.",
        meta: [["Mode", "Monitoring"], ["Sources", "14 / 14"]] },
    ];
  }
  return [
    { lvl: "ok", tag: "Nominal", title: "All governance signals nominal",
      body: <>Composite governance risk is <b>{fmt1(s.composite)}%</b>, well below the <b>{THRESHOLD}%</b> action threshold. Predicted schedule adherence is healthy.</>,
      meta: [["Composite", fmt1(s.composite) + "%"], ["Adherence", fmt1(s.adherence) + "%"], ["Confidence", "98%"]] },
    { lvl: "info", tag: "System", title: "Adaptive governance loop active",
      body: "Explainable-AI diagnostics standing by. Root-cause analysis will populate automatically if composite risk crosses the threshold.",
      meta: [["Mode", "Monitoring"], ["Sources", "14 / 14"]] },
  ];
}

function Clock() {
  const [t, setT] = useState("");
  useEffect(() => {
    const tick = () => setT(new Date().toLocaleTimeString([], { hour12: false }));
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id);
  }, []);
  return <span className="clock">{t} UTC{"·"}sim</span>;
}

const STATUS_TEXT = { ok: "All systems nominal", warn: "Elevated risk — monitoring", danger: "Risk threshold breached" };

function TopBar({ level }) {
  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-mark">G</div>
        <div className="brand-text">
          <h1>Governance Intelligence Console</h1>
          <p>AI-Driven Project Governance · Enterprise IT Delivery · simulation sandbox</p>
        </div>
      </div>
      <div className="topbar-spacer" />
      <span className="pill"><span className={"dot " + (level === "ok" ? "" : level)} />{STATUS_TEXT[level]}</span>
      <span className="pill"><Clock /></span>
    </div>
  );
}

function Kpi({ label, value, unit, delta, goodDir, riskClass }) {
  let cls = "flat", arrow = "";
  if (Math.abs(delta) >= 0.05) {
    const improving = (goodDir === "down" && delta < 0) || (goodDir === "up" && delta > 0);
    cls = improving ? "down" : "up";
    arrow = delta > 0 ? "▲" : "▼";
  }
  return (
    <div className={"kpi" + (riskClass ? " " + riskClass : "")}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}<span className="unit">{unit}</span></div>
      <div className={"kpi-delta " + cls}>{arrow} {Math.abs(delta) < 0.05 ? "no change" : fmt1(Math.abs(delta)) + unit + " vs baseline"}</div>
    </div>
  );
}

function Chart({ dates, series, baseSeries, level }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current || !window.Plotly) return;
    const color = COLORS[level];
    // Soft glow halo behind the markers (Oriel technique).
    const glow = {
      x: dates, y: series, type: "scatter", mode: "markers",
      marker: { size: 16, color: FILLS[level], line: { width: 0 } },
      hoverinfo: "skip", showlegend: false,
    };
    // Dashed gold reference = composite risk at default slider positions.
    const baseline = {
      x: dates, y: baseSeries, type: "scatter", mode: "lines",
      line: { color: GOLD, width: 1.5, dash: "dash" }, name: "Baseline",
      hovertemplate: "%{x}<br>Baseline %{y:.1f}%<extra></extra>", showlegend: false,
    };
    const main = {
      x: dates, y: series, type: "scatter", mode: "lines+markers",
      line: { color, width: 2.6, shape: "spline" },
      marker: { size: 5, color, line: { color: ORIEL.app, width: 1.4 } },
      fill: "tozeroy", fillcolor: FILLS[level],
      hovertemplate: "%{x}<br>Composite risk <b>%{y:.1f}%</b><extra></extra>", showlegend: false,
    };
    const axis = {
      showgrid: true, gridcolor: ORIEL.grid, gridwidth: 1,
      linecolor: ORIEL.border, tickcolor: ORIEL.border, zeroline: false,
      tickfont: { color: ORIEL.textSec },
    };
    const layout = {
      height: 360, margin: { l: 56, r: 24, t: 28, b: 48 },
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Inter, sans-serif", color: ORIEL.textSec, size: 12 },
      xaxis: axis,
      yaxis: { ...axis, range: [0, 100], ticksuffix: "%" },
      hoverlabel: { bgcolor: ORIEL.elevated, bordercolor: "rgba(212,168,90,0.35)",
        font: { color: "#E6EDF3", family: "Inter, sans-serif", size: 12 } },
      shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: THRESHOLD, y1: THRESHOLD,
        line: { color: "#ef4444", width: 1.4, dash: "dash" } }],
      annotations: [{ xref: "paper", x: 1, y: THRESHOLD, xanchor: "right", yanchor: "bottom",
        text: "Action threshold " + THRESHOLD + "%", showarrow: false, font: { color: "#ef4444", size: 10.5 } }],
      showlegend: false,
    };
    window.Plotly.react(ref.current, [glow, baseline, main], layout,
      { displayModeBar: false, displaylogo: false, responsive: true });
  }, [dates, series, baseSeries, level]);
  return (
    <div>
      <div className="chart-host" ref={ref} />
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch" style={{ background: COLORS[level] }} />Operational risk trajectory</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: GOLD }} />Baseline (default inputs)</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: "#ef4444" }} />Action threshold ({THRESHOLD}%)</span>
      </div>
    </div>
  );
}

function Slider({ name, help, value, min, max, step, fmt, onChange }) {
  return (
    <div className="control">
      <div className="control-top">
        <span className="control-name">{name}</span>
        <span className="control-val">{fmt(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
      <div className="control-help">{help}</div>
    </div>
  );
}

function App() {
  if (!GOV) return <div style={{ padding: 40, color: "#9fb0c3" }}>Awaiting data payload…</div>;

  const [lf, setLf] = useState(M.DEFAULT_LATENCY_FACTOR);
  const [ld, setLd] = useState(M.DEFAULT_LOAD_FACTOR);
  const [sn, setSn] = useState(M.DEFAULT_SENSITIVITY);

  const s = useMemo(() => computeState(lf, ld, sn), [lf, ld, sn]);
  const base = useMemo(() => computeState(M.DEFAULT_LATENCY_FACTOR, M.DEFAULT_LOAD_FACTOR, M.DEFAULT_SENSITIVITY), []);
  const alerts = useMemo(() => buildAlerts(s, lf), [s, lf]);

  const reset = () => { setLf(M.DEFAULT_LATENCY_FACTOR); setLd(M.DEFAULT_LOAD_FACTOR); setSn(M.DEFAULT_SENSITIVITY); };

  // Zone 4 — optional live diagnostic from Gemma (Gemini API). The templated
  // feed below stays instant; this adds a real LLM narrative on demand.
  const [ai, setAi] = useState({ text: "", loading: false, error: "" });
  const hasKey = typeof window !== "undefined" && !!window.__GOV_KEY__;

  const runAI = async () => {
    if (!window.GovAI) { setAi({ text: "", loading: false, error: "AI module not loaded." }); return; }
    setAi({ text: "", loading: true, error: "" });
    try {
      const text = await window.GovAI.generateDiagnostic({
        composite: fmt1(s.composite), threshold: THRESHOLD, level: s.level,
        driver: s.driver === "latency" ? "schema-normalization latency" : "ingestion log volume",
        phase: s.worstPhase, lf: lf.toFixed(1), ld: ld.toFixed(1), sn: sn.toFixed(1),
      });
      setAi({ text, loading: false, error: "" });
    } catch (e) {
      setAi({ text: "", loading: false, error: (e && e.message) || "AI request failed." });
    }
  };

  return (
    <div className="app">
      <TopBar level={s.level} />
      <div className="grid">
        <div className="col">
          <div className="zone">
            <div className="zone-head">
              <div><div className="zone-eyebrow">Zone 1 · Governance health</div><div className="zone-title">Key performance indicators</div></div>
            </div>
            <div className="zone-body">
              <div className="kpi-strip">
                <Kpi label="Composite Risk Index" value={fmt1(s.composite)} unit="%" delta={s.composite - base.composite} goodDir="down" riskClass={"risk-" + s.level} />
                <Kpi label="Schedule Adherence" value={fmt1(s.adherence)} unit="%" delta={s.adherence - base.adherence} goodDir="up" />
                <Kpi label="Avg Schema Latency" value={fmt1(s.avgLatency)} unit="ms" delta={s.avgLatency - base.avgLatency} goodDir="down" />
                <Kpi label="Ingestion Throughput" value={Math.round(s.avgVolume)} unit="" delta={s.avgVolume - base.avgVolume} goodDir="down" />
              </div>
            </div>
          </div>

          <div className="zone">
            <div className="zone-head">
              <div><div className="zone-eyebrow">Zone 2 · Governance intelligence engine</div><div className="zone-title">Operational risk trajectory</div></div>
              <span className="pill"><span className={"dot " + (s.level === "ok" ? "" : s.level)} />{fmt1(s.composite)}% composite</span>
            </div>
            <Chart dates={s.dates} series={s.series} baseSeries={base.series} level={s.level} />
          </div>
        </div>

        <div className="col">
          <div className="zone">
            <div className="zone-head">
              <div><div className="zone-eyebrow">Zone 3 · Simulation inputs</div><div className="zone-title">Control parameters</div></div>
            </div>
            <div className="zone-body">
              <Slider name="Pipeline Latency Factor" help="Multiplier on schema-normalization latency feeding the risk engine."
                value={lf} min={1} max={5} step={0.1} fmt={(v) => v.toFixed(1) + "×"} onChange={setLf} />
              <Slider name="Ingestion Load Factor" help="Scales ingested log volume against the normalization envelope."
                value={ld} min={0.5} max={3} step={0.1} fmt={(v) => v.toFixed(1) + "×"} onChange={setLd} />
              <Slider name="Risk Sensitivity" help="Governance-engine sensitivity applied to the composite score."
                value={sn} min={0.5} max={2} step={0.1} fmt={(v) => v.toFixed(1) + "×"} onChange={setSn} />
              <button className="reset-btn" onClick={reset}>Reset to baseline</button>
            </div>
          </div>

          <div className="zone">
            <div className="zone-head">
              <div><div className="zone-eyebrow">Zone 4 · Explainable AI</div><div className="zone-title">Root-cause diagnostic feed</div></div>
              <button className="ai-btn" onClick={runAI} disabled={ai.loading || !hasKey}
                title={hasKey ? "Generate a live diagnostic with Gemma 4" : "Set gemini_api_key in secrets to enable"}>
                {ai.loading ? "Generating…" : "✨ Gemma 4"}
              </button>
            </div>
            <div className="zone-body">
              <div className="alerts">
                {ai.error && (
                  <div className="alert lvl-warn">
                    <div className="alert-head"><span className="alert-tag">Gemma 4</span><span className="alert-title">AI request failed</span></div>
                    <div className="alert-body">{ai.error}</div>
                  </div>
                )}
                {ai.text && (
                  <div className="alert lvl-info">
                    <div className="alert-head"><span className="alert-tag">Gemma 4 · live</span><span className="alert-title">AI root-cause narrative</span></div>
                    <div className="alert-body" style={{ whiteSpace: "pre-line" }}>{ai.text}</div>
                    <div className="alert-meta"><span><b>Model:</b> gemma-4-26b-a4b-it</span><span><b>Composite:</b> {fmt1(s.composite)}%</span></div>
                  </div>
                )}
                {alerts.map((a, i) => (
                  <div className={"alert lvl-" + a.lvl} key={i}>
                    <div className="alert-head"><span className="alert-tag">{a.tag}</span><span className="alert-title">{a.title}</span></div>
                    <div className="alert-body">{a.body}</div>
                    <div className="alert-meta">{a.meta.map((m, j) => <span key={j}><b>{m[0]}:</b> {m[1]}</span>)}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="foot">
        Simulation sandbox · mock data ({GOV.meta.rows} records, {GOV.meta.start} → {GOV.meta.end}) · no production systems connected ·
        <b> Work Made for Hire</b>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
