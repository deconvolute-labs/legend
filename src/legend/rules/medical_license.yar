rule medical_license {
    meta:
        entity_type = "MEDICAL_LICENSE"
        confidence = "0.7"
    strings:
        // Generic medical license: 2-letter state code + 5-8 alphanumeric chars
        $med_lic = /\b[A-Z]{2}[0-9A-Z]{5,8}\b/
        // NPI: 10 digits starting with 1 or 2
        $npi     = /\b[12][0-9]{9}\b/
        // DEA number: 2 letters + 7 digits
        $dea     = /\b[A-Z]{2}[0-9]{7}\b/
    condition:
        any of them
}
