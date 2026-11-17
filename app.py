import re


def normalize_dtc(cod: str) -> str:
    if not cod:
        return ""

    cod = cod.strip().upper()
    cod = re.sub(r"\s+", "", cod)

    return cod


def valideaza_dtc(cod: str) -> bool:
    cod = normalize_dtc(cod)

    return bool(re.fullmatch(r"[PBCU][0-9A-F]{4}", cod))
