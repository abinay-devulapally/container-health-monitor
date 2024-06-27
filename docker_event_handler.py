import docker
from time import sleep
from multiprocessing.pool import ThreadPool

client = docker.from_env()

class DockerEventHandler:
    def __init__(self, queue):
        self.queue = queue
        self.max_retries = 2
        self.processed_containers = set()

    def check_unhealthy_containers(self):
        return client.containers.list(filters={"health": "unhealthy"})
    
    def check_healthy_containers(self):
        return client.containers.list(filters={"health": "healthy"})
    
    def process_container(self, container, max_retries):
        retries = 1
        while retries < max_retries:
            if container in self.check_healthy_containers():
                break
            if container not in self.processed_containers:
                # print(f"#####In Queue ALERT##### current retries: {retries} container name {container.name}")
                self.queue.put({"service": container.name, "status": False})
                # print(f"Restarting container {container.name}")
                # container.restart()
                sleep(30)
            else:
                break
            retries += 1

        if retries == max_retries:
            # print(f"#####In Queue ALARM##### current retries: {retries} container name {container.name}")
            self.queue.put({"service": container.name, "status": True})
            self.processed_containers.add(container)

    def process_unhealthy_containers(self):
        unhealthy_containers = self.check_unhealthy_containers()
        pool = ThreadPool(processes=5)
        pool.map(lambda container: self.process_container(container, self.max_retries), unhealthy_containers)

    def run(self):
        while True:
            unhealthy_containers = self.check_unhealthy_containers()
            healthy_containers = self.check_healthy_containers()

            # Remove healthy containers from processed_containers
            print("START")
            for container in healthy_containers:
                self.processed_containers.discard(container)

            if unhealthy_containers:
                self.process_unhealthy_containers()
            
            sleep(30)
