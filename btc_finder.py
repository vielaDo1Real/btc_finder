import sys
import os
import logging
import concurrent.futures

from word_compare import WordCompare
from mongo_main import MongoMain
from bip39_v1 import Bip39V
from hex_v3 import HexV
from btc_find_utils import BtcFindUtils

btc_utils = BtcFindUtils()
db = MongoMain('hex')
last_state = ''
# Função principal
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    option = input('Para Hex Finder, digite 1. Para Bip39 Finder, digite 2: ')
    if option == '1':
        hex_finder = HexV()
        attempted_keys = db.load_attempted_keys()
        state = db.load_state()
        last_tested_key = db.load_state()
        if last_tested_key is None:
            last_tested_key = hex_finder.start_key_hex
        available_cores = btc_utils.get_cpu_cores()
        option = input("Deseja apenas gerar as chaves (1), apenas verificar os endereços gerados (2): ")
        os.system("cls")
        if option == '2':
            option = '1'
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_verify = executor.submit(hex_finder.verify_key, hex_finder.target_address)
                future_verify.result()
        else:
            cores = int(input(f"Escolha a quantidade de cores (Cores disponíveis: {available_cores}):"))
            if cores <= 1 or cores > available_cores:
                cores = 1
            processes = []
            range_size = (hex_finder.stop_key_int - hex_finder.start_key_int + 1) // cores
            type_gen = input("Para geração sequencial (1) ou (2) para randômico? Escolha: ")
            os.system("cls")
            for i in range(cores):
                start = hex_finder.start_key_int + i * range_size
                stop = min(hex_finder.start_key_int + (i + 1) * range_size - 1, hex_finder.stop_key_int)
                if type_gen == '1':
                    hex_finder.process_range_sequential(start=start, stop=stop, attempted_keys=attempted_keys)
                else:
                    hex_finder.process_range_random(start=start, stop=stop, attempted_keys=attempted_keys)
            
    elif option == '2':
        
        target_address = '1EciYvS7FFjSYfrWxsWYjGB8K9BobBfCXw'
        option = input("Deseja apenas gerar as chaves (1), apenas verificar os endereços gerados (2) ou gerar e verificar (3)? Escolha: ")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            try:
                bip39_finder = Bip39V()
                if option == '1':
                    word_l = WordCompare('bip39_english.txt', 'bip39_portuguese.txt')
                    text_file = input('Escreva o nome do arquivo com o texto: ')
                    word_text = word_l.load_wordlist(text_file)
                    word_p = word_l.preprocess_text(word_text)
                    word = word_l.find_possible_words(word_p, language="portuguese")
                    num_words = int(input("Digite o número de palavras para gerar as combinações: "))
                    type_gen = input("Para geração sequencial (1) ou (2) para randômico? Escolha: ")
                    if type_gen == '1':
                        type_gen = 'sequence'
                    else:
                        type_gen = 'random'
                    os.system("cls")
                    logging.info("Iniciando geração de combinações...\n")
                    if type_gen == 'sequence':
                        future_generate = executor.submit(bip39_finder.generate_combinations, word, num_words)
                        future_generate.result()
                    elif type_gen == 'random':
                        future_generate = executor.submit(bip39_finder.generate_random_combinations, word, num_words)
                        future_generate.result()
                elif option == '2':
                    logging.info("Iniciando verificação de frases...\n")
                    future_verify = executor.submit(bip39_finder.verify_seed, target_address)
                    future_verify.result()
                elif option == '3':
                    logging.info("Iniciando geração de combinações e verificação em paralelo...\n")
                    if type_gen == 'sequence':
                        future_generate = executor.submit(bip39_finder.generate_combinations, word, num_words)
                        future_verify = executor.submit(bip39_finder.verify_seed, target_address)
                        future_generate.result()
                        future_verify.result()
                    elif type_gen == 'random':
                        future_generate = executor.submit(bip39_finder.generate_random_combinations, word, num_words)
                        future_verify = executor.submit(bip39_finder.verify_seed, target_address)
                        future_generate.result()
                        future_verify.result()
                else:
                    raise ValueError("Opção inválida. Escolha 1, 2 ou 3.")
            except KeyboardInterrupt:
                logging.warning("Execução interrompida pelo usuário.")
                executor.shutdown(wait=False)
                sys.exit(1)
        
        if option != '2':
            word_l = WordCompare('bip39_english.txt', 'bip39_portuguese.txt')
            text_file = input('Write the file name: ')
            word_text = word_l.load_wordlist(text_file)
            word_p = word_l.preprocess_text(word_text)
            word = word_l.find_possible_words(word_p, language="portuguese")
            num_words = int(input("Digite o número de palavras para gerar as combinações: "))
            os.system('cls')
            if option != '2':
                type_gen = input("Para geração sequencial (1) ou (2) para randômico? Escolha: ")
                if type_gen == '1':
                    type_gen = 'sequence'
                elif type_gen == '2':
                    type_gen = 'random'
            os.system('cls')
    else:
        raise ValueError("Opção inválida. Escolha 1 ou 2.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Execução finalizada pelo usuário.")