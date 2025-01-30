import random
from bit import Key
import time
import logging
from tqdm import tqdm
from threading import Lock
from pymongo import ASCENDING, UpdateOne
from concurrent.futures import ThreadPoolExecutor

from mongo_main import MongoMain
from btc_find_utils import BtcFindUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Implementar lista de target address ao invés de endereço único
# Puzzle 67
class HexV():
    def __init__(self):
        self.start_key_hex = "0000000000000000000000000000000000000000000000040000000000000000"
        self.stop_key_hex = "000000000000000000000000000000000000000000000007ffffffffffffffff"
        self.target_address = '1BY8GQbnueYofwSuFAT3USAhGjPrkxDdW9'
        self.db = MongoMain('hex')
        self.start_key_int = int(self.start_key_hex, 16)
        self.state = [i for i in self.db.state_collection.find({})]
        if self.state == []:
            self.db.insert_state(self.start_key_int)
        else:
            self.start_key_int = int(self.state[0]['state'])
        self.stop_key_int = int(self.stop_key_hex, 16)
        self.state = ''
        self.utils = BtcFindUtils()

    def generate_random_hex(self, start, stop, attempted_keys):
        start_int = int(start, 16)
        stop_int = int(stop, 16)
        while True:
            random_int = random.randint(start_int, stop_int)
            random_hex = format(random_int, '064x')
            if random_hex not in attempted_keys:
                return random_hex

    def process_range_sequential(self, start, stop, attempted_keys):
        progress_bar = tqdm(total=None, desc="Gerando chaves privadas:", unit=" chaves")
        for key_int in range(start, stop + 1):
            priv_key_hex = self.utils.int_to_hex(key_int)
            if priv_key_hex in attempted_keys:
                continue
            key = Key.from_hex(priv_key_hex)
            btc_address = key.address
            self.db.log_attempt(
                priv_key_hex=priv_key_hex,
                phrase='null', 
                btc_address=btc_address, 
                status='not found', 
                is_verified=False, 
                type_op='insert', 
            )
            progress_bar.update(1)
            attempted_keys.add(priv_key_hex)
            if btc_address == self.target_address:
                self.db.log_attempt(
                    priv_key_hex=priv_key_hex, 
                    phrase='null', 
                    btc_address=btc_address, 
                    status='found', 
                    is_verified=True, 
                    type_op='insert', 
                )
            self.db.save_state(key_int)
            """
            balance = check_balance(btc_address)
            if balance:
                log_success(priv_key_hex, key.to_wif(), btc_address, balance)
                exec_time(start_time, "sequential")
            return
            """
            
    def process_range_random(self, start, stop, attempted_keys):
        start_time = time.time()
        progress_bar = tqdm(total=None, desc="Gerando chaves privadas:", unit=" chaves")
        while True:
            priv_key_hex = self.generate_random_hex(start=self.start_key_hex, stop=self.stop_key_hex, attempted_keys=attempted_keys)
            key = Key.from_hex(priv_key_hex)
            btc_address = key.address
            
            self.db.log_attempt(
                priv_key_hex=priv_key_hex,
                phrase='null', 
                btc_address=btc_address, 
                status='not found', 
                is_verified=False, 
                type_op='insert', 
            )
            attempted_keys.add(priv_key_hex)
            progress_bar.update(1)
            if btc_address == self.target_address:
                """
                balance = check_balance(btc_address)
                if balance:
                    log_success(priv_key_hex, key.to_wif(), btc_address, balance)
                    exec_time(start_time, "random")
                break
                """
                pass

    # Verifica combinações na base de dados para encontrar um endereço-alvo.
    def verify_key(self, target_address, batch_size=1000, num_threads=1):
        target_address = self.target_address
        try:
            start_time = time.time()
            # Define número de threads baseado no número de CPUs disponíveis
            if num_threads is None:
                num_threads = self.utils.get_cpu_cores()

            # Garantir que exista um índice no campo 'is_verified' para acelerar as consultas
            self.db.attempts_collection.create_index([("is_verified", ASCENDING)], background=True)

            # Busca apenas documentos não verificados, sem carregar tudo em memória
            cursor = self.db.attempts_collection.find({"is_verified": False}).batch_size(batch_size)

            # Inicializa tqdm com o total de documentos não verificados
            total_docs = self.db.attempts_collection.count_documents({"is_verified": False})
            lock = Lock()

            # Função para processar um lote de dados
            def process_batch(batch):
                updates = []
                for doc in batch:
                    priv_key_hex = doc['priv_key_hex']
                    address = doc['address']
                    updates.append({
                        'filter': {'_id': doc['_id']},
                        'update': {
                            '$set': {
                                'priv_key_hex': priv_key_hex,
                                'phrase': 'null',
                                'address': address,
                                'status': 'found' if address == target_address else 'not found',
                                'is_verified': True
                            }
                        }
                    })

                # Atualização em lote no MongoDB
                if updates:
                    self.db.attempts_collection.bulk_write(
                        [UpdateOne(u['filter'], u['update']) for u in updates]
                    )
                
                # Atualiza a barra de progresso
                with lock:
                    pbar.update(len(batch))

            # Dividindo o cursor em lotes e processando em paralelo
            with tqdm(total=total_docs, desc="Verificando endereços", unit=" chaves") as pbar:
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

                # Aguarda a conclusão de todas as threads
                executor.shutdown(wait=True)

            logging.info("Nenhum endereço correspondente encontrado.")
            self.utils.exec_time(start_time=start_time, mode='Verify')
            return "Nenhum endereço correspondente encontrado."

        except Exception as e:
            logging.error(f"Erro ao verificar endereços: {e}")
            return f"Erro: {e}"
