"use client";

import { useRef, useState } from "react";
import { Upload } from "lucide-react";

import { cn } from "@/lib/utils";

export const ACCEPT = ".pdf,.docx,.txt,.md,.markdown,.vtt,.srt,.csv,.json,.html,.htm";

export function DropZone({ files, onFiles, multiple = true }: { files: File[]; onFiles: (f: File[]) => void; multiple?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        onFiles(Array.from(e.dataTransfer.files).slice(0, multiple ? 20 : 1));
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed border-ink px-6 py-8 text-center",
        over ? "bg-acid" : "bg-white hover:bg-paper-2",
      )}
    >
      <Upload className="size-6" />
      {files.length ? (
        <ul className="font-mono text-xs">{files.map((f) => <li key={f.name}>{f.name}</li>)}</ul>
      ) : (
        <>
          <p className="font-bold">Drop files or click to browse</p>
          <p className="label text-[10px] text-muted">PDF · DOCX · TXT · MD · VTT · SRT · HTML</p>
        </>
      )}
      <input
        ref={input}
        type="file"
        hidden
        multiple={multiple}
        accept={ACCEPT}
        onChange={(e) => onFiles(Array.from(e.target.files ?? []))}
      />
    </div>
  );
}
