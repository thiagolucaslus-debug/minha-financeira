import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BellRing,
  CheckCircle2,
  Edit3,
  Layers,
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
} from '../utils/format';
import { ColorPickerField } from '../components/ColorPickerField';
import { Modal } from '../components/Modal';
import { VisualCard } from '../components/VisualCard';
import { useToast } from '../components/Toast';

export function ModulosDividaPage({ competencia, refreshSignal, onGlobalMutate }) {
  const { notify } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  const [modModalOpen, setModModalOpen] = useState(false);
  const [editingMod, setEditingMod] = useState(null);
  const [modForm, setModForm] = useState({
    nome: '',
    descricao: '',
    cor_hex: '#10B981',
    dia_fechamento: '10',
    dia_vencimento: '18',
    limite: '',
  });

  const [compraModalOpen, setCompraModalOpen] = useState(false);
  const [compraForm, setCompraForm] = useState({
    descricao: '',
    categoria: 'Dívidas',
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
      const res = await api.listModulos(competencia);
      setData(res);
      setSelectedId((prev) => {
        if (prev && res.itens.some((m) => m.id === prev)) return prev;
        return res.itens[0]?.id || null;
      });
    } catch (err) {
      notify(err.message || 'Erro ao carregar módulos de dívida.', 'error');
    } finally {
      setLoading(false);
    }
  }, [competencia, notify]);

  useEffect(() => {
    load();
  }, [load, refreshSignal]);

  const selectedMod = useMemo(
    () => (data?.itens || []).find((m) => m.id === selectedId) || null,
    [data, selectedId]
  );

  const openNewModulo = () => {
    setEditingMod(null);
    setModForm({
      nome: '',
      descricao: '',
      cor_hex: '#10B981',
      dia_fechamento: '10',
      dia_vencimento: '18',
      limite: '',
    });
    setModModalOpen(true);
  };

  const openEditModulo = (mod) => {
    setEditingMod(mod);
    setModForm({
      nome: mod.nome,
      descricao: mod.descricao || '',
      cor_hex: mod.cor_hex || '#10B981',
      dia_fechamento: String(mod.dia_fechamento),
      dia_vencimento: String(mod.dia_vencimento),
      limite: mod.limite ? String(mod.limite) : '',
    });
    setModModalOpen(true);
  };

  const handleSaveModulo = async (e) => {
    e.preventDefault();
    const payload = {
      nome: modForm.nome,
      descricao: modForm.descricao,
      cor_hex: modForm.cor_hex,
      dia_fechamento: Number(modForm.dia_fechamento),
      dia_vencimento: Number(modForm.dia_vencimento),
      limite: Number(String(modForm.limite || 0).replace(',', '.')) || 0,
    };
    try {
      if (editingMod) {
        await api.updateModulo(editingMod.id, payload);
        notify(`Módulo "${payload.nome}" atualizado!`);
      } else {
        const created = await api.createModulo(payload);
        setSelectedId(created.id);
        notify(`Módulo "${payload.nome}" criado! Agora você pode lançar compras dentro dele.`);
      }
      setModModalOpen(false);
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao salvar módulo.', 'error');
    }
  };

  const handleDeleteModulo = async (mod) => {
    try {
      await api.deleteModulo(mod.id);
      notify(`Módulo "${mod.nome}" excluído.`);
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao excluir módulo.', 'error');
    }
  };

  const handleAddCompra = async (e) => {
    e.preventDefault();
    if (!selectedMod) return;
    try {
      const created = await api.createModuloCompra(selectedMod.id, {
        descricao: compraForm.descricao,
        categoria: compraForm.categoria,
        valor: Number(String(compraForm.valor).replace(',', '.')),
        modo_valor: compraForm.modo_valor,
        parcelas_total: Number(compraForm.parcelas_total || 1),
        data_compra: compraForm.data_compra,
        competencia_inicial: compraForm.competencia_inicial || null,
      });
      notify(
        `Compra adicionada em ${selectedMod.nome}! 1ª cobrança em ${formatCompetenciaFull(
          created.competencia_inicial
        )}.`
      );
      setCompraModalOpen(false);
      setCompraForm({
        descricao: '',
        categoria: 'Dívidas',
        valor: '',
        modo_valor: 'total',
        parcelas_total: '1',
        data_compra: getTodayISO(),
        competencia_inicial: '',
      });
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao lançar compra no módulo.', 'error');
    }
  };

  const handleDeleteCompra = async (compraId) => {
    if (!selectedMod) return;
    try {
      await api.deleteModuloCompra(selectedMod.id, compraId);
      notify('Compra removida do módulo (módulo mantido intacto).');
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao excluir compra.', 'error');
    }
  };

  const handlePayMes = async () => {
    if (!selectedMod) return;
    try {
      await api.pagarModulo(selectedMod.id, {
        competencia,
        lancar_no_caixa: lancarNoCaixa,
      });
      notify(`Módulo ${selectedMod.nome} quitado em ${formatCompetenciaFull(competencia)}!`);
      setPayModalOpen(false);
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao quitar módulo.', 'error');
    }
  };

  const handleUndoMes = async () => {
    if (!selectedMod) return;
    try {
      await api.estornarModulo(selectedMod.id, competencia);
      notify(`Baixa do módulo ${selectedMod.nome} estornada.`);
      load();
      onGlobalMutate?.();
    } catch (err) {
      notify(err.message || 'Erro ao estornar módulo.', 'error');
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
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">
            Estilo Cartão Virtual · {formatCompetenciaFull(competencia)}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--text-primary)] mt-1">
            Módulos de Dívida
          </h1>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Crie módulos como <strong>Thiago</strong> ou <strong>Seu Luiz</strong>, lance várias compras à vista ou parceladas dentro de cada um e receba alertas automáticos no Radar.
          </p>
        </div>

        <button
          type="button"
          onClick={openNewModulo}
          data-testid="new-modulo-btn"
          className="btn-gold rounded-2xl px-5 py-3 text-sm inline-flex items-center justify-center gap-2 flex-shrink-0"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          Novo Módulo
        </button>
      </div>

      {/* Resumo dos Módulos */}
      <div className="grid grid-cols-3 gap-3 sm:gap-4">
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">
            Total no mês
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-[var(--text-primary)] tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_mes || 0)}
          </div>
        </div>
        <div className="glass-panel rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">Pago</div>
          <div className="text-lg sm:text-2xl font-extrabold text-emerald-400 tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_pago || 0)}
          </div>
        </div>
        <div className="glass-panel-gold rounded-2xl p-4">
          <div className="text-[11px] uppercase font-semibold text-[var(--text-muted)]">
            Pendente
          </div>
          <div className="text-lg sm:text-2xl font-extrabold text-gold-400 tabular-nums mt-1">
            {formatBRL(data?.resumo?.total_pendente || 0)}
          </div>
        </div>
      </div>

      {/* Grid dos Módulos (Cartões Virtuais) */}
      {loading ? (
        <div className="glass-panel rounded-3xl p-10 text-center text-sm text-[var(--text-muted)]">
          Carregando módulos...
        </div>
      ) : (data?.itens || []).length === 0 ? (
        <div className="glass-panel-gold rounded-3xl p-12 text-center space-y-3">
          <Layers className="w-9 h-9 text-emerald-400 mx-auto" />
          <div className="text-base font-bold text-[var(--text-primary)]">
            Crie seu primeiro Módulo de Dívida
          </div>
          <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto">
            Exemplo: crie um módulo chamado <strong>Thiago</strong> e outro chamado <strong>Seu Luiz</strong>.
            Cada módulo funciona como um cartão próprio com fechamento, vencimento e parcelamento automático.
          </p>
          <button type="button" onClick={openNewModulo} className="btn-gold rounded-2xl px-5 py-2.5 text-xs">
            Criar Primeiro Módulo
          </button>
        </div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.itens.map((mod) => (
              <VisualCard
                key={mod.id}
                variant="modulo"
                item={mod}
                selected={mod.id === selectedMod?.id}
                onClick={() => setSelectedId(mod.id)}
              />
            ))}
          </div>

          {/* Extrato Mensal Item a Item do Módulo Selecionado */}
          {selectedMod && (
            <section className="glass-panel-gold rounded-3xl p-5 sm:p-6 space-y-5">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--border-subtle)]">
                <div className="flex items-start sm:items-center gap-3">
                  <span
                    className="w-4 h-4 rounded-full ring-2 ring-white/25 flex-shrink-0 mt-1 sm:mt-0"
                    style={{ backgroundColor: selectedMod.cor_hex }}
                  />
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-extrabold text-[var(--text-primary)]">
                        Módulo {selectedMod.nome}
                      </h2>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        <BellRing className="w-3 h-3" /> Alerta ativo no Radar
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">
                      {selectedMod.descricao ? `${selectedMod.descricao} · ` : ''}
                      Fecha {formatShortDateBR(selectedMod.data_fechamento)} · Vence{' '}
                      {formatShortDateBR(selectedMod.data_vencimento)} · Próximos meses:{' '}
                      <strong className="text-[var(--text-primary)]">
                        {formatBRL(selectedMod.total_futuro)}
                      </strong>
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setCompraModalOpen(true)}
                    data-testid="add-modulo-compra-btn"
                    className="btn-gold rounded-xl px-3.5 py-2 text-xs inline-flex items-center gap-1.5 whitespace-nowrap"
                  >
                    <ShoppingBag className="w-3.5 h-3.5" />
                    Nova Compra
                  </button>

                  {selectedMod.pago ? (
                    <button
                      type="button"
                      onClick={handleUndoMes}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/35 hover:bg-rose-500/15 hover:text-rose-400"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Mês Quitado <Undo2 className="w-3 h-3" />
                    </button>
                  ) : (
                    selectedMod.total_mes > 0 && (
                      <button
                        type="button"
                        onClick={() => {
                          setLancarNoCaixa(true);
                          setPayModalOpen(true);
                        }}
                        className="px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/35 hover:bg-emerald-500/25"
                      >
                        Pagar Mês ({formatBRL(selectedMod.total_mes)})
                      </button>
                    )
                  )}

                  <button
                    type="button"
                    onClick={() => openEditModulo(selectedMod)}
                    aria-label="Editar módulo"
                    className="p-2 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-gold-400"
                  >
                    <Edit3 className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteModulo(selectedMod)}
                    aria-label="Excluir módulo"
                    className="p-2 rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-rose-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {selectedMod.itens.length === 0 ? (
                <div className="py-8 text-center text-xs text-[var(--text-muted)] space-y-1.5">
                  <div>Nenhuma compra ou parcela vencendo em {formatCompetenciaFull(competencia)} neste módulo.</div>
                  {selectedMod.total_futuro > 0 && (
                    <div className="text-emerald-400 font-semibold">
                      Há {formatBRL(selectedMod.total_futuro)} projetados nos próximos meses — avance o mês no topo para conferir.
                    </div>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-[var(--border-subtle)]">
                  {selectedMod.itens.map((item) => (
                    <div
                      key={item.id}
                      className="py-3.5 flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-bold text-[var(--text-primary)] truncate">
                            {item.descricao}
                          </span>
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-gold-500/15 text-gold-400 border border-gold-500/30">
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

      {/* Modal Criar / Editar Módulo de Dívida */}
      <Modal
        open={modModalOpen}
        onClose={() => setModModalOpen(false)}
        title={editingMod ? 'Editar Módulo de Dívida' : 'Novo Módulo de Dívida'}
        subtitle="Funciona como um cartão virtual com compras, parcelas e alerta de vencimento"
      >
        <form onSubmit={handleSaveModulo} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Nome do módulo
            </label>
            <input
              type="text"
              required
              value={modForm.nome}
              onChange={(e) => setModForm({ ...modForm, nome: e.target.value })}
              placeholder="Ex.: Thiago, Seu Luiz, Cartão Emprestado..."
              data-testid="input-modulo-nome"
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
              Descrição curta (opcional)
            </label>
            <input
              type="text"
              value={modForm.descricao}
              onChange={(e) => setModForm({ ...modForm, descricao: e.target.value })}
              placeholder="Ex.: Compras feitas no cartão do Seu Luiz"
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Dia fechamento
              </label>
              <input
                type="number"
                min="1"
                max="31"
                required
                value={modForm.dia_fechamento}
                onChange={(e) => setModForm({ ...modForm, dia_fechamento: e.target.value })}
                className="w-full input-private rounded-xl px-3 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Dia vencimento
              </label>
              <input
                type="number"
                min="1"
                max="31"
                required
                value={modForm.dia_vencimento}
                onChange={(e) => setModForm({ ...modForm, dia_vencimento: e.target.value })}
                className="w-full input-private rounded-xl px-3 py-2.5 text-sm font-bold"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1">
                Teto (opc.)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={modForm.limite}
                onChange={(e) => setModForm({ ...modForm, limite: e.target.value })}
                placeholder="0"
                className="w-full input-private rounded-xl px-3 py-2.5 text-sm font-bold"
              />
            </div>
          </div>

          <ColorPickerField
            label="Cor do Módulo"
            value={modForm.cor_hex}
            onChange={(hex) => setModForm({ ...modForm, cor_hex: hex })}
          />

          <button
            type="submit"
            data-testid="save-modulo-btn"
            className="w-full btn-gold rounded-2xl py-3.5 text-sm"
          >
            {editingMod ? 'Salvar Alterações' : 'Criar Módulo'}
          </button>
        </form>
      </Modal>

      {/* Modal Nova Compra no Módulo */}
      <Modal
        open={compraModalOpen}
        onClose={() => setCompraModalOpen(false)}
        title={`Lançar Compra · Módulo ${selectedMod?.nome || ''}`}
        subtitle="À vista ou parcelada (Nx) com cálculo automático mês a mês"
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
              placeholder="Ex.: Celular, Supermercado, Oficina..."
              data-testid="input-mod-compra-desc"
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
                {compraForm.modo_valor === 'parcela' ? 'Valor da parcela (R$)' : 'Valor total (R$)'}
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={compraForm.valor}
                onChange={(e) => setCompraForm({ ...compraForm, valor: e.target.value })}
                placeholder="600,00"
                data-testid="input-mod-compra-valor"
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
                data-testid="input-mod-compra-parcelas"
                className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm font-bold"
              />
            </div>
          </div>

          {compraNum > 0 && (
            <div className="rounded-xl bg-emerald-500/12 border border-emerald-500/30 px-3.5 py-2.5 text-xs text-emerald-300 font-semibold tabular-nums">
              Prévia: {compraParcelas}x de {formatBRL(previewParcela)} · Total {formatBRL(previewTotal)}
            </div>
          )}

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
                1ª cobrança (opcional)
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

          <button
            type="submit"
            data-testid="save-mod-compra-btn"
            className="w-full btn-gold rounded-2xl py-3.5 text-sm"
          >
            Salvar Compra no Módulo
          </button>
        </form>
      </Modal>

      {/* Modal Pagar Mês do Módulo */}
      <Modal
        open={payModalOpen}
        onClose={() => setPayModalOpen(false)}
        title={`Quitar Módulo ${selectedMod?.nome || ''}`}
        subtitle={selectedMod ? formatBRL(selectedMod.total_mes) : ''}
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
                Abate do seu saldo mensal e estorna automaticamente se desfazer.
              </div>
            </div>
          </label>
          <button type="button" onClick={handlePayMes} className="w-full btn-gold rounded-2xl py-3 text-sm">
            Confirmar Pagamento
          </button>
        </div>
      </Modal>
    </div>
  );
}
