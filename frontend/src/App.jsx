import React, { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './components/Toast';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { CaixaPage } from './pages/CaixaPage';
import { ContasPage } from './pages/ContasPage';
import { CartoesPage } from './pages/CartoesPage';
import { ModulosDividaPage } from './pages/ModulosDividaPage';
import { PerfilPage } from './pages/PerfilPage';
import { getCurrentCompetencia } from './utils/format';

function AuthenticatedShell() {
  const { user, loading } = useAuth();
  const [competencia, setCompetencia] = useState(() => getCurrentCompetencia());
  const [refreshSignal, setRefreshSignal] = useState(0);

  const bumpRefresh = () => setRefreshSignal((n) => n + 1);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [user?.id]);

  if (loading) {
    return (
      <div className="min-h-screen obsidian-backdrop flex items-center justify-center">
        <div className="glass-panel-gold rounded-3xl px-8 py-6 text-sm font-semibold text-gold-400">
          Carregando Minha Financeira...
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <Layout
      competencia={competencia}
      onChangeCompetencia={setCompetencia}
      onQuickSaved={bumpRefresh}
    >
      <Routes>
        <Route
          path="/"
          element={
            <DashboardPage
              competencia={competencia}
              refreshSignal={refreshSignal}
              onGlobalMutate={bumpRefresh}
            />
          }
        />
        <Route
          path="/caixa"
          element={
            <CaixaPage
              competencia={competencia}
              refreshSignal={refreshSignal}
              onGlobalMutate={bumpRefresh}
            />
          }
        />
        <Route
          path="/contas"
          element={
            <ContasPage
              competencia={competencia}
              refreshSignal={refreshSignal}
              onGlobalMutate={bumpRefresh}
            />
          }
        />
        <Route
          path="/cartoes"
          element={
            <CartoesPage
              competencia={competencia}
              onChangeCompetencia={setCompetencia}
              refreshSignal={refreshSignal}
              onGlobalMutate={bumpRefresh}
            />
          }
        />
        <Route
          path="/dividas"
          element={
            <ModulosDividaPage
              competencia={competencia}
              onChangeCompetencia={setCompetencia}
              refreshSignal={refreshSignal}
              onGlobalMutate={bumpRefresh}
            />
          }
        />
        <Route path="/perfil" element={<PerfilPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <AuthenticatedShell />
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
