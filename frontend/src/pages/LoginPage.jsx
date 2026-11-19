import React, { useState } from 'react';
import {
  ArrowRight,
  Cloud,
  CreditCard,
  Layers,
  Lock,
  Moon,
  ShieldCheck,
  Sun,
  User,
  UserPlus,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { BrandLogo } from '../components/BrandLogo';
import { useToast } from '../components/Toast';

export function LoginPage() {
  const { login, register } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { notify } = useToast();

  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [nome, setNome] = useState('');
  const [username, setUsername] = useState('');
  const [senha, setSenha] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'register') {
        await register(nome, username, senha);
        notify('Perfil criado com sucesso! Bem-vindo à Minha Financeira.');
      } else {
        await login(username, senha);
        notify('Acesso autorizado. Bom controle!');
      }
    } catch (err) {
      setError(err.message || 'Não foi possível autenticar.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen obsidian-backdrop flex flex-col justify-between p-4 sm:p-8 relative overflow-hidden">
      {/* Top Bar */}
      <div className="max-w-6xl w-full mx-auto flex items-center justify-between">
        <BrandLogo size="md" showSubtitle />
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Alternar tema"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl glass-panel text-xs font-semibold text-[var(--text-secondary)] hover:text-gold-400 transition"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          <span>{theme === 'dark' ? 'Modo Claro' : 'Modo Escuro'}</span>
        </button>
      </div>

      {/* Main Split Card */}
      <div className="max-w-5xl w-full mx-auto my-8 grid lg:grid-cols-12 gap-6 items-center">
        {/* Left Editorial / Value Prop */}
        <div className="lg:col-span-6 space-y-6 lg:pr-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-gold-500/12 border border-gold-500/30 text-gold-400 text-xs font-semibold">
            <Cloud className="w-3.5 h-3.5" />
            <span>100% Nuvem 24/7 · App Instalável PWA</span>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[var(--text-primary)] leading-[1.08]">
              Seu dinheiro sob{' '}
              <span className="bg-gradient-to-r from-gold-300 via-gold-500 to-emerald-400 bg-clip-text text-transparent">
                controle absoluto.
              </span>
            </h1>
            <p className="text-sm sm:text-base text-[var(--text-secondary)] leading-relaxed max-w-lg">
              Simples no dia a dia, sofisticada nos detalhes. Lance corridas e gastos em 2 toques,
              organize seus cartões e gerencie módulos de dívida com alertas automáticos de vencimento.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div className="glass-panel rounded-2xl p-4 space-y-1.5">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
                <Layers className="w-4 h-4" />
              </div>
              <div className="text-sm font-bold text-[var(--text-primary)]">
                Módulos Estilo Cartão
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Crie módulos como Thiago ou Seu Luiz com múltiplas compras, parcelas e alerta de vencimento.
              </p>
            </div>

            <div className="glass-panel rounded-2xl p-4 space-y-1.5">
              <div className="w-8 h-8 rounded-xl bg-gold-500/15 text-gold-400 flex items-center justify-center">
                <CreditCard className="w-4 h-4" />
              </div>
              <div className="text-sm font-bold text-[var(--text-primary)]">
                Radar Unificado 24/7
              </div>
              <p className="text-xs text-[var(--text-muted)]">
                Contas fixas, cartões e dívidas no mesmo painel com fechamento real de quanto entrou e sobrou.
              </p>
            </div>
          </div>
        </div>

        {/* Right Auth Panel */}
        <div className="lg:col-span-6">
          <div className="glass-panel-gold rounded-3xl p-6 sm:p-8 shadow-luxury">
            {/* Tabs Entrar / Criar Novo Perfil */}
            <div className="grid grid-cols-2 gap-2 p-1 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] mb-6">
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setError('');
                }}
                data-testid="tab-login"
                className={`py-2.5 rounded-xl text-sm font-bold transition ${
                  mode === 'login'
                    ? 'btn-gold shadow'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                Entrar
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('register');
                  setError('');
                }}
                data-testid="tab-register"
                className={`py-2.5 rounded-xl text-sm font-bold transition flex items-center justify-center gap-1.5 ${
                  mode === 'register'
                    ? 'btn-gold shadow'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <UserPlus className="w-4 h-4" />
                Criar Novo Perfil
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                    Nome completo
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      required
                      value={nome}
                      onChange={(e) => setNome(e.target.value)}
                      placeholder="Ex.: Thiago Lucas"
                      data-testid="input-nome"
                      className="w-full input-private rounded-xl pl-10 pr-4 py-3 text-sm"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Usuário
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Ex.: thiago"
                    data-testid="input-username"
                    className="w-full input-private rounded-xl pl-10 pr-4 py-3 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Senha
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    required
                    autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                    value={senha}
                    onChange={(e) => setSenha(e.target.value)}
                    placeholder="••••••••"
                    data-testid="input-senha"
                    className="w-full input-private rounded-xl pl-10 pr-4 py-3 text-sm"
                  />
                </div>
              </div>

              {error && (
                <div className="rounded-xl bg-rose-500/12 border border-rose-500/35 px-3.5 py-2.5 text-xs font-medium text-rose-400">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                data-testid="submit-auth-btn"
                className="w-full btn-gold rounded-2xl py-3.5 text-sm flex items-center justify-center gap-2 disabled:opacity-60"
              >
                <span>
                  {loading
                    ? 'Validando...'
                    : mode === 'register'
                    ? 'Criar Perfil e Acessar'
                    : 'Acessar Minha Financeira'}
                </span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>

            <div className="mt-5 pt-4 border-t border-[var(--border-subtle)] flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>
                Perfis isolados com senha criptografada (bcrypt) e cofre AES-256-GCM na nuvem.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="max-w-6xl w-full mx-auto text-center text-xs text-[var(--text-muted)]">
        Minha Financeira · Private Obsidian Edition
      </footer>
    </div>
  );
}
