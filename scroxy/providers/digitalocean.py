from scroxy.providers import Proxy, Provider
import requests
from requests.adapters import HTTPAdapter
from time import sleep
import logging
from typing import List

logger = logging.getLogger(__name__)


class DigitalOceanProvider(Provider):

    name = 'digitalocean'
    URL = 'https://api.digitalocean.com'

    def __init__(self, **config):
        self.config = config

        self.session = requests.Session()
        self.session.mount('http://', HTTPAdapter(max_retries=10))
        self.session.headers.update(
            {"Authorization": f"Bearer {self.config['token']}"})

        logger.debug('Loading SSH keys')
        self.config['sshKeyIds'] = self.get_ssh_key_ids(config['sshKeyNames'])
        logger.debug('Loading images')
        self.config['imageId'] = self.get_image_id(config['imageName'])
        logger.debug('Loading projects')
        self.config['projectId'] = self.get_project_id(config['projectName'])


    def get_ssh_key_ids(self, ssh_key_names):
        response = self.session.get(
            url=DigitalOceanProvider.URL + '/v2/account/keys',
            params={
                'per_page': 200
            },
        )
        if response.status_code != 200:
            logger.error(response.json()['message'])
            return []

        data = response.json()
        ssh_keys = {k['name']: k['id'] for k in data['ssh_keys']}
        ssh_key_ids = [ssh_keys[k] for k in ssh_key_names if k in ssh_keys]

        return ssh_key_ids

    def get_image_id(self, image_name):
        response = self.session.get(
            url=DigitalOceanProvider.URL + '/v2/snapshots',
            params={
                'per_page': 200,
                'resource_type': 'droplet'
            },
        )
        if response.status_code != 200:
            try:
                msg = response.json()['message']
            except:
                msg = ''
            logger.error(msg)
            raise RuntimeError(msg)

        data = response.json()

        for snapshot in data['snapshots']:
            if snapshot['name'] == image_name:
                return snapshot['id']

    def get_project_id(self, project_name):
        response = self.session.get(
            url=DigitalOceanProvider.URL + '/v2/projects',
            params={
                'per_page': 200,
            },
        )
        if response.status_code != 200:
            try:
                msg = response.json()['message']
            except:
                msg = ''
            logger.error(msg)
            return None

        data = response.json()

        for project in data['projects']:
            if project['name'] == project_name:
                return project['id']

        logger.error(f'No project with name "{project_name}"')
        return None

    def create(self, n: int) -> List['DigitalOceanProxy']:

        n = min(n, self.config['max'])
        if n <= 0:
            return []

        response = self.session.post(
            url=DigitalOceanProvider.URL + '/v2/droplets',
            json=dict(
                names=[self.config['name']] * n,
                region=self.config['region'],
                size=self.config['size'],
                image=self.config['imageId'],
                ssh_keys=self.config['sshKeyIds'],
                tags=self.config['tags'],
            ),
        )
        if response.status_code != 202:
            try:
                msg = response.json()['message']
            except:
                msg = ''
            logger.error(msg)
            return []

        data = response.json()

        new_proxies = [DigitalOceanProxy(droplet['id'], self.session)
                       for droplet in data['droplets']]

        if self.config['projectId'] is not None:
            response = self.session.post(
                url=DigitalOceanProvider.URL +
                f"/v2/projects/{self.config['projectId']}/resources",
                json=dict(
                    resources=['do:droplet:' + str(droplet.id)
                               for droplet in new_proxies]
                )
            )

        return new_proxies


class DigitalOceanProxy(Proxy):

    def __init__(self,
                 id,
                 session: requests.Session):

        self.id = id
        self.session = session
        self._host = None

    @property
    def host(self):
        while not self._host:
            response = self.session.get(
                url=DigitalOceanProvider.URL + f'/v2/droplets/{self.id}',
            )
            data = response.json()['droplet']
            for net in data['networks']['v4']:
                if net['type'] == 'public':
                    self._host = net['ip_address']
                    return self._host
            sleep(5)
        return self._host

    def destroy(self):
        response = self.session.delete(
            url=DigitalOceanProvider.URL + f'/v2/droplets/{self.id}',
        )
