from app.providers import Provider, Proxy
from app.providers.digitalocean import DigitalOceanProvider
import logging
from time import sleep, time
import subprocess
import signal
from pathlib import Path

logger = logging.getLogger(__name__)

SQUID_CONFIG_DIR = Path('/Users/contactone/.scroxy')


class Manager:

    IDLE, ACTIVE = 0, 1

    def __init__(self, **config):
        self.state = Manager.IDLE
        self.config: dict = config
        self.providers: list[Provider] = []
        self.proxies: list[Proxy] = []

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
            logger.critical('No valid provider')
            raise RuntimeError()

    def spinup(self):
        for provider in self.providers:

            n = self.config['instance']['scaling']['max'] - len(self.proxies)
            if n <= 0:
                break

            new_proxies = provider.create(n)
            self.proxies.extend(new_proxies)

        if len(self.proxies) < self.config['instance']['scaling']['max']:
            logger.error("Proxy instances undercount!")

        self.export_proxies()

    def spindown(self):

        while len(self.proxies) > self.config['instance']['scaling']['min']:
            self.proxies.pop(0).destroy()

        self.export_proxies()

        subprocess.run([
            self.config['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
            '-k', 'rotate'
        ])

    def __str__(self):
        return

    def export_proxies(self):

        with open(SQUID_CONFIG_DIR / 'peers.conf', 'w') as peers_file:
            for proxy in self.proxies:
                peers_file.write(
                    f"cache_peer {proxy.host} parent {self.config['instance']['port']} 0 no-query round-robin\n")

        subprocess.run([
            self.config['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
            '-k', 'reconfigure'
        ])

    def run(self):

        subprocess.run([
            self.config['proxy']['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf'
        ])

        logfile = SQUID_CONFIG_DIR / 'logs' / 'access.log'
        try:
            last_size = logfile.stat().st_size
        except FileNotFoundError:
            last_size = 0
        last_active = time()

        while True:
            try:
                try:
                    curr_size = logfile.stat().st_size
                except FileNotFoundError:
                    curr_size = 0
    
                if self.state == Manager.IDLE:
                    if curr_size > last_size:
                        self.spinup()
                        last_active = time()
                        self.state = Manager.ACTIVE

                elif self.state == Manager.ACTIVE:
                    if curr_size > last_size:
                        last_active = time()
                    elif time() - last_active >= self.config['instance']['scaling']['downscaleDelay']:
                        self.spindown()
                        self.state = Manager.IDLE
                last_size = curr_size
                sleep(0.1)
            except KeyboardInterrupt:
                break

        for proxy in self.proxies:
            proxy.destroy()

        subprocess.run([
            self.config['proxy']['squid']['path'],
            '-f', SQUID_CONFIG_DIR / 'scroxy.conf',
            '-k', 'shutdown'
        ])
