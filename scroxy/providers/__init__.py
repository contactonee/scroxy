from time import time
from abc import ABC, abstractmethod
from typing import List


class Provider:

    name = None

    def create(self, n: int) -> List['Proxy']:
        pass


class Proxy:

    @property
    def host(self):
        pass

    def destroy(self):
        pass
