import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, ResponsiveContainer,
} from "recharts";
import {
  FiSearch, FiUpload, FiActivity, FiUsers, FiTrendingUp,
  FiAlertCircle, FiCheckCircle, FiClock, FiWifiOff,
} from "react-icons/fi";
import { api } from "./api";

const SPECTRUM_COLORS = {
  "Ultra Negative": "#b41340",
  Negative: "#f74b6d",
  Neutral: "#abadaf",
  Positive: "#34c9b8",
  "Ultra Positive": "#00675e",
};

const DEMO_COLORS = ["#4a40e0", "#00a896", "#ff9198", "#8582ff"];

function StatCard({ icon: Icon, label, value, tint }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-panel p-5 flex items-center gap-4"
    >
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${tint}1a`, color: tint }}
      >
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-label uppercase tracking-wide text-on-surface-variant truncate">
          {label}
        </p>
        <p className="text-2xl font-headline font-extrabold text-on-surface leading-tight">
          {value}
        </p>
      </div>
    </motion.div>
  );
}

function SectionTitle({ children, eyebrow }) {
  return (
    <div className="mb-4">
      {eyebrow && (
        <p className="text-xs font-label font-semibold uppercase tracking-widest text-primary mb-1">
          {eyebrow}
        </p>
      )}
      <h2 className="text-lg font-headline font-bold text-on-surface">{children}</h2>
    </div>
  );
}

function KeywordCloud({ keywords }) {
  if (!keywords?.length) return null;
  return (
    <div className="glass-panel p-6">
      <SectionTitle eyebrow="Aspect Signals">What people are actually saying</SectionTitle>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {keywords.map((k, i) => (
          <motion.span
            key={`${k.word}-${i}`}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.03 }}
            style={{ fontSize: k.size, fontWeight: k.weight, color: k.color }}
            className="font-headline leading-none cursor-default"
            title={`${k.count} mention${k.count === 1 ? "" : "s"} · ${k.sentiment}`}
          >
            {k.word}
          </motion.span>
        ))}
      </div>
    </div>
  );
}

function MarketIntel({ intel }) {
  if (!intel) return null;
  return (
    <div className="glass-panel p-6 space-y-6">
      <SectionTitle eyebrow="Market Intelligence">Key highlights</SectionTitle>
      <div className="grid sm:grid-cols-3 gap-3">
        {intel.key_highlights?.map((h, i) => (
          <div key={i} className="rounded-xl bg-surface-container-low p-4">
            <p className="font-headline font-bold text-sm text-on-surface mb-1">{h.title}</p>
            <p className="text-sm text-on-surface-variant leading-snug">{h.description}</p>
          </div>
        ))}
      </div>

      {intel.market_velocity && (
        <div className="rounded-xl bg-primary-container/40 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-on-primary-container/70 font-label">
              Market velocity
            </p>
            <p className="text-sm text-on-primary-container">{intel.market_velocity.description}</p>
          </div>
          <div className="text-right shrink-0 ml-4">
            <p className="text-2xl font-headline font-extrabold text-on-primary-container">
              {intel.market_velocity.value}
            </p>
            <p className="text-xs text-on-primary-container/70">{intel.market_velocity.growth}</p>
          </div>
        </div>
      )}

      {intel.market_verticals?.length > 0 && (
        <div className="space-y-2">
          {intel.market_verticals.map((v, i) => (
            <div key={i} className="flex items-center justify-between rounded-xl border border-outline-variant/50 p-3">
              <div className="min-w-0 pr-3">
                <p className="font-label font-semibold text-sm text-on-surface">{v.title}</p>
                <p className="text-xs text-on-surface-variant truncate">{v.description}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs font-label px-2 py-1 rounded-full bg-surface-container text-on-surface-variant whitespace-nowrap">
                  {v.badge}
                </span>
                <span className="text-sm font-bold text-secondary w-10 text-right">{v.positive_percent}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function HistoryPanel({ sessions }) {
  return (
    <div className="glass-panel p-6">
      <SectionTitle eyebrow="Past Runs">Session history</SectionTitle>
      {sessions.length === 0 ? (
        <p className="text-sm text-on-surface-variant">
          No analyses yet — run one above and it'll show up here.
        </p>
      ) : (
        <ul className="space-y-2">
          {sessions.map((s, i) => (
            <li key={i} className="flex items-center justify-between rounded-xl border border-outline-variant/50 p-3">
              <div className="min-w-0">
                <p className="font-label font-semibold text-sm text-on-surface truncate">{s.product}</p>
                <p className="text-xs text-on-surface-variant">
                  {s.date} · {s.source} · {s.posts} posts
                </p>
              </div>
              <div className="text-right shrink-0 ml-3">
                <p className="text-sm font-bold" style={{ color: s.iconColor }}>{s.score}/10</p>
                <p className="text-xs text-on-surface-variant">{s.sentiment}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [product, setProduct] = useState("");
  const [status, setStatus] = useState(null);
  const [latest, setLatest] = useState(null);
  const [keywords, setKeywords] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [backendUp, setBackendUp] = useState(true);
  const [uploading, setUploading] = useState(false);
  const pollRef = useRef(null);
  const fileInputRef = useRef(null);

  const loadResults = useCallback(async () => {
    try {
      const [latestData, kwData, historyData] = await Promise.allSettled([
        api.latest(),
        api.keywords(),
        api.history(),
      ]);
      if (latestData.status === "fulfilled") setLatest(latestData.value);
      if (kwData.status === "fulfilled") setKeywords(kwData.value?.keywords || []);
      if (historyData.status === "fulfilled") setHistory(historyData.value?.sessions || []);
    } catch {
      // best-effort; individual panels just stay empty
    }
  }, []);

  const pollStatus = useCallback(() => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.status();
        setStatus(s);
        setBackendUp(true);
        if (s.status === "done" || s.status === "error") {
          clearInterval(pollRef.current);
          if (s.status === "done") loadResults();
        }
      } catch {
        setBackendUp(false);
      }
    }, 2000);
  }, [loadResults]);

  useEffect(() => {
    (async () => {
      try {
        const s = await api.status();
        setStatus(s);
        setBackendUp(true);
        if (s.status === "running") pollStatus();
        else loadResults();
      } catch {
        setBackendUp(false);
      }
    })();
    return () => clearInterval(pollRef.current);
  }, [pollStatus, loadResults]);

  const startAnalysis = async (e) => {
    e.preventDefault();
    setError("");
    if (!product.trim()) return;
    try {
      await api.analyze(product.trim());
      pollStatus();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCsvUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      await api.uploadCsv(file);
      pollStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const running = status?.status === "running";
  const stats = latest?.stats;

  const spectrumData = stats?.sentiment_spectrum
    ? Object.entries(stats.sentiment_spectrum).map(([bucket, count]) => ({
        bucket, count, fill: SPECTRUM_COLORS[bucket] || "#8582ff",
      }))
    : [];

  const demoData = stats?.demographics
    ? Object.entries(stats.demographics)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-outline-variant/50 bg-surface-container-lowest/70 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-on-primary font-headline font-extrabold text-sm">
              L
            </div>
            <div>
              <p className="font-headline font-extrabold text-on-surface leading-none">Lumina Analytics</p>
              <p className="text-xs text-on-surface-variant">Product Sentiment Intelligence</p>
            </div>
          </div>
          {!backendUp && (
            <div className="flex items-center gap-1.5 text-error text-xs font-label font-semibold">
              <FiWifiOff size={14} /> Backend unreachable
            </div>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
        {/* Hero / input */}
        <section className="glass-panel p-8">
          <SectionTitle eyebrow="New Analysis">
            What product should we listen to Reddit about?
          </SectionTitle>
          <form onSubmit={startAnalysis} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <FiSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={16} />
              <input
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g. OnePlus 12R, Nothing Phone 3, iPad Air"
                disabled={running}
                className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-lowest text-on-surface placeholder:text-on-surface-variant/70 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none disabled:opacity-50 text-sm"
              />
            </div>
            <button
              type="submit"
              disabled={running || !product.trim()}
              className="px-5 py-2.5 rounded-xl bg-primary text-on-primary font-label font-semibold text-sm shadow-primary hover:opacity-90 active:scale-[0.98] transition disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {running ? "Running…" : "Analyze"}
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={running || uploading}
              className="px-5 py-2.5 rounded-xl border border-outline-variant text-on-surface font-label font-semibold text-sm hover:bg-surface-container-low transition disabled:opacity-40 flex items-center gap-2 justify-center whitespace-nowrap"
            >
              <FiUpload size={15} /> {uploading ? "Uploading…" : "Upload CSV"}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleCsvUpload}
              className="hidden"
            />
          </form>
          <p className="text-xs text-on-surface-variant mt-2">
            CSV/Excel: first column header is the target product, each row a review. Extra columns are treated as competitors.
          </p>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 flex items-start gap-2 text-error text-sm bg-error-container/10 rounded-xl p-3"
              >
                <FiAlertCircle size={16} className="mt-0.5 shrink-0" /> {error}
              </motion.div>
            )}
            {status && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 flex items-center gap-2 text-sm rounded-xl p-3"
                style={{
                  backgroundColor:
                    status.status === "running" ? "#4a40e01a" :
                    status.status === "error" ? "#b413401a" :
                    status.status === "done" ? "#00675e1a" : "transparent",
                  color:
                    status.status === "running" ? "#4a40e0" :
                    status.status === "error" ? "#b41340" :
                    status.status === "done" ? "#00675e" : "#595c5e",
                }}
              >
                {status.status === "running" && <FiActivity className="animate-pulse" size={16} />}
                {status.status === "done" && <FiCheckCircle size={16} />}
                {status.status === "error" && <FiAlertCircle size={16} />}
                {status.status === "idle" && <FiClock size={16} />}
                <span className="font-label">
                  {status.status === "idle"
                    ? "No analysis run yet."
                    : `${status.product ? status.product + " — " : ""}${status.message || status.status}`}
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </section>

        {/* Stat cards */}
        {stats && (
          <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard icon={FiActivity} label="Total Posts" value={stats.total} tint="#4a40e0" />
            <StatCard icon={FiTrendingUp} label="Positive" value={stats.positive} tint="#00675e" />
            <StatCard icon={FiAlertCircle} label="Negative" value={stats.negative} tint="#b41340" />
            <StatCard icon={FiUsers} label="Sarcastic Flags" value={(stats.sarcastic_to_positive || 0) + (stats.sarcastic_to_negative || 0)} tint="#ff9198" />
          </section>
        )}

        {/* Charts */}
        {(spectrumData.length > 0 || demoData.length > 0) && (
          <section className="grid md:grid-cols-2 gap-6">
            {spectrumData.length > 0 && (
              <div className="glass-panel p-6">
                <SectionTitle eyebrow="Sentiment Spectrum">Distribution across posts</SectionTitle>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={spectrumData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e9eb" vertical={false} />
                    <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#595c5e" }} angle={-15} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 11, fill: "#595c5e" }} allowDecimals={false} />
                    <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #d9dde0", fontSize: 13 }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {spectrumData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {demoData.length > 0 && (
              <div className="glass-panel p-6">
                <SectionTitle eyebrow="Audience">Demographic breakdown</SectionTitle>
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={demoData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                      {demoData.map((_, i) => <Cell key={i} fill={DEMO_COLORS[i % DEMO_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #d9dde0", fontSize: 13 }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-3 justify-center mt-2">
                  {demoData.map((d, i) => (
                    <span key={i} className="flex items-center gap-1.5 text-xs text-on-surface-variant">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: DEMO_COLORS[i % DEMO_COLORS.length] }} />
                      {d.name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        <KeywordCloud keywords={keywords} />
        <MarketIntel intel={latest?.market_intelligence} />
        <HistoryPanel sessions={history} />
      </main>

      <footer className="max-w-6xl mx-auto px-6 pb-10 text-xs text-on-surface-variant/70">
        Lumina Analytics — sentiment pulled from Reddit and classified with Llama via Groq.
      </footer>
    </div>
  );
}
