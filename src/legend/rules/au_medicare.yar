rule au_medicare {
    meta:
        entity_type = "AU_MEDICARE"
        confidence = "0.8"
    strings:
        // Medicare card number: 10 digits + optional IRN digit (total 10-11)
        $medicare_spaced = /\b[2-6][0-9]{3}\s[0-9]{5}\s[0-9]{1,2}\b/
        $medicare_raw    = /\b[2-6][0-9]{9,10}\b/
    condition:
        any of them
}
