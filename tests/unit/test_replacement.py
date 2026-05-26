import string
from unittest.mock import MagicMock

import pytest

from legend.constants import FAKE_EMAIL_DOMAIN
from legend.core.entities import Boundary, Detector, EntityType
from legend.core.models import DetectedSpan, EntityMapEntry, PseudonymEvent
from legend.entity_map.memory import InMemoryEntityMap
from legend.exceptions import ReplacementError
from legend.observability.emitter import (
    ENTITY_MAP_HIT,
    PSEUDONYM_CREATED,
    EventEmitter,
)
from legend.replacement.engine import (
    ReplacementEngine,
    _faker_generate,
    _generate_variants,
    _normalize,
)
from legend.replacement.generators.base import GeneratorBase
from legend.replacement.generators.faker_generators import (
    CreditCardGenerator,
    EmailGenerator,
    IPGenerator,
    PersonGenerator,
    PhoneGenerator,
)
from legend.replacement.generators.format_preserving import (
    PassportGenerator,
    SSNGenerator,
)
from legend.replacement.generators.iban import (
    IBANGenerator,
    _compute_check_digits,
    _letter_to_num,
)

# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_email_lowercases() -> None:
    assert (
        _normalize("User@EXAMPLE.COM", EntityType.EMAIL_ADDRESS) == "user@example.com"
    )


def test_normalize_iban_uppercases_and_strips_spaces() -> None:
    assert _normalize("de89 3704 0044", EntityType.IBAN_CODE) == "DE8937040044"


def test_normalize_person_title_cases_and_strips_whitespace() -> None:
    assert _normalize("  john smith  ", EntityType.PERSON) == "John Smith"


def test_normalize_location_title_cases() -> None:
    assert _normalize("new york", EntityType.LOCATION) == "New York"


def test_normalize_organization_title_cases() -> None:
    assert _normalize("acme corp", EntityType.ORGANIZATION) == "Acme Corp"


def test_normalize_phone_keeps_digits_and_plus_only() -> None:
    assert _normalize("+1 (555) 867-5309", EntityType.PHONE_NUMBER) == "+15558675309"


def test_normalize_phone_strips_dashes_parens_spaces() -> None:
    assert _normalize("(800) 555-0100", EntityType.PHONE_NUMBER) == "8005550100"


def test_normalize_other_strips_leading_trailing_whitespace() -> None:
    assert _normalize("  123-45-6789  ", EntityType.US_SSN) == "123-45-6789"


def test_normalize_other_does_not_change_case() -> None:
    assert _normalize("  ABC-DEF  ", EntityType.CREDIT_CARD) == "ABC-DEF"


# ---------------------------------------------------------------------------
# _generate_variants
# ---------------------------------------------------------------------------


def test_variants_person_two_part_name_includes_lower_upper_first_last() -> None:
    variants = _generate_variants("Jan Jansen", EntityType.PERSON)
    assert "jan jansen" in variants
    assert "JAN JANSEN" in variants
    assert "Jan" in variants
    assert "Jansen" in variants


def test_variants_person_one_part_name_no_split() -> None:
    variants = _generate_variants("Madonna", EntityType.PERSON)
    assert "madonna" in variants
    assert "MADONNA" in variants
    # No first/last name split for single-word names
    assert variants.count("Madonna") == 1


def test_variants_email_includes_lower_and_upper() -> None:
    variants = _generate_variants("User@Example.com", EntityType.EMAIL_ADDRESS)
    assert "user@example.com" in variants
    assert "USER@EXAMPLE.COM" in variants


def test_variants_iban_includes_compact_and_grouped() -> None:
    fake = "DE89370400440532013000"
    variants = _generate_variants(fake, EntityType.IBAN_CODE)
    assert "DE89370400440532013000" in variants
    assert "DE89 3704 0044 0532 0130 00" in variants


def test_variants_credit_card_16_digits_includes_dash_and_space_formats() -> None:
    fake = "4111-1111-1111-1111"
    variants = _generate_variants(fake, EntityType.CREDIT_CARD)
    assert "4111111111111111" in variants
    assert "4111-1111-1111-1111" in variants
    assert "4111 1111 1111 1111" in variants


def test_variants_credit_card_15_digits_amex_includes_dash_and_space_formats() -> None:
    fake = "3714-496353-98431"
    variants = _generate_variants(fake, EntityType.CREDIT_CARD)
    digits = "371449635398431"
    assert digits in variants
    assert f"{digits[:4]}-{digits[4:10]}-{digits[10:]}" in variants
    assert f"{digits[:4]} {digits[4:10]} {digits[10:]}" in variants


