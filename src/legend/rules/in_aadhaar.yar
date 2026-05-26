rule in_aadhaar {
    meta:
        entity_type = "IN_AADHAAR"
        confidence = "0.8"
    strings:
        // Aadhaar: 12 digits, often formatted as XXXX XXXX XXXX
        $aadhaar_spaced = /\b[2-9][0-9]{3}\s[0-9]{4}\s[0-9]{4}\b/
        $aadhaar_raw    = /\b[2-9][0-9]{11}\b/
    condition:
        any of them
}
