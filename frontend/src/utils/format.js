/** Utilitários de formatação BRL, competências, datas, cores de cartão e urgência do Radar. */

const MESES_FULL = [
  '',
  'Janeiro',
  'Fevereiro',
  'Março',
  'Abril',
  'Maio',
  'Junho',
  'Julho',
  'Agosto',
  'Setembro',
  'Outubro',
  'Novembro',
  'Dezembro',
];

const MESES_SHORT = [
  '',
  'Jan',
  'Fev',
  'Mar',
  'Abr',
  'Mai',
  'Jun',
  'Jul',
  'Ago',
  'Set',
  'Out',
  'Nov',
  'Dez',
];

export const CURRENCY_FORMATTER = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatBRL(value) {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) return 'R$ 0,00';
  return CURRENCY_FORMATTER.format(num);
}

export function getCurrentCompetencia(now = new Date()) {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

export function getTodayISO(now = new Date()) {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function shiftCompetencia(comp, delta) {
  const [yStr, mStr] = String(comp || getCurrentCompetencia()).split('-');
  const y = Number(yStr);
  const m = Number(mStr);
  const total = y * 12 + (m - 1) + Number(delta || 0);
  const ny = Math.floor(total / 12);
  const nm = ((total % 12) + 12) % 12;
  return `${String(ny).padStart(4, '0')}-${String(nm + 1).padStart(2, '0')}`;
}

export function formatCompetenciaFull(comp) {
  const [yStr, mStr] = String(comp || '').split('-');
  const m = Number(mStr);
  if (!yStr || !m || m < 1 || m > 12) return comp || '';
  return `${MESES_FULL[m]} ${yStr}`;
}

export function formatCompetenciaShort(comp) {
  const [yStr, mStr] = String(comp || '').split('-');
  const m = Number(mStr);
  if (!yStr || !m || m < 1 || m > 12) return comp || '';
  return `${MESES_SHORT[m]}/${yStr.slice(-2)}`;
}

export function formatDateBR(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return '';
  const parts = isoDate.slice(0, 10).split('-');
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

export function formatShortDateBR(isoDate) {
  if (!isoDate || typeof isoDate !== 'string') return '';
  const parts = isoDate.slice(0, 10).split('-');
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}/${parts[1]}`;
}

export function parseHexColor(hex, fallback = '#C9A45C') {
  const cleaned = String(hex || '').trim();
  if (/^#[0-9A-Fa-f]{6}$/.test(cleaned)) return cleaned.toUpperCase();
  return fallback;
}

export function hexToRgb(hex) {
  const valid = parseHexColor(hex);
  return {
    r: parseInt(valid.slice(1, 3), 16),
    g: parseInt(valid.slice(3, 5), 16),
    b: parseInt(valid.slice(5, 7), 16),
  };
}

/** Calcula luminância relativa WCAG para decidir texto claro ou escuro sobre qualquer cor escolhida pelo usuário. */
export function getContrastTextForHex(hex) {
  const { r, g, b } = hexToRgb(hex);
  const toLinear = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const lum = 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
  return lum > 0.42 ? '#0B0E14' : '#FFFFFF';
}

/** Constrói gradiente sofisticado fiel à cor escolhida no seletor de cor do cartão ou módulo. */
export function buildCardSurfaceStyle(hex) {
  const base = parseHexColor(hex);
  const { r, g, b } = hexToRgb(base);
  const darken = (v, factor) => Math.max(0, Math.round(v * factor));
  const lighten = (v, factor) => Math.min(255, Math.round(v + (255 - v) * factor));
  const cLight = `rgb(${lighten(r, 0.14)}, ${lighten(g, 0.14)}, ${lighten(b, 0.14)})`;
  const cDark = `rgb(${darken(r, 0.56)}, ${darken(g, 0.56)}, ${darken(b, 0.56)})`;
  return {
    background: `linear-gradient(135deg, ${cLight} 0%, ${base} 46%, ${cDark} 100%)`,
    color: getContrastTextForHex(base),
    borderColor: `rgba(${lighten(r, 0.35)}, ${lighten(g, 0.35)}, ${lighten(b, 0.35)}, 0.45)`,
  };
}

export function getUrgencyMeta(statusUrgencia, diasRestantes) {
  switch (statusUrgencia) {
    case 'pago':
      return {
        label: 'Pago',
        tone: 'emerald',
        badgeClass: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/35',
        countdown: 'Quitado',
      };
    case 'atrasado': {
      const atraso = Math.abs(Number(diasRestantes || 0));
      return {
        label: 'Atrasado',
        tone: 'rose',
        badgeClass: 'bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/35',
        countdown: atraso === 1 ? '1 dia em atraso' : `${atraso} dias em atraso`,
      };
    }
    case 'vence_hoje':
      return {
        label: 'Vence Hoje',
        tone: 'amber',
        badgeClass: 'bg-amber-500/20 text-amber-800 dark:text-amber-300 border-amber-500/45',
        countdown: 'Vence hoje',
      };
    case 'proximos_7_dias': {
      const d = Number(diasRestantes || 0);
      return {
        label: 'Próximos 7 dias',
        tone: 'gold',
        badgeClass: 'bg-gold-500/20 text-gold-600 dark:text-gold-300 border-gold-500/40',
        countdown: d === 1 ? 'Vence amanhã' : `Em ${d} dias`,
      };
    }
    case 'proximos_15_dias': {
      const d = Number(diasRestantes || 0);
      return {
        label: 'Próximos 15 dias',
        tone: 'sky',
        badgeClass: 'bg-sky-500/15 text-sky-700 dark:text-sky-400 border-sky-500/35',
        countdown: `Em ${d} dias`,
      };
    }
    case 'sem_fatura':
      return {
        label: 'Sem lançamentos',
        tone: 'slate',
        badgeClass: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/25',
        countdown: 'Zerado no mês',
      };
    default: {
      const d = Number(diasRestantes || 0);
      return {
        label: 'Programado',
        tone: 'slate',
        badgeClass: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/25',
        countdown: d > 0 ? `Em ${d} dias` : 'No mês',
      };
    }
  }
}

export const QUICK_CATEGORIES = {
  entrada: ['Uber / App', 'Salário', 'Freela', 'Vendas', 'PIX Recebido', 'Extra'],
  saida: ['Mercado', 'Combustível', 'Alimentação', 'Farmácia', 'Transporte', 'Contas', 'Lazer', 'Outros'],
};

export const LUXURY_COLOR_SWATCHES = [
  '#C9A45C', // Ouro Champagne
  '#10B981', // Esmeralda Private
  '#1E293B', // Obsidiana Black
  '#7C3AED', // Ametista Nubank
  '#2563EB', // Safira Real
  '#DC2626', // Rubi Crimson
  '#F59E0B', // Âmbar Solar
  '#0891B2', // Ciano Oceano
  '#EC4899', // Magenta
  '#16A34A', // Verde Floresta
  '#EA580C', // Laranja Inter
  '#4F46E5', // Índigo
];
