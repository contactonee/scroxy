from scroxy.providers import Provider, Proxy
from scroxy.providers.digitalocean import DigitalOceanProvider
import logging
from time import sleep, time
import subprocess
from pathlib import Path
import signal
from typing import List
import htpasswd

logger = logging.getLogger(__name__)

SQUID_CONFIG_DIR = Path('scroxy/squid')


class Server:

    IDLE, ACTIVE = 0, 1

    def __init__(self, **config):
        self.state = Server.ACTIVE
        self.config: dict = config
        self.providers: List[Provider] = []
        self.proxies: List[Proxy] = []

        for provider_config in config['providers']:
            try:
                if provider_config['type'] == 'digitalocean':
                    provider = DigitalOceanProvider(**provider_config)
                else:
                    provider = None
            except Exception as e:
                provider = None
                logger.debug(e.with_traceback())

            if provider:
                self.providers.append(provider)
                logger.info('Registered "%s" provider',
                            provider_config['type'])
            else:
                logger.error(
                    'Error during registration "%s" provider. ', provider_config['type'])

        if len(self.providers) == 0:
            logger.error('No valid provider')

        self.configure()

    def configure(self):
        
        with open(SQUID_CONFIG_DIR / 'passwords', 'w') as fp:
            pass

        with htpasswd.Basic(SQUID_CONFIG_DIR / 'passwords', mode='md5') as fp:
            try:
                fp.add(self.config['proxy']['auth']['username'],
                       self.config['proxy']['auth']['password'])
            except htpasswd.UserExists:
                fp.change_password(self.config['proxy']['auth']['username'],
                                   self.config['proxy']['auth']['password'])
        
        with open(SQUID_CONFIG_DIR / 'peers.conf', 'w') as fp:
            pass

        with open(SQUID_CONFIG_DIR / 'scroxy.conf.temp') as fp, \
                open(SQUID_CONFIG_DIR / 'scroxy.conf', 'w') as conf_fp:
            str = fp.read()
            conf_fp.write(str.format(
                basic_auth=self.config['proxy']['auth']['path'],
                http_port=self.config['proxy']['port']
            ))

    def spinup(self):

        new_proxies = self.spawn(
            self.config['instance']['scaling']['max'] - len(self.proxies))
        self.proxies.extend(new_proxies)

        if len(self.proxies) < self.config['instance']['scaling']['max']:
            logger.error("Proxy instances undercount!")

        self.export_proxies()

    def spawn(self, n) -> List[Proxy]:

        n = max(n, 0)
        new_proxies = []

        for provider in self.providers:

            if n <= 0:
                break

            created = provider.create(n)
            new_proxies.extend(created)
            n -= len(created)

        if n > 0:
            logger.warning(
                f'Unable to spawn enough instances. Requested {n+len(new_proxies)}, spawned {len(new_proxies)}.')

        logger.debug(f'Spawned {len(new_proxies)} instances')

        return new_proxies

    def spindown(self):
        while len(self.proxies) > self.config['instance']['scaling']['min']:
            self.proxies.pop(0).destroy()

        self.export_proxies()

        subprocess.run([
            self.config['proxy']['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
            '-k', 'rotate'
        ])

    def export_proxies(self):

        with open(SQUID_CONFIG_DIR / 'peers.conf', 'w') as peers_file:
            for proxy in self.proxies:
                peers_file.write(
                    "cache_peer {host} parent {port} 0 no-query round-robin login={username}:{password}\n".format(
                        host=proxy.host,
                        port=self.config['instance']['port'],
                        username=self.config['instance']['username'],
                        password=self.config['instance']['password']
                    ))

        subprocess.run([
            self.config['proxy']['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
            '-k', 'reconfigure'
        ])

    def run(self):

        def close(signum, frame):
            logger.info('Destroying all instances')

            for proxy in self.proxies:
                proxy.destroy()

            logger.info('Shutting down Squid service')
            subprocess.run([
                self.config['proxy']['squid']['path'],
                '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
                '-k', 'interrupt'
            ])
            exit(0)

        signal.signal(signal.SIGINT, close)

        logger.info('Starting Squid process')

        subprocess.run([
            self.config['proxy']['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf'
        ])

        self.spinup()

        logfile = SQUID_CONFIG_DIR / 'logs' / 'access.log'
        try:
            last_size = logfile.stat().st_size
        except FileNotFoundError:
            last_size = 0
        last_active = time()

        logger.info('Listening to access log')

        while True:
            try:
                curr_size = logfile.stat().st_size
            except FileNotFoundError:
                curr_size = 0

            if self.state == Server.IDLE:
                if curr_size > last_size:
                    logger.info(
                        'Registered activity. Spinning up instances')
                    self.spinup()
                    last_active = time()
                    self.state = Server.ACTIVE

            elif self.state == Server.ACTIVE:
                if curr_size > last_size:
                    last_active = time()
                elif time() - last_active >= self.config['instance']['scaling']['downscaleDelay']:
                    logger.info(
                        'No activity for the set timeout. Going idle')
                    self.spindown()
                    self.state = Server.IDLE

            last_size = curr_size
            sleep(0.1)
