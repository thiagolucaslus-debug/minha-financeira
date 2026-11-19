"""Testes de Caixa Rápido (Uber +100 / Mercado -20) e Contas a Vencer (meses curtos, baixa e estorno)."""

from __future__ import annotations

from conftest import register_and_headers


def test_caixa_uber_mercado_filters_and_closing(client):
    h = register_and_headers(client, "Motorista App", "motorista")

    r1 = client.post(
        "/api/caixa",
        headers=h,
        json={"tipo": "entrada", "descricao": "Uber corrida manhã", "categoria": "Uber / App", "valor": 100.0, "data": "2026-05-12"},
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/caixa",
        headers=h,
        json={"tipo": "saida", "descricao": "Mercado bairro", "categoria": "Mercado", "valor": 20.0, "data": "2026-05-12"},
    )
    assert r2.status_code == 201
    cx2_id = r2.json()["id"]

    # Fechamento mensal: entrou 100, saiu 20, sobrou 80
    lst = client.get("/api/caixa?competencia=2026-05&periodo=mes", headers=h).json()
    assert lst["resumo_mensal"]["entrou"] == 100.0
    assert lst["resumo_mensal"]["saiu"] == 20.0
    assert lst["resumo_mensal"]["sobrou"] == 80.0

    # Filtro por busca
    busca = client.get("/api/caixa?competencia=2026-05&periodo=mes&busca=uber", headers=h).json()
    assert len(busca["itens"]) == 1
    assert busca["itens"][0]["descricao"] == "Uber corrida manhã"

    # Edição e exclusão
    upd = client.put(f"/api/caixa/{cx2_id}", headers=h, json={"valor": 35.5})
    assert upd.status_code == 200
    assert upd.json()["valor"] == 35.5

    lst2 = client.get("/api/caixa?competencia=2026-05&periodo=mes", headers=h).json()
    assert lst2["resumo_mensal"]["sobrou"] == 64.5

    assert client.delete(f"/api/caixa/{cx2_id}", headers=h).status_code == 200
    lst3 = client.get("/api/caixa?competencia=2026-05&periodo=mes", headers=h).json()
    assert lst3["resumo_mensal"]["saiu"] == 0.0
    assert lst3["resumo_mensal"]["sobrou"] == 100.0


def test_contas_short_month_clamping_installments_pay_and_clean_revert(client):
    h = register_and_headers(client, "Gestor Contas", "contas_user")

    # Conta fixa dia 31 -> fevereiro 2026 deve ajustar para 28, fevereiro 2028 (bissexto) para 29, abril para 30
    c_fixa = client.post(
        "/api/contas",
        headers=h,
        json={
            "nome": "Condomínio",
            "categoria": "Moradia",
            "tipo": "fixa",
            "valor": 450.0,
            "dia_vencimento": 31,
            "competencia_inicio": "2026-01",
            "cor_hex": "#C9A45C",
        },
    )
    assert c_fixa.status_code == 201
    fixa_id = c_fixa.json()["id"]

    feb26 = client.get("/api/contas?competencia=2026-02", headers=h).json()["itens"][0]
    assert feb26["data_vencimento"] == "2026-02-28"
    assert feb26["dia_ajustado"] is True

    apr26 = client.get("/api/contas?competencia=2026-04", headers=h).json()["itens"][0]
    assert apr26["data_vencimento"] == "2026-04-30"
    assert apr26["dia_ajustado"] is True

    feb28 = client.get("/api/contas?competencia=2028-02", headers=h).json()["itens"][0]
    assert feb28["data_vencimento"] == "2028-02-29"

    # Conta parcelada 3x a partir de 2026-05 -> aparece em 05, 06, 07 e desaparece em 08
    c_parc = client.post(
        "/api/contas",
        headers=h,
        json={
            "nome": "Financiamento Moto",
            "categoria": "Veículo",
            "tipo": "parcelada",
            "valor": 600.0,
            "dia_vencimento": 20,
            "competencia_inicio": "2026-05",
            "parcelas_total": 3,
        },
    )
    assert c_parc.status_code == 201
    parc_id = c_parc.json()["id"]

    m07 = [i for i in client.get("/api/contas?competencia=2026-07", headers=h).json()["itens"] if i["id"] == parc_id]
    assert len(m07) == 1
    assert m07[0]["parcela_atual"] == 3
    assert m07[0]["parcelas_total"] == 3

    m08 = [i for i in client.get("/api/contas?competencia=2026-08", headers=h).json()["itens"] if i["id"] == parc_id]
    assert m08 == []

    # Baixa em 1 toque lançando no Caixa + estorno limpo remove do Caixa
    pay = client.post(
        f"/api/contas/{fixa_id}/pagar",
        headers=h,
        json={"competencia": "2026-05", "lancar_no_caixa": True, "data_pagamento": "2026-05-15"},
    )
    assert pay.status_code == 200
    assert pay.json()["caixa_lancamento_id"] is not None

    # Duplicado retorna 409
    assert client.post(f"/api/contas/{fixa_id}/pagar", headers=h, json={"competencia": "2026-05"}).status_code == 409

    # Verifica saída criada no Caixa
    cx_after_pay = client.get("/api/caixa?competencia=2026-05", headers=h).json()
    assert cx_after_pay["resumo_mensal"]["saiu"] == 450.0

    # Desfazer pagamento (estorno limpo)
    undo = client.delete(f"/api/contas/{fixa_id}/pagamentos/2026-05", headers=h)
    assert undo.status_code == 200
    assert undo.json()["estornou_caixa"] is True

    cx_after_undo = client.get("/api/caixa?competencia=2026-05", headers=h).json()
    assert cx_after_undo["resumo_mensal"]["saiu"] == 0.0

    # Pagar novamente e DELETAR a conta -> também estorna a saída vinculada no Caixa
    client.post(
        f"/api/contas/{parc_id}/pagar",
        headers=h,
        json={"competencia": "2026-05", "lancar_no_caixa": True, "data_pagamento": "2026-05-20"},
    )
    assert client.get("/api/caixa?competencia=2026-05", headers=h).json()["resumo_mensal"]["saiu"] == 600.0

    del_res = client.delete(f"/api/contas/{parc_id}", headers=h)
    assert del_res.status_code == 200
    assert del_res.json()["caixa_estornados"] == 1
    assert client.get("/api/caixa?competencia=2026-05", headers=h).json()["resumo_mensal"]["saiu"] == 0.0
