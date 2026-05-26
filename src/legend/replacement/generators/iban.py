import random
import string

from legend.core.entities import EntityType
from legend.replacement.generators.base import GeneratorBase

# BBAN length per country code (total IBAN length minus 4 for CC+check digits).
# Source: ISO 13616-1. Defaults to 20 for unlisted countries.
_BBAN_LENGTHS: dict[str, int] = {
    "AL": 24,
    "AD": 20,
    "AT": 16,
    "AZ": 24,
    "BH": 18,
    "BE": 12,
    "BA": 16,
    "BR": 25,
    "BG": 18,
    "CR": 18,
    "HR": 17,
    "CY": 24,
    "CZ": 20,
    "DK": 14,
    "DO": 24,
    "EE": 16,
    "EG": 25,
    "FO": 14,
    "FI": 14,
    "FR": 23,
    "GE": 18,
    "DE": 18,
    "GI": 19,
    "GR": 23,
    "GL": 14,
    "GT": 24,
    "HU": 24,
    "IS": 22,
    "IQ": 19,
    "IE": 18,
    "IL": 19,
    "IT": 23,
    "JO": 26,
    "KZ": 16,
    "XK": 16,
    "KW": 26,
    "LV": 17,
    "LB": 24,
    "LI": 17,
    "LT": 16,
    "LU": 16,
    "MT": 27,
    "MR": 23,
    "MU": 26,
    "MD": 20,
    "MC": 23,
    "ME": 18,
    "NL": 14,
    "MK": 15,
    "NO": 11,
    "PK": 20,
    "PS": 25,
    "PL": 24,
    "PT": 21,
    "QA": 25,
    "RO": 20,
    "LC": 28,
    "SM": 23,
    "ST": 21,
    "SA": 20,
    "RS": 18,
    "SC": 27,
    "SK": 20,
    "SI": 15,
    "ES": 20,
    "SE": 20,
    "CH": 17,
    "TL": 19,
    "TN": 20,
    "TR": 22,
    "UA": 25,
    "AE": 19,
    "GB": 18,
    "VA": 18,
    "VG": 20,
}

_DEFAULT_BBAN_LENGTH: int = 20
_BBAN_CHARS: str = string.digits + string.ascii_uppercase


def _letter_to_num(ch: str) -> str:
    """Convert a letter to its MOD-97 numeric equivalent (A=10, Z=35)."""
    return str(ord(ch) - ord("A") + 10)


def _compute_check_digits(country_code: str, bban: str) -> str:
    """Compute the two IBAN check digits using the MOD-97 algorithm.

    Args:
        country_code: Two-letter ISO country code.
        bban: The Basic Bank Account Number string.

    Returns:
        Two-digit check digit string (zero-padded).
    """
    rearranged = bban + country_code + "00"
    numeric_str = "".join(_letter_to_num(c) if c.isalpha() else c for c in rearranged)
    check = 98 - (int(numeric_str) % 97)
    return str(check).zfill(2)


class IBANGenerator(GeneratorBase):
    """Generates fake IBANs preserving the country code with a valid MOD-97 check."""

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake IBAN for the same country as the real value.

        Args:
            real_value: The real IBAN (normalized: uppercase, no spaces).
            entity_type: Must be EntityType.IBAN_CODE.
            **kwargs: Ignored.

        Returns:
            A fake IBAN with a valid MOD-97 check digit.
        """
        clean = real_value.replace(" ", "").upper()
        country_code = clean[:2] if len(clean) >= 2 else "DE"
        bban_length = _BBAN_LENGTHS.get(country_code, _DEFAULT_BBAN_LENGTH)
        bban = "".join(random.choices(_BBAN_CHARS, k=bban_length))
        check_digits = _compute_check_digits(country_code, bban)
        return f"{country_code}{check_digits}{bban}"
