# InnerNode - Cross-Chain Bridge Event Listener

This repository contains the source code for `InnerNode`, a Python-based simulation of a crucial component in a cross-chain bridge: an event listener and oracle attestation service. It is designed to be a robust, modular, and understandable example of how off-chain services interact with blockchain networks.

## Concept

A cross-chain bridge allows users to transfer assets or data from a source blockchain (e.g., Ethereum) to a destination blockchain (e.g., Polygon). A common architecture for this involves several key steps:

1.  **Locking/Burning on Source Chain**: A user deposits assets into a smart contract on the source chain. This contract locks the assets and emits an event (e.g., `BridgeTransferInitiated`) containing details of the transfer.
2.  **Off-Chain Validation**: A network of off-chain nodes (validators, oracles, or listeners) constantly monitors the source chain for these specific events.
3.  **Attestation**: Upon detecting a valid event, each node independently creates a signed message (an "attestation") confirming that the event occurred.
4.  **Minting/Unlocking on Destination Chain**: These attestations are submitted to a smart contract on the destination chain. Once a sufficient number of attestations are collected, the contract mints or unlocks the corresponding assets for the user on the destination chain.

**`InnerNode` simulates the critical off-chain component (Steps 2 and 3)**. It listens for events on a source chain and submits an attestation to a simulated oracle network API for the destination chain.

### The Watched Event

`InnerNode` is configured to listen for a specific event signature. For this simulation, it targets an event named `BridgeTransferInitiated`. A simplified version of this event in a Solidity smart contract might look like this:

```solidity
contract BridgeContract {
    // A unique identifier for each transfer
    uint256 public nonce;

    // Event emitted when a user initiates a cross-chain transfer
    event BridgeTransferInitiated(
        address indexed from,
        address indexed to,
        uint256 amount,
        uint256 sourceChainId,
        uint256 destinationChainId,
        uint256 nonce
    );

    function bridgeAssets(address to, uint256 amount, uint256 destinationChainId) public payable {
        // ... logic to lock assets ...
        
        emit BridgeTransferInitiated(
            msg.sender,
            to,
            amount,
            block.chainid,
            destinationChainId,
            nonce++
        );
    }
}
```

The listener filters for this event and processes its arguments (`from`, `to`, `amount`, etc.) to build the attestation.

## Code Architecture

The script is designed with a clear separation of concerns, organized into several key classes:

-   **`InnerNodeConfig`**: A dedicated configuration class that loads all necessary parameters from environment variables (using a `.env` file). It centralizes settings like RPC URLs, contract addresses, and API keys, and performs basic validation on startup.

-   **`ChainEventListener`**: This is the core component that interacts with the source blockchain.
    -   It uses the `web3.py` library to connect to an Ethereum-compatible node.
    -   It initializes the bridge smart contract object using its address and ABI.
    -   Its main method, `listen_for_events`, runs in a continuous loop, polling the blockchain for new blocks and filtering for the target event (`BridgeTransferInitiated`).
    -   It includes logic to handle block confirmations to reduce the risk of processing events from chain reorganizations.

-   **`CrossChainOracleClient`**: This class simulates the interaction with the destination chain's oracle network.
    -   It uses the `requests` library to make authenticated HTTP POST requests to a simulated API endpoint.
    -   The `submit_attestation` method formats the event data into a payload and sends it, handling potential network errors and unsuccessful API responses.

-   **`BridgeOrchestrator`**: This class acts as the central coordinator.
    -   It initializes instances of `ChainEventListener` and `CrossChainOracleClient`.
    -   It provides a callback function (`handle_new_bridge_event`) which is passed to the listener. This decouples the listener from the oracle client; the listener's only job is to find events, and the orchestrator decides what to do with them.
    -   The `run()` method starts the entire process and includes top-level error handling and graceful shutdown logic (e.g., on `Ctrl+C`).

## How it Works

The operational flow of the script is as follows:

1.  **Initialization**: The script's entry point (`if __name__ == "__main__":`) creates an `InnerNodeConfig` instance to load the application settings. This configuration object is then used to initialize the `BridgeOrchestrator`.
2.  **Service Start**: The `BridgeOrchestrator.run()` method is called, which initiates the main service loop.
3.  **Connection**: The `ChainEventListener` connects to the configured RPC endpoint of the source chain.
4.  **Polling Loop**: The listener enters an infinite loop.
    a. It determines the range of blocks to scan, starting from the last processed block up to the latest block minus a confirmation delay (e.g., 6 blocks).
    b. It uses `web3.py` to query for `BridgeTransferInitiated` events within that block range.
    c. If events are found, it iterates through them.
