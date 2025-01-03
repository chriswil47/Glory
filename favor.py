import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from web3 import Web3
from bip44 import Wallet
import requests
from aiogram import Bot

# Replace with your values
ETH_RPC_URL = "https://mainnet.infura.io/v3/75722298119549be9f2e368591eb0a7b"
TELEGRAM_BOT_TOKEN = "6600045884:AAHCVIaUjbi9a0GbiQpcOEJcpxK-g0iqQsU"
TELEGRAM_CHAT_ID = "737206288"

web3 = Web3(Web3.HTTPProvider(ETH_RPC_URL))

bot = Bot(token=TELEGRAM_BOT_TOKEN)

generation_count = 0
valid_count = 0

def get_eth_address(mnemonic_phrase):
    """Generate Ethereum address from mnemonic."""
    wallet = Wallet(mnemonic_phrase)
    private_key = wallet.derive_account("eth", account=0)
    account = web3.eth.account.privateKeyToAccount(private_key)
    return account.address

def get_btc_address(mnemonic_phrase):
    """Generate Bitcoin address from mnemonic."""
    wallet = Wallet(mnemonic_phrase)
    btc_account = wallet.derive_account("btc", account=0)
    child_key = btc_account.get_child(0).get_child(0)  # First receiving address
    return child_key.address

def check_eth_balance(address):
    """Check Ethereum balance."""
    try:
        balance = web3.eth.get_balance(address)
        eth_balance = web3.from_wei(balance, "ether")
        return eth_balance
    except Exception as e:
        print(f"Error checking Ethereum balance: {e}")
        return 0

def check_btc_balance(address):
    """Check Bitcoin balance using Blockchain.info API."""
    try:
        url = f"https://blockchain.info/q/addressbalance/{address}"
        response = requests.get(url)
        if response.status_code == 200:
            satoshis = int(response.text)
            btc_balance = satoshis / 1e8
            return btc_balance
        else:
            print(f"Error fetching BTC balance for {address}: {response.status_code}")
            return 0
    except Exception as e:
        print(f"Error checking Bitcoin balance: {e}")
        return 0

def generate_and_check():
    """Generate mnemonic, addresses, and check balances."""
    global generation_count, valid_count
    from bip_utils import Bip39MnemonicGenerator

    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(24)
    eth_address = get_eth_address(mnemonic)
    btc_address = get_btc_address(mnemonic)

    eth_balance = check_eth_balance(eth_address)
    btc_balance = check_btc_balance(btc_address)

    generation_count += 1

    if eth_balance > 0.000000001 or btc_balance > 0.000000001:
        valid_count += 1
        return {
            "mnemonic": mnemonic,
            "eth_address": eth_address,
            "btc_address": btc_address,
            "eth_balance": eth_balance,
            "btc_balance": btc_balance,
        }
    return None

async def report_status():
    """Send periodic reports to Telegram."""
    global generation_count, valid_count
    while True:
        await bot.send_message(
            TELEGRAM_CHAT_ID,
            f"Total generations: {generation_count}\nValid balances found: {valid_count}"
        )
        await asyncio.sleep(300)  # Report every 5 minutes

async def main():
    """Main function for parallel generation and reporting."""
    global generation_count
    with ThreadPoolExecutor(max_workers=8) as executor:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(report_status())  # Start the reporting loop

        while True:
            futures = [
                loop.run_in_executor(executor, generate_and_check)
                for _ in range(8)
            ]
            results = await asyncio.gather(*futures)

            for result in results:
                if result:
                    message = (
                        f"Mnemonic: {result['mnemonic']}\n"
                        f"ETH Address: {result['eth_address']} (Balance: {result['eth_balance']} ETH)\n"
                        f"BTC Address: {result['btc_address']} (Balance: {result['btc_balance']} BTC)"
                    )
                    await bot.send_message(TELEGRAM_CHAT_ID, message)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user.")
