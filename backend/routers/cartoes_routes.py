"""Rotas de Meus Cartões de Crédito: paleta livre, compras à vista/Nx, projeção e baixa de fatura."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, notify_db_changed
from models import CaixaLancamento, Cartao, CartaoCompra, CartaoFaturaPagamento, Usuario
from schemas import CartaoCreateRequest, CartaoUpdateRequest, CompraCreateRequest, PagarMensalRequest
from services.dates import (
    brl_to_centavos,
    centavos_to_brl,
    current_competencia_brt,
    first_billing_competencia,
    parse_competencia,
    today_brt,
    today_brt_iso,
)
from services.radar import build_cartao_month_view

router = APIRouter(prefix="/cartoes", tags=["Meus Cartões"])


@router.get("")
def list_cartoes(
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
    cartoes = list(
        db.scalars(
            select(Cartao)
            .where(Cartao.usuario_id == current_user.id, Cartao.ativo.is_(True))
            .order_by(Cartao.nome.asc())
        ).all()
    )
    compras_all = list(
        db.scalars(select(CartaoCompra).where(CartaoCompra.usuario_id == current_user.id)).all()
    )
    pags_all = list(
        db.scalars(
            select(CartaoFaturaPagamento).where(CartaoFaturaPagamento.usuario_id == current_user.id)
        ).all()
    )

    compras_map: dict[int, list[CartaoCompra]] = {}
    for c in compras_all:
        compras_map.setdefault(c.cartao_id, []).append(c)
    pags_map: dict[int, list[CartaoFaturaPagamento]] = {}
    for p in pags_all:
        pags_map.setdefault(p.cartao_id, []).append(p)

    views = [
        build_cartao_month_view(card, compras_map.get(card.id, []), pags_map.get(card.id, []), comp, today)
        for card in cartoes
    ]
    total_faturas_cent = sum(v["valor_efetivo_centavos"] for v in views)
    total_pagas_cent = sum(v["valor_efetivo_centavos"] for v in views if v["pago"])

    return {
        "competencia": comp,
        "itens": views,
        "resumo": {
            "total_faturas": centavos_to_brl(total_faturas_cent),
            "total_pago": centavos_to_brl(total_pagas_cent),
            "total_pendente": centavos_to_brl(max(0, total_faturas_cent - total_pagas_cent)),
            "quantidade_cartoes": len(views),
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_cartao(
    req: CartaoCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    card = Cartao(
        usuario_id=current_user.id,
        nome=req.nome.strip(),
        bandeira=req.bandeira.strip() or "Black",
        ultimos_digitos=req.ultimos_digitos,
        cor_hex=req.cor_hex,
        limite_centavos=brl_to_centavos(req.limite),
        dia_fechamento=req.dia_fechamento,
        dia_vencimento=req.dia_vencimento,
        ativo=True,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    notify_db_changed("cartao_create")

    return build_cartao_month_view(card, [], [], current_competencia_brt(), today_brt())


@router.put("/{cartao_id}")
def update_cartao(
    cartao_id: int,
    req: CartaoUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    card = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, Cartao.usuario_id == current_user.id)
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Cartão não encontrado.")

    if req.nome is not None:
        card.nome = req.nome.strip()
    if req.bandeira is not None:
        card.bandeira = req.bandeira.strip() or "Black"
    if req.ultimos_digitos is not None:
        card.ultimos_digitos = req.ultimos_digitos
    if req.cor_hex is not None:
        card.cor_hex = req.cor_hex
    if req.limite is not None:
        card.limite_centavos = brl_to_centavos(req.limite)
    if req.dia_fechamento is not None:
        card.dia_fechamento = req.dia_fechamento
    if req.dia_vencimento is not None:
        card.dia_vencimento = req.dia_vencimento
    if req.ativo is not None:
        card.ativo = req.ativo

    db.commit()
    db.refresh(card)
    notify_db_changed("cartao_update")
    return build_cartao_month_view(card, card.compras, card.pagamentos, current_competencia_brt(), today_brt())


@router.delete("/{cartao_id}")
def delete_cartao(
    cartao_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    card = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, Cartao.usuario_id == current_user.id)
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Cartão não encontrado.")

    caixa_ids = [p.caixa_lancamento_id for p in card.pagamentos if p.caixa_lancamento_id is not None]
    for cid in caixa_ids:
        cx = db.scalar(
            select(CaixaLancamento).where(
                CaixaLancamento.id == cid, CaixaLancamento.usuario_id == current_user.id
            )
        )
        if cx is not None:
            db.delete(cx)

    db.delete(card)
    db.commit()
    notify_db_changed("cartao_delete")
    return {"ok": True, "id": cartao_id, "caixa_estornados": len(caixa_ids)}


@router.post("/{cartao_id}/compras", status_code=status.HTTP_201_CREATED)
def create_cartao_compra(
    cartao_id: int,
    req: CompraCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    card = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, Cartao.usuario_id == current_user.id)
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Cartão não encontrado.")

    dt_compra = req.data_compra or today_brt_iso()
    comp_ini = req.competencia_inicial or first_billing_competencia(
        dt_compra, card.dia_fechamento, card.dia_vencimento
    )
    valor_total_cent = (
        brl_to_centavos(req.valor) * req.parcelas_total
        if req.modo_valor == "parcela"
        else brl_to_centavos(req.valor)
    )

    compra = CartaoCompra(
        usuario_id=current_user.id,
        cartao_id=card.id,
        descricao=req.descricao.strip(),
        categoria=req.categoria.strip(),
        data_compra=dt_compra,
        valor_total_centavos=valor_total_cent,
        parcelas_total=req.parcelas_total,
        competencia_inicial=comp_ini,
        observacao=req.observacao.strip(),
    )
    db.add(compra)
    db.commit()
    db.refresh(compra)
    notify_db_changed("cartao_compra_create")

    return {
        "id": compra.id,
        "cartao_id": card.id,
        "descricao": compra.descricao,
        "categoria": compra.categoria,
        "data_compra": compra.data_compra,
        "valor_total": centavos_to_brl(compra.valor_total_centavos),
        "parcelas_total": compra.parcelas_total,
        "competencia_inicial": compra.competencia_inicial,
    }


@router.delete("/{cartao_id}/compras/{compra_id}")
def delete_cartao_compra(
    cartao_id: int,
    compra_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    compra = db.scalar(
        select(CartaoCompra).where(
            CartaoCompra.id == compra_id,
            CartaoCompra.cartao_id == cartao_id,
            CartaoCompra.usuario_id == current_user.id,
        )
    )
    if compra is None:
        raise HTTPException(status_code=404, detail="Compra não encontrada neste cartão.")

    db.delete(compra)
    db.commit()
    notify_db_changed("cartao_compra_delete")
    return {"ok": True, "id": compra_id}


@router.post("/{cartao_id}/pagar")
def pagar_fatura_cartao(
    cartao_id: int,
    req: PagarMensalRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    card = db.scalar(
        select(Cartao).where(Cartao.id == cartao_id, Cartao.usuario_id == current_user.id)
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Cartão não encontrado.")

    existing = db.scalar(
        select(CartaoFaturaPagamento).where(
            CartaoFaturaPagamento.cartao_id == card.id,
            CartaoFaturaPagamento.competencia == req.competencia,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A fatura deste mês já foi paga.")

    view = build_cartao_month_view(card, card.compras, card.pagamentos, req.competencia, today_brt())
    val_cent = (
        brl_to_centavos(req.valor_pago)
        if req.valor_pago is not None
        else view["total_fatura_centavos"]
    )
    if val_cent <= 0:
        raise HTTPException(status_code=400, detail="Esta fatura não possui valor a pagar neste mês.")

    dt_pag = req.data_pagamento or today_brt_iso()
    caixa_row: CaixaLancamento | None = None
    if req.lancar_no_caixa:
        caixa_row = CaixaLancamento(
            usuario_id=current_user.id,
            tipo="saida",
            descricao=f"Fatura Cartão {card.nome} ({req.competencia})",
            categoria="Cartão",
            valor_centavos=val_cent,
            data=dt_pag,
            forma_pagamento=req.forma_pagamento.strip() or "PIX",
            observacao="Pagamento de fatura de cartão",
            origem_tipo="cartao",
            origem_ref_id=card.id,
        )
        db.add(caixa_row)
        db.flush()

    pag = CartaoFaturaPagamento(
        usuario_id=current_user.id,
        cartao_id=card.id,
        competencia=req.competencia,
        valor_pago_centavos=val_cent,
        data_pagamento=dt_pag,
        caixa_lancamento_id=caixa_row.id if caixa_row else None,
    )
    db.add(pag)
    db.commit()
    db.refresh(pag)
    notify_db_changed("cartao_fatura_pagar")
    return {
        "ok": True,
        "pagamento_id": pag.id,
        "caixa_lancamento_id": pag.caixa_lancamento_id,
        "valor_pago": centavos_to_brl(val_cent),
    }


@router.delete("/{cartao_id}/pagamentos/{competencia}")
def estornar_fatura_cartao(
    cartao_id: int,
    competencia: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    try:
        parse_competencia(competencia)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pag = db.scalar(
        select(CartaoFaturaPagamento).where(
            CartaoFaturaPagamento.cartao_id == cartao_id,
            CartaoFaturaPagamento.usuario_id == current_user.id,
            CartaoFaturaPagamento.competencia == competencia,
        )
    )
    if pag is None:
        raise HTTPException(status_code=404, detail="Pagamento de fatura não encontrado.")

    estornou_caixa = False
    if pag.caixa_lancamento_id is not None:
        cx = db.scalar(
            select(CaixaLancamento).where(
                CaixaLancamento.id == pag.caixa_lancamento_id,
                CaixaLancamento.usuario_id == current_user.id,
            )
        )
        if cx is not None:
            db.delete(cx)
            estornou_caixa = True

    db.delete(pag)
    db.commit()
    notify_db_changed("cartao_fatura_estornar")
    return {"ok": True, "estornou_caixa": estornou_caixa}
