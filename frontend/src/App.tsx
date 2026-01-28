import { useEffect, useState } from "react";

const initialUploadStatus = { message: "No file selected.", tone: "idle" as const };
const initialQueryStatus = { message: "Waiting for a query.", tone: "idle" as const };
const initialSummaryStatus = { message: "No summary yet.", tone: "idle" as const };

type Tone = "idle" | "ok" | "warn" | "error";

type Status = {
  message: string;
  tone: Tone;
};

type QueryItem = {
  text: string;
  score?: number;
  metadata?: Record<string, unknown> | null;
};

type QueryResponse = {
  text_chunks: QueryItem[];
  captions: QueryItem[];
};

function setStatus(next: Status, setter: (value: Status) => void) {
  setter(next);
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<Status>(initialUploadStatus);
  const [queryStatus, setQueryStatus] = useState<Status>(initialQueryStatus);
  const [summaryStatus, setSummaryStatus] = useState<Status>(initialSummaryStatus);
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(null);
  const [lastUploaded, setLastUploaded] = useState<string | null>(null);
  const [processInfo, setProcessInfo] = useState<string>("-");
  const [languageInfo, setLanguageInfo] = useState<string>("-");
  const [sectionPatterns, setSectionPatterns] = useState<string[]>([]);
  const [queryText, setQueryText] = useState<string>("");
  const [results, setResults] = useState<QueryItem[]>([]);
  const [summary, setSummary] = useState<string>("");
  const [page, setPage] = useState<"home" | "patterns">(() => {
    return window.location.pathname.endsWith("/patterns") ? "patterns" : "home";
  });

  useEffect(() => {
    const onPop = () => {
      setPage(window.location.pathname.endsWith("/patterns") ? "patterns" : "home");
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = (next: "home" | "patterns") => {
    const basePath = "/app";
    const path = next === "patterns" ? `${basePath}/patterns` : `${basePath}`;
    window.history.pushState({}, "", path);
    setPage(next);
  };

  const applyFileList = (files: string[]) => {
    setAvailableFiles(files);
    setSelectedFilename((prev) => {
      if (prev && files.includes(prev)) {
        return prev;
      }
      return files[0] ?? null;
    });
  };

  const loadFiles = async () => {
    try {
      const res = await fetch("/backend/files/");
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const data = (await res.json()) as { files?: string[] };
      const files = Array.isArray(data.files) ? data.files : [];
      applyFileList(files);
    } catch {
      applyFileList([]);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0] ?? null;
    setFile(next);
    if (!next) {
      setStatus({ message: "No file selected.", tone: "idle" }, setUploadStatus);
      return;
    }
    setStatus({ message: "Ready to upload.", tone: "ok" }, setUploadStatus);
  };

  const handleUpload = async () => {
    if (!file) {
      setStatus({ message: "Select a PDF first.", tone: "warn" }, setUploadStatus);
      return;
    }

    try {
      setStatus({ message: "Uploading PDF...", tone: "idle" }, setUploadStatus);

      const formData = new FormData();
      formData.append("file", file);

      const uploadRes = await fetch("/backend/upload/", {
        method: "POST",
        body: formData
      });

      if (!uploadRes.ok) {
        throw new Error(await uploadRes.text());
      }

      const uploadData = await uploadRes.json();
      const uploadedName = uploadData.filename as string;
      setLastUploaded(uploadedName);
      setSelectedFilename(uploadedName);

      setStatus({ message: "Upload complete. Indexing...", tone: "ok" }, setUploadStatus);

      const processRes = await fetch(
        `/pdfworker/process/full/${encodeURIComponent(uploadedName)}`,
        { method: "POST" }
      );

      if (!processRes.ok) {
        throw new Error(await processRes.text());
      }

      const processData = await processRes.json();
      const pages = processData.pages ?? "?";
      const chunks = processData.chunks_indexed ?? "?";
      const captions = processData.captions_indexed ?? "?";
      const languageCode = processData.language ?? "und";
      const languageName = processData.language_name ?? "Unknown";
      const detectedPatterns = Array.isArray(processData.section_patterns)
        ? (processData.section_patterns as string[])
        : [];
      setProcessInfo(`Pages: ${pages} | Chunks: ${chunks} | Captions: ${captions}`);
      setLanguageInfo(`${languageCode} (${languageName})`);
      setSectionPatterns(detectedPatterns);
      setStatus({ message: "Indexed successfully.", tone: "ok" }, setUploadStatus);
      await loadFiles();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setStatus({ message: `Failed: ${message}`, tone: "error" }, setUploadStatus);
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) {
      setStatus({ message: "Type a question first.", tone: "warn" }, setQueryStatus);
      return;
    }
    if (!selectedFilename) {
      setStatus({ message: "Select a file first.", tone: "warn" }, setQueryStatus);
      return;
    }

    try {
      setStatus({ message: "Searching...", tone: "idle" }, setQueryStatus);
      setStatus({ message: "No summary yet.", tone: "idle" }, setSummaryStatus);
      setSummary("");
      setResults([]);

      const res = await fetch("/backend/query/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: queryText, top_k: 20 })
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = (await res.json()) as QueryResponse;
      const items = [...data.text_chunks, ...data.captions];

      const filtered = items.filter((item) => {
        const meta = item.metadata ?? {};
        const metaAny = meta as Record<string, unknown>;
        const filenameMatch = metaAny.filename === selectedFilename;
        const sourcePdf = metaAny.source_pdf;
        const sourceMatch =
          typeof sourcePdf === "string" &&
          !!selectedFilename &&
          sourcePdf.includes(selectedFilename);
        return filenameMatch || sourceMatch;
      });

      if (!filtered.length) {
        setStatus(
          { message: "No matches for this file in the top results.", tone: "warn" },
          setQueryStatus
        );
        return;
      }

      setResults(filtered);
      setStatus({ message: `Showing ${filtered.length} results.`, tone: "ok" }, setQueryStatus);
      void summarizeResults(filtered);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Query failed";
      setStatus({ message: `Failed: ${message}`, tone: "error" }, setQueryStatus);
    }
  };

  const summarizeResults = async (items: QueryItem[]) => {
    const texts = items.map((item) => item.text).filter((text) => !!text);
    if (!texts.length) {
      setStatus({ message: "No text to summarize.", tone: "warn" }, setSummaryStatus);
      return;
    }

    try {
      setStatus({ message: "Summarizing top results...", tone: "idle" }, setSummaryStatus);
      const res = await fetch("/backend/summarize_texts/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texts, query: queryText })
      });

      if (!res.ok) {
        throw new Error(await res.text());
      }

      const data = (await res.json()) as { summary?: string };
      setSummary(data.summary ?? "");
      setStatus({ message: "Summary ready.", tone: "ok" }, setSummaryStatus);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Summary failed";
      setStatus({ message: `Failed: ${message}`, tone: "error" }, setSummaryStatus);
    }
  };

  return (
    <div className="app">
      <div className="backdrop" />
      <div className="grid">
        <header className="hero">
          <span className="badge">PDF LAB</span>
          <h1>Upload, index, and query your PDFs.</h1>
          <p>
            Send a PDF to the backend, run the full pipeline, then query the indexed
            chunks and captions.
          </p>
          <div className="hero-meta">
            <div>
              <span className="label">API Root</span>
              <span className="value">/backend</span>
            </div>
            <div>
              <span className="label">Worker Root</span>
              <span className="value">/pdfworker</span>
            </div>
          </div>
          <div className="nav">
            <button
              type="button"
              className={page === "home" ? "active" : ""}
              onClick={() => navigate("home")}
            >
              Workspace
            </button>
            <button
              type="button"
              className={page === "patterns" ? "active" : ""}
              onClick={() => navigate("patterns")}
            >
              Section Patterns
            </button>
          </div>
        </header>

        {page === "patterns" ? (
          <section className="panel">
            <h2>Detected section patterns</h2>
            <p className="muted">
              These patterns are inferred from the PDF content and used to keep article or
              section boundaries intact during chunking.
            </p>
            <div className="details">
              <div>
                <span className="label">Selected file</span>
                <span className="value">{selectedFilename ?? "-"}</span>
              </div>
              <div>
                <span className="label">Detected language</span>
                <span className="value">{languageInfo}</span>
              </div>
            </div>
            {sectionPatterns.length ? (
              <ul className="pattern-list">
                {sectionPatterns.map((pattern) => (
                  <li key={pattern}>
                    <code>{pattern}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="status tone-warn">
                No patterns detected yet. Upload &amp; index a PDF to see them here.
              </div>
            )}
          </section>
        ) : (
        <>
          <section className="panel">
          <h2>1. Upload and index</h2>
          <p className="muted">Upload a PDF, then we chunk and embed it.</p>
          <div className="row">
            <input type="file" accept="application/pdf" onChange={handleFileChange} />
            <button type="button" onClick={handleUpload}>
              Upload &amp; index
            </button>
          </div>
          <div className={`status tone-${uploadStatus.tone}`}>{uploadStatus.message}</div>
          <div className="row">
            <select
              value={selectedFilename ?? ""}
              onChange={(event) => setSelectedFilename(event.target.value)}
            >
              <option value="" disabled>
                Select an uploaded file
              </option>
              {availableFiles.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <button type="button" onClick={loadFiles}>
              Refresh list
            </button>
          </div>
          <div className="details">
            <div>
              <span className="label">Selected file</span>
              <span className="value">{selectedFilename ?? "-"}</span>
            </div>
            <div>
              <span className="label">Last uploaded</span>
              <span className="value">{lastUploaded ?? "-"}</span>
            </div>
            <div>
              <span className="label">Last processing</span>
              <span className="value">{processInfo}</span>
            </div>
            <div>
              <span className="label">Detected language</span>
              <span className="value">{languageInfo}</span>
            </div>
          </div>
          </section>

          <section className="panel">
          <h2>2. Ask your document</h2>
          <p className="muted">We filter results to the selected file.</p>
          <textarea
            rows={4}
            placeholder="Ask something about the PDF..."
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
          />
          <div className="row">
            <button type="button" onClick={handleQuery}>
              Search
            </button>
            <span className={`status tone-${queryStatus.tone}`}>{queryStatus.message}</span>
          </div>
          <div className="summary">
            <h3>Summary of top results</h3>
            <span className={`status tone-${summaryStatus.tone}`}>{summaryStatus.message}</span>
            {summary && <p>{summary}</p>}
          </div>
          <div className="results">
            {results.map((item, idx) => (
              <div key={`${idx}-${item.score}`} className="result-card">
                <h4>
                  Result {idx + 1} ? score {item.score?.toFixed(4) ?? "n/a"}
                </h4>
                <p>{item.text.length > 280 ? `${item.text.slice(0, 280)}...` : item.text}</p>
              </div>
            ))}
          </div>
          </section>

          <aside className="panel tips">
          <h3>Tips</h3>
          <ul>
            <li>Large PDFs take time to embed; wait for the success status.</li>
            <li>Try broad queries if you get empty results.</li>
            <li>Elasticsearch must be running before indexing.</li>
          </ul>
          </aside>
        </>
        )}
      </div>
    </div>
  );
}
