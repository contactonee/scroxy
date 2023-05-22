import yaml
from app.core.manager import Manager
import logging


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    logger.addHandler(handler)

    logger.info('Started')

    with open('settings.yaml') as fp:
        config = yaml.safe_load(fp)

    app = Manager(**config)
    app.run()


if __name__ == '__main__':
    main()
    
