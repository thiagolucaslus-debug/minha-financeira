import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  CalendarCheck2,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Layers,
  LayoutDashboard,
  LogOut,
  Moon,
  Plus,
  Sun,
  UserCircle2,
  Wallet,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { api } from '../api/client';
import { formatCompetenciaFull, shiftCompetencia } from '../utils/format';
import { BrandLogo } from './BrandLogo';
import { QuickEntryModal } from './QuickEntryModal';

const NAV_ITEMS = [
  { to: '/', label: 'Início', icon: LayoutDashboard, end: true },
  { to: '/caixa', label: 'Caixa', icon: Wallet },
  { to: '/contas', label: 'Contas', icon: CalendarCheck2 },
  { to: '/cartoes', label: 'Cartões', icon: CreditCard },
  { to: '/dividas', label: 'Dívidas', icon: Layers },
  { to: '/perfil', label: 'Perfil', icon: UserCircle2 },
];

export function Layout({ competencia, onChangeCompetencia, onQuickSaved, children }) {
  const { user, logout, setUser } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [quickOpen, setQuickOpen] = useState(false);
  const location = useLocation();

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    toggleTheme();
    if (user) {
      setUser((prev) => (prev ? { ...prev, tema_preferido: next } : prev));
      api.updateMe({ tema_preferido: next }).catch(() => {});
    }
  };

  const currentMeta = NAV_ITEMS.find((n) =>
    n.end ? location.pathname === n.to : location.pathname.startsWith(n.to)
  );

  return (
    <div className="min-h-screen obsidian-backdrop flex flex-col lg:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 xl:w-72 lg:fixed lg:inset-y-0 glass-panel border-r border-[var(--border-subtle)] z-30">
        <div className="px-6 py-6 border-b border-[var(--border-subtle)]">
          <BrandLogo size="md" showSubtitle />
        </div>

        <nav className="flex-1 px-4 py-5 space-y-1.5 overflow-y-auto">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold transition-all ${
                  isActive
                    ? 'bg-gold-500/15 text-gold-400 border border-gold-500/35 shadow-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 border border-transparent'
                }`
              }
            >
              <Icon className="w-[18px] h-[18px]" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 space-y-3 border-t border-[var(--border-subtle)]">
          <button
            type="button"
            onClick={() => setQuickOpen(true)}
            data-testid="desktop-quick-entry-btn"
            className="w-full btn-gold rounded-2xl py-3 px-4 text-sm flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            Novo Lançamento
          </button>

          <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
            <div className="min-w-0">
              <div className="text-xs font-bold text-[var(--text-primary)] truncate">
                {user?.nome || 'Perfil'}
              </div>
              <div className="text-[11px] text-[var(--text-muted)] truncate">
                @{user?.username}
              </div>
            </div>
            <button
              type="button"
              onClick={logout}
              title="Sair da conta"
              className="p-2 rounded-xl text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-500/10 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Shell */}
      <div className="flex-1 lg:pl-64 xl:pl-72 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="sticky top-0 z-20 glass-panel border-b border-[var(--border-subtle)]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="lg:hidden">
                <BrandLogo size="sm" compact />
              </div>
              <div className="hidden sm:block">
                <div className="text-sm font-bold text-[var(--text-primary)]">
                  {currentMeta?.label || 'Minha Financeira'}
                </div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  Olá, {user?.nome?.split(' ')[0] || 'Cliente'}
                </div>
              </div>
            </div>

            {/* Seletor de Mês */}
            <div className="inline-flex items-center gap-1 px-1.5 py-1 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <button
                type="button"
                onClick={() => onChangeCompetencia(shiftCompetencia(competencia, -1))}
                aria-label="Mês anterior"
                className="p-1.5 rounded-xl text-[var(--text-secondary)] hover:text-gold-400 hover:bg-white/5 transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="px-2.5 text-xs sm:text-sm font-bold text-[var(--text-primary)] min-w-[116px] text-center">
                {formatCompetenciaFull(competencia)}
              </span>
              <button
                type="button"
                onClick={() => onChangeCompetencia(shiftCompetencia(competencia, 1))}
                aria-label="Próximo mês"
                className="p-1.5 rounded-xl text-[var(--text-secondary)] hover:text-gold-400 hover:bg-white/5 transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Tema + Sair mobile */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleToggleTheme}
                data-testid="theme-toggle-btn"
                aria-label={theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro'}
                className="p-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-gold-400 hover:border-gold-500/40 transition"
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button
                type="button"
                onClick={logout}
                aria-label="Sair"
                className="lg:hidden p-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-rose-400 transition"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>

        {/* Page body */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-28 lg:pb-12">
          {children}
        </main>
      </div>

      {/* Floating `+` Quick Entry Button (sempre acessível no celular e tablet/desktop) */}
      <button
        type="button"
        onClick={() => setQuickOpen(true)}
        data-testid="fab-quick-entry"
        aria-label="Lançamento Rápido"
        className="fixed bottom-20 right-4 lg:bottom-7 lg:right-7 z-40 w-14 h-14 rounded-2xl btn-gold shadow-luxury flex items-center justify-center ring-2 ring-gold-300/40"
      >
        <Plus className="w-6 h-6 stroke-[2.75]" />
      </button>

      {/* Mobile Bottom Navigation */}
      <nav
        aria-label="Navegação principal"
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 glass-panel border-t border-[var(--border-subtle)] px-1.5 pt-1.5 pb-[max(0.5rem,env(safe-area-inset-bottom))]"
      >
        <div className="grid grid-cols-6 gap-0.5 max-w-lg mx-auto">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center py-1.5 rounded-xl text-[10px] font-semibold transition ${
                  isActive
                    ? 'text-gold-400 bg-gold-500/12'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`
              }
            >
              <Icon className="w-5 h-5 mb-0.5" />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <QuickEntryModal
        open={quickOpen}
        onClose={() => setQuickOpen(false)}
        onSaved={onQuickSaved}
      />
    </div>
  );
}
