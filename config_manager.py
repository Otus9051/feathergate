import yaml
import urllib3

# Suppress SSL warnings for local, insecure connections
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def load_config(config_file="config.yaml"):
    """
    Loads and parses the YAML configuration file.

    Args:
        config_file (str): The path to the configuration file.

    Returns:
        dict: A dictionary containing the configuration settings.
        
    Raises:
        FileNotFoundError: If the configuration file is not found.
        yaml.YAMLError: If there is an error parsing the YAML file.
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: {config_file} not found. Please create it.")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing {config_file}: {e}")
        raise

def get_config_value(config, path, default=None):
    """
    Safely gets a nested value from a dictionary.

    Args:
        config (dict): The configuration dictionary.
        path (list): A list of keys to navigate the dictionary.
        default: The default value to return if the path is not found.

    Returns:
        The value at the specified path, or the default value.
    """
    value = config
    try:
        for key in path:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default
