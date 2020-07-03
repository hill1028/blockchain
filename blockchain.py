# {
#     "index": 0,
#     "timestamp": "",
#     "transactions": [
#         {
#             "sender": "",
#             "recipient": "",
#             "amount": 5
#         }
#     ],
#     "proof": "",
#     "previous_hash": ""
#
# }
import hashlib
import json
from time import time
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request
from uuid import uuid4

class Blockchain:

    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(proof=100, previous_hash=1)

    def register_node(self, address: str):
        parsered_url = urlparse(address)
        self.nodes.add(parsered_url.netloc)

    def valid_chain(self, chain) -> bool:
        current_index = 1
        last_block = chain[0]

        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self)->bool:
        neighbours = self.nodes
        max_length = len(self.chain)
        new_chain = None

        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['len']
                chain = response.json()['chain']

                if len(chain) > max_length and self.valid_chain(chain):
                    new_chain = chain
                    max_length = length

        if new_chain:
            self.chain = new_chain
            return True

        return False


    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block)
        }

        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount) -> int:
        self.current_transactions.append(
            {
                'sender': sender,
                'recipient': recipient,
                'amount': amount
            }
        )
        return self.last_block['index'] + 1

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    def valid_proof(self, last_proof: int, proof: int) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[0:3] == "000"


app = Flask(__name__)
blockchain = Blockchain()
node_identifier = str(uuid4()).replace('-', '')


@app.route('/index', methods=['get'])
def index():
    return "Hello, Blockchain."


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    if values == None:
        return "Missing Values."

    required = ["sender", "recipient", "amount"]
    if not all(k in values for k in required):
        return "Missing values.", 400

    block_index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to block {block_index}'}
    return jsonify(response), 201


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    #挖矿奖励
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1
    )

    block = blockchain.new_block(proof, None)

    response = {
        'message': "New block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }

    return jsonify(response), 200


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'len': len(blockchain.chain)
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    if values == None:
        return "Error: Please supply a valid list of nodes.", 400

    nodes = values['nodes']
    if nodes is None:
        return "Error: Please supply a valid list of nodes.", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': "New nodes have been added.",
        'node_list': list(blockchain.nodes)
    }

    return jsonify(response), 200


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    if blockchain.resolve_conflicts():
        response = {
            'message': "Our chain was replaced.",
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': "Our chain is authoritative.",
            'new_chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parser.parse_args()
    port = args.port
    app.run(host='0.0.0.0', port=port)

