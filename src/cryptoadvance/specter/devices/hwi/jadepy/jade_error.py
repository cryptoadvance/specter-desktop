class JadeError(Exception):
    def __init__(self, code, message, data):
        self.code = code
        self.message = message
        self.data = data

    def __repr__(self):
        return (
            "JadeError: "
            + str(self.code)
            + " - "
            + self.message
            + " (Data: "
            + repr(self.data)
            + ")"
        )

    def __str__(self):
        return repr(self)
