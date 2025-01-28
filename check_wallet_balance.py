import time
import requests
import json
import logging
from mongo_main import MongoMain 
from btc_find_utils import BtcFindUtils

db = MongoMain('hex')

utils = BtcFindUtils()

def check_balance():
    attempted_keys = set()
    start_time = time.time()
    try:
        cursor = db.load_objects()
        for object in cursor:
            response = requests.get(f"https://api.blockcypher.com/v1/btc/main/addrs/{object["btc_address"]}/balance")
            json_response = response.json()
            print(response)
            balance = json_response["balance"]
            print(object["btc_address"], "balance: ", balance)
            time.sleep(4)
            if balance != 0: 
                balance_collection.insert_one({"btc_address": object["btc_address"], "balance": balance})
        
        utils.exec_time(start_time, "balance mode")
    except FileNotFoundError:
        logging.warning("File not found")
        pass

check_balance()