def test_variants_phone_includes_digits_only_spaced_hyphenated() -> None:
    fake = "+31-123-456-789"
    variants = _generate_variants(fake, EntityType.PHONE_NUMBER)
    assert "31123456789" in variants
    # spaced variant: replace - with space
    assert "+31 123 456 789" in variants
    # hyphenated: replace space with -
    assert "+31-123-456-789" in variants


def test_variants_ssn_9_digits_includes_plain_and_formatted() -> None:
    fake = "123-45-6789"
    variants = _generate_variants(fake, EntityType.US_SSN)
    assert "123456789" in variants
    assert "123-45-6789" in variants


def test_variants_ssn_non_9_digits_no_extra_formatted_variant() -> None:
    fake = "12-34"
    variants = _generate_variants(fake, EntityType.US_SSN)
    assert "1234" in variants
    # No XXX-XX-XXXX because digit count is not 9
    for v in variants:
        if "-" in v:
            assert v == fake  # only the original formatted value is preserved


def test_variants_passport_includes_lowercase() -> None:
    fake = "A12345678"
    variants = _generate_variants(fake, EntityType.US_PASSPORT)
    assert "a12345678" in variants


def test_variants_other_type_includes_stripped() -> None:
    fake = "  192.168.0.1  "
    variants = _generate_variants(fake, EntityType.IP_ADDRESS)
    assert "192.168.0.1" in variants


def test_variants_deduplicates_identical_results() -> None:
    # If fake.lower() == fake (already lowercase), no dup
    fake = "jan jansen"
    variants = _generate_variants(fake, EntityType.PERSON)
    assert len(variants) == len(set(variants))


# ---------------------------------------------------------------------------
# _faker_generate
# ---------------------------------------------------------------------------


def test_faker_generate_location_returns_nonempty() -> None:
    result = _faker_generate(EntityType.LOCATION)
    assert isinstance(result, str)
    assert len(result) > 0


def test_faker_generate_organization_returns_nonempty() -> None:
    result = _faker_generate(EntityType.ORGANIZATION)
    assert isinstance(result, str)
    assert len(result) > 0


def test_faker_generate_nrp_returns_nonempty() -> None:
    result = _faker_generate(EntityType.NRP)
    assert isinstance(result, str)
    assert len(result) > 0


def test_faker_generate_url_returns_nonempty() -> None:
    result = _faker_generate(EntityType.URL)
    assert isinstance(result, str)
    assert len(result) > 0


def test_faker_generate_crypto_starts_with_0x_and_length_42() -> None:
    result = _faker_generate(EntityType.CRYPTO)
    assert result.startswith("0x")
    assert len(result) == 42


def test_faker_generate_unknown_type_returns_nonempty() -> None:
    result = _faker_generate(EntityType.MEDICAL_LICENSE)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# ReplacementEngine — constructor
# ---------------------------------------------------------------------------


def test_custom_generator_overrides_default_for_entity_type() -> None:
    mock_gen = MagicMock(spec=GeneratorBase)
    mock_gen.generate.return_value = "CustomFake"
    engine = ReplacementEngine(custom_generators={"PERSON": mock_gen})
    from legend.core.entities import EntityType

    assert engine._registry[EntityType.PERSON] is mock_gen


def test_unknown_entity_type_in_custom_generators_logs_warning_no_crash() -> None:
    mock_gen = MagicMock(spec=GeneratorBase)
    engine = ReplacementEngine(custom_generators={"NOT_A_TYPE": mock_gen})
    assert engine is not None  # No exception raised


# ---------------------------------------------------------------------------
# ReplacementEngine.replace — helpers
# ---------------------------------------------------------------------------


def _make_span(
    text: str,
    start: int,
    end: int,
    entity_type: EntityType,
    confidence: float = 0.9,
    detector: Detector = Detector.YARA,
) -> DetectedSpan:
    return DetectedSpan(
        text=text,
        start=start,
        end=end,
        entity_type=entity_type,
        confidence=confidence,
        detector=detector,
    )


def _capture_emitter() -> tuple[EventEmitter, list[PseudonymEvent]]:
    events: list[PseudonymEvent] = []
    e = EventEmitter()
    e.subscribe(lambda ev: events.append(ev))
    return e, events


