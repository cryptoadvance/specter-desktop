# Code adopted from https://github.com/jimmysong/pybtcfork/blob/master/helper.py

import hashlib

def double_sha256(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()


def int_to_little_endian(n, length):
    '''endian_to_little_endian takes an integer and returns the little-endian
    byte sequence of length'''
    # use the int.to_bytes(length, <endianness>) method
    return n.to_bytes(length, 'little')


def merkle_parent(hash1, hash2):
    '''Takes the binary hashes and calculates the double-sha256'''
    # return the double-sha256 of hash1 + hash2
    return double_sha256(hash1 + hash2)


def merkle_parent_level(hash_list):
    '''Takes a list of binary hashes and returns a list that's half
    the length'''
    # Exercise 2.2: if the list has exactly 1 element raise an error
    if len(hash_list) == 1:
        raise RuntimeError('Cannot take a parent level with only 1 item')
    # Exercise 3.2: if the list has an odd number of elements, duplicate the
    #               last one and put it at the end so it has an even number
    #               of elements
    if len(hash_list) % 2 == 1:
        hash_list.append(hash_list[-1])
    # Exercise 2.2: initialize next level
    parent_level = []
    # Exercise 2.2: loop over every pair
    #               (use: for i in range(0, len(hash_list), 2))
    for i in range(0, len(hash_list), 2):
        # Exercise 2.2: get the merkle parent of i and i+1 hashes
        parent = merkle_parent(hash_list[i], hash_list[i+1])
        # Exercise 2.2: append parent to parent level
        parent_level.append(parent)
    # Exercise 2.2: return parent level
    return parent_level


def merkle_root(hash_list):
    '''Takes a list of binary hashes and returns the merkle root
    '''
    # current level starts as hash_list
    current_level = hash_list
    # loop until there's exactly 1 element
    while len(current_level) > 1:
        # current level becomes the merkle parent level
        current_level = merkle_parent_level(current_level)
    # return the 1st item of current_level
    return current_level[0]


def hex_merkleroot(tx_hashes_hex):
    current_level = [bytes.fromhex(x)[::-1] for x in tx_hashes_hex]
    return merkle_root(current_level)[::-1].hex()

def calc_block_hash(version, prev_block_hash, merkle_root, timestamp, bits, nonce):
    # all input values are human readable (no bytes)

    # calculate an 80 byte header and then dsha256hex it
    result = int_to_little_endian(version, 4)
    # prev_block - 32 bytes, little endian
    result += bytes.fromhex(prev_block_hash)[::-1]
    # merkle_root - 32 bytes, little endian
    result += bytes.fromhex(merkle_root)[::-1]
    # timestamp - 4 bytes, little endian
    result += int_to_little_endian(timestamp, 4)
    # bits - 4 bytes
    result += bytes.fromhex(bits)[::-1]
    # nonce - 4 bytes
    result += int_to_little_endian(nonce, 4)
    return double_sha256(result)[::-1].hex()
