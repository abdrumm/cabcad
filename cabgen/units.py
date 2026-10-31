"""Inch formatting the way the shop writes it."""

from __future__ import annotations

from fractions import Fraction

SIXTEENTHS = Fraction(1, 16)


def to_frac(x: float) -> Fraction:
    """Snap to the nearest 1/16 and return an exact Fraction."""
    f = Fraction(x).limit_denominator(64)
    # snap to 1/16
    return Fraction(round(f * 16), 16)


def fmt_in(x: float, denom: int = 16) -> str:
    """27.0 -> '27"', 13.9375 -> '13 15/16"', 0.75 -> '3/4"'."""
    f = Fraction(x).limit_denominator(64)
    f = Fraction(round(f * denom), denom)
    whole = f.numerator // f.denominator
    rem = f - whole
    if rem == 0:
        return f'{whole}"'
    if whole == 0:
        return f'{_frac_str(rem)}"'
    return f'{whole} {_frac_str(rem)}"'


def fmt_in_plain(x: float, denom: int = 16) -> str:
    """Same as fmt_in without the inch mark."""
    return fmt_in(x, denom).replace('"', "")


def _frac_str(f: Fraction) -> str:
    if f.denominator == 1:
        return str(f.numerator)
    whole = f.numerator // f.denominator
    rem = f - whole
    if whole and rem:
        return f"{whole} {rem.numerator}/{rem.denominator}"
    if whole:
        return f"{whole}"
    return f"{f.numerator}/{f.denominator}"


def parse_in(text: str) -> float:
    """Parse '27', '27.5', '13 15/16', '13-15/16' into inches."""
    t = str(text).strip().replace('"', "").replace("in", "").strip()
    if not t:
        raise ValueError("empty value")
    if "-" in t and "/" not in t.split("-")[0]:
        whole, _, rest = t.partition("-")
        return float(whole) + parse_in(rest)
    if " " in t:
        whole, _, rest = t.partition(" ")
        return float(whole) + parse_in(rest)
    if "/" in t:
        num, _, den = t.partition("/")
        return float(Fraction(int(num), int(den)))
    return float(t)
