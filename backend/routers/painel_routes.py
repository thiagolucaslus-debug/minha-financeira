"""Rotas do Painel Executivo (Início): KPIs mensais, Radar Unificado de Vencimentos e Gráficos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import CaixaLancamento, Usuario
from services.dates import (
    add_months,
    centavos_to_brl,
    competencia_label,
    current_competencia_brt,
    parse_competencia,
    today_brt,
)
from services.radar import build_unified_radar

router = APIRouter(prefix="/painel", tags=["Painel Executivo"])

CHART_COLORS = (
    "#C9A45C",
    "#10B981",
    "#3B82F6",
    "#A855F7",
    "#F59E0B",
    "#EC4899",
    "#14B8A6",
    "#EF4444",
)


@router.get("/resumo")
def painel_resumo(
    competencia: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    comp = competencia or current_competencia_brt()
    try:
        parse_competencia(comp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    today = today_brt()
    radar = build_unified_radar(db, current_user.id, comp, ref_today=today)

    # Fluxo de Caixa do mês selecionado
    caixa_mes = list(
        db.scalars(
            select(CaixaLancamento)
            .where(
                CaixaLancamento.usuario_id == current_user.id,
                CaixaLancamento.data.like(f"{comp}-%"),
            )
            .order_by(desc(CaixaLancamento.data), desc(CaixaLancamento.id))
        ).all()
    )
    entrou_cent = sum(r.valor_centavos for r in caixa_mes if r.tipo == "entrada")
    saiu_cent = sum(r.valor_centavos for r in caixa_mes if r.tipo == "saida")
    sobrou_cent = entrou_cent - saiu_cent
    a_vencer_cent = int(round(radar["resumo"]["a_vencer"] * 100))

    # Série de 6 meses (5 anteriores + mês selecionado) para gráfico Entradas x Saídas
    months_6 = [add_months(comp, delta) for delta in range(-5, 1)]
    min_prefix = f"{months_6[0]}-01"
    max_prefix = f"{months_6[-1]}-31"
    caixa_6m = list(
        db.scalars(
            select(CaixaLancamento).where(
                CaixaLancamento.usuario_id == current_user.id,
                CaixaLancamento.data >= min_prefix,
                CaixaLancamento.data <= max_prefix,
            )
        ).all()
    )
    agg_6m = {m: {"entrou": 0, "saiu": 0} for m in months_6}
    for row in caixa_6m:
        m_key = row.data[:7]
        if m_key in agg_6m:
            if row.tipo == "entrada":
                agg_6m[m_key]["entrou"] += row.valor_centavos
            else:
                agg_6m[m_key]["saiu"] += row.valor_centavos

    fluxo_mensal = [
        {
            "competencia": m,
            "label": competencia_label(m),
            "entrou": centavos_to_brl(agg_6m[m]["entrou"]),
            "saiu": centavos_to_brl(agg_6m[m]["saiu"]),
            "sobrou": centavos_to_brl(agg_6m[m]["entrou"] - agg_6m[m]["saiu"]),
        }
        for m in months_6
    ]

    # Distribuição de saídas (por categoria do Caixa + compromissos pendentes do mês selecionado)
    dist_map: dict[str, int] = {}
    dist_colors: dict[str, str] = {}
    for row in caixa_mes:
        if row.tipo == "saida":
            cat = row.categoria or "Outros"
            dist_map[cat] = dist_map.get(cat, 0) + row.valor_centavos
    for it in radar["itens"]:
        if it.get("fora_competencia"):
            continue
        if not it["pago"] and it["valor_centavos"] > 0:
            label = it["titulo"]
            dist_map[label] = dist_map.get(label, 0) + it["valor_centavos"]
            if it.get("cor_hex"):
                dist_colors[label] = it["cor_hex"]

    sorted_dist = sorted(dist_map.items(), key=lambda kv: kv[1], reverse=True)[:8]
    distribuicao = [
        {
            "nome": nome,
            "valor": centavos_to_brl(val),
            "cor": dist_colors.get(nome) or CHART_COLORS[idx % len(CHART_COLORS)],
        }
        for idx, (nome, val) in enumerate(sorted_dist)
    ]

    ultimos_lancamentos = [
        {
            "id": r.id,
            "tipo": r.tipo,
            "descricao": r.descricao,
            "categoria": r.categoria,
            "valor": centavos_to_brl(r.valor_centavos),
            "data": r.data,
            "forma_pagamento": r.forma_pagamento,
            "origem_tipo": r.origem_tipo,
        }
        for r in caixa_mes[:6]
    ]

    return {
        "competencia": comp,
        "data_referencia": today.isoformat(),
        "kpis": {
            "entrou": centavos_to_brl(entrou_cent),
            "saiu": centavos_to_brl(saiu_cent),
            "sobrou": centavos_to_brl(sobrou_cent),
            "a_vencer": radar["resumo"]["a_vencer"],
            "total_compromissos": radar["resumo"]["total_compromissos"],
            "saldo_projetado": centavos_to_brl(sobrou_cent - a_vencer_cent),
        },
        "radar": radar,
        "graficos": {
            "fluxo_mensal": fluxo_mensal,
            "distribuicao": distribuicao,
            "compromissos_por_origem": radar["por_origem"],
        },
        "ultimos_lancamentos": ultimos_lancamentos,
    }
