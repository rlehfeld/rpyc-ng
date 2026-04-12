#!/usr/bin/env python
import time
import unittest
import rpyc
from rpyc.core import DEFAULT_CONFIG


class MyService(rpyc.Service):
    class exposed_Invoker(object):
        def __init__(self, callback, interval):
            self.callback = rpyc.async_(callback)
            self.interval = interval
            self.active = True
            self.thread = rpyc.worker(self.work)

        def exposed_stop(self):
            self.active = False
            self.thread.join()

        def work(self):
            while self.active:
                self.callback(time.monotonic())
                time.sleep(self.interval)

    def exposed_foo(self, x):
        time.sleep(2)
        return x * 17


@unittest.skipIf(
    DEFAULT_CONFIG['bind_threads'],
    "bind threads create additional ServingThreads in the background. Test makes no sense"
)
class Test_Multithreaded(unittest.TestCase):
    def setUp(self):
        self.conn = rpyc.connect_thread(remote_service=MyService)
        self.bgserver = rpyc.BgServingThread(self.conn, active=False)

    def tearDown(self):
        self.bgserver.stop()
        self.conn.close()

    def test_invoker(self):
        counter = [0]

        def callback(x):
            counter[0] += 1
            print(f"callback {x}")
        invoker = self.conn.root.Invoker(callback, 1)
        called = counter[0]
        print(f"callback called {called} times")
        self.assertTrue(called <= 1)
        counter[0] = 0

        print(f"direct {time.monotonic()}")
        time.sleep(3)
        print(f"direct {time.monotonic()}")
        called = counter[0]
        print(f"callback called {called} times")
        self.assertTrue(called == 0)

        self.bgserver.resume()
        print(f"direct {time.monotonic()}")
        time.sleep(3)
        print(f"direct {time.monotonic()}")
        self.bgserver.pause()
        # 3+3 sec = ~6 calls to callback
        called = counter[0]
        print(f"callback called {called} times")
        self.assertTrue(called >= 5)

        time.sleep(2)
        self.assertTrue(counter[0] == called)

        self.bgserver.resume()
        time.sleep(0.5)
        counter[0] = 0
        print(f"callback called {called} times")
        for i in range(3):
            print(f"foo{i} = {self.conn.root.foo(i)}")
        self.bgserver.pause()
        called = counter[0]
        print(f"callback called {called} times")
        # 3 * 2sec = 14 sec = ~6 extra calls to callback
        invoker.stop()
        self.assertTrue(called >= 5)


if __name__ == "__main__":
    unittest.main()
