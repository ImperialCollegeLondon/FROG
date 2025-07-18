# Hardware sets

Hardware sets are collections of hardware device types along with their associated
parameters. They are used in FROG to represent a particular hardware rig (e.g. FINESSE or
UNIRAS), so that users can easily swap between them. FROG comes with some built in
configurations, but users can also define their own, either for convenience during
testing or to build on FROG's functionality.

Hardware sets are represented in a [YAML](https://yaml.org) format. Custom hardware sets
can be created and imported into FROG. Here is an example:

```yaml
version: 1
name: My hardware set
devices:
  stepper_motor:
    class_name: stepper_motor.st10_controller.ST10Controller
    params:
      port: "0403:6011"
      baudrate: 9600
  temperature_controller.hot_bb:
    class_name: temperature.tc4820.TC4820
    params:
      port: "0403:6011 (2)"
      baudrate: 115200
  temperature_controller.cold_bb:
    class_name: temperature.tc4820.TC4820
    params:
      port: "0403:6011 (3)"
      baudrate: 115200
  temperature_monitor:
    class_name: temperature.dp9800.DP9800
    params:
      port: "0403:6001"
      baudrate: 38400
  sensors:
    class_name: sensors.em27_sensors.EM27Sensors
  spectrometer:
    class_name: spectrometer.opus_interface.OPUSInterface
    params:
      host: 10.10.0.2
      port: 80
```

The `version` indicates the version number of the hardware set definition, currently 1.
The `name` property defines a human-readable name for the hardware set, to be displayed
in the GUI and the `devices` property contains information about the devices in this
hardware set. The `devices` array consists of key-value pairs, with the keys
corresponding to device base types (see [Hardware]). The values are YAML objects with a
`class_name` property and (optionally) a `params` property. `class_name` is a string
corresponding to the Python class name, along with the last part of the module name (all
plugins are in the `frog.hardware.plugins` module, so this part is omitted). `params`
is also a YAML object, containing key-value pairs for each of the device parameters (see
[Hardware] again). If any of the parameters are omitted, their default values will be
used.

Note that the port names for USB devices are in a FROG-specific format (non-USB serial
devices are just listed with the port name, e.g. COM3). The string is composed of the
USB vendor and product IDs and (optionally) a number to distinguish ports which share
all these properties (as happens with USB-to-serial devices with multiple ports, for
example). The easiest way to figure out these strings is to run FROG and click on
"Manage devices". The available USB ports will be listed in the dialog.

[Hardware]: ./hardware.md
