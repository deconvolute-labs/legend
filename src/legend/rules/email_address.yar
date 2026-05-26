rule email_address {
    meta:
        entity_type = "EMAIL_ADDRESS"
        confidence = "0.9"
    strings:
        $email = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/
    condition:
        $email
}
