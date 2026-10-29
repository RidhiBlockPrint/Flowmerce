'use client';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './Icon';
import { Button } from './ui';
/* ---------- Dialog ---------- */
export function Dialog({ title, sub, children, footer, onClose, wide, labelledBy }) {
    const ref = useRef(null);
    useEffect(() => {
        const prev = document.activeElement;
        const el = ref.current;
        const focusable = () => el?.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])') ?? [];
        (el?.querySelector('[data-autofocus]') ?? focusable()[1] ?? focusable()[0])?.focus();
        const onKey = (e) => {
            if (e.key === 'Escape') {
                e.stopPropagation();
                onClose();
            }
            if (e.key === 'Tab' && el) {
                const f = [...focusable()].filter((x) => !x.hasAttribute('disabled'));
                if (!f.length)
                    return;
                if (e.shiftKey && document.activeElement === f[0]) {
                    e.preventDefault();
                    f[f.length - 1].focus();
                }
                else if (!e.shiftKey && document.activeElement === f[f.length - 1]) {
                    e.preventDefault();
                    f[0].focus();
                }
            }
        };
        document.addEventListener('keydown', onKey);
        const overflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; prev?.focus?.(); };
    }, [onClose]);
    const id = labelledBy ?? 'dlg-title';
    return createPortal(<div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget)
        onClose(); }}>
      <div className={`dialog ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={id} ref={ref}>
        <div className="dialog-head">
          <div style={{ flex: 1, minWidth: 0 }}>
            <h2 className="dialog-title" id={id}>{title}</h2>
            {sub ? <div className="muted small mt-4">{sub}</div> : null}
          </div>
          <Button variant="ghost" size="sm" iconOnly icon="close" aria-label="Close" onClick={onClose}/>
        </div>
        <div className="dialog-body">{children}</div>
        {footer ? <div className="dialog-foot">{footer}</div> : null}
      </div>
    </div>, document.body);
}
/** Confirmation for actions with consequences. With `phrase`, the user must type it exactly. */
export function ConfirmDialog({ title, children, confirmLabel, danger, phrase, onConfirm, onClose, busy, extra }) {
    const [typed, setTyped] = useState('');
    const ok = !phrase || typed.trim() === phrase;
    return (<Dialog title={title} onClose={onClose} footer={<>
        <Button variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant={danger ? 'danger' : 'primary'} onClick={() => onConfirm(typed.trim())} disabled={!ok} loading={busy}>{confirmLabel}</Button>
      </>}>
      <div className="col gap-12">
        {children}
        {extra}
        {phrase ? (<div className="field">
            <label htmlFor="confirm-phrase">Type <span className="mono strong">{phrase}</span> to confirm</label>
            <input id="confirm-phrase" data-autofocus className="input" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} onKeyDown={(e) => { if (e.key === 'Enter' && ok && !busy)
            onConfirm(typed.trim()); }}/>
          </div>) : null}
      </div>
    </Dialog>);
}
/* ---------- Drawer ---------- */
export function Drawer({ title, children, onClose }) {
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape')
            onClose(); };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [onClose]);
    return createPortal(<>
      <div className="drawer-overlay" onClick={onClose}/>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : 'Panel'}>
        <div className="drawer-head">
          <h2 className="card-title" style={{ flex: 1 }}>{title}</h2>
          <Button variant="ghost" size="sm" iconOnly icon="close" aria-label="Close" onClick={onClose}/>
        </div>
        <div className="drawer-body">{children}</div>
      </aside>
    </>, document.body);
}
const ToastCtx = createContext(() => { });
export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);
    const push = useCallback((t) => {
        const id = Date.now() + Math.random();
        setToasts((l) => [...l.slice(-3), { ...t, id }]);
        setTimeout(() => setToasts((l) => l.filter((x) => x.id !== id)), t.tone === 'crit' ? 9000 : 4500);
    }, []);
    return (<ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (<div key={t.id} className={`toast ${t.tone}`} role={t.tone === 'crit' ? 'alert' : 'status'}>
            <Icon name={t.tone === 'crit' ? 'alert' : t.tone === 'ok' ? 'checkCircle' : 'info'}/>
            <div style={{ flex: 1 }}>{t.text}</div>
            <button className="btn ghost xs" style={{ color: '#fff' }} aria-label="Dismiss" onClick={() => setToasts((l) => l.filter((x) => x.id !== t.id))}><Icon name="close" size="sm"/></button>
          </div>))}
      </div>
    </ToastCtx.Provider>);
}
export function useToast() {
    const push = useContext(ToastCtx);
    return {
        ok: (text) => push({ tone: 'ok', text }),
        error: (e) => push({ tone: 'crit', text: e instanceof Error ? e.message : String(e) }),
        info: (text) => push({ tone: 'info', text }),
    };
}
