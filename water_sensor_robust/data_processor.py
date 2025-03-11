class DataProcessor:
    def __init__(self, tank_height, tank_length, tank_width):
        self.tank_height = tank_height
        self.tank_length = tank_length
        self.tank_width = tank_width

    def calculate_volume(self, distance):
        height_filled = self.tank_height - distance
        volume = (height_filled * self.tank_length * self.tank_width) / 1000
        return max(0, volume)  # Ensure non-negative volume
    
    def calculate_tank_size(self):
        volume = (self.tank_height * self.tank_length * self.tank_width) / 1000
        return max(0, volume)  # Ensure non-negative volume