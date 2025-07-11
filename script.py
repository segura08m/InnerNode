import os
import time
import json
import logging
from typing import Dict, Any, Callable

import requests
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError, BadFunctionCallOutput, BlockNotFound
from dotenv import load_dotenv

# --- Configuration Loading ---
# In a real-world application, this would be managed more robustly.
load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - (%(name)s) - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class InnerNodeConfig:
    """A dedicated class to hold and validate configuration parameters."""
    def __init__(self):
        # --- Source Chain Configuration ---
        self.SOURCE_CHAIN_RPC_URL = os.getenv('SOURCE_CHAIN_RPC_URL', 'https://rpc.sepolia.org')
        # This is a placeholder address. Replace with your actual bridge contract address.
        self.BRIDGE_CONTRACT_ADDRESS = os.getenv('BRIDGE_CONTRACT_ADDRESS', '0x1234567890123456789012345678901234567890')

        # --- Destination Chain Oracle Configuration ---
        self.DESTINATION_ORACLE_API = os.getenv('DESTINATION_ORACLE_API', 'https://api.destination-chain.com/attest')
        self.ORACLE_API_KEY = os.getenv('ORACLE_API_KEY', 'your-secret-api-key')

        # --- Listener Configuration ---
        self.POLLING_INTERVAL_SECONDS = int(os.getenv('POLLING_INTERVAL_SECONDS', 15))
        self.BLOCK_CONFIRMATION_DELAY = int(os.getenv('BLOCK_CONFIRMATION_DELAY', 6))

        # --- Bridge Contract ABI (Simplified for demonstration) ---
        # In a real system, this would be loaded from a JSON file.
        self.BRIDGE_CONTRACT_ABI = json.loads('''
        [
            {
                "anonymous": false,
                "inputs": [
                    {"indexed": true, "internalType": "address", "name": "sender", "type": "address"},
                    {"indexed": true, "internalType": "string", "name": "destinationChain", "type": "string"},
                    {"indexed": true, "internalType": "address", "name": "recipient", "type": "address"},
                    {"indexed": false, "internalType": "address", "name": "token", "type": "address"},
                    {"indexed": false, "internalType": "uint256", "name": "amount", "type": "uint256"},
                    {"indexed": false, "internalType": "uint256", "name": "nonce", "type": "uint256"}
                ],
                "name": "BridgeTransferInitiated",
                "type": "event"
            }
        ]
        ''')

        self.validate()

    def validate(self):
        """Basic validation of critical configuration parameters."""
        if not self.SOURCE_CHAIN_RPC_URL.startswith(('http', 'ws')):
            raise ValueError("Invalid SOURCE_CHAIN_RPC_URL provided.")
        if not Web3.is_address(self.BRIDGE_CONTRACT_ADDRESS):
            raise ValueError("Invalid BRIDGE_CONTRACT_ADDRESS provided.")
        logging.info("Configuration validated successfully.")


class ChainEventListener:
    """
    Listens for specific events on a given blockchain contract.
    This class is responsible for connecting to a blockchain node, setting up
    an event filter, and polling for new event logs.
    """

    def __init__(self, config: InnerNodeConfig):
        """
        Initializes the listener with connection details and contract information.

        Args:
            config (InnerNodeConfig): The configuration object containing RPC URL, contract details, etc.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(self.config.SOURCE_CHAIN_RPC_URL))
        self.bridge_contract = self._initialize_contract()
        self.last_processed_block = None

    def _initialize_contract(self) -> Contract:
        """Initializes and returns the contract object."""
        try:
            contract_address = Web3.to_checksum_address(self.config.BRIDGE_CONTRACT_ADDRESS)
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=self.config.BRIDGE_CONTRACT_ABI
            )
            self.logger.info(f"Successfully initialized contract at address: {contract_address}")
            return contract
        except Exception as e:
            self.logger.error(f"Failed to initialize contract: {e}")
            raise

    def connect(self) -> bool:
        """Checks the connection to the blockchain node."""
        try:
            if self.w3.is_connected():
                self.logger.info(f"Successfully connected to Ethereum node. Chain ID: {self.w3.eth.chain_id}")
                return True
            else:
                self.logger.error("Failed to connect to Ethereum node.")
                return False
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False

    def listen_for_events(self, event_name: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Starts the main event listening loop.

        Args:
            event_name (str): The name of the event to listen for.
            callback (Callable): A function to call when a new event is detected.
        """
        if not self.connect():
            self.logger.error("Cannot start listening, no connection to the node.")
            return

        self.logger.info(f"Starting to listen for '{event_name}' events...")

        while True:
            try:
                latest_block = self.w3.eth.block_number
                if self.last_processed_block is None:
                    # On first run, start from a few blocks back to avoid missing events.
                    self.last_processed_block = max(0, latest_block - self.config.BLOCK_CONFIRMATION_DELAY - 10)

                # Define the block range for this polling cycle.
                from_block = self.last_processed_block + 1
                # Ensure we don't query blocks that are not yet confirmed.
                to_block = latest_block - self.config.BLOCK_CONFIRMATION_DELAY

                if from_block > to_block:
                    self.logger.debug(f"No new confirmed blocks to process. Current head: {latest_block}. Waiting...")
                    time.sleep(self.config.POLLING_INTERVAL_SECONDS)
                    continue

                self.logger.info(f"Scanning for events from block {from_block} to {to_block}.")

                event_filter = self.bridge_contract.events[event_name].create_filter(
                    fromBlock=from_block,
                    toBlock=to_block
                )
                
                new_events = event_filter.get_all_entries()

                if new_events:
                    self.logger.info(f"Found {len(new_events)} new '{event_name}' event(s).")
                    for event in new_events:
                        self._process_event(event, callback)
                else:
                    self.logger.debug(f"No new events found in block range [{from_block}-{to_block}].")

                self.last_processed_block = to_block

            except BlockNotFound:
                self.logger.warning("Block not found, possibly due to a reorg. Re-adjusting scan range.")
                # Simple reorg handling: step back a few blocks
                self.last_processed_block = max(0, self.last_processed_block - 10)
                time.sleep(self.config.POLLING_INTERVAL_SECONDS)
            except Exception as e:
                self.logger.error(f"An unexpected error occurred in the listening loop: {e}")
                # Exponential backoff could be implemented here.
                time.sleep(self.config.POLLING_INTERVAL_SECONDS * 2)

            time.sleep(self.config.POLLING_INTERVAL_SECONDS)

    def _process_event(self, event: Dict[str, Any], callback: Callable[[Dict[str, Any]], None]):
        """
        Processes a raw event log and invokes the callback.

        Args:
            event (Dict[str, Any]): The event log from web3.py.
            callback (Callable): The callback function to execute.
        """
        # We create a clean, serializable dictionary from the event log.
        processed_data = {
            'transactionHash': event['transactionHash'].hex(),
            'blockNumber': event['blockNumber'],
            'event': event['event'],
            'args': {
                'sender': event['args']['sender'],
                'destinationChain': event['args']['destinationChain'],
                'recipient': event['args']['recipient'],
                'token': event['args']['token'],
                'amount': event['args']['amount'],
                'nonce': event['args']['nonce']
            }
        }
        self.logger.info(f"Processing event from Tx: {processed_data['transactionHash']}")
        try:
            callback(processed_data)
        except Exception as e:
            self.logger.error(f"Callback failed for event {processed_data['transactionHash']}: {e}")


