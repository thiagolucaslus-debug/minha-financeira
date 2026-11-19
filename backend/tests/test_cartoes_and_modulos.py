"""Testes de Meus Cartões de Crédito e Módulos de Dívida estilo Cartão Virtual (Thiago / Seu Luiz)."""

from __future__ import annotations

from conftest import register_and_headers


def test_credit_card_cycle_penny_exact_installments_and_payment(client):
    h = register_and_headers(client, "Cartões User", "cartoes_u")

    # Cartão fecha dia 25 e vence dia 05 do mês seguinte (ciclo cruzado!)
    card = client.post(
        "/api/cartoes",
        headers=h,
        json={
            "nome": "Black Ouro",
            "bandeira": "Mastercard Black",
            "ultimos_digitos": "8842",
            "cor_hex": "#8B5CF6",
            "limite": 2000.0,
            "dia_fechamento": 25,
            "dia_vencimento": 5,
        },
    ).json()
    cid = card["id"]
    assert card["cor_hex"] == "#8B5CF6"

    # Compra dia 20/05 (antes do fechamento dia 25/05) -> 1ª parcela vence em 2026-06 (dia 05/06)
    # R$ 100,00 em 3x -> 33.34, 33.33, 33.33 (soma exata = 100.00)
    c1 = client.post(
        f"/api/cartoes/{cid}/compras",
        headers=h,
        json={"descricao": "Fone Bluetooth", "valor": 100.0, "parcelas_total": 3, "data_compra": "2026-05-20"},
    )
    assert c1.status_code == 201
    assert c1.json()["competencia_inicial"] == "2026-06"

    # Compra dia 26/05 (DEPOIS do fechamento dia 25/05) -> 1ª parcela vence em 2026-07 (dia 05/07)
    c2 = client.post(
        f"/api/cartoes/{cid}/compras",
        headers=h,
        json={"descricao": "Combustível", "valor": 150.0, "parcelas_total": 1, "data_compra": "2026-05-26"},
    )
    assert c2.status_code == 201
    assert c2.json()["competencia_inicial"] == "2026-07"

    jun = client.get("/api/cartoes?competencia=2026-06", headers=h).json()["itens"][0]
    assert jun["total_fatura"] == 33.34
    assert jun["limite_usado"] == 250.0  # 100 + 150 ainda não pagos
    assert jun["limite_disponivel"] == 1750.0

    jul = client.get("/api/cartoes?competencia=2026-07", headers=h).json()["itens"][0]
    assert jul["total_fatura"] == 183.33  # 33.33 + 150.00

    ago = client.get("/api/cartoes?competencia=2026-08", headers=h).json()["itens"][0]
    assert ago["total_fatura"] == 33.33

    # Paga fatura de Junho integrando ao Caixa e verifica liberação do limite + estorno limpo
    pag = client.post(
        f"/api/cartoes/{cid}/pagar",
        headers=h,
        json={"competencia": "2026-06", "lancar_no_caixa": True, "data_pagamento": "2026-06-05"},
    )
    assert pag.status_code == 200
    assert pag.json()["valor_pago"] == 33.34

    jun_paid = client.get("/api/cartoes?competencia=2026-06", headers=h).json()["itens"][0]
    assert jun_paid["pago"] is True
    assert jun_paid["limite_usado"] == 216.66  # 250.00 - 33.34

    # Estorna pagamento de Junho -> saída do Caixa some
    undo = client.delete(f"/api/cartoes/{cid}/pagamentos/2026-06", headers=h)
    assert undo.status_code == 200
    assert undo.json()["estornou_caixa"] is True
    assert client.get("/api/caixa?competencia=2026-06", headers=h).json()["resumo_mensal"]["saiu"] == 0.0


