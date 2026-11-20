import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  CreditCard,
  Edit3,
  Plus,
  ShoppingBag,
  Trash2,
  Undo2,
} from 'lucide-react';
import { api } from '../api/client';
import {
  formatBRL,
  formatCompetenciaFull,
  formatDateBR,
  formatShortDateBR,
  getTodayISO,
  shiftCompetencia,
} from '../utils/format';
import { ColorPickerField } from '../components/ColorPickerField';
import { Modal } from '../components/Modal';
import { VisualCard } from '../components/VisualCard';
import { useToast } from '../components/Toast';

const COMPRA_CATS = ['Compras', 'Mercado', 'Alimentação', 'Combustível', 'Farmácia', 'Eletrônicos', 'Lazer', 'Outros'];

export function CartoesPage({ competencia, onChangeCompetencia, refreshSignal, onGlobalMutate }) {
  const { notify } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  const [cardModalOpen, setCardModalOpen] = useState(false);
  const [editingCard, setEditingCard] = useState(null);
  const [deleteCardTarget, setDeleteCardTarget] = useState(null);
  const [cardForm, setCardForm] = useState({
    nome: '',
    bandeira: 'Mastercard Black',
    ultimos_digitos: '',
    cor_hex: '#C9A45C',
    limite: '3000',
    dia_fechamento: '10',
    dia_vencimento: '17',
  });

  const [compraModalOpen, setCompraModalOpen] = useState(false);
  const [compraForm, setCompraForm] = useState({
    descricao: '',
    categoria: 'Compras',
    valor: '',
    modo_valor: 'total',
    parcelas_total: '1',
    data_compra: getTodayISO(),
    competencia_inicial: '',
  });

  const [payModalOpen, setPayModalOpen] = useState(false);
  const [lancarNoCaixa, setLancarNoCaixa] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api.listCartoes(competencia);
      setData(res);
      setSelectedId((prev) => {
        if (prev && res.itens.some((c) => c.id === prev)) return prev;
        return res.itens[0]?.id || null;
      });
    } catch (err) {
      notify(err.message || 'Erro ao carregar cartões.', 'error');
    } finally {
      setLoading(false);
    }
  }, [competencia, notify]);

  useEffect(() => {
    load();
  }, [load, refreshSignal]);

  const selectedCard = useMemo(
    () => (data?.itens || []).find((c) => c.id === selectedId) || null,
    [data, selectedId]
  );

  const openNewCard = () => {
    setEditingCard(null);
    setCardForm({
      nome: '',
      bandeira: 'Mastercard Black',
      ultimos_digitos: '',
      cor_hex: '#C9A45C',
      limite: '3000',
      dia_fechamento: '10',
      dia_vencimento: '17',
    });
    setCardModalOpen(true);
  };

  const openEditCard = (card) => {
    setEditingCard(card);
    setCardForm({
      nome: card.nome,
      bandeira: card.bandeira || 'Black',
      ultimos_digitos: card.ultimos_digitos || '',
      cor_hex: card.cor_hex || '#C9A45C',
      limite: String(card.limite || 0),
      dia_fechamento: String(card.dia_fechamento),
      dia_vencimento: String(card.dia_vencimento),
    });
    setCardModalOpen(true);
  };

  const handleSaveCard = async (e) => {
    e.preventDefault();
    const payload = {
      nome: cardForm.nome,
      bandeira: cardForm.bandeira,
      ultimos_digitos: cardForm.ultimos_digitos,
      cor_hex: cardForm.cor_hex,
      limite: Number(String(cardForm.limite || 0).replace(',', '.')),
      dia_fechamento: Number(cardForm.dia_fechamento),
      dia_vencimento: Number(cardForm.dia_vencimento),
    };
    try {
      if (editingCard) {
        await api.updateCartao(editingCard.id, payload);
        notify(`Cartão "${payload.nome}" atualizado!`);
      } else {
        const created = await api.createCartao(payload);
        setSelectedId(created.id);
        notify(`Cartão "${payload.nome}" criado!`);
      }
      setCardModalOpen(false);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao salvar cartão.', 'error');
    }
  };

  const handleConfirmDeleteCard = async () => {
    if (!deleteCardTarget) return;
    try {
      await api.deleteCartao(deleteCardTarget.id);
      notify(`Cartão "${deleteCardTarget.nome}" removido.`);
      setDeleteCardTarget(null);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao excluir cartão.', 'error');
    }
  };

  const openCompraModal = () => {
    setCompraForm({
      descricao: '',
      categoria: 'Compras',
      valor: '',
      modo_valor: 'total',
      parcelas_total: '1',
      data_compra: getTodayISO(),
      competencia_inicial: '',
    });
    setCompraModalOpen(true);
  };

  const handleAddCompra = async (e) => {
    e.preventDefault();
    if (!selectedCard) return;
    try {
      const created = await api.createCartaoCompra(selectedCard.id, {
        descricao: compraForm.descricao,
        categoria: compraForm.categoria,
        valor: Number(String(compraForm.valor).replace(',', '.')),
        modo_valor: compraForm.modo_valor,
        parcelas_total: Number(compraForm.parcelas_total || 1),
        data_compra: compraForm.data_compra,
        competencia_inicial: compraForm.competencia_inicial || null,
      });
      notify(
        `Compra lançada no cartão ${selectedCard.nome}! 1ª parcela em ${formatCompetenciaFull(
          created.competencia_inicial
        )}.`
      );
      setCompraModalOpen(false);
      setCompraForm({
        descricao: '',
        categoria: 'Compras',
        valor: '',
        modo_valor: 'total',
        parcelas_total: '1',
        data_compra: getTodayISO(),
        competencia_inicial: '',
      });
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao lançar compra.', 'error');
    }
  };

  const handleDeleteCompra = async (compraId) => {
    if (!selectedCard) return;
    try {
      await api.deleteCartaoCompra(selectedCard.id, compraId);
      notify('Compra removida da fatura.');
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao remover compra.', 'error');
    }
  };

  const handlePayInvoice = async () => {
    if (!selectedCard) return;
    try {
      await api.pagarCartao(selectedCard.id, {
        competencia,
        lancar_no_caixa: lancarNoCaixa,
      });
      notify(`Fatura de ${selectedCard.nome} marcada como paga!`);
      setPayModalOpen(false);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao pagar fatura.', 'error');
    }
  };

  const handleUndoInvoice = async () => {
    if (!selectedCard) return;
    try {
      await api.estornarCartao(selectedCard.id, competencia);
      notify(`Pagamento da fatura ${selectedCard.nome} estornado.`);
      if (onGlobalMutate) onGlobalMutate();
      else load();
    } catch (err) {
      notify(err.message || 'Erro ao estornar fatura.', 'error');
    }
  };

  const compraNum = Number(String(compraForm.valor || 0).replace(',', '.'));
  const compraParcelas = Math.max(1, Number(compraForm.parcelas_total || 1));
  const previewParcela =
    compraForm.modo_valor === 'parcela'
      ? compraNum
      : compraParcelas > 0
      ? compraNum / compraParcelas
      : 0;
  const previewTotal =
    compraForm.modo_valor === 'parcela' ? compraNum * compraParcelas : compraNum;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gold-700 dark:text-gold-400">
            Meus Cartões · {formatCompetenciaFull(competencia)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
            Cartões de Crédito
          </h1>
        </div>
        <button
          type="button"
          onClick={openNewCard}
          data-testid="new-cartao-btn"
          className="btn-gold rounded-2xl px-5 py-3 text-sm inline-flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          Novo Cartão
        </button>
      </div>

      {/* Resumo Faturas */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">
            Faturas do mês
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-[var(--text-primary)] tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_faturas || 0)}
          </div>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">Pagas</div>
          <div className="text-lg sm:text-2xl font-extrabold text-emerald-700 dark:text-emerald-400 tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_pago || 0)}
          </div>
        </div>
        <div className="glass-panel-gold rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">
            A pagar
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-gold-700 dark:text-gold-400 tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_pendente || 0)}
          </div>
        </div>
      </div>

      {/* Grid de Cartões Visuais */}
      {loading ? (
        <div className="glass-panel rounded-3xl p-10 text-center text-sm text-[var(--text-muted)]">
          Carregando cartões...
        </div>
      ) : (data?.itens || []).length === 0 ? (
        <div className="glass-panel rounded-3xl p-12 text-center space-y-3">
          <CreditCard className="w-9 h-9 text-gold-700 dark:text-gold-400 mx-auto" />
          <div className="text-base font-bold text-[var(--text-primary)]">
            Nenhum cartão cadastrado ainda
          </div>
          <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto">
            Cadastre seus cartões com a cor exata de sua preferência, limite, fechamento e vencimento para acompanhar cada fatura mês a mês.
          </p>
          <button type="button" onClick={openNewCard} className="btn-gold rounded-2xl px-5 py-2.5 text-xs">
            Cadastrar Primeiro Cartão
          </button>
        </div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.itens.map((card) => (
              <VisualCard
                key={card.id}
                variant="cartao"
                item={card}
                selected={card.id === selectedCard?.id}
                onClick={() => setSelectedId(card.id)}
              />
            ))}
          </div>

          {/* Fatura Detalhada do Cartão Selecionado */}
          {selectedCard && (
            <section className="glass-panel-gold rounded-3xl p-5 sm:p-6 space-y-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
                <div className="flex items-center gap-3">
                  <span
                    className="w-4 h-4 rounded-full ring-2 ring-white/25 flex-shrink-0"
                    style={{ backgroundColor: selectedCard.cor_hex }}
                  />
                  <div>
                    <h2 className="text-lg font-extrabold text-[var(--text-primary)]">
                      Fatura · {selectedCard.nome}
                    </h2>
                    <p className="text-xs text-[var(--text-muted)]">
                      Fecha {formatShortDateBR(selectedCard.data_fechamento)} · Vence{' '}
                      {formatShortDateBR(selectedCard.data_vencimento)} · Restante em meses futuros:{' '}
                      <strong className="text-[var(--text-primary)]">
                        {formatBRL(selectedCard.total_futuro)}
                      </strong>
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={openCompraModal}
                    data-testid="add-cartao-compra-btn"
                    className="btn-gold rounded-xl px-4 py-2 text-xs inline-flex items-center gap-1.5"
                  >
                    <ShoppingBag className="w-3.5 h-3.5" />
                    Nova Compra
                  </button>

                  {selectedCard.pago ? (
                    <button
                      type="button"
                      onClick={handleUndoInvoice}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/35 hover:bg-rose-500/15 hover:text-rose-700 dark:hover:text-rose-400"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Fatura Paga <Undo2 className="w-3 h-3" />
                    </button>
                  ) : (
                    selectedCard.total_fatura > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          setLancarNoCaixa(true);
                          setPayModalOpen(true);
                        }}
                        className="px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/35 hover:bg-emerald-500/25"
                      >
                        Pagar Fatura ({formatBRL(selectedCard.total_fatura)})
                      </button>
                    )
                  )}

                  <button
                    type="button"
                    onClick={() => openEditCard(selectedCard)}
                    aria-label="Editar cartão"
                    className="p-2 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-gold-700 dark:hover:text-gold-400"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteCardTarget(selectedCard)}
                    aria-label="Excluir cartão"
                    className="p-2 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-rose-600 dark:hover:text-rose-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {selectedCard.itens.length === 0 ? (
                <div className="py-8 text-center text-xs text-[var(--text-muted)] space-y-2.5">
                  <div>Nenhuma compra lançada na fatura de {formatCompetenciaFull(competencia)}.</div>
                  {selectedCard.total_futuro > 0 && (
                    <div className="space-y-2">
                      <div className="text-gold-700 dark:text-gold-400 font-semibold">
                        Você tem {formatBRL(selectedCard.total_futuro)} projetados nos próximos meses.
                      </div>
                      {onChangeCompetencia && (
                        <button
                          type="button"
                          onClick={() => onChangeCompetencia(shiftCompetencia(competencia, 1))}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-gold-500/15 text-gold-700 dark:text-gold-400 border border-gold-500/35 text-xs font-bold hover:bg-gold-500/25 transition"
                        >
                          Ver próxima fatura →
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-[var(--border-subtle)]">
                  {selectedCard.itens.map((item) => (
                    <div
                      key={item.id}
                      className="py-3.5 flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-bold text-[var(--text-primary)] truncate">
                            {item.descricao}
                          </span>
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-gold-500/15 text-gold-700 dark:text-gold-400 border border-gold-500/35">
                            {item.parcelas_total > 1
                              ? `Parcela ${item.parcela_atual}/${item.parcelas_total}`
                              : 'À vista'}
                          </span>
                        </div>
                        <div className="text-xs text-[var(--text-muted)] mt-0.5">
                          {item.categoria} · Compra em {formatDateBR(item.data_compra)}
                          {item.parcelas_total > 1 && ` · Total ${formatBRL(item.valor_total)}`}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className="text-sm sm:text-base font-extrabold tabular-nums text-[var(--text-primary)]">
                          {formatBRL(item.valor_parcela)}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDeleteCompra(item.id)}
                          aria-label={`Remover compra ${item.descricao}`}
                          className="p-2 rounded-xl text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-500/10"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </>
      )}

      {/* Modal Criar / Editar Cartão */}
      <Modal
        open={cardModalOpen}
        onClose={() => setCardModalOpen(false)}
        title={editingCard ? 'Editar Cartão' : 'Novo Cartão de Crédito'}
        subtitle="A cor escolhida abaixo é aplicada fielmente ao cartão visual e aos alertas"
      >
        <form onSubmit={handleSaveCard} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Nome do cartão
              </label>
              <input
                type="text"
                required
                value={cardForm.nome}
                onChange={(e) => setCardForm({ ...cardForm, nome: e.target.value })}
                placeholder="Ex.: Nubank, Inter Black..."
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Bandeira / Tipo
              </label>
              <input
                type="text"
                value={cardForm.bandeira}
                onChange={(e) => setCardForm({ ...cardForm, bandeira: e.target.value })}
                placeholder="Mastercard Black, Visa..."
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Limite (R$)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={cardForm.limite}
                onChange={(e) => setCardForm({ ...cardForm, limite: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                4 últimos dígitos (opc.)
              </label>
              <input
                type="text"
                maxLength={4}
                value={cardForm.ultimos_digitos}
                onChange={(e) => setCardForm({ ...cardForm, ultimos_digitos: e.target.value })}
                placeholder="8842"
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Dia de fechamento
              </label>
              <input
                type="number"
                min="1"
                max="31"
                required
                value={cardForm.dia_fechamento}
                onChange={(e) => setCardForm({ ...cardForm, dia_fechamento: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Dia de vencimento
              </label>
              <input
                type="number"
                min="1"
                max="31"
                required
                value={cardForm.dia_vencimento}
                onChange={(e) => setCardForm({ ...cardForm, dia_vencimento: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
          </div>

          <ColorPickerField
            label="Cor do Cartão"
            value={cardForm.cor_hex}
            onChange={(hex) => setCardForm({ ...cardForm, cor_hex: hex })}
          />

          <button type="submit" className="w-full btn-gold rounded-2xl py-3.5 text-sm">
            {editingCard ? 'Salvar Alterações' : 'Criar Cartão'}
          </button>
        </form>
      </Modal>

      {/* Modal Nova Compra no Cartão */}
      <Modal
        open={compraModalOpen}
        onClose={() => setCompraModalOpen(false)}
        title={`Nova Compra · ${selectedCard?.nome || ''}`}
        subtitle="À vista ou parcelada (Nx) com projeção automática nas faturas futuras"
      >
        <form onSubmit={handleAddCompra} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Descrição da compra
            </label>
            <input
              type="text"
              required
              value={compraForm.descricao}
              onChange={(e) => setCompraForm({ ...compraForm, descricao: e.target.value })}
              placeholder="Ex.: Farmácia, Tênis, Pneu carro..."
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-2 p-1 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
            <button
              type="button"
              onClick={() => setCompraForm({ ...compraForm, modo_valor: 'total' })}
              className={`py-2 rounded-xl text-xs font-bold ${
                compraForm.modo_valor === 'total' ? 'btn-gold' : 'text-[var(--text-secondary)]'
              }`}
            >
              Valor Total
            </button>
            <button
              type="button"
              onClick={() => setCompraForm({ ...compraForm, modo_valor: 'parcela' })}
              className={`py-2 rounded-xl text-xs font-bold ${
                compraForm.modo_valor === 'parcela' ? 'btn-gold' : 'text-[var(--text-secondary)]'
              }`}
            >
              Valor da Parcela
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                {compraForm.modo_valor === 'parcela' ? 'Valor de cada parcela (R$)' : 'Valor total (R$)'}
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={compraForm.valor}
                onChange={(e) => setCompraForm({ ...compraForm, valor: e.target.value })}
                placeholder="300,00"
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Parcelas (Nx)
              </label>
              <input
                type="number"
                min="1"
                max="72"
                required
                value={compraForm.parcelas_total}
                onChange={(e) => setCompraForm({ ...compraForm, parcelas_total: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
          </div>

          {compraNum > 0 && (
            <div className="rounded-xl bg-gold-500/12 border border-gold-500/35 px-3.5 py-2.5 text-xs text-gold-700 dark:text-gold-300 font-semibold tabular-nums">
              Prévia: {compraParcelas}x de {formatBRL(previewParcela)} · Total {formatBRL(previewTotal)}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5">
              Categoria
            </label>
            <div className="flex flex-wrap gap-1.5">
              {COMPRA_CATS.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCompraForm({ ...compraForm, categoria: cat })}
                  className={`px-2.5 py-1 rounded-xl text-xs font-semibold border transition ${
                    compraForm.categoria === cat
                      ? 'bg-gold-500/20 border-gold-500/50 text-gold-700 dark:text-gold-300'
                      : 'bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)]'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Data da compra
              </label>
              <input
                type="date"
                value={compraForm.data_compra}
                onChange={(e) => setCompraForm({ ...compraForm, data_compra: e.target.value })}
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                1ª fatura (opcional)
              </label>
              <input
                type="month"
                value={compraForm.competencia_inicial}
                onChange={(e) =>
                  setCompraForm({ ...compraForm, competencia_inicial: e.target.value })
                }
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
              />
            </div>
          </div>

          <button type="submit" className="w-full btn-gold rounded-2xl py-3.5 text-sm">
            Adicionar à Fatura
          </button>
        </form>
      </Modal>

      {/* Modal Pagar Fatura */}
      <Modal
        open={payModalOpen}
        onClose={() => setPayModalOpen(false)}
        title={`Pagar Fatura · ${selectedCard?.nome || ''}`}
        subtitle={selectedCard ? formatBRL(selectedCard.total_fatura) : ''}
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
                Registra o pagamento no fluxo do mês e estorna limpo caso desfaça.
              </div>
            </div>
          </label>
          <button type="button" onClick={handlePayInvoice} className="w-full btn-gold rounded-2xl py-3 text-sm">
            Confirmar Pagamento da Fatura
          </button>
        </div>
      </Modal>

      {/* Modal Confirmar Exclusão de Cartão */}
      <Modal
        open={Boolean(deleteCardTarget)}
        onClose={() => setDeleteCardTarget(null)}
        title="Excluir Cartão?"
        subtitle={deleteCardTarget ? deleteCardTarget.nome : ''}
        maxWidth="max-w-md"
      >
        <div className="space-y-4">
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Isso excluirá o cartão <strong>{deleteCardTarget?.nome}</strong>, todas as compras
            lançadas nele e estornará eventuais baixas de fatura vinculadas ao Caixa. Para apagar
            apenas uma compra sem perder o cartão, use a lixeira ao lado da compra.
          </p>
          <div className="flex gap-2.5">
            <button
              type="button"
              onClick={() => setDeleteCardTarget(null)}
              className="flex-1 py-3 rounded-2xl bg-[var(--bg-elevated)] text-sm font-semibold text-[var(--text-secondary)]"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirmDeleteCard}
              className="flex-1 py-3 rounded-2xl bg-rose-600 text-white font-bold text-sm hover:bg-rose-700 transition"
            >
              Excluir Cartão
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
