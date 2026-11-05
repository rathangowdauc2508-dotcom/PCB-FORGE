import { useState, useCallback, useRef } from 'react';
import { useOrchestrationStore } from '../../stores/orchestrationStore';

type FileSlot = 'errorLog' | 'designImage' | 'testedImage' | 'designRefPdf' | 'specDoc';

interface ClassifiedFile {
  id: string;
  fileId: string;
  slot: FileSlot;
  name: string;
  preview?: string;
}

const SLOT_LABELS: Record<FileSlot, string> = {
  errorLog: 'Error Log',
  designImage: 'CAD / Reference Image',
  testedImage: 'Tested Board Photo',
  designRefPdf: 'Design Reference',
  specDoc: 'Spec Document',
};

const SLOT_COLORS: Record<FileSlot, string> = {
  errorLog: 'var(--danger)',
  designImage: 'var(--accent)',
  testedImage: 'var(--warning)',
  designRefPdf: 'var(--accent)',
  specDoc: 'var(--text-muted)',
};

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      resolve(dataUrl.split(',')[1] || dataUrl);
    };
    reader.onerror = () => reject(reader.error ?? new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

function classifyFile(
  file: File,
  occupied: Set<FileSlot>,
  hasDesignImage: boolean,
  hasTestedImage: boolean,
): FileSlot | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  const isImage = ['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(ext);
  const isText = ['log', 'txt'].includes(ext);
  const isPdf = ext === 'pdf';
  const name = file.name.toLowerCase();

  if (isText) {
    if (!occupied.has('errorLog')) return 'errorLog';
    return 'specDoc';
  }
  if (isImage) {
    const isCad = name.includes('cad') || name.includes('schematic') || name.includes('design') || name.includes('template');
    const isDefect = name.includes('defect') || name.includes('tested') || name.includes('pcb');

    if (isCad && !occupied.has('designImage')) return 'designImage';
    if (isDefect && !occupied.has('testedImage')) return 'testedImage';
    if (!occupied.has('designImage') && !hasDesignImage && !hasTestedImage) return 'designImage';
    if (!occupied.has('testedImage') && hasDesignImage) return 'testedImage';
    if (!occupied.has('designImage') && hasTestedImage) return 'designImage';
    if (!occupied.has('testedImage')) return 'testedImage';
    return null;
  }
  if (isPdf) {
    const isSpecPdf = name.includes('datasheet') || name.includes('spec');
    const isDesignPdf = name.includes('pinout') || name.includes('schematic') || name.includes('cad');

    if (isDesignPdf) return 'designRefPdf';
    if (isSpecPdf) return 'specDoc';
    if (!occupied.has('specDoc')) return 'specDoc';
    if (!occupied.has('designRefPdf')) return 'designRefPdf';
    return null;
  }
  return null;
}

function makeMimeType(ext: string, type: string): string {
  if (type) return type;
  if (ext === 'pdf') return 'application/pdf';
  if (['png', 'jpg', 'jpeg', 'bmp', 'webp'].includes(ext)) return 'image/png';
  return 'text/plain';
}

function makeFileId(slot: FileSlot): string {
  return `${slot}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function InputPanel() {
  const {
    errorLog,
    designImageB64,
    testedImageB64,
    errorLogFile,
    designImageFile,
    testedImageFile,
    setErrorLog,
    setDesignImage,
    setTestedImage,
    addDesignReferenceFile,
    removeDesignReferenceFile,
    setErrorLogFile,
    setDesignImageFile,
    setTestedImageFile,
    addSpecFile,
    removeSpecFile,
    inputCollapsed, setInputCollapsed,
    runCustom, runDemo, isRunning,
  } = useOrchestrationStore();

  const collapsed = inputCollapsed;
  const setCollapsed = setInputCollapsed;
  const [isDragging, setIsDragging] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [files, setFiles] = useState<ClassifiedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  const occupiedSlots = useCallback((): Set<FileSlot> => {
    const s = new Set<FileSlot>();
    if (errorLogFile) s.add('errorLog');
    if (designImageFile || designImageB64) s.add('designImage');
    if (testedImageFile || testedImageB64) s.add('testedImage');
    return s;
  }, [designImageB64, testedImageB64, errorLogFile, designImageFile, testedImageFile]);

  const upsertChip = useCallback((chip: ClassifiedFile) => {
    setFiles((prev) => {
      if (chip.slot === 'specDoc' || chip.slot === 'designRefPdf') return [...prev, chip];
      const idx = prev.findIndex((item) => item.slot === chip.slot);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = chip;
        return next;
      }
      return [...prev, chip];
    });
  }, []);

  const processFiles = useCallback((fileList: FileList) => {
    const occupied = occupiedSlots();
    const rejectedFiles: string[] = [];
    const queued = Array.from(fileList).map((file) => {
      const hasDesignImage = Boolean(occupied.has('designImage'));
      const hasTestedImage = Boolean(occupied.has('testedImage'));
      const slot = classifyFile(file, occupied, hasDesignImage, hasTestedImage);
      if (!slot) {
        rejectedFiles.push(file.name);
        return null;
      }

      if (slot === 'errorLog' || slot === 'designImage' || slot === 'testedImage') {
        occupied.add(slot);
      }
      const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
      const id = makeFileId(slot);
      return {
        id,
        fileId: id,
        slot,
        file,
        ext,
        mimeType: makeMimeType(ext, file.type),
      };
    }).filter((v): v is {
      id: string;
      fileId: string;
      slot: FileSlot;
      file: File;
      ext: string;
      mimeType: string;
    } => v !== null);

    if (rejectedFiles.length) {
      window.alert(
        `Unsupported files skipped: ${rejectedFiles.join(', ')}. `
        + 'Use expected names: '
        + '.log/.txt (error log), '
        + '*.png with cad/template/design for CAD, '
        + '*.png with defect/tested/pcb for defect image, '
        + '*datasheet/*spec*.pdf for spec, '
        + '*pinout/schematic/cad*.pdf for design reference.',
      );
    }

    if (!queued.length) return;

    Promise.all(
      queued.map(async (item) => {
        const b64 = await fileToBase64(item.file);
        const canonicalFileName = item.slot === 'designImage'
          ? 'cad.png'
          : item.slot === 'testedImage'
            ? 'defect.png'
            : item.slot === 'designRefPdf'
              ? item.file.name
            : item.file.name;
        const uploaded = {
          file_name: canonicalFileName,
          mime_type: item.mimeType,
          base64_data: b64,
          file_id: item.fileId,
        };

        upsertChip({
          id: item.id,
          fileId: item.fileId,
          slot: item.slot,
          name: canonicalFileName,
          preview: item.slot === 'designImage' || item.slot === 'testedImage' ? b64 : undefined,
        });

        if (item.slot === 'errorLog') {
          setErrorLog(await item.file.text());
          setErrorLogFile(uploaded);
          return;
        }
        if (item.slot === 'designImage') {
          setDesignImage(b64);
          setDesignImageFile(uploaded);
          return;
        }
        if (item.slot === 'testedImage') {
          setTestedImage(b64);
          setTestedImageFile(uploaded);
          return;
        }
        if (item.slot === 'designRefPdf') {
          addDesignReferenceFile(uploaded);
          return;
        }
        addSpecFile(uploaded);
      }),
    ).catch(() => {
      // File parsing errors are surfaced by missing outputs and local validation.
    });
  }, [
    occupiedSlots,
    addSpecFile,
    upsertChip,
    setErrorLog,
    setDesignImage,
    setTestedImage,
    addDesignReferenceFile,
    setErrorLogFile,
    setDesignImageFile,
    setTestedImageFile,
  ]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (e.dataTransfer.files?.length) processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const removeFile = useCallback((file: ClassifiedFile) => {
    if (file.slot === 'errorLog') {
      setErrorLog('');
      setErrorLogFile(null);
    }
    if (file.slot === 'designImage') {
      setDesignImage('');
      setDesignImageFile(null);
    }
    if (file.slot === 'testedImage') {
      setTestedImage('');
      setTestedImageFile(null);
    }
    if (file.slot === 'designRefPdf') {
      removeDesignReferenceFile(file.fileId);
    }
    if (file.slot === 'specDoc') {
      removeSpecFile(file.fileId);
    }

    setFiles((prev) => prev.filter((f) => f.id !== file.id));
  }, [
    setErrorLog,
    setDesignImage,
    setTestedImage,
    setErrorLogFile,
    setDesignImageFile,
    setTestedImageFile,
    removeDesignReferenceFile,
    removeSpecFile,
  ]);

  const fileCount = files.length;

  return (
    <section className="card" style={{ overflow: 'hidden' }}>
      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          padding: '10px 20px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: collapsed ? 'none' : '1px solid var(--border)',
          background: 'var(--card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: '0.8125rem', fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--accent)',
          }}>INPUT</span>
          <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            {fileCount > 0 ? `${fileCount} file${fileCount > 1 ? 's' : ''} loaded` : 'Drop files to begin'}
          </span>
        </div>
        <span style={{
          fontSize: '0.75rem', color: 'var(--text-muted)',
          transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)',
          transition: 'transform 0.2s',
        }}>&#9650;</span>
      </div>

      {!collapsed && (
        <div style={{ padding: 'var(--space-md)', animation: 'fadeUp 0.3s ease' }}>
          <div
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `1.5px dashed ${isDragging ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 'var(--radius-sm)',
              padding: fileCount > 0 ? '14px 16px' : '28px 16px',
              background: isDragging ? 'var(--accent-light)' : 'var(--card)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              textAlign: 'center',
            }}
          >
            {fileCount === 0 && !isDragging && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
                <div style={{ fontSize: '1.5rem', color: 'var(--text-muted)', opacity: 0.4, lineHeight: 1 }}>
                  &#8593;
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  Drop all files here
                </div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', opacity: 0.5 }}>
                  .log .txt .png .jpg .pdf — auto-classified
                </div>
              </div>
            )}

            {isDragging && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <div style={{ fontSize: '0.875rem', color: 'var(--accent)', fontWeight: 600 }}>
                  Drop to add
                </div>
              </div>
            )}

            {fileCount > 0 && !isDragging && (
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)',
                  justifyContent: 'center',
                }}
              >
                {files.map((f) => (
                  <div key={f.id} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '6px 10px',
                    borderRadius: 'var(--radius-xs)',
                    background: 'var(--bg-alt)',
                    border: '1px solid var(--border)',
                    fontSize: '0.75rem',
                  }}>
                    {f.preview && (
                      <img
                        src={`data:image/png;base64,${f.preview}`}
                        alt=""
                        style={{ width: 24, height: 24, borderRadius: 3, objectFit: 'cover' }}
                      />
                    )}
                    <span style={{
                      color: SLOT_COLORS[f.slot], fontWeight: 600, fontSize: '0.625rem',
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                    }}>
                      {SLOT_LABELS[f.slot]}
                    </span>
                    <span style={{
                      color: 'var(--text-secondary)',
                      maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {f.name}
                    </span>
                    <button
                      onClick={() => removeFile(f)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-muted)', fontSize: '0.625rem',
                        padding: '0 2px', lineHeight: 1,
                      }}
                    >&#10005;</button>
                  </div>
                ))}

                <div style={{
                  display: 'flex', alignItems: 'center',
                  padding: '6px 10px', borderRadius: 'var(--radius-xs)',
                  border: '1px dashed var(--border)',
                  fontSize: '0.6875rem', color: 'var(--text-muted)',
                }}>
                  + Drop more
                </div>
              </div>
            )}

            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".log,.txt,.png,.jpg,.jpeg,.bmp,.webp,.pdf"
              onChange={(e) => {
                if (e.target.files?.length) processFiles(e.target.files);
                e.target.value = '';
              }}
              style={{ display: 'none' }}
            />
          </div>

          <div style={{ marginTop: 'var(--space-sm)' }}>
            <button
              onClick={() => setShowTextInput(!showTextInput)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4,
                color: 'var(--text-muted)', fontSize: '0.6875rem', fontWeight: 500,
                padding: '2px 0',
              }}
            >
              <span style={{
                transform: showTextInput ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 0.2s', display: 'inline-block',
              }}>&#9656;</span>
              Or paste error log directly
            </button>
            {showTextInput && (
              <div style={{ marginTop: 'var(--space-sm)', animation: 'fadeUp 0.2s ease' }}>
                <textarea
                  rows={4}
                  placeholder="[ERROR] I2C Bus Arbitration Lost - SDA line held LOW..."
                  value={errorLog}
                  onChange={(e) => {
                    setErrorLog(e.target.value);
                    setErrorLogFile(null);
                  }}
                  style={{ fontSize: '0.75rem' }}
                />
              </div>
            )}
          </div>
          <div style={{ marginTop: 'var(--space-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
              Use your own design image and a photo of the assembled board.
            </span>
            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button className="btn" disabled={isRunning} onClick={runDemo} title="Shows a preloaded sample report, not an analysis of your upload">
                Show sample report
              </button>
              <button className="btn btn-accent" disabled={isRunning} onClick={runCustom}>
                {isRunning ? 'Analyzing…' : 'Inspect my PCB'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}



