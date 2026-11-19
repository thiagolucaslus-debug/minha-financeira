"""Cálculos exatos de datas, fuso BRT, meses curtos, ciclos de fechamento/vencimento e parcelas."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone

BRT_TZ = timezone(timedelta(hours=-3))
COMPETENCIA_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MESES_PT = (
    "",
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
)


def today_brt() -> date:
    return datetime.now(BRT_TZ).date()


def today_brt_iso() -> str:
    return today_brt().isoformat()


def current_competencia_brt() -> str:
    d = today_brt()
    return f"{d.year:04d}-{d.month:02d}"


def parse_competencia(comp: str) -> tuple[int, int]:
    cleaned = (comp or "").strip()
    if not COMPETENCIA_RE.match(cleaned):
        raise ValueError(f"Competência inválida (use YYYY-MM): {comp!r}")
    year_s, month_s = cleaned.split("-")
    return int(year_s), int(month_s)


def format_competencia(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def competencia_label(comp: str) -> str:
    y, m = parse_competencia(comp)
    return f"{MESES_PT[m]}/{str(y)[-2:]}"


def parse_iso_date(raw: str) -> date:
    cleaned = (raw or "").strip()
    if not ISO_DATE_RE.match(cleaned):
        raise ValueError(f"Data inválida (use YYYY-MM-DD): {raw!r}")
    return date.fromisoformat(cleaned)


def add_months(comp: str, delta: int) -> str:
    year, month = parse_competencia(comp)
    zero_based = (year * 12 + (month - 1)) + delta
    new_year, new_month0 = divmod(zero_based, 12)
    return format_competencia(new_year, new_month0 + 1)


def diff_months(comp_a: str, comp_b: str) -> int:
    """Retorna quantos meses `comp_a` está à frente de `comp_b`."""
    ya, ma = parse_competencia(comp_a)
    yb, mb = parse_competencia(comp_b)
    return (ya * 12 + (ma - 1)) - (yb * 12 + (mb - 1))


def clamp_day(year: int, month: int, day: int) -> date:
    """Ajusta automaticamente dias 29/30/31 em meses curtos (ex.: fev -> 28/29)."""
    last_day = calendar.monthrange(year, month)[1]
    safe_day = max(1, min(int(day), last_day))
    return date(year, month, safe_day)


def due_date_for_competencia(comp: str, dia_vencimento: int) -> date:
    year, month = parse_competencia(comp)
    return clamp_day(year, month, dia_vencimento)


def closing_date_for_competencia(comp: str, dia_fechamento: int, dia_vencimento: int) -> date:
    """
    Calcula a data de fechamento da fatura que vence na `comp` informada:
    - Se vencimento > fechamento (ex.: fecha dia 10, vence dia 17): fecha no mesmo mês `comp`.
    - Se vencimento <= fechamento (ex.: fecha dia 25, vence dia 05): fecha no mês anterior `comp - 1`.
    """
    if dia_vencimento > dia_fechamento:
        y, m = parse_competencia(comp)
        return clamp_day(y, m, dia_fechamento)
    prev_comp = add_months(comp, -1)
    y, m = parse_competencia(prev_comp)
    return clamp_day(y, m, dia_fechamento)


def first_billing_competencia(
    data_compra: str | date,
    dia_fechamento: int,
    dia_vencimento: int,
) -> str:
    """
    Determina a competência (mês de VENCIMENTO da 1ª fatura) para uma compra feita em `data_compra`.
    - Exemplo 1: fecha dia 10, vence dia 17.
      - Compra dia 08/05 -> fecha 10/05 -> vence 17/05 -> `2026-05`.
      - Compra dia 11/05 -> fecha 10/06 -> vence 17/06 -> `2026-06`.
    - Exemplo 2: fecha dia 25, vence dia 05.
      - Compra dia 20/05 -> fecha 25/05 -> vence 05/06 -> `2026-06`.
      - Compra dia 26/05 -> fecha 25/06 -> vence 05/07 -> `2026-07`.
    """
    dt = parse_iso_date(data_compra) if isinstance(data_compra, str) else data_compra
    comp_compra = format_competencia(dt.year, dt.month)
    closing_day_in_month = clamp_day(dt.year, dt.month, dia_fechamento).day
    month_shift = 0 if dt.day <= closing_day_in_month else 1
    if dia_vencimento <= dia_fechamento:
        month_shift += 1
    return add_months(comp_compra, month_shift)


def split_installment_centavos(total_centavos: int, parcelas_total: int) -> list[int]:
    """Divide `total_centavos` em `parcelas_total` parcelas exatas sem perda de centavos."""
    n = max(1, int(parcelas_total))
    total = int(total_centavos)
    base, remainder = divmod(total, n)
    return [base + (1 if idx < remainder else 0) for idx in range(n)]


def installment_value_for_index(total_centavos: int, parcelas_total: int, zero_idx: int) -> int:
    n = max(1, int(parcelas_total))
    base, remainder = divmod(int(total_centavos), n)
    return base + (1 if zero_idx < remainder else 0)


def brl_to_centavos(valor: float) -> int:
    return int(round(float(valor) * 100))


def centavos_to_brl(centavos: int) -> float:
    return round(int(centavos) / 100.0, 2)
