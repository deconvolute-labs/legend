rule uk_nhs {
    meta:
        entity_type = "UK_NHS"
        confidence = "0.8"
    strings:
        // NHS number: 10 digits, often formatted as NNN NNN NNNN or NNN-NNN-NNNN
        $nhs_spaced = /\b[0-9]{3}[\s\-][0-9]{3}[\s\-][0-9]{4}\b/
        $nhs_raw    = /\b[0-9]{10}\b/
    condition:
        any of them
}
