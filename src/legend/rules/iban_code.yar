rule iban_code {
    meta:
        entity_type = "IBAN_CODE"
        confidence = "0.9"
    strings:
        // IBAN: known country code + 2 check digits + 10-30 alphanumeric BBAN
        // Country codes restricted to the ~75 known IBAN-issuing countries (ISO 13616-1)
        // Optionally space-separated in groups of 4
        $iban_compact = /\b(AD|AE|AL|AT|AZ|BA|BE|BG|BH|BR|CH|CR|CY|CZ|DE|DK|DO|EE|EG|ES|FI|FO|FR|GB|GE|GI|GL|GR|GT|HR|HU|IE|IL|IQ|IS|IT|JO|KW|KZ|LB|LC|LI|LT|LU|LV|MC|MD|ME|MK|MR|MT|MU|NL|NO|PK|PL|PS|PT|QA|RO|RS|SA|SC|SE|SI|SK|SM|ST|TL|TN|TR|UA|VA|VG|XK)[0-9]{2}[A-Z0-9]{10,30}\b/
        $iban_spaced  = /\b(AD|AE|AL|AT|AZ|BA|BE|BG|BH|BR|CH|CR|CY|CZ|DE|DK|DO|EE|EG|ES|FI|FO|FR|GB|GE|GI|GL|GR|GT|HR|HU|IE|IL|IQ|IS|IT|JO|KW|KZ|LB|LC|LI|LT|LU|LV|MC|MD|ME|MK|MR|MT|MU|NL|NO|PK|PL|PS|PT|QA|RO|RS|SA|SC|SE|SI|SK|SM|ST|TL|TN|TR|UA|VA|VG|XK)[0-9]{2}(\s[A-Z0-9]{4}){2,7}\b/
    condition:
        any of them
}
