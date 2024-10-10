# hass-comapsmarthome
A Home Assistant custom component for comap smart home thermostats (qivivo)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jhenninot&repository=hass-comapsmarthome)

## Supported features
This is designed for Qivivo Fil Pilote thermostats.

It will set up :
* 1 device for the main housing  with the following entities :
    * 1 sensor  entity dedicated to main information about the housing
    * 1 sensor  entity dedicated to the comap network bridge
    * a select  entity allowing to change the schedule for all zonez at once

* 1 device per zone with the following sensors :
    * a select entity allowing to change the schedule fot the zone
    * a sensor  entity deticated to the heating module
    * a climate entity
    * a presence entity (if a thermostat is attached to the zone)
    * a battery sensor entity (if a thermostat is attached to the zone)

Features :

* Multi-zone support
* Thermostat zone: set temperature, current temperature and humidity
* Pilot wire zone: set preset mode
* Set home away, home back for housing
* Set schedule per zone or for all zones at once
* polling interval is customizable for sensors and for selects (schedules)

Does not support:

* Mulitple housings
* Programs (a program is a set of schedules to apply to your different zones)
* Other type of Comap thermal devices than pilot wire

## Current limitations

* Polling interval is not customizable for climates and switches
* Any manual instruction is set for 2 hours by default
* Your applied schedule will cancel any temporary orders - this is Comap behavior


## Configuration

You can deploy the component to custom_components directory in you home assistant config directory, or use HACS by pointing to this repository.

Setup through the Home Assistant Integration menu - you will need your Comap username and password.
