rule phone_number {
    meta:
        entity_type = "PHONE_NUMBER"
        confidence = "0.75"
    strings:
        // E.164: +CC followed by 7-14 digits
        $e164 = /\+[1-9][0-9]{6,14}/
        // North American: (NXX) NXX-XXXX or NXX-NXX-XXXX
        $nanp = /(\([2-9][0-9]{2}\)\s?|[2-9][0-9]{2}[-.\s])[2-9][0-9]{2}[-.\s][0-9]{4}/
        // European-style with spaces or dots, at least 8 digits
        $eu = /\+[1-9][0-9]{0,2}[\s.\-][0-9]{2,4}([\s.\-][0-9]{2,4}){2,4}/
    condition:
        any of them
}
