import configparser
import yaml

# 读取 INI 文件
config = configparser.ConfigParser()
config.read("../opensource/Repositories.ini")

yaml_data = {}
for section in config.sections():
    category = config[section]["category"]
    if category not in yaml_data:
        yaml_data[category] = {}
    yaml_data[category][section] = {k: v for k, v in config[section].items() if k != "category"}

# 将字典写入 YAML 文件
with open("../opensource/Repositories.yaml", "w") as yaml_file:
    yaml.dump(yaml_data, yaml_file, default_flow_style=False)