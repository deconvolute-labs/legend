rule us_bank_number {
    meta:
        entity_type = "US_BANK_NUMBER"
        confidence = "0.7"
    strings:
        // US bank account numbers: 8-17 digits
        $bank = /\b[0-9]{8,17}\b/
    condition:
        $bank
}
