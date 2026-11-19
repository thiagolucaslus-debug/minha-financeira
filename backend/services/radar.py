"""
Motor unificado de projeções mensais (Contas a Vencer, Cartões de Crédito,
Módulos de Dívida estilo Cartão Virtual) e Radar de Vencimentos.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    Cartao,
    CartaoCompra,
    CartaoFaturaPagamento,
    ContaPagamento,
    ContaVencer,
    ModuloCompra,
    ModuloDivida,
    ModuloFaturaPagamento,
)
from services.dates import (
    add_months,
    centavos_to_brl,
    closing_date_for_competencia,
    diff_months,
    due_date_for_competencia,
    installment_value_for_index,
    today_brt,
)


def classify_urgency(due_dt: date, ref_today: date, pago: bool) -> tuple[str, int]:
    dias_restantes = (due_dt - ref_today).days
    if pago:
        return "pago", dias_restantes
    if dias_restantes < 0:
        return "atrasado", dias_restantes
    if dias_restantes == 0:
        return "vence_hoje", dias_restantes
    if dias_restantes <= 7:
        return "proximos_7_dias", dias_restantes
    if dias_restantes <= 15:
        return "proximos_15_dias", dias_restantes
    return "futuro", dias_restantes


def conta_occurrence_for_month(
    conta: ContaVencer,
    competencia: str,
    pagamento: ContaPagamento | None,
    ref_today: date,
) -> dict[str, Any] | None:
    if not conta.ativo:
        return None
    offset = diff_months(competencia, conta.competencia_inicio)
    if offset < 0:
        return None

    parcela_atual: int | None = None
    if conta.tipo == "parcelada":
        total_p = int(conta.parcelas_total or 1)
        if offset >= total_p:
            return None
        parcela_atual = offset + 1
    else:
        if conta.competencia_fim and diff_months(competencia, conta.competencia_fim) > 0:
            return None

    due_dt = due_date_for_competencia(competencia, conta.dia_vencimento)
    pago = pagamento is not None
    urgencia, dias_restantes = classify_urgency(due_dt, ref_today, pago)
    valor_cent = pagamento.valor_pago_centavos if pagamento else conta.valor_centavos

    return {
        "id": conta.id,
        "nome": conta.nome,
        "categoria": conta.categoria,
        "tipo": conta.tipo,
        "valor": centavos_to_brl(conta.valor_centavos),
        "valor_centavos": conta.valor_centavos,
        "valor_efetivo": centavos_to_brl(valor_cent),
        "dia_vencimento": conta.dia_vencimento,
        "data_vencimento": due_dt.isoformat(),
        "dia_ajustado": due_dt.day != conta.dia_vencimento,
        "competencia": competencia,
        "competencia_inicio": conta.competencia_inicio,
        "parcela_atual": parcela_atual,
        "parcelas_total": conta.parcelas_total if conta.tipo == "parcelada" else None,
        "cor_hex": conta.cor_hex,
        "observacao": conta.observacao,
        "pago": pago,
        "pagamento_id": pagamento.id if pagamento else None,
        "data_pagamento": pagamento.data_pagamento if pagamento else None,
        "caixa_lancamento_id": pagamento.caixa_lancamento_id if pagamento else None,
        "status_urgencia": urgencia,
        "dias_restantes": dias_restantes,
    }


def _project_purchase_items(
    compras: list[CartaoCompra] | list[ModuloCompra],
    competencia: str,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    Retorna (itens_do_mes, total_mes_centavos, total_restante_futuro_centavos)
    para um conjunto de compras à vista ou parceladas.
    """
    itens: list[dict[str, Any]] = []
    total_mes = 0
    total_futuro = 0

    for c in compras:
        offset = diff_months(competencia, c.competencia_inicial)
        n = max(1, int(c.parcelas_total or 1))
        if 0 <= offset < n:
            val_cent = installment_value_for_index(c.valor_total_centavos, n, offset)
            total_mes += val_cent
            itens.append(
                {
                    "id": c.id,
                    "descricao": c.descricao,
                    "categoria": c.categoria,
                    "data_compra": c.data_compra,
                    "valor_total": centavos_to_brl(c.valor_total_centavos),
                    "valor_parcela": centavos_to_brl(val_cent),
                    "valor_parcela_centavos": val_cent,
                    "parcela_atual": offset + 1,
                    "parcelas_total": n,
                    "competencia_inicial": c.competencia_inicial,
                    "competencia_final": add_months(c.competencia_inicial, n - 1),
                    "observacao": c.observacao,
                }
            )
        # Parcelas ainda por vencer a partir do mês seguinte à competência consultada
        start_future = max(0, offset + 1)
        for k in range(start_future, n):
            total_futuro += installment_value_for_index(c.valor_total_centavos, n, k)

    itens.sort(key=lambda x: (x["data_compra"], x["id"]), reverse=True)
    return itens, total_mes, total_futuro


