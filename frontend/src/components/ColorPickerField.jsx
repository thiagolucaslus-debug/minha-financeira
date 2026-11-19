import React from 'react';
import { Palette } from 'lucide-react';
import { LUXURY_COLOR_SWATCHES, parseHexColor } from '../utils/format';

export function ColorPickerField({ label = 'Cor personalizada', value, onChange }) {
  const safeHex = parseHexColor(value, '#C9A45C');

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-1.5">
          <Palette className="w-3.5 h-3.5 text-gold-500" />
          {label}
        </label>
        <div className="inline-flex items-center gap-2 text-xs font-mono text-[var(--text-secondary)]">
          <span
            className="w-3.5 h-3.5 rounded-full ring-2 ring-white/25 inline-block"
            style={{ backgroundColor: safeHex }}
          />
          <span>{safeHex}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {LUXURY_COLOR_SWATCHES.map((swatch) => {
          const active = safeHex === swatch.toUpperCase();
          return (
            <button
              key={swatch}
              type="button"
              onClick={() => onChange(swatch.toUpperCase())}
              title={swatch}
              aria-label={`Selecionar cor ${swatch}`}
              className={`w-7 h-7 rounded-full transition-transform ${
                active
                  ? 'scale-110 ring-2 ring-offset-2 ring-offset-[var(--bg-surface-strong)] ring-gold-400'
                  : 'hover:scale-105 opacity-90 hover:opacity-100'
              }`}
              style={{ backgroundColor: swatch }}
            />
          );
        })}

        <label
          title="Escolher qualquer cor livre"
          className="inline-flex items-center gap-1.5 px-2.5 h-7 rounded-full input-private text-xs cursor-pointer hover:border-gold-500/60"
        >
          <input
            type="color"
            value={safeHex}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            className="w-4 h-4 rounded border-0 bg-transparent cursor-pointer p-0"
          />
          <span className="font-medium text-[var(--text-secondary)]">Livre</span>
        </label>
      </div>
    </div>
  );
}
