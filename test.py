import docker


client = docker.from_env()
healthy_containers = [container for container in client.containers.list(filters={"health": "healthy"})]


for i in healthy_containers:
    print(i.id,i.name,i.status)