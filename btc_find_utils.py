import logging
import time
import multiprocessing
import string
import unicodedata
import sys, os
import hashlib
import ecdsa
import base58
from hashlib import sha256


class BtcFindUtils:
    def __init__(self):
        pass
    
    @staticmethod
    def exec_time(start_time, mode):
        end_time = time.time()
        logging.info(f"Execution time: {end_time - start_time} seconds in {mode} mode")
    
    @staticmethod
    def get_cpu_cores():
        return multiprocessing.cpu_count()
    
    @staticmethod
    def normalize_combination(combo):
        return " ".join(sorted(set(combo)))
    
    @staticmethod
    def int_to_hex(value):
        return hex(value)[2:].zfill(64)
    
    @staticmethod
    def hex_to_int(hex_str):
        return int(hex_str, 16)
    
    @staticmethod
    def hex_to_decimal(hex_str):
        return int(hex_str, 16)
    
    @staticmethod
    def handle_exit(signal, frame):
        print("\nEncerrando... Aguarde.")
        sys.exit(0)

    @staticmethod
    def private_key_to_wif(private_key_hex):
        extended_key = b"\x80" + bytes.fromhex(private_key_hex)  # Adiciona prefixo 0x80
        first_sha256 = sha256(extended_key).digest()
        second_sha256 = sha256(first_sha256).digest()
        checksum = second_sha256[:4]  # Pegamos os primeiros 4 bytes como checksum
        return base58.b58encode(extended_key + checksum).decode()
    
    #
    @staticmethod
    def private_key_to_public_key_(private_key_hex):
        private_key_bytes = bytes.fromhex(private_key_hex)
        sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
        vk = sk.verifying_key
        public_key = b"\x04" + vk.to_string()  # Prefixo 0x04 indica chave não comprimida
        return public_key.hex()

    @staticmethod
    def private_key_to_public_key(private_key_hex, compressed=True):
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hex), curve=ecdsa.SECP256k1)
        vk = sk.verifying_key
        x = vk.to_string()[:32]
        y = vk.to_string()[32:]
        if compressed:
            prefix = b"\x02" if y[-1] % 2 == 0 else b"\x03"
            return (prefix + x).hex()
        return (b"\x04" + vk.to_string()).hex()


    @staticmethod
    def public_key_to_address(public_key_hex):
        public_key_bytes = bytes.fromhex(public_key_hex)

        sha256_hash = sha256(public_key_bytes).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256_hash)
        public_key_hash = ripemd160.digest()

        extended_key = b"\x00" + public_key_hash
        first_sha256 = sha256(extended_key).digest()
        second_sha256 = sha256(first_sha256).digest()
        checksum = second_sha256[:4]  # Pegamos os primeiros 4 bytes como checksum

        address = base58.b58encode(extended_key + checksum).decode()
        return address

class WordCompare:
    def __init__(self, word_list_language):
        # Inicializa os caminhos das wordlists
        self.wordlist = self.load_wordlist(f"bip39_{word_list_language}.txt")

    @staticmethod
    def load_wordlist(file_path):
        """Carrega uma wordlist BIP39 de um arquivo, tratando erros."""
        if not os.path.exists(file_path):
            logging.error(f"Arquivo {file_path} não encontrado.")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return [word.strip() for word in f.readlines()]
        except Exception as e:
            logging.error(f"Erro ao carregar wordlist {file_path}: {e}")
            return []
        
    @staticmethod
    def preprocess_text(text):
        if isinstance(text, list):
            text = ' '.join(text)
            
        text = text.lower().translate(str.maketrans('', '', string.punctuation))  # Remove pontuação e coloca em minúsculas
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode("utf-8")  # Remove acentos
        return [word.strip() for word in text.split() if word.strip()]


    def find_possible_words(self, text, language="english"):
        words_in_text = self.preprocess_text(text)
        found_words = set(word for word in words_in_text if word in self.wordlist)
        return list(found_words)
