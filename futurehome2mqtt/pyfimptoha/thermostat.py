import json
import typing

def new_thermostat(
        mqtt,
        device: typing.Any,
        state_topic,
        identifier,
        default_component,
        command_topic
):
    """
    Creates thermostat in Home Assistant based on FIMP services
    """

    statuses = []
    supported_thermostat_modes = [mode for mode in device["param"]["supportedThermostatModes"]]

    fan_component = None
    if "fan_ctrl" in device["services"]:
        fan_component = new_fan_component(device)

    humid_component = None
    if "sensor_humid" in device["services"]:
        humid_component = new_humid_component(device)

    if "sensor_temp" in device["services"]:
        current_temperature_topic = f'pt:j1/mt:evt{device["services"]["sensor_temp"]["addr"]}'
    else:
        # TODO logic to find thing_role:main on device with same address (e.g heatit on _4)
        current_temperature_topic = ""

    thermostat_component = {
        "current_temperature_template": "{{ value_json.val | round(1) }}",
        "current_temperature_topic": current_temperature_topic,
        "max_temp": 40.0,
        "min_temp": 5.0,
        "mode_command_template": """
            {
                "serv": "thermostat",
                "type": "cmd.mode.set",
                "val_t": "string",
                "val": "{{ value }}",
                "props": {},
                "tags": [],
                "src": "homeassistant"
            }
        """,
        "mode_command_topic": command_topic,
        "mode_state_template": """
            {% if value_json.type == 'evt.mode.report' %}
                {{ value_json.val }}
            {% endif %}
        """,
        "mode_state_topic": state_topic,
        "modes": supported_thermostat_modes,
        "name": None,
        "temperature_command_template": """
            {
                "serv": "thermostat",
                "type": "cmd.setpoint.set",
                "val_t": "str_map",
                "val": {
                    "temp": "{{ value }}",
                    "type": "heat",
                    "unit": "C"
                },
                "props": {},
                "tags": [],
                "src": "homeassistant"
            }
        """,
        "temperature_command_topic": command_topic,
        "temperature_state_template": """
            {% if value_json.type == 'evt.setpoint.report' %}
                {{ value_json.val.temp }}
            {% endif %}
        """,
        "temperature_state_topic": state_topic,
        "temperature_unit": "C",
        "temp_step": 1.0 # default 1.0
    }

    # Merge default_component with thermostat_component
    merged_component = {**default_component, **thermostat_component}

    if fan_component:
        merged_component = {**merged_component, **fan_component}

    if humid_component:
        merged_component = {**merged_component, **humid_component}

    payload = json.dumps(merged_component)
    mqtt.publish(f"homeassistant/climate/{identifier}/config", payload)

    # Queue status
    if fan_component:
        fan_payload = {
            "props": {},
            "serv": "fan_ctrl",
            "type": "cmd.mode.get_report",
            "val_t": "string",
            "val": "",
            "src": "homeassistant"
        }
        fan_mode_payload = json.dumps(fan_payload)
        statuses.append((f"pt:j1/mt:cmd{device['services']['fan_ctrl']['addr']}", fan_mode_payload))

    if device.get("param") and device["param"].get("targetTemperature"):
        temp = device["param"]["targetTemperature"]
        data_temp = {
            "props": {},
            "serv": "thermostat",
            "type": "evt.setpoint.report",
            "val_t": "str_map",
            "val": {
                "temp": f"{temp}",
                "type": "heat",
                "unit": "C"
            },
            "src": "homeassistant"
        }
        payload_temp = json.dumps(data_temp)
        if payload_temp:
            statuses.append((state_topic, payload_temp))

    if device.get("param") and device["param"].get("thermostatMode"):
        mode = device["param"]["thermostatMode"]
        data_mode = {
            "props": {},
            "serv": "thermostat",
            "type": "evt.mode.report",
            "val_t": "string",
            "val": f"{mode}",
            "src": "homeassistant"
        }
        payload_mode = json.dumps(data_mode)
        if payload_mode:
            statuses.append((state_topic, payload_mode))
    return statuses


def new_fan_component(device):
    fan_ctrl = device["services"]["fan_ctrl"]
    supported_fan_modes = [mode for mode in fan_ctrl["props"]["sup_modes"]]
    fan_component = {
        "fan_mode_command_template": """
            {
                "serv": "fan_ctrl",
                "type": "cmd.mode.set",
                "val_t": "string",
                "val": "{{ value }}",
                "props": {},
                "tags": [],
                "src": "homeassistant"
            }
        """,
        "fan_mode_command_topic": f"pt:j1/mt:cmd{fan_ctrl['addr']}",
        "fan_mode_state_template": """
            {% if value_json.type == 'evt.mode.report' %}
                {{ value_json.val }}
            {% endif %}
        """,
        "fan_mode_state_topic": f"pt:j1/mt:evt{fan_ctrl['addr']}",
        "fan_modes": supported_fan_modes
    }
    return fan_component


def new_humid_component(device):
    sensor_humid = device["services"]["sensor_humid"]
    humid_component = {
        "current_humidity_template": "{{ value_json.val | round(0) }}",
        "current_humidity_topic": f"pt:j1/mt:evt{sensor_humid['addr']}"
    }
    return humid_component
