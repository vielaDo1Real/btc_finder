import logging
import time
import multiprocessing


class BtcFindUtils:
    def __init__(self):
        pass
    
    # calculate the execution time
    def exec_time(self, start_time, mode):
        end_time = time.time()
        logging.info(f"Execution time: {end_time - start_time} seconds in {mode} mode")
    
    # get the number of CPU cores
    def get_cpu_cores(self):
        return multiprocessing.cpu_count()
    
    # organize the combination words
    def normalize_combination(self, combo):
        return " ".join(sorted(set(combo)))

    def int_to_hex(self, value):
        return hex(value)[2:].zfill(64)
