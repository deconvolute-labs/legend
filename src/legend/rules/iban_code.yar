rule iban_code {
    meta:
        entity_type = "IBAN_CODE"
        confidence = "0.9"
    strings:
        // IBAN: 2 letter country code + 2 check digits + 10-30 alphanumeric BBAN
        // Optionally space-separated in groups of 4
        $iban_compact = /[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}/
        $iban_spaced  = /[A-Z]{2}[0-9]{2}(\s[A-Z0-9]{4}){2,7}/
    condition:
        any of them
}
