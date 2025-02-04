import logging
from pymongo import MongoClient, UpdateOne, ASCENDING
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import random
from threading import Lock
import time
from mnemonic import Mnemonic

from btc_find_utils import BtcFindUtils, WordCompare
from  mongo_main import MongoMain
from monitor import HardwareMonitor

client = MongoClient('localhost', 27017)
db = client['bip39']
attempts_collection = db['bip39_attempts']
verified_collection = db['bip39_verified']


class Bip39V:
    def __init__(self):
        self.db = MongoMain('bip39')
        self.utils = BtcFindUtils()
        self.bip39_words = WordCompare('portuguese')
        # self.monitor = HardwareMonitor()
        # Inicializa as combinações tentadas
        try:
            logging.info("AGUARDE... Carregando banco de dados.")
            print() # Pular uma linha antes de exibir a próxima barra
            self.attempted_combinations = set(
                obj['combination'] for obj in tqdm(self.db.load_objects('attempts'), 
                                                   desc="Carregando combinações tentadas", 
                                                   unit=" registros", leave=True)
            )
            self.db.clean_duplicates()
            self.db.get_collection_size_mb()
        except Exception as e:
            logging.warning(f"Erro ao carregar 'attempts' do banco de dados: {e}")
        
        # Inicializa as combinações verificadas
        try:
            self.verified_combinations = self.db.load_objects('verified') or []
        except Exception as e:
            logging.warning(f"Erro ao carregar 'verified' do banco de dados: {e}")
    
    def process_combination_sequence(self, combo, insert_progress, threads_progress, futures):
        try:
            seed = Bip39SeedGenerator(combo).Generate()
            bip44 = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
            address = bip44.PublicKey().ToAddress()
            try:
                self.db.log_attempt('null', combo, address, 'not found', False, 'insert')

                # Atualiza progresso de inserção
                insert_progress.update(1)

                # Atualiza progresso das threads ativas
                futures.discard(combo)  # Remove a combinação concluída do conjunto
                threads_progress.n = len(futures)
                threads_progress.refresh()

                return True
            except Exception as e:
                logging.warning(f"Combinação duplicada ignorada: {combo}")
                return False
        except Exception as e:
            self.db.log_attempt('null', combo, 'Bip39SeedGenerator', 'error', None, 'insert')
            return False

    def process_combination_random(self, combo, insert_progress, threads_progress, futures):
        try:
            seed = Bip39SeedGenerator(combo).Generate()
            bip44 = Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
            address = bip44.PublicKey().ToAddress()
            try:
                self.db.log_attempt('null', combo, address, 'not found', False, 'insert')

                # Atualiza progresso de inserção
                insert_progress.update(1)

                # Atualiza progresso das threads ativas
                futures.discard(combo)  # Remove a combinação concluída do conjunto
                threads_progress.n = len(futures)
                threads_progress.refresh()

                return True
            except Exception as e:
                logging.warning(f"Combinação duplicada ignorada: {combo}")
                return False
        except Exception as e:
            self.db.log_attempt('null', combo, 'Bip39SeedGenerator', 'error', None, 'insert')
            return False

    def generate_combinations(self, words, num_words, num_threads, type_gen):
        if num_threads <=10: 
            num_threads = 10
        mnemo = Mnemonic("portuguese")
        words = list(set(words))
        total_combinations = itertools.combinations(words, num_words)
        insert_progress = tqdm(desc="Gerando seeds", unit=" seeds", position=2)
        # Inicializa a barra de progresso das threads ativas
        threads_progress = tqdm(desc="Threads em execução", position=0)

        # hardware_progress = tqdm(desc="Monitorando hardware", total=1, bar_format="{desc}", position=0)

        # self.monitor.start() # Implementar monitoramento de recursos
        try:
            if type_gen == "random":
                combinations_progress = tqdm(desc="Gerando combinações aleatórias", unit=" frases", position=1)
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    futures = set()  # Conjunto para rastrear threads ativas
                    try:

                        for combo in total_combinations:
                            # signal.signal(signal.SIGINT, self.utils.handle_exit)
                            combinations_progress.update(1)
                            combo_str = " ".join(random.sample(combo, num_words))

                            if combo_str not in self.attempted_combinations and mnemo.check(combo_str):
                                self.attempted_combinations.add(combo_str)

                                # Adiciona a combinação ao conjunto de threads ativas
                                futures.add(combo_str)

                                # Adiciona a thread ao executor
                                future = executor.submit(self.process_combination_random, combo_str, insert_progress, threads_progress, futures)

                                # Atualiza a barra de progresso das threads ativas
                                threads_progress.n = len(futures)
                                threads_progress.refresh()

                                #self.monitor.update_hardware_monitor(hardware_progress) # Implementar monitoramento de hardware
                    
                    except KeyboardInterrupt:
                        print("\nInterrompendo Threads...")
                        executor.shutdown(wait=False)
            
            elif type_gen == "sequence":
                combinations_progress = tqdm(desc="Gerando combinações em sequenciais", unit=" frases", position=0)
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    futures = set()  # Conjunto para rastrear threads ativas
            
                    try:
                        for combo in total_combinations:
                            # signal.signal(signal.SIGINT, self.utils.handle_exit)
                            combinations_progress.update(1)
                            combo_str = " ".join(combo)

                            if combo_str not in self.attempted_combinations and mnemo.check(combo_str):
                                self.attempted_combinations.add(combo_str)

                                # Adiciona a combinação ao conjunto de threads ativas
                                futures.add(combo_str)

                                # Adiciona a thread ao executor
                                future = executor.submit(self.process_combination_sequence, combo_str, insert_progress, threads_progress, futures)

                                # Atualiza a barra de progresso das threads ativas
                                threads_progress.n = len(futures)
                                threads_progress.refresh()
            
                    except KeyboardInterrupt:
                        print("\nInterrompido pelo usuário.")
                    finally:
                        combinations_progress.close()
                        insert_progress.close()
                       # hardware_progress.close()


                # Aguardar a conclusão das tarefas
                for future in as_completed(futures):
                    future.result()  # Garante que todas as threads sejam concluídas
                    # hardware_progress.close()


                    # Atualiza o progresso das threads ativas
                    threads_progress.n = len(futures)
                    threads_progress.refresh()

        except Exception as e:
            logging.error(f"Erro ao gerar combinações: {e}")

        finally:
            threads_progress.close() 

    def verify_seed(self, target_address, batch_size=100, num_threads=1):
        try:
            start_time = time.time()

            # Garantir que exista um índice no campo 'is_verified' para acelerar as consultas
            self.db.attempts_collection.create_index(
                [("is_verified", ASCENDING)], 
                background=True
            )

            # Busca apenas documentos não verificados, sem carregar tudo em memória
            cursor = self.db.attempts_collection.find({"is_verified": False}).batch_size(batch_size)

            # Inicializa tqdm com o total de documentos não verificados
            total_docs = self.db.attempts_collection.count_documents({"is_verified": False})
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
                                'status': 'found' 
                                if address == target_address 
                                else 'not found',
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
            with tqdm(
                total=total_docs, 
                desc="Verificando endereços", 
                unit=" combinações") as pbar:
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
