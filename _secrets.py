def get_embedded_credentials() -> tuple[str, str]:
    # Ofuscação binária via XOR (compilado em bytecode dentro do .exe; arquivo ignorado pelo Git)
    key = bytes([0x5A, 0x3C, 0x7F, 0x19, 0xA2, 0x4D, 0x88, 0xE1])
    u_enc = bytes([41, 83, 25, 109, 192, 63, 200, 146, 53, 90, 11, 123, 208, 99, 230, 132, 46])
    p_enc = bytes([31, 77, 26, 105, 199, 46, 224, 146, 107, 22])
    user = bytes(b ^ key[i % len(key)] for i, b in enumerate(u_enc)).decode("utf-8")
    pwd = bytes(b ^ key[i % len(key)] for i, b in enumerate(p_enc)).decode("utf-8")
    return user, pwd
