import { Fragment, useRef, useState } from 'react'

const FIELD_LABELS = {
  brand_name: 'Brand Name',
  class_type: 'Class / Type',
  alcohol_content: 'Alcohol Content',
  net_contents: 'Net Contents',
  government_warning: 'Government Warning',
  producer_name_address: 'Producer Name & Address',
  country_of_origin: 'Country of Origin',
}

const STATUS_LABELS = {
  APPROVED: '✓ Approved',
  NEEDS_REVIEW: '⚠ Needs Review',
  REJECTED: '✗ Rejected',
  ERROR: 'Error',
}

function StatusBanner({ result }) {
  return (
    <div className={`status-banner status-${result.overall_status}`}>
      <span>{STATUS_LABELS[result.overall_status]}</span>
      <span className="time">{result.processing_seconds}s</span>
    </div>
  )
}

function ChecksTable({ checks }) {
  return (
    <table className="checks">
      <thead>
        <tr>
          <th style={{ width: '18%' }}>Field</th>
          <th style={{ width: '14%' }}>Result</th>
          <th style={{ width: '32%' }}>Application Says</th>
          <th style={{ width: '36%' }}>Label Says</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((c) => (
          <tr key={c.field}>
            <td><strong>{FIELD_LABELS[c.field] || c.field}</strong></td>
            <td><span className={`pill pill-${c.status}`}>{c.status.replace('_', ' ')}</span></td>
            <td className="mono">{c.application_value || '—'}</td>
            <td>
              <span className="mono">{c.label_value || '—'}</span>
              {c.note && <div className="note">{c.note}</div>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ResultCard({ result }) {
  return (
    <div className="card">
      <StatusBanner result={result} />
      <p style={{ fontSize: 17 }}>{result.summary}</p>
      {result.error && <div className="error-box">{result.error}</div>}
      {result.checks?.length > 0 && <ChecksTable checks={result.checks} />}
    </div>
  )
}

function ImageDrop({ file, setFile, multiple = false, files, setFiles }) {
  const inputRef = useRef()
  const cameraRef = useRef()
  const [drag, setDrag] = useState(false)
  const [preview, setPreview] = useState(null)

  const onFiles = (list) => {
    const arr = Array.from(list).filter((f) => f.type.startsWith('image/'))
    if (!arr.length) return
    if (multiple) {
      setFiles(arr)
    } else {
      setFile(arr[0])
      const r = new FileReader()
      r.onload = (e) => setPreview(e.target.result)
      r.readAsDataURL(arr[0])
    }
  }

  return (
    <div
      className={`dropzone ${drag ? 'drag' : ''}`}
      onClick={() => inputRef.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(e.dataTransfer.files) }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple={multiple}
        hidden
        onChange={(e) => onFiles(e.target.files)}
      />
      {/* capture="environment": on phones this opens the camera directly —
          field-inspection mode. On desktop it falls back to the file picker. */}
      {!multiple && (
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => onFiles(e.target.files)}
        />
      )}
      {!multiple && preview ? (
        <div>
          <img src={preview} alt="Label preview" />
          <p style={{ marginBottom: 0 }}>{file?.name} — click to change</p>
        </div>
      ) : multiple && files?.length ? (
        <div>
          <strong style={{ color: '#111827', fontSize: 19 }}>{files.length} label image{files.length > 1 ? 's' : ''} selected</strong>
          <div className="filelist">{files.slice(0, 8).map((f) => f.name).join(', ')}{files.length > 8 ? ` … and ${files.length - 8} more` : ''}</div>
          <p style={{ marginBottom: 0 }}>Click to change selection</p>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 44, marginBottom: 6 }}>🏷️</div>
          <strong style={{ color: '#111827', fontSize: 19 }}>
            {multiple ? 'Drop label images here' : 'Drop a label image here'}
          </strong>
          <p style={{ marginBottom: 0 }}>or click to browse (PNG / JPG)</p>
          {!multiple && (
            <button
              type="button"
              className="btn-secondary"
              style={{ marginTop: 12 }}
              onClick={(e) => { e.stopPropagation(); cameraRef.current.click() }}
            >
              📷 Take a photo
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function SingleVerify() {
  const [file, setFile] = useState(null)
  const [form, setForm] = useState({
    brand_name: '',
    class_type: '',
    alcohol_content: '',
    net_contents: '',
    beverage_type: 'distilled_spirits',
  })
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const ready = file && form.brand_name && form.class_type && form.alcohol_content && form.net_contents

  const fillExample = () =>
    setForm({
      brand_name: 'OLD TOM DISTILLERY',
      class_type: 'Kentucky Straight Bourbon Whiskey',
      alcohol_content: '45% Alc./Vol. (90 Proof)',
      net_contents: '750 mL',
      beverage_type: 'distilled_spirits',
    })

  const submit = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      const fd = new FormData()
      fd.append('image', file)
      fd.append('application', JSON.stringify(form))
      const res = await fetch('/api/verify', { method: 'POST', body: fd })
      if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`)
      setResult(await res.json())
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <div className="grid-2">
        <div className="card">
          <h2>1. Label Image</h2>
          <ImageDrop file={file} setFile={setFile} />
        </div>
        <div className="card">
          <h2>2. Application Data <button className="btn-secondary" style={{ float: 'right' }} onClick={fillExample}>Fill example</button></h2>
          <label className="field-label">Brand Name</label>
          <input type="text" value={form.brand_name} onChange={set('brand_name')} placeholder="OLD TOM DISTILLERY" />
          <label className="field-label">Class / Type</label>
          <input type="text" value={form.class_type} onChange={set('class_type')} placeholder="Kentucky Straight Bourbon Whiskey" />
          <label className="field-label">Alcohol Content</label>
          <input type="text" value={form.alcohol_content} onChange={set('alcohol_content')} placeholder="45% Alc./Vol. (90 Proof)" />
          <label className="field-label">Net Contents</label>
          <input type="text" value={form.net_contents} onChange={set('net_contents')} placeholder="750 mL" />
          <label className="field-label">Beverage Type</label>
          <select value={form.beverage_type} onChange={set('beverage_type')}>
            <option value="distilled_spirits">Distilled Spirits</option>
            <option value="wine">Wine</option>
            <option value="beer">Beer / Malt Beverage</option>
          </select>
        </div>
      </div>

      <button className="btn" disabled={!ready || busy} onClick={submit}>
        {busy ? <><span className="spinner" />Checking label…</> : 'Verify Label'}
      </button>
      {!ready && <div className="note" style={{ marginTop: 8 }}>Add a label image and fill in all four fields to verify.</div>}
      {error && <div className="error-box">{error}</div>}
      {result && <div style={{ marginTop: 24 }}><ResultCard result={result} /></div>}
    </div>
  )
}

function BatchVerify() {
  const [files, setFiles] = useState([])
  const [csv, setCsv] = useState(null)
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState({})
  const csvRef = useRef()

  const submit = async () => {
    setBusy(true); setError(null); setResults([])
    try {
      const fd = new FormData()
      files.forEach((f) => fd.append('images', f))
      fd.append('applications', csv)
      const res = await fetch('/api/verify/batch', { method: 'POST', body: fd })
      if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`)
      // NDJSON stream: one result per line, in completion order — render each
      // label the moment the server finishes it (results table fills live).
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() // keep the trailing partial line in the buffer
        const parsed = lines.filter(Boolean).map((l) => JSON.parse(l))
        if (parsed.length) setResults((prev) => [...(prev || []), ...parsed])
      }
      if (buf.trim()) setResults((prev) => [...(prev || []), JSON.parse(buf)])
    } catch (e) {
      // Mid-stream failures keep the rows already received on screen.
      setError(String(e.message || e))
    } finally {
      setBusy(false)
    }
  }

  const counts = results
    ? results.reduce((a, r) => ({ ...a, [r.overall_status]: (a[r.overall_status] || 0) + 1 }), {})
    : {}

  return (
    <div>
      <div className="grid-2">
        <div className="card">
          <h2>1. Label Images</h2>
          <ImageDrop multiple files={files} setFiles={setFiles} />
        </div>
        <div className="card">
          <h2>2. Applications File</h2>
          <p className="note" style={{ marginTop: 0 }}>
            CSV or JSON, one row per image, matched by <strong>filename</strong>.
            Columns: filename, brand_name, class_type, alcohol_content, net_contents.
          </p>
          <div
            className="dropzone"
            onClick={() => csvRef.current.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); setCsv(e.dataTransfer.files[0]) }}
          >
            <input ref={csvRef} type="file" accept=".csv,.json" hidden onChange={(e) => setCsv(e.target.files[0])} />
            {csv ? <strong style={{ color: '#111827' }}>{csv.name}</strong> : <span>Drop CSV / JSON here or click to browse</span>}
          </div>
          <p className="note">
            <a href={'data:text/csv;charset=utf-8,' + encodeURIComponent(
              'filename,brand_name,class_type,alcohol_content,net_contents\n' +
              'old_tom.png,OLD TOM DISTILLERY,Kentucky Straight Bourbon Whiskey,45% Alc./Vol. (90 Proof),750 mL\n'
            )} download="applications_template.csv">Download CSV template</a>
          </p>
        </div>
      </div>

      <button className="btn" disabled={!files.length || !csv || busy} onClick={submit}>
        {busy
          ? <><span className="spinner" />Processing… {results?.length || 0} / {files.length} done</>
          : `Verify ${files.length || ''} Labels`}
      </button>
      {error && <div className="error-box">{error}</div>}

      {results && (
        <div style={{ marginTop: 24 }}>
          <div className="batch-summary">
            {['APPROVED', 'NEEDS_REVIEW', 'REJECTED', 'ERROR'].map((s) => (
              <div key={s} className="stat">
                <div className="num">{counts[s] || 0}</div>
                <div className="lbl">{STATUS_LABELS[s]}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <table className="checks">
              <thead>
                <tr><th>File</th><th>Result</th><th>Summary</th><th>Time</th></tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <Fragment key={i}>
                    <tr className="row-expand" onClick={() => setOpen({ ...open, [i]: !open[i] })}>
                      <td className="mono">{r.filename}</td>
                      <td><span className={`pill pill-${r.overall_status === 'APPROVED' ? 'MATCH' : r.overall_status === 'NEEDS_REVIEW' ? 'NEEDS_REVIEW' : 'MISMATCH'}`}>{STATUS_LABELS[r.overall_status]}</span></td>
                      <td>{r.summary}</td>
                      <td>{r.processing_seconds}s</td>
                    </tr>
                    {open[i] && r.checks?.length > 0 && (
                      <tr>
                        <td colSpan={4} style={{ background: '#f9fafb' }}>
                          <ChecksTable checks={r.checks} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <p className="note">Click a row to see field-by-field detail.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('single')
  return (
    <div>
      <div className="header">
        <h1>TTB Label Verification</h1>
        <p>AI-assisted check of label artwork against COLA application data — prototype</p>
      </div>
      <div className="container">
        <div className="tabs">
          <button className={`tab ${tab === 'single' ? 'active' : ''}`} onClick={() => setTab('single')}>
            Single Label
          </button>
          <button className={`tab ${tab === 'batch' ? 'active' : ''}`} onClick={() => setTab('batch')}>
            Batch Upload
          </button>
        </div>
        {tab === 'single' ? <SingleVerify /> : <BatchVerify />}
      </div>
    </div>
  )
}
