import React, { useEffect, useState } from 'react';
import {
  Cloud,
  Download,
  KeyRound,
  Moon,
  RefreshCw,
  ShieldCheck,
  Smartphone,
  Sun,
  UserCheck,
} from 'lucide-react';
import { api, setStoredToken } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useToast } from '../components/Toast';

export function PerfilPage() {
  const { user, setUser } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { notify } = useToast();

  const [nome, setNome] = useState(user?.nome || '');
  const [username, setUsername] = useState(user?.username || '');
  const [senhaAtual, setSenhaAtual] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [cloud, setCloud] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);

  useEffect(() => {
    setNome(user?.nome || '');
    setUsername(user?.username || '');
  }, [user]);

  useEffect(() => {
    api.cloudStatus().then(setCloud).catch(() => {});
    const onPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', onPrompt);
    return () => window.removeEventListener('beforeinstallprompt', onPrompt);
  }, []);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    try {
      const res = await api.updateMe({ nome, username, tema_preferido: theme });
      if (res.access_token) setStoredToken(res.access_token);
      setUser(res.usuario);
      notify('Perfil atualizado com sucesso!');
    } catch (err) {
      notify(err.message || 'Erro ao atualizar perfil.', 'error');
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    try {
      await api.changePassword({ senha_atual: senhaAtual, nova_senha: novaSenha });
      setSenhaAtual('');
      setNovaSenha('');
      notify('Senha alterada com sucesso!');
    } catch (err) {
      notify(err.message || 'Não foi possível trocar a senha.', 'error');
    }
  };

  const handleExportZip = async () => {
    try {
      const { blob, filename } = await api.exportBackupZip();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      notify('Backup isolado do seu perfil baixado (.zip)!');
    } catch (err) {
      notify(err.message || 'Falha ao exportar backup.', 'error');
    }
  };

  const handleSyncVault = async () => {
    setSyncing(true);
    try {
      await api.cloudSyncNow();
      const st = await api.cloudStatus();
      setCloud(st);
      notify('Cofre criptografado sincronizado com sucesso!');
    } catch (err) {
      notify(err.message || 'Cofre não conectado neste ambiente.', 'error');
    } finally {
      setSyncing(false);
    }
  };

  const handleToggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    toggleTheme();
    if (user) {
      setUser((prev) => (prev ? { ...prev, tema_preferido: next } : prev));
      api.updateMe({ tema_preferido: next }).catch(() => {});
    }
  };

  const handleInstallPwa = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    setDeferredPrompt(null);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-700 dark:text-gold-400">
          Conta, Segurança & Nuvem 24/7
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
          Meu Perfil
        </h1>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        {/* Dados do Perfil */}
        <form onSubmit={handleSaveProfile} className="glass-panel rounded-3xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center gap-2.5 text-sm font-extrabold text-[var(--text-primary)]">
            <UserCheck className="w-5 h-5 text-gold-700 dark:text-gold-400" />
            Dados do Perfil
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">Nome</label>
            <input
              type="text"
              required
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Usuário de acesso
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>
          <button type="submit" className="w-full btn-gold rounded-2xl py-3 text-sm">
            Salvar Dados
          </button>
        </form>

        {/* Alterar Senha */}
        <form onSubmit={handleChangePassword} className="glass-panel rounded-3xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center gap-2.5 text-sm font-extrabold text-[var(--text-primary)]">
            <KeyRound className="w-5 h-5 text-emerald-700 dark:text-emerald-400" />
            Alterar Senha
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Senha atual
            </label>
            <input
              type="password"
              required
              value={senhaAtual}
              onChange={(e) => setSenhaAtual(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Nova senha
            </label>
            <input
              type="password"
              required
              minLength={4}
              value={novaSenha}
              onChange={(e) => setNovaSenha(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>
          <button type="submit" className="w-full btn-gold rounded-2xl py-3 text-sm">
            Atualizar Senha
          </button>
        </form>
      </div>

      {/* Aparência + App Instalável PWA */}
      <div className="grid md:grid-cols-2 gap-5">
        <div className="glass-panel rounded-3xl p-5 sm:p-6 flex items-center justify-between gap-4">
          <div>
            <div className="text-sm font-extrabold text-[var(--text-primary)]">Tema Visual</div>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Private Obsidian Escuro ou Ivory Alabaster Claro
            </p>
          </div>
          <button
            type="button"
            onClick={handleToggleTheme}
            data-testid="perfil-theme-toggle-btn"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-xs font-bold text-[var(--text-primary)] hover:border-gold-500/40"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4 text-gold-400" /> : <Moon className="w-4 h-4 text-gold-700" />}
            {theme === 'dark' ? 'Mudar p/ Claro' : 'Mudar p/ Escuro'}
          </button>
        </div>

        <div className="glass-panel rounded-3xl p-5 sm:p-6 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="text-sm font-extrabold text-[var(--text-primary)] flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-emerald-400" />
              Instalar App no Celular / PC
            </div>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              No Chrome/Edge ou Safari, use "Adicionar à Tela Inicial" ou "Instalar Aplicativo".
            </p>
          </div>
          {deferredPrompt && (
            <button type="button" onClick={handleInstallPwa} className="btn-gold rounded-2xl px-4 py-2.5 text-xs flex-shrink-0">
              Instalar
            </button>
          )}
        </div>
      </div>

      {/* Cofre Criptografado 24/7 + Backup Isolado */}
      <div className="glass-panel-gold rounded-3xl p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 flex items-center justify-center border border-emerald-500/35">
              <Cloud className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-[var(--text-primary)]">
                Cofre Criptografado 24/7 & Backup Pessoal
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                {cloud?.vault_connected
                  ? `Conectado (AES-256-GCM) · Revisão #${cloud.revision || 0}`
                  : 'Armazenamento local ativo · Pronto para ativar Cofre AES-256-GCM no Render'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {cloud?.vault_connected && (
              <button
                type="button"
                onClick={handleSyncVault}
                disabled={syncing}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-2xl bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/35 text-xs font-bold"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                Sincronizar Agora
              </button>
            )}
            <button
              type="button"
              onClick={handleExportZip}
              data-testid="export-backup-btn"
              className="btn-gold rounded-2xl px-4 py-2.5 text-xs inline-flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              Baixar Backup (.zip)
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] pt-2 border-t border-[var(--border-subtle)]">
          <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>
            Seu backup contém exclusivamente os dados do perfil <strong>@{user?.username}</strong>.
          </span>
        </div>
      </div>
    </div>
  );
}