5.  **Event Processing**: For each event, the `_process_event` method extracts the relevant data (sender, recipient, amount, etc.) into a clean dictionary.
6.  **Callback Invocation**: The listener invokes the callback function provided by the `BridgeOrchestrator`, passing the processed event data.
7.  **Attestation Submission**: The orchestrator's callback method (`handle_new_bridge_event`) receives the data and instructs the `CrossChainOracleClient` to submit it.
8.  **API Call**: The `CrossChainOracleClient` formats a JSON payload and sends it via an HTTP POST request to the destination oracle's API endpoint.
9.  **Logging**: The entire process, from detecting an event to receiving an API response, is logged to the console for monitoring.
10. **Repeat**: After a configured polling interval (e.g., 15 seconds), the listener wakes up and the polling loop repeats.

## Usage

### 1. Setup

First, clone the repository and navigate into the directory:

```bash
git clone https://github.com/your-username/InnerNode.git
cd InnerNode
```

It is highly recommended to use a Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configuration

Create a file named `.env` in the root of the project directory. This file will store your configuration secrets. Populate it with the following variables, replacing the placeholder values with your own:

```dotenv
# URL for the source chain's RPC node (e.g., from Infura, Alchemy, or a personal node)
SOURCE_CHAIN_RPC_URL="https://rpc.sepolia.org"

# The address of the bridge contract you want to monitor
BRIDGE_CONTRACT_ADDRESS="0x9A2b455D82859EC403DF5742654A621319503B44" # Example address

# The API endpoint for the destination chain's oracle network
DESTINATION_ORACLE_API="https://httpbin.org/post" # Using httpbin to test POST requests

# A secret API key for authenticating with the oracle API
ORACLE_API_KEY="your-super-secret-api-key-for-oracle"

# (Optional) Polling interval in seconds
POLLING_INTERVAL_SECONDS=15

# (Optional) Number of blocks to wait for confirmation
BLOCK_CONFIRMATION_DELAY=6
```

**Important**: For the listener to detect events, you must replace `BRIDGE_CONTRACT_ADDRESS` with the address of a real contract that emits a `BridgeTransferInitiated` event (or one with a matching signature).

### 3. Run the Application

Once configured, you can start the service by running the main script from your terminal. The script will immediately attempt to connect to the source chain's RPC and begin polling for events according to your configuration.

```bash
python main.py
```

### 4. Expected Output

The script will start logging its activities to the console. When it detects an event on the source chain, you should see output similar to this:

```
2023-10-27 14:30:00 - [INFO] - (InnerNodeConfig) - Configuration validated successfully.
2023-10-27 14:30:00 - [INFO] - (BridgeOrchestrator) - --- InnerNode Bridge Listener Starting --- 
2023-10-27 14:30:00 - [INFO] - (ChainEventListener) - Successfully initialized contract at address: 0x9A2b455D82859EC403DF5742654A621319503B44
2023-10-27 14:30:01 - [INFO] - (ChainEventListener) - Successfully connected to Ethereum node. Chain ID: 11155111
2023-10-27 14:30:01 - [INFO] - (ChainEventListener) - Starting to listen for 'BridgeTransferInitiated' events...
2023-10-27 14:30:01 - [INFO] - (ChainEventListener) - Scanning for events from block 4812500 to 4812510.
2023-10-27 14:30:02 - [DEBUG] - (ChainEventListener) - No new events found in block range [4812500-4812510].
2023-10-27 14:30:17 - [INFO] - (ChainEventListener) - Scanning for events from block 4812511 to 4812511.
2023-10-27 14:30:18 - [INFO] - (ChainEventListener) - Found 1 new 'BridgeTransferInitiated' event(s).
2023-10-27 14:30:18 - [INFO] - (ChainEventListener) - Processing event from Tx: 0xabc...def
2023-10-27 14:30:18 - [INFO] - (BridgeOrchestrator) - Orchestrator received new event: Nonce 123
2023-10-27 14:30:18 - [INFO] - (CrossChainOracleClient) - Submitting attestation to https://httpbin.org/post for Tx: 0xabc...def
2023-10-27 14:30:19 - [INFO] - (CrossChainOracleClient) - Successfully submitted attestation. Response: { ...httpbin response... }
...
```