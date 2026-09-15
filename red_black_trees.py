import types


class node:
    """Red black tree Node."""

    def __init__(self, key):
        """Initialize the values of the node."""
        self.key = key
        self.red = True
        self.black = None


node1 = node(1)
node2 = node(2)

print("hello world")
