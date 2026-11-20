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
    format_competencia,
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
        "valor_efetivo_centavos": valor_cent,
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
    valor_efetivo_cent = pagamento.valor_pago_centavos if pagamento else total_mes_cent

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
        "valor_efetivo": centavos_to_brl(valor_efetivo_cent),
        "valor_efetivo_centavos": valor_efetivo_cent,
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
    valor_efetivo_cent = pagamento.valor_pago_centavos if pagamento else total_mes_cent

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
        "valor_efetivo": centavos_to_brl(valor_efetivo_cent),
        "valor_efetivo_centavos": valor_efetivo_cent,
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


def _build_radar_entries_for_month(
    *,
    contas: list[ContaVencer],
    conta_pags_by_key: dict[tuple[int, str], ContaPagamento],
    cartoes: list[Cartao],
    compras_by_cartao: dict[int, list[CartaoCompra]],
    pags_by_cartao: dict[int, list[CartaoFaturaPagamento]],
    modulos: list[ModuloDivida],
    compras_by_mod: dict[int, list[ModuloCompra]],
    pags_by_mod: dict[int, list[ModuloFaturaPagamento]],
    target_comp: str,
    today: date,
    fora_competencia: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    entries: list[dict[str, Any]] = []
    totals = {
        "contas_total": 0,
        "contas_pago": 0,
        "cartoes_total": 0,
        "cartoes_pago": 0,
        "modulos_total": 0,
        "modulos_pago": 0,
    }

    for c in contas:
        occ = conta_occurrence_for_month(c, target_comp, conta_pags_by_key.get((c.id, target_comp)), today)
        if not occ:
            continue
        val_c = occ["valor_efetivo_centavos"]
        totals["contas_total"] += val_c
        if occ["pago"]:
            totals["contas_pago"] += val_c
        sub = f"Conta fixa · {occ['categoria']}"
        if occ["parcela_atual"] and occ["parcelas_total"]:
            sub = f"Parcela {occ['parcela_atual']}/{occ['parcelas_total']} · {occ['categoria']}"
        entries.append(
            {
                "uid": f"conta:{c.id}:{target_comp}",
                "origem_tipo": "conta",
                "origem_id": c.id,
                "titulo": c.nome,
                "subtitulo": sub,
                "cor_hex": c.cor_hex,
                "competencia": target_comp,
                "fora_competencia": fora_competencia,
                "data_vencimento": occ["data_vencimento"],
                "dias_restantes": occ["dias_restantes"],
                "valor": occ["valor_efetivo"],
                "valor_centavos": val_c,
                "pago": occ["pago"],
                "status_urgencia": occ["status_urgencia"],
                "itens_count": 1,
            }
        )

    for card in cartoes:
        view = build_cartao_month_view(
            card,
            compras_by_cartao.get(card.id, []),
            pags_by_cartao.get(card.id, []),
            target_comp,
            today,
        )
        if view["valor_efetivo_centavos"] <= 0 and not view["pago"]:
            continue
        val_c = view["valor_efetivo_centavos"]
        totals["cartoes_total"] += val_c
        if view["pago"]:
            totals["cartoes_pago"] += val_c
        entries.append(
            {
                "uid": f"cartao:{card.id}:{target_comp}",
                "origem_tipo": "cartao",
                "origem_id": card.id,
                "titulo": f"Fatura {card.nome}",
                "subtitulo": f"Cartão · {view['itens_count']} compra(s) no mês",
                "cor_hex": card.cor_hex,
                "competencia": target_comp,
                "fora_competencia": fora_competencia,
                "data_vencimento": view["data_vencimento"],
                "dias_restantes": view["dias_restantes"],
                "valor": view["valor_efetivo"],
                "valor_centavos": val_c,
                "pago": view["pago"],
                "status_urgencia": view["status_urgencia"],
                "itens_count": view["itens_count"],
            }
        )

    for mod in modulos:
        view = build_modulo_month_view(
            mod,
            compras_by_mod.get(mod.id, []),
            pags_by_mod.get(mod.id, []),
            target_comp,
            today,
        )
        if view["valor_efetivo_centavos"] <= 0 and not view["pago"]:
            continue
        val_c = view["valor_efetivo_centavos"]
        totals["modulos_total"] += val_c
        if view["pago"]:
            totals["modulos_pago"] += val_c
        entries.append(
            {
                "uid": f"modulo_divida:{mod.id}:{target_comp}",
                "origem_tipo": "modulo_divida",
                "origem_id": mod.id,
                "titulo": f"Módulo {mod.nome}",
                "subtitulo": f"Dívida · {view['itens_count']} lançamento(s) no mês",
                "cor_hex": mod.cor_hex,
                "competencia": target_comp,
                "fora_competencia": fora_competencia,
                "data_vencimento": view["data_vencimento"],
                "dias_restantes": view["dias_restantes"],
                "valor": view["valor_efetivo"],
                "valor_centavos": val_c,
                "pago": view["pago"],
                "status_urgencia": view["status_urgencia"],
                "itens_count": view["itens_count"],
            }
        )

    return entries, totals


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

    Quando `competencia` é o mês corrente, também alerta automaticamente:
    - compromissos não pagos atrasados de meses anteriores (até 6 meses atrás);
    - compromissos não pagos do mês seguinte que já estão dentro da janela de 15 dias.
    """
    today = ref_today or today_brt()
    current_comp = format_competencia(today.year, today.month)

    contas = list(
        db.scalars(
            select(ContaVencer).where(ContaVencer.usuario_id == usuario_id, ContaVencer.ativo.is_(True))
        ).all()
    )
    conta_pags_all = list(
        db.scalars(select(ContaPagamento).where(ContaPagamento.usuario_id == usuario_id)).all()
    )
    conta_pags_by_key = {(p.conta_id, p.competencia): p for p in conta_pags_all}

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

    # 1. Compromissos da competência selecionada (alimentam os KPIs do mês)
    items, totals = _build_radar_entries_for_month(
        contas=contas,
        conta_pags_by_key=conta_pags_by_key,
        cartoes=cartoes,
        compras_by_cartao=compras_by_cartao,
        pags_by_cartao=pags_by_cartao,
        modulos=modulos,
        compras_by_mod=compras_by_mod,
        pags_by_mod=pags_by_mod,
        target_comp=competencia,
        today=today,
        fora_competencia=None,
    )

    atrasados_anteriores_cent = 0
    proximos_mes_seguinte_cent = 0

    # 2. Alertas cross-month automáticos quando o usuário está olhando o mês atual
    if competencia == current_comp:
        for delta in range(-6, 0):
            prev_comp = add_months(competencia, delta)
            prev_entries, _ = _build_radar_entries_for_month(
                contas=contas,
                conta_pags_by_key=conta_pags_by_key,
                cartoes=cartoes,
                compras_by_cartao=compras_by_cartao,
                pags_by_cartao=pags_by_cartao,
                modulos=modulos,
                compras_by_mod=compras_by_mod,
                pags_by_mod=pags_by_mod,
                target_comp=prev_comp,
                today=today,
                fora_competencia="anterior",
            )
            for it in prev_entries:
                if not it["pago"] and it["valor_centavos"] > 0 and it["status_urgencia"] == "atrasado":
                    items.append(it)
                    atrasados_anteriores_cent += it["valor_centavos"]

        next_comp = add_months(competencia, 1)
        next_entries, _ = _build_radar_entries_for_month(
            contas=contas,
            conta_pags_by_key=conta_pags_by_key,
            cartoes=cartoes,
            compras_by_cartao=compras_by_cartao,
            pags_by_cartao=pags_by_cartao,
            modulos=modulos,
            compras_by_mod=compras_by_mod,
            pags_by_mod=pags_by_mod,
            target_comp=next_comp,
            today=today,
            fora_competencia="proximo",
        )
        for it in next_entries:
            if (
                not it["pago"]
                and it["valor_centavos"] > 0
                and 0 <= it["dias_restantes"] <= 15
            ):
                items.append(it)
                proximos_mes_seguinte_cent += it["valor_centavos"]

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

    contas_total_cent = totals["contas_total"]
    contas_pago_cent = totals["contas_pago"]
    cartoes_total_cent = totals["cartoes_total"]
    cartoes_pago_cent = totals["cartoes_pago"]
    modulos_total_cent = totals["modulos_total"]
    modulos_pago_cent = totals["modulos_pago"]

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
            "atrasados_anteriores_total": centavos_to_brl(atrasados_anteriores_cent),
            "proximos_mes_seguinte_total": centavos_to_brl(proximos_mes_seguinte_cent),
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
