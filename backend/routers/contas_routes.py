"""Rotas de Contas a Vencer (Fixas & Parceladas) com baixa 1-toque e estorno limpo."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, notify_db_changed
from models import CaixaLancamento, ContaPagamento, ContaVencer, Usuario
from schemas import ContaCreateRequest, ContaUpdateRequest, PagarMensalRequest
from services.dates import (
    brl_to_centavos,
    centavos_to_brl,
    current_competencia_brt,
    parse_competencia,
    today_brt,
    today_brt_iso,
)
from services.radar import conta_occurrence_for_month

router = APIRouter(prefix="/contas", tags=["Contas a Vencer"])


@router.get("")
def list_contas(
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
    contas = list(
        db.scalars(
            select(ContaVencer)
            .where(ContaVencer.usuario_id == current_user.id, ContaVencer.ativo.is_(True))
            .order_by(ContaVencer.dia_vencimento.asc(), ContaVencer.nome.asc())
        ).all()
    )
    pags = {
        p.conta_id: p
        for p in db.scalars(
            select(ContaPagamento).where(
                ContaPagamento.usuario_id == current_user.id,
                ContaPagamento.competencia == comp,
            )
        ).all()
    }

    ocorrencias = []
    for c in contas:
        occ = conta_occurrence_for_month(c, comp, pags.get(c.id), today)
        if occ is not None:
            ocorrencias.append(occ)

    ocorrencias.sort(key=lambda x: (x["pago"], x["data_vencimento"], x["nome"]))
    total_cent = sum(o["valor_centavos"] for o in ocorrencias)
    pago_cent = sum(o["valor_centavos"] for o in ocorrencias if o["pago"])

    return {
        "competencia": comp,
        "itens": ocorrencias,
        "resumo": {
            "total": centavos_to_brl(total_cent),
            "pago": centavos_to_brl(pago_cent),
            "pendente": centavos_to_brl(max(0, total_cent - pago_cent)),
            "quantidade": len(ocorrencias),
            "pagas": sum(1 for o in ocorrencias if o["pago"]),
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conta(
    req: ContaCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if req.tipo == "parcelada" and not req.parcelas_total:
        raise HTTPException(
            status_code=422, detail="Informe a quantidade de parcelas para uma conta parcelada."
        )

    comp_ini = req.competencia_inicio or current_competencia_brt()
    conta = ContaVencer(
        usuario_id=current_user.id,
        nome=req.nome.strip(),
        categoria=req.categoria.strip(),
        tipo=req.tipo,
        valor_centavos=brl_to_centavos(req.valor),
        dia_vencimento=req.dia_vencimento,
        competencia_inicio=comp_ini,
        parcelas_total=req.parcelas_total if req.tipo == "parcelada" else None,
        cor_hex=req.cor_hex,
        observacao=req.observacao.strip(),
        ativo=True,
    )
    db.add(conta)
    db.commit()
    db.refresh(conta)
    notify_db_changed("conta_create")

    return conta_occurrence_for_month(conta, comp_ini, None, today_brt())


@router.put("/{conta_id}")
def update_conta(
    conta_id: int,
    req: ContaUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conta = db.scalar(
        select(ContaVencer).where(ContaVencer.id == conta_id, ContaVencer.usuario_id == current_user.id)
    )
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    if req.nome is not None:
        conta.nome = req.nome.strip()
    if req.categoria is not None:
        conta.categoria = req.categoria.strip()
    if req.tipo is not None:
        conta.tipo = req.tipo
    if req.valor is not None:
        conta.valor_centavos = brl_to_centavos(req.valor)
    if req.dia_vencimento is not None:
        conta.dia_vencimento = req.dia_vencimento
    if req.competencia_inicio is not None:
        conta.competencia_inicio = req.competencia_inicio
    if req.parcelas_total is not None:
        conta.parcelas_total = req.parcelas_total
    if conta.tipo == "fixa":
        conta.parcelas_total = None
    elif conta.tipo == "parcelada" and not conta.parcelas_total:
        raise HTTPException(status_code=422, detail="Conta parcelada precisa de parcelas_total >= 1.")
    if req.cor_hex is not None:
        conta.cor_hex = req.cor_hex
    if req.observacao is not None:
        conta.observacao = req.observacao.strip()
    if req.ativo is not None:
        conta.ativo = req.ativo

    db.commit()
    db.refresh(conta)
    notify_db_changed("conta_update")
    return {
        "id": conta.id,
        "nome": conta.nome,
        "categoria": conta.categoria,
        "tipo": conta.tipo,
        "valor": centavos_to_brl(conta.valor_centavos),
        "dia_vencimento": conta.dia_vencimento,
        "competencia_inicio": conta.competencia_inicio,
        "parcelas_total": conta.parcelas_total,
        "cor_hex": conta.cor_hex,
        "observacao": conta.observacao,
        "ativo": conta.ativo,
    }


@router.delete("/{conta_id}")
def delete_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conta = db.scalar(
        select(ContaVencer).where(ContaVencer.id == conta_id, ContaVencer.usuario_id == current_user.id)
    )
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    # Estorna de forma limpa quaisquer saídas no Caixa criadas pelas baixas desta conta
    caixa_ids = [p.caixa_lancamento_id for p in conta.pagamentos if p.caixa_lancamento_id is not None]
    for cid in caixa_ids:
        cx = db.scalar(
            select(CaixaLancamento).where(
                CaixaLancamento.id == cid, CaixaLancamento.usuario_id == current_user.id
            )
        )
        if cx is not None:
            db.delete(cx)

    db.delete(conta)
    db.commit()
    notify_db_changed("conta_delete")
    return {"ok": True, "id": conta_id, "caixa_estornados": len(caixa_ids)}


@router.post("/{conta_id}/pagar")
def pagar_conta(
    conta_id: int,
    req: PagarMensalRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conta = db.scalar(
        select(ContaVencer).where(ContaVencer.id == conta_id, ContaVencer.usuario_id == current_user.id)
    )
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    existing = db.scalar(
        select(ContaPagamento).where(
            ContaPagamento.conta_id == conta.id,
            ContaPagamento.competencia == req.competencia,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Esta conta já está marcada como paga neste mês.")

    val_cent = brl_to_centavos(req.valor_pago) if req.valor_pago is not None else conta.valor_centavos
    dt_pag = req.data_pagamento or today_brt_iso()

    caixa_row: CaixaLancamento | None = None
    if req.lancar_no_caixa:
        caixa_row = CaixaLancamento(
            usuario_id=current_user.id,
            tipo="saida",
            descricao=f"Conta: {conta.nome} ({req.competencia})",
            categoria=conta.categoria or "Contas",
            valor_centavos=val_cent,
            data=dt_pag,
            forma_pagamento=req.forma_pagamento.strip() or "PIX",
            observacao="Baixa automática de Conta a Vencer",
            origem_tipo="conta",
            origem_ref_id=conta.id,
        )
        db.add(caixa_row)
        db.flush()

    pag = ContaPagamento(
        usuario_id=current_user.id,
        conta_id=conta.id,
        competencia=req.competencia,
        valor_pago_centavos=val_cent,
        data_pagamento=dt_pag,
        caixa_lancamento_id=caixa_row.id if caixa_row else None,
    )
    db.add(pag)
    db.commit()
    db.refresh(pag)
    notify_db_changed("conta_pagar")

    return {
        "ok": True,
        "pagamento_id": pag.id,
        "caixa_lancamento_id": pag.caixa_lancamento_id,
        "ocorrencia": conta_occurrence_for_month(conta, req.competencia, pag, today_brt()),
    }


@router.delete("/{conta_id}/pagamentos/{competencia}")
def estornar_pagamento_conta(
    conta_id: int,
    competencia: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    conta = db.scalar(
        select(ContaVencer).where(ContaVencer.id == conta_id, ContaVencer.usuario_id == current_user.id)
    )
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")

    pag = db.scalar(
        select(ContaPagamento).where(
            ContaPagamento.conta_id == conta.id,
            ContaPagamento.usuario_id == current_user.id,
            ContaPagamento.competencia == competencia,
        )
    )
    if pag is None:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado para esta competência.")

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
    notify_db_changed("conta_estornar")
    return {"ok": True, "estornou_caixa": estornou_caixa}
