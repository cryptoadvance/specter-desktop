import logging
import threading
import time

logger = logging.getLogger(__name__)


class Checker:
    """
    Checker class that calls the periodic callback.
    If you want to force-check within the next second
    set checker.last_check to 0.
    """

    def __init__(self, callback, period=600, desc="unknown"):
        """Checker Contructor
        :param callback: a function to be called periodically
        :param period: defines the waiting time in seconds. If you specify values below 1, it won't sleep anymore
        :param desc: specifies an optional description used in logging
        """
        self.desc = desc
        self.callback = callback
        self.last_check = 0
        self.period = period
        self.running = False
        self.error_counter = 0

    def start(self):
        if not self.running:
            self.running = True
            self.error_counter = 0
            self.thread = threading.Thread(target=self.loop)
            self.thread.daemon = True
            self.thread.start()
        logger.info(f"Checker {self.desc} started with period {self.period}")

    def stop(self):
        logger.info(f"Checker {self.desc} stopped.")
        self.running = False

    def loop(self):
        self._execute(first_execution=True)
        while self.running:
            # check if it's time to update
            if time.time() - self.last_check >= self.period:
                self._execute()
            # wait 1 second
            self._sleep()

    def _execute(self, first_execution=False):
        try:
            t0 = time.time()
            self.callback()
            dt = time.time() - t0
            if first_execution:
                logger.info(
                    "Checker executed within %.3f seconds. This message won't show again until stopped and started."
                    % dt
                )
        except Exception as e:
            if self.error_counter < 5:
                logger.error(e)
                self.error_counter = self.error_counter + 1
            if self.error_counter == 4:
                logger.error("The above Error-Message is now suppressed!")
        finally:
            self.last_check = time.time()

    @property
    def period(self):
        return self._period

    @period.setter
    def period(self, value):
        self._period = value
        logger.info(f"Checker {self.desc} Checking every {self.period} seconds now")

    def _sleep(self):
        if self.period > 1:
            time.sleep(1)
        else:
            pass  # make tests as fast as possible
