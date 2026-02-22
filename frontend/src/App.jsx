import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, FileText, CheckCircle, ExternalLink, AlertTriangle, Loader2, BookOpen, Info, Sun, Moon, Shield, Terminal, Zap } from 'lucide-react';

const API_URL = 'http://localhost:8000/api';

function App() {
  const [file, setFile] = useState(null);
  const [pastedText, setPastedText] = useState('');
  const [directIssue, setDirectIssue] = useState('');
  const [activeTab, setActiveTab] = useState('upload');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [loadingPhaseIndex, setLoadingPhaseIndex] = useState(0);

  const loadingPhases = [
    'Log preprocessing and noise reduction',
    'Scenario intelligence and pattern mapping',
    'KB vector retrieval and ranking',
    'Neural remediation synthesis'
  ];

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    if (!loading) {
      setLoadingPhaseIndex(0);
      return;
    }

    setLoadingPhaseIndex(0);

    const timeouts = [
      setTimeout(() => setLoadingPhaseIndex(1), 700),
      setTimeout(() => setLoadingPhaseIndex(2), 1500),
      setTimeout(() => setLoadingPhaseIndex(3), 2600)
    ];

    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, [loading]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPastedText('');
      setDirectIssue('');
      setResult(null);
      setError(null);
    }
  };

  const handlePaste = (e) => {
    if (activeTab === 'upload') {
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
        }
      }
    }
  };

  const handleUpload = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      let response;
      if (activeTab === 'upload') {
        if (!file && !pastedText) {
          throw new Error('Please upload a file or paste log content');
        }
        const formData = new FormData();
        if (file) {
          formData.append('file', file);
        } else if (pastedText) {
          const blob = new Blob([pastedText], { type: 'text/plain' });
          const virtualFile = new File([blob], 'pasted_log.txt', { type: 'text/plain' });
          formData.append('file', virtualFile);
        }
        response = await axios.post(`${API_URL}/analyze`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else {
        if (!directIssue.trim()) {
          throw new Error('Please enter an error or issue description');
        }
        response = await axios.post(`${API_URL}/analyze-issue`, {
          issue: directIssue
        });
      }
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed');
      console.error(err);
    } finally {
      setLoading(false);
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
            PAN-OS <span className="text-blue-600 dark:text-blue-400">CyberOps</span> Analyzer
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
                  className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                    activeTab === 'upload'
                      ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <Upload size={16} />
                  Log Data
                </button>
                <button
                  onClick={() => setActiveTab('direct')}
                  className={`flex-1 py-2 px-4 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                    activeTab === 'direct'
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
                  className={`relative border-2 border-dashed rounded-2xl p-10 transition-all cursor-pointer group flex flex-col items-center justify-center text-center ${
                    file || pastedText 
                      ? 'border-blue-400 dark:border-blue-500/50 bg-blue-50/50 dark:bg-blue-500/5' 
                      : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/50 hover:bg-slate-100 dark:hover:bg-slate-900/50'
                  }`}
                >
                  <input 
                    type="file" 
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
                    onChange={handleFileChange}
                    accept=".log,.txt"
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

              <button
                onClick={handleUpload}
                disabled={(activeTab === 'upload' ? (!file && !pastedText) : !directIssue.trim()) || loading}
                className={`mt-8 w-full py-4 px-6 rounded-2xl font-black text-lg tracking-wider uppercase flex items-center justify-center gap-3 transition-all duration-300 ${
                  (activeTab === 'upload' ? (!file && !pastedText) : !directIssue.trim()) || loading 
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

            {loading && (
              <div className="bg-white dark:bg-slate-900/50 rounded-[2rem] border border-slate-200 dark:border-slate-800 p-32 text-center relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-500/5 to-transparent animate-shimmer" />
                <Loader2 className="animate-spin text-blue-500 w-16 h-16 mx-auto mb-8" />
                <h3 className="text-slate-800 dark:text-white font-black text-3xl mb-4">Analysis pipeline in progress</h3>
                <p className="text-slate-500 dark:text-slate-400 font-mono uppercase tracking-widest text-sm animate-pulse">
                  {loadingPhases[loadingPhaseIndex]}
                </p>
              </div>
            )}

            {result && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-1000">
                {/* Detected Issue Card */}
                <div className="bg-white dark:bg-slate-900/50 backdrop-blur-xl rounded-[2rem] shadow-xl border border-slate-200 dark:border-slate-800/50 overflow-hidden">
                  <div className="bg-amber-500/10 dark:bg-amber-500/5 px-8 py-5 border-b border-amber-100 dark:border-amber-500/10 flex items-center gap-4">
                    <div className="p-2 bg-amber-500/20 rounded-lg">
                      <AlertTriangle className="text-amber-600 dark:text-amber-500" size={24} />
                    </div>
                    <h2 className="text-amber-900 dark:text-amber-500 font-black uppercase tracking-widest">Anomaly Detected</h2>
                  </div>
                  <div className="p-10">
                    <p className="text-2xl font-bold text-slate-800 dark:text-slate-100 leading-relaxed font-mono">
                      <span className="text-blue-500 mr-2 opacity-50">&gt;</span>
                      {result.detected_issue}
                    </p>
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
