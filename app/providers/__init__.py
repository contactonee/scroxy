from time import time
from abc import ABC, abstractmethod


class Provider(ABC):

    @abstractmethod
    def create(self, n: int) -> list['Proxy']:
        pass


class Proxy(ABC):

    @property
    @abstractmethod
    def host(self):
        pass

    @abstractmethod
    def destroy(self):
        pass