def _compute_unpaid_commitment_centavos(
    compras: list[CartaoCompra] | list[ModuloCompra],
    paid_competencias: set[str],
) -> int:
    """Calcula comprometimento real de limite: soma de todas as parcelas em meses ainda não pagos."""
    total = 0
    for c in compras:
        n = max(1, int(c.parcelas_total or 1))
        for k in range(n):
            comp_k = add_months(c.competencia_inicial, k)
            if comp_k not in paid_competencias:
                total += installment_value_for_index(c.valor_total_centavos, n, k)
    return total


def build_cartao_month_view(
    cartao: Cartao,
    compras: list[CartaoCompra],
    pagamentos: list[CartaoFaturaPagamento],
    competencia: str,
    ref_today: date,
) -> dict[str, Any]:
    pag_by_comp = {p.competencia: p for p in pagamentos}
    pagamento = pag_by_comp.get(competencia)
    itens, total_mes_cent, total_futuro_cent = _project_purchase_items(compras, competencia)
    limite_usado_cent = _compute_unpaid_commitment_centavos(compras, set(pag_by_comp.keys()))
    limite_disponivel_cent = max(0, cartao.limite_centavos - limite_usado_cent) if cartao.limite_centavos > 0 else 0

    due_dt = due_date_for_competencia(competencia, cartao.dia_vencimento)
    close_dt = closing_date_for_competencia(competencia, cartao.dia_fechamento, cartao.dia_vencimento)
    pago = pagamento is not None
    urgencia, dias_restantes = classify_urgency(due_dt, ref_today, pago)

    return {
        "id": cartao.id,
        "nome": cartao.nome,
        "bandeira": cartao.bandeira,
        "ultimos_digitos": cartao.ultimos_digitos,
        "cor_hex": cartao.cor_hex,
        "limite": centavos_to_brl(cartao.limite_centavos),
        "limite_usado": centavos_to_brl(limite_usado_cent),
        "limite_disponivel": centavos_to_brl(limite_disponivel_cent),
        "uso_percentual": (
            round(min(100.0, (limite_usado_cent / cartao.limite_centavos) * 100.0), 1)
            if cartao.limite_centavos > 0
            else 0.0
        ),
        "dia_fechamento": cartao.dia_fechamento,
        "dia_vencimento": cartao.dia_vencimento,
        "data_fechamento": close_dt.isoformat(),
        "data_vencimento": due_dt.isoformat(),
        "competencia": competencia,
        "total_fatura": centavos_to_brl(total_mes_cent),
        "total_fatura_centavos": total_mes_cent,
        "total_futuro": centavos_to_brl(total_futuro_cent),
        "itens_count": len(itens),
        "itens": itens,
        "total_compras_cadastradas": len(compras),
        "pago": pago,
        "pagamento_id": pagamento.id if pagamento else None,
        "valor_pago": centavos_to_brl(pagamento.valor_pago_centavos) if pagamento else None,
        "data_pagamento": pagamento.data_pagamento if pagamento else None,
        "caixa_lancamento_id": pagamento.caixa_lancamento_id if pagamento else None,
        "status_urgencia": urgencia if total_mes_cent > 0 or pago else "sem_fatura",
        "dias_restantes": dias_restantes,
    }


