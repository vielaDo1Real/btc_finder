import itertools
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
import logging
import random
from tqdm import tqdm
from pymongo import MongoClient, UpdateOne, ASCENDING
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from btc_find_utils import BtcFindUtils
from  mongo_main import MongoMain

client = MongoClient('localhost', 27017)
db = client['bip39']
attempts_collection = db['bip39_attempts']
verified_collection = db['bip39_verified']


class Bip39V:
    def __init__(self):
        self.db = MongoMain('bip39')
        self.utils = BtcFindUtils()
        self.attempted_combinations = set()
        # Inicializa as combinações tentadas
        try:
            logging.info("Aguarde... Carregando banco de dados.")
            self.attempted_combinations = self.db.load_objects('attempts')
            if not self.attempted_combinations:
                self.attempted_combinations = set()  # Caso o banco retorne None ou vazio
        except Exception as e:
            logging.warning(f"Erro ao carregar 'attempts' do banco de dados: {e}")
            self.attempted_combinations = set()  # Garante que seja um set mesmo em caso de erro
        
        # Inicializa as combinações verificadas
        try:
            self.verified_combinations = self.db.load_objects('verified')
            if not self.verified_combinations:
                self.verified_combinations = []
        except Exception as e:
            logging.warning(f"Erro ao carregar 'verified' do banco de dados: {e}")
            self.verified_combinations = []

    def process_combination_seq(self, combo):
        if combo not in self.attempted_combinations:
            try:
                normalized = self.utils.normalize_combination(combo)
                seed = Bip39SeedGenerator(normalized).Generate()
                bip44 = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
                address = bip44.PublicKey().ToAddress()
                try:
                    self.db.log_attempt('null', normalized, address, 'not found', False, 'insert')
                    self.attempted_combinations.append(normalized)
                except Exception as e:
                    logging.warning(f"Combinação duplicada ignorada: {normalized}")
            except Exception as e:
                self.db.log_attempt('null', normalized, "Bip39SeedGenerator", 'error', False, 'insert') # Insere as combinações que deram erro para aumentar a base de combinações já geradas
                pass

    # Gerar combinações únicas
    def generate_combinations(self, words, num_words):
        words = list(set(words))  # Deduplicate input words
        total_combinations = itertools.combinations(words, num_words)
        try:
            with ThreadPoolExecutor() as executor:
                futures = []
                for combo in tqdm(total_combinations, desc="Gerando combinações", unit=" frases"):
                    future = executor.submit(self.process_combination_seq, combo)
                    if future.result():
                        futures.append(future)
        except Exception as e:
            logging.error(f"Erro ao gerar combinações: {e}")
            pass

    def process_combination(self, combo):
        if combo not in self.attempted_combinations:
            try:
                seed = Bip39SeedGenerator(combo).Generate()
                bip44 = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
                address = bip44.PublicKey().ToAddress()
                try:
                    self.db.log_attempt('null', combo, address, 'not found', False, 'insert')
                    self.attempted_combinations.append(combo)
                    return True
                except Exception as e:
                    logging.warning(f"Combinação duplicada ignorada: {combo}")
                    return False  # Retorna False se houve uma exceção ao registrar a tentativa
            except Exception as e:
                self.db.log_attempt('null', combo, "Bip39SeedGenerator", 'error', False, 'insert') # Insere as combinações que deram erro para aumentar a base de combinações já geradas
                pass
                return False  # Retorna False se houve uma exceção ao gerar o endereço
        return False  # Retorna False se a combinação já foi tentada

    def generate_random_combinations(self, words, num_words):
        words = list(set(words))
        total_combinations = itertools.combinations(words, num_words)
        try:
            # Use ThreadPoolExecutor para processar as combinações em paralelo
            with ThreadPoolExecutor() as executor:
                # Crie uma lista para as tarefas
                futures = []
                
                # Para cada combinação, envie para execução paralela
                for combo in tqdm(total_combinations, desc="Gerando combinações aleatórias", unit=" frases"):
                    combo_str = " ".join(random.sample(combo, num_words))  # Combinação como string, embaralhando palavras da combinação 
                    future = executor.submit(self.process_combination, combo_str)
                    if future.result():
                        futures.append(future)
        except Exception as e:
            logging.error(f"Erro ao gerar combinações: {e}")
            pass    
                
    def verify_seed(self, target_address, batch_size=100, num_threads=1):
        try:
            start_time = time.time()

            # Define número de threads baseado no número de CPUs disponíveis
            if num_threads is None:
                num_threads = self.utils.get_cpu_cores()

            # Garantir que exista um índice no campo 'is_verified' para acelerar as consultas
            self.db.attempts_collection.create_index([("is_verified", ASCENDING)], background=True)


            # Busca apenas documentos não verificados, sem carregar tudo em memória
            cursor = self.db.attempts_collection.find({"is_verified": False, "status": {"$ne": "error"}}).batch_size(batch_size)

            # Inicializa tqdm com o total de documentos não verificados
            total_docs = self.db.attempts_collection.count_documents({"is_verified": False, "status": {"$ne": "error"}})
            lock = Lock()

            # Função para processar um lote de dados
            def process_batch(batch):
                updates = []
                for doc in batch:
                    combination = doc['combination']
                    address = doc['address']
                    updates.append({
                        'filter': {'_id': doc['_id']},
                        'update': {
                            '$set': {
                                'priv_key_hex': 'null',
                                'phrase': combination,
                                'address': address,
                                'status': 'found' if address == target_address else 'not found',
                                'is_verified': True
                            }
                        }
                    })

                # Atualização em lote no MongoDB
                if updates:
                    attempts_collection.bulk_write(
                        [UpdateOne(u['filter'], u['update']) for u in updates]
                    )
                
                # Atualiza a barra de progresso
                with lock:
                    pbar.update(len(batch))

            # Dividindo o cursor em lotes e processando em paralelo
            with tqdm(total=total_docs, desc="Verificando endereços", unit=" combinações") as pbar:
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    batch = []
                    for doc in cursor:
                        batch.append(doc)
                        if len(batch) >= batch_size:
                            executor.submit(process_batch, batch)
                            batch = []
                    # Processa o último lote, se houver
                    if batch:
                        executor.submit(process_batch, batch)
                
                executor.shutdown(wait=True)

            logging.info("Nenhum endereço correspondente encontrado.")
            self.utils.exec_time(start_time=start_time, mode='Verify')
            return "Nenhum endereço correspondente encontrado."

        except Exception as e:
            logging.error(f"Erro ao verificar endereços: {e}")
            return f"Erro: {e}"
