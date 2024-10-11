# hass-comapsmarthome
A Home Assistant custom component for comap smart home thermostats (qivivo)

## Supported features
This is designed for Qivivo Fil Pilote thermostats.

It will set up :
* 1 device for the main housing  with the following entities :
    * 1 sensor entity providing informations about the house
    * 1 sensor entity providing informations about the comap network bridge
    * a select entity allowing to change the schedule for all zone at once
    * a select entity to choose active program
    * a switch do turn on/of the heating system at a home level
    * a switch to manage absence mode
    * a switch to manage holiday mode

* 1 device per zone with the following sensors :
    * a select entity allowing to change the schedule at a zone level
    * a sensor entity providing information about the heating module
    * a climate entity
    * a presence entity (if a thermostat is attached to the zone)
    * a battery sensor entity (if a thermostat is attached to the zone)
    * a thermostat sensor providing more information about the zone thermostat

Features :

* Multi-zone support
* Thermostat zone: set temperature, current temperature and humidity
* Pilot wire zone: set preset mode
* Set home away, home back for housing
* Set schedule per zone or for all zones at once
* polling interval is customizable for sensors and for selects (schedules)

Does not support:

* Mulitple housings
* Other type of Comap thermal devices than pilot wire

## Current limitations

* Polling interval is not customizable for climate entities (30 sec for all climate entities)
* Any manual instruction is set for 2 hours by default
* Your applied schedule will cancel any temporary orders - this is Comap behavior


## Configuration

You can deploy the component to custom_components directory in you home assistant config directory, or use HACS by pointing to this repository.

Setup through the Home Assistant Integration menu - you will need your Comap username and password.
During setup, you'll be able to choose polling interval for sensors and selects

## Unsupported features

* This integration will never make coffe or interact with your washing machine ;-)

## THANK YOU !

Many thanks to :
 * Romain Biremon for his initial work on comap smart home intergration : https://github.com/rbiremon/hass-comapsmarthome
 * petit-pierre melec for his python api, from which i took many useful information : https://gitlab.com/melec

