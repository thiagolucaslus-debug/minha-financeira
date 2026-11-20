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

    # Cores dos itens no gráfico de distribuição preservam a cor escolhida do cartão/módulo
    dist_by_name = {d["nome"]: d["cor"] for d in data["graficos"]["distribuicao"]}
    assert dist_by_name.get("Fatura Nubank Black") == "#8B5CF6"
    assert dist_by_name.get("Módulo Thiago") == "#10B981"


def test_radar_cross_month_overdue_and_15day_lookahead(client, monkeypatch):
    # Hoje = 28/05/2026, consultando o mês corrente 2026-05
    painel_routes = importlib.import_module("routers.painel_routes")
    monkeypatch.setattr(painel_routes, "today_brt", lambda: date(2026, 5, 28))
    h = register_and_headers(client, "Radar Cross", "radar_cross")

    # 1. Conta atrasada de Abril (venceu 20/04 -> 38 dias de atraso)
    c_abr = client.post(
        "/api/contas",
        headers=h,
        json={
            "nome": "Aluguel Atrasado",
            "tipo": "parcelada",
            "valor": 900.0,
            "dia_vencimento": 20,
            "competencia_inicio": "2026-04",
            "parcelas_total": 1,
        },
    ).json()
    # 2. Módulo Seu Luiz atrasado de Abril (venceu 25/04)
    mod_luiz = client.post(
        "/api/modulos-divida",
        headers=h,
        json={"nome": "Seu Luiz", "cor_hex": "#F59E0B", "dia_fechamento": 15, "dia_vencimento": 25},
    ).json()
    client.post(
        f"/api/modulos-divida/{mod_luiz['id']}/compras",
        headers=h,
        json={"descricao": "Oficina Abril", "valor": 350.0, "parcelas_total": 1, "data_compra": "2026-04-10"},
    )
    # 3. Conta de Junho vencendo dia 02/06 (5 dias -> Próximos 7 dias!)
    client.post(
        "/api/contas",
        headers=h,
        json={
            "nome": "Internet Inicio Junho",
            "tipo": "parcelada",
            "valor": 150.0,
            "dia_vencimento": 2,
            "competencia_inicio": "2026-06",
            "parcelas_total": 1,
        },
    )
    # 4. Cartão de Junho vencendo dia 08/06 (11 dias -> Próximos 15 dias!)
    card = client.post(
        "/api/cartoes",
        headers=h,
        json={"nome": "Inter Black", "cor_hex": "#EA580C", "limite": 3000, "dia_fechamento": 20, "dia_vencimento": 8},
    ).json()
    client.post(
        f"/api/cartoes/{card['id']}/compras",
        headers=h,
        json={"descricao": "Compra Maio", "valor": 200.0, "parcelas_total": 1, "data_compra": "2026-05-15"},
    )
    # 5. Conta de Junho vencendo dia 25/06 (28 dias -> fora da janela de 15 dias, NÃO deve poluir Maio)
    client.post(
        "/api/contas",
        headers=h,
        json={
            "nome": "Conta Distante Junho",
            "tipo": "parcelada",
            "valor": 500.0,
            "dia_vencimento": 25,
            "competencia_inicio": "2026-06",
            "parcelas_total": 1,
        },
    )

    res = client.get("/api/painel/resumo?competencia=2026-05", headers=h).json()
    radar = res["radar"]
    by_title = {it["titulo"]: it for it in radar["itens"]}

    assert "Aluguel Atrasado" in by_title
    assert by_title["Aluguel Atrasado"]["status_urgencia"] == "atrasado"
    assert by_title["Aluguel Atrasado"]["competencia"] == "2026-04"
    assert by_title["Aluguel Atrasado"]["fora_competencia"] == "anterior"

    assert "Módulo Seu Luiz" in by_title
    assert by_title["Módulo Seu Luiz"]["status_urgencia"] == "atrasado"
    assert by_title["Módulo Seu Luiz"]["competencia"] == "2026-04"

    assert "Internet Inicio Junho" in by_title
    assert by_title["Internet Inicio Junho"]["status_urgencia"] == "proximos_7_dias"
    assert by_title["Internet Inicio Junho"]["fora_competencia"] == "proximo"

    assert "Fatura Inter Black" in by_title
    assert by_title["Fatura Inter Black"]["status_urgencia"] == "proximos_15_dias"
    assert by_title["Fatura Inter Black"]["fora_competencia"] == "proximo"

    assert "Conta Distante Junho" not in by_title
    assert radar["resumo"]["atrasados_anteriores_total"] == 1250.0
    assert radar["resumo"]["proximos_mes_seguinte_total"] == 350.0
    assert radar["resumo"]["qtd_atrasados"] == 2
    assert radar["resumo"]["qtd_7_dias"] == 1
    assert radar["resumo"]["qtd_15_dias"] == 1

    # Pagar o aluguel atrasado usando a competencia original (2026-04) remove-o dos atrasados do Radar de Maio
    pay = client.post(
        f"/api/contas/{c_abr['id']}/pagar",
        headers=h,
        json={"competencia": "2026-04", "lancar_no_caixa": True, "data_pagamento": "2026-05-28"},
    )
    assert pay.status_code == 200
    res2 = client.get("/api/painel/resumo?competencia=2026-05", headers=h).json()
    assert res2["radar"]["resumo"]["qtd_atrasados"] == 1
    assert res2["radar"]["resumo"]["atrasados_anteriores_total"] == 350.0

    # Navegar explicitamente para mês histórico (2026-04) não duplica itens de outros meses
    res_abr = client.get("/api/painel/resumo?competencia=2026-04", headers=h).json()
    assert all(it["competencia"] == "2026-04" for it in res_abr["radar"]["itens"])
