import csv
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient('localhost', 27017)
db = client['key_search_db']
attempts_collection = db['attempts']

# Fetch BTC addresses from MongoDB collection and store them in a set
cursor = attempts_collection.find({}, {"_id": 0, "btc_address": 1})

wallets = set()
for obj in cursor:
    wallets.add(obj["btc_address"])

# Function to compare characters at the same position in two strings
def compare_addresses(addr1, addr2):
    if len(addr1) != len(addr2):
        return 0
    return sum(1 for a, b in zip(addr1, addr2) if a == b)

# Read BTC addresses from CSV and compare them with the addresses in the MongoDB collection
with open('addresses.csv', mode='r', newline='') as arquivo_csv:
    leitor_csv = csv.reader(arquivo_csv)

    for linha in leitor_csv:
        if linha:
            btc_address = linha[0]

            for address in wallets:
                if btc_address == address:
                    print("FOUND!!!")
                    break
                matches = compare_addresses(btc_address, address)
            
                print("ADDRESS DB", address)
                print("ADDRESS CSV:", btc_address)
                print(f"Compared with {address}: {matches} characters match at the same position.")
        else:
            print("Linha vazia encontrada.")
