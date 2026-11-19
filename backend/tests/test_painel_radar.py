"""Testes do Painel Executivo e do Radar Unificado de Vencimentos (Contas + Cartões + Módulos)."""

from __future__ import annotations

import importlib
from datetime import date

from conftest import register_and_headers


def test_unified_radar_urgency_buckets_and_kpis(client, monkeypatch):
    # Importa após o reload da fixture `client` e fixa a data de referência em 2026-05-10
    painel_routes = importlib.import_module("routers.painel_routes")
    monkeypatch.setattr(painel_routes, "today_brt", lambda: date(2026, 5, 10))
    h = register_and_headers(client, "Radar Master", "radar_u")

    # Entradas e Saídas no Caixa
    client.post(
        "/api/caixa",
        headers=h,
        json={"tipo": "entrada", "descricao": "Uber semana", "categoria": "Uber / App", "valor": 1500.0, "data": "2026-05-08"},
    )
    client.post(
        "/api/caixa",
        headers=h,
        json={"tipo": "saida", "descricao": "Mercado", "categoria": "Mercado", "valor": 200.0, "data": "2026-05-09"},
    )

    # 1. Conta ATRASADA (venceu dia 05/05)
    client.post(
        "/api/contas",
        headers=h,
        json={"nome": "Internet Fibra", "tipo": "fixa", "valor": 120.0, "dia_vencimento": 5, "competencia_inicio": "2026-05"},
    )
    # 2. Conta VENCE HOJE (dia 10/05)
    client.post(
        "/api/contas",
        headers=h,
        json={"nome": "Energia", "tipo": "fixa", "valor": 180.0, "dia_vencimento": 10, "competencia_inicio": "2026-05"},
    )
    # 3. Cartão PRÓXIMOS 7 DIAS (vence dia 15/05)
    card = client.post(
        "/api/cartoes",
        headers=h,
        json={"nome": "Nubank Black", "cor_hex": "#8B5CF6", "limite": 4000.0, "dia_fechamento": 8, "dia_vencimento": 15},
    ).json()
    client.post(
        f"/api/cartoes/{card['id']}/compras",
        headers=h,
        json={"descricao": "Notebook", "valor": 600.0, "parcelas_total": 2, "data_compra": "2026-05-02"},
    )
    # 4. Módulo de Dívida Thiago PRÓXIMOS 15 DIAS (vence dia 22/05 -> 12 dias)
    mod = client.post(
        "/api/modulos-divida",
        headers=h,
        json={"nome": "Thiago", "cor_hex": "#10B981", "dia_fechamento": 14, "dia_vencimento": 22},
    ).json()
    client.post(
        f"/api/modulos-divida/{mod['id']}/compras",
        headers=h,
        json={"descricao": "Compra loja", "valor": 250.0, "parcelas_total": 1, "data_compra": "2026-05-03"},
    )

    res = client.get("/api/painel/resumo?competencia=2026-05", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()

    # KPIs exatos: entrou 1500, saiu 200, sobrou 1300; a_vencer = 120 + 180 + 300 + 250 = 850; projetado = 450
    assert data["kpis"]["entrou"] == 1500.0
    assert data["kpis"]["saiu"] == 200.0
    assert data["kpis"]["sobrou"] == 1300.0
    assert data["kpis"]["a_vencer"] == 850.0
    assert data["kpis"]["saldo_projetado"] == 450.0

    radar = data["radar"]
    assert radar["resumo"]["qtd_atrasados"] == 1
    assert radar["resumo"]["qtd_hoje"] == 1
    assert radar["resumo"]["qtd_7_dias"] == 1
    assert radar["resumo"]["qtd_15_dias"] == 1
    assert radar["resumo"]["alertas_urgentes"] == 3

    statuses = [(it["titulo"], it["status_urgencia"], it["origem_tipo"]) for it in radar["itens"]]
    assert statuses == [
        ("Internet Fibra", "atrasado", "conta"),
        ("Energia", "vence_hoje", "conta"),
        ("Fatura Nubank Black", "proximos_7_dias", "cartao"),
        ("Módulo Thiago", "proximos_15_dias", "modulo_divida"),
    ]
    assert len(data["graficos"]["fluxo_mensal"]) == 6
