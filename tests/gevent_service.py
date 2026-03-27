from gevent import monkey
monkey.patch_all()
import gevent  # noqa, E402 need to be imported after monkey patch

import rpyc  # noqa, E402 need to be imported after monkey patch
from rpyc.utils.server import GeventServer  # noqa, E402 need to be imported after monkey patch


class GeventService(rpyc.SlaveService):
    @staticmethod
    def get_ident():
        return gevent.monkey.get_original('threading', 'get_ident')()


if __name__ == "__main__":
    server = GeventServer(GeventService, port=18878, auto_register=False)
    server.logger.quiet = False
    server._listen()
    print(GeventService.get_ident())
    server.start()
