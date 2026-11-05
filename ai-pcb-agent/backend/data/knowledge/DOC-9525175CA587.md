# PCB Forge Demo Engineering Notes

> DEMO DATA ONLY — Every component, value, limit, and recommendation in this file is fictional and created only to test PCB Forge document upload, search, and evidence citations. Do not use it to design or manufacture real hardware.

## Demo project

Project: PF-SENSOR-01 fictional environmental sensor controller
Board: 2-layer FR-4, nominal outline 50 mm × 40 mm
Nominal board thickness: 1.6 mm
Copper weight: 1 oz on both layers
Operating temperature target: 0 °C to 50 °C

## Fictional component notes

### U1 — DEMO-MCU-A

The fictional DEMO-MCU-A is a 3.3 V microcontroller for this demonstration project. The demo note recommends placing one 100 nF decoupling capacitor near each power pin. This is an invented example requirement, not a real datasheet specification.

### U2 — DEMO-SENSOR-B

The fictional DEMO-SENSOR-B communicates over I²C. The demo design uses a 4.7 kΩ pull-up resistor on SDA and another 4.7 kΩ pull-up resistor on SCL. The example I²C bus speed is 100 kHz.

### J1 — DEMO-USB-C

The fictional USB connector supplies nominal 5 V to the board. A separate 3.3 V regulator powers U1 and U2. These values are included only as searchable demo facts.

## Fictional layout and fabrication notes

- Demo minimum trace width: 0.20 mm.
- Demo minimum clearance: 0.20 mm.
- Demo minimum via drill: 0.30 mm.
- Demo copper-to-board-edge distance: at least 0.30 mm.
- Keep the sensor area away from the demo USB power input section.
- The demo fabrication estimate assumes standard FR-4 and a green solder mask.

These limits are invented solely to test retrieval. They are not a substitute for a real fabricator's capabilities or design rules.

## Fictional validation record

A demonstration bench check recorded 3.30 V at the sensor supply test point. The example I²C scan detected one device at address 0x48. The example room-temperature reading was 24.0 °C. All readings in this section are synthetic test data.

## Suggested questions for testing PCB Forge

1. What is the demo minimum trace width, and which note says so?
2. What pull-up resistor values are used for SDA and SCL?
3. What voltage was recorded at the sensor supply test point?
4. Which I²C address did the fictional bench scan detect?
5. What evidence does the demo note give for keeping the sensor area away from USB power?
6. Does this file contain real manufacturer specifications?
