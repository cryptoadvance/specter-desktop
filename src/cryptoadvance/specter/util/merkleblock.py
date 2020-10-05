# Code adopted from https://github.com/jimmysong/pb-exercises/
import hashlib
import math

from io import BytesIO


def hash256(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()


def read_varint(s):
    """read_varint reads a variable integer from a stream"""
    i = s.read(1)[0]
    if i == 0xFD:
        # 0xfd means the next two bytes are the number
        return little_endian_to_int(s.read(2))
    elif i == 0xFE:
        # 0xfe means the next four bytes are the number
        return little_endian_to_int(s.read(4))
    elif i == 0xFF:
        # 0xff means the next eight bytes are the number
        return little_endian_to_int(s.read(8))
    else:
        # anything else is just the integer
        return i


def merkle_parent(hash1, hash2):
    """Takes the binary hashes and calculates the hash256"""
    # return the hash256 of hash1 + hash2
    return hash256(hash1 + hash2)


def merkle_parent_level(hashes):
    """Takes a list of binary hashes and returns a list that's half
    the length"""
    # if the list has exactly 1 element raise an error
    if len(hashes) == 1:
        raise RuntimeError("Cannot take a parent level with only 1 item")
    # if the list has an odd number of elements, duplicate the last one
    #       and put it at the end so it has an even number of elements
    if len(hashes) % 2 == 1:
        hashes.append(hashes[-1])
    # initialize parent level
    parent_level = []
    # loop over every pair (use: for i in range(0, len(hashes), 2))
    for i in range(0, len(hashes), 2):
        # get the merkle parent of i and i+1 hashes
        parent = merkle_parent(hashes[i], hashes[i + 1])
        # append parent to parent level
        parent_level.append(parent)
    # return parent level
    return parent_level


def merkle_root(hashes):
    """Takes a list of binary hashes and returns the merkle root"""
    # current level starts as hashes
    current_level = hashes
    # loop until there's exactly 1 element
    while len(current_level) > 1:
        # current level becomes the merkle parent level
        current_level = merkle_parent_level(current_level)
    # return the 1st item of current_level
    return current_level[0]


def little_endian_to_int(b):
    """little_endian_to_int takes byte sequence as a little-endian number.
    Returns an integer"""
    # use the int.from_bytes(b, <endianness>) method
    return int.from_bytes(b, "little")


def int_to_little_endian(n, length):
    """endian_to_little_endian takes an integer and returns the little-endian
    byte sequence of length"""
    # use the to_bytes method of n
    return n.to_bytes(length, "little")


def bytes_to_bit_field(some_bytes):
    flag_bits = []
    # iterate over each byte of flags
    for byte in some_bytes:
        # iterate over each bit, right-to-left
        for _ in range(8):
            # add the current bit (byte & 1)
            flag_bits.append(byte & 1)
            # rightshift the byte 1
            byte >>= 1
    return flag_bits


class Block:
    command = b"block"

    def __init__(
        self, version, prev_block, merkle_root, timestamp, bits, nonce, tx_hashes=None
    ):
        self.version = version
        self.prev_block = prev_block
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.tx_hashes = tx_hashes
        self.merkle_tree = None

    @classmethod
    def parse_header(cls, s):
        """Takes a byte stream and parses a block. Returns a Block object"""
        # s.read(n) will read n bytes from the stream
        # version - 4 bytes, little endian, interpret as int
        version = little_endian_to_int(s.read(4))
        # prev_block - 32 bytes, little endian (use [::-1] to reverse)
        prev_block = s.read(32)[::-1]
        # merkle_root - 32 bytes, little endian (use [::-1] to reverse)
        merkle_root = s.read(32)[::-1]
        # timestamp - 4 bytes, little endian, interpret as int
        timestamp = little_endian_to_int(s.read(4))
        # bits - 4 bytes
        bits = s.read(4)
        # nonce - 4 bytes
        nonce = s.read(4)
        # initialize class
        return cls(version, prev_block, merkle_root, timestamp, bits, nonce)

    @classmethod
    def parse(cls, s):
        b = cls.parse_header(s)
        num_txs = read_varint(s)
        tx_hashes = []
        for _ in range(num_txs):
            t = Tx.parse(s)
            tx_hashes.append(t.hash())
        b.tx_hashes = tx_hashes
        return b

    def serialize(self):
        """Returns the 80 byte block header"""
        # version - 4 bytes, little endian
        result = int_to_little_endian(self.version, 4)
        # prev_block - 32 bytes, little endian
        result += self.prev_block[::-1]
        # merkle_root - 32 bytes, little endian
        result += self.merkle_root[::-1]
        # timestamp - 4 bytes, little endian
        result += int_to_little_endian(self.timestamp, 4)
        # bits - 4 bytes
        result += self.bits
        # nonce - 4 bytes
        result += self.nonce
        return result

    def hash(self):
        """Returns the hash256 interpreted little endian of the block"""
        # serialize
        s = self.serialize()
        # hash256
        h256 = hash256(s)
        # reverse
        return h256[::-1]

    def id(self):
        """Human-readable hexadecimal of the block hash"""
        return self.hash().hex()

    def bip9(self):
        """Returns whether this block is signaling readiness for BIP9"""
        # BIP9 is signalled if the top 3 bits are 001
        # remember version is 32 bytes so right shift 29 (>> 29) and see if
        # that is 001
        return self.version >> 29 == 0b001

    def bip91(self):
        """Returns whether this block is signaling readiness for BIP91"""
        # BIP91 is signalled if the 5th bit from the right is 1
        # shift 4 bits to the right and see if the last bit is 1
        return self.version >> 4 & 1 == 1

    def bip141(self):
        """Returns whether this block is signaling readiness for BIP141"""
        # BIP91 is signalled if the 2nd bit from the right is 1
        # shift 1 bit to the right and see if the last bit is 1
        return self.version >> 1 & 1 == 1

    def target(self):
        """Returns the proof-of-work target based on the bits"""
        # last byte is exponent
        exponent = self.bits[-1]
        # the first three bytes are the coefficient in little endian
        coefficient = little_endian_to_int(self.bits[:-1])
        # the formula is:
        # coefficient * 256**(exponent-3)
        return coefficient * 256 ** (exponent - 3)

    def difficulty(self):
        """Returns the block difficulty based on the bits"""
        # note difficulty is (target of lowest difficulty) / (self's target)
        # lowest difficulty has bits that equal 0xffff001d
        lowest = 0xFFFF * 256 ** (0x1D - 3)
        return lowest / self.target()

    def check_pow(self):
        """Returns whether this block satisfies proof of work"""
        # get the hash256 of the serialization of this block
        h256 = hash256(self.serialize())
        # interpret this hash as a little-endian number
        proof = little_endian_to_int(h256)
        # return whether this integer is less than the target
        return proof < self.target()

    def validate_merkle_root(self):
        """Gets the merkle root of the tx_hashes and checks that it's
        the same as the merkle root of this block.
        """
        # reverse all the transaction hashes (self.tx_hashes)
        hashes = [h[::-1] for h in self.tx_hashes]
        # get the Merkle Root
        root = merkle_root(hashes)
        # reverse the Merkle Root
        # return whether self.merkle root is the same as
        # the reverse of the calculated merkle root
        return root[::-1] == self.merkle_root


class MerkleTree:
    def __init__(self, total):
        self.total = total
        # compute max depth math.ceil(math.log(self.total, 2))
        self.max_depth = math.ceil(math.log(self.total, 2))
        # initialize the nodes property to hold the actual tree
        self.nodes = []
        # loop over the number of levels (max_depth+1)
        for depth in range(self.max_depth + 1):
            # the number of items at this depth is
            # math.ceil(self.total / 2**(self.max_depth - depth))
            num_items = math.ceil(self.total / 2 ** (self.max_depth - depth))
            # create this level's hashes list with the right number of items
            level_hashes = [None] * num_items
            # append this level's hashes to the merkle tree
            self.nodes.append(level_hashes)
        # set the pointer to the root (depth=0, index=0)
        self.current_depth = 0
        self.current_index = 0
        self.proved_txs = []

    def __repr__(self):
        result = []
        for depth, level in enumerate(self.nodes):
            items = []
            for index, h in enumerate(level):
                if h is None:
                    short = "None"
                else:
                    short = "{}...".format(h.hex()[:8])
                if depth == self.current_depth and index == self.current_index:
                    items.append("*{}*".format(short[:-2]))
                else:
                    items.append("{}".format(short))
            result.append(", ".join(items))
        return "\n".join(result)

    def up(self):
        # reduce depth by 1 and halve the index
        self.current_depth -= 1
        self.current_index //= 2

    def left(self):
        # increase depth by 1 and double the index
        self.current_depth += 1
        self.current_index *= 2

    def right(self):
        # increase depth by 1 and double the index + 1
        self.current_depth += 1
        self.current_index = self.current_index * 2 + 1

    def root(self):
        return self.nodes[0][0]

    def set_current_node(self, value):
        self.nodes[self.current_depth][self.current_index] = value

    def get_current_node(self):
        return self.nodes[self.current_depth][self.current_index]

    def get_left_node(self):
        return self.nodes[self.current_depth + 1][self.current_index * 2]

    def get_right_node(self):
        return self.nodes[self.current_depth + 1][self.current_index * 2 + 1]

    def is_leaf(self):
        return self.current_depth == self.max_depth

    def right_exists(self):
        return len(self.nodes[self.current_depth + 1]) > self.current_index * 2 + 1

    def populate_tree(self, flag_bits, hashes):
        # populate until we have the root
        while self.root() is None:
            # if we are a leaf, we know this position's hash
            if self.is_leaf():
                # get the next bit from flag_bits: flag_bits.pop(0)
                flag_bit = flag_bits.pop(0)
                # get the current hash from hashes: hashes.pop(0)
                current_hash = hashes.pop(0)
                # set the current node in the merkle tree to the current hash
                self.set_current_node(current_hash)
                # if our flag bit is 1, add to the self.proved_txs array
                if flag_bit == 1:
                    self.proved_txs.append(current_hash[::-1])
                # go up a level
                self.up()
            # else
            else:
                # get the left hash
                left_hash = self.get_left_node()
                # if we don't have the left hash
                if left_hash is None:
                    # if the next flag bit is 0, the next hash is our current node
                    if flag_bits.pop(0) == 0:
                        # set the current node to be the next hash
                        self.set_current_node(hashes.pop(0))
                        # sub-tree doesn't need calculation, go up
                        self.up()
                    # else
                    else:
                        # go to the left node
                        self.left()
                elif self.right_exists():
                    # get the right hash
                    right_hash = self.get_right_node()
                    # if we don't have the right hash
                    if right_hash is None:
                        # go to the right node
                        self.right()
                    # else
                    else:
                        # combine the left and right hashes
                        self.set_current_node(merkle_parent(left_hash, right_hash))
                        # we've completed this sub-tree, go up
                        self.up()
                # else
                else:
                    # combine the left hash twice
                    self.set_current_node(merkle_parent(left_hash, left_hash))
                    # we've completed this sub-tree, go up
                    self.up()
        if len(hashes) != 0:
            raise RuntimeError("hashes not all consumed {}".format(len(hashes)))
        for flag_bit in flag_bits:
            if flag_bit != 0:
                raise RuntimeError("flag bits not all consumed")


class MerkleBlock:
    command = b"merkleblock"

    def __init__(self, header, total, hashes, flags):
        self.header = header
        self.total = total
        self.hashes = hashes
        self.flags = flags
        self.merkle_tree = None

    def __repr__(self):
        result = "{}\n".format(self.total)
        for h in self.hashes:
            result += "\t{}\n".format(h.hex())
        result += "{}".format(self.flags.hex())

    def hash(self):
        return self.header.hash()

    def id(self):
        return self.header.id()

    @classmethod
    def parse(cls, s):
        """Takes a byte stream and parses a merkle block. Returns a Merkle Block object"""
        # s.read(n) will read n bytes from the stream
        # header - use Block.parse_header with the stream
        header = Block.parse_header(s)
        # total number of transactions (4 bytes, little endian)
        total = little_endian_to_int(s.read(4))
        # number of hashes is a varint
        num_txs = read_varint(s)
        # initialize the hashes array
        hashes = []
        # loop through the number of hashes times
        for _ in range(num_txs):
            # each hash is 32 bytes, little endian
            hashes.append(s.read(32)[::-1])
        # get the length of the flags field as a varint
        flags_length = read_varint(s)
        # read the flags field
        flags = s.read(flags_length)
        # initialize class
        return cls(header, total, hashes, flags)

    def is_valid(self):
        """Verifies whether the merkle tree information validates to the merkle root"""
        # use bytes_to_bit_field on self.flags to get the flag_bits
        flag_bits = bytes_to_bit_field(self.flags)
        # set hashes to be the reversed hashes of everything in self.hashes
        hashes = [h[::-1] for h in self.hashes]
        # initialize the merkle tree with self.total
        self.merkle_tree = MerkleTree(self.total)
        # populate_tree with flag_bits and hashes
        self.merkle_tree.populate_tree(flag_bits, hashes)
        # check if the computed root [::-1] is the same as the merkle root
        return self.merkle_tree.root()[::-1] == self.header.merkle_root

    def proved_txs(self):
        """Returns the list of proven transactions from the Merkle block"""
        if self.merkle_tree is None:
            return []
        else:
            return self.merkle_tree.proved_txs


def is_valid_merkle_proof(
    proof_hex, target_tx_hex, target_block_hash_hex, target_merkle_root_hex=None
):
    """
    Validate a `target_tx` and `target_block_hash` are part of a BIP37 merkle `proof`
    """

    mb = MerkleBlock.parse(BytesIO(bytes.fromhex(proof_hex)))

    if mb.is_valid() is not True:
        return False

    if mb.proved_txs()[0].hex() != target_tx_hex:
        return False

    if target_merkle_root_hex is not None:
        if mb.merkle_tree.root()[::-1].hex() != target_merkle_root_hex:
            return False

    if mb.hash().hex() != target_block_hash_hex:
        return False

    return True
