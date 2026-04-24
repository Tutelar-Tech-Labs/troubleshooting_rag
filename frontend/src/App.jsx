import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, ExternalLink, AlertTriangle, Loader2, BookOpen, Info, Sun, Moon, Shield, Terminal, Zap, Clock } from 'lucide-react';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [file, setFile] = useState(null);
  const [pastedText, setPastedText] = useState('');
  const [directIssue, setDirectIssue] = useState('');
  const [activeTab, setActiveTab] = useState('upload');
  const [loading, setLoading] = useState(false);
  const [currentStatus, setCurrentStatus] = useState({ stage: '', progress: '', messages: [] });
  const [countdown, setCountdown] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [fromTime, setFromTime] = useState('');
  const [toTime, setToTime] = useState('');
  const [isDarkMode, setIsDarkMode] = useState(true);
  const abortControllerRef = useRef(null);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    let timer;
    if (loading && countdown > 0) {
      timer = setInterval(() => {
        setCountdown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading, countdown]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPastedText('');
      setDirectIssue('');
      setResult(null);
      setError(null);
      setFromTime('');
      setToTime('');
      setCurrentStatus({ stage: '', progress: '', messages: [] });
    }
  };

  const handlePaste = (e) => {
    if (activeTab === 'upload') {
      // CRITICAL: Don't overwrite file if one is already selected
      // This prevents pasting into time filter inputs from clearing the uploaded file
      const target = e.target;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
        return; // Let native paste work in input fields
      }

      // If a file is already loaded, don't replace it with pasted text
      if (file) {
        return;
      }

      const items = e.clipboardData.items;
      let foundFile = false;

      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === 'file') {
          const blob = items[i].getAsFile();
          if (blob) {
            setFile(blob);
            setPastedText('');
            setDirectIssue('');
            setResult(null);
            setError(null);
            setCurrentStatus({ stage: '', progress: '', messages: [] });
            foundFile = true;
            break;
          }
        }
      }

      if (!foundFile) {
        const text = e.clipboardData.getData('text');
        if (text && text.trim().length > 10) {
          setPastedText(text);
          setFile(null);
          setDirectIssue('');
          setResult(null);
          setError(null);
          setCurrentStatus({ stage: '', progress: '', messages: [] });
        }
      }
    }
  };

  const handleUpload = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setCurrentStatus({ stage: 'Initiating forensic stream...', progress: '', messages: ['Initiating forensic stream...'], total_chunks: 0, current_chunk: 0 });
    setCountdown(120); // Initial 120s countdown

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let endpoint = '';
      let body = null;
      let headers = {};

      if (activeTab === 'upload') {
        if (!file && !pastedText) {
          throw new Error('Please upload a file or paste log content');
        }
        endpoint = `${API_URL}/analyze`;
        const formData = new FormData();
        if (file) {
          formData.append('file', file);
        } else if (pastedText) {
          const blob = new Blob([pastedText], { type: 'text/plain' });
          const virtualFile = new File([blob], 'pasted_log.txt', { type: 'text/plain' });
          formData.append('file', virtualFile);
        }

        if (fromTime) {
          formData.append('start_time', fromTime);
        }
        if (toTime) {
          formData.append('end_time', toTime);
        }

        body = formData;
      } else {
        if (!directIssue.trim()) {
          throw new Error('Please enter an error or issue description');
        }
        endpoint = `${API_URL}/analyze-issue`;
        body = { issue: directIssue };
        headers = { 'Content-Type': 'application/json' };
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        body: activeTab === 'upload' ? body : JSON.stringify(body),
        headers: headers,
        signal: controller.signal
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Analysis failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              if (data.status) {
                try {
                  const statusObj = JSON.parse(data.status);
                  // Update using previous state to ensure messages array appends correctly if needed,
                  // or just rely on backend sending the full array
                  setCurrentStatus(prev => ({
                    stage: statusObj.stage || prev.stage,
                    progress: statusObj.progress || prev.progress,
                    messages: statusObj.messages || prev.messages,
                    total_chunks: statusObj.total_chunks || prev.total_chunks,
                    current_chunk: statusObj.current_chunk || prev.current_chunk
                  }));

                  if (statusObj.stage?.includes('Neural') || statusObj.stage?.includes('solution')) {
                    setCountdown(60);
                  } else {
                    setCountdown(30);
                  }
                } catch (e) {
                  // Fallback for plain text
                  setCurrentStatus(prev => ({
                    ...prev,
                    stage: data.status,
                    messages: [...prev.messages, data.status]
                  }));
                  setCountdown(30);
                }
              } else if (data.result) {
                setResult(data.result);
                setLoading(false);
                setCountdown(0);
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setCurrentStatus(prev => ({ ...prev, stage: 'Analysis stopped by user.' }));
      } else {
        setError(err.message || 'Analysis failed');
      }
      console.error(err);
      setLoading(false);
      setCountdown(0);
    } finally {
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };


  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#020617] p-6 md:p-12 font-sans text-slate-900 dark:text-slate-100 transition-colors duration-300">
      {/* Theme Toggle */}
      <div className="fixed top-6 right-6 z-50">
        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className="p-3 rounded-2xl bg-white dark:bg-slate-900 shadow-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:scale-110 transition-all active:scale-95"
          title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {isDarkMode ? <Sun size={20} className="text-amber-400" /> : <Moon size={20} className="text-blue-600" />}
        </button>
      </div>

      <div className="max-w-6xl mx-auto" onPaste={handlePaste}>
        <header className="mb-12 text-center relative">
          <div className="inline-block p-3 bg-blue-100 dark:bg-blue-900/30 rounded-2xl mb-4 border border-blue-200 dark:border-blue-800/50">
            <Shield className="w-10 h-10 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-5xl font-black tracking-tight text-slate-900 dark:text-white mb-4">
            GlobalProtect <span className="text-blue-600 dark:text-blue-400">Log</span> Analyzer
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto font-medium">
            Advanced RAG-powered intelligence for automated GlobalProtect log forensic analysis and remediation.
          </p>
          <div className="absolute -top-10 -left-10 w-40 h-40 bg-blue-500/10 blur-[100px] rounded-full -z-10" />
          <div className="absolute -top-10 -right-10 w-40 h-40 bg-emerald-500/10 blur-[100px] rounded-full -z-10" />
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Sidebar: Control Panel */}
          <div className="lg:col-span-4 space-y-6">
            <div className="bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-3xl shadow-sm border border-slate-200 dark:border-slate-800/50 p-8">
              <h2 className="text-xl font-bold mb-6 flex items-center gap-3 text-slate-800 dark:text-slate-100">
                <Terminal size={22} className="text-blue-500" />
                Input Console
              </h2>

              {/* Tab Switcher */}
              <div className="flex bg-slate-100 dark:bg-slate-800/50 p-1 rounded-xl mb-6">
                <button
                  onClick={() => setActiveTab('upload')}
                  className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${activeTab === 'upload'
                    ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                    }`}
                >
                  <Upload size={16} />
                  Log Data
                </button>
                <button
                  onClick={() => setActiveTab('direct')}
                  className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${activeTab === 'direct'
                    ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                    }`}
                >
                  <Zap size={16} />
                  Direct Issue
                </button>
              </div>

              {activeTab === 'upload' ? (
                <div
                  className={`relative border-2 border-dashed rounded-2xl p-10 transition-all cursor-pointer group flex flex-col items-center justify-center text-center ${file || pastedText
                    ? 'border-blue-400 dark:border-blue-500/50 bg-blue-50/50 dark:bg-blue-500/5'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 hover:bg-slate-100 dark:hover:bg-slate-900/50'
                    }`}
                >
                  <input
                    type="file"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    onChange={handleFileChange}
                    accept=".log,.txt,.zip"
                  />

                  {file ? (
                    <>
                      <div className="bg-blue-600 dark:bg-blue-500 p-3 rounded-xl mb-4 shadow-lg shadow-blue-500/20">
                        <FileText className="w-8 h-8 text-white" />
                      </div>
                      <p className="text-base font-bold text-blue-700 dark:text-blue-400 break-all">{file.name}</p>
                      <p className="text-xs text-blue-500 dark:text-blue-500/70 mt-2 font-mono uppercase tracking-wider">{(file.size / 1024).toFixed(1)} KB • STATUS: READY</p>
                    </>
                  ) : pastedText ? (
                    <>
                      <div className="bg-emerald-600 dark:bg-emerald-500 p-3 rounded-xl mb-4 shadow-lg shadow-emerald-500/20">
                        <Zap className="w-8 h-8 text-white" />
                      </div>
                      <p className="text-base font-bold text-emerald-700 dark:text-emerald-400">Buffered Stream Content</p>
                      <p className="text-xs text-emerald-500 dark:text-emerald-500/70 mt-2 font-mono uppercase tracking-wider">{pastedText.length} CHR • STATUS: BUFFERED</p>
                    </>
                  ) : (
                    <>
                      <div className="bg-slate-200 dark:bg-slate-800 p-4 rounded-2xl mb-4 group-hover:scale-110 transition-transform duration-300">
                        <Upload className="w-10 h-10 text-slate-400 dark:text-slate-500" />
                      </div>
                      <p className="text-base font-bold text-slate-700 dark:text-slate-300">Ingest Log Data</p>
                      <p className="text-xs text-slate-500 dark:text-slate-500 mt-2 font-mono">DRAG-N-DROP, CTRL+V, OR BROWSE</p>
                    </>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="bg-slate-50 dark:bg-slate-950/50 border-2 border-slate-200 dark:border-slate-800 rounded-2xl p-4 transition-all focus-within:border-blue-400 dark:focus-within:border-blue-500/50">
                    <textarea
                      value={directIssue}
                      onChange={(e) => setDirectIssue(e.target.value)}
                      placeholder="e.g., GlobalProtect failed to connect with error: 'Portal not reachable'..."
                      className="w-full h-40 bg-transparent border-none outline-none text-slate-700 dark:text-slate-300 placeholder:text-slate-400 dark:placeholder:text-slate-600 resize-none font-medium"
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-600 font-mono uppercase tracking-widest text-center">Neural bypassing log extraction: direct vector search enabled</p>
                </div>
              )}

              {/* Time Filter Section */}
              {activeTab === 'upload' && (file || pastedText) && (
                <div className="mt-6 bg-slate-50 dark:bg-slate-950/50 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 space-y-4">
                  <h3 className="text-sm font-black text-slate-600 dark:text-slate-300 uppercase tracking-widest flex items-center gap-2">
                    <Clock size={16} className="text-blue-500" />
                    Time Filter (Optional)
                  </h3>
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                    FORMAT: MM/DD HH:MM:SS  (e.g. 08/20 15:30:45)
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1 block">From</label>
                      <input
                        type="text"
                        value={fromTime}
                        onChange={(e) => setFromTime(e.target.value)}
                        placeholder="08/20 10:00:00"
                        className="w-full px-3 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-700 dark:text-slate-300 placeholder:text-slate-300 dark:placeholder:text-slate-600 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-1 block">To</label>
                      <input
                        type="text"
                        value={toTime}
                        onChange={(e) => setToTime(e.target.value)}
                        placeholder="08/20 18:00:00"
                        className="w-full px-3 py-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-700 dark:text-slate-300 placeholder:text-slate-300 dark:placeholder:text-slate-600 outline-none focus:border-blue-400 dark:focus:border-blue-500 transition-colors"
                      />
                    </div>
                  </div>
                  {fromTime && toTime && (
                    <div className="flex items-center gap-2 text-xs text-blue-500 dark:text-blue-400 font-mono bg-blue-50 dark:bg-blue-500/10 px-3 py-2 rounded-lg border border-blue-100 dark:border-blue-500/20">
                      <Clock size={12} />
                      Analyzing logs between {fromTime} → {toTime}
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={handleUpload}
                disabled={(activeTab === 'upload' ? (!file && !pastedText) : !directIssue.trim()) || loading}
                className={`mt-8 w-full py-4 px-6 rounded-2xl font-black text-lg tracking-wider uppercase flex items-center justify-center gap-3 transition-all duration-300 ${(activeTab === 'upload' ? (!file && !pastedText) : !directIssue.trim()) || loading
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 cursor-not-allowed'
                  : 'bg-blue-600 dark:bg-blue-500 hover:bg-blue-700 dark:hover:bg-blue-600 text-white shadow-xl shadow-blue-500/30 hover:shadow-blue-500/40 hover:-translate-y-1'
                  }`}
              >
                {loading ? <Loader2 className="animate-spin" /> : <Shield size={22} />}
                {loading ? 'Analyzing...' : 'Execute Analysis'}
              </button>

              {error && (
                <div className="mt-6 p-5 bg-red-50 dark:bg-red-500/5 border border-red-100 dark:border-red-500/20 rounded-2xl flex items-start gap-4 text-red-700 dark:text-red-400 text-sm animate-in slide-in-from-top-2">
                  <AlertTriangle className="flex-shrink-0 w-6 h-6" />
                  <p className="leading-relaxed font-medium">{error}</p>
                </div>
              )}
            </div>

            <div className="bg-white dark:bg-blue-600/10 rounded-3xl p-8 text-slate-800 dark:text-white border border-slate-200 dark:border-blue-500/20 shadow-xl dark:shadow-2xl">
              <h3 className="font-black text-lg flex items-center gap-3 mb-6 text-blue-600 dark:text-blue-400 uppercase tracking-widest">
                <Info size={20} />
                Operations
              </h3>
              <ul className="space-y-5">
                {[
                  { step: '01', text: 'Neural pattern matching on log stream' },
                  { step: '02', text: 'Vector search across PAN-OS Knowledge Base' },
                  { step: '03', text: 'Generative AI synthesis of remediation steps' }
                ].map((item, i) => (
                  <li key={i} className="flex gap-4 items-start">
                    <span className="flex-shrink-0 font-mono text-xs font-black px-2 py-1 rounded bg-blue-100 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-500/30">
                      {item.step}
                    </span>
                    <span className="text-sm text-slate-600 dark:text-slate-300 font-medium leading-tight">{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Main Content: Intelligence Output */}
          <div className="lg:col-span-8 space-y-8">
            {!result && !loading && (
              <div className="bg-white dark:bg-slate-900/30 backdrop-blur-sm rounded-[2rem] border-2 border-slate-200 dark:border-slate-800/50 border-dashed p-32 text-center">
                <div className="bg-slate-100 dark:bg-slate-800/50 w-24 h-24 rounded-3xl flex items-center justify-center mx-auto mb-6 rotate-3 group-hover:rotate-0 transition-transform">
                  <Terminal className="text-slate-300 dark:text-slate-700 w-12 h-12" />
                </div>
                <h3 className="text-slate-400 dark:text-slate-600 font-bold text-2xl uppercase tracking-tighter">Awaiting Data Ingestion</h3>
                <p className="text-slate-300 dark:text-slate-700 mt-2 font-mono text-sm">SECURE ANALYTICS ENGINE IDLE</p>
              </div>
            )}

            {/* Loading Status */}
            {loading && (
              <div className="mt-8 space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="flex flex-col items-center justify-center p-8 bg-blue-50/50 dark:bg-blue-500/5 rounded-3xl border border-blue-100 dark:border-blue-500/20 relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-full h-1 bg-slate-100 dark:bg-slate-800">
                    <div className="h-full bg-blue-500 animate-progress-fast" />
                  </div>

                  <div className="relative">
                    <div className="absolute inset-0 bg-blue-400 blur-2xl opacity-20 animate-pulse" />
                    <Loader2 className="w-12 h-12 text-blue-600 dark:text-blue-400 animate-spin relative z-10" />
                  </div>

                  <div className="mt-6 w-full max-w-2xl space-y-4">
                    <div className="text-center">
                      <p className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                        {currentStatus.stage || 'Processing Analysis...'}
                      </p>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 font-medium">
                        {currentStatus.progress}
                      </p>
                      {countdown > 0 && (
                        <p className="text-xs text-slate-500 dark:text-slate-500 font-mono mt-2">
                          Estimated step time: {countdown}s
                        </p>
                      )}
                    </div>

                    {/* Live Terminal Log View */}
                    <div className="bg-slate-950 rounded-xl p-4 border border-slate-800 shadow-inner overflow-hidden flex flex-col items-start w-full min-h-[160px] text-left">
                      <div className="flex items-center gap-2 mb-3 border-b border-slate-800 w-full pb-2">
                        <Terminal size={14} className="text-emerald-500" />
                        <span className="text-xs font-mono font-bold text-slate-400">LIVE FORENSIC LOG</span>
                      </div>
                      <div className="flex-1 w-full overflow-y-auto space-y-1 max-h-[120px] scrollbar-thin scrollbar-thumb-slate-700">
                        {currentStatus.messages?.map((msg, i) => (
                          <div key={i} className="font-mono text-xs text-emerald-400/90 flex gap-2">
                            <span className="text-slate-600 select-none">❯</span>
                            <span className={i === currentStatus.messages.length - 1 ? "animate-pulse font-bold text-emerald-300" : ""}>{msg}</span>
                          </div>
                        ))}
                        {currentStatus.total_chunks > 0 && currentStatus.current_chunk > 0 && (
                          <div className="font-mono text-xs text-blue-400 mt-2">
                            Processing chunk {currentStatus.current_chunk}/{currentStatus.total_chunks}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-center gap-4 pt-2">
                      <div className="flex items-center justify-center gap-2">
                        <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]" />
                        <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]" />
                        <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-bounce" />
                      </div>
                      <button
                        onClick={handleStop}
                        className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-full text-xs font-bold transition-all shadow-lg shadow-red-500/20 active:scale-95 flex items-center gap-2"
                      >
                        <Zap className="w-3 h-3 fill-current" />
                        STOP ANALYSIS
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                {result.status === 'resolved' && (
                  <div className="bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20 rounded-[2rem] p-10 shadow-lg">
                    <div className="text-center mb-8">
                      <CheckCircle className="w-16 h-16 text-emerald-500 mx-auto mb-4" />
                      <h2 className="text-3xl font-black text-emerald-700 dark:text-emerald-400">Issue Detected & Resolved</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="bg-white/60 dark:bg-slate-900/40 rounded-2xl p-5 border border-emerald-200/50 dark:border-emerald-500/10">
                        <h4 className="text-xs font-black text-red-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                          <AlertTriangle size={14} />
                          What Happened
                        </h4>
                        <p className="text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed">
                          {result.detected_issue || 'Transient error detected in logs'}
                        </p>
                      </div>
                      <div className="bg-white/60 dark:bg-slate-900/40 rounded-2xl p-5 border border-emerald-200/50 dark:border-emerald-500/10">
                        <h4 className="text-xs font-black text-emerald-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                          <CheckCircle size={14} />
                          How It Recovered
                        </h4>
                        <p className="text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed">
                          {result.root_cause || 'System auto-recovered after transient failure'}
                        </p>
                      </div>
                      <div className="bg-white/60 dark:bg-slate-900/40 rounded-2xl p-5 border border-amber-200/50 dark:border-amber-500/10">
                        <h4 className="text-xs font-black text-amber-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                          <Info size={14} />
                          Monitoring Needed
                        </h4>
                        <p className="text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed">
                          Monitor logs for recurring patterns. If this issue repeats frequently, investigate the underlying cause.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Log Previews & Errors */}
                {result.previous_errors && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                    {['pangps', 'pangpa', 'event'].map(logType => {
                      const logErrors = result.previous_errors.filter(e => e.toLowerCase().includes(`[${logType}]`));
                      if (!result.logs_used?.includes(logType) && logErrors.length === 0) return null;
                      return (
                        <div key={logType} className="bg-slate-900/90 backdrop-blur-xl rounded-2xl p-5 border border-slate-800 shadow-xl">
                          <h4 className="text-blue-400 font-black uppercase mb-3 font-mono text-sm flex items-center gap-2">
                            <FileText size={16} />
                            {logType}.log Findings
                          </h4>
                          <div className="h-40 overflow-y-auto text-xs font-mono text-slate-300 space-y-2 scrollbar-thin scrollbar-thumb-slate-700">
                            {logErrors.length > 0 ? (
                              logErrors.map((e, i) => (
                                <div key={i} className="flex gap-2 text-amber-500">
                                  <span className="text-slate-600">⚠</span>
                                  <span className="break-all">{e.replace(/^\[.*?\]\s*/, '')}</span>
                                </div>
                              ))
                            ) : (
                              <div className="text-slate-500 italic flex items-center gap-2 mt-4"><CheckCircle size={14} className="text-emerald-500" /> No severe errors detected for this log</div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {result.status === 'not_relevant' && (
                  <div className="bg-slate-800 dark:bg-slate-900/80 border border-slate-700/50 rounded-[2rem] p-10 text-center shadow-lg animate-pulse shadow-slate-900/50">
                    <Shield className="w-20 h-20 text-slate-500 mx-auto mb-6" />
                    <h2 className="text-3xl font-black text-slate-300 dark:text-slate-400 uppercase tracking-widest">⚠ Not a GlobalProtect Issue</h2>
                    <p className="text-slate-400 dark:text-slate-500 mt-3 font-medium text-lg">Detected endpoint/application-level problem (e.g., Zoom/Teams). No VPN impact.</p>
                  </div>
                )}

                {/* Detected Issue Card */}
                <div className="bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-[2rem] shadow-xl border border-slate-200 dark:border-slate-800/50 overflow-hidden">
                  <div className="bg-amber-500/10 dark:bg-amber-500/5 px-8 py-5 border-b border-amber-100 dark:border-amber-500/10 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-amber-500/20 rounded-lg">
                        <AlertTriangle className="text-amber-600 dark:text-amber-500" size={24} />
                      </div>
                      <h2 className="text-amber-900 dark:text-amber-500 font-black uppercase tracking-widest">Anomaly Detected</h2>
                    </div>
                    {result.status === 'resolved' && (
                      <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-xs font-bold uppercase">Resolved State</span>
                    )}
                  </div>
                  <div className="p-10">
                    <p className="text-2xl font-bold text-slate-800 dark:text-slate-100 leading-relaxed font-mono">
                      <span className="text-blue-500 mr-2 opacity-50">&gt;</span>
                      {result.detected_issue}
                    </p>
                    {result.correlated_issue && result.correlated_issue !== result.detected_issue && (
                      <p className="mt-4 text-sm text-slate-500 dark:text-slate-400 font-medium border-l-2 border-blue-500/30 pl-4 italic">
                        Correlation: {result.correlated_issue}
                      </p>
                    )}
                    <div className="mt-6 flex items-center gap-3 flex-wrap">
                      {result.status && (
                        <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${result.status === 'resolved' ? 'bg-emerald-500/20 text-emerald-400' :
                          result.status === 'active' ? 'bg-red-500/20 text-red-400' :
                            'bg-slate-500/20 text-slate-400'
                          }`}>
                          {result.status}
                        </span>
                      )}
                      {result.confidence_score > 0 && (
                        <span className="px-3 py-1 bg-blue-500/10 text-blue-400 rounded-full text-xs font-mono font-bold">
                          Confidence: {(result.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                      {result.logs_used?.length > 0 && (
                        <span className="px-3 py-1 bg-slate-500/10 text-slate-400 rounded-full text-xs font-mono">
                          Logs: {result.logs_used.join(', ')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* AI Solution Card */}
                <div className="bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-[2rem] shadow-xl border border-slate-200 dark:border-slate-800/50 overflow-hidden">
                  <div className="bg-emerald-500/10 dark:bg-emerald-500/5 px-8 py-5 border-b border-emerald-100 dark:border-emerald-500/10 flex items-center gap-4">
                    <div className="p-2 bg-emerald-500/20 rounded-lg">
                      <CheckCircle className="text-emerald-600 dark:text-emerald-500" size={24} />
                    </div>
                    <h2 className="text-emerald-900 dark:text-emerald-500 font-black uppercase tracking-widest">Intelligence Synthesis</h2>
                  </div>
                  <div className="p-10 space-y-8">
                    {/* Root Cause Section */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-black text-blue-500 uppercase tracking-widest">Root Cause</h3>
                      <p className="text-lg text-slate-700 dark:text-slate-200 font-medium leading-relaxed">
                        {result.root_cause}
                      </p>
                    </div>

                    {/* User Impact Section */}
                    <div className="space-y-3">
                      <h3 className="text-sm font-black text-amber-500 uppercase tracking-widest">User Impact</h3>
                      <p className="text-lg text-slate-700 dark:text-slate-200 font-medium leading-relaxed italic">
                        {result.user_impact}
                      </p>
                    </div>

                    {/* Troubleshooting Steps Section */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-black text-emerald-500 uppercase tracking-widest">Remediation Steps</h3>
                      <div className="bg-slate-50 dark:bg-slate-800/50 rounded-2xl p-6 border border-slate-100 dark:border-slate-700/50">
                        <div className="text-slate-700 dark:text-slate-300 whitespace-pre-line leading-relaxed font-mono text-base">
                          {result.troubleshooting_steps}
                        </div>
                      </div>
                    </div>

                    {/* Technical Summary Section */}
                    <div className="pt-6 border-t border-slate-100 dark:border-slate-800/50">
                      <h3 className="text-sm font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-2">Technical Summary</h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400 font-medium italic">
                        {result.summary}
                      </p>
                    </div>
                  </div>
                </div>

                {/* KB Articles Card */}
                <div className="bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-[2rem] shadow-xl border border-slate-200 dark:border-slate-800/50 overflow-hidden">
                  <div className="bg-blue-500/10 dark:bg-blue-500/5 px-8 py-5 border-b border-slate-100 dark:border-slate-800/50 flex items-center gap-4">
                    <div className="p-2 bg-blue-500/20 rounded-lg">
                      <BookOpen className="text-blue-600 dark:text-blue-400" size={24} />
                    </div>
                    <h2 className="text-slate-900 dark:text-slate-100 font-black uppercase tracking-widest">Supporting Evidence</h2>
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-slate-800/50">
                    {result.related_kbs.map((kb, idx) => (
                      <a
                        key={idx}
                        href={kb.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between p-8 hover:bg-slate-50 dark:hover:bg-blue-500/5 transition-all group"
                      >
                        <div className="space-y-2">
                          <h3 className="text-lg font-bold text-slate-900 dark:text-white group-hover:text-blue-500 transition-colors flex items-center gap-3">
                            {kb.title}
                            <ExternalLink size={16} className="opacity-0 group-hover:opacity-100 transition-all -translate-y-1" />
                          </h3>
                          <p className="text-xs text-slate-500 dark:text-slate-500 font-mono uppercase tracking-widest">{kb.url}</p>
                        </div>
                        <div className="p-3 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 group-hover:bg-blue-500 group-hover:text-white transition-all">
                          <ExternalLink size={20} />
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
