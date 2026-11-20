"""Esquemas Pydantic v2 para validação estrita das rotas da Minha Financeira."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from services.dates import COMPETENCIA_RE, brl_to_centavos, parse_iso_date

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex(v: str) -> str:
    cleaned = (v or "").strip()
    if not HEX_COLOR_RE.match(cleaned):
        raise ValueError("Informe uma cor hexadecimal válida no formato #RRGGBB.")
    return cleaned.upper()


def _validate_competencia(v: str) -> str:
    cleaned = (v or "").strip()
    if not COMPETENCIA_RE.match(cleaned):
        raise ValueError("Competência inválida. Use o formato YYYY-MM.")
    return cleaned


def _validate_iso_date(v: str) -> str:
    cleaned = (v or "").strip()
    try:
        parsed = parse_iso_date(cleaned)
    except ValueError as exc:
        raise ValueError("Data inválida. Informe uma data real no formato YYYY-MM-DD.") from exc
    return parsed.isoformat()


def _validate_required_text(v: str) -> str:
    cleaned = (v or "").strip()
    if not cleaned:
        raise ValueError("Campo obrigatório não pode ficar em branco.")
    return cleaned


def _validate_optional_text(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        raise ValueError("Campo não pode ficar em branco.")
    return cleaned


def _validate_positive_money(v: float) -> float:
    if not math.isfinite(v) or brl_to_centavos(v) < 1:
        raise ValueError("Informe um valor válido de pelo menos R$ 0,01.")
    return float(v)


def _validate_non_negative_money(v: float) -> float:
    if not math.isfinite(v) or v < 0:
        raise ValueError("Informe um valor numérico válido maior ou igual a zero.")
    return float(v)


# ---------------------------------------------------------------------------
# Auth & Perfil
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    username: str = Field(..., min_length=3, max_length=80)
    senha: str = Field(..., min_length=4, max_length=128)

    @field_validator("nome")
    @classmethod
    def _clean_nome(cls, v: str) -> str:
        c = v.strip()
        if len(c) < 2:
            raise ValueError("Informe seu nome (mínimo 2 caracteres).")
        return c

    @field_validator("username")
    @classmethod
    def _clean_username(cls, v: str) -> str:
        c = v.strip().lower()
        if not re.match(r"^[a-z0-9._@-]{3,80}$", c):
            raise ValueError(
                "Usuário deve ter entre 3 e 80 caracteres (letras, números, ponto, traço ou _)."
            )
        return c


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    senha: str = Field(..., min_length=1, max_length=128)


class ProfileUpdateRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=80)
    tema_preferido: Literal["dark", "light"] | None = None

    @field_validator("nome")
    @classmethod
    def _clean_nome(cls, v: str | None) -> str | None:
        if v is None:
            return None
        c = v.strip()
        if len(c) < 2:
            raise ValueError("Informe um nome com pelo menos 2 caracteres.")
        return c

    @field_validator("username")
    @classmethod
    def _clean_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        c = v.strip().lower()
        if not re.match(r"^[a-z0-9._@-]{3,80}$", c):
            raise ValueError("Usuário inválido (use letras, números, ponto, traço ou _).")
        return c


class PasswordChangeRequest(BaseModel):
    senha_atual: str = Field(..., min_length=1, max_length=128)
    nova_senha: str = Field(..., min_length=4, max_length=128)


# ---------------------------------------------------------------------------
# Caixa Rápido (Entradas & Saídas)
# ---------------------------------------------------------------------------
class CaixaCreateRequest(BaseModel):
    tipo: Literal["entrada", "saida"]
    descricao: str = Field(..., min_length=1, max_length=180)
    categoria: str = Field(default="Geral", min_length=1, max_length=80)
    valor: float = Field(..., ge=0.01, le=100_000_000)
    data: str | None = None
    forma_pagamento: str = Field(default="PIX", max_length=40)
    observacao: str = Field(default="", max_length=500)

    @field_validator("descricao", "categoria", "forma_pagamento")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return _validate_required_text(v)

    @field_validator("valor")
    @classmethod
    def _v_valor(cls, v: float) -> float:
        return _validate_positive_money(v)

    @field_validator("data")
    @classmethod
    def _v_data(cls, v: str | None) -> str | None:
        return _validate_iso_date(v) if v else None


class CaixaUpdateRequest(BaseModel):
    tipo: Literal["entrada", "saida"] | None = None
    descricao: str | None = Field(default=None, min_length=1, max_length=180)
    categoria: str | None = Field(default=None, min_length=1, max_length=80)
    valor: float | None = Field(default=None, ge=0.01, le=100_000_000)
    data: str | None = None
    forma_pagamento: str | None = Field(default=None, max_length=40)
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator("descricao", "categoria", "forma_pagamento")
    @classmethod
    def _strip_opt_text(cls, v: str | None) -> str | None:
        return _validate_optional_text(v)

    @field_validator("valor")
    @classmethod
    def _v_valor(cls, v: float | None) -> float | None:
        return _validate_positive_money(v) if v is not None else None

    @field_validator("data")
    @classmethod
    def _v_data(cls, v: str | None) -> str | None:
        return _validate_iso_date(v) if v else None


# ---------------------------------------------------------------------------
# Contas a Vencer (Fixas & Parceladas)
# ---------------------------------------------------------------------------
class ContaCreateRequest(BaseModel):
    nome: str = Field(..., min_length=1, max_length=160)
    categoria: str = Field(default="Contas Fixas", min_length=1, max_length=80)
    tipo: Literal["fixa", "parcelada"] = "fixa"
    valor: float = Field(..., ge=0.01, le=100_000_000)
    dia_vencimento: int = Field(..., ge=1, le=31)
    competencia_inicio: str | None = None
    parcelas_total: int | None = Field(default=None, ge=1, le=480)
    cor_hex: str = "#C9A45C"
    observacao: str = Field(default="", max_length=500)

    @field_validator("nome", "categoria")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return _validate_required_text(v)

    @field_validator("valor")
    @classmethod
    def _v_valor(cls, v: float) -> float:
        return _validate_positive_money(v)

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str) -> str:
        return _validate_hex(v)

    @field_validator("competencia_inicio")
    @classmethod
    def _v_comp(cls, v: str | None) -> str | None:
        return _validate_competencia(v) if v else None


class ContaUpdateRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=160)
    categoria: str | None = Field(default=None, min_length=1, max_length=80)
    tipo: Literal["fixa", "parcelada"] | None = None
    valor: float | None = Field(default=None, ge=0.01, le=100_000_000)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    competencia_inicio: str | None = None
    parcelas_total: int | None = Field(default=None, ge=1, le=480)
    cor_hex: str | None = None
    observacao: str | None = Field(default=None, max_length=500)
    ativo: bool | None = None

    @field_validator("nome", "categoria")
    @classmethod
    def _strip_opt_text(cls, v: str | None) -> str | None:
        return _validate_optional_text(v)

    @field_validator("valor")
    @classmethod
    def _v_valor(cls, v: float | None) -> float | None:
        return _validate_positive_money(v) if v is not None else None

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str | None) -> str | None:
        return _validate_hex(v) if v is not None else None

    @field_validator("competencia_inicio")
    @classmethod
    def _v_comp(cls, v: str | None) -> str | None:
        return _validate_competencia(v) if v is not None else None


class PagarMensalRequest(BaseModel):
    competencia: str
    lancar_no_caixa: bool = True
    valor_pago: float | None = Field(default=None, ge=0.01, le=100_000_000)
    data_pagamento: str | None = None
    forma_pagamento: str = Field(default="PIX", max_length=40)

    @field_validator("competencia")
    @classmethod
    def _v_comp(cls, v: str) -> str:
        return _validate_competencia(v)

    @field_validator("valor_pago")
    @classmethod
    def _v_vp(cls, v: float | None) -> float | None:
        return _validate_positive_money(v) if v is not None else None

    @field_validator("data_pagamento")
    @classmethod
    def _v_dp(cls, v: str | None) -> str | None:
        return _validate_iso_date(v) if v else None


# ---------------------------------------------------------------------------
# Meus Cartões de Crédito
# ---------------------------------------------------------------------------
class CartaoCreateRequest(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120)
    bandeira: str = Field(default="Black", max_length=40)
    ultimos_digitos: str = Field(default="", max_length=4)
    cor_hex: str = "#C9A45C"
    limite: float = Field(default=0, ge=0, le=100_000_000)
    dia_fechamento: int = Field(..., ge=1, le=31)
    dia_vencimento: int = Field(..., ge=1, le=31)

    @field_validator("nome")
    @classmethod
    def _v_nome(cls, v: str) -> str:
        return _validate_required_text(v)

    @field_validator("limite")
    @classmethod
    def _v_lim(cls, v: float) -> float:
        return _validate_non_negative_money(v)

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str) -> str:
        return _validate_hex(v)

    @field_validator("ultimos_digitos")
    @classmethod
    def _v_digits(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v or "")
        return digits[:4]


class CartaoUpdateRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    bandeira: str | None = Field(default=None, max_length=40)
    ultimos_digitos: str | None = Field(default=None, max_length=4)
    cor_hex: str | None = None
    limite: float | None = Field(default=None, ge=0, le=100_000_000)
    dia_fechamento: int | None = Field(default=None, ge=1, le=31)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def _v_nome(cls, v: str | None) -> str | None:
        return _validate_optional_text(v)

    @field_validator("limite")
    @classmethod
    def _v_lim(cls, v: float | None) -> float | None:
        return _validate_non_negative_money(v) if v is not None else None

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str | None) -> str | None:
        return _validate_hex(v) if v is not None else None

    @field_validator("ultimos_digitos")
    @classmethod
    def _v_digits(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return re.sub(r"\D", "", v)[:4]


class CompraCreateRequest(BaseModel):
    descricao: str = Field(..., min_length=1, max_length=180)
    categoria: str = Field(default="Compras", min_length=1, max_length=80)
    data_compra: str | None = None
    valor: float = Field(..., ge=0.01, le=100_000_000)
    modo_valor: Literal["total", "parcela"] = "total"
    parcelas_total: int = Field(default=1, ge=1, le=72)
    competencia_inicial: str | None = None
    observacao: str = Field(default="", max_length=500)

    @field_validator("descricao", "categoria")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        return _validate_required_text(v)

    @field_validator("valor")
    @classmethod
    def _v_valor(cls, v: float) -> float:
        return _validate_positive_money(v)

    @field_validator("data_compra")
    @classmethod
    def _v_dt(cls, v: str | None) -> str | None:
        return _validate_iso_date(v) if v else None

    @field_validator("competencia_inicial")
    @classmethod
    def _v_ci(cls, v: str | None) -> str | None:
        return _validate_competencia(v) if v else None


# ---------------------------------------------------------------------------
# Módulos de Dívida estilo "Cartão Virtual" (Thiago, Seu Luiz, etc.)
# ---------------------------------------------------------------------------
class ModuloDividaCreateRequest(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120)
    descricao: str = Field(default="", max_length=200)
    cor_hex: str = "#10B981"
    dia_fechamento: int = Field(..., ge=1, le=31)
    dia_vencimento: int = Field(..., ge=1, le=31)
    limite: float = Field(default=0, ge=0, le=100_000_000)

    @field_validator("nome")
    @classmethod
    def _v_nome(cls, v: str) -> str:
        return _validate_required_text(v)

    @field_validator("limite")
    @classmethod
    def _v_lim(cls, v: float) -> float:
        return _validate_non_negative_money(v)

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str) -> str:
        return _validate_hex(v)


class ModuloDividaUpdateRequest(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = Field(default=None, max_length=200)
    cor_hex: str | None = None
    dia_fechamento: int | None = Field(default=None, ge=1, le=31)
    dia_vencimento: int | None = Field(default=None, ge=1, le=31)
    limite: float | None = Field(default=None, ge=0, le=100_000_000)
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def _v_nome(cls, v: str | None) -> str | None:
        return _validate_optional_text(v)

    @field_validator("limite")
    @classmethod
    def _v_lim(cls, v: float | None) -> float | None:
        return _validate_non_negative_money(v) if v is not None else None

    @field_validator("cor_hex")
    @classmethod
    def _v_hex(cls, v: str | None) -> str | None:
        return _validate_hex(v) if v is not None else None


# ---------------------------------------------------------------------------
# Cofre Criptografado 24/7
# ---------------------------------------------------------------------------
class VaultHydrateRequest(BaseModel):
    hydrate_secret: str = Field(..., min_length=8)
    github_token: str = Field(..., min_length=10)
    repo: str = Field(..., min_length=3)
    aes_key: str = Field(..., min_length=32)
    branch: str = Field(default="main", min_length=1, max_length=60)
