import psutil


class HardwareMonitor:
    def __init__(self, refresh_interval=1):
        self.refresh_interval = refresh_interval

    def get_performance_data(self):
        """Captura as métricas do sistema."""
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent
        threads = psutil.Process().num_threads()
        return cpu_usage, ram_usage, threads

    def update_hardware_monitor(self, hardware_progress):
        """Atualiza as métricas no tqdm."""
        cpu, ram, threads = self.get_performance_data()
        hardware_progress.set_description(
            f"CPU: {cpu:.1f}% | RAM: {ram:.1f}% | Threads: {threads}"
        )
        hardware_progress.n = 1  # Atualiza o contador fictício
        hardware_progress.refresh()
