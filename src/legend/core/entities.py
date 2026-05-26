from enum import StrEnum


class EntityType(StrEnum):
    """All supported PII entity types."""

    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    IBAN_CODE = "IBAN_CODE"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    US_SSN = "US_SSN"
    US_PASSPORT = "US_PASSPORT"
    US_DRIVER_LICENSE = "US_DRIVER_LICENSE"
    US_BANK_NUMBER = "US_BANK_NUMBER"
    US_ITIN = "US_ITIN"
    UK_NHS = "UK_NHS"
    AU_ABN = "AU_ABN"
    AU_ACN = "AU_ACN"
    AU_TFN = "AU_TFN"
    AU_MEDICARE = "AU_MEDICARE"
    IN_PAN = "IN_PAN"
    IN_AADHAAR = "IN_AADHAAR"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    DATE_TIME = "DATE_TIME"
    NRP = "NRP"
    CRYPTO = "CRYPTO"
    URL = "URL"
    MEDICAL_LICENSE = "MEDICAL_LICENSE"


class Boundary(StrEnum):
    """The four interception points in the agentic loop."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Detector(StrEnum):
    """Which detector produced a span."""

    YARA = "yara"
    SPACY = "spacy"
