# -*- coding: utf-8 -*-
"""
This module switches a sonoff relay on as long as smoke is detected.

It also exposes the relay and the smoke sensor readings via MQTT.
"""

import machine
import ubinascii as binascii
from umqtt.simple import MQTTClient
from config import broker
from sensors import MQ2
import webrepl
webrepl.start()

machine_id = binascii.hexlify(machine.unique_id())
print(b"Machine ID: {}".format(machine_id))
client = None


def mqtt_callback(topic, msg):
    """Handle mqtt messages from the server."""
    if topic == topic_name(b"set"):
        try:
            msg_type, payload = msg.split(b":", 1)
            if msg_type == b"power":
                set_relay(payload)
            else:
                print("Unknown message type, ignoring")
        except Exception:
            print("Couldn't parse/handle message, ignoring.")
    elif topic == topic_name(b"config"):
        load_config(msg)


def load_config(msg):
    """Load a json config received over mqtt."""
    import ujson as json
    try:
        config = json.loads(msg)
    except (OSError, ValueError):
        print("Couldn't load config from JSON.")
    else:
        set_relay(config['power'])


def topic_name(topic):
    """Create a absolute topic name for a topic."""
    return b"/".join([b"homeassistant", b"switch", b"fan", topic])


def set_relay(msg):
    """Set the relay state."""
    msg = msg.decode("utf-8") if isinstance(msg, bytes) else msg
    if msg == "on":
        print("set relay on")
        relay.high()
        led.high()
    else:
        print("set relay off")
        relay.low()
        led.low()
    publish_relay_state()


def publish_relay_state():
    """Publish the relay state to a mqtt channel."""
    if relay.value():
        client.publish(topic_name(b"state"), b"on")
    else:
        client.publish(topic_name(b"state"), b"off")
    print("Relay state: {}".format("on" if relay.value() else "off"))


def toggle_relay():
    """Toggle the relay state."""
    if relay.value():
        set_relay("off")
    else:
        set_relay("on")
    print("Toggled relay")


def get_smoke_sensor_reading():
    """Perform a smoke measurement, publish and control fan."""
    smoke_concentration = smoke_sensor.measure()
    print("%f ppm smoke" % smoke_concentration)
    client.publish(topic_name(b"airquality"), smoke_concentration)
    fan_control(smoke_concentration)


def fan_control(smoke_concentration):
    """Control the relay depending on the smoke concentration."""
    threshold = 1200
    if smoke_concentration >= threshold:
        set_relay("on")
    else:
        set_relay("off")


def button_callback(pin):
    """Handle relay button press."""
    print("button was pressed to %i" % pin.value())
    toggle_relay()


def relay_callback(pin):
    """Handle relay status change."""
    print("relay switched to %i" % pin.value())
    publish_relay_state()


def setup():
    """Set up the IOs and connect to mqtt server."""
    global button, relay, led, smoke_sensor
    button = machine.Pin(0, machine.Pin.IN)
    button.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)

    relay = machine.Pin(12, machine.Pin.OUT)
    relay.irq(trigger=machine.Pin.IRQ_FALLING, handler=relay_callback)

    led = machine.Pin(13, machine.Pin.OUT)  # could also be pin 2

    smoke_sensor = MQ2()

    # smoke_sensor2 = PPD42NS(0)
    # pcs_per_liter = smoke_sensor2.measure()
    # print(pcs_per_liter + " pcs/l")
    # smoke_sensor3 = GP2Y1010AU0F(0)
    # pcs_per_liter = smoke_sensor3.measure()
    # print(pcs_per_liter + " pcs/l")

    connect_and_subscribe()


def connect_and_subscribe():
    """Connect to a mqtt server and subscribe to channels."""
    global client
    client = MQTTClient(machine_id, broker)
    client.set_callback(mqtt_callback)
    client.connect()
    print("Connected to {}".format(broker))
    for topic in (b'config', b'set'):
        t = topic_name(topic)
        client.subscribe(t)
        print("Subscribed to {}".format(t))


def main_loop():
    """Run the main loop."""
    while True:
        client.wait_msg()
        print("tried to get mqtt mesgs")
        get_smoke_sensor_reading()
        print("tried to get smoke readings")


def teardown():
    """Tear down the mqtt connection to the server."""
    try:
        client.disconnect()
        print("Disconnected.")
    except Exception:
        print("Couldn't disconnect cleanly.")


if __name__ == '__main__':
    setup()
    try:
        main_loop()
    finally:
        teardown()
