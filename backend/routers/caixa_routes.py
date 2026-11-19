"""Rotas de Caixa Rápido (Entradas & Saídas diárias com fechamento mensal automático)."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, notify_db_changed
from models import CaixaLancamento, Usuario
from schemas import CaixaCreateRequest, CaixaUpdateRequest
from services.dates import (
    brl_to_centavos,
    centavos_to_brl,
    current_competencia_brt,
    parse_competencia,
    today_brt,
    today_brt_iso,
)

router = APIRouter(prefix="/caixa", tags=["Caixa Rápido"])


def _serialize_caixa(row: CaixaLancamento) -> dict:
    return {
        "id": row.id,
        "tipo": row.tipo,
        "descricao": row.descricao,
        "categoria": row.categoria,
        "valor": centavos_to_brl(row.valor_centavos),
        "valor_centavos": row.valor_centavos,
        "data": row.data,
        "forma_pagamento": row.forma_pagamento,
        "observacao": row.observacao,
        "origem_tipo": row.origem_tipo,
        "origem_ref_id": row.origem_ref_id,
    }


@router.get("")
def list_caixa(
    competencia: str | None = Query(default=None),
    periodo: str = Query(default="mes"),  # hoje | semana | mes | todos
    tipo: str | None = Query(default=None),  # entrada | saida
    categoria: str | None = Query(default=None),
    busca: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    comp = competencia or current_competencia_brt()
    try:
        parse_competencia(comp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stmt = select(CaixaLancamento).where(CaixaLancamento.usuario_id == current_user.id)

    today = today_brt()
    if periodo == "hoje":
        stmt = stmt.where(CaixaLancamento.data == today.isoformat())
    elif periodo == "semana":
        start_week = (today - timedelta(days=6)).isoformat()
        stmt = stmt.where(CaixaLancamento.data >= start_week, CaixaLancamento.data <= today.isoformat())
    elif periodo == "mes":
        stmt = stmt.where(CaixaLancamento.data.like(f"{comp}-%"))
    elif periodo != "todos":
        raise HTTPException(status_code=422, detail="Período inválido. Use hoje, semana, mes ou todos.")

    if tipo in ("entrada", "saida"):
        stmt = stmt.where(CaixaLancamento.tipo == tipo)
    if categoria and categoria.strip():
        stmt = stmt.where(CaixaLancamento.categoria == categoria.strip())

    rows = list(db.scalars(stmt.order_by(desc(CaixaLancamento.data), desc(CaixaLancamento.id))).all())

    if busca and busca.strip():
        q = busca.strip().lower()
        rows = [
            r
            for r in rows
            if q in r.descricao.lower()
            or q in r.categoria.lower()
            or q in (r.observacao or "").lower()
            or q in (r.forma_pagamento or "").lower()
        ]

    # Resumo do conjunto filtrado
    entrou_cent = sum(r.valor_centavos for r in rows if r.tipo == "entrada")
    saiu_cent = sum(r.valor_centavos for r in rows if r.tipo == "saida")

    # Resumo completo do mês (sempre consistente para o fechamento mensal)
    mes_rows = list(
        db.scalars(
            select(CaixaLancamento).where(
                CaixaLancamento.usuario_id == current_user.id,
                CaixaLancamento.data.like(f"{comp}-%"),
            )
        ).all()
    )
    mes_entrou = sum(r.valor_centavos for r in mes_rows if r.tipo == "entrada")
    mes_saiu = sum(r.valor_centavos for r in mes_rows if r.tipo == "saida")

    return {
        "competencia": comp,
        "periodo": periodo,
        "itens": [_serialize_caixa(r) for r in rows],
        "resumo_filtrado": {
            "entrou": centavos_to_brl(entrou_cent),
            "saiu": centavos_to_brl(saiu_cent),
            "sobrou": centavos_to_brl(entrou_cent - saiu_cent),
            "quantidade": len(rows),
        },
        "resumo_mensal": {
            "entrou": centavos_to_brl(mes_entrou),
            "saiu": centavos_to_brl(mes_saiu),
            "sobrou": centavos_to_brl(mes_entrou - mes_saiu),
            "quantidade": len(mes_rows),
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_caixa(
    req: CaixaCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    row = CaixaLancamento(
        usuario_id=current_user.id,
        tipo=req.tipo,
        descricao=req.descricao,
        categoria=req.categoria,
        valor_centavos=brl_to_centavos(req.valor),
        data=req.data or today_brt_iso(),
        forma_pagamento=req.forma_pagamento,
        observacao=req.observacao.strip(),
        origem_tipo="manual",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    notify_db_changed("caixa_create")
    return _serialize_caixa(row)


@router.put("/{item_id}")
def update_caixa(
    item_id: int,
    req: CaixaUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    row = db.scalar(
        select(CaixaLancamento).where(
            CaixaLancamento.id == item_id, CaixaLancamento.usuario_id == current_user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")

    if req.tipo is not None:
        row.tipo = req.tipo
    if req.descricao is not None:
        row.descricao = req.descricao.strip()
    if req.categoria is not None:
        row.categoria = req.categoria.strip()
    if req.valor is not None:
        row.valor_centavos = brl_to_centavos(req.valor)
    if req.data is not None:
        row.data = req.data
    if req.forma_pagamento is not None:
        row.forma_pagamento = req.forma_pagamento.strip()
    if req.observacao is not None:
        row.observacao = req.observacao.strip()

    db.commit()
    db.refresh(row)
    notify_db_changed("caixa_update")
    return _serialize_caixa(row)


@router.delete("/{item_id}")
def delete_caixa(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    row = db.scalar(
        select(CaixaLancamento).where(
            CaixaLancamento.id == item_id, CaixaLancamento.usuario_id == current_user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado.")

    db.delete(row)
    db.commit()
    notify_db_changed("caixa_delete")
    return {"ok": True, "id": item_id}
