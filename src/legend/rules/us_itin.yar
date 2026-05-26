rule us_itin {
    meta:
        entity_type = "US_ITIN"
        confidence = "0.85"
    strings:
        // ITIN: 9XX-7X-XXXX or 9XX-8X-XXXX (area 900-999, group 70-88 or 90-92 or 94-99)
        $itin = /\b9[0-9]{2}-(7[0-9]|8[0-8]|9[0-24-9])-[0-9]{4}\b/
    condition:
        $itin
}
