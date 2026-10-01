import { useCallback, useState } from "react";
import { Upload, FileImage, FileText, X } from "lucide-react";

interface UploadZoneProps {
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
  onClear: () => void;
}

const ALLOWED_TYPES = [
  "image/png",
  "image/jpeg",
  "image/jpg",
  "image/bmp",
  "image/tiff",
  "application/pdf",
];

export default function UploadZone({ onFileSelect, selectedFile, onClear }: UploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        return;
      }
      onFileSelect(file);

      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => setPreview(e.target?.result as string);
        reader.readAsDataURL(file);
      } else {
        setPreview(null);
      }
    },
    [onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleClear = () => {
    setPreview(null);
    onClear();
  };

  const isPdf = selectedFile?.type === "application/pdf";

  if (selectedFile) {
    return (
      <div className="rounded-xl border border-[#0EA5E9]/30 bg-[#0EA5E9]/5 p-6">
        <div className="flex items-start gap-4">
          {/* Preview / Icon */}
          <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[rgba(56,189,248,0.15)] bg-slate-900/40 backdrop-blur-xl">
            {preview ? (
              <img src={preview} alt="Preview" className="h-full w-full object-cover" />
            ) : (
              <FileText className="h-8 w-8 text-[#0EA5E9]" />
            )}
          </div>

          {/* Details */}
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-white">{selectedFile.name}</p>
            <p className="mt-1 text-xs text-[#94A3B8]">
              {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB &middot;{" "}
              <span className={`font-medium ${isPdf ? "text-[#FB923C]" : "text-[#22D3EE]"}`}>
                {isPdf ? "PDF Document" : "Image File"}
              </span>
            </p>
            <div className="mt-2 flex items-center gap-1.5">
              {isPdf ? (
                <FileText className="h-3.5 w-3.5 text-[#FB923C]" />
              ) : (
                <FileImage className="h-3.5 w-3.5 text-[#22D3EE]" />
              )}
              <span className="text-xs text-[#94A3B8]">
                {isPdf ? "PDF will be processed: extract floor plans then analyze" : "Image will be analyzed directly"}
              </span>
            </div>
          </div>

          {/* Remove */}
          <button
            onClick={handleClear}
            className="rounded-lg p-1.5 text-[#94A3B8] transition-colors hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
          >
            <X className="h-4 w-4 text-[#EF4444]" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={`relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-all duration-300 ${
        isDragOver
          ? "border-[#0EA5E9] bg-[#0EA5E9]/5 shadow-lg shadow-[#0EA5E9]/10"
          : "border-[rgba(56,189,248,0.15)] hover:border-[#0EA5E9]/40 hover:bg-[#CBD5E1]/10"
      }`}
    >
      <input
        type="file"
        accept=".png,.jpg,.jpeg,.bmp,.tiff,.tif,.pdf"
        onChange={handleInputChange}
        className="absolute inset-0 cursor-pointer opacity-0"
      />
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#0EA5E9]/10">
        <Upload className={`h-8 w-8 transition-colors ${isDragOver ? "text-[#0EA5E9]" : "text-[#94A3B8]"}`} />
      </div>
      <p className="mt-4 text-sm font-medium text-white">
        {isDragOver ? "Drop your file here" : "Drag & drop your floor plan"}
      </p>
      <p className="mt-1 text-xs text-[#94A3B8]">or click to browse &middot; PNG, JPG, PDF supported</p>
    </div>
  );
}
