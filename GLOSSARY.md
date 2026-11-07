# Petsee

Petsee sits between a pet GPS tracker and the vendor's cloud, correcting what the vendor app shows and making the tracker's data available to other systems.

## Language

**Tracker**:
The physical pet GPS device, identified by its IMEI.
_Avoid_: device, collar, client

**Vendor Cloud**:
The tracker manufacturer's server at `apptrackpets.com:5455` that the Tracker reports to.
_Avoid_: upstream, apptrackpets server

**Vendor App**:
The manufacturer's mobile app that shows positions from the Vendor Cloud.
_Avoid_: the app, client app

**Traccar**:
The self-hosted tracking server that receives the Mirror and turns it into positions; a passive observer that never sends anything back to the Tracker.
_Avoid_: tracking backend, our server

**Mirror**:
An unmodified copy of the Tracker's byte stream, taken before any correction, delivered to Traccar.
_Avoid_: adapter, tee, bridge, forwarder

**Topin protocol**:
The binary protocol the Tracker speaks: `78 78 | count/len | type | payload | 0D 0A`, no serial number or checksum.
_Avoid_: GT06, GT06 variant, Concox

**GPS Fix**:
A Tracker message carrying satellite coordinates (type `0x10`).
_Avoid_: GPS packet, location

**Network Scan**:
A Tracker message carrying nearby WiFi access points and cell towers but no coordinates (type `0x1A`); a position must be derived from it by geolocation.
_Avoid_: WiFi packet, LBS packet

**Hemisphere Bug**:
The Vendor App's inverted reading of the latitude/longitude hemisphere bits in a GPS Fix, which mirrors positions into the wrong hemisphere.
_Avoid_: coordinate bug, sign bug
