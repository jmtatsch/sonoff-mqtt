import machine
import utime


class GP2Y1010AU0F(object):
    """
    Sharp GP2Y1010AU0F Dust Sensor
    Datasheet: https://www.sparkfun.com/datasheets/Sensors/gp2y1010au_e.pdf
    Input voltage: DC5V
    Output voltage:
    Detection concentration: 0 to 600 mikrogr/m^3
    -> need a voltage divider 5v to 1v
    """

    def __init__(self, pin):
        self.sensor_led = machine.Pin(pin, machine.Pin.OUT)
        self.adc = machine.ADC(0)
        self.pre_sampling = 280
        self.post_sampling = 40
        self.end_of_cycle = 9680

    def measure(self):
        self.sensor_led.low()  # turn on the LED
        utime.sleep_us(self.pre_sampling)
        dust_sensor_measurement = self.adc.read()  # read the raw voltage
        utime.sleep_us(self.post_sampling)
        self.sensor_led.high()  # turn off the LED
        utime.sleep_us(self.end_of_cycle)

        # ESP8266 adc maps 0 - 3.3V from 0 - 1023
        sensor_output_voltage = 3.3 * dust_sensor_measurement / 1024
        # Formula by Christopher Nafis
        # http://www.howmuchsnow.com/arduino/airquality/dust.ino
        dust_density = 0.17 * sensor_output_voltage - 0.1  # mg/m^3
        # compute particles per 0.01 cubic foot by fitting with Dylos DC1100
        pcs_per_100th_cf = (sensor_output_voltage - 0.0256) * 120000
        pcs_per_liter = pcs_per_100th_cf * 3.54
        return pcs_per_liter


class PPD42NS(object):
    """
    SHINYEI PPD42NS Dust Sensor
    Datasheet: http://wiki.timelab.org/images/f/f9/PPD42NS.pdf
    Input voltage: DC5V
    Outputvoltage: Hi : over 4.0V(Rev.2) Lo : under 0.7V
    Particle size: 1.0 um
    Concentration 0 - 28,000 pcs/liter
    """
    def __init__(self, pin):
        self.pin = machine.Pin(pin, machine.Pin.IN)
        self.sample_time = 30000  # 30s in millis
        self.low_pulse_occupancy = 0

    def measure(self):
        start_time = utime.ticks_us()
        low_pulse_occupancy = 0
        while True:
            # Sum up the time the signal is low
            # This is the Low Pulse Occupancy Time (LPO Time)
            duration = machine.time_pulse_us(pin, pulse_level=0)
            low_pulse_occupancy += duration

            if (utime.ticks_us() - start_time) > self.sample_time:
                break  # sampled enough

        ratio = low_pulse_occupancy / (self.sample_time * 10.0)
        # FIXME: should this be 100?
        # cubic polynomial fitted to the spec sheet curve by
        # http://www.howmuchsnow.com/arduino/airquality/grovedust/
        # concentration in pcs/283ml
        pcs_per_100th_cf = (1.1 * pow(ratio, 3)
                            - 3.8 * pow(ratio, 2) + 520 * ratio + 0.62)
        pcs_per_liter = pcs_per_100th_cf * 3.54
        return pcs_per_liter


class MQ2:
    """
    MQ-2 Smoke/Gas Sensor based on LM393
    http://arduino-info.wikispaces.com/file/view/MQ2.pdf/608272393/MQ2.pdf
    Input voltage: DC5V
    Output voltage: 0 - 5V the higher the concentration the higher the voltage.
    Detecting Range : 300-10000 ppm
    Code adopted from http://sandboxelectronics.com/?p=165
    """

    def __init__(self, adc):
        self.r_0_clean_air_factor = 9.83  # from the datasheet
        self.r_load_resistor = 5.0  # on the board in kOhm
        self.smoke_curve = [2.3, 0.53, -0.44]
        self.adc = machine.ADC(0)
        self.r_0 = self.calibrate()  # r_0 is the resistance in clean air

    def calculate_resistance(self, raw_adc):
        """
        The sensor and the load resistor form a voltage divider.
        Given the voltage across the load resistor and its resistance,
        the resistance of the sensor can be calculated.
        """
        return self.r_load_resistor * (1023 - raw_adc) / raw_adc

    def average_sample(self, samples=50, time_between_samples=500):
        sum_readings = 0
        for i in range(samples):
            sum_readings += self.calculate_resistance(self.adc.read())
            utime.sleep_ms(time_between_samples)
        return sum_readings/samples

    def calibrate(self,):
        self.r_0 = self.average_sample()/self.r_0_clean_air_factor

    def measure(self):
        r_s = self.calculate_resistance(self.average_sample())
        rs_ro_ratio = r_s / self.r_0
        # compute the smoke concentration in ppm
        smoke_concentration = pow(10, (((log(rs_ro_ratio) -
                                         self.smoke_curve[1])
                                        / self.smoke_curve[2]) +
                                       self.smoke_curve[0]))
        return smoke_concentration