def test_virtual_card_debt_modules_thiago_and_seu_luiz(client):
    h = register_and_headers(client, "Dívidas User", "dividas_u")

    # Cria dois módulos estilo Cartão Virtual: Thiago e Seu Luiz
    m_thiago = client.post(
        "/api/modulos-divida",
        headers=h,
        json={
            "nome": "Thiago",
            "descricao": "Cartão compartilhado Thiago",
            "cor_hex": "#10B981",
            "dia_fechamento": 10,
            "dia_vencimento": 18,
            "limite": 3000.0,
        },
    ).json()
    m_luiz = client.post(
        "/api/modulos-divida",
        headers=h,
        json={
            "nome": "Seu Luiz",
            "descricao": "Compras no cartão do Seu Luiz",
            "cor_hex": "#F59E0B",
            "dia_fechamento": 15,
            "dia_vencimento": 25,
        },
    ).json()

    # Múltiplas compras dentro do módulo Thiago (1 à vista + 1 parcelada em 4x)
    t_c1 = client.post(
        f"/api/modulos-divida/{m_thiago['id']}/compras",
        headers=h,
        json={"descricao": "Supermercado Atacadão", "valor": 240.0, "parcelas_total": 1, "data_compra": "2026-05-04"},
    ).json()
    t_c2 = client.post(
        f"/api/modulos-divida/{m_thiago['id']}/compras",
        headers=h,
        json={"descricao": "Celular Novo", "valor": 1200.0, "parcelas_total": 4, "data_compra": "2026-05-06"},
    ).json()

    # Compra por valor da parcela no módulo Seu Luiz (6x de R$ 150 = R$ 900 total)
    l_c1 = client.post(
        f"/api/modulos-divida/{m_luiz['id']}/compras",
        headers=h,
        json={
            "descricao": "Peças carro",
            "valor": 150.0,
            "modo_valor": "parcela",
            "parcelas_total": 6,
            "data_compra": "2026-05-10",
        },
    ).json()
    assert l_c1["valor_total"] == 900.0

    # Fatura de Maio de Thiago = 240 + 300 = 540; Seu Luiz = 150
    mai = client.get("/api/modulos-divida?competencia=2026-05", headers=h).json()
    by_name = {m["nome"]: m for m in mai["itens"]}
    assert by_name["Thiago"]["total_mes"] == 540.0
    assert len(by_name["Thiago"]["itens"]) == 2
    assert by_name["Thiago"]["total_futuro"] == 900.0  # 3 parcelas restantes de 300
    assert by_name["Seu Luiz"]["total_mes"] == 150.0
    assert by_name["Seu Luiz"]["total_futuro"] == 750.0

    # Exclui compra individual do módulo Thiago SEM apagar o módulo nem a outra compra!
    del_c = client.delete(f"/api/modulos-divida/{m_thiago['id']}/compras/{t_c1['id']}", headers=h)
    assert del_c.status_code == 200

    mai_after = {m["nome"]: m for m in client.get("/api/modulos-divida?competencia=2026-05", headers=h).json()["itens"]}
    assert "Thiago" in mai_after
    assert mai_after["Thiago"]["total_mes"] == 300.0
    assert len(mai_after["Thiago"]["itens"]) == 1
    assert mai_after["Thiago"]["itens"][0]["id"] == t_c2["id"]

    # Baixa mensal do módulo Thiago integrando ao Caixa + estorno limpo
    pay_m = client.post(
        f"/api/modulos-divida/{m_thiago['id']}/pagar",
        headers=h,
        json={"competencia": "2026-05", "lancar_no_caixa": True, "data_pagamento": "2026-05-18"},
    )
    assert pay_m.status_code == 200
    assert client.get("/api/caixa?competencia=2026-05", headers=h).json()["resumo_mensal"]["saiu"] == 300.0

    undo_m = client.delete(f"/api/modulos-divida/{m_thiago['id']}/pagamentos/2026-05", headers=h)
    assert undo_m.status_code == 200
    assert undo_m.json()["estornou_caixa"] is True
    assert client.get("/api/caixa?competencia=2026-05", headers=h).json()["resumo_mensal"]["saiu"] == 0.0
