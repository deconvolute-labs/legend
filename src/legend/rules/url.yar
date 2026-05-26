rule url {
    meta:
        entity_type = "URL"
        confidence = "0.8"
    strings:
        // HTTP/HTTPS URLs
        $http  = /https?:\/\/[a-zA-Z0-9\-._~:\/?#\[\]@!$&'()*+,;=%]+/
        // FTP URLs
        $ftp   = /ftp:\/\/[a-zA-Z0-9\-._~:\/?#\[\]@!$&'()*+,;=%]+/
    condition:
        any of them
}
