rule us_ssn {
    meta:
        entity_type = "US_SSN"
        confidence = "0.85"
    strings:
        // XXX-XX-XXXX; area 001-899 (not 000 or 666), group 01-99, serial 0001-9999
        $ssn = /[0-9]{3}-[0-9]{2}-[0-9]{4}/
    condition:
        $ssn
}
