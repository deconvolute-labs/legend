import logging
import random

from faker import Faker

from legend.constants import DEFAULT_LOCALE, FAKE_EMAIL_DOMAIN
from legend.core.entities import EntityType
from legend.replacement.generators.base import GeneratorBase

logger = logging.getLogger(__name__)


class PersonGenerator(GeneratorBase):
    """Generates fake person names using Faker.

    Args:
        locale: Faker locale string. Defaults to DEFAULT_LOCALE.
    """

    def __init__(self, locale: str = DEFAULT_LOCALE) -> None:
        self._faker = Faker(locale)

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake full name.

        Args:
            real_value: The normalized real name (unused for generation).
            entity_type: Must be EntityType.PERSON.
            **kwargs: Ignored in v0.

        Returns:
            A fake person name string.
        """
        return self._faker.name()


class EmailGenerator(GeneratorBase):
    """Generates fake email addresses with the reserved example.com domain."""

    def __init__(self) -> None:
        self._faker = Faker()

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake email address using the reserved example.com domain.

        Args:
            real_value: Unused; present to satisfy the GeneratorBase interface.
            entity_type: Must be EntityType.EMAIL_ADDRESS.
            **kwargs: In v1, person_pseudonym= may be passed to derive the
                local part from an existing PERSON pseudonym.

        Returns:
            A fake email string with a random local part and FAKE_EMAIL_DOMAIN.
        """
        local = self._faker.user_name()
        return f"{local}@{FAKE_EMAIL_DOMAIN}"


class CreditCardGenerator(GeneratorBase):
    """Generates fake credit card numbers preserving the card network prefix."""

    def __init__(self) -> None:
        self._faker = Faker()

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake credit card number matching the network of the real value.

        Args:
            real_value: The real card number (digits only or formatted).
            entity_type: Must be EntityType.CREDIT_CARD.
            **kwargs: Ignored.

        Returns:
            A fake card number with a valid Luhn checksum in XXXX-XXXX-XXXX-XXXX
            format (or XXXX-XXXXXX-XXXXX for Amex).
        """
        digits = "".join(c for c in real_value if c.isdigit())
        if digits.startswith("34") or digits.startswith("37"):
            return self._generate_amex()
        if digits.startswith("4"):
            return self._generate_visa()
        if digits[:2] in {"51", "52", "53", "54", "55"}:
            return self._generate_mastercard()
        # Default to Visa
        return self._generate_visa()

    def _luhn_check_digit(self, partial: str) -> str:
        digits = [int(d) for d in partial]
        digits.reverse()
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return str((10 - (total % 10)) % 10)

    def _generate_visa(self) -> str:
        partial = "4" + "".join(str(random.randint(0, 9)) for _ in range(14))
        check = self._luhn_check_digit(partial)
        n = partial + check
        return f"{n[:4]}-{n[4:8]}-{n[8:12]}-{n[12:]}"

    def _generate_mastercard(self) -> str:
        prefix = str(random.choice([51, 52, 53, 54, 55]))
        partial = prefix + "".join(str(random.randint(0, 9)) for _ in range(13))
        check = self._luhn_check_digit(partial)
        n = partial + check
        return f"{n[:4]}-{n[4:8]}-{n[8:12]}-{n[12:]}"

    def _generate_amex(self) -> str:
        prefix = random.choice(["34", "37"])
        partial = prefix + "".join(str(random.randint(0, 9)) for _ in range(12))
        check = self._luhn_check_digit(partial)
        n = partial + check
        return f"{n[:4]}-{n[4:10]}-{n[10:]}"


class PhoneGenerator(GeneratorBase):
    """Generates fake phone numbers preserving the country code prefix."""

    def __init__(self) -> None:
        self._faker = Faker()

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake phone number.

        Preserves the E.164 country code prefix if detected in the real value.
        Falls back to a generic faker phone number otherwise.

        Args:
            real_value: The real phone number.
            entity_type: Must be EntityType.PHONE_NUMBER.
            **kwargs: Ignored.

        Returns:
            A fake phone number string.
        """
        if real_value.startswith("+"):
            # Extract country code (1-3 digits after +)
            digits = "".join(c for c in real_value[1:] if c.isdigit())
            for length in (3, 2, 1):
                prefix = "+" + digits[:length]
                n_digits = 9 - length
                fake_local = "".join(str(random.randint(0, 9)) for _ in range(n_digits))
                return f"{prefix}-{fake_local[:3]}-{fake_local[3:6]}-{fake_local[6:]}"
        return self._faker.phone_number()


class IPGenerator(GeneratorBase):
    """Generates fake IP addresses preserving IPv4/IPv6 and public/private scope."""

    def __init__(self) -> None:
        self._faker = Faker()

    def generate(self, real_value: str, entity_type: EntityType, **kwargs: str) -> str:
        """Generate a fake IP address matching the family and scope of the real value.

        Args:
            real_value: The real IP address string.
            entity_type: Must be EntityType.IP_ADDRESS.
            **kwargs: Ignored.

        Returns:
            A fake IP address string.
        """
        if ":" in real_value:
            return self._faker.ipv6()
        if self._is_private_ipv4(real_value):
            return self._faker.ipv4_private()
        return self._faker.ipv4_public()

    def _is_private_ipv4(self, address: str) -> bool:
        parts = address.split(".")
        if len(parts) != 4:
            return False
        try:
            octets = [int(p) for p in parts]
        except ValueError:
            return False
        # 10.0.0.0/8
        if octets[0] == 10:
            return True
        # 172.16.0.0/12
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return True
        # 192.168.0.0/16
        if octets[0] == 192 and octets[1] == 168:
            return True
        return False