# ---------------------------------------------------------------------------
# ReplacementEngine.replace — async tests
# ---------------------------------------------------------------------------


async def test_replace_empty_spans_returns_original_unchanged() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    result = await engine.replace([], "Hello World", em, "sid", Boundary.A, emitter)
    assert result == "Hello World"


async def test_replace_new_value_creates_entity_map_entry() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    span = _make_span("123-45-6789", 0, 11, EntityType.US_SSN)
    await engine.replace([span], "123-45-6789", em, "sid", Boundary.A, emitter)
    fake = await em.get_fake("123-45-6789")
    assert fake is not None
    assert fake != "123-45-6789"


async def test_replace_new_value_substitutes_text_correctly() -> None:
    mock_gen = MagicMock(spec=GeneratorBase)
    mock_gen.generate.return_value = "999-88-7777"
    engine = ReplacementEngine(custom_generators={"US_SSN": mock_gen})
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    span = _make_span("123-45-6789", 7, 18, EntityType.US_SSN)
    result = await engine.replace(
        [span], "My SSN 123-45-6789 here", em, "sid", Boundary.A, emitter
    )
    assert result == "My SSN 999-88-7777 here"


async def test_replace_new_value_emits_pseudonym_created_event() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, events = _capture_emitter()
    span = _make_span("123-45-6789", 0, 11, EntityType.US_SSN)
    await engine.replace([span], "123-45-6789", em, "sid", Boundary.A, emitter)
    created = [e for e in events if e.event_type == PSEUDONYM_CREATED]
    assert len(created) == 1
    assert created[0].entity_type == EntityType.US_SSN


async def test_replace_forward_hit_reuses_fake_value() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()

    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen", "jan jansen"],
    )
    await em.put(entry)

    span = _make_span("John Smith", 6, 16, EntityType.PERSON)
    result = await engine.replace(
        [span], "Hello John Smith!", em, "sid", Boundary.A, emitter
    )
    assert result == "Hello Jan Jansen!"


async def test_replace_forward_hit_emits_entity_map_hit_event() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, events = _capture_emitter()

    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen"],
    )
    await em.put(entry)

    span = _make_span("John Smith", 0, 10, EntityType.PERSON)
    await engine.replace([span], "John Smith", em, "sid", Boundary.A, emitter)
    hits = [e for e in events if e.event_type == ENTITY_MAP_HIT]
    assert len(hits) == 1
    assert hits[0].fake_value == "Jan Jansen"


async def test_replace_reverse_hit_already_a_fake_skips_span() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, events = _capture_emitter()

    entry = EntityMapEntry(
        real_normalized="John Smith",
        real_original="John Smith",
        fake="Jan Jansen",
        entity_type=EntityType.PERSON,
        variants=["Jan Jansen", "jan jansen"],
    )
    await em.put(entry)

    # Span covering a known fake value — should be skipped
    span = _make_span("Jan Jansen", 0, 10, EntityType.PERSON)
    result = await engine.replace(
        [span], "Jan Jansen is here", em, "sid", Boundary.A, emitter
    )
    assert result == "Jan Jansen is here"
    # No PSEUDONYM_CREATED or ENTITY_MAP_HIT events
    assert not any(e.event_type in (PSEUDONYM_CREATED, ENTITY_MAP_HIT) for e in events)


async def test_replace_date_time_passes_through_unchanged() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    span = _make_span("Monday", 8, 14, EntityType.DATE_TIME, detector=Detector.SPACY)
    result = await engine.replace(
        [span], "Meeting Monday afternoon", em, "sid", Boundary.A, emitter
    )
    assert result == "Meeting Monday afternoon"


async def test_replace_generator_raises_wraps_in_replacement_error() -> None:
    mock_gen = MagicMock(spec=GeneratorBase)
    mock_gen.generate.side_effect = ValueError("generator broken")
    engine = ReplacementEngine(custom_generators={"PERSON": mock_gen})
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    span = _make_span("John Smith", 0, 10, EntityType.PERSON)
    with pytest.raises(ReplacementError, match="generator broken"):
        await engine.replace([span], "John Smith", em, "sid", Boundary.A, emitter)


