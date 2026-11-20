import React, { useCallback, useEffect, useState } from 'react';
import {
  CalendarCheck2,
  CheckCircle2,
  Edit3,
  Plus,
  Repeat,
  Trash2,
  Undo2,
} from 'lucide-react';
import { api } from '../api/client';
import {
  formatBRL,
  formatCompetenciaFull,
  formatShortDateBR,
  getUrgencyMeta,
} from '../utils/format';
import { ColorPickerField } from '../components/ColorPickerField';
import { Modal } from '../components/Modal';
import { useToast } from '../components/Toast';

export function ContasPage({ competencia, refreshSignal, onGlobalMutate }) {
  const { notify } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editingConta, setEditingConta] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [payTarget, setPayTarget] = useState(null);
  const [lancarNoCaixa, setLancarNoCaixa] = useState(true);

  const [form, setForm] = useState({
    nome: '',
    categoria: 'Moradia',
    tipo: 'fixa',
    valor: '',
    dia_vencimento: '15',
    parcelas_total: '12',
    cor_hex: '#C9A45C',
    observacao: '',
  });

  const load = useCallback(async () => {
    try {
      const res = await api.listContas(competencia);
      setData(res);
    } catch (err) {
      notify(err.message || 'Erro ao carregar contas.', 'error');
    } finally {
      setLoading(false);
    }
  }, [competencia, notify]);

  useEffect(() => {
    load();
  }, [load, refreshSignal]);

  const openNewConta = () => {
    setEditingConta(null);
    setForm({
      nome: '',
      categoria: 'Moradia',
      tipo: 'fixa',
      valor: '',
      dia_vencimento: '15',
      parcelas_total: '12',
      cor_hex: '#C9A45C',
      observacao: '',
    });
    setCreateOpen(true);
  };

  const openEditConta = (item) => {
    setEditingConta(item);
    setForm({
      nome: item.nome || '',
      categoria: item.categoria || 'Moradia',
      tipo: item.tipo || 'fixa',
      valor: String(item.valor ?? ''),
      dia_vencimento: String(item.dia_vencimento ?? 15),
      parcelas_total: String(item.parcelas_total || 12),
      cor_hex: item.cor_hex || '#C9A45C',
      observacao: item.observacao || '',
    });
    setCreateOpen(true);
  };

  const handleSaveConta = async (e) => {
    e.preventDefault();
    const payload = {
      nome: form.nome,
      categoria: form.categoria,
      tipo: form.tipo,
      valor: Number(String(form.valor).replace(',', '.')),
      dia_vencimento: Number(form.dia_vencimento),
      parcelas_total: form.tipo === 'parcelada' ? Number(form.parcelas_total) : null,
      cor_hex: form.cor_hex,
      observacao: form.observacao,
    };
    try {
      if (editingConta) {
        await api.updateConta(editingConta.id, payload);
        notify(`Conta "${form.nome}" atualizada!`);
      } else {
        await api.createConta({ ...payload, competencia_inicio: competencia });
        notify(`Conta "${form.nome}" cadastrada!`);
      }
      setCreateOpen(false);
      setEditingConta(null);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao salvar conta.', 'error');
    }
  };

  const handlePay = async () => {
    if (!payTarget) return;
    try {
      await api.pagarConta(payTarget.id, {
        competencia,
        lancar_no_caixa: lancarNoCaixa,
      });
      notify(`Conta "${payTarget.nome}" paga!`);
      setPayTarget(null);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Falha ao pagar conta.', 'error');
    }
  };

  const handleUndo = async (item) => {
    try {
      await api.estornarConta(item.id, competencia);
      notify(`Baixa de "${item.nome}" estornada.`);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Falha ao estornar.', 'error');
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.deleteConta(deleteTarget.id);
      notify(`Conta "${deleteTarget.nome}" removida.`);
      setDeleteTarget(null);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Falha ao remover conta.', 'error');
    }
  };

  const resumo = data?.resumo || { total: 0, pago: 0, pendente: 0 };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-700 dark:text-gold-400">
            Compromissos · {formatCompetenciaFull(competencia)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
            Contas a Vencer
          </h1>
        </div>

        <button
          type="button"
          onClick={openNewConta}
          data-testid="new-conta-btn"
          className="btn-gold rounded-2xl px-5 py-3 text-sm inline-flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          Nova Conta
        </button>
      </div>

      {/* Resumo */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">Total mês</div>
          <div className="text-lg sm:text-2xl font-extrabold text-[var(--text-primary)] tabular-nums mt-1">
            {formatBRL(resumo.total)}
          </div>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">Pago</div>
          <div className="text-lg sm:text-2xl font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums mt-1">
            {formatBRL(resumo.pago)}
          </div>
        </div>
        <div className="glass-panel-gold rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">Falta pagar</div>
          <div className="text-lg sm:text-2xl font-extrabold text-amber-700 dark:text-amber-400 tabular-nums mt-1">
            {formatBRL(resumo.pendente)}
          </div>
        </div>
      </div>

      {/* Lista de Contas */}
      <div className="glass-panel rounded-3xl overflow-hidden">
        {loading ? (
          <div className="p-10 text-center text-sm text-[var(--text-muted)]">Carregando contas...</div>
        ) : (data?.itens || []).length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <CalendarCheck2 className="w-8 h-8 text-gold-700 dark:text-gold-400 mx-auto" />
            <div className="text-sm font-bold text-[var(--text-primary)]">
              Nenhuma conta cadastrada para {formatCompetenciaFull(competencia)}
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              Cadastre contas fixas (aluguel, condomínio, internet) ou financiamentos parcelados.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--border-subtle)]">
            {data.itens.map((item) => {
              const urg = getUrgencyMeta(item.status_urgencia, item.dias_restantes);
              return (
                <div
                  key={item.id}
                  className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-start sm:items-center gap-3 min-w-0">
                    <span
                      className="w-3.5 h-3.5 rounded-full flex-shrink-0 mt-1 sm:mt-0 ring-2 ring-white/15"
                      style={{ backgroundColor: item.cor_hex }}
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-sm text-[var(--text-primary)] truncate">
                          {item.nome}
                        </span>
                        {item.tipo === 'parcelada' ? (
                          <span className="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-gold-500/15 text-gold-700 dark:text-gold-400 border border-gold-500/35">
                            Parcela {item.parcela_atual}/{item.parcelas_total}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-[var(--bg-elevated)] text-[var(--text-secondary)]">
                            <Repeat className="w-3 h-3" /> Fixa
                          </span>
                        )}
                        <span
                          className={`px-2 py-0.5 rounded-lg text-[10px] font-bold border ${urg.badgeClass}`}
                        >
                          {urg.countdown}
                        </span>
                      </div>
                      <div className="text-xs text-[var(--text-muted)] mt-0.5">
                        {item.categoria} · Vence {formatShortDateBR(item.data_vencimento)}
                        {item.dia_ajustado ? ' (ajustado mês curto)' : ''}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-2 pl-6 sm:pl-0">
                    <span className="text-base font-extrabold tabular-nums text-[var(--text-primary)] mr-1">
                      {formatBRL(item.valor_efetivo)}
                    </span>
                    {item.pago ? (
                      <button
                        type="button"
                        onClick={() => handleUndo(item)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/35 hover:bg-rose-500/15 hover:text-rose-700 dark:hover:text-rose-400"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" /> Pago <Undo2 className="w-3 h-3" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setLancarNoCaixa(true);
                          setPayTarget(item);
                        }}
                        className="px-3.5 py-1.5 rounded-xl btn-gold text-xs"
                      >
                        Pagar
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => openEditConta(item)}
                      aria-label={`Editar conta ${item.nome}`}
                      className="p-2 rounded-xl text-[var(--text-muted)] hover:text-gold-700 dark:hover:text-gold-400 hover:bg-gold-500/10"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(item)}
                      aria-label={`Excluir conta ${item.nome}`}
                      className="p-2 rounded-xl text-[var(--text-muted)] hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-500/10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal Criar / Editar Conta */}
      <Modal
        open={createOpen}
        onClose={() => {
          setCreateOpen(false);
          setEditingConta(null);
        }}
        title={editingConta ? 'Editar Conta a Vencer' : 'Nova Conta a Vencer'}
        subtitle="Contas fixas mensais ou financiamentos parcelados"
      >
        <form onSubmit={handleSaveConta} className="space-y-4">
          <div className="grid grid-cols-2 gap-2 p-1 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
            <button
              type="button"
              onClick={() => setForm({ ...form, tipo: 'fixa' })}
              className={`py-2 rounded-xl text-xs font-bold transition ${
                form.tipo === 'fixa'
                  ? 'btn-gold'
                  : 'text-[var(--text-secondary)]'
              }`}
            >
              Fixa (todo mês)
            </button>
            <button
              type="button"
              onClick={() => setForm({ ...form, tipo: 'parcelada' })}
              className={`py-2 rounded-xl text-xs font-bold transition ${
                form.tipo === 'parcelada'
                  ? 'btn-gold'
                  : 'text-[var(--text-secondary)]'
              }`}
            >
              Parcelada (Nx)
            </button>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Nome da conta
            </label>
            <input
              type="text"
              required
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              placeholder="Ex.: Condomínio, Aluguel, Financiamento Moto"
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Valor mensal (R$)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={form.valor}
                onChange={(e) => setForm({ ...form, valor: e.target.value })}
                placeholder="450,00"
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Dia do vencimento
              </label>
              <input
                type="number"
                min="1"
                max="31"
                required
                value={form.dia_vencimento}
                onChange={(e) => setForm({ ...form, dia_vencimento: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Categoria
              </label>
              <input
                type="text"
                value={form.categoria}
                onChange={(e) => setForm({ ...form, categoria: e.target.value })}
                placeholder="Moradia, Energia, Veículo..."
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
            {form.tipo === 'parcelada' && (
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                  Qtd. parcelas
                </label>
                <input
                  type="number"
                  min="1"
                  max="480"
                  required
                  value={form.parcelas_total}
                  onChange={(e) => setForm({ ...form, parcelas_total: e.target.value })}
                  className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
                />
              </div>
            )}
          </div>

          <ColorPickerField
            label="Cor da conta"
            value={form.cor_hex}
            onChange={(hex) => setForm({ ...form, cor_hex: hex })}
          />

          <button type="submit" className="w-full btn-gold rounded-2xl py-3.5 text-sm">
            {editingConta ? 'Salvar Alterações' : 'Cadastrar Conta'}
          </button>
        </form>
      </Modal>

      {/* Modal Confirmar Exclusão */}
      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Excluir Conta?"
        subtitle={deleteTarget ? deleteTarget.nome : ''}
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Ao excluir esta conta, o compromisso e todas as baixas vinculadas a ela no Caixa serão
            removidos de forma limpa. Deseja continuar?
          </p>
          <div className="flex gap-2.5">
            <button
              type="button"
              onClick={() => setDeleteTarget(null)}
              className="flex-1 py-3 rounded-2xl bg-[var(--bg-elevated)] text-sm font-semibold text-[var(--text-secondary)]"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirmDelete}
              className="flex-1 py-3 rounded-2xl bg-rose-600 text-white font-bold text-sm hover:bg-rose-700 transition"
            >
              Confirmar Exclusão
            </button>
          </div>
        </div>
      </Modal>

      {/* Modal Baixa */}
      <Modal
        open={Boolean(payTarget)}
        onClose={() => setPayTarget(null)}
        title="Pagar Conta"
        subtitle={payTarget ? `${payTarget.nome} · ${formatBRL(payTarget.valor)}` : ''}
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
                Lançar saída no Caixa do mês
              </div>
              <div className="text-[var(--text-muted)] mt-0.5">
                Desconta automaticamente do saldo real do mês e estorna se desfazer.
              </div>
            </div>
          </label>
          <button type="button" onClick={handlePay} className="w-full btn-gold rounded-2xl py-3 text-sm">
            Confirmar Pagamento
          </button>
        </div>
      </Modal>
    </div>
  );
}
