import requests
from time import sleep
import docker
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = docker.from_env()

class DockerAlertHandler:
    def __init__(self, queue, host_address="http://localhost:8080", max_retries=3):
        self.queue = queue
        self.host_address = host_address
        self.raised_alerts = set()
        self.raised_alarms = set()
        self.max_retries = max_retries
        self.retry_attempts = {}  # Dictionary to track retry attempts

    def check_healthy_containers(self):
        return client.containers.list(filters={"health": "healthy"})

    def check_all_containers(self):
        return client.containers.list()

    def create_alert(self, severity, host, details, is_alarm, status):
        return {
            "severity": severity,
            "host": host,
            "details": details,
            "is_alarm": is_alarm,
            "status": status
        }

    def send_request(self, endpoint, alert, unit):
        if unit in self.retry_attempts and self.retry_attempts[unit] >= self.max_retries:
            logger.warning(f"Skipping {endpoint.capitalize()} for {unit}. Reached maximum retries.")
            return
        
        retry_count = self.retry_attempts.get(unit, 0)
        backoff_time = 1  # initial backoff time in seconds
        
        while retry_count < self.max_retries:
            try:
                logger.info(f"Sending {endpoint.capitalize()} Alert: {alert}")
                response = requests.post(f"{self.host_address}/{endpoint}", json=alert)
                response.raise_for_status()
                
                if response.status_code in [200, 201]:
                    if endpoint == "alerts":
                        (self.raised_alerts.add if not alert["is_alarm"] else self.raised_alarms.add)(unit)
                    elif endpoint == "clear-alert":
                        (self.raised_alerts.discard if not alert["is_alarm"] else self.raised_alarms.discard)(unit)
                    logger.info(f"{endpoint.capitalize()} request executed successfully")
                    self.retry_attempts.pop(unit, None)  # Clear retry attempts upon success
                    return  # Exit the loop if the request is successful
                else:
                    logger.error(f"Failed to {endpoint} alert with status code {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error {endpoint} alert: {e}")
            
            # Exponential backoff
            retry_count += 1
            self.retry_attempts[unit] = retry_count
            sleep(backoff_time)
            backoff_time *= 2  # Double the backoff time for the next retry

        logger.error(f"Exceeded maximum retries for {endpoint} service: {unit} and is_alarm: {alert['is_alarm']}")


    def process_event(self, event):
        service = event["service"]
        alert = self.create_alert("medium", "server2", f"The {service} container healthcheck failed", event["status"], "active")
        self.send_request("alerts", alert, service)

    def check_and_clear_alerts(self):
        healthy_container_names = {container.name for container in self.check_healthy_containers()}
        all_container_names = {container.name for container in self.check_all_containers()}
        
        for unit in list(self.raised_alerts):
            if unit in healthy_container_names or unit not in all_container_names:
                clear_alert = self.create_alert("medium", "server2", f"The {unit} container healthcheck failed", False, "cleared")
                self.send_request("clear-alert", clear_alert, unit)
        
        for unit in list(self.raised_alarms):
            if unit in healthy_container_names or unit not in all_container_names:
                clear_alert = self.create_alert("medium", "server2", f"The {unit} container healthcheck failed", True, "cleared")
                self.send_request("clear-alert", clear_alert, unit)

    def run(self):
        while True:
            try:
                if not self.queue.empty():
                    event = self.queue.get()
                    logger.info(f"Processing event: {event}")
                    self.process_event(event)
                    sleep(3)

                if self.raised_alerts or self.raised_alarms:
                    self.check_and_clear_alerts()

                sleep(10)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                sleep(1)