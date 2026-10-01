import { useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";
import UploadZone from "@/components/UploadZone";
import PipelineOverlay from "@/components/PipelineOverlay";
import api, { apiErrorMessage } from "@/api/client";

export interface PdfProgress {
  step: string;
  page: number;
  total: number;
  message: string;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [pipelineComplete, setPipelineComplete] = useState(false);
  const [pdfProgress, setPdfProgress] = useState<PdfProgress | null>(null);
  const resultIdRef = useRef<number | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const navigate = useNavigate();

  const handleFileSelect = useCallback((f: File) => {
    setFile(f);
    if (f.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(f);
    } else {
      setPreview(null);
    }
  }, []);

  const handleClear = () => {
    setFile(null);
    setPreview(null);
    setError("");
    setPdfProgress(null);
  };

  const isPdf = file?.name?.toLowerCase().endsWith(".pdf") ?? false;

  /** Follow a background analysis job via SSE, with polling fallback */
  const connectSSE = useCallback((jobId: number) => {
    const token = localStorage.getItem("archvision_token");
    const url = `/api/analyses/${jobId}/progress?token=${encodeURIComponent(token || "")}`;
    const es = new EventSource(url);
    sseRef.current = es;

    es.onmessage = (event) => {
      try {
        const data: PdfProgress = JSON.parse(event.data);
        setPdfProgress(data);
        if (data.step === "done" || data.step === "completed") {
          es.close();
          sseRef.current = null;
          setPipelineComplete(true);
        } else if (data.step === "failed") {
          es.close();
          sseRef.current = null;
          setError("Analysis failed on the server.");
          setUploading(false);
        }
      } catch { /* ignore parse errors */ }
    };

    es.onerror = () => {
      es.close();
      sseRef.current = null;
      // Fallback: poll job status
      const poll = setInterval(async () => {
        try {
          const r = await api.get(`/analyses/${jobId}`);
          if (r.data.status === "completed") {
            clearInterval(poll);
            setPipelineComplete(true);
          } else if (r.data.status === "failed") {
            clearInterval(poll);
            setError(r.data.error_message || "Analysis failed.");
            setUploading(false);
          }
        } catch {
          clearInterval(poll);
          setError("Lost connection to server.");
          setUploading(false);
        }
      }, 3000);
    };
  }, []);

  const handleAnalyze = async () => {
    if (!file) return;
    setUploading(true);
    setPipelineComplete(false);
    setPdfProgress(null);
    resultIdRef.current = null;
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      // The server only stores the file and starts a background job, so the
      // upload itself is quick; analysis progress comes over SSE.
      const res = await api.post("/analyze", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });

      resultIdRef.current = res.data.id;

      if (res.data.status === "processing") {
        connectSSE(res.data.id);
      } else if (res.data.status === "failed") {
        setError(res.data.error_message || "Analysis failed.");
        setUploading(false);
      } else {
        setPipelineComplete(true);
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Analysis failed. Please try again."));
      setUploading(false);
      setPipelineComplete(false);
    }
  };

  const handleAnimationDone = useCallback(() => {
    if (resultIdRef.current != null) {
      navigate(`/analysis/${resultIdRef.current}`);
    }
  }, [navigate]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-white">Upload Floor Plan</h1>
        <p className="mt-1 text-sm text-[#94A3B8]">
          Upload a floor plan image or PDF brochure for AI-powered analysis
        </p>
      </div>

      <div className="rounded-xl border border-[rgba(56,189,248,0.15)] bg-[#0F172A]/60 backdrop-blur-xl p-6">
        <UploadZone
          onFileSelect={handleFileSelect}
          selectedFile={file}
          onClear={handleClear}
        />

        {error && (
          <div className="mt-4 rounded-lg border border-[#EF4444]/50 bg-[#EF4444]/10 px-4 py-2 text-sm text-[#EF4444]">
            {error}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            onClick={handleAnalyze}
            disabled={!file || uploading}
            className="btn-shimmer flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 text-white" />
                Analyze Floor Plan
              </>
            )}
          </button>
        </div>
      </div>

      {/* Pipeline processing overlay */}
      <PipelineOverlay
        visible={uploading}
        preview={preview}
        fileName={file?.name ?? ""}
        pipelineComplete={pipelineComplete}
        onAnimationDone={handleAnimationDone}
        isPdf={isPdf}
        pdfProgress={pdfProgress}
      />
    </div>
  );
}
