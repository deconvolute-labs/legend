rule in_pan {
    meta:
        entity_type = "IN_PAN"
        confidence = "0.9"
    strings:
        // Indian PAN: AAAAA9999A (5 letters, 4 digits, 1 letter)
        $pan = /\b[A-Z]{5}[0-9]{4}[A-Z]\b/
    condition:
        $pan
}
