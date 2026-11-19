import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BellRing,
  CalendarClock,
  CheckCircle2,
  Clock,
  CreditCard,
  Layers,
  PiggyBank,
  Receipt,
  Sparkles,
  Undo2,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import {
  formatBRL,
  formatCompetenciaFull,
  formatShortDateBR,
  getUrgencyMeta,
} from '../utils/format';
import { Modal } from '../components/Modal';
import { QuickEntryModal } from '../components/QuickEntryModal';
import { useToast } from '../components/Toast';

export function DashboardPage({ competencia, refreshSignal, onGlobalMutate }) {
  const { notify } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [radarFilter, setRadarFilter] = useState('todos'); // todos | pendentes | pagos
  const [quickType, setQuickType] = useState(null);
  const [payTarget, setPayTarget] = useState(null);
  const [lancarNoCaixa, setLancarNoCaixa] = useState(true);
  const [paying, setPaying] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const res = await api.painelResumo(competencia);
      setData(res);
    } catch (err) {
      notify(err.message || 'Erro ao carregar painel.', 'error');
    } finally {
      setLoading(false);
    }
  }, [competencia, notify]);

  useEffect(() => {
    loadData();
  }, [loadData, refreshSignal]);

  const handleConfirmPay = async () => {
    if (!payTarget) return;
    setPaying(true);
    try {
      const payload = { competencia: payTarget.competencia, lancar_no_caixa: lancarNoCaixa };
      if (payTarget.origem_tipo === 'conta') {
        await api.pagarConta(payTarget.origem_id, payload);
      } else if (payTarget.origem_tipo === 'cartao') {
        await api.pagarCartao(payTarget.origem_id, payload);
      } else if (payTarget.origem_tipo === 'modulo_divida') {
        await api.pagarModulo(payTarget.origem_id, payload);
      }
      notify(`${payTarget.titulo} marcado como pago!`);
      setPayTarget(null);
      await loadData();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Falha ao registrar pagamento.', 'error');
    } finally {
      setPaying(false);
    }
  };

  const handleUndoPay = async (item) => {
    try {
      if (item.origem_tipo === 'conta') {
        await api.estornarConta(item.origem_id, item.competencia);
      } else if (item.origem_tipo === 'cartao') {
        await api.estornarCartao(item.origem_id, item.competencia);
      } else if (item.origem_tipo === 'modulo_divida') {
        await api.estornarModulo(item.origem_id, item.competencia);
      }
      notify(`Pagamento de ${item.titulo} estornado.`);
      await loadData();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao estornar pagamento.', 'error');
    }
  };

  const kpis = data?.kpis || {
    entrou: 0,
    saiu: 0,
    sobrou: 0,
    a_vencer: 0,
    saldo_projetado: 0,
  };
  const radar = data?.radar || { itens: [], resumo: {} };
  const filteredRadar = radar.itens.filter((it) => {
    if (radarFilter === 'pendentes') return !it.pago;
    if (radarFilter === 'pagos') return it.pago;
    return true;
  });

  const getOrigemBadge = (tipo) => {
    if (tipo === 'cartao') return { label: 'Cartão', Icon: CreditCard };
    if (tipo === 'modulo_divida') return { label: 'Módulo Dívida', Icon: Layers };
    return { label: 'Conta', Icon: Receipt };
  };

  return (
    <div className="space-y-6">
      {/* Cabeçalho Executivo + Ações Rápidas */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-400">
            Visão Executiva · {formatCompetenciaFull(competencia)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
            Painel Financeiro
          </h1>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setQuickType('entrada')}
            data-testid="quick-entrada-btn"
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-2xl bg-emerald-500/15 border border-emerald-500/35 text-emerald-400 text-xs sm:text-sm font-bold hover:bg-emerald-500/25 transition"
          >
            <ArrowUpRight className="w-4 h-4" />
            + Entrada
          </button>
          <button
            type="button"
            onClick={() => setQuickType('saida')}
            data-testid="quick-saida-btn"
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-2xl bg-rose-500/15 border border-rose-500/35 text-rose-400 text-xs sm:text-sm font-bold hover:bg-rose-500/25 transition"
          >
            <ArrowDownRight className="w-4 h-4" />
            - Saída
          </button>
        </div>
      </div>

      {/* 4 Cards KPI Executivos */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5 sm:gap-4">
        <div className="glass-panel rounded-3xl p-4 sm:p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold text-[var(--text-muted)]">
            <span>Entrou no mês</span>
            <span className="w-8 h-8 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center">
              <ArrowUpRight className="w-4 h-4" />
            </span>
          </div>
          <div
            data-testid="kpi-entrou"
            className="text-xl sm:text-2xl font-extrabold text-emerald-400 tabular-nums mt-3"
          >
            {formatBRL(kpis.entrou)}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-1">
            Uber, salário, vendas e extras
          </div>
        </div>

        <div className="glass-panel rounded-3xl p-4 sm:p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold text-[var(--text-muted)]">
            <span>Saiu no mês</span>
            <span className="w-8 h-8 rounded-xl bg-rose-500/15 text-rose-400 flex items-center justify-center">
              <ArrowDownRight className="w-4 h-4" />
            </span>
          </div>
          <div
            data-testid="kpi-saiu"
            className="text-xl sm:text-2xl font-extrabold text-rose-400 tabular-nums mt-3"
          >
            {formatBRL(kpis.saiu)}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-1">
            Mercado, contas pagas e gastos
          </div>
        </div>

        <div className="glass-panel-gold rounded-3xl p-4 sm:p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold text-[var(--text-muted)]">
            <span>Sobrou no caixa</span>
            <span className="w-8 h-8 rounded-xl bg-gold-500/18 text-gold-400 flex items-center justify-center">
              <PiggyBank className="w-4 h-4" />
            </span>
          </div>
          <div
            data-testid="kpi-sobrou"
            className={`text-xl sm:text-2xl font-extrabold tabular-nums mt-3 ${
              kpis.sobrou >= 0 ? 'text-[var(--text-primary)]' : 'text-rose-400'
            }`}
          >
            {formatBRL(kpis.sobrou)}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-1 tabular-nums">
            Projetado pós-contas: <strong className="text-gold-400">{formatBRL(kpis.saldo_projetado)}</strong>
          </div>
        </div>

        <div className="glass-panel rounded-3xl p-4 sm:p-5 relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-semibold text-[var(--text-muted)]">
            <span>A vencer no mês</span>
            <span className="w-8 h-8 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center">
              <CalendarClock className="w-4 h-4" />
            </span>
          </div>
          <div
            data-testid="kpi-avencer"
            className="text-xl sm:text-2xl font-extrabold text-amber-400 tabular-nums mt-3"
          >
            {formatBRL(kpis.a_vencer)}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-1">
            Contas + Cartões + Módulos
          </div>
        </div>
      </div>

      {/* Radar Unificado de Vencimentos */}
      <section className="glass-panel-gold rounded-3xl p-5 sm:p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gold-500/18 text-gold-400 flex items-center justify-center border border-gold-500/30">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[var(--text-primary)] tracking-tight">
                Radar Unificado de Vencimentos
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                Contas fixas, cartões e módulos de dívida (Thiago, Seu Luiz...) em ordem de urgência
              </p>
            </div>
          </div>

          {/* Resumo Urgências */}
          <div className="flex flex-wrap items-center gap-2">
            {radar.resumo?.qtd_atrasados > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/35">
                <AlertTriangle className="w-3.5 h-3.5" /> {radar.resumo.qtd_atrasados} atrasado(s)
              </span>
            )}
            {radar.resumo?.qtd_hoje > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40">
                <Clock className="w-3.5 h-3.5" /> {radar.resumo.qtd_hoje} hoje
              </span>
            )}
            {radar.resumo?.qtd_7_dias > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-gold-500/18 text-gold-400 border border-gold-500/35">
                {radar.resumo.qtd_7_dias} próx. 7d
              </span>
            )}
            {radar.resumo?.qtd_15_dias > 0 && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-sky-500/15 text-sky-400 border border-sky-500/30">
                {radar.resumo.qtd_15_dias} próx. 15d
              </span>
            )}
          </div>
        </div>

        {/* Filtros do Radar */}
        <div className="flex items-center gap-2">
          {[
            { id: 'todos', label: `Todos (${radar.itens.length})` },
            { id: 'pendentes', label: `Pendentes (${radar.itens.filter((i) => !i.pago).length})` },
            { id: 'pagos', label: `Pagos (${radar.itens.filter((i) => i.pago).length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setRadarFilter(tab.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition border ${
                radarFilter === tab.id
                  ? 'bg-gold-500/20 text-gold-400 border-gold-500/40'
                  : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)] hover:border-gold-500/30'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="py-10 text-center text-sm text-[var(--text-muted)]">
            Carregando radar de vencimentos...
          </div>
        ) : filteredRadar.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[var(--border-subtle)] p-8 text-center space-y-2">
            <Sparkles className="w-7 h-7 text-gold-400 mx-auto" />
            <div className="text-sm font-bold text-[var(--text-primary)]">
              Nenhum vencimento encontrado nesta visão
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              Cadastre contas fixas, cartões ou módulos de dívida para acompanhar tudo por aqui.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {filteredRadar.map((it) => {
              const urg = getUrgencyMeta(it.status_urgencia, it.dias_restantes);
              const { label: origLabel, Icon: OrigIcon } = getOrigemBadge(it.origem_tipo);
              return (
                <div
                  key={it.uid}
                  className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-start sm:items-center gap-3 min-w-0">
                    <span
                      className="w-3.5 h-3.5 rounded-full flex-shrink-0 mt-1 sm:mt-0 ring-2 ring-white/15"
                      style={{ backgroundColor: it.cor_hex }}
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-sm text-[var(--text-primary)] truncate">
                          {it.titulo}
                        </span>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)]">
                          <OrigIcon className="w-3 h-3" />
                          {origLabel}
                        </span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-lg text-[10px] font-bold border ${urg.badgeClass}`}
                        >
                          {urg.countdown}
                        </span>
                      </div>
                      <div className="text-xs text-[var(--text-muted)] mt-0.5">
                        {it.subtitulo} · Vence em {formatShortDateBR(it.data_vencimento)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-3 pl-6 sm:pl-0">
                    <span className="text-base font-extrabold tabular-nums text-[var(--text-primary)]">
                      {formatBRL(it.valor)}
                    </span>
                    {it.pago ? (
                      <button
                        type="button"
                        onClick={() => handleUndoPay(it)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-rose-500/15 hover:text-rose-400 hover:border-rose-500/35 transition"
                        title="Clique para estornar este pagamento"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Pago</span>
                        <Undo2 className="w-3 h-3 opacity-70" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setLancarNoCaixa(true);
                          setPayTarget(it);
                        }}
                        className="px-3.5 py-1.5 rounded-xl btn-gold text-xs"
                      >
                        Pagar
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Gráficos Limpos: Entradas × Saídas + Distribuição */}
      <div className="grid lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 glass-panel rounded-3xl p-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-extrabold text-[var(--text-primary)]">
                Entradas × Saídas (6 meses)
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                Evolução real do seu fluxo de caixa mensal
              </p>
            </div>
            <Link to="/caixa" className="text-xs font-semibold text-gold-400 hover:underline">
              Ver Caixa →
            </Link>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.graficos?.fluxo_mensal || []} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#8492A6', fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#8492A6', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={54}
                />
                <Tooltip
                  formatter={(v) => formatBRL(v)}
                  contentStyle={{
                    backgroundColor: '#11141C',
                    border: '1px solid rgba(201,164,92,0.35)',
                    borderRadius: '14px',
                    color: '#F8FAFC',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="entrou" name="Entrou" fill="#10B981" radius={[8, 8, 0, 0]} maxBarSize={24} />
                <Bar dataKey="saiu" name="Saiu" fill="#C9A45C" radius={[8, 8, 0, 0]} maxBarSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-5 glass-panel rounded-3xl p-5 sm:p-6 flex flex-col">
          <div className="mb-3">
            <h3 className="text-base font-extrabold text-[var(--text-primary)]">
              Distribuição de Gastos & Módulos
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              Categorias pagas no mês + compromissos em aberto
            </p>
          </div>
          {(data?.graficos?.distribuicao || []).length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-xs text-[var(--text-muted)] py-12">
              Sem saídas ou compromissos lançados neste mês.
            </div>
          ) : (
            <div className="flex-1 grid sm:grid-cols-2 items-center gap-4">
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data.graficos.distribuicao}
                      dataKey="valor"
                      nameKey="nome"
                      innerRadius={48}
                      outerRadius={76}
                      paddingAngle={3}
                    >
                      {data.graficos.distribuicao.map((entry) => (
                        <Cell key={entry.nome} fill={entry.cor} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v) => formatBRL(v)}
                      contentStyle={{
                        backgroundColor: '#11141C',
                        border: '1px solid rgba(201,164,92,0.35)',
                        borderRadius: '12px',
                        color: '#F8FAFC',
                        fontSize: '12px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                {data.graficos.distribuicao.map((item) => (
                  <div key={item.nome} className="flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: item.cor }}
                      />
                      <span className="truncate text-[var(--text-secondary)]">{item.nome}</span>
                    </div>
                    <span className="font-bold tabular-nums text-[var(--text-primary)]">
                      {formatBRL(item.valor)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Últimos lançamentos do Caixa */}
      {(data?.ultimos_lancamentos || []).length > 0 && (
        <section className="glass-panel rounded-3xl p-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-extrabold text-[var(--text-primary)]">
              Últimas Movimentações do Caixa
            </h3>
            <Link to="/caixa" className="text-xs font-semibold text-gold-400 hover:underline">
              Ver tudo →
            </Link>
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {data.ultimos_lancamentos.map((item) => (
              <div key={item.id} className="py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-bold text-[var(--text-primary)] truncate">
                    {item.descricao}
                  </div>
                  <div className="text-xs text-[var(--text-muted)]">
                    {item.categoria} · {formatShortDateBR(item.data)} · {item.forma_pagamento}
                  </div>
                </div>
                <span
                  className={`text-sm font-extrabold tabular-nums flex-shrink-0 ${
                    item.tipo === 'entrada' ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {item.tipo === 'entrada' ? '+' : '-'} {formatBRL(item.valor)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Modal confirmar pagamento 1-toque */}
      <Modal
        open={Boolean(payTarget)}
        onClose={() => setPayTarget(null)}
        title="Confirmar Pagamento"
        subtitle={payTarget ? `${payTarget.titulo} · ${formatBRL(payTarget.valor)}` : ''}
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <label className="flex items-start gap-3 p-3.5 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] cursor-pointer">
            <input
              type="checkbox"
              checked={lancarNoCaixa}
              onChange={(e) => setLancarNoCaixa(e.target.checked)}
              className="mt-1 w-4 h-4 accent-[#C9A45C]"
            />
            <div className="text-xs">
              <div className="font-bold text-[var(--text-primary)]">
                Lançar saída automaticamente no Caixa do mês
              </div>
              <div className="text-[var(--text-muted)] mt-0.5">
                Mantém o saldo real atualizado. Se estornar depois, o lançamento no Caixa também é removido.
              </div>
            </div>
          </label>
          <div className="flex gap-2.5">
            <button
              type="button"
              onClick={() => setPayTarget(null)}
              className="flex-1 py-3 rounded-2xl bg-[var(--bg-elevated)] text-sm font-semibold text-[var(--text-secondary)]"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={paying}
              onClick={handleConfirmPay}
              className="flex-1 py-3 rounded-2xl btn-gold text-sm"
            >
              {paying ? 'Confirmando...' : 'Confirmar Baixa'}
            </button>
          </div>
        </div>
      </Modal>

      <QuickEntryModal
        open={Boolean(quickType)}
        initialType={quickType || 'saida'}
        onClose={() => setQuickType(null)}
        onSaved={() => {
          loadData();
          onGlobalMutate?.();
        }}
      />
    </div>
  );
}
