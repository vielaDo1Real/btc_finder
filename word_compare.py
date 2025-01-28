import string

class WordCompare:
    def __init__(self, english_wordlist_path, portuguese_wordlist_path):
        # Inicializa os caminhos das wordlists
        self.english_wordlist = self.load_wordlist(english_wordlist_path)
        self.portuguese_wordlist = self.load_wordlist(portuguese_wordlist_path)

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
        if language == "english":
            return [word for word in words_in_text if word in self.english_wordlist]
        elif language == "portuguese":
            return [word for word in words_in_text if word in self.portuguese_wordlist]
        else:
            raise ValueError("Idioma inválido. Escolha 'english' ou 'portuguese'.")

# Caminhos para wordlists BIP39
english_wordlist_path = 'bip39_english.txt'  # Substitua pelo caminho correto
portuguese_wordlist_path = 'bip39_portuguese.txt'  # Substitua pelo caminho correto

# Instância da classe
word_compare = WordCompare(english_wordlist_path, portuguese_wordlist_path)

# Texto fornecido
text = ""

# Encontrar palavras correspondentes
english_matches = word_compare.find_possible_words(text, language="english")
portuguese_matches = word_compare.find_possible_words(text, language="portuguese")