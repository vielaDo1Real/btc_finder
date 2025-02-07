import logging
import time
import multiprocessing
import string
import unicodedata
import sys, os


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
