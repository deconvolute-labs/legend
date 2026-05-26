rule au_tfn {
    meta:
        entity_type = "AU_TFN"
        confidence = "0.75"
    strings:
        // Australian Tax File Number: 8 or 9 digits, sometimes with spaces
        $tfn_8  = /\b[0-9]{8}\b/
        $tfn_9  = /\b[0-9]{9}\b/
        $tfn_sp = /\b[0-9]{3}\s[0-9]{3}\s[0-9]{2,3}\b/
    condition:
        any of them
}
