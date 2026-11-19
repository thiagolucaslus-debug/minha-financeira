"""Testes de autenticação multi-perfil, perfil/senha e isolamento estrito entre usuários."""

from __future__ import annotations

from conftest import register_and_headers


def test_register_login_profile_and_password(client):
    res = client.post(
        "/api/auth/register",
        json={"nome": "Thiago Lucas", "username": "Thiago.L", "senha": "minhasenha"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["usuario"]["username"] == "thiago.l"
    assert body["access_token"]
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    # Username duplicado (case-insensitive)
    dup = client.post(
        "/api/auth/register",
        json={"nome": "Outro", "username": "THIAGO.L", "senha": "outrasenha"},
    )
    assert dup.status_code == 409

    # Login com senha errada e certa
    bad = client.post("/api/auth/login", json={"username": "thiago.l", "senha": "errada"})
    assert bad.status_code == 401

    ok = client.post("/api/auth/login", json={"username": "thiago.l", "senha": "minhasenha"})
    assert ok.status_code == 200

    # Atualiza perfil + tema
    upd = client.put(
        "/api/auth/me",
        headers=headers,
        json={"nome": "Thiago Silva", "tema_preferido": "light"},
    )
    assert upd.status_code == 200
    assert upd.json()["usuario"]["nome"] == "Thiago Silva"
    assert upd.json()["usuario"]["tema_preferido"] == "light"

    # Troca senha
    wrong_pw = client.put(
        "/api/auth/password",
        headers=headers,
        json={"senha_atual": "errada", "nova_senha": "novasenha99"},
    )
    assert wrong_pw.status_code == 400

    ok_pw = client.put(
        "/api/auth/password",
        headers=headers,
        json={"senha_atual": "minhasenha", "nova_senha": "novasenha99"},
    )
    assert ok_pw.status_code == 200

    # Login antigo falha, novo funciona
    assert client.post("/api/auth/login", json={"username": "thiago.l", "senha": "minhasenha"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "thiago.l", "senha": "novasenha99"}).status_code == 200


def test_strict_multi_profile_isolation(client):
    h_a = register_and_headers(client, "Perfil Alpha", "alpha")
    h_b = register_and_headers(client, "Perfil Beta", "beta")

    # Alpha cria recursos em todos os módulos
    cx = client.post(
        "/api/caixa",
        headers=h_a,
        json={"tipo": "entrada", "descricao": "Uber manhã", "categoria": "Uber / App", "valor": 100.0, "data": "2026-05-10"},
    ).json()
    conta = client.post(
        "/api/contas",
        headers=h_a,
        json={"nome": "Aluguel Alpha", "tipo": "fixa", "valor": 1200.0, "dia_vencimento": 10, "competencia_inicio": "2026-05"},
    ).json()
    cartao = client.post(
        "/api/cartoes",
        headers=h_a,
        json={"nome": "Black Alpha", "cor_hex": "#C9A45C", "limite": 5000.0, "dia_fechamento": 10, "dia_vencimento": 17},
    ).json()
    compra_c = client.post(
        f"/api/cartoes/{cartao['id']}/compras",
        headers=h_a,
        json={"descricao": "Tênis", "valor": 300.0, "parcelas_total": 3, "data_compra": "2026-05-05"},
    ).json()
    mod = client.post(
        "/api/modulos-divida",
        headers=h_a,
        json={"nome": "Seu Luiz", "cor_hex": "#10B981", "dia_fechamento": 12, "dia_vencimento": 20},
    ).json()
    compra_m = client.post(
        f"/api/modulos-divida/{mod['id']}/compras",
        headers=h_a,
        json={"descricao": "Pneu carro", "valor": 400.0, "parcelas_total": 2, "data_compra": "2026-05-05"},
    ).json()

    # Beta não enxerga nada do Alpha
    assert client.get("/api/caixa?competencia=2026-05", headers=h_b).json()["itens"] == []
    assert client.get("/api/contas?competencia=2026-05", headers=h_b).json()["itens"] == []
    assert client.get("/api/cartoes?competencia=2026-05", headers=h_b).json()["itens"] == []
    assert client.get("/api/modulos-divida?competencia=2026-05", headers=h_b).json()["itens"] == []
    assert client.get("/api/painel/resumo?competencia=2026-05", headers=h_b).json()["radar"]["itens"] == []

    # Beta não consegue alterar, pagar nem excluir recursos do Alpha (404 estrito)
    assert client.delete(f"/api/caixa/{cx['id']}", headers=h_b).status_code == 404
    assert client.put(f"/api/caixa/{cx['id']}", headers=h_b, json={"valor": 1.0}).status_code == 404
    assert client.post(f"/api/contas/{conta['id']}/pagar", headers=h_b, json={"competencia": "2026-05"}).status_code == 404
    assert client.delete(f"/api/contas/{conta['id']}", headers=h_b).status_code == 404
    assert client.delete(f"/api/cartoes/{cartao['id']}/compras/{compra_c['id']}", headers=h_b).status_code == 404
    assert client.delete(f"/api/cartoes/{cartao['id']}", headers=h_b).status_code == 404
    assert client.delete(f"/api/modulos-divida/{mod['id']}/compras/{compra_m['id']}", headers=h_b).status_code == 404
    assert client.delete(f"/api/modulos-divida/{mod['id']}", headers=h_b).status_code == 404

    # Sem token -> 401
    assert client.get("/api/painel/resumo").status_code == 401
