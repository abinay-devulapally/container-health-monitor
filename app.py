
from docker_alert_handler import DockerAlertHandler
from docker_event_handler import DockerEventHandler
import multiprocessing

if __name__ == "__main__":
    queue = multiprocessing.Queue()

    alert_handler = DockerAlertHandler(queue)
    event_handler = DockerEventHandler(queue)

    process1 = multiprocessing.Process(target=alert_handler.run)
    process2 = multiprocessing.Process(target=event_handler.run)

    process1.start()
    process2.start()

    process1.join()
    process2.join()