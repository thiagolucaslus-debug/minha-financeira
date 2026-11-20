"""
Rotas de Módulos de Dívida no estilo 'Cartão Virtual' (ex.: Thiago, Seu Luiz).
Cada módulo funciona como um cartão próprio: nome, cor livre, fechamento, vencimento,
múltiplas compras à vista ou parceladas (Nx), fatura mensal detalhada, exclusão
individual de compras sem apagar o módulo, baixa mensal (com opção de abater do Caixa)
e integração automática ao Radar Unificado de Vencimentos.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db, notify_db_changed
from models import (
    CaixaLancamento,
    ModuloCompra,
    ModuloDivida,
    ModuloFaturaPagamento,
    Usuario,
)
from schemas import (
    CompraCreateRequest,
    ModuloDividaCreateRequest,
    ModuloDividaUpdateRequest,
    PagarMensalRequest,
)
from services.dates import (
    brl_to_centavos,
    centavos_to_brl,
    current_competencia_brt,
    first_billing_competencia,
    parse_competencia,
    today_brt,
    today_brt_iso,
)
from services.radar import build_modulo_month_view

router = APIRouter(prefix="/modulos-divida", tags=["Módulos de Dívida"])


@router.get("")
def list_modulos(
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
    modulos = list(
        db.scalars(
            select(ModuloDivida)
            .where(ModuloDivida.usuario_id == current_user.id, ModuloDivida.ativo.is_(True))
            .order_by(ModuloDivida.nome.asc())
        ).all()
    )
    compras_all = list(
        db.scalars(select(ModuloCompra).where(ModuloCompra.usuario_id == current_user.id)).all()
    )
    pags_all = list(
        db.scalars(
            select(ModuloFaturaPagamento).where(ModuloFaturaPagamento.usuario_id == current_user.id)
        ).all()
    )

    compras_map: dict[int, list[ModuloCompra]] = {}
    for c in compras_all:
        compras_map.setdefault(c.modulo_id, []).append(c)
    pags_map: dict[int, list[ModuloFaturaPagamento]] = {}
    for p in pags_all:
        pags_map.setdefault(p.modulo_id, []).append(p)

    views = [
        build_modulo_month_view(m, compras_map.get(m.id, []), pags_map.get(m.id, []), comp, today)
        for m in modulos
    ]
    total_mes_cent = sum(v["valor_efetivo_centavos"] for v in views)
    total_pago_cent = sum(v["valor_efetivo_centavos"] for v in views if v["pago"])

    return {
        "competencia": comp,
        "itens": views,
        "resumo": {
            "total_mes": centavos_to_brl(total_mes_cent),
            "total_pago": centavos_to_brl(total_pago_cent),
            "total_pendente": centavos_to_brl(max(0, total_mes_cent - total_pago_cent)),
            "quantidade_modulos": len(views),
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_modulo(
    req: ModuloDividaCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mod = ModuloDivida(
        usuario_id=current_user.id,
        nome=req.nome.strip(),
        descricao=req.descricao.strip(),
        cor_hex=req.cor_hex,
        dia_fechamento=req.dia_fechamento,
        dia_vencimento=req.dia_vencimento,
        limite_centavos=brl_to_centavos(req.limite),
        ativo=True,
    )
    db.add(mod)
    db.commit()
    db.refresh(mod)
    notify_db_changed("modulo_divida_create")

    return build_modulo_month_view(mod, [], [], current_competencia_brt(), today_brt())


@router.put("/{modulo_id}")
def update_modulo(
    modulo_id: int,
    req: ModuloDividaUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mod = db.scalar(
        select(ModuloDivida).where(
            ModuloDivida.id == modulo_id, ModuloDivida.usuario_id == current_user.id
        )
    )
    if mod is None:
        raise HTTPException(status_code=404, detail="Módulo de dívida não encontrado.")

    if req.nome is not None:
        mod.nome = req.nome.strip()
    if req.descricao is not None:
        mod.descricao = req.descricao.strip()
    if req.cor_hex is not None:
        mod.cor_hex = req.cor_hex
    if req.dia_fechamento is not None:
        mod.dia_fechamento = req.dia_fechamento
    if req.dia_vencimento is not None:
        mod.dia_vencimento = req.dia_vencimento
    if req.limite is not None:
        mod.limite_centavos = brl_to_centavos(req.limite)
    if req.ativo is not None:
        mod.ativo = req.ativo

    db.commit()
    db.refresh(mod)
    notify_db_changed("modulo_divida_update")
    return build_modulo_month_view(
        mod, mod.compras, mod.pagamentos, current_competencia_brt(), today_brt()
    )


@router.delete("/{modulo_id}")
def delete_modulo(
    modulo_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mod = db.scalar(
        select(ModuloDivida).where(
            ModuloDivida.id == modulo_id, ModuloDivida.usuario_id == current_user.id
        )
    )
    if mod is None:
        raise HTTPException(status_code=404, detail="Módulo de dívida não encontrado.")

    caixa_ids = [p.caixa_lancamento_id for p in mod.pagamentos if p.caixa_lancamento_id is not None]
    for cid in caixa_ids:
        cx = db.scalar(
            select(CaixaLancamento).where(
                CaixaLancamento.id == cid, CaixaLancamento.usuario_id == current_user.id
            )
        )
        if cx is not None:
            db.delete(cx)

    db.delete(mod)
    db.commit()
    notify_db_changed("modulo_divida_delete")
    return {"ok": True, "id": modulo_id, "caixa_estornados": len(caixa_ids)}


@router.post("/{modulo_id}/compras", status_code=status.HTTP_201_CREATED)
def create_modulo_compra(
    modulo_id: int,
    req: CompraCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mod = db.scalar(
        select(ModuloDivida).where(
            ModuloDivida.id == modulo_id, ModuloDivida.usuario_id == current_user.id
        )
    )
    if mod is None:
        raise HTTPException(status_code=404, detail="Módulo de dívida não encontrado.")

    dt_compra = req.data_compra or today_brt_iso()
    comp_ini = req.competencia_inicial or first_billing_competencia(
        dt_compra, mod.dia_fechamento, mod.dia_vencimento
    )
    valor_total_cent = (
        brl_to_centavos(req.valor) * req.parcelas_total
        if req.modo_valor == "parcela"
        else brl_to_centavos(req.valor)
    )

    compra = ModuloCompra(
        usuario_id=current_user.id,
        modulo_id=mod.id,
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
    notify_db_changed("modulo_compra_create")

    return {
        "id": compra.id,
        "modulo_id": mod.id,
        "descricao": compra.descricao,
        "categoria": compra.categoria,
        "data_compra": compra.data_compra,
        "valor_total": centavos_to_brl(compra.valor_total_centavos),
        "parcelas_total": compra.parcelas_total,
        "competencia_inicial": compra.competencia_inicial,
    }


@router.delete("/{modulo_id}/compras/{compra_id}")
def delete_modulo_compra(
    modulo_id: int,
    compra_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    compra = db.scalar(
        select(ModuloCompra).where(
            ModuloCompra.id == compra_id,
            ModuloCompra.modulo_id == modulo_id,
            ModuloCompra.usuario_id == current_user.id,
        )
    )
    if compra is None:
        raise HTTPException(status_code=404, detail="Compra não encontrada neste módulo.")

    db.delete(compra)
    db.commit()
    notify_db_changed("modulo_compra_delete")
    return {"ok": True, "id": compra_id}


@router.post("/{modulo_id}/pagar")
def pagar_modulo_mes(
    modulo_id: int,
    req: PagarMensalRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    mod = db.scalar(
        select(ModuloDivida).where(
            ModuloDivida.id == modulo_id, ModuloDivida.usuario_id == current_user.id
        )
    )
    if mod is None:
        raise HTTPException(status_code=404, detail="Módulo de dívida não encontrado.")

    existing = db.scalar(
        select(ModuloFaturaPagamento).where(
            ModuloFaturaPagamento.modulo_id == mod.id,
            ModuloFaturaPagamento.competencia == req.competencia,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Este módulo já foi pago nesta competência.")

    view = build_modulo_month_view(mod, mod.compras, mod.pagamentos, req.competencia, today_brt())
    val_cent = (
        brl_to_centavos(req.valor_pago) if req.valor_pago is not None else view["total_mes_centavos"]
    )
    if val_cent <= 0:
        raise HTTPException(status_code=400, detail="Este módulo não possui valor em aberto neste mês.")

    dt_pag = req.data_pagamento or today_brt_iso()
    caixa_row: CaixaLancamento | None = None
    if req.lancar_no_caixa:
        caixa_row = CaixaLancamento(
            usuario_id=current_user.id,
            tipo="saida",
            descricao=f"Módulo {mod.nome} ({req.competencia})",
            categoria="Dívidas",
            valor_centavos=val_cent,
            data=dt_pag,
            forma_pagamento=req.forma_pagamento.strip() or "PIX",
            observacao="Pagamento mensal de Módulo de Dívida",
            origem_tipo="modulo_divida",
            origem_ref_id=mod.id,
        )
        db.add(caixa_row)
        db.flush()

    pag = ModuloFaturaPagamento(
        usuario_id=current_user.id,
        modulo_id=mod.id,
        competencia=req.competencia,
        valor_pago_centavos=val_cent,
        data_pagamento=dt_pag,
        caixa_lancamento_id=caixa_row.id if caixa_row else None,
    )
    db.add(pag)
    db.commit()
    db.refresh(pag)
    notify_db_changed("modulo_pagar")
    return {
        "ok": True,
        "pagamento_id": pag.id,
        "caixa_lancamento_id": pag.caixa_lancamento_id,
        "valor_pago": centavos_to_brl(val_cent),
    }


@router.delete("/{modulo_id}/pagamentos/{competencia}")
def estornar_modulo_mes(
    modulo_id: int,
    competencia: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    try:
        parse_competencia(competencia)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    pag = db.scalar(
        select(ModuloFaturaPagamento).where(
            ModuloFaturaPagamento.modulo_id == modulo_id,
            ModuloFaturaPagamento.usuario_id == current_user.id,
            ModuloFaturaPagamento.competencia == competencia,
        )
    )
    if pag is None:
        raise HTTPException(status_code=404, detail="Pagamento do módulo não encontrado.")

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
    notify_db_changed("modulo_estornar")
    return {"ok": True, "estornou_caixa": estornou_caixa}
