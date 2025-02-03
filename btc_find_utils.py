import logging
import time
import multiprocessing
import string


class BtcFindUtils:
    def __init__(self):
        pass
    
    # calculate the execution time
    def exec_time(self, start_time, mode):
        end_time = time.time()
        logging.info(f"Execution time: {end_time - start_time} seconds in {mode} mode")
    
    # get the number of CPU cores
    def get_cpu_cores(self):
        return multiprocessing.cpu_count()
    
    # organize the combination words
    def normalize_combination(self, combo):
        return " ".join(sorted(set(combo)))

    def int_to_hex(self, value):
        return hex(value)[2:].zfill(64)


class WordCompare:
    def __init__(self, word_list_language):
        # Inicializa os caminhos das wordlists
        self.wordlist = self.load_wordlist(f"bip39_{word_list_language}.txt")

    @staticmethod
    def load_wordlist(file_path):
        """Carrega uma wordlist BIP39 de um arquivo."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return [word.strip() for word in f.readlines()]

    @staticmethod
    def preprocess_text(text):
        if type(text) == list:
            text = ' '.join(text)
        """Pré-processa o texto para remover pontuação e normalizar palavras."""
        translator = str.maketrans('', '', string.punctuation)  # Remove pontuação
        words = text.translate(translator).lower().split()  # Converte para minúsculas e divide em palavras
        words = [word.strip() for word in words if word.strip()]  # Remove palavras vazias
        return words

    def find_possible_words(self, text, language="english"):
        if type(text) == list:
            words_in_text = ' '.join(text)
        words_in_text = self.preprocess_text(text)
        return [word for word in words_in_text if word in self.wordlist]
