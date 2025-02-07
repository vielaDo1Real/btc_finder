import sys
import os
import logging
import concurrent.futures
import threading
import time

from mongo_main import MongoMain
from bip39_v1 import Bip39V
from hex_v3 import HexV
from btc_find_utils import BtcFindUtils
from interact_pool import InteractPool

# Constantes para as opções do menu
HEX_FINDER = '1'
BIP39_FINDER = '2'
INTERACT_POOL = '3'

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

btc_utils = BtcFindUtils()


def clear_screen():
    os.system('cls')

def get_int_input(prompt, min_value=None, max_value=None):
    while True:
        try:
            value = int(input(prompt))
            if (min_value is not None and value < min_value) or (max_value is not None and value > max_value):
                print(f"Por favor, insira um valor entre {min_value} e {max_value}.")
            else:
                return value
        except ValueError:
            print("Entrada inválida. Por favor, insira um número inteiro.")

def hex_finder_menu():
    hex_finder = HexV()
    db = MongoMain('hex')
    database_insert = input("Armazenar no banco de dados [s/n]: ").strip().lower() == 's'
    
    if database_insert:
        attempted_keys = db.load_attempted_keys()
        last_tested_key = db.load_state() or hex_finder.start_key_int
        if last_tested_key:
            hex_finder.start_key_int = int(last_tested_key)
            print(hex_finder.start_key_int)
    else:
        attempted_keys = None
        last_tested_key = hex_finder.start_key_hex

    available_cores = btc_utils.get_cpu_cores()
    
    option = input("Deseja apenas gerar as chaves (1), apenas verificar os endereços gerados (2): ")
    clear_screen()
    num_threads = get_int_input("Digite o limite de threads a serem utilizadas: ", min_value=1)
    
    if option == '2':
        hex_finder.verify_key(hex_finder.target_address, batch_size=100, num_threads=num_threads)
    else:
        if not database_insert:
            num_cores = get_int_input(f"Escolha a quantidade de cores (Máx: {available_cores}): ", min_value=1, max_value=available_cores)

        type_gen = input("Para geração sequencial (1) ou randômica (2)? Escolha: ").strip()

        clear_screen()
        if database_insert:
            start = hex_finder.start_key_int
            stop = hex_finder.stop_key_int
            lock = threading.Lock()
            if type_gen == '1':
                hex_finder.process_range_sequential(start, stop, attempted_keys, num_threads)
            else:
                hex_finder.process_range_random(start, stop, attempted_keys, num_threads)
        else:
            start = hex_finder.start_key_int
            stop = hex_finder.stop_key_int
            hex_finder.hex_run_multiprocessing(start, stop, num_cores)

def bip39_finder_menu():
    num_threads = get_int_input("Digite o limite de threads a serem utilizados: ", min_value=1)
    target_address = '1EciYvS7FFjSYfrWxsWYjGB8K9BobBfCXw'
    option = input("Deseja gerar chaves (1), verificar endereços (2) ou ambos (3)? Escolha: ")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            bip39_finder = Bip39V()
            db = MongoMain('bip39')
            if option in ['1', '3']:
                word_l = bip39_finder.bip39_words
                text_file = input('Escreva o nome do arquivo com o texto: ')
                word_text = word_l.load_wordlist(text_file)
                word_p = word_l.preprocess_text(word_text)
                word = word_l.find_possible_words(word_p, language="portuguese")

                num_words = get_int_input("Digite o número de palavras para gerar as combinações: ", min_value=12)
                if not num_words in [12, 24, 32]:
                    num_words = 12
                type_gen = 'sequence' if input("Geração sequencial (1) ou randômica (2)? ") == '1' else 'random'

                clear_screen()
                logging.info("Iniciando geração de combinações...\n")

                future_generate = executor.submit(bip39_finder.generate_combinations, word, num_words, num_threads, type_gen)
                if option == '3':
                    future_verify = executor.submit(bip39_finder.verify_seed, target_address, num_threads)
                    future_generate.result()
                    future_verify.result()
                else:
                    future_generate.result()

            elif option == '2':
                logging.info("Iniciando verificação de frases...\n")
                bip39_finder.verify_seed(target_address, num_threads)
            else:
                raise ValueError("Opção inválida. Escolha 1, 2 ou 3.")
        except KeyboardInterrupt:
            logging.warning("Execução interrompida pelo usuário.")
            executor.shutdown(wait=False)
            sys.exit(1)

def interact_pool_menu():
    interact_pool = InteractPool()
    db = MongoMain('pool')
    
    if not interact_pool.pool_token:
        interact_pool.pool_token = input("Insira seu token de mineração: ")
        
    interval = get_int_input("Digite o intervalo em segundos (60) : ", min_value=10)
    
    logging.info("Iniciando o processo...")

    try: 
        interact_pool.generate_and_send_keys()
    except KeyboardInterrupt:
        logging.info("Processo interrompido pelo usuário.")
        # Aqui podemos adicionar uma ação de limpeza ou finalização, se necessário.

def main():
    while True:
        clear_screen()
        option = input('Para Hex Finder, digite 1. Para Bip39 Finder, digite 2. Para interagir com a Pool, digite 3: ')
        
        if option == HEX_FINDER:
            hex_finder_menu()
        elif option == BIP39_FINDER:
            bip39_finder_menu()
        elif option == INTERACT_POOL:
            interact_pool_menu()
        else:
            print("Opção inválida. Escolha 1, 2 ou 3.")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Execução finalizada pelo usuário.")