import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowDownCircle,
  ArrowUpCircle,
  Edit3,
  Plus,
  Search,
  Trash2,
} from 'lucide-react';
import { api } from '../api/client';
import {
  QUICK_CATEGORIES,
  formatBRL,
  formatCompetenciaFull,
  formatDateBR,
} from '../utils/format';
import { Modal } from '../components/Modal';
import { QuickEntryModal } from '../components/QuickEntryModal';
import { useToast } from '../components/Toast';

export function CaixaPage({ competencia, refreshSignal, onGlobalMutate }) {
  const { notify } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [periodo, setPeriodo] = useState('mes'); // hoje | semana | mes | todos
  const [tipo, setTipo] = useState(''); // '' | entrada | saida
  const [busca, setBusca] = useState('');
  const [quickType, setQuickType] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await api.listCaixa({ competencia, periodo, tipo, busca });
      setData(res);
    } catch (err) {
      notify(err.message || 'Erro ao carregar Caixa.', 'error');
    } finally {
      setLoading(false);
    }
  }, [competencia, periodo, tipo, busca, notify]);

  useEffect(() => {
    load();
  }, [load, refreshSignal]);

  const handleDelete = async (item) => {
    try {
      await api.deleteCaixa(item.id);
      notify('Lançamento excluído.');
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Não foi possível excluir.', 'error');
    }
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editing) return;
    try {
      await api.updateCaixa(editing.id, {
        tipo: editing.tipo,
        descricao: editing.descricao,
        categoria: editing.categoria,
        valor: Number(String(editing.valor).replace(',', '.')),
        data: editing.data,
        forma_pagamento: editing.forma_pagamento,
      });
      notify('Lançamento atualizado!');
      setEditing(null);
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Falha ao atualizar.', 'error');
    }
  };

  const mensal = data?.resumo_mensal || { entrou: 0, saiu: 0, sobrou: 0 };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-400">
            Caixa Rápido · {formatCompetenciaFull(competencia)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
            Entradas & Saídas
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setQuickType('entrada')}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-2xl bg-emerald-500/15 border border-emerald-500/35 text-emerald-400 text-xs sm:text-sm font-bold hover:bg-emerald-500/25"
          >
            <Plus className="w-4 h-4" /> Entrada
          </button>
          <button
            type="button"
            onClick={() => setQuickType('saida')}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-2xl bg-rose-500/15 border border-rose-500/35 text-rose-400 text-xs sm:text-sm font-bold hover:bg-rose-500/25"
          >
            <Plus className="w-4 h-4" /> Saída
          </button>
        </div>
      </div>

      {/* Fechamento Mensal */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
            Entrou no mês
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-emerald-400 tabular-nums mt-1">
            {formatBRL(mensal.entrou)}
          </div>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
            Saiu no mês
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-rose-400 tabular-nums mt-1">
            {formatBRL(mensal.saiu)}
          </div>
        </div>
        <div className="glass-panel-gold rounded-2xl p-4">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-muted)]">
            Sobrou
          </div>
          <div
            className={`text-lg sm:text-2xl font-extrabold tabular-nums mt-1 ${
              mensal.sobrou >= 0 ? 'text-gold-400' : 'text-rose-400'
            }`}
          >
            {formatBRL(mensal.sobrou)}
          </div>
        </div>
      </div>

      {/* Filtros & Busca */}
      <div className="glass-panel rounded-3xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: 'hoje', label: 'Hoje' },
            { id: 'semana', label: '7 dias' },
            { id: 'mes', label: 'Mês' },
            { id: 'todos', label: 'Todos' },
          ].map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPeriodo(p.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition ${
                periodo === p.id
                  ? 'bg-gold-500/20 text-gold-400 border-gold-500/40'
                  : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)]'
              }`}
            >
              {p.label}
            </button>
          ))}

          <span className="w-px h-5 bg-[var(--border-subtle)] mx-1" />

          {[
            { id: '', label: 'Tudo' },
            { id: 'entrada', label: 'Entradas' },
            { id: 'saida', label: 'Saídas' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTipo(t.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition ${
                tipo === t.id
                  ? 'bg-emerald-500/18 text-emerald-400 border-emerald-500/40'
                  : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="relative md:w-64">
          <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar Uber, mercado..."
            className="w-full input-private rounded-xl pl-9 pr-3 py-2 text-xs"
          />
        </div>
      </div>

      {/* Lista de Movimentações */}
      <div className="glass-panel rounded-3xl overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-sm text-[var(--text-muted)]">
            Carregando lançamentos...
          </div>
        ) : (data?.itens || []).length === 0 ? (
          <div className="p-10 text-center space-y-2">
            <div className="text-sm font-bold text-[var(--text-primary)]">
              Nenhuma movimentação encontrada
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              Toque no botão <strong>+</strong> para registrar uma corrida de Uber, venda ou gasto no mercado.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {data.itens.map((item) => (
              <div
                key={item.id}
                className="px-4 sm:px-6 py-4 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 ${
                      item.tipo === 'entrada'
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : 'bg-rose-500/15 text-rose-400'
                    }`}
                  >
                    {item.tipo === 'entrada' ? (
                      <ArrowUpCircle className="w-5 h-5" />
                    ) : (
                      <ArrowDownCircle className="w-5 h-5" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-[var(--text-primary)] truncate">
                      {item.descricao}
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-[var(--text-muted)] mt-0.5">
                      <span className="px-2 py-0.5 rounded-md bg-[var(--bg-elevated)] font-semibold">
                        {item.categoria}
                      </span>
                      <span>· {formatDateBR(item.data)}</span>
                      <span>· {item.forma_pagamento}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                  <span
                    className={`text-sm sm:text-base font-extrabold tabular-nums ${
                      item.tipo === 'entrada' ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {item.tipo === 'entrada' ? '+' : '-'} {formatBRL(item.valor)}
                  </span>
                  <button
                    type="button"
                    onClick={() => setEditing({ ...item, valor: String(item.valor) })}
                    aria-label="Editar lançamento"
                    className="p-2 rounded-xl text-[var(--text-muted)] hover:text-gold-400 hover:bg-gold-500/10"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(item)}
                    aria-label="Excluir lançamento"
                    className="p-2 rounded-xl text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-500/10"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal de Edição */}
      <Modal
        open={Boolean(editing)}
        onClose={() => setEditing(null)}
        title="Editar Lançamento"
        maxWidth="max-w-md"
      >
        {editing && (
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {['entrada', 'saida'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setEditing({ ...editing, tipo: t })}
                  className={`py-2.5 rounded-xl text-xs font-bold border ${
                    editing.tipo === t
                      ? t === 'entrada'
                        ? 'bg-emerald-500 text-obsidian-950 border-emerald-400'
                        : 'bg-rose-500 text-white border-rose-400'
                      : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-subtle)]'
                  }`}
                >
                  {t === 'entrada' ? 'Entrada' : 'Saída'}
                </button>
              ))}
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Valor (R$)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={editing.valor}
                onChange={(e) => setEditing({ ...editing, valor: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Descrição
              </label>
              <input
                type="text"
                required
                value={editing.descricao}
                onChange={(e) => setEditing({ ...editing, descricao: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                  Categoria
                </label>
                <select
                  value={editing.categoria}
                  onChange={(e) => setEditing({ ...editing, categoria: e.target.value })}
                  className="w-full input-private rounded-xl px-3 py-2.5 text-sm"
                >
                  {[...new Set([...QUICK_CATEGORIES[editing.tipo], editing.categoria])].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                  Data
                </label>
                <input
                  type="date"
                  value={editing.data}
                  onChange={(e) => setEditing({ ...editing, data: e.target.value })}
                  className="w-full input-private rounded-xl px-3 py-2.5 text-sm"
                />
              </div>
            </div>
            <button type="submit" className="w-full btn-gold rounded-2xl py-3 text-sm">
              Salvar Alterações
            </button>
          </form>
        )}
      </Modal>

      <QuickEntryModal
        open={Boolean(quickType)}
        initialType={quickType || 'saida'}
        onClose={() => setQuickType(null)}
        onSaved={() => {
          load();
          onGlobalMutate?.();
        }}
      />
    </div>
  );
}
