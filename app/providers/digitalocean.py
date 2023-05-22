from app.providers import Proxy, Provider
import requests
from time import sleep


class DigitalOceanProvider(Provider):

    URL = 'https://api.digitalocean.com'

    def __init__(self, **config):
        self.config = config
        self.config['sshKeyIds'] = self.get_ssh_key_ids(config['sshKeyNames'])
        self.config['imageId'] = self.get_image_id(config['imageName'])
        self.config['projectId'] = self.get_project_id(config['projectName'])

    def get_ssh_key_ids(self, ssh_key_names):
        response = requests.get(
            url=DigitalOceanProvider.URL + '/v2/account/keys',
            headers={"Authorization": f"Bearer {self.config['token']}"},
            params={
                'per_page': 200
            },
        )

        data = response.json()
        ssh_keys = {k['name']: k['id'] for k in data['ssh_keys']}

        ssh_key_ids = [ssh_keys[k] for k in ssh_key_names if k in ssh_keys]

        return ssh_key_ids

    def get_image_id(self, image_name):
        response = requests.get(
            url=DigitalOceanProvider.URL + '/v2/snapshots',
            headers={"Authorization": f"Bearer {self.config['token']}"},
            params={
                'per_page': 200,
                'resource_type': 'droplet'
            },
        )
        data = response.json()

        for snapshot in data['snapshots']:
            if snapshot['name'] == image_name:
                return snapshot['id']

    def get_project_id(self, project_name):
        response = requests.get(
            url=DigitalOceanProvider.URL + '/v2/projects',
            headers={"Authorization": f"Bearer {self.config['token']}"},
            params={
                'per_page': 200,
            },
        )
        data = response.json()

        for project in data['projects']:
            if project['name'] == project_name:
                return project['id']

    def create(self, n: int) -> list['DigitalOceanProxy']:

        response = requests.post(
            url=DigitalOceanProvider.URL + '/v2/droplets',
            headers={"Authorization": f"Bearer {self.config['token']}"},
            json=dict(
                names=[self.config['name']] * n,
                region=self.config['region'],
                size=self.config['size'],
                image=self.config['imageId'],
                ssh_keys=self.config['sshKeyIds'],
                tags=self.config['tags'],
            ),
        )
        data = response.json()

        new_proxies = [DigitalOceanProxy(droplet['id'], self.config['token'])
                       for droplet in data['droplets']]

        return new_proxies


class DigitalOceanProxy(Proxy):

    def __init__(self, id, token):
        super().__init__()

        self.id = id
        self.token = token

        self.host = None

        while not self.host:
            response = requests.get(
                url=DigitalOceanProvider.URL + f'/v2/droplets/{self.id}',
                headers={"Authorization": f"Bearer {self.token}"},
            )
            data = response.json()
            for net in data['networks']['v4']:
                if net['type'] == 'public':
                    self.host = net['ip_address']
                    return
            sleep(5)

    def destroy(self):
        response = requests.delete(
            url=DigitalOceanProvider.URL + f'/v2/droplets/{self.id}',
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def __del__(self):
        self.destroy()
        super().__del__()
