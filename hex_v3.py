import random
from bit import Key
import time
import logging
from tqdm import tqdm
from pymongo import ASCENDING, UpdateOne
from pymongo.errors import BulkWriteError
from multiprocessing import Pool, Manager
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
import hashlib
import ecdsa
import base58
from hashlib import sha256
import threading
from queue import Queue

from mongo_main import MongoMain
from btc_find_utils import BtcFindUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def private_key_to_wif(private_key_hex):
    extended_key = b"\x80" + bytes.fromhex(private_key_hex)  # Adiciona prefixo 0x80
    first_sha256 = sha256(extended_key).digest()
    second_sha256 = sha256(first_sha256).digest()
    checksum = second_sha256[:4]  # Pegamos os primeiros 4 bytes como checksum
    return base58.b58encode(extended_key + checksum).decode()

def private_key_to_public_key(private_key_hex):
    private_key_bytes = bytes.fromhex(private_key_hex)
    sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    public_key = b"\x04" + vk.to_string()  # Prefixo 0x04 indica chave não comprimida
    return public_key.hex()

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

class HexV():
    def __init__(self):
        self.start_key_hex = "0000000000000000000000000000000000000000000000040000000000000000"
        self.stop_key_hex = "000000000000000000000000000000000000000000000007ffffffffffffffff"
        self.target_address = '1BY8GQbnueYofwSuFAT3USAhGjPrkxDdW9'
        self.db = MongoMain('hex')
        self.start_key_int = int(self.start_key_hex, 16)
        self.index_db = self.db.attempts_collection.create_index([("is_verified", ASCENDING)], background=True)
        self.state = [i for i in self.db.state_collection.find({})]
        if not self.state:
            self.db.insert_state(self.start_key_int)
        else:
            self.start_key_int = int(self.state[0]['state'])
        self.stop_key_int = int(self.stop_key_hex, 16)
        self.utils = BtcFindUtils()

    def generate_random_hex(self, start, stop, attempted_keys):
        while True:
            random_int = random.randint(start, stop)
            random_hex = format(random_int, '064x')
            if random_hex not in attempted_keys:
                return random_hex

    def process_range_random(self, start, stop, attempted_keys, num_threads):
        batch_size=1000
        total_iterations = stop - start + 1
        progress_queue = Queue()

        # Função que será executada por cada thread
        def process_chunk(start, stop, chunk_progress_queue):
            keys_to_insert = []  # Lista para armazenar as chaves a serem inseridas em lote
            count = 0
            for _ in range(start, stop + 1):
                priv_key_hex = self.generate_random_hex(start, stop, attempted_keys)
                if priv_key_hex in attempted_keys:
                    continue

                public_key = private_key_to_public_key(priv_key_hex)
                btc_address = public_key_to_address(public_key)

                # Adiciona a chave à lista de chaves a serem inseridas
                keys_to_insert.append({
                    'priv_key_hex': priv_key_hex,
                    'btc_address': btc_address,
                    'status': 'not found',
                    'is_verified': False,
                    'type_op': 'insert'
                })

                attempted_keys.add(priv_key_hex)
                if btc_address == self.target_address:
                    # Adiciona as chaves com o status "found" e is_verified "true"
                    keys_to_insert.append({
                        'priv_key_hex': priv_key_hex,
                        'btc_address': btc_address,
                        'status': 'found',
                        'is_verified': True,
                        'type_op': 'insert'
                    })

                count += 1
                if count % batch_size == 0:
                    # Insere em lote e limpa a lista para o próximo lote
                    self.db.insert_batch(keys_to_insert, random=True, pool=False)
                    keys_to_insert = []
                    chunk_progress_queue.put(count)  # Atualiza o progresso a cada batch_size

            # Inserir as chaves restantes após o loop
            if keys_to_insert:
                self.db.insert_batch(keys_to_insert, random=True, pool=False)

        # Função para atualizar a barra de progresso
        def update_progress():
            progress_bar = tqdm(total=total_iterations, desc="Gerando chaves privadas", unit=" chaves")
            completed = 0
            while completed < total_iterations:
                progress_queue.get()  # Espera por um item na fila
                completed += batch_size  # Avança o progresso em batch_size chaves
                progress_bar.update(batch_size)  # Atualiza a barra de progresso
            progress_bar.close()

        # Iniciar a barra de progresso em um thread separado
        progress_thread = threading.Thread(target=update_progress)
        progress_thread.start()

        # Dividir o intervalo entre as threads
        chunk_size = (stop - start + 1) // num_threads
        threads = []

        for i in range(num_threads):
            chunk_start = start + i * chunk_size
            chunk_end = chunk_start + chunk_size - 1 if i < num_threads - 1 else stop

            # Criar e iniciar a thread
            thread = threading.Thread(target=process_chunk, args=(chunk_start, chunk_end, progress_queue))
            threads.append(thread)
            thread.start()

        # Espera o término de cada thread
        for thread in threads:
            thread.join()

        # Esperar o thread de progresso terminar
        progress_thread.join()


    def process_range_sequential(self, start, stop, attempted_keys, num_threads):
        # Inicializar a barra de progresso
        batch_size=1000
        total_iterations = stop - start + 1
        progress_queue = Queue()

        # Função que será executada por cada thread
        def process_chunk(start, stop, chunk_progress_queue):
            keys_to_insert = []  # Lista para armazenar as chaves a serem inseridas em lote
            count = 0
            for key_int in range(start, stop + 1):
                priv_key_hex = self.utils.int_to_hex(key_int)
                if priv_key_hex in attempted_keys:
                    continue

                public_key = private_key_to_public_key(priv_key_hex)
                btc_address = public_key_to_address(public_key)

                # Adiciona a chave à lista de chaves a serem inseridas
                keys_to_insert.append({
                    'priv_key_hex': priv_key_hex,
                    'btc_address': btc_address,
                    'status': 'not found',
                    'is_verified': False,
                    'type_op': 'insert'
                })

                attempted_keys.add(priv_key_hex)  # Marca a chave como utilizada
                if btc_address == self.target_address:
                    # Adiciona as chaves com o status "found" e is_verified "true"
                    keys_to_insert.append({
                        'priv_key_hex': priv_key_hex,
                        'btc_address': btc_address,
                        'status': 'found',
                        'is_verified': True,
                        'type_op': 'insert'
                    })

                count += 1
                if count % batch_size == 0:
                    # Insere em lote e limpa a lista para o próximo lote
                    self.db.insert_batch(keys_to_insert, random=False, pool=False)
                    keys_to_insert = []
                    chunk_progress_queue.put(count)  # Atualiza o progresso a cada batch_size

            # Inserir as chaves restantes após o loop
            if keys_to_insert:
                self.db.insert_batch(keys_to_insert, random=False, pool=False)

        # Função para atualizar a barra de progresso
        def update_progress():
            progress_bar = tqdm(total=total_iterations, desc="Gerando chaves privadas", unit=" chaves")
            completed = 0
            while completed < total_iterations:
                progress_queue.get()  # Espera por um item na fila
                completed += batch_size  # Avança o progresso em batch_size chaves
                progress_bar.update(batch_size)  # Atualiza a barra de progresso
            progress_bar.close()

        # Iniciar a barra de progresso em um thread separado
        progress_thread = threading.Thread(target=update_progress)
        progress_thread.start()

        # Dividir o intervalo entre as threads
        chunk_size = (stop - start + 1) // num_threads
        threads = []

        for i in range(num_threads):
            chunk_start = start + i * chunk_size
            chunk_end = chunk_start + chunk_size - 1 if i < num_threads - 1 else stop

            # Criar e iniciar a thread
            thread = threading.Thread(target=process_chunk, args=(chunk_start, chunk_end, progress_queue))
            threads.append(thread)
            thread.start()

        # Esperar todas as threads terminarem
        for thread in threads:
            thread.join()

        # Esperar o thread de progresso terminar
        progress_thread.join()


    def hex_run_multiprocessing(self, start, stop, num_cores, type_op=None):
        manager = Manager()
        attempted_keys = manager.dict()  # Dicionário compartilhado para evitar chaves repetidas
        progress_queue = manager.Queue()  # Fila para progresso
        total_keys = stop - start + 1
        chunk_size = (total_keys // num_cores) + 1  # Divide o intervalo entre os processos
        pool_args = []
        if type_op:
            self.keys = attempted_keys
        # Divide os intervalos para cada processo
        for i in range(num_cores):
            sub_start = start + i * chunk_size
            sub_stop = min(sub_start + chunk_size - 1, stop)
            pool_args.append((sub_start, sub_stop, attempted_keys, progress_queue))

        # Barra de progresso compartilhada
        with tqdm(desc="Processando Chaves", unit=" chaves", total=total_keys) as pbar:
            with Pool(processes=num_cores) as pool:
                result = pool.starmap_async(self._generate_keys_in_range, pool_args)

                while not result.ready():
                    try:
                        batch_size = progress_queue.get(timeout=1)  # Obtém progresso em blocos
                        pbar.update(batch_size)  # Atualiza a barra de progresso de forma eficiente
                    except:
                        pass

                result.wait()  # Aguarda que todos os processos finalizem corretamente

        print("✅ Processamento finalizado!")

    @staticmethod
    def _generate_keys_in_range(start, stop, attempted_keys, progress_queue, batch_size=1000):
        local_count = 0  # Contador local para enviar progresso em blocos
        utils = BtcFindUtils()

        for key_int in range(start, stop + 1):
            priv_key_hex = utils.int_to_hex(key_int)
            public_key = private_key_to_public_key(priv_key_hex)
            attempted_keys[priv_key_hex] = True  # Marca a chave como tentada
            key = Key.from_hex(priv_key_hex)
            btc_address = key.address

            local_count += 1  # Incrementa o contador local

            # Enviar progresso em blocos para evitar impacto no desempenho
            if local_count >= batch_size:
                progress_queue.put(local_count)
                local_count = 0  # Reinicia o contador

        # Enviar qualquer progresso restante no final do loop
        if local_count > 0:
            progress_queue.put(local_count)


    def verify_key(self, target_address, batch_size=1000, num_threads=4):
        global running
        running = True  # Define o estado inicial como "executando"

        try:
            start_time = time.time()
            total_docs = self.db.attempts_collection.count_documents({"is_verified": False})
            if total_docs == 0:
                logging.info("Nenhum documento para verificar.")
                return {"status": "success", "message": "Nenhum documento para verificar."}

            cursor = self.db.attempts_collection.find({"is_verified": False}).batch_size(batch_size)
            queue = Queue()

            def process_batch():
                while running:
                    try:
                        batch = queue.get(timeout=1)
                        if batch is None:
                            break
                        updates = []
                        for doc in batch:
                            if not running:
                                break
                            priv_key_hex = doc['priv_key_hex']
                            address = doc['btc_address']
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

                        if updates and running:
                            try:
                                self.db.attempts_collection.bulk_write(
                                    [UpdateOne(u['filter'], u['update']) for u in updates]
                                )
                                pbar.update(len(batch))
                            except BulkWriteError as e:
                                logging.error(f"Erro ao atualizar os documentos em lote: {e}")
                    except queue.Empty:
                        if not running:
                            break
                    except Exception as e:
                        logging.error(f"Erro inesperado ao processar lote: {e}")
                    finally:
                        queue.task_done()

            with tqdm(total=total_docs, desc="Verificando endereços", unit="documento") as pbar:
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    batch = []
                    for doc in cursor:
                        if not running:
                            break
                        batch.append(doc)
                        if len(batch) >= batch_size:
                            queue.put(batch)
                            batch = []

                    if batch and running:
                        queue.put(batch)

                    futures = [executor.submit(process_batch) for _ in range(num_threads)]

                    # Aguarda o sinal de interrupção (CTRL + C)
                    while running:
                        time.sleep(0.1)

                    # Adiciona sinal de parada para cada thread
                    for _ in range(num_threads):
                        queue.put(None)

                    # Aguarda a conclusão das threads
                    for future in futures:
                        future.result()

                    queue.join()
                    exit()
                logging.info("Verificação concluída.")
                self.utils.exec_time(start_time=start_time, mode='Verify')
                return {
                    "status": "success",
                    "message": "Verificação concluída.",
                    "total_docs": total_docs,
                    "execution_time": time.time() - start_time
                }

        except Exception as e:
            logging.error(f"Erro ao verificar endereços: {e}")
            return {"status": "error", "message": f"Erro: {e}"}
