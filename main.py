import machine
import ubinascii as binascii
from umqtt.simple import MQTTClient
from config import broker

machine_id = binascii.hexlify(machine.unique_id())
print(b"Machine ID: {}".format(machine_id))
powered_on = False
client = None


def callback(topic, msg):
    if topic == topic_name(b"control"):
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


def publish_relay_state():
    if relay.value():
        client.publish(topic_name(b"state"), b"on")
    else:
        client.publish(topic_name(b"state"), b"off")
    print("Relay state: {}".format("on" if relay.value() else "off"))


def topic_name(topic):
    return b"/".join([b"light", machine_id, topic])


def set_relay(msg):
    global powered_on
    msg = msg.decode("utf-8") if isinstance(msg, bytes) else msg
    if msg == "on":
        relay.high()
        led.high()
        powered_on = True
    else:
        relay.low()
        led.low()
        powered_on = False
    publish_relay_state()


def get_smoke_sensor_reading():
    smoke_concentration = smoke_sensor.measure()
    print("%f ppm smoke" % smoke_concentration)
    client.publish(topic_name(b"airquality"), smoke_concentration)
    fan_control(smoke_concentration)


def fan_control(reading):
    threshold = 1200
    if threshold >= reading:
        set_relay("on")
    else:
        set_relay("off")


def connect_and_subscribe():
    global client
    client = MQTTClient(machine_id, broker)
    client.set_callback(callback)
    client.connect()
    print("Connected to {}".format(broker))
    for topic in (b'config', b'control'):
        t = topic_name(topic)
        client.subscribe(t)
        print("Subscribed to {}".format(t))


def setup_smoke_sensor(pin):
    global smoke_sensor
    import sensors
    smoke_sensor = MQ2()

    # smoke_sensor2 = PPD42NS(0)
    # pcs_per_liter = smoke_sensor2.measure()
    # print(pcs_per_liter + " pcs/l")
    # smoke_sensor3 = GP2Y1010AU0F(0)
    # pcs_per_liter = smoke_sensor3.measure()
    # print(pcs_per_liter + " pcs/l")


def load_config(msg):
    import ujson as json
    try:
        config = json.loads(msg)
    except (OSError, ValueError):
        print("Couldn't load config from JSON, bailing out.")
    else:
        set_relay(config['power'])
        setup_smoke_senor(config['gpio_pin'])


def button_callback(pin):
    print("the sonoff button was pressed to %i" % pin.value())


def relay_callback(pin):
    print("the sonoff relay switched to %i" % pin.value())


def setup():
    global button, relay, led
    button = machine.Pin(0, machine.Pin.IN)
    button.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_callback)

    relay = machine.Pin(12, machine.Pin.OUT)
    led = machine.Pin(13, machine.Pin.OUT)
    relay.irq(trigger=machine.Pin.IRQ_FALLING, handler=relay_callback)
    connect_and_subscribe()


def main_loop():
    while True:
        client.wait_msg()
        get_smoke_sensor_reading()


def teardown():
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
