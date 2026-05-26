rule us_passport {
    meta:
        entity_type = "US_PASSPORT"
        confidence = "0.8"
    strings:
        // One uppercase letter followed by exactly 8 digits
        $passport = /\b[A-Z][0-9]{8}\b/
    condition:
        $passport
}
