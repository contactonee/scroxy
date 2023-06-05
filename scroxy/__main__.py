import yaml
from . import Server
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

    app = Server(**config)
    app.run()


if __name__ == '__main__':
    main()