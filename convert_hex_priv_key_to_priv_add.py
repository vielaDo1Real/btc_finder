import hashlib

def hex_to_wif(hex_private_key, compressed=True):
    # Remove espaços e aspas acidentais que venham do terminal
    hex_key = hex_private_key.strip().replace('"', '').replace("'", "").zfill(64)
    
    # 1. Adiciona o prefixo de rede (0x80 para a rede principal do Bitcoin)
    prefix_byte = b'\x80'
    key_bytes = bytes.fromhex(hex_key)
    extended_key = prefix_byte + key_bytes
    
    # 2. Se for para endereços comprimidos (padrão), adiciona o sufixo 0x01
    if compressed:
        extended_key += b'\x01'
        
    # 3. Calcula o Checksum (SHA256 duplo)
    first_sha = hashlib.sha256(extended_key).digest()
    second_sha = hashlib.sha256(first_sha).digest()
    checksum = second_sha[:4]
    
    # 4. Junta a chave estendida com o checksum
    final_key_bytes = extended_key + checksum
    
    # 5. Codifica em Base58 (CORRIGIDO: usando int padrão do Python)
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    value = int(final_key_bytes.hex(), 16)
    
    wif = ""
    while value > 0:
        value, mod = divmod(value, 58)
        wif = alphabet[mod] + wif
        
    # Trata bytes zero iniciais na codificação Base58
    for byte in final_key_bytes:
        if byte == 0:
            wif = alphabet[0] + wif
        else:
            break
            
    return wif

# Execução interativa no terminal
if __name__ == "__main__":
    hex_btx = input("Digite a chave privada hexadecimal: ")

    try:
        wif_compressed = hex_to_wif(hex_btx, compressed=True)
        wif_uncompressed = hex_to_wif(hex_btx, compressed=False)

        print("\n" + "="*60)
        print(f"WIF Comprimida (Recomendada): {wif_compressed}")
        print(f"WIF Não-Comprimida:           {wif_uncompressed}")
        print("="*60)
    except ValueError as e:
        print(f"\n❌ Erro: Certifique-se de que digitou um valor hexadecimal válido de 64 caracteres. Detalhes: {e}")
