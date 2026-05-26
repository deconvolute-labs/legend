rule ip_address {
    meta:
        entity_type = "IP_ADDRESS"
        confidence = "0.85"
    strings:
        // IPv4: four 0-255 octets
        $ipv4 = /\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/
        // IPv6: full or compressed form
        $ipv6_full = /[0-9a-fA-F]{1,4}(:[0-9a-fA-F]{1,4}){7}/
        $ipv6_compressed = /([0-9a-fA-F]{1,4}:){1,7}:/
        $ipv6_loopback = /::1/
    condition:
        any of them
}
