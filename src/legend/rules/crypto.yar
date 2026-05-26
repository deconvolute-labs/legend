rule crypto {
    meta:
        entity_type = "CRYPTO"
        confidence = "0.85"
    strings:
        // Bitcoin P2PKH/P2SH: base58, 25-34 chars, starts with 1 or 3
        $btc = /\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b/
        // Bitcoin bech32 (native SegWit): bc1 prefix
        $btc_bech32 = /\bbc1[a-z0-9]{6,87}\b/
        // Ethereum: 0x + 40 hex chars
        $eth = /\b0x[0-9a-fA-F]{40}\b/
    condition:
        any of them
}
