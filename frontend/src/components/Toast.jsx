import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

const ToastContext = createContext({
  notify: () => {},
});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const remove = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (message, type = 'success') => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev.slice(-1), { id, message, type }]);
      setTimeout(() => remove(id), 2600);
    },
    [remove]
  );

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="fixed bottom-24 lg:bottom-6 left-1/2 -translate-x-1/2 z-[70] flex flex-col items-center gap-2 max-w-md w-[calc(100%-2rem)] pointer-events-none">
        {toasts.map((t) => {
          const Icon =
            t.type === 'error' ? AlertCircle : t.type === 'info' ? Info : CheckCircle2;
          const ring =
            t.type === 'error'
              ? 'border-rose-500/45 text-rose-500 dark:text-rose-300'
              : t.type === 'info'
              ? 'border-gold-500/45 text-gold-600 dark:text-gold-300'
              : 'border-emerald-500/45 text-emerald-600 dark:text-emerald-300';
          return (
            <div
              key={t.id}
              className={`pointer-events-auto glass-panel rounded-2xl px-4 py-2.5 shadow-luxury flex items-center gap-2.5 border ${ring}`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="text-xs sm:text-sm text-[var(--text-primary)] font-medium">
                {t.message}
              </span>
              <button
                type="button"
                onClick={() => remove(t.id)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
