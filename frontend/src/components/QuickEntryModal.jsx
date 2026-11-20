import React, { useEffect, useState } from 'react';
import { ArrowDownCircle, ArrowUpCircle, Sparkles, Zap } from 'lucide-react';
import { api } from '../api/client';
import { QUICK_CATEGORIES, getTodayISO } from '../utils/format';
import { Modal } from './Modal';
import { useToast } from './Toast';

const FORMAS = ['PIX', 'Dinheiro', 'Débito', 'Transferência', 'Outro'];

export function QuickEntryModal({ open, onClose, initialType = 'saida', onSaved }) {
  const { notify } = useToast();
  const [tipo, setTipo] = useState(initialType);
  const [valor, setValor] = useState('');
  const [descricao, setDescricao] = useState('');
  const [categoria, setCategoria] = useState(
    initialType === 'entrada' ? 'Uber / App' : 'Mercado'
  );
  const [data, setData] = useState(getTodayISO());
  const [formaPagamento, setFormaPagamento] = useState('PIX');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setTipo(initialType);
      setCategoria(initialType === 'entrada' ? 'Uber / App' : 'Mercado');
      setValor('');
      setDescricao('');
      setData(getTodayISO());
      setFormaPagamento('PIX');
    }
  }, [open, initialType]);

  const handleSwitchType = (nextType) => {
    setTipo(nextType);
    setCategoria(nextType === 'entrada' ? 'Uber / App' : 'Mercado');
  };

  const applyPreset = (presetTipo, presetCat, presetDesc, presetValor) => {
    setTipo(presetTipo);
    setCategoria(presetCat);
    setDescricao(presetDesc);
    setValor(String(presetValor));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const numeric = Number(String(valor).replace(',', '.'));
    if (!Number.isFinite(numeric) || numeric <= 0) {
      notify('Informe um valor válido maior que zero.', 'error');
      return;
    }
    setSaving(true);
    try {
      await api.createCaixa({
        tipo,
        valor: numeric,
        descricao: descricao.trim() || categoria,
        categoria,
        data,
        forma_pagamento: formaPagamento,
      });
      notify(
        tipo === 'entrada'
          ? `Entrada de R$ ${numeric.toFixed(2).replace('.', ',')} registrada!`
          : `Saída de R$ ${numeric.toFixed(2).replace('.', ',')} registrada!`
      );
      onSaved?.();
      onClose?.();
    } catch (err) {
      notify(err.message || 'Não foi possível salvar o lançamento.', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Lançamento Relâmpago"
      subtitle="Registre entradas e saídas do dia a dia em segundos"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Seletor Entrada / Saída */}
        <div className="grid grid-cols-2 gap-2.5 p-1 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
          <button
            type="button"
            onClick={() => handleSwitchType('entrada')}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition ${
              tipo === 'entrada'
                ? 'bg-emerald-500 text-obsidian-950 shadow-lg'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <ArrowUpCircle className="w-4 h-4" />
            Entrada (+)
          </button>
          <button
            type="button"
            onClick={() => handleSwitchType('saida')}
            className={`flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition ${
              tipo === 'saida'
                ? 'bg-rose-500 text-white shadow-lg'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            <ArrowDownCircle className="w-4 h-4" />
            Saída (-)
          </button>
        </div>

        {/* Atalhos 1 toque */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] inline-flex items-center gap-1 flex-shrink-0">
            <Zap className="w-3 h-3 text-gold-700 dark:text-gold-400" /> Rápido:
          </span>
          <button
            type="button"
            onClick={() => applyPreset('entrada', 'Uber / App', 'Corridas Uber', 100)}
            className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/35 hover:bg-emerald-500/25 flex-shrink-0"
          >
            +R$ 100 Uber
          </button>
          <button
            type="button"
            onClick={() => applyPreset('saida', 'Mercado', 'Gasto Mercado', 20)}
            className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-700 dark:text-rose-400 border border-rose-500/35 hover:bg-rose-500/25 flex-shrink-0"
          >
            -R$ 20 Mercado
          </button>
          <button
            type="button"
            onClick={() => applyPreset('saida', 'Combustível', 'Abastecimento', 50)}
            className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-800 dark:text-amber-400 border border-amber-500/35 hover:bg-amber-500/25 flex-shrink-0"
          >
            -R$ 50 Combustível
          </button>
        </div>

        {/* Valor em destaque */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
            Valor (R$)
          </label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-lg font-bold text-gold-500">
              R$
            </span>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              autoFocus
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              placeholder="0,00"
              className="w-full input-private rounded-2xl pl-12 pr-4 py-3.5 text-2xl font-extrabold tabular-nums"
            />
          </div>
        </div>

        {/* Categorias inteligentes */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-2">
            Categoria
          </label>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_CATEGORIES[tipo].map((cat) => {
              const active = categoria === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategoria(cat)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold border transition ${
                    active
                      ? tipo === 'entrada'
                        ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-700 dark:text-emerald-400'
                        : 'bg-gold-500/20 border-gold-500/50 text-gold-700 dark:text-gold-400'
                      : 'bg-[var(--bg-elevated)] border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-gold-500/30'
                  }`}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </div>

        {/* Descrição */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
            Descrição
          </label>
          <input
            type="text"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            placeholder={
              tipo === 'entrada'
                ? 'Ex.: Uber turno manhã, freela, PIX cliente...'
                : 'Ex.: Mercado do bairro, gasolina, almoço...'
            }
            className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
          />
        </div>

        {/* Data + Forma */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
              Data
            </label>
            <input
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
              Meio
            </label>
            <select
              value={formaPagamento}
              onChange={(e) => setFormaPagamento(e.target.value)}
              className="w-full input-private rounded-xl px-3.5 py-2.5 text-sm"
            >
              {FORMAS.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="w-full btn-gold rounded-2xl py-3.5 text-sm tracking-wide flex items-center justify-center gap-2 disabled:opacity-60"
        >
          <Sparkles className="w-4 h-4" />
          {saving ? 'Salvando...' : tipo === 'entrada' ? 'Confirmar Entrada' : 'Confirmar Saída'}
        </button>
      </form>
    </Modal>
  );
}