async def test_replace_no_registered_generator_uses_faker_fallback() -> None:
    engine = ReplacementEngine()
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()
    # LOCATION has no registered generator → falls back to _faker_generate
    span = _make_span("London", 11, 17, EntityType.LOCATION, detector=Detector.SPACY)
    result = await engine.replace(
        [span], "Located in London today", em, "sid", Boundary.A, emitter
    )
    assert "London" not in result


async def test_replace_multiple_spans_applied_right_to_left_preserves_offsets() -> None:
    mock_person = MagicMock(spec=GeneratorBase)
    mock_person.generate.return_value = "Longfakename Here"
    mock_email = MagicMock(spec=GeneratorBase)
    mock_email.generate.return_value = "fake@example.com"
    engine = ReplacementEngine(
        custom_generators={"PERSON": mock_person, "EMAIL_ADDRESS": mock_email}
    )
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()

    # "Alice" at [3,8], "bob@work.com" at [16,28]
    text = "Hi Alice, email bob@work.com now"
    spans = [
        _make_span("Alice", 3, 8, EntityType.PERSON),
        _make_span("bob@work.com", 16, 28, EntityType.EMAIL_ADDRESS),
    ]
    result = await engine.replace(spans, text, em, "sid", Boundary.A, emitter)
    assert "Alice" not in result
    assert "bob@work.com" not in result
    assert "Longfakename Here" in result
    assert "fake@example.com" in result


async def test_replace_adjacent_non_overlapping_spans_both_replaced() -> None:
    mock_ssn = MagicMock(spec=GeneratorBase)
    mock_ssn.generate.return_value = "999-00-1234"
    mock_email = MagicMock(spec=GeneratorBase)
    mock_email.generate.return_value = "x@example.com"
    engine = ReplacementEngine(
        custom_generators={"US_SSN": mock_ssn, "EMAIL_ADDRESS": mock_email}
    )
    em = InMemoryEntityMap()
    emitter, _ = _capture_emitter()

    text = "123-45-6789 user@test.com"
    spans = [
        _make_span("123-45-6789", 0, 11, EntityType.US_SSN),
        _make_span("user@test.com", 12, 25, EntityType.EMAIL_ADDRESS),
    ]
    result = await engine.replace(spans, text, em, "sid", Boundary.A, emitter)
    assert "123-45-6789" not in result
    assert "user@test.com" not in result


# ---------------------------------------------------------------------------
# PersonGenerator
# ---------------------------------------------------------------------------


def test_person_generator_returns_nonempty_string() -> None:
    gen = PersonGenerator()
    result = gen.generate("John Smith", EntityType.PERSON)
    assert isinstance(result, str)
    assert len(result) > 0


def test_person_generator_custom_locale_accepted() -> None:
    gen = PersonGenerator(locale="en_US")
    result = gen.generate("John Smith", EntityType.PERSON)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# EmailGenerator
# ---------------------------------------------------------------------------


def test_email_generator_uses_fake_email_domain() -> None:
    gen = EmailGenerator()
    result = gen.generate("real@work.com", EntityType.EMAIL_ADDRESS)
    assert result.endswith(f"@{FAKE_EMAIL_DOMAIN}")


def test_email_generator_format_contains_at_symbol() -> None:
    gen = EmailGenerator()
    result = gen.generate("real@work.com", EntityType.EMAIL_ADDRESS)
    assert "@" in result
    local, domain = result.split("@", 1)
    assert len(local) > 0
    assert domain == FAKE_EMAIL_DOMAIN


# ---------------------------------------------------------------------------
# CreditCardGenerator
# ---------------------------------------------------------------------------


def _luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    digits.reverse()
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def test_credit_card_generator_visa_prefix_4() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("4111111111111111", EntityType.CREDIT_CARD)
    digits = result.replace("-", "")
    assert digits.startswith("4")


def test_credit_card_generator_mastercard_prefix_51_through_55() -> None:
    gen = CreditCardGenerator()
    for prefix in ["5111", "5211", "5311", "5411", "5511"]:
        result = gen.generate(prefix + "0" * 12, EntityType.CREDIT_CARD)
        digits = result.replace("-", "")
        assert digits[:2] in {"51", "52", "53", "54", "55"}


def test_credit_card_generator_amex_prefix_34() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("341234567890123", EntityType.CREDIT_CARD)
    digits = result.replace("-", "")
    assert digits.startswith("34") or digits.startswith("37")


def test_credit_card_generator_amex_prefix_37() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("371234567890123", EntityType.CREDIT_CARD)
    digits = result.replace("-", "")
    assert digits.startswith("34") or digits.startswith("37")


