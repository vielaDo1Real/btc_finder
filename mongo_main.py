from pymongo import MongoClient
import logging
import json
from bson import json_util
import tqdm

from btc_find_utils import BtcFindUtils

class MongoMain:
    def __init__(self, database):
        self.client = MongoClient('localhost', 27017)
        self.database = database
        if database == 'bip39':
            self.db_bip39 = self.client['bip39']
            self.attempts_collection = self.db_bip39['bip39_attempts']
        elif database == 'hex':
            self.db_hex = self.client['hex']
            self.attempts_collection = self.db_hex['hex_attempts']
            self.state_collection = self.db_hex['hex_state']
            self.success_collection = self.db_hex['hex_success']
        elif database == 'pool':
            self.db_pool = self.client['pool']
            self.attempts_collection = self.db_pool['pool_attempts']
            self.state_collection = self.db_pool['pool_state']
        else:
            raise ValueError("Database not found")

    def log_attempt(self, priv_key_hex, phrase, btc_address, status, is_verified, type_op):
        try:
            if self.database == 'hex' and priv_key_hex:
                if type_op == 'insert':
                    self.attempts_collection.insert_one({
                    "priv_key_hex": priv_key_hex,
                    "address": btc_address, 
                    "status": status, 
                    "is_verified": is_verified
                })
                elif type_op == 'update':
                    self.attempts_collection.update_one(
                        {"priv_key_hex": priv_key_hex, "address": btc_address},  # Filter
                        {"$set": {"status": status, "is_verified": is_verified}})  # Update
            elif self.database == 'bip39':
                if type_op == 'insert':
                    self.attempts_collection.insert_one({
                        "combination": phrase,
                        "address": btc_address,
                        "status": status,
                        "is_verified": is_verified,
                    })
                elif type_op == 'update':
                    self.attempts_collection.update_one(
                        {"combination": phrase, "address": btc_address},  # Filter
                        {"$set": {"status": status, "is_verified": is_verified}}  # Update
                    )
        except Exception as e:
            logging.error(f"Failed to log attempt: {e}")

    def insert_batch(self, batch_data, random=False, pool=False):
        utils = BtcFindUtils()
        save_state = False # Evitar que o estado seja armazenado diverssas vezes
        if not batch_data:
            return
        # Inserir documentos no banco de dados
        try:
            if not save_state and not random and not pool:
                key_int = utils.hex_to_int(batch_data[-1]['priv_key_hex'])
                save_state = self.save_state(key_int)
            elif pool:
                docs = []
                for key in batch_data:
                    docs.append({'priv_key_hex': key})
                key_int = docs[-1]['priv_key_hex']
                key_int = utils.hex_to_int(key_int)
                print(key_int)
                save_state = self.save_state(key_int)
                result = self.attempts_collection.insert_many(docs)
            else:
                result = self.attempts_collection.insert_many(batch_data)
            
        except Exception as e:
            logging.error(f'Erro ao inserir documentos em lote: {e}')

    def log_success(self, priv_key_hex, phrase, priv_key_wif, btc_address, balance):
        try:
            self.success_collection.insert_one({
                "priv_key_hex": priv_key_hex,
                "phrase": phrase,
                "priv_key_wif": priv_key_wif,
                "address": btc_address,
                "balance": balance
            })
            logging.info(json.dumps({
                "priv_key_hex": priv_key_hex,
                "phrase": phrase,
                "priv_key_wif": priv_key_wif,
                "address": btc_address,
                "balance": balance
            }, indent=4, default=json_util.default))
        except Exception as e:
            logging.error(f"Erro ao inserir sucesso: {e}")

    def load_objects(self, type_collection):
        try:
            if self.database == 'hex':
                cursor = list(self.attempts_collection.find({}, {"_id": 0}))
                if type_collection == 'attempts':
                    return cursor
                elif type_collection == 'address':
                    return [obj.get("address") for obj in cursor]
            elif self.database == 'bip39':
                cursor = list(self.attempts_collection.find({}, {"_id": 0}))
                if type_collection == 'attempts':
                    return cursor
                elif type_collection == 'address':
                    return [obj.get("address") for obj in cursor]
        except Exception as e:
            logging.warning(f"Error loading objects: {e}")
            return []

    def load_attempted_keys(self):
        try:
            objects = set()
            counter = self.attempts_collection.count_documents({})
            if counter:
                with tqdm.tqdm(total=counter, desc="Carregando endereços gerados.", unit=" endereços") as pbar:
                    for obj in self.attempts_collection.find({}, {"_id": 0}):
                        objects.add(tuple(obj.items()))
                        pbar.update(1)
                return objects
            else:
                logging.info("Nenhum endereço para carregar...\n")
                return set()
        except Exception as e:
            logging.error(f"Erro ao carregar endereços gerados: {e}")
            return set()

    def save_state(self, key_int):
        key_int = key_int
        try:
            state = self.state_collection.find_one(sort=[('_id', -1)])
            if state:
                self.state_collection.update_one({}, {"$set": {"state": str(key_int)}})
            else:
                self.insert_state(str(key_int))
        except Exception as e:
            logging.error(f"Erro ou salvar estado: {e}")
    
    def insert_state(self, state):
        try:
            self.state_collection.insert_one({"state": str(state)})
        except Exception as e:
            logging.error(f"Error inserting state: {e}")

    def load_state(self):
        try:
            state = self.state_collection.find_one({}, {"_id": 0})
            state = state['state']
            return state
        except Exception as e:
            logging.error(f"Error loading state: {e}")
            return 0

    def update_state(self, state):
        try:
            self.state_collection.update_one({}, {"$set": state})
        except Exception as e:
            logging.error(f"Error updating state: {e}")

    def clean_duplicates(self, loaded_objects=None):
        try:
            # Usar documentos carregados pela função load_objects, se fornecidos
            if not loaded_objects:
                loaded_objects = self.load_objects('attempts')

            # Criar um pipeline de agrupamento de duplicados na memória
            duplicates_map = {}
            print() # pular uma linha antes de exibir a próxima barra
            for obj in tqdm.tqdm(loaded_objects, desc="Mapeando objetos duplicados", unit=" documentos", leave=True):
                combination = obj.get("combination")
                address = obj.get("address")
                key = (combination, address)

                if key not in duplicates_map:
                    duplicates_map[key] = [obj]
                else:
                    duplicates_map[key].append(obj)

            # Identificar duplicados
            duplicates = [
                docs for docs in duplicates_map.values() if len(docs) > 1
            ]

            # Remover duplicados do banco de dados
            total_removed = 0
            print()
            for group in tqdm.tqdm(duplicates, desc="Removendo objetos duplicados", unit=" grupos", leave=True):
                ids_to_remove = [doc["_id"] for doc in group[1:]]  # Manter o primeiro, remover os demais
                self.attempts_collection.delete_many({"_id": {"$in": ids_to_remove}})
                total_removed += len(ids_to_remove)

            logging.info(f"Removidos {total_removed} registros duplicados.")

        except Exception as e:
            logging.error(f"Erro ao remover duplicados: {e}")

    def get_collection_size_mb(self, loaded_objects=None):
        try:
            # Caso os objetos já tenham sido carregados
            if loaded_objects:
                logging.info("Calculando tamanho da coleção com base nos objetos carregados...")

                total_size = 0
                print()
                for obj in tqdm.tqdm(loaded_objects, desc="Calculando tamanho", unit=" documentos", leave=True):
                    total_size += len(str(obj))  # Aproximação do tamanho em bytes

                size_in_mb = total_size / (1024 * 1024)  # Converte bytes para MB
                logging.info(f"📊 Tamanho estimado da coleção (em memória): {size_in_mb:.2f} MB")
                return size_in_mb

            # Se não foram carregados objetos, usar o comando `collStats`
            logging.info("Calculando tamanho da coleção diretamente do banco de dados...")
            stats = self.attempts_collection.database.command("collStats", self.attempts_collection.name)
            size_in_mb = stats["size"] / (1024 * 1024)  # Converte bytes para MB
            logging.info(f"📊 Tamanho da coleção no banco: {size_in_mb:.2f} MB")
            return size_in_mb

        except Exception as e:
            logging.error(f"❌ Erro ao obter tamanho da coleção: {e}")
            return None
