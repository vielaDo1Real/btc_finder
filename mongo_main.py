from pymongo import MongoClient, ASCENDING
import logging
import json
from bson import json_util
import tqdm


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
            logging.error(f"Failed to log success: {e}")

    def load_objects(self, type_collection):
        try:
            if self.database == 'hex':
                cursor = self.attempts_collection.find({}, {"_id": 0})
                if type_collection == 'attempts':
                    return [obj.get("priv_key_hex") for obj in cursor]
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

    def int_to_hex(self, value):
        return hex(value)[2:].zfill(64)

    def save_state(self, key_int):
        key_int = str(key_int)
        self.state_collection.update_one({}, {"$set": {"state": key_int}})
    
    def insert_state(self, state):
        try:
            self.state_collection.insert_one({"state": str(state)})
        except Exception as e:
            logging.error(f"Error inserting state: {e}")

    def load_state(self):
        try:
            state = self.state_collection.find_one({}, {"_id": 0})
            state = int(state['state'])
            return state
        except Exception as e:
            logging.error(f"Error loading state: {e}")
            return {}

    def update_state(self, state):
        try:
            self.state_collection.update_one({}, {"$set": state})
        except Exception as e:
            logging.error(f"Error updating state: {e}")