def test_credit_card_generator_unknown_prefix_defaults_to_visa() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("6011111111111117", EntityType.CREDIT_CARD)
    digits = result.replace("-", "")
    assert digits.startswith("4")


def test_credit_card_generator_visa_luhn_checksum_valid() -> None:
    gen = CreditCardGenerator()
    for _ in range(10):
        result = gen.generate("4111111111111111", EntityType.CREDIT_CARD)
        assert _luhn_valid(result), f"Invalid Luhn: {result}"


def test_credit_card_generator_visa_format_xxxx_xxxx_xxxx_xxxx() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("4111111111111111", EntityType.CREDIT_CARD)
    parts = result.split("-")
    assert len(parts) == 4
    assert all(len(p) == 4 for p in parts)


def test_credit_card_generator_amex_format_xxxx_xxxxxx_xxxxx() -> None:
    gen = CreditCardGenerator()
    result = gen.generate("341234567890123", EntityType.CREDIT_CARD)
    parts = result.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4
    assert len(parts[1]) == 6
    assert len(parts[2]) == 5


def test_luhn_check_digit_known_value() -> None:
    # 4111111111111110 → check digit should be 1 → final = 4111111111111111
    gen = CreditCardGenerator()
    check = gen._luhn_check_digit("411111111111111")
    assert check == "1"


# ---------------------------------------------------------------------------
# PhoneGenerator
# ---------------------------------------------------------------------------


def test_phone_generator_e164_extracts_three_digit_prefix() -> None:
    # The generator always tries the 3-digit extraction first and returns.
    gen = PhoneGenerator()
    result = gen.generate("+12025551234", EntityType.PHONE_NUMBER)
    # First 3 digits after '+' are "120"
    assert result.startswith("+120-")


def test_phone_generator_e164_different_prefix() -> None:
    gen = PhoneGenerator()
    result = gen.generate("+44712345678", EntityType.PHONE_NUMBER)
    # First 3 digits after '+' are "447"
    assert result.startswith("+447-")


def test_phone_generator_e164_short_number_still_starts_with_plus() -> None:
    gen = PhoneGenerator()
    result = gen.generate("+31612", EntityType.PHONE_NUMBER)
    assert result.startswith("+")


def test_phone_generator_no_plus_falls_back_to_faker() -> None:
    gen = PhoneGenerator()
    result = gen.generate("5551234567", EntityType.PHONE_NUMBER)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# IPGenerator
# ---------------------------------------------------------------------------


def test_ip_generator_ipv6_input_returns_ipv6_output() -> None:
    gen = IPGenerator()
    result = gen.generate("2001:db8::1", EntityType.IP_ADDRESS)
    assert ":" in result


def test_ip_generator_private_10_returns_private() -> None:
    gen = IPGenerator()
    result = gen.generate("10.0.0.1", EntityType.IP_ADDRESS)
    # Should return a private IP (starts with 10., 172.16-31., or 192.168.)
    assert (
        result.startswith("10.")
        or result.startswith("192.168.")
        or any(result.startswith(f"172.{i}.") for i in range(16, 32))
    )


def test_ip_generator_private_172_16_returns_private() -> None:
    gen = IPGenerator()
    result = gen.generate("172.16.0.1", EntityType.IP_ADDRESS)
    assert (
        result.startswith("10.")
        or result.startswith("192.168.")
        or any(result.startswith(f"172.{i}.") for i in range(16, 32))
    )


def test_ip_generator_private_192_168_returns_private() -> None:
    gen = IPGenerator()
    result = gen.generate("192.168.1.100", EntityType.IP_ADDRESS)
    assert (
        result.startswith("10.")
        or result.startswith("192.168.")
        or any(result.startswith(f"172.{i}.") for i in range(16, 32))
    )


def test_ip_generator_public_returns_public() -> None:
    gen = IPGenerator()
    result = gen.generate("8.8.8.8", EntityType.IP_ADDRESS)
    # Should be a public address (not private)
    assert ":" not in result  # IPv4
    parts = result.split(".")
    assert len(parts) == 4


def test_ip_generator_is_private_10_x_x_x() -> None:
    gen = IPGenerator()
    assert gen._is_private_ipv4("10.0.0.1") is True
    assert gen._is_private_ipv4("10.255.255.255") is True


