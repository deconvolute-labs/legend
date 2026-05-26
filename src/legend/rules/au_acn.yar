rule au_acn {
    meta:
        entity_type = "AU_ACN"
        confidence = "0.75"
    strings:
        // Australian Company Number: 9 digits, often formatted as XXX XXX XXX
        $acn_spaced = /\b[0-9]{3}\s[0-9]{3}\s[0-9]{3}\b/
        $acn_raw    = /\b[0-9]{9}\b/
    condition:
        any of them
}
