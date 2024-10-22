import math

class AstroConversion:
    def __init__(self, observer_latitude, observer_longitude, observer_altitude):
        # Observer's geographic coordinates
        self.lat = math.radians(observer_latitude)
        self.lon = math.radians(observer_longitude)
        self.altitude = observer_altitude  # In meters

    def azimuth_to_ra_dec(self, azimuth, altitude):
        # Convert azimuth and altitude to right ascension (RA) and declination (Dec)

        # Convert degrees to radians
        azimuth_rad = math.radians(azimuth)
        altitude_rad = math.radians(altitude)

        # Calculate the declination (Dec)
        dec = math.asin(math.sin(altitude_rad) * math.sin(self.lat) +
                        math.cos(altitude_rad) * math.cos(self.lat) * math.cos(azimuth_rad))
        
        # Calculate the hour angle (H)
        h = math.acos((math.sin(altitude_rad) - math.sin(self.lat) * math.sin(dec)) /
                       (math.cos(self.lat) * math.cos(dec)))
        
        # Right Ascension (RA) calculation
        if math.sin(azimuth_rad) > 0:
            ra = (self.lon + h) % (2 * math.pi)  # Adjust for the correct quadrant
        else:
            ra = (self.lon - h) % (2 * math.pi)

        # Convert RA and Dec back to degrees
        ra_deg = math.degrees(ra)
        dec_deg = math.degrees(dec)

        return ra_deg, dec_deg