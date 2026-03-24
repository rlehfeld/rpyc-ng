from __future__ import with_statement
import rpyc
import unittest
try:
    import numpy as np
    _numpy_import_failed = False
except Exception:
    _numpy_import_failed = True


class MyService(rpyc.Service):

    def exposed_create_array(self, array):
        return np.array(array, dtype=np.int64, copy=True)


@unittest.skipIf(_numpy_import_failed, "Skipping since numpy cannot be imported")
class TestNumpy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = rpyc.utils.server.OneShotServer(MyService, port=0, protocol_config={"allow_pickle": True})
        cls.server.logger.quiet = False
        cls.thd = cls.server._start_in_thread()
        cls.conn = rpyc.connect("localhost", port=cls.server.port, config={"allow_pickle": True})

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.server.close()
        cls.thd.join()

    def test_numpy(self):
        remote_array = self.conn.root.create_array(np.array([0.]))
        self.assertEqual(remote_array[0], 0)
        self.assertIsInstance(remote_array[0], np.int64)


if __name__ == "__main__":
    unittest.main()
