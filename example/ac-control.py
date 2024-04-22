import asyncio
import configparser
from py_miraie_ac import MirAIeAPI
from py_miraie_ac import AuthType

"""To read login details from ini file"""
config = configparser.ConfigParser()
config.read('login_info.ini')

api = MirAIeAPI

async def list_devices():
    async with MirAIeAPI(
            auth_type=AuthType.MOBILE, 
            login_id=config["login"]["username"],
            password=config["login"]["password"]
        ) as api:
        await api.initialize()

    return api

api = asyncio.get_event_loop().run_until_complete(list_devices())

for device in api.devices:
    print("Found device: ", device.friendly_name)
    print(f"Device is currently in Power mode: {device.status.power_mode}")
