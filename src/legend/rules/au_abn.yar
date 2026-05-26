rule au_abn {
    meta:
        entity_type = "AU_ABN"
        confidence = "0.8"
    strings:
        // Australian Business Number: 11 digits, often formatted as XX XXX XXX XXX
        $abn_spaced = /\b[0-9]{2}\s[0-9]{3}\s[0-9]{3}\s[0-9]{3}\b/
        $abn_raw    = /\b[0-9]{11}\b/
    condition:
        any of them
}
