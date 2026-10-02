
import logging
from pymongo import MongoClient
import tqdm
import os
from datetime import datetime, timezone
from pymongo import UpdateOne

TXT_PATH = "Latest_Rich_Bitcoin_P2PKH.txt"
from btc_find_utils import BtcFindUtils

logging.basicConfig(level=logging.INFO)



from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

client = MongoClient('localhost', 27017, serverSelectionTimeoutMS=5000)

try:
    client.admin.command('ping')
except (ConnectionFailure, ServerSelectionTimeoutError):
    logging.error("MongoDB indisponível em localhost:27017. Verifique se o serviço está rodando (Get-Service MongoDB).")
    raise SystemExit(1)

# Modificação referente ao instanciação redundante -> linha 13 
# client = MongoClient('localhost', 27017)
database = input("Digite o nome da base de dados (bip39, hex): ")
if database == 'bip39':
    db_bip39 = client['bip39']
    attempts_collection = db_bip39['bip39_attempts']
elif database == 'hex':
    db_hex = client['hex']
    attempts_collection = db_hex['hex_attempts']
    state_collection = db_hex['hex_state']
    success_collection = db_hex['hex_success']
elif database == 'pool':
    db_pool = client['pool']
    attempts_collection = db_pool['pool_attempts']
    state_collection = db_pool['pool_state']
elif database == 'funded':
    db_funded = client['funded']
    funded_collection = db_funded['btc_addresses']
    matches_collection = db_funded['matches']
    attempts_collection = funded_collection
    funded_collection.create_index('address', unique=True, background=True)
    matches_collection.create_index('address', background=True)
    matches_collection.create_index(
        [('source_db', 1), ('address', 1)],
        unique=True,
        background=True,
    )
else:
    raise ValueError("Database not found")

def load_rich_addresses(path="Latest_Rich_Bitcoin_P2PKH.txt"):
    if not os.path.isfile(path):
        logging.error("Arquivo não encontrado: %s", path)
        return set()
    with open(path, "r", encoding="utf-8-sig") as f:  # utf-8-sig remove BOM, comum no Windows
        return {line.strip() for line in f if line.strip()}

def log_attempt(priv_key_hex, phrase, btc_address, status, is_verified, type_op):
    try:
        if database == 'hex' and priv_key_hex:
            if type_op == 'insert':
                attempts_collection.insert_one({
                "priv_key_hex": priv_key_hex,
                "address": btc_address, 
                "status": status, 
                "is_verified": is_verified
            })
            elif type_op == 'update':
                attempts_collection.update_one(
                    {"priv_key_hex": priv_key_hex, "address": btc_address},  # Filter
                    {"$set": {"status": status, "is_verified": is_verified}})  # Update
        elif database == 'bip39':
            if type_op == 'insert':
                attempts_collection.insert_one({
                    "combination": phrase,
                    "address": btc_address,
                    "status": status,
                    "is_verified": is_verified,
                })
            elif type_op == 'update':
                attempts_collection.update_one(
                    {"combination": phrase, "address": btc_address},  # Filter
                    {"$set": {"status": status, "is_verified": is_verified}}  # Update
                )
    except Exception as e:
        logging.error(f"Failed to log attempt: {e}")


def load_attempted_keys(limit=None, skip=0):
    rich = load_rich_addresses()
    if not rich:
        logging.info("Nenhum endereço carregado do TXT.")
        return 0
    logging.info("%d endereços carregados do TXT.", len(rich))

    try:
        if limit is not None and limit <= 0:
            logging.info("Limite inválido (%s). Nada a carregar.\n", limit)
            return set()

        total = attempts_collection.count_documents({})
        available = max(total - skip, 0)
        to_load = min(available, limit) if limit is not None else available
        
        if not to_load:
            logging.info("Nenhum endereço para carregar...\n")
            return set()

        objects = set()
        cursor = attempts_collection.find({}, {"_id": 0}).skip(skip)
        if limit is not None:
            cursor = cursor.limit(limit)
        # Mudar o parâmetro total=limit para total=to_load caso a contagem total de endereços seja descomentada.
        with tqdm.tqdm(total=to_load, desc="Comparando endereços.", unit=" endereços") as pbar:
            for obj in cursor:
                addr = obj.get("address")
                if addr in rich:
                    objects.add(tuple(obj.items()))
                pbar.update(1)
        for obj in objects:
            print(obj[1][-1])
        return objects
    except Exception as e:
        logging.error(f"Erro ao carregar endereços gerados: {e}")
        return set()

if __name__ == "__main__":
    raw = input("Quantos documentos carregar? (Enter para todos): ").strip()
    limit = int(raw) if raw.isdigit() else None

    keys = load_attempted_keys(limit=limit)
    logging.info("%d endereços encontrados.", len(keys))
