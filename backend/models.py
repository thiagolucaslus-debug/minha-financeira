"""Modelos relacionais do sistema Minha Financeira — estritamente isolados por usuario_id."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tema_preferido: Mapped[str] = mapped_column(String(16), default="dark", nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class CaixaLancamento(Base):
    __tablename__ = "caixa_lancamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)  # "entrada" | "saida"
    descricao: Mapped[str] = mapped_column(String(180), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="Geral")
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    forma_pagamento: Mapped[str] = mapped_column(String(40), nullable=False, default="PIX")
    observacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origem_tipo: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual"
    )  # manual | conta | cartao | modulo_divida
    origem_ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_caixa_user_data", "usuario_id", "data"),)


class ContaVencer(Base):
    __tablename__ = "contas_vencer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="Moradia")
    tipo: Mapped[str] = mapped_column(String(16), nullable=False, default="fixa")  # fixa | parcelada
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    dia_vencimento: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..31
    competencia_inicio: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    competencia_fim: Mapped[str | None] = mapped_column(String(7), nullable=True)  # YYYY-MM opcional
    parcelas_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cor_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#C9A45C")
    observacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    pagamentos: Mapped[list["ContaPagamento"]] = relationship(
        "ContaPagamento", back_populates="conta", cascade="all, delete-orphan"
    )


class ContaPagamento(Base):
    __tablename__ = "conta_pagamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conta_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contas_vencer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    valor_pago_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    data_pagamento: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    caixa_lancamento_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("caixa_lancamentos.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    conta: Mapped["ContaVencer"] = relationship("ContaVencer", back_populates="pagamentos")

    __table_args__ = (
        UniqueConstraint("conta_id", "competencia", name="uq_conta_pagamento_competencia"),
    )


class Cartao(Base):
    __tablename__ = "cartoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    bandeira: Mapped[str] = mapped_column(String(40), nullable=False, default="Black")
    ultimos_digitos: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    cor_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#C9A45C")
    limite_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dia_fechamento: Mapped[int] = mapped_column(Integer, nullable=False)
    dia_vencimento: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    compras: Mapped[list["CartaoCompra"]] = relationship(
        "CartaoCompra", back_populates="cartao", cascade="all, delete-orphan"
    )
    pagamentos: Mapped[list["CartaoFaturaPagamento"]] = relationship(
        "CartaoFaturaPagamento", back_populates="cartao", cascade="all, delete-orphan"
    )


class CartaoCompra(Base):
    __tablename__ = "cartao_compras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cartao_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cartoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descricao: Mapped[str] = mapped_column(String(180), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="Compras")
    data_compra: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    valor_total_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    parcelas_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    competencia_inicial: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    observacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    cartao: Mapped["Cartao"] = relationship("Cartao", back_populates="compras")


class CartaoFaturaPagamento(Base):
    __tablename__ = "cartao_fatura_pagamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cartao_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cartoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    valor_pago_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    data_pagamento: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    caixa_lancamento_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("caixa_lancamentos.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    cartao: Mapped["Cartao"] = relationship("Cartao", back_populates="pagamentos")

    __table_args__ = (
        UniqueConstraint("cartao_id", "competencia", name="uq_cartao_fatura_competencia"),
    )


class ModuloDivida(Base):
    __tablename__ = "modulos_divida"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    cor_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#10B981")
    dia_fechamento: Mapped[int] = mapped_column(Integer, nullable=False)
    dia_vencimento: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    compras: Mapped[list["ModuloCompra"]] = relationship(
        "ModuloCompra", back_populates="modulo", cascade="all, delete-orphan"
    )
    pagamentos: Mapped[list["ModuloFaturaPagamento"]] = relationship(
        "ModuloFaturaPagamento", back_populates="modulo", cascade="all, delete-orphan"
    )


class ModuloCompra(Base):
    __tablename__ = "modulo_compras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modulo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modulos_divida.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descricao: Mapped[str] = mapped_column(String(180), nullable=False)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, default="Dívidas")
    data_compra: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    valor_total_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    parcelas_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    competencia_inicial: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    observacao: Mapped[str] = mapped_column(Text, nullable=False, default="")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    modulo: Mapped["ModuloDivida"] = relationship("ModuloDivida", back_populates="compras")


class ModuloFaturaPagamento(Base):
    __tablename__ = "modulo_fatura_pagamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modulo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("modulos_divida.id", ondelete="CASCADE"), nullable=False, index=True
    )
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    valor_pago_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    data_pagamento: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    caixa_lancamento_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("caixa_lancamentos.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    modulo: Mapped["ModuloDivida"] = relationship("ModuloDivida", back_populates="pagamentos")

    __table_args__ = (
        UniqueConstraint("modulo_id", "competencia", name="uq_modulo_fatura_competencia"),
    )