class CrossChainOracleClient:
    """
    Simulates a client that sends attestations to a destination chain's oracle network.
    This is done via a REST API call.
    """

    def __init__(self, config: InnerNodeConfig):
        """
        Initializes the oracle client.

        Args:
            config (InnerNodeConfig): The configuration object with API details.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.config.ORACLE_API_KEY}'
        })

    def submit_attestation(self, event_data: Dict[str, Any]):
        """
        Submits the event data as an attestation to the oracle's API.

        Args:
            event_data (Dict[str, Any]): The processed event data from the source chain.
        """
        payload = {
            'sourceTransactionHash': event_data['transactionHash'],
            'sourceBlockNumber': event_data['blockNumber'],
            'payload': event_data['args']
        }

        self.logger.info(f"Submitting attestation to {self.config.DESTINATION_ORACLE_API} for Tx: {payload['sourceTransactionHash']}")

        try:
            response = self.session.post(self.config.DESTINATION_ORACLE_API, json=payload, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

            self.logger.info(f"Successfully submitted attestation. Response: {response.json()}")
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP Error submitting attestation: {e.response.status_code} {e.response.text}")
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection Error submitting attestation: {e}")
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out while submitting attestation.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during attestation submission: {e}")


class BridgeOrchestrator:
    """
    The main orchestrator class that wires together the event listener and the oracle client.
    It controls the lifecycle of the bridge node component.
    """

    def __init__(self, config: InnerNodeConfig):
        """
        Initializes all components of the InnerNode service.
        
        Args:
            config (InnerNodeConfig): The main configuration object.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.listener = ChainEventListener(config)
        self.oracle_client = CrossChainOracleClient(config)

    def handle_new_bridge_event(self, event_data: Dict[str, Any]):
        """
        This is the callback function that connects the listener to the oracle.
        When the listener finds an event, it calls this method.

        Args:
            event_data (Dict[str, Any]): The processed event data.
        """
        self.logger.info(f"Orchestrator received new event: Nonce {event_data['args']['nonce']}")
        # Here, you could add more logic: database checks, fraud proofs, etc.
        self.oracle_client.submit_attestation(event_data)

    def run(self):
        """
        Starts the main service loop and handles graceful shutdown.
        """
        self.logger.info("--- InnerNode Bridge Listener Starting --- ")
        try:
            self.listener.listen_for_events(
                event_name='BridgeTransferInitiated',
                callback=self.handle_new_bridge_event
            )
        except KeyboardInterrupt:
            self.logger.info("Shutdown signal received. Exiting gracefully.")
        except Exception as e:
            self.logger.critical(f"A critical error forced the orchestrator to stop: {e}", exc_info=True)
        finally:
            self.logger.info("--- InnerNode Bridge Listener Stopped --- ")


if __name__ == "__main__":
    try:
        # 1. Load and validate configuration
        main_config = InnerNodeConfig()

        # 2. Initialize the main orchestrator
        orchestrator = BridgeOrchestrator(main_config)

        # 3. Start the service
        orchestrator.run()

    except ValueError as e:
        logging.critical(f"Configuration Error: {e}")
    except Exception as e:
        logging.critical(f"Failed to start the application: {e}")