def test_ip_generator_is_private_172_16_to_31() -> None:
    gen = IPGenerator()
    assert gen._is_private_ipv4("172.16.0.1") is True
    assert gen._is_private_ipv4("172.31.255.255") is True


def test_ip_generator_is_private_172_15_not_private() -> None:
    gen = IPGenerator()
    assert gen._is_private_ipv4("172.15.0.1") is False
    assert gen._is_private_ipv4("172.32.0.1") is False


def test_ip_generator_is_private_192_168_x_x() -> None:
    gen = IPGenerator()
    assert gen._is_private_ipv4("192.168.0.1") is True
    assert gen._is_private_ipv4("192.168.255.255") is True


def test_ip_generator_is_private_malformed_returns_false() -> None:
    gen = IPGenerator()
    assert gen._is_private_ipv4("not.an.ip") is False
    assert gen._is_private_ipv4("10.0.0") is False
    assert gen._is_private_ipv4("10.0.0.abc") is False


# ---------------------------------------------------------------------------
# SSNGenerator
# ---------------------------------------------------------------------------


def test_ssn_generator_output_format_xxx_xx_xxxx() -> None:
    gen = SSNGenerator()
    result = gen.generate("", EntityType.US_SSN)
    parts = result.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 3
    assert len(parts[1]) == 2
    assert len(parts[2]) == 4
    assert all(p.isdigit() for p in parts)


def test_ssn_generator_area_never_000() -> None:
    gen = SSNGenerator()
    for _ in range(50):
        result = gen.generate("", EntityType.US_SSN)
        assert not result.startswith("000-")


def test_ssn_generator_area_never_666() -> None:
    gen = SSNGenerator()
    for _ in range(50):
        result = gen.generate("", EntityType.US_SSN)
        assert not result.startswith("666-")


def test_ssn_generator_area_never_900_to_999() -> None:
    gen = SSNGenerator()
    for _ in range(50):
        result = gen.generate("", EntityType.US_SSN)
        area = int(result.split("-")[0])
        assert area < 900


# ---------------------------------------------------------------------------
# PassportGenerator
# ---------------------------------------------------------------------------


def test_passport_generator_first_char_is_uppercase_letter() -> None:
    gen = PassportGenerator()
    for _ in range(20):
        result = gen.generate("", EntityType.US_PASSPORT)
        assert result[0] in string.ascii_uppercase


def test_passport_generator_remaining_8_chars_are_digits() -> None:
    gen = PassportGenerator()
    for _ in range(20):
        result = gen.generate("", EntityType.US_PASSPORT)
        assert len(result) == 9
        assert result[1:].isdigit()


# ---------------------------------------------------------------------------
# IBANGenerator
# ---------------------------------------------------------------------------


def test_iban_generator_preserves_country_code_from_real_iban() -> None:
    gen = IBANGenerator()
    result = gen.generate("GB29NWBK60161331926819", EntityType.IBAN_CODE)
    assert result.startswith("GB")


def test_iban_generator_valid_mod97_check_digits() -> None:
    gen = IBANGenerator()
    for _ in range(10):
        iban = gen.generate("DE89370400440532013000", EntityType.IBAN_CODE)
        # Rearrange: move first 4 chars (CC + check digits) to the end
        rearranged = iban[4:] + iban[:4]
        numeric = "".join(
            str(ord(c) - ord("A") + 10) if c.isalpha() else c for c in rearranged
        )
        assert int(numeric) % 97 == 1, f"Invalid MOD-97 for IBAN: {iban}"


def test_iban_generator_unknown_country_uses_default_bban_length() -> None:
    gen = IBANGenerator()
    # "XX" is not in _BBAN_LENGTHS → defaults to 20
    result = gen.generate("XX00" + "A" * 20, EntityType.IBAN_CODE)
    # Length should be 2 (CC) + 2 (check) + 20 (default BBAN) = 24
    assert len(result) == 24


def test_iban_generator_empty_input_defaults_to_de() -> None:
    gen = IBANGenerator()
    result = gen.generate("", EntityType.IBAN_CODE)
    assert result.startswith("DE")


def test_letter_to_num_a_equals_10() -> None:
    assert _letter_to_num("A") == "10"


def test_letter_to_num_z_equals_35() -> None:
    assert _letter_to_num("Z") == "35"


def test_compute_check_digits_two_digit_string() -> None:
    result = _compute_check_digits("DE", "370400440532013000")
    assert len(result) == 2
    assert result.isdigit()