def build_modulo_month_view(
    modulo: ModuloDivida,
    compras: list[ModuloCompra],
    pagamentos: list[ModuloFaturaPagamento],
    competencia: str,
    ref_today: date,
) -> dict[str, Any]:
    pag_by_comp = {p.competencia: p for p in pagamentos}
    pagamento = pag_by_comp.get(competencia)
    itens, total_mes_cent, total_futuro_cent = _project_purchase_items(compras, competencia)
    total_aberto_cent = _compute_unpaid_commitment_centavos(compras, set(pag_by_comp.keys()))

    due_dt = due_date_for_competencia(competencia, modulo.dia_vencimento)
    close_dt = closing_date_for_competencia(competencia, modulo.dia_fechamento, modulo.dia_vencimento)
    pago = pagamento is not None
    urgencia, dias_restantes = classify_urgency(due_dt, ref_today, pago)

    return {
        "id": modulo.id,
        "nome": modulo.nome,
        "descricao": modulo.descricao,
        "cor_hex": modulo.cor_hex,
        "limite": centavos_to_brl(modulo.limite_centavos),
        "total_aberto": centavos_to_brl(total_aberto_cent),
        "uso_percentual": (
            round(min(100.0, (total_aberto_cent / modulo.limite_centavos) * 100.0), 1)
            if modulo.limite_centavos > 0
            else 0.0
        ),
        "dia_fechamento": modulo.dia_fechamento,
        "dia_vencimento": modulo.dia_vencimento,
        "data_fechamento": close_dt.isoformat(),
        "data_vencimento": due_dt.isoformat(),
        "competencia": competencia,
        "total_mes": centavos_to_brl(total_mes_cent),
        "total_mes_centavos": total_mes_cent,
        "total_futuro": centavos_to_brl(total_futuro_cent),
        "itens_count": len(itens),
        "itens": itens,
        "total_compras_cadastradas": len(compras),
        "pago": pago,
        "pagamento_id": pagamento.id if pagamento else None,
        "valor_pago": centavos_to_brl(pagamento.valor_pago_centavos) if pagamento else None,
        "data_pagamento": pagamento.data_pagamento if pagamento else None,
        "caixa_lancamento_id": pagamento.caixa_lancamento_id if pagamento else None,
        "status_urgencia": urgencia if total_mes_cent > 0 or pago else "sem_fatura",
        "dias_restantes": dias_restantes,
    }


