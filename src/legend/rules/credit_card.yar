rule credit_card {
    meta:
        entity_type = "CREDIT_CARD"
        confidence = "0.85"
    strings:
        // Visa/Mastercard/Discover: 16 digits in groups
        $cc16_dash  = /[3-6][0-9]{3}[-\s][0-9]{4}[-\s][0-9]{4}[-\s][0-9]{4}/
        // American Express: 15 digits 4-6-5 groups
        $amex_dash  = /3[47][0-9]{2}[-\s][0-9]{6}[-\s][0-9]{5}/
        // Raw 16-digit Visa/MC (no separator) — restricted prefixes to reduce FP
        $visa_raw   = /4[0-9]{15}/
        $mc_raw     = /5[1-5][0-9]{14}/
    condition:
        any of them
}
