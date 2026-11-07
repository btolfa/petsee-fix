# Mirror the raw Tracker stream into Traccar's native Topin decoder, on our own Traccar build

We want the Tracker's positions in a self-hosted Traccar while the Vendor Cloud and Vendor App keep working. The Tracker speaks the Topin protocol, which Traccar already decodes, so petsee sends a Mirror (the unmodified bytes, taken before the Hemisphere Bug correction) to Traccar's Topin port and discards everything Traccar sends back. Traccar is a passive observer: it never commands the Tracker, and its failures never affect the path to the Vendor Cloud.

Our Tracker reports cell towers in an LTE layout (4-byte LAC, 4-byte CID) that upstream Topin decodes as 2+2 bytes. We patch the decoder to read only the LTE layout, with no format detection, and run our own image: the official `traccar/traccar` image of the same version with only `tracker-server.jar` replaced. The patch lives in this repo and is deliberately not sent upstream.

## Considered Options

- **OsmAnd adapter** (petsee decodes and posts HTTP to Traccar): rejected because it duplicates a decoder Traccar already has, adds a second wire format to maintain, and still needs petsee to decode Network Scans, status, and alarms itself.
- **Tracker reports to Traccar directly**: rejected because it drops the Vendor Cloud, the Vendor App, and the Tracker settings the Vendor Cloud manages.

## Consequences

- Every Traccar upgrade means bumping the pinned version and re-applying the patch.
- Commands from Traccar to the Tracker are not supported.
