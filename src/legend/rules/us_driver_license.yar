rule us_driver_license {
    meta:
        entity_type = "US_DRIVER_LICENSE"
        confidence = "0.7"
    strings:
        // Generic US DL: 1-2 letters + 5-9 digits (covers most states)
        $dl_alpha_num = /\b[A-Z]{1,2}[0-9]{5,9}\b/
        // All-numeric DLs (e.g. NY, NJ): 9 digits
        $dl_numeric   = /\b[0-9]{9}\b/
        // Some states: 1 letter + 7 digits
        $dl_1alpha    = /\b[A-Z][0-9]{7}\b/
    condition:
        any of them
}
