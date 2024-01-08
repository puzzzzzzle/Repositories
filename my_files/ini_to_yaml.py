import configparser
import yaml

# 读取 INI 文件
base_path = "../study_reps/"
config = configparser.ConfigParser()
config.read(f"{base_path}Repositories.ini")

yaml_data = {}
for section in config.sections():
    if section == "__Global__":
        continue
    try:
        category = config[section]["category"]
    except KeyError:
        category = "other"
    if category not in yaml_data:
        yaml_data[category] = {}
    yaml_data[category][section] = {k: v for k, v in config[section].items() if k != "category"}

# 将字典写入 YAML 文件
with open(f"{base_path}Repositories.yaml", "wt") as yaml_file:
    yaml.dump(yaml_data, yaml_file, default_flow_style=False)