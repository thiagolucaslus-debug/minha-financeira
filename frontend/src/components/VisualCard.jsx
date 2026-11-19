import React from 'react';
import { CalendarClock, CheckCircle2, CreditCard, Layers, Sparkles } from 'lucide-react';
import {
  buildCardSurfaceStyle,
  formatBRL,
  formatShortDateBR,
  getUrgencyMeta,
} from '../utils/format';

export function VisualCard({
  variant = 'cartao', // 'cartao' | 'modulo'
  item,
  selected = false,
  onClick,
}) {
  const surface = buildCardSurfaceStyle(item.cor_hex);
  const amount = variant === 'modulo' ? item.total_mes : item.total_fatura;
  const urgency = getUrgencyMeta(item.status_urgencia, item.dias_restantes);
  const isLightText = surface.color === '#FFFFFF';
  const subTextClass = isLightText ? 'text-white/75' : 'text-black/70';
  const pillBg = isLightText
    ? 'bg-black/25 border-white/20 text-white'
    : 'bg-white/45 border-black/15 text-black';

  return (
    <button
      type="button"
      onClick={onClick}
      style={surface}
      className={`group relative w-full text-left rounded-3xl p-5 border overflow-hidden transition-all duration-200 ${
        selected
          ? 'ring-2 ring-gold-400 ring-offset-2 ring-offset-[var(--bg-canvas)] shadow-luxury scale-[1.01]'
          : 'hover:-translate-y-0.5 hover:shadow-luxury opacity-95 hover:opacity-100'
      }`}
    >
      {/* Brilho metálico diagonal discreto */}
      <div
        className="pointer-events-none absolute -top-16 -right-12 w-48 h-48 rounded-full opacity-25 blur-2xl"
        style={{ background: isLightText ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.75)' }}
      />
      <div className="relative z-10 flex flex-col justify-between min-h-[172px] gap-4">
        {/* Topo: nome + badge */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className={`text-[11px] font-semibold uppercase tracking-[0.18em] flex items-center gap-1.5 ${subTextClass}`}>
              {variant === 'modulo' ? (
                <>
                  <Layers className="w-3.5 h-3.5" />
                  <span>Módulo Cartão Virtual</span>
                </>
              ) : (
                <>
                  <CreditCard className="w-3.5 h-3.5" />
                  <span>{item.bandeira || 'Cartão Black'}</span>
                </>
              )}
            </div>
            <h3 className="text-xl font-extrabold tracking-tight truncate mt-0.5">
              {item.nome}
            </h3>
          </div>
          <span
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold border backdrop-blur-sm flex-shrink-0 ${pillBg}`}
          >
            {item.pago ? (
              <>
                <CheckCircle2 className="w-3 h-3" /> Pago
              </>
            ) : (
              <>
                <Sparkles className="w-3 h-3" /> {urgency.countdown}
              </>
            )}
          </span>
        </div>

        {/* Meio: Valor da fatura do mês */}
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className={`text-[11px] font-medium uppercase tracking-wider ${subTextClass}`}>
              {variant === 'modulo' ? 'Fatura do mês' : 'Fatura atual'}
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold tracking-tight tabular-nums leading-none mt-1">
              {formatBRL(amount)}
            </div>
          </div>
          {variant === 'cartao' && item.ultimos_digitos ? (
            <div className={`font-mono text-xs tracking-widest ${subTextClass}`}>
              •••• {item.ultimos_digitos}
            </div>
          ) : (
            <div className={`text-xs font-medium ${subTextClass}`}>
              {item.itens_count} {item.itens_count === 1 ? 'item' : 'itens'}
            </div>
          )}
        </div>

        {/* Rodapé: Fechamento/Vencimento + Barra de limite (quando houver) */}
        <div className="space-y-2 pt-2 border-t border-current/15">
          <div className={`flex items-center justify-between text-xs ${subTextClass}`}>
            <span className="inline-flex items-center gap-1">
              <CalendarClock className="w-3.5 h-3.5" />
              Fecha dia {String(item.dia_fechamento).padStart(2, '0')}
            </span>
            <span className="font-semibold">
              Vence {formatShortDateBR(item.data_vencimento)}
            </span>
          </div>

          {Number(item.limite || 0) > 0 && (
            <div className="space-y-1">
              <div className="h-1.5 rounded-full bg-black/25 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.min(100, Number(item.uso_percentual || 0))}%`,
                    backgroundColor: isLightText ? 'rgba(255,255,255,0.88)' : 'rgba(11,14,20,0.8)',
                  }}
                />
              </div>
              <div className={`flex justify-between text-[11px] tabular-nums ${subTextClass}`}>
                <span>
                  Em aberto: {formatBRL(variant === 'modulo' ? item.total_aberto : item.limite_usado)}
                </span>
                <span>Limite {formatBRL(item.limite)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
