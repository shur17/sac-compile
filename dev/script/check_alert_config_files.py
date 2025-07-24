import os
import traceback
import yaml
import glob

script_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.abspath(os.path.join(script_dir, '..', '..'))
ALERT_METRIC_CONFIG_FILE_PATTERN = os.path.join(base_dir, 'conf', 'default-alert-metric-config.yml.*')
ALERT_RULE_TMPL_FILE_PATTERN = os.path.join(base_dir, 'conf', 'default-alert-rule-tmpl.yml.*')
ALERT_METRIC_CONFIG_IGNORE_KEYS = ['desc']
ALERT_RULE_TMPL_IGNORE_KEYS = ['desc', 'summary_tmpl', 'description_tmpl', 'eval_rules.suggestion']


def remove_ignore_keys(map_item, ignore_keys):
    for ignore_key in ignore_keys:
        # key1 -> ['key1']
        # key1.key2 -> ['key1', 'key2']
        # key1.key2.key3 -> ['key1', 'key2.key3']
        ignore_key_array = ignore_key.split('.', 1)
        if len(ignore_key_array) == 1:
            map_item.pop(ignore_key_array[0], None)
        else:
            value = map_item.get(ignore_key_array[0])
            if value is None:
                continue
            if isinstance(value, dict):
                remove_ignore_keys(value, [ignore_key_array[1]])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        remove_ignore_keys(item, [ignore_key_array[1]])


def get_config_map_and_remove_ignore_keys(filename, tag, ignore_keys):
    with open(filename, 'r') as f:
        data = yaml.safe_load(f)
        config_map = {}
        for config in data[tag]:
            remove_ignore_keys(config, ignore_keys)
            config_name = config['name']
            config_map[config_name] = config
    return config_map


def get_matched_files(pattern):
    return glob.glob(pattern)


def compare_alert_metric_config_files():
    def get_alert_metric_config(filename):
        return get_config_map_and_remove_ignore_keys(filename, 'metrics', ALERT_METRIC_CONFIG_IGNORE_KEYS)

    alert_metric_config_file_list = get_matched_files(ALERT_METRIC_CONFIG_FILE_PATTERN)
    if len(alert_metric_config_file_list) < 2:
        raise Exception(
            "The number of alert metric config files is less than 2, please check the integrity of the alert metric config files.")

    base_alert_metric_config_file = alert_metric_config_file_list[0]
    base_file_config_map = get_alert_metric_config(base_alert_metric_config_file)
    for i in range(1, len(alert_metric_config_file_list)):
        other_file_config_map = get_alert_metric_config(alert_metric_config_file_list[i])
        try:
            compare_config(base_file_config_map, other_file_config_map)
        except Exception:
            message = "Alert metric config file are inconsistent when comparing {} and {}. please use the comparison function of " \
                      "the idea tool to compare all alert metric config files, when comparing, can ignore these fields:{}. detail: {}"
            raise Exception(
                message.format(base_alert_metric_config_file, alert_metric_config_file_list[i], ALERT_METRIC_CONFIG_IGNORE_KEYS, traceback.format_exc()))


def compare_alert_rule_tmpl_files():
    def get_alert_rule_tmpl_config(filename):
        return get_config_map_and_remove_ignore_keys(filename, 'rules', ALERT_RULE_TMPL_IGNORE_KEYS)

    alert_rule_tmpl_file_list = get_matched_files(ALERT_RULE_TMPL_FILE_PATTERN)
    if len(alert_rule_tmpl_file_list) < 2:
        raise Exception(
            "The number of alert rule tmpl files is less than 2, please check the integrity of the alert rule tmpl files.")

    base_alert_rule_tmpl_file = alert_rule_tmpl_file_list[0]
    base_file_config_map = get_alert_rule_tmpl_config(base_alert_rule_tmpl_file)
    for i in range(1, len(alert_rule_tmpl_file_list)):
        other_file_config_map = get_alert_rule_tmpl_config(alert_rule_tmpl_file_list[i])
        try:
            compare_config(base_file_config_map, other_file_config_map)
        except Exception:
            message = "Alert rule tmpl file are inconsistent when comparing {} and {}. please use the comparison function of " \
                      "the idea tool to compare all alert rule tmpl files, when comparing, can ignore these fields:{}. detail: {}"
            raise Exception(
                message.format(base_alert_rule_tmpl_file, alert_rule_tmpl_file_list[i], ALERT_RULE_TMPL_IGNORE_KEYS, traceback.format_exc()))


def compare_config(left_config, right_config):
    left_config_item_num = len(left_config)
    right_config_item_num = len(right_config)
    if left_config_item_num != right_config_item_num:
        raise Exception(
            "The number of config is inconsistent, left config has {} items, right config has {} items.".format(
                left_config_item_num, right_config_item_num))
    for name, left_item in left_config.items():
        right_item = right_config.get(name)
        if right_item is None:
            raise Exception("The {} is not found in the right config.".format(name))
        left_item_key_num = len(left_item)
        right_item_key_num = len(right_item)
        if left_item_key_num != right_item_key_num:
            raise Exception(
                "The number of key in {} is inconsistent, left has {} keys, but right has {} key.".format(name, left_item_key_num, right_item_key_num))
        for key, value in left_item.items():
            if key not in right_item:
                raise Exception("The {}.{} is not found in the right.".format(name, key))
            if value != right_item[key]:
                raise Exception(
                    "The {}.{} is inconsistent, left is {}, right is {}".format(name, key, value, right_item[key]))


if __name__ == "__main__":
    print("Comparing alert rule tmpl files...")
    compare_alert_rule_tmpl_files()
    print(" ok")

    print("Comparing alert metric config files...")
    compare_alert_metric_config_files()
    print(" ok")