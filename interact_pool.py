import requests
import logging
import time
from multiprocessing import Pool, Manager, Process
import hashlib
from hashlib import sha256
import ecdsa
import base58
from tqdm import tqdm
from pymongo import MongoClient
import queue
import _queue

from mongo_main import MongoMain
from btc_find_utils import BtcFindUtils


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class InteractPool:
    def __init__(self):
        self.db = MongoMain('hex')
        self.db_ = MongoMain('bip39')
        self.utils = BtcFindUtils()
        self.init_range = 0
        self.pool_token = ""
        self.api_url = "https://bitcoinflix.replit.app/api/block"
        self.headers = {"pool-token": self.pool_token}
        self.batch_size = 10  # Enviar 10 chaves por vez

    def get_pool_info(self):
        retries = 3
        for attempt in range(retries):
            try:
                response = requests.get(self.api_url, headers={"pool-token": self.pool_token})
                response.raise_for_status()
                data = response.json()
                logging.info(f"Dados fornecidos pela a pool:\n{data}")
                self.checkwork_addresses = data.get("checkwork_addresses", [])
                return {
                    'start': self.utils.hex_to_int(data['range']['start']),
                    'end': self.utils.hex_to_int(data['range']['end']),
                    'range': self.utils.hex_to_decimal(data['range']['end']) - self.utils.hex_to_decimal(data['range']['start'])
                }
            except requests.exceptions.RequestException as e:
                logging.error(f"Erro ao obter as informações do pool: {e}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    return None

    def get_db_priv_keys(self):
        logging.info("Aguarde... Carregando banco de dados.")
        
        pool_info = self.get_pool_info()
        if not pool_info:
            return []

        self.start_block = self.utils.hex_to_decimal(pool_info['start'])
        self.end_block = self.utils.hex_to_decimal(pool_info['end'])
        self.range_block = self.end_block - self.start_block
        
        if self.range_block != self.init_range and self.init_range != 0:
            logging.info(f"O range foi alterado: Início {self.start_block}, Fim {self.end_block}, Intervalo: {self.range_block}")
        
        self.docs = []
        self.priv_keys = set()
        logging.info("Carregando combinações tentadas do banco de dados...")

        for obj in tqdm(self.db.load_objects('attempts'), desc="Carregando registros", unit=" registros"):
            priv_key_decimal = self.utils.hex_to_decimal(obj['priv_key_hex'])
            self.docs.append(obj)
            if self.start_block <= priv_key_decimal <= self.end_block:
                self.priv_keys.add(obj['priv_key_hex'])

        return self.priv_keys
    
    @staticmethod
    def post_keys(pool_token, attempted_keys_queue, api_url, batch_size=10):
        headers = {
            "pool-token": pool_token,
        }

        while True:
            batch = []

            # Aguardar até ter exatamente batch_size elementos
            while len(batch) < 10:
                try:
                    attempted_keys = attempted_keys_queue.get(timeout=30)  # Timeout evita bloqueios indefinidos
                    if attempted_keys is None:  # Sinal de término
                        if batch:  # Enviar último batch se tiver elementos
                            break
                        return
                    batch.extend(attempted_keys[:batch_size - len(batch)])  # Garantir 10 chaves por requisição
                except:
                    continue  # Continuar tentando até atingir batch_size

            if not batch:
                continue  # Garantir que não envie requisições vazias

            # Formatar chaves para "0x..."
            batch = [f"0x{key.lstrip('0')}" for key in batch]

            data = {"privateKeys": batch}
            print(f"Enviando chaves restantes:\n {data}")

            try:
                response = requests.post(api_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    logging.info(f"{len(batch)} chaves enviadas com sucesso.")
                else:
                    logging.error(f"Falha ao enviar as chaves:\n {result.get('message')}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Erro ao enviar as chaves privadas: {e}")
                time.sleep(5)  # Evita requisições excessivas em caso de erro

    def generate_and_send_keys(self):
        manager = Manager()
        attempted_keys_queue = manager.Queue()
        progress_queue = manager.Queue()

        pool_info = self.get_pool_info()
        if not pool_info:
            return
        last_tested_key = self.db.attempts_collection.find_one(sort=[('_id', -1)])
        print(last_tested_key)
        start = pool_info['start']
        end = pool_info['end']

        num_cores = 8
        total_keys = end - start + 1
        chunk_size = total_keys // num_cores  # Melhor distribuição

        post_keys_process = Process(target=self.post_keys, args=(self.pool_token, attempted_keys_queue, self.api_url, self.headers))
        post_keys_process.start()

        pool_args = []
        for i in range(num_cores):
            sub_start = start + i * chunk_size
            sub_stop = min(sub_start + chunk_size - 1, end)
            pool_args.append((sub_start, sub_stop, attempted_keys_queue, progress_queue, self.checkwork_addresses))

        with tqdm(desc="Processando Chaves", unit=" chaves", total=total_keys) as pbar:
            with Pool(processes=num_cores) as pool:
                result = pool.starmap_async(self._generate_keys_in_range, pool_args)

                while not result.ready():
                    try:
                        batch_size = progress_queue.get(timeout=1)
                        pbar.update(batch_size)
                    except (queue.Empty, _queue.Empty):
                        pass  # Evita travamentos no loop

                result.wait()

        attempted_keys_queue.put(None)
        post_keys_process.join()

        logging.info("Processamento finalizado.")

    @staticmethod
    def _generate_keys_in_range(start, stop, attempted_keys_queue, progress_queue, checkwork_addresses, batch_size=1000):
        utils = BtcFindUtils()
        batch = []
        batch_check = []
        local_count = 0
        total_keys = stop - start + 1
            
        db = MongoMain('pool')

        for key_int in range(start, stop + 1):
            priv_key_hex = utils.int_to_hex(key_int)
            public_key_hex = private_key_to_public_key(priv_key_hex)
            address = public_key_to_address(public_key_hex)
            batch.append(priv_key_hex)

            if address in checkwork_addresses:
                batch_check.append(priv_key_hex)
                logging.info(f"\nCHECKWORK ADDRESS ENCONTRADO! {address}\n")

            local_count += 1

            if local_count % (batch_size // 100) == 0:  # Atualiza com mais precisão
                progress_queue.put(local_count)
                local_count = 0  # Reseta a contagem local após a atualização

            if len(batch) >= batch_size:  # Evita excesso de chaves na memória
                db.insert_batch(batch, random=False, pool=True)
                batch.clear()

        if batch:
            db.insert_batch(batch, random=False, pool=True)
            logging.info(f"\nInseridas {len(batch)} chaves finais do bloco no MongoDB.\n")

        if batch:
            attempted_keys_queue.put(batch)

        if local_count > 0:
            progress_queue.put(local_count)


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