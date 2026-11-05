import { useEffect, useRef, useState } from 'react';
import Header from './components/layout/Header';
import PageLayout from './components/layout/PageLayout';
import { api, type PCBDetectorStatus } from './api/client';
import type { PCBDetectionResponse } from './types/api';
import { useOrchestrationStore } from './stores/orchestrationStore';

type ReviewEngine = 'auto' | 'trained' | 'gemini';

async function imageToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.onerror = () => reject(new Error('Could not read this image.'));
    reader.readAsDataURL(file);
  });
}

function displayName(name: string): string {
  return name
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [engine, setEngine] = useState<ReviewEngine>('auto');
  const [engineStatus, setEngineStatus] = useState<PCBDetectorStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<PCBDetectionResponse | null>(null);

  useEffect(() => () => {
    if (preview.startsWith('blob:')) URL.revokeObjectURL(preview);
  }, [preview]);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const [health, status] = await Promise.all([api.health(), api.pcbDetectorStatus()]);
        if (!active) return;
        useOrchestrationStore.setState({ backendAvailable: health.status === 'ok' });
        setEngineStatus(status);
      } catch {
        if (active) {
          useOrchestrationStore.setState({ backendAvailable: false });
          setEngineStatus(null);
        }
      } finally {
        if (active) setChecking(false);
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const acceptFile = (next: File | undefined) => {
    if (!next) return;
    if (!next.type.startsWith('image/')) {
      setError('Choose a PCB photo in PNG, JPG, or WEBP format.');
      return;
    }
    if (next.size > 20 * 1024 * 1024) {
      setError('This image is over 20 MB. Choose a smaller photo.');
      return;
    }
    setFile(next);
    setPreview(URL.createObjectURL(next));
    setResult(null);
    setError('');
  };

  const inspect = async () => {
    if (!file) {
      setError('Choose a clear PCB photo first.');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const base64_data = await imageToBase64(file);
      const response = await api.detectPhotoDefects({
        mime_type: file.type || 'image/jpeg',
        base64_data,
      }, engine);
      setResult(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Inspection could not be completed.');
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setFile(null);
    setPreview('');
    setResult(null);
    setError('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const trainedReady = Boolean(engineStatus?.yolo_ready);
  const geminiReady = Boolean(engineStatus?.gemini_available ?? engineStatus?.mode === 'legacy-gemma');

  return (
    <>
      <Header />
      <PageLayout>
        <section className="inspection-hero card">
          <div className="inspection-eyebrow"><span className="hero-spark" aria-hidden="true">✳</span> PCB FORGE · VISUAL QUALITY CHECK</div>
          <h1>Inspect a PCB photo.</h1>
          <p>Upload one clear board image to locate suspected visible defects. Review the marked areas before making an engineering decision.</p>
          <div className="inspection-trust-row">
            <span>One photo to start</span><span>Annotated findings</span><span>Engineer verifies</span>
          </div>
        </section>

        {checking && <div className="notice">Connecting to the inspection service…</div>}
        {!checking && !engineStatus && <div className="notice notice-error" role="alert">Inspection service is offline. Start the PCB Forge backend, then refresh this page.</div>}
        {error && <div className="notice notice-error" role="alert">{error}</div>}

        <section className="card photo-inspector">
          <div className="photo-inspector-heading">
            <div><div className="inspection-eyebrow">INSPECTION INPUT</div><h2>PCB photo</h2></div>
            {file && <button className="btn" type="button" onClick={reset} disabled={busy}>Remove photo</button>}
          </div>

          <input
            ref={inputRef}
            className="visually-hidden-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(event) => acceptFile(event.target.files?.[0])}
          />
          <button
            type="button"
            className={`photo-dropzone${dragging ? ' is-dragging' : ''}${preview ? ' has-preview' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFile(event.dataTransfer.files?.[0]); }}
            aria-label="Choose or drop a PCB photo"
          >
            {preview ? <>
              <img src={preview} alt="Selected PCB to inspect" />
              <span className="photo-file-label">{file?.name} · click to replace</span>
            </> : <>
              <span className="upload-glyph" aria-hidden="true">↑</span>
              <strong>Drop a PCB photo here or browse</strong>
              <span>PNG, JPG, or WEBP · up to 20 MB</span>
            </>}
          </button>

          <div className="photo-inspector-controls">
            <div className="engine-control">
              <label htmlFor="review-engine">Review engine</label>
              <select id="review-engine" value={engine} onChange={(event) => setEngine(event.target.value as ReviewEngine)} disabled={busy}>
                <option value="auto">Automatic · trained model first</option>
                <option value="trained" disabled={!trainedReady}>Trained PCB detector{trainedReady ? '' : ' · weights unavailable'}</option>
                <option value="gemini" disabled={!geminiReady}>Gemini vision{geminiReady ? '' : ' · API unavailable'}</option>
              </select>
            </div>
            <button className="btn btn-accent inspect-button" type="button" onClick={inspect} disabled={!file || busy || !engineStatus}>
              {busy ? <><span className="spinner" /> Inspecting photo…</> : 'Inspect PCB'}
            </button>
          </div>
          {engineStatus && <p className="inspection-footnote">
            {trainedReady ? `Trained detector ready · ${engineStatus.weights_path.split(/[\\/]/).pop()}` : 'Trained detector weights are not configured.'}
            {' '}{geminiReady ? 'Gemini vision is available as an alternate review.' : 'Gemini vision is not configured.'}
          </p>}
        </section>

        {result && <section className="card inspection-result" aria-live="polite">
          <div className="result-heading">
            <div><div className="inspection-eyebrow">INSPECTION RESULT</div><h2>{result.detections.length ? `${result.detections.length} suspected finding${result.detections.length === 1 ? '' : 's'}` : 'No visible defects detected'}</h2></div>
            <div className="result-meta"><strong>{result.model_name}</strong><span>{result.inference_ms} ms</span></div>
          </div>
          <p className="result-caveat">These are model findings for human review. A photo cannot verify electrical continuity or hidden-layer faults.</p>
          <div className="result-image-wrap"><img src={`data:image/jpeg;base64,${result.annotated_image_base64}`} alt="PCB photo with suspected defect regions marked" /></div>
          {result.detections.length > 0 ? <ul className="finding-list">
            {result.detections.map((finding) => <li key={finding.id}>
              <span className="finding-number">{String(finding.id).padStart(2, '0')}</span>
              <span className="finding-label">{displayName(finding.class_name)}</span>
              <span className="finding-confidence">Model score {Math.round(finding.confidence * 100)}%</span>
              <span className="finding-location">x {Math.round(finding.bbox.x1)}, y {Math.round(finding.bbox.y1)}</span>
            </li>)}
          </ul> : <p className="no-findings-note">No regions crossed this model’s detection threshold. This does not prove the board is defect-free.</p>}
        </section>}
      </PageLayout>
    </>
  );
}
