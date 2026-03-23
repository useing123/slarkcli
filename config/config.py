from config.loader import load_config
from config.model import Config
from config.serializer import save_config
from config.wizard import setup_wizard

config = load_config()  # load
save_config(config)  # serialize
config = setup_wizard()  # setup wizard
