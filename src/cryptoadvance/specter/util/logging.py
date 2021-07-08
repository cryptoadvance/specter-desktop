import logging

logger = logging.getLogger(__name__)


class DuplicateFilter(logging.Filter):
    """A Filter filtering out messages coming in multiple times"""

    def __init__(self, name=""):
        super().__init__(name)
        self.last_log_count = 0
        self.last_log = "Something to compare with which is definitely not a logline"

    def filter(self, record):
        # add other fields if you need more granular comparison, depends on your app

        if record.module == "logging":
            return True  # maybe it's me logging

        current_log = (record.module, record.levelno, record.msg)
        if current_log == self.last_log:
            self.last_log_count = self.last_log_count + 1
            self.last_log = current_log
            return False
        else:
            if self.last_log_count > 0:
                logger.info(
                    f" ---=+ former message repeated {self.last_log_count} times +=---"
                )
                self.last_log = current_log
                self.last_log_count = 0
                return True
            else:
                self.last_log = current_log
                return True