def build_unified_radar(
    db: Session,
    usuario_id: int,
    competencia: str,
    ref_today: date | None = None,
) -> dict[str, Any]:
    """
    Constrói o Radar Unificado de Vencimentos juntando:
    1. Contas a Vencer (Fixas & Parceladas)
    2. Meus Cartões de Crédito (com fatura > 0 no mês)
    3. Módulos de Dívida estilo Cartão Virtual (ex.: Thiago, Seu Luiz — com valor > 0 no mês)
    """
    today = ref_today or today_brt()
    items: list[dict[str, Any]] = []

    # 1. Contas a Vencer
    contas = list(
        db.scalars(
            select(ContaVencer).where(ContaVencer.usuario_id == usuario_id, ContaVencer.ativo.is_(True))
        ).all()
    )
    conta_pags = {
        p.conta_id: p
        for p in db.scalars(
            select(ContaPagamento).where(
                ContaPagamento.usuario_id == usuario_id,
                ContaPagamento.competencia == competencia,
            )
        ).all()
    }
    contas_total_cent = 0
    contas_pago_cent = 0
    for c in contas:
        occ = conta_occurrence_for_month(c, competencia, conta_pags.get(c.id), today)
        if not occ:
            continue
        val_c = occ["valor_centavos"]
        contas_total_cent += val_c
        if occ["pago"]:
            contas_pago_cent += val_c
        sub = f"Conta fixa · {occ['categoria']}"
        if occ["parcela_atual"] and occ["parcelas_total"]:
            sub = f"Parcela {occ['parcela_atual']}/{occ['parcelas_total']} · {occ['categoria']}"
        items.append(
            {
                "uid": f"conta:{c.id}:{competencia}",
                "origem_tipo": "conta",
                "origem_id": c.id,
                "titulo": c.nome,
                "subtitulo": sub,
                "cor_hex": c.cor_hex,
                "competencia": competencia,
                "data_vencimento": occ["data_vencimento"],
                "dias_restantes": occ["dias_restantes"],
                "valor": occ["valor_efetivo"],
                "valor_centavos": val_c,
                "pago": occ["pago"],
                "status_urgencia": occ["status_urgencia"],
                "itens_count": 1,
            }
        )

    # 2. Meus Cartões de Crédito
    cartoes = list(
        db.scalars(
            select(Cartao).where(Cartao.usuario_id == usuario_id, Cartao.ativo.is_(True))
        ).all()
    )
    cartao_compras_all = list(
        db.scalars(select(CartaoCompra).where(CartaoCompra.usuario_id == usuario_id)).all()
    )
    cartao_pags_all = list(
        db.scalars(
            select(CartaoFaturaPagamento).where(CartaoFaturaPagamento.usuario_id == usuario_id)
        ).all()
    )
    compras_by_cartao: dict[int, list[CartaoCompra]] = {}
    for cc in cartao_compras_all:
        compras_by_cartao.setdefault(cc.cartao_id, []).append(cc)
    pags_by_cartao: dict[int, list[CartaoFaturaPagamento]] = {}
    for cp in cartao_pags_all:
        pags_by_cartao.setdefault(cp.cartao_id, []).append(cp)

    cartoes_total_cent = 0
    cartoes_pago_cent = 0
    for card in cartoes:
        view = build_cartao_month_view(
            card,
            compras_by_cartao.get(card.id, []),
            pags_by_cartao.get(card.id, []),
            competencia,
            today,
        )
        if view["total_fatura_centavos"] <= 0 and not view["pago"]:
            continue
        val_c = view["total_fatura_centavos"]
        cartoes_total_cent += val_c
        if view["pago"]:
            cartoes_pago_cent += val_c
        items.append(
            {
                "uid": f"cartao:{card.id}:{competencia}",
                "origem_tipo": "cartao",
                "origem_id": card.id,
                "titulo": f"Fatura {card.nome}",
                "subtitulo": f"Cartão · {view['itens_count']} compra(s) no mês",
                "cor_hex": card.cor_hex,
                "competencia": competencia,
                "data_vencimento": view["data_vencimento"],
                "dias_restantes": view["dias_restantes"],
                "valor": view["total_fatura"],
                "valor_centavos": val_c,
                "pago": view["pago"],
                "status_urgencia": view["status_urgencia"],
                "itens_count": view["itens_count"],
            }
        )

    # 3. Módulos de Dívida (Cartão Virtual — ex.: Thiago, Seu Luiz)
    modulos = list(
        db.scalars(
            select(ModuloDivida).where(
                ModuloDivida.usuario_id == usuario_id, ModuloDivida.ativo.is_(True)
            )
        ).all()
    )
    mod_compras_all = list(
        db.scalars(select(ModuloCompra).where(ModuloCompra.usuario_id == usuario_id)).all()
    )
    mod_pags_all = list(
        db.scalars(
            select(ModuloFaturaPagamento).where(ModuloFaturaPagamento.usuario_id == usuario_id)
        ).all()
    )
    compras_by_mod: dict[int, list[ModuloCompra]] = {}
    for mc in mod_compras_all:
        compras_by_mod.setdefault(mc.modulo_id, []).append(mc)
    pags_by_mod: dict[int, list[ModuloFaturaPagamento]] = {}
    for mp in mod_pags_all:
        pags_by_mod.setdefault(mp.modulo_id, []).append(mp)

    modulos_total_cent = 0
    modulos_pago_cent = 0
    for mod in modulos:
        view = build_modulo_month_view(
            mod,
            compras_by_mod.get(mod.id, []),
            pags_by_mod.get(mod.id, []),
            competencia,
            today,
        )
        if view["total_mes_centavos"] <= 0 and not view["pago"]:
            continue
        val_c = view["total_mes_centavos"]
        modulos_total_cent += val_c
        if view["pago"]:
            modulos_pago_cent += val_c
        items.append(
            {
                "uid": f"modulo_divida:{mod.id}:{competencia}",
                "origem_tipo": "modulo_divida",
                "origem_id": mod.id,
                "titulo": f"Módulo {mod.nome}",
                "subtitulo": f"Dívida · {view['itens_count']} lançamento(s) no mês",
                "cor_hex": mod.cor_hex,
                "competencia": competencia,
                "data_vencimento": view["data_vencimento"],
                "dias_restantes": view["dias_restantes"],
                "valor": view["total_mes"],
                "valor_centavos": val_c,
                "pago": view["pago"],
                "status_urgencia": view["status_urgencia"],
                "itens_count": view["itens_count"],
            }
        )

    # Ordenação por prioridade real: atrasado -> hoje -> 7d -> 15d -> futuro -> pago
    priority_rank = {
        "atrasado": 0,
        "vence_hoje": 1,
        "proximos_7_dias": 2,
        "proximos_15_dias": 3,
        "futuro": 4,
        "pago": 5,
        "sem_fatura": 6,
    }
    items.sort(key=lambda it: (priority_rank.get(it["status_urgencia"], 9), it["data_vencimento"], it["titulo"]))

    total_compromissos_cent = contas_total_cent + cartoes_total_cent + modulos_total_cent
    total_pago_cent = contas_pago_cent + cartoes_pago_cent + modulos_pago_cent
    a_vencer_cent = max(0, total_compromissos_cent - total_pago_cent)

    qtd_atrasados = sum(1 for x in items if x["status_urgencia"] == "atrasado")
    qtd_hoje = sum(1 for x in items if x["status_urgencia"] == "vence_hoje")
    qtd_7 = sum(1 for x in items if x["status_urgencia"] == "proximos_7_dias")
    qtd_15 = sum(1 for x in items if x["status_urgencia"] == "proximos_15_dias")

    return {
        "competencia": competencia,
        "data_referencia": today.isoformat(),
        "itens": items,
        "resumo": {
            "total_compromissos": centavos_to_brl(total_compromissos_cent),
            "total_pago": centavos_to_brl(total_pago_cent),
            "a_vencer": centavos_to_brl(a_vencer_cent),
            "qtd_atrasados": qtd_atrasados,
            "qtd_hoje": qtd_hoje,
            "qtd_7_dias": qtd_7,
            "qtd_15_dias": qtd_15,
            "alertas_urgentes": qtd_atrasados + qtd_hoje + qtd_7,
        },
        "por_origem": [
            {
                "nome": "Contas a Vencer",
                "valor": centavos_to_brl(contas_total_cent),
                "pago": centavos_to_brl(contas_pago_cent),
                "pendente": centavos_to_brl(max(0, contas_total_cent - contas_pago_cent)),
                "cor": "#C9A45C",
            },
            {
                "nome": "Cartões",
                "valor": centavos_to_brl(cartoes_total_cent),
                "pago": centavos_to_brl(cartoes_pago_cent),
                "pendente": centavos_to_brl(max(0, cartoes_total_cent - cartoes_pago_cent)),
                "cor": "#3B82F6",
            },
            {
                "nome": "Módulos de Dívida",
                "valor": centavos_to_brl(modulos_total_cent),
                "pago": centavos_to_brl(modulos_pago_cent),
                "pendente": centavos_to_brl(max(0, modulos_total_cent - modulos_pago_cent)),
                "cor": "#10B981",
            },
        ],
    }
